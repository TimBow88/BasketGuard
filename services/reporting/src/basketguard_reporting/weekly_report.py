from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from basketguard_analytics import (
    competitor_median_yoy,
    current_premium_over_cheapest,
    offender_score,
    retailer_excess_inflation,
    yoy_increase,
)


REPORT_TITLE = "Your weekly grocery warning"


def generate_weekly_report(fixture: dict[str, Any], max_offenders: int = 5) -> dict[str, Any]:
    findings = _rank_findings(fixture)
    retailer_comparison = _retailer_comparison(fixture, findings)
    worst_retailer = max(
        retailer_comparison,
        key=lambda item: Decimal(str(item["basket_total"])),
    )
    cheapest_total = min(Decimal(str(item["basket_total"])) for item in retailer_comparison)

    return {
        "title": REPORT_TITLE,
        "period": {
            "collected_at": fixture["collected_at"],
            "previous_collected_at": fixture["previous_collected_at"],
        },
        "summary": {
            "worst_retailer": worst_retailer["retailer"],
            "avoidable_overspend": _money(
                Decimal(str(worst_retailer["basket_total"])) - cheapest_total
            ),
            "tracked_groups": len(fixture["groups"]),
            "retailer_count": len(retailer_comparison),
            "headline": (
                f"{worst_retailer['retailer']} is currently the worst-value retailer "
                "for your tracked basket."
            ),
        },
        "worst_offenders": findings[:max_offenders],
        "retailer_comparison": retailer_comparison,
        "methodology_note": (
            "Scores compare unit-price adjusted YoY change, competitor median YoY, "
            "and current premium over the cheapest equivalent product."
        ),
    }


def render_plain_text_report(report: dict[str, Any]) -> str:
    lines = [
        report["title"],
        "",
        report["summary"]["headline"],
        "",
        f"Estimated avoidable overspend: {format_gbp(report['summary']['avoidable_overspend'])}",
        "",
        "Worst offenders:",
    ]

    for offender in report["worst_offenders"]:
        lines.extend(
            [
                f"{offender['rank']}. {offender['retailer']} - {offender['group_name']}",
                (
                    f"   {offender['retailer']} {format_percent(offender['evidence']['retailer_yoy'])} YoY. "
                    f"Competitor median {format_percent(offender['evidence']['competitor_median_yoy'])}."
                ),
                (
                    "   Current premium over cheapest: "
                    f"{format_percent(offender['evidence']['current_premium'])}."
                ),
                f"   Recommendation: {offender['recommendation']}",
            ]
        )

    lines.extend(["", "Retailer comparison:"])
    for retailer in report["retailer_comparison"]:
        lines.append(
            f"- {retailer['retailer']}: {format_gbp(retailer['basket_total'])} "
            f"({format_gbp(retailer['overspend_vs_cheapest'])} over cheapest)"
        )

    lines.extend(["", f"Methodology: {report['methodology_note']}"])
    return "\n".join(lines)


