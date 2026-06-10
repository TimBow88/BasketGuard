# BasketGuard MVP Delivery Roadmap

## Delivery principle

Build the smallest reliable price intelligence loop before expanding categories.

Do not start with every supermarket and every product group. Start with a narrow pipeline that proves the data quality model.

## Phase 0: Repo setup

### Goal

Create the backend skeleton and local dev environment.

### Tasks

1. Add FastAPI app skeleton.
2. Add PostgreSQL connection.
3. Add SQLAlchemy models that map to the existing raw SQL migrations.
4. Add pytest.
5. Add basic settings management.
6. Add Docker Compose for Postgres and Redis if needed.
7. Keep backend docs under `docs/backend/`.

### Definition of done

1. App starts locally.
2. Health endpoint works.
3. Tests run.
4. Existing raw SQL migrations apply cleanly.

## Phase 1: Data loop proof

### Goal

Fetch manually seeded product URLs and store immutable snapshots.

### Scope

One or two retailers only.

Groups:

```text
own_brand_cornflakes_standard
own_brand_porridge_oats_standard
```

### Tasks

1. Use existing `retailers` table.
2. Use existing `collection_targets` table for manual seed URLs.
3. Use existing `ingestion_jobs` table for collection runs.
4. Use existing `ingestion_job_targets` table for per-target attempts.
5. Use existing `raw_product_snapshots` table for immutable snapshots.
6. Add httpx/Playwright fetcher abstraction.
7. Store raw HTML snapshot.
8. Add basic extractor for first retailer.
9. Add tests using recorded fixture HTML.

### Definition of done

1. Seed URLs can be fetched.
2. `raw_product_snapshots` rows are created.
3. Raw HTML is stored.
4. Basic fields are extracted.
5. Failed fetches are recorded.

## Phase 2: Normalisation and low-risk grouping

### Goal

Normalise product data and auto-match low-risk groups.

### Tasks

1. Add unit normaliser.
2. Add pack-size parser.
3. Add unit-price parser.
4. Add brand-owner parser.
5. Add tier parser.
6. Add cereal parser.
7. Use existing `equivalence_groups` table.
8. Store equivalence group definitions as YAML/JSON fixtures.
9. Add matcher for cornflakes and porridge oats.
10. Add positive and negative parser tests.

### Definition of done

1. Cornflakes auto-match only when plain, own-brand, standard tier and valid kg unit basis.
2. Porridge oats auto-match only when standard oats, not sachets/jumbo/organic/branded.
3. Ambiguous products go to review.
4. Negative fixtures do not match.

## Phase 3: Price observations and comparison reports

### Goal

Append price observations and expose basic comparison endpoints.

### Tasks

1. Use existing `price_observations` table.
2. Append observation after snapshot parsing.
3. Build group aggregation as a query/report first.
4. Add group comparison endpoint.
5. Add group history endpoint.
6. Add simple admin/debug report.

### Definition of done

1. Current price per retailer/group is available.
2. Unit price comparison works.
3. Data links back to raw snapshot.
4. Reports exclude unapproved/low-confidence matches.

## Phase 4: Multi-retailer MVP

### Goal

Support Tesco, Asda, Sainsbury's and Morrisons for selected low-risk groups.

### Tasks

1. Add retailer-specific extractors.
2. Add seed URLs for each group/retailer.
3. Add extraction tests per retailer.
4. Add ingestion-job summaries.
5. Add missing-field warnings.
6. Add retailer comparison report.

### Initial group list

```text
own_brand_cornflakes_standard
own_brand_porridge_oats_standard
own_brand_spaghetti_standard
own_brand_plain_flour_standard
own_brand_granulated_sugar_standard
own_brand_long_grain_rice_standard
own_brand_baked_beans_standard
```

### Definition of done

1. Four retailers have at least five comparable own-brand groups.
2. Daily collection runs complete.
3. Missing products are visible.
4. Retailer price gaps can be reported.

## Phase 5: Human review queue

### Goal

Allow uncertain matches to be reviewed and converted into approved/rejected fixtures.

### Tasks

1. Use `product_group_memberships` for simple review gating first.
2. Surface a review candidate when match score is below auto threshold but above review threshold.
3. Add review list endpoint.
4. Add approve/reject endpoints.
5. Update group membership after review.
6. Record reviewer notes.
7. Generate fixture candidates from decisions.
8. Add `review_queue_items` in migration `0003` when richer queue/audit state is needed.

