"""Forward-only migration runner for the raw SQL files in ``db/migrations/``.

The migrations are the database source of truth, but until now there was no way
to apply them programmatically or know which had run. This adds:

* ``discover_migrations`` — read ``NNNN_name.sql`` files in version order;
* ``MigrationRunner`` — apply pending migrations against a DB-API connection,
  recording each in a ``schema_migrations`` ledger so re-runs are idempotent.

Each migration file wraps its own ``BEGIN; ... COMMIT;``. The runner records the
applied version in a separate statement and commits, so a half-applied file is
never marked as done. The runner is connection-agnostic (inject any DB-API
connection); the ``migrate`` CLI builds a real PostgreSQL connection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol


MIGRATION_FILENAME = re.compile(r"^(?P<version>\d+)_(?P<name>.+)\.sql$")

TRACKING_TABLE = "schema_migrations"
_CREATE_TRACKING_TABLE = (
    f"CREATE TABLE IF NOT EXISTS {TRACKING_TABLE} ("
    "version TEXT PRIMARY KEY, "
    "name TEXT NOT NULL, "
    "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
)
_SELECT_APPLIED = f"SELECT version FROM {TRACKING_TABLE} ORDER BY version"
_INSERT_APPLIED = f"INSERT INTO {TRACKING_TABLE} (version, name) VALUES (%s, %s)"


class MigrationError(RuntimeError):
    pass


class _Cursor(Protocol):
    def execute(self, sql: str, params: tuple[Any, ...] = ...) -> Any: ...
    def fetchall(self) -> list[tuple[Any, ...]]: ...
    def close(self) -> Any: ...


class _Connection(Protocol):
    def cursor(self) -> _Cursor: ...
    def commit(self) -> Any: ...
    def rollback(self) -> Any: ...


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    path: Path

    @property
    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")


def discover_migrations(directory: str | Path) -> list[Migration]:
    base = Path(directory)
    if not base.is_dir():
        raise MigrationError(f"Migrations directory not found: {base}")

    migrations: list[Migration] = []
    seen: dict[str, Path] = {}
    for path in sorted(base.glob("*.sql")):
        match = MIGRATION_FILENAME.match(path.name)
        if not match:
            continue
        version = match.group("version")
        if version in seen:
            raise MigrationError(
                f"Duplicate migration version {version!r}: {seen[version].name} "
                f"and {path.name}."
            )
        seen[version] = path
        migrations.append(Migration(version=version, name=match.group("name"), path=path))

    migrations.sort(key=lambda migration: migration.version)
    return migrations


class MigrationRunner:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    def ensure_tracking_table(self) -> None:
        cursor = self.connection.cursor()
        try:
            cursor.execute(_CREATE_TRACKING_TABLE)
            self.connection.commit()
        finally:
            cursor.close()

    def applied_versions(self) -> set[str]:
        self.ensure_tracking_table()
        cursor = self.connection.cursor()
        try:
            cursor.execute(_SELECT_APPLIED)
            return {row[0] for row in cursor.fetchall()}
        finally:
            cursor.close()

    def pending(self, migrations: Iterable[Migration]) -> list[Migration]:
        applied = self.applied_versions()
        return [migration for migration in migrations if migration.version not in applied]

    def apply(self, migrations: Iterable[Migration]) -> list[str]:
        """Apply every not-yet-applied migration in order; return their versions."""

        pending = self.pending(migrations)
        applied: list[str] = []
        for migration in pending:
            cursor = self.connection.cursor()
            try:
                cursor.execute(migration.sql)
                cursor.execute(_INSERT_APPLIED, (migration.version, migration.name))
                self.connection.commit()
            except Exception as error:
                self.connection.rollback()
                raise MigrationError(
                    f"Failed applying migration {migration.version} "
                    f"({migration.name}): {error}"
                ) from error
            finally:
                cursor.close()
            applied.append(migration.version)
        return applied
