from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from parsers.chat_action_registry import command_intent_from_action_plan, plan_chat_action


CHAT_DECISION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["conversation", "settings", "design", "explain", "fix", "improve"],
        },
        "assistant_message": {"type": "string"},
        "run_mode": {"type": "string", "enum": ["none", "run", "fix", "improve"]},
        "design_prompt": {"type": "string"},
        "needs_clarification": {"type": "boolean"},
        "reason": {"type": "string"},
        "confidence": {"type": "number"},
        "control_overrides": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "strategyMode": {"type": "string", "enum": ["user", "assisted"]},
                "projectType": {"type": "string"},
                "units": {"type": "string"},
                "roads": {"type": "boolean"},
                "grading": {"type": "boolean"},
                "drainage": {"type": "boolean"},
                "utilities": {"type": "boolean"},
                "siteName": {"type": "string"},
                "fileName": {"type": "string"},
                "lotWidth": {"type": "string"},
                "lotHeight": {"type": "string"},
                "buildingWidth": {"type": "string"},
                "buildingDepth": {"type": "string"},
                "setback": {"type": "string"},
                "parkingCount": {"type": "string"},
            },
            "required": [],
        },
        "response_metadata": {"type": "object"},
        "required_missing_inputs": {"type": "array", "items": {"type": "string"}},
        "action_taken": {"type": "string"},
        "action_blocked_reason": {"type": "string"},
        "affected_systems": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "next_best_action": {"type": "string"},
    },
    "required": [
        "intent",
        "assistant_message",
        "run_mode",
        "design_prompt",
        "needs_clarification",
        "reason",
        "confidence",
        "control_overrides",
    ],
}

CHAT_MEMORY_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "preferences": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["preferences", "constraints", "open_questions"],
}


def _load_chat_client() -> Any:
    from parsers.ai_parser import _get_client  # type: ignore

    return _get_client()


def build_chat_memory_summary(chat_thread: Any) -> Dict[str, Any]:
    heuristic = _extract_chat_memory(chat_thread)
    if not isinstance(chat_thread, list) or not chat_thread:
        return {**heuristic, "open_questions": []}
    try:
        client = _load_chat_client()
        response = client.responses.create(
            model="gpt-5",
            input=[
                {
                    "role": "system",
                    "content": (
                        "Summarize the user's preferences, constraints, and any open questions "
                        "from this chat thread. Return only JSON that matches the schema."
                    ),
                },
                {"role": "user", "content": json.dumps(chat_thread)},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "civora_chat_memory",
                    "schema": CHAT_MEMORY_SCHEMA,
                    "strict": True,
                }
            },
        )
        data = json.loads(response.output_text)
        if not isinstance(data, dict):
            raise ValueError("Chat memory response was not an object.")
        return {
            "preferences": list(data.get("preferences") or [])[:8],
            "constraints": list(data.get("constraints") or [])[:8],
            "open_questions": list(data.get("open_questions") or [])[:6],
        }
    except Exception:
        return {**heuristic, "open_questions": []}


def _trim_chat_history(value: Any, limit: int = 6) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []
    trimmed: List[Dict[str, str]] = []
    for item in value[-limit:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "assistant").strip().lower()
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        if role not in {"user", "assistant", "system"}:
            role = "assistant"
        trimmed.append({"role": role, "content": content})
    return trimmed


def _normalized_chat_text(text: str) -> str:
    normalized = text.strip().lower()
    normalized = normalized.replace("’", "'").replace("`", "'").replace("“", '"').replace("”", '"')
    replacements = {
        "pls": "please",
        "pls.": "please",
        "thx": "thanks",
        "thanx": "thanks",
        "ur": "your",
        "rly": "really",
        "idk": "i don't know",
        "w/": "with",
        "w/o": "without",
    }
    for source, target in replacements.items():
        normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized)
    normalized = normalized.replace("¿", "").replace("¡", "")
    return normalized


def _references_prior_design_context(text: str) -> bool:
    lowered = _normalized_chat_text(text)
    return any(
        phrase in lowered
        for phrase in [
            "same ",
            "same requirements",
            "same site",
            "same design",
            "same project",
            "using the same",
            "based on the same",
            "previous prompt",
            "earlier prompt",
            "earlier requirements",
            "original requirements",
        ]
    )


def _recent_user_context_text(context: Dict[str, Any], current_message: str) -> str:
    history = list(context.get("chat_history") or [])
    if not history or not _references_prior_design_context(current_message):
        return ""
    normalized_current = _normalized_chat_text(current_message)
    prior_user_messages = [
        str(item.get("content") or "").strip()
        for item in history
        if str(item.get("role") or "").strip().lower() == "user"
    ]
    if prior_user_messages and _normalized_chat_text(prior_user_messages[-1]) == normalized_current:
        prior_user_messages = prior_user_messages[:-1]
    prior_user_messages = [item for item in prior_user_messages if item]
    return "\n".join(prior_user_messages[-3:])


def _last_user_message(context: Dict[str, Any]) -> str:
    history = list(context.get("chat_history") or [])
    for item in reversed(history):
        if str(item.get("role") or "").strip().lower() == "user":
            return str(item.get("content") or "").strip()
    return ""


def _extract_chat_memory(value: Any, limit: int = 8) -> Dict[str, Any]:
    if not isinstance(value, list):
        return {"preferences": [], "constraints": [], "examples": []}

    preferences: List[str] = []
    constraints: List[str] = []
    seen = set()

    for item in value:
        if not isinstance(item, dict):
            continue
        if str(item.get("role") or "").strip().lower() != "user":
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        clauses = re.split(r"[.!?\n;]+", content)
        for clause in clauses:
            clean = " ".join(clause.split()).strip()
            if not clean:
                continue
            lowered = _normalized_chat_text(clean)
            if len(lowered) < 8:
                continue

            bucket: Optional[List[str]] = None
            if any(
                phrase in lowered
                for phrase in [
                    "make sure",
                    "remember to",
                    "remember that",
                    "always ",
                    "prefer ",
                    "care more about",
                    "prioritize",
                    "prioritise",
                    "use ",
                    "keep ",
                    "stay in ",
                ]
            ):
                bucket = preferences
            elif any(
                phrase in lowered
                for phrase in [
                    "do not",
                    "don't",
                    "dont",
                    "never ",
                    "without ",
                    "no guessing",
                    "ask for clarification",
                    "if you are unsure",
                    "do not optimize too aggressively",
                    "don't optimize too aggressively",
                    "dont optimize too aggressively",
                    "do not optimize aggressively",
                    "don't optimize aggressively",
                    "dont optimize aggressively",
                ]
            ):
                bucket = constraints

            if bucket is None:
                continue

            key = lowered[:160]
            if key in seen:
                continue
            seen.add(key)
            bucket.append(clean)

    return {
        "preferences": preferences[-limit:],
        "constraints": constraints[-limit:],
        "examples": (preferences + constraints)[-limit:],
    }


def _chat_context_summary(context: Dict[str, Any]) -> Dict[str, Any]:
    current_project = context.get("current_project") or {}
    current_truth = context.get("current_truth_audit") or {}
    current_explanation = context.get("current_explanation") or {}
    current_export_audit = context.get("current_export_audit") or {}
    engineering_status = context.get("engineering_status") or {}
    workspace_state = context.get("workspace_state") or {}
    active_workspace = context.get("active_workspace") or workspace_state.get("active_workspace")
    active_panel = context.get("active_panel") or workspace_state.get("active_panel")
    active_tool = context.get("active_tool") or workspace_state.get("active_tool")
    convergence_summary = context.get("convergence_summary") or {}
    issues = context.get("issues") or []
    manual_failures = context.get("manual_failures") or []
    missing_inputs = context.get("missing_inputs") or context.get("required_missing_inputs") or []
    blockers = context.get("blockers") or context.get("blocked_reasons") or []
    assumptions = context.get("assumptions") or []
    produced_deliverables = context.get("produced_deliverables") or []
    memory_summary = _extract_chat_memory(context.get("chat_thread"))
    return {
        "strategy_mode": context.get("strategy_mode") or "assisted",
        "active_workspace": active_workspace or "",
        "active_panel": active_panel or "",
        "active_tool": active_tool or "",
        "site_name": context.get("site_name") or "",
        "file_name": context.get("file_name") or "",
        "project_type": context.get("project_type") or "",
        "units": context.get("units") or "ft",
        "lot_width": context.get("lot_width"),
        "lot_height": context.get("lot_height"),
        "site_locked": context.get("site_locked"),
        "address_status": context.get("address_status") or "",
        "site_size_status": context.get("site_size_status") or "",
        "building_count": context.get("building_count"),
        "parking_count": context.get("parking_count"),
        "disciplines": {
            "roads": bool(context.get("roads", True)),
            "grading": bool(context.get("grading", True)),
            "drainage": bool(context.get("drainage", True)),
            "utilities": bool(context.get("utilities", True)),
        },
        "has_plan": bool(context.get("has_plan")),
        "has_preview": bool(context.get("has_preview")),
        "selected_object_ids": list(context.get("selected_object_ids") or []),
        "selected_geometry_ids": list(context.get("selected_geometry_ids") or []),
        "referenced_object_ids": list(context.get("referenced_object_ids") or []),
        "referenced_geometry_ids": list(context.get("referenced_geometry_ids") or []),
        "activePlacementId": context.get("activePlacementId") or context.get("active_placement_id"),
        "current_project_name": current_project.get("name"),
        "current_project": {
            "project_id": current_project.get("project_id"),
            "name": current_project.get("name"),
            "project_input": dict(current_project.get("project_input") or {}),
            "latest_result": dict(current_project.get("latest_result") or {}),
        },
        "truth_success": current_truth.get("success", context.get("truth_success")),
        "engineering_trust_score": current_truth.get(
            "engineering_trust_score", context.get("engineering_trust_score")
        ),
        "engineering_status": engineering_status.get("status", context.get("engineering_status")),
        "engine_depth_status": context.get("engine_depth_status")
        or context.get("depth_status")
        or engineering_status.get("depth_status"),
        "standards_status": context.get("standards_status") or "",
        "existing_conditions_status": context.get("existing_conditions_status") or "",
        "engineer_review_status": context.get("engineer_review_status") or "",
        "export_audit": dict(current_export_audit or {}),
        "convergence_summary": {
            "converged": bool(convergence_summary.get("converged")),
            "passes_run": convergence_summary.get("passes_run"),
            "unresolved_conflict_count": convergence_summary.get("unresolved_conflict_count"),
            "blocked_exports": list(convergence_summary.get("blocked_exports") or []),
            "blocked_reasons": list(convergence_summary.get("blocked_reasons") or []),
            "unresolved_issue_categories": list(convergence_summary.get("unresolved_issue_categories") or []),
            "dominant_issue_categories": list(convergence_summary.get("dominant_issue_categories") or []),
            "rerun_summary": dict(convergence_summary.get("rerun_summary") or {}),
            "fix_summary": dict(convergence_summary.get("fix_summary") or {}),
        },
        "explanation_summary": current_explanation.get("summary")
        or current_explanation.get("overview"),
        "produced_deliverables": [str(item) for item in produced_deliverables[:8]],
        "missing_inputs": [str(item) for item in missing_inputs[:8]],
        "blockers": [str(item) for item in blockers[:8]],
        "next_best_action": str(context.get("next_best_action") or ""),
        "assumptions": [
            {
                "field_name": item.get("field_name") or item.get("field"),
                "assumed_value": item.get("assumed_value") or item.get("value"),
                "reason": item.get("reason"),
            }
            for item in assumptions[:8]
            if isinstance(item, dict)
        ],
        "issues": [
            {
                "severity": item.get("severity"),
                "message": item.get("message"),
            }
            for item in issues[:6]
            if isinstance(item, dict)
        ],
        "manual_failures": [
            {
                "code": item.get("code"),
                "message": item.get("message"),
                "system": item.get("system"),
                "rule": item.get("rule"),
            }
            for item in manual_failures[:6]
            if isinstance(item, dict)
        ],
        "memory_summary": memory_summary,
        "chat_history": _trim_chat_history(context.get("chat_thread")),
    }


def _ctx_has_site_size(context: Dict[str, Any]) -> bool:
    if _safe_positive_number(context.get("lot_width")) and _safe_positive_number(context.get("lot_height")):
        return True
    current_project = context.get("current_project") or {}
    for source in [
        context,
        current_project,
        current_project.get("project_input") if isinstance(current_project, dict) else {},
        current_project.get("latest_result") if isinstance(current_project, dict) else {},
    ]:
        if not isinstance(source, dict):
            continue
        if source.get("site_area_acres") or source.get("site_area"):
            return True
    return False


def _ctx_has_low_point(context: Dict[str, Any]) -> bool:
    current_project = context.get("current_project") or {}
    sources = [context]
    if isinstance(current_project, dict):
        sources.extend([current_project, current_project.get("latest_result") or {}, current_project.get("project_input") or {}])
    for source in sources:
        if not isinstance(source, dict):
            continue
        text = json.dumps(source, default=str).lower()[:20000]
        if any(token in text for token in ["low_point", "low points", "low corner", "southeast corner", "southwest corner"]):
            return True
    return False


def _ctx_has_buildings(context: Dict[str, Any]) -> bool:
    if _safe_positive_number(context.get("building_count")):
        return True
    current_project = context.get("current_project") or {}
    sources = [context]
    if isinstance(current_project, dict):
        sources.extend([current_project, current_project.get("latest_result") or {}, current_project.get("project_input") or {}])
    for source in sources:
        if not isinstance(source, dict):
            continue
        text = json.dumps(source, default=str).lower()[:20000]
        if any(token in text for token in ["building", "buildings", "building_placements"]):
            return True
    return False


def _ctx_has_drainage_target(context: Dict[str, Any]) -> bool:
    if _ctx_has_low_point(context):
        return True
    current_project = context.get("current_project") or {}
    sources = [context]
    if isinstance(current_project, dict):
        sources.extend([current_project, current_project.get("latest_result") or {}, current_project.get("project_input") or {}])
    for source in sources:
        if not isinstance(source, dict):
            continue
        text = json.dumps(source, default=str).lower()[:20000]
        if any(token in text for token in ["detention", "basin", "outfall", "pond"]):
            return True
    return False


def _ctx_has_utility_tie_ins(context: Dict[str, Any]) -> bool:
    current_project = context.get("current_project") or {}
    sources = [context]
    if isinstance(current_project, dict):
        sources.extend([current_project, current_project.get("latest_result") or {}, current_project.get("project_input") or {}])
    for source in sources:
        if not isinstance(source, dict):
            continue
        text = json.dumps(source, default=str).lower()[:20000]
        if any(token in text for token in ["water", "sanitary", "sewer", "tie", "connection", "utility"]):
            return True
    return False


def _ctx_has_referenced_geometry(context: Dict[str, Any]) -> bool:
    if context.get("selected_geometry_ids") or context.get("referenced_geometry_ids"):
        return True
    if context.get("selected_object_ids") or context.get("referenced_object_ids"):
        return True
    if context.get("activePlacementId") or context.get("active_placement_id"):
        return True
    current_project = context.get("current_project") or {}
    sources = [context]
    if isinstance(current_project, dict):
        sources.extend([current_project, current_project.get("project_input") or {}])
    for source in sources:
        if not isinstance(source, dict):
            continue
        text = json.dumps(source, default=str).lower()[:20000]
        if "canonical_geometry_handoff_v1" in text and any(token in text for token in ["selected", "activeplacementid", "referenced_geometry"]):
            return True
    return False


