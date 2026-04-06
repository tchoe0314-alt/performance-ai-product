import unittest

from planner_orchestrator import PlannerOrchestratorRequest, _should_use_multi_option


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


if __name__ == "__main__":
    unittest.main()
