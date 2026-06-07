-- BasketGuard initial PostgreSQL schema.
-- Source of truth: docs/07_DATABASE_SCHEMA.md

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE retailers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  website_url TEXT,
  supports_loyalty_price BOOLEAN NOT NULL DEFAULT false,
  supports_online_grocery BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT retailers_name_not_blank CHECK (btrim(name) <> ''),
  CONSTRAINT retailers_slug_not_blank CHECK (btrim(slug) <> '')
);

CREATE TABLE raw_product_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  retailer_id UUID NOT NULL REFERENCES retailers(id),
  external_product_id TEXT,
  url TEXT,
  raw_title TEXT,
  raw_price_text TEXT,
  raw_unit_price_text TEXT,
  raw_promo_text TEXT,
  raw_pack_size_text TEXT,
  raw_payload_location TEXT,
  postcode_context TEXT,
  collection_status TEXT NOT NULL,
  parser_version TEXT,
  collected_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT raw_product_snapshots_collection_status_not_blank
    CHECK (btrim(collection_status) <> '')
);

CREATE INDEX idx_raw_product_snapshots_retailer_collected_at
ON raw_product_snapshots(retailer_id, collected_at DESC);

CREATE INDEX idx_raw_product_snapshots_external_product
ON raw_product_snapshots(retailer_id, external_product_id)
WHERE external_product_id IS NOT NULL;

CREATE TRIGGER trg_retailers_set_updated_at
BEFORE UPDATE ON retailers
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  retailer_id UUID NOT NULL REFERENCES retailers(id),
  external_product_id TEXT,
  url TEXT,
  canonical_name TEXT NOT NULL,
  brand TEXT,
  brand_owner TEXT,
  category TEXT,
  subcategory TEXT,
  product_type TEXT,
  product_form TEXT,
  flavour_variant TEXT,
  pack_size_value NUMERIC,
  pack_size_unit TEXT,
  normalised_size_value NUMERIC,
  normalised_size_unit TEXT,
  unit_basis TEXT,
  tier TEXT,
  is_own_brand BOOLEAN,
  is_premium BOOLEAN,
  is_value_range BOOLEAN,
  is_organic BOOLEAN,
  is_multipack BOOLEAN,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT products_canonical_name_not_blank CHECK (btrim(canonical_name) <> ''),
  CONSTRAINT products_pack_size_non_negative
    CHECK (pack_size_value IS NULL OR pack_size_value >= 0),
  CONSTRAINT products_normalised_size_non_negative
    CHECK (normalised_size_value IS NULL OR normalised_size_value >= 0),
  UNIQUE(retailer_id, external_product_id)
);

CREATE INDEX idx_products_retailer_active
ON products(retailer_id, is_active);

CREATE INDEX idx_products_category_type
ON products(category, subcategory, product_type);

CREATE INDEX idx_products_external_product
ON products(external_product_id)
WHERE external_product_id IS NOT NULL;

CREATE TRIGGER trg_products_set_updated_at
BEFORE UPDATE ON products
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE price_observations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES products(id),
  raw_snapshot_id UUID REFERENCES raw_product_snapshots(id),
  shelf_price NUMERIC,
  loyalty_price NUMERIC,
  was_price NUMERIC,
  effective_price NUMERIC,
  unit_price NUMERIC,
  unit_price_basis TEXT,
  promo_type TEXT,
  promo_description TEXT,
  availability TEXT,
  postcode_context TEXT,
  collected_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT price_observations_shelf_price_non_negative
    CHECK (shelf_price IS NULL OR shelf_price >= 0),
  CONSTRAINT price_observations_loyalty_price_non_negative
    CHECK (loyalty_price IS NULL OR loyalty_price >= 0),
  CONSTRAINT price_observations_was_price_non_negative
    CHECK (was_price IS NULL OR was_price >= 0),
  CONSTRAINT price_observations_effective_price_non_negative
    CHECK (effective_price IS NULL OR effective_price >= 0),
  CONSTRAINT price_observations_unit_price_non_negative
    CHECK (unit_price IS NULL OR unit_price >= 0)
);

