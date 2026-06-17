from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

from basketguard_shared import (  # noqa: E402
    Migration,
    MigrationError,
    MigrationRunner,
    discover_migrations,
)


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self._connection = connection
        self._result: list[tuple[Any, ...]] = []
        self.closed = False

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        self._connection.executions.append((sql, params))
        if self._connection.fail_on and self._connection.fail_on in sql:
            raise RuntimeError("boom")
        if sql.startswith("CREATE TABLE IF NOT EXISTS schema_migrations"):
            self._connection.tracking_table_exists = True
        elif sql.startswith("SELECT version FROM schema_migrations"):
            self._result = [(version,) for version in sorted(self._connection.applied)]
        elif sql.startswith("INSERT INTO schema_migrations"):
            self._connection.applied.add(params[0])

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._result

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, *, applied: set[str] | None = None, fail_on: str | None = None) -> None:
        self.executions: list[tuple[str, tuple[Any, ...]]] = []
        self.applied: set[str] = set(applied or set())
        self.committed = 0
        self.rolled_back = 0
        self.fail_on = fail_on
        self.tracking_table_exists = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.committed += 1

    def rollback(self) -> None:
        self.rolled_back += 1


def _migration(tmp: Path, version: str, name: str, sql: str) -> Migration:
    path = tmp / f"{version}_{name}.sql"
    path.write_text(sql, encoding="utf-8")
    return Migration(version=version, name=name, path=path)


class DiscoverMigrationsTests(unittest.TestCase):
    def test_reads_repo_migrations_in_version_order(self) -> None:
        migrations = discover_migrations(ROOT / "db" / "migrations")

        versions = [migration.version for migration in migrations]
        self.assertEqual(versions, ["0001", "0002", "0003", "0004"])
        self.assertTrue(migrations[0].sql.strip().startswith("-- BasketGuard"))

    def test_missing_directory_raises(self) -> None:
        with self.assertRaises(MigrationError):
            discover_migrations(ROOT / "db" / "does-not-exist")


class MigrationRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.migrations = [
            _migration(self.tmp, "0001", "initial", "CREATE TABLE a (id int);"),
            _migration(self.tmp, "0002", "second", "CREATE TABLE b (id int);"),
        ]

    def test_applies_all_pending_and_records_versions(self) -> None:
        connection = FakeConnection()

        applied = MigrationRunner(connection).apply(self.migrations)

        self.assertEqual(applied, ["0001", "0002"])
        self.assertEqual(connection.applied, {"0001", "0002"})
        # tracking-table ensure + two migration applies all committed.
        self.assertGreaterEqual(connection.committed, 3)
        self.assertEqual(connection.rolled_back, 0)

    def test_skips_already_applied_migrations(self) -> None:
        connection = FakeConnection(applied={"0001"})

        applied = MigrationRunner(connection).apply(self.migrations)

        self.assertEqual(applied, ["0002"])

    def test_pending_lists_only_unapplied(self) -> None:
        connection = FakeConnection(applied={"0001"})

        pending = MigrationRunner(connection).pending(self.migrations)

        self.assertEqual([m.version for m in pending], ["0002"])

    def test_failure_rolls_back_and_wraps_error(self) -> None:
        connection = FakeConnection(fail_on="CREATE TABLE b")

        with self.assertRaises(MigrationError):
            MigrationRunner(connection).apply(self.migrations)

        # First migration committed, second rolled back, and not recorded.
        self.assertEqual(connection.applied, {"0001"})
        self.assertEqual(connection.rolled_back, 1)


if __name__ == "__main__":
    unittest.main()
