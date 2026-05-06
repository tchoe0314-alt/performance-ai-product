import unittest
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from unittest.mock import patch

from backend.application.design_workflows import run_orchestration
from parsers.chat_intent_parser import decide_chat_message
from planner_orchestrator import PlannerOrchestratorRequest, orchestrate_plan


FORBIDDEN_USER_FACING_PHRASES = (
    "Manual" + "-mode validation failed",
    "Manual " + "Mode",
    "Manual " + "mode",
    "manual validation " + "failed",
    "backend validation",
    "Traceback",
    "UnboundLocalError",
)


def _assert_professional_response(testcase: unittest.TestCase, text: str) -> None:
    testcase.assertTrue(text.strip(), "Expected a non-empty conversational response.")
    for phrase in FORBIDDEN_USER_FACING_PHRASES:
        testcase.assertNotIn(phrase, text)


@dataclass
class _FakePlannerOrchestratorRequest:
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
class _FakeAssumption:
    field_name: str
    assumed_value: Any
    reason: str


@dataclass
class _FakeOrchestratorResult:
    success: bool = True
    message: str = "Generated coordinated plan."
    parsed_payload: Dict[str, Any] = field(default_factory=dict)
    final_plan: Dict[str, Any] = field(default_factory=lambda: {"meta": {"source_quality": "terrain"}})
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    assumptions: list = field(
        default_factory=lambda: [
            _FakeAssumption(
                field_name="grading source",
                assumed_value="terrain-derived surface",
                reason="Assisted was enabled and terrain context was available.",
            )
        ]
    )
    metadata: Dict[str, Any] = field(default_factory=lambda: {"assisted_enabled": True})


def _fake_load_orchestrator(calls: Dict[str, Any]):
    def fake_orchestrate(req: _FakePlannerOrchestratorRequest) -> _FakeOrchestratorResult:
        calls["request"] = req
        return _FakeOrchestratorResult(parsed_payload={"input_mode": req.input_mode})

    return _FakePlannerOrchestratorRequest, fake_orchestrate


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


