from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "apps" / "web"


class WebUiAssetTests(unittest.TestCase):
    def test_static_ui_files_exist(self) -> None:
        for filename in ("index.html", "styles.css", "app.js"):
            self.assertTrue((WEB_DIR / filename).exists(), filename)

    def test_html_references_local_assets(self) -> None:
        html = (WEB_DIR / "index.html").read_text(encoding="utf-8")

        self.assertIn('href="./styles.css"', html)
        self.assertIn('src="./app.js"', html)
        for view_id in ("overview", "comparisons", "gathering", "database"):
            self.assertIn(f'id="{view_id}"', html)

    def test_javascript_fixture_reference_exists(self) -> None:
        javascript = (WEB_DIR / "app.js").read_text(encoding="utf-8")
        match = re.search(r'const FIXTURE_URL = "([^"]+)"', javascript)

        self.assertIsNotNone(match)
        fixture_path = ROOT / match.group(1).lstrip("/")
        self.assertTrue(fixture_path.exists(), fixture_path)

    def test_data_gathering_migration_tables_exist(self) -> None:
        sql = (ROOT / "db" / "migrations" / "0002_data_gathering_workflow.sql").read_text(
            encoding="utf-8",
        )

        for table in ("collection_targets", "ingestion_jobs", "ingestion_job_targets"):
            self.assertRegex(sql, rf"CREATE TABLE {table}\b")

    def test_css_uses_stable_letter_spacing(self) -> None:
        css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")
        letter_spacing_values = re.findall(r"letter-spacing:\s*([^;]+);", css)

        self.assertTrue(letter_spacing_values)
        self.assertTrue(all(value.strip() == "0" for value in letter_spacing_values))

    def test_app_does_not_use_unbound_current_unit_price_shorthand(self) -> None:
        javascript = (WEB_DIR / "app.js").read_text(encoding="utf-8")

        self.assertNotIn("\n        currentUnitPrice,\n", javascript)
        self.assertIn("currentUnitPrice: item.currentUnitPrice", javascript)


if __name__ == "__main__":
    unittest.main()
