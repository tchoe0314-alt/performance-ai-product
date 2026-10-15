from copy import deepcopy
import pytest
from backend.services.brief_requirements import validate_brief_requirements, attach_brief_requirement_review, KEY, DEFINITIONS
from backend.services.canonical_project import validate_project_input, ProjectDocumentError
from backend.services.canonical_canvas import with_canvas_snapshot, resolve_canvas_input


def test_orchestration_and_run_summary_cannot_claim_ready_with_unchecked_requirements():
    from types import SimpleNamespace
    from backend.application.design_workflows import run_orchestration, build_run_summary
    result = SimpleNamespace(success=True, message="ok", parsed_payload={}, final_plan={"actions": [], "meta": {"private_alpha_readiness": {"status": "ready", "full_system_private_alpha_ready": True, "blocker_count": 0}}}, warnings=[], errors=[], issues=[], assumptions=[], metadata={"private_alpha_readiness": {"status": "ready"}})
    inputs = {"manual_fields": {"units": "ft", "site_objects": []}, "meta": {"site_inputs": {KEY: {"version": 1, "fields": {"height": {"value": 35, "unit": "ft"}}}}}}
    reviewed = run_orchestration(inputs, load_orchestrator=lambda: (SimpleNamespace, lambda request: result), assess_design_readiness=lambda *args: None)
    assert reviewed["metadata"]["private_alpha_readiness"]["status"] == "blocked"
    summary = build_run_summary(reviewed, source="brief_requirement_regression")
    assert summary["private_alpha_readiness"]["full_system_private_alpha_ready"] is False
    assert summary["private_alpha_readiness"]["blocker_count"] == 1


@pytest.mark.parametrize("field", sorted(DEFINITIONS))
def test_all_additional_requirement_fields_roundtrip_without_automatic_approval(field):
    unit, kind = DEFINITIONS[field]
    raw = "Explicit project requirement" if kind == "text" else 2
    stored = {"version": 1, "fields": {field: {"unit": unit, "value": raw}}}
    inputs = {"manual_fields": {"units": "ft", "site_objects": []}, "meta": {"site_inputs": {KEY: stored}}}
    restored = resolve_canvas_input(with_canvas_snapshot(inputs))
    assert restored["meta"]["site_inputs"][KEY] == stored
    result = {"success": True, "final_plan": {"meta": {"private_alpha_readiness": {"full_system_private_alpha_ready": True}}}}
    original = deepcopy(result)
    reviewed = attach_brief_requirement_review(result, inputs)
    assert result == original
    assert reviewed["metadata"]["brief_requirement_review_v1"]["automatic_validation"] == "not_implemented"
    assert reviewed["final_plan"]["meta"]["private_alpha_readiness"]["full_system_private_alpha_ready"] is False
    readiness = reviewed["final_plan"]["meta"]["private_alpha_readiness"]
    assert readiness["status"] == "blocked"
    assert readiness["blocker_count"] == len(readiness["blockers"]) == 1
    assert readiness["construction_release_blocked"] is True


@pytest.mark.parametrize("field, value, unit", [("height", -1, "ft"), ("height", 10 ** 400, "ft"), ("height", True, "ft"), ("height", float("nan"), "ft"), ("height", 10, "m"), ("impervious", 101, "%"), ("storeys", 1.5, "storeys"), ("access", "", "text"), ("access", "x" * 2001, "text")])
def test_invalid_requirements_cannot_be_saved(field, value, unit):
    with pytest.raises(ProjectDocumentError):
        validate_project_input({"meta": {"site_inputs": {KEY: {"version": 1, "fields": {field: {"value": value, "unit": unit}}}}}})
