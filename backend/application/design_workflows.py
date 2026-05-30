from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException

from backend.planning.release_gates import (
    construction_release_blockers_from_meta,
    final_plan_requires_construction_release,
)


def now_ts() -> float:
    return time.time()


def new_workflow_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _review_category_from_value(value: Any) -> str:
    lowered = str(value or "").strip().lower()
    if not lowered:
        return "general"
    if any(token in lowered for token in ("width", "linear feature", "discipline default", "design default", "default")):
        return "design_defaults"
    if any(token in lowered for token in ("drain", "detention", "basin", "inlet", "flow_path")):
        return "drainage"
    if any(token in lowered for token in ("storm", "pipe", "hydraulic")):
        return "pipes"
    if any(token in lowered for token in ("utility", "water", "sanitary", "sewer")):
        return "utilities"
    if any(token in lowered for token in ("grade", "contour", "surface", "slope")):
        return "grading"
    if any(token in lowered for token in ("layout", "parking", "building", "site")):
        return "layout"
    if any(token in lowered for token in ("deliverable", "profile", "section")):
        return "deliverables"
    if any(token in lowered for token in ("earthwork", "quantity")):
        return "quantities"
    if any(token in lowered for token in ("coordination", "conflict", "clearance")):
        return "coordination"
    if "qa" in lowered:
        return "validation"
    return "general"


def _is_user_facing_assumption(value: Any) -> bool:
    lowered = str(value or "").strip().lower()
    if not lowered:
        return False
    internal_markers = (
        "projectmanager as active lifecycle state",
        "action geometry is treated as output packaging",
        "quantities prefer canonical projectmanager metrics",
        "planner executed model-first workflow",
        "prompt was parsed with deterministic fast-path rules",
        "planner execution assumption",
        "autofix_site_layout",
    )
    return not any(marker in lowered for marker in internal_markers)


def _normalized_assumption_summary(raw_summary: Dict[str, Any]) -> Dict[str, Any]:
    examples = [
        str(item).strip()
        for item in list(raw_summary.get("examples") or [])
        if _is_user_facing_assumption(item)
    ]
    raw_categories = [
        str(item).strip()
        for item in list(raw_summary.get("categories") or [])
        if str(item or "").strip()
    ]
    categories: list[str] = []
    for item in raw_categories:
        category = _review_category_from_value(item)
        if category == "general" and str(item).strip():
            category = str(item).strip().lower()
        if category not in categories:
            categories.append(category)
    if not categories:
        category_counts: Dict[str, int] = {}
        for example in examples:
            category = _review_category_from_value(example)
            if category == "pipes":
                category = "storm"
            category_counts[category] = category_counts.get(category, 0) + 1
        categories = [
            name
            for name, count in sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))
            if count > 0
        ]
    raw_count = int(raw_summary.get("count") or 0)
    return {
        "count": max(raw_count, len(examples)),
        "categories": categories,
        "examples": examples[:5],
    }


def _normalized_review_categories(convergence: Dict[str, Any]) -> list[str]:
    raw = list(convergence.get("unresolved_issue_categories") or [])
    blocked = list(convergence.get("blocked_reasons") or [])
    qa = list(convergence.get("qa_issue_categories") or [])
    out: list[str] = []
    for item in raw + blocked + qa:
        category = _review_category_from_value(item)
        if category and category not in out:
            out.append(category)
    return out


def _deliverable_summary(deliverables: Dict[str, Any]) -> Dict[str, list[str]]:
    requested = [str(item) for item in list(deliverables.get("requested") or []) if str(item)]
    produced = [str(item) for item in list(deliverables.get("produced") or []) if str(item)]
    failed = [str(item) for item in list(deliverables.get("failed") or []) if str(item)]
    ready_requested = [item for item in requested if item in produced]
    extra_produced = [item for item in produced if item not in requested]
    return {
        "requested": requested,
        "produced": produced,
        "failed": failed,
        "ready_requested": ready_requested,
        "extra_produced": extra_produced,
    }


def _failed_deliverable_blockers(failed_deliverables: list[str]) -> list[str]:
    return list(
        dict.fromkeys(
            f"failed_deliverable_{str(item).strip().lower().replace(' ', '_')}"
            for item in failed_deliverables
            if str(item).strip()
        )
    )


