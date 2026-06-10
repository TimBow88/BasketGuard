# Data Ingestion

## Purpose

BasketGuard needs regular product and price data from UK supermarkets. The ingestion system should collect, parse, store and monitor product price observations.

## Data sources

### Source A — Retailer website collection

Automated collection from online grocery pages or APIs where available.

Target fields:

- retailer;
- product name;
- product URL;
- retailer product ID;
- price;
- loyalty price;
- was price;
- unit price;
- pack size;
- promotion text;
- availability;
- category;
- image URL;
- collection timestamp;
- postcode or location context.

### Source B — User receipt import

Receipts may come from:

- uploaded images;
- PDF receipts;
- email receipts;
- online grocery order confirmations;
- copy-pasted order summaries.

Receipt import supports user-specific basket analysis and reduces dependency on full-catalogue scraping.

### Source C — Public context data

Public inflation or food-category data can be used for context but should not replace item-level collection.

Examples:

- ONS food inflation data;
- CMA publications;
- public category-level analysis.

### Source D — Licensed data

Potential later-stage route if commercial scale justifies it.

## Collection strategy

Do not crawl every product initially. Start with a controlled catalogue.

Large supplier catalogues should be built as explicit allowlisted target seeds,
then processed by the supplier batch workflow. The process records one
`ingestion_jobs` row per batch, one `ingestion_job_targets` row per attempted
product, immutable raw snapshots for successful fetches, and skipped/error rows
for unsupported or failed targets. This supports thousands of staged entries
without category crawling or product discovery.

### MVP schedule

| Data type | Frequency |
|---|---:|
| User watchlist products | Daily |
| Core staple catalogue | Daily |
| Wider catalogue | 2 to 3 times per week |
| Product metadata refresh | Weekly |
| Full revalidation | Monthly |

## Raw data retention

Always store raw snapshots or raw extracted payloads.

Reasons:

1. auditability;
2. parser debugging;
3. evidence for user-facing claims;
4. recovery when parsing logic changes;
5. historical comparison.

## Crawler design

Recommended tools:

- Playwright for dynamic pages;
- Crawlee or Scrapy for orchestration;
- Redis/BullMQ, Celery or similar for queues;
- S3-compatible storage for raw snapshots;
- PostgreSQL for cleaned observations.

## Rate limiting

Crawlers should be conservative.

Rules:

1. crawl only required products;
2. cache pages aggressively;
3. avoid repeated unnecessary requests;
4. randomise timing modestly;
5. monitor block/error rates;
6. do not rely on a single IP/session/account;
7. respect legal review conclusions before production launch.

Batch workflow defaults should stay conservative:

1. start with `--max-targets`;
2. process in bounded batches;
3. keep live provider feature flags disabled unless intentionally collecting;
4. stage unsupported suppliers instead of attempting generic parsing;
5. review block/error rates before increasing target volume.

## Postcode handling

Prices and availability may vary by region.

Initial approach:

- use one default postcode region for MVP;
- add multiple regional contexts later.

Suggested regional sample:

- London;
- Birmingham;
- Manchester;
- Leeds;
- Glasgow;
- Cardiff;
- Bristol;
- Newcastle.

Each price observation must store its postcode or region context.

## Loyalty pricing

Separate price types:

- shelf price;
- loyalty price;
- multibuy price;
- was price;
- effective price.

Never collapse loyalty and non-loyalty pricing into a single field without preserving the original values.

## Failure handling

Each ingestion job should record:

- success or failure;
- retailer;
- product count attempted;
- product count collected;
- parser error count;
- changed selector warnings;
- missing price count;
- blocked or CAPTCHA indicators.

## Ingestion output contract

Cleaned observation example:

```json
{
  "retailer": "Tesco",
  "external_product_id": "123456789",
  "product_name": "Tesco Chopped Tomatoes 400G",
  "url": "https://...",
  "shelf_price": 0.55,
  "loyalty_price": null,
  "was_price": null,
  "unit_price": 1.38,
  "unit_price_basis": "kg",
  "pack_size_value": 400,
  "pack_size_unit": "g",
  "promotion_text": null,
  "availability": "in_stock",
  "postcode_context": "SW London",
  "collected_at": "2026-06-07T08:00:00Z"
}
```
