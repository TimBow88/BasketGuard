from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class FetchResponse:
    url: str
    status_code: int
    body: str
    headers: Mapping[str, str] = field(default_factory=dict)


class FetchError(RuntimeError):
    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        status_code: int | None = None,
        body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code
        self.body = body


class FetchHttpStatusError(FetchError):
    def __init__(self, status_code: int, reason: str, *, body: str | None = None) -> None:
        super().__init__(
            f"http_{status_code}",
            f"HTTP {status_code}: {reason}".strip(),
            status_code=status_code,
            body=body,
        )


class FetchTimeoutError(FetchError):
    def __init__(self, message: str = "Request timed out") -> None:
        super().__init__("timeout", message)


class FetchUrlError(FetchError):
    def __init__(self, message: str) -> None:
        super().__init__("url_error", message)


class SupplierFetcher(Protocol):
    def fetch(self, url: str, *, timeout_seconds: int, user_agent: str) -> FetchResponse:
        ...


Opener = Callable[..., object]


class UrllibSupplierFetcher:
    def __init__(self, opener: Opener = urlopen) -> None:
        self.opener = opener

    def fetch(self, url: str, *, timeout_seconds: int, user_agent: str) -> FetchResponse:
        request = Request(url, headers={"User-Agent": user_agent})
        try:
            with self.opener(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
                status_code = int(getattr(response, "status", 200))
                headers = dict(getattr(response, "headers", {}) or {})
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise FetchHttpStatusError(
                error.code,
                error.reason or "HTTP error",
                body=body,
            ) from error
        except TimeoutError as error:
            raise FetchTimeoutError(str(error) or "Request timed out") from error
        except socket.timeout as error:
            raise FetchTimeoutError(str(error) or "Request timed out") from error
        except URLError as error:
            reason = error.reason
            if isinstance(reason, TimeoutError | socket.timeout):
                raise FetchTimeoutError(str(reason) or "Request timed out") from error
            raise FetchUrlError(str(reason or error)) from error

        if status_code >= 400:
            raise FetchHttpStatusError(status_code, "HTTP error", body=body)

        return FetchResponse(
            url=url,
            status_code=status_code,
            body=body,
            headers=headers,
        )
