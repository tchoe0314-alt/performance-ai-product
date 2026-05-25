from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from core.config import (
    DEFAULT_LOT_HEIGHT,
    DEFAULT_LOT_WIDTH,
    DEFAULT_LOT_X,
    DEFAULT_LOT_Y,
    DEFAULT_SETBACK,
    PIPE_INTENSITY_IN_HR,
)
from core.geometry_core import EngineeringDomain, EngineeringObject, Point3D, ProjectModel, ZoneType, _snapshot_serialize, rect_zone
from core.project_manager import ConflictSeverity, DependencyState, ProjectManager
from engines.hydrology_engine import RationalArea, compute_rational_method

from .common import clamp, dedupe_keep_order, lower_text, polyline_length, rect_area, safe_dict, safe_float, safe_int, safe_list, safe_str
from .field_contract import field_path_is_omitted, preserve_field_states, resolve_field, unwrap_fields_for_execution


PLANNER_STAGE_ORDER: List[str] = [
    "layout",
    "grading",
    "drainage",
    "storm_pipes",
    "sanitary",
    "utility_network",
    "coordination_resolution",
    "earthwork",
    "sheets",
    "qa",
]

PLANNER_STAGE_DEPENDENCIES: Dict[str, List[str]] = {
    "layout": [],
    "grading": ["layout"],
    "drainage": ["grading"],
    "storm_pipes": ["drainage"],
    "sanitary": ["layout", "grading", "storm_pipes"],
    "utility_network": ["storm_pipes", "sanitary", "grading"],
    "coordination_resolution": ["storm_pipes", "sanitary", "utility_network", "grading"],
    "earthwork": ["utility_network", "grading", "coordination_resolution"],
    "sheets": ["grading", "storm_pipes", "sanitary", "coordination_resolution"],
    "qa": ["layout", "grading", "drainage", "storm_pipes", "sanitary", "utility_network", "earthwork", "coordination_resolution"],
}


@dataclass
class QualityIssue:
    code: str
    severity: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanQualityReport:
    issues: List[QualityIssue] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    checks_run: List[str] = field(default_factory=list)

    def add(self, code: str, severity: str, message: str, **context: Any) -> None:
        self.issues.append(QualityIssue(code=code, severity=severity, message=message, context=dict(context)))

    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if lower_text(issue.severity) == "warning")

    def error_count(self) -> int:
        return sum(1 for issue in self.issues if lower_text(issue.severity) == "error")

    def to_meta(self) -> Dict[str, Any]:
        return {
            "checks_run": list(self.checks_run),
            "stats": deepcopy(self.stats),
            "issues": [
                {"code": issue.code, "severity": issue.severity, "message": issue.message, "context": deepcopy(issue.context)}
                for issue in self.issues
            ],
            "warning_count": self.warning_count(),
            "error_count": self.error_count(),
        }


@dataclass
class RoutingDecision:
    path: str
    reasons: List[str]


@dataclass
class PlannerStageResult:
    stage_name: str
    success: bool
    message: str = ""
    warnings: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlannerExecutionContext:
    parsed: Dict[str, Any]
    manager: ProjectManager
    route: RoutingDecision
    stage_results: List[PlannerStageResult] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    pass_index: int = 0
    changed_targets: List[str] = field(default_factory=list)
    explanation: Dict[str, Any] = field(default_factory=dict)
    final_plan: Dict[str, Any] = field(default_factory=dict)
    option_name: str = "Base Option"
    option_family: str = "base"
    rerun_history: List[Dict[str, Any]] = field(default_factory=list)

    def add_stage(self, name: str, success: bool, message: str = "", **meta: Any) -> None:
        self.stage_results.append(PlannerStageResult(stage_name=name, success=success, message=message, meta=dict(meta)))

    def record_warning(self, text: str) -> None:
        if text and text not in self.warnings:
            self.warnings.append(text)

    def record_error(self, text: str) -> None:
        if text and text not in self.errors:
            self.errors.append(text)

    def record_assumption(self, text: str) -> None:
        if text and text not in self.assumptions:
            self.assumptions.append(text)


