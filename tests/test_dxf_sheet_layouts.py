import tempfile
import unittest
from pathlib import Path

import ezdxf

from output.dxf_exporter import save_dxf
from planner import build_plan


def _sheet_test_plan():
    return build_plan(
        {
            "project_name": "DXF Sheet Test",
            "units": "ft",
            "mode": "site_plan",
            "project_type": "commercial_pad",
            "site_type": "commercial_pad",
            "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
            "setback": 10.0,
            "street_edge": "bottom",
            "layout_strategy": "front_parking",
            "site_plan": {"parking_count": 24},
            "deliverables": ["road_profile", "cross_sections", "sanitary_plan", "storm_pipe_plan"],
            "meta": {"input_mode": "manual", "source_input_mode": "manual", "manual_mode": True},
        }
    )


class DxfSheetLayoutsTest(unittest.TestCase):
    def test_modelspace_prefers_layout_layers_over_detail_noise(self) -> None:
        plan = _sheet_test_plan()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "modelspace-clean-test.dxf"
            save_dxf(plan, filename=str(path))

            doc = ezdxf.readfile(path)
            modelspace_layers = {entity.dxf.layer for entity in doc.modelspace()}

            self.assertIn("BUILDING", modelspace_layers)
            self.assertTrue({"ROAD", "PAVEMENT", "PARKING", "WALK"} & modelspace_layers)
            self.assertNotIn("DRAIN_FLOW", modelspace_layers)
            self.assertNotIn("SPOT_FG", modelspace_layers)
            self.assertNotIn("LOW_POINTS", modelspace_layers)

    def test_modelspace_suppresses_wrapper_and_schematic_access_geometry(self) -> None:
        plan = _sheet_test_plan()
        actions = plan.setdefault("actions", [])
        actions.extend(
            [
                {"layer": "ROAD", "task": "rectangle", "origin": [8, 18], "width": 88, "height": 74},
                {"layer": "ROAD", "task": "circle", "center": [12, 44], "radius": 16},
                {"layer": "ROAD", "task": "polyline", "points": [[52, -8], [52, 18], [52, 54]]},
                {"layer": "WATER", "task": "polyline", "points": [[0, 0], [100, 0]]},
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "modelspace-wrapper-filter-test.dxf"
            save_dxf(plan, filename=str(path))

            doc = ezdxf.readfile(path)
            modelspace_layers = [entity.dxf.layer for entity in doc.modelspace()]

            self.assertNotIn("WATER", modelspace_layers)
            self.assertIn("BUILDING", modelspace_layers)

    def test_modelspace_keeps_curated_storm_context_in_layout_scene(self) -> None:
        plan = _sheet_test_plan()
        actions = plan.setdefault("actions", [])
        actions.extend(
            [
                {"layer": "BASIN_BOUNDARY", "task": "circle", "center": [110, 82], "radius": 10, "label": "BASIN-A"},
                {"layer": "PIPE", "task": "polyline", "points": [[30, 40], [65, 55], [100, 75]], "label": "PIPE-1"},
                {"layer": "STRUCTURE", "task": "circle", "center": [100, 75], "radius": 2.5, "label": "INLET-1"},
                {"layer": "UTILITY", "task": "polyline", "points": [[0, 0], [100, 0]], "label": "generic_utility_1"},
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "modelspace-curated-storm-test.dxf"
            save_dxf(plan, filename=str(path))

            doc = ezdxf.readfile(path)
            modelspace_layers = {entity.dxf.layer for entity in doc.modelspace()}

            self.assertIn("BUILDING", modelspace_layers)
            self.assertIn("PIPE", modelspace_layers)
            self.assertIn("STRUCTURE", modelspace_layers)
            self.assertIn("BASIN_BOUNDARY", modelspace_layers)
            self.assertNotIn("UTILITY", modelspace_layers)

    def test_profiles_and_sections_keep_canonical_context(self) -> None:
        plan = _sheet_test_plan()
        profiles = ((plan.get("meta") or {}).get("profiles") or [])
        sections = ((plan.get("meta") or {}).get("cross_sections") or [])

        self.assertTrue(profiles)
        self.assertTrue(sections)
        self.assertTrue(all("alignment_owner" in row for row in profiles))
        self.assertTrue(all("source_system" in row for row in profiles))
        self.assertTrue(all("preferred_corridor" in row for row in profiles))
        self.assertTrue(all("grading_context" in row for row in profiles))
        self.assertTrue(all("protected_zone_context" in row for row in profiles))
        self.assertTrue(all("structure_marks" in row for row in profiles))
        self.assertTrue(all("pipe_band_records" in row for row in profiles if row.get("alignment_type") != "roadway"))
        self.assertTrue(all("alignment_owner" in row for row in sections))
        self.assertTrue(all("section_context" in row for row in sections))
        self.assertTrue(all("feature_types" in (row.get("section_context") or {}) for row in sections))
        self.assertTrue(all("feature_runs" in (row.get("section_context") or {}) for row in sections))
        self.assertTrue(all("modeled_widths" in (row.get("section_context") or {}) for row in sections))

    def test_save_dxf_creates_sheet_layouts(self) -> None:
        plan = _sheet_test_plan()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sheet-test.dxf"
            save_dxf(plan, filename=str(path))

            doc = ezdxf.readfile(path)
            layout_names = [layout.name for layout in doc.layouts]

            self.assertIn("SITE PLAN", layout_names)
            self.assertTrue(any(name.startswith("PROFILE") for name in layout_names))
            self.assertTrue(any(name.startswith("CROSS SECTIONS") for name in layout_names))
            self.assertGreater(len(doc.modelspace()), 0)
            self.assertIn("CIVIL_NORTH_ARROW", doc.blocks)
            self.assertIn("CIVIL_MANHOLE", doc.blocks)
            self.assertIn("CIVIL-NARROW", doc.styles)
            audit = ((plan.get("meta") or {}).get("export_audit") or {})
            self.assertTrue(audit.get("success"))
            self.assertEqual(audit.get("sheet_total"), len([name for name in layout_names if name != "Model"]))
            self.assertIn("CIVIL_NORTH_ARROW", audit.get("block_definitions") or [])
            self.assertTrue(audit.get("sheet_registry_matches_outputs"))
            self.assertTrue((audit.get("canonical_sheet_alignment") or {}).get("profile_alignment"))
            self.assertTrue((audit.get("canonical_sheet_alignment") or {}).get("section_alignment"))
            self.assertTrue((audit.get("requested_vs_produced") or {}).get("profile_deliverable_consistent"))
            self.assertTrue((audit.get("requested_vs_produced") or {}).get("section_deliverable_consistent"))
            self.assertTrue(audit.get("legend_matches_content"))
            self.assertTrue((audit.get("canonical_sheet_alignment") or {}).get("site_callouts_canonical"))
            self.assertTrue((audit.get("canonical_sheet_alignment") or {}).get("sheet_element_alignment_complete"))
            self.assertTrue(audit.get("sheet_metadata_consistent"))
            self.assertTrue(audit.get("sheet_registry_meta_matches_plan"))
            self.assertTrue(audit.get("title_block_metadata_complete"))
            self.assertTrue(audit.get("sheet_registry_order_consistent"))

    def test_profile_and_section_sheets_contain_drafting_entities(self) -> None:
        plan = _sheet_test_plan()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sheet-content-test.dxf"
            save_dxf(plan, filename=str(path))

            doc = ezdxf.readfile(path)
            profile_layout = next(layout for layout in doc.layouts if layout.name.startswith("PROFILE"))
            section_layout = next(layout for layout in doc.layouts if layout.name.startswith("CROSS SECTIONS"))

            profile_layers = {entity.dxf.layer for entity in profile_layout}
            section_layers = {entity.dxf.layer for entity in section_layout}

            self.assertIn("GRID", profile_layers)
            self.assertIn("AXIS", profile_layers)
            self.assertTrue({"EG_CONTOUR", "FG_CONTOUR"} & profile_layers)
            self.assertIn("TITLE", profile_layers)
            self.assertIn("SHEET", profile_layers)
            self.assertIn("STRUCTURE", profile_layers)
            self.assertIn("DIM", section_layers)

            self.assertIn("GRID", section_layers)
            self.assertIn("AXIS", section_layers)
            self.assertIn("FG_CONTOUR", section_layers)
            self.assertIn("TITLE", section_layers)

    def test_site_plan_sheet_contains_summary_and_legend_annotation(self) -> None:
        plan = _sheet_test_plan()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "site-sheet-test.dxf"
            save_dxf(plan, filename=str(path))

            doc = ezdxf.readfile(path)
            site_layout = next(layout for layout in doc.layouts if layout.name == "SITE PLAN")
            site_layers = {entity.dxf.layer for entity in site_layout}

            self.assertIn("TITLE", site_layers)
            self.assertIn("SHEET", site_layers)
            self.assertIn("SYMBOL", site_layers)
            self.assertIn("VIEWPORT", site_layers)
            self.assertIn("STRUCTURE", site_layers)


if __name__ == "__main__":
    unittest.main()
