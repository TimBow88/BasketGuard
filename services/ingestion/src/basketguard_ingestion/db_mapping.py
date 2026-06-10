from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Sequence
from uuid import NAMESPACE_URL, uuid5

from basketguard_product_normalisation import EquivalenceGroupDefinition

from .contracts import (
    CollectionAttempt,
    CollectionTarget,
    IngestionJobResult,
    ParsedProduct,
    PriceObservation,
    RawProductSnapshot,
)
from .group_matching import match_parsed_products


@dataclass(frozen=True)
class IngestionPersistencePlan:
    retailers: list[dict[str, Any]] = field(default_factory=list)
    equivalence_groups: list[dict[str, Any]] = field(default_factory=list)
    collection_targets: list[dict[str, Any]] = field(default_factory=list)
    ingestion_jobs: list[dict[str, Any]] = field(default_factory=list)
    ingestion_job_targets: list[dict[str, Any]] = field(default_factory=list)
    raw_product_snapshots: list[dict[str, Any]] = field(default_factory=list)
    products: list[dict[str, Any]] = field(default_factory=list)
    price_observations: list[dict[str, Any]] = field(default_factory=list)
    product_group_memberships: list[dict[str, Any]] = field(default_factory=list)
    # Surfaced for callers/logging only; never persisted by the repository.
    group_review_candidates: list[dict[str, Any]] = field(default_factory=list)


def build_ingestion_persistence_plan(
    result: IngestionJobResult,
    collection_targets: list[CollectionTarget] | None = None,
    group_definitions: Sequence[EquivalenceGroupDefinition] | None = None,
) -> IngestionPersistencePlan:
    targets = collection_targets or []
    retailer_names = _retailer_names(result, targets)
    retailer_rows = [_retailer_row(name) for name in retailer_names]
    retailer_ids = {row["name"]: row["id"] for row in retailer_rows}
    retailer_ids_by_slug = {row["slug"]: row["id"] for row in retailer_rows}

    equivalence_group_rows = _equivalence_group_rows(targets)
    equivalence_group_ids = {row["slug"]: row["id"] for row in equivalence_group_rows}

    collection_target_rows = [
        _collection_target_row(target, retailer_ids_by_slug, equivalence_group_ids)
        for target in targets
    ]
    target_by_external_product_id = {
        row["external_product_id"]: row
        for row in collection_target_rows
        if row.get("external_product_id")
    }
    target_by_url = {
        row["target_url"]: row
        for row in collection_target_rows
        if row.get("target_url")
    }

    job_row = _ingestion_job_row(result, retailer_ids)
    snapshot_rows = [
        _raw_product_snapshot_row(snapshot, retailer_ids)
        for snapshot in result.raw_snapshots
    ]
    snapshot_ids_by_external_product_id = {
        row["external_product_id"]: row["id"]
        for row in snapshot_rows
        if row.get("external_product_id")
    }

    product_rows = [
        _product_row(product, retailer_ids)
        for product in result.parsed_products
    ]
    product_ids_by_external_product_id = {
        row["external_product_id"]: row["id"]
        for row in product_rows
        if row.get("external_product_id")
    }

    price_rows = [
        _price_observation_row(
            observation,
            product_ids_by_external_product_id,
            snapshot_ids_by_external_product_id,
        )
        for observation in result.price_observations
    ]

    job_target_rows = _ingestion_job_target_rows(
        job_id=job_row["id"],
        target_by_external_product_id=target_by_external_product_id,
        target_by_url=target_by_url,
        snapshot_rows=snapshot_rows,
        attempts=result.collection_attempts,
    )

    membership_rows: list[dict[str, Any]] = []
    review_candidate_rows: list[dict[str, Any]] = []
    if group_definitions:
        membership_rows, review_candidate_rows = _group_membership_rows(
            result=result,
            group_definitions=group_definitions,
            equivalence_group_rows=equivalence_group_rows,
            equivalence_group_ids=equivalence_group_ids,
            product_ids_by_external_product_id=product_ids_by_external_product_id,
        )
        if review_candidate_rows:
            existing_notes = job_row["notes"] or ""
            job_row["notes"] = (
                f"{existing_notes} "
                f"needs_review_group_candidates={len(review_candidate_rows)}"
            ).strip()

    return IngestionPersistencePlan(
        retailers=retailer_rows,
        equivalence_groups=equivalence_group_rows,
        collection_targets=collection_target_rows,
        ingestion_jobs=[job_row],
        ingestion_job_targets=job_target_rows,
        raw_product_snapshots=snapshot_rows,
        products=product_rows,
        price_observations=price_rows,
        product_group_memberships=membership_rows,
        group_review_candidates=review_candidate_rows,
    )


