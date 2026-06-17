"""Request politeness and retry/backoff around any ``SupplierFetcher``.

Sustained collection needs to be a good citizen (rate-limit ourselves per host)
and to ride out transient failures (timeouts, 429/5xx, flaky renders) without
hammering the origin. ``RetryingFetcher`` wraps any ``SupplierFetcher`` and adds:

* a per-host ``PolitenessPolicy`` minimum interval with optional jitter;
* bounded exponential backoff retries on *transient* failures only — never on a
  404 or a hard 403 challenge, where retrying the same way cannot help.

This is the implementable half of the anti-bot strategy (see
``docs/backend/11_ANTIBOT_AND_POLITENESS.md``). It conforms to the same
``SupplierFetcher`` Protocol, so providers wrap their fetcher without any change
to parsers. Clock, sleep and randomness are injected so behaviour is
deterministic under test with no real waiting.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from random import random as _system_random
from typing import Callable, Mapping
from urllib.parse import urlparse

from .fetcher import (
    FetchError,
    FetchHttpStatusError,
    FetchRenderError,
    FetchResponse,
    FetchTimeoutError,
    FetchUrlError,
    SupplierFetcher,
)


DEFAULT_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

# Lower-cased substrings that betray a WAF/anti-bot interstitial rather than a
# genuine product page. Used to label a fetch as a probable block for
# observability and drift detection; not every retailer hit will be covered.
_BLOCK_SIGNATURES = (
    "captcha",
    "are you a robot",
    "are you a human",
    "cf-browser-verification",
    "cloudflare",
    "access denied",
    "request unsuccessful. incapsula",
    "datadome",
    "px-captcha",
    "verifying you are human",
)


def detect_block_signal(body: str | None, status_code: int | None = None) -> str | None:
    """Return a short reason if the response looks like a bot challenge/block.

    Returns ``None`` when the response looks like genuine content. A 403/429 is
    reported as a block even without a body signature, since those are the
    canonical anti-bot status codes.
    """

    if status_code in (403, 429):
        return f"http_{status_code}"
    if not body:
        return None
    haystack = body.lower()
    for signature in _BLOCK_SIGNATURES:
        if signature in haystack:
            return signature
    return None


@dataclass
class PolitenessPolicy:
    """Throttle requests to honour a minimum interval per host.

    ``wait(host)`` blocks just long enough that consecutive requests to the same
    host are at least ``min_interval_seconds`` apart, plus up to
    ``jitter_seconds`` of randomness so the cadence is not perfectly regular.
    """

    min_interval_seconds: float = 1.0
    jitter_seconds: float = 0.0
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    random: Callable[[], float] = _system_random
    _last_request: dict[str, float] = field(default_factory=dict)

    def wait(self, host: str) -> float:
        """Sleep if needed; return the number of seconds slept."""

        now = self.clock()
        last = self._last_request.get(host)
        slept = 0.0
        if last is not None:
            elapsed = now - last
            delay = self.min_interval_seconds - elapsed
            if self.jitter_seconds:
                delay += self.random() * self.jitter_seconds
            if delay > 0:
                self.sleep(delay)
                slept = delay
        self._last_request[host] = self.clock()
        return slept


class RetryingFetcher:
    """A ``SupplierFetcher`` decorator adding politeness + bounded retries."""

    def __init__(
        self,
        inner: SupplierFetcher,
        *,
        max_retries: int = 2,
        backoff_seconds: float = 2.0,
        backoff_factor: float = 2.0,
        retryable_statuses: frozenset[int] = DEFAULT_RETRYABLE_STATUSES,
        politeness: PolitenessPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must not be negative")
        self.inner = inner
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.backoff_factor = backoff_factor
        self.retryable_statuses = retryable_statuses
        self.politeness = politeness
        self.sleep = sleep

    def fetch(self, url: str, *, timeout_seconds: int, user_agent: str) -> FetchResponse:
        host = urlparse(url).netloc or url
        attempt = 0
        while True:
            if self.politeness is not None:
                self.politeness.wait(host)
            try:
                return self.inner.fetch(
                    url,
                    timeout_seconds=timeout_seconds,
                    user_agent=user_agent,
                )
            except FetchError as error:
                if attempt >= self.max_retries or not self._is_retryable(error):
                    raise
                self.sleep(self.backoff_seconds * (self.backoff_factor ** attempt))
                attempt += 1

    def _is_retryable(self, error: FetchError) -> bool:
        if isinstance(error, (FetchTimeoutError, FetchUrlError, FetchRenderError)):
            return True
        if isinstance(error, FetchHttpStatusError):
            return error.status_code in self.retryable_statuses
        return False
