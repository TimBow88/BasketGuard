from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))

from basketguard_ingestion import (  # noqa: E402
    TESCO_FEATURE_FLAG,
    TescoIngestionProvider,
    TescoScraperConfig,
    run_tesco_allowlisted_collection,
)


FIXTURE_DIR = ROOT / "services" / "ingestion" / "fixtures"
TARGET_SEED = FIXTURE_DIR / "mvp_collection_targets.json"


class FakeCursor:
    def __init__(self) -> None:
        self.executions: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.executions.append((sql, params))

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()
        self.committed = False
        self.rolled_back = False

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class IngestionPipelineTests(unittest.TestCase):
    def test_disabled_pipeline_builds_failed_plan_without_network(self) -> None:
        old_value = os.environ.pop(TESCO_FEATURE_FLAG, None)
        try:
            result = run_tesco_allowlisted_collection(TARGET_SEED, enabled=False)
        finally:
            if old_value is not None:
                os.environ[TESCO_FEATURE_FLAG] = old_value

        self.assertEqual(len(result.targets), 2)
        self.assertEqual(result.ingestion_result.status, "failed")
        self.assertEqual(result.ingestion_result.target_count, 2)
        self.assertEqual(len(result.persistence_plan.collection_targets), 2)
        self.assertEqual(len(result.persistence_plan.ingestion_jobs), 1)
        self.assertEqual(len(result.persistence_plan.raw_product_snapshots), 0)
        self.assertIsNone(result.save_result)

    def test_enabled_fixture_pipeline_writes_snapshots_and_saves_plan(self) -> None:
        old_value = os.environ.get(TESCO_FEATURE_FLAG)
        os.environ[TESCO_FEATURE_FLAG] = "1"
        tomato_html = (FIXTURE_DIR / "tesco_chopped_tomatoes.html").read_text(encoding="utf-8")
        cornflakes_html = (FIXTURE_DIR / "tesco_clubcard_cornflakes.html").read_text(
            encoding="utf-8",
        )

        class FixtureTescoProvider(TescoIngestionProvider):
            def _fetch(self, url: str) -> str:
                if "303030001" in url:
                    return cornflakes_html
                return tomato_html

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                connection = FakeConnection()
                result = run_tesco_allowlisted_collection(
                    TARGET_SEED,
                    enabled=True,
                    snapshot_root=tmpdir,
                    connection=connection,
                    provider_factory=FixtureTescoProvider,
                )

                self.assertEqual(result.ingestion_result.status, "succeeded")
                self.assertEqual(result.ingestion_result.collected_count, 2)
                self.assertEqual(len(result.persistence_plan.raw_product_snapshots), 2)
                self.assertEqual(len(result.persistence_plan.price_observations), 2)
                self.assertIsNotNone(result.save_result)
                self.assertTrue(connection.committed)
                self.assertFalse(connection.rolled_back)
                self.assertTrue(connection.cursor_instance.closed)
                self.assertGreater(len(connection.cursor_instance.executions), 0)

                for snapshot in result.ingestion_result.raw_snapshots:
                    self.assertIsNotNone(snapshot.raw_payload_location)
                    self.assertTrue(Path(snapshot.raw_payload_location or "").exists())
        finally:
            if old_value is None:
                os.environ.pop(TESCO_FEATURE_FLAG, None)
            else:
                os.environ[TESCO_FEATURE_FLAG] = old_value


if __name__ == "__main__":
    unittest.main()