class ConversationalQATest(unittest.TestCase):
    def setUp(self) -> None:
        self._chat_client_patch = patch(
            "parsers.chat_intent_parser._load_chat_client",
            side_effect=RuntimeError("Conversation QA uses deterministic local chat logic."),
        )
        self._chat_client_patch.start()

    def tearDown(self) -> None:
        self._chat_client_patch.stop()

    def test_assisted_off_missing_requirement_scenarios_are_structured_and_human_readable(self) -> None:
        scenarios = [
            ("no site boundary", "A locked site boundary is needed to locate and size the design."),
            ("drainage outlet", "A basin or outfall is needed before drainage can be completed."),
            ("grading surface", "Survey, terrain, or an approved assumption is needed for grading/drainage."),
            ("building dimensions", "Building dimensions are needed to place objects and compute coverage."),
            ("utility tie-in information", "Utility routing needs known or assumed source and connection context."),
        ]
        for field, why_needed in scenarios:
            with self.subTest(field=field):
                calls: Dict[str, Any] = {}
                result = run_orchestration(
                    {
                        "input_mode": "user",
                        "allow_ai_fill_for_blanks": False,
                        "prompt_text": f"Design this site but I do not have {field}.",
                        "manual_fields": {},
                    },
                    load_orchestrator=lambda: _fake_load_orchestrator(calls),
                    assess_design_readiness=_readiness_for(field, why_needed),
                )
                self.assertFalse(result["success"])
                _assert_professional_response(self, result["message"])
                self.assertNotIn("request", calls, "Assisted-off missing inputs should not run the planner.")
                missing = result.get("missing_requirements") or {}
                self.assertEqual(missing.get("missing_fields"), [field])
                self.assertEqual((missing.get("why_needed") or {}).get(field), why_needed)
                self.assertTrue(missing.get("suggested_next_actions"))
                self.assertTrue(missing.get("can_assist_if_enabled"))

    def test_assisted_on_bypasses_missing_input_gate_and_preserves_assumptions(self) -> None:
        calls: Dict[str, Any] = {}
        result = run_orchestration(
            {
                "input_mode": "assisted",
                "allow_ai_fill_for_blanks": True,
                "prompt_text": "Design this site with missing grading context.",
                "manual_fields": {},
            },
            load_orchestrator=lambda: _fake_load_orchestrator(calls),
            assess_design_readiness=_readiness_for("grading surface", "Needed for terrain-aware grading."),
        )
        self.assertTrue(result["success"])
        self.assertIn("request", calls)
        self.assertTrue(calls["request"].allow_ai_fill_for_blanks)
        self.assertEqual(result["assumptions"][0]["field_name"], "grading source")
        self.assertIn("Assisted was enabled", result["assumptions"][0]["reason"])

    def test_real_orchestrator_assisted_off_returns_missing_requirements_not_jargon(self) -> None:
        req = PlannerOrchestratorRequest(
            input_mode="user",
            prompt_text=None,
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
            full_design_mode=False,
            allow_ai_fill_for_blanks=False,
            meta={"requested_system": "drainage", "assisted_enabled": False},
        )
        result = orchestrate_plan(req)
        self.assertFalse(result.success)
        _assert_professional_response(self, result.message)
        missing = result.metadata.get("missing_requirements") or {}
        self.assertTrue(missing.get("missing_fields"))
        self.assertTrue(missing.get("why_needed"))
        self.assertTrue(missing.get("suggested_next_actions"))
        self.assertTrue(missing.get("can_assist_if_enabled"))

    def test_real_orchestrator_assisted_on_proceeds_with_labeled_assumptions(self) -> None:
        req = PlannerOrchestratorRequest(
            input_mode="assisted",
            prompt_text=None,
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
            full_design_mode=False,
            allow_ai_fill_for_blanks=True,
            meta={"requested_system": "drainage", "assisted_enabled": True},
        )
        result = orchestrate_plan(req)
        self.assertTrue(result.success)
        _assert_professional_response(self, result.message)
        self.assertTrue(result.assumptions)
        self.assertFalse(result.metadata.get("missing_requirements"))

    def test_chat_missing_info_response_is_clear_and_not_jargony(self) -> None:
        result = decide_chat_message(
            {
                "message": "Design a site with drainage.",
                "context": {"strategy_mode": "user"},
            }
        )
        self.assertTrue(result["needs_clarification"])
        self.assertEqual(result["intent"], "conversation")
        _assert_professional_response(self, result["assistant_message"])
        self.assertIn("Before I move forward", result["assistant_message"])

    def test_chat_assisted_toggle_uses_assisted_on_off_labels(self) -> None:
        off = decide_chat_message({"message": "turn off assisted", "context": {}})
        legacy_off = decide_chat_message({"message": "switch to manual mode", "context": {}})
        on = decide_chat_message({"message": "turn on assisted", "context": {}})
        self.assertEqual(off["control_overrides"].get("strategyMode"), "user")
        self.assertEqual(legacy_off["control_overrides"].get("strategyMode"), "user")
        self.assertEqual(on["control_overrides"].get("strategyMode"), "assisted")
        _assert_professional_response(self, off["assistant_message"])
        _assert_professional_response(self, legacy_off["assistant_message"])
        _assert_professional_response(self, on["assistant_message"])
        self.assertIn("Assisted off", off["assistant_message"])
        self.assertIn("Assisted on", on["assistant_message"])

    def test_chat_memory_response_preserves_prior_user_context(self) -> None:
        result = decide_chat_message(
            {
                "message": "what do you remember?",
                "context": {
                    "strategy_mode": "user",
                    "chat_thread": [
                        {
                            "role": "user",
                            "content": "Use a 200 by 150 foot retail pad site with drainage.",
                        }
                    ],
                },
            }
        )
        _assert_professional_response(self, result["assistant_message"])
        self.assertIn("200 by 150", result["assistant_message"])
        self.assertIn("retail", result["assistant_message"].lower())


if __name__ == "__main__":
    unittest.main()
