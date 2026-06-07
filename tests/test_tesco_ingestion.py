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
    TESCO_FEATURE_FLAG,
    TescoIngestionProvider,
    TescoProductPageParser,
    TescoScraperConfig,
)


FIXTURE_DIR = ROOT / "services" / "ingestion" / "fixtures"


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


if __name__ == "__main__":
    unittest.main()
