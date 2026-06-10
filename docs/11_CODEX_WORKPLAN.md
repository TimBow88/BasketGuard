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

## Active Next Prompt

Use the reconciled backend prompt sequence instead of restarting this legacy plan.

```text
Add the review queue foundation. Add additive migration 0003_parser_review_and_aggregates.sql with a UUID-based review_queue_items table referencing raw_product_snapshots(id), products(id) where available, and equivalence_groups(id) for the proposed group, with match score, match reason and status. Extend the ingestion persistence plan so needs_review candidates produce review_queue_items row payloads (not product_group_memberships), persisted through the repository. Add tests with a fake connection. Do not add HTTP endpoints yet.
```

Source: [docs/backend/08_MVP_DELIVERY_ROADMAP.md](backend/08_MVP_DELIVERY_ROADMAP.md)

## Deferred Items

These should be tackled after the backend foundation is in place:

1. Rich review queue state through a future `0003` raw SQL migration.
2. Versioned parsed snapshot attributes through a future `0003` raw SQL migration.
3. Materialised daily equivalence group aggregates only if query-based reporting becomes too slow.
4. Receipt import implementation beyond the current placeholder schema.
5. Public account/auth flows.
