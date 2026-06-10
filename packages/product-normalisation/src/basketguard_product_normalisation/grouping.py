from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal


SUPPORTED_DEFINITION_VERSION = 1

ALLOWED_STATUSES = {"active", "draft", "blocked"}
ALLOWED_RISK_LEVELS = {"low", "medium", "high"}
ALLOWED_BRAND_OWNERS = {
    "retailer_own_label",
    "national_brand",
    "licensed_brand",
    "unknown",
}
ALLOWED_TIERS = {
    "retailer_value",
    "retailer_standard",
    "retailer_premium",
    "retailer_organic",
    "specialist_dietary",
    "national_brand_standard",
    "national_brand_premium",
    "unknown",
}
ALLOWED_UNIT_BASES = {
    "kg",
    "litre",
    "count",
    "each",
    "item",
    "biscuit",
    "egg",
    "roll",
    "sheet",
    "wash",
    "tablet",
    "nappy",
}
ALLOWED_REVIEW_TRIGGERS = {
    "category_missing",
    "unit_price_missing",
    "tier_unknown",
    "size_out_of_range",
}

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")

MatchOutcome = Literal["auto_match", "needs_review", "no_match"]


class EquivalenceGroupDefinitionError(ValueError):
    pass


@dataclass(frozen=True)
class GroupSizeRange:
    min_value: Decimal
    max_value: Decimal

    def contains(self, value: Decimal) -> bool:
        return self.min_value <= value <= self.max_value


@dataclass(frozen=True)
class EquivalenceGroupDefinition:
    slug: str
    name: str
    status: str
    risk_level: str
    unit_basis: str
    brand_owner: str
    tier: str
    title_contains_any: tuple[str, ...]
    category_contains_any: tuple[str, ...]
    size_range: GroupSizeRange
    exclude_terms: tuple[str, ...]
    review_triggers: tuple[str, ...]
    auto_match_threshold: Decimal
    review_threshold: Decimal


@dataclass(frozen=True)
class GroupMatchCandidate:
    """Parsed product attributes needed to score one group membership."""

    title: str
    category: str | None
    brand_owner: str
    tier: str | None
    normalised_size_value: Decimal | None
    normalised_size_unit: str | None


@dataclass(frozen=True)
class GroupMatchResult:
    outcome: MatchOutcome
    score: Decimal
    reasons: tuple[str, ...]
    exclusion_hits: tuple[str, ...]


def load_equivalence_group_definitions(path: str | Path) -> tuple[EquivalenceGroupDefinition, ...]:
    """Load and validate JSON equivalence group definitions."""

    raw_text = Path(path).read_text(encoding="utf-8")
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise EquivalenceGroupDefinitionError(f"Invalid JSON in {path}: {error}") from error

    if not isinstance(payload, dict):
        raise EquivalenceGroupDefinitionError("Definition file must contain a JSON object")
    if payload.get("version") != SUPPORTED_DEFINITION_VERSION:
        raise EquivalenceGroupDefinitionError(
            f"Unsupported definition version: {payload.get('version')!r}"
        )
    groups = payload.get("groups")
    if not isinstance(groups, list) or not groups:
        raise EquivalenceGroupDefinitionError("Definition file must contain a non-empty 'groups' list")

    definitions = tuple(_parse_group(index, group) for index, group in enumerate(groups))
    slugs = [definition.slug for definition in definitions]
    duplicates = {slug for slug in slugs if slugs.count(slug) > 1}
    if duplicates:
        raise EquivalenceGroupDefinitionError(f"Duplicate group slugs: {sorted(duplicates)}")
    return definitions


