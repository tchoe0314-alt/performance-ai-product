from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Protocol

from fastapi import HTTPException, UploadFile
from fastapi.responses import Response

from backend.application.file_workflows import _copy_upload_with_limit, _upload_limit_bytes, _validate_upload_metadata
from backend.planning.common import safe_str
from backend.planning.candidate_review_inbox import build_candidate_review_inbox
from backend.planning.plan_pdf_understanding import (
    SOURCE_CONFIDENCE,
    TRUTH_LABEL,
    analyze_plan_pdf,
    merge_plan_pdf_analysis_into_meta,
    plan_pdf_report,
    report_json_bytes,
    update_editable_sheet_element,
)
from backend.planning.source_confidence_map import attach_source_confidence_map, build_source_confidence_map


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


PDF_ALLOWED_EXTENSIONS = {".pdf"}
PDF_ALLOWED_CONTENT_TYPES = {"application/pdf", "application/octet-stream", "binary/octet-stream"}


def _large_pdf_queue_threshold_bytes() -> int:
    raw = str(os.getenv("CIVORA_PLAN_PDF_ASYNC_THRESHOLD_BYTES") or "").strip()
    try:
        value = int(raw) if raw else 8 * 1024 * 1024
    except Exception:
        value = 8 * 1024 * 1024
    return max(1, value)


def _safe_uploaded_path(upload_dir: Path, stored_filename: str) -> Path:
    base = upload_dir.resolve()
    candidate = (base / Path(stored_filename).name).resolve()
    if base not in candidate.parents and candidate != base:
        raise ValueError("Stored PDF path is outside the upload directory.")
    return candidate


def _save_project_with_meta(
    *,
    project_store: ProjectStoreProtocol,
    record: Dict[str, Any],
    meta: Dict[str, Any],
) -> Dict[str, Any]:
    latest_result = deepcopy(dict(record.get("latest_result") or {}))
    final_plan = deepcopy(dict(latest_result.get("final_plan") or {}))
    if not final_plan:
        final_plan = {"actions": [], "meta": {}}
    meta["candidate_review_inbox_v1"] = build_candidate_review_inbox(meta)
    meta["source_confidence_map_v1"] = build_source_confidence_map(meta, project_input=dict(record.get("project_input") or {}))
    final_plan["meta"] = meta
    latest_result["final_plan"] = final_plan
    latest_result = attach_source_confidence_map(latest_result, project_input=dict(record.get("project_input") or {}))
    return project_store.save_project(
        user_id=str(record.get("user_id") or record.get("_user_id")),
        project_id=str(record.get("project_id")),
        name=str(record.get("name") or "Untitled Project"),
        description=str(record.get("description") or ""),
        session_id=record.get("session_id"),
        tags=list(record.get("tags") or []),
        project_input=dict(record.get("project_input") or {}),
        latest_result=latest_result,
        session_state=dict(record.get("session_state") or {}),
        metadata=dict(record.get("metadata") or {}),
    )


