"""Unit tests for geocode_providers.py — no live API calls."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from geocode_providers import (
    format_coord,
    geocode_one,
    make_cache_key,
    main,
    plausibility_check,
)


class TestCacheKey(unittest.TestCase):
    def test_case_insensitive(self):
        k1 = make_cache_key("Hauptstraße 1", "80331", "München", "DE")
        k2 = make_cache_key("hauptstraße 1", "80331", "münchen", "de")
        self.assertEqual(k1, k2)

    def test_whitespace_trimmed(self):
        k1 = make_cache_key("Hauptstraße 1", "80331", "München", "DE")
        k2 = make_cache_key("  Hauptstraße 1  ", " 80331 ", " München ", " DE ")
        self.assertEqual(k1, k2)

    def test_different_addresses_differ(self):
        k1 = make_cache_key("Hauptstraße 1", "80331", "München", "DE")
        k2 = make_cache_key("Bahnhofstraße 1", "80331", "München", "DE")
        self.assertNotEqual(k1, k2)


class TestPlausibilityCheck(unittest.TestCase):
    def _make_location(self, country_code: str) -> MagicMock:
        loc = MagicMock()
        loc.raw = {"address": {"country_code": country_code}}
        return loc

    def test_matching_country(self):
        self.assertTrue(plausibility_check(self._make_location("de"), "DE"))

    def test_mismatching_country_de_in_fr(self):
        self.assertFalse(plausibility_check(self._make_location("fr"), "DE"))

    def test_mismatching_country_at_in_de(self):
        self.assertFalse(plausibility_check(self._make_location("de"), "AT"))

    def test_none_location(self):
        self.assertFalse(plausibility_check(None, "DE"))


class TestFormatCoord(unittest.TestCase):
    def test_seven_decimals(self):
        self.assertEqual(format_coord(52.52), 52.52)

    def test_precise_value(self):
        self.assertEqual(format_coord(52.5200066), 52.5200066)

    def test_negative(self):
        self.assertEqual(format_coord(-13.40495), -13.40495)

    def test_rounding(self):
        self.assertAlmostEqual(format_coord(52.52000665555), 52.5200067, places=7)

    def test_returns_float(self):
        self.assertIsInstance(format_coord(52.52), float)


class TestGeocodeOne(unittest.TestCase):
    def test_cache_hit_success(self):
        provider = {"street": "Hauptstraße 1", "postal_code": "80331", "city": "München", "country": "DE"}
        key = make_cache_key("Hauptstraße 1", "80331", "München", "DE")
        cache = {key: {"lat": 48.1371079, "lon": 11.5753822, "resolved_at": "2026-01-01T00:00:00+00:00"}}

        lat, lon, err = geocode_one(None, provider, cache)
        self.assertEqual(lat, 48.1371079)
        self.assertEqual(lon, 11.5753822)
        self.assertIsNone(err)

    def test_cache_hit_failure(self):
        provider = {"street": "Nirgendwo 999", "postal_code": "00000", "city": "Nixdorf", "country": "DE"}
        key = make_cache_key("Nirgendwo 999", "00000", "Nixdorf", "DE")
        cache = {key: {"lat": None, "lon": None, "resolved_at": "2026-01-01T00:00:00+00:00", "error": "no result"}}

        lat, lon, err = geocode_one(None, provider, cache)
        self.assertIsNone(lat)
        self.assertIsNone(lon)
        self.assertEqual(err, "no result")

    def test_missing_street(self):
        provider = {"street": "", "postal_code": "80331", "city": "München", "country": "DE"}
        lat, lon, err = geocode_one(None, provider, {})
        self.assertIsNone(lat)
        self.assertIn("missing", err)

    def test_missing_city(self):
        provider = {"street": "Hauptstraße 1", "postal_code": "80331", "city": "", "country": "DE"}
        lat, lon, err = geocode_one(None, provider, {})
        self.assertIsNone(lat)
        self.assertIn("missing", err)

    def test_plausibility_reject(self):
        provider = {"street": "Hauptstraße 1", "postal_code": "80331", "city": "München", "country": "DE"}
        cache: dict = {}

        mock_location = MagicMock()
        mock_location.latitude = 48.8566
        mock_location.longitude = 2.3522
        mock_location.raw = {"address": {"country_code": "fr"}}

        lat, lon, err = geocode_one(MagicMock(return_value=mock_location), provider, cache)
        self.assertIsNone(lat)
        self.assertIsNone(lon)
        self.assertIn("country mismatch", err)
        key = make_cache_key("Hauptstraße 1", "80331", "München", "DE")
        self.assertIn(key, cache)
        self.assertIsNone(cache[key]["lat"])

    def test_successful_geocode(self):
        provider = {"street": "Marienplatz 1", "postal_code": "80331", "city": "München", "country": "DE"}
        cache: dict = {}

        mock_location = MagicMock()
        mock_location.latitude = 48.1371079
        mock_location.longitude = 11.5753822
        mock_location.raw = {"address": {"country_code": "de"}}

        lat, lon, err = geocode_one(MagicMock(return_value=mock_location), provider, cache)
        self.assertEqual(lat, 48.1371079)
        self.assertEqual(lon, 11.5753822)
        self.assertIsNone(err)

    def test_geocoder_exception(self):
        provider = {"street": "Hauptstraße 1", "postal_code": "80331", "city": "München", "country": "DE"}
        cache: dict = {}
        mock_fn = MagicMock(side_effect=Exception("timeout"))

        lat, lon, err = geocode_one(mock_fn, provider, cache)
        self.assertIsNone(lat)
        self.assertIn("geocoder error", err)
        key = make_cache_key("Hauptstraße 1", "80331", "München", "DE")
        self.assertIn(key, cache)

    def test_no_result(self):
        provider = {"street": "Nirgendwo 999", "postal_code": "00000", "city": "Nixdorf", "country": "DE"}
        cache: dict = {}

        lat, lon, err = geocode_one(MagicMock(return_value=None), provider, cache)
        self.assertIsNone(lat)
        self.assertIn("no result", err)

    # --- NEW: None values for street and city (not empty string) ---

    def test_none_street_returns_error(self):
        """None street should behave the same as empty string — no crash, returns error."""
        provider = {"street": None, "postal_code": "80331", "city": "München", "country": "DE"}
        lat, lon, err = geocode_one(None, provider, {})
        self.assertIsNone(lat)
        self.assertIsNone(lon)
        self.assertIsNotNone(err)
        self.assertIn("missing", err)

    def test_none_city_returns_error(self):
        """None city should behave the same as empty string — no crash, returns error."""
        provider = {"street": "Hauptstraße 1", "postal_code": "80331", "city": None, "country": "DE"}
        lat, lon, err = geocode_one(None, provider, {})
        self.assertIsNone(lat)
        self.assertIsNone(lon)
        self.assertIsNotNone(err)
        self.assertIn("missing", err)

    def test_none_street_and_none_city_returns_error(self):
        """Both None — no crash, returns error."""
        provider = {"street": None, "postal_code": None, "city": None, "country": "DE"}
        lat, lon, err = geocode_one(None, provider, {})
        self.assertIsNone(lat)
        self.assertIsNone(lon)
        self.assertIsNotNone(err)
        self.assertIn("missing", err)


class TestForceFlag(unittest.TestCase):
    _PROVIDER = {
        "name": "Test", "street": "Marienplatz 1",
        "postal_code": "80331", "city": "München", "country": "DE",
        "latitude": 48.0, "longitude": 11.0,
        "phone": None, "email": None, "website": None,
        "source_url": "https://example.de/", "verified_at": "2026-01-01T00:00:00+00:00",
        "services": [],
    }

    def _make_mock_location(self) -> MagicMock:
        loc = MagicMock()
        loc.latitude = 48.1371079
        loc.longitude = 11.5753822
        loc.raw = {"address": {"country_code": "de"}}
        return loc

    def test_force_regeocodes_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "providers.json"
            cache_path = Path(tmpdir) / "cache.json"
            input_path.write_text(json.dumps([self._PROVIDER]), encoding="utf-8")

            with patch("geocode_providers.create_geocoder") as mock_cg, \
                 patch("geocode_providers.load_env", return_value="test/1.0"):
                mock_cg.return_value = MagicMock(return_value=self._make_mock_location())
                main([str(input_path), "--force", "--cache", str(cache_path)])

            result = json.loads(input_path.read_text(encoding="utf-8"))
            self.assertEqual(result[0]["latitude"], 48.1371079)
            self.assertEqual(result[0]["longitude"], 11.5753822)

    def test_no_force_skips_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "providers.json"
            cache_path = Path(tmpdir) / "cache.json"
            input_path.write_text(json.dumps([self._PROVIDER]), encoding="utf-8")

            with patch("geocode_providers.create_geocoder") as mock_cg, \
                 patch("geocode_providers.load_env", return_value="test/1.0"):
                mock_geocode = MagicMock()
                mock_cg.return_value = mock_geocode
                main([str(input_path), "--cache", str(cache_path)])

            mock_geocode.assert_not_called()
            result = json.loads(input_path.read_text(encoding="utf-8"))
            self.assertEqual(result[0]["latitude"], 48.0)
            self.assertEqual(result[0]["longitude"], 11.0)

    def test_null_longitude_triggers_geocoding(self):
        provider = {**self._PROVIDER, "latitude": 48.0, "longitude": None}
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "providers.json"
            cache_path = Path(tmpdir) / "cache.json"
            input_path.write_text(json.dumps([provider]), encoding="utf-8")

            with patch("geocode_providers.create_geocoder") as mock_cg, \
                 patch("geocode_providers.load_env", return_value="test/1.0"):
                mock_cg.return_value = MagicMock(return_value=self._make_mock_location())
                main([str(input_path), "--cache", str(cache_path)])

            result = json.loads(input_path.read_text(encoding="utf-8"))
            self.assertEqual(result[0]["latitude"], 48.1371079)
            self.assertEqual(result[0]["longitude"], 11.5753822)

    def test_none_lat_treated_as_needs_geocoding(self):
        provider = {**self._PROVIDER, "latitude": None, "longitude": None}
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "providers.json"
            cache_path = Path(tmpdir) / "cache.json"
            input_path.write_text(json.dumps([provider]), encoding="utf-8")

            with patch("geocode_providers.create_geocoder") as mock_cg, \
                 patch("geocode_providers.load_env", return_value="test/1.0"):
                mock_cg.return_value = MagicMock(return_value=self._make_mock_location())
                main([str(input_path), "--cache", str(cache_path)])

            result = json.loads(input_path.read_text(encoding="utf-8"))
            self.assertEqual(result[0]["latitude"], 48.1371079)


# ---------------------------------------------------------------------------
# NEW: empty input array
# ---------------------------------------------------------------------------

class TestEmptyInputArray(unittest.TestCase):
    """main() with an empty providers array should exit cleanly (return 0, no errors)."""

    def test_empty_array_exits_cleanly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "providers.json"
            cache_path = Path(tmpdir) / "cache.json"
            input_path.write_text("[]", encoding="utf-8")

            with patch("geocode_providers.create_geocoder"), \
                 patch("geocode_providers.load_env", return_value="test/1.0"):
                rc = main([str(input_path), "--cache", str(cache_path)])

            self.assertEqual(rc, 0)

    def test_empty_array_input_file_unchanged(self):
        """The providers file must still be a valid JSON array after the run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "providers.json"
            cache_path = Path(tmpdir) / "cache.json"
            input_path.write_text("[]", encoding="utf-8")

            with patch("geocode_providers.create_geocoder"), \
                 patch("geocode_providers.load_env", return_value="test/1.0"):
                main([str(input_path), "--cache", str(cache_path)])

            result = json.loads(input_path.read_text(encoding="utf-8"))
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 0)

    def test_empty_array_no_error_file_created(self):
        """No .geocode-errors.json should appear when the input is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "providers.json"
            cache_path = Path(tmpdir) / "cache.json"
            input_path.write_text("[]", encoding="utf-8")

            with patch("geocode_providers.create_geocoder"), \
                 patch("geocode_providers.load_env", return_value="test/1.0"):
                main([str(input_path), "--cache", str(cache_path)])

            error_path = input_path.with_suffix(".geocode-errors.json")
            self.assertFalse(error_path.exists())


# ---------------------------------------------------------------------------
# NEW: cache file persistence
# ---------------------------------------------------------------------------

_BASE_PROVIDER = {
    "name": "Praxis Muster",
    "street": "Marienplatz 1", "postal_code": "80331",
    "city": "München", "country": "DE",
    "latitude": None, "longitude": None,
    "phone": None, "email": None, "website": None,
    "source_url": "https://example.de/", "verified_at": "2026-01-01T00:00:00+00:00",
    "services": [],
}


class TestCachePersistence(unittest.TestCase):
    """After a successful geocode run the cache file must reflect the result."""

    def _make_mock_location(self, lat: float = 48.1371079, lon: float = 11.5753822,
                            cc: str = "de") -> MagicMock:
        loc = MagicMock()
        loc.latitude = lat
        loc.longitude = lon
        loc.raw = {"address": {"country_code": cc}}
        return loc

    def test_cache_written_on_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "providers.json"
            cache_path = Path(tmpdir) / "cache.json"
            input_path.write_text(json.dumps([_BASE_PROVIDER]), encoding="utf-8")

            with patch("geocode_providers.create_geocoder") as mock_cg, \
                 patch("geocode_providers.load_env", return_value="test/1.0"):
                mock_cg.return_value = MagicMock(return_value=self._make_mock_location())
                main([str(input_path), "--cache", str(cache_path)])

            self.assertTrue(cache_path.exists(), "cache file was not created")
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertIsInstance(cache, dict)
            self.assertEqual(len(cache), 1, "expected exactly one cache entry")

            key = make_cache_key("Marienplatz 1", "80331", "München", "DE")
            self.assertIn(key, cache)
            entry = cache[key]
            self.assertEqual(entry["lat"], 48.1371079)
            self.assertEqual(entry["lon"], 11.5753822)
            self.assertIn("resolved_at", entry)
            self.assertNotIn("error", entry)

    def test_cache_written_on_failure(self):
        """A geocoder error should still produce a cache entry (with error key)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "providers.json"
            cache_path = Path(tmpdir) / "cache.json"
            input_path.write_text(json.dumps([_BASE_PROVIDER]), encoding="utf-8")

            with patch("geocode_providers.create_geocoder") as mock_cg, \
                 patch("geocode_providers.load_env", return_value="test/1.0"):
                mock_cg.return_value = MagicMock(return_value=None)  # no result
                main([str(input_path), "--cache", str(cache_path)])

            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            key = make_cache_key("Marienplatz 1", "80331", "München", "DE")
            self.assertIn(key, cache)
            entry = cache[key]
            self.assertIsNone(entry["lat"])
            self.assertIsNone(entry["lon"])
            self.assertIn("error", entry)

    def test_cache_used_on_second_run_no_api_call(self):
        """A second run must use the cache and must NOT call the geocoder again."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "providers.json"
            cache_path = Path(tmpdir) / "cache.json"

            # Pre-populate the cache with a successful entry.
            key = make_cache_key("Marienplatz 1", "80331", "München", "DE")
            cache_path.write_text(
                json.dumps({
                    key: {
                        "lat": 48.1371079, "lon": 11.5753822,
                        "resolved_at": "2026-01-01T00:00:00+00:00",
                    }
                }),
                encoding="utf-8",
            )

            provider_needing_geocode = {**_BASE_PROVIDER}
            input_path.write_text(json.dumps([provider_needing_geocode]), encoding="utf-8")

            mock_geocode_fn = MagicMock()
            with patch("geocode_providers.create_geocoder") as mock_cg, \
                 patch("geocode_providers.load_env", return_value="test/1.0"):
                mock_cg.return_value = mock_geocode_fn
                main([str(input_path), "--cache", str(cache_path)])

            mock_geocode_fn.assert_not_called()

            result = json.loads(input_path.read_text(encoding="utf-8"))
            self.assertEqual(result[0]["latitude"], 48.1371079)


# ---------------------------------------------------------------------------
# NEW: error log file
# ---------------------------------------------------------------------------

class TestErrorLogFile(unittest.TestCase):
    """Verify that .geocode-errors.json is written correctly on failures and
    cleaned up when there are none."""

    def _provider(self, name: str, has_address: bool = True) -> dict:
        p = {**_BASE_PROVIDER, "name": name, "latitude": None, "longitude": None}
        if not has_address:
            p["street"] = None
            p["city"] = None
        return p

    def test_error_file_written_with_correct_schema(self):
        """When a provider fails geocoding the error file must contain expected fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "providers.json"
            cache_path = Path(tmpdir) / "cache.json"
            input_path.write_text(json.dumps([self._provider("Fehler GmbH")]),
                                  encoding="utf-8")

            with patch("geocode_providers.create_geocoder") as mock_cg, \
                 patch("geocode_providers.load_env", return_value="test/1.0"):
                mock_cg.return_value = MagicMock(return_value=None)  # no geocode result
                main([str(input_path), "--cache", str(cache_path)])

            error_path = input_path.with_suffix(".geocode-errors.json")
            self.assertTrue(error_path.exists(), ".geocode-errors.json was not created")

            errors = json.loads(error_path.read_text(encoding="utf-8"))
            self.assertIsInstance(errors, list)
            self.assertEqual(len(errors), 1)
            entry = errors[0]
            self.assertEqual(entry["name"], "Fehler GmbH")
            self.assertIn("error", entry)
            self.assertIn("address", entry)

    def test_multiple_errors_all_recorded(self):
        """Each failing provider appears in the error log exactly once."""
        providers = [
            self._provider("Praxis Eins"),
            self._provider("Praxis Zwei"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "providers.json"
            cache_path = Path(tmpdir) / "cache.json"
            input_path.write_text(json.dumps(providers), encoding="utf-8")

            with patch("geocode_providers.create_geocoder") as mock_cg, \
                 patch("geocode_providers.load_env", return_value="test/1.0"):
                mock_cg.return_value = MagicMock(return_value=None)
                main([str(input_path), "--cache", str(cache_path)])

            errors = json.loads(
                input_path.with_suffix(".geocode-errors.json").read_text(encoding="utf-8")
            )
            names = {e["name"] for e in errors}
            self.assertIn("Praxis Eins", names)
            self.assertIn("Praxis Zwei", names)

    def test_error_file_deleted_when_no_errors(self):
        """A stale .geocode-errors.json from a previous run must be removed when the
        current run produces zero errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "providers.json"
            cache_path = Path(tmpdir) / "cache.json"
            error_path = input_path.with_suffix(".geocode-errors.json")

            # Write a stale error file.
            error_path.write_text(json.dumps([{"name": "old", "error": "stale"}]),
                                  encoding="utf-8")

            mock_location = MagicMock()
            mock_location.latitude = 48.1371079
            mock_location.longitude = 11.5753822
            mock_location.raw = {"address": {"country_code": "de"}}

            input_path.write_text(
                json.dumps([self._provider("Praxis OK")]), encoding="utf-8"
            )

            with patch("geocode_providers.create_geocoder") as mock_cg, \
                 patch("geocode_providers.load_env", return_value="test/1.0"):
                mock_cg.return_value = MagicMock(return_value=mock_location)
                main([str(input_path), "--cache", str(cache_path)])

            self.assertFalse(error_path.exists(),
                             "stale .geocode-errors.json was not deleted after clean run")

    def test_failed_providers_have_null_coords_in_output(self):
        """Providers that fail geocoding must have latitude/longitude set to None in the
        written output file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "providers.json"
            cache_path = Path(tmpdir) / "cache.json"
            input_path.write_text(
                json.dumps([self._provider("Keine Adresse", has_address=False)]),
                encoding="utf-8",
            )

            with patch("geocode_providers.create_geocoder") as mock_cg, \
                 patch("geocode_providers.load_env", return_value="test/1.0"):
                mock_cg.return_value = MagicMock()
                main([str(input_path), "--cache", str(cache_path)])

            result = json.loads(input_path.read_text(encoding="utf-8"))
            self.assertIsNone(result[0]["latitude"])
            self.assertIsNone(result[0]["longitude"])


if __name__ == "__main__":
    unittest.main()
