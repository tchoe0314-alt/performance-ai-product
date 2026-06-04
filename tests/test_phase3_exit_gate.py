import tempfile
import unittest
from pathlib import Path

import ezdxf

from output.dxf_exporter import (
    _build_sheet_registry,
    _feature_runs,
    _legend_items,
    _pipe_band_records,
    _section_feature_label,
    save_dxf,
)


def _phase3_export_plan():
    profile = {
        "name": "STORM PROFILE 1",
        "alignment_name": "PIPE-1",
        "alignment_type": "storm_pipe",
        "source_system": "storm",
        "source": "canonical",
        "sheet_title": "UTILITY PROFILE",
        "sheet_name": "STORM PROFILE 1",
        "alignment_points": [[20.0, 20.0], [120.0, 70.0]],
        "stations": [
            {
                "station_ft": 0.0,
                "station_text": "0+00",
                "point": [20.0, 20.0],
                "existing_elev_ft": 101.0,
                "proposed_elev_ft": 102.0,
                "pipe_invert_ft": 96.0,
            },
            {
                "station_ft": 111.8,
                "station_text": "1+11.8",
                "point": [120.0, 70.0],
                "existing_elev_ft": 100.2,
                "proposed_elev_ft": 101.4,
                "pipe_invert_ft": 95.3,
            },
        ],
        "structure_marks": [
            {"label": "IN-1", "station_ft": 0.0, "rim_elev_ft": 102.0, "invert_ft": 96.0},
            {"label": "OUT-1", "station_ft": 111.8, "rim_elev_ft": 101.4, "invert_ft": 95.3},
        ],
        "pipe_band_records": [
            {
                "start_station_ft": 0.0,
                "end_station_ft": 111.8,
                "start_station_text": "0+00",
                "end_station_text": "1+11.8",
                "diameter_in": 18.0,
                "slope_pct": -0.63,
                "from_structure": "IN-1",
                "to_structure": "OUT-1",
                "rim_in_ft": 102.0,
                "rim_out_ft": 101.4,
                "invert_in_ft": 96.0,
                "invert_out_ft": 95.3,
                "cover_in_ft": 6.0,
                "cover_out_ft": 6.1,
                "flow_cfs": 2.4,
                "capacity_cfs": 5.8,
                "capacity_ratio": 0.41,
                "assumed": False,
            }
        ],
    }
    section = {
        "name": "PIPE-1 SECTION 1",
        "alignment_name": "PIPE-1",
        "alignment_type": "storm_pipe",
        "source_system": "storm",
        "sheet_title": "UTILITY CROSS SECTIONS",
        "sheet_name": "PIPE-1 SECTIONS",
        "station_ft": 55.9,
        "station_text": "0+55.9",
        "anchor_point": [70.0, 45.0],
        "cut_line_points": [[62.0, 33.0], [78.0, 57.0]],
        "width_ft": 28.8,
        "samples": [
            {"offset_ft": -14.4, "existing_elev_ft": 101.0, "proposed_elev_ft": 101.5, "feature_type": "section_edge"},
            {"offset_ft": -4.0, "existing_elev_ft": 100.8, "proposed_elev_ft": 101.2, "feature_type": "section_edge"},
            {"offset_ft": 0.0, "existing_elev_ft": 100.7, "proposed_elev_ft": 101.1, "pipe_invert_ft": 95.6, "feature_type": "pipe_centerline"},
            {"offset_ft": 4.0, "existing_elev_ft": 100.8, "proposed_elev_ft": 101.2, "feature_type": "section_edge"},
            {"offset_ft": 14.4, "existing_elev_ft": 101.1, "proposed_elev_ft": 101.6, "feature_type": "section_edge"},
        ],
    }
    return {
        "project_name": "Phase 3 Exit Gate",
        "units": "ft",
        "actions": [
            {"task": "rectangle", "layer": "SITE", "origin": [0.0, 0.0], "width": 160.0, "height": 120.0, "label": "SITE"},
            {
                "task": "polyline",
                "layer": "PIPE",
                "points": [[20.0, 20.0], [120.0, 70.0]],
                "label": "PIPE-1",
                "canonical_source_type": "storm_pipe_segment",
                "canonical_source_id": "storm-1",
                "canonical_source_name": "PIPE-1",
                "canonical_source_stage": "storm_pipes",
            },
        ],
        "meta": {
            "revision": "A",
            "issue_date": "2026-06-04",
            "canonical_model_id": "MODEL-PHASE3",
            "canonical_model_hash": "hash-phase3",
            "profiles": [profile],
            "cross_sections": [section],
            "storm_pipes": {
                "segments": [
                    {
                        "id": "storm-1",
                        "pipe": "PIPE-1",
                        "from": "IN-1",
                        "to": "OUT-1",
                        "length_ft": 111.8,
                        "diameter_in": 18.0,
                        "slope_pct": -0.63,
                        "start_invert": 96.0,
                        "end_invert": 95.3,
                        "cover_start_ft": 6.0,
                        "cover_end_ft": 6.1,
                        "flow_cfs": 2.4,
                        "capacity_cfs": 5.8,
                        "capacity_ratio": 0.41,
                        "source": "canonical_storm_engine",
                    }
                ]
            },
            "deliverables": {
                "requested": ["road_profile", "cross_sections"],
                "produced": ["profiles", "road_profile", "cross_sections"],
            },
        },
    }


