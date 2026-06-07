# Grouping Catalogue Draft

## 1. Purpose

This document defines how BasketGuard should create and review product equivalence groups.

The immediate goal is to turn broad product ideas such as "own-brand frozen cod" or "own-brand breakfast cereals" into concrete, testable grouping rules.

This document should support targeted future work:

1. add seed group definitions;
2. add parser attributes;
3. add matching rules;
4. add human-review tasks;
5. add scraper metadata requirements;
6. add tests for each product family.

## 2. Scope

Current draft scope:

1. own-brand frozen cod;
2. own-brand breakfast cereal subgroups.

Out of scope for this document:

1. live scraping implementation;
2. retailer-specific selector details;
3. legal review;
4. user-facing copy beyond group names;
5. full production taxonomy.

## 3. Core Grouping Principle

BasketGuard should compare products only when a user would reasonably treat them as substitutes.

The product should prefer fewer high-confidence groups over broad weak groups.

Bad grouping:

```text
own_brand_breakfast_cereals
```

Reason:

Cornflakes, wheat biscuits, granola, porridge oats and chocolate hoops are not equivalent substitutes.

Better grouping:

```text
own_brand_cornflakes_standard
own_brand_wheat_biscuits_standard
own_brand_porridge_oats_standard
own_brand_granola_standard
```

## 4. Grouping Dimensions

Every equivalence group should be defined using explicit dimensions.

| Dimension | Purpose |
|---|---|
| Category | Prevent cross-category matches. |
| Product type | Identify the actual comparable item. |
| Form | Distinguish fillets, loins, flakes, biscuits, sachets and other formats. |
| Brand owner | Separate retailer own-label from branded products. |
| Tier | Separate value, standard, premium, organic and specialist products. |
| Flavour or coating | Prevent plain products being compared with flavoured or coated products. |
| Pack size | Control comparison spread and identify unusual formats. |
| Unit basis | Ensure price comparison is mathematically valid. |
| Availability | Lower confidence when products are repeatedly unavailable. |
| Metadata confidence | Track whether title, category, image and unit price agree. |

## 5. Standard Attribute Model

Each candidate product should be parsed into the following attributes before matching.

| Attribute | Example |
|---|---|
| retailer | Tesco |
| product_name | Tesco Frozen Cod Fillets 500g |
| brand | Tesco |
| brand_owner | retailer_own_label |
| category | Frozen food |
| subcategory | Frozen fish |
| product_type | Cod |
| form | Fillet |
| state | Frozen |
| tier | retailer_standard |
| flavour | Plain |
| coating | None |
| species | Cod |
| pack_size_value | 500 |
| pack_size_unit | g |
| normalised_size_value | 0.5 |
| normalised_size_unit | kg |
| unit_basis | kg |
| organic | false |
| premium | false |
| value_range | false |
| multipack | false |

Not every product family needs every attribute, but missing critical attributes should reduce confidence or force human review.

## 6. Group Definition Template

Each grouping rule should follow this structure:

```text
Canonical slug
User-facing name
Comparison intent
Include rules
Exclude rules
Pack-size rule
Unit basis
Required parsed attributes
Matching rule
Human-review triggers
Scraping metadata requirements
Confidence policy
Test fixtures required
```

This format is intentionally repetitive. It makes each group easier to implement, test and review independently.

## 7. Confidence Policy

### Auto-Match

Use auto-match only when all are true:

1. product type is explicit;
2. tier is clear;
3. brand owner is clear;
4. form is clear;
5. exclusion terms are absent;
6. unit basis is available;
7. pack size is inside the group rule;
8. category breadcrumb supports the match.

Suggested threshold:

```text
match_score >= 0.92
```

### Human Review

Send to human review when:

1. title is ambiguous;
2. category and title disagree;
3. pack size is outside expected range;
4. product has quality claims that may imply a different tier;
5. image suggests a different form than the title;
6. product family is known to vary materially by recipe or quality.

Suggested threshold:

```text
0.75 <= match_score < 0.92
```

### No Match

Do not match when:

1. product type differs;
2. tier differs;
3. brand owner differs;
4. form differs materially;
5. flavour, coating or ingredients change the comparable use case;
6. unit basis cannot be trusted.

Suggested threshold:

```text
match_score < 0.75
```

## 8. Review Queue Fields

Each proposed group membership should expose these fields to reviewers.

