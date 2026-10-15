from itertools import permutations
import pytest
from engines.water_sizing_engine import analyze_water_pressure_graph


def edge(start,end):
    return {"start_node":start,"end_node":end,"flow_gpm":75,"diameter_in":2,"length_ft":100}


@pytest.mark.parametrize("edges", [[edge("SRC","A"),edge("A","SRC")],
    [edge("SRC","A"),edge("SRC","B"),edge("B","A")],
    [edge("SRC","A"),edge("SRC","A")], [edge("X","Y"),edge("Y","X")],
    [edge("X","Y")], [edge("SRC","SRC")]])
def test_unsupported_topology_fails_without_invented_pressures(edges):
    result=analyze_water_pressure_graph(edges,source_node="SRC",source_pressure_psi=70)
    assert result["success"] is False
    assert result["segments"] == []
    assert result["node_pressures_psi"] == {}
    assert result["warnings"]


def test_branching_tree_is_order_independent_and_accumulates_path_losses():
    for edges in permutations([edge("SRC","A"),edge("A","B"),edge("A","C")]):
        result=analyze_water_pressure_graph(edges,source_node="SRC",source_pressure_psi=70)
        assert result["success"] is True
        assert result["node_pressures_psi"] == {"SRC":70,"A":64.413,"B":58.826,"C":58.826}
