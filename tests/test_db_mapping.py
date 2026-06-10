from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))

from basketguard_ingestion import (  # noqa: E402
    TESCO_FEATURE_FLAG,
    TescoIngestionProvider,
    TescoScraperConfig,
    build_ingestion_persistence_plan,
    load_collection_targets,
)


FIXTURE_DIR = ROOT / "services" / "ingestion" / "fixtures"
TARGET_SEED = FIXTURE_DIR / "mvp_collection_targets.json"


class IngestionDbMappingTests(unittest.TestCase):
    def test_maps_tesco_collection_result_to_existing_schema_rows(self) -> None:
        old_value = os.environ.get(TESCO_FEATURE_FLAG)
        os.environ[TESCO_FEATURE_FLAG] = "1"
        html = (FIXTURE_DIR / "tesco_chopped_tomatoes.html").read_text(encoding="utf-8")
        targets = load_collection_targets(TARGET_SEED)
        tomato_target = [target for target in targets if target.external_product_id == "254879001"]

        class FixtureTescoProvider(TescoIngestionProvider):
            def _fetch(self, url: str) -> str:
                return html

        try:
            result = FixtureTescoProvider(
                TescoScraperConfig(
                    allowlisted_urls=(tomato_target[0].target_url or "",),
                    enabled=True,
                ),
            ).collect()
        finally:
            if old_value is None:
                os.environ.pop(TESCO_FEATURE_FLAG, None)
            else:
                os.environ[TESCO_FEATURE_FLAG] = old_value

        plan = build_ingestion_persistence_plan(result, collection_targets=tomato_target)

        self.assertEqual(len(plan.retailers), 1)
        self.assertEqual(plan.retailers[0]["slug"], "tesco")
        self.assertEqual(len(plan.equivalence_groups), 1)
        self.assertEqual(
            plan.equivalence_groups[0]["slug"],
            "own_brand_chopped_tomatoes_standard_400g",
        )
        self.assertEqual(len(plan.collection_targets), 1)
        self.assertEqual(len(plan.ingestion_jobs), 1)
        self.assertEqual(len(plan.ingestion_job_targets), 1)
        self.assertEqual(len(plan.raw_product_snapshots), 1)
        self.assertEqual(len(plan.products), 1)
        self.assertEqual(len(plan.price_observations), 1)

        self.assertEqual(
            plan.collection_targets[0]["retailer_id"],
            plan.retailers[0]["id"],
        )
        self.assertEqual(
            plan.raw_product_snapshots[0]["retailer_id"],
            plan.retailers[0]["id"],
        )
        self.assertEqual(
            plan.products[0]["retailer_id"],
            plan.retailers[0]["id"],
        )
        self.assertEqual(
            plan.price_observations[0]["product_id"],
            plan.products[0]["id"],
        )
        self.assertEqual(
            plan.price_observations[0]["raw_snapshot_id"],
            plan.raw_product_snapshots[0]["id"],
        )
        self.assertEqual(
            plan.ingestion_job_targets[0]["collection_target_id"],
            plan.collection_targets[0]["id"],
        )
        self.assertEqual(
            plan.ingestion_job_targets[0]["raw_snapshot_id"],
            plan.raw_product_snapshots[0]["id"],
        )

    def test_mapping_uses_stable_ids_for_same_input(self) -> None:
        old_value = os.environ.get(TESCO_FEATURE_FLAG)
        os.environ[TESCO_FEATURE_FLAG] = "1"
        html = (FIXTURE_DIR / "tesco_chopped_tomatoes.html").read_text(encoding="utf-8")
        target = [
            target
            for target in load_collection_targets(TARGET_SEED)
            if target.external_product_id == "254879001"
        ][0]

        class FixtureTescoProvider(TescoIngestionProvider):
            def _fetch(self, url: str) -> str:
                return html

        try:
            result = FixtureTescoProvider(
                TescoScraperConfig(
                    allowlisted_urls=(target.target_url or "",),
                    enabled=True,
                ),
            ).collect()
        finally:
            if old_value is None:
                os.environ.pop(TESCO_FEATURE_FLAG, None)
            else:
                os.environ[TESCO_FEATURE_FLAG] = old_value

        first_plan = build_ingestion_persistence_plan(result, collection_targets=[target])
        second_plan = build_ingestion_persistence_plan(result, collection_targets=[target])

        self.assertEqual(first_plan.products[0]["id"], second_plan.products[0]["id"])
        self.assertEqual(
            first_plan.raw_product_snapshots[0]["id"],
            second_plan.raw_product_snapshots[0]["id"],
        )

    def test_maps_failed_attempt_to_ingestion_job_target_error(self) -> None:
        old_value = os.environ.get(TESCO_FEATURE_FLAG)
        os.environ[TESCO_FEATURE_FLAG] = "1"
        target = [
            target
            for target in load_collection_targets(TARGET_SEED)
            if target.external_product_id == "254879001"
        ][0]

        class FailingTescoProvider(TescoIngestionProvider):
            def _fetch(self, url: str) -> str:
                raise URLError("network unavailable")

        try:
            result = FailingTescoProvider(
                TescoScraperConfig(
                    allowlisted_urls=(target.target_url or "",),
                    enabled=True,
                ),
            ).collect()
        finally:
            if old_value is None:
                os.environ.pop(TESCO_FEATURE_FLAG, None)
            else:
                os.environ[TESCO_FEATURE_FLAG] = old_value

        plan = build_ingestion_persistence_plan(result, collection_targets=[target])

        self.assertEqual(len(plan.raw_product_snapshots), 0)
        self.assertEqual(len(plan.price_observations), 0)
        self.assertEqual(len(plan.ingestion_job_targets), 1)
        self.assertEqual(plan.ingestion_job_targets[0]["status"], "failed")
        self.assertEqual(plan.ingestion_job_targets[0]["error_code"], "url_error")
        self.assertIn(
            "network unavailable",
            plan.ingestion_job_targets[0]["error_message"],
        )
        self.assertEqual(
            plan.ingestion_job_targets[0]["collection_target_id"],
            plan.collection_targets[0]["id"],
        )
        self.assertIsNone(plan.ingestion_job_targets[0]["raw_snapshot_id"])


if __name__ == "__main__":
    unittest.main()
