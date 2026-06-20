from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Callable, Literal, Mapping, Sequence

from .asda_provider import AsdaProductPageParser
from .contracts import CollectionTarget, ProductExtractor
from .fetcher import FetchError, FetchHttpStatusError, SupplierFetcher
from .local_persistence import DEFAULT_ALLOWLIST_SEED
from .morrisons_provider import MorrisonsProductPageParser
from .playwright_fetcher import PlaywrightSupplierFetcher
from .robots import RobotsPolicy
from .sainsburys_provider import SainsburysProductPageParser
from .seed_loader import load_collection_targets
from .tesco_provider import TescoProductPageParser


LIVE_SPIKE_FEATURE_FLAG = "BASKETGUARD_ENABLE_LIVE_SPIKE"
MAX_SPIKE_TARGETS = 25
SPIKE_USER_AGENT = "BasketGuardResearchBot/0.1"
DEFAULT_SPIKE_TIMEOUT_SECONDS = 20
DEFAULT_SPIKE_DELAY_SECONDS = Decimal("2.0")

SpikeOutcome = Literal["rendered", "blocked", "error", "skipped"]

# Specific, branded challenge signatures. Kept narrow so a legitimate product
# page does not trip the heuristic; this is a feasibility signal, not a WAF.
_BLOCK_SIGNATURES: tuple[str, ...] = (
    "captcha",
    "are you a robot",
    "are you human",
    "verify you are human",
    "unusual traffic",
    "access denied",
    "access to this page has been denied",
    "request blocked",
    "/cdn-cgi/challenge",
    "cf-chl",
    "just a moment...",
    "enable javascript and cookies to continue",
    "datadome",
    "px-captcha",
    "perimeterx",
    "incapsula",
    "distil",
)


def detect_block_signal(body: str | None) -> str | None:
    """Return the first bot-challenge signature found in ``body`` (or ``None``).

    Used to classify a ``200`` response that is actually a challenge page, so the
    spike records it as ``blocked`` rather than counting an empty shell as a
    successful render.
    """

    if not body:
        return None
    haystack = body.lower()
    for signature in _BLOCK_SIGNATURES:
        if signature in haystack:
            return signature
    return None


@dataclass(frozen=True)
class SpikeTargetResult:
    retailer: str
    target_url: str
    outcome: SpikeOutcome
    extractable: bool = False
    status_code: int | None = None
    detail: str | None = None
    title: str | None = None
    price: str | None = None


