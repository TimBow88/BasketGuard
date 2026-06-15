from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


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

NATIONAL_BRAND_SIGNALS = {
    "kellogg",
    "kellogg's",
    "heinz",
    "young's",
    "youngs",
    "birdseye",
    "birds eye",
}

FREE_FROM_SIGNALS = {"free from", "gluten free"}

PRODUCT_TYPE_SIGNALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cornflakes", ("corn flakes", "cornflakes")),
    ("porridge_oats", ("porridge oats", "rolled oats", "oats")),
    ("wheat_biscuits", ("wheat biscuits", "wheat biscuit")),
    ("spaghetti", ("spaghetti",)),
    ("baked_beans", ("baked beans",)),
    ("long_grain_rice", ("long grain rice",)),
    ("plain_flour", ("plain flour",)),
    ("granulated_sugar", ("granulated sugar",)),
)

EXCLUSION_SIGNALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("gluten_free", ("gluten free",)),
    ("free_from", ("free from",)),
    ("frosted", ("frosted",)),
    ("flavoured", ("chocolate", "honey", "cinnamon", "strawberry", "fruit")),
    ("porridge_sachet", ("sachet", "sachets", "instant pot", "protein porridge")),
    ("jumbo_oats", ("jumbo oats",)),
)

BrandOwner = Literal["retailer_own_label", "national_brand", "licensed_brand", "unknown"]
ParsedTier = Literal[
    "retailer_value",
    "retailer_standard",
    "retailer_premium",
    "retailer_organic",
    "specialist_dietary",
    "national_brand_standard",
    "national_brand_premium",
    "unknown",
]


@dataclass(frozen=True)
class ProductFlags:
    is_own_brand: bool
    is_value_range: bool
    is_premium: bool
    is_organic: bool
    is_multipack: bool
    tier: str | None


@dataclass(frozen=True)
class ParsedProductAttributes:
    raw_title: str
    brand_owner: BrandOwner
    tier: ParsedTier
    product_type: str | None
    exclusion_flags: tuple[str, ...]


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


def parse_product_attributes(
    product_name: str,
    retailer: str | None = None,
    category: str | None = None,
) -> ParsedProductAttributes:
    """Parse group-matching attributes from a retailer product title."""

    text = _normalise_text(product_name)
    brand_owner = parse_brand_owner(product_name, retailer)
    tier = parse_tier(product_name, retailer)
    product_type = parse_product_type(product_name, category)
    exclusions = set(parse_exclusion_flags(product_name))
    if brand_owner == "national_brand":
        exclusions.add("branded")
    if tier == "retailer_value":
        exclusions.add("value_tier")
    if tier == "retailer_premium":
        exclusions.add("premium_tier")
    if tier == "retailer_organic":
        exclusions.add("organic")
    if any(signal in text for signal in FREE_FROM_SIGNALS):
        exclusions.add("specialist_dietary")

    return ParsedProductAttributes(
        raw_title=product_name,
        brand_owner=brand_owner,
        tier=tier,
        product_type=product_type,
        exclusion_flags=tuple(sorted(exclusions)),
    )


def parse_brand_owner(product_name: str, retailer: str | None = None) -> BrandOwner:
    text = _normalise_text(product_name)
    flags = classify_product_flags(product_name, retailer)
    if flags.is_own_brand:
        return "retailer_own_label"
    if any(text == signal or text.startswith(f"{signal} ") for signal in NATIONAL_BRAND_SIGNALS):
        return "national_brand"
    return "unknown"


def parse_tier(product_name: str, retailer: str | None = None) -> ParsedTier:
    flags = classify_product_flags(product_name, retailer)
    brand_owner = parse_brand_owner(product_name, retailer)
    text = _normalise_text(product_name)

    if any(signal in text for signal in FREE_FROM_SIGNALS):
        return "specialist_dietary"
    if brand_owner == "national_brand":
        return "national_brand_premium" if flags.is_premium else "national_brand_standard"
    if flags.is_organic:
        return "retailer_organic"
    if flags.is_value_range:
        return "retailer_value"
    if flags.is_premium:
        return "retailer_premium"
    if brand_owner == "retailer_own_label":
        return "retailer_standard"
    return "unknown"


def parse_product_type(product_name: str, category: str | None = None) -> str | None:
    text = _normalise_text(f"{product_name} {category or ''}")
    for product_type, signals in PRODUCT_TYPE_SIGNALS:
        if any(signal in text for signal in signals):
            return product_type
    return None


def parse_exclusion_flags(product_name: str) -> tuple[str, ...]:
    text = _normalise_text(product_name)
    flags = {
        flag
        for flag, signals in EXCLUSION_SIGNALS
        if any(signal in text for signal in signals)
    }
    if "gluten_free" in flags:
        flags.add("free_from")
    return tuple(sorted(flags))


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
