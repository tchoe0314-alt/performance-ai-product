from itertools import permutations
import pytest
from engines.water_sizing_engine import WaterSizingEngine,WaterSizingRequest,WaterPipeSegment,WaterFixture


def test_sizing_residuals_follow_supply_path_not_sum_of_parallel_branches(monkeypatch):
    engine=WaterSizingEngine()
    # Independently assigned5psi/100ft isolates path bookkeeping from pipe
    # selection/formulas, which have separate analytical/reference tests.
    monkeypatch.setattr(engine,"_pick_pipe_size",lambda **kwargs:{"size_in":2,"loss_100ft":5,"velocity_fps":1})
    segments=[WaterPipeSegment("main","main",length=100,connected_segment_names=["a","b"]),
        WaterPipeSegment("a","branch",length=40,connected_fixture_names=["f1"]),
        WaterPipeSegment("b","branch",length=60,connected_fixture_names=["f2"])]
    for order in permutations(segments):
        result=engine.size(WaterSizingRequest(fixtures=[WaterFixture("f1","sink",2),WaterFixture("f2","sink",3)],segments=list(order)))
        assert result.success is True
        #60 source -5 meter -8 backflow =47; main loses5, a loses2,
        # b loses3. Branches do not lie in series with one another.
        assert {s.name:s.residual_pressure_psi for s in result.segments} == {"main":42,"a":40,"b":39}
        assert result.estimated_remaining_pressure_psi == 39
        assert all(segment.residual_pressure_psi == 0 for segment in segments)


def test_serial_path_accumulates_friction_and_static_losses():
    engine=WaterSizingEngine()
    segments=[WaterPipeSegment("main","main",connected_segment_names=["branch"],friction_loss_psi=5,elevation_gain=10),
        WaterPipeSegment("branch","branch",friction_loss_psi=2,elevation_gain=5)]
    request=WaterSizingRequest(available_pressure_psi=60,meter_loss_psi=0,backflow_loss_psi=0)
    assert engine._estimate_remaining_pressure(request,segments) == pytest.approx(46.505)
    assert segments[0].residual_pressure_psi == 50.67
    assert segments[1].residual_pressure_psi == 46.505
