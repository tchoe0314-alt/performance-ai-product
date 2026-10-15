from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import threading

import pytest
from fastapi import HTTPException

from backend.application.project_workflows import save_project_record
from backend.services.auth_store import AuthStore
from backend.services.canonical_canvas import with_canvas_snapshot
from backend.services.database import Database
from backend.services.project_revision import ProjectRevisionConflict
from backend.services.project_store import ProjectStore
from backend.services.canonical_results import ENGINE_REVISION
from tests.remediation.identity_fixtures import invite_test_member


@pytest.fixture
def setup(tmp_path):
    db = Database(tmp_path / "revisions.db")
    auth = AuthStore(db)
    user = auth.register_user(email="revision@example.test", password="Disposable-123", name="Revision")["user"]["user_id"]
    store = ProjectStore(db)
    inputs = with_canvas_snapshot({"manual_fields": {"units": "ft", "site_objects": [
        {"id": "building", "type": "office_building", "x": 100, "y": 0, "w": 40, "d": 30}
    ]}})
    project = store.save_project(user_id=user, project_id=None, name="Pilot", project_input=inputs)
    return store, auth, user, project


@pytest.mark.parametrize("method", ["save_project", "save_project_shell"])
def test_stale_revision_rejected_without_any_project_changes(setup, method):
    store, _, user, project = setup
    save = getattr(store, method)
    new = save(user_id=user, project_id=project["project_id"], name="First tab", expected_revision=project["revision_token"])
    assert new["revision_token"] != project["revision_token"]
    before = store.get_project(user_id=user, project_id=project["project_id"])
    with pytest.raises(ProjectRevisionConflict):
        save(user_id=user, project_id=project["project_id"], name="Second tab", expected_revision=project["revision_token"])
    assert store.get_project(user_id=user, project_id=project["project_id"]) == before


def test_simultaneous_saves_have_one_winner(setup):
    store, _, user, project = setup
    barrier = threading.Barrier(2)
    def save(index):
        barrier.wait(timeout=5)
        try:
            store.save_project_shell(user_id=user, project_id=project["project_id"], name=f"Tab {index}", expected_revision=project["revision_token"])
            return "saved"
        except ProjectRevisionConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(save, range(2))) == ["conflict", "saved"]


@pytest.mark.parametrize("method", ["save_project", "save_project_shell"])
def test_explicit_replacement_keeps_detached_recovery_snapshot(setup, method):
    store, _, user, project = setup
    save = getattr(store, method)
    save(user_id=user, project_id=project["project_id"], name="Replacement", expected_revision=project["revision_token"], replace_original=True)
    after = store.get_project(user_id=user, project_id=project["project_id"])
    snapshot = after["metadata"]["branch_recovery_v1"][0]
    assert snapshot["project"]["project_input"] == project["project_input"]
    assert snapshot["revision"] == project["revision_token"]
    assert "branch_recovery_v1" not in snapshot["project"]["metadata"]
    with pytest.raises(ValueError):
        save(user_id=user, project_id=project["project_id"], name="Unchecked", replace_original=True)


def test_api_workflow_returns_409_and_preserves_newer_artifact_metadata(setup):
    store, _, user, project = setup
    store.update_project_metadata(user_id=user, project_id=project["project_id"], update_metadata=lambda _: {"workflow": {"artifacts": [{"artifact_id": "a"}]}})
    saved = save_project_record(project_store=store, user_id=user, payload_data={"project_id": project["project_id"],
        "name": "Renamed", "expected_revision": project["revision_token"], "metadata": {"workflow": {"artifacts": []}}})["project"]
    assert saved["metadata"]["workflow"]["artifacts"][0]["artifact_id"] == "a"
    with pytest.raises(HTTPException) as exc:
        save_project_record(project_store=store, user_id=user, payload_data={"project_id": project["project_id"],
            "name": "Stale", "expected_revision": project["revision_token"]})
    assert exc.value.status_code == 409


def test_collaborator_full_save_does_not_transfer_ownership(setup):
    store, auth, owner, project = setup
    editor = auth.register_user(email="editor@example.test", password="Disposable-123", name="Editor")["user"]["user_id"]
    invite_test_member(store,actor_user_id=owner, project_id=project["project_id"], email="editor@example.test", role="editor")
    saved = store.save_project(user_id=editor, project_id=project["project_id"], name="Editor change", expected_revision=project["revision_token"])
    assert saved["user_id"] == owner
    assert saved["access_role"] == "editor"


def test_server_snapshot_workflow_cannot_restore_old_geometry(setup):
    from backend.application.project_snapshot import save_project_snapshot
    store, _, user, project = setup
    edited = deepcopy(project["project_input"])
    edited["manual_fields"]["site_objects"][0]["x"] = 250
    edited = with_canvas_snapshot(edited)
    store.save_project_shell(user_id=user, project_id=project["project_id"], name="New geometry", project_input=edited)
    before = store.get_project(user_id=user, project_id=project["project_id"])
    with pytest.raises(HTTPException) as exc:
        save_project_snapshot(store, project, user_id=user, project_id=project["project_id"],
                              name="Old operation", project_input=project["project_input"], latest_result={"success": True})
    assert exc.value.status_code == 409
    assert store.get_project(user_id=user, project_id=project["project_id"]) == before