def declared_stage_dependencies(stage_name: str) -> List[str]:
    return list(PLANNER_STAGE_DEPENDENCIES.get(stage_name, []))


def sanitize_action(action: Dict[str, Any]) -> Dict[str, Any]:
    norm = dict(action)
    if isinstance(norm.get("origin"), (list, tuple)) and len(norm["origin"]) >= 2:
        norm["origin"] = [safe_float(norm["origin"][0]), safe_float(norm["origin"][1])]
    if isinstance(norm.get("center"), (list, tuple)) and len(norm["center"]) >= 2:
        norm["center"] = [safe_float(norm["center"][0]), safe_float(norm["center"][1])]
    if isinstance(norm.get("points"), list):
        pts: List[List[float]] = []
        for point in norm["points"]:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                pts.append([safe_float(point[0]), safe_float(point[1])])
        norm["points"] = pts
    return preserve_field_states(norm)


_PLAN_META_KEYS = {
    "planner_workflow",
    "planner_pass_count",
    "option_name",
    "option_family",
    "stage_completeness",
    "runtime_phase_checkpoint",
    "routing",
    "strict_mode",
    "planner_score",
    "stats",
    "quantities",
    "deliverables",
    "engineering_status",
    "truth_audit",
    "manual_validation",
    "qa",
    "coordination",
    "coordination_realism",
    "convergence_summary",
    "optimization_summary",
    "manager_export",
    "grading",
    "drainage",
    "storm_pipes",
    "sanitary",
    "parking_program",
    "alignments",
    "profiles",
    "cross_sections",
    "sheet_registry",
    "export_audit",
    "utilities",
    "requested_deliverables",
    "produced_deliverables",
    "release_ready",
    "export_ready",
    "blockers",
    "review_categories",
    "assumption_summary",
}

_MANAGER_EXPORT_METRIC_KEYS = {
    "earthwork_cut_cf",
    "earthwork_fill_cf",
    "earthwork_net_cf",
    "storm_pipe_length_ft",
    "utility_total_length_ft",
    "sanitary_total_length_ft",
    "impervious_area_sf",
    "building_area_sf",
    "parking_area_sf",
    "road_area_sf",
}

_COORDINATION_KEYS = {
    "success",
    "detected_conflicts",
    "resolved_conflicts",
    "unresolved_conflicts",
    "unresolved_clusters",
    "assumption_resolutions",
    "resolved_count",
    "unresolved_count",
    "changed_systems",
    "coordination_realism",
    "selected_group_strategy",
    "selected_candidate_mode",
    "post_validation_valid",
    "reroute_resolution_count",
    "vertical_adjustment_count",
    "added_structures_from_coordination",
    "clearance_compliant_checks",
    "clearance_total_checks",
    "min_achieved_horizontal_clearance_ft",
    "min_achieved_vertical_clearance_ft",
    "max_horizontal_clearance_deficit_ft",
    "max_vertical_clearance_deficit_ft",
}

_CONVERGENCE_KEYS = {
    "passes_run",
    "max_passes",
    "converged",
    "warning_count",
    "error_count",
    "unresolved_conflict_count",
    "blocked_exports",
    "blocked_reasons",
    "dominant_issue_categories",
    "unresolved_issue_categories",
    "qa_issue_categories",
    "assumption_summary",
    "last_fix_attempt",
    "rerun_summary",
}

