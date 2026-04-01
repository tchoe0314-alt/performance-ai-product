import unittest
from unittest.mock import patch

from backend.planning.runtime import PlanQualityReport
from planner import build_plan


class DependencyAwareRerunTest(unittest.TestCase):
    def test_second_pass_reruns_only_dirty_stage(self) -> None:
        payload = {
            "project_name": "Selective Rerun Test",
            "units": "ft",
            "mode": "site_plan",
            "project_type": "commercial_pad",
            "site_type": "commercial_pad",
            "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
            "setback": 10.0,
            "street_edge": "bottom",
            "layout_strategy": "front_parking",
            "site_plan": {"parking_count": 24},
            "meta": {"input_mode": "assisted", "source_input_mode": "assisted", "manual_mode": False, "planner_passes": 2},
        }

        def fake_qa(ctx):
            report = PlanQualityReport()
            if ctx.pass_index == 1:
                for idx in range(5):
                    report.add(f"PASS1_WARN_{idx}", "warning", f"pass1 warning {idx}")
            return report

        def fake_fix(ctx, report):
            ctx.manager.mark_system_dirty("qa", reason="Targeted QA-only rerun for regression.")
            ctx.add_stage("fix", True, "Applied targeted QA-only rerun.", changed_targets=["qa"])

        with patch("planner._run_qa_stage", side_effect=fake_qa), patch("planner._apply_fix_pass", side_effect=fake_fix):
            plan = build_plan(payload)

        rerun_history = (plan.get("meta") or {}).get("rerun_history") or []
        layout_runs = [row for row in rerun_history if row.get("stage_name") == "layout"]
        qa_runs = [row for row in rerun_history if row.get("stage_name") == "qa"]

        self.assertGreaterEqual(len(layout_runs), 2)
        self.assertEqual(layout_runs[0]["action"], "run")
        self.assertEqual(layout_runs[1]["action"], "skipped_clean")
        self.assertEqual(qa_runs[0]["action"], "run")
        self.assertEqual(qa_runs[1]["action"], "run")


if __name__ == "__main__":
    unittest.main()
