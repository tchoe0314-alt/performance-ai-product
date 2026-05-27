from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence, Tuple

from engines.storm.hydraulic_engine import analyze_storm_hydraulics
from engines.storm.storm_types import HydraulicAnalysisRequest, StormNode, StormPipe, StormPoint
from engines.water_sizing_engine import WaterSizingEngine, analyze_water_pressure_graph

from .common import polyline_length, safe_dict, safe_float, safe_int, safe_list, safe_str


def _point_xy(point: Any) -> Optional[Tuple[float, float]]:
    if isinstance(point, dict):
        x_val = point.get("x")
        y_val = point.get("y")
    elif isinstance(point, (list, tuple)) and len(point) >= 2:
        x_val = point[0]
        y_val = point[1]
    else:
        x_val = getattr(point, "x", None)
        y_val = getattr(point, "y", None)
    if x_val is None or y_val is None:
        return None
    return safe_float(x_val, 0.0), safe_float(y_val, 0.0)


def _path_points(segment: Dict[str, Any]) -> List[List[float]]:
    raw_points = safe_list(segment.get("path")) or safe_list(segment.get("route_points")) or safe_list(segment.get("points"))
    points: List[List[float]] = []
    for point in raw_points:
        xy = _point_xy(point)
        if xy is not None:
            points.append([round(xy[0], 3), round(xy[1], 3)])
    return points


def _segment_name(segment: Dict[str, Any], fallback_index: int = 1) -> str:
    return (
        safe_str(segment.get("pipe"))
        or safe_str(segment.get("name"))
        or safe_str(segment.get("id"))
        or f"SEG-{fallback_index}"
    )


def _node_name_from_segment(segment: Dict[str, Any], key: str, fallback: str) -> str:
    if key == "from":
        return (
            safe_str(segment.get("from"))
            or safe_str(segment.get("start_name"))
            or safe_str(segment.get("upstream_node_name"))
            or fallback
        )
    return (
        safe_str(segment.get("to"))
        or safe_str(segment.get("end_name"))
        or safe_str(segment.get("downstream_node_name"))
        or fallback
    )


def _storm_hydraulic_request_from_summary(storm: Dict[str, Any], segments: Sequence[Dict[str, Any]]) -> Optional[HydraulicAnalysisRequest]:
    pipes: List[StormPipe] = []
    nodes_by_name: Dict[str, StormNode] = {}

    def _ensure_node(name: str, point: Sequence[float], invert: float, rim: float) -> None:
        if not name or name in nodes_by_name:
            return
        nodes_by_name[name] = StormNode(
            name=name,
            point=StormPoint(safe_float(point[0], 0.0), safe_float(point[1], 0.0), rim),
            rim_elev_ft=round(rim, 3),
            invert_elev_ft=round(invert, 3),
        )

    for raw_node in safe_list(storm.get("nodes")) + safe_list(storm.get("structures")) + safe_list(storm.get("inlets")):
        node = safe_dict(raw_node)
        name = safe_str(node.get("name") or node.get("id") or node.get("node_id"))
        if not name:
            continue
        point = _point_xy(node.get("point")) or (
            safe_float(node.get("x"), 0.0),
            safe_float(node.get("y"), 0.0),
        )
        invert = safe_float(node.get("invert_elev_ft") or node.get("invert_ft"), safe_float(node.get("z"), 0.0) - 4.0)
        rim = safe_float(node.get("rim_elev_ft") or node.get("rim_ft") or node.get("z"), invert + 4.0)
        _ensure_node(name, point, invert, rim)

    for index, segment in enumerate(segments, start=1):
        name = _segment_name(segment, index)
        path = _path_points(segment)
        if len(path) < 2:
            continue
        length = max(1.0, safe_float(segment.get("length_ft"), polyline_length(path)))
        start_inv = safe_float(segment.get("start_invert_ft"), safe_float(segment.get("start_invert"), 0.0))
        end_inv = safe_float(segment.get("end_invert_ft"), safe_float(segment.get("end_invert"), start_inv - 0.003 * length))
        slope = safe_float(segment.get("slope_ft_ft"), safe_float(segment.get("slope"), 0.0))
        if slope <= 0.0:
            slope = max((start_inv - end_inv) / max(length, 1e-9), 0.0001)
        upstream = _node_name_from_segment(segment, "from", f"{name}-UP")
        downstream = _node_name_from_segment(segment, "to", f"{name}-DN")
        _ensure_node(upstream, path[0], start_inv, safe_float(segment.get("start_rim_ft"), start_inv + 5.0))
        _ensure_node(downstream, path[-1], end_inv, safe_float(segment.get("end_rim_ft"), end_inv + 5.0))
        pipes.append(
            StormPipe(
                name=name,
                pipe_type=safe_str(segment.get("pipe_type"), safe_str(segment.get("segment_role"), "main")),
                upstream_node_name=upstream,
                downstream_node_name=downstream,
                diameter_in=max(1.0, safe_float(segment.get("diameter_in"), safe_float(segment.get("diameter_ft"), 1.0) * 12.0)),
                length_ft=length,
                slope=max(slope, 0.0001),
                mannings_n=max(0.001, safe_float(segment.get("mannings_n"), safe_float(segment.get("n"), 0.013))),
                upstream_invert_ft=start_inv,
                downstream_invert_ft=end_inv,
                route_points=[(safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)) for pt in path],
                assigned_runoff_cfs=max(0.0, safe_float(segment.get("flow_cfs"), safe_float(segment.get("governing_flow_cfs"), 0.0))),
                meta={
                    "tributary_area_sf": max(
                        0.0,
                        safe_float(segment.get("tributary_area_sf"), safe_float(segment.get("upstream_cumulative_area_sf"), 0.0)),
                    ),
                    "tributary_runoff_cfs": max(0.0, safe_float(segment.get("flow_cfs"), 0.0)),
                    "tributary_catchment_count": safe_int(segment.get("tributary_catchment_count"), 0),
                    "tributary_basin_names": safe_list(segment.get("tributary_basin_names")),
                },
            )
        )
    if not pipes:
        return None
    return HydraulicAnalysisRequest(
        pipes=pipes,
        nodes=list(nodes_by_name.values()),
        compute_hgl=True,
        compute_egl=True,
        allow_partial_flow=True,
        meta={"source": "storm_summary_recompute"},
    )


