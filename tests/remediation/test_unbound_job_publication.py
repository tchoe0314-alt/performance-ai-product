"""Unbound execution must be recoverable without overwriting a live design."""
from copy import deepcopy

import pytest

from backend.application.job_workflows import _save_generated_calculation
from backend.services.auth_store import AuthStore
from backend.services.canonical_canvas import with_canvas_snapshot
from backend.services.canonical_results import ENGINE_REVISION
from backend.services.database import Database
from backend.services.project_store import ProjectStore


@pytest.mark.parametrize("success", [True, False])
def test_unbound_job_never_falls_back_to_full_save(tmp_path, monkeypatch, success):
    db = Database(tmp_path / "unbound.db")
    owner = AuthStore(db).register_user(email="unbound@example.test", password="Synthetic-only-123", name="Owner")["user"]["user_id"]
    store = ProjectStore(db)
    project = store.save_project(user_id=owner, project_id=None, name="Current design",
        project_input=with_canvas_snapshot({"manual_fields": {"units": "ft", "site_objects": [
            {"id": "b1", "type": "office_building", "x": 250, "y": 0, "w": 30, "d": 20}]}}))
    before = store.get_project(user_id=owner, project_id=project["project_id"])
    source = {"manual_fields": {"units": "ft", "building_width": 10}, "meta": {"legacy": True}}
    generated = {"success": success, "message": "Delayed legacy execution",
        "metadata": {"calculation_engine_revision": ENGINE_REVISION}}
    original = deepcopy(generated)
    monkeypatch.setattr(store, "save_project", lambda **_: pytest.fail("Unbound result attempted a full project save"))
    _save_generated_calculation(store, user_id=owner, project_id=project["project_id"],
        name="Old design", project_input=source, latest_result=generated)
    assert generated["metadata"]["calculation_save_v1"]["reason"] == "input_binding_unverified"
    assert store.get_project(user_id=owner, project_id=project["project_id"]) == before
    history = store.list_calculation_history(user_id=owner, project_id=project["project_id"])
    assert len(history) == 1
    assert history[0]["is_active"] is False
    assert history[0]["disposition"] == "archived"
    reopened = ProjectStore(Database(db.db_path))
    saved = reopened.get_calculation_history(user_id=owner, project_id=project["project_id"], calculation_id=history[0]["calculation_id"])
    assert saved["source_input"] == source
    assert saved["result"]["message"] == original["message"]
    assert saved["result"]["success"] is success


def test_unbound_signature_does_not_accept_nonfinite_input(tmp_path):
    store = ProjectStore(Database(tmp_path / "invalid.db"))
    with pytest.raises(ValueError):
        store.save_calculation_result(user_id="synthetic", project_id="synthetic",
            source_input={"area": float("nan")}, result={"success": True})
