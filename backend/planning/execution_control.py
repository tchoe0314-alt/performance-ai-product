from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .common import canonical_stage_output, dedupe_keep_order, safe_dict, safe_float, safe_int, safe_list, safe_str
from .runtime import PLANNER_STAGE_ORDER, PlannerExecutionContext, PlannerStageResult, declared_stage_dependencies


def latest_stage_result(ctx: PlannerExecutionContext, stage_name: str) -> Optional[PlannerStageResult]:
    for stage in reversed(ctx.stage_results):
        if safe_str(stage.stage_name) == safe_str(stage_name):
            return stage
    return None


def _stage_ran_successfully_this_pass(ctx: PlannerExecutionContext, stage_name: str) -> bool:
    result = latest_stage_result(ctx, stage_name)
    if result is None or not bool(result.success):
        return False
    meta = safe_dict(result.meta)
    return safe_int(meta.get("pass_index"), -1) == safe_int(ctx.pass_index, -2) and safe_str(meta.get("action")).lower() == "run"


def stage_dirty_reasons(ctx: PlannerExecutionContext, stage_name: str) -> List[str]:
    manager = ctx.manager
    reasons: List[str] = []
    dirty_map = getattr(manager, "system_dirty_state", {})
    state_row = safe_dict(dirty_map.get(stage_name))
    reasons.extend([safe_str(item) for item in safe_list(state_row.get("reasons")) if safe_str(item)])
    for dep_name in declared_stage_dependencies(stage_name):
        dep_row = safe_dict(dirty_map.get(dep_name))
        if safe_str(dep_row.get("state")).lower() == "dirty":
            reasons.append(f"Dependency '{dep_name}' is dirty.")
        elif _stage_ran_successfully_this_pass(ctx, dep_name):
            reasons.append(f"Dependency '{dep_name}' reran this pass.")
    return dedupe_keep_order([item for item in reasons if item])


def stage_should_run(ctx: PlannerExecutionContext, stage_name: str, *, force_first_pass: bool = True) -> bool:
    if force_first_pass and ctx.pass_index <= 1:
        return True
    if latest_stage_result(ctx, stage_name) is None:
        return True
    manager = ctx.manager
    if hasattr(manager, "is_system_dirty") and manager.is_system_dirty(stage_name):
        return True
    return bool(stage_dirty_reasons(ctx, stage_name))


def mark_stage_skipped_clean(ctx: PlannerExecutionContext, stage_name: str) -> None:
    reasons = stage_dirty_reasons(ctx, stage_name)
    prior = latest_stage_result(ctx, stage_name)
    preserved_completeness = ""
    if prior is not None:
        preserved_completeness = safe_str(safe_dict(prior.meta).get("completeness")).strip().lower()
        if preserved_completeness not in {"complete", "assumed"} and bool(safe_dict(prior.meta).get("resumed_from_checkpoint")) and bool(prior.success):
            preserved_completeness = "complete"
    ctx.add_stage(
        stage_name,
        True,
        "Stage skipped because canonical state is already clean.",
        rerun_skipped=True,
        completeness=preserved_completeness or "partial",
        dirty_reasons=deepcopy(reasons),
        declared_dependencies=declared_stage_dependencies(stage_name),
    )
    ctx.rerun_history.append(
        {
            "pass_index": ctx.pass_index,
            "stage_name": stage_name,
            "action": "skipped_clean",
            "dirty_reasons": deepcopy(reasons),
            "declared_dependencies": declared_stage_dependencies(stage_name),
        }
    )


