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
from backend.planning.cad_entity_model import (
    CAD_ENTITY_CHAT_OPERATION_VERSION,
    CAD_ENTITY_MODEL_VERSION,
    apply_cad_entity_operation,
    attach_cad_entity_model_to_result,
    build_cad_entity_model,
    build_cad_history_snapshot,
    cad_entity_operation_result,
    cad_entities_to_site_object_candidates,
    history_event,
    locked_layer_blocker,
    manual_drawn_objects_to_cad_entities,
    normalize_cad_entity,
    plan_pdf_elements_to_cad_entities,
    refresh_dimension_associations,
)
from backend.planning.common import safe_float, safe_str
from backend.planning.design_alternatives import (
    ALTERNATIVES_VERSION,
    append_revised_design_alternative,
    build_design_alternatives,
    compare_design_alternatives,
    option_number_from_message,
    requested_alternative_count_from_message,
    select_design_alternative,
)
from backend.planning.dwg_compatibility import dwg_strategy_from_meta
from backend.planning.discipline_depth_proof import build_engine_proof_contract
from backend.planning.existing_conditions_online import fetch_online_existing_conditions
from backend.planning.gis_provider_registry import (
    build_arcgis_provider_record,
    build_provider_registry,
    check_registry_health,
    normalize_source_type,
)
from backend.planning.map_feature_detection import build_map_feature_detection_report
from backend.planning.progress_timeline import build_progress_timeline
from backend.planning.review_issue_tracker import (
    ISSUE_TRACKER_VERSION,
    apply_review_issue_update,
    build_review_issue_tracker,
    select_review_issues,
)
from backend.planning.review_issue_tracker import (
    ISSUE_TRACKER_VERSION,
    apply_review_issue_update,
    build_review_issue_tracker,
    select_review_issues,
)
from backend.planning.smart_fix import build_smart_fix_recommendations
from backend.planning.setup_wizard import build_setup_wizard_state
from backend.planning.source_confidence_map import (
    attach_source_confidence_map,
    build_source_confidence_map,
)
from backend.planning.standards_package import build_standards_package
from backend.planning.customer_templates import GLOBAL_CUSTOMER_TEMPLATE_MANAGER, template_behavior
from backend.planning.annotation_standards import annotation_chat_response_payload
from backend.planning.symbol_block_library import (
    SYMBOL_ATTRIBUTE_FIELDS,
    SUPPORTED_SYMBOL_KINDS,
    build_reference_underlay,
    build_symbol_instance,
    normalize_symbol_library,
)
from backend.planning.utility_catalogs import GLOBAL_UTILITY_CATALOG_MANAGER
from backend.planning.plan_pdf_understanding import (
    SOURCE_CONFIDENCE as PLAN_PDF_SOURCE_CONFIDENCE,
    plan_pdf_report,
    update_editable_sheet_element,
)
from backend.planning.plotting_standards import build_plotting_standards
from parsers.chat_intent_parser import build_chat_memory_summary


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return list(value) if isinstance(value, list) else []


def _customer_template_chat_response(message: str) -> Optional[Dict[str, Any]]:
    normalized = _normalized_text(message)
    mentions_template = "template" in normalized and any(
        phrase in normalized
        for phrase in (
            "company template",
            "customer template",
            "active template",
            "template is active",
            "template missing",
        )
    )
    if not mentions_template:
        return None
    registry = GLOBAL_CUSTOMER_TEMPLATE_MANAGER.snapshot()
    behavior = template_behavior(registry.get("active_template"))
    asks_missing = "missing" in normalized or "why" in normalized
    asks_active = "active" in normalized or "what template" in normalized
    action = (
        "answered_customer_template_missing_reason"
        if asks_missing
        else "answered_active_template"
        if asks_active
        else "activated_customer_template"
    )
    summary = " ".join(safe_str(item) for item in _safe_list(behavior.get("template_behavior")) if safe_str(item))
    if not summary:
        summary = "Company template behavior is unavailable; Civora will keep outputs review-required and will not claim legal compliance."
    decision = _truthful_decision_update(
        {},
        assistant_message=summary,
        intent="conversation",
        run_mode="none",
        design_prompt="",
        needs_clarification=False,
        action_taken=action,
        next_best_action="Review customer template settings before relying on generated layers, labels, reports, or defaults.",
        outcome="answered_customer_template_status",
        state_changed=False,
        blocker="",
    )
    metadata = _safe_dict(decision.get("response_metadata"))
    metadata["ui_navigation_target"] = "templates"
    metadata["template_policy"] = safe_str(_safe_dict(behavior.get("policy")).get("truth_label"))
    decision["response_metadata"] = metadata
    return decision


