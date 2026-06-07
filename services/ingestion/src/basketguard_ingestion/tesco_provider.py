from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from basketguard_product_normalisation import (
    UnitNormalisationError,
    classify_product_flags,
    normalise_pack_size,
    parse_pack_size,
)

from .contracts import (
    IngestionJobResult,
    ParsedProduct,
    PriceObservation,
    RawProductSnapshot,
)


TESCO_FEATURE_FLAG = "BASKETGUARD_ENABLE_TESCO_SCRAPER"
TESCO_PARSER_VERSION = "tesco-html-v1"


class TescoParseError(ValueError):
    pass


@dataclass(frozen=True)
class TescoScraperConfig:
    allowlisted_urls: tuple[str, ...]
    enabled: bool = False
    postcode_context: str | None = "MVP default region"
    request_delay_seconds: Decimal = Decimal("1.0")
    timeout_seconds: int = 15
    user_agent: str = "BasketGuardResearchBot/0.1"


class TescoProductPageParser:
    """Parse saved Tesco product HTML into BasketGuard ingestion records."""

    retailer = "Tesco"

    def parse(
        self,
        html: str,
        url: str | None,
        collected_at: str,
        postcode_context: str | None = None,
    ) -> tuple[RawProductSnapshot, ParsedProduct, PriceObservation]:
        document = _DataTestIdParser()
        document.feed(html)

        json_ld_product = _extract_json_ld_product(document.json_ld_payloads)
        name = (
            _first_text(document.data_text, "product-title", "product-name", "title")
            or json_ld_product.get("name")
            or _meta(document.meta, "og:title")
        )
        if not name:
            raise TescoParseError("Missing product title")

        external_product_id = _external_product_id(url, html)
        shelf_price_text = (
            _first_text(document.data_text, "price", "product-price", "current-price")
            or _json_ld_price(json_ld_product)
        )
        shelf_price = _parse_money(shelf_price_text)

        loyalty_price_text = _first_text(
            document.data_text,
            "clubcard-price",
            "loyalty-price",
            "member-price",
        )
        loyalty_price = _parse_money(loyalty_price_text) if loyalty_price_text else None
        effective_price = loyalty_price or shelf_price

        unit_price_text = _first_text(document.data_text, "unit-price", "price-per-unit")
        unit_price, unit_price_basis = _parse_unit_price(unit_price_text)

        promotion_text = _first_text(
            document.data_text,
            "promotion-text",
            "promo-text",
            "offer-text",
        )
        breadcrumb = _first_text(document.data_text, "breadcrumb", "breadcrumbs")
        availability = _availability(json_ld_product, document.data_text)
        raw_pack_size_text = _pack_size_text(name)
        pack_size = parse_pack_size(name)
        normalised_size = normalise_pack_size(name)
        flags = classify_product_flags(name, retailer=self.retailer)

        raw_snapshot = RawProductSnapshot(
            retailer=self.retailer,
            external_product_id=external_product_id,
            url=url,
            raw_title=name,
            raw_price_text=shelf_price_text or "",
            raw_unit_price_text=unit_price_text or "",
            raw_promo_text=promotion_text,
            raw_pack_size_text=raw_pack_size_text,
            postcode_context=postcode_context,
            collection_status="succeeded",
            parser_version=TESCO_PARSER_VERSION,
            collected_at=collected_at,
        )

        parsed_product = ParsedProduct(
            retailer=self.retailer,
            external_product_id=external_product_id,
            url=url,
            canonical_name=name,
            brand=self.retailer if flags.is_own_brand else None,
            category=_category_from_breadcrumb(breadcrumb),
            subcategory=breadcrumb,
            product_type=name,
            pack_size_value=pack_size.amount,
            pack_size_unit=pack_size.unit,
            normalised_size_value=normalised_size.value,
            normalised_size_unit=normalised_size.unit_basis,
            unit_basis=normalised_size.unit_basis,
            tier=flags.tier,
            is_own_brand=flags.is_own_brand,
            is_premium=flags.is_premium,
            is_value_range=flags.is_value_range,
            is_organic=flags.is_organic,
            is_multipack=flags.is_multipack,
        )

        price_observation = PriceObservation(
            retailer=self.retailer,
            external_product_id=external_product_id,
            shelf_price=shelf_price,
            loyalty_price=loyalty_price,
            was_price=None,
            effective_price=effective_price,
            unit_price=unit_price,
            unit_price_basis=unit_price_basis,
            promo_type="loyalty" if loyalty_price is not None else None,
            promo_description=promotion_text,
            availability=availability,
            postcode_context=postcode_context,
            collected_at=collected_at,
        )

        return raw_snapshot, parsed_product, price_observation


