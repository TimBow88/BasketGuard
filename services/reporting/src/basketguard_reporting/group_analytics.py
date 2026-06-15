from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence

from .group_comparison import (
    DEFAULT_MIN_AUTO_MATCH_CONFIDENCE,
    Connection,
)
from .group_gaps import RetailerGap, fetch_retailer_gaps
from .group_movement import (
    PRICE_MOVEMENT_WINDOWS,
    GroupPriceMovementReport,
    PriceMovementWindow,
    RetailerPriceMovement,
    fetch_group_price_movement,
)


YOY_MOVEMENT_WINDOW_DAYS = 365
PRICE_ANALYTICS_WINDOWS = (*PRICE_MOVEMENT_WINDOWS, YOY_MOVEMENT_WINDOW_DAYS)


@dataclass(frozen=True)
class RetailerPriceAnalytics:
    retailer_name: str
    retailer_slug: str
    movement_windows: tuple[PriceMovementWindow, ...]
    year_over_year: PriceMovementWindow | None


@dataclass(frozen=True)
class GroupPriceAnalyticsReport:
    group_slug: str
    retailers: tuple[RetailerPriceAnalytics, ...]
    retailer_gap: RetailerGap


@dataclass(frozen=True)
class BasketRetailerMovementWindow:
    window_days: int
    earliest_total_unit_price: Decimal | None
    latest_total_unit_price: Decimal | None
    absolute_total_unit_price_change: Decimal | None
    percentage_total_unit_price_change: Decimal | None
    present_group_count: int
    missing_group_count: int
    missing_group_slugs: tuple[str, ...]


@dataclass(frozen=True)
class BasketRetailerMovement:
    retailer_name: str
    retailer_slug: str
    windows: tuple[BasketRetailerMovementWindow, ...]


@dataclass(frozen=True)
class BasketPriceMovementReport:
    basket_slug: str
    group_slugs: tuple[str, ...]
    retailers: tuple[BasketRetailerMovement, ...]

    @property
    def retailer_count(self) -> int:
        return len(self.retailers)


def fetch_group_price_analytics(
    connection: Connection,
    group_slug: str,
    min_auto_match_confidence: Decimal = DEFAULT_MIN_AUTO_MATCH_CONFIDENCE,
) -> GroupPriceAnalyticsReport:
    """Return movement, YoY and retailer-gap analytics for one group.

    The underlying observations come from query-based reports that reuse the
    shared group join and membership eligibility predicate, so needs-review and
    rejected products never appear.
    """

    movement_report = fetch_group_price_movement(
        connection,
        group_slug,
        windows=PRICE_ANALYTICS_WINDOWS,
        min_auto_match_confidence=min_auto_match_confidence,
    )
    gap_report = fetch_retailer_gaps(
        connection,
        [group_slug],
        min_auto_match_confidence=min_auto_match_confidence,
    )

    retailers = tuple(_retailer_analytics(retailer) for retailer in movement_report.retailers)
    return GroupPriceAnalyticsReport(
        group_slug=group_slug,
        retailers=retailers,
        retailer_gap=gap_report.gaps[0],
    )


def fetch_basket_price_movement(
    connection: Connection,
    basket_slug: str,
    group_slugs: Sequence[str],
    windows: tuple[int, ...] = PRICE_MOVEMENT_WINDOWS,
    min_auto_match_confidence: Decimal = DEFAULT_MIN_AUTO_MATCH_CONFIDENCE,
) -> BasketPriceMovementReport:
    """Return basket-level price movement by summing group unit prices.

    A basket is a supplied fixed list of equivalence group slugs. For each
    retailer and window, groups with no eligible earliest/latest observation are
    reported as missing instead of being silently treated as zero.
    """

    if not group_slugs:
        raise ValueError("group_slugs must contain at least one group")

    movement_reports = tuple(
        fetch_group_price_movement(
            connection,
            group_slug,
            windows=windows,
            min_auto_match_confidence=min_auto_match_confidence,
        )
        for group_slug in group_slugs
    )
    retailers = _basket_retailers(tuple(group_slugs), tuple(sorted(dict.fromkeys(windows))), movement_reports)
    return BasketPriceMovementReport(
        basket_slug=basket_slug,
        group_slugs=tuple(group_slugs),
        retailers=retailers,
    )


def _retailer_analytics(retailer: RetailerPriceMovement) -> RetailerPriceAnalytics:
    yoy = next(
        (
            window
            for window in retailer.windows
            if window.window_days == YOY_MOVEMENT_WINDOW_DAYS and window.observation_count >= 2
        ),
        None,
    )
    movement_windows = tuple(
        window
        for window in retailer.windows
        if window.window_days in PRICE_MOVEMENT_WINDOWS
    )
    return RetailerPriceAnalytics(
        retailer_name=retailer.retailer_name,
        retailer_slug=retailer.retailer_slug,
        movement_windows=movement_windows,
        year_over_year=yoy,
    )


def _basket_retailers(
    group_slugs: tuple[str, ...],
    windows: tuple[int, ...],
    movement_reports: tuple[GroupPriceMovementReport, ...],
) -> tuple[BasketRetailerMovement, ...]:
    retailer_names: dict[str, str] = {}
    group_windows: dict[tuple[str, str, int], PriceMovementWindow] = {}

    for group_slug, report in zip(group_slugs, movement_reports):
        for retailer in report.retailers:
            retailer_names.setdefault(retailer.retailer_slug, retailer.retailer_name)
            for window in retailer.windows:
                group_windows[(group_slug, retailer.retailer_slug, window.window_days)] = window

    return tuple(
        BasketRetailerMovement(
            retailer_name=retailer_names[retailer_slug],
            retailer_slug=retailer_slug,
            windows=tuple(
                _basket_window(group_slugs, retailer_slug, window, group_windows)
                for window in windows
            ),
        )
        for retailer_slug in sorted(retailer_names)
    )


def _basket_window(
    group_slugs: tuple[str, ...],
    retailer_slug: str,
    window_days: int,
    group_windows: dict[tuple[str, str, int], PriceMovementWindow],
) -> BasketRetailerMovementWindow:
    earliest_total = Decimal("0.00")
    latest_total = Decimal("0.00")
    missing: list[str] = []

    for group_slug in group_slugs:
        window = group_windows.get((group_slug, retailer_slug, window_days))
        if window is None or window.earliest is None or window.latest is None:
            missing.append(group_slug)
            continue
        earliest_total += window.earliest.unit_price
        latest_total += window.latest.unit_price

    present_count = len(group_slugs) - len(missing)
    if present_count == 0:
        return BasketRetailerMovementWindow(
            window_days=window_days,
            earliest_total_unit_price=None,
            latest_total_unit_price=None,
            absolute_total_unit_price_change=None,
            percentage_total_unit_price_change=None,
            present_group_count=0,
            missing_group_count=len(missing),
            missing_group_slugs=tuple(missing),
        )

    absolute_change = latest_total - earliest_total
    percentage_change = None
    if earliest_total > 0:
        percentage_change = (
            absolute_change / earliest_total * Decimal("100")
        ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    return BasketRetailerMovementWindow(
        window_days=window_days,
        earliest_total_unit_price=earliest_total,
        latest_total_unit_price=latest_total,
        absolute_total_unit_price_change=absolute_change,
        percentage_total_unit_price_change=percentage_change,
        present_group_count=present_count,
        missing_group_count=len(missing),
        missing_group_slugs=tuple(missing),
    )
