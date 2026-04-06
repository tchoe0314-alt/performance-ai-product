from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional, Sequence

from .common import safe_dict, safe_int, safe_list, safe_str


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


def snapshot_coordination_state(project: Any, manager: Any) -> Dict[str, Any]:
    drainage = safe_dict(manager.latest_outputs.get("drainage", project.meta.get("drainage_canonical", {})))
    grading = safe_dict(project.meta.get("grading_summary", manager.latest_outputs.get("grading", {})))
    return {
        "storm": deepcopy(safe_dict(manager.latest_outputs.get("storm_pipe_summary", project.meta.get("storm_pipe_summary", {})))),
        "sanitary": deepcopy(safe_dict(manager.latest_outputs.get("sanitary", project.meta.get("sanitary_summary", {})))),
        "utilities": deepcopy(safe_dict(manager.latest_outputs.get("utilities", project.meta.get("utility_summary", {})))),
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
