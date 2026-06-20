# Risks, Legal and Trust

## Purpose

BasketGuard depends on accurate price data, reliable product matching and careful language. A false or exaggerated claim could damage trust quickly.

## Main risks

1. scraping restrictions;
2. data accuracy;
3. postcode variation;
4. loyalty price complexity;
5. product equivalence errors;
6. legal risk from wording;
7. platform blocking;
8. user privacy if receipts are imported;
9. commercial dependency on fragile data sources.

## Scraping risk

Regular collection from supermarket websites may face:

- rate limiting;
- bot detection;
- changing page structure;
- CAPTCHA;
- blocked IPs;
- login/session issues;
- terms-of-service restrictions.

Technical feasibility does not remove legal or commercial risk.

Recommendation:

- use scraping for MVP/prototype;
- keep crawl scope limited;
- store raw evidence;
- avoid aggressive scraping;
- seek legal advice before public commercial launch;
- add user receipt import to reduce dependency on scraped data;
- consider licensed data later if traction exists.

## Accuracy risk

Potential causes of inaccurate alerts:

- wrong pack size parsed;
- unit price parsed incorrectly;
- loyalty price mistaken for shelf price;
- product out of stock;
- product replaced or discontinued;
- wrong equivalence group;
- regional price variation;
- promotion temporarily distorting price.

Mitigation:

- confidence score every finding;
- raw snapshots retained;
- human review for uncertain product matches;
- conservative alert thresholds;
- explain evidence;
- suppress low-confidence findings.

## Product matching risk

This is the biggest product-quality risk.

Bad comparison example:

```text
Tesco Finest Cherry Tomatoes 400g
compared with
Asda Just Essentials Chopped Tomatoes 400g
```

This would destroy user trust.

Mitigation:

- tier model;
- human review;
- high auto-match threshold;
- visible group members;
- user feedback mechanism;
- conservative comparisons.

## Legal wording risk

Avoid directly accusing retailers of illegal conduct.

Safer language:

- price spike;
- price outlier;
- weak offer;
- poor value;
- retailer-specific increase;
- above competitor median;
- switch recommended.

Riskier language:

- illegal price gouging;
- scam;
- fraud;
- cartel;
- profiteering stated as fact.

Aggressive marketing can exist, but user-facing findings should be evidence-led.

## Loyalty pricing risk

Loyalty pricing must be handled transparently.

Store separately:

- standard shelf price;
- loyalty price;
- offer price;
- historical median;
- cheapest competitor equivalent.

Example wording:

> Clubcard price is cheaper than Tesco shelf price, but not materially cheaper than this product's 12-month median.

## Privacy risk

> **Governing policy:** see `docs/14_DATA_HANDLING_AND_PRIVACY.md`. BasketGuard
> currently retains **no personal data** and does **not** import receipts; GDPR
> leads data-handling design. The receipt-import guidance below applies only if
> that policy is explicitly revisited and the BAS-54 privacy baseline is met
> first.

If receipt import is used, receipts may contain:

- purchase habits;
- location;
- payment fragments;
- loyalty identifiers;
- timestamps;
- household information.

Mitigation:

- redact card numbers and loyalty IDs;
- minimise stored personal data;
- allow deletion;
- encrypt sensitive data;
- explain exactly how receipt data is used;
- do not sell personal receipt-level data.

## Trust principles

1. Show evidence.
2. Show confidence.
3. Use unit prices.
4. Do not overclaim.
5. Let users challenge bad matches.
6. Separate loyalty and non-loyalty pricing.
7. Be clear when regional prices may vary.
8. Prefer fewer accurate alerts over many noisy alerts.

## Public disclaimer draft

> BasketGuard analyses collected online grocery prices, user-submitted basket data and product equivalence groups. Prices may vary by store, region, delivery slot, promotion and loyalty-card eligibility. BasketGuard flags price behaviour and value outliers; it does not make legal findings about retailer conduct.
