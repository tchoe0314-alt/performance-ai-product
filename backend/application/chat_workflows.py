from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional

from backend.services.chat_learning_store import (
    append_chat_interaction_event,
    append_chat_learning_event,
)
from parsers.chat_intent_parser import build_chat_memory_summary


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return list(value) if isinstance(value, list) else []


def _truthful_decision_update(
    decision: Dict[str, Any],
    *,
    assistant_message: Optional[str] = None,
    intent: Optional[str] = None,
    run_mode: Optional[str] = None,
    design_prompt: Optional[str] = None,
    needs_clarification: Optional[bool] = None,
    action_taken: str,
    action_blocked_reason: str = "",
    required_missing_inputs: Optional[List[str]] = None,
    affected_systems: Optional[List[str]] = None,
    assumptions: Optional[List[str]] = None,
    next_best_action: str = "",
    command_payload_updates: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    updated = dict(decision)
    metadata = dict(updated.get("response_metadata") or {})
    if assistant_message is not None:
        updated["assistant_message"] = assistant_message
    if intent is not None:
        updated["intent"] = intent
    if run_mode is not None:
        updated["run_mode"] = run_mode
    if design_prompt is not None:
        updated["design_prompt"] = design_prompt
    if needs_clarification is not None:
        updated["needs_clarification"] = needs_clarification
    if required_missing_inputs is not None:
        metadata["required_missing_inputs"] = list(required_missing_inputs)
    if affected_systems is not None:
        metadata["affected_systems"] = list(affected_systems)
    if assumptions is not None:
        metadata["assumptions"] = list(assumptions)
    if command_payload_updates:
        command_payload = dict(metadata.get("command_payload") or {})
        command_payload.update(command_payload_updates)
        metadata["command_payload"] = command_payload
    metadata["action_taken"] = action_taken
    metadata["action_blocked_reason"] = action_blocked_reason
    metadata["next_best_action"] = next_best_action
    updated["response_metadata"] = metadata
    updated["required_missing_inputs"] = list(metadata.get("required_missing_inputs") or [])
    updated["action_taken"] = action_taken
    updated["action_blocked_reason"] = action_blocked_reason
    updated["affected_systems"] = list(metadata.get("affected_systems") or [])
    updated["assumptions"] = list(metadata.get("assumptions") or [])
    updated["next_best_action"] = next_best_action
    return updated


def _save_project_record(project_store: Any, record: Dict[str, Any], *, project_input: Dict[str, Any], latest_result: Dict[str, Any]) -> None:
    project_store.save_project(
        user_id=record.get("_user_id"),
        project_id=record.get("project_id"),
        name=record.get("name") or "Untitled Project",
        description=record.get("description") or "",
        session_id=record.get("session_id"),
        tags=record.get("tags") or [],
        project_input=project_input,
        latest_result=latest_result,
        session_state=record.get("session_state") or {},
        metadata=record.get("metadata") or {},
    )


def _next_draft_id(items: List[Any], prefix: str) -> str:
    return f"{prefix}-{len(items) + 1}"


def _apply_chat_command_execution(
    decision: Dict[str, Any],
    *,
    context: Dict[str, Any],
    record: Optional[Dict[str, Any]],
    project_store: Optional[Any],
    user_id: Optional[str],
    message: str,
) -> Dict[str, Any]:
    metadata = _safe_dict(decision.get("response_metadata"))
    command_intent = str(metadata.get("intent") or "")
    command_payload = _safe_dict(metadata.get("command_payload"))
    current_mode = str(context.get("strategy_mode") or "").strip().lower()
    strict_mode = current_mode in {"user", "manual"} or command_payload.get("assumption_policy") == "strict"
    assumptions = [str(item) for item in _safe_list(metadata.get("assumptions")) if str(item)]

    if strict_mode and assumptions:
        question = "I cannot assume that in strict mode. Please provide " + ", ".join(assumptions[:2]) + "."
        return _truthful_decision_update(
            decision,
            assistant_message=question,
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=True,
            action_taken="asked_clarifying_question",
            action_blocked_reason="Strict/no-assumption mode blocks inferred command inputs.",
            required_missing_inputs=["explicit user-provided command inputs"],
            assumptions=[],
            next_best_action=question,
        )

    if command_intent not in {
        "site_update",
        "object_or_layout_command",
        "grading_command",
        "drainage_command",
        "utility_command",
        "generate_command",
    }:
        return decision

    if metadata.get("required_missing_inputs"):
        return decision

    if command_intent in {"site_update", "object_or_layout_command"}:
        if not (record and project_store and user_id):
            ask = "I understood the command, but I need a saved canonical project before I can apply that edit."
            return _truthful_decision_update(
                decision,
                assistant_message=ask,
                intent="conversation",
                run_mode="none",
                design_prompt="",
                needs_clarification=True,
                action_taken="blocked_missing_canonical_edit_support",
                action_blocked_reason="No saved canonical project record is available for this command.",
                required_missing_inputs=["saved canonical project record"],
                next_best_action="Save or load a project, then retry the command.",
            )

    if not record:
        return decision

    record = dict(record)
    record["_user_id"] = user_id
    project_input = deepcopy(_safe_dict(record.get("project_input")))
    latest_result = deepcopy(_safe_dict(record.get("latest_result")))
    final_plan = _safe_dict(latest_result.get("final_plan"))
    meta = _safe_dict(final_plan.get("meta"))
    changed = False

    if command_intent == "site_update":
        area = command_payload.get("site_area_acres")
        width = command_payload.get("lot_width")
        height = command_payload.get("lot_height")
        if not area:
            ask = "I understood the site update, but I need the target site area before changing canonical state."
            return _truthful_decision_update(
                decision,
                assistant_message=ask,
                intent="conversation",
                run_mode="none",
                design_prompt="",
                needs_clarification=True,
                action_taken="asked_clarifying_question",
                action_blocked_reason="Site area value is missing from the parsed command.",
                required_missing_inputs=["site area"],
                next_best_action=ask,
            )
        manual_fields = _safe_dict(project_input.get("manual_fields"))
        lot = _safe_dict(manual_fields.get("lot"))
        lot.update({"site_area_acres": area, "w": width, "h": height, "source": "chat_command"})
        manual_fields["lot"] = lot
        project_input["manual_fields"] = manual_fields
        project_input["site_area_acres"] = area
        meta["site_area_acres"] = area
        meta["canonical_site_state"] = {
            "site_area_acres": area,
            "lot_width": width,
            "lot_height": height,
            "source": "chat_command",
            "ready_language": "ready_for_engineer_review",
            "engineer_review_required": True,
        }
        changed = True
        final_plan["meta"] = meta
        latest_result["final_plan"] = final_plan
        _save_project_record(project_store, record, project_input=project_input, latest_result=latest_result)
        return _truthful_decision_update(
            decision,
            assistant_message=f"I updated canonical site state to {area} acres for an engineer-review-required package.",
            action_taken="updated_canonical_site_state",
            action_blocked_reason="",
            affected_systems=list(metadata.get("affected_systems") or ["site", "layout", "grading", "drainage", "utilities"]),
            assumptions=list(metadata.get("assumptions") or []),
            next_best_action="Rerun affected systems and review downstream blockers.",
            command_payload_updates={"persisted": True, "ready_language": "ready_for_engineer_review"},
        )

    if command_intent == "object_or_layout_command":
        object_type = str(command_payload.get("object_type") or "")
        operation = str(command_payload.get("operation") or "")
        if operation != "create":
            ask = f"I understood the {object_type or 'object'} update, but canonical edit support for that change is not implemented yet."
            return _truthful_decision_update(
                decision,
                assistant_message=ask,
                intent="conversation",
                run_mode="none",
                design_prompt="",
                needs_clarification=True,
                action_taken="blocked_missing_canonical_edit_support",
                action_blocked_reason=f"Canonical {object_type or 'object'} {operation or 'update'} edits are not supported by chat execution yet.",
                required_missing_inputs=[f"supported canonical {object_type or 'object'} edit workflow"],
                next_best_action="Tell Civora the exact new geometry in a full design prompt or use a supported create command.",
            )
        supported_create = object_type in {"building", "detention_basin", "parking"}
        if not supported_create:
            ask = f"I understood the {object_type or 'object'} create command, but chat cannot create that canonical object type yet."
            return _truthful_decision_update(
                decision,
                assistant_message=ask,
                intent="conversation",
                run_mode="none",
                design_prompt="",
                needs_clarification=True,
                action_taken="blocked_missing_canonical_edit_support",
                action_blocked_reason=f"Canonical create support is missing for object type: {object_type or 'unknown'}.",
                required_missing_inputs=[f"supported canonical {object_type or 'object'} creation workflow"],
                next_best_action="Use a full design prompt or provide a supported building, parking, or detention basin create command.",
            )
        if object_type == "building" and not (command_payload.get("width") and command_payload.get("depth")):
            ask = "I can create draft building geometry, but I need the building footprint size first."
            return _truthful_decision_update(
                decision,
                assistant_message=ask,
                intent="conversation",
                run_mode="none",
                design_prompt="",
                needs_clarification=True,
                action_taken="asked_clarifying_question",
                action_blocked_reason="Building creation needs width and depth.",
                required_missing_inputs=["building dimensions"],
                next_best_action=ask,
            )
        drafts = _safe_list(meta.get("canonical_draft_geometry"))
        draft_id = _next_draft_id(drafts, f"draft-{object_type.replace('_', '-')}")
        location_hint = str(command_payload.get("location_hint") or "planner_selected_feasible_location")
        draft = {
            "id": draft_id,
            "object_type": object_type,
            "operation": "create",
            "source": "chat_command",
            "status": "draft_geometry",
            "location_hint": location_hint,
            "width": command_payload.get("width"),
            "depth": command_payload.get("depth"),
            "engineer_review_required": True,
            "ready_language": "ready_for_engineer_review",
            "civora_signoff_allowed": False,
            "construction_release_allowed": False,
        }
        drafts.append(draft)
        edits = _safe_list(meta.get("chat_command_edits"))
        edits.append({"message": message, "action_taken": "created_draft_geometry", "draft_id": draft_id, "object_type": object_type})
        meta["canonical_draft_geometry"] = drafts
        meta["chat_command_edits"] = edits
        final_plan["meta"] = meta
        latest_result["final_plan"] = final_plan
        changed = True
        _save_project_record(project_store, record, project_input=project_input, latest_result=latest_result)
        return _truthful_decision_update(
            decision,
            assistant_message=f"I created draft {object_type.replace('_', ' ')} geometry in canonical project state for engineer review.",
            action_taken="created_draft_geometry",
            action_blocked_reason="",
            affected_systems=list(metadata.get("affected_systems") or ["layout"]),
            assumptions=list(metadata.get("assumptions") or []),
            next_best_action="Review the draft geometry location and rerun affected systems.",
            command_payload_updates={"persisted": True, "draft_id": draft_id, "ready_language": "ready_for_engineer_review"},
        )

    workflow_by_intent = {
        "grading_command": "grading",
        "drainage_command": "drainage",
        "utility_command": "utilities",
        "generate_command": "all_enabled_systems",
    }
    workflow = workflow_by_intent.get(command_intent)
    if workflow:
        meta.setdefault("chat_command_workflows", []).append(
            {
                "message": message,
                "workflow": workflow,
                "source": "chat_command",
                "status": "queued_for_planner",
                "engineer_review_required": True,
                "ready_language": "ready_for_engineer_review",
            }
        )
        final_plan["meta"] = meta
        latest_result["final_plan"] = final_plan
        changed = True
        if project_store and user_id:
            _save_project_record(project_store, record, project_input=project_input, latest_result=latest_result)
        return _truthful_decision_update(
            decision,
            action_taken="queued_engineering_workflow",
            action_blocked_reason="",
            affected_systems=list(metadata.get("affected_systems") or [workflow]),
            assumptions=list(metadata.get("assumptions") or []),
            next_best_action="Run the planner and review returned blockers before using the result as an engineer-review package.",
            command_payload_updates={"workflow": workflow, "persisted": changed, "ready_language": "ready_for_engineer_review"},
        )

    return decision


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
    decision = _apply_chat_command_execution(
        decision,
        context=context,
        record=record,
        project_store=project_store,
        user_id=user_id,
        message=message,
    )
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
