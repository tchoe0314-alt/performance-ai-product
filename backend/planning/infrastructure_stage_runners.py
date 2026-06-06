from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional

from core.config import (
    DEFAULT_LOT_HEIGHT,
    DEFAULT_LOT_WIDTH,
    DEFAULT_LOT_X,
    DEFAULT_LOT_Y,
    DEFAULT_PAD_ELEV,
    DEFAULT_SETBACK,
    TEXT_HEIGHT_SMALL,
)
from core.geometry_core import ZoneType
from core.project_manager import ConflictRecord, ConflictSeverity, DependencyState
from engines.sanitary_engine import SanitaryEngine, SanitaryFixture, SanitaryPipeSegment, SanitarySizingRequest
from engines.utility_engine import UtilityEngine, UtilityNodeSpec, UtilityRequest

from .common import dedupe_keep_order, lower_text, polyline_length, safe_dict, safe_float, safe_int, safe_list, safe_str
from .field_contract import field_path_is_omitted, unwrap_fields_for_execution
from .runtime import PlannerExecutionContext, _mark_dependency_state


def _insert_sanitary_spacing_points(path: List[List[float]], max_spacing_ft: float = 240.0) -> List[List[float]]:
    if len(path) < 2 or max_spacing_ft <= 0:
        return path
    out: List[List[float]] = [list(path[0])]
    distance_since_node = 0.0
    for start, end in zip(path, path[1:]):
        sx = safe_float(start[0], 0.0)
        sy = safe_float(start[1], 0.0)
        ex = safe_float(end[0], 0.0)
        ey = safe_float(end[1], 0.0)
        segment_length = max(((ex - sx) ** 2 + (ey - sy) ** 2) ** 0.5, 0.0)
        if segment_length <= 1e-9:
            continue
        traversed = 0.0
        while distance_since_node + (segment_length - traversed) > max_spacing_ft:
            remaining = max_spacing_ft - distance_since_node
            traversed += remaining
            ratio = min(max(traversed / segment_length, 0.0), 1.0)
            out.append([round(sx + (ex - sx) * ratio, 3), round(sy + (ey - sy) * ratio, 3)])
            distance_since_node = 0.0
        distance_since_node += segment_length - traversed
        out.append([round(ex, 3), round(ey, 3)])
    deduped: List[List[float]] = []
    for point in out:
        if not deduped or abs(point[0] - deduped[-1][0]) > 1e-6 or abs(point[1] - deduped[-1][1]) > 1e-6:
            deduped.append(point)
    return deduped


def _preview_meta_for_action(layer: str, task: str, *, role: Optional[str] = None, system: Optional[str] = None) -> Dict[str, Any]:
    raw_layer = safe_str(layer, "").upper()
    task_lower = safe_str(task, "").lower()
    overlay_layers = {"ANNO", "DRAIN_FLOW", "FG_CONTOUR", "EG_CONTOUR", "SURFACE"}
    helper_layers = {"DRAIN", "PIPE", "BASIN_BOUNDARY"}
    if role:
        resolved_role = role
    elif task_lower in {"text_note", "point", "north_arrow"}:
        resolved_role = "overlay"
    elif raw_layer in helper_layers or raw_layer in overlay_layers:
        resolved_role = "overlay"
    else:
        resolved_role = "final"

    if system:
        resolved_system = system
    elif raw_layer in {"ROAD", "FIRE"}:
        resolved_system = "roads"
    elif raw_layer == "PARKING":
        resolved_system = "parking"
    elif raw_layer in {"WALK", "SIDEWALK"}:
        resolved_system = "pedestrian"
    elif raw_layer in {"DRAIN", "PIPE", "BASIN_BOUNDARY", "DRAIN_FLOW"}:
        resolved_system = "drainage"
    elif raw_layer == "SAN":
        resolved_system = "sanitary"
    elif raw_layer in {"WATER", "WATR"}:
        resolved_system = "water"
    elif raw_layer in {"FG_CONTOUR", "EG_CONTOUR", "SURFACE"}:
        resolved_system = "grading"
    else:
        resolved_system = "layout"

    return {
        "is_final": resolved_role == "final",
        "preview_role": resolved_role,
        "system": resolved_system,
    }


