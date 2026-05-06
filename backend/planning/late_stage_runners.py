from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List

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
from core.project_manager import ConflictRecord, ConflictSeverity, DependencyState
from engines.autofix_engine import autofix_site_layout
from engines.error_check_engine import run_plan_checks

from .common import canonical_stage_output, dedupe_keep_order, lower_text, safe_dict, safe_float, safe_int, safe_list, safe_str
from .field_contract import FIELD_SOURCE_INFER, field_path_is_omitted, omission_flags_from_parsed, unwrap_fields_for_execution
from .runtime import PlannerExecutionContext, PlanQualityReport, _lot_area, _mark_dependency_state, collect_plan_stats


def run_earthwork_stage(ctx: PlannerExecutionContext) -> None:
    manager = ctx.manager
    try:
        manager.mark_system_running("earthwork", "Running earthwork stage.")
        cut = safe_float(getattr(manager.metrics.get("earthwork_cut_cf"), "value", 0.0), 0.0)
        fill = safe_float(getattr(manager.metrics.get("earthwork_fill_cf"), "value", 0.0), 0.0)
        net = safe_float(getattr(manager.metrics.get("earthwork_net_cf"), "value", 0.0), 0.0)
        manager.set_metric("earthwork_success", 1.0, category="earthwork")
        _mark_dependency_state(
            manager,
            "utility_network",
            "earthwork",
            DependencyState.FRESH,
            reason="Earthwork finalized after utility coordination.",
        )
        _mark_dependency_state(manager, "earthwork", "qa", DependencyState.STALE, reason="QA depends on earthwork.")
        manager.mark_system_complete("earthwork", "Earthwork stage completed.")
        manager.invalidate_from("earthwork")
        ctx.add_stage("earthwork", True, "Earthwork stage completed.", cut_cf=cut, fill_cf=fill, net_cf=net)
    except Exception as exc:
        ctx.record_warning(f"Earthwork stage failed: {exc}")
        manager.mark_system_failed("earthwork", str(exc), [str(exc)])
        manager.add_conflict(
            ConflictRecord(
                code="EARTHWORK_STAGE_FAILED",
                message=str(exc),
                severity=ConflictSeverity.WARNING,
                category="earthwork",
            )
        )
        ctx.add_stage("earthwork", False, f"Earthwork stage failed: {exc}")


