from __future__ import annotations

import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))

from basketguard_ingestion import (  # noqa: E402
    FetchHttpStatusError,
    FetchResponse,
    FetchTimeoutError,
    FetchUrlError,
    TESCO_FEATURE_FLAG,
    TescoIngestionProvider,
    TescoProductPageParser,
    TescoScraperConfig,
)


FIXTURE_DIR = ROOT / "services" / "ingestion" / "fixtures"


class ResponseFetcher:
    def __init__(self, html: str) -> None:
        self.html = html

    def fetch(self, url: str, *, timeout_seconds: int, user_agent: str) -> FetchResponse:
        return FetchResponse(url=url, status_code=200, body=self.html)


class ErrorFetcher:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def fetch(self, url: str, *, timeout_seconds: int, user_agent: str) -> FetchResponse:
        raise self.error


class TescoProductPageParserTests(unittest.TestCase):
    def test_parses_plain_tesco_product_page(self) -> None:
        html = (FIXTURE_DIR / "tesco_chopped_tomatoes.html").read_text(encoding="utf-8")
        raw_snapshot, parsed_product, price_observation = TescoProductPageParser().parse(
            html=html,
            url="https://www.tesco.com/groceries/en-GB/products/254879001",
            collected_at="2026-06-07T08:00:00Z",
            postcode_context="SW London",
        )

        self.assertEqual(raw_snapshot.retailer, "Tesco")
        self.assertEqual(raw_snapshot.external_product_id, "254879001")
        self.assertEqual(raw_snapshot.raw_title, "Tesco Chopped Tomatoes 400G")
        self.assertEqual(raw_snapshot.raw_price_text, "GBP 0.55")
        self.assertEqual(raw_snapshot.raw_unit_price_text, "GBP 1.38/kg")

        self.assertEqual(parsed_product.canonical_name, "Tesco Chopped Tomatoes 400G")
        self.assertEqual(parsed_product.category, "Food Cupboard")
        self.assertEqual(parsed_product.pack_size_value, Decimal("400"))
        self.assertEqual(parsed_product.pack_size_unit, "g")
        self.assertEqual(parsed_product.normalised_size_value, Decimal("0.4"))
        self.assertEqual(parsed_product.normalised_size_unit, "kg")
        self.assertEqual(parsed_product.tier, "retailer_standard")

        self.assertEqual(price_observation.shelf_price, Decimal("0.55"))
        self.assertIsNone(price_observation.loyalty_price)
        self.assertEqual(price_observation.effective_price, Decimal("0.55"))
        self.assertEqual(price_observation.unit_price, Decimal("1.38"))
        self.assertEqual(price_observation.unit_price_basis, "kg")
        self.assertEqual(price_observation.availability, "in_stock")

    def test_parses_clubcard_price_as_loyalty_price(self) -> None:
        html = (FIXTURE_DIR / "tesco_clubcard_cornflakes.html").read_text(encoding="utf-8")
        _raw_snapshot, parsed_product, price_observation = TescoProductPageParser().parse(
            html=html,
            url="https://www.tesco.com/groceries/en-GB/products/303030001",
            collected_at="2026-06-07T08:00:00Z",
            postcode_context="SW London",
        )

        self.assertEqual(parsed_product.canonical_name, "Tesco Corn Flakes 500G")
        self.assertEqual(parsed_product.category, "Food Cupboard")
        self.assertEqual(price_observation.shelf_price, Decimal("2.50"))
        self.assertEqual(price_observation.loyalty_price, Decimal("2.25"))
        self.assertEqual(price_observation.effective_price, Decimal("2.25"))
        self.assertEqual(price_observation.promo_type, "loyalty")
        self.assertEqual(price_observation.promo_description, "Clubcard Price")


