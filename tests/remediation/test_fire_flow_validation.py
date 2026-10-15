import json
import pytest
from engines.water_sizing_engine import analyze_fire_flow_residual


def run(segments=None,**overrides):
    return analyze_fire_flow_residual(segments if segments is not None else [
        {"start_node":"SRC","end_node":"H","flow_gpm":0,"diameter_in":2,"length_ft":100}],
        **{**dict(source_node="SRC",hydrant_node="H",source_pressure_psi=60,required_fire_flow_gpm=100),**overrides})


@pytest.mark.parametrize("invalid", [{"required_fire_flow_gpm":float("nan")},
    {"source_pressure_psi":float("inf")},{"tolerance_gpm":0},{"max_search_gpm":-1},
    {"min_residual_pressure_psi":-1},{"hydrant_node":""}])
def test_invalid_fire_flow_has_no_fabricated_capacity(invalid):
    result=run(**invalid)
    assert result["valid"] is False
    assert result["available_fire_flow_gpm"] is None
    assert result["residual_pressure_psi"] is None
    json.dumps(result,allow_nan=False)


def test_unnamed_pipe_receives_same_identity_for_path_and_added_demand():
    result=run()
    assert result["fire_flow_path"] == ["W-1"]
    assert result["available_fire_flow_gpm"] < 1000
    solved=result["pressure_graph_at_available_flow"]["segments"][0]
    assert solved["flow_gpm"] > 0
    assert solved["flow_gpm"] == pytest.approx(result["available_fire_flow_gpm"],abs=0.001)


def test_duplicate_fire_flow_identity_rejects_before_search():
    result=run([{"name":"dup","start_node":"SRC","end_node":"A","flow_gpm":0,"diameter_in":2,"length_ft":10},
        {"name":"dup","start_node":"A","end_node":"H","flow_gpm":0,"diameter_in":2,"length_ft":10}])
    assert result["valid"] is False
    assert result["available_fire_flow_gpm"] is None
