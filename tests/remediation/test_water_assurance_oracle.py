from backend.application.internal_assurance import build_internal_calculation_crosschecks
from engines.water_sizing_engine import WaterSizingEngine


def test_internal_assurance_rejects_previous_duplicate_conversion(monkeypatch):
    monkeypatch.setattr(WaterSizingEngine,"_hazen_williams_loss_psi_per_100ft",lambda *a,**kw:2.419)
    result=build_internal_calculation_crosschecks()
    water=next(row for row in result["checks"] if row["check_id"]=="hazen_williams_pressure_loss")
    assert water["expected"] == 5.587
    assert water["observed"] == 2.419
    assert water["absolute_tolerance"] == 1e-9
    assert water["passed"] is False
    assert result["passed"] is False
    assert result["independent_external_review"] is False
