# BasketGuard Ingestion

Contracts and providers for collecting retailer product observations.

Current scope:

- typed ingestion contracts;
- a shared `ExtractedProduct` extraction contract produced by all retailer parsers;
- allowlisted collection target seed loading;
- fixture-backed mock provider;
- Tesco HTML parser and disabled-by-default allowlisted provider;
- Asda HTML parser and disabled-by-default allowlisted provider;
- local raw HTML snapshot artifact writing when a snapshot root is configured;
- database row-payload mapping for the existing UUID/raw SQL schema;
- DB-API repository writes for mapped ingestion plans;
- a local single-URL persistence command for allowlisted Tesco product pages;
- no live retailer crawling by default;
- no network requests unless the Tesco feature flag is explicitly enabled;
- no database writes unless a caller supplies a PostgreSQL connection or the local
  command is run with a database URL.

The provider output maps to the initial PostgreSQL tables:

- `raw_product_snapshots`;
- `products`;
- `price_observations`;
- `ingestion_jobs`.

## Collection Targets

MVP allowlisted targets live in:

```text
services/ingestion/fixtures/mvp_collection_targets.json
```

Load them with `load_collection_targets`. The seed format maps to the current `collection_targets` table vocabulary: retailer, target name, target URL, external product ID, equivalence group slug, postcode context, collection frequency, priority and active state.

## Shared Extraction Contract

Both `TescoProductPageParser` and `AsdaProductPageParser` expose an
`extract(html, url)` method returning the retailer-neutral `ExtractedProduct`
contract (title, brand, raw price text, currency, unit price text, pack size
text, category breadcrumb, image URL, availability, promotion text, external
product ID and a `raw_fields` map preserving retailer-specific selector
values such as Tesco Clubcard prices).

`ExtractedProduct.missing_fields` flags absent title, price, unit price,
category breadcrumb and image URL. `parse()` consumes the extracted contract
and still raises retailer parse errors for missing required fields, so failed
attempts continue to be recorded in `ingestion_job_targets`. The fixture
`asda_porridge_oats_missing_price.html` covers the parser-failure path.

## Snapshot Artifacts

`SnapshotArtifactWriter` stores raw HTML under a deterministic local path and writes `metadata.json` with the snapshot payload and SHA-256 content hash.

`TescoIngestionProvider` remains disabled by default. When explicit live collection is enabled and `TescoScraperConfig.snapshot_root` is provided, successful allowlisted fetches are written to disk and `RawProductSnapshot.raw_payload_location` is populated.

## Fetching

Supplier network access goes through a small fetcher boundary:

- `SupplierFetcher` defines the interface;
- `UrllibSupplierFetcher` is the current HTTP implementation;
- `FetchResponse` preserves status, headers and response body separately;
- `FetchError` subclasses represent HTTP status errors, timeouts and URL/network failures.

`TescoIngestionProvider` and `AsdaIngestionProvider` consume the configured fetcher and persist structured
attempt errors such as `timeout`, `http_404`, `http_429` and `url_error` into
`ingestion_job_targets` via the existing mapping layer. Live fetching remains
disabled unless both the provider config and the retailer feature flag allow it.

## Database Mapping

`build_ingestion_persistence_plan` converts an `IngestionJobResult` plus optional `CollectionTarget` records into row payloads for:

```text
retailers
equivalence_groups
collection_targets
ingestion_jobs
ingestion_job_targets
raw_product_snapshots
products
price_observations
```

The mapper uses deterministic UUIDs so relationships can be tested without a live PostgreSQL connection. It does not write to the database.

`IngestionPlanRepository` accepts a DB-API compatible connection and persists a plan with dependency-ordered `INSERT ... ON CONFLICT (id) DO UPDATE` statements. It commits on success and rolls back on failure. Tests use a fake connection; no PostgreSQL dependency is required yet.

## Group Membership Matching

When `build_ingestion_persistence_plan` is given loaded equivalence group
definitions (see `load_equivalence_group_definitions` in the
product-normalisation package), each parsed product is scored against the
active definitions:

- `auto_match` results emit `product_group_memberships` row payloads with
  `match_confidence` and a joined `match_reason`, persisted after `products`
  and `equivalence_groups`;
- `needs_review` results persist as `review_queue_items` row payloads (open
  status, match confidence, match reason, linked to the product, raw snapshot
  and proposed group) and are also surfaced on
  `IngestionPersistencePlan.group_review_candidates` and counted in the
  ingestion job notes;
- `no_match` results are dropped silently.

Review item IDs are keyed on the raw snapshot where possible, so re-running
the same snapshot upserts the same row while each new collection produces a
fresh review item against its own evidence.

Matched groups that are not already present from collection target seeds get
an `equivalence_groups` row created from the definition (slug, name, unit
basis, tier). Membership row IDs are deterministic per product/group pair, so
re-runs upsert instead of duplicating.

