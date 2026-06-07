# Product Normalisation and Equivalence

## Purpose

This is the core intellectual property of BasketGuard.

BasketGuard must compare equivalent products, not isolated SKUs. The app must understand that standard own-brand chopped tomatoes at Tesco, Asda and Sainsbury's are comparable, while premium, organic or branded alternatives may not be.

## Key concept: equivalence group

An equivalence group is a set of products that are comparable for price-behaviour analysis.

Example:

```text
Group: own_brand_chopped_tomatoes_standard_400g

Members:
- Tesco Chopped Tomatoes 400g
- Asda Chopped Tomatoes 400g
- Sainsbury's Chopped Tomatoes 400g
- Morrisons Chopped Tomatoes 400g

Excluded:
- Tesco Finest Cherry Tomatoes 400g
- Napolina Chopped Tomatoes 400g
- Mutti Polpa 400g
- Organic chopped tomatoes
- Chopped tomatoes with basil
```

## Product attributes

Each product should be parsed into structured attributes.

| Attribute | Example |
|---|---|
| Retailer | Tesco |
| Product name | Tesco Chopped Tomatoes 400G |
| Brand | Tesco |
| Brand owner | Retailer own-label |
| Category | Food cupboard |
| Subcategory | Tinned tomatoes |
| Product type | Chopped tomatoes |
| Form | Chopped |
| Pack size | 400g |
| Unit basis | kg |
| Tier | Retailer standard |
| Organic | false |
| Premium | false |
| Value range | false |
| Multipack | false |
| Flavour | Plain |
| Dietary | Vegan |

## Tier model

Suggested quality tiers:

```text
retailer_value
retailer_standard
retailer_premium
branded_standard
branded_premium
organic
specialist_dietary
```

Equivalence rules should normally compare within the same tier.

Examples:

- Tesco standard ↔ Asda standard;
- Tesco Finest ↔ Asda Extra Special;
- Tesco value ↔ Asda Just Essentials;
- Napolina ↔ Napolina across retailers;
- organic ↔ organic.

## Unit normalisation

All products require a comparable unit basis.

| Product type | Unit basis |
|---|---|
| Milk | litre |
| Cheese | kg |
| Tomatoes | kg |
| Pasta | kg |
| Rice | kg |
| Toilet roll | sheet or roll, with caution |
| Washing capsules | wash |
| Dishwasher tablets | tablet |
| Nappies | nappy |

Examples:

```text
400g -> 0.4kg
2.272L -> 2.272L
4 pints -> 2.272L
30 capsules -> 30 washes
```

## Matching strategy

Use a hybrid approach.

### Rule-based matching

Good for stable staples.

Example rule:

```text
IF category = tinned tomatoes
AND product_type = chopped tomatoes
AND tier = retailer_standard
AND pack_size BETWEEN 380g AND 420g
AND flavour = plain
THEN group = own_brand_chopped_tomatoes_standard_400g
```

### Embedding-assisted matching

Useful for messy titles.

Examples:

- British Semi Skimmed Milk 4 Pints;
- Semi Skimmed Milk 2.272L;
- Fresh British Semi-Skimmed Milk 4 Pint.

These should cluster together despite different wording.

### Human review

For MVP, a human review queue is essential.

Suggested thresholds:

```text
match_score > 0.92: auto-match
match_score 0.75 to 0.92: human review
match_score < 0.75: no match
```

## Match score formula

Initial formula:

```text
match_score =
  0.30 * title_similarity
+ 0.25 * category_match
+ 0.20 * pack_size_similarity
+ 0.15 * tier_match
+ 0.10 * attribute_match
```

## Product lineage

Product lineage tracks whether a product has changed over time.

Use cases:

1. product renamed;
2. pack size changed;
3. product discontinued and replaced;
4. old product URL redirected;
5. recipe or tier changed.

Lineage is needed for shrinkflation detection.

## Data confidence

Every equivalence group should have a confidence score.

Example:

```json
{
  "equivalence_group": "own_brand_chopped_tomatoes_standard_400g",
  "confidence": 0.96,
  "review_status": "human_reviewed",
  "notes": "Standard own-brand, plain, 400g tins only. Premium and organic excluded."
}
```

## Principle

It is better to make fewer high-confidence comparisons than many weak comparisons.