def match_equivalence_group(
    candidate: GroupMatchCandidate,
    definition: EquivalenceGroupDefinition,
) -> GroupMatchResult:
    """Deterministically score one candidate against one group definition.

    Hard exclusions (exclude terms, wrong product type, wrong brand owner,
    conflicting tier, wrong unit basis) return no_match regardless of score.
    Review triggers cap the outcome at needs_review.
    """

    title = _normalise_text(candidate.title)
    category = _normalise_text(candidate.category or "")
    reasons: list[str] = []

    exclusion_hits = tuple(term for term in definition.exclude_terms if term in title)
    if exclusion_hits:
        return GroupMatchResult(
            outcome="no_match",
            score=Decimal("0"),
            reasons=(f"excluded_terms:{','.join(exclusion_hits)}",),
            exclusion_hits=exclusion_hits,
        )

    title_supported = any(term in title for term in definition.title_contains_any)
    if not title_supported:
        return GroupMatchResult(
            outcome="no_match",
            score=Decimal("0"),
            reasons=("product_type_mismatch",),
            exclusion_hits=(),
        )

    if candidate.brand_owner != definition.brand_owner:
        return GroupMatchResult(
            outcome="no_match",
            score=Decimal("0"),
            reasons=(f"brand_owner_mismatch:{candidate.brand_owner}",),
            exclusion_hits=(),
        )

    if candidate.tier is not None and candidate.tier != definition.tier:
        return GroupMatchResult(
            outcome="no_match",
            score=Decimal("0"),
            reasons=(f"tier_mismatch:{candidate.tier}",),
            exclusion_hits=(),
        )

    if (
        candidate.normalised_size_unit is not None
        and candidate.normalised_size_unit != definition.unit_basis
    ):
        return GroupMatchResult(
            outcome="no_match",
            score=Decimal("0"),
            reasons=(f"unit_basis_mismatch:{candidate.normalised_size_unit}",),
            exclusion_hits=(),
        )

    score = Decimal("0")
    review_capped = False

    score += Decimal("0.25")
    reasons.append("product_type_supported")

    category_supported = bool(category) and any(
        term in category for term in definition.category_contains_any
    )
    if category_supported:
        score += Decimal("0.15")
        reasons.append("category_supported")
    elif not category and "category_missing" in definition.review_triggers:
        review_capped = True
        reasons.append("review:category_missing")

    score += Decimal("0.15")
    reasons.append("brand_owner_match")

    if candidate.tier == definition.tier:
        score += Decimal("0.15")
        reasons.append("tier_match")
    elif "tier_unknown" in definition.review_triggers:
        review_capped = True
        reasons.append("review:tier_unknown")

    # Form/state parsing is not yet defined for the current low-risk groups.
    score += Decimal("0.10")
    reasons.append("form_state_not_required")

    if candidate.normalised_size_unit == definition.unit_basis:
        score += Decimal("0.10")
        reasons.append("unit_basis_valid")

    if (
        candidate.normalised_size_value is not None
        and definition.size_range.contains(candidate.normalised_size_value)
    ):
        score += Decimal("0.05")
        reasons.append("size_in_range")
    else:
        review_capped = True
        reasons.append("review:size_out_of_range")

    score += Decimal("0.05")
    reasons.append("no_exclusion_flags")

    if score >= definition.auto_match_threshold and not review_capped:
        outcome: MatchOutcome = "auto_match"
    elif score >= definition.review_threshold:
        outcome = "needs_review"
    else:
        outcome = "no_match"

    return GroupMatchResult(
        outcome=outcome,
        score=score,
        reasons=tuple(reasons),
        exclusion_hits=(),
    )


