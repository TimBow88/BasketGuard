"""Proxy pool & UK-egress management for sustained collection.

A single datacentre IP gets rate-limited or blocked quickly, and UK retailer
pricing/availability assumes a UK egress. This provides a pluggable rotation
pool the fetching layer draws from, without hard-wiring a vendor:

* ``ProxyEndpoint`` — one upstream proxy (server URL, optional credentials,
  country, sticky-session flag), exposed as a Playwright-style ``as_config``.
* ``ProxyPool`` — round-robin selection over healthy endpoints, with failure
  reporting that quarantines an endpoint after repeated failures and restores it
  after a cooldown.

The pool is transport-agnostic: it hands out a proxy config that the headless
fetcher's ``proxy`` hook (or a urllib opener) consumes. Time is injected so
quarantine/cooldown is deterministic under test.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


class ProxyPoolError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProxyEndpoint:
    server: str
    username: str | None = None
    password: str | None = None
    country: str = "GB"
    sticky: bool = False

    def as_config(self) -> dict[str, str]:
        """Render as a Playwright ``proxy=`` mapping (also usable elsewhere)."""

        config: dict[str, str] = {"server": self.server}
        if self.username is not None:
            config["username"] = self.username
        if self.password is not None:
            config["password"] = self.password
        return config


@dataclass
class _EndpointHealth:
    consecutive_failures: int = 0
    quarantined_until: float | None = None


@dataclass
class ProxyPool:
    """Round-robin pool over healthy proxy endpoints with quarantine.

    ``acquire`` returns the next healthy endpoint (whose cooldown has expired);
    ``report_failure`` quarantines an endpoint once it crosses
    ``failure_threshold`` consecutive failures, for ``cooldown_seconds``;
    ``report_success`` clears its failure count.
    """

    endpoints: list[ProxyEndpoint]
    country: str = "GB"
    failure_threshold: int = 3
    cooldown_seconds: float = 300.0
    clock: Callable[[], float] = time.monotonic
    _health: dict[str, _EndpointHealth] = field(default_factory=dict)
    _cursor: int = 0

    def __post_init__(self) -> None:
        scoped = [endpoint for endpoint in self.endpoints if endpoint.country == self.country]
        # Keep only endpoints matching the required egress country.
        self.endpoints = scoped
        if not self.endpoints:
            raise ProxyPoolError(
                f"Proxy pool has no endpoints for country {self.country!r}."
            )
        self._health = {endpoint.server: _EndpointHealth() for endpoint in self.endpoints}

    def acquire(self) -> ProxyEndpoint:
        now = self.clock()
        count = len(self.endpoints)
        for offset in range(count):
            endpoint = self.endpoints[(self._cursor + offset) % count]
            if self._available(endpoint, now):
                self._cursor = (self._cursor + offset + 1) % count
                return endpoint
        raise ProxyPoolError("All proxy endpoints are quarantined.")

    def report_success(self, endpoint: ProxyEndpoint) -> None:
        health = self._health[endpoint.server]
        health.consecutive_failures = 0
        health.quarantined_until = None

    def report_failure(self, endpoint: ProxyEndpoint) -> None:
        health = self._health[endpoint.server]
        health.consecutive_failures += 1
        if health.consecutive_failures >= self.failure_threshold:
            health.quarantined_until = self.clock() + self.cooldown_seconds

    def available_count(self) -> int:
        now = self.clock()
        return sum(1 for endpoint in self.endpoints if self._available(endpoint, now))

    def _available(self, endpoint: ProxyEndpoint, now: float) -> bool:
        health = self._health[endpoint.server]
        if health.quarantined_until is None:
            return True
        if now >= health.quarantined_until:
            # Cooldown elapsed: restore the endpoint to the rotation.
            health.quarantined_until = None
            health.consecutive_failures = 0
            return True
        return False
