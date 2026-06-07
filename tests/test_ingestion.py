from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))

from basketguard_ingestion import FixtureIngestionProvider  # noqa: E402


FIXTURE_PATH = ROOT / "tests" / "fixtures" / "seed_price_observations.json"


class FixtureIngestionProviderTests(unittest.TestCase):
    def test_collects_full_fixture(self) -> None:
        result = FixtureIngestionProvider(FIXTURE_PATH).collect()

        self.assertEqual(result.provider_name, "fixture")
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.target_count, 40)
        self.assertEqual(result.collected_count, 40)
        self.assertEqual(result.parser_error_count, 0)
        self.assertEqual(result.missing_price_count, 0)
        self.assertEqual(len(result.raw_snapshots), 40)
        self.assertEqual(len(result.parsed_products), 40)
        self.assertEqual(len(result.price_observations), 40)
        self.assertEqual(result.success_rate, Decimal("1"))

    def test_filters_by_retailer(self) -> None:
        result = FixtureIngestionProvider(FIXTURE_PATH).collect(retailer="Tesco")

        self.assertEqual(result.target_count, 10)
        self.assertEqual({snapshot.retailer for snapshot in result.raw_snapshots}, {"Tesco"})
        self.assertEqual({product.retailer for product in result.parsed_products}, {"Tesco"})
        self.assertEqual(
            {observation.retailer for observation in result.price_observations},
            {"Tesco"},
        )

    def test_filters_by_group(self) -> None:
        result = FixtureIngestionProvider(FIXTURE_PATH).collect(
            group_slug="own_brand_chopped_tomatoes_standard_400g",
        )

        self.assertEqual(result.target_count, 4)
        self.assertEqual(result.collected_count, 4)
        self.assertEqual(
            {product.product_type for product in result.parsed_products},
            {"Own-brand chopped tomatoes 400g"},
        )

    def test_product_and_price_records_share_external_product_ids(self) -> None:
        result = FixtureIngestionProvider(FIXTURE_PATH).collect(retailer="Asda")

        product_ids = {product.external_product_id for product in result.parsed_products}
        price_ids = {observation.external_product_id for observation in result.price_observations}
        snapshot_ids = {snapshot.external_product_id for snapshot in result.raw_snapshots}

        self.assertEqual(product_ids, price_ids)
        self.assertEqual(product_ids, snapshot_ids)

    def test_maps_fixture_to_expected_price_observation(self) -> None:
        result = FixtureIngestionProvider(FIXTURE_PATH).collect(
            retailer="Tesco",
            group_slug="own_brand_chopped_tomatoes_standard_400g",
        )
        observation = result.price_observations[0]

        self.assertEqual(observation.shelf_price, Decimal("0.55"))
        self.assertEqual(observation.effective_price, Decimal("0.55"))
        self.assertEqual(observation.unit_price, Decimal("1.375"))
        self.assertEqual(observation.unit_price_basis, "kg")
        self.assertEqual(observation.availability, "in_stock")

    def test_exports_dict_payload(self) -> None:
        payload = FixtureIngestionProvider(FIXTURE_PATH).collect_as_dicts(retailer="Morrisons")

        self.assertEqual(payload["provider_name"], "fixture")
        self.assertEqual(payload["target_count"], 10)
        self.assertEqual(len(payload["raw_snapshots"]), 10)
        self.assertEqual(payload["raw_snapshots"][0]["collection_status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
