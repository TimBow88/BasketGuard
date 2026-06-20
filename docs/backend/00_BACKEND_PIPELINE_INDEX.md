# BasketGuard Backend Pipeline Index

## Purpose

This pack defines the backend pipeline required to make BasketGuard functional.

BasketGuard is a supermarket price intelligence app. Its core value is not simply collecting prices. Its value is comparing genuinely equivalent products, especially UK supermarket own-brand products, then showing meaningful price movement such as retailer divergence, year-on-year increases, promotion masking and shrinkflation.

The grouping catalogue remains the controlling product-equivalence document. This backend pack explains how to turn that grouping logic into a working system.

## Recommended docs folder structure

Place these files under:

```text
/docs/backend/
```

Recommended order:

```text
00_BACKEND_PIPELINE_INDEX.md
01_BACKEND_TECH_DECISION.md
02_PIPELINE_END_TO_END.md
03_DATABASE_SCHEMA.md
04_INGESTION_AND_SNAPSHOT_STRATEGY.md
05_NORMALISATION_GROUPING_AND_MATCHING.md
06_HUMAN_REVIEW_QUEUE.md
07_PRICE_ANALYTICS_AND_REPORTING.md
08_MVP_DELIVERY_ROADMAP.md
09_CODEX_PROMPTS.md
10_IMPLEMENTATION_CHECKLIST.md
```

## Backend principle

```text
Raw snapshots are immutable.
Parsers are versioned.
Grouping is conservative.
Human review beats weak automation.
Price history is append-only.
Reports only use approved or high-confidence groups.
```

## Schema principle

The existing UUID-based raw SQL migrations in `db/migrations/` are the source of truth for backend storage.

Use the current table vocabulary:

```text
raw_product_snapshots
products
price_observations
equivalence_groups
product_group_memberships
collection_targets
ingestion_jobs
ingestion_job_targets
```

Do not create parallel `source_products`, `product_snapshots`, `group_definitions`, `group_memberships`, `scrape_runs` or `retailer_configs` tables. Add missing backend-pipeline concepts with the next unused numbered SQL migration under `db/migrations/`.

## Main system modules

```text
basketguard/
  app/
    api/
    core/
    db/
    models/
    schemas/
    services/
  ingestion/
    retailers/
    discovery/
    fetchers/
    extractors/
    snapshots/
  normalisation/
    units.py
    pack_sizes.py
    prices.py
    promotions.py
  parsing/
    brand_owner.py
    tier.py
    product_type.py
    cereal.py
    fish.py
    dairy.py
    meat.py
  grouping/
    definitions/
    matcher.py
    scoring.py
    exclusions.py
  review/
    queue.py
    decisions.py
  analytics/
    price_history.py
    yoy.py
    shrinkflation.py
    basket.py
  tests/
    fixtures/
    snapshots/
    grouping/
```

## Functional phases

| Phase | Goal | Primary output |
|---|---|---|
| 1 | Prove the data loop | One retailer, seed URLs, two groups, price history |
| 2 | Multi-retailer comparison | Tesco/Asda/Sainsbury's/Morrisons equivalent-group comparisons |
| 3 | Human review | Controlled approval/rejection before risky groups pollute data |
| 4 | Price intelligence | YoY, 30/90-day movement, retailer gaps, shrinkflation suspects |
| 5 | Hardening | Drift detection, parser versioning, replay, monitoring, backfill |

## Minimum viable product

The first useful BasketGuard backend should support:

1. fixed retailer seed URLs;
2. daily snapshot fetches;
3. parsed product title, price, unit price, pack size, category breadcrumb, image URL and availability;
4. unit normalisation;
5. group matching for low-risk own-brand products;
6. price observations;
7. retailer comparison reports;
8. basic review queue for uncertain products;
9. repeatable tests using recorded fixtures.

## Do not start with

Avoid these until the core data loop is proven:

1. microservices;
2. Kafka;
3. Spark;
4. ML-first matching;
5. browser automation of logged-in baskets;
6. every supermarket category;
7. a public-facing app before admin/review quality exists;
8. scraping without immutable snapshots.
