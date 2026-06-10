# BasketGuard Codex Prompts

## Prompt style

Use short, controlled Codex prompts.

Each prompt should:

1. implement the smallest safe backend step;
2. run tests;
3. fix failures;
4. summarise only files changed, test result and next recommended prompt;
5. avoid broad refactors unless explicitly requested.

Schema guardrail:

Use the existing UUID/raw SQL schema in `db/migrations/` as the source of truth. Do not introduce parallel tables named `source_products`, `product_snapshots`, `group_definitions`, `group_memberships`, `scrape_runs` or `retailer_configs`. Add missing backend concepts with a future numbered raw SQL migration, starting with `0003`.

## Prompt 1: Backend skeleton

```text
BasketGuard backend setup.

Create a Python FastAPI backend skeleton as a modular monolith. Add app startup, /health endpoint, settings module, pytest setup, and a minimal project structure for api, db, ingestion, normalisation, parsing, grouping, review and analytics. Do not implement scraping yet. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.94

## Prompt 2: Database foundation

```text
Add the initial database foundation for BasketGuard.

Implement SQLAlchemy models that map to the existing raw SQL migrations for retailers, collection_targets, ingestion_jobs, ingestion_job_targets, raw_product_snapshots, products, price_observations, equivalence_groups and product_group_memberships. Preserve UUID primary keys and existing table names. Do not add a new migration unless it is an additive numbered raw SQL migration. Add basic repository/service functions and tests. Do not add price analytics yet. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.92

## Prompt 3: Manual seed URL loader

```text
Add manual seed URL support for MVP scraping.

Create a YAML/JSON seed format mapping group slugs to retailer product URLs. Add loader validation and tests. Store or upsert allowlisted `collection_targets` from seed files, linked to `retailers` and `equivalence_groups` where available. Do not crawl category pages or sitemaps. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.91

## Prompt 4: Snapshot fetcher

```text
Implement the first BasketGuard snapshot fetcher.

Add a fetcher abstraction with httpx as the first implementation and a placeholder interface for Playwright later. Given a `collection_targets` row, fetch the page, create an `ingestion_jobs` entry, create an `ingestion_job_targets` attempt row, create an immutable `raw_product_snapshots` row, and save raw HTML to a local snapshot path referenced by `raw_payload_location`. Record failures instead of dropping them. Add tests with mocked HTTP responses. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.9

## Prompt 5: Product extraction contract

```text
Add the product extraction contract.

Create an ExtractedProduct schema with title, brand, price, currency, unit_price_text, pack_size_text, category_breadcrumb, image_url, availability, promotion_text, external_product_id and raw_fields. Add a generic extractor interface and one simple test extractor using recorded fixture HTML. Do not build retailer-specific selectors beyond the fixture. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.89

## Prompt 6: Unit and pack normalisation

```text
Implement unit and pack-size normalisation.

Add parsers for g, kg, ml, l, x multipacks, count packs, and unit price conversions such as p/100g to GBP/kg. Preserve raw text and return structured normalised values. Add strong pytest coverage for common UK grocery formats and edge cases. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.93

## Prompt 7: Parsed attributes table

```text
Add parsed product attributes.

Add migration `0003_parser_review_and_aggregates.sql` with UUID-based `parser_versions` and `parsed_product_attributes` tables that reference `raw_product_snapshots(id)`. Add a parser pipeline that takes an ExtractedProduct plus raw snapshot ID and stores parsed category, product_type, form, state, brand_owner, tier, flavour, coating, normalised_size, unit_basis, count, parser_confidence and exclusion_flags. Keep logic simple and deterministic. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.89

## Prompt 8: Cereal parser MVP

```text
Implement the MVP cereal parser.

Add deterministic parsing for cornflakes and porridge oats. Detect plain cornflakes vs honey/frosted/chocolate/bran/rice/multigrain exclusions. Detect porridge oats vs jumbo oats, sachets, instant, muesli and granola exclusions. Detect retailer own-label vs branded and standard vs value/premium/organic where possible. Add positive, negative and ambiguous fixtures. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.88

## Prompt 9: Equivalence group definitions as fixtures

