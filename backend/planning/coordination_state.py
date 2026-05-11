from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional, Sequence

from .common import canonical_stage_output, safe_dict, safe_int, safe_list, safe_str


def new_coordination_metrics() -> Dict[str, Any]:
    return {
        "candidate_counts": {
            "cluster_orders_total": 0,
            "cluster_orders_kept": 0,
            "group_plans_total": 0,
            "group_plans_kept": 0,
            "geometry_candidates_generated": 0,
            "geometry_candidates_evaluated": 0,
            "geometry_candidates_pruned": 0,
        },
        "prune_reasons": {},
        "structure_insertion": {
            "analysis_cache_hits": 0,
            "analysis_cache_misses": 0,
            "rule_calls": 0,
            "attempt_points": 0,
            "successful_insertions": 0,
        },
        "rollbacks": 0,
        "timings_ms": {
            "apply_conflict_resolution": 0.0,
            "solve_conflict_cluster": 0.0,
            "solve_conflict_cluster_group": 0.0,
            "conflict_resolution_stage": 0.0,
        },
    }


def coordination_metric_inc(metrics: Optional[Dict[str, Any]], path: Sequence[str], amount: float = 1.0) -> None:
    if not isinstance(metrics, dict):
        return
    target: Any = metrics
    for key in path[:-1]:
        rec = safe_dict(target.get(key))
        target[key] = rec
        target = rec
    leaf = safe_str(path[-1])
    current = target.get(leaf, 0.0)
    target[leaf] = amount if not isinstance(current, (int, float)) else current + amount


def coordination_record_prune(metrics: Optional[Dict[str, Any]], reason: str, amount: int = 1) -> None:
    if not isinstance(metrics, dict):
        return
    coordination_metric_inc(metrics, ["candidate_counts", "geometry_candidates_pruned"], amount)
    prune_reasons = safe_dict(metrics.get("prune_reasons"))
    prune_reasons[reason] = safe_int(prune_reasons.get(reason), 0) + amount
    metrics["prune_reasons"] = prune_reasons


def full_coordination_state_snapshot(project: Any, manager: Any) -> Dict[str, Any]:
    """Capture full manager/project state for candidate isolation.

    The narrow coordination snapshot is useful for engineering deltas, but
    candidate rollback must include project.meta, latest_outputs, metrics,
    conflicts, dirty state, and audit state.
    """

    if hasattr(manager, "_export_state_bundle"):
        state = manager._export_state_bundle(  # noqa: SLF001 - internal snapshot is intentional here.
            include_snapshots=True,
            include_variants=True,
            include_audit_log=True,
        )
    elif hasattr(manager, "to_dict"):
        state = manager.to_dict()
    else:
        state = {
            "project": project.to_dict() if hasattr(project, "to_dict") else deepcopy(getattr(project, "__dict__", {})),
            "state": deepcopy(getattr(manager, "state", {})),
        }
    return {
        "state": deepcopy(state),
        "transaction_snapshots": deepcopy(getattr(manager, "_transaction_snapshots", {})),
    }


def restore_full_coordination_state(project: Any, manager: Any, snapshot: Dict[str, Any]) -> None:
    payload = deepcopy(safe_dict(snapshot).get("state"))
    if not payload:
        return
    from core.project_manager import ProjectManager

    restored = ProjectManager.from_dict(payload, assume_isolated=True)
    if hasattr(project, "__dict__") and hasattr(restored.project, "__dict__"):
        project.__dict__.clear()
        project.__dict__.update(deepcopy(restored.project.__dict__))
        manager.project = project
    else:
        manager.project = restored.project
    manager.state = restored.state
    if hasattr(manager, "_transaction_snapshots"):
        manager._transaction_snapshots = deepcopy(safe_dict(snapshot).get("transaction_snapshots"))


