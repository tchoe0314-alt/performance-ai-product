from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional, Protocol

from fastapi import HTTPException

from backend.application.design_workflows import (
    new_workflow_id,
    now_ts,
)
from backend.planning.release_gates import (
    construction_release_blockers_from_meta,
    final_plan_requires_construction_release,
)
from backend.application.protocols import ArtifactServiceProtocol
from backend.application.job_workflows import JobQueueProtocol


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
        "latest_artifact_id": str(latest_artifact.get("artifact_id") or ""),
        "latest_artifact_kind": str(latest_artifact.get("kind") or ""),
        "latest_artifact_created_at": latest_artifact.get("created_at"),
        "latest_artifact_release_status": latest_artifact_status,
        "latest_artifact_release_ready": latest_artifact_release_ready,
        "latest_artifact_release_blockers": latest_artifact_blockers,
        "latest_artifact_model_reference": dict(latest_artifact.get("canonical_model_reference") or {}),
    }


def _latest_release_blockers(
    *,
    latest_run: Dict[str, Any],
    latest_reliability: Dict[str, Any],
    latest_convergence: Dict[str, Any],
    latest_artifact: Optional[Dict[str, Any]] = None,
) -> list[str]:
    blockers: list[str] = []

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
    _extend(latest_run.get("failed_deliverables"))
    _extend(latest_run.get("manual_failures"))
    artifact = dict(latest_artifact or {})
    _extend(artifact.get("release_blockers"))

    if int(latest_reliability.get("blocked_export_count") or 0) > 0:
        blockers.append("blocked_exports")
    if int(latest_reliability.get("unresolved_conflict_count") or 0) > 0:
        blockers.append("unresolved_conflicts")
    if int(latest_reliability.get("failed_deliverable_count") or 0) > 0:
        blockers.append("failed_deliverables")
    if int(latest_reliability.get("manual_failure_count") or 0) > 0:
        blockers.append("manual_validation_failures")
    if latest_reliability.get("release_ready") is False:
        blockers.append("latest_run_release_not_ready")
    if latest_run.get("final_plan_release_ready") is False:
        blockers.append("final_plan_release_blocked")
    if str(artifact.get("release_status") or "").lower() == "blocked":
        blockers.append("latest_artifact_release_blocked")
    return list(dict.fromkeys(blockers))


def _project_operational_summary(record: Dict[str, Any]) -> Dict[str, Any]:
    workflow_summary = dict(dict(record.get("metadata") or {}).get("workflow", {}).get("summary") or {})
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
    final_meta = dict(final_plan.get("meta") or {})
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
    if release_review.get("release_ready") is False and "release_review_not_ready" not in release_blockers:
        release_blockers.append("release_review_not_ready")
    if final_meta.get("release_ready") is False and "final_plan_release_blocked" not in release_blockers:
        release_blockers.append("final_plan_release_blocked")
    release_status = str(release_review.get("release_status") or final_meta.get("release_status") or "")
    if release_status.lower() == "blocked" and not release_blockers:
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
    package = dict(final_meta.get("construction_package_manifest") or final_meta.get("construction_package") or {})
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
    if canonical_model_reference:
        artifact["canonical_model_reference"] = canonical_model_reference
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