_DISCIPLINE_KEYS = {
    "grading": {
        "schema_version",
        "source",
        "success",
        "message",
        "warnings",
        "existing_surface",
        "proposed_surface",
        "earthwork",
        "checks",
        "low_points",
        "flow_samples",
        "surface_controls",
        "drainage_hints",
        "explain",
        "optimize_hooks",
        "conflict_hooks",
        "stats",
        "export_validation",
    },
    "drainage": {
        "schema_version",
        "source",
        "mode",
        "success",
        "message",
        "warnings",
        "structures",
        "basins",
        "pipes",
        "low_points",
        "flow_paths",
        "stats",
        "coordination",
        "surface_guidance",
        "issues",
        "autofix_suggestions",
        "export_validation",
    },
    "storm_pipes": {"segments", "stats", "max_capacity_ratio", "selected_outfall_name", "selected_basin_name", "selected_basin_adequacy_status"},
    "sanitary": {"segments", "manholes", "total_length_ft", "manhole_count", "service_count"},
    "utilities": {
        "route_count",
        "min_horizontal_separation_ft",
        "min_vertical_separation_ft",
        "min_cover_ft",
        "trunk_count",
        "service_count",
        "coordination",
        "export_validation",
    },
}


def _sanitize_manager_export(value: Any) -> Dict[str, Any]:
    manager_export = safe_dict(value)
    metrics = safe_dict(manager_export.get("metrics"))
    clean_metrics: Dict[str, Any] = {}
    for key in _MANAGER_EXPORT_METRIC_KEYS:
        metric = safe_dict(metrics.get(key))
        if metric:
            clean_metrics[key] = {
                "value": safe_float(metric.get("value"), 0.0),
                "unit": safe_str(metric.get("unit"), ""),
            }
    return preserve_field_states(
        {
            "system_counts": _snapshot_serialize(safe_dict(manager_export.get("system_counts"))),
            "dependency_counts": _snapshot_serialize(safe_dict(manager_export.get("dependency_counts"))),
            "dirty_state": _snapshot_serialize(safe_dict(manager_export.get("dirty_state"))),
            "metrics": clean_metrics,
        }
    )


def _sanitize_coordination(value: Any) -> Dict[str, Any]:
    coordination = safe_dict(value)
    return preserve_field_states(
        {
            key: _snapshot_serialize(coordination.get(key))
            for key in _COORDINATION_KEYS
            if key in coordination
        }
    )


def _sanitize_convergence_summary(value: Any) -> Dict[str, Any]:
    convergence = safe_dict(value)
    clean: Dict[str, Any] = {}
    for key in _CONVERGENCE_KEYS:
        if key not in convergence:
            continue
        if key == "last_fix_attempt":
            fix_attempt = safe_dict(convergence.get(key))
            clean[key] = {
                "autofix_actions": [
                    safe_str(item)
                    for item in safe_list(fix_attempt.get("autofix_actions"))
                    if safe_str(item)
                ][:5]
            }
            continue
        if key == "rerun_summary":
            rerun = safe_dict(convergence.get(key))
            clean[key] = {
                "total_reruns": safe_int(rerun.get("total_reruns"), 0),
                "stage_counts": _snapshot_serialize(safe_dict(rerun.get("stage_counts"))),
                "reason_counts": _snapshot_serialize(safe_dict(rerun.get("reason_counts"))),
            }
            continue
        clean[key] = _snapshot_serialize(convergence.get(key))
    return preserve_field_states(clean)


def _sanitize_discipline_meta(key: str, value: Any) -> Dict[str, Any]:
    payload = safe_dict(value)
    allowed = _DISCIPLINE_KEYS.get(key, set())
    clean: Dict[str, Any] = {}
    for subkey in allowed:
        if subkey in payload:
            if key == "utilities" and subkey == "coordination":
                clean[subkey] = _sanitize_coordination(payload.get(subkey))
            else:
                clean[subkey] = _snapshot_serialize(payload.get(subkey))
    return preserve_field_states(clean)


def sanitize_plan_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    clean: Dict[str, Any] = {}
    for key, value in safe_dict(meta).items():
        if key not in _PLAN_META_KEYS:
            continue
        if key == "manager_export":
            clean[key] = _sanitize_manager_export(value)
        elif key == "coordination":
            clean[key] = _sanitize_coordination(value)
        elif key == "convergence_summary":
            clean[key] = _sanitize_convergence_summary(value)
        elif key in _DISCIPLINE_KEYS:
            clean[key] = _sanitize_discipline_meta(key, value)
        else:
            clean[key] = _snapshot_serialize(value)
    return clean


