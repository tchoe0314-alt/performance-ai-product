from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence, Tuple

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
    hgl_profile: List[Dict[str, Any]] = []
    egl_profile: List[Dict[str, Any]] = []
    station = 0.0
    max_ratio = 0.0
    controlling = safe_str(enriched.get("controlling_segment"))
    total_flow = 0.0
    total_capacity = 0.0
    total_area_sf = 0.0
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
    return {
        "source": "dxf_exporter_metadata",
        "dxf": True,
        "dwg": False,
        "civil3d": False,
        "landxml": False,
        "surface_export": bool(safe_dict(meta.get("grading") or meta.get("grading_summary"))),
        "pipe_network_export": bool(safe_dict(meta.get("storm_pipes") or meta.get("storm_pipe_summary"))),
        "sheet_registry_ready": bool(safe_list(meta.get("sheet_registry")) or safe_dict(meta.get("sheet_registry"))),
        "export_audit_ready": bool(safe_dict(meta.get("export_audit"))),
        "contract_status": "dxf_ready; civil3d_landxml_contract_not_implemented",
        "truth_label": "DXF export metadata is available; Civil 3D/LandXML writers still require implementation.",
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
