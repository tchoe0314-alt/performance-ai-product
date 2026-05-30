import unittest

from backend.planning.common import blocker_explanation, blocker_explanations


class BlockerExplanationsTest(unittest.TestCase):
    def test_static_blocker_explanation_has_required_truth_fields(self):
        detail = blocker_explanation("construction_package_blocked")

        self.assertEqual(detail["code"], "construction_package_blocked")
        self.assertEqual(detail["what_failed"], "The construction package is not allowed for release.")
        self.assertTrue(detail["why_it_matters"])
        self.assertEqual(detail["missing_data"], ["release_allowed construction package status"])
        self.assertTrue(detail["next_action"])
        self.assertTrue(detail["engineer_review_required"])

    def test_dynamic_deliverable_manual_and_unknown_blockers_are_explained(self):
        details = blocker_explanations(
            [
                "failed_deliverable_report",
                "missing_deliverable_profile_sheet",
                "manual_validation_manual_storm_hydraulic_invalid",
                "county_standard_pending",
                "failed_deliverable_report",
            ]
        )

        self.assertEqual(
            [detail["code"] for detail in details],
            [
                "failed_deliverable_report",
                "missing_deliverable_profile_sheet",
                "manual_validation_manual_storm_hydraulic_invalid",
                "county_standard_pending",
            ],
        )
        self.assertIn("report", details[0]["what_failed"])
        self.assertIn("profile sheet", details[1]["missing_data"][0])
        self.assertTrue(details[2]["engineer_review_required"])
        self.assertEqual(details[3]["next_action"], "Inspect the source blocker, resolve the underlying issue, and rerun validation.")


if __name__ == "__main__":
    unittest.main()
