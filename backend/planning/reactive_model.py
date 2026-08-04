from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, Iterable, List, Set

from .common import blocker_explanations, safe_dict, safe_list, safe_str
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


REACTIVE_STAGE_COST = {
    "layout": 8,
    "grading": 7,
    "drainage": 6,
    "storm_pipes": 6,
    "sanitary": 6,
    "utility_network": 6,
    "coordination_resolution": 6,
    "earthwork": 5,
    "sheets": 2,
    "qa": 1,
}

REACTIVE_HEAVY_STAGES = {
    "layout",
    "grading",
    "drainage",
    "storm_pipes",
    "sanitary",
    "utility_network",
    "coordination_resolution",
    "earthwork",
}

REACTIVE_ENGINE_ORDER = [
    "geometry",
    "terrain_surface",
    "grading",
    "drainage",
    "storm_pipe",
    "sanitary",
    "water",
    "utility_coordination",
    "roadway_corridor",
    "profile_section",
    "structure",
    "earthwork",
    "hydrology",
    "conflict_resolution",
    "qa_validation",
    "quantity",
    "export_cad",
    "gis_existing_conditions",
    "ai_orchestration",
    "reactive_model",
]

REACTIVE_OBJECT_CHANGE_RULES = {
    "site": {
        "dirty_engine_ids": [
            "geometry",
            "terrain_surface",
            "grading",
            "drainage",
            "storm_pipe",
            "sanitary",
            "water",
            "utility_coordination",
            "roadway_corridor",
            "profile_section",
            "earthwork",
            "hydrology",
            "qa_validation",
            "quantity",
            "export_cad",
        ],
        "dirty_stages": [
            "layout",
            "grading",
            "drainage",
            "storm_pipes",
            "sanitary",
            "utility_network",
            "coordination_resolution",
            "earthwork",
            "sheets",
            "qa",
        ],
        "reason": "site_geometry_changed",
    },
    "building": {
        "dirty_engine_ids": [
            "geometry",
            "grading",
            "drainage",
            "storm_pipe",
            "sanitary",
            "water",
            "utility_coordination",
            "earthwork",
            "quantity",
            "export_cad",
        ],
        "dirty_stages": [
            "layout",
            "grading",
            "drainage",
            "storm_pipes",
            "sanitary",
            "utility_network",
            "coordination_resolution",
            "earthwork",
            "sheets",
            "qa",
        ],
        "reason": "building_footprint_or_location_changed",
    },
    "basin": {
        "dirty_engine_ids": ["grading", "drainage", "storm_pipe", "earthwork", "hydrology", "quantity", "export_cad"],
        "dirty_stages": ["grading", "drainage", "storm_pipes", "earthwork", "sheets", "qa"],
        "reason": "drainage_basin_location_or_geometry_changed",
    },
    "road": {
        "dirty_engine_ids": ["roadway_corridor", "grading", "drainage", "water", "utility_coordination", "profile_section", "earthwork", "quantity", "export_cad"],
        "dirty_stages": ["layout", "grading", "drainage", "utility_network", "coordination_resolution", "earthwork", "sheets", "qa"],
        "reason": "road_alignment_or_corridor_changed",
    },
    "utility": {
        "dirty_engine_ids": ["storm_pipe", "sanitary", "water", "utility_coordination", "profile_section", "earthwork", "quantity", "export_cad"],
        "dirty_stages": ["storm_pipes", "sanitary", "utility_network", "coordination_resolution", "earthwork", "sheets", "qa"],
        "reason": "utility_alignment_or_depth_changed",
    },
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


def _reactive_stage_cost(stage_names: Iterable[str]) -> int:
    return sum(REACTIVE_STAGE_COST.get(safe_str(stage_name), 3) for stage_name in set(stage_names))


def _sort_engines(engine_ids: Iterable[str]) -> List[str]:
    order = {engine_id: index for index, engine_id in enumerate(REACTIVE_ENGINE_ORDER)}
    return sorted({safe_str(item) for item in engine_ids if safe_str(item)}, key=lambda item: (order.get(item, len(order)), item))


def _all_stage_names() -> List[str]:
    return list(PLANNER_STAGE_ORDER)


def build_reactive_change_evidence(
    *,
    change_type: str,
    changed_object_id: str = "",
    actual_dirty_engine_ids: Iterable[str] = (),
    actual_dirty_stages: Iterable[str] = (),
    completed_stages: Iterable[str] = (),
    canonical_revision_before: str = "",
    canonical_revision_after: str = "",
) -> Dict[str, Any]:
    normalized_change = safe_str(change_type).lower()
    rule = safe_dict(REACTIVE_OBJECT_CHANGE_RULES.get(normalized_change))
    expected_engines = _sort_engines(rule.get("dirty_engine_ids") or [])
    expected_stages = sorted({safe_str(item) for item in safe_list(rule.get("dirty_stages")) if safe_str(item)}, key=_stage_index)
    actual_engines = _sort_engines(actual_dirty_engine_ids or expected_engines)
    actual_stages = sorted({safe_str(item) for item in (actual_dirty_stages or expected_stages) if safe_str(item)}, key=_stage_index)
    completed = sorted({safe_str(item) for item in completed_stages if safe_str(item)}, key=_stage_index)
    skipped_engines = _sort_engines(set(REACTIVE_ENGINE_ORDER) - set(expected_engines) - {"reactive_model"})
    skipped_stages = [stage_name for stage_name in _all_stage_names() if stage_name not in expected_stages]
    stale_outputs = [stage_name for stage_name in expected_stages if stage_name not in completed]
    affected_checks = [
        {
            "system": engine_id,
            "expected": "dirty",
            "actual": "dirty" if engine_id in actual_engines else "skipped",
            "valid": engine_id in actual_engines,
            "reason": safe_str(rule.get("reason"), f"{normalized_change}_changed"),
        }
        for engine_id in expected_engines
    ]
    skipped_checks = [
        {
            "system": engine_id,
            "expected": "skipped",
            "actual": "dirty" if engine_id in actual_engines else "skipped",
            "valid": engine_id not in actual_engines,
            "reason": f"not_downstream_of_{normalized_change}_change",
        }
        for engine_id in skipped_engines
    ]
    stage_checks = [
        {
            "stage": stage_name,
            "expected": "dirty",
            "actual": "dirty" if stage_name in actual_stages else "skipped",
            "valid": stage_name in actual_stages,
            "export_blocking_until_complete": stage_name not in completed,
        }
        for stage_name in expected_stages
    ] + [
        {
            "stage": stage_name,
            "expected": "skipped",
            "actual": "dirty" if stage_name in actual_stages else "skipped",
            "valid": stage_name not in actual_stages,
            "export_blocking_until_complete": False,
        }
        for stage_name in skipped_stages
    ]
    canonical_revision_valid = bool(canonical_revision_before and canonical_revision_after and canonical_revision_before != canonical_revision_after)
    production_ready = bool(rule) and canonical_revision_valid and not stale_outputs and all(
        bool(row.get("valid")) for row in affected_checks + skipped_checks + stage_checks
    )
    blockers = []
    if not rule:
        blockers.append("reactive_change_type_unknown")
    if not canonical_revision_valid:
        blockers.append("canonical_revision_trace_missing")
    if stale_outputs:
        blockers.append("stale_outputs_block_export")
    if any(not bool(row.get("valid")) for row in affected_checks):
        blockers.append("affected_system_mismatch")
    if any(not bool(row.get("valid")) for row in skipped_checks):
        blockers.append("unrelated_system_rerun_detected")
    if any(not bool(row.get("valid")) for row in stage_checks):
        blockers.append("stage_dirty_state_mismatch")
    return {
        "version": "reactive_model_evidence_v1",
        "change_type": normalized_change,
        "changed_object_id": safe_str(changed_object_id),
        "canonical_revision_before": safe_str(canonical_revision_before),
        "canonical_revision_after": safe_str(canonical_revision_after),
        "canonical_revision_valid": canonical_revision_valid,
        "expected_dirty_engine_ids": expected_engines,
        "actual_dirty_engine_ids": actual_engines,
        "expected_dirty_stages": expected_stages,
        "actual_dirty_stages": actual_stages,
        "expected_skipped_engine_ids": skipped_engines,
        "actual_skipped_engine_ids": _sort_engines(set(REACTIVE_ENGINE_ORDER) - set(actual_engines) - {"reactive_model"}),
        "expected_skipped_stages": skipped_stages,
        "actual_skipped_stages": [stage_name for stage_name in _all_stage_names() if stage_name not in actual_stages],
        "affected_system_checks": affected_checks,
        "skipped_system_checks": skipped_checks,
        "stage_checks": stage_checks,
        "completed_stages": completed,
        "stale_outputs": stale_outputs,
        "export_blocked": bool(stale_outputs),
        "review_readiness_blocked": bool(blockers),
        "production_ready": production_ready,
        "blockers": blockers,
        "run_policy": build_reactive_run_policy(impacted_stages=expected_stages, stale_outputs=stale_outputs),
        "truth_label": "Reactive evidence compares deterministic expected dirty/skipped systems to actual dirty/skipped systems; stale outputs remain blocked.",
    }


def validate_reactive_model_depth(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else safe_dict(plan_or_meta)
    report = safe_dict(meta.get("reactive_model_evidence") or meta.get("reactive_update_report"))
    checks: List[Dict[str, Any]] = []

    def add_check(name: str, ok: bool, evidence: str, blocker: str) -> None:
        checks.append(
            {
                "name": name,
                "ok": bool(ok),
                "evidence": evidence if ok else "",
                "blocker": "" if ok else blocker,
            }
        )

    if not report:
        add_check("reactive_report", False, "reactive report", "Reactive model depth needs a dependency-aware reactive update report.")
        add_check("affected_vs_skipped", False, "affected/skipped checks", "Reactive model depth needs deterministic affected-vs-skipped system checks.")
        add_check("stale_output_blocking", False, "stale output blocking", "Reactive model depth needs stale-output export/review blocking evidence.")
    else:
        affected = [safe_dict(row) for row in safe_list(report.get("affected_system_checks"))]
        skipped = [safe_dict(row) for row in safe_list(report.get("skipped_system_checks"))]
        stages = [safe_dict(row) for row in safe_list(report.get("stage_checks") or report.get("post_rerun_stage_status"))]
        add_check("reactive_report", safe_str(report.get("version")).startswith("reactive_model"), "reactive report", "Reactive model depth needs a versioned reactive report.")
        add_check(
            "canonical_revision_trace",
            report.get("canonical_revision_valid") is True or bool(safe_str(report.get("canonical_model_id"))),
            "canonical revision trace",
            "Reactive model depth needs canonical revision/model trace evidence.",
        )
        add_check(
            "affected_vs_skipped",
            bool(affected and skipped) and all(row.get("valid") is True for row in affected + skipped),
            "affected/skipped expected-actual checks",
            "Reactive model depth needs passing affected-vs-skipped system checks.",
        )
        add_check(
            "stage_dirty_checks",
            bool(stages) and all(row.get("valid") is not False for row in stages),
            "stage dirty expected-actual checks",
            "Reactive model depth needs passing stage dirty/skipped checks.",
        )
        stale = safe_list(report.get("stale_outputs") or report.get("post_rerun_stale_outputs"))
        export_blocked = report.get("export_blocked") is True or report.get("post_rerun_export_blocked") is True
        no_stale_after = not stale and (report.get("export_blocked") is False or report.get("post_rerun_export_blocked") is False)
        add_check(
            "stale_output_blocking",
            bool((stale and export_blocked) or no_stale_after),
            "stale output blocking",
            "Reactive model depth needs stale outputs blocked until affected reruns complete.",
        )
        add_check(
            "reactive_evidence_complete",
            report.get("production_ready") is True or (
                report.get("post_rerun_export_blocked") is False and not safe_list(report.get("post_rerun_stale_outputs"))
            ),
            "completed affected reruns",
            "Reactive model depth needs completed affected reruns before production-depth status.",
        )
        add_check(
            "partial_rerun_policy",
            report.get("partial_rerun_supported") is True or bool(safe_dict(report.get("run_policy"))),
            "partial rerun policy",
            "Reactive model depth needs partial-rerun policy evidence, not full-rerun-only behavior.",
        )
    blockers = [check["blocker"] for check in checks if not check["ok"] and check["blocker"]]
    return {
        "system": "reactive_model_depth",
        "production_ready": not blockers,
        "checks": checks,
        "blockers": blockers,
        "blocker_details": blocker_explanations(blockers),
        "evidence": [check["evidence"] for check in checks if check["ok"] and check["evidence"]],
        "reactive_report": deepcopy(report),
        "truth_label": "Reactive depth validates dependency-aware rerun evidence only; it never approves construction release.",
    }


def build_reactive_run_policy(
    *,
    impacted_stages: Iterable[str] = (),
    changed_engine_ids: Iterable[str] = (),
    changed_stages: Iterable[str] = (),
    stale_outputs: Iterable[str] = (),
) -> Dict[str, Any]:
    impacted = sorted({safe_str(item) for item in impacted_stages if safe_str(item)}, key=_stage_index)
    changed = sorted(
        {safe_str(item) for item in changed_stages if safe_str(item)}
        | {_target_stage(safe_str(item)) for item in changed_engine_ids if _target_stage(safe_str(item))},
        key=_stage_index,
    )
    stale = sorted({safe_str(item) for item in stale_outputs if safe_str(item)}, key=_stage_index)
    cost_score = _reactive_stage_cost(impacted)
    heavy_impacts = [stage for stage in impacted if stage in REACTIVE_HEAVY_STAGES]
    if not impacted:
        cost_label = "none"
        rerun_mode = "none"
    elif cost_score <= 3 and not heavy_impacts:
        cost_label = "quick"
        rerun_mode = "auto_live"
    elif cost_score <= 8 and not (set(changed) & {"layout", "grading"}):
        cost_label = "moderate"
        rerun_mode = "debounced_validation"
    else:
        cost_label = "heavy"
        rerun_mode = "manual_confirm_required"

    requires_confirmation = rerun_mode == "manual_confirm_required"
    automatic_engineering_rerun = rerun_mode == "auto_live"
    debounced_validation_ms = 500 if impacted else 0
    if rerun_mode == "none":
        next_action = "No downstream engineering rerun is required."
        message = "No impacted engineering systems were detected."
    elif automatic_engineering_rerun:
        next_action = "Apply the visual edit and rerun the quick affected outputs immediately."
        message = "This edit only touches quick downstream outputs, so it can run live."
    elif requires_confirmation:
        next_action = "Show the impact preview and wait for the user to approve re-engineering affected systems."
        message = "This edit affects heavy engineering systems; keep the visual move live and require confirmation before rerunning."
    else:
        next_action = "Apply the visual edit immediately, debounce cheap checks, and keep engineering regeneration explicit if the user keeps editing."
        message = "This edit supports debounced validation, but the app should not run heavy engineering on every movement."

    return {
        "version": "reactive_run_policy_v1",
        "rerun_mode": rerun_mode,
        "estimated_cost": cost_label,
        "estimated_cost_score": cost_score,
        "live_visual_update": bool(impacted or changed),
        "cheap_validation_auto_run": bool(impacted),
        "debounced_validation_ms": debounced_validation_ms,
        "automatic_engineering_rerun": automatic_engineering_rerun,
        "requires_user_confirmation": requires_confirmation,
        "impact_preview_required": bool(impacted) and not automatic_engineering_rerun,
        "heavy_impacted_stages": heavy_impacts,
        "changed_stages": changed,
        "impacted_stages": impacted,
        "stale_outputs": stale,
        "export_policy": (
            "block_exports_until_impacted_stages_complete"
            if impacted or stale
            else "exports_unchanged"
        ),
        "recommended_next_action": next_action,
        "user_message": message,
    }


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
    impacted_sorted = sorted(impacted_stages, key=_stage_index)
    skipped_stages = [
        stage_name
        for stage_name in PLANNER_STAGE_ORDER
        if stage_name not in set(impacted_sorted)
    ]
    dependency_edges: List[Dict[str, Any]] = []
    for upstream in PLANNER_STAGE_ORDER:
        for downstream in sorted(PLANNER_STAGE_DEPENDENCIES.get(upstream, set()), key=_stage_index):
            edge_impacted = upstream in impacted_stages or downstream in impacted_stages
            dependency_edges.append(
                {
                    "from": upstream,
                    "to": downstream,
                    "impacted": edge_impacted,
                    "why": (
                        f"{downstream} depends on {upstream}; rerun propagates through this edge."
                        if edge_impacted
                        else f"{downstream} depends on {upstream}; both are clean for this change."
                    ),
                }
            )
    impact_matrix: List[Dict[str, Any]] = []
    for stage_name in impacted_sorted:
        reasons: List[str] = []
        if stage_name in changed_stage_set:
            reasons.append("direct_changed_stage")
        for changed_stage in sorted(changed_stage_set, key=_stage_index):
            if stage_name != changed_stage and stage_name in _downstream_stage_closure(changed_stage):
                reasons.append(f"downstream_of_stage:{changed_stage}")
        for engine_id in sorted(changed_engine_set):
            if _target_stage(engine_id) == stage_name:
                reasons.append(f"mapped_from_changed_engine:{engine_id}")
            downstream_engine_stages = {
                _target_stage(item)
                for item in downstream_closure(engine_id)
                if _target_stage(item)
            }
            if stage_name in downstream_engine_stages:
                reasons.append(f"downstream_of_engine:{engine_id}")
        if stage_name in stale:
            reasons.append("already_stale")
        reason_summary = "; ".join(reason.replace("_", " ") for reason in sorted(dict.fromkeys(reasons)))
        impact_matrix.append(
            {
                "stage": stage_name,
                "changed": stage_name in changed_stage_set,
                "stale_before_rerun": stage_name in stale,
                "heavy": stage_name in REACTIVE_HEAVY_STAGES,
                "reason_codes": sorted(dict.fromkeys(reasons)),
                "why": reason_summary or "Included by dependency closure.",
                "export_blocking_until_complete": True,
            }
        )
    changed_system_report = [
        {
            "system": stage_name,
            "kind": "stage",
            "why": "Directly changed by the user edit.",
        }
        for stage_name in sorted(changed_stage_set, key=_stage_index)
    ] + [
        {
            "system": engine_id,
            "kind": "engine",
            "why": f"{engine_id} changed; mapped planner stages and downstream dependencies must be current.",
        }
        for engine_id in sorted(changed_engine_set)
    ]
    affected_system_report = {
        "changed_systems": changed_system_report,
        "affected_stages": [
            {
                "stage": row["stage"],
                "why": row["why"],
                "reason_codes": row["reason_codes"],
                "rerun_required": True,
            }
            for row in impact_matrix
        ],
        "skipped_stages": [
            {
                "stage": stage_name,
                "why": "No changed upstream dependency reaches this stage.",
                "rerun_required": False,
            }
            for stage_name in skipped_stages
        ],
        "unaffected_stages": skipped_stages,
    }
    before_after_comparison = [
        {
            "stage": stage_name,
            "before": "stale" if stage_name in impacted_stages or stage_name in stale else "current",
            "after": "pending_rerun" if stage_name in impacted_stages or stage_name in stale else "unchanged",
            "changed": stage_name in changed_stage_set,
            "rerun_required": stage_name in impacted_stages or stage_name in stale,
            "skipped": stage_name in skipped_stages,
        }
        for stage_name in PLANNER_STAGE_ORDER
    ]
    run_policy = build_reactive_run_policy(
        impacted_stages=impacted_stages,
        changed_engine_ids=changed_engine_set,
        changed_stages=changed_stage_set,
        stale_outputs=stale,
    )
    return {
        "version": "reactive_model_v1",
        "changed_engine_ids": sorted(changed_engine_set),
        "changed_stages": sorted(changed_stage_set, key=_stage_index),
        "impacted_engine_ids": sorted(impacted_engines),
        "impacted_stages": impacted_sorted,
        "skipped_stages": skipped_stages,
        "dependency_graph": {
            "nodes": [
                {
                    "id": stage_name,
                    "label": stage_name.replace("_", " ").title(),
                    "state": "affected" if stage_name in impacted_stages else "skipped",
                    "changed": stage_name in changed_stage_set,
                }
                for stage_name in PLANNER_STAGE_ORDER
            ],
            "edges": dependency_edges,
        },
        "impact_matrix": impact_matrix,
        "affected_system_report": affected_system_report,
        "before_after_comparison": before_after_comparison,
        "partial_rerun_supported": True,
        "ran_stages": sorted((stage for stage in ran_stages if stage), key=_stage_index),
        "stale_outputs": stale,
        "export_blocked": bool(stale),
        "export_requires_current_downstream": bool(impacted_stages or stale),
        "export_blocked_before_rerun": bool(impacted_stages or stale),
        "run_policy": run_policy,
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


def _merged_release_deliverables(*values: Any) -> List[str]:
    merged: List[str] = []
    for value in values:
        for item in safe_list(value):
            name = safe_str(item).strip()
            if name and name not in merged:
                merged.append(name)
    return merged


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


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
    failed_deliverables = _merged_release_deliverables(
        deliverables.get("failed"),
        release_review.get("failed_deliverables"),
    )
    for failed_deliverable in failed_deliverables:
        failed_name = safe_str(failed_deliverable).strip()
        if failed_name:
            _add(f"failed_deliverable_{failed_name.lower().replace(' ', '_')}")
    requested_deliverables = _merged_release_deliverables(
        deliverables.get("requested"),
        release_review.get("requested_deliverables"),
    )
    produced_deliverables = _merged_release_deliverables(
        deliverables.get("produced"),
        release_review.get("produced_deliverables"),
    )
    missing_deliverables = _merged_release_deliverables(
        deliverables.get("missing"),
        release_review.get("missing_deliverables"),
    )
    produced_set = {safe_str(item).strip() for item in produced_deliverables if safe_str(item).strip()}
    failed_set = {safe_str(item).strip() for item in failed_deliverables if safe_str(item).strip()}
    missing_deliverables.extend(
        item
        for item in requested_deliverables
        if safe_str(item).strip()
        and safe_str(item).strip() not in produced_set
        and safe_str(item).strip() not in failed_set
    )
    for missing_deliverable in missing_deliverables:
        missing_name = safe_str(missing_deliverable).strip()
        if missing_name:
            _add(f"missing_deliverable_{missing_name.lower().replace(' ', '_')}")

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
    run_summary = safe_dict(meta.get("run_summary"))
    if run_summary.get("success") is False:
        _add("planner_run_failed")
    if _safe_int(run_summary.get("error_count")) > 0:
        _add("planner_errors_present")
    return blockers


def execute_reactive_rerun(
    base_payload: Dict[str, Any],
    *,
    changed_engine_ids: Iterable[str] = (),
    changed_stages: Iterable[str] = (),
    edits: Dict[str, Any] = None,
    build_plan_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    partial_rerun_fn: Callable[[Dict[str, Any]], Dict[str, Any]] = None,
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
    dirty_state = dict(safe_dict(meta.get("system_dirty_state")))
    for stage_name in safe_list(report.get("impacted_stages")):
        stage_key = safe_str(stage_name)
        if not stage_key:
            continue
        dirty_state[stage_key] = {
            "state": "dirty",
            "reasons": [f"Reactive edit impacted {stage_key}; rerun required before export."],
            "source": "reactive_update",
        }
    if dirty_state:
        meta["system_dirty_state"] = dirty_state
    payload["meta"] = meta
    partial_attempted = callable(partial_rerun_fn)
    plan = partial_rerun_fn(payload) if partial_attempted else build_plan_fn(payload)
    final_meta = safe_dict(plan.get("meta"))
    final_report = dict(report)
    completed_stages = _completed_stage_names(final_meta)
    impacted_stages = {safe_str(item) for item in safe_list(final_report.get("impacted_stages")) if safe_str(item)}
    uncleared_stale = sorted(impacted_stages - completed_stages, key=_stage_index)
    final_report["execution_mode"] = (
        "isolated_downstream_partial_rerun"
        if partial_attempted
        else "full_plan_rerun_with_downstream_dirty_metadata"
    )
    final_report["partial_rerun_executed"] = partial_attempted
    if not partial_attempted:
        final_report["partial_rerun_blocker"] = "No partial rerun executor was provided for this reactive request."
    final_report["post_rerun_completed_stages"] = sorted(completed_stages, key=_stage_index)
    final_report["post_rerun_stale_outputs"] = uncleared_stale
    final_report["post_rerun_export_blocked"] = bool(uncleared_stale)
    final_report["post_rerun_stage_status"] = [
        {
            "stage": stage_name,
            "before": "stale",
            "after": "complete" if stage_name in completed_stages else "stale",
            "completed": stage_name in completed_stages,
            "stale_after_rerun": stage_name in uncleared_stale,
            "export_blocking": stage_name in uncleared_stale,
        }
        for stage_name in sorted(impacted_stages, key=_stage_index)
    ]
    final_report["affected_system_report"] = {
        "changed_stages": safe_list(final_report.get("changed_stages")),
        "impacted_stages": safe_list(final_report.get("impacted_stages")),
        "completed_stages": final_report["post_rerun_completed_stages"],
        "stale_after_rerun": uncleared_stale,
        "affected_stages": safe_list(safe_dict(final_report.get("affected_system_report")).get("affected_stages")),
        "skipped_stages": safe_list(safe_dict(final_report.get("affected_system_report")).get("skipped_stages")),
        "unaffected_stages": [
            stage_name
            for stage_name in PLANNER_STAGE_ORDER
            if stage_name not in impacted_stages
        ],
    }
    final_report["before_after_comparison"] = [
        {
            **safe_dict(row),
            "after": (
                "complete"
                if safe_str(safe_dict(row).get("stage")) in completed_stages
                else "stale"
                if safe_str(safe_dict(row).get("stage")) in uncleared_stale
                else safe_str(safe_dict(row).get("after"), "unchanged")
            ),
        }
        for row in safe_list(final_report.get("before_after_comparison"))
    ]
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
    final_report["post_rerun_construction_release_blocker_details"] = blocker_explanations(construction_release_blockers)
    final_report["post_rerun_release_blockers"] = release_blockers
    final_report["post_rerun_release_blocker_details"] = blocker_explanations(release_blockers)
    final_report["post_rerun_production_ready"] = bool(
        safe_dict(final_meta.get("civil_design_readiness")).get("production_ready")
    ) and not final_report["post_rerun_export_blocked"] and not release_blockers
    plan.setdefault("meta", {})["reactive_update_report"] = final_report
    return {
        "success": True,
        "plan": plan,
        "reactive_update_report": final_report,
        "truth_label": (
            "Reactive execution performed an isolated downstream partial rerun from checkpointed canonical state."
            if partial_attempted
            else "Reactive execution performed a safe full rerun with downstream dirty metadata because no partial executor was provided."
        ),
    }


__all__ = [
    "ENGINE_TO_STAGE",
    "build_reactive_change_evidence",
    "build_reactive_run_policy",
    "build_reactive_update_report",
    "execute_reactive_rerun",
    "reactive_report_from_plan",
    "validate_reactive_model_depth",
]
