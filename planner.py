from __future__ import annotations

"""
planner.py (FINAL TRUE MAX ALIGNED VERSION)

Merged intent
-------------
This file keeps your current planner as the base and hardens it to align with:
- the final integration-hardened orchestrator
- the upgraded ProjectManager lifecycle/state layer
- the upgraded pipe backend
- stronger conflict -> fix -> rerun behavior
- stronger metric/score propagation for intelligence/system_runner/UI

Design rules
------------
- planner remains the execution brain
- engines remain discipline-specific
- ProjectModel / ProjectManager remain the shared source of truth
- no capability loss; only stronger integration and coordination
"""

import inspect
import hashlib
import json
import logging
import math
import re
from copy import deepcopy
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import parsers.ai_parser
from parsers.ai_parser import ask_mode, command_mode

from core.config import (
    APP_NAME,
    APP_VERSION,
    CELL_SIZE,
    SURFACE_PADDING,
    TEXT_HEIGHT_SMALL,
    DEFAULT_LOT_X,
    DEFAULT_LOT_Y,
    DEFAULT_LOT_WIDTH,
    DEFAULT_LOT_HEIGHT,
    DEFAULT_SETBACK,
    DEFAULT_PAD_WIDTH,
    DEFAULT_PAD_DEPTH,
    DEFAULT_PAD_ELEV,
    DEFAULT_PARK_START_ELEV,
    DEFAULT_PARK_SLOPE_Y,
    DEFAULT_ROAD_START_ELEV,
    DEFAULT_ROAD_SLOPE_X,
    POND_RADIUS,
    PIPE_INTENSITY_IN_HR,
    PIPE_MANNINGS_N,
    PIPE_MAX_INLETS,
    PIPE_MIN_COVER_FT,
    PIPE_MIN_SLOPE,
    PIPE_RUNOFF_C,
    MIN_SLOPE,
)

from core.constraint_engine import (
    DuplicateObjectAnchorConstraint,
    MaxSpanConstraint,
    ObjectOverlapConstraint,
    ZoneOverlapConstraint,
    evaluate_constraints,
    validate_drainage_summary,
    validate_expanded_site_plan,
    validate_site_layout,
)

from core.geometry_core import (
    EngineeringDomain,
    EngineeringObject,
    Point3D,
    ProjectModel,
    ZoneType,
    rect_zone,
)
from core.civil_design import civil_design_readiness, construction_readiness, standards_from_meta

from core.project_manager import (
    ConflictRecord,
    ConflictSeverity,
    DependencyState,
    ProjectManager,
)

from engines.autofix_engine import autofix_site_layout
from engines.detention_engine import concept_detention_size
from engines.drainage_engine import DrainageEngine, HydraulicInputs
from engines.error_check_engine import run_checks, run_plan_checks
from engines.explain_engine import explain_plan
from engines.grading_engine import GradingEngine, GradeElement, GradingRequest
from engines.hydrology_engine import RationalArea, compute_rational_method
from engines.pipe_engine import PipeEngine
from engines.quantity_engine import compute_plan_quantities
from engines.sanitary_engine import SanitaryEngine, SanitaryFixture, SanitaryPipeSegment, SanitarySizingRequest
from engines.storm.hydraulic_engine import analyze_storm_hydraulics
from engines.storm.storm_network_engine import build_storm_network
from engines.storm.storm_types import (
    HydraulicAnalysisRequest,
    StormBasin,
    StormCatchment,
    StormInlet,
    StormNetworkRequest,
    StormNode,
    StormNodeType,
    StormPoint,
)
from engines.surface_engine import SurfaceEngine, GridSurface
from engines.utility_engine import UtilityEngine, UtilityNodeSpec, UtilityRequest
from engines.cost_engine import compute_cost_estimate

from geometry.layout_engine import expand_plan
from output.dxf_exporter import (
    _ensure_canonical_sheet_metadata,
    _export_cross_sections,
    _export_profiles,
    finalize_export_metadata,
    save_dxf,
)
from output.preview import preview_plan

from backend.planning.common import (
    _call_with_compatible_kwargs,
    _install_rect_obstacle_compatibility,
    blocker_explanations,
    clamp,
    canonical_stage_output,
    dedupe_keep_order,
    lower_text,
    polyline_length,
    rect_area,
    readiness_issue_explanations,
    safe_dict,
    safe_float,
    safe_int,
    safe_list,
    safe_str,
)
from backend.planning.field_contract import (
    FIELD_SOURCE_INFER,
    is_field_wrapper,
    field_source,
    is_user_set,
    is_inferable,
    is_omitted,
    resolve_field,
    make_field,
    preserve_field_states,
    field_state,
    field_path_is_omitted,
    field_path_source,
    field_path_is_inferred,
    field_path_is_user_locked,
    omission_flags_from_parsed,
    filter_actions_by_field_intent,
    wrap_fields_for_execution,
    unwrap_fields_for_execution,
)
from backend.planning.runtime import (
    PLANNER_STAGE_ORDER,
    PlanQualityReport,
    PlannerExecutionContext,
    QualityIssue,
    RoutingDecision,
    PlannerStageResult,
    declared_stage_dependencies,
    sanitize_action,
    sanitize_plan,
    collect_plan_stats,
    normalize_parsed_payload,
    triple_check_parsed_payload,
    choose_routing_path,
    _bootstrap_manager,
    _register_default_dependencies,
    _mark_dependency_state,
    _lot_area,
    _compute_hydrology_metrics,
    _planner_score_from_manager,
)
from backend.planning.export_validation import (
    drainage_export_validation as _drainage_export_validation,
    drainage_surface_alignment as _drainage_surface_alignment,
    grading_export_validation as _grading_export_validation,
    primary_engineered_basins as _primary_engineered_basins,
    storm_export_validation as _storm_export_validation,
    utility_export_validation as _utility_export_validation,
)
from backend.planning.storm_translation import (
    storm_basins_from_drainage as _storm_basins_from_drainage_impl,
    storm_catchments_from_drainage as _storm_catchments_from_drainage_impl,
    storm_inlets_from_drainage as _storm_inlets_from_drainage_impl,
    storm_summary_from_network_result as _storm_summary_from_network_result_impl,
)
from backend.planning.canonical_export import (
    canonical_export_actions as _canonical_export_actions,
)
from backend.planning.late_stage_runners import (
    apply_fix_pass as _apply_fix_pass_impl,
    run_earthwork_stage as _run_earthwork_stage_impl,
    run_qa_stage as _run_qa_stage_impl,
)
from backend.planning.sheet_stage import (
    run_sheet_stage as _run_sheet_stage_impl,
)
from backend.planning.execution_control import (
    canonical_state_snapshot as _canonical_state_snapshot_impl,
    latest_stage_result as _latest_stage_result_impl,
    mark_stage_skipped_clean as _mark_stage_skipped_clean_impl,
    record_stage_audit as _record_stage_audit_impl,
    stage_completeness_label as _stage_completeness_label_impl,
    stage_dirty_reasons as _stage_dirty_reasons_impl,
    stage_should_run as _stage_should_run_impl,
    stage_sort_key as _stage_sort_key_impl,
)
from backend.planning.finalization import (
    build_optimization_summary as _build_optimization_summary_impl,
    canonical_area_accounting as _canonical_area_accounting_impl,
    canonical_truth_audit as _canonical_truth_audit_impl,
    finalize_engineering_trust_score as _finalize_engineering_trust_score_impl,
    parking_program_context as _parking_program_context_impl,
    produced_deliverables as _produced_deliverables_impl,
    requested_deliverables as _requested_deliverables_impl,
)
from backend.planning.grading_support import (
    build_existing_surface as _build_existing_surface_impl,
    build_grade_elements as _build_grade_elements_impl,
    canonical_grading_payload as _canonical_grading_payload_impl,
    grading_drainage_coordination as _grading_drainage_coordination_impl,
    grading_surface_actions as _grading_surface_actions_impl,
    point_on_lot_edge as _point_on_lot_edge_impl,
    surface_actions_from_grid as _surface_actions_from_grid_impl,
    surface_range as _surface_range_impl,
)
from backend.planning.core_stage_runners import (
    run_grading_stage as _run_grading_stage_impl,
    run_layout_stage as _run_layout_stage_impl,
)
from backend.planning.hydrology_stage_runners import (
    run_drainage_stage as _run_drainage_stage_impl,
    run_storm_pipe_stage as _run_storm_pipe_stage_impl,
)
from backend.planning.infrastructure_stage_runners import (
    run_sanitary_stage as _run_sanitary_stage_impl,
    run_utility_stage as _run_utility_stage_impl,
)
from backend.planning.coordination_stage_runner import (
    run_conflict_resolution_stage as _run_conflict_resolution_stage_impl,
)
from backend.planning.coordination_realism import (
    coordination_realism_from_summary as _coordination_realism_from_summary_impl,
    coordination_realism_summary as _coordination_realism_summary_impl,
)
from backend.planning.coordination_state import (
    add_grading_adjustment as _add_grading_adjustment_impl,
    coordination_metric_inc as _coordination_metric_inc_impl,
    coordination_record_prune as _coordination_record_prune_impl,
    full_coordination_state_snapshot as _full_coordination_state_snapshot_impl,
    grading_local_adjustments as _grading_local_adjustments_impl,
    new_coordination_metrics as _new_coordination_metrics_impl,
    restore_full_coordination_state as _restore_full_coordination_state_impl,
    restore_coordination_state as _restore_coordination_state_impl,
    snapshot_coordination_state as _snapshot_coordination_state_impl,
    sync_drainage_mutable_state as _sync_drainage_mutable_state_impl,
)
from backend.planning.engine_readiness import (
    evaluate_engine_readiness as _evaluate_engine_readiness,
)
from backend.planning.construction_package import (
    build_construction_package_manifest as _build_construction_package_manifest,
)
from backend.planning.depth_validators import (
    validate_roadway_corridor_depth as _validate_roadway_corridor_depth,
    validate_stormwater_depth as _validate_stormwater_depth,
    validate_water_system_depth as _validate_water_system_depth,
)
from backend.planning.production_depth import (
    enrich_storm_production_depth as _enrich_storm_production_depth,
    enrich_water_production_depth as _enrich_water_production_depth,
)
from backend.planning.existing_conditions import summarize_existing_conditions as _summarize_existing_conditions
from backend.planning.reactive_model import reactive_report_from_plan as _reactive_report_from_plan


BASE_DIR = Path(__file__).parent
LOGGER = logging.getLogger(__name__)
if not LOGGER.handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")


def _bounded_state_copy(value: Any, *, max_depth: int = 16, max_items: int = 3000) -> Any:
    seen: set[int] = set()

    def clone(node: Any, depth: int) -> Any:
        if node is None or isinstance(node, (str, int, float, bool)):
            return node
        if depth > max_depth:
            return {"truncated": True, "type": type(node).__name__}
        if isinstance(node, dict):
            node_id = id(node)
            if node_id in seen:
                return {"cycle": True, "type": "dict"}
            seen.add(node_id)
            out: Dict[str, Any] = {}
            for idx, (key, item) in enumerate(node.items()):
                if idx >= max_items:
                    out["__truncated_items__"] = max(0, len(node) - max_items)
                    break
                out[str(key)] = clone(item, depth + 1)
            seen.discard(node_id)
            return out
        if isinstance(node, (list, tuple, set)):
            node_id = id(node)
            if node_id in seen:
                return {"cycle": True, "type": type(node).__name__}
            seen.add(node_id)
            seq = list(node)
            out = [clone(item, depth + 1) for item in seq[:max_items]]
            if len(seq) > max_items:
                out.append({"truncated_items": len(seq) - max_items})
            seen.discard(node_id)
            return out
        to_dict = getattr(node, "to_dict", None)
        if callable(to_dict):
            try:
                return clone(to_dict(), depth + 1)
            except Exception:
                pass
        if hasattr(node, "__dict__"):
            return clone({key: item for key, item in vars(node).items() if not str(key).startswith("_")}, depth + 1)
        return repr(node)

    return clone(value, 0)


def _storm_inlets_from_drainage(drainage_meta: Dict[str, Any]) -> List[Any]:
    return _storm_inlets_from_drainage_impl(drainage_meta)  # type: ignore[name-defined]


def _storm_basins_from_drainage(
    drainage_meta: Dict[str, Any],
    *,
    primary_engineered_basins: Optional[Callable[[Dict[str, Any]], List[Dict[str, Any]]]] = None,
) -> List[Any]:
    return _storm_basins_from_drainage_impl(
        drainage_meta,
        primary_engineered_basins=primary_engineered_basins or _primary_engineered_basins,
    )  # type: ignore[name-defined]


def _storm_catchments_from_drainage(
    drainage_meta: Dict[str, Any],
    *,
    runoff_c: float,
    intensity_in_hr: float,
) -> List[Any]:
    return _storm_catchments_from_drainage_impl(
        drainage_meta,
        runoff_c=runoff_c,
        intensity_in_hr=intensity_in_hr,
    )  # type: ignore[name-defined]


def _storm_summary_from_network_result(
    network_result: Any,
    hydraulic_result: Any,
    *,
    validate_network_graph: Optional[Callable[[Dict[str, Any], str], Dict[str, Any]]] = None,
    validate_storm_hydraulics: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return _storm_summary_from_network_result_impl(
        network_result,
        hydraulic_result,
        validate_network_graph=validate_network_graph or _validate_network_graph,
        validate_storm_hydraulics=validate_storm_hydraulics or _validate_storm_hydraulics,
    )  # type: ignore[name-defined]


def _user_supplied_geometry_available(parsed: Dict[str, Any], key: str) -> bool:
    value = unwrap_fields_for_execution(parsed.get(key))
    return isinstance(value, list) and any(isinstance(v, dict) for v in value)


def _strict_mode_enabled(parsed: Dict[str, Any]) -> bool:
    meta = safe_dict(parsed.get("meta"))
    for candidate in (parsed.get("strict_mode"), meta.get("strict_mode")):
        if isinstance(candidate, bool):
            return candidate
        if lower_text(candidate) in {"1", "true", "yes", "strict", "on"}:
            return True
    return False


def _sanitary_requested(parsed: Dict[str, Any]) -> bool:
    deliverables = {_requested for _requested in [lower_text(item) for item in safe_list(parsed.get("deliverables"))] if _requested}
    if any(any(token in deliverable for token in ("sanitary", "sewer")) for deliverable in deliverables):
        return True

    disciplines = {lower_text(item) for item in safe_list(parsed.get("disciplines")) if safe_str(item)}
    if {"sanitary", "sewer"} & disciplines:
        return True

    execution_payload = unwrap_fields_for_execution(parsed)
    for feature in safe_list(execution_payload.get("utility_network")):
        if not isinstance(feature, dict):
            continue
        utility_type = lower_text(feature.get("utility_type"))
        layer = safe_str(feature.get("layer"), "").upper()
        if utility_type in {"sanitary", "sewer", "san"} or layer == "SAN":
            return True

    sanitary_meta = safe_dict(safe_dict(parsed.get("meta")).get("sanitary"))
    if any(
        bool(sanitary_meta.get(key))
        for key in ("requested", "required", "enabled", "generate")
    ):
        return True

    site_plan = safe_dict(unwrap_fields_for_execution(parsed.get("site_plan")))
    has_building_program = (
        safe_float(site_plan.get("building_width"), 0.0) > 0.0
        and safe_float(site_plan.get("building_depth"), 0.0) > 0.0
    ) or safe_int(site_plan.get("building_count"), 0) > 0
    if has_building_program and not field_path_is_omitted(parsed, "sanitary"):
        return True
    return False


def _storm_requested(parsed: Dict[str, Any]) -> bool:
    deliverables = {lower_text(item) for item in safe_list(parsed.get("deliverables")) if safe_str(item)}
    if any(any(token in deliverable for token in ("storm", "drainage", "pipe")) for deliverable in deliverables):
        return True
    disciplines = {lower_text(item) for item in safe_list(parsed.get("disciplines")) if safe_str(item)}
    if {"storm", "drainage"} & disciplines:
        return True
    storm_meta = safe_dict(safe_dict(parsed.get("meta")).get("storm"))
    return any(bool(storm_meta.get(key)) for key in ("requested", "required", "enabled", "generate"))


def _sample_grid_surface(surface: Optional[GridSurface], x: float, y: float, default: float) -> float:
    if surface is None:
        return default
    try:
        cell = max(1.0, safe_float(getattr(surface, "cell_size", 1.0), 1.0))
        row = int(round((y - safe_float(getattr(surface, "y_min", 0.0), 0.0)) / cell))
        col = int(round((x - safe_float(getattr(surface, "x_min", 0.0), 0.0)) / cell))
        row = max(0, min(safe_int(getattr(surface, "nrows", 1), 1) - 1, row))
        col = max(0, min(safe_int(getattr(surface, "ncols", 1), 1) - 1, col))
        values = getattr(surface, "values", []) or []
        if not values:
            return default
        return safe_float(values[row][col], default)
    except Exception:
        return default


def _build_optimization_summary(parsed: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    return _build_optimization_summary_impl(parsed, plan)


def _segment_distance(a0: Sequence[float], a1: Sequence[float], b0: Sequence[float], b1: Sequence[float]) -> float:
    def _orientation(p: Tuple[float, float], q: Tuple[float, float], r: Tuple[float, float]) -> float:
        return (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])

    def _on_segment(p: Tuple[float, float], q: Tuple[float, float], r: Tuple[float, float]) -> bool:
        return (
            min(p[0], r[0]) - 1e-9 <= q[0] <= max(p[0], r[0]) + 1e-9
            and min(p[1], r[1]) - 1e-9 <= q[1] <= max(p[1], r[1]) + 1e-9
        )

    def _segments_intersect(p1: Tuple[float, float], q1: Tuple[float, float], p2: Tuple[float, float], q2: Tuple[float, float]) -> bool:
        o1 = _orientation(p1, q1, p2)
        o2 = _orientation(p1, q1, q2)
        o3 = _orientation(p2, q2, p1)
        o4 = _orientation(p2, q2, q1)
        if (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0):
            return True
        if abs(o1) <= 1e-9 and _on_segment(p1, p2, q1):
            return True
        if abs(o2) <= 1e-9 and _on_segment(p1, q2, q1):
            return True
        if abs(o3) <= 1e-9 and _on_segment(p2, p1, q2):
            return True
        if abs(o4) <= 1e-9 and _on_segment(p2, q1, q2):
            return True
        return False

    pts = [
        (safe_float(a0[0], 0.0), safe_float(a0[1], 0.0)),
        (safe_float(a1[0], 0.0), safe_float(a1[1], 0.0)),
        (safe_float(b0[0], 0.0), safe_float(b0[1], 0.0)),
        (safe_float(b1[0], 0.0), safe_float(b1[1], 0.0)),
    ]
    if _segments_intersect(pts[0], pts[1], pts[2], pts[3]):
        return 0.0
    min_dist = float("inf")
    for idx in (0, 1):
        px, py = pts[idx]
        q0, q1 = pts[2], pts[3]
        vx = q1[0] - q0[0]
        vy = q1[1] - q0[1]
        denom = max(vx * vx + vy * vy, 1e-9)
        t = ((px - q0[0]) * vx + (py - q0[1]) * vy) / denom
        t = max(0.0, min(1.0, t))
        proj_x = q0[0] + t * vx
        proj_y = q0[1] + t * vy
        min_dist = min(min_dist, ((px - proj_x) ** 2 + (py - proj_y) ** 2) ** 0.5)
    for idx in (2, 3):
        px, py = pts[idx]
        q0, q1 = pts[0], pts[1]
        vx = q1[0] - q0[0]
        vy = q1[1] - q0[1]
        denom = max(vx * vx + vy * vy, 1e-9)
        t = ((px - q0[0]) * vx + (py - q0[1]) * vy) / denom
        t = max(0.0, min(1.0, t))
        proj_x = q0[0] + t * vx
        proj_y = q0[1] + t * vy
        min_dist = min(min_dist, ((px - proj_x) ** 2 + (py - proj_y) ** 2) ** 0.5)
    return 0.0 if min_dist == float("inf") else min_dist


def _orthogonal_path(start: Tuple[float, float], end: Tuple[float, float], *, prefer_x_first: bool) -> List[List[float]]:
    sx, sy = start
    ex, ey = end
    if abs(sx - ex) <= 1e-6 or abs(sy - ey) <= 1e-6:
        return [[sx, sy], [ex, ey]]
    if prefer_x_first:
        return [[sx, sy], [ex, sy], [ex, ey]]
    return [[sx, sy], [sx, ey], [ex, ey]]


def _requested_profile_or_sections(parsed: Dict[str, Any]) -> Tuple[bool, bool]:
    requested = set(_requested_deliverables(parsed))
    wants_profile = any(item in requested for item in {"road_profile", "profiles"})
    wants_sections = any(item in requested for item in {"cross_sections", "cross_sections_plan"})
    return wants_profile, wants_sections


def _station_text(station_ft: float) -> str:
    total = max(0, int(round(safe_float(station_ft, 0.0))))
    return f"{total // 100}+{total % 100:02d}"


def _service_point_for_zone(zone: Any, street_edge: str) -> Tuple[float, float]:
    bbox = getattr(getattr(zone, "boundary", None), "bbox", None)
    if bbox is None:
        centroid = getattr(getattr(zone, "boundary", None), "centroid", lambda: Point3D(0.0, 0.0, 0.0))()
        return safe_float(getattr(centroid, "x", 0.0), 0.0), safe_float(getattr(centroid, "y", 0.0), 0.0)
    edge = lower_text(street_edge)
    cx = (bbox.min_x + bbox.max_x) / 2.0
    cy = (bbox.min_y + bbox.max_y) / 2.0
    inset_x = max(2.0, min(6.0, bbox.width * 0.2))
    inset_y = max(2.0, min(6.0, bbox.height * 0.2))
    if edge == "bottom":
        return cx, bbox.min_y + inset_y
    if edge == "top":
        return cx, bbox.max_y - inset_y
    if edge == "left":
        return bbox.min_x + inset_x, cy
    return bbox.max_x - inset_x, cy


def _record_strict_stage_failure(
    ctx: PlannerExecutionContext,
    stage_name: str,
    code: str,
    message: str,
    *,
    category: str,
    dependency: str,
    computation_step: str,
) -> None:
    manager = ctx.manager
    manager.mark_system_failed(stage_name, message, [message])
    manager.add_conflict(
        ConflictRecord(
            code=code,
            message=message,
            severity=ConflictSeverity.ERROR,
            category=category,
            context={"strict_mode": True, "dependency": dependency, "computation_step": computation_step},
        )
    )
    ctx.record_error(message)
    ctx.add_stage(
        stage_name,
        False,
        message,
        strict_mode=True,
        failure_code=code,
        dependency=dependency,
        computation_step=computation_step,
    )


def _manual_mode_enabled(parsed: Dict[str, Any]) -> bool:
    meta = safe_dict(parsed.get("meta"))
    if bool(meta.get("allow_ai_fill_for_blanks")) or bool(meta.get("assisted_enabled")):
        return False
    for candidate in (
        parsed.get("manual_mode"),
        meta.get("manual_mode"),
        meta.get("input_mode"),
        meta.get("source_input_mode"),
        meta.get("orchestrator_input_mode"),
    ):
        if isinstance(candidate, bool):
            if candidate:
                return True
            continue
        if lower_text(candidate) == "manual":
            return True
    return False


def _latest_stage_result(ctx: PlannerExecutionContext, stage_name: str) -> Optional[PlannerStageResult]:
    return _latest_stage_result_impl(ctx, stage_name)


def _stage_dirty_reasons(ctx: PlannerExecutionContext, stage_name: str) -> List[str]:
    return _stage_dirty_reasons_impl(ctx, stage_name)


def _stage_should_run(ctx: PlannerExecutionContext, stage_name: str, *, force_first_pass: bool = True) -> bool:
    return _stage_should_run_impl(ctx, stage_name, force_first_pass=force_first_pass)


def _mark_stage_skipped_clean(ctx: PlannerExecutionContext, stage_name: str) -> None:
    _mark_stage_skipped_clean_impl(ctx, stage_name)


def _manual_failure(
    gate_name: str,
    stage_name: str,
    code: str,
    message: str,
    *,
    engine: str,
    missing_computation: str,
    source_fields: Sequence[str],
    failure_type: str,
    reason_class: str,
    category: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "gate_name": gate_name,
        "stage_name": stage_name,
        "code": code,
        "message": message,
        "engine": engine,
        "missing_computation": missing_computation,
        "source_fields": list(source_fields),
        "failure_type": failure_type,
        "reason_class": reason_class,
        "category": category,
        "context": deepcopy(context or {}),
    }


def _manual_failure_reasoning(failure: Dict[str, Any]) -> Dict[str, Any]:
    rec = safe_dict(failure)
    context = safe_dict(rec.get("context"))
    unresolved = safe_list(context.get("unresolved_conflicts"))
    first_conflict = safe_dict(unresolved[0]) if unresolved else {}
    failure_breakdown = safe_dict(first_conflict.get("failure_breakdown") or context.get("failure_breakdown"))
    location = context.get("location", first_conflict.get("location"))
    rule = (
        safe_str(context.get("rule"))
        or safe_str(rec.get("reason_class"))
        or safe_str(rec.get("missing_computation"))
        or safe_str(rec.get("code"))
    )
    why_unresolved = (
        safe_str(failure_breakdown.get("rejected_reason"))
        or safe_str(context.get("why_unresolved"))
        or safe_str(first_conflict.get("resolution_reason"))
        or safe_str(context.get("failure_reason"))
        or safe_str(rec.get("message"))
    )
    return {
        "system": safe_str(rec.get("stage_name")),
        "engine": safe_str(rec.get("engine")),
        "rule": rule,
        "code": safe_str(rec.get("code")),
        "location": deepcopy(location) if isinstance(location, (list, dict, tuple)) else location,
        "why_unresolved": why_unresolved,
        "failure_type": safe_str(rec.get("failure_type")),
        "reason_class": safe_str(rec.get("reason_class")),
        "failure_breakdown": deepcopy(failure_breakdown),
    }


def _canonical_state_snapshot(project: ProjectModel, manager: ProjectManager) -> Dict[str, Any]:
    return _canonical_state_snapshot_impl(project, manager)


def _canonical_state_diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    keys = sorted(set(before.keys()) | set(after.keys()))
    changed: Dict[str, Dict[str, Any]] = {}
    for key in keys:
        before_value = deepcopy(before.get(key))
        after_value = deepcopy(after.get(key))
        if before_value != after_value:
            changed[key] = {"before": before_value, "after": after_value}
    return {
        "changed_keys": sorted(changed.keys()),
        "changed_count": len(changed),
        "changes": changed,
    }


def _record_stage_audit(
    ctx: PlannerExecutionContext,
    stage_name: str,
    *,
    pass_index: int,
    action: str,
    dirty_reasons: Sequence[str],
    before_state: Dict[str, Any],
) -> None:
    _record_stage_audit_impl(
        ctx,
        stage_name,
        pass_index=pass_index,
        action=action,
        dirty_reasons=dirty_reasons,
        before_state=before_state,
    )


def _stage_sort_key(stage_name: str) -> Tuple[int, str]:
    return _stage_sort_key_impl(stage_name)


def _stage_completeness_label(stage_name: str, success: bool, message: str, meta: Dict[str, Any]) -> str:
    return _stage_completeness_label_impl(stage_name, success, message, meta)


def _required_stage_names(parsed: Dict[str, Any], plan: Dict[str, Any]) -> List[str]:
    requested = set(_requested_deliverables(parsed))
    omit = omission_flags_from_parsed(parsed)
    if requested and requested <= {"sanitary_plan"}:
        return ["grading", "sanitary"]
    required = ["layout", "grading", "coordination_resolution", "earthwork", "qa"]
    if not omit.get("drainage"):
        required.extend(["drainage", "storm_pipes"])
    if not omit.get("utilities"):
        required.append("utility_network")
    if _sanitary_requested(parsed) or "sanitary_plan" in requested:
        required.append("sanitary")
    if requested & {"road_profile", "profiles", "cross_sections", "cross_sections_plan"}:
        required.append("sheets")
    return dedupe_keep_order(required)


def _compile_stage_completeness(ctx: PlannerExecutionContext, parsed: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    rows = []
    for stage in sorted(ctx.stage_results, key=lambda item: _stage_sort_key(safe_str(item.stage_name))):
        meta = deepcopy(safe_dict(stage.meta))
        rows.append(
            {
                "stage_name": safe_str(stage.stage_name),
                "success": bool(stage.success),
                "completeness": _stage_completeness_label(safe_str(stage.stage_name), bool(stage.success), safe_str(stage.message), meta),
                "message": safe_str(stage.message),
                "meta": meta,
            }
        )
    required = _required_stage_names(parsed, plan)
    required_status: Dict[str, str] = {}
    for row in rows:
        name = row["stage_name"]
        if name not in required:
            continue
        completeness = row["completeness"]
        if required_status.get(name) == "complete":
            continue
        required_status[name] = completeness
    return {
        "stages": rows,
        "required_stage_names": required,
        "required_stage_status": required_status,
        "all_required_complete": all(required_status.get(name) == "complete" for name in required),
    }


def _estimated_parking_stalls_from_actions(actions: Sequence[Dict[str, Any]]) -> int:
    parking_area = 0.0
    for action in actions:
        if not isinstance(action, dict):
            continue
        if lower_text(action.get("task")) != "rectangle":
            continue
        layer = safe_str(action.get("layer"), "").upper()
        label = lower_text(action.get("label"))
        if layer not in {"PARKING", "PAVEMENT"} and "park" not in label:
            continue
        parking_area += rect_area(action.get("width"), action.get("height"))
    if parking_area <= 0.0:
        return 0
    return max(0, int(round(parking_area / 162.0)))


def _requested_deliverables(parsed: Dict[str, Any]) -> List[str]:
    return _requested_deliverables_impl(parsed)


def _action_sort_key(action: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    rec = safe_dict(action)
    anchor = safe_list(rec.get("origin")) or safe_list(rec.get("center")) or safe_list((safe_list(rec.get("points")) or [[0.0, 0.0]])[0])
    anchor_key = ",".join(f"{safe_float(value, 0.0):.3f}" for value in anchor[:2]) if anchor else "0.000,0.000"
    return (
        safe_str(rec.get("layer")),
        lower_text(rec.get("task")),
        safe_str(rec.get("label")),
        safe_str(rec.get("canonical_source_id")),
        anchor_key,
    )


def _manual_gate_plan(ctx: PlannerExecutionContext) -> Dict[str, Any]:
    plan = project_model_to_plan(ctx.manager.project, ctx.parsed.get("project_name") or "Generated Plan")
    plan.setdefault("meta", {})
    manager_export = ctx.manager.export_metrics() if hasattr(ctx.manager, "export_metrics") else {}
    plan["meta"]["manager_export"] = manager_export
    _attach_canonical_stage_outputs(plan, ctx.manager.project, ctx.manager)
    wants_profile, wants_sections = _requested_profile_or_sections(ctx.parsed)
    if (wants_profile and not safe_list(plan["meta"].get("profiles"))) or (wants_sections and not safe_list(plan["meta"].get("cross_sections"))):
        _ensure_canonical_sheet_metadata(plan, _export_profiles(plan), _export_cross_sections(plan))
    try:
        qty = compute_plan_quantities(plan)
        plan["meta"]["quantities"] = {
            "success": getattr(qty, "success", True),
            "message": getattr(qty, "message", ""),
            "totals": deepcopy(getattr(qty, "totals", {})),
            "tables": deepcopy(getattr(qty, "tables", {})),
            "warnings": list(getattr(qty, "warnings", [])),
            "assumptions": list(getattr(qty, "assumptions", [])),
            "explain": deepcopy(getattr(qty, "explain", {})),
        }
    except Exception as exc:
        plan["meta"]["quantities"] = {"success": False, "message": f"Quantity computation failed: {exc}", "totals": {}}
    try:
        cost = compute_cost_estimate(plan)
        plan["meta"]["cost_estimate"] = {
            "success": getattr(cost, "success", True),
            "message": getattr(cost, "message", ""),
            "totals": deepcopy(getattr(cost, "totals", {})),
            "line_items": deepcopy(getattr(cost, "line_items", [])),
            "category_subtotals": deepcopy(getattr(cost, "category_subtotals", {})),
            "warnings": list(getattr(cost, "warnings", [])),
            "assumptions": list(getattr(cost, "assumptions", [])),
            "explain": deepcopy(getattr(cost, "explain", {})),
        }
    except Exception as exc:
        plan["meta"]["cost_estimate"] = {"success": False, "message": f"Cost computation failed: {exc}", "totals": {}}
    plan["meta"]["stats"] = collect_plan_stats(plan)
    return plan


def _attach_canonical_stage_outputs(plan: Dict[str, Any], project: ProjectModel, manager: ProjectManager) -> None:
    meta = plan.setdefault("meta", {})
    meta["grading"] = canonical_stage_output(project, manager, "grading")
    meta["drainage"] = canonical_stage_output(project, manager, "drainage")
    meta["storm_pipes"] = canonical_stage_output(project, manager, "storm_pipes")
    drainage_output = safe_dict(meta.get("drainage"))
    storm_output = safe_dict(meta.get("storm_pipes"))
    if drainage_output:
        drainage_output["export_validation"] = _drainage_export_validation(
            project,
            drainage_override=drainage_output,
            storm_override=storm_output,
        )
        meta["drainage"] = drainage_output
    if storm_output:
        storm_output["export_validation"] = _storm_export_validation(
            project,
            storm_override=storm_output,
        )
        meta["storm_pipes"] = storm_output
    sanitary_output = safe_dict(canonical_stage_output(project, manager, "sanitary"))
    meta["sanitary"] = (
        sanitary_output
        if safe_int(sanitary_output.get("route_count"), 0) > 0
        or safe_list(sanitary_output.get("segments"))
        or safe_list(sanitary_output.get("manholes"))
        else {}
    )
    meta["utilities"] = canonical_stage_output(project, manager, "utilities")
    meta["coordination"] = canonical_stage_output(project, manager, "coordination")
    meta["coordination_realism"] = _coordination_realism_from_summary_impl(safe_dict(meta.get("coordination")))
    meta["parking_program"] = canonical_stage_output(project, manager, "parking_program")
    meta["profiles"] = canonical_stage_output(project, manager, "profiles")
    meta["cross_sections"] = canonical_stage_output(project, manager, "cross_sections")


def _parking_program_context(parsed: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    return _parking_program_context_impl(parsed, plan)


def _layer_records(value: Any, layer_name: str) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [deepcopy(safe_dict(item)) for item in value if safe_dict(item)]
    rec = safe_dict(value)
    if not rec:
        return []
    rows = safe_list(rec.get("features") or rec.get("items") or rec.get("records"))
    if rows:
        return [deepcopy(safe_dict(item)) for item in rows if safe_dict(item)]
    return [{"id": safe_str(rec.get("id") or rec.get("name"), layer_name), **deepcopy(rec)}]


def _protected_zones_from_existing_conditions(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    existing = safe_dict(meta.get("existing_conditions") or meta.get("gis_layers"))
    zones: List[Dict[str, Any]] = []
    for layer_name, kind in (("wetlands", "wetland"), ("floodplain", "floodplain"), ("easements", "easement"), ("row", "right_of_way")):
        for index, rec in enumerate(_layer_records(existing.get(layer_name), layer_name), start=1):
            zones.append(
                {
                    "id": safe_str(rec.get("id") or rec.get("name"), f"{layer_name}-{index}"),
                    "kind": kind,
                    "source_layer": layer_name,
                    "avoid": kind in {"wetland", "floodplain"},
                    "geometry": deepcopy(rec.get("geometry") or rec.get("bounds") or rec.get("bbox")),
                    "truth_label": "Protected zone came from attached existing-condition/GIS evidence.",
                }
            )
    return zones


def _synthesize_retaining_wall_summary(parsed: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan.get("meta"))
    existing_summary = safe_dict(meta.get("structure_summary") or meta.get("structures"))
    if safe_list(existing_summary.get("retaining_walls")) or safe_list(meta.get("retaining_walls")):
        return existing_summary
    project_type = lower_text(parsed.get("project_type"))
    terrain = safe_dict(unwrap_fields_for_execution(parsed.get("terrain")))
    fall_ft = safe_float(terrain.get("fall_ft"), 0.0)
    if project_type != "retaining_wall_site" and fall_ft < 12.0:
        return existing_summary
    lot = safe_dict(unwrap_fields_for_execution(parsed.get("lot")))
    width = safe_float(lot.get("w") or lot.get("width"), 0.0)
    height = safe_float(lot.get("h") or lot.get("height"), 0.0)
    wall_height = max(4.0, min(12.0, fall_ft * 0.45 if fall_ft > 0.0 else 6.0))
    wall = {
        "id": "RW-1",
        "type": "concept_retaining_wall",
        "alignment": [[round(width * 0.12, 3), round(height * 0.18, 3)], [round(width * 0.88, 3), round(height * 0.18, 3)]],
        "length_ft": round(max(width * 0.76, 1.0), 3),
        "max_exposed_height_ft": round(wall_height, 3),
        "source": "terrain_fall_trigger",
        "review_required": True,
        "truth_label": "Concept retaining wall is generated from declared steep-site terrain and remains blocked for structural review.",
    }
    tie_check = {
        "wall_id": wall["id"],
        "status": "needs_structural_review",
        "grading_tie_in_checked": bool(safe_dict(meta.get("grading")).get("proposed_surface")),
        "utility_clearance_review_required": True,
        "truth_label": "Wall tie-in check is a coordination placeholder, not a sealed structural design.",
    }
    return {
        **existing_summary,
        "retaining_walls": [wall],
        "wall_tie_in_checks": [tie_check],
        "source": "canonical_structure_synthesis",
        "production_ready": False,
    }


def _synthesize_canonical_meta(parsed: Dict[str, Any], plan: Dict[str, Any]) -> None:
    meta = plan.setdefault("meta", {})
    grading = safe_dict(meta.get("grading") or meta.get("grading_summary"))
    if safe_dict(grading.get("earthwork")) and not safe_dict(meta.get("earthwork")):
        meta["earthwork"] = {
            **deepcopy(safe_dict(grading.get("earthwork"))),
            "source": "grading_surface_cut_fill",
            "truth_label": "Earthwork totals are derived from the canonical grading surface.",
        }

    parking = safe_dict(meta.get("parking_program"))
    if not parking or not bool(parking.get("traceable")):
        synthesized_parking = _parking_program_context(parsed, plan)
        if synthesized_parking.get("traceable") or safe_int(synthesized_parking.get("achieved_count"), 0) > 0:
            meta["parking_program"] = synthesized_parking

    parsed_existing = safe_dict(parsed.get("existing_conditions") or parsed.get("gis_layers"))
    if parsed_existing and not safe_dict(meta.get("existing_conditions")):
        meta["existing_conditions"] = deepcopy(parsed_existing)
    for key in ("floodplain", "wetlands"):
        if key in parsed_existing and key not in meta:
            meta[key] = {"features": deepcopy(_layer_records(parsed_existing.get(key), key)), "source": "existing_conditions"}
    protected_zones = _protected_zones_from_existing_conditions(meta)
    if protected_zones and not safe_list(meta.get("protected_zones")):
        meta["protected_zones"] = protected_zones

    structures = _synthesize_retaining_wall_summary(parsed, plan)
    if structures:
        meta["structures"] = deepcopy(structures)
        meta["structure_summary"] = deepcopy(structures)
        if safe_list(structures.get("retaining_walls")) and not safe_list(meta.get("retaining_walls")):
            meta["retaining_walls"] = deepcopy(safe_list(structures.get("retaining_walls")))

    coordination = safe_dict(meta.get("coordination"))
    if coordination and not safe_list(coordination.get("resolution_history")):
        history: List[Dict[str, Any]] = []
        for row in safe_list(coordination.get("resolved_conflicts")):
            rec = safe_dict(row)
            if rec:
                history.append({"status": "resolved", "source": "coordination.resolved_conflicts", "record": deepcopy(rec)})
        realism = safe_dict(coordination.get("coordination_realism") or meta.get("coordination_realism"))
        for row in safe_list(realism.get("best_near_valid_candidates")):
            rec = safe_dict(row)
            if rec:
                history.append({"status": "attempted_not_accepted", "source": "coordination_realism.best_near_valid_candidates", "record": deepcopy(rec)})
        if history:
            coordination["resolution_history"] = history
            meta["coordination"] = coordination


def _canonical_truth_audit(parsed: Dict[str, Any], plan: Dict[str, Any], manager: Optional[ProjectManager] = None) -> Dict[str, Any]:
    return _canonical_truth_audit_impl(
        parsed,
        plan,
        manager=manager,
        sanitary_requested=_sanitary_requested,
    )


def _finalize_engineering_trust_score(plan: Dict[str, Any], *, manual_failed: bool) -> float:
    return _finalize_engineering_trust_score_impl(plan, manual_failed=manual_failed)


def _canonical_area_accounting(parsed: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    return _canonical_area_accounting_impl(parsed, plan)


def _produced_deliverables(plan: Dict[str, Any]) -> List[str]:
    return _produced_deliverables_impl(plan)


def _record_manual_gate_result(ctx: PlannerExecutionContext, gate_name: str, failures: Sequence[Dict[str, Any]]) -> bool:
    seen = getattr(ctx, "_manual_gate_seen", set())
    unique: List[Dict[str, Any]] = []
    for failure in failures:
        key = (
            gate_name,
            safe_str(failure.get("code")),
            safe_str(failure.get("stage_name")),
            safe_str(failure.get("message")),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(deepcopy(failure))
        ctx.manager.add_conflict(
            ConflictRecord(
                code=safe_str(failure.get("code"), "MANUAL_GATE_FAILED"),
                message=safe_str(failure.get("message"), "Assisted-off validation needs more information."),
                severity=ConflictSeverity.ERROR,
                category=safe_str(failure.get("category"), "manual_validation"),
                context={
                    "manual_mode": True,
                    "gate_name": gate_name,
                    "engine": safe_str(failure.get("engine")),
                    "missing_computation": safe_str(failure.get("missing_computation")),
                    "source_fields": list(failure.get("source_fields") or []),
                    "failure_type": safe_str(failure.get("failure_type")),
                    "reason_class": safe_str(failure.get("reason_class")),
                    **safe_dict(failure.get("context")),
                },
            )
        )
        ctx.record_error(safe_str(failure.get("message"), "Assisted-off validation needs more information."))
    setattr(ctx, "_manual_gate_seen", seen)
    if unique:
        ctx.add_stage(
            gate_name,
            False,
            f"{gate_name} failed in manual mode.",
            completeness="failed",
            manual_mode=True,
            failures=deepcopy(unique),
        )
        return False
    ctx.add_stage(gate_name, True, f"{gate_name} passed.", completeness="complete", manual_mode=True)
    return True


def _run_manual_gate(ctx: PlannerExecutionContext, gate_name: str, plan: Optional[Dict[str, Any]] = None) -> bool:
    if not _manual_mode_enabled(ctx.parsed):
        return True

    plan = sanitize_plan(plan or _manual_gate_plan(ctx))
    parsed = ctx.parsed
    manager = ctx.manager
    project = manager.project
    failures: List[Dict[str, Any]] = []

    def gate_stage(stage: str) -> Dict[str, Any]:
        return safe_dict(canonical_stage_output(project, manager, stage))

    if gate_name == "layout_gate":
        if _lot_area(parsed) <= 0.0:
            failures.append(
                _manual_failure(
                    gate_name,
                    "layout",
                    "MANUAL_SITE_AREA_MISSING",
                    "Assisted off requires a canonical lot/site area before layout validation can pass.",
                    engine="layout_engine",
                    missing_computation="canonical_site_area",
                    source_fields=["lot.w", "lot.h"],
                    failure_type="missing_input",
                    reason_class="missing_site_area",
                    category="site",
                )
            )
        parking_program = _parking_program_context(parsed, plan)
        project.meta["parking_program"] = deepcopy(parking_program)
        manager.latest_outputs["parking_program"] = deepcopy(parking_program)
        if not parking_program.get("traceable"):
            failures.append(
                _manual_failure(
                    gate_name,
                    "layout",
                    "MANUAL_PARKING_TARGET_UNTRACEABLE",
                    "Assisted off requires a numerically traceable parking target from explicit input or project-type program rules.",
                    engine="layout_engine",
                    missing_computation="parking_target_traceability",
                    source_fields=parking_program.get("source_fields") or ["site_plan.parking_count", "project_type"],
                    failure_type="missing_input",
                    reason_class="parking_target_undefined",
                    category="parking",
                    context=parking_program,
                )
            )
        else:
            target = safe_int(parking_program.get("requested_target"), 0)
            achieved = safe_int(parking_program.get("achieved_count"), 0)
            upper_tolerance = max(int(round(target * 1.50)), target + 30)
            if target > 0 and (achieved < target or achieved > upper_tolerance):
                failures.append(
                    _manual_failure(
                        gate_name,
                        "layout",
                        "MANUAL_PARKING_VARIANCE_EXCESSIVE",
                        "Assisted off requires parking output to remain within a traceable target range; the current layout materially misses that target.",
                        engine="layout_engine",
                        missing_computation="parking_target_comparison",
                        source_fields=parking_program.get("source_fields") or ["site_plan.parking_count"],
                        failure_type="incomplete_postprocessing",
                        reason_class="parking_program_mismatch",
                        category="parking",
                        context=parking_program,
                    )
                )

    elif gate_name == "grading_gate":
        if not field_path_is_omitted(parsed, "grading"):
            grading = gate_stage("grading")
            stage = _latest_stage_result(ctx, "grading")
            stage_meta = safe_dict(getattr(stage, "meta", {}))
            derived = safe_dict(grading.get("derived_actions"))
            if not derived:
                derived = safe_dict(grading.get("stats"))
            if stage_meta.get("fallback_used"):
                failures.append(
                    _manual_failure(
                        gate_name,
                        "grading",
                        "MANUAL_GRADING_FALLBACK_USED",
                        "Assisted off does not allow grading fallback or placeholder grading geometry.",
                        engine="grading_engine",
                        missing_computation="real_surface_solution",
                        source_fields=["terrain", "grading", "lot"],
                        failure_type="engine_failure",
                        reason_class="fallback_used",
                        category="grading",
                        context=stage_meta,
                    )
                )
            if not safe_dict(grading.get("existing_surface")) or not safe_dict(grading.get("proposed_surface")):
                failures.append(
                    _manual_failure(
                        gate_name,
                        "grading",
                        "MANUAL_GRADING_SURFACES_MISSING",
                        "Assisted off requires both existing and proposed grading surfaces.",
                        engine="grading_engine",
                        missing_computation="existing_and_proposed_surfaces",
                        source_fields=["terrain", "grading", "lot"],
                        failure_type="incomplete_postprocessing",
                        reason_class="surface_output_missing",
                        category="grading",
                    )
                )
            if safe_int(derived.get("proposed_contour_count"), 0) <= 0 or safe_int(derived.get("spot_grade_count"), 0) <= 0 or safe_int(derived.get("flow_arrow_count"), 0) <= 0:
                failures.append(
                    _manual_failure(
                        gate_name,
                        "grading",
                        "MANUAL_GRADING_DELIVERABLES_INCOMPLETE",
                        "Assisted off requires real grading deliverables including contours, spot grades, and flow arrows.",
                        engine="grading_engine",
                        missing_computation="grading_deliverables",
                        source_fields=["grading", "terrain"],
                        failure_type="incomplete_postprocessing",
                        reason_class="grading_deliverables_missing",
                        category="grading",
                        context=derived,
                    )
                )
            earthwork = [
                safe_float(safe_dict(safe_dict(plan.get("meta")).get("manager_export")).get("metrics", {}).get("earthwork_cut_cf", {}).get("value"), 0.0),
                safe_float(safe_dict(safe_dict(plan.get("meta")).get("manager_export")).get("metrics", {}).get("earthwork_fill_cf", {}).get("value"), 0.0),
                safe_float(safe_dict(safe_dict(plan.get("meta")).get("manager_export")).get("metrics", {}).get("earthwork_net_cf", {}).get("value"), 0.0),
            ]
            if max(abs(v) for v in earthwork) <= 0.0:
                failures.append(
                    _manual_failure(
                        gate_name,
                        "grading",
                        "MANUAL_EARTHWORK_MISSING",
                        "Assisted off requires cut, fill, and net grading volume outputs when grading is requested.",
                        engine="grading_engine",
                        missing_computation="earthwork_volumes",
                        source_fields=["grading", "terrain"],
                        failure_type="incomplete_postprocessing",
                        reason_class="earthwork_missing",
                        category="grading",
                    )
                )

    elif gate_name == "drainage_gate":
        if not field_path_is_omitted(parsed, "drainage"):
            drainage = gate_stage("drainage")
            stats = safe_dict(drainage.get("stats"))
            coordination = safe_dict(drainage.get("coordination"))
            if not drainage or not bool(drainage.get("success", False)):
                failures.append(
                    _manual_failure(
                        gate_name,
                        "drainage",
                        "MANUAL_DRAINAGE_OUTPUT_MISSING",
                        "Assisted off requires a complete drainage output with canonical structures and pipe runs.",
                        engine="drainage_engine",
                        missing_computation="drainage_network",
                        source_fields=["drainage", "lot", "terrain"],
                        failure_type="engine_failure",
                        reason_class="drainage_output_missing",
                        category="drainage",
                    )
                )
            if safe_int(stats.get("inlet_count"), 0) <= 0 or safe_int(stats.get("pipe_count"), 0) <= 0:
                failures.append(
                    _manual_failure(
                        gate_name,
                        "drainage",
                        "MANUAL_DRAINAGE_NETWORK_INCOMPLETE",
                        "Assisted off requires real inlet and pipe network outputs instead of placeholder drainage geometry.",
                        engine="drainage_engine",
                        missing_computation="inlet_and_pipe_generation",
                        source_fields=["drainage", "terrain"],
                        failure_type="incomplete_postprocessing",
                        reason_class="network_incomplete",
                        category="drainage",
                        context=stats,
                    )
                )
            if gate_stage("grading") and (
                not safe_dict(coordination.get("preferred_outfall")) or not safe_list(coordination.get("preferred_targets"))
            ):
                failures.append(
                    _manual_failure(
                        gate_name,
                        "drainage",
                        "MANUAL_DRAINAGE_GRADING_COORDINATION_MISSING",
                        "Assisted off requires drainage placement to stay coordinated with grading low points and outfall logic.",
                        engine="drainage_engine",
                        missing_computation="surface_derived_drainage_coordination",
                        source_fields=["terrain", "grading", "drainage"],
                        failure_type="incomplete_postprocessing",
                        reason_class="grading_coordination_missing",
                        category="drainage",
                    )
                )

    elif gate_name == "storm_pipe_gate":
        if not field_path_is_omitted(parsed, "drainage"):
            storm = gate_stage("storm_pipes")
            segments = safe_list(storm.get("segments"))
            if segments:
                required_keys = {
                    "total_system_flow_cfs",
                    "total_system_capacity_cfs",
                    "controlling_segment",
                    "max_capacity_ratio",
                    "missing_data_segments",
                    "hydraulic_source",
                    "source_detail",
                    "pipe_count",
                }
                if (
                    not safe_dict(storm.get("graph_validation"))
                    or not safe_dict(storm.get("hydraulic_validation"))
                    or any(key not in storm for key in required_keys)
                ):
                    _recompute_storm_summary(project, manager)
                    storm = gate_stage("storm_pipes")
                    segments = safe_list(storm.get("segments"))
                if not safe_dict(storm.get("graph_validation")):
                    storm["graph_validation"] = _validate_network_graph({"segments": segments}, "storm")
                if not safe_dict(storm.get("hydraulic_validation")):
                    storm["hydraulic_validation"] = _validate_storm_hydraulics(storm)
                missing_keys = sorted(key for key in required_keys if key not in storm)
                if missing_keys:
                    failures.append(
                        _manual_failure(
                            gate_name,
                            "storm_pipes",
                            "MANUAL_STORM_HYDRAULICS_MISSING",
                            "Assisted off requires aggregate hydraulic reporting whenever storm pipe geometry exists.",
                            engine="pipe_engine",
                            missing_computation="hydraulic_aggregation",
                            source_fields=["drainage", "pipe_network", "terrain"],
                            failure_type="incomplete_postprocessing",
                            reason_class="hydraulic_summary_missing",
                            category="pipes",
                            context={"missing_keys": missing_keys},
                        )
                    )
                if safe_list(storm.get("missing_data_segments")):
                    failures.append(
                        _manual_failure(
                            gate_name,
                            "storm_pipes",
                            "MANUAL_STORM_SEGMENT_DATA_MISSING",
                            "Assisted off requires per-segment hydraulic data, invert data, and slope consistency for all storm pipes.",
                            engine="pipe_engine",
                            missing_computation="per_segment_hydraulic_reporting",
                            source_fields=["drainage", "pipe_network"],
                            failure_type="incomplete_postprocessing",
                            reason_class="segment_data_missing",
                            category="pipes",
                            context={"missing_data_segments": safe_list(storm.get("missing_data_segments"))},
                        )
                    )
                hydraulic_validation = safe_dict(storm.get("hydraulic_validation"))
                if not bool(hydraulic_validation.get("valid", False)):
                    failures.append(
                        _manual_failure(
                            gate_name,
                            "storm_pipes",
                            "MANUAL_STORM_HYDRAULIC_INVALID",
                            "Assisted off requires every storm segment to have complete hydraulic lineage, accumulation, and capacity validity.",
                            engine="pipe_engine",
                            missing_computation="storm_hydraulic_validation",
                            source_fields=["storm_pipes", "drainage", "pipe_network"],
                            failure_type="incomplete_postprocessing",
                            reason_class="hydraulic_validation_failed",
                            category="pipes",
                            context=deepcopy(hydraulic_validation),
                        )
                    )
                if not bool(safe_dict(storm.get("graph_validation")).get("valid", False)):
                    failures.append(
                        _manual_failure(
                            gate_name,
                            "storm_pipes",
                            "MANUAL_STORM_GRAPH_INVALID",
                            "Assisted off requires storm pipes to remain connected and directionally valid after routing and reroutes.",
                            engine="pipe_engine",
                            missing_computation="storm_graph_validation",
                            source_fields=["storm_pipes", "drainage", "pipe_network"],
                            failure_type="incomplete_postprocessing",
                            reason_class="graph_invalid",
                            category="pipes",
                            context={"graph_validation": safe_dict(storm.get("graph_validation"))},
                        )
                    )

    elif gate_name == "sanitary_gate":
        if _sanitary_requested(parsed):
            sanitary = gate_stage("sanitary")
            if sanitary and safe_list(sanitary.get("segments")):
                required_keys = {
                    "manhole_count",
                    "disconnected_segments",
                    "missing_data_segments",
                    "total_system_capacity_cfs",
                    "max_capacity_ratio",
                    "controlling_segment",
                }
                if (
                    not safe_dict(sanitary.get("graph_validation"))
                    or not safe_dict(sanitary.get("network_validation"))
                    or any(key not in sanitary for key in required_keys)
                ):
                    _recompute_sanitary_summary(project, manager)
                    sanitary = gate_stage("sanitary")
                if not safe_dict(sanitary.get("graph_validation")):
                    sanitary["graph_validation"] = _validate_network_graph(sanitary, "sanitary")
                if not safe_dict(sanitary.get("network_validation")):
                    sanitary["network_validation"] = _validate_sanitary_network(sanitary)
                missing_keys = sorted(key for key in required_keys if key not in sanitary)
                if missing_keys:
                    failures.append(
                        _manual_failure(
                            gate_name,
                            "sanitary",
                            "MANUAL_SANITARY_CANONICAL_FIELDS_MISSING",
                            "Assisted off requires complete canonical sanitary sizing, capacity, connectivity, and missing-data fields.",
                            engine="sanitary_engine",
                            missing_computation="sanitary_canonical_summary",
                            source_fields=["sanitary", "site_plan", "utility_network", "grading"],
                            failure_type="incomplete_postprocessing",
                            reason_class="canonical_fields_missing",
                            category="sanitary",
                            context={"missing_keys": missing_keys},
                        )
                    )
                if safe_list(sanitary.get("missing_data_segments")):
                    failures.append(
                        _manual_failure(
                            gate_name,
                            "sanitary",
                            "MANUAL_SANITARY_SEGMENT_DATA_MISSING",
                            "Assisted off requires per-segment sanitary capacity, slope, cover, and node data.",
                            engine="sanitary_engine",
                            missing_computation="per_segment_sanitary_reporting",
                            source_fields=["sanitary", "site_plan", "utility_network", "grading"],
                            failure_type="incomplete_postprocessing",
                            reason_class="segment_data_missing",
                            category="sanitary",
                            context={"missing_data_segments": safe_list(sanitary.get("missing_data_segments"))},
                        )
                    )
            if not sanitary or not bool(sanitary.get("success", False)):
                failures.append(
                    _manual_failure(
                        gate_name,
                        "sanitary",
                        "MANUAL_SANITARY_OUTPUT_MISSING",
                        "Assisted off requires a real sanitary routing result when sanitary deliverables are requested.",
                        engine="sanitary_engine",
                        missing_computation="sanitary_routing",
                        source_fields=["deliverables", "utility_network", "lot", "site_plan"],
                        failure_type="engine_failure",
                        reason_class="sanitary_output_missing",
                        category="sanitary",
                    )
                )
            if bool(sanitary.get("fallback_used")):
                failures.append(
                    _manual_failure(
                        gate_name,
                        "sanitary",
                        "MANUAL_SANITARY_FALLBACK_USED",
                        "Assisted off does not allow fallback or placeholder sanitary output.",
                        engine="sanitary_engine",
                        missing_computation="canonical_sanitary_routing",
                        source_fields=["deliverables", "utility_network", "lot", "site_plan"],
                        failure_type="engine_failure",
                        reason_class="fallback_used",
                        category="sanitary",
                        context=sanitary,
                    )
                )
            if safe_int(sanitary.get("route_count"), 0) <= 0 or safe_int(sanitary.get("service_count"), 0) <= 0:
                failures.append(
                    _manual_failure(
                        gate_name,
                        "sanitary",
                        "MANUAL_SANITARY_NETWORK_INCOMPLETE",
                        "Assisted off requires sanitary mains, laterals, and service connections for requested sanitary output.",
                        engine="sanitary_engine",
                        missing_computation="sanitary_network_components",
                        source_fields=["deliverables", "site_plan", "lot"],
                        failure_type="incomplete_postprocessing",
                        reason_class="network_incomplete",
                        category="sanitary",
                        context=sanitary,
                    )
                )
            if safe_list(sanitary.get("missing_service_buildings")):
                failures.append(
                    _manual_failure(
                        gate_name,
                        "sanitary",
                        "MANUAL_SANITARY_BUILDING_SERVICE_MISSING",
                        "Assisted off requires every served building or pad to have a sanitary service connection.",
                        engine="sanitary_engine",
                        missing_computation="building_service_connections",
                        source_fields=["site_plan", "lot", "building_geometry"],
                        failure_type="incomplete_postprocessing",
                        reason_class="missing_service_buildings",
                        category="sanitary",
                        context={"missing_service_buildings": safe_list(sanitary.get("missing_service_buildings"))},
                    )
                )
            if safe_list(sanitary.get("slope_violations")):
                failures.append(
                    _manual_failure(
                        gate_name,
                        "sanitary",
                        "MANUAL_SANITARY_SLOPE_VIOLATION",
                        "Assisted off requires sanitary runs to satisfy minimum gravity slope rules.",
                        engine="sanitary_engine",
                        missing_computation="sanitary_slope_validation",
                        source_fields=["grading", "utility_network", "site_plan"],
                        failure_type="incomplete_postprocessing",
                        reason_class="slope_violation",
                        category="sanitary",
                        context={"slope_violations": safe_list(sanitary.get("slope_violations"))},
                    )
                )
            if safe_list(sanitary.get("disconnected_segments")):
                failures.append(
                    _manual_failure(
                        gate_name,
                        "sanitary",
                        "MANUAL_SANITARY_DISCONNECTED",
                        "Assisted off requires sanitary segments to remain connected from served buildings to the downstream tie-in.",
                        engine="sanitary_engine",
                        missing_computation="sanitary_connectivity",
                        source_fields=["site_plan", "lot", "utility_network"],
                        failure_type="incomplete_postprocessing",
                        reason_class="disconnected_network",
                        category="sanitary",
                        context={"disconnected_segments": safe_list(sanitary.get("disconnected_segments"))},
                    )
                )
            if not bool(safe_dict(sanitary.get("graph_validation")).get("valid", False)):
                failures.append(
                    _manual_failure(
                        gate_name,
                        "sanitary",
                        "MANUAL_SANITARY_GRAPH_INVALID",
                        "Assisted off requires sanitary routing to remain connected and graph-valid after sizing and reroutes.",
                        engine="sanitary_engine",
                        missing_computation="sanitary_graph_validation",
                        source_fields=["sanitary", "site_plan", "utility_network"],
                        failure_type="incomplete_postprocessing",
                        reason_class="graph_invalid",
                        category="sanitary",
                        context={"graph_validation": safe_dict(sanitary.get("graph_validation"))},
                    )
                )
            if safe_list(sanitary.get("missing_manhole_points")):
                failures.append(
                    _manual_failure(
                        gate_name,
                        "sanitary",
                        "MANUAL_SANITARY_MANHOLES_MISSING",
                        "Assisted off requires manholes at sanitary bends, junctions, and spacing intervals.",
                        engine="sanitary_engine",
                        missing_computation="manhole_placement",
                        source_fields=["utility_network", "site_plan", "lot"],
                        failure_type="incomplete_postprocessing",
                        reason_class="missing_manhole_points",
                        category="sanitary",
                        context={"missing_manhole_points": safe_list(sanitary.get("missing_manhole_points"))},
                    )
                )
            coordination_summary = safe_dict(safe_dict(plan.get("meta")).get("coordination"))
            unresolved_coordination = safe_list(coordination_summary.get("unresolved_conflicts"))
            unresolved_sanitary_storm = [
                item
                for item in unresolved_coordination
                if "sanitary" in {lower_text(system) for system in safe_list(safe_dict(item).get("systems"))}
                and "storm" in {lower_text(system) for system in safe_list(safe_dict(item).get("systems"))}
            ]
            if _storm_requested(parsed) and safe_list(sanitary.get("storm_conflicts")) and (not coordination_summary or unresolved_sanitary_storm):
                failures.append(
                    _manual_failure(
                        gate_name,
                        "sanitary",
                        "MANUAL_SANITARY_STORM_CONFLICT",
                        "Assisted off requires sanitary routing to stay coordinated with storm infrastructure.",
                        engine="sanitary_engine",
                        missing_computation="storm_sanitary_coordination",
                        source_fields=["storm_pipes", "sanitary", "grading"],
                        failure_type="incomplete_postprocessing",
                        reason_class="storm_sanitary_conflict",
                        category="sanitary",
                        context={"storm_conflicts": safe_list(sanitary.get("storm_conflicts"))},
                    )
                )
            if not bool(safe_dict(sanitary.get("network_validation")).get("valid", False)):
                failures.append(
                    _manual_failure(
                        gate_name,
                        "sanitary",
                        "MANUAL_SANITARY_NETWORK_INVALID",
                        "Assisted off requires sanitary network validation to pass for slope, connectivity, cover, tie-ins, and manhole completeness.",
                        engine="sanitary_engine",
                        missing_computation="sanitary_network_validation",
                        source_fields=["sanitary", "site_plan", "utility_network", "grading"],
                        failure_type="incomplete_postprocessing",
                        reason_class="network_validation_failed",
                        category="sanitary",
                        context=deepcopy(safe_dict(sanitary.get("network_validation"))),
                    )
                )

    elif gate_name == "utility_gate":
        utilities = gate_stage("utilities")
        stage = _latest_stage_result(ctx, "utility_network")
        if safe_dict(getattr(stage, "meta", {})).get("fallback_used") or bool(utilities.get("fallback_used")):
            failures.append(
                _manual_failure(
                    gate_name,
                    "utility_network",
                    "MANUAL_UTILITY_FALLBACK_USED",
                    "Assisted off does not allow utility fallback routing.",
                    engine="utility_engine",
                    missing_computation="coordinated_utility_routing",
                    source_fields=["utility_network", "lot", "grading", "drainage"],
                    failure_type="engine_failure",
                    reason_class="fallback_used",
                    category="utilities",
                    context=utilities,
                )
            )
            return _record_manual_gate_result(ctx, gate_name, failures)
        if not field_path_is_omitted(parsed, "utility_network"):
            deliverables = {lower_text(item) for item in safe_list(parsed.get("deliverables")) if safe_str(item)}
            utility_required = any("utility" in item or "water" in item for item in deliverables) or _user_supplied_geometry_available(parsed, "utility_network")
            if not utility_required:
                return _record_manual_gate_result(ctx, gate_name, failures)
            if safe_int(utilities.get("route_count"), 0) <= 0:
                failures.append(
                    _manual_failure(
                        gate_name,
                        "utility_network",
                        "MANUAL_UTILITY_OUTPUT_MISSING",
                        "Assisted off requires utility routing outputs for the intended strong utility engine path.",
                        engine="utility_engine",
                        missing_computation="utility_network_output",
                        source_fields=["utility_network", "lot"],
                        failure_type="incomplete_postprocessing",
                        reason_class="route_output_missing",
                        category="utilities",
                    )
                )

    elif gate_name == "quantities_gate":
        truth_audit = _canonical_truth_audit(parsed, plan, manager)
        accounting = _canonical_area_accounting(parsed, plan)
        lot_area = safe_float(accounting.get("lot_area_sf"), 0.0)
        impervious_area = safe_float(accounting.get("impervious_area_sf"), 0.0)
        if lot_area > 0.0 and impervious_area > lot_area:
            failures.append(
                _manual_failure(
                    gate_name,
                    "quantities",
                    "MANUAL_SITE_AREA_INCONSISTENT",
                    "Assisted off failed because canonical impervious/site area accounting is inconsistent.",
                    engine="quantity_engine",
                    missing_computation="canonical_area_reconciliation",
                    source_fields=["lot", "site_plan", "manager_export", "quantities", "qa.stats"],
                    failure_type="incomplete_postprocessing",
                    reason_class=safe_str(accounting.get("reason_class"), "accounting_bug"),
                    category="site",
                    context=accounting,
                )
            )

        meta = safe_dict(plan.get("meta"))
        qty = safe_dict(safe_dict(meta.get("quantities")).get("totals"))
        qa_stats = safe_dict(safe_dict(meta.get("qa")).get("stats"))
        manager_metrics = safe_dict(safe_dict(meta.get("manager_export")).get("metrics"))

        consistency_checks = [
            (
                "estimated_impervious_area_sf",
                safe_float(qty.get("estimated_impervious_area_sf"), 0.0),
                max(
                    safe_float(qa_stats.get("estimated_impervious_area_sf"), 0.0),
                    safe_float(safe_dict(manager_metrics.get("layout_impervious_area_sf")).get("value"), 0.0),
                ),
            ),
            (
                "pipe_length_ft",
                safe_float(qty.get("pipe_length_ft"), 0.0),
                max(
                    safe_float(qa_stats.get("estimated_pipe_length_ft"), 0.0),
                    safe_float(safe_dict(manager_metrics.get("storm_pipe_length_ft")).get("value"), 0.0),
                    safe_float(safe_dict(manager_metrics.get("pipe_total_length_ft")).get("value"), 0.0),
                ),
            ),
            (
                "utility_length_ft",
                safe_float(qty.get("utility_length_ft"), 0.0),
                max(
                    safe_float(qa_stats.get("estimated_utility_length_ft"), 0.0),
                    safe_float(safe_dict(manager_metrics.get("utility_total_length_ft")).get("value"), 0.0),
                ),
            ),
            (
                "sanitary_length_ft",
                safe_float(qty.get("sanitary_length_ft"), 0.0),
                max(
                    safe_float(safe_dict(manager_metrics.get("sanitary_total_length_ft")).get("value"), 0.0),
                    safe_float(safe_dict(safe_dict(meta.get("sanitary")).get("stats")).get("total_length_ft"), 0.0),
                ),
            ),
        ]
        inconsistent_metrics: List[str] = []
        for metric_name, qty_value, truth_value in consistency_checks:
            if truth_value > 0.0 and qty_value <= 0.0:
                inconsistent_metrics.append(metric_name)
        if inconsistent_metrics:
            failures.append(
                _manual_failure(
                    gate_name,
                    "quantities",
                    "MANUAL_QUANTITIES_INCONSISTENT",
                    "Assisted off requires quantities, QA stats, and ProjectManager metrics to stay consistent when canonical geometry exists.",
                    engine="quantity_engine",
                    missing_computation="canonical_quantity_rollup",
                    source_fields=["manager_export", "quantities", "qa.stats"],
                    failure_type="incomplete_postprocessing",
                    reason_class="quantities_missing_from_canonical_state",
                    category="quantities",
                    context={"inconsistent_metrics": inconsistent_metrics},
                )
            )
        for check in safe_list(truth_audit.get("failing_checks")):
            code = safe_str(check.get("code"))
            if code in {"PIPE_LENGTH_CONSISTENT", "UTILITY_LENGTH_CONSISTENT", "SANITARY_LENGTH_CONSISTENT", "STORM_HYDRAULIC_COMPLETE", "STORM_SEGMENT_DATA_COMPLETE", "STORM_GRAPH_VALID", "SANITARY_GRAPH_VALID", "SANITARY_SERVICE_COMPLETE", "QUANTITY_AREA_VALID"}:
                failures.append(
                    _manual_failure(
                        gate_name,
                        "quantities",
                        f"MANUAL_{code}",
                        safe_str(check.get("message"), "Manual truth audit failed."),
                        engine="planner",
                        missing_computation="canonical_truth_audit",
                        source_fields=["manager_export", "quantities", "qa.stats", "storm_pipes", "sanitary"],
                        failure_type="incomplete_postprocessing",
                        reason_class="truth_audit_failed",
                        category="quantities",
                        context=deepcopy(check),
                    )
                )
        quantity_trace = safe_dict(safe_dict(safe_dict(meta.get("quantities")).get("explain")).get("quantity_audit"))
        trace_gaps = safe_dict(safe_dict(meta.get("quantities")).get("explain")).get("trace_gaps")
        if not safe_dict(safe_dict(meta.get("quantities")).get("explain")).get("meta_summary", {}).get("quantity_traceability_complete", False):
            failures.append(
                _manual_failure(
                    gate_name,
                    "quantities",
                    "MANUAL_QUANTITY_TRACEABILITY_INCOMPLETE",
                    "Assisted off requires every materially reported quantity to trace back to canonical sources.",
                    engine="quantity_engine",
                    missing_computation="quantity_trace_audit",
                    source_fields=["quantities", "manager_export", "actions", "storm_pipes", "sanitary", "utilities"],
                    failure_type="incomplete_postprocessing",
                    reason_class="quantity_trace_incomplete",
                    category="quantities",
                    context={"trace_gaps": deepcopy(trace_gaps), "quantity_audit_keys": sorted(quantity_trace.keys())},
                )
            )

    elif gate_name == "deliverables_gate":
        truth_audit = _canonical_truth_audit(parsed, plan, manager)
        requested = _requested_deliverables(parsed)
        produced = _produced_deliverables(plan)
        meta = safe_dict(plan.get("meta"))
        missing: List[str] = []
        for deliverable in requested:
            if deliverable in {"road_profile", "profiles"} and not any(item in produced for item in {"road_profile", "profiles"}):
                missing.append(deliverable)
            elif deliverable in {"cross_sections", "cross_sections_plan"} and "cross_sections" not in produced:
                missing.append(deliverable)
            elif any(token in deliverable for token in ("storm", "pipe")) and "storm_pipe_plan" not in produced:
                missing.append(deliverable)
            elif any(token in deliverable for token in ("utility", "utilities")) and "utility_plan" not in produced:
                missing.append(deliverable)
            elif any(token in deliverable for token in ("sanitary", "sewer")) and "sanitary_plan" not in produced:
                missing.append(deliverable)
            elif any(token in deliverable for token in ("drainage", "basin", "inlet")) and "drainage_plan" not in produced:
                missing.append(deliverable)
            elif any(token in deliverable for token in ("grading", "contour", "spot")) and not any(
                item in produced for item in {"grading_plan", "contours", "spot_grades"}
            ):
                missing.append(deliverable)
        if missing:
            failures.append(
                _manual_failure(
                    gate_name,
                    "deliverables",
                    "MANUAL_DELIVERABLES_MISSING",
                    "Assisted off requires requested deliverables to be generated from real canonical content, not just requested intent.",
                    engine="planner",
                    missing_computation="deliverable_generation",
                    source_fields=["deliverables", "grading", "storm_pipes"],
                    failure_type="incomplete_postprocessing",
                    reason_class="requested_deliverables_missing",
                    category="deliverables",
                    context={"requested": requested, "produced": produced, "missing": missing},
                )
            )
        for check in safe_list(truth_audit.get("failing_checks")):
            code = safe_str(check.get("code"))
            if code in {"STORM_DELIVERABLE_MATCH", "SANITARY_DELIVERABLE_MATCH", "STORM_SUMMARY_CURRENT", "SANITARY_SUMMARY_CURRENT", "UTILITY_SUMMARY_CURRENT", "DRAINAGE_SUMMARY_CURRENT"}:
                failures.append(
                    _manual_failure(
                        gate_name,
                        "deliverables",
                        f"MANUAL_{code}",
                        safe_str(check.get("message"), "Manual deliverable truth audit failed."),
                        engine="planner",
                        missing_computation="deliverable_truth_audit",
                        source_fields=["deliverables", "storm_pipes", "sanitary", "utilities", "coordination"],
                        failure_type="incomplete_postprocessing",
                        reason_class="deliverable_truth_mismatch",
                        category="deliverables",
                        context=deepcopy(check),
                    )
                )
        wants_profiles = any(item in requested for item in {"road_profile", "profiles"})
        if wants_profiles and any("storm" in item or "pipe" in item for item in requested):
            storm = safe_dict(meta.get("storm_pipes"))
            segments = [safe_dict(item) for item in safe_list(storm.get("segments")) if safe_dict(item)]
            if segments:
                missing_fields = sorted(
                    {
                        key
                        for segment in segments
                        for key in ("diameter_in", "slope_pct", "start_invert", "end_invert", "flow_cfs", "capacity_cfs", "capacity_ratio", "from", "to")
                        if key not in segment or segment.get(key) in (None, "")
                    }
                )
                if missing_fields:
                    failures.append(
                        _manual_failure(
                            gate_name,
                            "profiles",
                            "MANUAL_STORM_PROFILE_BAND_DATA_MISSING",
                            "Assisted off requires storm profile bands to be populated from real canonical pipe hydraulics and structure data.",
                            engine="pipe_engine",
                            missing_computation="storm_profile_bands",
                            source_fields=["storm_pipes", "profiles", "deliverables"],
                            failure_type="incomplete_postprocessing",
                            reason_class="storm_profile_band_data_missing",
                            category="deliverables",
                            context={"missing_fields": missing_fields},
                        )
                    )
        if wants_profiles and any("sanitary" in item or "sewer" in item for item in requested):
            sanitary = safe_dict(meta.get("sanitary"))
            segments = [safe_dict(item) for item in safe_list(sanitary.get("segments")) if safe_dict(item) and safe_str(item.get("segment_role")) == "main"]
            if segments:
                missing_fields = sorted(
                    {
                        key
                        for segment in segments
                        for key in ("diameter_in", "start_invert_ft", "end_invert_ft", "start_name", "end_name")
                        if key not in segment or segment.get(key) in (None, "")
                    }
                )
                if missing_fields:
                    failures.append(
                        _manual_failure(
                            gate_name,
                            "profiles",
                            "MANUAL_SANITARY_PROFILE_BAND_DATA_MISSING",
                            "Assisted off requires sanitary profile bands to be populated from real canonical sanitary routing data.",
                            engine="sanitary_engine",
                            missing_computation="sanitary_profile_bands",
                            source_fields=["sanitary", "profiles", "deliverables"],
                            failure_type="incomplete_postprocessing",
                            reason_class="sanitary_profile_band_data_missing",
                            category="deliverables",
                            context={"missing_fields": missing_fields},
                    )
                )

    elif gate_name == "coordination_gate":
        meta = safe_dict(plan.get("meta"))
        coordination = safe_dict(meta.get("coordination"))
        unresolved = safe_list(coordination.get("unresolved_conflicts"))
        assumptions = safe_list(coordination.get("assumption_resolutions"))
        deliverables = {lower_text(item) for item in safe_list(parsed.get("deliverables")) if safe_str(item)}
        sanitary_only_deliverable = bool(deliverables) and deliverables.issubset({"sanitary_plan"})
        coordination_required = (
            (bool(unresolved) and not sanitary_only_deliverable)
            or _storm_requested(parsed)
            or any("utility" in item or "coordination" in item or "full" in item for item in deliverables)
        )
        if coordination_required and unresolved:
            failures.append(
                _manual_failure(
                    gate_name,
                    "coordination",
                    "MANUAL_COORDINATION_UNRESOLVED",
                    "Assisted off requires utility and pipe conflicts to be fully resolved before final output.",
                    engine="coordination_resolution",
                    missing_computation="conflict_resolution",
                    source_fields=["storm_pipes", "sanitary", "utilities", "grading"],
                    failure_type="incomplete_postprocessing",
                    reason_class="unresolved_conflicts",
                    category="coordination",
                    context={"unresolved_conflicts": deepcopy(unresolved)},
                )
            )
        if assumptions:
            failures.append(
                _manual_failure(
                    gate_name,
                    "coordination",
                    "MANUAL_COORDINATION_ASSUMPTION_USED",
                    "Assisted off does not allow coordination conflicts to be closed with assumption-based fixes.",
                    engine="coordination_resolution",
                    missing_computation="deterministic_conflict_resolution",
                    source_fields=["storm_pipes", "sanitary", "utilities", "grading"],
                    failure_type="incomplete_postprocessing",
                    reason_class="assumption_resolution_used",
                    category="coordination",
                    context={"assumption_resolutions": deepcopy(assumptions)},
                )
            )

    return _record_manual_gate_result(ctx, gate_name, failures)


def _direction_vector(name: str) -> Optional[Tuple[float, float]]:
    key = lower_text(name).replace("-", "").replace("_", "").replace(" ", "")
    mapping = {
        "n": (0.0, 1.0),
        "north": (0.0, 1.0),
        "s": (0.0, -1.0),
        "south": (0.0, -1.0),
        "e": (1.0, 0.0),
        "east": (1.0, 0.0),
        "w": (-1.0, 0.0),
        "west": (-1.0, 0.0),
        "ne": (1.0, 1.0),
        "northeast": (1.0, 1.0),
        "nw": (-1.0, 1.0),
        "northwest": (-1.0, 1.0),
        "se": (1.0, -1.0),
        "southeast": (1.0, -1.0),
        "sw": (-1.0, -1.0),
        "southwest": (-1.0, -1.0),
    }
    return mapping.get(key)


def _normalize_vector(dx: float, dy: float) -> Tuple[float, float]:
    mag = max((dx * dx + dy * dy) ** 0.5, 1e-9)
    return dx / mag, dy / mag


def _infer_surface_profile(parsed: Dict[str, Any]) -> Dict[str, Any]:
    terrain_text = safe_str(parsed.get("terrain"), "")
    grading = safe_dict(parsed.get("grading"))
    minimum_pct = safe_float(grading.get("min_slope_pct"), 2.0)
    corner_elevations = safe_dict(grading.get("corner_elevations"))
    profile = {
        "terrain_text": terrain_text,
        "inferred": False,
        "slope_ratio": max(0.002, minimum_pct / 100.0 if minimum_pct > 0 else 0.02),
        "downhill_dx": 1.0,
        "downhill_dy": -0.3,
        "source": "default",
    }
    if corner_elevations.get("northwest") is not None and corner_elevations.get("southeast") is not None:
        lot = safe_dict(parsed.get("lot"))
        lot_w = safe_float(lot.get("w"), DEFAULT_LOT_WIDTH)
        lot_h = safe_float(lot.get("h"), DEFAULT_LOT_HEIGHT)
        diagonal = max((lot_w ** 2 + lot_h ** 2) ** 0.5, 1.0)
        dz = safe_float(corner_elevations.get("northwest"), 0.0) - safe_float(corner_elevations.get("southeast"), 0.0)
        profile["slope_ratio"] = max(0.002, abs(dz) / diagonal)
        profile["downhill_dx"], profile["downhill_dy"] = _normalize_vector(1.0, -1.0)
        profile["corner_elevations"] = {
            "northwest": safe_float(corner_elevations.get("northwest"), 0.0),
            "southeast": safe_float(corner_elevations.get("southeast"), 0.0),
        }
        profile["inferred"] = True
        profile["source"] = "corner_elevations"
        return profile
    if not terrain_text:
        profile["inferred"] = True
        profile["source"] = "default_min_slope"
        return profile

    text = lower_text(terrain_text)
    percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if percent_match:
        profile["slope_ratio"] = max(0.002, safe_float(percent_match.group(1), minimum_pct) / 100.0)

    directional_match = re.search(
        r"(northwest|northeast|southwest|southeast|north|south|east|west|nw|ne|sw|se)\s*(?:to|->|toward|towards)\s*(northwest|northeast|southwest|southeast|north|south|east|west|nw|ne|sw|se)",
        text,
    )
    if directional_match:
        start_vec = _direction_vector(directional_match.group(1))
        end_vec = _direction_vector(directional_match.group(2))
        if start_vec and end_vec:
            profile["downhill_dx"], profile["downhill_dy"] = _normalize_vector(end_vec[0] - start_vec[0], end_vec[1] - start_vec[1])
            profile["inferred"] = True
            profile["source"] = "terrain_direction_pair"
            return profile

    toward_match = re.search(
        r"(?:toward|towards|falling to|sloping to|slope to|drains to)\s*(northwest|northeast|southwest|southeast|north|south|east|west|nw|ne|sw|se)",
        text,
    )
    if toward_match:
        vec = _direction_vector(toward_match.group(1))
        if vec:
            profile["downhill_dx"], profile["downhill_dy"] = _normalize_vector(*vec)
            profile["inferred"] = True
            profile["source"] = "terrain_direction_target"
            return profile

    if "flat" in text:
        profile["slope_ratio"] = 0.002
        profile["downhill_dx"], profile["downhill_dy"] = _normalize_vector(1.0, 0.0)
        profile["inferred"] = True
        profile["source"] = "terrain_flat"
        return profile

    if "graded" in text or "slope" in text or "sloped" in text:
        profile["inferred"] = True
        profile["source"] = "terrain_generic"
    return profile


def _actions_from_linear_features(features: Sequence[Dict[str, Any]], layer_default: str, text_height: float = TEXT_HEIGHT_SMALL) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for feat in features or []:
        if not isinstance(feat, dict):
            continue
        pts = safe_list(feat.get("points"))
        if len(pts) >= 2:
            layer = safe_str(feat.get("layer"), layer_default).upper()
            label = safe_str(feat.get("label"), "")
            actions.append({
                "task": "polyline",
                "origin": None,
                "points": pts,
                "closed": False,
                "width": None,
                "height": None,
                "label": label or None,
                "layer": layer,
                "text": None,
                "text_height": None,
                "center": None,
                "radius": None,
                "start_angle": None,
                "end_angle": None,
                "meta": _preview_meta_for_base_action(layer, "polyline"),
            })
            if label:
                end_pt = safe_list(pts[-1])
                if len(end_pt) >= 2:
                    actions.append({
                        "task": "text_note",
                        "origin": [safe_float(end_pt[0], 0.0), safe_float(end_pt[1], 0.0)],
                        "points": None,
                        "closed": None,
                        "width": None,
                        "height": None,
                        "label": None,
                        "layer": layer,
                        "text": label,
                        "text_height": text_height,
                        "center": None,
                        "radius": None,
                        "start_angle": None,
                        "end_angle": None,
                        "meta": _preview_meta_for_base_action(layer, "text_note"),
                    })
    return actions


def _actions_from_point_features(features: Sequence[Dict[str, Any]], layer_default: str, text_height: float = 0.9) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for feat in features or []:
        if not isinstance(feat, dict):
            continue
        x = safe_float(feat.get("x"), 0.0)
        y = safe_float(feat.get("y"), 0.0)
        layer = safe_str(feat.get("layer"), layer_default).upper()
        label = safe_str(feat.get("label"), "")
        actions.append({
            "task": "circle",
            "origin": None,
            "points": None,
            "closed": None,
            "width": None,
            "height": None,
            "label": None,
            "layer": layer,
            "text": None,
            "text_height": None,
            "center": [x, y],
            "radius": 1.0,
            "start_angle": None,
            "end_angle": None,
            "meta": _preview_meta_for_base_action(layer, "circle"),
        })
        if label:
            actions.append({
                "task": "text_note",
                "origin": [x + 1.2, y + 1.2],
                "points": None,
                "closed": None,
                "width": None,
                "height": None,
                "label": None,
                "layer": layer,
                "text": label,
                "text_height": text_height,
                "center": None,
                "radius": None,
                "start_angle": None,
                "end_angle": None,
                "meta": _preview_meta_for_base_action(layer, "text_note"),
            })
    return actions


def _drainage_structure_type(record: Dict[str, Any]) -> str:
    kind = lower_text(record.get("object_type") or record.get("structure_type") or record.get("kind") or record.get("type"))
    label = lower_text(record.get("label") or record.get("name"))
    merged = f"{kind} {label}".strip()
    if any(token in merged for token in ("outfall", "headwall", "flared")):
        return "outfall"
    if any(token in merged for token in ("junction", "jb", "manhole")):
        return "junction_box"
    if any(token in merged for token in ("basin", "cb")):
        return "catch_basin"
    if any(token in merged for token in ("curb", "inlet", "ci")):
        return "curb_inlet"
    return "inlet"


def _canonical_drainage_payload(
    *,
    inlet_records: Sequence[Any] = (),
    basin_records: Sequence[Any] = (),
    pipe_runs: Sequence[Any] = (),
    low_point_records: Sequence[Any] = (),
    flow_paths: Sequence[Any] = (),
    source: str,
    mode: str = "assisted",
    success: bool = True,
    message: str = "",
    warnings: Sequence[str] = (),
) -> Dict[str, Any]:
    structures: List[Dict[str, Any]] = []
    basins: List[Dict[str, Any]] = []
    pipes: List[Dict[str, Any]] = []
    low_points: List[Dict[str, Any]] = []
    routed_flow_paths: List[Dict[str, Any]] = []
    total_pipe_length = 0.0

    for index, record in enumerate(inlet_records or [], start=1):
        if hasattr(record, "inlet"):
            inlet = getattr(record, "inlet")
            warnings_list = [safe_str(w) for w in safe_list(getattr(record, "warnings", [])) if safe_str(w)]
            name = safe_str(getattr(inlet, "name", ""), f"INLET-{index}")
            structure_type = _drainage_structure_type({"name": name, "type": "inlet"})
            structures.append({
                "name": name,
                "object_type": "inlet",
                "structure_type": structure_type,
                "canonical_type": structure_type,
                "layer": "DRAIN",
                "x": safe_float(getattr(inlet, "x", 0.0), 0.0),
                "y": safe_float(getattr(inlet, "y", 0.0), 0.0),
                "z": safe_float(getattr(inlet, "z", 0.0), 0.0),
                "contributing_cells": safe_int(getattr(inlet, "contributing_cells", 0), 0),
                "contributing_area_sf": safe_float(getattr(inlet, "contributing_area_sf", 0.0), 0.0),
                "estimated_flow_cfs": safe_float(getattr(inlet, "estimated_flow_cfs", 0.0), 0.0),
                "target_name": safe_str(getattr(inlet, "target_name", ""), "") or None,
                "tributary_basin_name": safe_str(getattr(inlet, "tributary_basin_name", ""), "") or None,
                "warnings": warnings_list,
            })
            continue

        rec = safe_dict(record)
        structure_type = _drainage_structure_type(rec)
        structures.append({
            "name": safe_str(rec.get("name") or rec.get("label"), f"STRUCT-{index}"),
            "object_type": "inlet" if structure_type in {"inlet", "curb_inlet", "catch_basin"} else "structure",
            "structure_type": structure_type,
            "canonical_type": structure_type,
            "layer": safe_str(rec.get("layer"), "DRAIN").upper(),
            "x": safe_float(rec.get("x"), 0.0),
            "y": safe_float(rec.get("y"), 0.0),
            "z": safe_float(rec.get("z"), 0.0),
            "contributing_cells": safe_int(rec.get("contributing_cells"), 0),
            "contributing_area_sf": safe_float(rec.get("contributing_area_sf"), 0.0),
            "estimated_flow_cfs": safe_float(rec.get("estimated_flow_cfs"), 0.0),
            "target_name": safe_str(rec.get("target_name"), "") or None,
            "tributary_basin_name": safe_str(rec.get("tributary_basin_name"), "") or None,
            "warnings": [safe_str(w) for w in safe_list(rec.get("warnings")) if safe_str(w)],
        })

    for index, record in enumerate(basin_records or [], start=1):
        if hasattr(record, "sink_name"):
            basins.append({
                "id": safe_str(getattr(record, "sink_name", ""), f"BASIN-{index}"),
                "name": safe_str(getattr(record, "sink_name", ""), f"BASIN-{index}"),
                "object_type": "basin",
                "canonical_type": "detention_basin",
                "layer": "BASIN_BOUNDARY",
                "sink": list(getattr(record, "sink", ())),
                "sink_name": safe_str(getattr(record, "sink_name", ""), f"BASIN-{index}"),
                "centroid_xy": list(getattr(record, "centroid_xy", (0.0, 0.0))),
                "area_sf": safe_float(getattr(record, "area_sf", 0.0), 0.0),
                "contributing_cells": safe_int(getattr(record, "contributing_cells", 0), 0),
                "target_name": safe_str(getattr(record, "target_name", ""), "") or None,
                "average_z": safe_float(getattr(record, "average_z", 0.0), 0.0),
                "estimated_runoff_cfs": safe_float(getattr(record, "estimated_runoff_cfs", 0.0), 0.0),
                "runoff_c": safe_float(getattr(record, "runoff_c", 0.0), 0.0),
                "intensity_in_hr": safe_float(getattr(record, "intensity_in_hr", 0.0), 0.0),
            })
            continue

        rec = safe_dict(record)
        basins.append({
            "id": safe_str(rec.get("id") or rec.get("sink_name") or rec.get("name") or rec.get("label"), f"BASIN-{index}"),
            "name": safe_str(rec.get("sink_name") or rec.get("name") or rec.get("label"), f"BASIN-{index}"),
            "object_type": "basin",
            "canonical_type": safe_str(rec.get("canonical_type"), "detention_basin"),
            "layer": safe_str(rec.get("layer"), "BASIN_BOUNDARY").upper(),
            "sink": safe_list(rec.get("sink")),
            "sink_name": safe_str(rec.get("sink_name") or rec.get("name") or rec.get("label"), f"BASIN-{index}"),
            "centroid_xy": safe_list(rec.get("centroid_xy")),
            "area_sf": safe_float(rec.get("area_sf"), 0.0),
            "contributing_cells": safe_int(rec.get("contributing_cells"), 0),
            "target_name": safe_str(rec.get("target_name"), "") or None,
            "average_z": safe_float(rec.get("average_z"), 0.0),
            "estimated_runoff_cfs": safe_float(rec.get("estimated_runoff_cfs"), 0.0),
            "runoff_c": safe_float(rec.get("runoff_c"), 0.0),
            "intensity_in_hr": safe_float(rec.get("intensity_in_hr"), 0.0),
        })

    for index, run in enumerate(pipe_runs or [], start=1):
        if hasattr(run, "label"):
            path = list(getattr(run, "path", None) or [getattr(run, "start", (0.0, 0.0)), getattr(run, "end", (0.0, 0.0))])
            length = polyline_length(path)
            total_pipe_length += length
            pipes.append({
                "name": safe_str(getattr(run, "label", ""), f"PIPE-{index}"),
                "object_type": "pipe_run",
                "canonical_type": "storm_pipe",
                "layer": "PIPE",
                "path": path,
                "length_ft": round(length, 3),
                "diameter_in": getattr(run, "diameter_in", None),
                "flow_cfs": getattr(run, "flow_cfs", None),
                "slope": getattr(run, "slope", None),
                "warnings": [safe_str(w) for w in safe_list(getattr(run, "warnings", [])) if safe_str(w)],
            })
            continue

        rec = safe_dict(run)
        path = safe_list(rec.get("path"))
        length = safe_float(rec.get("length_ft"), polyline_length(path))
        total_pipe_length += length
        pipes.append({
            "name": safe_str(rec.get("label") or rec.get("name"), f"PIPE-{index}"),
            "object_type": "pipe_run",
            "canonical_type": safe_str(rec.get("canonical_type"), "storm_pipe"),
            "layer": safe_str(rec.get("layer"), "PIPE").upper(),
            "path": path,
            "length_ft": round(length, 3),
            "diameter_in": rec.get("diameter_in"),
            "flow_cfs": rec.get("flow_cfs"),
            "slope": rec.get("slope"),
            "warnings": [safe_str(w) for w in safe_list(rec.get("warnings")) if safe_str(w)],
        })

    for index, record in enumerate(low_point_records or [], start=1):
        rec = safe_dict(record)
        if not rec:
            continue
        low_points.append({
            "id": safe_str(rec.get("name"), f"LOW-{index}"),
            "name": safe_str(rec.get("name"), f"LOW-{index}"),
            "x": round(safe_float(rec.get("x"), 0.0), 3),
            "y": round(safe_float(rec.get("y"), 0.0), 3),
            "z": round(safe_float(rec.get("z"), 0.0), 3),
            "row": safe_int(rec.get("row"), 0),
            "col": safe_int(rec.get("col"), 0),
            "contributing_cells": safe_int(rec.get("contributing_cells"), 0),
        })

    for index, route in enumerate(flow_paths or [], start=1):
        path: List[List[float]] = []
        target_name = None
        if isinstance(route, dict):
            rec = safe_dict(route)
            target_name = safe_str(rec.get("target_name") or rec.get("target"), "") or None
            raw_path = safe_list(rec.get("path") or rec.get("points"))
        elif isinstance(route, (list, tuple)):
            raw_path = safe_list(route[0]) if len(route) >= 1 else []
            target_name = safe_str(route[1], "") or None if len(route) > 1 else None
        else:
            raw_path = []
        for pt in raw_path:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                path.append([round(safe_float(pt[0], 0.0), 3), round(safe_float(pt[1], 0.0), 3)])
        if len(path) < 2:
            continue
        routed_flow_paths.append({
            "id": f"FLOW-{index}",
            "path": path,
            "target_name": target_name,
            "length_ft": round(polyline_length(path), 3),
        })

    has_flow_paths = bool(pipes) or bool(structures) or bool(basins) or bool(routed_flow_paths)
    return {
        "schema_version": "v1",
        "source": source,
        "mode": safe_str(mode, "assisted"),
        "success": bool(success),
        "message": safe_str(message, ""),
        "warnings": [safe_str(w) for w in warnings if safe_str(w)],
        "structures": structures,
        "basins": basins,
        "pipes": pipes,
        "low_points": low_points,
        "flow_paths": routed_flow_paths,
        "stats": {
            "inlet_count": sum(1 for item in structures if item.get("object_type") == "inlet"),
            "structure_count": len(structures),
            "basin_count": len(basins),
            "pipe_count": len(pipes),
            "low_point_count": len(low_points),
            "flow_path_count": len(routed_flow_paths),
            "pipe_total_length_ft": round(total_pipe_length, 3),
            "total_contributing_area_sf": round(
                sum(max(0.0, safe_float(item.get("contributing_area_sf"), 0.0)) for item in structures if item.get("object_type") == "inlet"),
                3,
            ),
            "total_estimated_inlet_flow_cfs": round(
                sum(max(0.0, safe_float(item.get("estimated_flow_cfs"), 0.0)) for item in structures if item.get("object_type") == "inlet"),
                3,
            ),
            "total_basin_runoff_cfs": round(
                sum(max(0.0, safe_float(item.get("estimated_runoff_cfs"), 0.0)) for item in basins),
                3,
            ),
            "has_flow_paths": has_flow_paths,
        },
        "surface_guidance": {},
    }


def _enrich_drainage_basins_with_engineering(
    canonical_drainage: Dict[str, Any],
    *,
    engine: Optional[DrainageEngine],
    hydrology: Dict[str, Any],
    coordination: Dict[str, Any],
) -> Dict[str, Any]:
    if engine is None:
        return canonical_drainage
    enriched = deepcopy(safe_dict(canonical_drainage))
    basins = [safe_dict(item) for item in safe_list(enriched.get("basins")) if safe_dict(item)]
    structures = [safe_dict(item) for item in safe_list(enriched.get("structures")) if safe_dict(item)]
    if not basins:
        preferred_targets = [safe_dict(item) for item in safe_list(safe_dict(enriched.get("surface_guidance")).get("preferred_targets")) if safe_dict(item)]
        preferred_target = preferred_targets[0] if preferred_targets else {}
        total_inlet_area_sf = sum(max(0.0, safe_float(item.get("contributing_area_sf"), 0.0)) for item in structures)
        total_inlet_flow_cfs = sum(max(0.0, safe_float(item.get("estimated_flow_cfs"), 0.0)) for item in structures)
        synthetic_area_sf = max(1600.0, round(max(total_inlet_area_sf * 0.08, 0.0), 3))
        target_name = safe_str(preferred_target.get("name"), "PRIMARY-DETENTION")
        target_x = safe_float(preferred_target.get("x"), 0.0)
        target_y = safe_float(preferred_target.get("y"), 0.0)
        target_z = safe_float(preferred_target.get("z"), 0.0)
        if target_x != 0.0 or target_y != 0.0 or synthetic_area_sf > 0.0:
            basins = [
                {
                    "id": target_name,
                    "name": target_name,
                    "object_type": "basin",
                    "canonical_type": "detention_basin",
                    "layer": "BASIN_BOUNDARY",
                    "sink": [],
                    "sink_name": target_name,
                    "centroid_xy": [round(target_x, 3), round(target_y, 3)],
                    "area_sf": synthetic_area_sf,
                    "contributing_cells": 0,
                    "target_name": target_name,
                    "average_z": round(target_z, 3),
                    "estimated_runoff_cfs": round(total_inlet_flow_cfs, 3),
                    "runoff_c": safe_float(hydrology.get("runoff_c"), PIPE_RUNOFF_C),
                    "intensity_in_hr": safe_float(hydrology.get("intensity_in_hr"), PIPE_INTENSITY_IN_HR),
                    "assumed": True,
                    "assumptions": [
                        "Primary detention basin footprint was synthesized from the preferred low-point target because the drainage engine did not emit an explicit basin record.",
                    ],
                }
            ]
            enriched["basins"] = deepcopy(basins)
        else:
            return enriched

    basin_cells = engine.drainage_basins(sample_step=2, min_slope=max(MIN_SLOPE, 0.001), max_steps=500)
    preferred_outfall = safe_dict(coordination.get("preferred_outfall"))
    outfall_xy = [
        safe_float(preferred_outfall.get("x"), 0.0),
        safe_float(preferred_outfall.get("y"), 0.0),
    ]
    runoff_c = safe_float(hydrology.get("runoff_c"), PIPE_RUNOFF_C)
    intensity = safe_float(hydrology.get("intensity_in_hr"), PIPE_INTENSITY_IN_HR)
    target_drawdown_hours = 48.0

    structure_flow_by_target: Dict[str, float] = {}
    for structure in safe_list(enriched.get("structures")):
        rec = safe_dict(structure)
        key = safe_str(rec.get("target_name")) or safe_str(rec.get("name"))
        if not key:
            continue
        structure_flow_by_target[key] = structure_flow_by_target.get(key, 0.0) + safe_float(
            rec.get("estimated_flow_cfs"),
            runoff_c * intensity * (safe_float(rec.get("contributing_area_sf"), 0.0) / 43560.0),
        )

    updated_basins: List[Dict[str, Any]] = []
    min_export_area_sf = max(4.0 * (safe_float(getattr(engine.surface, "cell_size", CELL_SIZE), CELL_SIZE) ** 2), 400.0)
    if len(basins) > 24:
        basins = sorted(
            basins,
            key=lambda item: (
                0 if safe_str(safe_dict(item).get("engineering_role")) == "primary_detention" else 1,
                -safe_float(safe_dict(item).get("area_sf"), 0.0),
                safe_str(safe_dict(item).get("name")),
            ),
        )[:24]
    for basin in basins:
        name = safe_str(basin.get("name"))
        sink_name = safe_str(basin.get("sink_name"), name)
        sink = safe_list(basin.get("sink"))
        sink_key: Optional[Tuple[int, int]] = None
        if len(sink) >= 2:
            sink_key = (safe_int(sink[0], 0), safe_int(sink[1], 0))
        if sink_key is None:
            match = next(
                (
                    key
                    for key in basin_cells.keys()
                    if f"SINK_{safe_int(key[0], 0)}_{safe_int(key[1], 0)}" == name
                    or f"SINK_{safe_int(key[0], 0)}_{safe_int(key[1], 0)}" == sink_name
                ),
                None,
            )
            sink_key = match

        boundary_points: List[List[float]] = []
        if sink_key is not None and sink_key in basin_cells:
            cells = safe_list(basin_cells[sink_key])
            if len(cells) > 500:
                step = max(1, len(cells) // 500)
                cells = cells[::step]
            hull = engine._convex_hull([engine._point_xy(r, c) for r, c in cells])  # type: ignore[attr-defined]
            boundary_points = [[round(pt[0], 3), round(pt[1], 3)] for pt in hull]
        top_area_sf = _polygon_area(boundary_points) or safe_float(basin.get("area_sf"), 0.0)
        centroid_xy = safe_list(basin.get("centroid_xy"))
        if not boundary_points and len(centroid_xy) >= 2 and top_area_sf > 0.0:
            side_ft = max(math.sqrt(max(top_area_sf, 1.0)), 20.0)
            half_side = side_ft / 2.0
            cx = safe_float(centroid_xy[0], 0.0)
            cy = safe_float(centroid_xy[1], 0.0)
            boundary_points = [
                [round(cx - half_side, 3), round(cy - half_side, 3)],
                [round(cx + half_side, 3), round(cy - half_side, 3)],
                [round(cx + half_side, 3), round(cy + half_side, 3)],
                [round(cx - half_side, 3), round(cy + half_side, 3)],
            ]
            top_area_sf = _polygon_area(boundary_points) or top_area_sf
        inflow_cfs = max(
            safe_float(structure_flow_by_target.get(safe_str(basin.get("target_name"))), 0.0),
            runoff_c * intensity * (safe_float(basin.get("area_sf"), 0.0) / 43560.0),
        )
        initial_release_cfs = max(0.1, inflow_cfs * 0.35)
        preliminary_detention = concept_detention_size(inflow_cfs, initial_release_cfs)
        preliminary_storage_cf = max(
            safe_float(getattr(preliminary_detention, "provided_geometry_storage_cf", 0.0), 0.0),
            safe_float(getattr(preliminary_detention, "required_storage_cf", 0.0), 0.0),
        )
        release_from_drawdown_cfs = preliminary_storage_cf / max(target_drawdown_hours * 3600.0, 1.0)
        release_cfs = max(0.1, min(inflow_cfs * 0.75, max(initial_release_cfs * 0.5, release_from_drawdown_cfs)))
        detention = concept_detention_size(inflow_cfs, release_cfs)
        geometry = getattr(detention, "recommended_geometry", None)
        required_storage_cf = safe_float(getattr(detention, "required_storage_cf", 0.0), 0.0)
        provided_storage_cf = safe_float(getattr(detention, "provided_geometry_storage_cf", 0.0), 0.0)
        target_bottom_area_sf = safe_float(getattr(geometry, "bottom_area_sf", 0.0), 0.0) if geometry is not None else 0.0
        depth_ft = round(safe_float(getattr(geometry, "depth_ft", 0.0), 0.0), 3) if geometry is not None else 0.0
        freeboard_ft = round(safe_float(getattr(geometry, "freeboard_ft", 0.0), 0.0), 3) if geometry is not None else 0.0
        side_slope_h_to_1v = round(safe_float(getattr(geometry, "side_slope_h_to_1v", 4.0), 4.0), 3) if geometry is not None else 4.0
        bottom_to_top_area_ratio = (target_bottom_area_sf / max(top_area_sf, 1.0)) if top_area_sf > 0.0 else 0.0
        expected_daylight_band_width_ft = max(0.0, side_slope_h_to_1v * max(depth_ft + freeboard_ft, 0.0))
        scale = 0.55
        if top_area_sf > 1e-6 and target_bottom_area_sf > 1e-6:
            area_scale = max(0.25, min(0.92, math.sqrt(target_bottom_area_sf / top_area_sf)))
            scale = area_scale
            top_equivalent_radius = math.sqrt(max(top_area_sf, 1.0) / math.pi)
            if top_equivalent_radius > 1e-6 and expected_daylight_band_width_ft > 0.0:
                target_bottom_radius = max(1.0, top_equivalent_radius - expected_daylight_band_width_ft)
                depth_scale = max(0.15, min(0.95, target_bottom_radius / top_equivalent_radius))
                scale = max(0.15, min(0.95, (area_scale * 0.6) + (depth_scale * 0.4)))
        bottom_points = _scale_polygon(boundary_points, scale) if boundary_points else []
        actual_bottom_area_sf = _polygon_area(bottom_points) or target_bottom_area_sf
        top_equivalent_radius = math.sqrt(max(top_area_sf, 1.0) / math.pi) if top_area_sf > 0.0 else 0.0
        bottom_equivalent_radius = math.sqrt(max(actual_bottom_area_sf, 1.0) / math.pi) if actual_bottom_area_sf > 0.0 else 0.0
        daylight_band_width_ft = max(0.0, top_equivalent_radius - bottom_equivalent_radius)
        footprint_consistency_ratio = (
            daylight_band_width_ft / max(expected_daylight_band_width_ft, 1e-9)
            if expected_daylight_band_width_ft > 0.0
            else 1.0
        )
        top_perimeter_ft = _polygon_perimeter(boundary_points)
        bottom_perimeter_ft = _polygon_perimeter(bottom_points)
        bottom_elev = round(
            safe_float(basin.get("average_z"), 0.0) - max(2.0, depth_ft),
            3,
        )
        top_of_bank_elev = round(
            bottom_elev
            + depth_ft
            + freeboard_ft,
            3,
        )
        outlet_xy = _nearest_polygon_vertex(boundary_points or [centroid_xy], outfall_xy or centroid_xy)
        storage_ratio = 0.0
        if required_storage_cf > 0.0:
            storage_ratio = provided_storage_cf / max(required_storage_cf, 1.0)
        storage_deficit_cf = max(0.0, required_storage_cf - provided_storage_cf)
        storage_surplus_cf = max(0.0, provided_storage_cf - required_storage_cf)
        adequacy_status = "adequate"
        if required_storage_cf > 0.0 and storage_ratio < 1.0:
            adequacy_status = "deficient"
        elif required_storage_cf > 0.0 and storage_ratio >= 1.1:
            adequacy_status = "surplus"
        spillway_drop_ft = max(0.3, min(1.0, freeboard_ft * 0.5)) if freeboard_ft > 0.0 else 0.3
        spillway_crest_elev_ft = round(top_of_bank_elev - spillway_drop_ft, 3)
        spillway_width_ft = round(max(8.0, min(24.0, math.sqrt(max(top_area_sf, 1.0)) * 0.2)), 3)
        overflow_depth_ft = round(max(0.5, freeboard_ft), 3)
        spillway_capacity_cfs = round(spillway_width_ft * overflow_depth_ft * 1.5, 3)
        geometry_quality = {
            "has_boundary": bool(boundary_points),
            "has_bottom": bool(bottom_points),
            "has_daylight_tie_in": bool(boundary_points),
            "storage_ratio": round(storage_ratio, 3),
            "bottom_to_top_area_ratio": round(bottom_to_top_area_ratio, 3),
            "adequacy_status": adequacy_status,
            "storage_deficit_cf": round(storage_deficit_cf, 3),
            "storage_surplus_cf": round(storage_surplus_cf, 3),
            "top_area_sf": round(top_area_sf, 3),
            "bottom_area_sf": round(actual_bottom_area_sf, 3),
            "target_bottom_area_sf": round(target_bottom_area_sf, 3),
            "top_perimeter_ft": round(top_perimeter_ft, 3),
            "bottom_perimeter_ft": round(bottom_perimeter_ft, 3),
            "expected_daylight_band_width_ft": round(expected_daylight_band_width_ft, 3),
            "daylight_band_width_ft": round(daylight_band_width_ft, 3),
            "footprint_consistency_ratio": round(footprint_consistency_ratio, 3),
            "depth_ft": depth_ft,
            "freeboard_ft": freeboard_ft,
            "side_slope_h_to_1v": side_slope_h_to_1v,
            "spillway_crest_elev_ft": spillway_crest_elev_ft,
            "spillway_width_ft": spillway_width_ft,
            "spillway_capacity_cfs": spillway_capacity_cfs,
            "stage_storage_point_count": len(safe_list(getattr(detention, "stage_storage_curve", []))),
        }
        basin["boundary_points"] = boundary_points
        basin["bottom_points"] = bottom_points
        basin["top_of_bank_area_sf"] = round(top_area_sf, 3)
        basin["bottom_area_sf"] = round(actual_bottom_area_sf, 3)
        basin["bottom_elev_ft"] = bottom_elev
        basin["top_of_bank_elev_ft"] = top_of_bank_elev
        basin["daylight_tie_in"] = bool(boundary_points)
        basin["storage_ratio"] = round(storage_ratio, 3)
        basin["geometry_quality"] = geometry_quality
        basin["overflow_spillway"] = {
            "crest_elev_ft": spillway_crest_elev_ft,
            "width_ft": spillway_width_ft,
            "overflow_depth_ft": overflow_depth_ft,
            "assumed_capacity_cfs": spillway_capacity_cfs,
            "to_target_name": safe_str(preferred_outfall.get("target_name"), "") or safe_str(basin.get("target_name"), ""),
            "daylight_tie_in": bool(boundary_points),
            "assumed": True,
        }
        basin["outlet_structure"] = {
            "name": f"{name}-OUTLET" if name else "BASIN-OUTLET",
            "x": round(safe_float(outlet_xy[0], 0.0), 3),
            "y": round(safe_float(outlet_xy[1], 0.0), 3),
            "invert_ft": round(bottom_elev + 1.0, 3),
            "flow_direction": "to_outfall",
            "daylight_tie_in": bool(boundary_points),
        }
        basin["detention_design"] = {
            "required_storage_cf": round(required_storage_cf, 3),
            "provided_storage_cf": round(provided_storage_cf, 3),
            "drawdown_hours": round(safe_float(getattr(detention, "drawdown_hours", 0.0), 0.0), 3),
            "inflow_cfs": round(inflow_cfs, 3),
            "release_cfs": round(release_cfs, 3),
            "release_basis": "target_drawdown",
            "target_drawdown_hours": round(target_drawdown_hours, 3),
            "release_fraction_of_inflow": round(release_cfs / max(inflow_cfs, 1e-9), 4) if inflow_cfs > 0.0 else 0.0,
            "storage_ratio": round(storage_ratio, 3),
            "bottom_to_top_area_ratio": round(bottom_to_top_area_ratio, 3),
            "adequacy_status": adequacy_status,
            "storage_deficit_cf": round(storage_deficit_cf, 3),
            "storage_surplus_cf": round(storage_surplus_cf, 3),
            "top_area_sf": round(top_area_sf, 3),
            "bottom_area_sf": round(actual_bottom_area_sf, 3),
            "target_bottom_area_sf": round(target_bottom_area_sf, 3),
            "top_perimeter_ft": round(top_perimeter_ft, 3),
            "bottom_perimeter_ft": round(bottom_perimeter_ft, 3),
            "expected_daylight_band_width_ft": round(expected_daylight_band_width_ft, 3),
            "daylight_band_width_ft": round(daylight_band_width_ft, 3),
            "footprint_consistency_ratio": round(footprint_consistency_ratio, 3),
            "side_slope_h_to_1v": side_slope_h_to_1v,
            "depth_ft": depth_ft,
            "freeboard_ft": freeboard_ft,
            "spillway_crest_elev_ft": spillway_crest_elev_ft,
            "spillway_width_ft": spillway_width_ft,
            "spillway_capacity_cfs": spillway_capacity_cfs,
            "stage_storage_point_count": len(safe_list(getattr(detention, "stage_storage_curve", []))),
            "assumptions": [
                "Storage sized from Rational Method inflow estimate using planner runoff assumptions.",
                "Outlet release was tuned to concept basin storage and a target 48-hour drawdown window.",
                "Emergency overflow spillway crest and width were inferred from top-of-bank elevation and basin footprint.",
            ],
        }
        updated_basins.append(basin)

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for basin in updated_basins:
        group_key = safe_str(basin.get("target_name")) or "__default__"
        grouped.setdefault(group_key, []).append(basin)
    for items in grouped.values():
        items.sort(key=lambda item: (-safe_float(item.get("area_sf"), 0.0), safe_str(item.get("name"))))
        for idx, basin in enumerate(items):
            exportable = (
                idx == 0
                and safe_float(basin.get("area_sf"), 0.0) >= min_export_area_sf
                and len(safe_list(basin.get("boundary_points"))) >= 3
            )
            basin["engineering_role"] = "primary_detention" if exportable else "minor_surface_sink"
            basin["exportable"] = exportable

    enriched["basins"] = updated_basins
    stats = safe_dict(enriched.get("stats"))
    stats["engineered_basin_geometry_count"] = sum(1 for item in updated_basins if safe_list(item.get("boundary_points")))
    stats["exportable_basin_count"] = sum(1 for item in updated_basins if bool(item.get("exportable")))
    stats["primary_detention_count"] = sum(
        1
        for item in updated_basins
        if safe_str(item.get("engineering_role")) == "primary_detention" and bool(item.get("exportable"))
    )
    existing_flow_paths = [safe_dict(item) for item in safe_list(enriched.get("flow_paths")) if safe_dict(item)]
    if not existing_flow_paths and structures and updated_basins:
        target_basin = next((item for item in updated_basins if bool(item.get("exportable"))), updated_basins[0])
        target_xy = safe_list(target_basin.get("centroid_xy"))
        synthesized_flow_paths: List[Dict[str, Any]] = []
        if len(target_xy) >= 2:
            tx = round(safe_float(target_xy[0], 0.0), 3)
            ty = round(safe_float(target_xy[1], 0.0), 3)
            for index, structure in enumerate(structures, start=1):
                sx = round(safe_float(structure.get("x"), 0.0), 3)
                sy = round(safe_float(structure.get("y"), 0.0), 3)
                if sx == tx and sy == ty:
                    continue
                path = [[sx, sy], [tx, ty]]
                synthesized_flow_paths.append(
                    {
                        "id": f"FLOW-AUTO-{index}",
                        "path": path,
                        "target_name": safe_str(target_basin.get("name"), "PRIMARY-DETENTION"),
                        "length_ft": round(polyline_length(path), 3),
                        "assumed": True,
                    }
                )
        if synthesized_flow_paths:
            enriched["flow_paths"] = synthesized_flow_paths
            stats["flow_path_count"] = len(synthesized_flow_paths)
            stats["has_flow_paths"] = True
    enriched["stats"] = stats
    return enriched


def _enrich_utility_summary_with_coordination(
    summary: Dict[str, Any],
    project: ProjectModel,
    manager: Optional[ProjectManager] = None,
) -> Dict[str, Any]:
    hooks = safe_dict(summary.get("conflict_hooks"))
    segments = [safe_dict(item) for item in safe_list(hooks.get("utility_segments"))]
    sanitary = safe_dict(
        (manager.latest_outputs.get("sanitary") if manager is not None else None)
        or project.meta.get("sanitary_summary", {})
    )
    coordination = safe_dict(
        (manager.latest_outputs.get("coordination") if manager is not None else None)
        or project.meta.get("coordination_summary", {})
    )
    post_resolution_validations = safe_dict(coordination.get("post_resolution_validations"))
    post_system_validations = safe_dict(post_resolution_validations.get("systems"))
    unresolved_conflicts = [safe_dict(item) for item in safe_list(coordination.get("unresolved_conflicts"))]
    resolved_conflicts = [safe_dict(item) for item in safe_list(coordination.get("resolved_conflicts"))]
    resolution_history = [safe_dict(item) for item in safe_list(coordination.get("resolution_history"))]
    utility_system_names = {"utilities", "utility", "water", "sanitary", "storm", "storm_pipes"}

    def _utility_related(conflict: Dict[str, Any]) -> bool:
        systems = {
            safe_str(item).lower()
            for item in safe_list(conflict.get("systems_involved") or conflict.get("systems"))
            if safe_str(item)
        }
        return bool(systems.intersection(utility_system_names))

    utility_unresolved = [item for item in unresolved_conflicts if _utility_related(item)]
    utility_resolved = [item for item in resolved_conflicts if _utility_related(item)]
    utility_history = [
        item
        for item in resolution_history
        if {
            safe_str(system).lower()
            for system in safe_list(item.get("changed_systems"))
            if safe_str(system)
        }.intersection(utility_system_names)
    ]
    utility_conflict_type_counts: Dict[str, int] = {}
    for conflict in utility_unresolved:
        conflict_type = safe_str(conflict.get("conflict_type"), "utility_conflict")
        utility_conflict_type_counts[conflict_type] = utility_conflict_type_counts.get(conflict_type, 0) + 1
    reroute_resolution_count = 0
    vertical_adjustment_count = 0
    added_structures_from_coordination = 0
    grading_adjustment_count = 0
    selected_candidate_modes: Dict[str, int] = {}
    selected_group_strategies: Dict[str, int] = {}
    clearance_total_checks = 0
    clearance_compliant_checks = 0
    for history_item in utility_history:
        strategy_name = safe_str(history_item.get("selected_group_strategy"))
        if strategy_name:
            selected_group_strategies[strategy_name] = selected_group_strategies.get(strategy_name, 0) + 1
        candidate_mode = safe_str(history_item.get("selected_candidate_mode"))
        if candidate_mode:
            selected_candidate_modes[candidate_mode] = selected_candidate_modes.get(candidate_mode, 0) + 1
        engineering_deltas = safe_dict(history_item.get("engineering_deltas"))
        added_structures_from_coordination += safe_int(engineering_deltas.get("added_structures"), 0)
        grading_adjustment_count += len(safe_list(engineering_deltas.get("grading_adjustments")))
        crossing_hierarchy = safe_dict(engineering_deltas.get("crossing_hierarchy"))
        clearance_total_checks += safe_int(crossing_hierarchy.get("total_checks"), 0)
        clearance_compliant_checks += safe_int(crossing_hierarchy.get("compliant_checks"), 0)
        for note in safe_list(history_item.get("notes")):
            note_text = safe_str(note).lower()
            if "reroute" in note_text:
                reroute_resolution_count += 1
            if "vertical_adjustment" in note_text or "vertical adjustment" in note_text:
                vertical_adjustment_count += 1
    utility_conflicts_all = utility_unresolved + utility_resolved
    actual_horizontal_values = [
        safe_float(conflict.get("actual_horizontal_clearance_ft"), 0.0)
        for conflict in utility_conflicts_all
        if conflict.get("actual_horizontal_clearance_ft") is not None
    ]
    actual_vertical_values = [
        safe_float(conflict.get("actual_vertical_clearance_ft"), 0.0)
        for conflict in utility_conflicts_all
        if conflict.get("actual_vertical_clearance_ft") is not None
    ]
    horizontal_deficits = [
        max(safe_float(conflict.get("required_horizontal_clearance_ft"), 0.0) - safe_float(conflict.get("actual_horizontal_clearance_ft"), 0.0), 0.0)
        for conflict in utility_conflicts_all
        if conflict.get("actual_horizontal_clearance_ft") is not None
    ]
    vertical_deficits = [
        max(safe_float(conflict.get("required_vertical_clearance_ft"), 0.0) - safe_float(conflict.get("actual_vertical_clearance_ft"), 0.0), 0.0)
        for conflict in utility_conflicts_all
        if conflict.get("actual_vertical_clearance_ft") is not None
    ]
    summary["trunk_count"] = sum(
        1 for seg in segments if safe_str(safe_dict(seg).get("segment_role"), "") == "trunk"
    )
    summary["service_count"] = sum(
        1 for seg in segments if safe_str(safe_dict(seg).get("segment_role"), "") != "trunk"
    )
    summary["gravity_segment_count"] = sum(
        1 for seg in segments if safe_str(safe_dict(seg).get("hydraulic_mode"), "") == "gravity"
    )
    summary["min_cover_ft"] = round(
        min(
            (
                min(
                    safe_float(safe_dict(seg).get("cover_start_ft"), 0.0),
                    safe_float(safe_dict(seg).get("cover_end_ft"), 0.0),
                )
                for seg in segments
            ),
            default=0.0,
        ),
        3,
    )
    summary["min_horizontal_separation_ft"] = round(
        safe_float(hooks.get("minimum_horizontal_separation_ft"), 0.0),
        3,
    )
    summary["min_vertical_separation_ft"] = round(
        safe_float(hooks.get("minimum_vertical_separation_ft"), 0.0),
        3,
    )
    summary["shallow_segment_count"] = sum(
        1
        for seg in segments
        if min(
            safe_float(safe_dict(seg).get("cover_start_ft"), 0.0),
            safe_float(safe_dict(seg).get("cover_end_ft"), 0.0),
        )
        < safe_float(safe_dict(seg).get("min_cover_ft"), 3.0)
    )
    summary["gravity_slope_issue_count"] = sum(
        1
        for seg in segments
        if safe_str(safe_dict(seg).get("hydraulic_mode"), "") == "gravity"
        and safe_float(safe_dict(seg).get("slope_ft_ft"), 0.0) > 0.0
        and safe_float(safe_dict(seg).get("slope_ft_ft"), 0.0) < PIPE_MIN_SLOPE
    )
    summary["coordination"] = {
        "sanitary_storm_conflict_count": safe_int(safe_dict(sanitary.get("stats")).get("storm_conflict_count"), 0),
        "unresolved_conflict_count": len(safe_list(coordination.get("unresolved_conflicts"))),
        "resolved_conflict_count": safe_int(coordination.get("resolved_count"), 0),
        "utility_related_unresolved_conflict_count": len(utility_unresolved),
        "utility_related_resolved_conflict_count": len(utility_resolved),
        "utility_related_conflict_types": utility_conflict_type_counts,
        "selected_group_strategy": safe_str(safe_dict(utility_history[-1] if utility_history else {}).get("selected_group_strategy"), ""),
        "selected_candidate_mode": safe_str(safe_dict(utility_history[-1] if utility_history else {}).get("selected_candidate_mode"), ""),
        "selected_group_strategy_counts": selected_group_strategies,
        "selected_candidate_mode_counts": selected_candidate_modes,
        "reroute_resolution_count": reroute_resolution_count,
        "vertical_adjustment_count": vertical_adjustment_count,
        "added_structures_from_coordination": added_structures_from_coordination,
        "grading_adjustment_count": grading_adjustment_count,
        "clearance_total_checks": clearance_total_checks,
        "clearance_compliant_checks": clearance_compliant_checks,
        "min_achieved_horizontal_clearance_ft": round(min(actual_horizontal_values, default=0.0), 3),
        "min_achieved_vertical_clearance_ft": round(min(actual_vertical_values, default=0.0), 3),
        "max_horizontal_clearance_deficit_ft": round(max(horizontal_deficits, default=0.0), 3),
        "max_vertical_clearance_deficit_ft": round(max(vertical_deficits, default=0.0), 3),
        "post_validation_valid": bool(post_resolution_validations.get("valid", True)),
        "post_validation_systems": {
            "storm": bool(safe_dict(post_system_validations.get("storm")).get("valid", True)),
            "storm_hydraulics": bool(safe_dict(post_system_validations.get("storm_hydraulics")).get("valid", True)),
            "sanitary": bool(safe_dict(post_system_validations.get("sanitary")).get("valid", True)),
            "utilities": bool(safe_dict(post_system_validations.get("utilities")).get("valid", True)),
        },
        "required_horizontal_separation_ft": round(safe_float(hooks.get("minimum_horizontal_separation_ft"), 0.0), 3),
        "required_vertical_separation_ft": round(safe_float(hooks.get("minimum_vertical_separation_ft"), 0.0), 3),
    }
    return _enrich_water_production_depth(summary)


def _filter_placeholder_engineering_actions(project: ProjectModel, actions: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    drainage = safe_dict(project.meta.get("drainage_canonical"))
    storm = safe_dict(project.meta.get("storm_pipe_summary"))
    grading = safe_dict(project.meta.get("grading_summary"))
    grading_export_ready = bool(_grading_export_validation(project, grading_override=grading).get("ready"))
    drainage_export_ready = bool(_drainage_export_validation(project).get("ready"))
    storm_export_ready = bool(_storm_export_validation(project).get("ready"))
    filtered: List[Dict[str, Any]] = []
    for action in safe_list(actions):
        rec = safe_dict(action)
        if not rec:
            continue
        layer = safe_str(rec.get("layer")).upper()
        has_canonical_tag = bool(safe_str(rec.get("canonical_source_type")))
        if layer in {"FG_CONTOUR", "SPOT_FG"} and not grading_export_ready and not has_canonical_tag:
            continue
        if layer == "PIPE" and storm_export_ready and not has_canonical_tag:
            continue
        if layer == "DRAIN" and drainage_export_ready and not has_canonical_tag:
            continue
        if layer == "BASIN_BOUNDARY" and drainage_export_ready and not has_canonical_tag:
            continue
        if layer == "STRUCTURE" and drainage_export_ready and not has_canonical_tag:
            continue
        filtered.append(rec)
    return filtered


def _install_minimum_grading_actions(project: ProjectModel, parsed: Dict[str, Any]) -> int:
    payload = unwrap_fields_for_execution(parsed)
    lot = safe_dict(payload.get("lot"))
    bx = by = 0.0
    bw = safe_float(lot.get("w"), DEFAULT_LOT_WIDTH)
    bh = safe_float(lot.get("h"), DEFAULT_LOT_HEIGHT)
    buildings = safe_list(payload.get("buildings"))
    if buildings:
        b = safe_dict(buildings[0])
        bx = safe_float(b.get("x"), 0.0)
        by = safe_float(b.get("y"), 0.0)
        bw = safe_float(b.get("w"), bw)
        bh = safe_float(b.get("d"), bh)
    actions = []
    corners = [
        (bx, by, "FG-1"),
        (bx + bw, by, "FG-2"),
        (bx + bw, by + bh, "FG-3"),
        (bx, by + bh, "FG-4"),
    ]
    for x, y, label in corners:
        actions.append({
            "task": "text_note",
            "origin": [x, y],
            "points": None,
            "closed": None,
            "width": None,
            "height": None,
            "label": None,
            "layer": "SPOT_FG",
            "text": label,
            "text_height": TEXT_HEIGHT_SMALL,
            "center": None,
            "radius": None,
            "start_angle": None,
            "end_angle": None,
            "meta": _preview_meta_for_base_action("SPOT_FG", "text_note"),
        })
    # concept contours / flow arrows
    for frac, label in ((0.25, 'FG-A'), (0.5, 'FG-B'), (0.75, 'FG-C')):
        y = safe_float(lot.get('y'), 0.0) + safe_float(lot.get('h'), DEFAULT_LOT_HEIGHT) * frac
        actions.append({
            "task": "polyline",
            "origin": None,
            "points": [[safe_float(lot.get('x'),0.0), y], [safe_float(lot.get('x'),0.0)+safe_float(lot.get('w'),DEFAULT_LOT_WIDTH), y]],
            "closed": False,
            "width": None,
            "height": None,
            "label": label,
            "layer": "FG_CONTOUR",
            "text": None,
            "text_height": None,
            "center": None,
            "radius": None,
            "start_angle": None,
            "end_angle": None,
            "meta": _preview_meta_for_base_action("FG_CONTOUR", "polyline"),
        })
    actions.append({
        "task": "polyline",
        "origin": None,
        "points": [[bx + bw/2.0, by + bh + 5.0], [bx + bw/2.0, by + bh + 20.0]],
        "closed": False,
        "width": None,
        "height": None,
        "label": "FLOW-1",
        "layer": "DRAIN_FLOW",
        "text": None,
        "text_height": None,
        "center": None,
        "radius": None,
        "start_angle": None,
        "end_angle": None,
        "meta": _preview_meta_for_base_action("DRAIN_FLOW", "polyline"),
    })
    _merge_actions_into_expanded_plan(project, actions, grading_fallback=True, grading_minimum_export=True)
    return len(actions)


# =============================================================================
# MODEL INGEST / LEGACY EXPANSION
# =============================================================================

def _ingest_parsed_into_model(ctx: PlannerExecutionContext) -> None:
    parsed = ctx.parsed
    project = ctx.manager.project
    lot = safe_dict(parsed.get("lot"))
    setback = safe_float(parsed.get("setback"), DEFAULT_SETBACK)

    buildable_x = safe_float(lot.get("x"), DEFAULT_LOT_X) + setback
    buildable_y = safe_float(lot.get("y"), DEFAULT_LOT_Y) + setback
    buildable_w = max(1.0, safe_float(lot.get("w"), DEFAULT_LOT_WIDTH) - 2 * setback)
    buildable_h = max(1.0, safe_float(lot.get("h"), DEFAULT_LOT_HEIGHT) - 2 * setback)

    project.add_zone(rect_zone(buildable_x, buildable_y, buildable_w, buildable_h, zone_type=ZoneType.PAD, name="BUILDABLE_AREA"))
    ctx.add_stage("ingest", True, "Parsed payload ingested into ProjectModel.", buildable_area_sf=round(buildable_w * buildable_h, 2))


def _legacy_expand_payload(parsed: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return expand_plan(parsed)
    except Exception:
        return {"actions": [], "meta": {"expand_failed": True}}


def _store_expanded_plan(project: ProjectModel, expanded: Dict[str, Any]) -> None:
    if not isinstance(getattr(project, "meta", None), dict):
        project.meta = {}
    project.meta["_expanded_plan"] = sanitize_plan(expanded)


def _merge_actions_into_expanded_plan(project: ProjectModel, new_actions: Sequence[Dict[str, Any]], **meta_updates: Any) -> None:
    if not isinstance(getattr(project, "meta", None), dict):
        project.meta = {}
    base = safe_dict(project.meta.get("_expanded_plan"))
    merged = sanitize_plan(
        base if base else {
            "project_name": getattr(project, "name", "Generated Plan"),
            "units": (lambda _u: ("ft" if safe_str(_u, "ft").split(".")[-1].lower() in {"feet","foot","ft"} else safe_str(_u, "ft").split(".")[-1].lower()))(getattr(project, "units", "ft")),
            "actions": [],
            "assumptions": [],
            "meta": {},
        }
    )
    existing_keys = {repr(a) for a in safe_list(merged.get("actions")) if isinstance(a, dict)}
    for action in new_actions:
        if not isinstance(action, dict):
            continue
        norm = sanitize_action(action)
        key = repr(norm)
        if key in existing_keys:
            continue
        existing_keys.add(key)
        merged["actions"].append(norm)
    merged.setdefault("meta", {})
    merged["meta"].update({k: v for k, v in meta_updates.items() if v is not None})
    project.meta["_expanded_plan"] = merged


def _merge_plan_actions(base_actions: Sequence[Dict[str, Any]], extra_actions: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for action in list(base_actions) + list(extra_actions):
        if not isinstance(action, dict):
            continue
        norm = sanitize_action(action)
        key = repr(norm)
        if key in seen:
            continue
        seen.add(key)
        merged.append(norm)
    return sorted(merged, key=_action_sort_key)


def _polygon_area(points: Sequence[Sequence[float]]) -> float:
    pts = [
        (safe_float(pt[0], 0.0), safe_float(pt[1], 0.0))
        for pt in safe_list(points)
        if isinstance(pt, (list, tuple)) and len(pt) >= 2
    ]
    if len(pts) < 3:
        return 0.0
    area = 0.0
    for idx, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(idx + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def _polygon_centroid(points: Sequence[Sequence[float]]) -> Tuple[float, float]:
    pts = [
        (safe_float(pt[0], 0.0), safe_float(pt[1], 0.0))
        for pt in safe_list(points)
        if isinstance(pt, (list, tuple)) and len(pt) >= 2
    ]
    if not pts:
        return 0.0, 0.0
    area_twice = 0.0
    cx = 0.0
    cy = 0.0
    for idx, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(idx + 1) % len(pts)]
        cross = x1 * y2 - x2 * y1
        area_twice += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(area_twice) < 1e-9:
        return (
            sum(pt[0] for pt in pts) / len(pts),
            sum(pt[1] for pt in pts) / len(pts),
        )
    factor = 1.0 / (3.0 * area_twice)
    return cx * factor, cy * factor


def _polygon_perimeter(points: Sequence[Sequence[float]]) -> float:
    pts = [
        (safe_float(pt[0], 0.0), safe_float(pt[1], 0.0))
        for pt in safe_list(points)
        if isinstance(pt, (list, tuple)) and len(pt) >= 2
    ]
    if len(pts) < 2:
        return 0.0
    perimeter = 0.0
    for idx, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(idx + 1) % len(pts)]
        perimeter += math.hypot(x2 - x1, y2 - y1)
    return perimeter


def _scale_polygon(points: Sequence[Sequence[float]], scale: float) -> List[List[float]]:
    cx, cy = _polygon_centroid(points)
    scaled: List[List[float]] = []
    for pt in safe_list(points):
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            continue
        px = safe_float(pt[0], 0.0)
        py = safe_float(pt[1], 0.0)
        scaled.append([
            round(cx + (px - cx) * scale, 3),
            round(cy + (py - cy) * scale, 3),
        ])
    return scaled


def _nearest_polygon_vertex(points: Sequence[Sequence[float]], target_xy: Sequence[float]) -> List[float]:
    pts = [
        [safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)]
        for pt in safe_list(points)
        if isinstance(pt, (list, tuple)) and len(pt) >= 2
    ]
    tx = safe_float(safe_list(target_xy)[0] if len(safe_list(target_xy)) >= 1 else 0.0, 0.0)
    ty = safe_float(safe_list(target_xy)[1] if len(safe_list(target_xy)) >= 2 else 0.0, 0.0)
    if not pts:
        return [tx, ty]
    return min(pts, key=lambda pt: (pt[0] - tx) ** 2 + (pt[1] - ty) ** 2)


def _zone_layer_for_preview(zone: Any) -> str:
    zone_type = getattr(getattr(zone, "zone_type", None), "value", "SITE")
    return str(zone_type or "SITE").upper()


def _zone_label_for_preview(zone: Any) -> Optional[str]:
    zone_name = safe_str(getattr(zone, "name", ""))
    zone_layer = _zone_layer_for_preview(zone)
    if zone_layer in {"SITE", "LOT"}:
        return None
    if zone_layer == "PAD" and zone_name.upper() in {"BUILDABLE_AREA", "SITE", "LOT"}:
        return None
    return zone_name or zone_layer


def _object_layer_for_preview(obj: Any) -> Optional[str]:
    kind = safe_str(getattr(obj, "kind", "")).lower()
    tags = [safe_str(item, "").lower() for item in safe_list(getattr(obj, "tags", []))]
    domain = safe_str(getattr(getattr(obj, "domain", None), "value", getattr(obj, "domain", ""))).lower()

    helper_prefixes = (
        "corridor_start",
        "corridor_end",
        "corridor_pi",
        "building_entry",
    )
    helper_tokens = ("service_tie", "source", "control_point", "utility_source")
    if kind.startswith(helper_prefixes) or any(token in kind for token in helper_tokens):
        return None

    if "building" in kind or "building" in tags:
        return "BUILDING"
    if "parking" in kind or "parking" in tags:
        return "PARKING"
    if "fire_lane" in kind or "fire_lane" in tags:
        return "FIRE"
    if any(token in kind for token in ("access_aisle", "ada_path", "walk", "walkway", "sidewalk")) or any(
        token in tags for token in ("access_aisle", "ada_path", "walk", "walkway", "sidewalk")
    ):
        return "WALK"
    if any(token in kind for token in ("pavement", "pad")):
        return "PAVEMENT"
    if any(token in kind for token in ("road", "corridor", "drive")):
        return "ROAD"
    if "bridge" in kind or "bridge" in tags:
        return "BRIDGE"
    if "pool" in kind or "pool" in tags:
        return "POOL"
    if any(token in kind for token in ("detention", "pond", "basin")):
        return "BASIN_BOUNDARY"
    if any(token in kind for token in ("storm", "inlet", "drain")):
        return "DRAIN"
    if any(token in kind for token in ("sanitary", "sewer")):
        return "SAN"
    if domain == "utility" or any(token in kind for token in ("utility", "water")):
        return "UTILITY"
    return None


def _boundary_points_for_preview(boundary: Any) -> List[List[float]]:
    points = []
    for point in safe_list(getattr(boundary, "points", [])):
        px = safe_float(getattr(point, "x", 0.0), 0.0)
        py = safe_float(getattr(point, "y", 0.0), 0.0)
        points.append([px, py])
    return points


def _preview_meta_for_base_action(layer: str, task: str) -> Dict[str, Any]:
    raw_layer = safe_str(layer, "").upper()
    role = "overlay" if task in {"text_note", "point", "north_arrow"} else "final"
    if raw_layer in {"ROAD", "FIRE"}:
        system = "roads"
    elif raw_layer in {"PARKING"}:
        system = "parking"
    elif raw_layer in {"WALK", "SIDEWALK"}:
        system = "pedestrian"
    elif raw_layer in {"PIPE", "STORM", "DRAIN", "STRUCTURE", "BASIN_BOUNDARY", "LOW_POINTS", "DRAIN_FLOW"}:
        system = "drainage"
    elif raw_layer in {"SAN"}:
        system = "sanitary"
    elif raw_layer in {"WATER", "WATR"}:
        system = "water"
    elif raw_layer in {"FG_CONTOUR", "EG_CONTOUR", "SURFACE"}:
        system = "grading"
    else:
        system = "layout"
    return {
        "is_final": role == "final",
        "preview_role": role,
        "system": system,
    }


def _project_model_base_actions(project: ProjectModel) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []

    def _stable_source_id(prefix: str, *parts: Any) -> str:
        payload = json.dumps(parts, sort_keys=True, default=str)
        return f"{prefix}_{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:10]}"

    zones = getattr(project, "zones", {}) or {}
    if isinstance(zones, dict):
        for zone in zones.values():
            boundary = getattr(zone, "boundary", None)
            boundary_points = _boundary_points_for_preview(boundary) if boundary is not None else []
            bbox = getattr(boundary, "bbox", None)
            layer = _zone_layer_for_preview(zone)
            zone_id = safe_str(getattr(zone, "id", ""), "")
            if zone_id.startswith("zone_"):
                zone_id = _stable_source_id(
                    "zone",
                    layer,
                    _zone_label_for_preview(zone),
                    [round(value, 4) for value in [bbox.min_x, bbox.min_y, bbox.width, bbox.height]] if bbox is not None else boundary_points,
                )
            zone_type = safe_str(getattr(zone, "zone_type", ""), "zone")
            if layer in {"SITE", "BUILDING"} and bbox is not None:
                actions.append({
                    "task": "rectangle",
                    "origin": [bbox.min_x, bbox.min_y],
                    "width": bbox.width,
                    "height": bbox.height,
                    "label": _zone_label_for_preview(zone),
                    "layer": layer,
                    "points": None,
                    "closed": None,
                    "text": None,
                    "text_height": None,
                    "center": None,
                    "radius": None,
                    "start_angle": None,
                    "end_angle": None,
                    "meta": {
                        **_preview_meta_for_base_action(layer, "rectangle"),
                        "entity_id": zone_id or None,
                        "source": "zone",
                    },
                    "canonical_source_id": zone_id or None,
                    "canonical_source_type": zone_type or "zone",
                })
                continue
            if len(boundary_points) >= 3:
                actions.append({
                    "task": "polygon",
                    "points": boundary_points,
                    "closed": True,
                    "label": _zone_label_for_preview(zone),
                    "layer": layer,
                    "origin": None,
                    "width": None,
                    "height": None,
                    "text": None,
                    "text_height": None,
                    "center": None,
                    "radius": None,
                    "start_angle": None,
                    "end_angle": None,
                    "meta": {
                        **_preview_meta_for_base_action(layer, "polygon"),
                        "entity_id": zone_id or None,
                        "source": "zone",
                    },
                    "canonical_source_id": zone_id or None,
                    "canonical_source_type": zone_type or "zone",
                })
                continue
            if bbox is None:
                continue
            actions.append({
                "task": "rectangle",
                "origin": [bbox.min_x, bbox.min_y],
                "width": bbox.width,
                "height": bbox.height,
                "label": _zone_label_for_preview(zone),
                "layer": layer,
                "points": None,
                "closed": None,
                "text": None,
                "text_height": None,
                "center": None,
                "radius": None,
                "start_angle": None,
                "end_angle": None,
                "meta": {
                    **_preview_meta_for_base_action(layer, "rectangle"),
                    "entity_id": zone_id or None,
                    "source": "zone",
                },
                "canonical_source_id": zone_id or None,
                "canonical_source_type": zone_type or "zone",
            })

    objects_dict = getattr(project, "objects", {}) or {}
    if isinstance(objects_dict, dict):
        for obj in objects_dict.values():
            layer = _object_layer_for_preview(obj)
            boundary = getattr(obj, "boundary", None)
            boundary_points = _boundary_points_for_preview(boundary) if boundary is not None else []
            if layer and boundary_points:
                obj_id = safe_str(getattr(obj, "id", ""), "")
                if obj_id.startswith("obj_"):
                    obj_id = _stable_source_id("obj", layer, safe_str(getattr(obj, "name", "")), boundary_points)
                obj_kind = safe_str(getattr(obj, "kind", ""), "object")
                actions.append({
                    "task": "polygon",
                    "points": boundary_points,
                    "closed": True,
                    "label": safe_str(getattr(obj, "name", "")) or None,
                    "layer": layer,
                    "origin": None,
                    "width": None,
                    "height": None,
                    "text": None,
                    "text_height": None,
                    "center": None,
                    "radius": None,
                    "start_angle": None,
                    "end_angle": None,
                    "meta": {
                        **_preview_meta_for_base_action(layer, "polygon"),
                        "entity_id": obj_id or None,
                        "source": safe_str(safe_dict(getattr(obj, "properties", {})).get("source"), "model"),
                    },
                    "canonical_source_id": obj_id or None,
                    "canonical_source_type": obj_kind or "object",
                })
                continue
            anchor = getattr(obj, "anchor", None)
            if anchor is None:
                continue
            if layer is None:
                continue
            obj_id = safe_str(getattr(obj, "id", ""), "")
            if obj_id.startswith("obj_"):
                obj_id = _stable_source_id(
                    "obj",
                    layer,
                    safe_str(getattr(obj, "name", "")),
                    [round(safe_float(getattr(anchor, "x", 0.0)), 4), round(safe_float(getattr(anchor, "y", 0.0)), 4)],
                )
            obj_kind = safe_str(getattr(obj, "kind", ""), "object")
            actions.append({
                "task": "text_note",
                "origin": [getattr(anchor, "x", 0.0), getattr(anchor, "y", 0.0)],
                "text": safe_str(getattr(obj, "name", getattr(obj, "kind", "OBJECT"))),
                "text_height": TEXT_HEIGHT_SMALL,
                "layer": layer,
                "points": None,
                "closed": None,
                "width": None,
                "height": None,
                "label": None,
                "center": None,
                "radius": None,
                "start_angle": None,
                "end_angle": None,
                "meta": {
                    **_preview_meta_for_base_action(layer, "text_note"),
                    "entity_id": obj_id or None,
                    "source": safe_str(safe_dict(getattr(obj, "properties", {})).get("source"), "model"),
                },
                "canonical_source_id": obj_id or None,
                "canonical_source_type": obj_kind or "object",
            })

    return actions


def _has_primary_preview_geometry(actions: Sequence[Dict[str, Any]]) -> bool:
    important_layers = {"BUILDING", "ROAD", "PAVEMENT", "PARKING", "WALK", "FIRE"}
    geometric_tasks = {"rectangle", "polygon", "polyline", "circle"}
    for action in safe_list(actions):
        rec = safe_dict(action)
        if not rec:
            continue
        if safe_str(rec.get("layer")).upper() not in important_layers:
            continue
        if lower_text(rec.get("task")) in geometric_tasks:
            return True
    return False


def _dirty_systems_from_project(project: ProjectModel) -> set[str]:
    meta = safe_dict(getattr(project, "meta", {}))
    dirty_state = safe_dict(meta.get("system_dirty_state"))
    dirty: set[str] = set()
    for name, record in dirty_state.items():
        entry = safe_dict(record) if isinstance(record, dict) else {"state": record}
        state_value = safe_str(entry.get("state"), entry.get("status") or entry.get("value") or "")
        if state_value.lower() in {"dirty", "stale"}:
            dirty.add(safe_str(name).lower())
    return dirty


def _action_system_from_meta(action: Dict[str, Any]) -> str:
    meta = safe_dict(action.get("meta"))
    system = safe_str(meta.get("system"), "").lower()
    if system:
        if system in {"water", "sanitary"}:
            return "utilities"
        return system
    layer = safe_str(action.get("layer"), "").upper()
    if layer in {"ROAD", "PAVEMENT", "FIRE", "ROUTE", "CENTERLINE"}:
        return "roads"
    if layer in {"PARKING"}:
        return "parking"
    if layer in {"WALK", "SIDEWALK"}:
        return "pedestrian"
    if layer in {"PIPE", "DRAIN", "STRUCTURE", "BASIN_BOUNDARY", "LOW_POINTS", "DRAIN_FLOW"}:
        return "drainage"
    if layer in {"SAN", "WATER", "WATR", "UTILITY"}:
        return "utilities"
    if layer in {"FG_CONTOUR", "EG_CONTOUR", "SURFACE", "SPOT_EG", "SPOT_FG"}:
        return "grading"
    return "layout"


def _filter_actions_for_dirty_systems(actions: Sequence[Dict[str, Any]], dirty_systems: set[str]) -> List[Dict[str, Any]]:
    if not dirty_systems:
        return list(actions)
    layout_layers = {
        "ROAD",
        "PAVEMENT",
        "FIRE",
        "PARKING",
        "WALK",
        "SIDEWALK",
        "ROUTE",
        "CENTERLINE",
        "C-ROAD",
        "C-PAVEMENT",
        "C-PARKING",
        "C-DRIVEWAY",
        "C-SIDEWALK",
        "C-CENTERLINE",
    }
    grading_layers = {
        "FG_CONTOUR",
        "EG_CONTOUR",
        "SURFACE",
        "SPOT_EG",
        "SPOT_FG",
        "C-CONTOUR",
        "C-SPOT-ELEV",
        "C-GRADING",
        "C-CUT",
        "C-FILL",
    }
    drainage_layers = {
        "PIPE",
        "DRAIN",
        "STRUCTURE",
        "BASIN_BOUNDARY",
        "LOW_POINTS",
        "DRAIN_FLOW",
        "C-STRM-PIPE",
        "C-STRM-INLET",
        "C-STRM-MH",
        "C-DRAIN-FLOW",
        "C-LOW-POINT",
        "C-POND",
    }
    utility_layers = {
        "UTILITY",
        "WATER",
        "WATR",
        "SAN",
        "C-WATR",
        "C-SAN",
        "C-UTIL",
        "C-HYDRANT",
    }
    protected_layout_layers = {"BUILDING", "SITE", "SETBACK", "C-BUILDING", "C-BOUNDARY", "C-SETBACK"}

    filtered: List[Dict[str, Any]] = []
    for action in safe_list(actions):
        rec = safe_dict(action)
        if not rec:
            continue
        layer = safe_str(rec.get("layer"), "").upper()
        if safe_str(rec.get("canonical_source_type")):
            filtered.append(rec)
            continue
        system = _action_system_from_meta(rec)
        if "grading" in dirty_systems and (system == "grading" or layer in grading_layers):
            continue
        if "drainage" in dirty_systems and (system == "drainage" or layer in drainage_layers):
            continue
        if "utilities" in dirty_systems and (system == "utilities" or layer in utility_layers):
            continue
        if dirty_systems.intersection({"layout", "roads", "parking"}):
            if layer in layout_layers and layer not in protected_layout_layers:
                continue
        filtered.append(rec)
    return filtered


def _filter_base_preview_actions_for_expanded_plan(
    base_actions: Sequence[Dict[str, Any]],
    expanded_actions: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    has_primary = _has_primary_preview_geometry(expanded_actions)
    primary_layers = {"BUILDING", "PARKING", "PAVEMENT", "ROAD", "FIRE", "WALK"}
    has_building_shapes = any(
        safe_str(safe_dict(action).get("layer")).upper() == "BUILDING"
        and lower_text(safe_dict(action).get("task")) in {"rectangle", "polygon"}
        for action in safe_list(expanded_actions)
    )
    expanded_primary_layers = {
        safe_str(safe_dict(action).get("layer")).upper()
        for action in safe_list(expanded_actions)
        if lower_text(safe_dict(action).get("task")) in {"rectangle", "polygon", "polyline", "circle"}
    }
    filtered: List[Dict[str, Any]] = []
    for action in safe_list(base_actions):
        rec = safe_dict(action)
        if not rec:
            continue
        layer = safe_str(rec.get("layer")).upper()
        label = safe_str(rec.get("label")).upper()
        task = lower_text(rec.get("task"))
        if has_primary and layer == "SITE":
            continue
        if has_primary and layer == "PAD" and label in {"BUILDABLE_AREA", "SITE", "LOT"}:
            continue
        if has_primary and layer in primary_layers and task in {"rectangle", "polygon", "polyline", "circle"}:
            continue
        if has_primary and layer in primary_layers and task == "text_note" and layer in expanded_primary_layers:
            continue
        if has_building_shapes and layer == "BUILDING" and task == "text_note":
            continue
        filtered.append(rec)
    return filtered


def project_model_to_plan(project: ProjectModel, project_name: str) -> Dict[str, Any]:
    dirty_systems = _dirty_systems_from_project(project)
    expanded = safe_dict(getattr(project, "meta", {}).get("_expanded_plan"))
    if expanded and safe_list(expanded.get("actions")):
        out = sanitize_plan(expanded)
        out["project_name"] = safe_str(project_name, safe_str(out.get("project_name"), "Generated Plan"))
        project_units = getattr(project, "units", out.get("units", "ft"))
        project_units_text = safe_str(project_units, "ft")
        if "." in project_units_text:
            project_units_text = project_units_text.split(".")[-1].lower()
        if project_units_text in {"feet", "foot"}:
            project_units_text = "ft"
        out["units"] = project_units_text
        out.setdefault("meta", {})
        out["meta"]["source"] = "project_model+expanded"
        expanded_actions = _filter_placeholder_engineering_actions(project, out.get("actions", []))
        base_actions = _filter_base_preview_actions_for_expanded_plan(
            _project_model_base_actions(project),
            expanded_actions,
        )
        merged_actions = _merge_plan_actions(
            _merge_plan_actions(
                base_actions,
                expanded_actions,
            ),
            _canonical_export_actions(project),
        )
        out["actions"] = _filter_actions_for_dirty_systems(merged_actions, dirty_systems)
        return out

    actions = _merge_plan_actions(_project_model_base_actions(project), _canonical_export_actions(project))
    actions = _filter_actions_for_dirty_systems(actions, dirty_systems)

    return sanitize_plan({
        "project_name": project_name,
        "units": getattr(project, "units", "ft"),
        "actions": actions,
        "assumptions": [],
        "meta": {"source": "project_model"},
    })


def _run_layout_stage(ctx: PlannerExecutionContext) -> None:
    _run_layout_stage_impl(
        ctx,
        legacy_expand_payload=_legacy_expand_payload,
        store_expanded_plan=_store_expanded_plan,
        project_model_to_plan=project_model_to_plan,
    )


def _build_existing_surface(parsed: Dict[str, Any]) -> GridSurface:
    return _build_existing_surface_impl(
        parsed,
        infer_surface_profile=_infer_surface_profile,
        normalize_vector=_normalize_vector,
    )


def _surface_range(surface: Optional[GridSurface]) -> Tuple[float, float]:
    return _surface_range_impl(surface)


def _surface_actions_from_grid(surface: Optional[GridSurface], *, layer: str, note_prefix: str, sample_lines: int = 6) -> List[Dict[str, Any]]:
    return _surface_actions_from_grid_impl(
        surface,
        layer=layer,
        note_prefix=note_prefix,
        sample_lines=sample_lines,
    )


def _grading_surface_actions(
    result: Any,
    existing_surface: Optional[GridSurface],
    proposed_surface: Optional[GridSurface],
    *,
    grade_elements: Optional[List[GradeElement]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    return _grading_surface_actions_impl(
        result,
        existing_surface,
        proposed_surface,
        grade_elements=grade_elements,
    )


def _canonical_grading_payload(
    *,
    existing_surface: Optional[GridSurface],
    result: Any,
    derived_action_stats: Dict[str, int],
    grade_elements: Optional[List[GradeElement]] = None,
) -> Dict[str, Any]:
    return _canonical_grading_payload_impl(
        existing_surface=existing_surface,
        result=result,
        derived_action_stats=derived_action_stats,
        grade_elements=grade_elements,
        normalize_vector=_normalize_vector,
    )


def _point_on_lot_edge(lot: Dict[str, Any], direction: Tuple[float, float], inset: float = 8.0) -> Tuple[float, float]:
    return _point_on_lot_edge_impl(
        lot,
        direction,
        normalize_vector=_normalize_vector,
        inset=inset,
    )


def _grading_drainage_coordination(parsed: Dict[str, Any], project: ProjectModel) -> Dict[str, Any]:
    return _grading_drainage_coordination_impl(
        parsed,
        project,
        normalize_vector=_normalize_vector,
    )


def _build_grade_elements(project: ProjectModel, parsed: Dict[str, Any]) -> List[GradeElement]:
    return _build_grade_elements_impl(project, parsed)


def _run_grading_stage(ctx: PlannerExecutionContext, hydrology: Dict[str, Any]) -> None:
    _run_grading_stage_impl(
        ctx,
        hydrology,
        strict_mode_enabled=_strict_mode_enabled,
        build_existing_surface=_build_existing_surface,
        build_grade_elements=_build_grade_elements,
        grading_surface_actions=_grading_surface_actions,
        canonical_grading_payload=_canonical_grading_payload,
        record_strict_stage_failure=_record_strict_stage_failure,
        install_minimum_grading_actions=_install_minimum_grading_actions,
        merge_actions_into_expanded_plan=_merge_actions_into_expanded_plan,
        call_with_compatible_kwargs=_call_with_compatible_kwargs,
        grading_engine_cls=GradingEngine,
    )


def _run_drainage_stage(ctx: PlannerExecutionContext, hydrology: Dict[str, Any]) -> None:
    _run_drainage_stage_impl(
        ctx,
        hydrology,
        strict_mode_enabled=_strict_mode_enabled,
        build_existing_surface=_build_existing_surface,
        user_supplied_geometry_available=_user_supplied_geometry_available,
        actions_from_point_features=_actions_from_point_features,
        actions_from_linear_features=_actions_from_linear_features,
        merge_actions_into_expanded_plan=_merge_actions_into_expanded_plan,
        canonical_drainage_payload=_canonical_drainage_payload,
        enrich_drainage_basins_with_engineering=_enrich_drainage_basins_with_engineering,
        primary_engineered_basins=_primary_engineered_basins,
        drainage_export_validation=_drainage_export_validation,
        record_strict_stage_failure=_record_strict_stage_failure,
        grading_drainage_coordination=_grading_drainage_coordination,
    )


def _run_storm_pipe_stage(ctx: PlannerExecutionContext, hydrology: Dict[str, Any]) -> None:
    _run_storm_pipe_stage_impl(
        ctx,
        hydrology,
        storm_inlets_from_drainage=_storm_inlets_from_drainage,
        storm_basins_from_drainage=_storm_basins_from_drainage,
        storm_catchments_from_drainage=_storm_catchments_from_drainage,
        storm_summary_from_network_result=_storm_summary_from_network_result,
        primary_engineered_basins=_primary_engineered_basins,
        validate_network_graph=_validate_network_graph,
        validate_storm_hydraulics=_validate_storm_hydraulics,
    )


def _sanitary_min_slope(segment_role: str, diameter_in: float) -> float:
    if segment_role == "service_connection":
        return 0.02
    if diameter_in >= 8.0:
        return 0.008
    if segment_role == "main":
        return 0.01
    return 0.02


def _sanitary_building_nodes(project: ProjectModel, street_edge: str) -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for zone in project.zones.values():
        zone_name = safe_str(getattr(zone, "name", ""))
        if zone.zone_type not in {ZoneType.BUILDING, ZoneType.BUILDING_PAD, ZoneType.PAD}:
            continue
        if zone.zone_type == ZoneType.PAD and zone_name.upper() in {"BUILDABLE_AREA", "SITE", "LOT"}:
            continue
        key = safe_str(getattr(zone, "id", None), zone_name or f"ZONE-{len(nodes)+1}")
        if key in seen:
            continue
        seen.add(key)
        service_x, service_y = _service_point_for_zone(zone, street_edge)
        centroid = getattr(zone.boundary, "centroid", lambda: Point3D(service_x, service_y, DEFAULT_PAD_ELEV))()
        bbox = getattr(zone.boundary, "bbox", None)
        nodes.append(
            {
                "zone_id": safe_str(getattr(zone, "id", None), key),
                "zone_name": zone_name or f"BLDG-{len(nodes)+1}",
                "service_point": [service_x, service_y],
                "centroid": [safe_float(getattr(centroid, "x", service_x), service_x), safe_float(getattr(centroid, "y", service_y), service_y)],
                "bbox": {
                    "min_x": safe_float(getattr(bbox, "min_x", service_x), service_x),
                    "min_y": safe_float(getattr(bbox, "min_y", service_y), service_y),
                    "max_x": safe_float(getattr(bbox, "max_x", service_x), service_x),
                    "max_y": safe_float(getattr(bbox, "max_y", service_y), service_y),
                } if bbox is not None else None,
            }
        )
    return nodes


def _sanitary_user_input_summary(parsed: Dict[str, Any], project: ProjectModel) -> Optional[Dict[str, Any]]:
    execution_payload = unwrap_fields_for_execution(parsed)
    sanitary_features = [
        safe_dict(feature)
        for feature in safe_list(execution_payload.get("utility_network"))
        if isinstance(feature, dict)
        and (lower_text(feature.get("utility_type")) in {"sanitary", "sewer", "san"} or safe_str(feature.get("layer"), "").upper() == "SAN")
    ]
    if not sanitary_features:
        return None

    segments: List[Dict[str, Any]] = []
    total_length = 0.0
    main_length = 0.0
    lateral_length = 0.0
    for index, feature in enumerate(sanitary_features, start=1):
        route_points = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(feature.get("points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        if len(route_points) < 2:
            continue
        length_ft = polyline_length(route_points)
        total_length += length_ft
        role = "main" if index == 1 else "lateral"
        if role == "main":
            main_length += length_ft
        else:
            lateral_length += length_ft
        slope_ft_ft = max(_sanitary_min_slope(role, safe_float(feature.get("diameter"), 8.0)), 0.01)
        segments.append(
            {
                "name": safe_str(feature.get("label"), f"SAN-{index}"),
                "segment_role": role,
                "route_points": route_points,
                "length_ft": round(length_ft, 3),
                "diameter_in": round(max(4.0, safe_float(feature.get("diameter"), 8.0)), 3),
                "slope_ft_ft": round(slope_ft_ft, 5),
                "start_invert_ft": round(DEFAULT_PAD_ELEV - 4.0, 3),
                "end_invert_ft": round(DEFAULT_PAD_ELEV - 4.0 - slope_ft_ft * length_ft, 3),
                "hydraulic_mode": "gravity",
                "warning_count": 0,
                "warnings": [],
            }
        )

    if not segments:
        return None

    return {
        "success": True,
        "message": "Sanitary stage accepted user-supplied sanitary geometry.",
        "source": "user_input",
        "fallback_used": False,
        "route_count": len(segments),
        "service_count": max(1, len(segments) - 1),
        "served_building_count": max(1, len(_sanitary_building_nodes(project, safe_str(parsed.get("street_edge"), "bottom")))),
        "total_length_ft": round(total_length, 3),
        "main_length_ft": round(main_length, 3),
        "lateral_length_ft": round(lateral_length, 3),
        "service_connection_length_ft": 0.0,
        "manhole_count": 0,
        "segments": segments,
        "manholes": [],
        "missing_service_buildings": [],
        "slope_violations": [],
        "disconnected_segments": [],
        "storm_conflicts": [],
        "missing_manhole_points": [],
        "stats": {
            "segment_count": len(segments),
            "route_count": len(segments),
            "total_length_ft": round(total_length, 3),
            "main_length_ft": round(main_length, 3),
            "lateral_length_ft": round(lateral_length, 3),
            "service_connection_length_ft": 0.0,
            "manhole_count": 0,
            "service_count": max(1, len(segments) - 1),
        },
    }


def _storm_pipe_paths(project: ProjectModel) -> List[List[List[float]]]:
    paths: List[List[List[float]]] = []
    for segment in safe_list(project.meta.get("storm_pipe_segments")):
        rec = safe_dict(segment)
        raw = safe_list(rec.get("path") or rec.get("route_points"))
        path = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in raw if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        if len(path) >= 2:
            paths.append(path)
    return paths


def _route_conflicts(route_points: List[List[float]], other_paths: Sequence[Sequence[Sequence[float]]], threshold_ft: float = 6.0) -> List[Dict[str, Any]]:
    conflicts: List[Dict[str, Any]] = []
    for other_index, other in enumerate(other_paths, start=1):
        other_points = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in other if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        if len(other_points) < 2:
            continue
        for idx in range(1, len(route_points)):
            for jdx in range(1, len(other_points)):
                distance = _segment_distance(route_points[idx - 1], route_points[idx], other_points[jdx - 1], other_points[jdx])
                if distance <= threshold_ft:
                    conflicts.append(
                        {
                            "segment_index": idx,
                            "other_path_index": other_index,
                            "clearance_ft": round(distance, 3),
                        }
                    )
                    break
            if conflicts:
                break
    return conflicts


def _utility_system_type(rec: Dict[str, Any], hooks: Optional[Dict[str, Any]] = None) -> str:
    text = lower_text(
        " ".join(
            safe_str(value)
            for value in (
                rec.get("system"),
                rec.get("system_type"),
                rec.get("utility_type"),
                rec.get("type"),
                rec.get("name"),
                safe_dict(hooks).get("utility_system_type"),
            )
            if safe_str(value)
        )
    )
    if "sanitary" in text or "sewer" in text:
        return "sanitary"
    if "storm" in text or "drain" in text:
        return "storm"
    if "gas" in text:
        return "gas"
    if "electric" in text or "power" in text:
        return "electric"
    if "telecom" in text or "fiber" in text or "communication" in text:
        return "telecom"
    return "water"


def _canonical_changed_systems(systems: Sequence[str]) -> List[str]:
    values = list(systems) if isinstance(systems, (list, tuple, set)) else []
    rows = {safe_str(item) for item in values if safe_str(item)}
    if rows & {"water", "gas", "electric", "telecom"}:
        rows.add("utilities")
    return sorted(rows)


COORDINATION_CROSSING_RULES: Dict[Tuple[str, str], Dict[str, Any]] = {
    tuple(sorted(("storm", "sanitary"))): {
        "preferred_lower_system": "storm",
        "required_horizontal_clearance_ft": 5.0,
        "required_vertical_clearance_ft": 1.5,
        "preferred_crossing_angle_deg": 75.0,
        "roadway_min_cover_ft": 3.5,
    },
    tuple(sorted(("storm", "water"))): {
        "preferred_lower_system": "storm",
        "required_horizontal_clearance_ft": 5.0,
        "required_vertical_clearance_ft": 1.0,
        "preferred_crossing_angle_deg": 70.0,
        "roadway_min_cover_ft": 3.5,
    },
    tuple(sorted(("sanitary", "water"))): {
        "preferred_lower_system": "sanitary",
        "required_horizontal_clearance_ft": 10.0,
        "required_vertical_clearance_ft": 1.5,
        "preferred_crossing_angle_deg": 75.0,
        "roadway_min_cover_ft": 4.0,
    },
    tuple(sorted(("gas", "water"))): {
        "preferred_lower_system": "gas",
        "required_horizontal_clearance_ft": 3.0,
        "required_vertical_clearance_ft": 1.0,
        "preferred_crossing_angle_deg": 70.0,
    },
    tuple(sorted(("electric", "water"))): {
        "preferred_lower_system": "electric",
        "required_horizontal_clearance_ft": 3.0,
        "required_vertical_clearance_ft": 1.0,
        "preferred_crossing_angle_deg": 70.0,
    },
    tuple(sorted(("gas", "sanitary"))): {
        "preferred_lower_system": "sanitary",
        "required_horizontal_clearance_ft": 5.0,
        "required_vertical_clearance_ft": 1.0,
        "preferred_crossing_angle_deg": 75.0,
    },
    tuple(sorted(("electric", "sanitary"))): {
        "preferred_lower_system": "sanitary",
        "required_horizontal_clearance_ft": 5.0,
        "required_vertical_clearance_ft": 1.0,
        "preferred_crossing_angle_deg": 75.0,
    },
    tuple(sorted(("gas", "storm"))): {
        "preferred_lower_system": "storm",
        "required_horizontal_clearance_ft": 3.0,
        "required_vertical_clearance_ft": 1.0,
        "preferred_crossing_angle_deg": 70.0,
    },
    tuple(sorted(("electric", "storm"))): {
        "preferred_lower_system": "storm",
        "required_horizontal_clearance_ft": 3.0,
        "required_vertical_clearance_ft": 1.0,
        "preferred_crossing_angle_deg": 70.0,
    },
    tuple(sorted(("electric", "gas"))): {
        "preferred_lower_system": "gas",
        "required_horizontal_clearance_ft": 2.0,
        "required_vertical_clearance_ft": 1.0,
        "preferred_crossing_angle_deg": 60.0,
    },
    tuple(sorted(("telecom", "water"))): {
        "preferred_lower_system": "telecom",
        "required_horizontal_clearance_ft": 2.0,
        "required_vertical_clearance_ft": 1.0,
        "preferred_crossing_angle_deg": 60.0,
    },
    tuple(sorted(("telecom", "sanitary"))): {
        "preferred_lower_system": "sanitary",
        "required_horizontal_clearance_ft": 5.0,
        "required_vertical_clearance_ft": 1.0,
        "preferred_crossing_angle_deg": 75.0,
    },
    tuple(sorted(("telecom", "storm"))): {
        "preferred_lower_system": "storm",
        "required_horizontal_clearance_ft": 3.0,
        "required_vertical_clearance_ft": 1.0,
        "preferred_crossing_angle_deg": 70.0,
    },
    tuple(sorted(("telecom", "gas"))): {
        "preferred_lower_system": "gas",
        "required_horizontal_clearance_ft": 2.0,
        "required_vertical_clearance_ft": 1.0,
        "preferred_crossing_angle_deg": 60.0,
    },
    tuple(sorted(("electric", "telecom"))): {
        "preferred_lower_system": "telecom",
        "required_horizontal_clearance_ft": 2.0,
        "required_vertical_clearance_ft": 1.0,
        "preferred_crossing_angle_deg": 60.0,
    },
}

PRECOORDINATION_SANITARY_MAIN_COVER_FT = 7.0
PRECOORDINATION_SANITARY_SERVICE_COVER_FT = 5.5
PRECOORDINATION_STORM_MAIN_COVER_FT = (
    PRECOORDINATION_SANITARY_MAIN_COVER_FT
    + COORDINATION_CROSSING_RULES[tuple(sorted(("storm", "sanitary")))]["required_vertical_clearance_ft"]
    + 1.0
)

SYSTEM_OWNERSHIP_PRIORITY: Dict[str, int] = {
    "roadway": 0,
    "storm_main": 1,
    "sanitary_main": 2,
    "water_main": 3,
    "gas_main": 3,
    "electric_main": 3,
    "storm_lateral": 4,
    "sanitary_lateral": 5,
    "telecom_main": 5,
    "utility_service": 6,
    "generic": 7,
}

PROTECTED_ZONE_RULES: Dict[str, Dict[str, Any]] = {
    "building_pad": {"penalty": 120.0, "avoid": True},
    "roadway": {"penalty": 60.0, "avoid": True},
    "ada_path": {"penalty": 140.0, "avoid": True},
    "fire_lane": {"penalty": 160.0, "avoid": True},
    "access_aisle": {"penalty": 150.0, "avoid": True},
    "parking_field": {"penalty": 35.0, "avoid": False},
    "retaining_sensitive": {"penalty": 180.0, "avoid": True},
    "wetland": {"penalty": 260.0, "avoid": True},
    "floodplain": {"penalty": 210.0, "avoid": True},
    "tree_save": {"penalty": 200.0, "avoid": True},
    "row_conflict": {"penalty": 170.0, "avoid": True},
    "construction_access": {"penalty": 130.0, "avoid": True},
}

GIS_PROTECTED_LAYER_RULES: Dict[str, Dict[str, Any]] = {
    "wetlands": {"kind": "wetland", "buffer_ft": 10.0},
    "wetland": {"kind": "wetland", "buffer_ft": 10.0},
    "floodplain": {"kind": "floodplain", "buffer_ft": 8.0},
    "floodplains": {"kind": "floodplain", "buffer_ft": 8.0},
    "row": {"kind": "row_conflict", "buffer_ft": 5.0},
    "right_of_way": {"kind": "row_conflict", "buffer_ft": 5.0},
    "tree_save": {"kind": "tree_save", "buffer_ft": 8.0},
    "tree_save_zones": {"kind": "tree_save", "buffer_ft": 8.0},
    "protected_trees": {"kind": "tree_save", "buffer_ft": 8.0},
    "construction_access": {"kind": "construction_access", "buffer_ft": 6.0},
}

HARD_PROTECTED_ZONE_KINDS = {
    "ada_path",
    "fire_lane",
    "access_aisle",
    "retaining_sensitive",
    "wetland",
    "floodplain",
    "tree_save",
    "row_conflict",
    "construction_access",
}

MAX_COORDINATION_CONFLICTS_PER_CANDIDATE = 8
MAX_COORDINATION_CLUSTERS_PER_GROUP_PLAN = 3


def _segment_midpoint(path: Sequence[Sequence[float]]) -> List[float]:
    if len(path) < 2:
        point = safe_list(path[0]) if path else [0.0, 0.0]
        return [safe_float(point[0], 0.0), safe_float(point[1], 0.0)]
    start = safe_list(path[0])
    end = safe_list(path[-1])
    return [
        round((safe_float(start[0], 0.0) + safe_float(end[0], 0.0)) / 2.0, 3),
        round((safe_float(start[1], 0.0) + safe_float(end[1], 0.0)) / 2.0, 3),
    ]


def _path_station_at_midpoint(path: Sequence[Sequence[float]]) -> float:
    return round(max(polyline_length(path), 0.0) / 2.0, 3)


def _normalized_summary_segments(project: ProjectModel, manager: ProjectManager) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []

    storm = safe_dict(manager.latest_outputs.get("storm_pipe_summary", project.meta.get("storm_pipe_summary", {})))
    for row in safe_list(storm.get("segments")):
        rec = safe_dict(row)
        raw_path = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(rec.get("path") or rec.get("route_points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        path = _sample_coordination_path(raw_path)
        if len(path) < 2:
            continue
        slope_ft_ft = safe_float(rec.get("slope_ft_ft"), safe_float(rec.get("slope_pct"), 0.0) / 100.0)
        segments.append(
            {
                "system": "storm",
                "name": safe_str(rec.get("pipe"), safe_str(rec.get("name"), "STORM")),
                "path": path,
                "length_ft": round(polyline_length(path), 3),
                "diameter_in": safe_float(rec.get("diameter_in"), 12.0),
                "start_invert_ft": safe_float(rec.get("start_invert_ft"), safe_float(rec.get("start_invert"), DEFAULT_PAD_ELEV - 4.0)),
                "end_invert_ft": safe_float(rec.get("end_invert_ft"), safe_float(rec.get("end_invert"), DEFAULT_PAD_ELEV - 5.0)),
                "cover_start_ft": safe_float(rec.get("cover_start_ft"), PIPE_MIN_COVER_FT),
                "cover_end_ft": safe_float(rec.get("cover_end_ft"), PIPE_MIN_COVER_FT),
                "min_cover_ft": PIPE_MIN_COVER_FT,
                "slope_ft_ft": slope_ft_ft,
                "min_slope_ft_ft": PIPE_MIN_SLOPE,
                "gravity": True,
                "from_name": safe_str(rec.get("from"), ""),
                "to_name": safe_str(rec.get("to"), ""),
                "flow_cfs": safe_float(rec.get("flow_cfs"), 0.0),
                "capacity_cfs": safe_float(rec.get("capacity_cfs"), 0.0),
                "capacity_ratio": safe_float(rec.get("capacity_ratio"), 0.0),
                "segment_role": safe_str(rec.get("segment_role") or rec.get("role"), ""),
                "source_summary": "storm_pipe_summary",
            }
        )

    sanitary = safe_dict(manager.latest_outputs.get("sanitary", project.meta.get("sanitary_summary", {})))
    grading = safe_dict(manager.latest_outputs.get("grading", project.meta.get("grading_summary", {})))
    proposed_surface = grading.get("proposed_surface")
    for row in safe_list(sanitary.get("segments")):
        rec = safe_dict(row)
        raw_path = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(rec.get("route_points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        path = _sample_coordination_path(raw_path)
        if len(path) < 2:
            continue
        surface_start = _sample_grid_surface(proposed_surface, path[0][0], path[0][1], DEFAULT_PAD_ELEV)
        surface_end = _sample_grid_surface(proposed_surface, path[-1][0], path[-1][1], DEFAULT_PAD_ELEV)
        start_invert = safe_float(rec.get("start_invert_ft"), DEFAULT_PAD_ELEV - 5.0)
        end_invert = safe_float(rec.get("end_invert_ft"), DEFAULT_PAD_ELEV - 6.0)
        segments.append(
            {
                "system": "sanitary",
                "name": safe_str(rec.get("name"), "SAN"),
                "path": path,
                "length_ft": round(polyline_length(path), 3),
                "diameter_in": safe_float(rec.get("diameter_in"), 8.0),
                "start_invert_ft": start_invert,
                "end_invert_ft": end_invert,
                "cover_start_ft": round(surface_start - start_invert, 3),
                "cover_end_ft": round(surface_end - end_invert, 3),
                "min_cover_ft": PIPE_MIN_COVER_FT,
                "slope_ft_ft": safe_float(rec.get("slope_ft_ft"), 0.0),
                "min_slope_ft_ft": _sanitary_min_slope(safe_str(rec.get("segment_role"), "main"), safe_float(rec.get("diameter_in"), 8.0)),
                "gravity": True,
                "from_name": safe_str(rec.get("start_name"), ""),
                "to_name": safe_str(rec.get("end_name"), ""),
                "segment_role": safe_str(rec.get("segment_role"), ""),
                "served_building": safe_str(rec.get("served_building"), ""),
                "flow_cfs": safe_float(rec.get("flow_cfs"), 0.0),
                "capacity_cfs": safe_float(rec.get("capacity_cfs"), 0.0),
                "capacity_ratio": safe_float(rec.get("capacity_ratio"), 0.0),
                "source_summary": "sanitary_summary",
            }
        )

    utilities = safe_dict(manager.latest_outputs.get("utilities", project.meta.get("utility_summary", {})))
    hooks = safe_dict(utilities.get("conflict_hooks"))
    for row in safe_list(hooks.get("utility_segments")):
        rec = safe_dict(row)
        raw_path = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(rec.get("route_points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        path = _sample_coordination_path(raw_path)
        if len(path) < 2:
            continue
        system = _utility_system_type(rec, hooks)
        min_cover = safe_float(rec.get("min_cover_ft"), 3.0 if system in {"water", "gas"} else 2.5)
        segments.append(
            {
                "system": system,
                "name": safe_str(rec.get("name"), "UTILITY"),
                "path": path,
                "length_ft": round(polyline_length(path), 3),
                "diameter_in": safe_float(rec.get("diameter_in"), 8.0),
                "start_invert_ft": safe_float(rec.get("start_invert_ft"), DEFAULT_PAD_ELEV - 4.0),
                "end_invert_ft": safe_float(rec.get("end_invert_ft"), DEFAULT_PAD_ELEV - 4.0),
                "cover_start_ft": safe_float(rec.get("cover_start_ft"), min_cover),
                "cover_end_ft": safe_float(rec.get("cover_end_ft"), min_cover),
                "min_cover_ft": min_cover,
                "slope_ft_ft": safe_float(rec.get("slope_ft_ft"), 0.0),
                "min_slope_ft_ft": safe_float(hooks.get("minimum_vertical_separation_ft"), 0.0) if system in {"storm", "sanitary"} else 0.0,
                "gravity": system in {"storm", "sanitary"} or safe_str(rec.get("hydraulic_mode"), "").lower() == "gravity",
                "from_name": safe_str(rec.get("start_name"), ""),
                "to_name": safe_str(rec.get("end_name"), ""),
                "segment_role": safe_str(rec.get("segment_role") or rec.get("role"), ""),
                "source_summary": "utility_summary",
            }
        )

    return segments


def _coordinate_pairs_from_geometry(value: Any) -> List[List[float]]:
    pairs: List[List[float]] = []
    if not isinstance(value, (list, tuple)):
        return pairs
    if len(value) >= 2 and isinstance(value[0], (int, float)) and isinstance(value[1], (int, float)):
        pairs.append([safe_float(value[0], 0.0), safe_float(value[1], 0.0)])
        return pairs
    for item in value:
        pairs.extend(_coordinate_pairs_from_geometry(item))
    return pairs


def _bbox_from_feature(feature: Dict[str, Any]) -> Optional[Dict[str, float]]:
    rec = safe_dict(feature)
    bbox = safe_list(rec.get("bbox") or safe_dict(rec.get("properties")).get("bbox"))
    if len(bbox) >= 4:
        min_x = safe_float(bbox[0], 0.0)
        min_y = safe_float(bbox[1], 0.0)
        max_x = safe_float(bbox[2], min_x)
        max_y = safe_float(bbox[3], min_y)
        return {"x": min(min_x, max_x), "y": min(min_y, max_y), "w": abs(max_x - min_x), "h": abs(max_y - min_y)}
    geometry = safe_dict(rec.get("geometry")) or rec
    points = _coordinate_pairs_from_geometry(geometry.get("coordinates"))
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {"x": min(xs), "y": min(ys), "w": max(xs) - min(xs), "h": max(ys) - min(ys)}


def _ordered_line_points_from_coordinates(value: Any) -> List[List[float]]:
    if not isinstance(value, (list, tuple)):
        return []
    if len(value) >= 2 and isinstance(value[0], (int, float)) and isinstance(value[1], (int, float)):
        return [[safe_float(value[0], 0.0), safe_float(value[1], 0.0)]]
    if value and all(isinstance(item, (list, tuple)) and len(item) >= 2 and isinstance(item[0], (int, float)) and isinstance(item[1], (int, float)) for item in value):
        return [[safe_float(item[0], 0.0), safe_float(item[1], 0.0)] for item in value]
    candidates = [_ordered_line_points_from_coordinates(item) for item in value]
    candidates = [candidate for candidate in candidates if len(candidate) >= 2]
    if not candidates:
        return []
    return max(candidates, key=polyline_length)


def _corridor_centerline_from_feature(feature: Dict[str, Any], bbox: Dict[str, float], orientation: str) -> List[List[float]]:
    rec = safe_dict(feature)
    props = safe_dict(rec.get("properties"))
    explicit = _ordered_line_points_from_coordinates(props.get("centerline") or rec.get("centerline"))
    if len(explicit) >= 2:
        return _dedupe_path_points(explicit)
    geometry = safe_dict(rec.get("geometry")) or rec
    geom_type = lower_text(geometry.get("type"))
    if "line" in geom_type:
        line = _ordered_line_points_from_coordinates(geometry.get("coordinates"))
        if len(line) >= 2:
            return _dedupe_path_points(line)
    x = safe_float(bbox.get("x"), 0.0)
    y = safe_float(bbox.get("y"), 0.0)
    w = safe_float(bbox.get("w"), 0.0)
    h = safe_float(bbox.get("h"), 0.0)
    if orientation == "horizontal":
        axis = y + h / 2.0
        return [[round(x, 3), round(axis, 3)], [round(x + w, 3), round(axis, 3)]]
    axis = x + w / 2.0
    return [[round(axis, 3), round(y, 3)], [round(axis, 3), round(y + h, 3)]]


def _gis_feature_rows(raw_layer: Any) -> List[Dict[str, Any]]:
    if isinstance(raw_layer, list):
        return [safe_dict(item) for item in raw_layer if safe_dict(item)]
    rec = safe_dict(raw_layer)
    for key in ("features", "items", "records"):
        rows = [safe_dict(item) for item in safe_list(rec.get(key)) if safe_dict(item)]
        if rows:
            return rows
    return [rec] if rec else []


def _feature_label(feature: Dict[str, Any], fallback: str) -> str:
    rec = safe_dict(feature)
    props = safe_dict(rec.get("properties"))
    return safe_str(
        props.get("name")
        or props.get("Name")
        or props.get("label")
        or rec.get("id")
        or props.get("id")
        or props.get("OBJECTID")
        or fallback
    )


def _protected_zones_from_gis(project: ProjectModel) -> List[Dict[str, Any]]:
    meta = safe_dict(project.meta)
    gis_layers = safe_dict(meta.get("gis_layers"))
    existing = safe_dict(meta.get("existing_conditions"))
    if not gis_layers:
        gis_layers = safe_dict(existing.get("gis_layers")) or safe_dict(existing.get("layers")) or existing
    protected_rows = safe_list(meta.get("protected_zones"))
    zones: List[Dict[str, Any]] = []
    for layer_name, layer_rule in GIS_PROTECTED_LAYER_RULES.items():
        raw = gis_layers.get(layer_name)
        for index, feature in enumerate(_gis_feature_rows(raw), start=1):
            bbox = _bbox_from_feature(feature)
            if bbox is None:
                continue
            kind = safe_str(layer_rule.get("kind"))
            rule = safe_dict(PROTECTED_ZONE_RULES.get(kind))
            zones.append(
                {
                    "kind": kind,
                    "name": _feature_label(feature, f"{layer_name.upper()}-{index}"),
                    "x": safe_float(bbox.get("x"), 0.0),
                    "y": safe_float(bbox.get("y"), 0.0),
                    "w": max(safe_float(bbox.get("w"), 0.0), 0.0),
                    "h": max(safe_float(bbox.get("h"), 0.0), 0.0),
                    "buffer_ft": safe_float(layer_rule.get("buffer_ft"), 6.0),
                    "penalty": safe_float(rule.get("penalty"), 120.0),
                    "avoid": bool(rule.get("avoid", True)),
                    "source": "gis_layers",
                    "source_layer": layer_name,
                }
            )
    for index, feature in enumerate([safe_dict(item) for item in protected_rows if safe_dict(item)], start=1):
        bbox = _bbox_from_feature(feature) or {
            "x": safe_float(feature.get("x"), 0.0),
            "y": safe_float(feature.get("y"), 0.0),
            "w": safe_float(feature.get("w") or feature.get("width"), 0.0),
            "h": safe_float(feature.get("h") or feature.get("height"), 0.0),
        }
        kind = safe_str(feature.get("kind") or feature.get("type"), "construction_access")
        rule = safe_dict(PROTECTED_ZONE_RULES.get(kind)) or safe_dict(PROTECTED_ZONE_RULES.get("construction_access"))
        zones.append(
            {
                "kind": kind,
                "name": _feature_label(feature, f"PROTECTED-{index}"),
                "x": safe_float(bbox.get("x"), 0.0),
                "y": safe_float(bbox.get("y"), 0.0),
                "w": max(safe_float(bbox.get("w"), 0.0), 0.0),
                "h": max(safe_float(bbox.get("h"), 0.0), 0.0),
                "buffer_ft": safe_float(feature.get("buffer_ft"), 6.0),
                "penalty": safe_float(feature.get("penalty"), safe_float(rule.get("penalty"), 120.0)),
                "avoid": bool(feature.get("avoid", rule.get("avoid", True))),
                "source": "protected_zones",
            }
        )
    return zones


def _expanded_obstacle_rectangles(project: ProjectModel) -> List[Dict[str, Any]]:
    obstacles: List[Dict[str, Any]] = []
    actions = safe_list(safe_dict(project.meta.get("_expanded_plan", {})).get("actions"))
    for action in actions:
        rec = safe_dict(action)
        if lower_text(rec.get("task")) != "rectangle":
            continue
        layer = safe_str(rec.get("layer"), "").upper()
        zone_kind = {
            "ROAD": "roadway",
            "BUILDING": "building_pad",
            "WALK": "ada_path",
            "FIRE": "fire_lane",
            "PARKING": "parking_field",
        }.get(layer)
        if zone_kind is None:
            continue
        origin = safe_list(rec.get("origin"))
        if len(origin) < 2:
            continue
        x = safe_float(origin[0], 0.0)
        y = safe_float(origin[1], 0.0)
        w = safe_float(rec.get("width"), 0.0)
        h = safe_float(rec.get("height"), 0.0)
        if w <= 0.0 or h <= 0.0:
            continue
        obstacles.append(
            {
                "kind": zone_kind,
                "name": safe_str(rec.get("label"), layer),
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "buffer_ft": 4.0 if zone_kind in {"roadway", "fire_lane"} else 2.0,
                "penalty": safe_float(safe_dict(PROTECTED_ZONE_RULES.get(zone_kind)).get("penalty"), 50.0),
                "avoid": bool(safe_dict(PROTECTED_ZONE_RULES.get(zone_kind)).get("avoid", False)),
            }
        )
    obstacles.extend(_protected_zones_from_gis(project))
    return obstacles


def _point_inside_buffered_rect(point: Sequence[float], rect: Dict[str, Any]) -> bool:
    x = safe_float(point[0], 0.0)
    y = safe_float(point[1], 0.0)
    pad = safe_float(rect.get("buffer_ft"), 0.0)
    return (
        safe_float(rect.get("x"), 0.0) - pad <= x <= safe_float(rect.get("x"), 0.0) + safe_float(rect.get("w"), 0.0) + pad
        and safe_float(rect.get("y"), 0.0) - pad <= y <= safe_float(rect.get("y"), 0.0) + safe_float(rect.get("h"), 0.0) + pad
    )


def _segment_hits_buffered_rect(start: Sequence[float], end: Sequence[float], rect: Dict[str, Any]) -> bool:
    if _point_inside_buffered_rect(start, rect) or _point_inside_buffered_rect(end, rect):
        return True
    pad = safe_float(rect.get("buffer_ft"), 0.0)
    x0 = safe_float(rect.get("x"), 0.0) - pad
    y0 = safe_float(rect.get("y"), 0.0) - pad
    x1 = safe_float(rect.get("x"), 0.0) + safe_float(rect.get("w"), 0.0) + pad
    y1 = safe_float(rect.get("y"), 0.0) + safe_float(rect.get("h"), 0.0) + pad
    sx0 = min(safe_float(start[0], 0.0), safe_float(end[0], 0.0))
    sx1 = max(safe_float(start[0], 0.0), safe_float(end[0], 0.0))
    sy0 = min(safe_float(start[1], 0.0), safe_float(end[1], 0.0))
    sy1 = max(safe_float(start[1], 0.0), safe_float(end[1], 0.0))
    if sx1 < x0 or sx0 > x1 or sy1 < y0 or sy0 > y1:
        return False
    edges = [
        ([x0, y0], [x1, y0]),
        ([x1, y0], [x1, y1]),
        ([x1, y1], [x0, y1]),
        ([x0, y1], [x0, y0]),
    ]
    return any(_segment_distance(start, end, edge_start, edge_end) <= 1e-6 for edge_start, edge_end in edges)


def _path_hits_buffered_rect(path: Sequence[Sequence[float]], rect: Dict[str, Any]) -> bool:
    point_count = len(path)
    if point_count < 2:
        return any(_point_inside_buffered_rect(point, rect) for point in path)
    # Some terrain/drainage paths can carry thousands of interpolated points.
    # Protected-zone checks only need corridor-scale evidence during candidate
    # scoring, so sample evenly to keep coordination solves deterministic.
    max_points = 80
    if point_count > max_points:
        step = max(1, int(math.ceil((point_count - 1) / float(max_points - 1))))
        sampled = list(path[0:point_count:step])
        if sampled[-1] is not path[-1]:
            sampled.append(path[-1])
    else:
        sampled = list(path)
    return any(
        _segment_hits_buffered_rect(sampled[idx - 1], sampled[idx], rect)
        for idx in range(1, len(sampled))
    )


def _sample_coordination_path(path: Sequence[Sequence[float]], max_points: int = 12) -> List[Sequence[float]]:
    point_count = len(path)
    if point_count <= max_points:
        return list(path)
    step = max(1, int(math.ceil((point_count - 1) / float(max_points - 1))))
    sampled = list(path[0:point_count:step])
    if sampled[-1] is not path[-1]:
        sampled.append(path[-1])
    return sampled


def _path_min_segment_distance(path_a: Sequence[Sequence[float]], path_b: Sequence[Sequence[float]], *, early_stop_ft: float = 1.0) -> float:
    def _bbox(path: Sequence[Sequence[float]]) -> Tuple[float, float, float, float]:
        xs = [safe_float(point[0], 0.0) for point in path]
        ys = [safe_float(point[1], 0.0) for point in path]
        return min(xs), min(ys), max(xs), max(ys)

    a_min_x, a_min_y, a_max_x, a_max_y = _bbox(path_a)
    b_min_x, b_min_y, b_max_x, b_max_y = _bbox(path_b)
    bbox_dx = max(0.0, max(a_min_x, b_min_x) - min(a_max_x, b_max_x))
    bbox_dy = max(0.0, max(a_min_y, b_min_y) - min(a_max_y, b_max_y))
    bbox_distance = math.hypot(bbox_dx, bbox_dy)
    if bbox_distance > max(early_stop_ft, 12.0):
        return bbox_distance
    best = float("inf")
    for a_idx in range(1, len(path_a)):
        a0 = path_a[a_idx - 1]
        a1 = path_a[a_idx]
        ax0 = min(safe_float(a0[0], 0.0), safe_float(a1[0], 0.0))
        ax1 = max(safe_float(a0[0], 0.0), safe_float(a1[0], 0.0))
        ay0 = min(safe_float(a0[1], 0.0), safe_float(a1[1], 0.0))
        ay1 = max(safe_float(a0[1], 0.0), safe_float(a1[1], 0.0))
        for b_idx in range(1, len(path_b)):
            b0 = path_b[b_idx - 1]
            b1 = path_b[b_idx]
            bx0 = min(safe_float(b0[0], 0.0), safe_float(b1[0], 0.0))
            bx1 = max(safe_float(b0[0], 0.0), safe_float(b1[0], 0.0))
            by0 = min(safe_float(b0[1], 0.0), safe_float(b1[1], 0.0))
            by1 = max(safe_float(b0[1], 0.0), safe_float(b1[1], 0.0))
            bbox_dx = max(0.0, max(ax0, bx0) - min(ax1, bx1))
            bbox_dy = max(0.0, max(ay0, by0) - min(ay1, by1))
            if bbox_dx > best or bbox_dy > best:
                continue
            distance = _segment_distance(a0, a1, b0, b1)
            if distance < best:
                best = distance
                if best <= early_stop_ft:
                    return best
    return best if math.isfinite(best) else 0.0


def _dedupe_path_points(path: Sequence[Sequence[float]]) -> List[List[float]]:
    deduped: List[List[float]] = []
    for point in path:
        row = [safe_float(point[0], 0.0), safe_float(point[1], 0.0)]
        if not deduped or abs(row[0] - deduped[-1][0]) > 1e-6 or abs(row[1] - deduped[-1][1]) > 1e-6:
            deduped.append(row)
    return deduped


def _point_key(point: Sequence[float], precision: int = 3) -> Tuple[float, float]:
    return (round(safe_float(point[0], 0.0), precision), round(safe_float(point[1], 0.0), precision))


def _path_turn_count(path: Sequence[Sequence[float]]) -> int:
    points = _dedupe_path_points(path)
    turns = 0
    for idx in range(1, len(points) - 1):
        ax = points[idx][0] - points[idx - 1][0]
        ay = points[idx][1] - points[idx - 1][1]
        bx = points[idx + 1][0] - points[idx][0]
        by = points[idx + 1][1] - points[idx][1]
        if abs(ax * by - ay * bx) > 1e-6:
            turns += 1
    return turns


def _segment_ownership_class(segment: Dict[str, Any]) -> str:
    system = safe_str(segment.get("system") or segment.get("system_type"))
    role = safe_str(segment.get("segment_role"))
    if system == "storm":
        return "storm_main" if role in {"", "main"} else "storm_lateral"
    if system == "sanitary":
        return "sanitary_main" if role in {"", "main"} else "sanitary_lateral"
    if system == "water":
        return "water_main" if role in {"", "main"} else "utility_service"
    if system == "gas":
        return "gas_main" if role in {"", "main"} else "utility_service"
    if system == "electric":
        return "electric_main" if role in {"", "main"} else "utility_service"
    if system == "telecom":
        return "telecom_main" if role in {"", "main"} else "utility_service"
    return "utility_service" if role in {"service", "service_connection", "lateral"} else "generic"


def _crossing_rule_for(systems: Sequence[str]) -> Dict[str, Any]:
    pair = tuple(sorted([safe_str(item) for item in systems if safe_str(item)]))
    return deepcopy(COORDINATION_CROSSING_RULES.get(pair, {}))


def _clearance_resolution_steps(
    interaction_type: str,
    strategy_name: str,
    ordered_targets: Sequence[Tuple[str, str]],
    preferred_lower: str = "",
) -> List[Tuple[str, str]]:
    preferred_lower = safe_str(preferred_lower)
    upper_targets = [item for item in ordered_targets if safe_str(item[0]) != preferred_lower] or list(ordered_targets)
    lower_targets = [item for item in ordered_targets if safe_str(item[0]) == preferred_lower] or list(ordered_targets)
    utility_gravity_systems = {"sanitary", "storm", "storm_pipes"}
    utility_pressurized_systems = {"water", "utilities", "gas", "electric", "telecom"}

    def _utility_vertical_first(rows: Sequence[Tuple[str, str]]) -> List[Tuple[str, str]]:
        vertical_first: List[Tuple[str, str]] = []
        reroute_after: List[Tuple[str, str]] = []
        for system_name, _role in rows:
            system_key = safe_str(system_name).lower()
            if system_key in utility_gravity_systems or system_name == preferred_lower:
                vertical_first.append(("vertical", system_name))
                reroute_after.append(("reroute", system_name))
            else:
                reroute_after.append(("reroute", system_name))
                reroute_after.append(("vertical", system_name))
        return vertical_first + reroute_after

    def _utility_reroute_first(rows: Sequence[Tuple[str, str]]) -> List[Tuple[str, str]]:
        reroute_first: List[Tuple[str, str]] = []
        vertical_after: List[Tuple[str, str]] = []
        for system_name, _role in rows:
            system_key = safe_str(system_name).lower()
            if system_key in utility_pressurized_systems or system_name != preferred_lower:
                reroute_first.append(("reroute", system_name))
                vertical_after.append(("vertical", system_name))
            else:
                vertical_after.append(("vertical", system_name))
                vertical_after.append(("reroute", system_name))
        return reroute_first + vertical_after

    utility_style = any(
        safe_str(system_name).lower() in utility_gravity_systems.union(utility_pressurized_systems)
        for system_name, _role in ordered_targets
    )
    if utility_style:
        if interaction_type == "parallel":
            if strategy_name == "parallel_shift_first":
                return [("reroute", system_name) for system_name, _role in upper_targets + lower_targets]
            return _utility_vertical_first(lower_targets) + _utility_reroute_first(upper_targets)
        if strategy_name == "upper_reroute_first":
            return _utility_reroute_first(upper_targets) + _utility_vertical_first(lower_targets)
        return _utility_vertical_first(lower_targets) + _utility_reroute_first(upper_targets)

    resolution_steps: List[Tuple[str, str]] = []
    if interaction_type == "parallel":
        if strategy_name == "parallel_shift_first":
            resolution_steps.extend([("reroute", system_name) for system_name, _ in upper_targets])
            resolution_steps.extend([("reroute", system_name) for system_name, _ in lower_targets if system_name not in {item[1] for item in resolution_steps}])
        else:
            resolution_steps.extend([("reroute", system_name) for system_name, _ in upper_targets])
            resolution_steps.extend([("vertical", system_name) for system_name, _ in lower_targets])
    elif strategy_name == "upper_reroute_first":
        resolution_steps.extend([("reroute", system_name) for system_name, _ in upper_targets])
        resolution_steps.extend([("vertical", system_name) for system_name, _ in lower_targets])
    else:
        resolution_steps.extend([("vertical", system_name) for system_name, _ in lower_targets])
        resolution_steps.extend([("reroute", system_name) for system_name, _ in upper_targets])
        resolution_steps.extend([("vertical", system_name) for system_name, _ in upper_targets if system_name != preferred_lower])
    return resolution_steps


def _gis_layer_payload(project: ProjectModel, layer_names: Sequence[str]) -> Tuple[str, Any]:
    meta = safe_dict(project.meta)
    gis_layers = safe_dict(meta.get("gis_layers"))
    existing = safe_dict(meta.get("existing_conditions"))
    if not gis_layers:
        gis_layers = safe_dict(existing.get("gis_layers")) or safe_dict(existing.get("layers")) or existing
    for layer_name in layer_names:
        value = gis_layers.get(layer_name)
        if value:
            return layer_name, value
    return "", None


def _preferred_corridor_from_gis(project: ProjectModel) -> Dict[str, Any]:
    layer_name, raw_layer = _gis_layer_payload(
        project,
        (
            "utility_corridors",
            "utility_easements",
            "easements",
            "private_easements",
        ),
    )
    if not raw_layer:
        return {}
    candidates: List[Dict[str, Any]] = []
    for index, feature in enumerate(_gis_feature_rows(raw_layer), start=1):
        bbox = _bbox_from_feature(feature)
        if not bbox:
            continue
        width = safe_float(bbox.get("w"), 0.0)
        height = safe_float(bbox.get("h"), 0.0)
        if width <= 0.0 and height <= 0.0:
            continue
        orientation = "horizontal" if width >= height else "vertical"
        axis_value = (
            safe_float(bbox.get("y"), 0.0) + height / 2.0
            if orientation == "horizontal"
            else safe_float(bbox.get("x"), 0.0) + width / 2.0
        )
        centerline = _corridor_centerline_from_feature(feature, bbox, orientation)
        candidates.append(
            {
                "orientation": orientation,
                "axis_value": round(axis_value, 3),
                "width_ft": round(height if orientation == "horizontal" else width, 3),
                "length_ft": round(max(width, height), 3),
                "centerline": centerline,
                "source": "gis_easement",
                "source_layer": layer_name,
                "source_name": _feature_label(feature, f"{layer_name.upper()}-{index}"),
            }
        )
    if not candidates:
        return {}
    return max(candidates, key=lambda item: safe_float(item.get("length_ft"), 0.0))


def _preferred_corridor_from_roads(project: ProjectModel) -> Dict[str, Any]:
    actions = safe_list(safe_dict(project.meta.get("_expanded_plan")).get("actions"))
    candidates: List[Dict[str, Any]] = []
    for index, raw in enumerate(actions, start=1):
        action = safe_dict(raw)
        label = " ".join(
            safe_str(action.get(key))
            for key in ("layer", "label", "kind", "task", "canonical_source_type")
            if safe_str(action.get(key))
        ).lower()
        if not any(token in label for token in ("road", "drive", "corridor", "street")):
            continue
        points = _dedupe_path_points(safe_list(action.get("points") or action.get("path") or action.get("route_points")))
        if len(points) >= 2:
            bbox = {
                "x": min(point[0] for point in points),
                "y": min(point[1] for point in points),
                "w": max(point[0] for point in points) - min(point[0] for point in points),
                "h": max(point[1] for point in points) - min(point[1] for point in points),
            }
            orientation = "horizontal" if safe_float(bbox.get("w"), 0.0) >= safe_float(bbox.get("h"), 0.0) else "vertical"
            axis_value = (
                sum(point[1] for point in points) / len(points)
                if orientation == "horizontal"
                else sum(point[0] for point in points) / len(points)
            )
            candidates.append(
                {
                    "orientation": orientation,
                    "axis_value": round(axis_value, 3),
                    "width_ft": max(12.0, safe_float(action.get("width"), safe_float(action.get("width_ft"), 24.0))),
                    "length_ft": round(polyline_length(points), 3),
                    "centerline": points,
                    "source": "road_corridor",
                    "source_layer": "expanded_plan",
                    "source_name": safe_str(action.get("label"), f"ROAD-{index}"),
                }
            )
            continue
        origin = safe_list(action.get("origin"))
        width = safe_float(action.get("width"), safe_float(action.get("w"), 0.0))
        height = safe_float(action.get("height"), safe_float(action.get("h"), 0.0))
        if len(origin) >= 2 and width > 0.0 and height > 0.0:
            x = safe_float(origin[0], 0.0)
            y = safe_float(origin[1], 0.0)
            orientation = "horizontal" if width >= height else "vertical"
            axis_value = y + height / 2.0 if orientation == "horizontal" else x + width / 2.0
            centerline = (
                [[x, axis_value], [x + width, axis_value]]
                if orientation == "horizontal"
                else [[axis_value, y], [axis_value, y + height]]
            )
            candidates.append(
                {
                    "orientation": orientation,
                    "axis_value": round(axis_value, 3),
                    "width_ft": round(height if orientation == "horizontal" else width, 3),
                    "length_ft": round(max(width, height), 3),
                    "centerline": _dedupe_path_points(centerline),
                    "source": "road_corridor",
                    "source_layer": "expanded_plan",
                    "source_name": safe_str(action.get("label"), f"ROAD-{index}"),
                }
            )
    if not candidates:
        return {}
    return max(candidates, key=lambda item: safe_float(item.get("length_ft"), 0.0))


def _corridor_slots_from_axis(axis: Dict[str, Any], fallback: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    orientation = safe_str(axis.get("orientation"))
    axis_value = safe_float(axis.get("axis_value"), 0.0)
    if orientation not in {"horizontal", "vertical"}:
        return fallback
    width_ft = safe_float(axis.get("width_ft"), 0.0)
    slot = max(4.0, min(10.0, width_ft / 4.0 if width_ft > 0.0 else 6.0))
    source = {
        "orientation": orientation,
        "source": safe_str(axis.get("source"), "derived_corridor"),
        "source_layer": safe_str(axis.get("source_layer")),
        "source_name": safe_str(axis.get("source_name")),
    }
    raw_centerline = _dedupe_path_points(safe_list(axis.get("centerline")))

    def _slot_centerline(slot_axis: float) -> List[List[float]]:
        if len(raw_centerline) < 2:
            return []
        if orientation == "horizontal":
            current = sum(safe_float(pt[1], 0.0) for pt in raw_centerline) / len(raw_centerline)
            delta = slot_axis - current
            return [[round(safe_float(pt[0], 0.0), 3), round(safe_float(pt[1], 0.0) + delta, 3)] for pt in raw_centerline]
        current = sum(safe_float(pt[0], 0.0) for pt in raw_centerline) / len(raw_centerline)
        delta = slot_axis - current
        return [[round(safe_float(pt[0], 0.0) + delta, 3), round(safe_float(pt[1], 0.0), 3)] for pt in raw_centerline]

    storm_axis = round(axis_value - slot, 3)
    sanitary_axis = round(axis_value, 3)
    water_axis = round(axis_value + slot, 3)
    generic_axis = round(axis_value + slot * 1.5, 3)
    return {
        "storm": {**source, "axis_value": storm_axis, "centerline": _slot_centerline(storm_axis), "weight": 1.1, "slot_role": "storm_lower_slot"},
        "sanitary": {**source, "axis_value": sanitary_axis, "centerline": _slot_centerline(sanitary_axis), "weight": 1.15, "slot_role": "sanitary_middle_slot"},
        "water": {**source, "axis_value": water_axis, "centerline": _slot_centerline(water_axis), "weight": 1.0, "slot_role": "water_pressure_slot"},
        "generic": {**source, "axis_value": generic_axis, "centerline": _slot_centerline(generic_axis), "weight": 0.8, "slot_role": "generic_utility_slot"},
    }


def _preferred_corridors(parsed: Dict[str, Any], project: ProjectModel) -> Dict[str, Dict[str, Any]]:
    lot = safe_dict(unwrap_fields_for_execution(parsed.get("lot")))
    x = safe_float(lot.get("x"), DEFAULT_LOT_X)
    y = safe_float(lot.get("y"), DEFAULT_LOT_Y)
    w = safe_float(lot.get("w"), DEFAULT_LOT_WIDTH)
    h = safe_float(lot.get("h"), DEFAULT_LOT_HEIGHT)
    street_edge = lower_text(parsed.get("street_edge") or "bottom")
    setback = max(8.0, safe_float(parsed.get("setback"), DEFAULT_SETBACK))
    road_bias_y = y + 12.0 if street_edge == "bottom" else y + h - 12.0
    road_bias_x = x + 12.0 if street_edge == "left" else x + w - 12.0
    horizontal = street_edge in {"bottom", "top"}
    sanitary_offset = setback * 0.75
    storm_offset = setback * 1.0
    water_offset = setback * 1.35
    source_axis = _preferred_corridor_from_gis(project) or _preferred_corridor_from_roads(project)
    if horizontal:
        fallback = {
            "storm": {"orientation": "horizontal", "axis_value": round(road_bias_y + storm_offset, 3), "weight": 0.8},
            "sanitary": {"orientation": "horizontal", "axis_value": round(road_bias_y + sanitary_offset, 3), "weight": 0.9},
            "water": {"orientation": "horizontal", "axis_value": round(road_bias_y + water_offset, 3), "weight": 0.7},
            "generic": {"orientation": "horizontal", "axis_value": round(road_bias_y + water_offset + 4.0, 3), "weight": 0.5},
        }
        return _corridor_slots_from_axis(source_axis, fallback)
    fallback = {
        "storm": {"orientation": "vertical", "axis_value": round(road_bias_x + storm_offset, 3), "weight": 0.8},
        "sanitary": {"orientation": "vertical", "axis_value": round(road_bias_x + sanitary_offset, 3), "weight": 0.9},
        "water": {"orientation": "vertical", "axis_value": round(road_bias_x + water_offset, 3), "weight": 0.7},
        "generic": {"orientation": "vertical", "axis_value": round(road_bias_x + water_offset + 4.0, 3), "weight": 0.5},
    }
    return _corridor_slots_from_axis(source_axis, fallback)


def _corridor_deviation_cost(path: Sequence[Sequence[float]], preference: Dict[str, Any]) -> float:
    orientation = safe_str(preference.get("orientation"))
    axis = safe_float(preference.get("axis_value"), 0.0)
    weight = max(safe_float(preference.get("weight"), 0.0), 0.0)
    if len(path) < 2 or weight <= 0.0:
        return 0.0
    if orientation == "horizontal":
        deviation = sum(abs(safe_float(pt[1], 0.0) - axis) for pt in path) / len(path)
    else:
        deviation = sum(abs(safe_float(pt[0], 0.0) - axis) for pt in path) / len(path)
    return round(deviation * weight, 3)


def _snap_point_outside_buffered_rect(point: Sequence[float], rect: Dict[str, Any], reference: Optional[Sequence[float]] = None) -> List[float]:
    x = safe_float(point[0], 0.0)
    y = safe_float(point[1], 0.0)
    pad = safe_float(rect.get("buffer_ft"), 0.0)
    x0 = safe_float(rect.get("x"), 0.0) - pad
    y0 = safe_float(rect.get("y"), 0.0) - pad
    x1 = safe_float(rect.get("x"), 0.0) + safe_float(rect.get("w"), 0.0) + pad
    y1 = safe_float(rect.get("y"), 0.0) + safe_float(rect.get("h"), 0.0) + pad
    offset = 0.25
    candidates = [
        [x0 - offset, min(max(y, y0), y1)],
        [x1 + offset, min(max(y, y0), y1)],
        [min(max(x, x0), x1), y0 - offset],
        [min(max(x, x0), x1), y1 + offset],
    ]
    if reference is None or len(reference) < 2:
        return min(candidates, key=lambda row: ((row[0] - x) ** 2 + (row[1] - y) ** 2) ** 0.5)
    ref_x = safe_float(reference[0], 0.0)
    ref_y = safe_float(reference[1], 0.0)
    return min(candidates, key=lambda row: ((row[0] - ref_x) ** 2 + (row[1] - ref_y) ** 2) ** 0.5)


def _segment_average_invert(segment: Dict[str, Any]) -> float:
    start = safe_float(segment.get("start_invert_ft", segment.get("start_invert")), DEFAULT_PAD_ELEV - 4.0)
    end = safe_float(segment.get("end_invert_ft", segment.get("end_invert")), DEFAULT_PAD_ELEV - 4.0)
    return (start + end) / 2.0


def _path_heading_deg(path: Sequence[Sequence[float]]) -> float:
    points = _dedupe_path_points(path)
    if len(points) < 2:
        return 0.0
    dx = safe_float(points[-1][0], 0.0) - safe_float(points[0][0], 0.0)
    dy = safe_float(points[-1][1], 0.0) - safe_float(points[0][1], 0.0)
    return math.degrees(math.atan2(dy, dx))


def _crossing_angle_deg(path_a: Sequence[Sequence[float]], path_b: Sequence[Sequence[float]]) -> float:
    heading_a = _path_heading_deg(path_a)
    heading_b = _path_heading_deg(path_b)
    diff = abs(heading_a - heading_b) % 180.0
    return round(min(diff, 180.0 - diff), 3)


def _conflict_station(segment: Dict[str, Any]) -> float:
    return _path_station_at_midpoint(safe_list(segment.get("path")))


def _path_protected_zone_penalty(path: Sequence[Sequence[float]], protected_zones: Sequence[Dict[str, Any]]) -> float:
    total = 0.0
    for zone in protected_zones:
        if _path_hits_buffered_rect(path, zone):
            total += safe_float(zone.get("penalty"), 0.0)
    return round(total, 3)


def _path_protected_zone_hits(
    path: Sequence[Sequence[float]],
    protected_zones: Sequence[Dict[str, Any]],
    *,
    ignored_names: Sequence[str] = (),
) -> List[Dict[str, Any]]:
    ignored = {safe_str(name) for name in ignored_names if safe_str(name)}
    hits: List[Dict[str, Any]] = []
    for zone in protected_zones:
        rec = safe_dict(zone)
        if safe_str(rec.get("name")) in ignored:
            continue
        if not _path_hits_buffered_rect(path, rec):
            continue
        hits.append(
            {
                "kind": safe_str(rec.get("kind")),
                "name": safe_str(rec.get("name")),
                "penalty": round(safe_float(rec.get("penalty"), 0.0), 3),
                "avoid": bool(rec.get("avoid")),
            }
        )
    return hits


def _grading_repair_penalty(note: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    rec = safe_dict(note)
    if not rec:
        return {"score": 0.0, "blocked": False}
    disturbance = safe_str(rec.get("disturbance_class"), "standard")
    delta_depth = abs(safe_float(rec.get("delta_depth_ft"), 0.0))
    cut_fill = abs(safe_float(rec.get("cut_fill_delta_cf"), 0.0))
    repair_modes = {safe_str(item) for item in safe_list(rec.get("repair_modes")) if safe_str(item)}
    score = cut_fill * 0.04 + delta_depth * 14.0
    if disturbance == "moderate":
        score += 25.0
    elif disturbance == "high":
        score += 70.0
    if "road_edge_transition" in repair_modes or "pavement_transition" in repair_modes:
        score += 18.0
    if "pad_tie_in" in repair_modes:
        score += 12.0
    if "ada_path_repair" in repair_modes:
        score += 35.0
    if "retaining_sensitive_transition" in repair_modes:
        score += 45.0
    if "protected_zone_grading_avoidance" in repair_modes:
        score += 55.0
    blocked = (
        ("ada_path_repair" in repair_modes and delta_depth > 1.5)
        or ("road_edge_transition" in repair_modes and delta_depth > 1.25)
        or ("pavement_transition" in repair_modes and cut_fill > 140.0)
        or ("pad_tie_in" in repair_modes and delta_depth > 1.1)
        or ("retaining_sensitive_transition" in repair_modes and delta_depth > 1.0)
        or ("protected_zone_grading_avoidance" in repair_modes and delta_depth > 0.75)
        or (disturbance == "high" and cut_fill > 180.0)
    )
    return {
        "score": round(score, 3),
        "blocked": blocked,
        "disturbance_class": disturbance,
        "repair_modes": sorted(repair_modes),
    }


def _candidate_constructability_score(
    before_path: Sequence[Sequence[float]],
    after_path: Sequence[Sequence[float]],
    *,
    protected_penalty: float,
    added_structures: int,
    ownership_class: str,
    grading_penalty: float = 0.0,
) -> Dict[str, Any]:
    before_len = polyline_length(before_path)
    after_len = polyline_length(after_path)
    added_length = max(after_len - before_len, 0.0)
    bend_count = _path_turn_count(after_path)
    score = (
        protected_penalty * 2.5
        + added_length * 0.35
        + bend_count * 12.0
        + added_structures * 18.0
        + grading_penalty
        + max(0, SYSTEM_OWNERSHIP_PRIORITY.get(ownership_class, 7) - 3) * 6.0
    )
    return {
        "score": round(score, 3),
        "added_length_ft": round(added_length, 3),
        "bend_complexity": bend_count,
        "added_structures": added_structures,
        "protected_zone_penalty": round(protected_penalty, 3),
        "grading_penalty": round(grading_penalty, 3),
    }


def _preferred_corridor_for_segment(project: ProjectModel, segment: Dict[str, Any]) -> Dict[str, Any]:
    corridors = safe_dict(project.meta.get("preferred_corridors"))
    system = safe_str(segment.get("system") or segment.get("system_type"))
    ownership = _segment_ownership_class(segment)
    if ownership == "utility_service":
        return deepcopy(safe_dict(corridors.get("generic", {})))
    return deepcopy(safe_dict(corridors.get(system) or corridors.get("generic", {})))


def _nearest_point_on_corridor(path: Sequence[Sequence[float]], point: Sequence[float]) -> Tuple[List[float], float, int]:
    px = safe_float(point[0], 0.0)
    py = safe_float(point[1], 0.0)
    best_point = [px, py]
    best_station = 0.0
    best_index = 0
    best_dist = float("inf")
    station = 0.0
    for index in range(1, len(path)):
        ax = safe_float(path[index - 1][0], 0.0)
        ay = safe_float(path[index - 1][1], 0.0)
        bx = safe_float(path[index][0], 0.0)
        by = safe_float(path[index][1], 0.0)
        dx = bx - ax
        dy = by - ay
        seg_len_sq = dx * dx + dy * dy
        seg_len = math.sqrt(seg_len_sq) if seg_len_sq > 0.0 else 0.0
        t = 0.0 if seg_len_sq <= 0.0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
        qx = ax + t * dx
        qy = ay + t * dy
        dist = math.hypot(px - qx, py - qy)
        if dist < best_dist:
            best_dist = dist
            best_point = [round(qx, 3), round(qy, 3)]
            best_station = station + t * seg_len
            best_index = index - 1
        station += seg_len
    return best_point, best_station, best_index


def _preferred_route_along_centerline(start: Sequence[float], end: Sequence[float], centerline: Sequence[Sequence[float]]) -> List[List[float]]:
    line = _dedupe_path_points(centerline)
    if len(line) < 2:
        return []
    start_projection, start_station, start_index = _nearest_point_on_corridor(line, start)
    end_projection, end_station, end_index = _nearest_point_on_corridor(line, end)
    if start_station <= end_station:
        corridor_part = [start_projection]
        corridor_part.extend(line[start_index + 1 : end_index + 1])
        corridor_part.append(end_projection)
    else:
        corridor_part = [start_projection]
        corridor_part.extend(reversed(line[end_index + 1 : start_index + 1]))
        corridor_part.append(end_projection)
    return _dedupe_path_points([[safe_float(start[0], 0.0), safe_float(start[1], 0.0)], *corridor_part, [safe_float(end[0], 0.0), safe_float(end[1], 0.0)]])


def _preferred_route_between(start: Sequence[float], end: Sequence[float], preference: Dict[str, Any]) -> List[List[float]]:
    sx = safe_float(start[0], 0.0)
    sy = safe_float(start[1], 0.0)
    ex = safe_float(end[0], 0.0)
    ey = safe_float(end[1], 0.0)
    orientation = safe_str(preference.get("orientation"))
    axis = safe_float(preference.get("axis_value"), 0.0)
    centerline_route = _preferred_route_along_centerline(start, end, safe_list(preference.get("centerline")))
    if centerline_route:
        return centerline_route
    if orientation == "horizontal":
        return _dedupe_path_points([[sx, sy], [sx, axis], [ex, axis], [ex, ey]])
    if orientation == "vertical":
        return _dedupe_path_points([[sx, sy], [axis, sy], [axis, ey], [ex, ey]])
    return _dedupe_path_points([[sx, sy], [ex, ey]])


def _hard_protected_zone_names_hit(path: Sequence[Sequence[float]], project: ProjectModel) -> List[str]:
    hits = _path_protected_zone_hits(path, _expanded_obstacle_rectangles(project))
    return dedupe_keep_order(
        safe_str(hit.get("name"))
        for hit in hits
        if bool(hit.get("avoid")) and safe_str(hit.get("kind")) in HARD_PROTECTED_ZONE_KINDS and safe_str(hit.get("name"))
    )


def _maybe_prefer_corridor_route(project: ProjectModel, segment: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    rec = deepcopy(safe_dict(segment))
    path = _dedupe_path_points(safe_list(rec.get("route_points") or rec.get("path")))
    if len(path) < 2:
        return rec, {}
    role = safe_str(rec.get("segment_role") or rec.get("role")).lower()
    if role and role not in {"main", "trunk", "collector", "transmission", "loop", "primary"}:
        return rec, {}
    preference = _preferred_corridor_for_segment(project, rec)
    if not preference:
        return rec, {}
    source = safe_str(preference.get("source"))
    if source not in {"gis_easement", "road_corridor"} and not safe_list(preference.get("centerline")):
        return rec, {}
    candidate = _preferred_route_between(path[0], path[-1], preference)
    if len(candidate) < 2:
        return rec, {}
    before_dev = _corridor_deviation_cost(path, preference)
    after_dev = _corridor_deviation_cost(candidate, preference)
    before_len = polyline_length(path)
    after_len = polyline_length(candidate)
    hard_hits = _hard_protected_zone_names_hit(candidate, project)
    if hard_hits or after_dev >= before_dev or after_len > max(before_len * 3.0, before_len + 350.0):
        rec["corridor_routing_audit"] = {
            "applied": False,
            "reason": "candidate_blocked_or_not_better",
            "preferred_source": source or safe_str(preference.get("source_layer")),
            "before_deviation_ft": round(before_dev, 3),
            "after_deviation_ft": round(after_dev, 3),
            "candidate_length_ft": round(after_len, 3),
            "hard_protected_zone_hits": hard_hits,
        }
        return rec, rec["corridor_routing_audit"]
    rec["route_points"] = candidate
    if "path" in rec:
        rec["path"] = candidate
    rec["corridor_routing_audit"] = {
        "applied": True,
        "reason": "preferred_corridor_reduced_deviation",
        "preferred_source": source or safe_str(preference.get("source_layer")),
        "preferred_source_name": safe_str(preference.get("source_name")),
        "slot_role": safe_str(preference.get("slot_role")),
        "before_deviation_ft": round(before_dev, 3),
        "after_deviation_ft": round(after_dev, 3),
        "before_length_ft": round(before_len, 3),
        "after_length_ft": round(after_len, 3),
    }
    return rec, rec["corridor_routing_audit"]


def _station_point_on_path(path: Sequence[Sequence[float]], station_ft: float) -> List[float]:
    points = _dedupe_path_points(path)
    if not points:
        return [0.0, 0.0]
    remaining = max(0.0, safe_float(station_ft, 0.0))
    for index in range(1, len(points)):
        start = points[index - 1]
        end = points[index]
        seg_len = math.hypot(end[0] - start[0], end[1] - start[1])
        if remaining <= seg_len or index == len(points) - 1:
            ratio = 0.0 if seg_len <= 0.0 else min(max(remaining / seg_len, 0.0), 1.0)
            return [round(start[0] + (end[0] - start[0]) * ratio, 3), round(start[1] + (end[1] - start[1]) * ratio, 3)]
        remaining -= seg_len
    return [round(points[-1][0], 3), round(points[-1][1], 3)]


def _insert_points_into_path(path: Sequence[Sequence[float]], insert_points: Sequence[Sequence[float]]) -> List[List[float]]:
    points = _dedupe_path_points(path)
    if len(points) < 2 or not insert_points:
        return points
    inserts = {_point_key(point): [round(safe_float(point[0], 0.0), 3), round(safe_float(point[1], 0.0), 3)] for point in insert_points if isinstance(point, (list, tuple)) and len(point) >= 2}
    rows: List[Tuple[float, List[float]]] = []
    station = 0.0
    rows.append((0.0, points[0]))
    for index in range(1, len(points)):
        start = points[index - 1]
        end = points[index]
        seg_len = math.hypot(end[0] - start[0], end[1] - start[1])
        for insert in inserts.values():
            if _point_key(insert) in {_point_key(start), _point_key(end)}:
                continue
            seg_len_sq = seg_len * seg_len
            if seg_len_sq <= 0.0:
                continue
            t = ((insert[0] - start[0]) * (end[0] - start[0]) + (insert[1] - start[1]) * (end[1] - start[1])) / seg_len_sq
            if 1e-6 < t < 1.0 - 1e-6:
                projected = [round(start[0] + (end[0] - start[0]) * t, 3), round(start[1] + (end[1] - start[1]) * t, 3)]
                if math.hypot(projected[0] - insert[0], projected[1] - insert[1]) <= 0.05:
                    rows.append((station + seg_len * t, insert))
        station += seg_len
        rows.append((station, end))
    return _dedupe_path_points([point for _, point in sorted(rows, key=lambda row: row[0])])


def _support_structure_points_for_path(path: Sequence[Sequence[float]], max_spacing_ft: float) -> List[List[float]]:
    points = _dedupe_path_points(path)
    if len(points) < 2:
        return []
    total = polyline_length(points)
    spacing = max(1.0, safe_float(max_spacing_ft, 1.0))
    stations = {0.0, round(total, 3)}
    count = max(0, int(math.floor(total / spacing)))
    for index in range(1, count + 1):
        station = min(index * spacing, total)
        if 1.0 < station < total - 1.0:
            stations.add(round(station, 3))
    for index in range(1, len(points) - 1):
        if _path_turn_count(points[index - 1 : index + 2]) > 0:
            stations.add(round(polyline_length(points[: index + 1]), 3))
    return _dedupe_path_points([_station_point_on_path(points, station) for station in sorted(stations)])


def _reroute_candidates_around_rect(path: List[List[float]], rect: Dict[str, Any], preference: Optional[Dict[str, Any]] = None) -> List[List[List[float]]]:
    if len(path) < 2:
        return [path]
    start = path[0]
    end = path[-1]
    pad = safe_float(rect.get("buffer_ft"), 0.0) + 4.0
    x0 = safe_float(rect.get("x"), 0.0) - pad
    y0 = safe_float(rect.get("y"), 0.0) - pad
    x1 = safe_float(rect.get("x"), 0.0) + safe_float(rect.get("w"), 0.0) + pad
    y1 = safe_float(rect.get("y"), 0.0) + safe_float(rect.get("h"), 0.0) + pad
    candidates: List[List[List[float]]] = []
    for detour_y in (y0, y1):
        candidates.append([[start[0], start[1]], [start[0], detour_y], [end[0], detour_y], [end[0], end[1]]])
    for detour_x in (x0, x1):
        candidates.append([[start[0], start[1]], [detour_x, start[1]], [detour_x, end[1]], [end[0], end[1]]])
    if isinstance(preference, dict) and preference:
        preferred = _preferred_route_between(start, end, preference)
        if preferred and len(preferred) >= 2:
            candidates.append(preferred)
            orientation = safe_str(preference.get("orientation"))
            axis = safe_float(preference.get("axis_value"), 0.0)
            if orientation == "horizontal":
                candidates.append([[start[0], start[1]], [start[0], axis], [x0, axis], [x0, end[1]], [end[0], end[1]]])
                candidates.append([[start[0], start[1]], [start[0], axis], [x1, axis], [x1, end[1]], [end[0], end[1]]])
            elif orientation == "vertical":
                candidates.append([[start[0], start[1]], [axis, start[1]], [axis, y0], [end[0], y0], [end[0], end[1]]])
                candidates.append([[start[0], start[1]], [axis, start[1]], [axis, y1], [end[0], y1], [end[0], end[1]]])
    normalized: List[List[List[float]]] = []
    seen: set[Tuple[Tuple[float, float], ...]] = set()
    for candidate in candidates:
        deduped = _dedupe_path_points(candidate)
        key = tuple((round(pt[0], 3), round(pt[1], 3)) for pt in deduped)
        if len(deduped) >= 2 and key not in seen:
            seen.add(key)
            normalized.append(deduped)
    valid = [candidate for candidate in normalized if not _path_hits_buffered_rect(candidate, rect)]
    return valid or normalized or [path]


def _geometry_candidate_paths(
    path: List[List[float]],
    rect: Dict[str, Any],
    preference: Optional[Dict[str, Any]],
    *,
    candidate_mode: str,
    cluster_context: Optional[Dict[str, Any]] = None,
    protected_zones: Sequence[Dict[str, Any]] = (),
) -> List[Dict[str, Any]]:
    if len(path) < 2:
        return [{"strategy": "unchanged", "source_mode": "degenerate", "path": deepcopy(path)}]
    adjusted_path = _dedupe_path_points(path)
    if adjusted_path and _point_inside_buffered_rect(adjusted_path[0], rect):
        adjusted_path[0] = _snap_point_outside_buffered_rect(adjusted_path[0], rect, adjusted_path[1] if len(adjusted_path) > 1 else None)
    if adjusted_path and _point_inside_buffered_rect(adjusted_path[-1], rect):
        adjusted_path[-1] = _snap_point_outside_buffered_rect(adjusted_path[-1], rect, adjusted_path[-2] if len(adjusted_path) > 1 else None)

    raw_candidates: List[Dict[str, Any]] = []
    if not _path_hits_buffered_rect(adjusted_path, rect):
        raw_candidates.append({"strategy": "terminal_shift", "source_mode": "endpoint_snap", "path": adjusted_path})

    for candidate in _reroute_candidates_around_rect(adjusted_path, rect, None):
        raw_candidates.append({"strategy": "reroute_around_obstacle", "source_mode": "naive_detour", "path": candidate})

    if isinstance(preference, dict) and preference:
        for candidate in _reroute_candidates_around_rect(adjusted_path, rect, preference):
            raw_candidates.append({"strategy": "corridor_guided_reroute", "source_mode": "preferred_corridor", "path": candidate})

    cluster = safe_dict(cluster_context)
    orientation = safe_str(cluster.get("corridor_axis"))
    axis = safe_float(cluster.get("axis_value"), 0.0)
    if orientation in {"horizontal", "vertical"} and axis:
        start = adjusted_path[0]
        end = adjusted_path[-1]
        pad = safe_float(rect.get("buffer_ft"), 0.0) + 4.0
        x0 = safe_float(rect.get("x"), 0.0) - pad
        y0 = safe_float(rect.get("y"), 0.0) - pad
        x1 = safe_float(rect.get("x"), 0.0) + safe_float(rect.get("w"), 0.0) + pad
        y1 = safe_float(rect.get("y"), 0.0) + safe_float(rect.get("h"), 0.0) + pad
        if orientation == "horizontal":
            raw_candidates.append({"strategy": "trench_cluster_reroute", "source_mode": "cluster_corridor", "path": _dedupe_path_points([[start[0], start[1]], [start[0], axis], [x0, axis], [x0, end[1]], [end[0], end[1]]])})
            raw_candidates.append({"strategy": "trench_cluster_reroute", "source_mode": "cluster_corridor", "path": _dedupe_path_points([[start[0], start[1]], [start[0], axis], [x1, axis], [x1, end[1]], [end[0], end[1]]])})
        else:
            raw_candidates.append({"strategy": "trench_cluster_reroute", "source_mode": "cluster_corridor", "path": _dedupe_path_points([[start[0], start[1]], [axis, start[1]], [axis, y0], [end[0], y0], [end[0], end[1]]])})
            raw_candidates.append({"strategy": "trench_cluster_reroute", "source_mode": "cluster_corridor", "path": _dedupe_path_points([[start[0], start[1]], [axis, start[1]], [axis, y1], [end[0], y1], [end[0], end[1]]])})

    normalized: List[Dict[str, Any]] = []
    seen: set[Tuple[Tuple[float, float], ...]] = set()
    for row in raw_candidates:
        candidate = _dedupe_path_points(safe_list(row.get("path")))
        key = tuple((round(pt[0], 3), round(pt[1], 3)) for pt in candidate)
        if len(candidate) < 2 or key in seen:
            continue
        seen.add(key)
        corridor_penalty = _corridor_deviation_cost(candidate, preference or {})
        protected_penalty = _path_protected_zone_penalty(candidate, protected_zones)
        protected_hits = _path_protected_zone_hits(candidate, protected_zones, ignored_names=[safe_str(rect.get("name"))])
        added_length = max(polyline_length(candidate) - polyline_length(path), 0.0)
        bend_count = _path_turn_count(candidate)
        normalized.append(
            {
                **row,
                "path": candidate,
                "corridor_penalty": corridor_penalty,
                "protected_penalty": protected_penalty,
                "protected_hits": protected_hits,
                "added_length_ft": round(added_length, 3),
                "bend_count": bend_count,
            }
        )

    def _sort_key(row: Dict[str, Any]) -> Tuple[float, float, float, float, str]:
        protected_penalty = safe_float(row.get("protected_penalty"), 0.0)
        corridor_penalty = safe_float(row.get("corridor_penalty"), 0.0)
        added_length = safe_float(row.get("added_length_ft"), 0.0)
        bend_count = float(safe_int(row.get("bend_count"), 0))
        source_mode = safe_str(row.get("source_mode"))
        if candidate_mode == "protected_zone_bias":
            return (protected_penalty, corridor_penalty, bend_count, added_length, source_mode)
        if candidate_mode == "corridor_bias":
            return (corridor_penalty, protected_penalty, added_length, bend_count, source_mode)
        if candidate_mode == "trench_cluster":
            return (protected_penalty * 2.0 + corridor_penalty * 1.5, added_length, bend_count, corridor_penalty, source_mode)
        return (protected_penalty, corridor_penalty, added_length, bend_count, source_mode)

    return sorted(normalized, key=_sort_key)


def _support_structure_spacing_ft(system_name: str) -> float:
    return {
        "storm": 220.0,
        "sanitary": 260.0,
        "water": 280.0,
        "utilities": 280.0,
    }.get(system_name, 260.0)


def _cluster_preferred_corridor(cluster: Dict[str, Any], project: ProjectModel, system_name: str) -> Dict[str, Any]:
    corridor = {
        "orientation": safe_str(cluster.get("corridor_axis")),
        "axis_value": safe_float(cluster.get("axis_value"), 0.0),
        "weight": 1.1 if bool(cluster.get("trench_like")) else 0.8,
    }
    if safe_str(corridor.get("orientation")) in {"horizontal", "vertical"} and safe_float(corridor.get("axis_value"), 0.0):
        return corridor
    return _preferred_corridor_for_segment(project, {"system": system_name})


def _crossing_hierarchy_evaluation(
    conflict: Dict[str, Any],
    target_system: str,
    strategy: str,
    *,
    target_ownership_class: str = "generic",
    crossing_strategy: str = "",
) -> Dict[str, Any]:
    interaction_type = safe_str(conflict.get("interaction_type"), "crossing")
    preferred_lower = safe_str(conflict.get("preferred_lower_system"))
    actual_angle = safe_float(conflict.get("crossing_angle_deg"), 0.0)
    preferred_angle = safe_float(conflict.get("preferred_crossing_angle_deg"), 0.0)
    compliant = True
    blocked = False
    penalty = 0.0
    rule = "crossing_hierarchy"
    reason = ""

    if safe_str(conflict.get("conflict_type")).endswith("_clearance") and preferred_lower:
        if interaction_type == "crossing":
            if strategy == "vertical_adjustment":
                compliant = safe_str(target_system) == preferred_lower
                if not compliant:
                    penalty += 260.0
                    blocked = True
                    reason = f"{target_system} should not be lowered beneath {preferred_lower} at a crossing."
            else:
                compliant = safe_str(target_system) != preferred_lower
                if not compliant:
                    penalty += 140.0
                    reason = f"{preferred_lower} should stay in the lower crossing hierarchy while the upper system reroutes."
                else:
                    if SYSTEM_OWNERSHIP_PRIORITY.get(target_ownership_class, 99) <= SYSTEM_OWNERSHIP_PRIORITY.get("water_main", 3):
                        penalty += 40.0
                        reason = reason or f"Rerouting {target_ownership_class} is allowed but less preferred than moving a lower-priority branch."
                    if safe_str(crossing_strategy) == "upper_reroute_first":
                        penalty = max(penalty - 25.0, 0.0)
                    elif safe_str(crossing_strategy) == "hierarchy_first":
                        penalty += 10.0 if SYSTEM_OWNERSHIP_PRIORITY.get(target_ownership_class, 99) <= 3 else 0.0
            if preferred_angle > 0.0 and actual_angle > 0.0 and actual_angle + 5.0 < preferred_angle:
                penalty += (preferred_angle - actual_angle) * 2.0
                compliant = False
                reason = reason or "Crossing angle does not satisfy preferred hierarchy angle."
        else:
            if strategy == "vertical_adjustment":
                compliant = False
                penalty += 220.0
                blocked = True
                reason = "Parallel utility conflicts should prefer corridor rerouting over vertical stack adjustments."
            else:
                compliant = True
                if safe_str(target_system) == preferred_lower:
                    penalty += 60.0
                    reason = f"Parallel reroute should prefer keeping {preferred_lower} in the lower hierarchy corridor."
                if safe_str(crossing_strategy) == "parallel_shift_first" and safe_str(target_system) != preferred_lower:
                    penalty = max(penalty - 20.0, 0.0)

    return {
        "rule": rule,
        "interaction_type": interaction_type,
        "preferred_lower_system": preferred_lower,
        "actual_crossing_angle_deg": round(actual_angle, 3),
        "preferred_crossing_angle_deg": round(preferred_angle, 3),
        "compliant": compliant,
        "blocked": blocked,
        "penalty": round(penalty, 3),
        "reason": reason,
    }


def _group_crossing_strategy_options(group: Dict[str, Any]) -> List[Dict[str, Any]]:
    conflicts = [safe_dict(item) for item in safe_list(safe_dict(group).get("conflicts")) if safe_dict(item)]
    has_clearance = any(safe_str(item.get("conflict_type")).endswith("_clearance") for item in conflicts)
    has_parallel = any(safe_str(item.get("interaction_type")) == "parallel" for item in conflicts)
    if not has_clearance:
        return [{"name": "default_crossing", "description": "No clearance crossing strategy needed."}]
    options: List[Dict[str, Any]] = [
        {"name": "hierarchy_first", "description": "Preserve hierarchy-first lowering and keep lower system in place where possible."},
        {"name": "upper_reroute_first", "description": "Prefer rerouting the upper or lower-priority crossing system around the conflict group."},
    ]
    if has_parallel:
        options.append({"name": "parallel_shift_first", "description": "Prefer corridor shifts for parallel clearance groups before local stack changes."})
    return options[:3]


def _new_coordination_metrics() -> Dict[str, Any]:
    return _new_coordination_metrics_impl()


def _coordination_metric_inc(metrics: Optional[Dict[str, Any]], path: Sequence[str], amount: float = 1.0) -> None:
    _coordination_metric_inc_impl(metrics, path, amount)


def _coordination_record_prune(metrics: Optional[Dict[str, Any]], reason: str, amount: int = 1) -> None:
    _coordination_record_prune_impl(metrics, reason, amount)


def _path_signature(path: Sequence[Sequence[float]], *, coarse_ft: float = 0.5) -> Tuple[Tuple[float, float], ...]:
    scale = max(coarse_ft, 0.1)
    return tuple((round(safe_float(pt[0], 0.0) / scale), round(safe_float(pt[1], 0.0) / scale)) for pt in safe_list(path))


def _analyze_structure_insertion_needs(path: Sequence[Sequence[float]], spacing_limit: float) -> Dict[str, Any]:
    inserted_points: List[List[float]] = []
    bend_points: List[List[float]] = []
    spacing_points: List[List[float]] = []
    points = _dedupe_path_points(path)
    if len(points) < 2:
        return {"points": inserted_points, "bend_points": bend_points, "spacing_points": spacing_points}
    for idx in range(1, len(points) - 1):
        ax = points[idx][0] - points[idx - 1][0]
        ay = points[idx][1] - points[idx - 1][1]
        bx = points[idx + 1][0] - points[idx][0]
        by = points[idx + 1][1] - points[idx][1]
        if abs(ax * by - ay * bx) > 1e-6:
            bend_point = [round(points[idx][0], 3), round(points[idx][1], 3)]
            bend_points.append(bend_point)
            inserted_points.append(bend_point)
    cumulative = 0.0
    for idx in range(1, len(points)):
        seg_length = ((points[idx][0] - points[idx - 1][0]) ** 2 + (points[idx][1] - points[idx - 1][1]) ** 2) ** 0.5
        cumulative += seg_length
        if cumulative > spacing_limit:
            midpoint = _segment_midpoint([points[idx - 1], points[idx]])
            spacing_points.append(midpoint)
            inserted_points.append(midpoint)
            cumulative = seg_length / 2.0
    return {"points": inserted_points, "bend_points": bend_points, "spacing_points": spacing_points}


def _apply_structure_insertion_rules(
    project: ProjectModel,
    manager: ProjectManager,
    system_name: str,
    segment_name: str,
    path: Sequence[Sequence[float]],
    *,
    metrics: Optional[Dict[str, Any]] = None,
    analysis_cache: Optional[Dict[Tuple[str, str, Tuple[Tuple[float, float], ...]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    added = 0
    inserted_points: List[List[float]] = []
    _coordination_metric_inc(metrics, ["structure_insertion", "rule_calls"])
    points = _dedupe_path_points(path)
    if len(points) < 2:
        return {"added_count": 0, "points": inserted_points, "cache_hit": False}
    spacing_limit = _support_structure_spacing_ft(system_name)
    cache_key = (safe_str(system_name), safe_str(segment_name), _path_signature(points, coarse_ft=0.25))
    analysis: Dict[str, Any]
    cache_hit = False
    if isinstance(analysis_cache, dict) and cache_key in analysis_cache:
        analysis = deepcopy(safe_dict(analysis_cache.get(cache_key)))
        cache_hit = True
        _coordination_metric_inc(metrics, ["structure_insertion", "analysis_cache_hits"])
    else:
        analysis = _analyze_structure_insertion_needs(points, spacing_limit)
        if isinstance(analysis_cache, dict):
            analysis_cache[cache_key] = deepcopy(analysis)
        _coordination_metric_inc(metrics, ["structure_insertion", "analysis_cache_misses"])
    planned_points = [safe_list(item) for item in safe_list(analysis.get("points")) if len(safe_list(item)) >= 2]
    if not planned_points:
        return {"added_count": 0, "points": inserted_points, "cache_hit": cache_hit}
    _coordination_metric_inc(metrics, ["structure_insertion", "attempt_points"], len(planned_points))
    for point in safe_list(analysis.get("bend_points")):
        added += _insert_support_structure(project, manager, system_name, segment_name, point, reason="bend_split")
        inserted_points.append([round(safe_float(point[0], 0.0), 3), round(safe_float(point[1], 0.0), 3)])
    for point in safe_list(analysis.get("spacing_points")):
        midpoint = [safe_float(point[0], 0.0), safe_float(point[1], 0.0)]
        added += _insert_support_structure(project, manager, system_name, segment_name, midpoint, reason="spacing_split")
        inserted_points.append(midpoint)
    _coordination_metric_inc(metrics, ["structure_insertion", "successful_insertions"], added)
    return {"added_count": added, "points": inserted_points, "cache_hit": cache_hit}


def _prune_geometry_candidate_rows(
    candidate_rows: Sequence[Dict[str, Any]],
    base_path: Sequence[Sequence[float]],
    *,
    metrics: Optional[Dict[str, Any]] = None,
    breadth_cap: int = 4,
    preserve_first_hard_avoid: bool = False,
) -> List[Dict[str, Any]]:
    rows = [safe_dict(item) for item in candidate_rows if safe_dict(item)]
    _coordination_metric_inc(metrics, ["candidate_counts", "geometry_candidates_generated"], len(rows))
    if not rows:
        return []
    base_length = max(polyline_length(base_path), 1e-9)
    base_bends = _path_turn_count(base_path)
    kept: List[Dict[str, Any]] = []
    seen: set[Tuple[Tuple[float, float], ...]] = set()
    preserved_hard_avoid = False
    for row in rows:
        path = safe_list(row.get("path"))
        if len(path) < 2:
            _coordination_record_prune(metrics, "degenerate_path")
            continue
        signature = _path_signature(path, coarse_ft=4.0)
        if signature in seen:
            _coordination_record_prune(metrics, "near_equivalent_duplicate")
            continue
        seen.add(signature)
        added_length = safe_float(row.get("added_length_ft"), max(polyline_length(path) - base_length, 0.0))
        bend_count = safe_int(row.get("bend_count"), _path_turn_count(path))
        hard_hits = [
            safe_dict(hit)
            for hit in safe_list(row.get("protected_hits"))
            if bool(safe_dict(hit).get("avoid")) and safe_str(safe_dict(hit).get("kind")) in HARD_PROTECTED_ZONE_KINDS
        ]
        if hard_hits:
            if preserve_first_hard_avoid and not preserved_hard_avoid:
                preserved_hard_avoid = True
                row["_quick_score"] = 1_000_000.0 + safe_float(row.get("protected_penalty"), 0.0)
                kept.append(row)
                continue
            _coordination_record_prune(metrics, "protected_hard_avoid")
            continue
        if polyline_length(path) <= base_length + 0.5 and bend_count <= base_bends and safe_str(row.get("strategy")) != "terminal_shift":
            _coordination_record_prune(metrics, "no_material_change")
            continue
        if added_length > max(35.0, base_length * 1.6):
            _coordination_record_prune(metrics, "excess_added_length")
            continue
        if bend_count > max(base_bends + 4, 6):
            _coordination_record_prune(metrics, "excess_bend_complexity")
            continue
        row["_quick_score"] = round(
            safe_float(row.get("protected_penalty"), 0.0) * 4.0
            + safe_float(row.get("corridor_penalty"), 0.0) * 2.0
            + added_length
            + bend_count * 8.0,
            3,
        )
        kept.append(row)
    kept.sort(
        key=lambda row: (
            safe_float(row.get("_quick_score"), 0.0),
            safe_float(row.get("protected_penalty"), 0.0),
            safe_float(row.get("corridor_penalty"), 0.0),
            safe_float(row.get("added_length_ft"), 0.0),
            safe_int(row.get("bend_count"), 0),
        )
    )
    if len(kept) > breadth_cap:
        _coordination_record_prune(metrics, "breadth_cap", len(kept) - breadth_cap)
    final_rows = kept[:breadth_cap]
    _coordination_metric_inc(metrics, ["candidate_counts", "geometry_candidates_evaluated"], len(final_rows))
    return final_rows


def _resolution_engineering_deltas(before_snapshot: Dict[str, Any], project: ProjectModel, manager: ProjectManager, changed_systems: Sequence[str], *, pre_conflicts: Sequence[Dict[str, Any]], post_conflicts: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    def _length_total(segments: Sequence[Dict[str, Any]], path_key: str) -> float:
        total = 0.0
        for row in segments:
            rec = safe_dict(row)
            if path_key == "route_points":
                path = safe_list(rec.get("route_points"))
            else:
                path = safe_list(rec.get("path") or rec.get("route_points"))
            total += polyline_length(path)
        return round(total, 3)

    def _avg_depth(summary: Dict[str, Any], start_key: str, end_key: str) -> float:
        segments = [safe_dict(item) for item in safe_list(summary.get("segments"))]
        if not segments:
            return 0.0
        values = []
        for rec in segments:
            values.append((safe_float(rec.get(start_key), 0.0) + safe_float(rec.get(end_key), 0.0)) / 2.0)
        return round(sum(values) / max(len(values), 1), 3)

    before_storm = safe_dict(before_snapshot.get("storm"))
    before_sanitary = safe_dict(before_snapshot.get("sanitary"))
    before_utilities = safe_dict(before_snapshot.get("utilities"))
    before_drainage = safe_dict(before_snapshot.get("drainage"))
    after_storm = safe_dict(manager.latest_outputs.get("storm_pipe_summary", project.meta.get("storm_pipe_summary", {})))
    after_sanitary = safe_dict(manager.latest_outputs.get("sanitary", project.meta.get("sanitary_summary", {})))
    after_utilities = safe_dict(manager.latest_outputs.get("utilities", project.meta.get("utility_summary", {})))
    after_drainage = safe_dict(manager.latest_outputs.get("drainage", project.meta.get("drainage_canonical", {})))
    added_length = 0.0
    added_depth = 0.0
    if "storm" in changed_systems:
        added_length += _length_total(safe_list(after_storm.get("segments")), "path") - _length_total(safe_list(before_storm.get("segments")), "path")
        added_depth += _avg_depth(after_storm, "start_invert", "end_invert") - _avg_depth(before_storm, "start_invert", "end_invert")
    if "sanitary" in changed_systems:
        added_length += _length_total(safe_list(after_sanitary.get("segments")), "route_points") - _length_total(safe_list(before_sanitary.get("segments")), "route_points")
        added_depth += _avg_depth(after_sanitary, "start_invert_ft", "end_invert_ft") - _avg_depth(before_sanitary, "start_invert_ft", "end_invert_ft")
    if "utilities" in changed_systems or "water" in changed_systems:
        before_hooks = safe_dict(before_utilities.get("conflict_hooks"))
        after_hooks = safe_dict(after_utilities.get("conflict_hooks"))
        added_length += _length_total(safe_list(after_hooks.get("utility_segments")), "route_points") - _length_total(safe_list(before_hooks.get("utility_segments")), "route_points")
        added_depth += _avg_depth({"segments": safe_list(after_hooks.get("utility_segments"))}, "start_invert_ft", "end_invert_ft") - _avg_depth({"segments": safe_list(before_hooks.get("utility_segments"))}, "start_invert_ft", "end_invert_ft")
    after_structures = len(safe_list(after_sanitary.get("manholes"))) + len(safe_list(after_drainage.get("structures"))) + len(safe_list(after_utilities.get("structures")))
    before_structures = len(safe_list(before_sanitary.get("manholes"))) + len(safe_list(before_drainage.get("structures"))) + len(safe_list(before_utilities.get("structures")))
    grading_adjustments = _grading_local_adjustments(project)
    return {
        "added_length_ft": round(added_length, 3),
        "added_depth_ft": round(added_depth, 3),
        "added_structures": max(after_structures - before_structures, 0),
        "hydraulic_impact": {
            "storm_capacity_delta_cfs": round(safe_float(after_storm.get("total_system_capacity_cfs"), 0.0) - safe_float(before_storm.get("total_system_capacity_cfs"), 0.0), 3),
            "storm_ratio_delta": round(safe_float(after_storm.get("max_capacity_ratio"), 0.0) - safe_float(before_storm.get("max_capacity_ratio"), 0.0), 3),
            "sanitary_slope_violation_delta": len(safe_list(after_sanitary.get("slope_violations"))) - len(safe_list(before_sanitary.get("slope_violations"))),
        },
        "earthwork_impact": {
            "grading_adjustment_count": len(grading_adjustments),
            "cut_fill_delta_cf": round(sum(safe_float(item.get("cut_fill_delta_cf"), 0.0) for item in grading_adjustments), 3),
        },
        "resolved_conflicts": max(len(pre_conflicts) - len(post_conflicts), 0),
        "new_conflicts_avoided": max(len(pre_conflicts) - len(post_conflicts), 0),
    }


def _conflict_signature(conflict: Dict[str, Any]) -> Tuple[str, Tuple[str, ...]]:
    return (
        safe_str(conflict.get("conflict_type")),
        tuple(sorted(safe_str(name) for name in safe_list(conflict.get("involved_objects")) if safe_str(name))),
    )


def _conflict_location(conflict: Dict[str, Any]) -> List[float]:
    location = safe_list(safe_dict(conflict).get("location"))
    if len(location) >= 2:
        return [safe_float(location[0], 0.0), safe_float(location[1], 0.0)]
    return [0.0, 0.0]


def _conflict_distance(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    pa = _conflict_location(a)
    pb = _conflict_location(b)
    return ((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2) ** 0.5


def _conflicts_related(a: Dict[str, Any], b: Dict[str, Any], threshold_ft: float = 18.0) -> bool:
    a_rec = safe_dict(a)
    b_rec = safe_dict(b)
    a_objects = {safe_str(item) for item in safe_list(a_rec.get("involved_objects")) if safe_str(item)}
    b_objects = {safe_str(item) for item in safe_list(b_rec.get("involved_objects")) if safe_str(item)}
    if a_objects & b_objects:
        return True
    a_systems = {safe_str(item) for item in safe_list(a_rec.get("systems")) if safe_str(item)}
    b_systems = {safe_str(item) for item in safe_list(b_rec.get("systems")) if safe_str(item)}
    if a_systems and b_systems and (a_systems & b_systems) and _conflict_distance(a_rec, b_rec) <= threshold_ft:
        return True
    trench_systems = {"storm", "sanitary", "water", "utilities", "gas", "electric", "telecom"}
    if (a_systems & trench_systems) and (b_systems & trench_systems):
        if _conflict_distance(a_rec, b_rec) <= max(threshold_ft, 28.0):
            return True
    a_types = {safe_str(a_rec.get("conflict_type"))}
    b_types = {safe_str(b_rec.get("conflict_type"))}
    if any(item.endswith("_geometry") for item in a_types | b_types):
        protected_systems = {"building_pad", "roadway"} | HARD_PROTECTED_ZONE_KINDS
        if (a_systems & protected_systems or b_systems & protected_systems) and _conflict_distance(a_rec, b_rec) <= max(threshold_ft, 24.0):
            return True
    return False


def _system_family_name(system_name: str) -> str:
    name = lower_text(system_name)
    if name in {"storm", "drainage"}:
        return "storm"
    if name in {"sanitary", "sewer"}:
        return "sanitary"
    if name in {"water", "utilities", "utility", "gas", "electric", "telecom"}:
        return "water_utility"
    if name in {"roadway", "building_pad"} or name in HARD_PROTECTED_ZONE_KINDS:
        return "protected_zone"
    return name or "unknown"


def _cluster_corridor_context(project: Optional[ProjectModel], systems: Sequence[str], center: Sequence[float]) -> Dict[str, Any]:
    rows = [safe_str(item) for item in systems if safe_str(item)]
    corridor_key = "generic"
    if "sanitary" in rows:
        corridor_key = "sanitary"
    elif "storm" in rows:
        corridor_key = "storm"
    elif "water" in rows or "utilities" in rows or "gas" in rows or "electric" in rows or "telecom" in rows:
        corridor_key = "water"
    corridor = safe_dict(safe_dict(project.meta.get("preferred_corridors")).get(corridor_key)) if project is not None else {}
    if not corridor:
        return {"corridor_key": corridor_key, "corridor_axis": "unknown", "axis_value": None, "corridor_offset_ft": None}
    orientation = safe_str(corridor.get("orientation"), "unknown")
    axis_value = safe_float(corridor.get("axis_value"), 0.0)
    offset = None
    if isinstance(center, (list, tuple)) and len(center) >= 2:
        offset = abs(safe_float(center[1], 0.0) - axis_value) if orientation == "horizontal" else abs(safe_float(center[0], 0.0) - axis_value)
    return {
        "corridor_key": corridor_key,
        "corridor_axis": orientation,
        "axis_value": round(axis_value, 3),
        "corridor_offset_ft": round(safe_float(offset), 3) if offset is not None else None,
    }


def _group_conflict_clusters(conflicts: Sequence[Dict[str, Any]], project: Optional[ProjectModel] = None) -> List[Dict[str, Any]]:
    clusters: List[List[Dict[str, Any]]] = []
    for conflict in conflicts:
        rec = safe_dict(conflict)
        if not rec:
            continue
        related_indexes: List[int] = []
        for idx, cluster in enumerate(clusters):
            if any(_conflicts_related(existing, rec) for existing in cluster):
                related_indexes.append(idx)
        if not related_indexes:
            clusters.append([deepcopy(rec)])
            continue
        merged: List[Dict[str, Any]] = [deepcopy(rec)]
        for idx in reversed(related_indexes):
            merged.extend(clusters.pop(idx))
        deduped: List[Dict[str, Any]] = []
        seen: set[Tuple[str, Tuple[str, ...]]] = set()
        for item in merged:
            signature = _conflict_signature(item)
            if signature in seen:
                continue
            seen.add(signature)
            deduped.append(item)
        clusters.append(sorted(deduped, key=_conflict_priority_key))

    cluster_rows: List[Dict[str, Any]] = []
    for idx, cluster in enumerate(sorted(clusters, key=lambda items: _conflict_priority_key(items[0]) if items else (9, 9, "zzz")), start=1):
        objects = sorted({safe_str(name) for item in cluster for name in safe_list(safe_dict(item).get("involved_objects")) if safe_str(name)})
        systems = sorted({safe_str(name) for item in cluster for name in safe_list(safe_dict(item).get("systems")) if safe_str(name)})
        center = _segment_midpoint([_conflict_location(item) for item in cluster] or [[0.0, 0.0], [0.0, 0.0]])
        corridor_context = _cluster_corridor_context(project, systems, center)
        families = sorted({_system_family_name(name) for name in systems if safe_str(name)})
        trench_like = bool({"storm", "sanitary", "water_utility"} & set(families))
        blocking_kinds = sorted(
            {
                safe_str(name)
                for name in systems
                if safe_str(name) in {"roadway", "building_pad"} or safe_str(name) in HARD_PROTECTED_ZONE_KINDS
            }
        )
        cluster_rows.append(
            {
                "cluster_id": f"cluster_group::{idx}",
                "conflicts": deepcopy(cluster),
                "systems": systems,
                "objects": objects,
                "conflict_count": len(cluster),
                "center": center,
                "system_families": families,
                "trench_group_id": f"trench::{corridor_context.get('corridor_key')}::{idx}" if trench_like else "",
                "trench_like": trench_like,
                "blocking_zone_kinds": blocking_kinds,
                **corridor_context,
            }
        )
    return cluster_rows


def _cluster_group_related(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    a_rec = safe_dict(a)
    b_rec = safe_dict(b)
    if safe_str(a_rec.get("cluster_id")) == safe_str(b_rec.get("cluster_id")):
        return True
    a_objects = {safe_str(item) for item in safe_list(a_rec.get("objects")) if safe_str(item)}
    b_objects = {safe_str(item) for item in safe_list(b_rec.get("objects")) if safe_str(item)}
    if a_objects & b_objects:
        return True
    a_systems = {safe_str(item) for item in safe_list(a_rec.get("systems")) if safe_str(item)}
    b_systems = {safe_str(item) for item in safe_list(b_rec.get("systems")) if safe_str(item)}
    same_corridor = (
        bool(a_rec.get("trench_like"))
        and bool(b_rec.get("trench_like"))
        and safe_str(a_rec.get("corridor_key"))
        and safe_str(a_rec.get("corridor_key")) == safe_str(b_rec.get("corridor_key"))
        and safe_str(a_rec.get("corridor_axis")) == safe_str(b_rec.get("corridor_axis"))
    )
    if same_corridor:
        distance = _conflict_distance({"location": safe_list(a_rec.get("center"))}, {"location": safe_list(b_rec.get("center"))})
        if distance <= 72.0:
            return True
        if a_systems & b_systems and distance <= 108.0:
            return True
    return False


def _group_cluster_groups(clusters: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: List[List[Dict[str, Any]]] = []
    for cluster in [safe_dict(item) for item in clusters if safe_dict(item)]:
        related_indexes: List[int] = []
        for idx, group in enumerate(groups):
            if any(_cluster_group_related(existing, cluster) for existing in group):
                related_indexes.append(idx)
        if not related_indexes:
            groups.append([deepcopy(cluster)])
            continue
        merged: List[Dict[str, Any]] = [deepcopy(cluster)]
        for idx in reversed(related_indexes):
            merged.extend(groups.pop(idx))
        deduped: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for row in merged:
            cluster_id = safe_str(safe_dict(row).get("cluster_id"))
            if cluster_id and cluster_id in seen:
                continue
            if cluster_id:
                seen.add(cluster_id)
            deduped.append(deepcopy(safe_dict(row)))
        groups.append(sorted(deduped, key=lambda item: safe_str(safe_dict(item).get("cluster_id"))))

    grouped_rows: List[Dict[str, Any]] = []
    ordered_groups = sorted(
        groups,
        key=lambda rows: (
            min((_conflict_priority_key(safe_list(safe_dict(item).get("conflicts"))[0]) for item in rows if safe_list(safe_dict(item).get("conflicts"))), default=(9, 9, "zzz")),
            safe_str(safe_dict(rows[0]).get("cluster_id")) if rows else "",
        ),
    )
    for idx, group in enumerate(ordered_groups, start=1):
        all_conflicts = [deepcopy(safe_dict(conflict)) for cluster in group for conflict in safe_list(safe_dict(cluster).get("conflicts")) if safe_dict(conflict)]
        grouped_rows.append(
            {
                "cluster_group_id": f"cluster_bundle::{idx}",
                "clusters": deepcopy(group),
                "cluster_ids": [safe_str(safe_dict(item).get("cluster_id")) for item in group if safe_str(safe_dict(item).get("cluster_id"))],
                "conflicts": all_conflicts,
                "systems": sorted({safe_str(name) for item in group for name in safe_list(safe_dict(item).get("systems")) if safe_str(name)}),
                "objects": sorted({safe_str(name) for item in group for name in safe_list(safe_dict(item).get("objects")) if safe_str(name)}),
                "trench_like": any(bool(safe_dict(item).get("trench_like")) for item in group),
                "corridor_key": safe_str(safe_dict(group[0]).get("corridor_key")) if group else "",
                "corridor_axis": safe_str(safe_dict(group[0]).get("corridor_axis")) if group else "",
                "axis_value": safe_float(safe_dict(group[0]).get("axis_value"), 0.0) if group else 0.0,
                "blocking_zone_kinds": sorted({safe_str(kind) for item in group for kind in safe_list(safe_dict(item).get("blocking_zone_kinds")) if safe_str(kind)}),
            }
        )
    return grouped_rows


def _matching_cluster(current_clusters: Sequence[Dict[str, Any]], target: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    target_rec = safe_dict(target)
    target_id = safe_str(target_rec.get("cluster_id"))
    if target_id:
        for cluster in current_clusters:
            if safe_str(safe_dict(cluster).get("cluster_id")) == target_id:
                return safe_dict(cluster)
    target_objects = {safe_str(item) for item in safe_list(target_rec.get("objects")) if safe_str(item)}
    target_systems = {safe_str(item) for item in safe_list(target_rec.get("systems")) if safe_str(item)}
    best: Optional[Dict[str, Any]] = None
    best_score = -1
    for cluster in current_clusters:
        rec = safe_dict(cluster)
        objects = {safe_str(item) for item in safe_list(rec.get("objects")) if safe_str(item)}
        systems = {safe_str(item) for item in safe_list(rec.get("systems")) if safe_str(item)}
        score = len(target_objects & objects) * 10 + len(target_systems & systems)
        if score > best_score:
            best_score = score
            best = rec
    return deepcopy(best) if best_score > 0 and best is not None else None


def _cluster_group_remaining_conflicts(conflicts: Sequence[Dict[str, Any]], group: Dict[str, Any]) -> List[Dict[str, Any]]:
    originals = [safe_dict(item) for item in safe_list(safe_dict(group).get("conflicts")) if safe_dict(item)]
    remaining: List[Dict[str, Any]] = []
    for conflict in conflicts:
        rec = safe_dict(conflict)
        if any(_conflicts_related(rec, original, threshold_ft=30.0) for original in originals):
            remaining.append(deepcopy(rec))
    return sorted(remaining, key=_conflict_priority_key)


def _matching_conflicts(conflicts: Sequence[Dict[str, Any]], target: Dict[str, Any]) -> List[Dict[str, Any]]:
    signature = _conflict_signature(target)
    return [safe_dict(item) for item in conflicts if _conflict_signature(safe_dict(item)) == signature]


def _count_conflicts_by_type(conflicts: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for conflict in conflicts:
        conflict_type = safe_str(safe_dict(conflict).get("conflict_type"), "unknown")
        counts[conflict_type] = counts.get(conflict_type, 0) + 1
    return counts


def _conflict_priority_key(conflict: Dict[str, Any]) -> Tuple[int, int, str]:
    rec = safe_dict(conflict)
    severity_rank = {"error": 0, "warning": 1, "info": 2}.get(lower_text(rec.get("severity")), 3)
    conflict_type = safe_str(rec.get("conflict_type"))
    system_priority = 5
    systems = {safe_str(item) for item in safe_list(rec.get("systems"))}
    if {"storm", "sanitary"} <= systems:
        system_priority = 0
    elif "water" in systems and ("storm" in systems or "sanitary" in systems):
        system_priority = 1
    elif "building_pad" in systems or "roadway" in systems:
        system_priority = 2
    elif conflict_type == "pipe_cover_violation":
        system_priority = 3
    elif conflict_type == "slope_violation":
        system_priority = 4
    return (severity_rank, system_priority, conflict_type)


def _detect_coordination_conflicts(project: ProjectModel, manager: ProjectManager) -> List[Dict[str, Any]]:
    segments = _normalized_summary_segments(project, manager)
    obstacles = _expanded_obstacle_rectangles(project)
    conflicts: List[Dict[str, Any]] = []

    for idx, first in enumerate(segments):
        path_a = _sample_coordination_path(safe_list(first.get("path")))
        if len(path_a) < 2:
            continue
        for second in segments[idx + 1 :]:
            path_b = _sample_coordination_path(safe_list(second.get("path")))
            if len(path_b) < 2 or safe_str(first.get("name")) == safe_str(second.get("name")):
                continue
            pair = tuple(sorted([safe_str(first.get("system")), safe_str(second.get("system"))]))
            rule = _crossing_rule_for(pair)
            if not rule:
                continue
            required_h = safe_float(rule.get("required_horizontal_clearance_ft"), 0.0)
            required_v = safe_float(rule.get("required_vertical_clearance_ft"), 0.0)
            actual_h = _path_min_segment_distance(path_a, path_b, early_stop_ft=min(required_h, 1.0))
            avg_v = abs(_segment_average_invert(first) - _segment_average_invert(second))
            is_crossing = actual_h <= 1.0
            actual_angle = _crossing_angle_deg(path_a, path_b)
            conflict_detected = avg_v < required_v if is_crossing else actual_h < required_h
            if conflict_detected:
                conflicts.append(
                    {
                        "conflict_type": f"{pair[0]}_{pair[1]}_clearance",
                        "involved_objects": [safe_str(first.get("name")), safe_str(second.get("name"))],
                        "systems": [safe_str(first.get("system")), safe_str(second.get("system"))],
                        "location": _segment_midpoint(path_a),
                        "station_ft": _conflict_station(first),
                        "severity": "error" if actual_h < required_h * 0.6 or avg_v < required_v * 0.6 else "warning",
                        "required_horizontal_clearance_ft": required_h,
                        "actual_horizontal_clearance_ft": round(actual_h, 3),
                        "required_vertical_clearance_ft": required_v,
                        "actual_vertical_clearance_ft": round(avg_v, 3),
                        "preferred_lower_system": safe_str(rule.get("preferred_lower_system")),
                        "preferred_crossing_angle_deg": safe_float(rule.get("preferred_crossing_angle_deg"), 0.0),
                        "interaction_type": "crossing" if is_crossing else "parallel",
                        "crossing_angle_deg": actual_angle,
                        "status": "detected",
                    }
                )

    for segment in segments:
        if safe_float(segment.get("cover_start_ft"), 0.0) + 1e-6 < safe_float(segment.get("min_cover_ft"), 0.0):
            conflicts.append(
                {
                    "conflict_type": "pipe_cover_violation",
                    "involved_objects": [safe_str(segment.get("name"))],
                    "systems": [safe_str(segment.get("system"))],
                    "location": safe_list(safe_list(segment.get("path"))[:1] or [[0.0, 0.0]])[0],
                    "station_ft": 0.0,
                    "severity": "error",
                    "required_clearance_ft": safe_float(segment.get("min_cover_ft"), 0.0),
                    "actual_clearance_ft": round(safe_float(segment.get("cover_start_ft"), 0.0), 3),
                    "status": "detected",
                }
            )
        if safe_float(segment.get("cover_end_ft"), 0.0) + 1e-6 < safe_float(segment.get("min_cover_ft"), 0.0):
            conflicts.append(
                {
                    "conflict_type": "pipe_cover_violation",
                    "involved_objects": [safe_str(segment.get("name"))],
                    "systems": [safe_str(segment.get("system"))],
                    "location": safe_list(safe_list(segment.get("path"))[-1:] or [[0.0, 0.0]])[0],
                    "station_ft": safe_float(segment.get("length_ft"), 0.0),
                    "severity": "error",
                    "required_clearance_ft": safe_float(segment.get("min_cover_ft"), 0.0),
                    "actual_clearance_ft": round(safe_float(segment.get("cover_end_ft"), 0.0), 3),
                    "status": "detected",
                }
            )
        min_slope = safe_float(segment.get("min_slope_ft_ft"), 0.0)
        actual_slope = safe_float(segment.get("slope_ft_ft"), 0.0)
        if min_slope > 0.0 and actual_slope + 1e-4 < min_slope:
            conflicts.append(
                {
                    "conflict_type": "slope_violation",
                    "involved_objects": [safe_str(segment.get("name"))],
                    "systems": [safe_str(segment.get("system"))],
                    "location": _segment_midpoint(safe_list(segment.get("path"))),
                    "station_ft": _conflict_station(segment),
                    "severity": "error",
                    "required_slope_ft_ft": round(min_slope, 5),
                    "actual_slope_ft_ft": round(actual_slope, 5),
                    "status": "detected",
                }
            )
        for rect in obstacles:
            system_name = safe_str(segment.get("system"))
            if system_name not in {"storm", "sanitary", "water", "gas", "electric", "telecom"}:
                continue
            if not bool(rect.get("avoid")):
                continue
            path = safe_list(segment.get("path"))
            if safe_str(rect.get("kind")) == "building_pad" and system_name in {"storm", "sanitary", "water", "gas", "electric", "telecom"}:
                endpoint_inside = bool(path) and (
                    _point_inside_buffered_rect(path[0], rect)
                    or _point_inside_buffered_rect(path[-1], rect)
                )
                interior_points = path[1:-1]
                role = safe_str(segment.get("segment_role")).lower()
                if (
                    endpoint_inside
                    and role in {"service", "service_connection", "lateral", "roof_lateral", "building_service"}
                ):
                    continue
            if any(_point_inside_buffered_rect(point, rect) for point in path) or any(
                _segment_hits_buffered_rect(path[idx - 1], path[idx], rect) for idx in range(1, len(path))
            ):
                conflicts.append(
                    {
                        "conflict_type": f"{safe_str(segment.get('system'))}_{safe_str(rect.get('kind'))}_geometry",
                        "involved_objects": [safe_str(segment.get("name")), safe_str(rect.get("name"))],
                        "systems": [safe_str(segment.get("system")), safe_str(rect.get("kind"))],
                        "location": _segment_midpoint(safe_list(segment.get("path"))),
                        "station_ft": _conflict_station(segment),
                        "severity": "error",
                        "required_clearance_ft": safe_float(rect.get("buffer_ft"), 0.0),
                        "actual_clearance_ft": 0.0,
                        "status": "detected",
                    }
                )
    return conflicts


def _find_summary_segment(project: ProjectModel, manager: ProjectManager, name: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    storm = safe_dict(manager.latest_outputs.get("storm_pipe_summary", project.meta.get("storm_pipe_summary", {})))
    for rec in safe_list(storm.get("segments")):
        row = safe_dict(rec)
        if safe_str(row.get("pipe"), safe_str(row.get("name"))) == name:
            return "storm", row
    sanitary = safe_dict(manager.latest_outputs.get("sanitary", project.meta.get("sanitary_summary", {})))
    for rec in safe_list(sanitary.get("segments")):
        row = safe_dict(rec)
        if safe_str(row.get("name")) == name:
            return "sanitary", row
    utilities = safe_dict(manager.latest_outputs.get("utilities", project.meta.get("utility_summary", {})))
    hooks = safe_dict(utilities.get("conflict_hooks"))
    for rec in safe_list(hooks.get("utility_segments")):
        row = safe_dict(rec)
        if safe_str(row.get("name")) == name:
            return _utility_system_type(row, hooks), row
    return None


def _snapshot_coordination_state(project: ProjectModel, manager: ProjectManager) -> Dict[str, Any]:
    return _snapshot_coordination_state_impl(project, manager)


def _restore_coordination_state(project: ProjectModel, manager: ProjectManager, snapshot: Dict[str, Any]) -> None:
    _restore_coordination_state_impl(project, manager, snapshot)


def _full_coordination_state_snapshot(project: ProjectModel, manager: ProjectManager) -> Dict[str, Any]:
    return _full_coordination_state_snapshot_impl(project, manager)


def _restore_full_coordination_state(project: ProjectModel, manager: ProjectManager, snapshot: Dict[str, Any]) -> None:
    _restore_full_coordination_state_impl(project, manager, snapshot)


def _sync_drainage_mutable_state(
    project: ProjectModel,
    manager: ProjectManager,
    *,
    structures: Optional[Sequence[Dict[str, Any]]] = None,
    stats: Optional[Dict[str, Any]] = None,
    export_validation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _sync_drainage_mutable_state_impl(
        project,
        manager,
        structures=structures,
        stats=stats,
        export_validation=export_validation,
    )


def _reroute_around_rect(path: List[List[float]], rect: Dict[str, Any]) -> List[List[float]]:
    candidates = _reroute_candidates_around_rect(path, rect)
    return min(candidates, key=lambda candidate: polyline_length(candidate))


def _grading_local_adjustments(project: ProjectModel) -> List[Dict[str, Any]]:
    return _grading_local_adjustments_impl(project)


def _add_grading_adjustment(project: ProjectModel, note: Dict[str, Any]) -> None:
    _add_grading_adjustment_impl(project, note)


def _manning_full_capacity_cfs(diameter_in: float, slope_ft_ft: float, mannings_n: float = PIPE_MANNINGS_N) -> float:
    diameter_ft = max(diameter_in, 1.0) / 12.0
    area = 3.141592653589793 * diameter_ft * diameter_ft / 4.0
    wetted_perimeter = 3.141592653589793 * diameter_ft
    hydraulic_radius = area / max(wetted_perimeter, 1e-9)
    return round((1.486 / max(mannings_n, 1e-9)) * area * (hydraulic_radius ** (2.0 / 3.0)) * (max(slope_ft_ft, 1e-9) ** 0.5), 3)


def _summary_segment_id(rec: Dict[str, Any], fallback_prefix: str) -> str:
    return safe_str(rec.get("id"), safe_str(rec.get("name") or rec.get("pipe"), f"{fallback_prefix}_segment"))


def _hydraulic_contributing_area_ac(flow_cfs: float, runoff_c: float, intensity_in_hr: float) -> float:
    if flow_cfs <= 0.0 or runoff_c <= 0.0 or intensity_in_hr <= 0.0:
        return 0.0
    return round(flow_cfs * 96.23 / max(runoff_c * intensity_in_hr, 1e-9), 4)


def _merge_validation_payload(
    computed: Dict[str, Any],
    prior: Dict[str, Any],
    list_keys: Sequence[str],
) -> Dict[str, Any]:
    if not prior:
        return computed
    merged = deepcopy(computed)
    for key in list_keys:
        merged[key] = dedupe_keep_order(list(safe_list(computed.get(key))) + list(safe_list(prior.get(key))))
    if "valid" in computed or "valid" in prior:
        merged["valid"] = bool(computed.get("valid", True)) and bool(prior.get("valid", True))
    return merged


def _validate_storm_hydraulics(summary: Dict[str, Any]) -> Dict[str, Any]:
    segments = [safe_dict(item) for item in safe_list(summary.get("segments")) if safe_dict(item)]
    geometry_only_segments: List[str] = []
    missing_accumulation_segments: List[str] = []
    invalid_capacity_ratio_segments: List[Dict[str, Any]] = []
    downstream_total_inconsistencies: List[Dict[str, Any]] = []
    backwater_failures: List[Dict[str, Any]] = []
    surcharge_failures: List[Dict[str, Any]] = []
    node_inflow: Dict[str, float] = {}
    node_outflow: Dict[str, float] = {}
    tolerance = 0.05

    for rec in segments:
        seg_id = _summary_segment_id(rec, "storm")
        flow = safe_float(rec.get("flow_cfs"), 0.0)
        capacity = safe_float(rec.get("capacity_cfs"), 0.0)
        slope = safe_float(rec.get("slope_ft_ft"), safe_float(rec.get("slope_pct"), 0.0) / 100.0)
        from_name = safe_str(rec.get("from") or rec.get("start_name"))
        to_name = safe_str(rec.get("to") or rec.get("end_name"))
        if flow <= 0.0 or capacity <= 0.0 or slope <= 0.0:
            geometry_only_segments.append(seg_id)
        contributing_area = safe_float(rec.get("contributing_area_ac"), safe_float(rec.get("tributary_area_ac"), 0.0))
        if contributing_area <= 0.0:
            missing_accumulation_segments.append(seg_id)
        ratio = safe_float(rec.get("capacity_ratio"), 0.0)
        if flow > 0.0 and capacity > 0.0 and ratio <= 0.0:
            ratio = flow / max(capacity, 1e-9)
        if flow > 0.0 and (ratio <= 0.0 or ratio > 1.05):
            invalid_capacity_ratio_segments.append({"segment_id": seg_id, "capacity_ratio": round(ratio, 3)})
        if from_name:
            node_outflow[from_name] = node_outflow.get(from_name, 0.0) + flow
        if to_name:
            node_inflow[to_name] = node_inflow.get(to_name, 0.0) + flow

    for node_id, inflow in node_inflow.items():
        outflow = node_outflow.get(node_id, 0.0)
        if outflow > 0.0 and outflow + tolerance < inflow:
            downstream_total_inconsistencies.append(
                {
                    "node_id": node_id,
                    "incoming_flow_cfs": round(inflow, 3),
                    "outgoing_flow_cfs": round(outflow, 3),
                }
            )
    backwater_validation = safe_dict(summary.get("backwater_validation"))
    if backwater_validation and backwater_validation.get("valid") is False:
        backwater_failures.append(
            {
                "reason": "tailwater_surcharges_pipe_crown",
                "max_tailwater_surcharge_ft": round(safe_float(backwater_validation.get("max_tailwater_surcharge_ft"), 0.0), 3),
                "surcharged_segments": deepcopy(safe_list(backwater_validation.get("surcharged_segments"))),
            }
        )
    hydraulic_engine_summary = safe_dict(summary.get("hydraulic_engine_summary"))
    for node in safe_list(hydraulic_engine_summary.get("critical_nodes")):
        rec = safe_dict(node)
        if bool(rec.get("surcharge_risk")):
            surcharge_failures.append(
                {
                    "reason": "node_hgl_exceeds_rim_threshold",
                    "node": safe_str(rec.get("name")),
                    "max_hgl_ft": round(safe_float(rec.get("max_hgl_ft"), 0.0), 3),
                    "rim_elev_ft": round(safe_float(rec.get("rim_elev_ft"), 0.0), 3),
                }
            )

    return {
        "system": "storm",
        "geometry_only_segments": geometry_only_segments,
        "missing_accumulation_segments": missing_accumulation_segments,
        "invalid_capacity_ratio_segments": invalid_capacity_ratio_segments,
        "downstream_total_inconsistencies": downstream_total_inconsistencies,
        "backwater_failures": backwater_failures,
        "surcharge_failures": surcharge_failures,
        "valid": not any(
            [
                geometry_only_segments,
                missing_accumulation_segments,
                invalid_capacity_ratio_segments,
                downstream_total_inconsistencies,
                backwater_failures,
                surcharge_failures,
            ]
        ),
    }


def _repair_sanitary_segment_covers(
    segments: Sequence[Dict[str, Any]],
    proposed_surface: Optional[GridSurface],
    *,
    min_cover_ft: float = PIPE_MIN_COVER_FT,
) -> List[Dict[str, Any]]:
    repairs: List[Dict[str, Any]] = []
    max_cover_ft = 30.0
    if proposed_surface is None:
        return repairs
    for rec in segments:
        path = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(rec.get("route_points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        if len(path) < 2:
            continue
        length_ft = max(polyline_length(path), 1e-9)
        role = safe_str(rec.get("segment_role"), "main")
        diameter = safe_float(rec.get("diameter_in"), 8.0)
        min_slope = _sanitary_min_slope(role, diameter)
        start_surface = _sample_grid_surface(proposed_surface, path[0][0], path[0][1], DEFAULT_PAD_ELEV)
        end_surface = _sample_grid_surface(proposed_surface, path[-1][0], path[-1][1], DEFAULT_PAD_ELEV)
        start_invert = safe_float(rec.get("start_invert_ft"), DEFAULT_PAD_ELEV - 5.0)
        end_invert = safe_float(rec.get("end_invert_ft"), DEFAULT_PAD_ELEV - 6.0)
        repaired_start = min(max(start_invert, start_surface - max_cover_ft), start_surface - min_cover_ft)
        repaired_end = min(max(end_invert, end_surface - max_cover_ft), end_surface - min_cover_ft)
        required_drop = min_slope * length_ft
        if repaired_start - repaired_end + 1e-6 < required_drop:
            repaired_end = min(
                max(repaired_start - required_drop, end_surface - max_cover_ft),
                end_surface - min_cover_ft,
            )
            if repaired_start - repaired_end + 1e-6 < required_drop:
                repaired_start = min(
                    max(repaired_end + required_drop, start_surface - max_cover_ft),
                    start_surface - min_cover_ft,
                )
        if abs(repaired_start - start_invert) > 1e-6 or abs(repaired_end - end_invert) > 1e-6:
            repairs.append(
                {
                    "segment_id": _summary_segment_id(rec, "sanitary"),
                    "start_invert_before_ft": round(start_invert, 3),
                    "end_invert_before_ft": round(end_invert, 3),
                    "start_invert_after_ft": round(repaired_start, 3),
                    "end_invert_after_ft": round(repaired_end, 3),
                    "min_cover_ft": round(min_cover_ft, 3),
                }
            )
        rec["start_invert_ft"] = round(repaired_start, 3)
        rec["end_invert_ft"] = round(repaired_end, 3)
        rec["slope_ft_ft"] = round(max((repaired_start - repaired_end) / length_ft, 0.0), 5)
        rec["cover_start_ft"] = round(start_surface - repaired_start, 3)
        rec["cover_end_ft"] = round(end_surface - repaired_end, 3)
    return repairs


def _precoordinate_vertical_hierarchy(project: ProjectModel, manager: ProjectManager) -> None:
    """Set a deterministic concept-depth stack before geometric conflict solving.

    This does not waive any clearance rule; it gives the solver a realistic
    starting point: water shallow, sanitary below water, storm deepest.
    """

    grading = safe_dict(canonical_stage_output(project, manager, "grading"))
    proposed_surface = grading.get("proposed_surface")

    def _surface_at(path: List[List[float]], index: int, default: float = DEFAULT_PAD_ELEV) -> float:
        if not path:
            return default
        point = path[index]
        return _sample_grid_surface(proposed_surface, point[0], point[1], default)

    storm = safe_dict(manager.latest_outputs.get("storm_pipe_summary", project.meta.get("storm_pipe_summary", {})))
    storm_changed = False
    building_pads = [
        rect for rect in _expanded_obstacle_rectangles(project)
        if safe_str(rect.get("kind")) == "building_pad" and bool(rect.get("avoid"))
    ]

    def _path_hits_rect(path: List[List[float]], rect: Dict[str, Any]) -> bool:
        return any(
            _segment_hits_buffered_rect(path[idx - 1], path[idx], rect)
            for idx in range(1, len(path))
        )

    def _reroute_around_rect(path: List[List[float]], rect: Dict[str, Any]) -> List[List[float]]:
        if len(path) < 2 or not _path_hits_rect(path, rect):
            return path
        start = path[0]
        end = path[-1]
        buffer_ft = max(6.0, safe_float(rect.get("buffer_ft"), 0.0) + 4.0)
        left_x = safe_float(rect.get("x"), 0.0) - buffer_ft
        right_x = safe_float(rect.get("x"), 0.0) + safe_float(rect.get("w"), 0.0) + buffer_ft
        below_y = safe_float(rect.get("y"), 0.0) - buffer_ft
        above_y = safe_float(rect.get("y"), 0.0) + safe_float(rect.get("h"), 0.0) + buffer_ft
        candidates = [
            [start, [left_x, start[1]], [left_x, end[1]], end],
            [start, [right_x, start[1]], [right_x, end[1]], end],
            [start, [start[0], below_y], [end[0], below_y], end],
            [start, [start[0], above_y], [end[0], above_y], end],
        ]
        clean = [
            candidate for candidate in candidates
            if not _path_hits_rect([[round(pt[0], 3), round(pt[1], 3)] for pt in candidate], rect)
        ]
        if not clean:
            return path
        best = min(clean, key=polyline_length)
        deduped: List[List[float]] = []
        for pt in best:
            rounded = [round(safe_float(pt[0], 0.0), 3), round(safe_float(pt[1], 0.0), 3)]
            if not deduped or abs(deduped[-1][0] - rounded[0]) > 1e-6 or abs(deduped[-1][1] - rounded[1]) > 1e-6:
                deduped.append(rounded)
        return deduped

    for rec in safe_list(storm.get("segments")):
        row = safe_dict(rec)
        path = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(row.get("path") or row.get("route_points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        if len(path) < 2:
            continue
        original_path = deepcopy(path)
        for rect in building_pads:
            path = _reroute_around_rect(path, rect)
        if path != original_path:
            row["path"] = deepcopy(path)
            row["route_points"] = deepcopy(path)
            row["length_ft"] = round(polyline_length(path), 3)
            row.setdefault("routing_adjustments", []).append(
                {
                    "type": "building_pad_avoidance",
                    "source": "precoordination_reroute",
                    "truth_label": "storm route adjusted to avoid building pad before coordination validation.",
                }
            )
            storm_changed = True
        target_start = _surface_at(path, 0) - PRECOORDINATION_STORM_MAIN_COVER_FT
        target_end = _surface_at(path, -1) - PRECOORDINATION_STORM_MAIN_COVER_FT
        current_start = safe_float(row.get("start_invert_ft", row.get("start_invert")), target_start)
        current_end = safe_float(row.get("end_invert_ft", row.get("end_invert")), target_end)
        new_start = min(current_start, target_start)
        new_end = min(current_end, target_end, new_start - PIPE_MIN_SLOPE * max(polyline_length(path), 1.0))
        if abs(new_start - current_start) > 1e-6 or abs(new_end - current_end) > 1e-6:
            row["start_invert"] = row["start_invert_ft"] = round(new_start, 3)
            row["end_invert"] = row["end_invert_ft"] = round(new_end, 3)
            row["cover_start_ft"] = round(_surface_at(path, 0) - new_start, 3)
            row["cover_end_ft"] = round(_surface_at(path, -1) - new_end, 3)
            storm_changed = True
    if storm_changed:
        storm.setdefault("vertical_coordination", {})["depth_stack"] = "storm_below_sanitary_below_water"
        manager.latest_outputs["storm_pipe_summary"] = deepcopy(storm)
        project.meta["storm_pipe_summary"] = deepcopy(storm)

    sanitary = safe_dict(manager.latest_outputs.get("sanitary", project.meta.get("sanitary_summary", {})))
    sanitary_changed = False
    for rec in safe_list(sanitary.get("segments")):
        row = safe_dict(rec)
        path = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(row.get("route_points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        if len(path) < 2:
            continue
        role = safe_str(row.get("segment_role"), "main")
        target_cover = (
            PRECOORDINATION_SANITARY_SERVICE_COVER_FT
            if role == "service_connection"
            else PRECOORDINATION_SANITARY_MAIN_COVER_FT
        )
        target_start = _surface_at(path, 0) - target_cover
        target_end = _surface_at(path, -1) - max(target_cover, 7.5)
        current_start = safe_float(row.get("start_invert_ft"), target_start)
        current_end = safe_float(row.get("end_invert_ft"), target_end)
        new_start = min(current_start, target_start)
        new_end = min(current_end, target_end, new_start - _sanitary_min_slope(role, safe_float(row.get("diameter_in"), 8.0)) * max(polyline_length(path), 1.0))
        if abs(new_start - current_start) > 1e-6 or abs(new_end - current_end) > 1e-6:
            row["start_invert_ft"] = round(new_start, 3)
            row["end_invert_ft"] = round(new_end, 3)
            row["cover_start_ft"] = round(_surface_at(path, 0) - new_start, 3)
            row["cover_end_ft"] = round(_surface_at(path, -1) - new_end, 3)
            row["slope_ft_ft"] = round(max((new_start - new_end) / max(polyline_length(path), 1.0), 0.0), 5)
            sanitary_changed = True
    if sanitary_changed:
        sanitary.setdefault("vertical_coordination", {})["depth_stack"] = "sanitary_below_water_above_storm"
        manager.latest_outputs["sanitary"] = deepcopy(sanitary)
        project.meta["sanitary_summary"] = deepcopy(sanitary)


def _bind_sanitary_graph_nodes(
    segments: Sequence[Dict[str, Any]],
    manholes: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    bound_segments = [deepcopy(safe_dict(item)) for item in segments if safe_dict(item)]
    bound_manholes: List[Dict[str, Any]] = []
    canonical_nodes: List[Dict[str, Any]] = []
    known_node_ids: set[str] = set()
    coord_to_node_id: Dict[Tuple[float, float], str] = {}

    def _register_node(node_id: str, *, name: str, point: Optional[Sequence[float]], node_type: str) -> None:
        if not node_id or node_id in known_node_ids:
            return
        payload: Dict[str, Any] = {"id": node_id, "name": name or node_id, "node_type": node_type}
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            payload["x"] = round(safe_float(point[0], 0.0), 3)
            payload["y"] = round(safe_float(point[1], 0.0), 3)
        canonical_nodes.append(payload)
        known_node_ids.add(node_id)

    for index, manhole in enumerate(manholes, start=1):
        rec = deepcopy(safe_dict(manhole))
        x = round(safe_float(rec.get("x"), 0.0), 3)
        y = round(safe_float(rec.get("y"), 0.0), 3)
        name = safe_str(rec.get("name"), f"SMH-{index}")
        node_id = safe_str(rec.get("node_id") or rec.get("id"), name)
        rec["name"] = name
        rec["id"] = node_id
        rec["node_id"] = node_id
        coord_to_node_id[(x, y)] = node_id
        bound_manholes.append(rec)
        _register_node(node_id, name=name, point=[x, y], node_type="sanitary_manhole")

    for rec in bound_segments:
        path = [[round(safe_float(pt[0], 0.0), 3), round(safe_float(pt[1], 0.0), 3)] for pt in safe_list(rec.get("route_points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        node_chain: List[str] = []
        for idx, point in enumerate(path):
            node_id = coord_to_node_id.get((point[0], point[1]))
            if not node_id and idx == 0:
                node_id = safe_str(rec.get("from") or rec.get("start_name"))
            if not node_id and idx == len(path) - 1:
                node_id = safe_str(rec.get("to") or rec.get("end_name"))
            if node_id and (not node_chain or node_chain[-1] != node_id):
                node_chain.append(node_id)
                _register_node(node_id, name=node_id, point=point, node_type="sanitary_node")
        if len(node_chain) >= 2:
            rec["node_ids"] = node_chain
            rec["from"] = node_chain[0]
            rec["to"] = node_chain[-1]
            rec["start_name"] = node_chain[0]
            rec["end_name"] = node_chain[-1]

    return bound_segments, bound_manholes, canonical_nodes


def _validate_sanitary_network(summary: Dict[str, Any]) -> Dict[str, Any]:
    segments = [safe_dict(item) for item in safe_list(summary.get("segments")) if safe_dict(item)]
    slope_violations: List[Dict[str, Any]] = []
    disconnected_services: List[str] = []
    invalid_cover_segments: List[Dict[str, Any]] = []
    tie_in_issues: List[Dict[str, Any]] = []
    service_coverage = safe_dict(summary.get("service_coverage"))
    missing_service_buildings = safe_list(service_coverage.get("missing_buildings") or summary.get("missing_service_buildings"))
    disconnected_service_segments = safe_list(summary.get("disconnected_service_segments"))

    for rec in segments:
        seg_id = _summary_segment_id(rec, "sanitary")
        role = safe_str(rec.get("segment_role"))
        slope = safe_float(rec.get("slope_ft_ft"), 0.0)
        min_slope = _sanitary_min_slope(role, safe_float(rec.get("diameter_in"), 8.0))
        if slope + 1e-6 < min_slope:
            slope_violations.append({"segment_id": seg_id, "required_min_slope": round(min_slope, 5), "actual_slope": round(slope, 5)})
        if role == "service_connection" and (not safe_str(rec.get("start_name")) or not safe_str(rec.get("end_name"))):
            disconnected_services.append(seg_id)
        cover_start = safe_float(rec.get("cover_start_ft"), PIPE_MIN_COVER_FT)
        cover_end = safe_float(rec.get("cover_end_ft"), PIPE_MIN_COVER_FT)
        if cover_start < 2.0 or cover_end < 2.0 or cover_start > 30.0 or cover_end > 30.0:
            invalid_cover_segments.append(
                {
                    "segment_id": seg_id,
                    "cover_start_ft": round(cover_start, 3),
                    "cover_end_ft": round(cover_end, 3),
                }
            )
        if role == "main" and not safe_str(rec.get("end_name")):
            tie_in_issues.append({"segment_id": seg_id, "reason": "missing_downstream_tie_in"})

    return {
        "system": "sanitary",
        "slope_violations": slope_violations,
        "disconnected_services": disconnected_services,
        "invalid_cover_segments": invalid_cover_segments,
        "tie_in_issues": tie_in_issues,
        "service_coverage": deepcopy(service_coverage),
        "missing_service_buildings": deepcopy(missing_service_buildings),
        "disconnected_service_segments": deepcopy(disconnected_service_segments),
        "missing_manhole_points": deepcopy(safe_list(summary.get("missing_manhole_points"))),
        "storm_conflicts": deepcopy(safe_list(summary.get("storm_conflicts"))),
        "coordination_conflicts_present": bool(safe_list(summary.get("storm_conflicts"))),
        "valid": not any(
            [
                slope_violations,
                disconnected_services,
                disconnected_service_segments,
                invalid_cover_segments,
                tie_in_issues,
                missing_service_buildings,
                safe_list(summary.get("missing_manhole_points")),
            ]
        ),
    }


def _expected_sanitary_service_buildings(project: ProjectModel, summary: Dict[str, Any]) -> List[str]:
    explicit = safe_list(
        summary.get("expected_service_buildings")
        or summary.get("service_buildings")
        or summary.get("required_service_buildings")
    )
    names = [safe_str(item) for item in explicit if safe_str(item)]
    if names:
        return dedupe_keep_order(names)
    zone_names: List[str] = []
    for zone in project.zones.values():
        if getattr(zone, "zone_type", None) in {ZoneType.BUILDING, ZoneType.BUILDING_PAD}:
            zone_names.append(safe_str(getattr(zone, "name", ""), safe_str(getattr(zone, "id", ""))))
    return dedupe_keep_order([name for name in zone_names if name])


def _recompute_sanitary_service_loads(project: ProjectModel, summary: Dict[str, Any]) -> Dict[str, Any]:
    segments = [safe_dict(item) for item in safe_list(summary.get("segments"))]
    service_segments = [
        rec
        for rec in segments
        if safe_str(rec.get("segment_role")) in {"service_connection", "lateral"}
    ]
    main_segments = [rec for rec in segments if safe_str(rec.get("segment_role")) == "main"]
    node_inflow: Dict[str, float] = {}
    main_outgoing: Dict[str, List[Dict[str, Any]]] = {}
    main_incoming_count: Dict[str, int] = {}
    main_names: set[str] = set()
    disconnected_service_segments: List[Dict[str, Any]] = []
    for rec in main_segments:
        from_node = safe_str(rec.get("from") or rec.get("start_name"))
        to_node = safe_str(rec.get("to") or rec.get("end_name"))
        if from_node:
            main_outgoing.setdefault(from_node, []).append(rec)
        if to_node:
            main_incoming_count[to_node] = main_incoming_count.get(to_node, 0) + 1
        if safe_str(rec.get("name")):
            main_names.add(safe_str(rec.get("name")))
    served_buildings = dedupe_keep_order(
        [
            safe_str(rec.get("served_building"))
            for rec in service_segments
            if safe_str(rec.get("served_building")) and safe_str(rec.get("served_building")) != "shared_main"
        ]
    )
    expected_buildings = _expected_sanitary_service_buildings(project, summary)
    existing_missing = [safe_str(item) for item in safe_list(summary.get("missing_service_buildings")) if safe_str(item)]
    missing_buildings = dedupe_keep_order(
        [name for name in expected_buildings if name not in set(served_buildings)]
        + [name for name in existing_missing if name not in set(served_buildings)]
    )
    service_flow_total = round(
        sum(max(0.0, safe_float(rec.get("flow_cfs"), 0.0)) for rec in service_segments),
        6,
    )
    for rec in service_segments:
        flow = round(max(0.0, safe_float(rec.get("flow_cfs"), 0.0)), 6)
        end_node = safe_str(rec.get("to") or rec.get("end_name"))
        rec["upstream_service_flow_cfs"] = flow
        rec["post_reroute_recalculated"] = True
        if end_node and (end_node in main_outgoing or end_node in main_incoming_count or end_node in main_names):
            node_inflow[end_node] = node_inflow.get(end_node, 0.0) + flow
        elif flow > 0.0:
            disconnected_service_segments.append(
                {
                    "segment": safe_str(rec.get("name"), "SAN-SERVICE"),
                    "end_node": end_node,
                    "reason": "service_lateral_does_not_land_on_main_graph",
                }
            )

    pending_nodes = list(node_inflow.keys()) or [safe_str(rec.get("from") or rec.get("start_name")) for rec in main_segments]
    visited_edges: set[str] = set()
    iterations = 0
    max_iterations = max(len(main_segments) * 3, 1)
    while pending_nodes and iterations < max_iterations:
        iterations += 1
        node_id = pending_nodes.pop(0)
        inflow = max(0.0, node_inflow.get(node_id, 0.0))
        for rec in main_outgoing.get(node_id, []):
            seg_id = safe_str(rec.get("name") or rec.get("id") or f"main_{id(rec)}")
            to_node = safe_str(rec.get("to") or rec.get("end_name"))
            original_flow = max(0.0, safe_float(rec.get("flow_cfs"), 0.0))
            recomputed_flow = max(original_flow, inflow)
            if recomputed_flow > original_flow + 1e-9:
                rec["flow_cfs"] = round(recomputed_flow, 6)
                rec["post_reroute_flow_source"] = "upstream_service_topology"
            rec["upstream_service_flow_cfs"] = round(inflow, 6)
            rec["post_reroute_recalculated"] = True
            rec["flow_topology"] = {
                "from_node": node_id,
                "to_node": to_node,
                "incoming_service_flow_cfs": round(inflow, 6),
                "computed_segment_flow_cfs": round(recomputed_flow, 6),
            }
            edge_key = f"{seg_id}:{node_id}->{to_node}:{round(recomputed_flow, 6)}"
            if to_node and edge_key not in visited_edges:
                visited_edges.add(edge_key)
                if recomputed_flow > 0.0:
                    node_inflow[to_node] = node_inflow.get(to_node, 0.0) + recomputed_flow
                    pending_nodes.append(to_node)

    for rec in main_segments:
        if not bool(rec.get("post_reroute_recalculated")):
            rec["upstream_service_flow_cfs"] = round(max(0.0, safe_float(rec.get("flow_cfs"), 0.0)), 6)
            rec["post_reroute_recalculated"] = True
    summary["segments"] = segments
    summary["missing_service_buildings"] = missing_buildings
    summary["served_buildings"] = served_buildings
    summary["disconnected_service_segments"] = disconnected_service_segments
    summary["service_coverage"] = {
        "expected_buildings": expected_buildings,
        "served_buildings": served_buildings,
        "missing_buildings": missing_buildings,
        "expected_count": len(expected_buildings),
        "served_count": len(served_buildings),
        "valid": not missing_buildings,
        "truth_label": "Sanitary service coverage is derived from canonical service/lateral segments after reroute recomputation.",
    }
    summary["post_reroute_recalculation"] = {
        "service_flow_total_cfs": service_flow_total,
        "main_segments_recomputed": len(main_segments),
        "service_segments_recomputed": len(service_segments),
        "node_inflow_cfs": {key: round(value, 6) for key, value in sorted(node_inflow.items())},
        "disconnected_service_count": len(disconnected_service_segments),
        "truth_label": "Post-reroute sanitary recalculation propagates service lateral flow through the directed main graph before validation.",
    }
    return summary


def _recompute_storm_summary(project: ProjectModel, manager: ProjectManager) -> None:
    storm_source = safe_dict(manager.latest_outputs.get("storm_pipe_summary", project.meta.get("storm_pipe_summary", {})))
    storm = _bounded_state_copy(
        {key: value for key, value in storm_source.items() if key != "segments"},
        max_depth=5,
        max_items=220,
    )
    prior_graph_validation = _bounded_state_copy(safe_dict(storm.get("graph_validation")))
    prior_hydraulic_validation = _bounded_state_copy(safe_dict(storm.get("hydraulic_validation")))
    segments = [
        _bounded_state_copy(safe_dict(item), max_depth=4, max_items=140)
        for item in safe_list(storm_source.get("segments"))[:160]
    ]
    missing: List[Dict[str, Any]] = []
    resized_segments: List[Dict[str, Any]] = []
    total_length = 0.0
    total_capacity = 0.0
    total_flow = 0.0
    max_ratio = 0.0
    controlling: Optional[str] = None
    pipe_engine = PipeEngine(
        runoff_c=safe_float(storm.get("runoff_c"), PIPE_RUNOFF_C),
        intensity_in_hr=safe_float(storm.get("intensity_in_hr"), PIPE_INTENSITY_IN_HR),
        min_pipe_slope=PIPE_MIN_SLOPE,
        min_cover_ft=PIPE_MIN_COVER_FT,
    )
    runoff_c = safe_float(storm.get("runoff_c"), PIPE_RUNOFF_C)
    intensity_in_hr = safe_float(storm.get("intensity_in_hr"), PIPE_INTENSITY_IN_HR)
    for rec in segments:
        raw_path = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(rec.get("path") or rec.get("route_points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        path = _sample_coordination_path(raw_path, max_points=100)
        length_ft = safe_float(rec.get("length_ft"), 0.0) if len(raw_path) > len(path) else 0.0
        if length_ft <= 0.0:
            length_ft = polyline_length(path)
        rec["id"] = _summary_segment_id(rec, "storm")
        start_invert = safe_float(rec.get("start_invert"), DEFAULT_PAD_ELEV - 4.0)
        end_invert = safe_float(rec.get("end_invert"), DEFAULT_PAD_ELEV - 5.0)
        slope_ft_ft = max((start_invert - end_invert) / max(length_ft, 1e-9), 0.0)
        diameter_in = max(safe_float(rec.get("diameter_in"), 12.0), 12.0)
        flow = safe_float(rec.get("flow_cfs"), 0.0)
        if safe_float(rec.get("contributing_area_ac"), 0.0) <= 0.0 and flow > 0.0:
            rec["contributing_area_ac"] = _hydraulic_contributing_area_ac(flow, runoff_c, intensity_in_hr)
        diameter_choice = pipe_engine.choose_diameter(flow, max(slope_ft_ft, PIPE_MIN_SLOPE)) if flow > 0.0 else int(round(diameter_in))
        if diameter_choice > diameter_in + 1e-6:
            rec["diameter_in"] = float(diameter_choice)
            diameter_in = float(diameter_choice)
            resized_segments.append({"pipe": safe_str(rec.get("pipe"), safe_str(rec.get("name"), "PIPE")), "new_diameter_in": diameter_in, "reason": "post_reroute_capacity_check"})
        capacity = _manning_full_capacity_cfs(diameter_in, slope_ft_ft)
        ratio = flow / max(capacity, 1e-9) if capacity > 0.0 else 0.0
        rec["length_ft"] = round(length_ft, 1)
        rec["slope_pct"] = round(slope_ft_ft * 100.0, 3)
        rec["slope_ft_ft"] = round(slope_ft_ft, 5)
        rec["capacity_cfs"] = round(capacity, 3)
        rec["capacity_ratio"] = round(ratio, 3)
        missing_fields: List[str] = []
        for key in ("from", "to"):
            if not safe_str(rec.get(key)):
                missing_fields.append(key)
        for key in ("flow_cfs", "capacity_cfs", "slope_ft_ft", "contributing_area_ac"):
            if safe_float(rec.get(key), 0.0) <= 0.0:
                missing_fields.append(key)
        if "cover_start_ft" in rec and safe_float(rec.get("cover_start_ft"), 0.0) <= 0.0:
            missing_fields.append("cover_start_ft")
        if "cover_end_ft" in rec and safe_float(rec.get("cover_end_ft"), 0.0) <= 0.0:
            missing_fields.append("cover_end_ft")
        if missing_fields:
            missing.append(
                {
                    "segment": safe_str(rec.get("pipe"), safe_str(rec.get("name"), "PIPE")),
                    "missing_fields": dedupe_keep_order(missing_fields),
                }
            )
        total_length += length_ft
        total_capacity += capacity
        total_flow += flow
        if ratio >= max_ratio:
            max_ratio = ratio
            controlling = safe_str(rec.get("pipe"), safe_str(rec.get("name"), "PIPE"))
    storm["segments"] = segments
    storm["pipe_count"] = len(segments)
    storm["total_length_ft"] = round(total_length, 3)
    storm["total_system_flow_cfs"] = round(total_flow, 3)
    storm["total_system_capacity_cfs"] = round(total_capacity, 3)
    storm["controlling_segment"] = controlling
    storm["max_capacity_ratio"] = round(max_ratio, 3)
    storm["missing_data_segments"] = missing
    storm["hydraulic_source"] = safe_str(storm.get("hydraulic_source")) or (
        "fallback" if lower_text(storm.get("source")) in {"surface_fallback", "fallback", "synthesized"} else "engine"
    )
    storm["source_detail"] = safe_str(storm.get("source_detail")) or (
        "surface_fallback" if storm["hydraulic_source"] == "fallback" else "storm_network_engine+hydraulic_engine"
    )
    storm["pipe_slope_invert_consistency"] = all(safe_float(rec.get("slope_pct"), 0.0) > 0.0 for rec in segments)
    storm["resized_segments"] = resized_segments
    drainage = safe_dict(project.meta.get("drainage_canonical"))
    storm = _enrich_storm_production_depth(storm, drainage)
    storm["graph_validation"] = _merge_validation_payload(
        _validate_network_graph(
            {
                "segments": segments,
                "nodes": safe_list(storm.get("nodes")),
            },
            "storm",
        ),
        prior_graph_validation,
        [
            "disconnected_runs",
            "loop_nodes",
            "duplicate_segments",
            "duplicate_edges",
            "invalid_direction_segments",
            "illegal_branch_nodes",
            "orphan_nodes",
            "unreasonable_degree_nodes",
        ],
    )
    storm["hydraulic_validation"] = _merge_validation_payload(
        _validate_storm_hydraulics(storm),
        prior_hydraulic_validation,
        [
            "geometry_only_segments",
            "missing_accumulation_segments",
            "invalid_capacity_ratio_segments",
            "downstream_total_inconsistencies",
            "backwater_failures",
            "surcharge_failures",
        ],
    )
    storm["success"] = bool(storm["graph_validation"].get("valid")) and bool(storm["hydraulic_validation"].get("valid"))
    manager.latest_outputs["storm_pipe_summary"] = _bounded_state_copy(storm, max_depth=6, max_items=260)
    project.meta["storm_pipe_summary"] = _bounded_state_copy(storm, max_depth=6, max_items=260)
    if drainage:
        export_validation = _drainage_export_validation(
            project,
            drainage_override=drainage,
            storm_override=storm,
        )
        _sync_drainage_mutable_state(project, manager, export_validation=export_validation)
    manager.set_metric("storm_pipe_count", len(segments), category="pipes")
    manager.set_metric("storm_pipe_length_ft", total_length, units="ft", category="pipes")
    manager.set_metric("pipe_capacity_total_cfs", total_capacity, units="cfs", category="pipes")


def _ensure_sanitary_structure_spacing(
    segments: Sequence[Dict[str, Any]],
    manholes: Sequence[Dict[str, Any]],
    *,
    max_spacing_ft: float,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    updated_segments = [deepcopy(safe_dict(item)) for item in segments]
    updated_manholes = [deepcopy(safe_dict(item)) for item in manholes if safe_dict(item)]
    existing_points = {
        _point_key([safe_float(item.get("x"), 0.0), safe_float(item.get("y"), 0.0)])
        for item in updated_manholes
    }
    inserted: List[Dict[str, Any]] = []
    for rec in updated_segments:
        role = safe_str(rec.get("segment_role")).lower()
        if role not in {"main", "trunk", "collector", ""}:
            continue
        path = _dedupe_path_points(safe_list(rec.get("route_points")))
        if len(path) < 2:
            continue
        points = _support_structure_points_for_path(path, max_spacing_ft)
        new_points: List[List[float]] = []
        for point in points:
            key = _point_key(point)
            if key in existing_points:
                continue
            name = f"SMH-{len(updated_manholes) + 1}"
            row = {
                "name": name,
                "id": name,
                "node_id": name,
                "x": key[0],
                "y": key[1],
                "reason": "sanitary_structure_spacing",
                "source": "generated_from_canonical_route",
                "max_spacing_ft": round(max_spacing_ft, 3),
                "segment": safe_str(rec.get("name"), "SAN"),
            }
            updated_manholes.append(row)
            inserted.append(row)
            existing_points.add(key)
            new_points.append([key[0], key[1]])
        if new_points:
            rec["route_points"] = _insert_points_into_path(path, new_points)
            rec["structure_spacing_audit"] = {
                "generated_manhole_count": len(new_points),
                "max_spacing_ft": round(max_spacing_ft, 3),
                "reason": "main_route_spacing_and_bends",
            }
    return updated_segments, updated_manholes, {
        "valid": True,
        "max_spacing_ft": round(max_spacing_ft, 3),
        "generated_manhole_count": len(inserted),
        "generated_manholes": deepcopy(inserted),
        "truth_label": "Sanitary manholes are generated from canonical main route bends and spacing points.",
    }


def _ensure_water_hydrant_spacing(
    summary: Dict[str, Any],
    segments: Sequence[Dict[str, Any]],
    *,
    max_spacing_ft: float,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    enriched = deepcopy(safe_dict(summary))
    hydrants = [deepcopy(safe_dict(item)) for item in safe_list(enriched.get("hydrants") or enriched.get("fire_hydrants")) if safe_dict(item)]
    existing_points = {
        _point_key([safe_float(item.get("x"), 0.0), safe_float(item.get("y"), 0.0)])
        for item in hydrants
    }
    inserted: List[Dict[str, Any]] = []
    for rec in segments:
        system = safe_str(rec.get("system_type") or rec.get("system")).lower()
        role = safe_str(rec.get("segment_role") or rec.get("role")).lower()
        if system and system != "water":
            continue
        if role and role not in {"main", "loop", "transmission", "primary"}:
            continue
        path = _dedupe_path_points(safe_list(rec.get("route_points")))
        if len(path) < 2:
            continue
        for point in _support_structure_points_for_path(path, max_spacing_ft):
            key = _point_key(point)
            if key in existing_points:
                continue
            name = f"HYD-{len(hydrants) + 1}"
            row = {
                "name": name,
                "id": name,
                "x": key[0],
                "y": key[1],
                "reason": "water_hydrant_spacing",
                "source": "generated_from_canonical_water_main",
                "max_spacing_ft": round(max_spacing_ft, 3),
                "segment": safe_str(rec.get("name"), "WATER"),
            }
            hydrants.append(row)
            inserted.append(row)
            existing_points.add(key)
    if hydrants:
        enriched["hydrants"] = hydrants
        enriched["fire_hydrants"] = hydrants
    return enriched, {
        "max_spacing_ft": round(max_spacing_ft, 3),
        "generated_hydrant_count": len(inserted),
        "hydrant_count": len(hydrants),
        "generated_hydrants": deepcopy(inserted),
        "truth_label": "Water hydrants are generated from canonical water-main geometry for spacing validation; jurisdiction approval is still required.",
    }


def _recompute_sanitary_summary(project: ProjectModel, manager: ProjectManager, *, prefer_cache: bool = False) -> None:
    summary = (
        deepcopy(safe_dict(manager.latest_outputs.get("sanitary", project.meta.get("sanitary_summary", {}))))
        if prefer_cache
        else deepcopy(safe_dict(canonical_stage_output(project, manager, "sanitary")))
    )
    grading = (
        safe_dict(manager.latest_outputs.get("grading", project.meta.get("grading_summary", {})))
        if prefer_cache
        else safe_dict(canonical_stage_output(project, manager, "grading"))
    )
    proposed_surface = grading.get("proposed_surface")
    summary = _recompute_sanitary_service_loads(project, summary)
    standards = standards_from_meta(project.meta)
    segments = []
    corridor_audits: List[Dict[str, Any]] = []
    for item in safe_list(summary.get("segments")):
        routed, audit = _maybe_prefer_corridor_route(project, safe_dict(item))
        source_missing_fields: List[str] = []
        if not safe_str(routed.get("start_name") or routed.get("from")):
            source_missing_fields.append("start_name")
        if not safe_str(routed.get("end_name") or routed.get("to")):
            source_missing_fields.append("end_name")
        if routed.get("start_invert_ft") is None:
            source_missing_fields.append("start_invert_ft")
        if routed.get("end_invert_ft") is None:
            source_missing_fields.append("end_invert_ft")
        if routed.get("diameter_in") is None:
            source_missing_fields.append("diameter_in")
        if source_missing_fields:
            routed["_source_missing_fields"] = dedupe_keep_order(source_missing_fields)
        if audit:
            corridor_audits.append({"segment": safe_str(routed.get("name"), "SAN"), **audit})
        segments.append(routed)
    slope_violations: List[Dict[str, Any]] = []
    resized_segments: List[Dict[str, Any]] = []
    missing_data_segments: List[Dict[str, Any]] = []
    total_length = 0.0
    total_capacity = 0.0
    main_length = 0.0
    lateral_length = 0.0
    service_length = 0.0
    max_ratio = 0.0
    controlling: Optional[str] = None
    for rec in segments:
        path = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(rec.get("route_points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        if len(path) < 2:
            missing_data_segments.append(
                {
                    "segment": safe_str(rec.get("name"), "SAN"),
                    "missing_fields": ["route_points"],
                }
            )
            continue
        length_ft = polyline_length(path)
        start_invert = safe_float(rec.get("start_invert_ft"), DEFAULT_PAD_ELEV - 5.0)
        end_invert = safe_float(rec.get("end_invert_ft"), DEFAULT_PAD_ELEV - 6.0)
        slope_ft_ft = max((start_invert - end_invert) / max(length_ft, 1e-9), 0.0)
        rec["length_ft"] = round(length_ft, 3)
        rec["slope_ft_ft"] = round(slope_ft_ft, 5)
        role = safe_str(rec.get("segment_role"), "")
        min_slope = _sanitary_min_slope(role, safe_float(rec.get("diameter_in"), 8.0))
        if slope_ft_ft + 1e-6 < min_slope:
            slope_violations.append({"segment": safe_str(rec.get("name")), "required_min_slope": round(min_slope, 5), "actual_slope": round(slope_ft_ft, 5)})
        flow_cfs = safe_float(rec.get("flow_cfs"), 0.0)
        capacity_cfs = _manning_full_capacity_cfs(safe_float(rec.get("diameter_in"), 8.0), max(slope_ft_ft, min_slope))
        if flow_cfs > 0.0 and flow_cfs > capacity_cfs * 0.95:
            upgraded = max(8.0, safe_float(rec.get("diameter_in"), 8.0) + 2.0)
            rec["diameter_in"] = upgraded
            capacity_cfs = _manning_full_capacity_cfs(upgraded, max(slope_ft_ft, min_slope))
            resized_segments.append({"segment": safe_str(rec.get("name")), "new_diameter_in": upgraded, "reason": "post_reroute_capacity_check"})
        rec["capacity_cfs"] = round(capacity_cfs, 3)
        rec["capacity_ratio"] = round(flow_cfs / max(capacity_cfs, 1e-9), 3) if flow_cfs > 0.0 else 0.0
        total_length += length_ft
        total_capacity += capacity_cfs
        if safe_float(rec.get("capacity_ratio"), 0.0) >= max_ratio:
            max_ratio = safe_float(rec.get("capacity_ratio"), 0.0)
            controlling = safe_str(rec.get("name"), "SAN")
        if role == "main":
            main_length += length_ft
        elif role == "lateral":
            lateral_length += length_ft
        elif role == "service_connection":
            service_length += length_ft
        if proposed_surface is not None and path:
            rec["cover_start_ft"] = round(_sample_grid_surface(proposed_surface, path[0][0], path[0][1], DEFAULT_PAD_ELEV) - start_invert, 3)
            rec["cover_end_ft"] = round(_sample_grid_surface(proposed_surface, path[-1][0], path[-1][1], DEFAULT_PAD_ELEV) - end_invert, 3)
    repairs = _repair_sanitary_segment_covers(segments, proposed_surface)
    segments, generated_manholes, structure_spacing = _ensure_sanitary_structure_spacing(
        segments,
        safe_list(summary.get("manholes")),
        max_spacing_ft=safe_float(standards.max_sanitary_manhole_spacing_ft, 400.0),
    )
    segments, manholes, nodes = _bind_sanitary_graph_nodes(segments, generated_manholes)
    referenced_node_ids = {
        safe_str(node_id)
        for rec in segments
        for node_id in safe_list(rec.get("node_ids"))
        if safe_str(node_id)
    }
    filtered_manholes = [
        deepcopy(safe_dict(item))
        for item in manholes
        if safe_str(safe_dict(item).get("node_id") or safe_dict(item).get("id")) in referenced_node_ids
    ]
    if len(filtered_manholes) != len(manholes):
        segments, manholes, nodes = _bind_sanitary_graph_nodes(segments, filtered_manholes)
    for rec in segments:
        missing_fields: List[str] = []
        for key in ("start_name", "end_name"):
            if not safe_str(rec.get(key)):
                missing_fields.append(key)
        missing_fields.extend(safe_str(item) for item in safe_list(rec.get("_source_missing_fields")) if safe_str(item))
        for key in ("length_ft", "slope_ft_ft", "capacity_cfs"):
            if safe_float(rec.get(key), 0.0) <= 0.0:
                missing_fields.append(key)
        if "cover_start_ft" in rec and safe_float(rec.get("cover_start_ft"), 0.0) <= 0.0:
            missing_fields.append("cover_start_ft")
        if "cover_end_ft" in rec and safe_float(rec.get("cover_end_ft"), 0.0) <= 0.0:
            missing_fields.append("cover_end_ft")
        if missing_fields:
            missing_data_segments.append(
                {
                    "segment": safe_str(rec.get("name"), "SAN"),
                    "missing_fields": dedupe_keep_order(missing_fields),
                }
            )
    summary["segments"] = segments
    summary["manholes"] = manholes
    summary["nodes"] = nodes
    summary["slope_violations"] = slope_violations
    summary["total_length_ft"] = round(total_length, 3)
    summary["main_length_ft"] = round(main_length, 3)
    summary["lateral_length_ft"] = round(lateral_length, 3)
    summary["service_connection_length_ft"] = round(service_length, 3)
    summary["manhole_count"] = len(manholes)
    summary["total_system_capacity_cfs"] = round(total_capacity, 3)
    summary["max_capacity_ratio"] = round(max_ratio, 3)
    summary["controlling_segment"] = controlling
    summary["missing_data_segments"] = missing_data_segments
    summary["stats"] = {
        **safe_dict(summary.get("stats")),
        "segment_count": len(segments),
        "route_count": len(segments),
        "total_length_ft": round(total_length, 3),
        "main_length_ft": round(main_length, 3),
        "lateral_length_ft": round(lateral_length, 3),
        "service_connection_length_ft": round(service_length, 3),
        "manhole_count": len(manholes),
        "total_system_capacity_cfs": round(total_capacity, 3),
        "max_capacity_ratio": round(max_ratio, 3),
        "storm_conflict_count": len(safe_list(summary.get("storm_conflicts"))),
    }
    summary["resized_segments"] = resized_segments
    summary["cover_repairs"] = repairs
    summary["corridor_routing_audit"] = corridor_audits
    summary["structure_spacing_validation"] = structure_spacing
    summary["graph_validation"] = _validate_network_graph(summary, "sanitary")
    summary["network_validation"] = _validate_sanitary_network(summary)
    summary["disconnected_segments"] = deepcopy(safe_list(safe_dict(summary["network_validation"]).get("disconnected_services")))
    summary["success"] = bool(summary["graph_validation"].get("valid")) and bool(summary["network_validation"].get("valid"))
    manager.latest_outputs["sanitary"] = deepcopy(summary)
    project.meta["sanitary_summary"] = deepcopy(summary)
    manager.set_metric("sanitary_total_length_ft", total_length, units="ft", category="sanitary")
    manager.set_metric("sanitary_main_length_ft", main_length, units="ft", category="sanitary")
    manager.set_metric("sanitary_lateral_length_ft", lateral_length, units="ft", category="sanitary")
    manager.set_metric("sanitary_service_connection_length_ft", service_length, units="ft", category="sanitary")


def _recompute_utility_summary(project: ProjectModel, manager: ProjectManager, *, prefer_cache: bool = False) -> None:
    summary = (
        deepcopy(safe_dict(manager.latest_outputs.get("utilities", project.meta.get("utility_summary", {}))))
        if prefer_cache
        else deepcopy(safe_dict(canonical_stage_output(project, manager, "utilities")))
    )
    hooks = safe_dict(summary.get("conflict_hooks"))
    standards = standards_from_meta(project.meta)
    segments: List[Dict[str, Any]] = []
    corridor_audits: List[Dict[str, Any]] = []
    for item in safe_list(hooks.get("utility_segments")):
        routed, audit = _maybe_prefer_corridor_route(project, safe_dict(item))
        if audit:
            corridor_audits.append({"segment": safe_str(routed.get("name"), "UTILITY"), **audit})
        segments.append(routed)
    total_length = 0.0
    for rec in segments:
        path = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(rec.get("route_points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        total_length += polyline_length(path)
    summary["route_count"] = len(segments)
    summary["total_length_ft"] = round(total_length, 3)
    hooks["utility_segments"] = segments
    summary["conflict_hooks"] = hooks
    summary["corridor_routing_audit"] = corridor_audits
    summary, hydrant_spacing_generation = _ensure_water_hydrant_spacing(
        summary,
        segments,
        max_spacing_ft=safe_float(standards.max_hydrant_spacing_ft, 500.0),
    )
    summary["hydrant_spacing_generation"] = hydrant_spacing_generation
    summary = _enrich_utility_summary_with_coordination(summary, project, manager)
    summary["export_validation"] = _utility_export_validation(project, utilities_override=summary)
    manager.latest_outputs["utilities"] = deepcopy(summary)
    project.meta["utility_summary"] = deepcopy(summary)
    manager.set_metric("utility_route_count", len(segments), category="utilities")
    manager.set_metric("utility_total_length_ft", total_length, units="ft", category="utilities")


def _insert_support_structure(project: ProjectModel, manager: ProjectManager, system_name: str, segment_name: str, point: Sequence[float], reason: str) -> int:
    x = round(safe_float(point[0], 0.0), 3)
    y = round(safe_float(point[1], 0.0), 3)
    if system_name == "sanitary":
        summary = safe_dict(manager.latest_outputs.get("sanitary", project.meta.get("sanitary_summary", {})))
        manholes = safe_list(summary.get("manholes"))
        if any(abs(safe_float(item.get("x"), 0.0) - x) <= 0.25 and abs(safe_float(item.get("y"), 0.0) - y) <= 0.25 for item in manholes):
            return 0
        manholes.append({"name": f"SMH-{len(manholes)+1}", "x": x, "y": y, "reason": reason})
        summary["manholes"] = manholes
        summary["manhole_count"] = len(manholes)
        manager.latest_outputs["sanitary"] = deepcopy(summary)
        project.meta["sanitary_summary"] = deepcopy(summary)
        return 1
    if system_name == "storm":
        drainage = safe_dict(manager.latest_outputs.get("drainage", project.meta.get("drainage_canonical", {})))
        structures = safe_list(drainage.get("structures"))
        if any(abs(safe_float(item.get("x"), 0.0) - x) <= 0.25 and abs(safe_float(item.get("y"), 0.0) - y) <= 0.25 for item in structures):
            return 0
        structures.append({"name": f"JB-{len(structures)+1}", "object_type": "structure", "structure_type": "junction_box", "canonical_type": "junction_box", "layer": "DRAIN", "x": x, "y": y, "z": DEFAULT_PAD_ELEV, "reason": reason})
        drainage_stats = safe_dict(drainage.get("stats"))
        drainage_stats["structure_count"] = len(structures)
        _sync_drainage_mutable_state(project, manager, structures=structures, stats=drainage_stats)
        return 1
    if system_name in {"water", "utilities"}:
        utilities = safe_dict(manager.latest_outputs.get("utilities", project.meta.get("utility_summary", {})))
        jboxes = safe_list(utilities.get("structures"))
        if any(abs(safe_float(item.get("x"), 0.0) - x) <= 0.25 and abs(safe_float(item.get("y"), 0.0) - y) <= 0.25 for item in jboxes):
            return 0
        jboxes.append({"name": f"UBOX-{len(jboxes)+1}", "object_type": "junction_box", "x": x, "y": y, "reason": reason})
        utilities["structures"] = jboxes
        manager.latest_outputs["utilities"] = _bounded_state_copy(utilities)
        project.meta["utility_summary"] = _bounded_state_copy(utilities)
        return 1
    return 0


def _apply_local_grading_repair(project: ProjectModel, target_name: str, *, delta_depth_ft: float = 0.0, point: Optional[Sequence[float]] = None) -> Dict[str, Any]:
    location = [round(safe_float(point[0], 0.0), 3), round(safe_float(point[1], 0.0), 3)] if isinstance(point, (list, tuple)) and len(point) >= 2 else None
    nearby_zones: List[Dict[str, Any]] = []
    zone_kinds: List[str] = []
    if location is not None:
        for rect in _expanded_obstacle_rectangles(project):
            probe = {
                **rect,
                "buffer_ft": safe_float(rect.get("buffer_ft"), 0.0) + 8.0,
            }
            if _point_inside_buffered_rect(location, probe):
                nearby_zones.append(
                    {
                        "kind": safe_str(rect.get("kind")),
                        "name": safe_str(rect.get("name")),
                        "penalty": safe_float(rect.get("penalty"), 0.0),
                    }
                )
                zone_kinds.append(safe_str(rect.get("kind")))
    recomputed_outputs = ["spot_grades", "flow_arrows", "local_contours", "earthwork_delta"]
    repair_modes: List[str] = []
    if "roadway" in zone_kinds or "fire_lane" in zone_kinds:
        repair_modes.extend(["road_edge_transition", "pavement_transition"])
        recomputed_outputs.extend(["road_edge_grades", "gutter_flow", "driveway_tie_in"])
    if "building_pad" in zone_kinds:
        repair_modes.append("pad_tie_in")
        recomputed_outputs.extend(["pad_tie_slopes", "corner_grade_breaklines"])
    if "ada_path" in zone_kinds or "access_aisle" in zone_kinds:
        repair_modes.append("ada_path_repair")
        recomputed_outputs.extend(["ada_walk_slopes", "accessible_landings"])
    if "retaining_sensitive" in zone_kinds:
        repair_modes.append("retaining_sensitive_transition")
        recomputed_outputs.extend(["retaining_transition", "embankment_check"])
    if any(kind in {"wetland", "floodplain", "tree_save", "row_conflict", "construction_access"} for kind in zone_kinds):
        repair_modes.append("protected_zone_grading_avoidance")
        recomputed_outputs.extend(["constraint_buffer_tie_in", "access_constructability_check"])
    recomputed_outputs = dedupe_keep_order(recomputed_outputs)
    disturbance_weight = 1.0 + sum(safe_float(item.get("penalty"), 0.0) for item in nearby_zones) / 250.0
    note = {
        "type": "local_grading_repair",
        "target": safe_str(target_name),
        "delta_depth_ft": round(delta_depth_ft, 3),
        "location": location,
        "recomputed_outputs": recomputed_outputs,
        "repair_modes": repair_modes or ["local_surface_adjustment"],
        "protected_zone_context": nearby_zones,
        "disturbance_class": "high" if any(kind in {"roadway"} or kind in HARD_PROTECTED_ZONE_KINDS for kind in zone_kinds) else ("moderate" if zone_kinds else "standard"),
        "cut_fill_delta_cf": round(abs(delta_depth_ft) * 18.0 * disturbance_weight, 3),
    }
    _add_grading_adjustment(project, note)
    return note


def _validate_network_graph(summary: Dict[str, Any], system_name: str) -> Dict[str, Any]:
    segments = [safe_dict(item) for item in safe_list(summary.get("segments")) if safe_dict(item)]
    graph: Dict[str, set[str]] = {}
    in_degree: Dict[str, int] = {}
    out_degree: Dict[str, int] = {}
    referenced_nodes: set[str] = set()
    duplicate_segments: List[str] = []
    duplicate_edges: List[Dict[str, Any]] = []
    invalid_direction_segments: List[Dict[str, Any]] = []
    illegal_branch_nodes: List[Dict[str, Any]] = []
    unreasonable_degree_nodes: List[Dict[str, Any]] = []
    orphan_nodes: List[str] = []
    explicit_nodes: set[str] = set()
    explicit_node_types: Dict[str, str] = {}
    seen_segment_ids: set[str] = set()
    seen_edges: set[Tuple[str, str, str]] = set()
    for node in safe_list(summary.get("nodes")):
        rec = safe_dict(node)
        node_id = safe_str(rec.get("node_id") or rec.get("id"), safe_str(rec.get("name")))
        if node_id:
            explicit_nodes.add(node_id)
            explicit_node_types[node_id] = safe_str(rec.get("node_type"))
    for node in safe_list(summary.get("manholes")):
        rec = safe_dict(node)
        node_id = safe_str(rec.get("node_id") or rec.get("id"), safe_str(rec.get("name")))
        if node_id:
            explicit_nodes.add(node_id)
            explicit_node_types[node_id] = safe_str(rec.get("node_type"), "sanitary_manhole")
    for node in safe_list(summary.get("structures")):
        rec = safe_dict(node)
        node_id = safe_str(rec.get("node_id") or rec.get("id"), safe_str(rec.get("name")))
        if node_id:
            explicit_nodes.add(node_id)
            explicit_node_types[node_id] = safe_str(rec.get("node_type"), safe_str(rec.get("structure_type")))
    for seg in segments:
        seg_id = _summary_segment_id(seg, system_name)
        if seg_id in seen_segment_ids:
            duplicate_segments.append(seg_id)
        seen_segment_ids.add(seg_id)
        node_chain = [safe_str(item) for item in safe_list(seg.get("node_ids")) if safe_str(item)]
        if len(node_chain) < 2:
            start = safe_str(seg.get("from") or seg.get("start_name"))
            end = safe_str(seg.get("to") or seg.get("end_name"))
            node_chain = [item for item in [start, end] if item]
        if len(node_chain) < 2:
            continue
        referenced_nodes.update(node_chain)
        start = node_chain[0]
        end = node_chain[-1]
        for edge_index, (edge_start, edge_end) in enumerate(zip(node_chain, node_chain[1:]), start=1):
            graph.setdefault(edge_start, set()).add(edge_end)
            graph.setdefault(edge_end, set())
            in_degree[edge_end] = in_degree.get(edge_end, 0) + 1
            in_degree.setdefault(edge_start, in_degree.get(edge_start, 0))
            out_degree[edge_start] = out_degree.get(edge_start, 0) + 1
            out_degree.setdefault(edge_end, out_degree.get(edge_end, 0))
            edge_key = (edge_start, edge_end, safe_str(seg.get("segment_role")))
            if edge_key in seen_edges:
                duplicate_edges.append({"segment_id": seg_id, "edge_index": edge_index, "start_node": edge_start, "end_node": edge_end})
            seen_edges.add(edge_key)
        slope = safe_float(seg.get("slope_ft_ft"), safe_float(seg.get("slope_pct"), 0.0) / 100.0)
        start_invert = safe_float(seg.get("start_invert_ft", seg.get("start_invert")), DEFAULT_PAD_ELEV - 4.0)
        end_invert = safe_float(seg.get("end_invert_ft", seg.get("end_invert")), DEFAULT_PAD_ELEV - 5.0)
        if start == end or slope <= 0.0 or start_invert <= end_invert:
            invalid_direction_segments.append(
                {
                    "segment_id": seg_id,
                    "start_node": start,
                    "end_node": end,
                    "start_invert_ft": round(start_invert, 3),
                    "end_invert_ft": round(end_invert, 3),
                    "slope_ft_ft": round(slope, 5),
                }
            )
    disconnected = [
        safe_str(seg.get("name") or seg.get("pipe"))
        for seg in segments
        if len([safe_str(item) for item in safe_list(seg.get("node_ids")) if safe_str(item)]) < 2
        and (not safe_str(seg.get("from") or seg.get("start_name")) or not safe_str(seg.get("to") or seg.get("end_name")))
    ]
    loops: List[Dict[str, Any]] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: List[str] = []

    def _dfs(node: str) -> None:
        visiting.add(node)
        stack.append(node)
        for downstream in sorted(graph.get(node, set())):
            if downstream in visiting:
                cycle_start = stack.index(downstream) if downstream in stack else 0
                loops.append({"node_id": downstream, "cycle_path": stack[cycle_start:] + [downstream]})
            elif downstream not in visited:
                _dfs(downstream)
        stack.pop()
        visiting.discard(node)
        visited.add(node)

    for node in sorted(graph.keys()):
        if node not in visited:
            _dfs(node)

    branch_limit = 1 if system_name in {"storm", "sanitary"} else 2
    max_total_degree = 4 if system_name == "sanitary" else 6 if system_name == "storm" else 8
    for node in sorted(set(graph.keys()) | explicit_nodes):
        indeg = in_degree.get(node, 0)
        outdeg = out_degree.get(node, 0)
        node_type = safe_str(explicit_node_types.get(node))
        if outdeg > branch_limit:
            illegal_branch_nodes.append({"node_id": node, "out_degree": outdeg, "allowed_out_degree": branch_limit})
        allowed_total_degree = max_total_degree
        if system_name == "storm" and node_type in {"junction", "basin_connection", "outfall"}:
            allowed_total_degree = 12
        if indeg + outdeg > allowed_total_degree:
            unreasonable_degree_nodes.append({"node_id": node, "total_degree": indeg + outdeg, "allowed_total_degree": allowed_total_degree})
    orphan_nodes = sorted(node for node in explicit_nodes if node not in referenced_nodes)
    return {
        "system": system_name,
        "segment_count": len(segments),
        "node_count": len(graph),
        "disconnected_runs": disconnected,
        "loop_nodes": deepcopy(loops),
        "duplicate_segments": duplicate_segments,
        "duplicate_edges": duplicate_edges,
        "invalid_direction_segments": invalid_direction_segments,
        "illegal_branch_nodes": illegal_branch_nodes,
        "orphan_nodes": orphan_nodes,
        "unreasonable_degree_nodes": unreasonable_degree_nodes,
        "valid": not any(
            [
                disconnected,
                loops,
                duplicate_segments,
                duplicate_edges,
                invalid_direction_segments,
                illegal_branch_nodes,
                orphan_nodes,
                unreasonable_degree_nodes,
            ]
        ),
    }


def _post_reroute_validations(project: ProjectModel, manager: ProjectManager, changed_systems: Sequence[str]) -> Dict[str, Any]:
    validations: Dict[str, Any] = {"valid": True, "systems": {}, "consistency": {}}
    changed = {safe_str(item) for item in changed_systems if safe_str(item)}
    if "storm" in changed:
        storm = safe_dict(manager.latest_outputs.get("storm_pipe_summary", project.meta.get("storm_pipe_summary", {})))
        storm_graph = _validate_network_graph(storm, "storm")
        storm_hydraulic = _validate_storm_hydraulics(storm)
        validations["systems"]["storm"] = storm_graph
        validations["systems"]["storm_hydraulics"] = storm_hydraulic
        validations["valid"] = validations["valid"] and bool(storm_graph.get("valid")) and bool(storm_hydraulic.get("valid")) and not safe_list(storm.get("missing_data_segments"))
    if "sanitary" in changed:
        sanitary = safe_dict(manager.latest_outputs.get("sanitary", project.meta.get("sanitary_summary", {})))
        sanitary_graph = _validate_network_graph(sanitary, "sanitary")
        sanitary_network = _validate_sanitary_network(sanitary)
        validations["systems"]["sanitary"] = sanitary_graph
        validations["systems"]["sanitary_network"] = sanitary_network
        validations["valid"] = validations["valid"] and bool(sanitary_graph.get("valid")) and bool(sanitary_network.get("valid")) and not safe_list(sanitary.get("slope_violations"))
    if "utilities" in changed or "water" in changed:
        utilities = safe_dict(manager.latest_outputs.get("utilities", project.meta.get("utility_summary", {})))
        hooks = safe_dict(utilities.get("conflict_hooks"))
        utility_segments = safe_list(hooks.get("utility_segments"))
        validations["systems"]["utilities"] = {
            "valid": bool(utility_segments),
            "segment_count": len(utility_segments),
            "service_assignment_complete": all(safe_list(safe_dict(seg).get("route_points")) for seg in utility_segments),
        }
        validations["valid"] = validations["valid"] and bool(validations["systems"]["utilities"]["valid"])
    consistency: Dict[str, bool] = {}
    if "storm" in changed:
        consistency["storm_summary_current"] = safe_dict(manager.latest_outputs.get("storm_pipe_summary", {})) == safe_dict(project.meta.get("storm_pipe_summary", {}))
    if "sanitary" in changed:
        consistency["sanitary_summary_current"] = safe_dict(manager.latest_outputs.get("sanitary", {})) == safe_dict(project.meta.get("sanitary_summary", {}))
    if "utilities" in changed or "water" in changed:
        consistency["utility_summary_current"] = safe_dict(manager.latest_outputs.get("utilities", {})) == safe_dict(project.meta.get("utility_summary", {}))
    if "drainage" in changed:
        consistency["drainage_summary_current"] = safe_dict(manager.latest_outputs.get("drainage", {})) == safe_dict(project.meta.get("drainage_canonical", {}))
    validations["consistency"] = consistency
    validations["valid"] = validations["valid"] and all(bool(flag) for flag in validations["consistency"].values())
    return validations


def _conflict_cluster_id(conflict: Dict[str, Any]) -> str:
    rec = safe_dict(conflict)
    objects = "-".join(sorted(safe_str(item) for item in safe_list(rec.get("involved_objects")) if safe_str(item)))
    return f"cluster::{safe_str(rec.get('conflict_type'), 'conflict')}::{objects or 'unknown'}"


def _apply_conflict_resolution(
    project: ProjectModel,
    manager: ProjectManager,
    conflict: Dict[str, Any],
    assisted_mode: bool,
    *,
    candidate_mode: str = "balanced",
    cluster_context: Optional[Dict[str, Any]] = None,
    crossing_strategy: str = "",
    metrics: Optional[Dict[str, Any]] = None,
    structure_analysis_cache: Optional[Dict[Tuple[str, str, Tuple[Tuple[float, float], ...]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    started = perf_counter()
    resolution = {
        "success": False,
        "assumed": False,
        "strategy": None,
        "notes": [],
        "changed_systems": [],
        "constructability": {},
        "engineering_deltas": {},
        "best_near_valid_candidate": None,
        "failure_reason": "",
        "evaluated_candidates": [],
    }
    conflict_type = safe_str(conflict.get("conflict_type"))
    names = [safe_str(name) for name in safe_list(conflict.get("involved_objects")) if safe_str(name)]
    if not names:
        return resolution

    base_snapshot = _snapshot_coordination_state(project, manager)
    base_full_snapshot = _full_coordination_state_snapshot(project, manager)
    pre_all = _detect_coordination_conflicts(project, manager)
    pre_related = _matching_conflicts(pre_all, conflict)
    protected_zones = _expanded_obstacle_rectangles(project)
    best_snapshot: Optional[Dict[str, Any]] = None
    best_full_snapshot: Optional[Dict[str, Any]] = None
    best_choice: Optional[Dict[str, Any]] = None
    best_near_valid: Optional[Dict[str, Any]] = None
    evaluated_candidates: List[Dict[str, Any]] = []

    def _finalize_candidate(
        *,
        strategy: str,
        target_name: str,
        changed_systems: Sequence[str],
        before_path: Optional[Sequence[Sequence[float]]] = None,
        after_path: Optional[Sequence[Sequence[float]]] = None,
        added_structures: int = 0,
        notes: Optional[List[str]] = None,
        preference: Optional[Dict[str, Any]] = None,
        extra_penalty: float = 0.0,
        why_failed: str = "",
        grading_note: Optional[Dict[str, Any]] = None,
        ignored_zone_names: Sequence[str] = (),
        source_mode: str = "",
    ) -> Dict[str, Any]:
        _refresh_conflict_resolved_state(project, manager, changed_systems)
        post_all = _detect_coordination_conflicts(project, manager)
        post_related = _matching_conflicts(post_all, conflict)
        validations = _post_reroute_validations(project, manager, changed_systems)
        protected_penalty = _path_protected_zone_penalty(after_path or before_path or [], protected_zones)
        ownership_class = _segment_ownership_class({"system": safe_str(changed_systems[0]) if changed_systems else "", "segment_role": "main"})
        grading_eval = _grading_repair_penalty(grading_note)
        protected_hits = _path_protected_zone_hits(after_path or before_path or [], protected_zones, ignored_names=ignored_zone_names)
        protected_blocked = any(
            bool(hit.get("avoid")) and safe_str(hit.get("kind")) in HARD_PROTECTED_ZONE_KINDS
            for hit in protected_hits
        )
        constructability = _candidate_constructability_score(
            before_path or [],
            after_path or before_path or [],
            protected_penalty=protected_penalty,
            added_structures=added_structures,
            ownership_class=ownership_class,
            grading_penalty=safe_float(grading_eval.get("score"), 0.0),
        )
        corridor_penalty = _corridor_deviation_cost(after_path or before_path or [], preference or {})
        deltas = _resolution_engineering_deltas(base_snapshot, project, manager, changed_systems, pre_conflicts=pre_all, post_conflicts=post_all)
        crossing_eval = _crossing_hierarchy_evaluation(
            conflict,
            safe_str(changed_systems[0]) if changed_systems else "",
            strategy,
            target_ownership_class=ownership_class,
            crossing_strategy=crossing_strategy,
        )
        deltas["corridor_impact"] = {
            "before_deviation_ft": round(_corridor_deviation_cost(before_path or [], preference or {}), 3),
            "after_deviation_ft": round(corridor_penalty, 3),
            "delta_ft": round(corridor_penalty - _corridor_deviation_cost(before_path or [], preference or {}), 3),
        }
        deltas["protected_zone_impact"] = {
            "hit_count": len(protected_hits),
            "hit_kinds": dedupe_keep_order(safe_str(hit.get("kind")) for hit in protected_hits if safe_str(hit.get("kind"))),
            "penalty": round(protected_penalty, 3),
        }
        deltas["grading_impact"] = {
            "blocked": bool(grading_eval.get("blocked")),
            "score": round(safe_float(grading_eval.get("score"), 0.0), 3),
            "disturbance_class": safe_str(grading_eval.get("disturbance_class")),
            "repair_modes": deepcopy(safe_list(grading_eval.get("repair_modes"))),
        }
        deltas["constructability_impact"] = {
            "score": round(safe_float(constructability.get("score"), 0.0), 3),
            "bend_complexity": safe_int(constructability.get("bend_complexity"), 0),
            "protected_zone_penalty": round(safe_float(constructability.get("protected_zone_penalty"), 0.0), 3),
        }
        deltas["crossing_hierarchy"] = {
            "total_checks": 1 if safe_str(conflict.get("conflict_type")).endswith("_clearance") else 0,
            "compliant_checks": 1 if bool(crossing_eval.get("compliant")) and safe_str(conflict.get("conflict_type")).endswith("_clearance") else 0,
            "penalty": round(safe_float(crossing_eval.get("penalty"), 0.0), 3),
            "blocked": bool(crossing_eval.get("blocked")),
            "interaction_types": [safe_str(crossing_eval.get("interaction_type"))] if safe_str(crossing_eval.get("interaction_type")) else [],
        }
        mode_weights = {
            "balanced": {"corridor": 3.0, "extra_protected": 0.0},
            "corridor_bias": {"corridor": 6.0, "extra_protected": 0.0},
            "protected_zone_bias": {"corridor": 2.0, "extra_protected": 180.0},
            "trench_cluster": {"corridor": 5.0, "extra_protected": 120.0},
        }
        weights = mode_weights.get(candidate_mode, mode_weights["balanced"])
        valid = bool(validations.get("valid")) and len(post_related) == 0 and not protected_blocked and not bool(grading_eval.get("blocked")) and not bool(crossing_eval.get("blocked"))
        score = (
            len(post_related) * 550.0
            + len(post_all) * 180.0
            + (0.0 if validations.get("valid") else 700.0)
            + safe_float(constructability.get("score"), 0.0)
            + corridor_penalty * safe_float(weights.get("corridor"), 3.0)
            + (safe_float(weights.get("extra_protected"), 0.0) if protected_blocked else 0.0)
            + (260.0 if bool(grading_eval.get("blocked")) else 0.0)
            + safe_float(crossing_eval.get("penalty"), 0.0)
            + abs(safe_float(safe_dict(deltas.get("earthwork_impact")).get("cut_fill_delta_cf"), 0.0)) * 0.02
            + extra_penalty
        )
        candidate = {
            "strategy": strategy,
            "source_mode": source_mode,
            "target": target_name,
            "changed_systems": _canonical_changed_systems(changed_systems),
            "valid": valid,
            "score": round(score, 3),
            "constructability": constructability,
            "engineering_deltas": deltas,
            "post_validation": validations,
            "remaining_related_conflicts": len(post_related),
            "remaining_total_conflicts": len(post_all),
            "corridor_penalty": round(corridor_penalty, 3),
            "protected_zone_hits": deepcopy(protected_hits),
            "crossing_hierarchy": deepcopy(crossing_eval),
            "ownership_class": ownership_class,
            "notes": deepcopy(notes or []),
            "why_failed": safe_str(why_failed),
        }
        if valid:
            candidate["why_failed"] = ""
        candidate["coordination_realism"] = _coordination_realism_summary_impl(candidate, conflict=conflict)
        candidate["failure_breakdown"] = _coordination_failure_breakdown(
            remaining_conflicts=post_related,
            post_validation=validations,
            protected_zone_hits=protected_hits,
            engineering_deltas=deltas,
            rejected_reason=safe_str(candidate.get("why_failed")),
        )
        evaluated_candidates.append(
            {
                "strategy": strategy,
                "source_mode": source_mode,
                "target": target_name,
                "valid": bool(candidate.get("valid")),
                "score": safe_float(candidate.get("score"), 0.0),
                "corridor_penalty": round(corridor_penalty, 3),
                "protected_zone_penalty": round(protected_penalty, 3),
                "protected_zone_hit_kinds": dedupe_keep_order(safe_str(hit.get("kind")) for hit in protected_hits if safe_str(hit.get("kind"))),
                "grading_blocked": bool(grading_eval.get("blocked")),
                "crossing_blocked": bool(crossing_eval.get("blocked")),
                "crossing_penalty": round(safe_float(crossing_eval.get("penalty"), 0.0), 3),
                "coordination_realism": deepcopy(safe_dict(candidate.get("coordination_realism"))),
                "failure_breakdown": deepcopy(safe_dict(candidate.get("failure_breakdown"))),
            }
        )
        return candidate

    if conflict_type.endswith("_clearance"):
        primary = _find_summary_segment(project, manager, names[0])
        secondary = _find_summary_segment(project, manager, names[1]) if len(names) > 1 else None
        segment_candidates = [item for item in (primary, secondary) if item is not None]
        preferred_lower = safe_str(conflict.get("preferred_lower_system"))
        interaction_type = safe_str(conflict.get("interaction_type"), "crossing")
        candidate_targets: List[Tuple[str, str]] = []
        for target_system, rec in segment_candidates:
            role = _segment_ownership_class({"system": target_system, "segment_role": safe_str(rec.get("segment_role"))})
            candidate_targets.append((safe_str(target_system), role))
        ordered_targets = sorted(candidate_targets, key=lambda item: (SYSTEM_OWNERSHIP_PRIORITY.get(item[1], 99), item[0]))
        strategy_name = safe_str(crossing_strategy, "default_crossing")
        resolution_steps = _clearance_resolution_steps(interaction_type, strategy_name, ordered_targets, preferred_lower)

        seen_steps: set[Tuple[str, str]] = set()
        for action_kind, target_system in resolution_steps:
            step_key = (action_kind, safe_str(target_system))
            if step_key in seen_steps:
                continue
            seen_steps.add(step_key)
            _restore_full_coordination_state(project, manager, base_full_snapshot)
            target = _find_summary_segment(project, manager, names[0] if safe_str(target_system) == safe_str(primary[0] if primary else "") else names[1])
            if target is None:
                continue
            peer_name = names[1] if safe_str(target[1].get("name") or target[1].get("pipe")) == names[0] else names[0]
            peer = _find_summary_segment(project, manager, peer_name)
            if peer is None:
                continue
            _, rec = target
            target_name = safe_str(rec.get("name"), safe_str(rec.get("pipe"), target_system))
            peer_avg = (
                safe_float(peer[1].get("start_invert_ft", peer[1].get("start_invert", DEFAULT_PAD_ELEV - 4.0)), DEFAULT_PAD_ELEV - 4.0)
                + safe_float(peer[1].get("end_invert_ft", peer[1].get("end_invert", DEFAULT_PAD_ELEV - 5.0)), DEFAULT_PAD_ELEV - 5.0)
            ) / 2.0
            target_avg = (
                safe_float(rec.get("start_invert_ft", rec.get("start_invert", DEFAULT_PAD_ELEV - 4.0)), DEFAULT_PAD_ELEV - 4.0)
                + safe_float(rec.get("end_invert_ft", rec.get("end_invert", DEFAULT_PAD_ELEV - 5.0)), DEFAULT_PAD_ELEV - 5.0)
            ) / 2.0
            point = safe_list(conflict.get("location")) if isinstance(conflict.get("location"), (list, tuple)) else None
            if action_kind == "vertical":
                required_v = safe_float(conflict.get("required_vertical_clearance_ft"), 0.0)
                current_gap = abs(target_avg - peer_avg)
                if safe_str(target_system) == preferred_lower:
                    needed = max(target_avg - (peer_avg - required_v) + 0.25, 0.5)
                    direction = "deepen"
                else:
                    needed = max(required_v - current_gap + 0.25, 0.5)
                    direction = "raise"
                route_points = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(rec.get("route_points") or rec.get("path")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                if direction == "raise" and route_points:
                    grading_summary = safe_dict(project.meta.get("grading_summary", manager.latest_outputs.get("grading", {})))
                    proposed_surface = grading_summary.get("proposed_surface")
                    start_invert_value = safe_float(rec.get("start_invert_ft", rec.get("start_invert", DEFAULT_PAD_ELEV - 4.0)), DEFAULT_PAD_ELEV - 4.0)
                    end_invert_value = safe_float(rec.get("end_invert_ft", rec.get("end_invert", DEFAULT_PAD_ELEV - 5.0)), DEFAULT_PAD_ELEV - 5.0)
                    start_surface = _sample_grid_surface(proposed_surface, route_points[0][0], route_points[0][1], DEFAULT_PAD_ELEV)
                    end_surface = _sample_grid_surface(proposed_surface, route_points[-1][0], route_points[-1][1], DEFAULT_PAD_ELEV)
                    max_raise = min(
                        max(start_invert_value - (start_surface - PIPE_MIN_COVER_FT), 0.0),
                        max(end_invert_value - (end_surface - PIPE_MIN_COVER_FT), 0.0),
                    )
                    needed = min(needed, max_raise)
                    if needed <= 1e-6:
                        continue
                sign = -1.0 if direction == "deepen" else 1.0
                if "start_invert" in rec:
                    rec["start_invert"] = round(safe_float(rec.get("start_invert"), DEFAULT_PAD_ELEV - 4.0) + sign * needed, 3)
                    rec["end_invert"] = round(safe_float(rec.get("end_invert"), DEFAULT_PAD_ELEV - 5.0) + sign * needed, 3)
                    rec["cover_start_ft"] = round(max(safe_float(rec.get("cover_start_ft"), PIPE_MIN_COVER_FT) - sign * needed, 0.0), 3)
                    rec["cover_end_ft"] = round(max(safe_float(rec.get("cover_end_ft"), PIPE_MIN_COVER_FT) - sign * needed, 0.0), 3)
                else:
                    rec["start_invert_ft"] = round(safe_float(rec.get("start_invert_ft"), DEFAULT_PAD_ELEV - 4.0) + sign * needed, 3)
                    rec["end_invert_ft"] = round(safe_float(rec.get("end_invert_ft"), DEFAULT_PAD_ELEV - 5.0) + sign * needed, 3)
                    if "cover_start_ft" in rec:
                        rec["cover_start_ft"] = round(max(safe_float(rec.get("cover_start_ft"), PIPE_MIN_COVER_FT) - sign * needed, 0.0), 3)
                    if "cover_end_ft" in rec:
                        rec["cover_end_ft"] = round(max(safe_float(rec.get("cover_end_ft"), PIPE_MIN_COVER_FT) - sign * needed, 0.0), 3)
                grading_note = _apply_local_grading_repair(project, safe_str(target_name), delta_depth_ft=needed, point=point)
                candidate = _finalize_candidate(
                    strategy="vertical_adjustment",
                    source_mode=f"{candidate_mode}:vertical:{strategy_name}",
                    target_name=target_name,
                    changed_systems=[safe_str(target_system)],
                    before_path=safe_list(rec.get("route_points") or rec.get("path")),
                    after_path=safe_list(rec.get("route_points") or rec.get("path")),
                    notes=[f"{'Lowered' if direction == 'deepen' else 'Raised'} {target_name} by {needed:.2f} ft to satisfy {conflict_type}.", f"Triggered local grading repair near {safe_str(target_name)}."],
                    extra_penalty=(
                        (0.0 if safe_str(rec.get("system")) == preferred_lower or safe_str(target_system) == preferred_lower else 120.0)
                        + (180.0 if interaction_type == "crossing" and strategy_name == "upper_reroute_first" and safe_str(target_system) == preferred_lower else 0.0)
                        + (120.0 if interaction_type == "parallel" and strategy_name == "parallel_shift_first" else 0.0)
                    ),
                    why_failed="Vertical separation remained insufficient or downstream validations failed.",
                    grading_note=grading_note,
                )
            else:
                route_path = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(rec.get("route_points") or rec.get("path")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                if len(route_path) < 2:
                    continue
                center = point if len(point) >= 2 else _segment_midpoint(route_path)
                required_h = max(safe_float(conflict.get("required_horizontal_clearance_ft"), 0.0), 8.0)
                synthetic_rect = {
                    "name": f"{target_name}-CROSSING",
                    "kind": "crossing_window",
                    "x": safe_float(center[0], 0.0) - required_h / 2.0,
                    "y": safe_float(center[1], 0.0) - required_h / 2.0,
                    "w": required_h,
                    "h": required_h,
                    "buffer_ft": max(required_h / 2.0, 4.0),
                    "penalty": 40.0,
                    "avoid": False,
                }
                preference = _preferred_corridor_for_segment(project, {"system": safe_str(target_system), **rec})
                effective_cluster_context = cluster_context
                effective_candidate_mode = "corridor_bias" if strategy_name != "hierarchy_first" else candidate_mode
                if interaction_type == "crossing" and strategy_name == "upper_reroute_first" and safe_str(target_system) != preferred_lower:
                    effective_cluster_context = None
                    effective_candidate_mode = "corridor_bias"
                candidate_paths = _geometry_candidate_paths(
                    route_path,
                    synthetic_rect,
                    preference,
                    candidate_mode=effective_candidate_mode,
                    cluster_context=effective_cluster_context,
                    protected_zones=protected_zones,
                )
                candidate_paths = _prune_geometry_candidate_rows(candidate_paths, route_path, metrics=metrics, breadth_cap=4)
                for candidate_row in candidate_paths:
                    _coordination_metric_inc(metrics, ["rollbacks"])
                    _restore_full_coordination_state(project, manager, base_full_snapshot)
                    refreshed = _find_summary_segment(project, manager, names[0] if safe_str(target_system) == safe_str(primary[0] if primary else "") else names[1])
                    if refreshed is None:
                        continue
                    refreshed_system, refreshed_rec = refreshed
                    reroute_path = deepcopy(safe_list(candidate_row.get("path")))
                    if "route_points" in refreshed_rec:
                        refreshed_rec["route_points"] = reroute_path
                    else:
                        refreshed_rec["path"] = reroute_path
                    length_ft = polyline_length(reroute_path)
                    refreshed_rec["length_ft"] = round(length_ft, 3)
                    if safe_float(refreshed_rec.get("slope_ft_ft"), 0.0) > 0.0:
                        start_invert = safe_float(refreshed_rec.get("start_invert_ft", refreshed_rec.get("start_invert", DEFAULT_PAD_ELEV - 4.0)), DEFAULT_PAD_ELEV - 4.0)
                        drop = safe_float(refreshed_rec.get("slope_ft_ft"), 0.0) * length_ft
                        if "end_invert_ft" in refreshed_rec:
                            refreshed_rec["end_invert_ft"] = round(start_invert - drop, 3)
                        elif "end_invert" in refreshed_rec:
                            refreshed_rec["end_invert"] = round(start_invert - drop, 3)
                    structure_info = _apply_structure_insertion_rules(
                        project,
                        manager,
                        safe_str(refreshed_system),
                        safe_str(refreshed_rec.get("name"), target_name),
                        reroute_path,
                        metrics=metrics,
                        analysis_cache=structure_analysis_cache,
                    )
                    grading_note = _apply_local_grading_repair(project, safe_str(refreshed_rec.get("name"), target_name), delta_depth_ft=max(length_ft - polyline_length(route_path), 0.0) * 0.025, point=_segment_midpoint(reroute_path))
                    candidate = _finalize_candidate(
                        strategy="clearance_reroute",
                        source_mode=f"{candidate_mode}:{strategy_name}:{safe_str(candidate_row.get('source_mode'))}",
                        target_name=safe_str(refreshed_rec.get("name"), target_name),
                        changed_systems=[safe_str(refreshed_system)],
                        before_path=route_path,
                        after_path=reroute_path,
                        added_structures=safe_int(structure_info.get("added_count"), 0),
                        notes=[f"Rerouted {safe_str(refreshed_rec.get('name'), target_name)} to satisfy {conflict_type} using {strategy_name} crossing strategy."],
                        preference=preference,
                        extra_penalty=(
                            (-30.0 if interaction_type == "crossing" and strategy_name == "upper_reroute_first" and safe_str(target_system) != preferred_lower else 0.0)
                            + (-20.0 if interaction_type == "parallel" and strategy_name == "parallel_shift_first" else 0.0)
                            + (25.0 if interaction_type == "crossing" and strategy_name == "hierarchy_first" and safe_str(target_system) != preferred_lower else 0.0)
                        ),
                        why_failed="Crossing reroute did not satisfy downstream clearance or coordination validation.",
                        grading_note=grading_note,
                        ignored_zone_names=[safe_str(synthetic_rect.get("name"))],
                    )
                    candidate["grading_repair"] = grading_note
                    candidate["inserted_structures"] = structure_info
                    candidate["coordination_realism"] = _coordination_realism_summary_impl(candidate, conflict=conflict)
                    if candidate["valid"] and (best_choice is None or safe_float(candidate.get("score"), 0.0) < safe_float(best_choice.get("score"), 1e9)):
                        best_choice = candidate
                        best_snapshot = _snapshot_coordination_state(project, manager)
                        best_full_snapshot = _full_coordination_state_snapshot(project, manager)
                    elif best_near_valid is None or safe_float(candidate.get("score"), 0.0) < safe_float(best_near_valid.get("score"), 1e9):
                        best_near_valid = candidate
                continue
            candidate["grading_repair"] = grading_note
            candidate["coordination_realism"] = _coordination_realism_summary_impl(candidate, conflict=conflict)
            if candidate["valid"] and (best_choice is None or safe_float(candidate.get("score"), 0.0) < safe_float(best_choice.get("score"), 1e9)):
                best_choice = candidate
                best_snapshot = _snapshot_coordination_state(project, manager)
                best_full_snapshot = _full_coordination_state_snapshot(project, manager)
            elif best_near_valid is None or safe_float(candidate.get("score"), 0.0) < safe_float(best_near_valid.get("score"), 1e9):
                best_near_valid = candidate

    elif conflict_type.endswith("_geometry"):
        primary = _find_summary_segment(project, manager, names[0])
        if primary is not None:
            _, base_rec = primary
            path = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(base_rec.get("route_points") or base_rec.get("path")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
            obstacles = _expanded_obstacle_rectangles(project)
            rect = next((item for item in obstacles if safe_str(item.get("name")) == safe_str(names[1])), None)
            if len(path) >= 2 and rect is not None:
                preference = _preferred_corridor_for_segment(project, {"system": safe_str(primary[0]), **base_rec})
                candidate_paths = _geometry_candidate_paths(
                    path,
                    rect,
                    preference,
                    candidate_mode=candidate_mode,
                    cluster_context=cluster_context,
                    protected_zones=protected_zones,
                )
                candidate_paths = _prune_geometry_candidate_rows(
                    candidate_paths,
                    path,
                    metrics=metrics,
                    breadth_cap=4,
                    preserve_first_hard_avoid=(candidate_mode == "protected_zone_bias"),
                )
                for candidate_row in candidate_paths:
                    candidate_path = deepcopy(safe_list(candidate_row.get("path")))
                    _coordination_metric_inc(metrics, ["rollbacks"])
                    _restore_full_coordination_state(project, manager, base_full_snapshot)
                    refreshed = _find_summary_segment(project, manager, names[0])
                    if refreshed is None:
                        continue
                    target_system, rec = refreshed
                    if "route_points" in rec:
                        rec["route_points"] = candidate_path
                    else:
                        rec["path"] = candidate_path
                    length_ft = polyline_length(candidate_path)
                    rec["length_ft"] = round(length_ft, 3)
                    if safe_float(rec.get("slope_ft_ft"), 0.0) > 0.0:
                        start_invert = safe_float(rec.get("start_invert_ft", rec.get("start_invert", DEFAULT_PAD_ELEV - 4.0)), DEFAULT_PAD_ELEV - 4.0)
                        drop = safe_float(rec.get("slope_ft_ft"), 0.0) * length_ft
                        if "end_invert_ft" in rec:
                            rec["end_invert_ft"] = round(start_invert - drop, 3)
                        elif "end_invert" in rec:
                            rec["end_invert"] = round(start_invert - drop, 3)
                    structure_info = _apply_structure_insertion_rules(
                        project,
                        manager,
                        safe_str(target_system),
                        safe_str(rec.get("name"), names[0]),
                        candidate_path,
                        metrics=metrics,
                        analysis_cache=structure_analysis_cache,
                    )
                    grading_note = _apply_local_grading_repair(project, safe_str(rec.get("name"), names[0]), delta_depth_ft=max(length_ft - polyline_length(path), 0.0) * 0.02, point=_segment_midpoint(candidate_path))
                    strategy = safe_str(candidate_row.get("strategy"), "reroute_around_obstacle")
                    candidate = _finalize_candidate(
                        strategy=strategy,
                        source_mode=f"{candidate_mode}:{safe_str(candidate_row.get('source_mode'))}",
                        target_name=safe_str(rec.get("name"), names[0]),
                        changed_systems=[safe_str(target_system)],
                        before_path=path,
                        after_path=candidate_path,
                        added_structures=safe_int(structure_info.get("added_count"), 0),
                        notes=[
                            f"{'Shifted the terminal point for' if strategy == 'terminal_shift' else 'Rerouted'} {safe_str(rec.get('name'), names[0])} around {safe_str(rect.get('name'))} using {safe_str(candidate_row.get('source_mode'), 'candidate')} routing.",
                            f"Triggered local grading repair near {safe_str(rec.get('name'), names[0])}.",
                        ],
                        preference=preference,
                        why_failed=f"Protected-zone or graph validations remained unsatisfied after rerouting around {safe_str(rect.get('name'))}.",
                        grading_note=grading_note,
                        ignored_zone_names=[safe_str(rect.get("name"))],
                    )
                    candidate["grading_repair"] = grading_note
                    candidate["inserted_structures"] = structure_info
                    candidate["coordination_realism"] = _coordination_realism_summary_impl(candidate, conflict=conflict)
                    if candidate["valid"] and (best_choice is None or safe_float(candidate.get("score"), 0.0) < safe_float(best_choice.get("score"), 1e9)):
                        best_choice = candidate
                        best_snapshot = _snapshot_coordination_state(project, manager)
                        best_full_snapshot = _full_coordination_state_snapshot(project, manager)
                    elif best_near_valid is None or safe_float(candidate.get("score"), 0.0) < safe_float(best_near_valid.get("score"), 1e9):
                        best_near_valid = candidate

    elif conflict_type == "pipe_cover_violation":
        target = _find_summary_segment(project, manager, names[0])
        if target is not None:
            _restore_full_coordination_state(project, manager, base_full_snapshot)
            target = _find_summary_segment(project, manager, names[0])
            if target is not None:
                target_system, rec = target
                needed = max(safe_float(conflict.get("required_clearance_ft"), 0.0) - safe_float(conflict.get("actual_clearance_ft"), 0.0) + 0.25, 0.5)
                if "start_invert" in rec:
                    rec["start_invert"] = round(safe_float(rec.get("start_invert"), DEFAULT_PAD_ELEV - 4.0) - needed, 3)
                    rec["end_invert"] = round(safe_float(rec.get("end_invert"), DEFAULT_PAD_ELEV - 5.0) - needed, 3)
                else:
                    rec["start_invert_ft"] = round(safe_float(rec.get("start_invert_ft"), DEFAULT_PAD_ELEV - 4.0) - needed, 3)
                    rec["end_invert_ft"] = round(safe_float(rec.get("end_invert_ft"), DEFAULT_PAD_ELEV - 5.0) - needed, 3)
                grading_note = _apply_local_grading_repair(project, safe_str(rec.get("name"), names[0]), delta_depth_ft=needed, point=safe_list(conflict.get("location")))
                candidate = _finalize_candidate(
                    strategy="cover_adjustment",
                    source_mode=f"{candidate_mode}:cover",
                    target_name=safe_str(rec.get("name"), names[0]),
                    changed_systems=[safe_str(target_system)],
                    before_path=safe_list(rec.get("route_points") or rec.get("path")),
                    after_path=safe_list(rec.get("route_points") or rec.get("path")),
                    notes=[f"Deepened {safe_str(rec.get('name'), names[0])} to restore cover."],
                    why_failed="Cover remained below the minimum requirement or downstream validations failed.",
                    grading_note=grading_note,
                )
                candidate["grading_repair"] = grading_note
                candidate["coordination_realism"] = _coordination_realism_summary_impl(candidate, conflict=conflict)
                if candidate["valid"]:
                    best_choice = candidate
                    best_snapshot = _snapshot_coordination_state(project, manager)
                    best_full_snapshot = _full_coordination_state_snapshot(project, manager)
                else:
                    best_near_valid = candidate

    elif conflict_type == "slope_violation":
        target = _find_summary_segment(project, manager, names[0])
        if target is not None:
            _restore_full_coordination_state(project, manager, base_full_snapshot)
            target = _find_summary_segment(project, manager, names[0])
            if target is not None:
                target_system, rec = target
                path = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(rec.get("route_points") or rec.get("path")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                length_ft = max(polyline_length(path), 1e-9)
                min_slope = max(safe_float(conflict.get("required_slope_ft_ft"), safe_float(rec.get("slope_ft_ft"), 0.0)), 0.01)
                start_invert = safe_float(rec.get("start_invert_ft", rec.get("start_invert", DEFAULT_PAD_ELEV - 4.0)), DEFAULT_PAD_ELEV - 4.0)
                new_end = start_invert - min_slope * length_ft
                rec["slope_ft_ft"] = round(min_slope, 5)
                if "end_invert_ft" in rec:
                    rec["end_invert_ft"] = round(new_end, 3)
                elif "end_invert" in rec:
                    rec["end_invert"] = round(new_end, 3)
                structure_info = _apply_structure_insertion_rules(project, manager, safe_str(target_system), safe_str(rec.get("name"), names[0]), path)
                grading_note = _apply_local_grading_repair(project, safe_str(rec.get("name"), names[0]), delta_depth_ft=max(start_invert - new_end, 0.0) * 0.1, point=_segment_midpoint(path))
                candidate = _finalize_candidate(
                    strategy="slope_adjustment",
                    source_mode=f"{candidate_mode}:slope",
                    target_name=safe_str(rec.get("name"), names[0]),
                    changed_systems=[safe_str(target_system)],
                    before_path=path,
                    after_path=path,
                    added_structures=safe_int(structure_info.get("added_count"), 0),
                    notes=[f"Adjusted downstream invert on {safe_str(rec.get('name'), names[0])} to restore minimum slope."],
                    why_failed="Minimum slope could not be restored without breaking graph or consistency checks.",
                    grading_note=grading_note,
                )
                candidate["grading_repair"] = grading_note
                candidate["inserted_structures"] = structure_info
                candidate["coordination_realism"] = _coordination_realism_summary_impl(candidate, conflict=conflict)
                if candidate["valid"]:
                    best_choice = candidate
                    best_snapshot = _snapshot_coordination_state(project, manager)
                    best_full_snapshot = _full_coordination_state_snapshot(project, manager)
                else:
                    best_near_valid = candidate

    _coordination_metric_inc(metrics, ["timings_ms", "apply_conflict_resolution"], round((perf_counter() - started) * 1000.0, 3))
    if best_snapshot is not None and best_choice is not None:
        if best_full_snapshot is not None:
            _restore_full_coordination_state(project, manager, best_full_snapshot)
        else:
            _restore_coordination_state(project, manager, best_snapshot)
        resolution.update(
            {
                "success": True,
                "strategy": safe_str(best_choice.get("strategy")),
                "notes": deepcopy(safe_list(best_choice.get("notes"))),
                "changed_systems": deepcopy(safe_list(best_choice.get("changed_systems"))),
                "constructability": deepcopy(safe_dict(best_choice.get("constructability"))),
                "engineering_deltas": deepcopy(safe_dict(best_choice.get("engineering_deltas"))),
                "best_near_valid_candidate": deepcopy(safe_dict(best_near_valid or {})),
                "coordination_realism": deepcopy(safe_dict(best_choice.get("coordination_realism"))),
                "evaluated_candidates": deepcopy(evaluated_candidates),
            }
        )
        return resolution

    _restore_full_coordination_state(project, manager, base_full_snapshot)
    resolution["best_near_valid_candidate"] = deepcopy(safe_dict(best_near_valid or {}))
    resolution["failure_reason"] = safe_str(safe_dict(best_near_valid or {}).get("why_failed")) or "No safe candidate reduced this conflict cluster without violating downstream engineering checks."
    resolution["notes"].append(resolution["failure_reason"])
    resolution["evaluated_candidates"] = deepcopy(evaluated_candidates)
    if assisted_mode:
        resolution["assumed"] = True
    return resolution


def _refresh_conflict_resolved_state(
    project: ProjectModel,
    manager: ProjectManager,
    changed_systems: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    changed = {safe_str(item) for item in safe_list(changed_systems) if safe_str(item)}
    if not changed:
        changed = {"storm", "storm_pipes", "sanitary", "utilities", "water"}
    if changed.intersection({"storm", "storm_pipes"}):
        _recompute_storm_summary(project, manager)
    if "sanitary" in changed:
        _recompute_sanitary_summary(project, manager, prefer_cache=True)
    if changed.intersection({"utilities", "water", "gas", "electric", "telecom"}):
        _recompute_utility_summary(project, manager, prefer_cache=True)
    return {
        "storm": deepcopy(safe_dict(manager.latest_outputs.get("storm_pipe_summary", project.meta.get("storm_pipe_summary", {})))),
        "sanitary": deepcopy(safe_dict(manager.latest_outputs.get("sanitary", project.meta.get("sanitary_summary", {})))),
        "utilities": deepcopy(safe_dict(manager.latest_outputs.get("utilities", project.meta.get("utility_summary", {})))),
    }


def _cluster_remaining_conflicts(conflicts: Sequence[Dict[str, Any]], cluster: Dict[str, Any]) -> List[Dict[str, Any]]:
    cluster_conflicts = [safe_dict(item) for item in safe_list(safe_dict(cluster).get("conflicts"))]
    return [
        safe_dict(item)
        for item in conflicts
        if any(_conflict_signature(item) == _conflict_signature(cluster_item) or _conflicts_related(item, cluster_item) for cluster_item in cluster_conflicts)
    ]


def _cluster_candidate_orders(cluster: Dict[str, Any]) -> List[Dict[str, Any]]:
    conflicts = [safe_dict(item) for item in safe_list(safe_dict(cluster).get("conflicts")) if safe_dict(item)]
    if not conflicts:
        return []
    trench_like = bool(cluster.get("trench_like"))
    blocking_zone_kinds = {safe_str(item) for item in safe_list(cluster.get("blocking_zone_kinds")) if safe_str(item)}
    base_orders: List[Tuple[str, List[Dict[str, Any]]]] = [
        ("priority", sorted(conflicts, key=_conflict_priority_key)),
    ]
    if len(conflicts) > 1:
        base_orders.append(("reverse_priority", list(reversed(sorted(conflicts, key=_conflict_priority_key)))))
        base_orders.append(("geometry_first", sorted(conflicts, key=lambda item: (0 if safe_str(item.get("conflict_type")).endswith("_geometry") else 1, _conflict_priority_key(item)))))
        base_orders.append(("clearance_first", sorted(conflicts, key=lambda item: (0 if safe_str(item.get("conflict_type")).endswith("_clearance") else 1, _conflict_priority_key(item)))))
    candidate_modes = ["balanced"]
    if trench_like:
        candidate_modes.append("trench_cluster")
        candidate_modes.append("corridor_bias")
    if blocking_zone_kinds:
        candidate_modes.append("protected_zone_bias")
    unique: List[Dict[str, Any]] = []
    seen: set[Tuple[str, Tuple[Tuple[str, Tuple[str, ...]], ...]]] = set()
    for mode in candidate_modes:
        for name, ordered in base_orders:
            key = (mode, tuple(_conflict_signature(item) for item in ordered))
            if key in seen:
                continue
            seen.add(key)
            unique.append({"name": f"{name}:{mode}", "order_name": name, "candidate_mode": mode, "conflicts": deepcopy(ordered)})
    return unique


def _merge_engineering_deltas(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "added_length_ft": round(sum(safe_float(safe_dict(item).get("added_length_ft"), 0.0) for item in rows), 3),
        "added_depth_ft": round(sum(safe_float(safe_dict(item).get("added_depth_ft"), 0.0) for item in rows), 3),
        "added_structures": sum(safe_int(safe_dict(item).get("added_structures"), 0) for item in rows),
        "hydraulic_impact": {
            "storm_capacity_delta_cfs": round(sum(safe_float(safe_dict(safe_dict(item).get("hydraulic_impact")).get("storm_capacity_delta_cfs"), 0.0) for item in rows), 3),
            "storm_ratio_delta": round(sum(safe_float(safe_dict(safe_dict(item).get("hydraulic_impact")).get("storm_ratio_delta"), 0.0) for item in rows), 3),
            "sanitary_slope_violation_delta": sum(safe_int(safe_dict(safe_dict(item).get("hydraulic_impact")).get("sanitary_slope_violation_delta"), 0) for item in rows),
        },
        "earthwork_impact": {
            "grading_adjustment_count": sum(safe_int(safe_dict(safe_dict(item).get("earthwork_impact")).get("grading_adjustment_count"), 0) for item in rows),
            "cut_fill_delta_cf": round(sum(safe_float(safe_dict(safe_dict(item).get("earthwork_impact")).get("cut_fill_delta_cf"), 0.0) for item in rows), 3),
        },
        "resolved_conflicts": sum(safe_int(safe_dict(item).get("resolved_conflicts"), 0) for item in rows),
        "new_conflicts_avoided": sum(safe_int(safe_dict(item).get("new_conflicts_avoided"), 0) for item in rows),
        "protected_zone_impact": {
            "hit_count": sum(safe_int(safe_dict(safe_dict(item).get("protected_zone_impact")).get("hit_count"), 0) for item in rows),
            "penalty": round(sum(safe_float(safe_dict(safe_dict(item).get("protected_zone_impact")).get("penalty"), 0.0) for item in rows), 3),
            "hit_kinds": dedupe_keep_order(
                safe_str(kind)
                for item in rows
                for kind in safe_list(safe_dict(safe_dict(item).get("protected_zone_impact")).get("hit_kinds"))
                if safe_str(kind)
            ),
        },
        "grading_impact": {
            "blocked": any(bool(safe_dict(safe_dict(item).get("grading_impact")).get("blocked")) for item in rows),
            "score": round(sum(safe_float(safe_dict(safe_dict(item).get("grading_impact")).get("score"), 0.0) for item in rows), 3),
            "disturbance_classes": dedupe_keep_order(
                safe_str(safe_dict(safe_dict(item).get("grading_impact")).get("disturbance_class"))
                for item in rows
                if safe_str(safe_dict(safe_dict(item).get("grading_impact")).get("disturbance_class"))
            ),
            "repair_modes": dedupe_keep_order(
                safe_str(mode)
                for item in rows
                for mode in safe_list(safe_dict(safe_dict(item).get("grading_impact")).get("repair_modes"))
                if safe_str(mode)
            ),
        },
        "constructability_impact": {
            "score": round(sum(safe_float(safe_dict(safe_dict(item).get("constructability_impact")).get("score"), 0.0) for item in rows), 3),
            "bend_complexity": sum(safe_int(safe_dict(safe_dict(item).get("constructability_impact")).get("bend_complexity"), 0) for item in rows),
            "protected_zone_penalty": round(sum(safe_float(safe_dict(safe_dict(item).get("constructability_impact")).get("protected_zone_penalty"), 0.0) for item in rows), 3),
        },
        "crossing_hierarchy": {
            "total_checks": sum(safe_int(safe_dict(safe_dict(item).get("crossing_hierarchy")).get("total_checks"), 0) for item in rows),
            "compliant_checks": sum(safe_int(safe_dict(safe_dict(item).get("crossing_hierarchy")).get("compliant_checks"), 0) for item in rows),
            "penalty": round(sum(safe_float(safe_dict(safe_dict(item).get("crossing_hierarchy")).get("penalty"), 0.0) for item in rows), 3),
            "blocked": any(bool(safe_dict(safe_dict(item).get("crossing_hierarchy")).get("blocked")) for item in rows),
            "interaction_types": dedupe_keep_order(
                safe_str(interaction)
                for item in rows
                for interaction in safe_list(safe_dict(safe_dict(item).get("crossing_hierarchy")).get("interaction_types"))
                if safe_str(interaction)
            ),
        },
    }


def _apply_cluster_trench_prefit(project: ProjectModel, manager: ProjectManager, cluster: Dict[str, Any], candidate_mode: str) -> Dict[str, Any]:
    if candidate_mode not in {"trench_cluster", "corridor_bias", "protected_zone_bias"} or not bool(cluster.get("trench_like")):
        return {"applied": False, "changed_systems": [], "notes": [], "moved_segments": [], "added_structures": 0, "grading_notes": []}
    protected_zones = _expanded_obstacle_rectangles(project)
    obstacle_names = {
        safe_str(name)
        for conflict in safe_list(cluster.get("conflicts"))
        for name in safe_list(safe_dict(conflict).get("involved_objects"))
        if safe_str(name) and safe_str(name) not in {safe_str(item) for item in safe_list(cluster.get("objects")) if _find_summary_segment(project, manager, safe_str(item))}
    }
    target_obstacles = [zone for zone in protected_zones if safe_str(safe_dict(zone).get("name")) in obstacle_names]
    segment_rows: List[Tuple[str, str, str]] = []
    for name in safe_list(cluster.get("objects")):
        seg = _find_summary_segment(project, manager, safe_str(name))
        if seg is None:
            continue
        system_name, rec = seg
        ownership = _segment_ownership_class({"system": system_name, "segment_role": safe_str(rec.get("segment_role"))})
        segment_rows.append((system_name, safe_str(rec.get("name") or rec.get("pipe") or name), ownership))
    if not segment_rows or not target_obstacles:
        return {"applied": False, "changed_systems": [], "notes": [], "moved_segments": [], "added_structures": 0, "grading_notes": []}

    ordered_rows = sorted(segment_rows, key=lambda row: (SYSTEM_OWNERSHIP_PRIORITY.get(row[2], 99), row[1]), reverse=True)
    if candidate_mode == "trench_cluster":
        movable = [row for row in ordered_rows if SYSTEM_OWNERSHIP_PRIORITY.get(row[2], 99) >= 4] or ordered_rows
    else:
        movable = ordered_rows

    changed_systems: set[str] = set()
    notes: List[str] = []
    moved_segments: List[Dict[str, Any]] = []
    grading_notes: List[Dict[str, Any]] = []
    added_structures = 0
    cluster_corridor = _cluster_preferred_corridor(cluster, project, safe_str(cluster.get("corridor_key"), "water"))
    for system_name, segment_name, ownership in movable:
        refreshed = _find_summary_segment(project, manager, segment_name)
        if refreshed is None:
            continue
        target_system, rec = refreshed
        current_path = [
            [safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)]
            for pt in safe_list(rec.get("route_points") or rec.get("path"))
            if isinstance(pt, (list, tuple)) and len(pt) >= 2
        ]
        if len(current_path) < 2:
            continue
        before_path = deepcopy(current_path)
        segment_preference = _cluster_preferred_corridor(cluster, project, safe_str(target_system))
        candidate_path = deepcopy(current_path)
        for rect in target_obstacles:
            if not _path_hits_buffered_rect(candidate_path, rect):
                continue
            candidates = _geometry_candidate_paths(
                candidate_path,
                rect,
                segment_preference or cluster_corridor,
                candidate_mode=candidate_mode,
                cluster_context=cluster,
                protected_zones=protected_zones,
            )
            if not candidates:
                continue
            candidate_path = deepcopy(safe_list(candidates[0].get("path")))
        if candidate_path == before_path:
            continue
        if "route_points" in rec:
            rec["route_points"] = candidate_path
        else:
            rec["path"] = candidate_path
        length_ft = polyline_length(candidate_path)
        rec["length_ft"] = round(length_ft, 3)
        slope_ft_ft = safe_float(rec.get("slope_ft_ft"), 0.0)
        if slope_ft_ft > 0.0:
            start_invert = safe_float(rec.get("start_invert_ft", rec.get("start_invert", DEFAULT_PAD_ELEV - 4.0)), DEFAULT_PAD_ELEV - 4.0)
            drop = slope_ft_ft * length_ft
            if "end_invert_ft" in rec:
                rec["end_invert_ft"] = round(start_invert - drop, 3)
            elif "end_invert" in rec:
                rec["end_invert"] = round(start_invert - drop, 3)
        structure_info = _apply_structure_insertion_rules(project, manager, safe_str(target_system), segment_name, candidate_path)
        grading_note = _apply_local_grading_repair(project, segment_name, delta_depth_ft=max(length_ft - polyline_length(before_path), 0.0) * 0.03, point=_segment_midpoint(candidate_path))
        added_structures += safe_int(structure_info.get("added_count"), 0)
        grading_notes.append(deepcopy(grading_note))
        changed_systems.add(safe_str(target_system))
        moved_segments.append(
            {
                "name": segment_name,
                "system": safe_str(target_system),
                "ownership_class": ownership,
                "before_length_ft": round(polyline_length(before_path), 3),
                "after_length_ft": round(length_ft, 3),
            }
        )
        notes.append(f"Cluster-prefit rerouted {segment_name} using {candidate_mode} to reduce trench-group conflicts.")
    return {
        "applied": bool(moved_segments),
        "changed_systems": _canonical_changed_systems(changed_systems),
        "notes": notes,
        "moved_segments": moved_segments,
        "added_structures": added_structures,
        "grading_notes": grading_notes,
    }


def _cluster_group_ownership_rank(project: ProjectModel, manager: ProjectManager, cluster: Dict[str, Any]) -> int:
    ranks: List[int] = []
    for name in safe_list(safe_dict(cluster).get("objects")):
        seg = _find_summary_segment(project, manager, safe_str(name))
        if seg is None:
            continue
        _system_name, rec = seg
        ranks.append(SYSTEM_OWNERSHIP_PRIORITY.get(_segment_ownership_class(rec), 99))
    return min(ranks) if ranks else 99


def _cluster_group_candidate_plans(project: ProjectModel, manager: ProjectManager, group: Dict[str, Any]) -> List[Dict[str, Any]]:
    clusters = [safe_dict(item) for item in safe_list(safe_dict(group).get("clusters")) if safe_dict(item)]
    if not clusters:
        return []
    base = sorted(clusters, key=lambda item: (_cluster_group_ownership_rank(project, manager, item), safe_str(item.get("cluster_id"))))
    lateral_first = sorted(base, key=lambda item: (-_cluster_group_ownership_rank(project, manager, item), safe_str(item.get("cluster_id"))))
    corridor_first = sorted(
        base,
        key=lambda item: (
            safe_float(item.get("corridor_offset_ft"), 0.0),
            _cluster_group_ownership_rank(project, manager, item),
            safe_str(item.get("cluster_id")),
        ),
    )
    protected_first = sorted(
        base,
        key=lambda item: (
            -len(safe_list(safe_dict(item).get("blocking_zone_kinds"))),
            safe_float(item.get("corridor_offset_ft"), 0.0),
            safe_str(item.get("cluster_id")),
        ),
    )
    base_plans = [
        {
            "name": "balanced_group",
            "clusters": deepcopy(base),
            "allowed_candidate_modes": [],
            "group_prefit_mode": "balanced",
        },
        {
            "name": "trunk_preserve_group",
            "clusters": deepcopy(lateral_first),
            "allowed_candidate_modes": ["trench_cluster", "corridor_bias", "balanced"],
            "group_prefit_mode": "trench_cluster",
        },
        {
            "name": "corridor_hold_group",
            "clusters": deepcopy(corridor_first),
            "allowed_candidate_modes": ["corridor_bias", "trench_cluster", "balanced"],
            "group_prefit_mode": "corridor_bias",
        },
    ]
    if safe_list(safe_dict(group).get("blocking_zone_kinds")):
        base_plans.append(
            {
                "name": "protected_first_group",
                "clusters": deepcopy(protected_first),
                "allowed_candidate_modes": ["protected_zone_bias", "trench_cluster", "corridor_bias", "balanced"],
                "group_prefit_mode": "protected_zone_bias",
            }
        )
    crossing_strategies = _group_crossing_strategy_options(group)
    geometry_strategies = (
        ["", "shared_corridor_escape"]
        if bool(group.get("trench_like")) and any(safe_str(item.get("conflict_type")).endswith("_geometry") for item in safe_list(group.get("conflicts")))
        else [""]
    )
    plans: List[Dict[str, Any]] = []
    for base_plan in base_plans:
        for strategy in crossing_strategies:
            for geometry_strategy in geometry_strategies:
                row = deepcopy(base_plan)
                strategy_name = safe_str(safe_dict(strategy).get("name"), "default_crossing")
                row["crossing_strategy"] = strategy_name
                row["crossing_strategy_description"] = safe_str(safe_dict(strategy).get("description"))
                row["geometry_strategy"] = geometry_strategy
                row["name"] = (
                    f"{safe_str(base_plan.get('name'))}:{strategy_name}:{geometry_strategy}"
                    if geometry_strategy
                    else f"{safe_str(base_plan.get('name'))}:{strategy_name}"
                )
                plans.append(row)
    unique: List[Dict[str, Any]] = []
    seen: set[Tuple[str, Tuple[str, ...], Tuple[str, ...]]] = set()
    for plan in plans:
        key = (
            safe_str(plan.get("name")),
            tuple(safe_str(item.get("cluster_id")) for item in safe_list(plan.get("clusters")) if safe_str(safe_dict(item).get("cluster_id"))),
            tuple(safe_str(item) for item in safe_list(plan.get("allowed_candidate_modes")) if safe_str(item)),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(plan)
    return unique[:12]


def _apply_trench_group_prefit(project: ProjectModel, manager: ProjectManager, group: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    mode = safe_str(safe_dict(plan).get("group_prefit_mode"), "balanced")
    if mode == "balanced":
        return {"applied": False, "cluster_prefits": [], "changed_systems": [], "added_structures": 0, "grading_notes": []}
    changed_systems: set[str] = set()
    added_structures = 0
    grading_notes: List[Dict[str, Any]] = []
    cluster_prefits: List[Dict[str, Any]] = []
    for cluster in safe_list(safe_dict(plan).get("clusters")):
        prefit = _apply_cluster_trench_prefit(project, manager, safe_dict(cluster), mode)
        if not bool(prefit.get("applied")):
            continue
        changed_systems.update(safe_str(item) for item in safe_list(prefit.get("changed_systems")) if safe_str(item))
        added_structures += safe_int(prefit.get("added_structures"), 0)
        grading_notes.extend(deepcopy(safe_list(prefit.get("grading_notes"))))
        cluster_prefits.append(
            {
                "cluster_id": safe_str(safe_dict(cluster).get("cluster_id")),
                "moved_segments": deepcopy(safe_list(prefit.get("moved_segments"))),
                "notes": deepcopy(safe_list(prefit.get("notes"))),
            }
        )
    return {
        "applied": bool(cluster_prefits),
        "cluster_prefits": cluster_prefits,
        "changed_systems": _canonical_changed_systems(changed_systems),
        "added_structures": added_structures,
        "grading_notes": grading_notes,
    }


def _combined_obstacle_rect(obstacles: Sequence[Dict[str, Any]], *, name: str) -> Optional[Dict[str, Any]]:
    rows = [safe_dict(item) for item in obstacles if safe_dict(item)]
    if not rows:
        return None
    min_x = min(safe_float(item.get("x"), 0.0) - safe_float(item.get("buffer_ft"), 0.0) for item in rows)
    min_y = min(safe_float(item.get("y"), 0.0) - safe_float(item.get("buffer_ft"), 0.0) for item in rows)
    max_x = max(safe_float(item.get("x"), 0.0) + safe_float(item.get("w"), 0.0) + safe_float(item.get("buffer_ft"), 0.0) for item in rows)
    max_y = max(safe_float(item.get("y"), 0.0) + safe_float(item.get("h"), 0.0) + safe_float(item.get("buffer_ft"), 0.0) for item in rows)
    return {
        "name": name,
        "kind": "group_geometry_window",
        "x": round(min_x, 3),
        "y": round(min_y, 3),
        "w": round(max(max_x - min_x, 1.0), 3),
        "h": round(max(max_y - min_y, 1.0), 3),
        "buffer_ft": 4.0,
        "penalty": round(sum(safe_float(item.get("penalty"), 0.0) for item in rows) / max(len(rows), 1), 3),
        "avoid": any(bool(item.get("avoid")) for item in rows),
    }


def _apply_group_geometry_strategy_prefit(project: ProjectModel, manager: ProjectManager, group: Dict[str, Any], geometry_strategy: str) -> Dict[str, Any]:
    if safe_str(geometry_strategy) != "shared_corridor_escape":
        return {"applied": False, "changed_systems": [], "added_structures": 0, "grading_notes": [], "notes": [], "rerouted_segments": []}
    conflicts = [
        safe_dict(item)
        for item in safe_list(safe_dict(group).get("conflicts"))
        if safe_dict(item) and safe_str(item.get("conflict_type")).endswith("_geometry")
    ]
    if not conflicts:
        return {"applied": False, "changed_systems": [], "added_structures": 0, "grading_notes": [], "notes": [], "rerouted_segments": []}
    protected_zones = _expanded_obstacle_rectangles(project)
    obstacle_names = {
        safe_str(name)
        for conflict in conflicts
        for name in safe_list(safe_dict(conflict).get("involved_objects"))
        if safe_str(name) and any(safe_str(safe_dict(zone).get("name")) == safe_str(name) for zone in protected_zones)
    }
    target_obstacles = [zone for zone in protected_zones if safe_str(safe_dict(zone).get("name")) in obstacle_names]
    union_rect = _combined_obstacle_rect(target_obstacles, name="GROUP_GEOMETRY_ESCAPE")
    if union_rect is None:
        return {"applied": False, "changed_systems": [], "added_structures": 0, "grading_notes": [], "notes": [], "rerouted_segments": []}

    segment_names: List[str] = []
    for conflict in conflicts:
        for name in safe_list(safe_dict(conflict).get("involved_objects")):
            target_name = safe_str(name)
            found = _find_summary_segment(project, manager, target_name)
            if found is None:
                continue
            system_name, _rec = found
            if safe_str(system_name) in {"sanitary", "water", "storm", "utilities"} and target_name not in segment_names:
                segment_names.append(target_name)
    if not segment_names:
        return {"applied": False, "changed_systems": [], "added_structures": 0, "grading_notes": [], "notes": [], "rerouted_segments": []}

    orientation = safe_str(group.get("corridor_axis"))
    axis_value = safe_float(group.get("axis_value"), 0.0)
    union_x0 = safe_float(union_rect.get("x"), 0.0) - 4.0
    union_y0 = safe_float(union_rect.get("y"), 0.0) - 4.0
    union_x1 = safe_float(union_rect.get("x"), 0.0) + safe_float(union_rect.get("w"), 0.0) + 4.0
    union_y1 = safe_float(union_rect.get("y"), 0.0) + safe_float(union_rect.get("h"), 0.0) + 4.0
    if orientation == "horizontal":
        detour_primary = union_y0 if abs(axis_value - union_y0) <= abs(axis_value - union_y1) else union_y1
    elif orientation == "vertical":
        detour_primary = union_x0 if abs(axis_value - union_x0) <= abs(axis_value - union_x1) else union_x1
    else:
        detour_primary = union_y0

    changed_systems: set[str] = set()
    notes: List[str] = []
    rerouted_segments: List[Dict[str, Any]] = []
    grading_notes: List[Dict[str, Any]] = []
    added_structures = 0
    for target_name in segment_names:
        found = _find_summary_segment(project, manager, target_name)
        if found is None:
            continue
        system_name, rec = found
        before_path = [
            [safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)]
            for pt in safe_list(rec.get("route_points") or rec.get("path"))
            if isinstance(pt, (list, tuple)) and len(pt) >= 2
        ]
        if len(before_path) < 2:
            continue
        start = deepcopy(before_path[0])
        end = deepcopy(before_path[-1])
        if _point_inside_buffered_rect(start, union_rect):
            start = _snap_point_outside_buffered_rect(start, union_rect, before_path[1] if len(before_path) > 1 else end)
        if _point_inside_buffered_rect(end, union_rect):
            end = _snap_point_outside_buffered_rect(end, union_rect, before_path[-2] if len(before_path) > 1 else start)
        preference = _preferred_corridor_for_segment(project, {"system": safe_str(system_name), **rec})
        synthetic_cluster = {
            "corridor_axis": orientation,
            "axis_value": detour_primary,
            "trench_like": True,
        }
        candidates = _geometry_candidate_paths(
            [start, *before_path[1:-1], end] if len(before_path) > 2 else [start, end],
            union_rect,
            preference,
            candidate_mode="corridor_bias",
            cluster_context=synthetic_cluster,
            protected_zones=protected_zones,
        )
        if not candidates:
            continue
        if orientation == "horizontal":
            chosen_row = min(
                candidates,
                key=lambda row: (
                    sum(abs(safe_float(pt[1], 0.0) - detour_primary) for pt in safe_list(row.get("path"))) / max(len(safe_list(row.get("path"))), 1),
                    safe_float(row.get("protected_penalty"), 0.0),
                    safe_float(row.get("corridor_penalty"), 0.0),
                    safe_float(row.get("added_length_ft"), 0.0),
                ),
            )
        else:
            chosen_row = min(
                candidates,
                key=lambda row: (
                    sum(abs(safe_float(pt[0], 0.0) - detour_primary) for pt in safe_list(row.get("path"))) / max(len(safe_list(row.get("path"))), 1),
                    safe_float(row.get("protected_penalty"), 0.0),
                    safe_float(row.get("corridor_penalty"), 0.0),
                    safe_float(row.get("added_length_ft"), 0.0),
                ),
            )
        after_path = deepcopy(safe_list(chosen_row.get("path")))
        if not after_path or after_path == before_path:
            continue
        if "route_points" in rec:
            rec["route_points"] = after_path
        else:
            rec["path"] = after_path
        length_ft = polyline_length(after_path)
        rec["length_ft"] = round(length_ft, 3)
        if safe_float(rec.get("slope_ft_ft"), 0.0) > 0.0:
            start_invert = safe_float(rec.get("start_invert_ft", rec.get("start_invert", DEFAULT_PAD_ELEV - 4.0)), DEFAULT_PAD_ELEV - 4.0)
            drop = safe_float(rec.get("slope_ft_ft"), 0.0) * length_ft
            if "end_invert_ft" in rec:
                rec["end_invert_ft"] = round(start_invert - drop, 3)
            elif "end_invert" in rec:
                rec["end_invert"] = round(start_invert - drop, 3)
        structure_info = _apply_structure_insertion_rules(project, manager, safe_str(system_name), safe_str(rec.get("name"), target_name), after_path)
        grading_note = _apply_local_grading_repair(project, safe_str(rec.get("name"), target_name), delta_depth_ft=max(length_ft - polyline_length(before_path), 0.0) * 0.02, point=_segment_midpoint(after_path))
        changed_systems.add(safe_str(system_name))
        added_structures += safe_int(structure_info.get("added_count"), 0)
        grading_notes.append(deepcopy(grading_note))
        rerouted_segments.append(
            {
                "name": safe_str(rec.get("name"), target_name),
                "system": safe_str(system_name),
                "before_length_ft": round(polyline_length(before_path), 3),
                "after_length_ft": round(length_ft, 3),
                "source_mode": safe_str(chosen_row.get("source_mode")),
            }
        )
        notes.append(f"Group geometry strategy shared_corridor_escape rerouted {safe_str(rec.get('name'), target_name)} around combined protected geometry.")
    return {
        "applied": bool(rerouted_segments),
        "changed_systems": _canonical_changed_systems(changed_systems),
        "added_structures": added_structures,
        "grading_notes": grading_notes,
        "notes": notes,
        "rerouted_segments": rerouted_segments,
    }


def _coordination_failure_tags(candidate_summaries: Sequence[Dict[str, Any]], best_near_valid_candidate: Dict[str, Any]) -> List[str]:
    summaries = [safe_dict(item) for item in candidate_summaries if safe_dict(item)]
    best = safe_dict(best_near_valid_candidate)
    if not summaries:
        return ["missing_candidate_family"]
    tags: List[str] = []
    if all(not safe_list(item.get("changed_systems")) for item in summaries):
        tags.append("missing_route_options")
    if any(bool(item.get("crossing_blocked")) for item in summaries):
        tags.append("crossing_hierarchy")
    if any(bool(item.get("grading_blocked")) for item in summaries):
        tags.append("grading_validity")
    if any(safe_float(item.get("protected_zone_penalty"), 0.0) > 0.0 for item in summaries):
        tags.append("protected_zone")
    if any(bool(item.get("geometry_prefit_applied")) for item in summaries):
        tags.append("corridor_trench_group")
    if any(safe_int(item.get("corridor_switch_count"), 0) > 0 for item in summaries):
        tags.append("corridor_switching")
    if best and not bool(safe_dict(best.get("post_validation")).get("valid", True)):
        tags.append("downstream_validation")
    return dedupe_keep_order(tags)


def _coordination_conflict_report_id(conflict: Dict[str, Any]) -> str:
    rec = safe_dict(conflict)
    signature = _conflict_signature(rec)
    location = _conflict_location(rec)
    station = safe_float(rec.get("station_ft"), 0.0)
    return "::".join(
        [
            safe_str(signature[0], "conflict"),
            "-".join(signature[1]) or "unknown",
            f"{location[0]:.1f},{location[1]:.1f}",
            f"{station:.1f}",
        ]
    )


def _coordination_conflict_rule(conflict: Dict[str, Any]) -> Dict[str, Any]:
    rec = safe_dict(conflict)
    rule_keys = (
        "required_horizontal_clearance_ft",
        "actual_horizontal_clearance_ft",
        "required_vertical_clearance_ft",
        "actual_vertical_clearance_ft",
        "required_clearance_ft",
        "actual_clearance_ft",
        "required_slope_ft_ft",
        "actual_slope_ft_ft",
        "preferred_lower_system",
        "preferred_crossing_angle_deg",
        "crossing_angle_deg",
        "interaction_type",
    )
    return {
        "conflict_id": _coordination_conflict_report_id(rec),
        "conflict_type": safe_str(rec.get("conflict_type")),
        "systems": deepcopy(safe_list(rec.get("systems"))),
        "involved_objects": deepcopy(safe_list(rec.get("involved_objects"))),
        "severity": safe_str(rec.get("severity")),
        "location": deepcopy(_conflict_location(rec)),
        "rules": {key: deepcopy(rec.get(key)) for key in rule_keys if key in rec},
    }


def _coordination_post_validation_failures(post_validation: Dict[str, Any]) -> List[Dict[str, Any]]:
    validation = safe_dict(post_validation)
    failures: List[Dict[str, Any]] = []
    for system_name, payload in safe_dict(validation.get("systems")).items():
        rec = safe_dict(payload)
        if rec and not bool(rec.get("valid", True)):
            failures.append({"system": safe_str(system_name), "details": deepcopy(rec)})
    for field_name, value in safe_dict(validation.get("consistency")).items():
        if not bool(value):
            failures.append({"system": "consistency", "field": safe_str(field_name), "details": {"valid": False}})
    if validation and not bool(validation.get("valid", True)) and not failures:
        failures.append({"system": "post_validation", "details": deepcopy(validation)})
    return failures


def _coordination_failure_breakdown(
    *,
    remaining_conflicts: Sequence[Dict[str, Any]] = (),
    post_validation: Optional[Dict[str, Any]] = None,
    protected_zone_hits: Sequence[Dict[str, Any]] = (),
    engineering_deltas: Optional[Dict[str, Any]] = None,
    assumption_used: bool = False,
    rejected_reason: str = "",
) -> Dict[str, Any]:
    remaining = [safe_dict(item) for item in safe_list(remaining_conflicts) if safe_dict(item)]
    deltas = safe_dict(engineering_deltas)
    protected_impact = safe_dict(deltas.get("protected_zone_impact"))
    grading_impact = safe_dict(deltas.get("grading_impact"))
    crossing_hierarchy = safe_dict(deltas.get("crossing_hierarchy"))
    constructability = safe_dict(deltas.get("constructability_impact"))
    hits = [safe_dict(item) for item in safe_list(protected_zone_hits) if safe_dict(item)]
    if not hits and safe_int(protected_impact.get("hit_count"), 0) > 0:
        hits = [
            {
                "kind": safe_str(kind),
                "penalty": safe_float(protected_impact.get("penalty"), 0.0),
            }
            for kind in safe_list(protected_impact.get("hit_kinds"))
            if safe_str(kind)
        ]
    post_failures = _coordination_post_validation_failures(safe_dict(post_validation or {}))
    return {
        "remaining_conflict_ids": [_coordination_conflict_report_id(item) for item in remaining],
        "remaining_conflict_rules": [_coordination_conflict_rule(item) for item in remaining],
        "post_validation_failures": post_failures,
        "protected_zone_hits": deepcopy(hits),
        "grading_blocked": bool(grading_impact.get("blocked")),
        "crossing_hierarchy_blocked": bool(crossing_hierarchy.get("blocked")),
        "assumption_used": bool(assumption_used),
        "constructability_penalties": {
            "score": round(safe_float(constructability.get("score"), 0.0), 3),
            "bend_complexity": safe_int(constructability.get("bend_complexity"), 0),
            "protected_zone_penalty": round(safe_float(constructability.get("protected_zone_penalty"), safe_float(protected_impact.get("penalty"), 0.0)), 3),
            "corridor_switch_count": safe_int(deltas.get("corridor_switch_count"), 0),
            "fragmentation_penalty": round(safe_float(deltas.get("fragmentation_penalty"), 0.0), 3),
        },
        "unresolved_systems": sorted(
            {
                safe_str(system)
                for conflict in remaining
                for system in safe_list(conflict.get("systems"))
                if safe_str(system)
            }
        ),
        "rejected_reason": safe_str(rejected_reason),
    }


def _apply_group_crossing_strategy_prefit(project: ProjectModel, manager: ProjectManager, group: Dict[str, Any], crossing_strategy: str) -> Dict[str, Any]:
    strategy_name = safe_str(crossing_strategy)
    if strategy_name not in {"upper_reroute_first", "parallel_shift_first"}:
        return {"applied": False, "changed_systems": [], "added_structures": 0, "grading_notes": [], "notes": [], "rerouted_segments": []}
    conflicts = [safe_dict(item) for item in safe_list(safe_dict(group).get("conflicts")) if safe_dict(item) and safe_str(item.get("conflict_type")).endswith("_clearance")]
    if not conflicts:
        return {"applied": False, "changed_systems": [], "added_structures": 0, "grading_notes": [], "notes": [], "rerouted_segments": []}
    changed_systems: set[str] = set()
    notes: List[str] = []
    rerouted_segments: List[Dict[str, Any]] = []
    grading_notes: List[Dict[str, Any]] = []
    added_structures = 0
    protected_zones = _expanded_obstacle_rectangles(project)
    for conflict in conflicts:
        interaction_type = safe_str(conflict.get("interaction_type"), "crossing")
        if strategy_name == "parallel_shift_first" and interaction_type != "parallel":
            continue
        preferred_lower = safe_str(conflict.get("preferred_lower_system"))
        names = [safe_str(name) for name in safe_list(conflict.get("involved_objects")) if safe_str(name)]
        candidate_names = [name for name in names if safe_str(_find_summary_segment(project, manager, name)[0] if _find_summary_segment(project, manager, name) else "") != preferred_lower]
        for name in candidate_names:
            found = _find_summary_segment(project, manager, name)
            if found is None:
                continue
            target_system, rec = found
            current_path = [
                [safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)]
                for pt in safe_list(rec.get("route_points") or rec.get("path"))
                if isinstance(pt, (list, tuple)) and len(pt) >= 2
            ]
            if len(current_path) < 2:
                continue
            point = safe_list(conflict.get("location")) if isinstance(conflict.get("location"), (list, tuple)) else _segment_midpoint(current_path)
            required_h = max(safe_float(conflict.get("required_horizontal_clearance_ft"), 0.0), 8.0)
            synthetic_rect = {
                "name": f"{name}-GROUP-CROSSING",
                "kind": "crossing_window",
                "x": safe_float(point[0], 0.0) - required_h / 2.0,
                "y": safe_float(point[1], 0.0) - required_h / 2.0,
                "w": required_h,
                "h": required_h,
                "buffer_ft": max(required_h / 2.0, 4.0),
                "penalty": 30.0,
                "avoid": False,
            }
            preference = _preferred_corridor_for_segment(project, {"system": safe_str(target_system), **rec})
            candidates = _geometry_candidate_paths(
                current_path,
                synthetic_rect,
                preference,
                candidate_mode="corridor_bias",
                cluster_context=None,
                protected_zones=protected_zones,
            )
            chosen: Optional[List[List[float]]] = None
            for row in candidates:
                candidate_path = deepcopy(safe_list(row.get("path")))
                if candidate_path and candidate_path != current_path:
                    chosen = candidate_path
                    break
            if chosen is None:
                continue
            if "route_points" in rec:
                rec["route_points"] = chosen
            else:
                rec["path"] = chosen
            length_ft = polyline_length(chosen)
            rec["length_ft"] = round(length_ft, 3)
            if safe_float(rec.get("slope_ft_ft"), 0.0) > 0.0:
                start_invert = safe_float(rec.get("start_invert_ft", rec.get("start_invert", DEFAULT_PAD_ELEV - 4.0)), DEFAULT_PAD_ELEV - 4.0)
                drop = safe_float(rec.get("slope_ft_ft"), 0.0) * length_ft
                if "end_invert_ft" in rec:
                    rec["end_invert_ft"] = round(start_invert - drop, 3)
                elif "end_invert" in rec:
                    rec["end_invert"] = round(start_invert - drop, 3)
            structure_info = _apply_structure_insertion_rules(project, manager, safe_str(target_system), safe_str(rec.get("name"), name), chosen)
            grading_note = _apply_local_grading_repair(project, safe_str(rec.get("name"), name), delta_depth_ft=max(length_ft - polyline_length(current_path), 0.0) * 0.02, point=_segment_midpoint(chosen))
            changed_systems.add(safe_str(target_system))
            added_structures += safe_int(structure_info.get("added_count"), 0)
            grading_notes.append(deepcopy(grading_note))
            rerouted_segments.append(
                {
                    "name": safe_str(rec.get("name"), name),
                    "system": safe_str(target_system),
                    "before_length_ft": round(polyline_length(current_path), 3),
                    "after_length_ft": round(length_ft, 3),
                }
            )
            notes.append(f"Group crossing strategy {strategy_name} rerouted {safe_str(rec.get('name'), name)} before cluster solving.")
    return {
        "applied": bool(rerouted_segments),
        "changed_systems": _canonical_changed_systems(changed_systems),
        "added_structures": added_structures,
        "grading_notes": grading_notes,
        "notes": notes,
        "rerouted_segments": rerouted_segments,
    }


def _solve_conflict_cluster(
    project: ProjectModel,
    manager: ProjectManager,
    cluster: Dict[str, Any],
    assisted_mode: bool,
    allowed_candidate_modes: Optional[Sequence[str]] = None,
    crossing_strategy: str = "",
    metrics: Optional[Dict[str, Any]] = None,
    structure_analysis_cache: Optional[Dict[Tuple[str, str, Tuple[Tuple[float, float], ...]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    started = perf_counter()
    base_snapshot = _snapshot_coordination_state(project, manager)
    base_full_snapshot = _full_coordination_state_snapshot(project, manager)
    initial_conflicts = _detect_coordination_conflicts(project, manager)
    initial_related = _cluster_remaining_conflicts(initial_conflicts, cluster)
    candidate_orders = _cluster_candidate_orders(cluster)
    _coordination_metric_inc(metrics, ["candidate_counts", "cluster_orders_total"], len(candidate_orders))
    allowed_modes = {safe_str(item) for item in safe_list(allowed_candidate_modes) if safe_str(item)}
    if allowed_modes:
        filtered_orders = [deepcopy(row) for row in candidate_orders if safe_str(safe_dict(row).get("candidate_mode")) in allowed_modes]
        if filtered_orders:
            candidate_orders = filtered_orders
    order_priority = {"balanced": 0, "trench_cluster": 1, "corridor_bias": 2, "protected_zone_bias": 3}
    candidate_orders = sorted(
        candidate_orders,
        key=lambda row: (
            order_priority.get(safe_str(safe_dict(row).get("candidate_mode")), 99),
            0 if safe_str(safe_dict(row).get("order_name")) == "priority" else 1,
            safe_str(safe_dict(row).get("name")),
        ),
    )[:4]
    for order in candidate_orders:
        conflicts_for_order = safe_list(safe_dict(order).get("conflicts"))
        if len(conflicts_for_order) > MAX_COORDINATION_CONFLICTS_PER_CANDIDATE:
            order["conflicts"] = conflicts_for_order[:MAX_COORDINATION_CONFLICTS_PER_CANDIDATE]
            prune_reasons = safe_dict(metrics.get("prune_reasons")) if isinstance(metrics, dict) else {}
            if isinstance(metrics, dict):
                metrics["prune_reasons"] = prune_reasons
            prune_reasons["cluster_conflict_attempt_cap"] = (
                safe_int(prune_reasons.get("cluster_conflict_attempt_cap"), 0)
                + len(conflicts_for_order)
                - MAX_COORDINATION_CONFLICTS_PER_CANDIDATE
            )
    total_cluster_orders = safe_int(safe_dict(metrics or {}).get("candidate_counts", {}).get("cluster_orders_total"), 0)
    if total_cluster_orders > len(candidate_orders):
        prune_count = total_cluster_orders - len(candidate_orders)
        prune_reasons = safe_dict(metrics.get("prune_reasons")) if isinstance(metrics, dict) else {}
        if isinstance(metrics, dict):
            metrics["prune_reasons"] = prune_reasons
        prune_reasons["cluster_order_cap"] = safe_int(prune_reasons.get("cluster_order_cap"), 0) + prune_count
    _coordination_metric_inc(metrics, ["candidate_counts", "cluster_orders_kept"], len(candidate_orders))
    best_valid: Optional[Dict[str, Any]] = None
    best_valid_snapshot: Optional[Dict[str, Any]] = None
    best_valid_full_snapshot: Optional[Dict[str, Any]] = None
    best_near_valid: Optional[Dict[str, Any]] = None
    candidate_summaries: List[Dict[str, Any]] = []

    for order in candidate_orders:
        _restore_full_coordination_state(project, manager, base_full_snapshot)
        candidate_changed_systems: set[str] = set()
        candidate_resolution_rows: List[Dict[str, Any]] = []
        candidate_assumptions: List[Dict[str, Any]] = []
        failed_reason = ""
        prefit = _apply_cluster_trench_prefit(project, manager, cluster, safe_str(order.get("candidate_mode"), "balanced"))
        if bool(prefit.get("applied")):
            candidate_changed_systems.update(safe_str(item) for item in safe_list(prefit.get("changed_systems")) if safe_str(item))
            candidate_resolution_rows.append(
                {
                    "conflict_type": "cluster_prefit",
                    "involved_objects": deepcopy([safe_str(item.get("name")) for item in safe_list(prefit.get("moved_segments")) if safe_str(safe_dict(item).get("name"))]),
                    "strategy": f"cluster_prefit:{safe_str(order.get('candidate_mode'), 'balanced')}",
                    "notes": deepcopy(safe_list(prefit.get("notes"))),
                    "constructability": {},
                    "engineering_deltas": {},
                }
            )
        for original_conflict in safe_list(order.get("conflicts")):
            current_conflicts = _detect_coordination_conflicts(project, manager)
            matching = _matching_conflicts(current_conflicts, original_conflict)
            if not matching:
                continue
            active_conflict = matching[0]
            attempt_full_snapshot = _full_coordination_state_snapshot(project, manager)
            resolution = _apply_conflict_resolution(
                project,
                manager,
                active_conflict,
                assisted_mode=assisted_mode,
                candidate_mode=safe_str(order.get("candidate_mode"), "balanced"),
                cluster_context=cluster,
                crossing_strategy=crossing_strategy,
                metrics=metrics,
                structure_analysis_cache=structure_analysis_cache,
            )
            if resolution.get("success"):
                candidate_changed_systems.update(safe_str(item) for item in safe_list(resolution.get("changed_systems")) if safe_str(item))
                candidate_resolution_rows.append(
                    {
                        "conflict_type": safe_str(active_conflict.get("conflict_type")),
                        "involved_objects": deepcopy(safe_list(active_conflict.get("involved_objects"))),
                        "strategy": safe_str(resolution.get("strategy")),
                        "notes": deepcopy(safe_list(resolution.get("notes"))),
                        "constructability": deepcopy(safe_dict(resolution.get("constructability"))),
                        "engineering_deltas": deepcopy(safe_dict(resolution.get("engineering_deltas"))),
                    }
                )
            else:
                failed_reason = safe_str(resolution.get("failure_reason")) or "A cluster candidate could not resolve one of its member conflicts."
                _restore_full_coordination_state(project, manager, attempt_full_snapshot)
                if resolution.get("assumed"):
                    candidate_assumptions.append(
                        {
                            "conflict_type": safe_str(active_conflict.get("conflict_type")),
                            "involved_objects": deepcopy(safe_list(active_conflict.get("involved_objects"))),
                            "reason": failed_reason,
                        }
                    )
                if not assisted_mode:
                    break

        _refresh_conflict_resolved_state(project, manager, sorted(candidate_changed_systems))
        post_conflicts = _detect_coordination_conflicts(project, manager)
        remaining_related = _cluster_remaining_conflicts(post_conflicts, cluster)
        validations = _post_reroute_validations(project, manager, sorted(candidate_changed_systems))
        constructability_total = round(
            sum(safe_float(safe_dict(item.get("constructability")).get("score"), 0.0) for item in candidate_resolution_rows),
            3,
        )
        overall_deltas = _resolution_engineering_deltas(
            base_snapshot,
            project,
            manager,
            sorted(candidate_changed_systems),
            pre_conflicts=initial_conflicts,
            post_conflicts=post_conflicts,
        )
        overall_deltas["cluster_prefit"] = {
            "applied": bool(prefit.get("applied")),
            "moved_segment_count": len(safe_list(prefit.get("moved_segments"))),
            "added_structures": safe_int(prefit.get("added_structures"), 0),
        }
        merged_resolution_deltas = _merge_engineering_deltas([safe_dict(item.get("engineering_deltas")) for item in candidate_resolution_rows if safe_dict(item.get("engineering_deltas"))])
        for key in ("protected_zone_impact", "grading_impact", "constructability_impact", "crossing_hierarchy"):
            if key in merged_resolution_deltas:
                overall_deltas[key] = deepcopy(safe_dict(merged_resolution_deltas.get(key)))
        score = round(
            len(remaining_related) * 800.0
            + len(post_conflicts) * 150.0
            + (0.0 if validations.get("valid") else 700.0)
            + constructability_total
            + safe_float(safe_dict(overall_deltas.get("crossing_hierarchy")).get("penalty"), 0.0)
            + safe_float(safe_dict(overall_deltas.get("grading_impact")).get("score"), 0.0)
            + len(candidate_assumptions) * 120.0,
            3,
        )
        candidate = {
            "cluster_id": safe_str(cluster.get("cluster_id")),
            "order_name": safe_str(order.get("name")),
            "candidate_mode": safe_str(order.get("candidate_mode"), "balanced"),
            "candidate_count": len(candidate_orders),
            "changed_systems": _canonical_changed_systems(candidate_changed_systems),
            "valid": len(remaining_related) == 0 and bool(validations.get("valid")) and not candidate_assumptions,
            "score": score,
            "remaining_cluster_conflicts": deepcopy(remaining_related),
            "remaining_total_conflicts": len(post_conflicts),
            "constructability_score": constructability_total,
            "resolution_rows": candidate_resolution_rows,
            "engineering_deltas": overall_deltas,
            "assumptions": candidate_assumptions,
            "post_validation": validations,
            "why_failed": failed_reason or ("Cluster still had related conflicts after candidate application." if remaining_related else "Cluster candidate failed downstream validation."),
        }
        candidate["coordination_realism"] = _coordination_realism_summary_impl(candidate, group=cluster)
        candidate["failure_breakdown"] = _coordination_failure_breakdown(
            remaining_conflicts=remaining_related,
            post_validation=validations,
            engineering_deltas=overall_deltas,
            assumption_used=bool(candidate_assumptions),
            rejected_reason=safe_str(candidate.get("why_failed")),
        )
        candidate_summaries.append(
            {
                "order_name": safe_str(candidate.get("order_name")),
                "candidate_mode": safe_str(candidate.get("candidate_mode")),
                "valid": bool(candidate.get("valid")),
                "score": safe_float(candidate.get("score"), 0.0),
                "constructability_score": safe_float(candidate.get("constructability_score"), 0.0),
                "remaining_cluster_conflicts": len(remaining_related),
                "changed_systems": deepcopy(safe_list(candidate.get("changed_systems"))),
                "crossing_blocked": bool(safe_dict(safe_dict(overall_deltas.get("crossing_hierarchy")).get("blocked"))),
                "grading_blocked": bool(safe_dict(safe_dict(overall_deltas.get("grading_impact")).get("blocked"))),
                "protected_zone_penalty": safe_float(safe_dict(safe_dict(overall_deltas.get("protected_zone_impact")).get("penalty")), 0.0),
                "coordination_realism": deepcopy(safe_dict(candidate.get("coordination_realism"))),
                "failure_reason": safe_str(candidate.get("why_failed")),
                "failure_breakdown": deepcopy(safe_dict(candidate.get("failure_breakdown"))),
            }
        )
        if candidate["valid"]:
            if best_valid is None or safe_float(candidate.get("score"), 0.0) < safe_float(best_valid.get("score"), 1e9):
                best_valid = candidate
                best_valid_snapshot = _snapshot_coordination_state(project, manager)
                best_valid_full_snapshot = _full_coordination_state_snapshot(project, manager)
        elif best_near_valid is None or safe_float(candidate.get("score"), 0.0) < safe_float(best_near_valid.get("score"), 1e9):
            best_near_valid = candidate

    if best_valid is not None and best_valid_snapshot is not None:
        _coordination_metric_inc(metrics, ["timings_ms", "solve_conflict_cluster"], round((perf_counter() - started) * 1000.0, 3))
        if best_valid_full_snapshot is not None:
            _restore_full_coordination_state(project, manager, best_valid_full_snapshot)
        else:
            _restore_coordination_state(project, manager, best_valid_snapshot)
        return {
            "success": True,
            "cluster_id": safe_str(cluster.get("cluster_id")),
            "candidate_count": len(candidate_orders),
            "selected_order": safe_str(best_valid.get("order_name")),
            "selected_candidate_mode": safe_str(best_valid.get("candidate_mode")),
            "changed_systems": deepcopy(safe_list(best_valid.get("changed_systems"))),
            "resolution_rows": deepcopy(safe_list(best_valid.get("resolution_rows"))),
            "constructability_score": safe_float(best_valid.get("constructability_score"), 0.0),
            "engineering_deltas": deepcopy(safe_dict(best_valid.get("engineering_deltas"))),
            "best_near_valid_candidate": deepcopy(safe_dict(best_near_valid or {})),
            "coordination_realism": deepcopy(safe_dict(best_valid.get("coordination_realism"))),
            "post_validation": deepcopy(safe_dict(best_valid.get("post_validation"))),
            "remaining_cluster_conflicts": [],
            "score": safe_float(best_valid.get("score"), 0.0),
            "candidate_summaries": candidate_summaries,
            "selection_reason": (
                f"Selected {safe_str(best_valid.get('order_name'))} because it resolved the cluster with "
                f"{safe_float(safe_dict(best_valid.get('engineering_deltas')).get('added_length_ft'), 0.0):.1f} ft added length, "
                f"{safe_int(safe_dict(best_valid.get('engineering_deltas')).get('added_structures'), 0)} added structures, "
                f"{safe_float(safe_dict(safe_dict(best_valid.get('engineering_deltas')).get('protected_zone_impact')).get('penalty'), 0.0):.1f} protected-zone penalty, and "
                f"{safe_float(safe_dict(safe_dict(best_valid.get('engineering_deltas')).get('crossing_hierarchy')).get('penalty'), 0.0):.1f} crossing-rule penalty under {safe_str(crossing_strategy or 'default_crossing')}."
            ),
            "crossing_strategy": safe_str(crossing_strategy),
        }

    _restore_full_coordination_state(project, manager, base_full_snapshot)
    _coordination_metric_inc(metrics, ["timings_ms", "solve_conflict_cluster"], round((perf_counter() - started) * 1000.0, 3))
    return {
        "success": False,
        "cluster_id": safe_str(cluster.get("cluster_id")),
        "candidate_count": len(candidate_orders),
        "selected_order": "",
        "selected_candidate_mode": "",
        "changed_systems": [],
        "resolution_rows": [],
        "constructability_score": 0.0,
        "engineering_deltas": {},
        "best_near_valid_candidate": deepcopy(safe_dict(best_near_valid or {})),
        "coordination_realism": deepcopy(safe_dict(safe_dict(best_near_valid or {}).get("coordination_realism"))),
        "post_validation": deepcopy(safe_dict(safe_dict(best_near_valid or {}).get("post_validation"))),
        "remaining_cluster_conflicts": deepcopy(initial_related),
        "score": safe_float(safe_dict(best_near_valid or {}).get("score"), 0.0),
        "failure_reason": safe_str(safe_dict(best_near_valid or {}).get("why_failed")) or "No cluster candidate could satisfy the related conflicts without violating downstream validation.",
        "candidate_summaries": candidate_summaries,
        "failure_tags": _coordination_failure_tags(candidate_summaries, safe_dict(best_near_valid or {})),
        "crossing_strategy": safe_str(crossing_strategy),
    }
def _solve_conflict_cluster_group(
    project: ProjectModel,
    manager: ProjectManager,
    group: Dict[str, Any],
    assisted_mode: bool,
    metrics: Optional[Dict[str, Any]] = None,
    structure_analysis_cache: Optional[Dict[Tuple[str, str, Tuple[Tuple[float, float], ...]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    started = perf_counter()
    clusters = [safe_dict(item) for item in safe_list(safe_dict(group).get("clusters")) if safe_dict(item)]
    if not clusters:
        return {"success": True, "cluster_group_id": safe_str(safe_dict(group).get("cluster_group_id")), "candidate_summaries": []}
    if len(clusters) == 1 and not bool(safe_dict(group).get("trench_like")):
        default_crossing_strategy = safe_str(safe_dict(_group_crossing_strategy_options(group)[0]).get("name"))
        result = _solve_conflict_cluster(
            project,
            manager,
            clusters[0],
            assisted_mode=assisted_mode,
            crossing_strategy=default_crossing_strategy,
            metrics=metrics,
            structure_analysis_cache=structure_analysis_cache,
        )
        result["cluster_group_id"] = safe_str(safe_dict(group).get("cluster_group_id"))
        result["group_plan"] = "single_cluster"
        result["selected_group_strategy"] = safe_str(result.get("crossing_strategy"), default_crossing_strategy)
        result["cluster_group_summary"] = {
            "cluster_count": 1,
            "resolved_conflicts": len(safe_list(result.get("resolution_rows"))),
            "added_structures": safe_int(safe_dict(result.get("engineering_deltas")).get("added_structures"), 0),
            "added_length_ft": safe_float(safe_dict(result.get("engineering_deltas")).get("added_length_ft"), 0.0),
            "added_depth_ft": safe_float(safe_dict(result.get("engineering_deltas")).get("added_depth_ft"), 0.0),
            "grading_disturbance_score": safe_float(safe_dict(safe_dict(result.get("engineering_deltas")).get("grading_impact")).get("score"), 0.0),
            "crossing_rule_penalty": safe_float(safe_dict(safe_dict(result.get("engineering_deltas")).get("crossing_hierarchy")).get("penalty"), 0.0),
            "crossing_strategy": safe_str(result.get("crossing_strategy"), default_crossing_strategy),
        }
        return result

    base_snapshot = _snapshot_coordination_state(project, manager)
    base_full_snapshot = _full_coordination_state_snapshot(project, manager)
    initial_conflicts = _detect_coordination_conflicts(project, manager)
    initial_related = _cluster_group_remaining_conflicts(initial_conflicts, group)
    group_plans = _cluster_group_candidate_plans(project, manager, group)
    _coordination_metric_inc(metrics, ["candidate_counts", "group_plans_total"], len(group_plans))
    group_plans = sorted(
        group_plans,
        key=lambda plan: (
            0 if bool(safe_dict(plan).get("group_prefit")) else 1,
            0 if safe_str(safe_dict(plan).get("crossing_strategy")) == "hierarchy_first" else 1,
            0 if safe_str(safe_dict(plan).get("geometry_strategy")) == "balanced_group" else 1,
            safe_str(safe_dict(plan).get("name")),
        ),
    )[:6]
    for plan in group_plans:
        clusters_for_plan = safe_list(safe_dict(plan).get("clusters"))
        if len(clusters_for_plan) > MAX_COORDINATION_CLUSTERS_PER_GROUP_PLAN:
            plan["clusters"] = clusters_for_plan[:MAX_COORDINATION_CLUSTERS_PER_GROUP_PLAN]
            prune_reasons = safe_dict(metrics.get("prune_reasons")) if isinstance(metrics, dict) else {}
            if isinstance(metrics, dict):
                metrics["prune_reasons"] = prune_reasons
            prune_reasons["group_cluster_attempt_cap"] = (
                safe_int(prune_reasons.get("group_cluster_attempt_cap"), 0)
                + len(clusters_for_plan)
                - MAX_COORDINATION_CLUSTERS_PER_GROUP_PLAN
            )
    total_group_plans = safe_int(safe_dict(metrics or {}).get("candidate_counts", {}).get("group_plans_total"), 0)
    if total_group_plans > len(group_plans):
        prune_count = total_group_plans - len(group_plans)
        prune_reasons = safe_dict(metrics.get("prune_reasons")) if isinstance(metrics, dict) else {}
        if isinstance(metrics, dict):
            metrics["prune_reasons"] = prune_reasons
        prune_reasons["group_plan_cap"] = safe_int(prune_reasons.get("group_plan_cap"), 0) + prune_count
    _coordination_metric_inc(metrics, ["candidate_counts", "group_plans_kept"], len(group_plans))
    best_valid: Optional[Dict[str, Any]] = None
    best_valid_snapshot: Optional[Dict[str, Any]] = None
    best_near_valid: Optional[Dict[str, Any]] = None
    candidate_summaries: List[Dict[str, Any]] = []

    for plan in group_plans:
        _restore_full_coordination_state(project, manager, base_full_snapshot)
        changed_systems: set[str] = set()
        cluster_results: List[Dict[str, Any]] = []
        cluster_rows: List[Dict[str, Any]] = []
        failed_reason = ""
        assumptions: List[Dict[str, Any]] = []
        geometry_prefit = _apply_group_geometry_strategy_prefit(project, manager, group, safe_str(plan.get("geometry_strategy")))
        changed_systems.update(safe_str(item) for item in safe_list(geometry_prefit.get("changed_systems")) if safe_str(item))
        crossing_prefit = _apply_group_crossing_strategy_prefit(project, manager, group, safe_str(plan.get("crossing_strategy")))
        changed_systems.update(safe_str(item) for item in safe_list(crossing_prefit.get("changed_systems")) if safe_str(item))
        group_prefit = _apply_trench_group_prefit(project, manager, group, plan)
        changed_systems.update(safe_str(item) for item in safe_list(group_prefit.get("changed_systems")) if safe_str(item))
        for original_cluster in safe_list(plan.get("clusters")):
            current_conflicts = _detect_coordination_conflicts(project, manager)
            if not current_conflicts:
                break
            current_clusters = _group_conflict_clusters(current_conflicts, project)
            matched = _matching_cluster(current_clusters, safe_dict(original_cluster))
            if matched is None:
                continue
            result = _solve_conflict_cluster(
                project,
                manager,
                matched,
                assisted_mode=assisted_mode,
                allowed_candidate_modes=safe_list(plan.get("allowed_candidate_modes")),
                crossing_strategy=safe_str(plan.get("crossing_strategy")),
                metrics=metrics,
                structure_analysis_cache=structure_analysis_cache,
            )
            cluster_results.append(deepcopy(result))
            if not bool(result.get("success")):
                failed_reason = safe_str(result.get("failure_reason")) or "A trench-group candidate failed to solve one of its member clusters."
                if bool(result.get("assumed")):
                    assumptions.append({"cluster_id": safe_str(matched.get("cluster_id")), "reason": failed_reason})
                if not assisted_mode:
                    break
            else:
                changed_systems.update(safe_str(item) for item in safe_list(result.get("changed_systems")) if safe_str(item))
                cluster_rows.extend(deepcopy(safe_list(result.get("resolution_rows"))))

        _refresh_conflict_resolved_state(project, manager, sorted(changed_systems))
        post_conflicts = _detect_coordination_conflicts(project, manager)
        remaining_related = _cluster_group_remaining_conflicts(post_conflicts, group)
        validations = _post_reroute_validations(project, manager, sorted(changed_systems))
        overall_deltas = _resolution_engineering_deltas(
            base_snapshot,
            project,
            manager,
            sorted(changed_systems),
            pre_conflicts=initial_conflicts,
            post_conflicts=post_conflicts,
        )
        merged_cluster_deltas = _merge_engineering_deltas(
            [safe_dict(item.get("engineering_deltas")) for item in cluster_results if safe_dict(item.get("engineering_deltas"))]
        )
        for key in ("protected_zone_impact", "grading_impact", "constructability_impact", "crossing_hierarchy"):
            if key in merged_cluster_deltas:
                overall_deltas[key] = deepcopy(safe_dict(merged_cluster_deltas.get(key)))
        overall_deltas["crossing_strategy_prefit"] = {
            "applied": bool(crossing_prefit.get("applied")),
            "rerouted_segments": len(safe_list(crossing_prefit.get("rerouted_segments"))),
            "added_structures": safe_int(crossing_prefit.get("added_structures"), 0),
        }
        overall_deltas["geometry_strategy_prefit"] = {
            "applied": bool(geometry_prefit.get("applied")),
            "rerouted_segments": len(safe_list(geometry_prefit.get("rerouted_segments"))),
            "added_structures": safe_int(geometry_prefit.get("added_structures"), 0),
            "strategy": safe_str(plan.get("geometry_strategy")),
        }
        corridor_switch_count = 0
        prior_mode = ""
        for row in cluster_results:
            mode = safe_str(row.get("selected_candidate_mode"))
            if prior_mode and mode and prior_mode != mode:
                corridor_switch_count += 1
            if mode:
                prior_mode = mode
        system_touch_counts: Dict[str, int] = {}
        for row in cluster_results:
            for system_name in safe_list(safe_dict(row).get("changed_systems")):
                key = safe_str(system_name)
                if not key:
                    continue
                system_touch_counts[key] = system_touch_counts.get(key, 0) + 1
        shared_system_repeats = sum(max(count - 1, 0) for count in system_touch_counts.values())
        primary_system_changes = sum(1 for item in changed_systems if item in {"storm", "sanitary", "water"})
        structures_added = safe_int(safe_dict(overall_deltas).get("added_structures"), 0)
        crossing_prefit_reroutes = len(safe_list(crossing_prefit.get("rerouted_segments")))
        fragmentation_penalty = 34.0 * shared_system_repeats if not bool(group_prefit.get("applied")) else 0.0
        trench_group_credit = 28.0 * shared_system_repeats if bool(group_prefit.get("applied")) else 0.0
        constructability_score = round(
            max(
                safe_float(safe_dict(safe_dict(overall_deltas).get("constructability_impact")).get("score"), 0.0)
                + structures_added * 16.0
                + corridor_switch_count * 42.0
                + primary_system_changes * 18.0
                + fragmentation_penalty
                - trench_group_credit,
                0.0,
            ),
            3,
        )
        if bool(crossing_prefit.get("applied")):
            constructability_score = round(max(constructability_score - min(crossing_prefit_reroutes * 18.0, 54.0), 0.0), 3)
        score = round(
            len(remaining_related) * 1200.0
            + len(post_conflicts) * 160.0
            + (0.0 if validations.get("valid") else 700.0)
            + constructability_score
            + safe_float(safe_dict(safe_dict(overall_deltas).get("crossing_hierarchy")).get("penalty"), 0.0)
            + safe_float(safe_dict(safe_dict(overall_deltas).get("grading_impact")).get("score"), 0.0)
            + len(assumptions) * 150.0,
            3,
        )
        cluster_group_summary = {
            "cluster_count": len(clusters),
            "resolved_conflicts": max(len(initial_related) - len(remaining_related), 0),
            "added_structures": structures_added,
            "added_length_ft": round(safe_float(safe_dict(overall_deltas).get("added_length_ft"), 0.0), 3),
            "added_depth_ft": round(safe_float(safe_dict(overall_deltas).get("added_depth_ft"), 0.0), 3),
            "grading_disturbance_score": round(safe_float(safe_dict(safe_dict(overall_deltas).get("grading_impact")).get("score"), 0.0), 3),
            "crossing_rule_penalty": round(safe_float(safe_dict(safe_dict(overall_deltas).get("crossing_hierarchy")).get("penalty"), 0.0), 3),
            "corridor_switch_count": corridor_switch_count,
            "fragmentation_penalty": round(fragmentation_penalty, 3),
            "trench_group_credit": round(trench_group_credit, 3),
            "crossing_strategy": safe_str(plan.get("crossing_strategy")),
            "geometry_strategy": safe_str(plan.get("geometry_strategy")),
            "crossing_strategy_prefit_reroutes": crossing_prefit_reroutes,
            "geometry_strategy_prefit_reroutes": len(safe_list(geometry_prefit.get("rerouted_segments"))),
        }
        overall_deltas["corridor_switch_count"] = corridor_switch_count
        overall_deltas["fragmentation_penalty"] = round(fragmentation_penalty, 3)
        candidate = {
            "cluster_group_id": safe_str(group.get("cluster_group_id")),
            "plan_name": safe_str(plan.get("name")),
            "valid": len(remaining_related) == 0 and bool(validations.get("valid")) and not assumptions and all(bool(item.get("success")) for item in cluster_results),
            "score": score,
            "changed_systems": _canonical_changed_systems(changed_systems),
            "cluster_results": cluster_results,
            "resolution_rows": cluster_rows,
            "constructability_score": constructability_score,
            "engineering_deltas": overall_deltas,
            "cluster_group_summary": cluster_group_summary,
            "post_validation": validations,
            "remaining_cluster_conflicts": deepcopy(remaining_related),
            "why_failed": failed_reason or ("Trench-group candidate left related conflicts unresolved." if remaining_related else "Trench-group candidate failed downstream validation."),
        }
        candidate["coordination_realism"] = _coordination_realism_summary_impl(candidate, group=group)
        candidate["failure_breakdown"] = _coordination_failure_breakdown(
            remaining_conflicts=remaining_related,
            post_validation=validations,
            engineering_deltas=overall_deltas,
            assumption_used=bool(assumptions),
            rejected_reason=safe_str(candidate.get("why_failed")),
        )
        candidate_summaries.append(
            {
                "plan_name": safe_str(candidate.get("plan_name")),
                "valid": bool(candidate.get("valid")),
                "score": safe_float(candidate.get("score"), 0.0),
                "constructability_score": safe_float(candidate.get("constructability_score"), 0.0),
                "remaining_cluster_conflicts": len(remaining_related),
                "changed_systems": deepcopy(safe_list(candidate.get("changed_systems"))),
                "group_prefit_applied": bool(group_prefit.get("applied")),
                "geometry_prefit_applied": bool(geometry_prefit.get("applied")),
                "crossing_prefit_applied": bool(crossing_prefit.get("applied")),
                "corridor_switch_count": corridor_switch_count,
                "crossing_strategy": safe_str(plan.get("crossing_strategy")),
                "geometry_strategy": safe_str(plan.get("geometry_strategy")),
                "crossing_blocked": bool(safe_dict(safe_dict(overall_deltas.get("crossing_hierarchy")).get("blocked"))),
                "grading_blocked": bool(safe_dict(safe_dict(overall_deltas.get("grading_impact")).get("blocked"))),
                "protected_zone_penalty": safe_float(safe_dict(safe_dict(overall_deltas.get("protected_zone_impact")).get("penalty")), 0.0),
                "coordination_realism": deepcopy(safe_dict(candidate.get("coordination_realism"))),
                "failure_reason": safe_str(candidate.get("why_failed")),
                "failure_breakdown": deepcopy(safe_dict(candidate.get("failure_breakdown"))),
            }
        )
        if candidate["valid"]:
            if best_valid is None or safe_float(candidate.get("score"), 0.0) < safe_float(best_valid.get("score"), 1e9):
                best_valid = candidate
                best_valid_snapshot = _snapshot_coordination_state(project, manager)
                best_valid_full_snapshot = _full_coordination_state_snapshot(project, manager)
        elif best_near_valid is None or safe_float(candidate.get("score"), 0.0) < safe_float(best_near_valid.get("score"), 1e9):
            best_near_valid = candidate

    if best_valid is not None and best_valid_snapshot is not None:
        _coordination_metric_inc(metrics, ["timings_ms", "solve_conflict_cluster_group"], round((perf_counter() - started) * 1000.0, 3))
        if best_valid_full_snapshot is not None:
            _restore_full_coordination_state(project, manager, best_valid_full_snapshot)
        else:
            _restore_coordination_state(project, manager, best_valid_snapshot)
        return {
            "success": True,
            "cluster_group_id": safe_str(group.get("cluster_group_id")),
            "cluster_id": safe_str(group.get("cluster_group_id")),
            "group_plan": safe_str(best_valid.get("plan_name")),
            "selected_group_strategy": safe_str(safe_dict(best_valid.get("cluster_group_summary")).get("crossing_strategy")),
            "candidate_count": len(group_plans),
            "selected_order": safe_str(best_valid.get("plan_name")),
            "selected_candidate_mode": safe_str(safe_dict(safe_list(best_valid.get("cluster_results"))[0] if safe_list(best_valid.get("cluster_results")) else {}).get("selected_candidate_mode")),
            "changed_systems": deepcopy(safe_list(best_valid.get("changed_systems"))),
            "resolution_rows": deepcopy(safe_list(best_valid.get("resolution_rows"))),
            "constructability_score": safe_float(best_valid.get("constructability_score"), 0.0),
            "engineering_deltas": deepcopy(safe_dict(best_valid.get("engineering_deltas"))),
            "cluster_group_summary": deepcopy(safe_dict(best_valid.get("cluster_group_summary"))),
            "best_near_valid_candidate": deepcopy(safe_dict(best_near_valid or {})),
            "coordination_realism": deepcopy(safe_dict(best_valid.get("coordination_realism"))),
            "post_validation": deepcopy(safe_dict(best_valid.get("post_validation"))),
            "remaining_cluster_conflicts": [],
            "score": safe_float(best_valid.get("score"), 0.0),
            "candidate_summaries": candidate_summaries,
            "selection_reason": (
                f"Selected {safe_str(best_valid.get('plan_name'))} with {safe_str(safe_dict(best_valid.get('cluster_group_summary')).get('crossing_strategy'), 'default_crossing')} because it resolved {safe_int(safe_dict(best_valid.get('cluster_group_summary')).get('resolved_conflicts'), 0)} related conflicts across "
                f"{safe_int(safe_dict(best_valid.get('cluster_group_summary')).get('cluster_count'), 0)} clusters with "
                f"{safe_float(safe_dict(best_valid.get('cluster_group_summary')).get('added_length_ft'), 0.0):.1f} ft added length, "
                f"{safe_float(safe_dict(best_valid.get('cluster_group_summary')).get('added_depth_ft'), 0.0):.1f} ft added depth, "
                f"{safe_int(safe_dict(best_valid.get('cluster_group_summary')).get('added_structures'), 0)} added structures, "
                f"{safe_float(safe_dict(best_valid.get('cluster_group_summary')).get('grading_disturbance_score'), 0.0):.1f} grading disturbance, and "
                f"{safe_float(safe_dict(best_valid.get('cluster_group_summary')).get('crossing_rule_penalty'), 0.0):.1f} crossing-rule penalty."
            ),
        }

    _restore_full_coordination_state(project, manager, base_full_snapshot)
    _coordination_metric_inc(metrics, ["timings_ms", "solve_conflict_cluster_group"], round((perf_counter() - started) * 1000.0, 3))
    return {
        "success": False,
        "cluster_group_id": safe_str(group.get("cluster_group_id")),
        "cluster_id": safe_str(group.get("cluster_group_id")),
        "group_plan": "",
        "selected_group_strategy": "",
        "candidate_count": len(group_plans),
        "selected_order": "",
        "selected_candidate_mode": "",
        "changed_systems": [],
        "resolution_rows": [],
        "constructability_score": 0.0,
        "engineering_deltas": {},
        "cluster_group_summary": {},
        "best_near_valid_candidate": deepcopy(safe_dict(best_near_valid or {})),
        "coordination_realism": deepcopy(safe_dict(safe_dict(best_near_valid or {}).get("coordination_realism"))),
        "post_validation": deepcopy(safe_dict(safe_dict(best_near_valid or {}).get("post_validation"))),
        "remaining_cluster_conflicts": deepcopy(initial_related),
        "score": safe_float(safe_dict(best_near_valid or {}).get("score"), 0.0),
        "failure_reason": safe_str(safe_dict(best_near_valid or {}).get("why_failed")) or "No trench-group candidate could satisfy the related conflicts without violating downstream validation.",
        "candidate_summaries": candidate_summaries,
        "failure_tags": _coordination_failure_tags(candidate_summaries, safe_dict(best_near_valid or {})),
    }


def _run_conflict_resolution_stage(ctx: PlannerExecutionContext, hydrology: Dict[str, Any]) -> None:
    _precoordinate_vertical_hierarchy(ctx.manager.project, ctx.manager)
    _run_conflict_resolution_stage_impl(
        ctx,
        hydrology,
        manual_mode_enabled=_manual_mode_enabled,
        new_coordination_metrics=_new_coordination_metrics,
        detect_coordination_conflicts=_detect_coordination_conflicts,
        conflict_priority_key=_conflict_priority_key,
        group_conflict_clusters=_group_conflict_clusters,
        group_cluster_groups=_group_cluster_groups,
        snapshot_coordination_state=_snapshot_coordination_state,
        full_coordination_state_snapshot=_full_coordination_state_snapshot,
        cluster_group_remaining_conflicts=_cluster_group_remaining_conflicts,
        solve_conflict_cluster_group=_solve_conflict_cluster_group,
        refresh_conflict_resolved_state=_refresh_conflict_resolved_state,
        coordination_metric_inc=_coordination_metric_inc,
        restore_coordination_state=_restore_coordination_state,
        restore_full_coordination_state=_restore_full_coordination_state,
        conflict_cluster_id=_conflict_cluster_id,
        post_reroute_validations=_post_reroute_validations,
        count_conflicts_by_type=_count_conflicts_by_type,
        grading_local_adjustments=_grading_local_adjustments,
    )


def _run_sanitary_stage(ctx: PlannerExecutionContext) -> None:
    _run_sanitary_stage_impl(
        ctx,
        strict_mode_enabled=_strict_mode_enabled,
        sanitary_requested=_sanitary_requested,
        sanitary_user_input_summary=_sanitary_user_input_summary,
        record_strict_stage_failure=_record_strict_stage_failure,
        sanitary_building_nodes=_sanitary_building_nodes,
        storm_pipe_paths=_storm_pipe_paths,
        orthogonal_path=_orthogonal_path,
        sanitary_min_slope=_sanitary_min_slope,
        sample_grid_surface=_sample_grid_surface,
        route_conflicts=_route_conflicts,
        preferred_route_between=_preferred_route_between,
        repair_sanitary_segment_covers=_repair_sanitary_segment_covers,
        bind_sanitary_graph_nodes=_bind_sanitary_graph_nodes,
        validate_network_graph=_validate_network_graph,
        validate_sanitary_network=_validate_sanitary_network,
    )


def _run_utility_stage(ctx: PlannerExecutionContext) -> None:
    _run_utility_stage_impl(
        ctx,
        strict_mode_enabled=_strict_mode_enabled,
        install_rect_obstacle_compatibility=_install_rect_obstacle_compatibility,
        user_supplied_geometry_available=_user_supplied_geometry_available,
        actions_from_linear_features=_actions_from_linear_features,
        merge_actions_into_expanded_plan=_merge_actions_into_expanded_plan,
        enrich_utility_summary_with_coordination=_enrich_utility_summary_with_coordination,
        utility_export_validation=_utility_export_validation,
        record_strict_stage_failure=_record_strict_stage_failure,
        preferred_route_between=_preferred_route_between,
        utility_engine_cls=UtilityEngine,
    )


def _run_earthwork_stage(ctx: PlannerExecutionContext) -> None:
    _run_earthwork_stage_impl(ctx)


def _sheet_alignment(project: ProjectModel, parsed: Dict[str, Any]) -> Tuple[List[List[float]], bool, str]:
    expanded_actions = safe_list(safe_dict(getattr(project, "meta", {})).get("_expanded_plan", {}).get("actions"))
    preferred_road_line: Optional[List[List[float]]] = None
    for action in expanded_actions:
        if not isinstance(action, dict):
            continue
        if lower_text(action.get("task")) != "polyline":
            continue
        if safe_str(action.get("layer"), "").upper() != "ROAD":
            continue
        label = lower_text(action.get("label"))
        points = [[safe_float(pt[0], 0.0), safe_float(pt[1], 0.0)] for pt in safe_list(action.get("points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        if len(points) < 2:
            continue
        if "cl" in label or "centerline" in label:
            return points, abs(points[-1][0] - points[0][0]) >= abs(points[-1][1] - points[0][1]), "road_centerline"
        if preferred_road_line is None:
            preferred_road_line = points
    if preferred_road_line is not None:
        return preferred_road_line, abs(preferred_road_line[-1][0] - preferred_road_line[0][0]) >= abs(preferred_road_line[-1][1] - preferred_road_line[0][1]), "road_polyline"

    road_rect: Optional[Tuple[float, float, float, float]] = None
    for action in expanded_actions:
        if not isinstance(action, dict):
            continue
        if lower_text(action.get("task")) != "rectangle":
            continue
        if safe_str(action.get("layer"), "").upper() != "ROAD":
            continue
        origin = safe_list(action.get("origin"))
        if len(origin) < 2:
            continue
        x = safe_float(origin[0], 0.0)
        y = safe_float(origin[1], 0.0)
        w = safe_float(action.get("width"), 0.0)
        h = safe_float(action.get("height"), 0.0)
        if w <= 0.0 or h <= 0.0:
            continue
        candidate = (x, y, w, h)
        if road_rect is None or max(w, h) > max(road_rect[2], road_rect[3]):
            road_rect = candidate
    if road_rect is not None:
        x, y, w, h = road_rect
        if w >= h:
            return [[x, y + h / 2.0], [x + w, y + h / 2.0]], True, "road_rectangle"
        return [[x + w / 2.0, y], [x + w / 2.0, y + h]], False, "road_rectangle"

    lot = safe_dict(unwrap_fields_for_execution(parsed.get("lot")))
    x = safe_float(lot.get("x"), DEFAULT_LOT_X)
    y = safe_float(lot.get("y"), DEFAULT_LOT_Y)
    w = safe_float(lot.get("w"), DEFAULT_LOT_WIDTH)
    h = safe_float(lot.get("h"), DEFAULT_LOT_HEIGHT)
    street_edge = lower_text(parsed.get("street_edge") or "bottom")
    if street_edge in {"bottom", "top"}:
        align_y = y + (10.0 if street_edge == "bottom" else max(10.0, h - 10.0))
        return [[x + 5.0, align_y], [x + w - 5.0, align_y]], True, "lot_fallback"
    align_x = x + (10.0 if street_edge == "left" else max(10.0, w - 10.0))
    return [[align_x, y + 5.0], [align_x, y + h - 5.0]], False, "lot_fallback"


def _run_sheet_stage(ctx: PlannerExecutionContext) -> None:
    _run_sheet_stage_impl(
        ctx,
        requested_profile_or_sections=_requested_profile_or_sections,
        build_existing_surface=_build_existing_surface,
        expanded_obstacle_rectangles=_expanded_obstacle_rectangles,
        path_hits_buffered_rect=_path_hits_buffered_rect,
        grading_local_adjustments=_grading_local_adjustments,
        station_text=_station_text,
        sample_grid_surface=_sample_grid_surface,
        preferred_corridor_for_segment=_preferred_corridor_for_segment,
        sheet_alignment=_sheet_alignment,
    )


def _run_qa_stage(ctx: PlannerExecutionContext) -> PlanQualityReport:
    return _run_qa_stage_impl(
        ctx,
        project_model_to_plan=project_model_to_plan,
        manual_mode_enabled=_manual_mode_enabled,
    )


def _apply_fix_pass(ctx: PlannerExecutionContext, report: PlanQualityReport) -> None:
    _apply_fix_pass_impl(ctx, report)


# =============================================================================
# MODEL-FIRST ORCHESTRATION
# =============================================================================

def _run_model_first_workflow(
    parsed: Dict[str, Any],
    route: RoutingDecision,
    option_name: str = "Base Option",
    option_family: str = "base",
    progress_callback: Optional[Callable[..., None]] = None,
) -> PlannerExecutionContext:
    manager = _bootstrap_manager(parsed)
    _register_default_dependencies(manager)
    manual_mode = _manual_mode_enabled(parsed)

    ctx = PlannerExecutionContext(
        parsed=deepcopy(parsed),
        manager=manager,
        route=route,
        option_name=option_name,
        option_family=option_family,
    )
    ctx.record_assumption("Planner executed model-first workflow with ProjectManager as active lifecycle state.")
    ctx.record_assumption("Action geometry is treated as output packaging, not the primary internal truth.")
    manager.project.meta["omission_flags"] = omission_flags_from_parsed(parsed)

    _ingest_parsed_into_model(ctx)
    manager.project.meta["preferred_corridors"] = _preferred_corridors(parsed, manager.project)
    orchestrator_meta = safe_dict(safe_dict(parsed.get("meta")).get("orchestrator_meta"))
    runtime_phase_batch_limit = max(0, safe_int(orchestrator_meta.get("runtime_phase_batch_limit"), 0))

    class _RuntimePhaseYield(Exception):
        def __init__(self, plan: Dict[str, Any], stage_name: str, message: str) -> None:
            super().__init__(message)
            self.plan = plan
            self.stage_name = stage_name
            self.message = message

    def _seed_runtime_resume_state() -> set[str]:
        parsed_meta = safe_dict(parsed.get("meta"))
        orchestrator_meta = safe_dict(parsed_meta.get("orchestrator_meta"))
        resume_payload = safe_dict(orchestrator_meta.get("runtime_resume"))
        checkpoint_plan = safe_dict(resume_payload.get("final_plan"))
        checkpoint_meta = safe_dict(checkpoint_plan.get("meta"))
        stage_statuses = safe_dict(
            resume_payload.get("stage_statuses")
            or safe_dict(safe_dict(checkpoint_meta.get("stage_completeness")).get("statuses"))
        )
        if not stage_statuses:
            return set()

        resumable_statuses = {"complete", "assumed"}
        resumed: set[str] = set()

        def _stage_is_resumable(stage_name: str) -> bool:
            return lower_text(stage_statuses.get(stage_name)) in resumable_statuses

        def _record_resumed_stage(stage_name: str, message: str) -> None:
            manager.mark_system_complete(stage_name, message)
            ctx.add_stage(
                stage_name,
                True,
                message,
                resumed_from_checkpoint=True,
                completeness=lower_text(stage_statuses.get(stage_name)) or "complete",
            )
            resumed.add(stage_name)

        if _stage_is_resumable("layout"):
            restored_actions = [
                sanitize_action(dict(action))
                for action in safe_list(checkpoint_plan.get("actions"))
                if isinstance(action, dict)
            ]
            if restored_actions:
                manager.project.meta["_expanded_plan"] = {"actions": deepcopy(restored_actions)}
                parking_program = deepcopy(safe_dict(checkpoint_meta.get("parking_program")))
                if parking_program:
                    manager.latest_outputs["parking_program"] = deepcopy(parking_program)
                    manager.project.meta["parking_program"] = deepcopy(parking_program)
                _record_resumed_stage("layout", "Restored layout state from saved checkpoint.")

        if _stage_is_resumable("grading"):
            grading_summary = deepcopy(safe_dict(checkpoint_meta.get("grading")))
            if grading_summary:
                manager.latest_outputs["grading"] = deepcopy(grading_summary)
                manager.project.meta["grading_summary"] = deepcopy(grading_summary)
                _record_resumed_stage("grading", "Restored grading state from saved checkpoint.")

        if _stage_is_resumable("drainage"):
            drainage_summary = deepcopy(safe_dict(checkpoint_meta.get("drainage")))
            if drainage_summary:
                manager.latest_outputs["drainage"] = deepcopy(drainage_summary)
                manager.project.meta["drainage_canonical"] = deepcopy(drainage_summary)
                manager.project.meta["drainage_summary"] = deepcopy(drainage_summary)
                _record_resumed_stage("drainage", "Restored drainage state from saved checkpoint.")

        if _stage_is_resumable("storm_pipes"):
            storm_summary = deepcopy(safe_dict(checkpoint_meta.get("storm_pipes")))
            if storm_summary:
                manager.latest_outputs["storm_pipe_summary"] = deepcopy(storm_summary)
                manager.project.meta["storm_pipe_summary"] = deepcopy(storm_summary)
                manager.project.meta["storm_pipe_segments"] = deepcopy(
                    safe_list(storm_summary.get("segments"))
                )
                _record_resumed_stage("storm_pipes", "Restored storm pipe state from saved checkpoint.")

        if _stage_is_resumable("sanitary"):
            sanitary_summary = deepcopy(safe_dict(checkpoint_meta.get("sanitary")))
            if sanitary_summary:
                manager.latest_outputs["sanitary"] = deepcopy(sanitary_summary)
                manager.project.meta["sanitary_summary"] = deepcopy(sanitary_summary)
                _record_resumed_stage("sanitary", "Restored sanitary state from saved checkpoint.")

        if _stage_is_resumable("utility_network"):
            utility_summary = deepcopy(safe_dict(checkpoint_meta.get("utilities")))
            if utility_summary:
                manager.latest_outputs["utilities"] = deepcopy(utility_summary)
                manager.project.meta["utility_summary"] = deepcopy(utility_summary)
                _record_resumed_stage("utility_network", "Restored utility state from saved checkpoint.")

        if _stage_is_resumable("sheets"):
            profiles = deepcopy(safe_list(checkpoint_meta.get("profiles")))
            cross_sections = deepcopy(safe_list(checkpoint_meta.get("cross_sections")))
            if profiles or cross_sections:
                manager.latest_outputs["profiles"] = deepcopy(profiles)
                manager.latest_outputs["cross_sections"] = deepcopy(cross_sections)
                manager.project.meta["profiles"] = deepcopy(profiles)
                manager.project.meta["cross_sections"] = deepcopy(cross_sections)
                _record_resumed_stage("sheets", "Restored sheet state from saved checkpoint.")

        if resumed:
            ctx.record_assumption(
                f"Resumed saved engineering phases from checkpoint state: {', '.join(sorted(resumed))}."
            )
        return resumed

    resumed_stage_names = _seed_runtime_resume_state()
    newly_completed_stage_count = 0

    max_passes = max(2, safe_int(safe_dict(parsed.get("meta")).get("planner_passes"), 2))
    final_report = PlanQualityReport()
    best_snapshot_id: Optional[str] = None
    best_score: Optional[float] = None

    stage_progress = {
        "layout": ("Layout Phase", 18),
        "grading": ("Grading Phase", 30),
        "drainage": ("Drainage Phase", 42),
        "storm_pipes": ("Storm Pipe Phase", 54),
        "sanitary": ("Sanitary Phase", 64),
        "utility_network": ("Utilities Phase", 72),
        "coordination_resolution": ("Coordination Phase", 82),
        "earthwork": ("Earthwork Phase", 88),
        "sheets": ("Sheet Phase", 91),
        "qa": ("Validation Phase", 94),
    }

    def _emit_stage_progress(stage_name: str, status: str, detail: str, checkpoint: Optional[Dict[str, Any]] = None) -> None:
        if progress_callback is None:
            return
        label, progress_value = stage_progress.get(stage_name, ("Engineering Run", 48))
        try:
            signature = inspect.signature(progress_callback)
            if "checkpoint" in signature.parameters:
                progress_callback(stage_name, status, progress_value, detail or label, checkpoint=checkpoint)
            else:
                progress_callback(stage_name, status, progress_value, detail or label)
        except Exception:
            pass

    def _current_stage_statuses() -> Dict[str, str]:
        statuses: Dict[str, str] = {}
        for stage in ctx.stage_results:
            stage_name = safe_str(stage.stage_name)
            if not stage_name:
                continue
            statuses[stage_name] = _stage_completeness_label(
                stage_name,
                bool(stage.success),
                safe_str(stage.message),
                safe_dict(stage.meta),
            )
        return statuses

    def _checkpoint_stage_summary(value: Any) -> Dict[str, Any]:
        rec = safe_dict(value)
        if not rec:
            return {}
        return {
            "success": rec.get("success"),
            "source": rec.get("source") or rec.get("source_quality") or rec.get("hydraulic_source"),
            "source_detail": rec.get("source_detail"),
            "stats": _bounded_state_copy(safe_dict(rec.get("stats")), max_depth=2, max_items=30),
            "segment_count": len(safe_list(rec.get("segments"))),
            "structure_count": len(safe_list(rec.get("structures"))),
            "issue_count": len(safe_list(rec.get("issues"))),
            "missing_data_count": len(safe_list(rec.get("missing_data_segments"))),
        }

    def _build_runtime_checkpoint_plan(stage_name: str, message: str) -> Dict[str, Any]:
        checkpoint_plan = sanitize_plan(
            project_model_to_plan(
                manager.project,
                parsed.get("project_name") or "Generated Plan",
            )
        )
        checkpoint_plan.setdefault("meta", {})
        checkpoint_plan["meta"]["planner_workflow"] = "model_first"
        checkpoint_plan["meta"]["routing"] = {"path": route.path, "reasons": list(route.reasons)}
        checkpoint_plan["meta"]["option_name"] = option_name
        checkpoint_plan["meta"]["option_family"] = option_family
        checkpoint_plan["meta"]["runtime_phase_checkpoint"] = {
            "stage_name": stage_name,
            "status": "complete",
            "message": message,
            "yielded": False,
        }
        checkpoint_plan["meta"]["stage_completeness"] = {
            "statuses": _current_stage_statuses(),
        }
        checkpoint_plan["meta"]["parking_program"] = _checkpoint_stage_summary(manager.project.meta.get("parking_program"))
        checkpoint_plan["meta"]["grading"] = _checkpoint_stage_summary(manager.project.meta.get("grading_summary"))
        checkpoint_plan["meta"]["drainage"] = _checkpoint_stage_summary(manager.project.meta.get("drainage_canonical"))
        checkpoint_plan["meta"]["storm_pipes"] = _checkpoint_stage_summary(manager.project.meta.get("storm_pipe_summary"))
        checkpoint_plan["meta"]["sanitary"] = _checkpoint_stage_summary(manager.project.meta.get("sanitary_summary"))
        checkpoint_plan["meta"]["utilities"] = _checkpoint_stage_summary(manager.project.meta.get("utility_summary"))
        checkpoint_plan["meta"]["profiles"] = {"count": len(safe_list(manager.project.meta.get("profiles")))}
        checkpoint_plan["meta"]["cross_sections"] = {"count": len(safe_list(manager.project.meta.get("cross_sections")))}
        return checkpoint_plan

    def _run_declared_stage(stage_name: str, runner: Any, *args: Any) -> Any:
        nonlocal newly_completed_stage_count
        before_state = _canonical_state_snapshot(manager.project, manager)
        dirty_reasons = _stage_dirty_reasons(ctx, stage_name)
        if _stage_should_run(
            ctx,
            stage_name,
            force_first_pass=stage_name not in resumed_stage_names,
        ):
            _emit_stage_progress(
                stage_name,
                "running",
                f"Running {stage_progress.get(stage_name, ('Engineering Run', 48))[0].lower()}.",
            )
            result = runner(*args)
            latest = _latest_stage_result(ctx, stage_name)
            checkpoint_plan: Optional[Dict[str, Any]] = None
            if bool(getattr(latest, "success", True)):
                try:
                    checkpoint_plan = _build_runtime_checkpoint_plan(
                        stage_name,
                        safe_str(getattr(latest, "message", "")),
                    )
                except Exception:
                    checkpoint_plan = None
            _emit_stage_progress(
                stage_name,
                "complete" if bool(getattr(latest, "success", True)) else "failed",
                safe_str(getattr(latest, "message", "")) or f"{stage_progress.get(stage_name, ('Engineering Run', 48))[0]} completed.",
                checkpoint=checkpoint_plan,
            )
            _record_stage_audit(
                ctx,
                stage_name,
                pass_index=pass_index,
                action="run",
                dirty_reasons=dirty_reasons,
                before_state=before_state,
            )
            if bool(getattr(latest, "success", True)) and stage_name not in resumed_stage_names:
                newly_completed_stage_count += 1
                if runtime_phase_batch_limit and newly_completed_stage_count >= runtime_phase_batch_limit:
                    yielded_plan = checkpoint_plan or _build_runtime_checkpoint_plan(
                        stage_name,
                        safe_str(getattr(latest, "message", "")),
                    )
                    yielded_plan.setdefault("meta", {})
                    yielded_meta = safe_dict(yielded_plan.get("meta"))
                    yielded_meta["runtime_phase_checkpoint"] = {
                        **safe_dict(yielded_meta.get("runtime_phase_checkpoint")),
                        "stage_name": stage_name,
                        "status": "complete",
                        "message": safe_str(getattr(latest, "message", "")),
                        "yielded": True,
                    }
                    yielded_plan["meta"] = yielded_meta
                    raise _RuntimePhaseYield(
                        yielded_plan,
                        stage_name,
                        safe_str(getattr(latest, "message", "")) or f"{stage_name} phase checkpoint saved.",
                    )
            return result
        _mark_stage_skipped_clean(ctx, stage_name)
        _record_stage_audit(
            ctx,
            stage_name,
            pass_index=pass_index,
            action="skipped_clean",
            dirty_reasons=dirty_reasons,
            before_state=before_state,
        )
        return final_report if stage_name == "qa" else None

    try:
        for pass_index in range(1, max_passes + 1):
            ctx.pass_index = pass_index
            manager.log("planner_pass", pass_index=pass_index, option_name=option_name, option_family=option_family)

            preliminary_plan = project_model_to_plan(manager.project, parsed.get("project_name") or "Generated Plan")
            preliminary_stats = collect_plan_stats(preliminary_plan)
            hydrology = _compute_hydrology_metrics(parsed, preliminary_stats)

            txn_id = manager.begin_transaction(f"planner_pass_{pass_index}")

            _run_declared_stage("layout", _run_layout_stage, ctx)
            if manual_mode:
                _run_manual_gate(ctx, "layout_gate")
            _run_declared_stage("grading", _run_grading_stage, ctx, hydrology)
            if manual_mode:
                _run_manual_gate(ctx, "grading_gate")
            _run_declared_stage("drainage", _run_drainage_stage, ctx, hydrology)
            if manual_mode:
                _run_manual_gate(ctx, "drainage_gate")
            _run_declared_stage("storm_pipes", _run_storm_pipe_stage, ctx, hydrology)
            if manual_mode:
                _run_manual_gate(ctx, "storm_pipe_gate")
            _run_declared_stage("sanitary", _run_sanitary_stage, ctx)
            if manual_mode:
                _run_manual_gate(ctx, "sanitary_gate")
            _run_declared_stage("utility_network", _run_utility_stage, ctx)
            if manual_mode:
                _run_manual_gate(ctx, "utility_gate")
            _run_declared_stage("coordination_resolution", _run_conflict_resolution_stage, ctx, hydrology)
            if manual_mode:
                _run_manual_gate(ctx, "coordination_gate")
            _run_declared_stage("earthwork", _run_earthwork_stage, ctx)
            _run_declared_stage("sheets", _run_sheet_stage, ctx)
            report = _run_declared_stage("qa", _run_qa_stage, ctx)
            final_report = report

            score_total, _ = _planner_score_from_manager(manager)
            if best_score is None or score_total > best_score:
                best_score = score_total
                best_snapshot_id = manager.snapshot(f"best_pass_{pass_index}")
                manager.commit_transaction(txn_id)
            else:
                manager.rollback_transaction(txn_id)

            if manual_mode and ctx.errors:
                ctx.add_stage(
                    "coordination",
                    False,
                    "Assisted off validation blocked assisted-style retries and returned the current engineering state as failed.",
                    pass_index=pass_index,
                    planner_score=score_total,
                    manual_mode=True,
                )
                break

            if report.error_count() == 0 and report.warning_count() < 5:
                ctx.add_stage("coordination", True, "Planner reached acceptable convergence.", pass_index=pass_index, planner_score=score_total)
                break

            if pass_index < max_passes:
                _apply_fix_pass(ctx, report)
            else:
                ctx.add_stage("coordination", True, "Reached max planner passes; preserving best coordinated state.", pass_index=pass_index, planner_score=score_total)
    except _RuntimePhaseYield as yielded:
        ctx.final_plan = sanitize_plan(dict(yielded.plan))
        return ctx

    if best_snapshot_id:
        try:
            manager.restore_snapshot(best_snapshot_id)
        except Exception:
            pass

    plan = project_model_to_plan(manager.project, parsed.get("project_name") or "Generated Plan")
    plan.setdefault("meta", {})
    plan["meta"]["planner_workflow"] = "model_first"
    plan["meta"]["planner_pass_count"] = ctx.pass_index
    plan["meta"]["option_name"] = option_name
    plan["meta"]["option_family"] = option_family
    stage_completeness = _compile_stage_completeness(ctx, parsed, plan)
    plan["meta"]["stage_results"] = [
        {
            "stage_name": s.stage_name,
            "success": s.success,
            "message": s.message,
            "warnings": list(s.warnings),
            "meta": deepcopy(s.meta),
        }
        for s in ctx.stage_results
    ]
    plan["meta"]["stage_completeness"] = stage_completeness
    plan["meta"]["rerun_history"] = deepcopy(ctx.rerun_history)
    plan["meta"]["routing"] = {"path": route.path, "reasons": list(route.reasons)}
    plan["meta"]["strict_mode"] = _strict_mode_enabled(parsed)
    manager_export = manager.export_metrics(summary_only=True) if hasattr(manager, "export_metrics") else {}
    plan["meta"]["project_manager"] = {
        "metrics": {k: getattr(v, "value", None) for k, v in manager.metrics.items()},
        "conflict_count": len(manager.conflicts),
        "system_count": safe_int(safe_dict(manager_export.get("system_counts")).get("total"), len(getattr(manager, "systems", {}))),
        "dependency_count": safe_int(safe_dict(manager_export.get("dependency_counts")).get("total"), len(getattr(manager, "dependencies", []))),
        "snapshot_count": len(getattr(manager, "snapshots", {})),
        "variant_count": len(getattr(manager, "variants", {})),
        "rerun_queue": manager.list_rerun_queue() if hasattr(manager, "list_rerun_queue") else [],
        "invalidated_targets": manager.get_invalidated_targets() if hasattr(manager, "get_invalidated_targets") else [],
        "dirty_state": deepcopy(safe_dict(manager_export.get("dirty_state"))),
    }
    plan["meta"]["system_dirty_state"] = deepcopy(getattr(manager, "system_dirty_state", {}))

    score_total, weighted = _planner_score_from_manager(manager)
    plan["meta"]["planner_score"] = {"total": round(score_total, 3), "weighted_components": weighted}
    plan["meta"]["warnings"] = deepcopy(ctx.warnings)
    plan["meta"]["errors"] = deepcopy(ctx.errors)
    plan["meta"]["fallbacks"] = [
        {
            "stage_name": s.stage_name,
            "message": s.message,
            "meta": deepcopy(s.meta),
        }
        for s in ctx.stage_results
        if safe_dict(s.meta).get("fallback_used")
    ]
    plan["meta"]["manager_export"] = manager_export
    _attach_canonical_stage_outputs(plan, manager.project, manager)
    plan["actions"] = _filter_actions_for_dirty_systems(
        _merge_plan_actions(safe_list(plan.get("actions")), _canonical_export_actions(manager.project)),
        _dirty_systems_from_project(manager.project),
    )
    plan["meta"]["preferred_corridors"] = deepcopy(manager.project.meta.get("preferred_corridors", {}))
    wants_profile, wants_sections = _requested_profile_or_sections(parsed)
    if (wants_profile and not safe_list(plan["meta"].get("profiles"))) or (wants_sections and not safe_list(plan["meta"].get("cross_sections"))):
        _ensure_canonical_sheet_metadata(plan, _export_profiles(plan), _export_cross_sections(plan))

    try:
        qty = compute_plan_quantities(plan)
        qty_warnings = list(getattr(qty, "warnings", []))
        omit_flags = omission_flags_from_parsed(parsed)
        filtered_qty_warnings: List[str] = []
        for warning in qty_warnings:
            lowered = lower_text(warning)
            if omit_flags.get("utilities") and "utility" in lowered:
                continue
            if omit_flags.get("drainage") and any(term in lowered for term in ("drainage", "inlet", "pond", "pipe")):
                continue
            if omit_flags.get("parking") and "parking" in lowered:
                continue
            filtered_qty_warnings.append(safe_str(warning))
        plan["meta"]["quantities"] = {
            "success": getattr(qty, "success", True),
            "message": getattr(qty, "message", ""),
            "totals": deepcopy(getattr(qty, "totals", {})),
            "tables": deepcopy(getattr(qty, "tables", {})),
            "warnings": filtered_qty_warnings,
            "assumptions": list(getattr(qty, "assumptions", [])),
            "explain": deepcopy(getattr(qty, "explain", {})),
        }
    except Exception as exc:
        plan["meta"]["quantities"] = {"success": False, "message": f"Quantity computation failed: {exc}"}
    try:
        cost = compute_cost_estimate(plan)
        plan["meta"]["cost_estimate"] = {
            "success": getattr(cost, "success", True),
            "message": getattr(cost, "message", ""),
            "totals": deepcopy(getattr(cost, "totals", {})),
            "line_items": deepcopy(getattr(cost, "line_items", [])),
            "category_subtotals": deepcopy(getattr(cost, "category_subtotals", {})),
            "warnings": list(getattr(cost, "warnings", [])),
            "assumptions": list(getattr(cost, "assumptions", [])),
            "explain": deepcopy(getattr(cost, "explain", {})),
        }
    except Exception as exc:
        plan["meta"]["cost_estimate"] = {"success": False, "message": f"Cost computation failed: {exc}", "totals": {}}

    _synthesize_canonical_meta(parsed, plan)
    plan["meta"]["optimization_summary"] = _build_optimization_summary(parsed, plan)

    try:
        explanation = explain_plan(plan)
        plan["meta"]["explanation"] = {
            "success": getattr(explanation, "success", True),
            "summary": getattr(explanation, "summary", ""),
            "bullets": list(getattr(explanation, "bullets", [])),
        }
    except Exception as exc:
        plan["meta"]["explanation"] = {"success": False, "summary": f"Explain stage failed: {exc}", "bullets": []}

    plan["meta"]["qa"] = final_report.to_meta()
    plan["meta"]["truth_audit"] = _canonical_truth_audit(parsed, plan, manager)
    coordination_meta = safe_dict(plan["meta"].get("coordination"))
    fix_summary = deepcopy(safe_dict(manager.project.meta.get("fix_summary")))
    unresolved_conflicts = safe_list(coordination_meta.get("unresolved_conflicts"))
    def _review_category_from_value(value: str) -> str:
        lowered = lower_text(value)
        if not lowered:
            return "general"
        if "drain" in lowered or "basin" in lowered or "detention" in lowered or "inlet" in lowered or "flow_path" in lowered:
            return "drainage"
        if "storm" in lowered or "pipe" in lowered or "hydraulic" in lowered:
            return "pipes"
        if "utility" in lowered or "water" in lowered or "sanitary" in lowered or "sewer" in lowered:
            return "utilities"
        if "grade" in lowered or "contour" in lowered or "slope" in lowered or "surface" in lowered:
            return "grading"
        if "layout" in lowered or "parking" in lowered or "building" in lowered or "site" in lowered:
            return "layout"
        if "deliverable" in lowered or "profile" in lowered or "section" in lowered:
            return "deliverables"
        if "quantity" in lowered or "earthwork" in lowered:
            return "quantities"
        if "coordination" in lowered or "conflict" in lowered or "clearance" in lowered:
            return "coordination"
        if "qa" in lowered:
            return "qa"
        return "general"

    unresolved_category_counts: Dict[str, int] = {}
    for conflict in unresolved_conflicts:
        category = _review_category_from_value(
            safe_str(safe_dict(conflict).get("category"))
            or safe_str(safe_dict(conflict).get("code"))
            or safe_str(safe_dict(conflict).get("message"))
        )
        unresolved_category_counts[category] = unresolved_category_counts.get(category, 0) + 1
    unresolved_issue_categories = [
        name
        for name, count in sorted(unresolved_category_counts.items(), key=lambda item: (-item[1], item[0]))
        if count > 0
    ]
    qa_issue_category_counts: Dict[str, int] = {}
    for issue in final_report.issues:
        code = lower_text(safe_str(issue.code))
        category = _review_category_from_value(code)
        qa_issue_category_counts[category] = qa_issue_category_counts.get(category, 0) + 1
    qa_issue_categories = [
        name
        for name, count in sorted(qa_issue_category_counts.items(), key=lambda item: (-item[1], item[0]))
        if count > 0
    ]
    def _is_user_facing_assumption(value: str) -> bool:
        lowered = lower_text(value)
        if not lowered:
            return False
        internal_markers = (
            "projectmanager as active lifecycle state",
            "action geometry is treated as output packaging",
            "quantities prefer canonical projectmanager metrics",
            "planner executed model-first workflow",
            "prompt was parsed with deterministic fast-path rules",
            "planner execution assumption",
            "autofix_site_layout",
        )
        return not any(marker in lowered for marker in internal_markers)

    assumption_items = dedupe_keep_order(
        [
            safe_str(item)
            for item in list(ctx.assumptions) + list(parsed.get("_planner_review_notes") or [])
            if safe_str(item) and _is_user_facing_assumption(safe_str(item))
        ]
    )
    quantity_assumptions = [safe_str(item) for item in safe_list(safe_dict(plan["meta"].get("quantities")).get("assumptions")) if safe_str(item)]
    assumption_items = dedupe_keep_order(assumption_items + [item for item in quantity_assumptions if _is_user_facing_assumption(item)])
    assumption_category_counts: Dict[str, int] = {}
    for item in assumption_items:
        category = _review_category_from_value(item)
        if category == "pipes":
            category = "storm"
        assumption_category_counts[category] = assumption_category_counts.get(category, 0) + 1
    assumption_categories = [
        name
        for name, count in sorted(assumption_category_counts.items(), key=lambda item: (-item[1], item[0]))
        if count > 0
    ]
    rerun_stage_counts: Dict[str, int] = {}
    rerun_reason_counts: Dict[str, Dict[str, int]] = {}
    total_reruns = 0
    for entry in safe_list(ctx.rerun_history):
        record = safe_dict(entry)
        if safe_str(record.get("action")) != "run":
            continue
        pass_number = safe_int(record.get("pass_index"), 0)
        stage_name = safe_str(record.get("stage_name"))
        if pass_number <= 1 or not stage_name:
            continue
        total_reruns += 1
        rerun_stage_counts[stage_name] = rerun_stage_counts.get(stage_name, 0) + 1
        reason_bucket = rerun_reason_counts.setdefault(stage_name, {})
        for reason in safe_list(record.get("dirty_reasons")):
            reason_text = safe_str(reason)
            if reason_text:
                reason_bucket[reason_text] = reason_bucket.get(reason_text, 0) + 1
    stage_rerun_counts = {
        stage_name: rerun_stage_counts[stage_name]
        for stage_name in sorted(rerun_stage_counts.keys(), key=lambda name: (-rerun_stage_counts[name], name))
    }
    dominant_rerun_reasons = {
        stage_name: [
            reason
            for reason, _count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))[:3]
        ]
        for stage_name, reason_counts in rerun_reason_counts.items()
        if stage_name in stage_rerun_counts
    }
    pass_history: List[Dict[str, Any]] = []
    for pass_number in range(1, ctx.pass_index + 1):
        pass_results = [
            stage
            for stage in ctx.stage_results
            if safe_int(safe_dict(stage.meta).get("pass_index"), 0) == pass_number
        ]
        if not pass_results:
            continue
        qa_stage = next((stage for stage in reversed(pass_results) if safe_str(stage.stage_name) == "qa"), None)
        coordination_stage = next((stage for stage in reversed(pass_results) if safe_str(stage.stage_name) == "coordination"), None)
        fix_stage = next((stage for stage in reversed(pass_results) if safe_str(stage.stage_name) == "fix"), None)
        fix_stage_meta = safe_dict(getattr(fix_stage, "meta", {}))
        fix_stage_summary = safe_dict(fix_stage_meta.get("fix_summary"))
        qa_stage_meta = safe_dict(getattr(qa_stage, "meta", {}))
        pass_history.append(
            {
                "pass_index": pass_number,
                "qa_warning_count": safe_int(qa_stage_meta.get("warning_count"), 0),
                "qa_error_count": safe_int(qa_stage_meta.get("error_count"), 0),
                "coordination_message": safe_str(getattr(coordination_stage, "message", "")),
                "coordination_success": bool(getattr(coordination_stage, "success", False)),
                "fix_attempted": bool(fix_stage),
                "fix_effective_change": bool(fix_stage_summary.get("effective_change", False)),
                "changed_targets": deepcopy(safe_list(fix_stage_summary.get("changed_targets"))),
                "autofix_actions": deepcopy(safe_list(fix_stage_summary.get("autofix_actions"))),
                "dominant_issue_categories": deepcopy(safe_list(fix_stage_summary.get("dominant_issue_categories"))),
                "last_fix_attempt": deepcopy(safe_dict(fix_stage_summary.get("last_fix_attempt"))),
            }
        )
    blocked_exports: List[str] = []
    blocked_reasons: List[str] = []
    grading_export = safe_dict(safe_dict(plan["meta"].get("grading")).get("export_validation"))
    if grading_export and not bool(grading_export.get("ready")):
        blocked_exports.append("grading")
        blocked_reasons.extend(safe_str(item) for item in safe_list(grading_export.get("reasons")) if safe_str(item))
    drainage_export = safe_dict(safe_dict(plan["meta"].get("drainage")).get("export_validation"))
    if drainage_export and not bool(drainage_export.get("ready")):
        blocked_exports.append("drainage")
        blocked_reasons.extend(safe_str(item) for item in safe_list(drainage_export.get("reasons")) if safe_str(item))
    utility_export = safe_dict(safe_dict(plan["meta"].get("utilities")).get("export_validation"))
    if utility_export and not bool(utility_export.get("ready")):
        blocked_exports.append("utilities")
        blocked_reasons.extend(safe_str(item) for item in safe_list(utility_export.get("reasons")) if safe_str(item))
    storm_export = _storm_export_validation(manager.project)
    if safe_dict(storm_export):
        plan["meta"].setdefault("storm_pipes", {})
        if isinstance(plan["meta"]["storm_pipes"], dict):
            plan["meta"]["storm_pipes"]["export_validation"] = deepcopy(safe_dict(storm_export))
        project_storm = safe_dict(manager.project.meta.get("storm_pipe_summary"))
        if project_storm:
            project_storm["export_validation"] = deepcopy(safe_dict(storm_export))
            manager.project.meta["storm_pipe_summary"] = project_storm
            manager.latest_outputs["storm_pipe_summary"] = deepcopy(project_storm)
    if safe_dict(storm_export) and not bool(safe_dict(storm_export).get("ready")):
        blocked_exports.append("storm")
        blocked_reasons.extend(safe_str(item) for item in safe_list(safe_dict(storm_export).get("reasons")) if safe_str(item))
    blocked_exports = dedupe_keep_order(blocked_exports)
    blocked_reasons = dedupe_keep_order([item for item in blocked_reasons if item])
    unresolved_issue_categories = dedupe_keep_order(
        unresolved_issue_categories
        + [_review_category_from_value(item) for item in blocked_reasons if safe_str(item)]
        + qa_issue_categories
    )
    plan["meta"]["convergence_summary"] = {
        "passes_run": ctx.pass_index,
        "max_passes": max_passes,
        "converged": bool(final_report.error_count() == 0 and final_report.warning_count() < 5 and not unresolved_conflicts),
        "warning_count": final_report.warning_count(),
        "error_count": final_report.error_count(),
        "unresolved_conflict_count": len(unresolved_conflicts),
        "assumption_summary": {
            "count": len(assumption_items),
            "categories": assumption_categories,
            "examples": assumption_items[:5],
        },
        "unresolved_issue_categories": unresolved_issue_categories,
        "qa_issue_categories": qa_issue_categories,
        "rerun_summary": {
            "total_reruns": total_reruns,
            "stage_rerun_counts": stage_rerun_counts,
            "dominant_rerun_reasons": dominant_rerun_reasons,
            "stages_touched": list(stage_rerun_counts.keys()),
        },
        "blocked_exports": blocked_exports,
        "blocked_reasons": blocked_reasons,
        "pass_history": pass_history,
        "fix_summary": fix_summary,
    }
    plan["assumptions"] = dedupe_keep_order(
        list(plan.get("assumptions") or []) + ctx.assumptions + list(parsed.get("_planner_review_notes") or [])
    )

    produced_deliverables = _produced_deliverables(plan)
    requested_deliverables = _requested_deliverables(parsed)
    plan["meta"]["deliverables"] = {
        "requested": requested_deliverables,
        "produced": produced_deliverables,
        "missing": [item for item in requested_deliverables if item not in produced_deliverables],
    }

    if manual_mode:
        _run_manual_gate(ctx, "quantities_gate", plan)
        _run_manual_gate(ctx, "deliverables_gate", plan)
        plan["meta"]["manual_mode"] = True

        gate_results = [stage for stage in ctx.stage_results if safe_str(stage.stage_name).endswith("_gate")]
        gate_failures: List[Dict[str, Any]] = []
        for stage in gate_results:
            gate_failures.extend([deepcopy(item) for item in safe_list(safe_dict(stage.meta).get("failures")) if isinstance(item, dict)])

        deduped_gate_failures: List[Dict[str, Any]] = []
        gate_seen: set[Tuple[str, str, str]] = set()
        for failure in gate_failures:
            gate_key = (
                safe_str(failure.get("gate_name")),
                safe_str(failure.get("code")),
                safe_str(failure.get("message")),
            )
            if gate_key in gate_seen:
                continue
            gate_seen.add(gate_key)
            deduped_gate_failures.append(deepcopy(failure))

        if _sanitary_requested(parsed):
            sanitary_meta = safe_dict(plan["meta"].get("sanitary"))
            sanitary_ready = (
                bool(sanitary_meta.get("success"))
                and safe_int(sanitary_meta.get("route_count"), 0) > 0
                and safe_int(sanitary_meta.get("service_count"), 0) > 0
                and bool(safe_dict(sanitary_meta.get("graph_validation")).get("valid", False))
                and bool(safe_dict(sanitary_meta.get("network_validation")).get("valid", False))
            )
            if sanitary_ready:
                stale_sanitary_codes = {
                    "MANUAL_SANITARY_OUTPUT_MISSING",
                    "MANUAL_SANITARY_SLOPE_VIOLATION",
                    "MANUAL_SANITARY_GRAPH_INVALID",
                    "MANUAL_SANITARY_NETWORK_INVALID",
                }
                deduped_gate_failures = [
                    failure for failure in deduped_gate_failures if safe_str(failure.get("code")) not in stale_sanitary_codes
                ]

        current_deliverables = safe_dict(plan["meta"].get("deliverables"))
        current_missing_deliverables = set(safe_str(item) for item in safe_list(current_deliverables.get("missing")) if safe_str(item))
        current_truth_failures = {
            safe_str(item.get("code"))
            for item in safe_list(safe_dict(plan["meta"].get("truth_audit")).get("failing_checks"))
            if isinstance(item, dict)
        }
        if not current_missing_deliverables:
            deduped_gate_failures = [
                failure
                for failure in deduped_gate_failures
                if safe_str(failure.get("code")) != "MANUAL_DELIVERABLES_MISSING"
            ]
        stale_truth_failure_codes = {
            "MANUAL_STORM_DELIVERABLE_MATCH": "STORM_DELIVERABLE_MATCH",
            "MANUAL_SANITARY_DELIVERABLE_MATCH": "SANITARY_DELIVERABLE_MATCH",
            "MANUAL_UTILITY_SUMMARY_CURRENT": "UTILITY_SUMMARY_CURRENT",
            "MANUAL_DRAINAGE_SUMMARY_CURRENT": "DRAINAGE_SUMMARY_CURRENT",
        }
        deduped_gate_failures = [
            failure
            for failure in deduped_gate_failures
            if not (
                safe_str(failure.get("code")) in stale_truth_failure_codes
                and stale_truth_failure_codes[safe_str(failure.get("code"))] not in current_truth_failures
            )
        ]

        manual_validation = {
            "mode": "manual",
            "failed": bool(deduped_gate_failures),
            "gate_count": len(gate_results),
            "failed_gate_count": sum(1 for stage in gate_results if not stage.success),
            "gates": [
                {
                    "gate_name": stage.stage_name,
                    "success": stage.success,
                    "message": stage.message,
                    "meta": deepcopy(stage.meta),
                }
                for stage in gate_results
            ],
            "failures": deduped_gate_failures,
            "failure_reasoning": [_manual_failure_reasoning(item) for item in deduped_gate_failures],
        }
        required_stage_status = safe_dict(safe_dict(plan["meta"].get("stage_completeness")).get("required_stage_status"))
        incomplete_required = [
            stage_name
            for stage_name, completeness in required_stage_status.items()
            if safe_str(completeness) != "complete"
        ]
        for stage_name in incomplete_required:
            deduped_gate_failures.append(
                _manual_failure(
                    "stage_completeness_gate",
                    stage_name,
                    "MANUAL_STAGE_INCOMPLETE",
                    f"Assisted off requires stage '{stage_name}' to be COMPLETE before engineering signoff can pass.",
                    engine=stage_name,
                    missing_computation="stage_completeness",
                    source_fields=[stage_name],
                    failure_type="incomplete_postprocessing",
                    reason_class="stage_not_complete",
                    category="manual_validation",
                    context={"rule": "stage_completeness", "stage_name": stage_name, "why_unresolved": f"Stage '{stage_name}' reported completeness '{required_stage_status.get(stage_name)}'."},
                )
            )
        manual_validation["failed"] = bool(deduped_gate_failures)
        manual_validation["failures"] = deduped_gate_failures
        manual_validation["failure_reasoning"] = [_manual_failure_reasoning(item) for item in deduped_gate_failures]
        plan["meta"]["manual_validation"] = manual_validation
        trust_score = _finalize_engineering_trust_score(plan, manual_failed=manual_validation["failed"])
        plan["meta"]["engineering_status"] = {
            "mode": "manual",
            "success": not manual_validation["failed"],
            "status": "failed" if manual_validation["failed"] else "complete",
            "required_stage_names": deepcopy(safe_list(safe_dict(plan["meta"].get("stage_completeness")).get("required_stage_names"))),
            "required_stages_complete": bool(safe_dict(plan["meta"].get("stage_completeness")).get("all_required_complete")),
            "engineering_trust_score": trust_score,
            "signoff_summary": (
                f"Assisted-off engineering validation passed with complete required systems and trust score {trust_score:.1f}."
                if not manual_validation["failed"]
                else f"Assisted-off engineering validation failed because one or more required systems violated hard engineering rules or remained incomplete. Trust score {trust_score:.1f}."
            ),
        }
        if manual_validation["failed"]:
            qa_meta = safe_dict(plan["meta"]["qa"])
            qa_issues = safe_list(qa_meta.get("issues"))
            for failure in deduped_gate_failures:
                qa_issues.append(
                    {
                        "code": safe_str(failure.get("code"), "MANUAL_VALIDATION_FAILED"),
                        "severity": "error",
                        "message": safe_str(failure.get("message"), "Assisted-off validation needs more information."),
                        "context": deepcopy(failure),
                    }
                )
            qa_meta["issues"] = qa_issues
            qa_meta["error_count"] = final_report.error_count() + len(deduped_gate_failures)
            qa_meta["warning_count"] = final_report.warning_count()
            plan["meta"]["qa"] = qa_meta
            plan["meta"]["errors"] = dedupe_keep_order(list(plan["meta"].get("errors") or []) + [safe_str(f.get("message")) for f in deduped_gate_failures if safe_str(f.get("message"))])
    else:
        trust_score = _finalize_engineering_trust_score(plan, manual_failed=False)
        plan["meta"]["manual_mode"] = False
        plan["meta"]["engineering_status"] = {
            "mode": "assisted",
            "success": True,
            "status": "complete" if not ctx.errors else "partial",
            "required_stage_names": deepcopy(safe_list(safe_dict(plan["meta"].get("stage_completeness")).get("required_stage_names"))),
            "required_stages_complete": bool(safe_dict(plan["meta"].get("stage_completeness")).get("all_required_complete")),
            "engineering_trust_score": trust_score,
            "signoff_summary": f"Assisted engineering run completed with trust score {trust_score:.1f}.",
        }

    ctx.final_plan = sanitize_plan(plan)
    return ctx


# =============================================================================
# PUBLIC BUILD ENTRYPOINTS
# =============================================================================

def build_plan_from_parsed(
    parsed: Dict[str, Any],
    route: RoutingDecision,
    *,
    progress_callback: Optional[Callable[[str, str, int, str], None]] = None,
) -> Dict[str, Any]:
    if route.path == "model_first":
        ctx = _run_model_first_workflow(parsed, route, progress_callback=progress_callback)
        return ctx.final_plan
    raise ValueError(f"Unsupported planner route '{route.path}'.")


def _ensure_subdivision_road_preview(plan: Dict[str, Any], parsed: Dict[str, Any]) -> None:
    subdivision = safe_dict(parsed.get("subdivision"))
    if not subdivision:
        return
    actions = safe_list(plan.get("actions"))
    if any(safe_str(safe_dict(action).get("layer")).upper() == "ROAD" for action in actions):
        return
    lot = safe_dict(parsed.get("lot"))
    x = safe_float(lot.get("x"), 0.0)
    y = safe_float(lot.get("y"), 0.0)
    w = safe_float(lot.get("w"), 0.0)
    h = safe_float(lot.get("h"), 0.0)
    if w <= 0.0 or h <= 0.0:
        return
    margin = max(safe_float(parsed.get("setback"), 15.0) * 2.0, min(w, h) * 0.08)
    road_y = y + h * 0.5
    road_points = [
        [round(x + margin, 3), round(road_y, 3)],
        [round(x + w * 0.35, 3), round(road_y, 3)],
        [round(x + w * 0.5, 3), round(y + h - margin, 3)],
        [round(x + w * 0.65, 3), round(road_y, 3)],
        [round(x + w - margin, 3), round(road_y, 3)],
    ]
    actions.append(
        {
            "task": "polyline",
            "layer": "ROAD",
            "points": road_points,
            "label": "Subdivision loop road",
            "meta": {"system": "roads", "preview_role": "road_centerline", "source": "subdivision_preview_fallback"},
            "canonical_source_type": "subdivision_road_centerline",
        }
    )
    culdesac_count = max(0, safe_int(subdivision.get("culdesac_count"), 0))
    centers = [[x + margin, road_y], [x + w - margin, road_y], [x + w * 0.5, y + h - margin]]
    for idx, center in enumerate(centers[:culdesac_count], start=1):
        actions.append(
            {
                "task": "circle",
                "layer": "ROAD",
                "center": [round(center[0], 3), round(center[1], 3)],
                "radius": round(max(35.0, min(w, h) * 0.045), 3),
                "label": f"Cul-de-sac {idx}",
                "meta": {"system": "roads", "preview_role": "culdesac", "source": "subdivision_preview_fallback"},
                "canonical_source_type": "subdivision_culdesac",
            }
        )
    plan["actions"] = actions


def _dedupe_readiness_details(details: Iterable[Any]) -> List[Dict[str, Any]]:
    clean: List[Dict[str, Any]] = []
    seen = set()
    for item in details:
        detail = safe_dict(item)
        if not detail:
            continue
        key = (
            safe_str(detail.get("code"))
            or f"{safe_str(detail.get('area'))}:{safe_str(detail.get('field'))}:{safe_str(detail.get('what_failed'))}"
        )
        if not key or key in seen:
            continue
        seen.add(key)
        clean.append(detail)
    return clean


def _planner_release_readiness_summary(final: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(final.get("meta"))
    civil = safe_dict(meta.get("civil_design_readiness"))
    construction = safe_dict(meta.get("construction_readiness"))
    package = safe_dict(meta.get("construction_package_manifest"))
    engine = safe_dict(meta.get("engine_readiness"))
    export_audit = safe_dict(meta.get("export_audit"))
    release_review = safe_dict(meta.get("release_review"))
    engine_gap_details = [
        safe_dict(item.get("first_gap_detail"))
        for item in safe_list(safe_dict(engine.get("summary")).get("most_important_backend_gaps"))
        if safe_dict(item.get("first_gap_detail"))
    ]
    structured_details = _dedupe_readiness_details(
        safe_list(civil.get("critical_blocker_details"))
        + safe_list(civil.get("production_blocker_details"))
        + safe_list(construction.get("blocker_details"))
        + safe_list(package.get("blocker_details"))
        + safe_list(engine_gap_details)
        + safe_list(export_audit.get("blocked_reason_details"))
        + safe_list(release_review.get("release_blocker_details"))
        + readiness_issue_explanations(safe_list(civil.get("critical_blockers")))
        + readiness_issue_explanations(safe_list(civil.get("production_blockers")))
        + readiness_issue_explanations(safe_list(construction.get("blockers")))
        + blocker_explanations(safe_list(meta.get("blockers")))
    )
    release_allowed = bool(package.get("release_allowed") or package.get("construction_export_allowed"))
    civil_ready = bool(civil.get("production_ready"))
    construction_ready = bool(construction.get("ready"))
    engine_ready = bool(engine.get("production_ready"))
    export_ready = bool(export_audit.get("production_export_ready") or export_audit.get("ready")) and not bool(
        export_audit.get("export_blocked")
    )
    ready = release_allowed and civil_ready and construction_ready and engine_ready and export_ready and not structured_details
    if ready:
        status = "release_ready"
    elif construction_ready and civil_ready:
        status = "release_blocked"
    elif civil_ready:
        status = "construction_blocked"
    else:
        status = "production_blocked"
    primary_detail = structured_details[0] if structured_details else {}
    return {
        "version": "planner_release_readiness_v1",
        "status": status,
        "release_ready": ready,
        "civil_production_ready": civil_ready,
        "construction_ready": construction_ready,
        "construction_release_allowed": release_allowed,
        "engine_production_ready": engine_ready,
        "export_production_ready": export_ready,
        "primary_attention": safe_str(primary_detail.get("code") or primary_detail.get("field")),
        "primary_attention_detail": primary_detail,
        "blocker_count": len(structured_details),
        "blocker_details": structured_details,
        "next_actions": dedupe_keep_order(
            [safe_str(detail.get("next_action")) for detail in structured_details if safe_str(detail.get("next_action"))]
        )[:10],
        "truth_label": (
            "Planner release readiness summarizes backend evidence only; construction use still requires official inputs, "
            "traceable deliverables, and licensed professional review."
        ),
    }


_CANONICAL_MODEL_META_KEYS = (
    "site_boundary",
    "stats",
    "grading",
    "drainage",
    "storm_pipes",
    "sanitary",
    "utilities",
    "coordination",
    "earthwork",
    "profiles",
    "cross_sections",
    "alignments",
)

_VOLATILE_MODEL_IDENTITY_KEYS = {
    "analysis_cache_hit_rate",
    "duration_ms",
    "elapsed_ms",
    "generated_at",
    "generated_on",
    "performance",
    "runtime_ms",
    "surface_object_id",
    "timestamp",
    "timing_ms",
    "timings_ms",
}


def _canonical_model_identity_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _canonical_model_identity_value(item)
            for key, item in value.items()
            if safe_str(key).lower() not in _VOLATILE_MODEL_IDENTITY_KEYS
        }
    if isinstance(value, list):
        return [_canonical_model_identity_value(item) for item in value]
    return value


def _canonical_model_identity_payload(final: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(final.get("meta"))
    actions = []
    for action in safe_list(final.get("actions")):
        rec = safe_dict(action)
        actions.append(
            {
                key: deepcopy(rec.get(key))
                for key in (
                    "task",
                    "layer",
                    "origin",
                    "points",
                    "center",
                    "radius",
                    "width",
                    "height",
                    "label",
                    "canonical_source_id",
                    "canonical_source_type",
                )
                if key in rec
            }
        )
    return {
        "payload_version": "canonical_model_identity_v1",
        "project_name": safe_str(final.get("project_name")),
        "units": safe_str(final.get("units")),
        "actions": actions,
        "meta": {
            key: _canonical_model_identity_value(deepcopy(meta.get(key)))
            for key in _CANONICAL_MODEL_META_KEYS
            if key in meta
        },
    }


def _attach_final_model_identity(final: Dict[str, Any]) -> None:
    meta = final.setdefault("meta", {})
    payload = _canonical_model_identity_payload(final)
    stable = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    digest = hashlib.sha256(stable.encode("utf-8")).hexdigest()
    model_id = safe_str(meta.get("canonical_model_id") or meta.get("final_model_id")) or f"MODEL-{digest[:16].upper()}"
    model_hash = safe_str(meta.get("canonical_model_hash") or meta.get("final_model_hash")) or digest
    meta["canonical_model_id"] = model_id
    meta["canonical_model_hash"] = model_hash
    meta.setdefault("final_model_id", model_id)
    meta.setdefault("final_model_hash", model_hash)
    meta["canonical_model_identity"] = {
        "version": "canonical_model_identity_v1",
        "canonical_model_id": model_id,
        "canonical_model_hash": model_hash,
        "hash_algorithm": "sha256",
    }


def _final_model_trace_fields(final: Dict[str, Any]) -> Dict[str, str]:
    meta = safe_dict(final.get("meta"))
    trace: Dict[str, str] = {}
    for key in ("canonical_model_id", "canonical_model_hash", "final_model_id", "final_model_hash"):
        value = safe_str(meta.get(key))
        if value:
            trace[key] = value
    return trace


def _attach_final_model_trace(final: Dict[str, Any]) -> None:
    meta = final.setdefault("meta", {})
    trace = _final_model_trace_fields(final)
    if not trace:
        return
    for key in ("truth_audit", "manual_validation", "reactive_update_report", "quantities", "cost_estimate"):
        payload = meta.get(key)
        if isinstance(payload, dict):
            payload.update(trace)
    depth = meta.get("depth_validation")
    if isinstance(depth, dict):
        for payload in depth.values():
            if isinstance(payload, dict):
                payload.update(trace)


def finalize_plan(plan: Dict[str, Any], *, parsed: Dict[str, Any], route: RoutingDecision) -> Dict[str, Any]:
    final = sanitize_plan(plan)
    _ensure_subdivision_road_preview(final, parsed)
    final.setdefault("meta", {})
    parsed_meta = safe_dict(parsed.get("meta"))
    for key in ("survey", "gis_layers", "existing_conditions", "coordinate_system", "standards_review_packet", "standards_acceptance", "design_standards", "jurisdiction_standards", "company_standards"):
        if key in parsed_meta and key not in final["meta"]:
            final["meta"][key] = deepcopy(parsed_meta.get(key))
    for key in ("survey", "gis_layers", "existing_conditions", "coordinate_system"):
        if key in parsed and key not in final["meta"]:
            final["meta"][key] = deepcopy(parsed.get(key))
    _synthesize_canonical_meta(parsed, final)
    final["meta"].setdefault("routing", {"path": route.path, "reasons": list(route.reasons)})
    final["meta"].setdefault("parsed_mode", lower_text(parsed.get("mode")))
    final["meta"].setdefault("project_type", lower_text(parsed.get("project_type")))
    final["meta"].setdefault("stats", collect_plan_stats(final))
    _attach_final_model_identity(final)
    if "quantities" not in final["meta"]:
        try:
            qty = compute_plan_quantities(final)
            final["meta"]["quantities"] = {
                "success": getattr(qty, "success", True),
                "message": getattr(qty, "message", ""),
                "totals": deepcopy(getattr(qty, "totals", {})),
                "tables": deepcopy(getattr(qty, "tables", {})),
                "warnings": list(getattr(qty, "warnings", [])),
                "assumptions": list(getattr(qty, "assumptions", [])),
                "explain": deepcopy(getattr(qty, "explain", {})),
            }
        except Exception as exc:
            final["meta"]["quantities"] = {"success": False, "message": f"Quantity computation failed: {exc}", "totals": {}}
    if "cost_estimate" not in final["meta"]:
        try:
            cost = compute_cost_estimate(final)
            final["meta"]["cost_estimate"] = {
                "success": getattr(cost, "success", True),
                "message": getattr(cost, "message", ""),
                "totals": deepcopy(getattr(cost, "totals", {})),
                "line_items": deepcopy(getattr(cost, "line_items", [])),
                "category_subtotals": deepcopy(getattr(cost, "category_subtotals", {})),
                "warnings": list(getattr(cost, "warnings", [])),
                "assumptions": list(getattr(cost, "assumptions", [])),
                "explain": deepcopy(getattr(cost, "explain", {})),
            }
        except Exception as exc:
            final["meta"]["cost_estimate"] = {"success": False, "message": f"Cost computation failed: {exc}", "totals": {}}
    try:
        finalize_export_metadata(final)
    except Exception as exc:
        final["meta"].setdefault("export_audit", {"ready": False, "error": safe_str(exc)})
    final["meta"]["existing_conditions_summary"] = _summarize_existing_conditions(final, parsed)
    final["meta"].setdefault("reactive_update_report", _reactive_report_from_plan(final))
    final["meta"]["depth_validation"] = {
        "stormwater": _validate_stormwater_depth(final),
        "water": _validate_water_system_depth(final),
        "roadway_corridor": _validate_roadway_corridor_depth(final),
    }
    _attach_final_model_trace(final)
    final["meta"]["civil_design_readiness"] = civil_design_readiness(final)
    final["meta"]["construction_readiness"] = construction_readiness(final)
    final["meta"]["construction_package_manifest"] = _build_construction_package_manifest(final)
    final["meta"]["engine_readiness"] = _evaluate_engine_readiness(final)
    final["meta"]["release_readiness_summary"] = _planner_release_readiness_summary(final)
    return final


def build_plan(
    parsed: Dict[str, Any],
    *,
    progress_callback: Optional[Callable[[str, str, int, str], None]] = None,
) -> Dict[str, Any]:
    parsed_checked = triple_check_parsed_payload(parsed)
    route = choose_routing_path(parsed_checked)
    raw = build_plan_from_parsed(parsed_checked, route, progress_callback=progress_callback)
    return finalize_plan(raw, parsed=parsed_checked, route=route)


def build_reactive_partial_plan(
    parsed: Dict[str, Any],
    *,
    changed_engine_ids: Iterable[str] = (),
    changed_stages: Iterable[str] = (),
    progress_callback: Optional[Callable[[str, str, int, str], None]] = None,
) -> Dict[str, Any]:
    from backend.planning.reactive_model import build_reactive_update_report

    parsed_checked = triple_check_parsed_payload(parsed)
    payload = deepcopy(parsed_checked)
    meta = dict(safe_dict(payload.get("meta")))
    orchestrator_meta = dict(safe_dict(meta.get("orchestrator_meta")))
    runtime_resume = dict(safe_dict(orchestrator_meta.get("runtime_resume")))
    checkpoint_plan = (
        safe_dict(runtime_resume.get("final_plan"))
        or safe_dict(meta.get("reactive_checkpoint_final_plan"))
        or safe_dict(payload.get("final_plan"))
    )
    if not checkpoint_plan:
        raise ValueError("Reactive partial rerun requires a checkpoint final_plan.")

    report = build_reactive_update_report(
        changed_engine_ids=changed_engine_ids or safe_list(meta.get("changed_engine_ids")),
        changed_stages=changed_stages or safe_list(meta.get("changed_targets")),
        stale_outputs=safe_list(meta.get("stale_outputs")),
    )
    dirty_state = dict(safe_dict(meta.get("system_dirty_state")))
    for stage_name in safe_list(report.get("impacted_stages")):
        stage_key = safe_str(stage_name)
        if not stage_key:
            continue
        dirty_state[stage_key] = {
            "state": "dirty",
            "reasons": [f"Reactive partial rerun impacted {stage_key}."],
            "source": "reactive_partial_rerun",
        }

    runtime_resume["final_plan"] = deepcopy(checkpoint_plan)
    orchestrator_meta["runtime_resume"] = runtime_resume
    meta["orchestrator_meta"] = orchestrator_meta
    meta["changed_engine_ids"] = list(report.get("changed_engine_ids") or [])
    meta["changed_targets"] = list(report.get("impacted_stages") or [])
    meta["stale_outputs"] = list(report.get("impacted_stages") or [])
    meta["system_dirty_state"] = dirty_state
    meta["reactive_update_report"] = deepcopy(report)
    meta["reactive_partial_rerun"] = {
        "enabled": True,
        "checkpoint_restored": True,
        "impacted_stages": list(report.get("impacted_stages") or []),
        "truth_label": "Planner restored checkpointed canonical state and reran only dirty downstream stages.",
    }
    payload["meta"] = meta
    payload.pop("final_plan", None)

    route = choose_routing_path(payload)
    raw = build_plan_from_parsed(payload, route, progress_callback=progress_callback)
    final = finalize_plan(raw, parsed=payload, route=route)
    final.setdefault("meta", {})
    final["meta"]["reactive_partial_rerun"] = {
        **safe_dict(final["meta"].get("reactive_partial_rerun")),
        "enabled": True,
        "checkpoint_restored": True,
        "impacted_stages": list(report.get("impacted_stages") or []),
    }
    return final


def build_plan_options(parsed: Dict[str, Any], candidate_payloads: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    parsed_checked = triple_check_parsed_payload(parsed)
    results: List[Dict[str, Any]] = []

    for idx, candidate in enumerate(candidate_payloads, start=1):
        payload = triple_check_parsed_payload(candidate)
        route = choose_routing_path(payload)
        option_name = safe_str(safe_dict(payload.get("__strategy__")).get("option_name"), f"Option {idx}")
        option_family = safe_str(safe_dict(payload.get("__strategy__")).get("strategy_family"), "generated")
        ctx = _run_model_first_workflow(payload, route, option_name=option_name, option_family=option_family)
        score = safe_float(safe_dict(safe_dict(ctx.final_plan.get("meta")).get("planner_score")).get("total"), 0.0)
        results.append({
            "option_name": option_name,
            "option_family": option_family,
            "score": score,
            "plan": deepcopy(ctx.final_plan),
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    best = deepcopy(results[0]["plan"]) if results else build_plan(parsed_checked)
    best.setdefault("meta", {})
    best["meta"]["multi_option"] = {
        "recommended_score": results[0]["score"] if results else 0.0,
        "alternatives": [
            {
                "option_name": r["option_name"],
                "option_family": r["option_family"],
                "score": r["score"],
            }
            for r in results[1:]
        ],
    }
    return best


# =============================================================================
# CLI HELPERS
# =============================================================================

def print_examples() -> None:
    print("\\nExamples:")
    print("/ask what makes a good subdivision layout?")
    print("/cmd create a commercial pad site on a 140 by 110 lot with front parking")
    print("/cmd create a 12 acre apartment site with buildings parking sidewalks drainage detention and utilities")
    print("/cmd create a storm drainage layout for a 120 by 100 lot with 4 inlets 1 trunk line and 1 pond")
    print("/surface-demo")
    print("/test-engine-only")
    print("quit\\n")


def _parse_command_text(command_text: str) -> Dict[str, Any]:
    parsed_raw = command_mode(command_text)
    return triple_check_parsed_payload(parsed_raw)


def run_command_mode(command_text: str) -> None:
    print("AI PARSER FILE =", parsers.ai_parser.__file__)
    parsed = _parse_command_text(command_text)

    print("\\nParsed JSON:\\n")
    print(json.dumps(parsed, indent=2))
    print("\\n-------------------\\n")

    route = choose_routing_path(parsed)
    expanded = build_plan_from_parsed(parsed, route)
    expanded = finalize_plan(expanded, parsed=parsed, route=route)

    print("\\nExpanded Plan JSON:\\n")
    print(json.dumps(expanded, indent=2))
    print("\\n-------------------\\n")

    preview_now = input("Preview this plan now? (y/n): ").strip().lower()
    if preview_now == "y":
        preview_plan(expanded)

    save_now = input("Save as DXF for AutoCAD? (y/n): ").strip().lower()
    if save_now == "y":
        filename = save_dxf(expanded)
        print(f"\\nSaved DXF: {filename}\\n")

    print("\\n-------------------\\n")


def main() -> None:
    print(f"\\n{APP_NAME} v{APP_VERSION}")
    print_examples()

    while True:
        command = input("Enter command: ").strip()
        if not command:
            continue
        if command.lower() in {"quit", "exit"}:
            print("Goodbye.")
            break

        if command.startswith("/ask"):
            answer = ask_mode(command[4:].strip())
            print("\\n" + answer + "\\n")
            continue

        if command.startswith("/cmd"):
            run_command_mode(command[4:].strip())
            continue

        if command == "/surface-demo":
            demo = {
                "project_name": "Surface Demo",
                "units": "ft",
                "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 120.0},
                "site_plan": {"parking_count": 24, "building_width": 48.0, "building_depth": 36.0},
                "mode": "site_plan",
                "project_type": "commercial_pad",
            }
            out = build_plan(demo)
            preview_plan(out)
            continue

        if command == "/test-engine-only":
            demo = {
                "project_name": "Drainage Test",
                "units": "ft",
                "lot": {"x": 0.0, "y": 0.0, "w": 180.0, "h": 120.0},
                "mode": "drainage",
                "project_type": "drainage_network",
                "drainage": {"inlet_count": 5, "trunk_line_count": 2, "pond_count": 1},
            }
            out = build_plan(demo)
            print(json.dumps(out, indent=2))
            continue

        print("Unknown command.")
        print_examples()


if __name__ == "__main__":
    main()
