# BasketGuard Price Analytics and Reporting

## Purpose

BasketGuard should convert approved product-equivalence data into clear supermarket price intelligence.

The user-facing value is not a product list. The value is identifying meaningful price movement and retailer divergence across equivalent own-brand products.

## Reporting principle

```text
Reports must be blunt enough to be useful and evidence-based enough to defend.
```

Avoid legal conclusions unless legally reviewed.

Prefer:

```text
Tesco own-brand cornflakes are up 55% year-on-year and are currently 31% more expensive than Asda's comparable own-brand product.
```

Avoid:

```text
Tesco is price gouging.
```

## Base analytics

### Current equivalent price

For each group and retailer:

```text
current product
current price
current unit price
pack size
availability
promotion flag
confidence level
last observed date
```

### Retailer comparison

For each group:

```text
lowest current unit price
highest current unit price
retailer gap absolute
retailer gap percentage
ranking by unit price
confidence warning if any retailer is missing or review-only
```

### Price movement

For each group/retailer:

```text
7-day change
30-day change
90-day change
year-on-year change
all-time low/high since tracking began
```

### Basket-level tracking

A basket is a fixed list of group slugs.

Example:

```yaml
slug: basic_weekly_own_brand_basket
name: Basic weekly own-brand basket
groups:
  - own_brand_cornflakes_standard
  - own_brand_porridge_oats_standard
  - own_brand_spaghetti_standard
  - own_brand_baked_beans_standard
  - own_brand_semi_skimmed_milk_2l_standard
  - own_brand_plain_flour_standard
  - own_brand_granulated_sugar_standard
```

Basket report:

```text
basket cost by retailer
basket cost movement over time
missing item count
substitution confidence
largest contributors to increase
```

## Shrinkflation detection

Shrinkflation is suspected when:

1. product identity appears stable;
2. pack size decreases;
3. shelf price remains similar or increases;
4. unit price increases materially;
5. group membership remains equivalent.

Store suspected cases separately for review.

Example:

```text
Product: Own-brand cereal
Old size: 500g
New size: 450g
Shelf price: £1.25 -> £1.25
Unit price: £2.50/kg -> £2.78/kg
Flag: pack_size_reduction_price_held
```

## Promotion masking

Promotion masking occurs when a temporary offer hides an underlying price increase.

Track:

1. standard shelf price;
2. current selling price;
3. loyalty price;
4. promotion text;
5. promotion duration;
6. post-promotion price.

Do not mix loyalty-card prices with standard prices unless report explicitly says so.

## Confidence labels

Every report row should carry a confidence label.

```text
high
medium
low
insufficient_data
```

### High confidence

1. group is low-risk;
2. product membership is auto-approved or human-approved;
3. unit basis is reliable;
4. current observation is recent;
5. retailer coverage is complete.

### Medium confidence

1. group is medium-risk;
2. some review decisions involved;
3. one retailer missing;
4. pack-size spread is acceptable but not ideal.

### Low confidence

1. group is high-risk;
2. category data is incomplete;
3. unit basis is weak;
4. product may be a poor substitute.

Low-confidence data should be hidden from public headline reports by default.

## Initial report endpoints

```text
GET /reports/group-comparison/{group_slug}
GET /reports/group-history/{group_slug}
GET /reports/retailer-gaps
GET /reports/biggest-risers
GET /reports/shrinkflation-suspects
GET /reports/review-required
GET /reports/basket/{basket_slug}
```

Database mapping:

Initial endpoints should read from `price_observations` joined through `products`, `product_group_memberships`, `equivalence_groups` and `retailers`. Generated warnings can be stored in `analytics_findings`, and generated report payloads can be stored in `reports`.

## Example group comparison response

```json
{
  "group_slug": "own_brand_cornflakes_standard",
  "group_name": "Own-brand cornflakes",
  "unit_basis": "kg",
  "as_of": "2026-06-08",
  "confidence": "high",
  "retailers": [
    {
      "retailer": "Tesco",
      "product_title": "Tesco Corn Flakes 500g",
      "price": 1.25,
      "unit_price": 2.50,
      "pack_size": "500g",
      "availability": "in_stock",
      "promotion_flag": false
    },
    {
      "retailer": "Asda",
      "product_title": "Asda Corn Flakes 500g",
      "price": 0.95,
      "unit_price": 1.90,
      "pack_size": "500g",
      "availability": "in_stock",
      "promotion_flag": false
    }
  ],
  "summary": {
    "lowest_retailer": "Asda",
    "highest_retailer": "Tesco",
    "gap_absolute_per_kg": 0.60,
    "gap_percentage": 31.6
  }
}
```

## Example headline report

```text
Own-brand cornflakes
Tesco: £2.50/kg
Asda: £1.90/kg
Difference: Tesco is 31.6% higher than Asda
30-day movement: Tesco +8.7%, Asda unchanged
Confidence: High
```

## Data requirements for public reports

A group can appear in a public report only when:

1. the `equivalence_groups` row is approved or otherwise eligible for reporting;
2. the `product_group_memberships` row is high-confidence or human-reviewed;
3. latest observation is recent;
4. unit basis is valid;
5. confidence is medium or high;
6. no blocking review issue exists.

## Initial analytics jobs

### daily_group_price_job

Builds daily group prices from latest observations. For MVP this can be a query or report payload. If repeated reporting needs a materialized table, add `daily_equivalence_group_prices` in a future `0003` migration.

### retailer_gap_job

Calculates current highest/lowest retailer gaps by group.

### price_movement_job

Calculates movement over 7/30/90 days.

### shrinkflation_suspect_job

Finds pack-size reductions and unit-price jumps.

### review_required_job

Summarises uncertain matches and extractor issues.

## Reporting MVP

First report should be:

```text
Own-brand equivalent price comparison across Tesco, Asda, Sainsbury's and Morrisons for cornflakes and porridge oats.
```

Do not build complex dashboards before this works.
