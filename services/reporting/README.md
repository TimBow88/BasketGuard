# BasketGuard Reporting

Generates weekly BasketGuard reports from analytics-ready product comparison data.

Current scope:

- fixture-backed weekly report generation;
- structured JSON-compatible report payloads;
- plain-text weekly report rendering;
- retailer basket comparison;
- ranked offender evidence and recommendations;
- a query-based group comparison report against a DB-API PostgreSQL connection.

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
database is required. There are no HTTP endpoints yet.
