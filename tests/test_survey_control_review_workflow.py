from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.project_store import ProjectStore
from backend.services.project_revision import project_revision
from tests.remediation.identity_fixtures import invite_test_member


DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def _project_input(*, owner_user_id: str, source_id: str, digest: str, complete: bool = True) -> dict:
    review = {
        "status": "complete_for_review" if complete else "blocked",
        "source_digest": digest if complete else "",
        "review_only": True,
        "grading_authorized": False,
    }
    return {
        "meta": {
            "site_inputs": {
                "survey_file": {
                    "stored_filename": source_id,
                    "source_reference": {
                        "source_id": source_id,
                        "source_digest": digest,
                        "owner_user_id": owner_user_id,
                        "immutable": True,
                    },
                },
                "survey_control_evidence_review": review,
            },
            "survey_control_evidence_review": review,
        }
    }


@pytest.fixture()
def stores():
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Database(Path(temp_dir) / "survey-review.db")
        auth = AuthStore(database)
        projects = ProjectStore(database)
        owner = auth.register_user(email="owner@example.test", password="password-1", name="Owner")["user"]
        reviewer = auth.register_user(email="reviewer@example.test", password="password-1", name="Reviewer")["user"]
        viewer = auth.register_user(email="viewer@example.test", password="password-1", name="Viewer")["user"]
        yield database, projects, owner, reviewer, viewer


def test_reviewer_decision_is_bound_audited_and_remains_review_only(stores) -> None:
    database, projects, owner, reviewer, _viewer = stores
    project = projects.save_project(
        user_id=owner["user_id"], project_id=None, name="Synthetic survey review",
        project_input=_project_input(owner_user_id=owner["user_id"], source_id="upload-a.csv", digest=DIGEST_A),
    )
    invite_test_member(projects, actor_user_id=owner["user_id"], project_id=project["project_id"], email=reviewer["email"], role="reviewer")

    decision = projects.record_survey_control_review(
        user_id=reviewer["user_id"], project_id=project["project_id"],
        source_id="upload-a.csv", source_digest=DIGEST_A,
        decision="accepted_for_review", note="Metadata and source identity match.",
    )

    assert decision["reviewer_user_id"] == reviewer["user_id"]
    assert decision["reviewer_role"] == "reviewer"
    assert decision["review_only"] is True
    assert decision["grading_authorized"] is False
    assert decision["construction_release_allowed"] is False
    saved = projects.get_project(user_id=owner["user_id"], project_id=project["project_id"])
    assert saved["metadata"]["survey_control_reviews_v1"][-1] == decision
    assert saved["project_input"]["meta"]["site_inputs"]["survey_control_evidence_review"]["grading_authorized"] is False
    connection = database.connect()
    try:
        audit = connection.execute(
            "SELECT action, actor_user_id, metadata_json FROM access_audit_log WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (project["project_id"],),
        ).fetchone()
    finally:
        connection.close()
    assert audit["action"] == "survey_control_review_recorded"
    assert audit["actor_user_id"] == reviewer["user_id"]
    assert DIGEST_A in audit["metadata_json"]


def test_review_rejects_viewer_incomplete_replaced_and_cross_project_sources(stores) -> None:
    _database, projects, owner, reviewer, viewer = stores
    project = projects.save_project(
        user_id=owner["user_id"], project_id=None, name="Project A",
        project_input=_project_input(owner_user_id=owner["user_id"], source_id="upload-a.csv", digest=DIGEST_A, complete=False),
    )
    invite_test_member(projects, actor_user_id=owner["user_id"], project_id=project["project_id"], email=reviewer["email"], role="reviewer")
    invite_test_member(projects, actor_user_id=owner["user_id"], project_id=project["project_id"], email=viewer["email"], role="viewer")

    with pytest.raises(ValueError, match="reviewer access"):
        projects.record_survey_control_review(
            user_id=viewer["user_id"], project_id=project["project_id"], source_id="upload-a.csv",
            source_digest=DIGEST_A, decision="rejected",
        )
    with pytest.raises(ValueError, match="incomplete, mismatched, or stale"):
        projects.record_survey_control_review(
            user_id=reviewer["user_id"], project_id=project["project_id"], source_id="upload-a.csv",
            source_digest=DIGEST_A, decision="accepted_for_review",
        )
    with pytest.raises(ValueError, match="replaced or does not belong"):
        projects.record_survey_control_review(
            user_id=reviewer["user_id"], project_id=project["project_id"], source_id="upload-b.csv",
            source_digest=DIGEST_B, decision="rejected",
        )

    current = projects.get_project(user_id=owner["user_id"], project_id=project["project_id"])
    replaced = projects.save_project(
        user_id=owner["user_id"], project_id=project["project_id"], name=project["name"],
        project_input=_project_input(owner_user_id=owner["user_id"], source_id="upload-b.csv", digest=DIGEST_B),
        expected_revision=project_revision(current),
    )
    assert replaced["project_input"]["meta"]["site_inputs"]["survey_file"]["source_reference"]["source_id"] == "upload-b.csv"
    with pytest.raises(ValueError, match="replaced or does not belong"):
        projects.record_survey_control_review(
            user_id=reviewer["user_id"], project_id=project["project_id"], source_id="upload-a.csv",
            source_digest=DIGEST_A, decision="rejected",
        )


def test_browser_metadata_save_cannot_erase_server_owned_review_history(stores) -> None:
    _database, projects, owner, _reviewer, _viewer = stores
    project = projects.save_project(
        user_id=owner["user_id"], project_id=None, name="Protected review history",
        project_input=_project_input(owner_user_id=owner["user_id"], source_id="upload-a.csv", digest=DIGEST_A),
    )
    review = projects.record_survey_control_review(
        user_id=owner["user_id"], project_id=project["project_id"], source_id="upload-a.csv",
        source_digest=DIGEST_A, decision="accepted_for_review",
    )
    current = projects.get_project(user_id=owner["user_id"], project_id=project["project_id"])
    saved = projects.save_project(
        user_id=owner["user_id"], project_id=project["project_id"], name=current["name"],
        project_input=current["project_input"], metadata={"survey_control_reviews_v1": []},
        expected_revision=project_revision(current),
    )
    assert saved["metadata"]["survey_control_reviews_v1"] == [review]
