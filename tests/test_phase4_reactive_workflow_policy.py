import unittest

from backend.planning.reactive_model import build_reactive_run_policy, build_reactive_update_report


class Phase4ReactiveWorkflowPolicyTests(unittest.TestCase):
    def test_layout_move_keeps_visual_edit_live_but_requires_engineering_confirmation(self) -> None:
        report = build_reactive_update_report(changed_engine_ids=["roadway_corridor"])
        policy = report["run_policy"]

        self.assertEqual(policy["rerun_mode"], "manual_confirm_required")
        self.assertEqual(policy["estimated_cost"], "heavy")
        self.assertTrue(policy["live_visual_update"])
        self.assertTrue(policy["cheap_validation_auto_run"])
        self.assertFalse(policy["automatic_engineering_rerun"])
        self.assertTrue(policy["requires_user_confirmation"])
        self.assertTrue(policy["impact_preview_required"])
        self.assertIn("layout", policy["heavy_impacted_stages"])
        self.assertIn("grading", policy["heavy_impacted_stages"])
        self.assertEqual(policy["debounced_validation_ms"], 500)
        self.assertEqual(policy["export_policy"], "block_exports_until_impacted_stages_complete")

    def test_sheet_only_edit_is_fast_enough_for_live_engineering_rerun(self) -> None:
        report = build_reactive_update_report(changed_stages=["sheets"])
        policy = report["run_policy"]

        self.assertEqual(policy["rerun_mode"], "auto_live")
        self.assertEqual(policy["estimated_cost"], "quick")
        self.assertTrue(policy["automatic_engineering_rerun"])
        self.assertFalse(policy["requires_user_confirmation"])
        self.assertFalse(policy["impact_preview_required"])
        self.assertEqual(policy["heavy_impacted_stages"], [])

    def test_storm_pipe_edit_debounces_checks_without_live_heavy_rerun(self) -> None:
        report = build_reactive_update_report(changed_engine_ids=["storm_pipe"])
        policy = report["run_policy"]

        self.assertEqual(policy["rerun_mode"], "manual_confirm_required")
        self.assertTrue(policy["live_visual_update"])
        self.assertTrue(policy["cheap_validation_auto_run"])
        self.assertFalse(policy["automatic_engineering_rerun"])
        self.assertTrue(policy["requires_user_confirmation"])
        self.assertIn("storm_pipes", policy["heavy_impacted_stages"])
        self.assertIn("sheets", policy["impacted_stages"])

    def test_small_qa_edit_uses_debounced_validation_contract(self) -> None:
        policy = build_reactive_run_policy(impacted_stages=["qa"], changed_stages=["qa"])

        self.assertEqual(policy["rerun_mode"], "auto_live")
        self.assertEqual(policy["estimated_cost"], "quick")
        self.assertEqual(policy["debounced_validation_ms"], 500)
        self.assertTrue(policy["cheap_validation_auto_run"])
        self.assertTrue(policy["automatic_engineering_rerun"])


if __name__ == "__main__":
    unittest.main()
