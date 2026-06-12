# Codex Workplan

## Status

This document is now a legacy checkpoint for the initial scaffold work. The early repo setup, initial raw SQL migrations, product normalisation utilities, analytics functions, seed fixtures, reporting scaffolds, ingestion contracts and basic web UI already exist.

Active backend implementation should now follow:

1. [Backend pipeline index](backend/00_BACKEND_PIPELINE_INDEX.md)
2. [Backend database schema](backend/03_DATABASE_SCHEMA.md)
3. [Backend MVP roadmap](backend/08_MVP_DELIVERY_ROADMAP.md)
4. [Backend Codex prompts](backend/09_CODEX_PROMPTS.md)

## Current Development Principle

Codex should always:

1. inspect the repo first;
2. use the existing UUID/raw SQL migrations in `db/migrations/` as the database source of truth;
3. implement the smallest useful change;
4. add or update tests;
5. run `python -m unittest discover -s tests -v`;
6. fix failures if safe;
7. summarise changed files, test result and next recommended task only.

## Completed Scaffold Milestones

The following initial workplan items are complete or superseded by existing repo state:

1. Initial documentation and repo structure.
2. Initial PostgreSQL schema migrations.
3. Product normalisation package.
4. Price analytics package.
5. Seed data fixtures.
6. Weekly report generator.
7. Ingestion service contracts and fixture provider.
8. First retailer parser tests behind disabled live collection.
9. Basic dashboard files and UI asset tests.

## Delivered Milestones

Each delivered milestone is a lightweight git tag on `main`. Only tag after the
full test suite passes.

| Tag | Date | Content |
|---|---|---|
| `milestone-001-scaffold` | 2026-06 (initial import) | Docs pack, migrations `0001`/`0002`, normalisation/analytics packages, fixtures, weekly report, web UI scaffold. |
| `milestone-002-ingestion-pipeline` | 2026-06-10 (PRs #1–#4) | Fetcher abstraction, snapshot store, DB mapping/repository, local persistence command, supplier batch, Asda provider, shared `ExtractedProduct` contract, equivalence group definitions + matcher, membership wiring, group comparison report. |
| `milestone-003-mvp-reports` | 2026-06-10 (PRs #5–#8) | Group price history report, retailer gap report, migration `0003` review queue foundation, review-required products report. All four required MVP reports exist as query-based functions. |
| `milestone-004-review-loop` | 2026-06-10 (PR #9) | Review decision functions: approve resolves the queue item and upserts a `human_reviewed=true` membership; reject resolves and removes the membership. |
| `milestone-005-multi-retailer` | 2026-06-11 (PRs #10–#11) | Sainsbury's and Morrisons fixture-backed providers with comparable own-brand groups. Both follow the Tesco/Asda safety model. |

Planned next milestones (tag when delivered):

1. `milestone-006-api-skeleton` — FastAPI app, `/health`, and HTTP endpoints wrapping the query-based reports.

## Active Next Prompt

Use the reconciled backend prompt sequence instead of restarting this legacy plan.

```text
Add a FastAPI app skeleton for BasketGuard. Create services/api/ with a minimal FastAPI app, a /health endpoint, and HTTP GET endpoints that wrap the four existing query-based report functions (group price history, retailer gap report, review-required products, and group comparison). Wire up a PostgreSQL connection using the existing open_postgres_connection helper. Add unittest-based tests for the /health route and at least one report endpoint using a fake connection. Do not introduce SQLAlchemy or any ORM. Tag milestone-006-api-skeleton once merged.
```

Source: [docs/backend/08_MVP_DELIVERY_ROADMAP.md](backend/08_MVP_DELIVERY_ROADMAP.md)

## Deferred Items

These should be tackled after the backend foundation is in place:

1. Rich review queue state through a future `0003` raw SQL migration.
2. Versioned parsed snapshot attributes through a future `0003` raw SQL migration.
3. Materialised daily equivalence group aggregates only if query-based reporting becomes too slow.
4. Receipt import implementation beyond the current placeholder schema.
5. Public account/auth flows.
