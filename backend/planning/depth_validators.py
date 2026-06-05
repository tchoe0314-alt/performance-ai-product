from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Tuple

from .common import blocker_explanations, safe_dict, safe_float, safe_list, safe_str


def _present(value: Any) -> bool:
    return value not in (None, "", [], {})


_CONCEPT_MARKERS = ("concept", "proxy", "fallback", "placeholder", "verify")


def _text_has_concept_marker(value: Any) -> bool:
    text = safe_str(value).lower()
    return any(marker in text for marker in _CONCEPT_MARKERS)


def _row_is_production_evidence(row: Dict[str, Any]) -> bool:
    fields = (
        "source",
        "control_source",
        "routing_source",
        "routing_method",
        "truth_label",
        "hydraulic_depth_source",
        "profile_source",
        "standard_source",
    )
    return not any(_text_has_concept_marker(row.get(field)) for field in fields)


def _has_production_rows(rows: Iterable[Dict[str, Any]]) -> bool:
    return any(_row_is_production_evidence(safe_dict(row)) for row in rows)


def _has_verified_crown(row: Dict[str, Any]) -> bool:
    if not _row_is_production_evidence(row):
        return False
    return bool(
        row.get("verified") is True
        or _present(row.get("standard"))
        or _present(row.get("standard_id"))
        or _present(row.get("profile_id"))
    )


def _has_valid_velocity(row: Dict[str, Any]) -> bool:
    if row.get("valid") is False:
        return False
    velocity = row.get("velocity_fps")
    if velocity is None:
        return False
    max_velocity = safe_float(row.get("max_velocity_fps"), 0.0)
    velocity_value = safe_float(velocity, -1.0)
    return velocity_value > 0.0 and (max_velocity <= 0.0 or velocity_value <= max_velocity)


def _has_valid_hydrant_spacing(row: Dict[str, Any]) -> bool:
    rec = safe_dict(row)
    if rec.get("valid") is not True:
        return False
    hydrant_count = safe_float(rec.get("hydrant_count"), 0.0)
    max_spacing = safe_float(rec.get("max_spacing_ft"), -1.0)
    limit = safe_float(rec.get("limit_ft"), 0.0)
    return hydrant_count >= 2 and max_spacing >= 0.0 and limit > 0.0 and max_spacing <= limit


def _has_valid_pressure_validation(row: Dict[str, Any]) -> bool:
    rec = safe_dict(row)
    if rec.get("valid") is not True or not _row_is_production_evidence(rec):
        return False
    source_pressure = safe_float(rec.get("source_pressure_psi"), 0.0)
    min_pressure = safe_float(rec.get("min_pressure_psi"), -1.0)
    required = safe_float(rec.get("min_required_pressure_psi"), 0.0)
    graph = safe_dict(rec.get("pressure_graph"))
    if graph:
        if graph.get("success") is not True or not safe_dict(graph.get("node_pressures_psi")):
            return False
    return source_pressure > 0.0 and required > 0.0 and min_pressure >= required


def _has_valid_fire_flow_validation(row: Dict[str, Any], pressure: Dict[str, Any]) -> bool:
    rec = safe_dict(row)
    if rec.get("valid") is not True or not _row_is_production_evidence(rec):
        return False
    required = safe_float(rec.get("required_fire_flow_gpm"), 0.0)
    available = safe_float(rec.get("available_fire_flow_gpm"), 0.0)
    residual = safe_float(rec.get("residual_pressure_psi"), safe_float(pressure.get("min_pressure_psi"), -1.0))
    min_required = safe_float(
        rec.get("min_required_residual_pressure_psi"),
        safe_float(pressure.get("min_required_pressure_psi"), 0.0),
    )
    return required > 0.0 and available >= required and residual >= min_required > 0.0


def _has_valid_sizing_optimization(value: Any) -> bool:
    rec = safe_dict(value)
    if not rec:
        return False
    status = safe_str(rec.get("status") or rec.get("selected")).lower()
    return status in {"checked", "optimized", "accepted", "selected"} or bool(safe_list(rec.get("alternatives")))