| Field | Purpose |
|---|---|
| product_name | Human-readable source title. |
| retailer | Check retailer coverage. |
| product_url | Open source product page. |
| image_url | Verify coating, form and pack format. |
| category_breadcrumb | Check retailer taxonomy. |
| parsed_attributes | Inspect extracted product type, tier, size and unit basis. |
| proposed_group | Suggested equivalence group. |
| match_score | Numeric confidence. |
| match_reason | Explanation of positive signals. |
| exclusion_flags | Branded, premium, organic, flavoured, coated and other negative signals. |
| raw_snapshot_id | Link back to audit evidence. |

## 9. Scraping Metadata Needed for Grouping

Grouping quality depends on richer metadata than price alone.

Minimum metadata for all grouping:

1. product title;
2. retailer;
3. product URL;
4. external product ID;
5. category breadcrumb;
6. pack size;
7. unit price;
8. image URL;
9. availability;
10. promotion text;
11. raw snapshot ID.

Additional metadata for higher-risk categories:

| Category | Extra fields |
|---|---|
| Frozen fish | species, coating, form, sourcing claims, image URL. |
| Cereal | flavour, format, count, weight, specialist dietary claims. |
| Toilet roll | rolls, sheets per roll, ply where available. |
| Washing products | wash count, capsule/tablet/liquid format, bio/non-bio. |

## 10. Product Family: Own-Brand Frozen Cod

### 10.1 Status

```text
Draft: high value, medium/high grouping risk
```

Frozen cod is useful for BasketGuard but should not be implemented as a title-only matcher.

Reason:

Fish products vary by species, cut, coating, skin status, sourcing claim, pack format and tier.

### 10.2 Canonical Group

```text
own_brand_frozen_cod_fillets_standard
```

### 10.3 User-Facing Name

```text
Own-brand frozen cod fillets
```

### 10.4 Comparison Intent

Compare standard own-brand frozen cod fillets across retailers using price per kg.

### 10.5 Include Rules

Products should be included only when all conditions are true.

| Attribute | Required value |
|---|---|
| Category | Frozen food |
| Subcategory | Frozen fish |
| Species | Cod |
| Form | Fillet or fillets |
| State | Frozen |
| Brand owner | Retailer own-label |
| Tier | Retailer standard |
| Coating | None |
| Flavour | Plain |
| Unit basis | kg |
| Pack format | Bag or box of fillets |

Example included products:

```text
Tesco Frozen Cod Fillets 500g
Asda Frozen Cod Fillets 500g
Sainsbury's Frozen Cod Fillets 520g
Morrisons Cod Fillets 500g
```

### 10.6 Exclude Rules

Exclude:

1. battered cod;
2. breaded cod;
3. fish fingers;
4. cod loins;
5. cod portions when clearly not fillets;
6. smoked cod;
7. flavoured cod;
8. marinated cod;
9. skin-on variants if most group members are skinless;
10. premium range cod;
11. value range cod;
12. branded cod;
13. organic or specialist sourcing ranges if positioned as separate tiers;
14. haddock, pollock, basa, hake or mixed white fish.

Example excluded products:

```text
Tesco 4 Battered Cod Fillets
Asda Breaded Cod Fillets
Sainsbury's Taste the Difference Cod Loin Fillets
Young's Cod Fillets
Morrisons White Fish Fillets
```

### 10.7 Pack-Size Rule

Initial rule:

```text
400g to 650g allowed if unit price is present
```

Preferred MVP rule:

```text
450g to 550g
```

Use the narrower rule first unless retailer coverage is too weak.

### 10.8 Unit Basis

```text
kg
```

### 10.9 Required Parsed Attributes

| Attribute | Required |
|---|---|
| species | yes |
| state | yes |
| form | yes |
| coating | yes |
| tier | yes |
| brand_owner | yes |
| normalised_size_value | yes |
| normalised_size_unit | yes |
| unit_basis | yes |

### 10.10 Matching Rule

```text
IF category contains frozen
AND subcategory contains fish
AND species = cod
AND form = fillet
AND state = frozen
AND coating = none
AND tier = retailer_standard
AND brand_owner = retailer_own_label
AND normalised_size_unit = kg
AND normalised_size_value BETWEEN 0.4 AND 0.65
THEN group = own_brand_frozen_cod_fillets_standard
```

### 10.11 Human-Review Triggers

Send to review when:

1. title says "cod portions";
2. title says "white fish";
3. title says "responsibly sourced" and tier is unclear;
4. product image suggests coating;
5. category breadcrumb is missing;
6. pack size is outside 400g to 650g;
7. retailer title does not clearly say frozen.

