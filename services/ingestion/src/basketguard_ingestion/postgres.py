from __future__ import annotations

import os
from typing import Any


DATABASE_URL_ENV = "BASKETGUARD_DATABASE_URL"


class PostgresConnectionError(RuntimeError):
    pass


def open_postgres_connection(database_url: str | None = None) -> Any:
    """Open a DB-API compatible PostgreSQL connection for repository writes."""
    resolved_url = database_url or os.environ.get(DATABASE_URL_ENV) or os.environ.get("DATABASE_URL")
    if not resolved_url:
        raise PostgresConnectionError(
            f"Set {DATABASE_URL_ENV} or pass --database-url for local persistence.",
        )

    try:
        import psycopg
    except ImportError:
        psycopg = None

    if psycopg is not None:
        return psycopg.connect(resolved_url)

    try:
        import psycopg2
    except ImportError as error:
        raise PostgresConnectionError(
            "Install psycopg or psycopg2 to use the local Postgres persistence command.",
        ) from error

    return psycopg2.connect(resolved_url)
