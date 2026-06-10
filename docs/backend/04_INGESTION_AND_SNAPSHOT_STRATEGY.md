# BasketGuard Ingestion and Snapshot Strategy

## Purpose

The ingestion system collects public supermarket product data and preserves enough evidence to support reliable price history, parser debugging and grouping audits.

## Ingestion principle

```text
Fetch broadly enough to track price history.
Store raw evidence before parsing.
Parse conservatively.
Never trust a scrape without a snapshot.
```

## Retailer source registry

Each retailer should have a config file.

Example:

```yaml
slug: tesco
name: Tesco
base_url: https://www.tesco.com
active: true
fetch_mode: playwright
requires_javascript: true
supports_sitemap_discovery: true
supports_category_discovery: true
rate_limit_per_minute: 20
postcode_context: null
logged_in_required: false
mvp_strategy: manual_seed_urls
```

## MVP ingestion strategy

Start with manual seed URLs.

Store those seed URLs as allowlisted `collection_targets` in the current database model. Do not introduce a separate `source_products` seed table.

Do not build full supermarket crawling first.

The first version should prove:

1. can fetch product pages;
2. can store raw snapshots;
3. can extract core fields;
4. can normalise units;
5. can match low-risk groups;
6. can append daily prices;
7. can compare retailers.

## Discovery stages

### Stage 1: Manual seed URLs

Use manually maintained seed files.

Example:

```yaml
group_slug: own_brand_cornflakes_standard
retailers:
  tesco:
    - https://example.com/tesco-cornflakes
  asda:
    - https://example.com/asda-cornflakes
  sainsburys:
    - https://example.com/sainsburys-cornflakes
  morrisons:
    - https://example.com/morrisons-cornflakes
```

This is sufficient for MVP.

### Stage 2: Category discovery

Add category page crawling when seed data proves valuable.

Crawler should capture candidate product URLs, not immediately trust them.

### Stage 3: Sitemap discovery

Use retailer sitemaps where available.

This is useful for coverage but can add noise. Discovered products still require extraction, normalisation and matching.

### Stage 4: Search discovery

Use public search pages only if they are stable, permitted and not dependent on logged-in user state.

## Fetch modes

### httpx fetch

Use for:

1. static pages;
2. JSON endpoints where clearly exposed;
3. sitemap files;
4. category pages that render server-side.

### Playwright fetch

Use for:

1. JavaScript-rendered pages;
2. product pages where price appears after hydration;
3. pages where structured data is loaded client-side;
4. screenshot/debug needs.

## Snapshot artefacts

For every product fetch, store:

```text
raw HTML
raw JSON if discovered
rendered text
final URL
HTTP status
response headers subset
screenshot optional
content hash
fetch timestamp
fetch mode
retailer config version
```

Database mapping:

```text
ingestion_jobs records the overall run.
ingestion_job_targets records each attempted target.
raw_product_snapshots records immutable source evidence.
products stores the cleaned retailer-specific product identity.
price_observations links a product back to the raw snapshot used for the price.
```

## Snapshot path convention

```text
/data/snapshots/{retailer_slug}/{yyyy}/{mm}/{dd}/{source_product_id}/{snapshot_id}/
  raw.html
  raw.json optional
  rendered.txt
  screenshot.png optional
  metadata.json
```

## Snapshot metadata example

```json
{
  "retailer": "tesco",
  "source_product_id": 123,
  "snapshot_id": 456,
  "url": "https://www.example.com/product",
  "fetched_at": "2026-06-08T10:00:00Z",
  "fetch_mode": "playwright",
  "http_status": 200,
  "content_hash": "sha256:...",
  "parser_version": "0.1.0"
}
```

## Extractor responsibilities

Retailer-specific extractors should produce a shared output shape.

```python
class ExtractedProduct(BaseModel):
    title: str | None
    brand: str | None
    price: Decimal | None
    currency: str = "GBP"
    unit_price_text: str | None
    pack_size_text: str | None
    category_breadcrumb: str | None
    image_url: str | None
    availability: str | None
    promotion_text: str | None
    external_product_id: str | None
    raw_fields: dict
```

Extractor rules:

1. Extractors should not decide group membership.
2. Extractors should preserve raw text.
3. Extractors should emit missing-field warnings.
4. Extractors should be tested with recorded HTML fixtures.

## Ingestion job lifecycle

```text
queued
running
completed
completed_with_warnings
failed
cancelled
```

Map these states to the existing `ingestion_jobs.status` and `ingestion_job_targets.status` values. If a more detailed status vocabulary is needed, add it with a future numbered migration instead of creating a parallel scrape-run table.

## Ingestion failure types

```text
network_error
blocked_or_challenged
not_found
selector_missing
price_missing
unit_price_missing
pack_size_missing
category_missing
image_missing
availability_unknown
parse_exception
```

## Rate limiting

Use conservative defaults.

Initial recommendation:

```text
Per retailer: 10-30 product pages per minute
Concurrency: 1-3 browser pages per retailer
Jitter: enabled
Retries: 2 max
```

BasketGuard does not need high-frequency scraping for MVP. Daily price tracking is enough.

## Location and account context

Every scrape must declare context.

```text
logged_out_public
logged_in_account
postcode_context
collection_store_context
delivery_context
```

MVP recommendation:

```text
logged_out_public where possible
one fixed postcode context where required
no logged-in basket scraping
```

## Promotion capture

Capture promotion text separately from base price.

Fields:

```text
base_price if available
current_price
membership_price
promotion_text
promotion_type
promotion_end_date if available
multibuy_text
```

Do not treat a loyalty-card price as the same as standard public price.

## Drift detection

A retailer extractor may have drifted when:

1. sudden price missing rate increases;
2. unit price missing rate increases;
3. title extraction fails;
4. category breadcrumbs disappear;
5. content hash changes drastically across many products;
6. number of product candidates falls sharply.

Drift should create an admin warning, not silently corrupt data.

## Snapshot replay

The system should support replaying old snapshots against a new parser.

Use cases:

1. parser bug fixes;
2. grouping rule changes;
3. new unit normalisation logic;
4. backfilling attributes;
5. comparing parser versions.

Replay should not refetch pages.
