import unittest

from backend.planning.reactive_model import (
    build_reactive_change_evidence,
    build_reactive_update_report,
    execute_reactive_rerun,
    reactive_report_from_plan,
    validate_reactive_model_depth,
)


class ReactiveModelContractTests(unittest.TestCase):
    def test_site_change_marks_downstream_systems_dirty_with_no_stage_skips(self) -> None:
        report = build_reactive_change_evidence(
            change_type="site",
            changed_object_id="SITE-1",
            canonical_revision_before="REV-1",
            canonical_revision_after="REV-2",
        )

        self.assertEqual(report["expected_dirty_stages"], [
            "layout",
            "grading",
            "drainage",
            "storm_pipes",
            "sanitary",
            "utility_network",
            "coordination_resolution",
            "earthwork",
            "sheets",
            "qa",
        ])
        self.assertEqual(report["expected_skipped_stages"], [])
        self.assertTrue(report["export_blocked"])
        self.assertIn("stale_outputs_block_export", report["blockers"])

    def test_building_change_marks_expected_systems_and_skips_unrelated(self) -> None:
        report = build_reactive_change_evidence(
            change_type="building",
            changed_object_id="BLDG-1",
            canonical_revision_before="REV-1",
            canonical_revision_after="REV-2",
        )

        self.assertEqual(report["expected_dirty_engine_ids"], ["grading", "drainage", "water", "utility_coordination", "quantity"])
        self.assertEqual(report["expected_dirty_stages"], ["grading", "drainage", "utility_network", "coordination_resolution", "qa"])
        self.assertIn("storm_pipe", report["expected_skipped_engine_ids"])
        self.assertIn("profile_section", report["expected_skipped_engine_ids"])
        self.assertNotIn("storm_pipes", report["actual_dirty_stages"])
        skipped = {row["system"]: row for row in report["skipped_system_checks"]}
        self.assertEqual(skipped["storm_pipe"]["expected"], "skipped")
        self.assertTrue(skipped["storm_pipe"]["valid"])

    def test_basin_change_marks_drainage_storm_and_quantity_only(self) -> None:
        report = build_reactive_change_evidence(
            change_type="basin",
            changed_object_id="BASIN-1",
            canonical_revision_before="REV-1",
            canonical_revision_after="REV-2",
        )

        self.assertEqual(report["expected_dirty_engine_ids"], ["drainage", "storm_pipe", "hydrology", "quantity"])
        self.assertEqual(report["expected_dirty_stages"], ["drainage", "storm_pipes", "qa"])
        self.assertIn("grading", report["expected_skipped_engine_ids"])
        self.assertIn("utility_network", report["expected_skipped_stages"])

    def test_road_change_marks_corridor_profile_and_utility_chain(self) -> None:
        report = build_reactive_change_evidence(
            change_type="road",
            changed_object_id="ROAD-1",
            canonical_revision_before="REV-1",
            canonical_revision_after="REV-2",
        )

        self.assertEqual(
            report["expected_dirty_engine_ids"],
            ["grading", "drainage", "water", "utility_coordination", "roadway_corridor", "profile_section", "quantity"],
        )
        self.assertEqual(
            report["expected_dirty_stages"],
            ["layout", "grading", "drainage", "utility_network", "coordination_resolution", "sheets", "qa"],
        )
        self.assertIn("storm_pipe", report["expected_skipped_engine_ids"])
        self.assertIn("storm_pipes", report["expected_skipped_stages"])

    def test_utility_change_marks_coordination_profiles_and_quantity(self) -> None:
        report = build_reactive_change_evidence(
            change_type="utility",
            changed_object_id="W-1",
            canonical_revision_before="REV-1",
            canonical_revision_after="REV-2",
        )

        self.assertEqual(report["expected_dirty_engine_ids"], ["water", "utility_coordination", "profile_section", "quantity"])
        self.assertEqual(report["expected_dirty_stages"], ["utility_network", "coordination_resolution", "sheets", "qa"])
        self.assertIn("grading", report["expected_skipped_engine_ids"])
        self.assertIn("drainage", report["expected_skipped_stages"])

    def test_reactive_depth_passes_after_expected_partial_rerun_completion(self) -> None:
        evidence = build_reactive_change_evidence(
            change_type="road",
            changed_object_id="ROAD-1",
            canonical_revision_before="REV-1",
            canonical_revision_after="REV-2",
            completed_stages=["layout", "grading", "drainage", "utility_network", "coordination_resolution", "sheets", "qa"],
        )

        result = validate_reactive_model_depth({"meta": {"reactive_model_evidence": evidence}})

        self.assertTrue(result["production_ready"])
        self.assertEqual(evidence["stale_outputs"], [])
        self.assertFalse(evidence["export_blocked"])
        self.assertIn("affected/skipped expected-actual checks", result["evidence"])

    def test_reactive_depth_blocks_missing_report_and_stale_outputs(self) -> None:
        missing = validate_reactive_model_depth({"meta": {}})
        stale = build_reactive_change_evidence(
            change_type="basin",
            changed_object_id="BASIN-1",
            canonical_revision_before="REV-1",
            canonical_revision_after="REV-2",
        )
        stale_result = validate_reactive_model_depth({"meta": {"reactive_model_evidence": stale}})

        self.assertFalse(missing["production_ready"])
        self.assertIn("Reactive model depth needs a dependency-aware reactive update report.", missing["blockers"])
        self.assertFalse(stale_result["production_ready"])
        self.assertIn("Reactive model depth needs completed affected reruns before production-depth status.", stale_result["blockers"])
        self.assertIn("stale output blocking", stale_result["evidence"])

    def test_roadway_change_marks_downstream_engines_and_stages(self) -> None:
        report = build_reactive_update_report(changed_engine_ids=["roadway_corridor"])

        self.assertIn("grading", report["impacted_engine_ids"])
        self.assertIn("storm_pipes", report["impacted_stages"])
        self.assertIn("qa", report["impacted_stages"])
        self.assertFalse(report["export_blocked"])
        self.assertTrue(report["export_blocked_before_rerun"])
        self.assertTrue(report["export_requires_current_downstream"])
        self.assertTrue(report["partial_rerun_supported"])
        impact_by_stage = {item["stage"]: item for item in report["impact_matrix"]}
        self.assertIn("mapped_from_changed_engine:roadway_corridor", impact_by_stage["layout"]["reason_codes"])
        self.assertIn("downstream_of_engine:roadway_corridor", impact_by_stage["storm_pipes"]["reason_codes"])
        self.assertTrue(impact_by_stage["storm_pipes"]["export_blocking_until_complete"])

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

    def test_execute_reactive_rerun_uses_partial_executor_when_available(self) -> None:
        partial_payloads = []

        def full_build(_payload):
            raise AssertionError("full build should not be called when partial executor is available")

        def partial_build(payload):
            partial_payloads.append(payload)
            return {
                "meta": {
                    "civil_design_readiness": {"production_ready": True},
                    "stage_results": [
                        {"stage_name": "grading", "success": True, "completeness": "complete"},
                        {"stage_name": "drainage", "success": True, "completeness": "complete"},
                        {"stage_name": "storm_pipes", "success": True, "completeness": "complete"},
                        {"stage_name": "sanitary", "success": True, "completeness": "complete"},
                        {"stage_name": "utility_network", "success": True, "completeness": "complete"},
                        {"stage_name": "coordination_resolution", "success": True, "completeness": "complete"},
                        {"stage_name": "earthwork", "success": True, "completeness": "complete"},
                        {"stage_name": "sheets", "success": True, "completeness": "complete"},
                        {"stage_name": "qa", "success": True, "completeness": "complete"},
                    ],
                }
            }

        result = execute_reactive_rerun(
            {"project_name": "Reactive", "meta": {}},
            changed_stages=["grading"],
            build_plan_fn=full_build,
            partial_rerun_fn=partial_build,
        )

        report = result["reactive_update_report"]
        self.assertTrue(report["partial_rerun_executed"])
        self.assertEqual(report["execution_mode"], "isolated_downstream_partial_rerun")
        self.assertFalse(report["post_rerun_export_blocked"])
        self.assertIn("isolated downstream partial rerun", result["truth_label"])
        status_by_stage = {item["stage"]: item for item in report["post_rerun_stage_status"]}
        self.assertTrue(status_by_stage["grading"]["completed"])
        self.assertFalse(status_by_stage["grading"]["stale_after_rerun"])
        self.assertIn("layout", report["affected_system_report"]["unaffected_stages"])
        self.assertEqual(len(partial_payloads), 1)
        dirty_state = partial_payloads[0]["meta"]["system_dirty_state"]
        self.assertEqual(dirty_state["grading"]["state"], "dirty")
        self.assertIn("storm_pipes", dirty_state)

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
        status_by_stage = {item["stage"]: item for item in report["post_rerun_stage_status"]}
        self.assertTrue(status_by_stage["storm_pipes"]["stale_after_rerun"])
        self.assertTrue(status_by_stage["storm_pipes"]["export_blocking"])

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
        release_detail = next(
            item
            for item in report["post_rerun_release_blocker_details"]
            if item["code"] == "construction_package_blocked"
        )
        construction_detail = next(
            item
            for item in report["post_rerun_construction_release_blocker_details"]
            if item["code"] == "construction_package_blocked"
        )
        self.assertEqual(release_detail["what_failed"], "The construction package is not allowed for release.")
        self.assertTrue(construction_detail["next_action"])

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

    def test_execute_reactive_rerun_blocks_production_ready_when_deliverables_are_missing(self) -> None:
        def fake_build(payload):
            return {
                "meta": {
                    "civil_design_readiness": {"production_ready": True},
                    "deliverables": {"requested": ["site_plan", "report"], "produced": ["site_plan"]},
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
        self.assertFalse(report["post_rerun_production_ready"])
        self.assertIn("missing_deliverable_report", report["post_rerun_release_blockers"])

    def test_execute_reactive_rerun_blocks_release_review_missing_deliverables(self) -> None:
        def fake_build(payload):
            return {
                "meta": {
                    "civil_design_readiness": {"production_ready": True},
                    "release_review": {
                        "requested_deliverables": ["site_plan", "report"],
                        "produced_deliverables": ["site_plan"],
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
        self.assertFalse(report["post_rerun_production_ready"])
        self.assertIn("missing_deliverable_report", report["post_rerun_release_blockers"])

    def test_execute_reactive_rerun_blocks_stored_run_errors(self) -> None:
        def fake_build(payload):
            return {
                "meta": {
                    "civil_design_readiness": {"production_ready": True},
                    "run_summary": {"success": False, "error_count": 1},
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
        self.assertFalse(report["post_rerun_production_ready"])
        self.assertIn("planner_run_failed", report["post_rerun_release_blockers"])
        self.assertIn("planner_errors_present", report["post_rerun_release_blockers"])


if __name__ == "__main__":
    unittest.main()
