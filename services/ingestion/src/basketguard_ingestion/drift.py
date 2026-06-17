"""Scraper drift & parser-breakage detection.

Retailer markup changes silently. When a selector moves, a parser starts
returning nulls and the pipeline keeps "succeeding" with empty data. A single
missing price can be genuine (out of stock); a *whole batch* losing its price is
a parser break. This module works at the batch altitude so it can tell those
apart, and surfaces failed jobs and probable WAF blocks.

Two entry points, both returning a ``DriftReport``:

* ``analyse_extracted_batch`` — structural canaries over a batch of
  ``ExtractedProduct`` (e.g. replaying fixtures), independent of the database;
* ``analyse_job`` — operational checks over a real ``IngestionJobResult`` (job
  success rate, missing fields in the raw snapshots, non-positive prices).

Alerting is a thin injectable seam (``DriftAlertSink``) so wiring to a real
channel is a later, separate concern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal, Mapping, Protocol, Sequence

from .contracts import ExtractedProduct, IngestionJobResult


Severity = Literal["critical", "warning", "info"]


@dataclass(frozen=True)
class DriftFinding:
    check: str
    severity: Severity
    message: str
    detail: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DriftExpectations:
    """Tolerated missing-field / failure rates before a finding is raised.

    Rates are fractions in ``0..1`` of the evaluated batch. Title is expected on
    essentially every page, so its default tolerance is zero; unit price is more
    often legitimately absent, so it tolerates more.
    """

    max_missing_title: float = 0.0
    max_missing_price: float = 0.2
    max_missing_unit_price: float = 0.5
    min_success_rate: float = 0.5
    max_block_rate: float = 0.0


@dataclass(frozen=True)
class DriftReport:
    retailer: str | None
    evaluated: int
    findings: list[DriftFinding]
    missing_rates: Mapping[str, float] = field(default_factory=dict)
    block_rate: float = 0.0

    @property
    def has_breakage(self) -> bool:
        return any(finding.severity == "critical" for finding in self.findings)

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def highest_severity(self) -> Severity | None:
        for severity in ("critical", "warning", "info"):
            if any(finding.severity == severity for finding in self.findings):
                return severity  # type: ignore[return-value]
        return None


class DriftAlertSink(Protocol):
    def send(self, report: DriftReport) -> Any: ...


def analyse_extracted_batch(
    retailer: str | None,
    products: Sequence[ExtractedProduct],
    *,
    expectations: DriftExpectations | None = None,
    block_signals: Sequence[str | None] | None = None,
) -> DriftReport:
    expectations = expectations or DriftExpectations()
    evaluated = len(products)
    findings: list[DriftFinding] = []
    missing_rates: dict[str, float] = {}

    if evaluated == 0:
        findings.append(
            DriftFinding(
                check="empty_batch",
                severity="warning",
                message="No products were extracted; nothing to evaluate for drift.",
            )
        )
        return DriftReport(retailer=retailer, evaluated=0, findings=findings)

    field_tolerances = (
        ("title", lambda p: not p.title, expectations.max_missing_title, "critical"),
        ("price", lambda p: not p.price, expectations.max_missing_price, "critical"),
        (
            "unit_price_text",
            lambda p: not p.unit_price_text,
            expectations.max_missing_unit_price,
            "warning",
        ),
    )

    for name, is_missing, tolerance, severity in field_tolerances:
        missing = sum(1 for product in products if is_missing(product))
        rate = missing / evaluated
        missing_rates[name] = rate
        if rate > tolerance:
            findings.append(
                DriftFinding(
                    check=f"missing_{name}",
                    severity=severity,  # type: ignore[arg-type]
                    message=(
                        f"{missing}/{evaluated} products missing {name} "
                        f"({rate:.0%} > tolerated {tolerance:.0%}) — likely parser drift."
                    ),
                    detail={"missing": missing, "evaluated": evaluated, "rate": rate},
                )
            )

    block_rate = 0.0
    if block_signals:
        blocked = sum(1 for signal in block_signals if signal)
        block_rate = blocked / evaluated
        if block_rate > expectations.max_block_rate:
            findings.append(
                DriftFinding(
                    check="blocked_responses",
                    severity="critical",
                    message=(
                        f"{blocked}/{evaluated} responses look like anti-bot blocks "
                        f"({block_rate:.0%}) — collection may be challenged."
                    ),
                    detail={"blocked": blocked, "evaluated": evaluated},
                )
            )

    return DriftReport(
        retailer=retailer,
        evaluated=evaluated,
        findings=findings,
        missing_rates=missing_rates,
        block_rate=block_rate,
    )


def analyse_job(
    result: IngestionJobResult,
    *,
    expectations: DriftExpectations | None = None,
) -> DriftReport:
    expectations = expectations or DriftExpectations()
    findings: list[DriftFinding] = []

    if result.status == "failed":
        findings.append(
            DriftFinding(
                check="job_failed",
                severity="critical",
                message=f"Ingestion job {result.job_type!r} failed for {result.retailer}.",
                detail={"parser_errors": result.parser_error_count},
            )
        )

    success_rate = float(result.success_rate)
    if result.target_count and success_rate < expectations.min_success_rate:
        findings.append(
            DriftFinding(
                check="low_success_rate",
                severity="critical" if success_rate == 0 else "warning",
                message=(
                    f"Job collected {result.collected_count}/{result.target_count} "
                    f"targets ({success_rate:.0%} < {expectations.min_success_rate:.0%})."
                ),
                detail={"success_rate": success_rate},
            )
        )

    snapshots = result.raw_snapshots
    missing_rates: dict[str, float] = {}
    if snapshots:
        snapshot_checks = (
            ("title", lambda s: not s.raw_title.strip(), expectations.max_missing_title, "critical"),
            ("price", lambda s: not s.raw_price_text.strip(), expectations.max_missing_price, "critical"),
            (
                "unit_price",
                lambda s: not s.raw_unit_price_text.strip(),
                expectations.max_missing_unit_price,
                "warning",
            ),
        )
        for name, is_missing, tolerance, severity in snapshot_checks:
            missing = sum(1 for snapshot in snapshots if is_missing(snapshot))
            rate = missing / len(snapshots)
            missing_rates[name] = rate
            if rate > tolerance:
                findings.append(
                    DriftFinding(
                        check=f"snapshot_missing_{name}",
                        severity=severity,  # type: ignore[arg-type]
                        message=(
                            f"{missing}/{len(snapshots)} snapshots missing {name} "
                            f"({rate:.0%} > tolerated {tolerance:.0%})."
                        ),
                        detail={"missing": missing, "evaluated": len(snapshots)},
                    )
                )

    non_positive = [
        observation
        for observation in result.price_observations
        if observation.shelf_price <= Decimal("0") or observation.unit_price <= Decimal("0")
    ]
    if non_positive:
        findings.append(
            DriftFinding(
                check="non_positive_price",
                severity="critical",
                message=(
                    f"{len(non_positive)} price observations have a non-positive "
                    "shelf or unit price — probable parser misread."
                ),
                detail={"count": len(non_positive)},
            )
        )

    return DriftReport(
        retailer=result.retailer,
        evaluated=len(snapshots),
        findings=findings,
        missing_rates=missing_rates,
    )


def format_drift_alert(report: DriftReport) -> str:
    if report.ok:
        return f"[BasketGuard drift] {report.retailer}: OK ({report.evaluated} evaluated)"
    lines = [
        f"[BasketGuard drift] {report.retailer}: {report.highest_severity} "
        f"({report.evaluated} evaluated)"
    ]
    for finding in report.findings:
        lines.append(f"  - {finding.severity}: {finding.message}")
    return "\n".join(lines)


def alert_on_drift(report: DriftReport, sink: DriftAlertSink) -> bool:
    """Send the report to the sink when there is anything to report. Returns sent?"""

    if report.ok:
        return False
    sink.send(report)
    return True
