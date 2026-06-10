from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))

from basketguard_ingestion import (  # noqa: E402
    TESCO_FEATURE_FLAG,
    RawProductSnapshot,
    SnapshotArtifactWriter,
    TescoIngestionProvider,
    TescoScraperConfig,
)


FIXTURE_DIR = ROOT / "services" / "ingestion" / "fixtures"


class SnapshotArtifactWriterTests(unittest.TestCase):
    def test_writes_raw_html_and_metadata(self) -> None:
        snapshot = RawProductSnapshot(
            retailer="Tesco",
            external_product_id="254879001",
            url="https://www.tesco.com/groceries/en-GB/products/254879001",
            raw_title="Tesco Chopped Tomatoes 400G",
            raw_price_text="GBP 0.55",
            raw_unit_price_text="GBP 1.38/kg",
            raw_promo_text=None,
            raw_pack_size_text="400g",
            postcode_context="MVP default region",
            collection_status="succeeded",
            parser_version="tesco-html-v1",
            collected_at="2026-06-07T08:00:00Z",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = SnapshotArtifactWriter(tmpdir).write_html(snapshot, "<html>ok</html>")

            raw_path = Path(artifact.raw_payload_location)
            metadata_path = Path(artifact.metadata_location)

            self.assertTrue(raw_path.exists())
            self.assertTrue(metadata_path.exists())
            self.assertEqual(raw_path.read_text(encoding="utf-8"), "<html>ok</html>")
            self.assertIn("sha256:", artifact.content_hash)

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["snapshot"]["external_product_id"], "254879001")
            self.assertEqual(metadata["content_hash"], artifact.content_hash)


class TescoSnapshotPersistenceTests(unittest.TestCase):
    def test_provider_persists_raw_html_when_snapshot_root_is_configured(self) -> None:
        old_value = os.environ.get(TESCO_FEATURE_FLAG)
        os.environ[TESCO_FEATURE_FLAG] = "1"
        html = (FIXTURE_DIR / "tesco_chopped_tomatoes.html").read_text(encoding="utf-8")

        class FixtureTescoProvider(TescoIngestionProvider):
            def _fetch(self, url: str) -> str:
                return html

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                result = FixtureTescoProvider(
                    TescoScraperConfig(
                        allowlisted_urls=(
                            "https://www.tesco.com/groceries/en-GB/products/254879001",
                        ),
                        enabled=True,
                        snapshot_root=Path(tmpdir),
                    ),
                ).collect()

                self.assertEqual(result.status, "succeeded")
                self.assertEqual(result.collected_count, 1)
                self.assertIsNotNone(result.raw_snapshots[0].raw_payload_location)
                raw_payload_location = Path(result.raw_snapshots[0].raw_payload_location or "")
                self.assertTrue(raw_payload_location.exists())
                self.assertIn(
                    "Tesco Chopped Tomatoes",
                    raw_payload_location.read_text(encoding="utf-8"),
                )
        finally:
            if old_value is None:
                os.environ.pop(TESCO_FEATURE_FLAG, None)
            else:
                os.environ[TESCO_FEATURE_FLAG] = old_value


if __name__ == "__main__":
    unittest.main()
