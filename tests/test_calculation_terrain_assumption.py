from copy import deepcopy
from types import SimpleNamespace
import pytest
from fastapi import HTTPException

from backend.application.design_workflows import run_orchestration
from backend.services.canonical_canvas import with_canvas_snapshot
from backend.services.canonical_results import canvas_result_freshness


def submitted(terrain=None):
    fields = {"units": "ft", "grading": {"min_slope_pct": 2}, "site_objects": [
        {"id": "office", "type": "building", "x": 0, "y": 0, "w": 40, "d": 30}]}
    if terrain is not None:
        fields["terrain"] = terrain
    return with_canvas_snapshot({"input_mode": "assisted", "allow_ai_fill_for_blanks": True,
        "manual_fields": fields, "meta": {"requested_system": "full",
        "calculation_terrain_assumption_v1": {"version": 1, "slope_percent": 8, "direction": "southeast"}}})


@pytest.mark.parametrize("terrain", [None, "Surveyed 2% west to east", {"source": "user", "value": "Survey control"}, {"source": "omit", "value": None}])
def test_assumption_is_execution_only_never_replaces_explicit_terrain_or_design_minimum(terrain):
    source = submitted(terrain)
    before = deepcopy(source)
    seen = []
    def engine(request):
        seen.append(request)
        return SimpleNamespace(success=True, message="ok", parsed_payload={}, final_plan={"actions": [], "meta": {}},
            warnings=[], errors=[], issues=[], assumptions=[], metadata={})
    result = run_orchestration(source, load_orchestrator=lambda: (SimpleNamespace, engine), assess_design_readiness=lambda *_: None)
    assert source == before
    assert seen[0].manual_fields["grading"]["min_slope_pct"] == 2
    assert result["metadata"]["calculation_terrain_assumption_v1"]["applied"] is (terrain is None)
    if terrain is None:
        assert "assumed 8.00%" in seen[0].manual_fields["terrain"]
        assert seen[0].manual_fields["grading"]["assumed_terrain_source"] is True
        assert result["assumptions"][0]["field_name"] == "terrain"
    else:
        assert seen[0].manual_fields["terrain"] == terrain
    assert canvas_result_freshness(result, source)["status"] == "current"


@pytest.mark.parametrize("change", [
    {"slope_percent": True}, {"slope_percent": float("nan")}, {"slope_percent": -1}, {"slope_percent": 101},
    {"direction": ""}, {"version": 2}, {"version": True},
])
def test_invalid_assumption_is_rejected_before_engine(change):
    source = submitted()
    source["meta"]["calculation_terrain_assumption_v1"].update(change)
    with pytest.raises(HTTPException) as error:
        run_orchestration(source, load_orchestrator=lambda: pytest.fail("Invalid assumption reached engine"), assess_design_readiness=lambda *_: None)
    assert error.value.status_code == 422


def test_manual_mode_cannot_silently_acquire_assumed_terrain():
    source = submitted()
    source["input_mode"] = "user"
    source["allow_ai_fill_for_blanks"] = False
    with pytest.raises(HTTPException) as error:
        run_orchestration(source, load_orchestrator=lambda: pytest.fail("Manual source reached assisted engine"), assess_design_readiness=lambda *_: None)
    assert error.value.status_code == 422
