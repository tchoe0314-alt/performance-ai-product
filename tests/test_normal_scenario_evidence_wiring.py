from copy import deepcopy
import unittest

from backend.planning.engine_depth_audit import CLASS_PRODUCTION_DEPTH, run_engine_depth_audit_for_scenario
from backend.planning.engine_readiness import evaluate_engine_readiness
from backend.planning.engineer_review_package import build_engineer_review_package
from backend.planning.export_package_report import build_export_package_report_v1
from backend.planning.production_evidence import build_production_evidence
from tests.test_engine_depth_audit import (
    _complete_storm_hgl_fixture,
    _hgl_egl_depth_plan,
    _review_depth_meta,
    _roadway_grading_depth_plan,
)


class NormalScenarioEvidenceWiringTests(unittest.TestCase):
    def test_normal_roadway_scenario_feeds_accepted_surface_evidence(self) -> None:
        plan = _roadway_grading_depth_plan({"project_name": "normal roadway accepted surface"})
        evidence = build_production_evidence(plan)
        report = run_engine_depth_audit_for_scenario("roadway_corridor", build_plan_fn=_roadway_grading_depth_plan)

        surfaces = evidence["accepted_surfaces"]
        self.assertTrue(surfaces["ready"])
        self.assertEqual(surfaces["existing_surface_id"], "EG-ACCEPTED-1")
        self.assertEqual(surfaces["proposed_surface_id"], "FG-ACCEPTED-1")
        self.assertIn("grading", surfaces["feeds"])
        self.assertIn("roadway_corridor", surfaces["feeds"])
        self.assertTrue(report["scenario_results"][0]["production_evidence_summary"]["accepted_surface_ready"])
        self.assertEqual(report["engine_results"]["grading"]["actual_depth_classification"], CLASS_PRODUCTION_DEPTH)
        self.assertEqual(report["engine_results"]["roadway_corridor"]["actual_depth_classification"], CLASS_PRODUCTION_DEPTH)

    def test_surface_ids_alone_do_not_clear_accepted_surface_evidence(self) -> None:
        evidence = build_production_evidence(
            {
                "meta": {
                    "grading": {
                        "accepted_existing_surface_id": "EG-NOT-ENOUGH",
                        "accepted_proposed_surface_id": "FG-NOT-ENOUGH",
                        "existing_surface": {"id": "EG-NOT-ENOUGH"},
                        "proposed_surface": {"id": "FG-NOT-ENOUGH"},
                    }
                }
            }
        )

        surfaces = evidence["accepted_surfaces"]
        self.assertFalse(surfaces["ready"])
        self.assertFalse(surfaces["accepted_surfaces"])
        self.assertIn("accepted_surfaces", surfaces["missing_inputs"])
        self.assertIn("accepted_surfaces", {item["field"] for item in surfaces["blockers"]})
        self.assertFalse(evidence["production_evidence_ready"])

    def test_normal_storm_scenario_complete_network_inputs_feed_hgl_egl_evidence(self) -> None:
        plan = _hgl_egl_depth_plan({"project_name": "normal storm hgl egl"})
        evidence = build_production_evidence(plan)
        report = run_engine_depth_audit_for_scenario("sloped_detention_site", build_plan_fn=_hgl_egl_depth_plan)

        storm = evidence["storm_hydraulics"]
        self.assertTrue(storm["ready"])
        self.assertGreater(storm["hgl_row_count"], 0)
        self.assertGreater(storm["egl_row_count"], 0)
        self.assertEqual(storm["missing_required_hydraulic_inputs"], [])
        self.assertEqual(report["scenario_results"][0]["production_evidence_summary"]["storm_hgl_row_count"], 2)
        self.assertEqual(report["engine_results"]["storm_pipe"]["actual_depth_classification"], CLASS_PRODUCTION_DEPTH)
        self.assertEqual(report["engine_results"]["hydrology"]["actual_depth_classification"], CLASS_PRODUCTION_DEPTH)

    def test_missing_hydraulic_inputs_emit_exact_storm_blockers(self) -> None:
        storm, drainage = _complete_storm_hgl_fixture()
        storm["target_outfall"].pop("z", None)
        drainage["coordination"]["preferred_outfall"].pop("z", None)
        storm["segments"][0].pop("end_invert_ft")
        storm["segments"][0].pop("slope_ft_ft")
        evidence = build_production_evidence({"meta": {"storm_pipes": storm, "drainage": drainage}})

        missing = evidence["storm_hydraulics"]["missing_required_hydraulic_inputs"]
        self.assertIn("segment.end_invert_ft", missing)
        self.assertIn("tailwater_elev_ft", missing)
        fields = {item["field"] for item in evidence["storm_hydraulics"]["blockers"]}
        self.assertIn("segment.end_invert_ft", fields)
        self.assertIn("tailwater_elev_ft", fields)

    def test_profile_section_evidence_appears_in_export_and_review_packages(self) -> None:
        plan = _roadway_grading_depth_plan({"project_name": "normal profile section export"})
        meta = plan["meta"]
        meta["production_evidence"] = build_production_evidence(plan)

        export = build_export_package_report_v1(plan, export_type="report", generated_at="2026-06-06T00:00:00Z")
        review = build_engineer_review_package(plan)

        self.assertTrue(export["canonical_evidence"]["profile_section"]["profiles"])
        self.assertTrue(export["canonical_evidence"]["profile_section"]["cross_sections"])
        self.assertTrue(review["engine_depth_summary"]["canonical_evidence_present"])
        self.assertEqual(
            review["engine_depth_summary"]["canonical_evidence_version"],
            export["canonical_evidence_version"],
        )
        artifact_ids = {item["artifact_id"] for item in review["calculation_artifacts"]}
        self.assertIn("production_evidence", artifact_ids)

    def test_missing_cost_source_blocks_quantity_production_depth(self) -> None:
        meta = _review_depth_meta()
        meta["cost_estimate"] = {}
        plan = {"meta": meta}
        evidence = build_production_evidence(plan)
        readiness = evaluate_engine_readiness(plan)

        self.assertFalse(evidence["quantity_cost"]["approved_cost_source"])
        self.assertIn("approved_cost_source", {item["field"] for item in evidence["quantity_cost"]["blockers"]})
        quantity = readiness["engines"]["quantity"]
        self.assertEqual(quantity["status"], "concept_ready_needs_production_depth")
        self.assertIn("approved_cost_source", {item["field"] for item in quantity["production_blockers"]})

    def test_reactive_dirty_evidence_flows_to_audit_and_readiness(self) -> None:
        def dirty_plan(payload: dict) -> dict:
            plan = _roadway_grading_depth_plan(payload)
            plan["meta"]["system_dirty_state"] = {
                "grading": {
                    "state": "dirty",
                    "reasons": ["Accepted surface edit invalidated grading."],
                    "source": "test_reactive_dirty",
                }
            }
            plan["meta"]["reactive_update_report"] = {
                "post_rerun_release_blockers": ["grading_dirty_after_edit"],
                "post_rerun_production_ready": False,
            }
            plan["meta"]["production_evidence"] = build_production_evidence(plan)
            plan["meta"]["engine_readiness"] = evaluate_engine_readiness(plan)
            return plan

        plan = dirty_plan({"project_name": "normal reactive dirty"})
        evidence = plan["meta"]["production_evidence"]
        readiness = plan["meta"]["engine_readiness"]
        report = run_engine_depth_audit_for_scenario("roadway_corridor", build_plan_fn=dirty_plan)

        self.assertEqual(evidence["reactive_dirty_state"]["dirty_state"][0]["stage"], "grading")
        self.assertEqual(readiness["engines"]["reactive_model"]["status"], "concept_ready_needs_production_depth")
        self.assertGreater(report["scenario_results"][0]["production_evidence_summary"]["reactive_dirty_count"], 0)

    def test_construction_release_remains_blocked_without_external_gates(self) -> None:
        plan = _hgl_egl_depth_plan({"project_name": "normal review only storm"})
        plan["meta"]["production_evidence"] = build_production_evidence(plan)
        export = build_export_package_report_v1(plan, export_type="report", generated_at="2026-06-06T00:00:00Z")
        review = build_engineer_review_package(plan)

        self.assertFalse(export["construction_release_allowed"])
        self.assertTrue(export["construction_release_blocked"])
        self.assertFalse(review["ready_for_construction"])
        self.assertFalse(review["construction_release_allowed"])
        self.assertTrue(review["external_engineer_approval"]["required"])
        self.assertIn("external_engineer_approval_record", {item["field"] for item in review["missing_inputs"]})


if __name__ == "__main__":
    unittest.main()
