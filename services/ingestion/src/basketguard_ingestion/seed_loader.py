from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import CollectionFrequency, CollectionTarget


ALLOWED_FREQUENCIES: set[CollectionFrequency] = {
    "daily",
    "twice_weekly",
    "weekly",
    "monthly",
    "manual",
}


class CollectionTargetSeedError(ValueError):
    pass


def load_collection_targets(seed_path: str | Path) -> list[CollectionTarget]:
    payload = json.loads(Path(seed_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CollectionTargetSeedError("Collection target seed must be a JSON object")

    targets = payload.get("targets")
    if not isinstance(targets, list):
        raise CollectionTargetSeedError("Collection target seed must contain a targets list")

    return [_target_from_payload(item, index) for index, item in enumerate(targets, start=1)]


def _target_from_payload(item: Any, index: int) -> CollectionTarget:
    if not isinstance(item, dict):
        raise CollectionTargetSeedError(f"Target {index} must be an object")

    retailer = _required_text(item, "retailer", index)
    target_name = _required_text(item, "target_name", index)
    target_url = _optional_text(item, "target_url", index)
    external_product_id = _optional_text(item, "external_product_id", index)
    group_slug = _optional_text(item, "group_slug", index)
    postcode_context = _optional_text(item, "postcode_context", index)
    notes = _optional_text(item, "notes", index)

    if not target_url and not external_product_id and not group_slug:
        raise CollectionTargetSeedError(
            f"Target {index} must include target_url, external_product_id or group_slug",
        )

    frequency = item.get("collection_frequency", "daily")
    if frequency not in ALLOWED_FREQUENCIES:
        raise CollectionTargetSeedError(f"Target {index} has invalid collection_frequency")

    priority = item.get("priority", 50)
    if not isinstance(priority, int) or not 0 <= priority <= 100:
        raise CollectionTargetSeedError(f"Target {index} priority must be an integer from 0 to 100")

    is_active = item.get("is_active", True)
    if not isinstance(is_active, bool):
        raise CollectionTargetSeedError(f"Target {index} is_active must be true or false")

    return CollectionTarget(
        retailer=retailer,
        target_name=target_name,
        target_url=target_url,
        external_product_id=external_product_id,
        group_slug=group_slug,
        postcode_context=postcode_context,
        collection_frequency=frequency,
        priority=priority,
        is_active=is_active,
        notes=notes,
    )


def _required_text(item: dict[str, Any], key: str, index: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CollectionTargetSeedError(f"Target {index} missing required text field {key}")
    return value.strip()


def _optional_text(item: dict[str, Any], key: str, index: int) -> str | None:
    value = item.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CollectionTargetSeedError(f"Target {index} field {key} must be non-empty text")
    return value.strip()
