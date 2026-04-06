from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.config import DEFAULT_PAD_ELEV, PIPE_INTENSITY_IN_HR, PIPE_RUNOFF_C
from engines.storm.storm_types import (
    StormBasin,
    StormCatchment,
    StormInlet,
    StormNodeType,
    StormPoint,
)

from backend.planning.common import (
    polyline_length,
    safe_dict,
    safe_float,
    safe_int,
    safe_list,
    safe_str,
)
from backend.planning.export_validation import detention_basin_score


def storm_inlets_from_drainage(
    drainage_meta: Dict[str, Any],
) -> List[StormInlet]:
    surface_guidance = safe_dict(drainage_meta.get("surface_guidance"))
    preferred_targets = [
        safe_dict(item)
        for item in safe_list(surface_guidance.get("preferred_targets"))
        if safe_dict(item)
    ]

    def infer_surface_target(x: float, y: float) -> Tuple[Optional[str], int]:
        best_name: Optional[str] = None
        best_rank = len(preferred_targets) + 1
        best_distance = float("inf")
        for rank, target in enumerate(preferred_targets, start=1):
            tx = target.get("x")
            ty = target.get("y")
            if tx is None or ty is None:
                continue
            distance_ft = math.hypot(float(tx) - x, float(ty) - y)
            if distance_ft < best_distance:
                best_distance = distance_ft
                best_rank = rank
                best_name = safe_str(target.get("target_name"), "") or None
        return best_name, best_rank

    inlets: List[StormInlet] = []
    for rec in safe_list(drainage_meta.get("structures")):
        item = safe_dict(rec)
        if safe_str(item.get("object_type")) != "inlet":
            continue
        name = safe_str(item.get("name"), f"INLET-{len(inlets)+1}")
        x = safe_float(item.get("x"), 0.0)
        y = safe_float(item.get("y"), 0.0)
        z = safe_float(item.get("z"), DEFAULT_PAD_ELEV)
        target_name = safe_str(item.get("target_name"), "") or None
        inferred_surface_target, target_rank = infer_surface_target(x, y)
        if not target_name:
            target_name = inferred_surface_target
        rank_bonus = max(0.0, float(max(len(preferred_targets) - target_rank + 1, 0)))
        inlets.append(
            StormInlet(
                name=name,
                node_type=StormNodeType.INLET.value,
                point=StormPoint(x=x, y=y, z=z, label=name),
                rim_elev_ft=z,
                inlet_type="curb"
                if safe_str(item.get("structure_type")) == "curb_inlet"
                else "area",
                local_low_point_score=max(
                    0.0, safe_float(item.get("contributing_cells"), 0.0)
                )
                + rank_bonus,
                placement_reason="surface_low_point_capture",
                contributing_area_sf=max(
                    0.0, safe_float(item.get("contributing_area_sf"), 0.0)
                ),
                contributing_runoff_cfs=max(
                    0.0, safe_float(item.get("estimated_flow_cfs"), 0.0)
                ),
                meta={
                    "target_name": target_name,
                    "surface_target_name": inferred_surface_target,
                    "surface_target_rank": target_rank
                    if inferred_surface_target
                    else None,
                    "canonical_type": safe_str(item.get("canonical_type"), "inlet"),
                },
            )
        )
    return inlets


