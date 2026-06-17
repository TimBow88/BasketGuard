from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))

from basketguard_ingestion import (  # noqa: E402
    DEFAULT_LIVE_HEADERS,
    FetchResponse,
    ProxyEndpoint,
    ProxyPool,
    RetryingFetcher,
    RenderRequest,
    RenderResult,
    UrllibSupplierFetcher,
    build_live_fetcher,
)
from basketguard_ingestion.headless_fetcher import PlaywrightSupplierFetcher  # noqa: E402


@dataclass
class FakeSettings:
    fetcher_mode: str = "headless"
    proxy_url: str | None = None
    request_delay_seconds: float = 1.0
    max_retries: int = 2
    retry_backoff_seconds: float = 2.0


class RecordingRenderer:
    def __init__(self) -> None:
        self.requests: list[RenderRequest] = []

    def render(self, request: RenderRequest) -> RenderResult:
        self.requests.append(request)
        return RenderResult(200, "<html>ok</html>")


class NoSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


class BuildLiveFetcherTests(unittest.TestCase):
    def test_headless_mode_composes_retrying_over_playwright(self) -> None:
        renderer = RecordingRenderer()
        fetcher = build_live_fetcher(
            FakeSettings(fetcher_mode="headless"),
            renderer=renderer,
            sleep=NoSleep(),
            clock=lambda: 0.0,
        )

        self.assertIsInstance(fetcher, RetryingFetcher)
        self.assertIsInstance(fetcher.inner, PlaywrightSupplierFetcher)

        response = fetcher.fetch(
            "https://www.tesco.com/groceries/en-GB/products/254879001",
            timeout_seconds=20,
            user_agent="BasketGuardResearchBot/0.1",
        )
        self.assertEqual(response.status_code, 200)
        # Honest locale headers are forwarded; nothing is spoofed.
        self.assertEqual(renderer.requests[0].extra_headers, DEFAULT_LIVE_HEADERS)
        self.assertEqual(renderer.requests[0].wait_until, "networkidle")

    def test_urllib_mode_uses_plain_fetcher(self) -> None:
        fetcher = build_live_fetcher(FakeSettings(fetcher_mode="urllib"))
        self.assertIsInstance(fetcher, RetryingFetcher)
        self.assertIsInstance(fetcher.inner, UrllibSupplierFetcher)

    def test_proxy_pool_supplies_egress_proxy(self) -> None:
        renderer = RecordingRenderer()
        pool = ProxyPool(endpoints=[ProxyEndpoint(server="http://uk-1:8080", country="GB")])

        fetcher = build_live_fetcher(
            FakeSettings(),
            proxy_pool=pool,
            renderer=renderer,
            sleep=NoSleep(),
            clock=lambda: 0.0,
        )
        fetcher.fetch("https://t/1", timeout_seconds=10, user_agent="ua")

        self.assertEqual(renderer.requests[0].proxy, {"server": "http://uk-1:8080"})

    def test_settings_proxy_url_used_when_no_pool(self) -> None:
        renderer = RecordingRenderer()
        fetcher = build_live_fetcher(
            FakeSettings(proxy_url="http://proxy:3128"),
            renderer=renderer,
            sleep=NoSleep(),
            clock=lambda: 0.0,
        )
        fetcher.fetch("https://t/1", timeout_seconds=10, user_agent="ua")

        self.assertEqual(renderer.requests[0].proxy, {"server": "http://proxy:3128"})

    def test_retry_config_flows_from_settings(self) -> None:
        fetcher = build_live_fetcher(
            FakeSettings(max_retries=5, retry_backoff_seconds=3.0),
            renderer=RecordingRenderer(),
            sleep=NoSleep(),
            clock=lambda: 0.0,
        )
        self.assertEqual(fetcher.max_retries, 5)
        self.assertEqual(fetcher.backoff_seconds, 3.0)


if __name__ == "__main__":
    unittest.main()
