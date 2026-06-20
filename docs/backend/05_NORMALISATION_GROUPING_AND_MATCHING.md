# BasketGuard Normalisation, Grouping and Matching

## Purpose

This document turns raw supermarket product data into controlled equivalence groups.

The grouping catalogue is the authority for what should and should not be considered comparable.

## Core rule

```text
Only group products when a normal shopper would reasonably treat them as substitutes.
```

BasketGuard must prefer fewer high-confidence groups over broad weak groups.

## Normalisation stages

```text
Raw title/price/pack text
  -> unit and pack normalisation
  -> brand-owner parsing
  -> tier parsing
  -> product-type parsing
  -> exclusion flag extraction
  -> group candidate scoring
  -> auto-match/review/no-match
```

## Unit normalisation

### Weight

```text
500g     -> 0.5 kg
1kg      -> 1.0 kg
750g     -> 0.75 kg
2 x 500g -> 1.0 kg
```

### Volume

```text
1L        -> 1.0 l
500ml     -> 0.5 l
6 x 330ml -> 1.98 l
```

### Count

```text
24 pack       -> count = 24
6 rolls       -> count = 6
10 sachets    -> count = 10
12 fishcakes  -> count = 12
```

### Unit price conversion

```text
75p/100g -> £7.50/kg
£1.20/kg -> £1.20/kg
£0.10 each -> £0.10/item
```

## Unit basis policy

| Product family | Preferred unit basis | Notes |
|---|---|---|
| Cereal flakes | kg | Weight comparison is valid |
| Porridge oats | kg | Exclude sachets and jumbo variants unless separate group |
| Wheat biscuits | biscuit | Count preferred; kg fallback only when format is reliable |
| Pasta/rice/flour/sugar | kg | Low-risk commodity groups |
| Milk/juice/oil | litre | Volume comparison |
| Eggs | egg | Count and size class matter |
| Toilet roll equivalent future non-food | roll/sheet | Not a food group but same logic applies |
| Meat/fish | kg | Must parse cut/species/form |
| Ready meals | meal or kg | Usually human review initially |
| Multipack snacks | item or kg | Product family dependent |

## Brand-owner parsing

Allowed brand-owner values:

```text
retailer_own_label
national_brand
licensed_brand
unknown
```

Examples:

```text
Tesco Corn Flakes -> retailer_own_label
Asda Just Essentials -> retailer_own_label
Kellogg's Corn Flakes -> national_brand
Young's Cod Fillets -> national_brand
```

## Tier parsing

Allowed tier values:

```text
retailer_value
retailer_standard
retailer_premium
retailer_organic
specialist_dietary
national_brand_standard
national_brand_premium
unknown
```

Tier examples:

| Retailer | Value tier | Standard tier | Premium tier |
|---|---|---|---|
| Tesco | Stockwell | Tesco | Finest |
| Asda | Just Essentials | Asda | Extra Special |
| Sainsbury's | Stamford Street | Sainsbury's | Taste the Difference |
| Morrisons | Savers | Morrisons | The Best |
| Waitrose | Essential Waitrose | Waitrose | No.1 |

Do not group value, standard and premium products unless a group explicitly permits tier comparison.

## Exclusion flags

Every parser should extract exclusion flags.

Common flags:

```text
branded
value_tier
premium_tier
organic
free_from
gluten_free
lactose_free
vegan
flavoured
coated
smoked
marinated
instant
sachets
multipack
mini
protein
low_sugar
reduced_fat
kids
seasonal
limited_edition
```

## Equivalence group definition format

Equivalence group definitions should live as structured YAML or JSON fixtures first. Persist the group identity in the existing `equivalence_groups` table, and persist product-to-group decisions in `product_group_memberships`.

If group rules need to be queryable in PostgreSQL later, add `definition_json`, `version` and `status` to `equivalence_groups`, or add an `equivalence_group_versions` child table in a future numbered migration.

Example:

```yaml
slug: own_brand_cornflakes_standard
name: Own-brand cornflakes
status: active
risk_level: low
unit_basis: kg
brand_owner: retailer_own_label
tier: retailer_standard
required:
  category:
    contains_any:
      - cereal
      - breakfast cereal
  product_type: cornflakes
  flavour: plain
  normalised_size_unit: kg
size_range:
  min: 0.45
  max: 0.75
exclude_terms:
  - kellogg
  - honey
  - frosted
  - chocolate
  - bran
  - organic
  - finest
  - taste the difference
review_triggers:
  - category_missing
  - unit_price_missing
  - tier_unknown
auto_match_threshold: 0.92
review_threshold: 0.75
```

