import unittest
from typing import Optional
from unittest.mock import patch

from parsers.chat_action_registry import build_action_registry
from parsers.chat_intent_parser import decide_chat_message


def _decide(message: str, context: Optional[dict] = None):
    return decide_chat_message({"message": message, "context": context or {}})


class ChatIntentParserTest(unittest.TestCase):
    def test_greeting_stays_conversation(self):
        result = _decide("how r u")
        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(result["run_mode"], "none")
        self.assertFalse(result["needs_clarification"])
        self.assertEqual(result["response_metadata"]["completed_actions"], ["answered"])
        self.assertFalse(result["response_metadata"]["can_execute_now"])

    def test_casual_greeting_has_no_workflow_handoff(self):
        result = _decide("hi how r u")
        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(result["run_mode"], "none")
        self.assertEqual(result["design_prompt"], "")
        self.assertEqual(result["action_taken"], "answered")
        self.assertIn("help", result["assistant_message"].lower())

    def test_settings_only_message_does_not_run(self):
        result = _decide("turn off grading and turn off assisted")
        self.assertEqual(result["intent"], "settings")
        self.assertEqual(result["run_mode"], "none")
        self.assertEqual(result["control_overrides"]["strategyMode"], "user")
        self.assertEqual(result["control_overrides"]["grading"], False)

    def test_assisted_off_ambiguous_request_asks_for_more(self):
        result = _decide(
            "make me a site",
            {
                "strategy_mode": "user",
                "roads": True,
                "grading": True,
                "drainage": True,
                "utilities": True,
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertTrue(result["needs_clarification"])
        self.assertEqual(result["run_mode"], "none")
        self.assertIn("site type or land use", result["assistant_message"])
        self.assertIn("rough lot size", result["assistant_message"])

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

    def test_site_area_command_routes_as_site_update(self):
        result = _decide("make the site 14 acres", {"has_plan": True})
        self.assertEqual(result["intent"], "design")
        self.assertEqual(result["run_mode"], "run")
        self.assertIn("14 acres", result["design_prompt"])
        self.assertEqual(result["response_metadata"]["intent"], "site_update")
        self.assertEqual(result["action_taken"], "prepared_canonical_edit")
        self.assertIn("site", result["affected_systems"])
        self.assertEqual(result["response_metadata"]["command_payload"]["site_area_acres"], 14.0)

    def test_site_setup_dimensions_and_address_does_not_ask_for_design_program(self):
        result = _decide("make the site size 1000x1000 and the address is 20525 Margo St gretna ne")
        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(result["run_mode"], "none")
        self.assertFalse(result["needs_clarification"])
        self.assertEqual(result["response_metadata"]["intent"], "site_setup")
        self.assertEqual(result["action_taken"], "prepared_site_setup_update")
        self.assertEqual(result["control_overrides"]["lotWidth"], "1000")
        self.assertEqual(result["control_overrides"]["lotHeight"], "1000")
        self.assertEqual(result["response_metadata"]["command_payload"]["address"], "20525 Margo St, Gretna, NE")
        self.assertNotIn("land use", result["assistant_message"])
        self.assertNotIn("building", result["assistant_message"].lower())
        self.assertIn("Do you want to lock this 1000 ft x 1000 ft site boundary", result["assistant_message"])

    def test_site_setup_dimensions_only_does_not_trigger_generation(self):
        result = _decide("set site to 500 by 800")
        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(result["run_mode"], "none")
        self.assertEqual(result["response_metadata"]["intent"], "site_setup")
        self.assertEqual(result["control_overrides"]["lotWidth"], "500")
        self.assertEqual(result["control_overrides"]["lotHeight"], "800")
        self.assertNotIn("land use", result["assistant_message"])

    def test_address_only_is_location_evidence_not_boundary(self):
        result = _decide("address is 123 Main St")
        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(result["run_mode"], "none")
        self.assertEqual(result["response_metadata"]["intent"], "site_setup")
        self.assertEqual(result["response_metadata"]["command_payload"]["address"], "123 Main St")
        self.assertIn("location evidence only", result["assistant_message"])
        self.assertIn("not a trusted site boundary", result["assistant_message"])

    def test_blank_acreage_site_setup_does_not_run_planner(self):
        result = _decide("make a 10 acre blank site")
        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(result["run_mode"], "none")
        self.assertEqual(result["response_metadata"]["intent"], "site_setup")
        self.assertEqual(result["response_metadata"]["command_payload"]["site_area_acres"], 10.0)
        self.assertEqual(result["control_overrides"]["lotWidth"], "660")
        self.assertEqual(result["control_overrides"]["lotHeight"], "660")

    def test_site_setup_geocode_failure_blocks_with_location_blocker(self):
        result = _decide("address is 123 Main St", {"address_status": "geocode_failed"})
        self.assertEqual(result["action_taken"], "blocked_site_setup_geocode_failed")
        self.assertEqual(result["response_metadata"]["intent"], "site_setup")
        self.assertFalse(result["response_metadata"]["state_changed"])
        self.assertIn("Address/location evidence is blocked", result["assistant_message"])

    def test_full_design_generation_still_asks_for_program_when_needed(self):
        result = _decide("design a site with drainage")
        self.assertEqual(result["intent"], "conversation")
        self.assertTrue(result["needs_clarification"])
        self.assertIn("land use", result["assistant_message"])
        self.assertIn("building or parking program", result["assistant_message"])

    def test_building_command_asks_for_site_when_no_plan(self):
        result = _decide("add a 100 by 60 building")
        self.assertEqual(result["intent"], "conversation")
        self.assertTrue(result["needs_clarification"])
        self.assertIn("site size", result["assistant_message"])
        self.assertEqual(result["response_metadata"]["intent"], "object_or_layout_command")
        self.assertIn("site size or boundary", result["required_missing_inputs"])
        self.assertEqual(result["action_taken"], "asked_clarifying_question")

    def test_building_command_runs_against_existing_plan(self):
        result = _decide("add a 100 by 60 building", {"strategy_mode": "assisted", "has_plan": True, "lot_width": "500", "lot_height": "400"})
        self.assertEqual(result["intent"], "design")
        self.assertEqual(result["run_mode"], "run")
        self.assertEqual(result["response_metadata"]["intent"], "object_or_layout_command")
        self.assertIn("layout", result["affected_systems"])
        self.assertEqual(result["action_taken"], "prepared_canonical_edit")
        self.assertIn("draft", " ".join(result["assumptions"]).lower())

    def test_strict_object_creation_blocks_missing_location(self):
        result = _decide("add a 100 by 60 building", {"strategy_mode": "user", "has_plan": True, "lot_width": "500", "lot_height": "400"})
        self.assertEqual(result["intent"], "conversation")
        self.assertTrue(result["needs_clarification"])
        self.assertIn("location", result["assistant_message"])
        self.assertIn("object location", result["required_missing_inputs"])
        self.assertEqual(result["action_taken"], "asked_clarifying_question")

    def test_detention_basin_low_corner_runs_drainage_layout_command(self):
        result = _decide(
            "put detention basin in the low corner",
            {"has_plan": True, "lot_width": "500", "lot_height": "400"},
        )
        self.assertEqual(result["intent"], "design")
        self.assertEqual(result["run_mode"], "run")
        self.assertEqual(result["response_metadata"]["intent"], "object_or_layout_command")
        self.assertIn("drainage", result["affected_systems"])

    def test_action_registry_exposes_supported_safe_actions(self):
        registry = build_action_registry()
        action_ids = {action["action_id"] for action in registry}
        self.assertIn("open_ui_panel", action_ids)
        self.assertIn("set_preview_mode", action_ids)
        self.assertIn("request_site_lock_state", action_ids)
        self.assertIn("request_detect_grading", action_ids)
        self.assertIn("request_review_export_package", action_ids)
        self.assertIn("revise_drainage", action_ids)
        self.assertIn("classify_geometry_as_parking", action_ids)
        self.assertIn("update_road_geometry", action_ids)
        for action in registry:
            self.assertIn("required_inputs", action)
            self.assertIn("supported_object_types", action)
            self.assertIn("side_effects", action)
            self.assertIn("blocked_if", action)
            self.assertIn("engineer_review_required", action)

    def test_varied_natural_language_maps_without_external_ai(self):
        cases = [
            ("why is this broken", {"has_plan": True, "convergence_summary": {"blocked_reasons": ["storm_graph_invalid"]}}, "explain_blockers", "explain"),
            ("make this work", {"has_plan": True}, "fix_current_design", "fix"),
            ("why can’t I export", {"has_plan": True, "convergence_summary": {"blocked_exports": ["export"], "blocked_reasons": ["accepted_standards_missing"]}}, "explain_blockers", "explain"),
            ("put that pond in the low spot", {"has_plan": True, "lot_width": "500", "lot_height": "400"}, "place_basin", "design"),
            ("turn this polygon into parking", {"has_plan": True, "selected_geometry_ids": ["geom-1"]}, "classify_geometry_as_parking", "design"),
            ("move the road away from the building", {"has_plan": True, "lot_width": "500", "lot_height": "400"}, "update_road_geometry", "design"),
            ("don’t assume anything", {}, "set_no_assumptions_mode", "settings"),
        ]
        with patch("parsers.chat_intent_parser._load_chat_client", side_effect=RuntimeError("AI disabled")):
            for message, context, selected_action, expected_intent in cases:
                with self.subTest(message=message):
                    result = _decide(message, context)
                    planning = result["response_metadata"]["action_planning"]
                    self.assertEqual(planning["selected_action_id"], selected_action)
                    self.assertGreaterEqual(planning["confidence"], 0.76)
                    self.assertEqual(result["intent"], expected_intent)

    def test_natural_language_drainage_asks_targeted_question_when_missing_outfall(self):
        with patch("parsers.chat_intent_parser._load_chat_client", side_effect=RuntimeError("AI disabled")):
            result = _decide("fix the drainage", {"has_plan": True})
        planning = result["response_metadata"]["action_planning"]
        self.assertEqual(planning["selected_action_id"], "revise_drainage")
        self.assertIn("detention basin or outfall target", result["required_missing_inputs"])
        self.assertEqual(
            result["assistant_message"],
            "I can’t run drainage yet because I need a basin or outfall target. Select/draw one, or say ‘add a draft basin in the low corner’.",
        )
        self.assertEqual(result["response_metadata"]["exact_missing_inputs"], ["a basin or outfall target"])
        self.assertIn("add a draft basin in the low corner", result["response_metadata"]["suggested_user_replies"])

    def test_missing_info_response_metadata_is_specific(self):
        result = _decide("generate drainage", {"has_plan": True, "lot_width": "500", "lot_height": "400"})
        metadata = result["response_metadata"]
        self.assertEqual(metadata["understood_goal"], "generate drainage")
        self.assertEqual(metadata["blocked_actions"], ["asked_clarifying_question"])
        self.assertEqual(metadata["completed_actions"], [])
        self.assertEqual(metadata["exact_missing_inputs"], ["a basin or outfall target"])
        self.assertFalse(metadata["can_execute_now"])
        for generic in ["manual validation failed", "missing requirements", "missing inputs", "cannot proceed"]:
            self.assertNotIn(generic, result["assistant_message"].lower())

    def test_export_blocked_explanation_is_specific(self):
        result = _decide(
            "what do I need before export",
            {
                "has_plan": True,
                "current_export_audit": {
                    "export_blocked": True,
                    "blocked_reasons": ["canonical_id_traceability_missing"],
                },
            },
        )
        self.assertEqual(result["response_metadata"]["intent"], "export_readiness")
        self.assertIn("canonical_id_traceability_missing", result["assistant_message"])
        self.assertIn("canonical_id_traceability_missing", result["response_metadata"]["blockers"])

    def test_unsupported_road_edit_says_understood_and_alternative(self):
        result = _decide("delete the road network")
        self.assertEqual(result["response_metadata"]["intent"], "unsupported_or_not_understood")
        self.assertIn("I understood this as", result["assistant_message"])
        self.assertIn("supported", result["assistant_message"])
        self.assertFalse(result["response_metadata"]["can_execute_now"])

    def test_what_should_i_do_next_uses_top_blocker(self):
        result = _decide(
            "what should I do next?",
            {
                "has_plan": True,
                "convergence_summary": {"blocked_reasons": ["drainage_outfall_missing"]},
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("drainage_outfall_missing", result["assistant_message"])
        self.assertIn("Clear drainage_outfall_missing", result["response_metadata"]["next_best_action"])

    def test_can_you_fix_it_explains_supported_or_blocked(self):
        result = _decide(
            "can you fix it?",
            {
                "has_plan": True,
                "convergence_summary": {"blocked_reasons": ["storm_graph_invalid"]},
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("storm_graph_invalid", result["assistant_message"])
        self.assertIn("supported chat actions", result["assistant_message"])

    def test_responsibility_guard_has_no_positive_approval_language(self):
        result = _decide("stamp it")
        self.assertEqual(result["action_taken"], "blocked_responsibility_request")
        self.assertIn("cannot approve, stamp, seal", result["assistant_message"])
        self.assertNotIn("construction-ready", result["assistant_message"])

    def test_safety_gate_blocks_fabricated_evidence(self):
        result = _decide("make up survey control and fake calculations")
        self.assertEqual(result["action_taken"], "blocked_safety_gate")
        self.assertIn("cannot fabricate", result["assistant_message"])

    def test_random_unsupported_request_has_low_confidence_plan(self):
        result = _decide("purple banana orbit sandwich")
        planning = result["response_metadata"]["action_planning"]
        self.assertEqual(result["action_taken"], "unsupported_or_not_understood")
        self.assertTrue(planning["low_confidence"])

    def test_chat_can_open_common_ui_panels(self):
        cases = [
            ("open setup", "site_existing", "setup"),
            ("open canvas", "model", "canvas"),
            ("open review", "reports", "review"),
            ("open deliver", "deliverables", "deliver"),
            ("open data", "data", "data"),
        ]
        for message, panel, mode in cases:
            with self.subTest(message=message):
                result = _decide(message)
                metadata = result["response_metadata"]
                self.assertEqual(result["intent"], "conversation")
                self.assertEqual(result["run_mode"], "none")
                self.assertEqual(result["action_taken"], "routed_ui_action")
                self.assertEqual(metadata["intent"], "ui_navigation")
                self.assertEqual(metadata["ui_navigation_target"], panel)
                self.assertEqual(metadata["requested_ui_mode"], mode)
                self.assertFalse(metadata["state_changed"])

    def test_chat_can_request_canvas_mode_and_quality(self):
        result = _decide("switch the canvas to 3D high quality", {"has_preview": True})
        metadata = result["response_metadata"]
        self.assertEqual(result["action_taken"], "routed_ui_action")
        self.assertEqual(metadata["ui_navigation_target"], "model")
        self.assertEqual(metadata["requested_ui_mode"], "canvas")
        self.assertEqual(metadata["requested_preview_mode"], "3d")
        self.assertEqual(metadata["requested_preview_quality"], "high")

    def test_chat_blocks_3d_without_preview(self):
        result = _decide("switch to 3D view", {"has_preview": False})
        self.assertEqual(result["action_taken"], "blocked_ui_action")
        self.assertIn("3D preview needs", result["assistant_message"])

    def test_chat_can_request_lock_and_unlock_site(self):
        lock_result = _decide("lock site boundary", {"lot_width": "500", "lot_height": "800"})
        lock_meta = lock_result["response_metadata"]
        self.assertEqual(lock_result["action_taken"], "routed_ui_action")
        self.assertEqual(lock_meta["ui_navigation_target"], "site_existing")
        self.assertEqual(lock_meta["requested_site_lock_state"], "lock")
        unlock_result = _decide("unlock site")
        unlock_meta = unlock_result["response_metadata"]
        self.assertEqual(unlock_result["action_taken"], "routed_ui_action")
        self.assertEqual(unlock_meta["requested_site_lock_state"], "unlock")

    def test_chat_blocks_lock_site_without_boundary(self):
        result = _decide("lock site boundary")
        self.assertEqual(result["action_taken"], "blocked_ui_action")
        self.assertIn("needs confirmed site dimensions", result["assistant_message"])

    def test_detect_grading_blocks_without_source_evidence(self):
        result = _decide("detect grading")
        self.assertEqual(result["action_taken"], "blocked_ui_action")
        self.assertIn("Detect grading needs terrain", result["assistant_message"])

    def test_detect_grading_routes_when_source_evidence_exists(self):
        result = _decide("detect grading", {"current_project": {"project_input": {"meta": {"site_inputs": {"geocode": {"lat": 41.1, "lng": -96.1}}}}}})
        metadata = result["response_metadata"]
        self.assertEqual(result["action_taken"], "routed_ui_action")
        self.assertEqual(metadata["ui_navigation_target"], "data")
        self.assertEqual(metadata["requested_ui_mode"], "data")

    def test_export_review_package_blocks_without_plan(self):
        result = _decide("export review package")
        self.assertEqual(result["action_taken"], "blocked_ui_action")
        self.assertIn("needs a planner result", result["assistant_message"])

    def test_export_review_package_routes_when_available(self):
        result = _decide("export review package", {"has_plan": True})
        metadata = result["response_metadata"]
        self.assertEqual(result["action_taken"], "routed_ui_action")
        self.assertEqual(metadata["ui_navigation_target"], "deliverables")
        self.assertEqual(metadata["requested_ui_mode"], "deliver")
        self.assertIn("engineer-review package", result["assistant_message"])

    def test_unsupported_ui_action_blocks_clearly(self):
        result = _decide("undo the last canvas action")
        self.assertEqual(result["action_taken"], "blocked_ui_action")
        self.assertIn("not safely chat-routable", result["assistant_message"])

    def test_generate_drainage_asks_for_outfall_without_target(self):
        result = _decide("generate drainage", {"has_plan": True, "lot_width": "500", "lot_height": "400"})
        self.assertEqual(result["intent"], "conversation")
        self.assertTrue(result["needs_clarification"])
        self.assertIn("detention basin or outfall", result["assistant_message"])
        self.assertEqual(result["response_metadata"]["intent"], "drainage_command")
        self.assertIn("detention basin or outfall target", result["required_missing_inputs"])

    def test_generate_drainage_runs_when_basin_exists_in_canonical_context(self):
        result = _decide(
            "generate drainage",
            {
                "has_plan": True,
                "lot_width": "500",
                "lot_height": "400",
                "current_project": {
                    "latest_result": {
                        "final_plan": {
                            "meta": {
                                "drainage_canonical": {
                                    "basins": [{"id": "BASIN-1", "label": "Detention basin"}]
                                }
                            }
                        }
                    }
                },
            },
        )
        self.assertEqual(result["intent"], "design")
        self.assertEqual(result["run_mode"], "run")
        self.assertEqual(result["control_overrides"]["drainage"], True)
        self.assertEqual(result["response_metadata"]["intent"], "drainage_command")

    def test_why_is_storm_blocked_uses_specific_blocker_state(self):
        result = _decide(
            "why is storm blocked",
            {
                "has_plan": True,
                "convergence_summary": {
                    "blocked_exports": ["storm"],
                    "blocked_reasons": ["storm_graph_invalid"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("storm_graph_invalid", result["assistant_message"])
        self.assertEqual(result["response_metadata"]["intent"], "blocker_explanation")
        self.assertEqual(result["action_taken"], "answered_from_project_context")

    def test_change_the_road_asks_specific_question(self):
        result = _decide("change the road", {"has_plan": True, "lot_width": "500", "lot_height": "400"})
        self.assertEqual(result["intent"], "conversation")
        self.assertTrue(result["needs_clarification"])
        self.assertIn("move it, widen it, reroute it", result["assistant_message"])
        self.assertIn("what road change you want", result["required_missing_inputs"])

    def test_make_parking_fit_buildings_routes_layout_run(self):
        result = _decide(
            "make parking fit the buildings",
            {"has_plan": True, "lot_width": "500", "lot_height": "400", "building_count": "3"},
        )
        self.assertEqual(result["intent"], "design")
        self.assertEqual(result["run_mode"], "run")
        self.assertEqual(result["response_metadata"]["intent"], "object_or_layout_command")
        self.assertIn("layout", result["affected_systems"])

    def test_before_export_question_returns_export_metadata(self):
        result = _decide(
            "what do I need before export",
            {
                "has_plan": True,
                "convergence_summary": {"blocked_reasons": ["storm_graph_invalid"]},
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("Before export", result["assistant_message"])
        self.assertEqual(result["response_metadata"]["intent"], "export_readiness")
        self.assertIn("export", result["affected_systems"])

    def test_before_export_question_reads_export_audit_blockers(self):
        result = _decide(
            "what do I need before export",
            {
                "has_plan": True,
                "current_export_audit": {
                    "export_blocked": True,
                    "blocked_reasons": ["canonical_id_traceability_missing"],
                },
            },
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertIn("canonical_id_traceability_missing", result["assistant_message"])
        self.assertEqual(result["response_metadata"]["intent"], "export_readiness")

    def test_use_assisted_mode_is_mode_command(self):
        result = _decide("use assisted mode")
        self.assertEqual(result["intent"], "settings")
        self.assertEqual(result["control_overrides"]["strategyMode"], "assisted")
        self.assertEqual(result["response_metadata"]["intent"], "mode_command")

    def test_dont_assume_anything_switches_to_user_mode(self):
        result = _decide("don't assume anything")
        self.assertEqual(result["intent"], "settings")
        self.assertEqual(result["control_overrides"]["strategyMode"], "user")
        self.assertEqual(result["response_metadata"]["intent"], "mode_command")


if __name__ == "__main__":
    unittest.main()
