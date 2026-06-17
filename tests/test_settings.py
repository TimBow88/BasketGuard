from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

from basketguard_shared import Settings, SettingsError  # noqa: E402


class SettingsTests(unittest.TestCase):
    def test_defaults_when_environment_empty(self) -> None:
        settings = Settings.from_env({})

        self.assertIsNone(settings.database_url)
        self.assertEqual(settings.enabled_retailers, frozenset())
        self.assertEqual(settings.fetcher_mode, "urllib")
        self.assertEqual(settings.request_timeout_seconds, 15)
        self.assertEqual(settings.request_delay_seconds, 1.0)
        self.assertEqual(settings.max_retries, 2)
        self.assertIsNone(settings.proxy_url)
        self.assertIsNone(settings.snapshot_root)
        self.assertEqual(settings.log_level, "INFO")

    def test_reads_database_url_and_fallback(self) -> None:
        primary = Settings.from_env({"BASKETGUARD_DATABASE_URL": "postgresql://a"})
        self.assertEqual(primary.database_url, "postgresql://a")

        fallback = Settings.from_env({"DATABASE_URL": "postgresql://b"})
        self.assertEqual(fallback.database_url, "postgresql://b")

    def test_enabled_retailers_from_flags(self) -> None:
        settings = Settings.from_env(
            {
                "BASKETGUARD_ENABLE_TESCO_SCRAPER": "1",
                "BASKETGUARD_ENABLE_ASDA_SCRAPER": "0",
                "BASKETGUARD_ENABLE_MORRISONS_SCRAPER": "1",
            }
        )

        self.assertEqual(settings.enabled_retailers, frozenset({"tesco", "morrisons"}))
        self.assertTrue(settings.retailer_enabled("Tesco"))
        self.assertFalse(settings.retailer_enabled("asda"))

    def test_parses_numeric_tuning_values(self) -> None:
        settings = Settings.from_env(
            {
                "BASKETGUARD_REQUEST_TIMEOUT_SECONDS": "30",
                "BASKETGUARD_REQUEST_DELAY_SECONDS": "2.5",
                "BASKETGUARD_MAX_RETRIES": "5",
                "BASKETGUARD_RETRY_BACKOFF_SECONDS": "0",
                "BASKETGUARD_SNAPSHOT_ROOT": "artifacts/raw_snapshots",
                "BASKETGUARD_COLLECTION_POSTCODE_CONTEXT": "EC1A 1BB",
                "BASKETGUARD_LOG_LEVEL": "debug",
            }
        )

        self.assertEqual(settings.request_timeout_seconds, 30)
        self.assertEqual(settings.request_delay_seconds, 2.5)
        self.assertEqual(settings.max_retries, 5)
        self.assertEqual(settings.retry_backoff_seconds, 0.0)
        self.assertEqual(settings.snapshot_root, Path("artifacts/raw_snapshots"))
        self.assertEqual(settings.collection_postcode_context, "EC1A 1BB")
        self.assertEqual(settings.log_level, "DEBUG")

    def test_invalid_fetcher_mode_raises(self) -> None:
        with self.assertRaises(SettingsError):
            Settings.from_env({"BASKETGUARD_FETCHER_MODE": "selenium"})

    def test_non_numeric_timeout_raises(self) -> None:
        with self.assertRaises(SettingsError):
            Settings.from_env({"BASKETGUARD_REQUEST_TIMEOUT_SECONDS": "soon"})

    def test_negative_timeout_raises(self) -> None:
        with self.assertRaises(SettingsError):
            Settings.from_env({"BASKETGUARD_REQUEST_TIMEOUT_SECONDS": "-1"})

    def test_require_database_url_raises_when_missing(self) -> None:
        with self.assertRaises(SettingsError):
            Settings.from_env({}).require_database_url()


if __name__ == "__main__":
    unittest.main()