def sanitize_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    out = {
        "project_name": safe_str(plan.get("project_name"), "Generated Plan"),
        "units": safe_str(plan.get("units"), "ft"),
        "actions": [],
        "assumptions": [safe_str(x) for x in safe_list(plan.get("assumptions")) if safe_str(x)],
        "meta": sanitize_plan_meta(safe_dict(plan.get("meta"))),
    }
    for action in safe_list(plan.get("actions")):
        if isinstance(action, dict):
            out["actions"].append(sanitize_action(action))
    return out


def _rect_union_area(rects: List[Tuple[float, float, float, float]]) -> float:
    if not rects:
        return 0.0
    xs = sorted({round(x1, 6) for x1, _, x2, _ in rects} | {round(x2, 6) for _, _, x2, _ in rects})
    total = 0.0
    for idx in range(len(xs) - 1):
        x_left = xs[idx]
        x_right = xs[idx + 1]
        if x_right <= x_left:
            continue
        spans: List[Tuple[float, float]] = []
        for rx1, ry1, rx2, ry2 in rects:
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
        covered_y = sum(max(0.0, y2 - y1) for y1, y2 in merged)
        total += (x_right - x_left) * covered_y
    return total


def collect_plan_stats(plan: Dict[str, Any]) -> Dict[str, Any]:
    stats = {
        "action_count": 0,
        "estimated_building_area_sf": 0.0,
        "estimated_parking_area_sf": 0.0,
        "estimated_road_area_sf": 0.0,
        "estimated_pipe_length_ft": 0.0,
        "estimated_utility_length_ft": 0.0,
        "estimated_impervious_area_sf": 0.0,
    }
    meta = safe_dict(plan.get("meta"))
    manager_export = safe_dict(meta.get("manager_export"))
    manager_metrics = safe_dict(manager_export.get("metrics"))
    quantity_totals = safe_dict(safe_dict(meta.get("quantities")).get("totals"))

    def metric_value(name: str, default: float = 0.0) -> float:
        return safe_float(safe_dict(manager_metrics.get(name)).get("value"), default)

    def has_quantity_value(name: str) -> bool:
        return name in quantity_totals and quantity_totals.get(name) is not None

    def metric_fallback(final_value: float, metric_name: str, *, canonical_present: bool = False) -> float:
        final_number = safe_float(final_value, 0.0)
        if final_number > 0.0 or canonical_present:
            return final_number
        return metric_value(metric_name, 0.0)

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

    storm_summary = safe_dict(meta.get("storm_pipes") or meta.get("storm_pipe_summary"))
    storm_stats = safe_dict(storm_summary.get("stats"))
    canonical_storm_length = max(
        safe_float(storm_summary.get("total_length_ft"), 0.0),
        safe_float(storm_stats.get("total_length_ft"), 0.0),
        safe_float(storm_stats.get("total_pipe_length_ft"), 0.0),
        segment_total_length(storm_summary.get("segments")),
    )
    utility_summary = safe_dict(meta.get("utilities"))
    utility_stats = safe_dict(utility_summary.get("stats"))
    utility_hooks = safe_dict(utility_summary.get("conflict_hooks"))
    canonical_utility_length = max(
        safe_float(utility_summary.get("total_length_ft"), 0.0),
        safe_float(utility_stats.get("total_length_ft"), 0.0),
        segment_total_length(utility_summary.get("segments")),
        segment_total_length(utility_hooks.get("utility_segments")),
    )

    actions = safe_list(plan.get("actions"))
    stats["action_count"] = len(actions)
    building_rects: List[Tuple[float, float, float, float]] = []
    parking_rects: List[Tuple[float, float, float, float]] = []
    road_rects: List[Tuple[float, float, float, float]] = []
    for action in actions:
        task = lower_text(action.get("task"))
        layer = safe_str(action.get("layer"), "SITE").upper()
        label = lower_text(action.get("label"))
        width = safe_float(action.get("width"), 0.0)
        height = safe_float(action.get("height"), 0.0)
        area = rect_area(width, height)
        if task == "rectangle":
            origin = safe_list(action.get("origin"))
            rect = None
            if len(origin) >= 2 and width > 0.0 and height > 0.0:
                x = safe_float(origin[0], 0.0)
                y = safe_float(origin[1], 0.0)
                rect = (x, y, x + width, y + height)
            if layer in {"BUILDING", "STRUCTURE"} or "building" in label or "bldg" in label or "pad" in label:
                if rect is not None:
                    building_rects.append(rect)
                else:
                    stats["estimated_building_area_sf"] += area
            elif layer in {"PARKING", "PAVEMENT"} or "park" in label:
                if rect is not None:
                    parking_rects.append(rect)
                else:
                    stats["estimated_parking_area_sf"] += area
            elif layer in {"ROAD"} or "road" in label:
                if rect is not None:
                    road_rects.append(rect)
                else:
                    stats["estimated_road_area_sf"] += area
        points = action.get("points")
        if isinstance(points, list) and len(points) >= 2:
            length = polyline_length(points)
            if layer == "PIPE":
                stats["estimated_pipe_length_ft"] += length
            elif layer in {"UTILITY", "WATER", "SAN", "STORM", "DRAIN"}:
                stats["estimated_utility_length_ft"] += length
    if building_rects:
        stats["estimated_building_area_sf"] = _rect_union_area(building_rects)
    if parking_rects:
        stats["estimated_parking_area_sf"] = _rect_union_area(parking_rects)
    if road_rects:
        stats["estimated_road_area_sf"] = _rect_union_area(road_rects)
    area_total = (
        safe_float(stats["estimated_building_area_sf"])
        + safe_float(stats["estimated_parking_area_sf"])
        + safe_float(stats["estimated_road_area_sf"])
    )
    stats["estimated_impervious_area_sf"] = round(max(area_total, safe_float(stats["estimated_impervious_area_sf"])), 3)

    final_action_count = max(
        int(stats["action_count"]),
        int(round(safe_float(quantity_totals.get("action_count"), stats["action_count"]))),
    )
    stats["action_count"] = final_action_count if final_action_count > 0 or has_quantity_value("action_count") else int(round(metric_value("layout_action_count", 0.0)))

    final_building_area = max(
        safe_float(stats["estimated_building_area_sf"]),
        safe_float(quantity_totals.get("building_area_sf"), 0.0),
    )
    stats["estimated_building_area_sf"] = metric_fallback(
        final_building_area,
        "layout_building_area_sf",
        canonical_present=has_quantity_value("building_area_sf") or bool(building_rects),
    )
    final_parking_area = max(
        safe_float(stats["estimated_parking_area_sf"]),
        safe_float(quantity_totals.get("parking_area_sf"), 0.0),
    )
    stats["estimated_parking_area_sf"] = metric_fallback(
        final_parking_area,
        "layout_parking_area_sf",
        canonical_present=has_quantity_value("parking_area_sf") or bool(parking_rects),
    )
    final_road_area = max(
        safe_float(stats["estimated_road_area_sf"]),
        safe_float(quantity_totals.get("road_area_sf"), 0.0),
    )
    stats["estimated_road_area_sf"] = metric_fallback(
        final_road_area,
        "layout_road_area_sf",
        canonical_present=has_quantity_value("road_area_sf") or bool(road_rects),
    )
    final_pipe_length = max(
        safe_float(stats["estimated_pipe_length_ft"]),
        safe_float(quantity_totals.get("pipe_length_ft"), 0.0),
        canonical_storm_length,
    )
    stats["estimated_pipe_length_ft"] = metric_fallback(
        final_pipe_length,
        "storm_pipe_length_ft",
        canonical_present=bool(storm_summary) or has_quantity_value("pipe_length_ft"),
    )
    final_utility_length = max(
        safe_float(stats["estimated_utility_length_ft"]),
        safe_float(quantity_totals.get("utility_length_ft"), 0.0),
        canonical_utility_length,
    )
    stats["estimated_utility_length_ft"] = metric_fallback(
        final_utility_length,
        "utility_total_length_ft",
        canonical_present=bool(utility_summary) or has_quantity_value("utility_length_ft"),
    )
    final_impervious_area = max(
        safe_float(stats["estimated_impervious_area_sf"]),
        safe_float(quantity_totals.get("estimated_impervious_area_sf"), 0.0),
    )
    stats["estimated_impervious_area_sf"] = metric_fallback(
        final_impervious_area,
        "layout_impervious_area_sf",
        canonical_present=has_quantity_value("estimated_impervious_area_sf") or area_total > 0.0,
    )

    for key in list(stats.keys()):
        if isinstance(stats[key], float):
            stats[key] = round(stats[key], 3)
    return stats