def test_server_snapshot_cannot_restore_old_review_metadata(setup):
    from backend.application.project_snapshot import save_project_snapshot
    store, _, user, project = setup
    store.update_project_metadata(user_id=user,project_id=project["project_id"],
        update_metadata=lambda record:{**record["metadata"],"review_evidence":{"version":"new"}})
    before=store.get_project(user_id=user,project_id=project["project_id"])
    assert before["revision_token"] == project["revision_token"]
    with pytest.raises(HTTPException) as error:
        save_project_snapshot(store,project,user_id=user,project_id=project["project_id"],
            name=project["name"],project_input=project["project_input"],metadata={"review_evidence":{"version":"old"}})
    assert error.value.status_code == 409
    assert store.get_project(user_id=user,project_id=project["project_id"]) == before


def test_current_server_snapshot_can_update_metadata(setup):
    from backend.application.project_snapshot import save_project_snapshot
    store, _, user, project = setup
    saved=save_project_snapshot(store,project,user_id=user,project_id=project["project_id"],
        name=project["name"],project_input=project["project_input"],metadata={"review_evidence":{"version":"new"}})
    assert saved["metadata"]["review_evidence"] == {"version":"new"}


@pytest.mark.parametrize("method", ["save_project", "save_project_shell"])
def test_change_and_restore_does_not_revalidate_old_save_token(setup,method):
    store,_,user,project=setup
    save=getattr(store,method)
    changed=save(user_id=user,project_id=project["project_id"],name="Changed name",expected_revision=project["revision_token"])
    restored=save(user_id=user,project_id=project["project_id"],name=project["name"],expected_revision=changed["revision_token"])
    before=store.get_project(user_id=user,project_id=project["project_id"])
    assert restored["revision_token"] != project["revision_token"]
    with pytest.raises(ProjectRevisionConflict):
        save(user_id=user,project_id=project["project_id"],name="Delayed overwrite",expected_revision=project["revision_token"])
    assert store.get_project(user_id=user,project_id=project["project_id"]) == before


def test_metadata_patch_cannot_drop_or_forge_design_generation(setup):
    store,_,user,project=setup
    generation=project["metadata"]["design_save_generation_v1"]
    for metadata in ({"review":"new"},{"review":"new","design_save_generation_v1":0}):
        store.update_project_metadata(user_id=user,project_id=project["project_id"],update_metadata=lambda _,m=metadata:m)
        current=store.get_project(user_id=user,project_id=project["project_id"])
        assert current["metadata"]["design_save_generation_v1"] == generation
        assert current["revision_token"] == project["revision_token"]


def test_low_level_full_save_requires_revision_and_preserves_record(setup):
    store,_,user,project=setup
    before=store.get_project(user_id=user,project_id=project["project_id"])
    with pytest.raises(ProjectRevisionConflict):
        store.save_project(user_id=user,project_id=project["project_id"],name="Unchecked overwrite")
    assert store.get_project(user_id=user,project_id=project["project_id"]) == before


def test_server_snapshot_cannot_overwrite_a_new_calculation_with_no_geometry_edit(setup):
    from backend.application.project_snapshot import save_project_snapshot
    store, _, user, project = setup
    store.save_calculation_result(user_id=user, project_id=project["project_id"], source_input=project["project_input"],
                                 result={"success": True, "message": "New calculation", "metadata": {"calculation_engine_revision": ENGINE_REVISION}})
    before = store.get_project(user_id=user, project_id=project["project_id"])
    assert before["latest_result"]["message"] == "New calculation"
    assert before["revision_token"] == project["revision_token"]
    with pytest.raises(HTTPException) as exc:
        save_project_snapshot(store, project, user_id=user, project_id=project["project_id"],
                              name="Pilot", project_input=project["project_input"], latest_result={"message": "Old"})
    assert exc.value.status_code == 409
    assert store.get_project(user_id=user, project_id=project["project_id"]) == before


def test_delayed_chat_save_returns_conflict_without_overwriting_new_design(setup, monkeypatch):
    from backend.application import chat_workflows as chat
    store, _, user, snapshot = setup
    snapshot = deepcopy(snapshot)
    snapshot["_user_id"] = user
    # Legacy snapshot without an explicit token still has a derived precondition.
    snapshot.pop("revision_token", None)
    monkeypatch.setattr(chat,"attach_cad_entity_model_to_result",lambda result,**kwargs:result)
    monkeypatch.setattr(chat,"attach_source_confidence_map",lambda result,**kwargs:result)
    store.save_project_shell(user_id=user,project_id=snapshot["project_id"],name="Newer edit")
    before=store.get_project(user_id=user,project_id=snapshot["project_id"])
    with pytest.raises(HTTPException) as error:
        chat._save_project_record(store,snapshot,project_input=snapshot["project_input"],latest_result={})
    assert error.value.status_code == 409
    assert store.get_project(user_id=user,project_id=snapshot["project_id"]) == before
