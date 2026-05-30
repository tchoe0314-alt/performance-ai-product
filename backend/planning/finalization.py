from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from core.project_manager import ProjectManager

from .common import canonical_stage_name, canonical_state_integrity, dedupe_keep_order, lower_text, polyline_length, safe_dict, safe_float, safe_int, safe_list, safe_str
from .field_contract import unwrap_fields_for_execution
from .production_depth import build_optimization_alternatives
from .runtime import _lot_area


def build_optimization_summary(parsed: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan.get("meta"))
    planner_score = safe_dict(meta.get("planner_score"))
    weighted = safe_dict(planner_score.get("weighted_components"))
    quantities = safe_dict(safe_dict(meta.get("quantities")).get("totals"))
    grading = safe_dict(meta.get("grading"))
    earthwork = safe_dict(grading.get("earthwork"))
    storm = safe_dict(meta.get("storm_pipes"))
    storm_stats = safe_dict(storm.get("stats"))
    utilities = safe_dict(meta.get("utilities"))
    exec_payload = safe_dict(unwrap_fields_for_execution(parsed))
    parking_program = safe_dict(meta.get("parking_program"))

    lot = safe_dict(exec_payload.get("lot"))
    lot_area_sf = max(
        safe_float(lot.get("w"), 0.0) * safe_float(lot.get("h"), 0.0),
        safe_float(quantities.get("lot_area_sf"), 0.0),
        1.0,
    )
    site_plan = safe_dict(exec_payload.get("site_plan"))
    parking_target = max(
        safe_int(site_plan.get("parking_count"), 0),
        safe_int(parking_program.get("target_count"), 0),
    )
    parking_actual = max(
        safe_int(quantities.get("estimated_parking_stalls"), 0),
        safe_int(parking_program.get("actual_count"), 0),
        safe_int(parking_program.get("parking_actual"), 0),
    )

    if parking_target > 0:
        parking_fit_score = max(0.0, min(100.0, (parking_actual / max(parking_target, 1)) * 100.0))
    elif parking_actual > 0:
        parking_fit_score = 75.0
    else:
        parking_fit_score = 0.0

    net_cf = safe_float(earthwork.get("net_cf"), 0.0)
    earthwork_balance_score = max(0.0, 100.0 - min(abs(net_cf) / 5000.0 * 100.0, 100.0))

    deficient = safe_int(storm_stats.get("deficient_count"), 0)
    marginal = safe_int(storm_stats.get("marginal_count"), 0)
    max_capacity_ratio = safe_float(storm.get("max_capacity_ratio"), 0.0)
    drainage_capacity_score = max(
        0.0,
        100.0 - deficient * 25.0 - marginal * 10.0 - max(0.0, max_capacity_ratio - 0.95) * 100.0,
    )

    storm_pipe_length_ft = max(
        safe_float(quantities.get("pipe_length_ft"), 0.0),
        safe_float(storm_stats.get("total_pipe_length_ft"), 0.0),
    )
    utility_length_ft = safe_float(quantities.get("utility_length_ft"), 0.0)
    sanitary_length_ft = safe_float(quantities.get("sanitary_length_ft"), 0.0)
    total_linear_utility_ft = storm_pipe_length_ft + utility_length_ft + sanitary_length_ft
    normalized_linear_density = total_linear_utility_ft / max(math.sqrt(lot_area_sf), 1.0)
    pipe_efficiency_score = max(0.0, 100.0 - min(normalized_linear_density * 6.0, 100.0))

    utility_coordination = safe_dict(utilities.get("coordination"))
    utility_efficiency_score = max(
        0.0,
        100.0
        - safe_int(utility_coordination.get("unresolved_conflict_count"), 0) * 18.0
        - max(0.0, 3.0 - safe_float(utilities.get("min_cover_ft"), 0.0)) * 12.0,
    )

    component_scores = {
        "parking_fit": round(parking_fit_score, 1),
        "earthwork_balance": round(earthwork_balance_score, 1),
        "drainage_capacity": round(drainage_capacity_score, 1),
        "pipe_efficiency": round(pipe_efficiency_score, 1),
        "utility_efficiency": round(utility_efficiency_score, 1),
    }
    overall_score = round(sum(component_scores.values()) / max(len(component_scores), 1), 1)

    optimization_goals = safe_dict(exec_payload.get("optimization_goals"))
    active_goal = safe_str(optimization_goals.get("goal")) or safe_str(meta.get("optimize_goal")) or "balanced"
    recommendations: List[str] = []
    if parking_target > 0 and parking_actual < parking_target:
        recommendations.append(
            f"Parking program is below target by {max(parking_target - parking_actual, 0)} stalls; favor layout efficiency before adding corridor length."
        )
    if earthwork_balance_score < 70.0:
        recommendations.append("Earthwork imbalance is still high; favor grading refinement and pad/road tie-in smoothing.")
    if drainage_capacity_score < 75.0:
        recommendations.append("Storm demand is pressuring capacity; prioritize basin release, trunk sizing, or catchment redistribution.")
    if pipe_efficiency_score < 70.0:
        recommendations.append("Utility and pipe runs are long for the site size; look for shorter trunk alignments or tighter corridor grouping.")
    if utility_efficiency_score < 80.0:
        recommendations.append("Utility coordination still carries efficiency risk; reduce unresolved crossings and shallow cover exposure.")
    if not recommendations:
        recommendations.append("Current design is reasonably balanced across parking, grading, drainage, and utility efficiency.")

    return build_optimization_alternatives({
        "active_goal": active_goal or "balanced",
        "planner_score_total": round(safe_float(planner_score.get("total"), 0.0), 3),
        "weighted_components": weighted,
        "component_scores": component_scores,
        "overall_score": overall_score,
        "metrics": {
            "parking_target": parking_target,
            "parking_actual": parking_actual,
            "earthwork_net_cf": round(net_cf, 3),
            "storm_pipe_length_ft": round(storm_pipe_length_ft, 3),
            "utility_length_ft": round(utility_length_ft, 3),
            "sanitary_length_ft": round(sanitary_length_ft, 3),
            "total_linear_utility_ft": round(total_linear_utility_ft, 3),
            "lot_area_sf": round(lot_area_sf, 3),
            "normalized_linear_density": round(normalized_linear_density, 3),
            "storm_deficient_count": deficient,
            "storm_marginal_count": marginal,
            "max_capacity_ratio": round(max_capacity_ratio, 3),
        },
        "recommendations": recommendations[:4],
    })


