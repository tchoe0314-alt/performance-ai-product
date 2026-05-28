from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Tuple

from .common import safe_dict, safe_float, safe_list, safe_str


def _present(value: Any) -> bool:
    return value not in (None, "", [], {})


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
    checks = [
        _check("tributary_areas", any(safe_float(seg.get("tributary_area_sf") or seg.get("upstream_cumulative_area_sf"), 0.0) > 0.0 for seg in segments) or bool(catchments), evidence="tributary areas/catchments", blocker="Storm depth needs true tributary areas tied to pipes or catchments."),
        _check("runoff_coefficients", any(_present(safe_dict(item).get("runoff_c") or safe_dict(item).get("runoff_coefficient")) for item in catchments) or _present(drainage.get("runoff_coefficient")), evidence="runoff coefficients", blocker="Storm depth needs runoff coefficients by catchment/surface."),
        _check("hgl_egl_profiles", bool(safe_list(storm.get("hgl_profile")) and safe_list(storm.get("egl_profile"))), evidence="HGL/EGL profile rows", blocker="Storm depth needs HGL and EGL profiles."),
        _check("tailwater", _present(storm.get("tailwater_elev_ft")), evidence="tailwater elevation", blocker="Storm depth needs tailwater/backwater evidence."),
        _check(
            "inlet_capacity",
            bool(inlet_checks) and all(item.get("valid") is not False for item in inlet_checks),
            evidence="inlet capacity/spread/bypass checks",
            blocker="Storm depth needs passing inlet capacity, spread, and bypass checks.",
        ),
        _check("detention_routing", any(safe_list(safe_dict(basin).get("detention_routing") or safe_dict(basin).get("stage_storage")) for basin in basins) or bool(safe_list(drainage.get("detention_routing"))), evidence="detention stage-storage/routing", blocker="Storm depth needs detention stage-storage/outlet/drawdown routing."),
        _check(
            "overflow_routing",
            bool(safe_list(drainage.get("overflow_paths") or storm.get("overflow_paths"))) or overflow_analysis.get("valid") is True,
            evidence="overflow routing",
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
    velocity_checks = safe_list(source.get("velocity_checks")) or [seg for seg in segments if _present(seg.get("velocity_fps"))]
    looped = bool(source.get("looped") or source.get("is_looped")) or _has_cycle(segments)
    checks = [
        _check("pressure_zones", bool(safe_list(source.get("pressure_zones")) or safe_dict(source.get("pressure_zone"))), evidence="pressure zones", blocker="Water depth needs pressure zones."),
        _check("hydrant_spacing", bool(hydrants and (source.get("hydrant_spacing_validation") or len(hydrants) >= 2)), evidence="hydrant spacing evidence", blocker="Water depth needs hydrant spacing coverage."),
        _check("fire_flow", bool(safe_dict(source.get("fire_flow_validation")).get("valid") or safe_float(source.get("available_fire_flow_gpm"), 0.0) > 0.0), evidence="fire flow validation", blocker="Water depth needs fire-flow validation."),
        _check("looping", looped, evidence="looped network graph", blocker="Water depth needs looping/redundancy evidence."),
        _check("pressure_validation", bool(pressure and pressure.get("valid") is not None), evidence="pressure validation", blocker="Water depth needs pressure validation."),
        _check("velocity_checks", bool(velocity_checks), evidence="velocity checks", blocker="Water depth needs velocity checks."),
        _check("sizing_optimization", bool(safe_dict(source.get("sizing_optimization")) or safe_list(source.get("sizing_alternatives"))), evidence="sizing optimization", blocker="Water depth needs sizing optimization evidence."),
    ]
    return _finalize("water_system_depth", checks)


def validate_roadway_corridor_depth(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else safe_dict(plan_or_meta)
    grading_detail = safe_dict(meta.get("grading_detail"))
    checks = [
        _check("alignments", bool(safe_list(meta.get("alignments") or meta.get("road_alignments"))), evidence="road alignments", blocker="Roadway depth needs alignments."),
        _check("profiles", bool(safe_list(meta.get("profiles") or meta.get("road_profiles"))), evidence="road profiles", blocker="Roadway depth needs profiles."),
        _check("intersections", bool(safe_list(meta.get("intersections"))), evidence="intersections", blocker="Roadway depth needs intersection geometry."),
        _check("curb_returns", bool(safe_list(meta.get("curb_returns"))), evidence="curb returns", blocker="Roadway depth needs curb-return geometry."),
        _check("crowns", bool(safe_list(grading_detail.get("road_crown_controls") or meta.get("road_crowns"))), evidence="road crown controls", blocker="Roadway depth needs road crown controls."),
        _check("sidewalks", bool(safe_list(meta.get("sidewalks") or meta.get("pedestrian_paths"))), evidence="sidewalk/pedestrian paths", blocker="Roadway depth needs sidewalk/path geometry."),
        _check("ada", bool(safe_list(grading_detail.get("ada_path_checks")) or safe_dict(meta.get("ada_compliance"))), evidence="ADA compliance checks", blocker="Roadway depth needs ADA checks."),
        _check("sections", bool(safe_list(meta.get("cross_sections") or meta.get("corridor_sections"))), evidence="corridor sections", blocker="Roadway depth needs corridor sections."),
    ]
    return _finalize("roadway_corridor_depth", checks)


__all__ = [
    "validate_roadway_corridor_depth",
    "validate_stormwater_depth",
    "validate_water_system_depth",
]
