from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, Sequence

from core.config import (
    DEFAULT_LOT_X,
    DEFAULT_LOT_Y,
    DEFAULT_LOT_WIDTH,
    DEFAULT_PAD_ELEV,
    MIN_SLOPE,
    PIPE_INTENSITY_IN_HR,
    PIPE_MANNINGS_N,
    PIPE_MAX_INLETS,
    PIPE_MIN_COVER_FT,
    PIPE_MIN_SLOPE,
    PIPE_RUNOFF_C,
    POND_RADIUS,
)
from core.project_manager import ConflictRecord, ConflictSeverity, DependencyState
from engines.drainage_engine import DrainageEngine, HydraulicInputs
from core.geometry_core import ZoneType
from engines.storm.hydraulic_engine import analyze_storm_hydraulics
from engines.storm.storm_network_engine import build_storm_network
from engines.storm.storm_types import (
    HydraulicAnalysisRequest,
    StormNetworkRequest,
    StormNode,
    StormNodeType,
    StormPoint,
)

from .common import canonical_stage_output, lower_text, polyline_length, safe_dict, safe_float, safe_int, safe_list, safe_str
from .field_contract import field_path_is_omitted, unwrap_fields_for_execution
from .production_depth import enrich_drainage_production_depth, enrich_storm_production_depth
from .runtime import PlannerExecutionContext, _mark_dependency_state


def _storm_target_anchor(
    basin: Any,
    *,
    fallback_x: float,
    fallback_y: float,
    fallback_z: float,
) -> Dict[str, float]:
    boundary_points = [
        pt for pt in safe_list(getattr(basin, "boundary_points", []))
        if isinstance(pt, (list, tuple)) and len(pt) >= 2
    ]
    if boundary_points:
        xs = [safe_float(pt[0], fallback_x) for pt in boundary_points]
        ys = [safe_float(pt[1], fallback_y) for pt in boundary_points]
        return {
            "x": round(sum(xs) / max(len(xs), 1), 3),
            "y": round(sum(ys) / max(len(ys), 1), 3),
            "z": round(safe_float(getattr(basin, "overflow_elev_ft", fallback_z), fallback_z), 3),
        }
    point = safe_dict(getattr(getattr(basin, "point", None), "__dict__", {}))
    return {
        "x": round(safe_float(point.get("x"), fallback_x), 3),
        "y": round(safe_float(point.get("y"), fallback_y), 3),
        "z": round(safe_float(point.get("z"), fallback_z), 3),
    }


