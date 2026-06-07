# Technical Architecture

## System overview

```text
Frontend Web App
       |
Backend API
       |
Core Database ------------------ Object Storage
       |                              |
Analytics Engine              Raw Snapshots
       |
Report Generator
       |
Email / Alerts

Data Ingestion Workers
       |
Retailer Websites / Receipts / Public Data
```

## Recommended stack

| Layer | Recommended technology |
|---|---|
| Frontend | Next.js / React |
| Backend API | FastAPI, Django, NestJS or similar |
| Database | PostgreSQL |
| Time-series support | TimescaleDB or partitioned PostgreSQL tables |
| Queue | Redis + BullMQ, Celery, or Temporal |
| Crawling | Playwright, Crawlee, Scrapy |
| ML / matching | Python, scikit-learn, sentence-transformers |
| Object storage | S3-compatible storage |
| Search | Meilisearch or OpenSearch |
| Reporting | Server-rendered HTML email initially |
| Hosting | AWS, GCP, Fly.io, Render, or similar |

## Main services

### 1. Frontend

Responsibilities:

- user onboarding;
- watchlist management;
- basket overview;
- worst-offender dashboard;
- item detail pages;
- methodology display;
- receipt upload interface.

### 2. Backend API

Responsibilities:

- authentication;
- user watchlists;
- report retrieval;
- product search;
- item detail data;
- receipt upload endpoints;
- admin review endpoints.

### 3. Ingestion workers

Responsibilities:

- crawl retailer data;
- collect raw snapshots;
- parse product details;
- schedule recurring jobs;
- record scrape health;
- flag parser failures.

### 4. Normalisation pipeline

Responsibilities:

- parse names;
- classify product type;
- extract pack size;
- convert units;
- classify tier;
- identify own-brand/branded/premium/organic variants.

### 5. Equivalence engine

Responsibilities:

- assign products to equivalence groups;
- calculate match confidence;
- create human-review tasks;
- manage product lineage;
- prevent weak comparisons.

### 6. Analytics engine

Responsibilities:

- calculate YoY changes;
- calculate competitor median;
- detect current premium;
- detect shrinkflation;
- assess promotion quality;
- calculate offender score;
- generate finding confidence.

### 7. Report generator

Responsibilities:

- weekly report;
- item alerts;
- basket comparison;
- retailer-specific warnings;
- email summaries.

## Processing flow

```text
1. Scheduler starts retailer collection job.
2. Crawler fetches target product pages or catalogue endpoints.
3. Raw response is saved.
4. Parser extracts product and price fields.
5. Clean observation is stored.
6. Normalisation pipeline standardises units and attributes.
7. Equivalence engine maps product to group.
8. Analytics engine calculates price behaviour metrics.
9. Report generator creates ranked findings.
10. User sees dashboard or receives email.
```

## Architecture principles

1. Store raw data before parsing.
2. Separate shelf, loyalty, promotion and effective prices.
3. Treat equivalence as a first-class domain object.
4. Use high-confidence comparisons only in user-facing claims.
5. Make every finding explainable.
6. Keep MVP narrow and data quality high.
7. Design ingestion as replaceable, not permanent.

## Admin tools needed

The product requires an internal admin interface early.

Admin features:

- review product matches;
- merge duplicate products;
- approve equivalence groups;
- inspect scrape failures;
- override parsed attributes;
- flag unreliable products;
- manage product lineage;
- view raw snapshots.

## Observability

Track:

- scrape success rate;
- parser error rate;
- price missing rate;
- outlier spikes;
- product count per retailer;
- group coverage;
- stale product count;
- human-review backlog;
- report generation failures.

## Security and privacy

If receipt or email import is added:

- minimise stored personal data;
- redact payment card details;
- separate receipt metadata from user identity where possible;
- encrypt sensitive data at rest;
- allow user deletion;
- clearly explain data usage.
