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


def _has_accepted_standard(row: Dict[str, Any]) -> bool:
    rec = safe_dict(row)
    status = safe_str(rec.get("standard_status") or rec.get("acceptance_status") or rec.get("jurisdiction_status")).lower()
    return bool(
        rec.get("standard_accepted") is True
        or rec.get("accepted_standard") is True
        or rec.get("jurisdiction_standard_accepted") is True
        or status in {"accepted", "adopted", "approved"}
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
    return hydrant_count >= 2 and max_spacing >= 0.0 and limit > 0.0 and max_spacing <= limit and _has_accepted_standard(rec)


def _has_valid_pressure_validation(row: Dict[str, Any]) -> bool:
    rec = safe_dict(row)
    if rec.get("valid") is not True or not _row_is_production_evidence(rec):
        return False
    source_pressure = safe_float(rec.get("source_pressure_psi"), 0.0)
    source_pressure_source = safe_str(rec.get("source_pressure_source"))
    min_pressure = safe_float(rec.get("min_pressure_psi"), -1.0)
    required = safe_float(rec.get("min_required_pressure_psi"), 0.0)
    residual_source = safe_str(rec.get("residual_pressure_source"))
    graph = safe_dict(rec.get("pressure_graph"))
    if graph:
        if graph.get("success") is not True or not safe_dict(graph.get("node_pressures_psi")):
            return False
    return (
        source_pressure > 0.0
        and bool(source_pressure_source)
        and required > 0.0
        and bool(residual_source)
        and min_pressure >= required
        and _has_accepted_standard(rec)
        and rec.get("utility_owner_criteria_accepted") is True
    )


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
    method = safe_str(rec.get("calculation_method") or rec.get("source")).lower()
    graph = safe_dict(rec.get("fire_flow_graph"))
    has_residual_evidence = (
        "residual" in method
        or bool(safe_list(rec.get("fire_flow_path")))
        or bool(safe_dict(graph.get("pressure_graph_at_available_flow")))
    )
    return (
        required > 0.0
        and bool(safe_str(rec.get("fire_flow_criteria_source")))
        and bool(safe_str(rec.get("source_pressure_source")))
        and bool(safe_str(rec.get("residual_pressure_source")))
        and bool(safe_str(rec.get("hydrant_evidence_source")))
        and available >= required
        and residual >= min_required > 0.0
        and has_residual_evidence
        and _has_accepted_standard(rec)
        and rec.get("utility_owner_criteria_accepted") is True
    )


def _has_valid_sizing_optimization(value: Any) -> bool:
    rec = safe_dict(value)
    if not rec:
        return False
    status = safe_str(rec.get("status") or rec.get("selected")).lower()
    return status in {"checked", "optimized", "accepted", "selected"} or bool(safe_list(rec.get("alternatives")))


def _has_valid_alignment(row: Dict[str, Any]) -> bool:
    rec = safe_dict(row)
    return bool(safe_str(rec.get("name") or rec.get("id")) and len(safe_list(rec.get("points") or rec.get("geometry"))) >= 2)


def _has_valid_profile(row: Dict[str, Any]) -> bool:
    rec = safe_dict(row)
    points = safe_list(rec.get("profile_points") or rec.get("points") or rec.get("samples"))
    has_samples = len(points) >= 2 or (_present(rec.get("station_start_ft")) and _present(rec.get("station_end_ft")))
    return bool(has_samples and _present(rec.get("alignment_owner") or rec.get("alignment_id") or rec.get("alignment")))


def _has_valid_intersection(row: Dict[str, Any]) -> bool:
    rec = safe_dict(row)
    connected = safe_list(rec.get("connected_alignments") or rec.get("legs"))
    leg_geometry = safe_list(rec.get("leg_geometry") or rec.get("approach_points"))
    return bool(
        _present(rec.get("point") or rec.get("geometry") or rec.get("x"))
        and len(connected) >= 2
        and (_present(rec.get("angle_deg") or rec.get("deflection_angle_deg")) or len(leg_geometry) >= 2 or _present(rec.get("geometry")))
    )


def _has_valid_curb_return(row: Dict[str, Any]) -> bool:
    rec = safe_dict(row)
    radius = safe_float(rec.get("radius_ft") or rec.get("design_radius_ft"), 0.0)
    geometry = safe_list(rec.get("geometry") or rec.get("arc_points") or rec.get("points"))
    tangent_points = safe_list(rec.get("tangent_points"))
    has_arc_geometry = len(geometry) >= 3 or len(tangent_points) >= 2 or (
        _present(rec.get("center")) and _present(rec.get("start_point")) and _present(rec.get("end_point"))
    )
    return bool(radius > 0.0 and _present(rec.get("intersection_id") or rec.get("intersection")) and has_arc_geometry)


def _has_valid_sidewalk(row: Dict[str, Any]) -> bool:
    rec = safe_dict(row)
    path = safe_list(rec.get("path") or rec.get("points") or rec.get("geometry"))
    width = safe_float(rec.get("width_ft") or rec.get("sidewalk_width_ft"), 0.0)
    continuity = safe_dict(rec.get("continuity_validation") or rec.get("continuity_check"))
    continuity_ok = continuity.get("valid") is not False and rec.get("continuous") is not False
    return bool(len(path) >= 2 and width > 0.0 and continuity_ok)


def _has_valid_ada_check(row: Dict[str, Any]) -> bool:
    rec = safe_dict(row)
    if rec.get("valid") is not True:
        return False
    has_slope_evidence = _present(rec.get("max_running_slope")) or _present(rec.get("running_slope")) or _present(rec.get("max_cross_slope"))
    continuity = safe_dict(rec.get("continuity_validation") or rec.get("continuity_check"))
    continuity_ok = continuity.get("valid") is not False and rec.get("continuous") is not False
    return bool(has_slope_evidence and _present(rec.get("standard") or rec.get("standard_id") or rec.get("source")) and _has_accepted_standard(rec) and continuity_ok)


def _has_valid_section(row: Dict[str, Any]) -> bool:
    rec = safe_dict(row)
    points = safe_list(rec.get("section_points") or rec.get("points") or rec.get("samples"))
    return bool(_present(rec.get("station_ft")) and len(points) >= 3 and _present(rec.get("alignment_owner") or rec.get("alignment_id") or rec.get("alignment")))


def _combined_grading_detail(meta: Dict[str, Any]) -> Dict[str, Any]:
    grading = safe_dict(meta.get("grading") or meta.get("grading_summary"))
    explicit = safe_dict(meta.get("grading_detail"))
    return {**grading, **explicit}


def _roadway_crown_expected_actual(row: Dict[str, Any]) -> Dict[str, Any]:
    rec = safe_dict(row)
    road_id = safe_str(rec.get("road_id") or rec.get("alignment_id") or rec.get("road") or rec.get("alignment"))
    expected_crown = rec.get("expected_crown_elev_ft", rec.get("design_crown_elev_ft"))
    actual_crown = rec.get("actual_crown_elev_ft", rec.get("crown_elev_ft"))
    expected_cross = rec.get("expected_cross_slope", rec.get("design_cross_slope", rec.get("standard_cross_slope")))
    actual_cross = rec.get("actual_cross_slope", rec.get("cross_slope"))
    expected_left_cross = rec.get("expected_left_cross_slope")
    actual_left_cross = rec.get("actual_left_cross_slope")
    expected_right_cross = rec.get("expected_right_cross_slope")
    actual_right_cross = rec.get("actual_right_cross_slope")
    crown_tolerance = safe_float(rec.get("crown_tolerance_ft"), 0.0)
    slope_tolerance = safe_float(rec.get("cross_slope_tolerance"), 0.0)
    valid = bool(
        road_id
        and _present(expected_crown)
        and _present(actual_crown)
        and _present(expected_cross)
        and _present(actual_cross)
        and _present(expected_left_cross)
        and _present(actual_left_cross)
        and _present(expected_right_cross)
        and _present(actual_right_cross)
        and abs(safe_float(actual_crown, 0.0) - safe_float(expected_crown, 0.0)) <= crown_tolerance
        and abs(safe_float(actual_cross, 0.0) - safe_float(expected_cross, 0.0)) <= slope_tolerance
        and abs(safe_float(actual_left_cross, 0.0) - safe_float(expected_left_cross, 0.0)) <= slope_tolerance
        and abs(safe_float(actual_right_cross, 0.0) - safe_float(expected_right_cross, 0.0)) <= slope_tolerance
        and _has_accepted_standard(rec)
        and _row_is_production_evidence(rec)
    )
    return {
        "road_id": road_id,
        "profile_id": safe_str(rec.get("profile_id")),
        "expected_crown_elev_ft": expected_crown,
        "actual_crown_elev_ft": actual_crown,
        "expected_cross_slope": expected_cross,
        "actual_cross_slope": actual_cross,
        "expected_left_cross_slope": expected_left_cross,
        "actual_left_cross_slope": actual_left_cross,
        "expected_right_cross_slope": expected_right_cross,
        "actual_right_cross_slope": actual_right_cross,
        "crown_tolerance_ft": crown_tolerance,
        "cross_slope_tolerance": slope_tolerance,
        "standard_id": safe_str(rec.get("standard_id") or rec.get("standard")),
        "valid": valid,
    }


def _roadway_gutter_expected_actual(row: Dict[str, Any]) -> Dict[str, Any]:
    rec = safe_dict(row)
    road_id = safe_str(rec.get("road_id") or rec.get("alignment_id") or rec.get("road") or rec.get("alignment"))
    expected_min = rec.get("expected_min_gutter_slope", rec.get("min_gutter_slope"))
    actual = rec.get("actual_gutter_slope", rec.get("gutter_slope"))
    valid = bool(
        road_id
        and _present(expected_min)
        and _present(actual)
        and safe_float(actual, -1.0) >= safe_float(expected_min, 0.0)
        and _has_accepted_standard(rec)
        and _row_is_production_evidence(rec)
    )
    return {
        "road_id": road_id,
        "alignment_id": safe_str(rec.get("alignment_id")),
        "expected_min_gutter_slope": expected_min,
        "actual_gutter_slope": actual,
        "flow_direction": rec.get("flow_direction"),
        "standard_id": safe_str(rec.get("standard_id") or rec.get("standard")),
        "valid": valid,
    }


def _roadway_ada_expected_actual(row: Dict[str, Any]) -> Dict[str, Any]:
    rec = safe_dict(row)
    expected_running = rec.get("expected_max_running_slope", rec.get("max_running_slope"))
    actual_running = rec.get("actual_running_slope", rec.get("running_slope"))
    expected_cross = rec.get("expected_max_cross_slope", rec.get("max_cross_slope"))
    actual_cross = rec.get("actual_cross_slope", rec.get("cross_slope"))
    continuity = safe_dict(rec.get("continuity_validation") or rec.get("continuity_check"))
    continuity_ok = continuity.get("valid") is not False and rec.get("continuous") is not False
    valid = bool(
        rec.get("valid") is True
        and _present(expected_running)
        and _present(actual_running)
        and _present(expected_cross)
        and _present(actual_cross)
        and safe_float(actual_running, 1.0) <= safe_float(expected_running, 0.0)
        and safe_float(actual_cross, 1.0) <= safe_float(expected_cross, 0.0)
        and continuity_ok
        and _has_accepted_standard(rec)
        and _row_is_production_evidence(rec)
    )
    return {
        "path_id": safe_str(rec.get("path_id") or rec.get("path") or rec.get("id")),
        "expected_max_running_slope": expected_running,
        "actual_running_slope": actual_running,
        "expected_max_cross_slope": expected_cross,
        "actual_cross_slope": actual_cross,
        "continuous": continuity_ok,
        "standard_id": safe_str(rec.get("standard_id") or rec.get("standard")),
        "valid": valid,
    }


def _roadway_pad_tie_expected_actual(row: Dict[str, Any], surface_trace: Dict[str, Any]) -> Dict[str, Any]:
    rec = safe_dict(row)
    expected_surface = safe_str(surface_trace.get("proposed_surface_id"))
    actual_surface = safe_str(rec.get("proposed_surface_id") or rec.get("surface_id") or rec.get("accepted_surface_id"))
    expected_max_tie_slope = rec.get("expected_max_tie_slope", rec.get("max_tie_slope"))
    actual_tie_slope = rec.get("actual_tie_slope", rec.get("tie_slope"))
    slope_ok = True
    if _present(expected_max_tie_slope) or _present(actual_tie_slope):
        slope_ok = bool(
            _present(expected_max_tie_slope)
            and _present(actual_tie_slope)
            and safe_float(actual_tie_slope, 1.0) <= safe_float(expected_max_tie_slope, 0.0)
        )
    valid = bool(
        rec.get("valid") is True
        and safe_str(rec.get("building") or rec.get("building_id"))
        and _present(rec.get("pad_elev_ft") or rec.get("actual_pad_elev_ft"))
        and rec.get("positive_drainage") is not False
        and slope_ok
        and surface_trace.get("valid") is True
        and actual_surface
        and actual_surface == expected_surface
        and _row_is_production_evidence(rec)
    )
    return {
        "building_id": safe_str(rec.get("building_id") or rec.get("building")),
        "expected_proposed_surface_id": expected_surface,
        "actual_proposed_surface_id": actual_surface,
        "pad_elev_ft": rec.get("pad_elev_ft", rec.get("actual_pad_elev_ft")),
        "positive_drainage": rec.get("positive_drainage"),
        "expected_max_tie_slope": expected_max_tie_slope,
        "actual_tie_slope": actual_tie_slope,
        "tie_in_elevations_ft": safe_list(rec.get("tie_in_elevations_ft") or rec.get("tie_elevations_ft")),
        "valid": valid,
    }


def _roadway_contour_expected_actual(row: Dict[str, Any], surface_trace: Dict[str, Any]) -> Dict[str, Any]:
    rec = safe_dict(row)
    expected_surface = safe_str(surface_trace.get("proposed_surface_id"))
    actual_surface = safe_str(rec.get("proposed_surface_id") or rec.get("surface_id") or rec.get("accepted_surface_id"))
    interval = rec.get("interval_ft")
    sample_values = safe_list(rec.get("sample_elevations_ft") or rec.get("sample_values") or rec.get("contour_values_ft"))
    if "actual_contour_count" in rec:
        actual_count = rec.get("actual_contour_count")
    else:
        actual_count = rec.get("contour_count", len(sample_values))
    expected_min_count = rec.get("expected_min_contour_count", rec.get("expected_min_sample_count"))
    count_ok = True
    if _present(expected_min_count):
        count_ok = safe_float(actual_count, 0.0) >= safe_float(expected_min_count, 0.0)
    valid = bool(
        surface_trace.get("valid") is True
        and actual_surface
        and actual_surface == expected_surface
        and safe_float(interval, 0.0) > 0.0
        and count_ok
        and _row_is_production_evidence(rec)
    )
    return {
        "contour_id": safe_str(rec.get("contour_id") or rec.get("id") or rec.get("contour_index")),
        "expected_proposed_surface_id": expected_surface,
        "actual_proposed_surface_id": actual_surface,
        "expected_interval_ft": surface_trace.get("contour_interval_ft", rec.get("expected_interval_ft")),
        "actual_interval_ft": interval,
        "expected_min_contour_count": expected_min_count,
        "actual_contour_count": actual_count,
        "sample_elevations_ft": sample_values,
        "valid": valid,
    }


def _grading_surface_source_expected_actual(grading: Dict[str, Any], surface_trace: Dict[str, Any]) -> Dict[str, Any]:
    proposed_surface = safe_dict(grading.get("proposed_surface"))
    source = safe_str(
        grading.get("proposed_surface_source")
        or proposed_surface.get("source")
        or safe_dict(grading.get("grading_source")).get("source_status")
    )
    confidence = grading.get("proposed_surface_confidence", proposed_surface.get("confidence"))
    confidence_value = safe_float(confidence, -1.0) if isinstance(confidence, (int, float)) else -1.0
    confidence_text = safe_str(confidence).lower()
    confidence_valid = bool(confidence_value >= 0.75 or confidence_text in {"high", "accepted", "calculated_from_accepted_surfaces"})
    return {
        "expected_existing_surface_id": surface_trace.get("existing_surface_id"),
        "actual_existing_surface_id": surface_trace.get("existing_surface_id"),
        "expected_proposed_surface_id": surface_trace.get("proposed_surface_id"),
        "actual_proposed_surface_id": surface_trace.get("proposed_surface_id"),
        "proposed_surface_source": source,
        "proposed_surface_confidence": confidence,
        "valid": bool(surface_trace.get("valid") is True and source and confidence_valid and not _text_has_concept_marker(source)),
    }


def _grading_cut_fill_expected_actual(grading: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
    earthwork = safe_dict(grading.get("earthwork") or meta.get("earthwork") or meta.get("earthwork_summary"))
    expected_cut = earthwork.get("expected_cut_cf")
    actual_cut = earthwork.get("actual_cut_cf")
    expected_fill = earthwork.get("expected_fill_cf")
    actual_fill = earthwork.get("actual_fill_cf")
    expected_net = earthwork.get("expected_net_cf")
    actual_net = earthwork.get("actual_net_cf")
    tolerance = safe_float(earthwork.get("volume_tolerance_cf"), 0.0)
    valid = bool(
        _present(expected_cut)
        and _present(actual_cut)
        and _present(expected_fill)
        and _present(actual_fill)
        and _present(expected_net)
        and _present(actual_net)
        and abs(safe_float(actual_cut, 0.0) - safe_float(expected_cut, 0.0)) <= tolerance
        and abs(safe_float(actual_fill, 0.0) - safe_float(expected_fill, 0.0)) <= tolerance
        and abs(safe_float(actual_net, 0.0) - safe_float(expected_net, 0.0)) <= tolerance
        and _row_is_production_evidence(earthwork)
    )
    return {
        "expected_cut_cf": expected_cut,
        "actual_cut_cf": actual_cut,
        "expected_fill_cf": expected_fill,
        "actual_fill_cf": actual_fill,
        "expected_net_cf": expected_net,
        "actual_net_cf": actual_net,
        "volume_tolerance_cf": tolerance,
        "source_surface_ids": safe_list(earthwork.get("source_surface_ids")),
        "valid": valid,
    }


def _grading_slope_expected_actual(grading: Dict[str, Any]) -> Dict[str, Any]:
    slope = safe_dict(grading.get("slope_summary") or grading.get("surface_controls"))
    expected_min = slope.get("expected_min_slope", slope.get("min_required_slope"))
    actual_min = slope.get("actual_min_slope", slope.get("min_slope"))
    expected_max = slope.get("expected_max_slope", slope.get("max_allowed_slope"))
    actual_max = slope.get("actual_max_slope", slope.get("max_slope"))
    expected_average = slope.get("expected_average_slope")
    actual_average = slope.get("actual_average_slope", slope.get("average_slope"))
    valid = bool(
        _present(expected_min)
        and _present(actual_min)
        and _present(expected_max)
        and _present(actual_max)
        and _present(expected_average)
        and _present(actual_average)
        and safe_float(actual_min, -1.0) >= safe_float(expected_min, 0.0)
        and safe_float(actual_max, 1.0) <= safe_float(expected_max, 0.0)
        and _row_is_production_evidence(slope)
    )
    return {
        "expected_min_slope": expected_min,
        "actual_min_slope": actual_min,
        "expected_max_slope": expected_max,
        "actual_max_slope": actual_max,
        "expected_average_slope": expected_average,
        "actual_average_slope": actual_average,
        "valid": valid,
    }


def _grading_repair_expected_actual(grading: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for index, row in enumerate(safe_list(grading.get("drainage_aware_repairs") or grading.get("grading_repairs"))):
        rec = safe_dict(row)
        before = safe_dict(rec.get("before"))
        after = safe_dict(rec.get("after"))
        rows.append(
            {
                "repair_id": safe_str(rec.get("repair_id") or rec.get("id"), f"repair-{index + 1}"),
                "expected_valid": True,
                "actual_valid": rec.get("valid"),
                "reason": safe_str(rec.get("reason") or rec.get("why")),
                "drainage_evidence_id": safe_str(rec.get("drainage_evidence_id") or rec.get("drainage_id")),
                "before_low_point_count": before.get("low_point_count"),
                "after_low_point_count": after.get("low_point_count"),
                "before_min_slope": before.get("min_slope"),
                "after_min_slope": after.get("min_slope"),
                "valid": bool(
                    rec.get("valid") is True
                    and safe_str(rec.get("reason") or rec.get("why"))
                    and safe_str(rec.get("drainage_evidence_id") or rec.get("drainage_id"))
                    and bool(before)
                    and bool(after)
                    and _row_is_production_evidence(rec)
                ),
            }
        )
    return rows


def _grading_retaining_wall_expected_actual(grading: Dict[str, Any], meta: Dict[str, Any], surface_trace: Dict[str, Any]) -> Dict[str, Any]:
    walls = safe_list(grading.get("retaining_walls") or meta.get("retaining_walls"))
    checks = [safe_dict(row) for row in safe_list(grading.get("wall_tie_in_checks") or meta.get("wall_tie_in_checks"))]
    if not walls:
        return {"required": False, "valid": True, "status": "not_required"}
    valid_checks = [
        row
        for row in checks
        if row.get("valid") is True
        and safe_str(row.get("wall_id") or row.get("retaining_wall_id"))
        and safe_str(row.get("proposed_surface_id") or row.get("surface_id")) == safe_str(surface_trace.get("proposed_surface_id"))
        and _present(row.get("top_tie_elev_ft"))
        and _present(row.get("bottom_tie_elev_ft"))
        and _row_is_production_evidence(row)
    ]
    return {
        "required": True,
        "wall_count": len(walls),
        "tie_in_check_count": len(checks),
        "valid_tie_in_check_count": len(valid_checks),
        "expected_proposed_surface_id": surface_trace.get("proposed_surface_id"),
        "valid": len(valid_checks) >= len(walls),
    }


def _canonical_alignment_id(row: Dict[str, Any]) -> str:
    rec = safe_dict(row)
    for key in ("canonical_alignment_id", "alignment_id", "canonical_id", "id", "name"):
        value = safe_str(rec.get(key))
        if value:
            return value
    return ""


def _profile_alignment_id(row: Dict[str, Any]) -> str:
    rec = safe_dict(row)
    for key in ("canonical_alignment_id", "alignment_id", "alignment_owner_id", "alignment_ref", "alignment_name", "alignment_owner"):
        value = safe_str(rec.get(key))
        if value:
            return value
    return ""


def _surface_traceability(meta: Dict[str, Any]) -> Dict[str, Any]:
    grading = safe_dict(meta.get("grading") or meta.get("grading_summary"))
    trace = safe_dict(
        meta.get("surface_traceability")
        or grading.get("surface_traceability")
        or safe_dict(meta.get("earthwork") or meta.get("earthwork_summary")).get("surface_traceability")
    )
    existing_id = safe_str(
        trace.get("existing_surface_id")
        or grading.get("existing_surface_id")
        or meta.get("existing_surface_id")
        or safe_dict(grading.get("existing_surface")).get("id")
    )
    proposed_id = safe_str(
        trace.get("proposed_surface_id")
        or grading.get("proposed_surface_id")
        or meta.get("proposed_surface_id")
        or safe_dict(grading.get("proposed_surface")).get("id")
    )
    accepted = bool(
        trace.get("valid") is True
        or trace.get("accepted_surfaces") is True
        or grading.get("accepted_surfaces") is True
        or meta.get("accepted_surfaces") is True
    )
    missing = [
        name
        for name, ok in (
            ("accepted_surfaces", accepted),
            ("existing_surface_id", bool(existing_id)),
            ("proposed_surface_id", bool(proposed_id)),
        )
        if not ok
    ]
    return {
        "valid": not missing,
        "accepted_surfaces": accepted,
        "existing_surface_id": existing_id,
        "proposed_surface_id": proposed_id,
        "missing_inputs": missing,
        "truth_label": "Profile/section surface traceability requires accepted existing and proposed surface IDs.",
    }


def _section_surface_id(row: Dict[str, Any], key: str, trace: Dict[str, Any]) -> str:
    rec = safe_dict(row)
    if key == "existing":
        return safe_str(rec.get("existing_surface_id") or rec.get("eg_surface_id") or trace.get("existing_surface_id"))
    return safe_str(rec.get("proposed_surface_id") or rec.get("fg_surface_id") or trace.get("proposed_surface_id"))


def _profile_band_rows(profiles: Iterable[Dict[str, Any]], explicit_bands: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for band in explicit_bands:
        rec = safe_dict(band)
        if rec:
            rows.append(rec)
    for profile in profiles:
        profile_rec = safe_dict(profile)
        profile_system = safe_str(profile_rec.get("source_system") or profile_rec.get("alignment_type"))
        for band in safe_list(profile_rec.get("profile_bands") or profile_rec.get("pipe_band_records") or profile_rec.get("bands")):
            rec = safe_dict(band)
            if not rec:
                continue
            if profile_system and not safe_str(rec.get("system") or rec.get("source_system") or rec.get("utility_type")):
                rec = {**rec, "source_system": profile_system}
            rows.append(rec)
    return rows


def _required_profile_band_systems(meta: Dict[str, Any]) -> List[str]:
    systems: List[str] = []
    storm = safe_dict(meta.get("storm_pipes") or meta.get("storm_pipe_summary"))
    sanitary = safe_dict(meta.get("sanitary") or meta.get("sanitary_summary"))
    utilities = safe_dict(meta.get("utilities") or meta.get("utility_summary") or meta.get("water") or meta.get("water_summary"))
    if safe_list(storm.get("segments")):
        systems.append("storm")
    if safe_list(sanitary.get("segments")):
        systems.append("sanitary")
    hooks = safe_dict(utilities.get("conflict_hooks"))
    if safe_list(utilities.get("segments") or hooks.get("utility_segments")):
        systems.append("water")
    return systems


def _band_system(row: Dict[str, Any]) -> str:
    system = safe_str(row.get("system") or row.get("source_system") or row.get("utility_type") or row.get("alignment_type")).lower()
    if system in {"storm_pipe", "stormwater"}:
        return "storm"
    if system in {"sanitary_pipe", "sewer"}:
        return "sanitary"
    if system in {"water", "fire_water", "utility", "utilities"}:
        return "water"
    return system


def _has_retaining_wall_scope(meta: Dict[str, Any]) -> bool:
    structures = safe_dict(meta.get("structures") or meta.get("structure_summary"))
    grading = safe_dict(meta.get("grading") or meta.get("grading_summary"))
    return bool(
        safe_list(meta.get("retaining_walls"))
        or safe_list(structures.get("retaining_walls"))
        or safe_list(grading.get("retaining_walls"))
    )


def _is_wall_section(row: Dict[str, Any]) -> bool:
    rec = safe_dict(row)
    source = safe_str(rec.get("source_system") or rec.get("alignment_type") or rec.get("section_type") or rec.get("ownership_class")).lower()
    return bool(
        safe_str(rec.get("retaining_wall_id") or rec.get("wall_id"))
        or "retaining" in source
        or "wall" in source
    )


def validate_profile_section_depth(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else safe_dict(plan_or_meta)
    alignments = [safe_dict(row) for row in safe_list(meta.get("alignments") or meta.get("road_alignments")) if safe_dict(row)]
    profiles = [safe_dict(row) for row in safe_list(meta.get("profiles") or meta.get("road_profiles")) if safe_dict(row)]
    sections = [safe_dict(row) for row in safe_list(meta.get("cross_sections") or meta.get("corridor_sections")) if safe_dict(row)]
    surface_trace = _surface_traceability(meta)
    canonical_alignment_ids = sorted({value for value in (_canonical_alignment_id(row) for row in alignments) if value})

    profile_trace_checks: List[Dict[str, Any]] = []
    for profile in profiles:
        profile_id = safe_str(profile.get("name") or profile.get("id"), "profile")
        alignment_id = _profile_alignment_id(profile)
        samples = safe_list(profile.get("profile_points") or profile.get("stations") or profile.get("points") or profile.get("samples"))
        valid = bool(alignment_id and alignment_id in canonical_alignment_ids and len(samples) >= 2)
        profile_trace_checks.append(
            {
                "profile": profile_id,
                "expected_alignment_ids": canonical_alignment_ids,
                "actual_alignment_id": alignment_id,
                "sample_count": len(samples),
                "valid": valid,
            }
        )

    section_trace_checks: List[Dict[str, Any]] = []
    for section in sections:
        section_id = safe_str(section.get("name") or section.get("id"), "section")
        alignment_id = _profile_alignment_id(section)
        samples = safe_list(section.get("section_points") or section.get("samples") or section.get("points"))
        existing_id = _section_surface_id(section, "existing", surface_trace)
        proposed_id = _section_surface_id(section, "proposed", surface_trace)
        valid = bool(
            alignment_id
            and alignment_id in canonical_alignment_ids
            and len(samples) >= 3
            and surface_trace.get("valid") is True
            and existing_id == surface_trace.get("existing_surface_id")
            and proposed_id == surface_trace.get("proposed_surface_id")
        )
        section_trace_checks.append(
            {
                "section": section_id,
                "expected_alignment_ids": canonical_alignment_ids,
                "actual_alignment_id": alignment_id,
                "expected_existing_surface_id": surface_trace.get("existing_surface_id"),
                "actual_existing_surface_id": existing_id,
                "expected_proposed_surface_id": surface_trace.get("proposed_surface_id"),
                "actual_proposed_surface_id": proposed_id,
                "sample_count": len(samples),
                "valid": valid,
            }
        )

    required_band_systems = _required_profile_band_systems(meta)
    band_rows = _profile_band_rows(profiles, safe_list(meta.get("profile_bands")))
    band_checks = []
    for system in required_band_systems:
        matching = [row for row in band_rows if _band_system(row) == system]
        band_checks.append(
            {
                "system": system,
                "expected": "profile_band_row_present",
                "actual_count": len(matching),
                "valid": bool(matching),
            }
        )

    wall_scope = _has_retaining_wall_scope(meta)
    wall_sections = [row for row in sections if _is_wall_section(row)]
    wall_tie_in_checks = [
        safe_dict(row)
        for row in safe_list(meta.get("wall_tie_in_checks") or safe_dict(meta.get("structures") or meta.get("structure_summary")).get("wall_tie_in_checks"))
        if safe_dict(row)
    ]
    wall_valid = not wall_scope or bool(wall_sections and any(row.get("valid") is not False for row in wall_tie_in_checks + wall_sections))
    wall_check = {
        "scope_required": wall_scope,
        "wall_section_count": len(wall_sections),
        "tie_in_check_count": len(wall_tie_in_checks),
        "valid": wall_valid,
    }

    export_audit = safe_dict(meta.get("export_audit"))
    requested = safe_dict(export_audit.get("requested_vs_produced"))
    requested_profiles_missing = bool(requested.get("missing_requested_profiles"))
    requested_sections_missing = bool(requested.get("missing_requested_sections"))
    export_linkage_required = bool(export_audit) or bool(requested)
    export_linkage = {
        "required": export_linkage_required,
        "expected_profile_count": len(profiles),
        "actual_export_profile_count": safe_float(export_audit.get("canonical_profile_count"), len(profiles)) if export_audit else len(profiles),
        "expected_section_count": len(sections),
        "actual_export_section_count": safe_float(export_audit.get("canonical_cross_section_count"), len(sections)) if export_audit else len(sections),
        "missing_requested_profiles": requested_profiles_missing,
        "missing_requested_sections": requested_sections_missing,
    }
    export_linkage["valid"] = bool(
        not requested_profiles_missing
        and not requested_sections_missing
        and (not export_audit or safe_float(export_linkage["actual_export_profile_count"], 0.0) >= len(profiles))
        and (not export_audit or safe_float(export_linkage["actual_export_section_count"], 0.0) >= len(sections))
    )

    checks = [
        _check("canonical_alignments", bool(canonical_alignment_ids), evidence="canonical alignment IDs", blocker="Profile/section depth needs canonical alignment IDs."),
        _check("profiles", bool(profiles), evidence="profile rows", blocker="Profile/section depth needs profile rows."),
        _check("profiles_trace_alignments", bool(profile_trace_checks) and all(row["valid"] for row in profile_trace_checks), evidence="profiles trace canonical alignments", blocker="Profile/section depth needs every profile to trace a canonical alignment ID."),
        _check("accepted_surfaces", surface_trace.get("valid") is True, evidence="accepted surface IDs", blocker="Profile/section depth needs accepted existing/proposed surface IDs."),
        _check("sections", bool(sections), evidence="cross-section rows", blocker="Profile/section depth needs cross-section rows."),
        _check("sections_trace_surfaces", bool(section_trace_checks) and all(row["valid"] for row in section_trace_checks), evidence="sections trace accepted surfaces", blocker="Profile/section depth needs sections tied to accepted surface IDs."),
        _check("profile_bands", all(row["valid"] for row in band_checks), evidence="utility/storm/sanitary profile bands", blocker="Profile/section depth needs profile band rows for existing storm, sanitary, and water systems."),
        _check("retaining_wall_sections", wall_check["valid"], evidence="retaining wall section/tie-in evidence", blocker="Profile/section depth needs retaining wall section and tie-in evidence when wall scope exists."),
        _check("export_linkage", export_linkage["valid"], evidence="export profile/section linkage", blocker="Profile/section depth needs export/profile-section linkage when profile or section deliverables are requested."),
    ]
    result = _finalize("profile_section_depth", checks)
    result.update(
        {
            "profile_trace_checks": profile_trace_checks,
            "section_trace_checks": section_trace_checks,
            "surface_traceability": surface_trace,
            "profile_band_checks": band_checks,
            "retaining_wall_section_check": wall_check,
            "export_linkage": export_linkage,
            "expected_actual_checks": profile_trace_checks + section_trace_checks + band_checks + [wall_check, export_linkage],
        }
    )
    return result


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
    required_storage = safe_float(rec.get("required_storage_cf"), 0.0)
    max_drawdown = safe_float(rec.get("max_drawdown_hours"), 0.0)
    if required_storage > 0.0 and provided_storage < required_storage:
        return False
    if max_drawdown > 0.0 and drawdown > max_drawdown:
        return False
    return (has_stage_storage or provided_storage > 0.0) and has_outlet and release > 0.0 and drawdown > 0.0


def _valid_flag(value: Any) -> bool:
    return safe_dict(value).get("valid") is True


def _has_valid_overflow_routing(drainage: Dict[str, Any], storm: Dict[str, Any]) -> bool:
    paths = safe_list(drainage.get("overflow_paths") or storm.get("overflow_paths"))
    overflow_analysis = safe_dict(drainage.get("overflow_analysis"))
    storm_overflow = safe_dict(storm.get("overflow_analysis"))
    terrain_evidence = safe_dict(overflow_analysis.get("terrain_evidence") or storm_overflow.get("terrain_evidence") or drainage.get("terrain_evidence") or drainage.get("surface_controls"))
    if overflow_analysis:
        if overflow_analysis.get("production_valid") is True:
            return bool(paths and terrain_evidence)
        if overflow_analysis.get("valid") is False:
            return False
        if "production_valid" in overflow_analysis or safe_str(overflow_analysis.get("capacity_status")):
            return False
    if storm_overflow:
        if storm_overflow.get("production_valid") is True:
            return bool(paths and terrain_evidence)
        if storm_overflow.get("valid") is False:
            return False
    return any(
        safe_dict(path).get("capacity_valid") is True
        and safe_float(safe_dict(path).get("capacity_cfs") or safe_dict(path).get("spillway_capacity_cfs"), 0.0)
        >= safe_float(safe_dict(path).get("required_capacity_cfs"), 0.0)
        and _row_is_production_evidence(safe_dict(path))
        and bool(terrain_evidence)
        for path in paths
    )


def _has_valid_drainage_target(storm: Dict[str, Any], drainage: Dict[str, Any]) -> bool:
    validation = safe_dict(storm.get("drainage_target_validation") or drainage.get("drainage_target_validation"))
    if validation:
        return validation.get("valid") is True
    target = safe_dict(storm.get("target_outfall") or storm.get("outfall_target_metadata") or safe_dict(drainage.get("coordination")).get("preferred_outfall"))
    basins = safe_list(drainage.get("basins") or storm.get("basins"))
    return bool(target or basins)


def _storm_hgl_egl_expected_actual(storm: Dict[str, Any], hgl_rows: List[Dict[str, Any]], egl_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    profile_evidence = safe_dict(storm.get("hydraulic_profile_evidence"))
    valid = bool(hgl_rows and egl_rows and ((_has_production_rows(hgl_rows) and _has_production_rows(egl_rows)) or storm.get("hydraulic_source") == "engine"))
    return {
        "expected": "production_hgl_and_egl_profile_rows",
        "actual_hgl_count": len(hgl_rows),
        "actual_egl_count": len(egl_rows),
        "hydraulic_source": safe_str(storm.get("hydraulic_source")),
        "confidence": safe_str(profile_evidence.get("confidence")),
        "confidence_labels": safe_list(profile_evidence.get("labels")),
        "missing_profile_inputs": safe_list(profile_evidence.get("missing_profile_inputs")),
        "valid": valid,
    }


def _storm_tailwater_expected_actual(storm: Dict[str, Any]) -> Dict[str, Any]:
    tailwater = storm.get("tailwater_elev_ft")
    backwater = safe_dict(storm.get("backwater_validation"))
    return {
        "expected": "tailwater_elev_ft_present_with_backwater_context",
        "actual_tailwater_elev_ft": tailwater,
        "backwater_valid": backwater.get("valid"),
        "tailwater_controls_hgl": backwater.get("tailwater_controls_hgl"),
        "valid": _present(tailwater),
    }


def _storm_inlet_expected_actual(inlet_checks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for index, inlet in enumerate(inlet_checks):
        rows.append(
            {
                "inlet": safe_str(inlet.get("inlet") or inlet.get("name") or inlet.get("id"), f"inlet-{index + 1}"),
                "expected_valid": True,
                "actual_valid": inlet.get("valid"),
                "expected_bypass_cfs": 0.0,
                "actual_bypass_cfs": safe_float(inlet.get("bypass_cfs"), 0.0),
                "expected_spread_lte_ft": safe_float(inlet.get("spread_limit_ft"), safe_float(inlet.get("gutter_spread_limit_ft"), 0.0)),
                "actual_spread_ft": safe_float(inlet.get("spread_ft"), 0.0),
                "valid": inlet.get("valid") is True,
            }
        )
    return rows


def _storm_detention_expected_actual(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    for index, row in enumerate(rows):
        rec = safe_dict(row)
        checks.append(
            {
                "basin": safe_str(rec.get("basin") or rec.get("name"), f"basin-{index + 1}"),
                "expected_storage_cf": safe_float(rec.get("required_storage_cf"), 0.0),
                "actual_storage_cf": safe_float(rec.get("provided_storage_cf") or rec.get("storage_cf"), 0.0),
                "expected_release_cfs_gt": 0.0,
                "actual_release_cfs": max(safe_float(rec.get("release_cfs"), 0.0), safe_float(rec.get("outlet_release_cfs"), 0.0), safe_float(rec.get("outflow_cfs"), 0.0)),
                "expected_drawdown_hours_gt": 0.0,
                "actual_drawdown_hours": max(safe_float(rec.get("drawdown_hours"), 0.0), safe_float(rec.get("estimated_drawdown_hours"), 0.0), safe_float(rec.get("actual_drawdown_hours"), 0.0)),
                "valid": _has_valid_detention_routing(rec),
            }
        )
    return checks


def _storm_overflow_expected_actual(drainage: Dict[str, Any], storm: Dict[str, Any]) -> List[Dict[str, Any]]:
    paths = [safe_dict(path) for path in safe_list(drainage.get("overflow_paths") or storm.get("overflow_paths")) if safe_dict(path)]
    rows: List[Dict[str, Any]] = []
    for index, path in enumerate(paths):
        rows.append(
            {
                "path": safe_str(path.get("name") or path.get("id"), f"overflow-{index + 1}"),
                "expected_capacity_cfs": safe_float(path.get("required_capacity_cfs"), 0.0),
                "actual_capacity_cfs": safe_float(path.get("capacity_cfs") or path.get("spillway_capacity_cfs"), 0.0),
                "expected_capacity_valid": True,
                "actual_capacity_valid": path.get("capacity_valid"),
                "valid": path.get("capacity_valid") is True
                and safe_float(path.get("capacity_cfs") or path.get("spillway_capacity_cfs"), 0.0) >= safe_float(path.get("required_capacity_cfs"), 0.0),
            }
        )
    return rows


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


def _dead_end_nodes(segments: Iterable[Dict[str, Any]]) -> List[str]:
    degree: Dict[str, int] = defaultdict(int)
    for segment in segments:
        start, end = _segment_endpoints(segment)
        if not start or not end:
            continue
        degree[start] += 1
        degree[end] += 1
    return sorted(node for node, count in degree.items() if count <= 1)


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
    hgl_egl_trace = _storm_hgl_egl_expected_actual(storm, hgl_rows, egl_rows)
    tailwater_trace = _storm_tailwater_expected_actual(storm)
    inlet_trace = _storm_inlet_expected_actual(inlet_checks)
    detention_trace = _storm_detention_expected_actual(detention_rows)
    overflow_trace = _storm_overflow_expected_actual(drainage, storm)
    checks = [
        _check("basin_outfall_target", _has_valid_drainage_target(storm, drainage), evidence="drainage basin/outfall target", blocker="Storm depth needs drainage-selected basin/outfall target evidence."),
        _check("tributary_areas", any(safe_float(seg.get("tributary_area_sf") or seg.get("upstream_cumulative_area_sf"), 0.0) > 0.0 for seg in segments) or bool(catchments), evidence="tributary areas/catchments", blocker="Storm depth needs true tributary areas tied to pipes or catchments."),
        _check("runoff_coefficients", any(_present(safe_dict(item).get("runoff_c") or safe_dict(item).get("runoff_coefficient")) for item in catchments) or _present(drainage.get("runoff_coefficient")), evidence="runoff coefficients", blocker="Storm depth needs runoff coefficients by catchment/surface."),
        _check("hgl_egl_profiles", hgl_egl_trace["valid"], evidence="HGL/EGL profile rows", blocker="Storm depth needs HGL and EGL profiles from production hydraulic evidence."),
        _check("tailwater", tailwater_trace["valid"], evidence="tailwater elevation", blocker="Storm depth needs tailwater/backwater evidence."),
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
    result = _finalize("stormwater_depth", checks)
    result.update(
        {
            "hgl_egl_trace": hgl_egl_trace,
            "tailwater_backwater_trace": tailwater_trace,
            "inlet_capacity_trace": inlet_trace,
            "detention_routing_trace": detention_trace,
            "overflow_capacity_trace": overflow_trace,
            "expected_actual_checks": [hgl_egl_trace, tailwater_trace, *inlet_trace, *detention_trace, *overflow_trace],
        }
    )
    return result


def validate_water_system_depth(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else safe_dict(plan_or_meta)
    water = safe_dict(meta.get("water") or meta.get("water_summary"))
    utilities = safe_dict(meta.get("utilities") or meta.get("utility_summary"))
    source = water or utilities
    hooks = safe_dict(source.get("conflict_hooks"))
    segments = [safe_dict(item) for item in safe_list(source.get("water_segments") or source.get("segments") or hooks.get("utility_segments"))]
    hydrants = safe_list(source.get("hydrants") or source.get("fire_hydrants"))
    pressure = safe_dict(source.get("pressure_validation"))
    velocity_checks = safe_list(source.get("velocity_checks"))
    pressure_zone_validation = safe_dict(source.get("pressure_zone_validation"))
    owner_criteria = safe_dict(source.get("water_fire_flow_proof")).get("utility_owner_criteria") or source
    looped = bool(source.get("looped") or source.get("is_looped")) or _has_cycle(segments)
    dead_end_validation = safe_dict(source.get("dead_end_validation"))
    dead_ends = safe_list(dead_end_validation.get("dead_end_nodes")) if dead_end_validation else _dead_end_nodes(segments)
    no_dead_ends = dead_end_validation.get("valid") is True if dead_end_validation else not dead_ends
    checks = [
        _check(
            "pressure_zones",
            pressure_zone_validation.get("valid") is True,
            evidence="pressure zones",
            blocker="Water depth needs accepted pressure-zone evidence tied to source pressure.",
        ),
        _check(
            "utility_owner_criteria",
            safe_dict(owner_criteria).get("utility_owner_criteria_accepted") is True,
            evidence="utility owner criteria",
            blocker="Water depth needs accepted utility-owner water/fire-flow criteria.",
        ),
        _check("hydrant_spacing", bool(hydrants and _has_valid_hydrant_spacing(source.get("hydrant_spacing_validation"))), evidence="hydrant spacing evidence", blocker="Water depth needs passing hydrant spacing coverage."),
        _check("fire_flow", _has_valid_fire_flow_validation(source.get("fire_flow_validation"), pressure), evidence="fire flow validation", blocker="Water depth needs passing fire-flow validation."),
        _check("looping", looped, evidence="looped network graph", blocker="Water depth needs looping/redundancy evidence."),
        _check("dead_ends", no_dead_ends, evidence="no dead-end water nodes", blocker="Water depth needs no unresolved dead-end mains."),
        _check("pressure_validation", _has_valid_pressure_validation(pressure), evidence="pressure validation", blocker="Water depth needs passing pressure validation."),
        _check("velocity_checks", bool(velocity_checks) and all(_has_valid_velocity(safe_dict(item)) for item in velocity_checks), evidence="velocity checks", blocker="Water depth needs passing velocity checks."),
        _check("sizing_optimization", _has_valid_sizing_optimization(source.get("sizing_optimization")) or bool(safe_list(source.get("sizing_alternatives"))), evidence="sizing optimization", blocker="Water depth needs sizing optimization evidence."),
    ]
    return _finalize("water_system_depth", checks)


def validate_grading_depth(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else safe_dict(plan_or_meta)
    grading = _combined_grading_detail(meta)
    surface_trace = _surface_traceability(meta)
    surface_trace["contour_interval_ft"] = grading.get("contour_interval_ft")
    surface_source_trace = _grading_surface_source_expected_actual(grading, surface_trace)
    cut_fill_trace = _grading_cut_fill_expected_actual(grading, meta)
    slope_trace = _grading_slope_expected_actual(grading)
    ada_rows = [safe_dict(row) for row in safe_list(grading.get("ada_path_checks"))]
    ada_trace = [_roadway_ada_expected_actual(row) for row in ada_rows]
    pad_rows = [safe_dict(row) for row in safe_list(grading.get("pad_tie_ins") or meta.get("pad_tie_ins"))]
    pad_trace = [_roadway_pad_tie_expected_actual(row, surface_trace) for row in pad_rows]
    contour_rows = [safe_dict(row) for row in safe_list(grading.get("contours") or meta.get("contours"))]
    contour_trace = [_roadway_contour_expected_actual(row, surface_trace) for row in contour_rows]
    repair_trace = _grading_repair_expected_actual(grading)
    retaining_wall_trace = _grading_retaining_wall_expected_actual(grading, meta, surface_trace)
    checks = [
        _check("accepted_surfaces", surface_trace.get("valid") is True, evidence="accepted existing/proposed surface IDs", blocker="Grading depth needs accepted existing/proposed surface IDs."),
        _check("proposed_surface_source", surface_source_trace["valid"], evidence="proposed surface source/confidence", blocker="Grading depth needs proposed surface source and confidence evidence."),
        _check("cut_fill", cut_fill_trace["valid"], evidence="cut/fill expected/actual volumes", blocker="Grading depth needs cut/fill expected/actual volume evidence tied to accepted surfaces."),
        _check("slope_summary", slope_trace["valid"], evidence="slope expected/actual summary", blocker="Grading depth needs slope summary expected/actual evidence."),
        _check("ada_or_repair", (bool(ada_trace) and all(row["valid"] for row in ada_trace)) or (bool(repair_trace) and all(row["valid"] for row in repair_trace)), evidence="ADA path or drainage repair expected/actual evidence", blocker="Grading depth needs ADA path or drainage-aware repair expected/actual evidence."),
        _check("pad_tie_ins", bool(pad_trace) and all(row["valid"] for row in pad_trace), evidence="pad tie-in expected/actual evidence", blocker="Grading depth needs pad tie-in evidence tied to the accepted proposed surface."),
        _check("contours", bool(contour_trace) and all(row["valid"] for row in contour_trace), evidence="contour interval/count/sample evidence", blocker="Grading depth needs contour interval and sample/count evidence tied to the accepted proposed surface."),
        _check("drainage_aware_repairs", bool(repair_trace) and all(row["valid"] for row in repair_trace), evidence="drainage-aware grading repair evidence", blocker="Grading depth needs drainage-aware grading repair evidence."),
        _check("retaining_wall_tie_ins", retaining_wall_trace["valid"], evidence="retaining wall tie-in evidence or no wall scope", blocker="Grading depth needs retaining wall tie-in evidence when wall scope exists."),
    ]
    result = _finalize("grading_depth", checks)
    result.update(
        {
            "surface_traceability": surface_trace,
            "surface_source_trace": surface_source_trace,
            "cut_fill_trace": cut_fill_trace,
            "slope_trace": slope_trace,
            "ada_path_trace": ada_trace,
            "pad_tie_in_trace": pad_trace,
            "contour_trace": contour_trace,
            "drainage_repair_trace": repair_trace,
            "retaining_wall_trace": retaining_wall_trace,
            "expected_actual_checks": [
                surface_trace,
                surface_source_trace,
                cut_fill_trace,
                slope_trace,
                *ada_trace,
                *pad_trace,
                *contour_trace,
                *repair_trace,
                retaining_wall_trace,
            ],
        }
    )
    return result


def validate_roadway_corridor_depth(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else safe_dict(plan_or_meta)
    grading_detail = _combined_grading_detail(meta)
    crown_rows = [safe_dict(row) for row in safe_list(grading_detail.get("road_crown_controls") or meta.get("road_crowns"))]
    gutter_rows = [safe_dict(row) for row in safe_list(grading_detail.get("curb_gutter_controls") or meta.get("curb_gutter_controls"))]
    ada_rows = [safe_dict(row) for row in safe_list(grading_detail.get("ada_path_checks"))]
    pad_rows = [safe_dict(row) for row in safe_list(grading_detail.get("pad_tie_ins") or meta.get("pad_tie_ins"))]
    contour_rows = [safe_dict(row) for row in safe_list(grading_detail.get("contours") or meta.get("contours"))]
    ada_summary = safe_dict(meta.get("ada_compliance"))
    crown_trace = [_roadway_crown_expected_actual(row) for row in crown_rows]
    gutter_trace = [_roadway_gutter_expected_actual(row) for row in gutter_rows]
    ada_trace = [_roadway_ada_expected_actual(row) for row in ada_rows]
    surface_trace = _surface_traceability(meta)
    surface_trace["contour_interval_ft"] = grading_detail.get("contour_interval_ft")
    pad_trace = [_roadway_pad_tie_expected_actual(row, surface_trace) for row in pad_rows]
    contour_trace = [_roadway_contour_expected_actual(row, surface_trace) for row in contour_rows]
    ada_ready = any(row["valid"] for row in ada_trace) or _valid_flag(ada_summary)
    alignments = [safe_dict(row) for row in safe_list(meta.get("alignments") or meta.get("road_alignments"))]
    profiles = [safe_dict(row) for row in safe_list(meta.get("profiles") or meta.get("road_profiles"))]
    intersections = [safe_dict(row) for row in safe_list(meta.get("intersections"))]
    curb_returns = [safe_dict(row) for row in safe_list(meta.get("curb_returns"))]
    sidewalks = [safe_dict(row) for row in safe_list(meta.get("sidewalks") or meta.get("pedestrian_paths"))]
    sections = [safe_dict(row) for row in safe_list(meta.get("cross_sections") or meta.get("corridor_sections"))]
    checks = [
        _check("alignments", any(_has_valid_alignment(row) for row in alignments), evidence="road alignments", blocker="Roadway depth needs alignments."),
        _check("profiles", any(_has_valid_profile(row) for row in profiles), evidence="road profiles", blocker="Roadway depth needs profiles."),
        _check("intersections", any(_has_valid_intersection(row) for row in intersections), evidence="intersections", blocker="Roadway depth needs intersection geometry."),
        _check("curb_returns", any(_has_valid_curb_return(row) for row in curb_returns), evidence="curb returns", blocker="Roadway depth needs curb-return geometry."),
        _check("crowns", bool(crown_trace) and all(row["valid"] for row in crown_trace), evidence="road crown expected/actual controls", blocker="Roadway depth needs verified road crown controls with expected/actual crown and cross-slope values."),
        _check("curb_gutter", bool(gutter_trace) and all(row["valid"] for row in gutter_trace), evidence="curb/gutter expected/actual controls", blocker="Roadway depth needs curb/gutter controls tied to road or alignment IDs."),
        _check("sidewalks", any(_has_valid_sidewalk(row) for row in sidewalks), evidence="sidewalk/pedestrian paths", blocker="Roadway depth needs sidewalk/path geometry."),
        _check("ada", ada_ready, evidence="ADA compliance checks", blocker="Roadway depth needs passing ADA checks."),
        _check("sections", any(_has_valid_section(row) for row in sections), evidence="corridor sections", blocker="Roadway depth needs corridor sections."),
        _check("accepted_surfaces", surface_trace.get("valid") is True, evidence="accepted grading surface IDs", blocker="Roadway depth needs accepted grading surface traceability."),
        _check("pad_tie_ins", bool(pad_trace) and all(row["valid"] for row in pad_trace), evidence="pad tie-in expected/actual evidence", blocker="Roadway depth needs pad tie-ins tied to accepted proposed surface IDs."),
        _check("contours", bool(contour_trace) and all(row["valid"] for row in contour_trace), evidence="contour expected/actual evidence", blocker="Roadway depth needs contours tied to accepted proposed surface evidence."),
    ]
    result = _finalize("roadway_corridor_depth", checks)
    result.update(
        {
            "road_crown_trace": crown_trace,
            "curb_gutter_trace": gutter_trace,
            "ada_path_trace": ada_trace,
            "pad_tie_in_trace": pad_trace,
            "contour_trace": contour_trace,
            "surface_traceability": surface_trace,
            "expected_actual_checks": crown_trace + gutter_trace + ada_trace + pad_trace + contour_trace + [surface_trace],
        }
    )
    return result


__all__ = [
    "validate_grading_depth",
    "validate_profile_section_depth",
    "validate_roadway_corridor_depth",
    "validate_stormwater_depth",
    "validate_water_system_depth",
]
