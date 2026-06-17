# Postcode / Store-Level Price Collection Strategy

Status: design baseline for the BAS-29 live-collection epic (BAS-36). UK grocery
prices and availability vary by store / delivery postcode. The schema already
carries `postcode_context` on `raw_product_snapshots` and `price_observations`;
this defines how collection sets it and how reports must interpret it. The
helper `basketguard_shared.postcode` ships the implementable parts.

## MVP decision: a single fixed postcode

The MVP collects every retailer against **one fixed delivery postcode**, so that
"retailer X is more expensive than retailer Y" is a like-for-like claim. Mixing
postcodes silently would make comparisons apples-to-oranges. Multi-postcode /
regional collection is an explicit later expansion, not MVP scope.

* The chosen postcode is configured via `BASKETGUARD_COLLECTION_POSTCODE_CONTEXT`
  (`Settings.collection_postcode_context`). Until a real postcode is chosen, the
  default context label is `MVP default region`
  (`MVP_DEFAULT_POSTCODE_CONTEXT`).
* Every collected snapshot and observation records that context, so the basis of
  every price is auditable.

## Setting location during collection

Each retailer needs its delivery/store location set before prices are read
(usually a postcode entry or store selection that sets a cookie/session). That
per-retailer mechanism is collection-code work tracked under the headless
fetcher / anti-bot children; this issue fixes the **policy**:

1. one postcode for the whole MVP collection run;
2. the postcode context is stamped on every row from that run;
3. a run must not mix postcodes.

## How reports must interpret postcode context

* Comparison and gap reports compare observations **within one postcode
  context**. `assert_consistent_postcode` raises `PostcodeConsistencyError` if a
  comparison is handed observations from more than one known context, so a
  cross-postcode comparison fails loudly instead of producing a misleading
  number. `None` (unknown) contexts are ignored rather than blocking.
* `normalise_postcode_context` canonicalises values so the same location always
  compares equal (`ec1a1bb` and `EC1A 1BB` are one context); descriptive labels
  are trimmed but preserved.
* Report wording must state the postcode basis of any claim (covered by the
  report-UX / claim-safety work, BAS-50 / BAS-26).

## Deferred (post-MVP)

* Collecting multiple postcodes/regions and reporting regional differences.
* Store-level (click-and-collect) pricing distinct from delivery pricing.
* Reconciling retailers that do not vary price by location (national pricing)
  with those that do, so we do not over-state regional effects.