def requested_deliverables(parsed: Dict[str, Any]) -> List[str]:
    return dedupe_keep_order([lower_text(item) for item in safe_list(parsed.get("deliverables")) if lower_text(item)])


def _truth_integrity_stages(parsed: Dict[str, Any], plan: Dict[str, Any]) -> List[str]:
    meta = safe_dict(plan.get("meta"))
    stage_alias = {
        "storm": "storm_pipes",
        "storm_pipe_summary": "storm_pipes",
        "storm_pipe_gate": "storm_pipes",
        "utility": "utilities",
        "utility_network": "utilities",
        "utility_gate": "utilities",
        "coordination_resolution": "coordination",
        "coordination_gate": "coordination",
        "grading_gate": "grading",
        "drainage_gate": "drainage",
        "sanitary_gate": "sanitary",
        "sheets": "cross_sections",
    }

    stages: List[str] = []
    for key in (
        "grading",
        "drainage",
        "storm_pipes",
        "sanitary",
        "utilities",
        "coordination",
        "profiles",
        "cross_sections",
        "parking_program",
    ):
        value = meta.get(key)
        if safe_dict(value) or safe_list(value):
            stages.append(key)

    stage_completeness = safe_dict(meta.get("stage_completeness"))
    for name in safe_list(stage_completeness.get("required_stage_names")):
        stage_name = stage_alias.get(safe_str(name), safe_str(name))
        if stage_name:
            stages.append(stage_name)
    for name in safe_dict(stage_completeness.get("required_stage_status")).keys():
        stage_name = stage_alias.get(safe_str(name), safe_str(name))
        if stage_name:
            stages.append(stage_name)

    requested = requested_deliverables(parsed)
    if any("grading" in item or "contour" in item or "spot" in item for item in requested):
        stages.append("grading")
    if any("drainage" in item or "basin" in item or "inlet" in item for item in requested):
        stages.extend(["drainage", "storm_pipes"])
    if any("storm" in item or "pipe" in item for item in requested):
        stages.extend(["drainage", "storm_pipes"])
    if any("sanitary" in item or "sewer" in item for item in requested):
        stages.append("sanitary")
    if any("utility" in item or "water" in item for item in requested):
        stages.append("utilities")
    if any("profile" in item for item in requested):
        stages.append("profiles")
    if any("section" in item for item in requested):
        stages.append("cross_sections")

    return dedupe_keep_order([item for item in stages if item])


def _completed_integrity_stages(plan: Dict[str, Any]) -> List[str]:
    meta = safe_dict(plan.get("meta"))
    completeness = safe_dict(meta.get("stage_completeness"))
    completed: List[str] = []

    def _benign_skip_message(message: str) -> bool:
        lowered = safe_str(message).strip().lower()
        if not lowered:
            return False
        return any(
            token in lowered
            for token in (
                "was not requested",
                "omitted by user intent",
                "source=omit",
                "no profile or cross-section deliverables were requested",
            )
        )

    for name, status in safe_dict(completeness.get("required_stage_status")).items():
        if safe_str(status).lower() == "complete":
            completed.append(canonical_stage_name(name))
    for row in safe_list(meta.get("stage_results")):
        rec = safe_dict(row)
        stage_name = safe_str(rec.get("stage_name"))
        row_meta = safe_dict(rec.get("meta"))
        row_completeness = safe_str(row_meta.get("completeness")).lower()
        if bool(rec.get("success")) and row_completeness == "complete":
            completed.append(canonical_stage_name(stage_name))
        elif bool(rec.get("success")) and _benign_skip_message(safe_str(rec.get("message"))):
            completed.append(canonical_stage_name(stage_name))
    return dedupe_keep_order([item for item in completed if item])


