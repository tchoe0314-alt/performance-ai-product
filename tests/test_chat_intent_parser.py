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


if __name__ == "__main__":
    unittest.main()
