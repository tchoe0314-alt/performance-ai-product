from copy import deepcopy
from types import SimpleNamespace
import json

from backend.application.design_workflows import run_orchestration
from backend.services.canonical_canvas import with_canvas_snapshot
from backend.services.canonical_results import canvas_result_freshness


def test_resume_reaches_engine_but_not_repeated_response_echoes():
    checkpoint = {"actions": [{"task": "rectangle", "width": 100}], "meta": {"proof": "x" * 100_000}}
    submitted = with_canvas_snapshot({"manual_fields": {"units": "ft", "site_objects": [
        {"id": "office", "type": "building", "x": 0, "y": 0, "w": 40, "d": 30}]},
        "meta": {"runtime_resume": {"final_plan": checkpoint},
                 "orchestrator_meta": {"runtime_resume": {"final_plan": checkpoint}, "runtime_approved_stages": ["layout"]}}})
    before = deepcopy(submitted)
    produced = []
    def engine(request):
        assert request.meta["runtime_resume"]["final_plan"] == checkpoint
        assert request.meta["orchestrator_meta"]["runtime_resume"]["final_plan"] == checkpoint
        output = SimpleNamespace(success=True, message="ok", parsed_payload={"meta": request.meta},
            final_plan=deepcopy(checkpoint), warnings=[], errors=[], issues=[], assumptions=[],
            metadata={"parsed_payload_meta": request.meta, "runtime_phase_checkpoint": {"stage_name": "grading"}})
        produced.append(output)
        return output
    result = run_orchestration(submitted, load_orchestrator=lambda: (SimpleNamespace, engine), assess_design_readiness=lambda *_: None)
    assert submitted == before
    assert produced[0].metadata["parsed_payload_meta"]["runtime_resume"]["final_plan"] == checkpoint
    assert result["final_plan"]["actions"] == checkpoint["actions"]
    assert result["final_plan"]["meta"]["proof"] == checkpoint["meta"]["proof"]
    assert result["metadata"]["runtime_phase_checkpoint"] == {"stage_name": "grading"}
    for echo in [result["parsed_payload"]["meta"], result["metadata"]["parsed_payload_meta"]]:
        assert "runtime_resume" not in echo
        assert echo["orchestrator_meta"] == {"runtime_approved_stages": ["layout"]}
    assert len(json.dumps(result)) < 150_000
    assert canvas_result_freshness(result, submitted)["status"] == "current"
