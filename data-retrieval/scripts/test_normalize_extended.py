"""Extended unit tests for scrape_providers.py.

Focuses on:
- build_record  (no existing coverage)
- is_complete   (no existing coverage)
- Additional edge-cases for normalize_phone, normalize_country,
  homepage_from_url, infer_country_from_tld not already in test_normalize.py

Run:
    python -m unittest scripts.test_normalize_extended
or:
    python scripts/test_normalize_extended.py
"""

from __future__ import annotations

import re
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scrape_providers import (  # noqa: E402
    build_record,
    homepage_from_url,
    infer_country_from_tld,
    is_complete,
    normalize_country,
    normalize_phone,
)

PHONE_PATTERN = re.compile(r"^\+[0-9 ]+$")
ISO8601_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+\d{2}:\d{2}$"
)


# ---------------------------------------------------------------------------
# normalize_phone — additional edge cases
# ---------------------------------------------------------------------------

class NormalizePhoneExtendedTests(unittest.TestCase):

    # Label variants
    def test_telefon_label_full_word(self):
        result = normalize_phone("Telefon: +43 1 9876543")
        self.assertIsNotNone(result)
        self.assertRegex(result, PHONE_PATTERN)
        self.assertEqual(result, "+43 1 9876543")

    def test_fon_label(self):
        result = normalize_phone("Fon +41 44 123 45 67")
        self.assertIsNotNone(result)
        self.assertRegex(result, PHONE_PATTERN)

    def test_phone_label_english(self):
        result = normalize_phone("Phone: +49 89 12345678")
        self.assertIsNotNone(result)
        self.assertRegex(result, PHONE_PATTERN)

    def test_fax_label_strips(self):
        # "Fax" label should be stripped and number parsed
        result = normalize_phone("Fax. +49 30 9876543")
        self.assertIsNotNone(result)
        self.assertRegex(result, PHONE_PATTERN)

    # Swiss numbers
    def test_swiss_number(self):
        result = normalize_phone("+41 44 987 65 43")
        self.assertIsNotNone(result)
        self.assertEqual(result, "+41 44 987 65 43")

    def test_swiss_double_zero(self):
        result = normalize_phone("0041 44 987 65 43")
        self.assertIsNotNone(result)
        self.assertRegex(result, PHONE_PATTERN)
        self.assertTrue(result.startswith("+41"))

    # Austrian number with parenthesised trunk code
    def test_austrian_parens_trunk(self):
        result = normalize_phone("+43 (0)1 234 5678")
        self.assertIsNotNone(result)
        self.assertRegex(result, PHONE_PATTERN)

    # Exactly 7 digits (boundary: minimum allowed)
    def test_exactly_seven_digits_passes(self):
        result = normalize_phone("+49 123456 7")
        # seven digits total after country code stripping is >7 combined with cc
        # +491234567 = 9 digits total so this should pass
        self.assertIsNotNone(result)

    def test_six_digits_total_returns_none(self):
        # +49 12 345 -> digits = 491 2345 = 7; edge: just +49 1234 = 6 non-cc digits
        # We want a case where total digit count (including cc) < 7
        result = normalize_phone("+12 3456")
        # +12 3456 -> digits=123456 -> 6 digits < 7 -> None
        self.assertIsNone(result)

    # bool input (subtype of int in Python)
    def test_bool_input_returns_none(self):
        self.assertIsNone(normalize_phone(True))
        self.assertIsNone(normalize_phone(False))

    # dict/list input
    def test_dict_input_returns_none(self):
        self.assertIsNone(normalize_phone({"number": "+49 30 123"}))

    # Whitespace-only after label strip
    def test_only_label_no_number(self):
        self.assertIsNone(normalize_phone("Tel.:"))
        self.assertIsNone(normalize_phone("Telefon:"))

    # Number with extension marker — letters after digits
    def test_letters_at_end_returns_none(self):
        self.assertIsNone(normalize_phone("+49 30 12345 ext"))

    # Hyphen-only junk
    def test_dash_only_returns_none(self):
        self.assertIsNone(normalize_phone("---"))

    # Already-valid input unchanged
    def test_already_valid_passthrough(self):
        self.assertEqual(normalize_phone("+49 30 12345678"), "+49 30 12345678")

    # Output always matches schema when not None
    def test_all_valid_outputs_match_schema(self):
        cases = [
            "Telefon: +43 1 9876543",
            "+41 44 987 65 43",
            "0041 44 987 65 43",
            "+49 (0)511/123-7170",
        ]
        for raw in cases:
            with self.subTest(raw=raw):
                out = normalize_phone(raw)
                self.assertIsNotNone(out, f"Expected non-None for: {raw!r}")
                self.assertRegex(out, PHONE_PATTERN)


# ---------------------------------------------------------------------------
# normalize_country — additional edge cases
# ---------------------------------------------------------------------------

