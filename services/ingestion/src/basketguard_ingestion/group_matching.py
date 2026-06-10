from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from basketguard_product_normalisation import (
    EquivalenceGroupDefinition,
    GroupMatchCandidate,
    GroupMatchResult,
    match_equivalence_group,
)

from .contracts import ParsedProduct


@dataclass(frozen=True)
class ProductGroupMatch:
    product: ParsedProduct
    group_slug: str
    result: GroupMatchResult


@dataclass(frozen=True)
class GroupMatchingSummary:
    auto_matches: tuple[ProductGroupMatch, ...]
    review_candidates: tuple[ProductGroupMatch, ...]


def candidate_from_parsed_product(product: ParsedProduct) -> GroupMatchCandidate:
    # Brand owner stays "unknown" for non-own-brand products so own-label group
    # definitions hard-reject them instead of guessing national_brand.
    return GroupMatchCandidate(
        title=product.canonical_name,
        category=product.subcategory or product.category,
        brand_owner="retailer_own_label" if product.is_own_brand else "unknown",
        tier=product.tier,
        normalised_size_value=product.normalised_size_value,
        normalised_size_unit=product.normalised_size_unit,
    )


def match_parsed_products(
    products: Iterable[ParsedProduct],
    definitions: Sequence[EquivalenceGroupDefinition],
) -> GroupMatchingSummary:
    """Score parsed products against active group definitions."""

    auto_matches: list[ProductGroupMatch] = []
    review_candidates: list[ProductGroupMatch] = []
    for product in products:
        candidate = candidate_from_parsed_product(product)
        for definition in definitions:
            if definition.status != "active":
                continue
            result = match_equivalence_group(candidate, definition)
            if result.outcome == "auto_match":
                auto_matches.append(ProductGroupMatch(product, definition.slug, result))
            elif result.outcome == "needs_review":
                review_candidates.append(ProductGroupMatch(product, definition.slug, result))
    return GroupMatchingSummary(
        auto_matches=tuple(auto_matches),
        review_candidates=tuple(review_candidates),
    )