`open_postgres_connection` opens a DB-API compatible PostgreSQL connection using `psycopg` or `psycopg2`. It reads `BASKETGUARD_DATABASE_URL` first, then `DATABASE_URL`, unless a URL is passed directly.

## Pipeline Runner

`run_tesco_allowlisted_collection` ties the MVP pieces together:

1. load allowlisted Tesco targets from a seed file;
2. run `TescoIngestionProvider` with live collection still disabled by default;
3. write snapshot artifacts when `snapshot_root` is provided;
4. build an `IngestionPersistencePlan`;
5. optionally save the plan when a DB-API connection is supplied.

Tests inject a fixture-backed provider so the pipeline can be verified without network requests.

## Live Postgres Integration Test

The normal test suite skips live database checks. To verify ordered upserts and
idempotent single-product re-runs against a migrated local PostgreSQL database:

```powershell
$env:BASKETGUARD_RUN_POSTGRES_INTEGRATION="1"
$env:BASKETGUARD_DATABASE_URL="postgresql://basketguard:basketguard@localhost:5432/basketguard"
python -m unittest tests.test_postgres_integration -v
```

The integration test uses recorded Tesco fixture HTML and a fixed collection
timestamp, so it proves repository ordering and `ON CONFLICT (id)` idempotency
without making a network request.

## Local Persistence Command

The narrow local workflow for one product URL is:

1. validate that the URL is an active Tesco target in the allowlist seed;
2. fetch the product page when live fetching is enabled;
3. write raw HTML and `metadata.json` under the snapshot root;
4. parse product and price fields;
5. build `price_observations` and related row payloads;
6. save the plan through `IngestionPlanRepository`.

Fetch and parser failures are persisted as failed `ingestion_job_targets` rows with `error_code`, `error_message` and `attempted_at`. Successful fetches continue to write immutable raw HTML snapshots and link the attempt row to `raw_product_snapshots.id`.

From the repository root:

```powershell
$env:PYTHONPATH="services/ingestion/src;packages/product-normalisation/src"
$env:BASKETGUARD_ENABLE_TESCO_SCRAPER="1"
$env:BASKETGUARD_DATABASE_URL="postgresql://basketguard:basketguard@localhost:5432/basketguard"
python -m basketguard_ingestion.local_persistence `
  --url "https://www.tesco.com/groceries/en-GB/products/254879001" `
  --allowlist-seed services/ingestion/fixtures/mvp_collection_targets.json `
  --snapshot-root artifacts/raw_snapshots `
  --live
```

The command intentionally handles one allowlisted URL at a time. It does not crawl category pages, discover new products or bypass the `BASKETGUARD_ENABLE_TESCO_SCRAPER` safety flag.

## Supplier Batch Process

For large supplier target lists, use the batch command instead of adding a crawler.
It processes explicit allowlisted product URLs in configurable batches and saves
each batch through the same repository layer:

```powershell
$env:PYTHONPATH="services/ingestion/src;packages/product-normalisation/src"
$env:BASKETGUARD_ENABLE_TESCO_SCRAPER="1"
$env:BASKETGUARD_DATABASE_URL="postgresql://basketguard:basketguard@localhost:5432/basketguard"
python -m basketguard_ingestion.supplier_batch `
  --allowlist-seed services/ingestion/fixtures/mvp_collection_targets.json `
  --snapshot-root artifacts/raw_snapshots `
  --retailer Tesco `
  --batch-size 100 `
  --max-targets 1000 `
  --live
```

The seed file may contain suppliers such as Tesco or Asda. Implemented providers
are fetched only when their live feature flag is set; unsupported suppliers are
staged into `collection_targets` and recorded as skipped `ingestion_job_targets`
with `error_code=unsupported_retailer`.
That makes large catalogue preparation auditable without pretending unsupported
retailers have been collected.

Operational guardrails:

1. only product URLs present in the seed are eligible;
2. use `--max-targets` for first runs and production safety caps;
3. keep `--batch-size` conservative so failures are easy to isolate;
4. store raw snapshots under `artifacts/raw_snapshots/` or object storage later;
5. add a retailer provider/parser before enabling collection for that supplier.

## Tesco Provider

`TescoIngestionProvider` will not run live collection unless both are true:

1. `TescoScraperConfig.enabled` is `true`;
2. `BASKETGUARD_ENABLE_TESCO_SCRAPER=1` is set in the environment.

The provider only accepts explicit allowlisted URLs. Parser behaviour is tested against saved HTML fixtures before any live collection is enabled.

## Asda Provider

`AsdaIngestionProvider` follows the same safety model:

1. `AsdaScraperConfig.enabled` is `true`;
2. `BASKETGUARD_ENABLE_ASDA_SCRAPER=1` is set in the environment.

The current Asda implementation is fixture-backed and intentionally narrow. It
parses recorded product HTML for explicit allowlisted Asda product URLs and is
wired into the supplier batch dispatcher. It does not crawl Asda categories or
discover products.
