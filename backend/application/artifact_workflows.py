from __future__ import annotations

from base64 import b64encode
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

from backend.application.design_workflows import final_plan_from_result
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
