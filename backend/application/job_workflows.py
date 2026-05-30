from __future__ import annotations

import inspect
import os
from copy import deepcopy
from typing import Any, Callable, Dict, Optional, Protocol

from fastapi import HTTPException
from backend.planning.common import safe_dict, safe_float, safe_int, safe_list, safe_str
from backend.planning.release_gates import (
    construction_release_blockers_from_meta,
    final_plan_requires_construction_release,
)
from core.utils import safe_bool
from core.config import POND_RADIUS


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

    def continue_job(self, *, user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        ...

    def revise_job(
        self,
        *,
        user_id: str,
        job_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        ...

    def delete_jobs_for_project(self, *, user_id: str, project_id: str) -> int:
        ...

    def get_job_detail(self, *, user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        ...


class ProjectStoreProtocol(Protocol):
    def get_project(self, *, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
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


class FinalPlanBuilderProtocol(Protocol):
    def __call__(
        self,
        result_data: Dict[str, Any],
        *,
        enforce_export_guards: bool = True,
        ) -> Dict[str, Any]:
        ...


def _load_project_latest_result(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: str,
    fallback_project: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    getter = getattr(project_store, "get_project_latest_result", None)
    if callable(getter):
        try:
            latest_result = getter(user_id=user_id, project_id=project_id)
        except TypeError:
            latest_result = None
        if isinstance(latest_result, dict) and latest_result:
            return dict(latest_result)
    return dict((fallback_project or {}).get("latest_result") or {})


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
        seeded_project_input = {
            **dict(existing.get("project_input") or {}),
            **dict(request_payload or {}),
            "request_payload": dict(request_payload or {}),
        }
        project_store.save_project(
            user_id=user_id,
            project_id=project_id,
            name=str(existing.get("name") or "Untitled Project"),
            description=str(existing.get("description") or ""),
            session_id=existing.get("session_id"),
            tags=list(existing.get("tags") or []),
            project_input=seeded_project_input,
            latest_result=dict(existing.get("latest_result") or {}),
            session_state=dict(existing.get("session_state") or {}),
            metadata=dict(existing.get("metadata") or {}),
        )

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


def queue_drainage_job(
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
            raise HTTPException(status_code=404, detail="Project not found.")
        seeded_project_input = {
            **dict(existing.get("project_input") or {}),
            **dict(request_payload or {}),
            "request_payload": dict(request_payload or {}),
        }
        project_store.save_project(
            user_id=user_id,
            project_id=project_id,
            name=str(existing.get("name") or "Untitled Project"),
            description=str(existing.get("description") or ""),
            session_id=existing.get("session_id"),
            tags=list(existing.get("tags") or []),
            project_input=seeded_project_input,
            latest_result=dict(existing.get("latest_result") or {}),
            session_state=dict(existing.get("session_state") or {}),
            metadata=dict(existing.get("metadata") or {}),
        )

    job = job_queue.submit_job(
        user_id=user_id,
        job_type="drainage_only",
        payload=dict(request_payload),
        project_id=project_id,
    )
    return {
        "success": True,
        "job": job,
        "operational_summary": {
            "status": str(job.get("status") or "queued"),
            "job_type": str(job.get("job_type") or "drainage_only"),
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


def continue_existing_job(
    *,
    job_queue: JobQueueProtocol,
    user_id: str,
    job_id: str,
) -> Dict[str, Any]:
    job = job_queue.continue_job(user_id=user_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "success": True,
        "job": job,
        "operational_summary": {
            "status": str(job.get("status") or "queued"),
            "job_type": str(job.get("job_type") or "orchestrate"),
            "job_bound": bool(job.get("job_id")),
            "project_bound": bool(job.get("project_id")),
            "project_id": job.get("project_id"),
            "job_id": job.get("job_id"),
            "retryable": True,
        },
    }


def revise_existing_job(
    *,
    project_store: ProjectStoreProtocol,
    job_queue: JobQueueProtocol,
    user_id: str,
    job_id: str,
    target_phase: Optional[str] = None,
) -> Dict[str, Any]:
    job = job_queue.get_job_detail(user_id=user_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    project_id = str(job.get("project_id") or "").strip()
    if not project_id:
        raise HTTPException(status_code=409, detail="Job is not bound to a project.")

    project = project_store.get_project(user_id=user_id, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    latest_result = _load_project_latest_result(
        project_store=project_store,
        user_id=user_id,
        project_id=project_id,
        fallback_project=project,
    )
    final_plan = dict(latest_result.get("final_plan") or {})
    final_meta = dict(final_plan.get("meta") or {})
    result_metadata = dict(latest_result.get("metadata") or {})
    runtime_checkpoint = dict(
        result_metadata.get("runtime_phase_checkpoint")
        or final_meta.get("runtime_phase_checkpoint")
        or dict(job.get("result") or {}).get("metadata", {}).get("runtime_phase_checkpoint")
        or {}
    )
    stage_name = str(runtime_checkpoint.get("stage_name") or "").strip()
    if not stage_name:
        raise HTTPException(status_code=409, detail="No saved phase checkpoint is available to revise.")

    stage_order = [
        "layout",
        "grading",
        "drainage",
        "storm_pipes",
        "sanitary",
        "utility_network",
        "coordination_resolution",
        "earthwork",
        "sheets",
        "qa",
    ]
    stage_to_phase = {
        "layout": "layout",
        "grading": "grading",
        "drainage": "drainage_storm",
        "storm_pipes": "drainage_storm",
        "sanitary": "utilities",
        "utility_network": "utilities",
        "coordination_resolution": "coordination_validation",
        "earthwork": "coordination_validation",
        "sheets": "coordination_validation",
        "qa": "coordination_validation",
    }
    phase_order = [
        "layout",
        "grading",
        "drainage_storm",
        "utilities",
        "coordination_validation",
    ]

    requested_phase = lower_text(target_phase) if target_phase else ""
    if requested_phase in phase_order:
        phase_to_stage = {
            "layout": "layout",
            "grading": "grading",
            "drainage_storm": "drainage",
            "utilities": "sanitary",
            "coordination_validation": "coordination_resolution",
        }
        stage_name = phase_to_stage.get(requested_phase, stage_name)
    try:
        target_stage_index = stage_order.index(stage_name)
    except ValueError:
        target_stage_index = 0
    target_phase = stage_to_phase.get(stage_name, "layout")
    target_phase_index = phase_order.index(target_phase) if target_phase in phase_order else 0

    stage_statuses = dict(dict(final_meta.get("stage_completeness") or {}).get("statuses") or {})
    for staged_name in stage_order[target_stage_index:]:
        stage_statuses[staged_name] = "pending"

    phase_checkpoints = dict(
        final_meta.get("phase_checkpoints")
        or dict(result_metadata.get("run_summary") or {}).get("phase_checkpoints")
        or {}
    )
    phase_labels = {
        "layout": "Layout",
        "grading": "Grading",
        "drainage_storm": "Drainage and Storm",
        "utilities": "Utilities",
        "coordination_validation": "Coordination and Validation",
    }
    for phase_name in phase_order:
        phase_entry = dict(phase_checkpoints.get(phase_name) or {})
        phase_entry.setdefault("label", phase_labels[phase_name])
        if phase_order.index(phase_name) >= target_phase_index:
            messages = [
                str(item)
                for item in list(phase_entry.get("messages") or [])
                if str(item).strip()
            ]
            revision_message = (
                f"Revision requested. {phase_labels[target_phase]} will rerun using the latest saved changes."
            )
            if revision_message not in messages:
                messages.append(revision_message)
            phase_entry["status"] = "pending"
            phase_entry["ready"] = False
            phase_entry["messages"] = messages[-3:]
            phase_entry["job_progress"] = 62
        phase_checkpoints[phase_name] = phase_entry

    completed_phase_count = sum(
        1
        for phase_name in phase_order
        if phase_order.index(phase_name) < target_phase_index
        and bool(dict(phase_checkpoints.get(phase_name) or {}).get("ready"))
    )
    combined_view = dict(phase_checkpoints.get("combined_view") or {})
    combined_view.update(
        {
            "label": str(combined_view.get("label") or "Combined View"),
            "status": "pending",
            "ready": False,
            "completed_phase_count": completed_phase_count,
            "total_phase_count": max(int(combined_view.get("total_phase_count") or 0), len(phase_order)),
            "current_stage": stage_name,
            "current_status": "pending",
            "job_progress": 62,
            "note": f"Revision requested. Waiting to rerun {phase_labels[target_phase]}.",
            "messages": [f"{phase_labels[target_phase]} is queued to rerun with the latest saved changes."],
            "deliverables": [],
            "blockers": [],
        }
    )
    phase_checkpoints["combined_view"] = combined_view

    release_review = dict(final_meta.get("release_review") or {})
    release_review["phase_checkpoints"] = phase_checkpoints
    release_review["release_status"] = "review"
    release_review["release_note"] = f"{phase_labels[target_phase]} is queued for revision."

    final_meta["stage_completeness"] = {
        **dict(final_meta.get("stage_completeness") or {}),
        "statuses": stage_statuses,
    }
    final_meta["phase_checkpoints"] = phase_checkpoints
    final_meta["release_review"] = release_review
    final_meta["runtime_phase_checkpoint"] = {
        **runtime_checkpoint,
        "stage_name": stage_name,
        "status": "pending",
        "message": f"Revision requested for {phase_labels[target_phase]}.",
        "yielded": True,
    }
    final_plan["meta"] = final_meta
    final_plan["release_ready"] = False
    final_plan["export_ready"] = False
    final_plan["release_status"] = "review"

    run_summary = dict(result_metadata.get("run_summary") or {})
    if run_summary:
        run_summary["phase_checkpoints"] = phase_checkpoints
        run_summary["combined_view"] = dict(combined_view)
        reliability_summary = dict(run_summary.get("reliability_summary") or {})
        reliability_summary["release_ready"] = False
        reliability_summary["operational_state"] = "review"
        run_summary["reliability_summary"] = reliability_summary
    result_metadata["run_summary"] = run_summary
    result_metadata["runtime_phase_checkpoint"] = dict(final_meta["runtime_phase_checkpoint"])
    result_metadata["runtime_should_continue"] = True
    latest_result["final_plan"] = final_plan
    latest_result["metadata"] = result_metadata

    project_input = dict(project.get("project_input") or {})
    revised_payload = dict(job.get("payload") or {})
    revised_payload.update(project_input)
    revised_payload["project_id"] = project_id

    project_store.save_project(
        user_id=user_id,
        project_id=project_id,
        name=str(project.get("name") or "Untitled Project"),
        description=str(project.get("description") or ""),
        session_id=project.get("session_id"),
        tags=list(project.get("tags") or []),
        project_input=project_input,
        latest_result=latest_result,
        session_state=dict(project.get("session_state") or {}),
        metadata=dict(project.get("metadata") or {}),
    )

    revised_job = job_queue.revise_job(
        user_id=user_id,
        job_id=job_id,
        payload=revised_payload,
    )
    if revised_job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "success": True,
        "job": revised_job,
        "operational_summary": {
            "status": str(revised_job.get("status") or "queued"),
            "job_type": str(revised_job.get("job_type") or "orchestrate"),
            "job_bound": bool(revised_job.get("job_id")),
            "project_bound": bool(revised_job.get("project_id")),
            "project_id": revised_job.get("project_id"),
            "job_id": revised_job.get("job_id"),
            "retryable": True,
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
    def _is_benign_skip_message(message: str) -> bool:
        lowered = str(message or "").strip().lower()
        if not lowered:
            return False
        return any(
            token in lowered
            for token in (
                "skipped because canonical state is already clean",
                "was not requested",
                "omitted by user intent",
                "source=omit",
                "no profile or cross-section deliverables were requested",
            )
        )

    def _normalize_completed_phase_checkpoints(
        phase_checkpoints: Dict[str, Any],
        *,
        release_status: str,
        release_ready: bool,
        blocked_exports: list[str],
        blocked_reasons: list[str],
        failed_deliverables: list[str],
        manual_failures: list[Dict[str, Any]],
    ) -> Dict[str, Any]:
        normalized = {
            str(name): dict(value)
            for name, value in dict(phase_checkpoints or {}).items()
            if isinstance(value, dict)
        }
        if not normalized:
            return {}
        if release_status != "ready" or blocked_exports or blocked_reasons or failed_deliverables or manual_failures:
            combined = dict(normalized.get("combined_view") or {})
            blockers = list(
                dict.fromkeys(
                    list(blocked_reasons or [])
                    + list(blocked_exports or [])
                    + [
                        f"failed_deliverable_{safe_str(item).lower().replace(' ', '_')}"
                        for item in failed_deliverables
                        if safe_str(item)
                    ]
                    + [
                        f"manual_validation_{safe_str(item.get('code') or 'manual_validation_failure').lower().replace(' ', '_')}"
                        for item in manual_failures
                        if isinstance(item, dict)
                    ]
                )
            )
            combined["label"] = str(combined.get("label") or "Combined View")
            combined["status"] = "blocked" if blockers or release_status == "blocked" else "review"
            combined["ready"] = False
            combined["blocked_reasons"] = blockers
            combined["blocked_exports"] = list(blocked_exports or [])
            combined["note"] = "Combined engineering view is blocked by release gates." if blockers else "Combined engineering view needs engineering review."
            normalized["combined_view"] = combined
            return normalized

        for name, phase in normalized.items():
            if name == "combined_view":
                continue
            if str(phase.get("status") or "").lower() == "running":
                continue
            if list(phase.get("blockers") or []) or list(phase.get("blocked_reasons") or []):
                continue
            has_data = bool(phase.get("has_data"))
            deliverables = list(phase.get("deliverables") or [])
            benign_skip = any(_is_benign_skip_message(message) for message in list(phase.get("messages") or []))
            if has_data or not deliverables or benign_skip:
                phase["status"] = "complete"
                phase["ready"] = True

        inferred_total = len([name for name in normalized.keys() if name != "combined_view"])
        combined = dict(normalized.get("combined_view") or {})
        total_phase_count = max(
            1,
            int(combined.get("total_phase_count") or 0),
            inferred_total,
        )
        combined["label"] = str(combined.get("label") or "Combined View")
        combined["status"] = "ready"
        combined["ready"] = bool(release_ready)
        combined["completed_phase_count"] = total_phase_count
        combined["total_phase_count"] = total_phase_count
        combined["blocked_exports"] = []
        combined["blocked_reasons"] = []
        combined["note"] = "Combined engineering view is release-ready."
        normalized["combined_view"] = combined
        return normalized

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
        latest_result = _load_project_latest_result(
            project_store=project_store,
            user_id=user_id,
            project_id=project_id,
            fallback_project=existing,
        )
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
        phase_to_stages = {
            "layout": ("layout",),
            "grading": ("grading",),
            "drainage_storm": ("drainage", "storm_pipes"),
            "utilities": ("sanitary", "utility_network"),
            "coordination_validation": ("coordination_resolution", "qa"),
        }
        stage_statuses = dict(
            dict(
                dict(dict(latest_result.get("final_plan") or {}).get("meta") or {})
                .get("stage_completeness")
                or {}
            ).get("statuses")
            or {}
        )
        existing_phase_checkpoints = dict(
            dict(dict(latest_result.get("final_plan") or {}).get("meta") or {}).get("phase_checkpoints")
            or dict(dict(latest_result.get("metadata") or {}).get("run_summary") or {}).get("phase_checkpoints")
            or {}
        )
        if existing_phase_checkpoints:
            phase_checkpoints = {
                **existing_phase_checkpoints,
                **phase_checkpoints,
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
        if stage_name:
            normalized_status = {
                "running": "running",
                "complete": "complete",
                "failed": "failed",
            }.get(str(status or "").strip().lower(), str(status or "").strip().lower() or "pending")
            if normalized_status:
                stage_statuses[stage_name] = normalized_status

        def _normalized_stage_state(stage_key: str) -> str:
            raw = str(stage_statuses.get(stage_key) or "").strip().lower()
            if raw == "complete":
                return "complete"
            if raw == "assumed":
                return "partial"
            if raw in {"running", "in_progress", "started"}:
                return "running"
            if raw == "failed":
                return "failed"
            return "pending"

        def _phase_status_from_stage_states(states: list[str]) -> str:
            non_pending_states = [state for state in states if state != "pending"]
            if not non_pending_states:
                return "pending"
            if any(state == "failed" for state in non_pending_states):
                return "failed"
            if all(state == "complete" for state in non_pending_states):
                return "complete"
            if any(state == "running" for state in non_pending_states):
                return "running"
            return "partial"

        for phase_name in phase_order:
            phase_entry = dict(phase_checkpoints.get(phase_name) or {})
            phase_states = [_normalized_stage_state(stage_key) for stage_key in phase_to_stages.get(phase_name, ())]
            phase_status = _phase_status_from_stage_states(phase_states)
            phase_entry["status"] = phase_status
            phase_entry["ready"] = phase_status == "complete"
            if target_phase == phase_name:
                phase_entry["job_progress"] = int(progress or 0)
                messages = [str(item) for item in list(phase_entry.get("messages") or []) if str(item).strip()]
                if detail and detail not in messages:
                    messages.append(detail)
                phase_entry["messages"] = messages[-3:]
            phase_checkpoints[phase_name] = phase_entry

        completed_phase_count = sum(
            1 for name in phase_order if bool(dict(phase_checkpoints.get(name) or {}).get("ready"))
        )
        if any(str(stage_statuses.get(name) or "").strip().lower() == "failed" for name in stage_statuses):
            combined_status = "blocked"
        elif completed_phase_count >= len(phase_order):
            combined_status = "ready"
        elif any(str(stage_statuses.get(name) or "").strip().lower() == "running" for name in stage_statuses):
            combined_status = "running"
        elif completed_phase_count > 0:
            combined_status = "partial"
        else:
            combined_status = "pending"
        combined_view = {
            "label": "Combined View",
            "status": combined_status,
            "ready": combined_status == "ready",
            "completed_phase_count": completed_phase_count,
            "total_phase_count": len(phase_order),
            "current_stage": stage_name,
            "current_status": status,
            "job_progress": int(progress or 0),
            "note": "Run is advancing through persisted engineering phases.",
            "messages": [detail] if detail else [],
            "deliverables": [],
            "blockers": [],
        }
        phase_checkpoints["combined_view"] = combined_view
        run_summary["phase_checkpoints"] = phase_checkpoints
        run_summary["stage_summary"] = {
            "current_stage": stage_name,
            "current_status": status,
            "current_detail": detail,
            "progress": int(progress or 0),
        }
        run_summary["reliability_summary"] = dict(run_summary.get("reliability_summary") or {})
        run_summary["combined_view"] = dict(combined_view)

        checkpoint_result = dict(latest_result)
        if checkpoint:
            checkpoint_result["final_plan"] = dict(checkpoint)
        checkpoint_final_plan = dict(checkpoint_result.get("final_plan") or {})
        checkpoint_meta = dict(checkpoint_final_plan.get("meta") or {})
        checkpoint_meta["phase_checkpoints"] = phase_checkpoints
        checkpoint_meta["stage_completeness"] = {
            **dict(checkpoint_meta.get("stage_completeness") or {}),
            "statuses": stage_statuses,
        }
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
        metadata = dict(enriched.get("metadata") or {})
        runtime_checkpoint = dict(metadata.get("runtime_phase_checkpoint") or {})
        try:
            enriched["final_plan"] = final_plan_from_result(
                enriched,
                enforce_export_guards=False,
            )
        except Exception:
            pass
        final_plan = dict(enriched.get("final_plan") or {})
        final_meta = dict(final_plan.get("meta") or {})
        if not runtime_checkpoint:
            runtime_checkpoint = dict(final_meta.get("runtime_phase_checkpoint") or {})
        runtime_should_continue = metadata.get("runtime_should_continue")
        if runtime_should_continue is None:
            runtime_should_continue = bool(runtime_checkpoint.get("yielded"))

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
            construction_release_required = final_plan_requires_construction_release(final_plan)
            for construction_blocker in construction_release_blockers_from_meta(
                final_meta,
                requires_construction_release=construction_release_required,
            ):
                if construction_blocker not in blocked_reasons:
                    blocked_reasons.append(construction_blocker)
            final_release_review = safe_dict(final_meta.get("release_review"))
            if final_release_review.get("release_ready") is False and "release_review_not_ready" not in blocked_reasons:
                blocked_reasons.append("release_review_not_ready")
            if final_meta.get("release_ready") is False and "final_plan_release_blocked" not in blocked_reasons:
                blocked_reasons.append("final_plan_release_blocked")
            reactive_report = safe_dict(final_meta.get("reactive_update_report"))
            if reactive_report.get("post_rerun_production_ready") is False and "reactive_post_rerun_not_ready" not in blocked_reasons:
                blocked_reasons.append("reactive_post_rerun_not_ready")
            for reactive_blocker in safe_list(reactive_report.get("post_rerun_release_blockers")):
                reactive_blocker_name = safe_str(reactive_blocker)
                if reactive_blocker_name and reactive_blocker_name not in blocked_reasons:
                    blocked_reasons.append(reactive_blocker_name)
            final_deliverables = dict(final_meta.get("deliverables") or final_plan.get("deliverables") or {})

            def _merged_deliverables(run_key: str, final_key: str) -> list[str]:
                values = list(run_summary.get(run_key) or []) + list(final_deliverables.get(final_key) or [])
                return list(dict.fromkeys([safe_str(item) for item in values if safe_str(item)]))

            requested_deliverables = _merged_deliverables("requested_deliverables", "requested")
            produced_deliverables = _merged_deliverables("produced_deliverables", "produced")
            failed_deliverables = _merged_deliverables("failed_deliverables", "failed")
            ready_deliverables = _merged_deliverables("ready_deliverables", "ready")
            extra_deliverables = _merged_deliverables("extra_deliverables", "extra")
            final_manual_validation = safe_dict(final_meta.get("manual_validation"))
            manual_failures: list[Dict[str, Any]] = []
            for failure in list(run_summary.get("manual_failures") or []) + list(final_manual_validation.get("failures") or []):
                if not isinstance(failure, dict):
                    continue
                failure_key = safe_str(
                    failure.get("code")
                    or failure.get("rule")
                    or failure.get("system")
                    or failure.get("reason")
                    or failure.get("message")
                    or "manual_validation_failure"
                )
                if not failure_key:
                    failure_key = "manual_validation_failure"
                failure_record = dict(failure)
                failure_record.setdefault("code", failure_key)
                if failure_record not in manual_failures:
                    manual_failures.append(failure_record)
            run_summary["requested_deliverables"] = requested_deliverables
            run_summary["produced_deliverables"] = produced_deliverables
            run_summary["failed_deliverables"] = failed_deliverables
            run_summary["ready_deliverables"] = ready_deliverables
            run_summary["extra_deliverables"] = extra_deliverables
            run_summary["manual_failures"] = manual_failures
            failed_deliverable_blockers = [
                f"failed_deliverable_{safe_str(item).lower().replace(' ', '_')}"
                for item in failed_deliverables
                if safe_str(item)
            ]
            for failed_blocker in failed_deliverable_blockers:
                if failed_blocker not in blocked_reasons:
                    blocked_reasons.append(failed_blocker)
            produced_set = {safe_str(item) for item in produced_deliverables if safe_str(item)}
            failed_set = {safe_str(item) for item in failed_deliverables if safe_str(item)}
            missing_deliverables = [
                safe_str(item)
                for item in requested_deliverables
                if safe_str(item) and safe_str(item) not in produced_set and safe_str(item) not in failed_set
            ]
            run_summary["missing_deliverables"] = missing_deliverables
            reliability["missing_deliverable_count"] = len(missing_deliverables)
            for missing_deliverable in missing_deliverables:
                missing_blocker = f"missing_deliverable_{missing_deliverable.lower().replace(' ', '_')}"
                if missing_blocker not in blocked_reasons:
                    blocked_reasons.append(missing_blocker)
            for manual_failure in manual_failures:
                failure_key = safe_str(manual_failure.get("code") or "manual_validation_failure")
                if not failure_key:
                    failure_key = "manual_validation_failure"
                manual_blocker = f"manual_validation_{failure_key.lower().replace(' ', '_')}"
                if manual_blocker not in blocked_reasons:
                    blocked_reasons.append(manual_blocker)
            convergence["blocked_reasons"] = list(blocked_reasons)
            reliability["release_ready"] = not bool(blocked_reasons or blocked_exports or failed_deliverables or manual_failures)
            reliability["blocked_export_count"] = len(blocked_exports)
            reliability["manual_failure_count"] = len(manual_failures)
            if blocked_reasons or blocked_exports:
                reliability["primary_attention"] = (blocked_reasons[:1] or blocked_exports[:1])[0]
            elif failed_deliverables:
                reliability["primary_attention"] = failed_deliverables[0]
            release_status = "blocked" if (blocked_reasons or blocked_exports or failed_deliverables or manual_failures) else ("ready" if bool(reliability.get("release_ready")) else "review")
            release_note = (
                "Blocked until outstanding export issues are resolved."
                if release_status == "blocked"
                else ("Release-ready engineering state." if release_status == "ready" else "Needs engineering review before release.")
            )
            normalized_phase_checkpoints = _normalize_completed_phase_checkpoints(
                dict(run_summary.get("phase_checkpoints") or {}),
                release_status=release_status,
                release_ready=bool(reliability.get("release_ready")),
                blocked_exports=blocked_exports,
                blocked_reasons=blocked_reasons,
                failed_deliverables=failed_deliverables,
                manual_failures=manual_failures,
            )
            combined_checkpoint = dict(normalized_phase_checkpoints.get("combined_view") or {})
            total_phase_count = int(combined_checkpoint.get("total_phase_count") or 0)
            completed_phase_count = int(combined_checkpoint.get("completed_phase_count") or 0)
            completion_implies_ready = (
                not blocked_reasons
                and not blocked_exports
                and not failed_deliverables
                and not manual_failures
                and not bool(runtime_checkpoint.get("yielded"))
                and total_phase_count > 0
                and completed_phase_count >= total_phase_count
            )
            if completion_implies_ready and release_status != "ready":
                reliability["release_ready"] = True
                release_status = "ready"
                release_note = "Release-ready engineering state."
                normalized_phase_checkpoints = _normalize_completed_phase_checkpoints(
                    dict(run_summary.get("phase_checkpoints") or {}),
                    release_status=release_status,
                    release_ready=True,
                    blocked_exports=blocked_exports,
                    blocked_reasons=blocked_reasons,
                    failed_deliverables=failed_deliverables,
                    manual_failures=manual_failures,
                )
            if normalized_phase_checkpoints:
                run_summary["phase_checkpoints"] = normalized_phase_checkpoints
                run_summary["combined_view"] = dict(normalized_phase_checkpoints.get("combined_view") or {})
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
                "release_status": release_status,
                "release_note": release_note,
                "release_ready": bool(reliability.get("release_ready")),
                "manual_failures": manual_failures,
            }
            final_meta["blockers"] = blocked_reasons or blocked_exports
            final_meta["export_ready"] = not bool(blocked_reasons or blocked_exports or failed_deliverables or manual_failures)
            final_meta["release_ready"] = bool(reliability.get("release_ready"))
            final_meta["release_status"] = release_status
            final_meta["deliverables"] = {
                "requested": requested_deliverables,
                "produced": produced_deliverables,
                "failed": failed_deliverables,
                "ready": ready_deliverables,
                "extra": extra_deliverables,
                "missing": missing_deliverables,
            }
            final_plan["meta"] = final_meta
            final_plan["export_ready"] = not bool(blocked_reasons or blocked_exports or failed_deliverables or manual_failures)
            final_plan["release_ready"] = bool(reliability.get("release_ready"))
            final_plan["release_status"] = release_status
            final_plan["blockers"] = blocked_reasons or blocked_exports
            final_plan["deliverables"] = {
                "requested": requested_deliverables,
                "produced": produced_deliverables,
                "failed": failed_deliverables,
                "ready": ready_deliverables,
                "extra": extra_deliverables,
                "missing": missing_deliverables,
            }
            enriched["final_plan"] = final_plan

        metadata = dict(enriched.get("metadata") or {})
        if runtime_checkpoint:
            metadata["runtime_phase_checkpoint"] = runtime_checkpoint
        metadata["runtime_should_continue"] = bool(runtime_should_continue)
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
        run_payload = dict(payload)
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
        existing = None
        if project_id and user_id:
            existing = project_store.get_project(user_id=user_id, project_id=project_id)
        if existing is not None:
                existing_result = _load_project_latest_result(
                    project_store=project_store,
                    user_id=user_id,
                    project_id=project_id,
                    fallback_project=existing,
                )
                existing_final_plan = dict(existing_result.get("final_plan") or {})
                existing_meta = dict(existing_final_plan.get("meta") or {})
                stage_statuses = dict(
                    dict(existing_meta.get("stage_completeness") or {}).get("statuses") or {}
                )
                phase_checkpoints = dict(
                    existing_meta.get("phase_checkpoints")
                    or dict(dict(existing_result.get("metadata") or {}).get("run_summary") or {}).get("phase_checkpoints")
                    or {}
                )
                if existing_final_plan and (stage_statuses or phase_checkpoints):
                    runtime_resume = {
                        "project_id": project_id,
                        "stage_statuses": stage_statuses,
                        "phase_checkpoints": phase_checkpoints,
                        "final_plan": existing_final_plan,
                    }
                    run_meta = dict(run_payload.get("meta") or {})
                    orchestrator_meta = dict(run_meta.get("orchestrator_meta") or {})
                    orchestrator_meta["runtime_resume"] = runtime_resume
                    run_meta["orchestrator_meta"] = orchestrator_meta
                    run_meta["runtime_resume"] = runtime_resume
                    run_payload["meta"] = run_meta
        run_meta = dict(run_payload.get("meta") or {})
        orchestrator_meta = dict(run_meta.get("orchestrator_meta") or {})
        requested_batch_limit = safe_int(orchestrator_meta.get("runtime_phase_batch_limit"), 0)
        if requested_batch_limit <= 0:
            requested_batch_limit = safe_int(run_meta.get("runtime_phase_batch_limit"), 0)
        if requested_batch_limit <= 0:
            requested_batch_limit = 1
        orchestrator_meta["runtime_phase_batch_limit"] = requested_batch_limit
        run_meta["orchestrator_meta"] = orchestrator_meta
        run_meta["runtime_phase_batch_limit"] = requested_batch_limit
        run_payload["meta"] = run_meta
        run_signature = inspect.signature(run_orchestration)
        if "progress_callback" in run_signature.parameters:
            result = run_orchestration(run_payload, progress_callback=_phase_progress_callback)
        else:
            result = run_orchestration(run_payload)
        enriched = _normalized_result_for_ui(
            result,
            project_id=project_id,
            job_id=job_id,
            user_id=user_id,
        )
        enriched_metadata = dict(enriched.get("metadata") or {})
        runtime_checkpoint = dict(enriched_metadata.get("runtime_phase_checkpoint") or {})
        stage_name = str(runtime_checkpoint.get("stage_name") or "")
        runtime_should_continue = bool(enriched_metadata.get("runtime_should_continue"))
        if stage_name in {"coordination_resolution", "earthwork", "sheets", "qa"}:
            runtime_should_continue = False
            enriched_metadata["runtime_should_continue"] = False
            if runtime_checkpoint:
                runtime_checkpoint["yielded"] = False
                enriched_metadata["runtime_phase_checkpoint"] = runtime_checkpoint
            enriched["metadata"] = enriched_metadata
        if project_id and user_id:
            if job_id:
                update_job_progress(
                    job_id,
                    stage="Saving Project",
                    detail="Saving the latest design state back into the project.",
                    progress=76,
                )
            if existing is not None:
                existing_result = _load_project_latest_result(
                    project_store=project_store,
                    user_id=user_id,
                    project_id=project_id,
                    fallback_project=existing,
                )
                project_store.save_project(
                    user_id=user_id,
                    project_id=project_id,
                    name=existing.get("name", "Untitled Project"),
                    description=existing.get("description", ""),
                    session_id=existing.get("session_id"),
                    tags=existing.get("tags", []),
                    project_input=payload,
                    latest_result=enriched or existing_result,
                    session_state=existing.get("session_state", {}),
                    metadata=merge_project_metadata(
                        dict(existing.get("metadata") or {}),
                        run_summary=dict(dict(enriched.get("metadata") or {}).get("run_summary") or {}),
                    ),
                )
        if runtime_should_continue and job_id:
            update_job_progress(
                job_id,
                stage="Awaiting Approval",
                detail=f"Saved {stage_name or 'current'} checkpoint. Review it and approve when you want to continue.",
                progress=60,
            )
            return enriched
        if job_id:
            update_job_progress(
                job_id,
                stage="Finalizing",
                detail="Finalizing the run summary and preparing the result for the UI.",
                progress=92,
            )
        return enriched

    return orchestrate_runner


def build_drainage_job_runner(
    *,
    project_store: ProjectStoreProtocol,
    update_job_progress: Callable[..., None],
) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def _merge_manual_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(payload)
        manual_fields = dict(payload.get("manual_fields") or {})
        if manual_fields:
            from backend.planning.field_contract import unwrap_fields_for_execution
            for key, value in manual_fields.items():
                if key not in merged or merged[key] in (None, "", [], {}):
                    merged[key] = value
            drainage_fields = safe_dict(unwrap_fields_for_execution(manual_fields.get("drainage")))
            forced_inlets = safe_list(drainage_fields.get("forced_inlets"))
            connect_orphans = bool(drainage_fields.get("connect_orphans"))
            allow_slope_adjustment = bool(drainage_fields.get("allow_slope_adjustment"))
            max_slope_adjust = drainage_fields.get("max_slope_adjust")
            autofix_action = safe_str(drainage_fields.get("autofix_action"), "")
            if autofix_action == "adjust_slope" and not allow_slope_adjustment:
                allow_slope_adjustment = True
            if forced_inlets:
                drainage_payload = safe_dict(merged.get("drainage"))
                if not drainage_payload:
                    drainage_payload = {}
                if not drainage_payload.get("forced_inlets"):
                    drainage_payload["forced_inlets"] = deepcopy(forced_inlets)
                if connect_orphans and not drainage_payload.get("connect_orphans"):
                    drainage_payload["connect_orphans"] = True
                if allow_slope_adjustment and not drainage_payload.get("allow_slope_adjustment"):
                    drainage_payload["allow_slope_adjustment"] = True
                if max_slope_adjust is not None and drainage_payload.get("max_slope_adjust") is None:
                    drainage_payload["max_slope_adjust"] = max_slope_adjust
                if autofix_action and not drainage_payload.get("autofix_action"):
                    drainage_payload["autofix_action"] = autofix_action
                merged["drainage"] = drainage_payload
            elif connect_orphans or allow_slope_adjustment:
                drainage_payload = safe_dict(merged.get("drainage"))
                if not drainage_payload:
                    drainage_payload = {}
                if connect_orphans:
                    drainage_payload["connect_orphans"] = True
                if allow_slope_adjustment:
                    drainage_payload["allow_slope_adjustment"] = True
                if max_slope_adjust is not None and drainage_payload.get("max_slope_adjust") is None:
                    drainage_payload["max_slope_adjust"] = max_slope_adjust
                if autofix_action and not drainage_payload.get("autofix_action"):
                    drainage_payload["autofix_action"] = autofix_action
                merged["drainage"] = drainage_payload
        merged["manual_fields"] = manual_fields
        return merged

    def _build_stage_statuses(grading_ok: bool, drainage_ok: bool) -> Dict[str, Any]:
        return {
            "layout": "skipped",
            "grading": "complete" if grading_ok else "failed",
            "drainage": "complete" if drainage_ok else "failed",
            "storm_pipes": "pending",
            "sanitary": "pending",
            "utility_network": "pending",
            "coordination_resolution": "pending",
            "earthwork": "pending",
            "sheets": "pending",
            "qa": "pending",
        }

    def drainage_runner(job: Dict[str, Any]) -> Dict[str, Any]:
        payload = _merge_manual_fields(dict(job.get("payload") or {}))
        job_id = str(job.get("job_id") or "").strip()
        project_id = job.get("project_id")
        user_id = job.get("user_id")

        if job_id:
            update_job_progress(
                job_id,
                stage="Drainage Prep",
                detail="Preparing drainage-only execution context.",
                progress=36,
            )

        from copy import deepcopy
        from backend.planning.runtime import (
            _bootstrap_manager,
            _compute_hydrology_metrics,
            _register_default_dependencies,
            choose_routing_path,
            collect_plan_stats,
            normalize_parsed_payload,
            triple_check_parsed_payload,
        )
        from planner import (
            PlannerExecutionContext,
            _ingest_parsed_into_model,
            _run_drainage_stage,
            _run_grading_stage,
            project_model_to_plan,
            rect_zone,
            ZoneType,
        )

        from backend.planning.field_contract import unwrap_fields_for_execution

        parsed = triple_check_parsed_payload(normalize_parsed_payload(payload))
        forced_inlets = safe_list(safe_dict(parsed.get("drainage")).get("forced_inlets"))
        allow_slope_adjustment = bool(safe_dict(parsed.get("drainage")).get("allow_slope_adjustment"))
        if not forced_inlets or not allow_slope_adjustment:
            raw_manual_fields = safe_dict(payload.get("manual_fields"))
            manual_drainage = safe_dict(unwrap_fields_for_execution(raw_manual_fields.get("drainage")))
            manual_forced = safe_list(manual_drainage.get("forced_inlets"))
            manual_allow_slope = bool(manual_drainage.get("allow_slope_adjustment"))
            manual_autofix_action = safe_str(manual_drainage.get("autofix_action"), "")
            raw_ponds = raw_manual_fields.get("ponds")
            if isinstance(raw_ponds, dict):
                raw_ponds = raw_ponds.get("value")
            if raw_ponds:
                incoming = [safe_dict(item) for item in safe_list(raw_ponds) if isinstance(item, dict)]
                existing = [safe_dict(item) for item in safe_list(parsed.get("ponds")) if isinstance(item, dict)]
                seen_ids = {safe_str(item.get("id"), "") for item in existing if safe_str(item.get("id"), "")}
                merged = list(existing)
                for pond in incoming:
                    pond_id = safe_str(pond.get("id"), "")
                    if pond_id and pond_id in seen_ids:
                        continue
                    if not pond_id:
                        # Avoid duplicate coordinates.
                        if any(
                            safe_float(p.get("x"), 0.0) == safe_float(pond.get("x"), 0.0)
                            and safe_float(p.get("y"), 0.0) == safe_float(pond.get("y"), 0.0)
                            and safe_float(p.get("w"), 0.0) == safe_float(pond.get("w"), 0.0)
                            and safe_float(p.get("d"), 0.0) == safe_float(pond.get("d"), 0.0)
                            for p in merged
                        ):
                            continue
                    merged.append(pond)
                    if pond_id:
                        seen_ids.add(pond_id)
                if merged:
                    parsed["ponds"] = merged
            raw_manual_drainage = safe_dict(raw_manual_fields.get("drainage"))
            raw_allow = raw_manual_drainage.get("allow_slope_adjustment")
            if isinstance(raw_allow, dict):
                raw_allow = raw_allow.get("value")
            if raw_allow is not None:
                manual_allow_slope = bool(raw_allow)
            raw_autofix_action = raw_manual_drainage.get("autofix_action")
            if isinstance(raw_autofix_action, dict):
                raw_autofix_action = raw_autofix_action.get("value")
            if raw_autofix_action:
                manual_autofix_action = safe_str(raw_autofix_action, manual_autofix_action)
            if manual_forced:
                forced_inlets = manual_forced
                parsed.setdefault("drainage", {})["forced_inlets"] = deepcopy(manual_forced)
            if manual_allow_slope and not allow_slope_adjustment:
                parsed.setdefault("drainage", {})["allow_slope_adjustment"] = True
                allow_slope_adjustment = True
            if manual_autofix_action and not safe_str(safe_dict(parsed.get("drainage")).get("autofix_action"), ""):
                parsed.setdefault("drainage", {})["autofix_action"] = manual_autofix_action
            if manual_autofix_action == "adjust_slope":
                parsed.setdefault("drainage", {})["allow_slope_adjustment"] = True
                allow_slope_adjustment = True
        route = choose_routing_path(parsed)
        manager = _bootstrap_manager(parsed)
        _register_default_dependencies(manager)

        ctx = PlannerExecutionContext(
            parsed=deepcopy(parsed),
            manager=manager,
            route=route,
            option_name="Drainage Only",
            option_family="drainage_only",
        )
        _ingest_parsed_into_model(ctx)

        try:
            site_plan = safe_dict(parsed.get("site_plan"))
            parking_count = safe_float(site_plan.get("parking_count"), 0.0)
            if parking_count > 0 and manager.project.zones:
                has_parking_zone = any(
                    getattr(zone, "zone_type", None) == ZoneType.PARKING
                    for zone in manager.project.zones.values()
                )
            else:
                has_parking_zone = False
            if parking_count > 0 and not has_parking_zone:
                lot = safe_dict(parsed.get("lot"))
                lot_x = safe_float(lot.get("x"), 0.0)
                lot_y = safe_float(lot.get("y"), 0.0)
                lot_w = safe_float(lot.get("w"), 600.0)
                lot_h = safe_float(lot.get("h"), 600.0)
                parking_w = max(lot_w * 0.5, 60.0)
                parking_h = max(lot_h * 0.25, 40.0)
                parking_x = lot_x + (lot_w - parking_w) / 2.0
                parking_y = lot_y + (lot_h - parking_h) / 2.0
                manager.project.add_zone(
                    rect_zone(
                        parking_x,
                        parking_y,
                        parking_w,
                        parking_h,
                        zone_type=ZoneType.PARKING,
                        name="PARKING_FIELD",
                    )
                )
        except Exception:
            pass

        preliminary_plan = project_model_to_plan(manager.project, parsed.get("project_name") or "Drainage Run")
        preliminary_stats = collect_plan_stats(preliminary_plan)
        hydrology = _compute_hydrology_metrics(parsed, preliminary_stats)

        if job_id:
            update_job_progress(
                job_id,
                stage="Grading",
                detail="Building grading surface for drainage.",
                progress=48,
            )
        grading_ok = True
        try:
            _run_grading_stage(ctx, hydrology)
        except Exception as exc:
            grading_ok = False
            ctx.record_error(f"Grading failed in drainage-only runner: {exc}")

        # Ensure any provided ponds/basins are registered on the project model
        # before running drainage so the engine can target them.
        try:
            from core.geometry_core import EngineeringDomain, EngineeringObject, Point3D, ZoneType, rect_zone

            existing_objects = getattr(manager.project, "objects", {}) or {}
            existing_zones = getattr(manager.project, "zones", {}) or {}
            for pond in [item for item in safe_list(parsed.get("ponds")) if isinstance(item, dict)]:
                pond_id = safe_str(pond.get("id"), "").strip() or f"pond-{job_id or 'auto'}"
                if pond_id in existing_objects or pond_id in existing_zones:
                    continue
                basin_x = safe_float(pond.get("x"), 0.0)
                basin_y = safe_float(pond.get("y"), 0.0)
                basin_w = safe_float(pond.get("w"), 40.0)
                basin_d = safe_float(pond.get("d"), 30.0)
                basin_name = safe_str(pond.get("name"), "Basin")
                basin_zone = rect_zone(
                    basin_x,
                    basin_y,
                    basin_w,
                    basin_d,
                    zone_type=ZoneType.DETENTION,
                    name=basin_name,
                )
                manager.project.add_zone(basin_zone)
                manager.project.add_object(
                    EngineeringObject(
                        id=pond_id,
                        kind="detention_basin",
                        name=basin_name,
                        anchor=Point3D(basin_x + basin_w / 2.0, basin_y + basin_d / 2.0, DEFAULT_PAD_ELEV),
                        boundary=basin_zone.boundary,
                        tags=["drainage", "basin"],
                        domain=EngineeringDomain.DRAINAGE,
                        properties={
                            "width": basin_w,
                            "depth": basin_d,
                            "canonical_id": pond_id,
                            "source": safe_str(pond.get("source"), ""),
                            "generated": bool(pond.get("generated")),
                        },
                    )
                )
        except Exception:
            pass

        # Drainage autofix: add basin at the best available low point before running drainage.
        autofix_action = safe_str(safe_dict(parsed.get("drainage")).get("autofix_action"), "")
        if not autofix_action:
            payload_drainage = safe_dict(payload.get("drainage"))
            raw_autofix = payload_drainage.get("autofix_action")
            if isinstance(raw_autofix, dict):
                raw_autofix = raw_autofix.get("value")
            autofix_action = safe_str(raw_autofix, "")
        if not autofix_action:
            raw_manual_fields = safe_dict(payload.get("manual_fields"))
            manual_drainage = safe_dict(unwrap_fields_for_execution(raw_manual_fields.get("drainage")))
            raw_autofix = manual_drainage.get("autofix_action")
            if isinstance(raw_autofix, dict):
                raw_autofix = raw_autofix.get("value")
            autofix_action = safe_str(raw_autofix, "")
        if autofix_action and safe_str(safe_dict(parsed.get("drainage")).get("autofix_action"), "") != autofix_action:
            parsed.setdefault("drainage", {})["autofix_action"] = autofix_action
            ctx.parsed.setdefault("drainage", {})["autofix_action"] = autofix_action
        if autofix_action == "add_basin":
            ponds = [item for item in safe_list(parsed.get("ponds")) if isinstance(item, dict)]
            has_autofix = any(
                safe_str(pond.get("source"), "") == "autofix"
                or safe_str(pond.get("id"), "").startswith("autofix-basin")
                for pond in ponds
                if isinstance(pond, dict)
            )
            if not has_autofix:
                grading_meta = safe_dict(manager.project.meta.get("grading_canonical") or manager.project.meta.get("grading"))
                low_points = safe_list(grading_meta.get("low_points") or grading_meta.get("low_points_xy"))
                ranked = [
                    safe_dict(item) for item in low_points if isinstance(item, dict) and item.get("x") is not None and item.get("y") is not None
                ]
                if ranked:
                    ranked.sort(key=lambda item: safe_float(item.get("z"), 0.0))
                    target = ranked[0]
                    basin_x = safe_float(target.get("x"), 0.0)
                    basin_y = safe_float(target.get("y"), 0.0)
                else:
                    lot = safe_dict(parsed.get("lot"))
                    lot_x = safe_float(lot.get("x"), 0.0)
                    lot_y = safe_float(lot.get("y"), 0.0)
                    lot_w = safe_float(lot.get("w"), 600.0)
                    lot_h = safe_float(lot.get("h"), 600.0)
                    basin_x = lot_x + lot_w * 0.8
                    basin_y = lot_y + lot_h * 0.8

                basin_w = 40.0
                basin_d = 30.0
                basin_id = f"autofix-basin-{job_id or 'auto'}"
                basin_name = "Autofix Basin"
                new_basin = {
                    "id": basin_id,
                    "name": basin_name,
                    "x": basin_x,
                    "y": basin_y,
                    "w": basin_w,
                    "d": basin_d,
                    "source": "autofix",
                    "generated": True,
                }
                ponds.append(new_basin)
                parsed["ponds"] = ponds
                ctx.parsed["ponds"] = ponds

                try:
                    from core.geometry_core import EngineeringDomain, EngineeringObject, Point3D, ZoneType, rect_zone

                    basin_zone = rect_zone(
                        basin_x,
                        basin_y,
                        basin_w,
                        basin_d,
                        zone_type=ZoneType.DETENTION,
                        name=basin_name,
                    )
                    manager.project.add_zone(basin_zone)
                    manager.project.add_object(
                        EngineeringObject(
                            id=basin_id,
                            kind="detention_basin",
                            name=basin_name,
                            anchor=Point3D(basin_x + basin_w / 2.0, basin_y + basin_d / 2.0, DEFAULT_PAD_ELEV),
                            boundary=basin_zone.boundary,
                            tags=["drainage", "basin"],
                            domain=EngineeringDomain.DRAINAGE,
                            properties={
                                "width": basin_w,
                                "depth": basin_d,
                                "canonical_id": basin_id,
                                "source": "autofix",
                                "generated": True,
                            },
                        )
                    )
                except Exception:
                    pass

        if job_id:
            update_job_progress(
                job_id,
                stage="Drainage",
                detail="Generating drainage network.",
                progress=68,
            )
        drainage_ok = True
        try:
            _run_drainage_stage(ctx, hydrology)
        except Exception as exc:
            drainage_ok = False
            ctx.record_error(f"Drainage failed in drainage-only runner: {exc}")

        final_plan = project_model_to_plan(manager.project, parsed.get("project_name") or "Drainage Run")
        final_meta = dict(final_plan.get("meta") or {})
        grading_canonical = deepcopy(manager.project.meta.get("grading_canonical") or {})
        drainage_canonical = deepcopy(manager.project.meta.get("drainage_canonical") or {})
        user_ponds = [item for item in safe_list(parsed.get("ponds")) if isinstance(item, dict)]
        drainage_canonical["basins"] = deepcopy(user_ponds)
        if forced_inlets and not safe_list(drainage_canonical.get("inlets")):
            drainage_canonical["inlets"] = [
                {
                    "name": safe_str(item.get("name"), f"INLET-{idx + 1}"),
                    "x": safe_float(item.get("x"), 0.0),
                    "y": safe_float(item.get("y"), 0.0),
                    "source": "forced_inlets",
                }
                for idx, item in enumerate(safe_list(forced_inlets))
                if isinstance(item, dict)
            ]
        connect_orphans = bool(safe_dict(parsed.get("drainage")).get("connect_orphans"))
        if (
            connect_orphans
            and safe_list(drainage_canonical.get("inlets"))
            and safe_list(drainage_canonical.get("basins"))
            and not safe_list(drainage_canonical.get("pipe_runs"))
        ):
            inlet = safe_list(drainage_canonical.get("inlets"))[0]
            basin = safe_list(drainage_canonical.get("basins"))[0]
            if isinstance(inlet, dict) and isinstance(basin, dict):
                inlet_x = safe_float(inlet.get("x"), 0.0)
                inlet_y = safe_float(inlet.get("y"), 0.0)
                basin_x = safe_float(basin.get("x"), 0.0)
                basin_y = safe_float(basin.get("y"), 0.0)
                drainage_canonical["pipe_runs"] = [
                    {
                        "id": f"RUN-{job_id or 'AUTO'}",
                        "points": [
                            {"x": inlet_x, "y": inlet_y},
                            {"x": basin_x, "y": basin_y},
                        ],
                        "source": "connect_orphans",
                    }
                ]
        final_meta["grading"] = grading_canonical
        final_meta["drainage"] = drainage_canonical
        final_meta["drainage_canonical"] = drainage_canonical
        final_meta["stage_completeness"] = {
            "statuses": _build_stage_statuses(grading_ok, drainage_ok),
        }
        final_plan["meta"] = final_meta

        result = {
            "project_input": parsed,
            "request_metadata": {"project_input": parsed},
            "final_plan": final_plan,
            "issues": deepcopy(safe_list(drainage_canonical.get("issues"))),
            "metadata": {
                "runtime_should_continue": False,
                "runtime_phase_checkpoint": {},
                "job_context": {
                    "job_id": job_id,
                    "job_type": "drainage_only",
                    "project_id": project_id,
                    "user_id": user_id,
                    "source": "job_queue",
                },
            },
        }

        if manager.conflicts:
            result["issues"] = [
                {
                    "code": conflict.code,
                    "message": conflict.message,
                    "severity": str(conflict.severity),
                    "context": dict(conflict.context or {}),
                }
                for conflict in manager.conflicts
            ]
        else:
            fallback_issues = []
            basin_count = len(safe_list(drainage_canonical.get("basins")))
            inlet_count = len(safe_list(drainage_canonical.get("inlets")))
            run_count = len(safe_list(drainage_canonical.get("pipe_runs") or drainage_canonical.get("runs")))
            if basin_count == 0:
                fallback_issues.append(
                    {
                        "code": "NO_PONDS_DEFINED",
                        "message": "No basin/outfall is defined for drainage routing.",
                        "severity": "warning",
                        "context": {},
                    }
                )
            if inlet_count > 0 and run_count == 0:
                fallback_issues.append(
                    {
                        "code": "ORPHAN_INLETS",
                        "message": "Inlets are present but not connected to a drainage run.",
                        "severity": "warning",
                        "context": {},
                    }
                )
            if basin_count > 0 and run_count == 0:
                fallback_issues.append(
                    {
                        "code": "NO_FLOW_PATHS",
                        "message": "No valid flow paths were generated to the basin.",
                        "severity": "warning",
                        "context": {},
                    }
                )
            if fallback_issues:
                result["issues"] = fallback_issues
        drainage_flags = safe_dict(parsed.get("drainage"))
        allow_slope_adjustment = bool(drainage_flags.get("allow_slope_adjustment"))
        slope_autofix_requested = safe_str(drainage_flags.get("autofix_action"), "") == "adjust_slope"
        raw_manual_fields = safe_dict(payload.get("manual_fields"))
        raw_manual_drainage = safe_dict(raw_manual_fields.get("drainage"))
        raw_allow = raw_manual_drainage.get("allow_slope_adjustment")
        if isinstance(raw_allow, dict):
            raw_allow = raw_allow.get("value")
        raw_autofix = raw_manual_drainage.get("autofix_action")
        if isinstance(raw_autofix, dict):
            raw_autofix = raw_autofix.get("value")
        if isinstance(raw_manual_drainage.get("value"), dict):
            value_drainage = safe_dict(raw_manual_drainage.get("value"))
            if raw_allow is None:
                raw_allow = value_drainage.get("allow_slope_adjustment")
            if not raw_autofix:
                raw_autofix = value_drainage.get("autofix_action")
        payload_drainage = safe_dict(payload.get("drainage"))
        payload_autofix = payload_drainage.get("autofix_action")
        if isinstance(payload_autofix, dict):
            payload_autofix = payload_autofix.get("value")
        if not raw_autofix and payload_autofix:
            raw_autofix = payload_autofix
        payload_allow = payload_drainage.get("allow_slope_adjustment")
        if isinstance(payload_allow, dict):
            payload_allow = payload_allow.get("value")
        if raw_allow is None and payload_allow is not None:
            raw_allow = payload_allow
        if raw_allow:
            allow_slope_adjustment = True
        if safe_str(raw_autofix, "") == "adjust_slope":
            slope_autofix_requested = True
            allow_slope_adjustment = True
        if not allow_slope_adjustment and not slope_autofix_requested:
            def _candidate_adjust_flag(source: Any) -> tuple[bool, bool]:
                if not isinstance(source, dict):
                    return False, False
                if isinstance(source.get("value"), dict):
                    source = safe_dict(source.get("value"))
                allow_flag = bool(source.get("allow_slope_adjustment"))
                adjust_flag = safe_str(source.get("autofix_action"), "") == "adjust_slope"
                return allow_flag, adjust_flag

            for candidate in (
                payload_drainage,
                raw_manual_drainage,
                safe_dict(raw_manual_drainage.get("value")) if isinstance(raw_manual_drainage, dict) else {},
            ):
                cand_allow, cand_adjust = _candidate_adjust_flag(candidate)
                if cand_allow:
                    allow_slope_adjustment = True
                if cand_adjust:
                    slope_autofix_requested = True
                    allow_slope_adjustment = True
                if allow_slope_adjustment or slope_autofix_requested:
                    break
        if allow_slope_adjustment or slope_autofix_requested:
            inlet_count = len(safe_list(drainage_canonical.get("inlets")))
            run_count = len(safe_list(drainage_canonical.get("pipe_runs") or drainage_canonical.get("runs")))
            if run_count == 0:
                slope_issue = {
                    "code": "SLOPE_ADJUSTMENT_FAILED",
                    "message": "Slope adjustment not feasible without a valid drainage run.",
                    "severity": "info",
                    "context": {
                        "reason": "no_runs",
                    },
                }
                def _has_issue(issue_list, code: str) -> bool:
                    return any(
                        isinstance(item, dict) and safe_str(item.get("code"), "") == code
                        for item in safe_list(issue_list)
                    )
                if not _has_issue(result.get("issues"), slope_issue["code"]):
                    result["issues"] = list(safe_list(result.get("issues"))) + [slope_issue]
                if not _has_issue(drainage_canonical.get("issues"), slope_issue["code"]):
                    drainage_canonical["issues"] = list(safe_list(drainage_canonical.get("issues"))) + [slope_issue]
        autofix_action = safe_str(safe_dict(parsed.get("drainage")).get("autofix_action"), "")
        if autofix_action == "add_basin":
            run_count = len(safe_list(drainage_canonical.get("pipe_runs") or drainage_canonical.get("runs")))
            if run_count == 0 and any(
                safe_str(issue.get("code"), "") == "BASIN_UNREACHABLE"
                for issue in safe_list(drainage_canonical.get("issues"))
                if isinstance(issue, dict)
            ):
                basin_issue = {
                    "code": "BASIN_ADD_NOT_FEASIBLE",
                    "message": "Added basin could not be connected to a valid flow path.",
                    "severity": "info",
                    "context": {
                        "reason": "no_flow_path_after_add",
                    },
                }
                def _has_issue(issue_list, code: str) -> bool:
                    return any(
                        isinstance(item, dict) and safe_str(item.get("code"), "") == code
                        for item in safe_list(issue_list)
                    )
                if not _has_issue(result.get("issues"), basin_issue["code"]):
                    result["issues"] = list(safe_list(result.get("issues"))) + [basin_issue]
                if not _has_issue(drainage_canonical.get("issues"), basin_issue["code"]):
                    drainage_canonical["issues"] = list(safe_list(drainage_canonical.get("issues"))) + [basin_issue]

        def _normalize_under_collection(issue_list, has_inlets: bool):
            if not has_inlets:
                return list(safe_list(issue_list))
            normalized = []
            for issue in safe_list(issue_list):
                if isinstance(issue, dict) and safe_str(issue.get("code"), "") == "UNDER_COLLECTION":
                    normalized.append(
                        {
                            **issue,
                            "code": "UNDER_COLLECTION_REDUCED",
                            "severity": "info",
                            "message": "Inlet coverage improved, but paved areas remain under-collected.",
                            "context": {
                                **dict(issue.get("context") or {}),
                                "improvement_detected": True,
                                "remaining_deficit": issue.get("suggested_additional_inlets"),
                            },
                        }
                    )
                else:
                    normalized.append(issue)
            return normalized

        has_inlets_for_reduction = bool(safe_list(drainage_canonical.get("inlets")))
        if has_inlets_for_reduction:
            result["issues"] = _normalize_under_collection(result.get("issues"), True)
            drainage_canonical["issues"] = _normalize_under_collection(drainage_canonical.get("issues"), True)

        guidance_map = {
            "BASIN_UNREACHABLE": {
                "explanation": "Flow cannot reach the basin from current low points.",
                "suggested_actions": [
                    "Move the basin to a lower point.",
                    "Add an inlet near the low point.",
                    "Adjust grading to direct flow toward the basin.",
                ],
                "best_next_fix": "Move the basin to a lower point.",
            },
            "DRAINAGE_NO_BASIN": {
                "explanation": "No valid basin or outfall was provided for drainage.",
                "suggested_actions": [
                    "Add a basin at a low point.",
                    "Define an outfall location.",
                    "Connect to an existing downstream system.",
                ],
                "best_next_fix": "Add a basin at a low point.",
            },
            "NO_VALID_OUTFALL": {
                "explanation": "No valid outlet was found for drainage discharge.",
                "suggested_actions": [
                    "Add a basin at a low point.",
                    "Define an outfall location.",
                    "Connect to an existing downstream system.",
                ],
                "best_next_fix": "Add a basin at a low point.",
            },
            "NO_PONDS_DEFINED": {
                "explanation": "No basin/pond target is defined for drainage.",
                "suggested_actions": [
                    "Add a basin at a low point.",
                    "Define an outfall location.",
                    "Connect to an existing downstream system.",
                ],
                "best_next_fix": "Add a basin at a low point.",
            },
            "POOR_SLOPE": {
                "explanation": "Terrain is too flat for the minimum pipe slope.",
                "suggested_actions": [
                    "Modify grading to introduce slope.",
                    "Relocate inlets or basin to a steeper area.",
                    "Increase slope in this region.",
                ],
                "best_next_fix": "Modify grading to introduce slope.",
            },
            "SLOPE_ADJUSTMENT_FAILED": {
                "explanation": "Slope adjustment is not feasible with the current geometry.",
                "suggested_actions": [
                    "Modify grading to introduce slope.",
                    "Relocate inlets or basin to a steeper area.",
                    "Increase slope in this region.",
                ],
                "best_next_fix": "Modify grading to introduce slope.",
            },
            "ORPHAN_INLETS": {
                "explanation": "One or more inlets are not connected to a drainage run.",
                "suggested_actions": [
                    "Connect the inlet to the nearest run.",
                    "Reroute the pipe network to include the inlet.",
                ],
                "best_next_fix": "Connect the inlet to the nearest run.",
            },
            "ORPHAN_INLET_CONNECT_FAILED": {
                "explanation": "An orphan inlet could not be connected to a valid drainage run.",
                "suggested_actions": [
                    "Add a basin at a low point.",
                    "Modify grading to create a downhill path.",
                    "Relocate the inlet closer to a basin.",
                ],
                "best_next_fix": "Add a basin at a low point.",
            },
            "UNDER_COLLECTION": {
                "explanation": "There are not enough inlets to collect runoff.",
                "suggested_actions": [
                    "Add inlets along pavement edges.",
                ],
                "best_next_fix": "Add inlets along pavement edges.",
            },
            "UNDER_COLLECTION_REDUCED": {
                "explanation": "Inlet coverage improved, but runoff is still under-collected.",
                "suggested_actions": [
                    "Add inlets along pavement edges.",
                ],
                "best_next_fix": "Add inlets along pavement edges.",
            },
        }

        final_plan = dict(result.get("final_plan") or {})
        meta = dict(final_plan.get("meta") or {})
        low_points = safe_list(
            meta.get("drainage_low_points")
            or drainage_canonical.get("low_points")
            or drainage_canonical.get("low_points_xy")
        )
        low_point_count = len(low_points)
        has_basin = len(safe_list(drainage_canonical.get("basins"))) > 0
        has_inlet = len(safe_list(drainage_canonical.get("inlets"))) > 0
        has_run = len(safe_list(drainage_canonical.get("pipe_runs") or drainage_canonical.get("runs"))) > 0

        def _resolve_best_next_fix(code: str, context: dict | None) -> str | None:
            guidance = guidance_map.get(code)
            if not guidance:
                return None
            if code in {"DRAINAGE_NO_BASIN", "NO_VALID_OUTFALL", "NO_PONDS_DEFINED"}:
                if low_point_count == 0:
                    return "Define an outfall location."
                return "Add a basin at a low point."
            if code == "BASIN_UNREACHABLE":
                if low_point_count and not has_inlet:
                    return "Add an inlet near the low point."
                if has_basin:
                    return "Move the basin to a lower point."
                return "Add a basin at a low point."
            if code in {"POOR_SLOPE", "SLOPE_ADJUSTMENT_FAILED"}:
                if not has_run:
                    return "Create a valid drainage path (add basin and connect inlets)."
                return "Modify grading to introduce slope."
            if code == "ORPHAN_INLETS":
                return "Connect the inlet to the nearest run."
            if code == "ORPHAN_INLET_CONNECT_FAILED":
                if low_point_count == 0:
                    return "Define an outfall location."
                if not has_basin:
                    return "Add a basin at a low point."
                return "Modify grading to create a downhill path."
            if code in {"UNDER_COLLECTION", "UNDER_COLLECTION_REDUCED"}:
                return "Add inlets along pavement edges."
            return guidance.get("best_next_fix")

        def _apply_guidance(issue_list):
            enriched = []
            for issue in safe_list(issue_list):
                if not isinstance(issue, dict):
                    enriched.append(issue)
                    continue
                code = safe_str(issue.get("code"), "")
                guidance = guidance_map.get(code)
                if guidance:
                    context = dict(issue.get("context") or {})
                    if "explanation" not in context:
                        context["explanation"] = guidance["explanation"]
                    if "suggested_actions" not in context:
                        context["suggested_actions"] = guidance["suggested_actions"]
                    if "best_next_fix" not in context:
                        context["best_next_fix"] = _resolve_best_next_fix(code, context)
                    if code in {"POOR_SLOPE", "SLOPE_ADJUSTMENT_FAILED"} and not has_run:
                        context.setdefault("best_next_fix_reason", "no_runs")
                    if code in {"DRAINAGE_NO_BASIN", "NO_VALID_OUTFALL", "NO_PONDS_DEFINED"} and low_point_count == 0:
                        context.setdefault("best_next_fix_reason", "no_low_points")
                    enriched.append({**issue, "context": context})
                else:
                    enriched.append(issue)
            return enriched

        if safe_list(result.get("issues")):
            result["issues"] = _apply_guidance(result.get("issues"))
        if safe_list(drainage_canonical.get("issues")):
            drainage_canonical["issues"] = _apply_guidance(drainage_canonical.get("issues"))

        if safe_list(result.get("issues")) and not safe_list(drainage_canonical.get("issues")):
            drainage_canonical["issues"] = deepcopy(safe_list(result.get("issues")))
        elif safe_list(drainage_canonical.get("issues")) and not safe_list(result.get("issues")):
            result["issues"] = deepcopy(safe_list(drainage_canonical.get("issues")))
        else:
            # Ensure slope adjustment failures are visible in the top-level issues list
            # even when other issues already exist (matrix path relies on result.issues).
            canonical_codes = {
                safe_str(issue.get("code"), "")
                for issue in safe_list(drainage_canonical.get("issues"))
                if isinstance(issue, dict)
            }
            result_codes = {
                safe_str(issue.get("code"), "")
                for issue in safe_list(result.get("issues"))
                if isinstance(issue, dict)
            }
            if "SLOPE_ADJUSTMENT_FAILED" in canonical_codes and "SLOPE_ADJUSTMENT_FAILED" not in result_codes:
                slope_issue = next(
                    (
                        issue
                        for issue in safe_list(drainage_canonical.get("issues"))
                        if isinstance(issue, dict)
                        and safe_str(issue.get("code"), "") == "SLOPE_ADJUSTMENT_FAILED"
                    ),
                    None,
                )
                if slope_issue:
                    result["issues"] = list(safe_list(result.get("issues"))) + [deepcopy(slope_issue)]

        # Final guard: ensure slope-adjustment failure is present after all
        # normalization/guidance steps when no runs exist and adjustment was requested.
        def _flag_from_payload(source: Any) -> tuple[bool, bool]:
            if not isinstance(source, dict):
                return False, False
            if isinstance(source.get("value"), dict):
                source = safe_dict(source.get("value"))
            allow_flag = bool(source.get("allow_slope_adjustment"))
            adjust_flag = safe_str(source.get("autofix_action"), "") == "adjust_slope"
            return allow_flag, adjust_flag

        force_allow = allow_slope_adjustment or slope_autofix_requested
        if not force_allow:
            for candidate in (
                safe_dict(payload.get("drainage")),
                safe_dict(raw_manual_fields.get("drainage")),
                safe_dict(safe_dict(raw_manual_fields.get("drainage")).get("value")),
            ):
                cand_allow, cand_adjust = _flag_from_payload(candidate)
                if cand_allow or cand_adjust:
                    force_allow = True
                    break

        if force_allow and os.environ.get("DRAINAGE_DEBUG") == "1":
            print(
                "[drainage-debug] slope guard allow=True",
                {
                    "allow_slope_adjustment": allow_slope_adjustment,
                    "slope_autofix_requested": slope_autofix_requested,
                    "payload_autofix_action": safe_str(safe_dict(payload.get("drainage")).get("autofix_action"), ""),
                    "manual_autofix_action": safe_str(safe_dict(raw_manual_fields.get("drainage")).get("autofix_action"), ""),
                },
            )
        if force_allow:
            run_count = len(safe_list(drainage_canonical.get("pipe_runs") or drainage_canonical.get("runs")))
            if run_count == 0:
                result_codes = {
                    safe_str(issue.get("code"), "")
                    for issue in safe_list(result.get("issues"))
                    if isinstance(issue, dict)
                }
                if "SLOPE_ADJUSTMENT_FAILED" not in result_codes:
                    slope_issue = {
                        "code": "SLOPE_ADJUSTMENT_FAILED",
                        "message": "Slope adjustment not feasible without a valid drainage run.",
                        "severity": "info",
                        "context": {"reason": "no_runs"},
                    }
                    result["issues"] = list(safe_list(result.get("issues"))) + [slope_issue]
        elif os.environ.get("DRAINAGE_DEBUG") == "1":
            print(
                "[drainage-debug] slope guard allow=False",
                {
                    "allow_slope_adjustment": allow_slope_adjustment,
                    "slope_autofix_requested": slope_autofix_requested,
                    "payload_autofix_action": safe_str(safe_dict(payload.get("drainage")).get("autofix_action"), ""),
                    "manual_autofix_action": safe_str(safe_dict(raw_manual_fields.get("drainage")).get("autofix_action"), ""),
                },
            )

        # Final guard: if connect-orphans was requested but no runs were created,
        # surface a not-feasible issue so the action is not a silent no-op.
        if connect_orphans:
            run_count = len(safe_list(drainage_canonical.get("pipe_runs") or drainage_canonical.get("runs")))
            if run_count == 0 and has_inlet:
                existing = list(safe_list(result.get("issues")))
                existing_codes = {safe_str(issue.get("code"), "") for issue in existing if isinstance(issue, dict)}
                if "ORPHAN_INLET_CONNECT_FAILED" not in existing_codes:
                    filtered = [issue for issue in existing if safe_str(issue.get("code"), "") != "ORPHAN_INLETS"]
                    reason = "no_runs"
                    if "BASIN_UNREACHABLE" in existing_codes:
                        reason = "basin_unreachable"
                    elif "NO_FLOW_PATHS" in existing_codes:
                        reason = "no_flow_paths"
                    filtered.append(
                        {
                            "code": "ORPHAN_INLET_CONNECT_FAILED",
                            "message": "Orphan inlet could not be connected to a valid drainage run.",
                            "severity": "info",
                            "context": {"reason": reason},
                        }
                    )
                    result["issues"] = filtered
        else:
            # Final fallback: if the payload explicitly requested adjust_slope,
            # surface the not-feasible issue even if flags were lost upstream.
            payload_autofix = safe_str(safe_dict(payload.get("drainage")).get("autofix_action"), "")
            manual_autofix = safe_str(safe_dict(raw_manual_fields.get("drainage")).get("autofix_action"), "")
            if payload_autofix == "adjust_slope" or manual_autofix == "adjust_slope":
                run_count = len(safe_list(drainage_canonical.get("pipe_runs") or drainage_canonical.get("runs")))
                if run_count == 0:
                    result_codes = {
                        safe_str(issue.get("code"), "")
                        for issue in safe_list(result.get("issues"))
                        if isinstance(issue, dict)
                    }
                    if "SLOPE_ADJUSTMENT_FAILED" not in result_codes:
                        slope_issue = {
                            "code": "SLOPE_ADJUSTMENT_FAILED",
                            "message": "Slope adjustment not feasible without a valid drainage run.",
                            "severity": "info",
                            "context": {"reason": "no_runs"},
                        }
                        result["issues"] = list(safe_list(result.get("issues"))) + [slope_issue]

        validation_control = bool(safe_dict(raw_manual_fields.get("drainage")).get("validation_control"))
        if validation_control:
            result["issues"] = []
            drainage_canonical["issues"] = []

        # Final matrix-path guard: ensure not-feasible slope adjustment is surfaced
        # after all other issue assembly and before persistence.
        final_run_count = len(safe_list(drainage_canonical.get("pipe_runs") or drainage_canonical.get("runs")))
        if final_run_count == 0:
            payload_drainage = safe_dict(payload.get("drainage"))
            raw_drainage = safe_dict(raw_manual_fields.get("drainage"))
            final_allow = (
                allow_slope_adjustment
                or slope_autofix_requested
                or safe_bool(payload_drainage.get("allow_slope_adjustment"))
                or safe_bool(raw_drainage.get("allow_slope_adjustment"))
            )
            if not final_allow:
                final_allow = safe_str(payload_autofix, "") == "adjust_slope" or safe_str(raw_autofix, "") == "adjust_slope"
            if final_allow:
                final_codes = {
                    safe_str(issue.get("code"), "")
                    for issue in safe_list(result.get("issues"))
                    if isinstance(issue, dict)
                }
                if "SLOPE_ADJUSTMENT_FAILED" not in final_codes:
                    result["issues"] = list(safe_list(result.get("issues"))) + [
                        {
                            "code": "SLOPE_ADJUSTMENT_FAILED",
                            "message": "Slope adjustment not feasible without a valid drainage run.",
                            "severity": "info",
                            "context": {"reason": "no_runs"},
                        }
                    ]

        # Final attribution guard (drainage-only): emit grading-blocked issue when
        # existing surface reaches but proposed surface does not (attribution-only).
        try:
            drainage_summary = manager.project.meta.get("drainage_summary")
            proposed_run_count = len(safe_list(drainage_canonical.get("pipe_runs") or drainage_canonical.get("runs")))
            proposed_reached = False
            if drainage_summary is not None:
                for run in safe_list(getattr(drainage_summary, "pipe_runs", [])):
                    if not bool(getattr(run, "reached_target", False)):
                        continue
                    path = getattr(run, "path", None)
                    if isinstance(path, (list, tuple)) and len(path) <= 1:
                        continue
                    proposed_reached = True
                    break
            else:
                for run in safe_list(drainage_canonical.get("pipe_runs") or drainage_canonical.get("runs")):
                    if not safe_bool(run.get("reached_target")):
                        continue
                    path = safe_list(run.get("path"))
                    if len(path) <= 1:
                        continue
                    proposed_reached = True
                    break
            from engines.drainage_engine import DrainageEngine
            existing_surface = None
            try:
                from planner import _build_existing_surface as _build_existing_surface_impl
                existing_surface = _build_existing_surface_impl(parsed)
            except Exception:
                existing_surface = None
            surface_guidance = safe_dict(drainage_canonical.get("surface_guidance"))
            preferred_targets = safe_list(surface_guidance.get("preferred_targets"))
            if not preferred_targets:
                preferred_targets = [
                    {
                        "name": safe_str(getattr(rec, "sink_name", ""), "OUTFALL_A"),
                        "x": safe_float(getattr(rec, "centroid_xy", (0.0, 0.0))[0], 0.0),
                        "y": safe_float(getattr(rec, "centroid_xy", (0.0, 0.0))[1], 0.0),
                        "radius": max(1.0, safe_float(getattr(rec, "area_sf", 0.0) ** 0.5, POND_RADIUS)),
                    }
                    for rec in safe_list(getattr(drainage_summary, "basin_records", []))
                ]
            proposed_reached_for_attribution = False
            if preferred_targets:
                if drainage_summary is not None:
                    for run in safe_list(getattr(drainage_summary, "pipe_runs", [])):
                        if not bool(getattr(run, "reached_target", False)):
                            continue
                        if len(safe_list(getattr(run, "path", []))) <= 1:
                            continue
                        proposed_reached_for_attribution = True
                        break
                else:
                    for run in safe_list(drainage_canonical.get("pipe_runs") or drainage_canonical.get("runs")):
                        if not safe_bool(run.get("reached_target")):
                            continue
                        if len(safe_list(run.get("path"))) <= 1:
                            continue
                        proposed_reached_for_attribution = True
                        break
            alt_reached = False
            alt_closest_target = None
            alt_distance = None
            alt_engine = DrainageEngine(existing_surface) if existing_surface is not None else None
            if alt_engine is not None and hasattr(alt_engine, "clear_pond_targets"):
                alt_engine.clear_pond_targets()
            if alt_engine is not None:
                for target in preferred_targets:
                    target_data = safe_dict(target)
                    alt_engine.add_pond_target(
                        safe_str(target_data.get("name"), "OUTFALL_A"),
                        safe_float(target_data.get("x"), 0.0),
                        safe_float(target_data.get("y"), 0.0),
                        radius=max(1.0, safe_float(target_data.get("radius"), POND_RADIUS)),
                    )
            alt_inlets = []
            if drainage_summary is not None:
                alt_inlets = [
                    rec.inlet
                    for rec in safe_list(getattr(drainage_summary, "inlet_records", []))
                    if hasattr(rec, "inlet")
                ]
            elif alt_engine is not None:
                try:
                    from engines.drainage_engine import Inlet as DrainageInlet
                    alt_inlets = [
                        DrainageInlet(
                            name=safe_str(item.get("name"), f"INLET-{idx + 1}"),
                            x=safe_float(item.get("x"), 0.0),
                            y=safe_float(item.get("y"), 0.0),
                            z=alt_engine._cell_z(
                                *alt_engine._normalize_xy(
                                    safe_float(item.get("x"), 0.0),
                                    safe_float(item.get("y"), 0.0),
                                )
                            ),
                            is_forced=True,
                        )
                        for idx, item in enumerate(safe_list(drainage_canonical.get("inlets")))
                        if isinstance(item, dict)
                    ]
                except Exception:
                    alt_inlets = []
            alt_basin_records = []
            if drainage_summary is not None:
                alt_basin_records = safe_list(getattr(drainage_summary, "basin_records", []))
            elif alt_engine is not None:
                try:
                    alt_basin_records = alt_engine.basin_records()
                except Exception:
                    alt_basin_records = []
            if alt_engine is not None and alt_inlets:
                _, alt_summary = alt_engine.pipe_runs(
                    inlets=alt_inlets,
                    basin_records=alt_basin_records,
                    follow_surface=True,
                    min_slope=0.001,
                    max_steps=500,
                    mode=safe_str(getattr(drainage_summary, "mode", "assisted"), "assisted") if drainage_summary else "assisted",
                    hydraulic=None,
                    connect_orphans=False,
                    allow_slope_adjustment=False,
                )
                attribution_buffer = 5.0
                target_cache = []
                for target in preferred_targets:
                    target_data = safe_dict(target)
                    target_cache.append(
                        (
                            safe_float(target_data.get("x"), 0.0),
                            safe_float(target_data.get("y"), 0.0),
                            max(1.0, safe_float(target_data.get("radius"), POND_RADIUS)),
                        )
                    )
                for run in safe_list(getattr(alt_summary, "pipe_runs", [])):
                    path = safe_list(getattr(run, "path", []))
                    if not path:
                        continue
                    end = path[-1]
                    if not isinstance(end, (list, tuple)) or len(end) < 2:
                        continue
                    end_x = safe_float(end[0], 0.0)
                    end_y = safe_float(end[1], 0.0)
                    if bool(getattr(run, "reached_target", False)):
                        alt_reached = True
                        alt_closest_target = None
                        alt_distance = 0.0
                        break
                    for tx, ty, radius in target_cache:
                        dx = end_x - tx
                        dy = end_y - ty
                        dist = (dx * dx + dy * dy) ** 0.5
                        if alt_distance is None or dist < alt_distance:
                            alt_distance = dist
                            alt_closest_target = (tx, ty, radius)
                        if dist <= radius + attribution_buffer:
                            alt_reached = True
                            alt_distance = dist
                            alt_closest_target = (tx, ty, radius)
                            break
                    if alt_reached:
                        break
                if alt_reached and not proposed_reached_for_attribution:
                    source_point = None
                    blocked_target = None
                    suggested_fix_zone = None
                    inlet_records = safe_list(drainage_canonical.get("inlets"))
                    basin_records = safe_list(drainage_canonical.get("basins"))
                    for rec in inlet_records:
                        if not isinstance(rec, dict):
                            continue
                        sx = safe_float(rec.get("x"), None)
                        sy = safe_float(rec.get("y"), None)
                        if sx is None or sy is None:
                            continue
                        source_point = (sx, sy)
                        break
                    for rec in basin_records:
                        if not isinstance(rec, dict):
                            continue
                        bx = safe_float(rec.get("x"), None)
                        by = safe_float(rec.get("y"), None)
                        if bx is None or by is None:
                            continue
                        blocked_target = (bx, by)
                        break
                    if source_point and blocked_target:
                        sx, sy = source_point
                        tx, ty = blocked_target
                        mid_x = (sx + tx) / 2.0
                        mid_y = (sy + ty) / 2.0
                        zone_w = max(abs(tx - sx) * 0.6, 40.0)
                        zone_h = max(abs(ty - sy) * 0.6, 40.0)
                        suggested_fix_zone = {
                            "x": mid_x - zone_w / 2.0,
                            "y": mid_y - zone_h / 2.0,
                            "w": zone_w,
                            "h": zone_h,
                            "approximate": True,
                        }

                    existing_codes = {
                        safe_str(issue.get("code"), "")
                        for issue in safe_list(result.get("issues"))
                        if isinstance(issue, dict)
                    }
                    if "DRAINAGE_BLOCKED_BY_GRADING" not in existing_codes:
                        grading_issue = {
                            "code": "DRAINAGE_BLOCKED_BY_GRADING",
                            "message": "Proposed grading blocks flow paths that were reachable on existing terrain.",
                            "severity": "warning",
                            "context": {
                                "explanation": "Proposed grading blocks flow paths that would otherwise reach the basin.",
                                "reason": "proposed_surface_blocks_flow",
                                "best_next_fix": "Introduce a grading swale toward the basin or lower the ridge between inlet and basin.",
                                "suggested_actions": [
                                    "Introduce a grading swale toward the basin.",
                                    "Lower local ridge between inlet and basin.",
                                    "Adjust pad edges to restore flow.",
                                ],
                                "blocker_type": "ridge",
                                "source_point": {"x": source_point[0], "y": source_point[1]} if source_point else None,
                                "blocked_target": {"x": blocked_target[0], "y": blocked_target[1]} if blocked_target else None,
                                "blocker_location": (
                                    {"x": (source_point[0] + blocked_target[0]) / 2.0, "y": (source_point[1] + blocked_target[1]) / 2.0, "approximate": True}
                                    if source_point and blocked_target
                                    else None
                                ),
                                "suggested_fix_zone": suggested_fix_zone,
                                "approximate": True,
                            },
                        }
                        result["issues"] = list(safe_list(result.get("issues"))) + [grading_issue]
                        drainage_canonical.setdefault("issues", [])
                        drainage_canonical["issues"] = list(safe_list(drainage_canonical.get("issues"))) + [deepcopy(grading_issue)]
                        result.setdefault("issue_details", [])
                        result["issue_details"] = list(safe_list(result.get("issue_details"))) + [deepcopy(grading_issue)]
                        drainage_canonical.setdefault("issue_details", [])
                        drainage_canonical["issue_details"] = list(safe_list(drainage_canonical.get("issue_details"))) + [deepcopy(grading_issue)]
        except Exception as exc:
            ctx.record_error(f"ATTRIBUTION_ALT_EXCEPTION: {exc}")
            raise

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
                    metadata=dict(existing.get("metadata") or {}),
                )

        if job_id:
            update_job_progress(
                job_id,
                stage="Finalizing",
                detail="Drainage-only run complete.",
                progress=92,
            )
        return result

    return drainage_runner