def _stage_storage_rows(basin: Dict[str, Any], design: Dict[str, Any]) -> List[Dict[str, Any]]:
    provided = max(0.0, safe_float(design.get("provided_storage_cf"), 0.0))
    required = max(0.0, safe_float(design.get("required_storage_cf"), 0.0))
    bottom = safe_float(design.get("bottom_elev_ft"), safe_float(basin.get("bottom_elev_ft"), 0.0))
    normal = safe_float(design.get("normal_pool_elev_ft"), safe_float(basin.get("normal_pool_elev_ft"), bottom + 2.0))
    top = safe_float(design.get("top_of_bank_elev_ft"), safe_float(basin.get("top_of_bank_elev_ft"), normal + 2.0))
    required_storage = required if required > 0.0 else provided * 0.8
    return [
        {
            "stage_name": "bottom",
            "elevation_ft": round(bottom, 3),
            "storage_cf": 0.0,
        },
        {
            "stage_name": "design_required",
            "elevation_ft": round(normal, 3),
            "storage_cf": round(required_storage, 3),
        },
        {
            "stage_name": "top_of_bank",
            "elevation_ft": round(max(top, normal), 3),
            "storage_cf": round(max(provided, required_storage), 3),
        },
    ]


def enrich_drainage_production_depth(drainage: Dict[str, Any]) -> Dict[str, Any]:
    """Add deterministic detention/routing evidence from canonical drainage data.

    The rows are intentionally labeled as concept-stage routing evidence unless a
    later engine supplies a more rigorous hydrograph method.
    """

    enriched = deepcopy(safe_dict(drainage))
    routing: List[Dict[str, Any]] = []
    all_stage_storage: List[Dict[str, Any]] = []
    for index, basin_raw in enumerate(safe_list(enriched.get("basins")), start=1):
        basin = safe_dict(basin_raw)
        design = safe_dict(basin.get("detention_design")) or safe_dict(basin.get("engineering")) or basin
        basin_name = safe_str(basin.get("name")) or safe_str(basin.get("target_name")) or f"BASIN-{index}"
        provided = max(0.0, safe_float(design.get("provided_storage_cf"), safe_float(design.get("storage_cf"), 0.0)))
        required = max(0.0, safe_float(design.get("required_storage_cf"), 0.0))
        inflow = max(
            0.0,
            safe_float(design.get("peak_inflow_cfs"), 0.0),
            safe_float(design.get("tributary_flow_cfs"), 0.0),
            safe_float(basin.get("tributary_flow_cfs"), 0.0),
        )
        release = max(0.0, safe_float(design.get("release_cfs"), safe_float(design.get("outlet_release_cfs"), 0.0)))
        rows = _stage_storage_rows(basin, design)
        all_stage_storage.extend([{**row, "basin": basin_name} for row in rows])
        adequate = provided >= required if required > 0.0 and provided > 0.0 else None
        routing.append(
            {
                "basin": basin_name,
                "routing_source": safe_str(design.get("routing_source"), "concept_detention_design"),
                "routing_method": safe_str(design.get("routing_method"), "stage_storage_concept"),
                "status": "adequate" if adequate is True else "needs_capacity_review" if adequate is False else "concept_only",
                "required_storage_cf": round(required, 3),
                "provided_storage_cf": round(provided, 3),
                "peak_inflow_cfs": round(inflow, 3),
                "release_cfs": round(release, 3),
                "drawdown_hours": round(max(0.0, safe_float(design.get("drawdown_hours"), 0.0)), 3),
                "freeboard_ft": (
                    round(
                        safe_float(design.get("top_of_bank_elev_ft"), 0.0)
                        - safe_float(design.get("high_water_elev_ft"), 0.0),
                        3,
                    )
                    if design.get("top_of_bank_elev_ft") is not None and design.get("high_water_elev_ft") is not None
                    else None
                ),
                "stage_storage": rows,
                "truth_label": "concept-stage detention routing; verify against jurisdiction method before construction.",
            }
        )
    if routing:
        enriched["detention_routing"] = routing
        enriched["stage_storage"] = all_stage_storage
    return enriched


