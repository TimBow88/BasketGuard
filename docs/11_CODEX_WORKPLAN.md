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

This section is the authoritative project progress ledger. Update it in the
same PR that delivers a milestone, after tests pass and before creating the
matching git tag. The tag list in Git should match this table exactly.

Progress tracking uses this order of authority:

1. Git tags named `milestone-00X-short-name`.
2. This delivered milestone table.
3. [Backend implementation checklist](backend/10_IMPLEMENTATION_CHECKLIST.md)
   for capability-level detail.
4. [MVP delivery roadmap](backend/08_MVP_DELIVERY_ROADMAP.md) for future
   direction and active prompt text.

When assessing project status, treat git tags and this table as the record of
what is delivered. Treat roadmap prompts as planned work unless a matching
milestone tag has been created.

| Tag | Date | Content |
|---|---|---|
| `milestone-001-scaffold` | 2026-06 (initial import) | Docs pack, migrations `0001`/`0002`, normalisation/analytics packages, fixtures, weekly report, web UI scaffold. |
| `milestone-002-ingestion-pipeline` | 2026-06-10 (PRs #1–#4) | Fetcher abstraction, snapshot store, DB mapping/repository, local persistence command, supplier batch, Asda provider, shared `ExtractedProduct` contract, equivalence group definitions + matcher, membership wiring, group comparison report. |
| `milestone-003-mvp-reports` | 2026-06-10 (PRs #5–#8) | Group price history report, retailer gap report, migration `0003` review queue foundation, review-required products report. All four required MVP reports exist as query-based functions. |
| `milestone-004-review-loop` | 2026-06-10 (PR #9) | Review decision functions: approve resolves the queue item and upserts a `human_reviewed=true` membership; reject resolves and removes the membership. |
| `milestone-005-multi-retailer` | 2026-06-11 (PRs #10–#11) | Sainsbury's and Morrisons fixture-backed providers with comparable own-brand groups. Both follow the Tesco/Asda safety model. |
| `milestone-006-api-skeleton` | 2026-06-11 (PR #12) | FastAPI app in `services/api/` with `/health` and GET endpoints wrapping the four query-based reports. Injectable connection factory, per-request connections via `open_postgres_connection`, Decimals serialised as strings. No ORM. |
| `milestone-007-review-api` | 2026-06-11 (PR #13) | Review loop over HTTP: `POST /review-items/{id}/approve` and `/reject` wrapping the existing decision functions, optional reviewer notes body, 404 for missing or already-resolved items. |
| `milestone-008-mvp-groups` | 2026-06-11 (PR #14) | All seven required MVP equivalence groups exist: spaghetti, plain flour, granulated sugar, long grain rice and baked beans added alongside cornflakes and porridge oats, each with positive fixtures across the four retailers, hard-exclusion negatives and a needs_review ambiguous case. Matcher scoring unchanged. |

Planned next milestones (tag when delivered):

1. `milestone-009-price-movement` — query-based 7/30/90-day unit-price movement per group and retailer, reusing the shared group join and membership eligibility rules.

## Milestone Closeout Procedure

Use this procedure when a milestone is complete:

1. Run the full suite:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m unittest discover -s tests -v
```

2. Confirm the working tree contains only the intended milestone changes:

```powershell
git status --short
```

3. Update this file:

- add one row to "Delivered Milestones";
- remove or advance the completed item from "Planned next milestones";
- replace "Active Next Prompt" with the next milestone prompt.

4. Update supporting docs when relevant:

- [Backend implementation checklist](backend/10_IMPLEMENTATION_CHECKLIST.md)
- [MVP delivery roadmap](backend/08_MVP_DELIVERY_ROADMAP.md)
- [Git workflow](13_GIT_WORKFLOW.md), if the milestone/tag list changed

5. Commit and merge through the normal PR flow.

6. Create and push the lightweight tag on `main`:

```powershell
git tag milestone-00X-short-name
git push origin milestone-00X-short-name
```

7. Re-check that `git tag --list "milestone-*"` matches the delivered
milestone table.

## Active Next Prompt

Use the reconciled backend prompt sequence instead of restarting this legacy plan.

```text
Add a query-based price movement report to basketguard_reporting. For a given group slug, return the unit-price movement per retailer over 7, 30 and 90 day windows: earliest and latest eligible observation in each window, absolute and percentage change, reusing GROUP_OBSERVATION_JOIN and MEMBERSHIP_ELIGIBILITY_CLAUSE so needs-review and rejected products never appear. Expose it as GET /reports/price-movement/{group_slug} on the existing FastAPI app. Add unittest tests with a fake connection covering movement maths, empty windows and serialisation. Do not add materialised aggregates. Tag milestone-009-price-movement once merged.
```

Source: [docs/backend/08_MVP_DELIVERY_ROADMAP.md](backend/08_MVP_DELIVERY_ROADMAP.md)

## Deferred Items

These should be tackled after the backend foundation is in place:

1. ~~Rich review queue state through a future raw SQL migration.~~ Delivered in
   migration `0004`: `in_review` state, reviewer/parser/group-version columns on
   `review_queue_items`, and a `review_queue_events` audit trail.
2. ~~Versioned parsed snapshot attributes through a future raw SQL migration.~~
   Delivered in migration `0004` as the `parsed_product_attributes` table.
3. Materialised daily equivalence group aggregates only if query-based reporting becomes too slow.
4. Receipt import implementation beyond the current placeholder schema.
5. Public account/auth flows.
