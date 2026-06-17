"""Live feasibility spike harness (PREP ONLY — gated, not run by default).

Answers the empirical go/no-go question for live collection: does a *polite*
headless client actually get served real product pages, or get challenged? It
makes at most one request per allowlisted target, classifies the outcome
(rendered / blocked / error), and reports the per-retailer block rate.

Safety model (three independent gates; see the CLI):

1. ``--live`` must be passed explicitly;
2. ``--i-have-legal-signoff`` must be passed (BAS-26 / BAS-46 cleared);
3. ``BASKETGUARD_ENABLE_LIVE_SPIKE=1`` must be set in the environment.

Without all three the CLI refuses and makes no network request. There is a hard
cap on target count even when gated. The harness class itself takes an injected
fetcher, so it is unit-tested against fakes with no network — exactly how it is
exercised here. It performs no evasion: a challenge is recorded as a block and
collection stops, it is never escalated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence

from .contracts import ProductExtractor
from .fetcher import FetchError, FetchHttpStatusError, FetchResponse, SupplierFetcher
from .resilience import detect_block_signal


SpikeOutcome = Literal["rendered", "blocked", "error"]

# Even with every gate cleared, refuse to fan out beyond this in one spike.
MAX_SPIKE_TARGETS = 25


@dataclass(frozen=True)
class SpikeTarget:
    retailer: str
    url: str


@dataclass(frozen=True)
class SpikeAttempt:
    retailer: str
    url: str
    outcome: SpikeOutcome
    status_code: int | None = None
    block_signal: str | None = None
    content_length: int = 0
    extracted_title: str | None = None
    extracted_price: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def extractable(self) -> bool:
        return bool(self.extracted_title and self.extracted_price)


@dataclass(frozen=True)
class SpikeReport:
    attempts: list[SpikeAttempt] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.attempts)

    def _count(self, outcome: SpikeOutcome) -> int:
        return sum(1 for attempt in self.attempts if attempt.outcome == outcome)

    @property
    def rendered(self) -> int:
        return self._count("rendered")

    @property
    def blocked(self) -> int:
        return self._count("blocked")

    @property
    def errored(self) -> int:
        return self._count("error")

    @property
    def extractable(self) -> int:
        return sum(1 for attempt in self.attempts if attempt.extractable)

    @property
    def block_rate(self) -> float:
        return self.blocked / self.total if self.total else 0.0

    def by_retailer(self) -> dict[str, dict[str, int]]:
        summary: dict[str, dict[str, int]] = {}
        for attempt in self.attempts:
            bucket = summary.setdefault(
                attempt.retailer,
                {"rendered": 0, "blocked": 0, "error": 0, "extractable": 0},
            )
            bucket[attempt.outcome] += 1
            if attempt.extractable:
                bucket["extractable"] += 1
        return summary

    def format(self) -> str:
        lines = [
            f"Feasibility spike: {self.total} target(s) — "
            f"rendered={self.rendered} blocked={self.blocked} error={self.errored} "
            f"extractable={self.extractable} block_rate={self.block_rate:.0%}",
        ]
        for retailer, counts in sorted(self.by_retailer().items()):
            lines.append(
                f"  {retailer:12} rendered={counts['rendered']} "
                f"blocked={counts['blocked']} error={counts['error']} "
                f"extractable={counts['extractable']}"
            )
        return "\n".join(lines)


class FeasibilitySpike:
    """Run one polite request per target and classify what came back."""

    def __init__(
        self,
        fetcher: SupplierFetcher,
        *,
        extractors: Mapping[str, ProductExtractor],
        timeout_seconds: int = 20,
        user_agent: str = "BasketGuardResearchBot/0.1 (+contact)",
    ) -> None:
        self.fetcher = fetcher
        self.extractors = extractors
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent

    def run(self, targets: Sequence[SpikeTarget]) -> SpikeReport:
        if len(targets) > MAX_SPIKE_TARGETS:
            raise ValueError(
                f"Spike refuses more than {MAX_SPIKE_TARGETS} targets at once "
                f"(got {len(targets)})."
            )
        return SpikeReport(attempts=[self._attempt(target) for target in targets])

    def _attempt(self, target: SpikeTarget) -> SpikeAttempt:
        try:
            response = self.fetcher.fetch(
                target.url,
                timeout_seconds=self.timeout_seconds,
                user_agent=self.user_agent,
            )
        except FetchHttpStatusError as error:
            # 403/429 are anti-bot status codes; treat as a block, not noise.
            outcome: SpikeOutcome = "blocked" if error.status_code in (403, 429) else "error"
            return SpikeAttempt(
                retailer=target.retailer,
                url=target.url,
                outcome=outcome,
                status_code=error.status_code,
                block_signal=f"http_{error.status_code}" if outcome == "blocked" else None,
                error_code=error.error_code,
                error_message=str(error)[:300],
            )
        except FetchError as error:
            return SpikeAttempt(
                retailer=target.retailer,
                url=target.url,
                outcome="error",
                error_code=error.error_code,
                error_message=str(error)[:300],
            )

        return self._classify_response(target, response)

    def _classify_response(
        self, target: SpikeTarget, response: FetchResponse
    ) -> SpikeAttempt:
        block_signal = detect_block_signal(response.body, response.status_code)
        if block_signal is not None:
            return SpikeAttempt(
                retailer=target.retailer,
                url=target.url,
                outcome="blocked",
                status_code=response.status_code,
                block_signal=block_signal,
                content_length=len(response.body),
            )

        title = price = None
        extractor = self.extractors.get(target.retailer)
        if extractor is not None:
            extracted = extractor.extract(response.body, target.url)
            title = extracted.title
            price = extracted.price
        return SpikeAttempt(
            retailer=target.retailer,
            url=target.url,
            outcome="rendered",
            status_code=response.status_code,
            content_length=len(response.body),
            extracted_title=title,
            extracted_price=price,
        )
