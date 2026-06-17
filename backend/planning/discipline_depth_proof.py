from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Sequence

from .common import safe_dict, safe_list, safe_str


ENGINEER_REVIEW_REQUIRED_LABEL = "engineer_review_required"


DISCIPLINE_PROOF_REQUIREMENTS: Dict[str, List[Dict[str, Any]]] = {
    "grading": [
        {"id": "terrain_tin_dependency", "label": "Terrain/TIN dependency", "evidence": ("surface_metadata", "accepted existing/proposed surface IDs", "proposed surface source/confidence"), "blocker_terms": ("surface", "terrain", "tin")},
        {"id": "cut_fill", "label": "Cut/fill volumes", "evidence": ("cut/fill expected/actual volumes",), "blocker_terms": ("cut/fill", "earthwork")},
        {"id": "slopes", "label": "Slopes and positive drainage", "evidence": ("slope expected/actual summary", "drainage-aware grading repair evidence"), "blocker_terms": ("slope", "drainage-aware")},
        {"id": "tie_ins", "label": "Pad, road, and basin tie-ins", "evidence": ("pad tie-in expected/actual evidence",), "blocker_terms": ("tie-in", "tie ins", "pad")},
        {"id": "retaining_wall_triggers", "label": "Retaining wall triggers", "evidence": ("retaining wall tie-in evidence or no wall scope",), "blocker_terms": ("retaining wall", "wall")},
        {"id": "pad_road_basin_interaction", "label": "Pad/road/basin interaction", "evidence": ("ADA path or drainage repair expected/actual evidence", "drainage-aware grading repair evidence"), "blocker_terms": ("roadway", "basin", "drainage")},
    ],
    "storm_pipe": [
        {"id": "basin_outfall_dependency", "label": "Basin/outfall dependency", "evidence": ("drainage basin/outfall target",), "blocker_terms": ("basin/outfall", "outfall", "target")},
        {"id": "hgl_egl", "label": "HGL/EGL evidence", "evidence": ("HGL/EGL profile rows", "hydraulic_validation"), "blocker_terms": ("HGL", "EGL", "hydraulic")},
        {"id": "inlet_spread", "label": "Inlet spread and bypass", "evidence": ("inlet capacity/spread/bypass checks",), "blocker_terms": ("inlet", "spread", "bypass")},
        {"id": "overflow_paths", "label": "Overflow paths", "evidence": ("overflow routing/capacity",), "blocker_terms": ("overflow",)},
        {"id": "detention_routing", "label": "Detention routing", "evidence": ("detention stage-storage/routing",), "blocker_terms": ("detention", "stage-storage", "drawdown")},
        {"id": "storm_depth_validation", "label": "Storm depth validation", "evidence": ("depth_validation",), "blocker_terms": ("storm depth", "tailwater", "tributary")},
    ],
    "hydrology": [
        {"id": "basin_outfall_dependency", "label": "Basin/outfall dependency", "evidence": ("drainage basin/outfall target",), "blocker_terms": ("basin/outfall", "outfall")},
        {"id": "detention_routing", "label": "Detention routing", "evidence": ("detention stage-storage/routing", "hydrology_or_detention"), "blocker_terms": ("detention", "routing")},
        {"id": "overflow_paths", "label": "Overflow paths", "evidence": ("overflow routing/capacity",), "blocker_terms": ("overflow",)},
        {"id": "storm_depth_validation", "label": "Storm depth validation", "evidence": ("depth_validation",), "blocker_terms": ("storm depth", "tailwater", "tributary")},
    ],
    "sanitary": [
        {"id": "service_coverage", "label": "Service coverage", "evidence": ("service_coverage",), "blocker_terms": ("service", "lateral", "coverage")},
        {"id": "slope", "label": "Pipe slope", "evidence": ("network_validation",), "blocker_terms": ("slope",)},
        {"id": "cover", "label": "Pipe cover", "evidence": ("network_validation",), "blocker_terms": ("cover",)},
        {"id": "tie_in", "label": "Tie-in validation", "evidence": ("tie_in_validation",), "blocker_terms": ("tie-in", "tie_in")},
        {"id": "capacity", "label": "Capacity", "evidence": ("capacity_validation",), "blocker_terms": ("capacity",)},
        {"id": "manhole_spacing", "label": "Manhole spacing", "evidence": ("manhole_spacing",), "blocker_terms": ("manhole", "spacing")},
        {"id": "reroute_recalculation", "label": "Reroute recalculation", "evidence": ("post_reroute_recalculation",), "blocker_terms": ("recalculation", "reroute")},
    ],
    "water": [
        {"id": "hydrants", "label": "Hydrant locations and spacing", "evidence": ("hydrant spacing evidence",), "blocker_terms": ("hydrant",)},
        {"id": "source_pressure", "label": "Source pressure and source record", "evidence": ("pressure validation",), "blocker_terms": ("source pressure", "source_pressure")},
        {"id": "residual_pressure", "label": "Residual pressure target and check", "evidence": ("fire flow validation", "pressure validation"), "blocker_terms": ("residual", "fire-flow", "fire flow")},
        {"id": "demand", "label": "Demand/fire-flow criteria", "evidence": ("fire flow validation", "velocity checks"), "blocker_terms": ("demand", "flow", "criteria")},
        {"id": "accepted_standard", "label": "Accepted standard", "evidence": ("fire flow validation", "pressure validation"), "blocker_terms": ("standard", "accepted")},
        {"id": "utility_owner_criteria", "label": "Utility-owner criteria", "evidence": ("utility owner criteria",), "blocker_terms": ("utility owner", "owner criteria")},
        {"id": "pressure_zones", "label": "Pressure zones", "evidence": ("pressure zones",), "blocker_terms": ("pressure zones", "zone")},
        {"id": "main_evidence", "label": "Main size, material, and source", "evidence": ("pressure validation", "velocity checks"), "blocker_terms": ("main", "material", "diameter")},
        {"id": "velocities", "label": "Velocities", "evidence": ("velocity checks",), "blocker_terms": ("velocity",)},
        {"id": "loop_dead_end", "label": "Loop/dead-end checks", "evidence": ("looped network graph", "no dead-end water nodes"), "blocker_terms": ("loop", "dead-end", "dead end")},
    ],
    "roadway_corridor": [
        {"id": "alignment", "label": "Alignment", "evidence": ("road alignments", "alignment_or_sheet_views"), "blocker_terms": ("alignment",)},
        {"id": "profile", "label": "Profile", "evidence": ("road profiles",), "blocker_terms": ("profile",)},
        {"id": "sections", "label": "Sections", "evidence": ("corridor sections",), "blocker_terms": ("section",)},
        {"id": "crown_cross_slope", "label": "Crown/cross-slope", "evidence": ("road crown expected/actual controls",), "blocker_terms": ("crown", "cross-slope", "cross slope")},
        {"id": "curb_returns", "label": "Curb returns", "evidence": ("curb returns",), "blocker_terms": ("curb-return", "curb return")},
        {"id": "ada", "label": "ADA checks", "evidence": ("ADA compliance checks",), "blocker_terms": ("ADA",)},
        {"id": "max_grade", "label": "Max grade", "evidence": ("curb/gutter expected/actual controls", "road profiles"), "blocker_terms": ("grade", "gutter")},
    ],
    "quantity": [
        {"id": "upstream_systems", "label": "Upstream blocked systems", "evidence": ("quantity_outputs",), "blocker_terms": ("upstream", "blocked", "quantity_success")},
        {"id": "canonical_ids", "label": "Canonical ID trace", "evidence": ("quantity_outputs",), "blocker_terms": ("trace", "canonical")},
        {"id": "cost_book", "label": "Approved/current cost book", "evidence": ("quantity_outputs",), "blocker_terms": ("pricing", "cost", "approved", "unit-price", "price book")},
    ],
}


