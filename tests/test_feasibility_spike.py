from __future__ import annotations

import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))

from basketguard_ingestion import (  # noqa: E402
    FeasibilitySpike,
    FetchHttpStatusError,
    FetchResponse,
    FetchTimeoutError,
    LIVE_SPIKE_FEATURE_FLAG,
    MAX_SPIKE_TARGETS,
    SpikeNotAuthorisedError,
    SpikeTargetCapError,
    detect_block_signal,
    run_feasibility_spike,
)
from basketguard_ingestion.contracts import CollectionTarget, ExtractedProduct  # noqa: E402
from basketguard_ingestion.feasibility_spike import main  # noqa: E402


def _target(retailer: str, url: str) -> CollectionTarget:
    return CollectionTarget(retailer=retailer, target_name=f"{retailer} item", target_url=url)


class _MappedFetcher:
    """SupplierFetcher that returns a canned response/exception per URL."""

    def __init__(self, responses: dict[str, object]) -> None:
        self._responses = responses
        self.calls: list[str] = []

    def fetch(self, url: str, *, timeout_seconds: int, user_agent: str) -> FetchResponse:
        self.calls.append(url)
        outcome = self._responses[url]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome  # type: ignore[return-value]


class _StubExtractor:
    retailer = "Stub"

    def __init__(self, *, title: str | None, price: str | None) -> None:
        self._title = title
        self._price = price

    def extract(self, html: str, url: str | None) -> ExtractedProduct:
        return ExtractedProduct(
            retailer=self.retailer,
            source_url=url,
            title=self._title,
            brand=None,
            price=self._price,
            currency="GBP" if self._price else None,
            unit_price_text=None,
            pack_size_text=None,
            category_breadcrumb=None,
            image_url=None,
            availability="unknown",
            promotion_text=None,
            external_product_id=None,
        )


def _ok(url: str, body: str = "<html>ok</html>") -> FetchResponse:
    return FetchResponse(url=url, status_code=200, body=body, headers={})


class DetectBlockSignalTests(unittest.TestCase):
    def test_detects_known_signature_case_insensitively(self) -> None:
        self.assertEqual(detect_block_signal("Please solve the CAPTCHA"), "captcha")
        self.assertEqual(detect_block_signal("Just a moment..."), "just a moment...")

    def test_clean_page_returns_none(self) -> None:
        self.assertIsNone(detect_block_signal("<html>Cornflakes 500g £1.50</html>"))
        self.assertIsNone(detect_block_signal(None))


