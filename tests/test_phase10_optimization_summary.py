import unittest

from planner import build_plan
from planner_intelligence import CandidateLineage, CandidatePlan, PlannerIntelligence


class Phase10OptimizationSummaryTest(unittest.TestCase):
    def test_build_plan_preserves_optimization_summary(self) -> None:
        plan = build_plan(
            {
                "project_name": "Optimization Summary Test",
                "units": "ft",
                "mode": "site_plan",
                "project_type": "commercial_pad",
                "site_type": "commercial_pad",
                "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
                "setback": 10.0,
                "street_edge": "bottom",
                "layout_strategy": "front_parking",
                "site_plan": {"parking_count": 24},
                "meta": {"input_mode": "manual", "source_input_mode": "manual", "manual_mode": True},
            }
        )
        optimization = ((plan.get("meta") or {}).get("optimization_summary") or {})
        self.assertEqual(str(optimization.get("active_goal") or ""), "balanced")
        self.assertIn("parking_fit", dict(optimization.get("component_scores") or {}))
        self.assertIn("earthwork_balance", dict(optimization.get("component_scores") or {}))
        self.assertIn("drainage_capacity", dict(optimization.get("component_scores") or {}))
        self.assertIn("pipe_efficiency", dict(optimization.get("component_scores") or {}))
        self.assertIn("recommendations", optimization)

    def test_goal_scoring_uses_pipe_efficiency_summary(self) -> None:
        intelligence = PlannerIntelligence()
        candidate = CandidatePlan(
            candidate_id="cand_1",
            option_name="Pipe Efficient",
            strategy={"strategy_name": "utility_efficient"},
            payload={"mode": "site_plan", "site_plan": {"parking_count": 24}},
            lineage=CandidateLineage(candidate_id="cand_1"),
            plan={
                "actions": [{"layer": "PIPE"}, {"layer": "UTILITY"}],
                "meta": {
                    "qa": {"warning_count": 0, "error_count": 0, "stats": {"estimated_pipe_length_ft": 220.0}},
                    "planner_score": {"total": 82.0},
                    "optimization_summary": {
                        "overall_score": 81.0,
                        "component_scores": {
                            "pipe_efficiency": 92.0,
                            "parking_fit": 80.0,
                            "earthwork_balance": 76.0,
                            "drainage_capacity": 84.0,
                            "utility_efficiency": 79.0,
                        },
                        "metrics": {
                            "normalized_linear_density": 8.0,
                            "max_capacity_ratio": 0.82,
                        },
                    },
                },
            },
        )
        intelligence._score_candidate(candidate, {"goal": "reduce_pipe_length"})
        self.assertGreater(candidate.score.bonuses.get("goal_match", 0.0), 0.0)
        self.assertGreater(candidate.score.bonuses.get("optimization_alignment", 0.0), 0.0)


if __name__ == "__main__":
    unittest.main()