def canonical_state_snapshot(project: Any, manager: Any) -> Dict[str, Any]:
    drainage = safe_dict(canonical_stage_output(project, manager, "drainage"))
    storm = safe_dict(canonical_stage_output(project, manager, "storm_pipes"))
    sanitary = safe_dict(canonical_stage_output(project, manager, "sanitary"))
    utilities = safe_dict(canonical_stage_output(project, manager, "utilities"))
    grading = safe_dict(canonical_stage_output(project, manager, "grading"))
    expanded_actions = safe_list(safe_dict(project.meta.get("_expanded_plan")).get("actions"))
    return {
        "project_object_count": len(getattr(project, "objects", {}) or {}),
        "project_graph_count": len(getattr(project, "graphs", {}) or {}),
        "drawing_entity_count": len(getattr(project, "drawing_entities", []) or []),
        "expanded_action_count": len(expanded_actions),
        "drainage_structure_count": len(safe_list(drainage.get("structures"))),
        "drainage_basin_count": len(safe_list(drainage.get("basins"))),
        "drainage_pipe_run_count": len(safe_list(drainage.get("pipe_runs"))),
        "storm_segment_count": len(safe_list(storm.get("segments"))),
        "storm_total_length_ft": round(safe_float(storm.get("total_length_ft"), 0.0), 3),
        "sanitary_segment_count": len(safe_list(sanitary.get("segments"))),
        "sanitary_manhole_count": len(safe_list(sanitary.get("manholes"))),
        "sanitary_total_length_ft": round(safe_float(sanitary.get("total_length_ft"), 0.0), 3),
        "utility_segment_count": len(safe_list(safe_dict(utilities.get("conflict_hooks")).get("utility_segments"))),
        "utility_structure_count": len(safe_list(utilities.get("structures"))),
        "utility_total_length_ft": round(safe_float(utilities.get("total_length_ft"), 0.0), 3),
        "profile_count": len(safe_list(project.meta.get("profiles"))),
        "cross_section_count": len(safe_list(project.meta.get("cross_sections"))),
        "grading_adjustment_count": len(safe_list(grading.get("local_adjustments"))),
        "has_proposed_surface": bool(grading.get("proposed_surface")),
        "review_issue_count": len(getattr(project, "review_issues", []) or []),
    }


def canonical_state_diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
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


def record_stage_audit(
    ctx: PlannerExecutionContext,
    stage_name: str,
    *,
    pass_index: int,
    action: str,
    dirty_reasons: Sequence[str],
    before_state: Dict[str, Any],
) -> None:
    after_state = canonical_state_snapshot(ctx.manager.project, ctx.manager)
    diff = canonical_state_diff(before_state, after_state)
    stage_meta = {
        "pass_index": pass_index,
        "stage_name": stage_name,
        "action": action,
        "declared_dependencies": declared_stage_dependencies(stage_name),
        "dirty_reasons": list(dirty_reasons),
        "canonical_snapshot_before": deepcopy(before_state),
        "canonical_snapshot_after": deepcopy(after_state),
        "canonical_diff": deepcopy(diff),
    }
    for result in reversed(ctx.stage_results):
        if safe_str(result.stage_name) == stage_name:
            result.meta.update(deepcopy(stage_meta))
            break
    ctx.rerun_history.append(deepcopy(stage_meta))
    manager_meta = ctx.manager.state.meta.setdefault("stage_canonical_diffs", [])
    manager_meta.append(deepcopy(stage_meta))


def stage_sort_key(stage_name: str) -> Tuple[int, str]:
    if stage_name in PLANNER_STAGE_ORDER:
        return (PLANNER_STAGE_ORDER.index(stage_name), stage_name)
    if stage_name.endswith("_gate"):
        base = stage_name.replace("_gate", "")
        if base in PLANNER_STAGE_ORDER:
            return (PLANNER_STAGE_ORDER.index(base), stage_name)
    if stage_name == "coordination":
        return (len(PLANNER_STAGE_ORDER) + 1, stage_name)
    if stage_name == "fix":
        return (len(PLANNER_STAGE_ORDER) + 2, stage_name)
    return (len(PLANNER_STAGE_ORDER) + 10, stage_name)


def stage_completeness_label(stage_name: str, success: bool, message: str, meta: Dict[str, Any]) -> str:
    explicit = safe_str(meta.get("completeness")).strip().lower()
    if explicit in {"complete", "partial", "failed", "assumed"}:
        return explicit
    if bool(meta.get("fallback_used")) or bool(meta.get("assumed")):
        return "assumed"
    lowered = safe_str(message).strip().lower()
    if not success:
        return "failed"
    if "skipped" in lowered:
        return "partial"
    return "complete"
