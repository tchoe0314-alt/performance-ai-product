import unittest
from types import SimpleNamespace

from backend.planning.production_depth import (
    build_cad_interop_metadata,
    build_grading_detail_controls,
    build_optimization_alternatives,
    enrich_drainage_production_depth,
    enrich_storm_production_depth,
)
from core.civil_design import civil_design_readiness


class ProductionDepthArtifactTests(unittest.TestCase):
    def test_drainage_adds_detention_routing_and_stage_storage(self) -> None:
        drainage = {
            "success": True,
            "basins": [
                {
                    "name": "BASIN-1",
                    "detention_design": {
                        "required_storage_cf": 4200.0,
                        "provided_storage_cf": 5100.0,
                        "release_cfs": 1.1,
                        "drawdown_hours": 18.0,
                        "bottom_elev_ft": 96.0,
                        "normal_pool_elev_ft": 99.0,
                        "top_of_bank_elev_ft": 101.0,
                    },
                }
            ],
        }

        enriched = enrich_drainage_production_depth(drainage)

        self.assertEqual(enriched["detention_routing"][0]["basin"], "BASIN-1")
        self.assertEqual(enriched["detention_routing"][0]["status"], "adequate")
        self.assertGreaterEqual(len(enriched["stage_storage"]), 3)

    def test_storm_adds_hgl_egl_tailwater_and_inlet_checks(self) -> None:
        storm = {
            "success": True,
            "hydraulic_source": "engine",
            "segments": [
                {
                    "pipe": "P-1",
                    "path": [[0.0, 0.0], [80.0, 0.0]],
                    "diameter_in": 18.0,
                    "flow_cfs": 1.4,
                    "capacity_cfs": 4.0,
                    "capacity_ratio": 0.35,
                    "velocity_fps": 3.0,
                    "start_invert_ft": 97.0,
                    "end_invert_ft": 96.2,
                    "tributary_area_sf": 10000.0,
                }
            ],
            "target_outfall": {"name": "BASIN-1", "z": 96.0},
        }
        drainage = {"structures": [{"name": "INLET-1", "estimated_flow_cfs": 1.4}]}

        enriched = enrich_storm_production_depth(storm, drainage)

        self.assertTrue(enriched["hgl_profile"])
        self.assertTrue(enriched["egl_profile"])
        self.assertEqual(enriched["tailwater_elev_ft"], 96.0)
        self.assertEqual(enriched["inlet_capacity_checks"][0]["inlet"], "INLET-1")
        self.assertEqual(enriched["controlling_segment"], "P-1")

    def test_grading_detail_controls_are_derived_from_grade_elements(self) -> None:
        controls = build_grading_detail_controls(
            grade_elements=[
                SimpleNamespace(kind="road", name="Road A", slope_x=0.01, slope_y=0.02, width=24.0, depth=120.0),
                SimpleNamespace(kind="walk", name="ADA-1", slope_x=0.01, slope_y=0.01, width=5.0, depth=80.0),
                SimpleNamespace(kind="pad", name="Building Pad", base_elev=102.0, slope_x=0.01, slope_y=0.0, transition_zone=8.0),
            ],
            derived_action_stats={"proposed_contour_count": 2},
            downhill_vector={"dx": 0.7, "dy": -0.7},
            existing_high_points=[{"x": 0.0, "y": 10.0, "z": 104.0}],
            existing_low_points=[{"x": 10.0, "y": 0.0, "z": 98.0}],
            proposed_range_ft=6.0,
        )

        self.assertEqual(controls["road_crown_controls"][0]["road"], "Road A")
        self.assertEqual(controls["ada_path_checks"][0]["path"], "ADA-1")
        self.assertEqual(controls["pad_tie_ins"][0]["building"], "Building Pad")
        self.assertTrue(controls["contours"])

    def test_cad_interop_metadata_is_truthful_about_dxf_vs_civil3d(self) -> None:
        plan = {
            "meta": {
                "sheet_registry": [{"sheet_id": "C-100"}],
                "export_audit": {"ready": True},
                "grading": {"success": True},
                "storm_pipes": {"success": True},
            }
        }

        cad = build_cad_interop_metadata(plan)

        self.assertTrue(cad["dxf"])
        self.assertFalse(cad["civil3d"])
        self.assertIn("civil3d_landxml_contract_not_implemented", cad["contract_status"])

    def test_baseline_optimization_recommendations_do_not_fake_production_ready(self) -> None:
        summary = build_optimization_alternatives(
            {
                "overall_score": 80.0,
                "component_scores": {"grading": 82.0, "drainage": 78.0},
                "metrics": {"earthwork_net_cf": 1200.0, "total_linear_utility_ft": 900.0},
                "recommendations": ["Refine grading."],
            }
        )
        meta = {
            "optimization_summary": summary,
            "export_audit": {"ready": True},
            "sheet_registry": {"sheets": [{"id": "C-100"}]},
            "cad_interop": build_cad_interop_metadata({"meta": {"export_audit": {"ready": True}, "sheet_registry": [{"id": "C-100"}]}}),
        }

        readiness = civil_design_readiness({"meta": meta})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertIn(("optimization", "committed_alternatives"), gaps)
        self.assertIn(("cad_interop", "civil3d_landxml"), gaps)


if __name__ == "__main__":
    unittest.main()
