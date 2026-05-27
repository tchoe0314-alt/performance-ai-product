import unittest

from backend.planning.reactive_model import build_reactive_update_report, execute_reactive_rerun


class ReactiveModelContractTests(unittest.TestCase):
    def test_roadway_change_marks_downstream_engines_and_stages(self) -> None:
        report = build_reactive_update_report(changed_engine_ids=["roadway_corridor"])

        self.assertIn("grading", report["impacted_engine_ids"])
        self.assertIn("storm_pipes", report["impacted_stages"])
        self.assertIn("qa", report["impacted_stages"])
        self.assertFalse(report["export_blocked"])
        self.assertTrue(report["partial_rerun_supported"])

    def test_stale_outputs_block_export(self) -> None:
        report = build_reactive_update_report(changed_engine_ids=["grading"], stale_outputs=["storm_pipes", "sheets"])

        self.assertTrue(report["export_blocked"])
        self.assertEqual(report["stale_outputs"], ["sheets", "storm_pipes"])
        self.assertTrue(report["dirty_reasons"])

    def test_execute_reactive_rerun_performs_safe_full_rerun_with_truth_label(self) -> None:
        def fake_build(payload):
            return {"meta": {"civil_design_readiness": {"production_ready": False}, "payload": payload}}

        result = execute_reactive_rerun(
            {"project_name": "Reactive", "meta": {}},
            changed_engine_ids=["roadway_corridor"],
            edits={"project_name": "Reactive Edited"},
            build_plan_fn=fake_build,
        )

        report = result["reactive_update_report"]

        self.assertTrue(result["success"])
        self.assertFalse(report["partial_rerun_executed"])
        self.assertIn("full rerun", result["truth_label"])
        self.assertIn("grading", report["impacted_engine_ids"])


if __name__ == "__main__":
    unittest.main()
