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
            {"layer": "ROAD", "task": "circle", "center": [18, 42], "radius": 45},
            {"layer": "ROAD", "task": "circle", "center": [82, 42], "radius": 45},
            {"layer": "ROAD", "task": "polyline", "points": [[50, 0], [50, 55]]},
            {"layer": "PARKING", "task": "rectangle", "label": "Lot A", "origin": [18, 40], "width": 54, "height": 10},
        ]

        filtered = _filtered_preview_actions(actions)
        kept = [(str(action.get("layer") or "").upper(), str(action.get("task") or "").lower()) for action in filtered]

        self.assertIn(("BUILDING", "rectangle"), kept)
        self.assertIn(("PARKING", "rectangle"), kept)
        self.assertNotIn(("ROAD", "circle"), kept)
        self.assertNotIn(("ROAD", "polyline"), kept)

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


if __name__ == "__main__":
    unittest.main()
