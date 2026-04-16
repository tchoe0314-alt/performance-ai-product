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

    def get_project_shell(self, *, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        ...

    def get_project_latest_result(self, *, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
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
        "latest_release_ready": bool(latest_reliability.get("release_ready")),
        "latest_artifact_id": str(latest_artifact.get("artifact_id") or ""),
        "latest_artifact_kind": str(latest_artifact.get("kind") or ""),
        "latest_artifact_created_at": latest_artifact.get("created_at"),
    }


def _project_operational_summary(record: Dict[str, Any]) -> Dict[str, Any]:
    workflow_summary = dict(dict(record.get("metadata") or {}).get("workflow", {}).get("summary") or {})
    return {
        "operational_state": str(workflow_summary.get("latest_operational_state") or ""),
        "primary_attention": str(workflow_summary.get("latest_primary_attention") or ""),
        "release_ready": bool(workflow_summary.get("latest_release_ready")),
        "run_count": int(workflow_summary.get("run_count") or 0),
        "artifact_count": int(workflow_summary.get("artifact_count") or 0),
        "latest_run_id": str(workflow_summary.get("latest_run_id") or ""),
        "latest_artifact_id": str(workflow_summary.get("latest_artifact_id") or ""),
    }


def _record_with_operational_summary(record: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(record)
    enriched["operational_summary"] = _project_operational_summary(record)
    return enriched


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
    workflow["summary"] = _build_workflow_summary(runs=runs, artifacts=artifacts)
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
        "latest_result": dict(latest_result or {}),
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
    latest_result_in_payload = "latest_result" in payload_data
    latest_result = dict(payload_data.get("latest_result") or {})
    project_input = dict(payload_data.get("project_input") or {})
    if current_existing and (not latest_result_in_payload or not latest_result):
        existing_latest_result = dict(current_existing.get("latest_result") or {})
        if existing_latest_result:
            latest_result = existing_latest_result
    if current_existing:
        existing_project_input = dict(current_existing.get("project_input") or {})
        if existing_project_input:
            project_input = _merge_project_input(existing_project_input, project_input)
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
    user_id: str,
    project_id: str,
) -> Dict[str, Any]:
    deleted = project_store.delete_project(user_id=user_id, project_id=project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"success": True, "project_id": project_id}
