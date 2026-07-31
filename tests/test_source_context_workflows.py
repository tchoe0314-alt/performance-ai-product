from backend.application.source_context_workflows import (
    build_detection_coverage_report,
    build_source_context_job_runner,
    queue_source_context_job,
)
from backend.application.project_workflows import review_project_candidates


class FakeProjectStore:
    def __init__(self):
        self.project = {
            "user_id": "u1",
            "project_id": "p1",
            "name": "Site",
            "description": "",
            "session_id": None,
            "tags": [],
            "project_input": {"meta": {"site_inputs": {"address": "20525 Margo St"}}},
            "latest_result": {},
            "session_state": {},
            "metadata": {},
        }
        self.saved = None

    def get_project(self, *, user_id, project_id):
        return dict(self.project) if user_id == "u1" and project_id == "p1" else None

    def save_project(self, **kwargs):
        kwargs.pop("minimum_role", None)
        self.saved = kwargs
        self.project = {**self.project, **kwargs}
        return dict(self.project)


class FakeQueue:
    def __init__(self):
        self.submitted = None

    def submit_job(self, *, user_id, job_type, payload, project_id=None):
        self.submitted = {
            "user_id": user_id,
            "job_type": job_type,
            "payload": payload,
            "project_id": project_id,
        }
        return {
            "job_id": "job_source",
            "job_type": job_type,
            "status": "queued",
            "project_id": project_id,
        }


def source_result():
    return {
        "success": True,
        "online_existing_conditions_discovery_v1": {
            "version": "online_existing_conditions_discovery_v1",
            "status": "candidates_found",
            "candidate_count": 2,
            "sources": [
                {
                    "key": "building_footprints",
                    "label": "Building footprints",
                    "status": "candidates_found",
                    "candidate_count": 1,
                    "provider": "official_gis",
                },
                {
                    "key": "roads_row",
                    "label": "Roads / ROW",
                    "status": "candidates_found",
                    "candidate_count": 1,
                    "provider": "official_gis",
                },
                {
                    "key": "existing_utilities",
                    "label": "Existing utilities",
                    "status": "unconfigured",
                    "candidate_count": 0,
                },
            ],
        },
        "map_feature_detection_report_v1": {
            "version": "map_feature_detection_report_v1",
            "candidate_count": 2,
            "feature_candidates": [
                {
                    "candidate_id": "building-1",
                    "feature_type": "building_footprint",
                    "source_type": "official_gis",
                    "source_name": "County buildings",
                    "geometry": {"type": "Polygon", "coordinates": []},
                    "confidence": 0.9,
                    "acceptance_status": "pending",
                    "review_required": True,
                },
                {
                    "candidate_id": "road-1",
                    "feature_type": "road_or_drive",
                    "source_type": "official_gis",
                    "source_name": "County roads",
                    "geometry": {"type": "LineString", "coordinates": []},
                    "confidence": 0.9,
                    "acceptance_status": "pending",
                    "review_required": True,
                },
            ],
        },
        "existing_conditions_package": {"version": "existing_conditions_package_v1"},
        "existing_conditions_summary": {"status": "review_required"},
    }


def test_queue_source_context_job_submits_background_work():
    store = FakeProjectStore()
    queue = FakeQueue()
    response = queue_source_context_job(
        project_store=store,
        job_queue=queue,
        user_id="u1",
        project_id="p1",
        request_payload={"address": "20525 Margo St"},
    )
    assert response["success"] is True
    assert response["job"]["job_id"] == "job_source"
    assert queue.submitted["job_type"] == "source_context"


def test_detection_coverage_reports_found_missing_and_field_only_categories():
    coverage = build_detection_coverage_report(source_result())
    by_key = {item["key"]: item for item in coverage["categories"]}
    assert by_key["buildings"]["status"] == "found"
    assert by_key["roads_row"]["status"] == "found"
    assert by_key["utilities"]["status"] == "source_unavailable"
    assert by_key["survey_control"]["status"] == "requires_project_source"
    assert by_key["buried_utility_locates"]["status"] == "requires_project_source"


def test_source_context_runner_persists_candidates_before_generation():
    store = FakeProjectStore()
    progress = []
    runner = build_source_context_job_runner(
        project_store=store,
        update_job_progress=lambda job_id, **kwargs: progress.append({"job_id": job_id, **kwargs}),
        fetch_source_context=lambda **_: source_result(),
    )
    result = runner(
        {
            "job_id": "job_source",
            "user_id": "u1",
            "project_id": "p1",
            "payload": {"address": "20525 Margo St"},
        }
    )
    site_inputs = store.saved["project_input"]["meta"]["site_inputs"]
    assert result["candidate_review_inbox_v1"]["candidate_count"] == 2
    assert site_inputs["candidate_review_inbox_v1"]["counts"]["pending"] == 2
    assert site_inputs["source_context_detection_coverage_v1"]["found_category_count"] == 2
    assert store.saved["latest_result"] == {}
    assert progress[-1]["stage"] == "Preparing Candidate Review"


def test_candidate_can_be_accepted_before_any_generated_plan_exists():
    store = FakeProjectStore()
    runner = build_source_context_job_runner(
        project_store=store,
        update_job_progress=lambda *_args, **_kwargs: None,
        fetch_source_context=lambda **_: source_result(),
    )
    runner(
        {
            "job_id": "job_source",
            "user_id": "u1",
            "project_id": "p1",
            "payload": {"address": "20525 Margo St"},
        }
    )
    response = review_project_candidates(
        project_store=store,
        user_id="u1",
        project_id="p1",
        candidate_ids=["building-1"],
        action="accept",
        reviewer_id="u1",
    )
    assert response["candidate_review_inbox_v1"]["counts"]["accepted"] == 1
    assert store.saved["project_input"]["meta"]["site_inputs"]["candidate_review_accepted_drafts_v1"][0]["source_candidate_id"] == "building-1"
    assert store.saved["latest_result"] == {}

    rejected = review_project_candidates(
        project_store=store,
        user_id="u1",
        project_id="p1",
        candidate_ids=["building-1"],
        action="reject",
        reviewer_id="u1",
    )
    saved_inputs = store.saved["project_input"]["meta"]["site_inputs"]
    assert rejected["candidate_review_inbox_v1"]["counts"]["accepted"] == 0
    assert rejected["candidate_review_inbox_v1"]["counts"]["rejected"] == 1
    assert saved_inputs["candidate_review_accepted_drafts_v1"] == []


def test_source_context_rerun_preserves_existing_review_decisions():
    store = FakeProjectStore()
    runner = build_source_context_job_runner(
        project_store=store,
        update_job_progress=lambda *_args, **_kwargs: None,
        fetch_source_context=lambda **_: source_result(),
    )
    job = {
        "job_id": "job_source",
        "user_id": "u1",
        "project_id": "p1",
        "payload": {"address": "20525 Margo St"},
    }
    runner(job)
    review_project_candidates(
        project_store=store,
        user_id="u1",
        project_id="p1",
        candidate_ids=["building-1"],
        action="accept",
        reviewer_id="u1",
    )

    rerun = runner({**job, "job_id": "job_source_rerun"})

    assert rerun["candidate_review_inbox_v1"]["counts"]["accepted"] == 1
    assert rerun["candidate_review_inbox_v1"]["counts"]["pending"] == 1
    site_inputs = store.saved["project_input"]["meta"]["site_inputs"]
    assert site_inputs["candidate_review_accepted_drafts_v1"][0]["source_candidate_id"] == "building-1"
