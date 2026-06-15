from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path


PACKAGE_SRC = (
    Path(__file__).resolve().parents[1]
    / "packages"
    / "product-normalisation"
    / "src"
)
sys.path.insert(0, str(PACKAGE_SRC))

from basketguard_product_normalisation import (  # noqa: E402
    classify_product_flags,
    normalise_pack_size,
    normalise_unit_price,
    parse_pack_size,
    parse_unit_price,
)


class PackSizeParsingTests(unittest.TestCase):
    def test_parses_tinned_tomatoes_grams(self) -> None:
        parsed = parse_pack_size("Tesco Chopped Tomatoes 400G")

        self.assertEqual(parsed.amount, Decimal("400"))
        self.assertEqual(parsed.unit, "g")
        self.assertEqual(parsed.quantity, Decimal("1"))

    def test_parses_multipack_millilitres(self) -> None:
        parsed = parse_pack_size("Sparkling Water 6 x 500ml")

        self.assertEqual(parsed.amount, Decimal("500"))
        self.assertEqual(parsed.unit, "ml")
        self.assertEqual(parsed.quantity, Decimal("6"))
        self.assertEqual(parsed.raw_text, "6 x 500ml")

    def test_parses_washing_capsules(self) -> None:
        parsed = parse_pack_size("Ariel Washing Capsules 30 Washes")

        self.assertEqual(parsed.amount, Decimal("30"))
        self.assertEqual(parsed.unit, "wash")

    def test_parses_count_items_and_biscuits(self) -> None:
        items = parse_pack_size("Free Range Eggs 12 Items")
        biscuits = parse_pack_size("Wheat Biscuits 24 Biscuits")

        self.assertEqual(items.amount, Decimal("12"))
        self.assertEqual(items.unit, "item")
        self.assertEqual(biscuits.amount, Decimal("24"))
        self.assertEqual(biscuits.unit, "item")


class UnitNormalisationTests(unittest.TestCase):
    def test_normalises_cheese_to_kg(self) -> None:
        normalised = normalise_pack_size("Mature Cheddar 550g", "cheese")

        self.assertEqual(normalised.value, Decimal("0.55"))
        self.assertEqual(normalised.unit_basis, "kg")

    def test_normalises_pasta_to_kg(self) -> None:
        normalised = normalise_pack_size("Penne Pasta 1kg", "pasta")

        self.assertEqual(normalised.value, Decimal("1"))
        self.assertEqual(normalised.unit_basis, "kg")

    def test_normalises_milk_pints_to_litres(self) -> None:
        normalised = normalise_pack_size("British Semi Skimmed Milk 4 Pints", "milk")

        self.assertEqual(normalised.value, Decimal("2.273"))
        self.assertEqual(normalised.unit_basis, "litre")

    def test_normalises_milk_litres(self) -> None:
        normalised = normalise_pack_size("Semi Skimmed Milk 2.272L", "milk")

        self.assertEqual(normalised.value, Decimal("2.272"))
        self.assertEqual(normalised.unit_basis, "litre")

    def test_normalises_toilet_rolls(self) -> None:
        normalised = normalise_pack_size("Soft Toilet Tissue 9 Rolls", "toilet roll")

        self.assertEqual(normalised.value, Decimal("9"))
        self.assertEqual(normalised.unit_basis, "roll")

    def test_normalises_washing_capsules_to_washes(self) -> None:
        normalised = normalise_pack_size("Bio Washing Capsules 30 Capsules", "washing capsules")

        self.assertEqual(normalised.value, Decimal("30"))
        self.assertEqual(normalised.unit_basis, "wash")

    def test_normalises_count_pack_to_items(self) -> None:
        normalised = normalise_pack_size("Own Brand Wheat Biscuits 24 Pack", "wheat biscuits")

        self.assertEqual(normalised.value, Decimal("24"))
        self.assertEqual(normalised.unit_basis, "item")
        self.assertEqual(normalised.parsed.raw_text, "24 Pack")


class UnitPriceParsingTests(unittest.TestCase):
    def test_parses_unit_price_and_preserves_raw_text(self) -> None:
        parsed = parse_unit_price("Tesco Corn Flakes 10p/100g")

        self.assertEqual(parsed.price_gbp, Decimal("0.1"))
        self.assertEqual(parsed.per_amount, Decimal("100"))
        self.assertEqual(parsed.per_unit, "g")
        self.assertEqual(parsed.raw_text, "10p/100g")

    def test_normalises_pence_per_100g_to_gbp_per_kg(self) -> None:
        normalised = normalise_unit_price("Tesco Corn Flakes 10p/100g")

        self.assertEqual(normalised.value, Decimal("1"))
        self.assertEqual(normalised.unit_basis, "kg")

    def test_normalises_pence_per_100ml_to_gbp_per_litre(self) -> None:
        normalised = normalise_unit_price("Milk 65p/100ml")

        self.assertEqual(normalised.value, Decimal("6.5"))
        self.assertEqual(normalised.unit_basis, "litre")

    def test_normalises_pounds_per_kg(self) -> None:
        normalised = normalise_unit_price("Cheddar £5.50/kg")

        self.assertEqual(normalised.value, Decimal("5.5"))
        self.assertEqual(normalised.unit_basis, "kg")


class ProductClassificationTests(unittest.TestCase):
    def test_classifies_standard_own_brand(self) -> None:
        flags = classify_product_flags("Tesco Chopped Tomatoes 400G", retailer="Tesco")

        self.assertTrue(flags.is_own_brand)
        self.assertFalse(flags.is_value_range)
        self.assertFalse(flags.is_premium)
        self.assertEqual(flags.tier, "retailer_standard")

    def test_classifies_value_range(self) -> None:
        flags = classify_product_flags("Asda Just Essentials Baked Beans 410g", retailer="Asda")

        self.assertTrue(flags.is_own_brand)
        self.assertTrue(flags.is_value_range)
        self.assertEqual(flags.tier, "retailer_value")

    def test_classifies_premium_range(self) -> None:
        flags = classify_product_flags("Tesco Finest Mature Cheddar 400g", retailer="Tesco")

        self.assertTrue(flags.is_own_brand)
        self.assertTrue(flags.is_premium)
        self.assertEqual(flags.tier, "retailer_premium")

    def test_classifies_organic_above_retailer_tier(self) -> None:
        flags = classify_product_flags("Sainsbury's Organic Penne Pasta 500g", retailer="Sainsbury's")

        self.assertTrue(flags.is_own_brand)
        self.assertTrue(flags.is_organic)
        self.assertEqual(flags.tier, "organic")


if __name__ == "__main__":
    unittest.main()
