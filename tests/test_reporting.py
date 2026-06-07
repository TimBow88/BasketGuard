from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "analytics" / "src"))
sys.path.insert(0, str(ROOT / "services" / "reporting" / "src"))

from basketguard_reporting import generate_weekly_report, render_plain_text_report  # noqa: E402


FIXTURE_PATH = ROOT / "tests" / "fixtures" / "seed_price_observations.json"


class WeeklyReportTests(unittest.TestCase):
    def test_generates_structured_weekly_report(self) -> None:
        report = generate_weekly_report(_fixture())

        self.assertEqual(report["title"], "Your weekly grocery warning")
        self.assertEqual(report["summary"]["tracked_groups"], 10)
        self.assertEqual(report["summary"]["retailer_count"], 4)
        self.assertEqual(report["summary"]["worst_retailer"], "Sainsbury's")
        self.assertEqual(report["summary"]["avoidable_overspend"], "2.42")
        self.assertEqual(len(report["worst_offenders"]), 5)

    def test_orders_worst_offenders_by_score(self) -> None:
        report = generate_weekly_report(_fixture())
        top = report["worst_offenders"][0]

        self.assertEqual(top["rank"], 1)
        self.assertEqual(top["retailer"], "Tesco")
        self.assertEqual(top["group_slug"], "own_brand_chopped_tomatoes_standard_400g")
        self.assertEqual(top["headline"], "Avoid Tesco for Own-brand chopped tomatoes 400g.")
        self.assertGreaterEqual(float(top["offender_score"]), 60)

    def test_includes_retailer_comparison(self) -> None:
        report = generate_weekly_report(_fixture())
        comparison = report["retailer_comparison"]

        self.assertEqual(comparison[0]["retailer"], "Sainsbury's")
        self.assertEqual(comparison[-1]["retailer"], "Morrisons")
        self.assertEqual(comparison[-1]["overspend_vs_cheapest"], "0.00")

    def test_renders_plain_text_report_wording(self) -> None:
        report = generate_weekly_report(_fixture())
        text = render_plain_text_report(report)

        self.assertIn("Your weekly grocery warning", text)
        self.assertIn("Sainsbury's is currently the worst-value retailer", text)
        self.assertIn("Estimated avoidable overspend: £2.42", text)
        self.assertIn("1. Tesco - Own-brand chopped tomatoes 400g", text)
        self.assertIn("Tesco +57.1% YoY. Competitor median +7.7%.", text)
        self.assertIn("Recommendation: Avoid Tesco for this item this week.", text)


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
