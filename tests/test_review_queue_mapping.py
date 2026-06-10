from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))

from basketguard_ingestion import (  # noqa: E402
    IngestionJobResult,
    IngestionPersistencePlan,
    IngestionPlanRepository,
    ParsedProduct,
    TescoProductPageParser,
    build_ingestion_persistence_plan,
)
from basketguard_product_normalisation import (  # noqa: E402
    load_equivalence_group_definitions,
)


FIXTURE_DIR = ROOT / "services" / "ingestion" / "fixtures"
DEFINITIONS_PATH = (
    ROOT / "packages" / "product-normalisation" / "fixtures" / "equivalence_group_definitions.json"
)
TESCO_URL = "https://www.tesco.com/groceries/en-GB/products/303030001"


def _ambiguous_cornflakes_result() -> IngestionJobResult:
    """A parse result whose product lacks a category, forcing needs_review."""

    html = (FIXTURE_DIR / "tesco_clubcard_cornflakes.html").read_text(encoding="utf-8")
    raw_snapshot, parsed_product, price_observation = TescoProductPageParser().parse(
        html=html,
        url=TESCO_URL,
        collected_at="2026-06-10T08:00:00Z",
        postcode_context="MVP default region",
    )
    ambiguous = ParsedProduct(
        retailer=parsed_product.retailer,
        external_product_id=parsed_product.external_product_id,
        url=parsed_product.url,
        canonical_name=parsed_product.canonical_name,
        brand=parsed_product.brand,
        category=None,
        subcategory=None,
        product_type=parsed_product.product_type,
        pack_size_value=parsed_product.pack_size_value,
        pack_size_unit=parsed_product.pack_size_unit,
        normalised_size_value=parsed_product.normalised_size_value,
        normalised_size_unit=parsed_product.normalised_size_unit,
        unit_basis=parsed_product.unit_basis,
        tier=parsed_product.tier,
        is_own_brand=parsed_product.is_own_brand,
        is_premium=parsed_product.is_premium,
        is_value_range=parsed_product.is_value_range,
        is_organic=parsed_product.is_organic,
        is_multipack=parsed_product.is_multipack,
    )
    return IngestionJobResult(
        provider_name="tesco",
        job_type="tesco_allowlisted_product_collection",
        status="succeeded",
        retailer="Tesco",
        target_count=1,
        collected_count=1,
        parser_error_count=0,
        missing_price_count=0,
        raw_snapshots=[raw_snapshot],
        parsed_products=[ambiguous],
        price_observations=[price_observation],
        notes="Live Tesco collection ran against explicit allowlisted URLs.",
    )


class ReviewQueueMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.definitions = load_equivalence_group_definitions(DEFINITIONS_PATH)

    def test_needs_review_candidate_emits_review_queue_item(self) -> None:
        plan = build_ingestion_persistence_plan(
            _ambiguous_cornflakes_result(),
            group_definitions=self.definitions,
        )

        self.assertEqual(plan.product_group_memberships, [])
        self.assertEqual(len(plan.review_queue_items), 1)
        item = plan.review_queue_items[0]
        self.assertEqual(item["product_id"], plan.products[0]["id"])
        self.assertEqual(item["raw_snapshot_id"], plan.raw_product_snapshots[0]["id"])
        self.assertEqual(item["match_confidence"], Decimal("0.85"))
        self.assertIn("review:category_missing", item["match_reason"])
        self.assertEqual(item["status"], "open")

        group_rows_by_slug = {row["slug"]: row for row in plan.equivalence_groups}
        self.assertIn("own_brand_cornflakes_standard", group_rows_by_slug)
        self.assertEqual(
            item["equivalence_group_id"],
            group_rows_by_slug["own_brand_cornflakes_standard"]["id"],
        )

    def test_review_item_ids_are_stable_for_same_snapshot(self) -> None:
        plan_one = build_ingestion_persistence_plan(
            _ambiguous_cornflakes_result(),
            group_definitions=self.definitions,
        )
        plan_two = build_ingestion_persistence_plan(
            _ambiguous_cornflakes_result(),
            group_definitions=self.definitions,
        )

        self.assertEqual(
            plan_one.review_queue_items[0]["id"],
            plan_two.review_queue_items[0]["id"],
        )

    def test_review_summary_and_job_notes_still_surfaced(self) -> None:
        plan = build_ingestion_persistence_plan(
            _ambiguous_cornflakes_result(),
            group_definitions=self.definitions,
        )

        self.assertEqual(len(plan.group_review_candidates), 1)
        self.assertIn(
            "needs_review_group_candidates=1",
            plan.ingestion_jobs[0]["notes"],
        )

    def test_no_definitions_means_no_review_items(self) -> None:
        plan = build_ingestion_persistence_plan(_ambiguous_cornflakes_result())

        self.assertEqual(plan.review_queue_items, [])


class FakeCursor:
    def __init__(self) -> None:
        self.executions: list[tuple[str, tuple[Any, ...]]] = []

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.executions.append((sql, params))

    def close(self) -> None:
        pass


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


class ReviewQueueRepositoryTests(unittest.TestCase):
    def test_review_items_saved_after_their_references(self) -> None:
        plan = IngestionPersistencePlan(
            equivalence_groups=[{"id": "group-id", "slug": "own_brand_cornflakes_standard"}],
            raw_product_snapshots=[{"id": "snapshot-id", "collection_status": "succeeded"}],
            products=[{"id": "product-id", "canonical_name": "Tesco Corn Flakes 500G"}],
            review_queue_items=[
                {
                    "id": "review-id",
                    "raw_snapshot_id": "snapshot-id",
                    "product_id": "product-id",
                    "equivalence_group_id": "group-id",
                    "match_confidence": Decimal("0.85"),
                    "status": "open",
                },
            ],
        )
        connection = FakeConnection()

        result = IngestionPlanRepository(connection).save_plan(plan)

        tables = [sql.split('"')[1] for sql, _ in connection.cursor_instance.executions]
        self.assertIn("review_queue_items", tables)
        for dependency in ("equivalence_groups", "raw_product_snapshots", "products"):
            self.assertLess(tables.index(dependency), tables.index("review_queue_items"))
        self.assertEqual(result.inserted_or_updated["review_queue_items"], 1)


if __name__ == "__main__":
    unittest.main()