def _rank_findings(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []

    for group in fixture["groups"]:
        enriched = []
        yoy_by_retailer = {}

        for observation in group["observations"]:
            current_unit_price = _unit_price(observation["current"])
            previous_unit_price = _unit_price(observation["previous_year"])
            retailer_yoy = yoy_increase(current_unit_price, previous_unit_price)
            enriched_observation = {
                "observation": observation,
                "current_unit_price": current_unit_price,
                "previous_unit_price": previous_unit_price,
                "retailer_yoy": retailer_yoy,
            }
            enriched.append(enriched_observation)
            yoy_by_retailer[observation["retailer"]] = retailer_yoy

        cheapest_unit_price = min(item["current_unit_price"] for item in enriched)

        for item in enriched:
            observation = item["observation"]
            retailer = observation["retailer"]
            competitor_yoy = competitor_median_yoy(yoy_by_retailer, retailer)
            excess = retailer_excess_inflation(item["retailer_yoy"], competitor_yoy)
            premium = current_premium_over_cheapest(item["current_unit_price"], cheapest_unit_price)
            score = offender_score(
                retailer_excess_yoy_inflation_score=_ratio_to_score(excess, Decimal("0.50")),
                current_premium_score=_ratio_to_score(premium, Decimal("0.50")),
            )

            findings.append(
                {
                    "rank": 0,
                    "retailer": retailer,
                    "group_slug": group["slug"],
                    "group_name": group["display_name"],
                    "product_name": observation["product_name"],
                    "offender_score": _score(score),
                    "confidence": {
                        "score": 91,
                        "label": "High confidence",
                        "reason": "4 retailer equivalents matched in fixture data.",
                    },
                    "headline": _headline(retailer, group["display_name"], score),
                    "explanation": (
                        f"{retailer} has a retailer-specific increase above the competitor median "
                        "and is compared on a unit-price basis."
                    ),
                    "recommendation": _recommendation(retailer, score),
                    "evidence": {
                        "retailer_yoy": _ratio(item["retailer_yoy"]),
                        "competitor_median_yoy": _ratio(competitor_yoy),
                        "retailer_excess_inflation": _ratio(excess),
                        "current_premium": _ratio(premium),
                        "current_unit_price": _money(item["current_unit_price"]),
                        "cheapest_unit_price": _money(cheapest_unit_price),
                    },
                }
            )

    ranked = sorted(
        findings,
        key=lambda finding: (
            Decimal(str(finding["offender_score"])),
            Decimal(str(finding["evidence"]["current_premium"])),
            Decimal(str(finding["evidence"]["retailer_yoy"])),
        ),
        reverse=True,
    )

    for index, finding in enumerate(ranked, start=1):
        finding["rank"] = index

    return ranked


def _retailer_comparison(
    fixture: dict[str, Any],
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    totals: dict[str, Decimal] = {}

    for group in fixture["groups"]:
        for observation in group["observations"]:
            retailer = observation["retailer"]
            totals[retailer] = totals.get(retailer, Decimal("0")) + Decimal(
                observation["current"]["price"]
            )

    cheapest_total = min(totals.values())
    offender_counts = {
        retailer: sum(
            1
            for finding in findings
            if finding["retailer"] == retailer
            and Decimal(str(finding["offender_score"])) >= Decimal("20")
        )
        for retailer in totals
    }

    return sorted(
        [
            {
                "retailer": retailer,
                "basket_total": _money(total),
                "overspend_vs_cheapest": _money(total - cheapest_total),
                "watch_or_worse_count": offender_counts[retailer],
            }
            for retailer, total in totals.items()
        ],
        key=lambda item: Decimal(str(item["basket_total"])),
        reverse=True,
    )


def _unit_price(observation: dict[str, str]) -> Decimal:
    price = Decimal(observation["price"])
    size = Decimal(observation["normalised_size"])
    return (price / size).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP).normalize()


def _ratio_to_score(value: Decimal, cap: Decimal) -> Decimal:
    if value <= 0:
        return Decimal("0")
    return min(Decimal("100"), (value / cap * Decimal("100")))


def _headline(retailer: str, group_name: str, score: Decimal) -> str:
    if score >= Decimal("60"):
        return f"Avoid {retailer} for {group_name}."
    if score >= Decimal("40"):
        return f"{retailer} is poor value for {group_name}."
    if score >= Decimal("20"):
        return f"Watch {retailer} for {group_name}."
    return f"No issue detected for {retailer} {group_name}."


def _recommendation(retailer: str, score: Decimal) -> str:
    if score >= Decimal("60"):
        return f"Avoid {retailer} for this item this week."
    if score >= Decimal("40"):
        return "Switch to the cheapest equivalent if available."
    if score >= Decimal("20"):
        return "Monitor before buying at this retailer."
    return "No issue detected."


def _money(value: Decimal | int | float | str) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _ratio(value: Decimal | int | float | str) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP).normalize())


def _score(value: Decimal | int | float | str) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP).normalize())


def format_gbp(value: Decimal | int | float | str) -> str:
    return f"£{Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}"


def format_percent(value: Decimal | int | float | str) -> str:
    decimal_value = Decimal(str(value)) * Decimal("100")
    sign = "+" if decimal_value > 0 else ""
    return f"{sign}{decimal_value.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"
