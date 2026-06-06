from copy import deepcopy
import tempfile
import unittest
from pathlib import Path

from backend.application.artifact_workflows import export_report_artifact
from backend.application.design_workflows import build_run_summary
from backend.application.project_workflows import save_project_record
from backend.planning.engine_depth_audit import CLASS_PRODUCTION_DEPTH, run_engine_depth_audit_for_scenario
from backend.planning.engine_readiness import evaluate_engine_readiness
from backend.planning.engineer_review_package import build_engineer_review_package
from backend.planning.export_package_report import build_export_package_report_v1
from backend.planning.production_evidence import build_production_evidence
from core.civil_design import civil_design_readiness
from backend.planning.production_depth import enrich_storm_production_depth
from tests.test_engine_depth_audit import (
    _complete_storm_hgl_fixture,
    _complete_roadway_grading_fixture_meta,
    _hgl_egl_depth_plan,
    _review_depth_meta,
    _roadway_grading_depth_plan,
)


class _ScenarioProjectStore:
    def __init__(self) -> None:
        self.project = {
            "user_id": "u1",
            "project_id": "chat15-alpha",
            "name": "Chat 15 Blank Project",
            "description": "",
            "session_id": None,
            "tags": [],
            "project_input": {},
            "latest_result": {},
            "session_state": {},
            "metadata": {},
        }
        self.saved_payloads = []

    def get_project(self, *, user_id: str, project_id: str):
        if user_id == self.project.get("user_id") and project_id == self.project.get("project_id"):
            return deepcopy(self.project)
        return None

    def save_project(self, **kwargs):
        self.saved_payloads.append(deepcopy(kwargs))
        self.project = {
            "user_id": kwargs["user_id"],
            "project_id": kwargs["project_id"],
            "name": kwargs["name"],
            "description": kwargs["description"],
            "session_id": kwargs["session_id"],
            "tags": kwargs["tags"],
            "project_input": kwargs["project_input"],
            "latest_result": kwargs["latest_result"],
            "session_state": kwargs["session_state"],
            "metadata": kwargs["metadata"],
        }
        return deepcopy(self.project)


class _ScenarioArtifactService:
    def __init__(self) -> None:
        self.report_export = {}

    def export_report_json(self, *, user_id, result_data, stem=None):
        self.report_export = {"user_id": user_id, "result_data": deepcopy(result_data), "stem": stem}
        path = Path(tempfile.gettempdir()) / "chat15-alpha-report.json"
        path.write_text("{}", encoding="utf-8")
        return path


