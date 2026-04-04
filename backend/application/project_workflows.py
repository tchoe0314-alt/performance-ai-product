from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional, Protocol

from fastapi import HTTPException

from backend.application.design_workflows import new_workflow_id, now_ts


class ProjectStoreProtocol(Protocol):
    def list_projects(self, *, user_id: str) -> list[Dict[str, Any]]:
        ...

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

    def delete_project(self, *, user_id: str, project_id: str) -> bool:
        ...


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


def merge_project_metadata(
    existing_metadata: Optional[Dict[str, Any]],
    *,
    run_summary: Optional[Dict[str, Any]] = None,
    artifact_summary: Optional[Dict[str, Any]] = None,
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
    metadata["workflow"] = workflow
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
    return {
        "artifact_id": new_workflow_id("artifact"),
        "kind": artifact_kind,
        "project_id": project_id,
        "filename": path.name,
        "created_at": now_ts(),
        "project_name": str(final_plan.get("project_name") or "Generated Plan"),
        "download_path": f"/api/artifacts/{path.name}",
    }


def list_projects(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
) -> Dict[str, Any]:
    return {
        "success": True,
        "projects": project_store.list_projects(user_id=user_id),
    }


def get_project_detail(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: str,
) -> Dict[str, Any]:
    record = project_store.get_project(user_id=user_id, project_id=project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"success": True, "project": record}


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
    existing = None
    if project_id:
        existing = project_store.get_project(user_id=user_id, project_id=project_id)
    metadata = dict(existing.get("metadata") or {}) if existing else {}
    metadata.update(dict(payload_data.get("metadata") or {}))
    latest_result = dict(payload_data.get("latest_result") or {})
    if latest_result and build_run_summary:
        metadata = merge_project_metadata(
            metadata,
            run_summary=build_run_summary(
                latest_result,
                source="project_save",
                project_id=project_id,
            ),
        )
    try:
        record = project_store.save_project(
            user_id=user_id,
            project_id=project_id,
            name=str(payload_data.get("name") or ""),
            description=str(payload_data.get("description") or ""),
            session_id=session_id,
            tags=list(payload_data.get("tags") or []),
            project_input=dict(payload_data.get("project_input") or {}),
            latest_result=latest_result,
            session_state=dict(session_export or {}),
            metadata=metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"success": True, "project": record}


def delete_project_record(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: str,
) -> Dict[str, Any]:
    deleted = project_store.delete_project(user_id=user_id, project_id=project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"success": True, "project_id": project_id}
