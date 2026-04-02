import unittest

from fastapi import HTTPException

from backend.api.app import _final_plan_from_result, _run_orchestration


class ApiEngineeringGuardsTest(unittest.TestCase):
    def test_manual_orchestration_asks_for_clarification_when_prompt_is_underspecified(self) -> None:
        result = _run_orchestration(
            {
                "input_mode": "manual",
                "strict_mode": False,
                "prompt_text": "Design a fully coordinated civil site with grading, drainage, utilities, and a detention basin.",
                "manual_fields": {},
                "meta": {},
            }
        )
        self.assertFalse(result["success"])
        self.assertTrue((result.get("metadata") or {}).get("needs_clarification"))
        self.assertIn("need", result["message"].lower())

    def test_export_requires_stable_engineered_storm_and_drainage_state(self) -> None:
        with self.assertRaises(HTTPException) as exc_info:
            _final_plan_from_result(
                {
                    "final_plan": {
                        "project_name": "Unstable Plan",
                        "actions": [
                            {"task": "polyline", "layer": "PIPE", "points": [[0.0, 0.0], [10.0, 0.0]]},
                            {"task": "polyline", "layer": "BASIN_BOUNDARY", "points": [[0.0, 0.0], [0.0, 5.0], [5.0, 5.0]]},
                        ],
                        "meta": {
                            "deliverables": {"requested": ["storm_pipe_plan", "drainage_plan"], "produced": ["storm_pipe_plan", "drainage_plan"]},
                            "drainage": {"export_validation": {"ready": False, "reasons": ["primary_detention_missing"]}},
                            "storm_pipes": {
                                "graph_validation": {"valid": False},
                                "hydraulic_validation": {"valid": False},
                                "missing_data_segments": ["P-1"],
                            },
                        },
                    }
                }
            )
        self.assertEqual(exc_info.exception.status_code, 409)
        self.assertIn("stable drainage/storm state", str(exc_info.exception.detail))

    def test_export_no_longer_falls_back_to_fake_drawable_geometry(self) -> None:
        with self.assertRaises(HTTPException) as exc_info:
            _final_plan_from_result({"final_plan": {"project_name": "No Actions", "actions": []}})
        self.assertEqual(exc_info.exception.status_code, 409)
        self.assertIn("stable engineered plan actions", str(exc_info.exception.detail))


if __name__ == "__main__":
    unittest.main()
