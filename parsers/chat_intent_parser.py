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


def _normalized_chat_text(text: str) -> str:
    normalized = text.strip().lower()
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
    engineering_status = context.get("engineering_status") or {}
    convergence_summary = context.get("convergence_summary") or {}
    issues = context.get("issues") or []
    manual_failures = context.get("manual_failures") or []
    assumptions = context.get("assumptions") or []
    produced_deliverables = context.get("produced_deliverables") or []
    memory_summary = _extract_chat_memory(context.get("chat_thread"))
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
        "truth_success": current_truth.get("success", context.get("truth_success")),
        "engineering_trust_score": current_truth.get(
            "engineering_trust_score", context.get("engineering_trust_score")
        ),
        "engineering_status": engineering_status.get("status", context.get("engineering_status")),
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

    if re.search(r"\bmanual mode\b|\buse manual\b|\bswitch to manual\b", lowered):
        overrides["strategyMode"] = "manual"
    elif re.search(r"\bassisted mode\b|\buse assisted\b|\bswitch to assisted\b", lowered):
        overrides["strategyMode"] = "assisted"

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
        parts.append(f"switched to {overrides['strategyMode']} mode")
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
    issues = context.get("issues") or []
    manual_failures = context.get("manual_failures") or []
    assumptions = context.get("assumptions") or []
    deliverables = context.get("produced_deliverables") or []
    convergence = context.get("convergence_summary") or {}
    fix_summary = convergence.get("fix_summary") or {}
    blocked_exports = convergence.get("blocked_exports") or []
    blocked_reasons = convergence.get("blocked_reasons") or []
    unresolved_categories = convergence.get("unresolved_issue_categories") or []
    rerun_summary = convergence.get("rerun_summary") or {}
    memory_summary = context.get("memory_summary") or {}
    remembered_examples = list(memory_summary.get("examples") or [])
    remembered_preferences = list(memory_summary.get("preferences") or [])
    remembered_constraints = list(memory_summary.get("constraints") or [])
    trust_score = context.get("engineering_trust_score")

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
        project_type = str(context.get("project_type") or "").strip()
        lot_width = context.get("lot_width")
        lot_height = context.get("lot_height")
        parking_count = context.get("parking_count")
        asks: List[str] = []
        if not project_type:
            asks.append("site type")
        if not (lot_width and lot_height):
            asks.append("rough lot size")
        if not parking_count:
            asks.append("building or parking program")
        asks.append("terrain or slope information")
        asks.append("which systems to include")
        return "The most useful inputs right now are " + _format_missing_requirements(asks[:4]) + "."
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
        return "I don’t see a strong uncertainty signal in the current run state, but I’d still review the assumptions and final deliverables before treating it as final."
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
        return "Short version: I don’t see any major blockers recorded right now, but I’d still review the current design before treating it as final."
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
                return f"It’s moving in the right direction, but I’d still review {review_text} before treating it as final."
        return "Yes, it looks reasonably strong from the current run state. I don’t see any explicit blockers recorded right now."
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
        if blocked_exports or blocked_reasons:
            return "I’d address the blockers first: " + "; ".join(
                str(item) for item in (blocked_reasons[:3] or blocked_exports[:3])
            ) + "."
        if manual_failures:
            messages = [str(item.get("message") or "").strip() for item in manual_failures[:2] if isinstance(item, dict)]
            messages = [item for item in messages if item]
            if messages:
                return "I’d review these items next: " + "; ".join(messages) + "."
        if issues:
            messages = [str(item.get("message") or "").strip() for item in issues[:2] if isinstance(item, dict)]
            messages = [item for item in messages if item]
            if messages:
                return "I’d review these warnings next: " + "; ".join(messages) + "."
        if deliverables:
            return "The current design looks stable enough to review the deliverables and decide whether you want another revision."
        return "I’d give me the next design change you want, or ask me to explain the current assumptions and fixes."
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
            ) + " because that is what still blocks the strongest release-ready result."
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
        return "I don’t see any major recorded risks beyond the normal need to review the current design before treating it as final."
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
            return f"The current engineering trust score is {float(trust_score):.1f}. I’d still review the assumptions and any recorded warnings before treating it as final."
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
        " If you want, I can help fill in the blanks once you confirm that you want AI assistance."
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
    primary_missing = missing[:3]
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
        prompt_parts.append("Tell me " + _format_missing_requirements(examples[:3]) + ".")

    if strategy_mode == "assisted":
        prompt_parts.append(
            "If you want, I can help fill in the missing details once you tell me which assumptions you want Civora to make."
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
    return ""


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
    lowered = _normalized_chat_text(message)
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
    lowered = _normalized_chat_text(message)
    if _looks_like_follow_up_design_edit(message, context):
        return True
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
) -> Dict[str, Any]:
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
    }


