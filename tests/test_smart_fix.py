import unittest

from backend.planning.smart_fix import (
    SMART_FIX_VERSION,
    build_smart_fix_recommendations,
    classify_blocker,
)


class SmartFixRecommendationsTest(unittest.TestCase):
    def test_contract_explains_supported_and_manual_blockers(self) -> None:
        final_plan = {
            "meta": {
                "release_review": {
                    "blocked_reasons": [
                        "drainage_outfall_missing",
                        "survey_control_missing",
                        "standards_source_missing",
                        "cost_book_missing",
                        "stale_outputs_detected",
                    ],
                    "blocked_exports": ["export_audit_blocked"],
                }
            }
        }

        result = build_smart_fix_recommendations(final_plan)
        by_code = {item["blocker_code"]: item for item in result["recommendations"]}

        self.assertEqual(result["version"], SMART_FIX_VERSION)
        self.assertIn("drainage_outfall_missing", by_code)
        self.assertTrue(by_code["drainage_outfall_missing"]["can_civora_fix"])
        self.assertEqual(by_code["drainage_outfall_missing"]["supported_action_id"], "add_drainage_basin")
        self.assertFalse(by_code["survey_control_missing"]["can_civora_fix"])
        self.assertIn("survey/control file", by_code["survey_control_missing"]["missing_user_input_or_source"])
        self.assertFalse(by_code["standards_source_missing"]["can_civora_fix"])
        self.assertFalse(by_code["cost_book_missing"]["can_civora_fix"])
        self.assertGreaterEqual(result["auto_fix_action_count"], 2)
        self.assertGreaterEqual(result["manual_action_count"], 3)
        for recommendation in result["recommendations"]:
            for key in (
                "what_is_wrong",
                "why_it_matters",
                "can_civora_fix",
                "one_action_needed_next",
                "what_happens_after_fix",
            ):
                self.assertIn(key, recommendation)

    def test_classification_covers_requested_blocker_families(self) -> None:
        cases = {
            "site_boundary_missing": "setup_site_boundary",
            "geocode_failed": "address_geocode",
            "online_candidate_pending": "online_candidates",
            "survey_control_missing": "survey_control",
            "standards_source_missing": "standards",
            "grading_slope_blocked": "grading",
            "drainage_outfall_missing": "drainage",
            "storm_graph_invalid": "storm",
            "utility_connection_missing": "utilities",
            "roadway_access_blocked": "roadway",
            "cost_book_missing": "cost_book",
            "export_audit_blocked": "exports",
            "stale_outputs_detected": "stale_outputs",
            "engineer_review_package_missing": "engineer_review_package",
        }
        for blocker, category in cases.items():
            with self.subTest(blocker=blocker):
                self.assertEqual(classify_blocker(blocker), category)


if __name__ == "__main__":
    unittest.main()