def _is_casual_chat_message(text: str) -> bool:
    normalized = _normalized_chat_text(text)
    if not normalized:
        return True
    casual_exact = {
        "hello",
        "hi",
        "hey",
        "yo",
        "sup",
        "what's up",
        "whats up",
        "how are you",
        "how r u",
        "how are u",
        "how you doing",
        "how's it going",
        "hows it going",
        "good morning",
        "good afternoon",
        "good evening",
        "thanks",
        "thank you",
        "cool",
        "nice",
        "okay",
        "ok",
        "hola",
        "gracias",
        "que tal",
        "como estas",
        "cómo estás",
        "buenos dias",
        "buenas tardes",
    }
    if normalized in casual_exact:
        return True
    casual_fragments = [
        "how are you",
        "how r u",
        "how are u",
        "how's it going",
        "hows it going",
        "can you help",
        "what do you think",
        "tell me about",
        "can you explain",
        "can you tell me",
        "que tal",
        "como estas",
    ]
    if any(fragment in normalized for fragment in casual_fragments):
        return True
    return normalized.endswith("?") and not any(
        keyword in normalized
        for keyword in [
            "design",
            "create",
            "generate",
            "make",
            "move",
            "add",
            "change",
            "update",
            "reroute",
            "grade",
            "drainage",
            "utility",
            "road",
            "parking",
            "building",
            "basin",
        ]
    )


