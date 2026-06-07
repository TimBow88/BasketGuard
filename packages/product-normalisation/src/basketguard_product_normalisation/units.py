from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


UK_PINT_IN_LITRES = Decimal("0.56826125")


UNIT_ALIASES = {
    "g": "g",
    "gram": "g",
    "grams": "g",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "ml": "ml",
    "millilitre": "ml",
    "millilitres": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "l": "l",
    "litre": "l",
    "litres": "l",
    "liter": "l",
    "liters": "l",
    "pint": "pint",
    "pints": "pint",
    "pt": "pint",
    "pts": "pint",
    "capsule": "capsule",
    "capsules": "capsule",
    "wash": "wash",
    "washes": "wash",
    "tablet": "tablet",
    "tablets": "tablet",
    "roll": "roll",
    "rolls": "roll",
    "sheet": "sheet",
    "sheets": "sheet",
    "nappy": "nappy",
    "nappies": "nappy",
}

UNIT_PATTERN = "|".join(
    sorted((re.escape(unit) for unit in UNIT_ALIASES), key=len, reverse=True)
)

PACK_SIZE_PATTERN = re.compile(
    rf"""
    (?:
      (?P<quantity>\d+(?:\.\d+)?)\s*(?:x|\*)\s*
    )?
    (?P<amount>\d+(?:\.\d+)?)\s*
    (?P<unit>{UNIT_PATTERN})\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

PACK_OF_PATTERN = re.compile(r"\bpack\s+of\s+(?P<amount>\d+(?:\.\d+)?)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedPackSize:
    amount: Decimal
    unit: str
    quantity: Decimal = Decimal("1")

    @property
    def total_amount(self) -> Decimal:
        return self.amount * self.quantity


@dataclass(frozen=True)
class NormalisedPackSize:
    value: Decimal
    unit_basis: str
    parsed: ParsedPackSize


class UnitNormalisationError(ValueError):
    pass


def parse_pack_size(text: str) -> ParsedPackSize:
    """Parse the first recognisable pack size from product text."""

    match = PACK_SIZE_PATTERN.search(text)
    if match:
        quantity = Decimal(match.group("quantity") or "1")
        amount = Decimal(match.group("amount"))
        unit = UNIT_ALIASES[match.group("unit").lower()]
        return ParsedPackSize(amount=amount, unit=unit, quantity=quantity)

    pack_of_match = PACK_OF_PATTERN.search(text)
    if pack_of_match:
        return ParsedPackSize(amount=Decimal(pack_of_match.group("amount")), unit="item")

    raise UnitNormalisationError(f"Could not parse pack size from: {text!r}")


def normalise_pack_size(
    text: str,
    product_type: str | None = None,
) -> NormalisedPackSize:
    """Parse and convert product size to a comparable unit basis."""

    parsed = parse_pack_size(text)
    target_basis = _target_basis(parsed.unit, product_type)
    value = _convert(parsed.total_amount, parsed.unit, target_basis)

    return NormalisedPackSize(
        value=_quantize(value),
        unit_basis=target_basis,
        parsed=parsed,
    )


def _target_basis(unit: str, product_type: str | None) -> str:
    product_key = " ".join((product_type or "").lower().split())

    if unit in {"g", "kg"}:
        return "kg"
    if unit in {"ml", "l", "pint"}:
        return "litre"
    if unit in {"capsule", "wash"}:
        return "wash"
    if unit == "tablet":
        return "tablet"
    if unit in {"roll", "sheet"}:
        if "toilet" in product_key and unit == "sheet":
            return "sheet"
        return unit
    if unit == "nappy":
        return "nappy"

    raise UnitNormalisationError(f"Unsupported unit: {unit!r}")


def _convert(value: Decimal, source_unit: str, target_basis: str) -> Decimal:
    if source_unit == target_basis:
        return value
    if source_unit == "g" and target_basis == "kg":
        return value / Decimal("1000")
    if source_unit == "kg" and target_basis == "kg":
        return value
    if source_unit == "ml" and target_basis == "litre":
        return value / Decimal("1000")
    if source_unit == "l" and target_basis == "litre":
        return value
    if source_unit == "pint" and target_basis == "litre":
        return value * UK_PINT_IN_LITRES
    if source_unit == "capsule" and target_basis == "wash":
        return value
    if source_unit == "wash" and target_basis == "wash":
        return value
    if source_unit == "tablet" and target_basis == "tablet":
        return value
    if source_unit == "roll" and target_basis == "roll":
        return value
    if source_unit == "sheet" and target_basis == "sheet":
        return value
    if source_unit == "nappy" and target_basis == "nappy":
        return value

    raise UnitNormalisationError(
        f"Cannot convert from {source_unit!r} to {target_basis!r}"
    )


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP).normalize()