def _group_membership_rows(
    result: IngestionJobResult,
    group_definitions: Sequence[EquivalenceGroupDefinition],
    equivalence_group_rows: list[dict[str, Any]],
    equivalence_group_ids: dict[str, str],
    product_ids_by_external_product_id: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    definitions_by_slug = {definition.slug: definition for definition in group_definitions}
    summary = match_parsed_products(result.parsed_products, group_definitions)

    best_score_by_product: dict[str, Decimal] = {}
    for match in summary.auto_matches:
        key = match.product.external_product_id or ""
        if key not in best_score_by_product or match.result.score > best_score_by_product[key]:
            best_score_by_product[key] = match.result.score

    membership_rows = []
    for match in summary.auto_matches:
        external_product_id = match.product.external_product_id or ""
        product_id = product_ids_by_external_product_id.get(external_product_id)
        if product_id is None:
            continue
        group_id = equivalence_group_ids.get(match.group_slug)
        if group_id is None:
            group_row = _equivalence_group_row_from_definition(definitions_by_slug[match.group_slug])
            equivalence_group_rows.append(group_row)
            equivalence_group_ids[match.group_slug] = group_row["id"]
            group_id = group_row["id"]
        membership_rows.append(
            {
                "id": _stable_uuid("product_group_membership", product_id, group_id),
                "product_id": product_id,
                "equivalence_group_id": group_id,
                "match_confidence": match.result.score,
                "match_reason": "; ".join(match.result.reasons),
                "is_primary_match": match.result.score
                == best_score_by_product[external_product_id],
                "human_reviewed": False,
            },
        )

    review_candidate_rows = [
        {
            "external_product_id": match.product.external_product_id,
            "canonical_name": match.product.canonical_name,
            "group_slug": match.group_slug,
            "match_confidence": match.result.score,
            "match_reason": "; ".join(match.result.reasons),
        }
        for match in summary.review_candidates
    ]
    return membership_rows, review_candidate_rows


def _equivalence_group_row_from_definition(
    definition: EquivalenceGroupDefinition,
) -> dict[str, Any]:
    return {
        "id": _stable_uuid("equivalence_group", definition.slug),
        "canonical_group_name": definition.name,
        "slug": definition.slug,
        "category": None,
        "subcategory": None,
        "product_type": None,
        "comparison_level": "definition_v1",
        "unit_basis": definition.unit_basis,
        "tier": definition.tier,
        "confidence_score": Decimal("0.9"),
        "review_status": "pending",
        "notes": "Created from equivalence group definition fixture.",
    }


def _retailer_names(
    result: IngestionJobResult,
    collection_targets: list[CollectionTarget],
) -> list[str]:
    names = set()
    if result.retailer:
        names.add(result.retailer)
    names.update(target.retailer for target in collection_targets)
    names.update(snapshot.retailer for snapshot in result.raw_snapshots)
    names.update(product.retailer for product in result.parsed_products)
    names.update(observation.retailer for observation in result.price_observations)
    return sorted(names)


def _retailer_row(name: str) -> dict[str, Any]:
    slug = _slug(name)
    return {
        "id": _stable_uuid("retailer", slug),
        "name": name,
        "slug": slug,
        "website_url": _website_url(slug),
        "supports_loyalty_price": slug == "tesco",
        "supports_online_grocery": True,
    }


def _equivalence_group_rows(collection_targets: list[CollectionTarget]) -> list[dict[str, Any]]:
    rows = {}
    for target in collection_targets:
        if not target.group_slug:
            continue
        rows[target.group_slug] = {
            "id": _stable_uuid("equivalence_group", target.group_slug),
            "canonical_group_name": _title_from_slug(target.group_slug),
            "slug": target.group_slug,
            "category": None,
            "subcategory": None,
            "product_type": None,
            "comparison_level": "mvp_seed",
            "unit_basis": None,
            "tier": None,
            "confidence_score": Decimal("0.8"),
            "review_status": "pending",
            "notes": "Created from allowlisted collection target seed.",
        }
    return [rows[key] for key in sorted(rows)]


def _collection_target_row(
    target: CollectionTarget,
    retailer_ids_by_slug: dict[str, str],
    equivalence_group_ids: dict[str, str],
) -> dict[str, Any]:
    slug = _slug(target.retailer)
    group_id = equivalence_group_ids.get(target.group_slug or "")
    return {
        "id": _stable_uuid(
            "collection_target",
            slug,
            target.target_url or "",
            target.external_product_id or "",
            target.group_slug or "",
        ),
        "retailer_id": retailer_ids_by_slug[slug],
        "equivalence_group_id": group_id,
        "external_product_id": target.external_product_id,
        "target_name": target.target_name,
        "target_url": target.target_url,
        "postcode_context": target.postcode_context,
        "collection_frequency": target.collection_frequency,
        "priority": target.priority,
        "is_active": target.is_active,
        "notes": target.notes,
    }


def _ingestion_job_row(
    result: IngestionJobResult,
    retailer_ids: dict[str, str],
) -> dict[str, Any]:
    started_at = _first_collected_at(result.raw_snapshots) or _first_attempted_at(
        result.collection_attempts,
    )
    return {
        "id": _stable_uuid(
            "ingestion_job",
            result.provider_name,
            result.job_type,
            result.retailer or "all-retailers",
            started_at or "no-observations",
            str(result.target_count),
        ),
        "retailer_id": retailer_ids.get(result.retailer or ""),
        "job_type": result.job_type,
        "status": result.status,
        "postcode_context": _first_postcode_context(result.raw_snapshots),
        "scheduled_for": None,
        "started_at": started_at,
        "finished_at": _last_collected_at(result.raw_snapshots)
        or _last_attempted_at(result.collection_attempts),
        "target_count": result.target_count,
        "collected_count": result.collected_count,
        "parser_error_count": result.parser_error_count,
        "missing_price_count": result.missing_price_count,
        "blocked_indicator": False,
        "changed_selector_warning": False,
        "notes": result.notes,
    }


def _raw_product_snapshot_row(
    snapshot: RawProductSnapshot,
    retailer_ids: dict[str, str],
) -> dict[str, Any]:
    return {
        "id": _stable_uuid(
            "raw_product_snapshot",
            snapshot.retailer,
            snapshot.external_product_id or "",
            snapshot.collected_at,
            snapshot.raw_title,
        ),
        "retailer_id": retailer_ids[snapshot.retailer],
        "external_product_id": snapshot.external_product_id,
        "url": snapshot.url,
        "raw_title": snapshot.raw_title,
        "raw_price_text": snapshot.raw_price_text,
        "raw_unit_price_text": snapshot.raw_unit_price_text,
        "raw_promo_text": snapshot.raw_promo_text,
        "raw_pack_size_text": snapshot.raw_pack_size_text,
        "raw_payload_location": snapshot.raw_payload_location,
        "postcode_context": snapshot.postcode_context,
        "collection_status": snapshot.collection_status,
        "parser_version": snapshot.parser_version,
        "collected_at": snapshot.collected_at,
    }


def _product_row(product: ParsedProduct, retailer_ids: dict[str, str]) -> dict[str, Any]:
    return {
        "id": _stable_uuid(
            "product",
            product.retailer,
            product.external_product_id or "",
            product.canonical_name,
        ),
        "retailer_id": retailer_ids[product.retailer],
        "external_product_id": product.external_product_id,
        "url": product.url,
        "canonical_name": product.canonical_name,
        "brand": product.brand,
        "brand_owner": "retailer_own_label" if product.is_own_brand else None,
        "category": product.category,
        "subcategory": product.subcategory,
        "product_type": product.product_type,
        "product_form": None,
        "flavour_variant": None,
        "pack_size_value": product.pack_size_value,
        "pack_size_unit": product.pack_size_unit,
        "normalised_size_value": product.normalised_size_value,
        "normalised_size_unit": product.normalised_size_unit,
        "unit_basis": product.unit_basis,
        "tier": product.tier,
        "is_own_brand": product.is_own_brand,
        "is_premium": product.is_premium,
        "is_value_range": product.is_value_range,
        "is_organic": product.is_organic,
        "is_multipack": product.is_multipack,
        "is_active": True,
    }


def _price_observation_row(
    observation: PriceObservation,
    product_ids_by_external_product_id: dict[str, str],
    snapshot_ids_by_external_product_id: dict[str, str],
) -> dict[str, Any]:
    external_product_id = observation.external_product_id or ""
    return {
        "id": _stable_uuid(
            "price_observation",
            observation.retailer,
            external_product_id,
            observation.collected_at,
            str(observation.effective_price),
        ),
        "product_id": product_ids_by_external_product_id[external_product_id],
        "raw_snapshot_id": snapshot_ids_by_external_product_id.get(external_product_id),
        "shelf_price": observation.shelf_price,
        "loyalty_price": observation.loyalty_price,
        "was_price": observation.was_price,
        "effective_price": observation.effective_price,
        "unit_price": observation.unit_price,
        "unit_price_basis": observation.unit_price_basis,
        "promo_type": observation.promo_type,
        "promo_description": observation.promo_description,
        "availability": observation.availability,
        "postcode_context": observation.postcode_context,
        "collected_at": observation.collected_at,
    }


def _ingestion_job_target_rows(
    job_id: str,
    target_by_external_product_id: dict[str, dict[str, Any]],
    target_by_url: dict[str, dict[str, Any]],
    snapshot_rows: list[dict[str, Any]],
    attempts: list[CollectionAttempt],
) -> list[dict[str, Any]]:
    if attempts:
        return [
            _ingestion_job_target_row_from_attempt(
                job_id,
                target_by_external_product_id,
                target_by_url,
                snapshot_rows,
                attempt,
            )
            for attempt in attempts
        ]

    rows = []
    for snapshot in snapshot_rows:
        external_product_id = snapshot.get("external_product_id")
        target = target_by_external_product_id.get(external_product_id or "")
        if not target:
            continue
        rows.append(
            {
                "id": _stable_uuid("ingestion_job_target", job_id, target["id"], snapshot["id"]),
                "ingestion_job_id": job_id,
                "collection_target_id": target["id"],
                "raw_snapshot_id": snapshot["id"],
                "status": snapshot["collection_status"],
                "error_code": None,
                "error_message": None,
                "attempted_at": snapshot["collected_at"],
            },
        )
    return rows


def _ingestion_job_target_row_from_attempt(
    job_id: str,
    target_by_external_product_id: dict[str, dict[str, Any]],
    target_by_url: dict[str, dict[str, Any]],
    snapshot_rows: list[dict[str, Any]],
    attempt: CollectionAttempt,
) -> dict[str, Any]:
    external_product_id = attempt.external_product_id or ""
    target = target_by_external_product_id.get(external_product_id)
    if target is None and attempt.target_url:
        target = target_by_url.get(attempt.target_url)

    snapshot = _snapshot_for_attempt(snapshot_rows, attempt)
    target_id = target["id"] if target else None
    snapshot_id = snapshot["id"] if snapshot else None

    return {
        "id": _stable_uuid(
            "ingestion_job_target",
            job_id,
            target_id or attempt.target_url or external_product_id or "unknown-target",
            snapshot_id or attempt.attempted_at,
            attempt.status,
        ),
        "ingestion_job_id": job_id,
        "collection_target_id": target_id,
        "raw_snapshot_id": snapshot_id,
        "status": attempt.status,
        "error_code": attempt.error_code,
        "error_message": attempt.error_message,
        "attempted_at": attempt.attempted_at,
    }


def _snapshot_for_attempt(
    snapshot_rows: list[dict[str, Any]],
    attempt: CollectionAttempt,
) -> dict[str, Any] | None:
    snapshot_external_id = attempt.raw_snapshot_external_product_id or attempt.external_product_id
    for snapshot in snapshot_rows:
        if snapshot_external_id and snapshot.get("external_product_id") == snapshot_external_id:
            return snapshot
        if attempt.target_url and snapshot.get("url") == attempt.target_url:
            return snapshot
    return None


def _first_collected_at(snapshots: list[RawProductSnapshot]) -> str | None:
    if not snapshots:
        return None
    return min(snapshot.collected_at for snapshot in snapshots)


def _last_collected_at(snapshots: list[RawProductSnapshot]) -> str | None:
    if not snapshots:
        return None
    return max(snapshot.collected_at for snapshot in snapshots)


def _first_attempted_at(attempts: list[CollectionAttempt]) -> str | None:
    if not attempts:
        return None
    return min(attempt.attempted_at for attempt in attempts)


def _last_attempted_at(attempts: list[CollectionAttempt]) -> str | None:
    if not attempts:
        return None
    return max(attempt.attempted_at for attempt in attempts)


def _first_postcode_context(snapshots: list[RawProductSnapshot]) -> str | None:
    for snapshot in snapshots:
        if snapshot.postcode_context:
            return snapshot.postcode_context
    return None


def _stable_uuid(*parts: str) -> str:
    return str(uuid5(NAMESPACE_URL, "basketguard:" + ":".join(parts)))


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _title_from_slug(value: str) -> str:
    return value.replace("_", " ").title()


def _website_url(retailer_slug: str) -> str | None:
    if retailer_slug == "tesco":
        return "https://www.tesco.com"
    return None
