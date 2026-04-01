import unittest

import planner


class Phase4GradingSurfaceTests(unittest.TestCase):
    def test_prompt_defined_slope_builds_inferred_existing_surface(self) -> None:
        payload = {
            "project_name": "Terrain Inference",
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
        grading = out.get("meta", {}).get("grading", {})
        existing = grading.get("existing_surface", {})

        self.assertTrue(existing.get("terrain_inferred"))
        self.assertEqual(existing.get("terrain_profile", {}).get("source"), "terrain_direction_pair")
        self.assertGreater(existing.get("range_z", 0.0), 0.0)

    def test_grading_exports_real_surface_outputs(self) -> None:
        payload = {
            "project_name": "Grading Outputs",
            "units": "ft",
            "mode": "site_plan",
            "project_type": "commercial_pad",
            "site_type": "commercial_pad",
            "terrain": "4% slope toward south",
            "lot": {"x": 0.0, "y": 0.0, "w": 180.0, "h": 140.0},
            "setback": 10.0,
            "street_edge": "bottom",
            "site_plan": {"building_width": 52.0, "building_depth": 38.0, "parking_count": 30},
        }

        out = planner.build_plan(payload)
        grading = out.get("meta", {}).get("grading", {})
        stats = grading.get("stats", {})
        earthwork = grading.get("earthwork", {})

        self.assertGreater(stats.get("proposed_contour_count", 0), 0)
        self.assertGreater(stats.get("spot_grade_count", 0), 0)
        self.assertGreater(stats.get("flow_arrow_count", 0), 0)
        self.assertTrue(grading.get("low_points"))
        self.assertTrue(grading.get("flow_samples"))
        self.assertGreaterEqual(abs(earthwork.get("net_cf", 0.0)) + earthwork.get("cut_cf", 0.0) + earthwork.get("fill_cf", 0.0), 0.0)


if __name__ == "__main__":
    unittest.main()
