from __future__ import annotations

import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))

from basketguard_product_normalisation import (  # noqa: E402
    GroupMatchCandidate,
    load_equivalence_group_definitions,
    match_equivalence_group,
    normalise_pack_size,
    normalise_unit_price,
    parse_product_attributes,
)


GROUP_DEFINITIONS_PATH = (
    ROOT / "packages" / "product-normalisation" / "fixtures" / "equivalence_group_definitions.json"
)
GOLD_DATASET_PATH = (
    ROOT / "packages" / "product-normalisation" / "fixtures" / "mvp_gold_validation_dataset.json"
)


class MvpGoldValidationDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = _load_json(GOLD_DATASET_PATH)
        cls.definition_payload = _load_json(GROUP_DEFINITIONS_PATH)
        definitions = load_equivalence_group_definitions(GROUP_DEFINITIONS_PATH)
        cls.definitions = {definition.slug: definition for definition in definitions}

    def test_dataset_targets_current_group_definition_version(self) -> None:
        self.assertEqual(self.dataset["version"], 1)
        self.assertEqual(
            self.dataset["equivalence_group_definition_version"],
            self.definition_payload["version"],
        )
        self.assertEqual(
            {group["slug"] for group in self.dataset["groups"]},
            {group["slug"] for group in self.definition_payload["groups"]},
        )

    def test_dataset_has_measurable_quality_thresholds(self) -> None:
        thresholds = self.dataset["quality_thresholds"]

        for key in (
            "parser_field_accuracy_min",
            "grouping_decision_accuracy_min",
            "review_routing_accuracy_min",
        ):
            with self.subTest(threshold=key):
                value = Decimal(thresholds[key])
                self.assertGreater(value, Decimal("0"))
                self.assertLessEqual(value, Decimal("1"))

    def test_each_group_has_auto_match_no_match_and_review_cases(self) -> None:
        for group in self.dataset["groups"]:
            outcomes = {case["expected"]["group_outcome"] for case in group["cases"]}

            with self.subTest(group=group["slug"]):
                self.assertEqual(outcomes, {"auto_match", "no_match", "needs_review"})

    def test_gold_cases_match_parser_and_grouping_expectations(self) -> None:
        for group in self.dataset["groups"]:
            definition = self.definitions[group["slug"]]
            for case in group["cases"]:
                with self.subTest(case=case["id"]):
                    expected = case["expected"]
                    attributes = parse_product_attributes(
                        case["title"],
                        retailer=case["retailer"],
                        category=case["category"],
                    )
                    normalised_size = normalise_pack_size(case["title"], attributes.product_type)
                    unit_price = normalise_unit_price(case["unit_price_text"])

                    self.assertEqual(attributes.brand_owner, expected["brand_owner"])
                    self.assertEqual(attributes.tier, expected["tier"])
                    self.assertEqual(attributes.product_type, expected["product_type"])
                    self.assertEqual(
                        attributes.exclusion_flags,
                        tuple(expected["exclusion_flags"]),
                    )
                    self.assertEqual(
                        normalised_size.value,
                        Decimal(expected["normalised_size_value"]),
                    )
                    self.assertEqual(
                        normalised_size.unit_basis,
                        expected["normalised_size_unit"],
                    )
                    self.assertEqual(unit_price.value, Decimal(expected["unit_price_value"]))
                    self.assertEqual(unit_price.unit_basis, expected["unit_price_basis"])

                    result = match_equivalence_group(
                        GroupMatchCandidate(
                            title=case["title"],
                            category=case["category"],
                            brand_owner=attributes.brand_owner,
                            tier=attributes.tier,
                            normalised_size_value=normalised_size.value,
                            normalised_size_unit=normalised_size.unit_basis,
                        ),
                        definition,
                    )

                    self.assertEqual(result.outcome, expected["group_outcome"])
                    if "reason_contains" in expected:
                        self.assertIn(expected["reason_contains"], result.reasons)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
