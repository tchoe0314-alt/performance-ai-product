from __future__ import annotations

from copy import deepcopy
import os
import re
from typing import Any, Callable, Dict, List, Optional

from backend.services.chat_learning_store import (
    append_chat_interaction_event,
    append_chat_learning_event,
)
from backend.planning.ai_orchestration_evidence import (
    attach_ai_orchestration_evidence_to_decision,
    attach_ai_orchestration_evidence_to_plan,
)
from backend.planning.candidate_review_inbox import (
    apply_candidate_review_decision,
    build_candidate_review_inbox,
)
from backend.planning.common import safe_str
from backend.planning.existing_conditions_online import fetch_online_existing_conditions
from backend.planning.map_feature_detection import build_map_feature_detection_report
from backend.planning.progress_timeline import build_progress_timeline
from backend.planning.smart_fix import build_smart_fix_recommendations
from backend.planning.setup_wizard import build_setup_wizard_state
from backend.planning.source_confidence_map import (
    attach_source_confidence_map,
    build_source_confidence_map,
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
    outcome: str = "",
    state_changed: Optional[bool] = None,
    referenced_object_ids: Optional[List[str]] = None,
    referenced_geometry_ids: Optional[List[str]] = None,
    confidence: Optional[float] = None,
    unsupported_reason: str = "",
    blocker: str = "",
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
    if confidence is not None:
        metadata["confidence"] = confidence
    metadata.setdefault("confidence", updated.get("confidence"))
    metadata["unsupported_reason"] = unsupported_reason or str(metadata.get("unsupported_reason") or "")
    metadata["blocker"] = blocker or action_blocked_reason or str(metadata.get("blocker") or "")
    metadata["outcome"] = outcome or (
        "unsupported_or_not_understood"
        if metadata["unsupported_reason"]
        else "understood_but_blocked"
        if action_blocked_reason
        else "understood_and_executed"
    )
    if state_changed is not None:
        metadata["state_changed"] = bool(state_changed)
    else:
        metadata.setdefault("state_changed", False)
    if referenced_object_ids is not None:
        metadata["referenced_object_ids"] = list(referenced_object_ids)
    else:
        metadata.setdefault("referenced_object_ids", [])
    if referenced_geometry_ids is not None:
        metadata["referenced_geometry_ids"] = list(referenced_geometry_ids)
    else:
        metadata.setdefault("referenced_geometry_ids", [])
    updated["response_metadata"] = metadata
    updated["required_missing_inputs"] = list(metadata.get("required_missing_inputs") or [])
    updated["action_taken"] = action_taken
    updated["action_blocked_reason"] = action_blocked_reason
    updated["affected_systems"] = list(metadata.get("affected_systems") or [])
    updated["assumptions"] = list(metadata.get("assumptions") or [])
    updated["next_best_action"] = next_best_action
    return _enrich_response_contract(updated, message=str(metadata.get("understood_goal") or ""))


def _save_project_record(project_store: Any, record: Dict[str, Any], *, project_input: Dict[str, Any], latest_result: Dict[str, Any]) -> None:
    final_plan = _safe_dict(latest_result.get("final_plan"))
    if final_plan:
        meta = _safe_dict(final_plan.get("meta"))
        meta["setup_wizard_state_v1"] = build_setup_wizard_state(
            project_input=project_input,
            latest_result=latest_result,
        )
        meta["source_confidence_map_v1"] = build_source_confidence_map(meta, project_input=project_input)
        meta["smart_fix_recommendations_v1"] = build_smart_fix_recommendations(final_plan, meta=meta)
        final_plan["meta"] = meta
        latest_result["final_plan"] = final_plan
    latest_result = attach_source_confidence_map(latest_result, project_input=project_input)
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


def _persist_orchestration_evidence(
    *,
    decision: Dict[str, Any],
    project_store: Optional[Any],
    user_id: Optional[str],
    project_id: Optional[str],
) -> None:
    evidence = _safe_dict(decision.get("ai_orchestration_evidence_v1"))
    metadata = _safe_dict(decision.get("response_metadata"))
    if not evidence or metadata.get("state_changed") is not True or not (project_store and user_id and project_id):
        return
    try:
        record = project_store.get_project(user_id=user_id, project_id=project_id)
        latest_result = deepcopy(_safe_dict(record.get("latest_result")))
        final_plan = _safe_dict(latest_result.get("final_plan"))
        if not final_plan:
            return
        latest_result["final_plan"] = attach_ai_orchestration_evidence_to_plan(final_plan, evidence)
        _save_project_record(
            project_store,
            record,
            project_input=deepcopy(_safe_dict(record.get("project_input"))),
            latest_result=latest_result,
        )
    except Exception:
        return


def _next_draft_id(items: List[Any], prefix: str) -> str:
    return f"{prefix}-{len(items) + 1}"


def _normalized_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _human_missing_input(value: str) -> str:
    text = str(value or "").strip()
    labels = {
        "detention basin or outfall target": "a basin or outfall target",
        "saved canonical project record": "a saved project",
        "valid canonical_geometry_handoff_v1": "a valid drawn-geometry handoff",
        "supported canonical road edit workflow": "a supported road edit workflow",
        "supported canonical road creation workflow": "a supported road creation workflow",
        "building dimensions": "building footprint dimensions",
        "explicit user-provided command inputs": "explicit user-provided command inputs",
    }
    return labels.get(text, text)


def _suggested_replies(metadata: Dict[str, Any]) -> List[str]:
    missing = [str(item) for item in _safe_list(metadata.get("required_missing_inputs")) if str(item)]
    if "detention basin or outfall target" in missing:
        return ["add a draft basin in the low corner", "I selected an outfall target"]
    if "saved canonical project record" in missing:
        return ["save project", "load project"]
    if any("road" in item for item in missing):
        return ["use the road panel", "describe the full design change"]
    if "building dimensions" in missing:
        return ["100 ft by 60 ft", "cancel that"]
    if str(metadata.get("intent") or "") == "site_setup":
        return ["lock site boundary", "draw the boundary instead"]
    return []


def _enrich_response_contract(decision: Dict[str, Any], *, message: str) -> Dict[str, Any]:
    updated = dict(decision)
    metadata = _safe_dict(updated.get("response_metadata"))
    missing = [str(item) for item in _safe_list(metadata.get("required_missing_inputs")) if str(item)]
    action_taken = str(metadata.get("action_taken") or updated.get("action_taken") or "")
    action_blocked_reason = str(metadata.get("action_blocked_reason") or updated.get("action_blocked_reason") or "")
    blockers = [str(item) for item in _safe_list(metadata.get("blockers")) if str(item)]
    if action_blocked_reason and action_blocked_reason not in blockers:
        blockers.append(action_blocked_reason)
    if metadata.get("blocker") and str(metadata["blocker"]) not in blockers:
        blockers.append(str(metadata["blocker"]))
    metadata["understood_goal"] = str(metadata.get("understood_goal") or message).strip()
    metadata["completed_actions"] = [action_taken] if action_taken and not missing and not action_blocked_reason and not action_taken.startswith("blocked") else []
    metadata["blocked_actions"] = [action_taken] if action_taken and (missing or action_blocked_reason or action_taken.startswith("blocked")) else []
    metadata["exact_missing_inputs"] = [_human_missing_input(item) for item in missing]
    metadata["missing_inputs"] = list(dict.fromkeys([*list(metadata.get("missing_inputs") or []), *missing]))
    metadata["blockers"] = list(dict.fromkeys(blockers))
    metadata["suggested_user_replies"] = _suggested_replies(metadata)
    metadata["can_execute_now"] = bool(
        updated.get("run_mode") not in {"", "none"}
        and not missing
        and not action_blocked_reason
        and not action_taken.startswith("blocked")
    )
    updated["response_metadata"] = metadata
    return updated


def _classification_type_from_message(message: str) -> str:
    lowered = _normalized_text(message)
    if "protected zone" in lowered or "protected_zone" in lowered or "wetland" in lowered or "buffer" in lowered:
        return "protected_zone"
    if "parking" in lowered:
        return "parking"
    if "building" in lowered:
        return "building"
    if "road" in lowered:
        return "road"
    if "basin" in lowered or "detention" in lowered or "pond" in lowered:
        return "basin"
    return ""


def _looks_like_geometry_reference(message: str) -> bool:
    lowered = _normalized_text(message)
    return any(token in lowered for token in ["this", "that", "selected", "drawn", "polygon", "shape", "geometry"])


def _looks_like_geometry_classification_request(message: str) -> bool:
    lowered = _normalized_text(message)
    if any(token in lowered for token in ["polygon", "shape", "geometry", "drawn", "selected"]):
        return True
    return bool(re.search(r"\b(turn|make|classify)\s+(this|that)\b", lowered))


def _collect_selected_ids(context: Dict[str, Any]) -> tuple[List[str], List[str]]:
    object_ids: List[str] = []
    geometry_ids: List[str] = []

    def _extend(target: List[str], value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                text = str(item or "").strip()
                if text and text not in target:
                    target.append(text)
        else:
            text = str(value or "").strip()
            if text and text not in target:
                target.append(text)

    for key in ("referenced_object_ids", "selected_object_ids"):
        _extend(object_ids, context.get(key))
    for key in ("referenced_geometry_ids", "selected_geometry_ids"):
        _extend(geometry_ids, context.get(key))
    for key in ("activePlacementId", "active_placement_id", "selected_object_id", "selected_geometry_id"):
        value = context.get(key)
        if key.endswith("geometry_id"):
            _extend(geometry_ids, value)
        else:
            _extend(object_ids, value)
    return object_ids, geometry_ids


def _canonical_geometry_handoffs(project_input: Dict[str, Any], latest_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    handoffs: List[Dict[str, Any]] = []
    manual_fields = _safe_dict(project_input.get("manual_fields"))
    for item in _safe_list(manual_fields.get("canonical_geometry_handoff_v1")):
        rec = _safe_dict(item)
        if rec:
            handoffs.append(rec)
    for item in _safe_list(project_input.get("canonical_geometry_handoff_v1")):
        rec = _safe_dict(item)
        if rec:
            handoffs.append(rec)
    for source in [manual_fields, project_input, _safe_dict(_safe_dict(latest_result.get("final_plan")).get("meta"))]:
        for item in _safe_list(source.get("site_objects")):
            rec = _safe_dict(item)
            handoff = _safe_dict(rec.get("canonical_geometry_handoff_v1"))
            if handoff:
                handoffs.append(handoff)
    seen = set()
    unique: List[Dict[str, Any]] = []
    for item in handoffs:
        key = (str(item.get("object_id") or ""), str(item.get("geometry_id") or ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _matching_handoffs(handoffs: List[Dict[str, Any]], object_ids: List[str], geometry_ids: List[str]) -> List[Dict[str, Any]]:
    if not object_ids and not geometry_ids:
        return []
    matches: List[Dict[str, Any]] = []
    object_set = set(object_ids)
    geometry_set = set(geometry_ids)
    for item in handoffs:
        object_id = str(item.get("object_id") or "").strip()
        geometry_id = str(item.get("geometry_id") or "").strip()
        if object_id in object_set or geometry_id in geometry_set:
            matches.append(item)
    return matches


def _handoff_blockers(handoff: Dict[str, Any]) -> List[str]:
    blockers = [str(item) for item in _safe_list(handoff.get("blockers")) if str(item)]
    if handoff.get("valid") is not True:
        blockers.append("canonical_geometry_handoff_v1 is not valid")
    if handoff.get("source") != "manual_drawn":
        blockers.append("source must be manual_drawn")
    if handoff.get("confidence") != "user_drawn_review_required":
        blockers.append("confidence must be user_drawn_review_required")
    if handoff.get("engineering_status") != "draft_review_required":
        blockers.append("engineering_status must remain draft_review_required")
    if not str(handoff.get("object_id") or "").strip():
        blockers.append("object_id is required")
    if not str(handoff.get("geometry_id") or "").strip():
        blockers.append("geometry_id is required")
    return list(dict.fromkeys(blockers))


def _package_status(record: Dict[str, Any]) -> str:
    for key in ("status", "review_status", "export_status", "readiness_status", "qa_status"):
        value = str(record.get(key) or "").strip()
        if value:
            return value
    if record.get("ready") is True or record.get("production_usable") is True or record.get("production_evidence_ready") is True:
        return "ready_for_review"
    if record.get("construction_release_blocked") is True or record.get("export_blocked") is True:
        return "blocked"
    return "present" if record else "missing"


def _package_blockers(record: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    for key in ("blockers", "warnings", "missing_inputs", "blocked_reasons", "post_rerun_stale_outputs", "stale_outputs"):
        for item in _safe_list(record.get(key)):
            if isinstance(item, dict):
                text = str(item.get("field") or item.get("reason") or item.get("message") or item.get("code") or "").strip()
            else:
                text = str(item or "").strip()
            if text and text not in blockers:
                blockers.append(text)
    return blockers


def _build_capability_statuses(project_input: Dict[str, Any], latest_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    final_plan = _safe_dict(latest_result.get("final_plan"))
    meta = _safe_dict(final_plan.get("meta") or latest_result.get("metadata") or latest_result.get("meta"))
    production = _safe_dict(meta.get("production_evidence"))
    quantity_cost = _safe_dict(production.get("quantity_cost"))
    handoffs = _canonical_geometry_handoffs(project_input, latest_result)

    def rec(key: str) -> Dict[str, Any]:
        return _safe_dict(meta.get(key))

    def row(key: str, label: str, record: Dict[str, Any], *, next_action: str) -> Dict[str, Any]:
        blockers = _package_blockers(record)
        present = bool(record)
        return {
            "key": key,
            "label": label,
            "exposed": present,
            "surfaces": ["UI", "chat", "API", "report"],
            "status": _package_status(record),
            "blockers": blockers,
            "missing_wiring": "" if present else f"{label} evidence is not attached to the current plan.",
            "exact_fix": next_action if (blockers or not present) else "Review accepted evidence and regenerate the package if project inputs changed.",
        }

    return [
        row(
            "standards_source_registry",
            "Standards source registry",
            rec("standards_source_registry") or rec("standards_package"),
            next_action="Run standards discovery, review official HTTPS sources, accept the applicable source, and regenerate the standards package.",
        ),
        row(
            "candidate_standards_review",
            "Candidate standards review",
            rec("candidate_rule_report") or rec("standards_acceptance_report") or rec("standards_package"),
            next_action="Build or extract a standards review packet, then accept or reject each candidate rule before relying on it.",
        ),
        row(
            "existing_conditions_package",
            "Existing conditions package",
            rec("existing_conditions_package"),
            next_action="Upload or fetch survey/topo/GIS existing-condition sources and rerun import validation.",
        ),
        row(
            "survey_control_package",
            "Survey control package",
            rec("survey_control_package"),
            next_action="Attach survey/control evidence with datum, benchmark, coordinate system, and verification status.",
        ),
        row(
            "map_feature_candidates",
            "Map feature candidates",
            rec("map_feature_detection_report_v1"),
            next_action="Analyze a map snapshot or official GIS source, then review candidates before turning them into draft objects.",
        ),
        row(
            "engine_depth_audit",
            "Engine depth audit",
            rec("engine_depth_audit") or rec("engine_readiness"),
            next_action="Run the engine depth audit and address each discipline validation blocker.",
        ),
        row(
            "production_evidence",
            "Production evidence",
            production,
            next_action="Assemble production evidence after standards, existing conditions, quantities, export audit, and reactive checks exist.",
        ),
        row(
            "cost_book_pricing",
            "Cost book / pricing",
            quantity_cost or rec("cost_estimate") or rec("cost_package_status"),
            next_action="Normalize and validate an approved current unit-price book, then rerun quantities/cost evidence.",
        ),
        row(
            "export_package_report",
            "Export package report",
            rec("export_package_report_v1") or rec("export_audit"),
            next_action="Generate the export package report so support matrix, traceability, and blockers are recorded.",
        ),
        row(
            "construction_document_support_package",
            "Construction document support package",
            rec("construction_document_support_package_v1") or rec("construction_package_manifest"),
            next_action="Build the construction document support package after deliverables, QA, standards, survey/control, and pricing evidence exist.",
        ),
        row(
            "engineer_review_package",
            "Engineer review package",
            rec("engineer_review_package_v1"),
            next_action="Generate the engineer review package and route unresolved blockers to a licensed external reviewer.",
        ),
        row(
            "reactive_rerun_evidence",
            "Reactive rerun evidence",
            rec("reactive_update_report") or rec("reactive_partial_rerun"),
            next_action="Make a scoped model edit and run the dependency-aware partial rerun before exporting stale outputs.",
        ),
        {
            "key": "cad_geometry_handoff",
            "label": "CAD geometry handoff",
            "exposed": bool(handoffs),
            "surfaces": ["UI", "chat", "API", "report"],
            "status": "present" if handoffs else "missing",
            "blockers": [] if handoffs else ["canonical_geometry_handoff_v1_missing"],
            "missing_wiring": "" if handoffs else "No canonical geometry handoff exists for current drawn/imported geometry.",
            "exact_fix": "Draw or import geometry, classify it, and preserve canonical_geometry_handoff_v1 for CAD/export.",
        },
    ]


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
            outcome="understood_needs_more_info",
            state_changed=False,
            blocker="Strict/no-assumption mode blocks inferred command inputs.",
        )

    if command_intent not in {
        "site_setup",
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
    if metadata.get("action_blocked_reason"):
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
                outcome="understood_but_blocked",
                state_changed=False,
                blocker="No saved canonical project record is available for this command.",
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

    if command_intent == "site_setup":
        width = command_payload.get("lot_width")
        height = command_payload.get("lot_height")
        area = command_payload.get("site_area_acres")
        address = str(command_payload.get("address") or "").strip()
        if not (width or height or address):
            ask = "I understood the site setup, but I need a site size, acreage, or address before changing canonical state."
            return _truthful_decision_update(
                decision,
                assistant_message=ask,
                intent="conversation",
                run_mode="none",
                design_prompt="",
                needs_clarification=True,
                action_taken="asked_clarifying_question",
                action_blocked_reason="Site setup command did not include dimensions, acreage, or address.",
                required_missing_inputs=["site dimensions, acreage, or address"],
                next_best_action=ask,
                outcome="understood_needs_more_info",
                state_changed=False,
                blocker="Site setup command did not include dimensions, acreage, or address.",
            )
        manual_fields = _safe_dict(project_input.get("manual_fields"))
        lot = _safe_dict(manual_fields.get("lot"))
        changed_fields: List[str] = []
        if width and height:
            lot.update(
                {
                    "w": width,
                    "h": height,
                    "area_sf": round(float(width) * float(height), 3),
                    "site_area_acres": area,
                    "source": "chat_site_setup",
                    "boundary_status": "draft_unlocked",
                }
            )
            manual_fields["lot"] = lot
            project_input["site_area_acres"] = area
            meta["site_area_acres"] = area
            changed_fields.extend(["manual_fields.lot", "site_area_acres"])
        site_inputs = _safe_dict(_safe_dict(project_input.get("meta")).get("site_inputs"))
        location_context = _safe_dict(meta.get("location_context"))
        if address:
            site_inputs["address"] = address
            location_context = {
                "address": address,
                "matched_address": "",
                "geocode": {"lat": None, "lng": None, "provider": "", "source": "", "confidence": None},
                "evidence_source": "chat_address",
                "truth_label": "Address text is location context only; it is not a site boundary, survey, control, parcel, or final reliance source.",
                "status": "address_unverified_geocode_required",
            }
            meta["location_context"] = location_context
            meta["map_feature_detection_report_v1"] = build_map_feature_detection_report(location_context=location_context)
            changed_fields.extend(["project_input.meta.site_inputs.address", "final_plan.meta.location_context"])
        project_meta = _safe_dict(project_input.get("meta"))
        if site_inputs:
            project_meta["site_inputs"] = site_inputs
            project_input["meta"] = project_meta
        if manual_fields:
            project_input["manual_fields"] = manual_fields
        meta["canonical_site_state"] = {
            "site_area_acres": area,
            "lot_width": width,
            "lot_height": height,
            "address": address,
            "boundary_status": "draft_unlocked",
            "source": "chat_site_setup",
            "location_context": location_context,
            "ready_language": "ready_for_engineer_review",
            "engineer_review_required": True,
            "civora_signoff_allowed": False,
            "construction_release_allowed": False,
        }
        meta.setdefault("chat_command_edits", []).append(
            {
                "message": message,
                "action_taken": "updated_site_dimensions_and_location_evidence",
                "changed_fields": changed_fields,
            }
        )
        final_plan["meta"] = meta
        latest_result["final_plan"] = final_plan
        _save_project_record(project_store, record, project_input=project_input, latest_result=latest_result)
        if width and height and address:
            assistant = (
                f"I set the draft site size to {float(width):g} ft x {float(height):g} ft and recorded {address} as location evidence only. "
                f"Do you want to lock this {float(width):g} ft x {float(height):g} ft site boundary at this address?"
            )
        elif width and height:
            assistant = (
                f"I set the draft site size to {float(width):g} ft x {float(height):g} ft. "
                f"Do you want to lock this {float(width):g} ft x {float(height):g} ft site boundary?"
            )
        else:
            assistant = (
                f"I recorded {address} as address/location evidence only. Address evidence is not a trusted site boundary. "
                "What site size should I use, or do you want to draw the boundary?"
            )
        return _truthful_decision_update(
            decision,
            assistant_message=assistant,
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=not bool(width and height),
            action_taken="updated_site_dimensions_and_location_evidence",
            action_blocked_reason="",
            affected_systems=["site"],
            assumptions=[],
            next_best_action="Lock the site boundary or draw/confirm the boundary before generation.",
            command_payload_updates={"persisted": True, "changed_fields": changed_fields, "ready_language": "ready_for_engineer_review"},
            outcome="understood_and_answered",
            state_changed=True,
        )

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
                outcome="understood_needs_more_info",
                state_changed=False,
                blocker="Site area value is missing from the parsed command.",
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
            outcome="understood_and_executed",
            state_changed=True,
        )

    if command_intent == "object_or_layout_command":
        object_type = str(command_payload.get("object_type") or "")
        operation = str(command_payload.get("operation") or "")
        classification_type = _classification_type_from_message(message)
        if classification_type and _looks_like_geometry_reference(message) and _looks_like_geometry_classification_request(message):
            handoffs = _canonical_geometry_handoffs(project_input, latest_result)
            selected_object_ids, selected_geometry_ids = _collect_selected_ids(context)
            matches = _matching_handoffs(handoffs, selected_object_ids, selected_geometry_ids)
            if not selected_object_ids and not selected_geometry_ids:
                ask = "Which drawn geometry should I classify? Select one polygon or shape, then ask again."
                return _truthful_decision_update(
                    decision,
                    assistant_message=ask,
                    intent="conversation",
                    run_mode="none",
                    design_prompt="",
                    needs_clarification=True,
                    action_taken="asked_targeted_geometry_selection_question",
                    action_blocked_reason="No selected or referenced drawn geometry was provided.",
                    required_missing_inputs=["selected drawn geometry"],
                    next_best_action=ask,
                    outcome="understood_needs_more_info",
                    state_changed=False,
                    referenced_object_ids=[],
                    referenced_geometry_ids=[],
                )
            if len(matches) != 1:
                ask = "I need exactly one selected drawn geometry to classify. Please select one shape and try again."
                return _truthful_decision_update(
                    decision,
                    assistant_message=ask,
                    intent="conversation",
                    run_mode="none",
                    design_prompt="",
                    needs_clarification=True,
                    action_taken="asked_targeted_geometry_selection_question",
                    action_blocked_reason=f"Referenced geometry was ambiguous: {len(matches)} matching handoffs found.",
                    required_missing_inputs=["one unambiguous selected drawn geometry"],
                    next_best_action=ask,
                    outcome="understood_needs_more_info",
                    state_changed=False,
                    referenced_object_ids=selected_object_ids,
                    referenced_geometry_ids=selected_geometry_ids,
                )
            handoff = matches[0]
            blockers = _handoff_blockers(handoff)
            referenced_object_ids = [str(handoff.get("object_id") or "").strip()]
            referenced_geometry_ids = [str(handoff.get("geometry_id") or "").strip()]
            if blockers:
                reason = "; ".join(blockers)
                return _truthful_decision_update(
                    decision,
                    assistant_message=f"I found the drawn geometry, but I cannot classify it yet: {reason}.",
                    intent="conversation",
                    run_mode="none",
                    design_prompt="",
                    needs_clarification=True,
                    action_taken="blocked_invalid_geometry_handoff",
                    action_blocked_reason=reason,
                    required_missing_inputs=["valid canonical_geometry_handoff_v1"],
                    next_best_action="Fix the drawn geometry handoff blockers, then classify it again.",
                    outcome="understood_but_blocked",
                    state_changed=False,
                    blocker=reason,
                    referenced_object_ids=referenced_object_ids,
                    referenced_geometry_ids=referenced_geometry_ids,
                )
            updates = _safe_list(meta.get("canonical_geometry_classification_updates"))
            update_id = _next_draft_id(updates, f"draft-{classification_type.replace('_', '-')}-classification")
            classification_update = {
                "id": update_id,
                "object_id": referenced_object_ids[0],
                "geometry_id": referenced_geometry_ids[0],
                "object_type": classification_type,
                "source": "manual_drawn",
                "confidence": "user_drawn_review_required",
                "engineering_status": "draft_review_required",
                "status": "draft_review_required",
                "ready_language": "ready_for_engineer_review",
                "engineer_review_required": True,
                "civora_signoff_allowed": False,
                "construction_release_allowed": False,
                "canonical_geometry_handoff_v1": deepcopy(handoff),
            }
            updates.append(classification_update)
            edits = _safe_list(meta.get("chat_command_edits"))
            edits.append(
                {
                    "message": message,
                    "action_taken": "classified_drawn_geometry",
                    "classification_id": update_id,
                    "object_type": classification_type,
                    "object_id": referenced_object_ids[0],
                    "geometry_id": referenced_geometry_ids[0],
                }
            )
            meta["canonical_geometry_classification_updates"] = updates
            meta["chat_command_edits"] = edits
            final_plan["meta"] = meta
            latest_result["final_plan"] = final_plan
            _save_project_record(project_store, record, project_input=project_input, latest_result=latest_result)
            return _truthful_decision_update(
                decision,
                assistant_message=(
                    f"I classified the selected manual drawn geometry as draft {classification_type.replace('_', ' ')} "
                    "for engineer review. I did not run engineering generation."
                ),
                intent="conversation",
                run_mode="none",
                design_prompt="",
                needs_clarification=False,
                action_taken="classified_drawn_geometry",
                action_blocked_reason="",
                affected_systems=["layout"],
                assumptions=list(metadata.get("assumptions") or []),
                next_best_action="Review the draft classification, then run affected systems only when you are ready.",
                command_payload_updates={
                    "persisted": True,
                    "classification_id": update_id,
                    "object_type": classification_type,
                    "ready_language": "ready_for_engineer_review",
                },
                outcome="understood_and_executed",
                state_changed=True,
                referenced_object_ids=referenced_object_ids,
                referenced_geometry_ids=referenced_geometry_ids,
            )
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
                outcome="understood_but_blocked",
                state_changed=False,
                blocker=f"Canonical {object_type or 'object'} {operation or 'update'} edits are not supported by chat execution yet.",
            )
        supported_create = object_type in {"building", "basin", "detention_basin", "parking"}
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
                outcome="understood_but_blocked",
                state_changed=False,
                blocker=f"Canonical create support is missing for object type: {object_type or 'unknown'}.",
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
                outcome="understood_needs_more_info",
                state_changed=False,
                blocker="Building creation needs width and depth.",
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
            outcome="understood_and_executed",
            state_changed=True,
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
            outcome="understood_and_executed",
            state_changed=changed,
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
    for source_key, merged_key in [
        ("missing_inputs", "missing_inputs"),
        ("required_missing_inputs", "missing_inputs"),
        ("blockers", "blockers"),
        ("standards_status", "standards_status"),
        ("existing_conditions_status", "existing_conditions_status"),
        ("engine_depth_status", "engine_depth_status"),
        ("depth_status", "engine_depth_status"),
        ("engineer_review_status", "engineer_review_status"),
        ("next_best_action", "next_best_action"),
        ("site_locked", "site_locked"),
        ("address_status", "address_status"),
        ("site_size_status", "site_size_status"),
    ]:
        value = meta.get(source_key)
        if value is None and source_key in latest_result:
            value = latest_result.get(source_key)
        if value is None and source_key in project_input:
            value = project_input.get(source_key)
        if value is not None and not merged.get(merged_key):
            merged[merged_key] = value
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
    capability_statuses = _build_capability_statuses(project_input, latest_result)
    if capability_statuses:
        merged["capability_statuses"] = capability_statuses
    wizard_state = build_setup_wizard_state(
        project_input=project_input,
        latest_result=latest_result,
        context={**merged, "capability_statuses": capability_statuses},
    )
    merged["setup_wizard_state_v1"] = wizard_state
    progress_timeline = build_progress_timeline(
        project_input=project_input,
        latest_result=latest_result,
        context={**merged, "capability_statuses": capability_statuses, "setup_wizard_state_v1": wizard_state},
    )
    merged["progress_timeline_v1"] = progress_timeline
    if (
        meta.get("site_locked") is False
        and safe_str(meta.get("site_size_status")) == "provided"
        and safe_str(meta.get("address_status")).lower() not in {"", "missing", "not_set"}
    ):
        merged["next_best_action"] = "Lock the site boundary after confirming the address or site size."
    if safe_str(meta.get("address_status")).lower() in {"missing", "not_set"}:
        merged["next_best_action"] = "Enter an address, provide coordinates, or choose a blank site."
    if not merged.get("next_best_action"):
        merged["next_best_action"] = str(progress_timeline.get("next_action") or wizard_state.get("next_action") or "")
    inbox = build_candidate_review_inbox(meta)
    if inbox.get("candidate_count"):
        merged["candidate_review_inbox_v1"] = inbox
    smart_fix = _safe_dict(meta.get("smart_fix_recommendations_v1"))
    if smart_fix:
        merged["smart_fix_recommendations_v1"] = smart_fix
        next_best = _safe_dict(smart_fix.get("next_best_recommendation"))
        if next_best:
            merged["smart_fix_next_best"] = next_best

    if not merged.get("project_type"):
        merged["project_type"] = project_input.get("project_type") or meta.get("project_type")
    if not merged.get("lot_width"):
        merged["lot_width"] = lot.get("w") or lot.get("width")
    if not merged.get("lot_height"):
        merged["lot_height"] = lot.get("h") or lot.get("height")
    if not merged.get("parking_count"):
        merged["parking_count"] = site_plan.get("parking_count") or meta.get("parking_count")
    return merged


def _online_discovery_from_record(record: Dict[str, Any]) -> Dict[str, Any]:
    project_input = _safe_dict(record.get("project_input"))
    project_meta = _safe_dict(project_input.get("meta"))
    site_inputs = _safe_dict(project_meta.get("site_inputs"))
    latest_result = _safe_dict(record.get("latest_result"))
    final_plan = _safe_dict(latest_result.get("final_plan"))
    plan_meta = _safe_dict(final_plan.get("meta"))
    return _safe_dict(site_inputs.get("online_existing_conditions_discovery_v1") or plan_meta.get("online_existing_conditions_discovery_v1"))


def _address_from_online_message(message: str, record: Optional[Dict[str, Any]]) -> str:
    cleaned = re.sub(r"(?i)\b(find site data from this address|use online sources if available|find site data|online sources|from this address)\b", "", message)
    cleaned = cleaned.strip(" :-,")
    if cleaned and len(cleaned) > 4:
        return cleaned
    if record:
        site_inputs = _safe_dict(_safe_dict(_safe_dict(record.get("project_input")).get("meta")).get("site_inputs"))
        return safe_str(site_inputs.get("address") or _safe_dict(site_inputs.get("geocode")).get("display_name"))
    return ""


def _summarize_online_discovery(discovery: Dict[str, Any], *, why_buildings: bool = False) -> str:
    if not discovery:
        return "I do not have an online existing-conditions discovery report saved for this project yet."
    sources = [_safe_dict(item) for item in _safe_list(discovery.get("sources")) if _safe_dict(item)]
    found = [item for item in sources if int(item.get("candidate_count") or 0) > 0]
    missing = [item for item in sources if int(item.get("candidate_count") or 0) <= 0]
    if why_buildings:
        building = next((item for item in sources if safe_str(item.get("key")) == "building_footprints"), {})
        blockers = _safe_list(_safe_dict(building).get("blockers"))
        reason = safe_str(blockers[0] if blockers else "", "No building footprint source is configured or available.")
        return f"It did not find buildings because: {reason} Building footprints stay candidate/review-required until a configured provider returns features and the user reviews them."
    lines = []
    if found:
        lines.append(
            "Found candidates: "
            + "; ".join(
                f"{safe_str(item.get('label') or item.get('key'))} ({int(item.get('candidate_count') or 0)}, {safe_str(item.get('provider') or item.get('source_type'))})"
                for item in found[:6]
            )
            + "."
        )
    else:
        lines.append("No online source candidates were found from the currently available providers.")
    if missing:
        lines.append(
            "Missing/unavailable: "
            + "; ".join(
                f"{safe_str(item.get('label') or item.get('key'))}: {safe_str((_safe_list(item.get('blockers')) or ['missing/unavailable'])[0])}"
                for item in missing[:6]
            )
            + "."
        )
    lines.append("Everything online is candidate/review-required and does not satisfy survey/control.")
    return " ".join(lines)


def _online_discovery_chat_response(
    *,
    message: str,
    record: Optional[Dict[str, Any]],
    project_store: Optional[Any],
    user_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    normalized = _normalized_text(message)
    asks_summary = any(
        phrase in normalized
        for phrase in (
            "what did you find online",
            "what did you find from online",
            "what online sources",
            "online existing conditions",
        )
    )
    asks_find = any(phrase in normalized for phrase in ("find site data from this address", "find site data", "use online sources if available"))
    asks_building_gap = "why" in normalized and any(phrase in normalized for phrase in ("didn't it find buildings", "did not find buildings", "no buildings", "building footprints"))
    if not any((asks_summary, asks_find, asks_building_gap)):
        return None
    if not record:
        return _truthful_decision_update(
            {},
            assistant_message="I need a saved project before I can run or summarize online source discovery.",
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=True,
            action_taken="blocked_missing_online_discovery_project",
            action_blocked_reason="No saved project record is available for online source discovery.",
            required_missing_inputs=["saved canonical project record"],
            affected_systems=["site"],
            assumptions=[],
            next_best_action="Save or load a project, apply an address, then ask again.",
            outcome="understood_but_blocked",
            state_changed=False,
            blocker="No saved project record is available for online source discovery.",
        )
    if asks_find:
        address = _address_from_online_message(message, record)
        if not address:
            return _truthful_decision_update(
                {},
                assistant_message="I need an address before I can look for online source candidates.",
                intent="conversation",
                run_mode="none",
                design_prompt="",
                needs_clarification=True,
                action_taken="blocked_online_discovery_missing_address",
                action_blocked_reason="Address is missing.",
                required_missing_inputs=["address"],
                affected_systems=["site"],
                assumptions=[],
                next_best_action="Apply an address or include the address in your message.",
                outcome="understood_but_blocked",
                state_changed=False,
                blocker="Address is missing.",
            )
        result = fetch_online_existing_conditions(
            address=address,
            parcel_service_url=safe_str(os.getenv("CIVORA_PARCEL_ARCGIS_SERVICE_URL")),
            parcel_layer_id=int(os.getenv("CIVORA_PARCEL_ARCGIS_LAYER_ID") or "0"),
            building_footprints_service_url=safe_str(os.getenv("CIVORA_BUILDING_FOOTPRINTS_ARCGIS_SERVICE_URL")),
            building_footprints_layer_id=int(os.getenv("CIVORA_BUILDING_FOOTPRINTS_ARCGIS_LAYER_ID") or "0"),
            roads_service_url=safe_str(os.getenv("CIVORA_ROADS_ROW_ARCGIS_SERVICE_URL")),
            roads_layer_id=int(os.getenv("CIVORA_ROADS_ROW_ARCGIS_LAYER_ID") or "0"),
            easements_service_url=safe_str(os.getenv("CIVORA_EASEMENTS_ARCGIS_SERVICE_URL")),
            easements_layer_id=int(os.getenv("CIVORA_EASEMENTS_ARCGIS_LAYER_ID") or "0"),
            zoning_service_url=safe_str(os.getenv("CIVORA_ZONING_ARCGIS_SERVICE_URL")),
            zoning_layer_id=int(os.getenv("CIVORA_ZONING_ARCGIS_LAYER_ID") or "0"),
            utilities_service_url=safe_str(os.getenv("CIVORA_EXISTING_UTILITIES_ARCGIS_SERVICE_URL")),
            utilities_layer_id=int(os.getenv("CIVORA_EXISTING_UTILITIES_ARCGIS_LAYER_ID") or "0"),
        )
        discovery = _safe_dict(result.get("online_existing_conditions_discovery_v1"))
        latest_result = deepcopy(_safe_dict(record.get("latest_result")))
        final_plan = _safe_dict(latest_result.get("final_plan"))
        meta = _safe_dict(final_plan.get("meta"))
        meta["online_existing_conditions_discovery_v1"] = discovery
        meta["map_feature_detection_report_v1"] = result.get("map_feature_detection_report_v1")
        meta["existing_conditions_package"] = result.get("existing_conditions_package")
        meta["location_context"] = result.get("location_context")
        final_plan["meta"] = meta
        latest_result["final_plan"] = final_plan
        project_input = deepcopy(_safe_dict(record.get("project_input")))
        project_meta = _safe_dict(project_input.get("meta"))
        site_inputs = _safe_dict(project_meta.get("site_inputs"))
        site_inputs["address"] = address
        site_inputs["online_existing_conditions_discovery_v1"] = discovery
        site_inputs["map_feature_detection_report_v1"] = result.get("map_feature_detection_report_v1")
        site_inputs["existing_conditions_package"] = result.get("existing_conditions_package")
        project_meta["site_inputs"] = site_inputs
        project_input["meta"] = project_meta
        if project_store and user_id:
            _save_project_record(project_store, {**record, "_user_id": user_id}, project_input=project_input, latest_result=latest_result)
        return _truthful_decision_update(
            {},
            assistant_message=_summarize_online_discovery(discovery),
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=False,
            action_taken="fetched_online_existing_conditions_candidates",
            action_blocked_reason="",
            affected_systems=["site", "standards"],
            assumptions=[],
            next_best_action="Review found and missing online sources in the setup/data panel before using any candidate.",
            command_payload_updates={"online_existing_conditions_discovery_v1": discovery, "ui_navigation_target": "site_existing", "requested_ui_mode": "setup"},
            outcome="understood_and_executed",
            state_changed=True,
        )
    discovery = _online_discovery_from_record(record)
    return _truthful_decision_update(
        {},
        assistant_message=_summarize_online_discovery(discovery, why_buildings=asks_building_gap),
        intent="conversation",
        run_mode="none",
        design_prompt="",
        needs_clarification=not bool(discovery),
        action_taken="reported_online_existing_conditions_discovery",
        action_blocked_reason="" if discovery else "No online discovery report is saved for this project.",
        required_missing_inputs=[] if discovery else ["online existing-conditions discovery report"],
        affected_systems=["site", "standards"],
        assumptions=[],
        next_best_action="Apply an address or ask me to find site data from this address.",
        command_payload_updates={"online_existing_conditions_discovery_v1": discovery, "ui_navigation_target": "site_existing", "requested_ui_mode": "setup"},
        outcome="understood_and_answered" if discovery else "understood_but_blocked",
        state_changed=False,
        blocker="" if discovery else "No online discovery report is saved for this project.",
    )


def _candidate_chat_response(
    *,
    message: str,
    record: Optional[Dict[str, Any]],
    project_store: Optional[Any],
    user_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    normalized = _normalized_text(message)
    asks_found = any(
        phrase in normalized
        for phrase in (
            "what did you find",
            "what did you find online",
            "what did you find from online",
            "what candidates did you find",
        )
    )
    asks_pending = "pending" in normalized and "candidate" in normalized
    asks_why_candidate = any(
        phrase in normalized
        for phrase in (
            "why is this only a candidate",
            "why are these only candidates",
            "why is it only a candidate",
            "why candidate",
        )
    )
    wants_parcel = any(phrase in normalized for phrase in ("use the parcel boundary", "use parcel boundary", "accept the parcel boundary"))
    accepts_buildings = ("accept" in normalized or "use" in normalized) and any(
        phrase in normalized for phrase in ("those buildings", "the buildings", "building candidates", "building footprints")
    )
    rejects_buildings = ("reject" in normalized or "remove" in normalized or "decline" in normalized) and any(
        phrase in normalized for phrase in ("those buildings", "the buildings", "building candidates", "building footprints")
    )
    rejects_roads = ("reject" in normalized or "remove" in normalized or "decline" in normalized) and any(
        phrase in normalized for phrase in ("those roads", "the roads", "road candidates", "roads", "row candidates", "right of way")
    )
    if not any((asks_found, asks_pending, asks_why_candidate, wants_parcel, accepts_buildings, rejects_buildings, rejects_roads)):
        return None
    if not record:
        return _truthful_decision_update(
            {},
            assistant_message="I need a saved project before I can review online/GIS/map candidates.",
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=True,
            action_taken="blocked_missing_candidate_project",
            action_blocked_reason="No saved project record is available for candidate review.",
            required_missing_inputs=["saved canonical project record"],
            affected_systems=["site"],
            assumptions=[],
            next_best_action="Save or load a project with discovered candidates, then ask again.",
            outcome="understood_but_blocked",
            state_changed=False,
            blocker="No saved project record is available for candidate review.",
        )
    latest_result = deepcopy(_safe_dict(record.get("latest_result")))
    final_plan = _safe_dict(latest_result.get("final_plan"))
    meta = _safe_dict(final_plan.get("meta"))
    inbox = build_candidate_review_inbox(meta)
    candidates = [_safe_dict(item) for item in _safe_list(inbox.get("candidates")) if _safe_dict(item)]

    def matching(*candidate_types: str, status: str = "") -> List[Dict[str, Any]]:
        wanted = {item for item in candidate_types if item}
        result = [item for item in candidates if str(item.get("candidate_type") or "") in wanted]
        if status:
            result = [item for item in result if str(item.get("status") or "") == status]
        return result

    if asks_why_candidate:
        return _truthful_decision_update(
            {},
            assistant_message=(
                "It is only a candidate because the source is discovered/imported/detected evidence, not survey truth. "
                "Accepting it only promotes it to draft/review-required project evidence; it still needs source verification, survey/control, and professional review before final reliance."
            ),
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=False,
            action_taken="explained_candidate_review_truth_boundary",
            action_blocked_reason="",
            affected_systems=["site", "standards"],
            assumptions=[],
            next_best_action="Use the Candidate Review Inbox to accept, reject, or leave the candidate pending.",
            command_payload_updates={"candidate_review_inbox_v1": inbox, "ui_navigation_target": "data", "requested_ui_mode": "data"},
            outcome="understood_and_answered",
            state_changed=False,
        )

    if asks_found or asks_pending:
        visible = [item for item in candidates if not asks_pending or str(item.get("status") or "") == "pending"]
        counts = _safe_dict(inbox.get("counts"))
        if not visible:
            msg = "I do not have any pending candidates in this project yet." if asks_pending else "I do not have any online/GIS/map candidates saved for this project yet."
        else:
            lines = [
                f"{safe_str(item.get('label') or item.get('candidate_type'))}: {safe_str(item.get('status'))}, source {safe_str(item.get('source'))}, provider {safe_str(item.get('provider'))}, confidence {item.get('confidence')}, objects {int(item.get('object_count') or 1)}, reason {safe_str(item.get('blocker_review_reason'))}"
                for item in visible[:6]
            ]
            prefix = (
                f"Candidate inbox: {counts.get('pending', 0)} pending, {counts.get('accepted', 0)} accepted, {counts.get('rejected', 0)} rejected."
            )
            msg = prefix + "\n" + "\n".join(f"- {line}" for line in lines)
        return _truthful_decision_update(
            {},
            assistant_message=msg,
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=False,
            action_taken="reported_candidate_review_inbox",
            action_blocked_reason="",
            affected_systems=["site", "standards"],
            assumptions=[],
            next_best_action="Accept, reject, or leave candidates pending in the candidate review inbox.",
            command_payload_updates={"candidate_review_inbox_v1": inbox, "ui_navigation_target": "data", "requested_ui_mode": "data"},
            outcome="understood_and_answered",
            state_changed=False,
        )

    action = ""
    targets: List[Dict[str, Any]] = []
    reason = ""
    if wants_parcel:
        action = "accept"
        targets = matching("parcel_site_boundary", status="pending") or matching("parcel_site_boundary")
        reason = "User asked to use the parcel boundary as draft/review-required evidence."
    elif accepts_buildings:
        action = "accept"
        targets = matching("building_footprint", status="pending") or matching("building_footprint")
        reason = "User asked to accept building footprint candidates as draft/review-required evidence."
    elif rejects_buildings:
        action = "reject"
        targets = matching("building_footprint", status="pending") or matching("building_footprint")
        reason = "User rejected building footprint candidates."
    elif rejects_roads:
        action = "reject"
        targets = matching("road_row", status="pending") or matching("road_row")
        reason = "User rejected road/ROW candidates."
    if not targets:
        label = "parcel boundary" if wants_parcel else "road/ROW" if rejects_roads else "building footprint"
        return _truthful_decision_update(
            {},
            assistant_message=f"I could not find a {label} candidate to review in the saved project.",
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=True,
            action_taken="blocked_candidate_not_found",
            action_blocked_reason=f"No {label} candidate is available.",
            required_missing_inputs=[f"{label} candidate"],
            affected_systems=["site"],
            assumptions=[],
            next_best_action="Fetch/import GIS or map candidates, then ask again.",
            outcome="understood_but_blocked",
            state_changed=False,
            blocker=f"No {label} candidate is available.",
        )
    if not (project_store and user_id):
        return None
    decision = apply_candidate_review_decision(
        meta,
        candidate_ids=[safe_str(item.get("candidate_id")) for item in targets],
        action=action,
        reviewer_id=user_id,
        reason=reason,
    )
    final_plan["meta"] = _safe_dict(decision.get("updated_meta"))
    latest_result["final_plan"] = final_plan
    _save_project_record(
        project_store,
        {**record, "_user_id": user_id},
        project_input=deepcopy(_safe_dict(record.get("project_input"))),
        latest_result=latest_result,
    )
    changed = len(targets)
    verb = "accepted as draft/review-required evidence" if action == "accept" else "rejected and preserved in the audit trail"
    return _truthful_decision_update(
        {},
        assistant_message=(
            f"I {verb} {changed} candidate{'s' if changed != 1 else ''}. "
            "This does not make the project survey-true or ready for final reliance."
        ),
        intent="conversation",
        run_mode="none",
        design_prompt="",
        needs_clarification=False,
        action_taken=f"{action}ed_candidate_review_items",
        action_blocked_reason="",
        affected_systems=["site", "layout"],
        assumptions=[],
        next_best_action="Review remaining pending candidates before relying on source evidence.",
        command_payload_updates={"candidate_review_inbox_v1": decision["candidate_review_inbox_v1"], "ui_navigation_target": "data", "requested_ui_mode": "data"},
        outcome="understood_and_executed",
        state_changed=True,
    )


def _source_confidence_chat_response(
    *,
    message: str,
    record: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    normalized = _normalized_text(message)
    asks_trust = "what can i trust" in normalized or ("trust" in normalized and "source" in normalized)
    asks_low = "why is this low confidence" in normalized or "low confidence" in normalized
    asks_drawn = "what is user drawn" in normalized or "user drawn" in normalized or "user-drawn" in normalized
    asks_control = "what needs survey control" in normalized or "needs survey control" in normalized or "need survey control" in normalized
    asks_stale_missing = (
        "show me stale or missing sources" in normalized
        or "stale sources" in normalized
        or "missing sources" in normalized
        or ("stale" in normalized and "source" in normalized)
    )
    if not any((asks_trust, asks_low, asks_drawn, asks_control, asks_stale_missing)):
        return None
    if not record:
        return _truthful_decision_update(
            {},
            assistant_message="I need a saved project before I can summarize source confidence.",
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=True,
            action_taken="blocked_missing_source_confidence_project",
            action_blocked_reason="No saved project record is available for source confidence.",
            required_missing_inputs=["saved canonical project record"],
            affected_systems=["site", "data"],
            assumptions=[],
            next_best_action="Save or load a project, then ask for the source confidence map.",
            outcome="understood_but_blocked",
            state_changed=False,
            blocker="No saved project record is available for source confidence.",
        )

    latest_result = _safe_dict(record.get("latest_result"))
    meta = _safe_dict(_safe_dict(latest_result.get("final_plan")).get("meta"))
    confidence_map = build_source_confidence_map(meta, project_input=_safe_dict(record.get("project_input")))
    entries = [_safe_dict(item) for item in _safe_list(confidence_map.get("entries"))]
    summary = _safe_dict(confidence_map.get("summary"))

    def line(item: Dict[str, Any]) -> str:
        reason = safe_str(item.get("why_low_confidence")) or safe_str(item.get("next_action"))
        return (
            f"- {safe_str(item.get('label'))}: {safe_str(item.get('visible_badge'))}; "
            f"source {safe_str(item.get('source_name'))}; why {reason}"
        )

    if asks_trust:
        selected = [item for item in entries if item.get("confidence_band") == "higher"]
        heading = "What you can trust most right now"
        fallback = "Nothing is high-confidence yet. Verify survey/control and accept official/current sources before relying on location or engineering evidence."
    elif asks_drawn:
        selected = [item for item in entries if item.get("source_type") == "user-drawn"]
        heading = "User-drawn geometry"
        fallback = "No user-drawn objects are recorded in the source confidence map."
    elif asks_control:
        selected = [item for item in entries if item.get("needs_survey_control")]
        heading = "Needs survey control"
        fallback = "No entries are currently flagged for survey/control, but construction reliance still requires external professional review."
    elif asks_stale_missing:
        selected = [item for item in entries if item.get("stale") or item.get("dirty") or item.get("missing")]
        heading = "Stale or missing sources"
        fallback = "No stale/dirty/missing source entries are recorded right now."
    else:
        selected = [
            item
            for item in entries
            if item.get("confidence_band") in {"low", "missing"} or item.get("stale") or item.get("dirty")
        ]
        heading = "Low confidence sources"
        fallback = "No low-confidence source entries are recorded right now."

    body = "\n".join(line(item) for item in selected[:8]) if selected else fallback
    assistant_message = (
        f"{heading}: {summary.get('entry_count', 0)} mapped source/object/layer entries. "
        f"{summary.get('low_confidence_count', 0)} low confidence, "
        f"{summary.get('needs_survey_control_count', 0)} need survey control, "
        f"{summary.get('stale_or_missing_count', 0)} stale/missing.\n"
        f"{body}\n"
        "This is review transparency only; it does not imply field-use readiness."
    )
    return _truthful_decision_update(
        {},
        assistant_message=assistant_message,
        intent="conversation",
        run_mode="none",
        design_prompt="",
        needs_clarification=False,
        action_taken="reported_source_confidence_map",
        action_blocked_reason="",
        affected_systems=["site", "data", "review"],
        assumptions=[],
        next_best_action="Open Data to review the Source Confidence Map, then verify missing/control-dependent entries.",
        command_payload_updates={
            "source_confidence_map_v1": confidence_map,
            "ui_navigation_target": "data",
            "requested_ui_mode": "data",
        },
        outcome="understood_and_answered",
        state_changed=False,
    )


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
    online_discovery_decision = _online_discovery_chat_response(
        message=message,
        record=record,
        project_store=project_store,
        user_id=user_id,
    )
    if online_discovery_decision is not None:
        return _enrich_response_contract(online_discovery_decision, message=message)
    source_confidence_decision = _source_confidence_chat_response(message=message, record=record)
    if source_confidence_decision is not None:
        return _enrich_response_contract(source_confidence_decision, message=message)
    candidate_decision = _candidate_chat_response(
        message=message,
        record=record,
        project_store=project_store,
        user_id=user_id,
    )
    if candidate_decision is not None:
        return _enrich_response_contract(candidate_decision, message=message)
    decision = decide_chat_message(payload)
    if safe_str(decision.get("action_taken")) == "answered_from_project_context" and safe_str(context.get("next_best_action")):
        metadata = _safe_dict(decision.get("response_metadata"))
        metadata["next_best_action"] = safe_str(context.get("next_best_action"))
        decision["response_metadata"] = metadata
        decision["next_best_action"] = metadata["next_best_action"]
    decision = _apply_chat_command_execution(
        decision,
        context=context,
        record=record,
        project_store=project_store,
        user_id=user_id,
        message=message,
    )
    decision = attach_ai_orchestration_evidence_to_decision(message, decision)
    _persist_orchestration_evidence(
        decision=decision,
        project_store=project_store,
        user_id=user_id,
        project_id=project_id,
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
    return _enrich_response_contract(decision, message=message)
