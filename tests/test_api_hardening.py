from __future__ import annotations

import sys
import unittest
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
    from basketguard_api.hardening import RateLimiter, validate_group_slug


class FakeCursor:
    def __init__(self) -> None:
        self.closed = False

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        return None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return []

    def fetchone(self) -> tuple[Any, ...] | None:
        return None

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None


@unittest.skipUnless(TestClient is not None, "fastapi is not installed")
class RateLimiterUnitTests(unittest.TestCase):
    def test_allows_up_to_limit_then_blocks(self) -> None:
        now = [0.0]
        limiter = RateLimiter(limit=2, window_seconds=60, clock=lambda: now[0])

        self.assertTrue(limiter.check("ip"))
        self.assertTrue(limiter.check("ip"))
        self.assertFalse(limiter.check("ip"))

    def test_window_rollover_resets_count(self) -> None:
        now = [0.0]
        limiter = RateLimiter(limit=1, window_seconds=60, clock=lambda: now[0])

        self.assertTrue(limiter.check("ip"))
        self.assertFalse(limiter.check("ip"))
        now[0] = 61.0
        self.assertTrue(limiter.check("ip"))

    def test_separate_clients_have_separate_budgets(self) -> None:
        limiter = RateLimiter(limit=1, window_seconds=60, clock=lambda: 0.0)
        self.assertTrue(limiter.check("a"))
        self.assertTrue(limiter.check("b"))


@unittest.skipUnless(TestClient is not None, "fastapi is not installed")
class SlugValidationUnitTests(unittest.TestCase):
    def test_accepts_well_formed_slug(self) -> None:
        self.assertEqual(
            validate_group_slug("own_brand_cornflakes_standard"),
            "own_brand_cornflakes_standard",
        )

    def test_rejects_bad_characters(self) -> None:
        from fastapi import HTTPException

        for bad in ("Bad Slug", "drop;table", "../etc", "x" * 101, ""):
            with self.assertRaises(HTTPException):
                validate_group_slug(bad)


@unittest.skipUnless(TestClient is not None, "fastapi is not installed")
class HardeningIntegrationTests(unittest.TestCase):
    def _client(self, **kwargs) -> Any:
        return TestClient(create_app(lambda: FakeConnection(), **kwargs))

    def test_security_headers_present_on_responses(self) -> None:
        response = self._client().get("/health")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")

    def test_malformed_slug_rejected_with_422(self) -> None:
        response = self._client().get("/reports/group-comparison/Not%20A%20Slug")
        self.assertEqual(response.status_code, 422)

    def test_rate_limit_returns_429_after_budget(self) -> None:
        client = self._client(rate_limit=2, rate_window_seconds=60, clock=lambda: 0.0)

        self.assertEqual(client.get("/reports/review-required").status_code, 200)
        self.assertEqual(client.get("/reports/review-required").status_code, 200)
        blocked = client.get("/reports/review-required")
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json()["detail"], "Rate limit exceeded")

    def test_health_is_exempt_from_rate_limit(self) -> None:
        client = self._client(rate_limit=1, rate_window_seconds=60, clock=lambda: 0.0)
        for _ in range(5):
            self.assertEqual(client.get("/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()
