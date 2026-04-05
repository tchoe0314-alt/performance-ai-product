from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional

from core.config import (
    DEFAULT_LOT_HEIGHT,
    DEFAULT_LOT_WIDTH,
    DEFAULT_LOT_X,
    DEFAULT_LOT_Y,
    DEFAULT_PAD_DEPTH,
    DEFAULT_PAD_ELEV,
    DEFAULT_PAD_WIDTH,
)
from core.geometry_core import EngineeringDomain, EngineeringObject, Point3D, ZoneType, rect_zone
from core.project_manager import ConflictRecord, ConflictSeverity, DependencyState
from engines.grading_engine import GradingEngine, GradingRequest
from engines.surface_engine import GridSurface

from .common import lower_text, safe_dict, safe_float, safe_int, safe_list, safe_str
from .field_contract import (
    field_path_is_omitted,
    filter_actions_by_field_intent,
    preserve_field_states,
    unwrap_fields_for_execution,
)
from .runtime import PlannerExecutionContext, _lot_area, _mark_dependency_state, collect_plan_stats


def run_layout_stage(
    ctx: PlannerExecutionContext,
    *,
    legacy_expand_payload: Callable[[Dict[str, Any]], Dict[str, Any]],
    store_expanded_plan: Callable[[Any, Dict[str, Any]], None],
    project_model_to_plan: Callable[[Any, str], Dict[str, Any]],
) -> None:
    manager = ctx.manager
    project = manager.project
    parsed = preserve_field_states(ctx.parsed)
    lot = safe_dict(unwrap_fields_for_execution(parsed.get("lot")))
    site_plan = safe_dict(unwrap_fields_for_execution(parsed.get("site_plan")))

    try:
        execution_payload = unwrap_fields_for_execution(parsed)
        expanded = legacy_expand_payload(execution_payload)
        if isinstance(expanded, dict):
            expanded_actions = filter_actions_by_field_intent(parsed, safe_list(expanded.get("actions")))
            expanded["actions"] = expanded_actions
        if safe_list(expanded.get("actions")):
            store_expanded_plan(project, expanded)

        build_w = max(20.0, safe_float(site_plan.get("building_width"), DEFAULT_PAD_WIDTH))
        build_d = max(20.0, safe_float(site_plan.get("building_depth"), DEFAULT_PAD_DEPTH))
        lot_x = safe_float(lot.get("x"), DEFAULT_LOT_X)
        lot_y = safe_float(lot.get("y"), DEFAULT_LOT_Y)
        lot_w = safe_float(lot.get("w"), DEFAULT_LOT_WIDTH)
        lot_h = safe_float(lot.get("h"), DEFAULT_LOT_HEIGHT)

        building_action = None
        for action in safe_list(expanded.get("actions")):
            if not isinstance(action, dict):
                continue
            if lower_text(action.get("task")) == "rectangle" and safe_str(action.get("layer")).upper() == "BUILDING":
                building_action = action
                break

        if building_action is not None:
            origin = safe_list(building_action.get("origin"))
            bx = safe_float(origin[0], lot_x) if len(origin) >= 2 else lot_x
            by = safe_float(origin[1], lot_y) if len(origin) >= 2 else lot_y
            build_w = max(1.0, safe_float(building_action.get("width"), build_w))
            build_d = max(1.0, safe_float(building_action.get("height"), build_d))
        else:
            bx = lot_x + max(5.0, (lot_w - build_w) / 2.0)
            by = lot_y + max(5.0, (lot_h - build_d) / 2.0)

        project.add_zone(rect_zone(bx, by, build_w, build_d, zone_type=ZoneType.BUILDING, name="BUILDING"))
        project.add_object(
            EngineeringObject(
                kind="building",
                name="BUILDING",
                anchor=Point3D(bx + build_w / 2.0, by + build_d / 2.0, DEFAULT_PAD_ELEV),
                tags=["layout", "building"],
                domain=EngineeringDomain.BUILDING,
                properties={"width": build_w, "depth": build_d},
            )
        )

        if field_path_is_omitted(parsed, "site_plan.parking_count"):
            parking_count = 0
        else:
            parking_count = max(
                0,
                safe_int(
                    safe_dict(expanded.get("meta")).get("parking_count"),
                    safe_int(site_plan.get("parking_count"), 24),
                ),
            )
        layout_stats = collect_plan_stats(
            expanded if expanded else project_model_to_plan(project, parsed.get("project_name") or "Generated Plan")
        )
        manager.set_metric("parking_count", parking_count, category="layout")
        manager.set_metric("lot_area_sf", _lot_area(parsed), units="sf", category="layout")
        manager.set_metric("layout_success", 1.0, category="layout")
        manager.set_metric("layout_action_count", len(safe_list(expanded.get("actions"))), category="layout")
        manager.set_metric("layout_building_area_sf", safe_float(layout_stats.get("estimated_building_area_sf"), 0.0), category="layout")
        manager.set_metric("layout_parking_area_sf", safe_float(layout_stats.get("estimated_parking_area_sf"), 0.0), category="layout")
        manager.set_metric("layout_road_area_sf", safe_float(layout_stats.get("estimated_road_area_sf"), 0.0), category="layout")
        manager.set_metric("layout_impervious_area_sf", safe_float(layout_stats.get("estimated_impervious_area_sf"), 0.0), category="layout")
        _mark_dependency_state(manager, "layout", "grading", DependencyState.FRESH, reason="Layout updated.")
        manager.mark_system_complete("layout", "Layout stage completed.")
        manager.invalidate_from("layout")
        ctx.add_stage(
            "layout",
            True,
            "Layout stage completed.",
            parking_count=parking_count,
            building_width=build_w,
            building_depth=build_d,
            expanded_action_count=len(safe_list(expanded.get("actions"))),
        )
    except Exception as exc:
        ctx.record_warning(f"Layout stage failed: {exc}")
        manager.add_conflict(
            ConflictRecord(
                code="LAYOUT_STAGE_FAILED",
                message=str(exc),
                severity=ConflictSeverity.WARNING,
                category="layout",
            )
        )
        ctx.add_stage("layout", False, f"Layout stage failed: {exc}")


