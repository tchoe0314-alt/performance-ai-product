from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional

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
from engines.storm.hydraulic_engine import analyze_storm_hydraulics
from engines.storm.storm_network_engine import build_storm_network
from engines.storm.storm_types import (
    HydraulicAnalysisRequest,
    StormNetworkRequest,
    StormNode,
    StormNodeType,
    StormPoint,
)

from .common import lower_text, safe_dict, safe_float, safe_int, safe_list, safe_str
from .field_contract import field_path_is_omitted, unwrap_fields_for_execution
from .runtime import PlannerExecutionContext, _mark_dependency_state


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

        surface = project.meta.get("proposed_surface") or project.meta.get("existing_surface") or build_existing_surface(execution_payload)
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
        if engine is not None and hasattr(engine, "clear_pond_targets"):
            try:
                engine.clear_pond_targets()
            except Exception:
                pass
        if engine is not None and hasattr(engine, "add_pond_target"):
            try:
                for target in safe_list(coordination.get("preferred_targets")):
                    target_data = safe_dict(target)
                    engine.add_pond_target(
                        safe_str(target_data.get("name"), "OUTFALL_A"),
                        safe_float(target_data.get("x"), safe_float(lot.get("x"), DEFAULT_LOT_X) + safe_float(lot.get("w"), DEFAULT_LOT_WIDTH) - 10.0),
                        safe_float(target_data.get("y"), safe_float(lot.get("y"), DEFAULT_LOT_Y) + 10.0),
                        radius=max(1.0, safe_float(target_data.get("radius"), POND_RADIUS)),
                    )
            except Exception:
                pass

        summary = None
        if engine is not None and hasattr(engine, "design_network"):
            hydraulic = HydraulicInputs(
                runoff_c=safe_float(hydrology.get("runoff_c"), PIPE_RUNOFF_C),
                intensity_in_hr=safe_float(hydrology.get("intensity_in_hr"), PIPE_INTENSITY_IN_HR),
                min_pipe_slope=PIPE_MIN_SLOPE,
                min_pipe_diameter_in=12,
            )
            try:
                summary = engine.design_network(
                    mode=getattr(DrainageEngine, "ASSISTED_MODE", "assisted"),
                    hydraulic=hydraulic,
                    max_inlets=PIPE_MAX_INLETS,
                    min_slope=max(MIN_SLOPE, 0.001),
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
        canonical_drainage = enrich_drainage_basins_with_engineering(
            canonical_drainage,
            engine=engine,
            hydrology=hydrology,
            coordination=coordination,
        )
        canonical_drainage["coordination"] = deepcopy(coordination)
        canonical_drainage["surface_guidance"] = {
            "downhill_vector": deepcopy(safe_dict(coordination.get("downhill_vector"))),
            "preferred_targets": deepcopy(safe_list(coordination.get("preferred_targets"))),
            "grading_low_point_count": safe_int(coordination.get("grading_low_point_count"), 0),
            "grading_flow_sample_count": safe_int(coordination.get("grading_flow_sample_count"), 0),
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

        drainage_meta = safe_dict(manager.latest_outputs.get("drainage", project.meta.get("drainage_canonical", {})))
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
        storm_catchments = storm_catchments_from_drainage(
            drainage_meta,
            runoff_c=safe_float(hydrology.get("runoff_c"), PIPE_RUNOFF_C),
            intensity_in_hr=safe_float(hydrology.get("intensity_in_hr"), PIPE_INTENSITY_IN_HR),
        )
        preferred_outfall = safe_dict(coordination.get("preferred_outfall"))
        outfall_x = safe_float(preferred_outfall.get("x"), storm_inlets[0].point.x + 40.0)
        outfall_y = safe_float(preferred_outfall.get("y"), storm_inlets[0].point.y - 20.0)
        outfall_z = safe_float(preferred_outfall.get("z"), safe_float(storm_inlets[0].rim_elev_ft, DEFAULT_PAD_ELEV) - 1.0)
        outfalls: List[StormNode] = []
        if not storm_basins:
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
                basins=storm_basins,
                outfalls=outfalls,
                default_pipe_material="RCP",
                default_mannings_n=PIPE_MANNINGS_N,
                min_pipe_slope=PIPE_MIN_SLOPE,
                min_cover_ft=PIPE_MIN_COVER_FT,
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
