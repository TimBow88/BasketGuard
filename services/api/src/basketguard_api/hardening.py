"""Edge hardening for the public API: rate limiting, input validation, headers.

The report endpoints query PostgreSQL with bound parameters, so they are not
injectable, but the surface still needs basic abuse protection before it is
exposed publicly (distinct from user auth, BAS-20). This adds:

* ``RateLimiter`` — a fixed-window per-client counter (pure, clock-injected, so
  it is unit-tested without HTTP or real time);
* ``validate_group_slug`` — reject malformed/oversized slugs early with 422;
* ``install_hardening`` — wire the limiter + security headers onto a FastAPI app.

Defaults are generous so normal use and the existing tests are unaffected; the
limit/window are configurable for deployment and for tests that exercise 429.
"""

from __future__ import annotations

import time
from typing import Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse


import re

SLUG_PATTERN = re.compile(r"^[a-z0-9_]{1,100}$")
MAX_GROUP_SLUGS = 50

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


def validate_group_slug(slug: str) -> str:
    """Return the slug if it is a well-formed group slug, else raise 422."""

    if not SLUG_PATTERN.match(slug):
        raise HTTPException(
            status_code=422,
            detail=(
                "group_slug must be 1-100 chars of lowercase letters, digits or "
                "underscores."
            ),
        )
    return slug


def validate_group_slugs(slugs: list[str], *, max_slugs: int = MAX_GROUP_SLUGS) -> list[str]:
    if len(slugs) > max_slugs:
        raise HTTPException(
            status_code=422,
            detail=f"At most {max_slugs} group_slug values may be requested at once.",
        )
    return [validate_group_slug(slug) for slug in slugs]


class RateLimiter:
    def __init__(
        self,
        *,
        limit: int = 120,
        window_seconds: int = 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self._hits: dict[tuple[str, int], int] = {}

    def check(self, key: str) -> bool:
        """Record a hit for ``key``; return True if still within the limit."""

        bucket = int(self.clock() // self.window_seconds)
        # Drop counters from elapsed windows so memory stays bounded.
        for existing in [k for k in self._hits if k[1] != bucket]:
            del self._hits[existing]
        count = self._hits.get((key, bucket), 0) + 1
        self._hits[(key, bucket)] = count
        return count <= self.limit


def install_hardening(
    app: FastAPI,
    *,
    rate_limit: int = 120,
    rate_window_seconds: int = 60,
    clock: Callable[[], float] = time.monotonic,
    exempt_paths: frozenset[str] = frozenset({"/health"}),
) -> RateLimiter:
    limiter = RateLimiter(limit=rate_limit, window_seconds=rate_window_seconds, clock=clock)

    @app.middleware("http")
    async def _rate_limit_and_headers(request, call_next):  # type: ignore[no-untyped-def]
        if request.url.path not in exempt_paths:
            client_key = request.client.host if request.client else "anonymous"
            if not limiter.check(client_key):
                response = JSONResponse(
                    status_code=429, content={"detail": "Rate limit exceeded"}
                )
                _apply_security_headers(response)
                return response
        response = await call_next(request)
        _apply_security_headers(response)
        return response

    app.state.rate_limiter = limiter
    return limiter


def _apply_security_headers(response) -> None:  # type: ignore[no-untyped-def]
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
