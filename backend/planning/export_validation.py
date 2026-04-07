from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Dict, List, Optional

from core.geometry_core import ProjectModel

from backend.planning.common import (
    safe_dict,
    safe_float,
    safe_int,
    safe_list,
    safe_str,
)


def drainage_surface_alignment(
    grading: Dict[str, Any],
    drainage: Dict[str, Any],
) -> Dict[str, Any]:
    grading_low_points = [
        safe_dict(item) for item in safe_list(grading.get("low_points")) if safe_dict(item)
    ]
    drainage_low_points = [
        safe_dict(item) for item in safe_list(drainage.get("low_points")) if safe_dict(item)
    ]
    grading_stats = safe_dict(grading.get("stats"))
    threshold_ft = max(
        20.0,
        safe_float(safe_dict(grading.get("proposed_surface")).get("cell_size"), 0.0) * 8.0,
    )
    min_distance_ft: Optional[float] = None
    matched_pairs = 0

    if grading_low_points and drainage_low_points:
        remaining = list(drainage_low_points)
        for glp in grading_low_points[:4]:
            gx = safe_float(glp.get("x"), 0.0)
            gy = safe_float(glp.get("y"), 0.0)
            best_index = None
            best_distance = None
            for idx, dlp in enumerate(remaining):
                dx = safe_float(dlp.get("x"), 0.0)
                dy = safe_float(dlp.get("y"), 0.0)
                dist = math.hypot(dx - gx, dy - gy)
                if best_distance is None or dist < best_distance:
                    best_distance = dist
                    best_index = idx
            if best_distance is None:
                continue
            min_distance_ft = (
                best_distance
                if min_distance_ft is None
                else min(min_distance_ft, best_distance)
            )
            if best_distance <= threshold_ft and best_index is not None:
                matched_pairs += 1
                remaining.pop(best_index)

    return {
        "grading_low_point_count": len(grading_low_points),
        "drainage_low_point_count": len(drainage_low_points),
        "grading_flow_sample_count": safe_int(grading_stats.get("flow_sample_count"), 0),
        "threshold_ft": round(threshold_ft, 3),
        "matched_low_points": matched_pairs,
        "min_low_point_distance_ft": round(min_distance_ft, 3)
        if min_distance_ft is not None
        else None,
    }


