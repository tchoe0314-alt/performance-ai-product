import unittest
from unittest.mock import patch

from planner_orchestrator import (
    PlannerOrchestratorRequest,
    _merge_manual_fields,
    _parse_from_prompt,
    _should_use_multi_option,
)


class PlannerOrchestratorRoutingTests(unittest.TestCase):
    def test_large_fully_engineered_prompt_avoids_multi_option_in_assisted_mode(self):
        prompt = (
            "Design a fully engineered civil site plan for a 22-acre mixed-use development on irregular terrain.\n"
            "Include storm drainage, sanitary sewer, water system, ADA paths, grading, cul-de-sacs, and detention basin.\n"
            "- building program\n"
            "- roadway loop\n"
            "- emergency access\n"
            "- parking sizing\n"
            "- grading plan\n"
            "- spot elevations\n"
            "- contours\n"
            "- storm drainage\n"
            "- sanitary sewer\n"
            "- water distribution\n"
            "- optimization goals\n"
            "- review summary\n"
        )
        req = PlannerOrchestratorRequest(
            input_mode="assisted",
            strict_mode=False,
            full_design_mode=False,
            prompt_text=prompt,
        )
        parsed_payload = {
            "project_type": "mixed_use",
            "site_plan": {"parking_count": 120},
            "meta": {"input_mode": "assisted"},
        }
        self.assertFalse(_should_use_multi_option(parsed_payload, req))

    def test_small_commercial_prompt_can_still_use_multi_option(self):
        req = PlannerOrchestratorRequest(
            input_mode="assisted",
            strict_mode=False,
            full_design_mode=False,
            prompt_text="Create a commercial pad site on a 140 by 110 foot lot with front parking and drainage.",
        )
        parsed_payload = {
            "project_type": "commercial_pad",
            "mode": "site_plan",
            "site_plan": {"parking_count": 24},
            "meta": {"input_mode": "assisted"},
        }
        self.assertTrue(_should_use_multi_option(parsed_payload, req))

    def test_structured_two_acre_prompt_uses_fast_parse_without_ai_call(self):
        req = PlannerOrchestratorRequest(
            input_mode="assisted",
            prompt_text=(
                "Design a civil site plan for a 2-acre rectangular lot with gentle slope falling from the northwest corner to the southeast corner.\n"
                "Include one building, 120 ft by 60 ft, parking for 40 cars, one 12 ft wide driveway, grading, storm drainage, sanitary sewer, and water service."
            ),
        )
        with patch("planner_orchestrator.command_mode", side_effect=AssertionError("AI parser should not be called")):
            parsed = _parse_from_prompt(req)
        self.assertTrue(parsed["meta"]["fast_prompt_parse"])
        self.assertEqual(parsed["project_type"], "generic_site")
        self.assertEqual(int(parsed["site_plan"]["parking_count"]), 40)
        self.assertGreater(float(parsed["lot"]["w"]), 200.0)
        self.assertGreater(float(parsed["lot"]["h"]), 200.0)

    def test_structured_mixed_use_prompt_uses_fast_parse_without_ai_call(self):
        req = PlannerOrchestratorRequest(
            input_mode="assisted",
            prompt_text=(
                "Design a fully engineered civil site plan for a 22-acre mixed-use development on irregular terrain.\n"
                "Include 3 multifamily buildings, each 120 ft x 60 ft, and 1 commercial retail pad, 80 ft x 50 ft.\n"
                "Residential parking at 1.75 spaces per unit assuming 24 units per building. Commercial parking at 1 space per 250 sq ft.\n"
                "Generate grading, storm drainage, sanitary sewer, water systems, and detention basin."
            ),
        )
        with patch("planner_orchestrator.command_mode", side_effect=AssertionError("AI parser should not be called")):
            parsed = _parse_from_prompt(req)
        self.assertTrue(parsed["meta"]["fast_prompt_parse"])
        self.assertEqual(parsed["project_type"], "mixed_use")
        self.assertGreaterEqual(int(parsed["site_plan"]["parking_count"]), 140)
        self.assertGreaterEqual(len(parsed.get("buildings") or []), 4)

    def test_zero_placeholder_manual_fields_do_not_override_fast_parsed_site_geometry(self):
        req = PlannerOrchestratorRequest(
            input_mode="assisted",
            prompt_text=(
                "Design a fully engineered civil site plan for a 22-acre mixed-use development on irregular terrain.\n"
                "Include 3 multifamily buildings, each 120 ft x 60 ft, and 1 commercial retail pad, 80 ft x 50 ft.\n"
                "Residential parking at 1.75 spaces per unit assuming 24 units per building. Commercial parking at 1 space per 250 sq ft.\n"
                "Generate grading, storm drainage, sanitary sewer, water systems, and detention basin."
            ),
        )
        with patch("planner_orchestrator.command_mode", side_effect=AssertionError("AI parser should not be called")):
            parsed = _parse_from_prompt(req)
        merged = _merge_manual_fields(
            parsed,
            {
                "lot": {"x": 0, "y": 0, "w": 0, "h": 0},
                "building_width": 0,
                "building_depth": 0,
                "setback": 0,
                "site_plan": {"parking_count": 0},
            },
            allow_fill_for_blanks=True,
        )
        self.assertGreater(float(merged["lot"]["w"]), 900.0)
        self.assertGreater(float(merged["lot"]["h"]), 900.0)
        self.assertGreaterEqual(int(merged["site_plan"]["parking_count"]), 140)

    def test_positive_manual_site_geometry_still_overrides_when_provided(self):
        req = PlannerOrchestratorRequest(
            input_mode="assisted",
            prompt_text=(
                "Design a fully engineered civil site plan for a 22-acre mixed-use development on irregular terrain.\n"
                "Include 3 multifamily buildings, each 120 ft x 60 ft, and 1 commercial retail pad, 80 ft x 50 ft.\n"
                "Generate grading, storm drainage, sanitary sewer, water systems, and detention basin."
            ),
        )
        with patch("planner_orchestrator.command_mode", side_effect=AssertionError("AI parser should not be called")):
            parsed = _parse_from_prompt(req)
        merged = _merge_manual_fields(
            parsed,
            {
                "lot": {"x": 0, "y": 0, "w": 1200, "h": 900},
                "site_plan": {"parking_count": 180},
            },
            allow_fill_for_blanks=True,
        )
        self.assertEqual(float(merged["lot"]["w"]), 1200.0)
        self.assertEqual(float(merged["lot"]["h"]), 900.0)
        self.assertEqual(int(merged["site_plan"]["parking_count"]), 180)


if __name__ == "__main__":
    unittest.main()
