"""Unit tests for the pure normalisers in scrape_providers.py.

Run: python -m unittest scripts.test_normalize
or:  python scripts/test_normalize.py
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scrape_providers import (  # noqa: E402  (path mutation above is intentional)
    _sanitize_null,
    _sanitize_scraped,
    homepage_from_url,
    infer_country_from_tld,
    normalize_country,
    normalize_phone,
)


PHONE_PATTERN = re.compile(r"^\+[0-9 ]+$")


class NormalizePhoneTests(unittest.TestCase):
    def test_german_with_parens_slash_dash(self):
        # CLAUDE.md example 1
        self.assertEqual(
            normalize_phone("+49 (0)511/123-7170"),
            "+49 0 511 123 7170",
        )

    def test_german_double_zero_prefix(self):
        # CLAUDE.md example 2
        self.assertEqual(
            normalize_phone("0049 511 1237170"),
            "+49 511 1237170",
        )

    def test_austrian_with_dashes(self):
        self.assertEqual(
            normalize_phone("+43-1-234 5678"),
            "+43 1 234 5678",
        )

    def test_austrian_double_zero(self):
        self.assertEqual(
            normalize_phone("0043 1 5891234"),
            "+43 1 5891234",
        )

    def test_strips_tel_prefix(self):
        self.assertEqual(
            normalize_phone("Tel.: +49 30 12345678"),
            "+49 30 12345678",
        )

    def test_collapses_runs_of_whitespace(self):
        self.assertEqual(
            normalize_phone("+49   30    1234"),
            "+49 30 1234",
        )

    def test_none_returns_none(self):
        self.assertIsNone(normalize_phone(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(normalize_phone(""))
        self.assertIsNone(normalize_phone("   "))

    def test_non_string_returns_none(self):
        self.assertIsNone(normalize_phone(12345))
        self.assertIsNone(normalize_phone(["+49 30 1"]))

    def test_email_input_returns_none(self):
        self.assertIsNone(normalize_phone("info@example.de"))
        self.assertIsNone(normalize_phone("praxis@klinik-berlin.de"))

    def test_letters_in_middle_returns_none(self):
        self.assertIsNone(normalize_phone("+49 30 abc 4567"))

    def test_too_few_digits_returns_none(self):
        self.assertIsNone(normalize_phone("+49 12"))

    def test_no_country_code_returns_none(self):
        # 030 12345 has no leading + or 00 → cannot promote to international
        self.assertIsNone(normalize_phone("030 12345 67"))

    def test_double_plus_returns_none(self):
        self.assertIsNone(normalize_phone("+49 +30 1234567"))

    def test_output_matches_schema_regex(self):
        for raw in (
            "+49 (0)511/123-7170",
            "0049 511 1237170",
            "+43-1-234 5678",
            "Tel.: +49 30 12345678",
        ):
            with self.subTest(raw=raw):
                out = normalize_phone(raw)
                self.assertIsNotNone(out)
                self.assertRegex(out, PHONE_PATTERN)


class InferCountryFromTldTests(unittest.TestCase):
    def test_de(self):
        self.assertEqual(infer_country_from_tld("https://example.de/foo"), "DE")
        self.assertEqual(infer_country_from_tld("https://www.example.de/"), "DE")

    def test_at(self):
        self.assertEqual(infer_country_from_tld("https://diagnostikum.at/de/locations/"), "AT")

    def test_ch(self):
        self.assertEqual(infer_country_from_tld("https://praxis.ch"), "CH")

    def test_unknown_tld(self):
        self.assertIsNone(infer_country_from_tld("https://example.com/foo"))
        self.assertIsNone(infer_country_from_tld("https://example.org/"))

    def test_invalid_input(self):
        self.assertIsNone(infer_country_from_tld(None))
        self.assertIsNone(infer_country_from_tld(""))
        self.assertIsNone(infer_country_from_tld("not a url"))

    def test_with_port(self):
        self.assertEqual(infer_country_from_tld("https://example.de:8443/path"), "DE")


class NormalizeCountryTests(unittest.TestCase):
    def test_iso_code_passthrough(self):
        self.assertEqual(normalize_country("DE", None), "DE")
        self.assertEqual(normalize_country("at", "https://x.de"), "AT")

    def test_full_name(self):
        self.assertEqual(normalize_country("Deutschland", None), "DE")
        self.assertEqual(normalize_country("Österreich", None), "AT")
        self.assertEqual(normalize_country("Schweiz", None), "CH")
        self.assertEqual(normalize_country("Germany", None), "DE")

    def test_tld_fallback_when_raw_missing(self):
        self.assertEqual(normalize_country(None, "https://praxis.de/"), "DE")
        self.assertEqual(normalize_country("", "https://klinik.at/x"), "AT")

    def test_tld_fallback_when_raw_invalid(self):
        self.assertEqual(normalize_country("Wonderland", "https://praxis.de/"), "DE")

    def test_no_signal_returns_none(self):
        self.assertIsNone(normalize_country(None, "https://example.com/"))
        self.assertIsNone(normalize_country("", None))


class HomepageFromUrlTests(unittest.TestCase):
    def test_strips_path(self):
        self.assertEqual(
            homepage_from_url("https://www.example.de/leistungen/dexa"),
            "https://www.example.de/",
        )

    def test_strips_query_and_fragment(self):
        self.assertEqual(
            homepage_from_url("https://x.at/de/foo?bar=1#baz"),
            "https://x.at/",
        )

    def test_root_already(self):
        self.assertEqual(homepage_from_url("https://x.de/"), "https://x.de/")

    def test_invalid(self):
        self.assertIsNone(homepage_from_url(None))
        self.assertIsNone(homepage_from_url(""))
        self.assertIsNone(homepage_from_url("not-a-url"))


class SanitizeNullTests(unittest.TestCase):
    def test_string_null_becomes_none(self):
        self.assertIsNone(_sanitize_null("null"))
        self.assertIsNone(_sanitize_null("Null"))
        self.assertIsNone(_sanitize_null("NULL"))
        self.assertIsNone(_sanitize_null("  null  "))

    def test_string_none_becomes_none(self):
        self.assertIsNone(_sanitize_null("none"))
        self.assertIsNone(_sanitize_null("None"))

    def test_na_variants(self):
        self.assertIsNone(_sanitize_null("n/a"))
        self.assertIsNone(_sanitize_null("N/A"))
        self.assertIsNone(_sanitize_null("na"))

    def test_dash_and_em_dash(self):
        self.assertIsNone(_sanitize_null("-"))
        self.assertIsNone(_sanitize_null("—"))

    def test_german_variants(self):
        self.assertIsNone(_sanitize_null("nicht verfügbar"))
        self.assertIsNone(_sanitize_null("nicht vorhanden"))

    def test_real_values_preserved(self):
        self.assertEqual(_sanitize_null("Musterstraße 1"), "Musterstraße 1")
        self.assertEqual(_sanitize_null("+49 30 1234567"), "+49 30 1234567")
        self.assertEqual(_sanitize_null("info@example.de"), "info@example.de")

    def test_actual_none_preserved(self):
        self.assertIsNone(_sanitize_null(None))

    def test_non_string_passthrough(self):
        self.assertEqual(_sanitize_null(42), 42)
        self.assertEqual(_sanitize_null([]), [])

    def test_sanitize_scraped_dict(self):
        raw = {
            "name": "Praxis XY",
            "street": "null",
            "postal_code": "None",
            "city": "n/a",
            "phone": "+49 30 1234567",
            "email": "null",
        }
        cleaned = _sanitize_scraped(raw)
        self.assertEqual(cleaned["name"], "Praxis XY")
        self.assertIsNone(cleaned["street"])
        self.assertIsNone(cleaned["postal_code"])
        self.assertIsNone(cleaned["city"])
        self.assertEqual(cleaned["phone"], "+49 30 1234567")
        self.assertIsNone(cleaned["email"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
