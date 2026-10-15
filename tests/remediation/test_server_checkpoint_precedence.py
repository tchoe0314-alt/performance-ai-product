"""Server-bound execution cannot inherit a conflicting client resume plan."""
from copy import deepcopy

import pytest

from backend.application.design_workflows import prepare_reactive_orchestration_payload


@pytest.mark.parametrize("system", ["drainage", "full"])
@pytest.mark.parametrize("server", [{}, {"project_name": "Server plan", "actions": [{"id": "server-road"}]}])
def test_server_checkpoint_overrides_every_client_alias(system, server):
    stale = {"project_name": "Stale or fabricated client plan", "actions": [{"id": "wrong-road"}]}
    request = {"manual_fields": {"units": "ft"}, "final_plan": stale,
        "meta": {"requested_system": system, "runtime_resume": {"final_plan": stale},
            "reactive_checkpoint_final_plan": stale, "reactive_partial_rerun_request": {"enabled": True},
            "orchestrator_meta": {"runtime_resume": {"final_plan": stale, "stage_statuses": {"layout": "complete"}},
                "runtime_approved_stages": ["drainage"]}}}
    before = deepcopy(request)
    result = prepare_reactive_orchestration_payload(request, checkpoint_final_plan=server)
    assert request == before
    assert "final_plan" not in result
    assert "runtime_resume" not in result["meta"]
    assert result["meta"]["orchestrator_meta"]["runtime_approved_stages"] == ["drainage"]
    if system == "drainage" and server:
        assert result["meta"]["reactive_checkpoint_final_plan"] == server
        assert result["meta"]["orchestrator_meta"]["runtime_resume"] == {
            "final_plan": server, "reactive_checkpoint_source": "latest_project_result"}
    else:
        assert "runtime_resume" not in result["meta"]["orchestrator_meta"]
        assert "reactive_checkpoint_final_plan" not in result["meta"]
        assert "reactive_partial_rerun_request" not in result["meta"]


def test_unbound_helper_keeps_explicit_checkpoint_compatibility():
    plan = {"project_name": "Explicit standalone plan"}
    request = {"manual_fields": {"units": "ft"}, "meta": {"requested_system": "drainage",
        "orchestrator_meta": {"runtime_resume": {"final_plan": plan}}}}
    result = prepare_reactive_orchestration_payload(request)
    assert result["meta"]["orchestrator_meta"]["runtime_resume"]["final_plan"] == plan
