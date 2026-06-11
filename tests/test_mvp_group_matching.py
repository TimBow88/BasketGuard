from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))

from basketguard_product_normalisation import (  # noqa: E402
    GroupMatchCandidate,
    load_equivalence_group_definitions,
    match_equivalence_group,
)


FIXTURE_PATH = (
    ROOT / "packages" / "product-normalisation" / "fixtures" / "equivalence_group_definitions.json"
)


def _candidate(
    title: str,
    category: str | None,
    size: str,
    brand_owner: str = "retailer_own_label",
    tier: str | None = "retailer_standard",
    unit: str | None = "kg",
) -> GroupMatchCandidate:
    return GroupMatchCandidate(
        title=title,
        category=category,
        brand_owner=brand_owner,
        tier=tier,
        normalised_size_value=Decimal(size),
        normalised_size_unit=unit,
    )


class MvpGroupMatchingTests(unittest.TestCase):
    """Positive, negative and ambiguous fixtures for the five remaining MVP groups."""

    @classmethod
    def setUpClass(cls) -> None:
        definitions = load_equivalence_group_definitions(FIXTURE_PATH)
        cls.groups = {definition.slug: definition for definition in definitions}

    def _assert_all_auto_match(self, slug: str, candidates: list[GroupMatchCandidate]) -> None:
        for candidate in candidates:
            with self.subTest(title=candidate.title):
                result = match_equivalence_group(candidate, self.groups[slug])
                self.assertEqual(result.outcome, "auto_match")
                self.assertEqual(result.score, Decimal("1.00"))

    def _assert_no_match(self, slug: str, candidate: GroupMatchCandidate) -> None:
        result = match_equivalence_group(candidate, self.groups[slug])
        self.assertEqual(result.outcome, "no_match", msg=f"{candidate.title}: {result.reasons}")

    def _assert_needs_review(self, slug: str, candidate: GroupMatchCandidate) -> None:
        result = match_equivalence_group(candidate, self.groups[slug])
        self.assertEqual(result.outcome, "needs_review", msg=f"{candidate.title}: {result.reasons}")

    # --- Spaghetti -----------------------------------------------------------

    def test_own_brand_spaghetti_auto_matches_across_retailers(self) -> None:
        category = "Food Cupboard > Pasta > Spaghetti"
        self._assert_all_auto_match(
            "own_brand_spaghetti_standard",
            [
                _candidate("Tesco Spaghetti 500g", category, "0.5"),
                _candidate("ASDA Spaghetti 500g", category, "0.5"),
                _candidate("Sainsbury's Spaghetti 500g", category, "0.5"),
                _candidate("Morrisons Spaghetti 500g", category, "0.5"),
            ],
        )

    def test_spaghetti_negative_fixtures_are_rejected(self) -> None:
        slug = "own_brand_spaghetti_standard"
        category = "Food Cupboard > Pasta > Spaghetti"
        # Premium tier term is a hard exclusion.
        self._assert_no_match(slug, _candidate("Tesco Finest Spaghetti 500g", category, "0.5"))
        # Value tier conflicts with the group tier.
        self._assert_no_match(
            slug,
            _candidate("Stockwell & Co Spaghetti 500g", category, "0.5", tier="retailer_value"),
        )
        # Branded products have the wrong brand owner.
        self._assert_no_match(
            slug,
            _candidate("Napolina Spaghetti 500g", category, "0.5", brand_owner="national_brand"),
        )
        # Canned spaghetti hoops are a different product.
        self._assert_no_match(
            slug,
            _candidate("Tesco Spaghetti Hoops in Tomato Sauce 410g", "Food Cupboard > Tins", "0.41"),
        )
        # Wholewheat is not a substitute for standard spaghetti.
        self._assert_no_match(slug, _candidate("ASDA Wholewheat Spaghetti 500g", category, "0.5"))
        # A different pasta shape never title-matches.
        self._assert_no_match(slug, _candidate("Tesco Penne 500g", category, "0.5"))

    def test_spaghetti_missing_category_goes_to_review(self) -> None:
        self._assert_needs_review(
            "own_brand_spaghetti_standard",
            _candidate("Morrisons Spaghetti 500g", None, "0.5"),
        )

    # --- Plain flour ---------------------------------------------------------

    def test_own_brand_plain_flour_auto_matches_across_retailers(self) -> None:
        category = "Food Cupboard > Home Baking > Flour"
        self._assert_all_auto_match(
            "own_brand_plain_flour_standard",
            [
                _candidate("Tesco Plain Flour 1.5kg", category, "1.5"),
                _candidate("ASDA Plain Flour 1.5kg", category, "1.5"),
                _candidate("Sainsbury's Plain Flour 1.5kg", category, "1.5"),
                _candidate("Morrisons Plain Flour 1.5kg", category, "1.5"),
            ],
        )

    def test_plain_flour_negative_fixtures_are_rejected(self) -> None:
        slug = "own_brand_plain_flour_standard"
        category = "Food Cupboard > Home Baking > Flour"
        self._assert_no_match(slug, _candidate("Tesco Self Raising Flour 1.5kg", category, "1.5"))
        self._assert_no_match(
            slug, _candidate("ASDA Strong White Bread Flour 1.5kg", category, "1.5"),
        )
        self._assert_no_match(slug, _candidate("Sainsbury's Wholemeal Plain Flour 1kg", category, "1.0"))
        self._assert_no_match(
            slug,
            _candidate("McDougalls Plain Flour 1.1kg", category, "1.1", brand_owner="national_brand"),
        )
        self._assert_no_match(
            slug,
            _candidate(
                "Tesco Finest Organic Plain Flour 1kg",
                category,
                "1.0",
                tier="retailer_premium",
            ),
        )

    def test_plain_flour_missing_category_goes_to_review(self) -> None:
        self._assert_needs_review(
            "own_brand_plain_flour_standard",
            _candidate("Tesco Plain Flour 1.5kg", None, "1.5"),
        )

    # --- Granulated sugar ----------------------------------------------------

    def test_own_brand_granulated_sugar_auto_matches_across_retailers(self) -> None:
        category = "Food Cupboard > Home Baking > Sugar"
        self._assert_all_auto_match(
            "own_brand_granulated_sugar_standard",
            [
                _candidate("Tesco Granulated Sugar 1kg", category, "1.0"),
                _candidate("ASDA Granulated Sugar 1kg", category, "1.0"),
                _candidate("Sainsbury's Granulated Sugar 1kg", category, "1.0"),
                _candidate("Morrisons Granulated Sugar 1kg", category, "1.0"),
            ],
        )

    def test_granulated_sugar_negative_fixtures_are_rejected(self) -> None:
        slug = "own_brand_granulated_sugar_standard"
        category = "Food Cupboard > Home Baking > Sugar"
        self._assert_no_match(slug, _candidate("Tesco Caster Sugar 1kg", category, "1.0"))
        self._assert_no_match(slug, _candidate("ASDA Demerara Sugar 500g", category, "0.5"))
        self._assert_no_match(slug, _candidate("Morrisons Light Brown Sugar 500g", category, "0.5"))
        self._assert_no_match(
            slug,
            _candidate(
                "Silver Spoon Granulated Sugar 1kg",
                category,
                "1.0",
                brand_owner="national_brand",
            ),
        )
        self._assert_no_match(
            slug,
            _candidate("Tesco Granulated Sugar 1kg", category, "1.0", tier="retailer_value"),
        )

    def test_granulated_sugar_bulk_pack_goes_to_review(self) -> None:
        # 5kg catering packs sit outside the comparable size range.
        self._assert_needs_review(
            "own_brand_granulated_sugar_standard",
            _candidate("Tesco Granulated Sugar 5kg", "Food Cupboard > Home Baking > Sugar", "5.0"),
        )

    # --- Long grain rice -----------------------------------------------------

    def test_own_brand_long_grain_rice_auto_matches_across_retailers(self) -> None:
        category = "Food Cupboard > Rice, Pasta & Pulses > Rice"
        self._assert_all_auto_match(
            "own_brand_long_grain_rice_standard",
            [
                _candidate("Tesco Long Grain Rice 1kg", category, "1.0"),
                _candidate("ASDA Long Grain Rice 1kg", category, "1.0"),
                _candidate("Sainsbury's Long Grain Rice 1kg", category, "1.0"),
                _candidate("Morrisons Long Grain Rice 1kg", category, "1.0"),
            ],
        )

    def test_long_grain_rice_negative_fixtures_are_rejected(self) -> None:
        slug = "own_brand_long_grain_rice_standard"
        category = "Food Cupboard > Rice, Pasta & Pulses > Rice"
        self._assert_no_match(slug, _candidate("Tesco Basmati Rice 1kg", category, "1.0"))
        self._assert_no_match(
            slug, _candidate("ASDA Wholegrain Long Grain Rice 1kg", category, "1.0"),
        )
        self._assert_no_match(
            slug, _candidate("Sainsbury's Microwave Long Grain Rice 250g", category, "0.25"),
        )
        self._assert_no_match(
            slug,
            _candidate("Tilda Long Grain Rice 1kg", category, "1.0", brand_owner="national_brand"),
        )
        self._assert_no_match(
            slug,
            _candidate(
                "Morrisons Savers Long Grain Rice 1kg",
                category,
                "1.0",
                tier="retailer_value",
            ),
        )

    def test_long_grain_rice_missing_category_goes_to_review(self) -> None:
        self._assert_needs_review(
            "own_brand_long_grain_rice_standard",
            _candidate("Sainsbury's Long Grain Rice 1kg", None, "1.0"),
        )

    # --- Baked beans ---------------------------------------------------------

    def test_own_brand_baked_beans_auto_matches_across_retailers(self) -> None:
        category = "Food Cupboard > Tins & Cans > Baked Beans"
        self._assert_all_auto_match(
            "own_brand_baked_beans_standard",
            [
                _candidate("Tesco Baked Beans in Tomato Sauce 420g", category, "0.42"),
                _candidate("ASDA Baked Beans in Tomato Sauce 410g", category, "0.41"),
                _candidate("Sainsbury's Baked Beans in Tomato Sauce 400g", category, "0.40"),
                _candidate("Morrisons Baked Beans in Tomato Sauce 410g", category, "0.41"),
            ],
        )

    def test_baked_beans_negative_fixtures_are_rejected(self) -> None:
        slug = "own_brand_baked_beans_standard"
        category = "Food Cupboard > Tins & Cans > Baked Beans"
        self._assert_no_match(
            slug,
            _candidate("Heinz Baked Beans 415g", category, "0.415", brand_owner="national_brand"),
        )
        self._assert_no_match(
            slug, _candidate("Tesco Baked Beans & Sausages 395g", category, "0.395"),
        )
        self._assert_no_match(
            slug, _candidate("ASDA Reduced Sugar Baked Beans 410g", category, "0.41"),
        )
        self._assert_no_match(
            slug, _candidate("Sainsbury's Curried Baked Beans 400g", category, "0.40"),
        )
        self._assert_no_match(
            slug,
            _candidate(
                "Morrisons Baked Beans in Tomato Sauce 410g",
                category,
                "0.41",
                tier="retailer_value",
            ),
        )
        # Kidney beans never title-match the baked beans group.
        self._assert_no_match(slug, _candidate("Tesco Red Kidney Beans 400g", category, "0.40"))

    def test_baked_beans_multipack_size_goes_to_review(self) -> None:
        # A 4x410g multipack is outside the single-can size range.
        self._assert_needs_review(
            "own_brand_baked_beans_standard",
            _candidate(
                "Tesco Baked Beans in Tomato Sauce 4x410g",
                "Food Cupboard > Tins & Cans > Baked Beans",
                "1.64",
            ),
        )


if __name__ == "__main__":
    unittest.main()
