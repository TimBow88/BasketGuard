# BasketGuard Human Review Queue

## Purpose

The review queue prevents weak automated grouping from contaminating BasketGuard's price intelligence.

BasketGuard should not pretend all supermarket products are directly comparable. Many are not.

## Review principle

```text
When in doubt, do not group automatically.
```

A product in review is not a failure. It is a controlled quality gate.

## When review is required

Send a product to review when:

1. title is ambiguous;
2. category and title disagree;
3. pack size is outside expected range;
4. product has quality claims that may imply a different tier;
5. image suggests a different form than title;
6. product family varies materially by recipe or quality;
7. unit basis cannot be trusted;
8. brand owner is unclear;
9. product is in a medium/high-risk group;
10. parser confidence is below auto-match threshold.

## Review item fields

Each review item should show:

| Field | Purpose |
|---|---|
| Product title | Human-readable source title |
| Retailer | Retailer coverage check |
| Product URL | Open original page |
| Image URL | Verify form, coating, pack format |
| Category breadcrumb | Check retailer taxonomy |
| Price | Check current shelf price |
| Unit price | Check comparison basis |
| Pack size | Validate size range |
| Promotion text | Identify promo masking |
| Parsed attributes | Inspect extracted product type, tier, size and unit basis |
| Proposed group | Suggested equivalence group |
| Match score | Numeric confidence |
| Match reason | Positive signals |
| Exclusion flags | Negative signals |
| Raw snapshot ID | Audit evidence |

## Review decisions

Allowed decisions:

```text
approve_group_membership
reject_group_membership
new_group_needed
parser_bug
retailer_data_issue
insufficient_evidence
retire_source_product
```

Database mapping:

MVP review work is persisted in `review_queue_items`. Approval updates or creates the relevant `product_group_memberships` row with `human_reviewed=true`; rejection resolves the queue item and removes the proposed membership for that product/group pair. Migration `0004` adds richer queue state and `review_queue_events` for audit history.

## Decision effects

### approve_group_membership

1. Creates or updates `product_group_memberships` and marks the decision as human reviewed.
2. Allows future price observations to appear in group reports.
3. Creates a positive test fixture candidate.

### reject_group_membership

1. Blocks or marks the `product_group_memberships` candidate as rejected once an explicit membership status exists.
2. Blocks the same `products` row from the same `equivalence_groups` row unless the group version changes.
3. Creates a negative test fixture candidate.

### new_group_needed

Use when product is valid but belongs in a different equivalence group.

Example:

```text
A product proposed for standard cornflakes is actually honey nut cornflakes.
```

### parser_bug

Use when the parser extracted attributes incorrectly.

Example:

```text
Title says "jumbo oats" but parser returned product_type = porridge_oats_standard.
```

### retailer_data_issue

Use when source data is missing or contradictory.

Example:

```text
Retailer category says frozen fish but image/title are chicken nuggets.
```

## Review UI layout

Recommended admin layout:

```text
Left panel:
  Product image
  Product title
  Retailer
  Product link
  Category breadcrumb
  Price/unit price/pack size

Middle panel:
  Parsed attributes
  Proposed group
  Match score
  Match reason
  Exclusion flags

Right panel:
  Approve
  Reject
  New group needed
  Parser bug
  Retailer data issue
  Reviewer notes
```

## Review priority

Prioritise review items by business value and risk.

Highest priority:

1. products in high-traffic MVP groups;
2. products blocking retailer coverage;
3. products with large price movement;
4. products proposed for public reports;
5. products in medium/high-risk categories.

Lower priority:

1. rare products;
2. unavailable products;
3. products outside MVP categories;
4. seasonal products;
5. premium or specialist products.

## Review queue states

```text
open
in_review
approved
rejected
closed
needs_parser_fix
needs_new_group
```

## Review audit trail

Every review action must store:

```text
reviewer
reviewed_at
decision
notes
previous_status
new_status
snapshot_id
proposed_group_id
parser_version
group_definition_version
```

In the current schema, persist queue state on `review_queue_items`, approved report eligibility on `product_group_memberships`, and audit history in `review_queue_events`.

## Creating test fixtures from review

Approved and rejected review decisions should become fixtures.

Fixture generation should capture:

1. source title;
2. retailer;
3. category breadcrumb;
4. image URL if useful;
5. parsed attributes;
6. expected group decision;
7. reason.

Example fixture:

```yaml
case_id: cornflakes_tesco_standard_positive_001
title: Tesco Corn Flakes 500g
retailer: tesco
category_breadcrumb: Food Cupboard > Cereals > Cornflakes
expected:
  group: own_brand_cornflakes_standard
  decision: auto_match
```

## Review queue MVP

MVP review queue can be simple.

Required:

1. list open review items;
2. show product evidence;
3. approve/reject proposed group;
4. add reviewer notes;
5. update `product_group_memberships`;
6. create audit row.

Not required for MVP:

1. multiple reviewer roles;
2. complex workflow assignment;
3. ML training loop;
4. bulk decisions;
5. reviewer performance analytics.
