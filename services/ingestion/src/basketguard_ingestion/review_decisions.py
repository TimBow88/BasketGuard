from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from .db_mapping import _stable_uuid


APPROVE_DECISION = "approve_group_membership"
REJECT_DECISION = "reject_group_membership"

_SELECT_OPEN_ITEM_SQL = """
SELECT id, product_id, equivalence_group_id, match_confidence, match_reason, status
FROM review_queue_items
WHERE id = %s
"""

_RESOLVE_ITEM_SQL = """
UPDATE review_queue_items
SET status = 'resolved',
    decision = %s,
    reviewer_notes = %s,
    resolved_at = %s
WHERE id = %s
"""

_UPSERT_MEMBERSHIP_SQL = """
INSERT INTO product_group_memberships
    (id, product_id, equivalence_group_id, match_confidence, match_reason,
     is_primary_match, human_reviewed)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    match_confidence = EXCLUDED.match_confidence,
    match_reason = EXCLUDED.match_reason,
    human_reviewed = EXCLUDED.human_reviewed
"""

_DELETE_MEMBERSHIP_SQL = """
DELETE FROM product_group_memberships
WHERE product_id = %s AND equivalence_group_id = %s
"""


class ReviewDecisionError(ValueError):
    pass


class Cursor(Protocol):
    def execute(self, sql: str, params: tuple[Any, ...]) -> Any:
        ...

    def fetchone(self) -> tuple[Any, ...] | None:
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
class ReviewDecisionResult:
    review_item_id: str
    decision: str
    product_id: str | None
    equivalence_group_id: str
    membership_id: str | None
    resolved_at: str


def approve_review_item(
    connection: Connection,
    review_item_id: str,
    reviewer_notes: str | None = None,
    resolved_at: str | None = None,
) -> ReviewDecisionResult:
    """Resolve an open review item as approved and create the membership.

    The membership row uses the same deterministic product/group ID as the
    auto-match path, so approving an item upserts rather than duplicates, and
    `human_reviewed=true` makes the product eligible for group reports.
    """

    return _decide(
        connection,
        review_item_id,
        decision=APPROVE_DECISION,
        reviewer_notes=reviewer_notes,
        resolved_at=resolved_at,
    )


def reject_review_item(
    connection: Connection,
    review_item_id: str,
    reviewer_notes: str | None = None,
    resolved_at: str | None = None,
) -> ReviewDecisionResult:
    """Resolve an open review item as rejected and remove any membership.

    The resolved review item records the rejection for audit. A later
    collection run can still propose the product again; consulting resolved
    rejections during matching is a future enhancement.
    """

    return _decide(
        connection,
        review_item_id,
        decision=REJECT_DECISION,
        reviewer_notes=reviewer_notes,
        resolved_at=resolved_at,
    )


def _decide(
    connection: Connection,
    review_item_id: str,
    decision: str,
    reviewer_notes: str | None,
    resolved_at: str | None,
) -> ReviewDecisionResult:
    resolved_at = resolved_at or (
        datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    cursor = connection.cursor()
    try:
        cursor.execute(_SELECT_OPEN_ITEM_SQL, (review_item_id,))
        row = cursor.fetchone()
        if row is None:
            raise ReviewDecisionError(f"Review item not found: {review_item_id}")
        _, product_id, group_id, match_confidence, match_reason, status = row
        if status != "open":
            raise ReviewDecisionError(
                f"Review item {review_item_id} is already {status}"
            )

        membership_id = None
        if decision == APPROVE_DECISION:
            if product_id is None:
                raise ReviewDecisionError(
                    f"Review item {review_item_id} has no linked product to approve"
                )
            membership_id = _stable_uuid(
                "product_group_membership", str(product_id), str(group_id)
            )
            cursor.execute(
                _UPSERT_MEMBERSHIP_SQL,
                (
                    membership_id,
                    product_id,
                    group_id,
                    match_confidence,
                    match_reason,
                    True,
                    True,
                ),
            )
        elif product_id is not None:
            cursor.execute(_DELETE_MEMBERSHIP_SQL, (product_id, group_id))

        cursor.execute(
            _RESOLVE_ITEM_SQL,
            (decision, reviewer_notes, resolved_at, review_item_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()

    return ReviewDecisionResult(
        review_item_id=review_item_id,
        decision=decision,
        product_id=str(product_id) if product_id is not None else None,
        equivalence_group_id=str(group_id),
        membership_id=membership_id,
        resolved_at=resolved_at,
    )
