# BasketGuard Backend Tech Decision

## Decision

Use a Python-first modular monolith.

Recommended stack:

```text
Backend API:        FastAPI
Workers:            Python workers using Playwright + httpx
Database:           PostgreSQL
Time-series option: TimescaleDB later, not required for MVP
Queue:              Redis + RQ or Dramatiq
Models/migrations:  SQLAlchemy models against existing raw SQL migrations
Validation:         Pydantic
Admin UI:           Next.js or React
Object storage:     Local filesystem first; S3/MinIO later
Tests:              pytest + recorded fixtures
```

Migration note:

BasketGuard already has raw SQL PostgreSQL migrations under `db/migrations/`, using UUID primary keys. Treat those migrations as canonical. SQLAlchemy models can be added to match the existing schema, but Alembic should not replace or rename the current migration history unless the project explicitly adopts it later.

## Why Python-first

BasketGuard is primarily a data system:

1. scraping;
2. product extraction;
3. unit parsing;
4. deterministic classification;
5. fuzzy-but-controlled grouping;
6. audit snapshots;
7. time-series price history;
8. review workflows;
9. analytics.

Python has the strongest fit for these tasks. FastAPI gives a clean API layer while keeping ingestion, parsing, tests and analytics in the same language.

## Why not a pure Node/Nest backend first

Node/Nest can work for API-heavy products, but BasketGuard's risk is not API routing. The risk is data quality.

The harder backend work is:

1. extracting inconsistent product data;
2. parsing pack sizes and unit prices;
3. maintaining category-specific grouping rules;
4. replaying historical snapshots against newer parsers;
5. building human-review datasets;
6. analysing price histories.

Python is better suited to this workload.

## Architecture style

Use a modular monolith.

```text
One repo.
One database.
One backend app.
Separate modules for ingestion, parsing, grouping, review and analytics.
Background workers for scrape and processing jobs.
```

Do not split into microservices until there is clear operational pressure.

## Runtime components

### API process

Responsible for:

1. group browsing;
2. product detail views;
3. price history endpoints;
4. reports;
5. review queue actions;
6. ingestion-job control endpoints for admin use.

### Worker process

Responsible for:

1. discovery jobs;
2. product fetching;
3. snapshot creation;
4. extraction;
5. normalisation;
6. grouping;
7. analytics aggregation;
8. scheduled reports.

### Database

PostgreSQL should hold:

1. retailers;
2. collection targets;
3. ingestion jobs;
4. raw product snapshots;
5. cleaned retailer products;
6. equivalence groups;
7. product group memberships;
8. price observations;
9. review decisions;
10. parser versions.

### Object storage

Store large raw artefacts outside relational rows:

1. raw HTML;
2. raw JSON;
3. screenshots;
4. debug extraction payloads.

For local dev, store under:

```text
/data/snapshots/
```

Later move to S3-compatible storage.

## Recommended package choices

| Need | Recommended option | Notes |
|---|---|---|
| API | FastAPI | Clean Pydantic integration |
| DB | PostgreSQL | Strong relational model plus JSONB support |
| Models | SQLAlchemy | Mature, flexible; map to existing tables |
| Migrations | Raw SQL | Existing `db/migrations/` history stays canonical |
| Queue | Redis + RQ/Dramatiq | Simple enough for MVP |
| Dynamic scraping | Playwright | For JS-rendered pages |
| Static fetching | httpx | For simple pages and APIs |
| HTML parsing | selectolax or BeautifulSoup | Use retailer-specific extractors |
| Tests | pytest | Fixture-driven parser tests |
| Scheduling | worker beat/cron | Keep simple initially |

## Tech decisions to defer

Do not decide these on day one:

1. TimescaleDB versus plain partitioned Postgres;
2. Elasticsearch/OpenSearch;
3. ML embeddings;
4. event streaming;
5. public user accounts;
6. mobile app backend concerns.

## Non-negotiables

1. Every fetched page must have a raw snapshot.
2. Every parser output must record parser version.
3. Every equivalence-group definition must be versioned.
4. Every price observation must be append-only.
5. Every uncertain match must be reviewable.
6. Reports must show confidence level.

## First backend target

Build the smallest system that can answer:

```text
Across Tesco, Asda, Sainsbury's and Morrisons, what is the current and historical price per kg for standard own-brand cornflakes and porridge oats?
```

If that cannot be answered accurately, broader categories should not be added.
