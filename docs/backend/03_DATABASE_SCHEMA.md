# BasketGuard Backend Database Schema

## Source of truth

The authoritative backend schema is the existing raw SQL migration set in `db/migrations/`.

Current migrations:

1. `0001_initial_schema.sql` creates the UUID-based BasketGuard core schema.
2. `0002_data_gathering_workflow.sql` adds controlled collection targets and ingestion job tracking.

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

## Future `0003` migration candidates

Add missing backend-pipeline concepts by extending the existing schema in `db/migrations/0003_*.sql`.

Recommended candidates:

1. `parser_versions`
   Tracks parser release metadata beyond the current `raw_product_snapshots.parser_version` text field.

2. `parsed_product_attributes`
   Stores versioned parser outputs for each raw snapshot. This should reference `raw_product_snapshots(id)` with UUID foreign keys.

3. `review_queue_items`
   Stores human review work. It should reference `raw_product_snapshots(id)`, `products(id)` where available, and `equivalence_groups(id)` for proposed groups.

4. `daily_equivalence_group_prices`
   Rebuildable daily aggregate for group/retailer reporting. This should reference `equivalence_groups(id)`, `retailers(id)` and the selected `products(id)`.

5. Membership status extension
   Add explicit status values to `product_group_memberships` if `human_reviewed` plus `match_confidence` is not enough.

6. Group rule versioning
   Add `version`, `definition_json` and `status` fields to `equivalence_groups`, or add a child `equivalence_group_versions` table if multiple active historical definitions are needed.

## Migration policy

1. Preserve UUID primary keys.
2. Preserve existing table names.
3. Use raw SQL migrations under `db/migrations/`.
4. Add new concepts incrementally with a numbered migration.
5. Avoid destructive renames until the current implementation has real data and tests proving the migration path.
