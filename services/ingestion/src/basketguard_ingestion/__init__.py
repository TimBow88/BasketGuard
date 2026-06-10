from .contracts import (
    CollectionAttempt,
    CollectionTarget,
    ExtractedProduct,
    IngestionJobResult,
    ParsedProduct,
    PriceObservation,
    ProductExtractor,
    RawProductSnapshot,
)
from .asda_provider import (
    ASDA_FEATURE_FLAG,
    AsdaIngestionProvider,
    AsdaParseError,
    AsdaProductPageParser,
    AsdaScraperConfig,
)
from .db_mapping import IngestionPersistencePlan, build_ingestion_persistence_plan
from .db_repository import IngestionPlanRepository, SavePlanResult
from .group_matching import (
    GroupMatchingSummary,
    ProductGroupMatch,
    candidate_from_parsed_product,
    match_parsed_products,
)
from .fetcher import (
    FetchError,
    FetchHttpStatusError,
    FetchResponse,
    FetchTimeoutError,
    FetchUrlError,
    UrllibSupplierFetcher,
)
from .mock_provider import FixtureIngestionProvider
from .local_persistence import (
    AllowlistedProductUrlError,
    run_allowlisted_product_url_persistence,
)
from .pipeline import CollectionPipelineResult, run_tesco_allowlisted_collection
from .review_decisions import (
    ReviewDecisionError,
    ReviewDecisionResult,
    approve_review_item,
    reject_review_item,
)
from .postgres import DATABASE_URL_ENV, PostgresConnectionError, open_postgres_connection
from .seed_loader import CollectionTargetSeedError, load_collection_targets
from .snapshot_store import SnapshotArtifact, SnapshotArtifactWriter
from .supplier_batch import SupplierBatchRunResult, run_supplier_batch_persistence
from .tesco_provider import (
    TESCO_FEATURE_FLAG,
    TescoIngestionProvider,
    TescoParseError,
    TescoProductPageParser,
    TescoScraperConfig,
)

__all__ = [
    "CollectionTarget",
    "CollectionAttempt",
    "CollectionTargetSeedError",
    "CollectionPipelineResult",
    "FixtureIngestionProvider",
    "IngestionJobResult",
    "IngestionPersistencePlan",
    "IngestionPlanRepository",
    "AllowlistedProductUrlError",
    "ASDA_FEATURE_FLAG",
    "AsdaIngestionProvider",
    "AsdaParseError",
    "AsdaProductPageParser",
    "AsdaScraperConfig",
    "DATABASE_URL_ENV",
    "ExtractedProduct",
    "ProductExtractor",
    "FetchError",
    "FetchHttpStatusError",
    "FetchResponse",
    "FetchTimeoutError",
    "FetchUrlError",
    "GroupMatchingSummary",
    "ProductGroupMatch",
    "candidate_from_parsed_product",
    "match_parsed_products",
    "TESCO_FEATURE_FLAG",
    "ParsedProduct",
    "PostgresConnectionError",
    "PriceObservation",
    "RawProductSnapshot",
    "ReviewDecisionError",
    "ReviewDecisionResult",
    "approve_review_item",
    "reject_review_item",
    "SnapshotArtifact",
    "SnapshotArtifactWriter",
    "SupplierBatchRunResult",
    "TescoIngestionProvider",
    "TescoParseError",
    "TescoProductPageParser",
    "TescoScraperConfig",
    "UrllibSupplierFetcher",
    "SavePlanResult",
    "build_ingestion_persistence_plan",
    "load_collection_targets",
    "open_postgres_connection",
    "run_allowlisted_product_url_persistence",
    "run_supplier_batch_persistence",
    "run_tesco_allowlisted_collection",
]
