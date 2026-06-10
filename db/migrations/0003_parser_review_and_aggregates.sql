-- BasketGuard review queue foundation.
-- Persists needs-review group match candidates so uncertain products stop
-- disappearing, as described in docs/backend/06_HUMAN_REVIEW_QUEUE.md.
-- Additive only; existing tables are not modified.

BEGIN;

CREATE TABLE review_queue_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  raw_snapshot_id UUID REFERENCES raw_product_snapshots(id),
  product_id UUID REFERENCES products(id),
  equivalence_group_id UUID NOT NULL REFERENCES equivalence_groups(id),
  match_confidence NUMERIC NOT NULL,
  match_reason TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  decision TEXT,
  reviewer_notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ,
  CONSTRAINT review_queue_items_match_confidence_range
    CHECK (match_confidence BETWEEN 0 AND 1),
  CONSTRAINT review_queue_items_status_known
    CHECK (status IN ('open', 'resolved')),
  CONSTRAINT review_queue_items_decision_known
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
    ),
  CONSTRAINT review_queue_items_resolution_consistent
    CHECK (
      (status = 'open' AND decision IS NULL AND resolved_at IS NULL)
      OR (status = 'resolved' AND decision IS NOT NULL AND resolved_at IS NOT NULL)
    ),
  CONSTRAINT review_queue_items_has_subject
    CHECK (raw_snapshot_id IS NOT NULL OR product_id IS NOT NULL)
);

CREATE INDEX idx_review_queue_items_open
ON review_queue_items(status, created_at)
WHERE status = 'open';

CREATE INDEX idx_review_queue_items_group
ON review_queue_items(equivalence_group_id, status);

CREATE INDEX idx_review_queue_items_product
ON review_queue_items(product_id);

COMMIT;
