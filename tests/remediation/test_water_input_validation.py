from copy import deepcopy
import json
import pytest
from engines.water_sizing_engine import WaterSizingEngine, WaterSizingRequest, WaterPipeSegment, analyze_water_pressure_graph


@pytest.mark.parametrize("field,value", [("flow_gpm",-1),("flow_gpm",float("nan")),
    ("diameter_in",0),("diameter_in",None),("length_ft",-1),("length_ft",float("inf")),
    ("elevation_gain_ft",float("nan")),("start_node","")])
def test_bad_graph_input_has_no_partial_success(field,value):
    segment={"start_node":"SRC","end_node":"A","flow_gpm":75,"diameter_in":2,"length_ft":100}
    segment[field]=value
    before=deepcopy(segment)
    result=analyze_water_pressure_graph([segment],source_node="SRC",source_pressure_psi=60)
    assert result["success"] is False
    assert result["segments"] == [] and result["node_pressures_psi"] == {}
    assert result["min_pressure_psi"] is None
    assert json.dumps(segment, sort_keys=True) == json.dumps(before, sort_keys=True)


def test_zero_flow_does_not_fall_back_to_conflicting_alias():
    result=analyze_water_pressure_graph([{"start_node":"SRC","end_node":"A","flow_gpm":0,
        "assigned_flow_gpm":100,"diameter_in":2,"length_ft":100}],source_node="SRC",source_pressure_psi=60)
    assert result["success"] is True
    assert result["node_pressures_psi"]["A"] == 60


@pytest.mark.parametrize("value", [float("nan"),float("inf"),-1,True])
def test_invalid_sizing_request_reports_failure(value):
    result=WaterSizingEngine().size(WaterSizingRequest(available_pressure_psi=value,
        segments=[WaterPipeSegment("main","main")]))
    assert result.success is False
    assert result.segments == []
