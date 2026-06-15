from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .group_comparison import (
    DEFAULT_MIN_AUTO_MATCH_CONFIDENCE,
    GROUP_OBSERVATION_JOIN,
    MEMBERSHIP_ELIGIBILITY_CLAUSE,
    Connection,
)


PRICE_MOVEMENT_WINDOWS = (7, 30, 90)

# The query stays on the shared eligible group-observation path and binds three
# parameters in this order: group slug, minimum auto-match confidence, window.
GROUP_PRICE_MOVEMENT_SQL = f"""
SELECT
    retailers.name,
    retailers.slug,
    products.canonical_name,
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
class PriceMovementObservation:
    product_title: str
    unit_price: Decimal
    unit_price_basis: str | None
    availability: str
    collected_at: str
    raw_snapshot_id: str | None
    match_confidence: Decimal
    human_reviewed: bool


@dataclass(frozen=True)
class PriceMovementWindow:
    window_days: int
    earliest: PriceMovementObservation | None
    latest: PriceMovementObservation | None
    absolute_unit_price_change: Decimal | None
    percentage_unit_price_change: Decimal | None
    observation_count: int


@dataclass(frozen=True)
class RetailerPriceMovement:
    retailer_name: str
    retailer_slug: str
    windows: tuple[PriceMovementWindow, ...]


@dataclass(frozen=True)
class GroupPriceMovementReport:
    group_slug: str
    retailers: tuple[RetailerPriceMovement, ...]

    @property
    def retailer_count(self) -> int:
        return len(self.retailers)


def fetch_group_price_movement(
    connection: Connection,
    group_slug: str,
    windows: tuple[int, ...] = PRICE_MOVEMENT_WINDOWS,
    min_auto_match_confidence: Decimal = DEFAULT_MIN_AUTO_MATCH_CONFIDENCE,
) -> GroupPriceMovementReport:
    """Return per-retailer unit-price movement over the requested windows.

    Observations come from the shared group join and membership eligibility
    predicate, so needs-review and rejected products never appear. Each window
    uses PostgreSQL's current time for its cutoff, then each retailer gets
    earliest/latest observations and absolute/percentage unit-price movement.
    """

    if not windows:
        raise ValueError("windows must contain at least one day window")
    if any(window <= 0 for window in windows):
        raise ValueError("windows must contain positive integers")

    grouped: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    ordered_windows = tuple(sorted(dict.fromkeys(windows)))

    for window in ordered_windows:
        cursor = connection.cursor()
        try:
            cursor.execute(
                GROUP_PRICE_MOVEMENT_SQL,
                (group_slug, min_auto_match_confidence, window),
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()

        for row in rows:
            (
                retailer_name,
                retailer_slug,
                product_title,
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
                {"retailer_name": str(retailer_name), "windows": {}},
            )
            bucket["windows"].setdefault(window, []).append(
                PriceMovementObservation(
                    product_title=str(product_title),
                    unit_price=_decimal(unit_price),
                    unit_price_basis=str(unit_price_basis) if unit_price_basis is not None else None,
                    availability=str(availability),
                    collected_at=str(collected_at),
                    raw_snapshot_id=str(raw_snapshot_id) if raw_snapshot_id is not None else None,
                    match_confidence=_decimal(match_confidence),
                    human_reviewed=bool(human_reviewed),
                ),
            )

    retailers = tuple(
        RetailerPriceMovement(
            retailer_name=bucket["retailer_name"],
            retailer_slug=slug,
            windows=tuple(
                _movement_window(window, bucket["windows"].get(window, []))
                for window in ordered_windows
            ),
        )
        for slug, bucket in grouped.items()
    )
    return GroupPriceMovementReport(group_slug=group_slug, retailers=retailers)


def _movement_window(
    window: int,
    observations: list[PriceMovementObservation],
) -> PriceMovementWindow:
    if not observations:
        return PriceMovementWindow(
            window_days=window,
            earliest=None,
            latest=None,
            absolute_unit_price_change=None,
            percentage_unit_price_change=None,
            observation_count=0,
        )

    earliest = observations[0]
    latest = observations[-1]
    absolute_change = latest.unit_price - earliest.unit_price
    percentage_change = None
    if earliest.unit_price > 0:
        percentage_change = (
            absolute_change / earliest.unit_price * Decimal("100")
        ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    return PriceMovementWindow(
        window_days=window,
        earliest=earliest,
        latest=latest,
        absolute_unit_price_change=absolute_change,
        percentage_unit_price_change=percentage_change,
        observation_count=len(observations),
    )


def _decimal(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))
