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
    fetch_basket_price_movement,
    fetch_group_price_analytics,
)


def _movement_row(
    retailer: str,
    slug: str,
    title: str,
    unit_price: str,
    collected_at: str,
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
        False,
    )


def _comparison_row(
    retailer: str,
    slug: str,
    title: str,
    unit_price: str,
    collected_at: str = "2026-06-15T08:00:00Z",
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
        False,
    )


class FakeCursor:
    def __init__(
        self,
        movement_rows: dict[tuple[str, int], list[tuple[Any, ...]]],
        comparison_rows: dict[str, list[tuple[Any, ...]]],
    ) -> None:
        self.movement_rows = movement_rows
        self.comparison_rows = comparison_rows
        self.executions: list[tuple[str, tuple[Any, ...]]] = []
        self.closed_count = 0
        self._last_params: tuple[Any, ...] | None = None

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.executions.append((sql, params))
        self._last_params = params

    def fetchall(self) -> list[tuple[Any, ...]]:
        if self._last_params is None:
            return []
        if len(self._last_params) == 3:
            return self.movement_rows.get((self._last_params[0], int(self._last_params[2])), [])
        return self.comparison_rows.get(str(self._last_params[0]), [])

    def close(self) -> None:
        self.closed_count += 1


class FakeConnection:
    def __init__(
        self,
        movement_rows: dict[tuple[str, int], list[tuple[Any, ...]]],
        comparison_rows: dict[str, list[tuple[Any, ...]]] | None = None,
    ) -> None:
        self.cursor_instance = FakeCursor(movement_rows, comparison_rows or {})

    def cursor(self) -> FakeCursor:
        return self.cursor_instance


