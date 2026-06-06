from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


EVIDENCE_VERSION = "ai_orchestration_evidence_v1"


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _unique_strings(values: Any) -> List[str]:
    unique: List[str] = []
    for item in _safe_list(values):
        text = _safe_str(item)
        if text and text not in unique:
            unique.append(text)
    return unique


def _workflow_from_decision(decision: Dict[str, Any], metadata: Dict[str, Any]) -> str:
    command_payload = _safe_dict(metadata.get("command_payload"))
    workflow = _safe_str(command_payload.get("workflow"))
    if workflow:
        return workflow
    run_mode = _safe_str(decision.get("run_mode"))
    if run_mode and run_mode != "none":
        return run_mode
    intent = _safe_str(metadata.get("intent") or decision.get("intent"))
    intent_workflow = {
        "grading_command": "grading",
        "drainage_command": "drainage",
        "utility_command": "utilities",
        "generate_command": "all_enabled_systems",
    }.get(intent)
    if intent_workflow:
        return intent_workflow
    if intent:
        return intent
    return "conversation"


def _planned_actions(decision: Dict[str, Any], metadata: Dict[str, Any]) -> List[str]:
    actions = _unique_strings(metadata.get("actions_planned"))
    if actions:
        return actions
    action = _safe_str(metadata.get("action_taken") or decision.get("action_taken"))
    run_mode = _safe_str(decision.get("run_mode"))
    workflow = _workflow_from_decision(decision, metadata)
    if action.startswith("blocked") or action.startswith("asked") or action == "unsupported_or_not_understood":
        return []
    if run_mode == "fix":
        return ["run_supported_fix_pass"]
    if run_mode == "improve":
        return ["run_supported_improvement_pass"]
    if workflow and workflow not in {"conversation", "unsupported_or_not_understood", "responsibility_guard"}:
        return [workflow]
    return [action] if action and action != "responded" else []


def build_ai_orchestration_evidence(
    *,
    user_intent: str,
    parsed_intent: str,
    selected_workflow: str,
    required_inputs: Optional[List[str]] = None,
    missing_inputs: Optional[List[str]] = None,
    assumptions: Optional[List[str]] = None,
    actions_planned: Optional[List[str]] = None,
    actions_executed: Optional[List[str]] = None,
    actions_blocked: Optional[List[str]] = None,
    affected_systems: Optional[List[str]] = None,
    next_best_action: str = "",
    confidence: Optional[float] = None,
    unsupported_actions: Optional[List[str]] = None,
    state_changed: bool = False,
    engineer_review_required: bool = True,
) -> Dict[str, Any]:
    unsupported = _unique_strings(unsupported_actions or [])
    blocked = _unique_strings(actions_blocked or [])
    missing = _unique_strings(missing_inputs or [])
    executed = _unique_strings(actions_executed or [])
    planned = _unique_strings(actions_planned or [])
    fake_success = bool((unsupported or blocked or missing) and (state_changed or executed))
    return {
        "version": EVIDENCE_VERSION,
        "user_intent": _safe_str(user_intent),
        "parsed_intent": _safe_str(parsed_intent),
        "selected_workflow": _safe_str(selected_workflow, "conversation"),
        "required_inputs": _unique_strings(required_inputs or []),
        "missing_inputs": missing,
        "assumptions": _unique_strings(assumptions or []),
        "actions_planned": planned,
        "actions_executed": executed,
        "actions_blocked": blocked,
        "affected_systems": _unique_strings(affected_systems or []),
        "next_best_action": _safe_str(next_best_action),
        "confidence": round(float(confidence), 3) if confidence is not None else None,
        "unsupported_actions": unsupported,
        "state_changed": bool(state_changed),
        "engineer_review_required": bool(engineer_review_required),
        "construction_release_allowed": False,
        "construction_ready": False,
        "fake_success_detected": fake_success,
        "truth_label": (
            "AI orchestration evidence records intent, routing, assumptions, actions, and blockers; "
            "it is review evidence only and never construction approval."
        ),
    }


