# BasketGuard Ingestion

Contracts and providers for collecting retailer product observations.

Current scope:

- typed ingestion contracts;
- fixture-backed mock provider;
- Tesco HTML parser and disabled-by-default allowlisted provider;
- no live retailer crawling by default;
- no network requests unless the Tesco feature flag is explicitly enabled;
- no database writes.

The provider output maps to the initial PostgreSQL tables:

- `raw_product_snapshots`;
- `products`;
- `price_observations`;
- `ingestion_jobs`.

## Tesco Provider

`TescoIngestionProvider` will not run live collection unless both are true:

1. `TescoScraperConfig.enabled` is `true`;
2. `BASKETGUARD_ENABLE_TESCO_SCRAPER=1` is set in the environment.

The provider only accepts explicit allowlisted URLs. Parser behaviour is tested against saved HTML fixtures before any live collection is enabled.