def _extract_control_overrides(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    lowered = _normalized_chat_text(message)
    overrides: Dict[str, Any] = {}

    if re.search(r"\bmanual mode\b|\buse manual\b|\bswitch to manual\b|\bassisted off\b|\bturn off assisted\b|\bdisable assisted\b", lowered):
        overrides["strategyMode"] = "user"
    elif re.search(r"\bassisted mode\b|\buse assisted\b|\bswitch to assisted\b|\bassisted on\b|\bturn on assisted\b|\benable assisted\b", lowered):
        overrides["strategyMode"] = "assisted"
    if re.search(r"\bdon't assume anything\b|\bdont assume anything\b|\bno assumptions\b|\bdo not assume\b", lowered):
        overrides["strategyMode"] = "user"

    for field, patterns in {
        "roads": [r"\bturn on roads\b", r"\benable roads\b", r"\binclude roads\b", r"\bwith roads\b"],
        "grading": [r"\bturn on grading\b", r"\benable grading\b", r"\binclude grading\b", r"\bwith grading\b"],
        "drainage": [r"\bturn on drainage\b", r"\benable drainage\b", r"\binclude drainage\b", r"\bwith drainage\b", r"\binclude storm\b"],
        "utilities": [r"\bturn on utilit(?:y|ies)\b", r"\benable utilit(?:y|ies)\b", r"\binclude utilit(?:y|ies)\b", r"\bwith utilit(?:y|ies)\b", r"\binclude water\b", r"\binclude sanitary\b"],
    }.items():
        if any(re.search(pattern, lowered) for pattern in patterns):
            overrides[field] = True
    for field, patterns in {
        "roads": [r"\bturn off roads\b", r"\bdisable roads\b", r"\bwithout roads\b", r"\bremove roads\b"],
        "grading": [r"\bturn off grading\b", r"\bdisable grading\b", r"\bwithout grading\b", r"\bremove grading\b"],
        "drainage": [r"\bturn off drainage\b", r"\bdisable drainage\b", r"\bwithout drainage\b", r"\bremove drainage\b", r"\bwithout storm\b"],
        "utilities": [r"\bturn off utilit(?:y|ies)\b", r"\bdisable utilit(?:y|ies)\b", r"\bwithout utilit(?:y|ies)\b", r"\bremove utilit(?:y|ies)\b", r"\bwithout water\b", r"\bwithout sanitary\b"],
    }.items():
        if any(re.search(pattern, lowered) for pattern in patterns):
            overrides[field] = False

    name_match = re.search(r"(?:call|name)\s+(?:this|the project)?\s*[\"']?([^\"'\n]+)[\"']?$", message, re.IGNORECASE)
    if name_match:
        overrides["siteName"] = name_match.group(1).strip()

    file_match = re.search(r"(?:file name|filename|call the file)\s+(?:to|as)?\s*[\"']?([^\"'\n]+)[\"']?$", message, re.IGNORECASE)
    if file_match:
        overrides["fileName"] = file_match.group(1).strip()

    lot_by_dims = re.search(
        r"(?:lot|site)(?:\s+size|\s+dimensions?)?\s*(?:to|as|is)?\s*(\d+(?:\.\d+)?)\s*(?:ft|feet|m|meters)?\s*(?:x|by)\s*(\d+(?:\.\d+)?)",
        lowered,
    )
    if lot_by_dims:
        overrides["lotWidth"] = lot_by_dims.group(1)
        overrides["lotHeight"] = lot_by_dims.group(2)

    for field, pattern in {
        "lotWidth": r"(?:lot width|site width)\s*(?:to|is|=)?\s*(\d+(?:\.\d+)?)",
        "lotHeight": r"(?:lot height|site height|site depth|lot depth)\s*(?:to|is|=)?\s*(\d+(?:\.\d+)?)",
        "buildingWidth": r"(?:building width)\s*(?:to|is|=)?\s*(\d+(?:\.\d+)?)",
        "buildingDepth": r"(?:building depth|building length)\s*(?:to|is|=)?\s*(\d+(?:\.\d+)?)",
        "setback": r"(?:setback)\s*(?:to|is|=)?\s*(\d+(?:\.\d+)?)",
        "parkingCount": r"(?:parking count|parking|stalls?)\s*(?:to|is|=)?\s*(\d+(?:\.\d+)?)",
    }.items():
        match = re.search(pattern, lowered)
        if match:
            overrides[field] = match.group(1)

    units_match = re.search(r"\buse\s+(feet|foot|ft|meters|meter|m)\b", lowered)
    if units_match:
        unit = units_match.group(1)
        overrides["units"] = "m" if unit.startswith("m") else "ft"

    inferred_project_type = _infer_project_type_from_message(message)
    if inferred_project_type:
        overrides["projectType"] = inferred_project_type

    return overrides


def _is_settings_only_message(message: str, overrides: Dict[str, Any]) -> bool:
    if not overrides:
        return False
    lowered = _normalized_chat_text(message)
    design_verbs = [
        "design",
        "create",
        "generate",
        "make",
        "move",
        "add",
        "remove",
        "change the design",
        "update the design",
        "reroute",
        "grade",
        "layout",
    ]
    return not any(phrase in lowered for phrase in design_verbs)


def _has_edit_intent(message: str) -> bool:
    lowered = _normalized_chat_text(message)
    edit_phrases = [
        "move",
        "shift",
        "relocate",
        "reroute",
        "add",
        "remove",
        "change",
        "update",
        "adjust",
        "resize",
        "reduce",
        "increase",
        "widen",
        "narrow",
        "rotate",
        "keep the",
        "make the",
        "more",
        "less",
        "bigger",
        "smaller",
        "larger",
    ]
    design_targets = [
        "building",
        "road",
        "parking",
        "grading",
        "drainage",
        "storm",
        "basin",
        "utility",
        "utilities",
        "sanitary",
        "water",
        "layout",
        "site",
        "plan",
    ]
    return any(phrase in lowered for phrase in edit_phrases) and any(
        target in lowered for target in design_targets
    )


def _looks_like_follow_up_design_edit(message: str, context: Dict[str, Any]) -> bool:
    if not bool(context.get("has_plan")):
        return False
    lowered = _normalized_chat_text(message)
    if _has_edit_intent(message):
        return True
    if any(
        phrase in lowered
        for phrase in [
            "make it",
            "keep the",
            "use the same",
            "change that",
            "move that",
            "add more",
            "less parking",
            "more parking",
            "lower the",
            "raise the",
            "go back",
            "undo",
            "revert",
            "original idea",
            "earlier version",
            "last version",
            "last change",
        ]
    ):
        return True
    return False


def _looks_like_continuation_edit(message: str, context: Dict[str, Any]) -> bool:
    if not bool(context.get("has_plan")):
        return False
    lowered = _normalized_chat_text(message)
    chat_history = list(context.get("chat_history") or [])
    previous_user_messages = [
        _normalized_chat_text(str(item.get("content") or ""))
        for item in chat_history
        if isinstance(item, dict) and str(item.get("role") or "").strip().lower() == "user"
    ]
    last_user = previous_user_messages[-1] if previous_user_messages else ""

    continuation_starters = [
            "actually ",
            "okay now ",
            "ok now ",
            "now ",
            "also ",
            "same but ",
            "do the same but ",
            "keep the ",
            "keep everything else ",
            "keep the rest ",
            "leave the ",
            "leave everything else ",
            "instead ",
            "focus on ",
            "prioritize ",
            "go back ",
            "undo ",
            "revert ",
            "use the original ",
        ]
    if any(lowered.startswith(prefix) for prefix in continuation_starters):
        if _has_edit_intent(message):
            return True
        if any(
            token in lowered
            for token in [
                "building",
                "parking",
                "road",
                "grading",
                "drainage",
                "storm",
                "basin",
                "utility",
                "utilities",
                "sanitary",
                "water",
                "layout",
            ]
        ):
            return True
        if last_user and any(
            token in last_user
            for token in [
                "design",
                "create",
                "generate",
                "move",
                "add",
                "parking",
                "building",
                "grading",
                "drainage",
                "storm",
                "utility",
            ]
        ):
            return True
    return False


def _extract_revision_constraints(message: str) -> Dict[str, List[str]]:
    lowered = _normalized_chat_text(message)
    preserve_targets = [
        "building",
        "parking",
        "road",
        "roads",
        "grading",
        "drainage",
        "storm",
        "basin",
        "utilities",
        "utility",
        "sanitary",
        "water",
        "layout",
        "site",
    ]
    focus_targets = [
        "grading",
        "drainage",
        "storm",
        "basin",
        "utilities",
        "utility",
        "sanitary",
        "water",
        "parking",
        "layout",
        "roads",
        "building",
    ]

    preserve: List[str] = []
    focus: List[str] = []

    if any(phrase in lowered for phrase in ["keep everything else the same", "keep the rest the same", "leave everything else the same", "leave the rest the same"]):
        preserve.append("the rest of the design")

    for target in preserve_targets:
        if any(
            phrase in lowered
            for phrase in [
                f"keep the {target}",
                f"keep {target}",
                f"keep the new {target}",
                f"keep new {target}",
                f"leave the {target}",
                f"do not change the {target}",
                f"don't change the {target}",
                f"dont change the {target}",
            ]
        ):
            preserve.append(target)

    for target in focus_targets:
        if any(
            phrase in lowered
            for phrase in [
                f"focus on {target}",
                f"prioritize {target}",
                f"focus more on {target}",
                f"prioritise {target}",
                f"care more about {target}",
            ]
        ):
            focus.append(target)
        if re.search(rf"\b{re.escape(target)}\b.*\bmore than\b", lowered):
            focus.append(target)

    return {
        "preserve": list(dict.fromkeys(preserve)),
        "focus": list(dict.fromkeys(focus)),
    }


def _extract_revision_direction(message: str) -> Optional[str]:
    lowered = _normalized_chat_text(message)
    rollback_phrases = [
        "go back to",
        "go back",
        "undo the last change",
        "undo that",
        "undo it",
        "revert the last change",
        "revert that",
        "revert it",
        "use the original idea",
        "use the original version",
        "back to the earlier version",
        "back to the original",
    ]
    if any(phrase in lowered for phrase in rollback_phrases):
        return "rollback"
    return None


def _revision_acknowledgement(message: str, context: Dict[str, Any]) -> str:
    constraints = _extract_revision_constraints(message)
    direction = _extract_revision_direction(message)
    parts: List[str] = []
    if direction == "rollback":
        parts.append("I’m rolling the design back toward the earlier direction")
    elif bool(context.get("has_plan")):
        parts.append("I’m updating the current design")
    else:
        parts.append("I have enough context to start the design")

    if constraints["focus"]:
        parts.append("with extra attention on " + _format_missing_requirements(constraints["focus"][:3]))
    if constraints["preserve"]:
        parts.append("while keeping " + _format_missing_requirements(constraints["preserve"][:3]) + " intact")

    reply = " ".join(parts).strip()
    if not reply.endswith("."):
        reply += "."
    phase = str(context.get("current_phase") or "").strip()
    if phase:
        reply = f"{reply} Current phase: {phase}."
    return reply + _remembered_instruction_fragment(context)


def _revision_mode_acknowledgement(message: str, context: Dict[str, Any], preamble: str) -> str:
    constraints = _extract_revision_constraints(message)
    direction = _extract_revision_direction(message)
    parts: List[str] = [preamble.rstrip(".")]
    if direction == "rollback":
        parts.append("and steering it back toward the earlier version")
    if constraints["focus"]:
        parts.append("with extra attention on " + _format_missing_requirements(constraints["focus"][:3]))
    if constraints["preserve"]:
        parts.append("while keeping " + _format_missing_requirements(constraints["preserve"][:3]) + " intact")
    reply = " ".join(parts).strip()
    if not reply.endswith("."):
        reply += "."
    phase = str(context.get("current_phase") or "").strip()
    if phase:
        reply = f"{reply} Current phase: {phase}."
    return reply + _remembered_instruction_fragment(context)


def _is_question(message: str) -> bool:
    lowered = _normalized_chat_text(message)
    return lowered.endswith("?") or any(
        lowered.startswith(prefix)
        for prefix in [
            "why ",
            "what ",
            "how ",
            "can ",
            "could ",
            "should ",
            "is ",
            "are ",
            "do ",
            "does ",
            "did ",
            "por que ",
            "porque ",
            "que ",
            "como ",
        ]
    )


def _is_ambiguous_request(message: str, context: Dict[str, Any]) -> bool:
    lowered = _normalized_chat_text(message)
    if not lowered:
        return True
    if _is_explicit_plan_tool_request(message, "fix") or _is_explicit_plan_tool_request(message, "improve"):
        return False

    exact_ambiguous = {
        "do it",
        "do that",
        "do this",
        "fix it",
        "change it",
        "change that",
        "change this",
        "make it better",
        "improve it",
        "try again",
        "again",
        "more",
        "less",
        "something like that",
        "you decide",
        "do whatever you think is best",
        "whatever you think is best",
        "whatever you think",
        "whatever",
        "idk",
        "i dont know",
        "i don't know",
    }
    if lowered in exact_ambiguous:
        return True

    tokens = re.findall(r"[a-z0-9']+", lowered)
    if len(tokens) <= 3 and any(
        token in {"it", "that", "this", "there", "thing", "something"} for token in tokens
    ):
        return True

    if any(
        phrase in lowered
        for phrase in [
            "something like",
            "kind of like",
            "sort of like",
            "whatever works",
            "not sure",
            "you pick",
        ]
    ):
        return True

    vague_directives = ["do", "make", "change", "update", "fix", "improve", "add", "remove", "move"]
    design_targets = [
        "building",
        "road",
        "parking",
        "grading",
        "drainage",
        "storm",
        "basin",
        "utility",
        "utilities",
        "sanitary",
        "water",
        "layout",
        "site",
        "plan",
        "pad",
        "drive",
        "inlet",
        "pipe",
    ]
    if any(token in vague_directives for token in tokens):
        has_target = any(target in lowered for target in design_targets)
        if not has_target:
            return True
        if bool(context.get("has_plan")) and any(
            phrase in lowered for phrase in ["change that", "move that", "fix it", "do it again"]
        ):
            return True

    return False


def _looks_like_run_confirmation(message: str, context: Dict[str, Any]) -> bool:
    lowered = _normalized_chat_text(message)
    if lowered not in {
        "send it",
        "run it",
        "go ahead",
        "go for it",
        "start it",
        "send",
        "run",
    }:
        return False
    previous_user = _last_user_message(context)
    if not previous_user:
        return False
    return _looks_like_explicit_design_request(previous_user) or _is_well_specified_design_request(
        previous_user,
        context,
    )


def _conversation_reply(message: str, context: Dict[str, Any]) -> str:
    lowered = _normalized_chat_text(message)
    if any(phrase in lowered for phrase in ["how are you", "how r u", "how are u"]):
        return "I’m doing well and I’m ready to help with the design. You can ask me about the current plan or tell me what you want to change."
    if any(phrase in lowered for phrase in ["hola", "que tal", "como estas", "cómo estás"]):
        return "Hola, I’m Civora. You can ask about the current design, change a setting, or tell me what you want me to create or revise."
    if lowered in {"hello", "hi", "hey", "yo"}:
        return "Hi, I’m Civora. Tell me what you want to design, or ask me about the current plan."
    if "thank" in lowered:
        return "You’re welcome. Tell me what you want to adjust next, or ask me about the current design."
    if "help me think" in lowered or "think through" in lowered:
        return (
            "Absolutely. I can help you think through the design, talk through tradeoffs, or help you decide what to change next."
            + _current_project_fragment(context)
        )
    if "what do you need" in lowered or "what info do you need" in lowered or "what information do you need" in lowered:
        return (
            "For a solid design start, the most useful inputs are the site type, rough lot size, building or parking program, terrain or slope information, and which systems you want included."
            + _remembered_instruction_fragment(context)
        )
    if any(
        phrase in lowered
        for phrase in [
            "what would i need",
            "what do i need",
            "what supplies",
            "what materials",
            "what equipment",
        ]
    ):
        return (
            "For Civora, the first thing I need is project input rather than construction materials: site type, lot size, building or parking program, terrain information, and which systems you want included. "
            "If you want, I can also turn the current design scope into a practical checklist of supporting files, field information, and likely materials or equipment."
            + _current_project_fragment(context)
        )
    if "can you help" in lowered and bool(context.get("has_plan")):
        return (
            "Yes. I can explain the current design, help you choose the next revision, or make a targeted change once you tell me what you want adjusted."
            + _current_project_fragment(context)
        )
    if "help" in lowered and not bool(context.get("has_plan")):
        return "I can help design a civil site plan, explain tradeoffs, or guide you through the inputs I need. Start by telling me the site type and what you want to build."
    return (
        "I’m here with you. Ask me about the current design, change a setting, or tell me what you want me to create or modify."
        + _current_project_fragment(context)
    )


def _settings_reply(overrides: Dict[str, Any]) -> str:
    parts: List[str] = []
    if "strategyMode" in overrides:
        parts.append("switched Assisted on" if overrides["strategyMode"] == "assisted" else "switched Assisted off")
    for key, label in [
        ("roads", "roads"),
        ("grading", "grading"),
        ("drainage", "drainage"),
        ("utilities", "utilities"),
    ]:
        if key in overrides:
            parts.append(f"{'enabled' if overrides[key] else 'disabled'} {label}")
    if overrides.get("siteName"):
        parts.append(f"project name set to {overrides['siteName']}")
    if overrides.get("fileName"):
        parts.append(f"file name set to {overrides['fileName']}")
    if overrides.get("projectType"):
        parts.append(f"project type set to {str(overrides['projectType']).replace('_', ' ')}")
    if overrides.get("lotWidth") or overrides.get("lotHeight"):
        width = overrides.get("lotWidth") or "?"
        height = overrides.get("lotHeight") or "?"
        parts.append(f"site size updated to {width} by {height}")
    if overrides.get("parkingCount"):
        parts.append(f"parking target set to {overrides['parkingCount']}")
    if not parts:
        return "I updated the project settings."
    return "I updated the workspace: " + "; ".join(parts) + "."


def _contextual_question_reply(message: str, context: Dict[str, Any]) -> Optional[str]:
    lowered = _normalized_chat_text(message)
    structured_prompt_markers = [
        "include:",
        "requirements:",
        "output:",
        "output requirements:",
        "run this in",
        "the site must include",
    ]
    looks_like_structured_design_prompt = (
        len(message) > 180
        and (
            _looks_like_explicit_design_request(message)
            or _references_prior_design_context(message)
            or _message_has_dimension_signal(message)
        )
        and (
            any(marker in lowered for marker in structured_prompt_markers)
            or message.count("\n") >= 4
        )
    )
    if looks_like_structured_design_prompt:
        return None
    issues = context.get("issues") or []
    manual_failures = context.get("manual_failures") or []
    missing_inputs = list(context.get("missing_inputs") or [])
    explicit_blockers = list(context.get("blockers") or [])
    assumptions = context.get("assumptions") or []
    deliverables = context.get("produced_deliverables") or []
    convergence = context.get("convergence_summary") or {}
    fix_summary = convergence.get("fix_summary") or {}
    export_audit = context.get("export_audit") or {}
    blocked_exports = list(convergence.get("blocked_exports") or [])
    blocked_reasons = list(convergence.get("blocked_reasons") or [])
    for blocker in explicit_blockers:
        if blocker not in blocked_reasons:
            blocked_reasons.append(blocker)
    if isinstance(export_audit, dict) and export_audit:
        for reason in list(export_audit.get("blocked_reasons") or []):
            if reason not in blocked_reasons:
                blocked_reasons.append(reason)
        if export_audit.get("export_blocked") is True and "export_audit_blocked" not in blocked_reasons:
            blocked_reasons.append("export_audit_blocked")
        if export_audit.get("export_blocked") is True and "export" not in blocked_exports:
            blocked_exports.append("export")
    unresolved_categories = convergence.get("unresolved_issue_categories") or []
    rerun_summary = convergence.get("rerun_summary") or {}
    memory_summary = context.get("memory_summary") or {}
    remembered_examples = list(memory_summary.get("examples") or [])
    remembered_preferences = list(memory_summary.get("preferences") or [])
    remembered_constraints = list(memory_summary.get("constraints") or [])
    trust_score = context.get("engineering_trust_score")
    project_type = str(context.get("project_type") or "").strip()
    lot_width = context.get("lot_width")
    lot_height = context.get("lot_height")
    disciplines = context.get("disciplines") or {}
    active_workspace = str(context.get("active_workspace") or "").strip()
    active_panel = str(context.get("active_panel") or "").strip()
    active_tool = str(context.get("active_tool") or "").strip()
    selected_object_ids = [str(item) for item in list(context.get("selected_object_ids") or []) if str(item)]
    selected_geometry_ids = [str(item) for item in list(context.get("selected_geometry_ids") or []) if str(item)]
    site_locked = context.get("site_locked")
    address_status = str(context.get("address_status") or "").strip()
    site_size_status = str(context.get("site_size_status") or "").strip()
    standards_status = str(context.get("standards_status") or "").strip()
    existing_conditions_status = str(context.get("existing_conditions_status") or "").strip()
    engine_depth_status = str(context.get("engine_depth_status") or "").strip()
    engineer_review_status = str(context.get("engineer_review_status") or "").strip()
    recorded_next_best_action = str(context.get("next_best_action") or "").strip()

    def _format_requested_systems() -> str:
        enabled = [
            label
            for key, label in [
                ("roads", "roads and access"),
                ("grading", "grading"),
                ("drainage", "drainage and storm"),
                ("utilities", "utilities"),
            ]
            if bool(disciplines.get(key))
        ]
        return joiner if (joiner := _format_missing_requirements(enabled[:4])) else "the current design systems"

    def _current_input_needs() -> List[str]:
        asks: List[str] = []
        if not project_type:
            asks.append("site type or land use")
        if not (lot_width and lot_height):
            asks.append("rough lot size or boundary dimensions")
        if not context.get("parking_count"):
            asks.append("building and parking program")
        if bool(disciplines.get("grading")) or bool(disciplines.get("drainage")):
            asks.append("topography, slope, or survey information")
        if bool(disciplines.get("drainage")):
            asks.append("storm outfall or drainage direction")
        if bool(disciplines.get("utilities")):
            asks.append("water and sanitary tie-in assumptions")
        return asks

    def _supporting_inputs() -> List[str]:
        support: List[str] = []
        if bool(disciplines.get("roads")):
            support.append("frontage or access constraints")
        if bool(disciplines.get("grading")):
            support.append("benchmark or control elevations")
        if bool(disciplines.get("drainage")):
            support.append("existing drainage patterns or receiving point")
        if bool(disciplines.get("utilities")):
            support.append("utility maps or known connection points")
        return support

    def _workspace_state_missing() -> bool:
        return not any(
            [
                active_workspace,
                active_panel,
                active_tool,
                selected_object_ids,
                selected_geometry_ids,
                context.get("has_plan"),
                site_locked is not None,
                missing_inputs,
                blocked_reasons,
                standards_status,
                existing_conditions_status,
                engine_depth_status,
                engineer_review_status,
                recorded_next_best_action,
            ]
        )

    def _primary_next_action() -> str:
        if recorded_next_best_action:
            return recorded_next_best_action
        if site_locked is False:
            return "Lock the site boundary after confirming the address or site size."
        if missing_inputs:
            return "Provide " + _format_missing_requirements([str(item) for item in missing_inputs[:3]]) + "."
        if blocked_reasons:
            return "Clear " + "; ".join(str(item) for item in blocked_reasons[:3]) + "."
        if standards_status and standards_status not in {"accepted", "engineer_user_accepted", "complete"}:
            return "Have the engineer/user accept the applicable standards before export review."
        if existing_conditions_status and existing_conditions_status not in {"accepted", "complete", "verified"}:
            return "Provide or verify existing conditions, survey, and control evidence."
        if engine_depth_status and engine_depth_status not in {"complete", "passed", "accepted"}:
            return "Review the engine depth status and address the listed depth blockers."
        if engineer_review_status and engineer_review_status not in {"approved_external", "ready_for_engineer_review"}:
            return "Prepare the review package for engineer/user review."
        if context.get("has_plan"):
            return "Review the current design assumptions, warnings, and engineer-review blockers."
        return "Load a project or provide the site inputs needed to start."

    def _blocked_text(system_hint: str = "") -> Optional[str]:
        focused = []
        if system_hint:
            for reason in blocked_reasons:
                text = str(reason)
                if system_hint in text.lower():
                    focused.append(text)
        reasons = focused or [str(item) for item in blocked_reasons[:3] if str(item)]
        if reasons:
            return "The exact blocker is " + "; ".join(reasons[:3]) + "."
        if missing_inputs:
            return "This is blocked because Civora still needs " + _format_missing_requirements(
                [str(item) for item in missing_inputs[:3]]
            ) + "."
        return None

    if (
        "what am i doing" in lowered
        or "where am i" in lowered
        or "what is selected" in lowered
        or "what do i have selected" in lowered
        or "current workspace" in lowered
    ):
        if _workspace_state_missing():
            return "I do not have enough workspace state to know what panel, tool, or selection is active."
        parts: List[str] = []
        if active_workspace:
            parts.append(f"workspace {active_workspace}")
        if active_panel:
            parts.append(f"panel {active_panel}")
        if active_tool:
            parts.append(f"tool {active_tool}")
        if selected_geometry_ids:
            parts.append("selected geometry " + ", ".join(selected_geometry_ids[:3]))
        if selected_object_ids:
            parts.append("selected object " + ", ".join(selected_object_ids[:3]))
        if site_locked is not None:
            parts.append("site is locked" if site_locked else "site is not locked")
        if not parts:
            return "I can see the project, but I do not have active panel, tool, or selection metadata."
        return "Right now you are in " + "; ".join(parts) + "."

    if (
        "what should i do next" in lowered
        or "what next" in lowered
        or "what would you do next" in lowered
        or "what do you recommend next" in lowered
        or "what would you recommend here" in lowered
        or "what's the smartest next move" in lowered
        or "whats the smartest next move" in lowered
        or "what is the smartest next move" in lowered
        or "if you were me" in lowered
    ):
        action = _primary_next_action()
        if blocked_reasons or blocked_exports:
            return "I’d address the blockers first. Next best action: " + action
        return "Next best action: " + action

    if (
        "what is missing" in lowered
        or "what's missing" in lowered
        or "whats missing" in lowered
        or "what state is missing" in lowered
    ):
        if missing_inputs:
            return "The missing inputs are " + _format_missing_requirements([str(item) for item in missing_inputs[:5]]) + "."
        inferred = _current_input_needs()
        if inferred:
            return "From the current context, the likely missing inputs are " + _format_missing_requirements(inferred[:5]) + "."
        return "I do not see explicit missing inputs recorded in the current workspace state."

    if "what does this warning mean" in lowered or "what does this mean" in lowered:
        messages = [str(item.get("message") or item.get("code") or "").strip() for item in manual_failures[:1] if isinstance(item, dict)]
        messages += [str(item.get("message") or "").strip() for item in issues[:1] if isinstance(item, dict)]
        messages = [item for item in messages if item]
        if messages:
            return "The warning means this needs review before the package can be treated as ready_for_engineer_review: " + messages[0] + "."
        if blocked_reasons:
            return "The warning is tied to this blocker: " + str(blocked_reasons[0]) + "."
        return "I do not have a warning message in the current workspace state. Select the warning or include its text and I can explain it."

    if "why isn't this working" in lowered or "why isnt this working" in lowered or "why is this not working" in lowered:
        blocked = _blocked_text()
        if blocked:
            return blocked + " Next best action: " + _primary_next_action()
        if _workspace_state_missing():
            return "I cannot tell why this is not working because the current workspace state is missing blockers, warnings, selection, and run status."
        return "I do not see an exact blocker recorded. Next best action: " + _primary_next_action()

    if "can you fix this" in lowered or "can you fix it" in lowered:
        blocked = _blocked_text()
        if blocked:
            return blocked + " I can help with supported chat actions, but I will not pretend unsupported edits worked."
        return "I can help if the fix is a supported site, object, grading, drainage, utility, or review command. Next best action: " + _primary_next_action()

    if "what mode" in lowered or "which mode" in lowered:
        return f"You’re currently in {str(context.get('strategy_mode') or 'assisted').strip().lower()} mode."
    if "project name" in lowered or "what is this project called" in lowered:
        name = str(context.get("site_name") or context.get("current_project_name") or "").strip()
        return f"The current project is named {name}." if name else "The current project does not have a name yet."
    if "file name" in lowered:
        file_name = str(context.get("file_name") or "").strip()
        return f"The current file name is {file_name}." if file_name else "The current file name is still blank."
    if (
        "what do you remember" in lowered
        or "what are you remembering" in lowered
        or "what are you keeping in mind" in lowered
        or "what rules are you following" in lowered
    ):
        if remembered_examples:
            return "I’m keeping these instructions in mind: " + "; ".join(remembered_examples[:3]) + "."
        return "I don’t have any persistent user rules or preferences recorded from this chat yet."
    if (
        "what are my priorities" in lowered
        or "what priorities are you using" in lowered
        or "what are you prioritizing" in lowered
        or "what are you prioritising" in lowered
    ):
        if remembered_preferences:
            return "Right now I’m prioritizing these user preferences: " + "; ".join(remembered_preferences[:3]) + "."
        return "I don’t have any explicit user priorities recorded yet beyond the current design state."
    if (
        "what constraints are you following" in lowered
        or "what rules are you following" in lowered
        or "what constraints do you remember" in lowered
    ):
        if remembered_constraints:
            return "I’m keeping these constraints in mind: " + "; ".join(remembered_constraints[:3]) + "."
        return "I don’t have any explicit user constraints recorded yet beyond the current engineering blockers."
    if (
        "don't forget" in lowered
        or "dont forget" in lowered
        or "remember what i said" in lowered
        or "keep my original priorities" in lowered
    ):
        if remembered_examples:
            return "I’ve still got it. I’m keeping these earlier instructions in mind: " + "; ".join(remembered_examples[:3]) + "."
        return "I don’t see any earlier persistent rules recorded yet, so if something is especially important, tell me again and I’ll treat it as a standing instruction."
    if (
        "what do you need from me" in lowered
        or "what do you need" in lowered
        or "what information do you need" in lowered
        or "what info do you need" in lowered
        or "what should i give you" in lowered
    ):
        asks = _current_input_needs()
        if asks:
            return "The most useful inputs right now are " + _format_missing_requirements(asks[:4]) + "."
        support = _supporting_inputs()
        if support:
            return "The core design inputs are already there. The next most useful supporting information would be " + _format_missing_requirements(support[:4]) + "."
        return "You already have the core inputs I’d normally ask for. At this point I’d focus on reviewing the current design outputs and tightening any open review items."
    if (
        "what do i need before export" in lowered
        or "what do we need before export" in lowered
        or "what is needed before export" in lowered
        or "ready for export" in lowered
        or "export ready" in lowered
        or "why can't i export" in lowered
        or "why cant i export" in lowered
        or "why can’t i export" in lowered
    ):
        needs: List[str] = []
        if blocked_exports or blocked_reasons:
            needs.append("resolve blockers: " + "; ".join(str(item) for item in (blocked_reasons[:2] or blocked_exports[:2])))
        if unresolved_categories:
            needs.append("review " + ", ".join(str(item) for item in unresolved_categories[:2]))
        if assumptions:
            fields = [
                str(item.get("field_name") or item.get("field") or "an input").replace("_", " ")
                for item in assumptions[:2]
                if isinstance(item, dict)
            ]
            fields = [item for item in fields if item]
            if fields:
                needs.append("replace assumptions for " + ", ".join(fields))
        if not deliverables:
            needs.append("generate and review deliverables")
        if needs:
            return "Before export, you need to " + _format_missing_requirements(needs[:4]) + "."
        return "I do not see recorded blockers before export right now, but I would still review assumptions, warnings, and deliverables before treating it as a review package."
    if (
        "what supplies" in lowered
        or "what materials" in lowered
        or "what equipment" in lowered
        or "what would i need" in lowered
        or "what do i need" in lowered
    ):
        asks = _current_input_needs()
        support = _supporting_inputs()
        systems = _format_requested_systems()
        parts: List[str] = []
        if asks:
            parts.append("For this design, the main missing inputs are " + _format_missing_requirements(asks[:4]))
        else:
            parts.append("The core design inputs are already in place")
        if support:
            parts.append("the most useful supporting files or field information would be " + _format_missing_requirements(support[:4]))
        parts.append(f"and the active scope is {systems}")
        return ". ".join(parts) + "."
    if (
        "what are you unsure about" in lowered
        or "what are you uncertain about" in lowered
        or "where are you uncertain" in lowered
        or "where are you unsure" in lowered
        or "what are you least confident about" in lowered
        or "what feels uncertain" in lowered
    ):
        parts: List[str] = []
        if blocked_reasons or blocked_exports:
            parts.append(
                "the main uncertainty is around "
                + "; ".join(str(item) for item in (blocked_reasons[:2] or blocked_exports[:2]))
            )
        elif unresolved_categories:
            parts.append(
                "the weakest area is still "
                + ", ".join(str(item) for item in unresolved_categories[:2])
            )
        if assumptions:
            fields = [
                str(item.get("field_name") or item.get("field") or "an input").replace("_", " ")
                for item in assumptions[:2]
                if isinstance(item, dict)
            ]
            fields = [item for item in fields if item]
            if fields:
                parts.append("some of the design still depends on assumptions about " + ", ".join(fields))
        if trust_score is not None and float(trust_score) < 85.0:
            parts.append(f"the current engineering trust score is {float(trust_score):.1f}")
        if parts:
            return "Right now, " + ". ".join(parts) + "."
        return "I don’t see a strong uncertainty signal in the current run state, but I’d still review the assumptions and deliverables before treating it as ready_for_engineer_review."
    if (
        "what would make you more confident" in lowered
        or "how can we make this more confident" in lowered
        or "what would help you be more confident" in lowered
        or "what would increase your confidence" in lowered
    ):
        asks: List[str] = []
        if blocked_reasons or blocked_exports:
            asks.append("clear the active blockers")
        if unresolved_categories:
            asks.append("tighten the open review areas in " + ", ".join(str(item) for item in unresolved_categories[:2]))
        if assumptions:
            fields = [
                str(item.get("field_name") or item.get("field") or "an input").replace("_", " ")
                for item in assumptions[:2]
                if isinstance(item, dict)
            ]
            fields = [item for item in fields if item]
            if fields:
                asks.append("replace assumptions with explicit inputs for " + ", ".join(fields))
        if not asks:
            asks.append("do one more careful review of the current deliverables")
        return "The best next step would be to " + _format_missing_requirements(asks[:3]) + "."
    if (
        "summarize" in lowered
        or "sum it up" in lowered
        or "short version" in lowered
        or "quick summary" in lowered
        or "tldr" in lowered
    ):
        parts: List[str] = []
        if assumptions:
            fields = [
                str(item.get("field_name") or item.get("field") or "an input").replace("_", " ")
                for item in assumptions[:2]
                if isinstance(item, dict)
            ]
            fields = [item for item in fields if item]
            if fields:
                parts.append("assumptions: " + ", ".join(fields))
        autofix_actions = [str(item) for item in list(fix_summary.get("autofix_actions") or []) if str(item)]
        if autofix_actions:
            parts.append("fixes: " + ", ".join(autofix_actions[:2]))
        if unresolved_categories:
            parts.append("review: " + ", ".join(str(item) for item in unresolved_categories[:2]))
        if blocked_exports or blocked_reasons:
            parts.append("blocked: " + "; ".join(str(item) for item in (blocked_reasons[:2] or blocked_exports[:2])))
        if parts:
            return "Short version: " + ". ".join(parts) + "."
        return "Short version: I don’t see any major blockers recorded right now, but I’d still review the current design before treating it as ready_for_engineer_review."
    if (
        "what assumptions" in lowered
        or "where did ai help" in lowered
        or "what did ai use" in lowered
        or "what assumptions did you use" in lowered
        or "what assumptions did you make" in lowered
        or "que asum" in lowered
    ):
        if assumptions:
            formatted = []
            for item in assumptions[:3]:
                field = str(item.get("field_name") or "an input").replace("_", " ")
                reason = str(item.get("reason") or "").strip()
                formatted.append(f"{field} ({reason})" if reason else field)
            return "AI helped fill in: " + "; ".join(formatted) + "."
        return "There are no explicit AI-filled assumptions recorded on the current design."
    if (
        "what did you fix" in lowered
        or "what did you change" in lowered
        or "what got fixed" in lowered
        or "what did you do" in lowered
        or "what did you adjust" in lowered
    ):
        autofix_actions = [str(item) for item in list(fix_summary.get("autofix_actions") or []) if str(item)]
        dominant_targets = [str(item) for item in list(convergence.get("dominant_issue_categories") or []) if str(item)]
        if autofix_actions or dominant_targets:
            parts: List[str] = []
            if autofix_actions:
                parts.append("I applied: " + ", ".join(autofix_actions[:3]))
            if dominant_targets:
                parts.append("The main fix targets were " + ", ".join(dominant_targets[:3]))
            return ". ".join(parts) + "."
        return "I don’t have any recorded fix actions on the current design."
    if (
        "what changed" in lowered
        or "what's different" in lowered
        or "whats different" in lowered
        or "what is different" in lowered
        or "did this improve" in lowered
        or "is this better than before" in lowered
        or "is this better now" in lowered
        or "compare this to before" in lowered
    ):
        parts: List[str] = []
        autofix_actions = [str(item) for item in list(fix_summary.get("autofix_actions") or []) if str(item)]
        if autofix_actions:
            parts.append("changes: " + ", ".join(autofix_actions[:3]))
        rerun_total = rerun_summary.get("total_reruns")
        if rerun_total:
            parts.append(f"reruns: {int(rerun_total)}")
        if blocked_exports or blocked_reasons:
            parts.append("still blocked: " + "; ".join(str(item) for item in (blocked_reasons[:2] or blocked_exports[:2])))
        elif unresolved_categories:
            parts.append("still needs review: " + ", ".join(str(item) for item in unresolved_categories[:2]))
        else:
            parts.append("no explicit blockers are recorded right now")
        if parts:
            return "Compared with the earlier state, " + ". ".join(parts) + "."
        return "I don’t have enough recorded change history to compare this to the earlier state yet."
    if (
        "which version is better" in lowered
        or "which version do you think is better" in lowered
        or "which one is better" in lowered
        or "which approach is better" in lowered
    ):
        if blocked_exports or blocked_reasons:
            return "The safer version is the one with fewer blockers. Right now I’d favor the current direction only if we can clear " + "; ".join(
                str(item) for item in (blocked_reasons[:2] or blocked_exports[:2])
            ) + "."
        if unresolved_categories:
            return "I’d favor the version with fewer open review items. Right now the biggest comparison pressure is in " + ", ".join(
                str(item) for item in unresolved_categories[:2]
            ) + "."
        if remembered_preferences:
            return "Based on your priorities, I’d favor the version that better respects " + "; ".join(remembered_preferences[:2]) + "."
        return "I’d usually favor the version with fewer blockers, fewer review items, and fewer design assumptions."
    if (
        "why is that better" in lowered
        or "why is it better" in lowered
        or "why do you think that is better" in lowered
    ):
        if blocked_exports or blocked_reasons:
            return "Because the stronger option is usually the one with fewer blockers, and right now the blocking pressure is " + "; ".join(
                str(item) for item in (blocked_reasons[:2] or blocked_exports[:2])
            ) + "."
        if unresolved_categories:
            return "Because I’d rather trust the version with fewer unresolved review items, especially around " + ", ".join(
                str(item) for item in unresolved_categories[:2]
            ) + "."
        if remembered_preferences:
            return "Because it fits the priorities you gave me better, especially " + "; ".join(remembered_preferences[:2]) + "."
        return "Because I’d rather keep the version that is simpler, more stable, and less assumption-heavy."
    if "what needs review" in lowered or "what should i review" in lowered:
        review_items = [str(item) for item in unresolved_categories if str(item)]
        if manual_failures:
            messages = [str(item.get("message") or "").strip() for item in manual_failures[:3] if isinstance(item, dict)]
            messages = [item for item in messages if item]
            if messages:
                return "You should review: " + "; ".join(messages) + "."
        if issues:
            messages = [str(item.get("message") or "").strip() for item in issues[:3] if isinstance(item, dict)]
            messages = [item for item in messages if item]
            if messages:
                return "You should review: " + "; ".join(messages) + "."
        if review_items:
            return "The main review categories are: " + ", ".join(review_items[:3]) + "."
        return "I don’t see any explicit review items recorded on the current design."
    if (
        "what is blocked" in lowered
        or "what's blocked" in lowered
        or "whats blocked" in lowered
        or "why is it blocked" in lowered
        or "why did it block" in lowered
        or "why is export blocked" in lowered
        or "why can't i export" in lowered
        or "why cant i export" in lowered
        or "why can’t i export" in lowered
        or "why is storm blocked" in lowered
        or "why is drainage blocked" in lowered
        or "why generate drainage blocked" in lowered
        or "why drainage blocked" in lowered
        or "why is utility blocked" in lowered
        or "why are utilities blocked" in lowered
        or "why is grading blocked" in lowered
        or "why did export fail" in lowered
        or "por que esta bloqueado" in lowered
    ):
        if blocked_exports or blocked_reasons:
            parts: List[str] = []
            if blocked_exports:
                parts.append("blocked outputs: " + ", ".join(str(item) for item in blocked_exports[:3]))
            if blocked_reasons:
                parts.append("reasons: " + "; ".join(str(item) for item in blocked_reasons[:3]))
            return "Right now, " + ". ".join(parts) + "."
        return "Nothing is explicitly blocked right now."
    if (
        "how many passes" in lowered
        or "how many reruns" in lowered
        or "did it converge" in lowered
        or "did this converge" in lowered
        or "how long did it take" in lowered
    ):
        passes_run = convergence.get("passes_run")
        rerun_total = rerun_summary.get("total_reruns")
        converged = convergence.get("converged")
        parts: List[str] = []
        if passes_run is not None:
            parts.append(f"it took {int(passes_run)} pass{'es' if int(passes_run) != 1 else ''}")
        if rerun_total is not None:
            parts.append(f"{int(rerun_total)} rerun{'s' if int(rerun_total) != 1 else ''}")
        if converged is True:
            parts.append("and it converged")
        elif converged is False:
            parts.append("and it did not fully converge")
        if parts:
            return "The latest run " + " ".join(parts) + "."
    if "is this good" in lowered or "does this look good" in lowered or "is it good" in lowered:
        if blocked_exports or blocked_reasons:
            return "It’s not fully ready yet. The biggest blockers right now are " + "; ".join(
                str(item) for item in (blocked_reasons[:2] or blocked_exports[:2])
            ) + "."
        if unresolved_categories or issues or manual_failures:
            review_text = (
                ", ".join(str(item) for item in unresolved_categories[:2])
                or "; ".join(
                    str(item.get("message") or "").strip()
                    for item in (manual_failures[:1] + issues[:1])
                    if isinstance(item, dict)
                )
            )
            if review_text:
                return f"It’s moving in the right direction, but I’d still review {review_text} before treating it as ready_for_engineer_review."
        return "Yes, it looks reasonably strong from the current run state. I don’t see any explicit blockers recorded right now."
    if (
        "what should i focus on" in lowered
        or "what should we focus on" in lowered
        or "what should i prioritize" in lowered
        or "what should we prioritize" in lowered
        or "what is the best option" in lowered
        or "what's the best option" in lowered
        or "whats the best option" in lowered
    ):
        if blocked_exports or blocked_reasons:
            return "I’d focus first on clearing " + "; ".join(
                str(item) for item in (blocked_reasons[:2] or blocked_exports[:2])
            ) + " because that is what still blocks the strongest engineer-review package."
        if unresolved_categories:
            return "I’d focus first on " + ", ".join(
                str(item) for item in unresolved_categories[:2]
            ) + " because that is where the current design still looks weakest."
        if remembered_preferences:
            return "Given your priorities, the best option is the one that keeps emphasizing " + "; ".join(
                remembered_preferences[:2]
            ) + "."
        return "I’d focus on the cleanest next revision you care about most, then review the deliverables again before changing more things."
    if (
        "what are the tradeoffs" in lowered
        or "what tradeoffs" in lowered
        or "what are the trade-offs" in lowered
        or "what trade offs" in lowered
    ):
        parts: List[str] = []
        if remembered_preferences:
            parts.append("I’m currently weighting " + "; ".join(remembered_preferences[:2]))
        if assumptions:
            fields = [
                str(item.get("field_name") or item.get("field") or "an input").replace("_", " ")
                for item in assumptions[:2]
                if isinstance(item, dict)
            ]
            fields = [item for item in fields if item]
            if fields:
                parts.append("some inputs were assumed, especially " + ", ".join(fields))
        if unresolved_categories:
            parts.append("the main tradeoff pressure is in " + ", ".join(str(item) for item in unresolved_categories[:2]))
        if parts:
            return "The main tradeoffs right now are that " + ". ".join(parts) + "."
        return "I don’t see a strong tradeoff signal recorded yet beyond the normal balance between layout quality, drainage, and utility coordination."
    if (
        "what are the risks" in lowered
        or "what risks" in lowered
        or "what is risky" in lowered
        or "what's risky" in lowered
        or "whats risky" in lowered
    ):
        if blocked_exports or blocked_reasons:
            return "The biggest risks right now are " + "; ".join(str(item) for item in (blocked_reasons[:3] or blocked_exports[:3])) + "."
        if unresolved_categories:
            return "The biggest risks right now are in " + ", ".join(str(item) for item in unresolved_categories[:3]) + "."
        if assumptions:
            fields = [
                str(item.get("field_name") or item.get("field") or "an input").replace("_", " ")
                for item in assumptions[:2]
                if isinstance(item, dict)
            ]
            fields = [item for item in fields if item]
            if fields:
                return "The main risk right now is that parts of the design still depend on assumptions, especially " + ", ".join(fields) + "."
        return "I don’t see any major recorded risks beyond the normal need to review the current design before treating it as ready_for_engineer_review."
    if "what would you change" in lowered or "what should change" in lowered:
        if blocked_reasons or unresolved_categories:
            focus = ", ".join(str(item) for item in (unresolved_categories[:2] or blocked_reasons[:2]))
            if focus:
                return "I’d focus first on " + focus + " because that’s where the current design still looks weakest."
        if issues:
            messages = [str(item.get("message") or "").strip() for item in issues[:2] if isinstance(item, dict)]
            messages = [item for item in messages if item]
            if messages:
                return "I’d probably tighten up " + "; ".join(messages) + "."
        return "I wouldn’t force another change yet unless you want a different design direction or tighter constraints."
    if (
        "are you sure" in lowered
        or "how confident are you" in lowered
        or "can i trust this" in lowered
    ):
        blocked = list(blocked_reasons or blocked_exports)
        if blocked:
            return "Not fully yet. I’d be careful because there are still active blockers: " + "; ".join(
                str(item) for item in blocked[:3]
            ) + "."
        if trust_score is not None:
            return f"The current engineering trust score is {float(trust_score):.1f}. I’d still review the assumptions and any recorded warnings before treating it as ready_for_engineer_review."
        return "I’d still treat it as something to review, not blindly trust, unless the blockers and review items are clear."
    if (
        "what are my options" in lowered
        or "what are the options" in lowered
        or "what can i do next" in lowered
        or "give me options" in lowered
    ):
        options: List[str] = []
        if blocked_exports or blocked_reasons:
            options.append("clear the blockers first")
        if unresolved_categories or issues or manual_failures:
            options.append("review the open issues before changing more geometry")
        if bool(context.get("has_plan")):
            options.append("tell me one targeted design change to make next")
            options.append("ask me for a short summary of assumptions and fixes")
        if not options:
            options.append("give me the next design direction or site constraint")
        return "You can " + _format_missing_requirements(options[:4]) + "."
    if (
        "this looks wrong" in lowered
        or "this is wrong" in lowered
        or "that looks wrong" in lowered
        or "that is wrong" in lowered
        or "this doesn't make sense" in lowered
        or "that doesn't make sense" in lowered
        or "i don't like this" in lowered
        or "i dont like this" in lowered
    ):
        if blocked_exports or blocked_reasons:
            return "That’s fair. The strongest reason to distrust it right now is " + "; ".join(
                str(item) for item in (blocked_reasons[:2] or blocked_exports[:2])
            ) + ". If you want, tell me what feels off and I’ll focus there."
        if unresolved_categories or issues or manual_failures:
            focus = ", ".join(str(item) for item in unresolved_categories[:2])
            if not focus:
                messages = [str(item.get("message") or "").strip() for item in (manual_failures[:1] + issues[:1]) if isinstance(item, dict)]
                focus = "; ".join(item for item in messages if item)
            if focus:
                return f"That may be because the weakest part right now is {focus}. Tell me what seems off and I’ll narrow it down."
        return "Understood. Tell me what seems off to you and I’ll either explain it, review it, or revise that part of the design."
    if (
        "that doesn't help" in lowered
        or "that doesnt help" in lowered
        or "be more specific" in lowered
        or "be specific" in lowered
        or "rephrase that" in lowered
        or "say that again" in lowered
        or "make that simpler" in lowered
        or lowered == "simpler"
    ):
        if blocked_exports or blocked_reasons:
            return "In simple terms: the design is still blocked by " + "; ".join(
                str(item) for item in (blocked_reasons[:2] or blocked_exports[:2])
            ) + ". If you want, I can walk through one blocker at a time."
        if unresolved_categories:
            return "In simple terms: the main thing that still needs work is " + ", ".join(
                str(item) for item in unresolved_categories[:2]
            ) + "."
        if assumptions:
            fields = [
                str(item.get("field_name") or item.get("field") or "an input").replace("_", " ")
                for item in assumptions[:2]
                if isinstance(item, dict)
            ]
            fields = [item for item in fields if item]
            if fields:
                return "In simple terms: I had to assume " + ", ".join(fields) + "."
        return "In simple terms: tell me what you want to change, and I’ll focus just on that."
    if (
        "i disagree" in lowered
        or "you're wrong" in lowered
        or "you are wrong" in lowered
    ):
        if blocked_exports or blocked_reasons or unresolved_categories:
            focus = "; ".join(str(item) for item in (blocked_reasons[:2] or blocked_exports[:2])) or ", ".join(
                str(item) for item in unresolved_categories[:2]
            )
            return "Fair enough. The weakest part I’d revisit first is " + focus + ". Tell me what you disagree with and I’ll focus there."
        return "Fair enough. Tell me what you think is wrong, and I’ll either explain it more clearly or revise that part of the design."
    if "what warnings" in lowered or "what issues" in lowered or "what's wrong" in lowered or "whats wrong" in lowered:
        messages = [str(item.get("message") or "").strip() for item in manual_failures[:2] if isinstance(item, dict)]
        messages += [str(item.get("message") or "").strip() for item in issues[:2] if isinstance(item, dict)]
        messages = [item for item in messages if item]
        if messages:
            return "The main issues right now are: " + "; ".join(messages) + "."
        return "I don’t see any active blockers or warnings on the current design."
    if "what did you produce" in lowered or "what was produced" in lowered or "what deliverables" in lowered:
        if deliverables:
            return "The current design produced: " + ", ".join(str(item) for item in deliverables[:6]) + "."
        return "There are no finished deliverables in the current workspace yet."
    if "trust" in lowered or "truth" in lowered:
        truth_success = context.get("truth_success")
        trust_score = context.get("engineering_trust_score")
        engineering_status = str(context.get("engineering_status") or "").strip()
        parts: List[str] = []
        if trust_score is not None:
            parts.append(f"trust score {float(trust_score):.1f}")
        if truth_success is True:
            parts.append("truth checks are currently passing")
        elif truth_success is False:
            parts.append("truth checks still need review")
        if engineering_status:
            parts.append(f"engineering status is {engineering_status}")
        if parts:
            return "Right now, " + ", and ".join(parts) + "."
    if ("why" in lowered or "explain" in lowered) and (
        context.get("explanation_summary")
        or issues
        or manual_failures
        or context.get("has_plan")
    ):
        base = str(context.get("explanation_summary") or "").strip()
        extras = []
        if manual_failures:
            extras.append(
                "Current blockers: "
                + "; ".join(
                    str(item.get("message") or item.get("code") or "").strip()
                    for item in manual_failures[:2]
                    if isinstance(item, dict)
                )
            )
        elif issues:
            extras.append(
                "Current warnings: "
                + "; ".join(
                    str(item.get("message") or "").strip()
                    for item in issues[:2]
                    if isinstance(item, dict)
                )
            )
        if base or extras:
            return " ".join(part for part in [base, *extras] if part).strip()
    return None


def _looks_like_explicit_design_request(text: str) -> bool:
    normalized = _normalized_chat_text(text)
    strong_design_phrases = [
        "create a",
        "create an",
        "design a",
        "design an",
        "generate a",
        "generate an",
        "make a",
        "make an",
        "build a",
        "build an",
        "update the design",
        "revise the design",
        "move the building",
        "add parking",
        "add drainage",
        "add utilities",
        "reroute",
    ]
    if any(phrase in normalized for phrase in strong_design_phrases):
        return True
    if any(
        keyword in normalized
        for keyword in ["site plan", "grading plan", "drainage plan", "utility plan"]
    ):
        return True
    return False


def _looks_like_assisted_scope_confirmation(text: str) -> bool:
    normalized = _normalized_chat_text(text)
    if not normalized:
        return False
    confirmation_phrases = [
        "yes assist",
        "yes, assist",
        "use ai assistance",
        "use ai help",
        "go ahead and assist",
        "go ahead with ai assistance",
        "help fill in the missing details",
        "fill in the missing details",
        "fill in the blanks",
        "infer the missing details",
        "make the assumptions you need",
        "make reasonable assumptions",
        "you can infer the rest",
    ]
    if any(phrase in normalized for phrase in confirmation_phrases):
        return True
    return normalized in {
        "assist",
        "yes assist me",
        "yes use ai",
        "go ahead and do it with ai",
    }


def _last_design_request_from_history(context: Dict[str, Any]) -> str:
    history = list(context.get("chat_history") or [])
    for item in reversed(history):
        if str(item.get("role") or "").strip().lower() != "user":
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        if _looks_like_assisted_scope_confirmation(content):
            continue
        normalized = _normalized_chat_text(content)
        if (
            _looks_like_explicit_design_request(content)
            or _message_has_dimension_signal(content)
            or any(
                phrase in normalized
                for phrase in [
                    "site plan",
                    "civil site plan",
                    "grading",
                    "drainage",
                    "storm",
                    "sanitary",
                    "water",
                    "parking",
                    "building",
                ]
            )
        ):
            return content
    return ""


def _is_explicit_plan_tool_request(text: str, tool: str) -> bool:
    normalized = _normalized_chat_text(text)
    explicit_phrases = {
        "fix": [
            "fix this",
            "fix the design",
            "fix issues",
            "fix the issues",
            "resolve the issues",
            "resolve conflicts",
            "run a fix pass",
            "fix this and",
            "fix it and",
        ],
        "improve": [
            "improve this",
            "improve the design",
            "make this better",
            "optimize this",
            "run an improvement pass",
        ],
    }
    phrases = explicit_phrases.get(tool, [])
    if any(phrase in normalized for phrase in phrases):
        return True
    return normalized.startswith(f"{tool} ")


def _clarifying_design_reply(context: Dict[str, Any]) -> str:
    project_type = str(context.get("project_type") or "").strip()
    strategy_mode = str(context.get("strategy_mode") or "assisted").strip().lower()
    missing: List[str] = []
    if not project_type:
        missing.append("what kind of site you want")
    lot_known = bool(context.get("lot_width")) and bool(context.get("lot_height"))
    if not lot_known:
        missing.append("rough lot size")
    missing.append("what systems matter most")
    ask = ", ".join(missing[:3])
    assist_line = (
        " If you want, I can stay within exactly what you asked for, or I can assist by filling in only the missing engineering details once you say yes."
        if strategy_mode == "assisted"
        else ""
    )
    return (
        "I can help with that. Before I generate a design, tell me "
        f"{ask}. For example: site type, approximate lot dimensions, parking target, and whether roads, grading, drainage, or utilities should be included.{assist_line}"
    )


def _format_missing_requirements(missing: List[str]) -> str:
    cleaned = [item.strip() for item in missing if item and item.strip()]
    if not cleaned:
        return "a little more design context"
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _remembered_instruction_fragment(context: Dict[str, Any]) -> str:
    memory_summary = context.get("memory_summary") or {}
    examples = list(memory_summary.get("examples") or [])
    if not examples:
        return ""
    remembered = str(examples[-1]).strip()
    if not remembered:
        return ""
    return f" I’ll keep your earlier instruction in mind: {remembered}."


def _current_project_fragment(context: Dict[str, Any]) -> str:
    project_name = str(context.get("site_name") or context.get("current_project_name") or "").strip()
    if not project_name:
        return ""
    return f" We’re currently working in {project_name}."


def _structured_clarification_reply(
    *,
    context: Dict[str, Any],
    missing: List[str],
    inferred_project_type: str,
) -> str:
    strategy_mode = str(context.get("strategy_mode") or "assisted").strip().lower()
    primary_missing = missing[:2]
    ask = _format_missing_requirements(primary_missing)
    prompt_parts: List[str] = []
    if inferred_project_type:
        prompt_parts.append(
            f"I understand that you want a {inferred_project_type.replace('_', ' ')} design."
        )
    else:
        prompt_parts.append("I can help with that design.")
    prompt_parts.append(f"Before I move forward, I still need {ask}.")

    examples: List[str] = []
    if any("site type" in item or "land use" in item for item in primary_missing):
        examples.append("site type or land use")
    if any("lot" in item or "site area" in item for item in primary_missing):
        examples.append("rough lot size or site area")
    if any("building" in item or "parking" in item or "program" in item for item in primary_missing):
        examples.append("building or parking program")
    if any("terrain" in item or "slope" in item for item in primary_missing):
        examples.append("terrain or slope information")
    if any("systems" in item for item in primary_missing):
        examples.append("which systems to include")
    if examples:
        prompt_parts.append("Tell me " + _format_missing_requirements(examples[:2]) + ".")

    if strategy_mode == "assisted":
        prompt_parts.append(
            "If you want, I can stay within exactly what you asked for, or I can fill in only the missing engineering details once you say yes."
        )

    return " ".join(prompt_parts) + _remembered_instruction_fragment(context)


def _clarifying_ambiguous_reply(context: Dict[str, Any]) -> str:
    if bool(context.get("has_plan")):
        return (
            "I’m not fully sure what you want me to change yet. Tell me what part of the current design you want to update, "
            "what outcome you want, or ask me a specific question about assumptions, fixes, review items, or blockers."
        ) + _remembered_instruction_fragment(context)
    return (
        "I’m not fully sure what you want me to do yet. Tell me whether you want a new design, a settings change, or an explanation. "
        "If you want a design, give me the site type, rough size, and the main systems you want included."
    ) + _remembered_instruction_fragment(context)


def _safe_positive_number(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
        return parsed if parsed > 0 else None
    except Exception:
        return None


def _message_has_dimension_signal(message: str) -> bool:
    lowered = _normalized_chat_text(message)
    patterns = [
        r"\b\d+(?:\.\d+)?\s*(?:x|by)\s*\d+(?:\.\d+)?\b",
        r"\b\d+(?:\.\d+)?\s*(?:ft|feet|m|meters|ac|acre|acres)\b",
        r"\b\d+(?:\.\d+)?\s*%\s*slope\b",
    ]
    return any(re.search(pattern, lowered) for pattern in patterns)


def _infer_project_type_from_message(message: str) -> str:
    lowered = _normalized_chat_text(message)
    project_keywords = {
        "mixed_use": ["mixed-use", "mixed use"],
        "multifamily": ["multifamily", "multi-family", "apartment", "apartments"],
        "retail": ["retail", "shopping center"],
        "office": ["office", "office park"],
        "industrial": ["industrial", "warehouse", "distribution"],
        "commercial_pad": ["commercial", "pad site", "commercial pad"],
    }
    for project_type, keywords in project_keywords.items():
        if any(keyword in lowered for keyword in keywords):
            return project_type
    if (
        any(keyword in lowered for keyword in ["site plan", "civil site plan", "lot", "driveway"])
        and _message_has_dimension_signal(message)
        and any(keyword in lowered for keyword in ["building", "parking", "pad", "road", "drainage"])
    ):
        return "generic_site"
    return ""


def _extract_site_area_acres(message: str) -> Optional[str]:
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:ac|acre|acres)\b", _normalized_chat_text(message))
    return match.group(1) if match else None


def _command_family(message: str) -> str:
    lowered = _normalized_chat_text(message)
    if _is_responsibility_blocked_request(message):
        return "responsibility_guard"
    if any(phrase in lowered for phrase in ["what do i need before export", "before export", "export ready", "ready to export"]):
        return "export_readiness"
    if re.search(r"\bwhy\b.*\b(storm|drainage|export|utility|utilities|grading)\b.*\b(blocked|failed|stuck)\b", lowered):
        return "blocker_explanation"
    if any(phrase in lowered for phrase in ["use assisted mode", "turn on assisted", "enable assisted", "assisted mode", "don't assume anything", "dont assume anything", "no assumptions"]):
        return "mode_command"
    if any(phrase in lowered for phrase in ["generate drainage", "generate storm", "run drainage", "design drainage", "design storm"]):
        return "drainage_command"
    if any(phrase in lowered for phrase in ["generate grading", "run grading", "grade the site", "create contours", "generate contours"]):
        return "grading_command"
    if any(phrase in lowered for phrase in ["generate utilities", "run utilities", "design utilities", "water system", "sanitary system", "sewer system"]):
        return "utility_command"
    if any(phrase in lowered for phrase in ["generate systems", "generate the systems", "generate everything", "run the engines", "run all systems"]):
        return "generate_command"
    if any(target in lowered for target in ["building", "basin", "detention", "parking", "road", "protected zone", "protected_zone", "wetland", "buffer"]) and any(
        verb in lowered for verb in ["add", "put", "place", "make", "change", "move", "fit"]
    ):
        if "site" in lowered and _extract_site_area_acres(message):
            return "site_update"
        return "object_or_layout_command"
    if any(phrase in lowered for phrase in ["make the site", "site area", "lot area"]) and _extract_site_area_acres(message):
        return "site_update"
    return "conversation"


def _is_responsibility_blocked_request(message: str) -> bool:
    lowered = _normalized_chat_text(message)
    return any(
        phrase in lowered
        for phrase in [
            "approve this",
            "approve it",
            "stamp it",
            "seal it",
            "sign off",
            "signoff",
            "certify",
            "do full construction set",
            "full construction set",
            "issue for construction",
            "ifc set",
            "construction approved",
        ]
    )


def _looks_unsupported_or_random(message: str) -> bool:
    lowered = _normalized_chat_text(message)
    if not lowered:
        return False
    if _is_question(message) or _is_casual_chat_message(message):
        return False
    if _has_edit_intent(message) or _looks_like_explicit_design_request(message):
        return False
    tokens = re.findall(r"[a-z0-9']+", lowered)
    if len(tokens) <= 2:
        return True
    civil_tokens = {
        "site",
        "building",
        "road",
        "parking",
        "grading",
        "drainage",
        "storm",
        "utility",
        "utilities",
        "water",
        "sanitary",
        "basin",
        "export",
        "standards",
        "survey",
        "plan",
        "geometry",
        "polygon",
    }
    action_tokens = {"make", "add", "change", "move", "generate", "run", "use", "turn", "set", "explain", "fix", "improve"}
    return not any(token in civil_tokens or token in action_tokens for token in tokens)


def _affected_systems_for_command(command_intent: str, message: str) -> List[str]:
    lowered = _normalized_chat_text(message)
    systems: List[str] = []
    mapping = [
        ("site", ["site", "lot", "acre"]),
        ("layout", ["building", "parking", "road", "layout", "basin", "detention"]),
        ("grading", ["grading", "grade", "contour", "slope", "low corner"]),
        ("drainage", ["drainage", "storm", "detention", "basin", "outfall", "inlet", "pipe"]),
        ("utilities", ["utility", "utilities", "water", "sanitary", "sewer"]),
        ("export", ["export", "deliverable"]),
    ]
    for system, tokens in mapping:
        if any(token in lowered for token in tokens):
            systems.append(system)
    if command_intent == "grading_command":
        systems.append("grading")
    if command_intent == "drainage_command":
        systems.extend(["drainage", "grading"])
    if command_intent == "utility_command":
        systems.append("utilities")
    if command_intent == "generate_command":
        systems.extend(["layout", "grading", "drainage", "utilities"])
    if command_intent == "export_readiness":
        systems.append("export")
    return list(dict.fromkeys(systems))


def _missing_inputs_for_command(command_intent: str, message: str, context: Dict[str, Any]) -> List[str]:
    lowered = _normalized_chat_text(message)
    missing: List[str] = []
    has_plan = bool(context.get("has_plan"))
    if command_intent in {"object_or_layout_command", "grading_command", "drainage_command", "utility_command", "generate_command"} and not has_plan:
        explicit_site_size = (
            bool(re.search(r"\b(?:site|lot)\b.*\b\d+(?:\.\d+)?\s*(?:ft|feet|m|meters)?\s*(?:x|by)\s*\d+(?:\.\d+)?", lowered))
            or bool(_extract_site_area_acres(message))
        )
        if not _ctx_has_site_size(context) and not explicit_site_size:
            missing.append("site size or boundary")
    if command_intent == "object_or_layout_command":
        object_payload = _extract_object_command_payload(message, context)
        strict_policy = object_payload.get("assumption_policy") == "strict"
        if (
            "building" in lowered
            and any(phrase in lowered for phrase in ["add a", "add one", "place a", "put a", "create a", "new building"])
            and not re.search(r"\b\d+(?:\.\d+)?\s*(?:ft|feet|m|meters)?\s*(?:x|by)\s*\d+(?:\.\d+)?", lowered)
        ):
            missing.append("building dimensions")
        if (
            strict_policy
            and object_payload.get("operation") == "create"
            and object_payload.get("object_type") in {"building", "detention_basin", "parking"}
            and not object_payload.get("location_hint")
        ):
            missing.append("object location")
        if "basin" in lowered or "detention" in lowered:
            if not (
                _ctx_has_low_point(context)
                or _ctx_has_referenced_geometry(context)
                or any(token in lowered for token in ["this", "that", "selected", "drawn", "polygon", "shape", "geometry"])
                or "low corner" in lowered
                or any(corner in lowered for corner in ["northwest", "northeast", "southwest", "southeast"])
            ):
                missing.append("basin location or low point")
        if "change the road" in lowered or lowered in {"change road", "change the roads"}:
            missing.append("what road change you want")
    if command_intent == "grading_command" and not any(token in lowered for token in ["slope", "contour", "elevation", "low", "high"]) and not _ctx_has_low_point(context):
        missing.append("terrain, slope, or target drainage direction")
    if command_intent == "drainage_command":
        if not _ctx_has_drainage_target(context) and not any(token in lowered for token in ["basin", "outfall", "pond", "low corner"]):
            missing.append("detention basin or outfall target")
    if command_intent == "utility_command" and not _ctx_has_utility_tie_ins(context):
        missing.append("water and sanitary tie-in locations or assumptions")
    if command_intent == "object_or_layout_command" and "parking" in lowered and "fit" in lowered and not (_ctx_has_buildings(context) or "building" in lowered):
        missing.append("building program or occupancy target")
    return list(dict.fromkeys(missing))


def _specific_missing_question(command_intent: str, missing: List[str], context: Dict[str, Any]) -> str:
    if not missing:
        return ""
    first = missing[0]
    if command_intent == "drainage_command":
        return "I can generate drainage, but I need the detention basin or outfall target first. Where should stormwater discharge or be stored?"
    if command_intent == "grading_command":
        return "I can generate grading, but I need terrain direction first. What is the high side, low side, or approximate slope?"
    if command_intent == "utility_command":
        return "I can generate utilities, but I need tie-in assumptions first. Where should water and sanitary connect?"
    if command_intent == "object_or_layout_command" and "building dimensions" in missing:
        return "I can add the building, but I need its footprint dimensions first, for example 100 ft by 60 ft."
    if command_intent == "object_or_layout_command" and "object location" in missing:
        return "I can create that object in strict mode, but I need its location first, for example north side, southeast corner, or x/y coordinates."
    if command_intent == "object_or_layout_command" and "what road change you want" in missing:
        return "I can change the road, but I need the target change: move it, widen it, reroute it, add an entrance, or reduce its footprint?"
    return "I can do that, but I need " + _format_missing_requirements(missing[:2]) + " first."


def _metadata_for_decision(
    *,
    command_intent: str,
    missing: Optional[List[str]] = None,
    action_taken: str = "responded",
    action_blocked_reason: str = "",
    affected_systems: Optional[List[str]] = None,
    assumptions: Optional[List[str]] = None,
    next_best_action: str = "",
    command_payload: Optional[Dict[str, Any]] = None,
    outcome: str = "",
    confidence: Optional[float] = None,
    state_changed: bool = False,
    unsupported_reason: str = "",
    blocker: str = "",
) -> Dict[str, Any]:
    required_missing = list(missing or [])
    resolved_outcome = outcome
    if not resolved_outcome:
        if unsupported_reason:
            resolved_outcome = "unsupported_or_not_understood"
        elif required_missing:
            resolved_outcome = "understood_needs_more_info"
        elif action_blocked_reason:
            resolved_outcome = "understood_but_blocked"
        else:
            resolved_outcome = "understood_and_executed" if state_changed else "understood_needs_more_info"
    return {
        "intent": command_intent,
        "outcome": resolved_outcome,
        "confidence": confidence,
        "state_changed": state_changed,
        "unsupported_reason": unsupported_reason,
        "blocker": blocker or action_blocked_reason,
        "required_missing_inputs": required_missing,
        "action_taken": action_taken,
        "action_blocked_reason": action_blocked_reason,
        "affected_systems": list(affected_systems or []),
        "assumptions": list(assumptions or []),
        "next_best_action": next_best_action,
        "command_payload": dict(command_payload or {}),
    }


def _attach_action_planning_metadata(decision: Dict[str, Any], action_plan: Dict[str, Any]) -> Dict[str, Any]:
    updated = dict(decision)
    metadata = dict(updated.get("response_metadata") or {})
    metadata["action_planning"] = {
        "user_goal": str(action_plan.get("user_goal") or ""),
        "candidate_actions": list(action_plan.get("candidate_actions") or []),
        "selected_action": action_plan.get("selected_action"),
        "selected_action_id": str(action_plan.get("selected_action_id") or ""),
        "confidence": float(action_plan.get("confidence") or 0.0),
        "low_confidence": bool(action_plan.get("low_confidence")),
        "missing_inputs": list(action_plan.get("missing_inputs") or []),
        "safety_blockers": list(action_plan.get("safety_blockers") or []),
        "next_best_question": str(action_plan.get("next_best_question") or ""),
    }
    metadata["action_registry"] = list(action_plan.get("action_registry") or [])
    updated["response_metadata"] = metadata
    return updated


def _context_blockers(context: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    for item in list(context.get("blockers") or []):
        text = str(item).strip()
        if text and text not in blockers:
            blockers.append(text)
    convergence = context.get("convergence_summary") or {}
    for key in ("blocked_reasons", "blocked_exports", "unresolved_issue_categories"):
        for item in list(convergence.get(key) or []):
            text = str(item).strip()
            if text and text not in blockers:
                blockers.append(text)
    export_audit = context.get("export_audit") or {}
    if isinstance(export_audit, dict):
        for item in list(export_audit.get("blocked_reasons") or []):
            text = str(item).strip()
            if text and text not in blockers:
                blockers.append(text)
        if export_audit.get("export_blocked") is True and "export_audit_blocked" not in blockers:
            blockers.append("export_audit_blocked")
    for item in list(context.get("manual_failures") or []):
        if not isinstance(item, dict):
            continue
        text = str(item.get("message") or item.get("code") or "").strip()
        if text and text not in blockers:
            blockers.append(text)
    return blockers


def _context_missing_inputs(context: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    for item in list(context.get("missing_inputs") or []):
        text = str(item).strip()
        if text and text not in missing:
            missing.append(text)
    return missing


def _context_next_best_action(context: Dict[str, Any], fallback: str) -> str:
    recorded = str(context.get("next_best_action") or "").strip()
    if recorded:
        return recorded
    missing = _context_missing_inputs(context)
    if missing:
        return "Provide " + _format_missing_requirements(missing[:3]) + "."
    blockers = _context_blockers(context)
    if blockers:
        return "Clear " + "; ".join(blockers[:3]) + "."
    if context.get("site_locked") is False:
        return "Lock the site boundary after confirming the address or site size."
    return fallback


def _extract_object_command_payload(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    lowered = _normalized_chat_text(message)
    payload: Dict[str, Any] = {}
    if "protected zone" in lowered or "protected_zone" in lowered or "wetland" in lowered or "buffer" in lowered:
        payload["object_type"] = "protected_zone"
    elif "building" in lowered:
        payload["object_type"] = "building"
    elif "basin" in lowered or "detention" in lowered or "pond" in lowered:
        payload["object_type"] = "basin"
    elif "parking" in lowered:
        payload["object_type"] = "parking"
    elif "road" in lowered:
        payload["object_type"] = "road"

    dims = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:ft|feet|m|meters)?\s*(?:x|by)\s*(\d+(?:\.\d+)?)",
        lowered,
    )
    if dims:
        payload["width"] = float(dims.group(1))
        payload["depth"] = float(dims.group(2))

    if "low corner" in lowered or "low spot" in lowered or "low point" in lowered:
        payload["location_hint"] = "low_corner"
    for corner in ["northwest", "northeast", "southwest", "southeast"]:
        if corner in lowered:
            payload["location_hint"] = f"{corner}_corner"
    if "north" in lowered and not payload.get("location_hint"):
        payload["location_hint"] = "north"
    if "south" in lowered and not payload.get("location_hint"):
        payload["location_hint"] = "south"
    if "east" in lowered and not payload.get("location_hint"):
        payload["location_hint"] = "east"
    if "west" in lowered and not payload.get("location_hint"):
        payload["location_hint"] = "west"

    if payload.get("object_type") == "parking" and "fit" in lowered:
        payload["operation"] = "fit_to_buildings"
    elif any(verb in lowered for verb in ["add", "put", "place", "create"]):
        payload["operation"] = "create"
    elif any(verb in lowered for verb in ["change", "move", "reroute", "widen", "narrow", "turn"]):
        payload["operation"] = "update"
    else:
        payload["operation"] = "update"

    if str(context.get("strategy_mode") or "").lower() in {"user", "manual"}:
        payload["assumption_policy"] = "strict"
    else:
        payload["assumption_policy"] = "assisted"
    return payload


def _build_design_readiness_reply(
    *,
    context: Dict[str, Any],
    inferred_project_type: str,
    missing: List[str],
) -> str:
    base = _structured_clarification_reply(
        context=context,
        missing=missing,
        inferred_project_type=inferred_project_type,
    )
    return base + " You can also upload a sketch or site image if that helps."


def _design_readiness_check(message: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    reference_text = _recent_user_context_text(context, message)
    analysis_text = f"{reference_text}\n{message}".strip() if reference_text else message
    lowered = _normalized_chat_text(analysis_text)
    inferred_project_type = str(context.get("project_type") or "").strip() or _infer_project_type_from_message(
        analysis_text
    )
    lot_width = _safe_positive_number(context.get("lot_width"))
    lot_height = _safe_positive_number(context.get("lot_height"))
    parking_count = _safe_positive_number(context.get("parking_count"))
    disciplines = context.get("disciplines") or {}
    requires_surface_context = (
        "grading" in lowered
        or "contour" in lowered
        or "storm" in lowered
        or "drainage" in lowered
        or bool(disciplines.get("grading"))
        or bool(disciplines.get("drainage"))
    )
    topology_signal = any(
        phrase in lowered
        for phrase in [
            "sloped",
            "slope",
            "survey",
            "contour",
            "existing grade",
            "topography",
            "terrain",
            "northwest to southeast",
            "nw to se",
        ]
    ) or _message_has_dimension_signal(analysis_text)
    building_program_signal = any(
        phrase in lowered
        for phrase in [
            "building",
            "buildings",
            "parking",
            "pad",
            "roadway",
            "road",
            "mixed-use",
            "mixed use",
        ]
    )
    explicit_site_layout_signal = (
        any(phrase in lowered for phrase in ["site plan", "civil site plan", "lot", "driveway", "setback"])
        and _message_has_dimension_signal(message)
        and building_program_signal
    )
    broad_engineering_scope = sum(
        1
        for phrase in [
            "grading",
            "storm",
            "drainage",
            "sanitary",
            "water",
            "utility",
            "utilities",
            "detention basin",
            "fully coordinated",
            "real-world",
        ]
        if phrase in lowered
    ) >= 4

    missing: List[str] = []
    if not inferred_project_type and not explicit_site_layout_signal:
        missing.append("the site type or land use")
    if not (lot_width and lot_height) and not _message_has_dimension_signal(analysis_text):
        missing.append("approximate lot dimensions or site area")
    if not parking_count and not building_program_signal:
        missing.append("the rough building or parking program")
    if requires_surface_context and not topology_signal:
        missing.append("terrain or slope information")

    if not missing:
        return None

    # Always ask focused follow-up questions when key requirements are missing.
    return {
        "needs_clarification": True,
        "assistant_message": _structured_clarification_reply(
            context=context,
            missing=missing,
            inferred_project_type=inferred_project_type,
        ),
        "missing_requirements": missing,
        "reason": "Missing core design inputs",
    }

    # Unreachable fallback for clarity.
    return None


def assess_design_readiness(message: str, context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    return _design_readiness_check(message, _chat_context_summary(dict(context or {})))


def _is_well_specified_design_request(message: str, context: Dict[str, Any]) -> bool:
    reference_text = _recent_user_context_text(context, message)
    analysis_text = f"{reference_text}\n{message}".strip() if reference_text else message
    lowered = _normalized_chat_text(analysis_text)
    if _looks_like_follow_up_design_edit(message, context):
        return True
    explicit_request = _looks_like_explicit_design_request(message)
    same_context_run_request = _references_prior_design_context(message) and any(
        phrase in _normalized_chat_text(message)
        for phrase in ["run the design", "run this design", "run it", "do the design", "start the design"]
    )
    if not explicit_request and not same_context_run_request:
        return False

    inferred_project_type = str(context.get("project_type") or "").strip() or _infer_project_type_from_message(
        analysis_text
    )
    lot_width = _safe_positive_number(context.get("lot_width"))
    lot_height = _safe_positive_number(context.get("lot_height"))
    has_site_size = bool(lot_width and lot_height) or _message_has_dimension_signal(analysis_text) or any(
        token in lowered for token in ["acre", "acres", "site area", "lot area"]
    )
    has_topography = any(
        phrase in lowered
        for phrase in [
            "sloped",
            "slope",
            "contour",
            "spot elevations",
            "topography",
            "terrain",
            "existing grade",
            "nw→se",
            "nw->se",
            "nw to se",
        ]
    ) or bool(re.search(r"\b\d+(?:\.\d+)?\s*%\s*slope\b", lowered))
    has_program = any(
        phrase in lowered
        for phrase in [
            "building",
            "buildings",
            "units",
            "multifamily",
            "commercial pad",
            "parking",
            "stalls",
            "road",
            "roads",
            "cul-de-sac",
        ]
    )
    if not inferred_project_type and has_site_size and has_program:
        inferred_project_type = "generic_site"
    systems_count = sum(
        1
        for phrase in [
            "grading",
            "storm",
            "drainage",
            "sanitary",
            "water",
            "utility",
            "utilities",
            "detention basin",
        ]
        if phrase in lowered
    )
    return bool(inferred_project_type) and has_site_size and has_topography and has_program and systems_count >= 3


def _base_decision(
    *,
    intent: str,
    assistant_message: str,
    run_mode: str = "none",
    design_prompt: str = "",
    needs_clarification: bool = False,
    reason: str,
    confidence: float,
    control_overrides: Optional[Dict[str, Any]] = None,
    response_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = dict(response_metadata or _metadata_for_decision(command_intent=intent))
    metadata.setdefault("confidence", confidence)
    metadata.setdefault("state_changed", False)
    metadata.setdefault("unsupported_reason", "")
    metadata.setdefault("blocker", metadata.get("action_blocked_reason") or "")
    if not metadata.get("outcome"):
        if metadata.get("unsupported_reason"):
            metadata["outcome"] = "unsupported_or_not_understood"
        elif metadata.get("required_missing_inputs"):
            metadata["outcome"] = "understood_needs_more_info"
        elif metadata.get("action_blocked_reason"):
            metadata["outcome"] = "understood_but_blocked"
        elif metadata.get("state_changed"):
            metadata["outcome"] = "understood_and_executed"
        else:
            metadata["outcome"] = "understood_needs_more_info" if needs_clarification else "understood_and_executed"
    return {
        "success": True,
        "intent": intent,
        "assistant_message": assistant_message,
        "run_mode": run_mode,
        "design_prompt": design_prompt,
        "needs_clarification": needs_clarification,
        "reason": reason,
        "confidence": confidence,
        "control_overrides": dict(control_overrides or {}),
        "response_metadata": metadata,
        "required_missing_inputs": list(metadata.get("required_missing_inputs") or []),
        "action_taken": str(metadata.get("action_taken") or ""),
        "action_blocked_reason": str(metadata.get("action_blocked_reason") or ""),
        "affected_systems": list(metadata.get("affected_systems") or []),
        "assumptions": list(metadata.get("assumptions") or []),
        "next_best_action": str(metadata.get("next_best_action") or ""),
    }


def _local_chat_decision(payload_data: Dict[str, Any]) -> Dict[str, Any]:
    message = str(payload_data.get("message") or "").strip()
    lowered = _normalized_chat_text(message)
    context = _chat_context_summary(dict(payload_data.get("context") or {}))
    strategy_mode = str(context.get("strategy_mode") or "assisted").strip().lower()
    overrides = _extract_control_overrides(message, context)
    action_plan = plan_chat_action(message, context)
    planned_intent = command_intent_from_action_plan(action_plan)
    command_intent = _command_family(message)
    if command_intent == "conversation" and planned_intent in {
        "workspace_state",
        "fix",
        "object_or_layout_command",
        "grading_command",
        "drainage_command",
        "utility_command",
        "generate_command",
        "mode_command",
        "unsupported_or_not_understood",
    }:
        command_intent = planned_intent
    affected_systems = _affected_systems_for_command(command_intent, message)
    if not message:
        return _base_decision(
            intent="conversation",
            assistant_message="Tell me what you want to change, or ask me a question about the current design.",
            needs_clarification=True,
            reason="Empty message",
            confidence=0.2,
            response_metadata=_metadata_for_decision(
                command_intent="conversation",
                missing=["chat message"],
                action_taken="asked_clarifying_question",
                action_blocked_reason="No chat message was provided.",
                next_best_action="Tell Civora what to design, revise, or explain.",
            ),
        )

    if command_intent != "responsibility_guard" and action_plan.get("safety_blockers"):
        blocker = "; ".join(str(item) for item in list(action_plan.get("safety_blockers") or []) if str(item))
        return _base_decision(
            intent="conversation",
            assistant_message=blocker,
            needs_clarification=False,
            reason="Deterministic safety gate blocked unsafe chat action",
            confidence=0.98,
            control_overrides=overrides,
            response_metadata=_metadata_for_decision(
                command_intent=command_intent if command_intent != "conversation" else "safety_gate",
                action_taken="blocked_safety_gate",
                action_blocked_reason=blocker,
                affected_systems=["review"],
                next_best_action="Use Civora to prepare engineer-review-required evidence, blockers, calculations, reports, exports, assumptions, or traceability instead.",
                outcome="understood_but_blocked",
                confidence=0.98,
                state_changed=False,
                blocker=blocker,
            ),
        )

    if command_intent == "responsibility_guard":
        blocker = (
            "Civora cannot approve, stamp, seal, certify, sign off, or issue construction sets. "
            "A responsible external licensed engineer/user must provide any approval record."
        )
        return _base_decision(
            intent="conversation",
            assistant_message=blocker,
            needs_clarification=False,
            reason="Responsibility guard blocked approval/signoff request",
            confidence=0.98,
            control_overrides=overrides,
            response_metadata=_metadata_for_decision(
                command_intent="responsibility_guard",
                action_taken="blocked_responsibility_request",
                action_blocked_reason=blocker,
                affected_systems=["review"],
                next_best_action="Prepare or review an engineer-review-required package, then attach an external licensed engineer approval record outside Civora if one exists.",
                outcome="understood_but_blocked",
                confidence=0.98,
                state_changed=False,
                blocker=blocker,
            ),
        )

    if _is_settings_only_message(message, overrides):
        return _base_decision(
            intent="settings",
            assistant_message=_settings_reply(overrides),
            reason="Settings-only update detected",
            confidence=0.95,
            control_overrides=overrides,
            response_metadata=_metadata_for_decision(
                command_intent=command_intent if command_intent != "conversation" else "settings",
                action_taken="updated_chat_controls",
                affected_systems=affected_systems,
                next_best_action="Give a design command when you want Civora to run the planner.",
                outcome="understood_and_executed",
                confidence=0.95,
                state_changed=True,
            ),
        )

    if command_intent in {
        "site_update",
        "object_or_layout_command",
        "grading_command",
        "drainage_command",
        "utility_command",
        "generate_command",
    }:
        command_payload: Dict[str, Any] = {}
        command_assumptions: List[str] = []
        if command_intent == "site_update" and _extract_site_area_acres(message):
            area = float(_extract_site_area_acres(message) or 0.0)
            side = round((area * 43560.0) ** 0.5, 1) if area > 0 else 0.0
            command_payload = {"site_area_acres": area, "lot_width": side, "lot_height": side}
            if side > 0:
                command_assumptions.append("Site area command uses a square draft boundary until exact boundary dimensions are provided.")
        elif command_intent == "object_or_layout_command":
            command_payload = _extract_object_command_payload(message, context)
            if (
                command_payload.get("assumption_policy") == "assisted"
                and command_payload.get("operation") == "create"
                and command_payload.get("object_type") in {"building", "detention_basin", "parking"}
                and not command_payload.get("location_hint")
            ):
                command_assumptions.append("Object will be added as draft geometry at a planner-selected feasible location.")
        missing_inputs = _missing_inputs_for_command(command_intent, message, context)
        if missing_inputs:
            ask = _specific_missing_question(command_intent, missing_inputs, context)
            return _base_decision(
                intent="conversation",
                assistant_message=ask + _remembered_instruction_fragment(context),
                needs_clarification=True,
                reason="Command is missing required inputs",
                confidence=0.91,
                control_overrides=overrides,
                response_metadata=_metadata_for_decision(
                    command_intent=command_intent,
                    missing=missing_inputs,
                    action_taken="asked_clarifying_question",
                    action_blocked_reason="Required command inputs are missing.",
                    affected_systems=affected_systems,
                    next_best_action=ask,
                    command_payload=command_payload,
                    outcome="understood_needs_more_info",
                    confidence=0.91,
                    state_changed=False,
                    blocker="Required command inputs are missing.",
                ),
            )

        if command_intent == "site_update" and _extract_site_area_acres(message):
            area = _extract_site_area_acres(message)
            prompt = f"Update the current site area to {area} acres and rerun affected layout, grading, drainage, utility, and export readiness checks."
            return _base_decision(
                intent="design",
                assistant_message=f"I’ll update the canonical site area to {area} acres and rerun the affected design systems.",
                run_mode="run",
                design_prompt=prompt,
                reason="Site area update command detected",
                confidence=0.9,
                control_overrides=overrides,
                response_metadata=_metadata_for_decision(
                    command_intent=command_intent,
                    action_taken="prepared_canonical_edit",
                    affected_systems=affected_systems or ["site", "layout", "grading", "drainage", "utilities"],
                    assumptions=command_assumptions,
                    next_best_action="Review the updated site extents and downstream system status.",
                    command_payload=command_payload,
                    outcome="understood_and_executed",
                    confidence=0.9,
                    state_changed=False,
                ),
            )

        if command_intent == "drainage_command":
            overrides["drainage"] = True
        elif command_intent == "grading_command":
            overrides["grading"] = True
        elif command_intent == "utility_command":
            overrides["utilities"] = True
        elif command_intent == "generate_command":
            overrides.update({"roads": True, "grading": True, "drainage": True, "utilities": True})

        return _base_decision(
            intent="design",
            assistant_message=_revision_acknowledgement(message, context),
            run_mode="run",
            design_prompt=message,
            reason=f"{command_intent.replace('_', ' ').title()} detected",
            confidence=0.9,
            control_overrides=overrides,
            response_metadata=_metadata_for_decision(
                command_intent=command_intent,
                action_taken="prepared_canonical_edit" if command_intent == "object_or_layout_command" else "prepared_engineering_run",
                affected_systems=affected_systems,
                assumptions=command_assumptions,
                next_best_action="Review the generated systems and any blockers returned by the planner.",
                command_payload=command_payload,
                outcome="understood_and_executed",
                confidence=0.9,
                state_changed=False,
            ),
        )

    contextual_reply = _contextual_question_reply(message, context)
    if contextual_reply:
        intent = "conversation"
        metadata_intent = "workspace_state"
        if ("why" in lowered or "explain" in lowered) and not any(
            phrase in lowered
            for phrase in [
                "what did you fix",
                "what did you change",
                "what got fixed",
                "what needs review",
                "what should i review",
                "what is blocked",
                "what's blocked",
                "whats blocked",
                "why is it blocked",
                "why did it block",
                "why is export blocked",
                "why did export fail",
                "why is storm blocked",
                "why is drainage blocked",
                "why is utility blocked",
                "why are utilities blocked",
                "why is grading blocked",
                "why is that better",
                "why is it better",
                "why do you think that is better",
            ]
        ):
            intent = "explain"
            metadata_intent = "workspace_state"
        if command_intent != "conversation":
            metadata_intent = command_intent
        context_blockers = _context_blockers(context)
        context_missing = _context_missing_inputs(context)
        next_best_action = _context_next_best_action(
            context,
            "Use a targeted command if you want Civora to change the design.",
        )
        return _base_decision(
            intent=intent,
            assistant_message=contextual_reply,
            reason="Answered from current workspace context",
            confidence=0.9,
            control_overrides=overrides,
            response_metadata=_metadata_for_decision(
                command_intent=metadata_intent,
                action_taken="answered_from_project_context",
                action_blocked_reason="; ".join(context_blockers[:3]),
                missing=context_missing,
                affected_systems=affected_systems,
                next_best_action=next_best_action,
                outcome="understood_and_executed",
                confidence=0.9,
                state_changed=False,
                blocker="; ".join(context_blockers[:3]),
            ),
        )

    if strategy_mode == "assisted" and _looks_like_assisted_scope_confirmation(message):
        prior_design = _last_design_request_from_history(context)
        if prior_design:
            return _base_decision(
                intent="design",
                assistant_message=(
                    "I’ll keep the scope anchored to what you asked for and use AI assistance only for the missing engineering details you approved."
                    + _remembered_instruction_fragment(context)
                ),
                run_mode="run",
                design_prompt=prior_design,
                reason="Assisted scope confirmation detected",
                confidence=0.92,
                control_overrides=overrides,
            )

    if _looks_like_run_confirmation(message, context):
        previous_user = _last_user_message(context)
        return _base_decision(
            intent="design",
            assistant_message="I’m using the design request you just gave me and moving forward with it."
            + _remembered_instruction_fragment(context),
            run_mode="run",
            design_prompt=previous_user,
            reason="Follow-up run confirmation detected",
            confidence=0.9,
            control_overrides=overrides,
        )

    if command_intent == "fix":
        return _base_decision(
            intent="fix",
            assistant_message=_revision_mode_acknowledgement(
                message,
                context,
                "I’ll run a focused fix pass on the current design" if bool(context.get("has_plan")) else "I’ll run a focused fix pass on the design",
            ),
            run_mode="fix",
            reason="Natural language fix request detected",
            confidence=0.86,
            control_overrides=overrides,
            response_metadata=_metadata_for_decision(
                command_intent="fix",
                action_taken="prepared_engineering_run",
                affected_systems=affected_systems or ["layout", "grading", "drainage", "utilities"],
                next_best_action="Review the fix pass result and any returned blockers.",
                outcome="understood_and_executed",
                confidence=0.86,
                state_changed=False,
            ),
        )

    if _is_ambiguous_request(message, context):
        ask = _clarifying_ambiguous_reply(context)
        return _base_decision(
            intent="conversation",
            assistant_message=ask,
            needs_clarification=True,
            reason="Ambiguous request needs clarification",
            confidence=0.9,
            control_overrides=overrides,
            response_metadata=_metadata_for_decision(
                command_intent="conversation",
                missing=["specific command or target"],
                action_taken="asked_clarifying_question",
                action_blocked_reason="The request was ambiguous.",
                next_best_action=ask,
                outcome="understood_needs_more_info",
                confidence=0.9,
                state_changed=False,
                blocker="The request was ambiguous.",
            ),
        )

    if _is_casual_chat_message(message):
        return _base_decision(
            intent="conversation",
            assistant_message=_conversation_reply(message, context),
            reason="Casual conversation detected",
            confidence=0.95,
            control_overrides=overrides,
            response_metadata=_metadata_for_decision(
                command_intent="conversation",
                action_taken="answered",
                next_best_action="Ask about the current project or give a supported design command.",
                outcome="understood_and_executed",
                confidence=0.95,
                state_changed=False,
            ),
        )

    if "explain" in lowered or ("why" in lowered and bool(context.get("has_plan"))):
        return _base_decision(
            intent="explain",
            assistant_message="I’ll explain what the current design is doing and what still needs attention.",
            reason="Explanation request detected",
            confidence=0.82,
            control_overrides=overrides,
        )
    if command_intent == "fix" or _is_explicit_plan_tool_request(message, "fix"):
        return _base_decision(
            intent="fix",
            assistant_message=_revision_mode_acknowledgement(
                message,
                context,
                "I’ll run a focused fix pass on the current design" if bool(context.get("has_plan")) else "I’ll run a focused fix pass on the design",
            ),
            run_mode="fix",
            reason="Fix request detected",
            confidence=0.88,
            control_overrides=overrides,
        )
    if _is_explicit_plan_tool_request(message, "improve"):
        return _base_decision(
            intent="improve",
            assistant_message=_revision_mode_acknowledgement(
                message,
                context,
                "I’ll improve the current design" if bool(context.get("has_plan")) else "I’ll improve the design",
            ),
            run_mode="improve",
            reason="Improve request detected",
            confidence=0.88,
            control_overrides=overrides,
        )

    follow_up_edit = _looks_like_follow_up_design_edit(message, context) or _looks_like_continuation_edit(
        message,
        context,
    )
    design_like = (
        _is_well_specified_design_request(message, context)
        or _looks_like_explicit_design_request(message)
        or follow_up_edit
        or _has_edit_intent(message)
    )

    readiness_issue = _design_readiness_check(message, context)
    if design_like and readiness_issue and not follow_up_edit:
        return _base_decision(
            intent="conversation",
            assistant_message=readiness_issue["assistant_message"],
            needs_clarification=True,
            reason=readiness_issue["reason"],
            confidence=0.93,
            control_overrides=overrides,
        )

    if design_like:
        reply = _revision_acknowledgement(message, context)
        return _base_decision(
            intent="design",
            assistant_message=reply,
            run_mode="run",
            design_prompt=message,
            reason="Explicit or follow-up design request detected",
            confidence=0.9,
            control_overrides=overrides,
        )

    if strategy_mode in {"manual", "user"}:
        reference_text = _recent_user_context_text(context, message)
        analysis_text = f"{reference_text}\n{message}".strip() if reference_text else message
        lowered_manual = _normalized_chat_text(analysis_text)
        if _references_prior_design_context(message) and _design_readiness_check(message, context) is None and any(
            phrase in lowered_manual for phrase in ["run the design", "strict mode", "no assumptions"]
        ):
            return _base_decision(
                intent="design",
                assistant_message=_revision_acknowledgement(message, context),
                run_mode="run",
                design_prompt=message,
                reason="Assisted off reused prior design context",
                confidence=0.84,
                control_overrides=overrides,
            )
        inferred_project_type = str(context.get("project_type") or "").strip() or _infer_project_type_from_message(
            analysis_text
        )
        manual_missing: List[str] = []
        if not inferred_project_type:
            manual_missing.append("the site type or land use")
        if not (context.get("lot_width") and context.get("lot_height")) and not _message_has_dimension_signal(analysis_text):
            manual_missing.append("rough lot size")
        systems_present = any(
            phrase in lowered_manual
            for phrase in ["grading", "drainage", "storm", "sanitary", "water", "utility", "utilities", "road", "roads"]
        )
        if not systems_present:
            manual_missing.append("which systems to include")
        return _base_decision(
            intent="conversation",
            assistant_message=(ask := _structured_clarification_reply(
                context=context,
                missing=manual_missing,
                inferred_project_type=inferred_project_type,
            )),
            needs_clarification=True,
            reason="Assisted off conservative fallback",
            confidence=0.72,
            control_overrides=overrides,
            response_metadata=_metadata_for_decision(
                command_intent="conversation",
                missing=manual_missing or ["explicit command details"],
                action_taken="asked_clarifying_question",
                action_blocked_reason="No-assumption mode requires explicit inputs before Civora fills gaps.",
                next_best_action=ask,
                outcome="understood_needs_more_info",
                confidence=0.72,
                state_changed=False,
                blocker="No-assumption mode requires explicit inputs before Civora fills gaps.",
            ),
        )

    if _is_question(message):
        fallback_reply = _conversation_reply(message, context)
        return _base_decision(
            intent="conversation",
            assistant_message=fallback_reply,
            needs_clarification=True,
            reason="General question without enough specific context",
            confidence=0.68,
            control_overrides=overrides,
            response_metadata=_metadata_for_decision(
                command_intent="conversation",
                missing=["more specific project context or command"],
                action_taken="asked_clarifying_question",
                action_blocked_reason="General question did not include enough project-specific context.",
                next_best_action=fallback_reply,
                outcome="understood_needs_more_info",
                confidence=0.68,
                state_changed=False,
                blocker="General question did not include enough project-specific context.",
            ),
        )

    unsupported_reason = "The message does not match a supported Civora chat command or project question."
    return _base_decision(
        intent="conversation",
        assistant_message="I do not recognize that as a supported Civora command. Ask a specific project question or give a supported site, object, grading, drainage, utility, or review command.",
        needs_clarification=False,
        reason="Unsupported fallback",
        confidence=0.62,
        control_overrides=overrides,
        response_metadata=_metadata_for_decision(
            command_intent="unsupported_or_not_understood",
            action_taken="unsupported_or_not_understood",
            action_blocked_reason=unsupported_reason,
            next_best_action="Ask a specific project question or give a supported design command.",
            outcome="unsupported_or_not_understood",
            confidence=0.62,
            state_changed=False,
            unsupported_reason=unsupported_reason,
        ),
    )


def decide_chat_message(payload_data: Dict[str, Any]) -> Dict[str, Any]:
    message = str(payload_data.get("message") or "").strip()
    if not message:
        raise ValueError("Chat message is required.")
    context = _chat_context_summary(dict(payload_data.get("context") or {}))
    local = _local_chat_decision(payload_data)
    action_plan = plan_chat_action(message, context)
    local = _attach_action_planning_metadata(local, action_plan)
    local_metadata = dict(local.get("response_metadata") or {})
    if str(local_metadata.get("intent") or "") in {
        "site_update",
        "object_or_layout_command",
        "grading_command",
        "drainage_command",
        "utility_command",
        "generate_command",
        "blocker_explanation",
        "export_readiness",
        "mode_command",
        "responsibility_guard",
        "unsupported_or_not_understood",
        "workspace_state",
    }:
        return local

    system_prompt = (
        "You are Civora AI, an AI-powered civil engineering design assistant. "
        "You are deciding how to handle the user's latest chat message inside a live design workspace. "
        "You must choose one intent: conversation, settings, design, explain, fix, or improve. "
        "Only choose design when the user is clearly asking to create or modify the plan. "
        "Choose settings when the user is changing workflow controls like the Assisted toggle, disciplines, names, dimensions, or counts without asking for a run. "
        "Choose conversation for greetings, casual chat, or general questions that should not trigger a plan run. "
        "Choose explain when the user wants an explanation of the current plan. "
        "Choose fix or improve only when the user is explicitly asking for that action. "
        "When Assisted is off, be conservative and ask for clarification unless the design request is explicit. "
        "If the user is asking for a design but the request is underspecified, do not bluff or invent a full plan. "
        "Set needs_clarification=true and write a short, natural assistant message that asks for the next most important missing details. "
        "Ask at most two questions and avoid long lists. "
        "In assisted mode, when key details are missing, you may ask whether the user wants Civora to help fill in those blanks instead of guessing outright. "
        "The context may include a memory_summary of the user's stated preferences and constraints from earlier in the chat. Respect those remembered instructions and do not forget them when deciding how to respond. "
        "If context includes current_phase, reference it briefly so the user knows where the workflow is. "
        "Ask only the smallest useful set of follow-up questions needed to move the design forward. "
        "For casual conversation, answer naturally and briefly like a helpful AI teammate. "
        "Return concise, helpful assistant wording with a calm professional personality. "
        "If the user message includes settings changes plus a design request, keep intent as design and include the setting overrides too. "
        "Do not invent unsupported fields. "
        "You may receive a heuristic_suggestion with a draft intent and run_mode; use it when it makes sense, but correct it if the user message clearly indicates otherwise. "
        "Always return valid JSON matching the schema."
    )
    user_payload = {
        "message": message,
        "context": context,
        "heuristic_suggestion": {
            "intent": local.get("intent"),
            "run_mode": local.get("run_mode"),
            "needs_clarification": local.get("needs_clarification"),
            "reason": local.get("reason"),
        },
    }

    try:
        client = _load_chat_client()
        response = client.responses.create(
            model="gpt-5",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload)},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "civora_chat_decision",
                    "schema": CHAT_DECISION_SCHEMA,
                    "strict": True,
                }
            },
        )
        data = json.loads(response.output_text)
        if not isinstance(data, dict):
            raise ValueError("Chat decision response was not an object.")
        if overrides := local.get("control_overrides"):
            merged = dict(data.get("control_overrides") or {})
            merged.update(overrides)
            data["control_overrides"] = merged
        local_metadata = dict(local.get("response_metadata") or {})
        data_metadata = dict(data.get("response_metadata") or {})
        merged_metadata = {**local_metadata, **{key: value for key, value in data_metadata.items() if value not in (None, "", [])}}
        if not merged_metadata:
            merged_metadata = _metadata_for_decision(command_intent=str(data.get("intent") or "conversation"))
        data["response_metadata"] = merged_metadata
        for key in [
            "required_missing_inputs",
            "action_taken",
            "action_blocked_reason",
            "affected_systems",
            "assumptions",
            "next_best_action",
        ]:
            if not data.get(key):
                data[key] = merged_metadata.get(key, [] if key in {"required_missing_inputs", "affected_systems", "assumptions"} else "")
        if str(data.get("intent") or "") == "design":
            readiness_issue = _design_readiness_check(message, context)
            if readiness_issue:
                clarification_message = _structured_clarification_reply(
                    context=context,
                    missing=readiness_issue.get("missing_requirements") or [],
                    inferred_project_type=context.get("project_type"),
                )
                try:
                    clarification_message = _openai_chat_clarification(
                        context=context,
                        missing=readiness_issue.get("missing_requirements") or [],
                        inferred_project_type=context.get("project_type"),
                    )
                except Exception:
                    pass
                data.update(
                    {
                        "intent": "conversation",
                        "assistant_message": clarification_message,
                        "run_mode": "none",
                        "design_prompt": "",
                        "needs_clarification": True,
                        "reason": readiness_issue["reason"],
                        "confidence": min(float(data.get("confidence") or 0.0), 0.92),
                    }
                )
                metadata = _metadata_for_decision(
                    command_intent=str(merged_metadata.get("intent") or "design"),
                    missing=list(readiness_issue.get("missing_requirements") or []),
                    action_taken="asked_clarifying_question",
                    action_blocked_reason=str(readiness_issue.get("reason") or "Missing required inputs."),
                    affected_systems=list(merged_metadata.get("affected_systems") or []),
                    next_best_action=str(data.get("assistant_message") or ""),
                )
                data["response_metadata"] = metadata
                data["required_missing_inputs"] = metadata["required_missing_inputs"]
                data["action_taken"] = metadata["action_taken"]
                data["action_blocked_reason"] = metadata["action_blocked_reason"]
                data["affected_systems"] = metadata["affected_systems"]
                data["assumptions"] = metadata["assumptions"]
                data["next_best_action"] = metadata["next_best_action"]
        elif _is_well_specified_design_request(message, context) or _looks_like_follow_up_design_edit(message, context):
            data.update(
                {
                    "intent": "design",
                    "assistant_message": (
                        "I’m updating the current design with that change."
                        if bool(context.get("has_plan"))
                        else "I have enough context to start the design."
                    ),
                    "run_mode": "run",
                    "design_prompt": message,
                    "needs_clarification": False,
                    "reason": "Well-specified or follow-up engineering design request detected",
                    "confidence": max(float(data.get("confidence") or 0.0), 0.88),
                }
            )
            metadata = _metadata_for_decision(
                command_intent=str(merged_metadata.get("intent") or "design"),
                action_taken="queued_design_run",
                affected_systems=list(merged_metadata.get("affected_systems") or []),
                next_best_action="Review the planner result and any returned blockers.",
            )
            data["response_metadata"] = metadata
            data["required_missing_inputs"] = metadata["required_missing_inputs"]
            data["action_taken"] = metadata["action_taken"]
            data["action_blocked_reason"] = metadata["action_blocked_reason"]
            data["affected_systems"] = metadata["affected_systems"]
            data["assumptions"] = metadata["assumptions"]
            data["next_best_action"] = metadata["next_best_action"]
        data["success"] = True
        return _attach_action_planning_metadata(data, action_plan)
    except Exception:
        return local


def _openai_chat_clarification(
    *,
    context: Dict[str, Any],
    missing: List[str],
    inferred_project_type: Optional[str],
) -> str:
    client = _load_chat_client()
    system_prompt = (
        "You are Civora AI. The user asked for a design, but required inputs are missing. "
        "Write a short, friendly clarification question that asks only for the missing details. "
        "Ask at most two questions, keep it to 1-3 sentences, and do not invent site details. "
        "Return plain text only."
    )
    payload = {
        "missing_requirements": missing,
        "inferred_project_type": inferred_project_type,
        "memory_summary": context.get("memory_summary"),
    }
    response = client.responses.create(
        model="gpt-5",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )
    message = str(response.output_text or "").strip()
    if not message:
        raise ValueError("Empty clarification response.")
    return message
