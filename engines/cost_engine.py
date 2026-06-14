from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Tuple


COST_BOOK_VERSION = "cost_book_v1"
STALE_PRICE_BOOK_DAYS = 365


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _dedupe(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = _safe_str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _parse_iso_date(value: Any) -> date | None:
    text = _safe_str(value)
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _pricing_age_days(effective_date: Any) -> int | None:
    parsed = _parse_iso_date(effective_date)
    if not parsed:
        return None
    return max(0, (date.today() - parsed).days)


def _validation_details(issues: Iterable[Dict[str, Any]], *, area: str) -> List[Dict[str, Any]]:
    details: List[Dict[str, Any]] = []
    seen = set()
    for issue in issues:
        rec = _safe_dict(issue)
        if not rec:
            continue
        field = _safe_str(rec.get("field"), "validation")
        code = f"{area}_{field}".lower().replace(" ", "_").replace(".", "_")
        if code in seen:
            continue
        seen.add(code)
        severity = _safe_str(rec.get("severity"), "blocker").lower()
        details.append(
            {
                "code": code,
                "area": area,
                "field": field,
                "severity": severity,
                "what_failed": _safe_str(rec.get("reason"), f"{field.replace('_', ' ')} is incomplete."),
                "why_it_matters": (
                    "Bid-ready cost output depends on traceable pricing evidence tied to the project region and reviewed source."
                ),
                "missing_data": [field],
                "next_action": "Attach a traceable approved unit-price book and rerun cost validation.",
                "engineer_review_required": severity != "warning",
            }
        )
    return details


@dataclass
class CostResult:
    success: bool = True
    message: str = ""
    totals: Dict[str, Any] = field(default_factory=dict)
    line_items: List[Dict[str, Any]] = field(default_factory=list)
    category_subtotals: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    explain: Dict[str, Any] = field(default_factory=dict)


DEFAULT_UNIT_PRICES: Dict[str, Dict[str, Any]] = {
    "parking_area_sf": {"item": "Asphalt parking pavement", "category": "pavement", "unit": "sf", "unit_cost": 7.5},
    "road_area_sf": {"item": "Roadway pavement", "category": "pavement", "unit": "sf", "unit_cost": 9.0},
    "sidewalk_area_sf": {"item": "Concrete sidewalk", "category": "flatwork", "unit": "sf", "unit_cost": 12.0},
    "pipe_length_ft": {"item": "Storm pipe", "category": "storm", "unit": "ft", "unit_cost": 110.0},
    "inlet_count": {"item": "Storm inlet", "category": "storm", "unit": "ea", "unit_cost": 4500.0},
    "pond_area_sf": {"item": "Detention basin grading", "category": "storm", "unit": "sf", "unit_cost": 4.0},
    "utility_length_ft": {"item": "Water/utility main", "category": "utilities", "unit": "ft", "unit_cost": 85.0},
    "sanitary_length_ft": {"item": "Sanitary sewer pipe", "category": "sanitary", "unit": "ft", "unit_cost": 95.0},
    "sanitary_manhole_count": {"item": "Sanitary manhole", "category": "sanitary", "unit": "ea", "unit_cost": 6000.0},
    "sanitary_service_count": {"item": "Sanitary service lateral", "category": "sanitary", "unit": "ea", "unit_cost": 1800.0},
    "estimated_parking_stalls": {"item": "Parking striping/signage allowance", "category": "pavement", "unit": "ea", "unit_cost": 75.0},
}


def normalize_unit_price_book(raw: Dict[str, Any]) -> Dict[str, Any]:
    source = _safe_str(raw.get("source_name") or raw.get("source") or raw.get("source_id"))
    source_type = _safe_str(raw.get("source_type"), "approved_cost_book" if source else "")
    location = _safe_str(raw.get("location") or raw.get("region") or raw.get("jurisdiction"))
    effective_date = _safe_str(raw.get("effective_date") or raw.get("date"))
    accepted_by = _safe_str(raw.get("accepted_by") or raw.get("approved_by") or raw.get("reviewed_by"))
    approved_by = _safe_str(raw.get("approved_by") or raw.get("reviewed_by") or accepted_by)
    approval_date = _safe_str(raw.get("approval_date") or raw.get("review_date"))
    currency = _safe_str(raw.get("currency"), "USD").upper()
    contingency_pct = _safe_float(raw.get("contingency_pct"), 15.0)
    unit_prices: Dict[str, Dict[str, Any]] = {}
    raw_prices = raw.get("unit_prices")
    if isinstance(raw_prices, list):
        iterable = raw_prices
    elif isinstance(raw_prices, dict):
        iterable = []
        for key, value in raw_prices.items():
            rec = dict(_safe_dict(value))
            rec.setdefault("metric", key)
            iterable.append(rec)
    else:
        iterable = []
    for value in iterable:
        rec = _safe_dict(value)
        metric = _safe_str(rec.get("metric") or rec.get("quantity_metric") or rec.get("key"))
        if not metric:
            continue
        normalized = {
            "metric": metric,
            "item": _safe_str(rec.get("item") or rec.get("description") or rec.get("name"), metric),
            "category": _safe_str(rec.get("category") or rec.get("discipline"), "general"),
            "unit": _safe_str(rec.get("unit") or rec.get("units")),
            "unit_cost": _safe_float(rec.get("unit_cost") or rec.get("price") or rec.get("cost")),
            "source_item_id": _safe_str(rec.get("source_item_id") or rec.get("bid_item_id") or rec.get("item_id")),
            "source_name": source,
            "source_type": source_type,
            "notes": _safe_str(rec.get("notes")),
        }
        unit_prices[metric] = normalized
    normalized = {
        "version": COST_BOOK_VERSION,
        "source": source,
        "source_name": source,
        "source_type": source_type,
        "location": location,
        "effective_date": effective_date,
        "accepted_by": accepted_by,
        "approved_by": approved_by,
        "approval_date": approval_date,
        "currency": currency,
        "contingency_pct": max(0.0, contingency_pct),
        "unit_prices": unit_prices,
    }
    normalized["items"] = [
        {
            "metric": metric,
            "item": rec["item"],
            "category": rec["category"],
            "unit": rec["unit"],
            "unit_cost": rec["unit_cost"],
            "source_item_id": rec["source_item_id"],
            "source_name": source,
            "source_type": source_type,
        }
        for metric, rec in sorted(unit_prices.items())
    ]
    stable_payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    normalized["price_book_hash"] = hashlib.sha256(stable_payload.encode("utf-8")).hexdigest()
    validation = validate_unit_price_book_for_production(normalized, attach_validation=False)
    normalized["production_usable"] = bool(validation.get("production_usable"))
    normalized["confidence"] = "approved" if normalized["production_usable"] else "blocked"
    normalized["production_validation"] = validation
    normalized["truth_label"] = (
        "Unit price books are production-usable only when source, location, effective date, approval, "
        "and positive traceable unit prices are present."
    )
    return normalized


def validate_unit_price_book_for_production(
    price_book: Dict[str, Any],
    *,
    attach_validation: bool = True,
) -> Dict[str, Any]:
    book = _safe_dict(price_book)
    unit_prices = _safe_dict(book.get("unit_prices"))
    blockers: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    for field_name, reason in (
        ("source", "Production cost estimates require a traceable source such as a company bid book, DOT schedule, or approved estimator file."),
        ("source_type", "Production cost estimates require the approved price source type, such as company_bid_book, dot_schedule, estimator_quote, or approved_cost_book."),
        ("location", "Production cost estimates require a region/jurisdiction because unit prices are location-sensitive."),
        ("effective_date", "Production cost estimates require the price book effective date."),
        ("approved_by", "Production cost estimates require reviewer/estimator approval evidence."),
        ("approval_date", "Production cost estimates require the date the price book was approved for use."),
    ):
        if not _safe_str(book.get(field_name)):
            blockers.append({"field": field_name, "reason": reason, "severity": "blocker"})
    age_days = _pricing_age_days(book.get("effective_date"))
    stale = bool(age_days is not None and age_days > STALE_PRICE_BOOK_DAYS)
    if stale:
        blockers.append(
            {
                "field": "effective_date",
                "reason": f"Unit-price book is stale ({age_days} days old); pricing older than {STALE_PRICE_BOOK_DAYS} days must be refreshed or explicitly reaccepted.",
                "severity": "blocker",
                "age_days": age_days,
                "stale_after_days": STALE_PRICE_BOOK_DAYS,
            }
        )
    if not unit_prices:
        blockers.append(
            {
                "field": "unit_prices",
                "reason": "Production cost estimates require at least one positive unit price.",
                "severity": "blocker",
            }
        )
    known_metrics = set(DEFAULT_UNIT_PRICES.keys())
    for metric, value in unit_prices.items():
        rec = _safe_dict(value)
        if _safe_float(rec.get("unit_cost"), 0.0) <= 0.0:
            blockers.append(
                {
                    "field": f"unit_prices.{metric}.unit_cost",
                    "reason": "Each production unit price must be a positive number.",
                    "severity": "blocker",
                }
            )
        if not _safe_str(rec.get("unit")):
            blockers.append(
                {
                    "field": f"unit_prices.{metric}.unit",
                    "reason": "Each production unit price must declare its measurement unit.",
                    "severity": "blocker",
                }
            )
        if not _safe_str(rec.get("item")):
            blockers.append(
                {
                    "field": f"unit_prices.{metric}.item",
                    "reason": "Each production unit price must include a readable item description.",
                    "severity": "blocker",
                }
            )
        if not _safe_str(rec.get("source_item_id")):
            blockers.append(
                {
                    "field": f"unit_prices.{metric}.source_item_id",
                    "reason": "Each production unit price must trace to a bid item, schedule line, or estimator source item ID.",
                    "severity": "blocker",
                }
            )
        if metric not in known_metrics:
            warnings.append(
                {
                    "field": f"unit_prices.{metric}",
                    "reason": "This unit price metric is not consumed by the current quantity engine unless matching quantities are present.",
                    "severity": "warning",
                }
            )
    validation = {
        "success": not blockers,
        "production_usable": not blockers,
        "age_days": age_days,
        "stale_after_days": STALE_PRICE_BOOK_DAYS,
        "stale": stale,
        "blockers": blockers,
        "blocker_details": _validation_details(blockers, area="unit_price_book"),
        "warnings": warnings,
        "warning_details": _validation_details(warnings, area="unit_price_book"),
        "required_fields": ["source", "source_type", "location", "effective_date", "approved_by", "approval_date", "unit_prices"],
        "truth_label": "Civora blocks bid-ready cost output unless the unit-price book has traceable source and approval metadata.",
    }
    if attach_validation and isinstance(price_book, dict):
        price_book["production_validation"] = validation
        price_book["production_usable"] = bool(validation["production_usable"])
    return validation


def unit_price_book_from_csv(
    csv_text: str,
    *,
    source: str = "",
    source_type: str = "approved_cost_book",
    location: str = "",
    effective_date: str = "",
    accepted_by: str = "",
    approved_by: str = "",
    approval_date: str = "",
    currency: str = "USD",
    contingency_pct: float = 15.0,
) -> Dict[str, Any]:
    reader = csv.DictReader(io.StringIO(csv_text or ""))
    unit_prices: Dict[str, Dict[str, Any]] = {}
    for row in reader:
        metric = _safe_str(row.get("metric") or row.get("quantity_metric") or row.get("key"))
        if not metric:
            continue
        unit_prices[metric] = {
            "metric": metric,
            "item": _safe_str(row.get("item") or row.get("description") or row.get("name"), metric),
            "category": _safe_str(row.get("category") or row.get("discipline"), "general"),
            "unit": _safe_str(row.get("unit") or row.get("units")),
            "unit_cost": _safe_float(row.get("unit_cost") or row.get("price") or row.get("cost")),
            "source_item_id": _safe_str(row.get("source_item_id") or row.get("bid_item_id") or row.get("item_id")),
            "notes": _safe_str(row.get("notes")),
        }
    return normalize_unit_price_book(
        {
            "source": source,
            "source_type": source_type,
            "location": location,
            "effective_date": effective_date,
            "accepted_by": accepted_by or approved_by,
            "approved_by": approved_by,
            "approval_date": approval_date,
            "currency": currency,
            "contingency_pct": contingency_pct,
            "unit_prices": unit_prices,
        }
    )


def _unit_price_book(meta: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    raw = _safe_dict(meta.get("cost_pricing") or meta.get("unit_price_book") or meta.get("unit_prices"))
    normalized = normalize_unit_price_book(raw) if raw else {}
    prices = dict(DEFAULT_UNIT_PRICES)
    user_prices = _safe_dict(normalized.get("unit_prices") if normalized else {})
    for key, value in user_prices.items():
        rec = _safe_dict(value)
        if not rec:
            continue
        merged = dict(prices.get(key, {}))
        merged.update(rec)
        prices[key] = merged
    validation = _safe_dict(normalized.get("production_validation"))
    pricing_meta = {
        "source": _safe_str(normalized.get("source") if normalized else "", "civora_concept_default_unit_prices" if not raw else "user_unit_price_book"),
        "source_name": _safe_str(normalized.get("source_name") if normalized else "", "Civora concept defaults" if not raw else "user_unit_price_book"),
        "source_type": _safe_str(normalized.get("source_type") if normalized else "", "concept_default" if not raw else ""),
        "production_usable": bool(validation.get("production_usable")) if raw else False,
        "currency": _safe_str(normalized.get("currency") if normalized else "", "USD"),
        "location": _safe_str(normalized.get("location") if normalized else ""),
        "effective_date": _safe_str(normalized.get("effective_date") if normalized else ""),
        "accepted_by": _safe_str(normalized.get("accepted_by") if normalized else ""),
        "approved_by": _safe_str(normalized.get("approved_by") if normalized else ""),
        "approval_date": _safe_str(normalized.get("approval_date") if normalized else ""),
        "price_book_hash": _safe_str(normalized.get("price_book_hash") if normalized else ""),
        "contingency_pct": _safe_float(normalized.get("contingency_pct") if normalized else None, 15.0),
        "confidence": _safe_str(normalized.get("confidence") if normalized else "", "concept_default" if not raw else "blocked"),
        "items": _safe_list(normalized.get("items") if normalized else []),
        "production_validation": validation,
        "production_metric_keys": sorted(user_prices.keys()),
    }
    return prices, pricing_meta


def _quantity_trace(quantities: Dict[str, Any], metric: str) -> Dict[str, Any]:
    return _safe_dict(_safe_dict(_safe_dict(quantities.get("explain")).get("quantity_audit")).get(metric))


def _quantity_model_reference(quantities: Dict[str, Any]) -> Dict[str, Any]:
    explain = _safe_dict(quantities.get("explain"))
    payload = {
        "success": quantities.get("success"),
        "totals": _safe_dict(quantities.get("totals")),
        "quantity_audit": _safe_dict(explain.get("quantity_audit")),
        "trace_gaps": _safe_dict(explain.get("trace_gaps")),
    }
    stable = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return {
        "quantity_model_hash": hashlib.sha256(stable.encode("utf-8")).hexdigest(),
        "quantity_success": quantities.get("success"),
        "quantity_traceability_complete": not bool(_safe_dict(explain.get("trace_gaps"))),
        "priced_quantity_metrics": sorted(
            metric
            for metric, value in _safe_dict(quantities.get("totals")).items()
            if _safe_float(value, 0.0) > 0.0
        ),
    }


def _cost_estimate_reference(
    *,
    totals: Dict[str, Any],
    line_items: List[Dict[str, Any]],
    category_subtotals: Dict[str, float],
    pricing_meta: Dict[str, Any],
    quantity_model_reference: Dict[str, Any],
) -> Dict[str, Any]:
    payload = {
        "totals": totals,
        "line_items": line_items,
        "category_subtotals": category_subtotals,
        "price_book_hash": _safe_str(pricing_meta.get("price_book_hash")),
        "pricing_source": _safe_str(pricing_meta.get("source")),
        "quantity_model_hash": _safe_str(quantity_model_reference.get("quantity_model_hash")),
    }
    stable = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return {
        "cost_estimate_hash": hashlib.sha256(stable.encode("utf-8")).hexdigest(),
        "quantity_model_hash": _safe_str(quantity_model_reference.get("quantity_model_hash")),
        "price_book_hash": _safe_str(pricing_meta.get("price_book_hash")),
        "pricing_source": _safe_str(pricing_meta.get("source")),
    }


def _cost_package_blocker(area: str, field: str, why_needed: str, next_action: str) -> Dict[str, Any]:
    return {
        "area": area,
        "field": field,
        "why_needed": why_needed,
        "suggested_next_action": next_action,
        "severity": "blocker",
    }


def build_cost_package_status(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Build a traceable cost package status for alpha review and release gates."""

    meta = _safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else _safe_dict(plan_or_meta)
    quantities = _safe_dict(meta.get("quantities"))
    cost = _safe_dict(meta.get("cost_estimate"))
    totals = _safe_dict(cost.get("totals"))
    explain = _safe_dict(cost.get("explain"))
    pricing = _safe_dict(explain.get("pricing"))
    pricing_validation = _safe_dict(pricing.get("production_validation"))
    quantity_reference = _safe_dict(explain.get("quantity_model_reference"))
    cost_reference = _safe_dict(explain.get("cost_estimate_reference"))
    coverage_gaps = _safe_dict(explain.get("pricing_coverage_gaps"))
    trace_gaps = _safe_dict(explain.get("trace_gaps"))
    priced_metrics = _safe_list(quantity_reference.get("priced_quantity_metrics"))
    production_metric_keys = _safe_list(pricing.get("production_metric_keys"))
    line_items = _safe_list(cost.get("line_items"))
    blockers: List[Dict[str, Any]] = []

    if not quantities:
        blockers.append(
            _cost_package_blocker(
                "cost",
                "quantities",
                "Cost package status requires a current quantity model.",
                "Run quantities before building the cost package.",
            )
        )
    if not cost:
        blockers.append(
            _cost_package_blocker(
                "cost",
                "cost_estimate",
                "Cost package status requires a current cost estimate.",
                "Run cost estimation after quantities are available.",
            )
        )
    elif cost.get("success") is not True:
        blockers.append(
            _cost_package_blocker(
                "cost",
                "cost_success",
                "Production cost package cannot use a failed or review-only cost estimate.",
                "Resolve cost estimate warnings/blockers and regenerate the estimate.",
            )
        )
    if not bool(pricing.get("production_usable")):
        blockers.append(
            _cost_package_blocker(
                "cost",
                "approved_unit_price_book",
                "Cost package needs an approved unit-price source before bid-ready output.",
                "Attach a regional/company unit-price book with source, date, approval, and source item IDs.",
            )
        )
    for gap in _safe_list(pricing_validation.get("blockers")):
        rec = _safe_dict(gap)
        field = _safe_str(rec.get("field"), "unit_price_book")
        blockers.append(
            _cost_package_blocker(
                "cost",
                field,
                _safe_str(rec.get("reason"), "Unit-price book validation failed."),
                "Fix the unit-price book metadata or line item and rerun cost validation.",
            )
        )
    if trace_gaps:
        blockers.append(
            _cost_package_blocker(
                "cost",
                "quantity_trace_gaps",
                "Cost package has priced quantities that do not trace to canonical source object IDs.",
                "Regenerate quantities with canonical source IDs before relying on the cost package.",
            )
        )
    if coverage_gaps:
        blockers.append(
            _cost_package_blocker(
                "cost",
                "price_book_coverage_gaps",
                "Approved unit-price book does not cover every positive priced quantity metric.",
                "Add missing unit-price rows or mark the estimate review-only.",
            )
        )
    quantity_hash = _safe_str(quantity_reference.get("quantity_model_hash"))
    cost_hash = _safe_str(cost_reference.get("cost_estimate_hash") or totals.get("cost_estimate_hash"))
    price_hash = _safe_str(cost_reference.get("price_book_hash") or pricing.get("price_book_hash"))
    if cost and not quantity_hash:
        blockers.append(
            _cost_package_blocker(
                "cost",
                "quantity_model_hash",
                "Cost package must identify the exact quantity model hash it priced.",
                "Regenerate cost from the current canonical quantity model.",
            )
        )
    if cost and not cost_hash:
        blockers.append(
            _cost_package_blocker(
                "cost",
                "cost_estimate_hash",
                "Cost package must identify the exact cost estimate hash.",
                "Regenerate the cost estimate and preserve its cost_estimate_hash.",
            )
        )
    if cost and not price_hash:
        blockers.append(
            _cost_package_blocker(
                "cost",
                "price_book_hash",
                "Cost package must identify the approved unit-price book hash.",
                "Attach an approved unit-price book and rerun cost estimation.",
            )
        )
    if (
        _safe_str(cost_reference.get("quantity_model_hash"))
        and quantity_hash
        and _safe_str(cost_reference.get("quantity_model_hash")) != quantity_hash
    ):
        blockers.append(
            _cost_package_blocker(
                "cost",
                "quantity_model_mismatch",
                "Cost estimate reference does not match the quantity model reference.",
                "Regenerate quantities and cost estimate from the same final model.",
            )
        )

    source_complete = all(
        _safe_str(pricing.get(field))
        for field in ("source", "source_type", "location", "effective_date", "approved_by", "approval_date")
    )
    production_usable = bool(cost.get("success") is True and totals.get("production_usable") is True and not blockers)
    if production_usable:
        status = "ready"
    elif cost and line_items:
        status = "needs_review"
    else:
        status = "blocked"
    return {
        "success": True,
        "source": "cost_package_status_v1",
        "status": status,
        "production_usable": production_usable,
        "review_ready": bool(cost and line_items),
        "cost_estimate_hash": cost_hash,
        "quantity_model_hash": quantity_hash,
        "price_book_hash": price_hash,
        "price_source": {
            "source": _safe_str(pricing.get("source")),
            "source_name": _safe_str(pricing.get("source_name") or pricing.get("source")),
            "source_type": _safe_str(pricing.get("source_type")),
            "location": _safe_str(pricing.get("location")),
            "effective_date": _safe_str(pricing.get("effective_date")),
            "accepted_by": _safe_str(pricing.get("accepted_by") or pricing.get("approved_by")),
            "approved_by": _safe_str(pricing.get("approved_by")),
            "approval_date": _safe_str(pricing.get("approval_date")),
            "currency": _safe_str(pricing.get("currency"), "USD"),
            "contingency_pct": _safe_float(pricing.get("contingency_pct"), 0.0),
            "confidence": _safe_str(pricing.get("confidence"), "blocked"),
            "items": _safe_list(pricing.get("items")),
            "stale": bool(pricing_validation.get("stale")),
            "age_days": pricing_validation.get("age_days"),
            "stale_after_days": pricing_validation.get("stale_after_days"),
            "approved_source_complete": source_complete,
            "production_usable": bool(pricing.get("production_usable")),
        },
        "coverage": {
            "positive_quantity_metrics": sorted(_safe_str(item) for item in priced_metrics if _safe_str(item)),
            "production_price_metrics": sorted(_safe_str(item) for item in production_metric_keys if _safe_str(item)),
            "missing_price_metrics": sorted(coverage_gaps.keys()),
            "trace_gap_metrics": sorted(trace_gaps.keys()),
            "pricing_coverage_complete": not bool(coverage_gaps),
            "quantity_traceability_complete": not bool(trace_gaps),
        },
        "line_item_count": len(line_items),
        "blockers": blockers,
        "blocker_details": _validation_details(blockers, area="cost_package"),
        "warnings": list(cost.get("warnings") or []),
        "truth_label": (
            "Cost packages are production-usable only when quantities are traceable, every positive metric is covered "
            "by an approved unit-price book, and cost/quantity/price hashes match."
        ),
    }


def compute_cost_estimate(plan_or_meta: Dict[str, Any]) -> CostResult:
    meta = _safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else _safe_dict(plan_or_meta)
    quantities = _safe_dict(meta.get("quantities"))
    totals = _safe_dict(quantities.get("totals"))
    prices, pricing_meta = _unit_price_book(meta)
    warnings: List[str] = []
    assumptions: List[str] = []
    if not quantities:
        return CostResult(
            success=False,
            message="Cost estimate requires quantity totals first.",
            warnings=["No quantity result is attached to the plan."],
            explain={"pricing": pricing_meta, "traceability_complete": False},
        )
    quantity_workflow = _safe_dict(quantities.get("workflow_review"))
    upstream_blocked_systems = _safe_list(_safe_dict(quantities.get("stale_or_reactive_status")).get("upstream_blocked_systems"))
    quantity_engine_blockers = _safe_list(quantities.get("engine_blockers")) + _safe_list(quantity_workflow.get("blockers"))
    if upstream_blocked_systems:
        warnings.append(
            "Upstream blocked systems prevent production quantity/cost readiness; cost output is review-only until rerun from current canonical systems."
        )
    if quantity_engine_blockers:
        warnings.append("Quantity workflow blockers remain unresolved; cost output cannot be production-ready.")
    if quantities.get("success") is not True:
        warnings.append("Quantity engine is not explicitly production-successful; cost estimate is for review only.")
    quantity_model_reference = _quantity_model_reference(quantities)
    if not pricing_meta["production_usable"]:
        if pricing_meta["source"] == "civora_concept_default_unit_prices":
            assumptions.append("Default concept unit prices are used because no production unit-price book is attached.")
        else:
            assumptions.append("Attached unit-price book is not production-usable until validation blockers are cleared.")
        warnings.append("Unit prices are concept/default or unapproved and are not production/bid authority.")

    line_items: List[Dict[str, Any]] = []
    category_subtotals: Dict[str, float] = {}
    trace_gaps: Dict[str, Dict[str, Any]] = {}
    pricing_coverage_gaps: Dict[str, Dict[str, Any]] = {}
    production_metric_keys = set(_safe_list(pricing_meta.get("production_metric_keys")))
    for metric, price in prices.items():
        quantity = _safe_float(totals.get(metric), 0.0)
        unit_cost = _safe_float(price.get("unit_cost"), 0.0)
        if quantity <= 0.0 or unit_cost <= 0.0:
            continue
        trace = _quantity_trace(quantities, metric)
        source_ids = [item for item in _safe_list(trace.get("source_object_ids")) if _safe_str(item)]
        amount = round(quantity * unit_cost, 2)
        category = _safe_str(price.get("category"), "general")
        line = {
            "metric": metric,
            "item": _safe_str(price.get("item"), metric),
            "category": category,
            "quantity": round(quantity, 3),
            "unit": _safe_str(price.get("unit"), _safe_str(price.get("units"))),
            "unit_cost": round(unit_cost, 2),
            "amount": amount,
            "currency": pricing_meta["currency"],
            "source_object_ids": source_ids,
            "trace_complete": bool(source_ids),
            "pricing_source": pricing_meta["source"],
            "unit_price_source": {
                "source_name": _safe_str(price.get("source_name") or pricing_meta.get("source_name") or pricing_meta.get("source")),
                "source_type": _safe_str(price.get("source_type") or pricing_meta.get("source_type")),
                "source_item_id": _safe_str(price.get("source_item_id")),
                "effective_date": _safe_str(pricing_meta.get("effective_date")),
                "accepted_by": _safe_str(pricing_meta.get("accepted_by") or pricing_meta.get("approved_by")),
                "confidence": _safe_str(pricing_meta.get("confidence"), "blocked"),
            },
            "unit_price_source_item_id": _safe_str(price.get("source_item_id")),
            "production_price": metric in production_metric_keys,
        }
        line_items.append(line)
        category_subtotals[category] = round(category_subtotals.get(category, 0.0) + amount, 2)
        if not source_ids:
            trace_gaps[metric] = {"quantity": quantity, "item": line["item"]}
        if pricing_meta["production_usable"] and metric not in production_metric_keys:
            pricing_coverage_gaps[metric] = {
                "quantity": quantity,
                "item": line["item"],
                "reason": "Positive quantity was priced with Civora concept defaults because the production unit-price book does not include this metric.",
            }

    direct_cost = round(sum(item["amount"] for item in line_items), 2)
    contingency_pct = max(0.0, _safe_float(pricing_meta.get("contingency_pct"), 0.0))
    contingency = round(direct_cost * contingency_pct / 100.0, 2)
    total = round(direct_cost + contingency, 2)
    traceability_complete = not bool(trace_gaps)
    if trace_gaps:
        warnings.append("Some priced quantities do not trace to canonical source object IDs.")
    if pricing_coverage_gaps:
        warnings.append("Some positive quantities are missing from the production unit-price book and were priced with concept defaults.")
    if not line_items:
        warnings.append("No positive priced quantities were found.")

    pricing_coverage_complete = not bool(pricing_coverage_gaps)
    upstream_clear = not upstream_blocked_systems and not quantity_engine_blockers
    calculation_complete = bool(line_items) and traceability_complete and quantities.get("success") is True and upstream_clear
    production_pricing_ready = bool(pricing_meta["production_usable"] and pricing_coverage_complete)
    success = calculation_complete and production_pricing_ready
    result_totals = {
        "direct_cost": direct_cost,
        "contingency_pct": contingency_pct,
        "contingency": contingency,
        "total_cost": total,
        "currency": pricing_meta["currency"],
        "line_item_count": len(line_items),
        "production_usable": bool(pricing_meta["production_usable"] and pricing_coverage_complete and success),
    }
    cost_reference = _cost_estimate_reference(
        totals=result_totals,
        line_items=line_items,
        category_subtotals=category_subtotals,
        pricing_meta=pricing_meta,
        quantity_model_reference=quantity_model_reference,
    )
    result_totals["cost_estimate_hash"] = cost_reference["cost_estimate_hash"]
    return CostResult(
        success=success,
        message=(
            "Cost estimate completed with production-usable pricing."
            if success
            else "Cost estimate completed for review, but production/bid signoff is blocked."
        ),
        totals=result_totals,
        line_items=line_items,
        category_subtotals=category_subtotals,
        warnings=sorted(set(warnings)),
        assumptions=assumptions,
        explain={
            "method": "quantity_x_unit_price",
            "pricing": pricing_meta,
            "traceability_complete": traceability_complete,
            "calculation_complete": calculation_complete,
            "trace_gaps": trace_gaps,
            "pricing_coverage_complete": pricing_coverage_complete,
            "pricing_coverage_gaps": pricing_coverage_gaps,
            "quantity_model_reference": quantity_model_reference,
            "cost_estimate_reference": cost_reference,
            "upstream_blocked_systems": upstream_blocked_systems,
            "quantity_engine_blockers": quantity_engine_blockers,
            "upstream_clear": upstream_clear,
            "truth_label": "Cost estimates are only as reliable as quantity traceability and the attached unit-price book.",
        },
    )


__all__ = [
    "CostResult",
    "DEFAULT_UNIT_PRICES",
    "build_cost_package_status",
    "compute_cost_estimate",
    "normalize_unit_price_book",
    "unit_price_book_from_csv",
    "validate_unit_price_book_for_production",
]