def _annotation_standards_chat_response(message: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    payload = annotation_chat_response_payload(message, _meta_from_chat_context(context))
    if payload is None:
        return None
    trace = _safe_dict(payload.get("trace"))
    return _truthful_decision_update(
        {},
        assistant_message=safe_str(payload.get("assistant_message")),
        intent="annotation_standards",
        run_mode="none",
        design_prompt="",
        needs_clarification=False,
        action_taken=f"answered_annotation_{safe_str(payload.get('action'), 'request')}",
        affected_systems=["annotation", "sheets", "dxf_export"],
        assumptions=[],
        next_best_action="Apply the annotation change in the sheet/editor workflow, then review the export trace before relying on it.",
        command_payload_updates={
            "annotation_standard_request_v1": {
                "action": safe_str(payload.get("action")),
                "trace": trace,
                "review_required": True,
                "construction_release_allowed": False,
            },
            "ui_navigation_target": "sheets",
            "requested_ui_mode": "sheet_review",
        },
        outcome="understood_and_answered",
        state_changed=False,
    )


def _standards_rules_chat_response(
    *,
    message: str,
    context: Dict[str, Any],
    record: Optional[Dict[str, Any]],
    project_store: Any,
    user_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    lowered = _normalized_text(message)
    mentions_standards = "standard" in lowered or "rule" in lowered or "compliance" in lowered or "company standard" in lowered
    if not mentions_standards:
        return None
    asks_missing = "missing" in lowered or "what standards" in lowered or "what standard" in lowered
    asks_company = "use my company standard" in lowered or "use company standard" in lowered or "company standard" in lowered
    asks_accepted = "accepted" in lowered or "is this rule accepted" in lowered or "is the rule accepted" in lowered
    asks_blocked = "why" in lowered and ("blocked" in lowered or "compliance" in lowered)
    if not (asks_missing or asks_company or asks_accepted or asks_blocked):
        return None

    meta = _meta_from_chat_context(context)
    changed = False
    if asks_company:
        supplied_company = _safe_dict(context.get("company_standards") or context.get("company_standard"))
        if supplied_company and record:
            latest_result = deepcopy(_safe_dict(record.get("latest_result")))
            final_plan = _safe_dict(latest_result.get("final_plan"))
            plan_meta = _safe_dict(final_plan.get("meta"))
            plan_meta["company_standards"] = supplied_company
            plan_meta["standards_package"] = build_standards_package(plan_meta)
            final_plan["meta"] = plan_meta
            latest_result["final_plan"] = final_plan
            if project_store and user_id:
                _save_project_record(project_store, record, project_input=deepcopy(_safe_dict(record.get("project_input"))), latest_result=latest_result)
            meta = plan_meta
            changed = True

    package = _safe_dict(meta.get("standards_package")) or build_standards_package(meta)
    matrix = _safe_dict(package.get("standards_rule_check_matrix"))
    checks = [_safe_dict(item) for item in _safe_list(matrix.get("checks"))]
    blockers = [_safe_dict(item) for item in _safe_list(package.get("blockers")) + _safe_list(matrix.get("blockers"))]
    accepted_rules = [_safe_dict(item) for item in _safe_list(package.get("accepted_rules"))]
    accepted_ids = [safe_str(rule.get("rule_id")) for rule in accepted_rules if safe_str(rule.get("rule_id"))]

    lines: List[str] = []
    action_taken = "answered_standards_status"
    if asks_company:
        action_taken = "recorded_company_standards_for_review" if changed else "blocked_company_standards_missing_trace"
        if changed:
            lines.append("Company standards were attached to the project standards package for review only.")
        else:
            lines.append("I can use a company standard only after it includes source/approval trace such as source, approved_by, approval_date, and review status.")
    if asks_accepted:
        action_taken = "answered_rule_acceptance_status"
        lines.append("Accepted rules: " + (", ".join(accepted_ids) if accepted_ids else "none."))
        lines.extend(
            [
                f"{safe_str(rule.get('rule_id'))}: accepted_by={safe_str(rule.get('accepted_by')) or 'missing'}, accepted_date={safe_str(rule.get('accepted_date')) or 'missing'}, source={safe_str(rule.get('source_url')) or 'missing'}"
                for rule in accepted_rules[:6]
            ]
        )
    if asks_missing:
        action_taken = "answered_missing_standards"
        missing_checks = [item for item in checks if item.get("blocked")]
        lines.append("Missing or blocked standards:")
        if missing_checks:
            lines.extend(
                f"- {safe_str(item.get('label'))}: {', '.join(_safe_list(item.get('blocker_fields'))) or 'no accepted current source-traceable rule'}"
                for item in missing_checks[:10]
            )
        else:
            lines.append("- No missing review-check standards are visible in the current package.")
    if asks_blocked:
        action_taken = "answered_standards_compliance_blockers"
        lines.append("Compliance is blocked because Civora has review evidence only, not jurisdiction approval or engineer-of-record certification.")
        lines.extend(
            f"- {safe_str(item.get('field'))}: {safe_str(item.get('reason')) or safe_str(item.get('message'))}"
            for item in blockers[:10]
        )
    lines.append("Civora does not stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record.")

    blocker_text = "; ".join(safe_str(item.get("field")) for item in blockers if safe_str(item.get("field")))
    return _truthful_decision_update(
        {},
        assistant_message="\n".join(lines),
        intent="standards_rules",
        run_mode="none",
        design_prompt="",
        needs_clarification=False,
        action_taken=action_taken,
        affected_systems=["standards", "review"],
        assumptions=[],
        next_best_action="Accept official-source standards through the company/engineer workflow, refresh stale sources, and keep all outputs review-required.",
        command_payload_updates={
            "standards_package": package,
            "standards_rule_check_matrix": matrix,
            "requested_ui_mode": "data",
        },
        outcome="understood_and_executed" if not action_taken.startswith("blocked") else "understood_but_blocked",
        state_changed=changed,
        blocker=blocker_text,
    )


def _symbol_kind_from_message(message: str) -> str:
    lowered = _normalized_text(message)
    aliases = {
        "note_callout": ("note/callout", "note callout", "callout", "note"),
        "utility_marker": ("utility marker", "utility"),
    }
    for kind, tokens in aliases.items():
        if any(token in lowered for token in tokens):
            return kind
    for kind in SUPPORTED_SYMBOL_KINDS:
        if kind.replace("_", " ") in lowered or kind in lowered:
            return kind
    return ""


def _symbol_block_chat_response(message: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    normalized = _normalized_text(message)
    mentions_symbol = any(token in normalized for token in ("symbol", "block", "xref", "underlay", "reference"))
    asks_template_symbols = "symbols" in normalized and "template" in normalized
    wants_insert = any(token in normalized for token in ("insert", "place", "add")) and ("symbol" in normalized or _symbol_kind_from_message(message))
    wants_attribute_edit = "attribute" in normalized and any(token in normalized for token in ("edit", "change", "update", "set", "this block", "this symbol"))
    wants_underlay = "underlay" in normalized or ("attach" in normalized and any(token in normalized for token in ("pdf", "dxf", "image", "reference", "xref")))
    if not any((asks_template_symbols, wants_insert, wants_attribute_edit, wants_underlay)) or not mentions_symbol and not wants_underlay and not wants_insert:
        return None

    meta = _meta_from_chat_context(context)
    template = _safe_dict(meta.get("active_customer_template")) or _safe_dict(GLOBAL_CUSTOMER_TEMPLATE_MANAGER.snapshot().get("active_template"))
    library = normalize_symbol_library(template)

    if asks_template_symbols:
        names = [
            f"{safe_str(item.get('kind'))}: {safe_str(item.get('name'))}"
            for item in _safe_list(library.get("blocks"))
            if safe_str(item.get("kind"))
        ]
        assistant_message = (
            "Template symbol library includes: "
            + "; ".join(names[:12])
            + ". These are drafting/review aids with editable ID, label, elevation, material, size, source, and review-note attributes."
        )
        return _truthful_decision_update(
            {},
            assistant_message=assistant_message,
            intent="symbol_library",
            run_mode="none",
            design_prompt="",
            needs_clarification=False,
            action_taken="answered_template_symbol_library",
            affected_systems=["cad_symbols", "customer_templates"],
            assumptions=["Customer template symbol libraries do not prove survey, engineering, or construction status."],
            next_best_action="Open the symbol/block library manager or select a symbol in object properties to edit review attributes.",
            command_payload_updates={
                "symbol_block_library_v1": library,
                "ui_navigation_target": "canvas",
                "requested_ui_mode": "symbol_library",
            },
            outcome="understood_and_answered",
            state_changed=False,
            confidence=0.93,
        )

    if wants_underlay:
        file_type = "pdf" if "pdf" in normalized else "dxf" if "dxf" in normalized else "image" if "image" in normalized else "external"
        reference = build_reference_underlay({"file_type": file_type, "source_confidence": "source_underlay_review_required"})
        assistant_message = (
            f"I can attach the {file_type.upper()} as a source-only underlay/reference. It stays not-editable where applicable, carries source confidence, "
            "and does not become survey-backed or construction-release evidence by being attached."
        )
        return _truthful_decision_update(
            {},
            assistant_message=assistant_message,
            intent="symbol_reference",
            run_mode="none",
            design_prompt="",
            needs_clarification=False,
            action_taken="prepared_reference_underlay_attachment",
            affected_systems=["cad_references", "export_trace"],
            assumptions=["The file source/path must be supplied by the upload or CAD reference UI."],
            next_best_action="Attach the source file in the underlay/reference panel, then review alignment and source confidence.",
            command_payload_updates={
                "reference_underlay_v1": reference,
                "ui_navigation_target": "canvas",
                "requested_ui_mode": "reference_underlay",
            },
            outcome="understood_and_answered",
            state_changed=False,
            confidence=0.91,
        )

    if wants_attribute_edit:
        selected_object_ids, selected_geometry_ids = _collect_selected_ids(context)
        assistant_message = (
            "Block/symbol attributes can be edited in object properties: ID, label, elevation, material, size, source, and review note. "
            "The edit remains draft_review_required and does not validate the symbol as survey-backed or engineer-reviewed."
        )
        return _truthful_decision_update(
            {},
            assistant_message=assistant_message,
            intent="symbol_attributes",
            run_mode="none",
            design_prompt="",
            needs_clarification=not bool(selected_object_ids or selected_geometry_ids),
            action_taken="answered_block_attribute_edit_path",
            affected_systems=["cad_symbols", "object_properties"],
            assumptions=["Attribute edits update review metadata only."],
            next_best_action="Select the symbol/block and edit its attributes in object properties.",
            command_payload_updates={
                "symbol_attribute_edit_v1": {
                    "editable_fields": list(SYMBOL_ATTRIBUTE_FIELDS),
                    "review_required": True,
                    "construction_release_allowed": False,
                },
                "ui_navigation_target": "canvas",
                "requested_ui_mode": "object_properties",
            },
            outcome="understood_and_answered",
            state_changed=False,
            referenced_object_ids=selected_object_ids,
            referenced_geometry_ids=selected_geometry_ids,
            confidence=0.9,
        )

    symbol_kind = _symbol_kind_from_message(message)
    if wants_insert and symbol_kind:
        symbol = build_symbol_instance(symbol_kind)
        assistant_message = (
            f"Prepared a {symbol['label']} symbol insert as a draft/review-required block-like object. "
            "Its editable attributes are ID, label, elevation, material, size, source, and review note; native DWG block parity is not claimed."
        )
        return _truthful_decision_update(
            {},
            assistant_message=assistant_message,
            intent="symbol_insert",
            run_mode="none",
            design_prompt="",
            needs_clarification=False,
            action_taken="prepared_symbol_insert",
            affected_systems=["cad_symbols", "object_properties", "export_trace"],
            assumptions=["Insertion creates a drafting/review aid until source evidence and reviewer checks are accepted outside the insert action."],
            next_best_action="Place the symbol on the canvas, then edit its attributes in object properties.",
            command_payload_updates={
                "symbol_insert_v1": symbol,
                "symbol_block_library_v1": library,
                "ui_navigation_target": "canvas",
                "requested_ui_mode": "symbol_insert",
            },
            outcome="understood_and_answered",
            state_changed=False,
            confidence=0.93,
        )
    return None


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
    payload_source_confidence = safe_str(_safe_dict(metadata.get("command_payload")).get("source_confidence"))
    if payload_source_confidence:
        updated["source_confidence"] = payload_source_confidence
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
        meta[ISSUE_TRACKER_VERSION] = build_review_issue_tracker(final_plan, meta=meta)
        meta[ISSUE_TRACKER_VERSION] = build_review_issue_tracker(final_plan, meta=meta)
        final_plan["meta"] = meta
        latest_result["final_plan"] = final_plan
    latest_result = attach_cad_entity_model_to_result(latest_result, project_input=project_input)
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


def _meta_from_chat_context(context: Dict[str, Any]) -> Dict[str, Any]:
    current_project = _safe_dict(context.get("current_project"))
    latest_result = _safe_dict(current_project.get("latest_result"))
    final_plan = _safe_dict(latest_result.get("final_plan"))
    return _safe_dict(final_plan.get("meta") or latest_result.get("metadata") or latest_result.get("meta"))


def _numeric_values_for_cad_command(message: str) -> List[float]:
    scrubbed = re.sub(r"\bcad[-_a-z0-9]*\b", " ", message.lower())
    return [float(item) for item in re.findall(r"(?<![a-z])-?\d+(?:\.\d+)?", scrubbed)]


def _point_pairs(values: List[float]) -> List[Dict[str, float]]:
    return [{"x": values[index], "y": values[index + 1]} for index in range(0, len(values) - 1, 2)]


def _collect_selected_cad_entity_ids(context: Dict[str, Any], model: Dict[str, Any], message: str) -> List[str]:
    entity_ids = {safe_str(item.get("id")) for item in _safe_list(model.get("entities")) if isinstance(item, dict)}
    selected: List[str] = []

    def _extend(value: Any) -> None:
        values = value if isinstance(value, list) else [value]
        for item in values:
            entity_id = safe_str(item)
            if entity_id and entity_id in entity_ids and entity_id not in selected:
                selected.append(entity_id)

    for key in (
        "selected_cad_entity_ids",
        "selected_entity_ids",
        "target_entity_ids",
        "selected_object_ids",
        "selected_object_id",
        "activePlacementId",
        "active_placement_id",
    ):
        _extend(context.get(key))
    for entity_id in _safe_list(model.get("selected_entity_ids")):
        _extend(entity_id)
    for entity_id in re.findall(r"\bcad[-_a-z0-9]+\b", message.lower()):
        _extend(entity_id)
    return selected


def _cad_lookup_key(value: Any) -> str:
    raw = safe_str(value).lower()
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in raw).strip("_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned


def _cad_layer_id_from_phrase(model: Dict[str, Any], phrase: str) -> str:
    target = _cad_lookup_key(phrase)
    aliases = {
        "utilities": "utilities",
        "utility": "utility",
        "drainage": "drainage",
        "drain": "drainage",
        "existing": "existing",
    }
    target = aliases.get(target, target)
    variants = {target}
    if target.endswith("ies"):
        variants.add(target[:-3] + "y")
    if target.endswith("y"):
        variants.add(target[:-1] + "ies")
    if target and not target.endswith("s"):
        variants.add(f"{target}s")
    for layer in _safe_list(model.get("layers")):
        rec = _safe_dict(layer)
        keys = {_cad_lookup_key(rec.get("id")), _cad_lookup_key(rec.get("layer_id")), _cad_lookup_key(rec.get("name"))}
        if variants & keys or any(any(key.endswith(f"_{variant}") or variant in key.split("_") for variant in variants) for key in keys if key):
            return safe_str(rec.get("id") or rec.get("layer_id"))
    return f"layer_{target}" if target else ""


def _cad_style_id_from_phrase(model: Dict[str, Any], phrase: str) -> str:
    target = _cad_lookup_key(phrase)
    for style in _safe_list(model.get("styles")):
        rec = _safe_dict(style)
        keys = {_cad_lookup_key(rec.get("id")), _cad_lookup_key(rec.get("style_id")), _cad_lookup_key(rec.get("name"))}
        if target in keys or any(key.endswith(f"_{target}") or target in key.split("_") for key in keys if key):
            return safe_str(rec.get("id") or rec.get("style_id"))
    return f"style_{target}" if target else ""


def _cad_layer_phrase(message: str) -> str:
    patterns = (
        r"\b(?:hide|show|lock|unlock|print|plot|make printable|make non-printable)\s+(.+?)\s+layer\b",
        r"\b(?:move|change|set)\s+selected(?:\s+cad\s+entit(?:y|ies)|\s+cad\s+object)?\s+(?:to|onto)\s+(.+?)\s+layer\b",
        r"\b(?:layer|to layer)\s+([a-zA-Z0-9_.-]+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            return safe_str(match.group(1))
    return ""


def _cad_entity_chat_command_operation(message: str, context: Dict[str, Any], model: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lowered = _normalized_text(message)
    if "command line" in lowered or "cad command" in lowered:
        return None
    if lowered in {"add dimension", "add dimensions"}:
        return None
    if "dimension" in lowered and "stale" in lowered and any(token in lowered for token in ("why", "what", "show", "which", "update", "refresh", "recalculate", "recalc")):
        return None
    if any(token in lowered for token in ("viewport", "sheet", "plot", "revision note", "road", "building", "basin")) and "cad entity" not in lowered and "cad object" not in lowered and "layer" not in lowered:
        return None
    command_tokens = (
        "create",
        "draw",
        "add",
        "move",
        "copy",
        "delete",
        "rotate",
        "scale",
        "grip",
        "set layer",
        "change layer",
        "change style",
        "set style",
        "show layers",
        "hide",
        "lock",
        "unlock",
        "printable",
        "company layer style",
        "line",
        "polyline",
        "rectangle",
        "dimension",
        "text",
        "callout",
        "leader",
        "note",
        "label",
        "cad entity",
        "cad object",
    )
    if not any(token in lowered for token in command_tokens):
        return None
    if "drawn object" in lowered and "convert" in lowered:
        return None

    release_terms = (
        "stamp",
        "seal",
        "sign off",
        "certify",
        "approve construction",
        "submit construction",
        "engineer of record",
        "construction ready",
        "construction-ready",
    )
    if any(term in lowered for term in release_terms):
        return {
            "action": "blocked_construction_release_request",
            "understood_goal": message,
            "safety_blockers": ["chat_cad_commands_cannot_stamp_seal_certify_approve_submit_or_act_as_engineer_of_record"],
            "next_best_action": "Use chat CAD commands only for drafting/review edits, then route review evidence through safe backend workflows.",
        }

    selected_ids = _collect_selected_cad_entity_ids(context, model, message)
    explicit_persistent_cad = "cad entity" in lowered or "cad object" in lowered or bool(selected_ids)
    values = _numeric_values_for_cad_command(message)
    points = _point_pairs(values)
    base = {
        "understood_goal": message,
        "target_entity_ids": selected_ids,
        "next_best_action": "Review the changed CAD entities and their source confidence before downstream use.",
    }

    if "show layers" in lowered or ("list" in lowered and "layers" in lowered):
        return None
    if "layer" in lowered and any(token in lowered for token in ("hide", "show", "lock", "unlock", "printable", "non-printable", "non printable")):
        phrase = _cad_layer_phrase(message)
        layer_id = _cad_layer_id_from_phrase(model, phrase)
        if not layer_id:
            return {**base, "action": "set_layer_visibility", "missing_inputs": ["target layer"], "next_best_action": "Name the target layer, for example: hide utilities layer."}
        if "hide" in lowered:
            return {**base, "action": "set_layer_visibility", "layer_id": layer_id, "visible": False}
        if re.search(r"\bshow\b", lowered):
            return {**base, "action": "set_layer_visibility", "layer_id": layer_id, "visible": True}
        if "unlock" in lowered:
            return {**base, "action": "set_layer_locked", "layer_id": layer_id, "locked": False}
        if "lock" in lowered:
            return {**base, "action": "set_layer_locked", "layer_id": layer_id, "locked": True}
        return {**base, "action": "set_layer_printable", "layer_id": layer_id, "printable": "non-printable" not in lowered and "non printable" not in lowered}
    if "company layer style" in lowered or "company layer standards" in lowered:
        return {**base, "action": "use_company_layer_style"}

    wants_create = any(token in lowered for token in ("create", "draw", "add"))
    targeted_dimension = "dimension" in lowered and (bool(selected_ids) or "this line" in lowered or "this circle" in lowered or "this arc" in lowered)
    if re.search(r"\b(line|segment)\b", lowered) and wants_create:
        if len(points) < 2:
            return {**base, "action": "create_line", "entity_type": "line", "missing_inputs": ["line start point", "line end point"], "next_best_action": "Provide start and end coordinates, for example: create line from 0,0 to 25,0."}
        return {**base, "action": "create_line", "entity_type": "line", "geometry": {"start": points[0], "end": points[1], "units": "ft"}}
    if ("polyline" in lowered or "pline" in lowered) and wants_create:
        if len(points) < 2:
            return {**base, "action": "create_polyline", "entity_type": "polyline", "missing_inputs": ["at least two polyline points"], "next_best_action": "Provide at least two coordinate pairs for the polyline."}
        return {**base, "action": "create_polyline", "entity_type": "polyline", "geometry": {"points": points, "closed": "closed" in lowered, "units": "ft"}}
    if ("rectangle" in lowered or "rect" in lowered) and wants_create:
        if len(points) < 1 or len(values) < 4:
            return {**base, "action": "create_rectangle", "entity_type": "rectangle", "missing_inputs": ["rectangle origin", "rectangle width", "rectangle height"], "next_best_action": "Provide origin, width, and height, for example: create rectangle at 0,0 width 40 height 20."}
        return {**base, "action": "create_rectangle", "entity_type": "rectangle", "geometry": {"origin": points[0], "width": abs(values[-2]), "height": abs(values[-1]), "units": "ft"}}
    if "dimension" in lowered and (wants_create or targeted_dimension):
        if len(points) < 2 and not selected_ids:
            if lowered in {"add dimension", "add dimensions"}:
                return None
            return {**base, "action": "create_dimension", "entity_type": "dimension", "missing_inputs": ["dimension start point", "dimension end point"], "next_best_action": "Provide two measurement points for the dimension."}
        dimension_type = "angular" if "angular" in lowered else "diameter" if "diameter" in lowered else "radius" if "radius" in lowered else "linear" if "linear" in lowered else "aligned"
        geometry = {"units": "ft"}
        if len(points) >= 2:
            geometry.update({"start": points[0], "end": points[1], "points": points[:3] if dimension_type == "angular" else points[:2]})
        return {**base, "action": "create_dimension", "entity_type": "dimension", "dimension_type": dimension_type, "geometry": geometry, "units": "deg" if dimension_type == "angular" else "ft", "precision": 1 if dimension_type == "angular" else 2}
    if any(token in lowered for token in ("callout", "leader", "note", "label")) and wants_create:
        text_match = re.search(r"['\"]([^'\"]+)['\"]", message)
        text = text_match.group(1).strip() if text_match else ("Callout" if "callout" in lowered else "Note" if "note" in lowered else "Label")
        annotation_type = "callout" if "callout" in lowered else "leader" if "leader" in lowered else "note" if "note" in lowered else "label"
        if annotation_type in {"callout", "leader"} and len(points) < 2:
            return {**base, "action": f"create_{annotation_type}", "entity_type": annotation_type, "missing_inputs": ["leader start point", "leader text point"], "next_best_action": "Provide leader/callout points, for example: add callout \"review inlet\" from 0,0 to 5,5."}
        if annotation_type in {"note", "label"} and not points:
            return {**base, "action": f"create_{annotation_type}", "entity_type": annotation_type, "missing_inputs": ["annotation insertion point"], "next_best_action": "Provide an insertion point for the annotation."}
        return {**base, "action": f"create_{annotation_type}", "entity_type": annotation_type, "text": text, "geometry": {"insert": points[-1] if points else {"x": 0, "y": 0}, "points": points, "text": text, "units": "ft"}}
    if re.search(r"\btext\b", lowered) and wants_create:
        text_match = re.search(r"['\"]([^'\"]+)['\"]", message)
        label = text_match.group(1).strip() if text_match else ""
        if not label or not points:
            missing = []
            if not label:
                missing.append("text label")
            if not points:
                missing.append("text insertion point")
            return {**base, "action": "create_text", "entity_type": "text", "missing_inputs": missing, "next_best_action": "Provide quoted text and an insertion point, for example: add text \"FFE 100.0\" at 5,5."}
        return {**base, "action": "create_text", "entity_type": "text", "geometry": {"insert": points[0], "text": label, "height": 1.0, "units": "ft"}}

    selected_action = ""
    if "layer" in lowered and any(token in lowered for token in ("set", "change", "move")) and re.search(r"\b(?:to|onto)\s+.+?\s+layer\b", message, flags=re.IGNORECASE):
        selected_action = "change_layer"
    elif "move" in lowered:
        selected_action = "move_grip" if "grip" in lowered else "move_selected"
    elif "copy" in lowered:
        selected_action = "copy_selected"
    elif "delete" in lowered or "erase" in lowered or "remove selected cad" in lowered:
        selected_action = "delete_selected"
    elif "rotate" in lowered:
        selected_action = "rotate_selected"
    elif "scale" in lowered:
        selected_action = "scale_selected"
    elif "layer" in lowered and any(token in lowered for token in ("set", "change", "move")):
        selected_action = "change_layer"
    elif "style" in lowered and any(token in lowered for token in ("set", "change")):
        selected_action = "change_style"
    elif explicit_persistent_cad and any(token in lowered for token in ("trim", "extend", "fillet", "offset")):
        unsupported = lowered.split()[0]
        return {
            **base,
            "action": "unsupported",
            "safety_blockers": [f"unsupported_persistent_cad_entity_command:{unsupported}"],
            "next_best_action": "Use supported persistent CAD entity commands: create line/polyline/rectangle/text/dimension; move/copy/rotate/scale selected entity; change layer/style; convert drawn object; explain invalid/stale entities.",
        }
    if not selected_action:
        return None
    if not explicit_persistent_cad:
        return None
    if not selected_ids:
        return {**base, "action": selected_action, "missing_inputs": ["selected CAD entity"], "next_best_action": "Select one or more persistent CAD entities, then retry the command."}
    if selected_action == "move_grip":
        grip_id = safe_str(context.get("selected_cad_grip_id") or context.get("selected_grip_id") or context.get("grip_id") or context.get("active_cad_grip_id"))
        entity_id = safe_str(context.get("selected_cad_grip_entity_id") or context.get("selected_grip_entity_id") or context.get("grip_entity_id") or selected_ids[0])
        if not grip_id:
            return {**base, "action": selected_action, "entity_id": entity_id, "missing_inputs": ["selected CAD grip"], "next_best_action": "Select a visible CAD grip point, then retry the grip move."}
        if len(values) < 2:
            return {**base, "action": selected_action, "entity_id": entity_id, "grip_id": grip_id, "missing_inputs": ["x offset", "y offset"], "next_best_action": "Provide a grip displacement, for example: move this grip by 5,0."}
        return {**base, "action": selected_action, "entity_id": entity_id, "target_entity_ids": [entity_id], "grip_id": grip_id, "dx": values[0], "dy": values[1]}
    if selected_action == "delete_selected":
        return {**base, "action": selected_action}
    if selected_action in {"move_selected", "copy_selected"}:
        if len(values) < 2:
            return {**base, "action": selected_action, "missing_inputs": ["x offset", "y offset"], "next_best_action": "Provide an X/Y offset, for example: move selected CAD entity by 10,0."}
        return {**base, "action": selected_action, "dx": values[0], "dy": values[1]}
    if selected_action == "rotate_selected":
        if not values:
            return {**base, "action": selected_action, "missing_inputs": ["rotation angle"], "next_best_action": "Provide a rotation angle in degrees."}
        return {**base, "action": selected_action, "angle_degrees": values[0]}
    if selected_action == "scale_selected":
        if not values or values[0] <= 0:
            return {**base, "action": selected_action, "missing_inputs": ["positive scale factor"], "next_best_action": "Provide a positive scale factor, for example: scale selected CAD entity by 2."}
        return {**base, "action": selected_action, "scale_factor": values[0]}
    if selected_action == "change_layer":
        phrase = _cad_layer_phrase(message)
        layer_id = _cad_layer_id_from_phrase(model, phrase)
        if not layer_id:
            return {**base, "action": selected_action, "missing_inputs": ["target layer"], "next_best_action": "Name the target layer, for example: change selected CAD entity to layer utility."}
        return {**base, "action": selected_action, "layer_id": layer_id}
    if selected_action == "change_style":
        match = re.search(r"(?:style|to style)\s+([a-zA-Z0-9_.-]+)", message)
        style_id = _cad_style_id_from_phrase(model, safe_str(match.group(1) if match else ""))
        if not style_id:
            return {**base, "action": selected_action, "missing_inputs": ["target style"], "next_best_action": "Name the target style, for example: set selected CAD entity style dashed."}
        return {**base, "action": selected_action, "style_id": style_id}
    return None


def _cad_entity_chat_response(
    *,
    message: str,
    context: Dict[str, Any],
    record: Optional[Dict[str, Any]],
    project_store: Optional[Any],
    user_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    lowered = _normalized_text(message)
    if ("pdf" in lowered and "cad" in lowered) or ("raster line" in lowered and "cad" in lowered) or "dxf" in lowered or "dwg" in lowered or "autocad" in lowered:
        return None
    mentions_cad_entity = "cad entit" in lowered or "cad object" in lowered or "drawn object" in lowered
    mentions_cad = bool(re.search(r"\bcad\b", lowered)) or mentions_cad_entity
    asks_list = any(phrase in lowered for phrase in ("what cad entities", "list cad entities", "cad entities are in", "what cad objects"))
    asks_review_only = "why" in lowered and ("review-only" in lowered or "review only" in lowered or "cad object" in lowered or "cad entity" in lowered)
    asks_stale_invalid = ("stale" in lowered or "invalid" in lowered) and ("cad" in lowered or "entity" in lowered or "object" in lowered)
    asks_dimension_stale = "dimension" in lowered and "stale" in lowered and any(token in lowered for token in ("why", "what", "show", "which"))
    asks_update_stale_dimensions = "dimension" in lowered and "stale" in lowered and any(token in lowered for token in ("update", "refresh", "recalculate", "recalc"))
    asks_history = mentions_cad and any(phrase in lowered for phrase in ("show cad history", "cad history", "revision timeline", "cad timeline"))
    asks_changed = mentions_cad and any(phrase in lowered for phrase in ("what changed in cad", "what changed on cad", "cad changes", "changed in cad"))
    asks_object_changed = any(phrase in lowered for phrase in ("what changed on this object", "what changed on this cad object", "show this object history", "object history"))
    asks_undo = mentions_cad and "undo" in lowered and ("edit" in lowered or "change" in lowered or "cad" in lowered)
    asks_restore = mentions_cad and "restore" in lowered and ("object" in lowered or "entity" in lowered or "cad" in lowered)
    asks_convert_drawn = "convert" in lowered and "drawn object" in lowered and "cad entit" in lowered
    asks_candidate = "convert" in lowered and "site object" in lowered and ("cad" in lowered or "entity" in lowered)
    asks_selection = any(phrase in lowered for phrase in ("what is selected", "what's selected", "current selection", "selected cad entities", "selected cad objects"))
    asks_grip_blocker = "why" in lowered and "grip" in lowered and any(phrase in lowered for phrase in ("can't", "cannot", "cant", "won't", "blocked", "edit"))
    asks_layers = "show layers" in lowered or ("list" in lowered and "layers" in lowered)
    asks_layer_edit_blocker = "why" in lowered and "layer" in lowered and any(phrase in lowered for phrase in ("can't", "cannot", "cant", "won't", "blocked", "edit"))

    if record:
        project_input = deepcopy(_safe_dict(record.get("project_input")))
        latest_result = deepcopy(_safe_dict(record.get("latest_result")))
    else:
        project_input = _safe_dict(context.get("project_input"))
        latest_result = _safe_dict(_safe_dict(context.get("current_project")).get("latest_result"))
    final_plan = _safe_dict(latest_result.get("final_plan"))
    meta = _safe_dict(final_plan.get("meta") or latest_result.get("metadata") or latest_result.get("meta"))
    if not _safe_dict(meta.get("active_customer_template")):
        meta["active_customer_template"] = _safe_dict(GLOBAL_CUSTOMER_TEMPLATE_MANAGER.snapshot().get("active_template"))
    model = build_cad_entity_model(meta, project_input=project_input)
    entities = [_safe_dict(item) for item in _safe_list(model.get("entities"))]
    chat_operation = _cad_entity_chat_command_operation(message, context, model)
    if not (
        mentions_cad_entity
        or asks_list
        or asks_review_only
        or asks_stale_invalid
        or asks_dimension_stale
        or asks_update_stale_dimensions
        or asks_history
        or asks_changed
        or asks_object_changed
        or asks_undo
        or asks_restore
        or asks_convert_drawn
        or asks_candidate
        or asks_selection
        or asks_grip_blocker
        or asks_layers
        or asks_layer_edit_blocker
        or chat_operation
    ):
        return None

    if chat_operation:
        if not (record and project_store and user_id):
            operation_result = cad_entity_operation_result(
                understood_goal=message,
                selected_action=safe_str(chat_operation.get("action"), "cad_entity_command"),
                target_entities=_safe_list(chat_operation.get("target_entity_ids")),
                missing_inputs=["saved project"],
                next_best_action="Save or load the project, then retry the CAD entity command.",
            )
            return _truthful_decision_update(
                {},
                assistant_message="I can run CAD entity drafting commands only after a saved project is loaded, so the persistent CAD entity model can be updated without touching loose UI-only state.",
                intent="cad_entity_command",
                run_mode="none",
                needs_clarification=True,
                action_taken="blocked_cad_entity_command_missing_project",
                action_blocked_reason="No saved canonical project record is available.",
                required_missing_inputs=["saved project"],
                affected_systems=["cad_entity_model"],
                next_best_action=operation_result["next_best_action"],
                command_payload_updates={CAD_ENTITY_CHAT_OPERATION_VERSION: operation_result, CAD_ENTITY_MODEL_VERSION: model},
                outcome="understood_but_blocked",
                state_changed=False,
                blocker="No saved canonical project record is available.",
            )
        next_source_model, operation_result = apply_cad_entity_operation(model, chat_operation, actor=user_id or "user")
        missing_inputs = _safe_list(operation_result.get("missing_inputs"))
        safety_blockers = _safe_list(operation_result.get("safety_blockers"))
        selection_action = safe_str(operation_result.get("selected_action")) in {"select_single", "select_add", "select_multi", "select_window", "clear_selection"}
        changed = bool(
            operation_result.get("created_entity_ids")
            or operation_result.get("updated_entity_ids")
            or operation_result.get("deleted_entity_ids")
            or operation_result.get("updated_layer_ids")
            or operation_result.get("updated_style_ids")
            or (selection_action and not missing_inputs and not safety_blockers)
        )
        if changed:
            meta[CAD_ENTITY_MODEL_VERSION] = build_cad_entity_model({**meta, CAD_ENTITY_MODEL_VERSION: next_source_model}, project_input=project_input)
            final_plan["meta"] = meta
            latest_result["final_plan"] = final_plan
            _save_project_record(project_store, {**record, "_user_id": user_id}, project_input=project_input, latest_result=latest_result)
            model = meta[CAD_ENTITY_MODEL_VERSION]
        if safety_blockers:
            assistant_message = (
                "I did not run that CAD entity command. "
                + "; ".join(safe_str(item) for item in safety_blockers)
                + ". Chat CAD commands are drafting/review actions only."
            )
            action_taken = "blocked_cad_entity_command"
            outcome = "understood_but_blocked"
            needs_clarification = False
        elif missing_inputs:
            assistant_message = "Which CAD command input should I use? Please provide: " + ", ".join(safe_str(item) for item in missing_inputs) + "."
            action_taken = "asked_cad_entity_command_clarifying_question"
            outcome = "understood_needs_more_info"
            needs_clarification = True
        else:
            assistant_message = (
                f"Applied CAD entity drafting command `{safe_str(operation_result.get('selected_action'))}` to the persistent CAD entity model. "
                "The changed entities remain review_required=true and construction_release_allowed=false."
            )
            action_taken = "executed_cad_entity_command"
            outcome = "understood_and_executed"
            needs_clarification = False
        return _truthful_decision_update(
            {},
            assistant_message=assistant_message,
            intent="cad_entity_command",
            run_mode="none",
            needs_clarification=needs_clarification,
            action_taken=action_taken,
            action_blocked_reason="; ".join(safe_str(item) for item in safety_blockers),
            required_missing_inputs=missing_inputs,
            affected_systems=["cad_entity_model", "cad_geometry"],
            assumptions=["Chat CAD entity commands mutate only persistent CAD drafting/review entities and do not mutate engineering evidence."],
            next_best_action=safe_str(operation_result.get("next_best_action")),
            command_payload_updates={CAD_ENTITY_CHAT_OPERATION_VERSION: operation_result, CAD_ENTITY_MODEL_VERSION: model},
            outcome=outcome,
            state_changed=changed,
            blocker="; ".join(safe_str(item) for item in safety_blockers),
        )

    if asks_convert_drawn:
        if not (record and project_store and user_id):
            return _truthful_decision_update(
                {},
                assistant_message="I can convert drawn geometry to CAD entities only after a saved project is loaded, so the review-only entity model can be persisted.",
                intent="cad_entity_model",
                run_mode="none",
                needs_clarification=True,
                action_taken="blocked_cad_entity_conversion_missing_project",
                action_blocked_reason="No saved canonical project record is available.",
                required_missing_inputs=["saved project"],
                affected_systems=["cad_entity_model"],
                next_best_action="Save or load the project, then retry the drawn-object conversion.",
                outcome="understood_but_blocked",
                state_changed=False,
                blocker="No saved canonical project record is available.",
            )
        selected_object_ids, selected_geometry_ids = _collect_selected_ids(context)
        converted = manual_drawn_objects_to_cad_entities(project_input, latest_result, created_by=user_id or "user")
        if selected_object_ids or selected_geometry_ids:
            selected = set(selected_object_ids + selected_geometry_ids)
            converted = [
                entity
                for entity in converted
                if safe_str(entity.get("linked_object_id")) in selected
                or safe_str(_safe_dict(entity.get("canonical_geometry_handoff")).get("geometry_id")) in selected
                or safe_str(_safe_dict(entity.get("canonical_geometry_handoff")).get("object_id")) in selected
            ]
        existing_by_id = {safe_str(entity.get("id")): entity for entity in entities if safe_str(entity.get("id"))}
        created_ids: List[str] = []
        for entity in converted:
            entity_id = safe_str(entity.get("id"))
            if not entity_id:
                continue
            existing_by_id[entity_id] = normalize_cad_entity(entity, created_by=user_id or "user")
            created_ids.append(entity_id)
        if not created_ids:
            return _truthful_decision_update(
                {},
                assistant_message="I did not find a valid manual drawn canonical geometry handoff to convert into a CAD entity.",
                intent="cad_entity_model",
                run_mode="none",
                needs_clarification=True,
                action_taken="blocked_no_drawn_geometry_for_cad_entity_conversion",
                action_blocked_reason="No matching manual_drawn canonical_geometry_handoff_v1 was found.",
                required_missing_inputs=["manual drawn geometry handoff"],
                affected_systems=["cad_entity_model"],
                next_best_action="Select or draw one review geometry object, then retry conversion.",
                outcome="understood_but_blocked",
                state_changed=False,
                blocker="No matching manual_drawn canonical_geometry_handoff_v1 was found.",
            )
        source_model = _safe_dict(meta.get(CAD_ENTITY_MODEL_VERSION))
        prior_model = build_cad_entity_model({**meta, CAD_ENTITY_MODEL_VERSION: source_model}, project_input=project_input)
        source_model["entities"] = list(existing_by_id.values())
        source_model["history_snapshots"] = _safe_list(source_model.get("history_snapshots")) + [
            build_cad_history_snapshot(prior_model, actor=user_id or "user")
        ]
        source_model["history"] = _safe_list(source_model.get("history")) + [
            history_event(
                "entity_converted",
                entity_id,
                actor=user_id or "user",
                details={"from": "manual_drawn", "review_required": True},
                before={},
                after=existing_by_id.get(entity_id),
                changed_fields=["entity", "geometry", "source", "review_status"],
            )
            for entity_id in created_ids
        ]
        meta[CAD_ENTITY_MODEL_VERSION] = build_cad_entity_model({**meta, CAD_ENTITY_MODEL_VERSION: source_model}, project_input=project_input)
        final_plan["meta"] = meta
        latest_result["final_plan"] = final_plan
        _save_project_record(project_store, {**record, "_user_id": user_id}, project_input=project_input, latest_result=latest_result)
        model = meta[CAD_ENTITY_MODEL_VERSION]
        return _truthful_decision_update(
            {},
            assistant_message=(
                f"Converted {len(created_ids)} manual drawn object(s) into persistent CAD entities for drafting/review. "
                "They remain draft_review_required, dirty for downstream review, and construction_release_allowed is false."
            ),
            intent="cad_entity_model",
            run_mode="none",
            needs_clarification=False,
            action_taken="converted_drawn_object_to_cad_entity",
            affected_systems=["cad_entity_model", "cad_geometry"],
            assumptions=["Manual drawn geometry conversion preserves review-required status and does not mutate engineering evidence."],
            next_best_action="Review CAD entity validation/source confidence before converting any entity into a site object candidate.",
            command_payload_updates={CAD_ENTITY_MODEL_VERSION: model, "converted_entity_ids": created_ids},
            outcome="understood_and_executed",
            state_changed=True,
        )

    if asks_candidate:
        candidates = cad_entities_to_site_object_candidates(model)
        return _truthful_decision_update(
            {},
            assistant_message=(
                f"{len(candidates)} CAD entity candidate(s) can be presented as review-required site object candidates. "
                "None are accepted as engineering evidence or approved for construction from the CAD conversion alone."
            ),
            intent="cad_entity_model",
            run_mode="none",
            needs_clarification=False,
            action_taken="reported_cad_entity_site_object_candidates",
            affected_systems=["cad_entity_model", "candidate_review"],
            next_best_action="Send candidates through review/acceptance before any engine uses them as project draft evidence.",
            command_payload_updates={"cad_site_object_candidates_v1": candidates, CAD_ENTITY_MODEL_VERSION: model},
            outcome="understood_and_answered",
            state_changed=False,
        )

    validation = _safe_dict(model.get("validation"))
    timeline = _safe_dict(model.get("revision_timeline"))
    history = [_safe_dict(item) for item in _safe_list(model.get("history"))]
    stale_invalid = [
        entity
        for entity in entities
        if entity.get("validation_status") == "invalid" or entity.get("dirty") or entity.get("stale") or entity.get("review_status") == "stale"
    ]
    selected_object_ids, selected_geometry_ids = _collect_selected_ids(context)
    selected_ids = set(selected_object_ids + selected_geometry_ids + _safe_list(_safe_dict(model.get("selection")).get("selected_entity_ids")))

    if asks_selection:
        selection = _safe_dict(model.get("selection"))
        selected_cad_ids = [safe_str(item) for item in _safe_list(selection.get("selected_entity_ids")) if safe_str(item)]
        lines = ["Selected CAD entity IDs:"]
        lines.append(", ".join(selected_cad_ids) if selected_cad_ids else "None.")
        grips = _safe_list(selection.get("grips"))
        blockers = _safe_list(selection.get("blockers"))
        if grips:
            lines.append(f"Visible grip points: {len(grips)}.")
            for grip in grips[:8]:
                rec = _safe_dict(grip)
                point = _safe_dict(rec.get("point"))
                lines.append(f"- {safe_str(rec.get('entity_id'))} {safe_str(rec.get('grip_id'))} at {safe_float(point.get('x'), 0.0):.3f},{safe_float(point.get('y'), 0.0):.3f}")
        if blockers:
            lines.append("Grip/blocker feedback:")
            for blocker in blockers[:8]:
                rec = _safe_dict(blocker)
                lines.append(f"- {safe_str(rec.get('entity_id'))}: {safe_str(rec.get('reason'))}")
        lines.append("Selection is over persistent cad_entity_model_v1 entity IDs and remains drafting/review-only.")
        return _truthful_decision_update({}, assistant_message="\n".join(lines), intent="cad_entity_selection", run_mode="none", needs_clarification=False, action_taken="reported_selected_cad_entities", affected_systems=["cad_entity_model", "cad_geometry"], assumptions=["CAD selection answers use persistent CAD entity IDs, not loose UI-only geometry."], next_best_action="Use grips or CAD commands for drafting/review edits, then rerun affected downstream checks before reliance.", command_payload_updates={CAD_ENTITY_MODEL_VERSION: model}, outcome="understood_and_answered", state_changed=False, blocker="; ".join(safe_str(_safe_dict(item).get("reason")) for item in blockers[:4]))

    if asks_grip_blocker:
        selection = _safe_dict(model.get("selection"))
        blockers = _safe_list(selection.get("blockers"))
        if blockers:
            lines = ["This grip edit is blocked because:"]
            for blocker in blockers[:8]:
                rec = _safe_dict(blocker)
                lines.append(f"- {safe_str(rec.get('entity_id'))}: {safe_str(rec.get('reason'))}")
        elif not _safe_list(selection.get("selected_entity_ids")):
            lines = ["This grip edit is blocked because: missing selected entity."]
        else:
            lines = ["No grip blocker is recorded on the selected CAD entity. If an edit failed, select a visible grip and retry with a valid displacement."]
        lines.append("Grip edits remain review_required=true, draft_review_required=true, and construction_release_allowed=false.")
        return _truthful_decision_update({}, assistant_message="\n".join(lines), intent="cad_entity_grip_edit", run_mode="none", needs_clarification=False, action_taken="explained_cad_grip_edit_blocker", affected_systems=["cad_entity_model", "cad_geometry"], next_best_action="Select an editable grip on a line/polyline/polygon/rectangle/circle/text/dimension/block reference, then retry.", command_payload_updates={CAD_ENTITY_MODEL_VERSION: model}, outcome="understood_and_answered", state_changed=False, blocker="; ".join(safe_str(_safe_dict(item).get("reason")) for item in blockers[:4]) or "missing selected entity")

    if asks_layers:
        lines = ["CAD layers:"]
        for layer in _safe_list(model.get("layers"))[:20]:
            rec = _safe_dict(layer)
            lines.append(
                f"- {safe_str(rec.get('id'))}: {safe_str(rec.get('name'))}, color={safe_str(rec.get('color'))}, "
                f"linetype={safe_str(rec.get('linetype'))}, lineweight={safe_str(rec.get('lineweight'))}, "
                f"visible={bool(rec.get('visible'))}, locked={bool(rec.get('locked'))}, printable={bool(rec.get('printable'))}, "
                f"source={safe_str(rec.get('source'))}, review_required=true"
            )
        if not _safe_list(model.get("layers")):
            lines.append("- No CAD layer registry records are saved yet.")
        lines.append("Layer/style settings are drafting/review metadata only; printable controls sheet/export trace and does not indicate construction readiness.")
        return _truthful_decision_update(
            {},
            assistant_message="\n".join(lines),
            intent="cad_layer_style_manager",
            run_mode="none",
            needs_clarification=False,
            action_taken="reported_cad_layers",
            affected_systems=["cad_entity_model"],
            assumptions=["Layer answers use cad_entity_model_v1 registry records and remain review-only."],
            next_best_action="Review layer visibility, lock, and printable flags before plotting or downstream review.",
            command_payload_updates={CAD_ENTITY_MODEL_VERSION: model},
            outcome="understood_and_answered",
            state_changed=False,
        )

    if asks_layer_edit_blocker:
        phrase = _cad_layer_phrase(message)
        layer_id = _cad_layer_id_from_phrase(model, phrase) if phrase else ""
        layers_by_id = {safe_str(_safe_dict(layer).get("id")): _safe_dict(layer) for layer in _safe_list(model.get("layers"))}
        selected_entities = [entity for entity in entities if safe_str(entity.get("id")) in selected_ids]
        selected_layer = layers_by_id.get(layer_id) if layer_id else layers_by_id.get(safe_str((selected_entities[0] if selected_entities else {}).get("layer_id")))
        if selected_layer and selected_layer.get("locked"):
            blocker = locked_layer_blocker(selected_layer)
        else:
            blocker = "layer_edit_not_blocked_by_layer_lock" if selected_layer else "target_layer_missing"
        lines = [
            f"Layer edit blocker: {blocker}.",
            "Locked layers prevent CAD entity edits and layer/style assignment changes until unlocked through review.",
            "This is a drafting/review guard only and does not change engineering evidence or construction readiness.",
        ]
        return _truthful_decision_update(
            {},
            assistant_message="\n".join(lines),
            intent="cad_layer_style_manager",
            run_mode="none",
            needs_clarification=False,
            action_taken="explained_cad_layer_edit_blocker",
            affected_systems=["cad_entity_model"],
            next_best_action="Unlock the layer after review or move the entity to an editable review layer.",
            command_payload_updates={CAD_ENTITY_MODEL_VERSION: model, "cad_layer_edit_blocker": blocker},
            outcome="understood_and_answered",
            state_changed=False,
            blocker=blocker,
        )

    if asks_undo or asks_restore:
        undo_redo = _safe_dict(model.get("undo_redo"))
        lines = []
        if asks_undo:
            lines.append("Undo last CAD edit is blocked from chat until a safe persisted CAD snapshot replay target is selected and reviewed.")
            action_taken = "blocked_cad_undo_requires_safe_snapshot_review"
        else:
            lines.append("Restore CAD object is blocked from chat until the object, revision snapshot, and review-only replay target are explicit.")
            action_taken = "blocked_cad_restore_requires_safe_snapshot_review"
        if undo_redo.get("can_undo"):
            lines.append(f"Latest snapshot hook: {safe_str(undo_redo.get('latest_undo_snapshot_id'))}; it still requires explicit review before replay.")
        else:
            lines.append(safe_str(undo_redo.get("blocked_reason"), "No persisted CAD history snapshot is available."))
        lines.append("Undo/restore would remain draft_review_required and construction_release_allowed=false; it would not approve or certify engineering evidence.")
        return _truthful_decision_update(
            {},
            assistant_message="\n".join(lines),
            intent="cad_entity_history",
            run_mode="none",
            needs_clarification=True,
            action_taken=action_taken,
            action_blocked_reason=lines[0],
            required_missing_inputs=["explicit CAD entity id", "persisted CAD revision snapshot", "review confirmation"],
            affected_systems=["cad_entity_model", "cad_history"],
            assumptions=["Chat undo/restore must not silently mutate CAD or engineering evidence."],
            next_best_action="Open CAD history, choose the entity and revision snapshot, then review the restore diff before applying it.",
            command_payload_updates={CAD_ENTITY_MODEL_VERSION: model, "cad_undo_redo": undo_redo},
            outcome="understood_but_blocked",
            state_changed=False,
            blocker=lines[0],
        )

    if asks_update_stale_dimensions:
        stale_dimensions = [
            entity
            for entity in entities
            if entity.get("type") == "dimension" and (entity.get("dirty") or entity.get("stale") or entity.get("review_status") == "stale")
        ]
        if not (record and project_store and user_id):
            return _truthful_decision_update(
                {},
                assistant_message="I can refresh stale dimension associations only after a saved project is loaded, so the persistent CAD entity model and history can be updated safely.",
                intent="cad_dimension_annotation",
                run_mode="none",
                needs_clarification=True,
                action_taken="blocked_stale_dimension_update_missing_project",
                action_blocked_reason="No saved canonical project record is available.",
                required_missing_inputs=["saved project"],
                affected_systems=["cad_entity_model", "cad_dimensions"],
                next_best_action="Save or load the project, then retry updating stale dimensions.",
                command_payload_updates={CAD_ENTITY_MODEL_VERSION: model},
                outcome="understood_but_blocked",
                state_changed=False,
                blocker="No saved canonical project record is available.",
            )
        changed_refs: List[str] = []
        for entity in stale_dimensions:
            changed_refs.extend(_safe_list(_safe_dict(entity.get("dimension")).get("measured_entity_refs")))
        source_model = _safe_dict(meta.get(CAD_ENTITY_MODEL_VERSION))
        refreshed_entities, association_events = refresh_dimension_associations(
            _safe_list(source_model.get("entities")) or entities,
            changed_entity_ids=changed_refs,
            actor=user_id or "user",
        )
        source_model["entities"] = refreshed_entities
        source_model["history"] = _safe_list(source_model.get("history")) + association_events
        meta[CAD_ENTITY_MODEL_VERSION] = build_cad_entity_model({**meta, CAD_ENTITY_MODEL_VERSION: source_model}, project_input=project_input)
        final_plan["meta"] = meta
        latest_result["final_plan"] = final_plan
        _save_project_record(project_store, {**record, "_user_id": user_id}, project_input=project_input, latest_result=latest_result)
        model = meta[CAD_ENTITY_MODEL_VERSION]
        return _truthful_decision_update(
            {},
            assistant_message=(
                f"Refreshed {len(association_events)} stale dimension association(s) where the measured CAD entity still exists. "
                "They remain stale/dirty review aids until reviewed; engineering quantities were not updated."
            ),
            intent="cad_dimension_annotation",
            run_mode="none",
            needs_clarification=False,
            action_taken="updated_stale_dimension_associations",
            affected_systems=["cad_entity_model", "cad_dimensions", "cad_history"],
            assumptions=["Dimension refresh updates drafting/review association metadata only and does not mutate engineering evidence."],
            next_best_action="Review refreshed dimensions before relying on them in exports or reports.",
            command_payload_updates={CAD_ENTITY_MODEL_VERSION: model, "updated_dimension_entity_ids": [safe_str(event.get("entity_id")) for event in association_events]},
            outcome="understood_and_executed",
            state_changed=bool(association_events),
        )

    if asks_history or asks_changed or asks_object_changed:
        filtered_history = history
        if asks_object_changed and selected_ids:
            filtered_history = [event for event in history if safe_str(event.get("entity_id")) in selected_ids]
        lines = [
            f"CAD revision timeline: {safe_str(timeline.get('latest_revision_id')) or 'no revision id'}; {len(history)} history event(s).",
            (
                f"Entities: {safe_str(_safe_dict(timeline.get('entity_counts')).get('total'), '0')} total, "
                f"{safe_str(_safe_dict(timeline.get('entity_counts')).get('stale_or_dirty'), '0')} stale/dirty, "
                f"{safe_str(_safe_dict(timeline.get('entity_counts')).get('invalid'), '0')} invalid."
            ),
        ]
        changed = _safe_list(timeline.get("changed_entities"))
        added = _safe_list(timeline.get("added_entities"))
        removed = _safe_list(timeline.get("removed_entities"))
        if changed:
            lines.append("Changed entities: " + ", ".join(safe_str(item) for item in changed[:10] if safe_str(item)))
        if added:
            lines.append("Added/imported/restored entities: " + ", ".join(safe_str(item) for item in added[:10] if safe_str(item)))
        if removed:
            lines.append("Removed entities: " + ", ".join(safe_str(item) for item in removed[:10] if safe_str(item)))
        if filtered_history:
            lines.append("Recent history:")
            for event in filtered_history[-8:]:
                fields = ", ".join(safe_str(field) for field in _safe_list(event.get("changed_fields")) if safe_str(field))
                lines.append(
                    f"- {safe_str(event.get('event_type'))} {safe_str(event.get('entity_id'))} by {safe_str(event.get('actor'))} "
                    f"at {safe_str(event.get('timestamp'))}; fields={fields or 'summary-only'}"
                )
        else:
            lines.append("- No matching CAD history events are saved yet.")
        blockers = _safe_list(timeline.get("review_blockers"))
        if blockers:
            lines.append(f"Review blockers: {len(blockers)} validation/source/stale blocker(s).")
        lines.append("CAD history is review-required and construction_release_allowed=false; it does not stamp, seal, sign, certify, approve, or submit construction documents.")
        return _truthful_decision_update(
            {},
            assistant_message="\n".join(lines),
            intent="cad_entity_history",
            run_mode="none",
            needs_clarification=asks_object_changed and not bool(selected_ids),
            action_taken="reported_cad_entity_history" if asks_history or asks_object_changed else "reported_cad_revision_changes",
            affected_systems=["cad_entity_model", "cad_history"],
            assumptions=["CAD history uses saved project metadata only and remains review-only."],
            next_best_action="Review changed CAD entities and rerun affected downstream checks before relying on drafting edits.",
            command_payload_updates={CAD_ENTITY_MODEL_VERSION: model, "cad_revision_timeline": timeline},
            outcome="understood_and_answered",
            state_changed=False,
            referenced_object_ids=selected_object_ids,
            referenced_geometry_ids=selected_geometry_ids,
            blocker="; ".join(safe_str(item.get("reason")) for item in blockers[:4] if isinstance(item, dict)),
        )

    if asks_stale_invalid or asks_dimension_stale:
        dimension_only = asks_dimension_stale and not asks_stale_invalid
        rows = [entity for entity in stale_invalid if entity.get("type") == "dimension"] if dimension_only else stale_invalid
        lines = ["Stale dimensions:" if dimension_only else "CAD entities that are stale or invalid:"]
        if rows:
            for entity in rows[:10]:
                blockers = ", ".join(safe_str(item) for item in _safe_list(entity.get("validation_blockers")) if safe_str(item))
                dim = _safe_dict(entity.get("dimension"))
                reason = safe_str(dim.get("association_dirty_reason") or dim.get("association_status"))
                lines.append(f"- {safe_str(entity.get('id'))} ({safe_str(entity.get('type'))}): {blockers or reason or 'stale/dirty rerun review required'}")
        else:
            lines.append("- None visible in the current CAD entity model.")
        lines.append("Dimensions and CAD entities remain review-only and cannot create construction release or update engineering quantities by themselves.")
        action_taken = "explained_stale_dimension_status" if dimension_only else "reported_stale_invalid_cad_entities"
    elif asks_review_only:
        lines = [
            "This CAD object is review-only because CAD/manual/imported geometry is drafting evidence, not survey-backed or engineer-approved evidence by itself.",
            "It needs valid geometry, source-confidence review, accepted source evidence where applicable, and external professional/user review before downstream reliance.",
            "Civora does not stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record.",
        ]
        action_taken = "explained_cad_entity_review_only"
    else:
        lines = [f"CAD entities in this project: {len(entities)}."]
        if entities:
            for entity in entities[:12]:
                lines.append(
                    f"- {safe_str(entity.get('id'))}: {safe_str(entity.get('type'))}, layer={safe_str(entity.get('layer_id'))}, "
                    f"source_confidence={safe_str(entity.get('source_confidence'))}, review_status={safe_str(entity.get('review_status'))}"
                )
        else:
            lines.append("- No persistent CAD entities are saved yet.")
        if validation.get("blockers"):
            lines.append(f"Blockers: {len(_safe_list(validation.get('blockers')))} validation/source/stale blocker(s).")
        lines.append("All CAD entities are drafting/review objects with construction_release_allowed=false.")
        action_taken = "reported_cad_entities"

    return _truthful_decision_update(
        {},
        assistant_message="\n".join(lines),
        intent="cad_entity_model",
        run_mode="none",
        needs_clarification=False,
        action_taken=action_taken,
        affected_systems=["cad_entity_model"],
        assumptions=["CAD entity answers use saved project metadata only."],
        next_best_action="Use CAD entities for command-line, snaps, grips, layers, dimensions, blocks, plotting, and DXF review workflows after validation.",
        command_payload_updates={CAD_ENTITY_MODEL_VERSION: model},
        outcome="understood_and_answered",
        state_changed=False,
        blocker="; ".join(safe_str(item.get("reason")) for item in _safe_list(validation.get("blockers"))[:4] if isinstance(item, dict)),
    )


def _dwg_compatibility_chat_response(message: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lowered = _normalized_text(message)
    mentions_dwg = bool(re.search(r"\bdwg\b", lowered))
    mentions_dxf = bool(re.search(r"\bdxf\b", lowered))
    mentions_autocad = "autocad" in lowered or "auto cad" in lowered
    mentions_civil3d = "civil3d" in lowered or "civil 3d" in lowered
    mentions_roundtrip = "roundtrip" in lowered or "round trip" in lowered
    if not mentions_dwg and not mentions_civil3d and not mentions_autocad and not mentions_dxf:
        return None
    asks_export = "export" in lowered or "download" in lowered or "save" in lowered
    asks_open = "open" in lowered or "load" in lowered or "import" in lowered
    asks_why = "why" in lowered or "unsupported" in lowered or "not supported" in lowered
    asks_need = "what do i need" in lowered or "what do we need" in lowered or "need for" in lowered or "civil3d" in lowered or "civil 3d" in lowered
    asks_preserved = "preserve" in lowered or "preserved" in lowered or "kept" in lowered
    asks_lost = "lost" in lowered or "missing" in lowered or "limited" in lowered or "dropped" in lowered
    asks_review_only = "review-only" in lowered or "review only" in lowered or ("why" in lowered and mentions_dxf)
    asks_ready = "ready" in lowered or "good to use" in lowered or "can i use" in lowered
    if not (asks_export or asks_why or asks_need or asks_open or asks_preserved or asks_lost or asks_review_only or asks_ready or mentions_roundtrip):
        return None

    meta = _meta_from_chat_context(context)
    strategy = dwg_strategy_from_meta(meta)
    export_report = _safe_dict(meta.get("export_package_report_v1"))
    dxf_roundtrip = _safe_dict(meta.get("dxf_roundtrip_report_v1") or export_report.get("dxf_roundtrip_report_v1"))
    civil3d_record = _safe_dict(_safe_dict(export_report.get("external_verification")).get("civil3d"))
    civil3d_status = str(
        civil3d_record.get("status")
        or _safe_dict(_safe_dict(meta.get("external_verification")).get("civil3d")).get("status")
        or "not_verified"
    )
    if civil3d_status not in {"not_verified", "blocked_needs_review", "externally_verified_review_only"}:
        civil3d_status = "not_verified"
    if mentions_dxf and asks_lost:
        lost = _safe_list(dxf_roundtrip.get("lost_limited"))
        unsupported = _safe_list(dxf_roundtrip.get("unsupported"))
        if lost or unsupported:
            lost_text = "; ".join(safe_str(item) for item in (lost + unsupported)[:6])
        else:
            lost_text = "No saved DXF roundtrip loss report is attached yet."
        assistant_message = (
            f"DXF lost/limited items: {lost_text} "
            "Anything stale, dirty, unsupported, or absent from the local parse remains review-required and cannot support export-ready or construction-release claims."
        )
        action_taken = "answered_dxf_roundtrip_loss"
        next_best_action = "Review dxf_roundtrip_report_v1.lost_limited, unsupported, and blockers before sharing the DXF review artifact."
    elif mentions_dxf and asks_review_only:
        assistant_message = (
            "DXF is review-only because the roundtrip is local exchange evidence: persistent CAD entities are exported, parsed back, and compared for preservation. "
            "That does not prove AutoCAD or Civil 3D acceptance, does not support DWG natively, and does not create construction approval or professional responsibility."
        )
        action_taken = "explained_dxf_review_only"
        next_best_action = "Use DXF as a review exchange artifact and attach external target-tool evidence before making any compatibility claim."
    elif mentions_dxf and (mentions_roundtrip or asks_preserved):
        preserved = _safe_dict(dxf_roundtrip.get("preserved"))
        matrix = _safe_dict(dxf_roundtrip.get("roundtrip_preservation_matrix"))
        if preserved or matrix:
            preserved_text = ", ".join(
                f"{key}={safe_str(value)}"
                for key, value in {**preserved, **matrix}.items()
                if safe_str(key)
            )
        else:
            preserved_text = "layer preservation, supported object types, text/labels, symbol placeholders when present, dimensions where supported, and canonical ID traceability through CAD entity IDs via sidecar are the expected checks; no saved roundtrip report is attached yet"
        assistant_message = (
            f"The DXF preservation check reports: {preserved_text}. "
            "This is local review evidence only; it does not verify Civil 3D or DWG, and it does not prove AutoCAD acceptance."
        )
        action_taken = "answered_dxf_roundtrip_preservation"
        next_best_action = "Run the persistent CAD entity DXF roundtrip and review dxf_roundtrip_report_v1 before sharing the artifact."
    elif (mentions_dxf or mentions_autocad) and asks_open:
        status = safe_str(_safe_dict(_safe_dict(export_report.get("supported_deliverables")).get("dxf")).get("roundtrip_status"), "not_run")
        assistant_message = (
            f"It may open in AutoCAD as a DXF review exchange artifact, but Civora cannot claim AutoCAD acceptance from local parsing alone. "
            f"Current DXF roundtrip status is {status}; Civil 3D remains not_verified and DWG is not natively supported."
        )
        action_taken = "answered_autocad_dxf_open_status"
        next_best_action = "Open the DXF in the target AutoCAD environment and attach a target-tool workflow record with observed preserved and lost/limited items."
    elif mentions_civil3d and asks_open:
        assistant_message = (
            "It might open as a review artifact if the target Civil 3D workflow accepts the DXF or LandXML, but Civora cannot claim it will open correctly "
            "until an external target-workflow record is attached. Civil 3D status remains not_verified without tool/version, source hashes, import result, "
            "and observed limitations."
        )
        action_taken = "answered_civil3d_open_status"
        next_best_action = "Export DXF/LandXML review artifacts and record the Civil 3D import workflow result from the target environment."
    elif mentions_civil3d and asks_preserved:
        preserved = [str(item) for item in _safe_list(civil3d_record.get("preserved_elements")) if str(item)]
        limited = [str(item) for item in _safe_list(civil3d_record.get("lost_limited_elements")) if str(item)]
        if civil3d_status == "externally_verified_review_only" and (preserved or limited):
            preserved_text = ", ".join(preserved[:6]) if preserved else "no preserved elements were listed"
            limited_text = ", ".join(limited[:6]) if limited else "no lost or limited elements were listed"
            assistant_message = (
                f"The attached Civil 3D workflow record is externally_verified_review_only. It says Civil 3D preserved: {preserved_text}. "
                f"Lost or limited elements: {limited_text}. This is import/workflow evidence only; engineer review is still required."
            )
        else:
            assistant_message = (
                "Civil 3D preservation is not_verified because no accepted external workflow record is attached. Civora can report what the DXF/LandXML "
                "review artifacts contain, but it cannot say what Civil 3D preserved until the target workflow record lists preserved_elements and "
                "lost_limited_elements."
            )
        action_taken = "answered_civil3d_preservation_status"
        next_best_action = "Attach the Civil 3D workflow record with preserved_elements, lost_limited_elements, screenshots/evidence URI, and source artifact hashes."
    elif mentions_civil3d and asks_ready:
        assistant_message = (
            f"No. This is not Civil3D-ready or approved for construction by Civora. Civil 3D workflow status is {civil3d_status}. "
            "DXF and LandXML remain the exchange paths unless an external workflow record exists; even externally_verified_review_only means review-only "
            "import/workflow evidence, not approval, stamping, sealing, certification, or submission readiness."
        )
        action_taken = "answered_civil3d_ready_status"
        next_best_action = "Use DXF/LandXML review artifacts and attach a target Civil 3D workflow record before describing any external import evidence."
    elif mentions_civil3d and not mentions_dwg:
        assistant_message = (
            "For Civil 3D, Civora needs a target-workflow record with verifier identity, date, tool and version, source artifacts, "
            "artifact hashes, workflow steps, import result, preserved elements, lost/limited elements, screenshots/evidence URI, and review-only status. "
            "Civora can provide DXF review exports and LandXML exchange data. Workflow state is not_verified until that record exists, "
            "blocked_needs_review if it fails or is incomplete, and externally_verified_review_only if the target import/workflow check passes."
        )
        action_taken = "answered_civil3d_compatibility_requirements"
        next_best_action = "Generate the DXF/LandXML review artifacts, then attach a Civil 3D workflow record from the target environment."
    elif asks_why:
        assistant_message = (
            "DWG is unsupported because Civora does not include a native DWG writer and DWG SDKs/providers require separate licensing, "
            "implementation, and repeatable compatibility tests. The truthful path today is DXF/LandXML review output, or an optional external "
            "conversion hook with a workflow record."
        )
        action_taken = "explained_dwg_unsupported_status"
        next_best_action = "Use DXF review export now, or configure an external DWG conversion hook and attach its workflow record."
    else:
        assistant_message = (
            "No, Civora cannot export DWG natively right now. DWG status is "
            f"{strategy['dwg_status']}. You can export DXF for review, use LandXML where available, or configure an external DWG conversion hook "
            "and attach a workflow record before Civora shows DWG as an externally converted review artifact. That hook is opt-in and review-only; "
            "it is never native DWG writing."
        )
        action_taken = "answered_dwg_export_capability"
        next_best_action = "Open Deliver for DXF review export, or configure the external DWG conversion hook outside Civora."

    return _truthful_decision_update(
        {},
        assistant_message=assistant_message,
        intent="explain",
        run_mode="none",
        needs_clarification=False,
        action_taken=action_taken,
        affected_systems=["cad_interop", "deliverables"],
        assumptions=["DWG answers are based on Civora compatibility metadata, not a native DWG writer."],
        next_best_action=next_best_action,
        command_payload_updates={
            "ui_navigation_target": "deliverables",
            "requested_ui_mode": "deliver",
            "dwg_strategy": strategy,
            "civil3d_status": civil3d_status,
            "civil3d_external_verification_record": civil3d_record,
        },
        confidence=0.92,
    )


def _plotting_sheet_chat_response(message: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lowered = _normalized_text(message)
    asks_sheet_set = bool(re.search(r"\b(make|create|build)\s+(a\s+)?sheet\s+set\b", lowered))
    asks_viewport_scale = "viewport" in lowered and "scale" in lowered
    asks_revision = "revision note" in lowered or re.search(r"\badd\s+revision\b", lowered)
    asks_plot = "plot this review set" in lowered or ("plot" in lowered and "review set" in lowered)
    asks_not_for_construction = "why is this not for construction" in lowered or "not for construction" in lowered
    if not any([asks_sheet_set, asks_viewport_scale, asks_revision, asks_plot, asks_not_for_construction]):
        return None

    meta = _meta_from_chat_context(context)
    standards = build_plotting_standards(meta)
    base_payload = {
        "paper_model_plotting_standards_v1": standards,
        "ui_navigation_target": "deliverables",
        "requested_ui_mode": "sheet_review",
        "review_only": True,
        "engineer_review_required": True,
        "construction_release_allowed": False,
    }
    scale_match = re.search(r"1\s*(?:inch|in|\")?\s*(?:equals|=|:)\s*(\d+(?:\.\d+)?)(?=\s*(?:feet|foot|ft|'|$))", lowered)
    if asks_sheet_set:
        message_text = (
            "I can make a review sheet set with separate model-space source geometry and sheet/layout viewports, a sheet index, title block fields, "
            "viewport scale locks, north arrows, scale bars, plot styles, a revision block, and review PDF/sheet JSON export metadata. "
            "It remains a review-only production aid, not an approved construction document."
        )
        action_taken = "answered_make_review_sheet_set"
        payload = {**base_payload, "sheet_action": "make_sheet_set"}
    elif asks_viewport_scale:
        scale_value = scale_match.group(1) if scale_match else "50"
        if "." in scale_value:
            scale_value = scale_value.rstrip("0").rstrip(".")
        requested_scale = f"1:{scale_value}"
        message_text = (
            f"Set the active sheet viewport scale to {requested_scale} and keep the viewport scale locked. "
            "Layer visibility, view target, north arrow, and scale bar stay viewport-specific for review plotting."
        )
        action_taken = "answered_set_viewport_scale"
        payload = {**base_payload, "sheet_action": "set_viewport_scale", "viewport_scale": requested_scale, "scale_locked": True}
    elif asks_revision:
        note_match = re.search(r"revision note(?:\s+that says|\s+saying|:)?\s*[\"]?(.+?)[\"]?$", message, flags=re.IGNORECASE)
        note = safe_str(note_match.group(1) if note_match else "", "Review revision note added; verify before package handoff.")
        message_text = (
            f"Added a review revision note: {note}. The revision block records review history only and is not Civora approval, signature, seal, or construction release."
        )
        action_taken = "answered_add_revision_note"
        payload = {**base_payload, "sheet_action": "add_revision_note", "revision_note": note}
    elif asks_plot:
        message_text = (
            "Plot the active review set as a review PDF/print package and sheet JSON with lineweight/color/linetype mapping, optional grayscale, "
            "and the REVIEW ONLY - NOT FOR CONSTRUCTION watermark. This does not create submission packages or construction approvals."
        )
        action_taken = "answered_plot_review_set"
        payload = {**base_payload, "sheet_action": "plot_review_set", "exports": standards["exports"], "plot_styles": standards["plot_styles"]}
    else:
        message_text = (
            "This is not for construction because Civora has only review-package evidence: sheets and plots are production aids that require external licensed/user review. "
            "Civora does not stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record."
        )
        action_taken = "answered_not_for_construction_sheet_limit"
        payload = {**base_payload, "sheet_action": "explain_not_for_construction", "limitations": standards["limitations"]}

    return _truthful_decision_update(
        {},
        assistant_message=message_text,
        intent="sheet_plotting",
        run_mode="none",
        needs_clarification=False,
        action_taken=action_taken,
        affected_systems=["sheets", "plotting", "deliverables"],
        assumptions=["Sheet and plot actions are review-package workflow aids only."],
        next_best_action="Open the sheet/layout editor, review blockers, then export review PDF or sheet JSON if appropriate.",
        command_payload_updates=payload,
        confidence=0.9,
    )


def _discipline_from_message(message: str) -> str:
    lowered = _normalized_text(message)
    aliases = {
        "grading": ("grading", "grade", "cut/fill", "cut fill", "slope"),
        "storm_pipe": ("storm", "drainage", "inlet", "hgl", "egl", "detention", "outfall", "overflow"),
        "sanitary": ("sanitary", "sewer", "manhole", "lateral"),
        "water": ("water", "fire flow", "fire-flow", "hydrant", "pressure"),
        "roadway_corridor": ("roadway", "road", "profile", "crown", "curb", "ada"),
        "quantity": ("quantity", "quantities", "cost", "price", "pricing"),
    }
    for engine_id, tokens in aliases.items():
        if any(token in lowered for token in tokens):
            return engine_id
    return ""


def _discipline_depth_chat_response(message: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lowered = _normalized_text(message)
    explicit_depth_request = (
        "proof" in lowered
        or "depth" in lowered
        or "readiness" in lowered
        or "exact fix" in lowered
        or "ready for production" in lowered
        or "production depth" in lowered
    )
    if not explicit_depth_request and "exact fix" not in lowered:
        return None
    engine_id = _discipline_from_message(message)
    if not engine_id:
        return None
    meta = _meta_from_chat_context(context)
    if not meta:
        return None
    readiness = _safe_dict(meta.get("engine_readiness"))
    engine_row = _safe_dict(_safe_dict(readiness.get("engines")).get(engine_id))
    if not engine_row:
        return None
    evidence = _safe_list(engine_row.get("evidence"))
    blockers = _safe_list(engine_row.get("missing_requirements")) + _safe_list(engine_row.get("production_blockers"))
    proof = _safe_dict(engine_row.get("discipline_depth_proof")) or build_engine_proof_contract(
        engine_id,
        meta=meta,
        evidence=evidence,
        blockers=blockers,
        classification="production-depth" if engine_row.get("status") == "production_ready" else "review",
        status=safe_str(engine_row.get("status"), "unknown"),
    )
    missing = [safe_str(_safe_dict(item).get("label")) for item in _safe_list(proof.get("missing_proof")) if safe_str(_safe_dict(item).get("label"))]
    exact_fixes = [safe_str(item) for item in _safe_list(proof.get("exact_fixes")) if safe_str(item)]
    blocker_text = [
        safe_str(_safe_dict(item).get("message") or _safe_dict(item).get("reason") or _safe_dict(item).get("field"))
        for item in blockers
        if safe_str(_safe_dict(item).get("message") or _safe_dict(item).get("reason") or _safe_dict(item).get("field"))
    ]
    if not missing and not blocker_text and safe_str(engine_row.get("status")) == "production_ready":
        summary = f"{engine_id.replace('_', ' ').title()} has production-depth backend evidence, but it is still engineer-review-required."
    else:
        summary = f"{engine_id.replace('_', ' ').title()} is blocked or review-depth because required proof is missing."
    lines = [summary]
    if blocker_text:
        lines.append("Blockers: " + "; ".join(blocker_text[:4]) + ".")
    if missing:
        lines.append("Missing proof: " + ", ".join(missing[:6]) + ".")
    if exact_fixes:
        lines.append("Exact fix: " + exact_fixes[0])
    lines.append("Civora does not stamp, seal, certify, approve construction, submit construction documents, or act as engineer of record.")
    return _truthful_decision_update(
        {},
        assistant_message="\n".join(lines),
        intent="explain",
        run_mode="none",
        needs_clarification=False,
        action_taken="answered_discipline_depth_blocker",
        affected_systems=[engine_id],
        assumptions=["Answer uses saved engine readiness and discipline proof records only."],
        next_best_action=exact_fixes[0] if exact_fixes else "Review the discipline proof checklist and rerun the engine depth audit after inputs are corrected.",
        command_payload_updates={
            "ui_navigation_target": "analysis",
            "requested_ui_mode": "review",
            "engine_id": engine_id,
            "discipline_depth_proof": proof,
        },
        confidence=0.91,
        blocker="; ".join(blocker_text[:4] or missing[:4]),
    )


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


def _geometry_edit_kind_from_message(message: str) -> str:
    lowered = _normalized_text(message)
    if "why" in lowered and "polygon" in lowered and ("close" in lowered or "closing" in lowered):
        return "polygon_close_explain"
    if "fix" in lowered and "geometry" in lowered:
        return "fix_geometry"
    if re.search(r"\btrim\b", lowered):
        return "trim"
    if re.search(r"\bextend\b", lowered):
        return "extend"
    if re.search(r"\boffset\b", lowered):
        return "offset"
    if re.search(r"\bfillet\b", lowered):
        return "fillet"
    return ""


def _geometry_edit_distance_from_message(message: str) -> Optional[float]:
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:ft|feet|foot)?", _normalized_text(message))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _cad_command_line_chat_response(message: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lowered = _normalized_text(message)
    if ("pdf" in lowered and "cad" in lowered) or ("raster line" in lowered and "cad" in lowered):
        return None
    mentions_command_line = (
        "command line" in lowered
        or "typed command" in lowered
        or "cad command" in lowered
        or "autocad" in lowered
        or re.search(r"\b(line|pline|rectangle|circle|arc|offset|trim|extend|fillet|move|rotate|scale|copy|delete|dim|text|layer|snap|ortho)\b", lowered)
    )
    if not mentions_command_line:
        return None
    asks_available = any(phrase in lowered for phrase in ("what commands", "available commands", "commands are available", "how do i use", "help"))
    asks_blocked = any(token in lowered for token in ("blocked", "can't", "cannot", "wont", "won't", "why"))
    if not asks_available and not asks_blocked and "command line" not in lowered and "cad command" not in lowered and "autocad" not in lowered:
        return None

    selected_object_ids, selected_geometry_ids = _collect_selected_ids(context)
    selected_count = len(selected_object_ids) + len(selected_geometry_ids)
    blocked_reasons: List[str] = []
    if any(token in lowered for token in ("offset", "trim", "extend", "fillet", "move", "rotate", "scale", "copy", "delete", "dim")) and selected_count == 0:
        blocked_reasons.append("selected-object commands need one or more selected editable draft CAD objects")
    if "offset" in lowered and (_geometry_edit_distance_from_message(message) is None):
        blocked_reasons.append("OFFSET needs a non-zero distance, for example OFFSET 10")
    if ("move" in lowered and "selected" in lowered and not re.search(r"-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?", lowered)):
        blocked_reasons.append("MOVE selected needs a displacement vector, for example MOVE selected 20,0")

    command_summary = (
        "The CAD command input supports LINE, PLINE, RECTANGLE, CIRCLE, ARC, OFFSET, TRIM, EXTEND, FILLET, MOVE, ROTATE, SCALE, COPY, "
        "DELETE, DIM, TEXT, LAYER, SNAP, and ORTHO. Simple forms include LINE 0,0 100,0; PLINE 0,0 50,0 50,50; "
        "RECTANGLE 0,0 100,60; OFFSET 10; MOVE selected 20,0; ROTATE selected 45; and SCALE selected 1.2."
    )
    if blocked_reasons:
        command_summary += " Blocked reason: " + "; ".join(blocked_reasons) + "."
    command_summary += (
        " These are drafting/review actions only: created or edited geometry remains manual_drawn and draft_review_required, "
        "and command-line edits do not certify evidence, approve construction, or trigger engineering success."
    )
    return _truthful_decision_update(
        {},
        assistant_message=command_summary,
        intent="conversation",
        run_mode="none",
        design_prompt="",
        needs_clarification=bool(blocked_reasons),
        action_taken="answered_cad_command_line_help" if not blocked_reasons else "answered_cad_command_line_blocked_reason",
        action_blocked_reason="; ".join(blocked_reasons),
        required_missing_inputs=blocked_reasons,
        affected_systems=["cad_geometry"],
        assumptions=["Typed CAD commands are drafting/review commands only and do not mutate engineering evidence from chat."],
        next_best_action="Use the canvas command input, then review topology/source blockers before rerunning affected systems.",
        outcome="understood_needs_more_info" if blocked_reasons else "understood_and_answered",
        state_changed=False,
    )



def _drawn_geometry_edit_chat_response(
    decision: Dict[str, Any],
    *,
    message: str,
    context: Dict[str, Any],
    project_input: Dict[str, Any],
    latest_result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    edit_kind = _geometry_edit_kind_from_message(message)
    if not edit_kind:
        return None
    handoffs = _canonical_geometry_handoffs(project_input, latest_result)
    selected_object_ids, selected_geometry_ids = _collect_selected_ids(context)
    matches = _matching_handoffs(handoffs, selected_object_ids, selected_geometry_ids)
    operation_labels = {
        "trim": "Trim",
        "extend": "Extend",
        "offset": "Offset",
        "fillet": "Fillet",
        "fix_geometry": "Fix geometry if safe",
        "polygon_close_explain": "Explain polygon closure",
    }
    if not selected_object_ids and not selected_geometry_ids:
        return _truthful_decision_update(
            decision,
            assistant_message=(
                f"{operation_labels[edit_kind]} needs a selected drawn CAD object. Select one draft/manual geometry item in the canvas, then ask again. "
                "Civora will keep it draft_review_required and will not run engineering generation from the edit."
            ),
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=True,
            action_taken="blocked_geometry_edit_missing_selection",
            action_blocked_reason="No selected or referenced drawn geometry was provided.",
            required_missing_inputs=["selected drawn geometry"],
            affected_systems=["cad_geometry"],
            next_best_action="Select one editable drawn object in the canvas and retry the CAD edit.",
            outcome="understood_needs_more_info",
            state_changed=False,
        )
    if len(matches) != 1:
        return _truthful_decision_update(
            decision,
            assistant_message="I need exactly one selected drawn geometry item for that edit so I do not mutate the wrong evidence.",
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=True,
            action_taken="blocked_geometry_edit_ambiguous_selection",
            action_blocked_reason=f"Referenced geometry was ambiguous: {len(matches)} matching handoffs found.",
            required_missing_inputs=["one unambiguous selected drawn geometry"],
            affected_systems=["cad_geometry"],
            next_best_action="Select a single CAD object or vertex and retry the edit.",
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
            assistant_message=f"I found the selected geometry, but the CAD edit is blocked: {reason}.",
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=True,
            action_taken="blocked_invalid_geometry_handoff",
            action_blocked_reason=reason,
            required_missing_inputs=["valid canonical_geometry_handoff_v1"],
            affected_systems=["cad_geometry"],
            next_best_action="Fix the drawn geometry handoff blockers before applying CAD edits.",
            outcome="understood_but_blocked",
            state_changed=False,
            blocker=reason,
            referenced_object_ids=referenced_object_ids,
            referenced_geometry_ids=referenced_geometry_ids,
        )
    distance = _geometry_edit_distance_from_message(message)
    if edit_kind == "offset" and (distance is None or abs(distance) <= 0):
        return _truthful_decision_update(
            decision,
            assistant_message="Offset needs a non-zero distance, for example: offset this line 10 feet.",
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=True,
            action_taken="blocked_geometry_edit_missing_distance",
            action_blocked_reason="Offset distance was missing or zero.",
            required_missing_inputs=["offset distance"],
            affected_systems=["cad_geometry"],
            next_best_action="Provide the offset distance in feet.",
            outcome="understood_needs_more_info",
            state_changed=False,
            referenced_object_ids=referenced_object_ids,
            referenced_geometry_ids=referenced_geometry_ids,
        )
    if edit_kind == "polygon_close_explain":
        message_text = (
            "A polygon may fail to close when it has fewer than three usable vertices, duplicate/zero-length edges, a gap beyond tolerance, "
            "or a self-intersection. The canvas cleanup can remove duplicate vertices and close small gaps, but it blocks self-intersections "
            "and polygon holes because the editor currently supports one exterior ring only. The result remains review-required."
        )
        action_taken = "explained_polygon_close_blockers"
    elif edit_kind == "fix_geometry":
        message_text = (
            "I can attempt safe cleanup in the canvas: remove duplicate vertices, close small gaps, preserve source confidence and canonical IDs, "
            "then leave the geometry draft_review_required. I will block instead of editing if cleanup would collapse the polygon, hide a hole, "
            "or leave a self-intersection."
        )
        action_taken = "answered_safe_geometry_fix_path"
    else:
        extra = f" with {distance:g} ft" if edit_kind == "offset" and distance is not None else ""
        message_text = (
            f"Use the CAD canvas {operation_labels[edit_kind].lower()} control{extra} on the selected draft geometry. "
            "The edit stays manual_drawn/user_drawn_review_required, keeps canonical IDs where available, marks geometry dirty for downstream rerun review, "
            "and does not trigger engineering generation or construction-document success."
        )
        action_taken = f"answered_cad_{edit_kind}_edit_path"
    return _truthful_decision_update(
        decision,
        assistant_message=message_text,
        intent="conversation",
        run_mode="none",
        design_prompt="",
        needs_clarification=False,
        action_taken=action_taken,
        action_blocked_reason="",
        affected_systems=["cad_geometry"],
        assumptions=["CAD geometry edits are client-side draft operations unless explicitly accepted and rerun later."],
        next_best_action="Apply the edit in the canvas, then review topology blockers before rerunning affected systems.",
        command_payload_updates={
            "cad_geometry_edit": {
                "operation": edit_kind,
                "distance_ft": distance,
                "object_id": referenced_object_ids[0],
                "geometry_id": referenced_geometry_ids[0],
                "review_required": True,
                "construction_release_allowed": False,
            }
        },
        outcome="understood_and_answered",
        state_changed=False,
        referenced_object_ids=referenced_object_ids,
        referenced_geometry_ids=referenced_geometry_ids,
    )


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


def _utility_catalog_chat_response(message: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lowered = _normalized_text(message)
    catalog_words = ("catalog", "part", "parts", "pipe size", "pipe sizes", "hydrant", "valve", "fitting", "manhole", "inlet")
    if not any(word in lowered for word in catalog_words):
        return None

    def _base_response(text: str, action_taken: str, *, metadata_updates: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        metadata = {
            "action_taken": action_taken,
            "state_changed": action_taken.startswith("added_"),
            "affected_systems": ["storm", "sanitary", "water"],
            "catalog_policy": "Catalog entries require explicit source metadata and workspace review status. Catalog presence does not claim standards compliance.",
            "ui_navigation_target": "catalogs",
            "requested_ui_mode": "data",
            "confidence": 0.96,
        }
        if metadata_updates:
            metadata.update(metadata_updates)
        return {
            "intent": "conversation",
            "run_mode": "none",
            "design_prompt": "",
            "needs_clarification": False,
            "assistant_message": text,
            "reason": "Handled by utility catalog chat support.",
            "confidence": 0.96,
            "response_metadata": metadata,
        }

    if "available" in lowered and "pipe" in lowered and ("size" in lowered or "sizes" in lowered):
        network = "storm" if "storm" in lowered else "sanitary" if "sanitary" in lowered else "water" if "water" in lowered else ""
        sizes = GLOBAL_UTILITY_CATALOG_MANAGER.available_pipe_sizes(network=network)
        rows = []
        for key, values in sorted(_safe_dict(sizes.get("sizes_by_network_material")).items()):
            formatted = ", ".join(f'{float(value):g}"' for value in values)
            rows.append(f"{key.replace(':', ' ')}: {formatted}")
        if not rows:
            rows.append("No matching pipe sizes are listed yet.")
        review_ids = [str(item) for item in _safe_list(sizes.get("review_required_catalog_ids")) if str(item)]
        review_text = f" Review required for: {', '.join(review_ids)}." if review_ids else ""
        return _base_response(
            "Available pipe sizes in the catalog: " + " | ".join(rows) + review_text,
            "answered_catalog_pipe_sizes",
            metadata_updates={"catalog_result": sizes},
        )

    if "why" in lowered and "pipe" in lowered and "invalid" in lowered:
        current_pipe = _safe_dict(context.get("selected_pipe") or context.get("current_pipe"))
        if not current_pipe:
            current_pipe = {
                "id": "chat_pipe_check",
                "network": "water" if "water" in lowered else "sanitary" if "sanitary" in lowered else "storm",
            }
            size_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:in|inch|inches|[\"”])", lowered)
            material_match = re.search(r"\b(rcp|pvc|dip|hdpe|cmp)\b", lowered)
            if size_match:
                current_pipe["size_in"] = float(size_match.group(1))
            if material_match:
                current_pipe["material"] = material_match.group(1).upper()
        if not current_pipe.get("material") or not (current_pipe.get("size_in") or current_pipe.get("diameter_in")):
            return _base_response(
                "I need the pipe network, material, and size to explain the catalog issue. Example: why is this water DIP 14 inch pipe invalid?",
                "asked_catalog_pipe_details",
                metadata_updates={"required_missing_inputs": ["pipe network, material, and size"]},
            )
        explanation = GLOBAL_UTILITY_CATALOG_MANAGER.explain_invalid_pipe(current_pipe)
        return _base_response(
            str(explanation.get("message") or "Pipe catalog validation did not return a reason."),
            "answered_invalid_pipe_reason",
            metadata_updates={"catalog_result": explanation},
        )

    if ("add" in lowered or "create" in lowered) and "hydrant" in lowered and "catalog" in lowered:
        source = _safe_dict(context.get("catalog_source") or context.get("utility_catalog_source"))
        if not source:
            return _base_response(
                "I can add a hydrant catalog entry after you provide source_name, source_type, source_reference, jurisdiction or company, reviewed_by, and review_date. I will not infer standards compliance from a hydrant name alone.",
                "blocked_catalog_missing_source_review",
                metadata_updates={
                    "required_missing_inputs": ["catalog source and review metadata"],
                    "state_changed": False,
                },
            )
        payload = {
            "item_id": str(context.get("catalog_item_id") or "water-hydrant-chat"),
            "network": "water",
            "part_type": "hydrant",
            "name": str(context.get("catalog_part_name") or "Hydrant assembly"),
            "compatible_materials": context.get("compatible_materials") or ["DIP"],
            "compatible_sizes_in": context.get("compatible_sizes_in") or [6, 8, 10, 12],
            "source": source,
            "review_status": str(context.get("catalog_review_status") or "needs_review"),
            "limitations": ["Added from chat; review source details before use in validation."],
        }
        result = GLOBAL_UTILITY_CATALOG_MANAGER.add_part_catalog(payload)
        if not result.get("success"):
            return _base_response(
                "I could not add the hydrant catalog entry: " + "; ".join(str(item) for item in _safe_list(result.get("issues"))),
                "blocked_catalog_validation",
                metadata_updates={"catalog_result": result, "state_changed": False},
            )
        return _base_response(
            "Hydrant catalog entry added with its source/review metadata. It is usable for validation only when its review status is accepted for this workspace.",
            "added_hydrant_catalog",
            metadata_updates={"catalog_result": result},
        )

    return None


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

    geometry_edit_response = _drawn_geometry_edit_chat_response(
        decision,
        message=message,
        context=context,
        project_input=project_input,
        latest_result=latest_result,
    )
    if geometry_edit_response is not None:
        return geometry_edit_response

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
    issue_tracker = _safe_dict(meta.get(ISSUE_TRACKER_VERSION)) or build_review_issue_tracker(final_plan, meta=meta)
    if issue_tracker:
        merged[ISSUE_TRACKER_VERSION] = issue_tracker

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
    cleaned = re.sub(r"(?i)\b(find providers for this address|find gis providers for this address|find site data from this address|use online sources if available|find providers|find site data|online sources|from this address)\b", "", message)
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
    packs = [
        safe_str(_safe_dict(item).get("label") or _safe_dict(item).get("pack_id"))
        for item in _safe_list(discovery.get("provider_packs"))
        if safe_str(_safe_dict(item).get("label") or _safe_dict(item).get("pack_id"))
    ]
    if packs:
        lines.append("Selected provider pack(s): " + "; ".join(packs[:4]) + ".")
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
            "what sources are available here",
            "what did you find online",
            "what did you find from online",
            "what online sources",
            "online existing conditions",
        )
    )
    asks_find = any(phrase in normalized for phrase in ("find providers for this address", "find gis providers for this address", "find site data from this address", "find site data", "use online sources if available"))
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
            contours_service_url=safe_str(os.getenv("CIVORA_CONTOURS_ARCGIS_SERVICE_URL")),
            contours_layer_id=int(os.getenv("CIVORA_CONTOURS_ARCGIS_LAYER_ID") or "0"),
            provider_registry=_provider_registry_from_record(record),
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


def _provider_registry_from_record(record: Dict[str, Any]) -> Dict[str, Any]:
    project_input = _safe_dict(record.get("project_input"))
    project_meta = _safe_dict(project_input.get("meta"))
    site_inputs = _safe_dict(project_meta.get("site_inputs"))
    latest_result = _safe_dict(record.get("latest_result"))
    final_plan = _safe_dict(latest_result.get("final_plan"))
    plan_meta = _safe_dict(final_plan.get("meta"))
    discovery = _safe_dict(site_inputs.get("online_existing_conditions_discovery_v1") or plan_meta.get("online_existing_conditions_discovery_v1"))
    registry = (
        _safe_dict(site_inputs.get("local_gis_provider_registry_v1"))
        or _safe_dict(plan_meta.get("local_gis_provider_registry_v1"))
        or _safe_dict(discovery.get("local_gis_provider_registry_v1"))
    )
    built = build_provider_registry(providers=_safe_list(registry.get("providers")) if registry else None)
    if registry:
        built["provider_packs"] = _safe_list(registry.get("provider_packs"))
        built["known_gaps"] = _safe_list(registry.get("known_gaps"))
    return built


def _summarize_provider_registry(registry: Dict[str, Any]) -> str:
    providers = [_safe_dict(item) for item in _safe_list(registry.get("providers")) if _safe_dict(item)]
    configured = [item for item in providers if safe_str(item.get("service_url")) and safe_str(item.get("status")) != "unconfigured"]
    packs = [
        safe_str(_safe_dict(item).get("label") or _safe_dict(item).get("pack_id"))
        for item in _safe_list(registry.get("provider_packs"))
        if safe_str(_safe_dict(item).get("label") or _safe_dict(item).get("pack_id"))
    ]
    if not configured:
        return "No local GIS ArcGIS providers are configured yet. Built-in public context sources may still be listed for floodplain/wetlands, but parcel/building/road/utility/contour providers need local service URLs."
    lines = [
        f"Configured GIS providers: {len(configured)} total. These are context sources and remain review-required.",
    ]
    if packs:
        lines.append("Provider pack(s): " + "; ".join(packs[:4]) + ".")
    for item in configured[:8]:
        freshness = _safe_dict(item.get("freshness"))
        health = _safe_dict(item.get("health"))
        queryable = "queryable" if item.get("queryable") is not False else "not queryable"
        lines.append(
            f"- {safe_str(item.get('source_type'))}: {safe_str(item.get('name') or item.get('id'))}; "
            f"{safe_str(item.get('jurisdiction_level'), 'jurisdiction')}; health {safe_str(health.get('status'), 'unchecked')}; "
            f"freshness {safe_str(freshness.get('status'), 'unknown')}; {queryable}."
        )
    return "\n".join(lines)


def _summarize_national_gis_sources() -> str:
    return (
        "National GIS fallbacks available for candidate discovery: US Census Geocoder for address/location context; "
        "USGS 3DEP EPQS for point elevation where available; FEMA NFHL ArcGIS for floodplain context; "
        "USFWS NWI ArcGIS for wetlands context. These are candidate/review-required context sources only and are not survey/control."
    )


def _extract_arcgis_url(message: str) -> str:
    match = re.search(r"https?://\S+", message)
    return match.group(0).rstrip(".,;)") if match else ""


def _provider_source_type_from_message(message: str) -> str:
    normalized = _normalized_text(message)
    if "building" in normalized:
        return "buildings"
    if "road" in normalized or "right of way" in normalized or "row" in normalized:
        return "roads_row"
    if "utilit" in normalized:
        return "utilities"
    if "contour" in normalized:
        return "contours"
    if "flood" in normalized:
        return "floodplain"
    if "wetland" in normalized:
        return "wetlands"
    return "parcels" if "parcel" in normalized else ""


def _provider_registry_chat_response(
    *,
    message: str,
    record: Optional[Dict[str, Any]],
    project_store: Optional[Any],
    user_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    normalized = _normalized_text(message)
    asks_configured = any(
        phrase in normalized
        for phrase in (
            "what national sources can you use",
            "national sources",
            "what online sources are configured",
            "configured online sources",
            "configured gis sources",
            "provider registry",
            "gis providers",
        )
    )
    asks_health = "check provider health" in normalized or ("provider" in normalized and "health" in normalized)
    asks_add = bool(re.search(r"\b(add|configure)\b", normalized)) and "provider" in normalized
    asks_national = "national sources" in normalized or "federal sources" in normalized
    asks_survey_control = "gis" in normalized and "survey control" in normalized
    missing_source_type = _provider_source_type_from_message(message)
    asks_missing_source = bool(missing_source_type) and (
        "why" in normalized
        and (
            "didn't" in normalized
            or "didnt" in normalized
            or "did not" in normalized
            or "not find" in normalized
            or "missing" in normalized
        )
    )
    if not any((asks_configured, asks_health, asks_add, asks_missing_source, asks_survey_control)):
        return None
    if asks_survey_control:
        return _truthful_decision_update(
            {},
            assistant_message="No. Online GIS data is candidate/review-required context only. It does not establish survey control, boundary control, benchmark datum, utility locate, construction approval, stamp, seal, certification, or engineer-of-record responsibility.",
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=False,
            action_taken="explained_gis_not_survey_control",
            action_blocked_reason="",
            affected_systems=["site", "data"],
            assumptions=[],
            next_best_action="Provide survey/control evidence or an engineer-review package source list before relying on geometry for production decisions.",
            command_payload_updates={"ui_navigation_target": "site_existing", "requested_ui_mode": "setup"},
            outcome="understood_and_answered",
            state_changed=False,
        )
    if asks_national and not record:
        return _truthful_decision_update(
            {},
            assistant_message=_summarize_national_gis_sources(),
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=False,
            action_taken="reported_national_gis_sources",
            action_blocked_reason="",
            affected_systems=["site", "data"],
            assumptions=[],
            next_best_action="Apply an address to select local provider packs and run candidate discovery.",
            outcome="understood_and_answered",
            state_changed=False,
        )
    if not record:
        return _truthful_decision_update(
            {},
            assistant_message="I need a saved project before I can manage local GIS providers.",
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=True,
            action_taken="blocked_missing_provider_registry_project",
            action_blocked_reason="No saved project record is available for GIS provider registry updates.",
            required_missing_inputs=["saved canonical project record"],
            affected_systems=["site", "data"],
            assumptions=[],
            next_best_action="Save or load a project, then ask about configured GIS providers.",
            outcome="understood_but_blocked",
            state_changed=False,
            blocker="No saved project record is available for GIS provider registry updates.",
        )
    registry = _provider_registry_from_record(record)
    if asks_national:
        return _truthful_decision_update(
            {},
            assistant_message=_summarize_national_gis_sources(),
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=False,
            action_taken="reported_national_gis_sources",
            action_blocked_reason="",
            affected_systems=["site", "data"],
            assumptions=[],
            next_best_action="Run online source discovery for the project address to combine local packs with national fallbacks.",
            command_payload_updates={"local_gis_provider_registry_v1": registry, "ui_navigation_target": "site_existing", "requested_ui_mode": "setup"},
            outcome="understood_and_answered",
            state_changed=False,
        )
    if asks_missing_source and not asks_add:
        providers = [
            _safe_dict(item)
            for item in _safe_list(registry.get("providers"))
            if safe_str(_safe_dict(item).get("source_type")) == missing_source_type
        ]
        configured = [
            item
            for item in providers
            if safe_str(item.get("service_url") or _safe_dict(item.get("arcgis")).get("service_url"))
            and safe_str(item.get("status")) != "unconfigured"
        ]
        if not configured:
            reason = f"No configured local GIS provider is registered for {missing_source_type}."
            next_action = f"Add a {missing_source_type} ArcGIS REST provider, then re-apply the address."
        else:
            statuses = ", ".join(
                f"{safe_str(item.get('name') or item.get('id'))}: {safe_str(_safe_dict(item.get('health')).get('status'), 'unchecked')}"
                for item in configured[:4]
            )
            reason = (
                f"{len(configured)} {missing_source_type} provider record(s) are configured, but the last discovery did not return candidate features. "
                f"Health/status: {statuses or 'unchecked'}."
            )
            next_action = "Run provider health and confirm the configured ArcGIS layer has query access and features inside the address search area."
        return _truthful_decision_update(
            {},
            assistant_message=f"{reason} Civora will not report source success when a provider is missing, unhealthy, stale/unknown, or returns no candidates.",
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=False,
            action_taken="explained_missing_local_gis_source",
            action_blocked_reason=reason,
            affected_systems=["site", "data"],
            assumptions=[],
            next_best_action=next_action,
            command_payload_updates={"local_gis_provider_registry_v1": registry, "ui_navigation_target": "site_existing", "requested_ui_mode": "setup"},
            outcome="understood_and_answered",
            state_changed=False,
        )
    if asks_add:
        source_type = _provider_source_type_from_message(message)
        url = _extract_arcgis_url(message)
        if not source_type or not url:
            missing = []
            if not source_type:
                missing.append("provider source type")
            if not url:
                missing.append("ArcGIS REST service URL")
            return _truthful_decision_update(
                {},
                assistant_message="I can add the provider once you include the source type and ArcGIS REST service URL.",
                intent="conversation",
                run_mode="none",
                design_prompt="",
                needs_clarification=True,
                action_taken="blocked_provider_add_missing_config",
                action_blocked_reason="Provider source type or ArcGIS REST service URL is missing.",
                required_missing_inputs=missing,
                affected_systems=["site", "data"],
                assumptions=[],
                next_best_action="Send something like: add a parcel provider https://county.example/arcgis/rest/services/Parcels/MapServer",
                outcome="understood_needs_more_info",
                state_changed=False,
                blocker="Provider source type or ArcGIS REST service URL is missing.",
            )
        providers = _safe_list(registry.get("providers"))
        provider = build_arcgis_provider_record(
            source_type=normalize_source_type(source_type),
            service_url=url,
            layer_id=0,
            name=f"Chat configured {normalize_source_type(source_type).replace('_', '/')} provider",
            jurisdiction_level="jurisdiction",
            notes="Added from chat; layer and freshness should be reviewed.",
        )
        providers.append(provider)
        updated_registry = build_provider_registry(providers=providers)
        latest_result = deepcopy(_safe_dict(record.get("latest_result")))
        final_plan = _safe_dict(latest_result.get("final_plan"))
        meta = _safe_dict(final_plan.get("meta"))
        meta["local_gis_provider_registry_v1"] = updated_registry
        final_plan["meta"] = meta
        latest_result["final_plan"] = final_plan
        project_input = deepcopy(_safe_dict(record.get("project_input")))
        project_meta = _safe_dict(project_input.get("meta"))
        site_inputs = _safe_dict(project_meta.get("site_inputs"))
        site_inputs["local_gis_provider_registry_v1"] = updated_registry
        project_meta["site_inputs"] = site_inputs
        project_input["meta"] = project_meta
        if project_store and user_id:
            _save_project_record(project_store, {**record, "_user_id": user_id}, project_input=project_input, latest_result=latest_result)
        return _truthful_decision_update(
            {},
            assistant_message=f"Added a {provider['source_type']} ArcGIS provider record. It is configured but unchecked, review-required, and not survey-backed.",
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=False,
            action_taken="added_local_gis_provider",
            action_blocked_reason="",
            affected_systems=["site", "data"],
            assumptions=[],
            next_best_action="Run provider health, then re-apply the address to fetch candidates from configured sources.",
            command_payload_updates={"local_gis_provider_registry_v1": updated_registry, "ui_navigation_target": "site_existing", "requested_ui_mode": "setup"},
            outcome="understood_and_executed",
            state_changed=True,
        )
    if asks_health:
        health = check_registry_health(registry)
        return _truthful_decision_update(
            {},
            assistant_message=(
                f"Provider health checked: {health.get('healthy_provider_count', 0)} of {health.get('provider_count', 0)} healthy; "
                f"{health.get('stale_provider_count', 0)} stale/unknown freshness. Health is reachability/config only."
            ),
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=False,
            action_taken="checked_local_gis_provider_health",
            action_blocked_reason="",
            affected_systems=["site", "data"],
            assumptions=[],
            next_best_action="Review failed or stale providers before re-running online source discovery.",
            command_payload_updates={"local_gis_provider_registry_health_v1": health, "ui_navigation_target": "site_existing", "requested_ui_mode": "setup"},
            outcome="understood_and_answered",
            state_changed=False,
        )
    return _truthful_decision_update(
        {},
        assistant_message=_summarize_provider_registry(registry),
        intent="conversation",
        run_mode="none",
        design_prompt="",
        needs_clarification=False,
        action_taken="reported_local_gis_provider_registry",
        action_blocked_reason="",
        affected_systems=["site", "data"],
        assumptions=[],
        next_best_action="Add missing parcel/building/road/utility/contour providers or check provider health.",
        command_payload_updates={"local_gis_provider_registry_v1": registry, "ui_navigation_target": "site_existing", "requested_ui_mode": "setup"},
        outcome="understood_and_answered",
        state_changed=False,
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


def _issue_selector_from_message(normalized: str) -> str:
    text = normalized
    for phrase in (
        "resolve this issue",
        "resolve issue",
        "reopen issue",
        "waive issue",
        "assign this issue",
        "assign issue",
        "assign",
        "put issue in review",
        "mark issue in review",
        "show review history",
        "review history",
        "show",
        "what issues are",
        "what issue is",
        "what does the engineer need to review",
        "who needs to review this",
    ):
        text = text.replace(phrase, " ")
    text = re.sub(r"\b(open|opened|resolved|reopened|grading|drainage|storm|water|sanitary|roadway|utility|utilities|issue|issues|blockers?|review|required|need|needs|engineer|reviewer|owner|admin|editor|viewer|to|the|a|an|are|is|what|does|who|this)\b", " ", text)
    return " ".join(text.split())


def _review_history_summary(meta: Dict[str, Any], tracker: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    workflow = _safe_dict(metadata.get("workflow"))
    version_history = _safe_dict(workflow.get("version_history"))
    candidate_inbox = build_candidate_review_inbox(meta)
    candidate_audit = _safe_list(meta.get("candidate_review_decisions_v1"))
    for candidate in _safe_list(candidate_inbox.get("candidates")):
        candidate_audit.extend(_safe_list(_safe_dict(candidate).get("audit_trail")))
    issue_events: List[Dict[str, Any]] = []
    for issue in _safe_list(tracker.get("issues")):
        rec = _safe_dict(issue)
        for event in _safe_list(rec.get("history")):
            event_rec = _safe_dict(event)
            issue_events.append(
                {
                    "issue_id": safe_str(rec.get("issue_id")),
                    "title": safe_str(rec.get("title")),
                    "action": safe_str(event_rec.get("action")),
                    "actor": safe_str(event_rec.get("actor")),
                    "status": safe_str(event_rec.get("status")),
                    "created_at": event_rec.get("created_at"),
                    "note": safe_str(event_rec.get("note")),
                }
            )
    return {
        "version": "project_review_history_v1",
        "issue_events": issue_events[-20:],
        "candidate_audit": candidate_audit[-20:],
        "version_history": version_history,
        "review_package_history": _safe_list(version_history.get("review_package_history")),
        "truth_label": "Review history is workflow/audit evidence only; it is not Civora approval, certification, stamp, seal, or engineer-of-record action.",
    }


def _issue_tracker_chat_response(
    *,
    message: str,
    record: Optional[Dict[str, Any]],
    project_store: Optional[Any],
    user_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    normalized = _normalized_text(message)
    asks_open = any(phrase in normalized for phrase in ("what issues are open", "open issues", "what issue is open"))
    asks_engineer_queue = "what does the engineer need to review" in normalized or "engineer need to review" in normalized
    asks_who_reviews = "who needs to review this" in normalized or "who needs to review" in normalized
    asks_review_history = "show review history" in normalized or "review history" in normalized
    asks_version_changes = "what changed since last version" in normalized or "changed since last version" in normalized
    asks_drainage = "drainage" in normalized and ("blocker" in normalized or "issue" in normalized)
    wants_resolve = "resolve" in normalized and "issue" in normalized
    wants_reopen = "reopen" in normalized and ("issue" in normalized or "grading" in normalized or "drainage" in normalized)
    wants_waive = "waive" in normalized and "issue" in normalized
    wants_assign = "assign" in normalized and "issue" in normalized
    wants_in_review = ("in review" in normalized or "review this issue" in normalized) and "issue" in normalized
    if not any((asks_open, asks_engineer_queue, asks_who_reviews, asks_review_history, asks_version_changes, asks_drainage, wants_resolve, wants_reopen, wants_waive, wants_assign, wants_in_review)):
        return None
    if not record:
        return _truthful_decision_update(
            {},
            assistant_message="I need a saved project result before I can show review issues.",
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=True,
            action_taken="blocked_missing_issue_tracker_project",
            action_blocked_reason="No saved project record is available for review issues.",
            required_missing_inputs=["saved project with review evidence"],
            affected_systems=["review"],
            assumptions=[],
            next_best_action="Save or load a project result, then ask for open issues again.",
            outcome="understood_but_blocked",
            state_changed=False,
            blocker="No saved project record is available for review issues.",
        )
    latest_result = deepcopy(_safe_dict(record.get("latest_result")))
    final_plan = _safe_dict(latest_result.get("final_plan"))
    if not final_plan:
        return _truthful_decision_update(
            {},
            assistant_message="I need a planner result before I can build the review issue tracker.",
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=True,
            action_taken="blocked_missing_issue_tracker_plan",
            action_blocked_reason="Saved project has no final plan.",
            required_missing_inputs=["saved planner result"],
            affected_systems=["review"],
            assumptions=[],
            next_best_action="Run or load a design first, then ask for issues.",
            outcome="understood_but_blocked",
            state_changed=False,
            blocker="Saved project has no final plan.",
        )
    meta = _safe_dict(final_plan.get("meta"))
    project_metadata = _safe_dict(record.get("metadata"))
    tracker = _safe_dict(meta.get(ISSUE_TRACKER_VERSION)) or build_review_issue_tracker(final_plan, meta=meta)
    action = ""
    if wants_resolve:
        action = "resolve"
    elif wants_reopen:
        action = "reopen"
    elif wants_waive:
        action = "waive"
    elif wants_assign:
        action = "assign"
    elif wants_in_review:
        action = "in_review"
    discipline = ""
    for candidate in ("grading", "drainage", "storm", "water", "sanitary", "roadway", "utilities"):
        if candidate in normalized:
            discipline = "drainage" if candidate == "storm" else candidate
            break
    selector = _issue_selector_from_message(normalized)
    assigned_to = ""
    if wants_assign:
        assigned_to = normalized.rsplit(" to ", 1)[-1].strip() if " to " in normalized else "reviewer"
        assigned_to = assigned_to or "reviewer"
    if asks_version_changes:
        version_history = _safe_dict(_safe_dict(project_metadata.get("workflow")).get("version_history"))
        comparison = _safe_dict(version_history.get("latest_comparison"))
        if comparison:
            assistant = (
                "Since the last project version: "
                f"{len(_safe_list(comparison.get('added_objects')))} added object(s), "
                f"{len(_safe_list(comparison.get('removed_objects')))} removed, "
                f"{len(_safe_list(comparison.get('changed_objects')))} changed; "
                f"{len(_safe_list(comparison.get('added_blockers')))} blocker(s) added, "
                f"{len(_safe_list(comparison.get('removed_blockers')))} removed; "
                f"{len(_safe_list(comparison.get('changed_quantities')))} quantity change(s) recorded."
            )
        else:
            assistant = "I do not have two project version snapshots to compare yet."
        return _truthful_decision_update(
            {},
            assistant_message=assistant,
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=False,
            action_taken="reported_project_version_comparison",
            action_blocked_reason="",
            affected_systems=["review"],
            assumptions=[],
            next_best_action="Generate or save another major project update to create a new comparison snapshot.",
            command_payload_updates={"project_version_history_v1": version_history, "ui_navigation_target": "reports", "requested_ui_mode": "review"},
            outcome="understood_and_answered",
            state_changed=False,
        )
    if asks_review_history:
        history = _review_history_summary(meta, tracker, project_metadata)
        assistant = (
            f"Review history: {len(_safe_list(history.get('issue_events')))} issue event(s), "
            f"{len(_safe_list(history.get('candidate_audit')))} candidate decision(s), "
            f"{len(_safe_list(_safe_dict(history.get('version_history')).get('snapshots')))} version snapshot(s), "
            f"{len(_safe_list(history.get('review_package_history')))} package artifact(s)."
        )
        return _truthful_decision_update(
            {},
            assistant_message=assistant,
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=False,
            action_taken="reported_project_review_history",
            action_blocked_reason="",
            affected_systems=["review"],
            assumptions=[],
            next_best_action="Use the Review/Admin surfaces to inspect the linked audit records.",
            command_payload_updates={"project_review_history_v1": history, "ui_navigation_target": "reports", "requested_ui_mode": "review"},
            outcome="understood_and_answered",
            state_changed=False,
        )
    if action:
        matches = select_review_issues(tracker, selector, discipline=discipline)
        if not matches and discipline:
            matches = select_review_issues(tracker, discipline=discipline, status="open")
        if not matches and not selector and not discipline:
            matches = select_review_issues(tracker, status="open")
        if len(matches) != 1:
            return _truthful_decision_update(
                {},
                assistant_message=(
                    "I found multiple matching review issues. Please include an issue id or a more specific discipline/title."
                    if matches
                    else "I could not find a matching review issue."
                ),
                intent="conversation",
                run_mode="none",
                design_prompt="",
                needs_clarification=True,
                action_taken="blocked_ambiguous_review_issue_update" if matches else "blocked_review_issue_not_found",
                action_blocked_reason="Review issue update needs exactly one matching issue.",
                required_missing_inputs=["specific review issue id or title"],
                affected_systems=["review"],
                assumptions=[],
                next_best_action="Ask “what issues are open?” and include the issue id in the follow-up.",
                command_payload_updates={ISSUE_TRACKER_VERSION: tracker, "ui_navigation_target": "reports", "requested_ui_mode": "review"},
                outcome="understood_but_blocked",
                state_changed=False,
                blocker="Review issue update needs exactly one matching issue.",
            )
        if not (project_store and user_id):
            return None
        matched = _safe_dict(matches[0])
        update = apply_review_issue_update(
            meta,
            action=action,
            issue_id=safe_str(matched.get("issue_id")),
            actor=user_id,
            note=message,
            discipline=discipline,
            assigned_to=assigned_to,
        )
        meta = _safe_dict(update.get("updated_meta"))
        tracker = _safe_dict(update.get(ISSUE_TRACKER_VERSION))
        final_plan["meta"] = meta
        latest_result["final_plan"] = final_plan
        _save_project_record(
            project_store,
            {**record, "_user_id": user_id},
            project_input=deepcopy(_safe_dict(record.get("project_input"))),
            latest_result=latest_result,
        )
        status = safe_str(update.get("status"))
        return _truthful_decision_update(
            {},
            assistant_message=(
                f"Updated {safe_str(matched.get('issue_id'))} to {status}. "
                "This changes the issue workflow only; review requirements and field-use boundaries remain visible."
            ),
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=False,
            action_taken=f"{action}_review_issue",
            action_blocked_reason="",
            affected_systems=[safe_str(matched.get("discipline"), "review")],
            assumptions=[],
            next_best_action="Review the remaining open issues before relying on outputs.",
            command_payload_updates={ISSUE_TRACKER_VERSION: tracker, "ui_navigation_target": "reports", "requested_ui_mode": "review"},
            outcome="understood_and_executed",
            state_changed=True,
        )

    if asks_engineer_queue:
        visible = [_safe_dict(item) for item in _safe_list(tracker.get("engineer_review_queue"))]
        heading = "Engineer review queue"
    elif asks_who_reviews:
        visible = [_safe_dict(item) for item in _safe_list(tracker.get("engineer_review_queue"))]
        heading = "Review assignments"
    elif asks_drainage:
        visible = select_review_issues(tracker, discipline="drainage", status="open")
        heading = "Drainage blockers"
    else:
        visible = select_review_issues(tracker, status="open")
        heading = "Open review issues"
    if visible:
        lines = [
            f"{safe_str(item.get('issue_id'))}: {safe_str(item.get('severity'))} {safe_str(item.get('discipline'))} - {safe_str(item.get('title'))} ({safe_str(item.get('assigned_to') or item.get('assigned_role') or 'project_reviewer')})"
            for item in visible[:8]
        ]
        assistant = f"{heading}: {len(visible)} item{'s' if len(visible) != 1 else ''}.\n" + "\n".join(f"- {line}" for line in lines)
    else:
        assistant = f"{heading}: no matching open items are recorded. Review-required boundaries still apply to generated outputs."
    return _truthful_decision_update(
        {},
        assistant_message=assistant,
        intent="conversation",
        run_mode="none",
        design_prompt="",
        needs_clarification=False,
        action_taken="reported_review_issue_tracker",
        action_blocked_reason="",
        affected_systems=["review"],
        assumptions=[],
        next_best_action="Resolve, reopen, waive with a review-required record, or assign visible issues as work progresses.",
        command_payload_updates={ISSUE_TRACKER_VERSION: tracker, "ui_navigation_target": "reports", "requested_ui_mode": "review"},
        outcome="understood_and_answered",
        state_changed=False,
    )


def _design_alternatives_chat_response(
    *,
    message: str,
    record: Optional[Dict[str, Any]],
    project_store: Optional[Any],
    user_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    normalized = _normalized_text(message)
    asks_show = any(
        phrase in normalized
        for phrase in (
            "show me 3 options",
            "show me options",
            "show options",
            "design alternatives",
            "layout alternatives",
            "parking alternatives",
            "road alternatives",
            "basin alternatives",
            "utility alternatives",
            "grading alternatives",
        )
    )
    asks_compare = any(phrase in normalized for phrase in ("compare these", "compare options", "compare alternatives"))
    asks_use = any(phrase in normalized for phrase in ("use option", "choose option", "merge option", "select option"))
    asks_revise = any(phrase in normalized for phrase in ("make another layout", "another layout", "revise option", "make another option"))
    if not any((asks_show, asks_compare, asks_use, asks_revise)):
        return None
    if not record:
        return _truthful_decision_update(
            {},
            assistant_message="I need a saved project with a planner result before I can create design alternatives.",
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=True,
            action_taken="blocked_missing_alternatives_project",
            action_blocked_reason="No saved project record is available for alternatives.",
            required_missing_inputs=["saved project with planner result"],
            affected_systems=["layout", "grading", "drainage", "utilities"],
            assumptions=[],
            next_best_action="Save or load a project result, then ask for alternatives again.",
            outcome="understood_but_blocked",
            state_changed=False,
            blocker="No saved project record is available for alternatives.",
        )
    latest_result = deepcopy(_safe_dict(record.get("latest_result")))
    final_plan = _safe_dict(latest_result.get("final_plan"))
    if not final_plan:
        return _truthful_decision_update(
            {},
            assistant_message="I need a saved planner result before I can compare layout alternatives.",
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=True,
            action_taken="blocked_missing_alternatives_plan",
            action_blocked_reason="Saved project has no final plan.",
            required_missing_inputs=["saved planner result"],
            affected_systems=["layout"],
            assumptions=[],
            next_best_action="Run or load a design first, then ask for alternatives.",
            outcome="understood_but_blocked",
            state_changed=False,
            blocker="Saved project has no final plan.",
        )
    meta = _safe_dict(final_plan.get("meta"))
    requested_count = requested_alternative_count_from_message(message)
    option_number = option_number_from_message(message)
    state_changed = False
    action_taken = "reported_design_alternatives"

    try:
        if asks_revise:
            result = append_revised_design_alternative(
                meta,
                basis_option_number=option_number,
                reviewer_id=user_id or "user",
                reason=message,
            )
            meta = _safe_dict(result.get("updated_meta"))
            action_taken = "revised_design_alternative"
            state_changed = True
        elif asks_use:
            if not option_number:
                return _truthful_decision_update(
                    {},
                    assistant_message="Which option should I use as the draft direction? Say something like “use option 2.”",
                    intent="conversation",
                    run_mode="none",
                    design_prompt="",
                    needs_clarification=True,
                    action_taken="blocked_missing_alternative_option",
                    action_blocked_reason="No option number was provided.",
                    required_missing_inputs=["option number"],
                    affected_systems=["layout"],
                    assumptions=[],
                    next_best_action="Choose one option number from the Alternatives panel.",
                    outcome="understood_but_blocked",
                    state_changed=False,
                    blocker="No option number was provided.",
                )
            result = select_design_alternative(
                meta,
                option_number=option_number,
                action="merge" if "merge" in normalized else "choose",
                reviewer_id=user_id or "user",
                reason=message,
            )
            meta = _safe_dict(result.get("updated_meta"))
            action_taken = "selected_design_alternative"
            state_changed = True
        else:
            alternatives = _safe_dict(meta.get(ALTERNATIVES_VERSION)) or build_design_alternatives(meta, requested_count=requested_count)
            meta[ALTERNATIVES_VERSION] = alternatives
            action_taken = "compared_design_alternatives" if asks_compare else "generated_design_alternatives"
            state_changed = asks_show or not _safe_dict(final_plan.get("meta")).get(ALTERNATIVES_VERSION)
        alternatives_record = _safe_dict(meta.get(ALTERNATIVES_VERSION)) or build_design_alternatives(meta, requested_count=requested_count)
        meta[ALTERNATIVES_VERSION] = alternatives_record
        comparison = compare_design_alternatives(meta, requested_count=requested_count)
    except ValueError as exc:
        return _truthful_decision_update(
            {},
            assistant_message=str(exc),
            intent="conversation",
            run_mode="none",
            design_prompt="",
            needs_clarification=True,
            action_taken="blocked_design_alternative_action",
            action_blocked_reason=str(exc),
            required_missing_inputs=["valid alternative option"],
            affected_systems=["layout"],
            assumptions=[],
            next_best_action="Generate alternatives and choose a visible option number.",
            outcome="understood_but_blocked",
            state_changed=False,
            blocker=str(exc),
        )

    if state_changed and project_store and user_id:
        final_plan["meta"] = meta
        latest_result["final_plan"] = final_plan
        _save_project_record(
            project_store,
            {**record, "_user_id": user_id},
            project_input=deepcopy(_safe_dict(record.get("project_input"))),
            latest_result=latest_result,
        )
    rows = _safe_list(comparison.get("rows"))
    if asks_use:
        selected = _safe_dict(alternatives_record.get("selected_alternative"))
        assistant = (
            f"I selected {safe_str(selected.get('label'), 'the requested option')} as a draft review direction. "
            "It remains a review-required concept and still depends on accepted inputs before deeper reliance."
        )
    elif asks_revise:
        assistant = (
            "I added another layout concept for comparison. "
            "It is review-required and should be compared before you choose or merge it."
        )
    else:
        lines = [
            f"Option {int(row.get('option_number') or 0)}: {safe_str(row.get('label'))}, score {safe_float(row.get('review_score'), 0):.0f}, {safe_str((_safe_list(row.get('top_tradeoffs')) or ['review required'])[0])}"
            for row in rows[:requested_count]
        ]
        assistant = (
            f"Here are {len(lines)} review-required design alternatives:\n"
            + "\n".join(f"- {line}" for line in lines)
            + "\nUse compare, revise, or choose one as a draft direction. These concepts are not field-use documents."
        )
    return _truthful_decision_update(
        {},
        assistant_message=assistant,
        intent="conversation",
        run_mode="none",
        design_prompt="",
        needs_clarification=False,
        action_taken=action_taken,
        action_blocked_reason="",
        affected_systems=["parking", "roads", "drainage", "utilities", "grading", "layout"],
        assumptions=["Alternatives are concept-level unless backed by accepted project inputs."],
        next_best_action="Review tradeoffs, compare costs/quantities where available, then choose or revise a concept.",
        command_payload_updates={
            ALTERNATIVES_VERSION: alternatives_record,
            "design_alternatives_comparison_v1": comparison,
            "ui_navigation_target": "reports",
            "requested_ui_mode": "review",
        },
        outcome="understood_and_executed" if state_changed else "understood_and_answered",
        state_changed=state_changed,
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


def _plan_pdf_text(meta: Dict[str, Any], bucket: str, limit: int = 8) -> List[str]:
    analysis = _safe_dict(meta.get("plan_pdf_analysis_v1"))
    values: List[str] = []
    for item in _safe_list(_safe_dict(analysis.get("classifications")).get(bucket))[:limit]:
        text = safe_str(_safe_dict(item).get("text"))
        if text and text not in values:
            values.append(text)
    return values


def _plan_pdf_elements(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [_safe_dict(item) for item in _safe_list(_safe_dict(meta.get("plan_pdf_editable_sheet_v1")).get("elements")) if _safe_dict(item)]


def _plan_pdf_target_element(meta: Dict[str, Any], message: str) -> Optional[Dict[str, Any]]:
    normalized = _normalized_text(message)
    elements = _plan_pdf_elements(meta)
    typed = {
        "owner": ["title_block_field"],
        "title block": ["title_block_field"],
        "elevation": ["elevation_callout"],
        "elev": ["elevation_callout"],
        "label": ["text_label"],
        "note": ["note"],
        "detail": ["detail_block"],
        "dimension": ["dimension"],
    }
    for phrase, types in typed.items():
        if phrase not in normalized:
            continue
        for element in elements:
            if safe_str(element.get("type")) in types or phrase in _normalized_text(safe_str(element.get("text"))):
                return element
    return elements[0] if elements else None


def _plan_pdf_replacement(message: str) -> str:
    text = str(message or "").strip()
    quoted = re.findall(r"[\"']([^\"']{1,180})[\"']", text)
    if quoted:
        return quoted[-1].strip()
    match = re.search(r"\b(?:to|as)\s+(.{1,180})$", text, re.IGNORECASE)
    return match.group(1).strip(" .") if match else ""


def _plan_pdf_move_target(message: str) -> Dict[str, float]:
    match = re.search(
        r"\b(?:to|target|at)\s*(?:x0?\s*)?(-?\d+(?:\.\d+)?)\s*[,/ ]+\s*(?:y0?\s*)?(-?\d+(?:\.\d+)?)\b",
        str(message or ""),
        re.IGNORECASE,
    )
    if not match:
        return {}
    return {"x0": float(match.group(1)), "y0": float(match.group(2))}


def _plan_pdf_changed_lines(meta: Dict[str, Any]) -> List[str]:
    report = plan_pdf_report(meta)
    changed = _safe_dict(report.get("changed_elements"))
    elements = [_safe_dict(item) for item in _safe_list(changed.get("elements"))]
    if not elements:
        return ["No PDF-derived sheet elements have been changed yet."]
    lines = [
        (
            f"{int(changed.get('changed_count') or len(elements))} changed PDF-derived element(s): "
            f"{int(changed.get('text_edit_count') or 0)} text edit(s), "
            f"{int(changed.get('moved_count') or 0)} move(s), "
            f"{int(changed.get('accepted_count') or 0)} accepted, "
            f"{int(changed.get('rejected_count') or 0)} rejected."
        )
    ]
    for item in elements[:8]:
        before = safe_str(item.get("original_text")) or "(blank)"
        after = safe_str(item.get("text")) or "(blank)"
        moved = " moved" if item.get("moved") else ""
        status = safe_str(item.get("review_status"), "pending")
        lines.append(f"- {safe_str(item.get('type'), 'element')} {safe_str(item.get('element_id'))}: {before} -> {after}; {status}{moved}")
    return lines


def _plan_pdf_unreadable_lines(meta: Dict[str, Any]) -> List[str]:
    analysis = _safe_dict(meta.get("plan_pdf_analysis_v1"))
    ocr = _safe_dict(analysis.get("ocr"))
    unreadable = [_safe_dict(item) for item in _safe_list(ocr.get("unreadable_regions"))]
    blockers = [safe_str(item) for item in _safe_list(analysis.get("blockers")) if safe_str(item)]
    lines = ["Unreadable or blocked PDF text:"]
    if unreadable:
        for item in unreadable[:8]:
            page = int(item.get("page_index") or 0) + 1
            raw = safe_str(item.get("raw_text")) or "(blank OCR fragment)"
            score = item.get("confidence_score")
            score_text = f"{float(score):.2f}" if isinstance(score, (int, float)) else "unknown"
            lines.append(f"- Page {page}: {raw} at OCR confidence {score_text}; reviewer verification required.")
    else:
        lines.append("- No low-confidence OCR regions are saved.")
    for blocker in blockers[:8]:
        if "ocr" in blocker or "raster_preview" in blocker:
            lines.append(f"- {blocker}")
    return lines


def _plan_pdf_ocr_behavior_line(meta: Dict[str, Any]) -> str:
    analysis = _safe_dict(meta.get("plan_pdf_analysis_v1"))
    ocr = _safe_dict(analysis.get("ocr"))
    engine = _safe_dict(ocr.get("engine"))
    status = safe_str(ocr.get("status"), "unknown")
    engine_name = safe_str(engine.get("engine"), "unknown")
    available = "available" if engine.get("available") else "blocked"
    return f"OCR status: {status}; engine {engine_name} is {available}; OCR results are review-required."


def _plan_pdf_cad_entity_lines(meta: Dict[str, Any]) -> List[str]:
    model = build_cad_entity_model(meta)
    entities = [
        _safe_dict(item)
        for item in _safe_list(model.get("entities"))
        if safe_str(_safe_dict(item).get("source")) in {"plan_pdf_extraction", "plan_pdf_vector_extraction"}
    ]
    if not entities:
        return ["No PDF elements have become CAD entities yet."]
    lines = [f"{len(entities)} PDF-derived CAD entit(ies) are present in cad_entity_model_v1:"]
    for entity in entities[:12]:
        source_pdf = _safe_dict(entity.get("source_pdf"))
        label = safe_str(entity.get("original_text") or _safe_dict(entity.get("geometry")).get("text")) or safe_str(entity.get("type"), "entity")
        page = int(source_pdf.get("page") or entity.get("page") or 0)
        lines.append(
            f"- {safe_str(entity.get('id'))}: {safe_str(entity.get('type'))} {safe_str(entity.get('pdf_annotation_kind'))} on page {page}; {label}; {safe_str(entity.get('source_confidence'), PLAN_PDF_SOURCE_CONFIDENCE)}."
        )
    lines.append("All PDF-derived CAD entities remain imported_pdf_review_required, review-only, not survey-backed, and not construction-release evidence.")
    return lines


def _plan_pdf_unconverted_cad_lines(meta: Dict[str, Any]) -> List[str]:
    analysis = _safe_dict(meta.get("plan_pdf_analysis_v1"))
    sheet = _safe_dict(meta.get("plan_pdf_editable_sheet_v1"))
    converted_element_ids = {safe_str(_safe_dict(item).get("linked_pdf_element_id")) for item in plan_pdf_elements_to_cad_entities(meta)}
    lines = ["Unreadable or unconverted PDF-to-CAD items:"]
    for element in _safe_list(sheet.get("elements")):
        rec = _safe_dict(element)
        element_id = safe_str(rec.get("element_id"))
        if element_id in converted_element_ids:
            continue
        reason = "not converted"
        if safe_str(rec.get("type")) == "stamp_or_seal_source_imagery":
            reason = "protected professional mark imagery is source-only and never approval evidence"
        elif safe_str(rec.get("type")) == "linework_geometry_candidate":
            reason = "; ".join(safe_str(item) for item in _safe_list(rec.get("blockers")) if safe_str(item)) or "vector geometry extraction is unavailable"
        elif not _safe_dict(rec.get("bbox") or rec.get("original_bbox")):
            reason = "missing reliable source bounds"
        lines.append(f"- {safe_str(rec.get('type'), 'element')} {element_id}: {reason}.")
    blockers = [safe_str(item) for item in _safe_list(analysis.get("blockers")) if safe_str(item)]
    for blocker in blockers[:8]:
        if "ocr" in blocker or "raster" in blocker or "vector" in blocker:
            lines.append(f"- blocker: {blocker}")
    if len(lines) == 1:
        lines.append("- No unconverted PDF sheet elements are saved.")
    return lines


def _plan_pdf_chat_response(
    *,
    message: str,
    record: Optional[Dict[str, Any]],
    project_store: Optional[Any],
    user_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    normalized = _normalized_text(message)
    asks_pdf = any(
        phrase in normalized
        for phrase in (
            "plan pdf",
            "this plan",
            "on this plan",
            "pdf",
            "owner block",
            "title block",
            "extract the dimensions",
            "what scale",
            "what can you not read",
            "what could you not read",
            "unreadable text",
            "read this scanned plan",
            "scanned plan",
            "image-only pdf",
            "image only pdf",
            "find all elevations",
            "all elevations",
            "make this detail editable",
            "turn this pdf into editable plan objects",
            "pool deck elevation",
            "move this label",
            "what changed",
            "turn pdf labels into cad text",
            "pdf labels into cad text",
            "convert plan dimensions to cad annotations",
            "what pdf elements became cad entities",
            "why can t this raster line become cad",
            "why can't this raster line become cad",
            "show unreadable unconverted pdf items",
            "unconverted pdf items",
        )
    )
    if "since last version" in normalized:
        asks_pdf = False
    if not asks_pdf:
        return None
    if not record:
        return _truthful_decision_update(
            {},
            assistant_message="I need a saved project with an uploaded plan PDF before I can answer PDF understanding questions.",
            intent="plan_pdf_understanding",
            run_mode="none",
            needs_clarification=True,
            action_taken="blocked_missing_plan_pdf_project",
            action_blocked_reason="No saved project record is available.",
            required_missing_inputs=["saved project with plan PDF analysis"],
            affected_systems=["plan_pdf_understanding", "editable_sheet"],
            next_best_action="Upload a plan PDF into a saved project, then ask again.",
            confidence=0.3,
            blocker="No saved project record is available.",
        )
    latest_result = _safe_dict(record.get("latest_result"))
    final_plan = _safe_dict(latest_result.get("final_plan"))
    meta = _safe_dict(final_plan.get("meta"))
    analysis = _safe_dict(meta.get("plan_pdf_analysis_v1"))
    if not analysis:
        return _truthful_decision_update(
            {},
            assistant_message="I do not have a plan PDF analysis saved on this project yet.",
            intent="plan_pdf_understanding",
            run_mode="none",
            needs_clarification=True,
            action_taken="blocked_missing_plan_pdf_analysis",
            action_blocked_reason="No plan_pdf_analysis_v1 record is attached to the project.",
            required_missing_inputs=["uploaded plan PDF"],
            affected_systems=["plan_pdf_understanding", "editable_sheet"],
            next_best_action="Upload a plan PDF from the Data panel.",
            confidence=0.35,
            blocker="No plan_pdf_analysis_v1 record is attached to the project.",
        )
    wants_move = "move" in normalized
    if wants_move and "to" not in normalized and "target" not in normalized and " at " not in f" {normalized} ":
        return _truthful_decision_update(
            {},
            assistant_message="I can move a PDF-derived label only with an explicit target x0/y0. Give me PDF coordinates like: move this label to x0 120, y0 640.",
            intent="plan_pdf_edit",
            run_mode="none",
            needs_clarification=True,
            action_taken="blocked_pdf_move_missing_target",
            action_blocked_reason="Moving a PDF-derived element requires explicit target x0/y0 coordinates.",
            required_missing_inputs=["explicit PDF coordinate target"],
            affected_systems=["editable_sheet"],
            next_best_action="Select a PDF-derived label and provide target x0/y0 coordinates.",
            command_payload_updates={"source_confidence": PLAN_PDF_SOURCE_CONFIDENCE},
            confidence=0.55,
            blocker="Moving a PDF-derived element requires explicit target x0/y0 coordinates.",
        )
    wants_change_summary = "what changed" in normalized
    wants_edit = (
        not wants_change_summary
        and any(token in normalized for token in ("change", "edit", "accept", "reject", "make this detail editable", "move"))
    )
    if wants_edit and project_store and user_id:
        element = _plan_pdf_target_element(meta, message)
        if element:
            updates: Dict[str, Any] = {}
            replacement = _plan_pdf_replacement(message)
            move_target = _plan_pdf_move_target(message)
            if wants_move and move_target:
                updates["move_target"] = move_target
            elif "reject" in normalized:
                updates["review_status"] = "rejected"
            elif "accept" in normalized or "make this detail editable" in normalized:
                updates["review_status"] = "accepted"
            elif replacement:
                updates["text"] = replacement
            if not updates:
                return _truthful_decision_update(
                    {},
                    assistant_message=(
                        "I found a PDF-derived element to edit, but I need the exact replacement text or value first. "
                        "For example: change pool deck elevation to \"POOL DECK ELEVATION 103.00\". "
                        "Any edit remains imported_pdf_review_required and must be reviewed before use."
                    ),
                    intent="plan_pdf_edit",
                    run_mode="none",
                    needs_clarification=True,
                    action_taken="blocked_pdf_edit_missing_replacement",
                    action_blocked_reason="PDF-derived edit request did not include replacement text or a supported review action.",
                    required_missing_inputs=["exact replacement text or value"],
                    affected_systems=["editable_sheet"],
                    next_best_action="Provide exact replacement text or use the sheet inspector Save/Accept/Reject controls.",
                    command_payload_updates={"source_confidence": PLAN_PDF_SOURCE_CONFIDENCE},
                    confidence=0.55,
                    blocker="PDF-derived edit request needs exact replacement text or value.",
                )
            if updates:
                try:
                    updated_meta = update_editable_sheet_element(meta, safe_str(element.get("element_id")), updates)
                    updated_latest = deepcopy(latest_result)
                    updated_plan = deepcopy(final_plan)
                    updated_plan["meta"] = updated_meta
                    updated_latest["final_plan"] = updated_plan
                    _save_project_record(
                        project_store,
                        {**record, "_user_id": user_id},
                        project_input=deepcopy(_safe_dict(record.get("project_input"))),
                        latest_result=updated_latest,
                    )
                except Exception as exc:
                    return _truthful_decision_update(
                        {},
                        assistant_message=f"I could not update that PDF-derived element: {exc}",
                        intent="plan_pdf_edit",
                        run_mode="none",
                        needs_clarification=False,
                        action_taken="blocked_pdf_element_update_failed",
                        action_blocked_reason=str(exc),
                        affected_systems=["editable_sheet"],
                        next_best_action="Use another extracted element or update it from the sheet inspector.",
                        command_payload_updates={"source_confidence": PLAN_PDF_SOURCE_CONFIDENCE},
                        confidence=0.4,
                        blocker=str(exc),
                    )
                changed = safe_str(updates.get("text")) or safe_str(updates.get("review_status")) or "new target location"
                return _truthful_decision_update(
                    {},
                    assistant_message=(
                        f"Updated PDF-derived element {safe_str(element.get('element_id'))} to {changed}. "
                        "It remains review-required imported PDF evidence, not survey-backed field evidence."
                    ),
                    intent="plan_pdf_edit",
                    run_mode="plan_pdf_editable_sheet_update",
                    needs_clarification=False,
                    action_taken="updated_pdf_derived_sheet_element",
                    affected_systems=["editable_sheet", "candidate_review_inbox"],
                    next_best_action="Review and accept/reject the updated extraction candidate before relying on it.",
                    command_payload_updates={"ui_navigation_target": "data", "requested_ui_mode": "data", "source_confidence": PLAN_PDF_SOURCE_CONFIDENCE},
                    state_changed=True,
                    referenced_object_ids=[safe_str(element.get("element_id"))],
                    confidence=0.72,
                )
    summary = _safe_dict(analysis.get("summary"))
    blockers = [safe_str(item) for item in _safe_list(analysis.get("blockers")) if safe_str(item)]
    wants_pdf_to_cad = (
        "cad" in normalized
        and "pdf" in normalized
        and any(phrase in normalized for phrase in ("turn", "convert", "became", "entities", "annotations", "labels"))
    )
    wants_unconverted = "unconverted" in normalized or ("unreadable" in normalized and "cad" in normalized)
    wants_raster_line_reason = "raster line" in normalized and "cad" in normalized
    if wants_pdf_to_cad and project_store and user_id and ("turn" in normalized or "convert" in normalized):
        converted = plan_pdf_elements_to_cad_entities(meta)
        updated_latest = deepcopy(latest_result)
        updated_plan = deepcopy(final_plan)
        updated_meta = deepcopy(meta)
        updated_meta[CAD_ENTITY_MODEL_VERSION] = build_cad_entity_model(updated_meta)
        updated_plan["meta"] = updated_meta
        updated_latest["final_plan"] = updated_plan
        _save_project_record(
            project_store,
            {**record, "_user_id": user_id},
            project_input=deepcopy(_safe_dict(record.get("project_input"))),
            latest_result=updated_latest,
        )
        lines = _plan_pdf_cad_entity_lines(updated_meta)
        if not converted:
            lines = ["No safe bounded embedded-text PDF candidates could be converted into CAD entities."] + _plan_pdf_unconverted_cad_lines(updated_meta)
        return _truthful_decision_update(
            {},
            assistant_message="\n".join(lines),
            intent="pdf_to_cad_entities",
            run_mode="cad_entity_model_update",
            needs_clarification=False,
            action_taken="converted_pdf_candidates_to_review_required_cad_entities",
            affected_systems=["plan_pdf_understanding", "cad_entity_model", "candidate_review_inbox"],
            assumptions=["Only bounded embedded PDF text and supported vector line/polyline records are converted; OCR/raster uncertainty remains blocked."],
            next_best_action="Review the PDF-derived CAD entity candidates in Candidate Review Inbox before relying on them.",
            command_payload_updates={"ui_navigation_target": "data", "requested_ui_mode": "data", "source_confidence": PLAN_PDF_SOURCE_CONFIDENCE},
            state_changed=True,
            confidence=0.66,
        )
    if wants_pdf_to_cad and ("became" in normalized or "entities" in normalized):
        lines = _plan_pdf_cad_entity_lines(meta)
    elif wants_unconverted or wants_raster_line_reason:
        lines = _plan_pdf_unconverted_cad_lines(meta)
        if wants_raster_line_reason:
            lines.insert(0, "A raster line cannot become CAD linework unless a configured extraction engine returns supported vector line/polyline geometry with confidence and source bounds.")
    elif wants_change_summary:
        lines = _plan_pdf_changed_lines(meta)
    elif "what can you not read" in normalized or "what could you not read" in normalized or "unreadable" in normalized or "blocker" in normalized:
        lines = _plan_pdf_unreadable_lines(meta)
    elif "scale" in normalized:
        values = _plan_pdf_text(meta, "scale_candidates")
        lines = ["Scale candidates from the PDF:"] + ([f"- {item}" for item in values] if values else ["- No scale text was extracted."])
    elif "elevation" in normalized:
        values = _plan_pdf_text(meta, "elevation_callouts", limit=20)
        lines = ["Elevation candidates from the PDF:"] + ([f"- {item}" for item in values] if values else ["- No elevation text was extracted."])
    elif "dimension" in normalized:
        values = _plan_pdf_text(meta, "dimensions")
        lines = ["Dimension candidates from the PDF:"] + ([f"- {item}" for item in values] if values else ["- No dimension text was extracted."])
    elif "turn this pdf into editable" in normalized or "make this detail editable" in normalized:
        sheet_summary = _safe_dict(_safe_dict(meta.get("plan_pdf_editable_sheet_v1")).get("summary"))
        lines = [
            f"Editable PDF-derived sheet objects exist: {int(sheet_summary.get('element_count') or 0)} total, {int(sheet_summary.get('editable_count') or 0)} editable text/note/detail candidates.",
            "Every element is review-required until accepted/rejected by a user or external reviewer.",
        ]
    else:
        lines = [
            f"I found a review-required plan PDF analysis with {int(analysis.get('page_count') or 0)} page(s).",
            (
                f"Extracted candidates: {int(summary.get('title_block_count') or 0)} title block, "
                f"{int(summary.get('note_block_count') or 0)} note block, "
                f"{int(summary.get('detail_block_count') or 0)} detail, "
                f"{int(summary.get('dimension_count') or 0)} dimension, "
                f"{int(summary.get('elevation_callout_count') or 0)} elevation, "
                f"{int(summary.get('scale_candidate_count') or 0)} scale."
            ),
            _plan_pdf_ocr_behavior_line(meta),
            "PDF-derived data remains imported_pdf_review_required and is not field-use release.",
        ]
    return _truthful_decision_update(
        {},
        assistant_message="\n".join(lines),
        intent="plan_pdf_understanding",
        run_mode="none",
        needs_clarification=False,
        action_taken="answered_plan_pdf_understanding_question",
        affected_systems=["plan_pdf_understanding", "editable_sheet"],
        assumptions=["Answers are based only on saved PDF extraction evidence."],
        next_best_action="Review extracted candidates in the Data panel and verify against survey/control before relying on them.",
        command_payload_updates={"ui_navigation_target": "data", "requested_ui_mode": "data", "source_confidence": PLAN_PDF_SOURCE_CONFIDENCE},
        confidence=0.68,
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
    early_project_input = _safe_dict(record.get("project_input")) if record else _safe_dict(context.get("project_input"))
    early_latest_result = _safe_dict(record.get("latest_result")) if record else _safe_dict(_safe_dict(context.get("current_project")).get("latest_result"))
    cad_entity_decision = _cad_entity_chat_response(
        message=message,
        context=context,
        record=record,
        project_store=project_store,
        user_id=user_id,
    )
    if cad_entity_decision is not None:
        return _enrich_response_contract(cad_entity_decision, message=message)
    dwg_decision = _dwg_compatibility_chat_response(message, context)
    if dwg_decision is not None:
        return _enrich_response_contract(dwg_decision, message=message)
    cad_command_line_decision = _cad_command_line_chat_response(message, context)
    if cad_command_line_decision is not None:
        return _enrich_response_contract(cad_command_line_decision, message=message)
    geometry_edit_decision = _drawn_geometry_edit_chat_response(
        {},
        message=message,
        context=context,
        project_input=early_project_input,
        latest_result=early_latest_result,
    )
    if geometry_edit_decision is not None:
        return _enrich_response_contract(geometry_edit_decision, message=message)
    plotting_decision = _plotting_sheet_chat_response(message, context)
    if plotting_decision is not None:
        return _enrich_response_contract(plotting_decision, message=message)
    discipline_depth_decision = _discipline_depth_chat_response(message, context)
    if discipline_depth_decision is not None:
        return _enrich_response_contract(discipline_depth_decision, message=message)
    symbol_block_decision = _symbol_block_chat_response(message, context)
    if symbol_block_decision is not None:
        return _enrich_response_contract(symbol_block_decision, message=message)
    plan_pdf_decision = _plan_pdf_chat_response(
        message=message,
        record=record,
        project_store=project_store,
        user_id=user_id,
    )
    if plan_pdf_decision is not None:
        return _enrich_response_contract(plan_pdf_decision, message=message)
    provider_registry_decision = _provider_registry_chat_response(
        message=message,
        record=record,
        project_store=project_store,
        user_id=user_id,
    )
    if provider_registry_decision is not None:
        return _enrich_response_contract(provider_registry_decision, message=message)
    online_discovery_decision = _online_discovery_chat_response(
        message=message,
        record=record,
        project_store=project_store,
        user_id=user_id,
    )
    if online_discovery_decision is not None:
        return _enrich_response_contract(online_discovery_decision, message=message)
    utility_catalog_decision = _utility_catalog_chat_response(message, context)
    if utility_catalog_decision is not None:
        return _enrich_response_contract(utility_catalog_decision, message=message)
    standards_rules_decision = _standards_rules_chat_response(
        message=message,
        context=context,
        record=record,
        project_store=project_store,
        user_id=user_id,
    )
    if standards_rules_decision is not None:
        return _enrich_response_contract(standards_rules_decision, message=message)
    issue_tracker_decision = _issue_tracker_chat_response(
        message=message,
        record=record,
        project_store=project_store,
        user_id=user_id,
    )
    if issue_tracker_decision is not None:
        return _enrich_response_contract(issue_tracker_decision, message=message)
    alternatives_decision = _design_alternatives_chat_response(
        message=message,
        record=record,
        project_store=project_store,
        user_id=user_id,
    )
    if alternatives_decision is not None:
        return _enrich_response_contract(alternatives_decision, message=message)
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
    customer_template_decision = _customer_template_chat_response(message)
    if customer_template_decision is not None:
        return _enrich_response_contract(customer_template_decision, message=message)
    annotation_standards_decision = _annotation_standards_chat_response(message, context)
    if annotation_standards_decision is not None:
        return _enrich_response_contract(annotation_standards_decision, message=message)
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