class FeasibilitySpikeRunTests(unittest.TestCase):
    def test_rendered_page_with_title_and_price_is_extractable(self) -> None:
        url = "https://shop.example/p/1"
        fetcher = _MappedFetcher({url: _ok(url, "<html>real product</html>")})
        spike = FeasibilitySpike(
            fetcher,
            extractors={"tesco": _StubExtractor(title="Cornflakes 500g", price="£1.50")},
            sleep=lambda _seconds: None,
        )

        report = spike.run([_target("Tesco", url)])
        result = report.results[0]

        self.assertEqual(result.outcome, "rendered")
        self.assertTrue(result.extractable)
        self.assertEqual(result.title, "Cornflakes 500g")
        self.assertEqual(result.price, "£1.50")
        self.assertEqual(report.extractable_count, 1)
        self.assertEqual(report.block_rate, 0)

    def test_rendered_without_price_is_not_extractable(self) -> None:
        url = "https://shop.example/p/2"
        fetcher = _MappedFetcher({url: _ok(url)})
        spike = FeasibilitySpike(
            fetcher,
            extractors={"tesco": _StubExtractor(title="Has title", price=None)},
            sleep=lambda _seconds: None,
        )

        result = spike.run([_target("Tesco", url)]).results[0]

        self.assertEqual(result.outcome, "rendered")
        self.assertFalse(result.extractable)
        self.assertIn("price", result.detail or "")

    def test_challenge_body_on_200_is_blocked(self) -> None:
        url = "https://shop.example/p/3"
        fetcher = _MappedFetcher({url: _ok(url, "<html>Please complete the captcha</html>")})
        spike = FeasibilitySpike(fetcher, extractors={}, sleep=lambda _seconds: None)

        result = spike.run([_target("Asda", url)]).results[0]

        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.detail, "block_signal:captcha")

    def test_http_403_is_blocked(self) -> None:
        url = "https://shop.example/p/4"
        fetcher = _MappedFetcher(
            {url: FetchHttpStatusError(403, "Forbidden", body="denied")},
        )
        spike = FeasibilitySpike(fetcher, extractors={}, sleep=lambda _seconds: None)

        result = spike.run([_target("Tesco", url)]).results[0]

        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.status_code, 403)
        self.assertEqual(result.detail, "http_403")

    def test_timeout_is_error(self) -> None:
        url = "https://shop.example/p/5"
        fetcher = _MappedFetcher({url: FetchTimeoutError("render timed out")})
        spike = FeasibilitySpike(fetcher, extractors={}, sleep=lambda _seconds: None)

        result = spike.run([_target("Tesco", url)]).results[0]

        self.assertEqual(result.outcome, "error")
        self.assertEqual(result.detail, "timeout")

    def test_mixed_batch_summary_and_block_rate(self) -> None:
        urls = {
            "https://t.example/a": _ok("https://t.example/a", "good"),
            "https://t.example/b": FetchHttpStatusError(429, "Too Many Requests", body="slow"),
            "https://a.example/c": _ok("https://a.example/c", "Are you a robot?"),
            "https://a.example/d": FetchTimeoutError("timed out"),
        }
        fetcher = _MappedFetcher(urls)
        spike = FeasibilitySpike(
            fetcher,
            extractors={"tesco": _StubExtractor(title="T", price="£2")},
            sleep=lambda _seconds: None,
        )

        report = spike.run(
            [
                _target("Tesco", "https://t.example/a"),
                _target("Tesco", "https://t.example/b"),
                _target("Asda", "https://a.example/c"),
                _target("Asda", "https://a.example/d"),
            ],
        )

        self.assertEqual(report.target_count, 4)
        self.assertEqual(report.rendered_count, 1)
        self.assertEqual(report.blocked_count, 2)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.extractable_count, 1)
        self.assertEqual(report.block_rate, Decimal("0.50"))

        summaries = {summary.retailer: summary for summary in report.retailer_summaries()}
        self.assertEqual(summaries["Tesco"].rendered, 1)
        self.assertEqual(summaries["Tesco"].blocked, 1)
        self.assertEqual(summaries["Asda"].blocked, 1)
        self.assertEqual(summaries["Asda"].error, 1)

    def test_one_request_per_target_no_retry(self) -> None:
        url = "https://shop.example/p/6"
        fetcher = _MappedFetcher({url: FetchHttpStatusError(403, "Forbidden", body="x")})
        spike = FeasibilitySpike(fetcher, extractors={}, sleep=lambda _seconds: None)

        spike.run([_target("Tesco", url)])

        self.assertEqual(fetcher.calls, [url])


class FeasibilitySpikeGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.seed = ROOT / "services" / "ingestion" / "fixtures" / "mvp_collection_targets.json"

    def _factory_that_must_not_run(self):
        def factory():
            raise AssertionError("fetcher_factory must not be called without all gates")

        return factory

    def test_all_gates_present_runs_against_seed(self) -> None:
        # The fixture has two active Tesco targets; _SeedFetcher answers any URL.
        report = run_feasibility_spike(
            seed_path=self.seed,
            live=True,
            legal_signoff=True,
            env={LIVE_SPIKE_FEATURE_FLAG: "1"},
            fetcher_factory=lambda: _SeedFetcher(),
            spike_factory=lambda f: FeasibilitySpike(f, extractors={}, sleep=lambda _s: None),
        )
        self.assertEqual(report.target_count, 2)

    def test_missing_live_flag_refuses_without_network(self) -> None:
        with self.assertRaises(SpikeNotAuthorisedError) as context:
            run_feasibility_spike(
                seed_path=self.seed,
                live=False,
                legal_signoff=True,
                env={LIVE_SPIKE_FEATURE_FLAG: "1"},
                fetcher_factory=self._factory_that_must_not_run(),
            )
        self.assertTrue(any("--live" in item for item in context.exception.missing))

    def test_missing_legal_signoff_refuses(self) -> None:
        with self.assertRaises(SpikeNotAuthorisedError) as context:
            run_feasibility_spike(
                seed_path=self.seed,
                live=True,
                legal_signoff=False,
                env={LIVE_SPIKE_FEATURE_FLAG: "1"},
                fetcher_factory=self._factory_that_must_not_run(),
            )
        self.assertTrue(any("legal-signoff" in item for item in context.exception.missing))

    def test_missing_env_flag_refuses(self) -> None:
        with self.assertRaises(SpikeNotAuthorisedError) as context:
            run_feasibility_spike(
                seed_path=self.seed,
                live=True,
                legal_signoff=True,
                env={},
                fetcher_factory=self._factory_that_must_not_run(),
            )
        self.assertTrue(any(LIVE_SPIKE_FEATURE_FLAG in item for item in context.exception.missing))

    def test_target_cap_refusal(self) -> None:
        with self.subTest("max_targets above hard cap"):
            with self.assertRaises(SpikeTargetCapError):
                run_feasibility_spike(
                    seed_path=self.seed,
                    live=True,
                    legal_signoff=True,
                    env={LIVE_SPIKE_FEATURE_FLAG: "1"},
                    max_targets=MAX_SPIKE_TARGETS + 1,
                    fetcher_factory=self._factory_that_must_not_run(),
                )

        big_seed = self._write_seed(MAX_SPIKE_TARGETS + 5)
        with self.subTest("more selected targets than cap"):
            with self.assertRaises(SpikeTargetCapError):
                run_feasibility_spike(
                    seed_path=big_seed,
                    live=True,
                    legal_signoff=True,
                    env={LIVE_SPIKE_FEATURE_FLAG: "1"},
                    fetcher_factory=self._factory_that_must_not_run(),
                )

    def _write_seed(self, count: int) -> Path:
        import tempfile

        targets = [
            {
                "retailer": "Tesco",
                "target_name": f"Item {index}",
                "target_url": f"https://www.tesco.com/groceries/en-GB/products/{index:09d}",
            }
            for index in range(count)
        ]
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8",
        )
        json.dump({"targets": targets}, handle)
        handle.close()
        return Path(handle.name)


class _SeedFetcher:
    def fetch(self, url: str, *, timeout_seconds: int, user_agent: str) -> FetchResponse:
        return FetchResponse(url=url, status_code=200, body="<html>seed</html>", headers={})


class FeasibilitySpikeCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.seed = str(ROOT / "services" / "ingestion" / "fixtures" / "mvp_collection_targets.json")

    def _run(self, argv, env):
        return main(
            argv,
            env=env,
            fetcher_factory=self._must_not_run,
            spike_factory=lambda f: FeasibilitySpike(f, extractors={}, sleep=lambda _s: None),
        )

    @staticmethod
    def _must_not_run():
        raise AssertionError("fetcher_factory must not be called without all gates")

    def test_cli_refuses_without_live(self) -> None:
        code = self._run(["--allowlist-seed", self.seed, "--i-have-legal-signoff"], {LIVE_SPIKE_FEATURE_FLAG: "1"})
        self.assertEqual(code, 2)

    def test_cli_refuses_without_legal_signoff(self) -> None:
        code = self._run(["--allowlist-seed", self.seed, "--live"], {LIVE_SPIKE_FEATURE_FLAG: "1"})
        self.assertEqual(code, 2)

    def test_cli_refuses_without_env_flag(self) -> None:
        code = self._run(
            ["--allowlist-seed", self.seed, "--live", "--i-have-legal-signoff"],
            {},
        )
        self.assertEqual(code, 2)

    def test_cli_runs_with_all_gates(self) -> None:
        code = main(
            ["--allowlist-seed", self.seed, "--live", "--i-have-legal-signoff"],
            env={LIVE_SPIKE_FEATURE_FLAG: "1"},
            fetcher_factory=lambda: _SeedFetcher(),
            spike_factory=lambda f: FeasibilitySpike(f, extractors={}, sleep=lambda _s: None),
        )
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
