from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "analytics" / "src"))
sys.path.insert(0, str(ROOT / "services" / "reporting" / "src"))

from basketguard_reporting import (  # noqa: E402
    DEFAULT_MIN_AUTO_MATCH_CONFIDENCE,
    fetch_group_comparison,
)


def _row(
    retailer: str,
    slug: str,
    title: str,
    unit_price: str,
    collected_at: str = "2026-06-10T08:00:00Z",
    human_reviewed: bool = False,
) -> tuple[Any, ...]:
    return (
        retailer,
        slug,
        title,
        Decimal("500"),
        "g",
        Decimal("2.50"),
        Decimal("2.25"),
        Decimal(unit_price),
        "kg",
        "in_stock",
        collected_at,
        f"snapshot-{slug}",
        Decimal("1.00"),
        human_reviewed,
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


class GroupComparisonReportTests(unittest.TestCase):
    def test_returns_entries_sorted_by_unit_price(self) -> None:
        connection = FakeConnection(
            [
                _row("Tesco", "tesco", "Tesco Corn Flakes 500G", "5.00"),
                _row("Asda", "asda", "ASDA Corn Flakes 500g", "2.70"),
            ],
        )

        report = fetch_group_comparison(connection, "own_brand_cornflakes_standard")

        self.assertEqual(report.group_slug, "own_brand_cornflakes_standard")
        self.assertEqual(report.retailer_count, 2)
        self.assertEqual(
            [entry.retailer_slug for entry in report.entries],
            ["asda", "tesco"],
        )
        cheapest = report.cheapest
        assert cheapest is not None
        self.assertEqual(cheapest.retailer_name, "Asda")
        self.assertEqual(cheapest.unit_price, Decimal("2.70"))
        self.assertEqual(cheapest.shelf_price, Decimal("2.50"))
        self.assertEqual(cheapest.effective_price, Decimal("2.25"))
        self.assertEqual(cheapest.pack_size_value, Decimal("500"))
        self.assertEqual(cheapest.pack_size_unit, "g")
        self.assertEqual(cheapest.availability, "in_stock")
        self.assertEqual(cheapest.collected_at, "2026-06-10T08:00:00Z")
        self.assertEqual(cheapest.raw_snapshot_id, "snapshot-asda")
        self.assertEqual(report.unit_price_gap, Decimal("2.30"))

    def test_query_filters_group_slug_and_confidence_floor(self) -> None:
        connection = FakeConnection([])

        fetch_group_comparison(connection, "own_brand_porridge_oats_standard")

        executions = connection.cursor_instance.executions
        self.assertEqual(len(executions), 1)
        sql, params = executions[0]
        self.assertEqual(
            params,
            ("own_brand_porridge_oats_standard", DEFAULT_MIN_AUTO_MATCH_CONFIDENCE),
        )
        self.assertIn("DISTINCT ON (retailers.id)", sql)
        self.assertIn("product_group_memberships.human_reviewed", sql)
        self.assertIn("product_group_memberships.match_confidence >= %s", sql)
        self.assertIn("price_observations.collected_at DESC", sql)
        self.assertIn("products.is_active", sql)
        self.assertTrue(connection.cursor_instance.closed)

    def test_supports_custom_confidence_floor(self) -> None:
        connection = FakeConnection([])

        fetch_group_comparison(
            connection,
            "own_brand_cornflakes_standard",
            min_auto_match_confidence=Decimal("0.95"),
        )

        _, params = connection.cursor_instance.executions[0]
        self.assertEqual(params[1], Decimal("0.95"))

    def test_empty_result_returns_empty_report(self) -> None:
        report = fetch_group_comparison(FakeConnection([]), "own_brand_cornflakes_standard")

        self.assertEqual(report.entries, ())
        self.assertEqual(report.retailer_count, 0)
        self.assertIsNone(report.cheapest)
        self.assertIsNone(report.most_expensive)
        self.assertIsNone(report.unit_price_gap)

    def test_coerces_driver_strings_to_decimal(self) -> None:
        row = list(_row("Tesco", "tesco", "Tesco Corn Flakes 500G", "5.00"))
        row[7] = "5.00"
        row[5] = "2.50"
        report = fetch_group_comparison(FakeConnection([tuple(row)]), "own_brand_cornflakes_standard")

        entry = report.entries[0]
        self.assertEqual(entry.unit_price, Decimal("5.00"))
        self.assertEqual(entry.shelf_price, Decimal("2.50"))


if __name__ == "__main__":
    unittest.main()
