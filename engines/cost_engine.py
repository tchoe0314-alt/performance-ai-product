from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Tuple


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
    source = _safe_str(raw.get("source") or raw.get("source_id"))
    location = _safe_str(raw.get("location") or raw.get("region") or raw.get("jurisdiction"))
    effective_date = _safe_str(raw.get("effective_date") or raw.get("date"))
    approved_by = _safe_str(raw.get("approved_by") or raw.get("reviewed_by"))
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
            "notes": _safe_str(rec.get("notes")),
        }
        unit_prices[metric] = normalized
    normalized = {
        "version": "unit_price_book_v1",
        "source": source,
        "location": location,
        "effective_date": effective_date,
        "approved_by": approved_by,
        "approval_date": approval_date,
        "currency": currency,
        "contingency_pct": max(0.0, contingency_pct),
        "unit_prices": unit_prices,
    }
    stable_payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    normalized["price_book_hash"] = hashlib.sha256(stable_payload.encode("utf-8")).hexdigest()
    validation = validate_unit_price_book_for_production(normalized, attach_validation=False)
    normalized["production_usable"] = bool(validation.get("production_usable"))
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
        ("location", "Production cost estimates require a region/jurisdiction because unit prices are location-sensitive."),
        ("effective_date", "Production cost estimates require the price book effective date."),
        ("approved_by", "Production cost estimates require reviewer/estimator approval evidence."),
        ("approval_date", "Production cost estimates require the date the price book was approved for use."),
    ):
        if not _safe_str(book.get(field_name)):
            blockers.append({"field": field_name, "reason": reason, "severity": "blocker"})
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
        "blockers": blockers,
        "warnings": warnings,
        "required_fields": ["source", "location", "effective_date", "approved_by", "approval_date", "unit_prices"],
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
    location: str = "",
    effective_date: str = "",
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
            "location": location,
            "effective_date": effective_date,
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
        "production_usable": bool(validation.get("production_usable")) if raw else False,
        "currency": _safe_str(normalized.get("currency") if normalized else "", "USD"),
        "location": _safe_str(normalized.get("location") if normalized else ""),
        "effective_date": _safe_str(normalized.get("effective_date") if normalized else ""),
        "approved_by": _safe_str(normalized.get("approved_by") if normalized else ""),
        "approval_date": _safe_str(normalized.get("approval_date") if normalized else ""),
        "price_book_hash": _safe_str(normalized.get("price_book_hash") if normalized else ""),
        "contingency_pct": _safe_float(normalized.get("contingency_pct") if normalized else None, 15.0),
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
    calculation_complete = bool(line_items) and traceability_complete and quantities.get("success") is True
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
            "truth_label": "Cost estimates are only as reliable as quantity traceability and the attached unit-price book.",
        },
    )


__all__ = [
    "CostResult",
    "DEFAULT_UNIT_PRICES",
    "compute_cost_estimate",
    "normalize_unit_price_book",
    "unit_price_book_from_csv",
    "validate_unit_price_book_for_production",
]