def normalize_parsed_payload(parsed: Dict[str, Any]) -> Dict[str, Any]:
    norm = preserve_field_states(deepcopy(parsed))
    norm["mode"] = lower_text(resolve_field(norm.get("mode"), "site_plan"))
    norm["project_type"] = lower_text(resolve_field(norm.get("project_type"), "generic_site"))
    norm["site_type"] = lower_text(resolve_field(norm.get("site_type"), resolve_field(norm.get("project_type"), "generic_site")))
    norm["street_edge"] = lower_text(resolve_field(norm.get("street_edge"), "bottom"))
    lot = safe_dict(unwrap_fields_for_execution(norm.get("lot")))
    norm["lot"] = {
        "x": safe_float(lot.get("x"), DEFAULT_LOT_X),
        "y": safe_float(lot.get("y"), DEFAULT_LOT_Y),
        "w": max(1.0, safe_float(lot.get("w"), DEFAULT_LOT_WIDTH)),
        "h": max(1.0, safe_float(lot.get("h"), DEFAULT_LOT_HEIGHT)),
    }
    setback_resolved = resolve_field(norm.get("setback"), DEFAULT_SETBACK)
    norm["setback"] = None if field_path_is_omitted(norm, "setback") else max(0.0, safe_float(setback_resolved, DEFAULT_SETBACK))
    norm.setdefault("meta", {})
    if isinstance(parsed.get("meta"), dict) and isinstance(parsed.get("meta", {}).get("site_inputs"), dict):
        norm["meta"]["site_inputs"] = deepcopy(parsed["meta"]["site_inputs"])
    return norm


