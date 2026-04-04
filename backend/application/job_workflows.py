from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Protocol


class JobQueueProtocol(Protocol):
    def submit_job(
        self,
        *,
        user_id: str,
        job_type: str,
        payload: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        ...

    def register_handler(self, job_type: str, runner: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
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


def queue_orchestrate_job(
    *,
    project_store: ProjectStoreProtocol,
    job_queue: JobQueueProtocol,
    user_id: str,
    project_id: Optional[str],
    request_payload: Dict[str, Any],
) -> Dict[str, Any]:
    if project_id:
        existing = project_store.get_project(user_id=user_id, project_id=project_id)
        if existing is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Project not found.")

    job = job_queue.submit_job(
        user_id=user_id,
        job_type="orchestrate",
        payload=dict(request_payload),
        project_id=project_id,
    )
    return {
        "success": True,
        "job": job,
        "operational_summary": {
            "status": str(job.get("status") or "queued"),
            "job_type": str(job.get("job_type") or "orchestrate"),
            "job_bound": bool(job.get("job_id")),
            "project_bound": bool(project_id),
            "project_id": project_id,
            "job_id": job.get("job_id"),
            "retryable": True,
        },
    }


def build_orchestrate_job_runner(
    *,
    project_store: ProjectStoreProtocol,
    run_orchestration: Callable[[Dict[str, Any]], Dict[str, Any]],
    build_run_summary: Callable[..., Dict[str, Any]],
    merge_project_metadata: Callable[..., Dict[str, Any]],
) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def orchestrate_runner(job: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(job.get("payload") or {})
        result = run_orchestration(payload)
        project_id = job.get("project_id")
        user_id = job.get("user_id")
        if project_id and user_id:
            existing = project_store.get_project(user_id=user_id, project_id=project_id)
            if existing is not None:
                project_store.save_project(
                    user_id=user_id,
                    project_id=project_id,
                    name=existing.get("name", "Untitled Project"),
                    description=existing.get("description", ""),
                    session_id=existing.get("session_id"),
                    tags=existing.get("tags", []),
                    project_input=payload,
                    latest_result=result,
                    session_state=existing.get("session_state", {}),
                    metadata=merge_project_metadata(
                        dict(existing.get("metadata") or {}),
                        run_summary=build_run_summary(
                            result,
                            source="queued_job",
                            project_id=project_id,
                            job_id=job.get("job_id"),
                        ),
                    ),
                )
        enriched = dict(result)
        metadata = dict(enriched.get("metadata") or {})
        metadata["job_context"] = {
            "job_id": job.get("job_id"),
            "job_type": job.get("job_type"),
            "project_id": project_id,
            "user_id": user_id,
            "source": "job_queue",
        }
        enriched["metadata"] = metadata
        return enriched

    return orchestrate_runner
