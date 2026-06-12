from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "analytics" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))
sys.path.insert(0, str(ROOT / "services" / "reporting" / "src"))
sys.path.insert(0, str(ROOT / "services" / "api" / "src"))

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - environments without the api extras
    TestClient = None  # type: ignore[assignment]
else:
    from basketguard_api import create_app


def _comparison_row(
    retailer: str,
    slug: str,
    title: str,
    unit_price: str,
) -> tuple[Any, ...]:
    return (
        retailer,
        slug,
        title,
        Decimal("500"),
        "g",
        Decimal("2.50"),
        Decimal("2.25"),
        Decimal(unit_price),
        "kg",
        "in_stock",
        "2026-06-11T08:00:00Z",
        f"snapshot-{slug}",
        Decimal("1.00"),
        False,
    )


def _review_row(item_id: str, group_slug: str) -> tuple[Any, ...]:
    return (
        item_id,
        "Tesco",
        "tesco",
        "Tesco Wheat Biscuits 24 Pack",
        "https://www.tesco.com/products/303030002",
        group_slug,
        Decimal("0.74"),
        "name_similarity_below_auto_match_threshold",
        "2026-06-11T08:00:00Z",
        "snapshot-tesco",
    )


class FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows
        self.executions: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.executions.append((sql, params))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.cursor_instance = FakeCursor(rows)
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def close(self) -> None:
        self.closed = True


@unittest.skipUnless(TestClient is not None, "fastapi is not installed")
class ApiTests(unittest.TestCase):
    def _client(self, rows: list[tuple[Any, ...]]) -> tuple[Any, list[FakeConnection]]:
        opened: list[FakeConnection] = []

        def factory() -> FakeConnection:
            connection = FakeConnection(rows)
            opened.append(connection)
            return connection

        return TestClient(create_app(factory)), opened

    def test_health_returns_ok_without_touching_the_database(self) -> None:
        client, opened = self._client([])

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(opened, [])

    def test_group_comparison_endpoint_serialises_report_and_closes_connection(self) -> None:
        client, opened = self._client(
            [
                _comparison_row("Tesco", "tesco", "Tesco Corn Flakes 500G", "5.00"),
                _comparison_row("Asda", "asda", "ASDA Corn Flakes 500g", "2.70"),
            ],
        )

        response = client.get("/reports/group-comparison/own_brand_cornflakes_standard")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["group_slug"], "own_brand_cornflakes_standard")
        self.assertEqual(len(payload["entries"]), 2)
        # Entries arrive cheapest-first with Decimals preserved as strings.
        self.assertEqual(payload["entries"][0]["retailer_slug"], "asda")
        self.assertEqual(payload["entries"][0]["unit_price"], "2.70")
        self.assertEqual(payload["entries"][0]["shelf_price"], "2.50")
        self.assertEqual(payload["entries"][0]["raw_snapshot_id"], "snapshot-asda")
        self.assertEqual(len(opened), 1)
        self.assertTrue(opened[0].closed)
        self.assertEqual(
            opened[0].cursor_instance.executions[0][1],
            ("own_brand_cornflakes_standard", Decimal("0.92")),
        )

    def test_group_history_endpoint_binds_window_days(self) -> None:
        client, opened = self._client([])

        response = client.get("/reports/group-history/own_brand_porridge_oats_standard?window_days=30")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["group_slug"], "own_brand_porridge_oats_standard")
        self.assertEqual(payload["window_days"], 30)
        self.assertEqual(payload["retailers"], [])
        self.assertEqual(
            opened[0].cursor_instance.executions[0][1],
            ("own_brand_porridge_oats_standard", Decimal("0.92"), 30),
        )

    def test_group_history_endpoint_rejects_non_positive_window(self) -> None:
        client, _ = self._client([])

        response = client.get("/reports/group-history/own_brand_porridge_oats_standard?window_days=0")

        self.assertEqual(response.status_code, 422)

    def test_retailer_gaps_endpoint_accepts_repeated_group_slugs(self) -> None:
        client, opened = self._client(
            [
                _comparison_row("Tesco", "tesco", "Tesco Corn Flakes 500G", "5.00"),
                _comparison_row("Asda", "asda", "ASDA Corn Flakes 500g", "2.70"),
            ],
        )

        response = client.get(
            "/reports/retailer-gaps"
            "?group_slug=own_brand_cornflakes_standard"
            "&group_slug=own_brand_porridge_oats_standard",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["gaps"]), 2)
        self.assertEqual(payload["gaps"][0]["group_slug"], "own_brand_cornflakes_standard")
        self.assertEqual(payload["gaps"][0]["cheapest_retailer_slug"], "asda")
        self.assertEqual(payload["gaps"][0]["absolute_unit_price_gap"], "2.30")
        self.assertTrue(opened[0].closed)

    def test_retailer_gaps_endpoint_requires_at_least_one_group_slug(self) -> None:
        client, _ = self._client([])

        response = client.get("/reports/retailer-gaps")

        self.assertEqual(response.status_code, 422)

    def test_review_required_endpoint_filters_by_group_slug(self) -> None:
        client, opened = self._client(
            [_review_row("review-1", "own_brand_wheat_biscuits_standard")],
        )

        response = client.get("/reports/review-required?group_slug=own_brand_wheat_biscuits_standard")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["group_slug_filter"], "own_brand_wheat_biscuits_standard")
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["review_item_id"], "review-1")
        self.assertEqual(payload["items"][0]["match_confidence"], "0.74")
        self.assertEqual(
            opened[0].cursor_instance.executions[0][1],
            ("own_brand_wheat_biscuits_standard",),
        )


if __name__ == "__main__":
    unittest.main()