def triple_check_parsed_payload(parsed: Dict[str, Any]) -> Dict[str, Any]:
    checked = normalize_parsed_payload(parsed)
    review_notes: List[str] = list(checked.get("_planner_review_notes") or [])
    lot = safe_dict(checked.get("lot"))
    if lot["w"] <= 0.0 or lot["h"] <= 0.0:
        checked["lot"]["w"] = max(1.0, safe_float(lot.get("w"), DEFAULT_LOT_WIDTH))
        checked["lot"]["h"] = max(1.0, safe_float(lot.get("h"), DEFAULT_LOT_HEIGHT))
        review_notes.append("Corrected non-positive lot dimensions to safe defaults.")
    if lower_text(checked.get("mode")) == "drainage":
        drainage = safe_dict(checked.get("drainage"))
        if safe_float(drainage.get("inlet_count"), 0) > 0 and safe_float(drainage.get("trunk_line_count"), 0) == 0:
            drainage["trunk_line_count"] = 1
            review_notes.append("Added default trunk_line_count=1 for drainage layout with inlets.")
        checked["drainage"] = drainage
    checked["_planner_review_notes"] = dedupe_keep_order(review_notes)
    return preserve_field_states(checked)


def choose_routing_path(parsed: Dict[str, Any]) -> RoutingDecision:
    mode = lower_text(parsed.get("mode"))
    reasons: List[str] = []
    if mode in {"site_plan", "drainage", "road", "subdivision", "bridge", "pool"}:
        reasons.append("Mode supports model-first coordinated engineering workflow.")
        return RoutingDecision(path="model_first", reasons=reasons)
    reasons.append("Falling back to model-first as default planner route.")
    return RoutingDecision(path="model_first", reasons=reasons)


