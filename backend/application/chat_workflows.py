from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from backend.services.chat_learning_store import (
    append_chat_interaction_event,
    append_chat_learning_event,
)
from parsers.chat_intent_parser import build_chat_memory_summary


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _canonical_chat_context(context: Dict[str, Any], record: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not record:
        return context
    merged = dict(context)
    project_input = _safe_dict(record.get("project_input"))
    latest_result = _safe_dict(record.get("latest_result"))
    final_plan = _safe_dict(latest_result.get("final_plan"))
    meta = _safe_dict(final_plan.get("meta") or latest_result.get("metadata") or latest_result.get("meta"))
    parsed_payload = _safe_dict(latest_result.get("parsed_payload"))
    manual_fields = _safe_dict(parsed_payload.get("manual_fields") or project_input.get("manual_fields"))
    lot = _safe_dict(manual_fields.get("lot") or project_input.get("lot"))
    site_plan = _safe_dict(manual_fields.get("site_plan") or project_input.get("site_plan"))

    current_project = _safe_dict(merged.get("current_project"))
    current_project.update(
        {
            "project_id": record.get("project_id"),
            "name": record.get("name"),
            "project_input": project_input,
            "latest_result": latest_result,
        }
    )
    merged["current_project"] = current_project
    merged["project_id"] = record.get("project_id") or merged.get("project_id")
    merged["has_plan"] = bool(latest_result.get("final_plan") or latest_result.get("success") or merged.get("has_plan"))
    merged["current_truth_audit"] = _safe_dict(
        meta.get("truth_audit")
        or meta.get("engineering_truth_audit")
        or merged.get("current_truth_audit")
    )
    merged["engineering_status"] = _safe_dict(meta.get("engineering_status") or merged.get("engineering_status"))
    convergence = _safe_dict(meta.get("convergence_summary") or merged.get("convergence_summary"))
    export_audit = _safe_dict(meta.get("export_audit"))
    if export_audit:
        blocked_reasons = list(convergence.get("blocked_reasons") or [])
        for reason in list(export_audit.get("blocked_reasons") or []):
            if reason not in blocked_reasons:
                blocked_reasons.append(reason)
        if export_audit.get("export_blocked") is True and "export_audit_blocked" not in blocked_reasons:
            blocked_reasons.append("export_audit_blocked")
        if blocked_reasons:
            convergence["blocked_reasons"] = blocked_reasons
        if export_audit.get("export_blocked") is True:
            blocked_exports = list(convergence.get("blocked_exports") or [])
            if "export" not in blocked_exports:
                blocked_exports.append("export")
            convergence["blocked_exports"] = blocked_exports
        merged["current_export_audit"] = export_audit
    merged["convergence_summary"] = convergence
    merged["assumptions"] = list(meta.get("assumptions") or latest_result.get("assumptions") or merged.get("assumptions") or [])
    merged["issues"] = list(latest_result.get("issues") or meta.get("issues") or merged.get("issues") or [])
    merged["manual_failures"] = list(
        latest_result.get("manual_failures")
        or meta.get("manual_failures")
        or meta.get("blocked_reasons")
        or merged.get("manual_failures")
        or []
    )
    deliverables = _safe_dict(meta.get("deliverables"))
    merged["produced_deliverables"] = list(
        deliverables.get("produced")
        or latest_result.get("produced_deliverables")
        or merged.get("produced_deliverables")
        or []
    )

    if not merged.get("project_type"):
        merged["project_type"] = project_input.get("project_type") or meta.get("project_type")
    if not merged.get("lot_width"):
        merged["lot_width"] = lot.get("w") or lot.get("width")
    if not merged.get("lot_height"):
        merged["lot_height"] = lot.get("h") or lot.get("height")
    if not merged.get("parking_count"):
        merged["parking_count"] = site_plan.get("parking_count") or meta.get("parking_count")
    return merged


def decide_chat(
    payload_data: Dict[str, Any],
    *,
    decide_chat_message: Callable[[Dict[str, Any]], Dict[str, Any]],
    project_store: Optional[Any] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    message = str(payload_data.get("message") or "").strip()
    if not message:
        raise ValueError("Chat message is required.")
    payload = dict(payload_data)
    context = dict(payload.get("context") or {})
    chat_thread = context.get("chat_thread")
    project = context.get("current_project") or {}
    project_id = project.get("project_id") or context.get("project_id")
    record = None
    if project_store and user_id and project_id:
        try:
            record = project_store.get_project(user_id=user_id, project_id=project_id)
        except Exception:
            record = None
    if record:
        context = _canonical_chat_context(context, record)
        payload["context"] = context
    decision = decide_chat_message(payload)
    memory_summary = None
    if chat_thread:
        memory_summary = build_chat_memory_summary(chat_thread)
    if chat_thread and project_store and user_id and project_id:
        try:
            if record:
                project_input = dict(record.get("project_input") or {})
                meta = dict(project_input.get("meta") or {})
                meta["chat_memory"] = memory_summary
                project_input["meta"] = meta
                project_store.save_project(
                    user_id=user_id,
                    project_id=record.get("project_id"),
                    name=record.get("name") or "Untitled Project",
                    description=record.get("description") or "",
                    session_id=record.get("session_id"),
                    tags=record.get("tags") or [],
                    project_input=project_input,
                    latest_result=record.get("latest_result") or {},
                    session_state=record.get("session_state") or {},
                    metadata=record.get("metadata") or {},
                )
        except Exception:
            pass
        append_chat_learning_event(
            {
                "project_id": project_id,
                "user_id": user_id,
                "message": message,
                "decision": decision,
                "memory_summary": memory_summary,
            }
        )

    append_chat_interaction_event(
        {
            "user_id": user_id,
            "project_id": project_id,
            "message": message,
            "assistant_message": decision.get("assistant_message"),
            "intent": decision.get("intent"),
            "run_mode": decision.get("run_mode"),
            "needs_clarification": decision.get("needs_clarification"),
            "design_prompt": decision.get("design_prompt"),
            "reason": decision.get("reason"),
            "confidence": decision.get("confidence"),
            "memory_summary": memory_summary,
        }
    )
    return decision
