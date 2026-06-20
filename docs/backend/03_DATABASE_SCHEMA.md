# BasketGuard Backend Database Schema

## Source of truth

The authoritative backend schema is the existing raw SQL migration set in `db/migrations/`.

Current migrations:

1. `0001_initial_schema.sql` creates the UUID-based BasketGuard core schema.
2. `0002_data_gathering_workflow.sql` adds controlled collection targets and ingestion job tracking.
3. `0003_parser_review_and_aggregates.sql` adds review queue items and report support.
4. `0004_review_state_and_parsed_attributes.sql` adds richer review queue state, review events and versioned parsed product attributes.

Do not introduce a second parallel schema with `BIGSERIAL` IDs or alternate table names. Backend code, prompts and future migrations should extend the current UUID/raw SQL model.

## Current table vocabulary

Use these names in backend code and docs:

| Concept | Current table |
|---|---|
| Retailers | `retailers` |
| Collection allowlist / seed targets | `collection_targets` |
| Collection jobs / scrape runs | `ingestion_jobs` |
| Per-target job attempts | `ingestion_job_targets` |
| Immutable source evidence | `raw_product_snapshots` |
| Retailer-specific cleaned products | `products` |
| Price history | `price_observations` |
| Comparable product groups | `equivalence_groups` |
| Product-to-group matches | `product_group_memberships` |
| Product replacement / resize lineage | `product_lineage` |
| User watchlists | `user_watchlists` |
| Generated analytics warnings | `analytics_findings` |
| Generated reports | `reports` |
| Receipt imports | `receipt_imports`, `receipt_items` |

## Current relationship summary

```text
retailers
  -> collection_targets
  -> ingestion_jobs
      -> ingestion_job_targets
          -> raw_product_snapshots
  -> products
      -> price_observations
      -> product_group_memberships
          -> equivalence_groups
      -> product_lineage

equivalence_groups
  -> analytics_findings
  -> user_watchlists

reports store generated report payloads.
receipt_imports and receipt_items are future receipt-ingestion support.
```

## Backend design mapping

### Immutable snapshots

Use `raw_product_snapshots` for raw collection evidence.

Important fields:

```text
retailer_id
external_product_id
url
raw_title
raw_price_text
raw_unit_price_text
raw_promo_text
raw_pack_size_text
raw_payload_location
postcode_context
collection_status
parser_version
collected_at
```

Raw HTML, JSON, rendered text and screenshots should live outside the database, with `raw_payload_location` pointing to the artifact path.

### Source products

Use `products`, not a separate `source_products` table.

`products` represents a retailer-specific product identity with cleaned, current parsed attributes. It should be traceable back to raw snapshots through `price_observations.raw_snapshot_id`.

### Price observations

Use `price_observations` as the append-only price history table.

It links to:

```text
product_id -> products.id
raw_snapshot_id -> raw_product_snapshots.id
```

Equivalent-group reports should join through:

```text
price_observations
  -> products
  -> product_group_memberships
  -> equivalence_groups
```

Do not add a competing `group_definition_id` column to `price_observations` unless a future migration explicitly proves the denormalisation is needed.

### Group definitions

Use `equivalence_groups` for comparable product groups.

Structured matching rules should initially live as YAML/JSON fixtures in the codebase. If those rules need to be stored in the database later, add columns to `equivalence_groups` or a child table in a future migration; do not create a parallel `group_definitions` table.

### Group memberships

Use `product_group_memberships`, not `group_memberships`.

Current fields already support:

```text
match_confidence
match_reason
is_primary_match
human_reviewed
```

If explicit rejected/retired states become necessary, add a `review_status` or `membership_status` column in a future migration.

### Collection jobs

Use:

```text
collection_targets
ingestion_jobs
ingestion_job_targets
```

These replace the proposed `retailer_configs`, `scrape_runs` and `source_products` seed flow. MVP collection should start from allowlisted `collection_targets`.

## Delivered backend extensions

The earlier `0003` candidate list has now been partly delivered:

1. `review_queue_items`
   Stores human review work linked to snapshots, products where available and proposed equivalence groups.

2. `review_queue_events`
   Stores the review audit trail introduced with migration `0004`.

3. `parsed_product_attributes`
   Stores versioned parser outputs for raw snapshots, introduced with migration `0004`.

Future schema work must use the next unused numbered migration in
`db/migrations/`. Do not reuse or edit `0003` or `0004` after they have been
accepted through GitHub change control.

Possible future candidates:

1. `parser_versions`
   Tracks parser release metadata beyond the current parser version fields.

2. `daily_equivalence_group_prices`
   Rebuildable daily aggregate for group/retailer reporting if query-based reporting becomes too slow.

3. Membership status extension
   Add explicit status values to `product_group_memberships` if existing review queue state is not enough.

4. Group rule versioning
   Add `version`, `definition_json` and `status` fields to `equivalence_groups`, or add a child `equivalence_group_versions` table if multiple active historical definitions are needed.

## Migration policy

1. Preserve UUID primary keys.
2. Preserve existing table names.
3. Use raw SQL migrations under `db/migrations/`.
4. Add new concepts incrementally with a numbered migration.
5. Avoid destructive renames until the current implementation has real data and tests proving the migration path.
