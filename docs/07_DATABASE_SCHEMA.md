# Database Schema

## Purpose

Initial relational schema for BasketGuard.

PostgreSQL is recommended. TimescaleDB can be added later for high-volume time-series optimisation.

## retailers

Stores supermarket metadata.

```sql
CREATE TABLE retailers (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  website_url TEXT,
  supports_loyalty_price BOOLEAN DEFAULT false,
  supports_online_grocery BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## raw_product_snapshots

Stores raw collection evidence.

```sql
CREATE TABLE raw_product_snapshots (
  id UUID PRIMARY KEY,
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
  collected_at TIMESTAMPTZ NOT NULL
);
```

## products

Cleaned retailer-specific product catalogue.

```sql
CREATE TABLE products (
  id UUID PRIMARY KEY,
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
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(retailer_id, external_product_id)
);
```

## price_observations

Stores historical prices.

```sql
CREATE TABLE price_observations (
  id UUID PRIMARY KEY,
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
  collected_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_price_observations_product_time
ON price_observations(product_id, collected_at DESC);
```

## equivalence_groups

Comparable product groups.

```sql
CREATE TABLE equivalence_groups (
  id UUID PRIMARY KEY,
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
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## product_group_memberships

Maps products to equivalence groups.

```sql
CREATE TABLE product_group_memberships (
  id UUID PRIMARY KEY,
  product_id UUID NOT NULL REFERENCES products(id),
  equivalence_group_id UUID NOT NULL REFERENCES equivalence_groups(id),
  match_confidence NUMERIC NOT NULL,
  match_reason TEXT,
  is_primary_match BOOLEAN DEFAULT true,
  human_reviewed BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(product_id, equivalence_group_id)
);
```

## product_lineage

Tracks renamed, resized or replaced products.

```sql
CREATE TABLE product_lineage (
  id UUID PRIMARY KEY,
  previous_product_id UUID REFERENCES products(id),
  new_product_id UUID REFERENCES products(id),
  relationship_type TEXT NOT NULL,
  confidence_score NUMERIC,
  notes TEXT,
  detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  human_reviewed BOOLEAN DEFAULT false
);
```

## users

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email TEXT UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## user_watchlists

```sql
CREATE TABLE user_watchlists (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  equivalence_group_id UUID NOT NULL REFERENCES equivalence_groups(id),
  preferred_retailer_ids UUID[],
  alert_threshold NUMERIC DEFAULT 60,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(user_id, equivalence_group_id)
);
```

## analytics_findings

Stores generated warnings.

```sql
CREATE TABLE analytics_findings (
  id UUID PRIMARY KEY,
  equivalence_group_id UUID NOT NULL REFERENCES equivalence_groups(id),
  retailer_id UUID NOT NULL REFERENCES retailers(id),
  finding_type TEXT NOT NULL,
  offender_score NUMERIC,
  confidence_score NUMERIC,
  headline TEXT NOT NULL,
  explanation TEXT NOT NULL,
  recommendation TEXT,
  evidence JSONB,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## reports

```sql
CREATE TABLE reports (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  report_type TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT,
  report_payload JSONB NOT NULL,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## receipt_imports

Future receipt upload support.

```sql
CREATE TABLE receipt_imports (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  retailer_id UUID REFERENCES retailers(id),
  source_type TEXT NOT NULL,
  raw_file_location TEXT,
  parsed_status TEXT NOT NULL DEFAULT 'pending',
  purchased_at TIMESTAMPTZ,
  total_amount NUMERIC,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## receipt_items

```sql
CREATE TABLE receipt_items (
  id UUID PRIMARY KEY,
  receipt_import_id UUID NOT NULL REFERENCES receipt_imports(id),
  raw_item_name TEXT NOT NULL,
  quantity NUMERIC,
  line_price NUMERIC,
  matched_product_id UUID REFERENCES products(id),
  matched_equivalence_group_id UUID REFERENCES equivalence_groups(id),
  match_confidence NUMERIC,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```
