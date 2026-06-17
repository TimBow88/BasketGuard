from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping

from .fetcher import (
    FetchHttpStatusError,
    FetchResponse,
    FetchTimeoutError,
    FetchUrlError,
)


@dataclass(frozen=True)
class RenderedPage:
    """A page rendered by a headless browser.

    This is the renderer-facing contract. The fetcher translates it into the
    shared :class:`FetchResponse`/``FetchError`` taxonomy so a Playwright-backed
    fetcher is a drop-in replacement for ``UrllibSupplierFetcher``.
    """

    status_code: int
    body: str
    headers: Mapping[str, str] = field(default_factory=dict)
    url: str | None = None


class RenderTimeout(RuntimeError):
    """Raised by a renderer when navigation or rendering exceeds the timeout."""


class RenderError(RuntimeError):
    """Raised by a renderer for non-timeout render failures (launch, navigation)."""


# A renderer takes the same call shape as SupplierFetcher.fetch and returns a
# RenderedPage, raising RenderTimeout / RenderError on failure. Injecting it
# keeps the browser out of unit tests, mirroring the urllib `opener` seam.
PageRenderer = Callable[..., RenderedPage]


class PlaywrightSupplierFetcher:
    """``SupplierFetcher`` that renders pages in a headless browser.

    Useful when a retailer returns price/title only after client-side
    rendering, where the plain-HTTP ``UrllibSupplierFetcher`` would see an empty
    shell. It deliberately makes no attempt to evade bot protection: a 403/429
    surfaces as :class:`FetchHttpStatusError` (with the challenge body preserved
    for later block-signal analysis) and collection stops.
    """

    def __init__(
        self,
        renderer: PageRenderer | None = None,
        *,
        wait_until: str = "domcontentloaded",
    ) -> None:
        self._renderer = renderer or PlaywrightPageRenderer(wait_until=wait_until)

    def fetch(self, url: str, *, timeout_seconds: int, user_agent: str) -> FetchResponse:
        try:
            rendered = self._renderer(
                url,
                timeout_seconds=timeout_seconds,
                user_agent=user_agent,
            )
        except RenderTimeout as error:
            raise FetchTimeoutError(str(error) or "Render timed out") from error
        except RenderError as error:
            raise FetchUrlError(str(error) or "Render failed") from error

        if rendered.status_code >= 400:
            raise FetchHttpStatusError(
                rendered.status_code,
                "HTTP error",
                body=rendered.body,
            )

        return FetchResponse(
            url=rendered.url or url,
            status_code=rendered.status_code,
            body=rendered.body,
            headers=dict(rendered.headers),
        )


class PlaywrightPageRenderer:
    """Default renderer backed by Playwright's headless Chromium.

    Playwright is imported lazily so the ingestion package still imports when the
    browser stack is not installed; only constructing the default fetcher and
    calling it requires Playwright.
    """

    def __init__(
        self,
        *,
        wait_until: str = "domcontentloaded",
        launch_kwargs: Mapping[str, object] | None = None,
    ) -> None:
        self._wait_until = wait_until
        self._launch_kwargs = dict(launch_kwargs or {})

    def __call__(
        self,
        url: str,
        *,
        timeout_seconds: int,
        user_agent: str,
    ) -> RenderedPage:
        try:
            from playwright.sync_api import (
                Error as PlaywrightError,
                TimeoutError as PlaywrightTimeoutError,
                sync_playwright,
            )
        except ImportError as error:  # pragma: no cover - exercised only without playwright
            raise RenderError(
                "Playwright is not installed. Install it with "
                "'pip install playwright' and 'playwright install chromium'."
            ) from error

        timeout_ms = max(0, int(timeout_seconds * 1000))
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, **self._launch_kwargs)
                try:
                    context = browser.new_context(user_agent=user_agent)
                    page = context.new_page()
                    try:
                        response = page.goto(
                            url,
                            timeout=timeout_ms,
                            wait_until=self._wait_until,
                        )
                    except PlaywrightTimeoutError as error:
                        raise RenderTimeout(str(error) or "Render timed out") from error
                    if response is None:
                        raise RenderError(f"No response received for {url}")
                    return RenderedPage(
                        status_code=response.status,
                        body=page.content(),
                        headers=dict(response.headers),
                        url=response.url,
                    )
                finally:
                    browser.close()
        except (RenderTimeout, RenderError):
            raise
        except PlaywrightTimeoutError as error:
            raise RenderTimeout(str(error) or "Render timed out") from error
        except PlaywrightError as error:
            raise RenderError(str(error) or "Playwright render failed") from error
