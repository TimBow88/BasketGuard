"""Orchestrate a daily collection run across providers.

Ties the moving parts into one resilient run: execute each provider, evaluate
its result for drift, optionally route drift to an alert sink, and produce a
consolidated summary. One provider failing (or raising) does not abort the rest
— its failure is captured as an outcome so the run is observable end to end.

This is deliberately scheduler-agnostic: a cron job, APScheduler or a worker
process calls ``CollectionOrchestrator.run`` with the provider runs that
``scheduling.due_targets`` selected. No real time, network or database is
required to test it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Callable, Sequence

from .contracts import IngestionJobResult
from .drift import (
    DriftAlertSink,
    DriftExpectations,
    DriftFinding,
    DriftReport,
    alert_on_drift,
    analyse_job,
)


@dataclass(frozen=True)
class ProviderRun:
    name: str
    run: Callable[[], IngestionJobResult]


@dataclass(frozen=True)
class OrchestrationOutcome:
    provider_name: str
    drift: DriftReport
    result: IngestionJobResult | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and not self.drift.has_breakage


@dataclass(frozen=True)
class OrchestrationRunResult:
    started_at: str
    outcomes: list[OrchestrationOutcome] = field(default_factory=list)
    alerts_sent: int = 0

    @property
    def total_targets(self) -> int:
        return sum(o.result.target_count for o in self.outcomes if o.result)

    @property
    def total_collected(self) -> int:
        return sum(o.result.collected_count for o in self.outcomes if o.result)

    @property
    def any_breakage(self) -> bool:
        return any(o.drift.has_breakage or o.error for o in self.outcomes)

    @property
    def failed_providers(self) -> list[str]:
        return [o.provider_name for o in self.outcomes if not o.ok]


class CollectionOrchestrator:
    def __init__(
        self,
        *,
        expectations: DriftExpectations | None = None,
        alert_sink: DriftAlertSink | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.expectations = expectations or DriftExpectations()
        self.alert_sink = alert_sink
        self.clock = clock or (lambda: datetime.now(UTC))

    def run(self, provider_runs: Sequence[ProviderRun]) -> OrchestrationRunResult:
        started_at = _isoformat(self.clock())
        outcomes: list[OrchestrationOutcome] = []
        alerts_sent = 0

        for provider_run in provider_runs:
            outcome = self._run_one(provider_run)
            outcomes.append(outcome)
            if self.alert_sink is not None and alert_on_drift(outcome.drift, self.alert_sink):
                alerts_sent += 1

        return OrchestrationRunResult(
            started_at=started_at,
            outcomes=outcomes,
            alerts_sent=alerts_sent,
        )

    def _run_one(self, provider_run: ProviderRun) -> OrchestrationOutcome:
        try:
            result = provider_run.run()
        except Exception as error:  # noqa: BLE001 - a provider crash is an outcome, not a halt
            drift = DriftReport(
                retailer=provider_run.name,
                evaluated=0,
                findings=[
                    DriftFinding(
                        check="provider_exception",
                        severity="critical",
                        message=f"Provider {provider_run.name!r} raised: {error}",
                    )
                ],
            )
            return OrchestrationOutcome(
                provider_name=provider_run.name,
                drift=drift,
                error=str(error) or error.__class__.__name__,
            )

        drift = analyse_job(result, expectations=self.expectations)
        return OrchestrationOutcome(
            provider_name=provider_run.name,
            drift=drift,
            result=result,
        )


def _isoformat(moment: datetime) -> str:
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")