```text
Add structured equivalence group definitions.

Create YAML/JSON equivalence group definition fixtures for own_brand_cornflakes_standard and own_brand_porridge_oats_standard. Include required attributes, exclude terms, size ranges, unit basis, risk level, auto_match_threshold and review_threshold. Load group identity into existing `equivalence_groups` rows. Add loader validation tests. Do not add broad food taxonomy yet. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.92

## Prompt 10: Group matcher MVP

```text
Implement the MVP group matcher.

Given parsed_product_attributes and equivalence group fixtures, return auto_match, needs_review or no_match with match_score, match_reason and exclusion_flags. Persist accepted candidates in `product_group_memberships`. Hard exclusions must override score. Add tests for cornflakes and porridge oats positives, negatives and review cases. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.9

## Prompt 11: Price observations

```text
Add price observations.

Use the existing `price_observations` table. After a raw snapshot is extracted, normalised and matched, append a price observation with product_id, raw_snapshot_id, collected_at, shelf_price/effective_price, unit_price, unit_price_basis, availability and promotion fields. Do not overwrite historical prices. Do not add group IDs directly to price observations; group reports should join through `product_group_memberships`. Add tests. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.91

## Prompt 12: Basic group comparison API

```text
Add the first reporting endpoint.

Create GET /reports/group-comparison/{group_slug}. It should return latest approved/high-confidence price observation per retailer for the group by joining `equivalence_groups`, `product_group_memberships`, `products`, `price_observations`, `raw_product_snapshots` and `retailers`. Include product title, price, unit price, pack size, availability, collected_at, confidence and raw snapshot ID. Exclude low-confidence or non-reviewed memberships. Add tests. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.88

## Prompt 13: Review queue foundation

```text
Add the review queue foundation.

Extend migration `0003_parser_review_and_aggregates.sql` with a UUID-based `review_queue_items` table referencing `raw_product_snapshots(id)`, `products(id)` where available, and `equivalence_groups(id)` for proposed groups. When matcher returns needs_review, create a review item containing raw snapshot, proposed group, match score, reason and status. Add endpoints to list open review items and approve/reject a proposed `product_group_memberships` row. Add tests. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.87

## Prompt 14: Wheat biscuit count parsing

```text
Add wheat biscuit count-aware parsing.

Implement parsing for own-brand wheat biscuits where count is the preferred unit basis. Detect 24 pack and similar counts. Exclude Weetabix, minis, chocolate, protein, organic, value and premium variants. Add equivalence group fixture and tests. Ambiguous count or format should go to review. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.86

## Prompt 15: Frozen cod gated implementation

```text
Add frozen cod only as a gated reviewed group.

Implement parser support for frozen cod fillets, including species, state, form, coating, tier and brand_owner. Add an equivalence group fixture for own_brand_frozen_cod_fillets_standard, but require category breadcrumb and image_url to be present before auto-match. Exclude battered, breaded, cod loins, portions, branded, premium/value/organic and non-cod white fish. Add tests. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.84

## Prompt 16: Daily aggregation

```text
Add daily group price aggregation.

Extend migration `0003_parser_review_and_aggregates.sql` with a rebuildable `daily_equivalence_group_prices` table if query-based reporting is too slow. Build one row per equivalence group, retailer and date from approved/high-confidence price observations. Include selected product, min price, min unit price, median unit price, observation count, availability count, promotion count and confidence level. Add tests. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.88

## Prompt 17: Retailer gap report

```text
Add retailer gap reporting.

Create GET /reports/retailer-gaps that lists eligible equivalence groups with lowest retailer, highest retailer, absolute unit price gap, percentage unit price gap, date, confidence and missing retailer count. Use `price_observations` joins first, or `daily_equivalence_group_prices` if migration `0003` has introduced it. Add tests. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.87

## Prompt 18: Shrinkflation suspect detection

```text
Add initial shrinkflation suspect detection.

Create a job that scans product price history for pack-size reductions where shelf price stayed similar or increased and unit price increased materially. Store suspect cases in `analytics_findings` or a report response unless a future migration adds a dedicated table. Keep it conservative and label as suspected, not confirmed. Add tests with synthetic histories. Run tests and fix failures. Summarise files changed, test result, and next recommended prompt only.
```

Confidence: 0.82
