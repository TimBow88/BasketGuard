from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol


# Memberships below this confidence are needs-review territory and must not
# appear in reports unless a human has approved them.
DEFAULT_MIN_AUTO_MATCH_CONFIDENCE = Decimal("0.92")

GROUP_COMPARISON_SQL = """
SELECT DISTINCT ON (retailers.id)
    retailers.name,
    retailers.slug,
    products.canonical_name,
    products.pack_size_value,
    products.pack_size_unit,
    price_observations.shelf_price,
    price_observations.effective_price,
    price_observations.unit_price,
    price_observations.unit_price_basis,
    price_observations.availability,
    price_observations.collected_at,
    price_observations.raw_snapshot_id,
    product_group_memberships.match_confidence,
    product_group_memberships.human_reviewed
FROM equivalence_groups
JOIN product_group_memberships
    ON product_group_memberships.equivalence_group_id = equivalence_groups.id
JOIN products
    ON products.id = product_group_memberships.product_id
JOIN retailers
    ON retailers.id = products.retailer_id
JOIN price_observations
    ON price_observations.product_id = products.id
WHERE equivalence_groups.slug = %s
  AND products.is_active
  AND (
    product_group_memberships.human_reviewed
    OR product_group_memberships.match_confidence >= %s
  )
ORDER BY retailers.id, price_observations.collected_at DESC
"""


class Cursor(Protocol):
    def execute(self, sql: str, params: tuple[Any, ...]) -> Any:
        ...

    def fetchall(self) -> list[tuple[Any, ...]]:
        ...

    def close(self) -> Any:
        ...


class Connection(Protocol):
    def cursor(self) -> Cursor:
        ...


@dataclass(frozen=True)
class GroupComparisonEntry:
    retailer_name: str
    retailer_slug: str
    product_title: str
    pack_size_value: Decimal | None
    pack_size_unit: str | None
    shelf_price: Decimal
    effective_price: Decimal
    unit_price: Decimal
    unit_price_basis: str | None
    availability: str
    collected_at: str
    raw_snapshot_id: str | None
    match_confidence: Decimal
    human_reviewed: bool


@dataclass(frozen=True)
class GroupComparisonReport:
    group_slug: str
    entries: tuple[GroupComparisonEntry, ...]

    @property
    def retailer_count(self) -> int:
        return len(self.entries)

    @property
    def cheapest(self) -> GroupComparisonEntry | None:
        return self.entries[0] if self.entries else None

    @property
    def most_expensive(self) -> GroupComparisonEntry | None:
        return self.entries[-1] if self.entries else None

    @property
    def unit_price_gap(self) -> Decimal | None:
        if len(self.entries) < 2:
            return None
        return self.entries[-1].unit_price - self.entries[0].unit_price


def fetch_group_comparison(
    connection: Connection,
    group_slug: str,
    min_auto_match_confidence: Decimal = DEFAULT_MIN_AUTO_MATCH_CONFIDENCE,
) -> GroupComparisonReport:
    """Return the latest eligible price observation per retailer for one group.

    Only memberships that were auto-matched at or above the confidence floor,
    or explicitly human-approved, are eligible. Needs-review candidates are
    never persisted as memberships, and rejected products have no membership
    row, so neither can appear here. Entries are sorted by unit price, cheapest
    first, and each carries its raw snapshot ID for audit.
    """

    cursor = connection.cursor()
    try:
        cursor.execute(GROUP_COMPARISON_SQL, (group_slug, min_auto_match_confidence))
        rows = cursor.fetchall()
    finally:
        cursor.close()

    entries = sorted(
        (_entry_from_row(row) for row in rows),
        key=lambda entry: (entry.unit_price, entry.retailer_slug),
    )
    return GroupComparisonReport(group_slug=group_slug, entries=tuple(entries))


def _entry_from_row(row: tuple[Any, ...]) -> GroupComparisonEntry:
    (
        retailer_name,
        retailer_slug,
        product_title,
        pack_size_value,
        pack_size_unit,
        shelf_price,
        effective_price,
        unit_price,
        unit_price_basis,
        availability,
        collected_at,
        raw_snapshot_id,
        match_confidence,
        human_reviewed,
    ) = row
    return GroupComparisonEntry(
        retailer_name=str(retailer_name),
        retailer_slug=str(retailer_slug),
        product_title=str(product_title),
        pack_size_value=_optional_decimal(pack_size_value),
        pack_size_unit=str(pack_size_unit) if pack_size_unit is not None else None,
        shelf_price=_decimal(shelf_price),
        effective_price=_decimal(effective_price),
        unit_price=_decimal(unit_price),
        unit_price_basis=str(unit_price_basis) if unit_price_basis is not None else None,
        availability=str(availability),
        collected_at=str(collected_at),
        raw_snapshot_id=str(raw_snapshot_id) if raw_snapshot_id is not None else None,
        match_confidence=_decimal(match_confidence),
        human_reviewed=bool(human_reviewed),
    )


def _decimal(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _optional_decimal(value: Any) -> Decimal | None:
    return None if value is None else _decimal(value)
