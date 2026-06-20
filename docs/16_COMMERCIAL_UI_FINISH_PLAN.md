# Commercial UI Finish Plan

## Purpose

This document defines the commercial finish pass for the BasketGuard MVP web UI. The goal is to move the static dashboard from a functional prototype into a product-grade decision surface that looks credible in customer, investor and internal review settings.

Linear remains the single source of truth for live task status. GitHub remains the change-control path for accepted UI changes. This document is durable design and implementation guidance.

## Product standard

BasketGuard should feel like a focused price-intelligence product, not a generic report page.

The interface should communicate:

1. confidence before claims;
2. evidence before drama;
3. a clear action for the week;
4. strong separation between consumer report views and operator tools;
5. polished commercial restraint without decorative noise.

## Current finish gap

The first professionalisation pass created the right content structure, but the UI still read as basic because:

- the header behaved like a document title rather than a product command surface;
- navigation was tab-heavy and visually flat;
- the first screen lacked a premium decision-desk frame;
- global report status was not visible enough;
- cards, metrics and panels had limited hierarchy;
- mobile worked, but the desktop composition did not yet feel like a commercial app.

## Target shell

The commercial shell should include:

- persistent report/operator navigation on desktop;
- a responsive horizontal navigation treatment on narrower screens;
- a command header with freshness, confidence and coverage metrics;
- a clear report status indicator;
- icon-only refresh/export actions with accessible names;
- no marketing hero and no decorative background effects.

## Target first screen

The first screen should show:

- a risk index for the top finding;
- a weekly verdict written in safe, direct language;
- evidence caveats for stale or incomplete data;
- freshness and confidence as first-class facts;
- high-level basket metrics;
- top findings and retailer totals without making the user hunt.

## Component quality bar

Commercial-grade components should:

- use stable dimensions so data changes do not cause visible layout shifts;
- show clear hover, focus and selected states;
- keep tables precise and scrollable only where table overflow is intended;
- keep cards compact enough for repeated operational use;
- avoid nested decorative cards;
- avoid one-note colour palettes;
- keep letter spacing at `0`;
- never use colour as the only signal for warning, confidence or status.

## Implementation notes

The current commercial pass updates:

- `apps/web/index.html`
  - adds a product navigation rail;
  - adds a decision-desk header;
  - adds freshness, confidence and coverage command metrics;
  - adds a first-screen risk index.

- `apps/web/styles.css`
  - replaces the flat dashboard styling with a rail/workspace app shell;
  - adds stronger card hierarchy, shadows, spacing and responsive behaviour;
  - keeps 8px radii and stable typography;
  - preserves accessible focus states.

- `apps/web/app.js`
  - populates the risk index;
  - updates global header metrics;
  - updates rail status for loading, stale, loaded and error states.

## Verification checklist

Before accepting a commercial UI pass:

1. Run `node --check apps/web/app.js`.
2. Run `$env:PYTHONDONTWRITEBYTECODE='1'; python -m unittest discover -s tests -v`.
3. Smoke-test desktop and mobile in a browser.
4. Capture new screenshots under `artifacts/ui-professionalisation/`.
5. Confirm no text overlap in the rail, header, verdict panel, metric cards or offender cards.
6. Confirm table overflow is limited to intended comparison tables.
7. Confirm stale-data and API-error states are visible and do not imply certainty.

## Follow-up candidates

Track follow-up work in Linear if needed:

- connect the report shell to API-backed report endpoints;
- add richer charts for price movement once time-series data is available;
- add review queue actions when the admin API is ready for UI integration;
- add an authenticated user/basket model;
- add visual regression tests for the static web shell.
