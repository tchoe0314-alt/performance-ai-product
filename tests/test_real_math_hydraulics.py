import math
import unittest

from engines.storm.hydraulic_engine import HydraulicEngine, analyze_storm_hydraulics
from engines.storm.catchment_engine import CatchmentEngine
from engines.storm.storm_types import HydraulicAnalysisRequest, StormNode, StormPipe
from engines.water_sizing_engine import WaterPipeSegment, WaterSizingEngine, WaterSizingRequest


class RealMathHydraulicsTests(unittest.TestCase):
    def test_storm_catchment_uses_same_us_customary_rational_conversion_as_hydrology(self) -> None:
        flow = CatchmentEngine()._rational_peak_runoff_cfs(0.82, 4.25, 4.2 * 43560.0)

        self.assertAlmostEqual(flow, 1.008 * 0.82 * 4.25 * 4.2, places=9)

    def test_storm_manning_full_flow_and_half_flow_normal_depth(self) -> None:
        engine = HydraulicEngine()
        full_capacity = engine._full_flow_capacity_cfs(2.0, 0.01, 0.013)
        expected = (1.486 / 0.013) * (math.pi * 2.0**2 / 4.0) * (0.5 ** (2.0 / 3.0)) * (0.01**0.5)

        self.assertAlmostEqual(full_capacity, expected, places=6)

        result = analyze_storm_hydraulics(
            HydraulicAnalysisRequest(
                pipes=[
                    StormPipe(
                        name="STM-1",
                        upstream_node_name="A",
                        downstream_node_name="B",
                        diameter_in=24.0,
                        length_ft=100.0,
                        slope=0.01,
                        mannings_n=0.013,
                        assigned_runoff_cfs=full_capacity / 2.0,
                        upstream_invert_ft=100.0,
                        downstream_invert_ft=99.0,
                    )
                ],
                nodes=[
                    StormNode(name="A", rim_elev_ft=105.0, invert_elev_ft=100.0),
                    StormNode(name="B", rim_elev_ft=104.0, invert_elev_ft=99.0),
                ],
            )
        )

        pipe = result.pipes[0]
        self.assertTrue(result.success)
        self.assertAlmostEqual(pipe.hydraulic.flow_depth_ratio, 0.5, places=3)
        self.assertAlmostEqual(pipe.hydraulic.normal_depth_ft, 1.0, places=3)
        self.assertAlmostEqual(pipe.hydraulic.flow_area_sf, math.pi * 2.0**2 / 8.0, places=3)
        self.assertGreater(pipe.hydraulic.egl_upstream_ft, pipe.hydraulic.hgl_upstream_ft)

    def test_water_uses_hazen_williams_loss_and_velocity_for_selected_size(self) -> None:
        result = WaterSizingEngine().size(
            WaterSizingRequest(
                available_pressure_psi=70.0,
                meter_loss_psi=4.0,
                backflow_loss_psi=6.0,
                hazen_williams_c=130.0,
                segments=[
                    WaterPipeSegment(
                        name="W-1",
                        segment_type="main",
                        length=250.0,
                        min_size_in=2.0,
                        assigned_fixture_units=0.0,
                        connected_fixture_names=[],
                    )
                ],
            )
        )

        segment = result.segments[0]
        self.assertTrue(result.success)
        self.assertEqual(segment.assigned_flow_gpm, 0.0)
        self.assertEqual(segment.pressure_loss_per_100ft, 0.0)
        self.assertEqual(segment.velocity_fps, 0.0)
        self.assertAlmostEqual(result.estimated_remaining_pressure_psi, 60.0, places=3)

        loss = WaterSizingEngine()._hazen_williams_loss_psi_per_100ft(75.0, 2.0, c_factor=130.0)
        expected_headloss_ft = 4.52 * 100.0 * (75.0**1.85) / ((130.0**1.85) * (2.0**4.87))
        self.assertAlmostEqual(loss, round(expected_headloss_ft * 0.433, 3), places=3)
        self.assertAlmostEqual(WaterSizingEngine()._velocity_fps(75.0, 2.0), 7.66, places=2)


if __name__ == "__main__":
    unittest.main()
