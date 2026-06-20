# UI Professionalisation Plan

## Purpose

The current static web UI proves the reporting concept, but it still feels like an internal demo. This plan defines the work needed to turn BasketGuard into a professional MVP product surface without changing the core product promise: blunt, fast, evidence-backed supermarket price movement reporting.

This is the implementation-ready UX baseline for the next UI slice. It complements [Reporting and UX](08_REPORTING_AND_UX.md) and should be used before coding changes in `apps/web/`.

Delivery status for this slice lives in Linear. Treat this document as durable
UX/product guidance and baseline context; do not use it as the live task board.
GitHub pull requests manage accepted code and documentation changes.

The follow-on commercial finish standard is documented in
[Commercial UI finish plan](16_COMMERCIAL_UI_FINISH_PLAN.md).

## Product standard

BasketGuard should feel like a serious consumer finance and grocery intelligence tool, not a generic admin dashboard.

The UI should be:

1. evidence-first;
2. readable at a glance;
3. restrained and credible;
4. fast to scan on mobile and desktop;
5. explicit about freshness, confidence, missing data and caveats;
6. safe in its language about retailers and product claims.

## Baseline UI assessment

This assessment describes the pre-professionalisation baseline that led to the
BAS-80 Linear task tree. After implementation starts, use Linear for current
status and GitHub for accepted-change evidence.

The existing `apps/web/` surface already has useful ingredients:

- summary metrics;
- worst-offender cards;
- retailer totals;
- product-group comparison detail;
- manual data capture;
- database/schema visibility.

The professionalisation gap is not the presence of features. The gap is product presentation, hierarchy, interaction quality and trust signalling.

Current weaknesses:

- the top-level story is too generic and does not immediately explain whether action is required;
- the navigation mixes consumer views with operator/data-gathering views;
- evidence is shown, but it is not structured as a defensible claim trail;
- visual treatment is functional but not yet distinctive or polished;
- loading, empty, error, stale-data and low-confidence states are not designed;
- manual capture and database views are useful, but should read as operator/admin surfaces rather than primary consumer UX;
- there is no explicit design acceptance bar for responsive layout, accessibility or screenshot review.

## Target information architecture

The first professional MVP should separate consumer-facing report views from operator views.

Primary consumer views:

1. This Week
2. Worst Offenders
3. Product Detail
4. Basket Comparison
5. Methodology

Operator/admin views:

1. Data Gathering
2. Review Queue
3. Source Health
4. Database Model

The static MVP may keep these in one app, but the navigation must make the split visible. Consumer users should never land first on capture forms, schema cards or internal database concepts.

## First-screen requirements

The first viewport should answer three questions without scrolling:

1. Is there a meaningful warning this week?
2. Which retailer/product group needs attention first?
3. How confident and fresh is the evidence?

Required first-screen elements:

- a clear weekly verdict;
- worst retailer or "no major warning" state;
- estimated avoidable overspend;
- data freshness;
- confidence band;
- top three offender preview;
- primary action to inspect the highest-risk finding.

Avoid:

- decorative hero sections;
- marketing copy;
- oversized page titles that crowd out evidence;
- unexplained scores;
- internal implementation labels.

## Visual design direction

Use a restrained, data-rich style with enough personality to be memorable.

Recommended direction:

- light neutral base with strong contrast;
- one assertive warning colour for risk;
- one stable success colour for normal/cheapest states;
- one cool accent for confidence/data provenance;
- compact panels with clear section titles;
- tabular price data where comparison precision matters;
- cards only for repeated findings or bounded tools;
- consistent 8px radius or less;
- icons for refresh, export, inspect, expand/collapse and warning states;
- responsive grid that keeps metrics stable and avoids layout shift.

Do not use a one-note beige, purple, blue-slate or espresso palette. Do not rely on decorative gradients or floating shapes.

## Component requirements

### Weekly verdict summary

Shows:

- verdict label;
- worst retailer;
- avoidable overspend;
- comparison basis;
- data freshness;
- confidence band;
- caveat if data is stale, incomplete or low confidence.

### Offender card

Shows:

- product group;
- retailer;
- direct recommendation;
- offender score;
- current premium versus cheapest comparable;
- movement versus competitor median;
- cheapest equivalent;
- confidence;
- "Why flagged" expansion.

### Product detail

Shows:

- retailer-by-retailer comparison table;
- unit price and shelf price;
- pack size and loyalty price distinctions;
- historical movement;
- equivalent group members;
- source freshness;
- recommendation and caveat.

### Basket comparison

Shows:

- retailer totals for tracked basket;
- missing product groups by retailer;
- avoidable overspend;
- cheapest equivalent route;
- caveat when a retailer lacks enough matches.

### Methodology

Shows:

- how BasketGuard compares products;
- what confidence means;
- how stale data is handled;
- what the app will not claim without review.

### Operator tools

Data gathering, source health, review queue and database views should use compact admin styling. They should not compete with the consumer report for attention.

## State requirements

Every user-facing report component must have designed states for:

- loading;
- empty data;
- no warning detected;
- stale data;
- missing retailer coverage;
- low confidence;
- parser/review required;
- API unavailable;
- partial failure.

The UI must not silently render blank panels or imply certainty when the data is incomplete.

## Data and API expectations

The professional UI should move away from fixture-only data once API endpoints are available. The implementation issue should define whether the slice remains static or calls the FastAPI report endpoints.

Minimum API-backed targets:

- report summary;
- offender list;
- retailer gap report;
- group comparison detail;
- price movement for selected group;
- review/source health summary when available.

Fixture fallback is acceptable for local demo mode only if it is clearly isolated in code and covered by tests.

## Accessibility and responsive requirements

Acceptance requires:

- keyboard-accessible navigation and controls;
- visible focus states;
- semantic headings;
- useful button labels and tooltips for icon-only actions;
- colour not used as the only signal;
- text that fits containers at mobile and desktop widths;
- no horizontal scrolling except inside comparison tables;
- readable table behaviour on mobile;
- stable dimensions for metrics, toolbar buttons and repeated cards.

## Verification requirements

The implementation issue must include:

1. updated unit or asset tests where static contracts change;
2. a local browser smoke test;
3. screenshots for desktop and mobile widths;
4. manual checks for empty, loading and stale-data states;
5. confirmation that claim wording still follows [Reporting and UX](08_REPORTING_AND_UX.md).

Default test command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m unittest discover -s tests -v
```

## Linear tasking

Linear tracking has been created in the BasketGuard MVP project. Linear is the
single source of truth for the current status, priority, ownership and sequence
of these issues:

- `BAS-80` - Professionalise MVP web UI
- `BAS-81` - UI: Build professional product shell and navigation
- `BAS-82` - UI: Redesign weekly verdict and offender cards
- `BAS-83` - UI: Add product detail and basket comparison polish
- `BAS-84` - UI: Design loading, empty, stale and error states
- `BAS-85` - UI: Responsive accessibility and screenshot verification pass

Keep this breakdown as one parent issue for the UI professionalisation slice and separate child issues for:

1. product shell and navigation;
2. weekly verdict and offender cards;
3. product detail and basket comparison;
4. loading, empty, stale and error states;
5. responsive/accessibility polish and screenshot verification.

Use `agent:codex` for implementation-ready UI work once this plan is accepted. Use `agent:chatgpt` only for documentation or product-control updates. Update this document through GitHub change control only when the durable UX guidance changes.
