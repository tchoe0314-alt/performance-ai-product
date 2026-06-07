import unittest

from backend.planning.setup_wizard import build_setup_wizard_state


class SetupWizardStateTest(unittest.TestCase):
    def test_empty_project_starts_with_address_and_boundary_blockers(self):
        state = build_setup_wizard_state(project_input={}, latest_result={})

        self.assertEqual(state["schema_version"], "setup_wizard_state_v1")
        self.assertEqual(state["current_step_id"], "address_location")
        self.assertEqual(state["steps"][0]["status"], "not_started")
        self.assertEqual(state["steps"][1]["status"], "blocked")
        self.assertIn("Enter an address", state["next_action"])
        self.assertEqual(len(state["steps"]), 8)

    def test_online_candidates_and_gates_remain_review_required_or_blocked(self):
        state = build_setup_wizard_state(
            project_input={
                "manual_fields": {
                    "lot": {"w": 500, "h": 400, "boundary_status": "locked"},
                    "site_plan": {"parking_count": 20},
                    "site_objects": [{"id": "site"}, {"id": "building-1"}],
                },
                "meta": {
                    "site_inputs": {
                        "address": "123 Main St",
                        "survey_points": [{"x": 0, "y": 0, "z": 100}],
                    }
                },
            },
            latest_result={
                "final_plan": {
                    "actions": [{"layer": "SITE"}],
                    "meta": {
                        "location_context": {"address": "123 Main St"},
                        "map_feature_detection_report_v1": {
                            "candidate_count": 1,
                            "feature_candidates": [
                                {"candidate_id": "c1", "acceptance_status": "pending"}
                            ],
                        },
                    },
                }
            },
            context={
                "site_locked": True,
                "placed_object_count": 2,
                "parking_count": 20,
                "system_statuses": {"grading": "fresh"},
            },
        )

        by_id = {step["id"]: step for step in state["steps"]}
        self.assertEqual(by_id["online_sources_candidates"]["status"], "needs_review")
        self.assertTrue(by_id["online_sources_candidates"]["review_required"])
        self.assertEqual(by_id["survey_terrain_control"]["status"], "needs_review")
        self.assertEqual(by_id["standards"]["status"], "blocked")
        self.assertIn("Standards", by_id["standards"]["label"])
        self.assertIn("standards", by_id["standards"]["next_action"].lower())


if __name__ == "__main__":
    unittest.main()
