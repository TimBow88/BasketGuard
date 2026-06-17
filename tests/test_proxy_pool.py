from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ingestion" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "product-normalisation" / "src"))

from basketguard_ingestion import ProxyEndpoint, ProxyPool, ProxyPoolError  # noqa: E402


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now


def _pool(clock: FakeClock, **kwargs) -> ProxyPool:
    return ProxyPool(
        endpoints=[
            ProxyEndpoint(server="http://uk-1:8080", country="GB"),
            ProxyEndpoint(server="http://uk-2:8080", country="GB"),
        ],
        clock=clock.monotonic,
        **kwargs,
    )


class ProxyEndpointTests(unittest.TestCase):
    def test_as_config_includes_credentials_when_present(self) -> None:
        endpoint = ProxyEndpoint(server="http://uk:8080", username="u", password="p")
        self.assertEqual(
            endpoint.as_config(),
            {"server": "http://uk:8080", "username": "u", "password": "p"},
        )

    def test_as_config_omits_absent_credentials(self) -> None:
        self.assertEqual(ProxyEndpoint(server="http://uk:8080").as_config(), {"server": "http://uk:8080"})


class ProxyPoolTests(unittest.TestCase):
    def test_filters_to_required_country(self) -> None:
        clock = FakeClock()
        pool = ProxyPool(
            endpoints=[
                ProxyEndpoint(server="http://uk:8080", country="GB"),
                ProxyEndpoint(server="http://us:8080", country="US"),
            ],
            clock=clock.monotonic,
        )
        self.assertEqual(pool.available_count(), 1)
        self.assertEqual(pool.acquire().server, "http://uk:8080")

    def test_no_matching_country_raises(self) -> None:
        with self.assertRaises(ProxyPoolError):
            ProxyPool(endpoints=[ProxyEndpoint(server="http://us:8080", country="US")])

    def test_round_robin_rotation(self) -> None:
        clock = FakeClock()
        pool = _pool(clock)
        self.assertEqual(pool.acquire().server, "http://uk-1:8080")
        self.assertEqual(pool.acquire().server, "http://uk-2:8080")
        self.assertEqual(pool.acquire().server, "http://uk-1:8080")

    def test_quarantine_after_threshold_then_cooldown_restore(self) -> None:
        clock = FakeClock()
        pool = _pool(clock, failure_threshold=2, cooldown_seconds=100.0)

        first = pool.acquire()  # uk-1
        pool.report_failure(first)
        pool.report_failure(first)  # crosses threshold → quarantined

        self.assertEqual(pool.available_count(), 1)
        # Only the healthy endpoint is handed out while uk-1 is quarantined.
        self.assertEqual(pool.acquire().server, "http://uk-2:8080")
        self.assertEqual(pool.acquire().server, "http://uk-2:8080")

        clock.now = 100.0  # cooldown elapses
        self.assertEqual(pool.available_count(), 2)

    def test_success_resets_failure_count(self) -> None:
        clock = FakeClock()
        pool = _pool(clock, failure_threshold=2)

        endpoint = pool.endpoints[0]
        pool.report_failure(endpoint)
        pool.report_success(endpoint)
        pool.report_failure(endpoint)

        # One failure short of threshold after the reset, so still available.
        self.assertEqual(pool.available_count(), 2)

    def test_all_quarantined_raises(self) -> None:
        clock = FakeClock()
        pool = _pool(clock, failure_threshold=1, cooldown_seconds=100.0)
        for endpoint in list(pool.endpoints):
            pool.report_failure(endpoint)
        with self.assertRaises(ProxyPoolError):
            pool.acquire()


if __name__ == "__main__":
    unittest.main()
