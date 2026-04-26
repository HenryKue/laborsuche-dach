"""Usage: python scripts/scrape_providers.py --input data/bodycomp_provider_url.json --output output/bodycomp_providers.json"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "street": {"type": ["string", "null"], "description": "Street and house number of the practice itself."},
        "postal_code": {"type": ["string", "null"], "description": "Postal code of the practice."},
        "city": {"type": ["string", "null"], "description": "City of the practice."},
        "country": {"type": ["string", "null"], "description": "Country name or ISO code of the practice."},
        "phone": {"type": ["string", "null"], "description": "Public phone number as printed on the page."},
        "email": {"type": ["string", "null"], "description": "Public contact email address."},
        "website": {"type": ["string", "null"], "description": "Homepage URL of the practice."},
    },
    "required": ["street", "postal_code", "city", "country", "phone", "email", "website"],
}

EXTRACTION_PROMPT = (
    "Extract the contact details of THE MEDICAL PRACTICE / CLINIC ITSELF. "
    "ONLY extract data that is EXPLICITLY PRINTED as contact information on the "
    "page (e.g. in a contact section, footer, sidebar, or Impressum block). "
    "Do NOT extract or infer addresses from article text, medical descriptions, "
    "or general page content — if there is no clearly formatted contact block, "
    "return null for ALL address fields. "
    "If the page is an Impressum that lists an IT or web-hosting provider, "
    "extract the practice's address, NOT the host's. "
    "If the page lists MULTIPLE LOCATIONS, extract the one whose name or address "
    "matches the URL path (e.g. /diagnostikum-linz/ → the Linz location). "
    "If a field is not present or not clearly readable, return JSON null (not the "
    "string \"null\"). Do not invent, guess, or hallucinate any value. "
    "The phone number should include the international prefix (e.g. +49 or +43)."
)

IMPRESSUM_PATHS = (
    "/impressum", "/de/impressum",
    "/kontakt", "/de/kontakt",
    "/contact", "/de/contact",
)

_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_PHONE_OK_RE = re.compile(r"^\+[0-9 ]+$")
_COUNTRY_NAMES = {
    "DEUTSCHLAND": "DE", "GERMANY": "DE", "GER": "DE",
    "OESTERREICH": "AT", "AUSTRIA": "AT",
    "SCHWEIZ": "CH", "SWITZERLAND": "CH", "SUISSE": "CH", "SVIZZERA": "CH",
}


def load_api_key() -> str:
    """Load FIRECRAWL_API_KEY from .env in project root, falling back to process env."""
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        sys.stderr.write(
            "WARN: python-dotenv not installed; reading FIRECRAWL_API_KEY from process env only.\n"
        )
    key = os.environ.get("FIRECRAWL_API_KEY")
    if not key:
        sys.stderr.write(
            "ERROR: FIRECRAWL_API_KEY not set. Add it to .env or export it.\n"
        )
        sys.exit(2)
    return key


def normalize_phone(raw: Any) -> str | None:
    """Normalize a phone string to '^\\+[0-9 ]+$'. Returns None if not recoverable."""
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    if _EMAIL_RE.search(s):
        return None
    s = re.sub(r"(?i)^(tel(?:efon)?|phone|fon|fax)\.?\s*[:.]?\s*", "", s).strip()
    s = re.sub(r"[\-/().‐-―]", " ", s)
    if re.search(r"[^\d+\s]", s):
        return None
    s = re.sub(r"\s+", " ", s).strip()
    if s.startswith("00"):
        s = "+" + s[2:].lstrip()
    if not s.startswith("+"):
        return None
    if "+" in s[1:]:
        return None
    s = re.sub(r"\s+", " ", s).strip()
    if not _PHONE_OK_RE.match(s):
        return None
    digits = re.sub(r"\D", "", s)
    if len(digits) < 7:
        return None
    return s


def infer_country_from_tld(url: str | None) -> str | None:
    """Map .de/.at/.ch TLDs to ISO codes. Returns None for anything else."""
    if not isinstance(url, str) or not url:
        return None
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return None
    if not host:
        return None
    host = host.split(":", 1)[0]
    if host.endswith(".de"):
        return "DE"
    if host.endswith(".at"):
        return "AT"
    if host.endswith(".ch"):
        return "CH"
    return None


def normalize_country(raw: Any, source_url: str | None) -> str | None:
    """Return ISO 3166-1 alpha-2 code, falling back to TLD of source_url."""
    if isinstance(raw, str):
        s = raw.strip().upper().replace("Ö", "OE").replace("Ä", "AE").replace("Ü", "UE")
        if s in _COUNTRY_NAMES:
            return _COUNTRY_NAMES[s]
        if re.fullmatch(r"[A-Z]{2}", s):
            return s
    return infer_country_from_tld(source_url)


def homepage_from_url(url: str | None) -> str | None:
    """Reduce any URL to its scheme://host/ form."""
    if not isinstance(url, str) or not url:
        return None
    try:
        p = urlparse(url)
    except Exception:
        return None
    if not p.scheme or not p.netloc:
        return None
    return f"{p.scheme}://{p.netloc}/"