def run_qa_stage(
    ctx: PlannerExecutionContext,
    *,
    project_model_to_plan: Callable[[Any, str], Dict[str, Any]],
    manual_mode_enabled: Callable[[Dict[str, Any]], bool],
) -> PlanQualityReport:
    report = PlanQualityReport()
    manager = ctx.manager
    project = manager.project
    parsed = ctx.parsed

    try:
        plan = project_model_to_plan(project, parsed.get("project_name") or "Generated Plan")
        plan.setdefault("meta", {})
        plan["meta"]["manager_export"] = manager.export_metrics() if hasattr(manager, "export_metrics") else {}
        plan["meta"]["grading"] = canonical_stage_output(project, manager, "grading")
        plan["meta"]["drainage"] = canonical_stage_output(project, manager, "drainage")
        plan["meta"]["storm_pipes"] = canonical_stage_output(project, manager, "storm_pipes")
        plan["meta"]["sanitary"] = canonical_stage_output(project, manager, "sanitary")
        plan["meta"]["parking_program"] = canonical_stage_output(project, manager, "parking_program")
        plan["meta"]["utilities"] = canonical_stage_output(project, manager, "utilities")
        plan["meta"]["coordination"] = canonical_stage_output(project, manager, "coordination")
        plan["meta"]["profiles"] = canonical_stage_output(project, manager, "profiles")
        plan["meta"]["cross_sections"] = canonical_stage_output(project, manager, "cross_sections")
        stats = collect_plan_stats(plan)
        report.stats = stats

        lot_area = _lot_area(parsed)
        if lot_area > 0:
            report.stats["lot_area_sf"] = round(lot_area, 2)
            report.stats["estimated_impervious_coverage_ratio"] = round(
                safe_float(stats.get("estimated_impervious_area_sf"), 0.0) / lot_area,
                4,
            )

        report.checks_run.append("validate_site_layout")
        try:
            validate_site_layout(plan)
        except Exception as exc:
            report.add("SITE_LAYOUT_VALIDATION", "warning", f"Site layout validation raised: {exc}")

        report.checks_run.append("validate_expanded_site_plan")
        try:
            validate_expanded_site_plan(plan)
        except Exception as exc:
            report.add("EXPANDED_PLAN_VALIDATION", "warning", f"Expanded site plan validation raised: {exc}")

        drainage_summary = project.meta.get("drainage_summary")
        pond_omitted = field_path_is_omitted(parsed, "drainage.pond_count")
        if drainage_summary is not None and not field_path_is_omitted(parsed, "drainage"):
            report.checks_run.append("validate_drainage_summary")
            try:
                inlet_count = len(getattr(drainage_summary, "inlet_records", []) or [])
                pond_count = len(getattr(drainage_summary, "basin_records", []) or [])
                if pond_omitted:
                    pond_count = max(1, pond_count)
                if hasattr(drainage_summary, "warning_count") and callable(drainage_summary.warning_count):
                    warning_count = int(drainage_summary.warning_count())
                else:
                    warning_count = len(getattr(drainage_summary, "warnings", []) or [])

                validate_drainage_summary(
                    drainage_summary,
                    inlet_count,
                    pond_count,
                    warning_count,
                )
            except Exception as exc:
                report.add("DRAINAGE_VALIDATION", "warning", f"Drainage validation raised: {exc}")

        try:
            constraints = [
                ObjectOverlapConstraint(),
                ZoneOverlapConstraint(),
                DuplicateObjectAnchorConstraint(),
            ]
            try:
                constraints.append(MaxSpanConstraint(max_span=500.0))
            except TypeError:
                try:
                    constraints.append(MaxSpanConstraint(500.0))
                except Exception:
                    constraints.append(MaxSpanConstraint())
            evaluate_constraints(project, constraints)
        except Exception as exc:
            report.add("CONSTRAINT_EVALUATION", "warning", f"Constraint evaluation raised: {exc}")

        try:
            qa_payload = run_plan_checks(unwrap_fields_for_execution(parsed), plan) if callable(run_plan_checks) else None

            if isinstance(qa_payload, dict):
                warnings_list = safe_list(qa_payload.get("warnings", []))
                errors_list = safe_list(qa_payload.get("errors", []))
            elif isinstance(qa_payload, (list, tuple)):
                warnings_list = []
                errors_list = []
                for item in qa_payload:
                    if isinstance(item, dict):
                        text = safe_str(item.get("message") or item.get("warning") or item.get("error"))
                    else:
                        text = safe_str(item)
                    if text:
                        warnings_list.append(text)
            else:
                warnings_list = []
                errors_list = []

            ignored_unknown_tasks = {"north_arrow", "point"}
            omit_flags = omission_flags_from_parsed(parsed)
            manual_mode = manual_mode_enabled(parsed)
            filtered_warnings: List[str] = []
            for warning in warnings_list:
                text = safe_str(warning)
                lowered = lower_text(text)
                if any(f"unknown task '{task}'" in lowered for task in ignored_unknown_tasks):
                    continue
                if manual_mode and any(
                    phrase in lowered
                    for phrase in (
                        "profile-like signal was found",
                        "cross-section-like signal was found",
                    )
                ):
                    continue
                if omit_flags.get("drainage") and any(term in lowered for term in ("inlet", "drainage", "pond", "pipe network", "outfall", "storm")):
                    continue
                if omit_flags.get("utilities") and any(term in lowered for term in ("utility", "water line", "sanitary", "sewer", "pipe network signals")):
                    continue
                if omit_flags.get("parking") and any(term in lowered for term in ("parking", "stall")):
                    continue
                filtered_warnings.append(text)

            for path, field in safe_dict(safe_dict(parsed.get("meta")).get("field_states")).items():
                if isinstance(field, dict) and field.get("source") == FIELD_SOURCE_INFER and field.get("assumption"):
                    ctx.record_assumption(f"{path}: {safe_str(field.get('assumption'))}")

            for warning in filtered_warnings:
                report.add("ENGINE_QA_WARNING", "warning", safe_str(warning))
            for error in errors_list:
                report.add("ENGINE_QA_ERROR", "error", safe_str(error))

        except Exception as exc:
            report.add("ERROR_CHECK_ENGINE", "warning", f"Error check engine raised: {exc}")

        manager.set_metric("qa_warning_count", report.warning_count(), category="qa")
        manager.set_metric("qa_error_count", report.error_count(), category="qa")

        for issue in report.issues:
            sev = ConflictSeverity.ERROR if lower_text(issue.severity) == "error" else ConflictSeverity.WARNING
            manager.add_conflict(
                ConflictRecord(
                    code=issue.code,
                    message=issue.message,
                    severity=sev,
                    category="qa",
                )
            )

        coordination = safe_dict(plan["meta"].get("coordination"))
        if safe_int(coordination.get("resolved_count"), 0) > 0 and not manual_mode_enabled(parsed):
            report.add(
                "COORDINATION_RESOLVED",
                "warning" if safe_list(coordination.get("assumption_resolutions")) else "warning",
                f"Coordination auto-resolved {safe_int(coordination.get('resolved_count'), 0)} conflict(s) across {len(safe_list(coordination.get('changed_systems')))} system group(s).",
            )
        for conflict in safe_list(coordination.get("unresolved_conflicts")):
            report.add(
                "COORDINATION_UNRESOLVED",
                "error",
                f"Unresolved coordination conflict remains: {safe_str(safe_dict(conflict).get('conflict_type'), 'conflict')}.",
            )
        for conflict in safe_list(coordination.get("assumption_resolutions")):
            report.add(
                "COORDINATION_ASSUMED",
                "warning",
                f"Coordination conflict was resolved using assisted-mode assumptions: {safe_str(safe_dict(conflict).get('conflict_type'), 'conflict')}.",
            )

        ctx.add_stage(
            "qa",
            report.error_count() == 0,
            "QA stage completed.",
            warning_count=report.warning_count(),
            error_count=report.error_count(),
        )
        return report
    except Exception as exc:
        ctx.record_warning(f"QA stage failed: {exc}")
        report.add("QA_STAGE_FAILED", "warning", str(exc))
        ctx.add_stage("qa", False, f"QA stage failed: {exc}")
        return report


