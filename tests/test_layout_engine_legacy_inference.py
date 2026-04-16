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

    def test_expanded_mixed_use_plan_keeps_retail_clustered_with_primary_buildings(self) -> None:
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
            }
        )

        buildings = [
            action
            for action in plan["actions"]
            if str(action.get("layer") or "").upper() == "BUILDING"
            and str(action.get("task") or "").lower() == "rectangle"
        ]
        multifamily = [action for action in buildings if "RETAIL" not in str(action.get("label") or "").upper()]
        retail = next(action for action in buildings if "RETAIL" in str(action.get("label") or "").upper())
        mf_center_y = sum(float(action["origin"][1]) + float(action["height"]) / 2.0 for action in multifamily) / len(multifamily)
        retail_center_y = float(retail["origin"][1]) + float(retail["height"]) / 2.0
        multifamily_bands = {
            round(float(action["origin"][1]) + float(action["height"]) / 2.0, 1) for action in multifamily
        }
        nearest_multifamily_y = min(
            float(action["origin"][1]) + float(action["height"]) / 2.0 for action in multifamily
        )
        avg_center_y = sum(float(action["origin"][1]) + float(action["height"]) / 2.0 for action in buildings) / len(buildings)
        self.assertLess(abs(nearest_multifamily_y - retail_center_y), 75.0)
        self.assertLess(avg_center_y, 145.0)
        self.assertGreaterEqual(len(multifamily_bands), 2)

    def test_expanded_mixed_use_plan_uses_shared_residential_courts(self) -> None:
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
            }
        )

        parking = [
            action
            for action in plan["actions"]
            if str(action.get("layer") or "").upper() == "PARKING"
            and str(action.get("task") or "").lower() == "rectangle"
        ]
        labels = [str(action.get("label") or "").upper() for action in parking]
        residential_widths = [
            float(action.get("width") or 0.0)
            for action in parking
            if str(action.get("label") or "").upper().startswith("RES-PARK-")
        ]

        self.assertEqual(len(parking), 3)
        self.assertEqual(sum(1 for label in labels if label.startswith("RES-PARK-")), 2)
        self.assertEqual(sum(1 for label in labels if "RETAIL-PARK" in label), 1)
        self.assertTrue(all(width <= 210.0 for width in residential_widths))
        residential_heights = [
            float(action.get("height") or 0.0)
            for action in parking
            if str(action.get("label") or "").upper().startswith("RES-PARK-")
        ]
        self.assertTrue(all(height <= 80.0 for height in residential_heights))
        retail_top = max(
            float(action.get("origin")[1])
            for action in parking
            if "RETAIL-PARK" in str(action.get("label") or "").upper()
        )
        residential_bottom = min(
            float(action.get("origin")[1])
            for action in parking
            if str(action.get("label") or "").upper().startswith("RES-PARK-")
        )
        self.assertLess(retail_top, residential_bottom)

    def test_shared_residential_courts_keep_walks_aligned_to_buildings(self) -> None:
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
            }
        )

        buildings = [
            action
            for action in plan["actions"]
            if str(action.get("layer") or "").upper() == "BUILDING"
            and str(action.get("task") or "").lower() == "rectangle"
        ]
        building_centers = sorted(
            float(action["origin"][0]) + float(action["width"]) / 2.0 for action in buildings if "RETAIL" not in str(action.get("label") or "").upper()
        )
        walks = [
            action
            for action in plan["actions"]
            if str(action.get("layer") or "").upper() == "WALK"
            and str(action.get("task") or "").lower() == "polyline"
        ]
        walk_xs = sorted({round(float(action["points"][0][0]), 3) for action in walks[:3]})
        self.assertEqual(len(walk_xs), 3)
        for walk_x, building_x in zip(walk_xs, building_centers):
            self.assertAlmostEqual(walk_x, round(building_x, 3), delta=0.5)

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

        self.assertFalse(
            any(
                str(action.get("layer") or "").upper() == "WALK"
                and str(action.get("label") or "").upper().startswith("WALK-")
                for action in actions
            )
        )

        self.assertFalse(
            any(
                str(action.get("label") or "").upper().startswith("FIRE-")
                for action in actions
            )
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

        generic_labels = {
            str(action.get("label") or "").upper()
            for action in plan["actions"]
            if str(action.get("label") or "").strip()
        }
        self.assertNotIn("AISLE-1", generic_labels)
        self.assertNotIn("PIPE-1", generic_labels)
        self.assertNotIn("BASIN-1", generic_labels)
        self.assertNotIn("WATER", generic_labels)

    def test_expanded_plan_drops_synthetic_flow_and_contour_labels(self) -> None:
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
                "grading": {"contours_required": True, "flow_arrow_count": 2, "pad_count": 1, "min_slope_pct": 2.5},
            }
        )

        drain_flow_texts = [
            str(action.get("text") or "").upper()
            for action in plan["actions"]
            if str(action.get("task") or "").lower() == "text_note"
            and str(action.get("layer") or "").upper() == "DRAIN_FLOW"
        ]
        contour_labels = [
            str(action.get("label") or "").upper()
            for action in plan["actions"]
            if str(action.get("task") or "").lower() == "polyline"
            and str(action.get("layer") or "").upper() == "FG_CONTOUR"
        ]

        self.assertFalse(any(text.endswith(" FLOW") for text in drain_flow_texts))
        self.assertTrue(contour_labels)
        self.assertTrue(all(not label for label in contour_labels))


if __name__ == "__main__":
    unittest.main()