def _parse_group(index: int, raw: Any) -> EquivalenceGroupDefinition:
    if not isinstance(raw, dict):
        raise EquivalenceGroupDefinitionError(f"Group at index {index} must be an object")

    slug = _required_str(raw, "slug", index)
    if not SLUG_PATTERN.match(slug):
        raise EquivalenceGroupDefinitionError(f"Invalid slug format: {slug!r}")

    status = _required_str(raw, "status", index)
    if status not in ALLOWED_STATUSES:
        raise EquivalenceGroupDefinitionError(f"{slug}: invalid status {status!r}")

    risk_level = _required_str(raw, "risk_level", index)
    if risk_level not in ALLOWED_RISK_LEVELS:
        raise EquivalenceGroupDefinitionError(f"{slug}: invalid risk_level {risk_level!r}")

    unit_basis = _required_str(raw, "unit_basis", index)
    if unit_basis not in ALLOWED_UNIT_BASES:
        raise EquivalenceGroupDefinitionError(f"{slug}: invalid unit_basis {unit_basis!r}")

    brand_owner = _required_str(raw, "brand_owner", index)
    if brand_owner not in ALLOWED_BRAND_OWNERS:
        raise EquivalenceGroupDefinitionError(f"{slug}: invalid brand_owner {brand_owner!r}")

    tier = _required_str(raw, "tier", index)
    if tier not in ALLOWED_TIERS:
        raise EquivalenceGroupDefinitionError(f"{slug}: invalid tier {tier!r}")

    required = raw.get("required")
    if not isinstance(required, dict):
        raise EquivalenceGroupDefinitionError(f"{slug}: 'required' must be an object")
    title_terms = _term_tuple(required.get("title_contains_any"), f"{slug}: required.title_contains_any")
    category_terms = _term_tuple(
        required.get("category_contains_any"),
        f"{slug}: required.category_contains_any",
    )

    size_range_raw = raw.get("size_range")
    if not isinstance(size_range_raw, dict):
        raise EquivalenceGroupDefinitionError(f"{slug}: 'size_range' must be an object")
    size_range = GroupSizeRange(
        min_value=_decimal(size_range_raw.get("min"), f"{slug}: size_range.min"),
        max_value=_decimal(size_range_raw.get("max"), f"{slug}: size_range.max"),
    )
    if size_range.min_value >= size_range.max_value:
        raise EquivalenceGroupDefinitionError(f"{slug}: size_range.min must be below size_range.max")

    exclude_terms = _term_tuple(raw.get("exclude_terms"), f"{slug}: exclude_terms")
    review_triggers = _term_tuple(raw.get("review_triggers"), f"{slug}: review_triggers")
    unknown_triggers = set(review_triggers) - ALLOWED_REVIEW_TRIGGERS
    if unknown_triggers:
        raise EquivalenceGroupDefinitionError(
            f"{slug}: unknown review_triggers {sorted(unknown_triggers)}"
        )

    auto_match_threshold = _decimal(raw.get("auto_match_threshold"), f"{slug}: auto_match_threshold")
    review_threshold = _decimal(raw.get("review_threshold"), f"{slug}: review_threshold")
    for label, threshold in (
        ("auto_match_threshold", auto_match_threshold),
        ("review_threshold", review_threshold),
    ):
        if not Decimal("0") < threshold <= Decimal("1"):
            raise EquivalenceGroupDefinitionError(f"{slug}: {label} must be within (0, 1]")
    if review_threshold >= auto_match_threshold:
        raise EquivalenceGroupDefinitionError(
            f"{slug}: review_threshold must be below auto_match_threshold"
        )

    return EquivalenceGroupDefinition(
        slug=slug,
        name=_required_str(raw, "name", index),
        status=status,
        risk_level=risk_level,
        unit_basis=unit_basis,
        brand_owner=brand_owner,
        tier=tier,
        title_contains_any=title_terms,
        category_contains_any=category_terms,
        size_range=size_range,
        exclude_terms=exclude_terms,
        review_triggers=review_triggers,
        auto_match_threshold=auto_match_threshold,
        review_threshold=review_threshold,
    )


def _required_str(raw: dict[str, Any], key: str, index: int) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EquivalenceGroupDefinitionError(
            f"Group at index {index} is missing required string field {key!r}"
        )
    return value.strip()


def _term_tuple(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise EquivalenceGroupDefinitionError(f"{label} must be a non-empty list")
    terms = []
    for term in value:
        if not isinstance(term, str) or not term.strip():
            raise EquivalenceGroupDefinitionError(f"{label} entries must be non-empty strings")
        terms.append(_normalise_text(term))
    return tuple(terms)


def _decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise EquivalenceGroupDefinitionError(f"{label} must be a number")
    try:
        return Decimal(str(value))
    except ArithmeticError as error:
        raise EquivalenceGroupDefinitionError(f"{label} is not a valid number") from error


def _normalise_text(value: str) -> str:
    return " ".join(value.lower().replace("&", " and ").split())
