import unittest

from backend.planning.golden_runner import run_golden_scenario, run_golden_scenarios


def _fake_plan(payload):
    return {
        "project_name": payload.get("project_name"),
        "actions": [
            {
                "task": "rectangle",
                "layer": "SITE",
                "canonical_source_type": "site",
                "canonical_source_id": "site-1",
                "width": 220.0,
                "height": 160.0,
            }
        ],
        "meta": {
            "lot": {"w": 220.0, "h": 160.0},
            "grading": {"proposed_surface": {"source": "test"}, "low_points": [{"id": "lp-1"}]},
            "drainage": {"basins": [{"id": "basin-1"}]},
            "storm_pipes": {"segments": [{"id": "storm-1", "length_ft": 50.0}]},
            "sanitary": {"segments": [{"id": "san-1", "length_ft": 40.0}]},
            "utilities": {"conflict_hooks": {"utility_segments": [{"id": "util-1"}]}},
            "quantities": {"totals": {"pipe_length_ft": 50.0}},
            "civil_design_readiness": {
                "status": "needs_engineering_review",
                "success": True,
                "production_ready": False,
                "critical_blockers": [],
                "production_blockers": [{"area": "existing_conditions", "field": "survey_surface"}],
                "missing_requirements": [],
            },
            "engine_readiness": {
                "production_ready": False,
                "blocked_engine_ids": [],
                "production_blocked_engine_ids": ["gis_existing_conditions"],
            },
            "construction_readiness": {
                "ready": False,
                "status": "not_construction_ready",
                "blockers": [{"area": "existing_conditions", "field": "survey"}],
            },
            "construction_package_manifest": {
                "release_allowed": False,
                "construction_ready": False,
                "blockers": [{"area": "existing_conditions", "field": "survey"}],
            },
        },
    }