CREATE INDEX idx_price_observations_product_time
ON price_observations(product_id, collected_at DESC);

CREATE INDEX idx_price_observations_collected_at
ON price_observations(collected_at DESC);

CREATE INDEX idx_price_observations_availability
ON price_observations(availability)
WHERE availability IS NOT NULL;

CREATE TABLE equivalence_groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_group_name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  category TEXT,
  subcategory TEXT,
  product_type TEXT,
  comparison_level TEXT,
  unit_basis TEXT,
  tier TEXT,
  confidence_score NUMERIC,
  review_status TEXT NOT NULL DEFAULT 'pending',
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT equivalence_groups_name_not_blank
    CHECK (btrim(canonical_group_name) <> ''),
  CONSTRAINT equivalence_groups_slug_not_blank CHECK (btrim(slug) <> ''),
  CONSTRAINT equivalence_groups_confidence_score_range
    CHECK (confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1),
  CONSTRAINT equivalence_groups_review_status_known
    CHECK (review_status IN ('pending', 'human_reviewed', 'approved', 'rejected', 'needs_review'))
);

CREATE INDEX idx_equivalence_groups_review_status
ON equivalence_groups(review_status);

CREATE INDEX idx_equivalence_groups_category_type
ON equivalence_groups(category, subcategory, product_type);

CREATE TRIGGER trg_equivalence_groups_set_updated_at
BEFORE UPDATE ON equivalence_groups
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE product_group_memberships (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES products(id),
  equivalence_group_id UUID NOT NULL REFERENCES equivalence_groups(id),
  match_confidence NUMERIC NOT NULL,
  match_reason TEXT,
  is_primary_match BOOLEAN NOT NULL DEFAULT true,
  human_reviewed BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT product_group_memberships_match_confidence_range
    CHECK (match_confidence BETWEEN 0 AND 1),
  UNIQUE(product_id, equivalence_group_id)
);

CREATE INDEX idx_product_group_memberships_group
ON product_group_memberships(equivalence_group_id);

CREATE INDEX idx_product_group_memberships_review
ON product_group_memberships(human_reviewed, match_confidence);

CREATE TABLE product_lineage (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  previous_product_id UUID REFERENCES products(id),
  new_product_id UUID REFERENCES products(id),
  relationship_type TEXT NOT NULL,
  confidence_score NUMERIC,
  notes TEXT,
  detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  human_reviewed BOOLEAN NOT NULL DEFAULT false,
  CONSTRAINT product_lineage_relationship_type_not_blank
    CHECK (btrim(relationship_type) <> ''),
  CONSTRAINT product_lineage_confidence_score_range
    CHECK (confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1),
  CONSTRAINT product_lineage_has_product_reference
    CHECK (previous_product_id IS NOT NULL OR new_product_id IS NOT NULL),
  CONSTRAINT product_lineage_not_self_reference
    CHECK (
      previous_product_id IS NULL
      OR new_product_id IS NULL
      OR previous_product_id <> new_product_id
    )
);

CREATE INDEX idx_product_lineage_previous_product
ON product_lineage(previous_product_id)
WHERE previous_product_id IS NOT NULL;

CREATE INDEX idx_product_lineage_new_product
ON product_lineage(new_product_id)
WHERE new_product_id IS NOT NULL;

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT users_email_not_blank CHECK (email IS NULL OR btrim(email) <> '')
);

CREATE TRIGGER trg_users_set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE user_watchlists (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  equivalence_group_id UUID NOT NULL REFERENCES equivalence_groups(id),
  preferred_retailer_ids UUID[],
  alert_threshold NUMERIC NOT NULL DEFAULT 60,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT user_watchlists_alert_threshold_range
    CHECK (alert_threshold BETWEEN 0 AND 100),
  UNIQUE(user_id, equivalence_group_id)
);

CREATE INDEX idx_user_watchlists_user
ON user_watchlists(user_id);

CREATE INDEX idx_user_watchlists_group
ON user_watchlists(equivalence_group_id);