class NormalizeCountryExtendedTests(unittest.TestCase):

    def test_austria_english(self):
        self.assertEqual(normalize_country("Austria", None), "AT")

    def test_switzerland_english(self):
        self.assertEqual(normalize_country("Switzerland", None), "CH")

    def test_suisse_french(self):
        self.assertEqual(normalize_country("Suisse", None), "CH")

    def test_svizzera_italian(self):
        self.assertEqual(normalize_country("Svizzera", None), "CH")

    def test_ger_abbreviation(self):
        self.assertEqual(normalize_country("GER", None), "DE")

    def test_lowercase_austria(self):
        self.assertEqual(normalize_country("austria", None), "AT")

    def test_lowercase_schweiz(self):
        self.assertEqual(normalize_country("schweiz", None), "CH")

    def test_non_string_raw_falls_back_to_tld(self):
        self.assertEqual(normalize_country(123, "https://praxis.ch"), "CH")
        self.assertEqual(normalize_country(None, "https://klinik.at"), "AT")

    def test_three_letter_unknown_code_falls_back_to_tld(self):
        # "XYZ" is 3 chars, not a 2-letter ISO code, should fall back
        self.assertEqual(normalize_country("XYZ", "https://example.de"), "DE")

    def test_two_letter_unknown_code_accepted_as_is(self):
        # Any 2-letter string is passed through; "FR" is technically valid
        result = normalize_country("FR", None)
        self.assertEqual(result, "FR")

    def test_whitespace_raw_falls_back_to_tld(self):
        self.assertEqual(normalize_country("   ", "https://praxis.de"), "DE")

    def test_com_tld_with_no_raw_returns_none(self):
        self.assertIsNone(normalize_country(None, "https://example.com"))

    def test_both_none_returns_none(self):
        self.assertIsNone(normalize_country(None, None))


# ---------------------------------------------------------------------------
# homepage_from_url — additional edge cases
# ---------------------------------------------------------------------------

class HomepageFromUrlExtendedTests(unittest.TestCase):

    def test_http_scheme(self):
        self.assertEqual(homepage_from_url("http://example.de/foo"), "http://example.de/")

    def test_with_port(self):
        self.assertEqual(
            homepage_from_url("https://example.de:8080/path?q=1"),
            "https://example.de:8080/",
        )

    def test_non_string_types(self):
        self.assertIsNone(homepage_from_url(42))
        self.assertIsNone(homepage_from_url(["https://x.de"]))
        self.assertIsNone(homepage_from_url(None))

    def test_url_without_scheme(self):
        # No scheme -> netloc not parsed correctly by urlparse
        self.assertIsNone(homepage_from_url("www.example.de/path"))

    def test_just_slash(self):
        self.assertIsNone(homepage_from_url("/"))

    def test_ftp_scheme_preserved(self):
        result = homepage_from_url("ftp://files.example.de/pub/file.txt")
        self.assertEqual(result, "ftp://files.example.de/")

    def test_unicode_url(self):
        # Should not crash
        result = homepage_from_url("https://ärztehaus.de/kontakt")
        # urlparse handles unicode hosts
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# infer_country_from_tld — additional edge cases
# ---------------------------------------------------------------------------

class InferCountryFromTldExtendedTests(unittest.TestCase):

    def test_subdomain_de(self):
        self.assertEqual(infer_country_from_tld("https://sub.praxis.de/kontakt"), "DE")

    def test_subdomain_at(self):
        self.assertEqual(infer_country_from_tld("https://www.klinik.at/"), "AT")

    def test_co_uk_returns_none(self):
        self.assertIsNone(infer_country_from_tld("https://example.co.uk/"))

    def test_upper_case_url(self):
        # Should be case-insensitive on host
        self.assertEqual(infer_country_from_tld("HTTPS://EXAMPLE.DE/PATH"), "DE")

    def test_non_string_int(self):
        self.assertIsNone(infer_country_from_tld(99))

    def test_path_ending_in_de_not_host(self):
        # Path that ends in /de should not match; TLD is .com
        self.assertIsNone(infer_country_from_tld("https://example.com/de"))

    def test_http_scheme(self):
        self.assertEqual(infer_country_from_tld("http://example.ch/"), "CH")


# ---------------------------------------------------------------------------
# build_record — primary new coverage
# ---------------------------------------------------------------------------

def _make_entry(url="https://www.praxis-muster.de/leistungen"):
    return {"name": "Muster Praxis", "url": url}


def _make_scraped(**overrides):
    base = {
        "name": "Muster Praxis GmbH",
        "street": "Musterstraße 42",
        "postal_code": "10115",
        "city": "Berlin",
        "country": "Deutschland",
        "phone": "+49 30 12345678",
        "email": "info@muster-praxis.de",
        "website": "https://www.praxis-muster.de/deep/link",
    }
    base.update(overrides)
    return base


