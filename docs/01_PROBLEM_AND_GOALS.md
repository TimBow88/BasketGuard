# Problem and Goals

## Problem

Current UK grocery comparison tools are useful for checking the price of a specific product today, but they do not clearly answer whether a supermarket has disproportionately increased prices across comparable products.

The existing tools usually operate at SKU level. This creates problems because equivalent products are split apart:

- Tesco Chopped Tomatoes 400g;
- Asda Chopped Tomatoes 400g;
- Sainsbury's Chopped Tomatoes 400g;
- Morrisons Chopped Tomatoes 400g.

A user does not want four disconnected product pages. They want to know:

> Which retailer is now overcharging for standard own-brand chopped tomatoes?

## Primary user goals

### Goal 1 — Identify price spikes

Show when a product or product group has increased unusually quickly.

Example:

> Tesco own-brand chopped tomatoes are up 55% YoY.

### Goal 2 — Compare against competitors

Separate general inflation from retailer-specific increases.

Example:

> Tesco is up 55%, while competitor median is up 8%.

### Goal 3 — Compare equivalent products

Group products by comparable use case, quality tier, pack size and unit basis.

Example:

> Compare standard own-brand chopped tomatoes with standard own-brand chopped tomatoes, not premium or organic alternatives.

### Goal 4 — Detect shrinkflation

Identify when pack size reduces while shelf price remains the same or increases.

Example:

> Pack size fell from 500g to 450g. Effective price per kg increased 11.1%.

### Goal 5 — Assess promotion quality

Determine whether a Clubcard, Nectar or other offer is genuinely strong against historical pricing.

Example:

> Clubcard price is lower than shelf price but only 3% below the 12-month median. Weak offer.

### Goal 6 — Produce simple action

The final output should be a recommendation.

Examples:

- buy at Asda this week;
- avoid Tesco for this item;
- wait for promotion;
- switch to own-brand;
- no issue detected.

## Non-goals

BasketGuard should not initially try to:

1. scrape every grocery product in the UK;
2. replace a full online supermarket shop;
3. provide nutrition advice;
4. make legal claims of illegal price gouging;
5. compare highly subjective products like fresh meat cuts in early MVP;
6. solve every postcode-level price variation at launch.

## Success metrics

### User value metrics

- Weekly savings identified per user.
- Number of high-confidence switch recommendations.
- Percentage of user's tracked basket covered by equivalence groups.
- Alert usefulness rating.
- Repeat weekly engagement.

### Data quality metrics

- Price collection success rate.
- Product matching confidence.
- Human-review correction rate.
- Duplicate product detection accuracy.
- Unit-price normalisation accuracy.
- Shrinkflation detection accuracy.

### Product metrics

- Watchlist creation rate.
- Receipt upload completion rate.
- Weekly report open rate.
- Alert click-through rate.
- Paid conversion rate, if monetised.
