from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

from core.civil_design import civil_design_readiness

from .engine_contracts import EngineContract, engine_contracts


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _has_any(mapping: Dict[str, Any], keys: Iterable[str]) -> bool:
    return any(mapping.get(key) not in (None, "", [], {}) for key in keys)


ENGINE_SYSTEM_MAP: Dict[str, Tuple[str, ...]] = {
    "geometry": ("site",),
    "terrain_surface": ("existing_conditions",),
    "grading": ("grading", "grading_detail"),
    "drainage": ("drainage",),
    "storm_pipe": ("storm_pipes", "hydraulic_depth"),
    "sanitary": ("sanitary",),
    "water": ("utilities",),
    "utility_coordination": ("coordination",),
    "roadway_corridor": ("site", "grading_detail"),
    "structure": (),
    "earthwork": ("grading",),
    "hydrology": ("drainage", "hydraulic_depth"),
    "conflict_resolution": ("coordination",),
    "qa_validation": ("site", "grading", "drainage", "storm_pipes", "sanitary", "utilities", "coordination"),
    "quantity": (),
    "export_cad": ("cad_interop",),
    "profile_section": (),
    "gis_existing_conditions": ("existing_conditions",),
    "ai_orchestration": (),
    "reactive_model": (),
}


def _engine_evidence(engine_id: str, meta: Dict[str, Any]) -> List[str]:
    evidence: List[str] = []
    if engine_id == "geometry":
        if _has_any(meta, ("site_boundary", "lot")):
            evidence.append("site_boundary")
        if _safe_dict(meta.get("stats")).get("estimated_building_area_sf"):
            evidence.append("layout_stats")
    elif engine_id == "terrain_surface":
        grading = _safe_dict(meta.get("grading") or meta.get("grading_summary"))
        existing = _safe_dict(meta.get("existing_conditions_summary"))
        if _has_any(grading, ("existing_surface", "proposed_surface", "source_quality")):
            evidence.append("surface_metadata")
        if _safe_dict(existing.get("survey")).get("ready") or _safe_dict(existing.get("dem_lidar")).get("ready"):
            evidence.append("existing_surface_source_summary")
    elif engine_id == "grading":
        grading = _safe_dict(meta.get("grading") or meta.get("grading_summary"))
        if _has_any(grading, ("proposed_surface", "contours", "spot_grades", "low_points")):
            evidence.append("grading_outputs")
    elif engine_id == "drainage":
        drainage = _safe_dict(meta.get("drainage") or meta.get("drainage_canonical"))
        if _has_any(drainage, ("structures", "basins", "flow_paths", "low_points")):
            evidence.append("drainage_network")
    elif engine_id == "storm_pipe":
        storm = _safe_dict(meta.get("storm_pipes") or meta.get("storm_pipe_summary"))
        if _safe_list(storm.get("segments")):
            evidence.append("storm_segments")
        if _safe_dict(storm.get("hydraulic_validation")).get("valid"):
            evidence.append("hydraulic_validation")
    elif engine_id == "sanitary":
        sanitary = _safe_dict(meta.get("sanitary") or meta.get("sanitary_summary"))
        if _safe_list(sanitary.get("segments")):
            evidence.append("sanitary_segments")
        if _safe_dict(sanitary.get("network_validation")).get("valid"):
            evidence.append("network_validation")
    elif engine_id == "water":
        utilities = _safe_dict(meta.get("utilities") or meta.get("utility_summary"))
        hooks = _safe_dict(utilities.get("conflict_hooks"))
        if _safe_list(utilities.get("segments")) or _safe_list(hooks.get("utility_segments")):
            evidence.append("utility_segments")
    elif engine_id in {"utility_coordination", "conflict_resolution"}:
        coordination = _safe_dict(meta.get("coordination") or meta.get("coordination_summary"))
        if coordination:
            evidence.append("coordination_summary")
        if _safe_list(coordination.get("resolution_history")):
            evidence.append("resolution_history")
    elif engine_id == "roadway_corridor":
        if _has_any(meta, ("alignments", "profiles", "cross_sections")):
            evidence.append("alignment_or_sheet_views")
    elif engine_id == "structure":
        if _has_any(meta, ("structure_summary", "retaining_walls", "foundations", "bridge_interfaces", "structure_conflicts")):
            evidence.append("structure_outputs")
    elif engine_id == "earthwork":
        if _has_any(meta, ("earthwork", "quantities")):
            evidence.append("earthwork_or_quantities")
    elif engine_id == "hydrology":
        drainage = _safe_dict(meta.get("drainage") or meta.get("drainage_canonical"))
        if _has_any(drainage, ("hydrology", "detention_routing", "basins")):
            evidence.append("hydrology_or_detention")
    elif engine_id == "qa_validation":
        if _has_any(meta, ("qa", "truth_audit", "civil_design_readiness", "manual_validation")):
            evidence.append("qa_truth_outputs")
    elif engine_id == "quantity":
        quantities = _safe_dict(meta.get("quantities"))
        if _has_any(quantities, ("totals", "quantity_audit", "explain")):
            evidence.append("quantity_outputs")
    elif engine_id == "export_cad":
        if _has_any(meta, ("export_audit", "cad_interop", "sheet_registry")):
            evidence.append("export_metadata")
    elif engine_id == "profile_section":
        if _has_any(meta, ("profiles", "cross_sections", "sheet_registry")):
            evidence.append("profile_section_outputs")
    elif engine_id == "gis_existing_conditions":
        existing = _safe_dict(meta.get("existing_conditions_summary"))
        if _has_any(meta, ("survey", "gis_layers", "existing_conditions")) or existing:
            evidence.append("existing_condition_sources")
        if _safe_dict(existing.get("coordinate_system")).get("ready"):
            evidence.append("coordinate_system")
    elif engine_id == "ai_orchestration":
        if _has_any(meta, ("routing", "planner_workflow", "assumption_summary")):
            evidence.append("workflow_metadata")
    elif engine_id == "reactive_model":
        if _has_any(meta, ("stage_completeness", "stage_results", "manager_export", "reactive_update_report")):
            evidence.append("stage_and_dirty_state")
    return evidence


