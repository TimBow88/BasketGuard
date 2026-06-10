from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))

from basketguard_ingestion import (  # noqa: E402
    ASDA_FEATURE_FLAG,
    AsdaIngestionProvider,
    AsdaParseError,
    AsdaProductPageParser,
    AsdaScraperConfig,
    ExtractedProduct,
    FetchResponse,
    TescoProductPageParser,
)


FIXTURE_DIR = ROOT / "services" / "ingestion" / "fixtures"
TESCO_URL = "https://www.tesco.com/groceries/en-GB/products/303030001"
ASDA_URL = "https://groceries.asda.com/product/cereal/100038316"
ASDA_OATS_URL = "https://groceries.asda.com/product/porridge-oats/910000448632"


class ResponseFetcher:
    def __init__(self, html: str) -> None:
        self.html = html

    def fetch(self, url: str, *, timeout_seconds: int, user_agent: str) -> FetchResponse:
        return FetchResponse(url=url, status_code=200, body=self.html)


class TescoExtractedProductTests(unittest.TestCase):
    def test_extract_returns_shared_contract(self) -> None:
        html = (FIXTURE_DIR / "tesco_clubcard_cornflakes.html").read_text(encoding="utf-8")
        extracted = TescoProductPageParser().extract(html, TESCO_URL)

        self.assertIsInstance(extracted, ExtractedProduct)
        self.assertEqual(extracted.retailer, "Tesco")
        self.assertEqual(extracted.title, "Tesco Corn Flakes 500G")
        self.assertEqual(extracted.price, "GBP 2.50")
        self.assertEqual(extracted.currency, "GBP")
        self.assertEqual(extracted.unit_price_text, "GBP 5.00/kg")
        self.assertEqual(extracted.pack_size_text, "500g")
        self.assertEqual(
            extracted.category_breadcrumb,
            "Food Cupboard > Cereals > Cornflakes",
        )
        self.assertEqual(extracted.availability, "in_stock")
        self.assertEqual(extracted.promotion_text, "Clubcard Price")
        self.assertEqual(extracted.external_product_id, "303030001")

    def test_extract_preserves_retailer_specific_raw_fields(self) -> None:
        html = (FIXTURE_DIR / "tesco_clubcard_cornflakes.html").read_text(encoding="utf-8")
        extracted = TescoProductPageParser().extract(html, TESCO_URL)

        self.assertEqual(extracted.raw_fields["clubcard-price"], "Clubcard Price GBP 2.25")
        self.assertEqual(extracted.raw_fields["meta:og:title"], "Tesco Corn Flakes 500G")

    def test_missing_fields_flags_absent_image_url(self) -> None:
        html = (FIXTURE_DIR / "tesco_clubcard_cornflakes.html").read_text(encoding="utf-8")
        extracted = TescoProductPageParser().extract(html, TESCO_URL)

        self.assertEqual(extracted.missing_fields, ("image_url",))


class AsdaExtractedProductTests(unittest.TestCase):
    def test_extract_returns_shared_contract(self) -> None:
        html = (FIXTURE_DIR / "asda_cornflakes.html").read_text(encoding="utf-8")
        extracted = AsdaProductPageParser().extract(html, ASDA_URL)

        self.assertIsInstance(extracted, ExtractedProduct)
        self.assertEqual(extracted.retailer, "Asda")
        self.assertEqual(extracted.title, "ASDA Corn Flakes 500g")
        self.assertEqual(extracted.price, "GBP 1.35")
        self.assertEqual(extracted.currency, "GBP")
        self.assertEqual(extracted.unit_price_text, "GBP 2.70/kg")
        self.assertEqual(extracted.pack_size_text, "500g")
        self.assertEqual(extracted.external_product_id, "100038316")

    def test_extract_flags_missing_price_fields(self) -> None:
        html = (FIXTURE_DIR / "asda_porridge_oats_missing_price.html").read_text(encoding="utf-8")
        extracted = AsdaProductPageParser().extract(html, ASDA_OATS_URL)

        self.assertEqual(extracted.title, "ASDA Scottish Porridge Oats 1kg")
        self.assertIn("price", extracted.missing_fields)
        self.assertIn("unit_price_text", extracted.missing_fields)
        self.assertNotIn("title", extracted.missing_fields)
        self.assertNotIn("category_breadcrumb", extracted.missing_fields)

    def test_parse_raises_for_missing_price_fixture(self) -> None:
        html = (FIXTURE_DIR / "asda_porridge_oats_missing_price.html").read_text(encoding="utf-8")
        with self.assertRaises(AsdaParseError):
            AsdaProductPageParser().parse(
                html=html,
                url=ASDA_OATS_URL,
                collected_at="2026-06-10T08:00:00Z",
            )

    def test_provider_records_missing_price_parser_failure(self) -> None:
        old_value = os.environ.get(ASDA_FEATURE_FLAG)
        os.environ[ASDA_FEATURE_FLAG] = "1"
        html = (FIXTURE_DIR / "asda_porridge_oats_missing_price.html").read_text(encoding="utf-8")
        try:
            result = AsdaIngestionProvider(
                AsdaScraperConfig(
                    allowlisted_urls=(ASDA_OATS_URL,),
                    enabled=True,
                    fetcher=ResponseFetcher(html),
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
        self.assertEqual(result.collection_attempts[0].status, "failed")
        self.assertEqual(result.collection_attempts[0].error_code, "parse_error")
        self.assertIn("money", (result.collection_attempts[0].error_message or "").lower())


if __name__ == "__main__":
    unittest.main()
