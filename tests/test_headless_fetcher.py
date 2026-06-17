from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))

from basketguard_ingestion import (  # noqa: E402
    FetchHttpStatusError,
    FetchRenderError,
    FetchResponse,
    FetchTimeoutError,
    PlaywrightPageRenderer,
    PlaywrightSupplierFetcher,
    RenderRequest,
    RenderResult,
    SupplierFetcher,
    TescoScraperConfig,
)


RENDERED_PRODUCT_FIXTURE = (
    ROOT / "services" / "ingestion" / "fixtures" / "tesco_clubcard_cornflakes.html"
)


class RecordingRenderer:
    """A ``PageRenderer`` double that records the request and replays a script."""

    def __init__(self, *, result: RenderResult | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.requests: list[RenderRequest] = []

    def render(self, request: RenderRequest) -> RenderResult:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


class PlaywrightSupplierFetcherTests(unittest.TestCase):
    def test_conforms_to_supplier_fetcher_protocol(self) -> None:
        fetcher: SupplierFetcher = PlaywrightSupplierFetcher(
            RecordingRenderer(result=RenderResult(200, "<html></html>"))
        )
        self.assertTrue(callable(fetcher.fetch))

    def test_fetch_returns_rendered_html_and_status(self) -> None:
        html = RENDERED_PRODUCT_FIXTURE.read_text(encoding="utf-8")
        renderer = RecordingRenderer(
            result=RenderResult(200, html, headers={"content-type": "text/html"})
        )

        response = PlaywrightSupplierFetcher(renderer).fetch(
            "https://www.tesco.com/groceries/en-GB/products/254879001",
            timeout_seconds=20,
            user_agent="BasketGuardResearchBot/0.1",
        )

        self.assertIsInstance(response, FetchResponse)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, html)
        self.assertEqual(response.headers["content-type"], "text/html")

    def test_fetch_forwards_request_shaping_to_renderer(self) -> None:
        renderer = RecordingRenderer(result=RenderResult(200, "<html></html>"))
        fetcher = PlaywrightSupplierFetcher(
            renderer,
            wait_until="load",
            wait_for_selector="[data-testid='price']",
            proxy={"server": "http://uk-proxy:8080"},
            extra_headers={"Accept-Language": "en-GB"},
        )

        fetcher.fetch(
            "https://www.tesco.com/groceries/en-GB/products/254879001",
            timeout_seconds=12,
            user_agent="BasketGuardResearchBot/0.1",
        )

        (request,) = renderer.requests
        self.assertEqual(request.timeout_seconds, 12)
        self.assertEqual(request.user_agent, "BasketGuardResearchBot/0.1")
        self.assertEqual(request.wait_until, "load")
        self.assertEqual(request.wait_for_selector, "[data-testid='price']")
        self.assertEqual(request.proxy, {"server": "http://uk-proxy:8080"})
        self.assertEqual(request.extra_headers, {"Accept-Language": "en-GB"})

    def test_challenge_page_status_maps_to_http_status_error(self) -> None:
        renderer = RecordingRenderer(
            result=RenderResult(403, "<html>Access denied</html>")
        )

        with self.assertRaises(FetchHttpStatusError) as context:
            PlaywrightSupplierFetcher(renderer).fetch(
                "https://www.tesco.com/groceries/en-GB/products/254879001",
                timeout_seconds=20,
                user_agent="BasketGuardResearchBot/0.1",
            )

        self.assertEqual(context.exception.error_code, "http_403")
        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(context.exception.body, "<html>Access denied</html>")

    def test_builtin_timeout_maps_to_fetch_timeout_error(self) -> None:
        renderer = RecordingRenderer(error=TimeoutError("navigation exceeded 20000ms"))

        with self.assertRaises(FetchTimeoutError) as context:
            PlaywrightSupplierFetcher(renderer).fetch(
                "https://www.tesco.com/groceries/en-GB/products/254879001",
                timeout_seconds=20,
                user_agent="BasketGuardResearchBot/0.1",
            )

        self.assertEqual(context.exception.error_code, "timeout")
        self.assertIn("20000ms", str(context.exception))

    def test_render_failure_maps_to_fetch_render_error(self) -> None:
        renderer = RecordingRenderer(error=RuntimeError("browser crashed"))

        with self.assertRaises(FetchRenderError) as context:
            PlaywrightSupplierFetcher(renderer).fetch(
                "https://www.tesco.com/groceries/en-GB/products/254879001",
                timeout_seconds=20,
                user_agent="BasketGuardResearchBot/0.1",
            )

        self.assertEqual(context.exception.error_code, "render_error")
        self.assertIn("browser crashed", str(context.exception))

    def test_existing_fetch_error_passes_through_unwrapped(self) -> None:
        original = FetchRenderError("Playwright is not installed.")
        renderer = RecordingRenderer(error=original)

        with self.assertRaises(FetchRenderError) as context:
            PlaywrightSupplierFetcher(renderer).fetch(
                "https://www.tesco.com/groceries/en-GB/products/254879001",
                timeout_seconds=20,
                user_agent="BasketGuardResearchBot/0.1",
            )

        self.assertIs(context.exception, original)

    def test_pluggable_into_scraper_config_in_place_of_urllib(self) -> None:
        fetcher = PlaywrightSupplierFetcher(
            RecordingRenderer(result=RenderResult(200, "<html></html>"))
        )
        config = TescoScraperConfig(allowlisted_urls=(), fetcher=fetcher)
        self.assertIs(config.fetcher, fetcher)


# --- Fakes mirroring the slice of Playwright's sync API the renderer drives. ---


