from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.application.design_workflows import run_orchestration
from parsers.chat_intent_parser import decide_chat_message
from planner_orchestrator import PlannerOrchestratorRequest, orchestrate_plan


FORBIDDEN_PHRASES = (
    "Manual" + "-mode validation failed",
    "Manual " + "Mode",
    "Manual " + "mode",
    "manual validation " + "failed",
    "backend validation",
    "Traceback",
    "UnboundLocalError",
)


@dataclass
class FakePlannerOrchestratorRequest:
    input_mode: str = "assisted"
    strict_mode: bool = False
    full_design_mode: bool = False
    prompt_text: Optional[str] = None
    image_path: Optional[str] = None
    manual_fields: Dict[str, Any] = field(default_factory=dict)
    image_width_px: Optional[int] = None
    image_height_px: Optional[int] = None
    pixels_per_unit: Optional[float] = None
    plan_type_hint: Optional[str] = None
    units: str = "ft"
    allow_ai_fill_for_blanks: bool = True
    persist_trace_metadata: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)
    progress_callback: Optional[Any] = None


@dataclass
class FakeAssumption:
    field_name: str
    assumed_value: Any
    reason: str


@dataclass
class FakeOrchestratorResult:
    success: bool = True
    message: str = "Generated coordinated plan."
    parsed_payload: Dict[str, Any] = field(default_factory=dict)
    final_plan: Dict[str, Any] = field(default_factory=lambda: {"meta": {"source_quality": "terrain"}})
    warnings: List[Any] = field(default_factory=list)
    errors: List[Any] = field(default_factory=list)
    issues: List[Any] = field(default_factory=list)
    assumptions: List[Any] = field(
        default_factory=lambda: [
            FakeAssumption(
                field_name="grading source",
                assumed_value="terrain-derived surface",
                reason="Assisted was enabled and terrain context was available.",
            )
        ]
    )
    metadata: Dict[str, Any] = field(default_factory=lambda: {"assisted_enabled": True})


def _fake_load_orchestrator(calls: Dict[str, Any]):
    def fake_orchestrate(req: FakePlannerOrchestratorRequest) -> FakeOrchestratorResult:
        calls["request"] = req
        return FakeOrchestratorResult(parsed_payload={"input_mode": req.input_mode})

    return FakePlannerOrchestratorRequest, fake_orchestrate


def _readiness_for(field: str, why: str):
    def assess_design_readiness(_message: str, _context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "assistant_message": (
                f"Civora needs {field} before it can complete this step. "
                "Add it, or turn on Assisted to let Civora infer a clearly labeled assumption."
            ),
            "missing_requirements": [{"field": field, "why_needed": why}],
            "reason": "Missing core design inputs",
        }

    return assess_design_readiness


def _clean_text(text: str) -> bool:
    return bool(text.strip()) and not any(phrase in text for phrase in FORBIDDEN_PHRASES)


def _record(
    *,
    name: str,
    passed: bool,
    exact_response: str,
    first_failing_layer: Optional[str],
    category: str,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "name": name,
        "pass": bool(passed),
        "exact_response": exact_response,
        "first_failing_layer": first_failing_layer,
        "category": category,
        "details": details or {},
    }


