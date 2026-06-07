# MVP Scope

## MVP objective

Build the smallest useful version of BasketGuard that can produce a weekly report showing price spikes, competitor differences and poor-value outliers across a defined set of staple grocery product groups.

## MVP user promise

> Track your regular supermarket basket and get a weekly warning when one retailer becomes unusually expensive versus equivalent products elsewhere.

## MVP retailers

Initial target retailers:

1. Tesco;
2. Asda;
3. Sainsbury's;
4. Morrisons.

Secondary retailers after MVP:

1. Waitrose;
2. Ocado;
3. Iceland;
4. Aldi;
5. Lidl.

Aldi and Lidl are commercially important but may be harder to use depending on online product and pricing availability.

## MVP categories

Start with 100 to 300 high-frequency staple groups.

Recommended first categories:

- milk;
- butter;
- cheese;
- eggs;
- bread;
- pasta;
- rice;
- tinned tomatoes;
- baked beans;
- tuna;
- cereal;
- oats;
- tea;
- coffee;
- toilet roll;
- kitchen roll;
- washing capsules;
- washing-up liquid;
- dishwasher tablets.

Avoid at MVP stage:

- fresh meat;
- loose fruit and vegetables;
- meal deals;
- highly seasonal items;
- alcohol;
- complex multi-buy confectionery;
- products where quality comparison is too subjective.

## MVP features

### Must have

1. Product watchlist.
2. Retailer product catalogue ingestion.
3. Price history storage.
4. Unit-price normalisation.
5. Product equivalence groups.
6. YoY price comparison.
7. Competitor median comparison.
8. Current cheapest equivalent.
9. Offender score.
10. Weekly report.
11. Simple item detail page.
12. Data confidence indicator.

### Should have

1. Receipt upload.
2. Email receipt import.
3. Loyalty price separation.
4. Promotion quality score.
5. Shrinkflation detection.
6. Regional postcode mode.

### Could have later

1. Browser extension.
2. Push notifications.
3. Full mobile app.
4. User household basket trends.
5. Public price index dashboard.
6. Journalist/export pack.

## MVP report format

The first report should look like this:

```text
Your weekly grocery warning

Your tracked basket is £11.60 more expensive at Tesco than the cheapest equivalent basket.

Worst offenders:

1. Tesco — Chopped tomatoes
   Tesco +55% YoY. Competitor median +8%.
   Current premium over cheapest: +31%.
   Recommendation: buy at Asda or Sainsbury's.

2. Sainsbury's — Mature cheddar
   Current price is 24% above cheapest equivalent.
   Recommendation: switch this week.

3. Tesco — Cereal
   Clubcard price is only 3% below 12-month median.
   Recommendation: weak offer; wait or buy elsewhere.
```

## MVP acceptance criteria

The MVP is successful if it can:

1. collect prices for at least 100 equivalent product groups across 4 retailers;
2. store daily price observations;
3. calculate unit-price adjusted YoY changes;
4. compare each retailer against competitor median;
5. produce a weekly ranked offender report;
6. show enough evidence for each finding that the user trusts it.
