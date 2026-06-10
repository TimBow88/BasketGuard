from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .db_mapping import IngestionPersistencePlan


class Cursor(Protocol):
    def execute(self, sql: str, params: tuple[Any, ...]) -> Any:
        ...

    def close(self) -> Any:
        ...


class Connection(Protocol):
    def cursor(self) -> Cursor:
        ...

    def commit(self) -> Any:
        ...

    def rollback(self) -> Any:
        ...


@dataclass(frozen=True)
class SavePlanResult:
    inserted_or_updated: dict[str, int]

    @property
    def total_rows(self) -> int:
        return sum(self.inserted_or_updated.values())


class IngestionPlanRepository:
    """Persist ingestion row payloads using a DB-API compatible connection."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def save_plan(self, plan: IngestionPersistencePlan) -> SavePlanResult:
        cursor = self.connection.cursor()
        counts: dict[str, int] = {}
        try:
            for table_name, rows in _ordered_plan_rows(plan):
                rows = list(rows)
                if not rows:
                    counts[table_name] = 0
                    continue
                for row in rows:
                    cursor.execute(_upsert_sql(table_name, row), tuple(row.values()))
                counts[table_name] = len(rows)
            self.connection.commit()
            return SavePlanResult(inserted_or_updated=counts)
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()


def _ordered_plan_rows(plan: IngestionPersistencePlan):
    yield "retailers", plan.retailers
    yield "equivalence_groups", plan.equivalence_groups
    yield "collection_targets", plan.collection_targets
    yield "ingestion_jobs", plan.ingestion_jobs
    yield "raw_product_snapshots", plan.raw_product_snapshots
    yield "products", plan.products
    yield "product_group_memberships", plan.product_group_memberships
    yield "price_observations", plan.price_observations
    yield "ingestion_job_targets", plan.ingestion_job_targets
    # plan.group_review_candidates is intentionally not persisted; review rows
    # belong to a future review_queue_items migration.


def _upsert_sql(table_name: str, row: dict[str, Any]) -> str:
    columns = list(row)
    if "id" not in row:
        raise ValueError(f"Cannot upsert {table_name} row without id")
    quoted_columns = [_quote_identifier(column) for column in columns]
    placeholders = ", ".join(["%s"] * len(columns))
    update_columns = [column for column in columns if column != "id"]
    assignments = ", ".join(
        f"{_quote_identifier(column)} = EXCLUDED.{_quote_identifier(column)}"
        for column in update_columns
    )
    conflict_action = f"DO UPDATE SET {assignments}" if assignments else "DO NOTHING"

    return (
        f"INSERT INTO {_quote_identifier(table_name)} "
        f"({', '.join(quoted_columns)}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT (id) {conflict_action}"
    )


def _quote_identifier(value: str) -> str:
    if not value.replace("_", "").isalnum() or value[0].isdigit():
        raise ValueError(f"Unsafe SQL identifier: {value!r}")
    return f'"{value}"'
