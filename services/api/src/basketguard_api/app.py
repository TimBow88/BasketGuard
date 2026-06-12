from __future__ import annotations

from dataclasses import asdict, is_dataclass
from decimal import Decimal
from typing import Any, Callable, Iterator

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel

from basketguard_ingestion.postgres import open_postgres_connection
from basketguard_ingestion.review_decisions import (
    ReviewDecisionError,
    approve_review_item,
    reject_review_item,
)
from basketguard_reporting import (
    DEFAULT_HISTORY_WINDOW_DAYS,
    fetch_group_comparison,
    fetch_group_price_history,
    fetch_retailer_gaps,
    fetch_review_required_products,
)


ConnectionFactory = Callable[[], Any]


class ReviewDecisionRequest(BaseModel):
    reviewer_notes: str | None = None


def create_app(connection_factory: ConnectionFactory = open_postgres_connection) -> FastAPI:
    """Build the API app with an injectable DB-API connection factory.

    The factory is called once per report request and the connection is closed
    afterwards. Tests inject a factory returning a fake connection; production
    uses the shared ``open_postgres_connection`` helper.
    """

    app = FastAPI(title="BasketGuard API", version="0.1.0")
    app.state.connection_factory = connection_factory

    def _connection(request: Request) -> Iterator[Any]:
        connection = request.app.state.connection_factory()
        try:
            yield connection
        finally:
            close = getattr(connection, "close", None)
            if callable(close):
                close()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/reports/group-comparison/{group_slug}")
    def group_comparison(
        group_slug: str,
        connection: Any = Depends(_connection),
    ) -> dict[str, Any]:
        return _serialise(fetch_group_comparison(connection, group_slug))

    @app.get("/reports/group-history/{group_slug}")
    def group_history(
        group_slug: str,
        window_days: int = Query(default=DEFAULT_HISTORY_WINDOW_DAYS, ge=1),
        connection: Any = Depends(_connection),
    ) -> dict[str, Any]:
        return _serialise(fetch_group_price_history(connection, group_slug, window_days))

    @app.get("/reports/retailer-gaps")
    def retailer_gaps(
        group_slug: list[str] = Query(min_length=1),
        connection: Any = Depends(_connection),
    ) -> dict[str, Any]:
        return _serialise(fetch_retailer_gaps(connection, group_slug))

    @app.get("/reports/review-required")
    def review_required(
        group_slug: str | None = Query(default=None),
        connection: Any = Depends(_connection),
    ) -> dict[str, Any]:
        return _serialise(fetch_review_required_products(connection, group_slug))

    @app.post("/review-items/{review_item_id}/approve")
    def approve(
        review_item_id: str,
        payload: ReviewDecisionRequest | None = None,
        connection: Any = Depends(_connection),
    ) -> dict[str, Any]:
        return _decide(approve_review_item, connection, review_item_id, payload)

    @app.post("/review-items/{review_item_id}/reject")
    def reject(
        review_item_id: str,
        payload: ReviewDecisionRequest | None = None,
        connection: Any = Depends(_connection),
    ) -> dict[str, Any]:
        return _decide(reject_review_item, connection, review_item_id, payload)

    return app


def _decide(
    decision: Callable[..., Any],
    connection: Any,
    review_item_id: str,
    payload: ReviewDecisionRequest | None,
) -> dict[str, Any]:
    notes = payload.reviewer_notes if payload is not None else None
    try:
        return _serialise(decision(connection, review_item_id, reviewer_notes=notes))
    except ReviewDecisionError as error:
        # Covers missing items and items that were already resolved.
        raise HTTPException(status_code=404, detail=str(error)) from error


def _serialise(value: Any) -> Any:
    """Convert report dataclasses to JSON-safe dicts, keeping Decimals as strings."""

    if is_dataclass(value) and not isinstance(value, type):
        return _serialise(asdict(value))
    if isinstance(value, dict):
        return {key: _serialise(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialise(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    return value


app = create_app()
