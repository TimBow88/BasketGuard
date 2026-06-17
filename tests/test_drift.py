from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))

from basketguard_ingestion import (  # noqa: E402
    DriftExpectations,
    DriftReport,
    ExtractedProduct,
    IngestionJobResult,
    PriceObservation,
    RawProductSnapshot,
    alert_on_drift,
    analyse_extracted_batch,
    analyse_job,
    format_drift_alert,
)


def _product(**overrides) -> ExtractedProduct:
    base = dict(
        retailer="Tesco",
        source_url="https://www.tesco.com/p/1",
        title="Tesco Cornflakes 500g",
        brand="Tesco",
        price="£1.20",
        currency="GBP",
        unit_price_text="24p/100g",
        pack_size_text="500g",
        category_breadcrumb="Cereal",
        image_url="https://img/1.jpg",
        availability="in_stock",
        promotion_text=None,
        external_product_id="1",
    )
    base.update(overrides)
    return ExtractedProduct(**base)


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


def _observation(**overrides) -> PriceObservation:
    base = dict(
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
    base.update(overrides)
    return PriceObservation(**base)


class ExtractedBatchDriftTests(unittest.TestCase):
    def test_healthy_batch_has_no_findings(self) -> None:
        report = analyse_extracted_batch("Tesco", [_product(), _product()])
        self.assertTrue(report.ok)
        self.assertFalse(report.has_breakage)

    def test_whole_batch_missing_price_is_critical_breakage(self) -> None:
        products = [_product(price=None) for _ in range(4)]
        report = analyse_extracted_batch("Tesco", products)

        self.assertTrue(report.has_breakage)
        self.assertEqual(report.missing_rates["price"], 1.0)
        checks = {finding.check for finding in report.findings}
        self.assertIn("missing_price", checks)

    def test_single_missing_price_within_tolerance(self) -> None:
        # One genuinely missing price out of five is below the 20% default.
        products = [_product()] * 4 + [_product(price=None)]
        report = analyse_extracted_batch("Tesco", products)
        self.assertTrue(report.ok)

    def test_missing_unit_price_is_warning_not_breakage(self) -> None:
        products = [_product(unit_price_text=None) for _ in range(4)]
        report = analyse_extracted_batch("Tesco", products)

        self.assertFalse(report.has_breakage)
        self.assertEqual(report.highest_severity, "warning")

    def test_block_signals_flag_critical(self) -> None:
        products = [_product(), _product()]
        report = analyse_extracted_batch(
            "Tesco", products, block_signals=["captcha", None]
        )
        self.assertTrue(report.has_breakage)
        self.assertEqual(report.block_rate, 0.5)

    def test_empty_batch_warns(self) -> None:
        report = analyse_extracted_batch("Tesco", [])
        self.assertFalse(report.ok)
        self.assertEqual(report.evaluated, 0)


class JobDriftTests(unittest.TestCase):
    def _job(self, **overrides) -> IngestionJobResult:
        base = dict(
            provider_name="tesco",
            job_type="tesco_allowlisted_product_collection",
            status="succeeded",
            retailer="Tesco",
            target_count=2,
            collected_count=2,
            parser_error_count=0,
            missing_price_count=0,
            raw_snapshots=[_snapshot(), _snapshot()],
            price_observations=[_observation(), _observation()],
        )
        base.update(overrides)
        return IngestionJobResult(**base)

    def test_healthy_job_ok(self) -> None:
        self.assertTrue(analyse_job(self._job()).ok)

    def test_failed_job_is_critical(self) -> None:
        report = analyse_job(self._job(status="failed", collected_count=0))
        self.assertTrue(report.has_breakage)
        self.assertIn("job_failed", {f.check for f in report.findings})

    def test_low_success_rate_flagged(self) -> None:
        report = analyse_job(
            self._job(status="partial", target_count=4, collected_count=1)
        )
        self.assertIn("low_success_rate", {f.check for f in report.findings})

    def test_non_positive_price_is_critical(self) -> None:
        report = analyse_job(
            self._job(price_observations=[_observation(unit_price=Decimal("0"))])
        )
        self.assertTrue(report.has_breakage)
        self.assertIn("non_positive_price", {f.check for f in report.findings})

    def test_snapshot_missing_price_flagged(self) -> None:
        report = analyse_job(
            self._job(raw_snapshots=[_snapshot(raw_price_text="  ") for _ in range(2)])
        )
        self.assertIn("snapshot_missing_price", {f.check for f in report.findings})


class AlertingTests(unittest.TestCase):
    def test_alert_only_sends_when_not_ok(self) -> None:
        sent: list[DriftReport] = []

        class Sink:
            def send(self, report: DriftReport) -> None:
                sent.append(report)

        ok_report = analyse_extracted_batch("Tesco", [_product()])
        self.assertFalse(alert_on_drift(ok_report, Sink()))

        broken = analyse_extracted_batch("Tesco", [_product(price=None)])
        self.assertTrue(alert_on_drift(broken, Sink()))
        self.assertEqual(len(sent), 1)

    def test_format_includes_severity_and_messages(self) -> None:
        broken = analyse_extracted_batch("Tesco", [_product(price=None)])
        text = format_drift_alert(broken)
        self.assertIn("critical", text)
        self.assertIn("Tesco", text)


if __name__ == "__main__":
    unittest.main()
