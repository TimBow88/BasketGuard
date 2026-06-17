"""Postcode-context helpers for location-aware collection and comparison.

UK grocery prices and availability vary by store / delivery postcode. The schema
already carries ``postcode_context`` on snapshots and observations; this module
gives that field meaning:

* ``normalise_postcode_context`` — canonicalise a value so the same location
  compares equal regardless of spacing/case (real UK postcodes are formatted;
  descriptive labels are just trimmed);
* ``assert_consistent_postcode`` — guard a comparison so prices from different
  postcodes are never silently treated as equivalent.

See ``docs/backend/12_POSTCODE_STRATEGY.md`` for the MVP single-postcode policy.
"""

from __future__ import annotations

import re
from typing import Iterable


# MVP collects against one fixed location so cross-retailer comparisons are
# like-for-like; multi-postcode collection is a later expansion.
MVP_DEFAULT_POSTCODE_CONTEXT = "MVP default region"

# Loose UK postcode shape: area+district, then sector+unit.
_UK_POSTCODE = re.compile(r"^([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})$", re.IGNORECASE)


class PostcodeConsistencyError(RuntimeError):
    pass


def is_uk_postcode(value: str) -> bool:
    return bool(_UK_POSTCODE.match(value.strip()))


def normalise_postcode_context(value: str | None) -> str | None:
    """Canonicalise a postcode context; ``None``/blank stays ``None``.

    Real UK postcodes are upper-cased and given a single internal space
    (``ec1a1bb`` -> ``EC1A 1BB``). Other context labels are whitespace-trimmed
    and collapsed but otherwise preserved.
    """

    if value is None:
        return None
    collapsed = " ".join(value.split())
    if not collapsed:
        return None
    match = _UK_POSTCODE.match(collapsed)
    if match:
        return f"{match.group(1).upper()} {match.group(2).upper()}"
    return collapsed


def assert_consistent_postcode(contexts: Iterable[str | None]) -> str | None:
    """Return the single shared postcode context, or raise if they differ.

    ``None`` contexts are ignored (unknown location). If two or more distinct
    known contexts are present the values are not comparable like-for-like, so
    this raises ``PostcodeConsistencyError``.
    """

    distinct = {
        normalised
        for normalised in (normalise_postcode_context(context) for context in contexts)
        if normalised is not None
    }
    if len(distinct) > 1:
        raise PostcodeConsistencyError(
            "Cannot compare prices across different postcode contexts: "
            f"{sorted(distinct)}."
        )
    return next(iter(distinct), None)