### 10.12 Test Fixtures Required

Positive fixtures:

1. Tesco standard frozen cod fillets;
2. Asda standard frozen cod fillets;
3. Sainsbury's standard frozen cod fillets;
4. Morrisons standard frozen cod fillets.

Negative fixtures:

1. battered cod;
2. breaded cod;
3. cod loins;
4. branded cod;
5. premium cod;
6. white fish fillets;
7. haddock fillets.

## 11. Product Family: Own-Brand Breakfast Cereals

### 11.1 Status

```text
Draft: high value, mixed grouping risk
```

Breakfast cereal must be split into subgroups. A broad own-brand cereal group is not acceptable.

### 11.2 Recommended Subgroups

| Slug | User-facing name | Unit basis | Risk |
|---|---|---|---|
| own_brand_cornflakes_standard | Own-brand cornflakes | kg | Low |
| own_brand_wheat_biscuits_standard | Own-brand wheat biscuits | biscuit preferred, kg fallback | Medium |
| own_brand_porridge_oats_standard | Own-brand porridge oats | kg | Low |
| own_brand_granola_standard | Own-brand granola | kg | Medium/high |
| own_brand_rice_snaps_standard | Own-brand rice snaps | kg | Medium |
| own_brand_choco_hoops_standard | Own-brand chocolate hoops | kg | Medium |
| own_brand_honey_nut_flakes_standard | Own-brand honey nut flakes | kg | Medium |
| own_brand_muesli_standard | Own-brand muesli | kg | Medium/high |

MVP priority:

1. cornflakes;
2. porridge oats;
3. wheat biscuits;
4. granola only after human review workflow exists.

## 12. Group: Own-Brand Cornflakes

### 12.1 Canonical Group

```text
own_brand_cornflakes_standard
```

### 12.2 Include Rules

| Attribute | Required value |
|---|---|
| Category | Breakfast cereal |
| Product type | Cornflakes |
| Brand owner | Retailer own-label |
| Tier | Retailer standard |
| Flavour | Plain |
| Unit basis | kg |

Example included products:

```text
Tesco Corn Flakes 500g
Asda Corn Flakes 500g
Sainsbury's Corn Flakes 500g
Morrisons Corn Flakes 500g
```

### 12.3 Exclude Rules

Exclude:

1. Kellogg's Corn Flakes;
2. value range cornflakes;
3. premium range cornflakes;
4. organic cornflakes;
5. honey nut cornflakes;
6. frosted flakes;
7. chocolate cornflakes;
8. bran flakes;
9. rice snaps;
10. multigrain flakes;
11. variety packs.

### 12.4 Pack-Size Rule

```text
450g to 750g
```

For early MVP, prefer 500g standard packs where available.

### 12.5 Matching Rule

```text
IF category = breakfast cereal
AND product_type = cornflakes
AND flavour = plain
AND tier = retailer_standard
AND brand_owner = retailer_own_label
AND normalised_size_unit = kg
AND normalised_size_value BETWEEN 0.45 AND 0.75
THEN group = own_brand_cornflakes_standard
```

### 12.6 Progression Tasks

1. Add cornflakes seed fixture group.
2. Add parser synonym handling for "Corn Flakes" and "Cornflakes".
3. Add negative tests for honey nut, frosted and branded cornflakes.

## 13. Group: Own-Brand Wheat Biscuits

### 13.1 Canonical Group

```text
own_brand_wheat_biscuits_standard
```

### 13.2 Include Rules

Example included products:

```text
Tesco Wheat Biscuits 24 Pack
Asda Wheat Bisks 24 Pack
Sainsbury's Wheat Biscuits 24
Morrisons Wheat Biscuits 24 Pack
```

### 13.3 Exclude Rules

Exclude:

1. Weetabix branded products;
2. chocolate wheat biscuits;
3. minis;
4. protein variants;
5. organic variants;
6. value tier;
7. premium tier;
8. variety packs.

### 13.4 Unit Basis

Preferred:

```text
biscuit
```

Fallback:

```text
kg
```

Use `biscuit` when count is clear. Use `kg` only when count is unavailable but weight and equivalent format are reliable.

### 13.5 Matching Rule

```text
IF category = breakfast cereal
AND product_type IN (wheat biscuit, wheat bisks)
AND form = biscuit
AND tier = retailer_standard
AND brand_owner = retailer_own_label
AND count BETWEEN 20 AND 30
THEN group = own_brand_wheat_biscuits_standard
```

### 13.6 Progression Tasks

