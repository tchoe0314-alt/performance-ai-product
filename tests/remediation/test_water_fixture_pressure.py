import pytest
from engines.water_sizing_engine import WaterSizingEngine,WaterSizingRequest,WaterPipeSegment,WaterFixture


@pytest.mark.parametrize("pressure,passed", [(20,True),(15,True),(14.9996,False),(10,False)])
def test_fixture_requirement_uses_unrounded_pressure(pressure,passed):
    result=WaterSizingEngine().size(WaterSizingRequest(available_pressure_psi=pressure,
        meter_loss_psi=0,backflow_loss_psi=0,fixtures=[WaterFixture("f","sink",2,required_pressure=15)],
        segments=[WaterPipeSegment("main","main",connected_fixture_names=["f"],length=0)]))
    assert result.success is passed
    assert result.pressure_requirements_met is passed
    check=result.fixture_pressure_checks[0]
    assert check["available_supply_endpoint_pressure_psi"] == pressure
    assert check["passed"] is passed


@pytest.mark.parametrize("connected,branch_length,reason", [(False,0,"unconnected_fixture"),(True,10,"unmodeled_fixture_branch_length")])
def test_incomplete_fixture_path_cannot_claim_pressure_qualification(connected,branch_length,reason):
    result=WaterSizingEngine().size(WaterSizingRequest(fixtures=[WaterFixture("f","sink",2,branch_length=branch_length)],
        segments=[WaterPipeSegment("main","main",connected_fixture_names=["f"] if connected else [])]))
    assert result.success is False
    assert result.pressure_requirements_met is False
    assert result.fixture_pressure_checks[0]["reason"] == reason


def test_no_fixture_does_not_invent_fixture_acceptance():
    result=WaterSizingEngine().size(WaterSizingRequest(segments=[WaterPipeSegment("main","main")]))
    assert result.success is True
    assert result.pressure_requirements_met is None
    assert result.fixture_pressure_checks == []
