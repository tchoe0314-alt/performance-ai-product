import json
import importlib
import logging
import tempfile
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.application.design_workflows import run_orchestration
from backend.application.job_workflows import build_orchestrate_job_runner
from backend.services.auth_store import AuthStore
from backend.services.canonical_results import ENGINE_REVISION
from backend.services.database import Database
from backend.services.job_queue import (
    JobQueueService,
    _log_job_transition,
    _transition_reason_category,
)
from backend.services.project_store import ProjectStore
from backend.services.rate_limit_store import RateLimitStore
from tests.test_engineering_generation_workflows import _supported_minimal_payload


def _load_orchestrator():
    from backend.planning.orchestrator import PlannerOrchestratorRequest, orchestrate_plan

    return PlannerOrchestratorRequest, orchestrate_plan


def _wait_for_review(queue, *, user_id, job_id, timeout=20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        detail = queue.get_job_detail(user_id=user_id, job_id=job_id)
        if detail and detail["status"] == "awaiting_approval":
            return detail
        if detail and detail["status"] in {"failed", "cancelled", "completed"}:
            raise AssertionError(f"job reached {detail['status']} before the next review checkpoint")
        time.sleep(0.05)
    raise AssertionError("timed out waiting for the next review checkpoint")


def _summary(result, **kwargs):
    final_meta = dict(dict(result.get("final_plan") or {}).get("meta") or {})
    return {
        "run_id": "synthetic_queue_resume",
        "job_id": kwargs.get("job_id"),
        "source": "queued_job",
        "convergence_summary": {
            "assumption_summary": {"count": 0, "categories": [], "examples": []},
            "unresolved_issue_categories": [],
            "blocked_reasons": [],
            "blocked_exports": [],
        },
        "reliability_summary": {"operational_state": "review", "release_ready": False},
        "phase_checkpoints": dict(final_meta.get("phase_checkpoints") or {}),
        "requested_deliverables": [],
        "produced_deliverables": [],
        "ready_deliverables": [],
        "extra_deliverables": [],
        "failed_deliverables": [],
    }


def test_transition_diagnostic_is_fail_closed(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    record = {
        "job_id": "job_synthetic_allowed",
        "user_id": "must-not-log-user",
        "payload": {
            "manual_fields": {"geometry": [[1, 2], [3, 4]]},
            "meta": {"secret": "must-not-log-secret"},
        },
    }
    monkeypatch.delenv("CIVORA_JOB_TRANSITION_DIAGNOSTIC_IDS", raising=False)
    monkeypatch.delenv("CIVORA_JOB_TRANSITION_DIAGNOSTIC_UNTIL_EPOCH", raising=False)
    _log_job_transition(
        record=record,
        prior_stage="sanitary",
        approved_stage="sanitary",
        next_stage="utility_network",
        reason_category="advanced",
    )
    monkeypatch.setenv("CIVORA_JOB_TRANSITION_DIAGNOSTIC_IDS", record["job_id"])
    _log_job_transition(
        record=record,
        prior_stage="sanitary",
        approved_stage="sanitary",
        next_stage="utility_network",
        reason_category="advanced",
    )
    monkeypatch.setenv(
        "CIVORA_JOB_TRANSITION_DIAGNOSTIC_IDS",
        f"{record['job_id']},job_another",
    )
    monkeypatch.setenv("CIVORA_JOB_TRANSITION_DIAGNOSTIC_UNTIL_EPOCH", str(time.time() + 300))
    _log_job_transition(
        record=record,
        prior_stage="sanitary",
        approved_stage="sanitary",
        next_stage="utility_network",
        reason_category="advanced",
    )
    monkeypatch.setenv("CIVORA_JOB_TRANSITION_DIAGNOSTIC_IDS", "job_different")
    monkeypatch.setenv("CIVORA_JOB_TRANSITION_DIAGNOSTIC_UNTIL_EPOCH", str(time.time() + 300))
    _log_job_transition(
        record=record,
        prior_stage="sanitary",
        approved_stage="sanitary",
        next_stage="utility_network",
        reason_category="advanced",
    )
    monkeypatch.setenv("CIVORA_JOB_TRANSITION_DIAGNOSTIC_IDS", record["job_id"])
    _log_job_transition(
        record=record,
        prior_stage="not-an-allowed-stage",
        approved_stage="sanitary",
        next_stage="utility_network",
        reason_category="advanced",
    )
    assert not [record for record in caplog.records if "JOB_LIFECYCLE " in record.getMessage()]
    assert _transition_reason_category(
        prior_stage="sanitary",
        approved_stage="sanitary",
        next_stage="sanitary",
    ) == "repeated_checkpoint"
    assert _transition_reason_category(
        prior_stage="sanitary",
        approved_stage="sanitary",
        next_stage="utility_network",
    ) == "advanced"
    _log_job_transition(
        record=record,
        prior_stage="sanitary",
        approved_stage="sanitary",
        next_stage="sanitary",
        reason_category="repeated_checkpoint",
        checkpoint_cause="repeated_after_job_checkpoint_resume",
    )
    events = [
        json.loads(item.getMessage().split("JOB_LIFECYCLE ", 1)[1])
        for item in caplog.records
        if "JOB_LIFECYCLE " in item.getMessage()
    ]
    assert [(item["reason_category"], item["prior_stage"], item["approved_stage"], item["next_stage"]) for item in events] == [
        ("repeated_checkpoint", "sanitary", "sanitary", "sanitary")
    ]
    assert events[0]["checkpoint_cause"] == "repeated_after_job_checkpoint_resume"
    diagnostic_text = " ".join(item.getMessage() for item in caplog.records)
    for forbidden in ("must-not-log-user", "must-not-log-secret", "geometry", "1,2"):
        assert forbidden not in diagnostic_text


def test_project_trace_admits_only_first_concurrent_orchestration(monkeypatch, caplog, tmp_path):
    db = Database(tmp_path / "project-trace.db")
    auth = AuthStore(db)
    user_id = auth.register_user(
        email="project-trace@example.invalid",
        password="synthetic-password-123",
        name="Project Trace",
    )["user"]["user_id"]
    queue = JobQueueService(db, worker_count=0)
    overlapping_queue = JobQueueService(db, worker_count=0)
    project_id = "project_exact_disposable_trace"
    ProjectStore(db).save_project(
        user_id=user_id,
        project_id=project_id,
        name="Exact Disposable Trace",
        project_input={},
    )
    trace_start = time.time() - 1
    trace_until = time.time() + 300
    monkeypatch.setenv("CIVORA_PROJECT_TRANSITION_DIAGNOSTIC_ID", project_id)
    monkeypatch.setenv("CIVORA_PROJECT_TRANSITION_DIAGNOSTIC_START_EPOCH", str(trace_start))
    monkeypatch.setenv("CIVORA_JOB_TRANSITION_DIAGNOSTIC_UNTIL_EPOCH", str(trace_until))
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    created = []

    def submit(sequence, service):
        created.append(
            service.submit_job(
                user_id=user_id,
                project_id=project_id,
                job_type="orchestrate",
                payload={"prompt": f"must-not-log-prompt-{sequence}"},
            )
        )

    threads = [
        threading.Thread(target=submit, args=(1, queue)),
        threading.Thread(target=submit, args=(2, overlapping_queue)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)
        assert not thread.is_alive()
    assert len(created) == 2
    initial_job_ids = {item["job_id"] for item in created}
    initial_details = [
        queue.get_job_detail(user_id=user_id, job_id=job_id)
        for job_id in initial_job_ids
    ]
    initially_marked = [
        detail
        for detail in initial_details
        if dict(detail["payload"].get("meta") or {}).get("_job_transition_diagnostic_v1")
    ]
    assert len(initially_marked) == 1
    for job_id in initial_job_ids:
        queue._update_job_state(job_id, status="completed", result={"final_plan": {}}, error=None)
    # A fresh service instance models an API restart during the active trace
    # window. The durable first-job marker must keep the later job untraced.
    restarted_queue = JobQueueService(db, worker_count=0)
    second = restarted_queue.submit_job(
        user_id=user_id,
        project_id=project_id,
        job_type="orchestrate",
        payload={"prompt": "must-not-log-second-completed-run"},
    )
    assert second["job_id"] not in initial_job_ids
    details = [
        restarted_queue.get_job_detail(user_id=user_id, job_id=job_id)
        for job_id in (*initial_job_ids, second["job_id"])
    ]
    marked = [
        detail
        for detail in details
        if dict(detail["payload"].get("meta") or {}).get("_job_transition_diagnostic_v1")
    ]
    assert len(marked) == 1, [
        (detail["job_id"], detail["payload"].get("meta")) for detail in details
    ]
    events = [
        json.loads(record.getMessage().split("JOB_LIFECYCLE ", 1)[1])
        for record in caplog.records
        if "JOB_LIFECYCLE " in record.getMessage()
    ]
    assert len(events) == 1
    assert events[0]["event"] == "job_admitted"
    assert events[0]["correlation_id"] == marked[0]["job_id"]
    diagnostic_text = " ".join(record.getMessage() for record in caplog.records)
    for forbidden in (
        project_id,
        "project-trace@example.invalid",
        "must-not-log-prompt",
        "synthetic-password-123",
    ):
        assert forbidden not in diagnostic_text
    queue.shutdown()
    overlapping_queue.shutdown()
    restarted_queue.shutdown()


@pytest.mark.parametrize(
    "scope,start_offset,until_offset",
    [
        ("project_one,project_two", -1, 300),
        ("", -1, 300),
        ("project_one", -901, 300),
        ("project_one", 30, 300),
        ("project_one", -1, -0.1),
    ],
)
def test_project_trace_scope_fails_closed(monkeypatch, caplog, tmp_path, scope, start_offset, until_offset):
    now = time.time()
    monkeypatch.setenv("CIVORA_PROJECT_TRANSITION_DIAGNOSTIC_ID", scope)
    monkeypatch.setenv("CIVORA_PROJECT_TRANSITION_DIAGNOSTIC_START_EPOCH", str(now + start_offset))
    monkeypatch.setenv("CIVORA_JOB_TRANSITION_DIAGNOSTIC_UNTIL_EPOCH", str(now + until_offset))
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    db = Database(tmp_path / f"fail-closed-{abs(hash((scope, start_offset, until_offset)))}.db")
    auth = AuthStore(db)
    user_id = auth.register_user(
        email=f"fail-closed-{abs(hash(scope))}@example.invalid",
        password="synthetic-password-123",
        name="Fail Closed",
    )["user"]["user_id"]
    queue = JobQueueService(db, worker_count=0)
    ProjectStore(db).save_project(
        user_id=user_id,
        project_id="project_one",
        name="Fail Closed Project",
        project_input={},
    )
    created = queue.submit_job(
        user_id=user_id,
        project_id="project_one",
        job_type="orchestrate",
        payload={"prompt": "must-not-log"},
    )
    detail = queue.get_job_detail(user_id=user_id, job_id=created["job_id"])
    assert "_job_transition_diagnostic_v1" not in dict(detail["payload"].get("meta") or {})
    assert not [record for record in caplog.records if "JOB_LIFECYCLE " in record.getMessage()]
    queue.shutdown()


def test_sqlite_queue_preserves_sanitary_approval_into_real_planner():
    """Exercise the persisted queue/claim/resume merge, not planner alone."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(Path(tmpdir) / "jobs.db")
        auth = AuthStore(db)
        user_id = auth.register_user(
            email="queue-regression@example.invalid",
            password="synthetic-password-123",
            name="Synthetic Queue Regression",
        )["user"]["user_id"]
        store = ProjectStore(db)
        payload = _supported_minimal_payload()
        project_id = "synthetic-sanitary-resume"
        store.save_project(
            user_id=user_id,
            project_id=project_id,
            name="Synthetic Sanitary Resume",
            project_input=payload,
        )
        queue = JobQueueService(
            db,
            heartbeat_interval_sec=0.2,
            resume_poll_interval_sec=0.2,
            in_process_start_delay_sec=0.05,
        )
        try:
            runner = build_orchestrate_job_runner(
                project_store=store,
                update_job_progress=queue.update_job_progress,
                run_orchestration=lambda value, progress_callback=None: run_orchestration(
                    value,
                    load_orchestrator=_load_orchestrator,
                    assess_design_readiness=lambda *_args, **_kwargs: None,
                    progress_callback=progress_callback,
                ),
                build_run_summary=_summary,
                merge_project_metadata=lambda metadata, **_kwargs: metadata,
                final_plan_from_result=lambda result, **_kwargs: dict(result.get("final_plan") or {}),
            )
            queue.register_handler("orchestrate", runner)
            created = queue.submit_job(
                user_id=user_id,
                project_id=project_id,
                job_type="orchestrate",
                payload=payload,
            )

            seen = []
            for expected in ("layout", "grading", "drainage", "storm_pipes", "sanitary"):
                held = _wait_for_review(queue, user_id=user_id, job_id=created["job_id"])
                stage = held["result"]["metadata"]["runtime_phase_checkpoint"]["stage_name"]
                seen.append(stage)
                assert stage == expected
                if expected == "sanitary":
                    with pytest.raises(ValueError, match="checkpoint is stale"):
                        queue.continue_job(
                            user_id=user_id,
                            job_id=created["job_id"],
                            expected_stage="utility_network",
                        )
                    unchanged = queue.get_job_detail(user_id=user_id, job_id=created["job_id"])
                    assert unchanged["status"] == "awaiting_approval"
                    assert "sanitary" not in unchanged["payload"].get("meta", {}).get(
                        "orchestrator_meta", {}
                    ).get("runtime_approved_stages", [])
                queue.continue_job(
                    user_id=user_id,
                    job_id=created["job_id"],
                    expected_stage=expected,
                )

            next_held = _wait_for_review(queue, user_id=user_id, job_id=created["job_id"])
            next_stage = next_held["result"]["metadata"]["runtime_phase_checkpoint"]["stage_name"]
            assert next_stage == "utility_network", {
                "seen": seen,
                "approved": next_held["payload"]["meta"]["orchestrator_meta"].get(
                    "runtime_approved_stages"
                ),
                "next_stage": next_stage,
            }
            assert "_runtime_checkpoint_transition_cause_v1" not in next_held["result"]["metadata"]
        finally:
            queue.shutdown()


def test_unapproved_partial_storm_remains_a_resume_frontier():
    manual_fields = _supported_minimal_payload()
    payload = {
        "project_id": "synthetic-unapproved-partial-storm",
        "full_design_mode": False,
        "input_mode": "user",
        "strict_mode": False,
        "manual_fields": manual_fields,
        "allow_ai_fill_for_blanks": False,
        "meta": {
            "orchestrator_meta": {
                "runtime_phase_batch_limit": 1,
                "runtime_approved_stages": ["layout", "grading", "drainage"],
                "runtime_resume": {
                    "project_id": "synthetic-unapproved-partial-storm",
                    "stage_statuses": {
                        "layout": "complete",
                        "grading": "complete",
                        "drainage": "complete",
                        "storm_pipes": "partial",
                    },
                    "phase_checkpoints": {},
                    "final_plan": {
                        "project_name": "Unapproved partial Storm checkpoint",
                        "actions": [],
                        "meta": {
                            "calculation_engine_revision": ENGINE_REVISION,
                            "stage_completeness": {
                                "statuses": {
                                    "layout": "complete",
                                    "grading": "complete",
                                    "drainage": "complete",
                                    "storm_pipes": "partial",
                                }
                            },
                        },
                    },
                    "source": "synthetic_exact_checkpoint",
                },
            }
        },
    }

    result = run_orchestration(
        payload,
        load_orchestrator=_load_orchestrator,
        assess_design_readiness=lambda *_args, **_kwargs: None,
    )

    storm_rows = [
        row
        for row in result["final_plan"]["meta"]["stage_results"]
        if row.get("stage_name") == "storm_pipes"
    ]
    assert storm_rows
    assert any(
        not bool(dict(row.get("meta") or {}).get("resumed_from_checkpoint"))
        and not bool(dict(row.get("meta") or {}).get("rerun_skipped"))
        for row in storm_rows
    ), storm_rows


def test_sqlite_queue_consumes_authored_sanitary_approval_once(monkeypatch, caplog):
    """Match the normal UI sanitary path through durable queue continuation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(Path(tmpdir) / "jobs.db")
        auth = AuthStore(db)
        user_id = auth.register_user(
            email="authored-sanitary-queue@example.invalid",
            password="synthetic-password-123",
            name="Authored Sanitary Queue Regression",
        )["user"]["user_id"]
        store = ProjectStore(db)
        manual_fields = _supported_minimal_payload()
        manual_fields["lot"] = {"x": 0, "y": 0, "w": 600, "h": 400}
        manual_fields["site_plan"] = {"building_width": 30, "building_depth": 20, "parking_count": 4}
        manual_fields["ponds"] = [{"name": "BASIN-1", "x": 520, "y": 24, "w": 48, "d": 36}]
        manual_fields["survey_control"]["points"][1].update({"x": 600, "y": 400})
        manual_fields["disciplines"] = ["grading", "drainage", "storm", "sanitary", "water", "utility"]
        manual_fields["utility_network"] = [
            {
                "id": "QA-SANITARY-CORRIDOR-1",
                "canonical_id": "QA-SANITARY-CORRIDOR-1",
                "placement_id": "QA-SANITARY-CORRIDOR-1",
                "label": "Review sanitary corridor concept",
                "utility_type": "sanitary",
                "points": [[24.0, 42.0], [120.0, 42.0], [216.0, 18.0]],
                "source": "manual_drawn",
                "source_confidence": "user_drawn_review_required",
                "review_required": True,
                "construction_release_allowed": False,
            }
        ]
        project_id = "synthetic-authored-sanitary-resume"
        payload = {
            "project_id": project_id,
            "full_design_mode": False,
            "input_mode": "user",
            "strict_mode": False,
            "manual_fields": manual_fields,
            "allow_ai_fill_for_blanks": False,
            "meta": {
                "orchestrator_meta": {
                    "runtime_approved_stages": ["layout", "grading", "drainage", "storm_pipes"],
                    "runtime_resume": {
                        "project_id": project_id,
                        "stage_statuses": {
                            "layout": "complete",
                            "grading": "complete",
                            "drainage": "complete",
                            "storm_pipes": "complete",
                        },
                        "phase_checkpoints": {},
                        "final_plan": {
                            "project_name": "Synthetic authored sanitary checkpoint",
                            "actions": [],
                            "meta": {
                                "calculation_engine_revision": ENGINE_REVISION,
                                "stage_completeness": {
                                    "statuses": {
                                        "layout": "complete",
                                        "grading": "complete",
                                        "drainage": "complete",
                                        "storm_pipes": "complete",
                                    }
                                },
                            },
                        },
                        "source": "synthetic_exact_checkpoint",
                    },
                }
            },
        }
        store.save_project(
            user_id=user_id,
            project_id=project_id,
            name="Synthetic Authored Sanitary Resume",
            project_input=payload,
        )
        queue = JobQueueService(
            db,
            heartbeat_interval_sec=0.2,
            resume_poll_interval_sec=0.2,
            in_process_start_delay_sec=0.05,
        )
        try:
            runner = build_orchestrate_job_runner(
                project_store=store,
                update_job_progress=queue.update_job_progress,
                run_orchestration=lambda value, progress_callback=None: run_orchestration(
                    value,
                    load_orchestrator=_load_orchestrator,
                    assess_design_readiness=lambda *_args, **_kwargs: None,
                    progress_callback=progress_callback,
                ),
                build_run_summary=_summary,
                merge_project_metadata=lambda metadata, **_kwargs: metadata,
                final_plan_from_result=lambda result, **_kwargs: dict(result.get("final_plan") or {}),
            )
            queue.register_handler("orchestrate", runner)
            created = queue.submit_job(
                user_id=user_id,
                project_id=project_id,
                job_type="orchestrate",
                payload=payload,
            )

            sanitary = _wait_for_review(queue, user_id=user_id, job_id=created["job_id"])
            sanitary_checkpoint = sanitary["result"]["metadata"]["runtime_phase_checkpoint"]
            assert sanitary_checkpoint["stage_name"] == "sanitary"
            assert sanitary_checkpoint["message"] == "Sanitary stage accepted user-supplied sanitary geometry."
            assert sanitary["result"]["final_plan"]["meta"]["sanitary"]["source"] == "user_input"
            sanitary_acceptance_rows = [
                row
                for row in sanitary["result"]["final_plan"]["meta"]["stage_results"]
                if row.get("stage_name") == "sanitary"
                and row.get("message") == "Sanitary stage accepted user-supplied sanitary geometry."
            ]
            assert len(sanitary_acceptance_rows) == 1
            before_approval = sanitary["payload"]["meta"].get("orchestrator_meta", {}).get(
                "runtime_approved_stages", []
            )
            assert "sanitary" not in before_approval

            # Match the live Haggard chain: Storm was explicitly reviewed and
            # approved after a truthful no-inlet partial result. The Sanitary
            # hold itself is otherwise an authentic result from the real
            # planner/queue path above.
            partial_result = dict(sanitary["result"])
            partial_plan = dict(partial_result["final_plan"])
            partial_meta = dict(partial_plan["meta"])
            partial_completeness = dict(partial_meta["stage_completeness"])
            partial_statuses = dict(partial_completeness["statuses"])
            partial_statuses["storm_pipes"] = "partial"
            partial_completeness["statuses"] = partial_statuses
            partial_meta["stage_completeness"] = partial_completeness
            partial_plan["meta"] = partial_meta
            partial_result["final_plan"] = partial_plan
            queue._update_job_state(
                created["job_id"],
                status="awaiting_approval",
                result=partial_result,
                error=None,
            )

            monkeypatch.setenv("CIVORA_JOB_TRANSITION_DIAGNOSTIC_IDS", created["job_id"])
            monkeypatch.setenv("CIVORA_JOB_TRANSITION_DIAGNOSTIC_UNTIL_EPOCH", str(time.time() + 300))
            caplog.set_level(logging.INFO, logger="uvicorn.error")
            queue.continue_job(
                user_id=user_id,
                job_id=created["job_id"],
                expected_stage="sanitary",
            )
            approved = queue.get_job_detail(user_id=user_id, job_id=created["job_id"])
            approved_stages = approved["payload"]["meta"]["orchestrator_meta"]["runtime_approved_stages"]
            assert approved_stages.count("sanitary") == 1

            next_held = _wait_for_review(queue, user_id=user_id, job_id=created["job_id"])
            next_stage = next_held["result"]["metadata"]["runtime_phase_checkpoint"]["stage_name"]
            assert next_stage == "utility_network", {
                "approved": next_held["payload"]["meta"]["orchestrator_meta"].get(
                    "runtime_approved_stages"
                ),
                "next_stage": next_stage,
            }
            assert (
                next_held["result"]["final_plan"]["meta"]["stage_completeness"]["statuses"][
                    "storm_pipes"
                ]
                == "partial"
            )
            sanitary_rows = [
                row
                for row in next_held["result"]["final_plan"]["meta"]["stage_results"]
                if row.get("stage_name") == "sanitary"
            ]
            resumed_rows = [row for row in sanitary_rows if row.get("meta", {}).get("resumed_from_checkpoint")]
            assert len(resumed_rows) == 1
            assert resumed_rows[0]["meta"].get("approved_checkpoint") is True
            transition_events = [
                json.loads(record.getMessage().split("JOB_LIFECYCLE ", 1)[1])
                for record in caplog.records
                if "JOB_LIFECYCLE " in record.getMessage()
            ]
            assert [event["reason_category"] for event in transition_events] == [
                "approval_queued",
                "queue_claimed",
                "advanced",
            ]
            assert transition_events[0]["prior_stage"] == "sanitary"
            assert transition_events[0]["approved_stage"] == "sanitary"
            assert transition_events[0]["next_stage"] == "utility_network"
            assert transition_events[1]["next_stage"] == "utility_network"
            assert transition_events[2]["next_stage"] == "utility_network"
            assert [event["checkpoint_cause"] for event in transition_events] == [
                "atomic_approval_accepted",
                "queue_claim_after_approval",
                "advanced_to_next_stage",
            ]
            assert all(event["attempt"] == 1 for event in transition_events)
            diagnostic_text = " ".join(record.getMessage() for record in caplog.records)
            for forbidden in (
                "authored-sanitary-queue@example.invalid",
                "QA-SANITARY-CORRIDOR-1",
                "Review sanitary corridor concept",
                "120.0",
                "synthetic-password-123",
            ):
                assert forbidden not in diagnostic_text
        finally:
            queue.shutdown()


def test_asgi_continue_advances_authored_sanitary_through_one_real_consumer(monkeypatch, caplog):
    """Exercise the production HTTP acknowledgement and one queue consumer together."""
    api = importlib.import_module("backend.api.app")
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(Path(tmpdir) / "jobs.db")
        auth = AuthStore(db)
        registration = auth.register_user(
            email="asgi-sanitary-queue@example.invalid",
            password="synthetic-password-123",
            name="ASGI Sanitary Queue Regression",
        )
        user_id = registration["user"]["user_id"]
        headers = {"Authorization": f"Bearer {registration['token']}"}
        store = ProjectStore(db)
        manual_fields = _supported_minimal_payload()
        manual_fields["lot"] = {"x": 0, "y": 0, "w": 600, "h": 400}
        manual_fields["site_plan"] = {
            "building_width": 30,
            "building_depth": 20,
            "parking_count": 4,
        }
        manual_fields["ponds"] = [{"name": "BASIN-1", "x": 520, "y": 24, "w": 48, "d": 36}]
        manual_fields["survey_control"]["points"][1].update({"x": 600, "y": 400})
        manual_fields["disciplines"] = [
            "grading",
            "drainage",
            "storm",
            "sanitary",
            "water",
            "utility",
        ]
        manual_fields["utility_network"] = [
            {
                "id": "QA-SANITARY-CORRIDOR-1",
                "canonical_id": "QA-SANITARY-CORRIDOR-1",
                "placement_id": "QA-SANITARY-CORRIDOR-1",
                "label": "Review sanitary corridor concept",
                "utility_type": "sanitary",
                "points": [[24.0, 42.0], [120.0, 42.0], [216.0, 18.0]],
                "source": "manual_drawn",
                "source_confidence": "user_drawn_review_required",
                "review_required": True,
                "construction_release_allowed": False,
            }
        ]
        project_id = "project_synthetic_asgi_sanitary_resume"
        trace_start = time.time() - 1
        trace_until = time.time() + 300
        monkeypatch.setenv("CIVORA_PROJECT_TRANSITION_DIAGNOSTIC_ID", project_id)
        monkeypatch.setenv("CIVORA_PROJECT_TRANSITION_DIAGNOSTIC_START_EPOCH", str(trace_start))
        monkeypatch.setenv("CIVORA_JOB_TRANSITION_DIAGNOSTIC_UNTIL_EPOCH", str(trace_until))
        caplog.set_level(logging.INFO, logger="uvicorn.error")
        store.save_project(
            user_id=user_id,
            project_id=project_id,
            name="Synthetic ASGI Sanitary Resume",
            project_input=manual_fields,
        )
        queue = JobQueueService(
            db,
            worker_count=1,
            heartbeat_interval_sec=0.2,
            resume_poll_interval_sec=0.2,
            in_process_start_delay_sec=0.05,
        )
        runner = build_orchestrate_job_runner(
            project_store=store,
            update_job_progress=queue.update_job_progress,
            run_orchestration=lambda value, progress_callback=None: run_orchestration(
                value,
                load_orchestrator=_load_orchestrator,
                assess_design_readiness=lambda *_args, **_kwargs: None,
                progress_callback=progress_callback,
            ),
            build_run_summary=_summary,
            merge_project_metadata=lambda metadata, **_kwargs: metadata,
            final_plan_from_result=lambda result, **_kwargs: dict(result.get("final_plan") or {}),
        )
        queue.register_handler("orchestrate", runner)
        monkeypatch.setattr(api, "AUTH_STORE", auth)
        monkeypatch.setattr(api, "PROJECT_STORE", store)
        monkeypatch.setattr(api, "JOB_QUEUE", queue)
        monkeypatch.setattr(api, "RATE_LIMIT_STORE", RateLimitStore(db))
        client = TestClient(api.app)
        try:
            created_response = client.post(
                "/api/jobs/orchestrate",
                headers=headers,
                json={"project_id": project_id, "request": manual_fields},
            )
            assert created_response.status_code == 200, created_response.text
            job_id = created_response.json()["job"]["job_id"]

            for expected in ("layout", "grading", "drainage", "storm_pipes", "sanitary"):
                held = _wait_for_review(queue, user_id=user_id, job_id=job_id)
                assert held["result"]["metadata"]["runtime_phase_checkpoint"]["stage_name"] == expected
                continued = client.post(
                    f"/api/jobs/{job_id}/continue",
                    headers=headers,
                    json={"expected_stage": expected},
                )
                assert continued.status_code == 200, continued.text
                assert continued.json()["job"]["status"] == "queued"

            next_held = _wait_for_review(queue, user_id=user_id, job_id=job_id)
            assert next_held["result"]["metadata"]["runtime_phase_checkpoint"]["stage_name"] == "utility_network"
            assert next_held["payload"]["meta"]["orchestrator_meta"]["runtime_approved_stages"].count(
                "sanitary"
            ) == 1
            events = [
                json.loads(record.getMessage().split("JOB_LIFECYCLE ", 1)[1])
                for record in caplog.records
                if "JOB_LIFECYCLE " in record.getMessage()
            ]
            assert events[0]["event"] == "job_admitted"
            assert events[0]["checkpoint_cause"] == "first_project_job_admitted"
            assert {event["correlation_id"] for event in events} == {job_id}
            sanitary_continue = [
                event
                for event in events
                if event["event"] == "continue_accepted" and event["approved_stage"] == "sanitary"
            ]
            assert len(sanitary_continue) == 1
            sanitary_claim = [
                event
                for event in events
                if event["event"] == "queue_claimed" and event["approved_stage"] == "sanitary"
            ]
            assert len(sanitary_claim) == 1
            assert sanitary_claim[0]["checkpoint_cause"] == "queue_claim_after_approval"
            assert any(
                event["event"] == "checkpoint_returned"
                and event["prior_stage"] == "sanitary"
                and event["next_stage"] == "utility_network"
                and event["checkpoint_cause"] == "advanced_to_next_stage"
                for event in events
            )
            diagnostic_text = " ".join(record.getMessage() for record in caplog.records)
            for forbidden in (
                project_id,
                "asgi-sanitary-queue@example.invalid",
                "QA-SANITARY-CORRIDOR-1",
                "Review sanitary corridor concept",
                "synthetic-password-123",
            ):
                assert forbidden not in diagnostic_text
        finally:
            queue.shutdown()
