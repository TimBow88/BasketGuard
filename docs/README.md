# BasketGuard Documentation

This folder contains the BasketGuard documentation pack. These documents define the product scope, technical architecture, data model, implementation order, and backend pipeline.

## Core Documents

1. [Product brief](00_PRODUCT_BRIEF.md)
2. [Problem and goals](01_PROBLEM_AND_GOALS.md)
3. [MVP scope](02_MVP_SCOPE.md)
4. [Data ingestion](03_DATA_INGESTION.md)
5. [Product normalisation and equivalence](04_PRODUCT_NORMALISATION_AND_EQUIVALENCE.md)
6. [Price analytics and offender score](05_PRICE_ANALYTICS_AND_OFFENDER_SCORE.md)
7. [Technical architecture](06_TECHNICAL_ARCHITECTURE.md)
8. [Database schema](07_DATABASE_SCHEMA.md)
9. [Reporting and UX](08_REPORTING_AND_UX.md)
10. [Risks, legal and trust](09_RISKS_LEGAL_TRUST.md)
11. [Roadmap](10_ROADMAP.md)
12. [Codex workplan](11_CODEX_WORKPLAN.md)
13. [Grouping catalogue draft](12_GROUPING_CATALOGUE_DRAFT.md)
14. [Git workflow](13_GIT_WORKFLOW.md)
15. [Backend pipeline pack](backend/00_BACKEND_PIPELINE_INDEX.md)

## Current Build Order

The original scaffold workplan is retained in [Codex workplan](11_CODEX_WORKPLAN.md) as a completed/legacy checkpoint. The active backend implementation sequence starts in [Backend Codex prompts](backend/09_CODEX_PROMPTS.md).

Recommended next steps:

1. Build backend models and services against the existing UUID/raw SQL migrations.
2. Start from allowlisted `collection_targets`, `ingestion_jobs`, immutable `raw_product_snapshots`, `products`, and append-only `price_observations`.
3. Add richer parser/review/aggregate concepts only through future numbered raw SQL migrations, beginning with `0003`.
4. Keep live crawling disabled by default and use fixture-backed tests first.

The backend-specific pipeline plan lives in [docs/backend](backend/00_BACKEND_PIPELINE_INDEX.md). It is reconciled to the existing UUID/raw SQL migrations in `db/migrations/`.
