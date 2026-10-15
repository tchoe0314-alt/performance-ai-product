from itertools import permutations
import pytest
from engines.water_sizing_engine import WaterSizingEngine,WaterSizingRequest,WaterPipeSegment,WaterFixture


def test_downstream_demand_is_accumulated_once_in_every_input_order():
    for rows in permutations([WaterPipeSegment("main","main",connected_segment_names=["a","b"]),
        WaterPipeSegment("a","branch",connected_fixture_names=["f1"]),
        WaterPipeSegment("b","branch",connected_fixture_names=["f2"]) ]):
        result=WaterSizingEngine().size(WaterSizingRequest(fixtures=[WaterFixture("f1","sink",2),WaterFixture("f2","sink",3)],segments=list(rows)))
        assert result.success is True
        assert {s.name:s.assigned_fixture_units for s in result.segments} == {"main":5,"a":2,"b":3}
        assert result.total_fixture_units == 5


@pytest.mark.parametrize("segments", [
    [WaterPipeSegment("a","main",connected_segment_names=["missing"])],
    [WaterPipeSegment("a","main",connected_segment_names=["b"]),WaterPipeSegment("b","main",connected_segment_names=["a"])],
    [WaterPipeSegment("a","main"),WaterPipeSegment("a","main")],
    [WaterPipeSegment("a","main",connected_fixture_names=["missing"])]])
def test_invalid_dependencies_are_not_successful(segments):
    result=WaterSizingEngine().size(WaterSizingRequest(segments=segments))
    assert result.success is False
    assert result.segments == []


def test_fixture_referenced_at_two_levels_is_not_double_counted():
    result=WaterSizingEngine().size(WaterSizingRequest(fixtures=[WaterFixture("f","sink",2)],segments=[
        WaterPipeSegment("main","main",connected_fixture_names=["f"],connected_segment_names=["branch"]),
        WaterPipeSegment("branch","branch",connected_fixture_names=["f"])]))
    assert result.success is True
    assert result.total_fixture_units == 2
    assert [s.assigned_fixture_units for s in result.segments] == [2,2]
