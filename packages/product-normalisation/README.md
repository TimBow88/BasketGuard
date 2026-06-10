# BasketGuard Product Normalisation

Utilities for turning messy supermarket product titles into structured, comparable attributes.

Current scope:

- parse common grocery pack sizes;
- convert grams, kilograms, millilitres, litres, and UK pints;
- normalise product sizes to comparison bases such as `kg`, `litre`, `wash`, `tablet`, `roll`, and `sheet`;
- classify obvious own-brand, value, premium, organic, and multipack signals from product names;
- load validated equivalence group definitions from JSON fixtures;
- deterministically match product candidates to groups with `auto_match`, `needs_review`, or `no_match` outcomes.

This package is intentionally dependency-free at this stage.

## Equivalence Groups

Group definitions live in `fixtures/equivalence_group_definitions.json` and follow the schema in
[docs/backend/05_NORMALISATION_GROUPING_AND_MATCHING.md](../../docs/backend/05_NORMALISATION_GROUPING_AND_MATCHING.md):
slug, name, status, risk level, unit basis, brand owner, tier, required title/category terms,
size range, exclude terms, review triggers, and match thresholds.

`load_equivalence_group_definitions` validates the file and raises
`EquivalenceGroupDefinitionError` with a specific message on any schema violation.

`match_equivalence_group(candidate, definition)` scores a `GroupMatchCandidate` using the
deterministic weight model from the grouping doc. Hard exclusions (exclude terms, product type,
brand owner, tier or unit basis conflicts) return `no_match` regardless of score; review
triggers such as a missing category or out-of-range size cap the outcome at `needs_review`.
