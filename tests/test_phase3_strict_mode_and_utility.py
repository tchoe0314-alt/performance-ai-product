import unittest
from unittest.mock import patch

import planner
from engines.utility_engine import UtilityEngine


DEMO = {
    "project_name": "Phase 3 Strict Test",
    "units": "ft",
    "mode": "site_plan",
    "project_type": "commercial_pad",
    "site_type": "commercial_pad",
    "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
    "setback": 10.0,
    "street_edge": "bottom",
    "layout_strategy": "front_parking",
    "site_plan": {"building_width": 48.0, "building_depth": 34.0, "parking_count": 24},
}


class _NullGradingEngine:
    def __init__(self, *args, **kwargs):
        self.elements = []

    def build(self, *args, **kwargs):
        return None

    def apply_to_project(self, *args, **kwargs):
        return None


class _ExplodingUtilityEngine:
    def __init__(self, *args, **kwargs):
        pass

    def generate(self, *args, **kwargs):
        raise RuntimeError("simulated utility engine failure")


class _EmptyUtilityEngine:
    def __init__(self, *args, **kwargs):
        pass

    class _Result:
        success = False
        message = "no routes produced"
        route_count = 0
        total_length = 0.0
        warnings = []
        explain = {"segments": []}
        conflict_hooks = {"utility_segments": []}

    def generate(self, *args, **kwargs):
        return self._Result()


class Phase3StrictModeTests(unittest.TestCase):
    def test_utility_engine_accepts_legacy_kwargs(self) -> None:
        engine = UtilityEngine(level="L1", layer_name="UTILITY", system_type="water")
        self.assertEqual(engine.compatibility_options["level"], "L1")
        self.assertEqual(engine.compatibility_options["layer_name"], "UTILITY")
        self.assertEqual(engine.compatibility_options["system_type"], "water")

    def test_strict_mode_blocks_grading_fallback(self) -> None:
        payload = {**DEMO, "strict_mode": True}
        with patch.object(planner, "GradingEngine", _NullGradingEngine):
            out = planner.build_plan(payload)
        stage_map = {item["stage_name"]: item for item in out.get("meta", {}).get("stage_results", [])}
        grading_stage = stage_map.get("grading", {})
        self.assertFalse(grading_stage.get("success", True))
        self.assertEqual(grading_stage.get("meta", {}).get("failure_code"), "STRICT_GRADING_FALLBACK_BLOCKED")
        self.assertIn("STRICT mode blocked grading fallback", " ".join(out.get("meta", {}).get("errors", [])))

    def test_strict_mode_blocks_utility_fallback(self) -> None:
        payload = {**DEMO, "strict_mode": True}
        with patch.object(planner, "UtilityEngine", _ExplodingUtilityEngine):
            out = planner.build_plan(payload)
        stage_map = {item["stage_name"]: item for item in out.get("meta", {}).get("stage_results", [])}
        utility_stage = stage_map.get("utility_network", {})
        self.assertFalse(utility_stage.get("success", True))
        self.assertEqual(utility_stage.get("meta", {}).get("failure_code"), "STRICT_UTILITY_FALLBACK_BLOCKED")
        self.assertIn("STRICT mode blocked utility fallback", " ".join(out.get("meta", {}).get("errors", [])))

    def test_non_strict_mode_falls_back_when_utility_engine_returns_no_routes(self) -> None:
        payload = {**DEMO, "strict_mode": False}
        with patch.object(planner, "UtilityEngine", _EmptyUtilityEngine):
            out = planner.build_plan(payload)
        utility = dict((out.get("meta") or {}).get("utilities") or {})
        self.assertTrue(utility.get("fallback_used"))
        self.assertGreater(int(utility.get("route_count") or 0), 0)
        self.assertNotIn("UTILITY_STAGE_FAILED", " ".join((out.get("meta") or {}).get("warnings", []) or []))


if __name__ == "__main__":
    unittest.main()
