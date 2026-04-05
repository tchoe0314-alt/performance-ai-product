from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException


def now_ts() -> float:
    return time.time()


def new_workflow_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def run_orchestration(
    payload_data: Dict[str, Any],
    *,
    load_orchestrator: Callable[[], tuple[Any, Any]],
    assess_design_readiness: Callable[[str, Optional[Dict[str, Any]]], Optional[Dict[str, Any]]],
) -> Dict[str, Any]:
    PlannerOrchestratorRequest, orchestrate_plan = load_orchestrator()

    req = PlannerOrchestratorRequest(
        input_mode=payload_data.get("input_mode", "assisted"),
        strict_mode=bool(payload_data.get("strict_mode", False)),
        prompt_text=payload_data.get("prompt_text"),
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
    )

    if str(req.input_mode or "assisted").strip().lower() == "manual" and str(req.prompt_text or "").strip():
        readiness_issue = assess_design_readiness(
            str(req.prompt_text),
            {
                "strategy_mode": "manual",
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
            return {
                "success": False,
                "message": str(readiness_issue.get("assistant_message") or "Manual mode needs more information before design can start."),
                "parsed_payload": dict(payload_data),
                "final_plan": {},
                "warnings": [],
                "errors": [str(readiness_issue.get("reason") or "Minimum engineering design context is incomplete")],
                "issues": [],
                "assumptions": [],
                "metadata": {
                    "_workflow_run_id": new_workflow_id("run"),
                    "input_mode": payload_data.get("input_mode", "manual"),
                    "needs_clarification": True,
                    "clarification_reason": readiness_issue.get("reason"),
                    "missing_requirements": list(readiness_issue.get("missing_requirements") or []),
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
    optimization = dict(plan_meta.get("optimization_summary") or {})
    run_id = metadata.get("_workflow_run_id") or new_workflow_id("run")
    created_at = now_ts()
    blocked_exports = list(convergence.get("blocked_exports") or [])
    blocked_reasons = list(convergence.get("blocked_reasons") or [])
    unresolved_conflict_count = int(convergence.get("unresolved_conflict_count") or 0)
    failed_deliverables = list(deliverables.get("failed") or [])
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
    release_ready = success and converged and unresolved_conflict_count == 0 and not blocked_exports and not blocked_reasons and not failed_deliverables
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

    return {
        "run_id": run_id,
        "project_id": project_id,
        "job_id": job_id,
        "source": source,
        "created_at": created_at,
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
        "requested_deliverables": list(deliverables.get("requested") or []),
        "produced_deliverables": list(deliverables.get("produced") or []),
        "failed_deliverables": failed_deliverables,
        "manual_failures": manual_failures,
        "stage_summary": {
            "all_required_complete": bool(stage_completeness.get("all_required_complete")),
            "required_stage_count": int(stage_completeness.get("required_stage_count") or 0),
            "complete_stage_count": int(stage_completeness.get("complete_stage_count") or 0),
            "statuses": dict(stage_completeness.get("statuses") or {}),
        },
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
            "assumption_summary": dict(convergence.get("assumption_summary") or {}),
            "unresolved_issue_categories": list(convergence.get("unresolved_issue_categories") or []),
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


def final_plan_from_result(result_data: Dict[str, Any]) -> Dict[str, Any]:
    final_plan = dict(result_data.get("final_plan") or result_data)
    actions = final_plan.get("actions")
    if isinstance(actions, list) and actions:
        meta = dict(final_plan.get("meta") or {})
        grading = dict(meta.get("grading") or {})
        drainage = dict(meta.get("drainage") or {})
        storm = dict(meta.get("storm_pipes") or {})
        utilities = dict(meta.get("utilities") or {})
        deliverables = dict(meta.get("deliverables") or {})
        produced = {str(item).lower() for item in list(deliverables.get("produced") or [])}
        requested = {str(item).lower() for item in list(deliverables.get("requested") or [])}
        engineering_layers = {
            str(dict(action).get("layer") or "").upper()
            for action in actions
            if isinstance(action, dict)
        }
        needs_grading_truth = bool(
            engineering_layers.intersection({"FG_CONTOUR", "SPOT_FG"})
            or any(any(token in item for token in ("grading", "contour", "spot_grade")) for item in produced | requested)
        )
        grading_export = dict(grading.get("export_validation") or {})
        needs_storm_truth = bool(
            engineering_layers.intersection({"PIPE", "DRAIN", "BASIN_BOUNDARY", "STRUCTURE"})
            or any(any(token in item for token in ("storm", "drain", "basin", "inlet")) for item in produced | requested)
        )
        if needs_grading_truth and not bool(grading_export.get("ready")):
            reasons = list(dict.fromkeys([str(item) for item in list(grading_export.get("reasons") or []) if str(item)]))
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
        if needs_utility_truth and not bool(utility_export.get("ready")):
            reasons = list(dict.fromkeys([str(item) for item in list(utility_export.get("reasons") or []) if str(item)]))
            raise HTTPException(
                status_code=409,
                detail=(
                    "Export is blocked because the utility design has not reached a stable engineered network state yet: "
                    + ", ".join(reasons)
                ),
            )
        drainage_export = dict(drainage.get("export_validation") or {})
        storm_ready = bool(dict(storm.get("graph_validation") or {}).get("valid", False)) and bool(
            dict(storm.get("hydraulic_validation") or {}).get("valid", False)
        ) and not list(storm.get("missing_data_segments") or [])
        if needs_storm_truth and (not bool(drainage_export.get("ready")) or not storm_ready):
            reasons = list(drainage_export.get("reasons") or [])
            if not bool(dict(storm.get("graph_validation") or {}).get("valid", False)):
                reasons.append("storm_graph_invalid")
            if not bool(dict(storm.get("hydraulic_validation") or {}).get("valid", False)):
                reasons.append("storm_hydraulics_invalid")
            if list(storm.get("missing_data_segments") or []):
                reasons.append("storm_segments_incomplete")
            reasons = list(dict.fromkeys([str(item) for item in reasons if str(item)]))
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