class Phase3ExitGateTest(unittest.TestCase):
    def test_profile_bands_use_canonical_pipe_records(self) -> None:
        plan = _phase3_export_plan()
        profile = plan["meta"]["profiles"][0]

        records = _pipe_band_records(plan, profile)

        self.assertEqual(records[0]["from_structure"], "IN-1")
        self.assertEqual(records[0]["to_structure"], "OUT-1")
        self.assertEqual(records[0]["diameter_in"], 18.0)
        self.assertFalse(records[0]["assumed"])

    def test_section_realism_keeps_feature_runs_and_labels(self) -> None:
        section = _phase3_export_plan()["meta"]["cross_sections"][0]

        runs = _feature_runs(section)
        labels = [_section_feature_label(row["feature_type"]) for row in runs]

        self.assertIn("PIPE CL", labels)
        self.assertIn("TIE-IN", labels)
        self.assertGreaterEqual(len(runs), 3)

    def test_sheet_registry_orders_site_profiles_then_sections(self) -> None:
        plan = _phase3_export_plan()
        profiles = plan["meta"]["profiles"]
        section_groups = [[plan["meta"]["cross_sections"][0]]]

        registry = _build_sheet_registry(plan, profiles, section_groups)

        self.assertEqual([row["sheet_kind"] for row in registry], ["site_plan", "profile", "cross_sections"])
        self.assertEqual([row["sheet_number"] for row in registry], [1, 2, 3])
        self.assertTrue(all(row["sheet_total"] == 3 for row in registry))
        self.assertEqual(registry[0]["canonical_model_id"], "MODEL-PHASE3")

    def test_dxf_export_audit_proves_phase3_deliverable_contract(self) -> None:
        plan = _phase3_export_plan()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "phase3-exit.dxf"

            save_dxf(plan, filename=str(path))

            doc = ezdxf.readfile(path)
            audit = plan["meta"]["export_audit"]
            self.assertEqual([layout.name for layout in doc.layouts if layout.name != "Model"], ["SITE PLAN", "PROFILE 1", "CROSS SECTIONS 1"])
            self.assertEqual(audit["sheet_total"], 3)
            self.assertTrue(audit["sheet_registry_order_consistent"])
            self.assertTrue(audit["title_block_metadata_complete"])
            self.assertTrue(audit["sheet_registry_matches_outputs"])
            self.assertTrue(audit["canonical_sheet_alignment"]["profile_alignment"])
            self.assertTrue(audit["canonical_sheet_alignment"]["section_alignment"])
            self.assertTrue(audit["canonical_id_traceability"]["ready"])
            self.assertIn("CIVIL_NORTH_ARROW", audit["block_definitions"])
            self.assertIn("CIVIL-BOLD", audit["text_styles"])
            self.assertTrue(any(item["label"] == "Storm pipe" for item in audit["legend_items"]))
            self.assertTrue(_legend_items(plan, plan["actions"]))


if __name__ == "__main__":
    unittest.main()
