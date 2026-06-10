from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .group_comparison import Connection


# Products may be absent for snapshot-only review items, so subject fields
# coalesce between the product row and the raw snapshot evidence.
_REVIEW_REQUIRED_SELECT = """
SELECT
    review_queue_items.id,
    retailers.name,
    retailers.slug,
    COALESCE(products.canonical_name, raw_product_snapshots.raw_title),
    COALESCE(products.url, raw_product_snapshots.url),
    equivalence_groups.slug,
    review_queue_items.match_confidence,
    review_queue_items.match_reason,
    review_queue_items.created_at,
    review_queue_items.raw_snapshot_id
FROM review_queue_items
JOIN equivalence_groups
    ON equivalence_groups.id = review_queue_items.equivalence_group_id
LEFT JOIN products
    ON products.id = review_queue_items.product_id
LEFT JOIN raw_product_snapshots
    ON raw_product_snapshots.id = review_queue_items.raw_snapshot_id
LEFT JOIN retailers
    ON retailers.id = COALESCE(products.retailer_id, raw_product_snapshots.retailer_id)
WHERE review_queue_items.status = 'open'
"""

_ORDER_OLDEST_FIRST = """
ORDER BY review_queue_items.created_at ASC
"""

REVIEW_REQUIRED_SQL = _REVIEW_REQUIRED_SELECT + _ORDER_OLDEST_FIRST

REVIEW_REQUIRED_FOR_GROUP_SQL = (
    _REVIEW_REQUIRED_SELECT
    + "  AND equivalence_groups.slug = %s\n"
    + _ORDER_OLDEST_FIRST
)


@dataclass(frozen=True)
class ReviewRequiredItem:
    review_item_id: str
    retailer_name: str | None
    retailer_slug: str | None
    product_title: str | None
    product_url: str | None
    proposed_group_slug: str
    match_confidence: Decimal
    match_reason: str | None
    created_at: str
    raw_snapshot_id: str | None


@dataclass(frozen=True)
class ReviewRequiredReport:
    group_slug_filter: str | None
    items: tuple[ReviewRequiredItem, ...]

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def proposed_group_slugs(self) -> tuple[str, ...]:
        return tuple(sorted({item.proposed_group_slug for item in self.items}))


def fetch_review_required_products(
    connection: Connection,
    group_slug: str | None = None,
) -> ReviewRequiredReport:
    """Return open review queue items oldest-first, optionally for one group.

    This is the review-required products report: every open
    ``review_queue_items`` row joined to its product (when linked), retailer,
    proposed equivalence group and raw snapshot evidence. Resolved items are
    excluded; review decisions are out of scope here.
    """

    cursor = connection.cursor()
    try:
        if group_slug is None:
            cursor.execute(REVIEW_REQUIRED_SQL, ())
        else:
            cursor.execute(REVIEW_REQUIRED_FOR_GROUP_SQL, (group_slug,))
        rows = cursor.fetchall()
    finally:
        cursor.close()

    items = tuple(_item_from_row(row) for row in rows)
    return ReviewRequiredReport(group_slug_filter=group_slug, items=items)


def _item_from_row(row: tuple[Any, ...]) -> ReviewRequiredItem:
    (
        review_item_id,
        retailer_name,
        retailer_slug,
        product_title,
        product_url,
        proposed_group_slug,
        match_confidence,
        match_reason,
        created_at,
        raw_snapshot_id,
    ) = row
    return ReviewRequiredItem(
        review_item_id=str(review_item_id),
        retailer_name=str(retailer_name) if retailer_name is not None else None,
        retailer_slug=str(retailer_slug) if retailer_slug is not None else None,
        product_title=str(product_title) if product_title is not None else None,
        product_url=str(product_url) if product_url is not None else None,
        proposed_group_slug=str(proposed_group_slug),
        match_confidence=(
            match_confidence
            if isinstance(match_confidence, Decimal)
            else Decimal(str(match_confidence))
        ),
        match_reason=str(match_reason) if match_reason is not None else None,
        created_at=str(created_at),
        raw_snapshot_id=str(raw_snapshot_id) if raw_snapshot_id is not None else None,
    )
