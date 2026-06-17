from __future__ import annotations

import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))

from basketguard_ingestion import (  # noqa: E402
    FetchHttpStatusError,
    FetchResponse,
    FetchTimeoutError,
    FetchUrlError,
    PlaywrightSupplierFetcher,
    RenderedPage,
    RenderError,
    RenderTimeout,
)

PRODUCT_URL = "https://www.tesco.com/groceries/en-GB/products/254879001"


class PlaywrightSupplierFetcherTests(unittest.TestCase):
    def test_rendered_page_maps_to_fetch_response(self) -> None:
        def renderer(url, *, timeout_seconds, user_agent):
            self.assertEqual(url, PRODUCT_URL)
            self.assertEqual(timeout_seconds, 12)
            self.assertEqual(user_agent, "BasketGuardResearchBot/0.1")
            return RenderedPage(
                status_code=200,
                body="<html><body>rendered title and £1.50</body></html>",
                headers={"content-type": "text/html"},
                url=url,
            )

        response = PlaywrightSupplierFetcher(renderer=renderer).fetch(
            PRODUCT_URL,
            timeout_seconds=12,
            user_agent="BasketGuardResearchBot/0.1",
        )

        self.assertIsInstance(response, FetchResponse)
        self.assertEqual(response.status_code, 200)
        self.assertIn("rendered title", response.body)
        self.assertEqual(response.headers["content-type"], "text/html")
        self.assertEqual(response.url, PRODUCT_URL)

    def test_403_challenge_preserves_body_as_status_error(self) -> None:
        def renderer(url, *, timeout_seconds, user_agent):
            return RenderedPage(
                status_code=403,
                body="<html><body>Access denied</body></html>",
                headers={},
                url=url,
            )

        with self.assertRaises(FetchHttpStatusError) as context:
            PlaywrightSupplierFetcher(renderer=renderer).fetch(
                PRODUCT_URL,
                timeout_seconds=12,
                user_agent="BasketGuardResearchBot/0.1",
            )

        self.assertEqual(context.exception.error_code, "http_403")
        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(context.exception.body, "<html><body>Access denied</body></html>")

    def test_429_maps_to_status_error(self) -> None:
        def renderer(url, *, timeout_seconds, user_agent):
            return RenderedPage(status_code=429, body="slow down", url=url)

        with self.assertRaises(FetchHttpStatusError) as context:
            PlaywrightSupplierFetcher(renderer=renderer).fetch(
                PRODUCT_URL,
                timeout_seconds=12,
                user_agent="BasketGuardResearchBot/0.1",
            )

        self.assertEqual(context.exception.error_code, "http_429")
        self.assertEqual(context.exception.status_code, 429)

    def test_render_timeout_maps_to_fetch_timeout(self) -> None:
        def renderer(url, *, timeout_seconds, user_agent):
            raise RenderTimeout("navigation exceeded 12000ms")

        with self.assertRaises(FetchTimeoutError) as context:
            PlaywrightSupplierFetcher(renderer=renderer).fetch(
                PRODUCT_URL,
                timeout_seconds=12,
                user_agent="BasketGuardResearchBot/0.1",
            )

        self.assertEqual(context.exception.error_code, "timeout")
        self.assertIn("navigation exceeded", str(context.exception))

    def test_render_error_maps_to_url_error(self) -> None:
        def renderer(url, *, timeout_seconds, user_agent):
            raise RenderError("net::ERR_NAME_NOT_RESOLVED")

        with self.assertRaises(FetchUrlError) as context:
            PlaywrightSupplierFetcher(renderer=renderer).fetch(
                PRODUCT_URL,
                timeout_seconds=12,
                user_agent="BasketGuardResearchBot/0.1",
            )

        self.assertEqual(context.exception.error_code, "url_error")
        self.assertIn("ERR_NAME_NOT_RESOLVED", str(context.exception))

    def test_falls_back_to_request_url_when_renderer_omits_it(self) -> None:
        def renderer(url, *, timeout_seconds, user_agent):
            return RenderedPage(status_code=200, body="ok", url=None)

        response = PlaywrightSupplierFetcher(renderer=renderer).fetch(
            PRODUCT_URL,
            timeout_seconds=12,
            user_agent="BasketGuardResearchBot/0.1",
        )

        self.assertEqual(response.url, PRODUCT_URL)


class _CannedHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - http.server interface
        if self.path == "/missing":
            body = b"<html><body>not found</body></html>"
            self.send_response(404)
        else:
            body = (
                b"<html><head><title>Cornflakes</title></head>"
                b"<body><span data-testid='price'>"
                b"<script>document.write('rendered')</script>"
                b"&pound;1.50</span></body></html>"
            )
            self.send_response(200)
        self.send_header("content-type", "text/html")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args, **kwargs) -> None:  # silence test server logging
        return None


@unittest.skipUnless(
    os.environ.get("BASKETGUARD_RUN_PLAYWRIGHT_LIVE") == "1",
    "Set BASKETGUARD_RUN_PLAYWRIGHT_LIVE=1 to launch a real headless browser.",
)
class PlaywrightSupplierFetcherLiveTests(unittest.TestCase):
    """End-to-end checks that launch real headless Chromium against a local server.

    Skipped by default so the normal suite needs no browser. Run with:
        BASKETGUARD_RUN_PLAYWRIGHT_LIVE=1 python -m unittest tests.test_playwright_fetcher
    """

    def setUp(self) -> None:
        self.server = HTTPServer(("127.0.0.1", 0), _CannedHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def test_real_browser_returns_rendered_html(self) -> None:
        response = PlaywrightSupplierFetcher().fetch(
            f"{self.base_url}/product",
            timeout_seconds=15,
            user_agent="BasketGuardResearchBot/0.1",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Cornflakes", response.body)
        # The price span content is written by client-side script, so a rendered
        # fetch proves we capture post-JavaScript DOM, not just the raw shell.
        self.assertIn("rendered", response.body)

    def test_real_browser_surfaces_http_404(self) -> None:
        with self.assertRaises(FetchHttpStatusError) as context:
            PlaywrightSupplierFetcher().fetch(
                f"{self.base_url}/missing",
                timeout_seconds=15,
                user_agent="BasketGuardResearchBot/0.1",
            )

        self.assertEqual(context.exception.status_code, 404)
        self.assertIn("not found", context.exception.body or "")


if __name__ == "__main__":
    unittest.main()
