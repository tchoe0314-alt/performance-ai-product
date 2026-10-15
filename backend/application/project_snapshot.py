"""Revision-aware boundary for existing server read/modify/save workflows."""
from fastapi import HTTPException
from backend.services.project_revision import ProjectRevisionConflict, project_revision, result_revision


def save_project_snapshot(store, snapshot: dict, **kwargs):
    kwargs["expected_revision"] = snapshot.get("revision_token") or project_revision(snapshot)
    kwargs["expected_result_revision"] = result_revision(snapshot)
    try:
        return store.save_project(**kwargs)
    except ProjectRevisionConflict as exc:
        raise HTTPException(status_code=409, detail="Project changed during this operation. Reopen it and retry.") from exc
