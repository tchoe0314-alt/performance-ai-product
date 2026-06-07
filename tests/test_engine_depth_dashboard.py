import unittest

from backend.planning.engine_depth_dashboard import DASHBOARD_VERSION, build_engine_depth_dashboard


def _audit_report(score: float = 70.0) -> dict:
    blocker = {
        "area": "expected_vs_actual_engine_depth",
        "field": "grading",
        "engine_id": "grading",
        "scenario_id": "small_commercial_pad",
        "message": "Engine depth audit failed deterministic check small_commercial_pad:grading:required_engine_depth.",
        "why_needed": "Required scenario engines must provide deterministic review or production-depth evidence.",
        "suggested_next_action": "Restore grading depth evidence and rerun the audit.",
        "severity": "blocker",
    }
    failed_check = {
        "check_id": "small_commercial_pad:grading:required_engine_depth",
        "scenario_id": "small_commercial_pad",
        "engine_id": "grading",
        "check_type": "expected_vs_actual_engine_depth",
        "passed": False,
        "truth_label": "Required scenario engines must produce deterministic review or production-depth evidence.",
    }
    return {
        "version": "engine_depth_audit_report_v1",
        "status": "failed",
        "engine_count": 2,
        "scenario_count": 1,
        "failed_deterministic_check_count": 1,
        "blocker_count": 1,
        "summary": {"overall_depth_score": score, "status": "failed"},
        "engine_rows": [
            {
                "engine_id": "grading",
                "name": "Grading",
                "score": 25.0,
                "classification": "concept",
                "required_scenario_ids": ["small_commercial_pad"],
                "failed_check_count": 1,
                "blockers": [blocker],
                "launch_gate": "blocked",
                "confidence": 0.2,
                "first_failing_layer": "expected_vs_actual_engine_depth",
            },
            {
                "engine_id": "storm_pipe",
                "name": "Storm Pipe",
                "score": 100.0,
                "classification": "production-depth",
                "required_scenario_ids": ["small_commercial_pad"],
                "failed_check_count": 0,
                "blockers": [],
                "launch_gate": "production_depth_gate_clear",
                "confidence": 0.95,
            },
        ],
        "scenario_results": [
            {
                "scenario_id": "small_commercial_pad",
                "name": "Small commercial pad",
                "status": "failed",
                "depth_score": 62.5,
                "required_engine_ids": ["grading", "storm_pipe"],
                "required_engine_results": {
                    "grading": {"classification": "concept", "failed_check_count": 1},
                    "storm_pipe": {"classification": "production-depth", "failed_check_count": 0},
                },
                "failed_check_ids": ["small_commercial_pad:grading:required_engine_depth"],
                "blockers": [blocker],
            }
        ],
        "deterministic_checks": [failed_check],
        "blockers": [blocker],
    }


class EngineDepthDashboardTests(unittest.TestCase):
    def test_exposes_depth_operational_views(self):
        dashboard = build_engine_depth_dashboard(_audit_report())

        self.assertEqual(dashboard["version"], DASHBOARD_VERSION)
        self.assertEqual(dashboard["overall_depth_score"], 70.0)
        self.assertIs(dashboard["construction_release_allowed"], False)
        self.assertEqual(dashboard["per_engine_scores"][0]["engine_id"], "grading")
        self.assertEqual(dashboard["per_engine_scores"][0]["fix_link"]["target_panel"], "grading")
        self.assertEqual(dashboard["scenario_coverage"][0]["coverage_percent"], 50.0)
        self.assertEqual(dashboard["missing_proof_checklist"][0]["target_panel"], "grading")
        self.assertEqual(dashboard["fix_links"][0]["suggested_next_action"], "Restore grading depth evidence and rerun the audit.")

    def test_records_trend_history_when_available(self):
        dashboard = build_engine_depth_dashboard(
            _audit_report(score=80.0),
            history_reports=[_audit_report(score=60.0), _audit_report(score=80.0)],
        )

        self.assertEqual([point["overall_depth_score"] for point in dashboard["trend_history"]], [60.0, 80.0])
        self.assertEqual([point["index"] for point in dashboard["trend_history"]], [0, 1])


if __name__ == "__main__":
    unittest.main()
