from copy import deepcopy
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from backend.application.design_workflows import run_orchestration
from backend.services.canonical_canvas import with_canvas_snapshot
from backend.services.canonical_results import canvas_result_freshness


def source(omitted=None, target="parking"):
    return with_canvas_snapshot({"manual_fields": {"units": "ft", "grading": {"min_slope_pct": 2},
        "site_objects": [{"id": "office", "type": "building", "x": 0, "y": 0, "w": 40, "d": 30}]},
        "meta": {"requested_system": target, "calculation_omit_fields_v1": omitted if omitted is not None else ["grading", "drainage", "utility_network"]}})


def test_selective_execution_keeps_original_binding_and_does_not_edit_source():
    submitted = source()
    before = deepcopy(submitted)
    seen = []
    def engine(request):
        seen.append(request)
        return SimpleNamespace(success=True, message="ok", parsed_payload={}, final_plan={"actions": [], "meta": {}}, warnings=[], errors=[], issues=[], assumptions=[], metadata={})
    result = run_orchestration(submitted, load_orchestrator=lambda: (SimpleNamespace, engine), assess_design_readiness=lambda *_: None)
    assert seen[0].manual_fields["grading"] == {"source": "omit", "value": None}
    assert canvas_result_freshness(result, submitted)["status"] == "current"
    assert result["metadata"]["calculation_scope_v1"]["requested_system"] == "parking"
    assert submitted == before


@pytest.mark.parametrize("omitted,target", [(["standards"], "parking"), (["grading"], "parking"), (["grading", "grading"], "parking"), (["grading"], "full"), ("grading", "parking"), ([], "unknown")])
def test_invalid_scope_cannot_suppress_unrelated_requirements(omitted, target):
    with pytest.raises(HTTPException) as error:
        run_orchestration(source(omitted, target), load_orchestrator=lambda: pytest.fail("Invalid scope reached engine"), assess_design_readiness=lambda *_: None)
    assert error.value.status_code == 422
