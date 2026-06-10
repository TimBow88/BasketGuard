from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal, Mapping, Protocol


CollectionStatus = Literal["succeeded", "failed", "skipped"]
Availability = Literal["in_stock", "out_of_stock", "unknown"]
JobStatus = Literal["succeeded", "failed", "partial"]
CollectionFrequency = Literal["daily", "twice_weekly", "weekly", "monthly", "manual"]


@dataclass(frozen=True)
class ExtractedProduct:
    """Retailer-neutral extraction output shared by all product page parsers.

    Fields hold raw page text; normalisation happens downstream. `raw_fields`
    preserves the retailer-specific selector values so retailer parsers can
    keep retailer-only concepts (for example Tesco Clubcard prices) without
    widening this contract.
    """

    retailer: str
    source_url: str | None
    title: str | None
    brand: str | None
    price: str | None
    currency: str | None
    unit_price_text: str | None
    pack_size_text: str | None
    category_breadcrumb: str | None
    image_url: str | None
    availability: Availability
    promotion_text: str | None
    external_product_id: str | None
    raw_fields: Mapping[str, str] = field(default_factory=dict)

    @property
    def missing_fields(self) -> tuple[str, ...]:
        checks = (
            ("title", self.title),
            ("price", self.price),
            ("unit_price_text", self.unit_price_text),
            ("category_breadcrumb", self.category_breadcrumb),
            ("image_url", self.image_url),
        )
        return tuple(name for name, value in checks if not value)


class ProductExtractor(Protocol):
    """Extracts the shared product contract from one retailer's page HTML."""

    retailer: str

    def extract(self, html: str, url: str | None) -> ExtractedProduct: ...


@dataclass(frozen=True)
class CollectionTarget:
    retailer: str
    target_name: str
    target_url: str | None = None
    external_product_id: str | None = None
    group_slug: str | None = None
    postcode_context: str | None = None
    collection_frequency: CollectionFrequency = "daily"
    priority: int = 50
    is_active: bool = True
    notes: str | None = None


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
    raw_payload_location: str | None = None


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
class CollectionAttempt:
    retailer: str
    target_url: str | None
    external_product_id: str | None
    status: CollectionStatus
    attempted_at: str
    raw_snapshot_external_product_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


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
    collection_attempts: list[CollectionAttempt] = field(default_factory=list)
    notes: str | None = None

    @property
    def success_rate(self) -> Decimal:
        if self.target_count == 0:
            return Decimal("0")
        return Decimal(self.collected_count) / Decimal(self.target_count)
