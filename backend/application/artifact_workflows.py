from __future__ import annotations

from base64 import b64encode
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

from backend.application.design_workflows import build_run_summary, final_plan_from_result
from backend.application.project_workflows import artifact_summary, save_project_workflow_update


class ArtifactServiceProtocol(Protocol):
    def build_preview_png(self, final_plan: Dict[str, Any]) -> bytes:
        ...

    def export_dxf(self, *, user_id: str, final_plan: Dict[str, Any], stem: Optional[str] = None) -> Path:
        ...

    def export_report_json(
        self,
        *,
        user_id: str,
        result_data: Dict[str, Any],
        stem: Optional[str] = None,
    ) -> Path:
        ...


class ProjectStoreProtocol(Protocol):
    def get_project(self, *, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
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
    ) -> Dict[str, Any]:
        ...


def _preview_review_summary(result_data: Dict[str, Any], final_plan: Dict[str, Any]) -> Dict[str, Any]:
    run_summary = build_run_summary(result_data, source="preview")
    convergence = dict(run_summary.get("convergence_summary") or {})
    engineering = dict(run_summary.get("engineering_status") or {})
    assumption_summary = dict(convergence.get("assumption_summary") or {})
    fix_summary = dict(convergence.get("fix_summary") or {})
    dominant_fix_targets = [
        str(item)
        for item in list(convergence.get("dominant_issue_categories") or [])
        if str(item)
    ]
    unresolved_issue_categories = [
        str(item)
        for item in list(convergence.get("unresolved_issue_categories") or [])
        if str(item)
    ]
    blocked_exports = [
        str(item)
        for item in list(convergence.get("blocked_exports") or [])
        if str(item)
    ]
    blocked_reasons = [
        str(item)
        for item in list(convergence.get("blocked_reasons") or [])
        if str(item)
    ]
    requested_deliverables = list(run_summary.get("requested_deliverables") or [])
    produced_deliverables = list(run_summary.get("produced_deliverables") or [])
    failed_deliverables = list(run_summary.get("failed_deliverables") or [])
    if blocked_exports or blocked_reasons or failed_deliverables:
        release_status = "blocked"
        release_note = "Blocked until outstanding export issues are resolved."
    elif bool(convergence.get("converged")) and int(convergence.get("unresolved_conflict_count") or 0) == 0:
        release_status = "ready"
        release_note = "Release-ready engineering state."
    else:
        release_status = "review"
        release_note = "Needs engineering review before release."
    return {
        "trust_score": float(engineering.get("trust_score") or 0.0),
        "converged": bool(convergence.get("converged")),
        "passes_run": int(convergence.get("passes_run") or 0),
        "unresolved_conflict_count": int(convergence.get("unresolved_conflict_count") or 0),
        "assumption_count": int(assumption_summary.get("count") or 0),
        "assumption_categories": [
            str(item)
            for item in list(assumption_summary.get("categories") or [])
            if str(item)
        ],
        "assumption_examples": [
            str(item)
            for item in list(assumption_summary.get("examples") or [])
            if str(item)
        ],
        "autofix_actions": [
            str(item)
            for item in list(fix_summary.get("autofix_actions") or [])
            if str(item)
        ],
        "dominant_fix_targets": dominant_fix_targets,
        "review_categories": unresolved_issue_categories,
        "blocked_exports": blocked_exports,
        "blocked_reasons": blocked_reasons,
        "requested_deliverables": requested_deliverables,
        "produced_deliverables": produced_deliverables,
        "failed_deliverables": failed_deliverables,
        "release_status": release_status,
        "release_note": release_note,
        "engineering_status": str((final_plan.get("meta") or {}).get("engineering_status") or ""),
    }


def build_preview_response(
    *,
    artifact_service: ArtifactServiceProtocol,
    result_data: Dict[str, Any],
) -> Dict[str, Any]:
    final_plan = final_plan_from_result(result_data)
    png_bytes = artifact_service.build_preview_png(final_plan)
    return {
        "success": True,
        "preview_image_data_url": f"data:image/png;base64,{b64encode(png_bytes).decode('ascii')}",
        "summary": {
            "project_name": final_plan.get("project_name", "Generated Plan"),
            "units": final_plan.get("units", "ft"),
            "action_count": len(final_plan.get("actions") or []),
            "review": _preview_review_summary(result_data, final_plan),
        },
    }


def export_dxf_artifact(
    *,
    artifact_service: ArtifactServiceProtocol,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: Optional[str],
    result_data: Dict[str, Any],
    filename_stem: Optional[str] = None,
) -> Path:
    final_plan = final_plan_from_result(result_data)
    stem = filename_stem or str(final_plan.get("project_name") or "civora-ai-plan")
    path = artifact_service.export_dxf(
        user_id=user_id,
        final_plan=final_plan,
        stem=stem,
    )
    if project_id:
        save_project_workflow_update(
            project_store=project_store,
            user_id=user_id,
            project_id=project_id,
            artifact_summary=artifact_summary(
                path=path,
                artifact_kind="dxf",
                project_id=project_id,
                result_data=result_data,
            ),
        )
    return path


def export_report_artifact(
    *,
    artifact_service: ArtifactServiceProtocol,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: Optional[str],
    result_data: Dict[str, Any],
    filename_stem: Optional[str] = None,
) -> Path:
    final_plan = dict(result_data.get("final_plan") or {})
    stem = filename_stem or str(final_plan.get("project_name") or "civora-ai-report")
    path = artifact_service.export_report_json(
        user_id=user_id,
        result_data=result_data,
        stem=stem,
    )
    if project_id:
        save_project_workflow_update(
            project_store=project_store,
            user_id=user_id,
            project_id=project_id,
            artifact_summary=artifact_summary(
                path=path,
                artifact_kind="report",
                project_id=project_id,
                result_data=result_data,
            ),
        )
    return path
