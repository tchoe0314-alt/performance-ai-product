from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

from .common import blocker_explanation, safe_dict, safe_list, safe_str


SMART_FIX_VERSION = "smart_fix_recommendations_v1"


AUTO_FIX_ACTIONS: Dict[str, Dict[str, Any]] = {
    "open_setup": {
        "label": "Open setup",
        "kind": "ui_navigation",
        "ui_action": {"type": "open_panel", "panel": "site_existing"},
        "chat_prompt": "open setup",
    },
    "retry_geocode": {
        "label": "Retry address lookup",
        "kind": "ui_navigation",
        "ui_action": {"type": "open_panel", "panel": "site_existing"},
        "chat_prompt": "retry address lookup",
    },
    "open_candidate_review": {
        "label": "Review candidates",
        "kind": "ui_navigation",
        "ui_action": {"type": "open_panel", "panel": "data"},
        "chat_prompt": "what candidates are pending?",
    },
    "run_fix_pass": {
        "label": "Run fix pass",
        "kind": "orchestrator",
        "ui_action": {"type": "run_fix"},
        "chat_prompt": "fix it",
    },
    "run_grading": {
        "label": "Run grading",
        "kind": "system_generation",
        "ui_action": {"type": "generate_system", "target": "grading"},
        "chat_prompt": "fix grading",
    },
    "run_drainage": {
        "label": "Run drainage",
        "kind": "system_generation",
        "ui_action": {"type": "generate_system", "target": "drainage"},
        "chat_prompt": "fix drainage",
    },
    "run_utilities": {
        "label": "Run utilities",
        "kind": "system_generation",
        "ui_action": {"type": "generate_system", "target": "utilities"},
        "chat_prompt": "fix utilities",
    },
    "run_roadway": {
        "label": "Run roadway",
        "kind": "system_generation",
        "ui_action": {"type": "generate_system", "target": "roadway"},
        "chat_prompt": "fix roadway",
    },
    "add_drainage_basin": {
        "label": "Add basin",
        "kind": "drainage_autofix",
        "ui_action": {"type": "chat_prompt", "prompt": "add a draft basin at the low point"},
        "chat_prompt": "add a draft basin at the low point",
    },
    "adjust_drainage_slope": {
        "label": "Adjust slope",
        "kind": "drainage_autofix",
        "ui_action": {"type": "chat_prompt", "prompt": "adjust drainage slope within allowed limits"},
        "chat_prompt": "adjust drainage slope within allowed limits",
    },
    "run_export_report": {
        "label": "Build report",
        "kind": "export",
        "ui_action": {"type": "export_report"},
        "chat_prompt": "build the engineer review report",
    },
    "run_reactive_rerun": {
        "label": "Rerun stale outputs",
        "kind": "reactive_rerun",
        "ui_action": {"type": "run_fix"},
        "chat_prompt": "rerun stale outputs",
    },
}


_MANUAL_SOURCE_BY_CATEGORY = {
    "survey_control": "survey/control file with datum, benchmark, coordinate system, and control notes",
    "standards": "accepted applicable standards source or rule packet",
    "cost_book": "approved current unit-price book source",
    "engineer_review_package": "responsible reviewer comments or requested review package scope",
    "online_candidates": "user review decision for each candidate",
}


def _unique_text(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    for value in values:
        text = safe_str(value)
        if text and text not in out:
            out.append(text)
    return out


def _slug(value: Any) -> str:
    text = safe_str(value, "blocker").lower()
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in text)
    return "_".join(part for part in cleaned.split("_") if part) or "blocker"


def _blocker_code(value: Any) -> str:
    if isinstance(value, dict):
        return _slug(
            value.get("code")
            or value.get("field")
            or value.get("blocker")
            or value.get("message")
            or value.get("reason")
        )
    return _slug(value)


def _text_contains(code: str, *tokens: str) -> bool:
    return any(token in code for token in tokens)


