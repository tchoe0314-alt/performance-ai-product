from __future__ import annotations

from typing import Any, Dict

from engines.cost_engine import (
    normalize_unit_price_book,
    unit_price_book_from_csv,
    validate_unit_price_book_for_production,
)


def normalize_unit_price_book_response(price_book: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_unit_price_book(price_book)
    return {
        "success": True,
        "unit_price_book": normalized,
        "validation": normalized["production_validation"],
        "truth_label": normalized["truth_label"],
    }


def unit_price_book_from_csv_response(
    *,
    csv_text: str,
    source: str = "",
    location: str = "",
    effective_date: str = "",
    approved_by: str = "",
    approval_date: str = "",
    currency: str = "USD",
    contingency_pct: float = 15.0,
) -> Dict[str, Any]:
    price_book = unit_price_book_from_csv(
        csv_text,
        source=source,
        location=location,
        effective_date=effective_date,
        approved_by=approved_by,
        approval_date=approval_date,
        currency=currency,
        contingency_pct=contingency_pct,
    )
    return {
        "success": True,
        "unit_price_book": price_book,
        "validation": price_book["production_validation"],
        "truth_label": price_book["truth_label"],
    }


def validate_unit_price_book_response(price_book: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_unit_price_book(price_book)
    validation = validate_unit_price_book_for_production(normalized)
    return {
        "success": bool(validation["success"]),
        "unit_price_book": normalized,
        "validation": validation,
        "truth_label": validation["truth_label"],
    }


__all__ = [
    "normalize_unit_price_book_response",
    "unit_price_book_from_csv_response",
    "validate_unit_price_book_response",
]
