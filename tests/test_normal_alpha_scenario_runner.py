import unittest

from backend.application.normal_alpha_scenario_runner import (
    HEAVY_EXPORT_BLOCKER,
    RUNNER_VERSION,
    run_normal_alpha_scenario,
)


class NormalAlphaScenarioRunnerTests(unittest.TestCase):
    def test_runner_completes_under_reasonable_timeout_and_produces_packages(self) -> None:
        result = run_normal_alpha_scenario()

        self.assertEqual(result["version"], RUNNER_VERSION)
        self.assertEqual(result["status"], "completed_with_blockers")
        self.assertLess(result["elapsed_ms"], 30000.0)
        self.assertEqual(result["export_package_report_v1"]["source"], "export_package_report_v1")
        self.assertEqual(result["engineer_review_package_v1"]["version"], "engineer_review_package_v1")
        self.assertEqual(result["engine_depth_audit_report_v1"]["version"], "engine_depth_audit_report_v1")
        self.assertEqual(result["ready_language"], "ready_for_engineer_review")
        self.assertFalse(result["construction_release_allowed"])

    def test_heavy_export_skip_is_explicit_and_blocks_release_confidence(self) -> None:
        result = run_normal_alpha_scenario()
        plan_meta = result["plan"]["meta"]
        export_report = result["export_package_report_v1"]
        review_package = result["engineer_review_package_v1"]

        self.assertIn("dxf", plan_meta["deliverables"]["requested"])
        self.assertNotIn("dxf", plan_meta["deliverables"]["produced"])
        self.assertIn("dxf", plan_meta["deliverables"]["skipped"])
        self.assertEqual(result["heavy_exports"]["blocker"], HEAVY_EXPORT_BLOCKER)
        self.assertIn(HEAVY_EXPORT_BLOCKER, export_report["construction_release_blockers"])
        self.assertFalse(export_report["construction_release_allowed"])
        self.assertFalse(review_package["construction_release_allowed"])
        self.assertFalse(review_package["ready_for_construction"])
        self.assertTrue(review_package["engineer_approval_required"])

    def test_ai_orchestration_and_sanitary_blockers_remain_visible(self) -> None:
        result = run_normal_alpha_scenario()
        failed_ids = set(result["engine_depth_audit_report_v1"]["failed_check_ids"])

        self.assertIn("mixed_use_14_acre_site:ai_orchestration:required_engine_depth", failed_ids)
        self.assertIn("mixed_use_14_acre_site:sanitary:required_engine_depth", failed_ids)
        self.assertIn("mixed_use_14_acre_site:ai_orchestration:required_engine_depth", result["remaining_engine_depth_blockers"])
        self.assertIn("mixed_use_14_acre_site:sanitary:required_engine_depth", result["remaining_engine_depth_blockers"])
        self.assertGreaterEqual(result["blocker_count"], 3)


if __name__ == "__main__":
    unittest.main()
