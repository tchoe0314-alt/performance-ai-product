import unittest

from backend.application.normal_alpha_scenario_runner import (
    HEAVY_EXPORT_BLOCKER,
    LICENSED_ENGINEER_REVIEW_BLOCKER,
    REAL_PROJECT_SUITE_VERSION,
    RUNNER_VERSION,
    run_normal_alpha_scenario,
    run_real_project_scenario_suite,
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
        self.assertEqual(result["construction_document_support_package_v1"]["version"], "construction_document_support_package_v1")
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

    def test_real_project_scenario_suite_reports_required_matrix_without_construction_release(self) -> None:
        result = run_real_project_scenario_suite()

        self.assertEqual(result["version"], REAL_PROJECT_SUITE_VERSION)
        self.assertEqual(result["runner_version"], RUNNER_VERSION)
        self.assertEqual(result["status"], "completed_with_blockers")
        self.assertEqual(result["scenario_count"], 5)
        self.assertFalse(result["construction_release_allowed"])
        self.assertTrue(result["construction_release_blocked"])

        rows = {row["scenario_id"]: row for row in result["scenario_matrix"]}
        self.assertEqual(
            set(rows),
            {
                "survey_backed_commercial_pad",
                "dem_backed_drainage_detention_site",
                "utility_heavy_site",
                "roadway_corridor",
                "incomplete_bad_input_case",
            },
        )
        self.assertEqual(rows["survey_backed_commercial_pad"]["survey_control_status"], "fixture_control_review_required")
        self.assertEqual(rows["dem_backed_drainage_detention_site"]["survey_control_status"], "dem_fixture_no_survey_control")
        self.assertEqual(rows["incomplete_bad_input_case"]["survey_control_status"], "missing_required_input")
        self.assertFalse(rows["incomplete_bad_input_case"]["ready_for_engineer_review"])
        for row in rows.values():
            self.assertEqual(row["standards_status"], "blocked_review_required")
            self.assertFalse(row["construction_release_allowed"])
            self.assertIn(row["construction_document_support_package_status"], {"blocked", "review_required", "included", "incomplete"})

    def test_each_real_project_scenario_reports_packages_inputs_engine_depth_and_blockers(self) -> None:
        result = run_real_project_scenario_suite()

        for scenario in result["scenarios"]:
            self.assertTrue(scenario["inputs_used"], scenario["scenario_id"])
            self.assertIn("survey_control_status", scenario)
            self.assertIn("standards_status", scenario)
            self.assertIn("systems_completed", scenario)
            self.assertIn("systems_blocked", scenario)
            self.assertEqual(scenario["engine_depth_summary"]["contract_version"], "engine_contracts_v1")
            self.assertEqual(scenario["export_package_report_v1"]["source"], "export_package_report_v1")
            self.assertEqual(scenario["engineer_review_package_v1"]["version"], "engineer_review_package_v1")
            self.assertEqual(scenario["construction_document_support_package_v1"]["version"], "construction_document_support_package_v1")
            self.assertFalse(scenario["export_package_report_v1"]["construction_release_allowed"])
            self.assertFalse(scenario["engineer_review_package_v1"]["construction_release_allowed"])
            self.assertFalse(scenario["construction_document_support_package_v1"]["construction_release_allowed"])
            self.assertFalse(scenario["construction_release_allowed"])
            blocker_fields = {
                item["field"]
                for item in scenario["blockers"]
                if isinstance(item, dict) and "field" in item
            }
            self.assertIn(LICENSED_ENGINEER_REVIEW_BLOCKER, blocker_fields)
            self.assertIn(HEAVY_EXPORT_BLOCKER, blocker_fields)

    def test_real_project_scenario_suite_does_not_claim_standards_or_survey_control_readiness(self) -> None:
        result = run_real_project_scenario_suite()

        commercial = next(row for row in result["scenarios"] if row["scenario_id"] == "survey_backed_commercial_pad")
        support_package = commercial["construction_document_support_package_v1"]
        self.assertFalse(commercial["plan"]["meta"]["standards_package"]["production_usable"])
        self.assertFalse(commercial["plan"]["meta"]["survey_control_package"]["production_usable"])
        self.assertFalse(support_package["civora_engineer_of_record"])
        self.assertFalse(support_package["simulated_seal_allowed"])
        self.assertFalse(support_package["submittal_by_civora_allowed"])


if __name__ == "__main__":
    unittest.main()
