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
    fetch_retailer_gaps,
)


def _row(
    retailer: str,
    slug: str,
    title: str,
    unit_price: str,
    collected_at: str = "2026-06-10T08:00:00Z",
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
    def __init__(self, rows_by_slug: dict[str, list[tuple[Any, ...]]]) -> None:
        self.rows_by_slug = rows_by_slug
        self.executions: list[tuple[str, tuple[Any, ...]]] = []
        self.closed_count = 0
        self._last_slug: str | None = None

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.executions.append((sql, params))
        self._last_slug = params[0]

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows_by_slug.get(self._last_slug, [])

    def close(self) -> None:
        self.closed_count += 1


class FakeConnection:
    def __init__(self, rows_by_slug: dict[str, list[tuple[Any, ...]]]) -> None:
        self.cursor_instance = FakeCursor(rows_by_slug)

    def cursor(self) -> FakeCursor:
        return self.cursor_instance


class RetailerGapReportTests(unittest.TestCase):
    def _connection(self) -> FakeConnection:
        return FakeConnection(
            {
                "own_brand_cornflakes_standard": [
                    _row("Asda", "asda", "ASDA Corn Flakes 500g", "2.70"),
                    _row("Tesco", "tesco", "Tesco Corn Flakes 500G", "5.00"),
                ],
                "own_brand_porridge_oats_standard": [
                    _row("Asda", "asda", "ASDA Porridge Oats 1kg", "1.50"),
                ],
            },
        )

    def test_computes_gap_between_cheapest_and_dearest(self) -> None:
        report = fetch_retailer_gaps(
            self._connection(),
            ["own_brand_cornflakes_standard", "own_brand_porridge_oats_standard"],
        )

        cornflakes = report.gaps[0]
        self.assertEqual(cornflakes.group_slug, "own_brand_cornflakes_standard")
        self.assertEqual(cornflakes.cheapest_retailer, "Asda")
        self.assertEqual(cornflakes.cheapest_unit_price, Decimal("2.70"))
        self.assertEqual(cornflakes.most_expensive_retailer, "Tesco")
        self.assertEqual(cornflakes.most_expensive_unit_price, Decimal("5.00"))
        self.assertEqual(cornflakes.unit_price_basis, "kg")
        self.assertEqual(cornflakes.absolute_unit_price_gap, Decimal("2.30"))
        self.assertEqual(cornflakes.percentage_unit_price_gap, Decimal("85.2"))
        self.assertEqual(cornflakes.retailer_count, 2)
        self.assertEqual(cornflakes.missing_retailer_count, 0)
        self.assertEqual(cornflakes.missing_retailers, ())
        self.assertEqual(cornflakes.as_of, "2026-06-10T08:00:00Z")

    def test_missing_retailer_derived_from_report_union(self) -> None:
        report = fetch_retailer_gaps(
            self._connection(),
            ["own_brand_cornflakes_standard", "own_brand_porridge_oats_standard"],
        )

        porridge = report.gaps[1]
        self.assertEqual(porridge.retailer_count, 1)
        # Tesco appears in cornflakes but not porridge, so it is missing here.
        self.assertEqual(porridge.missing_retailer_count, 1)
        self.assertEqual(porridge.missing_retailers, ("tesco",))
        # A single retailer means no computable gap.
        self.assertIsNone(porridge.absolute_unit_price_gap)
        self.assertIsNone(porridge.percentage_unit_price_gap)
        self.assertEqual(porridge.cheapest_retailer, "Asda")
        self.assertEqual(porridge.most_expensive_retailer, "Asda")

    def test_empty_group_reports_all_tracked_retailers_missing(self) -> None:
        connection = FakeConnection(
            {
                "own_brand_cornflakes_standard": [
                    _row("Asda", "asda", "ASDA Corn Flakes 500g", "2.70"),
                    _row("Tesco", "tesco", "Tesco Corn Flakes 500G", "5.00"),
                ],
                "own_brand_spaghetti_standard": [],
            },
        )

        report = fetch_retailer_gaps(
            connection,
            ["own_brand_cornflakes_standard", "own_brand_spaghetti_standard"],
        )

        spaghetti = report.gaps[1]
        self.assertEqual(spaghetti.retailer_count, 0)
        self.assertEqual(spaghetti.missing_retailers, ("asda", "tesco"))
        self.assertIsNone(spaghetti.cheapest_retailer)
        self.assertIsNone(spaghetti.as_of)

    def test_widest_gap_first_orders_groups(self) -> None:
        report = fetch_retailer_gaps(
            self._connection(),
            ["own_brand_porridge_oats_standard", "own_brand_cornflakes_standard"],
        )

        ranked = report.widest_gap_first
        self.assertEqual(ranked[0].group_slug, "own_brand_cornflakes_standard")
        self.assertEqual(ranked[-1].group_slug, "own_brand_porridge_oats_standard")

    def test_passes_confidence_floor_to_comparison_query(self) -> None:
        connection = self._connection()

        fetch_retailer_gaps(
            connection,
            ["own_brand_cornflakes_standard"],
            min_auto_match_confidence=Decimal("0.95"),
        )

        _, params = connection.cursor_instance.executions[0]
        self.assertEqual(params, ("own_brand_cornflakes_standard", Decimal("0.95")))

    def test_defaults_to_standard_confidence_floor(self) -> None:
        connection = self._connection()

        fetch_retailer_gaps(connection, ["own_brand_cornflakes_standard"])

        _, params = connection.cursor_instance.executions[0]
        self.assertEqual(params[1], DEFAULT_MIN_AUTO_MATCH_CONFIDENCE)


if __name__ == "__main__":
    unittest.main()
