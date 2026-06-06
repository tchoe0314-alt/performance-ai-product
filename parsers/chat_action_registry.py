from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List, Optional


CONFIDENCE_EXECUTION_THRESHOLD = 0.76


ACTION_REGISTRY: List[Dict[str, Any]] = [
    {
        "action_id": "open_ui_panel",
        "description": "Open a Civora workspace panel such as Setup, Canvas, Review, Deliver, Data, Layers, or Settings.",
        "required_inputs": ["target panel or workspace"],
        "supported_object_types": ["ui_panel", "workspace_mode"],
        "side_effects": ["opens UI panel when frontend applies metadata"],
        "blocked_if": ["target panel is not recognized"],
        "engineer_review_required": False,
        "intent": "ui_navigation",
        "patterns": ["open setup", "open canvas", "open review", "open deliver", "open data"],
        "confidence": 0.93,
    },
    {
        "action_id": "set_preview_mode",
        "description": "Switch the canvas preview between 2D/3D and Standard/High quality when the UI supports it.",
        "required_inputs": ["preview mode or quality"],
        "supported_object_types": ["canvas", "preview"],
        "side_effects": ["updates frontend preview mode/quality when applied by UI"],
        "blocked_if": ["3D requested before a preview/model exists"],
        "engineer_review_required": False,
        "intent": "ui_navigation",
        "patterns": ["2d", "3d", "standard", "high quality"],
        "confidence": 0.9,
    },
    {
        "action_id": "request_site_lock_state",
        "description": "Guide the user to lock, unlock, draw, or change the site boundary from the Setup/Canvas UI.",
        "required_inputs": ["site boundary/dimensions for locking", "user confirmation"],
        "supported_object_types": ["site", "boundary"],
        "side_effects": [],
        "blocked_if": ["site boundary is missing", "visual confirmation is required"],
        "engineer_review_required": True,
        "intent": "ui_navigation",
        "patterns": ["lock site", "unlock site", "change site", "draw site"],
        "confidence": 0.9,
    },
    {
        "action_id": "request_detect_grading",
        "description": "Route grading detection requests to the data/grading UI or supported grading generation workflow.",
        "required_inputs": ["terrain/source data or confirmed site context"],
        "supported_object_types": ["grading", "terrain", "survey", "map"],
        "side_effects": [],
        "blocked_if": ["terrain/source data is missing", "UI selection is required"],
        "engineer_review_required": True,
        "intent": "ui_navigation",
        "patterns": ["detect grading", "detect slope", "find contours"],
        "confidence": 0.89,
    },
    {
        "action_id": "request_review_export_package",
        "description": "Route review package/export requests to the Deliver panel or report export blockers truthfully.",
        "required_inputs": ["current planner result", "export gates passing"],
        "supported_object_types": ["review_package", "report", "dxf", "deliverables"],
        "side_effects": [],
        "blocked_if": ["planner result is missing", "export gates are blocked"],
        "engineer_review_required": True,
        "intent": "ui_navigation",
        "patterns": ["export review package", "make review package", "create review package", "deliver package", "export report", "download dxf"],
        "confidence": 0.9,
    },
    {
        "action_id": "unsupported_ui_action",
        "description": "A UI action was requested but is not safely chat-routable yet.",
        "required_inputs": ["supported UI action"],
        "supported_object_types": ["ui_action"],
        "side_effects": [],
        "blocked_if": ["unsupported UI action"],
        "engineer_review_required": False,
        "intent": "ui_navigation",
        "patterns": ["unsupported ui action"],
        "confidence": 0.8,
    },
    {
        "action_id": "site_setup",
        "description": "Set draft site dimensions, acreage, or address/location evidence without generating a design.",
        "required_inputs": ["site dimensions, acreage, or address"],
        "supported_object_types": ["site", "lot", "address", "location_context"],
        "side_effects": ["updates draft site setup state when project storage is available"],
        "blocked_if": ["address geocoding failed", "no site setup field was provided"],
        "engineer_review_required": True,
        "intent": "site_setup",
        "patterns": ["site size", "set site", "blank site", "address is"],
        "confidence": 0.94,
    },
    {
        "action_id": "explain_blockers",
        "description": "Explain current blockers, missing inputs, failed checks, or why export/design is not working.",
        "required_inputs": ["current workspace/project context"],
        "supported_object_types": ["workspace", "export", "grading", "drainage", "utilities", "layout"],
        "side_effects": [],
        "blocked_if": ["no current workspace context is available"],
        "engineer_review_required": True,
        "intent": "workspace_state",
        "patterns": [
            "why broken",
            "broken",
            "not working",
            "why can't export",
            "why cant export",
            "why can’t export",
            "why export",
            "what blocked",
            "what's wrong",
            "whats wrong",
        ],
        "confidence": 0.88,
    },
    {
        "action_id": "fix_current_design",
        "description": "Run a focused fix pass on the current design without approving or releasing it.",
        "required_inputs": ["existing plan"],
        "supported_object_types": ["workspace", "layout", "grading", "drainage", "utilities"],
        "side_effects": ["queues planner fix workflow"],
        "blocked_if": ["no existing plan is available"],
        "engineer_review_required": True,
        "intent": "fix",
        "patterns": ["make this work", "fix this", "fix it", "repair this", "resolve this", "make it work"],
        "confidence": 0.84,
    },
    {
        "action_id": "revise_drainage",
        "description": "Queue a drainage-focused revision or generation workflow.",
        "required_inputs": ["existing plan", "detention basin or outfall target"],
        "supported_object_types": ["drainage", "storm", "basin", "outfall", "pipe", "inlet"],
        "side_effects": ["queues drainage planner workflow"],
        "blocked_if": ["no plan is available", "detention basin or outfall target is missing"],
        "engineer_review_required": True,
        "intent": "drainage_command",
        "patterns": ["fix drainage", "fix storm", "make drainage work", "repair drainage", "drainage"],
        "confidence": 0.87,
    },
    {
        "action_id": "place_basin",
        "description": "Create draft detention basin/pond geometry from a user-directed location hint.",
        "required_inputs": ["existing plan", "basin location or low point"],
        "supported_object_types": ["basin", "detention_basin", "pond"],
        "side_effects": ["creates draft canonical geometry when execution support and project state exist"],
        "blocked_if": ["no plan is available", "basin location or low point is missing"],
        "engineer_review_required": True,
        "intent": "object_or_layout_command",
        "patterns": ["put pond", "place pond", "put basin", "place basin", "detention in low", "pond in low"],
        "confidence": 0.91,
    },
    {
        "action_id": "classify_geometry_as_parking",
        "description": "Classify selected user-drawn geometry as draft parking for engineer review.",
        "required_inputs": ["one selected drawn geometry"],
        "supported_object_types": ["parking", "polygon", "manual_drawn_geometry"],
        "side_effects": ["persists draft geometry classification when handoff is valid"],
        "blocked_if": ["selected drawn geometry is missing or ambiguous", "canonical geometry handoff is invalid"],
        "engineer_review_required": True,
        "intent": "object_or_layout_command",
        "patterns": ["turn polygon into parking", "make polygon parking", "make this parking", "this polygon parking"],
        "confidence": 0.93,
    },
    {
        "action_id": "update_road_geometry",
        "description": "Interpret a road relocation/reroute request and block if canonical road edit execution is unavailable.",
        "required_inputs": ["existing plan", "target road", "road change direction or offset"],
        "supported_object_types": ["road", "building"],
        "side_effects": [],
        "blocked_if": ["canonical road update execution is unsupported", "target road or movement details are missing"],
        "engineer_review_required": True,
        "intent": "object_or_layout_command",
        "patterns": ["move road", "road away", "reroute road", "shift road", "move the road away"],
        "confidence": 0.89,
    },
    {
        "action_id": "set_no_assumptions_mode",
        "description": "Switch Civora to strict/no-assumption mode so inferred values do not change canonical state.",
        "required_inputs": [],
        "supported_object_types": ["workspace_settings"],
        "side_effects": ["updates chat controls to user/manual strategy mode"],
        "blocked_if": [],
        "engineer_review_required": False,
        "intent": "mode_command",
        "patterns": ["don't assume anything", "dont assume anything", "do not assume", "no assumptions"],
        "confidence": 0.97,
    },
    {
        "action_id": "generate_grading",
        "description": "Queue grading generation or revision with terrain inputs.",
        "required_inputs": ["existing plan", "terrain, slope, or target drainage direction"],
        "supported_object_types": ["grading", "contours", "surface"],
        "side_effects": ["queues grading planner workflow"],
        "blocked_if": ["terrain or slope information is missing"],
        "engineer_review_required": True,
        "intent": "grading_command",
        "patterns": ["generate grading", "run grading", "grade this", "fix grading"],
        "confidence": 0.86,
    },
    {
        "action_id": "unsupported_or_unclear",
        "description": "No supported Civora action can be selected with enough confidence.",
        "required_inputs": ["clear supported Civora request"],
        "supported_object_types": [],
        "side_effects": [],
        "blocked_if": ["low confidence", "unsupported capability"],
        "engineer_review_required": False,
        "intent": "unsupported_or_not_understood",
        "patterns": [],
        "confidence": 0.0,
    },
]


