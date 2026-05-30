from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, Iterable, List, Set

from .common import safe_dict, safe_list, safe_str
from .engine_contracts import downstream_closure
from .release_gates import construction_release_blockers_from_meta, final_plan_requires_construction_release
from .runtime import PLANNER_STAGE_DEPENDENCIES, PLANNER_STAGE_ORDER


ENGINE_TO_STAGE = {
    "geometry": "layout",
    "terrain_surface": "grading",
    "grading": "grading",
    "drainage": "drainage",
    "storm_pipe": "storm_pipes",
    "sanitary": "sanitary",
    "water": "utility_network",
    "utility_coordination": "coordination_resolution",
    "roadway_corridor": "layout",
    "structure": "grading",
    "earthwork": "earthwork",
    "hydrology": "drainage",
    "conflict_resolution": "coordination_resolution",
    "qa_validation": "qa",
    "quantity": "qa",
    "export_cad": "sheets",
    "profile_section": "sheets",
    "gis_existing_conditions": "layout",
    "ai_orchestration": "layout",
    "reactive_model": "qa",
}


def _stage_index(stage_name: str) -> int:
    try:
        return PLANNER_STAGE_ORDER.index(stage_name)
    except ValueError:
        return len(PLANNER_STAGE_ORDER)


def _target_stage(target: str) -> str:
    if target in PLANNER_STAGE_ORDER:
        return target
    return ENGINE_TO_STAGE.get(target, "")


def _downstream_stage_closure(stage_name: str) -> Set[str]:
    if stage_name not in PLANNER_STAGE_ORDER:
        return set()
    reverse: Dict[str, Set[str]] = {stage: set() for stage in PLANNER_STAGE_ORDER}
    for stage, deps in PLANNER_STAGE_DEPENDENCIES.items():
        for dep in deps:
            reverse.setdefault(dep, set()).add(stage)
    seen: Set[str] = set()
    pending = sorted(reverse.get(stage_name, set()), key=_stage_index)
    while pending:
        stage = pending.pop(0)
        if stage in seen:
            continue
        seen.add(stage)
        pending.extend(sorted(reverse.get(stage, set()) - seen, key=_stage_index))
    return seen


def build_reactive_update_report(
    *,
    changed_engine_ids: Iterable[str] = (),
    changed_stages: Iterable[str] = (),
    stage_results: Iterable[Any] = (),
    stale_outputs: Iterable[str] = (),
) -> Dict[str, Any]:
    changed_engine_set = {safe_str(item) for item in changed_engine_ids if safe_str(item)}
    changed_stage_set = {safe_str(item) for item in changed_stages if safe_str(item)}
    impacted_engines: Set[str] = set()
    impacted_stages: Set[str] = set(changed_stage_set)
    for engine_id in changed_engine_set:
        impacted_engines.update(downstream_closure(engine_id))
    for stage_name in changed_stage_set:
        impacted_stages.update(_downstream_stage_closure(stage_name))
    for engine_id in changed_engine_set | impacted_engines:
        stage = _target_stage(engine_id)
        if stage:
            impacted_stages.add(stage)
    ran_stages = {
        safe_str(safe_dict(getattr(item, "meta", item)).get("stage_name") or getattr(item, "stage_name", ""))
        for item in stage_results
    }
    stale = sorted({safe_str(item) for item in stale_outputs if safe_str(item)})
    return {
        "version": "reactive_model_v1",
        "changed_engine_ids": sorted(changed_engine_set),
        "changed_stages": sorted(changed_stage_set, key=_stage_index),
        "impacted_engine_ids": sorted(impacted_engines),
        "impacted_stages": sorted(impacted_stages, key=_stage_index),
        "partial_rerun_supported": True,
        "ran_stages": sorted((stage for stage in ran_stages if stage), key=_stage_index),
        "stale_outputs": stale,
        "export_blocked": bool(stale),
        "dirty_reasons": [
            {
                "source": engine_id,
                "downstream": sorted(downstream_closure(engine_id)),
                "reason": f"{engine_id} changed; downstream canonical outputs must rerun or be blocked.",
            }
            for engine_id in sorted(changed_engine_set)
        ],
    }


def reactive_report_from_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan.get("meta"))
    raw_changed_engine_ids = safe_list(meta.get("changed_engine_ids"))
    raw_changed_targets = safe_list(meta.get("changed_targets"))
    changed_engine_ids = [
        safe_str(item)
        for item in raw_changed_engine_ids
        if safe_str(item) and safe_str(item) not in PLANNER_STAGE_ORDER
    ]
    changed_stages = [
        safe_str(item)
        for item in raw_changed_targets
        if safe_str(item) in PLANNER_STAGE_ORDER
    ]
    changed_engine_ids.extend(
        safe_str(item)
        for item in raw_changed_targets
        if safe_str(item) and safe_str(item) not in PLANNER_STAGE_ORDER
    )
    stale = safe_list(meta.get("stale_outputs"))
    stages = safe_list(meta.get("stage_results"))
    return build_reactive_update_report(
        changed_engine_ids=changed_engine_ids,
        changed_stages=changed_stages,
        stage_results=stages,
        stale_outputs=stale,
    )


