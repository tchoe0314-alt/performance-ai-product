from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import re
from typing import Any, Dict, List, Optional

from .common import safe_dict, safe_float, safe_list, safe_str


ALTERNATIVES_VERSION = "design_alternatives_v1"

ALTERNATIVE_CATEGORIES = [
    "parking_layouts",
    "road_circulation_layouts",
    "basin_placement",
    "utility_routing",
    "grading_drainage_concepts",
    "site_organization",
]

_OPTION_LIBRARY = [
    {
        "seed": "balanced_access",
        "label": "Option 1 - Balanced Access",
        "summary": "Balanced site organization with moderate paving, clear circulation, and a central review focus.",
        "concepts": {
            "parking_layouts": "Distributed parking fields near active building edges with aisle lengths kept moderate.",
            "road_circulation_layouts": "Loop-style internal drive with fewer dead ends and simple fire/service access review.",
            "basin_placement": "Basin near a low-side perimeter area when terrain evidence supports that direction.",
            "utility_routing": "Utility trunk routing follows drives where practical to reduce isolated crossings.",
            "grading_drainage_concepts": "Moderate surface slopes toward defined collection paths; relies on reviewed terrain inputs.",
            "site_organization": "Building, parking, drives, and drainage are separated into easy-to-review zones.",
        },
        "tradeoffs": [
            "Usually easiest to review and revise.",
            "May not minimize paving or pipe length.",
            "Needs accepted boundary and terrain inputs before deeper reliance.",
        ],
        "quantity_weights": {"paving": 1.0, "storm": 1.0, "utility": 1.0, "earthwork": 1.0},
    },
    {
        "seed": "compact_paving",
        "label": "Option 2 - Compact Paving",
        "summary": "Compact parking and circulation concept intended to reduce paved area where program fit allows.",
        "concepts": {
            "parking_layouts": "Tighter parking fields grouped near the primary building frontage.",
            "road_circulation_layouts": "Shorter drive geometry with limited internal loop length and fewer paved branches.",
            "basin_placement": "Basin tucked along an edge to preserve central site area.",
            "utility_routing": "Short utility runs prioritized, with crossings flagged for review.",
            "grading_drainage_concepts": "Shorter collection paths may increase grading sensitivity at pavement edges.",
            "site_organization": "Program is concentrated to preserve open area for landscape, drainage, or future adjustment.",
        },
        "tradeoffs": [
            "Can reduce paving and some utility length.",
            "May create tighter circulation and grading constraints.",
            "Needs turning, fire access, and stall geometry review.",
        ],
        "quantity_weights": {"paving": 0.88, "storm": 0.96, "utility": 0.92, "earthwork": 1.04},
    },
    {
        "seed": "drainage_first",
        "label": "Option 3 - Drainage First",
        "summary": "Drainage-led organization that preserves a basin/outfall corridor before tightening the program.",
        "concepts": {
            "parking_layouts": "Parking is shifted away from likely drainage corridors and low-side basin space.",
            "road_circulation_layouts": "Drive layout preserves positive drainage routes and clear overland review paths.",
            "basin_placement": "Basin placement is prioritized near low-side storage/outfall opportunity.",
            "utility_routing": "Utilities avoid basin and major flow paths where practical.",
            "grading_drainage_concepts": "Drainage paths are favored over compactness until terrain and outfall evidence are accepted.",
            "site_organization": "Stormwater space is reserved first, then buildings, parking, and utilities are fit around it.",
        },
        "tradeoffs": [
            "Usually strongest for early stormwater review.",
            "Can increase drive or utility length.",
            "Program yield may need another pass after basin sizing.",
        ],
        "quantity_weights": {"paving": 1.06, "storm": 0.9, "utility": 1.08, "earthwork": 0.95},
    },
    {
        "seed": "service_separation",
        "label": "Option 4 - Service Separation",
        "summary": "Separates customer/visitor movement from service, utility, and maintenance access.",
        "concepts": {
            "parking_layouts": "Parking is arranged to keep service movements from crossing the primary pedestrian edge.",
            "road_circulation_layouts": "Secondary service route is reserved where site shape allows.",
            "basin_placement": "Basin location favors maintenance access and separation from public-facing areas.",
            "utility_routing": "Utility corridors are grouped with service access for review and maintenance clarity.",
            "grading_drainage_concepts": "Grading preserves accessible public areas while service zones absorb steeper transitions.",
            "site_organization": "Public, service, drainage, and utility zones are separated for comparison.",
        },
        "tradeoffs": [
            "Improves operational clarity.",
            "May increase circulation length.",
            "Needs review against program, access, and source constraints.",
        ],
        "quantity_weights": {"paving": 1.1, "storm": 1.02, "utility": 0.98, "earthwork": 1.02},
    },
]


