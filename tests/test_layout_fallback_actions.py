import unittest

from backend.planning.core_stage_runners import (
    _layout_fallback_actions,
    _synthesize_layout_semantics,
    _synthesized_program_layout,
)


class LayoutFallbackActionsTests(unittest.TestCase):
    def test_synthesized_program_layout_keeps_frontage_row_clustered(self) -> None:
        placements = _synthesized_program_layout(
            lot_x=0.0,
            lot_y=0.0,
            lot_w=620.0,
            lot_h=980.0,
            street_edge="bottom",
            specs=[
                {"name": "MF-1", "use": "multifamily", "w": 110.0, "d": 58.0},
                {"name": "MF-2", "use": "multifamily", "w": 110.0, "d": 58.0},
                {"name": "MF-3", "use": "multifamily", "w": 110.0, "d": 58.0},
                {"name": "Retail", "use": "retail", "w": 70.0, "d": 45.0},
            ],
        )

        multifamily = [item for item in placements if str(item.get("use") or "").lower() == "multifamily"]
        retail = next(item for item in placements if str(item.get("use") or "").lower() == "retail")
        mf_center_y = sum(float(item["y"]) + float(item["d"]) / 2.0 for item in multifamily) / len(multifamily)
        retail_center_y = float(retail["y"]) + float(retail["d"]) / 2.0

        avg_center_y = sum(float(item["y"]) + float(item["d"]) / 2.0 for item in placements) / len(placements)

        self.assertEqual(len(placements), 4)
        self.assertLess(abs(mf_center_y - retail_center_y), 90.0)
        self.assertLess(avg_center_y, 345.0)

    def test_layout_fallback_emits_parking_walk_and_pavement_layers(self) -> None:
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
        self.assertIn("PAVEMENT", layers)
        self.assertIn("PARKING", layers)
        self.assertIn("WALK", layers)
        self.assertNotIn("ROAD", layers)
        self.assertNotIn("FIRE", layers)
        self.assertNotIn("circle", [str(action.get("task", "")).lower() for action in actions])

    def test_layout_fallback_keeps_parking_modules_proportional(self) -> None:
        actions = _layout_fallback_actions(
            [
                {"name": "MF-1", "use": "multifamily", "x": 112.264, "y": 540.0, "w": 110.0, "d": 58.0},
                {"name": "MF-2", "use": "multifamily", "x": 255.0, "y": 540.0, "w": 110.0, "d": 58.0},
                {"name": "MF-3", "use": "multifamily", "x": 397.736, "y": 540.0, "w": 110.0, "d": 58.0},
                {"name": "Retail", "use": "retail", "x": 275.0, "y": 405.5, "w": 70.0, "d": 45.0},
            ],
            lot_x=0.0,
            lot_y=0.0,
            lot_w=620.0,
            lot_h=980.0,
            street_edge="bottom",
        )

        parking_rects = [
            action
            for action in actions
            if str(action.get("layer", "")).upper() == "PARKING"
            and str(action.get("task", "")).lower() == "rectangle"
        ]
        self.assertEqual(len(parking_rects), 3)
        multifamily_parking = [action for action in parking_rects if float(action.get("width", 0.0)) >= 120.0]
        retail_parking = [action for action in parking_rects if float(action.get("width", 0.0)) < 120.0]
        self.assertEqual(len(multifamily_parking), 2)
        self.assertEqual(len(retail_parking), 1)

        self.assertTrue(all(float(action.get("height", 0.0)) <= 54.0 for action in multifamily_parking))
        self.assertTrue(all(float(action.get("height", 0.0)) <= 42.0 for action in retail_parking))
        self.assertTrue(all(float(action.get("width", 0.0)) <= 210.0 for action in multifamily_parking))
        self.assertTrue(all(float(action.get("width", 0.0)) <= 92.0 for action in retail_parking))

        multifamily_parking = sorted(multifamily_parking, key=lambda action: float(action.get("origin", [0])[0]))
        gaps = []
        for left, right in zip(multifamily_parking, multifamily_parking[1:]):
            left_x = float(left.get("origin", [0])[0])
            left_w = float(left.get("width", 0.0))
            right_x = float(right.get("origin", [0])[0])
            gaps.append(right_x - (left_x + left_w))
        self.assertTrue(all(gap >= 20.0 for gap in gaps))

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
            if str(action.get("layer", "")).upper() == "PAVEMENT"
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
        self.assertIn("PAVEMENT", layers)
        self.assertNotIn("FIRE", layers)

    def test_semantic_cleanup_replaces_schematic_roads_with_collectors(self) -> None:
        actions = [
            {"task": "rectangle", "layer": "PARKING", "origin": [239.764, 643.265], "width": 156, "height": 48},
            {"task": "rectangle", "layer": "PARKING", "origin": [411.45, 643.265], "width": 156, "height": 48},
            {"task": "rectangle", "layer": "PARKING", "origin": [583.136, 643.265], "width": 156, "height": 48},
            {"task": "rectangle", "layer": "PARKING", "origin": [431.45, 197.971], "width": 116, "height": 48},
            {"task": "rectangle", "layer": "BUILDING", "origin": [257.764, 709.265], "width": 120, "height": 60},
            {"task": "rectangle", "layer": "BUILDING", "origin": [429.45, 709.265], "width": 120, "height": 60},
            {"task": "rectangle", "layer": "BUILDING", "origin": [601.136, 709.265], "width": 120, "height": 60},
            {"task": "rectangle", "layer": "BUILDING", "origin": [449.45, 263.971], "width": 80, "height": 50},
            {"task": "circle", "layer": "ROAD", "center": [208.819, 516.618], "radius": 45},
            {"task": "circle", "layer": "ROAD", "center": [770.081, 516.618], "radius": 45},
            {"task": "polyline", "layer": "ROAD", "points": [[208.819, 215.026], [770.081, 215.026], [770.081, 818.21], [208.819, 818.21], [208.819, 215.026]], "closed": False},
            {"task": "polyline", "layer": "ROAD", "points": [[489.45, 0], [489.45, 215.026]], "closed": False},
            {"task": "polyline", "layer": "FIRE", "points": [[208.819, 215.026], [770.081, 215.026], [770.081, 818.21], [208.819, 818.21], [208.819, 215.026]], "closed": False},
            {"task": "polyline", "layer": "FIRE", "points": [[489.45, 0], [489.45, 215.026]], "closed": False},
        ]

        normalized = _synthesize_layout_semantics(actions)
        synthetic_tasks = [
            (str(action.get("task", "")).lower(), str(action.get("layer", "")).upper())
            for action in normalized
            if str(action.get("layer", "")).upper() in {"PAVEMENT", "FIRE"}
        ]

        self.assertTrue(all(task != "circle" for task, _ in synthetic_tasks))
        self.assertTrue(all(task != "polyline" for task, _ in synthetic_tasks))
        self.assertGreaterEqual(sum(1 for task, layer in synthetic_tasks if task == "rectangle" and layer == "PAVEMENT"), 2)
        self.assertEqual(sum(1 for task, layer in synthetic_tasks if task == "rectangle" and layer == "FIRE"), 0)

    def test_semantic_cleanup_does_not_promote_generic_pavement_to_parking(self) -> None:
        actions = [
            {"task": "rectangle", "layer": "BUILDING", "origin": [100, 200], "width": 120, "height": 60, "label": "BLDG 1"},
            {"task": "rectangle", "layer": "PAVEMENT", "origin": [82, 110], "width": 156, "height": 72, "label": "DRIVE"},
        ]

        normalized = _synthesize_layout_semantics(actions)
        layers = [str(action.get("layer", "")).upper() for action in normalized]
        self.assertIn("PAVEMENT", layers)
        self.assertNotIn("PARKING", layers)


if __name__ == "__main__":
    unittest.main()