class BuildRecordSchemaFieldsTests(unittest.TestCase):
    """Verify that build_record always emits all required schema fields."""

    REQUIRED_FIELDS = (
        "name", "street", "postal_code", "city", "country",
        "latitude", "longitude", "phone", "email", "website",
        "source_url", "verified_at", "services",
    )

    def _full_record(self):
        return build_record(_make_entry(), _make_scraped())

    def test_all_required_fields_present(self):
        record = self._full_record()
        for field in self.REQUIRED_FIELDS:
            with self.subTest(field=field):
                self.assertIn(field, record)

    def test_latitude_always_none(self):
        self.assertIsNone(self._full_record()["latitude"])

    def test_longitude_always_none(self):
        self.assertIsNone(self._full_record()["longitude"])

    def test_services_always_empty_list(self):
        result = self._full_record()["services"]
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    def test_source_url_is_input_url_not_website(self):
        entry = _make_entry(url="https://www.praxis-muster.de/leistungen")
        scraped = _make_scraped(website="https://www.praxis-muster.de/")
        record = build_record(entry, scraped)
        self.assertEqual(record["source_url"], "https://www.praxis-muster.de/leistungen")
        self.assertNotEqual(record["source_url"], record["website"])

    def test_website_is_homepage_not_deep_link(self):
        entry = _make_entry(url="https://www.praxis-muster.de/leistungen")
        scraped = _make_scraped(website="https://www.praxis-muster.de/deep/link?foo=1")
        record = build_record(entry, scraped)
        self.assertEqual(record["website"], "https://www.praxis-muster.de/")

    def test_website_falls_back_to_source_url_homepage_when_scraped_missing(self):
        entry = _make_entry(url="https://www.praxis-muster.de/leistungen")
        scraped = _make_scraped(website=None)
        record = build_record(entry, scraped)
        self.assertEqual(record["website"], "https://www.praxis-muster.de/")

    def test_verified_at_is_iso8601(self):
        record = self._full_record()
        ts = record["verified_at"]
        self.assertIsInstance(ts, str)
        # Must parse without error
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError as exc:
            self.fail(f"verified_at is not valid ISO-8601: {ts!r} -> {exc}")
        self.assertIsNotNone(dt.tzinfo, "verified_at must be timezone-aware")

    def test_phone_normalised_in_record(self):
        scraped = _make_scraped(phone="+49 (0)30/12345-678")
        record = build_record(_make_entry(), scraped)
        phone = record["phone"]
        self.assertIsNotNone(phone)
        self.assertRegex(phone, PHONE_PATTERN)

    def test_phone_null_when_invalid(self):
        scraped = _make_scraped(phone="not-a-phone")
        record = build_record(_make_entry(), scraped)
        self.assertIsNone(record["phone"])

    def test_phone_null_when_scraped_missing(self):
        scraped = _make_scraped(phone=None)
        record = build_record(_make_entry(), scraped)
        self.assertIsNone(record["phone"])

    def test_email_null_when_scraped_none(self):
        scraped = _make_scraped(email=None)
        record = build_record(_make_entry(), scraped)
        self.assertIsNone(record["email"])

    def test_email_null_when_scraped_empty_string(self):
        scraped = _make_scraped(email="   ")
        record = build_record(_make_entry(), scraped)
        self.assertIsNone(record["email"])

    def test_email_preserved_when_valid(self):
        scraped = _make_scraped(email="info@muster-praxis.de")
        record = build_record(_make_entry(), scraped)
        self.assertEqual(record["email"], "info@muster-praxis.de")

    def test_country_normalised_from_full_name(self):
        scraped = _make_scraped(country="Österreich")
        record = build_record(_make_entry(url="https://klinik.at/"), scraped)
        self.assertEqual(record["country"], "AT")

    def test_country_falls_back_to_tld_when_scraped_missing(self):
        scraped = _make_scraped(country=None)
        record = build_record(_make_entry(url="https://praxis.ch/kontakt"), scraped)
        self.assertEqual(record["country"], "CH")

    def test_country_empty_string_when_no_signal(self):
        scraped = _make_scraped(country=None)
        record = build_record(
            _make_entry(url="https://example.com/about"), scraped
        )
        self.assertEqual(record["country"], "")

    def test_name_always_from_input(self):
        entry = _make_entry()
        entry["name"] = "Input Name"
        scraped = _make_scraped(name="Scraped Name GmbH")
        record = build_record(entry, scraped)
        self.assertEqual(record["name"], "Input Name")

    def test_name_fallback_to_input_when_scraped_missing(self):
        entry = _make_entry()
        entry["name"] = "Input Praxis"
        scraped = _make_scraped(name=None)
        record = build_record(entry, scraped)
        self.assertEqual(record["name"], "Input Praxis")

    def test_name_empty_string_when_both_missing(self):
        entry = {"name": "", "url": "https://example.de/"}
        scraped = _make_scraped(name=None)
        record = build_record(entry, scraped)
        self.assertEqual(record["name"], "")

    def test_street_stripped_of_whitespace(self):
        scraped = _make_scraped(street="  Hauptstraße 1  ")
        record = build_record(_make_entry(), scraped)
        self.assertEqual(record["street"], "Hauptstraße 1")

    def test_street_empty_string_when_scraped_none(self):
        scraped = _make_scraped(street=None)
        record = build_record(_make_entry(), scraped)
        self.assertEqual(record["street"], "")

    def test_postal_code_stripped(self):
        scraped = _make_scraped(postal_code=" 80331 ")
        record = build_record(_make_entry(), scraped)
        self.assertEqual(record["postal_code"], "80331")

    def test_city_empty_string_when_scraped_none(self):
        scraped = _make_scraped(city=None)
        record = build_record(_make_entry(), scraped)
        self.assertEqual(record["city"], "")

    def test_services_never_populated_from_scraped(self):
        # Even if scraped somehow had a 'services' key (it won't per schema),
        # the output must always be []
        scraped = _make_scraped()
        scraped["services"] = ["DEXA"]  # inject rogue key
        record = build_record(_make_entry(), scraped)
        self.assertEqual(record["services"], [])

    def test_latitude_longitude_never_populated(self):
        scraped = _make_scraped()
        scraped["latitude"] = "52.5200"  # inject rogue key
        scraped["longitude"] = "13.4050"
        record = build_record(_make_entry(), scraped)
        self.assertIsNone(record["latitude"])
        self.assertIsNone(record["longitude"])


