from __future__ import annotations

import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))

from basketguard_ingestion import (  # noqa: E402
    ASDA_FEATURE_FLAG,
    AsdaIngestionProvider,
    AsdaProductPageParser,
    AsdaScraperConfig,
    FetchResponse,
)


FIXTURE_DIR = ROOT / "services" / "ingestion" / "fixtures"
ASDA_URL = "https://groceries.asda.com/product/cereal/100038316"


class ResponseFetcher:
    def __init__(self, html: str) -> None:
        self.html = html

    def fetch(self, url: str, *, timeout_seconds: int, user_agent: str) -> FetchResponse:
        return FetchResponse(url=url, status_code=200, body=self.html)


class AsdaProductPageParserTests(unittest.TestCase):
    def test_parses_asda_product_page_fixture(self) -> None:
        html = (FIXTURE_DIR / "asda_cornflakes.html").read_text(encoding="utf-8")
        raw_snapshot, parsed_product, price_observation = AsdaProductPageParser().parse(
            html=html,
            url=ASDA_URL,
            collected_at="2026-06-10T08:00:00Z",
            postcode_context="MVP default region",
        )

        self.assertEqual(raw_snapshot.retailer, "Asda")
        self.assertEqual(raw_snapshot.external_product_id, "100038316")
        self.assertEqual(raw_snapshot.raw_title, "ASDA Corn Flakes 500g")
        self.assertEqual(raw_snapshot.raw_price_text, "GBP 1.35")
        self.assertEqual(raw_snapshot.raw_unit_price_text, "GBP 2.70/kg")

        self.assertEqual(parsed_product.canonical_name, "ASDA Corn Flakes 500g")
        self.assertEqual(parsed_product.category, "Food Cupboard")
        self.assertEqual(parsed_product.pack_size_value, Decimal("500"))
        self.assertEqual(parsed_product.pack_size_unit, "g")
        self.assertEqual(parsed_product.normalised_size_value, Decimal("0.5"))
        self.assertEqual(parsed_product.normalised_size_unit, "kg")
        self.assertEqual(parsed_product.tier, "retailer_standard")

        self.assertEqual(price_observation.shelf_price, Decimal("1.35"))
        self.assertEqual(price_observation.effective_price, Decimal("1.35"))
        self.assertEqual(price_observation.unit_price, Decimal("2.70"))
        self.assertEqual(price_observation.unit_price_basis, "kg")
        self.assertEqual(price_observation.availability, "in_stock")


class AsdaIngestionProviderTests(unittest.TestCase):
    def test_live_provider_is_disabled_without_feature_flag(self) -> None:
        old_value = os.environ.pop(ASDA_FEATURE_FLAG, None)
        try:
            result = AsdaIngestionProvider(
                AsdaScraperConfig(
                    allowlisted_urls=(ASDA_URL,),
                    enabled=True,
                ),
            ).collect()
        finally:
            if old_value is not None:
                os.environ[ASDA_FEATURE_FLAG] = old_value

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.target_count, 1)
        self.assertEqual(result.collected_count, 0)
        self.assertIn("disabled", result.notes or "")

    def test_live_provider_uses_configured_fetcher_successfully(self) -> None:
        old_value = os.environ.get(ASDA_FEATURE_FLAG)
        os.environ[ASDA_FEATURE_FLAG] = "1"
        html = (FIXTURE_DIR / "asda_cornflakes.html").read_text(encoding="utf-8")
        try:
            result = AsdaIngestionProvider(
                AsdaScraperConfig(
                    allowlisted_urls=(ASDA_URL,),
                    enabled=True,
                    fetcher=ResponseFetcher(html),
                ),
            ).collect()
        finally:
            if old_value is None:
                os.environ.pop(ASDA_FEATURE_FLAG, None)
            else:
                os.environ[ASDA_FEATURE_FLAG] = old_value

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.collected_count, 1)
        self.assertEqual(len(result.raw_snapshots), 1)
        self.assertEqual(len(result.collection_attempts), 1)
        self.assertEqual(result.collection_attempts[0].status, "succeeded")

    def test_records_parser_failure_attempt(self) -> None:
        old_value = os.environ.get(ASDA_FEATURE_FLAG)
        os.environ[ASDA_FEATURE_FLAG] = "1"
        try:
            result = AsdaIngestionProvider(
                AsdaScraperConfig(
                    allowlisted_urls=(ASDA_URL,),
                    enabled=True,
                    fetcher=ResponseFetcher("<html><body>No product fields</body></html>"),
                ),
            ).collect()
        finally:
            if old_value is None:
                os.environ.pop(ASDA_FEATURE_FLAG, None)
            else:
                os.environ[ASDA_FEATURE_FLAG] = old_value

        self.assertEqual(result.status, "failed")
        self.assertEqual(len(result.raw_snapshots), 0)
        self.assertEqual(len(result.collection_attempts), 1)
        self.assertEqual(result.collection_attempts[0].error_code, "parse_error")
        self.assertIn("Missing product title", result.collection_attempts[0].error_message or "")


if __name__ == "__main__":
    unittest.main()
