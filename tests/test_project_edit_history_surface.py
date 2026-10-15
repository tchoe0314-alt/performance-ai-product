from copy import deepcopy
import pytest
from fastapi import HTTPException
import importlib
api = importlib.import_module("backend.api.app")
from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.project_store import ProjectStore
from backend.services.canonical_canvas import with_canvas_snapshot
from tests.remediation.identity_fixtures import invite_test_member

def test_named_history_is_access_checked_and_uses_server_actor(tmp_path, monkeypatch):
    store=ProjectStore(Database(tmp_path / "history.db")); auth=AuthStore(store.db)
    users=[auth.register_user(email=f"{name}@example.test", password="Disposable-123", name=name)["user"] for name in ["Creator", "Editor", "Viewer", "Outsider"]]
    creator,editor,viewer,outsider=users
    inputs=with_canvas_snapshot({"manual_fields":{"units":"ft","site_objects":[{"id":"a","type":"office_building","x":0,"y":0,"w":20,"d":20}]}})
    project=store.save_project(user_id=creator["user_id"],project_id=None,name="History",project_input=inputs)
    pid=project["project_id"]
    invite_test_member(store,actor_user_id=creator["user_id"],project_id=pid,email=editor["email"],role="editor")
    invite=invite_test_member(store,actor_user_id=creator["user_id"],project_id=pid,email=viewer["email"])
    assert invite["role"]=="viewer"
    changed=deepcopy(project["project_input"]); changed["manual_fields"]["site_objects"][0]["x"]=10
    store.save_project(user_id=editor["user_id"],project_id=pid,name="History",project_input=with_canvas_snapshot(changed),expected_revision=project["revision_token"])
    monkeypatch.setattr(api,"PROJECT_STORE",store)
    surface=api.get_project_edit_history(pid,viewer)
    assert surface["creator_name"]=="Creator"
    assert surface["entries"][0]["actor_name"]=="Editor"
    assert surface["entries"][0]["actor_user_id"]==editor["user_id"]
    assert "before" not in surface["entries"][0]
    with pytest.raises(HTTPException) as error: api.get_project_edit_history(pid,outsider)
    assert error.value.status_code==404
