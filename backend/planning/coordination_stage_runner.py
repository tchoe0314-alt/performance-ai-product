from __future__ import annotations

from copy import deepcopy
from time import perf_counter
from typing import Any, Callable, Dict, List, Sequence, Tuple

from core.config import PIPE_INTENSITY_IN_HR, PIPE_RUNOFF_C
from core.project_manager import ConflictRecord, ConflictSeverity

from .common import safe_dict, safe_float, safe_int, safe_list, safe_str, lower_text
from .runtime import PlannerExecutionContext


def run_conflict_resolution_stage(
    ctx: PlannerExecutionContext,
    hydrology: Dict[str, Any],
    *,
    manual_mode_enabled: Callable[[Dict[str, Any]], bool],
    new_coordination_metrics: Callable[[], Dict[str, Any]],
    detect_coordination_conflicts: Callable[..., List[Dict[str, Any]]],
    conflict_priority_key: Callable[[Dict[str, Any]], Tuple[int, int, str]],
    group_conflict_clusters: Callable[..., List[Dict[str, Any]]],
    group_cluster_groups: Callable[[Sequence[Dict[str, Any]]], List[Dict[str, Any]]],
    snapshot_coordination_state: Callable[..., Dict[str, Any]],
    full_coordination_state_snapshot: Callable[..., Dict[str, Any]],
    cluster_group_remaining_conflicts: Callable[..., List[Dict[str, Any]]],
    solve_conflict_cluster_group: Callable[..., Dict[str, Any]],
    refresh_conflict_resolved_state: Callable[..., None],
    coordination_metric_inc: Callable[..., None],
    restore_coordination_state: Callable[..., None],
    restore_full_coordination_state: Callable[..., None],
    conflict_cluster_id: Callable[[Dict[str, Any]], str],
    post_reroute_validations: Callable[..., Dict[str, Any]],
    count_conflicts_by_type: Callable[[Sequence[Dict[str, Any]]], Dict[str, int]],
    grading_local_adjustments: Callable[[Any], List[Dict[str, Any]]],
) -> None:
    stage_started = perf_counter()
    manager = ctx.manager
    project = manager.project
    assisted_mode = not manual_mode_enabled(ctx.parsed)
    max_iterations = 3
    coordination_metrics = new_coordination_metrics()
    structure_analysis_cache: Dict[Tuple[str, str, Tuple[Tuple[float, float], ...]], Dict[str, Any]] = {}
    previous_ids = safe_list(safe_dict(manager.latest_outputs.get("coordination", {})).get("manager_conflict_ids"))
    for conflict_id in previous_ids:
        manager.resolve_conflict(safe_str(conflict_id), resolution_note="Superseded by new coordination pass.")

    before = sorted(detect_coordination_conflicts(project, manager), key=conflict_priority_key)
    detected = deepcopy(before)
    resolved: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []
    assumptions: List[Dict[str, Any]] = []
    resolution_history: List[Dict[str, Any]] = []
    changed_systems: set[str] = set()
    best_iteration = 0
    best_state = snapshot_coordination_state(project, manager)
    best_full_state = full_coordination_state_snapshot(project, manager)
    best_unresolved = len(before)
    iterations_used = 0
    unresolved_clusters: List[Dict[str, Any]] = []
    unresolved_report_map: Dict[str, Dict[str, Any]] = {}

    for iteration_index in range(1, max_iterations + 1):
        iterations_used = iteration_index
        current = sorted(detect_coordination_conflicts(project, manager), key=conflict_priority_key)
        if not current:
            unresolved = []
            break
        clusters = group_conflict_clusters(current, project)
        cluster_groups = group_cluster_groups(clusters)
        changed = False
        unresolved = []
        for cluster_group in cluster_groups:
            snapshot = snapshot_coordination_state(project, manager)
            full_snapshot = full_coordination_state_snapshot(project, manager)
            pre_all = detect_coordination_conflicts(project, manager)
            pre_related = cluster_group_remaining_conflicts(pre_all, cluster_group)
            resolution = solve_conflict_cluster_group(
                project,
                manager,
                cluster_group,
                assisted_mode=assisted_mode,
                metrics=coordination_metrics,
                structure_analysis_cache=structure_analysis_cache,
            )
            if resolution.get("success"):
                refresh_conflict_resolved_state(project, manager, safe_list(resolution.get("changed_systems")))
                post_all = detect_coordination_conflicts(project, manager)
                post_related = cluster_group_remaining_conflicts(post_all, cluster_group)
                improved = len(post_related) < len(pre_related) or len(post_all) < len(pre_all)
                if improved:
                    changed = True
                    resolved.append(
                        {
                            "cluster_id": safe_str(cluster_group.get("cluster_group_id")),
                            "status": "resolved",
                            "systems": deepcopy(safe_list(cluster_group.get("systems"))),
                            "objects": deepcopy(safe_list(cluster_group.get("objects"))),
                            "conflicts": deepcopy(safe_list(cluster_group.get("conflicts"))),
                            "resolution": deepcopy(resolution),
                        }
                    )
                    changed_systems.update(safe_str(item) for item in safe_list(resolution.get("changed_systems")) if safe_str(item))
                    resolution_history.append(
                        {
                            "iteration": iteration_index,
                            "cluster_id": safe_str(cluster_group.get("cluster_group_id")),
                            "cluster_conflict_types": [safe_str(item.get("conflict_type")) for item in safe_list(cluster_group.get("conflicts"))],
                            "involved_objects": deepcopy(safe_list(cluster_group.get("objects"))),
                            "strategy": safe_str(resolution.get("selected_order")),
                            "group_plan": safe_str(resolution.get("group_plan")),
                            "selected_group_strategy": safe_str(resolution.get("selected_group_strategy")),
                            "selected_candidate_mode": safe_str(resolution.get("selected_candidate_mode")),
                            "selection_reason": safe_str(resolution.get("selection_reason")),
                            "notes": deepcopy([safe_str(item.get("strategy")) for item in safe_list(resolution.get("resolution_rows"))]),
                            "before_related_count": len(pre_related),
                            "after_related_count": len(post_related),
                            "before_total_count": len(pre_all),
                            "after_total_count": len(post_all),
                            "changed_systems": deepcopy(safe_list(resolution.get("changed_systems"))),
                            "candidate_count": safe_int(resolution.get("candidate_count"), 0),
                            "constructability_score": safe_float(resolution.get("constructability_score"), 0.0),
                            "engineering_deltas": deepcopy(safe_dict(resolution.get("engineering_deltas"))),
                            "cluster_group_summary": deepcopy(safe_dict(resolution.get("cluster_group_summary"))),
                        }
                    )
                else:
                    coordination_metric_inc(coordination_metrics, ["rollbacks"])
                    restore_full_coordination_state(project, manager, full_snapshot)
                    if assisted_mode:
                        resolution["assumed"] = True
                        assumptions.append(
                            {
                                "cluster_id": safe_str(cluster_group.get("cluster_group_id")),
                                "status": "resolved_with_assumptions",
                                "resolution": deepcopy(resolution),
                            }
                        )
                    for conflict in safe_list(cluster_group.get("conflicts")):
                        unresolved.append(
                            {
                                **deepcopy(safe_dict(conflict)),
                                "status": "unresolved",
                                "cluster_id": safe_str(cluster_group.get("cluster_group_id")),
                                "systems_involved": deepcopy(safe_list(cluster_group.get("systems"))),
                                "blocking_rules": {
                                    "required_horizontal_clearance_ft": safe_dict(conflict).get("required_horizontal_clearance_ft"),
                                    "required_vertical_clearance_ft": safe_dict(conflict).get("required_vertical_clearance_ft"),
                                    "required_clearance_ft": safe_dict(conflict).get("required_clearance_ft"),
                                    "required_slope_ft_ft": safe_dict(conflict).get("required_slope_ft_ft"),
                                    "preferred_lower_system": safe_dict(conflict).get("preferred_lower_system"),
                                    "preferred_crossing_angle_deg": safe_dict(conflict).get("preferred_crossing_angle_deg"),
                                },
                                "best_near_valid_candidate": deepcopy(safe_dict(resolution.get("best_near_valid_candidate"))),
                                "resolution_attempted": safe_str(resolution.get("selected_order")),
                                "resolution_reason": safe_str(resolution.get("failure_reason"), "No candidate improved canonical state without creating equal or worse conflicts."),
                            }
                        )
                    unresolved_report_map[safe_str(cluster_group.get("cluster_group_id"))] = {
                        "best_near_valid_candidate": deepcopy(safe_dict(resolution.get("best_near_valid_candidate"))),
                        "resolution_reason": safe_str(resolution.get("failure_reason")),
                        "candidate_summaries": deepcopy(safe_list(resolution.get("candidate_summaries"))),
                        "failure_tags": deepcopy(safe_list(resolution.get("failure_tags"))),
                        "selected_group_strategy": safe_str(resolution.get("selected_group_strategy") or resolution.get("crossing_strategy")),
                        "geometry_strategy": safe_str(safe_dict(resolution.get("cluster_group_summary")).get("geometry_strategy")),
                    }
                    for conflict in safe_list(cluster_group.get("conflicts")):
                        unresolved_report_map[conflict_cluster_id(safe_dict(conflict))] = deepcopy(unresolved_report_map[safe_str(cluster_group.get("cluster_group_id"))])
            else:
                if resolution.get("assumed"):
                    assumptions.append(
                        {
                            "cluster_id": safe_str(cluster_group.get("cluster_group_id")),
                            "status": "resolved_with_assumptions",
                            "resolution": deepcopy(resolution),
                        }
                    )
                for conflict in safe_list(cluster_group.get("conflicts")):
                    unresolved.append(
                        {
                            **deepcopy(safe_dict(conflict)),
                            "status": "unresolved",
                            "cluster_id": safe_str(cluster_group.get("cluster_group_id")),
                            "systems_involved": deepcopy(safe_list(cluster_group.get("systems"))),
                            "blocking_rules": {
                                "required_horizontal_clearance_ft": safe_dict(conflict).get("required_horizontal_clearance_ft"),
                                "required_vertical_clearance_ft": safe_dict(conflict).get("required_vertical_clearance_ft"),
                                "required_clearance_ft": safe_dict(conflict).get("required_clearance_ft"),
                                "required_slope_ft_ft": safe_dict(conflict).get("required_slope_ft_ft"),
                                "preferred_lower_system": safe_dict(conflict).get("preferred_lower_system"),
                                "preferred_crossing_angle_deg": safe_dict(conflict).get("preferred_crossing_angle_deg"),
                            },
                            "best_near_valid_candidate": deepcopy(safe_dict(resolution.get("best_near_valid_candidate"))),
                            "resolution_attempted": safe_str(resolution.get("selected_order")),
                            "resolution_reason": safe_str(resolution.get("failure_reason"), "No safe cluster candidate was available for this conflict group."),
                        }
                    )
                unresolved_report_map[safe_str(cluster_group.get("cluster_group_id"))] = {
                    "best_near_valid_candidate": deepcopy(safe_dict(resolution.get("best_near_valid_candidate"))),
                    "resolution_reason": safe_str(resolution.get("failure_reason")),
                    "candidate_summaries": deepcopy(safe_list(resolution.get("candidate_summaries"))),
                    "failure_tags": deepcopy(safe_list(resolution.get("failure_tags"))),
                    "selected_group_strategy": safe_str(resolution.get("selected_group_strategy") or resolution.get("crossing_strategy")),
                    "geometry_strategy": safe_str(safe_dict(resolution.get("cluster_group_summary")).get("geometry_strategy")),
                }
                for conflict in safe_list(cluster_group.get("conflicts")):
                    unresolved_report_map[conflict_cluster_id(safe_dict(conflict))] = deepcopy(unresolved_report_map[safe_str(cluster_group.get("cluster_group_id"))])
        if changed:
            refresh_conflict_resolved_state(project, manager, sorted(changed_systems))
            next_conflicts = sorted(detect_coordination_conflicts(project, manager), key=conflict_priority_key)
            if len(next_conflicts) < best_unresolved:
                best_state = snapshot_coordination_state(project, manager)
                best_full_state = full_coordination_state_snapshot(project, manager)
                best_unresolved = len(next_conflicts)
                best_iteration = iteration_index
            unresolved = next_conflicts
            if not next_conflicts:
                break
        else:
            break

    if unresolved and best_state:
        restore_full_coordination_state(project, manager, best_full_state)
        refresh_conflict_resolved_state(project, manager, None)
        unresolved = sorted(detect_coordination_conflicts(project, manager), key=conflict_priority_key)

    for conflict in unresolved:
        cluster_id = safe_str(conflict.get("cluster_id")) or conflict_cluster_id(conflict)
        prior_report = safe_dict(unresolved_report_map.get(cluster_id))
        unresolved_clusters.append(
            {
                "cluster_id": cluster_id,
                "systems_involved": deepcopy(safe_list(conflict.get("systems"))),
                "remaining_conflict_type": safe_str(conflict.get("conflict_type")),
                "blocking_rules": {
                    "required_horizontal_clearance_ft": conflict.get("required_horizontal_clearance_ft"),
                    "required_vertical_clearance_ft": conflict.get("required_vertical_clearance_ft"),
                    "required_clearance_ft": conflict.get("required_clearance_ft"),
                    "required_slope_ft_ft": conflict.get("required_slope_ft_ft"),
                    "preferred_lower_system": conflict.get("preferred_lower_system"),
                    "preferred_crossing_angle_deg": conflict.get("preferred_crossing_angle_deg"),
                },
                "best_near_valid_candidate": deepcopy(safe_dict(prior_report.get("best_near_valid_candidate") or conflict.get("best_near_valid_candidate"))),
                "candidate_family_failures": deepcopy(safe_list(prior_report.get("candidate_summaries"))),
                "failure_tags": deepcopy(safe_list(prior_report.get("failure_tags"))),
                "attempted_group_strategy": safe_str(prior_report.get("selected_group_strategy")),
                "attempted_geometry_strategy": safe_str(prior_report.get("geometry_strategy")),
                "exact_reason": safe_str(prior_report.get("resolution_reason"), safe_str(conflict.get("resolution_reason"), "No valid candidate satisfied this conflict cluster.")),
            }
        )

    manager_conflict_ids: List[str] = []
    for conflict in unresolved:
        manager_conflict_ids.append(
            manager.add_conflict(
                ConflictRecord(
                    code=f"COORD_{safe_str(conflict.get('conflict_type'), 'CONFLICT').upper()}",
                    message=f"Unresolved coordination conflict: {safe_str(conflict.get('conflict_type'))}",
                    severity=ConflictSeverity.ERROR if lower_text(conflict.get("severity")) == "error" else ConflictSeverity.WARNING,
                    category="coordination",
                    context=deepcopy(conflict),
                )
            )
        )

    changed_systems_list = sorted(changed_systems)
    final_validations = post_reroute_validations(project, manager, changed_systems_list)
    coordination_metric_inc(coordination_metrics, ["timings_ms", "conflict_resolution_stage"], round((perf_counter() - stage_started) * 1000.0, 3))
    structure_metrics = safe_dict(coordination_metrics.get("structure_insertion"))
    cache_ops = safe_float(structure_metrics.get("analysis_cache_hits"), 0.0) + safe_float(structure_metrics.get("analysis_cache_misses"), 0.0)
    structure_metrics["analysis_cache_hit_rate"] = round(
        safe_float(structure_metrics.get("analysis_cache_hits"), 0.0) / cache_ops,
        3,
    ) if cache_ops > 0 else 0.0
    coordination_metrics["structure_insertion"] = structure_metrics
    coordination_summary = {
        "success": len(unresolved) == 0,
        "detected_conflicts": detected,
        "resolved_conflicts": resolved,
        "unresolved_conflicts": unresolved,
        "unresolved_clusters": unresolved_clusters,
        "assumption_resolutions": assumptions,
        "before_count": len(detected),
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "before_counts_by_type": count_conflicts_by_type(detected),
        "after_counts_by_type": count_conflicts_by_type(unresolved),
        "manager_conflict_ids": manager_conflict_ids,
        "iterations": iterations_used,
        "max_iterations": max_iterations,
        "best_iteration": best_iteration,
        "resolution_history": resolution_history,
        "changed_systems": changed_systems_list,
        "grading_adjustment_count": len(grading_local_adjustments(project)),
        "rollback_protected": True,
        "candidate_isolation": "snapshot_copy",
        "preferred_corridors": deepcopy(project.meta.get("preferred_corridors", {})),
        "post_resolution_validations": final_validations,
        "performance": coordination_metrics,
        "hydrology_reference": {
            "runoff_c": safe_float(hydrology.get("runoff_c"), PIPE_RUNOFF_C),
            "intensity_in_hr": safe_float(hydrology.get("intensity_in_hr"), PIPE_INTENSITY_IN_HR),
        },
    }
    manager.latest_outputs["coordination"] = deepcopy(coordination_summary)
    project.meta["coordination_summary"] = deepcopy(coordination_summary)
    for system_name in changed_systems_list:
        manager.invalidate_from(system_name, reason="Coordination resolution updated canonical system geometry.")
    if changed_systems_list:
        manager.mark_system_dirty("earthwork", reason="Conflict resolution changed upstream geometry.", source="coordination_resolution")
        manager.mark_system_dirty("sheets", reason="Conflict resolution changed exported geometry.", source="coordination_resolution")
        manager.mark_system_dirty("qa", reason="Conflict resolution changed final engineering state.", source="coordination_resolution")
    manager.set_metric("coordination_detected_conflict_count", len(detected), category="coordination")
    manager.set_metric("coordination_resolved_conflict_count", len(resolved), category="coordination")
    manager.set_metric("coordination_unresolved_conflict_count", len(unresolved), category="coordination")
    manager.set_metric("coordination_assumption_resolution_count", len(assumptions), category="coordination")
    manager.set_metric("coordination_grading_adjustment_count", len(grading_local_adjustments(project)), category="coordination")
    manager.mark_system_complete("coordination_resolution", "Coordination stage completed.")
    ctx.add_stage(
        "coordination_resolution",
        len(unresolved) == 0,
        "Coordination stage completed." if not unresolved else "Coordination stage completed with unresolved conflicts.",
        detected_conflict_count=len(detected),
        resolved_conflict_count=len(resolved),
        unresolved_conflict_count=len(unresolved),
    )
