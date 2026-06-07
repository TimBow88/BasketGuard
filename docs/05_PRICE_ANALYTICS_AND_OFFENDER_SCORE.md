# Price Analytics and Offender Score

## Purpose

The analytics engine converts price observations into useful user-facing findings.

It should distinguish:

1. general inflation;
2. retailer-specific inflation;
3. current poor value;
4. promotion distortion;
5. loyalty-card distortion;
6. shrinkflation;
7. temporary availability issues.

## Core metrics

### Current unit price

Use unit price wherever possible.

```text
current_unit_price = effective_price / normalised_pack_size
```

### Year-on-year increase

```text
YoY increase =
  (current_unit_price - unit_price_365_days_ago)
  / unit_price_365_days_ago
```

If exact 365-day data is unavailable, use nearest observation within an acceptable window, for example plus/minus 14 days.

### Competitor median YoY

```text
competitor_median_yoy = median(YoY increase of equivalent products at other retailers)
```

### Retailer excess inflation

```text
retailer_excess_inflation = retailer_yoy - competitor_median_yoy
```

Example:

```text
Tesco YoY: +55%
Competitor median YoY: +8%
Retailer excess inflation: +47 percentage points
```

### Current premium over cheapest equivalent

```text
current_premium =
  (retailer_current_unit_price / cheapest_current_equivalent_unit_price) - 1
```

Example:

```text
Tesco: £1.38/kg
Asda: £0.95/kg
Premium: +45.3%
```

### Historical median comparison

Used to judge whether a promotion is actually good.

```text
historical_discount_strength =
  (historical_12m_median_price - current_effective_price)
  / historical_12m_median_price
```

Example:

```text
Current Clubcard price: £2.50
12-month median: £2.60
Discount vs median: 3.8%
Verdict: weak offer
```

## Shrinkflation detection

Detect when:

1. product lineage is the same or highly similar;
2. pack size decreased;
3. shelf price stayed the same or increased;
4. unit price increased materially.

Example:

```text
Old: £2.00 for 500g = £4.00/kg
New: £2.00 for 450g = £4.44/kg
Effective increase: +11.1%
```

## Weak promotion detection

A promotion may be weak if:

1. loyalty price is close to historical median;
2. shelf price rose before promotion;
3. promotion is worse than recent non-promo price;
4. competitor non-promo price is cheaper;
5. promotion requires excessive multibuy to achieve a normal price.

Suggested labels:

- strong offer;
- normal offer;
- weak offer;
- misleading-looking offer;
- cheaper elsewhere without loyalty.

Avoid legal wording unless reviewed.

## Offender score

The offender score ranks poor-value or suspicious price behaviour.

Initial formula:

```text
Offender Score =
  0.40 * retailer_excess_yoy_inflation_score
+ 0.25 * current_premium_score
+ 0.15 * shrinkflation_score
+ 0.10 * weak_promotion_score
+ 0.10 * volatility_score
```

All inputs should be normalised to 0 to 100.

## Score bands

| Score | Label | Meaning |
|---:|---|---|
| 0-19 | No issue | Price appears normal |
| 20-39 | Watch | Mildly poor value or mild increase |
| 40-59 | Poor value | Noticeable issue |
| 60-79 | Avoid | Strong evidence of poor value |
| 80-100 | Severe outlier | Very large retailer-specific issue |

## Example calculation

```text
Product group: own-brand chopped tomatoes 400g
Retailer: Tesco

Tesco YoY: +55%
Competitor median YoY: +8%
Retailer excess inflation: +47 percentage points

Tesco current unit price: £1.38/kg
Cheapest equivalent: £0.95/kg
Current premium: +45%

Shrinkflation: none detected
Promotion weakness: none
Volatility: medium

Offender score: 82/100
```

User-facing output:

> Avoid at Tesco. This looks like a Tesco-specific price spike, not general category inflation.

## Confidence score

Each finding should include confidence.

Inputs:

- data freshness;
- number of retailers compared;
- equivalence confidence;
- price observation completeness;
- availability consistency;
- unit normalisation reliability.

Example:

```text
Finding confidence: 91%
Reason: 4 retailer equivalents matched, all prices collected within last 24 hours, equivalence group human-reviewed.
```
