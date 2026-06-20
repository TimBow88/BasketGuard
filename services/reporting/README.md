# BasketGuard Reporting

Generates weekly BasketGuard reports from analytics-ready product comparison data.

Current scope:

- fixture-backed weekly report generation;
- structured JSON-compatible report payloads;
- plain-text weekly report rendering;
- retailer basket comparison;
- ranked offender evidence and recommendations;
- a query-based group comparison report against a DB-API PostgreSQL connection;
- a query-based group price history report over a rolling day window;
- a query-based retailer gap report across equivalence groups;
- a query-based review-required products report over open review queue items.

This service does not send email yet.

## Group Comparison Report

`fetch_group_comparison(connection, group_slug)` returns the latest eligible
price observation per retailer for one equivalence group:

- eligibility requires a `product_group_memberships` row that is either
  human-approved or auto-matched at or above the confidence floor
  (`DEFAULT_MIN_AUTO_MATCH_CONFIDENCE`, 0.92), so needs-review and rejected
  products never appear;
- each `GroupComparisonEntry` carries product title, shelf/effective price,
  unit price and basis, pack size, availability, `collected_at` and the raw
  snapshot ID for audit;
- entries are sorted cheapest-first by unit price, and the report exposes
  `cheapest`, `most_expensive` and `unit_price_gap` helpers.

The query uses PostgreSQL `DISTINCT ON` per retailer ordered by
`collected_at DESC`. Tests run against a fake DB-API connection; no live
database is required. HTTP access is provided by the FastAPI wrapper in
`services/api`; this package remains the reporting query/rendering layer.

## Group Price History Report

`fetch_group_price_history(connection, group_slug, window_days=90)` returns the
eligible price observations per retailer over a rolling day window. It reuses
the comparison report's shared join path (`GROUP_OBSERVATION_JOIN`) and
membership eligibility predicate (`MEMBERSHIP_ELIGIBILITY_CLAUSE`), so the same
human-approved / auto-match confidence rules apply and needs-review or rejected
products never appear.

- observations are filtered to the last `window_days` via
  `collected_at >= now() - make_interval(days => %s)` and ordered oldest-first;
- results group into `RetailerPriceHistory` series, each with `first`, `latest`
  and `unit_price_change` helpers and every `PriceHistoryPoint` carrying its raw
  snapshot ID for audit;
- `window_days` must be positive; the confidence floor is overridable.

## Retailer Gap Report

`fetch_retailer_gaps(connection, group_slugs)` reports, per group, the unit-price
gap between the cheapest and most expensive retailer. It reuses
`fetch_group_comparison` for each group (the latest eligible observation per
retailer), so the same eligibility rules apply.

- each `RetailerGap` carries the cheapest/most-expensive retailer and unit
  price, absolute and percentage unit-price gap, the unit price basis, the
  observation date (`as_of`), and the retailer/missing-retailer counts;
- the "missing retailers" for a group are those seen elsewhere in the same
  report but absent from that group's comparison, so missing coverage is
  visible without a separate query;
- a group with fewer than two retailers has no computable gap (`None`);
- `RetailerGapReport.widest_gap_first` orders groups by percentage gap.

## Review-Required Products Report

`fetch_review_required_products(connection, group_slug=None)` lists open
`review_queue_items` oldest-first, joined to the linked product (when present),
retailer, proposed equivalence group and raw snapshot evidence.

- each `ReviewRequiredItem` carries product title and URL (coalesced from the
  product row or the raw snapshot), retailer, proposed group slug, match
  confidence and reason, `created_at` and the raw snapshot ID;
- snapshot-only items without a product link are tolerated — the retailer
  resolves through the snapshot and missing fields stay `None`;
- resolved items are excluded; review decision actions are out of scope here.

This completes the four required MVP reports: group comparison, group history,
retailer gaps and review-required products.