def _local_chat_decision(payload_data: Dict[str, Any]) -> Dict[str, Any]:
    message = str(payload_data.get("message") or "").strip()
    lowered = _normalized_chat_text(message)
    context = _chat_context_summary(dict(payload_data.get("context") or {}))
    strategy_mode = str(context.get("strategy_mode") or "assisted").strip().lower()
    overrides = _extract_control_overrides(message, context)
    if not message:
        return _base_decision(
            intent="conversation",
            assistant_message="Tell me what you want to change, or ask me a question about the current design.",
            needs_clarification=True,
            reason="Empty message",
            confidence=0.2,
        )

    if _is_settings_only_message(message, overrides):
        return _base_decision(
            intent="settings",
            assistant_message=_settings_reply(overrides),
            reason="Settings-only update detected",
            confidence=0.95,
            control_overrides=overrides,
        )

    contextual_reply = _contextual_question_reply(message, context)
    if contextual_reply:
        intent = "conversation"
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
                "why is that better",
                "why is it better",
                "why do you think that is better",
            ]
        ):
            intent = "explain"
        return _base_decision(
            intent=intent,
            assistant_message=contextual_reply,
            reason="Answered from current workspace context",
            confidence=0.9,
            control_overrides=overrides,
        )

    if _is_ambiguous_request(message, context):
        return _base_decision(
            intent="conversation",
            assistant_message=_clarifying_ambiguous_reply(context),
            needs_clarification=True,
            reason="Ambiguous request needs clarification",
            confidence=0.9,
            control_overrides=overrides,
        )

    if _is_casual_chat_message(message):
        return _base_decision(
            intent="conversation",
            assistant_message=_conversation_reply(message, context),
            reason="Casual conversation detected",
            confidence=0.95,
            control_overrides=overrides,
        )

    if "explain" in lowered or ("why" in lowered and bool(context.get("has_plan"))):
        return _base_decision(
            intent="explain",
            assistant_message="I’ll explain what the current design is doing and what still needs attention.",
            reason="Explanation request detected",
            confidence=0.82,
            control_overrides=overrides,
        )
    if _is_explicit_plan_tool_request(message, "fix"):
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

    if strategy_mode == "manual":
        inferred_project_type = str(context.get("project_type") or "").strip() or _infer_project_type_from_message(
            message
        )
        manual_missing: List[str] = []
        if not inferred_project_type:
            manual_missing.append("the site type or land use")
        if not (context.get("lot_width") and context.get("lot_height")) and not _message_has_dimension_signal(message):
            manual_missing.append("rough lot size")
        manual_missing.append("which systems to include")
        return _base_decision(
            intent="conversation",
            assistant_message=_structured_clarification_reply(
                context=context,
                missing=manual_missing,
                inferred_project_type=inferred_project_type,
            ),
            needs_clarification=True,
            reason="Manual mode conservative fallback",
            confidence=0.72,
            control_overrides=overrides,
        )

    if _is_question(message):
        return _base_decision(
            intent="conversation",
            assistant_message="I can help with that. If you want a design change, tell me exactly what to change. If you want me to start a new design, give me the site type, rough size, and the main systems you want included.",
            needs_clarification=True,
            reason="General question without enough specific context",
            confidence=0.68,
            control_overrides=overrides,
        )

    return _base_decision(
        intent="conversation",
        assistant_message=_clarifying_design_reply(context),
        needs_clarification=True,
        reason="Fallback clarification for ambiguous request",
        confidence=0.62,
        control_overrides=overrides,
    )


def decide_chat_message(payload_data: Dict[str, Any]) -> Dict[str, Any]:
    message = str(payload_data.get("message") or "").strip()
    if not message:
        raise ValueError("Chat message is required.")
    context = _chat_context_summary(dict(payload_data.get("context") or {}))

    local = _local_chat_decision(payload_data)
    if local["intent"] != "conversation" or local["needs_clarification"] or local["confidence"] >= 0.9:
        return local

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
        "The context may include a memory_summary of the user's stated preferences and constraints from earlier in the chat. Respect those remembered instructions and do not forget them when deciding how to respond. "
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
        if overrides := local.get("control_overrides"):
            merged = dict(data.get("control_overrides") or {})
            merged.update(overrides)
            data["control_overrides"] = merged
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
        data["success"] = True
        return data
    except Exception:
        return local
