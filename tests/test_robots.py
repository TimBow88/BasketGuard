from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))

from basketguard_ingestion import (  # noqa: E402
    FetchHttpStatusError,
    FetchResponse,
    FetchTimeoutError,
    FetchUrlError,
    RobotsPolicy,
)

ROBOTS_BODY = "User-agent: *\nDisallow: /secret\n"
HOST = "https://shop.example"


class _RobotsFetcher:
    """SupplierFetcher stand-in that serves a canned robots.txt or raises."""

    def __init__(self, *, body: str | None = ROBOTS_BODY, error: Exception | None = None) -> None:
        self._body = body
        self._error = error
        self.calls: list[str] = []

    def fetch(self, url: str, *, timeout_seconds: int, user_agent: str) -> FetchResponse:
        self.calls.append(url)
        if self._error is not None:
            raise self._error
        return FetchResponse(url=url, status_code=200, body=self._body or "", headers={})


class RobotsPolicyTests(unittest.TestCase):
    def test_allows_path_not_disallowed(self) -> None:
        policy = RobotsPolicy(_RobotsFetcher())
        decision = policy.is_allowed(f"{HOST}/groceries/123", "BasketGuardResearchBot/0.1")
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "allowed")

    def test_disallows_blocked_path(self) -> None:
        policy = RobotsPolicy(_RobotsFetcher())
        decision = policy.is_allowed(f"{HOST}/secret/page", "BasketGuardResearchBot/0.1")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "disallowed")

    def test_missing_robots_404_allows_all(self) -> None:
        fetcher = _RobotsFetcher(error=FetchHttpStatusError(404, "Not Found", body="nope"))
        policy = RobotsPolicy(fetcher)
        decision = policy.is_allowed(f"{HOST}/secret/page", "agent")
        self.assertTrue(decision.allowed)

    def test_forbidden_robots_403_disallows_all(self) -> None:
        fetcher = _RobotsFetcher(error=FetchHttpStatusError(403, "Forbidden", body="no"))
        policy = RobotsPolicy(fetcher)
        decision = policy.is_allowed(f"{HOST}/anything", "agent")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "disallowed")

    def test_server_error_is_unavailable(self) -> None:
        fetcher = _RobotsFetcher(error=FetchHttpStatusError(503, "Service Unavailable"))
        policy = RobotsPolicy(fetcher)
        decision = policy.is_allowed(f"{HOST}/anything", "agent")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "unavailable")

    def test_network_error_is_unavailable(self) -> None:
        for error in (FetchTimeoutError("timed out"), FetchUrlError("dns failure")):
            with self.subTest(error=error.__class__.__name__):
                policy = RobotsPolicy(_RobotsFetcher(error=error))
                decision = policy.is_allowed(f"{HOST}/anything", "agent")
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason, "unavailable")

    def test_robots_fetched_once_per_host(self) -> None:
        fetcher = _RobotsFetcher()
        policy = RobotsPolicy(fetcher)
        policy.is_allowed(f"{HOST}/groceries/1", "agent")
        policy.is_allowed(f"{HOST}/groceries/2", "agent")
        policy.is_allowed(f"{HOST}/secret/3", "agent")
        self.assertEqual(fetcher.calls, [f"{HOST}/robots.txt"])

    def test_invalid_url_is_unavailable(self) -> None:
        policy = RobotsPolicy(_RobotsFetcher())
        decision = policy.is_allowed("not-a-url", "agent")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "unavailable")


if __name__ == "__main__":
    unittest.main()
