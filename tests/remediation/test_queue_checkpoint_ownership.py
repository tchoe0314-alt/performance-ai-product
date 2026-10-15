"""Execution checkpoint expansion must not become editable input duplication."""
from copy import deepcopy
import json

from backend.application.job_workflows import queue_orchestrate_job
from tests.test_application_job_workflows import FakeJobQueue, FakeProjectStore


def test_repeated_queue_keeps_generated_checkpoint_out_of_editable_state():
    checkpoint = {"project_name": "Synthetic checkpoint", "actions": [{"payload": "x" * 100_000}],
        "meta": {"stage_completeness": {"statuses": {"layout": "complete"}}}}
    store = FakeProjectStore({"user_id": "u1", "project_id": "p1", "name": "Synthetic",
        "project_input": {}, "latest_result": {"final_plan": checkpoint}, "metadata": {}})
    queue = FakeJobQueue()
    request = {"project_id": "p1", "full_design_mode": False,
        "manual_fields": {"units": "ft"}, "meta": {"requested_system": "drainage"}}
    original = deepcopy(request)
    sizes = []
    for _ in range(100):
        queue_orchestrate_job(project_store=store, job_queue=queue, user_id="u1", project_id="p1", request_payload=request)
        saved = store.saved_payload["project_input"]
        assert saved["request_payload"] == original
        assert saved["meta"] == original["meta"]
        assert queue.submitted["payload"]["meta"]["orchestrator_meta"]["runtime_resume"]["final_plan"] == checkpoint
        assert queue.submitted["payload"]["meta"]["reactive_checkpoint_final_plan"] == checkpoint
        sizes.append(len(json.dumps(saved, sort_keys=True)))
    assert request == original
    assert max(sizes) == min(sizes)
    assert max(sizes) < 1000
    assert store.project["latest_result"]["final_plan"] == checkpoint
