import json
import tempfile
import time
from pathlib import Path

from backend.application.design_workflows import run_orchestration
from backend.application.job_workflows import build_orchestrate_job_runner
from backend.services.auth_store import AuthStore
from backend.services.canonical_results import ENGINE_REVISION
from backend.services.canonical_results import bind_canvas_result
from backend.services.canonical_results import canvas_result_freshness
from backend.services.canonical_canvas import with_canvas_snapshot
from backend.services.canonical_project import PROJECT_DOCUMENT_KEY
from backend.services.database import Database
from backend.services.job_queue import JobQueueService
from backend.services.project_store import ProjectStore
from backend.services.project_revision import project_revision
from tests.test_engineering_generation_workflows import _supported_minimal_payload


def _load_orchestrator():
    from backend.planning.orchestrator import PlannerOrchestratorRequest, orchestrate_plan

    return PlannerOrchestratorRequest, orchestrate_plan


def _wait_for_stage(queue, *, user_id, job_id, stage, timeout=20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        detail = queue.get_job_detail(user_id=user_id, job_id=job_id)
        if detail and detail["status"] == "awaiting_approval":
            checkpoint = dict(dict(detail.get("result") or {}).get("metadata") or {}).get(
                "runtime_phase_checkpoint", {}
            )
            if checkpoint.get("stage_name") == stage:
                return detail
        if detail and detail["status"] in {"failed", "cancelled", "completed"}:
            raise AssertionError(f"job reached {detail['status']} before {stage}")
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {stage}")


def _wait_for_review(queue, *, user_id, job_id, timeout=20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        detail = queue.get_job_detail(user_id=user_id, job_id=job_id)
        if detail and detail["status"] == "awaiting_approval":
            return detail
        if detail and detail["status"] in {"failed", "cancelled", "completed"}:
            raise AssertionError(f"job reached {detail['status']} before review")
        time.sleep(0.05)
    raise AssertionError("timed out waiting for review")


def _summary(result, **kwargs):
    final_meta = dict(dict(result.get("final_plan") or {}).get("meta") or {})
    return {
        "run_id": "synthetic_project_fallback_resume",
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


def _payload(project_id):
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
        "grading", "drainage", "storm", "sanitary", "water", "utility"
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
    manual_fields.setdefault("site_objects", [])
    return {
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


def _runner(store, queue):
    return build_orchestrate_job_runner(
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


def test_project_fallback_consumes_persisted_sanitary_approval_after_restart():
    """A missing job detail can safely recover the same revision-bound project checkpoint."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(Path(tmpdir) / "jobs.db")
        auth = AuthStore(db)
        user_id = auth.register_user(
            email="fallback-sanitary@example.invalid",
            password="synthetic-password-123",
            name="Synthetic Fallback",
        )["user"]["user_id"]
        store = ProjectStore(db)
        project_id = "synthetic-project-fallback"
        payload = with_canvas_snapshot(_payload(project_id))
        store.save_project(
            user_id=user_id,
            project_id=project_id,
            name="Synthetic Project Fallback",
            project_input=payload,
        )

        queue = JobQueueService(db, heartbeat_interval_sec=0.2, resume_poll_interval_sec=0.2)
        queue.register_handler("orchestrate", _runner(store, queue))
        created = queue.submit_job(
            user_id=user_id,
            project_id=project_id,
            job_type="orchestrate",
            payload=payload,
        )
        sanitary = _wait_for_stage(
            queue, user_id=user_id, job_id=created["job_id"], stage="sanitary"
        )
        queue.shutdown()

        project = store.get_project(user_id=user_id, project_id=project_id)
        store.save_project(
            user_id=user_id,
            project_id=project_id,
            name=project["name"],
            project_input=project["project_input"],
            latest_result=sanitary["result"],
            expected_revision=project_revision(project),
        )

        paused = JobQueueService(db, worker_count=0, resume_poll_interval_sec=0)
        paused.continue_job(
            user_id=user_id,
            job_id=created["job_id"],
            expected_stage="sanitary",
        )
        # Simulate an old/incomplete queue detail while retaining the exact
        # immutable checkpoint in the project fallback record.
        connection = db.connect()
        try:
            connection.execute(
                "UPDATE jobs SET result_json = ? WHERE job_id = ?",
                (json.dumps({"job_progress": {"stage": "Queued Next Phase", "progress": 64}}), created["job_id"]),
            )
            connection.commit()
        finally:
            connection.close()
        paused.shutdown()

        resumed = JobQueueService(
            db,
            heartbeat_interval_sec=0.2,
            resume_poll_interval_sec=0.05,
            in_process_start_delay_sec=0.01,
        )
        try:
            resumed.register_handler("orchestrate", _runner(store, resumed))
            utility = _wait_for_stage(
                resumed, user_id=user_id, job_id=created["job_id"], stage="utility_network"
            )
            approvals = utility["payload"]["meta"]["orchestrator_meta"]["runtime_approved_stages"]
            assert approvals.count("sanitary") == 1
            resumed_rows = [
                row
                for row in utility["result"]["final_plan"]["meta"]["stage_results"]
                if row.get("stage_name") == "sanitary"
                and row.get("meta", {}).get("resumed_from_checkpoint")
            ]
            assert len(resumed_rows) == 1
            assert resumed_rows[0]["meta"].get("approved_checkpoint") is True
        finally:
            resumed.shutdown()


def test_stale_embedded_resume_cannot_consume_prior_sanitary_approval():
    """A stale project checkpoint must not survive via payload runtime_resume."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(Path(tmpdir) / "jobs.db")
        auth = AuthStore(db)
        user_id = auth.register_user(
            email="stale-sanitary@example.invalid",
            password="synthetic-password-123",
            name="Synthetic Stale Resume",
        )["user"]["user_id"]
        store = ProjectStore(db)
        project_id = "synthetic-stale-resume"
        payload = with_canvas_snapshot(_payload(project_id))
        store.save_project(
            user_id=user_id,
            project_id=project_id,
            name="Synthetic Stale Resume",
            project_input=payload,
        )
        first_queue = JobQueueService(db, heartbeat_interval_sec=0.2, resume_poll_interval_sec=0.2)
        first_queue.register_handler("orchestrate", _runner(store, first_queue))
        created = first_queue.submit_job(
            user_id=user_id,
            project_id=project_id,
            job_type="orchestrate",
            payload=payload,
        )
        sanitary = _wait_for_stage(
            first_queue, user_id=user_id, job_id=created["job_id"], stage="sanitary"
        )
        first_queue.cancel_job(user_id=user_id, job_id=created["job_id"])
        first_queue.shutdown()

        stale_payload = json.loads(json.dumps(payload))
        stale_payload["meta"] = json.loads(json.dumps(sanitary["payload"]["meta"]))
        old_result = bind_canvas_result(
            json.loads(json.dumps(sanitary["result"])), payload, calculation_executed=True
        )
        old_meta = old_result["final_plan"]["meta"]
        old_resume = {
            "project_id": project_id,
            "stage_statuses": dict(old_meta["stage_completeness"]["statuses"]),
            "phase_checkpoints": dict(old_meta.get("phase_checkpoints") or {}),
            "final_plan": old_result["final_plan"],
            "source": "stale_payload_checkpoint",
        }
        orchestrator_meta = stale_payload["meta"]["orchestrator_meta"]
        orchestrator_meta["runtime_resume"] = old_resume
        orchestrator_meta["runtime_approved_stages"] = [
            "layout", "grading", "drainage", "storm_pipes", "sanitary"
        ]
        stale_payload[PROJECT_DOCUMENT_KEY]["extensions"]["canvas_workspace_v1"][
            "manual_fields"
        ]["site_plan"]["building_width"] = 31
        assert canvas_result_freshness(
            old_result, stale_payload, require_engine_revision=False
        )["status"] == "stale"

        project = store.get_project(user_id=user_id, project_id=project_id)
        store.save_project(
            user_id=user_id,
            project_id=project_id,
            name=project["name"],
            project_input=stale_payload,
            latest_result=old_result,
            expected_revision=project_revision(project),
        )
        saved = store.get_project(user_id=user_id, project_id=project_id)
        assert canvas_result_freshness(
            saved["latest_result"], saved["project_input"], require_engine_revision=False
        )["status"] == "stale"

        resumed = JobQueueService(
            db,
            heartbeat_interval_sec=0.2,
            resume_poll_interval_sec=0.05,
            in_process_start_delay_sec=0.01,
        )
        try:
            resumed.register_handler("orchestrate", _runner(store, resumed))
            restarted = resumed.submit_job(
                user_id=user_id,
                project_id=project_id,
                job_type="orchestrate",
                payload=stale_payload,
            )
            detail = _wait_for_review(
                resumed, user_id=user_id, job_id=restarted["job_id"]
            )
            checkpoint = detail["result"]["metadata"]["runtime_phase_checkpoint"]
            assert checkpoint["stage_name"] == "layout"
            approvals = detail["payload"]["meta"]["orchestrator_meta"].get(
                "runtime_approved_stages", []
            )
            assert "sanitary" not in approvals
        finally:
            resumed.shutdown()