def upload_plan_pdf_file(
    *,
    upload_dir: Path,
    file: UploadFile,
    current_user: Dict[str, Any],
    project_store: Optional[ProjectStoreProtocol] = None,
    job_queue: Optional[JobQueueProtocol] = None,
    project_id: str = "",
) -> Dict[str, Any]:
    filename = file.filename or "plan.pdf"
    safe_prefix = str(current_user["user_id"]).replace("/", "_")
    safe_name = Path(filename).name
    _validate_upload_metadata(
        file=file,
        safe_name=safe_name,
        allowed_extensions=PDF_ALLOWED_EXTENSIONS,
        allowed_content_types=PDF_ALLOWED_CONTENT_TYPES,
    )
    stored_name = f"{safe_prefix}_{safe_name}"
    target = upload_dir / stored_name
    byte_count = _copy_upload_with_limit(file=file, target=target, max_bytes=_upload_limit_bytes("existing_conditions"))
    if job_queue is not None and byte_count >= _large_pdf_queue_threshold_bytes():
        job = job_queue.submit_job(
            user_id=str(current_user["user_id"]),
            job_type="plan_pdf_analysis",
            project_id=project_id or None,
            payload={
                "stored_filename": stored_name,
                "original_filename": safe_name,
                "file_url": f"/api/uploads/{stored_name}",
                "content_type": str(getattr(file, "content_type", "") or "application/pdf"),
                "byte_count": int(byte_count),
            },
        )
        return {
            "success": True,
            "message": "Large plan PDF stored. Analysis and editable report extraction are queued.",
            "filename": safe_name,
            "stored_filename": stored_name,
            "file_url": f"/api/uploads/{stored_name}",
            "source_confidence": SOURCE_CONFIDENCE,
            "review_required": True,
            "construction_release_allowed": False,
            "truth_label": TRUTH_LABEL,
            "plan_pdf_analysis_status": "queued",
            "plan_pdf_analysis_blockers": [
                "analysis_pending_async_job",
                "field_use_release_blocked:pdf_import_is_source_imagery_only",
            ],
            "job": job,
            "operational_summary": {
                "status": str(job.get("status") or "queued"),
                "job_type": str(job.get("job_type") or "plan_pdf_analysis"),
                "job_bound": bool(job.get("job_id")),
                "project_bound": bool(project_id),
                "project_id": project_id or None,
                "job_id": job.get("job_id"),
                "retryable": True,
                "review_only": True,
                "construction_release_allowed": False,
            },
        }
    analysis = analyze_plan_pdf(
        target,
        original_filename=safe_name,
        stored_filename=stored_name,
        file_url=f"/api/uploads/{stored_name}",
        content_type=str(getattr(file, "content_type", "") or "application/pdf"),
        byte_count=byte_count,
    )
    response: Dict[str, Any] = {
        "success": True,
        "message": "Plan PDF uploaded and analyzed as review-required source evidence.",
        "filename": safe_name,
        "stored_filename": stored_name,
        "file_url": f"/api/uploads/{stored_name}",
        "source_confidence": SOURCE_CONFIDENCE,
        "review_required": True,
        "construction_release_allowed": False,
        "truth_label": TRUTH_LABEL,
        "plan_pdf_analysis_v1": analysis,
        "plan_pdf_editable_sheet_v1": analysis.get("editable_sheet"),
    }
    if project_id:
        if not project_store:
            raise HTTPException(status_code=500, detail="Project store is unavailable.")
        record = project_store.get_project(user_id=str(current_user["user_id"]), project_id=project_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        latest_result = dict(record.get("latest_result") or {})
        final_plan = dict(latest_result.get("final_plan") or {})
        meta = dict(final_plan.get("meta") or {})
        merged_meta = merge_plan_pdf_analysis_into_meta(meta, analysis)
        saved = _save_project_with_meta(project_store=project_store, record=record, meta=merged_meta)
        response["project_id"] = project_id
        response["project"] = saved
        response["candidate_review_inbox_v1"] = dict(saved.get("latest_result", {}).get("final_plan", {}).get("meta", {}).get("candidate_review_inbox_v1") or {})
    return response


def build_plan_pdf_analysis_job_runner(
    *,
    upload_dir: Path,
    project_store: Optional[ProjectStoreProtocol] = None,
    update_job_progress: Optional[Callable[..., None]] = None,
) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def _progress(job_id: str, *, stage: str, detail: str, progress: int) -> None:
        if update_job_progress is not None:
            update_job_progress(job_id, stage=stage, detail=detail, progress=progress)

    def runner(job: Dict[str, Any]) -> Dict[str, Any]:
        job_id = str(job.get("job_id") or "")
        user_id = str(job.get("user_id") or "")
        project_id = str(job.get("project_id") or "").strip()
        payload = dict(job.get("payload") or {})
        stored_filename = str(payload.get("stored_filename") or "").strip()
        original_filename = str(payload.get("original_filename") or stored_filename or "plan.pdf").strip()
        if not stored_filename:
            raise RuntimeError("Plan PDF analysis job is missing stored_filename.")

        _progress(job_id, stage="Plan PDF Analysis", detail="Validating stored upload before extraction.", progress=24)
        path = _safe_uploaded_path(upload_dir, stored_filename)
        if not path.exists():
            raise RuntimeError("Stored plan PDF is missing; upload must be retried.")

        _progress(job_id, stage="Plan PDF Analysis", detail="Extracting pages, text evidence, and editable sheet candidates.", progress=48)
        analysis = analyze_plan_pdf(
            path,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_url=str(payload.get("file_url") or f"/api/uploads/{stored_filename}"),
            content_type=str(payload.get("content_type") or "application/pdf"),
            byte_count=int(payload.get("byte_count") or path.stat().st_size),
        )
        result: Dict[str, Any] = {
            "success": True,
            "review_required": True,
            "construction_release_allowed": False,
            "truth_label": TRUTH_LABEL,
            "plan_pdf_analysis_v1": analysis,
            "plan_pdf_editable_sheet_v1": analysis.get("editable_sheet"),
        }
        if project_id and project_store is not None:
            _progress(job_id, stage="Plan PDF Analysis", detail="Saving review-required PDF evidence to the project.", progress=78)
            record = project_store.get_project(user_id=user_id, project_id=project_id)
            if record is None:
                raise RuntimeError("Project not found while saving plan PDF analysis.")
            latest_result = dict(record.get("latest_result") or {})
            final_plan = dict(latest_result.get("final_plan") or {})
            meta = dict(final_plan.get("meta") or {})
            merged_meta = merge_plan_pdf_analysis_into_meta(meta, analysis)
            saved = _save_project_with_meta(project_store=project_store, record=record, meta=merged_meta)
            result["project_id"] = project_id
            result["project"] = saved
            result["candidate_review_inbox_v1"] = dict(
                saved.get("latest_result", {}).get("final_plan", {}).get("meta", {}).get("candidate_review_inbox_v1") or {}
            )

        _progress(job_id, stage="Plan PDF Analysis", detail="Plan PDF extraction report is ready for review.", progress=96)
        return result

    return runner


def update_project_plan_pdf_element(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: str,
    element_id: str,
    updates: Dict[str, Any],
) -> Dict[str, Any]:
    record = project_store.get_project(user_id=user_id, project_id=project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    latest_result = dict(record.get("latest_result") or {})
    final_plan = dict(latest_result.get("final_plan") or {})
    meta = dict(final_plan.get("meta") or {})
    cleaned_updates = dict(updates or {})
    if "review_status" in cleaned_updates and safe_str(cleaned_updates.get("review_status")) == "":
        cleaned_updates.pop("review_status", None)
    if "bbox" in cleaned_updates and cleaned_updates.get("bbox") is None:
        cleaned_updates.pop("bbox", None)
    if "move_target" in cleaned_updates and cleaned_updates.get("move_target") is None:
        cleaned_updates.pop("move_target", None)
    try:
        updated_meta = update_editable_sheet_element(meta, element_id, cleaned_updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    saved = _save_project_with_meta(project_store=project_store, record=record, meta=updated_meta)
    result_meta = dict(saved.get("latest_result", {}).get("final_plan", {}).get("meta", {}) or {})
    return {
        "success": True,
        "message": "PDF-derived editable sheet element updated. It remains review-required.",
        "project": saved,
        "plan_pdf_editable_sheet_v1": result_meta.get("plan_pdf_editable_sheet_v1"),
        "plan_pdf_changed_elements_v1": result_meta.get("plan_pdf_changed_elements_v1"),
        "candidate_review_inbox_v1": result_meta.get("candidate_review_inbox_v1"),
        "construction_release_allowed": False,
        "truth_label": TRUTH_LABEL,
    }


def get_project_plan_pdf_report(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: str,
) -> Dict[str, Any]:
    record = project_store.get_project(user_id=user_id, project_id=project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    meta = dict(record.get("latest_result", {}).get("final_plan", {}).get("meta", {}) or {})
    return {
        "success": True,
        "source_confidence": SOURCE_CONFIDENCE,
        "review_required": True,
        "construction_release_allowed": False,
        "truth_label": TRUTH_LABEL,
        "report": plan_pdf_report(meta),
    }


def download_project_plan_pdf_report(
    *,
    project_store: ProjectStoreProtocol,
    user_id: str,
    project_id: str,
) -> Response:
    record = project_store.get_project(user_id=user_id, project_id=project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    meta = dict(record.get("latest_result", {}).get("final_plan", {}).get("meta", {}) or {})
    filename = f"{project_id}_plan_pdf_extraction_report.json"
    return Response(
        content=report_json_bytes(meta),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
