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

    def update_job_progress(self, job_id: str, *, stage: str, detail: str, progress: int) -> None:
        ...

    def cancel_job(self, *, user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
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


class FinalPlanBuilderProtocol(Protocol):
    def __call__(
        self,
        result_data: Dict[str, Any],
        *,
        enforce_export_guards: bool = True,
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


def cancel_existing_job(
    *,
    job_queue: JobQueueProtocol,
    user_id: str,
    job_id: str,
) -> Dict[str, Any]:
    job = job_queue.cancel_job(user_id=user_id, job_id=job_id)
    if job is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "success": True,
        "job": job,
        "operational_summary": {
            "status": str(job.get("status") or "cancelled"),
            "job_type": str(job.get("job_type") or "orchestrate"),
            "job_bound": bool(job.get("job_id")),
            "project_bound": bool(job.get("project_id")),
            "project_id": job.get("project_id"),
            "job_id": job.get("job_id"),
            "retryable": False,
        },
    }


def build_orchestrate_job_runner(
    *,
    project_store: ProjectStoreProtocol,
    update_job_progress: Callable[..., None],
    run_orchestration: Callable[[Dict[str, Any]], Dict[str, Any]],
    build_run_summary: Callable[..., Dict[str, Any]],
    merge_project_metadata: Callable[..., Dict[str, Any]],
    final_plan_from_result: FinalPlanBuilderProtocol,
) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def _normalized_result_for_ui(
        result: Dict[str, Any],
        *,
        project_id: Optional[str],
        job_id: Optional[str],
        user_id: Optional[str],
    ) -> Dict[str, Any]:
        enriched = dict(result)
        try:
            enriched["final_plan"] = final_plan_from_result(
                enriched,
                enforce_export_guards=False,
            )
        except Exception:
            pass

        run_summary = build_run_summary(
            enriched,
            source="queued_job",
            project_id=project_id,
            job_id=job_id,
        )
        convergence = dict(run_summary.get("convergence_summary") or {})
        reliability = dict(run_summary.get("reliability_summary") or {})
        assumption_summary = dict(convergence.get("assumption_summary") or {})
        categories = [
            str(item).strip()
            for item in list(assumption_summary.get("categories") or [])
            if str(item).strip()
        ]
        assumption_examples = [
            str(item).strip()
            for item in list(assumption_summary.get("examples") or [])
            if str(item).strip()
        ]
        if assumption_examples:
            fallback_category = categories[0] if categories else "design_defaults"
            enriched["assumptions"] = [
                {
                    "field_name": fallback_category,
                    "assumed_value": example,
                    "reason": "Assisted design assumption",
                }
                for example in assumption_examples
            ]
        elif "assumptions" not in enriched:
            enriched["assumptions"] = []

        blocked_reasons = [str(item) for item in list(convergence.get("blocked_reasons") or []) if str(item)]
        blocked_exports = [str(item) for item in list(convergence.get("blocked_exports") or []) if str(item)]
        review_categories = [
            str(item)
            for item in list(convergence.get("unresolved_issue_categories") or [])
            if str(item)
        ]
        if blocked_reasons or blocked_exports:
            enriched["blocked"] = blocked_reasons or blocked_exports
        if review_categories:
            enriched["review_categories"] = review_categories

        final_plan = dict(enriched.get("final_plan") or {})
        if final_plan:
            final_meta = dict(final_plan.get("meta") or {})
            final_meta["run_summary"] = run_summary
            final_meta["release_review"] = {
                "blocked_reasons": blocked_reasons,
                "blocked_exports": blocked_exports,
                "review_categories": review_categories,
                "assumption_summary": assumption_summary,
                "reliability_summary": reliability,
            }
            final_plan["meta"] = final_meta
            final_plan["export_ready"] = not bool(blocked_reasons or blocked_exports)
            final_plan["release_ready"] = bool(reliability.get("release_ready"))
            final_plan["blockers"] = blocked_reasons or blocked_exports
            final_plan["deliverables"] = {
                "requested": list(run_summary.get("requested_deliverables") or []),
                "produced": list(run_summary.get("produced_deliverables") or []),
                "failed": list(run_summary.get("failed_deliverables") or []),
                "ready": list(run_summary.get("ready_deliverables") or []),
                "extra": list(run_summary.get("extra_deliverables") or []),
            }
            enriched["final_plan"] = final_plan

        metadata = dict(enriched.get("metadata") or {})
        metadata["run_summary"] = run_summary
        metadata["job_context"] = {
            "job_id": job_id,
            "job_type": "orchestrate",
            "project_id": project_id,
            "user_id": user_id,
            "source": "job_queue",
            "operational_state": reliability.get("operational_state"),
            "primary_attention": reliability.get("primary_attention"),
        }
        enriched["metadata"] = metadata
        return enriched

    def orchestrate_runner(job: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(job.get("payload") or {})
        job_id = str(job.get("job_id") or "").strip()
        if job_id:
            update_job_progress(
                job_id,
                stage="Engineering Run",
                detail="Running the core design pipeline and building the plan.",
                progress=48,
            )
        result = run_orchestration(payload)
        project_id = job.get("project_id")
        user_id = job.get("user_id")
        enriched = _normalized_result_for_ui(
            result,
            project_id=project_id,
            job_id=job_id,
            user_id=user_id,
        )
        if project_id and user_id:
            if job_id:
                update_job_progress(
                    job_id,
                    stage="Saving Project",
                    detail="Saving the latest design state back into the project.",
                    progress=76,
                )
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
                    latest_result=enriched,
                    session_state=existing.get("session_state", {}),
                    metadata=merge_project_metadata(
                        dict(existing.get("metadata") or {}),
                        run_summary=dict(dict(enriched.get("metadata") or {}).get("run_summary") or {}),
                    ),
                )
        if job_id:
            update_job_progress(
                job_id,
                stage="Finalizing",
                detail="Finalizing the run summary and preparing the result for the UI.",
                progress=92,
            )
        return enriched

    return orchestrate_runner
