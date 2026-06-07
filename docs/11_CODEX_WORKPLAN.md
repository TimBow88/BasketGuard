# Codex Workplan

## Purpose

This document breaks BasketGuard into small implementation tasks suitable for Codex.

The goal is to avoid vague "build the app" prompts. Each task should make the smallest safe change, run tests and report what changed.

## Development principle

Codex should always:

1. inspect the repo first;
2. implement the smallest useful change;
3. add or update tests;
4. run the relevant test suite;
5. fix failures if safe;
6. summarise changed files, test result and next recommended task only.

## Suggested initial repo structure

```text
basketguard/
  apps/
    web/
    api/
  packages/
    shared/
    product-normalisation/
    analytics/
  services/
    ingestion/
    reporting/
  docs/
  db/
    migrations/
  tests/
```

## Prompt 1 — Initialise documentation and repo structure

```text
Create the initial BasketGuard repo structure using the existing docs as the source of truth. Add a clear README, docs index, and placeholder folders for web, api, ingestion, analytics, reporting, shared packages and database migrations. Do not build features yet. Add minimal tooling only where appropriate. Run available checks. Summarise changed files, test/check result, and the next recommended prompt.
```

Confidence: 95%

## Prompt 2 — Add database schema draft

```text
Implement the initial PostgreSQL schema for BasketGuard based on docs/07_DATABASE_SCHEMA.md. Add migrations for retailers, products, raw snapshots, price observations, equivalence groups, product group memberships, users, watchlists, findings and reports. Include sensible indexes and constraints. Add tests or migration validation if the repo supports it. Run checks. Summarise changed files, test/check result, and next recommended prompt.
```

Confidence: 90%

## Prompt 3 — Add product normalisation package

```text
Create the product-normalisation package. Implement utilities to parse common grocery pack sizes, convert grams/kg/ml/litres/pints, normalise unit bases, and classify obvious own-brand/value/premium flags from product names. Add focused tests for milk, cheese, tomatoes, pasta, toilet roll and washing capsules. Keep scope narrow. Run tests. Summarise changed files, test result, and next recommended prompt.
```

Confidence: 88%

## Prompt 4 — Add price analytics package

```text
Create the analytics package. Implement pure functions for current premium over cheapest equivalent, YoY increase, competitor median YoY, retailer excess inflation, historical median comparison, shrinkflation effective increase, and an initial offender score. Add tests using simple fixture data. Do not build UI. Run tests. Summarise changed files, test result, and next recommended prompt.
```

Confidence: 92%

## Prompt 5 — Add seed data fixtures

```text
Add realistic seed fixtures for 10 product equivalence groups across Tesco, Asda, Sainsbury's and Morrisons. Include chopped tomatoes, milk, mature cheddar, pasta, baked beans, cereal, butter, toilet roll, washing capsules and dishwasher tablets. Include historical price observations sufficient to test YoY and current premium calculations. Add tests that generate a ranked offender list from the fixtures. Run tests. Summarise changed files, test result, and next recommended prompt.
```

Confidence: 88%

## Prompt 6 — Build first report generator

```text
Implement a simple report generator that takes analytics findings and outputs a weekly BasketGuard report as structured JSON and plain text. Include summary, worst offenders, retailer comparison, item evidence and recommendations. Use fixture data only. Add tests for report ordering and wording. Run tests. Summarise changed files, test result, and next recommended prompt.
```

Confidence: 90%

## Prompt 7 — Add ingestion interface

```text
Create an ingestion service interface for retailer product observations. Do not scrape live websites yet. Define types/contracts for raw snapshots, parsed products, price observations and ingestion job results. Add a mock ingestion provider using fixture data. Add tests. Run checks. Summarise changed files, test result, and next recommended prompt.
```

Confidence: 92%

## Prompt 8 — Add first crawler behind a feature flag

```text
Add a prototype crawler for one retailer behind a disabled-by-default feature flag. It should collect only a small allowlisted set of product URLs, store raw snapshots, parse price/unit/pack/promo fields where possible, and record failures clearly. Do not make aggressive requests. Add tests around parser functions using saved sample HTML fixtures. Run tests. Summarise changed files, test result, and next recommended prompt.
```

Confidence: 75%

## Prompt 9 — Add admin review model

```text
Add models and basic API routes for reviewing product equivalence matches. Include pending, approved and rejected states; match confidence; match reason; and reviewer notes. Add tests for approving and rejecting a suggested match. Run tests. Summarise changed files, test result, and next recommended prompt.
```

Confidence: 85%

## Prompt 10 — Build basic dashboard

```text
Build the first web dashboard using fixture/report API data. Show this week's basket warning, estimated avoidable overspend, worst offenders, confidence labels and item evidence expansion. Keep styling clean and functional. Do not add authentication unless already present. Add basic UI tests if available. Run checks. Summarise changed files, test/check result, and next recommended prompt.
```

Confidence: 82%

## Prompt 11 — Add receipt import placeholder

```text
Add a receipt import placeholder flow. Users should be able to upload a receipt file, store metadata, and create a pending parse record. Do not implement OCR yet. Add tests for upload metadata handling and validation. Run checks. Summarise changed files, test/check result, and next recommended prompt.
```

Confidence: 82%

## Prompt 12 — Hardening pass

```text
Review the BasketGuard codebase against the docs. Identify gaps, stale placeholders, duplicated concepts and fragile areas. Make only low-risk cleanup changes. Ensure tests pass. Produce a concise gap list and next recommended implementation prompt. Summarise changed files, test result and next prompt.
```

Confidence: 90%
