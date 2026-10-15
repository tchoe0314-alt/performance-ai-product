import pytest
from engines.water_sizing_engine import WaterSizingEngine


@pytest.mark.parametrize("gpm,diameter,c", [(75,2,130),(500,6,130),(1000,8,140),(10,1,120)])
def test_pressure_loss_agrees_with_independent_epa_head_form(gpm,diameter,c):
    # EPA EPANET2.2 Table3.1: head in feet, Q in cfs, d in feet.
    # Convert US gallons using231in3/gal and1728in3/ft3, then head to psi.
    q_cfs=gpm*231/1728/60
    d_ft=diameter/12
    reference_psi=4.727*100*q_cfs**1.852/(c**1.852*d_ft**4.871)*0.433
    actual=WaterSizingEngine()._hazen_williams_loss_psi_per_100ft(gpm,diameter,c_factor=c)
    # Existing GPM/inch formula uses rounded exponents; qualification tolerance
    # is1%, plus0.001psi reporting rounding. Not a full network benchmark.
    assert actual == pytest.approx(reference_psi,rel=0.01,abs=0.001)
