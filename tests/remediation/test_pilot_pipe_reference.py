"""Analytical fixture only: not a connected-network or Civil 3D acceptance."""
import pytest
from engines.pipe_engine import PipeEngine
from engines.storm.hydraulic_engine import HydraulicEngine

@pytest.mark.parametrize('diameter,length,expected_slope,expected_capacity', [
    (18,100,0.01,10.50433834026563),
    (24,80,0.0125,25.292611460686935),
])
def test_inlet_move_and_resize_analytical_full_flow_reference(diameter,length,expected_slope,expected_capacity):
    # Independently specified 100/99 ft invert elevations and 100/80 ft length.
    # Q=(1.486/n)*A*R^(2/3)*sqrt(S), n=.013; free full gravity flow only.
    slope=(100-99)/length
    assert slope == pytest.approx(expected_slope, abs=1e-12)
    assert PipeEngine.full_flow_capacity_cfs(diameter,slope,.013) == pytest.approx(expected_capacity,rel=1e-10)
    assert HydraulicEngine()._full_flow_capacity_cfs(diameter/12,slope,.013) == pytest.approx(expected_capacity,rel=1e-10)
