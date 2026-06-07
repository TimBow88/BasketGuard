-- BasketGuard data-gathering workflow tables.
-- Supports allowlisted collection targets, scrape/manual collection jobs,
-- and job-level health signals described in docs/03_DATA_INGESTION.md.

BEGIN;

CREATE TABLE collection_targets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  retailer_id UUID NOT NULL REFERENCES retailers(id),
  equivalence_group_id UUID REFERENCES equivalence_groups(id),
  external_product_id TEXT,
  target_name TEXT NOT NULL,
  target_url TEXT,
  postcode_context TEXT,
  collection_frequency TEXT NOT NULL DEFAULT 'daily',
  priority INTEGER NOT NULL DEFAULT 50,
  is_active BOOLEAN NOT NULL DEFAULT true,
  notes TEXT,
  last_collected_at TIMESTAMPTZ,
  next_collect_after TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT collection_targets_name_not_blank CHECK (btrim(target_name) <> ''),
  CONSTRAINT collection_targets_frequency_known
    CHECK (collection_frequency IN ('daily', 'twice_weekly', 'weekly', 'monthly', 'manual')),
  CONSTRAINT collection_targets_priority_range CHECK (priority BETWEEN 0 AND 100),
  CONSTRAINT collection_targets_has_locator
    CHECK (
      external_product_id IS NOT NULL
      OR target_url IS NOT NULL
      OR equivalence_group_id IS NOT NULL
    )
);

CREATE INDEX idx_collection_targets_due
ON collection_targets(is_active, next_collect_after, priority DESC);

CREATE INDEX idx_collection_targets_retailer
ON collection_targets(retailer_id, is_active);

CREATE INDEX idx_collection_targets_group
ON collection_targets(equivalence_group_id)
WHERE equivalence_group_id IS NOT NULL;

CREATE TRIGGER trg_collection_targets_set_updated_at
BEFORE UPDATE ON collection_targets
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE ingestion_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  retailer_id UUID REFERENCES retailers(id),
  job_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  postcode_context TEXT,
  scheduled_for TIMESTAMPTZ,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  target_count INTEGER NOT NULL DEFAULT 0,
  collected_count INTEGER NOT NULL DEFAULT 0,
  parser_error_count INTEGER NOT NULL DEFAULT 0,
  missing_price_count INTEGER NOT NULL DEFAULT 0,
  blocked_indicator BOOLEAN NOT NULL DEFAULT false,
  changed_selector_warning BOOLEAN NOT NULL DEFAULT false,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ingestion_jobs_job_type_not_blank CHECK (btrim(job_type) <> ''),
  CONSTRAINT ingestion_jobs_status_known
    CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'partial', 'cancelled')),
  CONSTRAINT ingestion_jobs_counts_non_negative
    CHECK (
      target_count >= 0
      AND collected_count >= 0
      AND parser_error_count >= 0
      AND missing_price_count >= 0
    )
);

CREATE INDEX idx_ingestion_jobs_status_created
ON ingestion_jobs(status, created_at DESC);

CREATE INDEX idx_ingestion_jobs_retailer_created
ON ingestion_jobs(retailer_id, created_at DESC)
WHERE retailer_id IS NOT NULL;

CREATE TABLE ingestion_job_targets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ingestion_job_id UUID NOT NULL REFERENCES ingestion_jobs(id),
  collection_target_id UUID REFERENCES collection_targets(id),
  raw_snapshot_id UUID REFERENCES raw_product_snapshots(id),
  status TEXT NOT NULL DEFAULT 'pending',
  error_code TEXT,
  error_message TEXT,
  attempted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ingestion_job_targets_status_known
    CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'skipped')),
  CONSTRAINT ingestion_job_targets_has_target_or_snapshot
    CHECK (collection_target_id IS NOT NULL OR raw_snapshot_id IS NOT NULL)
);

CREATE INDEX idx_ingestion_job_targets_job
ON ingestion_job_targets(ingestion_job_id);

CREATE INDEX idx_ingestion_job_targets_target
ON ingestion_job_targets(collection_target_id)
WHERE collection_target_id IS NOT NULL;

COMMIT;
