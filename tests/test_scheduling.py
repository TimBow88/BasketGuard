from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, UTC
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))

from basketguard_ingestion import (  # noqa: E402
    CollectionTarget,
    due_targets,
    is_due,
    target_key,
)


NOW = datetime(2026, 6, 17, 6, 0, 0, tzinfo=UTC)


def _target(**overrides) -> CollectionTarget:
    base = dict(
        retailer="Tesco",
        target_name="Cornflakes",
        target_url="https://www.tesco.com/p/1",
        collection_frequency="daily",
        is_active=True,
    )
    base.update(overrides)
    return CollectionTarget(**base)


class IsDueTests(unittest.TestCase):
    def test_never_collected_is_due(self) -> None:
        self.assertTrue(is_due(_target(), now=NOW, last_collected_at=None))

    def test_daily_due_after_a_day(self) -> None:
        self.assertTrue(is_due(_target(), now=NOW, last_collected_at=NOW - timedelta(days=1)))
        self.assertFalse(is_due(_target(), now=NOW, last_collected_at=NOW - timedelta(hours=12)))

    def test_weekly_respects_longer_interval(self) -> None:
        target = _target(collection_frequency="weekly")
        self.assertFalse(is_due(target, now=NOW, last_collected_at=NOW - timedelta(days=3)))
        self.assertTrue(is_due(target, now=NOW, last_collected_at=NOW - timedelta(days=8)))

    def test_inactive_never_due(self) -> None:
        self.assertFalse(is_due(_target(is_active=False), now=NOW, last_collected_at=None))

    def test_manual_never_auto_scheduled(self) -> None:
        target = _target(collection_frequency="manual")
        self.assertFalse(is_due(target, now=NOW, last_collected_at=None))


class DueTargetsTests(unittest.TestCase):
    def test_selects_only_due_targets(self) -> None:
        fresh = _target(target_url="https://t/fresh")
        stale = _target(target_url="https://t/stale")
        manual = _target(target_url="https://t/manual", collection_frequency="manual")

        selected = due_targets(
            [fresh, stale, manual],
            now=NOW,
            last_collected={
                target_key(fresh): NOW - timedelta(hours=2),
                target_key(stale): NOW - timedelta(days=2),
            },
        )

        urls = {target.target_url for target in selected}
        self.assertEqual(urls, {"https://t/stale"})


if __name__ == "__main__":
    unittest.main()