## Matching score model

Use deterministic scoring.

Suggested components:

| Signal | Weight |
|---|---:|
| Category breadcrumb supports group | 0.15 |
| Product type exact match | 0.25 |
| Brand owner exact match | 0.15 |
| Tier exact match | 0.15 |
| Form/state exact match where relevant | 0.10 |
| Unit basis valid | 0.10 |
| Pack size in range | 0.05 |
| No exclusion flags | 0.05 |

Suggested thresholds:

```text
auto_match:   >= 0.92
human_review: >= 0.75 and < 0.92
no_match:     < 0.75
```

Hard exclusions override score.

## Hard exclusions

Never auto-match when any of these differ materially:

1. product type;
2. brand owner;
3. tier;
4. form;
5. state;
6. flavour;
7. coating;
8. species;
9. unreliable unit basis.

Example:

```text
Cod fillets != cod loins
Cornflakes != frosted flakes
Porridge oats != instant sachets
Standard baked beans != reduced sugar baked beans
Plain Greek yogurt != flavoured Greek yogurt
```

## Risk levels

### Low-risk groups

Characteristics:

1. commodity or simple product;
2. stable format;
3. simple unit basis;
4. low recipe variation;
5. clear titles.

Examples:

```text
own_brand_cornflakes_standard
own_brand_porridge_oats_standard
own_brand_spaghetti_standard
own_brand_plain_flour_standard
own_brand_granulated_sugar_standard
own_brand_long_grain_rice_standard
```

### Medium-risk groups

Characteristics:

1. format or count matters;
2. title synonyms vary;
3. tier ambiguity is common;
4. recipe may vary moderately.

Examples:

```text
own_brand_wheat_biscuits_standard
own_brand_baked_beans_standard
own_brand_cheddar_mature_standard
own_brand_butter_unsalted_standard
own_brand_frozen_peas_standard
```

### Medium/high-risk groups

Characteristics:

1. species/cut/form matters;
2. recipe varies materially;
3. image review may be needed;
4. title alone is unreliable.

Examples:

```text
own_brand_frozen_cod_fillets_standard
own_brand_granola_standard
own_brand_chicken_breast_fillets_standard
own_brand_lasagne_ready_meal_standard
own_brand_plant_based_burgers_standard
```

### Blocked for auto-match initially

Do not auto-match:

1. ready meals;
2. recipe-led sauces;
3. premium ranges;
4. seasonal products;
5. mixed meat/fish packs;
6. deli counter equivalents;
7. bakery cakes/desserts;
8. products with unclear unit basis.

## Initial group candidates

### Phase 1 groups

```text
own_brand_cornflakes_standard
own_brand_porridge_oats_standard
own_brand_spaghetti_standard
own_brand_penne_standard
own_brand_plain_flour_standard
own_brand_granulated_sugar_standard
own_brand_long_grain_rice_standard
own_brand_baked_beans_standard
```

### Phase 2 groups

```text
own_brand_wheat_biscuits_standard
own_brand_semi_skimmed_milk_2l_standard
own_brand_whole_milk_2l_standard
own_brand_unsalted_butter_standard
own_brand_mature_cheddar_standard
own_brand_frozen_peas_standard
own_brand_frozen_chips_standard
own_brand_tinned_tomatoes_chopped_standard
```

### Phase 3 groups

```text
own_brand_frozen_cod_fillets_standard
own_brand_chicken_breast_fillets_standard
own_brand_minced_beef_5_percent_standard
own_brand_eggs_medium_free_range_standard
own_brand_plain_greek_yogurt_standard
own_brand_granola_standard_reviewed
```

## Parser test policy

Every group needs:

1. positive fixtures;
2. negative fixtures;
3. ambiguous fixtures;
4. tier tests;
5. brand-owner tests;
6. pack-size boundary tests;
7. unit-basis tests;
8. category-title disagreement tests.

## Grouping success criteria

A group is production-ready when:

1. equivalence group fixture exists;
2. positive fixtures pass;
3. negative fixtures are rejected;
4. ambiguous fixtures go to review;
5. parser confidence is recorded;
6. match reason is explainable;
7. review queue can display evidence;
8. reports only use high-confidence or human-reviewed memberships from `product_group_memberships`.
