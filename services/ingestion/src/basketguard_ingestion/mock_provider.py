from __future__ import annotations

import json
from dataclasses import asdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from basketguard_product_normalisation import classify_product_flags

from .contracts import (
    IngestionJobResult,
    ParsedProduct,
    PriceObservation,
    RawProductSnapshot,
)


DEFAULT_PARSER_VERSION = "fixture-v1"


class FixtureIngestionProvider:
    """Fixture-backed ingestion provider for local development and tests."""

    provider_name = "fixture"

    def __init__(
        self,
        fixture_path: str | Path,
        postcode_context: str | None = "MVP default region",
    ) -> None:
        self.fixture_path = Path(fixture_path)
        self.postcode_context = postcode_context

    def collect(
        self,
        retailer: str | None = None,
        group_slug: str | None = None,
    ) -> IngestionJobResult:
        fixture = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        observations = list(_iter_observations(fixture, retailer=retailer, group_slug=group_slug))

        raw_snapshots = []
        parsed_products = []
        price_observations = []
        parser_error_count = 0
        missing_price_count = 0

        for group, observation in observations:
            try:
                raw_snapshots.append(
                    self._raw_snapshot(fixture, group, observation)
                )
                parsed_products.append(self._parsed_product(group, observation))
                price_observations.append(self._price_observation(fixture, group, observation))
            except (KeyError, ValueError):
                parser_error_count += 1

            if not observation.get("current", {}).get("price"):
                missing_price_count += 1

        status = "succeeded"
        if parser_error_count and raw_snapshots:
            status = "partial"
        elif parser_error_count:
            status = "failed"

        return IngestionJobResult(
            provider_name=self.provider_name,
            job_type="fixture_collection",
            status=status,
            retailer=retailer,
            target_count=len(observations),
            collected_count=len(price_observations),
            parser_error_count=parser_error_count,
            missing_price_count=missing_price_count,
            raw_snapshots=raw_snapshots,
            parsed_products=parsed_products,
            price_observations=price_observations,
            notes="Collected from local seed fixture; no network requests made.",
        )

    def collect_as_dicts(
        self,
        retailer: str | None = None,
        group_slug: str | None = None,
    ) -> dict[str, Any]:
        result = self.collect(retailer=retailer, group_slug=group_slug)
        return asdict(result)

    def _raw_snapshot(
        self,
        fixture: dict[str, Any],
        group: dict[str, Any],
        observation: dict[str, Any],
    ) -> RawProductSnapshot:
        price = Decimal(observation["current"]["price"])
        normalised_size = Decimal(observation["current"]["normalised_size"])
        unit_price = _unit_price(price, normalised_size)

        return RawProductSnapshot(
            retailer=observation["retailer"],
            external_product_id=_external_product_id(group["slug"], observation["retailer"]),
            url=None,
            raw_title=observation["product_name"],
            raw_price_text=f"£{price}",
            raw_unit_price_text=f"£{unit_price}/{group['unit_basis']}",
            raw_promo_text=None,
            raw_pack_size_text=str(normalised_size),
            postcode_context=self.postcode_context,
            collection_status="succeeded",
            parser_version=DEFAULT_PARSER_VERSION,
            collected_at=fixture["collected_at"],
        )

    def _parsed_product(
        self,
        group: dict[str, Any],
        observation: dict[str, Any],
    ) -> ParsedProduct:
        retailer = observation["retailer"]
        current = observation["current"]
        flags = classify_product_flags(observation["product_name"], retailer=retailer)
        normalised_size = Decimal(current["normalised_size"])

        return ParsedProduct(
            retailer=retailer,
            external_product_id=_external_product_id(group["slug"], retailer),
            url=None,
            canonical_name=observation["product_name"],
            brand=retailer,
            category=_category_for_group(group["slug"]),
            subcategory=group["display_name"],
            product_type=group["display_name"],
            pack_size_value=normalised_size,
            pack_size_unit=group["unit_basis"],
            normalised_size_value=normalised_size,
            normalised_size_unit=group["unit_basis"],
            unit_basis=group["unit_basis"],
            tier=flags.tier,
            is_own_brand=flags.is_own_brand,
            is_premium=flags.is_premium,
            is_value_range=flags.is_value_range,
            is_organic=flags.is_organic,
            is_multipack=flags.is_multipack,
        )

    def _price_observation(
        self,
        fixture: dict[str, Any],
        group: dict[str, Any],
        observation: dict[str, Any],
    ) -> PriceObservation:
        current = observation["current"]
        shelf_price = Decimal(current["price"])
        normalised_size = Decimal(current["normalised_size"])

        return PriceObservation(
            retailer=observation["retailer"],
            external_product_id=_external_product_id(group["slug"], observation["retailer"]),
            shelf_price=shelf_price,
            loyalty_price=None,
            was_price=None,
            effective_price=shelf_price,
            unit_price=_unit_price(shelf_price, normalised_size),
            unit_price_basis=_unit_basis_from_observation(observation),
            promo_type=None,
            promo_description=None,
            availability="in_stock",
            postcode_context=self.postcode_context,
            collected_at=fixture["collected_at"],
        )


def _iter_observations(
    fixture: dict[str, Any],
    retailer: str | None,
    group_slug: str | None,
):
    for group in fixture["groups"]:
        if group_slug and group["slug"] != group_slug:
            continue
        for observation in group["observations"]:
            if retailer and observation["retailer"].lower() != retailer.lower():
                continue
            yield group, observation


def _unit_price(price: Decimal, normalised_size: Decimal) -> Decimal:
    return (price / normalised_size).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP).normalize()


def _external_product_id(group_slug: str, retailer: str) -> str:
    return f"fixture:{retailer.lower().replace(' ', '_')}:{group_slug}"


def _unit_basis_from_observation(observation: dict[str, Any]) -> str:
    product_name = observation["product_name"].lower()
    if "milk" in product_name:
        return "litre"
    if "roll" in product_name:
        return "roll"
    if "wash" in product_name or "capsule" in product_name:
        return "wash"
    if "tablet" in product_name:
        return "tablet"
    return "kg"


def _category_for_group(group_slug: str) -> str:
    if any(token in group_slug for token in ("washing", "dishwasher", "toilet")):
        return "Household"
    return "Food cupboard"
