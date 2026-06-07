from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal


CollectionStatus = Literal["succeeded", "failed", "skipped"]
Availability = Literal["in_stock", "out_of_stock", "unknown"]
JobStatus = Literal["succeeded", "failed", "partial"]


@dataclass(frozen=True)
class RawProductSnapshot:
    retailer: str
    external_product_id: str | None
    url: str | None
    raw_title: str
    raw_price_text: str
    raw_unit_price_text: str
    raw_promo_text: str | None
    raw_pack_size_text: str | None
    postcode_context: str | None
    collection_status: CollectionStatus
    parser_version: str
    collected_at: str


@dataclass(frozen=True)
class ParsedProduct:
    retailer: str
    external_product_id: str | None
    url: str | None
    canonical_name: str
    brand: str | None
    category: str | None
    subcategory: str | None
    product_type: str | None
    pack_size_value: Decimal
    pack_size_unit: str
    normalised_size_value: Decimal
    normalised_size_unit: str
    unit_basis: str
    tier: str | None
    is_own_brand: bool
    is_premium: bool
    is_value_range: bool
    is_organic: bool
    is_multipack: bool


@dataclass(frozen=True)
class PriceObservation:
    retailer: str
    external_product_id: str | None
    shelf_price: Decimal
    loyalty_price: Decimal | None
    was_price: Decimal | None
    effective_price: Decimal
    unit_price: Decimal
    unit_price_basis: str
    promo_type: str | None
    promo_description: str | None
    availability: Availability
    postcode_context: str | None
    collected_at: str


@dataclass(frozen=True)
class IngestionJobResult:
    provider_name: str
    job_type: str
    status: JobStatus
    retailer: str | None
    target_count: int
    collected_count: int
    parser_error_count: int
    missing_price_count: int
    raw_snapshots: list[RawProductSnapshot] = field(default_factory=list)
    parsed_products: list[ParsedProduct] = field(default_factory=list)
    price_observations: list[PriceObservation] = field(default_factory=list)
    notes: str | None = None

    @property
    def success_rate(self) -> Decimal:
        if self.target_count == 0:
            return Decimal("0")
        return Decimal(self.collected_count) / Decimal(self.target_count)