@dataclass(frozen=True)
class SpikeRetailerSummary:
    retailer: str
    targets: int
    rendered: int
    blocked: int
    error: int
    skipped: int
    extractable: int

    @property
    def attempted(self) -> int:
        """Targets that were actually requested (everything but ``skipped``)."""

        return self.rendered + self.blocked + self.error

    @property
    def block_rate(self) -> Decimal:
        if self.attempted == 0:
            return Decimal("0")
        return (Decimal(self.blocked) / Decimal(self.attempted)).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class FeasibilitySpikeReport:
    results: list[SpikeTargetResult] = field(default_factory=list)

    @property
    def target_count(self) -> int:
        return len(self.results)

    @property
    def rendered_count(self) -> int:
        return sum(1 for result in self.results if result.outcome == "rendered")

    @property
    def blocked_count(self) -> int:
        return sum(1 for result in self.results if result.outcome == "blocked")

    @property
    def error_count(self) -> int:
        return sum(1 for result in self.results if result.outcome == "error")

    @property
    def skipped_count(self) -> int:
        return sum(1 for result in self.results if result.outcome == "skipped")

    @property
    def attempted_count(self) -> int:
        """Targets that were actually requested (everything but ``skipped``)."""

        return self.rendered_count + self.blocked_count + self.error_count

    @property
    def extractable_count(self) -> int:
        return sum(1 for result in self.results if result.extractable)

    @property
    def block_rate(self) -> Decimal:
        if self.attempted_count == 0:
            return Decimal("0")
        return (Decimal(self.blocked_count) / Decimal(self.attempted_count)).quantize(
            Decimal("0.01"),
        )

    def retailer_summaries(self) -> list[SpikeRetailerSummary]:
        order: list[str] = []
        grouped: dict[str, list[SpikeTargetResult]] = {}
        for result in self.results:
            if result.retailer not in grouped:
                order.append(result.retailer)
            grouped.setdefault(result.retailer, []).append(result)
        summaries = []
        for retailer in order:
            entries = grouped[retailer]
            summaries.append(
                SpikeRetailerSummary(
                    retailer=retailer,
                    targets=len(entries),
                    rendered=sum(1 for entry in entries if entry.outcome == "rendered"),
                    blocked=sum(1 for entry in entries if entry.outcome == "blocked"),
                    error=sum(1 for entry in entries if entry.outcome == "error"),
                    skipped=sum(1 for entry in entries if entry.outcome == "skipped"),
                    extractable=sum(1 for entry in entries if entry.extractable),
                ),
            )
        return summaries

    def format_report(self) -> str:
        lines = ["basketguard feasibility spike report"]
        for summary in self.retailer_summaries():
            lines.append(
                f"  {summary.retailer}: targets={summary.targets} "
                f"rendered={summary.rendered} blocked={summary.blocked} "
                f"error={summary.error} skipped={summary.skipped} "
                f"extractable={summary.extractable} block_rate={summary.block_rate}",
            )
        lines.append(
            "  overall: "
            f"targets={self.target_count} rendered={self.rendered_count} "
            f"blocked={self.blocked_count} error={self.error_count} "
            f"skipped={self.skipped_count} extractable={self.extractable_count} "
            f"block_rate={self.block_rate}",
        )
        return "\n".join(lines)


class SpikeNotAuthorisedError(RuntimeError):
    """Raised when the live spike is invoked without all three required gates."""

    def __init__(self, missing: Sequence[str]) -> None:
        self.missing = tuple(missing)
        super().__init__("; ".join(self.missing))


class SpikeTargetCapError(RuntimeError):
    """Raised when a spike would exceed the hard target cap."""

    def __init__(self, requested: int, cap: int) -> None:
        self.requested = requested
        self.cap = cap
        super().__init__(
            f"feasibility spike refuses {requested} targets; the hard cap is {cap}. "
            "Narrow the seed or use --retailer/--max-targets to stay within it.",
        )


def missing_spike_gates(*, live: bool, legal_signoff: bool, env: Mapping[str, str]) -> list[str]:
    """List the human-readable gate requirements that are not satisfied."""

    missing: list[str] = []
    if not live:
        missing.append("--live flag is required to make any live request")
    if not legal_signoff:
        missing.append(
            "--i-have-legal-signoff flag is required (BAS-26/BAS-46 must be cleared)",
        )
    if env.get(LIVE_SPIKE_FEATURE_FLAG) != "1":
        missing.append(f"{LIVE_SPIKE_FEATURE_FLAG}=1 environment variable is required")
    return missing


def build_live_fetcher() -> SupplierFetcher:
    """Construct the live fetcher used by the spike.

    This is the single seam where a real browser-backed fetcher is created, so
    tests inject a fake instead and the gate logic can be exercised offline.
    """

    return PlaywrightSupplierFetcher()


def _default_extractors() -> dict[str, ProductExtractor]:
    return {
        "tesco": TescoProductPageParser(),
        "asda": AsdaProductPageParser(),
        "sainsbury's": SainsburysProductPageParser(),
        "sainsburys": SainsburysProductPageParser(),
        "morrisons": MorrisonsProductPageParser(),
    }