class TescoIngestionProviderTests(unittest.TestCase):
    def test_live_provider_uses_configured_fetcher_successfully(self) -> None:
        old_value = os.environ.get(TESCO_FEATURE_FLAG)
        os.environ[TESCO_FEATURE_FLAG] = "1"
        html = (FIXTURE_DIR / "tesco_chopped_tomatoes.html").read_text(encoding="utf-8")
        try:
            result = TescoIngestionProvider(
                TescoScraperConfig(
                    allowlisted_urls=(
                        "https://www.tesco.com/groceries/en-GB/products/254879001",
                    ),
                    enabled=True,
                    fetcher=ResponseFetcher(html),
                ),
            ).collect()
        finally:
            if old_value is None:
                os.environ.pop(TESCO_FEATURE_FLAG, None)
            else:
                os.environ[TESCO_FEATURE_FLAG] = old_value

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.collected_count, 1)
        self.assertEqual(result.collection_attempts[0].status, "succeeded")

    def test_live_provider_is_disabled_without_feature_flag(self) -> None:
        old_value = os.environ.pop(TESCO_FEATURE_FLAG, None)
        try:
            result = TescoIngestionProvider(
                TescoScraperConfig(
                    allowlisted_urls=(
                        "https://www.tesco.com/groceries/en-GB/products/254879001",
                    ),
                    enabled=True,
                )
            ).collect()
        finally:
            if old_value is not None:
                os.environ[TESCO_FEATURE_FLAG] = old_value

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.target_count, 1)
        self.assertEqual(result.collected_count, 0)
        self.assertIn("disabled", result.notes or "")

    def test_live_provider_is_disabled_when_config_is_false(self) -> None:
        old_value = os.environ.get(TESCO_FEATURE_FLAG)
        os.environ[TESCO_FEATURE_FLAG] = "1"
        try:
            result = TescoIngestionProvider(
                TescoScraperConfig(
                    allowlisted_urls=(
                        "https://www.tesco.com/groceries/en-GB/products/254879001",
                    ),
                    enabled=False,
                )
            ).collect()
        finally:
            if old_value is None:
                os.environ.pop(TESCO_FEATURE_FLAG, None)
            else:
                os.environ[TESCO_FEATURE_FLAG] = old_value

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.collected_count, 0)
        self.assertIn("disabled", result.notes or "")

    def test_records_failed_fetch_attempt(self) -> None:
        old_value = os.environ.get(TESCO_FEATURE_FLAG)
        os.environ[TESCO_FEATURE_FLAG] = "1"

        class FailingTescoProvider(TescoIngestionProvider):
            def _fetch(self, url: str) -> str:
                raise URLError("network unavailable")

        try:
            result = FailingTescoProvider(
                TescoScraperConfig(
                    allowlisted_urls=(
                        "https://www.tesco.com/groceries/en-GB/products/254879001",
                    ),
                    enabled=True,
                ),
            ).collect()
        finally:
            if old_value is None:
                os.environ.pop(TESCO_FEATURE_FLAG, None)
            else:
                os.environ[TESCO_FEATURE_FLAG] = old_value

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.collected_count, 0)
        self.assertEqual(len(result.raw_snapshots), 0)
        self.assertEqual(len(result.collection_attempts), 1)
        self.assertEqual(result.collection_attempts[0].status, "failed")
        self.assertEqual(result.collection_attempts[0].error_code, "url_error")
        self.assertIn("network unavailable", result.collection_attempts[0].error_message or "")

    def test_records_parser_failure_attempt(self) -> None:
        old_value = os.environ.get(TESCO_FEATURE_FLAG)
        os.environ[TESCO_FEATURE_FLAG] = "1"

        class BadHtmlTescoProvider(TescoIngestionProvider):
            def _fetch(self, url: str) -> str:
                return "<html><body>No product fields</body></html>"

        try:
            result = BadHtmlTescoProvider(
                TescoScraperConfig(
                    allowlisted_urls=(
                        "https://www.tesco.com/groceries/en-GB/products/254879001",
                    ),
                    enabled=True,
                ),
            ).collect()
        finally:
            if old_value is None:
                os.environ.pop(TESCO_FEATURE_FLAG, None)
            else:
                os.environ[TESCO_FEATURE_FLAG] = old_value

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.collected_count, 0)
        self.assertEqual(len(result.raw_snapshots), 0)
        self.assertEqual(len(result.collection_attempts), 1)
        self.assertEqual(result.collection_attempts[0].status, "failed")
        self.assertEqual(result.collection_attempts[0].error_code, "parse_error")
        self.assertIn("Missing product title", result.collection_attempts[0].error_message or "")

    def test_records_fetch_timeout_attempt(self) -> None:
        result = self._collect_with_fetcher_error(FetchTimeoutError("timed out"))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.collection_attempts[0].status, "failed")
        self.assertEqual(result.collection_attempts[0].error_code, "timeout")
        self.assertIn("timed out", result.collection_attempts[0].error_message or "")

    def test_records_http_404_attempt(self) -> None:
        result = self._collect_with_fetcher_error(
            FetchHttpStatusError(404, "Not Found", body="<html>missing</html>"),
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.collection_attempts[0].error_code, "http_404")
        self.assertIn("status_code=404", result.collection_attempts[0].error_message or "")

    def test_records_http_429_attempt(self) -> None:
        result = self._collect_with_fetcher_error(
            FetchHttpStatusError(429, "Too Many Requests", body="slow down"),
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.collection_attempts[0].error_code, "http_429")
        self.assertIn("status_code=429", result.collection_attempts[0].error_message or "")

    def test_records_fetch_network_failure_attempt(self) -> None:
        result = self._collect_with_fetcher_error(FetchUrlError("connection refused"))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.collection_attempts[0].error_code, "url_error")
        self.assertIn("connection refused", result.collection_attempts[0].error_message or "")

    def _collect_with_fetcher_error(self, error: Exception):
        old_value = os.environ.get(TESCO_FEATURE_FLAG)
        os.environ[TESCO_FEATURE_FLAG] = "1"
        try:
            return TescoIngestionProvider(
                TescoScraperConfig(
                    allowlisted_urls=(
                        "https://www.tesco.com/groceries/en-GB/products/254879001",
                    ),
                    enabled=True,
                    fetcher=ErrorFetcher(error),
                ),
            ).collect()
        finally:
            if old_value is None:
                os.environ.pop(TESCO_FEATURE_FLAG, None)
            else:
                os.environ[TESCO_FEATURE_FLAG] = old_value


if __name__ == "__main__":
    unittest.main()
