import unittest

from backend.planning.common import (
    blocker_explanation,
    blocker_explanations,
    readiness_issue_explanation,
)


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

    def test_structured_readiness_issue_explanation_keeps_area_and_field(self):
        detail = readiness_issue_explanation(
            {
                "area": "storm_depth",
                "field": "hgl_egl_profiles",
                "message": "Storm depth needs HGL and EGL profiles.",
                "severity": "blocker",
            }
        )

        self.assertEqual(detail["code"], "storm_depth_hgl_egl_profiles")
        self.assertEqual(detail["area"], "storm_depth")
        self.assertEqual(detail["field"], "hgl_egl_profiles")
        self.assertEqual(detail["what_failed"], "Storm depth needs HGL and EGL profiles.")
        self.assertIn("production-ready", detail["why_it_matters"])
        self.assertEqual(detail["missing_data"], ["hgl egl profiles"])
        self.assertTrue(detail["engineer_review_required"])


if __name__ == "__main__":
    unittest.main()
