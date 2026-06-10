from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .group_comparison import (
    DEFAULT_MIN_AUTO_MATCH_CONFIDENCE,
    GROUP_OBSERVATION_JOIN,
    MEMBERSHIP_ELIGIBILITY_CLAUSE,
    Connection,
)


DEFAULT_HISTORY_WINDOW_DAYS = 90

# Reuses the shared join path and membership eligibility rules from the group
# comparison report, then adds a rolling day-window filter and returns every
# eligible observation ordered oldest-first per retailer. Binds three
# parameters in this order: group slug, minimum auto-match confidence, window.
GROUP_HISTORY_SQL = f"""
SELECT
    retailers.name,
    retailers.slug,
    products.canonical_name,
    price_observations.shelf_price,
    price_observations.effective_price,
    price_observations.unit_price,
    price_observations.unit_price_basis,
    price_observations.availability,
    price_observations.collected_at,
    price_observations.raw_snapshot_id,
    product_group_memberships.match_confidence,
    product_group_memberships.human_reviewed
{GROUP_OBSERVATION_JOIN}
WHERE equivalence_groups.slug = %s
  AND {MEMBERSHIP_ELIGIBILITY_CLAUSE}
  AND price_observations.collected_at >= now() - make_interval(days => %s)
ORDER BY retailers.slug, price_observations.collected_at ASC
"""


@dataclass(frozen=True)
class PriceHistoryPoint:
    shelf_price: Decimal | None
    effective_price: Decimal
    unit_price: Decimal
    unit_price_basis: str | None
    availability: str
    collected_at: str
    raw_snapshot_id: str | None
    match_confidence: Decimal
    human_reviewed: bool


@dataclass(frozen=True)
class RetailerPriceHistory:
    retailer_name: str
    retailer_slug: str
    product_title: str
    points: tuple[PriceHistoryPoint, ...]

    @property
    def first(self) -> PriceHistoryPoint | None:
        return self.points[0] if self.points else None

    @property
    def latest(self) -> PriceHistoryPoint | None:
        return self.points[-1] if self.points else None

    @property
    def unit_price_change(self) -> Decimal | None:
        if len(self.points) < 2:
            return None
        return self.points[-1].unit_price - self.points[0].unit_price


@dataclass(frozen=True)
class GroupPriceHistoryReport:
    group_slug: str
    window_days: int
    retailers: tuple[RetailerPriceHistory, ...]

    @property
    def retailer_count(self) -> int:
        return len(self.retailers)

    @property
    def observation_count(self) -> int:
        return sum(len(history.points) for history in self.retailers)


def fetch_group_price_history(
    connection: Connection,
    group_slug: str,
    window_days: int = DEFAULT_HISTORY_WINDOW_DAYS,
    min_auto_match_confidence: Decimal = DEFAULT_MIN_AUTO_MATCH_CONFIDENCE,
) -> GroupPriceHistoryReport:
    """Return eligible price observations per retailer over a rolling window.

    Eligibility matches the group comparison report: only human-approved or
    auto-matched (>= confidence floor) memberships contribute, so needs-review
    and rejected products never appear. Observations within the last
    ``window_days`` are grouped per retailer and ordered oldest-first, each
    carrying its raw snapshot ID for audit.
    """

    if window_days <= 0:
        raise ValueError("window_days must be a positive integer")

    cursor = connection.cursor()
    try:
        cursor.execute(
            GROUP_HISTORY_SQL,
            (group_slug, min_auto_match_confidence, window_days),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()

    grouped: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for row in rows:
        (
            retailer_name,
            retailer_slug,
            product_title,
            shelf_price,
            effective_price,
            unit_price,
            unit_price_basis,
            availability,
            collected_at,
            raw_snapshot_id,
            match_confidence,
            human_reviewed,
        ) = row
        slug = str(retailer_slug)
        bucket = grouped.setdefault(
            slug,
            {"retailer_name": str(retailer_name), "product_title": str(product_title), "points": []},
        )
        # Rows arrive oldest-first; keep the latest observed title for the retailer.
        bucket["product_title"] = str(product_title)
        bucket["points"].append(
            PriceHistoryPoint(
                shelf_price=_optional_decimal(shelf_price),
                effective_price=_decimal(effective_price),
                unit_price=_decimal(unit_price),
                unit_price_basis=str(unit_price_basis) if unit_price_basis is not None else None,
                availability=str(availability),
                collected_at=str(collected_at),
                raw_snapshot_id=str(raw_snapshot_id) if raw_snapshot_id is not None else None,
                match_confidence=_decimal(match_confidence),
                human_reviewed=bool(human_reviewed),
            ),
        )

    histories = tuple(
        RetailerPriceHistory(
            retailer_name=bucket["retailer_name"],
            retailer_slug=slug,
            product_title=bucket["product_title"],
            points=tuple(bucket["points"]),
        )
        for slug, bucket in grouped.items()
    )
    return GroupPriceHistoryReport(
        group_slug=group_slug,
        window_days=window_days,
        retailers=histories,
    )


def _decimal(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _optional_decimal(value: Any) -> Decimal | None:
    return None if value is None else _decimal(value)