class FeasibilitySpike:
    """Make at most one polite request per allowlisted target and classify it.

    Each target is fetched exactly once (no retries, no evasion) and recorded as
    ``rendered``, ``blocked`` or ``error``. A rendered page is additionally run
    through the retailer extractor so the report distinguishes "a page came back"
    from "a real title and price came back" (``extractable``).
    """

    def __init__(
        self,
        fetcher: SupplierFetcher,
        *,
        extractors: Mapping[str, ProductExtractor] | None = None,
        robots_policy: RobotsPolicy | None = None,
        timeout_seconds: int = DEFAULT_SPIKE_TIMEOUT_SECONDS,
        user_agent: str = SPIKE_USER_AGENT,
        request_delay_seconds: Decimal = DEFAULT_SPIKE_DELAY_SECONDS,
        block_signal_detector: Callable[[str | None], str | None] = detect_block_signal,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._fetcher = fetcher
        self._extractors = dict(extractors) if extractors is not None else _default_extractors()
        self._robots_policy = robots_policy if robots_policy is not None else RobotsPolicy()
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent
        self._request_delay_seconds = request_delay_seconds
        self._detect_block_signal = block_signal_detector
        self._sleep = sleep

    def run(self, targets: Sequence[CollectionTarget]) -> FeasibilitySpikeReport:
        results: list[SpikeTargetResult] = []
        for index, target in enumerate(targets):
            if index > 0:
                self._sleep(float(self._request_delay_seconds))
            results.append(self._probe(target))
        return FeasibilitySpikeReport(results=results)

    def _probe(self, target: CollectionTarget) -> SpikeTargetResult:
        url = target.target_url or ""
        retailer = target.retailer

        robots = self._robots_policy.is_allowed(url, self._user_agent)
        if not robots.allowed:
            return SpikeTargetResult(
                retailer=retailer,
                target_url=url,
                outcome="skipped",
                detail=f"robots_{robots.reason}",
            )

        try:
            response = self._fetcher.fetch(
                url,
                timeout_seconds=self._timeout_seconds,
                user_agent=self._user_agent,
            )
        except FetchHttpStatusError as error:
            if error.status_code in (403, 429):
                return SpikeTargetResult(
                    retailer=retailer,
                    target_url=url,
                    outcome="blocked",
                    status_code=error.status_code,
                    detail=f"http_{error.status_code}",
                )
            signal = self._detect_block_signal(error.body)
            if signal:
                return SpikeTargetResult(
                    retailer=retailer,
                    target_url=url,
                    outcome="blocked",
                    status_code=error.status_code,
                    detail=f"block_signal:{signal}",
                )
            return SpikeTargetResult(
                retailer=retailer,
                target_url=url,
                outcome="error",
                status_code=error.status_code,
                detail=error.error_code,
            )
        except FetchError as error:
            return SpikeTargetResult(
                retailer=retailer,
                target_url=url,
                outcome="error",
                detail=error.error_code,
            )

        signal = self._detect_block_signal(response.body)
        if signal:
            return SpikeTargetResult(
                retailer=retailer,
                target_url=url,
                outcome="blocked",
                status_code=response.status_code,
                detail=f"block_signal:{signal}",
            )

        return self._classify_rendered(retailer, url, response.status_code, response.body)

    def _classify_rendered(
        self,
        retailer: str,
        url: str,
        status_code: int,
        body: str,
    ) -> SpikeTargetResult:
        extractor = self._extractors.get(retailer.lower())
        if extractor is None:
            return SpikeTargetResult(
                retailer=retailer,
                target_url=url,
                outcome="rendered",
                status_code=status_code,
                detail="no_extractor",
            )
        try:
            extracted = extractor.extract(body, url)
        except Exception as error:  # noqa: BLE001 - a parser bug must not abort the spike
            return SpikeTargetResult(
                retailer=retailer,
                target_url=url,
                outcome="rendered",
                status_code=status_code,
                detail=f"extract_error:{error.__class__.__name__}",
            )

        extractable = bool(extracted.title and extracted.price)
        detail = "extractable" if extractable else f"missing:{','.join(extracted.missing_fields)}"
        return SpikeTargetResult(
            retailer=retailer,
            target_url=url,
            outcome="rendered",
            extractable=extractable,
            status_code=status_code,
            detail=detail,
            title=extracted.title,
            price=extracted.price,
        )


def run_feasibility_spike(
    *,
    seed_path: str | Path = DEFAULT_ALLOWLIST_SEED,
    live: bool,
    legal_signoff: bool,
    env: Mapping[str, str] | None = None,
    retailers: set[str] | None = None,
    max_targets: int = MAX_SPIKE_TARGETS,
    fetcher_factory: Callable[[], SupplierFetcher] = build_live_fetcher,
    spike_factory: Callable[..., FeasibilitySpike] = FeasibilitySpike,
) -> FeasibilitySpikeReport:
    """Run the spike, refusing any network access unless all gates are present.

    Gates are checked before targets are loaded and before the fetcher is built,
    so an unauthorised call touches no network and the fetcher factory is never
    invoked.
    """

    environment = os.environ if env is None else env
    missing = missing_spike_gates(live=live, legal_signoff=legal_signoff, env=environment)
    if missing:
        raise SpikeNotAuthorisedError(missing)

    targets = _selected_spike_targets(seed_path, retailers=retailers, max_targets=max_targets)
    fetcher = fetcher_factory()
    spike = spike_factory(fetcher)
    return spike.run(targets)


def _selected_spike_targets(
    seed_path: str | Path,
    *,
    retailers: set[str] | None,
    max_targets: int,
) -> list[CollectionTarget]:
    if max_targets < 1:
        raise ValueError("max_targets must be at least 1")
    if max_targets > MAX_SPIKE_TARGETS:
        raise SpikeTargetCapError(max_targets, MAX_SPIKE_TARGETS)

    targets = [
        target
        for target in load_collection_targets(seed_path)
        if target.is_active and target.target_url
    ]
    if retailers is not None:
        targets = [target for target in targets if target.retailer.lower() in retailers]
    if len(targets) > max_targets:
        raise SpikeTargetCapError(len(targets), max_targets)
    return targets


def main(
    argv: list[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    fetcher_factory: Callable[[], SupplierFetcher] = build_live_fetcher,
    spike_factory: Callable[..., FeasibilitySpike] = FeasibilitySpike,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    selected_retailers = {retailer.lower() for retailer in args.retailer} or None

    try:
        report = run_feasibility_spike(
            seed_path=args.allowlist_seed,
            live=args.live,
            legal_signoff=args.i_have_legal_signoff,
            env=env,
            retailers=selected_retailers,
            max_targets=args.max_targets,
            fetcher_factory=fetcher_factory,
            spike_factory=spike_factory,
        )
    except SpikeNotAuthorisedError as error:
        print("basketguard feasibility spike refused: missing required gates", file=sys.stderr)
        for requirement in error.missing:
            print(f"  - {requirement}", file=sys.stderr)
        return 2
    except SpikeTargetCapError as error:
        print(f"basketguard feasibility spike refused: {error}", file=sys.stderr)
        return 2
    except Exception as error:  # noqa: BLE001 - surface the failure on the CLI boundary
        print(f"basketguard feasibility spike failed: {error}", file=sys.stderr)
        return 1

    print(report.format_report())
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Probe allowlisted targets once each to measure whether polite live "
            "collection is feasible. Requires --live, --i-have-legal-signoff and "
            f"{LIVE_SPIKE_FEATURE_FLAG}=1; it makes no network request otherwise."
        ),
    )
    parser.add_argument(
        "--allowlist-seed",
        default=DEFAULT_ALLOWLIST_SEED,
        type=Path,
        help="JSON seed containing explicit allowlisted product targets.",
    )
    parser.add_argument(
        "--retailer",
        action="append",
        default=[],
        help="Retailer name to include. Repeat for multiple. Defaults to all seed targets.",
    )
    parser.add_argument(
        "--max-targets",
        type=int,
        default=MAX_SPIKE_TARGETS,
        help=f"Per-run target limit (cannot exceed the hard cap of {MAX_SPIKE_TARGETS}).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Required gate: allow live requests.",
    )
    parser.add_argument(
        "--i-have-legal-signoff",
        dest="i_have_legal_signoff",
        action="store_true",
        help="Required gate: confirm BAS-26/BAS-46 legal review is cleared.",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
