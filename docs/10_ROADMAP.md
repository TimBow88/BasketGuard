# Roadmap

This roadmap is strategic product sequencing, not the active task board.
Linear is the single source of truth for planned work, current status,
priority, dependencies and ownership. GitHub manages change control for
accepted repository changes.

## Phase 0 — Discovery and validation

Objective: prove the problem and define the product universe.

Tasks:

1. define first 100 product groups;
2. pick initial retailers;
3. manually build 20 to 30 equivalence groups;
4. collect sample prices manually or semi-automatically;
5. mock weekly report;
6. validate with potential users.

Exit criteria:

- users understand the report instantly;
- at least 10 obvious price outliers can be shown;
- product-equivalence structure feels valid.

## Phase 1 — Prototype ingestion

Objective: collect repeatable price observations.

Tasks:

1. create retailer table;
2. create product table;
3. create price observation table;
4. build scraper for one retailer;
5. add raw snapshot storage;
6. parse price, unit price and pack size;
7. schedule daily collection;
8. add scrape health logs.

Exit criteria:

- daily price collection works for at least 50 products at one retailer;
- raw and parsed data are stored;
- failures are visible.

## Phase 2 — Multi-retailer MVP

Objective: compare equivalent products across retailers.

Tasks:

1. add Tesco, Asda, Sainsbury's and Morrisons;
2. build 100 equivalence groups;
3. create group membership table;
4. add unit normalisation;
5. calculate current cheapest equivalent;
6. calculate price premium.

Exit criteria:

- 100 product groups have at least 3 retailer matches;
- current comparison works reliably;
- obvious bad comparisons are excluded.

## Phase 3 — Historical analytics

Objective: detect price behaviour over time.

Tasks:

1. calculate 7-day, 30-day, 90-day and YoY changes;
2. calculate competitor median YoY;
3. calculate retailer excess inflation;
4. add promotion quality logic;
5. add early shrinkflation detection;
6. create offender score.

Exit criteria:

- weekly offender list can be generated;
- each finding includes evidence and confidence;
- false positives are manageable.

## Phase 4 — User-facing MVP

Objective: launch a private beta.

Tasks:

1. professionalise the dashboard shell and navigation using [UI professionalisation plan](14_UI_PROFESSIONALISATION_PLAN.md);
2. build the weekly verdict, worst-offender and basket-comparison views;
3. add product detail pages;
4. design loading, empty, stale-data, missing-retailer and low-confidence states;
5. add watchlist;
6. create weekly report email;
7. add basic auth;
8. add feedback on product matches;
9. add admin review queue.

Exit criteria:

- users can track items;
- weekly report sends automatically;
- users can understand and act on recommendations.
- consumer-facing UI feels credible, responsive and evidence-backed rather than like an internal demo.

## Phase 5 — Receipt import

Objective: make BasketGuard personal.

Tasks:

1. upload receipt image/PDF;
2. parse receipt items;
3. match receipt items to products/equivalence groups;
4. build personal basket comparison;
5. calculate avoidable overspend;
6. support email receipt import later.

Exit criteria:

- a user can upload a receipt;
- BasketGuard identifies major basket items;
- weekly report reflects actual purchases.

## Phase 6 — Browser extension

Objective: warn users while shopping.

Tasks:

1. detect supported supermarket product pages;
2. show price history overlay;
3. show competitor equivalent warning;
4. show weak promotion warning;
5. link to BasketGuard item page.

Exit criteria:

- when browsing Tesco, user sees relevant warnings in context;
- extension does not require a full app workflow.

## Phase 7 — Commercial hardening

Objective: reduce platform and legal risk.

Tasks:

1. legal review of scraping and wording;
2. data-source diversification;
3. licensed data investigation;
4. privacy audit;
5. security review;
6. monitoring and alerting;
7. improved regional price support.

Exit criteria:

- product is safe enough for public launch;
- data source risk is understood and mitigated;
- user-facing claims are defensible.
