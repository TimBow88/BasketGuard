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
    DEFAULT_HISTORY_WINDOW_DAYS,
    DEFAULT_MIN_AUTO_MATCH_CONFIDENCE,
    fetch_group_price_history,
)


def _row(
    retailer: str,
    slug: str,
    title: str,
    unit_price: str,
    collected_at: str,
    human_reviewed: bool = False,
) -> tuple[Any, ...]:
    return (
        retailer,
        slug,
        title,
        Decimal("2.50"),
        Decimal("2.25"),
        Decimal(unit_price),
        "kg",
        "in_stock",
        collected_at,
        f"snapshot-{slug}-{collected_at}",
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


class GroupPriceHistoryTests(unittest.TestCase):
    def test_groups_observations_per_retailer_in_order(self) -> None:
        connection = FakeConnection(
            [
                _row("Asda", "asda", "ASDA Corn Flakes 500g", "2.50", "2026-04-01T08:00:00Z"),
                _row("Asda", "asda", "ASDA Corn Flakes 500g", "2.70", "2026-05-01T08:00:00Z"),
                _row("Tesco", "tesco", "Tesco Corn Flakes 500G", "5.00", "2026-05-01T08:00:00Z"),
            ],
        )

        report = fetch_group_price_history(connection, "own_brand_cornflakes_standard")

        self.assertEqual(report.group_slug, "own_brand_cornflakes_standard")
        self.assertEqual(report.window_days, DEFAULT_HISTORY_WINDOW_DAYS)
        self.assertEqual(report.retailer_count, 2)
        self.assertEqual(report.observation_count, 3)

        asda = report.retailers[0]
        self.assertEqual(asda.retailer_slug, "asda")
        self.assertEqual(len(asda.points), 2)
        self.assertEqual(asda.first.unit_price, Decimal("2.50"))
        self.assertEqual(asda.latest.unit_price, Decimal("2.70"))
        self.assertEqual(asda.unit_price_change, Decimal("0.20"))
        self.assertEqual(asda.first.collected_at, "2026-04-01T08:00:00Z")
        self.assertEqual(asda.latest.raw_snapshot_id, "snapshot-asda-2026-05-01T08:00:00Z")

        tesco = report.retailers[1]
        self.assertEqual(tesco.retailer_slug, "tesco")
        self.assertEqual(len(tesco.points), 1)
        self.assertIsNone(tesco.unit_price_change)

    def test_query_binds_slug_confidence_and_window(self) -> None:
        connection = FakeConnection([])

        fetch_group_price_history(connection, "own_brand_porridge_oats_standard", window_days=30)

        executions = connection.cursor_instance.executions
        self.assertEqual(len(executions), 1)
        sql, params = executions[0]
        self.assertEqual(
            params,
            ("own_brand_porridge_oats_standard", DEFAULT_MIN_AUTO_MATCH_CONFIDENCE, 30),
        )
        self.assertIn("product_group_memberships.human_reviewed", sql)
        self.assertIn("product_group_memberships.match_confidence >= %s", sql)
        self.assertIn("products.is_active", sql)
        self.assertIn("make_interval(days => %s)", sql)
        self.assertIn("price_observations.collected_at ASC", sql)
        self.assertTrue(connection.cursor_instance.closed)

    def test_custom_confidence_floor_is_passed_through(self) -> None:
        connection = FakeConnection([])

        fetch_group_price_history(
            connection,
            "own_brand_cornflakes_standard",
            window_days=7,
            min_auto_match_confidence=Decimal("0.95"),
        )

        _, params = connection.cursor_instance.executions[0]
        self.assertEqual(params, ("own_brand_cornflakes_standard", Decimal("0.95"), 7))

    def test_non_positive_window_is_rejected(self) -> None:
        connection = FakeConnection([])

        with self.assertRaises(ValueError):
            fetch_group_price_history(connection, "own_brand_cornflakes_standard", window_days=0)

    def test_empty_result_returns_empty_report(self) -> None:
        report = fetch_group_price_history(FakeConnection([]), "own_brand_cornflakes_standard")

        self.assertEqual(report.retailers, ())
        self.assertEqual(report.retailer_count, 0)
        self.assertEqual(report.observation_count, 0)

    def test_coerces_driver_strings_to_decimal(self) -> None:
        row = list(_row("Tesco", "tesco", "Tesco Corn Flakes 500G", "5.00", "2026-05-01T08:00:00Z"))
        row[5] = "5.00"
        row[3] = "2.50"
        report = fetch_group_price_history(
            FakeConnection([tuple(row)]),
            "own_brand_cornflakes_standard",
        )

        point = report.retailers[0].points[0]
        self.assertEqual(point.unit_price, Decimal("5.00"))
        self.assertEqual(point.shelf_price, Decimal("2.50"))


if __name__ == "__main__":
    unittest.main()
