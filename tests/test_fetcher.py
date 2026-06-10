from __future__ import annotations

import socket
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))

from basketguard_ingestion import (  # noqa: E402
    FetchHttpStatusError,
    FetchResponse,
    FetchTimeoutError,
    FetchUrlError,
    UrllibSupplierFetcher,
)


class FakeResponse:
    def __init__(self, body: str, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.headers = {"content-type": "text/html"}

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self.body.encode("utf-8")

    def close(self) -> None:
        return None


class UrllibSupplierFetcherTests(unittest.TestCase):
    def test_fetch_success_returns_status_headers_and_body(self) -> None:
        def opener(request, *, timeout: int) -> FakeResponse:
            self.assertEqual(timeout, 7)
            self.assertEqual(request.headers["User-agent"], "BasketGuardTest/1.0")
            return FakeResponse("<html>ok</html>", status=200)

        response = UrllibSupplierFetcher(opener=opener).fetch(
            "https://www.tesco.com/groceries/en-GB/products/254879001",
            timeout_seconds=7,
            user_agent="BasketGuardTest/1.0",
        )

        self.assertIsInstance(response, FetchResponse)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, "<html>ok</html>")
        self.assertEqual(response.headers["content-type"], "text/html")

    def test_fetch_timeout_raises_structured_error(self) -> None:
        def opener(request, *, timeout: int) -> FakeResponse:
            raise TimeoutError("timed out")

        with self.assertRaises(FetchTimeoutError) as context:
            UrllibSupplierFetcher(opener=opener).fetch(
                "https://www.tesco.com/groceries/en-GB/products/254879001",
                timeout_seconds=7,
                user_agent="BasketGuardTest/1.0",
            )

        self.assertEqual(context.exception.error_code, "timeout")
        self.assertIn("timed out", str(context.exception))

    def test_fetch_url_error_timeout_reason_raises_timeout(self) -> None:
        def opener(request, *, timeout: int) -> FakeResponse:
            raise URLError(socket.timeout("socket timed out"))

        with self.assertRaises(FetchTimeoutError):
            UrllibSupplierFetcher(opener=opener).fetch(
                "https://www.tesco.com/groceries/en-GB/products/254879001",
                timeout_seconds=7,
                user_agent="BasketGuardTest/1.0",
            )

    def test_fetch_404_raises_status_error_with_response_body(self) -> None:
        def opener(request, *, timeout: int) -> FakeResponse:
            raise HTTPError(
                request.full_url,
                404,
                "Not Found",
                hdrs={},
                fp=FakeResponse("<html>missing</html>", status=404),
            )

        with self.assertRaises(FetchHttpStatusError) as context:
            UrllibSupplierFetcher(opener=opener).fetch(
                "https://www.tesco.com/groceries/en-GB/products/000000000",
                timeout_seconds=7,
                user_agent="BasketGuardTest/1.0",
            )

        self.assertEqual(context.exception.error_code, "http_404")
        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.body, "<html>missing</html>")

    def test_fetch_429_raises_status_error(self) -> None:
        def opener(request, *, timeout: int) -> FakeResponse:
            raise HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                hdrs={},
                fp=FakeResponse("slow down", status=429),
            )

        with self.assertRaises(FetchHttpStatusError) as context:
            UrllibSupplierFetcher(opener=opener).fetch(
                "https://www.tesco.com/groceries/en-GB/products/254879001",
                timeout_seconds=7,
                user_agent="BasketGuardTest/1.0",
            )

        self.assertEqual(context.exception.error_code, "http_429")
        self.assertEqual(context.exception.status_code, 429)

    def test_fetch_network_failure_raises_url_error(self) -> None:
        def opener(request, *, timeout: int) -> FakeResponse:
            raise URLError("connection refused")

        with self.assertRaises(FetchUrlError) as context:
            UrllibSupplierFetcher(opener=opener).fetch(
                "https://www.tesco.com/groceries/en-GB/products/254879001",
                timeout_seconds=7,
                user_agent="BasketGuardTest/1.0",
            )

        self.assertEqual(context.exception.error_code, "url_error")
        self.assertIn("connection refused", str(context.exception))


if __name__ == "__main__":
    unittest.main()
