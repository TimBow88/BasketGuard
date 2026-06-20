# BasketGuard

BasketGuard is a UK grocery price-behaviour tracker. It is intended to flag retailer-specific price spikes, weak promotions, shrinkflation, and poor-value outliers across comparable supermarket products.

The product should answer:

> Which supermarket is disproportionately increasing the price of things I actually buy, compared with equivalent products elsewhere?

## Repository Structure

```text
apps/
  web/                         Frontend web app
  api/                         Backend API
packages/
  shared/                      Shared types and utilities
  product-normalisation/       Product parsing, unit conversion, and equivalence logic
  analytics/                   Price metrics, offender scoring, and confidence logic
services/
  ingestion/                   Retailer and receipt ingestion workers
  reporting/                   Weekly reports and alert generation
db/
  migrations/                  PostgreSQL schema migrations
docs/                          Product, architecture, data, UX, and roadmap docs
tests/                         Cross-package and integration tests
artifacts/                     Local generated snapshots and runtime artifacts
```

## Documentation

Start with [docs/README.md](docs/README.md). The numbered documents in `docs/` define product, architecture, UX and implementation guidance.

Delivery governance is defined in [docs/15_DELIVERY_GOVERNANCE.md](docs/15_DELIVERY_GOVERNANCE.md):

- Linear is the single source of truth for planned work, current status, priority, ownership and delivery sequencing.
- GitHub manages change control through branches, pull requests, CI evidence, merge history and tags.
- Repository docs describe durable product and engineering decisions; they do not replace the live Linear backlog.

Backend pipeline details live in [docs/backend/00_BACKEND_PIPELINE_INDEX.md](docs/backend/00_BACKEND_PIPELINE_INDEX.md). The existing UUID/raw SQL migrations in `db/migrations/` are the source of truth for backend storage.

## Current Status

This repository has kickoff documentation, initial PostgreSQL migrations, ingestion/normalisation/analytics/reporting package scaffolds, a simple web UI, fixtures, and tests.

## Tests

The current test suite uses the Python standard library runner:

```powershell
python -m unittest discover -s tests -v
```

The live PostgreSQL integration test is opt-in and skipped by default:

```powershell
$env:BASKETGUARD_RUN_POSTGRES_INTEGRATION="1"
$env:BASKETGUARD_DATABASE_URL="postgresql://basketguard:basketguard@localhost:5432/basketguard"
python -m unittest tests.test_postgres_integration -v
```

For the next implementation task, use the BasketGuard project in Linear. Historical roadmap prompts in this repository are retained for context only.

## Local Ingestion Persistence

The current backend has a narrow local command for one allowlisted Tesco URL. It validates the URL against `services/ingestion/fixtures/mvp_collection_targets.json`, fetches it when the live safety flag is set, writes raw HTML snapshots to `artifacts/raw_snapshots/`, parses product and price fields, builds the `price_observations` row, and saves the ingestion plan to PostgreSQL through the repository layer.

See [services/ingestion/README.md](services/ingestion/README.md) for the exact command and environment variables.

For larger supplier target files, use the allowlisted batch process:

```powershell
python -m basketguard_ingestion.supplier_batch --allowlist-seed services/ingestion/fixtures/mvp_collection_targets.json --batch-size 100 --max-targets 1000 --live
```

The batch process does not crawl categories or discover products. Tesco, Asda
and Sainsbury's now have narrow fixture-backed provider/parser coverage;
unsupported suppliers are recorded as skipped attempts until a provider/parser
is implemented.