CREATE TABLE analytics_findings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  equivalence_group_id UUID NOT NULL REFERENCES equivalence_groups(id),
  retailer_id UUID NOT NULL REFERENCES retailers(id),
  finding_type TEXT NOT NULL,
  offender_score NUMERIC,
  confidence_score NUMERIC,
  headline TEXT NOT NULL,
  explanation TEXT NOT NULL,
  recommendation TEXT,
  evidence JSONB,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT analytics_findings_finding_type_not_blank
    CHECK (btrim(finding_type) <> ''),
  CONSTRAINT analytics_findings_headline_not_blank
    CHECK (btrim(headline) <> ''),
  CONSTRAINT analytics_findings_explanation_not_blank
    CHECK (btrim(explanation) <> ''),
  CONSTRAINT analytics_findings_offender_score_range
    CHECK (offender_score IS NULL OR offender_score BETWEEN 0 AND 100),
  CONSTRAINT analytics_findings_confidence_score_range
    CHECK (confidence_score IS NULL OR confidence_score BETWEEN 0 AND 100)
);

CREATE INDEX idx_analytics_findings_group_generated
ON analytics_findings(equivalence_group_id, generated_at DESC);

CREATE INDEX idx_analytics_findings_retailer_generated
ON analytics_findings(retailer_id, generated_at DESC);

CREATE INDEX idx_analytics_findings_offender_score
ON analytics_findings(offender_score DESC)
WHERE offender_score IS NOT NULL;

CREATE TABLE reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  report_type TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT,
  report_payload JSONB NOT NULL,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT reports_report_type_not_blank CHECK (btrim(report_type) <> ''),
  CONSTRAINT reports_title_not_blank CHECK (btrim(title) <> '')
);

CREATE INDEX idx_reports_user_generated
ON reports(user_id, generated_at DESC)
WHERE user_id IS NOT NULL;

CREATE INDEX idx_reports_type_generated
ON reports(report_type, generated_at DESC);

CREATE TABLE receipt_imports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  retailer_id UUID REFERENCES retailers(id),
  source_type TEXT NOT NULL,
  raw_file_location TEXT,
  parsed_status TEXT NOT NULL DEFAULT 'pending',
  purchased_at TIMESTAMPTZ,
  total_amount NUMERIC,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT receipt_imports_source_type_not_blank
    CHECK (btrim(source_type) <> ''),
  CONSTRAINT receipt_imports_parsed_status_not_blank
    CHECK (btrim(parsed_status) <> ''),
  CONSTRAINT receipt_imports_total_amount_non_negative
    CHECK (total_amount IS NULL OR total_amount >= 0)
);

CREATE INDEX idx_receipt_imports_user_created
ON receipt_imports(user_id, created_at DESC);

CREATE INDEX idx_receipt_imports_status
ON receipt_imports(parsed_status);

CREATE TABLE receipt_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  receipt_import_id UUID NOT NULL REFERENCES receipt_imports(id),
  raw_item_name TEXT NOT NULL,
  quantity NUMERIC,
  line_price NUMERIC,
  matched_product_id UUID REFERENCES products(id),
  matched_equivalence_group_id UUID REFERENCES equivalence_groups(id),
  match_confidence NUMERIC,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT receipt_items_raw_item_name_not_blank
    CHECK (btrim(raw_item_name) <> ''),
  CONSTRAINT receipt_items_quantity_non_negative
    CHECK (quantity IS NULL OR quantity >= 0),
  CONSTRAINT receipt_items_line_price_non_negative
    CHECK (line_price IS NULL OR line_price >= 0),
  CONSTRAINT receipt_items_match_confidence_range
    CHECK (match_confidence IS NULL OR match_confidence BETWEEN 0 AND 1)
);

CREATE INDEX idx_receipt_items_import
ON receipt_items(receipt_import_id);

CREATE INDEX idx_receipt_items_matched_product
ON receipt_items(matched_product_id)
WHERE matched_product_id IS NOT NULL;

CREATE INDEX idx_receipt_items_matched_group
ON receipt_items(matched_equivalence_group_id)
WHERE matched_equivalence_group_id IS NOT NULL;

COMMIT;