_ACTION_BY_ID = {action["action_id"]: action for action in ACTION_REGISTRY}


def _normalized_text(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("’", "'").replace("`", "'").replace("“", '"').replace("”", '"')
    return " ".join(text.split())


def _candidate(action_id: str, confidence: float, reasons: List[str]) -> Dict[str, Any]:
    action = _ACTION_BY_ID[action_id]
    return {
        "action_id": action_id,
        "description": action["description"],
        "confidence": round(max(0.0, min(float(confidence), 1.0)), 3),
        "reasons": reasons[:4],
    }


def _has_plan(context: Dict[str, Any]) -> bool:
    return bool(context.get("has_plan") or (context.get("current_project") or {}).get("latest_result"))


def _has_selected_geometry(context: Dict[str, Any]) -> bool:
    return bool(
        context.get("selected_geometry_ids")
        or context.get("referenced_geometry_ids")
        or context.get("selected_object_ids")
        or context.get("referenced_object_ids")
        or context.get("activePlacementId")
        or context.get("active_placement_id")
    )


def _has_drainage_target(text: str, context: Dict[str, Any]) -> bool:
    if any(token in text for token in ["basin", "pond", "outfall", "low spot", "low point", "low corner"]):
        return True
    blob = _normalized_text(str(context.get("current_project") or "")[:12000])
    return any(token in blob for token in ["basin", "pond", "outfall", "low_point", "low corner"])


def _responsibility_blocker(text: str) -> Optional[str]:
    if any(
        phrase in text
        for phrase in [
            "approve",
            "stamp",
            "seal",
            "sign off",
            "signoff",
            "certify",
            "issue for construction",
            "construction approved",
            "construction ready",
            "construction-ready",
            "permit ready",
            "permit-ready",
        ]
    ):
        return (
            "Civora cannot approve, stamp, seal, sign, certify, submit, act as engineer of record, "
            "or release construction documents."
        )
    return None


def _fake_evidence_blocker(text: str) -> Optional[str]:
    if any(
        phrase in text
        for phrase in [
            "fake survey",
            "make up survey",
            "invent survey",
            "fake standard",
            "make up standard",
            "invent standard",
            "fake calculation",
            "make up calculation",
            "pretend calculation",
        ]
    ):
        return "Civora cannot fabricate survey/control, standards, calculations, approvals, exports, or readiness evidence."
    return None


def _missing_inputs(action_id: str, text: str, context: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    if action_id in {"fix_current_design", "revise_drainage", "place_basin", "update_road_geometry", "generate_grading"} and not _has_plan(context):
        missing.append("existing plan")
    if action_id == "revise_drainage" and not _has_drainage_target(text, context):
        missing.append("detention basin or outfall target")
    if action_id == "place_basin" and not any(token in text for token in ["low", "corner", "north", "south", "east", "west", "selected", "this", "that"]):
        missing.append("basin location or low point")
    if action_id == "classify_geometry_as_parking" and not _has_selected_geometry(context):
        missing.append("selected drawn geometry")
    if action_id == "update_road_geometry":
        if not any(token in text for token in ["away", "north", "south", "east", "west", "reroute", "shift", "move"]):
            missing.append("road change direction or offset")
        if not any(token in text for token in ["road", "selected", "this", "that"]):
            missing.append("target road")
    if action_id == "generate_grading" and not any(token in text for token in ["slope", "contour", "elevation", "low", "high", "grade"]):
        missing.append("terrain, slope, or target drainage direction")
    return list(dict.fromkeys(missing))


def _next_question(action_id: str, missing: List[str]) -> str:
    if not missing:
        return ""
    if action_id == "revise_drainage":
        return "Where should stormwater discharge or be stored: a detention basin, pond, outfall, or selected low point?"
    if action_id == "place_basin":
        return "Where should the basin/pond go: a low point, corner, or selected geometry?"
    if action_id == "classify_geometry_as_parking":
        return "Which drawn polygon should become draft parking? Select exactly one geometry and ask again."
    if action_id == "update_road_geometry":
        return "Which road should move, and how far or in what direction should it move away from the building?"
    if action_id == "fix_current_design":
        return "Which saved/current design should I run the fix pass against?"
    if action_id == "generate_grading":
        return "What is the high side, low side, or approximate slope for grading?"
    return "Please provide " + ", ".join(missing[:2]) + "."


def _candidate_actions(text: str) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    if re.search(r"\b(open|show|go to|take me to)\b.*\b(setup|canvas|review|deliver|data|layers|settings|objects|generate)\b", text):
        candidates.append(_candidate("open_ui_panel", 0.94, ["UI navigation wording"]))
    if re.search(r"\b(2d|3d|standard|high quality|high-quality|quality)\b", text) and any(token in text for token in ["canvas", "preview", "view", "mode", "quality", "3d", "2d"]):
        candidates.append(_candidate("set_preview_mode", 0.9, ["preview mode/quality wording"]))
    if re.search(r"\b(lock|unlock|draw|change|redraw)\b.*\b(site|boundary)\b|\b(site|boundary)\b.*\b(lock|unlock|draw|change|redraw)\b", text):
        candidates.append(_candidate("request_site_lock_state", 0.9, ["site boundary lock/draw wording"]))
    if re.search(r"\b(detect|find|derive)\b.*\b(grading|slope|contour|terrain)\b", text):
        candidates.append(_candidate("request_detect_grading", 0.89, ["grading detection wording"]))
    if re.search(r"\b(export|deliver|download|prepare|make|create|build)\b.*\b(review package|package|report|dxf|deliverable|deliverables)\b", text):
        candidates.append(_candidate("request_review_export_package", 0.9, ["review/export package wording"]))
    if re.search(r"\b(undo|redo|search)\b", text):
        candidates.append(_candidate("unsupported_ui_action", 0.82, ["unsupported UI action wording"]))
    if re.search(r"\b(?:site|lot|boundary|size)\b.*\b\d+(?:\.\d+)?\s*(?:ft|feet|')?\s*(?:x|by)\s*\d+(?:\.\d+)?\b", text) or "address is" in text or re.search(r"\b\d+(?:\.\d+)?\s*(?:ac|acre|acres)\b.*\bblank site\b", text):
        candidates.append(_candidate("site_setup", 0.94, ["site setup dimensions/address wording"]))
    if any(phrase in text for phrase in ["why is this broken", "why broken", "broken", "not working", "what's wrong", "whats wrong"]):
        candidates.append(_candidate("explain_blockers", 0.88, ["debug/explain wording"]))
    if any(phrase in text for phrase in ["why can't i export", "why cant i export", "why can’t i export", "why can't export", "why cant export"]):
        candidates.append(_candidate("explain_blockers", 0.93, ["export blocker wording"]))
    if any(phrase in text for phrase in ["make this work", "make it work", "fix this", "fix it", "repair this", "resolve this"]):
        candidates.append(_candidate("fix_current_design", 0.84, ["fix/work wording"]))
    preserving_drainage = any(phrase in text for phrase in ["keep the drainage", "keep drainage", "preserve the drainage", "preserve drainage"])
    if not preserving_drainage and re.search(r"\bfix\b.*\b(drainage|storm)\b|\b(drainage|storm)\b.*\b(work|fix|broken)\b", text):
        candidates.append(_candidate("revise_drainage", 0.91, ["drainage fix wording"]))
    if any(phrase in text for phrase in ["put that pond in the low spot", "put pond in the low", "place pond in the low", "put basin in the low", "detention basin in the low"]):
        candidates.append(_candidate("place_basin", 0.94, ["basin/pond location wording"]))
    if re.search(r"\b(turn|make|classify)\b.*\b(polygon|shape|geometry|that|this)\b.*\bparking\b", text):
        candidates.append(_candidate("classify_geometry_as_parking", 0.94, ["geometry classification wording"]))
    if re.search(r"\b(move|shift|reroute)\b.*\broad\b|\broad\b.*\baway\b.*\bbuilding\b", text):
        candidates.append(_candidate("update_road_geometry", 0.9, ["road relocation wording"]))
    if any(phrase in text for phrase in ["don't assume anything", "dont assume anything", "do not assume", "no assumptions"]):
        candidates.append(_candidate("set_no_assumptions_mode", 0.97, ["strict/no-assumption wording"]))
    if re.search(r"\b(generate|run|fix|create)\b.*\bgrading\b|\bgrade this\b", text):
        candidates.append(_candidate("generate_grading", 0.86, ["grading workflow wording"]))
    candidates.sort(key=lambda item: item["confidence"], reverse=True)
    return candidates


def build_action_registry() -> List[Dict[str, Any]]:
    public_keys = {
        "action_id",
        "description",
        "required_inputs",
        "supported_object_types",
        "side_effects",
        "blocked_if",
        "engineer_review_required",
    }
    return [{key: deepcopy(value) for key, value in action.items() if key in public_keys} for action in ACTION_REGISTRY]


def plan_chat_action(message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    text = _normalized_text(message)
    ctx = dict(context or {})
    candidates = _candidate_actions(text)
    selected = candidates[0] if candidates and candidates[0]["confidence"] >= CONFIDENCE_EXECUTION_THRESHOLD else None
    action_id = str(selected.get("action_id")) if selected else ""
    safety_blockers = [item for item in [_responsibility_blocker(text), _fake_evidence_blocker(text)] if item]
    missing = _missing_inputs(action_id, text, ctx) if action_id else []

    if not selected:
        next_question = "Please ask for a supported Civora action: explain blockers, fix a current design, revise drainage/grading, classify selected geometry, or update a road."
    elif safety_blockers:
        next_question = ""
    else:
        next_question = _next_question(action_id, missing)

    return {
        "user_goal": str(message or "").strip(),
        "candidate_actions": candidates,
        "selected_action": deepcopy(_ACTION_BY_ID.get(action_id, {})) if action_id else None,
        "selected_action_id": action_id,
        "confidence": float(selected["confidence"]) if selected else (float(candidates[0]["confidence"]) if candidates else 0.0),
        "low_confidence": not bool(selected),
        "missing_inputs": missing,
        "safety_blockers": safety_blockers,
        "next_best_question": next_question,
        "action_registry": build_action_registry(),
    }


def command_intent_from_action_plan(action_plan: Dict[str, Any]) -> str:
    selected = action_plan.get("selected_action") or {}
    return str(selected.get("intent") or "")