def _bootstrap_manager(parsed: Dict[str, Any]) -> ProjectManager:
    lot = safe_dict(parsed.get("lot"))
    units_raw = safe_str(parsed.get("units"), "ft").lower()
    units_norm = "ft" if units_raw in {"feet", "foot", "ft"} else units_raw
    project = ProjectModel(name=safe_str(parsed.get("project_name"), "Generated Plan"), units=units_norm)
    site_zone = rect_zone(
        safe_float(lot.get("x"), DEFAULT_LOT_X),
        safe_float(lot.get("y"), DEFAULT_LOT_Y),
        max(1.0, safe_float(lot.get("w"), DEFAULT_LOT_WIDTH)),
        max(1.0, safe_float(lot.get("h"), DEFAULT_LOT_HEIGHT)),
        zone_type=ZoneType.SITE,
        name="SITE",
        meta={"source": "planner_bootstrap"},
    )
    project.add_zone(site_zone)
    manager = ProjectManager(project)

    meta = safe_dict(parsed.get("meta"))
    site_object_id = safe_str(meta.get("site_object_id"), "")
    if site_object_id:
        site_anchor = Point3D(
            site_zone.boundary.bbox.center_x,
            site_zone.boundary.bbox.center_y,
            0.0,
        )
        manager.add_object(
            EngineeringObject(
                id=site_object_id,
                kind="site",
                name="SITE",
                anchor=site_anchor,
                boundary=site_zone.boundary,
                tags=["layout", "site"],
                domain=EngineeringDomain.GENERAL,
                properties={
                    "width": site_zone.boundary.bbox.width,
                    "depth": site_zone.boundary.bbox.height,
                    "source": "user",
                    "generated": False,
                    "locked": True,
                    "system_dependencies": ["layout", "grading", "drainage", "sanitary", "utility_network"],
                },
            )
        )

    dirty_state = safe_dict(meta.get("system_dirty_state"))
    if dirty_state:
        for name, record in dirty_state.items():
            entry = safe_dict(record) if isinstance(record, dict) else {"state": record}
            state_value = safe_str(entry.get("state"), entry.get("status") or entry.get("value") or "")
            if state_value.lower() in {"dirty", "stale", "not_generated"}:
                manager.mark_system_dirty(
                    safe_str(name),
                    reason=safe_str(entry.get("reason"), "Frontend marked system dirty."),
                    source=safe_str(entry.get("source"), "frontend"),
                )
            elif state_value.lower() in {"clean", "fresh", "complete"}:
                manager.mark_system_clean(safe_str(name))
    return manager


def _register_default_dependencies(manager: ProjectManager) -> None:
    deps = [
        ("layout", "grading"),
        ("grading", "drainage"),
        ("drainage", "storm_pipes"),
        ("grading", "sanitary"),
        ("storm_pipes", "sanitary"),
        ("layout", "sanitary"),
        ("sanitary", "utility_network"),
        ("storm_pipes", "utility_network"),
        ("grading", "utility_network"),
        ("grading", "coordination_resolution"),
        ("storm_pipes", "coordination_resolution"),
        ("sanitary", "coordination_resolution"),
        ("utility_network", "coordination_resolution"),
        ("storm_pipes", "sheets"),
        ("sanitary", "sheets"),
        ("grading", "sheets"),
        ("coordination_resolution", "earthwork"),
        ("coordination_resolution", "sheets"),
        ("coordination_resolution", "qa"),
        ("utility_network", "earthwork"),
        ("grading", "earthwork"),
        ("earthwork", "qa"),
        ("sanitary", "qa"),
        ("utility_network", "qa"),
        ("storm_pipes", "qa"),
        ("drainage", "qa"),
        ("grading", "qa"),
        ("layout", "qa"),
    ]
    for src, tgt in deps:
        manager.add_dependency(src, tgt, DependencyState.STALE, reason="Default planner dependency.")


