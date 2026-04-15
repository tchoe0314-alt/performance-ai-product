import unittest
from types import SimpleNamespace

import planner
from backend.planning.grading_support import grading_surface_actions, surface_actions_from_grid
from engines.grading_engine import GradeElement
from engines.surface_engine import GridSurface


class Phase4GradingSurfaceTests(unittest.TestCase):
    def test_grading_surface_actions_prioritize_control_spot_grades(self) -> None:
        surface = GridSurface(
            x_min=0.0,
            y_min=0.0,
            x_max=100.0,
            y_max=100.0,
            cell_size=10.0,
            ncols=11,
            nrows=11,
            values=[[100.0 + row * 0.1 + col * 0.05 for col in range(11)] for row in range(11)],
        )
        result = SimpleNamespace(low_points=[SimpleNamespace(x=5.0, y=5.0, z=99.5)])
        grade_elements = [
            GradeElement(kind="pad", x=40.0, y=40.0, width=20.0, depth=20.0, base_elev=101.0, name="BLDG-1"),
            GradeElement(kind="parking", x=20.0, y=60.0, width=30.0, depth=20.0, base_elev=100.5, name="PARK-1"),
            GradeElement(kind="pad", x=0.0, y=0.0, width=100.0, depth=100.0, base_elev=100.0, name="BUILDABLE_AREA"),
        ]

        actions, stats = grading_surface_actions(
            result,
            surface,
            surface,
            grade_elements=grade_elements,
        )

        spot_origins = [
            tuple(action.get("origin") or [])
            for action in actions
            if str(action.get("layer") or "").upper() == "SPOT_FG"
            and str(action.get("task") or "").lower() == "text_note"
        ]

        self.assertIn((50.0, 50.0), spot_origins)
        self.assertIn((35.0, 70.0), spot_origins)
        self.assertNotIn((50.0, 50.0, 100.0), spot_origins)
        self.assertGreaterEqual(stats.get("spot_grade_count", 0), 2)

    def test_surface_actions_from_grid_places_labels_on_line_midpoint(self) -> None:
        surface = GridSurface(
            x_min=0.0,
            y_min=0.0,
            x_max=40.0,
            y_max=40.0,
            cell_size=10.0,
            ncols=5,
            nrows=5,
            values=[[100.0 for _ in range(5)] for _ in range(5)],
        )

        actions = surface_actions_from_grid(surface, layer="FG_CONTOUR", note_prefix="FG", sample_lines=2)
        polylines = [
            action for action in actions
            if str(action.get("task") or "").lower() == "polyline"
            and str(action.get("layer") or "").upper() == "FG_CONTOUR"
        ]
        labels = [
            action for action in actions
            if str(action.get("task") or "").lower() == "text_note"
            and str(action.get("layer") or "").upper() == "FG_CONTOUR"
        ]

        self.assertTrue(polylines)
        self.assertTrue(all(not action.get("label") for action in polylines))
        self.assertTrue(labels)
        self.assertNotEqual(labels[0].get("origin"), [0.0, 0.0])

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

        surface = planner._build_existing_surface(payload)
        profile = getattr(surface, "_inferred_profile", {})
        min_z, max_z = planner._surface_range(surface)

        self.assertTrue(profile.get("inferred"))
        self.assertEqual(profile.get("source"), "terrain_direction_pair")
        self.assertGreater(max_z - min_z, 0.0)

    def test_grading_exports_real_surface_outputs(self) -> None:
        surface = GridSurface(
            x_min=0.0,
            y_min=0.0,
            x_max=180.0,
            y_max=140.0,
            cell_size=10.0,
            ncols=19,
            nrows=15,
            values=[[100.0 + row * 0.15 + col * 0.04 for col in range(19)] for row in range(15)],
        )
        result = SimpleNamespace(
            proposed_surface=surface,
            success=True,
            message="Proposed grading surface built.",
            warnings=[],
            checks=[SimpleNamespace(name="max_slope", passed=False, value=6.1, threshold=5.0, message="Too steep")],
            low_points=[
                SimpleNamespace(x=12.0, y=18.0, z=100.2, row=1, col=1, local_basin_score=0.8),
                SimpleNamespace(x=48.0, y=54.0, z=101.1, row=5, col=4, local_basin_score=0.5),
            ],
            flow_samples=[
                SimpleNamespace(x=55.0, y=52.0, z=101.4, slope_x=0.01, slope_y=-0.02, magnitude=0.022, downhill_dx=0.45, downhill_dy=-0.89),
                SimpleNamespace(x=95.0, y=84.0, z=102.0, slope_x=0.008, slope_y=-0.015, magnitude=0.017, downhill_dx=0.47, downhill_dy=-0.88),
            ],
            drainage_hints={"outfall": "south"},
            explain={"summary": "grading ok"},
            optimize_hooks={},
            conflict_hooks={},
            cut_volume=120.0,
            fill_volume=95.0,
            net_volume=25.0,
        )
        grade_elements = [
            GradeElement(kind="pad", x=40.0, y=30.0, width=50.0, depth=40.0, base_elev=101.0, name="BLDG-1"),
            GradeElement(kind="parking", x=28.0, y=80.0, width=90.0, depth=28.0, base_elev=100.5, name="PARK-1"),
        ]

        actions, stats = grading_surface_actions(result, surface, surface, grade_elements=grade_elements)
        grading = planner._canonical_grading_payload(
            existing_surface=surface,
            result=result,
            derived_action_stats=stats,
            grade_elements=grade_elements,
        )
        spot_actions = [
            action for action in actions
            if str(action.get("layer") or "").upper() == "SPOT_FG"
            and str(action.get("task") or "").lower() == "text_note"
        ]

        self.assertGreater(grading.get("stats", {}).get("proposed_contour_count", 0), 0)
        self.assertGreater(grading.get("stats", {}).get("spot_grade_count", 0), 0)
        self.assertGreater(grading.get("stats", {}).get("flow_arrow_count", 0), 0)
        self.assertTrue(grading.get("low_points"))
        self.assertTrue(grading.get("flow_samples"))
        self.assertGreaterEqual(abs(grading.get("earthwork", {}).get("net_cf", 0.0)), 0.0)
        spot_origins = {tuple(action.get("origin") or []) for action in spot_actions}
        self.assertIn((65.0, 50.0), spot_origins)
        self.assertIn((73.0, 94.0), spot_origins)


if __name__ == "__main__":
    unittest.main()
