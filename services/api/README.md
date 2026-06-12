# BasketGuard API

Minimal FastAPI skeleton exposing the existing query-based reports over HTTP.
No ORM: every endpoint opens a DB-API connection through the shared
`open_postgres_connection` helper and passes it straight to the reporting
functions in `basketguard_reporting`.

## Endpoints

| Route | Report |
|---|---|
| `GET /health` | Liveness check, no database access. |
| `GET /reports/group-comparison/{group_slug}` | Latest eligible price per retailer for one group. |
| `GET /reports/group-history/{group_slug}?window_days=90` | Eligible observations per retailer over a rolling window. |
| `GET /reports/retailer-gaps?group_slug=a&group_slug=b` | Cheapest-vs-dearest unit-price gap per group. |
| `GET /reports/review-required?group_slug=` | Open review queue items, optionally for one group. |
| `POST /review-items/{id}/approve` | Resolve an open review item and upsert a `human_reviewed=true` membership. |
| `POST /review-items/{id}/reject` | Resolve an open review item and remove any membership. |

The decision endpoints accept an optional JSON body `{"reviewer_notes": "..."}`
and return 404 when the item is missing or already resolved.

Money values are serialised as strings to preserve decimal precision.

## Running locally

```bash
pip install -r services/api/requirements.txt uvicorn
set BASKETGUARD_DATABASE_URL=postgresql://...
python -m uvicorn basketguard_api.app:app --app-dir services/api/src
```

The reporting and ingestion `src` directories must be importable
(install them or extend `PYTHONPATH` the same way the tests do).
