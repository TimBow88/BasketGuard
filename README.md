# BasketGuard

BasketGuard is a UK grocery price-behaviour tracker. It is intended to flag retailer-specific price spikes, weak promotions, shrinkflation, and poor-value outliers across comparable supermarket products.

The product should answer:

> Which supermarket is disproportionately increasing the price of things I actually buy, compared with equivalent products elsewhere?

## Repository Structure

```text
apps/
  web/                         Frontend web app
  api/                         Backend API
packages/
  shared/                      Shared types and utilities
  product-normalisation/       Product parsing, unit conversion, and equivalence logic
  analytics/                   Price metrics, offender scoring, and confidence logic
services/
  ingestion/                   Retailer and receipt ingestion workers
  reporting/                   Weekly reports and alert generation
db/
  migrations/                  PostgreSQL schema migrations
docs/                          Product, architecture, data, UX, and roadmap docs
tests/                         Cross-package and integration tests
```

## Documentation

Start with [docs/README.md](docs/README.md). The numbered documents in `docs/` are the source of truth for the initial MVP scope and implementation sequence.

## Current Status

This repository is at kickoff scaffold stage. No application code or runtime tooling has been added yet.

Recommended next implementation task:

> Implement the initial PostgreSQL schema based on `docs/07_DATABASE_SCHEMA.md`.
