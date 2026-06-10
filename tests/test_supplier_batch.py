from __future__ import annotations

import io
import json
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
    ASDA_FEATURE_FLAG,
    AsdaIngestionProvider,
    TESCO_FEATURE_FLAG,
    TescoIngestionProvider,
    run_supplier_batch_persistence,
)
from basketguard_ingestion.supplier_batch import main  # noqa: E402


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
        self.commits = 0
        self.rolled_back = False
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


class FixtureTescoProvider(TescoIngestionProvider):
    def _fetch(self, url: str) -> str:
        if "303030001" in url:
            return (FIXTURE_DIR / "tesco_clubcard_cornflakes.html").read_text(encoding="utf-8")
        return (FIXTURE_DIR / "tesco_chopped_tomatoes.html").read_text(encoding="utf-8")


class FixtureAsdaProvider(AsdaIngestionProvider):
    def _fetch(self, url: str) -> str:
        return (FIXTURE_DIR / "asda_cornflakes.html").read_text(encoding="utf-8")


class SupplierBatchTests(unittest.TestCase):
    def test_batches_many_allowlisted_tesco_targets_and_saves_each_batch(self) -> None:
        old_value = os.environ.get(TESCO_FEATURE_FLAG)
        os.environ[TESCO_FEATURE_FLAG] = "1"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                connection = FakeConnection()
                result = run_supplier_batch_persistence(
                    TARGET_SEED,
                    snapshot_root=tmpdir,
                    connection=connection,
                    enabled=True,
                    retailers={"tesco"},
                    batch_size=1,
                    provider_factory=FixtureTescoProvider,
                )

                self.assertEqual(len(result.batch_results), 2)
                self.assertEqual(result.target_count, 2)
                self.assertEqual(result.collected_count, 2)
                self.assertEqual(result.failed_or_skipped_count, 0)
                self.assertEqual(connection.commits, 2)
                self.assertFalse(connection.rolled_back)
                self.assertGreater(result.saved_rows, 0)
                self.assertEqual(
                    sum(
                        len(batch.persistence_plan.price_observations)
                        for batch in result.batch_results
                    ),
                    2,
                )
        finally:
            if old_value is None:
                os.environ.pop(TESCO_FEATURE_FLAG, None)
            else:
                os.environ[TESCO_FEATURE_FLAG] = old_value

    def test_batches_allowlisted_asda_targets_with_asda_provider(self) -> None:
        old_value = os.environ.get(ASDA_FEATURE_FLAG)
        os.environ[ASDA_FEATURE_FLAG] = "1"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                seed_path = Path(tmpdir) / "supplier_targets.json"
                seed_path.write_text(
                    json.dumps(
                        {
                            "targets": [
                                {
                                    "retailer": "Asda",
                                    "target_name": "Asda own-brand corn flakes 500g",
                                    "target_url": "https://groceries.asda.com/product/cereal/100038316",
                                    "external_product_id": "100038316",
                                    "group_slug": "own_brand_cornflakes_standard",
                                    "postcode_context": "MVP default region",
                                    "is_active": True,
                                },
                            ],
                        },
                    ),
                    encoding="utf-8",
                )
                connection = FakeConnection()

                result = run_supplier_batch_persistence(
                    seed_path,
                    snapshot_root=Path(tmpdir) / "snapshots",
                    connection=connection,
                    enabled=True,
                    retailers={"asda"},
                    asda_provider_factory=FixtureAsdaProvider,
                )

                self.assertEqual(result.target_count, 1)
                self.assertEqual(result.collected_count, 1)
                self.assertEqual(result.failed_or_skipped_count, 0)
                batch = result.batch_results[0]
                self.assertEqual(batch.ingestion_result.status, "succeeded")
                self.assertEqual(len(batch.persistence_plan.raw_product_snapshots), 1)
                self.assertEqual(len(batch.persistence_plan.price_observations), 1)
                self.assertEqual(batch.persistence_plan.ingestion_job_targets[0]["status"], "succeeded")
                self.assertEqual(connection.commits, 1)
        finally:
            if old_value is None:
                os.environ.pop(ASDA_FEATURE_FLAG, None)
            else:
                os.environ[ASDA_FEATURE_FLAG] = old_value

    def test_stages_unsupported_supplier_targets_as_skipped_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            seed_path = Path(tmpdir) / "supplier_targets.json"
            seed_path.write_text(
                json.dumps(
                    {
                        "targets": [
                            {
                                "retailer": "Morrisons",
                                "target_name": "Morrisons own-brand corn flakes 500g",
                                "target_url": "https://groceries.morrisons.com/products/100038316",
                                "external_product_id": "100038316",
                                "group_slug": "own_brand_cornflakes_standard",
                                "postcode_context": "MVP default region",
                                "is_active": True,
                            },
                        ],
                    },
                ),
                encoding="utf-8",
            )
            connection = FakeConnection()

            result = run_supplier_batch_persistence(
                seed_path,
                snapshot_root=Path(tmpdir) / "snapshots",
                connection=connection,
                retailers={"morrisons"},
            )

            self.assertEqual(result.target_count, 1)
            self.assertEqual(result.collected_count, 0)
            self.assertEqual(result.failed_or_skipped_count, 1)
            self.assertEqual(len(result.batch_results), 1)
            batch = result.batch_results[0]
            self.assertEqual(batch.ingestion_result.status, "failed")
            self.assertEqual(batch.persistence_plan.ingestion_job_targets[0]["status"], "skipped")
            self.assertEqual(
                batch.persistence_plan.ingestion_job_targets[0]["error_code"],
                "unsupported_retailer",
            )
            self.assertEqual(len(batch.persistence_plan.raw_product_snapshots), 0)
            self.assertEqual(len(batch.persistence_plan.price_observations), 0)
            self.assertEqual(connection.commits, 1)

    def test_cli_uses_batch_process_and_closes_connection(self) -> None:
        old_value = os.environ.get(TESCO_FEATURE_FLAG)
        os.environ[TESCO_FEATURE_FLAG] = "1"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                connection = FakeConnection()
                with patch(
                    "basketguard_ingestion.supplier_batch.open_postgres_connection",
                    return_value=connection,
                ), patch("sys.stdout", new_callable=io.StringIO) as stdout:
                    exit_code = main(
                        [
                            "--allowlist-seed",
                            str(TARGET_SEED),
                            "--snapshot-root",
                            tmpdir,
                            "--database-url",
                            "postgresql://example.test/basketguard",
                            "--retailer",
                            "Tesco",
                            "--batch-size",
                            "2",
                            "--live",
                        ],
                        provider_factory=FixtureTescoProvider,
                    )

                self.assertEqual(exit_code, 0)
                self.assertTrue(connection.closed)
                self.assertEqual(connection.commits, 1)
                self.assertIn("targets=2", stdout.getvalue())
                self.assertIn("collected=2", stdout.getvalue())
        finally:
            if old_value is None:
                os.environ.pop(TESCO_FEATURE_FLAG, None)
            else:
                os.environ[TESCO_FEATURE_FLAG] = old_value


if __name__ == "__main__":
    unittest.main()
