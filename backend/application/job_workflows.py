from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, Optional, Protocol

from fastapi import HTTPException


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
    def _persist_runtime_phase_checkpoint(
        *,
        user_id: Optional[str],
        project_id: Optional[str],
        job_id: Optional[str],
        payload: Dict[str, Any],
        stage_name: str,
        status: str,
        detail: str,
        progress: int,
        checkpoint: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not (user_id and project_id and job_id):
            return
        existing = project_store.get_project(user_id=user_id, project_id=project_id)
        if existing is None:
            return

        metadata = dict(existing.get("metadata") or {})
        latest_result = dict(existing.get("latest_result") or {})
        workflow = dict(metadata.get("workflow") or {})
        runs = [dict(item) for item in list(workflow.get("runs") or []) if isinstance(item, dict)]
        existing_run = next((item for item in runs if str(item.get("job_id") or "") == job_id), {})
        run_summary = dict(existing_run)
        run_summary.setdefault("run_id", str(existing_run.get("run_id") or f"jobrun_{job_id}"))
        run_summary["job_id"] = job_id
        run_summary["project_id"] = project_id
        run_summary["source"] = str(existing_run.get("source") or "queued_job")
        phase_checkpoints = dict(run_summary.get("phase_checkpoints") or {})
        phase_order = [
            "layout",
            "grading",
            "drainage_storm",
            "utilities",
            "coordination_validation",
        ]
        labels = {
            "layout": "Layout",
            "grading": "Grading",
            "drainage_storm": "Drainage and Storm",
            "utilities": "Utilities",
            "coordination_validation": "Coordination and Validation",
        }
        stage_to_phase = {
            "layout": "layout",
            "grading": "grading",
            "drainage": "drainage_storm",
            "storm_pipes": "drainage_storm",
            "sanitary": "utilities",
            "utility_network": "utilities",
            "coordination_resolution": "coordination_validation",
            "qa": "coordination_validation",
        }
        target_phase = stage_to_phase.get(stage_name)
        for phase_name in phase_order:
            phase_entry = dict(phase_checkpoints.get(phase_name) or {})
            phase_entry.setdefault("label", labels[phase_name])
            phase_entry.setdefault("status", "pending")
            phase_entry.setdefault("ready", False)
            phase_entry.setdefault("messages", [])
            phase_checkpoints[phase_name] = phase_entry
        if target_phase:
            phase_entry = dict(phase_checkpoints.get(target_phase) or {})
            phase_entry["label"] = labels[target_phase]
            phase_entry["status"] = str(status or phase_entry.get("status") or "pending")
            phase_entry["ready"] = bool(status == "complete") or bool(phase_entry.get("ready"))
            messages = [str(item) for item in list(phase_entry.get("messages") or []) if str(item).strip()]
            if detail and detail not in messages:
                messages.append(detail)
            phase_entry["messages"] = messages[-3:]
            phase_entry["job_progress"] = int(progress or 0)
            phase_checkpoints[target_phase] = phase_entry
        completed_phase_count = sum(1 for name in phase_order if bool(dict(phase_checkpoints.get(name) or {}).get("ready")))
        run_summary["phase_checkpoints"] = phase_checkpoints
        run_summary["stage_summary"] = {
            "current_stage": stage_name,
            "current_status": status,
            "current_detail": detail,
            "progress": int(progress or 0),
        }
        run_summary["reliability_summary"] = dict(run_summary.get("reliability_summary") or {})
        run_summary["combined_view"] = {
            "status": "running",
            "ready": False,
            "completed_phase_count": completed_phase_count,
            "total_phase_count": len(phase_order),
            "current_stage": stage_name,
            "progress": int(progress or 0),
            "note": "Run is advancing through persisted engineering phases.",
        }

        checkpoint_result = dict(latest_result)
        if checkpoint:
            checkpoint_result["final_plan"] = dict(checkpoint)
        checkpoint_final_plan = dict(checkpoint_result.get("final_plan") or {})
        checkpoint_meta = dict(checkpoint_final_plan.get("meta") or {})
        checkpoint_meta["phase_checkpoints"] = phase_checkpoints
        checkpoint_meta["release_review"] = {
            **dict(checkpoint_meta.get("release_review") or {}),
            "phase_checkpoints": phase_checkpoints,
        }
        checkpoint_meta["run_summary"] = run_summary
        checkpoint_final_plan["meta"] = checkpoint_meta
        checkpoint_result["final_plan"] = checkpoint_final_plan
        checkpoint_metadata = dict(checkpoint_result.get("metadata") or {})
        checkpoint_metadata["run_summary"] = run_summary
        checkpoint_result["metadata"] = checkpoint_metadata
        if "success" not in checkpoint_result:
            checkpoint_result["success"] = False
        if "message" not in checkpoint_result:
            checkpoint_result["message"] = "Run is progressing through engineering phases."

        project_store.save_project(
            user_id=user_id,
            project_id=project_id,
            name=existing.get("name", "Untitled Project"),
            description=existing.get("description", ""),
            session_id=existing.get("session_id"),
            tags=existing.get("tags", []),
            project_input=payload,
            latest_result=checkpoint_result,
            session_state=existing.get("session_state", {}),
            metadata=merge_project_metadata(
                metadata,
                run_summary=run_summary,
            ),
        )

    def _current_export_guard_state(result_data: Dict[str, Any]) -> tuple[list[str], list[str]]:
        final_plan = dict(result_data.get("final_plan") or {})
        meta = dict(final_plan.get("meta") or {})
        has_discipline_meta = any(
            bool(meta.get(key))
            for key in ("grading", "drainage", "storm_pipes", "utilities")
        )
        if not has_discipline_meta:
            return [], []
        try:
            final_plan_from_result(result_data, enforce_export_guards=True)
            return [], []
        except HTTPException as exc:
            detail = str(exc.detail or "")
            lowered = detail.lower()
            blocked_exports: list[str] = []
            if "grading design" in lowered:
                blocked_exports = ["grading"]
            elif "utility design" in lowered:
                blocked_exports = ["utilities"]
            elif "drainage/storm state" in lowered:
                blocked_exports = ["drainage", "storm"]
            reasons_text = detail.split(": ", 1)[1] if ": " in detail else ""
            blocked_reasons = [part.strip() for part in reasons_text.split(",") if part.strip()]
            return blocked_exports, blocked_reasons
        except Exception:
            return [], []

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
        current_blocked_exports, current_blocked_reasons = _current_export_guard_state(enriched)
        final_plan = dict(enriched.get("final_plan") or {})
        final_meta = dict(final_plan.get("meta") or {})
        if current_blocked_exports or current_blocked_reasons or (
            bool(final_meta.get("grading") or final_meta.get("drainage") or final_meta.get("storm_pipes") or final_meta.get("utilities"))
            and not current_blocked_exports
            and not current_blocked_reasons
        ):
            blocked_exports = current_blocked_exports
            blocked_reasons = current_blocked_reasons
        if blocked_reasons or blocked_exports:
            enriched["blocked"] = blocked_reasons or blocked_exports
        elif "blocked" in enriched:
            enriched.pop("blocked", None)
        if review_categories:
            enriched["review_categories"] = review_categories

        if final_plan:
            convergence["blocked_reasons"] = list(blocked_reasons)
            convergence["blocked_exports"] = list(blocked_exports)
            reliability["release_ready"] = not bool(blocked_reasons or blocked_exports)
            reliability["blocked_export_count"] = len(blocked_exports)
            if blocked_reasons or blocked_exports:
                reliability["primary_attention"] = (blocked_reasons[:1] or blocked_exports[:1])[0]
            run_summary["convergence_summary"] = convergence
            run_summary["reliability_summary"] = reliability
            final_meta["run_summary"] = run_summary
            final_meta["phase_checkpoints"] = dict(run_summary.get("phase_checkpoints") or {})
            final_meta["release_review"] = {
                "blocked_reasons": blocked_reasons,
                "blocked_exports": blocked_exports,
                "review_categories": review_categories,
                "assumption_summary": assumption_summary,
                "reliability_summary": reliability,
                "phase_checkpoints": dict(run_summary.get("phase_checkpoints") or {}),
            }
            final_meta["blockers"] = blocked_reasons or blocked_exports
            final_meta["export_ready"] = not bool(blocked_reasons or blocked_exports)
            final_meta["release_ready"] = bool(reliability.get("release_ready"))
            final_meta["deliverables"] = {
                "requested": list(run_summary.get("requested_deliverables") or []),
                "produced": list(run_summary.get("produced_deliverables") or []),
                "failed": list(run_summary.get("failed_deliverables") or []),
                "ready": list(run_summary.get("ready_deliverables") or []),
                "extra": list(run_summary.get("extra_deliverables") or []),
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
        project_id = job.get("project_id")
        user_id = job.get("user_id")
        stage_labels = {
            "layout": "Layout Phase",
            "grading": "Grading Phase",
            "drainage": "Drainage Phase",
            "storm_pipes": "Storm Pipe Phase",
            "sanitary": "Sanitary Phase",
            "utility_network": "Utilities Phase",
            "coordination_resolution": "Coordination Phase",
            "earthwork": "Earthwork Phase",
            "sheets": "Sheet Phase",
            "qa": "Validation Phase",
        }

        def _phase_progress_callback(
            stage_name: str,
            status: str,
            progress: int,
            detail: str,
            *,
            checkpoint: Optional[Dict[str, Any]] = None,
        ) -> None:
            if not job_id:
                return
            label = stage_labels.get(str(stage_name or ""), "Engineering Run")
            message = str(detail or "").strip() or label
            update_job_progress(
                job_id,
                stage=label,
                detail=message,
                progress=int(progress or 48),
            )
            _persist_runtime_phase_checkpoint(
                user_id=user_id,
                project_id=project_id,
                job_id=job_id,
                payload=payload,
                stage_name=str(stage_name or ""),
                status=str(status or ""),
                detail=message,
                progress=int(progress or 48),
                checkpoint=checkpoint,
            )

        if job_id:
            update_job_progress(
                job_id,
                stage="Engineering Run",
                detail="Running the core design pipeline and building the plan.",
                progress=48,
            )
        run_signature = inspect.signature(run_orchestration)
        if "progress_callback" in run_signature.parameters:
            result = run_orchestration(payload, progress_callback=_phase_progress_callback)
        else:
            result = run_orchestration(payload)
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