def snapshot_coordination_state(project: Any, manager: Any) -> Dict[str, Any]:
    drainage = safe_dict(canonical_stage_output(project, manager, "drainage"))
    grading = safe_dict(canonical_stage_output(project, manager, "grading"))
    return {
        "storm": deepcopy(safe_dict(canonical_stage_output(project, manager, "storm_pipes"))),
        "sanitary": deepcopy(safe_dict(canonical_stage_output(project, manager, "sanitary"))),
        "utilities": deepcopy(safe_dict(canonical_stage_output(project, manager, "utilities"))),
        "grading": deepcopy(grading),
        "drainage_mutable": {
            "structures": deepcopy(safe_list(drainage.get("structures"))),
            "stats": deepcopy(safe_dict(drainage.get("stats"))),
            "export_validation": deepcopy(safe_dict(drainage.get("export_validation"))),
        },
        "grading_mutable": {
            "local_adjustments": deepcopy(safe_list(grading.get("local_adjustments"))),
        },
    }


def restore_coordination_state(project: Any, manager: Any, snapshot: Dict[str, Any]) -> None:
    manager.latest_outputs["storm_pipe_summary"] = deepcopy(safe_dict(snapshot.get("storm")))
    manager.latest_outputs["sanitary"] = deepcopy(safe_dict(snapshot.get("sanitary")))
    manager.latest_outputs["utilities"] = deepcopy(safe_dict(snapshot.get("utilities")))
    project.meta["storm_pipe_summary"] = deepcopy(safe_dict(snapshot.get("storm")))
    project.meta["sanitary_summary"] = deepcopy(safe_dict(snapshot.get("sanitary")))
    project.meta["utility_summary"] = deepcopy(safe_dict(snapshot.get("utilities")))
    drainage = safe_dict(manager.latest_outputs.get("drainage", project.meta.get("drainage_canonical", {})))
    drainage_mutable = safe_dict(snapshot.get("drainage_mutable"))
    drainage["structures"] = deepcopy(safe_list(drainage_mutable.get("structures")))
    drainage["stats"] = deepcopy(safe_dict(drainage_mutable.get("stats")))
    drainage["export_validation"] = deepcopy(safe_dict(drainage_mutable.get("export_validation")))
    manager.latest_outputs["drainage"] = drainage
    project.meta["drainage_canonical"] = drainage
    grading = safe_dict(snapshot.get("grading"))
    if not grading:
        grading = safe_dict(project.meta.get("grading_summary", manager.latest_outputs.get("grading", {})))
        grading_mutable = safe_dict(snapshot.get("grading_mutable"))
        grading["local_adjustments"] = deepcopy(safe_list(grading_mutable.get("local_adjustments")))
    manager.latest_outputs["grading"] = grading
    project.meta["grading_summary"] = grading


def sync_drainage_mutable_state(
    project: Any,
    manager: Any,
    *,
    structures: Optional[Sequence[Dict[str, Any]]] = None,
    stats: Optional[Dict[str, Any]] = None,
    export_validation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    base = safe_dict(manager.latest_outputs.get("drainage", project.meta.get("drainage_canonical", {})))
    project_drainage = safe_dict(project.meta.get("drainage_canonical", {}))
    if structures is not None:
        structures_payload = [safe_dict(item) for item in structures]
        base["structures"] = structures_payload
        project_drainage["structures"] = list(structures_payload)
    if stats is not None:
        stats_payload = safe_dict(stats)
        base["stats"] = stats_payload
        project_drainage["stats"] = dict(stats_payload)
    if export_validation is not None:
        validation_payload = safe_dict(export_validation)
        base["export_validation"] = validation_payload
        project_drainage["export_validation"] = dict(validation_payload)
    manager.latest_outputs["drainage"] = base
    project.meta["drainage_canonical"] = project_drainage
    return base


def grading_local_adjustments(project: Any) -> list[Dict[str, Any]]:
    grading = safe_dict(project.meta.get("grading_summary"))
    return safe_list(grading.get("local_adjustments"))


def add_grading_adjustment(project: Any, note: Dict[str, Any]) -> None:
    grading = safe_dict(project.meta.get("grading_summary"))
    adjustments = safe_list(grading.get("local_adjustments"))
    adjustments.append(deepcopy(note))
    grading["local_adjustments"] = adjustments
    project.meta["grading_summary"] = grading
