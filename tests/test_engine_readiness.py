import unittest

import planner
from backend.planning.engine_contracts import engine_contracts
from backend.planning.engine_readiness import evaluate_engine_readiness
from tests.test_civil_design_readiness import _complete_meta, _production_ready_meta


class EngineReadinessTests(unittest.TestCase):
    def test_engine_readiness_reports_every_contract(self) -> None:
        readiness = evaluate_engine_readiness({"meta": _complete_meta()})

        self.assertEqual(readiness["engine_count"], len(engine_contracts()))
        self.assertEqual(set(readiness["engines"].keys()), {contract.engine_id for contract in engine_contracts()})
        self.assertIn("storm_pipe", readiness["engines"])
        self.assertIn("water", readiness["engines"])
        self.assertIn("export_cad", readiness["engines"])

    def test_concept_plan_is_not_falsely_marked_production_ready(self) -> None:
        readiness = evaluate_engine_readiness({"meta": _complete_meta()})

        self.assertFalse(readiness["production_ready"])
        self.assertIn("storm_pipe", readiness["production_blocked_engine_ids"])
        self.assertIn("export_cad", readiness["production_blocked_engine_ids"])
        self.assertIn("gis_existing_conditions", readiness["production_blocked_engine_ids"])
        self.assertIn("structure", readiness["not_applicable_engine_ids"])
        self.assertIn("coordinate_system", {item["field"] for item in readiness["engines"]["gis_existing_conditions"]["production_blockers"]})
        storm = readiness["engines"]["storm_pipe"]
        self.assertEqual(storm["status"], "concept_ready_needs_production_depth")
        self.assertEqual(storm["review_state"], "needs_review")
        self.assertIn("storm_depth", {item["area"] for item in storm["production_blockers"]})
        self.assertEqual(readiness["review_state"], "needs_review")
        alpha = readiness["summary"]["alpha_readiness"]
        self.assertEqual(alpha["status"], "needs_review")
        self.assertIn("storm_pipe", alpha["needs_review_engine_ids"])
        self.assertTrue(alpha["top_issues"][0]["first_failing_layer"])
        self.assertTrue(alpha["top_issues"][0]["next_action"])
        self.assertTrue(storm["production_blockers"])
        self.assertTrue(storm["production_gate_status"])

    def test_production_depth_fixture_clears_engine_readiness_contracts(self) -> None:
        readiness = evaluate_engine_readiness({"meta": _production_ready_meta()})

        self.assertTrue(readiness["production_ready"])
        self.assertEqual(readiness["review_state"], "ready")
        self.assertEqual(readiness["not_evidenced_engine_ids"], [])
        self.assertEqual(readiness["blocked_engine_ids"], [])
        self.assertEqual(readiness["production_blocked_engine_ids"], [])
        self.assertIn("structure", readiness["not_applicable_engine_ids"])
        self.assertIn("orchestration_outputs", readiness["engines"]["ai_orchestration"]["evidence"])

    def test_missing_core_truth_blocks_impacted_engines(self) -> None:
        readiness = evaluate_engine_readiness({"meta": {"grading": {"source_quality": "fallback"}}})

        self.assertIn("grading", readiness["blocked_engine_ids"])
        self.assertEqual(readiness["review_state"], "blocked")
        self.assertEqual(readiness["engines"]["grading"]["review_state"], "blocked")
        self.assertIn("drainage", readiness["blocked_engine_ids"])
        self.assertIn("storm_pipe", readiness["blocked_engine_ids"])
        self.assertIn("sanitary", readiness["blocked_engine_ids"])
        self.assertIn("qa_validation", readiness["blocked_engine_ids"])
        self.assertFalse(readiness["production_ready"])
        alpha = readiness["summary"]["alpha_readiness"]
        self.assertEqual(alpha["status"], "blocked")
        self.assertIn("grading", alpha["blocked_engine_ids"])
        grading_issue = next(item for item in alpha["top_issues"] if item["engine_id"] == "grading")
        self.assertTrue(grading_issue["what_failed"])
        self.assertTrue(grading_issue["engineer_review_required"])

    def test_build_plan_attaches_engine_readiness(self) -> None:
        plan = planner.build_plan(
            {
                "project_name": "Engine Readiness Smoke",
                "units": "ft",
                "mode": "site_plan",
                "lot": {"x": 0.0, "y": 0.0, "w": 120.0, "h": 100.0},
                "site_plan": {"building_width": 40.0, "building_depth": 30.0, "parking_count": 12},
            }
        )
        readiness = (plan.get("meta") or {}).get("engine_readiness") or {}

        self.assertEqual(readiness.get("engine_count"), 20)
        self.assertFalse(readiness.get("production_ready"))
        self.assertIn("engines", readiness)
        self.assertIn("most_important_backend_gaps", readiness.get("summary") or {})

    def test_depth_validation_blockers_feed_engine_readiness(self) -> None:
        readiness = evaluate_engine_readiness(
            {
                "meta": {
                    **_complete_meta(),
                    "depth_validation": {
                        "stormwater": {
                            "production_ready": False,
                            "blockers": ["Storm depth needs HGL and EGL profiles."],
                        }
                    },
                }
            }
        )

        storm = readiness["engines"]["storm_pipe"]
        self.assertEqual(storm["status"], "concept_ready_needs_production_depth")
        self.assertIn("storm_depth", {item["area"] for item in storm["production_blockers"]})
        detail = next(item for item in storm["production_blocker_details"] if item.get("area") == "storm_depth")
        self.assertEqual(detail["area"], "storm_depth")
        self.assertEqual(detail["field"], "depth_validation")
        self.assertTrue(detail["what_failed"])
        self.assertTrue(detail["next_action"])
        self.assertTrue(detail["engineer_review_required"])

    def test_hydrology_uses_storm_depth_blockers_for_hydraulic_evidence(self) -> None:
        readiness = evaluate_engine_readiness({"meta": _complete_meta()})

        hydrology = readiness["engines"]["hydrology"]
        self.assertEqual(hydrology["status"], "concept_ready_needs_production_depth")
        self.assertIn("hydrology_depth", {item["area"] for item in hydrology["production_blockers"]})
        messages = {item["message"] for item in hydrology["production_blockers"] if item.get("area") == "hydrology_depth"}
        self.assertIn("Storm depth needs HGL and EGL profiles from production hydraulic evidence.", messages)
        self.assertIn("Storm depth needs tailwater/backwater evidence.", messages)

    def test_profile_section_depth_blockers_feed_engine_readiness(self) -> None:
        readiness = evaluate_engine_readiness(
            {
                "meta": {
                    **_complete_meta(),
                    "alignments": [{"id": "ALG-1", "name": "Road A", "points": [[0.0, 0.0], [100.0, 0.0]]}],
                    "profiles": [{"name": "Road Profile", "alignment_id": "ALG-MISSING", "stations": [{"station_ft": 0.0}, {"station_ft": 100.0}]}],
                    "cross_sections": [{"name": "Road Section", "alignment_id": "ALG-1", "station_ft": 50.0, "samples": [{"offset_ft": -10.0}, {"offset_ft": 0.0}, {"offset_ft": 10.0}]}],
                }
            }
        )

        profile_section = readiness["engines"]["profile_section"]
        self.assertEqual(profile_section["status"], "concept_ready_needs_production_depth")
        self.assertIn("profile_section_depth", {item["area"] for item in profile_section["production_blockers"]})
        messages = {item["message"] for item in profile_section["production_blockers"]}
        self.assertIn("Profile/section depth needs every profile to trace a canonical alignment ID.", messages)
        self.assertIn("Profile/section depth needs accepted existing/proposed surface IDs.", messages)

    def test_profile_section_depth_evidence_can_clear_profile_section_engine(self) -> None:
        readiness = evaluate_engine_readiness({"meta": _production_ready_meta()})

        profile_section = readiness["engines"]["profile_section"]
        self.assertEqual(profile_section["status"], "production_ready")
        self.assertIn("depth_validation", profile_section["evidence"])
        self.assertFalse(profile_section["production_blockers"])

    def test_failed_truth_gates_block_qa_engine_readiness(self) -> None:
        readiness = evaluate_engine_readiness(
            {
                "meta": {
                    **_complete_meta(),
                    "truth_audit": {"success": False, "summary": {"failing_checks": 1}},
                    "manual_validation": {"success": False, "failures": [{"code": "MANUAL_STORM_GRAPH_INVALID"}]},
                }
            }
        )

        qa = readiness["engines"]["qa_validation"]
        fields = {item["field"] for item in qa["production_blockers"]}
        self.assertEqual(qa["status"], "concept_ready_needs_production_depth")
        self.assertIn("truth_audit", fields)
        self.assertIn("manual_validation", fields)
        detail_fields = {item["field"] for item in qa["production_blocker_details"]}
        self.assertIn("truth_audit", detail_fields)
        self.assertIn("manual_validation", detail_fields)

    def test_quantity_trace_gaps_block_quantity_engine_readiness(self) -> None:
        readiness = evaluate_engine_readiness(
            {
                "meta": {
                    **_complete_meta(),
                    "quantities": {
                        "success": False,
                        "totals": {"pipe_length_ft": 120.0},
                        "explain": {
                            "meta_summary": {"quantity_traceability_complete": False},
                            "trace_gaps": {"pipe_length_ft": {"value": 120.0}},
                        },
                    },
                }
            }
        )

        quantity = readiness["engines"]["quantity"]
        fields = {item["field"] for item in quantity["production_blockers"]}
        self.assertEqual(quantity["status"], "concept_ready_needs_production_depth")
        self.assertIn("quantity_success", fields)
        self.assertIn("quantity_traceability", fields)
        self.assertIn("trace_gaps", fields)

    def test_stale_reactive_report_blocks_reactive_engine_readiness(self) -> None:
        readiness = evaluate_engine_readiness(
            {
                "meta": {
                    **_complete_meta(),
                    "stage_results": {"grading": {"completed": True}},
                    "reactive_update_report": {
                        "export_blocked": True,
                        "post_rerun_stale_outputs": ["drainage", "storm_pipes"],
                    },
                }
            }
        )

        reactive = readiness["engines"]["reactive_model"]
        self.assertEqual(reactive["status"], "concept_ready_needs_production_depth")
        self.assertIn("stale_outputs", {item["field"] for item in reactive["production_blockers"]})

    def test_release_blocked_reactive_report_blocks_reactive_engine_readiness(self) -> None:
        readiness = evaluate_engine_readiness(
            {
                "meta": {
                    **_complete_meta(),
                    "stage_results": {"grading": {"completed": True}},
                    "reactive_update_report": {
                        "export_blocked": False,
                        "post_rerun_stale_outputs": [],
                        "post_rerun_production_ready": False,
                        "post_rerun_release_blockers": ["manual_validation_manual_storm_hydraulic_invalid"],
                    },
                }
            }
        )

        reactive = readiness["engines"]["reactive_model"]
        self.assertEqual(reactive["status"], "concept_ready_needs_production_depth")
        self.assertIn("post_rerun_release_blockers", {item["field"] for item in reactive["production_blockers"]})

    def test_missing_reactive_depth_report_blocks_reactive_engine_readiness_at_review_depth(self) -> None:
        meta = _complete_meta()
        meta["stage_results"] = [{"stage_name": "grading", "success": True, "completeness": "complete"}]

        readiness = evaluate_engine_readiness({"meta": meta})

        reactive = readiness["engines"]["reactive_model"]
        self.assertEqual(reactive["status"], "concept_ready_needs_production_depth")
        self.assertIn("reactive_model_depth", {item["area"] for item in reactive["production_blockers"]})
        self.assertIn("Reactive model depth needs a dependency-aware reactive update report.", {item["message"] for item in reactive["production_blockers"]})

    def test_structure_engine_is_not_applicable_without_structure_scope(self) -> None:
        readiness = evaluate_engine_readiness({"meta": _complete_meta()})

        structure = readiness["engines"]["structure"]

        self.assertEqual(structure["status"], "not_applicable")
        self.assertFalse(structure["scope_required"])
        self.assertIn("scope_not_required", structure["evidence"])
        self.assertEqual({gate["status"] for gate in structure["production_gate_status"]}, {"not_applicable"})
        self.assertIn("structure", readiness["not_applicable_engine_ids"])
        self.assertNotIn("structure", readiness["not_evidenced_engine_ids"])
        self.assertFalse(readiness["production_ready"])

    def test_unresolved_structure_conflicts_block_structure_engine_readiness(self) -> None:
        readiness = evaluate_engine_readiness(
            {
                "meta": {
                    **_complete_meta(),
                    "structure_conflicts": [{"id": "SC-1", "status": "open", "resolved": False}],
                }
            }
        )

        structure = readiness["engines"]["structure"]

        self.assertEqual(structure["status"], "concept_ready_needs_production_depth")
        self.assertTrue(structure["scope_required"])
        self.assertIn("structure_conflicts", {item["field"] for item in structure["production_blockers"]})

    def test_structure_engine_is_applicable_when_structure_scope_exists(self) -> None:
        readiness = evaluate_engine_readiness(
            {
                "meta": {
                    **_complete_meta(),
                    "structure_summary": {"structure_conflicts": [{"id": "SC-1", "resolved": True}]},
                }
            }
        )

        structure = readiness["engines"]["structure"]

        self.assertTrue(structure["scope_required"])
        self.assertEqual(structure["applicability"], "required")
        self.assertNotEqual(structure["status"], "not_applicable")
        self.assertNotIn("structure", readiness["not_applicable_engine_ids"])


if __name__ == "__main__":
    unittest.main()