def classify_blocker(blocker: Any) -> str:
    code = _blocker_code(blocker)
    if _text_contains(code, "address", "geocode", "location"):
        return "address_geocode"
    if _text_contains(code, "boundary", "site_size", "site_area", "setup", "lot"):
        return "setup_site_boundary"
    if _text_contains(code, "candidate", "parcel", "gis", "map_feature", "online"):
        return "online_candidates"
    if _text_contains(code, "survey", "control", "datum", "benchmark", "topo", "terrain"):
        return "survey_control"
    if _text_contains(code, "standard", "source_registry", "rule"):
        return "standards"
    if _text_contains(code, "grading", "slope", "ada"):
        return "grading"
    if _text_contains(code, "drainage", "outfall", "basin", "inlet"):
        return "drainage"
    if _text_contains(code, "storm", "pipe", "hydraulic"):
        return "storm"
    if _text_contains(code, "utility", "utilities", "water", "sanitary"):
        return "utilities"
    if _text_contains(code, "road", "roadway", "access", "drive"):
        return "roadway"
    if _text_contains(code, "cost", "price", "pricing", "quantity"):
        return "cost_book"
    if _text_contains(code, "engineer_review", "engineer", "external_reviewer", "review_package"):
        return "engineer_review_package"
    if _text_contains(code, "stale", "reactive", "rerun", "dirty"):
        return "stale_outputs"
    if _text_contains(code, "export", "deliverable", "artifact", "package", "dxf", "report"):
        return "exports"
    return "general"


def _action_for(category: str, code: str, *, meta: Dict[str, Any]) -> Optional[str]:
    if category == "setup_site_boundary":
        return "open_setup"
    if category == "address_geocode":
        return "retry_geocode" if _has_address(meta) else None
    if category == "online_candidates":
        return "open_candidate_review"
    if category == "grading":
        return "run_grading"
    if category in {"drainage", "storm"}:
        if _text_contains(code, "outfall", "basin", "low_point", "no_low"):
            return "add_drainage_basin"
        if _text_contains(code, "slope", "flat"):
            return "adjust_drainage_slope"
        return "run_drainage"
    if category == "utilities":
        return "run_utilities"
    if category == "roadway":
        return "run_roadway"
    if category == "exports":
        return "run_export_report"
    if category == "stale_outputs":
        return "run_reactive_rerun"
    if category == "general":
        return "run_fix_pass"
    return None


def _has_address(meta: Dict[str, Any]) -> bool:
    location = safe_dict(meta.get("location_context"))
    site_inputs = safe_dict(safe_dict(meta.get("site_inputs")).get("location"))
    return bool(safe_str(location.get("address") or site_inputs.get("address") or meta.get("address")))


def _manual_missing_source(category: str, detail: Dict[str, Any], code: str) -> str:
    if category in _MANUAL_SOURCE_BY_CATEGORY:
        return _MANUAL_SOURCE_BY_CATEGORY[category]
    missing = _unique_text(detail.get("missing_data") or [])
    if missing:
        return missing[0]
    return f"resolved source evidence for {code.replace('_', ' ')}"


def _after_fix(category: str, can_fix: bool) -> str:
    if category == "stale_outputs":
        return "Civora will rebuild affected systems and keep exports blocked if anything remains stale."
    if category == "exports":
        return "Civora will rebuild review-package evidence and keep unresolved gates visible."
    if category in {"grading", "drainage", "storm", "utilities", "roadway"}:
        return "Civora will rerun affected systems, refresh blockers, and update review-package evidence."
    if category in {"setup_site_boundary", "address_geocode", "online_candidates"}:
        return "Civora will update project context and rerun only the checks that depend on that context."
    if can_fix:
        return "Civora will rerun validation and show any remaining blockers."
    return "After the missing input is provided, Civora can rerun validation and produce updated recommendations."


def _collect_blockers(final_plan: Dict[str, Any], meta: Dict[str, Any]) -> List[Any]:
    blockers: List[Any] = []
    release_review = safe_dict(meta.get("release_review"))
    for key in (
        "blockers",
        "blocked_reasons",
        "blocked_exports",
        "release_blockers",
        "missing_inputs",
    ):
        blockers.extend(safe_list(meta.get(key)))
        blockers.extend(safe_list(final_plan.get(key)))
        blockers.extend(safe_list(release_review.get(key)))
    for report_key in (
        "setup_wizard_state_v1",
        "existing_conditions_package",
        "survey_control_package",
        "standards_package",
        "standards_source_registry",
        "candidate_rule_report",
        "map_feature_detection_report_v1",
        "engine_depth_audit",
        "engine_readiness",
        "production_evidence",
        "export_package_report_v1",
        "export_audit",
        "reactive_update_report",
        "reactive_partial_rerun",
        "engineer_review_package_v1",
        "construction_document_support_package_v1",
    ):
        record = safe_dict(meta.get(report_key))
        if not record:
            continue
        blockers.extend(safe_list(record.get("blockers")))
        blockers.extend(safe_list(record.get("missing_inputs")))
        blockers.extend(safe_list(record.get("blocked_reasons")))
        blockers.extend(safe_list(record.get("stale_outputs")))
        blockers.extend(safe_list(record.get("post_rerun_stale_outputs")))
    return blockers


