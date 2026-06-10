from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))

from basketguard_ingestion import (  # noqa: E402
    CollectionAttempt,
    IngestionJobResult,
    TESCO_FEATURE_FLAG,
    TescoIngestionProvider,
    open_postgres_connection,
    run_allowlisted_product_url_persistence,
)


RUN_POSTGRES_INTEGRATION = "BASKETGUARD_RUN_POSTGRES_INTEGRATION"
DATABASE_URL_ENV = "BASKETGUARD_DATABASE_URL"
FIXTURE_DIR = ROOT / "services" / "ingestion" / "fixtures"
TARGET_SEED = FIXTURE_DIR / "mvp_collection_targets.json"
TOMATO_URL = "https://www.tesco.com/groceries/en-GB/products/254879001"
FIXED_COLLECTED_AT = "2026-06-10T08:00:00Z"


class FixedTescoProvider(TescoIngestionProvider):
    def collect(self) -> IngestionJobResult:
        html = (FIXTURE_DIR / "tesco_chopped_tomatoes.html").read_text(encoding="utf-8")
        url = self.config.allowlisted_urls[0]
        raw_snapshot, parsed_product, price_observation = self.parser.parse(
            html=html,
            url=url,
            collected_at=FIXED_COLLECTED_AT,
            postcode_context=self.config.postcode_context,
        )
        raw_snapshot = self._persist_snapshot(raw_snapshot, html)
        return IngestionJobResult(
            provider_name=self.provider_name,
            job_type="tesco_allowlisted_product_collection",
            status="succeeded",
            retailer="Tesco",
            target_count=1,
            collected_count=1,
            parser_error_count=0,
            missing_price_count=0,
            raw_snapshots=[raw_snapshot],
            parsed_products=[parsed_product],
            price_observations=[price_observation],
            collection_attempts=[
                CollectionAttempt(
                    retailer="Tesco",
                    target_url=url,
                    external_product_id=raw_snapshot.external_product_id,
                    status="succeeded",
                    attempted_at=FIXED_COLLECTED_AT,
                    raw_snapshot_external_product_id=raw_snapshot.external_product_id,
                ),
            ],
            notes="Deterministic Postgres integration fixture; no network request made.",
        )


@unittest.skipUnless(
    os.environ.get(RUN_POSTGRES_INTEGRATION) == "1",
    f"set {RUN_POSTGRES_INTEGRATION}=1 to run live Postgres integration tests",
)
class PostgresIntegrationTests(unittest.TestCase):
    def test_single_product_persistence_is_ordered_and_idempotent(self) -> None:
        database_url = os.environ.get(DATABASE_URL_ENV) or os.environ.get("DATABASE_URL")
        if not database_url:
            self.skipTest(f"set {DATABASE_URL_ENV} or DATABASE_URL for Postgres integration")

        old_flag = os.environ.get(TESCO_FEATURE_FLAG)
        os.environ[TESCO_FEATURE_FLAG] = "1"
        connection = open_postgres_connection(database_url)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                first = run_allowlisted_product_url_persistence(
                    product_url=TOMATO_URL,
                    allowlist_seed_path=TARGET_SEED,
                    snapshot_root=tmpdir,
                    connection=connection,
                    enabled=True,
                    provider_factory=FixedTescoProvider,
                )
                second = run_allowlisted_product_url_persistence(
                    product_url=TOMATO_URL,
                    allowlist_seed_path=TARGET_SEED,
                    snapshot_root=tmpdir,
                    connection=connection,
                    enabled=True,
                    provider_factory=FixedTescoProvider,
                )

                self.assertEqual(first.persistence_plan, second.persistence_plan)
                self.assertEqual(first.save_result.total_rows, second.save_result.total_rows)
                self.assertEqual(len(first.persistence_plan.price_observations), 1)
                self.assertEqual(len(first.persistence_plan.ingestion_job_targets), 1)

                self._assert_plan_rows_exist_once(connection, first.persistence_plan)
                self._assert_relationships_persisted(connection, first.persistence_plan)
        finally:
            close = getattr(connection, "close", None)
            if callable(close):
                close()
            if old_flag is None:
                os.environ.pop(TESCO_FEATURE_FLAG, None)
            else:
                os.environ[TESCO_FEATURE_FLAG] = old_flag

    def _assert_plan_rows_exist_once(self, connection, plan) -> None:
        for table_name, rows in _plan_table_rows(plan):
            for row in rows:
                self.assertEqual(
                    _count_id(connection, table_name, row["id"]),
                    1,
                    f"{table_name}.{row['id']} should exist exactly once after idempotent re-run",
                )

    def _assert_relationships_persisted(self, connection, plan) -> None:
        product_id = plan.products[0]["id"]
        snapshot_id = plan.raw_product_snapshots[0]["id"]
        target_id = plan.collection_targets[0]["id"]
        job_id = plan.ingestion_jobs[0]["id"]

        price_row = _fetch_one(
            connection,
            """
            SELECT product_id::text, raw_snapshot_id::text
            FROM price_observations
            WHERE id = %s
            """,
            (plan.price_observations[0]["id"],),
        )
        self.assertEqual(price_row, (product_id, snapshot_id))

        job_target_row = _fetch_one(
            connection,
            """
            SELECT ingestion_job_id::text, collection_target_id::text, raw_snapshot_id::text, status
            FROM ingestion_job_targets
            WHERE id = %s
            """,
            (plan.ingestion_job_targets[0]["id"],),
        )
        self.assertEqual(job_target_row, (job_id, target_id, snapshot_id, "succeeded"))


def _plan_table_rows(plan):
    yield "retailers", plan.retailers
    yield "equivalence_groups", plan.equivalence_groups
    yield "collection_targets", plan.collection_targets
    yield "ingestion_jobs", plan.ingestion_jobs
    yield "raw_product_snapshots", plan.raw_product_snapshots
    yield "products", plan.products
    yield "price_observations", plan.price_observations
    yield "ingestion_job_targets", plan.ingestion_job_targets


def _count_id(connection, table_name: str, row_id: str) -> int:
    row = _fetch_one(connection, f'SELECT COUNT(*) FROM "{table_name}" WHERE id = %s', (row_id,))
    return int(row[0])


def _fetch_one(connection, sql: str, params: tuple[str, ...]):
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params)
        return cursor.fetchone()
    finally:
        cursor.close()


if __name__ == "__main__":
    unittest.main()
