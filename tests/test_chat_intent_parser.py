import unittest
from typing import Optional

from parsers.chat_intent_parser import decide_chat_message


def _decide(message: str, context: Optional[dict] = None):
    return decide_chat_message({"message": message, "context": context or {}})


class ChatIntentParserTest(unittest.TestCase):
    def test_greeting_stays_conversation(self):
        result = _decide("how r u")
        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(result["run_mode"], "none")
        self.assertFalse(result["needs_clarification"])

    def test_settings_only_message_does_not_run(self):
        result = _decide("turn off grading and use manual mode")
        self.assertEqual(result["intent"], "settings")
        self.assertEqual(result["run_mode"], "none")
        self.assertEqual(result["control_overrides"]["strategyMode"], "manual")
        self.assertEqual(result["control_overrides"]["grading"], False)

    def test_manual_mode_ambiguous_request_asks_for_more(self):
        result = _decide(
            "make me a site",
            {
                "strategy_mode": "manual",
                "roads": True,
                "grading": True,
                "drainage": True,
                "utilities": True,
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertTrue(result["needs_clarification"])
        self.assertEqual(result["run_mode"], "none")
        self.assertIn("which systems to include", result["assistant_message"])

    def test_follow_up_design_edit_runs_when_plan_exists(self):
        result = _decide(
            "move the building north and add more parking",
            {
                "has_plan": True,
                "project_type": "commercial_pad",
                "lot_width": "220",
                "lot_height": "180",
                "parking_count": "32",
                "roads": True,
                "grading": True,
                "drainage": True,
                "utilities": True,
            },
        )
        self.assertEqual(result["intent"], "design")
        self.assertEqual(result["run_mode"], "run")
        self.assertFalse(result["needs_clarification"])

    def test_context_question_answers_without_run(self):
        result = _decide(
            "what assumptions did you make?",
            {
                "has_plan": True,
                "assumptions": [
                    {
                        "field_name": "lot_width",
                        "assumed_value": "220",
                        "reason": "No exact width was provided.",
                    }
                ],
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(result["run_mode"], "none")
        self.assertIn("AI helped fill in", result["assistant_message"])

    def test_fix_question_answers_from_convergence_summary(self):
        result = _decide(
            "what did you fix?",
            {
                "has_plan": True,
                "convergence_summary": {
                    "fix_summary": {
                        "autofix_actions": ["storm_validation_retry"],
                    },
                    "dominant_issue_categories": ["storm", "drainage"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("I applied", result["assistant_message"])

    def test_blocked_question_answers_from_convergence_summary(self):
        result = _decide(
            "what is blocked?",
            {
                "has_plan": True,
                "convergence_summary": {
                    "blocked_exports": ["storm"],
                    "blocked_reasons": ["storm_graph_invalid"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("blocked outputs", result["assistant_message"])

    def test_ambiguous_directive_asks_for_clarification(self):
        result = _decide("do it")
        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(result["run_mode"], "none")
        self.assertTrue(result["needs_clarification"])
        self.assertIn("not fully sure", result["assistant_message"])

    def test_ambiguous_follow_up_with_existing_plan_asks_what_to_change(self):
        result = _decide(
            "change that",
            {
                "has_plan": True,
                "project_type": "commercial_pad",
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(result["run_mode"], "none")
        self.assertTrue(result["needs_clarification"])
        self.assertIn("current design", result["assistant_message"])

    def test_shorthand_follow_up_edit_runs_when_plan_exists(self):
        result = _decide(
            "can u add more parking pls",
            {
                "has_plan": True,
                "project_type": "commercial_pad",
                "parking_count": "32",
            },
        )
        self.assertEqual(result["intent"], "design")
        self.assertEqual(result["run_mode"], "run")
        self.assertFalse(result["needs_clarification"])

    def test_spanish_greeting_stays_conversation(self):
        result = _decide("hola")
        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(result["run_mode"], "none")
        self.assertFalse(result["needs_clarification"])

    def test_blocked_why_question_answers_from_convergence_summary(self):
        result = _decide(
            "why is export blocked?",
            {
                "has_plan": True,
                "convergence_summary": {
                    "blocked_exports": ["storm"],
                    "blocked_reasons": ["storm_graph_invalid"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("reasons", result["assistant_message"])

    def test_memory_question_answers_from_chat_history(self):
        result = _decide(
            "what do you remember?",
            {
                "chat_thread": [
                    {"role": "user", "content": "Make sure you never guess if details are missing."},
                    {"role": "assistant", "content": "Understood."},
                    {"role": "user", "content": "Prefer drainage and grading before utilities."},
                ],
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("keeping these instructions in mind", result["assistant_message"])
        self.assertIn("never guess", result["assistant_message"])

    def test_assisted_clarification_offers_ai_help_for_missing_inputs(self):
        result = _decide(
            "design a site for me",
            {
                "strategy_mode": "assisted",
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertTrue(result["needs_clarification"])
        self.assertIn("help fill in the missing details", result["assistant_message"])

    def test_follow_up_design_reply_mentions_remembered_constraint(self):
        result = _decide(
            "add more parking",
            {
                "has_plan": True,
                "project_type": "commercial_pad",
                "chat_thread": [
                    {"role": "user", "content": "Make sure you never guess if details are missing."},
                ],
            },
        )
        self.assertEqual(result["intent"], "design")
        self.assertIn("earlier instruction", result["assistant_message"])
        self.assertIn("never guess", result["assistant_message"])

    def test_clarification_reply_mentions_remembered_instruction(self):
        result = _decide(
            "do it",
            {
                "chat_thread": [
                    {"role": "user", "content": "Remember to keep drainage and grading in scope."},
                ],
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertTrue(result["needs_clarification"])
        self.assertIn("earlier instruction", result["assistant_message"])

    def test_continuation_edit_runs_from_chat_history(self):
        result = _decide(
            "actually keep the building and do the same but less parking",
            {
                "has_plan": True,
                "project_type": "commercial_pad",
                "chat_thread": [
                    {"role": "user", "content": "Design a commercial site with parking and drainage."},
                    {"role": "assistant", "content": "I can do that."},
                ],
            },
        )
        self.assertEqual(result["intent"], "design")
        self.assertEqual(result["run_mode"], "run")
        self.assertFalse(result["needs_clarification"])


if __name__ == "__main__":
    unittest.main()
