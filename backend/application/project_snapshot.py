"""Revision-aware boundary for existing server read/modify/save workflows."""
from fastapi import HTTPException
from backend.services.project_revision import ProjectRevisionConflict, result_revision


def save_project_snapshot(store, snapshot: dict, **kwargs):
    if snapshot.get("revision_token"):
        kwargs["expected_revision"] = snapshot["revision_token"]
        kwargs["expected_result_revision"] = result_revision(snapshot)
    try:
        return store.save_project(**kwargs)
    except ProjectRevisionConflict as exc:
        raise HTTPException(status_code=409, detail="Project changed during this operation. Reopen it and retry.") from exc
