from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Protocol

from fastapi import HTTPException

from backend.application.design_workflows import (
    new_workflow_id,
    now_ts,
)
from backend.planning.common import blocker_explanations, construction_package_record, safe_dict
from backend.planning.candidate_review_inbox import (
    apply_candidate_review_decision,
    build_candidate_review_inbox,
)
from backend.planning.cad_entity_model import attach_cad_entity_model_to_result
from backend.planning.design_alternatives import (
    ALTERNATIVES_VERSION,
    append_revised_design_alternative,
    build_design_alternatives,
    compare_design_alternatives,
    select_design_alternative,
)
from backend.planning.progress_timeline import build_progress_timeline
from backend.planning.review_issue_tracker import build_review_issue_tracker
from backend.planning.release_gates import (
    construction_release_blockers_from_meta,
    final_plan_requires_construction_release,
)
from backend.planning.source_confidence_map import (
    attach_source_confidence_map,
    build_source_confidence_map,
)
from backend.planning.smart_fix import build_smart_fix_recommendations
from backend.planning.vision_detection_learning import (
    DATASET_VERSION as VISION_DATASET_VERSION,
    QUALITY_VERSION as VISION_QUALITY_VERSION,
    build_vision_learning_package,
)
from backend.application.protocols import ArtifactServiceProtocol
from backend.application.job_workflows import JobQueueProtocol

PROJECT_VERSION_HISTORY_VERSION = "project_version_history_v1"


