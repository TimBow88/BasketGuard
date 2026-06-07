from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from statistics import median
from typing import Iterable, Mapping


class AnalyticsError(ValueError):
    pass


def yoy_increase(current_unit_price: Decimal | float | int | str, previous_unit_price: Decimal | float | int | str) -> Decimal:
    """Return relative YoY increase, e.g. 0.55 for +55%."""

    return _relative_change(current_unit_price, previous_unit_price)


def competitor_median_yoy(
    yoy_by_retailer: Mapping[str, Decimal | float | int | str],
    retailer: str,
) -> Decimal:
    """Return the median YoY value for all retailers except the named one."""

    competitor_values = [
        _decimal(value)
        for name, value in yoy_by_retailer.items()
        if name.lower() != retailer.lower()
    ]
    if not competitor_values:
        raise AnalyticsError("At least one competitor YoY value is required")

    return _quantize_ratio(Decimal(str(median(competitor_values))))


def retailer_excess_inflation(
    retailer_yoy: Decimal | float | int | str,
    competitor_median: Decimal | float | int | str,
) -> Decimal:
    """Return retailer YoY minus competitor median YoY."""

    return _quantize_ratio(_decimal(retailer_yoy) - _decimal(competitor_median))


def current_premium_over_cheapest(
    retailer_current_unit_price: Decimal | float | int | str,
    cheapest_current_equivalent_unit_price: Decimal | float | int | str,
) -> Decimal:
    """Return premium over cheapest equivalent, e.g. 0.453 for +45.3%."""

    retailer_price = _decimal(retailer_current_unit_price)
    cheapest_price = _positive_decimal(
        cheapest_current_equivalent_unit_price,
        "cheapest_current_equivalent_unit_price",
    )
    return _quantize_ratio((retailer_price / cheapest_price) - Decimal("1"))


def historical_discount_strength(
    historical_12m_median_price: Decimal | float | int | str,
    current_effective_price: Decimal | float | int | str,
) -> Decimal:
    """Return discount versus historical median, e.g. 0.038 for a 3.8% discount."""

    historical_median = _positive_decimal(
        historical_12m_median_price,
        "historical_12m_median_price",
    )
    current_price = _decimal(current_effective_price)
    return _quantize_ratio((historical_median - current_price) / historical_median)


def shrinkflation_effective_increase(
    old_price: Decimal | float | int | str,
    old_normalised_size: Decimal | float | int | str,
    new_price: Decimal | float | int | str,
    new_normalised_size: Decimal | float | int | str,
) -> Decimal:
    """Return effective unit-price increase caused by price and size changes."""

    old_unit_price = _decimal(old_price) / _positive_decimal(
        old_normalised_size,
        "old_normalised_size",
    )
    new_unit_price = _decimal(new_price) / _positive_decimal(
        new_normalised_size,
        "new_normalised_size",
    )
    return _quantize_ratio((new_unit_price - old_unit_price) / old_unit_price)


def offender_score(
    retailer_excess_yoy_inflation_score: Decimal | float | int | str,
    current_premium_score: Decimal | float | int | str,
    shrinkflation_score: Decimal | float | int | str = 0,
    weak_promotion_score: Decimal | float | int | str = 0,
    volatility_score: Decimal | float | int | str = 0,
) -> Decimal:
    """Return weighted offender score on a 0..100 scale."""

    weighted = (
        Decimal("0.40") * _score(retailer_excess_yoy_inflation_score)
        + Decimal("0.25") * _score(current_premium_score)
        + Decimal("0.15") * _score(shrinkflation_score)
        + Decimal("0.10") * _score(weak_promotion_score)
        + Decimal("0.10") * _score(volatility_score)
    )
    return weighted.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP).normalize()


def _relative_change(
    current: Decimal | float | int | str,
    previous: Decimal | float | int | str,
) -> Decimal:
    previous_value = _positive_decimal(previous, "previous")
    return _quantize_ratio((_decimal(current) - previous_value) / previous_value)


def _score(value: Decimal | float | int | str) -> Decimal:
    score = _decimal(value)
    if score < 0 or score > 100:
        raise AnalyticsError(f"Score must be between 0 and 100: {score}")
    return score


def _positive_decimal(value: Decimal | float | int | str, label: str) -> Decimal:
    decimal_value = _decimal(value)
    if decimal_value <= 0:
        raise AnalyticsError(f"{label} must be greater than zero")
    return decimal_value


def _decimal(value: Decimal | float | int | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _quantize_ratio(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP).normalize()
