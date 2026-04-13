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
        self.assertIn("stay within exactly what you asked for", result["assistant_message"])
        self.assertIn("only the missing engineering details", result["assistant_message"])

    def test_assisted_scope_confirmation_reuses_prior_design_prompt(self):
        prior_prompt = "Design a site for me with parking and drainage."
        result = _decide(
            "yes, assist with the missing details",
            {
                "strategy_mode": "assisted",
                "chat_thread": [
                    {"role": "user", "content": prior_prompt},
                    {
                        "role": "assistant",
                        "content": "If you want, I can stay within exactly what you asked for, or I can assist by filling in only the missing engineering details once you say yes.",
                    },
                ],
            },
        )
        self.assertEqual(result["intent"], "design")
        self.assertEqual(result["run_mode"], "run")
        self.assertEqual(result["design_prompt"], prior_prompt)
        self.assertIn("use AI assistance", result["assistant_message"])

    def test_small_civil_site_prompt_runs_without_site_type_in_assisted_mode(self):
        result = _decide(
            "Design a civil site plan for a 120 ft by 100 ft lot. Include one 60 ft by 40 ft building centered on the lot, parking for 10 cars, one 12 ft wide driveway from the south side, maintain 10 ft setbacks, ensure proper drainage away from the building, and add a basic storm drainage layout with at least 2 inlets and 1 pipe.",
            {
                "strategy_mode": "assisted",
                "roads": True,
                "grading": True,
                "drainage": True,
                "utilities": False,
            },
        )
        self.assertEqual(result["intent"], "design")
        self.assertEqual(result["run_mode"], "run")
        self.assertFalse(result["needs_clarification"])

    def test_small_civil_site_prompt_runs_without_site_type_in_manual_mode(self):
        result = _decide(
            "Design a civil site plan for a 120 ft by 100 ft lot. Include one 60 ft by 40 ft building centered on the lot, parking for 10 cars, one 12 ft wide driveway from the south side, maintain 10 ft setbacks, ensure proper drainage away from the building, and add a basic storm drainage layout with at least 2 inlets and 1 pipe.",
            {
                "strategy_mode": "manual",
                "roads": True,
                "grading": True,
                "drainage": True,
                "utilities": False,
            },
        )
        self.assertEqual(result["intent"], "design")
        self.assertEqual(result["run_mode"], "run")
        self.assertFalse(result["needs_clarification"])

    def test_manual_mode_reuses_prior_context_when_user_says_using_the_same_requirements(self):
        result = _decide(
            "Using the same 22-acre mixed-use site requirements, run the design in strict mode with no assumptions.",
            {
                "strategy_mode": "manual",
                "chat_thread": [
                    {
                        "role": "user",
                        "content": "Design a fully engineered civil site plan for a 22-acre mixed-use development on irregular terrain with an average slope of 5% from the northwest corner (112.5 ft) to the southeast corner (101.0 ft). Design storm drainage, sanitary sewer, and water systems with no conflicts.",
                    },
                ],
            },
        )
        self.assertEqual(result["intent"], "design")
        self.assertEqual(result["run_mode"], "run")
        self.assertFalse(result["needs_clarification"])

    def test_structured_design_prompt_with_review_bullets_does_not_get_treated_as_context_question(self):
        result = _decide(
            "Design a fully engineered civil site plan for a 22-acre mixed-use development on irregular terrain with an average slope of 5% from the northwest corner (112.5 ft) to the southeast corner (101.0 ft).\n\nInclude:\n- 3 multifamily buildings\n- 1 commercial retail pad\n\nRequirements:\n- Generate grading with spot elevations and 2-ft contours\n- Design storm drainage with inlets, pipes, inverts, and detention basin\n\nRun this in assisted mode. If you need to infer anything, do it, but clearly list:\n- assumptions made\n- why those assumptions were made\n- fixes applied\n- what still needs review\n- what is blocked",
            {
                "strategy_mode": "assisted",
            },
        )
        self.assertEqual(result["intent"], "design")
        self.assertEqual(result["run_mode"], "run")
        self.assertFalse(result["needs_clarification"])

    def test_send_it_reuses_previous_design_prompt(self):
        original_prompt = (
            "Design a fully engineered civil site plan for a 22-acre mixed-use development on irregular terrain "
            "with an average slope of 5% from the northwest corner (112.5 ft) to the southeast corner (101.0 ft)."
        )
        result = _decide(
            "send it",
            {
                "strategy_mode": "assisted",
                "chat_thread": [
                    {"role": "user", "content": original_prompt},
                ],
            },
        )
        self.assertEqual(result["intent"], "design")
        self.assertEqual(result["run_mode"], "run")
        self.assertEqual(result["design_prompt"], original_prompt)

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

    def test_is_this_good_uses_blocked_state(self):
        result = _decide(
            "is this good?",
            {
                "has_plan": True,
                "convergence_summary": {
                    "blocked_exports": ["storm"],
                    "blocked_reasons": ["storm_graph_invalid"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("not fully ready", result["assistant_message"])

    def test_what_next_uses_review_items(self):
        result = _decide(
            "what should i do next?",
            {
                "has_plan": True,
                "issues": [
                    {"message": "Storm pipe review is still needed."},
                ],
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("review", result["assistant_message"])

    def test_what_do_you_need_from_me_answers_with_inputs(self):
        result = _decide(
            "what do you need from me?",
            {
                "strategy_mode": "assisted",
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("site type", result["assistant_message"])
        self.assertIn("rough lot size", result["assistant_message"])

    def test_supplies_question_answers_with_inputs_and_scope(self):
        result = _decide(
            "what supplies would you need for this?",
            {
                "strategy_mode": "assisted",
                "project_type": "mixed_use",
                "lot_width": "400",
                "lot_height": "250",
                "parking_count": "80",
                "roads": True,
                "grading": True,
                "drainage": True,
                "utilities": True,
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("supporting files or field information", result["assistant_message"])
        self.assertIn("roads and access", result["assistant_message"])

    def test_are_you_sure_uses_blocked_state(self):
        result = _decide(
            "are you sure?",
            {
                "has_plan": True,
                "convergence_summary": {
                    "blocked_exports": ["storm"],
                    "blocked_reasons": ["storm_graph_invalid"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("active blockers", result["assistant_message"])

    def test_short_version_summarizes_current_run_state(self):
        result = _decide(
            "give me the short version",
            {
                "has_plan": True,
                "assumptions": [
                    {"field_name": "lot_width", "assumed_value": "220", "reason": "No exact width was provided."}
                ],
                "convergence_summary": {
                    "fix_summary": {"autofix_actions": ["storm_validation_retry"]},
                    "unresolved_issue_categories": ["storm"],
                    "blocked_reasons": ["storm_graph_invalid"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("Short version", result["assistant_message"])
        self.assertIn("assumptions", result["assistant_message"])
        self.assertIn("blocked", result["assistant_message"])

    def test_options_question_returns_next_steps(self):
        result = _decide(
            "what are my options?",
            {
                "has_plan": True,
                "convergence_summary": {
                    "blocked_reasons": ["storm_graph_invalid"],
                    "unresolved_issue_categories": ["storm"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("clear the blockers first", result["assistant_message"])

    def test_negative_feedback_uses_current_weakness(self):
        result = _decide(
            "this looks wrong",
            {
                "has_plan": True,
                "convergence_summary": {
                    "unresolved_issue_categories": ["storm coordination"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("weakest part", result["assistant_message"])
        self.assertIn("storm coordination", result["assistant_message"])

    def test_follow_up_design_acknowledges_focus_target(self):
        result = _decide(
            "focus on drainage and add more parking",
            {
                "has_plan": True,
                "project_type": "commercial_pad",
            },
        )
        self.assertEqual(result["intent"], "design")
        self.assertIn("extra attention on drainage", result["assistant_message"])

    def test_follow_up_design_acknowledges_preserved_scope(self):
        result = _decide(
            "keep the building and do the same but less parking",
            {
                "has_plan": True,
                "project_type": "commercial_pad",
            },
        )
        self.assertEqual(result["intent"], "design")
        self.assertIn("keeping building intact", result["assistant_message"])

    def test_fix_request_acknowledges_revision_priority(self):
        result = _decide(
            "fix this but keep the drainage and focus on utilities",
            {
                "has_plan": True,
                "project_type": "commercial_pad",
            },
        )
        self.assertEqual(result["intent"], "fix")
        self.assertIn("focused fix pass", result["assistant_message"])
        self.assertIn("extra attention on utilities", result["assistant_message"])

    def test_rollback_style_follow_up_runs_as_design_edit(self):
        result = _decide(
            "go back to the earlier version but keep the new drainage",
            {
                "has_plan": True,
                "project_type": "commercial_pad",
            },
        )
        self.assertEqual(result["intent"], "design")
        self.assertIn("rolling the design back", result["assistant_message"])
        self.assertIn("keeping drainage intact", result["assistant_message"])

    def test_rollback_style_fix_acknowledges_earlier_direction(self):
        result = _decide(
            "fix this and go back to the original idea",
            {
                "has_plan": True,
                "project_type": "commercial_pad",
            },
        )
        self.assertEqual(result["intent"], "fix")
        self.assertIn("earlier version", result["assistant_message"])

    def test_memory_extracts_priority_style_preferences(self):
        result = _decide(
            "what are my priorities?",
            {
                "chat_thread": [
                    {"role": "user", "content": "I care more about drainage than parking."},
                    {"role": "user", "content": "Don't optimize too aggressively."},
                ],
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("drainage", result["assistant_message"])

    def test_design_acknowledges_priority_style_follow_up(self):
        result = _decide(
            "i care more about drainage than parking so add more parking only if it doesn't hurt drainage",
            {
                "has_plan": True,
                "project_type": "commercial_pad",
            },
        )
        self.assertEqual(result["intent"], "design")
        self.assertIn("extra attention on drainage", result["assistant_message"])

    def test_constraints_question_uses_memory_constraints(self):
        result = _decide(
            "what constraints are you following?",
            {
                "chat_thread": [
                    {"role": "user", "content": "Don't optimize too aggressively."},
                ],
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("constraints", result["assistant_message"])
        self.assertIn("optimize too aggressively", result["assistant_message"])

    def test_compare_question_uses_fix_and_block_state(self):
        result = _decide(
            "is this better than before?",
            {
                "has_plan": True,
                "convergence_summary": {
                    "fix_summary": {"autofix_actions": ["storm_validation_retry"]},
                    "rerun_summary": {"total_reruns": 2},
                    "blocked_reasons": ["storm_graph_invalid"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("Compared with the earlier state", result["assistant_message"])
        self.assertIn("storm_validation_retry", result["assistant_message"])

    def test_tradeoffs_question_uses_preferences_and_review_pressure(self):
        result = _decide(
            "what are the tradeoffs?",
            {
                "chat_thread": [
                    {"role": "user", "content": "I care more about drainage than parking."},
                ],
                "convergence_summary": {
                    "unresolved_issue_categories": ["storm"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("tradeoffs", result["assistant_message"].lower())
        self.assertIn("drainage", result["assistant_message"])

    def test_risks_question_uses_blocked_reasons(self):
        result = _decide(
            "what are the risks?",
            {
                "has_plan": True,
                "convergence_summary": {
                    "blocked_reasons": ["storm_graph_invalid"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("risks", result["assistant_message"])
        self.assertIn("storm_graph_invalid", result["assistant_message"])

    def test_dont_forget_reply_uses_memory(self):
        result = _decide(
            "don't forget what I said about drainage",
            {
                "chat_thread": [
                    {"role": "user", "content": "I care more about drainage than parking."},
                ],
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("keeping these earlier instructions in mind", result["assistant_message"])
        self.assertIn("drainage", result["assistant_message"])

    def test_which_version_is_better_uses_priorities(self):
        result = _decide(
            "which version is better?",
            {
                "has_plan": True,
                "chat_thread": [
                    {"role": "user", "content": "I care more about drainage than parking."},
                ],
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("Based on your priorities", result["assistant_message"])

    def test_why_is_that_better_uses_review_pressure(self):
        result = _decide(
            "why is that better?",
            {
                "has_plan": True,
                "convergence_summary": {
                    "unresolved_issue_categories": ["storm coordination"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("fewer unresolved review items", result["assistant_message"])

    def test_uncertainty_question_uses_blockers_and_assumptions(self):
        result = _decide(
            "what are you unsure about?",
            {
                "has_plan": True,
                "engineering_trust_score": 72.0,
                "assumptions": [
                    {"field_name": "lot_width", "assumed_value": "220", "reason": "No exact width was provided."}
                ],
                "convergence_summary": {
                    "blocked_reasons": ["storm_graph_invalid"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("storm_graph_invalid", result["assistant_message"])
        self.assertIn("lot width", result["assistant_message"])
        self.assertIn("72.0", result["assistant_message"])

    def test_more_confident_question_uses_review_and_assumptions(self):
        result = _decide(
            "what would make you more confident?",
            {
                "has_plan": True,
                "assumptions": [
                    {"field_name": "parking_count", "assumed_value": "32", "reason": "Program was not explicit."}
                ],
                "convergence_summary": {
                    "unresolved_issue_categories": ["storm coordination"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("storm coordination", result["assistant_message"])
        self.assertIn("parking count", result["assistant_message"])

    def test_recommendation_question_uses_blocked_state(self):
        result = _decide(
            "what would you recommend here?",
            {
                "has_plan": True,
                "convergence_summary": {
                    "blocked_reasons": ["storm_graph_invalid"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("address the blockers first", result["assistant_message"])

    def test_focus_question_uses_priorities_when_no_blockers(self):
        result = _decide(
            "what should i focus on?",
            {
                "has_plan": True,
                "chat_thread": [
                    {"role": "user", "content": "I care more about drainage than parking."},
                ],
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("Given your priorities", result["assistant_message"])
        self.assertIn("drainage", result["assistant_message"])

    def test_simpler_reply_uses_blocked_state(self):
        result = _decide(
            "that doesn't help",
            {
                "has_plan": True,
                "convergence_summary": {
                    "blocked_reasons": ["storm_graph_invalid"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("In simple terms", result["assistant_message"])
        self.assertIn("storm_graph_invalid", result["assistant_message"])

    def test_disagreement_reply_points_to_weakest_area(self):
        result = _decide(
            "you're wrong",
            {
                "has_plan": True,
                "convergence_summary": {
                    "unresolved_issue_categories": ["storm coordination"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("weakest part", result["assistant_message"])
        self.assertIn("storm coordination", result["assistant_message"])


if __name__ == "__main__":
    unittest.main()