def _build_phase_checkpoints(
    *,
    final_plan: Dict[str, Any],
    stage_completeness: Dict[str, Any],
    deliverable_summary: Dict[str, list[str]],
    blocked_exports: list[str],
    blocked_reasons: list[str],
    release_ready: bool,
) -> Dict[str, Any]:
    meta = dict(final_plan.get("meta") or {})
    actions = [
        dict(action)
        for action in list(final_plan.get("actions") or [])
        if isinstance(action, dict)
    ]
    stage_rows = {
        str(row.get("stage_name") or ""): dict(row)
        for row in list(stage_completeness.get("stages") or [])
        if str(dict(row).get("stage_name") or "")
    }
    compact_statuses = {
        str(name): str(status)
        for name, status in dict(stage_completeness.get("statuses") or {}).items()
        if str(name)
    }
    required_status = dict(stage_completeness.get("required_stage_status") or {})
    action_layers = {
        str(action.get("layer") or "").upper()
        for action in actions
        if str(action.get("layer") or "")
    }

    def _is_benign_skip_message(message: str) -> bool:
        lowered = str(message or "").strip().lower()
        if not lowered:
            return False
        return any(
            token in lowered
            for token in (
                "skipped because canonical state is already clean",
                "was not requested",
                "omitted by user intent",
                "source=omit",
                "no profile or cross-section deliverables were requested",
            )
        )

    def _stage_message(stage_name: str) -> str:
        return str(dict(stage_rows.get(stage_name) or {}).get("message") or "").strip()

    def _stage_state(stage_name: str) -> str:
        raw_status = str(
            required_status.get(stage_name)
            or compact_statuses.get(stage_name)
            or dict(stage_rows.get(stage_name) or {}).get("completeness")
            or ""
        ).strip().lower()
        if not raw_status:
            return "pending"
        if raw_status == "failed":
            return "failed"
        if raw_status in {"running", "in_progress", "started"}:
            return "running"
        if raw_status == "complete":
            return "complete"
        if raw_status == "assumed":
            return "pending" if _is_benign_skip_message(_stage_message(stage_name)) else "partial"
        if raw_status == "partial" and _is_benign_skip_message(_stage_message(stage_name)):
            return "complete"
        return raw_status

    def _phase_status(*stage_names: str) -> str:
        statuses = [_stage_state(stage) for stage in stage_names if _stage_state(stage) != "pending"]
        if not statuses:
            return "pending"
        if any(status == "failed" for status in statuses):
            return "failed"
        if all(status == "complete" for status in statuses):
            return "complete"
        if any(status in {"running", "in_progress", "started"} for status in statuses):
            return "running"
        return "partial"

    def _phase_messages(*stage_names: str) -> list[str]:
        out: list[str] = []
        for stage in stage_names:
            row = dict(stage_rows.get(stage) or {})
            message = str(row.get("message") or "").strip()
            if message and message not in out:
                out.append(message)
        return out

    def _phase(stage_names: tuple[str, ...], deliverables: list[str], has_data: bool, *, label: str, blockers: list[str]) -> Dict[str, Any]:
        status = _phase_status(*stage_names)
        messages = _phase_messages(*stage_names)[:3]
        benign_skip = any(_is_benign_skip_message(message) for message in messages)
        ready = status == "complete" and not blockers and (has_data or not deliverables or benign_skip)
        return {
            "label": label,
            "status": status,
            "ready": ready,
            "deliverables": deliverables,
            "messages": messages,
            "blockers": blockers,
            "has_data": has_data,
            "stages": list(stage_names),
        }

    requested = set(deliverable_summary.get("requested") or [])
    produced = set(deliverable_summary.get("produced") or [])
    layout_deliverables = sorted([item for item in requested | produced if item in {"site_plan"}])
    grading_deliverables = sorted([item for item in requested | produced if item in {"grading_plan", "contours", "spot_grades", "flow_arrows"}])
    drainage_deliverables = sorted([item for item in requested | produced if item in {"storm_pipe_plan", "drainage_plan"}])
    utility_deliverables = sorted([item for item in requested | produced if item in {"utility_plan", "sanitary_plan", "water_plan"}])
    coordination_deliverables = sorted([item for item in requested | produced if item in {"report", "coordination_report"}])

    layout_blockers = [reason for reason in blocked_reasons if any(token in reason for token in ("layout", "building", "parking", "site"))]
    grading_blockers = [reason for reason in blocked_reasons if any(token in reason for token in ("grading", "grade", "contour", "surface", "slope"))]
    drainage_blockers = [reason for reason in blocked_reasons if any(token in reason for token in ("storm", "drain", "basin", "inlet", "pipe", "hydraulic"))]
    utility_blockers = [reason for reason in blocked_reasons if any(token in reason for token in ("utility", "water", "sanitary", "sewer"))]
    coordination_blockers = [reason for reason in blocked_reasons if reason not in layout_blockers + grading_blockers + drainage_blockers + utility_blockers]

    phase_checkpoints = {
        "layout": _phase(
            ("layout",),
            layout_deliverables,
            has_data=bool(action_layers.intersection({"BUILDING", "PARKING", "PAVEMENT", "WALK", "ROAD"})) or "site_plan" in deliverable_summary.get("ready_requested", []),
            label="Layout",
            blockers=layout_blockers,
        ),
        "grading": _phase(
            ("grading",),
            grading_deliverables,
            has_data=bool(meta.get("grading")) or bool(action_layers.intersection({"FG_CONTOUR", "SPOT_FG"})),
            label="Grading",
            blockers=grading_blockers,
        ),
        "drainage_storm": _phase(
            ("drainage", "storm_pipes"),
            drainage_deliverables,
            has_data=bool(meta.get("drainage") or meta.get("storm_pipes")) or bool(action_layers.intersection({"PIPE", "BASIN_BOUNDARY", "STRUCTURE", "DRAIN", "STORM"})),
            label="Drainage and Storm",
            blockers=drainage_blockers,
        ),
        "utilities": _phase(
            ("sanitary", "utility_network"),
            utility_deliverables,
            has_data=bool(meta.get("utilities") or meta.get("sanitary")) or bool(action_layers.intersection({"UTILITY", "WATER", "SAN"})),
            label="Utilities",
            blockers=utility_blockers,
        ),
        "coordination_validation": _phase(
            ("coordination_resolution", "qa"),
            coordination_deliverables,
            has_data=bool(meta.get("coordination") or meta.get("manual_validation") or meta.get("truth_audit")),
            label="Coordination and Validation",
            blockers=coordination_blockers,
        ),
    }

    if release_ready and not blocked_exports and not blocked_reasons:
        for item in phase_checkpoints.values():
            if item.get("status") == "running":
                continue
            if item.get("blockers"):
                continue
            if item.get("has_data") or not item.get("deliverables") or any(
                _is_benign_skip_message(message) for message in list(item.get("messages") or [])
            ):
                item["status"] = "complete"
                item["ready"] = True

    completed_phases = sum(1 for item in phase_checkpoints.values() if bool(item.get("ready")))
    combined_status = "ready" if release_ready else ("blocked" if blocked_exports or blocked_reasons else "review")
    combined_note = (
        "Combined engineering view is release-ready."
        if combined_status == "ready"
        else ("Combined engineering view is blocked pending remaining phase issues." if combined_status == "blocked" else "Combined engineering view is available for review while phases continue to mature.")
    )
    return {
        "layout": phase_checkpoints["layout"],
        "grading": phase_checkpoints["grading"],
        "drainage_storm": phase_checkpoints["drainage_storm"],
        "utilities": phase_checkpoints["utilities"],
        "coordination_validation": phase_checkpoints["coordination_validation"],
        "combined_view": {
            "status": combined_status,
            "ready": release_ready,
            "completed_phase_count": completed_phases,
            "total_phase_count": len(phase_checkpoints),
            "blocked_exports": list(blocked_exports),
            "blocked_reasons": list(blocked_reasons),
            "deliverables_ready": list(deliverable_summary.get("ready_requested") or []),
            "deliverables_extra": list(deliverable_summary.get("extra_produced") or []),
            "note": combined_note,
        },
    }


