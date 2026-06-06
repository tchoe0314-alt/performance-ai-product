import unittest

from backend.application.chat_workflows import decide_chat
from backend.planning.ai_orchestration_evidence import (
    EVIDENCE_VERSION,
    build_ai_orchestration_evidence,
    validate_ai_orchestration_evidence,
)
from backend.planning.engine_depth_audit import CLASS_REVIEW, run_engine_depth_audit_scenario
from backend.planning.engine_readiness import evaluate_engine_readiness
from parsers.chat_intent_parser import decide_chat_message


def _record(project_id="project_123"):
    return {
        "project_id": project_id,
        "name": "Saved Project",
        "description": "",
        "session_id": None,
        "tags": [],
        "project_input": {"project_type": "mixed_use", "manual_fields": {"lot": {"w": 500, "h": 400}}},
        "latest_result": {
            "success": True,
            "final_plan": {
                "project_name": "Saved Project",
                "meta": {
                    "canonical_revision": "rev-1",
                    "drainage_canonical": {"basins": [{"id": "BASIN-1", "label": "Detention basin"}]},
                    "construction_release_allowed": False,
                    "construction_ready": False,
                },
            },
        },
        "session_state": {},
        "metadata": {},
    }


class RecordingProjectStore:
    def __init__(self, record=None):
        self.record = record or _record()
        self.saved = []

    def get_project(self, *, user_id, project_id):
        return self.record

    def save_project(self, **kwargs):
        self.saved.append(kwargs)
        self.record = {
            **self.record,
            "project_input": kwargs["project_input"],
            "latest_result": kwargs["latest_result"],
        }
        return self.record


def _minimal_ai_plan(payload):
    evidence = build_ai_orchestration_evidence(
        user_intent="Design the mixed-use site and route systems.",
        parsed_intent="mixed_use_site_plan",
        selected_workflow="single_plan",
        required_inputs=["site geometry", "requested systems"],
        missing_inputs=[],
        assumptions=["fixture assumes local coordinate basis for audit row only"],
        actions_planned=["single_plan"],
        actions_executed=["single_plan"],
        actions_blocked=[],
        affected_systems=["layout", "grading", "drainage", "utilities"],
        next_best_action="Engineer review required before construction use.",
        confidence=0.78,
        unsupported_actions=[],
        state_changed=True,
    )
    return {
        "project_name": payload.get("project_name"),
        "meta": {
            "lot": payload.get("lot") or {"w": 875.0, "h": 700.0},
            "building_count": 4,
            "parking_program": {"stall_count": 180},
            EVIDENCE_VERSION: evidence,
            "construction_release_allowed": False,
            "construction_ready": False,
        },
    }


