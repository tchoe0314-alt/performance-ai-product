from copy import deepcopy
import threading

import pytest

from backend.application.job_workflows import _save_generated_calculation
from backend.services.auth_store import AuthStore
from backend.services.canonical_canvas import with_canvas_snapshot
from backend.services.canonical_results import ENGINE_REVISION, canvas_result_freshness
from backend.services.database import Database
from backend.services.project_store import ProjectStore


@pytest.fixture
def setup(tmp_path):
    db = Database(tmp_path / "history.db")
    user = AuthStore(db).register_user(email="history@example.test", password="Disposable-123", name="History")["user"]["user_id"]
    store = ProjectStore(db)
    source = with_canvas_snapshot({"manual_fields": {"units": "ft", "site_objects": [
        {"id": "building", "type": "office_building", "x": 100, "y": 50, "w": 40, "d": 30},
    ]}})
    project = store.save_project(user_id=user, project_id=None, name="Pilot", project_input=source)
    return db, store, user, project["project_id"], source


def result(label):
    # Synthetic completed execution. Unstamped legacy results are tested below.
    return {"success": True, "message": label, "metadata": {"calculation_engine_revision": ENGINE_REVISION}, "final_plan": {"meta": {"quantities": {"area": 1200}}}}


def test_unstamped_or_obsolete_result_is_preserved_but_never_activated(setup):
    _, store, user, project_id, source = setup
    active = store.save_calculation_result(user_id=user, project_id=project_id, source_input=source, result=result("current"))
    for stamp in (None, "obsolete-method", "engineering_core_2026_10_v2"):
        legacy = result("legacy")
        legacy["metadata"] = {} if stamp is None else {"calculation_engine_revision": stamp}
        saved = store.save_calculation_result(user_id=user, project_id=project_id, source_input=source, result=legacy)
        assert saved["metadata"]["calculation_save_v1"]["reason"] == "engine_revision_unverified"
        assert saved["metadata"]["calculation_save_v1"]["disposition"] == "archived"
        assert store.get_project(user_id=user, project_id=project_id)["latest_result"] == active
        assert saved["metadata"].get("calculation_engine_revision") == stamp


def test_header_history_distinguishes_success_without_exposing_results(setup):
    db, store, user, project_id, source = setup
    store.save_calculation_result(user_id=user, project_id=project_id, source_input=source, result=result("successful"), force_archive=True)
    store.save_calculation_result(user_id=user, project_id=project_id, source_input=source, result={"success": False, "message": "failed"}, force_archive=True)
    entries = store.list_calculation_history(user_id=user, project_id=project_id)
    assert sorted(entry["successful"] for entry in entries) == [False, True]
    assert all("result_json" not in entry for entry in entries)
    successful = next(entry for entry in entries if entry["successful"])
    assert store.get_last_successful_calculation_at(user_id=user, project_id=project_id) == successful["created_at"]
    connection = db.connect()
    connection.execute("UPDATE project_calculation_history SET created_at = ? WHERE calculation_id = ?", (1000, successful["calculation_id"]))
    connection.commit()
    connection.close()
    for _ in range(51):
        store.save_calculation_result(user_id=user, project_id=project_id, source_input=source, result={"success": False}, force_archive=True)
    assert not any(entry["successful"] for entry in store.list_calculation_history(user_id=user, project_id=project_id))
    assert store.get_last_successful_calculation_at(user_id=user, project_id=project_id) == 1000


def moved(source):
    edited = deepcopy(source)
    edited["manual_fields"]["site_objects"][0]["x"] = 200
    return with_canvas_snapshot(edited)


def test_changed_layout_archives_late_result_without_overwriting_any_project_state(setup):
    db, store, user, project_id, source = setup
    edited = moved(source)
    store.save_project_shell(user_id=user, project_id=project_id, name="Renamed", project_input=edited, metadata={"keep": "new"})
    before = store.get_project(user_id=user, project_id=project_id)
    saved = store.save_calculation_result(user_id=user, project_id=project_id, source_input=source, result=result("old"))
    assert saved["metadata"]["calculation_save_v1"]["disposition"] == "archived"
    assert store.get_project(user_id=user, project_id=project_id) == before
    reopened = ProjectStore(Database(db.db_path))
    entries = reopened.list_calculation_history(user_id=user, project_id=project_id)
    entry = reopened.get_calculation_history(user_id=user, project_id=project_id, calculation_id=entries[0]["calculation_id"])
    assert entry["source_input"] == source
    assert entry["result"]["message"] == "old"
    assert entry["result"]["final_plan"]["meta"]["quantities"]["area"] == 1200


