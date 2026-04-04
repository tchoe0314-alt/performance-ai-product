import unittest

from planner import build_plan
from output.dxf_exporter import _site_plan_drainage_guidance_notes, _site_plan_summary_rows


class ExportPackagingRichnessTest(unittest.TestCase):
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
        self.assertTrue(any("UTILITY CORRIDOR" in note for note in notes))
        self.assertTrue(any("UTILITY COORDINATION" in note for note in notes))
        self.assertTrue(any("UTILITY CLEARANCE REVIEW" in note for note in notes))
        self.assertTrue(any("CONVERGENCE REVIEW" in note for note in notes))
        self.assertTrue(any("DELIVERABLE REVIEW" in note for note in notes))
        self.assertTrue(any("RERUN FOCUS" in note for note in notes))
        self.assertTrue(any("RELEASE READINESS" in note for note in notes))


if __name__ == "__main__":
    unittest.main()