# ---------------------------------------------------------------------------
# is_complete — primary new coverage
# ---------------------------------------------------------------------------

class IsCompleteTests(unittest.TestCase):

    def _complete_record(self):
        return {
            "name": "Muster Praxis",
            "street": "Musterstraße 1",
            "postal_code": "10115",
            "city": "Berlin",
            "country": "DE",
            "latitude": None,
            "longitude": None,
            "phone": None,
            "email": None,
            "website": "https://www.muster.de/",
            "source_url": "https://www.muster.de/leistungen",
            "verified_at": "2026-04-25T10:00:00+00:00",
            "services": [],
        }

    def test_complete_record_returns_true(self):
        self.assertTrue(is_complete(self._complete_record()))

    def test_missing_name_returns_false(self):
        r = self._complete_record()
        r["name"] = ""
        self.assertFalse(is_complete(r))

    def test_none_name_returns_false(self):
        r = self._complete_record()
        r["name"] = None
        self.assertFalse(is_complete(r))

    def test_whitespace_only_name_returns_false(self):
        r = self._complete_record()
        r["name"] = "   "
        self.assertFalse(is_complete(r))

    def test_missing_street_returns_false(self):
        r = self._complete_record()
        r["street"] = ""
        self.assertFalse(is_complete(r))

    def test_missing_postal_code_returns_false(self):
        r = self._complete_record()
        r["postal_code"] = ""
        self.assertFalse(is_complete(r))

    def test_missing_city_returns_false(self):
        r = self._complete_record()
        r["city"] = ""
        self.assertFalse(is_complete(r))

    def test_missing_country_returns_false(self):
        r = self._complete_record()
        r["country"] = ""
        self.assertFalse(is_complete(r))

    def test_none_country_returns_false(self):
        r = self._complete_record()
        r["country"] = None
        self.assertFalse(is_complete(r))

    def test_all_five_fields_missing_returns_false(self):
        r = self._complete_record()
        for k in ("name", "street", "postal_code", "city", "country"):
            r[k] = ""
        self.assertFalse(is_complete(r))

    def test_optional_fields_do_not_affect_completeness(self):
        # phone/email/website being None should NOT make is_complete False
        r = self._complete_record()
        r["phone"] = None
        r["email"] = None
        r["website"] = None
        self.assertTrue(is_complete(r))

    def test_non_string_int_field_returns_false(self):
        r = self._complete_record()
        r["city"] = 12345  # wrong type
        self.assertFalse(is_complete(r))

    def test_empty_dict_returns_false(self):
        self.assertFalse(is_complete({}))

    def test_build_record_then_is_complete_roundtrip(self):
        entry = _make_entry()
        scraped = _make_scraped()
        record = build_record(entry, scraped)
        self.assertTrue(is_complete(record))

    def test_build_record_missing_address_then_is_complete_false(self):
        entry = _make_entry()
        scraped = _make_scraped(street=None, postal_code=None, city=None)
        record = build_record(entry, scraped)
        self.assertFalse(is_complete(record))


if __name__ == "__main__":
    unittest.main(verbosity=2)