def _production_gaps_for_systems(civil_readiness: Dict[str, Any], system_names: Sequence[str]) -> List[Dict[str, Any]]:
    gaps = []
    if not system_names:
        return gaps
    area_aliases = {
        "hydraulic_depth": {"hydraulics"},
        "cad_interop": {"cad_interop"},
        "existing_conditions": {"existing_conditions"},
        "grading_detail": {"grading_detail"},
        "optimization": {"optimization"},
        "standards": {"standards"},
    }
    wanted = set(system_names)
    for name in system_names:
        wanted.update(area_aliases.get(name, set()))
    for item in _safe_list(civil_readiness.get("production_blockers")):
        rec = _safe_dict(item)
        area = _safe_str(rec.get("area"))
        if area in wanted or not wanted:
            gaps.append(deepcopy(rec))
    return gaps


def _missing_for_systems(civil_readiness: Dict[str, Any], system_names: Sequence[str]) -> List[Dict[str, Any]]:
    missing = []
    wanted = set(system_names)
    for item in _safe_list(civil_readiness.get("missing_requirements")):
        rec = _safe_dict(item)
        system = _safe_str(rec.get("system"))
        if system in wanted:
            missing.append(deepcopy(rec))
    return missing


def _warnings_for_systems(civil_readiness: Dict[str, Any], system_names: Sequence[str]) -> List[Dict[str, Any]]:
    warnings = []
    wanted = set(system_names)
    for item in _safe_list(civil_readiness.get("warnings")):
        rec = _safe_dict(item)
        system = _safe_str(rec.get("system"))
        if system in wanted:
            warnings.append(deepcopy(rec))
    return warnings


