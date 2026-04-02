from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


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
                "strategyMode": {"type": "string", "enum": ["manual", "assisted"]},
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


def _load_chat_client() -> Any:
    from parsers.ai_parser import _get_client  # type: ignore

    return _get_client()


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


def _chat_context_summary(context: Dict[str, Any]) -> Dict[str, Any]:
    current_project = context.get("current_project") or {}
    current_truth = context.get("current_truth_audit") or {}
    current_explanation = context.get("current_explanation") or {}
    issues = context.get("issues") or []
    manual_failures = context.get("manual_failures") or []
    return {
        "strategy_mode": context.get("strategy_mode") or "assisted",
        "site_name": context.get("site_name") or "",
        "file_name": context.get("file_name") or "",
        "project_type": context.get("project_type") or "",
        "units": context.get("units") or "ft",
        "lot_width": context.get("lot_width"),
        "lot_height": context.get("lot_height"),
        "parking_count": context.get("parking_count"),
        "disciplines": {
            "roads": bool(context.get("roads", True)),
            "grading": bool(context.get("grading", True)),
            "drainage": bool(context.get("drainage", True)),
            "utilities": bool(context.get("utilities", True)),
        },
        "has_plan": bool(context.get("has_plan")),
        "has_preview": bool(context.get("has_preview")),
        "current_project_name": current_project.get("name"),
        "truth_success": current_truth.get("success"),
        "engineering_trust_score": current_truth.get("engineering_trust_score"),
        "explanation_summary": current_explanation.get("summary")
        or current_explanation.get("overview"),
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
        "chat_history": _trim_chat_history(context.get("chat_thread")),
    }


def _is_casual_chat_message(text: str) -> bool:
    normalized = text.strip().lower()
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


def _looks_like_explicit_design_request(text: str) -> bool:
    normalized = text.strip().lower()
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


