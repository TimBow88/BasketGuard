# BasketGuard Implementation Checklist

## Backend foundation

- [ ] FastAPI app exists.
- [ ] `/health` endpoint exists.
- [ ] Settings module exists.
- [x] PostgreSQL connection helper exists for local persistence command.
- [ ] Raw SQL migrations run.
- [ ] Pytest runs locally.
- [x] Gated live PostgreSQL integration test exists for repository upserts.
- [ ] Docker Compose exists for local Postgres/Redis if required.

## Database

- [ ] `retailers` table.
- [ ] `collection_targets` table.
- [ ] `ingestion_jobs` table.
- [ ] `ingestion_job_targets` table.
- [ ] `raw_product_snapshots` table.
- [ ] `products` table.
- [ ] `equivalence_groups` table.
- [ ] `product_group_memberships` table.
- [ ] `price_observations` table.
- [ ] `analytics_findings` table.
- [ ] `reports` table.
- [ ] Future `0003`: `parser_versions` table if richer parser release metadata is needed.
- [ ] Future `0003`: `parsed_product_attributes` table for versioned snapshot parser outputs.
- [ ] Future `0003`: `review_queue_items` table for richer human-review workflow.
- [ ] Future `0003`: `daily_equivalence_group_prices` table if materialised aggregates are needed.

## Ingestion

- [x] Manual seed URL format exists.
- [x] Seed loader validates files.
- [x] Seed loader maps seeded targets into repository row payloads.
- [x] Supplier batch workflow processes large allowlisted target files.
- [x] Tesco supplier batch targets are supported.
- [x] Asda supplier batch targets are supported from recorded fixture HTML.
- [x] Unsupported supplier targets are staged as skipped attempts.
- [x] Fetcher abstraction exists.
- [x] urllib HTTP fetcher exists.
- [ ] Playwright fetcher interface exists or is planned.
- [x] Raw HTML snapshots are stored and referenced by `raw_product_snapshots.raw_payload_location`.
- [x] Snapshot metadata is written beside local raw HTML artifacts.
- [x] Failed fetches are recorded in `ingestion_job_targets` with error codes/messages.
- [x] Parser failures are recorded in `ingestion_job_targets` with error codes/messages.
- [x] Ingestion job summaries are mapped and saved through the repository layer.

## Extraction

- [ ] Shared `ExtractedProduct` schema exists.
- [ ] Extractor interface exists.
- [x] First retailer extractor exists.
- [x] Second retailer extractor exists for Asda fixture HTML.
- [x] Extraction tests use recorded fixtures.
- [ ] Missing title is flagged.
- [ ] Missing price is flagged.
- [ ] Missing unit price is flagged.
- [ ] Missing category breadcrumb is flagged.
- [ ] Missing image URL is flagged where required.

## Normalisation

- [ ] Weight parser handles g/kg.
- [ ] Volume parser handles ml/l.
- [ ] Count parser handles packs/items/biscuits.
- [ ] Multipack parser handles `x` formats.
- [ ] Unit-price parser converts p/100g to GBP/kg.
- [ ] Raw text is preserved.
- [ ] Normalised values are stored separately.

## Parsing

- [ ] Brand-owner parser exists.
- [ ] Tier parser exists.
- [ ] Product-type parser exists.
- [ ] Exclusion flags exist.
- [ ] Cereal parser exists.
- [ ] Porridge oats exclusions exist.
- [ ] Cornflakes exclusions exist.
- [ ] Wheat biscuit count parsing exists.
- [ ] Fish species/form/coating parser exists before frozen cod auto-match.

## Grouping

- [ ] Group definitions stored as YAML/JSON fixtures.
- [ ] Group definition loader validates schema.
- [ ] Cornflakes group exists.
- [ ] Porridge oats group exists.
- [ ] Matcher returns `auto_match`, `needs_review`, `no_match`.
- [ ] Hard exclusions override score.
- [ ] Match score is stored in `product_group_memberships.match_confidence`.
- [ ] Match reason is stored in `product_group_memberships.match_reason`.
- [ ] Negative fixtures are rejected.
- [ ] Ambiguous fixtures go to review.

## Review queue

- [ ] Review candidate is surfaced for uncertain matches.
- [ ] Review list endpoint exists.
- [ ] Review detail endpoint exists.
- [ ] Approve action exists.
- [ ] Reject action exists.
- [ ] Parser bug action exists.
- [ ] New group needed action exists.
- [ ] Reviewer notes are stored.
- [ ] Review decisions update `product_group_memberships`.
- [ ] Review decisions can become fixtures.
- [ ] Future `0003`: full `review_queue_items` audit table exists.

## Price history

- [x] Price observations are built as append-only row payloads.
- [x] Observations link to `products`.
- [x] Observations link to `raw_product_snapshots`.
- [ ] Observations join to groups through `product_group_memberships`.
- [ ] Promotion text is stored separately.
- [ ] Loyalty/member price is not mixed with standard price unless explicitly flagged.

## Reporting

- [ ] Group comparison endpoint exists.
- [ ] Group history endpoint exists.
- [ ] Retailer gap endpoint exists.
- [ ] Daily group aggregation exists.
- [ ] Daily group aggregation is query-based or backed by future `daily_equivalence_group_prices`.
- [ ] Confidence labels exist.
- [ ] Reports exclude rejected/needs-review data.
- [ ] Reports include source snapshot ID for audit.

## Analytics

- [ ] 7-day movement.
- [ ] 30-day movement.
- [ ] 90-day movement.
- [ ] YoY movement when enough history exists.
- [ ] Retailer price gap.
- [ ] Basket-level price movement.
- [ ] Shrinkflation suspect detection.
- [ ] Promotion masking detection.

## Quality gates

- [ ] Tests run on every change.
- [x] Parser fixtures cover current positive Tesco examples.
- [x] Parser fixtures cover current positive Asda examples.
- [x] Snapshot replay is possible from local raw HTML artifacts.
- [x] Parser versions are recorded on raw snapshot rows.
- [ ] Equivalence group definition versions are recorded.
- [ ] Scraper drift is detectable.
- [ ] Failed ingestion jobs are visible.

## MVP exit criteria

BasketGuard has a credible MVP when it can answer this accurately:

```text
For selected own-brand products across Tesco, Asda, Sainsbury's and Morrisons, what is the current equivalent unit price, how has it moved over time, and which retailer is materially more expensive?
```

Minimum required groups:

```text
own_brand_cornflakes_standard
own_brand_porridge_oats_standard
own_brand_spaghetti_standard
own_brand_plain_flour_standard
own_brand_granulated_sugar_standard
own_brand_long_grain_rice_standard
own_brand_baked_beans_standard
```

Minimum required reports:

```text
group comparison
group history
retailer gaps
review-required products
```
