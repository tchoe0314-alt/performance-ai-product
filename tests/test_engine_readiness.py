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


if __name__ == "__main__":
    unittest.main()