def storm_basins_from_drainage(
    drainage_meta: Dict[str, Any],
    *,
    primary_engineered_basins: Callable[[Dict[str, Any]], List[Dict[str, Any]]],
) -> List[StormBasin]:
    primary_basins = [
        safe_dict(item)
        for item in primary_engineered_basins(drainage_meta)
        if safe_dict(item)
    ]
    if not primary_basins:
        return []

    preferred_outfall = safe_dict(
        safe_dict(drainage_meta.get("coordination")).get("preferred_outfall")
    )
    preferred_target = safe_str(preferred_outfall.get("target_name"))

    primary_basins.sort(
        key=lambda item: (
            0
            if preferred_target and safe_str(item.get("target_name")) == preferred_target
            else 1,
            -safe_float(
                safe_dict(item.get("detention_design")).get("provided_storage_cf"), 0.0
            ),
            -safe_float(item.get("area_sf"), 0.0),
            safe_str(item.get("name")),
        )
    )

    basins: List[StormBasin] = []
    for rec in primary_basins:
        item = safe_dict(rec)
        name = safe_str(item.get("name"), f"BASIN-{len(basins)+1}")
        detention = safe_dict(item.get("detention_design"))
        basins.append(
            StormBasin(
                name=name,
                basin_type="detention",
                bottom_area_sf=max(0.0, safe_float(item.get("bottom_area_sf"), 0.0)),
                top_area_sf=max(
                    0.0,
                    safe_float(
                        item.get("top_of_bank_area_sf"),
                        safe_float(item.get("area_sf"), 0.0),
                    ),
                ),
                depth_ft=max(0.0, safe_float(detention.get("depth_ft"), 0.0)),
                side_slope_h_to_1v=max(
                    1.0, safe_float(detention.get("side_slope_h_to_1v"), 4.0)
                ),
                bottom_elev_ft=(
                    safe_float(item.get("bottom_elev_ft"), 0.0)
                    if item.get("bottom_elev_ft") is not None
                    else None
                ),
                overflow_elev_ft=(
                    safe_float(item.get("top_of_bank_elev_ft"), 0.0)
                    if item.get("top_of_bank_elev_ft") is not None
                    else None
                ),
                release_cfs=max(0.0, safe_float(detention.get("release_cfs"), 0.0)),
                required_storage_cf=max(
                    0.0, safe_float(detention.get("required_storage_cf"), 0.0)
                ),
                provided_storage_cf=max(
                    0.0, safe_float(detention.get("provided_storage_cf"), 0.0)
                ),
                drawdown_hours=(
                    safe_float(detention.get("drawdown_hours"), 0.0)
                    if detention.get("drawdown_hours") is not None
                    else None
                ),
                boundary_points=[
                    (safe_float(pt[0], 0.0), safe_float(pt[1], 0.0))
                    for pt in safe_list(item.get("boundary_points") or item.get("boundary"))
                    if isinstance(pt, (list, tuple)) and len(pt) >= 2
                ],
                connection_node_name=safe_str(
                    safe_dict(item.get("outlet_structure")).get("name"), ""
                )
                or None,
                meta={
                    "engineering_role": safe_str(item.get("engineering_role"), ""),
                    "target_name": safe_str(item.get("target_name"), "") or None,
                    "storage_ratio": (
                        round(
                            max(
                                0.0,
                                safe_float(detention.get("provided_storage_cf"), 0.0),
                            )
                            / max(
                                1.0,
                                safe_float(detention.get("required_storage_cf"), 1.0),
                            ),
                            4,
                        )
                        if safe_float(detention.get("required_storage_cf"), 0.0) > 0.0
                        else None
                    ),
                    "detention_design": deepcopy(detention),
                    "geometry_quality": deepcopy(safe_dict(item.get("geometry_quality"))),
                    "overflow_spillway": deepcopy(
                        safe_dict(item.get("overflow_spillway"))
                    ),
                    "outlet_structure": deepcopy(
                        safe_dict(item.get("outlet_structure"))
                    ),
                },
            )
        )
    return basins


def storm_catchments_from_drainage(
    drainage_meta: Dict[str, Any],
    *,
    runoff_c: float,
    intensity_in_hr: float,
) -> List[StormCatchment]:
    surface_guidance = safe_dict(drainage_meta.get("surface_guidance"))
    preferred_targets = [
        safe_dict(item)
        for item in safe_list(surface_guidance.get("preferred_targets"))
        if safe_dict(item)
    ]

    def infer_surface_target(x: float, y: float) -> Optional[str]:
        best_name: Optional[str] = None
        best_distance = float("inf")
        for target in preferred_targets:
            tx = target.get("x")
            ty = target.get("y")
            if tx is None or ty is None:
                continue
            distance_ft = math.hypot(float(tx) - x, float(ty) - y)
            if distance_ft < best_distance:
                best_distance = distance_ft
                best_name = safe_str(target.get("target_name"), "") or None
        return best_name

    catchments: List[StormCatchment] = []
    for rec in safe_list(drainage_meta.get("structures")):
        item = safe_dict(rec)
        if safe_str(item.get("object_type")) != "inlet":
            continue
        area_sf = max(0.0, safe_float(item.get("contributing_area_sf"), 0.0))
        if area_sf <= 0.0:
            continue
        name = safe_str(item.get("name"), f"CATCH-{len(catchments)+1}")
        x = safe_float(item.get("x"), 0.0)
        y = safe_float(item.get("y"), 0.0)
        preferred_target_name = safe_str(item.get("target_name"), "") or infer_surface_target(x, y)
        tributary_basin_name = safe_str(item.get("tributary_basin_name"), "") or None
        peak_runoff = max(
            0.0,
            safe_float(item.get("estimated_flow_cfs"), 0.0),
            1.008 * runoff_c * intensity_in_hr * (area_sf / 43560.0),
        )
        catchments.append(
            StormCatchment(
                name=f"{name}-CATCH",
                area_sf=area_sf,
                runoff_c=runoff_c,
                tc_minutes=10.0,
                intensity_in_hr=intensity_in_hr,
                peak_runoff_cfs=round(peak_runoff, 3),
                centroid=StormPoint(
                    x=x,
                    y=y,
                    z=safe_float(item.get("z"), DEFAULT_PAD_ELEV),
                    label=name,
                ),
                meta={
                    "source_inlet": name,
                    "target_name": preferred_target_name,
                    "preferred_target_name": preferred_target_name,
                    "tributary_basin_name": tributary_basin_name,
                },
            )
        )
    return catchments


