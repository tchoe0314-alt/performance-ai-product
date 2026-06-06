import math
import unittest

from backend.planning.grading_math import repair_ada_profile
from core.geometry_core import Point3D
from engines.corridor_engine import CorridorEngine
from engines.detention_engine import (
    BasinGeometry,
    generate_stage_storage_curve,
    route_detention_level_pool,
)
from engines.earthwork_engine import compute_cut_fill_detailed
from engines.sanitary_engine import SanitaryEngine, SanitaryFixture, SanitaryPipeSegment, SanitarySizingRequest
from engines.storm.inlet_engine import InletEngine
from engines.surface_engine import GridSurface
from engines.utility_engine import validate_utility_coordination
from engines.water_sizing_engine import analyze_fire_flow_residual, analyze_water_pressure_graph


class RealMathBigPassTests(unittest.TestCase):
    def test_sanitary_assigns_manning_capacity_velocity_and_ratio(self) -> None:
        result = SanitaryEngine().size(
            SanitarySizingRequest(
                segments=[
                    SanitaryPipeSegment(
                        name="SAN-1",
                        segment_type="main",
                        length=100.0,
                        slope=0.01,
                        min_size_in=4.0,
                        connected_fixture_names=["FX-1"],
                    )
                ],
                fixtures=[SanitaryFixture(name="FX-1", fixture_type="service_sink", drainage_fu=10.0, discharge_gpm=100.0)],
                conservative=False,
            )
        )

        seg = result.segments[0]
        expected_capacity_cfs = SanitaryEngine()._manning_full_flow_capacity_cfs(seg.assigned_size_in, seg.slope, seg.mannings_n)
        self.assertTrue(result.success)
        self.assertAlmostEqual(seg.capacity_cfs, round(expected_capacity_cfs, 4), places=4)
        self.assertGreater(seg.capacity_gpm, 0.0)
        self.assertGreaterEqual(seg.capacity_ratio, 0.0)

    def test_inlet_gutter_spread_inverts_triangular_gutter_capacity(self) -> None:
        engine = InletEngine()
        spread = engine._triangular_gutter_spread_ft(2.0, cross_slope=0.02, longitudinal_slope=0.005, mannings_n=0.016)
        capacity = engine._triangular_gutter_capacity_cfs(spread, cross_slope=0.02, longitudinal_slope=0.005, mannings_n=0.016)

        self.assertAlmostEqual(capacity, 2.0, places=5)
        capture = engine._estimate_capture(2.0, sag=True, max_capture_cfs=10.0, gutter_spread_limit_ft=8.0)
        self.assertGreater(capture.intercepted_cfs, 0.0)
        self.assertLessEqual(capture.intercepted_cfs, 2.0)

    def test_detention_level_pool_routes_storage_and_outflow(self) -> None:
        geometry = BasinGeometry(bottom_length_ft=40.0, bottom_width_ft=20.0, depth_ft=3.0, side_slope_h_to_1v=3.0)
        curve = generate_stage_storage_curve(geometry, base_elevation=90.0, stage_increment_ft=1.0)
        routed = route_detention_level_pool(
            [(0.0, 0.0), (0.5, 10.0), (1.0, 0.0), (2.0, 0.0)],
            curve,
            outlet_coefficient=0.6,
            outlet_area_sf=0.5,
            outlet_invert_elev=90.0,
        )

        self.assertEqual(len(routed), 4)
        self.assertGreater(max(row.storage_cf for row in routed), 0.0)
        self.assertGreater(max(row.outflow_cfs for row in routed), 0.0)

    def test_water_pressure_graph_solves_hazen_williams_pressure_drop(self) -> None:
        result = analyze_water_pressure_graph(
            [{"name": "W-1", "start_node": "SRC", "end_node": "A", "flow_gpm": 75.0, "diameter_in": 2.0, "length_ft": 100.0}],
            source_node="SRC",
            source_pressure_psi=70.0,
            hazen_williams_c=130.0,
        )

        expected_loss = 4.52 * 100.0 * (75.0**1.85) / ((130.0**1.85) * (2.0**4.87)) * 0.433
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["node_pressures_psi"]["A"], round(70.0 - expected_loss, 3), places=3)

    def test_fire_flow_residual_binary_searches_available_flow(self) -> None:
        result = analyze_fire_flow_residual(
            [{"name": "W-1", "start_node": "SRC", "end_node": "H-1", "flow_gpm": 250.0, "diameter_in": 6.0, "length_ft": 400.0}],
            source_node="SRC",
            hydrant_node="H-1",
            source_pressure_psi=72.0,
            required_fire_flow_gpm=1250.0,
            min_residual_pressure_psi=20.0,
            max_search_gpm=3000.0,
        )

        self.assertTrue(result["valid"])
        self.assertGreaterEqual(result["available_fire_flow_gpm"], 1250.0)
        self.assertEqual(result["fire_flow_path"], ["W-1"])
        self.assertGreaterEqual(result["residual_pressure_psi"], 20.0)

    def test_corridor_profile_and_crowned_section_are_numeric(self) -> None:
        engine = CorridorEngine()
        profile = engine.build_profile_from_points([Point3D(0.0, 0.0, 100.0), Point3D(100.0, 0.0, 102.0)])
        section = engine.build_crowned_section(lane_width=12.0, lane_count=2, crown_elev_ft=100.0, cross_slope=0.02)

        self.assertEqual(profile[1].station_ft, 100.0)
        self.assertAlmostEqual(profile[1].grade, 0.02, places=4)
        self.assertEqual(section[2].role, "crown")
        self.assertAlmostEqual(section[2].elevation_ft - section[1].elevation_ft, 0.24 - 0.5, places=2)
        self.assertTrue(engine.validate_profile_grades(profile, min_grade=0.003, max_grade=0.08)["valid"])
        self.assertTrue(engine.validate_crowned_section(section)["valid"])

    def test_ada_repair_clamps_running_slope(self) -> None:
        repaired = repair_ada_profile([(0.0, 0.0, 100.0), (10.0, 0.0, 102.0)], max_running_slope=0.05)

        self.assertEqual(len(repaired), 2)
        self.assertAlmostEqual(repaired[1].running_slope, 0.05, places=4)
        self.assertAlmostEqual(repaired[1].repaired_z, 100.5, places=4)
        self.assertAlmostEqual(repaired[1].adjusted_ft, -1.5, places=4)

    def test_earthwork_reports_adjusted_mass_balance_validation(self) -> None:
        existing = GridSurface(0.0, 0.0, 20.0, 20.0, 10.0, 2, 2, [[100.0, 100.0], [100.0, 100.0]])
        proposed = GridSurface(0.0, 0.0, 20.0, 20.0, 10.0, 2, 2, [[101.0, 101.0], [99.0, 99.0]])

        result = compute_cut_fill_detailed(
            existing,
            proposed,
            shrink_factor=1.0,
            swell_factor=1.0,
            include_cell_maps=False,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["results"]["mass_balance_validation"]["status"], "balanced")
        self.assertTrue(result["results"]["mass_balance_validation"]["valid"])

    def test_earthwork_reports_haul_balance_import_warning_and_expected_volumes(self) -> None:
        existing = GridSurface(0.0, 0.0, 20.0, 20.0, 10.0, 2, 2, [[100.0, 100.0], [100.0, 100.0]])
        proposed = GridSurface(0.0, 0.0, 20.0, 20.0, 10.0, 2, 2, [[101.0, 101.0], [101.0, 101.0]])

        result = compute_cut_fill_detailed(
            existing,
            proposed,
            shrink_factor=1.0,
            swell_factor=1.0,
            average_haul_distance_ft=500.0,
            include_cell_maps=False,
        )
        haul = result["results"]["haul_balance"]

        self.assertTrue(result["success"])
        self.assertEqual(haul["balance_status"], "borrow_required")
        self.assertEqual(haul["import_required_cf"], 400.0)
        self.assertAlmostEqual(haul["import_required_cy"], 14.8148148148)
        self.assertEqual(haul["onsite_reuse_cf"], 0.0)
        self.assertTrue(haul["requires_offsite_haul"])
        self.assertTrue(any("borrow_required" in warning for warning in result["warnings"]))

    def test_utility_coordination_validates_cover_slope_and_clearance(self) -> None:
        result = validate_utility_coordination(
            [
                {
                    "name": "SAN-1",
                    "cover_start_ft": 4.0,
                    "cover_end_ft": 4.5,
                    "hydraulic_mode": "gravity",
                    "slope_ft_ft": 0.01,
                }
            ],
            clearance_checks=[{"id": "C-1", "horizontal_clearance_ft": 4.0, "vertical_clearance_ft": 1.5}],
        )

        self.assertTrue(result["valid"])
        self.assertTrue(result["segment_checks"][0]["slope_valid"])


if __name__ == "__main__":
    unittest.main()
