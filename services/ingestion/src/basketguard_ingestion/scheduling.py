"""Collection cadence: decide which allowlisted targets are due for a run.

The roadmap requires "daily collection runs complete", but collection only ran
via manual commands. This is the scheduling decision layer: given each target's
``collection_frequency`` and when it was last collected, work out what is due
*now*. It is pure and time-injected, so a real scheduler (cron / APScheduler /
a worker) only has to call ``due_targets`` and run the result — the cadence
policy lives here and is unit-testable without waiting.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Mapping, Sequence

from .contracts import CollectionFrequency, CollectionTarget


# Minimum spacing between collections for each frequency. "twice_weekly" maps to
# roughly every 3 days; "manual" is never auto-scheduled.
FREQUENCY_INTERVALS: dict[CollectionFrequency, timedelta | None] = {
    "daily": timedelta(days=1),
    "twice_weekly": timedelta(days=3),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
    "manual": None,
}


def target_key(target: CollectionTarget) -> str:
    """Stable identity for a target's last-run bookkeeping."""

    return target.target_url or f"{target.retailer}:{target.external_product_id}"


def is_due(
    target: CollectionTarget,
    *,
    now: datetime,
    last_collected_at: datetime | None,
) -> bool:
    if not target.is_active:
        return False
    interval = FREQUENCY_INTERVALS.get(target.collection_frequency)
    if interval is None:  # manual / unknown frequency is never auto-scheduled
        return False
    if last_collected_at is None:
        return True
    return (now - last_collected_at) >= interval


def due_targets(
    targets: Sequence[CollectionTarget],
    *,
    now: datetime,
    last_collected: Mapping[str, datetime] | None = None,
) -> list[CollectionTarget]:
    """Return the active targets whose cadence makes them due at ``now``."""

    last_collected = last_collected or {}
    return [
        target
        for target in targets
        if is_due(
            target,
            now=now,
            last_collected_at=last_collected.get(target_key(target)),
        )
    ]
