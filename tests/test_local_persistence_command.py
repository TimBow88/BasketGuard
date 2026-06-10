from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))

from basketguard_ingestion import (  # noqa: E402
    AllowlistedProductUrlError,
    TESCO_FEATURE_FLAG,
    TescoIngestionProvider,
    run_allowlisted_product_url_persistence,
)
from basketguard_ingestion.local_persistence import main  # noqa: E402


FIXTURE_DIR = ROOT / "services" / "ingestion" / "fixtures"
TARGET_SEED = FIXTURE_DIR / "mvp_collection_targets.json"
TOMATO_URL = "https://www.tesco.com/groceries/en-GB/products/254879001"


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
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


class FixtureTescoProvider(TescoIngestionProvider):
    def _fetch(self, url: str) -> str:
        return (FIXTURE_DIR / "tesco_chopped_tomatoes.html").read_text(encoding="utf-8")


class BadHtmlTescoProvider(TescoIngestionProvider):
    def _fetch(self, url: str) -> str:
        return "<html><body>No product fields</body></html>"


class LocalPersistenceCommandTests(unittest.TestCase):
    def test_single_allowlisted_url_writes_snapshot_and_saves_plan(self) -> None:
        old_value = os.environ.get(TESCO_FEATURE_FLAG)
        os.environ[TESCO_FEATURE_FLAG] = "1"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                connection = FakeConnection()
                result = run_allowlisted_product_url_persistence(
                    product_url=TOMATO_URL + "?tracking=test",
                    allowlist_seed_path=TARGET_SEED,
                    snapshot_root=tmpdir,
                    connection=connection,
                    enabled=True,
                    provider_factory=FixtureTescoProvider,
                )

                self.assertEqual(result.ingestion_result.status, "succeeded")
                self.assertEqual(result.ingestion_result.target_count, 1)
                self.assertEqual(result.ingestion_result.collected_count, 1)
                self.assertEqual(len(result.persistence_plan.raw_product_snapshots), 1)
                self.assertEqual(len(result.persistence_plan.price_observations), 1)
                self.assertIsNotNone(result.save_result)
                self.assertGreater(result.save_result.total_rows, 0)
                self.assertTrue(connection.committed)
                self.assertFalse(connection.rolled_back)

                snapshot_path = Path(
                    result.ingestion_result.raw_snapshots[0].raw_payload_location or "",
                )
                self.assertTrue(snapshot_path.exists())
                self.assertEqual(snapshot_path.name, "raw.html")
        finally:
            if old_value is None:
                os.environ.pop(TESCO_FEATURE_FLAG, None)
            else:
                os.environ[TESCO_FEATURE_FLAG] = old_value

    def test_single_allowlisted_url_saves_parser_failure_attempt(self) -> None:
        old_value = os.environ.get(TESCO_FEATURE_FLAG)
        os.environ[TESCO_FEATURE_FLAG] = "1"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                connection = FakeConnection()
                result = run_allowlisted_product_url_persistence(
                    product_url=TOMATO_URL,
                    allowlist_seed_path=TARGET_SEED,
                    snapshot_root=tmpdir,
                    connection=connection,
                    enabled=True,
                    provider_factory=BadHtmlTescoProvider,
                )

                self.assertEqual(result.ingestion_result.status, "failed")
                self.assertEqual(len(result.persistence_plan.raw_product_snapshots), 0)
                self.assertEqual(len(result.persistence_plan.price_observations), 0)
                self.assertEqual(len(result.persistence_plan.ingestion_job_targets), 1)
                self.assertEqual(result.persistence_plan.ingestion_job_targets[0]["status"], "failed")
                self.assertEqual(
                    result.persistence_plan.ingestion_job_targets[0]["error_code"],
                    "parse_error",
                )
                self.assertIn(
                    "Missing product title",
                    result.persistence_plan.ingestion_job_targets[0]["error_message"],
                )
                self.assertTrue(connection.committed)
                self.assertFalse(connection.rolled_back)
        finally:
            if old_value is None:
                os.environ.pop(TESCO_FEATURE_FLAG, None)
            else:
                os.environ[TESCO_FEATURE_FLAG] = old_value

    def test_rejects_url_that_is_not_in_allowlist_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(AllowlistedProductUrlError):
                run_allowlisted_product_url_persistence(
                    product_url="https://www.tesco.com/groceries/en-GB/products/999999999",
                    allowlist_seed_path=TARGET_SEED,
                    snapshot_root=tmpdir,
                    connection=FakeConnection(),
                    provider_factory=FixtureTescoProvider,
                )

    def test_cli_uses_postgres_connection_and_repository_path(self) -> None:
        old_value = os.environ.get(TESCO_FEATURE_FLAG)
        os.environ[TESCO_FEATURE_FLAG] = "1"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                connection = FakeConnection()
                with patch(
                    "basketguard_ingestion.local_persistence.open_postgres_connection",
                    return_value=connection,
                ), patch("sys.stdout", new_callable=io.StringIO):
                    exit_code = main(
                        [
                            "--url",
                            TOMATO_URL,
                            "--allowlist-seed",
                            str(TARGET_SEED),
                            "--snapshot-root",
                            tmpdir,
                            "--database-url",
                            "postgresql://example.test/basketguard",
                            "--live",
                        ],
                        provider_factory=FixtureTescoProvider,
                    )

                self.assertEqual(exit_code, 0)
                self.assertTrue(connection.committed)
                self.assertTrue(connection.closed)
                self.assertGreater(len(connection.cursor_instance.executions), 0)
        finally:
            if old_value is None:
                os.environ.pop(TESCO_FEATURE_FLAG, None)
            else:
                os.environ[TESCO_FEATURE_FLAG] = old_value


if __name__ == "__main__":
    unittest.main()
