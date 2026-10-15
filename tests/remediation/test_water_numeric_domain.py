import pytest
from engines.water_sizing_engine import WaterSizingEngine, WaterSizingRequest, WaterPipeSegment, analyze_water_pressure_graph


@pytest.mark.parametrize("fields", [{"flow_gpm":1e308},{"diameter_in":1e-300},
    {"flow_gpm":10**1000},{"length_ft":1e308,"flow_gpm":1e10}])
def test_extreme_inputs_never_publish_partial_pressure(fields):
    segment={"start_node":"SRC","end_node":"A","flow_gpm":75,"diameter_in":2,"length_ft":100}
    result=analyze_water_pressure_graph([{**segment,**fields}],source_node="SRC",source_pressure_psi=60)
    assert result["success"] is False
    assert result["segments"] == [] and result["node_pressures_psi"] == {}
    assert result["min_pressure_psi"] is None


def test_sizing_overflow_is_structured_failure():
    result=WaterSizingEngine().size(WaterSizingRequest(meter_loss_psi=1e308,
        backflow_loss_psi=1e308,segments=[WaterPipeSegment("main","main")]))
    assert result.success is False
    assert result.segments == []