class ProjectStoreProtocol(Protocol):
    def list_projects(self, *, user_id: str) -> list[Dict[str, Any]]:
        ...

    def get_project(self, *, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        ...

    def get_project_shell(self, *, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        ...

    def get_project_latest_result(self, *, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        ...

    def update_project_candidate_review_state(
        self,
        *,
        user_id: str,
        project_id: str,
        candidate_state: Dict[str, Any],
        minimum_role: str = "reviewer",
    ) -> Dict[str, Any]:
        ...

    def save_project_shell(
        self,
        *,
        user_id: str,
        project_id: str,
        name: str,
        description: str,
        session_id: Optional[str],
        tags: list[str],
        project_input: Dict[str, Any],
        session_state: Dict[str, Any],
        metadata: Dict[str, Any],
        organization_id: Optional[str] = None,
        minimum_role: str = "editor",
    ) -> Dict[str, Any]:
        ...

    def save_project(
        self,
        *,
        user_id: str,
        project_id: str,
        name: str,
        description: str,
        session_id: Optional[str],
        tags: list[str],
        project_input: Dict[str, Any],
        latest_result: Dict[str, Any],
        session_state: Dict[str, Any],
        metadata: Dict[str, Any],
        organization_id: Optional[str] = None,
        minimum_role: str = "editor",
    ) -> Dict[str, Any]:
        ...

    def delete_project(self, *, user_id: str, project_id: str) -> bool:
        ...


def _merge_project_input_value(existing: Any, incoming: Any) -> Any:
    if incoming is None:
        return existing
    if isinstance(existing, dict) and isinstance(incoming, dict):
        return _merge_project_input(existing, incoming)
    if isinstance(existing, list) and isinstance(incoming, list):
        return incoming if incoming else existing
    if isinstance(existing, str) and isinstance(incoming, str):
        return incoming if incoming.strip() else existing
    if (
        isinstance(existing, (int, float))
        and isinstance(incoming, (int, float))
        and not isinstance(existing, bool)
        and not isinstance(incoming, bool)
    ):
        if incoming != 0:
            return incoming
        return existing if existing not in (0, 0.0) else incoming
    return incoming


def _merge_project_input(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    if not existing:
        return dict(incoming or {})
    if not incoming:
        return dict(existing or {})
    merged: Dict[str, Any] = {}
    for key in set(existing.keys()) | set(incoming.keys()):
        if key not in incoming:
            merged[key] = existing[key]
        elif key not in existing:
            merged[key] = incoming[key]
        else:
            merged[key] = _merge_project_input_value(existing[key], incoming[key])
    return merged


def result_from_payload(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: Optional[str],
    result: Optional[Dict[str, Any]] = None,
    final_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if project_id:
        project = project_store.get_project(user_id=user_id, project_id=project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        result_data = dict(project.get("latest_result") or {})
        if not result_data:
            raise HTTPException(status_code=400, detail="Selected project has no saved planner result.")
        return result_data

    if result:
        return dict(result)

    if final_plan:
        return {"final_plan": dict(final_plan)}

    raise HTTPException(status_code=400, detail="No plan or result payload was provided.")


def _build_workflow_summary(
    *,
    runs: list[Dict[str, Any]],
    artifacts: list[Dict[str, Any]],
) -> Dict[str, Any]:
    latest_run = dict(runs[0]) if runs else {}
    latest_reliability = dict(latest_run.get("reliability_summary") or {})
    latest_convergence = dict(latest_run.get("convergence_summary") or {})
    latest_artifact = dict(artifacts[0]) if artifacts else {}
    latest_blockers = _latest_release_blockers(
        latest_run=latest_run,
        latest_reliability=latest_reliability,
        latest_convergence=latest_convergence,
        latest_artifact=latest_artifact,
    )
    latest_artifact_blockers = list(latest_artifact.get("release_blockers") or [])
    latest_artifact_status = str(latest_artifact.get("release_status") or "")
    latest_artifact_release_ready = bool(latest_artifact.get("release_ready")) and not latest_artifact_blockers
    if latest_artifact_status.lower() == "blocked":
        latest_artifact_release_ready = False
    latest_release_ready = bool(latest_reliability.get("release_ready")) and not latest_blockers
    latest_private_alpha = _compact_private_alpha_readiness(
        latest_run.get("private_alpha_readiness")
        or latest_reliability.get("private_alpha_readiness")
        or latest_artifact.get("private_alpha_readiness")
    )
    return {
        "run_count": len(runs),
        "artifact_count": len(artifacts),
        "latest_run_id": str(latest_run.get("run_id") or ""),
        "latest_run_created_at": latest_run.get("created_at"),
        "latest_run_source": str(latest_run.get("source") or ""),
        "latest_operational_state": str(latest_reliability.get("operational_state") or ""),
        "latest_primary_attention": str(latest_reliability.get("primary_attention") or ""),
        "latest_blocked_export_count": int(latest_reliability.get("blocked_export_count") or 0),
        "latest_unresolved_conflict_count": int(latest_reliability.get("unresolved_conflict_count") or 0),
        "latest_failed_deliverable_count": int(latest_reliability.get("failed_deliverable_count") or 0),
        "latest_converged": bool(latest_convergence.get("converged")),
        "latest_release_ready": latest_release_ready,
        "latest_release_blockers": latest_blockers,
        "latest_release_blocker_details": blocker_explanations(latest_blockers),
        "latest_artifact_id": str(latest_artifact.get("artifact_id") or ""),
        "latest_artifact_kind": str(latest_artifact.get("kind") or ""),
        "latest_artifact_created_at": latest_artifact.get("created_at"),
        "latest_artifact_release_status": latest_artifact_status,
        "latest_artifact_release_ready": latest_artifact_release_ready,
        "latest_artifact_release_blockers": latest_artifact_blockers,
        "latest_artifact_release_blocker_details": blocker_explanations(latest_artifact_blockers),
        "latest_artifact_model_reference": dict(latest_artifact.get("canonical_model_reference") or {}),
        "latest_private_alpha_readiness": latest_private_alpha,
        "latest_private_alpha_status": str(latest_private_alpha.get("status") or ""),
        "latest_private_alpha_ready": bool(latest_private_alpha.get("full_system_private_alpha_ready")),
        "latest_private_alpha_blocker_count": int(latest_private_alpha.get("blocker_count") or 0),
    }


def _compact_private_alpha_readiness(value: Any) -> Dict[str, Any]:
    rec = dict(value or {}) if isinstance(value, dict) else {}
    if not rec:
        return {}
    return {
        "status": str(rec.get("status") or ""),
        "full_system_private_alpha_ready": bool(rec.get("full_system_private_alpha_ready")),
        "review_only": bool(rec.get("review_only")),
        "construction_release_blocked": bool(rec.get("construction_release_blocked")),
        "construction_release_allowed": bool(rec.get("construction_release_allowed")),
        "blocker_count": int(rec.get("blocker_count") or 0),
        "warning_count": int(rec.get("warning_count") or 0),
        "launch_recommendation": str(rec.get("launch_recommendation") or ""),
        "primary_next_action": str((list(rec.get("next_actions") or [])[:1] or [""])[0]),
    }


def _latest_release_blockers(
    *,
    latest_run: Dict[str, Any],
    latest_reliability: Dict[str, Any],
    latest_convergence: Dict[str, Any],
    latest_artifact: Optional[Dict[str, Any]] = None,
) -> list[str]:
    blockers: list[str] = []

    def _manual_failure_blocker(value: Any) -> str:
        if isinstance(value, dict):
            text = str(
                value.get("code")
                or value.get("rule")
                or value.get("system")
                or value.get("reason")
                or value.get("message")
                or "manual_validation_failure"
            ).strip()
        else:
            text = str(value).strip()
        if not text:
            text = "manual_validation_failure"
        normalized = text.lower().replace(" ", "_")
        if normalized.startswith("manual_validation_"):
            return normalized
        return f"manual_validation_{normalized}"

    def _extend(values: Any) -> None:
        for value in list(values or []):
            if isinstance(value, dict):
                text = str(value.get("code") or value.get("reason") or value.get("message") or "").strip()
            else:
                text = str(value).strip()
            if text and text not in blockers:
                blockers.append(text)

    _extend(latest_convergence.get("blocked_reasons"))
    _extend(latest_convergence.get("blocked_exports"))
    deliverables = dict(latest_run.get("deliverables") or {})
    failed_deliverables = list(latest_run.get("failed_deliverables") or []) + list(deliverables.get("failed") or [])
    for failed in failed_deliverables:
        failed_name = str(failed).strip()
        if not failed_name:
            continue
        blocker = f"failed_deliverable_{failed_name.lower().replace(' ', '_')}"
        if blocker not in blockers:
            blockers.append(blocker)
    requested_deliverables = list(latest_run.get("requested_deliverables") or []) + list(deliverables.get("requested") or [])
    produced_set = {
        str(item).strip()
        for item in list(latest_run.get("produced_deliverables") or []) + list(deliverables.get("produced") or [])
        if str(item).strip()
    }
    failed_set = {str(item).strip() for item in failed_deliverables if str(item).strip()}
    missing_deliverables = list(latest_run.get("missing_deliverables") or []) + list(deliverables.get("missing") or [])
    missing_deliverables.extend(
        str(item).strip()
        for item in requested_deliverables
        if str(item).strip() and str(item).strip() not in produced_set and str(item).strip() not in failed_set
    )
    for missing in list(dict.fromkeys(str(item).strip() for item in missing_deliverables if str(item).strip())):
        missing_name = str(missing).strip()
        if not missing_name:
            continue
        blocker = f"missing_deliverable_{missing_name.lower().replace(' ', '_')}"
        if blocker not in blockers:
            blockers.append(blocker)
    for manual_failure in list(latest_run.get("manual_failures") or []):
        blocker = _manual_failure_blocker(manual_failure)
        if blocker and blocker not in blockers:
            blockers.append(blocker)
    latest_run_release_review = dict(latest_run.get("release_review") or {})
    latest_run_release_status = str(
        latest_run_release_review.get("release_status") or latest_run.get("release_status") or ""
    ).lower()
    if latest_run_release_status == "blocked":
        blockers.append("latest_run_release_status_blocked")
    if latest_run_release_review.get("release_ready") is False or latest_run.get("release_ready") is False:
        blockers.append("latest_run_release_not_ready")
    _extend(latest_run_release_review.get("blocked_reasons"))
    _extend(latest_run_release_review.get("blocked_exports"))
    artifact = dict(latest_artifact or {})
    _extend(artifact.get("release_blockers"))

    if int(latest_reliability.get("blocked_export_count") or 0) > 0:
        blockers.append("blocked_exports")
    if int(latest_reliability.get("unresolved_conflict_count") or 0) > 0:
        blockers.append("unresolved_conflicts")
    if int(latest_reliability.get("failed_deliverable_count") or 0) > 0:
        blockers.append("failed_deliverables")
    if int(latest_reliability.get("missing_deliverable_count") or 0) > 0:
        blockers.append("missing_deliverables")
    if int(latest_reliability.get("manual_failure_count") or 0) > 0:
        blockers.append("manual_validation_failures")
    if latest_run.get("success") is False:
        blockers.append("planner_run_failed")
    if int(latest_run.get("error_count") or 0) > 0:
        blockers.append("planner_errors_present")
    if latest_reliability.get("release_ready") is False:
        blockers.append("latest_run_release_not_ready")
    if latest_run.get("final_plan_release_ready") is False:
        blockers.append("final_plan_release_blocked")
    if str(artifact.get("release_status") or "").lower() == "blocked":
        blockers.append("latest_artifact_release_blocked")
    return list(dict.fromkeys(blockers))


def _project_operational_summary(record: Dict[str, Any]) -> Dict[str, Any]:
    workflow_summary = dict(dict(record.get("metadata") or {}).get("workflow", {}).get("summary") or {})
    private_alpha = dict(workflow_summary.get("latest_private_alpha_readiness") or {})
    return {
        "operational_state": str(workflow_summary.get("latest_operational_state") or ""),
        "primary_attention": str(workflow_summary.get("latest_primary_attention") or ""),
        "release_ready": bool(workflow_summary.get("latest_release_ready")),
        "release_blockers": list(workflow_summary.get("latest_release_blockers") or []),
        "run_count": int(workflow_summary.get("run_count") or 0),
        "artifact_count": int(workflow_summary.get("artifact_count") or 0),
        "latest_run_id": str(workflow_summary.get("latest_run_id") or ""),
        "latest_artifact_id": str(workflow_summary.get("latest_artifact_id") or ""),
        "latest_artifact_release_status": str(workflow_summary.get("latest_artifact_release_status") or ""),
        "latest_artifact_release_ready": bool(workflow_summary.get("latest_artifact_release_ready")),
        "private_alpha_readiness": private_alpha,
        "private_alpha_status": str(private_alpha.get("status") or ""),
        "private_alpha_ready": bool(private_alpha.get("full_system_private_alpha_ready")),
        "private_alpha_blocker_count": int(private_alpha.get("blocker_count") or 0),
    }


def _compact_phase_status(phase_checkpoints: Dict[str, Any]) -> Dict[str, Any]:
    compact: Dict[str, Any] = {}
    for phase_name, phase in dict(phase_checkpoints or {}).items():
        if not isinstance(phase, dict):
            continue
        compact[str(phase_name)] = {
            "status": str(phase.get("status") or ""),
            "ready": bool(phase.get("ready")),
            "label": str(phase.get("label") or phase_name),
            "blocked_reasons": list(phase.get("blocked_reasons") or phase.get("blockers") or []),
            "blocked_exports": list(phase.get("blocked_exports") or []),
            "deliverables_ready": list(phase.get("deliverables_ready") or []),
            "completed_phase_count": phase.get("completed_phase_count"),
            "total_phase_count": phase.get("total_phase_count"),
        }
    return compact


def _compact_run_for_dashboard(run: Dict[str, Any]) -> Dict[str, Any]:
    reliability = dict(run.get("reliability_summary") or {})
    convergence = dict(run.get("convergence_summary") or {})
    phase_checkpoints = dict(run.get("phase_checkpoints") or {})
    deliverables = {
        "requested": list(run.get("requested_deliverables") or []),
        "produced": list(run.get("produced_deliverables") or []),
        "ready": list(run.get("ready_deliverables") or []),
        "failed": list(run.get("failed_deliverables") or []),
        "missing": list(run.get("missing_deliverables") or []),
        "extra": list(run.get("extra_deliverables") or []),
    }
    return {
        "run_id": str(run.get("run_id") or ""),
        "job_id": str(run.get("job_id") or ""),
        "source": str(run.get("source") or ""),
        "created_at": run.get("created_at"),
        "success": bool(run.get("success")),
        "message": str(run.get("message") or ""),
        "operational_state": str(reliability.get("operational_state") or ""),
        "release_ready": bool(reliability.get("release_ready")),
        "retryable": bool(reliability.get("retryable")),
        "primary_attention": str(reliability.get("primary_attention") or ""),
        "release_blocker_details": list(reliability.get("release_blocker_details") or []),
        "private_alpha_readiness": _compact_private_alpha_readiness(
            run.get("private_alpha_readiness") or reliability.get("private_alpha_readiness")
        ),
        "blocked_exports": list(convergence.get("blocked_exports") or []),
        "blocked_reasons": list(convergence.get("blocked_reasons") or []),
        "unresolved_conflict_count": int(
            reliability.get("unresolved_conflict_count")
            or convergence.get("unresolved_conflict_count")
            or 0
        ),
        "manual_failure_count": int(reliability.get("manual_failure_count") or 0),
        "failed_deliverable_count": int(reliability.get("failed_deliverable_count") or len(deliverables["failed"])),
        "missing_deliverable_count": int(reliability.get("missing_deliverable_count") or len(deliverables["missing"])),
        "assumption_summary": dict(convergence.get("assumption_summary") or {}),
        "manual_failures": list(run.get("manual_failures") or []),
        "deliverables": deliverables,
        "phase_checkpoints": _compact_phase_status(phase_checkpoints),
        "combined_view": dict(_compact_phase_status(phase_checkpoints).get("combined_view") or {}),
    }


def _compact_artifact_for_dashboard(artifact: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "artifact_id": str(artifact.get("artifact_id") or ""),
        "kind": str(artifact.get("kind") or ""),
        "filename": str(artifact.get("filename") or ""),
        "created_at": artifact.get("created_at"),
        "download_path": str(artifact.get("download_path") or ""),
        "release_status": str(artifact.get("release_status") or ""),
        "release_ready": bool(artifact.get("release_ready")),
        "release_blockers": list(artifact.get("release_blockers") or []),
        "release_blocker_details": list(artifact.get("release_blocker_details") or []),
        "canonical_model_reference": dict(artifact.get("canonical_model_reference") or {}),
        "construction_package_id": str(artifact.get("construction_package_id") or ""),
        "private_alpha_readiness": _compact_private_alpha_readiness(artifact.get("private_alpha_readiness")),
    }


def build_workflow_review_dashboard(*, runs: list[Dict[str, Any]], artifacts: list[Dict[str, Any]]) -> Dict[str, Any]:
    summary = _build_workflow_summary(runs=runs, artifacts=artifacts)
    latest_run = _compact_run_for_dashboard(dict(runs[0])) if runs else {}
    latest_artifact = _compact_artifact_for_dashboard(dict(artifacts[0])) if artifacts else {}
    latest_deliverables = dict(latest_run.get("deliverables") or {})
    latest_assumptions = dict(latest_run.get("assumption_summary") or {})
    latest_blockers = list(summary.get("latest_release_blockers") or [])
    return {
        "version": "workflow_review_dashboard_v1",
        "summary": summary,
        "release_ready": bool(summary.get("latest_release_ready")),
        "operational_state": str(summary.get("latest_operational_state") or ""),
        "primary_attention": str(summary.get("latest_primary_attention") or ""),
        "release_blockers": latest_blockers,
        "release_blocker_details": list(summary.get("latest_release_blocker_details") or []),
        "private_alpha_readiness": dict(summary.get("latest_private_alpha_readiness") or {}),
        "run_count": len(runs),
        "artifact_count": len(artifacts),
        "latest_run": latest_run,
        "latest_artifact": latest_artifact,
        "recent_runs": [_compact_run_for_dashboard(dict(item)) for item in runs[:5]],
        "recent_artifacts": [_compact_artifact_for_dashboard(dict(item)) for item in artifacts[:8]],
        "phase_checkpoints": dict(latest_run.get("phase_checkpoints") or {}),
        "combined_view": dict(latest_run.get("combined_view") or {}),
        "deliverable_manager": {
            "requested": list(latest_deliverables.get("requested") or []),
            "produced": list(latest_deliverables.get("produced") or []),
            "ready": list(latest_deliverables.get("ready") or []),
            "failed": list(latest_deliverables.get("failed") or []),
            "missing": list(latest_deliverables.get("missing") or []),
            "extra": list(latest_deliverables.get("extra") or []),
            "latest_artifact_release_ready": bool(summary.get("latest_artifact_release_ready")),
            "latest_artifact_release_status": str(summary.get("latest_artifact_release_status") or ""),
            "latest_artifact_release_blockers": list(summary.get("latest_artifact_release_blockers") or []),
        },
        "assumption_review": {
            "summary": latest_assumptions,
            "requires_approval": bool(latest_assumptions),
            "examples": list(latest_assumptions.get("examples") or []),
        },
        "conflict_review": {
            "unresolved_conflict_count": int(summary.get("latest_unresolved_conflict_count") or 0),
            "blocked_exports": int(summary.get("latest_blocked_export_count") or 0),
            "primary_attention": str(summary.get("latest_primary_attention") or ""),
        },
    }


def _stable_json(value: Any) -> str:
    import json

    try:
        return json.dumps(value, sort_keys=True, default=str)
    except Exception:
        return str(value)


def _walk_records(value: Any, *, limit: int = 250) -> list[Dict[str, Any]]:
    records: list[Dict[str, Any]] = []

    def visit(item: Any, path: str) -> None:
        if len(records) >= limit:
            return
        if isinstance(item, dict):
            object_id = str(
                item.get("object_id")
                or item.get("canonical_id")
                or item.get("id")
                or item.get("pipe_id")
                or item.get("structure_id")
                or ""
            ).strip()
            if object_id:
                records.append({"object_id": object_id, "path": path, "fingerprint": _stable_json(item)})
            for key, child in item.items():
                if key in {"meta", "metadata", "source_record", "history", "comments"}:
                    continue
                visit(child, f"{path}.{key}" if path else str(key))
        elif isinstance(item, list):
            for index, child in enumerate(item[:limit]):
                visit(child, f"{path}[{index}]")

    visit(value, "")
    deduped: Dict[str, Dict[str, Any]] = {}
    for record in records:
        deduped.setdefault(record["object_id"], record)
    return list(deduped.values())[:limit]


def _quantity_snapshot(meta: Dict[str, Any]) -> Dict[str, Any]:
    quantities: Dict[str, Any] = {}
    for source_key in ("quantity_takeoff_review_report_v1", "quantity_explain", "quantity_audit", "quantities"):
        source = meta.get(source_key)
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                quantities[str(key)] = value
            elif isinstance(value, dict):
                for subkey in ("quantity", "current_quantity", "total", "value", "amount"):
                    if isinstance(value.get(subkey), (int, float)) and not isinstance(value.get(subkey), bool):
                        quantities[f"{key}.{subkey}"] = value[subkey]
                        break
    return quantities


def _blocker_snapshot(meta: Dict[str, Any]) -> list[str]:
    tracker = dict(meta.get("review_issue_tracker_v1") or {})
    blocker_values = [
        str(item.get("issue_id") or item.get("title") or "")
        for item in list(tracker.get("open_issues") or tracker.get("issues") or [])
        if isinstance(item, dict) and str(item.get("status") or "open") in {"open", "in_review", "reopened"}
    ]
    for source_key in ("blockers", "release_blockers"):
        blocker_values.extend(str(item) for item in list(meta.get(source_key) or []) if str(item))
    return list(dict.fromkeys(item for item in blocker_values if item))


def project_version_snapshot(
    latest_result: Dict[str, Any],
    *,
    revision_id: str,
    created_at: Any,
    reason: str,
) -> Dict[str, Any]:
    final_plan = dict(latest_result.get("final_plan") or {})
    meta = dict(final_plan.get("meta") or {})
    objects = _walk_records(final_plan)
    return {
        "revision_id": revision_id,
        "created_at": created_at,
        "reason": reason,
        "object_count": len(objects),
        "objects": objects,
        "blockers": _blocker_snapshot(meta),
        "quantities": _quantity_snapshot(meta),
        "review_package_ids": [
            str(value)
            for value in (
                dict(meta.get("engineer_review_package_v1") or {}).get("package_id"),
                dict(meta.get("review_package_manifest") or {}).get("manifest_id"),
            )
            if value
        ],
        "truth_label": "Project versions are workflow snapshots for comparison and audit; they are not engineering approval records.",
    }


def compare_project_versions(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    before_objects = {str(item.get("object_id")): item for item in list(before.get("objects") or []) if isinstance(item, dict)}
    after_objects = {str(item.get("object_id")): item for item in list(after.get("objects") or []) if isinstance(item, dict)}
    before_ids = set(before_objects)
    after_ids = set(after_objects)
    changed = [
        object_id
        for object_id in sorted(before_ids & after_ids)
        if str(before_objects[object_id].get("fingerprint")) != str(after_objects[object_id].get("fingerprint"))
    ]
    before_blockers = set(str(item) for item in list(before.get("blockers") or []))
    after_blockers = set(str(item) for item in list(after.get("blockers") or []))
    before_quantities = dict(before.get("quantities") or {})
    after_quantities = dict(after.get("quantities") or {})
    quantity_changes = []
    for key in sorted(set(before_quantities) | set(after_quantities)):
        if before_quantities.get(key) != after_quantities.get(key):
            quantity_changes.append({"key": key, "before": before_quantities.get(key), "after": after_quantities.get(key)})
    return {
        "version": "project_version_comparison_v1",
        "from_revision_id": str(before.get("revision_id") or ""),
        "to_revision_id": str(after.get("revision_id") or ""),
        "added_objects": sorted(after_ids - before_ids),
        "removed_objects": sorted(before_ids - after_ids),
        "changed_objects": changed,
        "added_blockers": sorted(after_blockers - before_blockers),
        "removed_blockers": sorted(before_blockers - after_blockers),
        "changed_quantities": quantity_changes,
        "truth_label": "Version comparison is an audit/workflow aid only and does not certify, seal, stamp, or approve construction documents.",
    }


def update_project_version_history(
    metadata: Dict[str, Any],
    latest_result: Dict[str, Any],
    *,
    reason: str,
    artifact_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not dict(latest_result.get("final_plan") or {}):
        return metadata
    workflow = dict(metadata.get("workflow") or {})
    history = dict(workflow.get("version_history") or {})
    snapshots = [dict(item) for item in list(history.get("snapshots") or []) if isinstance(item, dict)]
    revision_id = f"rev_{len(snapshots) + 1}"
    snapshot = project_version_snapshot(latest_result, revision_id=revision_id, created_at=now_ts(), reason=reason)
    if snapshots and _stable_json({k: snapshot.get(k) for k in ("objects", "blockers", "quantities")}) == _stable_json(
        {k: snapshots[0].get(k) for k in ("objects", "blockers", "quantities")}
    ):
        return metadata
    snapshots.insert(0, snapshot)
    snapshots = snapshots[:20]
    latest_comparison = compare_project_versions(snapshots[1], snapshots[0]) if len(snapshots) >= 2 else {}
    package_history = [dict(item) for item in list(history.get("review_package_history") or []) if isinstance(item, dict)]
    if artifact_summary:
        artifact = dict(artifact_summary)
        artifact["revision_id"] = revision_id
        package_history.insert(0, artifact)
        package_history = package_history[:40]
    history = {
        "version": PROJECT_VERSION_HISTORY_VERSION,
        "latest_revision_id": revision_id,
        "snapshots": snapshots,
        "latest_comparison": latest_comparison,
        "review_package_history": package_history,
        "truth_label": "Snapshots and package history are workflow/audit records only; external stamps may be stored only as customer-provided metadata.",
    }
    workflow["version_history"] = history
    metadata["workflow"] = workflow
    return metadata


def _record_with_operational_summary(record: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(record)
    enriched["operational_summary"] = _project_operational_summary(record)
    return enriched


def _with_progress_timeline_result(
    latest_result: Dict[str, Any],
    *,
    project_input: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result = dict(latest_result or {})
    final_plan = dict(result.get("final_plan") or {})
    if not final_plan:
        return result
    meta = dict(final_plan.get("meta") or {})
    meta["progress_timeline_v1"] = build_progress_timeline(
        project_input=dict(project_input or {}),
        latest_result=result,
        context=dict(context or {}),
    )
    final_plan["meta"] = meta
    result["final_plan"] = final_plan
    return result


def merge_project_metadata(
    existing_metadata: Optional[Dict[str, Any]],
    *,
    run_summary: Optional[Dict[str, Any]] = None,
    artifact_summary: Optional[Dict[str, Any]] = None,
    latest_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = dict(existing_metadata or {})
    workflow = dict(metadata.get("workflow") or {})
    runs = [dict(item) for item in list(workflow.get("runs") or []) if isinstance(item, dict)]
    artifacts = [dict(item) for item in list(workflow.get("artifacts") or []) if isinstance(item, dict)]

    if run_summary:
        run_id = str(run_summary.get("run_id") or "")
        runs = [item for item in runs if str(item.get("run_id") or "") != run_id]
        runs.insert(0, dict(run_summary))
        runs = runs[:20]

    if artifact_summary:
        artifact_id = str(artifact_summary.get("artifact_id") or "")
        artifacts = [item for item in artifacts if str(item.get("artifact_id") or "") != artifact_id]
        artifacts.insert(0, dict(artifact_summary))
        artifacts = artifacts[:40]

    workflow["runs"] = runs
    workflow["artifacts"] = artifacts
    workflow["summary"] = _build_workflow_summary(runs=runs, artifacts=artifacts)
    workflow["review_dashboard"] = build_workflow_review_dashboard(runs=runs, artifacts=artifacts)
    metadata["workflow"] = workflow
    if latest_result:
        metadata = update_project_version_history(
            metadata,
            dict(latest_result),
            reason="artifact_generated" if artifact_summary else "planner_run",
            artifact_summary=artifact_summary,
        )
    return metadata


def save_project_workflow_update(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: str,
    run_summary: Optional[Dict[str, Any]] = None,
    artifact_summary: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    existing = project_store.get_project(user_id=user_id, project_id=project_id)
    if existing is None:
        return None
    metadata = merge_project_metadata(
        dict(existing.get("metadata") or {}),
        run_summary=run_summary,
        artifact_summary=artifact_summary,
        latest_result=dict(existing.get("latest_result") or {}),
    )
    return project_store.save_project(
        user_id=user_id,
        project_id=project_id,
        name=existing.get("name", "Untitled Project"),
        description=existing.get("description", ""),
        session_id=existing.get("session_id"),
        tags=existing.get("tags", []),
        project_input=existing.get("project_input", {}),
        latest_result=existing.get("latest_result", {}),
        session_state=existing.get("session_state", {}),
        metadata=metadata,
    )


def artifact_summary(
    *,
    path: Path,
    artifact_kind: str,
    project_id: Optional[str],
    result_data: Dict[str, Any],
) -> Dict[str, Any]:
    final_plan = dict(result_data.get("final_plan") or {})
    final_meta = dict(final_plan.get("meta") or {})
    if final_plan and "smart_fix_recommendations_v1" not in final_meta:
        final_meta["smart_fix_recommendations_v1"] = build_smart_fix_recommendations(final_plan, meta=final_meta)
        final_plan["meta"] = final_meta
        result_data["final_plan"] = final_plan
    if final_plan and "review_issue_tracker_v1" not in final_meta:
        final_meta["review_issue_tracker_v1"] = build_review_issue_tracker(final_plan, meta=final_meta)
        final_plan["meta"] = final_meta
        result_data["final_plan"] = final_plan
    request_metadata = dict(result_data.get("request_metadata") or {})
    release_review = dict(request_metadata.get("release_review") or final_meta.get("release_review") or {})
    blocked_reasons = [str(item) for item in list(release_review.get("blocked_reasons") or []) if str(item)]
    blocked_exports = [str(item) for item in list(release_review.get("blocked_exports") or []) if str(item)]
    release_blockers = list(dict.fromkeys(blocked_reasons + blocked_exports))
    for blocker in construction_release_blockers_from_meta(
        final_meta,
        requires_construction_release=final_plan_requires_construction_release(final_plan),
    ):
        if blocker not in release_blockers:
            release_blockers.append(blocker)

    final_deliverables = dict(final_meta.get("deliverables") or final_plan.get("deliverables") or {})
    run_summary = dict(result_data.get("run_summary") or dict(result_data.get("metadata") or {}).get("run_summary") or {})

    def _merged_deliverables(*values: Any) -> list[str]:
        merged: list[str] = []
        for value in values:
            for item in list(value or []):
                name = str(item).strip()
                if name and name not in merged:
                    merged.append(name)
        return merged

    failed_deliverables = _merged_deliverables(
        final_deliverables.get("failed"),
        release_review.get("failed_deliverables"),
        run_summary.get("failed_deliverables"),
    )
    for failed in failed_deliverables:
        failed_name = str(failed).strip()
        if not failed_name:
            continue
        blocker = f"failed_deliverable_{failed_name.lower().replace(' ', '_')}"
        if blocker not in release_blockers:
            release_blockers.append(blocker)
    missing_deliverables = _merged_deliverables(
        final_deliverables.get("missing"),
        release_review.get("missing_deliverables"),
        run_summary.get("missing_deliverables"),
    )
    requested_deliverables = _merged_deliverables(
        final_deliverables.get("requested"),
        release_review.get("requested_deliverables"),
        run_summary.get("requested_deliverables"),
    )
    produced_deliverables = _merged_deliverables(
        final_deliverables.get("produced"),
        release_review.get("produced_deliverables"),
        run_summary.get("produced_deliverables"),
    )
    produced_set = {str(item).strip() for item in produced_deliverables if str(item).strip()}
    failed_set = {str(item).strip() for item in failed_deliverables if str(item).strip()}
    missing_deliverables.extend(
        str(item).strip()
        for item in requested_deliverables
        if str(item).strip() and str(item).strip() not in produced_set and str(item).strip() not in failed_set
    )
    missing_deliverables = list(dict.fromkeys([str(item).strip() for item in missing_deliverables if str(item).strip()]))
    for missing in missing_deliverables:
        blocker = f"missing_deliverable_{missing.lower().replace(' ', '_')}"
        if blocker not in release_blockers:
            release_blockers.append(blocker)
    manual_validation = dict(final_meta.get("manual_validation") or {})
    for failure in list(manual_validation.get("failures") or []):
        if not isinstance(failure, dict):
            continue
        failure_name = str(
            failure.get("code")
            or failure.get("rule")
            or failure.get("system")
            or failure.get("reason")
            or failure.get("message")
            or "manual_validation_failure"
        ).strip()
        if not failure_name:
            failure_name = "manual_validation_failure"
        blocker = f"manual_validation_{failure_name.lower().replace(' ', '_')}"
        if blocker not in release_blockers:
            release_blockers.append(blocker)
    if release_review.get("release_ready") is False and "release_review_not_ready" not in release_blockers:
        release_blockers.append("release_review_not_ready")
    if final_meta.get("release_ready") is False and "final_plan_release_blocked" not in release_blockers:
        release_blockers.append("final_plan_release_blocked")
    reactive_report = dict(final_meta.get("reactive_update_report") or {})
    if reactive_report.get("post_rerun_production_ready") is False and "reactive_post_rerun_not_ready" not in release_blockers:
        release_blockers.append("reactive_post_rerun_not_ready")
    for blocker in list(reactive_report.get("post_rerun_release_blockers") or []):
        blocker_name = str(blocker).strip()
        if blocker_name and blocker_name not in release_blockers:
            release_blockers.append(blocker_name)
    release_status = str(release_review.get("release_status") or final_meta.get("release_status") or "")
    if release_status.lower() == "blocked" and "release_status_blocked" not in release_blockers:
        release_blockers.append("release_status_blocked")
    canonical_model_reference = {
        key: value
        for key, value in {
            "canonical_model_id": final_meta.get("canonical_model_id") or final_meta.get("model_id"),
            "canonical_model_hash": final_meta.get("canonical_model_hash") or final_meta.get("model_hash"),
            "source_model_id": final_meta.get("source_model_id"),
            "source_model_hash": final_meta.get("source_model_hash"),
            "final_model_id": final_meta.get("final_model_id"),
            "final_model_hash": final_meta.get("final_model_hash"),
        }.items()
        if value not in (None, "")
    }
    package = construction_package_record(final_meta)
    private_alpha = dict(final_meta.get("private_alpha_readiness") or {})
    artifact = {
        "artifact_id": new_workflow_id("artifact"),
        "kind": artifact_kind,
        "project_id": project_id,
        "filename": path.name,
        "created_at": now_ts(),
        "project_name": str(final_plan.get("project_name") or "Generated Plan"),
        "download_path": f"/api/artifacts/{path.name}",
    }
    if release_status:
        artifact["release_status"] = release_status
        artifact["release_ready"] = release_status == "ready" and not release_blockers
    elif "release_ready" in final_meta:
        artifact["release_ready"] = bool(final_meta.get("release_ready")) and not release_blockers
    if release_blockers:
        artifact["release_blockers"] = release_blockers
        artifact["release_blocker_details"] = blocker_explanations(release_blockers)
    if canonical_model_reference:
        artifact["canonical_model_reference"] = canonical_model_reference
    if private_alpha:
        artifact["private_alpha_readiness"] = {
            "status": str(private_alpha.get("status") or ""),
            "full_system_private_alpha_ready": bool(private_alpha.get("full_system_private_alpha_ready")),
            "review_only": bool(private_alpha.get("review_only")),
            "construction_release_blocked": bool(private_alpha.get("construction_release_blocked")),
            "construction_release_allowed": bool(private_alpha.get("construction_release_allowed")),
            "blocker_count": int(private_alpha.get("blocker_count") or 0),
            "launch_recommendation": str(private_alpha.get("launch_recommendation") or ""),
        }
    package_id = (
        package.get("id")
        or package.get("package_id")
        or package.get("manifest_id")
        or package.get("construction_package_id")
    )
    if package_id:
        artifact["construction_package_id"] = str(package_id)
    return artifact


def list_projects(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
) -> Dict[str, Any]:
    projects = [
        _record_with_operational_summary(dict(item))
        for item in list(project_store.list_projects(user_id=user_id) or [])
        if isinstance(item, dict)
    ]
    return {
        "success": True,
        "projects": projects,
    }


def get_project_detail(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: str,
) -> Dict[str, Any]:
    record = project_store.get_project_shell(user_id=user_id, project_id=project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"success": True, "project": _record_with_operational_summary(record)}


def get_project_result(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: str,
) -> Dict[str, Any]:
    record = project_store.get_project_shell(user_id=user_id, project_id=project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    latest_result = project_store.get_project_latest_result(
        user_id=user_id,
        project_id=project_id,
    )
    return {
        "success": True,
        "project_id": project_id,
        "latest_result": _with_progress_timeline_result(
            _with_smart_fix_result(dict(latest_result or {})),
            project_input=dict(record.get("project_input") or {}),
        ),
    }


def _with_smart_fix_result(latest_result: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(latest_result or {})
    final_plan = dict(result.get("final_plan") or {})
    if not final_plan:
        return result
    meta = dict(final_plan.get("meta") or {})
    if "smart_fix_recommendations_v1" not in meta:
        meta["smart_fix_recommendations_v1"] = build_smart_fix_recommendations(final_plan, meta=meta)
    if "review_issue_tracker_v1" not in meta:
        meta["review_issue_tracker_v1"] = build_review_issue_tracker(final_plan, meta=meta)
    final_plan["meta"] = meta
    result["final_plan"] = final_plan
    return result


def _project_final_plan_meta(record: Dict[str, Any]) -> Dict[str, Any]:
    latest_result = dict(record.get("latest_result") or {})
    final_plan = dict(latest_result.get("final_plan") or {})
    return dict(final_plan.get("meta") or {})


def _project_candidate_review_meta(record: Dict[str, Any]) -> Dict[str, Any]:
    project_input = safe_dict(record.get("project_input"))
    input_meta = safe_dict(project_input.get("meta"))
    site_inputs = safe_dict(input_meta.get("site_inputs"))
    final_meta = _project_final_plan_meta(record)
    return {
        **site_inputs,
        **final_meta,
        "map_feature_detection_report_v1": (
            final_meta.get("map_feature_detection_report_v1")
            or site_inputs.get("map_feature_detection_report_v1")
        ),
        "candidate_review_inbox_v1": (
            site_inputs.get("candidate_review_inbox_v1")
            or final_meta.get("candidate_review_inbox_v1")
        ),
        "candidate_review_decisions_v1": (
            site_inputs.get("candidate_review_decisions_v1")
            or final_meta.get("candidate_review_decisions_v1")
            or []
        ),
        "candidate_review_accepted_drafts_v1": (
            site_inputs.get("candidate_review_accepted_drafts_v1")
            or final_meta.get("candidate_review_accepted_drafts_v1")
            or []
        ),
        "candidate_review_rejected_v1": (
            site_inputs.get("candidate_review_rejected_v1")
            or final_meta.get("candidate_review_rejected_v1")
            or []
        ),
        VISION_DATASET_VERSION: (
            site_inputs.get(VISION_DATASET_VERSION)
            or final_meta.get(VISION_DATASET_VERSION)
            or {}
        ),
        VISION_QUALITY_VERSION: (
            site_inputs.get(VISION_QUALITY_VERSION)
            or final_meta.get(VISION_QUALITY_VERSION)
            or {}
        ),
    }


def _candidate_review_record(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: str,
) -> Optional[Dict[str, Any]]:
    shell_getter = getattr(project_store, "get_project_shell", None)
    shell = shell_getter(user_id=user_id, project_id=project_id) if callable(shell_getter) else None
    if shell is not None:
        shell_meta = _project_candidate_review_meta(shell)
        if shell_meta.get("candidate_review_inbox_v1") or shell_meta.get("map_feature_detection_report_v1"):
            return shell
    return project_store.get_project(user_id=user_id, project_id=project_id)


def get_project_candidate_review_inbox(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: str,
) -> Dict[str, Any]:
    record = _candidate_review_record(
        project_store=project_store,
        user_id=user_id,
        project_id=project_id,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    meta = _project_candidate_review_meta(record)
    inbox = dict(meta.get("candidate_review_inbox_v1") or build_candidate_review_inbox(meta))
    return {
        "success": True,
        "project_id": project_id,
        "candidate_review_inbox_v1": inbox,
        "truth_label": inbox.get("truth_label"),
    }


def get_project_vision_learning_package(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: str,
) -> Dict[str, Any]:
    record = _candidate_review_record(
        project_store=project_store,
        user_id=user_id,
        project_id=project_id,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    meta = _project_candidate_review_meta(record)
    package = build_vision_learning_package(
        meta,
        project_input=safe_dict(record.get("project_input")),
    )
    return {
        **package,
        "project_id": project_id,
    }


def get_project_source_confidence_map(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: str,
) -> Dict[str, Any]:
    record = project_store.get_project(user_id=user_id, project_id=project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    meta = _project_final_plan_meta(record)
    confidence_map = dict(
        meta.get("source_confidence_map_v1")
        or build_source_confidence_map(meta, project_input=dict(record.get("project_input") or {}))
    )
    return {
        "success": True,
        "project_id": project_id,
        "source_confidence_map_v1": confidence_map,
        "truth_label": confidence_map.get("truth_label"),
    }


def get_project_design_alternatives(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: str,
    requested_count: int = 3,
) -> Dict[str, Any]:
    record = project_store.get_project(user_id=user_id, project_id=project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    latest_result = dict(record.get("latest_result") or {})
    final_plan = dict(latest_result.get("final_plan") or {})
    if not final_plan:
        raise HTTPException(status_code=400, detail="Selected project has no saved planner result.")
    meta = dict(final_plan.get("meta") or {})
    alternatives = dict(meta.get(ALTERNATIVES_VERSION) or build_design_alternatives(meta, requested_count=requested_count))
    return {
        "success": True,
        "project_id": project_id,
        ALTERNATIVES_VERSION: alternatives,
        "comparison": compare_design_alternatives({**meta, ALTERNATIVES_VERSION: alternatives}, requested_count=requested_count),
        "truth_label": alternatives.get("truth_label"),
    }


def update_project_design_alternatives(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: str,
    action: str,
    requested_count: int = 3,
    option_number: Optional[int] = None,
    alternative_id: str = "",
    reason: str = "",
    reviewer_id: str = "",
) -> Dict[str, Any]:
    record = project_store.get_project(user_id=user_id, project_id=project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    latest_result = dict(record.get("latest_result") or {})
    final_plan = dict(latest_result.get("final_plan") or {})
    if not final_plan:
        raise HTTPException(status_code=400, detail="Selected project has no saved planner result.")
    meta = dict(final_plan.get("meta") or {})
    normalized_action = str(action or "generate").strip().lower()
    try:
        if normalized_action == "generate":
            alternatives = build_design_alternatives(meta, requested_count=requested_count)
            meta[ALTERNATIVES_VERSION] = alternatives
            result = {"success": True, ALTERNATIVES_VERSION: alternatives, "updated_meta": meta}
        elif normalized_action == "compare":
            alternatives = dict(meta.get(ALTERNATIVES_VERSION) or build_design_alternatives(meta, requested_count=requested_count))
            meta[ALTERNATIVES_VERSION] = alternatives
            result = {
                "success": True,
                ALTERNATIVES_VERSION: alternatives,
                "comparison": compare_design_alternatives(meta, requested_count=requested_count),
                "updated_meta": meta,
            }
        elif normalized_action in {"choose", "merge", "select", "use"}:
            result = select_design_alternative(
                meta,
                option_number=option_number,
                alternative_id=alternative_id,
                action="merge" if normalized_action == "merge" else "choose",
                reviewer_id=reviewer_id or user_id,
                reason=reason,
            )
            meta = dict(result.get("updated_meta") or meta)
        elif normalized_action == "revise":
            result = append_revised_design_alternative(
                meta,
                basis_option_number=option_number,
                reviewer_id=reviewer_id or user_id,
                reason=reason,
            )
            meta = dict(result.get("updated_meta") or meta)
        else:
            raise ValueError("Unsupported alternatives action.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    final_plan["meta"] = meta
    latest_result["final_plan"] = final_plan
    latest_result = _with_progress_timeline_result(
        latest_result,
        project_input=dict(record.get("project_input") or {}),
    )
    saved = project_store.save_project(
        user_id=user_id,
        project_id=project_id,
        name=record.get("name", "Untitled Project"),
        description=record.get("description", ""),
        session_id=record.get("session_id"),
        tags=record.get("tags", []),
        project_input=record.get("project_input", {}),
        latest_result=latest_result,
        session_state=record.get("session_state", {}),
        metadata=record.get("metadata", {}),
    )
    alternatives = dict(meta.get(ALTERNATIVES_VERSION) or {})
    return {
        **result,
        "success": True,
        "project_id": project_id,
        "project": _record_with_operational_summary(saved),
        ALTERNATIVES_VERSION: alternatives,
        "comparison": result.get("comparison") or compare_design_alternatives(meta, requested_count=requested_count),
        "truth_label": result.get("truth_label") or alternatives.get("truth_label"),
    }


def review_project_candidates(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: str,
    candidate_ids: list[str],
    action: str,
    reason: str = "",
    reviewer_id: str = "",
    corrected_feature_type: str = "",
    corrected_geometry: Any = None,
    correction_coordinate_space: str = "",
) -> Dict[str, Any]:
    record = _candidate_review_record(
        project_store=project_store,
        user_id=user_id,
        project_id=project_id,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    latest_result = dict(record.get("latest_result") or {})
    final_plan = dict(latest_result.get("final_plan") or {})
    meta = _project_candidate_review_meta(record)
    try:
        decision = apply_candidate_review_decision(
            meta,
            candidate_ids=candidate_ids,
            action=action,
            reviewer_id=reviewer_id or user_id,
            reason=reason,
            corrected_feature_type=corrected_feature_type,
            corrected_geometry=corrected_geometry,
            correction_coordinate_space=correction_coordinate_space,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    updated_meta = dict(decision.get("updated_meta") or meta)
    updated_meta["source_confidence_map_v1"] = build_source_confidence_map(
        updated_meta,
        project_input=dict(record.get("project_input") or {}),
    )
    project_input = deepcopy(safe_dict(record.get("project_input")))
    vision_package = build_vision_learning_package(updated_meta, project_input=project_input)
    updated_meta[VISION_DATASET_VERSION] = vision_package[VISION_DATASET_VERSION]
    updated_meta[VISION_QUALITY_VERSION] = vision_package[VISION_QUALITY_VERSION]
    input_meta = deepcopy(safe_dict(project_input.get("meta")))
    site_inputs = deepcopy(safe_dict(input_meta.get("site_inputs")))
    for key in (
        "candidate_review_inbox_v1",
        "candidate_review_decisions_v1",
        "candidate_review_accepted_drafts_v1",
        "candidate_review_rejected_v1",
        "source_confidence_map_v1",
        VISION_DATASET_VERSION,
        VISION_QUALITY_VERSION,
    ):
        if key in updated_meta:
            site_inputs[key] = deepcopy(updated_meta[key])
    input_meta["site_inputs"] = site_inputs
    project_input["meta"] = input_meta
    if final_plan:
        final_plan["meta"] = updated_meta
        latest_result["final_plan"] = final_plan
        latest_result = _with_progress_timeline_result(
            latest_result,
            project_input=project_input,
        )
    candidate_state = {
        key: updated_meta[key]
        for key in (
            "candidate_review_inbox_v1",
            "candidate_review_decisions_v1",
            "candidate_review_accepted_drafts_v1",
            "candidate_review_rejected_v1",
            "source_confidence_map_v1",
            VISION_DATASET_VERSION,
            VISION_QUALITY_VERSION,
        )
        if key in updated_meta
    }
    candidate_state_updater = getattr(project_store, "update_project_candidate_review_state", None)
    if callable(candidate_state_updater):
        saved = candidate_state_updater(
            user_id=user_id,
            project_id=project_id,
            candidate_state=candidate_state,
            minimum_role="reviewer",
        )
    else:
        saved = project_store.save_project(
            user_id=user_id,
            project_id=project_id,
            name=record.get("name", "Untitled Project"),
            description=record.get("description", ""),
            session_id=record.get("session_id"),
            tags=record.get("tags", []),
            project_input=project_input,
            latest_result=latest_result,
            session_state=record.get("session_state", {}),
            metadata=record.get("metadata", {}),
            minimum_role="reviewer",
        )
    return {
        "success": True,
        "project_id": project_id,
        "project": _record_with_operational_summary(saved),
        "candidate_review_inbox_v1": decision["candidate_review_inbox_v1"],
        "accepted_drafts": decision["accepted_drafts"],
        "rejected_candidates": decision["rejected_candidates"],
        "audit_trail": decision["audit_trail"],
        "truth_label": decision["truth_label"],
        VISION_DATASET_VERSION: vision_package[VISION_DATASET_VERSION],
        VISION_QUALITY_VERSION: vision_package[VISION_QUALITY_VERSION],
    }


def save_project_record(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    payload_data: Dict[str, Any],
    export_session_state: Optional[Callable[[Optional[str]], Dict[str, Any]]] = None,
    build_run_summary: Optional[Callable[..., Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    project_id = payload_data.get("project_id")
    session_id = payload_data.get("session_id")
    session_export = export_session_state(session_id) if export_session_state else {}
    latest_result_in_payload = "latest_result" in payload_data
    incoming_latest_result = dict(payload_data.get("latest_result") or {})
    shell_getter = getattr(project_store, "get_project_shell", None)
    shell_saver = getattr(project_store, "save_project_shell", None)
    if (
        project_id
        and callable(shell_getter)
        and callable(shell_saver)
        and not incoming_latest_result
    ):
        existing_shell = shell_getter(user_id=user_id, project_id=project_id)
        if existing_shell is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        payload_metadata = dict(payload_data.get("metadata") or {})
        metadata = dict(existing_shell.get("metadata") or {})
        metadata.update(payload_metadata)
        project_input = dict(payload_data.get("project_input") or {})
        try:
            record = shell_saver(
                user_id=user_id,
                project_id=project_id,
                organization_id=payload_data.get("organization_id"),
                name=str(payload_data.get("name") or ""),
                description=str(payload_data.get("description") or ""),
                session_id=session_id,
                tags=list(payload_data.get("tags") or []),
                project_input=project_input,
                session_state=dict(session_export or {}),
                metadata=metadata,
            )
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return {"success": True, "project": _record_with_operational_summary(record)}

    existing = None
    if project_id:
        existing = project_store.get_project(user_id=user_id, project_id=project_id)
    payload_metadata = dict(payload_data.get("metadata") or {})
    metadata = dict(existing.get("metadata") or {}) if existing else {}
    metadata.update(payload_metadata)
    current_existing = existing
    if project_id:
        # Refresh just before persisting so a stale autosave cannot wipe a newer
        # staged result or workflow checkpoint that landed after the first read.
        refreshed_existing = project_store.get_project(user_id=user_id, project_id=project_id)
        if refreshed_existing is not None:
            current_existing = refreshed_existing
            metadata = dict(current_existing.get("metadata") or {})
            metadata.update(payload_metadata)
    latest_result = incoming_latest_result
    project_input = dict(payload_data.get("project_input") or {})
    if current_existing and (not latest_result_in_payload or not latest_result):
        existing_latest_result = dict(current_existing.get("latest_result") or {})
        if existing_latest_result:
            latest_result = existing_latest_result
    if current_existing:
        existing_project_input = dict(current_existing.get("project_input") or {})
        if existing_project_input:
            project_input = _merge_project_input(existing_project_input, project_input)
    if latest_result:
        latest_result = attach_cad_entity_model_to_result(latest_result, project_input=project_input)
        latest_result = attach_source_confidence_map(latest_result, project_input=project_input)
    if latest_result and build_run_summary:
        latest_result = _with_smart_fix_result(latest_result)
        metadata = merge_project_metadata(
            metadata,
            run_summary=build_run_summary(
                latest_result,
                source="project_save",
                project_id=project_id,
            ),
            latest_result=latest_result,
        )
    elif latest_result:
        metadata = update_project_version_history(metadata, latest_result, reason="project_save")
    latest_result = _with_progress_timeline_result(
        latest_result,
        project_input=project_input,
    )
    try:
        record = project_store.save_project(
            user_id=user_id,
            project_id=project_id,
            organization_id=payload_data.get("organization_id"),
            name=str(payload_data.get("name") or ""),
            description=str(payload_data.get("description") or ""),
            session_id=session_id,
            tags=list(payload_data.get("tags") or []),
            project_input=project_input,
            latest_result=latest_result,
            session_state=dict(session_export or {}),
            metadata=metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"success": True, "project": _record_with_operational_summary(record)}


def delete_project_record(
    *,
    project_store: ProjectStoreProtocol,
    artifact_service: Optional[ArtifactServiceProtocol] = None,
    job_queue: Optional[JobQueueProtocol] = None,
    user_id: str,
    project_id: str,
) -> Dict[str, Any]:
    deleted = project_store.delete_project(user_id=user_id, project_id=project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found.")
    if artifact_service is not None:
        artifact_service.delete_preview_cache_for_project(user_id=user_id, project_id=project_id)
    if job_queue is not None:
        job_queue.delete_jobs_for_project(user_id=user_id, project_id=project_id)
    return {"success": True, "project_id": project_id}
