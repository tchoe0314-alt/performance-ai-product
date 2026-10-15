from copy import deepcopy
import importlib
import pytest
from fastapi import HTTPException
from backend.services.auth_store import AuthStore
from backend.services.canonical_canvas import with_canvas_snapshot
from backend.services.database import Database
from backend.services.project_store import ProjectStore
from tests.remediation.identity_fixtures import invite_test_member
from backend.services.canonical_results import ENGINE_REVISION

api = importlib.import_module("backend.api.app")


@pytest.fixture
def direct(tmp_path, monkeypatch):
    db = Database(tmp_path / "direct.db")
    auth, store = AuthStore(db), ProjectStore(db)
    owner = auth.register_user(email="owner@example.test", password="Disposable-123", name="Owner")["user"]
    viewer = auth.register_user(email="viewer@example.test", password="Disposable-123", name="Viewer")["user"]
    source = with_canvas_snapshot({"manual_fields": {"units": "ft", "site_objects": [{"id": "office", "type": "building", "x": 20, "y": 30, "w": 40, "d": 50}]}})
    project = store.save_project(user_id=owner["user_id"], project_id=None, name="Direct fixture", project_input=source)
    invite_test_member(store,actor_user_id=owner["user_id"], project_id=project["project_id"], email=viewer["email"], role="viewer")
    monkeypatch.setattr(api, "PROJECT_STORE", store)
    request = api.OrchestratePayload(**{**source, "project_id": project["project_id"]})
    return store, owner, viewer, project, source, request


def test_direct_success_is_persisted_with_exact_input_binding(direct, monkeypatch):
    store, owner, _, project, _, request = direct
    monkeypatch.setattr(api, "_run_orchestration", lambda *_args, **_kwargs: {"success": True, "metadata":{"calculation_engine_revision":ENGINE_REVISION}, "final_plan": {"actions": [], "meta": {}}})
    response = api.orchestrate(request, current_user=owner, _rate_limit=None)
    assert response["metadata"]["calculation_save_v1"]["disposition"] == "active"
    saved = store.get_project(user_id=owner["user_id"], project_id=project["project_id"])
    assert saved["latest_result"]["metadata"]["calculation_save_v1"] == response["metadata"]["calculation_save_v1"]
    assert len(store.list_calculation_history(user_id=owner["user_id"], project_id=project["project_id"])) == 1


def test_direct_late_result_archives_without_overwriting_an_edit(direct, monkeypatch):
    store, owner, _, project, source, request = direct
    changed = deepcopy(source)
    changed["manual_fields"]["site_objects"][0]["x"] = 100
    changed = with_canvas_snapshot(changed)
    def run(*_args, **_kwargs):
        store.save_project_shell(expected_revision=store.get_project(user_id=owner["user_id"], project_id=project["project_id"])["revision_token"], user_id=owner["user_id"], project_id=project["project_id"], name="Changed", project_input=changed)
        return {"success": True, "metadata":{"calculation_engine_revision":ENGINE_REVISION}, "final_plan": {"actions": [], "meta": {}}}
    monkeypatch.setattr(api, "_run_orchestration", run)
    response = api.orchestrate(request, current_user=owner, _rate_limit=None)
    assert response["metadata"]["calculation_save_v1"]["disposition"] == "archived"
    saved = store.get_project(user_id=owner["user_id"], project_id=project["project_id"])
    assert saved["project_input"]["manual_fields"]["site_objects"][0]["x"] == 100
    assert not saved["latest_result"]


def test_viewer_cannot_run_or_save_project_calculations(direct, monkeypatch):
    _, _, viewer, _, _, request = direct
    monkeypatch.setattr(api, "_run_orchestration", lambda *_args, **_kwargs: pytest.fail("Viewer reached calculation engine"))
    with pytest.raises(HTTPException) as error:
        api.orchestrate(request, current_user=viewer, _rate_limit=None)
    assert error.value.status_code == 403
