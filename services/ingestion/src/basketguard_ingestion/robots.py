from __future__ import annotations

from dataclasses import dataclass
from urllib import robotparser
from urllib.parse import urlsplit

from .fetcher import FetchError, FetchHttpStatusError, SupplierFetcher, UrllibSupplierFetcher


@dataclass(frozen=True)
class RobotsDecision:
    """Outcome of a robots.txt check for one URL.

    ``reason`` is one of:
    - ``allowed``     — robots.txt permits the path (or there is no robots.txt);
    - ``disallowed``  — robots.txt explicitly forbids the path for the agent;
    - ``unavailable`` — robots.txt could not be read (network error / 5xx), so
      the path is treated as not-allowed rather than guessed.
    """

    allowed: bool
    reason: str


class RobotsPolicy:
    """Checks target URLs against each host's robots.txt, with per-host caching.

    robots.txt is plain text, so it is fetched with the lightweight
    ``UrllibSupplierFetcher`` rather than a browser. Status handling follows the
    common crawler convention:

    - ``2xx``                 — parse and apply the rules;
    - ``401``/``403``         — access restricted, treat as disallow-all;
    - other ``4xx`` (e.g. 404) — no robots.txt, allow all;
    - ``5xx`` / network error  — unavailable, treated as not-allowed (cautious,
      so a compliance probe never hits a host whose robots.txt it could not read).
    """

    def __init__(
        self,
        fetcher: SupplierFetcher | None = None,
        *,
        timeout_seconds: int = 10,
    ) -> None:
        self._fetcher = fetcher or UrllibSupplierFetcher()
        self._timeout_seconds = timeout_seconds
        self._cache: dict[str, robotparser.RobotFileParser | None | str] = {}

    def is_allowed(self, url: str, user_agent: str) -> RobotsDecision:
        parts = urlsplit(url)
        if not parts.scheme or not parts.netloc:
            return RobotsDecision(False, "unavailable")
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._cache:
            self._cache[base] = self._load(f"{base}/robots.txt", user_agent)

        cached = self._cache[base]
        if cached == "unavailable":
            return RobotsDecision(False, "unavailable")
        if cached is None:
            return RobotsDecision(True, "allowed")

        assert isinstance(cached, robotparser.RobotFileParser)
        if cached.can_fetch(user_agent, url):
            return RobotsDecision(True, "allowed")
        return RobotsDecision(False, "disallowed")

    def _load(
        self,
        robots_url: str,
        user_agent: str,
    ) -> robotparser.RobotFileParser | None | str:
        try:
            response = self._fetcher.fetch(
                robots_url,
                timeout_seconds=self._timeout_seconds,
                user_agent=user_agent,
            )
        except FetchHttpStatusError as error:
            status = error.status_code or 0
            if status in (401, 403):
                parser = robotparser.RobotFileParser()
                parser.disallow_all = True
                return parser
            if 400 <= status < 500:
                return None
            return "unavailable"
        except FetchError:
            return "unavailable"

        parser = robotparser.RobotFileParser()
        parser.parse(response.body.splitlines())
        return parser
