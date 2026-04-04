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
    engineering_status = context.get("engineering_status") or {}
    convergence_summary = context.get("convergence_summary") or {}
    issues = context.get("issues") or []
    manual_failures = context.get("manual_failures") or []
    assumptions = context.get("assumptions") or []
    produced_deliverables = context.get("produced_deliverables") or []
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
        "engineering_status": engineering_status.get("status"),
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


def _extract_control_overrides(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    lowered = message.lower()
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
    lowered = message.lower()
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
    lowered = message.lower()
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
    lowered = message.lower()
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
        ]
    ):
        return True
    return False


def _is_question(message: str) -> bool:
    lowered = message.strip().lower()
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
        ]
    )


def _is_ambiguous_request(message: str, context: Dict[str, Any]) -> bool:
    lowered = message.strip().lower()
    if not lowered:
        return True

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
    lowered = message.strip().lower()
    if any(phrase in lowered for phrase in ["how are you", "how r u", "how are u"]):
        return "I’m doing well and I’m ready to help with the design. You can ask me about the current plan or tell me what you want to change."
    if lowered in {"hello", "hi", "hey", "yo"}:
        return "Hi, I’m Civora. Tell me what you want to design, or ask me about the current plan."
    if "thank" in lowered:
        return "You’re welcome. Tell me what you want to adjust next, or ask me about the current design."
    if "help" in lowered and not bool(context.get("has_plan")):
        return "I can help design a civil site plan, explain tradeoffs, or guide you through the inputs I need. Start by telling me the site type and what you want to build."
    return "I’m here with you. Ask me about the current design, change a setting, or tell me what you want me to create or modify."


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
    lowered = message.lower()
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

    if "what mode" in lowered or "which mode" in lowered:
        return f"You’re currently in {str(context.get('strategy_mode') or 'assisted').strip().lower()} mode."
    if "project name" in lowered or "what is this project called" in lowered:
        name = str(context.get("site_name") or context.get("current_project_name") or "").strip()
        return f"The current project is named {name}." if name else "The current project does not have a name yet."
    if "file name" in lowered:
        file_name = str(context.get("file_name") or "").strip()
        return f"The current file name is {file_name}." if file_name else "The current file name is still blank."
    if "what assumptions" in lowered or "where did ai help" in lowered or "what did ai use" in lowered:
        if assumptions:
            formatted = []
            for item in assumptions[:3]:
                field = str(item.get("field_name") or "an input").replace("_", " ")
                reason = str(item.get("reason") or "").strip()
                formatted.append(f"{field} ({reason})" if reason else field)
            return "AI helped fill in: " + "; ".join(formatted) + "."
        return "There are no explicit AI-filled assumptions recorded on the current design."
    if "what did you fix" in lowered or "what did you change" in lowered or "what got fixed" in lowered:
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
    if "what is blocked" in lowered or "what's blocked" in lowered or "whats blocked" in lowered:
        if blocked_exports or blocked_reasons:
            parts: List[str] = []
            if blocked_exports:
                parts.append("blocked outputs: " + ", ".join(str(item) for item in blocked_exports[:3]))
            if blocked_reasons:
                parts.append("reasons: " + "; ".join(str(item) for item in blocked_reasons[:3]))
            return "Right now, " + ". ".join(parts) + "."
        return "Nothing is explicitly blocked right now."
    if "how many passes" in lowered or "how many reruns" in lowered or "did it converge" in lowered:
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


def _clarifying_ambiguous_reply(context: Dict[str, Any]) -> str:
    if bool(context.get("has_plan")):
        return (
            "I’m not fully sure what you want me to change yet. Tell me what part of the current design you want to update, "
            "what outcome you want, or ask me a specific question about assumptions, fixes, review items, or blockers."
        )
    return (
        "I’m not fully sure what you want me to do yet. Tell me whether you want a new design, a settings change, or an explanation. "
        "If you want a design, give me the site type, rough size, and the main systems you want included."
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
    lowered = message.lower()
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
        intent = "explain" if ("why" in lowered or "explain" in lowered) else "conversation"
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
            assistant_message="I’ll run a focused fix pass on the current design.",
            run_mode="fix",
            reason="Fix request detected",
            confidence=0.88,
            control_overrides=overrides,
        )
    if _is_explicit_plan_tool_request(message, "improve"):
        return _base_decision(
            intent="improve",
            assistant_message="I’ll improve the current design while keeping your project intent intact.",
            run_mode="improve",
            reason="Improve request detected",
            confidence=0.88,
            control_overrides=overrides,
        )

    follow_up_edit = _looks_like_follow_up_design_edit(message, context)
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
        reply = (
            "I’m updating the current design with that change."
            if bool(context.get("has_plan"))
            else "I have enough context to start the design."
        )
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
        return _base_decision(
            intent="conversation",
            assistant_message="I’m treating that as conversation for now. In Manual mode, tell me exactly what you want me to design or change, and include the key parameters you already know.",
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