def _completed_stage_names(meta: Dict[str, Any]) -> Set[str]:
    completed: Set[str] = set()
    for item in safe_list(meta.get("stage_results")):
        row = safe_dict(item)
        stage_name = safe_str(row.get("stage_name"))
        if not stage_name:
            continue
        if bool(row.get("success")) and safe_str(row.get("completeness")).lower() == "complete":
            completed.add(stage_name)
            continue
        if bool(row.get("success")) and safe_str(row.get("action")).lower() == "run":
            completed.add(stage_name)

    completeness = safe_dict(meta.get("stage_completeness"))
    for source in (
        safe_dict(completeness.get("required_stage_status")),
        safe_dict(completeness.get("statuses")),
    ):
        for stage_name, status in source.items():
            if safe_str(status).lower() == "complete":
                completed.add(safe_str(stage_name))
    return completed


def _post_rerun_release_blockers(plan: Dict[str, Any], meta: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []

    def _add(value: Any) -> None:
        text = safe_str(value).strip()
        if text and text not in blockers:
            blockers.append(text)

    release_review = safe_dict(meta.get("release_review"))
    for item in safe_list(release_review.get("blocked_reasons")) + safe_list(release_review.get("blocked_exports")):
        _add(item)
    release_status = safe_str(release_review.get("release_status") or meta.get("release_status")).lower()
    release_ready = release_review.get("release_ready") if "release_ready" in release_review else meta.get("release_ready")
    if release_status == "blocked":
        _add("release_status_blocked")
    if release_ready is False:
        _add("final_plan_release_not_ready")

    for item in construction_release_blockers_from_meta(
        meta,
        requires_construction_release=final_plan_requires_construction_release(plan),
    ):
        _add(item)

    deliverables = safe_dict(meta.get("deliverables"))
    for failed_deliverable in safe_list(deliverables.get("failed")):
        failed_name = safe_str(failed_deliverable).strip()
        if failed_name:
            _add(f"failed_deliverable_{failed_name.lower().replace(' ', '_')}")

    manual_validation = safe_dict(meta.get("manual_validation"))
    for failure in [item for item in safe_list(manual_validation.get("failures")) if isinstance(item, dict)]:
        failure_key = safe_str(
            failure.get("code")
            or failure.get("rule")
            or failure.get("system")
            or failure.get("message")
            or "manual_validation_failure"
        ).strip()
        if not failure_key:
            failure_key = "manual_validation_failure"
        _add(f"manual_validation_{failure_key.lower().replace(' ', '_')}")

    export_audit = safe_dict(meta.get("export_audit"))
    if export_audit:
        if (
            export_audit.get("export_blocked") is True
            or export_audit.get("production_export_ready") is False
            or export_audit.get("ready") is False
        ):
            _add("export_audit_blocked")
        for item in safe_list(export_audit.get("blocked_reasons")):
            _add(item)
    return blockers


def execute_reactive_rerun(
    base_payload: Dict[str, Any],
    *,
    changed_engine_ids: Iterable[str] = (),
    changed_stages: Iterable[str] = (),
    edits: Dict[str, Any] = None,
    build_plan_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> Dict[str, Any]:
    payload = deepcopy(base_payload)
    if edits:
        payload.update(deepcopy(edits))
    report = build_reactive_update_report(changed_engine_ids=changed_engine_ids, changed_stages=changed_stages)
    meta = dict(safe_dict(payload.get("meta")))
    meta["changed_engine_ids"] = list(report.get("changed_engine_ids") or [])
    meta["changed_targets"] = list(report.get("impacted_stages") or [])
    meta["reactive_update_report"] = deepcopy(report)
    meta["stale_outputs"] = list(report.get("impacted_stages") or [])
    payload["meta"] = meta
    plan = build_plan_fn(payload)
    final_meta = safe_dict(plan.get("meta"))
    final_report = dict(report)
    completed_stages = _completed_stage_names(final_meta)
    impacted_stages = {safe_str(item) for item in safe_list(final_report.get("impacted_stages")) if safe_str(item)}
    uncleared_stale = sorted(impacted_stages - completed_stages, key=_stage_index)
    final_report["execution_mode"] = "full_plan_rerun_with_downstream_dirty_metadata"
    final_report["partial_rerun_executed"] = False
    final_report["partial_rerun_blocker"] = "Planner entrypoint does not yet expose isolated stage execution for external reactive edits."
    final_report["post_rerun_completed_stages"] = sorted(completed_stages, key=_stage_index)
    final_report["post_rerun_stale_outputs"] = uncleared_stale
    final_report["post_rerun_export_blocked"] = bool(uncleared_stale)
    final_report["post_rerun_truth"] = (
        "All impacted downstream stages reported complete after rerun."
        if not uncleared_stale
        else "Some impacted downstream stages did not report completion after rerun; exports remain blocked for those outputs."
    )
    construction_release_blockers = construction_release_blockers_from_meta(
        final_meta,
        requires_construction_release=final_plan_requires_construction_release(plan),
    )
    release_blockers = _post_rerun_release_blockers(plan, final_meta)
    final_report["post_rerun_construction_release_blockers"] = construction_release_blockers
    final_report["post_rerun_release_blockers"] = release_blockers
    final_report["post_rerun_production_ready"] = bool(
        safe_dict(final_meta.get("civil_design_readiness")).get("production_ready")
    ) and not final_report["post_rerun_export_blocked"] and not release_blockers
    plan.setdefault("meta", {})["reactive_update_report"] = final_report
    return {
        "success": True,
        "plan": plan,
        "reactive_update_report": final_report,
        "truth_label": "Reactive execution performed a safe full rerun with downstream dirty metadata; true isolated partial reruns still need planner-stage entrypoints.",
    }


__all__ = ["ENGINE_TO_STAGE", "build_reactive_update_report", "execute_reactive_rerun", "reactive_report_from_plan"]