_NULL_STRINGS = frozenset({"null", "none", "n/a", "na", "nicht verfügbar", "nicht vorhanden", "-", "—"})


def _sanitize_null(v: Any) -> Any:
    """Turn LLM-returned pseudo-null strings into real None."""
    if isinstance(v, str) and v.strip().lower() in _NULL_STRINGS:
        return None
    return v


def _sanitize_scraped(d: dict[str, Any]) -> dict[str, Any]:
    """Sanitize all values from LLM extraction — turn 'null' strings into None."""
    return {k: _sanitize_null(v) for k, v in d.items()}


def _empty_str(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _has_address(d: dict[str, Any]) -> bool:
    return all(not _empty_str(d.get(k)) for k in ("street", "postal_code", "city"))


def _make_client(api_key: str):
    """Return a callable scrape(url) -> dict, using firecrawl-py if available, else HTTP."""
    try:
        from firecrawl import FirecrawlApp, JsonConfig  # type: ignore
    except ImportError:
        import requests

        def _scrape_http(url: str) -> dict[str, Any]:
            resp = requests.post(
                "https://api.firecrawl.dev/v1/scrape",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": url,
                    "formats": ["json"],
                    "jsonOptions": {
                        "prompt": EXTRACTION_PROMPT,
                        "schema": EXTRACTION_SCHEMA,
                    },
                    "parsePDF": True,
                    "waitFor": 3000,
                },
                timeout=120,
            )
            resp.raise_for_status()
            payload = resp.json()
            data = (payload.get("data") or {}).get("json") or payload.get("json")
            return data or {}

        return _scrape_http

    client = FirecrawlApp(api_key=api_key)
    json_cfg = JsonConfig(prompt=EXTRACTION_PROMPT, schema=EXTRACTION_SCHEMA)

    def _scrape_sdk(url: str) -> dict[str, Any]:
        res = client.scrape_url(
            url,
            formats=["json"],
            json_options=json_cfg,
            parse_pdf=True,
            wait_for=3000,
        )
        data = getattr(res, "json", None)
        if data is None and isinstance(res, dict):
            data = res.get("json") or (res.get("data") or {}).get("json")
        return data or {}

    return _scrape_sdk


def scrape_extract(scrape_fn, url: str, *, max_attempts: int = 3) -> dict[str, Any]:
    """Call the scrape function with up to max_attempts retries (exponential backoff)."""
    delay = 4.0
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return scrape_fn(url) or {}
        except Exception as exc:  # noqa: BLE001 - re-raised after retry budget
            last_exc = exc
            if attempt == max_attempts:
                break
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"scrape failed for {url}: {last_exc}")


_CONTACT_FIELDS = ("street", "postal_code", "city", "phone", "email")


def _needs_fallback(d: dict[str, Any]) -> bool:
    """True if any contact field (address, phone, email) is still missing."""
    return any(_empty_str(d.get(k)) for k in _CONTACT_FIELDS)


def extract_provider(scrape_fn, source_url: str) -> tuple[dict[str, Any], list[str]]:
    """Scrape source_url; if any contact fields are missing, try fallback pages.

    Returns (merged_data, urls_attempted).
    """
    attempted: list[str] = []
    primary = _sanitize_scraped(scrape_extract(scrape_fn, source_url))
    attempted.append(source_url)
    merged = {k: primary.get(k) for k in EXTRACTION_SCHEMA["properties"]}
    if not _needs_fallback(merged):
        return merged, attempted

    parsed = urlparse(source_url)
    if not parsed.scheme or not parsed.netloc:
        return merged, attempted
    base = f"{parsed.scheme}://{parsed.netloc}"
    for path in IMPRESSUM_PATHS:
        candidate = urljoin(base, path)
        if candidate == source_url or candidate in attempted:
            continue
        time.sleep(7)
        try:
            fb = _sanitize_scraped(scrape_extract(scrape_fn, candidate))
        except Exception as exc:  # noqa: BLE001 - log and continue with next fallback
            sys.stderr.write(f"  fallback {candidate} failed: {exc}\n")
            attempted.append(candidate)
            continue
        attempted.append(candidate)
        for key, value in fb.items():
            if _empty_str(merged.get(key)) and not _empty_str(value):
                merged[key] = value
        if not _needs_fallback(merged):
            break
    return merged, attempted


def build_record(input_entry: dict[str, Any], scraped: dict[str, Any]) -> dict[str, Any]:
    """Assemble a schema-compliant record from input + scraped fields."""
    source_url = input_entry["url"]
    name = input_entry.get("name") or ""
    website_raw = scraped.get("website") or source_url
    website = homepage_from_url(website_raw)

    email = scraped.get("email")
    if isinstance(email, str):
        email = email.strip() or None
    if not isinstance(email, str):
        email = None

    return {
        "name": name.strip() if isinstance(name, str) else "",
        "street": (scraped.get("street") or "").strip() if isinstance(scraped.get("street"), str) else "",
        "postal_code": (scraped.get("postal_code") or "").strip() if isinstance(scraped.get("postal_code"), str) else "",
        "city": (scraped.get("city") or "").strip() if isinstance(scraped.get("city"), str) else "",
        "country": normalize_country(scraped.get("country"), source_url) or "",
        "latitude": None,
        "longitude": None,
        "phone": normalize_phone(scraped.get("phone")),
        "email": email,
        "website": website,
        "source_url": source_url,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "services": [],
    }