1. Add count extraction to product normalisation.
2. Add unit basis `biscuit`.
3. Add synonym handling for "wheat bisks".
4. Add negative tests for Weetabix, minis and chocolate variants.

## 14. Group: Own-Brand Porridge Oats

### 14.1 Canonical Group

```text
own_brand_porridge_oats_standard
```

### 14.2 Include Rules

Example included products:

```text
Tesco Porridge Oats 1kg
Asda Porridge Oats 1kg
Sainsbury's Porridge Oats 1kg
Morrisons Porridge Oats 1kg
```

### 14.3 Exclude Rules

Exclude:

1. instant oat sachets;
2. flavoured porridge sachets;
3. jumbo oats;
4. organic oats;
5. branded oats;
6. granola;
7. muesli.

### 14.4 Unit Basis

```text
kg
```

### 14.5 Matching Rule

```text
IF category = breakfast cereal
AND product_type = porridge oats
AND form = standard oats
AND tier = retailer_standard
AND brand_owner = retailer_own_label
AND normalised_size_unit = kg
AND normalised_size_value BETWEEN 0.75 AND 1.5
THEN group = own_brand_porridge_oats_standard
```

### 14.6 Progression Tasks

1. Add porridge oats seed fixture group.
2. Add negative tests for jumbo oats and sachets.
3. Add parser distinction between porridge oats, jumbo oats and oat sachets.

## 15. Group: Own-Brand Granola

### 15.1 Canonical Group

```text
own_brand_granola_standard
```

### 15.2 Include Rules

Include only plain or baseline own-brand granola when comparable.

Example included products:

```text
Tesco Granola 1kg
Asda Granola 1kg
Sainsbury's Granola 1kg
Morrisons Granola 1kg
```

### 15.3 Exclude Rules

Exclude:

1. chocolate granola;
2. honey granola if not the baseline equivalent;
3. fruit and nut granola;
4. protein granola;
5. low-sugar specialist variants;
6. premium granola;
7. organic granola;
8. branded granola.

### 15.4 Confidence Warning

Granola is lower confidence than cornflakes or porridge oats because baseline products vary materially by recipe.

For MVP, use human-reviewed groups only.

### 15.5 Matching Rule

```text
IF category = breakfast cereal
AND product_type = granola
AND flavour IN (plain, baseline)
AND tier = retailer_standard
AND brand_owner = retailer_own_label
AND normalised_size_unit = kg
AND normalised_size_value BETWEEN 0.5 AND 1.2
THEN group = own_brand_granola_standard
AND review_status = needs_human_review
```

### 15.6 Progression Tasks

1. Do not auto-match granola initially.
2. Add human-reviewed seed examples first.
3. Add exclusion tests for chocolate, fruit, nut, protein and premium variants.
4. Reassess whether baseline granola is consistent enough across retailers.

## 16. Implementation Backlog

### 16.1 Parser Work

1. Add cereal type classifier.
2. Add fish species classifier.
3. Add coating detector.
4. Add form detector for fillet, loin, portion, biscuit, flakes and sachets.
5. Add count extraction for products such as wheat biscuits.
6. Add exclusion flag extraction.

### 16.2 Group Definition Work

1. Store group definitions as structured fixtures.
2. Add include and exclude term lists per group.
3. Add pack-size tolerances per group.
4. Add unit-basis requirements per group.
5. Add review policy per group.

### 16.3 Test Work

1. Add positive and negative fixtures for cornflakes.
2. Add positive and negative fixtures for porridge oats.
3. Add positive and negative fixtures for wheat biscuits.
4. Add positive and negative fixtures for frozen cod.
5. Add granola tests only after human-reviewed examples exist.

### 16.4 Scraping Work

1. Ensure crawler captures category breadcrumb.
2. Ensure crawler captures image URL.
3. Ensure crawler preserves full raw title.
4. Ensure crawler captures unit price and pack size separately.
5. Ensure raw snapshots are retained before parsing.

## 17. Recommended Targeted Progression

Proceed in this order:

1. Implement structured group definitions for cornflakes and porridge oats.
2. Add parser tests for cereal type, tier and flavour exclusions.
3. Add group matching tests for cornflakes and porridge oats.
4. Add count-aware parsing for wheat biscuits.
5. Add frozen cod only after image URL and category breadcrumb are available from ingestion.
6. Add human-review queue support before granola auto-matching.

This order keeps early grouping work high-confidence and avoids spending effort on categories that need richer metadata before they can be matched safely.