### Definition of done

1. Ambiguous products no longer disappear.
2. Human-approved products appear in reports.
3. Rejected products are blocked from same group.
4. Parser bugs can be flagged.

## Phase 6: Medium-risk groups

### Goal

Add groups that require stronger parsing and/or human review.

Candidate groups:

```text
own_brand_wheat_biscuits_standard
own_brand_semi_skimmed_milk_2l_standard
own_brand_whole_milk_2l_standard
own_brand_unsalted_butter_standard
own_brand_mature_cheddar_standard
own_brand_frozen_peas_standard
own_brand_tinned_tomatoes_chopped_standard
```

### Definition of done

1. Count-based parsing works for wheat biscuits.
2. Dairy tier parsing is stable.
3. Medium-risk fixtures include review cases.
4. Reports label confidence accurately.

## Phase 7: High-risk controlled expansion

### Goal

Add high-value but riskier groups after review workflow exists.

Candidate groups:

```text
own_brand_frozen_cod_fillets_standard
own_brand_chicken_breast_fillets_standard
own_brand_minced_beef_5_percent_standard
own_brand_granola_standard_reviewed
own_brand_eggs_medium_free_range_standard
```

### Definition of done

1. Image URL and category breadcrumb are available.
2. Species/cut/form parsing is tested.
3. Granola remains review-led.
4. Reports avoid low-confidence automated claims.

## Phase 8: Price intelligence

### Goal

Move from tracking prices to generating useful insights.

### Tasks

1. 7/30/90-day movement.
2. Year-on-year movement once enough history exists.
3. Retailer gap ranking.
4. Shrinkflation suspect detection.
5. Basket-level reports.
6. Promotion masking flags.
7. Confidence labels in all reports.

### Definition of done

1. App can answer which retailer has moved most by group.
2. App can identify unusually large increases.
3. App can flag pack-size reductions.
4. Reports are evidence-linked and confidence-labelled.

## Recommended immediate next action

Start Phase 5 by adding the review queue foundation so needs-review candidates
are persisted and the final required MVP report (review-required products) can
be built.
The query-based reporting layer now covers three of the four required MVP
reports: group comparison (latest eligible observation per retailer,
cheapest-first), group price history (eligible observations per retailer over a
rolling day window), and retailer gaps (cheapest vs dearest unit price per
group with missing-retailer counts). All three share one membership eligibility
predicate and exclude needs-review and rejected products. The remaining
required report, review-required products, needs needs-review candidates to be
persisted first.
The group matcher is wired into the ingestion persistence plan: auto-match
results emit `product_group_memberships` rows with `match_confidence` and
`match_reason`, while needs-review candidates are surfaced on the plan and in
the ingestion job notes without being persisted.
Equivalence group definitions for own-brand cornflakes and porridge oats now
exist as validated JSON fixtures, and a deterministic matcher returns
`auto_match`, `needs_review` or `no_match` with hard exclusions overriding
score.
The shared `ExtractedProduct` contract is now produced by both the Tesco and
Asda parsers, with missing extraction fields flagged and an Asda
missing-price fixture proving the parser-failure path.
The local single-URL Tesco persistence command now proves the path from
allowlisted URL to raw snapshot, parsed product, `price_observations` row payload
and repository-backed PostgreSQL save. Failed fetches and parser failures are
mapped into `ingestion_job_targets` with error codes/messages. A supplier batch
workflow can process large explicit Tesco and Asda target seeds while staging
unsupported suppliers as skipped attempts. Fetch behavior is now behind a
testable urllib fetcher abstraction. A gated live PostgreSQL integration test
verifies ordered upserts and idempotent single-product re-runs.

First Codex target:

```text
Add the review queue foundation. Add additive migration 0003_parser_review_and_aggregates.sql with a UUID-based review_queue_items table referencing raw_product_snapshots(id), products(id) where available, and equivalence_groups(id) for the proposed group, with match score, match reason and status. Extend the ingestion persistence plan so needs_review candidates produce review_queue_items row payloads (not product_group_memberships), persisted through the repository. Add tests with a fake connection. Do not add HTTP endpoints yet.
```
