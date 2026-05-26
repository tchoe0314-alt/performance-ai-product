from __future__ import annotations

from dataclasses import dataclass, asdict
from math import hypot
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


Point = Tuple[float, float]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(round(float(value)))
    except Exception:
        return int(default)


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _truthy_mapping(value: Any) -> bool:
    return bool(_safe_dict(value))


@dataclass(frozen=True)
class CivilDesignStandards:
    """Concept-level civil design standards used for deterministic engine checks.

    These are not jurisdictional rules. They are intentionally conservative
    coordination defaults so the engines can explain when a design is ready,
    incomplete, or assumption-driven.
    """

    version: str = "civil_design_v1"
    min_site_slope: float = 0.005
    max_parking_slope: float = 0.06
    max_ada_cross_slope: float = 0.02
    max_road_grade: float = 0.10
    min_gravity_pipe_slope: float = 0.003
    max_pipe_capacity_ratio: float = 0.95
    min_utility_cover_ft: float = 3.0
    min_gravity_utility_horizontal_separation_ft: float = 10.0
    min_pressure_gravity_horizontal_separation_ft: float = 10.0
    min_electric_gas_horizontal_separation_ft: float = 3.0
    min_vertical_crossing_separation_ft: float = 1.5
    max_sanitary_manhole_spacing_ft: float = 400.0
    max_storm_structure_spacing_ft: float = 400.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DEFAULT_STANDARDS = CivilDesignStandards()


def coerce_point(value: Any) -> Optional[Point]:
    if isinstance(value, dict):
        if "x" in value and "y" in value:
            return (_safe_float(value.get("x")), _safe_float(value.get("y")))
        if "lng" in value and "lat" in value:
            return (_safe_float(value.get("lng")), _safe_float(value.get("lat")))
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (_safe_float(value[0]), _safe_float(value[1]))
    return None


def coerce_path(value: Any) -> List[Point]:
    points: List[Point] = []
    for item in _safe_list(value):
        point = coerce_point(item)
        if point is not None:
            points.append(point)
    return points


def path_length(points: Sequence[Point]) -> float:
    total = 0.0
    for index in range(1, len(points)):
        total += hypot(points[index][0] - points[index - 1][0], points[index][1] - points[index - 1][1])
    return total


def path_bbox(points: Sequence[Point]) -> Optional[Tuple[float, float, float, float]]:
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


def station_point(points: Sequence[Point], distance_ft: float) -> Optional[Point]:
    if not points:
        return None
    if len(points) == 1:
        return points[0]
    remaining = max(0.0, _safe_float(distance_ft))
    for index in range(1, len(points)):
        start = points[index - 1]
        end = points[index]
        seg_len = hypot(end[0] - start[0], end[1] - start[1])
        if seg_len <= 0.0:
            continue
        if remaining <= seg_len:
            t = remaining / seg_len
            return (start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t)
        remaining -= seg_len
    return points[-1]


def sample_path(points: Sequence[Point], *, spacing_ft: float = 50.0, max_samples: int = 120) -> List[Point]:
    if not points:
        return []
    total = path_length(points)
    if total <= 0.0:
        return [points[0]]
    spacing = max(1.0, _safe_float(spacing_ft, 50.0))
    count = min(max_samples, max(2, int(total / spacing) + 2))
    if count <= 2:
        return [points[0], points[-1]]
    return [station_point(points, total * i / (count - 1)) or points[-1] for i in range(count)]


def _point_segment_distance(point: Point, start: Point, end: Point) -> float:
    px, py = point
    ax, ay = start
    bx, by = end
    dx = bx - ax
    dy = by - ay
    denom = dx * dx + dy * dy
    if denom <= 0.0:
        return hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
    qx = ax + t * dx
    qy = ay + t * dy
    return hypot(px - qx, py - qy)


def segment_clearance(a1: Point, a2: Point, b1: Point, b2: Point) -> float:
    return min(
        _point_segment_distance(a1, b1, b2),
        _point_segment_distance(a2, b1, b2),
        _point_segment_distance(b1, a1, a2),
        _point_segment_distance(b2, a1, a2),
    )


