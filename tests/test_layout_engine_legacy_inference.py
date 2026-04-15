import unittest

from geometry.layout_engine import (
    _build_expanded_plan,
    _infer_drive_aisles_from_legacy,
    _infer_roads_from_legacy,
    _layout_to_actions,
    generate_smart_layout,
)


class LayoutEngineLegacyInferenceTests(unittest.TestCase):
    def test_multi_parking_legacy_inference_uses_local_aisles(self) -> None:
        parsed = {"street_edge": "bottom"}
        site_box = {"x": 0.0, "y": 0.0, "w": 500.0, "h": 500.0}
        parking_areas = [
            {"x": 100.0, "y": 220.0, "w": 120.0, "h": 60.0},
            {"x": 260.0, "y": 220.0, "w": 120.0, "h": 60.0},
        ]

        aisles = _infer_drive_aisles_from_legacy(parsed, site_box, parking_areas)

        self.assertEqual(len(aisles), 2)
        self.assertTrue(all(item.get("type") == "parking_aisle" for item in aisles))
        self.assertTrue(all(str(item.get("label", "")).startswith("AISLE-") for item in aisles))

    def test_single_parking_legacy_inference_does_not_create_long_access_drive(self) -> None:
        parsed = {"street_edge": "bottom"}
        site_box = {"x": 0.0, "y": 0.0, "w": 500.0, "h": 500.0}
        parking_areas = [{"x": 160.0, "y": 220.0, "w": 120.0, "h": 60.0}]

        aisles = _infer_drive_aisles_from_legacy(parsed, site_box, parking_areas)

        self.assertEqual(len(aisles), 1)
        self.assertEqual(aisles[0].get("type"), "parking_aisle")
        self.assertEqual(aisles[0].get("label"), "AISLE-1")

    def test_legacy_roads_are_suppressed_when_program_has_parking_areas(self) -> None:
        parsed = {
            "street_edge": "bottom",
            "parking_areas": [{"x": 160.0, "y": 220.0, "w": 120.0, "h": 60.0}],
        }
        site_box = {"x": 0.0, "y": 0.0, "w": 500.0, "h": 500.0}

        roads = _infer_roads_from_legacy(parsed, site_box)

        self.assertEqual(roads, [])

    def test_legacy_roads_are_suppressed_when_program_has_buildings(self) -> None:
        parsed = {
            "street_edge": "bottom",
            "buildings": [{"x": 200.0, "y": 300.0, "w": 80.0, "d": 50.0, "name": "BLDG"}],
        }
        site_box = {"x": 0.0, "y": 0.0, "w": 500.0, "h": 500.0}

        roads = _infer_roads_from_legacy(parsed, site_box)

        self.assertEqual(roads, [])

    def test_expanded_multi_building_plan_drops_schematic_raw_actions(self) -> None:
        plan = _build_expanded_plan(
            {
                "project_type": "mixed_use",
                "lot": {"w": 620.0, "h": 980.0},
                "buildings": [
                    {"name": "MF-1", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "MF-2", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "MF-3", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "Retail", "type": "retail", "width": 70, "depth": 45},
                ],
                "actions": [
                    {"task": "text_note", "layer": "PAVEMENT", "origin": [290, 534], "text": "FRONTAGE ACCESS"},
                    {"task": "polyline", "layer": "ROAD", "points": [[0, 0], [300, 300]]},
                    {"task": "circle", "layer": "FIRE", "center": [10, 10], "radius": 15},
                    {"task": "polyline", "layer": "PIPE", "points": [[220, 520], [310, 430], [410, 380]]},
                ],
            }
        )

        actions = plan["actions"]
        self.assertFalse(any("FRONTAGE" in str(action.get("text") or "").upper() for action in actions))
        self.assertFalse(any(str(action.get("layer") or "").upper() == "ROAD" and str(action.get("task") or "").lower() == "polyline" for action in actions))
        self.assertFalse(any(str(action.get("layer") or "").upper() == "FIRE" and str(action.get("task") or "").lower() == "circle" for action in actions))
        self.assertTrue(any(str(action.get("layer") or "").upper() == "PIPE" for action in actions))

    def test_expanded_multi_building_plan_drops_raw_layout_duplicates(self) -> None:
        plan = _build_expanded_plan(
            {
                "project_type": "mixed_use",
                "lot": {"w": 620.0, "h": 980.0},
                "buildings": [
                    {"name": "MF-1", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "MF-2", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "MF-3", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "Retail", "type": "retail", "width": 70, "depth": 45},
                ],
                "actions": [
                    {"task": "rectangle", "layer": "BUILDING", "origin": [10, 10], "width": 80, "height": 50, "label": "OLD BLDG"},
                    {"task": "rectangle", "layer": "PARKING", "origin": [12, 70], "width": 120, "height": 60, "label": "OLD PARK"},
                    {"task": "text_note", "layer": "ANNO", "origin": [15, 15], "text": "legacy layout note"},
                    {"task": "polyline", "layer": "PIPE", "points": [[220, 520], [310, 430], [410, 380]]},
                ],
            }
        )

        actions = plan["actions"]
        self.assertFalse(any(str(action.get("label") or "").upper() == "OLD BLDG" for action in actions))
        self.assertFalse(any(str(action.get("label") or "").upper() == "OLD PARK" for action in actions))
        self.assertFalse(any(str(action.get("text") or "").lower() == "legacy layout note" for action in actions))
        self.assertTrue(any(str(action.get("layer") or "").upper() == "PIPE" for action in actions))
        self.assertFalse(
            any(
                str(action.get("layer") or "").upper() == "BUILDING"
                and str(action.get("task") or "").lower() == "text_note"
                for action in actions
            )
        )
        self.assertFalse(
            any(
                str(action.get("layer") or "").upper() == "PARKING"
                and str(action.get("task") or "").lower() == "text_note"
                for action in actions
            )
        )

    def test_simple_layout_actions_do_not_label_synthetic_circulation_as_frontage_or_access(self) -> None:
        layout = generate_smart_layout(
            lot={"x": 0.0, "y": 0.0, "w": 120.0, "h": 100.0},
            setback=10.0,
            layout_strategy="front_parking",
            street_edge="bottom",
            site_type="commercial_pad",
        )

        actions = _layout_to_actions(layout)
        circulation_labels = [
            str(action.get("label") or "").upper()
            for action in actions
            if action.get("semantic_surface_role") == "circulation"
        ]

        self.assertNotIn("FRONTAGE", circulation_labels)
        self.assertNotIn("ACCESS", circulation_labels)

    def test_simple_layout_actions_do_not_emit_full_width_frontage_surface(self) -> None:
        layout = generate_smart_layout(
            lot={"x": 0.0, "y": 0.0, "w": 120.0, "h": 100.0},
            setback=10.0,
            layout_strategy="front_parking",
            street_edge="bottom",
            site_type="commercial_pad",
        )

        actions = _layout_to_actions(layout)
        pavement_rects = [
            action
            for action in actions
            if str(action.get("layer") or "").upper() == "PAVEMENT"
            and str(action.get("task") or "").lower() == "rectangle"
        ]

        self.assertFalse(
            any(float(action.get("width") or 0.0) >= 100.0 and float(action.get("height") or 0.0) >= 20.0 for action in pavement_rects)
        )

    def test_simple_layout_actions_do_not_emit_long_driveway_stem_or_synthetic_fire_polyline(self) -> None:
        layout = generate_smart_layout(
            lot={"x": 0.0, "y": 0.0, "w": 120.0, "h": 100.0},
            setback=10.0,
            layout_strategy="front_parking",
            street_edge="bottom",
            site_type="commercial_pad",
        )

        actions = _layout_to_actions(layout)
        pavement_rects = [
            action
            for action in actions
            if str(action.get("layer") or "").upper() == "PAVEMENT"
            and str(action.get("task") or "").lower() == "rectangle"
        ]
        self.assertFalse(
            any(float(action.get("height") or 0.0) >= 45.0 and float(action.get("width") or 0.0) <= 35.0 for action in pavement_rects)
        )
        self.assertFalse(
            any(
                str(action.get("layer") or "").upper() == "PAVEMENT"
                and str(action.get("task") or "").lower() == "polyline"
                for action in actions
            )
        )
        self.assertFalse(
            any(
                str(action.get("layer") or "").upper() == "PARKING"
                and str(action.get("task") or "").lower() == "text_note"
                for action in actions
            )
        )

    def test_simple_layout_actions_do_not_emit_redundant_building_or_walk_text_notes(self) -> None:
        layout = generate_smart_layout(
            lot={"x": 0.0, "y": 0.0, "w": 120.0, "h": 100.0},
            setback=10.0,
            layout_strategy="front_parking",
            street_edge="bottom",
            site_type="commercial_pad",
        )

        actions = _layout_to_actions(layout)
        text_notes = [
            action
            for action in actions
            if str(action.get("task") or "").lower() == "text_note"
        ]

        self.assertFalse(
            any(str(action.get("layer") or "").upper() in {"BUILDING", "WALK"} for action in text_notes)
        )

    def test_expanded_plan_drops_redundant_network_annotation_notes(self) -> None:
        plan = _build_expanded_plan(
            {
                "project_type": "mixed_use",
                "lot": {"w": 620.0, "h": 980.0},
                "buildings": [
                    {"name": "MF-1", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "MF-2", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "MF-3", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "Retail", "type": "retail", "width": 70, "depth": 45},
                ],
                "drive_aisles": [
                    {"label": "AISLE-1", "layer": "PAVEMENT", "width": 26.0, "points": [[180.0, 450.0], [420.0, 450.0]]}
                ],
                "sidewalks": [
                    {"label": "ADA", "layer": "WALK", "width": 5.0, "points": [[230.0, 520.0], [230.0, 430.0]]}
                ],
                "pipe_network": [
                    {"label": "PIPE-1", "layer": "PIPE", "diameter": 24.0, "start": [260.0, 500.0], "end": [380.0, 430.0]}
                ],
                "ponds": [
                    {"label": "BASIN-1", "layer": "BASIN_BOUNDARY", "x": 440.0, "y": 260.0, "w": 90.0, "h": 70.0}
                ],
                "utility_network": [
                    {"label": "WATER", "layer": "WATER", "points": [[160.0, 400.0], [440.0, 400.0]]}
                ],
            }
        )

        text_notes = [
            action
            for action in plan["actions"]
            if str(action.get("task") or "").lower() == "text_note"
        ]

        self.assertFalse(
            any(str(action.get("layer") or "").upper() in {"PAVEMENT", "WALK", "PIPE", "BASIN_BOUNDARY", "WATER", "UTILITY"} for action in text_notes)
        )


if __name__ == "__main__":
    unittest.main()
