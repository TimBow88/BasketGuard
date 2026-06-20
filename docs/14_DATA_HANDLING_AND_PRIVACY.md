# Data Handling and Privacy

## Status

**Governing policy.** Project-owner decision recorded 2026-06-17 (see Linear
BAS-46, and BAS-54 security & privacy baseline / BAS-48 decision log). This
document is the leading constraint on data-handling design across BasketGuard.
It is not legal advice.

## Core decision: no personal data retention

**BasketGuard does not retain personal data.** The system is intentionally **not
set up for GDPR-scope personal-data processing**, so the design stays out of that
scope rather than trying to comply within it.

**GDPR plays the leading role in data-handling design** — it is the governing
constraint considered first, not an afterthought.

## What this means in practice

- **Collect and store product/price data only** — retailer, product, pack size,
  prices (shelf / loyalty / promotion), unit price, availability, observation
  dates, provenance and raw HTML snapshots of public product pages.
- **No accounts and no user/personal data** while this policy stands.
- **No receipt import.** Receipts can contain purchase habits, location, payment
  fragments, loyalty identifiers, timestamps and household information — all
  personal data — so receipt import is **out of scope** under this policy.
- Any feature that would introduce personal data (accounts, receipt import, the
  BAS-46 §7 privacy gate) is a **hard stop**: it cannot proceed without an
  explicit, separate decision and the BAS-54 privacy baseline being met first.

## Enforcement

- Ingestion and storage paths must carry **non-personal** retailer product/price
  observations only.
- The feasibility spike and any collection handle product/price data only; no
  user, account or personal data is captured or stored.
- Reviewers should treat the introduction of any personal-data field as a
  policy breach to be raised, not a routine change.

## Relationship to other docs

- `docs/09_RISKS_LEGAL_TRUST.md` — broader legal/trust risks; its privacy section
  is superseded by this policy where they differ (this document leads).
- `services/ingestion/README.md` — ingestion scope and the feasibility spike.
- Linear BAS-46 (legal & compliance gate), BAS-54 (security & privacy baseline),
  BAS-48 (decision log).