class AIOrchestrationEvidenceTests(unittest.TestCase):
    def test_valid_multi_step_workflow_creates_traceable_orchestration_evidence(self):
        store = RecordingProjectStore()

        result = decide_chat(
            {
                "message": "generate drainage",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        evidence = result[EVIDENCE_VERSION]
        self.assertEqual(evidence["parsed_intent"], "drainage_command")
        self.assertEqual(evidence["selected_workflow"], "drainage")
        self.assertEqual(evidence["actions_executed"], ["queued_engineering_workflow"])
        self.assertIn("drainage", evidence["affected_systems"])
        self.assertTrue(evidence["engineer_review_required"])
        self.assertFalse(evidence["construction_release_allowed"])
        saved_meta = store.record["latest_result"]["final_plan"]["meta"]
        self.assertEqual(saved_meta[EVIDENCE_VERSION]["selected_workflow"], "drainage")

    def test_missing_inputs_produce_targeted_blockers(self):
        result = decide_chat(
            {"message": "add a building", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=RecordingProjectStore(),
            user_id="user_1",
        )

        evidence = result[EVIDENCE_VERSION]
        self.assertIn("building dimensions", evidence["missing_inputs"])
        self.assertTrue(evidence["actions_blocked"])
        self.assertFalse(evidence["state_changed"])
        self.assertFalse(evidence["actions_executed"])

    def test_unsupported_action_stays_unsupported(self):
        result = decide_chat(
            {"message": "purple banana orbit sandwich", "context": {}},
            decide_chat_message=decide_chat_message,
        )

        evidence = result[EVIDENCE_VERSION]
        self.assertEqual(evidence["parsed_intent"], "unsupported_or_not_understood")
        self.assertTrue(evidence["unsupported_actions"])
        self.assertFalse(evidence["state_changed"])
        self.assertFalse(evidence["actions_executed"])

    def test_no_assumption_mode_blocks_assumptions(self):
        store = RecordingProjectStore()

        def fake_decider(_payload):
            return {
                "success": True,
                "intent": "design",
                "assistant_message": "Prepared.",
                "run_mode": "run",
                "design_prompt": "add a building",
                "needs_clarification": False,
                "reason": "test",
                "confidence": 1.0,
                "control_overrides": {},
                "response_metadata": {
                    "intent": "object_or_layout_command",
                    "required_missing_inputs": [],
                    "action_taken": "prepared_canonical_edit",
                    "action_blocked_reason": "",
                    "affected_systems": ["layout"],
                    "assumptions": ["draft building location"],
                    "next_best_action": "",
                    "command_payload": {
                        "object_type": "building",
                        "operation": "create",
                        "width": 100,
                        "depth": 60,
                        "assumption_policy": "strict",
                    },
                },
            }

        result = decide_chat(
            {
                "message": "add a 100 by 60 building",
                "context": {"strategy_mode": "user", "current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=fake_decider,
            project_store=store,
            user_id="user_1",
        )

        evidence = result[EVIDENCE_VERSION]
        self.assertIn("explicit user-provided command inputs", evidence["missing_inputs"])
        self.assertEqual(evidence["assumptions"], [])
        self.assertFalse(evidence["state_changed"])
        self.assertEqual(store.saved, [])

    def test_fix_this_workflow_plans_only_supported_actions(self):
        result = decide_chat(
            {"message": "fix this", "context": {"has_plan": True}},
            decide_chat_message=decide_chat_message,
        )

        evidence = result[EVIDENCE_VERSION]
        self.assertEqual(evidence["selected_workflow"], "fix")
        self.assertEqual(evidence["actions_planned"], ["run_supported_fix_pass"])
        self.assertEqual(evidence["unsupported_actions"], [])
        self.assertFalse(evidence["construction_release_allowed"])

    def test_construction_release_remains_false(self):
        evidence = build_ai_orchestration_evidence(
            user_intent="create review package",
            parsed_intent="generate_command",
            selected_workflow="all_enabled_systems",
            required_inputs=[],
            missing_inputs=[],
            assumptions=[],
            actions_planned=["all_enabled_systems"],
            actions_executed=["all_enabled_systems"],
            actions_blocked=[],
            affected_systems=["layout"],
            next_best_action="Engineer review required.",
            confidence=0.8,
            unsupported_actions=[],
            state_changed=True,
        )

        self.assertTrue(validate_ai_orchestration_evidence(evidence)["valid"])
        self.assertFalse(evidence["construction_release_allowed"])
        self.assertFalse(evidence["construction_ready"])

    def test_engine_readiness_and_audit_classify_valid_evidence_as_review_level(self):
        plan = _minimal_ai_plan({"project_name": "AI audit fixture"})

        readiness = evaluate_engine_readiness(plan)
        ai_row = readiness["engines"]["ai_orchestration"]
        self.assertEqual(ai_row["status"], "needs_engineering_review")
        self.assertIn(EVIDENCE_VERSION, ai_row["evidence"])

        audit = run_engine_depth_audit_scenario("mixed_use_14_acre_site", build_plan_fn=_minimal_ai_plan)
        audit_row = audit["required_engine_results"]["ai_orchestration"]
        self.assertEqual(audit_row["actual_depth_classification"], CLASS_REVIEW)
        self.assertGreaterEqual(audit_row["score"], 70.0)

    def test_fake_unsupported_success_is_blocked(self):
        evidence = build_ai_orchestration_evidence(
            user_intent="approve this",
            parsed_intent="responsibility_guard",
            selected_workflow="responsibility_guard",
            required_inputs=[],
            missing_inputs=[],
            assumptions=[],
            actions_planned=[],
            actions_executed=["approved"],
            actions_blocked=[],
            affected_systems=["review"],
            next_best_action="External licensed engineer approval required.",
            confidence=0.9,
            unsupported_actions=["Civora cannot approve construction documents."],
            state_changed=True,
        )

        validation = validate_ai_orchestration_evidence(evidence)
        self.assertFalse(validation["valid"])
        self.assertIn("fake_success_detected", validation["blockers"])


if __name__ == "__main__":
    unittest.main()