def run_grading_stage(
    ctx: PlannerExecutionContext,
    hydrology: Dict[str, Any],
    *,
    strict_mode_enabled: Callable[[Dict[str, Any]], bool],
    build_existing_surface: Callable[[Dict[str, Any]], GridSurface],
    build_grade_elements: Callable[[Any, Dict[str, Any]], List[Any]],
    grading_surface_actions: Callable[[Any, Optional[GridSurface], Optional[GridSurface]], Any],
    canonical_grading_payload: Callable[..., Dict[str, Any]],
    record_strict_stage_failure: Callable[..., None],
    install_minimum_grading_actions: Callable[[Any, Dict[str, Any]], int],
    merge_actions_into_expanded_plan: Callable[[Any, Any], None],
    call_with_compatible_kwargs: Callable[..., Any],
) -> None:
    manager = ctx.manager
    project = manager.project
    parsed = ctx.parsed
    strict_mode = strict_mode_enabled(parsed)

    try:
        if field_path_is_omitted(parsed, "grading"):
            ctx.record_assumption("Grading omitted by user intent; planner preserved omission and skipped grading stage.")
            ctx.add_stage("grading", True, "Grading stage skipped because source=omit.")
            return

        execution_payload = unwrap_fields_for_execution(parsed)
        existing_surface = build_existing_surface(execution_payload)
        project.meta["existing_surface"] = existing_surface

        engine = GradingEngine(existing_surface)
        grade_elements = build_grade_elements(project, execution_payload)

        if hasattr(engine, "extend_elements"):
            engine.extend_elements(grade_elements)
        elif hasattr(engine, "elements"):
            current = list(getattr(engine, "elements", []) or [])
            current.extend(grade_elements)
            engine.elements = current

        result = None
        build_kwargs = {
            "request": GradingRequest(create_project_objects=False, create_project_zones=False),
            "project": project,
        }
        for caller in (
            lambda: call_with_compatible_kwargs(engine.build, **build_kwargs),
            lambda: call_with_compatible_kwargs(engine.build, GradingRequest(create_project_objects=False, create_project_zones=False)),
            lambda: call_with_compatible_kwargs(engine.build),
        ):
            try:
                result = caller()
                if result is not None:
                    break
            except Exception:
                continue

        if result is None and hasattr(engine, "apply_to_project"):
            result = engine.apply_to_project(
                project,
                GradingRequest(create_project_objects=False, create_project_zones=False),
            )

        if result is None:
            if strict_mode:
                manager.set_metric("grading_success", 0.0, category="grading")
                record_strict_stage_failure(
                    ctx,
                    "grading",
                    "STRICT_GRADING_FALLBACK_BLOCKED",
                    "STRICT mode blocked grading fallback because the grading engine did not produce a real surface solution.",
                    category="grading",
                    dependency="grading_engine",
                    computation_step="surface_generation",
                )
                return
            fallback_count = install_minimum_grading_actions(project, parsed)
            manager.set_metric("grading_success", 1.0, category="grading")
            manager.set_metric("grading_low_point_count", 1, category="grading")
            ctx.record_assumption("Grading engine could not build a full surface; planner installed minimum grading geometry fallback.")
            ctx.add_stage(
                "grading",
                True,
                "Grading stage completed using minimum grading fallback.",
                low_point_count=1,
                cut_cf=0.0,
                fill_cf=0.0,
                net_cf=0.0,
                added_actions=fallback_count,
                fallback_used=True,
                fallback_type="minimum_grading_geometry",
                dependency="grading_engine",
                computation_step="surface_generation",
            )
            return

        proposed_surface = getattr(result, "proposed_surface", None)
        project.meta["proposed_surface"] = proposed_surface

        low_points = safe_list(getattr(result, "low_points", []))
        flow_samples = safe_list(getattr(result, "flow_samples", []))
        cut_volume = safe_float(getattr(result, "cut_volume", 0.0), 0.0)
        fill_volume = safe_float(getattr(result, "fill_volume", 0.0), 0.0)
        net_volume = safe_float(getattr(result, "net_volume", 0.0), 0.0)
        success = bool(getattr(result, "success", True))
        message = safe_str(getattr(result, "message", "Grading stage completed."))
        grade_actions, grading_action_stats = grading_surface_actions(result, existing_surface, proposed_surface)
        merge_actions_into_expanded_plan(project, grade_actions, grading_surface_export=True)
        grading_payload = canonical_grading_payload(
            existing_surface=existing_surface,
            result=result,
            derived_action_stats=grading_action_stats,
            grade_elements=grade_elements,
        )
        project.meta["grading_summary"] = grading_payload
        manager.latest_outputs["grading"] = deepcopy(grading_payload)

        manager.set_metric("grading_success", 1.0 if success else 0.0, category="grading")
        manager.set_metric("grading_low_point_count", len(low_points), category="grading")
        manager.set_metric("grading_flow_sample_count", len(flow_samples), category="grading")
        manager.set_metric("grading_proposed_contour_count", safe_int(grading_action_stats.get("proposed_contour_count"), 0), category="grading")
        manager.set_metric("grading_existing_contour_count", safe_int(grading_action_stats.get("existing_contour_count"), 0), category="grading")
        manager.set_metric("grading_spot_grade_count", safe_int(grading_action_stats.get("spot_grade_count"), 0), category="grading")
        manager.set_metric("earthwork_cut_cf", cut_volume, units="cf", category="earthwork")
        manager.set_metric("earthwork_fill_cf", fill_volume, units="cf", category="earthwork")
        manager.set_metric("earthwork_net_cf", net_volume, units="cf", category="earthwork")

        _mark_dependency_state(manager, "layout", "grading", DependencyState.FRESH, reason="Grading rebuilt from layout.")
        _mark_dependency_state(manager, "grading", "drainage", DependencyState.STALE, reason="Drainage depends on grading.")
        manager.invalidate_from("grading")

        ctx.add_stage(
            "grading",
            success,
            message,
            low_point_count=len(low_points),
            flow_sample_count=len(flow_samples),
            cut_cf=round(cut_volume, 2),
            fill_cf=round(fill_volume, 2),
            net_cf=round(net_volume, 2),
            added_actions=len(grade_actions),
            contour_count=safe_int(grading_action_stats.get("proposed_contour_count"), 0),
            spot_grade_count=safe_int(grading_action_stats.get("spot_grade_count"), 0),
            flow_arrow_count=safe_int(grading_action_stats.get("flow_arrow_count"), 0),
            terrain_inferred=bool(safe_dict(grading_payload.get("existing_surface")).get("terrain_inferred")),
        )
    except Exception as exc:
        message = f"Grading stage failed: {exc}"
        manager.set_metric("grading_success", 0.0, category="grading")
        if strict_mode:
            record_strict_stage_failure(
                ctx,
                "grading",
                "STRICT_GRADING_STAGE_FAILED",
                message,
                category="grading",
                dependency="grading_engine",
                computation_step="stage_execution",
            )
        else:
            ctx.record_warning(message)
            manager.add_conflict(
                ConflictRecord(
                    code="GRADING_STAGE_FAILED",
                    message=str(exc),
                    severity=ConflictSeverity.WARNING,
                    category="grading",
                )
            )
            ctx.add_stage("grading", False, message)