class GoldenRunnerTests(unittest.TestCase):
    def test_run_single_golden_scenario_reports_readiness_and_gates(self) -> None:
        result = run_golden_scenario("small_commercial_pad", build_plan_fn=_fake_plan)

        self.assertTrue(result["success"])
        self.assertEqual(result["scenario_id"], "small_commercial_pad")
        self.assertFalse(result["readiness_summary"]["civil_production_ready"])
        self.assertTrue(result["gate_results"])
        self.assertFalse(result["missing_canonical_signals"])
        self.assertFalse(result["failed_benchmark_expectations"])
        detail = result["readiness_summary"]["production_blocker_details"][0]
        self.assertEqual(detail["area"], "existing_conditions")
        self.assertEqual(detail["field"], "survey_surface")
        self.assertTrue(detail["next_action"])
        self.assertEqual(result["benchmark_status"], "passed_with_expected_blockers")

    def test_run_selected_golden_scenarios(self) -> None:
        result = run_golden_scenarios(["small_commercial_pad", "incomplete_bad_input_case"], build_plan_fn=_fake_plan)

        self.assertTrue(result["success"])
        self.assertEqual(result["scenario_count"], 2)
        self.assertIn("explicit blockers", result["truth_label"])

    def test_run_scenario_fails_when_required_canonical_signals_are_missing(self) -> None:
        def incomplete_plan(payload):
            return {
                "project_name": payload.get("project_name"),
                "meta": {
                    "civil_design_readiness": {
                        "status": "blocked",
                        "success": False,
                        "production_ready": False,
                        "production_blockers": [{"field": "survey_surface"}],
                    },
                    "engine_readiness": {"production_ready": False},
                },
            }

        result = run_golden_scenario("small_commercial_pad", build_plan_fn=incomplete_plan)

        self.assertFalse(result["success"])
        self.assertIn("required_canonical_signals_missing", result["hard_failures"])
        self.assertIn("benchmark_numeric_expectations_failed", result["hard_failures"])
        self.assertIn("hard_failure_details", result)
        self.assertTrue(result["hard_failure_details"][0]["what_failed"])
        self.assertIn("site_boundary", result["missing_canonical_signals"])

    def test_run_scenario_fails_when_construction_release_gates_are_missing(self) -> None:
        def missing_construction_gates(payload):
            plan = _fake_plan(payload)
            plan["meta"].pop("construction_readiness", None)
            plan["meta"].pop("construction_package_manifest", None)
            return plan

        result = run_golden_scenario("small_commercial_pad", build_plan_fn=missing_construction_gates)

        self.assertFalse(result["success"])
        self.assertIn("construction_readiness_missing", result["hard_failures"])
        self.assertIn("construction_package_manifest_missing", result["hard_failures"])

    def test_run_scenario_accepts_deliverable_package_alias_for_package_gate_presence(self) -> None:
        def aliased_package(payload):
            plan = _fake_plan(payload)
            plan["meta"]["deliverable_package"] = plan["meta"].pop("construction_package_manifest")
            return plan

        result = run_golden_scenario("small_commercial_pad", build_plan_fn=aliased_package)

        self.assertTrue(result["success"])
        self.assertNotIn("construction_package_manifest_missing", result["hard_failures"])

    def test_run_scenario_fails_when_construction_release_is_allowed_without_civil_readiness(self) -> None:
        def false_release(payload):
            plan = _fake_plan(payload)
            plan["meta"]["construction_readiness"] = {"ready": False, "status": "not_construction_ready"}
            plan["meta"]["construction_package_manifest"] = {"release_allowed": True}
            return plan

        result = run_golden_scenario("small_commercial_pad", build_plan_fn=false_release)

        self.assertFalse(result["success"])
        self.assertIn("construction_release_allowed_without_readiness", result["hard_failures"])
        self.assertIn("construction_release_allowed_without_civil_production_ready", result["hard_failures"])
        self.assertIn("construction_release_allowed_with_incomplete_package", result["hard_failures"])
        self.assertIn("construction_release_allowed_with_unverified_package_model", result["hard_failures"])

    def test_run_scenario_fails_when_direct_construction_export_is_claimed_without_release_evidence(self) -> None:
        def false_direct_release(payload):
            plan = _fake_plan(payload)
            plan["construction_export_allowed"] = True
            plan["meta"]["release_state"] = "released_for_construction"
            return plan

        result = run_golden_scenario("small_commercial_pad", build_plan_fn=false_direct_release)

        self.assertFalse(result["success"])
        self.assertTrue(result["readiness_summary"]["construction_release_allowed"])
        self.assertIn("construction_release_allowed_without_readiness", result["hard_failures"])
        self.assertIn("construction_release_allowed_without_civil_production_ready", result["hard_failures"])
        self.assertIn("construction_release_allowed_with_incomplete_package", result["hard_failures"])
        self.assertIn("construction_release_allowed_with_unverified_package_model", result["hard_failures"])

    def test_run_scenario_reads_release_state_from_deliverable_package_alias(self) -> None:
        def false_alias_release(payload):
            plan = _fake_plan(payload)
            plan["meta"]["construction_readiness"] = {"ready": False, "status": "not_construction_ready"}
            plan["meta"]["construction_deliverable_package"] = {"release_allowed": True}
            return plan

        result = run_golden_scenario("small_commercial_pad", build_plan_fn=false_alias_release)

        self.assertFalse(result["success"])
        self.assertTrue(result["readiness_summary"]["construction_release_allowed"])
        self.assertIn("construction_release_allowed_without_readiness", result["hard_failures"])

    def test_run_scenario_fails_when_sealed_release_state_is_claimed_without_evidence(self) -> None:
        def false_direct_release(payload):
            plan = _fake_plan(payload)
            plan["meta"]["release_state"] = "sealed"
            return plan

        result = run_golden_scenario("small_commercial_pad", build_plan_fn=false_direct_release)

        self.assertFalse(result["success"])
        self.assertTrue(result["readiness_summary"]["construction_release_allowed"])
        self.assertIn("construction_release_allowed_without_readiness", result["hard_failures"])
        self.assertIn("construction_release_allowed_with_incomplete_package", result["hard_failures"])

    def test_run_scenario_fails_when_professional_review_claims_release_without_package_evidence(self) -> None:
        def false_professional_release(payload):
            plan = _fake_plan(payload)
            plan["meta"]["professional_review"] = {
                "status": "released_for_construction",
                "released_for_construction": True,
            }
            return plan

        result = run_golden_scenario("small_commercial_pad", build_plan_fn=false_professional_release)

        self.assertFalse(result["success"])
        self.assertTrue(result["readiness_summary"]["construction_release_allowed"])
        self.assertIn("construction_release_allowed_without_readiness", result["hard_failures"])
        self.assertIn("construction_release_allowed_with_incomplete_package", result["hard_failures"])

    def test_run_scenario_fails_when_sealed_professional_review_claims_release_without_package_evidence(self) -> None:
        def false_professional_release(payload):
            plan = _fake_plan(payload)
            plan["meta"]["professional_review"] = {
                "status": "sealed",
                "sealed": True,
            }
            return plan

        result = run_golden_scenario("small_commercial_pad", build_plan_fn=false_professional_release)

        self.assertFalse(result["success"])
        self.assertTrue(result["readiness_summary"]["construction_release_allowed"])
        self.assertIn("construction_release_allowed_without_readiness", result["hard_failures"])
        self.assertIn("construction_release_allowed_with_incomplete_package", result["hard_failures"])

    def test_run_scenario_fails_when_construction_release_package_is_incomplete(self) -> None:
        def incomplete_release_package(payload):
            plan = _fake_plan(payload)
            plan["meta"]["civil_design_readiness"]["production_ready"] = True
            plan["meta"]["construction_readiness"] = {"ready": True, "status": "construction_ready", "blockers": []}
            plan["meta"]["construction_package_manifest"] = {
                "release_allowed": True,
                "construction_package_artifact_status": {
                    "complete_for_release": False,
                    "model_matches_expected": False,
                    "missing": ["cad_export", "qa_report"],
                },
            }
            return plan

        result = run_golden_scenario("small_commercial_pad", build_plan_fn=incomplete_release_package)

        self.assertFalse(result["success"])
        self.assertIn("construction_release_allowed_with_incomplete_package", result["hard_failures"])
        self.assertIn("construction_release_allowed_with_unverified_package_model", result["hard_failures"])
        self.assertEqual(
            result["readiness_summary"]["construction_package_missing_artifacts"],
            ["cad_export", "qa_report"],
        )

    def test_run_scenario_fails_when_release_allowed_without_explicit_package_release_flag(self) -> None:
        def missing_package_release_flag(payload):
            plan = _fake_plan(payload)
            plan["meta"]["civil_design_readiness"]["production_ready"] = True
            plan["meta"]["construction_readiness"] = {"ready": True, "status": "construction_ready", "blockers": []}
            plan["meta"]["construction_package_manifest"] = {
                "release_allowed": True,
                "construction_package_artifact_status": {
                    "complete_for_release": True,
                    "model_matches_expected": True,
                    "release_ready_flag": None,
                    "production_ready_flag": True,
                    "missing": [],
                },
                "professional_package_release_status": {
                    "professional_review_present": True,
                    "professional_release_valid": True,
                    "model_matches_package": True,
                    "package_matches_review": True,
                },
            }
            return plan

        result = run_golden_scenario("small_commercial_pad", build_plan_fn=missing_package_release_flag)

        self.assertFalse(result["success"])
        self.assertIn(
            "construction_release_allowed_without_explicit_package_release_flag",
            result["hard_failures"],
        )
        self.assertFalse(result["readiness_summary"]["construction_package_release_ready_flag"])

    def test_run_scenario_fails_when_release_allowed_without_explicit_package_production_flag(self) -> None:
        def missing_package_production_flag(payload):
            plan = _fake_plan(payload)
            plan["meta"]["civil_design_readiness"]["production_ready"] = True
            plan["meta"]["construction_readiness"] = {"ready": True, "status": "construction_ready", "blockers": []}
            plan["meta"]["construction_package_manifest"] = {
                "release_allowed": True,
                "construction_package_artifact_status": {
                    "complete_for_release": True,
                    "model_matches_expected": True,
                    "release_ready_flag": True,
                    "production_ready_flag": None,
                    "missing": [],
                },
                "professional_package_release_status": {
                    "professional_review_present": True,
                    "professional_release_valid": True,
                    "model_matches_package": True,
                    "package_matches_review": True,
                },
            }
            return plan

        result = run_golden_scenario("small_commercial_pad", build_plan_fn=missing_package_production_flag)

        self.assertFalse(result["success"])
        self.assertIn(
            "construction_release_allowed_without_explicit_package_production_flag",
            result["hard_failures"],
        )
        self.assertFalse(result["readiness_summary"]["construction_package_production_ready_flag"])

    def test_run_scenario_fails_when_release_allowed_without_valid_professional_release(self) -> None:
        def invalid_professional_release(payload):
            plan = _fake_plan(payload)
            plan["meta"]["civil_design_readiness"]["production_ready"] = True
            plan["meta"]["construction_readiness"] = {"ready": True, "status": "construction_ready", "blockers": []}
            plan["meta"]["construction_package_manifest"] = {
                "release_allowed": True,
                "construction_package_artifact_status": {
                    "complete_for_release": True,
                    "model_matches_expected": True,
                    "release_ready_flag": True,
                    "production_ready_flag": True,
                    "missing": [],
                },
                "professional_package_release_status": {
                    "professional_review_present": True,
                    "professional_release_valid": False,
                    "model_matches_package": False,
                    "package_matches_review": False,
                },
            }
            return plan

        result = run_golden_scenario("small_commercial_pad", build_plan_fn=invalid_professional_release)

        self.assertFalse(result["success"])
        self.assertIn("construction_release_allowed_without_valid_professional_release", result["hard_failures"])
        self.assertIn("construction_release_allowed_with_professional_model_mismatch", result["hard_failures"])
        self.assertIn("construction_release_allowed_with_professional_package_mismatch", result["hard_failures"])
        self.assertFalse(result["readiness_summary"]["professional_release_valid"])

    def test_run_scenario_fails_when_numeric_expectations_are_implausible(self) -> None:
        def implausible_plan(payload):
            plan = _fake_plan(payload)
            plan["meta"]["lot"] = {"w": 10.0, "h": 10.0}
            plan["meta"]["storm_pipes"] = {"segments": []}
            plan["meta"]["quantities"] = {"totals": {"pipe_length_ft": 0.0}}
            return plan

        result = run_golden_scenario("small_commercial_pad", build_plan_fn=implausible_plan)

        self.assertFalse(result["success"])
        self.assertIn("benchmark_numeric_expectations_failed", result["hard_failures"])
        self.assertIn("lot_area_sf", result["failed_benchmark_expectations"])
        self.assertIn("storm_segment_count", result["failed_benchmark_expectations"])

    def test_real_small_commercial_golden_scenario_passes_harness(self) -> None:
        result = run_golden_scenario("small_commercial_pad")

        self.assertTrue(result["success"], result)
        self.assertFalse(result["missing_canonical_signals"])
        self.assertFalse(result["failed_benchmark_expectations"])
        self.assertFalse(result["readiness_summary"]["civil_production_ready"])

    def test_real_incomplete_golden_scenario_stays_truthfully_blocked(self) -> None:
        result = run_golden_scenario("incomplete_bad_input_case")

        self.assertTrue(result["success"], result)
        self.assertFalse(result["readiness_summary"]["civil_success"])
        self.assertGreater(result["readiness_summary"]["critical_blocker_count"], 0)
        self.assertFalse(result["readiness_summary"]["civil_production_ready"])

    def test_real_golden_scenario_suite_passes_with_expected_blockers(self) -> None:
        result = run_golden_scenarios()

        self.assertTrue(result["success"], result)
        self.assertEqual(result["scenario_count"], 10)
        for scenario in result["results"]:
            self.assertEqual(scenario["benchmark_status"], "passed_with_expected_blockers", scenario)
            self.assertFalse(scenario["missing_canonical_signals"], scenario)
            self.assertFalse(scenario["failed_benchmark_expectations"], scenario)
            self.assertFalse(scenario["readiness_summary"]["civil_production_ready"], scenario)


if __name__ == "__main__":
    unittest.main()
