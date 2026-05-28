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
        self.assertIn("site_boundary", result["missing_canonical_signals"])

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


if __name__ == "__main__":
    unittest.main()