def enrich_storm_production_depth(storm: Dict[str, Any], drainage: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Attach HGL/EGL, tailwater, inlet checks, and summary context to storm truth."""

    enriched = deepcopy(safe_dict(storm))
    drainage_meta = safe_dict(drainage)
    segments = [safe_dict(item) for item in safe_list(enriched.get("segments"))]
    hydraulic_request = _storm_hydraulic_request_from_summary(enriched, segments)
    if hydraulic_request is not None:
        hydraulic_result = analyze_storm_hydraulics(hydraulic_request)
        if hydraulic_result.success:
            by_name = {pipe.name: pipe for pipe in hydraulic_result.pipes}
            for index, segment in enumerate(segments, start=1):
                pipe = by_name.get(_segment_name(segment, index))
                if pipe is None or pipe.hydraulic is None:
                    continue
                segment["capacity_cfs"] = round(pipe.hydraulic.full_capacity_cfs, 3)
                segment["capacity_ratio"] = (
                    round(pipe.hydraulic.design_flow_cfs / max(pipe.hydraulic.full_capacity_cfs, 1e-9), 3)
                    if pipe.hydraulic.design_flow_cfs > 0.0
                    else 0.0
                )
                segment["velocity_fps"] = round(pipe.hydraulic.velocity_fps, 3)
                segment["normal_depth_ft"] = round(pipe.hydraulic.normal_depth_ft, 3)
                segment["hgl_start"] = segment["hgl_start_ft"] = pipe.hydraulic.hgl_upstream_ft
                segment["hgl_end"] = segment["hgl_end_ft"] = pipe.hydraulic.hgl_downstream_ft
                segment["egl_start"] = segment["egl_start_ft"] = pipe.hydraulic.egl_upstream_ft
                segment["egl_end"] = segment["egl_end_ft"] = pipe.hydraulic.egl_downstream_ft
                segment["capacity_status"] = pipe.hydraulic.capacity_status
                segment["hydraulic_depth_source"] = "storm_hydraulic_engine"
            enriched["hydraulic_engine_summary"] = {
                **safe_dict(hydraulic_result.summary),
                "warnings": list(hydraulic_result.warnings),
                "truth_label": "Storm HGL/EGL, velocity, normal depth, and capacity are computed by the storm hydraulic engine from canonical pipe/node data.",
            }
            enriched["hydraulic_source"] = "engine"
            enriched["segments"] = segments
    hgl_profile: List[Dict[str, Any]] = []
    egl_profile: List[Dict[str, Any]] = []
    station = 0.0
    max_ratio = 0.0
    controlling = safe_str(enriched.get("controlling_segment"))
    total_flow = 0.0
    total_capacity = 0.0
    total_area_sf = 0.0
    segment_hydraulics: List[Dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        name = _segment_name(segment, index)
        points = _path_points(segment)
        length = max(
            1.0,
            safe_float(segment.get("length_ft"), 0.0),
            polyline_length(points) if len(points) >= 2 else 0.0,
        )
        diameter_ft = max(0.5, safe_float(segment.get("diameter_ft"), safe_float(segment.get("diameter_in"), 12.0) / 12.0))
        flow = max(0.0, safe_float(segment.get("flow_cfs"), safe_float(segment.get("governing_flow_cfs"), 0.0)))
        capacity = max(0.0, safe_float(segment.get("capacity_cfs"), 0.0))
        ratio = safe_float(segment.get("capacity_ratio"), flow / capacity if capacity > 0.0 else 0.0)
        velocity = max(0.0, safe_float(segment.get("velocity_fps"), 0.0))
        start_inv = safe_float(segment.get("start_invert_ft"), safe_float(segment.get("start_invert"), 0.0))
        end_inv = safe_float(segment.get("end_invert_ft"), safe_float(segment.get("end_invert"), start_inv - 0.01 * length))
        depth_fraction = max(0.15, min(1.0, ratio if ratio > 0.0 else 0.35))
        hgl_start = safe_float(segment.get("hgl_start"), start_inv + diameter_ft * depth_fraction)
        hgl_end = safe_float(segment.get("hgl_end"), end_inv + diameter_ft * depth_fraction)
        velocity_head = (velocity * velocity) / (2.0 * 32.2) if velocity > 0.0 else 0.05
        egl_start = safe_float(segment.get("egl_start"), hgl_start + velocity_head)
        egl_end = safe_float(segment.get("egl_end"), hgl_end + velocity_head)
        hgl_profile.extend(
            [
                {"station_ft": round(station, 3), "hgl_ft": round(hgl_start, 3), "segment": name},
                {"station_ft": round(station + length, 3), "hgl_ft": round(hgl_end, 3), "segment": name},
            ]
        )
        egl_profile.extend(
            [
                {"station_ft": round(station, 3), "egl_ft": round(egl_start, 3), "segment": name},
                {"station_ft": round(station + length, 3), "egl_ft": round(egl_end, 3), "segment": name},
            ]
        )
        segment["hgl_start_ft"] = round(hgl_start, 3)
        segment["hgl_end_ft"] = round(hgl_end, 3)
        segment["egl_start_ft"] = round(egl_start, 3)
        segment["egl_end_ft"] = round(egl_end, 3)
        segment_hydraulics.append(
            {
                "segment": name,
                "station_start_ft": station,
                "station_end_ft": station + length,
                "hgl_start_ft": hgl_start,
                "hgl_end_ft": hgl_end,
                "crown_start_ft": start_inv + diameter_ft,
                "crown_end_ft": end_inv + diameter_ft,
            }
        )
        segment.setdefault("hydraulic_depth_source", "hydraulic_engine" if safe_str(enriched.get("hydraulic_source")) == "engine" else "concept_hgl_egl_proxy")
        max_ratio = max(max_ratio, ratio)
        if not controlling or ratio >= safe_float(safe_dict(next((seg for seg in segments if _segment_name(seg) == controlling), {})).get("capacity_ratio"), -1.0):
            controlling = name
        total_flow += flow
        total_capacity += capacity
        total_area_sf += max(0.0, safe_float(segment.get("tributary_area_sf"), safe_float(segment.get("upstream_cumulative_area_sf"), 0.0)))
        station += length
    if segments:
        enriched["segments"] = segments
        enriched.setdefault("hgl_profile", hgl_profile)
        enriched.setdefault("egl_profile", egl_profile)
        enriched.setdefault("hydraulic_depth_source", "storm_hydraulic_engine_or_concept_proxy")
    target = safe_dict(enriched.get("target_outfall")) or safe_dict(enriched.get("outfall_target_metadata")) or safe_dict(drainage_meta.get("coordination", {}).get("preferred_outfall"))
    tailwater = safe_float(target.get("z"), float("nan")) if target.get("z") is not None else float("nan")
    if not math.isfinite(tailwater) and hgl_profile:
        tailwater = safe_float(hgl_profile[-1].get("hgl_ft"), 0.0) - 0.25
    if math.isfinite(tailwater):
        enriched["tailwater_elev_ft"] = round(tailwater, 3)
        enriched["tailwater_source"] = "selected_outfall_or_terminal_hgl"
        terminal_hgl = safe_float(hgl_profile[-1].get("hgl_ft"), tailwater) if hgl_profile else tailwater
        surcharge = max(tailwater - terminal_hgl, 0.0)
        total_station = max((safe_float(row.get("station_ft"), 0.0) for row in hgl_profile), default=0.0)
        backwater_rows: List[Dict[str, Any]] = []
        surcharged_segments: List[Dict[str, Any]] = []
        for row in segment_hydraulics:
            start_station = safe_float(row.get("station_start_ft"), 0.0)
            end_station = safe_float(row.get("station_end_ft"), start_station)
            if total_station > 0.0 and surcharge > 0.0:
                start_influence = max(0.0, min(1.0, 1.0 - ((total_station - start_station) / total_station)))
                end_influence = max(0.0, min(1.0, 1.0 - ((total_station - end_station) / total_station)))
            else:
                start_influence = end_influence = 0.0
            adjusted_start = safe_float(row.get("hgl_start_ft"), 0.0) + surcharge * start_influence
            adjusted_end = safe_float(row.get("hgl_end_ft"), 0.0) + surcharge * end_influence
            max_above_crown = max(
                adjusted_start - safe_float(row.get("crown_start_ft"), adjusted_start),
                adjusted_end - safe_float(row.get("crown_end_ft"), adjusted_end),
                0.0,
            )
            payload = {
                "segment": safe_str(row.get("segment")),
                "adjusted_hgl_start_ft": round(adjusted_start, 3),
                "adjusted_hgl_end_ft": round(adjusted_end, 3),
                "max_hgl_above_crown_ft": round(max_above_crown, 3),
            }
            backwater_rows.append(payload)
            if max_above_crown > 0.05:
                surcharged_segments.append(payload)
        enriched["backwater_validation"] = {
            "valid": not surcharged_segments,
            "tailwater_controls_hgl": surcharge > 0.01,
            "tailwater_elev_ft": round(tailwater, 3),
            "terminal_hgl_ft": round(terminal_hgl, 3),
            "max_tailwater_surcharge_ft": round(surcharge, 3),
            "surcharged_segments": surcharged_segments,
            "profile": backwater_rows,
            "truth_label": "Tailwater/backwater check compares terminal HGL against pipe crown using supplied or selected outfall elevation.",
        }
    inlet_checks: List[Dict[str, Any]] = []
    structures = safe_list(drainage_meta.get("structures")) or safe_list(drainage_meta.get("inlets"))
    for index, structure_raw in enumerate(structures[:25], start=1):
        structure = safe_dict(structure_raw)
        name = safe_str(structure.get("name")) or safe_str(structure.get("id")) or f"INLET-{index}"
        demand = max(
            0.0,
            safe_float(structure.get("estimated_flow_cfs"), 0.0),
            safe_float(structure.get("contributing_runoff_cfs"), 0.0),
        )
        capacity = max(demand * 1.25, safe_float(structure.get("capacity_cfs"), 0.0), 0.5)
        inlet_checks.append(
            {
                "inlet": name,
                "demand_cfs": round(demand, 3),
                "capacity_cfs": round(capacity, 3),
                "capacity_ratio": round(demand / max(capacity, 1e-9), 4),
                "spread_ft": round(max(2.0, demand * 3.0), 3),
                "bypass_cfs": round(max(0.0, demand - capacity), 3),
                "truth_label": "concept inlet capacity check; confirm grate/curb opening with local standard.",
            }
        )
    if inlet_checks:
        enriched["inlet_capacity_checks"] = inlet_checks
    hydraulic_summary = safe_dict(enriched.get("hydraulic_summary"))
    hydraulic_summary.setdefault("system_tributary_area_sf", round(total_area_sf, 3))
    hydraulic_summary.setdefault("system_tributary_runoff_cfs", round(total_flow, 3))
    hydraulic_summary.setdefault("max_capacity_ratio", round(max_ratio, 4))
    enriched["hydraulic_summary"] = hydraulic_summary
    enriched.setdefault("total_system_flow_cfs", round(total_flow, 3))
    enriched.setdefault("total_system_capacity_cfs", round(total_capacity, 3))
    enriched.setdefault("max_capacity_ratio", round(max_ratio, 4))
    enriched.setdefault("controlling_segment", controlling)
    return enriched


def _finite_or_none(value: Any) -> Optional[float]:
    number = safe_float(value, float("nan"))
    return number if math.isfinite(number) else None


def _water_segment_system(segment: Dict[str, Any], default_system: str = "") -> str:
    text = " ".join(
        safe_str(value).lower()
        for value in (
            segment.get("system"),
            segment.get("system_type"),
            segment.get("utility_type"),
            segment.get("type"),
            segment.get("layer"),
            segment.get("name"),
            default_system,
        )
        if safe_str(value)
    )
    if any(token in text for token in ("sanitary", "sewer", "storm", "drain", "gas", "electric", "telecom", "fiber")):
        return "other"
    if any(token in text for token in ("water", "watr", "potable", "hydrant", "fire")):
        return "water"
    return "water" if default_system == "water" else "other"


def _endpoint_node_name(point: Sequence[float], fallback: str) -> str:
    if len(point) < 2:
        return fallback
    return f"N-{round(safe_float(point[0], 0.0), 3)}-{round(safe_float(point[1], 0.0), 3)}"


def _water_has_cycle(segments: Sequence[Dict[str, Any]]) -> bool:
    adjacency: Dict[str, List[str]] = {}
    for rec in segments:
        start = safe_str(rec.get("start_node") or rec.get("from_node"))
        end = safe_str(rec.get("end_node") or rec.get("to_node"))
        if not start or not end:
            continue
        adjacency.setdefault(start, []).append(end)
        adjacency.setdefault(end, []).append(start)
    visited: set[str] = set()

    def visit(node: str, parent: str) -> bool:
        visited.add(node)
        for neighbor in adjacency.get(node, []):
            if neighbor == parent:
                continue
            if neighbor in visited or visit(neighbor, node):
                return True
        return False

    return any(visit(node, "") for node in adjacency if node not in visited)


def _hydrant_spacing_validation(hydrants: Sequence[Any], *, default_limit_ft: float = 500.0) -> Dict[str, Any]:
    points: List[Tuple[str, float, float]] = []
    for index, item in enumerate(hydrants, start=1):
        rec = safe_dict(item)
        xy = _point_xy(rec)
        if xy is None:
            continue
        points.append((safe_str(rec.get("name") or rec.get("id"), f"HYD-{index}"), xy[0], xy[1]))
    if len(points) < 2:
        return {
            "valid": False,
            "hydrant_count": len(points),
            "missing_inputs": ["at_least_two_hydrants"],
            "truth_label": "Hydrant spacing was not validated because fewer than two hydrants have coordinates.",
        }
    ordered = sorted(points, key=lambda row: (row[1], row[2], row[0]))
    spacing_rows: List[Dict[str, Any]] = []
    max_spacing = 0.0
    for current, nxt in zip(ordered, ordered[1:]):
        distance = math.hypot(nxt[1] - current[1], nxt[2] - current[2])
        max_spacing = max(max_spacing, distance)
        spacing_rows.append(
            {
                "from": current[0],
                "to": nxt[0],
                "spacing_ft": round(distance, 3),
            }
        )
    limit = max(1.0, default_limit_ft)
    return {
        "valid": max_spacing <= limit,
        "hydrant_count": len(points),
        "max_spacing_ft": round(max_spacing, 3),
        "limit_ft": round(limit, 3),
        "spacing_rows": spacing_rows,
        "truth_label": "Coordinate-based hydrant spacing check; confirm jurisdiction spacing and fire-flow method.",
    }


def enrich_water_production_depth(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Attach pressure, hydrant, fire-flow, velocity, and sizing evidence.

    This function intentionally records missing inputs instead of inventing
    demand, pressure, hydrants, or looping. Validations only turn true when the
    necessary canonical inputs are present.
    """

    enriched = deepcopy(safe_dict(summary))
    hooks = safe_dict(enriched.get("conflict_hooks"))
    default_system = safe_str(hooks.get("utility_system_type")).lower()
    raw_segments = safe_list(enriched.get("water_segments")) or safe_list(enriched.get("segments")) or safe_list(hooks.get("utility_segments"))
    water_segments: List[Dict[str, Any]] = []
    graph_rows: List[Dict[str, Any]] = []
    velocity_checks: List[Dict[str, Any]] = []
    missing_inputs: List[Dict[str, Any]] = []
    engine = WaterSizingEngine()
    for index, raw_segment in enumerate(raw_segments, start=1):
        rec = deepcopy(safe_dict(raw_segment))
        if _water_segment_system(rec, default_system) != "water":
            continue
        name = safe_str(rec.get("name") or rec.get("id") or rec.get("pipe"), f"W-{index}")
        points = _path_points(rec)
        length_ft = max(
            0.0,
            safe_float(rec.get("length_ft"), safe_float(rec.get("length"), 0.0)),
            polyline_length(points) if len(points) >= 2 else 0.0,
        )
        diameter_in = safe_float(rec.get("diameter_in") or rec.get("assigned_size_in"), 0.0)
        flow_gpm = safe_float(
            rec.get("flow_gpm")
            or rec.get("assigned_flow_gpm")
            or rec.get("design_flow_gpm")
            or rec.get("demand_gpm"),
            0.0,
        )
        max_velocity = max(0.1, safe_float(rec.get("max_velocity_fps"), safe_float(enriched.get("max_velocity_fps"), 8.0)))
        if flow_gpm > 0.0 and diameter_in > 0.0:
            velocity = engine._velocity_fps(flow_gpm, diameter_in)
            rec["velocity_fps"] = velocity
            velocity_checks.append(
                {
                    "segment": name,
                    "flow_gpm": round(flow_gpm, 3),
                    "diameter_in": round(diameter_in, 3),
                    "velocity_fps": velocity,
                    "max_velocity_fps": round(max_velocity, 3),
                    "valid": velocity <= max_velocity,
                }
            )
        segment_missing: List[str] = []
        if length_ft <= 0.0:
            segment_missing.append("length_ft")
        if flow_gpm <= 0.0:
            segment_missing.append("flow_gpm")
        if diameter_in <= 0.0:
            segment_missing.append("diameter_in")
        start_node = safe_str(rec.get("start_node") or rec.get("from_node") or rec.get("start_name"))
        end_node = safe_str(rec.get("end_node") or rec.get("to_node") or rec.get("end_name"))
        if not start_node and points:
            start_node = _endpoint_node_name(points[0], f"{name}-START")
            rec["start_node_inferred_from_geometry"] = True
        if not end_node and points:
            end_node = _endpoint_node_name(points[-1], f"{name}-END")
            rec["end_node_inferred_from_geometry"] = True
        if not start_node or not end_node:
            segment_missing.append("start_end_nodes")
        rec["name"] = name
        rec["system_type"] = "water"
        rec["length_ft"] = round(length_ft, 3)
        if diameter_in > 0.0:
            rec["diameter_in"] = round(diameter_in, 3)
        if flow_gpm > 0.0:
            rec["flow_gpm"] = round(flow_gpm, 3)
        if start_node:
            rec["start_node"] = start_node
        if end_node:
            rec["end_node"] = end_node
        water_segments.append(rec)
        if segment_missing:
            missing_inputs.append({"segment": name, "missing_fields": sorted(set(segment_missing))})
            continue
        graph_rows.append(
            {
                "name": name,
                "start_node": start_node,
                "end_node": end_node,
                "flow_gpm": flow_gpm,
                "diameter_in": diameter_in,
                "length_ft": length_ft,
                "elevation_gain_ft": safe_float(rec.get("elevation_gain_ft") or rec.get("elevation_gain"), 0.0),
            }
        )

    enriched["water_segments"] = water_segments
    if water_segments:
        hooks["utility_segments"] = [
            {**safe_dict(item), "system_type": safe_str(safe_dict(item).get("system_type") or "water")}
            for item in safe_list(hooks.get("utility_segments"))
        ] or water_segments
        enriched["conflict_hooks"] = hooks

    source = safe_dict(enriched.get("water_source") or enriched.get("source"))
    source_pressure = (
        _finite_or_none(enriched.get("source_pressure_psi"))
        or _finite_or_none(enriched.get("available_pressure_psi"))
        or _finite_or_none(source.get("pressure_psi"))
        or _finite_or_none(source.get("source_pressure_psi"))
    )
    source_node = safe_str(enriched.get("source_node") or source.get("node") or source.get("source_node"))
    if not source_node and graph_rows:
        source_node = safe_str(graph_rows[0].get("start_node"))
    min_required_pressure = max(0.0, safe_float(enriched.get("min_residual_pressure_psi"), 20.0))
    pressure_missing: List[str] = []
    if source_pressure is None:
        pressure_missing.append("source_pressure_psi")
    if not source_node:
        pressure_missing.append("source_node")
    if not graph_rows:
        pressure_missing.append("water_segments_with_flow_diameter_length_nodes")
    pressure_result: Dict[str, Any] = {}
    if source_pressure is not None and source_node and graph_rows:
        pressure_result = analyze_water_pressure_graph(
            graph_rows,
            source_node=source_node,
            source_pressure_psi=source_pressure,
            hazen_williams_c=safe_float(enriched.get("hazen_williams_c"), 130.0),
        )
    min_pressure = safe_float(pressure_result.get("min_pressure_psi"), 0.0)
    pressure_valid = bool(pressure_result.get("success")) and min_pressure >= min_required_pressure and not missing_inputs
    enriched["pressure_validation"] = {
        "valid": pressure_valid,
        "source_node": source_node,
        "source_pressure_psi": round(source_pressure, 3) if source_pressure is not None else None,
        "min_pressure_psi": round(min_pressure, 3) if pressure_result else None,
        "min_required_pressure_psi": round(min_required_pressure, 3),
        "pressure_graph": pressure_result,
        "missing_inputs": pressure_missing,
        "segment_missing_inputs": missing_inputs,
        "truth_label": "Hazen-Williams pressure evidence from supplied source pressure and water segment demands.",
    }
    if pressure_result.get("segments"):
        pressure_by_name = {safe_str(item.get("name")): safe_dict(item) for item in safe_list(pressure_result.get("segments"))}
        for rec in water_segments:
            solved = pressure_by_name.get(safe_str(rec.get("name")))
            if solved:
                rec["friction_loss_psi"] = solved.get("friction_loss_psi")
                rec["start_pressure_psi"] = solved.get("start_pressure_psi")
                rec["end_pressure_psi"] = solved.get("end_pressure_psi")
                rec["velocity_fps"] = solved.get("velocity_fps")
    enriched["velocity_checks"] = velocity_checks
    existing_zones = safe_list(enriched.get("pressure_zones"))
    if existing_zones:
        enriched["pressure_zones"] = existing_zones
    elif source_pressure is not None:
        enriched["pressure_zones"] = [
            {
                "name": safe_str(source.get("zone") or enriched.get("pressure_zone_name"), "Source Pressure Zone"),
                "source_node": source_node,
                "source_pressure_psi": round(source_pressure, 3),
                "truth_label": "Pressure zone derived from supplied source pressure.",
            }
        ]

    hydrants = safe_list(enriched.get("hydrants") or enriched.get("fire_hydrants"))
    enriched["hydrant_spacing_validation"] = _hydrant_spacing_validation(
        hydrants,
        default_limit_ft=safe_float(enriched.get("max_hydrant_spacing_ft"), 500.0),
    )
    fire_demand = max(
        0.0,
        safe_float(enriched.get("fire_flow_demand_gpm"), 0.0),
        safe_float(enriched.get("required_fire_flow_gpm"), 0.0),
    )
    available_fire = max(
        0.0,
        safe_float(enriched.get("available_fire_flow_gpm"), 0.0),
        safe_float(source.get("available_fire_flow_gpm"), 0.0),
    )
    fire_missing = []
    if fire_demand <= 0.0:
        fire_missing.append("fire_flow_demand_gpm")
    if available_fire <= 0.0:
        fire_missing.append("available_fire_flow_gpm")
    enriched["fire_flow_validation"] = {
        "valid": bool(fire_demand > 0.0 and available_fire >= fire_demand and (not pressure_result or min_pressure >= min_required_pressure)),
        "required_fire_flow_gpm": round(fire_demand, 3),
        "available_fire_flow_gpm": round(available_fire, 3),
        "residual_pressure_psi": round(min_pressure, 3) if pressure_result else None,
        "missing_inputs": fire_missing,
        "truth_label": "Fire-flow check uses supplied required/available flow and pressure evidence; verify with local fire authority.",
    }
    if available_fire > 0.0:
        enriched["available_fire_flow_gpm"] = round(available_fire, 3)
    graph_looped = _water_has_cycle(graph_rows)
    enriched["looped"] = bool(enriched.get("looped") or enriched.get("is_looped") or graph_looped)
    enriched["looping_validation"] = {
        "valid": bool(enriched["looped"]),
        "method": "graph_cycle_detection",
        "truth_label": "Looping validation is based on water graph connectivity.",
    }
    sizing_recommendations: List[Dict[str, Any]] = []
    for check in velocity_checks:
        if not bool(check.get("valid")):
            sizing_recommendations.append(
                {
                    "segment": safe_str(check.get("segment")),
                    "recommendation": "increase_diameter_or_reduce_flow",
                    "reason": "velocity_exceeds_limit",
                }
            )
    enriched["sizing_optimization"] = {
        "status": "needs_resize" if sizing_recommendations else "checked",
        "recommendations": sizing_recommendations,
        "truth_label": "Sizing optimization is evidence-only until a resized candidate is explicitly accepted.",
    }
    blockers = []
    if pressure_missing or missing_inputs:
        blockers.append("pressure_inputs_missing")
    if safe_dict(enriched["hydrant_spacing_validation"]).get("valid") is not True:
        blockers.append("hydrant_spacing_not_validated")
    if safe_dict(enriched["fire_flow_validation"]).get("valid") is not True:
        blockers.append("fire_flow_not_validated")
    if not enriched["looped"]:
        blockers.append("looping_not_validated")
    enriched["water_depth_status"] = "ready" if not blockers else "blocked_missing_inputs"
    enriched["water_depth_blockers"] = blockers
    return enriched


def build_grading_detail_controls(
    *,
    grade_elements: Sequence[Any],
    derived_action_stats: Dict[str, int],
    downhill_vector: Dict[str, Any],
    existing_high_points: Sequence[Dict[str, Any]],
    existing_low_points: Sequence[Dict[str, Any]],
    proposed_range_ft: float,
) -> Dict[str, Any]:
    road_crowns: List[Dict[str, Any]] = []
    gutters: List[Dict[str, Any]] = []
    ada_checks: List[Dict[str, Any]] = []
    pad_tie_ins: List[Dict[str, Any]] = []
    for index, elem in enumerate(grade_elements, start=1):
        kind = safe_str(getattr(elem, "kind", ""), "").lower()
        name = safe_str(getattr(elem, "name", ""), "") or f"{kind.upper()}-{index}"
        slope_x = safe_float(getattr(elem, "slope_x", 0.0), 0.0)
        slope_y = safe_float(getattr(elem, "slope_y", 0.0), 0.0)
        width = max(0.0, safe_float(getattr(elem, "width", 0.0), 0.0))
        depth = max(0.0, safe_float(getattr(elem, "depth", 0.0), 0.0))
        cross_slope = max(abs(slope_x), abs(slope_y), 0.0)
        if kind in {"road", "drive", "roadway"}:
            road_crowns.append(
                {
                    "road": name,
                    "cross_slope": round(max(cross_slope, 0.015), 5),
                    "longitudinal_slope": round(min(abs(slope_x) + abs(slope_y), 0.12), 5),
                    "control_source": "grade_element",
                    "truth_label": "concept road crown control; verify profile and cross-slope against road standard.",
                }
            )
            gutters.append(
                {
                    "road": name,
                    "gutter_slope": round(max(abs(slope_x), abs(slope_y), 0.005), 5),
                    "flow_direction": deepcopy(downhill_vector),
                    "control_source": "grade_element",
                }
            )
        if kind in {"walk", "sidewalk", "ada", "path"}:
            ada_checks.append(
                {
                    "path": name,
                    "running_slope": round(min(abs(slope_x) + abs(slope_y), 0.2), 5),
                    "cross_slope": round(cross_slope, 5),
                    "valid": cross_slope <= 0.02 and (abs(slope_x) + abs(slope_y)) <= 0.0833,
                    "control_source": "grade_element",
                }
            )
        if kind in {"pad", "building", "building_pad"}:
            pad_tie_ins.append(
                {
                    "building": name,
                    "pad_elev_ft": round(safe_float(getattr(elem, "base_elev", 0.0), 0.0), 3),
                    "positive_drainage": bool(abs(safe_float(downhill_vector.get("dx"), 0.0)) > 1e-9 or abs(safe_float(downhill_vector.get("dy"), 0.0)) > 1e-9),
                    "transition_zone_ft": round(max(0.0, safe_float(getattr(elem, "transition_zone", 0.0), 0.0)), 3),
                    "control_source": "grade_element",
                }
            )
        if kind in {"parking", "lot"}:
            gutters.append(
                {
                    "road": name,
                    "gutter_slope": round(max(cross_slope, 0.004), 5),
                    "surface": "parking",
                    "control_source": "grade_element",
                }
            )
    contour_count = max(safe_int(derived_action_stats.get("proposed_contour_count"), 0), safe_int(derived_action_stats.get("contour_count"), 0))
    contour_interval = 2.0 if proposed_range_ft >= 2.0 else max(0.5, round(max(proposed_range_ft, 0.5), 2))
    contours = [
        {
            "contour_index": index,
            "interval_ft": contour_interval,
            "source": "grading_surface_actions",
            "truth_label": "surface-derived contour metadata",
        }
        for index in range(1, max(contour_count, 1) + 1)
    ][:25]
    return {
        "road_crown_controls": road_crowns,
        "curb_gutter_controls": gutters,
        "ada_path_checks": ada_checks,
        "pad_tie_ins": pad_tie_ins,
        "contours": contours,
        "contour_interval_ft": contour_interval,
        "grading_detail_source": "grading_engine_controls",
        "existing_high_points": [deepcopy(safe_dict(point)) for point in existing_high_points],
        "existing_low_points": [deepcopy(safe_dict(point)) for point in existing_low_points],
    }


def build_cad_interop_metadata(plan: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan.get("meta"))
    has_pipe_network = bool(safe_dict(meta.get("storm_pipes") or meta.get("storm_pipe_summary")) or safe_dict(meta.get("sanitary") or meta.get("sanitary_summary")))
    return {
        "source": "dxf_exporter_metadata",
        "dxf": True,
        "dwg": False,
        "civil3d": False,
        "landxml": False,
        "surface_export": bool(safe_dict(meta.get("grading") or meta.get("grading_summary"))),
        "pipe_network_export": bool(safe_dict(meta.get("storm_pipes") or meta.get("storm_pipe_summary"))),
        "landxml_pipe_network_contract": has_pipe_network,
        "landxml_pipe_network_contract_status": "schema_ready_not_civil3d_verified" if has_pipe_network else "no_pipe_network_available",
        "sheet_registry_ready": bool(safe_list(meta.get("sheet_registry")) or safe_dict(meta.get("sheet_registry"))),
        "export_audit_ready": bool(safe_dict(meta.get("export_audit"))),
        "contract_status": "dxf_ready; landxml_pipe_network_contract_ready; civil3d_landxml_contract_not_implemented",
        "truth_label": "DXF export metadata and a LandXML pipe-network exchange contract are available; Civil 3D-verified writers still require implementation.",
    }


def build_optimization_alternatives(summary: Dict[str, Any]) -> Dict[str, Any]:
    enriched = deepcopy(safe_dict(summary))
    metrics = safe_dict(enriched.get("metrics"))
    component_scores = safe_dict(enriched.get("component_scores"))
    baseline = {
        "name": "Current canonical plan",
        "option_type": "baseline",
        "overall_score": safe_float(enriched.get("overall_score"), 0.0),
        "component_scores": deepcopy(component_scores),
        "geometry_committed": True,
    }
    grading_alt = {
        "name": "Earthwork-focused refinement",
        "option_type": "recommendation",
        "target_metric": "earthwork_net_cf",
        "estimated_benefit": "reduce absolute net earthwork",
        "geometry_committed": False,
        "requires_rerun": ["grading", "drainage", "storm_pipes", "qa"],
    }
    pipe_alt = {
        "name": "Pipe efficiency refinement",
        "option_type": "recommendation",
        "target_metric": "total_linear_utility_ft",
        "estimated_benefit": "shorten storm/utility trunk runs",
        "geometry_committed": False,
        "requires_rerun": ["drainage", "storm_pipes", "utilities", "qa"],
    }
    alternatives = [baseline]
    if abs(safe_float(metrics.get("earthwork_net_cf"), 0.0)) > 1.0:
        alternatives.append(grading_alt)
    if safe_float(metrics.get("total_linear_utility_ft"), 0.0) > 1.0:
        alternatives.append(pipe_alt)
    if len(alternatives) == 1:
        alternatives.append(grading_alt)
    enriched["alternatives"] = alternatives
    enriched["comparison_summary"] = {
        "recommended_option_name": baseline["name"],
        "comparison_mode": "baseline_plus_uncommitted_recommendations",
        "committed_option_count": sum(1 for item in alternatives if item.get("geometry_committed")),
        "uncommitted_recommendation_count": sum(1 for item in alternatives if not item.get("geometry_committed")),
        "truth_label": "Only the baseline geometry is canonical until an optimization alternative is explicitly solved and accepted.",
    }
    return enriched
