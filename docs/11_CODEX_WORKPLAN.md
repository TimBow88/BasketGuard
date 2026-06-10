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
Add review decision functions. Given a DB-API connection and a review_queue_items id, approve_review_item should mark the item resolved with decision approve_group_membership and upsert the corresponding product_group_memberships row with human_reviewed=true, while reject_review_item should mark it resolved with decision reject_group_membership and delete or block the membership. Record reviewer notes and resolved_at, commit on success and roll back on failure. Add tests with a fake connection. Do not add HTTP endpoints yet.
```

Source: [docs/backend/08_MVP_DELIVERY_ROADMAP.md](backend/08_MVP_DELIVERY_ROADMAP.md)

## Deferred Items

These should be tackled after the backend foundation is in place:

1. Rich review queue state through a future `0003` raw SQL migration.
2. Versioned parsed snapshot attributes through a future `0003` raw SQL migration.
3. Materialised daily equivalence group aggregates only if query-based reporting becomes too slow.
4. Receipt import implementation beyond the current placeholder schema.
5. Public account/auth flows.
