from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))

from basketguard_ingestion import IngestionPersistencePlan, IngestionPlanRepository  # noqa: E402


class FakeCursor:
    def __init__(self, fail_after: int | None = None) -> None:
        self.executions: list[tuple[str, tuple[Any, ...]]] = []
        self.fail_after = fail_after
        self.closed = False

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        if self.fail_after is not None and len(self.executions) >= self.fail_after:
            raise RuntimeError("database write failed")
        self.executions.append((sql, params))

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, fail_after: int | None = None) -> None:
        self.cursor_instance = FakeCursor(fail_after=fail_after)
        self.committed = False
        self.rolled_back = False

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class IngestionPlanRepositoryTests(unittest.TestCase):
    def test_saves_plan_rows_in_dependency_order(self) -> None:
        plan = IngestionPersistencePlan(
            retailers=[{"id": "retailer-id", "name": "Tesco", "slug": "tesco"}],
            collection_targets=[
                {
                    "id": "target-id",
                    "retailer_id": "retailer-id",
                    "target_name": "Tomatoes",
                },
            ],
            ingestion_jobs=[{"id": "job-id", "job_type": "tesco", "status": "succeeded"}],
            raw_product_snapshots=[
                {
                    "id": "snapshot-id",
                    "retailer_id": "retailer-id",
                    "collection_status": "succeeded",
                },
            ],
            products=[
                {
                    "id": "product-id",
                    "retailer_id": "retailer-id",
                    "canonical_name": "Tesco Chopped Tomatoes",
                },
            ],
            price_observations=[
                {
                    "id": "price-id",
                    "product_id": "product-id",
                    "raw_snapshot_id": "snapshot-id",
                },
            ],
            ingestion_job_targets=[
                {
                    "id": "job-target-id",
                    "ingestion_job_id": "job-id",
                    "collection_target_id": "target-id",
                    "raw_snapshot_id": "snapshot-id",
                    "status": "succeeded",
                },
            ],
        )
        connection = FakeConnection()

        result = IngestionPlanRepository(connection).save_plan(plan)

        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertTrue(connection.cursor_instance.closed)
        self.assertEqual(result.total_rows, 7)
        self.assertEqual(
            [sql.split()[2].strip('"') for sql, _params in connection.cursor_instance.executions],
            [
                "retailers",
                "collection_targets",
                "ingestion_jobs",
                "raw_product_snapshots",
                "products",
                "price_observations",
                "ingestion_job_targets",
            ],
        )

    def test_uses_id_conflict_upserts_with_positional_params(self) -> None:
        plan = IngestionPersistencePlan(
            retailers=[{"id": "retailer-id", "name": "Tesco", "slug": "tesco"}],
        )
        connection = FakeConnection()

        IngestionPlanRepository(connection).save_plan(plan)

        sql, params = connection.cursor_instance.executions[0]
        self.assertIn('INSERT INTO "retailers"', sql)
        self.assertIn('ON CONFLICT (id) DO UPDATE SET', sql)
        self.assertIn('"name" = EXCLUDED."name"', sql)
        self.assertEqual(params, ("retailer-id", "Tesco", "tesco"))

    def test_rolls_back_and_closes_cursor_on_write_failure(self) -> None:
        plan = IngestionPersistencePlan(
            retailers=[{"id": "retailer-id", "name": "Tesco"}],
            ingestion_jobs=[{"id": "job-id", "job_type": "tesco"}],
        )
        connection = FakeConnection(fail_after=1)

        with self.assertRaises(RuntimeError):
            IngestionPlanRepository(connection).save_plan(plan)

        self.assertFalse(connection.committed)
        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.cursor_instance.closed)


if __name__ == "__main__":
    unittest.main()
