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


def _cornflakes_result() -> IngestionJobResult:
    html = (FIXTURE_DIR / "tesco_clubcard_cornflakes.html").read_text(encoding="utf-8")
    raw_snapshot, parsed_product, price_observation = TescoProductPageParser().parse(
        html=html,
        url=TESCO_URL,
        collected_at="2026-06-10T08:00:00Z",
        postcode_context="MVP default region",
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
        parsed_products=[parsed_product],
        price_observations=[price_observation],
        notes="Live Tesco collection ran against explicit allowlisted URLs.",
    )


class GroupMembershipMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.definitions = load_equivalence_group_definitions(DEFINITIONS_PATH)

    def test_auto_match_emits_membership_row(self) -> None:
        plan = build_ingestion_persistence_plan(
            _cornflakes_result(),
            group_definitions=self.definitions,
        )

        self.assertEqual(len(plan.product_group_memberships), 1)
        membership = plan.product_group_memberships[0]
        self.assertEqual(membership["product_id"], plan.products[0]["id"])
        self.assertEqual(membership["match_confidence"], Decimal("1.00"))
        self.assertIn("product_type_supported", membership["match_reason"])
        self.assertTrue(membership["is_primary_match"])
        self.assertFalse(membership["human_reviewed"])

        group_rows_by_slug = {row["slug"]: row for row in plan.equivalence_groups}
        self.assertIn("own_brand_cornflakes_standard", group_rows_by_slug)
        group_row = group_rows_by_slug["own_brand_cornflakes_standard"]
        self.assertEqual(membership["equivalence_group_id"], group_row["id"])
        self.assertEqual(group_row["unit_basis"], "kg")
        self.assertEqual(group_row["tier"], "retailer_standard")
        self.assertEqual(plan.group_review_candidates, [])

    def test_membership_ids_are_stable_across_runs(self) -> None:
        plan_one = build_ingestion_persistence_plan(
            _cornflakes_result(),
            group_definitions=self.definitions,
        )
        plan_two = build_ingestion_persistence_plan(
            _cornflakes_result(),
            group_definitions=self.definitions,
        )

        self.assertEqual(
            plan_one.product_group_memberships[0]["id"],
            plan_two.product_group_memberships[0]["id"],
        )

    def test_needs_review_is_surfaced_without_membership_row(self) -> None:
        result = _cornflakes_result()
        ambiguous = ParsedProduct(
            retailer="Tesco",
            external_product_id="303030001",
            url=TESCO_URL,
            canonical_name="Tesco Corn Flakes 500G",
            brand="Tesco",
            category=None,
            subcategory=None,
            product_type="Tesco Corn Flakes 500G",
            pack_size_value=Decimal("500"),
            pack_size_unit="g",
            normalised_size_value=Decimal("0.5"),
            normalised_size_unit="kg",
            unit_basis="kg",
            tier="retailer_standard",
            is_own_brand=True,
            is_premium=False,
            is_value_range=False,
            is_organic=False,
            is_multipack=False,
        )
        result = IngestionJobResult(
            provider_name=result.provider_name,
            job_type=result.job_type,
            status=result.status,
            retailer=result.retailer,
            target_count=result.target_count,
            collected_count=result.collected_count,
            parser_error_count=0,
            missing_price_count=0,
            raw_snapshots=result.raw_snapshots,
            parsed_products=[ambiguous],
            price_observations=result.price_observations,
            notes=result.notes,
        )

        plan = build_ingestion_persistence_plan(result, group_definitions=self.definitions)

        self.assertEqual(plan.product_group_memberships, [])
        self.assertEqual(len(plan.group_review_candidates), 1)
        candidate = plan.group_review_candidates[0]
        self.assertEqual(candidate["group_slug"], "own_brand_cornflakes_standard")
        self.assertEqual(candidate["match_confidence"], Decimal("0.85"))
        self.assertIn("review:category_missing", candidate["match_reason"])
        self.assertIn(
            "needs_review_group_candidates=1",
            plan.ingestion_jobs[0]["notes"],
        )

    def test_plan_without_definitions_has_no_membership_rows(self) -> None:
        plan = build_ingestion_persistence_plan(_cornflakes_result())

        self.assertEqual(plan.product_group_memberships, [])
        self.assertEqual(plan.group_review_candidates, [])


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


class GroupMembershipRepositoryTests(unittest.TestCase):
    def test_memberships_are_saved_after_products_and_groups(self) -> None:
        plan = IngestionPersistencePlan(
            equivalence_groups=[{"id": "group-id", "slug": "own_brand_cornflakes_standard"}],
            products=[{"id": "product-id", "canonical_name": "Tesco Corn Flakes 500G"}],
            product_group_memberships=[
                {
                    "id": "membership-id",
                    "product_id": "product-id",
                    "equivalence_group_id": "group-id",
                    "match_confidence": Decimal("1.00"),
                },
            ],
            group_review_candidates=[{"group_slug": "ignored"}],
        )
        connection = FakeConnection()

        result = IngestionPlanRepository(connection).save_plan(plan)

        statements = [sql for sql, _ in connection.cursor_instance.executions]
        tables = [sql.split('"')[1] for sql in statements]
        self.assertIn("product_group_memberships", tables)
        self.assertLess(tables.index("products"), tables.index("product_group_memberships"))
        self.assertLess(
            tables.index("equivalence_groups"),
            tables.index("product_group_memberships"),
        )
        self.assertEqual(result.inserted_or_updated["product_group_memberships"], 1)
        # Review candidates are surfaced on the plan but never written to the DB.
        self.assertNotIn("group_review_candidates", tables)


if __name__ == "__main__":
    unittest.main()