def run() -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    missing_cases = [
        ("missing_no_site_boundary", "site boundary", "A locked site boundary is needed to locate and size the design."),
        ("missing_no_drainage_outlet", "drainage outlet", "A basin or outfall is needed before drainage can be completed."),
        ("missing_no_grading_surface", "grading surface", "Survey, terrain, or an approved assumption is needed for grading/drainage."),
        ("missing_no_building_dimensions", "building dimensions", "Building dimensions are needed to place objects and compute coverage."),
        ("missing_incomplete_utility_info", "utility tie-in information", "Utility routing needs known or assumed source and connection context."),
    ]
    for name, field, why_needed in missing_cases:
        calls: Dict[str, Any] = {}
        response = run_orchestration(
            {
                "input_mode": "user",
                "allow_ai_fill_for_blanks": False,
                "prompt_text": f"Design this site but I do not have {field}.",
                "manual_fields": {},
            },
            load_orchestrator=lambda calls=calls: _fake_load_orchestrator(calls),
            assess_design_readiness=_readiness_for(field, why_needed),
        )
        missing = response.get("missing_requirements") or {}
        passed = (
            response.get("success") is False
            and _clean_text(str(response.get("message") or ""))
            and missing.get("missing_fields") == [field]
            and bool(missing.get("suggested_next_actions"))
            and bool(missing.get("can_assist_if_enabled"))
            and "request" not in calls
        )
        results.append(
            _record(
                name=name,
                passed=passed,
                exact_response=str(response.get("message") or ""),
                first_failing_layer=None if passed else "validation",
                category="validation",
                details={"missing_requirements": missing},
            )
        )

    calls = {}
    assisted = run_orchestration(
        {
            "input_mode": "assisted",
            "allow_ai_fill_for_blanks": True,
            "prompt_text": "Design this site with missing grading context.",
            "manual_fields": {},
        },
        load_orchestrator=lambda: _fake_load_orchestrator(calls),
        assess_design_readiness=_readiness_for("grading surface", "Needed for terrain-aware grading."),
    )
    assisted_pass = (
        assisted.get("success") is True
        and "request" in calls
        and bool(assisted.get("assumptions"))
        and "Assisted was enabled" in str((assisted.get("assumptions") or [{}])[0].get("reason") or "")
    )
    results.append(
        _record(
            name="assisted_on_uses_labeled_assumptions",
            passed=assisted_pass,
            exact_response=str(assisted.get("message") or ""),
            first_failing_layer=None if assisted_pass else "orchestration",
            category="orchestration",
            details={"assumptions": assisted.get("assumptions")},
        )
    )

    real_off = orchestrate_plan(
        PlannerOrchestratorRequest(
            input_mode="user",
            manual_fields={
                "project_name": "Conversation QA",
                "units": "ft",
                "project_type": "commercial",
                "disciplines": ["grading", "drainage"],
                "lot": {"x": 0, "y": 0, "w": 90, "h": 60},
                "buildings": [{"name": "Building 1"}],
                "drainage": {"min_pipe_slope_pct": 0.5},
                "utility_network": {"source": "omit", "value": None},
            },
            allow_ai_fill_for_blanks=False,
            meta={"requested_system": "drainage", "assisted_enabled": False},
        )
    )
    real_missing = real_off.metadata.get("missing_requirements") or {}
    real_off_pass = (
        real_off.success is False
        and _clean_text(real_off.message)
        and bool(real_missing.get("missing_fields"))
        and bool(real_missing.get("why_needed"))
    )
    results.append(
        _record(
            name="real_orchestrator_assisted_off_missing_info",
            passed=real_off_pass,
            exact_response=real_off.message,
            first_failing_layer=None if real_off_pass else "orchestration",
            category="orchestration",
            details={"missing_requirements": real_missing},
        )
    )

    real_on = orchestrate_plan(
        PlannerOrchestratorRequest(
            input_mode="assisted",
            manual_fields={
                "project_name": "Conversation QA Assisted",
                "units": "ft",
                "project_type": "commercial",
                "disciplines": ["grading", "drainage"],
                "lot": {"x": 0, "y": 0, "w": 90, "h": 60},
                "buildings": [{"name": "Building 1"}],
                "drainage": {"min_pipe_slope_pct": 0.5},
                "utility_network": {"source": "omit", "value": None},
            },
            allow_ai_fill_for_blanks=True,
            meta={"requested_system": "drainage", "assisted_enabled": True},
        )
    )
    real_on_pass = real_on.success is True and _clean_text(real_on.message) and bool(real_on.assumptions)
    results.append(
        _record(
            name="real_orchestrator_assisted_on_proceeds",
            passed=real_on_pass,
            exact_response=real_on.message,
            first_failing_layer=None if real_on_pass else "orchestration",
            category="orchestration",
            details={"assumption_count": len(real_on.assumptions)},
        )
    )

    with patch(
        "parsers.chat_intent_parser._load_chat_client",
        side_effect=RuntimeError("Conversation QA uses deterministic local chat logic."),
    ):
        chat_missing = decide_chat_message({"message": "Design a site with drainage.", "context": {"strategy_mode": "user"}})
        chat_missing_pass = (
            chat_missing.get("needs_clarification") is True
            and chat_missing.get("intent") == "conversation"
            and _clean_text(str(chat_missing.get("assistant_message") or ""))
        )
        results.append(
            _record(
                name="chat_missing_info_is_clear",
                passed=chat_missing_pass,
                exact_response=str(chat_missing.get("assistant_message") or ""),
                first_failing_layer=None if chat_missing_pass else "UX",
                category="UX",
                details={"decision": chat_missing},
            )
        )

        for name, message, expected_mode, expected_phrase in [
            ("chat_assisted_off_toggle", "turn off assisted", "user", "Assisted off"),
            ("chat_legacy_manual_alias", "switch to manual mode", "user", "Assisted off"),
            ("chat_assisted_on_toggle", "turn on assisted", "assisted", "Assisted on"),
        ]:
            decision = decide_chat_message({"message": message, "context": {}})
            response = str(decision.get("assistant_message") or "")
            passed = (
                decision.get("control_overrides", {}).get("strategyMode") == expected_mode
                and expected_phrase in response
                and _clean_text(response)
            )
            results.append(
                _record(
                    name=name,
                    passed=passed,
                    exact_response=response,
                    first_failing_layer=None if passed else "UX",
                    category="UX",
                    details={"decision": decision},
                )
            )

        memory = decide_chat_message(
            {
                "message": "what do you remember?",
                "context": {
                    "strategy_mode": "user",
                    "chat_thread": [
                        {"role": "user", "content": "Use a 200 by 150 foot retail pad site with drainage."}
                    ],
                },
            }
        )
        memory_response = str(memory.get("assistant_message") or "")
        memory_pass = _clean_text(memory_response) and "200 by 150" in memory_response and "retail" in memory_response.lower()
        results.append(
            _record(
                name="chat_memory_preserves_prior_input",
                passed=memory_pass,
                exact_response=memory_response,
                first_failing_layer=None if memory_pass else "memory",
                category="memory",
                details={"decision": memory},
            )
        )

    return results


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
