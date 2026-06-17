from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))

from basketguard_ingestion import (  # noqa: E402
    FeasibilitySpike,
    FetchHttpStatusError,
    FetchResponse,
    FetchTimeoutError,
    MAX_SPIKE_TARGETS,
    SpikeTarget,
    TescoProductPageParser,
)
from basketguard_ingestion.run_feasibility_spike import main as spike_main  # noqa: E402


REAL_FIXTURE = (
    ROOT / "services" / "ingestion" / "fixtures" / "tesco_clubcard_cornflakes.html"
)
CHALLENGE_HTML = "<html><body>Please verify you are human. cf-browser-verification</body></html>"


class MappedFetcher:
    """Returns a scripted FetchResponse/exception per URL — no network."""

    def __init__(self, by_url: dict) -> None:
        self.by_url = by_url
        self.calls: list[str] = []

    def fetch(self, url: str, *, timeout_seconds: int, user_agent: str) -> FetchResponse:
        self.calls.append(url)
        outcome = self.by_url[url]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FeasibilitySpikeTests(unittest.TestCase):
    def _spike(self, by_url: dict) -> FeasibilitySpike:
        return FeasibilitySpike(
            MappedFetcher(by_url),
            extractors={"Tesco": TescoProductPageParser()},
        )

    def test_rendered_page_is_extractable(self) -> None:
        html = REAL_FIXTURE.read_text(encoding="utf-8")
        spike = self._spike({"https://t/ok": FetchResponse("https://t/ok", 200, html)})

        report = spike.run([SpikeTarget("Tesco", "https://t/ok")])
        attempt = report.attempts[0]

        self.assertEqual(attempt.outcome, "rendered")
        self.assertTrue(attempt.extractable)
        self.assertIsNotNone(attempt.extracted_title)
        self.assertEqual(report.block_rate, 0.0)

    def test_challenge_body_is_blocked(self) -> None:
        spike = self._spike({"https://t/c": FetchResponse("https://t/c", 200, CHALLENGE_HTML)})

        report = spike.run([SpikeTarget("Tesco", "https://t/c")])

        self.assertEqual(report.attempts[0].outcome, "blocked")
        self.assertEqual(report.attempts[0].block_signal, "cf-browser-verification")
        self.assertEqual(report.block_rate, 1.0)

    def test_403_status_is_blocked_not_error(self) -> None:
        spike = self._spike({"https://t/403": FetchHttpStatusError(403, "Forbidden")})

        report = spike.run([SpikeTarget("Tesco", "https://t/403")])

        self.assertEqual(report.attempts[0].outcome, "blocked")
        self.assertEqual(report.attempts[0].block_signal, "http_403")

    def test_timeout_is_error(self) -> None:
        spike = self._spike({"https://t/slow": FetchTimeoutError("timed out")})

        report = spike.run([SpikeTarget("Tesco", "https://t/slow")])

        self.assertEqual(report.attempts[0].outcome, "error")
        self.assertEqual(report.attempts[0].error_code, "timeout")

    def test_mixed_batch_summary(self) -> None:
        html = REAL_FIXTURE.read_text(encoding="utf-8")
        spike = self._spike(
            {
                "https://t/ok": FetchResponse("https://t/ok", 200, html),
                "https://t/c": FetchResponse("https://t/c", 200, CHALLENGE_HTML),
            }
        )
        report = spike.run(
            [SpikeTarget("Tesco", "https://t/ok"), SpikeTarget("Tesco", "https://t/c")]
        )

        self.assertEqual(report.total, 2)
        self.assertEqual(report.rendered, 1)
        self.assertEqual(report.blocked, 1)
        self.assertIn("block_rate=50%", report.format())

    def test_refuses_more_than_cap(self) -> None:
        spike = self._spike({})
        too_many = [SpikeTarget("Tesco", f"https://t/{i}") for i in range(MAX_SPIKE_TARGETS + 1)]
        with self.assertRaises(ValueError):
            spike.run(too_many)


class SpikeCliGateTests(unittest.TestCase):
    """The CLI must refuse (and touch no network) unless every gate is set."""

    SEED = str(ROOT / "services" / "ingestion" / "fixtures" / "mvp_collection_targets.json")

    def test_refuses_without_any_gates(self) -> None:
        import os

        os.environ.pop("BASKETGUARD_ENABLE_LIVE_SPIKE", None)
        code = spike_main(["--allowlist-seed", self.SEED])
        self.assertEqual(code, 2)

    def test_refuses_with_flags_but_no_env(self) -> None:
        import os

        os.environ.pop("BASKETGUARD_ENABLE_LIVE_SPIKE", None)
        code = spike_main(
            ["--allowlist-seed", self.SEED, "--live", "--i-have-legal-signoff"]
        )
        self.assertEqual(code, 2)

    def test_refuses_with_env_but_no_flags(self) -> None:
        import os

        os.environ["BASKETGUARD_ENABLE_LIVE_SPIKE"] = "1"
        try:
            code = spike_main(["--allowlist-seed", self.SEED])
        finally:
            os.environ.pop("BASKETGUARD_ENABLE_LIVE_SPIKE", None)
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