def primary_engineered_basins(drainage: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    primary: List[Dict[str, Any]] = []
    for item in safe_list(safe_dict(drainage).get("basins")):
        rec = safe_dict(item)
        if not rec:
            continue
        if len(safe_list(rec.get("boundary_points"))) < 3:
            continue
        is_exportable = bool(rec.get("exportable"))
        engineering_role = safe_str(rec.get("engineering_role"))
        if engineering_role == "primary_detention" and is_exportable:
            primary.append(rec)
            continue
        canonical_type = safe_str(rec.get("canonical_type"))
        detention_design = safe_dict(rec.get("detention_design"))
        has_detention_design = bool(detention_design)
        has_overflow = bool(safe_dict(rec.get("overflow_spillway")))
        if (
            canonical_type == "detention_basin"
            or has_detention_design
            or has_overflow
        ):
            candidates.append(rec)
    if primary:
        return primary

    def _candidate_score(rec: Dict[str, Any]) -> tuple:
        detention_design = safe_dict(rec.get("detention_design"))
        geometry_quality = safe_dict(rec.get("geometry_quality"))
        adequacy = safe_str(detention_design.get("adequacy_status"), "adequate").lower()
        has_bottom = bool(geometry_quality.get("has_bottom"))
        consistency = safe_float(geometry_quality.get("footprint_consistency_ratio"), 0.0)
        return (
            1 if bool(rec.get("exportable")) else 0,
            1 if adequacy == "adequate" else 0,
            1 if bool(safe_dict(rec.get("overflow_spillway"))) else 0,
            1 if has_bottom else 0,
            round(consistency, 3),
            round(safe_float(rec.get("area_sf"), 0.0), 3),
        )

    candidates.sort(key=_candidate_score, reverse=True)
    return candidates


def detention_basin_score(rec: Dict[str, Any]) -> tuple:
    detention_design = safe_dict(rec.get("detention_design"))
    geometry_quality = safe_dict(rec.get("geometry_quality"))
    overflow = safe_dict(rec.get("overflow_spillway"))
    adequacy = safe_str(detention_design.get("adequacy_status"), "adequate").lower()
    has_bottom = bool(geometry_quality.get("has_bottom"))
    consistency = safe_float(geometry_quality.get("footprint_consistency_ratio"), 0.0)
    spillway_capacity = safe_float(overflow.get("assumed_capacity_cfs"), 0.0)
    return (
        1 if bool(rec.get("exportable")) else 0,
        1 if adequacy == "adequate" else 0,
        1 if spillway_capacity > 0.0 else 0,
        1 if has_bottom else 0,
        round(consistency, 3),
        round(safe_float(rec.get("storage_cf"), 0.0), 3),
        round(safe_float(rec.get("area_sf"), 0.0), 3),
    )


def basin_has_exportable_detention_geometry(rec: Dict[str, Any]) -> bool:
    item = safe_dict(rec)
    detention_design = safe_dict(item.get("detention_design"))
    geometry_quality = safe_dict(item.get("geometry_quality"))
    overflow = safe_dict(item.get("overflow_spillway"))
    boundary_points = safe_list(item.get("boundary_points") or item.get("boundary"))
    has_bottom = bool(geometry_quality.get("has_bottom"))
    consistency = safe_float(geometry_quality.get("footprint_consistency_ratio"), 0.0)
    provided_storage_cf = safe_float(detention_design.get("provided_storage_cf"), 0.0)
    top_area_sf = max(
        safe_float(item.get("top_of_bank_area_sf"), 0.0),
        safe_float(item.get("area_sf"), 0.0),
    )
    spillway_capacity = safe_float(overflow.get("assumed_capacity_cfs"), 0.0)
    if has_bottom and consistency >= 0.4:
        return True
    if (
        len(boundary_points) >= 3
        and top_area_sf > 0.0
        and provided_storage_cf > 0.0
        and spillway_capacity > 0.0
    ):
        return True
    return False


def _storm_segment_is_exportable(segment: Dict[str, Any]) -> bool:
    rec = safe_dict(segment)
    path = safe_list(rec.get("route_points") or rec.get("path"))
    if len(path) < 2:
        return False
    length_ft = safe_float(rec.get("length_ft"), 0.0)
    flow_cfs = safe_float(rec.get("flow_cfs"), safe_float(rec.get("local_flow_cfs"), 0.0))
    diameter_in = safe_float(rec.get("diameter_in"), 0.0)
    return length_ft > 0.0 and diameter_in > 0.0 and flow_cfs >= 0.0


def storm_summary_is_exportable(storm: Dict[str, Any]) -> bool:
    summary = safe_dict(storm)
    segments = [safe_dict(item) for item in safe_list(summary.get("segments")) if safe_dict(item)]
    if not segments:
        return False
    if not all(_storm_segment_is_exportable(item) for item in segments):
        return False
    if safe_list(summary.get("missing_data_segments")):
        return False
    if bool(safe_dict(summary.get("graph_validation")).get("valid", False)) and bool(
        safe_dict(summary.get("hydraulic_validation")).get("valid", False)
    ):
        return True
    return safe_str(summary.get("source")) == "surface_fallback"


def _storm_segments_from_project(project: ProjectModel, storm: Dict[str, Any]) -> List[Dict[str, Any]]:
    summary = safe_dict(storm)
    segments = [safe_dict(item) for item in safe_list(summary.get("segments")) if safe_dict(item)]
    if segments:
        return segments
    persisted = [
        safe_dict(item)
        for item in safe_list(project.meta.get("storm_pipe_segments"))
        if safe_dict(item)
    ]
    return persisted


def _storm_segments_are_viable(segments: List[Dict[str, Any]]) -> bool:
    return bool(segments) and all(_storm_segment_is_exportable(item) for item in segments)


def _utility_segment_is_exportable(segment: Dict[str, Any]) -> bool:
    rec = safe_dict(segment)
    route_points = safe_list(rec.get("route_points"))
    return (
        len(route_points) >= 2
        and safe_float(rec.get("cover_start_ft"), 0.0) > 0.0
        and safe_float(rec.get("cover_end_ft"), 0.0) > 0.0
    )


def utility_summary_is_exportable(utilities: Dict[str, Any]) -> bool:
    summary = safe_dict(utilities)
    hooks = safe_dict(summary.get("conflict_hooks"))
    segments = [safe_dict(item) for item in safe_list(hooks.get("utility_segments")) if safe_dict(item)]
    if safe_int(summary.get("route_count"), 0) <= 0 or not segments:
        return False
    if not all(_utility_segment_is_exportable(item) for item in segments):
        return False
    if safe_int(summary.get("shallow_segment_count"), 0) > 0:
        return False
    if safe_int(summary.get("gravity_slope_issue_count"), 0) > 0:
        return False
    coordination = safe_dict(summary.get("coordination"))
    if safe_int(coordination.get("utility_related_unresolved_conflict_count"), 0) > 0:
        return False
    if coordination and not bool(coordination.get("post_validation_valid", True)):
        return False
    return True


def grading_export_validation(
    project: ProjectModel,
    *,
    grading_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    grading = safe_dict(
        grading_override if grading_override is not None else project.meta.get("grading_summary")
    )
    reasons: List[str] = []
    if not bool(grading.get("success", False)):
        reasons.append("grading_stage_invalid")
    if bool(grading.get("fallback_used")):
        reasons.append("grading_fallback_used")
    existing = safe_dict(grading.get("existing_surface"))
    proposed = safe_dict(grading.get("proposed_surface"))
    if not existing or not proposed:
        reasons.append("grading_surfaces_missing")
    derived = safe_dict(grading.get("derived_actions") or grading.get("stats"))
    surface_controls = safe_dict(grading.get("surface_controls"))
    if safe_int(derived.get("proposed_contour_count"), 0) <= 0:
        reasons.append("grading_contours_missing")
    if safe_int(derived.get("spot_grade_count"), 0) <= 0:
        reasons.append("grading_spot_grades_missing")
    if safe_int(derived.get("flow_arrow_count"), 0) <= 0:
        reasons.append("grading_flow_arrows_missing")
    if not bool(surface_controls.get("has_primary_drainage_direction")):
        reasons.append("grading_drainage_direction_missing")
    if not safe_dict(surface_controls.get("primary_low_point")):
        reasons.append("grading_primary_low_point_missing")
    return {
        "ready": not reasons,
        "reasons": reasons,
        "surface_controls": surface_controls,
    }


def drainage_export_validation(
    project: ProjectModel,
    *,
    drainage_override: Optional[Dict[str, Any]] = None,
    storm_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    drainage = safe_dict(
        drainage_override
        if drainage_override is not None
        else project.meta.get("drainage_canonical")
    )
    storm = safe_dict(
        storm_override if storm_override is not None else project.meta.get("storm_pipe_summary")
    )
    grading_export = grading_export_validation(project)
    grading = safe_dict(project.meta.get("grading_summary"))
    surface_alignment = drainage_surface_alignment(grading, drainage)
    primary_basins = primary_engineered_basins(drainage)
    storm_stats = safe_dict(storm.get("stats"))
    selected_basin_name = safe_str(storm_stats.get("selected_basin_name"), "")
    validation_basins = [
        item
        for item in primary_basins
        if safe_str(item.get("name"), "") == selected_basin_name
    ]
    if not validation_basins and primary_basins:
        best_basin = max(primary_basins, key=detention_basin_score)
        validation_basins = [best_basin]
    drainage_stats = safe_dict(drainage.get("stats"))
    drainage_source = safe_str(drainage.get("source"), "")
    reasons: List[str] = []
    if not bool(drainage.get("success", False)):
        reasons.append("drainage_stage_invalid")
    if not bool(grading_export.get("ready")):
        reasons.append("grading_surface_unstable")
    if not primary_basins:
        reasons.append("primary_detention_missing")
    else:
        inadequate_basins = [
            item
            for item in validation_basins
            if safe_str(
                safe_dict(item.get("detention_design")).get("adequacy_status"),
                "adequate",
            ).lower()
            == "deficient"
        ]
        if inadequate_basins:
            reasons.append("primary_detention_inadequate")
        weak_spillway = [
            item
            for item in validation_basins
            if safe_float(
                safe_dict(item.get("overflow_spillway")).get("assumed_capacity_cfs"),
                0.0,
            )
            <= 0.0
        ]
        if weak_spillway:
            reasons.append("primary_detention_overflow_missing")
        weak_geometry = [
            item
            for item in validation_basins
            if not basin_has_exportable_detention_geometry(item)
        ]
        if weak_geometry:
            reasons.append("primary_detention_geometry_weak")
    if not safe_list(drainage.get("structures")):
        reasons.append("drainage_structures_missing")
    if drainage_source == "drainage_engine":
        if safe_int(drainage_stats.get("low_point_count"), 0) <= 0:
            reasons.append("drainage_low_points_missing")
        if safe_int(drainage_stats.get("flow_path_count"), 0) <= 0:
            reasons.append("drainage_flow_paths_missing")
        if (
            safe_int(surface_alignment.get("grading_low_point_count"), 0) > 0
            and safe_int(surface_alignment.get("drainage_low_point_count"), 0) > 0
            and safe_int(surface_alignment.get("matched_low_points"), 0) <= 0
        ):
            reasons.append("drainage_surface_alignment_missing")

    storm_segments = _storm_segments_from_project(project, storm)
    storm_exportable = storm_summary_is_exportable({**storm, "segments": storm_segments}) or _storm_segments_are_viable(
        storm_segments
    )
    if primary_basins:
        if not storm_segments:
            reasons.append("storm_network_missing")
        if not storm_exportable and not bool(safe_dict(storm.get("graph_validation")).get("valid", False)):
            reasons.append("storm_graph_invalid")
        if not storm_exportable and not bool(safe_dict(storm.get("hydraulic_validation")).get("valid", False)):
            reasons.append("storm_hydraulics_invalid")
        if not storm_exportable and safe_list(storm.get("missing_data_segments")):
            reasons.append("storm_segments_incomplete")

    return {
        "ready": not reasons,
        "reasons": reasons,
        "primary_basin_count": len(primary_basins),
        "validation_basin_count": len(validation_basins),
        "selected_basin_name": selected_basin_name,
        "primary_basin_ids": [
            safe_str(item.get("id"), safe_str(item.get("name"), "BASIN"))
            for item in primary_basins
        ],
        "inadequate_basin_count": len(
            [
                item
                for item in validation_basins
                if safe_str(
                    safe_dict(item.get("detention_design")).get("adequacy_status"),
                    "adequate",
                ).lower()
                == "deficient"
            ]
        ),
        "weak_geometry_basin_count": len(
            [
                item
                for item in validation_basins
                if not basin_has_exportable_detention_geometry(item)
            ]
        ),
        "storm_pipe_count": len(storm_segments),
        "grading_export_ready": bool(grading_export.get("ready")),
        "surface_controls": deepcopy(safe_dict(grading_export.get("surface_controls"))),
        "low_point_count": safe_int(drainage_stats.get("low_point_count"), 0),
        "flow_path_count": safe_int(drainage_stats.get("flow_path_count"), 0),
        "total_contributing_area_sf": round(
            safe_float(drainage_stats.get("total_contributing_area_sf"), 0.0), 3
        ),
        "total_estimated_inlet_flow_cfs": round(
            safe_float(drainage_stats.get("total_estimated_inlet_flow_cfs"), 0.0), 3
        ),
        "total_basin_runoff_cfs": round(
            safe_float(drainage_stats.get("total_basin_runoff_cfs"), 0.0), 3
        ),
        "surface_alignment": surface_alignment,
    }


def storm_export_validation(
    project: ProjectModel,
    *,
    storm_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    storm = safe_dict(
        storm_override if storm_override is not None else project.meta.get("storm_pipe_summary")
    )
    drainage_validation = drainage_export_validation(project)
    reasons: List[str] = []
    segments = _storm_segments_from_project(project, storm)
    storm_exportable = storm_summary_is_exportable({**storm, "segments": segments}) or _storm_segments_are_viable(
        segments
    )
    if not segments:
        reasons.append("storm_network_missing")
    if not storm_exportable and not bool(safe_dict(storm.get("graph_validation")).get("valid", False)):
        reasons.append("storm_graph_invalid")
    if not storm_exportable and not bool(safe_dict(storm.get("hydraulic_validation")).get("valid", False)):
        reasons.append("storm_hydraulics_invalid")
    if not storm_exportable and bool(safe_dict(storm.get("explain")).get("implied_target_used")):
        reasons.append("storm_downstream_target_implied")
    if not storm_exportable and safe_list(storm.get("missing_data_segments")):
        reasons.append("storm_segments_incomplete")
    for drainage_reason in (
        "primary_detention_inadequate",
        "primary_detention_overflow_missing",
        "primary_detention_geometry_weak",
    ):
        if drainage_reason in safe_list(drainage_validation.get("reasons")):
            reasons.append(drainage_reason)
    return {
        "ready": not reasons,
        "reasons": reasons,
        "segment_count": len(segments),
    }


def utility_export_validation(
    project: ProjectModel,
    *,
    utilities_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    utilities = safe_dict(
        utilities_override
        if utilities_override is not None
        else project.meta.get("utility_summary")
    )
    hooks = safe_dict(utilities.get("conflict_hooks"))
    segments = safe_list(hooks.get("utility_segments"))
    reasons: List[str] = []
    utility_exportable = utility_summary_is_exportable(utilities)
    if not bool(utilities.get("success", False)):
        reasons.append("utility_stage_invalid")
    if bool(utilities.get("fallback_used")) and not utility_exportable:
        reasons.append("utility_fallback_used")
    if safe_int(utilities.get("route_count"), 0) <= 0 or not segments:
        reasons.append("utility_network_missing")
    if safe_int(utilities.get("shallow_segment_count"), 0) > 0:
        reasons.append("utility_cover_weak")
    if safe_int(utilities.get("gravity_slope_issue_count"), 0) > 0:
        reasons.append("utility_gravity_slope_weak")
    coordination = safe_dict(utilities.get("coordination"))
    if safe_int(coordination.get("utility_related_unresolved_conflict_count"), 0) > 0:
        reasons.append("utility_coordination_unresolved")
    if coordination and not bool(coordination.get("post_validation_valid", True)):
        reasons.append("utility_post_validation_failed")
    return {
        "ready": not reasons,
        "reasons": reasons,
        "route_count": safe_int(utilities.get("route_count"), 0),
        "shallow_segment_count": safe_int(utilities.get("shallow_segment_count"), 0),
        "gravity_slope_issue_count": safe_int(
            utilities.get("gravity_slope_issue_count"), 0
        ),
        "utility_related_unresolved_conflict_count": safe_int(
            coordination.get("utility_related_unresolved_conflict_count"),
            0,
        ),
        "post_validation_valid": bool(coordination.get("post_validation_valid", True)),
    }
