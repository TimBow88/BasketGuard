from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence

from .group_comparison import (
    DEFAULT_MIN_AUTO_MATCH_CONFIDENCE,
    Connection,
    GroupComparisonReport,
    fetch_group_comparison,
)


@dataclass(frozen=True)
class RetailerGap:
    group_slug: str
    cheapest_retailer: str | None
    cheapest_retailer_slug: str | None
    cheapest_unit_price: Decimal | None
    most_expensive_retailer: str | None
    most_expensive_retailer_slug: str | None
    most_expensive_unit_price: Decimal | None
    unit_price_basis: str | None
    absolute_unit_price_gap: Decimal | None
    percentage_unit_price_gap: Decimal | None
    retailer_count: int
    missing_retailer_count: int
    missing_retailers: tuple[str, ...]
    as_of: str | None


@dataclass(frozen=True)
class RetailerGapReport:
    gaps: tuple[RetailerGap, ...]

    @property
    def widest_gap_first(self) -> tuple[RetailerGap, ...]:
        # Groups with no computable gap sort last.
        return tuple(
            sorted(
                self.gaps,
                key=lambda gap: (
                    gap.percentage_unit_price_gap is not None,
                    gap.percentage_unit_price_gap or Decimal("0"),
                ),
                reverse=True,
            )
        )


def fetch_retailer_gaps(
    connection: Connection,
    group_slugs: Sequence[str],
    min_auto_match_confidence: Decimal = DEFAULT_MIN_AUTO_MATCH_CONFIDENCE,
) -> RetailerGapReport:
    """Report the unit-price gap between the cheapest and dearest retailer per group.

    Each group's eligible observations come from ``fetch_group_comparison`` (the
    latest eligible observation per retailer), so the shared group join and
    membership eligibility rules apply and needs-review or rejected products
    never appear. The "missing retailer" set for a group is the retailers seen
    elsewhere in this report but absent from that group's comparison.
    """

    comparisons: dict[str, GroupComparisonReport] = {
        slug: fetch_group_comparison(connection, slug, min_auto_match_confidence)
        for slug in group_slugs
    }

    tracked_retailers: set[str] = set()
    for report in comparisons.values():
        for entry in report.entries:
            tracked_retailers.add(entry.retailer_slug)

    gaps = tuple(
        _gap_for_group(slug, comparisons[slug], tracked_retailers) for slug in group_slugs
    )
    return RetailerGapReport(gaps=gaps)


def _gap_for_group(
    slug: str,
    report: GroupComparisonReport,
    tracked_retailers: set[str],
) -> RetailerGap:
    entries = report.entries
    present = {entry.retailer_slug for entry in entries}
    missing_retailers = tuple(sorted(tracked_retailers - present))

    cheapest = report.cheapest
    dearest = report.most_expensive
    absolute_gap = report.unit_price_gap
    percentage_gap = None
    if (
        absolute_gap is not None
        and cheapest is not None
        and cheapest.unit_price > 0
    ):
        percentage_gap = (
            absolute_gap / cheapest.unit_price * Decimal("100")
        ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    as_of = max((entry.collected_at for entry in entries), default=None)

    return RetailerGap(
        group_slug=slug,
        cheapest_retailer=cheapest.retailer_name if cheapest else None,
        cheapest_retailer_slug=cheapest.retailer_slug if cheapest else None,
        cheapest_unit_price=cheapest.unit_price if cheapest else None,
        most_expensive_retailer=dearest.retailer_name if dearest else None,
        most_expensive_retailer_slug=dearest.retailer_slug if dearest else None,
        most_expensive_unit_price=dearest.unit_price if dearest else None,
        unit_price_basis=cheapest.unit_price_basis if cheapest else None,
        absolute_unit_price_gap=absolute_gap,
        percentage_unit_price_gap=percentage_gap,
        retailer_count=len(entries),
        missing_retailer_count=len(missing_retailers),
        missing_retailers=missing_retailers,
        as_of=as_of,
    )
