"""Centralised, typed runtime configuration for BasketGuard backends.

Today configuration is read ad-hoc with scattered ``os.environ`` lookups
(database URL in ``postgres.py``, per-retailer ``BASKETGUARD_ENABLE_*`` flags in
each provider). ``Settings`` gathers those into one validated object so services,
the migration runner, the collection orchestrator and the fetching layer read a
single source of truth.

``Settings.from_env`` takes an explicit environment mapping (defaulting to
``os.environ``) so it is deterministic to unit-test, and raises ``SettingsError``
with an actionable message on malformed values rather than failing later deep in
a run. Nothing here connects to anything or has side effects.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


DATABASE_URL_ENV = "BASKETGUARD_DATABASE_URL"
FALLBACK_DATABASE_URL_ENV = "DATABASE_URL"

# Per-retailer live-collection flags, kept identical to the names the providers
# already check so adopting Settings does not change operational behaviour.
RETAILER_FEATURE_FLAGS: dict[str, str] = {
    "tesco": "BASKETGUARD_ENABLE_TESCO_SCRAPER",
    "asda": "BASKETGUARD_ENABLE_ASDA_SCRAPER",
    "sainsburys": "BASKETGUARD_ENABLE_SAINSBURYS_SCRAPER",
    "morrisons": "BASKETGUARD_ENABLE_MORRISONS_SCRAPER",
}

FETCHER_MODE_ENV = "BASKETGUARD_FETCHER_MODE"
VALID_FETCHER_MODES = ("urllib", "headless")

REQUEST_TIMEOUT_ENV = "BASKETGUARD_REQUEST_TIMEOUT_SECONDS"
REQUEST_DELAY_ENV = "BASKETGUARD_REQUEST_DELAY_SECONDS"
MAX_RETRIES_ENV = "BASKETGUARD_MAX_RETRIES"
RETRY_BACKOFF_ENV = "BASKETGUARD_RETRY_BACKOFF_SECONDS"
PROXY_URL_ENV = "BASKETGUARD_PROXY_URL"
SNAPSHOT_ROOT_ENV = "BASKETGUARD_SNAPSHOT_ROOT"
POSTCODE_CONTEXT_ENV = "BASKETGUARD_COLLECTION_POSTCODE_CONTEXT"
LOG_LEVEL_ENV = "BASKETGUARD_LOG_LEVEL"


class SettingsError(RuntimeError):
    """Raised when an environment value cannot be parsed into a setting."""


@dataclass(frozen=True)
class Settings:
    database_url: str | None = None
    enabled_retailers: frozenset[str] = frozenset()
    fetcher_mode: str = "urllib"
    request_timeout_seconds: int = 15
    request_delay_seconds: float = 1.0
    max_retries: int = 2
    retry_backoff_seconds: float = 2.0
    proxy_url: str | None = None
    snapshot_root: Path | None = None
    collection_postcode_context: str | None = None
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ

        database_url = (
            _clean(env.get(DATABASE_URL_ENV))
            or _clean(env.get(FALLBACK_DATABASE_URL_ENV))
        )

        enabled_retailers = frozenset(
            retailer
            for retailer, flag in RETAILER_FEATURE_FLAGS.items()
            if env.get(flag) == "1"
        )

        fetcher_mode = _clean(env.get(FETCHER_MODE_ENV)) or "urllib"
        if fetcher_mode not in VALID_FETCHER_MODES:
            raise SettingsError(
                f"{FETCHER_MODE_ENV} must be one of {VALID_FETCHER_MODES}, "
                f"got {fetcher_mode!r}."
            )

        snapshot_root_value = _clean(env.get(SNAPSHOT_ROOT_ENV))

        return cls(
            database_url=database_url,
            enabled_retailers=enabled_retailers,
            fetcher_mode=fetcher_mode,
            request_timeout_seconds=_positive_int(env, REQUEST_TIMEOUT_ENV, 15),
            request_delay_seconds=_non_negative_float(env, REQUEST_DELAY_ENV, 1.0),
            max_retries=_non_negative_int(env, MAX_RETRIES_ENV, 2),
            retry_backoff_seconds=_non_negative_float(env, RETRY_BACKOFF_ENV, 2.0),
            proxy_url=_clean(env.get(PROXY_URL_ENV)),
            snapshot_root=Path(snapshot_root_value) if snapshot_root_value else None,
            collection_postcode_context=_clean(env.get(POSTCODE_CONTEXT_ENV)),
            log_level=(_clean(env.get(LOG_LEVEL_ENV)) or "INFO").upper(),
        )

    def retailer_enabled(self, retailer: str) -> bool:
        return retailer.lower() in self.enabled_retailers

    def require_database_url(self) -> str:
        if not self.database_url:
            raise SettingsError(
                f"Set {DATABASE_URL_ENV} (or {FALLBACK_DATABASE_URL_ENV}) to a "
                "PostgreSQL connection string."
            )
        return self.database_url


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _positive_int(env: Mapping[str, str], key: str, default: int) -> int:
    value = _non_negative_int(env, key, default)
    if value <= 0:
        raise SettingsError(f"{key} must be a positive integer, got {value!r}.")
    return value


def _non_negative_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = _clean(env.get(key))
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise SettingsError(f"{key} must be an integer, got {raw!r}.") from error
    if value < 0:
        raise SettingsError(f"{key} must not be negative, got {value!r}.")
    return value


def _non_negative_float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = _clean(env.get(key))
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as error:
        raise SettingsError(f"{key} must be a number, got {raw!r}.") from error
    if value < 0:
        raise SettingsError(f"{key} must not be negative, got {value!r}.")
    return value
