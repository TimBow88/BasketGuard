"""CLI entrypoint to apply pending SQL migrations against PostgreSQL.

    python -m basketguard_shared.migrate \
        --database-url postgresql://basketguard:basketguard@localhost:5432/basketguard \
        --migrations-dir db/migrations

The database URL falls back to ``Settings.from_env`` (``BASKETGUARD_DATABASE_URL``
then ``DATABASE_URL``). With ``--dry-run`` it prints the pending versions and
applies nothing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

from .migrations import MigrationRunner, discover_migrations
from .settings import Settings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply BasketGuard SQL migrations.")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--migrations-dir", default="db/migrations")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    migrations = discover_migrations(args.migrations_dir)
    settings = Settings.from_env()
    database_url = args.database_url or settings.database_url

    if args.dry_run:
        connection = _NullConnection()
        runner = MigrationRunner(connection)
        # Without a database we cannot know what is applied; just list discovered.
        for migration in migrations:
            print(f"discovered {migration.version} {migration.name}")
        return 0

    if not database_url:
        parser.error(
            "No database URL. Pass --database-url or set BASKETGUARD_DATABASE_URL."
        )

    connection = _connect(database_url)
    try:
        applied = MigrationRunner(connection).apply(migrations)
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            close()

    if applied:
        for version in applied:
            print(f"applied {version}")
    else:
        print("no pending migrations")
    return 0


def _connect(database_url: str) -> Any:
    try:
        import psycopg

        return psycopg.connect(database_url)
    except ImportError:
        pass
    try:
        import psycopg2

        return psycopg2.connect(database_url)
    except ImportError as error:  # pragma: no cover - depends on local install
        raise SystemExit(
            "Install psycopg or psycopg2 to run migrations."
        ) from error


class _NullConnection:  # pragma: no cover - only used by --dry-run listing
    def cursor(self) -> Any:
        raise RuntimeError("dry-run does not open a database connection")

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
