# BasketGuard End-to-End Pipeline

## Pipeline overview

```text
Source registry
  -> Product discovery
  -> Fetch and snapshot
  -> Field extraction
  -> Normalisation
  -> Attribute parsing
  -> Group matching
  -> Human review where needed
  -> Price observations
  -> Daily group aggregation
  -> Reports and alerts
```

## 1. Source registry

Maintain a controlled registry of retailers.

Initial retailers:

```text
tesco
asda
sainsburys
morrisons
waitrose
ocado
aldi_partial
lidl_partial
```

Each retailer config should include:

```yaml
slug: tesco
name: Tesco
base_url: https://www.tesco.com
active: true
requires_javascript: true
supports_sitemap_discovery: true
supports_category_discovery: true
postcode_context_required: maybe
rate_limit_per_minute: 20
fetch_mode: playwright
notes: "Logged-out public catalogue only for MVP."
```

Database mapping:

```text
retailers stores retailer identity.
collection_targets stores allowlisted product/category targets for MVP collection.
ingestion_jobs and ingestion_job_targets track collection attempts.
```

## 2. Product discovery

Product discovery identifies candidate product URLs.

Discovery order:

1. manual seed URLs for MVP;
2. sitemap discovery where available;
3. public category pages;
4. public product pages;
5. search pages only when stable and permitted.

MVP should use manual seed URLs first.

Reason:

The early risk is not discovery coverage. The early risk is proving extraction, normalisation, grouping and price history.

## 3. Fetch and snapshot

Every fetch creates an immutable snapshot.

Snapshot fields:

```text
retailer
source_url
external_product_id
collected_at
http_status
raw_payload_location
raw_json_payload
rendered_text
screenshot_path optional
content_hash
parser_version
ingestion_job_target_id
```

Rules:

1. Do not overwrite snapshots.
2. Do not only store parsed output.
3. Do not parse without linking back to the raw source.
4. Do not delete failed snapshots; failed fetches are useful for drift analysis.

## 4. Field extraction

Extract raw product fields before normalisation.

Minimum fields:

```text
title
retailer
brand
price
currency
unit_price
unit_price_basis
pack_size_text
promotion_text
availability
category_breadcrumb
image_url
product_url
external_product_id
```

Extractor output should be close to the retailer page, not heavily interpreted.

## 5. Normalisation

Normalisation converts messy retailer values into standard mathematical values.

Examples:

```text
500g       -> 0.5 kg
1kg        -> 1.0 kg
75p/100g   -> £7.50/kg
24 pack    -> count = 24, unit_basis = biscuit
4 x 400g   -> total_weight = 1.6 kg
2L         -> 2.0 l
6 x 330ml  -> total_volume = 1.98 l
```

Store both:

1. retailer displayed value;
2. BasketGuard normalised value.

Never destroy the original retailer text.

## 6. Attribute parsing

Attribute parsing converts product data into grouping dimensions.

Example attributes:

```text
category
subcategory
product_type
form
state
brand_owner
tier
flavour
coating
organic
premium
value_range
free_from
gluten_free
lactose_free
vegan
multipack
count
species
cut
```

Parsers should be deterministic first. ML can be added later for suggestions, not auto-matching.

## 7. Group matching

Group matching compares parsed attributes against equivalence group definitions.

Output states:

```text
auto_match
needs_review
no_match
```

Auto-match only when:

1. product type is explicit;
2. tier is clear;
3. brand owner is clear;
4. form is clear;
5. exclusion terms are absent;
6. unit basis is available;
7. pack size is inside group rule;
8. category breadcrumb supports the match.

## 8. Human review

Human review is used for uncertain or medium/high-risk categories.

Review is required when:

1. title is ambiguous;
2. category and title disagree;
3. image suggests a different form;
4. quality tier is unclear;
5. recipe varies materially;
6. unit basis is unreliable;
7. pack size is outside expected range.

Approved/rejected decisions become future test fixtures.

## 9. Price observations

Create an append-only price observation after extraction, normalisation and grouping.

Observation should include:

```text
product_id
raw_snapshot_id
collected_at
shelf_price
effective_price
unit_price
unit_price_basis
availability
promo_type
promo_description
loyalty_price
confidence_level
```

If grouping is uncertain, still store product-level price, but do not use it in public equivalent-group reports.

## 10. Daily group aggregation

Build derived daily summaries from raw observations.

Examples:

```text
daily min price by group and retailer
daily median unit price by group and retailer
current product selected for each retailer/group
availability count
promotion count
confidence distribution
```

Do not replace raw observations with aggregates.

For MVP, reports can query `price_observations` joined through `products`, `product_group_memberships` and `equivalence_groups`. Add a rebuildable daily aggregate table only in a future numbered migration if the query shape needs it.

## 11. Reports

Initial reports:

1. current equivalent price comparison;
2. 7-day change;
3. 30-day change;
4. 90-day change;
5. year-on-year change once enough history exists;
6. retailer gap report;
7. shrinkflation suspects;
8. review-required products.

## 12. Error handling

All pipeline stages should record structured failures.

Failure types:

```text
fetch_failed
extract_failed
normalisation_failed
parser_failed
matching_failed
review_required
price_missing
unit_price_missing
category_missing
image_missing
availability_unknown
```

A failed stage should not silently disappear.

## 13. Pipeline success criteria

A collection run is successful when:

1. expected seed URLs were attempted;
2. `ingestion_jobs` and `ingestion_job_targets` were recorded;
3. `raw_product_snapshots` were created;
4. extraction produced required fields;
5. normalisation succeeded or failure was recorded;
6. parser version was recorded;
7. matching produced auto/review/no-match state;
8. price observations were appended;
9. ingestion-job summary was stored.
