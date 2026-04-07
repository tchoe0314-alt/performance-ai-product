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
        self.assertNotIn("PARKING", kept_layers)

    def test_non_layout_scene_keeps_engineering_geometry_available(self):
        actions = [
            {"layer": "PIPE", "task": "polyline", "label": "PIPE-1"},
            {"layer": "STRUCTURE", "task": "circle", "label": "INLET-1"},
        ]

        filtered = _filtered_preview_actions(actions)
        kept_layers = [str(action.get("layer") or "").upper() for action in filtered]

        self.assertIn("PIPE", kept_layers)
        self.assertIn("STRUCTURE", kept_layers)


if __name__ == "__main__":
    unittest.main()
