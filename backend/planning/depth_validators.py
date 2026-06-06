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
    min_pressure = safe_float(rec.get("min_pressure_psi"), -1.0)
    required = safe_float(rec.get("min_required_pressure_psi"), 0.0)
    graph = safe_dict(rec.get("pressure_graph"))
    if graph:
        if graph.get("success") is not True or not safe_dict(graph.get("node_pressures_psi")):
            return False
    return source_pressure > 0.0 and required > 0.0 and min_pressure >= required and _has_accepted_standard(rec)


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
    return required > 0.0 and available >= required and residual >= min_required > 0.0 and has_residual_evidence and _has_accepted_standard(rec)


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
    checks = [
        _check("basin_outfall_target", _has_valid_drainage_target(storm, drainage), evidence="drainage basin/outfall target", blocker="Storm depth needs drainage-selected basin/outfall target evidence."),
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
    dead_end_validation = safe_dict(source.get("dead_end_validation"))
    dead_ends = safe_list(dead_end_validation.get("dead_end_nodes")) if dead_end_validation else _dead_end_nodes(segments)
    no_dead_ends = dead_end_validation.get("valid") is True if dead_end_validation else not dead_ends
    checks = [
        _check("pressure_zones", bool(safe_list(source.get("pressure_zones")) or safe_dict(source.get("pressure_zone"))), evidence="pressure zones", blocker="Water depth needs pressure zones."),
        _check("hydrant_spacing", bool(hydrants and _has_valid_hydrant_spacing(source.get("hydrant_spacing_validation"))), evidence="hydrant spacing evidence", blocker="Water depth needs passing hydrant spacing coverage."),
        _check("fire_flow", _has_valid_fire_flow_validation(source.get("fire_flow_validation"), pressure), evidence="fire flow validation", blocker="Water depth needs passing fire-flow validation."),
        _check("looping", looped, evidence="looped network graph", blocker="Water depth needs looping/redundancy evidence."),
        _check("dead_ends", no_dead_ends, evidence="no dead-end water nodes", blocker="Water depth needs no unresolved dead-end mains."),
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
    ada_ready = any(_has_valid_ada_check(row) for row in ada_rows) or _valid_flag(ada_summary)
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
        _check("crowns", any(_has_verified_crown(row) for row in crown_rows), evidence="road crown controls", blocker="Roadway depth needs verified road crown controls tied to a profile or standard."),
        _check("sidewalks", any(_has_valid_sidewalk(row) for row in sidewalks), evidence="sidewalk/pedestrian paths", blocker="Roadway depth needs sidewalk/path geometry."),
        _check("ada", ada_ready, evidence="ADA compliance checks", blocker="Roadway depth needs passing ADA checks."),
        _check("sections", any(_has_valid_section(row) for row in sections), evidence="corridor sections", blocker="Roadway depth needs corridor sections."),
    ]
    return _finalize("roadway_corridor_depth", checks)


__all__ = [
    "validate_profile_section_depth",
    "validate_roadway_corridor_depth",
    "validate_stormwater_depth",
    "validate_water_system_depth",
]
