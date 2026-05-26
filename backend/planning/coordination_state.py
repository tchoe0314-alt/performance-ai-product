from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional, Sequence

from .common import safe_dict, safe_int, safe_list, safe_str

_COORDINATION_LATEST_OUTPUT_KEYS = {
    "storm_pipe_summary",
    "sanitary",
    "utilities",
    "grading",
}

_COORDINATION_PROJECT_META_KEYS = {
    "preferred_corridors",
    "system_dirty_state",
    "storm_pipe_summary",
    "storm_pipe_segments",
    "sanitary_summary",
    "utility_summary",
    "grading_summary",
    "coordination_summary",
}


def _canonical_stage_ref(project: Any, manager: Any, stage: str) -> Any:
    meta = safe_dict(getattr(project, "meta", {}))
    latest = safe_dict(getattr(manager, "latest_outputs", {}))
    mapping = {
        "grading": ("grading_summary", "grading"),
        "drainage": ("drainage_canonical", "drainage"),
        "storm_pipes": ("storm_pipe_summary", "storm_pipe_summary"),
        "sanitary": ("sanitary_summary", "sanitary"),
        "utilities": ("utility_summary", "utilities"),
    }
    meta_key, cache_key = mapping.get(stage, (stage, stage))
    if meta.get(meta_key) is not None:
        return meta.get(meta_key)
    return latest.get(cache_key)


def _bounded_copy(value: Any, *, max_depth: int = 4, max_items: int = 120) -> Any:
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
            if type(node).__module__.startswith("core.") or type(node).__module__.startswith("engines."):
                return repr(node)
            return clone({key: item for key, item in vars(node).items() if not str(key).startswith("_")}, depth + 1)
        return repr(node)

    return clone(value, 0)


def _restore_manager_meta_snapshot(meta_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    restored: Dict[str, Any] = {}
    for key, value in safe_dict(meta_snapshot).items():
        if key != "latest_outputs":
            restored[key] = _bounded_copy(value)
            continue
        latest: Dict[str, Any] = {}
        for latest_key, latest_value in safe_dict(value).items():
            latest[latest_key] = _copy_coordination_payload(latest_key, latest_value) if latest_key in _COORDINATION_LATEST_OUTPUT_KEYS else latest_value
        restored[key] = latest
    return restored


def _copy_segment_list(value: Any) -> list[Dict[str, Any]]:
    copied: list[Dict[str, Any]] = []
    for row in safe_list(value):
        rec = safe_dict(row)
        out: Dict[str, Any] = {}
        for key, item in rec.items():
            if key in {"path", "route_points", "points"}:
                out[key] = [
                    [float(pt[0]), float(pt[1])] if isinstance(pt, (list, tuple)) and len(pt) >= 2 else _bounded_copy(pt)
                    for pt in safe_list(item)
                ]
            elif isinstance(item, (dict, list, tuple, set)):
                out[key] = _bounded_copy(item)
            else:
                out[key] = item
        copied.append(out)
    return copied


def _copy_coordination_payload(key: str, value: Any) -> Any:
    if key in {"grading", "grading_summary"}:
        rec = dict(safe_dict(value))
        if "local_adjustments" in rec:
            rec["local_adjustments"] = _bounded_copy(safe_list(rec.get("local_adjustments")))
        return rec
    if key in {"drainage", "drainage_canonical", "drainage_summary"}:
        rec = dict(safe_dict(value))
        for field in ("structures", "stats", "export_validation", "issues", "coordination"):
            if field in rec:
                rec[field] = _bounded_copy(rec[field])
        return rec
    rec = dict(safe_dict(value))
    for field in ("segments", "pipes", "structures", "manholes", "nodes"):
        if field in rec:
            rec[field] = _copy_segment_list(rec.get(field))
    if "conflict_hooks" in rec:
        hooks = dict(safe_dict(rec.get("conflict_hooks")))
        if "utility_segments" in hooks:
            hooks["utility_segments"] = _copy_segment_list(hooks.get("utility_segments"))
        if "storm_segments" in hooks:
            hooks["storm_segments"] = _copy_segment_list(hooks.get("storm_segments"))
        rec["conflict_hooks"] = hooks
    for field in ("graph_validation", "network_validation", "hydraulic_validation", "stats", "export_validation", "coordination"):
        if field in rec:
            rec[field] = _bounded_copy(rec.get(field))
    return rec


def _snapshot_project_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: _copy_coordination_payload(key, value)
        for key, value in safe_dict(meta).items()
        if key in _COORDINATION_PROJECT_META_KEYS
    }


def _restore_project_meta_snapshot(meta_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: _copy_coordination_payload(key, value)
        for key, value in safe_dict(meta_snapshot).items()
        if key in _COORDINATION_PROJECT_META_KEYS
    }


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

    # This is an in-process rollback guard, not a persisted interchange format.
    # Coordination candidates mutate canonical summaries in project.meta plus
    # manager state/latest_outputs. Avoid serializing the entire ProjectModel
    # because drawing/entity geometry can be very large during full planner runs.
    state = getattr(manager, "state", None)
    meta = safe_dict(getattr(state, "meta", {}))
    latest_outputs = safe_dict(meta.get("latest_outputs"))
    latest_outputs_snapshot = {
        key: _copy_coordination_payload(key, value) if key in _COORDINATION_LATEST_OUTPUT_KEYS else value
        for key, value in latest_outputs.items()
    }
    manager_meta_snapshot = {
        key: (latest_outputs_snapshot if key == "latest_outputs" else _bounded_copy(value))
        for key, value in meta.items()
    }
    return {
        "project_meta": _snapshot_project_meta(getattr(project, "meta", {})),
        "project_drawing_entities": list(getattr(project, "drawing_entities", []) or []),
        "project_review_issues": _bounded_copy(getattr(project, "review_issues", [])),
        "manager_state_parts": {
            "dependencies": dict(getattr(state, "dependencies", {}) or {}),
            "conflicts": dict(getattr(state, "conflicts", {}) or {}),
            "systems": dict(getattr(state, "systems", {}) or {}),
            "metrics": dict(getattr(state, "metrics", {}) or {}),
            "audit_log": list(getattr(state, "audit_log", []) or []),
            "meta": manager_meta_snapshot,
        },
        "transaction_snapshots": _bounded_copy(getattr(manager, "_transaction_snapshots", {})),
    }