def _chat15_alpha_plan(payload: dict) -> dict:
    attach_audit = payload.get("attach_audit", True)
    meta = _review_depth_meta()
    fixture = _complete_roadway_grading_fixture_meta()
    meta.update(fixture)
    storm, drainage = _complete_storm_hgl_fixture()
    lot = dict(payload.get("lot") or {"x": 0.0, "y": 0.0, "w": 875.0, "h": 700.0, "area_sf": 612500.0})
    lot.setdefault("x", 0.0)
    lot.setdefault("y", 0.0)
    lot.setdefault("area_sf", float(lot.get("w") or 0.0) * float(lot.get("h") or 0.0))
    meta.update(
        {
            "project_id": payload.get("project_id", "chat15-alpha"),
            "source_project_id": payload.get("project_id", "chat15-alpha"),
            "canonical_model_id": "canon-chat15-alpha",
            "canonical_model_hash": "hash-chat15-alpha-001",
            "canonical_revision": "rev-chat15-alpha-001",
            "ready_language": "ready_for_engineer_review",
            "construction_release_allowed": False,
            "site_locked": True,
            "site_boundary": {"id": "SITE-CHAT15", **lot, "locked": True},
            "site": {"lot": lot, "locked": True},
            "lot": lot,
            "building_count": 4,
            "parking_count": 180,
            "parking_program": {"stall_count": 180},
            "alignments": [{"id": "ALG-LOOP-1", "type": "internal_loop_road", "length_ft": 620.0}],
            "layout": {"success": True, "objects": ["SITE-CHAT15", "BLDG-1", "BLDG-2", "BLDG-3", "RETAIL-1", "PARK-1", "BASIN-1"]},
            "drainage": drainage,
            "storm_pipes": enrich_storm_production_depth(storm, drainage),
            "sanitary": {
                "success": True,
                "segments": [{"id": "SAN-1", "from": "MH-1", "to": "MH-2", "length_ft": 260.0, "slope_ft_ft": 0.01}],
            },
            "utilities": {
                "success": True,
                "segments": [{"id": "WAT-1", "type": "water", "length_ft": 410.0}],
                "conflict_hooks": {"utility_segments": [{"id": "WAT-1"}]},
            },
            "coordination": {
                "success": True,
                "detected_conflicts": 0,
                "resolved_conflicts": [],
                "unresolved_conflicts": [],
            },
            "deliverables": {
                "requested": ["site_plan", "grading_plan", "drainage_plan", "storm_pipe_plan", "utility_plan", "report", "engineer_review_package"],
                "produced": ["site_plan", "grading_plan", "drainage_plan", "storm_pipe_plan", "utility_plan", "report", "engineer_review_package"],
                "failed": [],
            },
            "stage_completeness": {
                "statuses": {
                    "layout": "complete",
                    "grading": "complete",
                    "drainage": "complete",
                    "storm_pipes": "complete",
                    "sanitary": "complete",
                    "utility_network": "complete",
                    "coordination_resolution": "complete",
                    "qa": "complete",
                }
            },
        }
    )
    meta["quantities"]["totals"].update(
        {
            "lot_area_sf": float(lot["area_sf"]),
            "estimated_parking_stalls": 180,
            "pipe_length_ft": 100.0,
        }
    )
    meta["quantities"]["explain"]["quantity_audit"].update(
        {
            "pipe_length_ft": {"source_object_ids": ["STM-HGL-1"]},
            "roadway_area_sf": {"source_object_ids": ["ALG-LOOP-1"]},
            "utility_length_ft": {"source_object_ids": ["WAT-1", "SAN-1"]},
        }
    )
    plan = {
        "project_id": payload.get("project_id", "chat15-alpha"),
        "project_name": payload.get("project_name", "Chat 15 End-to-End Alpha Scenario"),
        "units": "ft",
        "actions": [
            {"task": "rectangle", "layer": "SITE", "canonical_source_type": "site", "canonical_source_id": "SITE-CHAT15", "x": 0, "y": 0, "w": lot["w"], "h": lot["h"]},
            {"task": "rectangle", "layer": "BUILDING", "canonical_source_type": "building", "canonical_source_id": "BLDG-1", "x": 120, "y": 120, "w": 110, "h": 58},
            {"task": "rectangle", "layer": "BUILDING", "canonical_source_type": "building", "canonical_source_id": "BLDG-2", "x": 270, "y": 120, "w": 110, "h": 58},
            {"task": "rectangle", "layer": "BUILDING", "canonical_source_type": "building", "canonical_source_id": "BLDG-3", "x": 420, "y": 120, "w": 110, "h": 58},
            {"task": "rectangle", "layer": "BUILDING", "canonical_source_type": "retail", "canonical_source_id": "RETAIL-1", "x": 130, "y": 450, "w": 70, "h": 45},
            {"task": "polyline", "layer": "ROAD", "canonical_source_type": "road_alignment", "canonical_source_id": "ALG-LOOP-1", "points": [[80, 80], [680, 80], [680, 560], [80, 560], [80, 80]]},
            {"task": "rectangle", "layer": "PARKING", "canonical_source_type": "parking", "canonical_source_id": "PARK-1", "x": 240, "y": 430, "w": 260, "h": 120},
            {"task": "rectangle", "layer": "BASIN_BOUNDARY", "canonical_source_type": "detention_basin", "canonical_source_id": "BASIN-1", "x": 650, "y": 545, "w": 130, "h": 110},
            {"task": "polyline", "layer": "STORM", "canonical_source_type": "storm_pipe_segment", "canonical_source_id": "STM-HGL-1", "points": [[620, 500], [710, 590]]},
            {"task": "polyline", "layer": "SAN", "canonical_source_type": "sanitary_segment", "canonical_source_id": "SAN-1", "points": [[120, 80], [540, 80]]},
            {"task": "polyline", "layer": "WATER", "canonical_source_type": "water_segment", "canonical_source_id": "WAT-1", "points": [[90, 110], [660, 110]]},
        ],
        "meta": meta,
    }
    meta["production_evidence"] = build_production_evidence(plan)
    meta["civil_design_readiness"] = civil_design_readiness(plan)
    meta["engine_readiness"] = evaluate_engine_readiness(plan)
    meta["export_package_report_v1"] = build_export_package_report_v1(plan, export_type="report", generated_at="2026-06-06T00:00:00Z")
    meta["engineer_review_package_v1"] = build_engineer_review_package(plan)
    if attach_audit:
        meta["engine_depth_audit_report_v1"] = run_engine_depth_audit_for_scenario(
            "mixed_use_14_acre_site",
            build_plan_fn=lambda audit_payload: _chat15_alpha_plan({**audit_payload, "attach_audit": False}),
        )
    return plan


