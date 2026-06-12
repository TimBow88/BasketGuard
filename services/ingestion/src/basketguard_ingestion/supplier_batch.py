from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterable

from .contracts import CollectionAttempt, CollectionTarget, IngestionJobResult
from .asda_provider import AsdaIngestionProvider, AsdaScraperConfig
from .db_repository import Connection, IngestionPlanRepository
from .local_persistence import DEFAULT_ALLOWLIST_SEED, DEFAULT_SNAPSHOT_ROOT
from .pipeline import CollectionPipelineResult, ProviderFactory
from .postgres import DATABASE_URL_ENV, PostgresConnectionError, open_postgres_connection
from .sainsburys_provider import SainsburysIngestionProvider, SainsburysScraperConfig
from .seed_loader import load_collection_targets
from .tesco_provider import TESCO_FEATURE_FLAG, TescoIngestionProvider, TescoScraperConfig
from .db_mapping import build_ingestion_persistence_plan


SUPPORTED_RETAILERS = {"asda", "tesco", "sainsbury's", "sainsburys"}
DEFAULT_BATCH_SIZE = 100
AsdaProviderFactory = Callable[[AsdaScraperConfig], AsdaIngestionProvider]
SainsburysProviderFactory = Callable[[SainsburysScraperConfig], SainsburysIngestionProvider]


@dataclass(frozen=True)
class SupplierBatchRunResult:
    batch_results: list[CollectionPipelineResult]

    @property
    def target_count(self) -> int:
        return sum(result.ingestion_result.target_count for result in self.batch_results)

    @property
    def collected_count(self) -> int:
        return sum(result.ingestion_result.collected_count for result in self.batch_results)

    @property
    def failed_or_skipped_count(self) -> int:
        return sum(
            len(
                [
                    attempt
                    for attempt in result.ingestion_result.collection_attempts
                    if attempt.status != "succeeded"
                ],
            )
            for result in self.batch_results
        )

    @property
    def saved_rows(self) -> int:
        return sum(
            result.save_result.total_rows
            for result in self.batch_results
            if result.save_result is not None
        )


def run_supplier_batch_persistence(
    seed_path: str | Path = DEFAULT_ALLOWLIST_SEED,
    *,
    snapshot_root: str | Path = DEFAULT_SNAPSHOT_ROOT,
    connection: Connection,
    enabled: bool = False,
    retailers: set[str] | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_targets: int | None = None,
    provider_factory: ProviderFactory = TescoIngestionProvider,
    asda_provider_factory: AsdaProviderFactory = AsdaIngestionProvider,
    sainsburys_provider_factory: SainsburysProviderFactory = SainsburysIngestionProvider,
) -> SupplierBatchRunResult:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    targets = _selected_targets(seed_path, retailers=retailers, max_targets=max_targets)
    batch_results: list[CollectionPipelineResult] = []

    for retailer, retailer_targets in _targets_by_retailer(targets).items():
        for batch_targets in _chunks(retailer_targets, batch_size):
            if retailer == "tesco":
                result = _run_tesco_batch(
                    batch_targets,
                    snapshot_root=snapshot_root,
                    enabled=enabled,
                    connection=connection,
                    provider_factory=provider_factory,
                )
            elif retailer == "asda":
                result = _run_asda_batch(
                    batch_targets,
                    snapshot_root=snapshot_root,
                    enabled=enabled,
                    connection=connection,
                    provider_factory=asda_provider_factory,
                )
            elif retailer in ("sainsbury's", "sainsburys"):
                result = _run_sainsburys_batch(
                    batch_targets,
                    snapshot_root=snapshot_root,
                    enabled=enabled,
                    connection=connection,
                    provider_factory=sainsburys_provider_factory,
                )
            else:
                result = _run_unsupported_retailer_batch(
                    retailer,
                    batch_targets,
                    connection=connection,
                )
            batch_results.append(result)

    return SupplierBatchRunResult(batch_results=batch_results)