class _FakePlaywrightTimeoutError(Exception):
    """Stand-in named exactly like ``playwright.sync_api.TimeoutError``."""


_FakePlaywrightTimeoutError.__name__ = "TimeoutError"


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status
        self.headers = {"content-type": "text/html"}


class _FakePage:
    def __init__(self, *, html: str, status: int, raise_on_goto: Exception | None = None) -> None:
        self._html = html
        self._status = status
        self._raise_on_goto = raise_on_goto
        self.goto_calls: list[dict] = []
        self.selector_waits: list[str] = []

    def goto(self, url, *, wait_until, timeout):
        self.goto_calls.append({"url": url, "wait_until": wait_until, "timeout": timeout})
        if self._raise_on_goto is not None:
            raise self._raise_on_goto
        return _FakeResponse(self._status)

    def wait_for_selector(self, selector, *, timeout):
        self.selector_waits.append(selector)

    def content(self) -> str:
        return self._html


class _FakeContext:
    def __init__(self, page: _FakePage) -> None:
        self._page = page
        self.user_agent = None
        self.proxy = None
        self.extra_http_headers = None

    def new_page(self) -> _FakePage:
        return self._page


class _FakeBrowser:
    def __init__(self, page: _FakePage) -> None:
        self._page = page
        self.closed = False
        self.new_context_kwargs: dict | None = None

    def new_context(self, **kwargs) -> _FakeContext:
        self.new_context_kwargs = kwargs
        return _FakeContext(self._page)

    def close(self) -> None:
        self.closed = True


class _FakeChromium:
    def __init__(self, browser: _FakeBrowser) -> None:
        self._browser = browser
        self.launch_kwargs: dict | None = None

    def launch(self, **kwargs) -> _FakeBrowser:
        self.launch_kwargs = kwargs
        return self._browser


class _FakePlaywright:
    def __init__(self, browser: _FakeBrowser) -> None:
        self.chromium = _FakeChromium(browser)


class _FakeSyncPlaywright:
    """Mimics the ``sync_playwright()`` context manager."""

    def __init__(self, playwright: _FakePlaywright) -> None:
        self._playwright = playwright

    def __call__(self) -> "_FakeSyncPlaywright":
        return self

    def __enter__(self) -> _FakePlaywright:
        return self._playwright

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


class PlaywrightPageRendererTests(unittest.TestCase):
    def _renderer_for(self, page: _FakePage) -> tuple[PlaywrightPageRenderer, _FakeBrowser]:
        browser = _FakeBrowser(page)
        factory = _FakeSyncPlaywright(_FakePlaywright(browser))
        renderer = PlaywrightPageRenderer(playwright_factory=factory)
        return renderer, browser

    def test_render_drives_browser_and_returns_result(self) -> None:
        page = _FakePage(html="<html>rendered</html>", status=200)
        renderer, browser = self._renderer_for(page)

        result = renderer.render(
            RenderRequest(
                url="https://www.tesco.com/groceries/en-GB/products/254879001",
                timeout_seconds=15,
                user_agent="BasketGuardResearchBot/0.1",
                wait_for_selector="[data-testid='price']",
                extra_headers={"Accept-Language": "en-GB"},
            )
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.body, "<html>rendered</html>")
        self.assertEqual(page.goto_calls[0]["timeout"], 15000)
        self.assertEqual(page.selector_waits, ["[data-testid='price']"])
        self.assertEqual(browser.new_context_kwargs["user_agent"], "BasketGuardResearchBot/0.1")
        self.assertEqual(browser.new_context_kwargs["extra_http_headers"], {"Accept-Language": "en-GB"})
        self.assertTrue(browser.closed)

    def test_render_translates_playwright_timeout(self) -> None:
        page = _FakePage(
            html="",
            status=200,
            raise_on_goto=_FakePlaywrightTimeoutError("Timeout 15000ms exceeded"),
        )
        renderer, browser = self._renderer_for(page)

        with self.assertRaises(FetchTimeoutError):
            renderer.render(
                RenderRequest(
                    url="https://www.tesco.com/groceries/en-GB/products/254879001",
                    timeout_seconds=15,
                    user_agent="BasketGuardResearchBot/0.1",
                )
            )
        self.assertTrue(browser.closed)

    def test_render_translates_other_failure_to_render_error(self) -> None:
        page = _FakePage(html="", status=200, raise_on_goto=RuntimeError("net::ERR_FAILED"))
        renderer, browser = self._renderer_for(page)

        with self.assertRaises(FetchRenderError):
            renderer.render(
                RenderRequest(
                    url="https://www.tesco.com/groceries/en-GB/products/254879001",
                    timeout_seconds=15,
                    user_agent="BasketGuardResearchBot/0.1",
                )
            )
        self.assertTrue(browser.closed)

    def test_missing_playwright_raises_actionable_render_error(self) -> None:
        # The default factory imports Playwright lazily; when it is not installed
        # rendering surfaces a clear, actionable FetchRenderError rather than a
        # bare ImportError.
        try:
            import playwright.sync_api  # noqa: F401
        except ImportError:
            pass
        else:
            self.skipTest("Playwright is installed in this environment")
        renderer = PlaywrightPageRenderer()
        with self.assertRaises(FetchRenderError) as context:
            renderer.render(
                RenderRequest(
                    url="https://www.tesco.com/groceries/en-GB/products/254879001",
                    timeout_seconds=15,
                    user_agent="BasketGuardResearchBot/0.1",
                )
            )
        self.assertIn("Playwright is not installed", str(context.exception))


if __name__ == "__main__":
    unittest.main()
