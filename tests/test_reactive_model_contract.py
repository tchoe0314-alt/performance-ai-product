import unittest

from backend.planning.reactive_model import build_reactive_update_report, execute_reactive_rerun, reactive_report_from_plan


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

    def test_changed_stage_marks_declared_downstream_stages(self) -> None:
        report = build_reactive_update_report(changed_stages=["grading"])

        self.assertIn("grading", report["impacted_stages"])
        self.assertIn("drainage", report["impacted_stages"])
        self.assertIn("storm_pipes", report["impacted_stages"])
        self.assertIn("qa", report["impacted_stages"])
        self.assertNotIn("layout", report["impacted_stages"])

    def test_reactive_report_from_plan_treats_changed_targets_as_stages(self) -> None:
        report = reactive_report_from_plan(
            {
                "meta": {
                    "changed_targets": ["grading"],
                    "stage_results": [{"stage_name": "grading"}],
                    "stale_outputs": ["storm_pipes"],
                }
            }
        )

        self.assertEqual(report["changed_stages"], ["grading"])
        self.assertEqual(report["changed_engine_ids"], [])
        self.assertIn("drainage", report["impacted_stages"])
        self.assertIn("storm_pipes", report["impacted_stages"])
        self.assertTrue(report["export_blocked"])

    def test_execute_reactive_rerun_performs_safe_full_rerun_with_truth_label(self) -> None:
        def fake_build(payload):
            return {
                "meta": {
                    "civil_design_readiness": {"production_ready": False},
                    "payload": payload,
                    "stage_results": [
                        {"stage_name": "layout", "success": True, "completeness": "complete"},
                        {"stage_name": "grading", "success": True, "completeness": "complete"},
                        {"stage_name": "drainage", "success": True, "completeness": "complete"},
                        {"stage_name": "storm_pipes", "success": True, "completeness": "complete"},
                        {"stage_name": "sanitary", "success": True, "completeness": "complete"},
                        {"stage_name": "utility_network", "success": True, "completeness": "complete"},
                        {"stage_name": "coordination_resolution", "success": True, "completeness": "complete"},
                        {"stage_name": "earthwork", "success": True, "completeness": "complete"},
                        {"stage_name": "qa", "success": True, "completeness": "complete"},
                        {"stage_name": "sheets", "success": True, "completeness": "complete"},
                    ],
                }
            }

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
        self.assertFalse(report["post_rerun_export_blocked"])
        self.assertFalse(report["post_rerun_stale_outputs"])

    def test_execute_reactive_rerun_keeps_exports_blocked_when_impacted_stage_does_not_complete(self) -> None:
        def fake_build(payload):
            return {
                "meta": {
                    "civil_design_readiness": {"production_ready": False},
                    "payload": payload,
                    "stage_results": [
                        {"stage_name": "layout", "success": True, "completeness": "complete"},
                        {"stage_name": "grading", "success": True, "completeness": "complete"},
                    ],
                }
            }

        result = execute_reactive_rerun(
            {"project_name": "Reactive", "meta": {}},
            changed_engine_ids=["roadway_corridor"],
            build_plan_fn=fake_build,
        )

        report = result["reactive_update_report"]

        self.assertTrue(report["post_rerun_export_blocked"])
        self.assertIn("storm_pipes", report["post_rerun_stale_outputs"])
        self.assertIn("exports remain blocked", report["post_rerun_truth"])

    def test_execute_reactive_rerun_does_not_clear_stale_outputs_with_assumed_stages(self) -> None:
        def fake_build(payload):
            return {
                "meta": {
                    "civil_design_readiness": {"production_ready": False},
                    "payload": payload,
                    "stage_results": [
                        {"stage_name": "layout", "success": True, "completeness": "complete"},
                        {"stage_name": "grading", "success": True, "completeness": "assumed"},
                        {"stage_name": "drainage", "success": True, "completeness": "assumed"},
                        {"stage_name": "storm_pipes", "success": True, "completeness": "assumed"},
                    ],
                    "stage_completeness": {
                        "statuses": {
                            "grading": "assumed",
                            "drainage": "assumed",
                            "storm_pipes": "assumed",
                        }
                    },
                }
            }

        result = execute_reactive_rerun(
            {"project_name": "Reactive", "meta": {}},
            changed_engine_ids=["roadway_corridor"],
            build_plan_fn=fake_build,
        )

        report = result["reactive_update_report"]
        self.assertTrue(report["post_rerun_export_blocked"])
        self.assertIn("grading", report["post_rerun_stale_outputs"])
        self.assertIn("storm_pipes", report["post_rerun_stale_outputs"])

    def test_execute_reactive_rerun_blocks_production_ready_when_construction_release_is_stale(self) -> None:
        def fake_build(payload):
            return {
                "meta": {
                    "construction_release_required": True,
                    "civil_design_readiness": {"production_ready": True},
                    "construction_readiness": {"ready": True},
                    "construction_package_manifest": {
                        "release_allowed": False,
                        "construction_package_artifact_status": {
                            "release_ready_flag": True,
                            "stale": ["C-200"],
                            "missing": [],
                            "anonymous": [],
                            "untraced": [],
                            "mismatched": [],
                            "cost_untraced": [],
                            "cost_mismatched": [],
                        },
                    },
                    "payload": payload,
                    "stage_results": [
                        {"stage_name": "layout", "success": True, "completeness": "complete"},
                        {"stage_name": "grading", "success": True, "completeness": "complete"},
                        {"stage_name": "drainage", "success": True, "completeness": "complete"},
                        {"stage_name": "storm_pipes", "success": True, "completeness": "complete"},
                        {"stage_name": "sanitary", "success": True, "completeness": "complete"},
                        {"stage_name": "utility_network", "success": True, "completeness": "complete"},
                        {"stage_name": "coordination_resolution", "success": True, "completeness": "complete"},
                        {"stage_name": "earthwork", "success": True, "completeness": "complete"},
                        {"stage_name": "qa", "success": True, "completeness": "complete"},
                        {"stage_name": "sheets", "success": True, "completeness": "complete"},
                    ],
                }
            }

        result = execute_reactive_rerun(
            {"project_name": "Reactive", "meta": {}},
            changed_engine_ids=["roadway_corridor"],
            build_plan_fn=fake_build,
        )

        report = result["reactive_update_report"]
        self.assertFalse(report["post_rerun_export_blocked"])
        self.assertFalse(report["post_rerun_production_ready"])
        self.assertIn("construction_package_blocked", report["post_rerun_construction_release_blockers"])
        self.assertIn("construction_package_stale_artifacts", report["post_rerun_construction_release_blockers"])
        self.assertIn("construction_package_blocked", report["post_rerun_release_blockers"])
        self.assertIn("construction_package_stale_artifacts", report["post_rerun_release_blockers"])

    def test_execute_reactive_rerun_blocks_production_ready_when_manual_validation_fails(self) -> None:
        def fake_build(payload):
            return {
                "meta": {
                    "civil_design_readiness": {"production_ready": True},
                    "manual_validation": {
                        "failures": [
                            {
                                "code": "MANUAL_STORM_HYDRAULIC_INVALID",
                                "message": "Storm hydraulic review failed.",
                            }
                        ]
                    },
                    "stage_results": [
                        {"stage_name": "layout", "success": True, "completeness": "complete"},
                        {"stage_name": "grading", "success": True, "completeness": "complete"},
                        {"stage_name": "drainage", "success": True, "completeness": "complete"},
                        {"stage_name": "storm_pipes", "success": True, "completeness": "complete"},
                        {"stage_name": "sanitary", "success": True, "completeness": "complete"},
                        {"stage_name": "utility_network", "success": True, "completeness": "complete"},
                        {"stage_name": "coordination_resolution", "success": True, "completeness": "complete"},
                        {"stage_name": "earthwork", "success": True, "completeness": "complete"},
                        {"stage_name": "qa", "success": True, "completeness": "complete"},
                        {"stage_name": "sheets", "success": True, "completeness": "complete"},
                    ],
                }
            }

        result = execute_reactive_rerun(
            {"project_name": "Reactive", "meta": {}},
            changed_engine_ids=["roadway_corridor"],
            build_plan_fn=fake_build,
        )

        report = result["reactive_update_report"]
        self.assertFalse(report["post_rerun_export_blocked"])
        self.assertFalse(report["post_rerun_production_ready"])
        self.assertIn("manual_validation_manual_storm_hydraulic_invalid", report["post_rerun_release_blockers"])

    def test_execute_reactive_rerun_blocks_production_ready_when_deliverables_fail(self) -> None:
        def fake_build(payload):
            return {
                "meta": {
                    "civil_design_readiness": {"production_ready": True},
                    "deliverables": {"failed": ["report"]},
                    "stage_results": [
                        {"stage_name": "layout", "success": True, "completeness": "complete"},
                        {"stage_name": "grading", "success": True, "completeness": "complete"},
                        {"stage_name": "drainage", "success": True, "completeness": "complete"},
                        {"stage_name": "storm_pipes", "success": True, "completeness": "complete"},
                        {"stage_name": "sanitary", "success": True, "completeness": "complete"},
                        {"stage_name": "utility_network", "success": True, "completeness": "complete"},
                        {"stage_name": "coordination_resolution", "success": True, "completeness": "complete"},
                        {"stage_name": "earthwork", "success": True, "completeness": "complete"},
                        {"stage_name": "qa", "success": True, "completeness": "complete"},
                        {"stage_name": "sheets", "success": True, "completeness": "complete"},
                    ],
                }
            }

        result = execute_reactive_rerun(
            {"project_name": "Reactive", "meta": {}},
            changed_engine_ids=["roadway_corridor"],
            build_plan_fn=fake_build,
        )

        report = result["reactive_update_report"]
        self.assertFalse(report["post_rerun_export_blocked"])
        self.assertFalse(report["post_rerun_production_ready"])
        self.assertIn("failed_deliverable_report", report["post_rerun_release_blockers"])


if __name__ == "__main__":
    unittest.main()
