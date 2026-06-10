from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "analytics" / "src"))
sys.path.insert(0, str(ROOT / "services" / "reporting" / "src"))

from basketguard_reporting import fetch_review_required_products  # noqa: E402


def _row(
    review_item_id: str,
    title: str,
    group_slug: str,
    created_at: str,
    retailer: str | None = "Tesco",
    retailer_slug: str | None = "tesco",
) -> tuple[Any, ...]:
    return (
        review_item_id,
        retailer,
        retailer_slug,
        title,
        f"https://example.test/{review_item_id}",
        group_slug,
        Decimal("0.85"),
        "review:category_missing",
        created_at,
        f"snapshot-{review_item_id}",
    )


class FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows
        self.executions: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.executions.append((sql, params))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.cursor_instance = FakeCursor(rows)

    def cursor(self) -> FakeCursor:
        return self.cursor_instance


class ReviewRequiredReportTests(unittest.TestCase):
    def test_returns_open_items_with_evidence_fields(self) -> None:
        connection = FakeConnection(
            [
                _row("review-1", "Tesco Corn Flakes 500G", "own_brand_cornflakes_standard", "2026-06-01T08:00:00Z"),
                _row("review-2", "Tesco Porridge Oats 1Kg", "own_brand_porridge_oats_standard", "2026-06-02T08:00:00Z"),
            ],
        )

        report = fetch_review_required_products(connection)

        self.assertIsNone(report.group_slug_filter)
        self.assertEqual(report.item_count, 2)
        self.assertEqual(
            report.proposed_group_slugs,
            ("own_brand_cornflakes_standard", "own_brand_porridge_oats_standard"),
        )
        first = report.items[0]
        self.assertEqual(first.review_item_id, "review-1")
        self.assertEqual(first.retailer_name, "Tesco")
        self.assertEqual(first.product_title, "Tesco Corn Flakes 500G")
        self.assertEqual(first.product_url, "https://example.test/review-1")
        self.assertEqual(first.proposed_group_slug, "own_brand_cornflakes_standard")
        self.assertEqual(first.match_confidence, Decimal("0.85"))
        self.assertEqual(first.match_reason, "review:category_missing")
        self.assertEqual(first.created_at, "2026-06-01T08:00:00Z")
        self.assertEqual(first.raw_snapshot_id, "snapshot-review-1")

    def test_query_selects_open_items_oldest_first(self) -> None:
        connection = FakeConnection([])

        fetch_review_required_products(connection)

        executions = connection.cursor_instance.executions
        self.assertEqual(len(executions), 1)
        sql, params = executions[0]
        self.assertEqual(params, ())
        self.assertIn("review_queue_items.status = 'open'", sql)
        self.assertIn("ORDER BY review_queue_items.created_at ASC", sql)
        self.assertIn("LEFT JOIN products", sql)
        self.assertIn("LEFT JOIN raw_product_snapshots", sql)
        self.assertIn(
            "COALESCE(products.retailer_id, raw_product_snapshots.retailer_id)",
            sql,
        )
        self.assertTrue(connection.cursor_instance.closed)

    def test_group_slug_filter_is_bound_as_parameter(self) -> None:
        connection = FakeConnection([])

        report = fetch_review_required_products(connection, group_slug="own_brand_cornflakes_standard")

        sql, params = connection.cursor_instance.executions[0]
        self.assertEqual(params, ("own_brand_cornflakes_standard",))
        self.assertIn("AND equivalence_groups.slug = %s", sql)
        self.assertEqual(report.group_slug_filter, "own_brand_cornflakes_standard")

    def test_snapshot_only_item_tolerates_missing_product_fields(self) -> None:
        connection = FakeConnection(
            [
                (
                    "review-3",
                    None,
                    None,
                    "Raw snapshot title",
                    None,
                    "own_brand_cornflakes_standard",
                    "0.85",
                    None,
                    "2026-06-03T08:00:00Z",
                    "snapshot-review-3",
                ),
            ],
        )

        report = fetch_review_required_products(connection)

        item = report.items[0]
        self.assertIsNone(item.retailer_name)
        self.assertIsNone(item.product_url)
        self.assertEqual(item.product_title, "Raw snapshot title")
        self.assertEqual(item.match_confidence, Decimal("0.85"))
        self.assertIsNone(item.match_reason)

    def test_empty_queue_returns_empty_report(self) -> None:
        report = fetch_review_required_products(FakeConnection([]))

        self.assertEqual(report.items, ())
        self.assertEqual(report.item_count, 0)
        self.assertEqual(report.proposed_group_slugs, ())


if __name__ == "__main__":
    unittest.main()
