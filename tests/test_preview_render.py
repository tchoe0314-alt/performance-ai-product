import unittest

from output.preview import _choose_view_bounds, _filtered_preview_actions, _preview_draw_priority, preview_label


class PreviewRenderTests(unittest.TestCase):
    def test_preview_label_suppresses_generic_aisle_names(self):
        action = {"layer": "PAVEMENT", "task": "rectangle", "label": "AISLE-1"}
        self.assertEqual(preview_label(action), "")

    def test_preview_draw_priority_renders_engineering_over_pavement(self):
        pavement = {"layer": "PAVEMENT", "task": "rectangle"}
        drain = {"layer": "DRAIN", "task": "circle"}
        label = {"layer": "DRAIN", "task": "text_note"}

        self.assertLess(_preview_draw_priority(pavement), _preview_draw_priority(drain))
        self.assertLess(_preview_draw_priority(drain), _preview_draw_priority(label))

    def test_choose_view_bounds_prefers_primary_layout_cluster(self):
        drawn_items = [
            ("SITE", "rectangle", (0, 0, 400, 300)),
            ("BUILDING", "rectangle", (120, 140, 210, 210)),
            ("PARKING", "rectangle", (110, 90, 240, 135)),
            ("WALK", "rectangle", (160, 135, 170, 160)),
        ]

        selected = _choose_view_bounds(drawn_items, engineering_profile="layout")

        self.assertEqual(selected, (110, 90, 240, 210))

    def test_choose_view_bounds_keeps_key_engineering_with_completed_runs(self):
        drawn_items = [
            ("SITE", "rectangle", (0, 0, 400, 300)),
            ("BUILDING", "rectangle", (120, 140, 210, 210)),
            ("PARKING", "rectangle", (110, 90, 240, 135)),
            ("PIPE", "polyline", (220, 70, 280, 125)),
            ("BASIN_BOUNDARY", "polygon", (250, 40, 320, 100)),
            ("FG_CONTOUR", "polyline", (40, 30, 360, 240)),
        ]

        selected = _choose_view_bounds(drawn_items, engineering_profile="complete")

        self.assertEqual(selected, (110, 40, 320, 210))

    def test_choose_view_bounds_grading_keeps_contours_tight_to_layout(self):
        drawn_items = [
            ("SITE", "rectangle", (0, 0, 500, 380)),
            ("BUILDING", "rectangle", (140, 170, 230, 240)),
            ("PARKING", "rectangle", (120, 120, 260, 165)),
            ("FG_CONTOUR", "polyline", (105, 110, 275, 255)),
            ("EG_CONTOUR", "polyline", (110, 118, 268, 248)),
            ("DRAIN_FLOW", "polyline", (70, 50, 430, 320)),
        ]

        selected = _choose_view_bounds(drawn_items, engineering_profile="grading")

        self.assertEqual(selected, (105, 110, 275, 255))

    def test_choose_view_bounds_grading_does_not_collapse_back_to_base_engineering(self):
        drawn_items = [
            ("SITE", "rectangle", (0, 0, 780, 780)),
            ("BUILDING", "rectangle", (165, 440, 615, 572)),
            ("PARKING", "rectangle", (180, 430, 626, 560)),
            ("FG_CONTOUR", "polyline", (0, 390, 780, 650)),
            ("EG_CONTOUR", "polyline", (0, 390, 780, 650)),
            ("DRAIN", "circle", (300, 470, 305, 475)),
            ("PIPE", "polyline", (305, 475, 360, 500)),
        ]

        selected = _choose_view_bounds(drawn_items, engineering_profile="grading")

        self.assertEqual(selected, (0, 390, 780, 650))

    def test_choose_view_bounds_grading_returns_phase_frame_even_when_not_tighter(self):
        drawn_items = [
            ("BUILDING", "rectangle", (165, 440, 615, 572)),
            ("PARKING", "rectangle", (180, 430, 626, 560)),
            ("FG_CONTOUR", "polyline", (0, 390, 780, 650)),
            ("EG_CONTOUR", "polyline", (0, 390, 780, 650)),
        ]

        selected = _choose_view_bounds(drawn_items, engineering_profile="grading")

        self.assertEqual(selected, (0, 390, 780, 650))

    def test_choose_view_bounds_grading_includes_spot_grade_cluster(self):
        drawn_items = [
            ("SITE", "rectangle", (0, 0, 500, 380)),
            ("BUILDING", "rectangle", (140, 170, 230, 240)),
            ("PARKING", "rectangle", (120, 120, 260, 165)),
            ("FG_CONTOUR", "polyline", (118, 118, 270, 252)),
            ("SPOT_FG", "text_note", (132, 132, 132, 132)),
            ("SPOT_FG", "text_note", (252, 238, 252, 238)),
            ("DRAIN_FLOW", "polyline", (70, 50, 430, 320)),
        ]

        selected = _choose_view_bounds(drawn_items, engineering_profile="grading")

        self.assertEqual(selected, (118, 118, 270, 252))

    def test_choose_view_bounds_drainage_prefers_on_site_drain_network(self):
        drawn_items = [
            ("SITE", "rectangle", (0, 0, 500, 380)),
            ("BUILDING", "rectangle", (140, 170, 230, 240)),
            ("PARKING", "rectangle", (120, 120, 260, 165)),
            ("DRAIN", "circle", (150, 135, 155, 140)),
            ("DRAIN", "polyline", (132, 118, 235, 176)),
            ("DRAIN_FLOW", "polyline", (126, 124, 240, 188)),
            ("PIPE", "polyline", (235, 150, 430, 96)),
            ("BASIN_BOUNDARY", "polygon", (380, 70, 470, 150)),
        ]

        selected = _choose_view_bounds(drawn_items, engineering_profile="drainage")

        self.assertEqual(selected, (120, 118, 260, 240))

    def test_grading_preview_keeps_nearby_contour_labels_outside_layout_band(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [165, 440], "width": 110, "height": 58},
            {"layer": "PARKING", "task": "rectangle", "origin": [180, 430], "width": 446, "height": 130},
            {"layer": "FG_CONTOUR", "task": "polyline", "points": [[0, 390], [780, 390]]},
            {"layer": "FG_CONTOUR", "task": "text_note", "origin": [0, 390], "text": "FG 102.06"},
        ]

        filtered = _filtered_preview_actions(actions, rich_engineering="grading")
        contour_texts = [
            str(action.get("text") or "")
            for action in filtered
            if str(action.get("layer") or "").upper() == "FG_CONTOUR"
            and str(action.get("task") or "").lower() == "text_note"
        ]

        self.assertIn("FG 102.06", contour_texts)

    def test_layout_scene_suppresses_engineering_overlay_noise(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [20, 60], "width": 12, "height": 8},
            {"layer": "ROAD", "task": "rectangle", "label": "DRIVE", "origin": [10, 20], "width": 80, "height": 8},
            {"layer": "PARKING", "task": "rectangle", "origin": [16, 40], "width": 58, "height": 10},
            {"layer": "ANNO", "task": "text_note", "text": 'PIPE-1 12" INV 98.52->98.24'},
            {"layer": "PIPE", "task": "polyline", "label": "PIPE-1", "points": [[30, 36], [45, 44], [58, 52]]},
            {"layer": "BASIN_BOUNDARY", "task": "circle", "label": "BASIN-A", "center": [70, 48], "radius": 6},
            {"layer": "UTILITY", "task": "polyline", "label": "generic_utility_1"},
            {"layer": "WATER", "task": "polyline", "label": "WATER MAIN", "points": [[18, 32], [45, 32], [72, 34]]},
            {"layer": "STRUCTURE", "task": "circle", "label": "INLET-1", "center": [58, 52], "radius": 2.5},
            {"layer": "FG_CONTOUR", "task": "polyline", "label": "FG-101"},
        ]

        filtered = _filtered_preview_actions(actions)
        kept_layers = [str(action.get("layer") or "").upper() for action in filtered]

        self.assertIn("BUILDING", kept_layers)
        self.assertNotIn("ROAD", kept_layers)
        self.assertIn("PAVEMENT", kept_layers)
        self.assertNotIn("ANNO", kept_layers)
        self.assertIn("PIPE", kept_layers)
        self.assertIn("BASIN_BOUNDARY", kept_layers)
        self.assertNotIn("UTILITY", kept_layers)
        self.assertIn("WATER", kept_layers)
        self.assertIn("STRUCTURE", kept_layers)
        self.assertNotIn("FG_CONTOUR", kept_layers)
        self.assertIn("PARKING", kept_layers)
        self.assertNotIn("FIRE", kept_layers)

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
        self.assertFalse(
            any(
                str(action.get("layer") or "").upper() == "PAVEMENT"
                and str(action.get("task") or "").lower() == "rectangle"
                and action.get("origin") == [10, 20]
                for action in filtered
            )
        )

    def test_layout_scene_suppresses_thin_fire_bars_near_buildings(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [20, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 2", "origin": [40, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 3", "origin": [60, 60], "width": 12, "height": 8},
            {"layer": "PARKING", "task": "rectangle", "origin": [16, 40], "width": 58, "height": 10},
            {"layer": "FIRE", "task": "rectangle", "origin": [14, 35], "width": 62, "height": 6},
        ]

        filtered = _filtered_preview_actions(actions)
        kept_fire_rectangles = [
            action
            for action in filtered
            if str(action.get("layer") or "").upper() == "FIRE"
            and str(action.get("task") or "").lower() == "rectangle"
        ]

        self.assertEqual(len(kept_fire_rectangles), 0)

    def test_layout_scene_suppresses_oversized_diagonal_engineering_lines(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [20, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 2", "origin": [40, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 3", "origin": [60, 60], "width": 12, "height": 8},
            {"layer": "PARKING", "task": "rectangle", "origin": [16, 40], "width": 58, "height": 10},
            {"layer": "PIPE", "task": "polyline", "points": [[5, 95], [50, 18], [95, 95]], "label": "PIPE-1"},
            {"layer": "WATER", "task": "polyline", "points": [[5, 95], [95, 15]], "label": "WATER MAIN"},
            {"layer": "STORM", "task": "polyline", "points": [[5, 20], [50, 18], [95, 20]], "label": "STORM-1"},
        ]

        filtered = _filtered_preview_actions(actions)
        kept_engineering = [
            action
            for action in filtered
            if str(action.get("layer") or "").upper() in {"PIPE", "WATER", "STORM"}
        ]

        self.assertEqual(len(kept_engineering), 0)

    def test_layout_scene_keeps_drainage_overlay_geometry(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [20, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 2", "origin": [40, 60], "width": 12, "height": 8},
            {"layer": "PARKING", "task": "rectangle", "origin": [16, 40], "width": 42, "height": 10},
            {"layer": "DRAIN", "task": "polyline", "label": "SWALE-1", "points": [[24, 38], [34, 30], [48, 24]]},
            {"layer": "PIPE", "task": "polyline", "label": "PIPE-1", "points": [[28, 36], [42, 28], [54, 24]]},
            {"layer": "BASIN_BOUNDARY", "task": "polygon", "label": "BASIN-A", "points": [[58, 18], [68, 18], [70, 12], [56, 12], [58, 18]]},
        ]

        filtered = _filtered_preview_actions(actions)
        kept_layers = [str(action.get("layer") or "").upper() for action in filtered]

        self.assertIn("DRAIN", kept_layers)
        self.assertIn("PIPE", kept_layers)
        self.assertIn("BASIN_BOUNDARY", kept_layers)

    def test_layout_scene_keeps_multiple_drainage_lines_when_they_are_on_site(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [20, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 2", "origin": [40, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 3", "origin": [60, 60], "width": 12, "height": 8},
            {"layer": "PARKING", "task": "rectangle", "origin": [16, 40], "width": 58, "height": 10},
            {"layer": "DRAIN", "task": "polyline", "label": "SWALE-1", "points": [[18, 42], [28, 34], [40, 28]]},
            {"layer": "DRAIN", "task": "polyline", "label": "SWALE-2", "points": [[42, 40], [50, 32], [58, 28]]},
            {"layer": "PIPE", "task": "polyline", "label": "P-1", "points": [[30, 36], [42, 28], [54, 22]]},
            {"layer": "PIPE", "task": "polyline", "label": "P-2", "points": [[54, 36], [60, 30], [68, 22]]},
            {"layer": "BASIN_BOUNDARY", "task": "polygon", "label": "BASIN-A", "points": [[70, 18], [80, 18], [82, 10], [68, 10], [70, 18]]},
        ]

        filtered = _filtered_preview_actions(actions)
        kept_engineering = [
            action
            for action in filtered
            if str(action.get("layer") or "").upper() in {"DRAIN", "PIPE", "BASIN_BOUNDARY"}
        ]

        self.assertGreaterEqual(len(kept_engineering), 5)

    def test_layout_scene_dedupes_overlapping_primary_building_shapes(self):
        actions = [
            {"layer": "BUILDING", "task": "polygon", "label": "BLDG 1", "points": [[20, 60], [32, 60], [32, 68], [20, 68], [20, 60]]},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [20, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 2", "origin": [40, 60], "width": 12, "height": 8},
            {"layer": "PARKING", "task": "rectangle", "origin": [16, 40], "width": 58, "height": 10},
        ]

        filtered = _filtered_preview_actions(actions)
        kept_buildings = [
            action
            for action in filtered
            if str(action.get("layer") or "").upper() == "BUILDING"
            and str(action.get("task") or "").lower() in {"rectangle", "polygon"}
        ]

        self.assertEqual(len(kept_buildings), 2)

    def test_completed_layout_scene_keeps_richer_engineering_context(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [20, 60], "width": 12, "height": 8},
            {"layer": "PARKING", "task": "rectangle", "origin": [16, 40], "width": 58, "height": 10},
            {"layer": "DRAIN", "task": "polyline", "label": "SWALE-1", "points": [[18, 42], [28, 34], [40, 28]]},
            {"layer": "PIPE", "task": "polyline", "label": "P-1", "points": [[30, 36], [42, 28], [54, 22]]},
            {"layer": "DRAIN_FLOW", "task": "polyline", "label": "FLOW-1", "points": [[26, 54], [34, 44], [44, 34]]},
            {"layer": "FG_CONTOUR", "task": "polyline", "label": "FG-1", "points": [[14, 72], [40, 70], [78, 68]]},
            {"layer": "BASIN_BOUNDARY", "task": "polygon", "label": "BASIN-A", "points": [[70, 18], [80, 18], [82, 10], [68, 10], [70, 18]]},
        ]

        filtered = _filtered_preview_actions(actions, rich_engineering=True)
        kept_layers = [str(action.get("layer") or "").upper() for action in filtered]

        self.assertIn("DRAIN_FLOW", kept_layers)
        self.assertIn("FG_CONTOUR", kept_layers)

    def test_grading_checkpoint_keeps_contour_context_without_flow_lines(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [20, 60], "width": 12, "height": 8},
            {"layer": "PARKING", "task": "rectangle", "origin": [16, 40], "width": 58, "height": 10},
            {"layer": "PIPE", "task": "polyline", "label": "P-1", "points": [[30, 36], [42, 28], [54, 22]]},
            {"layer": "BASIN_BOUNDARY", "task": "polygon", "label": "BASIN-A", "points": [[70, 18], [80, 18], [82, 10], [68, 10], [70, 18]]},
            {"layer": "FG_CONTOUR", "task": "polyline", "label": "FG-1", "points": [[14, 72], [40, 70], [78, 68]]},
            {"layer": "FG_CONTOUR", "task": "polyline", "label": "FG-2", "points": [[14, 92], [40, 90], [78, 88]]},
            {"layer": "EG_CONTOUR", "task": "polyline", "label": "EG-1", "points": [[14, 64], [40, 62], [78, 60]]},
            {"layer": "FG_CONTOUR", "task": "text_note", "text": "FG 101.5", "origin": [12, 74]},
            {"layer": "EG_CONTOUR", "task": "text_note", "text": "EG 100.9", "origin": [12, 66]},
            {"layer": "SPOT_FG", "task": "text_note", "text": "101.2", "origin": [28, 58]},
            {"layer": "SPOT_FG", "task": "text_note", "text": "100.8", "origin": [52, 48]},
            {"layer": "DRAIN_FLOW", "task": "polyline", "label": "FLOW-1", "points": [[26, 54], [34, 44], [44, 34]]},
        ]

        filtered = _filtered_preview_actions(actions, rich_engineering="grading")
        kept_layers = [str(action.get("layer") or "").upper() for action in filtered]
        spot_texts = [
            str(action.get("text") or "")
            for action in filtered
            if str(action.get("layer") or "").upper() == "SPOT_FG"
        ]
        contour_texts = [
            str(action.get("text") or "")
            for action in filtered
            if str(action.get("layer") or "").upper() in {"FG_CONTOUR", "EG_CONTOUR"}
            and str(action.get("task") or "").lower() == "text_note"
        ]

        self.assertIn("FG_CONTOUR", kept_layers)
        self.assertIn("EG_CONTOUR", kept_layers)
        self.assertIn("SPOT_FG", kept_layers)
        self.assertGreaterEqual(kept_layers.count("FG_CONTOUR"), 3)
        self.assertIn("101.2", spot_texts)
        self.assertIn("100.8", spot_texts)
        self.assertIn("FG 101.5", contour_texts)
        self.assertIn("EG 100.9", contour_texts)
        self.assertNotIn("DRAIN_FLOW", kept_layers)
        self.assertNotIn("PIPE", kept_layers)
        self.assertNotIn("BASIN_BOUNDARY", kept_layers)

    def test_drainage_checkpoint_keeps_flow_context(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [20, 60], "width": 12, "height": 8},
            {"layer": "PARKING", "task": "rectangle", "origin": [16, 40], "width": 58, "height": 10},
            {"layer": "DRAIN", "task": "circle", "label": "INLET-1", "center": [28, 34], "radius": 2},
            {"layer": "DRAIN", "task": "polyline", "label": "SWALE-1", "points": [[18, 42], [28, 34], [40, 28]]},
            {"layer": "DRAIN", "task": "text_note", "text": "INLET-1", "origin": [30, 36]},
            {"layer": "PIPE", "task": "polyline", "label": "P-1", "points": [[30, 36], [42, 28], [54, 22]]},
            {"layer": "BASIN_BOUNDARY", "task": "polygon", "label": "BASIN-A", "points": [[70, 18], [80, 18], [82, 10], [68, 10], [70, 18]]},
            {"layer": "DRAIN_FLOW", "task": "polyline", "label": "FLOW-1", "points": [[26, 54], [34, 44], [44, 34]]},
            {"layer": "FG_CONTOUR", "task": "polyline", "label": "FG-1", "points": [[14, 72], [40, 70], [78, 68]]},
        ]

        filtered = _filtered_preview_actions(actions, rich_engineering="drainage")
        kept_layers = [str(action.get("layer") or "").upper() for action in filtered]
        drain_texts = [
            str(action.get("text") or "")
            for action in filtered
            if str(action.get("layer") or "").upper() == "DRAIN"
            and str(action.get("task") or "").lower() == "text_note"
        ]

        self.assertIn("DRAIN", kept_layers)
        self.assertIn("DRAIN_FLOW", kept_layers)
        self.assertNotIn("PIPE", kept_layers)
        self.assertNotIn("BASIN_BOUNDARY", kept_layers)
        self.assertNotIn("FG_CONTOUR", kept_layers)
        self.assertIn("INLET-1", drain_texts)

    def test_storm_pipe_checkpoint_keeps_pipe_and_basin_context(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [20, 60], "width": 12, "height": 8},
            {"layer": "PARKING", "task": "rectangle", "origin": [16, 40], "width": 58, "height": 10},
            {"layer": "DRAIN", "task": "polyline", "label": "SWALE-1", "points": [[18, 42], [28, 34], [40, 28]]},
            {"layer": "PIPE", "task": "polyline", "label": "P-1", "points": [[30, 36], [42, 28], [54, 22]]},
            {"layer": "BASIN_BOUNDARY", "task": "polygon", "label": "BASIN-A", "points": [[70, 18], [80, 18], [82, 10], [68, 10], [70, 18]]},
            {"layer": "DRAIN_FLOW", "task": "polyline", "label": "FLOW-1", "points": [[26, 54], [34, 44], [44, 34]]},
        ]

        filtered = _filtered_preview_actions(actions, rich_engineering="storm")
        kept_layers = [str(action.get("layer") or "").upper() for action in filtered]

        self.assertIn("DRAIN", kept_layers)
        self.assertIn("PIPE", kept_layers)
        self.assertIn("BASIN_BOUNDARY", kept_layers)

    def test_layout_scene_suppresses_diagonal_schematic_road_and_fire_shapes(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [20, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 2", "origin": [40, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 3", "origin": [60, 60], "width": 12, "height": 8},
            {"layer": "PARKING", "task": "rectangle", "origin": [16, 40], "width": 58, "height": 10},
            {"layer": "ROAD", "task": "polyline", "points": [[6, 95], [50, 18], [94, 95]]},
            {"layer": "FIRE", "task": "polyline", "points": [[6, 18], [50, 18], [94, 18], [50, 95], [6, 18]]},
            {"layer": "FIRE", "task": "rectangle", "origin": [82, 14], "width": 8, "height": 92},
        ]

        filtered = _filtered_preview_actions(actions)
        kept_schematic = [
            action
            for action in filtered
            if str(action.get("layer") or "").upper() in {"ROAD", "FIRE"}
        ]

        self.assertEqual(kept_schematic, [])

    def test_layout_scene_suppresses_structure_point_markers(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [20, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 2", "origin": [40, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 3", "origin": [60, 60], "width": 12, "height": 8},
            {"layer": "PARKING", "task": "rectangle", "origin": [16, 40], "width": 58, "height": 10},
            {"layer": "STRUCTURE", "task": "point", "origin": [5, 90], "label": "MH-1"},
            {"layer": "STRUCTURE", "task": "point", "origin": [6, 15], "label": "INLET-1"},
            {"layer": "STRUCTURE", "task": "circle", "center": [72, 34], "radius": 2.5, "label": "INLET-A"},
        ]

        filtered = _filtered_preview_actions(actions)
        kept_structure_tasks = [
            str(action.get("task") or "").lower()
            for action in filtered
            if str(action.get("layer") or "").upper() == "STRUCTURE"
        ]

        self.assertNotIn("point", kept_structure_tasks)
        self.assertIn("circle", kept_structure_tasks)

    def test_layout_scene_suppresses_tiny_engineering_marker_circles(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [20, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 2", "origin": [40, 60], "width": 12, "height": 8},
            {"layer": "PARKING", "task": "rectangle", "origin": [16, 40], "width": 42, "height": 10},
            {"layer": "STRUCTURE", "task": "circle", "center": [5, 90], "radius": 0.8, "label": ""},
            {"layer": "STRUCTURE", "task": "circle", "center": [72, 34], "radius": 2.5, "label": "INLET-A"},
        ]

        filtered = _filtered_preview_actions(actions)
        kept_structure_circles = [
            action
            for action in filtered
            if str(action.get("layer") or "").upper() == "STRUCTURE"
            and str(action.get("task") or "").lower() == "circle"
        ]

        self.assertEqual(len(kept_structure_circles), 1)
        self.assertEqual(kept_structure_circles[0].get("label"), "INLET-A")

    def test_layout_scene_suppresses_route_lines_and_route_points(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [20, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 2", "origin": [40, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 3", "origin": [60, 60], "width": 12, "height": 8},
            {"layer": "PARKING", "task": "rectangle", "origin": [16, 40], "width": 58, "height": 10},
            {"layer": "ROUTE", "task": "polyline", "points": [[5, 90], [50, 15], [95, 90]], "label": "SECTION CUT"},
            {"layer": "ROUTE", "task": "point", "origin": [6, 88], "label": "SEC 10+00"},
            {"layer": "ROUTE", "task": "point", "origin": [8, 14], "label": "SEC 12+00"},
        ]

        filtered = _filtered_preview_actions(actions)
        kept_route_layers = [
            str(action.get("layer") or "").upper()
            for action in filtered
            if str(action.get("layer") or "").upper() == "ROUTE"
        ]

        self.assertEqual(kept_route_layers, [])

    def test_layout_scene_suppresses_long_cross_site_engineering_span(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 1", "origin": [30, 60], "width": 12, "height": 8},
            {"layer": "BUILDING", "task": "rectangle", "label": "BLDG 2", "origin": [50, 60], "width": 12, "height": 8},
            {"layer": "PARKING", "task": "rectangle", "origin": [26, 40], "width": 40, "height": 10},
            {"layer": "PIPE", "task": "polyline", "points": [[42, 25], [92, 15]], "label": "PIPE-2"},
        ]

        filtered = _filtered_preview_actions(actions)
        kept_pipe = [
            action
            for action in filtered
            if str(action.get("layer") or "").upper() == "PIPE"
        ]

        self.assertEqual(kept_pipe, [])

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
        self.assertNotIn("FIRE", kept_layers)

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
        self.assertEqual(len(fire_rectangles), 0)
        self.assertLessEqual(float(pavement_rectangles[0].get("width") or 0.0), 180.0)
        self.assertTrue(
            any(
                420.0 <= float(action.get("origin", [0.0])[0]) <= 450.0
                and float(action.get("width") or 0.0) >= 100.0
                for action in pavement_rectangles
            ),
            "expected synthesized retail collector pavement to remain near the lower parking cluster",
        )
        self.assertFalse(
            any(
                float(action.get("width") or 0.0) <= 20.0
                and float(action.get("height") or 0.0) > 100.0
                and 300.0 <= float(action.get("origin", [0.0])[0]) <= 680.0
                for action in pavement_rectangles
            ),
            "did not expect a tall thin synthetic connector stem through the center of the layout",
        )
        self.assertTrue(
            all(str(action.get("layer") or "").upper() != "FIRE" for action in filtered),
            "did not expect synthetic pavement aisles to be duplicated into fire overlays",
        )
        self.assertTrue(
            any(
                float(action.get("width") or 0.0) >= 100.0
                and float(action.get("height") or 0.0) <= 18.0
                and 180.0 <= float(action.get("origin", [0.0])[0]) <= 760.0
                for action in pavement_rectangles
            ),
            "expected synthesized collector pavement to remain near the parking clusters",
        )

    def test_layout_scene_suppresses_isolated_pavement_stem(self):
        actions = [
            {"layer": "BUILDING", "task": "rectangle", "origin": [220, 700], "width": 120, "height": 60, "label": "BLDG 1"},
            {"layer": "BUILDING", "task": "rectangle", "origin": [410, 700], "width": 120, "height": 60, "label": "BLDG 2"},
            {"layer": "PARKING", "task": "rectangle", "origin": [200, 560], "width": 160, "height": 70},
            {"layer": "PARKING", "task": "rectangle", "origin": [390, 560], "width": 160, "height": 70},
            {"layer": "PAVEMENT", "task": "rectangle", "origin": [815, 210], "width": 10, "height": 220},
        ]

        filtered = _filtered_preview_actions(actions)
        kept_isolated = [
            action
            for action in filtered
            if str(action.get("layer") or "").upper() == "PAVEMENT"
            and action.get("origin") == [815, 210]
        ]

        self.assertEqual(kept_isolated, [])


if __name__ == "__main__":
    unittest.main()