def _has_valid_detention_routing(row: Dict[str, Any]) -> bool:
    rec = safe_dict(row)
    if not _row_is_production_evidence(rec):
        return False
    stage_rows = [safe_dict(item) for item in safe_list(rec.get("stage_storage") or rec.get("stage_storage_rows"))]
    has_stage_storage = (
        len(stage_rows) >= 3
        and any(safe_float(item.get("storage_cf"), 0.0) > 0.0 for item in stage_rows)
        and any(_present(item.get("elevation_ft")) for item in stage_rows)
    )
    provided_storage = safe_float(rec.get("provided_storage_cf"), 0.0)
    release = max(
        safe_float(rec.get("release_cfs"), 0.0),
        safe_float(rec.get("outlet_release_cfs"), 0.0),
        safe_float(rec.get("outflow_cfs"), 0.0),
    )
    drawdown = max(
        safe_float(rec.get("drawdown_hours"), 0.0),
        safe_float(rec.get("estimated_drawdown_hours"), 0.0),
        safe_float(rec.get("actual_drawdown_hours"), 0.0),
    )
    outlet = safe_dict(rec.get("outlet") or rec.get("outlet_structure"))
    has_outlet = bool(outlet) or _present(rec.get("outlet_release_cfs"))
    status = safe_str(rec.get("status")).lower()
    if status in {"deficient", "concept_only", "blocked", "invalid"}:
        return False
    return (has_stage_storage or provided_storage > 0.0) and has_outlet and release > 0.0 and drawdown > 0.0


def _valid_flag(value: Any) -> bool:
    return safe_dict(value).get("valid") is True


def _has_valid_overflow_routing(drainage: Dict[str, Any], storm: Dict[str, Any]) -> bool:
    paths = safe_list(drainage.get("overflow_paths") or storm.get("overflow_paths"))
    overflow_analysis = safe_dict(drainage.get("overflow_analysis"))
    if overflow_analysis:
        if overflow_analysis.get("production_valid") is True:
            return True
        if overflow_analysis.get("valid") is False:
            return False
        if "production_valid" in overflow_analysis or safe_str(overflow_analysis.get("capacity_status")):
            return False
    return bool(paths)


def _all_rows_valid(rows: Iterable[Dict[str, Any]]) -> bool:
    clean_rows = [safe_dict(row) for row in rows]
    return bool(clean_rows) and all(row.get("valid") is True for row in clean_rows)


def _check(name: str, ok: bool, *, evidence: str = "", blocker: str = "") -> Dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "evidence": evidence,
        "blocker": "" if ok else blocker,
    }


def _segment_endpoints(segment: Dict[str, Any]) -> Tuple[str, str]:
    start = safe_str(segment.get("start_node") or segment.get("from_node") or segment.get("upstream_node"))
    end = safe_str(segment.get("end_node") or segment.get("to_node") or segment.get("downstream_node"))
    if start and end:
        return start, end
    points = safe_list(segment.get("path") or segment.get("route_points") or segment.get("points"))
    if len(points) >= 2:
        return _point_key(points[0]), _point_key(points[-1])
    return "", ""


def _point_key(point: Any) -> str:
    if isinstance(point, dict):
        return f"{safe_float(point.get('x'), 0.0):.3f},{safe_float(point.get('y'), 0.0):.3f}"
    if isinstance(point, (list, tuple)) and len(point) >= 2:
        return f"{safe_float(point[0], 0.0):.3f},{safe_float(point[1], 0.0):.3f}"
    return safe_str(point)


def _has_cycle(segments: Iterable[Dict[str, Any]]) -> bool:
    graph: Dict[str, List[str]] = defaultdict(list)
    edge_count = 0
    for segment in segments:
        start, end = _segment_endpoints(segment)
        if not start or not end:
            continue
        graph[start].append(end)
        graph[end].append(start)
        edge_count += 1
    if edge_count <= 0:
        return False
    visited = set()

    def visit(node: str, parent: str) -> bool:
        visited.add(node)
        for nxt in graph[node]:
            if nxt == parent:
                continue
            if nxt in visited or visit(nxt, node):
                return True
        return False

    return any(visit(node, "") for node in graph if node not in visited)


