from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .contracts import CollectionTarget, IngestionJobResult
from .db_mapping import IngestionPersistencePlan, build_ingestion_persistence_plan
from .db_repository import Connection, IngestionPlanRepository, SavePlanResult
from .seed_loader import load_collection_targets
from .tesco_provider import TescoIngestionProvider, TescoScraperConfig


ProviderFactory = Callable[[TescoScraperConfig], TescoIngestionProvider]


@dataclass(frozen=True)
class CollectionPipelineResult:
    targets: list[CollectionTarget]
    ingestion_result: IngestionJobResult
    persistence_plan: IngestionPersistencePlan
    save_result: SavePlanResult | None = None


def run_tesco_allowlisted_collection(
    seed_path: str | Path,
    *,
    enabled: bool = False,
    snapshot_root: str | Path | None = None,
    connection: Connection | None = None,
    provider_factory: ProviderFactory = TescoIngestionProvider,
) -> CollectionPipelineResult:
    targets = [
        target
        for target in load_collection_targets(seed_path)
        if target.is_active and target.retailer.lower() == "tesco" and target.target_url
    ]
    config = TescoScraperConfig(
        allowlisted_urls=tuple(target.target_url or "" for target in targets),
        enabled=enabled,
        postcode_context=_shared_postcode_context(targets),
        snapshot_root=Path(snapshot_root) if snapshot_root is not None else None,
    )
    ingestion_result = provider_factory(config).collect()
    persistence_plan = build_ingestion_persistence_plan(
        ingestion_result,
        collection_targets=targets,
    )
    save_result = None
    if connection is not None:
        save_result = IngestionPlanRepository(connection).save_plan(persistence_plan)

    return CollectionPipelineResult(
        targets=targets,
        ingestion_result=ingestion_result,
        persistence_plan=persistence_plan,
        save_result=save_result,
    )


def _shared_postcode_context(targets: list[CollectionTarget]) -> str | None:
    contexts = {target.postcode_context for target in targets if target.postcode_context}
    if len(contexts) == 1:
        return contexts.pop()
    return None
