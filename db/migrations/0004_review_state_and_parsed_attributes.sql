-- BasketGuard richer review-queue state and versioned parsed attributes.
-- Covers deferred items 1-2 in docs/11_CODEX_WORKPLAN.md:
--   1. richer review-queue state beyond the 0003 foundation;
--   2. parsed_product_attributes for versioned snapshot parser outputs.
-- Adds the reviewer/workflow/audit surface described in
-- docs/backend/06_HUMAN_REVIEW_QUEUE.md.
-- Additive and backward compatible: existing 'open'/'resolved' review rows and
-- the review_decisions code path keep working unchanged.

BEGIN;

-- 1. Richer review-queue item state ------------------------------------------

-- Reviewer attribution plus the parser/group definition versions in force when
-- an item was raised, per the review audit-trail spec. All nullable so existing
-- rows and the current approve/reject path remain valid without backfill.
ALTER TABLE review_queue_items
  ADD COLUMN reviewer TEXT,
  ADD COLUMN reviewed_at TIMESTAMPTZ,
  ADD COLUMN parser_version TEXT,
  ADD COLUMN group_definition_version TEXT;

-- Allow an item to be claimed ('in_review') between 'open' and 'resolved'.
-- 'in_review' is an unresolved state, so like 'open' it carries no decision or
-- resolved_at. Existing 'open'/'resolved' rows stay valid.
ALTER TABLE review_queue_items
  DROP CONSTRAINT review_queue_items_status_known;
ALTER TABLE review_queue_items
  ADD CONSTRAINT review_queue_items_status_known
    CHECK (status IN ('open', 'in_review', 'resolved'));

ALTER TABLE review_queue_items
  DROP CONSTRAINT review_queue_items_resolution_consistent;
ALTER TABLE review_queue_items
  ADD CONSTRAINT review_queue_items_resolution_consistent
    CHECK (
      (status IN ('open', 'in_review') AND decision IS NULL AND resolved_at IS NULL)
      OR (status = 'resolved' AND decision IS NOT NULL AND resolved_at IS NOT NULL)
    );

-- 2. Review-queue audit trail ------------------------------------------------

-- One row per review-queue state transition / decision, capturing the full
-- audit trail from docs/backend/06_HUMAN_REVIEW_QUEUE.md so queue history,
-- parser-bug flags and reviewer attribution survive beyond the latest state
-- stored on review_queue_items. new_status carries the richer review-state
-- vocabulary (open, in_review, resolved, approved, rejected, closed,
-- needs_parser_fix, needs_new_group).
CREATE TABLE review_queue_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  review_queue_item_id UUID NOT NULL REFERENCES review_queue_items(id),
  previous_status TEXT,
  new_status TEXT NOT NULL,
  decision TEXT,
  reviewer TEXT,
  reviewer_notes TEXT,
  parser_version TEXT,
  group_definition_version TEXT,
  raw_snapshot_id UUID REFERENCES raw_product_snapshots(id),
  proposed_group_id UUID REFERENCES equivalence_groups(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT review_queue_events_new_status_known
    CHECK (new_status IN (
      'open', 'in_review', 'resolved',
      'approved', 'rejected', 'closed',
      'needs_parser_fix', 'needs_new_group'
    )),
  CONSTRAINT review_queue_events_previous_status_known
    CHECK (
      previous_status IS NULL
      OR previous_status IN (
        'open', 'in_review', 'resolved',
        'approved', 'rejected', 'closed',
        'needs_parser_fix', 'needs_new_group'
      )
    ),
  CONSTRAINT review_queue_events_decision_known
    CHECK (
      decision IS NULL
      OR decision IN (
        'approve_group_membership',
        'reject_group_membership',
        'new_group_needed',
        'parser_bug',
        'retailer_data_issue',
        'insufficient_evidence',
        'retire_source_product'
      )
    )
);

CREATE INDEX idx_review_queue_events_item
ON review_queue_events(review_queue_item_id, created_at);

CREATE INDEX idx_review_queue_events_decision
ON review_queue_events(decision)
WHERE decision IS NOT NULL;

-- 3. Versioned parsed product attributes -------------------------------------

-- Versioned parser outputs for a raw snapshot: normalisation (size / unit /
-- unit price) and classification (brand owner, tier, product type, exclusion
-- flags) that feed the equivalence matcher. Raw text stays on
-- raw_product_snapshots; normalised values are stored here separately. Keyed by
-- parser_version so a reparse adds a new row rather than overwriting prior
-- output, preserving attribute history.
CREATE TABLE parsed_product_attributes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  raw_snapshot_id UUID NOT NULL REFERENCES raw_product_snapshots(id),
  product_id UUID REFERENCES products(id),
  parser_version TEXT NOT NULL,
  -- classification
  brand TEXT,
  brand_owner TEXT,
  product_type TEXT,
  product_form TEXT,
  flavour_variant TEXT,
  tier TEXT,
  -- normalisation (raw text preserved on raw_product_snapshots)
  pack_size_value NUMERIC,
  pack_size_unit TEXT,
  normalised_size_value NUMERIC,
  normalised_size_unit TEXT,
  unit_basis TEXT,
  unit_price NUMERIC,
  unit_price_basis TEXT,
  multipack_count INTEGER,
  item_count INTEGER,
  -- boolean classification flags
  is_own_brand BOOLEAN,
  is_premium BOOLEAN,
  is_value_range BOOLEAN,
  is_organic BOOLEAN,
  is_multipack BOOLEAN,
  -- negative signals and any additional parsed signals
  exclusion_flags JSONB,
  parsed_attributes JSONB,
  parse_confidence NUMERIC,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT parsed_product_attributes_parser_version_not_blank
    CHECK (btrim(parser_version) <> ''),
  CONSTRAINT parsed_product_attributes_pack_size_non_negative
    CHECK (pack_size_value IS NULL OR pack_size_value >= 0),
  CONSTRAINT parsed_product_attributes_normalised_size_non_negative
    CHECK (normalised_size_value IS NULL OR normalised_size_value >= 0),
  CONSTRAINT parsed_product_attributes_unit_price_non_negative
    CHECK (unit_price IS NULL OR unit_price >= 0),
  CONSTRAINT parsed_product_attributes_multipack_count_non_negative
    CHECK (multipack_count IS NULL OR multipack_count >= 0),
  CONSTRAINT parsed_product_attributes_item_count_non_negative
    CHECK (item_count IS NULL OR item_count >= 0),
  CONSTRAINT parsed_product_attributes_parse_confidence_range
    CHECK (parse_confidence IS NULL OR parse_confidence BETWEEN 0 AND 1),
  UNIQUE (raw_snapshot_id, parser_version)
);

CREATE INDEX idx_parsed_product_attributes_snapshot
ON parsed_product_attributes(raw_snapshot_id);

CREATE INDEX idx_parsed_product_attributes_product
ON parsed_product_attributes(product_id)
WHERE product_id IS NOT NULL;

CREATE INDEX idx_parsed_product_attributes_parser_version
ON parsed_product_attributes(parser_version);

COMMIT;
