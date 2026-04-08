import unittest

from backend.planning.core_stage_runners import _layout_fallback_actions, _synthesize_layout_semantics


class LayoutFallbackActionsTests(unittest.TestCase):
    def test_layout_fallback_emits_parking_walk_and_fire_layers(self) -> None:
        actions = _layout_fallback_actions(
            [{"name": "BLDG 1", "x": 100.0, "y": 200.0, "w": 120.0, "d": 60.0}],
            lot_x=0.0,
            lot_y=0.0,
            lot_w=500.0,
            lot_h=500.0,
            street_edge="bottom",
            culdesac_count=2,
        )

        layers = [str(action.get("layer", "")).upper() for action in actions]
        self.assertIn("ROAD", layers)
        self.assertIn("FIRE", layers)
        self.assertIn("PARKING", layers)
        self.assertIn("WALK", layers)
        self.assertNotIn("circle", [str(action.get("task", "")).lower() for action in actions])

    def test_layout_fallback_avoids_loop_and_culdesac_schematic_shapes(self) -> None:
        actions = _layout_fallback_actions(
            [
                {"name": "BLDG 1", "x": 220.0, "y": 700.0, "w": 120.0, "d": 60.0},
                {"name": "BLDG 2", "x": 410.0, "y": 700.0, "w": 120.0, "d": 60.0},
                {"name": "BLDG 3", "x": 600.0, "y": 700.0, "w": 120.0, "d": 60.0},
                {"name": "RETAIL PAD", "x": 435.0, "y": 240.0, "w": 90.0, "d": 60.0},
            ],
            lot_x=0.0,
            lot_y=0.0,
            lot_w=980.0,
            lot_h=980.0,
            street_edge="bottom",
            culdesac_count=2,
        )

        tasks = [str(action.get("task", "")).lower() for action in actions]
        self.assertNotIn("circle", tasks)
        self.assertTrue(all(task != "polyline" for task in tasks))

    def test_layout_fallback_avoids_single_center_spine_for_mixed_rows(self) -> None:
        actions = _layout_fallback_actions(
            [
                {"name": "BLDG 1", "x": 220.0, "y": 700.0, "w": 120.0, "d": 60.0},
                {"name": "BLDG 2", "x": 410.0, "y": 700.0, "w": 120.0, "d": 60.0},
                {"name": "BLDG 3", "x": 600.0, "y": 700.0, "w": 120.0, "d": 60.0},
                {"name": "RETAIL PAD", "x": 435.0, "y": 240.0, "w": 90.0, "d": 60.0},
            ],
            lot_x=0.0,
            lot_y=0.0,
            lot_w=980.0,
            lot_h=980.0,
            street_edge="bottom",
            culdesac_count=2,
        )

        road_rects = [
            action for action in actions
            if str(action.get("layer", "")).upper() == "ROAD"
            and str(action.get("task", "")).lower() == "rectangle"
        ]
        narrow_vertical_roads = [
            action for action in road_rects
            if float(action.get("height", 0)) > 200 and float(action.get("width", 0)) < 28
        ]
        centered_spines = [
            action for action in narrow_vertical_roads
            if 300.0 <= float(action.get("origin", [0])[0]) <= 680.0
        ]

        self.assertEqual(len(centered_spines), 0)

    def test_semantic_cleanup_promotes_parking_walk_and_fire_for_expanded_layout(self) -> None:
        actions = [
            {"task": "rectangle", "layer": "BUILDING", "origin": [100, 200], "width": 120, "height": 60, "label": "BLDG 1"},
            {"task": "rectangle", "layer": "BUILDING", "origin": [260, 200], "width": 120, "height": 60, "label": "BLDG 2"},
            {"task": "rectangle", "layer": "PAVEMENT", "origin": [82, 110], "width": 156, "height": 72},
            {"task": "rectangle", "layer": "PAVEMENT", "origin": [242, 110], "width": 156, "height": 72},
            {"task": "polyline", "layer": "ROAD", "points": [[50, 80], [450, 80], [450, 420], [50, 420], [50, 80]], "closed": False},
        ]

        normalized = _synthesize_layout_semantics(actions)
        layers = [str(action.get("layer", "")).upper() for action in normalized]

        self.assertIn("PARKING", layers)
        self.assertIn("WALK", layers)
        self.assertIn("FIRE", layers)


if __name__ == "__main__":
    unittest.main()