def _mark_dependency_state(manager: ProjectManager, source: str, target: str, state: DependencyState, reason: str = "") -> None:
    for dep in manager.dependencies:
        if dep.source == source and dep.target == target:
            dep.state = state
            dep.reason = reason
            return
    manager.add_dependency(source, target, state, reason=reason)


def _lot_area(parsed: Dict[str, Any]) -> float:
    lot = safe_dict(parsed.get("lot"))
    return rect_area(lot.get("w"), lot.get("h"))


def _compute_hydrology_metrics(parsed: Dict[str, Any], stats: Dict[str, Any]) -> Dict[str, Any]:
    area_sf = max(_lot_area(parsed), 1.0)
    impervious_sf = max(0.0, safe_float(stats.get("estimated_impervious_area_sf"), 0.0))
    impervious_ratio = clamp(impervious_sf / area_sf, 0.0, 1.0)
    tc = max(5.0, 5.0 + (area_sf / 25000.0) ** 0.5 * 6.0)
    runoff_c = clamp(0.35 + impervious_ratio * 0.55, 0.35, 0.95)
    intensity = max(2.0, PIPE_INTENSITY_IN_HR)
    try:
        hydrology = compute_rational_method([
            RationalArea(name="SITE", area_ac=area_sf / 43560.0, runoff_c=runoff_c, intensity_in_hr=intensity)
        ])
        peak = safe_float(getattr(hydrology, "total_flow_cfs", 0.0), 0.0)
    except Exception:
        peak = 1.008 * (area_sf / 43560.0) * runoff_c * intensity
    return {
        "lot_area_sf": area_sf,
        "impervious_ratio": impervious_ratio,
        "tc_minutes": round(tc, 3),
        "runoff_c": round(runoff_c, 4),
        "intensity_in_hr": round(intensity, 3),
        "peak_runoff_cfs": round(peak, 3),
    }


def _planner_score_from_manager(manager: ProjectManager) -> Tuple[float, Dict[str, float]]:
    parking_score = safe_float(getattr(manager.metrics.get("parking_count"), "value", 0.0), 0.0)
    earthwork_score = -abs(safe_float(getattr(manager.metrics.get("earthwork_net_cf"), "value", 0.0), 0.0)) / 500.0
    drainage_score = safe_float(getattr(manager.metrics.get("drainage_low_point_count"), "value", 0.0), 0.0)
    constructability = max(0.0, 20.0 - sum(1 for conflict in manager.conflicts if conflict.severity == ConflictSeverity.ERROR))
    completeness = min(
        20.0,
        20.0 * sum(
            1
            for metric_name in ("grading_success", "storm_pipe_count", "utility_route_count", "drainage_low_point_count", "earthwork_success")
            if manager.metrics.get(metric_name) is not None
        ),
    )
    qa_error_penalty = safe_float(getattr(manager.metrics.get("qa_error_count"), "value", 0.0), 0.0) * 20.0
    qa_warning_penalty = safe_float(getattr(manager.metrics.get("qa_warning_count"), "value", 0.0), 0.0) * 3.5
    pipe_ratio = safe_float(getattr(manager.metrics.get("pipe_max_capacity_ratio"), "value", 0.0), 0.0)
    pipe_penalty = max(0.0, pipe_ratio - 0.95) * 50.0
    conflict_penalty = sum(10.0 for conflict in manager.conflicts if not conflict.resolved)
    weighted = {
        "parking": parking_score * 1.15,
        "constructability": constructability * 1.05,
        "earthwork": earthwork_score * 1.05,
        "drainage": drainage_score * 1.10,
        "completeness": completeness * 1.0,
        "qa_warning_penalty": -qa_warning_penalty,
        "qa_error_penalty": -qa_error_penalty,
        "pipe_penalty": -pipe_penalty,
        "conflict_penalty": -conflict_penalty,
    }
    return sum(weighted.values()), weighted
