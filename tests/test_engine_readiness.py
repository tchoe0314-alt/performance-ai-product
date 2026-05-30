import unittest

import planner
from backend.planning.engine_contracts import engine_contracts
from backend.planning.engine_readiness import evaluate_engine_readiness
from tests.test_civil_design_readiness import _complete_meta


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
        self.assertIn("structure", readiness["not_evidenced_engine_ids"])
        self.assertIn("coordinate_system", {item["field"] for item in readiness["engines"]["gis_existing_conditions"]["production_blockers"]})
        storm = readiness["engines"]["storm_pipe"]
        self.assertEqual(storm["status"], "concept_ready_needs_production_depth")
        self.assertTrue(storm["production_blockers"])
        self.assertTrue(storm["production_gate_status"])

    def test_missing_core_truth_blocks_impacted_engines(self) -> None:
        readiness = evaluate_engine_readiness({"meta": {"grading": {"source_quality": "fallback"}}})

        self.assertIn("grading", readiness["blocked_engine_ids"])
        self.assertIn("drainage", readiness["blocked_engine_ids"])
        self.assertIn("storm_pipe", readiness["blocked_engine_ids"])
        self.assertIn("sanitary", readiness["blocked_engine_ids"])
        self.assertIn("qa_validation", readiness["blocked_engine_ids"])
        self.assertFalse(readiness["production_ready"])

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

    def test_structure_engine_is_not_production_ready_without_evidence(self) -> None:
        readiness = evaluate_engine_readiness({"meta": _complete_meta()})

        structure = readiness["engines"]["structure"]

        self.assertEqual(structure["status"], "not_evidenced")
        self.assertIn("structure", readiness["not_evidenced_engine_ids"])
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
        self.assertIn("structure_conflicts", {item["field"] for item in structure["production_blockers"]})


if __name__ == "__main__":
    unittest.main()
