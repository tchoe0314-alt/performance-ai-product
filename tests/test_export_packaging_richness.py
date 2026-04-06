import unittest

import planner
from planner import build_plan
from output.dxf_exporter import _site_plan_drainage_guidance_notes, _site_plan_summary_rows


class ExportPackagingRichnessTest(unittest.TestCase):
    def test_multi_building_program_keeps_multiple_building_footprints_in_preview_plan(self) -> None:
        plan = build_plan(
            {
                "project_name": "Mixed Use Preview Test",
                "units": "ft",
                "mode": "site_plan",
                "project_type": "mixed_use",
                "site_type": "mixed_use",
                "lot": {"x": 0.0, "y": 0.0, "w": 978.9, "h": 978.9},
                "setback": 15.0,
                "street_edge": "bottom",
                "layout_strategy": "balanced",
                "site_plan": {"building_width": 120.0, "building_depth": 60.0, "parking_count": 0},
                "buildings": [
                    {"name": "Building 1", "use": "multifamily", "w": 120.0, "d": 60.0},
                    {"name": "Building 2", "use": "multifamily", "w": 120.0, "d": 60.0},
                    {"name": "Building 3", "use": "multifamily", "w": 120.0, "d": 60.0},
                    {"name": "Retail Pad", "use": "retail", "w": 80.0, "d": 50.0},
                ],
                "subdivision": {"acreage": 22.0, "culdesac_count": 2},
                "drainage": {"detention_required": True},
                "meta": {"input_mode": "assisted", "source_input_mode": "prompt"},
            }
        )

        building_rectangles = [
            action
            for action in plan.get("actions") or []
            if str(action.get("layer") or "").upper() == "BUILDING"
            and str(action.get("task") or "").lower() == "rectangle"
        ]
        road_shapes = [
            action
            for action in plan.get("actions") or []
            if str(action.get("layer") or "").upper() == "ROAD"
            and str(action.get("task") or "").lower() in {"polyline", "circle", "rectangle", "polygon"}
        ]
        pavement_shapes = [
            action
            for action in plan.get("actions") or []
            if str(action.get("layer") or "").upper() == "PAVEMENT"
            and str(action.get("task") or "").lower() == "rectangle"
        ]

        self.assertGreaterEqual(len(building_rectangles), 4)
        self.assertTrue(any("BUILDING 1" in str(action.get("label") or "").upper() for action in building_rectangles))
        self.assertTrue(any("RETAIL PAD" in str(action.get("label") or "").upper() for action in building_rectangles))
        self.assertTrue(road_shapes)
        self.assertTrue(pavement_shapes)

    def test_project_model_plan_keeps_site_geometry_when_expanded_plan_is_engineering_heavy(self) -> None:
        project = planner.ProjectModel(name="Preview Context Test", units="ft")
        project.add_zone(planner.rect_zone(0.0, 0.0, 220.0, 160.0, zone_type=planner.ZoneType.SITE, name="LOT"))
        project.add_zone(planner.rect_zone(40.0, 50.0, 80.0, 50.0, zone_type=planner.ZoneType.BUILDING, name="BLDG-1"))
        project.meta["_expanded_plan"] = {
            "project_name": "Expanded Preview",
            "units": "ft",
            "actions": [
                {
                    "task": "polyline",
                    "layer": "PIPE",
                    "points": [[10.0, 10.0], [140.0, 30.0]],
                    "canonical_source_type": "storm_pipe_segment",
                    "canonical_source_id": "PIPE-1",
                }
            ],
        }

        plan = planner.project_model_to_plan(project, "Preview Context Test")
        actions = plan.get("actions") or []

        rect_layers = {str(action.get("layer") or "").upper() for action in actions if str(action.get("task") or "").lower() == "rectangle"}

        self.assertIn("SITE", rect_layers)
        self.assertIn("BUILDING", rect_layers)
        self.assertTrue(
            any(str(action.get("canonical_source_type") or "") == "storm_pipe_segment" for action in actions)
        )

    def test_project_model_plan_hides_generic_site_envelopes_when_real_layout_geometry_exists(self) -> None:
        project = planner.ProjectModel(name="Primary Preview Test", units="ft")
        project.add_zone(planner.rect_zone(0.0, 0.0, 220.0, 160.0, zone_type=planner.ZoneType.SITE, name="SITE"))
        project.add_zone(
            planner.rect_zone(15.0, 15.0, 190.0, 130.0, zone_type=planner.ZoneType.PAD, name="BUILDABLE_AREA")
        )
        project.meta["_expanded_plan"] = {
            "project_name": "Expanded Layout Preview",
            "units": "ft",
            "actions": [
                {"task": "rectangle", "layer": "BUILDING", "origin": [20.0, 30.0], "width": 50.0, "height": 30.0, "label": "BUILDING 1"},
                {"task": "rectangle", "layer": "BUILDING", "origin": [90.0, 30.0], "width": 50.0, "height": 30.0, "label": "BUILDING 2"},
                {"task": "polyline", "layer": "ROAD", "points": [[10.0, 20.0], [200.0, 20.0], [200.0, 120.0], [10.0, 120.0], [10.0, 20.0]]},
                {"task": "rectangle", "layer": "PAVEMENT", "origin": [18.0, 65.0], "width": 124.0, "height": 32.0},
            ],
        }

        plan = planner.project_model_to_plan(project, "Primary Preview Test")
        actions = plan.get("actions") or []

        self.assertFalse(
            any(
                str(action.get("task") or "").lower() == "rectangle"
                and str(action.get("layer") or "").upper() == "SITE"
                for action in actions
            )
        )
        self.assertFalse(
            any(
                str(action.get("task") or "").lower() == "rectangle"
                and str(action.get("layer") or "").upper() == "PAD"
                and str(action.get("label") or "").upper() == "BUILDABLE_AREA"
                for action in actions
            )
        )
        self.assertGreaterEqual(
            len(
                [
                    action
                    for action in actions
                    if str(action.get("layer") or "").upper() == "BUILDING"
                    and str(action.get("task") or "").lower() == "rectangle"
                ]
            ),
            2,
        )

    def test_manual_mode_packages_canonical_engineering_layers_for_export(self) -> None:
        plan = build_plan(
            {
                "project_name": "Export Richness Test",
                "units": "ft",
                "mode": "site_plan",
                "project_type": "commercial_pad",
                "site_type": "commercial_pad",
                "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
                "setback": 10.0,
                "street_edge": "bottom",
                "layout_strategy": "front_parking",
                "site_plan": {"parking_count": 24},
                "meta": {"input_mode": "manual", "source_input_mode": "manual", "manual_mode": True},
            }
        )

        layer_counts = {}
        for action in plan.get("actions") or []:
            layer = str(action.get("layer") or "").upper()
            layer_counts[layer] = layer_counts.get(layer, 0) + 1

        self.assertGreater(layer_counts.get("PIPE", 0), 0)
        self.assertGreater(layer_counts.get("STRUCTURE", 0), 0)
        self.assertGreater(layer_counts.get("UTILITY", 0), 0)
        self.assertGreater(layer_counts.get("BASIN_BOUNDARY", 0), 0)
        pipe_actions = [action for action in plan.get("actions") or [] if str(action.get("layer") or "").upper() == "PIPE"]
        self.assertTrue(pipe_actions)
        self.assertTrue(all(str(action.get("canonical_source_type") or "") == "storm_pipe_segment" for action in pipe_actions))

    def test_engineered_basin_export_uses_computed_geometry_instead_of_symbol_circle(self) -> None:
        plan = build_plan(
            {
                "project_name": "Engineered Basin Export Test",
                "units": "ft",
                "mode": "site_plan",
                "project_type": "commercial_pad",
                "site_type": "commercial_pad",
                "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
                "setback": 10.0,
                "street_edge": "bottom",
                "layout_strategy": "front_parking",
                "site_plan": {"parking_count": 24},
                "meta": {"input_mode": "manual", "source_input_mode": "manual", "manual_mode": True},
            }
        )

        basins = (((plan.get("meta") or {}).get("drainage") or {}).get("basins") or [])
        self.assertTrue(basins)
        self.assertTrue(any((basin.get("boundary_points") or []) for basin in basins))
        self.assertTrue(all("detention_design" in basin for basin in basins))
        primary_basins = [
            basin
            for basin in basins
            if basin.get("engineering_role") == "primary_detention" and basin.get("exportable")
        ]
        self.assertTrue(primary_basins)
        self.assertTrue(all("overflow_spillway" in basin for basin in primary_basins))
        self.assertTrue(all("adequacy_status" in (basin.get("detention_design") or {}) for basin in primary_basins))
        self.assertTrue(all("release_basis" in (basin.get("detention_design") or {}) for basin in primary_basins))
        self.assertTrue(all("target_drawdown_hours" in (basin.get("detention_design") or {}) for basin in primary_basins))
        self.assertTrue(all("assumed_capacity_cfs" in (basin.get("overflow_spillway") or {}) for basin in primary_basins))
        export_validation = (((plan.get("meta") or {}).get("drainage") or {}).get("export_validation") or {})
        self.assertTrue(export_validation.get("ready"))
        self.assertEqual(export_validation.get("primary_basin_count"), len(primary_basins))
        self.assertGreater(export_validation.get("low_point_count", 0), 0)
        self.assertGreater(export_validation.get("flow_path_count", 0), 0)
        self.assertTrue(export_validation.get("grading_export_ready"))

        basin_actions = [
            action for action in plan.get("actions") or []
            if str(action.get("layer") or "").upper() == "BASIN_BOUNDARY"
        ]
        flow_actions = [
            action for action in plan.get("actions") or []
            if str(action.get("canonical_source_type") or "") == "drainage_flow_path"
        ]
        low_point_actions = [
            action for action in plan.get("actions") or []
            if str(action.get("canonical_source_type") or "") == "drainage_low_point"
        ]
        self.assertTrue(basin_actions)
        self.assertTrue(all(str(action.get("task") or "").lower() == "polyline" for action in basin_actions))
        self.assertTrue(any("DETENTION BASIN" in str(action.get("text") or "") for action in plan.get("actions") or []))
        self.assertTrue(flow_actions)
        self.assertTrue(low_point_actions)
        self.assertEqual(
            len({str(action.get("canonical_source_id") or "") for action in basin_actions}),
            len(primary_basins),
        )
        pond_count = ((((plan.get("meta") or {}).get("quantities") or {}).get("totals") or {}).get("pond_count"))
        self.assertEqual(int(pond_count), len(primary_basins))

    def test_sanitary_request_packages_real_san_layer_from_canonical_state(self) -> None:
        plan = build_plan(
            {
                "project_name": "Export Sanitary Richness Test",
                "units": "ft",
                "mode": "site_plan",
                "project_type": "commercial_pad",
                "site_type": "commercial_pad",
                "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
                "setback": 10.0,
                "street_edge": "bottom",
                "layout_strategy": "front_parking",
                "site_plan": {"parking_count": 24},
                "deliverables": ["sanitary_plan"],
                "meta": {"input_mode": "manual", "source_input_mode": "manual", "manual_mode": True},
            }
        )

        layer_counts = {}
        for action in plan.get("actions") or []:
            layer = str(action.get("layer") or "").upper()
            layer_counts[layer] = layer_counts.get(layer, 0) + 1

        self.assertGreater(layer_counts.get("SAN", 0), 0)

    def test_site_plan_summary_and_notes_include_surface_storm_story(self) -> None:
        plan = build_plan(
            {
                "project_name": "Surface Story Test",
                "units": "ft",
                "mode": "site_plan",
                "project_type": "commercial_pad",
                "site_type": "commercial_pad",
                "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
                "setback": 10.0,
                "street_edge": "bottom",
                "layout_strategy": "front_parking",
                "site_plan": {"parking_count": 24},
                "meta": {"input_mode": "manual", "source_input_mode": "manual", "manual_mode": True},
            }
        )

        rows = _site_plan_summary_rows(plan, plan.get("actions") or [])
        notes = _site_plan_drainage_guidance_notes(plan)

        self.assertTrue(any(row and row[0] == "SURFACE" for row in rows))
        self.assertTrue(any(row and row[0] == "STORM" and "T " in str(row[1]) for row in rows))
        self.assertTrue(any(row and row[0] == "GRADING" and "Range" in str(row[1]) for row in rows))
        self.assertTrue(any(row and row[0] == "DRAIN" and "CFS" in str(row[2]) for row in rows))
        self.assertTrue(any(row and row[0] == "BASIN" and "CF" in str(row[1]) for row in rows))
        self.assertTrue(any(row and row[0] == "UTIL" and "Sep" in str(row[1]) for row in rows))
        self.assertTrue(any(row and row[0] == "DELIV" for row in rows))
        self.assertTrue(any(row and row[0] == "OPT" and "Score" in str(row[1]) for row in rows))
        self.assertTrue(any("GRADING CONTROL" in note for note in notes))
        self.assertTrue(any("GRADED CONTROLS" in note for note in notes))
        self.assertTrue(any("SURFACE DRAINAGE GUIDANCE" in note for note in notes))
        self.assertTrue(any("TRIBUTARY SUMMARY" in note for note in notes))
        self.assertTrue(any("STORM ROUTING" in note for note in notes))
        self.assertTrue(any("SELECTED BASIN DESIGN" in note for note in notes))
        self.assertTrue(any("DETENTION STORAGE" in note for note in notes))
        self.assertTrue(any("STORAGE ADEQUACY" in note for note in notes))
        self.assertTrue(any("BASIN GEOMETRY" in note for note in notes))
        self.assertTrue(any("BASIN FOOTPRINT" in note for note in notes))
        self.assertTrue(any("TARGET" in note for note in notes if "BASIN FOOTPRINT" in note))
        self.assertTrue(any("BASIN OVERFLOW" in note for note in notes))
        self.assertTrue(any("OPTIMIZATION REVIEW" in note for note in notes))
        self.assertTrue(any("OPTIMIZATION METRICS" in note for note in notes))
        self.assertTrue(any("UTILITY CORRIDOR" in note for note in notes))
        self.assertTrue(any("UTILITY COORDINATION" in note for note in notes))
        self.assertTrue(any("UTILITY CLEARANCE REVIEW" in note for note in notes))
        self.assertTrue(any("CONVERGENCE REVIEW" in note for note in notes))
        self.assertTrue(any("DELIVERABLE REVIEW" in note for note in notes))
        self.assertTrue(any("RERUN FOCUS" in note for note in notes))
        self.assertTrue(any("RELEASE READINESS" in note for note in notes))


if __name__ == "__main__":
    unittest.main()