def _recommendation(blocker: Any, *, index: int, meta: Dict[str, Any]) -> Dict[str, Any]:
    code = _blocker_code(blocker)
    detail = blocker_explanation(blocker)
    category = classify_blocker(blocker)
    action_id = _action_for(category, code, meta=meta)
    action = deepcopy(AUTO_FIX_ACTIONS.get(action_id or "")) if action_id else {}
    can_fix = bool(action)
    missing_source = "" if can_fix else _manual_missing_source(category, detail, code)
    one_action = (
        safe_str(action.get("label"))
        if can_fix
        else f"Provide {missing_source}."
    )
    return {
        "id": f"sfr_{index + 1}_{code}",
        "blocker_code": code,
        "category": category,
        "severity": "blocker",
        "what_is_wrong": safe_str(detail.get("what_failed"), f"{code.replace('_', ' ')} is blocking progress."),
        "why_it_matters": safe_str(detail.get("why_it_matters"), "Civora keeps unresolved blockers visible so outputs are not overstated."),
        "can_civora_fix": can_fix,
        "fix_mode": "auto_supported" if can_fix else "manual_input_required",
        "supported_action_id": action_id or "",
        "supported_action": action,
        "one_action_needed_next": one_action,
        "missing_user_input_or_source": missing_source,
        "what_happens_after_fix": _after_fix(category, can_fix),
        "ui_action": deepcopy(action.get("ui_action") or {}),
        "chat_prompt": safe_str(action.get("chat_prompt")),
        "engineer_review_required": True,
    }


def _default_manual_recommendations(meta: Dict[str, Any]) -> List[Any]:
    defaults: List[Any] = []
    if not safe_dict(meta.get("survey_control_package")):
        defaults.append("survey_control_missing")
    if not safe_dict(meta.get("standards_package")) and not safe_dict(meta.get("standards_source_registry")):
        defaults.append("standards_source_missing")
    if not safe_dict(meta.get("engineer_review_package_v1")):
        defaults.append("engineer_review_package_missing")
    return defaults


def build_smart_fix_recommendations(final_plan: Optional[Dict[str, Any]] = None, *, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    plan = safe_dict(final_plan)
    plan_meta = safe_dict(meta) or safe_dict(plan.get("meta"))
    raw_blockers = _collect_blockers(plan, plan_meta)
    if not raw_blockers:
        raw_blockers = _default_manual_recommendations(plan_meta)
    seen: set[str] = set()
    recommendations: List[Dict[str, Any]] = []
    for blocker in raw_blockers:
        code = _blocker_code(blocker)
        if not code or code in seen:
            continue
        seen.add(code)
        recommendations.append(_recommendation(blocker, index=len(recommendations), meta=plan_meta))

    supported = [rec for rec in recommendations if rec["can_civora_fix"]]
    manual = [rec for rec in recommendations if not rec["can_civora_fix"]]
    next_best = supported[0] if supported else (manual[0] if manual else {})
    return {
        "version": SMART_FIX_VERSION,
        "recommendation_count": len(recommendations),
        "auto_fix_action_count": len(supported),
        "manual_action_count": len(manual),
        "recommendations": recommendations,
        "supported_auto_fix_actions": [
            {
                "id": rec["supported_action_id"],
                "label": rec["supported_action"].get("label"),
                "category": rec["category"],
                "ui_action": rec["ui_action"],
                "chat_prompt": rec["chat_prompt"],
            }
            for rec in supported
        ],
        "blocked_manual_only_actions": [
            {
                "blocker_code": rec["blocker_code"],
                "category": rec["category"],
                "missing_user_input_or_source": rec["missing_user_input_or_source"],
                "one_action_needed_next": rec["one_action_needed_next"],
            }
            for rec in manual
        ],
        "next_best_recommendation": deepcopy(next_best),
        "truth_label": "Smart Fix explains blockers and only runs supported actions. Missing survey, standards, cost, or reviewer sources must come from the user or responsible source.",
    }


__all__ = [
    "AUTO_FIX_ACTIONS",
    "SMART_FIX_VERSION",
    "build_smart_fix_recommendations",
    "classify_blocker",
]
