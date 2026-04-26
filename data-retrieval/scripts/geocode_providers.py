"""Usage: python scripts/geocode_providers.py output/bodycomp_providers.json [--force] [--cache data/geocode_cache.json]"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_env() -> str:
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        sys.stderr.write(
            "WARN: python-dotenv not installed; reading NOMINATIM_USER_AGENT from process env only.\n"
        )
    ua = os.environ.get("NOMINATIM_USER_AGENT")
    if not ua:
        sys.stderr.write(
            "ERROR: NOMINATIM_USER_AGENT not set. Add it to .env or export it.\n"
        )
        sys.exit(2)
    return ua


def make_cache_key(street: str, postal_code: str, city: str, country: str) -> str:
    normalized = "|".join(s.strip().lower() for s in (street, postal_code, city, country))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        if sys.platform == "win32" and path.exists():
            path.unlink()
        os.rename(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def create_geocoder(user_agent: str):
    from geopy.geocoders import Nominatim  # type: ignore
    from geopy.extra.rate_limiter import RateLimiter  # type: ignore

    geolocator = Nominatim(user_agent=user_agent)
    return RateLimiter(geolocator.geocode, min_delay_seconds=1.1)


def plausibility_check(location: Any, expected_country: str) -> bool:
    if location is None:
        return False
    address = (location.raw or {}).get("address", {})
    return address.get("country_code", "").upper() == expected_country.upper()


def format_coord(value: float) -> float:
    """Round to 7 decimal places (~1cm precision) and return as float."""
    return round(value, 7)


def _needs_geocoding(provider: dict[str, Any]) -> bool:
    lat = provider.get("latitude")
    lon = provider.get("longitude")
    return lat is None or lon is None


def geocode_one(
    geocode_fn: Any,
    provider: dict[str, Any],
    cache: dict[str, Any],
) -> tuple[float | None, float | None, str | None]:
    street = provider.get("street") or ""
    postal_code = provider.get("postal_code") or ""
    city = provider.get("city") or ""
    country = provider.get("country") or ""

    if not street.strip() or not city.strip():
        return None, None, "missing street or city"

    key = make_cache_key(street, postal_code, city, country)

    if key in cache:
        entry = cache[key]
        lat_c = entry.get("lat")
        lon_c = entry.get("lon")
        if lat_c is not None:
            lat_c = float(lat_c)
        if lon_c is not None:
            lon_c = float(lon_c)
        return lat_c, lon_c, entry.get("error")

    try:
        location = geocode_fn(
            query={
                "street": street,
                "postalcode": postal_code,
                "city": city,
                "country": country,
            },
            addressdetails=True,
        )
    except Exception as exc:
        error_msg = f"geocoder error: {exc}"
        cache[key] = {
            "lat": None, "lon": None,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "error": error_msg,
        }
        return None, None, error_msg

    if location is None:
        error_msg = "no result from Nominatim"
        cache[key] = {
            "lat": None, "lon": None,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "error": error_msg,
        }
        return None, None, error_msg

    if not plausibility_check(location, country):
        result_cc = (location.raw or {}).get("address", {}).get("country_code", "??").upper()
        error_msg = f"country mismatch: expected {country}, got {result_cc}"
        cache[key] = {
            "lat": None, "lon": None,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "error": error_msg,
        }
        return None, None, error_msg

    lat = format_coord(location.latitude)
    lon = format_coord(location.longitude)
    cache[key] = {
        "lat": lat, "lon": lon,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }
    return lat, lon, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Geocode providers using Nominatim (Stage 2).")
    parser.add_argument("input", type=Path, help="Providers JSON file (updated in-place).")
    parser.add_argument("--force", action="store_true", help="Re-geocode records that already have coordinates.")
    parser.add_argument(
        "--cache", type=Path,
        default=PROJECT_ROOT / "data" / "geocode_cache.json",
        help="Path to geocode cache file.",
    )
    args = parser.parse_args(argv)

    user_agent = load_env()

    providers = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(providers, list):
        sys.stderr.write(f"ERROR: {args.input} must contain a JSON array.\n")
        return 1

    cache = load_cache(args.cache)
    geocode_fn = create_geocoder(user_agent)

    to_geocode = [
        (i, p) for i, p in enumerate(providers)
        if args.force or _needs_geocoding(p)
    ]

    if not to_geocode:
        sys.stderr.write("All records already geocoded. Nothing to do.\n")
        return 0

    try:
        from tqdm import tqdm  # type: ignore
        iterator = tqdm(to_geocode, desc="Geocoding", unit="provider")
    except ImportError:
        sys.stderr.write("WARN: tqdm not installed; running without progress bar.\n")
        iterator = to_geocode

    errors: list[dict[str, Any]] = []
    geocoded_count = 0

    for idx, provider in iterator:
        lat, lon, error = geocode_one(geocode_fn, provider, cache)
        if error:
            errors.append({
                "name": provider.get("name"),
                "address": f"{provider.get('street')}, {provider.get('postal_code')} {provider.get('city')}, {provider.get('country')}",
                "error": error,
            })
            sys.stderr.write(f"  {provider.get('name')}: {error}\n")
            providers[idx]["latitude"] = None
            providers[idx]["longitude"] = None
        else:
            providers[idx]["latitude"] = lat
            providers[idx]["longitude"] = lon
            geocoded_count += 1

    _write_json_atomic(args.input, providers)
    _write_json_atomic(args.cache, cache)

    error_path = args.input.with_suffix(".geocode-errors.json")
    if errors:
        _write_json_atomic(error_path, errors)
        sys.stderr.write(f"\n{geocoded_count} geocoded, {len(errors)} errors -> {error_path}\n")
    else:
        if error_path.exists():
            error_path.unlink()
        sys.stderr.write(f"\n{geocoded_count} geocoded, 0 errors.\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