def parking_program_context(parsed: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    site_plan = safe_dict(unwrap_fields_for_execution(parsed.get("site_plan")))
    stats = safe_dict(safe_dict(plan.get("meta")).get("stats"))
    manager_metrics = safe_dict(safe_dict(safe_dict(plan.get("meta")).get("manager_export")).get("metrics"))
    actions = safe_list(plan.get("actions"))
    explicit_target = max(0, safe_int(site_plan.get("parking_count"), 0))
    building_area = max(
        0.0,
        safe_float(site_plan.get("building_area_sf"), 0.0),
        safe_float(stats.get("estimated_building_area_sf"), 0.0),
    )
    retail_area = max(0.0, safe_float(site_plan.get("retail_area_sf"), 0.0))
    office_area = max(0.0, safe_float(site_plan.get("office_area_sf"), 0.0))
    multifamily_units = max(0, safe_int(site_plan.get("dwelling_units"), 0))
    project_type = lower_text(parsed.get("project_type") or parsed.get("site_type"))

    target = 0
    method = "undefined"
    reason = ""
    source_fields: List[str] = []

    if explicit_target > 0:
        target = explicit_target
        method = "explicit_input"
        reason = "Parking target came directly from manual site_plan.parking_count."
        source_fields = ["site_plan.parking_count"]
    elif project_type in {"commercial_pad", "retail_site", "strip_center"}:
        proxy_area = retail_area or building_area
        target = max(1, int(round(proxy_area / 275.0))) if proxy_area > 0 else 0
        method = "program_rule"
        reason = "Retail/commercial parking target derived from a concept 1 stall per 275 sf rule."
        source_fields = ["project_type", "site_plan.retail_area_sf", "site_plan.building_area_sf"]
    elif project_type in {"office_site"}:
        target = max(1, int(round(building_area / 300.0))) if building_area > 0 else 0
        method = "program_rule"
        reason = "Office parking target derived from a concept 1 stall per 300 sf rule."
        source_fields = ["project_type", "site_plan.building_area_sf"]
    elif project_type in {"multifamily_site"}:
        if multifamily_units > 0:
            target = max(1, int(round(multifamily_units * 1.75)))
            source_fields = ["project_type", "site_plan.dwelling_units"]
        elif building_area > 0:
            target = max(1, int(round(building_area / 625.0)))
            source_fields = ["project_type", "site_plan.building_area_sf"]
        method = "program_rule"
        reason = "Multifamily parking target derived from dwelling units when available, otherwise a concept building-area proxy."
    elif project_type in {"mixed_use", "mixed_use_site"}:
        mixed_target = 0.0
        if retail_area > 0:
            mixed_target += retail_area / 250.0
            source_fields.append("site_plan.retail_area_sf")
        if office_area > 0:
            mixed_target += office_area / 300.0
            source_fields.append("site_plan.office_area_sf")
        if multifamily_units > 0:
            mixed_target += multifamily_units * 1.5
            source_fields.append("site_plan.dwelling_units")
        if mixed_target <= 0.0 and building_area > 0:
            mixed_target = building_area / 300.0
            source_fields.append("site_plan.building_area_sf")
        target = max(1, int(round(mixed_target))) if mixed_target > 0.0 else 0
        method = "program_rule"
        reason = "Mixed-use parking target derived from retail, office, and residential program proxies."
        source_fields = ["project_type"] + source_fields
    elif project_type in {"industrial_site"}:
        target = max(1, int(round(building_area / 800.0))) if building_area > 0 else 0
        method = "program_rule"
        reason = "Industrial parking target derived from a concept 1 stall per 800 sf rule."
        source_fields = ["project_type", "site_plan.building_area_sf"]

    canonical_achieved = max(0, safe_int(safe_dict(manager_metrics.get("parking_count")).get("value"), 0))
    achieved_count = canonical_achieved
    if achieved_count <= 0:
        achieved_count = max(
            0,
            safe_int(safe_dict(safe_dict(plan.get("meta")).get("quantities")).get("totals", {}).get("estimated_parking_stalls"), 0),
            _estimated_parking_stalls_from_actions(actions),
        )
    variance = achieved_count - target if target > 0 else None
    return {
        "requested_target": target,
        "explicit_target": explicit_target,
        "program_target": target if method == "program_rule" else 0,
        "achieved_count": achieved_count,
        "variance": variance,
        "method": method,
        "reason": reason,
        "traceable": target > 0 and bool(method and source_fields),
        "source_fields": dedupe_keep_order(source_fields),
    }


def canonical_truth_audit(
    parsed: Dict[str, Any],
    plan: Dict[str, Any],
    *,
    manager: Optional[ProjectManager] = None,
    sanitary_requested: Callable[[Dict[str, Any]], bool],
) -> Dict[str, Any]:
    meta = safe_dict(plan.get("meta"))
    qa_stats = safe_dict(safe_dict(meta.get("qa")).get("stats"))
    qty_totals = safe_dict(safe_dict(meta.get("quantities")).get("totals"))
    storm = safe_dict(meta.get("storm_pipes"))
    sanitary = safe_dict(meta.get("sanitary"))
    utilities = safe_dict(meta.get("utilities"))
    coordination = safe_dict(meta.get("coordination"))
    produced = produced_deliverables(plan)
    checks: List[Dict[str, Any]] = []
    accounting = canonical_area_accounting(parsed, plan)
    parking_program = parking_program_context(parsed, plan)
    engineering_layers = {"PIPE", "SAN", "STRUCTURE", "BASIN_BOUNDARY", "UTILITY", "WATER", "ROUTE"}
    mapped_actions = [
        safe_dict(action)
        for action in safe_list(plan.get("actions"))
        if safe_str(safe_dict(action).get("layer")).upper() in engineering_layers
    ]
    unmapped_actions = [
        action
        for action in mapped_actions
        if not safe_str(action.get("canonical_source_id")) or not safe_str(action.get("canonical_source_type"))
    ]
    integrity = safe_dict(meta.get("canonical_integrity"))
    if manager is not None:
        integrity = canonical_state_integrity(
            manager.project,
            manager,
            required_stages=_truth_integrity_stages(parsed, plan),
            completed_stages=_completed_integrity_stages(plan),
        )
        plan.setdefault("meta", {})["canonical_integrity"] = deepcopy(integrity)
        manager.project.meta["canonical_integrity"] = deepcopy(integrity)

    checks.append(
        {
            "code": "CANONICAL_ACCEPTED_STATE_CURRENT",
            "ok": not bool(integrity.get("blocked")),
            "severity": "error",
            "message": "Canonical outputs must be accepted, clean, and non-cache-only before QA/export can claim engineering truth.",
            "context": deepcopy(integrity),
        }
    )
    if safe_list(integrity.get("cache_differs_stages")):
        checks.append(
            {
                "code": "CANONICAL_CACHE_DIFFERS_REVIEW",
                "ok": True,
                "severity": "warning",
                "message": "Manager cache differs from accepted project meta; project meta remains authoritative.",
                "context": {
                    "cache_differs_stages": deepcopy(safe_list(integrity.get("cache_differs_stages"))),
                },
            }
        )
    consistency = safe_dict(safe_dict(coordination.get("post_resolution_validations")).get("consistency"))
    for key in ("storm_summary_current", "sanitary_summary_current", "utility_summary_current", "drainage_summary_current"):
        if key in consistency:
            checks.append(
                {
                    "code": key.upper(),
                    "ok": bool(consistency.get(key)),
                    "severity": "error",
                    "message": f"{key} must remain aligned to canonical state.",
                }
            )

    if manager is not None:
        checks.append(
            {
                "code": "CANONICAL_REFERENCE_VALID",
                "ok": not manager.assert_references_valid(),
                "severity": "error",
                "message": "Canonical ProjectManager references must remain internally valid.",
            }
        )

    if safe_list(storm.get("segments")):
        graph = safe_dict(storm.get("graph_validation"))
        storm_export_ready = bool(safe_dict(storm.get("export_validation")).get("ready"))
        storm_deliverable_requested = any(
            any(token in item for token in ("storm", "pipe"))
            for item in requested_deliverables(parsed)
        )
        checks.extend(
            [
                {
                    "code": "STORM_HYDRAULIC_COMPLETE",
                    "ok": all(key in storm for key in ("total_system_flow_cfs", "total_system_capacity_cfs", "controlling_segment", "max_capacity_ratio"))
                    and bool(safe_dict(storm.get("hydraulic_validation")).get("valid", False)),
                    "severity": "error",
                    "message": "Storm summary must expose aggregate hydraulic metrics when storm geometry exists.",
                },
                {
                    "code": "STORM_SEGMENT_DATA_COMPLETE",
                    "ok": not safe_list(storm.get("missing_data_segments")),
                    "severity": "error",
                    "message": "Storm summary must not contain geometry-only segments.",
                },
                {
                    "code": "STORM_GRAPH_VALID",
                    "ok": bool(graph.get("valid", False)),
                    "severity": "error",
                    "message": "Storm network graph must remain connected and directionally valid.",
                    "context": {
                        "disconnected_runs": deepcopy(safe_list(graph.get("disconnected_runs"))),
                        "loop_nodes": deepcopy(safe_list(graph.get("loop_nodes"))),
                        "invalid_direction_segments": deepcopy(safe_list(graph.get("invalid_direction_segments"))),
                        "orphan_nodes": deepcopy(safe_list(graph.get("orphan_nodes"))),
                    },
                },
                {
                    "code": "STORM_DELIVERABLE_MATCH",
                    "ok": (not storm_deliverable_requested and not storm_export_ready) or "storm_pipe_plan" in produced,
                    "severity": "error",
                    "message": "Storm deliverables must be present when requested or export-ready canonical storm geometry exists.",
                },
            ]
        )

    if sanitary_requested(parsed) or safe_int(sanitary.get("route_count"), 0) > 0:
        graph = safe_dict(sanitary.get("graph_validation"))
        checks.extend(
            [
                {
                    "code": "SANITARY_GRAPH_VALID",
                    "ok": bool(graph.get("valid", False)) if sanitary else False,
                    "severity": "error",
                    "message": "Sanitary network graph must remain connected and loop-safe.",
                    "context": {
                        "disconnected_runs": deepcopy(safe_list(graph.get("disconnected_runs"))),
                        "loop_nodes": deepcopy(safe_list(graph.get("loop_nodes"))),
                        "invalid_direction_segments": deepcopy(safe_list(graph.get("invalid_direction_segments"))),
                        "orphan_nodes": deepcopy(safe_list(graph.get("orphan_nodes"))),
                    },
                },
                {
                    "code": "SANITARY_SERVICE_COMPLETE",
                    "ok": not safe_list(sanitary.get("missing_service_buildings")) and bool(safe_dict(sanitary.get("network_validation")).get("valid", False)),
                    "severity": "error",
                    "message": "Sanitary canonical state must include service coverage for all served buildings.",
                },
                {
                    "code": "SANITARY_DELIVERABLE_MATCH",
                    "ok": (safe_int(sanitary.get("route_count"), 0) <= 0 and not sanitary_requested(parsed)) or ("sanitary_plan" in produced),
                    "severity": "error",
                    "message": "Sanitary deliverables must be present when canonical sanitary geometry exists.",
                },
            ]
        )

    manager_metrics = safe_dict(safe_dict(meta.get("manager_export")).get("metrics", {}))

    def segment_total_length(segments: Any) -> float:
        total = 0.0
        for segment in safe_list(segments):
            record = safe_dict(segment)
            length = safe_float(record.get("length_ft"), 0.0)
            if length <= 0.0:
                points = safe_list(record.get("path") or record.get("route_points") or record.get("points"))
                if len(points) >= 2:
                    length = polyline_length(points)
            total += max(0.0, length)
        return total

    def first_truth_value(candidates: Sequence[Tuple[str, Any]]) -> Tuple[float, str]:
        for source, value in candidates:
            number = safe_float(value, 0.0)
            if number > 0.0:
                return number, source
        return 0.0, "missing"

    def length_matches(value: Any, truth: float) -> bool:
        number = safe_float(value, 0.0)
        if truth <= 0.0:
            return True
        if number <= 0.0:
            return False
        return abs(number - truth) <= max(0.01, truth * 0.005)

    qty_pipe = safe_float(qty_totals.get("pipe_length_ft"), 0.0)
    qa_pipe = safe_float(qa_stats.get("estimated_pipe_length_ft"), 0.0)
    storm_pipe_metric = safe_float(safe_dict(manager_metrics.get("storm_pipe_length_ft")).get("value"), 0.0)
    storm_stats = safe_dict(storm.get("stats"))
    storm_truth, storm_truth_source = first_truth_value(
        [
            ("storm_pipes.total_length_ft", storm.get("total_length_ft")),
            ("storm_pipes.stats.total_length_ft", storm_stats.get("total_length_ft")),
            ("storm_pipes.stats.total_pipe_length_ft", storm_stats.get("total_pipe_length_ft")),
            ("storm_pipes.segments", segment_total_length(storm.get("segments"))),
            ("quantities.pipe_length_ft", qty_pipe),
            ("qa.estimated_pipe_length_ft", qa_pipe),
            ("manager_export.metrics.storm_pipe_length_ft", storm_pipe_metric),
        ]
    )
    checks.append(
        {
            "code": "PIPE_LENGTH_CONSISTENT",
            "ok": not (storm_truth > 0.0 and not length_matches(qty_pipe, storm_truth)),
            "severity": "error",
            "message": "Pipe length totals must agree across canonical storm, quantities, and QA state.",
            "context": {
                "truth_length_ft": round(storm_truth, 3),
                "truth_source": storm_truth_source,
                "quantity_pipe_length_ft": round(qty_pipe, 3),
                "qa_pipe_length_ft": round(qa_pipe, 3),
                "quantity_delta_ft": round(qty_pipe - storm_truth, 3) if storm_truth > 0.0 else 0.0,
                "qa_delta_ft": round(qa_pipe - storm_truth, 3) if storm_truth > 0.0 else 0.0,
            },
        }
    )
    qty_utility = safe_float(qty_totals.get("utility_length_ft"), 0.0)
    qa_utility = safe_float(qa_stats.get("estimated_utility_length_ft"), 0.0)
    utility_metric = safe_float(safe_dict(manager_metrics.get("utility_total_length_ft")).get("value"), 0.0)
    utility_stats = safe_dict(utilities.get("stats"))
    utility_hooks = safe_dict(utilities.get("conflict_hooks"))
    utility_truth, utility_truth_source = first_truth_value(
        [
            ("utilities.total_length_ft", utilities.get("total_length_ft")),
            ("utilities.stats.total_length_ft", utility_stats.get("total_length_ft")),
            ("utilities.segments", segment_total_length(utilities.get("segments"))),
            ("utilities.conflict_hooks.utility_segments", segment_total_length(utility_hooks.get("utility_segments"))),
            ("quantities.utility_length_ft", qty_utility),
            ("qa.estimated_utility_length_ft", qa_utility),
            ("manager_export.metrics.utility_total_length_ft", utility_metric),
        ]
    )
    checks.append(
        {
            "code": "UTILITY_LENGTH_CONSISTENT",
            "ok": not (utility_truth > 0.0 and not length_matches(qty_utility, utility_truth)),
            "severity": "error",
            "message": "Utility length totals must agree across canonical utility, quantities, and QA state.",
            "context": {
                "truth_length_ft": round(utility_truth, 3),
                "truth_source": utility_truth_source,
                "quantity_utility_length_ft": round(qty_utility, 3),
                "qa_utility_length_ft": round(qa_utility, 3),
                "quantity_delta_ft": round(qty_utility - utility_truth, 3) if utility_truth > 0.0 else 0.0,
                "qa_delta_ft": round(qa_utility - utility_truth, 3) if utility_truth > 0.0 else 0.0,
            },
        }
    )
    qty_sanitary = safe_float(qty_totals.get("sanitary_length_ft"), 0.0)
    sanitary_stats = safe_dict(sanitary.get("stats"))
    sanitary_metric = safe_float(safe_dict(manager_metrics.get("sanitary_total_length_ft")).get("value"), 0.0)
    sanitary_truth, sanitary_truth_source = first_truth_value(
        [
            ("sanitary.total_length_ft", sanitary.get("total_length_ft")),
            ("sanitary.stats.total_length_ft", sanitary_stats.get("total_length_ft")),
            ("sanitary.segments", segment_total_length(sanitary.get("segments"))),
            ("quantities.sanitary_length_ft", qty_sanitary),
            ("manager_export.metrics.sanitary_total_length_ft", sanitary_metric),
        ]
    )
    checks.append(
        {
            "code": "SANITARY_LENGTH_CONSISTENT",
            "ok": not (sanitary_truth > 0.0 and not length_matches(qty_sanitary, sanitary_truth)),
            "severity": "error",
            "message": "Sanitary quantities must reflect canonical sanitary geometry.",
            "context": {
                "truth_length_ft": round(sanitary_truth, 3),
                "truth_source": sanitary_truth_source,
                "quantity_sanitary_length_ft": round(qty_sanitary, 3),
                "quantity_delta_ft": round(qty_sanitary - sanitary_truth, 3) if sanitary_truth > 0.0 else 0.0,
            },
        }
    )
    checks.extend(
        [
            {
                "code": "QUANTITY_AREA_VALID",
                "ok": safe_float(accounting.get("impervious_area_sf"), 0.0) <= safe_float(accounting.get("lot_area_sf"), 0.0) + 1e-6,
                "severity": "error",
                "message": "Impervious area must not exceed canonical lot area unless explicitly reconciled.",
                "context": deepcopy(accounting),
            },
            {
                "code": "PARKING_COUNT_TRACEABLE",
                "ok": bool(parking_program.get("traceable")),
                "severity": "error",
                "message": "Parking counts must be traceable back to canonical layout intent.",
                "context": deepcopy(parking_program),
            },
            {
                "code": "CONFLICT_INTEGRITY",
                "ok": not safe_list(coordination.get("unresolved_conflicts")),
                "severity": "error",
                "message": "Canonical coordination state must not retain unresolved conflicts for a trusted result.",
                "context": {
                    "unresolved_conflict_count": len(safe_list(coordination.get("unresolved_conflicts"))),
                },
            },
            {
                "code": "EXPORT_OBJECT_MAPPING_COMPLETE",
                "ok": not unmapped_actions,
                "severity": "error",
                "message": "Engineering export actions must map back to canonical source objects.",
                "context": {
                    "unmapped_action_count": len(unmapped_actions),
                    "sample_unmapped_layers": dedupe_keep_order(safe_str(item.get("layer")).upper() for item in unmapped_actions[:8]),
                },
            },
            {
                "code": "GRADING_STATE_EFFECTIVE",
                "ok": not safe_list(safe_dict(meta.get("grading")).get("local_adjustments")) or (
                    bool(safe_dict(meta.get("grading")).get("proposed_surface")) and bool(safe_dict(meta.get("grading")).get("earthwork"))
                ),
                "severity": "error",
                "message": "Grading repairs must update canonical surface and earthwork state, not only annotations.",
            },
        ]
    )

    failing = [deepcopy(check) for check in checks if not bool(check.get("ok"))]
    weight_by_code = {
        "CANONICAL_ACCEPTED_STATE_CURRENT": 18.0,
        "CANONICAL_REFERENCE_VALID": 15.0,
        "STORM_HYDRAULIC_COMPLETE": 16.0,
        "STORM_SEGMENT_DATA_COMPLETE": 12.0,
        "STORM_GRAPH_VALID": 16.0,
        "SANITARY_GRAPH_VALID": 16.0,
        "SANITARY_SERVICE_COMPLETE": 12.0,
        "QUANTITY_AREA_VALID": 10.0,
        "PARKING_COUNT_TRACEABLE": 8.0,
        "CONFLICT_INTEGRITY": 12.0,
        "EXPORT_OBJECT_MAPPING_COMPLETE": 10.0,
        "GRADING_STATE_EFFECTIVE": 10.0,
    }
    penalty = sum(weight_by_code.get(safe_str(check.get("code")), 6.0) for check in failing)
    result = {
        "success": len(failing) == 0,
        "checks": checks,
        "failing_checks": failing,
        "summary": {
            "canonical_validity": not any(safe_str(item.get("code")) in {"CANONICAL_ACCEPTED_STATE_CURRENT", "CANONICAL_REFERENCE_VALID", "EXPORT_OBJECT_MAPPING_COMPLETE"} for item in failing),
            "hydraulic_completeness": not any(safe_str(item.get("code")).startswith("STORM_") for item in failing),
            "graph_validity": not any(safe_str(item.get("code")) in {"STORM_GRAPH_VALID", "SANITARY_GRAPH_VALID"} for item in failing),
            "quantity_alignment": not any(safe_str(item.get("code")) in {"PIPE_LENGTH_CONSISTENT", "UTILITY_LENGTH_CONSISTENT", "SANITARY_LENGTH_CONSISTENT", "QUANTITY_AREA_VALID"} for item in failing),
            "conflict_integrity": not any(safe_str(item.get("code")) == "CONFLICT_INTEGRITY" for item in failing),
            "stale_output_blocking": bool(integrity.get("blocked")),
        },
        "canonical_integrity": deepcopy(integrity),
        "engineering_trust_score": round(max(0.0, 100.0 - penalty), 1),
    }
    if manager is not None:
        manager.project.meta["truth_audit"] = deepcopy(result)
    return result


def finalize_engineering_trust_score(plan: Dict[str, Any], *, manual_failed: bool) -> float:
    meta = safe_dict(plan.get("meta"))
    truth_audit = safe_dict(meta.get("truth_audit"))
    completeness = safe_dict(meta.get("stage_completeness"))
    required_complete = bool(completeness.get("all_required_complete"))
    base_score = safe_float(truth_audit.get("engineering_trust_score"), 0.0)
    penalty = 0.0
    if not required_complete:
        penalty += 25.0
    if manual_failed:
        penalty += 35.0
        failure_count = len(safe_list(safe_dict(meta.get("manual_validation")).get("failures")))
        penalty += min(20.0, float(failure_count) * 2.0)
    adjusted = round(max(0.0, base_score - penalty), 1)

    updated_truth = deepcopy(truth_audit)
    updated_summary = safe_dict(updated_truth.get("summary"))
    updated_summary["required_stage_completeness"] = required_complete
    updated_summary["manual_failure_state"] = not manual_failed
    updated_truth["summary"] = updated_summary
    updated_truth["engineering_trust_score"] = adjusted
    plan.setdefault("meta", {})
    plan["meta"]["truth_audit"] = updated_truth
    return adjusted


def canonical_area_accounting(parsed: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan.get("meta"))
    qa_stats = safe_dict(safe_dict(meta.get("qa")).get("stats"))
    stats = safe_dict(meta.get("stats"))
    qty_totals = safe_dict(safe_dict(meta.get("quantities")).get("totals"))
    manager_metrics = safe_dict(safe_dict(meta.get("manager_export")).get("metrics"))
    actions = safe_list(plan.get("actions"))

    lot_area = max(
        0.0,
        _lot_area(parsed),
        safe_float(qa_stats.get("lot_area_sf"), 0.0),
        safe_float(qty_totals.get("lot_area_sf"), 0.0),
    )

    canonical_impervious_candidates = [
        safe_float(stats.get("estimated_impervious_area_sf"), 0.0),
        safe_float(qa_stats.get("estimated_impervious_area_sf"), 0.0),
        safe_float(qty_totals.get("estimated_impervious_area_sf"), 0.0),
    ]
    manager_impervious = safe_float(safe_dict(manager_metrics.get("layout_impervious_area_sf")).get("value"), 0.0)
    impervious_area = max(canonical_impervious_candidates) if canonical_impervious_candidates else 0.0

    rect_keys: Dict[Tuple[float, float, float, float], int] = {}
    impervious_rects: List[Tuple[float, float, float, float]] = []
    for action in actions:
        if lower_text(action.get("task")) != "rectangle":
            continue
        layer = safe_str(action.get("layer"), "").upper()
        label = lower_text(action.get("label"))
        if layer not in {"BUILDING", "STRUCTURE", "PARKING", "PAVEMENT", "ROAD", "WALK"} and not any(
            token in label for token in ("building", "bldg", "park", "road", "walk", "sidewalk")
        ):
            continue
        origin = safe_list(action.get("origin"))
        if len(origin) < 2:
            continue
        width = safe_float(action.get("width"), 0.0)
        height = safe_float(action.get("height"), 0.0)
        if width <= 0.0 or height <= 0.0:
            continue
        key = (round(safe_float(origin[0], 0.0), 3), round(safe_float(origin[1], 0.0), 3), round(width, 3), round(height, 3))
        rect_keys[key] = rect_keys.get(key, 0) + 1
        x = safe_float(origin[0], 0.0)
        y = safe_float(origin[1], 0.0)
        impervious_rects.append((x, y, x + width, y + height))

    duplicate_rectangles = sum(1 for count in rect_keys.values() if count > 1)
    impervious_by_action = 0.0
    if impervious_rects:
        xs = sorted({round(x1, 6) for x1, _, x2, _ in impervious_rects} | {round(x2, 6) for _, _, x2, _ in impervious_rects})
        for idx in range(len(xs) - 1):
            x_left = xs[idx]
            x_right = xs[idx + 1]
            if x_right <= x_left:
                continue
            spans: List[Tuple[float, float]] = []
            for rx1, ry1, rx2, ry2 in impervious_rects:
                if rx1 < x_right and rx2 > x_left:
                    spans.append((min(ry1, ry2), max(ry1, ry2)))
            if not spans:
                continue
            spans.sort()
            merged: List[Tuple[float, float]] = [spans[0]]
            for y1, y2 in spans[1:]:
                last_y1, last_y2 = merged[-1]
                if y1 <= last_y2:
                    merged[-1] = (last_y1, max(last_y2, y2))
                else:
                    merged.append((y1, y2))
            impervious_by_action += (x_right - x_left) * sum(max(0.0, y2 - y1) for y1, y2 in merged)
    impervious_candidates = list(canonical_impervious_candidates)
    if impervious_by_action > 0.0:
        impervious_candidates.append(impervious_by_action)
    authoritative_impervious = max(impervious_candidates) if impervious_candidates else 0.0
    impervious_area = authoritative_impervious if authoritative_impervious > 0.0 else manager_impervious
    span_candidates = impervious_candidates if authoritative_impervious > 0.0 else [manager_impervious]
    value_span = (max(span_candidates) - min(span_candidates)) if span_candidates else 0.0
    if lot_area <= 0.0:
        reason_class = "missing_lot_area"
    elif impervious_area <= lot_area and impervious_by_action <= lot_area * 1.02:
        reason_class = "balanced"
    elif duplicate_rectangles > 0:
        reason_class = "geometry_duplication"
    elif impervious_by_action > 0.0 and impervious_by_action <= lot_area and impervious_area > lot_area:
        reason_class = "accounting_bug"
    elif value_span > max(100.0, lot_area * 0.10):
        reason_class = "accounting_bug"
    elif lot_area < 1000.0 and impervious_area > lot_area * 20.0:
        reason_class = "unit_scaling_mismatch"
    else:
        reason_class = "true_overdevelopment"

    return {
        "lot_area_sf": round(lot_area, 3),
        "impervious_area_sf": round(impervious_area, 3),
        "impervious_by_action_sf": round(impervious_by_action, 3),
        "duplicate_impervious_rectangles": duplicate_rectangles,
        "reason_class": reason_class,
        "candidate_values": [round(value, 3) for value in impervious_candidates if value > 0.0],
    }


def produced_deliverables(plan: Dict[str, Any]) -> List[str]:
    actions = safe_list(plan.get("actions"))
    meta = safe_dict(plan.get("meta"))
    produced: List[str] = []
    layers = {safe_str(action.get("layer"), "").upper() for action in actions if isinstance(action, dict)}
    grading_export_ready = bool(safe_dict(safe_dict(meta.get("grading")).get("export_validation")).get("ready"))
    drainage_export_ready = bool(safe_dict(safe_dict(meta.get("drainage")).get("export_validation")).get("ready"))
    storm_export_ready = bool(safe_dict(safe_dict(meta.get("storm_pipes")).get("export_validation")).get("ready"))
    utility_export_ready = bool(safe_dict(safe_dict(meta.get("utilities")).get("export_validation")).get("ready"))

    if actions:
        produced.append("site_plan")
    if "ROAD" in layers:
        produced.append("roadway_plan")
    if grading_export_ready and any(layer in layers for layer in {"FG_CONTOUR", "EG_CONTOUR", "SPOT_FG", "DRAIN_FLOW"}):
        produced.extend(["grading_plan", "contours"])
    if grading_export_ready and "SPOT_FG" in layers:
        produced.append("spot_grades")
    if grading_export_ready and "DRAIN_FLOW" in layers:
        produced.append("flow_arrows")
    if storm_export_ready and (safe_dict(meta.get("storm_pipes")).get("pipe_count", 0) or safe_dict(meta.get("storm_pipes")).get("segments")):
        produced.append("storm_pipe_plan")
    if drainage_export_ready and any(layer in layers for layer in {"STRUCTURE", "BASIN_BOUNDARY", "PIPE"}):
        produced.append("drainage_plan")
    if utility_export_ready and safe_dict(meta.get("utilities")).get("route_count", 0) > 0:
        produced.append("utility_plan")
    sanitary = safe_dict(meta.get("sanitary"))
    utility_system = lower_text(safe_dict(meta.get("utilities")).get("system_type"))
    sanitary_ready = (
        bool(sanitary.get("success"))
        and safe_int(sanitary.get("route_count"), 0) > 0
        and bool(safe_dict(sanitary.get("graph_validation")).get("valid"))
        and bool(safe_dict(sanitary.get("network_validation")).get("valid"))
        and not safe_list(sanitary.get("missing_service_buildings"))
        and not safe_list(safe_dict(sanitary.get("service_coverage")).get("missing_buildings"))
    )
    if sanitary_ready and (safe_int(sanitary.get("route_count"), 0) > 0 or "sanitary" in utility_system or "SAN" in layers):
        produced.append("sanitary_plan")
    if safe_list(meta.get("profiles")):
        produced.extend(["profiles", "road_profile"])
    if safe_list(meta.get("cross_sections")):
        produced.append("cross_sections")
    return dedupe_keep_order(produced)


def _estimated_parking_stalls_from_actions(actions: Sequence[Dict[str, Any]]) -> int:
    parking_area = 0.0
    for action in actions:
        if not isinstance(action, dict):
            continue
        if lower_text(action.get("task")) != "rectangle":
            continue
        layer = safe_str(action.get("layer"), "").upper()
        label = lower_text(action.get("label"))
        if layer not in {"PARKING", "PAVEMENT"} and "park" not in label:
            continue
        parking_area += safe_float(action.get("width"), 0.0) * safe_float(action.get("height"), 0.0)
    if parking_area <= 0.0:
        return 0
    return max(0, int(round(parking_area / 162.0)))