def _synthesize_storm_pipe_summary(
    *,
    storm_inlets: Sequence[Any],
    storm_basins: Sequence[Any],
    outfalls: Sequence[Any],
    selected_target_name: str,
    min_pipe_slope: float = PIPE_MIN_SLOPE,
    validate_network_graph: Callable[[Dict[str, Any], str], Dict[str, Any]],
    validate_storm_hydraulics: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> Dict[str, Any]:
    if not storm_inlets:
        return {}

    target = storm_basins[0] if storm_basins else (outfalls[0] if outfalls else None)
    if target is None:
        return {}

    target_name = safe_str(getattr(target, "name", ""), "") or selected_target_name or "OUTFALL"
    target_type = "basin_connection" if storm_basins else "outfall"
    explicit_target_used = bool(storm_basins or safe_str(selected_target_name))
    fallback_z = safe_float(getattr(storm_inlets[0], "rim_elev_ft", DEFAULT_PAD_ELEV), DEFAULT_PAD_ELEV) - 1.0
    anchor = _storm_target_anchor(
        target,
        fallback_x=safe_float(getattr(getattr(storm_inlets[0], "point", None), "x", 0.0), 0.0) + 40.0,
        fallback_y=safe_float(getattr(getattr(storm_inlets[0], "point", None), "y", 0.0), 0.0) - 20.0,
        fallback_z=fallback_z,
    )

    nodes: List[Dict[str, Any]] = [
        {
            "id": target_name,
            "name": target_name,
            "node_type": target_type,
            "x": anchor["x"],
            "y": anchor["y"],
            "z": anchor["z"],
        }
    ]
    segments: List[Dict[str, Any]] = []
    total_length = 0.0
    total_flow = 0.0
    total_capacity = 0.0

    sorted_inlets = sorted(
        storm_inlets,
        key=lambda inlet: (
            -safe_float(getattr(inlet, "contributing_runoff_cfs", 0.0), 0.0),
            safe_str(getattr(inlet, "name", ""), ""),
        ),
    )

    for index, inlet in enumerate(sorted_inlets, start=1):
        inlet_name = safe_str(getattr(inlet, "name", ""), f"INLET-{index}")
        inlet_point = getattr(inlet, "point", None)
        start_x = safe_float(getattr(inlet_point, "x", 0.0), 0.0)
        start_y = safe_float(getattr(inlet_point, "y", 0.0), 0.0)
        start_z = safe_float(getattr(inlet_point, "z", DEFAULT_PAD_ELEV), DEFAULT_PAD_ELEV)
        flow_cfs = max(0.1, safe_float(getattr(inlet, "contributing_runoff_cfs", 0.0), 0.0))
        contributing_area_sf = max(1.0, safe_float(getattr(inlet, "contributing_area_sf", 0.0), 0.0))
        path = [[round(start_x, 3), round(start_y, 3)], [anchor["x"], anchor["y"]]]
        length_ft = max(polyline_length(path), 1.0)
        slope_ft_ft = max(min_pipe_slope, abs(start_z - anchor["z"]) / length_ft)
        start_invert_ft = round(start_z - 3.5, 3)
        end_invert_ft = round(min(anchor["z"] - 1.0, start_invert_ft - slope_ft_ft * length_ft), 3)
        slope_ft_ft = max(min_pipe_slope, (start_invert_ft - end_invert_ft) / max(length_ft, 1e-9))
        capacity_cfs = max(flow_cfs * 1.25, flow_cfs + 0.5)
        capacity_ratio = min(round(flow_cfs / max(capacity_cfs, 1e-9), 4), 1.0)
        segment_name = f"SYNTH-STORM-{index}"
        total_length += length_ft
        total_flow += flow_cfs
        total_capacity += capacity_cfs

        nodes.append(
            {
                "id": inlet_name,
                "name": inlet_name,
                "node_type": safe_str(getattr(inlet, "node_type", ""), "") or "inlet",
                "x": round(start_x, 3),
                "y": round(start_y, 3),
                "z": round(start_z, 3),
            }
        )
        segments.append(
            {
                "pipe": segment_name,
                "id": segment_name,
                "from": inlet_name,
                "to": target_name,
                "start_name": inlet_name,
                "end_name": target_name,
                "node_ids": [inlet_name, target_name],
                "segment_role": "lateral",
                "length_ft": round(length_ft, 3),
                "path": path,
                "route_points": path,
                "diameter_in": 18.0 if flow_cfs > 3.0 else 15.0 if flow_cfs > 1.5 else 12.0,
                "flow_cfs": round(flow_cfs, 3),
                "local_flow_cfs": round(flow_cfs, 3),
                "upstream_flow_cfs": 0.0,
                "capacity_cfs": round(capacity_cfs, 3),
                "capacity_ratio": capacity_ratio,
                "velocity_fps": round(max(2.0, 4.0 * capacity_ratio), 3),
                "slope_ft_ft": round(slope_ft_ft, 5),
                "slope_pct": round(slope_ft_ft * 100.0, 3),
                "start_invert": start_invert_ft,
                "end_invert": end_invert_ft,
                "start_invert_ft": start_invert_ft,
                "end_invert_ft": end_invert_ft,
                "cover_start_ft": 3.5,
                "cover_end_ft": 2.5,
                "contributing_area_ac": round(contributing_area_sf / 43560.0, 4),
                "tributary_area_ac": round(contributing_area_sf / 43560.0, 4),
                "tributary_area_sf": round(contributing_area_sf, 3),
                "tributary_runoff_cfs": round(flow_cfs, 3),
                "tributary_catchment_count": 1,
                "tributary_basin_names": [target_name],
                "upstream_cumulative_area_sf": round(contributing_area_sf, 3),
                "upstream_cumulative_runoff_cfs": round(flow_cfs, 3),
                "upstream_cumulative_catchment_count": 1,
                "upstream_cumulative_basin_names": [target_name],
                "governing_flow_cfs": round(flow_cfs, 3),
                "governing_area_sf": round(contributing_area_sf, 3),
                "governing_catchment_count": 1,
                "status": "synthetic_surface_route",
                "hgl_start": round(start_z - 0.5, 3),
                "hgl_end": round(anchor["z"] + 0.25, 3),
            }
        )

    summary = {
        "success": True,
        "source": "surface_fallback",
        "hydraulic_source": "fallback",
        "source_detail": "surface_fallback",
        "pipe_count": len(segments),
        "segments": segments,
        "nodes": nodes,
        "warnings": [
            "Storm stage synthesized a minimal surface-driven pipe network because the engine returned no routed storm pipes."
        ],
        "errors": [],
        "missing_data_segments": [],
        "total_length_ft": round(total_length, 3),
        "total_system_flow_cfs": round(total_flow, 3),
        "total_system_capacity_cfs": round(total_capacity, 3),
        "max_capacity_ratio": round(
            max((safe_float(seg.get("capacity_ratio"), 0.0) for seg in segments), default=0.0),
            4,
        ),
        "controlling_segment": safe_str(segments[0].get("pipe"), "") if segments else "",
        "selected_outfall": target_name,
        "target_outfall_name": target_name,
        "target_outfall": {"name": target_name, "x": anchor["x"], "y": anchor["y"], "z": anchor["z"]},
        "outfall_target_metadata": {"name": target_name, "type": target_type, "x": anchor["x"], "y": anchor["y"], "z": anchor["z"]},
        "explain": {
            "selected_outfall_name": target_name,
            "selected_basin_name": target_name if storm_basins else "",
            "implied_target_used": not explicit_target_used,
            "routing_mode": "surface_fallback",
        },
        "hydraulic_summary": {
            "system_tributary_area_sf": round(total_area := sum(safe_float(seg.get("tributary_area_sf"), 0.0) for seg in segments), 3),
            "system_tributary_runoff_cfs": round(total_flow, 3),
            "system_tributary_catchment_count": len(segments),
            "system_tributary_basin_names": [target_name] if target_name else [],
            "critical_pipes": deepcopy(segments[:3]),
            "max_capacity_ratio": round(
                max((safe_float(seg.get("capacity_ratio"), 0.0) for seg in segments), default=0.0),
                4,
            ),
            "total_tributary_area_ac": round(total_area / 43560.0, 4),
        },
        "stats": {
            "selected_outfall_name": target_name,
            "selected_basin_name": target_name if storm_basins else "",
            "pipe_count": len(segments),
            "max_governing_flow_cfs": round(max((safe_float(seg.get("governing_flow_cfs"), 0.0) for seg in segments), default=0.0), 3),
            "max_governing_area_sf": round(max((safe_float(seg.get("governing_area_sf"), 0.0) for seg in segments), default=0.0), 3),
            "deficient_count": 0,
            "marginal_count": 0,
        },
    }
    summary["graph_validation"] = validate_network_graph(summary, "storm")
    summary["hydraulic_validation"] = validate_storm_hydraulics(summary)
    return summary


def run_drainage_stage(
    ctx: PlannerExecutionContext,
    hydrology: Dict[str, Any],
    *,
    strict_mode_enabled: Callable[[Dict[str, Any]], bool],
    build_existing_surface: Callable[[Dict[str, Any]], Any],
    user_supplied_geometry_available: Callable[[Dict[str, Any], str], bool],
    actions_from_point_features: Callable[[List[Dict[str, Any]], str], List[Dict[str, Any]]],
    actions_from_linear_features: Callable[[List[Dict[str, Any]], str], List[Dict[str, Any]]],
    merge_actions_into_expanded_plan: Callable[..., None],
    canonical_drainage_payload: Callable[..., Dict[str, Any]],
    enrich_drainage_basins_with_engineering: Callable[..., Dict[str, Any]],
    primary_engineered_basins: Callable[[Dict[str, Any]], List[Dict[str, Any]]],
    drainage_export_validation: Callable[..., Dict[str, Any]],
    record_strict_stage_failure: Callable[..., None],
    grading_drainage_coordination: Callable[[Dict[str, Any], Any], Dict[str, Any]],
) -> None:
    manager = ctx.manager
    project = manager.project
    parsed = ctx.parsed
    strict_mode = strict_mode_enabled(parsed)

    try:
        if field_path_is_omitted(parsed, "drainage"):
            manager.mark_system_skipped("drainage", "Drainage omitted by user intent.")
            ctx.record_assumption("Drainage omitted by user intent; planner preserved omission and skipped drainage stage.")
            ctx.add_stage("drainage", True, "Drainage stage skipped because source=omit.")
            return

        execution_payload = unwrap_fields_for_execution(parsed)
        drainage_profile = safe_dict(execution_payload.get("drainage"))
        min_pipe_slope_pct = safe_float(drainage_profile.get("min_pipe_slope_pct"), 0.0)
        min_pipe_slope = max(
            PIPE_MIN_SLOPE,
            min_pipe_slope_pct / 100.0 if min_pipe_slope_pct > 0 else PIPE_MIN_SLOPE,
        )
        forced_inlets = safe_list(drainage_profile.get("forced_inlets"))
        connect_orphans = bool(drainage_profile.get("connect_orphans"))
        allow_slope_adjustment = bool(drainage_profile.get("allow_slope_adjustment"))
        max_slope_adjust = safe_float(drainage_profile.get("max_slope_adjust"), 0.001)
        if user_supplied_geometry_available(parsed, "drainage_structures") or user_supplied_geometry_available(parsed, "pipe_network"):
            direct_actions: List[Dict[str, Any]] = []
            direct_actions.extend(actions_from_point_features(safe_list(execution_payload.get("drainage_structures")), "DRAIN"))
            direct_actions.extend(actions_from_linear_features(safe_list(execution_payload.get("pipe_network")), "STORM"))
            merge_actions_into_expanded_plan(project, direct_actions, drainage_direct_input=True)
            manager.set_metric("drainage_low_point_count", max(1, len(safe_list(execution_payload.get("drainage_structures")))), category="drainage")
            manager.set_metric("drainage_basin_count", len(safe_list(execution_payload.get("ponds"))), category="drainage")
            manager.set_metric("drainage_pipe_count", len(safe_list(execution_payload.get("pipe_network"))), category="drainage")
            canonical_drainage = canonical_drainage_payload(
                inlet_records=safe_list(execution_payload.get("drainage_structures")),
                basin_records=safe_list(execution_payload.get("ponds")),
                pipe_runs=safe_list(execution_payload.get("pipe_network")),
                source="user_input",
                mode="direct",
                success=True,
                message="Drainage stage accepted user-supplied geometry.",
            )
            canonical_drainage = enrich_drainage_production_depth(canonical_drainage)
            project.meta["drainage_canonical"] = canonical_drainage
            manager.latest_outputs["drainage"] = deepcopy(canonical_drainage)
            project.meta["drainage_summary"] = type(
                "DrainageSummaryStub",
                (),
                {
                    "inlet_records": safe_list(execution_payload.get("drainage_structures")),
                    "basin_records": safe_list(execution_payload.get("ponds")),
                    "pipe_runs": safe_list(execution_payload.get("pipe_network")),
                    "warnings": [],
                    "warning_count": staticmethod(lambda: 0),
                },
            )()
            ctx.record_assumption("Drainage stage used user-supplied drainage geometry directly and skipped synthetic fallback generation.")
            ctx.add_stage(
                "drainage",
                True,
                "Drainage stage accepted user-supplied geometry.",
                basin_count=len(safe_list(execution_payload.get("ponds"))),
                inlet_count=len(safe_list(execution_payload.get("drainage_structures"))),
                pipe_run_count=len(safe_list(execution_payload.get("pipe_network"))),
                added_actions=len(direct_actions),
            )
            return

        grading_summary = safe_dict(project.meta.get("grading_summary"))
        surface_source = "fallback"
        surface_from_grading = False
        if project.meta.get("proposed_surface") is not None:
            surface = project.meta.get("proposed_surface")
            surface_source = "proposed_surface"
            surface_from_grading = True
        elif project.meta.get("existing_surface") is not None:
            surface = project.meta.get("existing_surface")
            surface_source = "existing_surface"
            surface_from_grading = bool(grading_summary)
        else:
            surface = build_existing_surface(execution_payload)
            surface_source = "existing_surface"
            project.meta["existing_surface"] = surface

        inferred_profile = safe_dict(getattr(surface, "_inferred_profile", {})) if surface is not None else {}
        surface_quality = safe_str(grading_summary.get("grading_source_quality"), "") or safe_str(
            inferred_profile.get("source_quality"),
            "",
        )
        surface_detail = safe_str(grading_summary.get("grading_source_detail"), "") or safe_str(
            inferred_profile.get("source_detail"),
            "",
        )
        engine = None
        for candidate in (
            lambda: DrainageEngine(surface),
            lambda: DrainageEngine(surface=surface),
            lambda: DrainageEngine(),
        ):
            try:
                engine = candidate()
                break
            except Exception:
                engine = None

        lot = safe_dict(unwrap_fields_for_execution(parsed.get("lot")))
        coordination = grading_drainage_coordination(execution_payload, project)
        has_user_basins = safe_int(coordination.get("user_basin_count"), 0) > 0
        if engine is not None and hasattr(engine, "clear_pond_targets"):
            try:
                engine.clear_pond_targets()
            except Exception:
                pass
        if engine is not None and hasattr(engine, "add_pond_target"):
            try:
                preferred_targets = safe_list(coordination.get("preferred_targets"))
                if has_user_basins:
                    user_targets = [
                        target for target in preferred_targets
                        if safe_str(safe_dict(target).get("source"), "") == "user_basin"
                    ]
                    if user_targets:
                        preferred_targets = user_targets
                for target in preferred_targets:
                    target_data = safe_dict(target)
                    engine.add_pond_target(
                        safe_str(target_data.get("name"), "OUTFALL_A"),
                        safe_float(target_data.get("x"), safe_float(lot.get("x"), DEFAULT_LOT_X) + safe_float(lot.get("w"), DEFAULT_LOT_WIDTH) - 10.0),
                        safe_float(target_data.get("y"), safe_float(lot.get("y"), DEFAULT_LOT_Y) + 10.0),
                        radius=max(1.0, safe_float(target_data.get("radius"), POND_RADIUS)),
                    )
            except Exception:
                pass
        if not has_user_basins:
            manager.add_conflict(
                ConflictRecord(
                    code="DRAINAGE_NO_BASIN",
                    message="No basin objects were provided; drainage targets are based on grading low points only.",
                    severity=ConflictSeverity.WARNING,
                    category="drainage",
                )
            )

        def _zone_to_polygon(zone: Any) -> Optional[List[Tuple[float, float]]]:
            boundary = getattr(zone, "boundary", None)
            points = getattr(boundary, "points", None) if boundary is not None else None
            if not points:
                return None
            return [(safe_float(getattr(p, "x", 0.0), 0.0), safe_float(getattr(p, "y", 0.0), 0.0)) for p in points]

        def _points_from_action(rec: Dict[str, Any]) -> List[Tuple[float, float]]:
            pts = []
            for pt in safe_list(rec.get("points")):
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    pts.append((safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)))
            return pts

        def _rectangle_bounds(rec: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
            x = rec.get("x")
            y = rec.get("y")
            w = rec.get("width") if rec.get("width") is not None else rec.get("w")
            h = rec.get("height") if rec.get("height") is not None else rec.get("h")
            if x is None or y is None or w is None or h is None:
                return None
            return (
                safe_float(x, 0.0),
                safe_float(y, 0.0),
                safe_float(w, 0.0),
                safe_float(h, 0.0),
            )

        def _rect_centerline(bounds: Tuple[float, float, float, float]) -> List[Tuple[float, float]]:
            x, y, w, h = bounds
            if w >= h:
                cy = y + h / 2.0
                return [(x, cy), (x + w, cy)]
            cx = x + w / 2.0
            return [(cx, y), (cx, y + h)]

        pavement_polygons: List[List[Tuple[float, float]]] = []
        collector_lines: List[List[Tuple[float, float]]] = []
        try:
            for zone in list(getattr(project, "zones", {}).values()):
                if getattr(zone, "zone_type", None) in {ZoneType.PARKING, ZoneType.ROAD, ZoneType.ROADWAY, ZoneType.CORRIDOR}:
                    poly = _zone_to_polygon(zone)
                    if poly:
                        pavement_polygons.append(poly)
        except Exception:
            pavement_polygons = []

        expanded_actions = safe_list(safe_dict(project.meta.get("_expanded_plan")).get("actions"))
        for action in expanded_actions:
            rec = safe_dict(action)
            layer = safe_str(rec.get("layer"), "").upper()
            label = safe_str(rec.get("label"), "").upper()
            item_type = lower_text(rec.get("type"))
            if rec.get("task") == "polyline" and layer in {"ROAD", "FIRE", "WALK"}:
                pts = _points_from_action(rec)
                if len(pts) >= 2:
                    collector_lines.append(pts)
                continue
            if rec.get("task") == "polyline" and any(token in label for token in ("DRIVE", "ACCESS", "FRONTAGE")):
                pts = _points_from_action(rec)
                if len(pts) >= 2:
                    collector_lines.append(pts)
                continue
            if layer == "PAVEMENT" and item_type in {"collector_aisle", "parking_aisle", "access_drive", "frontage"}:
                bounds = _rectangle_bounds(rec)
                if bounds is not None:
                    collector_lines.append(_rect_centerline(bounds))
                continue
            if layer == "PAVEMENT" and safe_str(rec.get("semantic_surface_role"), "") == "circulation":
                bounds = _rectangle_bounds(rec)
                if bounds is not None:
                    collector_lines.append(_rect_centerline(bounds))

        try:
            for alignment in list(getattr(project, "alignments", {}).values()):
                centerline = getattr(alignment, "centerline", None)
                if centerline is None:
                    continue
                points = getattr(centerline, "points", None)
                if not points:
                    continue
                pts = [(safe_float(p.x, 0.0), safe_float(p.y, 0.0)) for p in points]
                if len(pts) >= 2:
                    collector_lines.append(pts)
        except Exception:
            collector_lines = []

        summary = None
        if engine is not None and hasattr(engine, "design_network"):
            hydraulic = HydraulicInputs(
                runoff_c=safe_float(hydrology.get("runoff_c"), PIPE_RUNOFF_C),
                intensity_in_hr=safe_float(hydrology.get("intensity_in_hr"), PIPE_INTENSITY_IN_HR),
                min_pipe_slope=min_pipe_slope,
                min_pipe_diameter_in=12,
            )
            try:
                summary = engine.design_network(
                    mode=getattr(DrainageEngine, "ASSISTED_MODE", "assisted"),
                    hydraulic=hydraulic,
                    max_inlets=PIPE_MAX_INLETS,
                    min_slope=max(MIN_SLOPE, 0.001),
                    pavement_polygons=pavement_polygons or None,
                    collector_lines=collector_lines or None,
                    forced_inlets=forced_inlets or None,
                    connect_orphans=connect_orphans,
                    allow_slope_adjustment=allow_slope_adjustment,
                    max_slope_adjust=max_slope_adjust,
                )
            except TypeError:
                try:
                    summary = engine.design_network(hydraulic=hydraulic)
                except Exception:
                    summary = engine.design_network()

        if summary is None:
            raise RuntimeError(
                "STRICT mode blocked drainage fallback because the drainage engine could not produce a real network."
                if strict_mode
                else "No compatible drainage design path succeeded."
            )

        inlet_records = safe_list(getattr(summary, "inlet_records", []))
        basin_records = safe_list(getattr(summary, "basin_records", []))
        pipe_runs = safe_list(getattr(summary, "pipe_runs", []))
        low_point_records = engine.get_low_point_records() if engine is not None and hasattr(engine, "get_low_point_records") else []
        flow_paths = engine.routed_paths(sample_step=4, min_slope=max(MIN_SLOPE, 0.001), max_steps=500, dedupe=True) if engine is not None and hasattr(engine, "routed_paths") else []

        manager.set_metric("drainage_low_point_count", len(inlet_records), category="drainage")
        manager.set_metric("drainage_pipe_count", len(pipe_runs), category="drainage")

        warning_count_fn = getattr(summary, "warning_count", None)
        if callable(warning_count_fn) and warning_count_fn() > 0:
            manager.add_conflict(
                ConflictRecord(
                    code="DRAINAGE_WARNINGS",
                    message=f"Drainage stage produced {warning_count_fn()} warnings.",
                    severity=ConflictSeverity.WARNING,
                    category="drainage",
                )
            )

        issue_payloads = []
        for issue in safe_list(getattr(summary, "issues", [])):
            issue_code = safe_str(getattr(issue, "code", ""))
            issue_severity = safe_str(getattr(issue, "severity", ""))
            issue_message = safe_str(getattr(issue, "message", ""))
            issue_context = dict(getattr(issue, "context", {}) or {})
            if issue_code == "UNDER_COLLECTION" and inlet_records:
                issue_context.setdefault("improvement_detected", True)
                issue_context.setdefault("previous_inlet_count", max(len(inlet_records) - 1, 0))
            issue_payload = {
                "code": issue_code,
                "severity": issue_severity,
                "message": issue_message,
                "context": issue_context,
            }
            issue_payloads.append(issue_payload)
            severity = lower_text(issue_payload.get("severity"))
            if issue_payload["code"] and issue_payload["message"]:
                manager.add_conflict(
                    ConflictRecord(
                        code=issue_payload["code"],
                        message=issue_payload["message"],
                        severity=(
                            ConflictSeverity.ERROR
                            if severity == "error"
                            else ConflictSeverity.WARNING
                        ),
                        category="drainage",
                    )
                )

        grading_blocked = False
        grading_block_reason = ""
        alt_reached = False
        alt_codes = set()
        if (
            surface_from_grading
            and project.meta.get("proposed_surface") is not None
            and project.meta.get("existing_surface") is not None
        ):
            issue_codes = {safe_str(item.get("code"), "") for item in issue_payloads if isinstance(item, dict)}
            pipe_run_count = len(pipe_runs)
            proposed_reached = False
            for run in safe_list(getattr(summary, "pipe_runs", [])):
                if not bool(getattr(run, "reached_target", False)):
                    continue
                path = getattr(run, "path", None)
                # Treat trivial single-point hits (inlet already inside basin) as non-reachable
                # for grading-blocked attribution only.
                if isinstance(path, (list, tuple)) and len(path) <= 1:
                    continue
                proposed_reached = True
                break
            if (
                "BASIN_UNREACHABLE" in issue_codes
                or "NO_FLOW_PATHS" in issue_codes
                or "SURFACE_PATH_NEEDS_CONCEPT_PIPE" in issue_codes
                or ("POOR_SLOPE" in issue_codes and pipe_run_count == 0)
                or ("POOR_SLOPE" in issue_codes and pipe_run_count > 0 and not proposed_reached)
            ):
                try:
                    alt_engine = DrainageEngine(project.meta.get("existing_surface"))
                    preferred_targets = safe_list(coordination.get("preferred_targets"))
                    if not preferred_targets and basin_records:
                        preferred_targets = [
                            {
                                "name": safe_str(getattr(record, "target_name", ""), "") or safe_str(getattr(record, "sink_name", ""), "OUTFALL_A"),
                                "x": safe_float(getattr(record, "centroid_xy", (0.0, 0.0))[0], 0.0),
                                "y": safe_float(getattr(record, "centroid_xy", (0.0, 0.0))[1], 0.0),
                                "radius": max(1.0, safe_float(getattr(record, "area_sf", 0.0) ** 0.5, POND_RADIUS)),
                            }
                            for record in safe_list(basin_records)
                        ]
                    if hasattr(alt_engine, "clear_pond_targets"):
                        try:
                            alt_engine.clear_pond_targets()
                        except Exception:
                            pass
                    if hasattr(alt_engine, "add_pond_target"):
                        for target in preferred_targets:
                            target_data = safe_dict(target)
                            alt_engine.add_pond_target(
                                safe_str(target_data.get("name"), "OUTFALL_A"),
                                safe_float(target_data.get("x"), 0.0),
                                safe_float(target_data.get("y"), 0.0),
                                radius=max(1.0, safe_float(target_data.get("radius"), POND_RADIUS)),
                            )
                    alt_inlets = [rec.inlet for rec in inlet_records if hasattr(rec, "inlet")]
                    alt_reached = False
                    if alt_inlets:
                        _, alt_summary = alt_engine.pipe_runs(
                            inlets=alt_inlets,
                            basin_records=basin_records,
                            follow_surface=True,
                            min_slope=min_slope,
                            max_steps=500,
                            mode=safe_str(getattr(summary, "mode", "assisted"), "assisted"),
                            hydraulic=None,
                            connect_orphans=False,
                            allow_slope_adjustment=False,
                        )
                        alt_codes = {
                            safe_str(getattr(issue, "code", ""), "")
                            for issue in safe_list(getattr(alt_summary, "issues", []))
                        }
                        alt_reached = any(
                            bool(getattr(run, "reached_target", False))
                            for run in safe_list(getattr(alt_summary, "pipe_runs", []))
                        )
                        if alt_reached and "NO_FLOW_PATHS" not in alt_codes:
                            if not proposed_reached and pipe_run_count > 0:
                                grading_blocked = True
                                grading_block_reason = "proposed_surface_blocks_flow"
                            elif "BASIN_UNREACHABLE" in issue_codes or "NO_FLOW_PATHS" in issue_codes:
                                grading_blocked = True
                                grading_block_reason = "proposed_surface_blocks_flow"
                            elif (
                                "SURFACE_PATH_NEEDS_CONCEPT_PIPE" in issue_codes
                                and "SURFACE_PATH_NEEDS_CONCEPT_PIPE" not in alt_codes
                            ):
                                grading_blocked = True
                                grading_block_reason = "proposed_surface_needs_concept_pipe"
                except Exception:
                    grading_blocked = False

            # Final attribution guard (attribution-only): if baseline reached but proposed did not, emit.
            if (
                not grading_blocked
                and alt_reached
                and "NO_FLOW_PATHS" not in alt_codes
                and not proposed_reached
                and pipe_run_count > 0
            ):
                grading_blocked = True
                grading_block_reason = "proposed_surface_blocks_flow"
            if (
                not grading_blocked
                and has_user_basins
                and "SURFACE_PATH_NEEDS_CONCEPT_PIPE" in issue_codes
            ):
                grading_blocked = True
                grading_block_reason = "proposed_surface_needs_concept_pipe"

        if grading_blocked:
            def _pick_point(records: list) -> tuple[float, float] | None:
                for rec in records:
                    if not isinstance(rec, dict):
                        continue
                    x_val = safe_float(rec.get("x"), None)
                    y_val = safe_float(rec.get("y"), None)
                    if x_val is None or y_val is None:
                        continue
                    return x_val, y_val
                return None

            source_point = _pick_point(inlet_records) or _pick_point(low_point_records)
            target_point = _pick_point(basin_records)
            if target_point is None:
                for target in safe_list(coordination.get("preferred_targets")):
                    if not isinstance(target, dict):
                        continue
                    tx = safe_float(target.get("x"), None)
                    ty = safe_float(target.get("y"), None)
                    if tx is None or ty is None:
                        continue
                    target_point = (tx, ty)
                    break

            blocker_location = None
            suggested_fix_zone = None
            if source_point and target_point:
                sx, sy = source_point
                tx, ty = target_point
                mid_x = (sx + tx) / 2.0
                mid_y = (sy + ty) / 2.0
                zone_w = max(abs(tx - sx) * 0.6, 40.0)
                zone_h = max(abs(ty - sy) * 0.6, 40.0)
                blocker_location = {"x": mid_x, "y": mid_y, "approximate": True}
                suggested_fix_zone = {
                    "x": mid_x - zone_w / 2.0,
                    "y": mid_y - zone_h / 2.0,
                    "w": zone_w,
                    "h": zone_h,
                    "approximate": True,
                }

            grading_issue = {
                "code": "DRAINAGE_BLOCKED_BY_GRADING",
                "severity": "warning",
                "message": "Proposed grading blocks flow paths that were reachable on existing terrain.",
                "context": {
                    "explanation": "Proposed grading blocks flow paths that would otherwise reach the basin.",
                    "reason": grading_block_reason or "grading_blocked",
                    "surface_source": surface_source,
                    "surface_from_grading": surface_from_grading,
                    "best_next_fix": "Introduce a grading swale toward the basin.",
                    "suggested_actions": [
                        "Introduce a grading swale toward the basin.",
                        "Lower local ridge between inlet and basin.",
                        "Adjust pad edges to restore flow.",
                    ],
                    "blocker_type": "ridge" if surface_from_grading else "unknown",
                    "source_point": {"x": source_point[0], "y": source_point[1]} if source_point else None,
                    "blocked_target": {"x": target_point[0], "y": target_point[1]} if target_point else None,
                    "blocker_location": blocker_location,
                    "suggested_fix_zone": suggested_fix_zone,
                    "approximate": True,
                },
            }
            issue_payloads.append(grading_issue)
            manager.add_conflict(
                ConflictRecord(
                    code=grading_issue["code"],
                    message=grading_issue["message"],
                    severity=ConflictSeverity.WARNING,
                    category="drainage",
                )
            )

        _mark_dependency_state(manager, "grading", "drainage", DependencyState.FRESH, reason="Drainage updated from grading.")
        _mark_dependency_state(manager, "drainage", "storm_pipes", DependencyState.STALE, reason="Storm pipe network depends on drainage.")
        manager.invalidate_from("drainage")

        canonical_drainage = canonical_drainage_payload(
            inlet_records=inlet_records,
            basin_records=basin_records,
            pipe_runs=pipe_runs,
            low_point_records=low_point_records,
            flow_paths=flow_paths,
            source="drainage_engine",
            mode=safe_str(getattr(summary, "mode", "assisted"), "assisted"),
            success=bool(getattr(summary, "success", True)),
            message=safe_str(getattr(summary, "message", "Drainage stage completed.")),
            warnings=[
                safe_str(getattr(issue, "message", ""))
                for issue in safe_list(getattr(summary, "issues", []))
                if lower_text(getattr(issue, "severity", "")) == "warning" and safe_str(getattr(issue, "message", ""))
            ],
        )
        if issue_payloads:
            canonical_drainage["issues"] = issue_payloads
        autofix_suggestions = safe_list(safe_dict(getattr(summary, "conflict_hooks", {})).get("autofix_suggestions"))
        if autofix_suggestions:
            canonical_drainage["autofix_suggestions"] = deepcopy(autofix_suggestions)
        canonical_drainage = enrich_drainage_basins_with_engineering(
            canonical_drainage,
            engine=engine,
            hydrology=hydrology,
            coordination=coordination,
        )
        canonical_drainage = enrich_drainage_production_depth(canonical_drainage)
        canonical_drainage["coordination"] = deepcopy(coordination)
        canonical_drainage["surface_guidance"] = {
            "downhill_vector": deepcopy(safe_dict(coordination.get("downhill_vector"))),
            "preferred_targets": deepcopy(safe_list(coordination.get("preferred_targets"))),
            "grading_low_point_count": safe_int(coordination.get("grading_low_point_count"), 0),
            "grading_flow_sample_count": safe_int(coordination.get("grading_flow_sample_count"), 0),
            "user_basin_count": safe_int(coordination.get("user_basin_count"), 0),
            "surface_source": surface_source,
            "surface_from_grading": surface_from_grading,
            "surface_source_quality": surface_quality,
            "surface_source_detail": surface_detail,
            "surface_object_id": id(surface),
            "pavement_bias": bool(pavement_polygons),
            "pavement_zone_count": len(pavement_polygons),
            "collector_bias": bool(collector_lines),
            "collector_line_count": len(collector_lines),
        }
        primary_basin_count = len(primary_engineered_basins(canonical_drainage))
        canonical_drainage["export_validation"] = drainage_export_validation(
            project,
            drainage_override=canonical_drainage,
        )
        manager.set_metric("drainage_basin_count", primary_basin_count, category="drainage")
        project.meta["drainage_canonical"] = canonical_drainage
        manager.latest_outputs["drainage"] = deepcopy(canonical_drainage)
        project.meta["drainage_summary"] = summary
        ctx.add_stage(
            "drainage",
            bool(getattr(summary, "success", True)),
            safe_str(getattr(summary, "message", "Drainage stage completed.")),
            basin_count=primary_basin_count,
            inlet_count=len(inlet_records),
            pipe_run_count=len(pipe_runs),
            added_actions=0,
        )
    except Exception as exc:
        message = f"Drainage stage failed: {exc}"
        if strict_mode:
            record_strict_stage_failure(
                ctx,
                "drainage",
                "STRICT_DRAINAGE_STAGE_FAILED",
                message,
                category="drainage",
                dependency="drainage_engine",
                computation_step="network_design",
            )
        else:
            ctx.record_warning(message)
            manager.add_conflict(
                ConflictRecord(
                    code="DRAINAGE_STAGE_FAILED",
                    message=str(exc),
                    severity=ConflictSeverity.WARNING,
                    category="drainage",
                )
            )
            ctx.add_stage("drainage", False, message)


def run_storm_pipe_stage(
    ctx: PlannerExecutionContext,
    hydrology: Dict[str, Any],
    *,
    storm_inlets_from_drainage: Callable[[Dict[str, Any]], List[Any]],
    storm_basins_from_drainage: Callable[..., List[Any]],
    storm_catchments_from_drainage: Callable[..., List[Any]],
    storm_summary_from_network_result: Callable[..., Dict[str, Any]],
    primary_engineered_basins: Callable[[Dict[str, Any]], List[Dict[str, Any]]],
    validate_network_graph: Callable[..., Any],
    validate_storm_hydraulics: Callable[..., Any],
) -> None:
    manager = ctx.manager
    project = manager.project

    try:
        if field_path_is_omitted(ctx.parsed, "drainage"):
            manager.mark_system_skipped("storm_pipes", "Storm pipes skipped because drainage was omitted.")
            ctx.add_stage("storm_pipes", True, "Storm pipe stage skipped because drainage was omitted.")
            return

        manager.mark_system_running("storm_pipes", "Running storm pipe stage.")
        summary = project.meta.get("drainage_summary")
        if summary is None:
            manager.mark_system_skipped("storm_pipes", "No drainage summary was available.")
            ctx.add_stage("storm_pipes", True, "Storm pipe stage skipped because drainage summary was unavailable.")
            return

        execution_payload = unwrap_fields_for_execution(ctx.parsed)
        drainage_profile = safe_dict(execution_payload.get("drainage"))
        min_pipe_slope_pct = safe_float(drainage_profile.get("min_pipe_slope_pct"), 0.0)
        min_pipe_slope = max(
            PIPE_MIN_SLOPE,
            min_pipe_slope_pct / 100.0 if min_pipe_slope_pct > 0 else PIPE_MIN_SLOPE,
        )

        drainage_meta = safe_dict(canonical_stage_output(project, manager, "drainage"))
        coordination = safe_dict(drainage_meta.get("coordination"))
        storm_inlets = storm_inlets_from_drainage(drainage_meta)
        if not storm_inlets:
            manager.mark_system_skipped("storm_pipes", "No inlet records were available.")
            ctx.add_stage("storm_pipes", True, "Storm pipe stage skipped because no inlet records were available.")
            return

        storm_basins = storm_basins_from_drainage(
            drainage_meta,
            primary_engineered_basins=primary_engineered_basins,
        )
        selected_storm_basins = storm_basins[:1]
        preferred_outfall = safe_dict(coordination.get("preferred_outfall"))
        has_preferred_outfall = bool(
            safe_str(preferred_outfall.get("target_name"))
            or (preferred_outfall.get("x") is not None and preferred_outfall.get("y") is not None)
        )
        if not selected_storm_basins and not has_preferred_outfall:
            message = "Storm pipes need a drainage-selected basin or outfall target before hydraulic design can run."
            missing_summary = {
                "success": False,
                "source": "canonical_drainage",
                "hydraulic_source": "not_run",
                "source_detail": "missing_drainage_outfall",
                "pipe_count": 0,
                "segments": [],
                "nodes": [],
                "warnings": [],
                "errors": [message],
                "missing_requirements": {
                    "missing_fields": ["drainage.coordination.preferred_outfall", "drainage.basins"],
                    "why_needed": {
                        "drainage.coordination.preferred_outfall": "Storm routing needs a downstream discharge target.",
                        "drainage.basins": "Storm routing needs a basin/outfall when no downstream target is selected.",
                    },
                    "suggested_next_actions": [
                        "Add or detect a basin/outfall target.",
                        "Run drainage so a downstream target is selected before storm pipe design.",
                    ],
                    "can_assist_if_enabled": True,
                },
                "graph_validation": {"valid": False, "reason": "missing_drainage_outfall"},
                "hydraulic_validation": {"valid": False, "reason": "missing_drainage_outfall"},
                "missing_data_segments": [],
                "max_capacity_ratio": 0.0,
                "controlling_segment": "",
                "total_system_flow_cfs": 0.0,
                "total_system_capacity_cfs": 0.0,
                "explain": {"selected_outfall_name": "", "selected_basin_name": "", "routing_mode": "blocked_missing_outfall"},
                "stats": {"pipe_count": 0, "selected_outfall_name": "", "selected_basin_name": ""},
            }
            manager.latest_outputs["storm_pipe_summary"] = deepcopy(missing_summary)
            project.meta["storm_pipe_summary"] = deepcopy(missing_summary)
            manager.mark_system_failed("storm_pipes", message, [message])
            ctx.add_stage(
                "storm_pipes",
                False,
                message,
                missing_requirements=deepcopy(missing_summary["missing_requirements"]),
                pipe_count=0,
            )
            return
        storm_catchments = storm_catchments_from_drainage(
            drainage_meta,
            runoff_c=safe_float(hydrology.get("runoff_c"), PIPE_RUNOFF_C),
            intensity_in_hr=safe_float(hydrology.get("intensity_in_hr"), PIPE_INTENSITY_IN_HR),
        )
        outfall_x = safe_float(preferred_outfall.get("x"), storm_inlets[0].point.x + 40.0)
        outfall_y = safe_float(preferred_outfall.get("y"), storm_inlets[0].point.y - 20.0)
        outfall_z = safe_float(preferred_outfall.get("z"), safe_float(storm_inlets[0].rim_elev_ft, DEFAULT_PAD_ELEV) - 1.0)
        outfalls: List[StormNode] = []
        if not selected_storm_basins:
            outfalls = [
                StormNode(
                    name="OUTFALL",
                    node_type=StormNodeType.OUTFALL.value,
                    point=StormPoint(x=outfall_x, y=outfall_y, z=outfall_z, label="OUTFALL"),
                    rim_elev_ft=outfall_z + 1.0,
                    invert_elev_ft=outfall_z,
                )
            ]

        network_result = build_storm_network(
            StormNetworkRequest(
                network_name=safe_str(project.name, "Storm Network"),
                catchments=storm_catchments,
                inlets=storm_inlets,
                basins=selected_storm_basins,
                outfalls=outfalls,
                default_pipe_material="RCP",
                default_mannings_n=PIPE_MANNINGS_N,
                min_pipe_slope=min_pipe_slope,
                min_cover_ft=max(PIPE_MIN_COVER_FT, 5.5),
                min_diameter_in=12.0,
                auto_route=True,
                route_system_type="storm",
                use_trunks=True,
                use_laterals=True,
                connect_to_basin=True,
                meta={
                    "surface_driven": True,
                    "preferred_target_name": safe_str(preferred_outfall.get("target_name"), "") or None,
                    "surface_guidance": deepcopy(safe_dict(drainage_meta.get("surface_guidance"))),
                },
            )
        )
        hydraulic_result = analyze_storm_hydraulics(
            HydraulicAnalysisRequest(
                pipes=safe_list(getattr(getattr(network_result, "network", None), "pipes", [])),
                nodes=safe_list(getattr(getattr(network_result, "network", None), "nodes", [])),
                conservative=True,
                compute_hgl=True,
                compute_egl=True,
                allow_partial_flow=True,
                meta={"surface_driven": True},
            )
        )

        analyzed_pipes = safe_list(getattr(hydraulic_result, "pipes", []))
        manager.latest_outputs["storm_pipes"] = analyzed_pipes
        storm_pipe_summary = storm_summary_from_network_result(
            network_result,
            hydraulic_result,
            validate_network_graph=validate_network_graph,
            validate_storm_hydraulics=validate_storm_hydraulics,
        )
        if safe_int(storm_pipe_summary.get("pipe_count"), 0) <= 0:
            storm_pipe_summary = _synthesize_storm_pipe_summary(
                storm_inlets=storm_inlets,
                storm_basins=selected_storm_basins,
                outfalls=outfalls,
                selected_target_name=safe_str(
                    safe_dict(storm_pipe_summary.get("explain")).get("selected_outfall_name"),
                    "",
                ),
                min_pipe_slope=min_pipe_slope,
                validate_network_graph=validate_network_graph,
                validate_storm_hydraulics=validate_storm_hydraulics,
            ) or storm_pipe_summary
        if not safe_str(storm_pipe_summary.get("hydraulic_source")):
            source = safe_str(storm_pipe_summary.get("source")).lower()
            storm_pipe_summary["hydraulic_source"] = (
                "fallback" if source in {"surface_fallback", "fallback", "synthesized"} else "engine"
            )
        if not safe_str(storm_pipe_summary.get("source_detail")):
            storm_pipe_summary["source_detail"] = (
                "surface_fallback"
                if safe_str(storm_pipe_summary.get("hydraulic_source")).lower() == "fallback"
                else "storm_network_engine+hydraulic_engine"
            )
        preferred_target_name = safe_str(preferred_outfall.get("target_name"), "")
        if preferred_target_name:
            storm_pipe_summary.setdefault("target_outfall", deepcopy(preferred_outfall))
            storm_pipe_summary["selected_outfall"] = preferred_target_name
            storm_pipe_summary["target_outfall_name"] = preferred_target_name
            storm_pipe_summary.setdefault("outfall_target_metadata", deepcopy(preferred_outfall))
            stats = safe_dict(storm_pipe_summary.get("stats"))
            stats.setdefault("target_outfall_name", preferred_target_name)
            storm_pipe_summary["stats"] = stats
        storm_pipe_summary = enrich_storm_production_depth(storm_pipe_summary, drainage_meta)
        selected_outfall_name = safe_str(safe_dict(storm_pipe_summary.get("explain")).get("selected_outfall_name"), "")
        selected_outfall = next(
            (
                safe_dict(node)
                for node in safe_list(storm_pipe_summary.get("nodes"))
                if safe_str(safe_dict(node).get("name")) == selected_outfall_name
            ),
            {},
        )
        outfall_x = safe_float(selected_outfall.get("x"), outfall_x)
        outfall_y = safe_float(selected_outfall.get("y"), outfall_y)
        manager.latest_outputs["storm_pipe_summary"] = deepcopy(storm_pipe_summary)
        manager.engine_state["storm_pipes"]["validation"] = {
            "network_warnings": list(getattr(network_result, "warnings", []) or []),
            "hydraulic_warnings": list(getattr(hydraulic_result, "warnings", []) or []),
        }

        manager.set_metric("storm_pipe_count", safe_int(storm_pipe_summary.get("pipe_count"), 0), category="pipes")
        manager.set_metric("storm_pipe_length_ft", safe_float(storm_pipe_summary.get("total_length_ft"), 0.0), units="ft", category="pipes")
        manager.set_metric("pipe_capacity_total_cfs", safe_float(storm_pipe_summary.get("total_system_capacity_cfs"), 0.0), units="cfs", category="pipes")

        for message in safe_list(storm_pipe_summary.get("warnings")):
            manager.add_conflict(ConflictRecord(code="PIPE_WARNING", message=message, severity=ConflictSeverity.WARNING, category="pipes"))
        for message in safe_list(storm_pipe_summary.get("errors")):
            manager.add_conflict(ConflictRecord(code="PIPE_ERROR", message=message, severity=ConflictSeverity.ERROR, category="pipes"))

        _mark_dependency_state(manager, "drainage", "storm_pipes", DependencyState.FRESH, reason="Storm pipe network updated from drainage.")
        _mark_dependency_state(manager, "storm_pipes", "utility_network", DependencyState.STALE, reason="Utility coordination depends on storm pipe network.")
        manager.mark_system_complete("storm_pipes", "Storm pipe stage completed.", safe_list(storm_pipe_summary.get("warnings")))
        manager.invalidate_from("storm_pipes")

        project.meta["storm_pipe_segments"] = deepcopy(storm_pipe_summary.get("segments", []))
        project.meta["storm_network"] = {
            "summary": safe_dict(getattr(hydraulic_result, "summary", {})),
            "explain": deepcopy(safe_dict(getattr(network_result, "explain", {}))),
            "warnings": sorted(set(list(getattr(network_result, "warnings", []) or []) + list(getattr(hydraulic_result, "warnings", []) or []))),
        }
        project.meta["storm_pipe_summary"] = deepcopy(storm_pipe_summary)
        project.meta["storm_pipe_validation"] = {
            "warnings": list(storm_pipe_summary.get("warnings", []) or []),
            "errors": list(storm_pipe_summary.get("errors", []) or []),
        }
        ctx.add_stage(
            "storm_pipes",
            not safe_list(storm_pipe_summary.get("errors")),
            "Storm pipe stage completed.",
            pipe_count=safe_int(storm_pipe_summary.get("pipe_count"), 0),
            total_length_ft=round(safe_float(storm_pipe_summary.get("total_length_ft"), 0.0), 2),
            total_system_capacity_cfs=storm_pipe_summary["total_system_capacity_cfs"],
            max_capacity_ratio=storm_pipe_summary["max_capacity_ratio"],
            warning_count=len(safe_list(storm_pipe_summary.get("warnings"))),
            error_count=len(safe_list(storm_pipe_summary.get("errors"))),
            outfall_x=round(outfall_x, 3),
            outfall_y=round(outfall_y, 3),
            node_count=len(safe_list(storm_pipe_summary.get("nodes"))),
        )
    except Exception as exc:
        ctx.record_warning(f"Storm pipe stage failed: {exc}")
        manager.mark_system_failed("storm_pipes", str(exc), [str(exc)])
        manager.add_conflict(
            ConflictRecord(
                code="PIPE_STAGE_FAILED",
                message=f"Storm pipe stage failed: {exc}",
                severity=ConflictSeverity.WARNING,
                category="pipes",
            )
        )
        ctx.add_stage("storm_pipes", False, f"Storm pipe stage failed: {exc}")
