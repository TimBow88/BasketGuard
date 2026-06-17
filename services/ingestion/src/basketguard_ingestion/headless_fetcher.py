"""Headless-browser fetcher for JS-rendered retailer product pages.

Tesco/Asda/Sainsbury's/Morrisons serve their product pages as JavaScript
single-page apps behind WAF/anti-bot stacks. A bare ``urllib`` GET (see
``UrllibSupplierFetcher``) returns an empty shell or a challenge page, so this
module adds a fetcher that drives a real headless browser and returns the
fully-rendered HTML.

The public class is ``PlaywrightSupplierFetcher``. It conforms to the existing
``SupplierFetcher`` Protocol, so a provider can opt into rendered fetches by
passing it as the ``fetcher`` on its scraper config — no parser changes needed.

Playwright is an optional dependency. Importing this module never imports
Playwright; the import happens lazily the first time the default renderer
actually renders a page. Rendering work is delegated to a ``PageRenderer`` seam
so the fetcher and its error mapping are unit-tested against fakes with no live
network and no browser installed (mirroring the injectable ``opener`` on
``UrllibSupplierFetcher``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol

from .fetcher import (
    FetchError,
    FetchHttpStatusError,
    FetchRenderError,
    FetchResponse,
    FetchTimeoutError,
)


@dataclass(frozen=True)
class RenderRequest:
    """Everything a backend needs to render one page."""

    url: str
    timeout_seconds: int
    user_agent: str
    wait_until: str = "networkidle"
    wait_for_selector: str | None = None
    proxy: Mapping[str, str] | None = None
    extra_headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RenderResult:
    """The rendered outcome a backend hands back to the fetcher."""

    status_code: int
    body: str
    headers: Mapping[str, str] = field(default_factory=dict)


class PageRenderer(Protocol):
    def render(self, request: RenderRequest) -> RenderResult:
        ...


class PlaywrightSupplierFetcher:
    """Render a page in a headless browser and return its HTML as a snapshot.

    The actual browser work lives behind a ``PageRenderer``; the default is
    ``PlaywrightPageRenderer``. This class owns the request shaping and the
    mapping from backend outcomes onto the shared ``FetchError`` taxonomy.

    Proxy and extra-header hooks are accepted but default to off, so the
    proxy-pool and anti-bot children of the live-collection epic can wire them
    in later without changing this contract.
    """

    def __init__(
        self,
        renderer: PageRenderer | None = None,
        *,
        wait_until: str = "networkidle",
        wait_for_selector: str | None = None,
        proxy: Mapping[str, str] | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        self.renderer = renderer if renderer is not None else PlaywrightPageRenderer()
        self.wait_until = wait_until
        self.wait_for_selector = wait_for_selector
        self.proxy = proxy
        self.extra_headers = dict(extra_headers) if extra_headers else {}

    def fetch(self, url: str, *, timeout_seconds: int, user_agent: str) -> FetchResponse:
        request = RenderRequest(
            url=url,
            timeout_seconds=timeout_seconds,
            user_agent=user_agent,
            wait_until=self.wait_until,
            wait_for_selector=self.wait_for_selector,
            proxy=self.proxy,
            extra_headers=self.extra_headers,
        )

        try:
            result = self.renderer.render(request)
        except FetchError:
            raise
        except TimeoutError as error:
            raise FetchTimeoutError(str(error) or "Headless render timed out") from error
        except Exception as error:  # noqa: BLE001 - any backend failure is a render failure
            raise FetchRenderError(str(error) or "Headless render failed") from error

        if result.status_code >= 400:
            raise FetchHttpStatusError(
                result.status_code,
                "Rendered page returned an error status",
                body=result.body,
            )

        return FetchResponse(
            url=url,
            status_code=result.status_code,
            body=result.body,
            headers=dict(result.headers),
        )


class PlaywrightPageRenderer:
    """Default ``PageRenderer`` backed by Playwright's sync API.

    Playwright is imported lazily on first ``render`` so the module (and the
    test suite) load without it installed. Playwright's own ``TimeoutError`` is
    translated to ``FetchTimeoutError`` and every other failure to
    ``FetchRenderError`` so callers only ever see the shared taxonomy.
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        launch_options: Mapping[str, object] | None = None,
        playwright_factory=None,
    ) -> None:
        self.headless = headless
        self.launch_options = dict(launch_options) if launch_options else {}
        self._playwright_factory = playwright_factory

    def render(self, request: RenderRequest) -> RenderResult:
        factory = self._playwright_factory or self._default_factory()
        timeout_ms = max(request.timeout_seconds, 0) * 1000

        with factory() as playwright:
            browser = playwright.chromium.launch(headless=self.headless, **self.launch_options)
            try:
                context = browser.new_context(
                    user_agent=request.user_agent,
                    proxy=dict(request.proxy) if request.proxy else None,
                    extra_http_headers=dict(request.extra_headers) if request.extra_headers else None,
                )
                page = context.new_page()
                try:
                    response = page.goto(
                        request.url,
                        wait_until=request.wait_until,
                        timeout=timeout_ms,
                    )
                    if request.wait_for_selector:
                        page.wait_for_selector(request.wait_for_selector, timeout=timeout_ms)
                    body = page.content()
                except Exception as error:  # noqa: BLE001 - translate to shared taxonomy
                    if _is_timeout(error):
                        raise FetchTimeoutError(
                            str(error) or "Headless navigation timed out"
                        ) from error
                    raise FetchRenderError(str(error) or "Headless navigation failed") from error
            finally:
                browser.close()

        if response is None:
            raise FetchRenderError(f"No navigation response for {request.url!r}")

        return RenderResult(
            status_code=int(response.status),
            body=body,
            headers=dict(response.headers),
        )

    @staticmethod
    def _default_factory():
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:  # pragma: no cover - exercised only without playwright
            raise FetchRenderError(
                "Playwright is not installed. Install it with "
                "`pip install playwright` and `playwright install chromium` "
                "to enable headless fetching."
            ) from error
        return sync_playwright


def _is_timeout(error: Exception) -> bool:
    if isinstance(error, TimeoutError):
        return True
    # Playwright raises its own TimeoutError that is not the builtin.
    return type(error).__name__ == "TimeoutError"