def restore_full_coordination_state(project: Any, manager: Any, snapshot: Dict[str, Any]) -> None:
    if "manager_state_parts" in safe_dict(snapshot):
        if hasattr(project, "meta"):
            restored_meta = safe_dict(getattr(project, "meta", {}))
            for key in _COORDINATION_PROJECT_META_KEYS:
                restored_meta.pop(key, None)
            restored_meta.update(_restore_project_meta_snapshot(safe_dict(snapshot).get("project_meta")))
            project.meta = restored_meta
        if hasattr(project, "drawing_entities"):
            project.drawing_entities = list(snapshot.get("project_drawing_entities") or [])
        if hasattr(project, "review_issues"):
            project.review_issues = _bounded_copy(safe_list(snapshot.get("project_review_issues")))
        manager.project = project
        state_parts = safe_dict(snapshot.get("manager_state_parts"))
        manager.state.dependencies = dict(safe_dict(state_parts.get("dependencies")))
        manager.state.conflicts = dict(safe_dict(state_parts.get("conflicts")))
        manager.state.systems = dict(safe_dict(state_parts.get("systems")))
        manager.state.metrics = dict(safe_dict(state_parts.get("metrics")))
        manager.state.audit_log = list(safe_list(state_parts.get("audit_log")))
        manager.state.meta = _restore_manager_meta_snapshot(safe_dict(state_parts.get("meta")))
        if hasattr(manager, "_transaction_snapshots"):
            manager._transaction_snapshots = _bounded_copy(safe_dict(snapshot).get("transaction_snapshots"))
        return

    if "manager_state" in safe_dict(snapshot):
        if hasattr(project, "meta"):
            project.meta = deepcopy(safe_dict(snapshot).get("project_meta"))
        if hasattr(project, "drawing_entities"):
            project.drawing_entities = list(snapshot.get("project_drawing_entities") or [])
        if hasattr(project, "review_issues"):
            project.review_issues = deepcopy(safe_list(snapshot.get("project_review_issues")))
        manager.project = project
        manager.state = deepcopy(snapshot.get("manager_state"))
        if hasattr(manager, "_transaction_snapshots"):
            manager._transaction_snapshots = deepcopy(safe_dict(snapshot).get("transaction_snapshots"))
        return

    # Backward-compatible restore for older serialized snapshots.
    payload = safe_dict(snapshot).get("state")
    if not payload:
        return
    from core.project_manager import ProjectManager

    # Restore must never share nested dictionaries/lists with the stored
    # snapshot. Candidate attempts mutate manager.latest_outputs, project.meta,
    # metrics, and dirty state in place; sharing those objects would corrupt the
    # rollback point itself and let failed candidates leak into canonical state.
    restored = ProjectManager.from_dict(deepcopy(payload), assume_isolated=True)
    restored.state.snapshots = safe_dict(snapshot.get("snapshots"))
    restored.state.variants = safe_dict(snapshot.get("variants"))
    restored.state.audit_log = deepcopy(safe_list(snapshot.get("audit_log")))
    if hasattr(project, "__dict__") and hasattr(restored.project, "__dict__"):
        project.__dict__.clear()
        project.__dict__.update(restored.project.__dict__)
        manager.project = project
    else:
        manager.project = restored.project
    manager.state = restored.state
    if hasattr(manager, "_transaction_snapshots"):
        manager._transaction_snapshots = deepcopy(safe_dict(snapshot).get("transaction_snapshots"))


def snapshot_coordination_state(project: Any, manager: Any) -> Dict[str, Any]:
    drainage = safe_dict(_canonical_stage_ref(project, manager, "drainage"))
    grading = safe_dict(_canonical_stage_ref(project, manager, "grading"))
    return {
        "storm": _copy_coordination_payload("storm_pipe_summary", _canonical_stage_ref(project, manager, "storm_pipes")),
        "sanitary": _copy_coordination_payload("sanitary", _canonical_stage_ref(project, manager, "sanitary")),
        "utilities": _copy_coordination_payload("utilities", _canonical_stage_ref(project, manager, "utilities")),
        "grading": _copy_coordination_payload("grading", grading),
        "drainage_mutable": {
            "structures": _bounded_copy(safe_list(drainage.get("structures")), max_depth=3, max_items=80),
            "stats": _bounded_copy(safe_dict(drainage.get("stats")), max_depth=2, max_items=40),
            "export_validation": _bounded_copy(safe_dict(drainage.get("export_validation")), max_depth=2, max_items=40),
        },
        "grading_mutable": {
            "local_adjustments": _bounded_copy(safe_list(grading.get("local_adjustments")), max_depth=3, max_items=80),
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