def run_orchestration(
    payload_data: Dict[str, Any],
    *,
    load_orchestrator: Callable[[], tuple[Any, Any]],
    assess_design_readiness: Callable[[str, Optional[Dict[str, Any]]], Optional[Dict[str, Any]]],
    progress_callback: Optional[Callable[..., None]] = None,
) -> Dict[str, Any]:
    PlannerOrchestratorRequest, orchestrate_plan = load_orchestrator()
    prompt_text = payload_data.get("prompt_text")
    if prompt_text is None:
        prompt_text = payload_data.get("prompt")

    req = PlannerOrchestratorRequest(
        input_mode=payload_data.get("input_mode", "assisted"),
        strict_mode=bool(payload_data.get("strict_mode", False)),
        full_design_mode=bool(payload_data.get("full_design_mode", False)),
        prompt_text=prompt_text,
        image_path=payload_data.get("image_path"),
        manual_fields=dict(payload_data.get("manual_fields") or {}),
        image_width_px=payload_data.get("image_width_px"),
        image_height_px=payload_data.get("image_height_px"),
        pixels_per_unit=payload_data.get("pixels_per_unit"),
        plan_type_hint=payload_data.get("plan_type_hint"),
        units=payload_data.get("units", "ft"),
        allow_ai_fill_for_blanks=bool(payload_data.get("allow_ai_fill_for_blanks", True)),
        persist_trace_metadata=bool(payload_data.get("persist_trace_metadata", True)),
        meta=dict(payload_data.get("meta") or {}),
        progress_callback=progress_callback,
    )

    assisted_enabled = bool(req.allow_ai_fill_for_blanks)
    if not assisted_enabled and str(req.prompt_text or "").strip():
        readiness_issue = assess_design_readiness(
            str(req.prompt_text),
            {
                "strategy_mode": "user",
                "project_type": (req.manual_fields or {}).get("project_type") or (req.meta or {}).get("project_type"),
                "lot_width": ((req.manual_fields or {}).get("lot") or {}).get("w"),
                "lot_height": ((req.manual_fields or {}).get("lot") or {}).get("h"),
                "parking_count": ((req.manual_fields or {}).get("site_plan") or {}).get("parking_count"),
                "disciplines": {
                    "roads": bool((req.manual_fields or {}).get("roads")) or bool((req.meta or {}).get("include_roads")),
                    "grading": bool((req.manual_fields or {}).get("grading")) or bool((req.meta or {}).get("include_grading")),
                    "drainage": bool((req.manual_fields or {}).get("drainage")) or bool((req.meta or {}).get("include_drainage")),
                    "utilities": bool((req.manual_fields or {}).get("utility_network")) or bool((req.meta or {}).get("include_utilities")),
                },
            },
        )
        if readiness_issue:
            missing_requirements = list(readiness_issue.get("missing_requirements") or [])
            missing_fields = [
                str(item.get("field") or item.get("name") or item) if isinstance(item, dict) else str(item)
                for item in missing_requirements
            ]
            structured_missing = {
                "missing_fields": missing_fields,
                "why_needed": {
                    str(item.get("field") or item.get("name") or item): str(
                        item.get("why_needed") or item.get("reason") or "Required to complete the engineering step."
                    )
                    for item in missing_requirements
                    if isinstance(item, dict)
                },
                "suggested_next_actions": [
                    "Add the missing information.",
                    "Turn on Assisted to let Civora infer reasonable, clearly labeled assumptions.",
                ],
                "can_assist_if_enabled": True,
            }
            return {
                "success": False,
                "message": str(
                    readiness_issue.get("assistant_message")
                    or "Civora needs more information before it can complete this step. Add the missing details, or turn on Assisted to let Civora infer reasonable, clearly labeled assumptions."
                ),
                "parsed_payload": dict(payload_data),
                "final_plan": {},
                "warnings": [],
                "errors": [str(readiness_issue.get("reason") or "Minimum engineering design context is incomplete")],
                "issues": [],
                "assumptions": [],
                "missing_requirements": structured_missing,
                "metadata": {
                    "_workflow_run_id": new_workflow_id("run"),
                    "input_mode": payload_data.get("input_mode", "user"),
                    "needs_clarification": True,
                    "clarification_reason": readiness_issue.get("reason"),
                    "missing_requirements": structured_missing,
                },
            }

    result = orchestrate_plan(req)
    result_payload = {
        "success": result.success,
        "message": result.message,
        "parsed_payload": result.parsed_payload,
        "final_plan": result.final_plan,
        "warnings": result.warnings,
        "errors": result.errors,
        "issues": [
            {
                "code": issue.code,
                "severity": issue.severity,
                "message": issue.message,
                "context": issue.context,
            }
            for issue in result.issues
        ],
        "assumptions": [
            {
                "field_name": assumption.field_name,
                "assumed_value": assumption.assumed_value,
                "reason": assumption.reason,
            }
            for assumption in result.assumptions
        ],
        "metadata": dict(result.metadata or {}),
    }
    result_payload["metadata"].setdefault("_workflow_run_id", new_workflow_id("run"))
    result_payload["metadata"].setdefault("input_mode", payload_data.get("input_mode", "assisted"))
    if isinstance(result_payload["metadata"].get("missing_requirements"), dict):
        result_payload["missing_requirements"] = dict(result_payload["metadata"]["missing_requirements"])
    return result_payload


