"""Public save preconditions; no existing user or project access."""
import importlib

import pytest
from fastapi import HTTPException


def test_existing_project_requires_revision_before_any_write(monkeypatch):
    api = importlib.import_module("backend.api.app")
    calls = []
    monkeypatch.setattr(api,"application_save_project_record",lambda **kwargs:calls.append(kwargs))
    for replace in (False,True):
        with pytest.raises(HTTPException) as error:
            api.save_project(api.SaveProjectPayload(project_id="synthetic",name="Test",replace_original=replace),{"user_id":"test"})
        assert error.value.status_code == 409
    assert calls == []


def test_new_project_and_revision_bound_save_reach_normal_authorization(monkeypatch):
    api = importlib.import_module("backend.api.app")
    calls=[]
    def save(**kwargs):
        calls.append(kwargs); return {"success":True}
    monkeypatch.setattr(api,"application_save_project_record",save)
    api.save_project(api.SaveProjectPayload(name="New"),{"user_id":"test"})
    api.save_project(api.SaveProjectPayload(project_id="synthetic",name="Existing",expected_revision="a"*64),{"user_id":"test"})
    assert len(calls) == 2
    assert calls[1]["payload_data"]["expected_revision"] == "a"*64
