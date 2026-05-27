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
from engines.sanitary_engine import SanitaryEngine, SanitaryFixture, SanitaryPipeSegment, SanitarySizingRequest
from engines.storm.inlet_engine import InletEngine
from engines.water_sizing_engine import analyze_water_pressure_graph


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

    def test_corridor_profile_and_crowned_section_are_numeric(self) -> None:
        engine = CorridorEngine()
        profile = engine.build_profile_from_points([Point3D(0.0, 0.0, 100.0), Point3D(100.0, 0.0, 102.0)])
        section = engine.build_crowned_section(lane_width=12.0, lane_count=2, crown_elev_ft=100.0, cross_slope=0.02)

        self.assertEqual(profile[1].station_ft, 100.0)
        self.assertAlmostEqual(profile[1].grade, 0.02, places=4)
        self.assertEqual(section[2].role, "crown")
        self.assertAlmostEqual(section[2].elevation_ft - section[1].elevation_ft, 0.24 - 0.5, places=2)

    def test_ada_repair_clamps_running_slope(self) -> None:
        repaired = repair_ada_profile([(0.0, 0.0, 100.0), (10.0, 0.0, 102.0)], max_running_slope=0.05)

        self.assertEqual(len(repaired), 2)
        self.assertAlmostEqual(repaired[1].running_slope, 0.05, places=4)
        self.assertAlmostEqual(repaired[1].repaired_z, 100.5, places=4)
        self.assertAlmostEqual(repaired[1].adjusted_ft, -1.5, places=4)


if __name__ == "__main__":
    unittest.main()