def _finalize(system: str, checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    blockers = [check["blocker"] for check in checks if not check["ok"] and check["blocker"]]
    evidence = [check["evidence"] for check in checks if check["ok"] and check["evidence"]]
    return {
        "system": system,
        "production_ready": not blockers,
        "checks": checks,
        "blockers": blockers,
        "blocker_details": blocker_explanations(blockers),
        "evidence": evidence,
        "truth_label": "Depth validator checks explicit backend evidence only; missing evidence remains blocked for engineering review.",
    }


def validate_stormwater_depth(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else safe_dict(plan_or_meta)
    storm = safe_dict(meta.get("storm_pipes") or meta.get("storm_pipe_summary"))
    drainage = safe_dict(meta.get("drainage") or meta.get("drainage_canonical"))
    segments = [safe_dict(item) for item in safe_list(storm.get("segments"))]
    catchments = safe_list(drainage.get("catchments") or storm.get("catchments"))
    basins = safe_list(drainage.get("basins") or storm.get("basins"))
    inlet_checks = [safe_dict(item) for item in safe_list(storm.get("inlet_capacity_checks"))]
    overflow_analysis = safe_dict(drainage.get("overflow_analysis"))
    hgl_rows = [safe_dict(row) for row in safe_list(storm.get("hgl_profile"))]
    egl_rows = [safe_dict(row) for row in safe_list(storm.get("egl_profile"))]
    detention_rows = [safe_dict(row) for row in safe_list(drainage.get("detention_routing"))]
    for basin in basins:
        detention_rows.extend(
            safe_dict(row)
            for row in safe_list(safe_dict(basin).get("detention_routing") or safe_dict(basin).get("stage_storage"))
        )
    checks = [
        _check("tributary_areas", any(safe_float(seg.get("tributary_area_sf") or seg.get("upstream_cumulative_area_sf"), 0.0) > 0.0 for seg in segments) or bool(catchments), evidence="tributary areas/catchments", blocker="Storm depth needs true tributary areas tied to pipes or catchments."),
        _check("runoff_coefficients", any(_present(safe_dict(item).get("runoff_c") or safe_dict(item).get("runoff_coefficient")) for item in catchments) or _present(drainage.get("runoff_coefficient")), evidence="runoff coefficients", blocker="Storm depth needs runoff coefficients by catchment/surface."),
        _check("hgl_egl_profiles", bool(hgl_rows and egl_rows and ((_has_production_rows(hgl_rows) and _has_production_rows(egl_rows)) or storm.get("hydraulic_source") == "engine")), evidence="HGL/EGL profile rows", blocker="Storm depth needs HGL and EGL profiles from production hydraulic evidence."),
        _check("tailwater", _present(storm.get("tailwater_elev_ft")), evidence="tailwater elevation", blocker="Storm depth needs tailwater/backwater evidence."),
        _check(
            "inlet_capacity",
            _all_rows_valid(inlet_checks),
            evidence="inlet capacity/spread/bypass checks",
            blocker="Storm depth needs passing inlet capacity, spread, and bypass checks.",
        ),
        _check(
            "detention_routing",
            any(_has_valid_detention_routing(row) for row in detention_rows),
            evidence="detention stage-storage/routing",
            blocker="Storm depth needs production detention stage-storage/outlet/drawdown routing.",
        ),
        _check(
            "overflow_routing",
            _has_valid_overflow_routing(drainage, storm),
            evidence="overflow routing/capacity",
            blocker="Storm depth needs overflow routing evidence.",
        ),
    ]
    return _finalize("stormwater_depth", checks)


def validate_water_system_depth(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else safe_dict(plan_or_meta)
    water = safe_dict(meta.get("water") or meta.get("water_summary"))
    utilities = safe_dict(meta.get("utilities") or meta.get("utility_summary"))
    source = water or utilities
    hooks = safe_dict(source.get("conflict_hooks"))
    segments = [safe_dict(item) for item in safe_list(source.get("segments") or hooks.get("utility_segments"))]
    hydrants = safe_list(source.get("hydrants") or source.get("fire_hydrants"))
    pressure = safe_dict(source.get("pressure_validation"))
    velocity_checks = safe_list(source.get("velocity_checks"))
    looped = bool(source.get("looped") or source.get("is_looped")) or _has_cycle(segments)
    checks = [
        _check("pressure_zones", bool(safe_list(source.get("pressure_zones")) or safe_dict(source.get("pressure_zone"))), evidence="pressure zones", blocker="Water depth needs pressure zones."),
        _check("hydrant_spacing", bool(hydrants and _has_valid_hydrant_spacing(source.get("hydrant_spacing_validation"))), evidence="hydrant spacing evidence", blocker="Water depth needs passing hydrant spacing coverage."),
        _check("fire_flow", _has_valid_fire_flow_validation(source.get("fire_flow_validation"), pressure), evidence="fire flow validation", blocker="Water depth needs passing fire-flow validation."),
        _check("looping", looped, evidence="looped network graph", blocker="Water depth needs looping/redundancy evidence."),
        _check("pressure_validation", _has_valid_pressure_validation(pressure), evidence="pressure validation", blocker="Water depth needs passing pressure validation."),
        _check("velocity_checks", bool(velocity_checks) and all(_has_valid_velocity(safe_dict(item)) for item in velocity_checks), evidence="velocity checks", blocker="Water depth needs passing velocity checks."),
        _check("sizing_optimization", _has_valid_sizing_optimization(source.get("sizing_optimization")) or bool(safe_list(source.get("sizing_alternatives"))), evidence="sizing optimization", blocker="Water depth needs sizing optimization evidence."),
    ]
    return _finalize("water_system_depth", checks)


def validate_roadway_corridor_depth(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else safe_dict(plan_or_meta)
    grading_detail = safe_dict(meta.get("grading_detail"))
    crown_rows = [safe_dict(row) for row in safe_list(grading_detail.get("road_crown_controls") or meta.get("road_crowns"))]
    ada_rows = [safe_dict(row) for row in safe_list(grading_detail.get("ada_path_checks"))]
    ada_summary = safe_dict(meta.get("ada_compliance"))
    ada_ready = _all_rows_valid(ada_rows) or _valid_flag(ada_summary)
    checks = [
        _check("alignments", bool(safe_list(meta.get("alignments") or meta.get("road_alignments"))), evidence="road alignments", blocker="Roadway depth needs alignments."),
        _check("profiles", bool(safe_list(meta.get("profiles") or meta.get("road_profiles"))), evidence="road profiles", blocker="Roadway depth needs profiles."),
        _check("intersections", bool(safe_list(meta.get("intersections"))), evidence="intersections", blocker="Roadway depth needs intersection geometry."),
        _check("curb_returns", bool(safe_list(meta.get("curb_returns"))), evidence="curb returns", blocker="Roadway depth needs curb-return geometry."),
        _check("crowns", any(_has_verified_crown(row) for row in crown_rows), evidence="road crown controls", blocker="Roadway depth needs verified road crown controls tied to a profile or standard."),
        _check("sidewalks", bool(safe_list(meta.get("sidewalks") or meta.get("pedestrian_paths"))), evidence="sidewalk/pedestrian paths", blocker="Roadway depth needs sidewalk/path geometry."),
        _check("ada", ada_ready, evidence="ADA compliance checks", blocker="Roadway depth needs passing ADA checks."),
        _check("sections", bool(safe_list(meta.get("cross_sections") or meta.get("corridor_sections"))), evidence="corridor sections", blocker="Roadway depth needs corridor sections."),
    ]
    return _finalize("roadway_corridor_depth", checks)


__all__ = [
    "validate_roadway_corridor_depth",
    "validate_stormwater_depth",
    "validate_water_system_depth",
]
