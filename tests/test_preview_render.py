import unittest

from output.preview import _filtered_preview_actions


class PreviewRenderTests(unittest.TestCase):
    def test_layout_scene_suppresses_engineering_overlay_noise(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1"},
            {"layer": "ROAD", "task": "rectangle", "label": "DRIVE"},
            {"layer": "PARKING", "task": "polyline", "label": None, "text": None},
            {"layer": "ANNO", "task": "text_note", "text": 'PIPE-1 12" INV 98.52->98.24'},
            {"layer": "PIPE", "task": "polyline", "label": "PIPE-1"},
            {"layer": "BASIN_BOUNDARY", "task": "circle", "label": "SINK_0_43"},
            {"layer": "UTILITY", "task": "polyline", "label": "generic_utility_1"},
            {"layer": "STRUCTURE", "task": "circle", "label": "INLET-1"},
            {"layer": "FG_CONTOUR", "task": "polyline", "label": "FG-101"},
        ]

        filtered = _filtered_preview_actions(actions)
        kept_layers = [str(action.get("layer") or "").upper() for action in filtered]

        self.assertIn("BUILDING", kept_layers)
        self.assertIn("ROAD", kept_layers)
        self.assertNotIn("ANNO", kept_layers)
        self.assertNotIn("PIPE", kept_layers)
        self.assertNotIn("BASIN_BOUNDARY", kept_layers)
        self.assertNotIn("UTILITY", kept_layers)
        self.assertNotIn("STRUCTURE", kept_layers)
        self.assertNotIn("FG_CONTOUR", kept_layers)
        self.assertIn("PARKING", kept_layers)

    def test_layout_scene_suppresses_giant_wrapper_rectangles(self):
        actions = [
            {"layer": "ROAD", "task": "rectangle", "label": "DRIVE", "origin": [0, 0], "width": 100, "height": 100},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [10, 10], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 2", "origin": [32, 10], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 3", "origin": [54, 10], "width": 12, "height": 8},
            {"layer": "ROAD", "task": "polyline", "label": "Loop Road", "points": [[0, 70], [100, 70]]},
            {"layer": "PARKING", "task": "rectangle", "label": "Lot A", "origin": [8, 24], "width": 24, "height": 12},
        ]

        filtered = _filtered_preview_actions(actions)
        kept = [(str(action.get("layer") or "").upper(), str(action.get("task") or "").lower(), str(action.get("label") or "")) for action in filtered]

        self.assertIn(("ROAD", "polyline", "Loop Road"), kept)
        self.assertIn(("PARKING", "rectangle", "Lot A"), kept)
        self.assertNotIn(("ROAD", "rectangle", "DRIVE"), kept)

    def test_layout_scene_suppresses_schematic_circles_and_access_stems(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [20, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 2", "origin": [40, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 3", "origin": [60, 60], "width": 12, "height": 8},
            {"layer": "ROAD", "task": "circle", "center": [18, 42], "radius": 16},
            {"layer": "ROAD", "task": "circle", "center": [82, 42], "radius": 16},
            {"layer": "ROAD", "task": "polyline", "points": [[50, -10], [50, 0], [50, 55]]},
            {"layer": "PARKING", "task": "rectangle", "label": "Lot A", "origin": [18, 40], "width": 54, "height": 10},
        ]

        filtered = _filtered_preview_actions(actions)
        kept = [(str(action.get("layer") or "").upper(), str(action.get("task") or "").lower()) for action in filtered]

        self.assertIn(("BUILDING", "rectangle"), kept)
        self.assertIn(("PARKING", "rectangle"), kept)
        self.assertNotIn(("ROAD", "circle"), kept)
        self.assertNotIn(("ROAD", "polyline"), kept)

    def test_layout_scene_suppresses_enclosing_layout_wrappers_more_aggressively(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [20, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 2", "origin": [40, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 3", "origin": [60, 60], "width": 12, "height": 8},
            {"layer": "ROAD", "task": "rectangle", "origin": [10, 20], "width": 74, "height": 62},
            {"layer": "PARKING", "task": "rectangle", "origin": [16, 40], "width": 58, "height": 10},
            {"layer": "WALK", "task": "rectangle", "origin": [45, 50], "width": 4, "height": 10},
        ]

        filtered = _filtered_preview_actions(actions)
        kept = [(str(action.get("layer") or "").upper(), str(action.get("task") or "").lower()) for action in filtered]
        road_rectangles = [
            action
            for action in filtered
            if str(action.get("layer") or "").upper() == "ROAD"
            and str(action.get("task") or "").lower() == "rectangle"
        ]

        self.assertIn(("PARKING", "rectangle"), kept)
        self.assertIn(("WALK", "rectangle"), kept)
        self.assertFalse(
            any(
                action.get("origin") == [10, 20]
                and action.get("width") == 74
                and action.get("height") == 62
                for action in road_rectangles
            )
        )
        pavement_rectangles = [
            action
            for action in filtered
            if str(action.get("layer") or "").upper() == "PAVEMENT"
            and str(action.get("task") or "").lower() == "rectangle"
        ]
        self.assertGreaterEqual(len(pavement_rectangles), 1)

    def test_non_layout_scene_keeps_engineering_geometry_available(self):
        actions = [
            {"layer": "PIPE", "task": "polyline", "label": "PIPE-1"},
            {"layer": "STRUCTURE", "task": "circle", "label": "INLET-1"},
        ]

        filtered = _filtered_preview_actions(actions)
        kept_layers = [str(action.get("layer") or "").upper() for action in filtered]

        self.assertIn("PIPE", kept_layers)
        self.assertIn("STRUCTURE", kept_layers)

    def test_layout_scene_synthesizes_parking_walk_and_fire_when_missing(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "origin": [20, 60], "width": 12, "height": 8, "label": "BLDG 1"},
            {"layer": "BUILDING", "task": "rectangle", "origin": [40, 60], "width": 12, "height": 8, "label": "BLDG 2"},
            {"layer": "ROAD", "task": "polyline", "points": [[10, 20], [90, 20]], "label": "Loop"},
            {"layer": "PAVEMENT", "task": "rectangle", "origin": [18, 34], "width": 40, "height": 14, "label": "Lot Base"},
        ]

        filtered = _filtered_preview_actions(actions)
        kept_layers = [str(action.get("layer") or "").upper() for action in filtered]

        self.assertIn("PARKING", kept_layers)
        self.assertIn("WALK", kept_layers)
        self.assertIn("FIRE", kept_layers)

    def test_layout_scene_synthesizes_drive_aisles_when_only_wrapper_roads_exist(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "origin": [220, 700], "width": 120, "height": 60, "label": "BLDG 1"},
            {"layer": "BUILDING", "task": "rectangle", "origin": [410, 700], "width": 120, "height": 60, "label": "BLDG 2"},
            {"layer": "BUILDING", "task": "rectangle", "origin": [600, 700], "width": 120, "height": 60, "label": "BLDG 3"},
            {"layer": "BUILDING", "task": "rectangle", "origin": [435, 240], "width": 90, "height": 60, "label": "RETAIL PAD"},
            {"layer": "PARKING", "task": "rectangle", "origin": [200, 560], "width": 160, "height": 70},
            {"layer": "PARKING", "task": "rectangle", "origin": [390, 560], "width": 160, "height": 70},
            {"layer": "PARKING", "task": "rectangle", "origin": [580, 560], "width": 160, "height": 70},
            {"layer": "PARKING", "task": "rectangle", "origin": [420, 120], "width": 120, "height": 70},
            {"layer": "ROAD", "task": "polyline", "points": [[208.819, 215.026], [770.081, 215.026], [770.081, 818.21], [208.819, 818.21], [208.819, 215.026]]},
            {"layer": "ROAD", "task": "polyline", "points": [[489.45, 0.0], [489.45, 215.026]]},
            {"layer": "ROAD", "task": "circle", "center": [208.819, 516.618], "radius": 45.0},
            {"layer": "ROAD", "task": "circle", "center": [770.081, 516.618], "radius": 45.0},
        ]

        filtered = _filtered_preview_actions(actions)
        pavement_rectangles = [
            action
            for action in filtered
            if str(action.get("layer") or "").upper() == "PAVEMENT"
            and str(action.get("task") or "").lower() == "rectangle"
        ]
        fire_rectangles = [
            action
            for action in filtered
            if str(action.get("layer") or "").upper() == "FIRE"
            and str(action.get("task") or "").lower() == "rectangle"
        ]
        pavement_rectangles = sorted(pavement_rectangles, key=lambda action: float(action.get("width") or 0.0), reverse=True)

        self.assertGreaterEqual(len(pavement_rectangles), 2)
        self.assertGreaterEqual(len(fire_rectangles), 2)
        self.assertLessEqual(float(pavement_rectangles[0].get("width") or 0.0), 180.0)
        self.assertTrue(
            any(float(action.get("origin", [0.0])[0]) >= 740.0 for action in pavement_rectangles),
            "expected synthesized connector pavement to route along the layout edge",
        )


if __name__ == "__main__":
    unittest.main()
