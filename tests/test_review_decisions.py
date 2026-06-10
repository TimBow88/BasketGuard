from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))

from basketguard_ingestion import (  # noqa: E402
    ReviewDecisionError,
    approve_review_item,
    reject_review_item,
)


OPEN_ITEM_ROW = (
    "review-id",
    "product-id",
    "group-id",
    Decimal("0.85"),
    "review:category_missing",
    "open",
)


class FakeCursor:
    def __init__(
        self,
        select_row: tuple[Any, ...] | None,
        fail_on_execution: int | None = None,
    ) -> None:
        self.select_row = select_row
        self.fail_on_execution = fail_on_execution
        self.executions: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        if self.fail_on_execution is not None and len(self.executions) >= self.fail_on_execution:
            raise RuntimeError("database write failed")
        self.executions.append((sql, params))

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.select_row

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(
        self,
        select_row: tuple[Any, ...] | None,
        fail_on_execution: int | None = None,
    ) -> None:
        self.cursor_instance = FakeCursor(select_row, fail_on_execution)
        self.committed = False
        self.rolled_back = False

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class ApproveReviewItemTests(unittest.TestCase):
    def test_approve_upserts_membership_and_resolves_item(self) -> None:
        connection = FakeConnection(OPEN_ITEM_ROW)

        result = approve_review_item(
            connection,
            "review-id",
            reviewer_notes="Looks like standard own-brand cornflakes.",
            resolved_at="2026-06-10T09:00:00Z",
        )

        executions = connection.cursor_instance.executions
        self.assertEqual(len(executions), 3)

        membership_sql, membership_params = executions[1]
        self.assertIn("INSERT INTO product_group_memberships", membership_sql)
        self.assertIn("ON CONFLICT (id) DO UPDATE", membership_sql)
        self.assertEqual(membership_params[1], "product-id")
        self.assertEqual(membership_params[2], "group-id")
        self.assertEqual(membership_params[3], Decimal("0.85"))
        self.assertTrue(membership_params[6])  # human_reviewed

        resolve_sql, resolve_params = executions[2]
        self.assertIn("SET status = 'resolved'", resolve_sql)
        self.assertEqual(
            resolve_params,
            (
                "approve_group_membership",
                "Looks like standard own-brand cornflakes.",
                "2026-06-10T09:00:00Z",
                "review-id",
            ),
        )

        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertTrue(connection.cursor_instance.closed)
        self.assertEqual(result.decision, "approve_group_membership")
        self.assertEqual(result.membership_id, membership_params[0])
        self.assertEqual(result.resolved_at, "2026-06-10T09:00:00Z")

    def test_approve_membership_id_matches_auto_match_path(self) -> None:
        connection = FakeConnection(OPEN_ITEM_ROW)

        first = approve_review_item(connection, "review-id", resolved_at="2026-06-10T09:00:00Z")
        second = approve_review_item(
            FakeConnection(OPEN_ITEM_ROW),
            "review-id",
            resolved_at="2026-06-11T09:00:00Z",
        )

        # Deterministic per product/group pair, so repeat approvals upsert.
        self.assertEqual(first.membership_id, second.membership_id)

    def test_approve_requires_linked_product(self) -> None:
        row = ("review-id", None, "group-id", Decimal("0.85"), None, "open")
        connection = FakeConnection(row)

        with self.assertRaises(ReviewDecisionError):
            approve_review_item(connection, "review-id")
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)


class RejectReviewItemTests(unittest.TestCase):
    def test_reject_deletes_membership_and_resolves_item(self) -> None:
        connection = FakeConnection(OPEN_ITEM_ROW)

        result = reject_review_item(
            connection,
            "review-id",
            reviewer_notes="Premium tier, not comparable.",
            resolved_at="2026-06-10T09:00:00Z",
        )

        executions = connection.cursor_instance.executions
        self.assertEqual(len(executions), 3)

        delete_sql, delete_params = executions[1]
        self.assertIn("DELETE FROM product_group_memberships", delete_sql)
        self.assertEqual(delete_params, ("product-id", "group-id"))

        _, resolve_params = executions[2]
        self.assertEqual(resolve_params[0], "reject_group_membership")
        self.assertTrue(connection.committed)
        self.assertIsNone(result.membership_id)

    def test_reject_without_product_skips_membership_delete(self) -> None:
        row = ("review-id", None, "group-id", Decimal("0.85"), None, "open")
        connection = FakeConnection(row)

        result = reject_review_item(connection, "review-id", resolved_at="2026-06-10T09:00:00Z")

        executions = connection.cursor_instance.executions
        self.assertEqual(len(executions), 2)
        self.assertIn("SET status = 'resolved'", executions[1][0])
        self.assertTrue(connection.committed)
        self.assertIsNone(result.product_id)


class ReviewDecisionGuardTests(unittest.TestCase):
    def test_missing_item_raises_and_rolls_back(self) -> None:
        connection = FakeConnection(None)

        with self.assertRaises(ReviewDecisionError):
            approve_review_item(connection, "missing-id")
        self.assertTrue(connection.rolled_back)

    def test_already_resolved_item_is_rejected(self) -> None:
        row = ("review-id", "product-id", "group-id", Decimal("0.85"), None, "resolved")
        connection = FakeConnection(row)

        with self.assertRaises(ReviewDecisionError):
            reject_review_item(connection, "review-id")
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)

    def test_write_failure_rolls_back(self) -> None:
        connection = FakeConnection(OPEN_ITEM_ROW, fail_on_execution=2)

        with self.assertRaises(RuntimeError):
            approve_review_item(connection, "review-id")
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)
        self.assertTrue(connection.cursor_instance.closed)

    def test_generated_resolved_at_is_utc_iso(self) -> None:
        connection = FakeConnection(OPEN_ITEM_ROW)

        result = approve_review_item(connection, "review-id")

        self.assertRegex(result.resolved_at, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


if __name__ == "__main__":
    unittest.main()