class TescoIngestionProvider:
    provider_name = "tesco"

    def __init__(self, config: TescoScraperConfig) -> None:
        self.config = config
        self.parser = TescoProductPageParser()

    def collect(self) -> IngestionJobResult:
        if not self._enabled():
            return IngestionJobResult(
                provider_name=self.provider_name,
                job_type="tesco_allowlisted_product_collection",
                status="failed",
                retailer="Tesco",
                target_count=len(self.config.allowlisted_urls),
                collected_count=0,
                parser_error_count=0,
                missing_price_count=0,
                notes=(
                    f"Tesco live scraping is disabled. Set {TESCO_FEATURE_FLAG}=1 "
                    "and provide explicit allowlisted URLs to run it."
                ),
            )

        raw_snapshots: list[RawProductSnapshot] = []
        parsed_products: list[ParsedProduct] = []
        price_observations: list[PriceObservation] = []
        parser_error_count = 0
        missing_price_count = 0

        for index, url in enumerate(self.config.allowlisted_urls):
            if index > 0:
                time.sleep(float(self.config.request_delay_seconds))

            collected_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            try:
                html = self._fetch(url)
                raw_snapshot, parsed_product, price_observation = self.parser.parse(
                    html=html,
                    url=url,
                    collected_at=collected_at,
                    postcode_context=self.config.postcode_context,
                )
                raw_snapshots.append(raw_snapshot)
                parsed_products.append(parsed_product)
                price_observations.append(price_observation)
            except (HTTPError, URLError, TimeoutError, TescoParseError, UnitNormalisationError, ValueError):
                parser_error_count += 1
                missing_price_count += 1

        status = "succeeded"
        if parser_error_count and price_observations:
            status = "partial"
        elif parser_error_count:
            status = "failed"

        return IngestionJobResult(
            provider_name=self.provider_name,
            job_type="tesco_allowlisted_product_collection",
            status=status,
            retailer="Tesco",
            target_count=len(self.config.allowlisted_urls),
            collected_count=len(price_observations),
            parser_error_count=parser_error_count,
            missing_price_count=missing_price_count,
            raw_snapshots=raw_snapshots,
            parsed_products=parsed_products,
            price_observations=price_observations,
            notes="Live Tesco collection ran against explicit allowlisted URLs.",
        )

    def _enabled(self) -> bool:
        return self.config.enabled and os.environ.get(TESCO_FEATURE_FLAG) == "1"

    def _fetch(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": self.config.user_agent})
        with urlopen(request, timeout=self.config.timeout_seconds) as response:
            return response.read().decode("utf-8", errors="replace")


class _DataTestIdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.data_text: dict[str, list[str]] = {}
        self.meta: dict[str, str] = {}
        self.json_ld_payloads: list[str] = []
        self._active_data_key: str | None = None
        self._active_script_type: str | None = None
        self._script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value or "" for key, value in attrs}
        if "data-testid" in attr_map:
            self._active_data_key = attr_map["data-testid"]
        if tag.lower() == "meta":
            key = attr_map.get("property") or attr_map.get("name")
            content = attr_map.get("content")
            if key and content:
                self.meta[key] = content
        if tag.lower() == "script":
            self._active_script_type = attr_map.get("type")
            self._script_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._active_script_type == "application/ld+json":
            self.json_ld_payloads.append("".join(self._script_parts))
        if tag.lower() == "script":
            self._active_script_type = None
            self._script_parts = []
        self._active_data_key = None

    def handle_data(self, data: str) -> None:
        text = " ".join(unescape(data).split())
        if not text:
            return
        if self._active_script_type == "application/ld+json":
            self._script_parts.append(data)
        if self._active_data_key:
            self.data_text.setdefault(self._active_data_key, []).append(text)