def _is_explicit_plan_tool_request(text: str, tool: str) -> bool:
    normalized = text.strip().lower()
    explicit_phrases = {
        "fix": [
            "fix this",
            "fix the design",
            "fix issues",
            "fix the issues",
            "resolve the issues",
            "resolve conflicts",
            "run a fix pass",
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
    if strategy_mode == "hybrid":
        strategy_mode = "assisted"
    missing: List[str] = []
    if not project_type:
        missing.append("what kind of site you want")
    lot_known = bool(context.get("lot_width")) and bool(context.get("lot_height"))
    if not lot_known:
        missing.append("rough lot size")
    missing.append("what systems matter most")
    ask = ", ".join(missing[:3])
    assist_line = (
        " If you want, I can help fill in the blanks once you confirm that you want AI assistance."
        if strategy_mode == "assisted"
        else ""
    )
    return (
        "I can help with that. Before I generate a design, tell me "
        f"{ask}. For example: site type, approximate lot dimensions, parking target, and whether roads, grading, drainage, or utilities should be included.{assist_line}"
    )


def _safe_positive_number(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
        return parsed if parsed > 0 else None
    except Exception:
        return None


def _message_has_dimension_signal(message: str) -> bool:
    lowered = message.lower()
    patterns = [
        r"\b\d+(?:\.\d+)?\s*(?:x|by)\s*\d+(?:\.\d+)?\b",
        r"\b\d+(?:\.\d+)?\s*(?:ft|feet|m|meters|ac|acre|acres)\b",
        r"\b\d+(?:\.\d+)?\s*%\s*slope\b",
    ]
    return any(re.search(pattern, lowered) for pattern in patterns)


def _infer_project_type_from_message(message: str) -> str:
    lowered = message.lower()
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
    return ""


def _build_design_readiness_reply(
    *,
    context: Dict[str, Any],
    inferred_project_type: str,
    missing: List[str],
) -> str:
    strategy_mode = str(context.get("strategy_mode") or "assisted").strip().lower()
    if strategy_mode == "hybrid":
        strategy_mode = "assisted"
    starter_parts: List[str] = []
    if inferred_project_type:
        starter_parts.append(
            f"I understand that you want a {inferred_project_type.replace('_', ' ')} design."
        )
    else:
        starter_parts.append("I can help with that design.")
    missing_text = ", ".join(missing[:4])
    assist_line = (
        " If you want, I can help fill in the blanks once you tell me which assumptions you want Civora to make."
        if strategy_mode == "assisted"
        else ""
    )
    return (
        f"{' '.join(starter_parts)} Before I generate a real coordinated plan, I still need {missing_text}. "
        "Give me the missing details, or upload a sketch/site image if you have one."
        f"{assist_line}"
    )


def _design_readiness_check(message: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lowered = message.lower()
    inferred_project_type = str(context.get("project_type") or "").strip() or _infer_project_type_from_message(
        message
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
    ) or _message_has_dimension_signal(message)
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
    if not inferred_project_type:
        missing.append("the site type or land use")
    if not (lot_width and lot_height) and not _message_has_dimension_signal(message):
        missing.append("approximate lot dimensions or site area")
    if not parking_count and not building_program_signal:
        missing.append("the rough building or parking program")
    if requires_surface_context and not topology_signal:
        missing.append("terrain or slope information")

    if not missing:
        return None

    if broad_engineering_scope or len(message.split()) >= 25 or requires_surface_context:
        return {
            "needs_clarification": True,
            "assistant_message": _build_design_readiness_reply(
                context=context,
                inferred_project_type=inferred_project_type,
                missing=missing,
            ),
            "missing_requirements": missing,
            "reason": "Minimum engineering design context is incomplete",
        }

    return None


def assess_design_readiness(message: str, context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    return _design_readiness_check(message, _chat_context_summary(dict(context or {})))


def _is_well_specified_design_request(message: str, context: Dict[str, Any]) -> bool:
    lowered = message.lower()
    if not _looks_like_explicit_design_request(message):
        return False

    inferred_project_type = str(context.get("project_type") or "").strip() or _infer_project_type_from_message(
        message
    )
    lot_width = _safe_positive_number(context.get("lot_width"))
    lot_height = _safe_positive_number(context.get("lot_height"))
    has_site_size = bool(lot_width and lot_height) or _message_has_dimension_signal(message) or any(
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


def _fallback_chat_decision(payload_data: Dict[str, Any]) -> Dict[str, Any]:
    message = str(payload_data.get("message") or "").strip()
    lowered = message.lower()
    context = _chat_context_summary(dict(payload_data.get("context") or {}))
    strategy_mode = str(context.get("strategy_mode") or "assisted")
    if strategy_mode == "hybrid":
        strategy_mode = "assisted"
    if not message:
        return {
            "success": True,
            "intent": "conversation",
            "assistant_message": "Tell me what you want to change, or ask me a question about the current design.",
            "run_mode": "none",
            "design_prompt": "",
            "needs_clarification": True,
            "reason": "Empty message",
            "confidence": 0.2,
            "control_overrides": {},
        }
    if _is_casual_chat_message(message):
        return {
            "success": True,
            "intent": "conversation",
            "assistant_message": (
                "I’m doing well and I’m ready to help. You can ask me about the current plan, change settings, or tell me what you want to design."
                if "how" in lowered
                else "Hi, I’m Civora. Tell me what you want to design, or ask me about the current plan."
            ),
            "run_mode": "none",
            "design_prompt": "",
            "needs_clarification": False,
            "reason": "Casual conversation detected",
            "confidence": 0.82,
            "control_overrides": {},
        }
    if "explain" in lowered or "why" in lowered:
        return {
            "success": True,
            "intent": "explain",
            "assistant_message": "I’ll explain what the current design is doing and what needs attention.",
            "run_mode": "none",
            "design_prompt": "",
            "needs_clarification": False,
            "reason": "Explanation request detected",
            "confidence": 0.6,
            "control_overrides": {},
        }
    if _is_explicit_plan_tool_request(message, "fix"):
        return {
            "success": True,
            "intent": "fix",
            "assistant_message": "I’ll run a focused fix pass on the current design.",
            "run_mode": "fix",
            "design_prompt": "",
            "needs_clarification": False,
            "reason": "Fix request detected",
            "confidence": 0.6,
            "control_overrides": {},
        }
    if _is_explicit_plan_tool_request(message, "improve"):
        return {
            "success": True,
            "intent": "improve",
            "assistant_message": "I’ll improve the current design while keeping your project intent intact.",
            "run_mode": "improve",
            "design_prompt": "",
            "needs_clarification": False,
            "reason": "Improve request detected",
            "confidence": 0.6,
            "control_overrides": {},
        }
    readiness_issue = _design_readiness_check(message, context)
    if readiness_issue:
        return {
            "success": True,
            "intent": "conversation",
            "assistant_message": readiness_issue["assistant_message"],
            "run_mode": "none",
            "design_prompt": "",
            "needs_clarification": True,
            "reason": readiness_issue["reason"],
            "confidence": 0.9,
            "control_overrides": {},
        }
    if _is_well_specified_design_request(message, context):
        return {
            "success": True,
            "intent": "design",
            "assistant_message": "I have enough engineering context to generate a coordinated design from that brief.",
            "run_mode": "run",
            "design_prompt": message,
            "needs_clarification": False,
            "reason": "Well-specified engineering design brief detected",
            "confidence": 0.88,
            "control_overrides": {},
        }
    if strategy_mode == "manual":
        return {
            "success": True,
            "intent": "conversation",
            "assistant_message": "I’m treating that as conversation for now. In Manual mode, tell me exactly what you want me to design or change, and include the key parameters you already know.",
            "run_mode": "none",
            "design_prompt": "",
            "needs_clarification": True,
            "reason": "Manual mode fallback",
            "confidence": 0.45,
            "control_overrides": {},
        }
    if not _looks_like_explicit_design_request(message):
        return {
            "success": True,
            "intent": "conversation",
            "assistant_message": _clarifying_design_reply(context),
            "run_mode": "none",
            "design_prompt": "",
            "needs_clarification": True,
            "reason": "Fallback clarification for underspecified request",
            "confidence": 0.62,
            "control_overrides": {},
        }
    return {
        "success": True,
        "intent": "design",
        "assistant_message": "I’m treating that as a design request and updating the active plan.",
        "run_mode": "run",
        "design_prompt": message,
        "needs_clarification": False,
        "reason": "Fallback design classification",
        "confidence": 0.45,
        "control_overrides": {},
    }


def decide_chat_message(payload_data: Dict[str, Any]) -> Dict[str, Any]:
    context = _chat_context_summary(dict(payload_data.get("context") or {}))
    message = str(payload_data.get("message") or "").strip()
    if not message:
        raise ValueError("Chat message is required.")

    system_prompt = (
        "You are Civora AI, an AI-powered civil engineering design assistant. "
        "You are deciding how to handle the user's latest chat message inside a live design workspace. "
        "You must choose one intent: conversation, settings, design, explain, fix, or improve. "
        "Only choose design when the user is clearly asking to create or modify the plan. "
        "Choose settings when the user is changing workflow controls like manual/assisted mode, disciplines, names, dimensions, or counts without asking for a run. "
        "Choose conversation for greetings, casual chat, or general questions that should not trigger a plan run. "
        "Choose explain when the user wants an explanation of the current plan. "
        "Choose fix or improve only when the user is explicitly asking for that action. "
        "In manual mode, be conservative and ask for clarification unless the design request is explicit. "
        "If the user is asking for a design but the request is underspecified, do not bluff or invent a full plan. "
        "Set needs_clarification=true and write a short, natural assistant message that asks for the next most important missing details, such as site type, lot size, parking target, building size, road needs, grading needs, drainage needs, utility scope, or image/sketch availability. "
        "In assisted mode, when key details are missing, you may ask whether the user wants Civora to help fill in those blanks instead of guessing outright. "
        "Ask only the smallest useful set of follow-up questions needed to move the design forward. "
        "For casual conversation, answer naturally and briefly like a helpful AI teammate. "
        "Return concise, helpful assistant wording with a calm professional personality. "
        "If the user message includes settings changes plus a design request, keep intent as design and include the setting overrides too. "
        "Do not invent unsupported fields. "
        "Always return valid JSON matching the schema."
    )
    user_payload = {
        "message": message,
        "context": context,
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
        if str(data.get("intent") or "") == "design":
            readiness_issue = _design_readiness_check(message, context)
            if readiness_issue:
                data.update(
                    {
                        "intent": "conversation",
                        "assistant_message": readiness_issue["assistant_message"],
                        "run_mode": "none",
                        "design_prompt": "",
                        "needs_clarification": True,
                        "reason": readiness_issue["reason"],
                        "confidence": min(float(data.get("confidence") or 0.0), 0.92),
                    }
                )
        elif _is_well_specified_design_request(message, context):
            data.update(
                {
                    "intent": "design",
                    "assistant_message": "I have enough engineering context to generate a coordinated design from that brief.",
                    "run_mode": "run",
                    "design_prompt": message,
                    "needs_clarification": False,
                    "reason": "Well-specified engineering design brief detected",
                    "confidence": max(float(data.get("confidence") or 0.0), 0.88),
                }
            )
        data["success"] = True
        return data
    except Exception:
        return _fallback_chat_decision(payload_data)
