from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db" / "migrations" / "0004_review_state_and_parsed_attributes.sql"


class Migration0004StructureTests(unittest.TestCase):
    """Structural checks on migration 0004.

    There is no live database in the default suite (the Postgres integration
    test is gated), so this mirrors the migration-text assertions used for
    ``0002`` in ``test_web_ui`` and guards the schema contract the mapping and
    repository layers will build on.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_migration_file_exists(self) -> None:
        self.assertTrue(MIGRATION.exists(), MIGRATION)

    def test_runs_in_a_single_transaction(self) -> None:
        self.assertIn("BEGIN;", self.sql)
        self.assertRegex(self.sql, r"COMMIT;\s*$")
        # Every DDL statement must sit inside the BEGIN/COMMIT block.
        self.assertLess(self.sql.index("BEGIN;"), self.sql.index("ALTER TABLE"))
        self.assertLess(self.sql.index("BEGIN;"), self.sql.index("CREATE TABLE"))
        self.assertLess(self.sql.index("CREATE TABLE"), self.sql.rindex("COMMIT;"))

    def test_creates_new_tables(self) -> None:
        for table in ("review_queue_events", "parsed_product_attributes"):
            self.assertRegex(self.sql, rf"CREATE TABLE {table}\b")

    def test_adds_richer_review_state_columns(self) -> None:
        for column in (
            "reviewer",
            "reviewed_at",
            "parser_version",
            "group_definition_version",
        ):
            self.assertRegex(self.sql, rf"ADD COLUMN {column}\b")

    def test_introduces_in_review_state_without_breaking_existing_states(self) -> None:
        # The status check must still accept the original two states plus the
        # new claimed state, so existing 'open'/'resolved' rows stay valid.
        self.assertRegex(
            self.sql,
            r"review_queue_items_status_known\s+CHECK \(status IN "
            r"\('open', 'in_review', 'resolved'\)\)",
        )

    def test_resolution_consistency_allows_in_review(self) -> None:
        # in_review is unresolved, so it must carry no decision or resolved_at,
        # exactly like open.
        self.assertIn(
            "status IN ('open', 'in_review') AND decision IS NULL AND resolved_at IS NULL",
            self.sql,
        )

    def test_parsed_attributes_are_versioned_per_snapshot(self) -> None:
        self.assertRegex(self.sql, r"UNIQUE \(raw_snapshot_id, parser_version\)")
        self.assertRegex(
            self.sql,
            r"parsed_product_attributes_parser_version_not_blank",
        )

    def test_parsed_attributes_reference_existing_tables(self) -> None:
        self.assertRegex(
            self.sql, r"raw_snapshot_id UUID NOT NULL REFERENCES raw_product_snapshots\(id\)"
        )
        self.assertRegex(self.sql, r"product_id UUID REFERENCES products\(id\)")

    def test_audit_events_reference_review_items(self) -> None:
        self.assertRegex(
            self.sql,
            r"review_queue_item_id UUID NOT NULL REFERENCES review_queue_items\(id\)",
        )

    def test_audit_events_cover_richer_state_vocabulary(self) -> None:
        for state in (
            "in_review",
            "approved",
            "rejected",
            "closed",
            "needs_parser_fix",
            "needs_new_group",
        ):
            self.assertIn(f"'{state}'", self.sql)

    def test_non_negative_numeric_guards_present(self) -> None:
        for constraint in (
            "parsed_product_attributes_pack_size_non_negative",
            "parsed_product_attributes_unit_price_non_negative",
            "parsed_product_attributes_parse_confidence_range",
        ):
            self.assertIn(constraint, self.sql)

    def test_indexes_created_for_lookups(self) -> None:
        for index in (
            "idx_review_queue_events_item",
            "idx_parsed_product_attributes_snapshot",
            "idx_parsed_product_attributes_product",
        ):
            self.assertRegex(self.sql, rf"CREATE INDEX {index}\b")


if __name__ == "__main__":
    unittest.main()
