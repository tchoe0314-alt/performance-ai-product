"""A design autosave cannot publish, roll back or recertify calculation output."""
from copy import deepcopy
import importlib

import pytest
from fastapi import HTTPException

from backend.services.auth_store import AuthStore
from backend.services.canonical_canvas import with_canvas_snapshot
from backend.services.canonical_results import ENGINE_REVISION
from backend.services.database import Database
from backend.services.project_store import ProjectStore


@pytest.mark.parametrize("echo", [{}, {"success": True, "message": "Old browser output"},
    {"success": True, "metadata": {"calculation_engine_revision": ENGINE_REVISION},
     "final_plan": {"meta": {"quantities": {"invented_volume": 999999}}}}])
def test_browser_save_preserves_new_server_calculation(tmp_path, monkeypatch, echo):
    api = importlib.import_module("backend.api.app")
    db = Database(tmp_path / "ownership.db")
    auth = AuthStore(db)
    actor = auth.register_user(email="ownership@example.test", password="Synthetic-only-123", name="Owner")["user"]
    store = ProjectStore(db)
    project = store.save_project(user_id=actor["user_id"], project_id=None, name="Before",
        project_input=with_canvas_snapshot({"manual_fields": {"units": "ft"}}))
    store.save_calculation_result(user_id=actor["user_id"], project_id=project["project_id"],
        source_input=project["project_input"], result={"success": True, "message": "New server output",
            "metadata": {"calculation_engine_revision": ENGINE_REVISION}})
    store.update_project_metadata(user_id=actor["user_id"],project_id=project["project_id"],
        update_metadata=lambda record:{**record["metadata"],"review_evidence":{"version":"server"}})
    before = store.get_project(user_id=actor["user_id"], project_id=project["project_id"])
    monkeypatch.setattr(api, "PROJECT_STORE", store)
    monkeypatch.setattr(api, "_maybe_export_session", lambda _: {})
    response = api.save_project(api.SaveProjectPayload(project_id=project["project_id"],
        expected_revision=project["revision_token"], name="Renamed", project_input=project["project_input"],
        latest_result=deepcopy(echo),metadata={"review_evidence":{"version":"client"},"auto_named":False}), actor)
    after = store.get_project(user_id=actor["user_id"], project_id=project["project_id"])
    assert response["success"] is True
    assert after["name"] == "Renamed"
    assert after["metadata"]["review_evidence"] == {"version":"server"}
    assert after["metadata"]["auto_named"] is False
    assert after["latest_result"] == before["latest_result"]
    assert after["project_input"]["canonical_project_v1"]["calculation_results"] == before["project_input"]["canonical_project_v1"]["calculation_results"]
    with pytest.raises(HTTPException) as error:
        api.save_project(api.SaveProjectPayload(project_id=project["project_id"],
            expected_revision=project["revision_token"], name="Stale tab", latest_result=echo), actor)
    assert error.value.status_code == 409
    assert store.get_project(user_id=actor["user_id"], project_id=project["project_id"]) == after


def test_browser_payload_result_removed_only_for_existing_projects(monkeypatch):
    api = importlib.import_module("backend.api.app")
    calls = []
    monkeypatch.setattr(api, "application_save_project_record", lambda **kw: calls.append(kw) or {"success": True})
    result = {"message": "Imported legacy snapshot"}
    api.save_project(api.SaveProjectPayload(name="New", latest_result=result), {"user_id": "synthetic"})
    api.save_project(api.SaveProjectPayload(project_id="existing", expected_revision="a" * 64,
        name="Existing", latest_result=result), {"user_id": "synthetic"})
    assert calls[0]["payload_data"]["latest_result"]["message"] == result["message"]
    assert calls[0]["payload_data"]["latest_result"]["metadata"]["client_import_v1"]["verified_execution"] is False
    assert "latest_result" not in calls[1]["payload_data"]


@pytest.mark.parametrize("value", ["false", 0, None, {"unexpected":True}])
def test_existing_save_rejects_nonboolean_naming_flags(monkeypatch,value):
    api=importlib.import_module("backend.api.app")
    monkeypatch.setattr(api,"application_save_project_record",lambda **kw:pytest.fail("Invalid naming flag reached persistence"))
    with pytest.raises(HTTPException) as error:
        api.save_project(api.SaveProjectPayload(project_id="existing",expected_revision="a"*64,
            name="Existing",metadata={"auto_named":value}),{"user_id":"synthetic"})
    assert error.value.status_code == 422
