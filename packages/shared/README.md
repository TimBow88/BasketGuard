# BasketGuard Shared

Cross-cutting runtime utilities used by the backend services.

## Settings

`Settings` (`basketguard_shared.settings`) is the single, typed source of runtime
configuration, replacing scattered `os.environ` reads. Build it with
`Settings.from_env()` (or pass an explicit mapping in tests):

```python
from basketguard_shared import Settings

settings = Settings.from_env()
settings.require_database_url()
settings.retailer_enabled("tesco")
```

It carries the database URL, the set of retailers whose live-collection flag is
on, the fetcher mode (`urllib` / `headless`), request timeout / politeness delay
/ retry-backoff parameters, an optional proxy URL, the snapshot root, the
collection postcode context and the log level. Malformed values raise
`SettingsError` with an actionable message instead of failing later in a run. The
per-retailer flag names match those the providers already check, so adopting
`Settings` does not change behaviour.

## Migration runner

`discover_migrations` reads the `NNNN_name.sql` files in `db/migrations/` in
version order. `MigrationRunner` applies the not-yet-applied ones against a
DB-API connection and records each in a `schema_migrations` ledger, so runs are
idempotent and forward-only. Apply migrations with the CLI:

```bash
python -m basketguard_shared.migrate \
  --database-url postgresql://basketguard:basketguard@localhost:5432/basketguard \
  --migrations-dir db/migrations
```

`--dry-run` lists the discovered migrations without connecting. The runner is
connection-agnostic, so it is unit-tested against a fake connection with no
database.