def apply_fix_pass(ctx: PlannerExecutionContext, report: PlanQualityReport) -> None:
    parsed = ctx.parsed
    manager = ctx.manager

    layout_related = [i for i in report.issues if i.code in {"SITE_LAYOUT_VALIDATION", "EXPANDED_PLAN_VALIDATION", "CONSTRAINT_EVALUATION"}]
    drainage_related = [i for i in report.issues if "DRAINAGE" in i.code]
    pipe_related = [c for c in manager.unresolved_conflicts_by_category("pipes")]
    utility_related = [c for c in manager.unresolved_conflicts_by_category("utilities")]
    grading_related = [c for c in manager.unresolved_conflicts_by_category("grading")]
    qa_errors = [i for i in report.issues if lower_text(i.severity) == "error"]
    fix_summary = {
        "layout_issue_count": len(layout_related),
        "drainage_issue_count": len(drainage_related),
        "pipe_conflict_count": len(pipe_related),
        "utility_conflict_count": len(utility_related),
        "grading_conflict_count": len(grading_related),
        "qa_error_count": len(qa_errors),
        "dominant_issue_categories": [],
        "changed_targets": [],
        "autofix_actions": [],
        "effective_change": False,
    }
    issue_category_counts = {
        "layout": len(layout_related),
        "drainage": len(drainage_related),
        "pipes": len(pipe_related),
        "utilities": len(utility_related),
        "grading": len(grading_related),
        "qa": len(qa_errors),
    }
    fix_summary["dominant_issue_categories"] = [
        name
        for name, count in sorted(issue_category_counts.items(), key=lambda item: (-item[1], item[0]))
        if count > 0
    ]

    if not layout_related and not drainage_related and not pipe_related and not utility_related and not grading_related and not qa_errors:
        manager.project.meta["fix_summary"] = deepcopy(fix_summary)
        ctx.add_stage("fix", True, "No deterministic fix pass changes were required.", fix_summary=deepcopy(fix_summary))
        return

    changed_targets: List[str] = []

    if layout_related:
        try:
            legacy_layout = unwrap_fields_for_execution(parsed)
            fixed_layout = autofix_site_layout(legacy_layout, layout_related)
            if isinstance(fixed_layout, dict):
                if "building" in fixed_layout:
                    parsed["building"] = fixed_layout["building"]
                if "parking" in fixed_layout:
                    parsed["parking"] = fixed_layout["parking"]
                if "driveway" in fixed_layout:
                    parsed["driveway"] = fixed_layout["driveway"]
                parsed["_planner_review_notes"] = dedupe_keep_order(
                    list(parsed.get("_planner_review_notes") or []) + ["Applied deterministic planner fix pass using autofix_site_layout."]
                )
                changed_targets.extend(["layout", "grading", "drainage", "storm_pipes", "utility_network", "earthwork"])
                fix_summary["autofix_actions"].append("layout_autofix")
        except Exception as exc:
            ctx.record_warning(f"Fix pass failed in layout autofix: {exc}")

    if drainage_related:
        parsed.setdefault("drainage", {})
        drainage = safe_dict(parsed.get("drainage"))
        drainage["trunk_line_count"] = max(1, safe_int(drainage.get("trunk_line_count"), 1))
        parsed["drainage"] = drainage
        parsed["layout_strategy"] = "drainage_friendly"
        changed_targets.extend(["drainage", "storm_pipes", "utility_network"])
        fix_summary["autofix_actions"].append("drainage_retry_bias")

    if pipe_related:
        parsed.setdefault("meta", {})
        parsed["meta"]["pipe_retry_bias"] = True
        parsed.setdefault("optimization_goals", {})
        goals = safe_dict(parsed["optimization_goals"])
        goals["goal"] = "reduce_pipe_length"
        parsed["optimization_goals"] = goals
        changed_targets.extend(["storm_pipes", "utility_network"])
        fix_summary["autofix_actions"].append("pipe_retry_bias")

    if utility_related:
        parsed["layout_strategy"] = "utility_efficient"
        parsed.setdefault("meta", {})
        parsed["meta"]["utility_retry_bias"] = True
        changed_targets.extend(["utility_network", "earthwork"])
        fix_summary["autofix_actions"].append("utility_retry_bias")

    if grading_related:
        parsed["layout_strategy"] = "grading_friendly"
        parsed.setdefault("optimization_goals", {})
        goals = safe_dict(parsed["optimization_goals"])
        goals["goal"] = "reduce_grading"
        parsed["optimization_goals"] = goals
        changed_targets.extend(["grading", "drainage", "storm_pipes", "utility_network", "earthwork"])
        fix_summary["autofix_actions"].append("grading_retry_bias")

    if qa_errors:
        qa_error_codes = {lower_text(safe_str(issue.code)) for issue in qa_errors}
        parsed.setdefault("meta", {})
        parsed["meta"]["planner_passes"] = max(3, safe_int(safe_dict(parsed["meta"]).get("planner_passes"), 2) + 1)
        if any("storm" in code or "pipe" in code for code in qa_error_codes):
            changed_targets.extend(["drainage", "storm_pipes"])
            fix_summary["autofix_actions"].append("storm_validation_retry")
        if any("sanitary" in code or "sewer" in code for code in qa_error_codes):
            changed_targets.extend(["sanitary", "utility_network"])
            fix_summary["autofix_actions"].append("sanitary_validation_retry")
        if any("utility" in code or "water" in code for code in qa_error_codes):
            changed_targets.extend(["utility_network"])
            fix_summary["autofix_actions"].append("utility_validation_retry")
        if any("grade" in code or "contour" in code or "slope" in code for code in qa_error_codes):
            changed_targets.extend(["grading", "drainage", "earthwork"])
            fix_summary["autofix_actions"].append("grading_validation_retry")
        if any("drain" in code or "basin" in code or "detention" in code for code in qa_error_codes):
            changed_targets.extend(["drainage", "storm_pipes", "earthwork"])
            fix_summary["autofix_actions"].append("drainage_validation_retry")
        if any("layout" in code or "constraint" in code or "site" in code for code in qa_error_codes):
            changed_targets.extend(["layout", "grading", "drainage"])
            fix_summary["autofix_actions"].append("layout_validation_retry")
        changed_targets.extend(["grading", "drainage", "storm_pipes", "utility_network", "earthwork", "qa"])
        fix_summary["autofix_actions"].append("planner_pass_extension")

    changed_targets = dedupe_keep_order(changed_targets)
    ctx.changed_targets.extend(changed_targets)
    fix_summary["changed_targets"] = deepcopy(changed_targets)
    fix_summary["effective_change"] = bool(changed_targets)
    fix_summary["last_fix_attempt"] = {
        "target_count": len(changed_targets),
        "primary_target": safe_str(changed_targets[0]) if changed_targets else "",
        "autofix_actions": deepcopy(fix_summary["autofix_actions"]),
    }
    manager.project.meta["fix_summary"] = deepcopy(fix_summary)
    if changed_targets:
        for target in changed_targets:
            manager.invalidate_from(target, include_source=True)
        ctx.add_stage(
            "fix",
            True,
            "Applied deterministic planner fix pass.",
            changed_targets=deepcopy(changed_targets),
            fix_summary=deepcopy(fix_summary),
        )
    else:
        ctx.add_stage("fix", False, "Fix pass attempted no effective change.", fix_summary=deepcopy(fix_summary))