def storm_summary_from_network_result(
    network_result: Any,
    hydraulic_result: Any,
    *,
    validate_network_graph: Callable[[Dict[str, Any], str], Dict[str, Any]],
    validate_storm_hydraulics: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> Dict[str, Any]:
    network = getattr(network_result, "network", None)
    pipes = safe_list(getattr(hydraulic_result, "pipes", []))
    hydraulic_summary = safe_dict(getattr(hydraulic_result, "summary", {}))
    explain = safe_dict(getattr(network_result, "explain", {}))
    node_lookup = {
        safe_str(getattr(node, "name", ""), ""): node
        for node in safe_list(getattr(network, "nodes", []))
        if safe_str(getattr(node, "name", ""), "")
    }
    segments: List[Dict[str, Any]] = []
    missing_data_segments: List[str] = []
    total_length = 0.0
    total_capacity = 0.0
    total_flow = 0.0
    max_ratio = 0.0
    controlling_segment: Optional[str] = None
    downstream_inflow: Dict[str, float] = {}

    for pipe in pipes:
        downstream_inflow[pipe.downstream_node_name] = (
            downstream_inflow.get(pipe.downstream_node_name, 0.0)
            + safe_float(pipe.assigned_runoff_cfs, 0.0)
        )

    for pipe in pipes:
        route_points = [
            [safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)]
            for pt in safe_list(getattr(pipe, "route_points", []))
            if isinstance(pt, (list, tuple)) and len(pt) >= 2
        ]
        length_ft = safe_float(getattr(pipe, "length_ft", 0.0), polyline_length(route_points))
        design_flow = safe_float(
            getattr(getattr(pipe, "hydraulic", None), "design_flow_cfs", 0.0), 0.0
        )
        full_capacity = safe_float(
            getattr(getattr(pipe, "hydraulic", None), "full_capacity_cfs", 0.0), 0.0
        )
        ratio = safe_float(
            getattr(getattr(pipe, "hydraulic", None), "flow_depth_ratio", 0.0), 0.0
        )
        if design_flow > 0.0 and full_capacity > 0.0:
            ratio = max(ratio, design_flow / max(full_capacity, 1e-9))
        total_length += length_ft
        total_capacity += full_capacity
        total_flow += design_flow
        if ratio >= max_ratio:
            max_ratio = ratio
            controlling_segment = safe_str(
                getattr(pipe, "name", ""), controlling_segment or ""
            )
        if (
            design_flow <= 0.0
            or full_capacity <= 0.0
            or safe_float(getattr(pipe, "slope", 0.0), 0.0) <= 0.0
            or length_ft <= 0.0
        ):
            missing_data_segments.append(safe_str(getattr(pipe, "name", ""), "PIPE"))

        upstream_node = node_lookup.get(
            safe_str(getattr(pipe, "upstream_node_name", ""), "")
        )
        local_flow_cfs = max(
            0.0, safe_float(getattr(upstream_node, "contributing_runoff_cfs", 0.0), 0.0)
        )
        contributing_area_ac = max(
            0.0,
            safe_float(getattr(upstream_node, "contributing_area_sf", 0.0), 0.0)
            / 43560.0,
        )
        if contributing_area_ac <= 0.0 and design_flow > 0.0:
            contributing_area_ac = max(
                design_flow / max(1.008 * PIPE_RUNOFF_C * PIPE_INTENSITY_IN_HR, 1e-9),
                0.0001,
            )
        segments.append(
            {
                "pipe": safe_str(getattr(pipe, "name", ""), "PIPE"),
                "id": safe_str(getattr(pipe, "name", ""), "PIPE"),
                "from": safe_str(getattr(pipe, "upstream_node_name", ""), ""),
                "to": safe_str(getattr(pipe, "downstream_node_name", ""), ""),
                "start_name": safe_str(getattr(pipe, "upstream_node_name", ""), ""),
                "end_name": safe_str(getattr(pipe, "downstream_node_name", ""), ""),
                "node_ids": [
                    safe_str(getattr(pipe, "upstream_node_name", ""), ""),
                    safe_str(getattr(pipe, "downstream_node_name", ""), ""),
                ],
                "segment_role": safe_str(getattr(pipe, "pipe_type", "main"), "main"),
                "length_ft": round(length_ft, 3),
                "path": route_points,
                "route_points": route_points,
                "diameter_in": round(
                    safe_float(getattr(pipe, "diameter_in", 0.0), 0.0), 3
                ),
                "flow_cfs": round(design_flow, 3),
                "local_flow_cfs": round(local_flow_cfs, 3),
                "upstream_flow_cfs": round(max(0.0, design_flow - local_flow_cfs), 3),
                "capacity_cfs": round(full_capacity, 3),
                "capacity_ratio": round(ratio, 4),
                "velocity_fps": round(
                    safe_float(
                        getattr(getattr(pipe, "hydraulic", None), "velocity_fps", 0.0),
                        0.0,
                    ),
                    3,
                ),
                "slope_ft_ft": round(safe_float(getattr(pipe, "slope", 0.0), 0.0), 5),
                "slope_pct": round(
                    safe_float(getattr(pipe, "slope", 0.0), 0.0) * 100.0, 3
                ),
                "start_invert": round(
                    safe_float(getattr(pipe, "upstream_invert_ft", 0.0), 0.0), 3
                ),
                "end_invert": round(
                    safe_float(getattr(pipe, "downstream_invert_ft", 0.0), 0.0), 3
                ),
                "start_invert_ft": round(
                    safe_float(getattr(pipe, "upstream_invert_ft", 0.0), 0.0), 3
                ),
                "end_invert_ft": round(
                    safe_float(getattr(pipe, "downstream_invert_ft", 0.0), 0.0), 3
                ),
                "cover_start_ft": round(
                    safe_float(getattr(pipe, "cover_ft", 0.0), 0.0), 3
                ),
                "cover_end_ft": round(
                    safe_float(getattr(pipe, "cover_ft", 0.0), 0.0), 3
                ),
                "contributing_area_ac": round(contributing_area_ac, 4),
                "tributary_area_ac": round(contributing_area_ac, 4),
                "tributary_area_sf": round(
                    safe_float(
                        safe_dict(getattr(pipe, "meta", {})).get("tributary_area_sf"),
                        0.0,
                    ),
                    3,
                ),
                "tributary_runoff_cfs": round(
                    safe_float(
                        safe_dict(getattr(pipe, "meta", {})).get(
                            "tributary_runoff_cfs"
                        ),
                        design_flow,
                    ),
                    3,
                ),
                "tributary_catchment_count": int(
                    safe_float(
                        safe_dict(getattr(pipe, "meta", {})).get(
                            "tributary_catchment_count"
                        ),
                        0.0,
                    )
                ),
                "tributary_basin_names": list(
                    safe_list(
                        safe_dict(getattr(pipe, "meta", {})).get(
                            "tributary_basin_names"
                        )
                    )
                ),
                "upstream_cumulative_area_sf": round(
                    safe_float(
                        safe_dict(getattr(pipe, "meta", {})).get(
                            "upstream_cumulative_area_sf"
                        ),
                        0.0,
                    ),
                    3,
                ),
                "upstream_cumulative_runoff_cfs": round(
                    safe_float(
                        safe_dict(getattr(pipe, "meta", {})).get(
                            "upstream_cumulative_runoff_cfs"
                        ),
                        design_flow,
                    ),
                    3,
                ),
                "upstream_cumulative_catchment_count": int(
                    safe_float(
                        safe_dict(getattr(pipe, "meta", {})).get(
                            "upstream_cumulative_catchment_count"
                        ),
                        0.0,
                    )
                ),
                "upstream_cumulative_basin_names": list(
                    safe_list(
                        safe_dict(getattr(pipe, "meta", {})).get(
                            "upstream_cumulative_basin_names"
                        )
                    )
                ),
                "governing_flow_cfs": round(
                    safe_float(
                        safe_dict(getattr(pipe, "meta", {})).get("governing_flow_cfs"),
                        design_flow,
                    ),
                    3,
                ),
                "governing_area_sf": round(
                    safe_float(
                        safe_dict(getattr(pipe, "meta", {})).get("governing_area_sf"),
                        0.0,
                    ),
                    3,
                ),
                "governing_catchment_count": int(
                    safe_float(
                        safe_dict(getattr(pipe, "meta", {})).get(
                            "governing_catchment_count"
                        ),
                        0.0,
                    )
                ),
                "status": safe_str(
                    getattr(getattr(pipe, "hydraulic", None), "capacity_status", ""), ""
                ),
                "hgl_start": round(
                    safe_float(
                        getattr(getattr(pipe, "hydraulic", None), "hgl_upstream_ft", 0.0),
                        0.0,
                    ),
                    3,
                ),
                "hgl_end": round(
                    safe_float(
                        getattr(getattr(pipe, "hydraulic", None), "hgl_downstream_ft", 0.0),
                        0.0,
                    ),
                    3,
                ),
                "egl_start": round(
                    safe_float(
                        getattr(getattr(pipe, "hydraulic", None), "egl_upstream_ft", 0.0),
                        0.0,
                    ),
                    3,
                ),
                "egl_end": round(
                    safe_float(
                        getattr(getattr(pipe, "hydraulic", None), "egl_downstream_ft", 0.0),
                        0.0,
                    ),
                    3,
                ),
                "warnings": list(getattr(pipe, "warnings", []) or []),
            }
        )

    nodes: List[Dict[str, Any]] = []
    for node in safe_list(getattr(network, "nodes", [])):
        name = safe_str(getattr(node, "name", ""), "")
        nodes.append(
            {
                "id": name,
                "name": name,
                "node_type": safe_str(getattr(node, "node_type", ""), ""),
                "x": round(
                    safe_float(getattr(getattr(node, "point", None), "x", 0.0), 0.0), 3
                ),
                "y": round(
                    safe_float(getattr(getattr(node, "point", None), "y", 0.0), 0.0), 3
                ),
                "rim_elev_ft": round(
                    safe_float(getattr(node, "rim_elev_ft", 0.0), 0.0), 3
                ),
                "invert_elev_ft": round(
                    safe_float(getattr(node, "invert_elev_ft", 0.0), 0.0), 3
                ),
                "contributing_area_sf": round(
                    safe_float(getattr(node, "contributing_area_sf", 0.0), 0.0), 3
                ),
                "contributing_runoff_cfs": round(
                    safe_float(getattr(node, "contributing_runoff_cfs", 0.0), 0.0), 3
                ),
                "incoming_flow_cfs": round(downstream_inflow.get(name, 0.0), 3),
                "tributary_basin_names": list(
                    safe_list(
                        safe_dict(getattr(node, "meta", {})).get("tributary_basin_names")
                    )
                ),
                "tributary_catchment_count": int(
                    safe_float(
                        safe_dict(getattr(node, "meta", {})).get(
                            "tributary_catchment_count"
                        ),
                        0.0,
                    )
                ),
                "upstream_cumulative_area_sf": round(
                    safe_float(
                        safe_dict(getattr(node, "meta", {})).get(
                            "upstream_cumulative_area_sf"
                        ),
                        0.0,
                    ),
                    3,
                ),
                "upstream_cumulative_runoff_cfs": round(
                    safe_float(
                        safe_dict(getattr(node, "meta", {})).get(
                            "upstream_cumulative_runoff_cfs"
                        ),
                        0.0,
                    ),
                    3,
                ),
                "upstream_cumulative_catchment_count": int(
                    safe_float(
                        safe_dict(getattr(node, "meta", {})).get(
                            "upstream_cumulative_catchment_count"
                        ),
                        0.0,
                    )
                ),
                "upstream_cumulative_basin_names": list(
                    safe_list(
                        safe_dict(getattr(node, "meta", {})).get(
                            "upstream_cumulative_basin_names"
                        )
                    )
                ),
                "max_hgl_ft": round(
                    safe_float(getattr(node, "max_hgl_ft", 0.0), 0.0), 3
                ),
                "surcharge_risk": bool(getattr(node, "surcharge_risk", False)),
                "warnings": list(getattr(node, "warnings", []) or []),
            }
        )

    selected_outfall_name = safe_str(explain.get("selected_outfall_name"), "")
    basin_candidates = list(safe_list(getattr(network, "basins", [])))
    selected_basin: Optional[Any] = None
    for basin in basin_candidates:
        basin_name = safe_str(getattr(basin, "name", ""), "")
        connection_node_name = safe_str(
            getattr(basin, "connection_node_name", ""), f"{basin_name}_CONN"
        )
        if connection_node_name == selected_outfall_name:
            selected_basin = basin
            break
    if selected_basin is None and selected_outfall_name:
        for basin in basin_candidates:
            if safe_str(getattr(basin, "name", ""), "") == selected_outfall_name:
                selected_basin = basin
                break
    if selected_basin is None and basin_candidates:
        selected_basin = max(
            basin_candidates,
            key=lambda basin: detention_basin_score(
                safe_dict(getattr(basin, "meta", {}))
            ),
        )
    selected_basin_meta = (
        safe_dict(getattr(selected_basin, "meta", {}))
        if selected_basin is not None
        else {}
    )
    selected_detention = safe_dict(selected_basin_meta.get("detention_design"))
    selected_overflow = safe_dict(selected_basin_meta.get("overflow_spillway"))

    summary = {
        "success": bool(getattr(network_result, "success", False)),
        "pipe_count": len(segments),
        "total_length_ft": round(total_length, 3),
        "total_system_flow_cfs": round(total_flow, 3),
        "total_system_capacity_cfs": round(total_capacity, 3),
        "controlling_segment": controlling_segment,
        "max_capacity_ratio": round(max_ratio, 3),
        "missing_data_segments": sorted(set(missing_data_segments)),
        "pipe_slope_invert_consistency": all(
            safe_float(seg.get("start_invert_ft"), 0.0)
            > safe_float(seg.get("end_invert_ft"), 0.0)
            and safe_float(seg.get("slope_ft_ft"), 0.0) > 0.0
            and safe_float(seg.get("length_ft"), 0.0) > 0.0
            for seg in segments
        ),
        "segments": segments,
        "nodes": nodes,
        "warnings": sorted(
            set(
                list(getattr(network_result, "warnings", []) or [])
                + list(getattr(hydraulic_result, "warnings", []) or [])
            )
        ),
        "errors": [],
        "explain": explain,
        "hydraulic_summary": hydraulic_summary,
        "stats": {
            "trunk_count": sum(
                1
                for seg in segments
                if safe_str(seg.get("segment_role"), "main") in {"main", "trunk"}
            ),
            "lateral_count": sum(
                1
                for seg in segments
                if safe_str(seg.get("segment_role"), "") == "lateral"
            ),
            "selected_outfall_name": selected_outfall_name,
            "selected_basin_name": safe_str(getattr(selected_basin, "name", ""), ""),
            "selected_basin_adequacy_status": safe_str(
                selected_detention.get("adequacy_status"), ""
            ),
            "selected_basin_release_basis": safe_str(
                selected_detention.get("release_basis"), ""
            ),
            "selected_basin_target_drawdown_hours": round(
                safe_float(
                    selected_detention.get("target_drawdown_hours"),
                    safe_float(selected_detention.get("drawdown_hours"), 0.0),
                ),
                3,
            ),
            "selected_basin_spillway_capacity_cfs": round(
                safe_float(selected_overflow.get("assumed_capacity_cfs"), 0.0), 3
            ),
            "max_governing_flow_cfs": round(
                max(
                    (
                        safe_float(seg.get("governing_flow_cfs"), 0.0)
                        for seg in segments
                    ),
                    default=0.0,
                ),
                3,
            ),
            "max_governing_area_sf": round(
                max(
                    (
                        safe_float(seg.get("governing_area_sf"), 0.0)
                        for seg in segments
                    ),
                    default=0.0,
                ),
                3,
            ),
            "deficient_count": sum(
                1 for seg in segments if safe_str(seg.get("status"), "") == "deficient"
            ),
            "marginal_count": sum(
                1 for seg in segments if safe_str(seg.get("status"), "") == "marginal"
            ),
        },
    }
    summary["graph_validation"] = validate_network_graph(summary, "storm")
    summary["hydraulic_validation"] = validate_storm_hydraulics(summary)
    return summary
