from copy import deepcopy
import importlib
import pytest
from fastapi import HTTPException
from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.workspace_layout import DEFAULT_LAYOUT, read_layout, save_layout, validate_layout
from backend.services.project_store import ProjectStore

def test_account_layout_isolated_and_reset_without_project_change(tmp_path,monkeypatch):
    db=Database(tmp_path/"layout.db");auth=AuthStore(db);store=ProjectStore(db)
    users=[auth.register_user(email=f"layout-{i}@example.test",password="Disposable-123",name=f"User {i}")["user"] for i in range(2)]
    first,second=users
    project=store.save_project(user_id=first["user_id"],project_id=None,name="Unchanged")
    before=store.get_project(user_id=first["user_id"],project_id=project["project_id"])
    custom={**DEFAULT_LAYOUT,"mode":"professional","leftWidth":400,"leftVisible":True}
    assert save_layout(db,first["user_id"],custom)==custom
    assert read_layout(Database(tmp_path/"layout.db"),first["user_id"])==custom
    assert read_layout(db,second["user_id"])==DEFAULT_LAYOUT
    api=importlib.import_module("backend.api.app");monkeypatch.setattr(api,"AUTH_STORE",auth)
    assert api.get_workspace_layout(second)["layout"]==DEFAULT_LAYOUT
    assert api.put_workspace_layout(DEFAULT_LAYOUT,first)["layout"]==DEFAULT_LAYOUT
    assert store.get_project(user_id=first["user_id"],project_id=project["project_id"])==before
    with pytest.raises(HTTPException) as error:api.put_workspace_layout({"user_id":first["user_id"]},second)
    assert error.value.status_code==422

@pytest.mark.parametrize("key,value",[("version",True),("mode","other"),("leftWidth",0),("rightWidth",float("inf")),("deltaHeight",49.5),("leftVisible","yes")])
def test_layout_validation_rejects_corruption(key,value):
    candidate=deepcopy(DEFAULT_LAYOUT);candidate[key]=value
    with pytest.raises(ValueError):validate_layout(candidate)
