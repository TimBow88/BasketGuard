"""Assemble a production-ready fetcher from the live-collection components.

This is the *wiring* that turns the separate BAS-30/31/33 building blocks into a
single fetcher a provider can use for live collection: a headless render (for JS
SPAs) behind a UK-egress proxy, wrapped in per-host politeness and bounded
retries, configured from ``Settings``.

What this deliberately does and does not do:

* DOES: render JavaScript pages, route through a UK proxy, send honest realistic
  locale headers, rate-limit itself and back off on transient failures.
* DOES NOT: spoof browser/TLS fingerprints, solve CAPTCHAs, or otherwise try to
  *defeat* a WAF/anti-bot challenge. Those are out of scope and gated on the
  data-source & claim-safety review (BAS-26 / BAS-46) — see
  ``docs/backend/11_ANTIBOT_AND_POLITENESS.md``. If a site challenges this
  fetcher it fails honestly (and ``detect_block_signal`` labels the response),
  rather than escalating into evasion.

So this readies live collection up to the defensible line; whether a given
retailer serves a polite headless client is an empirical, per-retailer question
that must be answered by a controlled, authorised spike, not assumed here.
"""

from __future__ import annotations

import time
from typing import Callable, Protocol

from .fetcher import SupplierFetcher, UrllibSupplierFetcher
from .headless_fetcher import PageRenderer, PlaywrightSupplierFetcher
from .proxy import ProxyPool
from .resilience import PolitenessPolicy, RetryingFetcher


# Honest locale/accept headers so pages render correctly. NOT a fingerprint:
# these declare what we accept, they do not impersonate a specific browser.
DEFAULT_LIVE_HEADERS = {
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class LiveFetcherSettings(Protocol):
    fetcher_mode: str
    proxy_url: str | None
    request_delay_seconds: float
    max_retries: int
    retry_backoff_seconds: float


def build_live_fetcher(
    settings: LiveFetcherSettings,
    *,
    proxy_pool: ProxyPool | None = None,
    renderer: PageRenderer | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> SupplierFetcher:
    """Compose the configured live fetcher (politeness + retries + base).

    ``proxy_pool`` takes precedence over ``settings.proxy_url`` for the egress
    proxy. ``renderer``/``sleep``/``clock`` are injectable so the composition is
    unit-tested without a browser, real network or real waiting.
    """

    proxy = _select_proxy(settings, proxy_pool)

    if settings.fetcher_mode == "headless":
        base: SupplierFetcher = PlaywrightSupplierFetcher(
            renderer=renderer,
            wait_until="networkidle",
            proxy=proxy,
            extra_headers=DEFAULT_LIVE_HEADERS,
        )
    else:
        base = UrllibSupplierFetcher()

    politeness = PolitenessPolicy(
        min_interval_seconds=settings.request_delay_seconds,
        jitter_seconds=min(settings.request_delay_seconds, 1.0),
        clock=clock,
        sleep=sleep,
    )
    return RetryingFetcher(
        base,
        max_retries=settings.max_retries,
        backoff_seconds=settings.retry_backoff_seconds,
        politeness=politeness,
        sleep=sleep,
    )


def _select_proxy(
    settings: LiveFetcherSettings, proxy_pool: ProxyPool | None
) -> dict[str, str] | None:
    if proxy_pool is not None:
        return proxy_pool.acquire().as_config()
    if settings.proxy_url:
        return {"server": settings.proxy_url}
    return None