class GroupPriceAnalyticsTests(unittest.TestCase):
    def test_group_analytics_combines_movement_yoy_and_retailer_gap(self) -> None:
        connection = FakeConnection(
            {
                ("own_brand_cornflakes_standard", 7): [
                    _movement_row("Asda", "asda", "ASDA Corn Flakes 500g", "2.70", "2026-06-08"),
                    _movement_row("Asda", "asda", "ASDA Corn Flakes 500g", "2.97", "2026-06-15"),
                ],
                ("own_brand_cornflakes_standard", 30): [
                    _movement_row("Asda", "asda", "ASDA Corn Flakes 500g", "2.50", "2026-05-16"),
                    _movement_row("Asda", "asda", "ASDA Corn Flakes 500g", "2.97", "2026-06-15"),
                ],
                ("own_brand_cornflakes_standard", 90): [
                    _movement_row("Asda", "asda", "ASDA Corn Flakes 500g", "2.20", "2026-03-17"),
                    _movement_row("Asda", "asda", "ASDA Corn Flakes 500g", "2.97", "2026-06-15"),
                ],
                ("own_brand_cornflakes_standard", 365): [
                    _movement_row("Asda", "asda", "ASDA Corn Flakes 500g", "1.98", "2025-06-15"),
                    _movement_row("Asda", "asda", "ASDA Corn Flakes 500g", "2.97", "2026-06-15"),
                ],
            },
            {
                "own_brand_cornflakes_standard": [
                    _comparison_row("Asda", "asda", "ASDA Corn Flakes 500g", "2.97"),
                    _comparison_row("Tesco", "tesco", "Tesco Corn Flakes 500G", "5.00"),
                ],
            },
        )

        report = fetch_group_price_analytics(connection, "own_brand_cornflakes_standard")

        self.assertEqual(report.group_slug, "own_brand_cornflakes_standard")
        self.assertEqual(report.retailer_gap.absolute_unit_price_gap, Decimal("2.03"))
        self.assertEqual(report.retailer_gap.percentage_unit_price_gap, Decimal("68.4"))
        asda = report.retailers[0]
        self.assertEqual([window.window_days for window in asda.movement_windows], [7, 30, 90])
        self.assertIsNotNone(asda.year_over_year)
        self.assertEqual(asda.year_over_year.absolute_unit_price_change, Decimal("0.99"))
        self.assertEqual(asda.year_over_year.percentage_unit_price_change, Decimal("50.0"))

        self.assertEqual(
            [params for _, params in connection.cursor_instance.executions],
            [
                ("own_brand_cornflakes_standard", DEFAULT_MIN_AUTO_MATCH_CONFIDENCE, 7),
                ("own_brand_cornflakes_standard", DEFAULT_MIN_AUTO_MATCH_CONFIDENCE, 30),
                ("own_brand_cornflakes_standard", DEFAULT_MIN_AUTO_MATCH_CONFIDENCE, 90),
                ("own_brand_cornflakes_standard", DEFAULT_MIN_AUTO_MATCH_CONFIDENCE, 365),
                ("own_brand_cornflakes_standard", DEFAULT_MIN_AUTO_MATCH_CONFIDENCE),
            ],
        )

    def test_group_analytics_omits_yoy_when_history_is_insufficient(self) -> None:
        report = fetch_group_price_analytics(
            FakeConnection(
                {
                    ("own_brand_cornflakes_standard", 365): [
                        _movement_row("Asda", "asda", "ASDA Corn Flakes 500g", "2.97", "2026-06-15"),
                    ],
                },
                {"own_brand_cornflakes_standard": []},
            ),
            "own_brand_cornflakes_standard",
        )

        self.assertIsNone(report.retailers[0].year_over_year)

    def test_basket_price_movement_sums_groups_and_reports_missing_groups(self) -> None:
        report = fetch_basket_price_movement(
            FakeConnection(
                {
                    ("own_brand_cornflakes_standard", 7): [
                        _movement_row("Asda", "asda", "ASDA Corn Flakes 500g", "2.70", "2026-06-08"),
                        _movement_row("Asda", "asda", "ASDA Corn Flakes 500g", "2.97", "2026-06-15"),
                        _movement_row("Tesco", "tesco", "Tesco Corn Flakes 500G", "4.50", "2026-06-08"),
                        _movement_row("Tesco", "tesco", "Tesco Corn Flakes 500G", "5.00", "2026-06-15"),
                    ],
                    ("own_brand_porridge_oats_standard", 7): [
                        _movement_row("Asda", "asda", "ASDA Porridge Oats 1kg", "1.50", "2026-06-08"),
                        _movement_row("Asda", "asda", "ASDA Porridge Oats 1kg", "1.65", "2026-06-15"),
                    ],
                },
            ),
            "basic_weekly_own_brand_basket",
            ["own_brand_cornflakes_standard", "own_brand_porridge_oats_standard"],
            windows=(7,),
        )

        self.assertEqual(report.basket_slug, "basic_weekly_own_brand_basket")
        self.assertEqual(report.group_slugs, ("own_brand_cornflakes_standard", "own_brand_porridge_oats_standard"))
        asda = report.retailers[0]
        self.assertEqual(asda.retailer_slug, "asda")
        self.assertEqual(asda.windows[0].earliest_total_unit_price, Decimal("4.20"))
        self.assertEqual(asda.windows[0].latest_total_unit_price, Decimal("4.62"))
        self.assertEqual(asda.windows[0].absolute_total_unit_price_change, Decimal("0.42"))
        self.assertEqual(asda.windows[0].percentage_total_unit_price_change, Decimal("10.0"))
        self.assertEqual(asda.windows[0].missing_group_count, 0)

        tesco = report.retailers[1]
        self.assertEqual(tesco.windows[0].present_group_count, 1)
        self.assertEqual(tesco.windows[0].missing_group_count, 1)
        self.assertEqual(tesco.windows[0].missing_group_slugs, ("own_brand_porridge_oats_standard",))

    def test_basket_price_movement_rejects_empty_group_list(self) -> None:
        with self.assertRaises(ValueError):
            fetch_basket_price_movement(FakeConnection({}), "empty_basket", [])


if __name__ == "__main__":
    unittest.main()
