"""Candidate decisions must not erase a concurrent review or new source set."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from fastapi import HTTPException

from backend.application.project_workflows import review_project_candidates
from backend.planning.candidate_review_inbox import build_candidate_review_inbox
from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.project_revision import ProjectRevisionConflict
from backend.services.project_store import ProjectStore


@pytest.fixture
def project(tmp_path):
    store = ProjectStore(Database(tmp_path / "reviews.db"))
    user = AuthStore(store.db).register_user(email="reviews@example.test", password="Synthetic-only-123", name="Review")["user"]["user_id"]
    report = {"feature_candidates": [{"candidate_id": "b1", "feature_type": "building_footprint",
        "source_type": "official_gis", "source_name": "Synthetic source", "confidence": 0.9,
        "acceptance_status": "pending"}]}
    inputs = {"map_feature_detection_report_v1": report,
        "candidate_review_inbox_v1": build_candidate_review_inbox({"map_feature_detection_report_v1": report})}
    saved = store.save_project(user_id=user, project_id=None, name="Synthetic", project_input={"meta": {"site_inputs": inputs}})
    return store, user, saved


def test_second_review_from_same_snapshot_cannot_overwrite_first(project):
    store, user, saved = project
    shell = store.get_project_shell(user_id=user, project_id=saved["project_id"])
    store.update_project_candidate_review_state(user_id=user, project_id=saved["project_id"],
        candidate_state={"review_marker": "first"}, expected_revision=shell["revision_token"])
    before = store.get_project(user_id=user, project_id=saved["project_id"])
    with pytest.raises(ProjectRevisionConflict):
        store.update_project_candidate_review_state(user_id=user, project_id=saved["project_id"],
            candidate_state={"review_marker": "second"}, expected_revision=shell["revision_token"])
    assert store.get_project(user_id=user, project_id=saved["project_id"]) == before


def test_workflow_conflicts_if_source_changes_during_review(project, monkeypatch):
    store, user, saved = project
    original = store.update_project_candidate_review_state
    committed = []
    def competing_update(**kwargs):
        current = store.get_project_shell(user_id=user, project_id=saved["project_id"])
        inputs = deepcopy(current["project_input"])
        inputs["meta"]["site_inputs"]["source_revision"] = "new survey"
        store.save_project_shell(user_id=user, project_id=saved["project_id"], name="Updated source",
            project_input=inputs, expected_revision=current["revision_token"])
        committed.append(store.get_project(user_id=user, project_id=saved["project_id"]))
        return original(**kwargs)
    monkeypatch.setattr(store, "update_project_candidate_review_state", competing_update)
    with pytest.raises(HTTPException) as error:
        review_project_candidates(project_store=store, user_id=user, project_id=saved["project_id"],
            candidate_ids=["b1"], action="accept")
    assert error.value.status_code == 409
    assert store.get_project(user_id=user, project_id=saved["project_id"]) == committed[0]


def test_simultaneous_review_updates_have_one_winner(project):
    store, user, saved = project
    shell = store.get_project_shell(user_id=user, project_id=saved["project_id"])
    barrier = threading.Barrier(2)
    def update(index):
        barrier.wait(timeout=5)
        try:
            store.update_project_candidate_review_state(user_id=user, project_id=saved["project_id"],
                candidate_state={"review_marker": str(index)}, expected_revision=shell["revision_token"])
            return "saved"
        except ProjectRevisionConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(update, range(2))) == ["conflict", "saved"]
