from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))

from basketguard_ingestion import CollectionTargetSeedError, load_collection_targets  # noqa: E402


FIXTURE_PATH = ROOT / "services" / "ingestion" / "fixtures" / "mvp_collection_targets.json"


class CollectionTargetSeedTests(unittest.TestCase):
    def test_loads_mvp_collection_targets(self) -> None:
        targets = load_collection_targets(FIXTURE_PATH)

        self.assertEqual(len(targets), 2)
        self.assertEqual(targets[0].retailer, "Tesco")
        self.assertEqual(targets[0].external_product_id, "254879001")
        self.assertEqual(
            targets[0].group_slug,
            "own_brand_chopped_tomatoes_standard_400g",
        )
        self.assertEqual(targets[0].collection_frequency, "daily")
        self.assertEqual(targets[0].priority, 90)
        self.assertTrue(targets[0].is_active)

    def test_rejects_targets_without_locator(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            seed_path = Path(tmpdir) / "bad_targets.json"
            seed_path.write_text(
                json.dumps(
                    {
                        "targets": [
                            {
                                "retailer": "Tesco",
                                "target_name": "No locator",
                            },
                        ],
                    },
                ),
                encoding="utf-8",
            )

            with self.assertRaises(CollectionTargetSeedError):
                load_collection_targets(seed_path)

    def test_rejects_invalid_priority(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            seed_path = Path(tmpdir) / "bad_targets.json"
            seed_path.write_text(
                json.dumps(
                    {
                        "targets": [
                            {
                                "retailer": "Tesco",
                                "target_name": "Bad priority",
                                "target_url": "https://example.test/product",
                                "priority": 101,
                            },
                        ],
                    },
                ),
                encoding="utf-8",
            )

            with self.assertRaises(CollectionTargetSeedError):
                load_collection_targets(seed_path)


if __name__ == "__main__":
    unittest.main()
