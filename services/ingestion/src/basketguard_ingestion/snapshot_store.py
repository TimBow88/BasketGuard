from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .contracts import RawProductSnapshot


@dataclass(frozen=True)
class SnapshotArtifact:
    raw_payload_location: str
    metadata_location: str
    content_hash: str


class SnapshotArtifactWriter:
    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)

    def write_html(self, snapshot: RawProductSnapshot, html: str) -> SnapshotArtifact:
        content_hash = "sha256:" + hashlib.sha256(html.encode("utf-8")).hexdigest()
        snapshot_dir = self._snapshot_dir(snapshot, content_hash)
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        raw_path = snapshot_dir / "raw.html"
        metadata_path = snapshot_dir / "metadata.json"

        raw_path.write_text(html, encoding="utf-8")
        metadata_path.write_text(
            json.dumps(
                {
                    "snapshot": asdict(snapshot),
                    "content_hash": content_hash,
                    "raw_payload_location": str(raw_path),
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        return SnapshotArtifact(
            raw_payload_location=str(raw_path),
            metadata_location=str(metadata_path),
            content_hash=content_hash,
        )

    def _snapshot_dir(self, snapshot: RawProductSnapshot, content_hash: str) -> Path:
        collected_at = _parse_timestamp(snapshot.collected_at)
        retailer = _safe_path_part(snapshot.retailer)
        product_id = _safe_path_part(snapshot.external_product_id or "unknown-product")
        hash_part = content_hash.split(":", 1)[1][:12]

        return (
            self.root_dir
            / retailer
            / f"{collected_at.year:04d}"
            / f"{collected_at.month:02d}"
            / f"{collected_at.day:02d}"
            / product_id
            / hash_part
        )


def _parse_timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return datetime.now(UTC)


def _safe_path_part(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-") or "unknown"
