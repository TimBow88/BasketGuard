from __future__ import annotations

import sys
import unittest
from datetime import datetime, UTC
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))

from basketguard_ingestion import (  # noqa: E402
    CollectionOrchestrator,
    DriftReport,
    IngestionJobResult,
    PriceObservation,
    ProviderRun,
    RawProductSnapshot,
)


def _snapshot(**overrides) -> RawProductSnapshot:
    base = dict(
        retailer="Tesco",
        external_product_id="1",
        url="https://www.tesco.com/p/1",
        raw_title="Tesco Cornflakes 500g",
        raw_price_text="£1.20",
        raw_unit_price_text="24p/100g",
        raw_promo_text=None,
        raw_pack_size_text="500g",
        postcode_context=None,
        collection_status="succeeded",
        parser_version="tesco-html-v1",
        collected_at="2026-06-17T00:00:00Z",
    )
    base.update(overrides)
    return RawProductSnapshot(**base)


def _observation() -> PriceObservation:
    return PriceObservation(
        retailer="Tesco",
        external_product_id="1",
        shelf_price=Decimal("1.20"),
        loyalty_price=None,
        was_price=None,
        effective_price=Decimal("1.20"),
        unit_price=Decimal("2.40"),
        unit_price_basis="kg",
        promo_type=None,
        promo_description=None,
        availability="in_stock",
        postcode_context=None,
        collected_at="2026-06-17T00:00:00Z",
    )


def _healthy_job(retailer: str) -> IngestionJobResult:
    return IngestionJobResult(
        provider_name=retailer.lower(),
        job_type="collection",
        status="succeeded",
        retailer=retailer,
        target_count=1,
        collected_count=1,
        parser_error_count=0,
        missing_price_count=0,
        raw_snapshots=[_snapshot(retailer=retailer)],
        price_observations=[_observation()],
    )


class CollectingSink:
    def __init__(self) -> None:
        self.reports: list[DriftReport] = []

    def send(self, report: DriftReport) -> None:
        self.reports.append(report)


FIXED_NOW = lambda: datetime(2026, 6, 17, 6, 0, 0, tzinfo=UTC)


class CollectionOrchestratorTests(unittest.TestCase):
    def test_runs_all_providers_and_summarises(self) -> None:
        runs = [
            ProviderRun("tesco", lambda: _healthy_job("Tesco")),
            ProviderRun("asda", lambda: _healthy_job("Asda")),
        ]
        result = CollectionOrchestrator(clock=FIXED_NOW).run(runs)

        self.assertEqual(len(result.outcomes), 2)
        self.assertEqual(result.total_collected, 2)
        self.assertEqual(result.total_targets, 2)
        self.assertFalse(result.any_breakage)
        self.assertEqual(result.started_at, "2026-06-17T06:00:00Z")

    def test_provider_exception_is_captured_not_raised(self) -> None:
        def boom() -> IngestionJobResult:
            raise RuntimeError("network down")

        runs = [
            ProviderRun("tesco", boom),
            ProviderRun("asda", lambda: _healthy_job("Asda")),
        ]
        sink = CollectingSink()
        result = CollectionOrchestrator(alert_sink=sink, clock=FIXED_NOW).run(runs)

        self.assertEqual(len(result.outcomes), 2)
        self.assertTrue(result.any_breakage)
        self.assertEqual(result.failed_providers, ["tesco"])
        # The healthy provider still ran and its result is present.
        self.assertEqual(result.total_collected, 1)
        # The crashing provider raised an alert.
        self.assertEqual(result.alerts_sent, 1)
        self.assertEqual(sink.reports[0].findings[0].check, "provider_exception")

    def test_drift_in_result_triggers_alert(self) -> None:
        failed = IngestionJobResult(
            provider_name="tesco",
            job_type="collection",
            status="failed",
            retailer="Tesco",
            target_count=2,
            collected_count=0,
            parser_error_count=2,
            missing_price_count=2,
        )
        sink = CollectingSink()
        result = CollectionOrchestrator(alert_sink=sink, clock=FIXED_NOW).run(
            [ProviderRun("tesco", lambda: failed)]
        )

        self.assertTrue(result.any_breakage)
        self.assertEqual(result.alerts_sent, 1)


if __name__ == "__main__":
    unittest.main()
