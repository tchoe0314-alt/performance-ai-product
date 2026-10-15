from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import threading
import time

import pytest
from fastapi import HTTPException

from backend.application.artifact_workflows import export_dxf_artifact, export_report_artifact, export_review_pdf_artifact, finalize_export_artifact
from backend.application.project_workflows import save_project_workflow_update
from backend.services.auth_store import AuthStore
from backend.services.canonical_canvas import with_canvas_snapshot
from backend.services.database import Database
from backend.services.project_store import ProjectStore
from backend.services.job_queue import JobQueueService
from backend.services.canonical_results import ENGINE_REVISION


@pytest.fixture
def setup(tmp_path):
    db = Database(tmp_path / "exports.db")
    auth = AuthStore(db)
    user = auth.register_user(email="exports@example.test", password="Disposable-123", name="Exports")["user"]["user_id"]
    store = ProjectStore(db)
    source = with_canvas_snapshot({"manual_fields": {"units": "ft", "site_objects": [
        {"id": "building", "type": "office_building", "x": 100, "y": 50, "w": 40, "d": 30}
    ]}})
    project = store.save_project(user_id=user, project_id=None, name="Pilot", project_input=source,
                                 metadata={"note": "preserve"}, session_state={"note": "session"})
    result = store.save_calculation_result(user_id=user, project_id=project["project_id"], source_input=source,
        result={"success": True, "metadata": {"calculation_engine_revision": ENGINE_REVISION}, "final_plan": {"project_name": "Pilot", "units": "ft", "actions": [], "meta": {}}})
    return db, store, auth, user, project["project_id"], source, result


def edit(store, user, project_id, source):
    changed = deepcopy(source)
    changed["manual_fields"]["site_objects"][0]["x"] = 200
    changed = with_canvas_snapshot(changed)
    store.save_project_shell(expected_revision=store.get_project(user_id=user, project_id=project_id)["revision_token"], user_id=user, project_id=project_id, name="New name", project_input=changed,
                             session_state={"note": "new session"}, metadata={"note": "new note"})
    result = store.save_calculation_result(user_id=user, project_id=project_id, source_input=changed,
        result={"success": True, "message": "new calculation", "metadata": {"calculation_engine_revision": ENGINE_REVISION}, "final_plan": {"meta": {}}})
    return changed, result


def test_workflow_update_does_not_use_read_then_full_project_save(setup, monkeypatch):
    _, store, _, user, project_id, _, _ = setup
    before = store.get_project(user_id=user, project_id=project_id)
    def forbidden(**_):
        raise AssertionError("Workflow metadata must not use full project read/save")
    with monkeypatch.context() as scoped:
        scoped.setattr(store, "get_project", forbidden)
        scoped.setattr(store, "save_project", forbidden)
        save_project_workflow_update(project_store=store, user_id=user, project_id=project_id,
            artifact_summary={"artifact_id": "a", "kind": "report"})
    after = store.get_project(user_id=user, project_id=project_id)
    for field in ("name", "latest_result", "session_state", "tags", "user_id", "revision_token"):
        assert after[field] == before[field]
    assert after["project_input"]["manual_fields"] == before["project_input"]["manual_fields"]
    assert after["project_input"]["canonical_project_v1"]["export_history"][0]["artifact_v1"]["artifact_id"] == "a"
    assert after["metadata"]["note"] == "preserve"
    assert after["metadata"]["workflow"]["artifacts"][0]["artifact_id"] == "a"


def test_simultaneous_export_history_updates_do_not_drop_records(setup):
    _, store, _, user, project_id, source, result = setup
    barrier = threading.Barrier(6)
    def save(index):
        barrier.wait(timeout=10)
        return save_project_workflow_update(project_store=store, user_id=user, project_id=project_id,
            artifact_summary={"artifact_id": f"a-{index}", "kind": "report"}, exported_result=result)
    with ThreadPoolExecutor(max_workers=6) as executor:
        assert all(executor.map(save, range(6)))
    project = store.get_project(user_id=user, project_id=project_id)
    assert {item["artifact_id"] for item in project["metadata"]["workflow"]["artifacts"]} == {f"a-{i}" for i in range(6)}
    assert project["project_input"]["manual_fields"] == source["manual_fields"]
    assert len(project["project_input"]["canonical_project_v1"]["export_history"]) == 6
    assert project["latest_result"] == result