def count_unresolved_conflicts(final_plan: Dict[str, Any]) -> int:
    meta = dict(final_plan.get("meta") or {})
    coordination = dict(meta.get("coordination") or {})
    unresolved = coordination.get("unresolved_conflicts") or []
    if isinstance(unresolved, int):
        return int(unresolved)
    return len(unresolved)


def build_run_summary(
    result_data: Dict[str, Any],
    *,
    source: str,
    project_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    metadata = dict(result_data.get("metadata") or {})
    final_plan = dict(result_data.get("final_plan") or {})
    plan_meta = dict(final_plan.get("meta") or {})
    deliverables = dict(plan_meta.get("deliverables") or {})
    engineering = dict(plan_meta.get("engineering_status") or {})
    truth = dict(plan_meta.get("truth_audit") or {})
    manual_validation = dict(plan_meta.get("manual_validation") or {})
    stage_completeness = dict(plan_meta.get("stage_completeness") or {})
    coordination = dict(plan_meta.get("coordination") or {})
    convergence = dict(plan_meta.get("convergence_summary") or {})
    final_release_review = dict(plan_meta.get("release_review") or {})
    optimization = dict(plan_meta.get("optimization_summary") or {})
    run_id = metadata.get("_workflow_run_id") or new_workflow_id("run")
    created_at = now_ts()
    parsed_payload = dict(result_data.get("parsed_payload") or {})
    input_summary = {
        "project_type": parsed_payload.get("project_type") or parsed_payload.get("site_type") or "",
        "site_type": parsed_payload.get("site_type") or parsed_payload.get("project_type") or "",
        "street_edge": parsed_payload.get("street_edge") or "",
        "lot": dict(parsed_payload.get("lot") or {}),
        "building_count": len([item for item in list(parsed_payload.get("buildings") or []) if isinstance(item, dict)]),
        "buildings": [
            {
                "name": str(item.get("name") or item.get("label") or item.get("type") or ""),
                "type": str(item.get("type") or ""),
                "width": item.get("width", item.get("w")),
                "depth": item.get("depth", item.get("d")),
            }
            for item in list(parsed_payload.get("buildings") or [])
            if isinstance(item, dict)
        ],
    }
    blocked_exports = list(
        final_release_review.get("blocked_exports")
        if "blocked_exports" in final_release_review
        else (convergence.get("blocked_exports") or [])
    )
    blocked_reasons = list(
        final_release_review.get("blocked_reasons")
        if "blocked_reasons" in final_release_review
        else (convergence.get("blocked_reasons") or [])
    )
    for construction_blocker in construction_release_blockers_from_meta(
        plan_meta,
        requires_construction_release=final_plan_requires_construction_release(final_plan),
    ):
        if construction_blocker not in blocked_reasons:
            blocked_reasons.append(construction_blocker)
    unresolved_conflict_count = int(convergence.get("unresolved_conflict_count") or 0)
    failed_deliverables = list(deliverables.get("failed") or [])
    normalized_assumptions = _normalized_assumption_summary(dict(convergence.get("assumption_summary") or {}))
    normalized_review_categories = _normalized_review_categories(convergence)
    deliverable_summary = _deliverable_summary(deliverables)
    success = bool(result_data.get("success"))
    converged = bool(convergence.get("converged"))
    warning_count = len(list(result_data.get("warnings") or []))
    error_count = len(list(result_data.get("errors") or []))
    manual_failures = [
        {
            "code": item.get("code"),
            "message": item.get("message"),
            "system": item.get("system"),
            "rule": item.get("rule"),
            "location": item.get("location"),
            "reason": item.get("reason"),
        }
        for item in list(manual_validation.get("failures") or [])
    ]
    for failure in manual_failures:
        failure_code = str(failure.get("code") or failure.get("rule") or failure.get("system") or "manual_validation_failure").strip()
        if not failure_code:
            failure_code = "manual_validation_failure"
        blocker = f"manual_validation_{failure_code.lower().replace(' ', '_')}"
        if blocker not in blocked_reasons:
            blocked_reasons.append(blocker)
    for failed_blocker in _failed_deliverable_blockers(failed_deliverables):
        if failed_blocker not in blocked_reasons:
            blocked_reasons.append(failed_blocker)
    release_ready = (
        success
        and converged
        and unresolved_conflict_count == 0
        and not blocked_exports
        and not blocked_reasons
        and not failed_deliverables
        and not manual_failures
    )
    retryable = not release_ready and (not success or bool(blocked_exports or blocked_reasons or unresolved_conflict_count or error_count or manual_failures))
    primary_attention = (
        (blocked_reasons[:1] or blocked_exports[:1] or list(convergence.get("unresolved_issue_categories") or [])[:1] or failed_deliverables[:1] or [None])[0]
    )
    persistence_scope = "ephemeral"
    if project_id and job_id:
        persistence_scope = "project_and_job"
    elif project_id:
        persistence_scope = "project"
    elif job_id:
        persistence_scope = "job"

    phase_checkpoints = _build_phase_checkpoints(
        final_plan=final_plan,
        stage_completeness=stage_completeness,
        deliverable_summary=deliverable_summary,
        blocked_exports=blocked_exports,
        blocked_reasons=blocked_reasons,
        release_ready=release_ready,
    )

    return {
        "run_id": run_id,
        "project_id": project_id,
        "job_id": job_id,
        "source": source,
        "created_at": created_at,
        "input_summary": input_summary,
        "input_mode": metadata.get("input_mode") or dict(result_data.get("parsed_payload") or {}).get("input_mode"),
        "strict_mode": bool(dict(result_data.get("parsed_payload") or {}).get("strict_mode", False)),
        "success": success,
        "message": str(result_data.get("message") or ""),
        "engineering_status": {
            "success": bool(engineering.get("success")),
            "status": str(engineering.get("status") or ""),
            "trust_score": float(engineering.get("engineering_trust_score") or truth.get("engineering_trust_score") or 0.0),
        },
        "truth_success": bool(truth.get("success")),
        "all_required_complete": bool(stage_completeness.get("all_required_complete")),
        "requested_deliverables": deliverable_summary["requested"],
        "produced_deliverables": deliverable_summary["produced"],
        "failed_deliverables": deliverable_summary["failed"],
        "ready_deliverables": deliverable_summary["ready_requested"],
        "extra_deliverables": deliverable_summary["extra_produced"],
        "manual_failures": manual_failures,
        "stage_summary": {
            "all_required_complete": bool(stage_completeness.get("all_required_complete")),
            "required_stage_count": int(stage_completeness.get("required_stage_count") or 0),
            "complete_stage_count": int(stage_completeness.get("complete_stage_count") or 0),
            "statuses": dict(stage_completeness.get("statuses") or {}),
        },
        "phase_checkpoints": phase_checkpoints,
        "coordination_summary": {
            "unresolved_conflicts": count_unresolved_conflicts(final_plan),
            "selected_strategy": coordination.get("selected_group_strategy") or "none",
        },
        "convergence_summary": {
            "converged": converged,
            "passes_run": int(convergence.get("passes_run") or 0),
            "max_passes": int(convergence.get("max_passes") or 0),
            "warning_count": int(convergence.get("warning_count") or 0),
            "error_count": int(convergence.get("error_count") or 0),
            "unresolved_conflict_count": unresolved_conflict_count,
            "assumption_summary": normalized_assumptions,
            "unresolved_issue_categories": normalized_review_categories,
            "qa_issue_categories": list(convergence.get("qa_issue_categories") or []),
            "rerun_summary": dict(convergence.get("rerun_summary") or {}),
            "blocked_exports": blocked_exports,
            "blocked_reasons": blocked_reasons,
            "pass_history": list(convergence.get("pass_history") or []),
            "fix_summary": dict(convergence.get("fix_summary") or {}),
            "dominant_issue_categories": list(dict(convergence.get("fix_summary") or {}).get("dominant_issue_categories") or []),
            "last_fix_attempt": dict(dict(convergence.get("fix_summary") or {}).get("last_fix_attempt") or {}),
        },
        "optimization_summary": {
            "active_goal": str(optimization.get("active_goal") or ""),
            "overall_score": float(optimization.get("overall_score") or 0.0),
            "component_scores": dict(optimization.get("component_scores") or {}),
            "metrics": dict(optimization.get("metrics") or {}),
            "recommendations": list(optimization.get("recommendations") or []),
            "comparison_summary": dict(optimization.get("comparison_summary") or metadata.get("comparison_summary") or {}),
        },
        "reliability_summary": {
            "release_ready": release_ready,
            "retryable": retryable,
            "operational_state": "ready" if release_ready else ("retryable" if retryable else "review"),
            "persistence_scope": persistence_scope,
            "project_bound": bool(project_id),
            "job_bound": bool(job_id),
            "primary_attention": str(primary_attention or ""),
            "blocked_export_count": len(blocked_exports),
            "failed_deliverable_count": len(failed_deliverables),
            "manual_failure_count": len(manual_failures),
            "unresolved_conflict_count": unresolved_conflict_count,
            "trace": {
                "run_id": run_id,
                "project_id": project_id,
                "job_id": job_id,
                "source": source,
                "created_at": created_at,
            },
        },
        "warning_count": warning_count,
        "error_count": error_count,
    }


def final_plan_from_result(
    result_data: Dict[str, Any],
    *,
    enforce_export_guards: bool = True,
) -> Dict[str, Any]:
    def _normalized_reasons(value: Any, fallback: str) -> List[str]:
        reasons = [str(item) for item in list(value or []) if str(item)]
        deduped = list(dict.fromkeys(reasons))
        return deduped or [fallback]

    final_plan = dict(result_data.get("final_plan") or result_data)
    actions = final_plan.get("actions")
    if isinstance(actions, list) and actions:
        meta = dict(final_plan.get("meta") or {})
        grading = dict(meta.get("grading") or {})
        drainage = dict(meta.get("drainage") or {})
        storm = dict(meta.get("storm_pipes") or {})
        utilities = dict(meta.get("utilities") or {})
        deliverables = dict(meta.get("deliverables") or {})
        if enforce_export_guards and final_plan_requires_construction_release(final_plan):
            construction_blockers = construction_release_blockers_from_meta(
                meta,
                requires_construction_release=True,
            )
            if construction_blockers:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Export is blocked because construction release evidence is incomplete: "
                        + ", ".join(construction_blockers)
                    ),
                )
        produced = {str(item).lower() for item in list(deliverables.get("produced") or [])}
        requested = {str(item).lower() for item in list(deliverables.get("requested") or [])}
        engineering_layers = {
            str(dict(action).get("layer") or "").upper()
            for action in actions
            if isinstance(action, dict)
        }
        grading_layers_present = bool(engineering_layers.intersection({"FG_CONTOUR", "SPOT_FG", "DRAIN_FLOW"}))
        needs_grading_truth = bool(
            grading_layers_present
            or any(any(token in item for token in ("grading", "contour", "spot_grade")) for item in produced | requested)
        )
        grading_export = dict(grading.get("export_validation") or {})
        grading_ready = bool(grading_export.get("ready"))
        grading_reasons = _normalized_reasons(grading_export.get("reasons"), "grading_export_not_ready")
        grading_deliverables_present = bool(
            produced.intersection({"grading_plan", "contours", "spot_grades", "flow_arrows"})
            or requested.intersection({"grading_plan", "contours", "spot_grades", "flow_arrows"})
        )
        if (
            not grading_ready
            and (grading_layers_present or grading_deliverables_present)
            and grading_reasons == ["grading_export_not_ready"]
        ):
            grading_ready = True
        needs_storm_truth = bool(
            engineering_layers.intersection({"PIPE", "DRAIN", "BASIN_BOUNDARY", "STRUCTURE"})
            or any(any(token in item for token in ("storm", "drain", "basin", "inlet")) for item in produced | requested)
        )
        if enforce_export_guards and needs_grading_truth and not grading_ready:
            reasons = grading_reasons
            raise HTTPException(
                status_code=409,
                detail=(
                    "Export is blocked because the grading design has not reached a stable engineered surface state yet: "
                    + ", ".join(reasons)
                ),
            )
        needs_utility_truth = bool(
            engineering_layers.intersection({"UTILITY", "WATER"})
            or any(any(token in item for token in ("utility", "utilities", "water")) for item in produced | requested)
        )
        utility_export = dict(utilities.get("export_validation") or {})
        utility_ready = bool(utility_export.get("ready"))
        utility_reasons = _normalized_reasons(
            utility_export.get("reasons"),
            "utility_export_not_ready",
        )
        if enforce_export_guards and needs_utility_truth and not utility_ready:
            reasons = utility_reasons
            raise HTTPException(
                status_code=409,
                detail=(
                    "Export is blocked because the utility design has not reached a stable engineered network state yet: "
                    + ", ".join(reasons)
                ),
            )
        drainage_export = dict(drainage.get("export_validation") or {})
        storm_export = dict(storm.get("export_validation") or {})
        drainage_ready = bool(drainage_export.get("ready"))
        drainage_reasons = _normalized_reasons(
            drainage_export.get("reasons"),
            "storm_export_not_ready",
        )
        storm_ready = bool(storm_export.get("ready"))
        if not storm_ready:
            from backend.planning.export_validation import storm_summary_is_exportable

            persisted_segments = [
                dict(item)
                for item in list(
                    storm.get("storm_pipe_segments")
                    or storm.get("pipe_segments")
                    or storm.get("segments")
                    or []
                )
                if isinstance(item, dict)
            ]
            storm_ready = storm_summary_is_exportable({**storm, "segments": persisted_segments})
        storm_only_drainage_reasons = {
            "storm_network_missing",
            "storm_graph_invalid",
            "storm_hydraulics_invalid",
            "storm_segments_incomplete",
            "storm_fallback_used",
        }
        if (
            not drainage_ready
            and storm_ready
            and drainage_reasons
            and set(drainage_reasons).issubset(storm_only_drainage_reasons)
        ):
            drainage_ready = True
        if enforce_export_guards and needs_storm_truth and (not drainage_ready or not storm_ready):
            reasons = list(drainage_export.get("reasons") or [])
            if storm_export:
                reasons.extend(str(item) for item in list(storm_export.get("reasons") or []) if str(item))
            else:
                if not bool(dict(storm.get("graph_validation") or {}).get("valid", False)):
                    reasons.append("storm_graph_invalid")
                if not bool(dict(storm.get("hydraulic_validation") or {}).get("valid", False)):
                    reasons.append("storm_hydraulics_invalid")
                if list(storm.get("missing_data_segments") or []):
                    reasons.append("storm_segments_incomplete")
            reasons = _normalized_reasons(reasons, "storm_export_not_ready")
            raise HTTPException(
                status_code=409,
                detail=(
                    "Export is blocked because the engineering design has not reached a stable drainage/storm state yet: "
                    + ", ".join(reasons)
                ),
            )
        return final_plan

    raise HTTPException(
        status_code=409,
        detail="No stable engineered plan actions are available yet. Complete the engineering run before preview or export.",
    )
