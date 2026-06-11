from __future__ import annotations

import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))

from basketguard_product_normalisation import (  # noqa: E402
    EquivalenceGroupDefinitionError,
    GroupMatchCandidate,
    load_equivalence_group_definitions,
    match_equivalence_group,
)


FIXTURE_PATH = (
    ROOT / "packages" / "product-normalisation" / "fixtures" / "equivalence_group_definitions.json"
)


def _load_fixture_payload() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _write_payload(payload: dict) -> Path:
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    with handle:
        json.dump(payload, handle)
    return Path(handle.name)


class EquivalenceGroupLoaderTests(unittest.TestCase):
    def test_loads_mvp_group_definitions(self) -> None:
        definitions = load_equivalence_group_definitions(FIXTURE_PATH)

        self.assertEqual(
            [definition.slug for definition in definitions],
            [
                "own_brand_cornflakes_standard",
                "own_brand_porridge_oats_standard",
                "own_brand_spaghetti_standard",
                "own_brand_plain_flour_standard",
                "own_brand_granulated_sugar_standard",
                "own_brand_long_grain_rice_standard",
                "own_brand_baked_beans_standard",
            ],
        )
        cornflakes = definitions[0]
        self.assertEqual(cornflakes.status, "active")
        self.assertEqual(cornflakes.risk_level, "low")
        self.assertEqual(cornflakes.unit_basis, "kg")
        self.assertEqual(cornflakes.brand_owner, "retailer_own_label")
        self.assertEqual(cornflakes.tier, "retailer_standard")
        self.assertIn("corn flakes", cornflakes.title_contains_any)
        self.assertIn("kellogg", cornflakes.exclude_terms)
        self.assertEqual(cornflakes.size_range.min_value, Decimal("0.45"))
        self.assertEqual(cornflakes.size_range.max_value, Decimal("0.75"))
        self.assertEqual(cornflakes.auto_match_threshold, Decimal("0.92"))
        self.assertEqual(cornflakes.review_threshold, Decimal("0.75"))

    def test_rejects_duplicate_slugs(self) -> None:
        payload = _load_fixture_payload()
        payload["groups"].append(payload["groups"][0])
        path = _write_payload(payload)
        try:
            with self.assertRaises(EquivalenceGroupDefinitionError):
                load_equivalence_group_definitions(path)
        finally:
            path.unlink()

    def test_rejects_review_threshold_at_or_above_auto_threshold(self) -> None:
        payload = _load_fixture_payload()
        payload["groups"][0]["review_threshold"] = 0.92
        path = _write_payload(payload)
        try:
            with self.assertRaises(EquivalenceGroupDefinitionError):
                load_equivalence_group_definitions(path)
        finally:
            path.unlink()

    def test_rejects_missing_required_field(self) -> None:
        payload = _load_fixture_payload()
        del payload["groups"][0]["risk_level"]
        path = _write_payload(payload)
        try:
            with self.assertRaises(EquivalenceGroupDefinitionError):
                load_equivalence_group_definitions(path)
        finally:
            path.unlink()

    def test_rejects_unknown_review_trigger(self) -> None:
        payload = _load_fixture_payload()
        payload["groups"][0]["review_triggers"] = ["vibes"]
        path = _write_payload(payload)
        try:
            with self.assertRaises(EquivalenceGroupDefinitionError):
                load_equivalence_group_definitions(path)
        finally:
            path.unlink()

    def test_rejects_inverted_size_range(self) -> None:
        payload = _load_fixture_payload()
        payload["groups"][0]["size_range"] = {"min": 0.75, "max": 0.45}
        path = _write_payload(payload)
        try:
            with self.assertRaises(EquivalenceGroupDefinitionError):
                load_equivalence_group_definitions(path)
        finally:
            path.unlink()


class GroupMatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        definitions = load_equivalence_group_definitions(FIXTURE_PATH)
        self.cornflakes = definitions[0]
        self.porridge = definitions[1]

    def test_own_brand_cornflakes_auto_match(self) -> None:
        result = match_equivalence_group(
            GroupMatchCandidate(
                title="Tesco Corn Flakes 500G",
                category="Food Cupboard > Cereals > Cornflakes",
                brand_owner="retailer_own_label",
                tier="retailer_standard",
                normalised_size_value=Decimal("0.5"),
                normalised_size_unit="kg",
            ),
            self.cornflakes,
        )

        self.assertEqual(result.outcome, "auto_match")
        self.assertEqual(result.score, Decimal("1.00"))
        self.assertIn("product_type_supported", result.reasons)
        self.assertIn("size_in_range", result.reasons)

    def test_branded_cornflakes_hard_excluded(self) -> None:
        result = match_equivalence_group(
            GroupMatchCandidate(
                title="Kellogg's Corn Flakes 500G",
                category="Food Cupboard > Cereals > Cornflakes",
                brand_owner="national_brand",
                tier=None,
                normalised_size_value=Decimal("0.5"),
                normalised_size_unit="kg",
            ),
            self.cornflakes,
        )

        self.assertEqual(result.outcome, "no_match")
        self.assertEqual(result.score, Decimal("0"))
        self.assertEqual(result.exclusion_hits, ("kellogg",))

    def test_flavoured_variant_hard_excluded(self) -> None:
        result = match_equivalence_group(
            GroupMatchCandidate(
                title="Tesco Frosted Flakes 500G",
                category="Food Cupboard > Cereals",
                brand_owner="retailer_own_label",
                tier="retailer_standard",
                normalised_size_value=Decimal("0.5"),
                normalised_size_unit="kg",
            ),
            self.cornflakes,
        )

        self.assertEqual(result.outcome, "no_match")
        self.assertIn("frosted", result.exclusion_hits)

    def test_tier_conflict_never_auto_matches(self) -> None:
        result = match_equivalence_group(
            GroupMatchCandidate(
                title="Tesco Corn Flakes 500G",
                category="Food Cupboard > Cereals",
                brand_owner="retailer_own_label",
                tier="retailer_value",
                normalised_size_value=Decimal("0.5"),
                normalised_size_unit="kg",
            ),
            self.cornflakes,
        )

        self.assertEqual(result.outcome, "no_match")
        self.assertIn("tier_mismatch:retailer_value", result.reasons)

    def test_unit_basis_conflict_never_auto_matches(self) -> None:
        result = match_equivalence_group(
            GroupMatchCandidate(
                title="Tesco Corn Flakes 500G",
                category="Food Cupboard > Cereals",
                brand_owner="retailer_own_label",
                tier="retailer_standard",
                normalised_size_value=Decimal("0.5"),
                normalised_size_unit="litre",
            ),
            self.cornflakes,
        )

        self.assertEqual(result.outcome, "no_match")
        self.assertIn("unit_basis_mismatch:litre", result.reasons)

    def test_missing_category_goes_to_review(self) -> None:
        result = match_equivalence_group(
            GroupMatchCandidate(
                title="Tesco Corn Flakes 500G",
                category=None,
                brand_owner="retailer_own_label",
                tier="retailer_standard",
                normalised_size_value=Decimal("0.5"),
                normalised_size_unit="kg",
            ),
            self.cornflakes,
        )

        self.assertEqual(result.outcome, "needs_review")
        self.assertEqual(result.score, Decimal("0.85"))
        self.assertIn("review:category_missing", result.reasons)

    def test_size_out_of_range_goes_to_review(self) -> None:
        result = match_equivalence_group(
            GroupMatchCandidate(
                title="Tesco Corn Flakes 1Kg",
                category="Food Cupboard > Cereals > Cornflakes",
                brand_owner="retailer_own_label",
                tier="retailer_standard",
                normalised_size_value=Decimal("1.0"),
                normalised_size_unit="kg",
            ),
            self.cornflakes,
        )

        self.assertEqual(result.outcome, "needs_review")
        self.assertEqual(result.score, Decimal("0.95"))
        self.assertIn("review:size_out_of_range", result.reasons)

    def test_own_brand_porridge_oats_auto_match(self) -> None:
        result = match_equivalence_group(
            GroupMatchCandidate(
                title="Tesco Scottish Porridge Oats 1Kg",
                category="Food Cupboard > Cereals > Porridge & Oats",
                brand_owner="retailer_own_label",
                tier="retailer_standard",
                normalised_size_value=Decimal("1.0"),
                normalised_size_unit="kg",
            ),
            self.porridge,
        )

        self.assertEqual(result.outcome, "auto_match")
        self.assertEqual(result.score, Decimal("1.00"))

    def test_oat_sachets_hard_excluded_from_porridge(self) -> None:
        result = match_equivalence_group(
            GroupMatchCandidate(
                title="Tesco Golden Syrup Porridge Oats Sachets 10x36g",
                category="Food Cupboard > Cereals > Porridge & Oats",
                brand_owner="retailer_own_label",
                tier="retailer_standard",
                normalised_size_value=Decimal("0.36"),
                normalised_size_unit="kg",
            ),
            self.porridge,
        )

        self.assertEqual(result.outcome, "no_match")
        self.assertIn("sachet", result.exclusion_hits)

    def test_unrelated_product_is_no_match(self) -> None:
        result = match_equivalence_group(
            GroupMatchCandidate(
                title="Tesco Granulated Sugar 1Kg",
                category="Food Cupboard > Home Baking",
                brand_owner="retailer_own_label",
                tier="retailer_standard",
                normalised_size_value=Decimal("1.0"),
                normalised_size_unit="kg",
            ),
            self.cornflakes,
        )

        self.assertEqual(result.outcome, "no_match")
        self.assertIn("product_type_mismatch", result.reasons)


if __name__ == "__main__":
    unittest.main()