def _today() -> str:
    return date.today().isoformat()


def _stable_id(*parts: Any) -> str:
    seed = "|".join(safe_str(part) for part in parts if safe_str(part))
    digest = hashlib.sha1(seed.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
    return f"alt_{digest}"


def _accepted_input_summary(meta: Dict[str, Any]) -> Dict[str, Any]:
    accepted_candidates = [
        safe_dict(item)
        for item in safe_list(meta.get("candidate_review_accepted_drafts_v1"))
        if safe_dict(item)
    ]
    existing = safe_dict(meta.get("existing_conditions_package"))
    source_confidence = safe_dict(meta.get("source_confidence_map_v1"))
    entries = [safe_dict(item) for item in safe_list(source_confidence.get("entries")) if safe_dict(item)]
    accepted_source_labels = [
        safe_str(item.get("label") or item.get("candidate_type") or item.get("object_type"))
        for item in accepted_candidates
        if safe_str(item.get("label") or item.get("candidate_type") or item.get("object_type"))
    ]
    trusted_entries = [
        safe_str(item.get("label") or item.get("source_name"))
        for item in entries
        if safe_str(item.get("confidence_band")) == "higher" and safe_str(item.get("label") or item.get("source_name"))
    ]
    return {
        "accepted_candidate_count": len(accepted_candidates),
        "trusted_source_count": len(trusted_entries),
        "has_existing_conditions_package": bool(existing),
        "has_verified_survey_control": bool(
            safe_dict(meta.get("survey_control_package")).get("verified")
            or safe_dict(meta.get("survey_control")).get("verified")
            or any(safe_str(item.get("source_type")) == "survey-backed" for item in entries)
        ),
        "accepted_labels": accepted_source_labels[:6],
        "trusted_labels": trusted_entries[:6],
    }


def _quantity_basis(meta: Dict[str, Any]) -> Dict[str, Any]:
    quantities = safe_dict(meta.get("quantities"))
    totals = safe_dict(quantities.get("totals"))
    cost = safe_dict(meta.get("cost_estimate"))
    line_items = [safe_dict(item) for item in safe_list(cost.get("line_items")) if safe_dict(item)]
    available = bool(totals or line_items)
    return {
        "available": available,
        "totals": deepcopy(totals),
        "line_item_count": len(line_items),
        "cost_status": safe_str(cost.get("status") or cost.get("confidence") or ""),
        "review_required": True,
        "truth_label": "Cost and quantity comparison is shown only where current traceable quantities or estimate lines exist.",
    }


def _weighted_quantity_snapshot(quantity_basis: Dict[str, Any], weights: Dict[str, float]) -> Dict[str, Any]:
    totals = safe_dict(quantity_basis.get("totals"))
    if not totals:
        return {"available": False, "reason": "No quantity totals are available for this concept comparison."}
    keys = {
        "paving": ("paving_area_sf", "pavement_area_sf", "parking_area_sf"),
        "storm": ("storm_pipe_lf", "storm_length_lf", "pipe_length_lf"),
        "utility": ("utility_length_lf", "water_length_lf", "sanitary_length_lf"),
        "earthwork": ("earthwork_cy", "cut_fill_cy", "grading_volume_cy"),
    }
    comparison: Dict[str, Any] = {"available": True, "estimated_review_deltas": {}}
    for group, aliases in keys.items():
        raw_value = 0.0
        matched = ""
        for alias in aliases:
            value = safe_float(totals.get(alias), 0.0)
            if value:
                raw_value = value
                matched = alias
                break
        if raw_value:
            weight = float(weights.get(group, 1.0))
            comparison["estimated_review_deltas"][group] = {
                "basis_key": matched,
                "base_value": round(raw_value, 3),
                "concept_value": round(raw_value * weight, 3),
                "delta": round((raw_value * weight) - raw_value, 3),
                "basis": "concept_weighted_existing_quantity",
            }
    if not comparison["estimated_review_deltas"]:
        return {"available": False, "reason": "Quantity totals exist but do not map to alternative comparison categories."}
    return comparison


def _score_option(option: Dict[str, Any], index: int, accepted_inputs: Dict[str, Any], quantity_basis: Dict[str, Any]) -> Dict[str, Any]:
    support_bonus = min(12, int(accepted_inputs.get("accepted_candidate_count") or 0) * 2)
    trusted_bonus = min(8, int(accepted_inputs.get("trusted_source_count") or 0) * 2)
    quantity_bonus = 5 if quantity_basis.get("available") else 0
    base = 58 + support_bonus + trusted_bonus + quantity_bonus
    if option["seed"] == "balanced_access":
        base += 5
    elif option["seed"] == "compact_paving":
        base += 3
    elif option["seed"] == "drainage_first":
        base += 4 if accepted_inputs.get("has_existing_conditions_package") else 1
    elif option["seed"] == "service_separation":
        base += 1
    score = max(0, min(100, base - index))
    return {
        "review_score": score,
        "score_basis": [
            "conceptual multi-criteria score",
            "accepted input support included" if support_bonus or trusted_bonus else "limited accepted input support",
            "cost/quantity comparison included" if quantity_bonus else "cost/quantity comparison unavailable",
        ],
        "criteria": {
            "program_fit": max(0, min(100, score + (3 if option["seed"] == "compact_paving" else 0))),
            "circulation_clarity": max(0, min(100, score + (4 if option["seed"] == "balanced_access" else -2))),
            "drainage_review_strength": max(0, min(100, score + (6 if option["seed"] == "drainage_first" else -1))),
            "utility_coordination": max(0, min(100, score + (4 if option["seed"] == "service_separation" else 0))),
            "revision_flexibility": max(0, min(100, score + (4 if option["seed"] == "balanced_access" else -1))),
        },
    }


def _normalize_count(value: Any, default: int = 3) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(1, min(parsed, len(_OPTION_LIBRARY)))


def requested_alternative_count_from_message(message: str, default: int = 3) -> int:
    match = re.search(r"\bshow\s+me\s+(\d+)\s+options?\b", safe_str(message).lower())
    if match:
        return _normalize_count(match.group(1), default)
    return default


def build_design_alternatives(
    meta: Dict[str, Any],
    *,
    requested_count: int = 3,
    focus: Optional[List[str]] = None,
) -> Dict[str, Any]:
    meta = safe_dict(meta)
    count = _normalize_count(requested_count, 3)
    accepted_inputs = _accepted_input_summary(meta)
    quantity_basis = _quantity_basis(meta)
    selected_prior = safe_str(safe_dict(meta.get(ALTERNATIVES_VERSION)).get("selected_alternative_id"))
    alternatives: List[Dict[str, Any]] = []
    for index, option in enumerate(_OPTION_LIBRARY[:count], start=1):
        alternative_id = _stable_id(option["seed"], index, ",".join(focus or []))
        scoring = _score_option(option, index, accepted_inputs, quantity_basis)
        quantity_comparison = _weighted_quantity_snapshot(quantity_basis, safe_dict(option.get("quantity_weights")))
        support_state = (
            "supported_by_accepted_inputs"
            if accepted_inputs.get("accepted_candidate_count") or accepted_inputs.get("trusted_source_count")
            else "concept_review_required"
        )
        alternatives.append(
            {
                "alternative_id": alternative_id,
                "option_number": index,
                "label": option["label"],
                "summary": option["summary"],
                "categories": list(ALTERNATIVE_CATEGORIES),
                "concepts": deepcopy(option["concepts"]),
                "scoring": scoring,
                "tradeoffs": list(option["tradeoffs"]),
                "cost_quantity_comparison": quantity_comparison,
                "input_support_state": support_state,
                "review_required": True,
                "status": "review_required_concept",
                "construction_release_allowed": False,
                "construction_readiness_implied": False,
                "merge_ready": support_state == "supported_by_accepted_inputs",
                "next_action": "Compare, revise, or select this concept as a draft direction for review.",
                "truth_label": "Design alternative is a review-required concept unless backed by accepted project inputs.",
            }
        )
    ranked = sorted(alternatives, key=lambda item: safe_float(safe_dict(item.get("scoring")).get("review_score")), reverse=True)
    return {
        "version": ALTERNATIVES_VERSION,
        "generated_on": _today(),
        "requested_count": count,
        "alternative_count": len(alternatives),
        "selected_alternative_id": selected_prior if any(item["alternative_id"] == selected_prior for item in alternatives) else "",
        "categories": list(ALTERNATIVE_CATEGORIES),
        "accepted_input_summary": accepted_inputs,
        "quantity_basis": quantity_basis,
        "alternatives": alternatives,
        "ranked_alternative_ids": [safe_str(item.get("alternative_id")) for item in ranked],
        "review_required": True,
        "construction_release_allowed": False,
        "construction_readiness_implied": False,
        "truth_label": "Alternatives are review-required concepts unless supported by accepted inputs; they do not create field-use readiness.",
    }


def compare_design_alternatives(meta: Dict[str, Any], *, requested_count: int = 3) -> Dict[str, Any]:
    alternatives_record = safe_dict(meta.get(ALTERNATIVES_VERSION)) or build_design_alternatives(meta, requested_count=requested_count)
    alternatives = [safe_dict(item) for item in safe_list(alternatives_record.get("alternatives")) if safe_dict(item)]
    rows = []
    for item in alternatives:
        scoring = safe_dict(item.get("scoring"))
        quantity = safe_dict(item.get("cost_quantity_comparison"))
        rows.append(
            {
                "alternative_id": safe_str(item.get("alternative_id")),
                "option_number": int(safe_float(item.get("option_number"), 0)),
                "label": safe_str(item.get("label")),
                "review_score": safe_float(scoring.get("review_score"), 0.0),
                "top_tradeoffs": safe_list(item.get("tradeoffs"))[:3],
                "quantity_available": bool(quantity.get("available")),
                "status": safe_str(item.get("status"), "review_required_concept"),
            }
        )
    return {
        "version": "design_alternatives_comparison_v1",
        "rows": rows,
        "best_review_score_option": rows[0]["alternative_id"] if rows else "",
        "review_required": True,
        "construction_release_allowed": False,
        "truth_label": "Comparison ranks review-required concepts for user review only.",
    }


def select_design_alternative(
    meta: Dict[str, Any],
    *,
    option_number: Optional[int] = None,
    alternative_id: str = "",
    action: str = "choose",
    reviewer_id: str = "",
    reason: str = "",
) -> Dict[str, Any]:
    updated_meta = deepcopy(safe_dict(meta))
    alternatives_record = safe_dict(updated_meta.get(ALTERNATIVES_VERSION)) or build_design_alternatives(updated_meta)
    alternatives = [safe_dict(item) for item in safe_list(alternatives_record.get("alternatives")) if safe_dict(item)]
    selected: Dict[str, Any] = {}
    for item in alternatives:
        if alternative_id and safe_str(item.get("alternative_id")) == alternative_id:
            selected = item
            break
        if option_number and int(safe_float(item.get("option_number"), 0)) == int(option_number):
            selected = item
            break
    if not selected:
        raise ValueError("Requested design alternative was not found.")
    normalized_action = safe_str(action).lower() or "choose"
    if normalized_action not in {"choose", "merge", "revise"}:
        normalized_action = "choose"
    audit = {
        "alternative_id": safe_str(selected.get("alternative_id")),
        "option_number": int(safe_float(selected.get("option_number"), 0)),
        "action": normalized_action,
        "reviewed_by": safe_str(reviewer_id, "user"),
        "reviewed_at": _today(),
        "reason": safe_str(reason),
        "status_after": "selected_review_required_concept",
        "construction_release_allowed": False,
    }
    selected = deepcopy(selected)
    selected["status"] = "selected_review_required_concept"
    selected["selected_action"] = normalized_action
    selected["selected_at"] = audit["reviewed_at"]
    selected["review_required"] = True
    alternatives_record["selected_alternative_id"] = selected["alternative_id"]
    alternatives_record["selected_alternative"] = selected
    alternatives_record["selection_status"] = "selected_review_required_concept"
    alternatives_record["merge_revise_workflow"] = {
        "available_actions": ["choose", "merge", "revise"],
        "last_action": normalized_action,
        "review_required": True,
        "construction_release_allowed": False,
        "truth_label": "Choose/merge/revise records a draft direction only; accepted source inputs are still required before deeper reliance.",
    }
    decisions = safe_list(updated_meta.get("design_alternative_decisions_v1"))
    decisions.append(audit)
    updated_meta["design_alternative_decisions_v1"] = decisions[-50:]
    updated_meta[ALTERNATIVES_VERSION] = alternatives_record
    return {
        "success": True,
        "updated_meta": updated_meta,
        ALTERNATIVES_VERSION: alternatives_record,
        "selected_alternative": selected,
        "audit_trail": decisions[-50:],
        "truth_label": "Selected alternative remains a review-required concept and does not create field-use readiness.",
    }


def append_revised_design_alternative(
    meta: Dict[str, Any],
    *,
    basis_option_number: Optional[int] = None,
    reviewer_id: str = "",
    reason: str = "",
) -> Dict[str, Any]:
    updated_meta = deepcopy(safe_dict(meta))
    alternatives_record = safe_dict(updated_meta.get(ALTERNATIVES_VERSION)) or build_design_alternatives(updated_meta)
    alternatives = [safe_dict(item) for item in safe_list(alternatives_record.get("alternatives")) if safe_dict(item)]
    basis = alternatives[0] if alternatives else {}
    if basis_option_number:
        basis = next((item for item in alternatives if int(safe_float(item.get("option_number"), 0)) == basis_option_number), basis)
    next_number = len(alternatives) + 1
    revised = deepcopy(basis)
    revised["alternative_id"] = _stable_id("revision", next_number, reason or basis.get("alternative_id"))
    revised["option_number"] = next_number
    revised["label"] = f"Option {next_number} - Revised Concept"
    revised["summary"] = "Revised concept generated from the current alternatives and user direction."
    revised["status"] = "review_required_concept"
    revised["review_required"] = True
    revised["construction_release_allowed"] = False
    revised["construction_readiness_implied"] = False
    revised["revision_basis_alternative_id"] = safe_str(basis.get("alternative_id"))
    revised["tradeoffs"] = [
        "Revision needs review against the original program and accepted inputs.",
        "Use compare again before selecting it as the draft direction.",
    ] + safe_list(basis.get("tradeoffs"))[:2]
    concepts = safe_dict(revised.get("concepts"))
    concepts["site_organization"] = (
        safe_str(concepts.get("site_organization"))
        + " Revision note: adjust layout around the latest user direction before relying on it."
    ).strip()
    revised["concepts"] = concepts
    alternatives.append(revised)
    alternatives_record["alternatives"] = alternatives
    alternatives_record["alternative_count"] = len(alternatives)
    alternatives_record["requested_count"] = len(alternatives)
    alternatives_record["ranked_alternative_ids"] = [
        safe_str(item.get("alternative_id"))
        for item in sorted(alternatives, key=lambda item: safe_float(safe_dict(item.get("scoring")).get("review_score")), reverse=True)
    ]
    decisions = safe_list(updated_meta.get("design_alternative_decisions_v1"))
    decisions.append(
        {
            "alternative_id": revised["alternative_id"],
            "action": "revise",
            "reviewed_by": safe_str(reviewer_id, "user"),
            "reviewed_at": _today(),
            "reason": safe_str(reason, "User requested another layout."),
            "status_after": "review_required_concept",
            "construction_release_allowed": False,
        }
    )
    updated_meta["design_alternative_decisions_v1"] = decisions[-50:]
    updated_meta[ALTERNATIVES_VERSION] = alternatives_record
    return {
        "success": True,
        "updated_meta": updated_meta,
        ALTERNATIVES_VERSION: alternatives_record,
        "revised_alternative": revised,
        "audit_trail": decisions[-50:],
        "truth_label": "Revised alternative is a review-required concept only.",
    }


def option_number_from_message(message: str) -> Optional[int]:
    match = re.search(r"\boption\s*(\d+)\b", safe_str(message).lower())
    if not match:
        return None
    return _normalize_count(match.group(1), 1)
