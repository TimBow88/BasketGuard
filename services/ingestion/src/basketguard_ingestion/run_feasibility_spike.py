"""Gated CLI for the live feasibility spike.

This is the ONLY place that turns the spike into live network requests, and it
refuses unless all three gates are satisfied:

    BASKETGUARD_ENABLE_LIVE_SPIKE=1 \
    python -m basketguard_ingestion.run_feasibility_spike \
        --allowlist-seed services/ingestion/fixtures/mvp_collection_targets.json \
        --max-targets 8 --live --i-have-legal-signoff

Without ``--live`` AND ``--i-have-legal-signoff`` AND the env flag, it prints
what is missing and exits without touching the network. Run it only after the
BAS-26 / BAS-46 data-source and legal review is cleared.
"""

from __future__ import annotations

import os
import sys
from typing import Sequence

from .asda_provider import AsdaProductPageParser
from .feasibility_spike import FeasibilitySpike, MAX_SPIKE_TARGETS, SpikeTarget
from .morrisons_provider import MorrisonsProductPageParser
from .sainsburys_provider import SainsburysProductPageParser
from .seed_loader import load_collection_targets
from .tesco_provider import TescoProductPageParser


LIVE_SPIKE_ENV = "BASKETGUARD_ENABLE_LIVE_SPIKE"

EXTRACTORS = {
    "Tesco": TescoProductPageParser(),
    "Asda": AsdaProductPageParser(),
    "Sainsbury's": SainsburysProductPageParser(),
    "Morrisons": MorrisonsProductPageParser(),
}


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run the gated live feasibility spike.")
    parser.add_argument("--allowlist-seed", required=True)
    parser.add_argument("--retailer", default=None, help="Optional retailer filter.")
    parser.add_argument("--max-targets", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--i-have-legal-signoff", action="store_true")
    args = parser.parse_args(argv)

    missing = _missing_gates(args)
    if missing:
        print("REFUSING to run the live spike. Missing gate(s):")
        for item in missing:
            print(f"  - {item}")
        print(
            "\nThis spike makes live requests to real retailers. Run it only "
            "after the BAS-26 / BAS-46 data-source and legal review is cleared."
        )
        return 2

    if args.max_targets > MAX_SPIKE_TARGETS:
        parser.error(f"--max-targets cannot exceed {MAX_SPIKE_TARGETS}.")

    targets = _load_targets(args.allowlist_seed, args.retailer, args.max_targets)
    if not targets:
        print("No active allowlisted targets matched; nothing to do.")
        return 0

    fetcher = _build_live_fetcher()
    report = FeasibilitySpike(
        fetcher,
        extractors=EXTRACTORS,
        timeout_seconds=args.timeout,
    ).run(targets)
    print(report.format())
    # Non-zero exit if every target was blocked, so CI/automation can react.
    return 1 if report.total and report.blocked == report.total else 0


def _missing_gates(args) -> list[str]:
    missing: list[str] = []
    if not args.live:
        missing.append("--live flag")
    if not args.i_have_legal_signoff:
        missing.append("--i-have-legal-signoff flag (BAS-26 / BAS-46 cleared)")
    if os.environ.get(LIVE_SPIKE_ENV) != "1":
        missing.append(f"{LIVE_SPIKE_ENV}=1 environment variable")
    return missing


def _load_targets(seed_path: str, retailer: str | None, max_targets: int) -> list[SpikeTarget]:
    targets = []
    for target in load_collection_targets(seed_path):
        if not target.is_active or not target.target_url:
            continue
        if retailer and target.retailer.lower() != retailer.lower():
            continue
        targets.append(SpikeTarget(retailer=target.retailer, url=target.target_url))
    return targets[:max_targets]


def _build_live_fetcher():  # pragma: no cover - only reachable once gates pass
    # Imported lazily so the module loads (and tests run) without basketguard_shared.
    from basketguard_shared import Settings  # type: ignore[import-not-found]

    from .live_fetcher import build_live_fetcher

    return build_live_fetcher(Settings.from_env())


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