def main(
    argv: list[str] | None = None,
    *,
    provider_factory: ProviderFactory = TescoIngestionProvider,
    asda_provider_factory: AsdaProviderFactory = AsdaIngestionProvider,
    sainsburys_provider_factory: SainsburysProviderFactory = SainsburysIngestionProvider,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    selected_retailers = {retailer.lower() for retailer in args.retailer} or None
    try:
        connection = open_postgres_connection(args.database_url)
    except PostgresConnectionError as error:
        print(f"basketguard supplier batch: {error}", file=sys.stderr)
        return 2

    try:
        result = run_supplier_batch_persistence(
            seed_path=args.allowlist_seed,
            snapshot_root=args.snapshot_root,
            connection=connection,
            enabled=args.live,
            retailers=selected_retailers,
            batch_size=args.batch_size,
            max_targets=args.max_targets,
            provider_factory=provider_factory,
            asda_provider_factory=asda_provider_factory,
            sainsburys_provider_factory=sainsburys_provider_factory,
        )
    except Exception as error:
        print(f"basketguard supplier batch failed: {error}", file=sys.stderr)
        return 1
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            close()

    print(
        "basketguard supplier batch: "
        f"batches={len(result.batch_results)} "
        f"targets={result.target_count} "
        f"collected={result.collected_count} "
        f"failed_or_skipped={result.failed_or_skipped_count} "
        f"saved_rows={result.saved_rows}",
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persist a large allowlisted supplier target seed in controlled batches.",
    )
    parser.add_argument(
        "--allowlist-seed",
        default=DEFAULT_ALLOWLIST_SEED,
        type=Path,
        help="JSON seed containing explicit supplier product targets.",
    )
    parser.add_argument(
        "--snapshot-root",
        default=DEFAULT_SNAPSHOT_ROOT,
        type=Path,
        help="Directory where successful raw HTML snapshots are written.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help=f"PostgreSQL connection URL. Defaults to {DATABASE_URL_ENV} or DATABASE_URL.",
    )
    parser.add_argument(
        "--retailer",
        action="append",
        default=[],
        help="Retailer name to include. Repeat for multiple retailers. Defaults to all seed targets.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Number of product targets per saved ingestion batch.",
    )
    parser.add_argument(
        "--max-targets",
        type=int,
        default=None,
        help="Optional safety limit for one run.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=f"Enable live Tesco fetching. {TESCO_FEATURE_FLAG}=1 must also be set.",
    )
    return parser


def _selected_targets(
    seed_path: str | Path,
    *,
    retailers: set[str] | None,
    max_targets: int | None,
) -> list[CollectionTarget]:
    targets = [
        target
        for target in load_collection_targets(seed_path)
        if target.is_active and target.target_url
    ]
    if retailers is not None:
        targets = [target for target in targets if target.retailer.lower() in retailers]
    if max_targets is not None:
        if max_targets < 1:
            raise ValueError("max_targets must be at least 1 when provided")
        targets = targets[:max_targets]
    return targets


def _targets_by_retailer(targets: Iterable[CollectionTarget]) -> dict[str, list[CollectionTarget]]:
    grouped: dict[str, list[CollectionTarget]] = {}
    for target in targets:
        grouped.setdefault(target.retailer.lower(), []).append(target)
    return grouped


def _chunks(targets: list[CollectionTarget], batch_size: int) -> Iterable[list[CollectionTarget]]:
    for index in range(0, len(targets), batch_size):
        yield targets[index : index + batch_size]


def _run_tesco_batch(
    targets: list[CollectionTarget],
    *,
    snapshot_root: str | Path,
    enabled: bool,
    connection: Connection,
    provider_factory: ProviderFactory,
) -> CollectionPipelineResult:
    config = TescoScraperConfig(
        allowlisted_urls=tuple(target.target_url or "" for target in targets),
        enabled=enabled,
        postcode_context=_shared_postcode_context(targets),
        snapshot_root=Path(snapshot_root),
    )
    ingestion_result = provider_factory(config).collect()
    persistence_plan = build_ingestion_persistence_plan(
        ingestion_result,
        collection_targets=targets,
    )
    save_result = IngestionPlanRepository(connection).save_plan(persistence_plan)
    return CollectionPipelineResult(
        targets=targets,
        ingestion_result=ingestion_result,
        persistence_plan=persistence_plan,
        save_result=save_result,
    )


def _run_asda_batch(
    targets: list[CollectionTarget],
    *,
    snapshot_root: str | Path,
    enabled: bool,
    connection: Connection,
    provider_factory: AsdaProviderFactory,
) -> CollectionPipelineResult:
    config = AsdaScraperConfig(
        allowlisted_urls=tuple(target.target_url or "" for target in targets),
        enabled=enabled,
        postcode_context=_shared_postcode_context(targets),
        snapshot_root=Path(snapshot_root),
    )
    ingestion_result = provider_factory(config).collect()
    persistence_plan = build_ingestion_persistence_plan(
        ingestion_result,
        collection_targets=targets,
    )
    save_result = IngestionPlanRepository(connection).save_plan(persistence_plan)
    return CollectionPipelineResult(
        targets=targets,
        ingestion_result=ingestion_result,
        persistence_plan=persistence_plan,
        save_result=save_result,
    )


def _run_sainsburys_batch(
    targets: list[CollectionTarget],
    *,
    snapshot_root: str | Path,
    enabled: bool,
    connection: Connection,
    provider_factory: SainsburysProviderFactory,
) -> CollectionPipelineResult:
    config = SainsburysScraperConfig(
        allowlisted_urls=tuple(target.target_url or "" for target in targets),
        enabled=enabled,
        postcode_context=_shared_postcode_context(targets),
        snapshot_root=Path(snapshot_root),
    )
    ingestion_result = provider_factory(config).collect()
    persistence_plan = build_ingestion_persistence_plan(
        ingestion_result,
        collection_targets=targets,
    )
    save_result = IngestionPlanRepository(connection).save_plan(persistence_plan)
    return CollectionPipelineResult(
        targets=targets,
        ingestion_result=ingestion_result,
        persistence_plan=persistence_plan,
        save_result=save_result,
    )


def _run_unsupported_retailer_batch(
    retailer: str,
    targets: list[CollectionTarget],
    *,
    connection: Connection,
) -> CollectionPipelineResult:
    attempted_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    retailer_name = targets[0].retailer if targets else retailer.title()
    ingestion_result = IngestionJobResult(
        provider_name=retailer,
        job_type=f"{retailer}_allowlisted_product_collection",
        status="failed",
        retailer=retailer_name,
        target_count=len(targets),
        collected_count=0,
        parser_error_count=0,
        missing_price_count=0,
        collection_attempts=[
            CollectionAttempt(
                retailer=target.retailer,
                target_url=target.target_url,
                external_product_id=target.external_product_id,
                status="skipped",
                attempted_at=attempted_at,
                error_code="unsupported_retailer",
                error_message=(
                    f"{target.retailer} targets are staged but no provider/parser is implemented yet."
                ),
            )
            for target in targets
        ],
        notes="Targets were staged from the allowlist but skipped because the retailer is unsupported.",
    )
    persistence_plan = build_ingestion_persistence_plan(
        ingestion_result,
        collection_targets=targets,
    )
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


if __name__ == "__main__":
    raise SystemExit(main())