def test_current_result_activates_but_late_old_result_preserves_it(setup):
    _, store, user, project_id, source = setup
    edited = moved(source)
    store.save_project_shell(user_id=user, project_id=project_id, name="Pilot", project_input=edited)
    active = store.save_calculation_result(user_id=user, project_id=project_id, source_input=edited, result=result("new"))
    store.save_calculation_result(user_id=user, project_id=project_id, source_input=source, result=result("late old"))
    current = store.get_project(user_id=user, project_id=project_id)
    assert current["latest_result"] == active
    assert current["project_input"]["manual_fields"] == edited["manual_fields"]
    assert canvas_result_freshness(active, current["project_input"])["status"] == "current"
    assert canvas_result_freshness(active, edited)["status"] == "current"
    assert len(store.list_calculation_history(user_id=user, project_id=project_id)) == 2
    assert sum(entry["is_active"] for entry in store.list_calculation_history(user_id=user, project_id=project_id)) == 1


@pytest.mark.parametrize("success", [False, None, "true", "false", 1])
def test_failed_or_unverified_result_never_replaces_active_calculation(setup, success):
    _, store, user, project_id, source = setup
    active = store.save_calculation_result(user_id=user, project_id=project_id, source_input=source, result=result("active"))
    failed = store.save_calculation_result(user_id=user, project_id=project_id, source_input=source, result={"success": success, "message": "unsuccessful"})
    assert failed["metadata"]["calculation_save_v1"]["disposition"] == "archived"
    assert failed["metadata"]["calculation_save_v1"]["reason"] == "calculation_not_successful"
    assert store.get_project(user_id=user, project_id=project_id)["latest_result"] == active


def test_editing_after_activation_makes_retained_history_inactive(setup):
    _, store, user, project_id, source = setup
    store.save_calculation_result(user_id=user, project_id=project_id, source_input=source, result=result("current"))
    assert store.list_calculation_history(user_id=user, project_id=project_id)[0]["is_active"] is True
    store.save_project_shell(user_id=user, project_id=project_id, name="Pilot", project_input=moved(source))
    entries = store.list_calculation_history(user_id=user, project_id=project_id)
    assert len(entries) == 1
    assert entries[0]["is_active"] is False


def test_unsaved_edit_can_force_history_only_even_when_database_inputs_match(setup):
    _, store, user, project_id, source = setup
    before = store.get_project(user_id=user, project_id=project_id)
    saved = store.save_calculation_result(user_id=user, project_id=project_id, source_input=source, result=result("unsaved edit"), force_archive=True)
    assert saved["metadata"]["calculation_save_v1"]["disposition"] == "archived"
    assert store.get_project(user_id=user, project_id=project_id) == before


def test_archive_api_never_activates_result_against_matching_saved_inputs(setup, monkeypatch):
    import importlib
    api = importlib.import_module("backend.api.app")
    _, store, user, project_id, source = setup
    monkeypatch.setattr(api, "PROJECT_STORE", store)
    response = api.archive_project_calculation(project_id, api.CalculationArchivePayload(source_input=source, result=result("direct stale")), {"user_id": user})
    assert response["calculation"]["metadata"]["calculation_save_v1"]["disposition"] == "archived"
    assert store.get_project(user_id=user, project_id=project_id)["latest_result"] == {}


def test_job_save_uses_result_only_path_and_marks_returned_job_result_archived(setup):
    _, store, user, project_id, source = setup
    store.save_project_shell(user_id=user, project_id=project_id, name="New name", project_input=moved(source))
    generated = result("old checkpoint")
    _save_generated_calculation(store, user_id=user, project_id=project_id, name="Old name", project_input=source, latest_result=generated)
    assert generated["metadata"]["calculation_save_v1"]["disposition"] == "archived"
    assert store.get_project(user_id=user, project_id=project_id)["name"] == "New name"


def test_actual_job_runner_archives_when_user_edits_during_engine_execution(setup):
    from backend.application.job_workflows import build_orchestrate_job_runner
    _, store, user, project_id, source = setup
    def engine(payload):
        store.save_project_shell(user_id=user, project_id=project_id, name="Changed during run", project_input=moved(source))
        return result("Late engine result")
    runner = build_orchestrate_job_runner(
        project_store=store, update_job_progress=lambda *_, **__: None, run_orchestration=engine,
        build_run_summary=lambda *_, **__: {}, merge_project_metadata=lambda metadata, **_: metadata,
        final_plan_from_result=lambda value, **_: value["final_plan"],
    )
    finished = runner({"job_id": "job-late", "job_type": "orchestrate", "user_id": user,
                       "project_id": project_id, "payload": source})
    assert finished["metadata"]["calculation_save_v1"]["disposition"] == "archived"
    current = store.get_project(user_id=user, project_id=project_id)
    assert current["latest_result"] == {}
    assert current["name"] == "Changed during run"
    assert current["project_input"]["manual_fields"] == moved(source)["manual_fields"]


