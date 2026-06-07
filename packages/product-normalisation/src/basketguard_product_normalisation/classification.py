from __future__ import annotations

from dataclasses import dataclass


RETAILER_BRANDS = {
    "tesco",
    "asda",
    "sainsbury's",
    "sainsburys",
    "morrisons",
    "waitrose",
    "ocado",
    "aldi",
    "lidl",
}

VALUE_SIGNALS = {
    "value",
    "everyday value",
    "just essentials",
    "essentials",
    "savers",
    "stockwell",
}

PREMIUM_SIGNALS = {
    "finest",
    "extra special",
    "taste the difference",
    "the best",
    "specially selected",
    "no.1",
    "no 1",
}

ORGANIC_SIGNALS = {"organic"}

MULTIPACK_SIGNALS = {
    "multipack",
    "multi pack",
    "twin pack",
    "double pack",
    "pack of",
}


@dataclass(frozen=True)
class ProductFlags:
    is_own_brand: bool
    is_value_range: bool
    is_premium: bool
    is_organic: bool
    is_multipack: bool
    tier: str | None


def classify_product_flags(product_name: str, retailer: str | None = None) -> ProductFlags:
    """Classify obvious product tier signals from a supermarket title."""

    text = _normalise_text(product_name)
    retailer_key = _normalise_text(retailer or "")

    is_value = any(signal in text for signal in VALUE_SIGNALS)
    is_premium = any(signal in text for signal in PREMIUM_SIGNALS)
    is_organic = any(signal in text for signal in ORGANIC_SIGNALS)
    is_multipack = any(signal in text for signal in MULTIPACK_SIGNALS)

    known_retailer_in_name = any(
        text == brand or text.startswith(f"{brand} ") for brand in RETAILER_BRANDS
    )
    retailer_matches_name = bool(retailer_key) and (
        text == retailer_key or text.startswith(f"{retailer_key} ")
    )
    is_own_brand = known_retailer_in_name or retailer_matches_name or is_value or is_premium

    tier = _classify_tier(is_own_brand, is_value, is_premium, is_organic)

    return ProductFlags(
        is_own_brand=is_own_brand,
        is_value_range=is_value,
        is_premium=is_premium,
        is_organic=is_organic,
        is_multipack=is_multipack,
        tier=tier,
    )


def _classify_tier(
    is_own_brand: bool,
    is_value: bool,
    is_premium: bool,
    is_organic: bool,
) -> str | None:
    if is_organic:
        return "organic"
    if is_value:
        return "retailer_value"
    if is_premium and is_own_brand:
        return "retailer_premium"
    if is_own_brand:
        return "retailer_standard"
    return None


def _normalise_text(value: str) -> str:
    return " ".join(value.lower().replace("&", " and ").split())
