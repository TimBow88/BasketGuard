# Reporting and UX

## Product principle

BasketGuard should be blunt, fast and evidence-based.

The user should not need to inspect hundreds of products. They should get a ranked report of where they are likely overpaying.

## Core dashboard

The main screen should answer:

1. Which retailer is worst for my basket this week?
2. Which products are the biggest offenders?
3. Where should I switch?
4. How much could I save?
5. How confident is the app?

## Main dashboard example

```text
This week's basket warning

Tesco is currently the worst-value retailer for your tracked basket.

Estimated avoidable overspend:
£11.60 versus cheapest equivalent basket.

Worst offenders:
1. Chopped tomatoes — Tesco +55% YoY
2. Mature cheddar — Sainsbury's 24% above cheapest
3. Cereal — weak Clubcard offer
4. Washing capsules — Asda 31% above cheapest per wash
```

## Weekly report

A weekly email or app report should be the core MVP output.

### Report sections

1. Executive summary.
2. Worst offender list.
3. Retailer comparison.
4. Basket savings estimate.
5. Notable price spikes.
6. Weak promotions.
7. Shrinkflation alerts.
8. Methodology note.

## Offender card

Each finding should be displayed as a card.

Example:

```text
Tesco — Own-brand chopped tomatoes

Verdict: Avoid at Tesco
Offender score: 82/100
Confidence: 91%

Tesco price is up 55% year-on-year.
Competitor median increase is 8%.
Tesco is now 31% more expensive than the cheapest comparable product.

Cheapest equivalent this week:
Asda Chopped Tomatoes 400g — £0.39

Why flagged:
- Large retailer-specific YoY increase
- High current premium
- Equivalent products available elsewhere
```

## Item detail page

The item detail page should show:

- current retailer prices;
- price history chart;
- YoY changes;
- unit prices;
- pack sizes;
- loyalty prices;
- confidence level;
- equivalence group members;
- recommendation.

Example table:

| Retailer | Product | Current | Unit price | YoY | Notes |
|---|---|---:|---:|---:|---|
| Tesco | Chopped Tomatoes 400g | £0.55 | £1.38/kg | +55% | Outlier |
| Asda | Chopped Tomatoes 400g | £0.39 | £0.98/kg | +5% | Cheapest |
| Sainsbury's | Chopped Tomatoes 400g | £0.42 | £1.05/kg | +8% | Normal |
| Morrisons | Chopped Tomatoes 400g | £0.45 | £1.13/kg | +12% | Normal |

## Language rules

Use direct but legally safer wording.

Good:

- Avoid at Tesco.
- Poor value this week.
- Retailer-specific price spike.
- Weak offer.
- Above competitor median.
- Switch recommended.

Avoid unless legally reviewed:

- illegal price gouging;
- fraud;
- scam;
- cartel;
- profiteering claim stated as fact.

## Tone variants

The app can allow tone settings later.

### Neutral

> Tesco is currently poor value for this product group.

### Direct

> Avoid Tesco for this item this week.

### Aggressive

> Tesco is rinsing you on this item.

Default should be direct but not legally reckless.

## Navigation

Suggested primary tabs:

1. This Week
2. Your Basket
3. Worst Offenders
4. Watchlist
5. Price History
6. Receipts
7. Methodology

## Trust features

Every claim should include a "why" expansion.

Example:

```text
Why we flagged this

- Tesco price increased from £0.35 to £0.55.
- Equivalent products at 3 competitors increased by a median of 8%.
- Tesco is 31% above the cheapest equivalent today.
- Product match confidence is 96%.
```

## Confidence display

Use simple bands:

| Confidence | Label |
|---:|---|
| 90-100% | High confidence |
| 75-89% | Good confidence |
| 60-74% | Moderate confidence |
| <60% | Low confidence; do not show as major alert |

## UX anti-patterns to avoid

Do not copy basic comparison apps that show enormous unfiltered product lists.

Avoid:

- showing every SKU first;
- hiding the recommendation;
- mixing loyalty and non-loyalty prices;
- comparing premium against budget products;
- using unexplained scores;
- overclaiming legal wrongdoing.
