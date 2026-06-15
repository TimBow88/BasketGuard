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
    PRICE_MOVEMENT_WINDOWS,
    fetch_group_price_movement,
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
        Decimal(unit_price),
        "kg",
        "in_stock",
        collected_at,
        f"snapshot-{slug}-{collected_at}",
        Decimal("1.00"),
        human_reviewed,
    )


class FakeCursor:
    def __init__(self, rows_by_window: dict[int, list[tuple[Any, ...]]]) -> None:
        self.rows_by_window = rows_by_window
        self.executions: list[tuple[str, tuple[Any, ...]]] = []
        self.closed_count = 0
        self._last_window: int | None = None

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.executions.append((sql, params))
        self._last_window = int(params[2])

    def fetchall(self) -> list[tuple[Any, ...]]:
        if self._last_window is None:
            return []
        return self.rows_by_window.get(self._last_window, [])

    def close(self) -> None:
        self.closed_count += 1


class FakeConnection:
    def __init__(self, rows_by_window: dict[int, list[tuple[Any, ...]]]) -> None:
        self.cursor_instance = FakeCursor(rows_by_window)

    def cursor(self) -> FakeCursor:
        return self.cursor_instance


class GroupPriceMovementTests(unittest.TestCase):
    def test_computes_price_movement_for_each_retailer_window(self) -> None:
        connection = FakeConnection(
            {
                7: [
                    _row("Asda", "asda", "ASDA Corn Flakes 500g", "2.70", "2026-06-08T08:00:00Z"),
                    _row("Asda", "asda", "ASDA Corn Flakes 500g", "2.97", "2026-06-15T08:00:00Z"),
                ],
                30: [
                    _row("Asda", "asda", "ASDA Corn Flakes 500g", "2.50", "2026-05-16T08:00:00Z"),
                    _row("Asda", "asda", "ASDA Corn Flakes 500g", "2.97", "2026-06-15T08:00:00Z"),
                    _row("Tesco", "tesco", "Tesco Corn Flakes 500G", "4.50", "2026-06-01T08:00:00Z"),
                    _row("Tesco", "tesco", "Tesco Corn Flakes 500G", "5.00", "2026-06-15T08:00:00Z"),
                ],
                90: [
                    _row("Asda", "asda", "ASDA Corn Flakes 500g", "2.20", "2026-03-17T08:00:00Z"),
                    _row("Asda", "asda", "ASDA Corn Flakes 500g", "2.97", "2026-06-15T08:00:00Z"),
                    _row("Tesco", "tesco", "Tesco Corn Flakes 500G", "4.00", "2026-03-17T08:00:00Z"),
                    _row("Tesco", "tesco", "Tesco Corn Flakes 500G", "5.00", "2026-06-15T08:00:00Z"),
                ],
            },
        )

        report = fetch_group_price_movement(connection, "own_brand_cornflakes_standard")

        self.assertEqual(report.group_slug, "own_brand_cornflakes_standard")
        self.assertEqual(report.retailer_count, 2)
        asda = report.retailers[0]
        self.assertEqual(asda.retailer_slug, "asda")
        self.assertEqual([window.window_days for window in asda.windows], list(PRICE_MOVEMENT_WINDOWS))

        seven_day = asda.windows[0]
        self.assertEqual(seven_day.earliest.unit_price, Decimal("2.70"))
        self.assertEqual(seven_day.latest.unit_price, Decimal("2.97"))
        self.assertEqual(seven_day.absolute_unit_price_change, Decimal("0.27"))
        self.assertEqual(seven_day.percentage_unit_price_change, Decimal("10.0"))
        self.assertEqual(seven_day.observation_count, 2)
        self.assertEqual(seven_day.latest.raw_snapshot_id, "snapshot-asda-2026-06-15T08:00:00Z")

        ninety_day = asda.windows[2]
        self.assertEqual(ninety_day.absolute_unit_price_change, Decimal("0.77"))
        self.assertEqual(ninety_day.percentage_unit_price_change, Decimal("35.0"))

        tesco = report.retailers[1]
        self.assertEqual(tesco.windows[1].absolute_unit_price_change, Decimal("0.50"))
        self.assertEqual(tesco.windows[1].percentage_unit_price_change, Decimal("11.1"))

    def test_empty_window_is_returned_for_retailer_seen_elsewhere(self) -> None:
        report = fetch_group_price_movement(
            FakeConnection(
                {
                    7: [],
                    30: [
                        _row("Tesco", "tesco", "Tesco Corn Flakes 500G", "5.00", "2026-06-15T08:00:00Z"),
                    ],
                    90: [
                        _row("Tesco", "tesco", "Tesco Corn Flakes 500G", "4.00", "2026-03-17T08:00:00Z"),
                        _row("Tesco", "tesco", "Tesco Corn Flakes 500G", "5.00", "2026-06-15T08:00:00Z"),
                    ],
                },
            ),
            "own_brand_cornflakes_standard",
        )

        tesco = report.retailers[0]
        seven_day = tesco.windows[0]
        self.assertIsNone(seven_day.earliest)
        self.assertIsNone(seven_day.latest)
        self.assertIsNone(seven_day.absolute_unit_price_change)
        self.assertIsNone(seven_day.percentage_unit_price_change)
        self.assertEqual(seven_day.observation_count, 0)

    def test_query_binds_slug_confidence_and_each_window(self) -> None:
        connection = FakeConnection({})

        fetch_group_price_movement(connection, "own_brand_porridge_oats_standard")

        executions = connection.cursor_instance.executions
        self.assertEqual(len(executions), 3)
        self.assertEqual(connection.cursor_instance.closed_count, 3)
        self.assertEqual(
            [params for _, params in executions],
            [
                ("own_brand_porridge_oats_standard", DEFAULT_MIN_AUTO_MATCH_CONFIDENCE, 7),
                ("own_brand_porridge_oats_standard", DEFAULT_MIN_AUTO_MATCH_CONFIDENCE, 30),
                ("own_brand_porridge_oats_standard", DEFAULT_MIN_AUTO_MATCH_CONFIDENCE, 90),
            ],
        )
        sql, _ = executions[0]
        self.assertIn("product_group_memberships.human_reviewed", sql)
        self.assertIn("product_group_memberships.match_confidence >= %s", sql)
        self.assertIn("products.is_active", sql)
        self.assertIn("make_interval(days => %s)", sql)

    def test_empty_result_returns_empty_report(self) -> None:
        report = fetch_group_price_movement(FakeConnection({}), "own_brand_cornflakes_standard")

        self.assertEqual(report.retailers, ())
        self.assertEqual(report.retailer_count, 0)

    def test_custom_windows_and_confidence_floor_are_passed_through(self) -> None:
        connection = FakeConnection({})

        fetch_group_price_movement(
            connection,
            "own_brand_cornflakes_standard",
            windows=(14,),
            min_auto_match_confidence=Decimal("0.95"),
        )

        _, params = connection.cursor_instance.executions[0]
        self.assertEqual(params, ("own_brand_cornflakes_standard", Decimal("0.95"), 14))

    def test_invalid_windows_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            fetch_group_price_movement(FakeConnection({}), "own_brand_cornflakes_standard", windows=())
        with self.assertRaises(ValueError):
            fetch_group_price_movement(
                FakeConnection({}),
                "own_brand_cornflakes_standard",
                windows=(7, 0),
            )

    def test_coerces_driver_strings_to_decimal(self) -> None:
        row = list(_row("Tesco", "tesco", "Tesco Corn Flakes 500G", "5.00", "2026-06-15T08:00:00Z"))
        row[3] = "5.00"

        report = fetch_group_price_movement(
            FakeConnection({7: [tuple(row)]}),
            "own_brand_cornflakes_standard",
            windows=(7,),
        )

        window = report.retailers[0].windows[0]
        self.assertEqual(window.latest.unit_price, Decimal("5.00"))
        self.assertEqual(window.absolute_unit_price_change, Decimal("0.00"))
        self.assertEqual(window.percentage_unit_price_change, Decimal("0.0"))


if __name__ == "__main__":
    unittest.main()
