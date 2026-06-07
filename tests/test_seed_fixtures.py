from __future__ import annotations

import json
import sys
import unittest
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ANALYTICS_SRC = Path(__file__).resolve().parents[1] / "packages" / "analytics" / "src"
sys.path.insert(0, str(ANALYTICS_SRC))

from basketguard_analytics import (  # noqa: E402
    competitor_median_yoy,
    current_premium_over_cheapest,
    offender_score,
    retailer_excess_inflation,
    yoy_increase,
)


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "seed_price_observations.json"


class SeedFixtureTests(unittest.TestCase):
    def test_fixture_has_ten_groups_across_four_retailers(self) -> None:
        fixture = _load_fixture()

        self.assertEqual(len(fixture["groups"]), 10)
        for group in fixture["groups"]:
            retailers = {observation["retailer"] for observation in group["observations"]}
            self.assertEqual(retailers, {"Tesco", "Asda", "Sainsbury's", "Morrisons"})

    def test_generates_ranked_offender_list_from_seed_data(self) -> None:
        ranked = _rank_offenders(_load_fixture())

        self.assertEqual(len(ranked), 40)
        self.assertEqual(ranked[0]["group_slug"], "own_brand_chopped_tomatoes_standard_400g")
        self.assertEqual(ranked[0]["retailer"], "Tesco")
        self.assertGreater(ranked[0]["offender_score"], Decimal("55"))

        top_five = {(finding["group_slug"], finding["retailer"]) for finding in ranked[:5]}
        self.assertIn(("own_brand_baked_beans_standard_410g", "Asda"), top_five)
        self.assertIn(("own_brand_dishwasher_tablets_30_tablets", "Sainsbury's"), top_five)


def _rank_offenders(fixture: dict) -> list[dict]:
    findings = []

    for group in fixture["groups"]:
        enriched_observations = []
        yoy_by_retailer = {}

        for observation in group["observations"]:
            current_unit_price = _unit_price(observation["current"])
            previous_unit_price = _unit_price(observation["previous_year"])
            yoy = yoy_increase(current_unit_price, previous_unit_price)

            enriched = {
                **observation,
                "current_unit_price": current_unit_price,
                "previous_unit_price": previous_unit_price,
                "yoy": yoy,
            }
            enriched_observations.append(enriched)
            yoy_by_retailer[observation["retailer"]] = yoy

        cheapest_unit_price = min(
            observation["current_unit_price"] for observation in enriched_observations
        )

        for observation in enriched_observations:
            competitor_yoy = competitor_median_yoy(
                yoy_by_retailer,
                observation["retailer"],
            )
            excess = retailer_excess_inflation(observation["yoy"], competitor_yoy)
            premium = current_premium_over_cheapest(
                observation["current_unit_price"],
                cheapest_unit_price,
            )
            score = offender_score(
                retailer_excess_yoy_inflation_score=_ratio_to_score(excess, Decimal("0.5")),
                current_premium_score=_ratio_to_score(premium, Decimal("0.5")),
            )

            findings.append(
                {
                    "group_slug": group["slug"],
                    "retailer": observation["retailer"],
                    "product_name": observation["product_name"],
                    "yoy": observation["yoy"],
                    "competitor_median_yoy": competitor_yoy,
                    "current_premium": premium,
                    "offender_score": score,
                }
            )

    return sorted(
        findings,
        key=lambda finding: (
            finding["offender_score"],
            finding["current_premium"],
            finding["yoy"],
        ),
        reverse=True,
    )


def _unit_price(observation: dict) -> Decimal:
    price = Decimal(observation["price"])
    size = Decimal(observation["normalised_size"])
    return (price / size).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP).normalize()


def _ratio_to_score(value: Decimal, cap: Decimal) -> Decimal:
    if value <= 0:
        return Decimal("0")
    return min(Decimal("100"), (value / cap * Decimal("100")))


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