def _text_values(records: Iterable[Any]) -> List[str]:
    values: List[str] = []
    for item in records:
        if isinstance(item, dict):
            values.extend(
                safe_str(item.get(key))
                for key in ("area", "field", "message", "reason", "what_failed", "blocker", "input")
            )
        else:
            values.append(safe_str(item))
    return [value for value in values if value]


def _has_term(values: Sequence[str], terms: Sequence[str]) -> bool:
    lowered = " | ".join(values).lower()
    return any(term.lower() in lowered for term in terms)


def _dependency_status(engine_id: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    standards = safe_dict(meta.get("standards_package") or meta.get("design_standards") or meta.get("jurisdiction_standards"))
    survey = safe_dict(meta.get("survey_control_package") or meta.get("survey_control"))
    existing = safe_dict(meta.get("existing_conditions_summary") or meta.get("existing_conditions_package"))
    terrain = safe_dict(meta.get("grading") or meta.get("grading_summary") or meta.get("grading_detail"))
    source_confidence = safe_dict(meta.get("source_confidence_map_v1"))
    return {
        "standards_dependency": {
            "required": engine_id in {"grading", "storm_pipe", "hydrology", "sanitary", "water", "roadway_corridor", "quantity"},
            "status": safe_str(standards.get("status"), "missing" if not standards else "present"),
            "production_usable": standards.get("production_usable") is True,
        },
        "survey_control_dependency": {
            "required": engine_id in {"grading", "storm_pipe", "hydrology", "sanitary", "water", "roadway_corridor", "quantity"},
            "status": safe_str(survey.get("status"), "missing" if not survey else "present"),
            "verified": bool(
                survey.get("control_verified")
                or survey.get("verified")
                or survey.get("production_usable") is True
                or safe_dict(existing.get("survey")).get("ready")
            ),
        },
        "terrain_dependency": {
            "required": engine_id in {"grading", "storm_pipe", "hydrology", "sanitary", "water", "roadway_corridor"},
            "status": safe_str(
                terrain.get("source_quality")
                or safe_dict(terrain.get("existing_surface")).get("source_quality")
                or safe_dict(existing.get("terrain_source_confidence")).get("label"),
                "missing" if not terrain and not existing else "present",
            ),
            "tin_or_surface_present": bool(
                terrain.get("existing_surface")
                or terrain.get("proposed_surface")
                or safe_dict(existing.get("terrain_source_confidence"))
            ),
        },
        "source_confidence": deepcopy(safe_dict(source_confidence.get("summary")) or source_confidence),
    }


def build_engine_proof_contract(
    engine_id: str,
    *,
    meta: Dict[str, Any] | None = None,
    evidence: Sequence[Any] | None = None,
    blockers: Sequence[Any] | None = None,
    classification: str = "",
    status: str = "",
) -> Dict[str, Any]:
    evidence_values = _text_values(evidence or [])
    blocker_values = _text_values(blockers or [])
    requirements = DISCIPLINE_PROOF_REQUIREMENTS.get(engine_id, [])
    checklist: List[Dict[str, Any]] = []
    for requirement in requirements:
        evidence_terms = tuple(requirement.get("evidence") or ())
        blocker_terms = tuple(requirement.get("blocker_terms") or ())
        present = _has_term(evidence_values, evidence_terms)
        missing = not present
        if blocker_terms and _has_term(blocker_values, blocker_terms):
            missing = True
        checklist.append(
            {
                "id": safe_str(requirement.get("id")),
                "label": safe_str(requirement.get("label")),
                "status": "present" if not missing else "missing",
                "evidence_terms": list(evidence_terms),
                "blocker_terms": list(blocker_terms),
                "engineer_review_required": True,
            }
        )
    missing = [item for item in checklist if item["status"] == "missing"]
    exact_fixes = [
        f"Provide {item['label'].lower()} proof and rerun {engine_id.replace('_', ' ')} depth validation."
        for item in missing
    ]
    return {
        "version": "discipline_depth_proof_v1",
        "engine_id": engine_id,
        "classification": classification,
        "status": status,
        "engineer_review_status": ENGINEER_REVIEW_REQUIRED_LABEL,
        "engineer_review_required": True,
        "production_depth": classification == "production-depth" and not missing,
        "review_depth": classification in {"review", "production-depth"} or (bool(checklist) and len(missing) < len(checklist)),
        "proof_checklist": checklist,
        "missing_proof": missing,
        "exact_fixes": exact_fixes,
        "dependencies": _dependency_status(engine_id, safe_dict(meta)),
        "assumptions": deepcopy(safe_list(safe_dict(meta).get("assumptions") or safe_dict(meta).get("assumption_summary"))),
        "native_engine_blockers": deepcopy([safe_dict(item) for item in blockers or [] if safe_dict(item)]),
        "truth_label": "Discipline proof is deterministic review evidence only; it is not a stamp, seal, certification, or construction approval.",
    }


__all__ = ["DISCIPLINE_PROOF_REQUIREMENTS", "build_engine_proof_contract"]
