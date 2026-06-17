from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))

from basketguard_ingestion import (  # noqa: E402
    FetchHttpStatusError,
    FetchResponse,
    FetchTimeoutError,
    FetchUrlError,
    PolitenessPolicy,
    RetryingFetcher,
    detect_block_signal,
)


class ScriptedFetcher:
    """A SupplierFetcher double that replays a scripted sequence of outcomes."""

    def __init__(self, outcomes: list) -> None:
        self._outcomes = list(outcomes)
        self.calls = 0

    def fetch(self, url: str, *, timeout_seconds: int, user_agent: str) -> FetchResponse:
        self.calls += 1
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


class DetectBlockSignalTests(unittest.TestCase):
    def test_status_403_and_429_are_blocks(self) -> None:
        self.assertEqual(detect_block_signal("<html>ok</html>", 403), "http_403")
        self.assertEqual(detect_block_signal(None, 429), "http_429")

    def test_body_signature_detected(self) -> None:
        self.assertEqual(
            detect_block_signal("<html>Please complete the CAPTCHA</html>", 200),
            "captcha",
        )

    def test_genuine_page_is_not_a_block(self) -> None:
        self.assertIsNone(detect_block_signal("<html>Cornflakes 75p</html>", 200))


class PolitenessPolicyTests(unittest.TestCase):
    def test_first_request_does_not_wait(self) -> None:
        clock = FakeClock()
        policy = PolitenessPolicy(min_interval_seconds=2.0, clock=clock.monotonic, sleep=clock.sleep)

        self.assertEqual(policy.wait("tesco.com"), 0.0)
        self.assertEqual(clock.slept, [])

    def test_second_immediate_request_waits_remaining_interval(self) -> None:
        clock = FakeClock()
        policy = PolitenessPolicy(min_interval_seconds=2.0, clock=clock.monotonic, sleep=clock.sleep)

        policy.wait("tesco.com")
        slept = policy.wait("tesco.com")

        self.assertEqual(slept, 2.0)
        self.assertEqual(clock.slept, [2.0])

    def test_separate_hosts_are_throttled_independently(self) -> None:
        clock = FakeClock()
        policy = PolitenessPolicy(min_interval_seconds=2.0, clock=clock.monotonic, sleep=clock.sleep)

        policy.wait("tesco.com")
        self.assertEqual(policy.wait("asda.com"), 0.0)


class RetryingFetcherTests(unittest.TestCase):
    def _fetch(self, fetcher: RetryingFetcher) -> FetchResponse:
        return fetcher.fetch(
            "https://www.tesco.com/groceries/en-GB/products/254879001",
            timeout_seconds=15,
            user_agent="BasketGuardResearchBot/0.1",
        )

    def test_returns_first_success_without_sleeping(self) -> None:
        clock = FakeClock()
        inner = ScriptedFetcher([FetchResponse("u", 200, "<html>ok</html>")])
        fetcher = RetryingFetcher(inner, sleep=clock.sleep)

        response = self._fetch(fetcher)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(inner.calls, 1)
        self.assertEqual(clock.slept, [])

    def test_retries_timeout_then_succeeds_with_backoff(self) -> None:
        clock = FakeClock()
        inner = ScriptedFetcher(
            [FetchTimeoutError("slow"), FetchResponse("u", 200, "<html>ok</html>")]
        )
        fetcher = RetryingFetcher(inner, backoff_seconds=2.0, backoff_factor=2.0, sleep=clock.sleep)

        response = self._fetch(fetcher)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(inner.calls, 2)
        self.assertEqual(clock.slept, [2.0])

    def test_exhausts_retries_and_reraises(self) -> None:
        clock = FakeClock()
        inner = ScriptedFetcher(
            [FetchTimeoutError("1"), FetchTimeoutError("2"), FetchTimeoutError("3")]
        )
        fetcher = RetryingFetcher(inner, max_retries=2, sleep=clock.sleep)

        with self.assertRaises(FetchTimeoutError):
            self._fetch(fetcher)
        self.assertEqual(inner.calls, 3)
        self.assertEqual(clock.slept, [2.0, 4.0])

    def test_429_is_retryable_but_404_is_not(self) -> None:
        clock = FakeClock()
        inner = ScriptedFetcher(
            [FetchHttpStatusError(429, "Too Many Requests"), FetchResponse("u", 200, "ok")]
        )
        fetcher = RetryingFetcher(inner, sleep=clock.sleep)
        self.assertEqual(self._fetch(fetcher).status_code, 200)

        not_found = ScriptedFetcher([FetchHttpStatusError(404, "Not Found")])
        fetcher = RetryingFetcher(not_found, sleep=clock.sleep)
        with self.assertRaises(FetchHttpStatusError):
            self._fetch(fetcher)
        self.assertEqual(not_found.calls, 1)

    def test_applies_politeness_before_each_attempt(self) -> None:
        clock = FakeClock()
        policy = PolitenessPolicy(
            min_interval_seconds=1.0, clock=clock.monotonic, sleep=clock.sleep
        )
        inner = ScriptedFetcher(
            [FetchUrlError("reset"), FetchResponse("u", 200, "ok")]
        )
        fetcher = RetryingFetcher(inner, politeness=policy, backoff_seconds=0.0, sleep=clock.sleep)

        self._fetch(fetcher)

        # Two attempts → policy invoked twice; second attempt throttled.
        self.assertEqual(inner.calls, 2)
        self.assertIn(1.0, clock.slept)


if __name__ == "__main__":
    unittest.main()
