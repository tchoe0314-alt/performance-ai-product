from __future__ import annotations

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


def _unit_price_book(meta: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    raw = _safe_dict(meta.get("cost_pricing") or meta.get("unit_price_book") or meta.get("unit_prices"))
    prices = dict(DEFAULT_UNIT_PRICES)
    user_prices = _safe_dict(raw.get("unit_prices") if raw else {})
    for key, value in user_prices.items():
        rec = _safe_dict(value)
        if not rec:
            continue
        merged = dict(prices.get(key, {}))
        merged.update(rec)
        prices[key] = merged
    pricing_meta = {
        "source": _safe_str(raw.get("source"), "civora_concept_default_unit_prices" if not raw else "user_unit_price_book"),
        "production_usable": raw.get("production_usable") is True,
        "currency": _safe_str(raw.get("currency"), "USD"),
        "location": _safe_str(raw.get("location")),
        "effective_date": _safe_str(raw.get("effective_date")),
        "contingency_pct": _safe_float(raw.get("contingency_pct"), 15.0),
    }
    return prices, pricing_meta


def _quantity_trace(quantities: Dict[str, Any], metric: str) -> Dict[str, Any]:
    return _safe_dict(_safe_dict(_safe_dict(quantities.get("explain")).get("quantity_audit")).get(metric))


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
    if quantities.get("success") is False:
        warnings.append("Quantity engine is not production-successful; cost estimate is for review only.")
    if not pricing_meta["production_usable"]:
        assumptions.append("Default concept unit prices are used because no production unit-price book is attached.")
        warnings.append("Unit prices are concept defaults and are not production/bid authority.")

    line_items: List[Dict[str, Any]] = []
    category_subtotals: Dict[str, float] = {}
    trace_gaps: Dict[str, Dict[str, Any]] = {}
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
        }
        line_items.append(line)
        category_subtotals[category] = round(category_subtotals.get(category, 0.0) + amount, 2)
        if not source_ids:
            trace_gaps[metric] = {"quantity": quantity, "item": line["item"]}

    direct_cost = round(sum(item["amount"] for item in line_items), 2)
    contingency_pct = max(0.0, _safe_float(pricing_meta.get("contingency_pct"), 0.0))
    contingency = round(direct_cost * contingency_pct / 100.0, 2)
    total = round(direct_cost + contingency, 2)
    traceability_complete = not bool(trace_gaps)
    if trace_gaps:
        warnings.append("Some priced quantities do not trace to canonical source object IDs.")
    if not line_items:
        warnings.append("No positive priced quantities were found.")

    success = bool(line_items) and traceability_complete and quantities.get("success") is not False
    return CostResult(
        success=success,
        message=(
            "Cost estimate completed."
            if success
            else "Cost estimate completed for review, but production/bid signoff is blocked."
        ),
        totals={
            "direct_cost": direct_cost,
            "contingency_pct": contingency_pct,
            "contingency": contingency,
            "total_cost": total,
            "currency": pricing_meta["currency"],
            "line_item_count": len(line_items),
            "production_usable": bool(pricing_meta["production_usable"] and success),
        },
        line_items=line_items,
        category_subtotals=category_subtotals,
        warnings=sorted(set(warnings)),
        assumptions=assumptions,
        explain={
            "method": "quantity_x_unit_price",
            "pricing": pricing_meta,
            "traceability_complete": traceability_complete,
            "trace_gaps": trace_gaps,
            "truth_label": "Cost estimates are only as reliable as quantity traceability and the attached unit-price book.",
        },
    )


__all__ = ["CostResult", "DEFAULT_UNIT_PRICES", "compute_cost_estimate"]