@pytest.mark.parametrize("export", [export_dxf_artifact, export_report_artifact, export_review_pdf_artifact])
def test_edit_during_generation_retains_file_as_history_without_overwriting_new_design(setup, tmp_path, export):
    _, store, _, user, project_id, source, old_result = setup
    expected = {}
    path = tmp_path / "old-snapshot.file"
    def generate(**_):
        expected["input"], expected["result"] = edit(store, user, project_id, source)
        path.write_bytes(b"old snapshot retained")
        return path
    service = SimpleNamespace(export_dxf=generate, export_report_json=generate, export_review_pdf=generate)
    args = {"artifact_service": service, "project_store": store, "user_id": user,
            "project_id": project_id, "result_data": old_result}
    if export is export_dxf_artifact:
        args["export_scope"] = "review"
    if export is export_review_pdf_artifact:
        args["review_sheet_set"] = {"sheets": []}
    with pytest.raises(HTTPException) as exc:
        export(**args)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "export_became_historical"
    assert path.read_bytes() == b"old snapshot retained"
    project = store.get_project(user_id=user, project_id=project_id)
    assert project["project_input"]["manual_fields"] == expected["input"]["manual_fields"]
    assert project["latest_result"] == expected["result"]
    assert project["name"] == "New name"
    assert project["session_state"] == {"note": "new session"}
    assert project["metadata"]["note"] == "new note"
    artifact = project["metadata"]["workflow"]["artifacts"][0]
    assert artifact["snapshot_status"] == "historical"
    assert artifact["release_ready"] is False
    assert artifact["download_path"] == exc.value.detail["download_path"]
    assert artifact["calculation_reference"]["calculation_id"] == old_result["metadata"]["calculation_save_v1"]["calculation_id"]
    assert "version_history" not in project["metadata"]["workflow"]
    assert project["metadata"]["workflow"]["review_dashboard"]["recent_artifacts"][0]["snapshot_status"] == "historical"


def test_matching_export_is_committed_as_current(setup):
    _, store, _, user, project_id, _, result = setup
    finalize_export_artifact(project_store=store, user_id=user, project_id=project_id,
        path=Path("current.json"), artifact_kind="report", result_data=result)
    artifact = store.get_project(user_id=user, project_id=project_id)["metadata"]["workflow"]["artifacts"][0]
    assert artifact["snapshot_status"] == "current"


def test_metadata_failure_rolls_back_and_unauthorized_user_cannot_write(setup):
    _, store, auth, user, project_id, _, _ = setup
    before = store.get_project(user_id=user, project_id=project_id)
    def failing(record):
        record["metadata"]["note"] = "bad"
        raise RuntimeError("callback failed")
    with pytest.raises(RuntimeError):
        store.update_project_metadata(user_id=user, project_id=project_id, update_metadata=failing)
    assert store.get_project(user_id=user, project_id=project_id) == before
    other = auth.register_user(email="other@example.test", password="Disposable-123", name="Other")["user"]["user_id"]
    with pytest.raises(ValueError):
        store.update_project_metadata(user_id=other, project_id=project_id, update_metadata=lambda _: {"bad": True})
    assert store.get_project(user_id=user, project_id=project_id) == before


def test_project_deleted_during_generation_is_not_published(setup):
    _, store, _, user, project_id, _, result = setup
    store.delete_project(user_id=user, project_id=project_id)
    with pytest.raises(HTTPException) as exc:
        finalize_export_artifact(project_store=store, user_id=user, project_id=project_id,
            path=Path("old.json"), artifact_kind="report", result_data=result)
    assert exc.value.status_code == 409


@pytest.mark.parametrize("job_type", ["export_dxf", "export_pdf", "export_report"])
def test_async_export_keeps_historical_download_and_meaningful_error(setup, job_type):
    db, store, _, user, project_id, source, result = setup
    queue = JobQueueService(db, heartbeat_interval_sec=0.1, resume_poll_interval_sec=0.1)
    def runner(_):
        edit(store, user, project_id, source)
        finalize_export_artifact(project_store=store, user_id=user, project_id=project_id,
            path=Path("historical.file"), artifact_kind="report", result_data=result)
    try:
        queue.register_handler(job_type, runner)
        created = queue.submit_job(user_id=user, job_type=job_type, project_id=project_id, payload={})
        deadline = time.monotonic() + 5
        record = None
        while time.monotonic() < deadline:
            record = queue.get_job_detail(user_id=user, job_id=created["job_id"])
            if record["status"] == "failed":
                break
            time.sleep(0.02)
        assert record["status"] == "failed"
        assert record["result"]["error_details"]["code"] == "export_became_historical"
        assert "Project changed during export" in record["error"]
        assert record["artifact_history"][0]["snapshot_status"] == "historical"
        assert record["artifact_history"][0]["download_path"] == "/api/artifacts/historical.file"
    finally:
        queue.shutdown()