def _empty_record(input_entry: dict[str, Any]) -> dict[str, Any]:
    """Build a blank record template for entries that need manual editing."""
    source_url = input_entry["url"]
    return {
        "name": input_entry.get("name") or "",
        "street": "",
        "postal_code": "",
        "city": "",
        "country": infer_country_from_tld(source_url) or "",
        "latitude": None,
        "longitude": None,
        "phone": None,
        "email": None,
        "website": homepage_from_url(source_url),
        "source_url": source_url,
        "verified_at": "",
        "services": [],
    }


def is_complete(record: dict[str, Any]) -> bool:
    """Schema-mandatory fields are non-empty strings."""
    for k in ("name", "street", "postal_code", "city", "country"):
        v = record.get(k)
        if not isinstance(v, str) or not v.strip():
            return False
    return True


def load_input(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Input {path} must be a JSON array.")
    cleaned: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        url = entry.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        if not entry.get("name"):
            continue
        cleaned.append(entry)
    return cleaned


_IGNORE_FOR_DUP_CHECK = frozenset(
    {"verified_at", "country", "city", "postal_code", "latitude", "longitude", "services"}
)


def _find_possible_duplicates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag records that share a non-trivial field value with another record.

    Returns the subset of records where at least one compared field has the same
    value as in a different record.  Fields in _IGNORE_FOR_DUP_CHECK are skipped,
    and null / empty-string values are never treated as duplicates.
    Uses the record's index in the list as identifier (source_url for final lookup).
    """
    compared_keys = [
        k for k in (records[0] if records else {})
        if k not in _IGNORE_FOR_DUP_CHECK
    ]
    # Build value→set-of-indices index per field
    index: dict[str, dict[str, set[int]]] = {k: {} for k in compared_keys}
    for i, rec in enumerate(records):
        for k in compared_keys:
            v = rec.get(k)
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            vstr = str(v)
            index[k].setdefault(vstr, set()).add(i)

    flagged: set[int] = set()
    for k in compared_keys:
        for _val, indices in index[k].items():
            if len(indices) > 1:
                flagged.update(indices)

    return [records[i] for i in sorted(flagged)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape provider contact data via Firecrawl.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--sleep",
        type=float,
        default=7.0,
        help="Seconds between consecutive Firecrawl calls (free tier: 10 req/min).",
    )
    args = parser.parse_args(argv)

    api_key = load_api_key()
    scrape_fn = _make_client(api_key)

    entries = load_input(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    try:
        from tqdm import tqdm  # type: ignore
        iterator = tqdm(entries, desc="Scraping", unit="provider")
    except ImportError:
        sys.stderr.write("WARN: tqdm not installed; running without progress bar.\n")
        iterator = entries

    complete: list[dict[str, Any]] = []
    manual: list[dict[str, Any]] = []

    for i, entry in enumerate(iterator):
        if i > 0:
            time.sleep(args.sleep)
        try:
            scraped, attempted = extract_provider(scrape_fn, entry["url"])
            record = build_record(entry, scraped)
            if is_complete(record):
                complete.append(record)
            else:
                missing = [
                    k for k in ("name", "street", "postal_code", "city", "country")
                    if not (isinstance(record.get(k), str) and record[k].strip())
                ]
                manual.append(record)
                sys.stderr.write(f"  incomplete: {entry['name']} missing={missing}\n")
        except Exception as exc:  # noqa: BLE001 - logged to manual file
            sys.stderr.write(f"  error: {entry['name']} {entry['url']} -> {exc}\n")
            manual.append(_empty_record(entry))

    args.output.write_text(
        json.dumps(complete, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manual_path = args.output.with_suffix(".manual.json")
    if manual:
        manual_path.write_text(
            json.dumps(manual, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        sys.stderr.write(
            f"Wrote {len(complete)} complete records to {args.output}; "
            f"{len(manual)} records need manual editing in {manual_path}\n"
        )
    else:
        if manual_path.exists():
            manual_path.unlink()
        sys.stderr.write(f"Wrote {len(complete)} records to {args.output}\n")

    duplicates = _find_possible_duplicates(complete)
    dup_path = args.output.with_suffix(".possible_errors.json")
    if duplicates:
        dup_path.write_text(
            json.dumps(duplicates, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        sys.stderr.write(
            f"{len(duplicates)} records with shared field values written to {dup_path}\n"
        )
    else:
        if dup_path.exists():
            dup_path.unlink()

    return 0


if __name__ == "__main__":
    sys.exit(main())
