import unittest

import planner


class Phase5SurfaceDrainageCoordinationTests(unittest.TestCase):
    def test_drainage_coordination_uses_grading_surface_targets(self) -> None:
        payload = {
            "project_name": "Surface Drainage Coordination",
            "units": "ft",
            "mode": "site_plan",
            "project_type": "commercial_pad",
            "site_type": "commercial_pad",
            "terrain": "6% slope NW to SE",
            "lot": {"x": 0.0, "y": 0.0, "w": 180.0, "h": 140.0},
            "setback": 10.0,
            "street_edge": "bottom",
            "site_plan": {"building_width": 52.0, "building_depth": 38.0, "parking_count": 30},
        }

        out = planner.build_plan(payload)
        drainage = out.get("meta", {}).get("drainage", {})
        coordination = drainage.get("coordination", {})
        preferred = coordination.get("preferred_outfall", {})

        self.assertTrue(coordination)
        self.assertGreaterEqual(coordination.get("grading_low_point_count", 0), 1)
        self.assertGreater(preferred.get("x", 0.0), 90.0)
        self.assertLess(preferred.get("y", 999.0), 70.0)

    def test_storm_pipes_honor_surface_driven_outfall(self) -> None:
        payload = {
            "project_name": "Storm Outfall Coordination",
            "units": "ft",
            "mode": "site_plan",
            "project_type": "commercial_pad",
            "site_type": "commercial_pad",
            "terrain": "5% slope toward southeast",
            "lot": {"x": 0.0, "y": 0.0, "w": 180.0, "h": 140.0},
            "setback": 10.0,
            "street_edge": "bottom",
            "site_plan": {"building_width": 52.0, "building_depth": 38.0, "parking_count": 30},
        }

        out = planner.build_plan(payload)
        drainage = out.get("meta", {}).get("drainage", {})
        preferred = drainage.get("coordination", {}).get("preferred_outfall", {})
        stage_map = {item["stage_name"]: item for item in out.get("meta", {}).get("stage_results", [])}
        storm_stage = stage_map.get("storm_pipes", {})
        storm_meta = storm_stage.get("meta", {})

        self.assertAlmostEqual(storm_meta.get("outfall_x", 0.0), preferred.get("x", 0.0), places=3)
        self.assertAlmostEqual(storm_meta.get("outfall_y", 0.0), preferred.get("y", 0.0), places=3)


if __name__ == "__main__":
    unittest.main()
