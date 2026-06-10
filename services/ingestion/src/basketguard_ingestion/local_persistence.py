from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .contracts import CollectionTarget
from .db_repository import Connection
from .pipeline import CollectionPipelineResult, ProviderFactory
from .postgres import DATABASE_URL_ENV, PostgresConnectionError, open_postgres_connection
from .seed_loader import load_collection_targets
from .tesco_provider import TESCO_FEATURE_FLAG, TescoIngestionProvider, TescoScraperConfig
from .db_mapping import build_ingestion_persistence_plan
from .db_repository import IngestionPlanRepository


DEFAULT_ALLOWLIST_SEED = Path("services/ingestion/fixtures/mvp_collection_targets.json")
DEFAULT_SNAPSHOT_ROOT = Path("artifacts/raw_snapshots")


class AllowlistedProductUrlError(ValueError):
    pass


def run_allowlisted_product_url_persistence(
    product_url: str,
    allowlist_seed_path: str | Path = DEFAULT_ALLOWLIST_SEED,
    *,
    snapshot_root: str | Path = DEFAULT_SNAPSHOT_ROOT,
    connection: Connection,
    enabled: bool = True,
    provider_factory: ProviderFactory = TescoIngestionProvider,
) -> CollectionPipelineResult:
    target = _select_allowlisted_tesco_target(product_url, allowlist_seed_path)
    target = replace(target, target_url=_canonical_product_url(target.target_url or product_url))

    config = TescoScraperConfig(
        allowlisted_urls=(target.target_url or product_url,),
        enabled=enabled,
        postcode_context=target.postcode_context,
        snapshot_root=Path(snapshot_root),
    )
    ingestion_result = provider_factory(config).collect()
    persistence_plan = build_ingestion_persistence_plan(
        ingestion_result,
        collection_targets=[target],
    )
    save_result = IngestionPlanRepository(connection).save_plan(persistence_plan)

    return CollectionPipelineResult(
        targets=[target],
        ingestion_result=ingestion_result,
        persistence_plan=persistence_plan,
        save_result=save_result,
    )


def main(
    argv: list[str] | None = None,
    *,
    provider_factory: ProviderFactory = TescoIngestionProvider,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        connection = open_postgres_connection(args.database_url)
    except PostgresConnectionError as error:
        print(f"basketguard ingestion: {error}", file=sys.stderr)
        return 2

    try:
        result = run_allowlisted_product_url_persistence(
            product_url=args.url,
            allowlist_seed_path=args.allowlist_seed,
            snapshot_root=args.snapshot_root,
            connection=connection,
            enabled=args.live,
            provider_factory=provider_factory,
        )
    except AllowlistedProductUrlError as error:
        print(f"basketguard ingestion: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"basketguard ingestion failed: {error}", file=sys.stderr)
        return 1
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            close()

    _print_summary(result)
    if result.ingestion_result.status not in {"succeeded", "partial"}:
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch one allowlisted Tesco product URL and persist the parsed observation.",
    )
    parser.add_argument("--url", required=True, help="Allowlisted Tesco product URL to fetch.")
    parser.add_argument(
        "--allowlist-seed",
        default=DEFAULT_ALLOWLIST_SEED,
        type=Path,
        help="JSON seed containing allowed collection targets.",
    )
    parser.add_argument(
        "--snapshot-root",
        default=DEFAULT_SNAPSHOT_ROOT,
        type=Path,
        help="Directory where raw HTML snapshots and metadata are written.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help=f"PostgreSQL connection URL. Defaults to {DATABASE_URL_ENV} or DATABASE_URL.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=f"Enable live fetching. {TESCO_FEATURE_FLAG}=1 must also be set.",
    )
    return parser


def _select_allowlisted_tesco_target(
    product_url: str,
    allowlist_seed_path: str | Path,
) -> CollectionTarget:
    requested_url = _canonical_product_url(product_url)
    for target in load_collection_targets(allowlist_seed_path):
        if not target.is_active or target.retailer.lower() != "tesco" or not target.target_url:
            continue
        if _canonical_product_url(target.target_url) == requested_url:
            return target

    raise AllowlistedProductUrlError(
        f"URL is not an active Tesco target in {allowlist_seed_path}: {product_url}",
    )


def _canonical_product_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or hostname not in {"www.tesco.com", "tesco.com"}:
        raise AllowlistedProductUrlError(f"Only HTTPS Tesco product URLs are supported: {value}")
    path = parsed.path.rstrip("/")
    if "/products/" not in path:
        raise AllowlistedProductUrlError(f"URL is not a Tesco product page: {value}")
    netloc = parsed.netloc.lower()
    return urlunsplit(("https", netloc, path, "", ""))


def _print_summary(result: CollectionPipelineResult) -> None:
    save_total = result.save_result.total_rows if result.save_result is not None else 0
    print(
        "basketguard ingestion: "
        f"status={result.ingestion_result.status} "
        f"targets={result.ingestion_result.target_count} "
        f"collected={result.ingestion_result.collected_count} "
        f"snapshots={len(result.persistence_plan.raw_product_snapshots)} "
        f"price_observations={len(result.persistence_plan.price_observations)} "
        f"saved_rows={save_total}",
    )


if __name__ == "__main__":
    raise SystemExit(main())