def _first_text(data_text: dict[str, list[str]], *keys: str) -> str | None:
    for key in keys:
        values = data_text.get(key)
        if values:
            return " ".join(values)
    return None


def _meta(meta: dict[str, str], key: str) -> str | None:
    return meta.get(key)


def _extract_json_ld_product(payloads: list[str]) -> dict[str, Any]:
    for payload in payloads:
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue
        products = _find_json_ld_products(parsed)
        if products:
            return products[0]
    return {}


def _find_json_ld_products(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        if value.get("@type") == "Product":
            return [value]
        products = []
        for child in value.values():
            products.extend(_find_json_ld_products(child))
        return products
    if isinstance(value, list):
        products = []
        for item in value:
            products.extend(_find_json_ld_products(item))
        return products
    return []


def _json_ld_price(product: dict[str, Any]) -> str | None:
    offers = product.get("offers")
    if isinstance(offers, dict) and offers.get("price") is not None:
        return str(offers["price"])
    return None


def _availability(product: dict[str, Any], data_text: dict[str, list[str]]) -> str:
    availability_text = str(product.get("offers", {}).get("availability", "")).lower()
    page_text = " ".join(" ".join(values) for values in data_text.values()).lower()
    if "outofstock" in availability_text or "out of stock" in page_text:
        return "out_of_stock"
    if availability_text or "in stock" in page_text:
        return "in_stock"
    return "unknown"


def _parse_money(text: str | None) -> Decimal:
    if not text:
        raise TescoParseError("Missing money value")
    compact = text.replace(",", "").strip()
    pound_match = re.search(r"(?:GBP|£)\s*(\d+(?:\.\d+)?)", compact, re.IGNORECASE)
    if pound_match:
        return Decimal(pound_match.group(1))
    pence_match = re.search(r"\b(\d+(?:\.\d+)?)\s*p\b", compact, re.IGNORECASE)
    if pence_match:
        return (Decimal(pence_match.group(1)) / Decimal("100")).quantize(Decimal("0.01"))
    number_match = re.search(r"\b(\d+(?:\.\d+)?)\b", compact)
    if number_match:
        return Decimal(number_match.group(1))
    raise TescoParseError(f"Could not parse money value: {text!r}")


def _parse_unit_price(text: str | None) -> tuple[Decimal, str]:
    if not text:
        raise TescoParseError("Missing unit price")
    match = re.search(
        r"((?:GBP|£)?\s*\d+(?:\.\d+)?\s*p?)\s*/\s*(100g|kg|g|litre|l|each|roll|wash|tablet)",
        text,
        re.IGNORECASE,
    )
    if not match:
        raise TescoParseError(f"Could not parse unit price: {text!r}")
    return _parse_money(match.group(1)), _normalise_unit_basis(match.group(2))


def _normalise_unit_basis(unit: str) -> str:
    unit_key = unit.lower()
    if unit_key == "l":
        return "litre"
    return unit_key


def _pack_size_text(name: str) -> str | None:
    try:
        parsed = parse_pack_size(name)
    except UnitNormalisationError:
        return None
    return f"{parsed.amount}{parsed.unit}"


def _category_from_breadcrumb(breadcrumb: str | None) -> str | None:
    if not breadcrumb:
        return None
    return breadcrumb.split(">")[0].strip()


def _external_product_id(url: str | None, html: str) -> str | None:
    if url:
        product_match = re.search(r"/products/(\d+)", url)
        if product_match:
            return product_match.group(1)
    id_match = re.search(r'"productId"\s*:\s*"?(?P<id>\d+)"?', html)
    if id_match:
        return id_match.group("id")
    return None