def run_sanitary_stage(
    ctx: PlannerExecutionContext,
    *,
    strict_mode_enabled: Callable[[Dict[str, Any]], bool],
    sanitary_requested: Callable[[Dict[str, Any]], bool],
    sanitary_user_input_summary: Callable[[Dict[str, Any], Any], Optional[Dict[str, Any]]],
    record_strict_stage_failure: Callable[..., None],
    sanitary_building_nodes: Callable[[Any, str], List[Dict[str, Any]]],
    storm_pipe_paths: Callable[[Any], List[List[List[float]]]],
    orthogonal_path: Callable[..., List[List[float]]],
    sanitary_min_slope: Callable[[str, float], float],
    sample_grid_surface: Callable[..., float],
    route_conflicts: Callable[..., List[Dict[str, Any]]],
    preferred_route_between: Callable[..., List[List[float]]],
    repair_sanitary_segment_covers: Callable[[List[Dict[str, Any]], Any], List[Dict[str, Any]]],
    bind_sanitary_graph_nodes: Callable[[List[Dict[str, Any]], List[Dict[str, Any]]], Any],
    validate_network_graph: Callable[..., Any],
    validate_sanitary_network: Callable[..., Any],
) -> None:
    manager = ctx.manager
    project = manager.project
    parsed = ctx.parsed
    strict_mode = strict_mode_enabled(parsed)

    try:
        if not sanitary_requested(parsed):
            manager.mark_system_skipped("sanitary", "Sanitary stage skipped because sanitary was not requested.")
            ctx.add_stage(
                "sanitary",
                True,
                "Sanitary stage skipped because sanitary was not requested.",
                completeness="assumed",
                assumed=True,
            )
            return

        manager.mark_system_running("sanitary", "Running sanitary stage.")
        direct_summary = sanitary_user_input_summary(parsed, project)
        if direct_summary is not None:
            manager.latest_outputs["sanitary"] = deepcopy(direct_summary)
            project.meta["sanitary_summary"] = deepcopy(direct_summary)
            manager.set_metric("sanitary_total_length_ft", safe_float(direct_summary.get("total_length_ft"), 0.0), units="ft", category="sanitary")
            manager.set_metric("sanitary_main_length_ft", safe_float(direct_summary.get("main_length_ft"), 0.0), units="ft", category="sanitary")
            manager.set_metric("sanitary_lateral_length_ft", safe_float(direct_summary.get("lateral_length_ft"), 0.0), units="ft", category="sanitary")
            manager.set_metric("sanitary_service_connection_length_ft", safe_float(direct_summary.get("service_connection_length_ft"), 0.0), units="ft", category="sanitary")
            manager.set_metric("sanitary_manhole_count", safe_int(direct_summary.get("manhole_count"), 0), category="sanitary")
            manager.set_metric("sanitary_service_count", safe_int(direct_summary.get("service_count"), 0), category="sanitary")
            manager.set_metric("sanitary_route_count", safe_int(direct_summary.get("route_count"), 0), category="sanitary")
            manager.mark_system_complete("sanitary", "Sanitary stage completed from user input.")
            ctx.add_stage("sanitary", True, "Sanitary stage accepted user-supplied sanitary geometry.", route_count=safe_int(direct_summary.get("route_count"), 0))
            return

        street_edge = safe_str(parsed.get("street_edge"), "bottom") or "bottom"
        lot = safe_dict(unwrap_fields_for_execution(parsed.get("lot")))
        lot_x = safe_float(lot.get("x"), DEFAULT_LOT_X)
        lot_y = safe_float(lot.get("y"), DEFAULT_LOT_Y)
        lot_w = safe_float(lot.get("w"), DEFAULT_LOT_WIDTH)
        lot_h = safe_float(lot.get("h"), DEFAULT_LOT_HEIGHT)
        sanitary_nodes = sanitary_building_nodes(project, street_edge)
        if not sanitary_nodes:
            if strict_mode:
                record_strict_stage_failure(
                    ctx,
                    "sanitary",
                    "STRICT_SANITARY_OUTPUT_MISSING",
                    "STRICT mode requires sanitary service destinations before sanitary routing can be generated.",
                    category="sanitary",
                    dependency="layout",
                    computation_step="service_destination_collection",
                )
                return
            manager.mark_system_skipped("sanitary", "No sanitary service destinations were found.")
            ctx.add_stage(
                "sanitary",
                True,
                "Sanitary stage skipped because no sanitary service destinations were found.",
                completeness="assumed",
                assumed=True,
            )
            return

        storm_summary = safe_dict(manager.latest_outputs.get("storm_pipe_summary", project.meta.get("storm_pipe_summary", {})))
        preferred_outfall = safe_dict(safe_dict(manager.latest_outputs.get("drainage", project.meta.get("drainage_canonical", {}))).get("coordination", {})).get("preferred_outfall")
        corridor_preferences = safe_dict(project.meta.get("preferred_corridors"))
        sanitary_preference = safe_dict(corridor_preferences.get("sanitary"))
        offset = max(12.0, safe_float(parsed.get("setback"), DEFAULT_SETBACK) * 0.75)
        if isinstance(preferred_outfall, dict):
            offset += 6.0

        if lower_text(street_edge) == "bottom":
            corridor_y = safe_float(sanitary_preference.get("axis_value"), lot_y + offset) if safe_str(sanitary_preference.get("orientation")) == "horizontal" else lot_y + offset
            corridor_start = [lot_x + 8.0, corridor_y]
            tie_in = [lot_x + lot_w * 0.5, lot_y]
            prefer_x_first = False
        elif lower_text(street_edge) == "top":
            corridor_y = safe_float(sanitary_preference.get("axis_value"), lot_y + lot_h - offset) if safe_str(sanitary_preference.get("orientation")) == "horizontal" else lot_y + lot_h - offset
            corridor_start = [lot_x + 8.0, corridor_y]
            tie_in = [lot_x + lot_w * 0.5, lot_y + lot_h]
            prefer_x_first = False
        elif lower_text(street_edge) == "left":
            corridor_x = safe_float(sanitary_preference.get("axis_value"), lot_x + offset) if safe_str(sanitary_preference.get("orientation")) == "vertical" else lot_x + offset
            corridor_start = [corridor_x, lot_y + 8.0]
            tie_in = [lot_x, lot_y + lot_h * 0.5]
            prefer_x_first = True
        else:
            corridor_x = safe_float(sanitary_preference.get("axis_value"), lot_x + lot_w - offset) if safe_str(sanitary_preference.get("orientation")) == "vertical" else lot_x + lot_w - offset
            corridor_start = [corridor_x, lot_y + 8.0]
            tie_in = [lot_x + lot_w, lot_y + lot_h * 0.5]
            prefer_x_first = True

        if isinstance(preferred_outfall, dict):
            if lower_text(street_edge) in {"bottom", "top"}:
                tie_in[0] = min(max(lot_x + 8.0, safe_float(preferred_outfall.get("x"), tie_in[0]) + 18.0), lot_x + lot_w - 8.0)
            else:
                tie_in[1] = min(max(lot_y + 8.0, safe_float(preferred_outfall.get("y"), tie_in[1]) + 18.0), lot_y + lot_h - 8.0)

        proposed_surface = safe_dict(manager.latest_outputs.get("grading", project.meta.get("grading_summary", {}))).get("proposed_surface")

        fixtures: List[SanitaryFixture] = []
        sanitary_segments: List[Dict[str, Any]] = []
        sanitary_engine_segments: List[SanitaryPipeSegment] = []
        main_connection_points: List[List[float]] = []
        storm_paths = storm_pipe_paths(project)

        for index, node in enumerate(sanitary_nodes, start=1):
            zone_name = safe_str(node.get("zone_name"), f"BLDG-{index}")
            service_point = [safe_float(safe_list(node.get("service_point"))[0], 0.0), safe_float(safe_list(node.get("service_point"))[1], 0.0)]
            centroid = [safe_float(safe_list(node.get("centroid"))[0], service_point[0]), safe_float(safe_list(node.get("centroid"))[1], service_point[1])]
            if lower_text(street_edge) in {"bottom", "top"}:
                connection_point = [service_point[0], corridor_start[1]]
            else:
                connection_point = [corridor_start[0], service_point[1]]
            stub_path = orthogonal_path((centroid[0], centroid[1]), (service_point[0], service_point[1]), prefer_x_first=prefer_x_first)
            lateral_path = orthogonal_path((service_point[0], service_point[1]), (connection_point[0], connection_point[1]), prefer_x_first=prefer_x_first)
            main_connection_points.append(connection_point)

            for role, path in (("service_connection", stub_path), ("lateral", lateral_path)):
                if len(path) < 2:
                    continue
                path = _insert_sanitary_spacing_points(path)
                length_ft = polyline_length(path)
                diameter_in = 6.0 if role == "service_connection" else 8.0
                slope_ft_ft = sanitary_min_slope(role, diameter_in)
                surface_start = sample_grid_surface(proposed_surface, path[0][0], path[0][1], DEFAULT_PAD_ELEV)
                surface_end = sample_grid_surface(proposed_surface, path[-1][0], path[-1][1], DEFAULT_PAD_ELEV - 0.5)
                start_depth = 5.0 if role == "service_connection" else 6.5
                start_invert = surface_start - start_depth
                min_drop = slope_ft_ft * length_ft
                target_end_depth = 7.0 if role == "service_connection" else 8.0
                end_invert = min(surface_end - target_end_depth, start_invert - min_drop)
                actual_slope = (start_invert - end_invert) / max(length_ft, 1e-9)
                warnings: List[str] = []
                if actual_slope + 1e-6 < slope_ft_ft:
                    warnings.append("Sanitary segment slope is below minimum gravity slope.")
                conflict_rows = route_conflicts(path, storm_paths, threshold_ft=6.0)
                segment_name = f"SAN-{index}-{1 if role == 'service_connection' else 2}"
                rec = {
                    "name": segment_name,
                    "segment_role": role,
                    "system_type": "sanitary",
                    "start_name": f"{zone_name}_{role.upper()}_START",
                    "end_name": f"{zone_name}_{role.upper()}_END",
                    "route_points": path,
                    "length_ft": round(length_ft, 3),
                    "diameter_in": diameter_in,
                    "slope_ft_ft": round(actual_slope, 5),
                    "start_invert_ft": round(start_invert, 3),
                    "end_invert_ft": round(end_invert, 3),
                    "hydraulic_mode": "gravity",
                    "served_building": zone_name,
                    "storm_conflicts": conflict_rows,
                    "warnings": warnings,
                }
                sanitary_segments.append(rec)
                if role == "lateral":
                    fixture_name = f"{zone_name}_FIXTURE"
                    fixtures.append(SanitaryFixture(name=fixture_name, fixture_type="wc_public", drainage_fu=12.0, branch_length=length_ft, meta={"building": zone_name}))
                    sanitary_engine_segments.append(
                        SanitaryPipeSegment(
                            name=segment_name,
                            segment_type="lateral",
                            connected_fixture_names=[fixture_name],
                            length=length_ft,
                            slope=actual_slope,
                            min_slope=slope_ft_ft,
                            min_size_in=diameter_in,
                            geometry_points=[(pt[0], pt[1]) for pt in path],
                            meta={"served_building": zone_name},
                        )
                    )

        main_route: List[List[float]] = []
        if main_connection_points:
            sorted_points = sorted(main_connection_points, key=lambda pt: (pt[0], pt[1]))
            if lower_text(street_edge) in {"left", "right"}:
                sorted_points = sorted(main_connection_points, key=lambda pt: pt[1])
            first_connection = sorted_points[0]
            last_connection = sorted_points[-1]
            main_route = [tie_in]
            if lower_text(street_edge) in {"bottom", "top"}:
                main_route.append([tie_in[0], first_connection[1]])
                if abs(first_connection[0] - tie_in[0]) > 1e-6:
                    main_route.append([first_connection[0], first_connection[1]])
                if abs(last_connection[0] - first_connection[0]) > 1e-6:
                    main_route.append([last_connection[0], last_connection[1]])
            else:
                main_route.append([first_connection[0], tie_in[1]])
                if abs(first_connection[1] - tie_in[1]) > 1e-6:
                    main_route.append([first_connection[0], first_connection[1]])
                if abs(last_connection[1] - first_connection[1]) > 1e-6:
                    main_route.append([last_connection[0], last_connection[1]])
            deduped_route: List[List[float]] = []
            for point in main_route:
                if not deduped_route or abs(point[0] - deduped_route[-1][0]) > 1e-6 or abs(point[1] - deduped_route[-1][1]) > 1e-6:
                    deduped_route.append(point)
            main_route = preferred_route_between(deduped_route[0], deduped_route[-1], sanitary_preference) if sanitary_preference else deduped_route
            main_route = _insert_sanitary_spacing_points(main_route)

        if len(main_route) < 2:
            if strict_mode:
                record_strict_stage_failure(
                    ctx,
                    "sanitary",
                    "STRICT_SANITARY_ROUTE_MISSING",
                    "STRICT mode blocked sanitary completion because no downstream sanitary main could be formed.",
                    category="sanitary",
                    dependency="layout",
                    computation_step="main_route_generation",
                )
                return
            manager.mark_system_failed("sanitary", "Failed to build a sanitary main route.", ["No sanitary main route was generated."])
            ctx.add_stage("sanitary", False, "Sanitary stage failed because no sanitary main route was generated.")
            return

        main_length_ft = polyline_length(main_route)
        main_surface_start = sample_grid_surface(proposed_surface, main_route[0][0], main_route[0][1], DEFAULT_PAD_ELEV - 0.5)
        main_surface_end = sample_grid_surface(proposed_surface, main_route[-1][0], main_route[-1][1], DEFAULT_PAD_ELEV - 1.5)
        main_min_slope = sanitary_min_slope("main", 8.0)
        main_start_invert = main_surface_start - 7.0
        main_end_invert = min(main_surface_end - 9.0, main_start_invert - main_min_slope * main_length_ft)
        main_actual_slope = (main_start_invert - main_end_invert) / max(main_length_ft, 1e-9)
        main_warnings: List[str] = []
        if main_actual_slope + 1e-6 < main_min_slope:
            main_warnings.append("Sanitary main slope is below minimum gravity slope.")
        main_conflicts = route_conflicts(main_route, storm_paths, threshold_ft=8.0)
        sanitary_segments.append(
            {
                "name": "SAN-MAIN-1",
                "segment_role": "main",
                "system_type": "sanitary",
                "start_name": "SAN_MAIN_START",
                "end_name": "SAN_TIE_IN",
                "route_points": main_route,
                "length_ft": round(main_length_ft, 3),
                "diameter_in": 8.0,
                "slope_ft_ft": round(main_actual_slope, 5),
                "start_invert_ft": round(main_start_invert, 3),
                "end_invert_ft": round(main_end_invert, 3),
                "hydraulic_mode": "gravity",
                "served_building": "shared_main",
                "storm_conflicts": main_conflicts,
                "warnings": main_warnings,
            }
        )
        sanitary_engine_segments.append(
            SanitaryPipeSegment(
                name="SAN-MAIN-1",
                segment_type="main",
                connected_fixture_names=[fixture.name for fixture in fixtures],
                length=main_length_ft,
                slope=main_actual_slope,
                min_slope=main_min_slope,
                min_size_in=8.0,
                geometry_points=[(pt[0], pt[1]) for pt in main_route],
                meta={"served_building_count": len(sanitary_nodes)},
            )
        )

        sizing_result = SanitaryEngine().size(
            SanitarySizingRequest(
                fixtures=fixtures,
                segments=sanitary_engine_segments,
                conservative=True,
                auto_assign_slopes=False,
                auto_assign_inverts=True,
                grease_interceptor_required=False,
                default_main_slope=main_min_slope,
                default_lateral_slope=0.02,
                default_site_connection_slope=0.01,
            )
        )
        size_map = {safe_str(seg.name): seg for seg in getattr(sizing_result, "segments", [])}
        for rec in sanitary_segments:
            seg = size_map.get(safe_str(rec.get("name")))
            if seg is None:
                continue
            rec["diameter_in"] = round(max(safe_float(rec.get("diameter_in"), 0.0), safe_float(getattr(seg, "assigned_size_in", rec.get("diameter_in")), rec.get("diameter_in"))), 3)
            rec["start_invert_ft"] = round(safe_float(getattr(seg, "upstream_invert_ft", rec.get("start_invert_ft")), rec.get("start_invert_ft")), 3)
            rec["end_invert_ft"] = round(safe_float(getattr(seg, "downstream_invert_ft", rec.get("end_invert_ft")), rec.get("end_invert_ft")), 3)
            rec["slope_ft_ft"] = round(max(safe_float(rec.get("slope_ft_ft"), 0.0), safe_float(getattr(seg, "slope", rec.get("slope_ft_ft")), rec.get("slope_ft_ft"))), 5)
            rec["warnings"] = dedupe_keep_order(list(rec.get("warnings") or []) + list(getattr(seg, "warnings", []) or []))

        manholes: List[Dict[str, Any]] = []
        missing_manhole_points: List[Dict[str, Any]] = []
        storm_conflicts: List[Dict[str, Any]] = []
        slope_violations: List[Dict[str, Any]] = []
        disconnected_segments: List[str] = []
        junction_lookup = {(round(pt[0], 3), round(pt[1], 3)) for pt in main_connection_points}
        for seg_index, segment in enumerate(sanitary_segments, start=1):
            route_points = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(segment.get("route_points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
            if len(route_points) < 2:
                disconnected_segments.append(safe_str(segment.get("name"), f"SAN-{seg_index}"))
                continue
            diameter = safe_float(segment.get("diameter_in"), 8.0)
            min_slope = sanitary_min_slope(safe_str(segment.get("segment_role"), "main"), diameter)
            if safe_float(segment.get("slope_ft_ft"), 0.0) + 1e-6 < min_slope:
                slope_violations.append({"segment": safe_str(segment.get("name")), "required_min_slope": round(min_slope, 5), "actual_slope": safe_float(segment.get("slope_ft_ft"), 0.0)})
            for conflict in safe_list(segment.get("storm_conflicts")):
                if isinstance(conflict, dict):
                    storm_conflicts.append({"segment": safe_str(segment.get("name")), **deepcopy(conflict)})
            points_for_manholes = [route_points[0], route_points[-1]]
            for idx in range(1, len(route_points) - 1):
                prev_pt = route_points[idx - 1]
                pt = route_points[idx]
                next_pt = route_points[idx + 1]
                if abs((pt[0] - prev_pt[0]) * (next_pt[1] - pt[1]) - (pt[1] - prev_pt[1]) * (next_pt[0] - pt[0])) > 1e-6:
                    points_for_manholes.append(pt)
            for point in points_for_manholes:
                key = (round(point[0], 3), round(point[1], 3))
                if any(round(mh.get("x", 0.0), 3) == key[0] and round(mh.get("y", 0.0), 3) == key[1] for mh in manholes):
                    continue
                if safe_str(segment.get("segment_role")) != "main" and key not in junction_lookup and point not in [route_points[0], route_points[-1]]:
                    missing_manhole_points.append({"segment": safe_str(segment.get("name")), "reason": "bend_requires_manhole", "point": [point[0], point[1]]})
                    continue
                rim = sample_grid_surface(proposed_surface, point[0], point[1], DEFAULT_PAD_ELEV)
                manholes.append({"name": f"SMH-{len(manholes)+1}", "x": point[0], "y": point[1], "rim_elev_ft": round(rim, 3)})

        missing_service_buildings = [
            safe_str(node.get("zone_name"))
            for node in sanitary_nodes
            if not any(safe_str(segment.get("served_building")) == safe_str(node.get("zone_name")) for segment in sanitary_segments if safe_str(segment.get("segment_role")) in {"service_connection", "lateral"})
        ]

        cover_repairs = repair_sanitary_segment_covers(sanitary_segments, proposed_surface)
        sanitary_segments, manholes, nodes = bind_sanitary_graph_nodes(sanitary_segments, manholes)

        summary = {
            "success": not bool(missing_service_buildings or slope_violations or disconnected_segments),
            "message": "Sanitary stage completed.",
            "source": "generated",
            "fallback_used": False,
            "route_count": len(sanitary_segments),
            "service_count": len(sanitary_nodes),
            "served_building_count": len(sanitary_nodes) - len(missing_service_buildings),
            "total_length_ft": round(sum(safe_float(seg.get("length_ft"), 0.0) for seg in sanitary_segments), 3),
            "main_length_ft": round(sum(safe_float(seg.get("length_ft"), 0.0) for seg in sanitary_segments if safe_str(seg.get("segment_role")) == "main"), 3),
            "lateral_length_ft": round(sum(safe_float(seg.get("length_ft"), 0.0) for seg in sanitary_segments if safe_str(seg.get("segment_role")) == "lateral"), 3),
            "service_connection_length_ft": round(sum(safe_float(seg.get("length_ft"), 0.0) for seg in sanitary_segments if safe_str(seg.get("segment_role")) == "service_connection"), 3),
            "manhole_count": len(manholes),
            "segments": sanitary_segments,
            "manholes": manholes,
            "nodes": nodes,
            "missing_service_buildings": missing_service_buildings,
            "slope_violations": slope_violations,
            "disconnected_segments": disconnected_segments,
            "storm_conflicts": storm_conflicts,
            "missing_manhole_points": missing_manhole_points,
            "cover_repairs": cover_repairs,
            "warnings": dedupe_keep_order(list(getattr(sizing_result, "warnings", []) or [])),
            "coordination": {
                "street_edge": street_edge,
                "tie_in_point": [round(tie_in[0], 3), round(tie_in[1], 3)],
                "main_corridor_start": [round(main_route[0][0], 3), round(main_route[0][1], 3)] if main_route else None,
                "main_corridor_end": [round(main_route[-1][0], 3), round(main_route[-1][1], 3)] if main_route else None,
                "storm_pipe_count": safe_int(storm_summary.get("pipe_count"), 0),
                "preferred_corridor": deepcopy(sanitary_preference),
            },
            "stats": {
                "segment_count": len(sanitary_segments),
                "route_count": len(sanitary_segments),
                "service_count": len(sanitary_nodes),
                "total_length_ft": round(sum(safe_float(seg.get("length_ft"), 0.0) for seg in sanitary_segments), 3),
                "main_length_ft": round(sum(safe_float(seg.get("length_ft"), 0.0) for seg in sanitary_segments if safe_str(seg.get("segment_role")) == "main"), 3),
                "lateral_length_ft": round(sum(safe_float(seg.get("length_ft"), 0.0) for seg in sanitary_segments if safe_str(seg.get("segment_role")) == "lateral"), 3),
                "service_connection_length_ft": round(sum(safe_float(seg.get("length_ft"), 0.0) for seg in sanitary_segments if safe_str(seg.get("segment_role")) == "service_connection"), 3),
                "manhole_count": len(manholes),
                "storm_conflict_count": len(storm_conflicts),
            },
            "sizing": {
                "success": bool(getattr(sizing_result, "success", False)),
                "summary": deepcopy(getattr(getattr(sizing_result, "summary", None), "to_dict", lambda: {})()),
            },
        }
        expected_service_buildings = dedupe_keep_order(
            [
                safe_str(node.get("building_id") or node.get("zone_name") or node.get("name"))
                for node in sanitary_nodes
                if safe_str(node.get("building_id") or node.get("zone_name") or node.get("name"))
            ]
        )
        served_buildings = dedupe_keep_order(
            [
                safe_str(seg.get("served_building"))
                for seg in sanitary_segments
                if safe_str(seg.get("segment_role")) in {"service_connection", "lateral"}
                and safe_str(seg.get("served_building"))
                and safe_str(seg.get("served_building")) != "shared_main"
            ]
        )
        summary["service_coverage"] = {
            "expected_buildings": expected_service_buildings,
            "served_buildings": served_buildings,
            "missing_buildings": deepcopy(missing_service_buildings),
            "expected_count": len(expected_service_buildings),
            "served_count": len(served_buildings),
            "valid": not missing_service_buildings,
            "truth_label": "Sanitary service coverage is generated from canonical sanitary service nodes before validation.",
        }
        node_inflow: Dict[str, float] = {}
        for seg in sanitary_segments:
            flow = round(max(0.0, safe_float(seg.get("flow_cfs"), 0.0)), 6)
            seg["post_reroute_recalculated"] = True
            seg["upstream_service_flow_cfs"] = flow
            end_node = safe_str(seg.get("end_name") or seg.get("to"))
            if end_node and flow > 0.0:
                node_inflow[end_node] = round(node_inflow.get(end_node, 0.0) + flow, 6)
        summary["post_reroute_recalculation"] = {
            "service_flow_total_cfs": round(sum(max(0.0, safe_float(seg.get("flow_cfs"), 0.0)) for seg in sanitary_segments if safe_str(seg.get("segment_role")) in {"service_connection", "lateral"}), 6),
            "main_segments_recomputed": len([seg for seg in sanitary_segments if safe_str(seg.get("segment_role")) == "main"]),
            "service_segments_recomputed": len([seg for seg in sanitary_segments if safe_str(seg.get("segment_role")) in {"service_connection", "lateral"}]),
            "node_inflow_cfs": node_inflow,
            "disconnected_service_count": len(disconnected_segments),
            "all_segments_recalculated": True,
            "truth_label": "Sanitary stage emits deterministic post-reroute recalculation evidence before validation.",
        }
        summary["graph_validation"] = validate_network_graph(summary, "sanitary")
        summary["network_validation"] = validate_sanitary_network(summary)
        summary["success"] = bool(summary["graph_validation"].get("valid")) and bool(summary["network_validation"].get("valid"))
        manager.latest_outputs["sanitary"] = deepcopy(summary)
        project.meta["sanitary_summary"] = deepcopy(summary)
        manager.set_metric("sanitary_total_length_ft", safe_float(summary.get("total_length_ft"), 0.0), units="ft", category="sanitary")
        manager.set_metric("sanitary_main_length_ft", safe_float(summary.get("main_length_ft"), 0.0), units="ft", category="sanitary")
        manager.set_metric("sanitary_lateral_length_ft", safe_float(summary.get("lateral_length_ft"), 0.0), units="ft", category="sanitary")
        manager.set_metric("sanitary_service_connection_length_ft", safe_float(summary.get("service_connection_length_ft"), 0.0), units="ft", category="sanitary")
        manager.set_metric("sanitary_manhole_count", len(manholes), category="sanitary")
        manager.set_metric("sanitary_service_count", len(sanitary_nodes), category="sanitary")
        manager.set_metric("sanitary_route_count", len(sanitary_segments), category="sanitary")
        manager.upsert_system(
            "sanitary_network",
            "sanitary",
            zone_ids=[safe_str(node.get("zone_id")) for node in sanitary_nodes],
            related_system_ids=[system.id for system in manager.systems_by_type("storm_pipes")] if hasattr(manager, "systems_by_type") else [],
            message="Canonical sanitary routing generated.",
        )
        _mark_dependency_state(manager, "storm_pipes", "sanitary", DependencyState.FRESH, reason="Sanitary coordinated against storm pipes.")
        _mark_dependency_state(manager, "grading", "sanitary", DependencyState.FRESH, reason="Sanitary coordinated against grading.")
        _mark_dependency_state(manager, "sanitary", "utility_network", DependencyState.STALE, reason="Utility coordination should respect sanitary routing.")
        if bool(summary.get("success", False)):
            manager.mark_system_complete("sanitary", "Sanitary stage completed.", summary.get("warnings"))
            manager.invalidate_from("sanitary")
        else:
            manager.mark_system_failed(
                "sanitary",
                "Sanitary stage failed canonical validation.",
                [safe_str(item.get("segment_id")) for item in safe_list(safe_dict(summary.get("network_validation")).get("invalid_cover_segments"))]
                + [safe_str(item) for item in safe_list(safe_dict(summary.get("graph_validation")).get("orphan_nodes"))],
            )
        ctx.add_stage(
            "sanitary",
            bool(summary.get("success", False)),
            "Sanitary stage completed." if bool(summary.get("success", False)) else "Sanitary stage failed canonical validation.",
            completeness="complete" if bool(summary.get("success", False)) else "failed",
            route_count=len(sanitary_segments),
            service_count=len(sanitary_nodes),
            main_length_ft=safe_float(summary.get("main_length_ft"), 0.0),
            lateral_length_ft=safe_float(summary.get("lateral_length_ft"), 0.0),
            manhole_count=len(manholes),
            storm_conflict_count=len(storm_conflicts),
            missing_service_count=len(missing_service_buildings),
            graph_valid=bool(safe_dict(summary.get("graph_validation")).get("valid")),
            network_valid=bool(safe_dict(summary.get("network_validation")).get("valid")),
            invalid_cover_segment_count=len(safe_list(safe_dict(summary.get("network_validation")).get("invalid_cover_segments"))),
            fallback_used=False,
        )
    except Exception as exc:
        message = f"Sanitary stage failed: {exc}"
        if strict_mode:
            record_strict_stage_failure(
                ctx,
                "sanitary",
                "STRICT_SANITARY_STAGE_FAILED",
                message,
                category="sanitary",
                dependency="sanitary_engine",
                computation_step="stage_execution",
            )
            return
        manager.mark_system_failed("sanitary", message, [safe_str(exc)])
        manager.add_conflict(ConflictRecord(code="SANITARY_STAGE_FAILED", message=message, severity=ConflictSeverity.WARNING, category="sanitary"))
        ctx.record_warning(message)
        ctx.add_stage("sanitary", False, message)


def run_utility_stage(
    ctx: PlannerExecutionContext,
    *,
    strict_mode_enabled: Callable[[Dict[str, Any]], bool],
    install_rect_obstacle_compatibility: Callable[[], None],
    user_supplied_geometry_available: Callable[[Dict[str, Any], str], bool],
    actions_from_linear_features: Callable[[List[Dict[str, Any]], str, float], List[Dict[str, Any]]],
    merge_actions_into_expanded_plan: Callable[..., None],
    enrich_utility_summary_with_coordination: Callable[[Dict[str, Any], Any, Any], Dict[str, Any]],
    utility_export_validation: Callable[..., Dict[str, Any]],
    record_strict_stage_failure: Callable[..., None],
    preferred_route_between: Callable[..., List[List[float]]],
    utility_engine_cls: Callable[..., Any] = UtilityEngine,
) -> None:
    manager = ctx.manager
    project = manager.project
    parsed = ctx.parsed
    strict_mode = strict_mode_enabled(parsed)

    try:
        if field_path_is_omitted(parsed, "utility_network"):
            manager.mark_system_skipped("utility_network", "Utilities omitted by user intent.")
            ctx.record_assumption("Utilities omitted by user intent; planner preserved omission and skipped utility stage.")
            ctx.add_stage(
                "utility_network",
                True,
                "Utility stage skipped because source=omit.",
                completeness="assumed",
                assumed=True,
            )
            return

        install_rect_obstacle_compatibility()

        lot = safe_dict(unwrap_fields_for_execution(parsed.get("lot")))
        if not lot:
            ctx.add_stage(
                "utility_network",
                True,
                "Utility stage skipped because lot was unavailable.",
                completeness="assumed",
                assumed=True,
            )
            return

        execution_payload = unwrap_fields_for_execution(parsed)
        if user_supplied_geometry_available(parsed, "utility_network"):
            user_utility_actions = actions_from_linear_features(safe_list(execution_payload.get("utility_network")), "UTILITY", text_height=0.8)
            merge_actions_into_expanded_plan(project, user_utility_actions, utility_direct_input=True)
            total_length = sum(polyline_length(safe_list(f.get("points"))) for f in safe_list(execution_payload.get("utility_network")) if isinstance(f, dict))
            route_count = len([f for f in safe_list(execution_payload.get("utility_network")) if isinstance(f, dict)])
            manager.set_metric("utility_route_count", route_count, category="utilities")
            manager.set_metric("utility_total_length_ft", total_length, units="ft", category="utilities")
            utility_summary = {
                "success": True,
                "message": "Utility stage accepted user-supplied geometry.",
                "route_count": route_count,
                "total_length_ft": round(total_length, 3),
                "warning_count": 0,
                "fallback_used": False,
                "source": "user_input",
            }
            manager.latest_outputs["utilities"] = deepcopy(utility_summary)
            project.meta["utility_summary"] = deepcopy(utility_summary)
            ctx.record_assumption("Utility stage used user-supplied utility geometry directly and skipped fallback routing.")
            ctx.add_stage("utility_network", True, "Utility stage accepted user-supplied geometry.", route_count=route_count, total_length_ft=total_length)
            return

        source = UtilityNodeSpec(
            x=safe_float(lot.get("x"), 0.0),
            y=safe_float(lot.get("y"), 0.0) + safe_float(lot.get("h"), DEFAULT_LOT_HEIGHT) / 2.0,
            z=DEFAULT_PAD_ELEV,
            name="UTILITY_SOURCE",
            kind="source",
        )

        destinations = []
        for zone in project.zones.values():
            zone_name = safe_str(getattr(zone, "name", ""))
            zone_type = getattr(zone, "zone_type", None)
            if zone_type not in {ZoneType.BUILDING, ZoneType.BUILDING_PAD, ZoneType.PAD}:
                continue
            if zone_type == ZoneType.PAD and zone_name.upper() in {"BUILDABLE_AREA", "SITE", "LOT"}:
                continue
            if zone_type == ZoneType.PAD and "BUILDABLE" in zone_name.upper():
                continue
            if zone_type == ZoneType.PAD and not zone_name:
                continue
            c = zone.boundary.centroid()
            destinations.append(
                UtilityNodeSpec(
                    x=c.x,
                    y=c.y,
                    z=DEFAULT_PAD_ELEV,
                    name=f"{zone_name or 'BLDG'}_SERVICE",
                    kind="service",
                )
            )

        if not destinations:
            ctx.add_stage(
                "utility_network",
                True,
                "Utility stage skipped because no service destinations were found.",
                completeness="assumed",
                assumed=True,
            )
            return

        route_count = 0
        total_length = 0.0
        warnings: List[str] = []
        success = True
        message = "Utility stage completed."
        utility_summary: Dict[str, Any] = {}
        corridor_preferences = safe_dict(project.meta.get("preferred_corridors"))
        utility_preference = safe_dict(corridor_preferences.get("water") or corridor_preferences.get("generic"))

        try:
            engine = utility_engine_cls(level=safe_str(parsed.get("level"), "") or None)
            request = UtilityRequest(
                system_type="generic_utility",
                source=source,
                destinations=destinations,
                layer_name="UTILITY",
                graph_name="Generic Utility",
                review_after_generation=False,
            )
            result = engine.generate(project, request)
            route_count = safe_int(getattr(result, "route_count", 0), 0)
            total_length = safe_float(getattr(result, "total_length", 0.0), 0.0)
            success = bool(getattr(result, "success", True))
            message = safe_str(getattr(result, "message", message))
            warnings.extend([safe_str(w) for w in safe_list(getattr(result, "warnings", [])) if safe_str(w)])
            utility_summary = {
                "success": success,
                "message": message,
                "route_count": route_count,
                "total_length_ft": round(total_length, 3),
                "warning_count": len(warnings),
                "fallback_used": False,
                "segments": deepcopy(safe_list(safe_dict(getattr(result, "explain", {})).get("segments"))),
                "explain": deepcopy(getattr(result, "explain", {})),
                "conflict_hooks": deepcopy(getattr(result, "conflict_hooks", {})),
                "preferred_corridor": deepcopy(utility_preference),
            }
            utility_summary = enrich_utility_summary_with_coordination(utility_summary, project, manager)
            conflict_hooks = safe_dict(utility_summary.get("conflict_hooks"))
            utility_segments = safe_list(conflict_hooks.get("utility_segments"))
            if (not success) or route_count <= 0 or not utility_segments:
                raise RuntimeError(
                    safe_str(message, "Utility engine produced no usable utility network.")
                    or "Utility engine produced no usable utility network."
                )
        except Exception as inner_exc:
            if strict_mode:
                manager.set_metric("utility_route_count", 0, category="utilities")
                manager.set_metric("utility_total_length_ft", 0.0, units="ft", category="utilities")
                record_strict_stage_failure(
                    ctx,
                    "utility_network",
                    "STRICT_UTILITY_FALLBACK_BLOCKED",
                    f"STRICT mode blocked utility fallback because the utility engine failed: {inner_exc}",
                    category="utilities",
                    dependency="utility_engine",
                    computation_step="network_routing",
                )
                return
            fallback_actions: List[Dict[str, Any]] = []
            fallback_segments: List[Dict[str, Any]] = []
            for idx, dest in enumerate(destinations, start=1):
                pts = preferred_route_between([source.x, source.y], [dest.x, dest.y], utility_preference)
                total_length += polyline_length(pts)
                route_count += 1
                fallback_actions.append(
                    {
                        "task": "polyline",
                        "origin": None,
                        "points": pts,
                        "closed": False,
                        "width": None,
                        "height": None,
                        "label": f"UTILITY-{idx}",
                        "layer": "UTILITY",
                        "text": None,
                        "text_height": None,
                        "center": None,
                        "radius": None,
                        "start_angle": None,
                        "end_angle": None,
                        "meta": _preview_meta_for_action("UTILITY", "polyline", role="overlay", system="utilities"),
                    }
                )
                fallback_actions.append(
                    {
                        "task": "text_note",
                        "origin": [dest.x, dest.y],
                        "points": None,
                        "closed": None,
                        "width": None,
                        "height": None,
                        "label": None,
                        "layer": "UTILITY",
                        "text": f"UTILITY-{idx}",
                        "text_height": TEXT_HEIGHT_SMALL,
                        "center": None,
                        "radius": None,
                        "start_angle": None,
                        "end_angle": None,
                        "meta": _preview_meta_for_action("UTILITY", "text_note", role="overlay", system="utilities"),
                    }
                )
                fallback_segments.append(
                    {
                        "name": f"UTILITY-{idx}",
                        "system_type": "water",
                        "route_points": deepcopy(pts),
                        "diameter_in": 8.0,
                        "start_invert_ft": DEFAULT_PAD_ELEV - 4.0,
                        "end_invert_ft": DEFAULT_PAD_ELEV - 4.2,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                        "hydraulic_mode": "pressurized",
                    }
                )
            merge_actions_into_expanded_plan(project, fallback_actions, utility_fallback=True)
            warnings.append(f"Utility engine fallback used: {inner_exc}")
            success = True
            message = "Utility stage completed using fallback routing."
            utility_summary = {
                "success": True,
                "message": message,
                "route_count": route_count,
                "total_length_ft": round(total_length, 3),
                "warning_count": len(warnings),
                "fallback_used": True,
                "segments": [],
                "fallback_error": safe_str(inner_exc),
                "conflict_hooks": {"utility_system_type": "water", "utility_segments": fallback_segments},
                "preferred_corridor": deepcopy(utility_preference),
            }
            utility_summary = enrich_utility_summary_with_coordination(utility_summary, project, manager)

        manager.set_metric("utility_route_count", route_count, category="utilities")
        manager.set_metric("utility_total_length_ft", total_length, units="ft", category="utilities")
        utility_summary["export_validation"] = utility_export_validation(project, utilities_override=utility_summary)
        manager.latest_outputs["utilities"] = deepcopy(utility_summary)
        project.meta["utility_summary"] = deepcopy(utility_summary)

        _mark_dependency_state(manager, "storm_pipes", "utility_network", DependencyState.FRESH, reason="Utility network coordinated after storm pipe stage.")
        _mark_dependency_state(manager, "utility_network", "earthwork", DependencyState.STALE, reason="Earthwork may depend on utility network.")
        manager.invalidate_from("utility_network")

        fallback_used = bool(utility_summary.get("fallback_used")) or any("fallback" in lower_text(warning) for warning in warnings)
        ctx.add_stage(
            "utility_network",
            success,
            message,
            route_count=route_count,
            total_length_ft=total_length,
            fallback_used=fallback_used,
            dependency="utility_engine" if fallback_used else None,
            computation_step="network_routing" if fallback_used else None,
        )
        for warning in warnings:
            ctx.record_warning(warning)
    except Exception as exc:
        message = f"Utility stage failed: {exc}"
        if strict_mode:
            record_strict_stage_failure(
                ctx,
                "utility_network",
                "STRICT_UTILITY_STAGE_FAILED",
                message,
                category="utilities",
                dependency="utility_engine",
                computation_step="stage_execution",
            )
        else:
            ctx.record_warning(message)
            manager.add_conflict(ConflictRecord(code="UTILITY_STAGE_FAILED", message=str(exc), severity=ConflictSeverity.WARNING, category="utilities"))
            ctx.add_stage("utility_network", False, message)
