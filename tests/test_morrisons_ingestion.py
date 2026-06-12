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
    MORRISONS_FEATURE_FLAG,
    ExtractedProduct,
    FetchResponse,
    MorrisonsIngestionProvider,
    MorrisonsParseError,
    MorrisonsProductPageParser,
    MorrisonsScraperConfig,
)


FIXTURE_DIR = ROOT / "services" / "ingestion" / "fixtures"
MORRISONS_URL = "https://groceries.morrisons.com/products/morrisons-scottish-porridge-oats-268703011"


class ResponseFetcher:
    def __init__(self, html: str) -> None:
        self.html = html

    def fetch(self, url: str, *, timeout_seconds: int, user_agent: str) -> FetchResponse:
        return FetchResponse(url=url, status_code=200, body=self.html)


class MorrisonsProductPageParserTests(unittest.TestCase):
    def test_parses_morrisons_product_page_fixture(self) -> None:
        html = (FIXTURE_DIR / "morrisons_porridge_oats.html").read_text(encoding="utf-8")
        raw_snapshot, parsed_product, price_observation = MorrisonsProductPageParser().parse(
            html=html,
            url=MORRISONS_URL,
            collected_at="2026-06-11T08:00:00Z",
            postcode_context="MVP default region",
        )

        self.assertEqual(raw_snapshot.retailer, "Morrisons")
        # URL ends with the numeric product ID.
        self.assertEqual(raw_snapshot.external_product_id, "268703011")
        self.assertEqual(raw_snapshot.raw_title, "Morrisons Scottish Porridge Oats 1kg")
        self.assertEqual(raw_snapshot.raw_price_text, "£1.09")
        self.assertEqual(raw_snapshot.raw_unit_price_text, "£1.09/kg")
        self.assertEqual(raw_snapshot.parser_version, "morrisons-html-v1")

        self.assertEqual(parsed_product.canonical_name, "Morrisons Scottish Porridge Oats 1kg")
        self.assertEqual(parsed_product.category, "Food Cupboard")
        self.assertEqual(parsed_product.brand, "Morrisons")
        self.assertEqual(parsed_product.pack_size_value, Decimal("1"))
        self.assertEqual(parsed_product.pack_size_unit, "kg")
        self.assertEqual(parsed_product.normalised_size_value, Decimal("1"))
        self.assertEqual(parsed_product.normalised_size_unit, "kg")
        self.assertEqual(parsed_product.tier, "retailer_standard")
        self.assertTrue(parsed_product.is_own_brand)

        self.assertEqual(price_observation.shelf_price, Decimal("1.09"))
        self.assertEqual(price_observation.effective_price, Decimal("1.09"))
        self.assertEqual(price_observation.unit_price, Decimal("1.09"))
        self.assertEqual(price_observation.unit_price_basis, "kg")
        self.assertEqual(price_observation.availability, "in_stock")

    def test_extract_returns_shared_contract(self) -> None:
        html = (FIXTURE_DIR / "morrisons_porridge_oats.html").read_text(encoding="utf-8")
        extracted = MorrisonsProductPageParser().extract(html, MORRISONS_URL)

        self.assertIsInstance(extracted, ExtractedProduct)
        self.assertEqual(extracted.retailer, "Morrisons")
        self.assertEqual(extracted.title, "Morrisons Scottish Porridge Oats 1kg")
        self.assertEqual(extracted.price, "£1.09")
        self.assertEqual(extracted.currency, "GBP")
        self.assertEqual(extracted.unit_price_text, "£1.09/kg")
        self.assertEqual(extracted.pack_size_text, "1kg")
        self.assertEqual(extracted.external_product_id, "268703011")
        self.assertEqual(extracted.missing_fields, ("image_url",))

    def test_missing_unit_price_fixture_raises_parse_error(self) -> None:
        html = (FIXTURE_DIR / "morrisons_cornflakes_missing_unit_price.html").read_text(
            encoding="utf-8",
        )
        with self.assertRaises(MorrisonsParseError):
            MorrisonsProductPageParser().parse(
                html=html,
                url="https://groceries.morrisons.com/products/morrisons-corn-flakes-268900122",
                collected_at="2026-06-11T08:00:00Z",
            )

    def test_missing_unit_price_is_flagged_by_extract(self) -> None:
        html = (FIXTURE_DIR / "morrisons_cornflakes_missing_unit_price.html").read_text(
            encoding="utf-8",
        )
        extracted = MorrisonsProductPageParser().extract(html, None)

        self.assertIn("unit_price_text", extracted.missing_fields)
        self.assertNotIn("price", extracted.missing_fields)


class MorrisonsIngestionProviderTests(unittest.TestCase):
    def test_live_provider_is_disabled_without_feature_flag(self) -> None:
        old_value = os.environ.pop(MORRISONS_FEATURE_FLAG, None)
        try:
            result = MorrisonsIngestionProvider(
                MorrisonsScraperConfig(
                    allowlisted_urls=(MORRISONS_URL,),
                    enabled=True,
                ),
            ).collect()
        finally:
            if old_value is not None:
                os.environ[MORRISONS_FEATURE_FLAG] = old_value

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.target_count, 1)
        self.assertEqual(result.collected_count, 0)
        self.assertIn("disabled", result.notes or "")

    def test_live_provider_uses_configured_fetcher_successfully(self) -> None:
        old_value = os.environ.get(MORRISONS_FEATURE_FLAG)
        os.environ[MORRISONS_FEATURE_FLAG] = "1"
        html = (FIXTURE_DIR / "morrisons_porridge_oats.html").read_text(encoding="utf-8")
        try:
            result = MorrisonsIngestionProvider(
                MorrisonsScraperConfig(
                    allowlisted_urls=(MORRISONS_URL,),
                    enabled=True,
                    fetcher=ResponseFetcher(html),
                ),
            ).collect()
        finally:
            if old_value is None:
                os.environ.pop(MORRISONS_FEATURE_FLAG, None)
            else:
                os.environ[MORRISONS_FEATURE_FLAG] = old_value

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.collected_count, 1)
        self.assertEqual(len(result.raw_snapshots), 1)
        self.assertEqual(len(result.collection_attempts), 1)
        self.assertEqual(result.collection_attempts[0].status, "succeeded")

    def test_records_parser_failure_attempt(self) -> None:
        old_value = os.environ.get(MORRISONS_FEATURE_FLAG)
        os.environ[MORRISONS_FEATURE_FLAG] = "1"
        html = (FIXTURE_DIR / "morrisons_cornflakes_missing_unit_price.html").read_text(
            encoding="utf-8",
        )
        try:
            result = MorrisonsIngestionProvider(
                MorrisonsScraperConfig(
                    allowlisted_urls=(MORRISONS_URL,),
                    enabled=True,
                    fetcher=ResponseFetcher(html),
                ),
            ).collect()
        finally:
            if old_value is None:
                os.environ.pop(MORRISONS_FEATURE_FLAG, None)
            else:
                os.environ[MORRISONS_FEATURE_FLAG] = old_value

        self.assertEqual(result.status, "failed")
        self.assertEqual(len(result.raw_snapshots), 0)
        self.assertEqual(len(result.collection_attempts), 1)
        self.assertEqual(result.collection_attempts[0].error_code, "parse_error")
        self.assertIn("unit price", (result.collection_attempts[0].error_message or "").lower())


if __name__ == "__main__":
    unittest.main()