def _depth_validation_for_engine(engine_id: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    validations = _safe_dict(meta.get("depth_validation"))
    if engine_id == "storm_pipe":
        return _safe_dict(validations.get("stormwater"))
    if engine_id == "water":
        return _safe_dict(validations.get("water"))
    if engine_id == "roadway_corridor":
        return _safe_dict(validations.get("roadway_corridor"))
    return {}


def _depth_blockers_for_engine(engine_id: str, meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    validation = _depth_validation_for_engine(engine_id, meta)
    if not validation or validation.get("production_ready"):
        return []
    area = {
        "storm_pipe": "storm_depth",
        "water": "water_depth",
        "roadway_corridor": "roadway_depth",
    }.get(engine_id, "engine_depth")
    return [
        {
            "area": area,
            "field": "depth_validation",
            "message": _safe_str(message),
            "severity": "blocker",
        }
        for message in _safe_list(validation.get("blockers"))
        if _safe_str(message)
    ]


def _explicit_blockers_for_engine(engine_id: str, meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    blockers: List[Dict[str, Any]] = []
    if engine_id == "qa_validation":
        truth_audit = _safe_dict(meta.get("truth_audit"))
        if truth_audit and truth_audit.get("success") is not True:
            blockers.append(
                {
                    "area": "qa_validation",
                    "field": "truth_audit",
                    "message": "QA readiness is blocked because the canonical truth audit failed.",
                    "severity": "blocker",
                }
            )
        manual_validation = _safe_dict(meta.get("manual_validation"))
        if manual_validation and manual_validation.get("success") is not True:
            blockers.append(
                {
                    "area": "qa_validation",
                    "field": "manual_validation",
                    "message": "QA readiness is blocked because manual validation gates failed.",
                    "severity": "blocker",
                }
            )
    elif engine_id == "quantity":
        quantities = _safe_dict(meta.get("quantities"))
        explain = _safe_dict(quantities.get("explain"))
        meta_summary = _safe_dict(explain.get("meta_summary"))
        cost = _safe_dict(meta.get("cost_estimate"))
        cost_explain = _safe_dict(cost.get("explain"))
        if quantities and quantities.get("success") is False:
            blockers.append(
                {
                    "area": "quantity",
                    "field": "quantity_success",
                    "message": "Quantity readiness is blocked because the quantity engine reported failure.",
                    "severity": "blocker",
                }
            )
        if meta_summary and meta_summary.get("quantity_traceability_complete") is False:
            blockers.append(
                {
                    "area": "quantity",
                    "field": "quantity_traceability",
                    "message": "Quantity readiness is blocked because material takeoff values are not traceable to canonical source IDs.",
                    "severity": "blocker",
                }
            )
        if _safe_dict(explain.get("trace_gaps")):
            blockers.append(
                {
                    "area": "quantity",
                    "field": "trace_gaps",
                    "message": "Quantity readiness is blocked by unresolved source trace gaps.",
                    "severity": "blocker",
                }
            )
        if not cost:
            blockers.append(
                {
                    "area": "quantity",
                    "field": "cost_estimate",
                    "message": "Quantity readiness is blocked because no cost estimate has been generated from the takeoff.",
                    "severity": "blocker",
                }
            )
        elif cost.get("success") is False:
            blockers.append(
                {
                    "area": "quantity",
                    "field": "cost_success",
                    "message": "Quantity readiness is blocked because the cost engine reported review-only or failed cost output.",
                    "severity": "blocker",
                }
            )
        if _safe_dict(cost_explain.get("trace_gaps")):
            blockers.append(
                {
                    "area": "quantity",
                    "field": "cost_traceability",
                    "message": "Cost readiness is blocked because priced quantities are not traceable to canonical source IDs.",
                    "severity": "blocker",
                }
            )
        if _safe_dict(cost_explain.get("pricing_coverage_gaps")):
            blockers.append(
                {
                    "area": "quantity",
                    "field": "pricing_coverage",
                    "message": "Cost readiness is blocked because one or more positive quantities are missing from the production unit-price book.",
                    "severity": "blocker",
                }
            )
        pricing = _safe_dict(cost_explain.get("pricing"))
        if pricing and pricing.get("production_usable") is not True:
            blockers.append(
                {
                    "area": "quantity",
                    "field": "pricing_source",
                    "message": "Cost readiness is blocked for production because unit prices are concept defaults or lack production source approval.",
                    "severity": "blocker",
                }
            )
    elif engine_id == "export_cad":
        export_audit = _safe_dict(meta.get("export_audit"))
        if export_audit and (export_audit.get("ready") is False or export_audit.get("production_export_ready") is False or export_audit.get("export_blocked") is True):
            blockers.append(
                {
                    "area": "cad_interop",
                    "field": "export_audit",
                    "message": "Export readiness is blocked because the export audit is not production-ready.",
                    "severity": "blocker",
                }
            )
        traceability = _safe_dict(export_audit.get("canonical_id_traceability"))
        if traceability and traceability.get("ready") is not True:
            blockers.append(
                {
                    "area": "cad_interop",
                    "field": "canonical_id_traceability",
                    "message": "Export readiness is blocked because exported objects are not fully mapped to canonical IDs.",
                    "severity": "blocker",
                }
            )
    elif engine_id == "reactive_model":
        reactive = _safe_dict(meta.get("reactive_update_report"))
        if reactive and (reactive.get("export_blocked") is True or _safe_list(reactive.get("post_rerun_stale_outputs"))):
            blockers.append(
                {
                    "area": "reactive_model",
                    "field": "stale_outputs",
                    "message": "Reactive readiness is blocked because downstream outputs remain stale after rerun.",
                    "severity": "blocker",
                }
            )
        if reactive and (reactive.get("post_rerun_production_ready") is False or _safe_list(reactive.get("post_rerun_release_blockers"))):
            blockers.append(
                {
                    "area": "reactive_model",
                    "field": "post_rerun_release_blockers",
                    "message": "Reactive readiness is blocked because the post-rerun release review still has blockers.",
                    "severity": "blocker",
                }
            )
    elif engine_id == "structure":
        structures = _safe_dict(meta.get("structures") or meta.get("structure_summary"))
        conflicts = _safe_list(meta.get("structure_conflicts")) or _safe_list(structures.get("structure_conflicts"))
        unresolved = [
            _safe_dict(item)
            for item in conflicts
            if _safe_dict(item).get("resolved") is not True and _safe_str(_safe_dict(item).get("status")).lower() not in {"resolved", "accepted"}
        ]
        if unresolved:
            blockers.append(
                {
                    "area": "structure",
                    "field": "structure_conflicts",
                    "message": "Structure readiness is blocked because unresolved structure conflicts remain.",
                    "severity": "blocker",
                }
            )
    return blockers


def _contract_gate_status(contract: EngineContract, *, production_ready: bool, evidence: Sequence[str], production_gaps: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    status = "passed" if production_ready else ("blocked" if production_gaps else "pending")
    return [
        {
            "gate": gate,
            "status": status,
            "evidence": list(evidence),
        }
        for gate in contract.production_readiness_gates
    ]


def evaluate_engine_readiness(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = _safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else _safe_dict(plan_or_meta)
    civil = _safe_dict(meta.get("civil_design_readiness")) or civil_design_readiness(plan_or_meta)
    engine_rows: Dict[str, Dict[str, Any]] = {}
    blocked: List[str] = []
    production_blocked: List[str] = []
    review: List[str] = []
    concept_ready: List[str] = []
    no_evidence: List[str] = []

    for contract in engine_contracts():
        systems = ENGINE_SYSTEM_MAP.get(contract.engine_id, ())
        evidence = _engine_evidence(contract.engine_id, meta)
        missing = _missing_for_systems(civil, systems)
        warnings = _warnings_for_systems(civil, systems)
        production_gaps = _production_gaps_for_systems(civil, systems)
        depth_validation = _depth_validation_for_engine(contract.engine_id, meta)
        if depth_validation.get("production_ready"):
            evidence.append("depth_validation")
        production_gaps.extend(_depth_blockers_for_engine(contract.engine_id, meta))
        production_gaps.extend(_explicit_blockers_for_engine(contract.engine_id, meta))

        if missing:
            status = "blocked"
            blocked.append(contract.engine_id)
        elif production_gaps:
            status = "concept_ready_needs_production_depth"
            production_blocked.append(contract.engine_id)
            concept_ready.append(contract.engine_id)
        elif not evidence:
            status = "not_evidenced"
            no_evidence.append(contract.engine_id)
        elif warnings:
            status = "needs_engineering_review"
            review.append(contract.engine_id)
            concept_ready.append(contract.engine_id)
        else:
            status = "production_ready"
            concept_ready.append(contract.engine_id)

        production_ready = status == "production_ready"
        engine_rows[contract.engine_id] = {
            "engine_id": contract.engine_id,
            "name": contract.name,
            "maturity": contract.maturity,
            "status": status,
            "stage_name": contract.stage_name,
            "canonical_owns": sorted(contract.owns),
            "read_dependencies": sorted(contract.reads),
            "dirty_downstream": sorted(contract.dirty_downstream),
            "evidence": list(evidence),
            "missing_requirements": missing,
            "warnings": warnings,
            "production_blockers": production_gaps,
            "manual_mode_forbidden": list(contract.manual_mode_forbidden),
            "production_gate_status": _contract_gate_status(
                contract,
                production_ready=production_ready,
                evidence=evidence,
                production_gaps=production_gaps,
            ),
            "final_capabilities": list(contract.final_capabilities),
            "golden_scenarios": list(contract.golden_scenarios),
        }

    production_ready_ids = [
        engine_id
        for engine_id, row in engine_rows.items()
        if row.get("status") == "production_ready"
    ]
    blocked_or_unproven: Set[str] = set(blocked) | set(production_blocked) | set(no_evidence)
    return {
        "contract_version": "engine_contracts_v1",
        "engine_count": len(engine_rows),
        "production_ready": not blocked_or_unproven and len(production_ready_ids) == len(engine_rows),
        "concept_ready_count": len(set(concept_ready)),
        "production_ready_count": len(production_ready_ids),
        "blocked_engine_ids": sorted(set(blocked)),
        "production_blocked_engine_ids": sorted(set(production_blocked)),
        "not_evidenced_engine_ids": sorted(set(no_evidence)),
        "review_engine_ids": sorted(set(review)),
        "engines": engine_rows,
        "summary": {
            "civil_readiness_status": _safe_str(civil.get("status")),
            "civil_production_ready": bool(civil.get("production_ready")),
            "most_important_backend_gaps": [
                {
                    "engine_id": engine_id,
                    "status": engine_rows[engine_id]["status"],
                    "first_missing": (engine_rows[engine_id]["missing_requirements"] or engine_rows[engine_id]["production_blockers"] or [{}])[0],
                }
                for engine_id in sorted(blocked_or_unproven)[:10]
            ],
        },
    }


__all__ = ["ENGINE_SYSTEM_MAP", "evaluate_engine_readiness"]