class NormalScenarioEvidenceWiringTests(unittest.TestCase):
    def test_chat15_end_to_end_alpha_scenario_from_blank_project(self) -> None:
        store = _ScenarioProjectStore()
        service = _ScenarioArtifactService()
        self.assertEqual(store.project["latest_result"], {})

        plan = _chat15_alpha_plan(
            {
                "project_id": "chat15-alpha",
                "project_name": "Chat 15 End-to-End Alpha Scenario",
                "lot": {"x": 0.0, "y": 0.0, "w": 875.0, "h": 700.0, "area_sf": 612500.0},
            }
        )
        result = {
            "success": True,
            "message": "ready_for_engineer_review; construction_release_allowed=false",
            "parsed_payload": {
                "project_name": plan["project_name"],
                "lot": plan["meta"]["lot"],
                "site_locked": True,
            },
            "final_plan": plan,
            "warnings": [],
            "errors": [],
            "issues": [],
            "assumptions": ["Deterministic alpha scenario uses labeled review fixtures for traceability, not construction approval."],
        }

        saved = save_project_record(
            project_store=store,
            user_id="u1",
            payload_data={
                "project_id": "chat15-alpha",
                "name": "Chat 15 End-to-End Alpha Scenario",
                "project_input": {"started_from_blank_project": True, "site_boundary_locked": True},
                "latest_result": result,
            },
            build_run_summary=build_run_summary,
        )
        report_path = export_report_artifact(
            artifact_service=service,
            project_store=store,
            user_id="u1",
            project_id="chat15-alpha",
            result_data=store.project["latest_result"],
            filename_stem="chat15-alpha-report",
        )

        exported_plan = service.report_export["result_data"]["final_plan"]
        exported_meta = exported_plan["meta"]
        export_report = exported_meta["export_package_report_v1"]
        review_package = exported_meta["engineer_review_package_v1"]
        audit_report = exported_meta["engine_depth_audit_report_v1"]

        self.assertEqual(report_path.name, "chat15-alpha-report.json")
        self.assertTrue(saved["success"])
        self.assertTrue(exported_meta["site_locked"])
        self.assertEqual(export_report["source"], "export_package_report_v1")
        self.assertEqual(review_package["version"], "engineer_review_package_v1")
        self.assertEqual(audit_report["version"], "engine_depth_audit_report_v1")
        self.assertEqual(review_package["ready_language"], "ready_for_engineer_review")
        self.assertFalse(export_report["construction_release_allowed"])
        self.assertFalse(review_package["construction_release_allowed"])
        self.assertFalse(audit_report["construction_release_allowed"])
        self.assertFalse(exported_meta["construction_release_allowed"])
        self.assertTrue(review_package["external_engineer_approval"]["required"])
        self.assertGreaterEqual(len(exported_plan["actions"]), 10)
        self.assertIn("report", exported_meta["deliverables"]["produced"])
        self.assertIn("engineer_review_package", exported_meta["deliverables"]["produced"])
        self.assertIn("mixed_use_14_acre_site", [row["scenario_id"] for row in audit_report["scenario_results"]])
        self.assertEqual(
            store.project["metadata"]["workflow"]["summary"]["latest_run_source"],
            "project_save",
        )
        self.assertEqual(
            store.project["metadata"]["workflow"]["artifacts"][0]["kind"],
            "report",
        )

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