def test_legacy_inputs_are_archived_without_unsafe_full_save(setup):
    _, store, user, project_id, _ = setup
    before = store.get_project(user_id=user, project_id=project_id)
    saved = store.save_calculation_result(user_id=user, project_id=project_id, source_input={}, result=result("legacy"))
    assert saved["metadata"]["calculation_save_v1"]["reason"] == "input_binding_unverified"
    assert saved["metadata"]["calculation_save_v1"]["disposition"] == "archived"
    assert store.get_project(user_id=user, project_id=project_id) == before
    history = store.list_calculation_history(user_id=user, project_id=project_id)
    assert len(history) == 1 and history[0]["is_active"] is False


def test_history_access_scoped_to_project_and_authorized_user(setup):
    _, store, user, project_id, source = setup
    saved = store.save_calculation_result(user_id=user, project_id=project_id, source_input=source, result=result("current"))
    calculation_id = saved["metadata"]["calculation_save_v1"]["calculation_id"]
    assert store.list_calculation_history(user_id="stranger", project_id=project_id) is None
    assert store.get_calculation_history(user_id="stranger", project_id=project_id, calculation_id=calculation_id) is None
    assert store.get_calculation_history(user_id=user, project_id="different", calculation_id=calculation_id) is None
    with pytest.raises(ValueError, match="editor access"):
        store.save_calculation_result(user_id="stranger", project_id=project_id, source_input=source, result=result("bad"))


def test_account_deletion_cascades_calculation_history(setup):
    db, store, user, project_id, source = setup
    store.save_calculation_result(user_id=user, project_id=project_id, source_input=source, result=result("current"))
    connection = db.connect()
    connection.execute("DELETE FROM users WHERE user_id = ?", (user,))
    connection.commit()
    assert connection.execute("SELECT COUNT(*) FROM project_calculation_history").fetchone()[0] == 0
    connection.close()


def test_history_is_included_in_account_export(setup, tmp_path):
    from backend.services.data_lifecycle import DataLifecycleService
    db, store, user, project_id, source = setup
    saved = store.save_calculation_result(user_id=user, project_id=project_id, source_input=source, result=result("export me"))
    service = DataLifecycleService(db, storage_dir=tmp_path, upload_dir=tmp_path / "uploads", artifact_dir=tmp_path / "artifacts", learning_paths=[])
    exported = service.account_export(user_id=user)
    history = exported["data"]["calculation_history"]
    assert history[0]["source_input"] == source
    assert history[0]["result"] == saved


def test_api_history_and_job_freshness_use_authorized_current_project(setup, monkeypatch):
    import importlib
    api = importlib.import_module("backend.api.app")
    from types import SimpleNamespace
    from fastapi import HTTPException
    _, store, user, project_id, source = setup
    saved = store.save_calculation_result(user_id=user, project_id=project_id, source_input=source, result=result("old"))
    calculation_id = saved["metadata"]["calculation_save_v1"]["calculation_id"]
    monkeypatch.setattr(api, "PROJECT_STORE", store)
    monkeypatch.setattr(api, "JOB_QUEUE", SimpleNamespace(get_job_detail=lambda **_: {
        "project_id": project_id, "job_type": "orchestrate", "result": saved,
    }))
    assert api.list_project_calculations(project_id, {"user_id": user})["calculations"][0]["is_active"] is True
    assert api.get_project_calculation(project_id, calculation_id, {"user_id": user})["calculation"]["result"] == saved
    store.save_project_shell(user_id=user, project_id=project_id, name="Pilot", project_input=moved(source))
    assert api.get_job("job-1", {"user_id": user})["job"]["result_freshness_v1"]["status"] == "stale"
    with pytest.raises(HTTPException) as caught:
        api.get_project_calculation(project_id, calculation_id, {"user_id": "stranger"})
    assert caught.value.status_code == 404
    paths = [route.path for route in api.app.routes]
    assert paths.count("/api/projects/{project_id}/admin") == 1


def test_edit_committed_while_result_waits_for_database_lock_is_preserved(setup):
    db, store, user, project_id, source = setup
    lock = db.connect()
    lock.execute("BEGIN IMMEDIATE")
    started = threading.Event()
    completed = threading.Event()
    outcome = []
    def finish_calculation():
        started.set()
        try:
            outcome.append(store.save_calculation_result(user_id=user, project_id=project_id, source_input=source, result=result("racing")))
        except Exception as exc:
            outcome.append(exc)
        finally:
            completed.set()
    worker = threading.Thread(target=finish_calculation)
    worker.start()
    assert started.wait(2)
    import json
    edited = moved(source)
    lock.execute("UPDATE projects SET project_input_json = ? WHERE project_id = ?", (json.dumps(edited), project_id))
    lock.commit()
    lock.close()
    assert completed.wait(5)
    worker.join()
    assert not isinstance(outcome[0], Exception)
    assert outcome[0]["metadata"]["calculation_save_v1"]["disposition"] == "archived"
    assert store.get_project(user_id=user, project_id=project_id)["project_input"] == edited
