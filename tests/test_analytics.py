from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path


PACKAGE_SRC = Path(__file__).resolve().parents[1] / "packages" / "analytics" / "src"
sys.path.insert(0, str(PACKAGE_SRC))

from basketguard_analytics import (  # noqa: E402
    AnalyticsError,
    competitor_median_yoy,
    current_premium_over_cheapest,
    historical_discount_strength,
    offender_score,
    retailer_excess_inflation,
    shrinkflation_effective_increase,
    yoy_increase,
)


class AnalyticsMetricTests(unittest.TestCase):
    def test_yoy_increase(self) -> None:
        self.assertEqual(yoy_increase("0.55", "0.35"), Decimal("0.5714"))

    def test_competitor_median_yoy_excludes_target_retailer(self) -> None:
        result = competitor_median_yoy(
            {
                "Tesco": Decimal("0.55"),
                "Asda": Decimal("0.05"),
                "Sainsbury's": Decimal("0.08"),
                "Morrisons": Decimal("0.12"),
            },
            "Tesco",
        )

        self.assertEqual(result, Decimal("0.08"))

    def test_retailer_excess_inflation(self) -> None:
        self.assertEqual(retailer_excess_inflation("0.55", "0.08"), Decimal("0.47"))

    def test_current_premium_over_cheapest(self) -> None:
        result = current_premium_over_cheapest("1.38", "0.95")

        self.assertEqual(result, Decimal("0.4526"))

    def test_historical_discount_strength(self) -> None:
        result = historical_discount_strength("2.60", "2.50")

        self.assertEqual(result, Decimal("0.0385"))

    def test_shrinkflation_effective_increase(self) -> None:
        result = shrinkflation_effective_increase(
            old_price="2.00",
            old_normalised_size="0.5",
            new_price="2.00",
            new_normalised_size="0.45",
        )

        self.assertEqual(result, Decimal("0.1111"))

    def test_offender_score(self) -> None:
        result = offender_score(
            retailer_excess_yoy_inflation_score=95,
            current_premium_score=90,
            shrinkflation_score=0,
            weak_promotion_score=0,
            volatility_score=30,
        )

        self.assertEqual(result, Decimal("63.5"))

    def test_rejects_zero_denominator(self) -> None:
        with self.assertRaises(AnalyticsError):
            current_premium_over_cheapest("1.00", "0")

    def test_rejects_out_of_range_score(self) -> None:
        with self.assertRaises(AnalyticsError):
            offender_score(101, 0)


if __name__ == "__main__":
    unittest.main()
