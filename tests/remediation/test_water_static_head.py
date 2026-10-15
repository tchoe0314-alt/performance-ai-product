import pytest
from engines.water_sizing_engine import WaterSizingEngine,WaterSizingRequest,WaterPipeSegment,analyze_water_pressure_graph


@pytest.mark.parametrize("rise,expected", [(10,55.67),(-10,64.33),(0,60)])
def test_static_head_sign_agrees_in_both_water_paths(rise,expected):
    # Zero flow isolates pressure-head/elevation balance from friction.
    result=analyze_water_pressure_graph([{"start_node":"SRC","end_node":"A","flow_gpm":0,
        "diameter_in":2,"length_ft":100,"elevation_gain_ft":rise}],source_node="SRC",source_pressure_psi=60)
    assert result["success"] is True
    assert result["node_pressures_psi"]["A"] == expected
    segment=WaterPipeSegment("main","main",elevation_gain=rise)
    pressure=WaterSizingEngine()._estimate_remaining_pressure(
        WaterSizingRequest(available_pressure_psi=60,meter_loss_psi=0,backflow_loss_psi=0),[segment])
    assert segment.residual_pressure_psi == expected
    assert pressure == pytest.approx(expected)


def test_equal_rise_and_fall_restores_pressure_when_friction_is_zero():
    rows=[{"start_node":"SRC","end_node":"A","flow_gpm":0,"diameter_in":2,"length_ft":10,"elevation_gain_ft":10},
        {"start_node":"A","end_node":"B","flow_gpm":0,"diameter_in":2,"length_ft":10,"elevation_gain_ft":-10}]
    result=analyze_water_pressure_graph(rows,source_node="SRC",source_pressure_psi=60)
    assert result["success"] is True
    assert result["node_pressures_psi"] == {"SRC":60,"A":55.67,"B":60}
