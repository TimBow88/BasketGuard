# BasketGuard Database

Database migrations live in `db/migrations/`.

## Current Migration

- `0001_initial_schema.sql` creates the initial PostgreSQL schema described in `docs/07_DATABASE_SCHEMA.md`.
- `0002_data_gathering_workflow.sql` adds collection targets and ingestion job tracking for controlled data gathering.
- `0003_parser_review_and_aggregates.sql` adds `review_queue_items` so needs-review group match candidates are persisted with status, decision and reviewer notes.
- `0004_review_state_and_parsed_attributes.sql` adds richer review queue state, review queue events and versioned parsed product attributes.

## Notes

- PostgreSQL is the target database.
- UUID primary keys use `gen_random_uuid()` from the `pgcrypto` extension.
- Price and score columns include conservative non-negative/range checks.
- Product matching confidence is stored as `0..1`; offender and alert scores are stored as `0..100`.
- TimescaleDB is intentionally not required yet. It can be introduced later if price-observation volume needs it.
- Data gathering starts from allowlisted `collection_targets` so MVP collection can stay narrow and auditable.