def build_ai_orchestration_evidence_from_decision(message: str, decision: Dict[str, Any]) -> Dict[str, Any]:
    metadata = _safe_dict(decision.get("response_metadata"))
    action_taken = _safe_str(metadata.get("action_taken") or decision.get("action_taken"))
    blocker = _safe_str(metadata.get("action_blocked_reason") or metadata.get("blocker") or decision.get("action_blocked_reason"))
    unsupported = _safe_str(metadata.get("unsupported_reason"))
    outcome = _safe_str(metadata.get("outcome"))
    state_changed = bool(metadata.get("state_changed"))
    action_blocked = []
    if blocker and (outcome in {"understood_but_blocked", "understood_needs_more_info"} or action_taken.startswith(("blocked", "asked"))):
        action_blocked.append(blocker)
    unsupported_actions = [unsupported] if unsupported or outcome == "unsupported_or_not_understood" else []
    actions_executed = [action_taken] if state_changed and action_taken and not action_blocked and not unsupported_actions else []
    return build_ai_orchestration_evidence(
        user_intent=message,
        parsed_intent=_safe_str(metadata.get("intent") or decision.get("intent")),
        selected_workflow=_workflow_from_decision(decision, metadata),
        required_inputs=_safe_list(metadata.get("required_inputs")),
        missing_inputs=_safe_list(metadata.get("required_missing_inputs")),
        assumptions=_safe_list(metadata.get("assumptions")),
        actions_planned=_planned_actions(decision, metadata),
        actions_executed=actions_executed,
        actions_blocked=action_blocked,
        affected_systems=_safe_list(metadata.get("affected_systems")),
        next_best_action=_safe_str(metadata.get("next_best_action") or decision.get("next_best_action")),
        confidence=metadata.get("confidence") if metadata.get("confidence") is not None else decision.get("confidence"),
        unsupported_actions=unsupported_actions,
        state_changed=state_changed,
    )


def attach_ai_orchestration_evidence_to_decision(message: str, decision: Dict[str, Any]) -> Dict[str, Any]:
    updated = deepcopy(decision)
    evidence = build_ai_orchestration_evidence_from_decision(message, updated)
    metadata = dict(updated.get("response_metadata") or {})
    metadata[EVIDENCE_VERSION] = evidence
    updated["response_metadata"] = metadata
    updated[EVIDENCE_VERSION] = evidence
    return updated


def attach_ai_orchestration_evidence_to_plan(plan: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]:
    updated = deepcopy(plan)
    meta = dict(updated.get("meta") or {})
    existing_history = _safe_list(meta.get("ai_orchestration_evidence_history_v1"))
    meta[EVIDENCE_VERSION] = deepcopy(evidence)
    meta["ai_orchestration_evidence_history_v1"] = [*existing_history, deepcopy(evidence)][-20:]
    meta["engineer_review_required"] = True
    meta["construction_release_allowed"] = False
    meta["construction_ready"] = False
    updated["meta"] = meta
    return updated


def validate_ai_orchestration_evidence(evidence: Dict[str, Any]) -> Dict[str, Any]:
    rec = _safe_dict(evidence)
    blockers: List[str] = []
    required_fields = [
        "user_intent",
        "parsed_intent",
        "selected_workflow",
        "required_inputs",
        "missing_inputs",
        "assumptions",
        "actions_planned",
        "actions_executed",
        "actions_blocked",
        "affected_systems",
        "next_best_action",
        "confidence",
        "unsupported_actions",
        "state_changed",
        "engineer_review_required",
    ]
    for field in required_fields:
        if field not in rec:
            blockers.append(f"missing_{field}")
    if rec.get("version") != EVIDENCE_VERSION:
        blockers.append("wrong_or_missing_evidence_version")
    if rec.get("engineer_review_required") is not True:
        blockers.append("engineer_review_required_not_true")
    if rec.get("construction_release_allowed") is not False or rec.get("construction_ready") is not False:
        blockers.append("construction_release_not_blocked")
    if rec.get("fake_success_detected") is True:
        blockers.append("fake_success_detected")
    if _safe_list(rec.get("unsupported_actions")) and (rec.get("state_changed") is True or _safe_list(rec.get("actions_executed"))):
        blockers.append("unsupported_action_marked_success")
    if (_safe_list(rec.get("missing_inputs")) or _safe_list(rec.get("actions_blocked"))) and (
        rec.get("state_changed") is True or _safe_list(rec.get("actions_executed"))
    ):
        blockers.append("blocked_or_missing_action_marked_success")
    if rec.get("confidence") is None:
        blockers.append("confidence_missing")
    return {
        "valid": not blockers,
        "blockers": blockers,
        "review_level": not blockers,
        "truth_label": "Valid orchestration evidence may support review-depth classification only; it is not construction release.",
    }


__all__ = [
    "EVIDENCE_VERSION",
    "attach_ai_orchestration_evidence_to_decision",
    "attach_ai_orchestration_evidence_to_plan",
    "build_ai_orchestration_evidence",
    "build_ai_orchestration_evidence_from_decision",
    "validate_ai_orchestration_evidence",
]
