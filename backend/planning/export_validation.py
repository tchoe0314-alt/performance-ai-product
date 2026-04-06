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
        if not selected_basin_name or safe_str(item.get("name"), "") == selected_basin_name
    ]
    if not validation_basins:
        validation_basins = primary_basins
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
            if (
                not bool(safe_dict(item.get("geometry_quality")).get("has_bottom"))
                or safe_float(
                    safe_dict(item.get("geometry_quality")).get(
                        "footprint_consistency_ratio"
                    ),
                    1.0,
                )
                < 0.4
            )
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

    storm_segments = safe_list(storm.get("segments"))
    if primary_basins:
        if not storm_segments:
            reasons.append("storm_network_missing")
        if not bool(safe_dict(storm.get("graph_validation")).get("valid", False)):
            reasons.append("storm_graph_invalid")
        if not bool(safe_dict(storm.get("hydraulic_validation")).get("valid", False)):
            reasons.append("storm_hydraulics_invalid")
        if safe_list(storm.get("missing_data_segments")):
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
                if (
                    not bool(safe_dict(item.get("geometry_quality")).get("has_bottom"))
                    or safe_float(
                        safe_dict(item.get("geometry_quality")).get(
                            "footprint_consistency_ratio"
                        ),
                        1.0,
                    )
                    < 0.4
                )
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
    segments = safe_list(storm.get("segments"))
    if not segments:
        reasons.append("storm_network_missing")
    if not bool(safe_dict(storm.get("graph_validation")).get("valid", False)):
        reasons.append("storm_graph_invalid")
    if not bool(safe_dict(storm.get("hydraulic_validation")).get("valid", False)):
        reasons.append("storm_hydraulics_invalid")
    if bool(safe_dict(storm.get("explain")).get("implied_target_used")):
        reasons.append("storm_downstream_target_implied")
    if safe_list(storm.get("missing_data_segments")):
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
    if not bool(utilities.get("success", False)):
        reasons.append("utility_stage_invalid")
    if bool(utilities.get("fallback_used")):
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
