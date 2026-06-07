from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

from fastapi import HTTPException, UploadFile
from fastapi.responses import Response

from backend.application.file_workflows import _copy_upload_with_limit, _upload_limit_bytes, _validate_upload_metadata
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


PDF_ALLOWED_EXTENSIONS = {".pdf"}
PDF_ALLOWED_CONTENT_TYPES = {"application/pdf", "application/octet-stream", "binary/octet-stream"}


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
    try:
        updated_meta = update_editable_sheet_element(meta, element_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    saved = _save_project_with_meta(project_store=project_store, record=record, meta=updated_meta)
    result_meta = dict(saved.get("latest_result", {}).get("final_plan", {}).get("meta", {}) or {})
    return {
        "success": True,
        "message": "PDF-derived editable sheet element updated. It remains review-required.",
        "project": saved,
        "plan_pdf_editable_sheet_v1": result_meta.get("plan_pdf_editable_sheet_v1"),
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
    return {"success": True, "report": plan_pdf_report(meta)}


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