def path_clearance(path_a: Sequence[Point], path_b: Sequence[Point]) -> float:
    if not path_a or not path_b:
        return 0.0
    if len(path_a) == 1 or len(path_b) == 1:
        return min(hypot(a[0] - b[0], a[1] - b[1]) for a in path_a for b in path_b)
    best = float("inf")
    for ai in range(1, len(path_a)):
        for bi in range(1, len(path_b)):
            best = min(best, segment_clearance(path_a[ai - 1], path_a[ai], path_b[bi - 1], path_b[bi]))
    return 0.0 if best == float("inf") else best


def rect_from_action(action: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    origin = _safe_list(action.get("origin"))
    if len(origin) >= 2:
        width = _safe_float(action.get("width"), _safe_float(action.get("w"), 0.0))
        height = _safe_float(action.get("height"), _safe_float(action.get("h"), 0.0))
        if width > 0.0 and height > 0.0:
            x = _safe_float(origin[0])
            y = _safe_float(origin[1])
            return (x, y, x + width, y + height)
    center = coerce_point(action.get("center"))
    radius = _safe_float(action.get("radius"), 0.0)
    if center is not None and radius > 0.0:
        return (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)
    return None


def classify_action_system(action: Dict[str, Any]) -> str:
    layer = _safe_str(action.get("layer")).lower()
    label = _safe_str(action.get("label")).lower()
    canonical = _safe_str(action.get("canonical_source_type")).lower()
    haystack = " ".join([layer, label, canonical])
    if "sanitary" in haystack or "sewer" in haystack:
        return "sanitary"
    if "storm" in haystack or "drainage" in haystack or "basin" in haystack or "pond" in haystack:
        return "drainage"
    if "water" in haystack or "utility" in haystack or "gas" in haystack or "electric" in haystack:
        return "utilities"
    if "road" in haystack:
        return "road"
    if "parking" in haystack or "pavement" in haystack:
        return "parking"
    if "building" in haystack or "structure" in haystack:
        return "building"
    return "site"


def utility_pairing_rule(system_a: str, system_b: str, standards: CivilDesignStandards = DEFAULT_STANDARDS) -> Dict[str, Any]:
    pair = {system_a.lower(), system_b.lower()}
    if {"water", "sanitary"} <= pair or {"water", "storm"} <= pair:
        return {
            "horizontal_separation_ft": standards.min_pressure_gravity_horizontal_separation_ft,
            "vertical_separation_ft": standards.min_vertical_crossing_separation_ft,
            "priority": "pressure_utility_protected",
            "lower_owner": "gravity",
        }
    if {"storm", "sanitary"} <= pair:
        return {
            "horizontal_separation_ft": standards.min_gravity_utility_horizontal_separation_ft,
            "vertical_separation_ft": standards.min_vertical_crossing_separation_ft,
            "priority": "sanitary_service_continuity",
            "lower_owner": "storm_where_feasible",
        }
    if {"electric", "gas"} <= pair:
        return {
            "horizontal_separation_ft": standards.min_electric_gas_horizontal_separation_ft,
            "vertical_separation_ft": standards.min_vertical_crossing_separation_ft,
            "priority": "joint_trench_review",
            "lower_owner": "jurisdictional_standard",
        }
    return {
        "horizontal_separation_ft": standards.min_gravity_utility_horizontal_separation_ft,
        "vertical_separation_ft": standards.min_vertical_crossing_separation_ft,
        "priority": "coordinate_crossing",
        "lower_owner": "case_by_case",
    }


def _missing(system: str, field: str, why: str, action: str) -> Dict[str, Any]:
    return {
        "system": system,
        "field": field,
        "why_needed": why,
        "suggested_next_action": action,
    }


def _system_result(
    *,
    status: str,
    source: str = "missing",
    missing: Optional[List[Dict[str, Any]]] = None,
    warnings: Optional[List[str]] = None,
    metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "status": status,
        "source": source,
        "missing": missing or [],
        "warnings": warnings or [],
        "metrics": metrics or {},
    }


def check_grading_truth(grading: Dict[str, Any]) -> Dict[str, Any]:
    missing: List[Dict[str, Any]] = []
    warnings: List[str] = []
    source = (
        _safe_str(grading.get("source_quality"))
        or _safe_str(grading.get("grading_source_quality"))
        or _safe_str(_safe_dict(grading.get("existing_surface")).get("source_quality"))
        or "missing"
    )
    low_points = _safe_list(grading.get("low_points"))
    high_points = _safe_list(grading.get("high_points"))
    slope_summary = _safe_dict(grading.get("slope_summary")) or _safe_dict(grading.get("surface_controls"))
    if not grading:
        missing.append(_missing("grading", "grading", "Drainage and earthwork need an existing/proposed surface.", "Run Detect Grading or upload survey/terrain."))
    if not low_points:
        missing.append(_missing("grading", "low_points", "Drainage needs low points to route flow.", "Generate or import a surface with low-point analysis."))
    if not high_points:
        warnings.append("No high points were reported; grading review is less complete.")
    if not slope_summary:
        missing.append(_missing("grading", "slope_summary", "Civil checks need slope direction and surface controls.", "Run grading analysis from terrain or survey."))
    if source in {"assumed", "fallback", "synthetic"}:
        warnings.append(f"Grading source is {source}; do not treat it as survey.")
    return _system_result(
        status="ready" if not missing else "missing",
        source=source,
        missing=missing,
        warnings=warnings,
        metrics={"low_point_count": len(low_points), "high_point_count": len(high_points)},
    )


def check_drainage_truth(drainage: Dict[str, Any]) -> Dict[str, Any]:
    missing: List[Dict[str, Any]] = []
    warnings: List[str] = []
    structures = _safe_list(drainage.get("structures"))
    basins = _safe_list(drainage.get("basins"))
    low_points = _safe_list(drainage.get("low_points"))
    flow_paths = _safe_list(drainage.get("flow_paths"))
    surface_guidance = _safe_dict(drainage.get("surface_guidance"))
    source = _safe_str(surface_guidance.get("surface_source")) or _safe_str(drainage.get("surface_source")) or _safe_str(drainage.get("source")) or "missing"
    if not drainage or not bool(drainage.get("success", bool(structures or basins))):
        missing.append(_missing("drainage", "success", "Storm and grading coordination need a valid drainage network.", "Run drainage after grading and basin/outfall placement."))
    if not basins and not _truthy_mapping(_safe_dict(drainage.get("coordination")).get("preferred_outfall")):
        missing.append(_missing("drainage", "basin_or_outfall", "Storm pipes need a detention basin or outfall target.", "Add or identify a basin/outfall."))
    if not low_points:
        missing.append(_missing("drainage", "low_points", "Drainage routing needs surface low points.", "Run terrain-based grading first."))
    if not flow_paths:
        missing.append(_missing("drainage", "flow_paths", "Drainage needs flow paths to connect inlets to basins/outfalls.", "Run drainage on the current surface."))
    issue_codes = {_safe_str(item.get("code")) for item in _safe_list(drainage.get("issues")) if isinstance(item, dict)}
    if "DRAINAGE_BLOCKED_BY_GRADING" in issue_codes:
        warnings.append("Drainage is blocked by grading and needs a spatial grading fix before final storm design.")
    return _system_result(
        status="ready" if not missing else "missing",
        source=source,
        missing=missing,
        warnings=warnings,
        metrics={"structure_count": len(structures), "basin_count": len(basins), "low_point_count": len(low_points), "flow_path_count": len(flow_paths)},
    )


def check_storm_truth(storm: Dict[str, Any]) -> Dict[str, Any]:
    missing: List[Dict[str, Any]] = []
    warnings: List[str] = []
    segments = _safe_list(storm.get("segments"))
    source = _safe_str(storm.get("hydraulic_source")) or _safe_str(storm.get("source")) or "missing"
    if not storm or not bool(storm.get("success", bool(segments))):
        missing.append(_missing("storm_pipes", "success", "Storm design needs a valid pipe network.", "Run storm after drainage target selection."))
    if not (_safe_str(storm.get("selected_outfall")) or _safe_str(storm.get("target_outfall_name")) or _truthy_mapping(storm.get("target_outfall"))):
        missing.append(_missing("storm_pipes", "selected_outfall", "Storm pipes need the drainage-selected outfall/basin.", "Confirm drainage outfall and rerun storm."))
    for field in ("total_system_flow_cfs", "total_system_capacity_cfs", "controlling_segment", "max_capacity_ratio"):
        if field not in storm:
            missing.append(_missing("storm_pipes", field, f"Storm hydraulic truth requires {field}.", "Run storm hydraulic sizing/checking."))
    graph = _safe_dict(storm.get("graph_validation"))
    hydraulics = _safe_dict(storm.get("hydraulic_validation"))
    if segments and not bool(graph.get("valid", False)):
        missing.append(_missing("storm_pipes", "graph_validation", "Storm graph must be connected and directionally valid.", "Repair storm graph connectivity."))
    if segments and not bool(hydraulics.get("valid", False)):
        missing.append(_missing("storm_pipes", "hydraulic_validation", "Storm pipe capacities and slopes must be checked.", "Run hydraulic validation."))
    missing_segments = _safe_list(storm.get("missing_data_segments"))
    if missing_segments:
        warnings.append("Storm has segments with missing hydraulic fields.")
    return _system_result(
        status="ready" if not missing else "missing",
        source=source,
        missing=missing,
        warnings=warnings,
        metrics={"segment_count": len(segments), "missing_data_segment_count": len(missing_segments), "max_capacity_ratio": _safe_float(storm.get("max_capacity_ratio"), 0.0)},
    )


def check_sanitary_truth(sanitary: Dict[str, Any]) -> Dict[str, Any]:
    missing: List[Dict[str, Any]] = []
    warnings: List[str] = []
    segments = _safe_list(sanitary.get("segments"))
    manholes = _safe_list(sanitary.get("manholes"))
    source = _safe_str(sanitary.get("source")) or "missing"
    if not sanitary or not bool(sanitary.get("success", bool(segments or manholes))):
        missing.append(_missing("sanitary", "success", "Sanitary design needs a valid service network.", "Run sanitary design for buildings requiring service."))
    if not segments:
        missing.append(_missing("sanitary", "segments", "Sanitary design needs main/service segments.", "Generate sanitary routes."))
    if not manholes:
        missing.append(_missing("sanitary", "manholes", "Sanitary graph needs manholes for constructible service routing.", "Generate sanitary manholes."))
    graph = _safe_dict(sanitary.get("graph_validation"))
    network = _safe_dict(sanitary.get("network_validation"))
    if segments and not bool(graph.get("valid", False)):
        missing.append(_missing("sanitary", "graph_validation", "Sanitary graph must be connected and directionally valid.", "Repair sanitary graph connectivity."))
    if segments and not bool(network.get("valid", False)):
        missing.append(_missing("sanitary", "network_validation", "Sanitary must prove building services connect to the network.", "Run sanitary service validation."))
    if _safe_list(sanitary.get("missing_service_buildings")):
        missing.append(_missing("sanitary", "missing_service_buildings", "All served buildings need sanitary service coverage.", "Add missing services or mark buildings unserved."))
    if _safe_list(sanitary.get("missing_data_segments")):
        warnings.append("Sanitary has segments with missing design fields.")
    return _system_result(
        status="ready" if not missing else "missing",
        source=source,
        missing=missing,
        warnings=warnings,
        metrics={"segment_count": len(segments), "manhole_count": len(manholes), "route_count": _safe_int(sanitary.get("route_count"), len(segments))},
    )


def check_utility_truth(utilities: Dict[str, Any]) -> Dict[str, Any]:
    missing: List[Dict[str, Any]] = []
    warnings: List[str] = []
    hooks = _safe_dict(utilities.get("conflict_hooks"))
    segments = _safe_list(utilities.get("segments")) or _safe_list(hooks.get("utility_segments"))
    source = _safe_str(utilities.get("source")) or "missing"
    if not utilities:
        missing.append(_missing("utilities", "utility_summary", "Coordination needs utility paths and conflicts.", "Run utility network coordination."))
    if utilities and not segments:
        missing.append(_missing("utilities", "segments", "Utility coordination needs utility segments.", "Generate utility segments."))
    coordination = _safe_dict(utilities.get("coordination"))
    if _safe_int(coordination.get("unresolved_conflict_count"), 0) > 0:
        warnings.append("Utilities still have unresolved conflicts.")
    if _safe_float(utilities.get("min_cover_ft"), 999.0) < DEFAULT_STANDARDS.min_utility_cover_ft:
        warnings.append("Utility cover is below concept minimum.")
    return _system_result(
        status="ready" if not missing else "missing",
        source=source,
        missing=missing,
        warnings=warnings,
        metrics={"segment_count": len(segments), "unresolved_conflict_count": _safe_int(coordination.get("unresolved_conflict_count"), 0)},
    )


def check_coordination_truth(coordination: Dict[str, Any]) -> Dict[str, Any]:
    missing: List[Dict[str, Any]] = []
    warnings: List[str] = []
    unresolved_count = _safe_int(coordination.get("unresolved_count"), _safe_int(coordination.get("unresolved_conflict_count"), 0))
    detected_count = _safe_int(coordination.get("detected_conflicts"), 0)
    if unresolved_count > 0:
        missing.append(_missing("coordination", "unresolved_conflicts", "Open conflicts mean final systems are not coordinated.", "Resolve or explicitly document unresolved conflicts."))
    if _safe_list(coordination.get("assumption_resolutions")):
        warnings.append("Coordination used assumption-based resolutions.")
    status = "ready"
    if missing:
        status = "missing"
    elif not coordination and detected_count <= 0:
        status = "not_run"
        warnings.append("Coordination summary was not present.")
    return _system_result(
        status=status,
        source=_safe_str(coordination.get("source"), "coordination"),
        missing=missing,
        warnings=warnings,
        metrics={"detected_conflict_count": detected_count, "unresolved_conflict_count": unresolved_count},
    )


def civil_design_readiness(plan_or_meta: Dict[str, Any], *, standards: CivilDesignStandards = DEFAULT_STANDARDS) -> Dict[str, Any]:
    meta = _safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else _safe_dict(plan_or_meta)
    systems = {
        "grading": check_grading_truth(_safe_dict(meta.get("grading") or meta.get("grading_summary"))),
        "drainage": check_drainage_truth(_safe_dict(meta.get("drainage") or meta.get("drainage_canonical"))),
        "storm_pipes": check_storm_truth(_safe_dict(meta.get("storm_pipes") or meta.get("storm_pipe_summary"))),
        "sanitary": check_sanitary_truth(_safe_dict(meta.get("sanitary") or meta.get("sanitary_summary"))),
        "utilities": check_utility_truth(_safe_dict(meta.get("utilities") or meta.get("utility_summary"))),
        "coordination": check_coordination_truth(_safe_dict(meta.get("coordination") or meta.get("coordination_summary"))),
    }
    missing_requirements: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    truth_sources: Dict[str, str] = {}
    for system, result in systems.items():
        truth_sources[system] = _safe_str(result.get("source"), "missing")
        missing_requirements.extend(_safe_list(result.get("missing")))
        for warning in _safe_list(result.get("warnings")):
            warnings.append({"system": system, "message": _safe_str(warning)})
    critical_blockers = [
        item
        for item in missing_requirements
        if item.get("system") in {"grading", "drainage", "storm_pipes", "sanitary", "coordination"}
    ]
    ready_systems = [system for system, result in systems.items() if result.get("status") == "ready"]
    success = not critical_blockers
    status = "ready" if success else "blocked"
    if success and warnings:
        status = "needs_engineering_review"
    return {
        "success": success,
        "status": status,
        "standards_version": standards.version,
        "standards": standards.to_dict(),
        "systems": systems,
        "ready_systems": ready_systems,
        "missing_requirements": missing_requirements,
        "critical_blockers": critical_blockers,
        "warnings": warnings,
        "truth_sources": truth_sources,
        "can_assist_if_enabled": bool(missing_requirements),
        "message": (
            "Canonical engineering state is ready for coordinated review."
            if success
            else "Civora needs additional canonical engineering inputs before this is final-design ready."
        ),
    }


__all__ = [
    "CivilDesignStandards",
    "DEFAULT_STANDARDS",
    "civil_design_readiness",
    "check_coordination_truth",
    "check_drainage_truth",
    "check_grading_truth",
    "check_sanitary_truth",
    "check_storm_truth",
    "check_utility_truth",
    "classify_action_system",
    "coerce_path",
    "coerce_point",
    "path_bbox",
    "path_clearance",
    "path_length",
    "rect_from_action",
    "sample_path",
    "station_point",
    "utility_pairing_rule",
]
