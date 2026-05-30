import unittest

from fastapi import HTTPException

from backend.application.job_workflows import (
    build_orchestrate_job_runner,
    cancel_existing_job,
    revise_existing_job,
    queue_orchestrate_job,
)


class FakeProjectStore:
    def __init__(self, project=None):
        self.project = project
        self.saved_payload = None
        self.save_calls = []
        self.latest_result_override = None

    def get_project(self, *, user_id: str, project_id: str):
        if self.project and user_id == self.project.get("user_id") and project_id == self.project.get("project_id"):
            return dict(self.project)
        return None

    def get_project_latest_result(self, *, user_id: str, project_id: str):
        if self.project and user_id == self.project.get("user_id") and project_id == self.project.get("project_id"):
            if self.latest_result_override is not None:
                return dict(self.latest_result_override)
            return dict(self.project.get("latest_result") or {})
        return None

    def save_project(self, **kwargs):
        self.saved_payload = dict(kwargs)
        self.save_calls.append(dict(kwargs))
        self.project = {
            "user_id": kwargs["user_id"],
            "project_id": kwargs["project_id"],
            "name": kwargs["name"],
            "description": kwargs["description"],
            "session_id": kwargs["session_id"],
            "tags": kwargs["tags"],
            "project_input": kwargs["project_input"],
            "latest_result": kwargs["latest_result"],
            "session_state": kwargs["session_state"],
            "metadata": kwargs["metadata"],
        }
        return dict(self.project)


class FakeJobQueue:
    def __init__(self):
        self.submitted = None
        self.registered = {}
        self.progress_updates = []
        self.cancelled = None
        self.continued = None
        self.revised = None
        self.jobs = {}

    def submit_job(self, *, user_id, job_type, payload, project_id=None):
        self.submitted = {
            "user_id": user_id,
            "job_type": job_type,
            "payload": dict(payload),
            "project_id": project_id,
        }
        job = {"job_id": "job_1", "status": "queued", "project_id": project_id, "job_type": job_type, "payload": dict(payload), "result": {}}
        self.jobs[job["job_id"]] = dict(job)
        return job

    def register_handler(self, job_type, runner):
        self.registered[job_type] = runner

    def update_job_progress(self, job_id, *, stage, detail, progress):
        self.progress_updates.append(
            {
                "job_id": job_id,
                "stage": stage,
                "detail": detail,
                "progress": progress,
            }
        )

    def cancel_job(self, *, user_id, job_id):
        self.cancelled = {"user_id": user_id, "job_id": job_id}
        if job_id == "missing":
            return None
        return {"job_id": job_id, "status": "cancelled", "project_id": "p1", "job_type": "orchestrate"}

    def continue_job(self, *, user_id, job_id):
        self.continued = {"user_id": user_id, "job_id": job_id}
        if job_id == "missing":
            return None
        job = dict(self.jobs.get(job_id) or {"job_id": job_id, "project_id": "p1", "job_type": "orchestrate"})
        job["status"] = "queued"
        self.jobs[job_id] = dict(job)
        return job

    def revise_job(self, *, user_id, job_id, payload=None):
        self.revised = {"user_id": user_id, "job_id": job_id, "payload": dict(payload or {})}
        if job_id == "missing":
            return None
        job = dict(self.jobs.get(job_id) or {"job_id": job_id, "project_id": "p1", "job_type": "orchestrate"})
        job["status"] = "queued"
        job["payload"] = dict(payload or {})
        self.jobs[job_id] = dict(job)
        return job

    def get_job_detail(self, *, user_id, job_id):
        if job_id == "missing":
            return None
        return dict(self.jobs.get(job_id) or {})


class ApplicationJobWorkflowsTest(unittest.TestCase):
    def test_queue_orchestrate_job_validates_project(self):
        with self.assertRaises(HTTPException) as ctx:
            queue_orchestrate_job(
                project_store=FakeProjectStore(),
                job_queue=FakeJobQueue(),
                user_id="u1",
                project_id="missing",
                request_payload={"prompt_text": "hi"},
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_queue_orchestrate_job_submits(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Untitled Project",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {
                    "manual_fields": {
                        "disciplines": ["corridor", "grading", "drainage", "utility"],
                    }
                },
                "latest_result": {},
                "session_state": {},
                "metadata": {},
            }
        )
        queue = FakeJobQueue()
        response = queue_orchestrate_job(
            project_store=store,
            job_queue=queue,
            user_id="u1",
            project_id="p1",
            request_payload={
                "prompt_text": "run",
                "full_design_mode": True,
                "manual_fields": {
                    "building_width": 110,
                    "building_depth": 58,
                    "disciplines": ["corridor", "grading", "drainage", "utility"],
                },
            },
        )
        self.assertTrue(response["success"])
        self.assertEqual(queue.submitted["job_type"], "orchestrate")
        self.assertEqual(response["operational_summary"]["status"], "queued")
        self.assertTrue(response["operational_summary"]["project_bound"])
        self.assertEqual(response["operational_summary"]["job_id"], "job_1")
        self.assertEqual(store.saved_payload["project_input"]["prompt_text"], "run")
        self.assertTrue(store.saved_payload["project_input"]["full_design_mode"])
        self.assertEqual(
            store.saved_payload["project_input"]["request_payload"]["prompt_text"],
            "run",
        )
        self.assertEqual(
            store.saved_payload["project_input"]["manual_fields"]["building_width"],
            110,
        )

    def test_revise_existing_job_requeues_current_phase_with_saved_project_input(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {
                    "prompt_text": "move the basin south and widen access",
                    "manual_fields": {"project_name": "Demo"},
                    "meta": {"chat_thread": [{"role": "user", "content": "adjust grading"}]},
                },
                "latest_result": {
                    "final_plan": {
                        "project_name": "Demo",
                        "release_ready": True,
                        "export_ready": True,
                        "release_status": "ready",
                        "meta": {
                            "runtime_phase_checkpoint": {
                                "stage_name": "grading",
                                "status": "complete",
                                "message": "Grading checkpoint saved.",
                                "yielded": True,
                            },
                            "stage_completeness": {
                                "statuses": {
                                    "layout": "complete",
                                    "grading": "complete",
                                    "drainage": "pending",
                                }
                            },
                            "phase_checkpoints": {
                                "layout": {"status": "complete", "ready": True},
                                "grading": {"status": "complete", "ready": True},
                                "drainage_storm": {"status": "pending", "ready": False},
                                "utilities": {"status": "pending", "ready": False},
                                "coordination_validation": {"status": "pending", "ready": False},
                                "combined_view": {"status": "ready", "ready": True, "completed_phase_count": 2, "total_phase_count": 5},
                            },
                            "release_review": {"release_status": "ready"},
                        },
                    },
                    "metadata": {
                        "runtime_phase_checkpoint": {
                            "stage_name": "grading",
                            "status": "complete",
                            "message": "Grading checkpoint saved.",
                            "yielded": True,
                        },
                        "run_summary": {
                            "phase_checkpoints": {
                                "layout": {"status": "complete", "ready": True},
                                "grading": {"status": "complete", "ready": True},
                                "drainage_storm": {"status": "pending", "ready": False},
                                "utilities": {"status": "pending", "ready": False},
                                "coordination_validation": {"status": "pending", "ready": False},
                                "combined_view": {"status": "ready", "ready": True, "completed_phase_count": 2, "total_phase_count": 5},
                            },
                            "reliability_summary": {"release_ready": True, "operational_state": "ready"},
                        },
                    },
                },
                "session_state": {},
                "metadata": {},
            }
        )
        queue = FakeJobQueue()
        queue.jobs["job_await"] = {
            "job_id": "job_await",
            "status": "awaiting_approval",
            "project_id": "p1",
            "job_type": "orchestrate",
            "payload": {"prompt_text": "old prompt"},
            "result": {
                "metadata": {
                    "runtime_phase_checkpoint": {
                        "stage_name": "grading",
                        "message": "Grading checkpoint saved.",
                        "yielded": True,
                    }
                }
            },
        }

        response = revise_existing_job(
            project_store=store,
            job_queue=queue,
            user_id="u1",
            job_id="job_await",
        )

        self.assertTrue(response["success"])
        self.assertEqual(response["job"]["status"], "queued")
        self.assertEqual(queue.revised["payload"]["prompt_text"], "move the basin south and widen access")
        saved_final_plan = store.saved_payload["latest_result"]["final_plan"]
        self.assertFalse(saved_final_plan["release_ready"])
        self.assertFalse(saved_final_plan["export_ready"])
        self.assertEqual(saved_final_plan["meta"]["stage_completeness"]["statuses"]["grading"], "pending")
        self.assertEqual(saved_final_plan["meta"]["phase_checkpoints"]["grading"]["status"], "pending")
        self.assertFalse(saved_final_plan["meta"]["phase_checkpoints"]["grading"]["ready"])
        self.assertEqual(saved_final_plan["meta"]["phase_checkpoints"]["combined_view"]["status"], "pending")

    def test_build_orchestrate_job_runner_updates_project(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {},
                "latest_result": {},
                "session_state": {},
                "metadata": {},
            }
        )
        def plan_builder(result, **kwargs):
            if kwargs.get("enforce_export_guards"):
                return result["final_plan"]
            return result["final_plan"]

        progress_updates = []
        runner = build_orchestrate_job_runner(
            project_store=store,
            update_job_progress=lambda job_id, **kwargs: progress_updates.append({"job_id": job_id, **kwargs}),
            run_orchestration=lambda payload: {
                "success": True,
                "final_plan": {
                    "project_name": "Demo",
                    "meta": {
                        "drainage": {"export_validation": {"ready": False, "reasons": ["storm_network_missing"]}},
                        "storm_pipes": {"storm_pipe_segments": [{"id": "sp-1"}]},
                    },
                },
                "assumptions": [
                    {
                        "field_name": "plan",
                        "assumed_value": "Planner executed model-first workflow with ProjectManager as active lifecycle state.",
                        "reason": "Planner execution assumption",
                    }
                ],
            },
            build_run_summary=lambda result, **kwargs: {
                "run_id": "run_1",
                "job_id": kwargs.get("job_id"),
                "convergence_summary": {
                    "assumption_summary": {
                        "count": 1,
                        "categories": ["design_defaults"],
                        "examples": ["Where widths are not explicit for linear features, discipline defaults are used."],
                    },
                    "unresolved_issue_categories": ["drainage", "coordination"],
                    "blocked_reasons": ["primary_detention_missing"],
                    "blocked_exports": ["dxf"],
                },
                "reliability_summary": {
                    "operational_state": "review",
                    "primary_attention": "primary_detention_missing",
                },
                "phase_checkpoints": {
                    "layout": {"status": "complete", "ready": True},
                    "grading": {"status": "partial", "ready": False},
                    "combined_view": {"status": "review", "ready": False},
                },
            },
            merge_project_metadata=lambda metadata, **kwargs: {"workflow": {"runs": [kwargs["run_summary"]]}},
            final_plan_from_result=plan_builder,
        )
        result = runner(
            {
                "job_id": "job_1",
                "job_type": "orchestrate",
                "user_id": "u1",
                "project_id": "p1",
                "payload": {"prompt_text": "run"},
            }
        )
        self.assertTrue(result["success"])
        self.assertEqual(
            result["assumptions"][0]["assumed_value"],
            "Where widths are not explicit for linear features, discipline defaults are used.",
        )
        self.assertEqual(result["review_categories"], ["drainage", "coordination"])
        self.assertNotIn("blocked", result)
        self.assertEqual(result["metadata"]["run_summary"]["run_id"], "run_1")
        self.assertTrue(result["final_plan"]["export_ready"])
        self.assertTrue(result["final_plan"]["release_ready"])
        self.assertEqual(result["final_plan"]["release_status"], "ready")
        self.assertEqual(result["final_plan"]["blockers"], [])
        self.assertEqual(result["final_plan"]["deliverables"]["ready"], [])
        self.assertEqual(result["final_plan"]["meta"]["phase_checkpoints"]["layout"]["status"], "complete")
        self.assertTrue(result["final_plan"]["meta"]["phase_checkpoints"]["combined_view"]["ready"])
        self.assertEqual(result["final_plan"]["meta"]["phase_checkpoints"]["combined_view"]["completed_phase_count"], 2)
        self.assertEqual(result["metadata"]["job_context"]["job_id"], "job_1")
        self.assertEqual(result["metadata"]["job_context"]["source"], "job_queue")
        self.assertEqual(result["metadata"]["job_context"]["user_id"], "u1")
        self.assertEqual(store.saved_payload["metadata"]["workflow"]["runs"][0]["job_id"], "job_1")
        self.assertEqual(
            store.saved_payload["latest_result"]["assumptions"][0]["assumed_value"],
            "Where widths are not explicit for linear features, discipline defaults are used.",
        )
        self.assertEqual(store.saved_payload["latest_result"]["final_plan"]["blockers"], [])
        self.assertEqual(
            store.saved_payload["latest_result"]["final_plan"]["meta"]["release_review"]["phase_checkpoints"]["layout"]["status"],
            "complete",
        )
        self.assertEqual(
            store.saved_payload["latest_result"]["final_plan"]["meta"]["release_review"]["release_status"],
            "ready",
        )
        self.assertEqual(
            [item["stage"] for item in progress_updates],
            ["Engineering Run", "Saving Project", "Finalizing"],
        )

    def test_build_orchestrate_job_runner_marks_fully_completed_checkpoint_release_ready(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {},
                "latest_result": {},
                "session_state": {},
                "metadata": {},
            }
        )

        def plan_builder(result, **kwargs):
            return {
                "project_name": "Demo",
                "actions": [{"layer": "BUILDING", "task": "rectangle", "x": 0, "y": 0, "w": 10, "h": 10}],
                "meta": dict(result.get("final_plan", {}).get("meta") or {}),
            }

        runner = build_orchestrate_job_runner(
            project_store=store,
            update_job_progress=lambda *args, **kwargs: None,
            run_orchestration=lambda payload: {
                "success": True,
                "final_plan": {
                    "project_name": "Demo",
                    "actions": [{"layer": "BUILDING", "task": "rectangle", "x": 0, "y": 0, "w": 10, "h": 10}],
                    "meta": {},
                },
                "metadata": {
                    "runtime_phase_checkpoint": {
                        "stage_name": "coordination_resolution",
                        "status": "complete",
                        "yielded": False,
                    }
                },
            },
            build_run_summary=lambda result, **kwargs: {
                "run_id": "run_complete",
                "job_id": kwargs.get("job_id"),
                "convergence_summary": {
                    "assumption_summary": {"count": 0, "categories": [], "examples": []},
                    "unresolved_issue_categories": [],
                    "blocked_reasons": [],
                    "blocked_exports": [],
                },
                "reliability_summary": {
                    "operational_state": "review",
                    "primary_attention": "",
                    "release_ready": False,
                },
                "phase_checkpoints": {
                    "layout": {"status": "complete", "ready": True},
                    "grading": {"status": "complete", "ready": True},
                    "drainage_storm": {"status": "complete", "ready": True},
                    "utilities": {"status": "complete", "ready": True},
                    "coordination_validation": {"status": "complete", "ready": True},
                    "combined_view": {
                        "status": "review",
                        "ready": False,
                        "completed_phase_count": 5,
                        "total_phase_count": 5,
                    },
                },
                "requested_deliverables": [],
                "produced_deliverables": [],
                "failed_deliverables": [],
                "ready_deliverables": [],
                "extra_deliverables": [],
            },
            merge_project_metadata=lambda metadata, **kwargs: {"workflow": {"runs": [kwargs["run_summary"]]}},
            final_plan_from_result=plan_builder,
        )

        result = runner(
            {
                "job_id": "job_complete",
                "job_type": "orchestrate",
                "user_id": "u1",
                "project_id": "p1",
                "payload": {"prompt_text": "run"},
            }
        )

        self.assertTrue(result["final_plan"]["release_ready"])
        self.assertEqual(result["final_plan"]["release_status"], "ready")
        self.assertTrue(result["final_plan"]["meta"]["phase_checkpoints"]["combined_view"]["ready"])
        self.assertEqual(
            result["final_plan"]["meta"]["phase_checkpoints"]["combined_view"]["completed_phase_count"],
            5,
        )
        self.assertEqual(
            store.saved_payload["latest_result"]["final_plan"]["meta"]["release_review"]["release_status"],
            "ready",
        )

    def test_build_orchestrate_job_runner_blocks_construction_release_without_readiness(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {},
                "latest_result": {},
                "session_state": {},
                "metadata": {},
            }
        )

        def plan_builder(result, **kwargs):
            return {
                "project_name": "Demo",
                "actions": [{"layer": "BUILDING", "task": "rectangle", "x": 0, "y": 0, "w": 10, "h": 10}],
                "meta": dict(result.get("final_plan", {}).get("meta") or {}),
            }

        runner = build_orchestrate_job_runner(
            project_store=store,
            update_job_progress=lambda *args, **kwargs: None,
            run_orchestration=lambda payload: {
                "success": True,
                "final_plan": {
                    "project_name": "Demo",
                    "actions": [{"layer": "BUILDING", "task": "rectangle", "x": 0, "y": 0, "w": 10, "h": 10}],
                    "meta": {"construction_release_required": True},
                },
                "metadata": {
                    "runtime_phase_checkpoint": {
                        "stage_name": "coordination_resolution",
                        "status": "complete",
                        "yielded": False,
                    }
                },
            },
            build_run_summary=lambda result, **kwargs: {
                "run_id": "run_complete",
                "job_id": kwargs.get("job_id"),
                "convergence_summary": {
                    "assumption_summary": {"count": 0, "categories": [], "examples": []},
                    "unresolved_issue_categories": [],
                    "blocked_reasons": [],
                    "blocked_exports": [],
                },
                "reliability_summary": {
                    "operational_state": "review",
                    "primary_attention": "",
                    "release_ready": False,
                },
                "phase_checkpoints": {
                    "layout": {"status": "complete", "ready": True},
                    "grading": {"status": "complete", "ready": True},
                    "drainage_storm": {"status": "complete", "ready": True},
                    "utilities": {"status": "complete", "ready": True},
                    "coordination_validation": {"status": "complete", "ready": True},
                    "combined_view": {
                        "status": "review",
                        "ready": False,
                        "completed_phase_count": 5,
                        "total_phase_count": 5,
                    },
                },
                "requested_deliverables": [],
                "produced_deliverables": [],
                "failed_deliverables": [],
                "ready_deliverables": [],
                "extra_deliverables": [],
            },
            merge_project_metadata=lambda metadata, **kwargs: {"workflow": {"runs": [kwargs["run_summary"]]}},
            final_plan_from_result=plan_builder,
        )

        result = runner(
            {
                "job_id": "job_construction_missing",
                "job_type": "orchestrate",
                "user_id": "u1",
                "project_id": "p1",
                "payload": {"prompt_text": "run"},
            }
        )

        self.assertFalse(result["final_plan"]["release_ready"])
        self.assertEqual(result["final_plan"]["release_status"], "blocked")
        self.assertIn("construction_readiness_missing", result["final_plan"]["blockers"])
        self.assertFalse(result["final_plan"]["meta"]["phase_checkpoints"]["combined_view"]["ready"])
        self.assertEqual(
            store.saved_payload["latest_result"]["final_plan"]["meta"]["release_review"]["release_status"],
            "blocked",
        )

    def test_build_orchestrate_job_runner_preserves_current_export_guard_failures(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {},
                "latest_result": {},
                "session_state": {},
                "metadata": {},
            }
        )

        def plan_builder(result, **kwargs):
            if kwargs.get("enforce_export_guards"):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Export is blocked because the engineering design has not reached a stable "
                        "drainage/storm state yet: storm_network_missing, storm_graph_invalid"
                    ),
                )
            return {
                "project_name": "Demo",
                "meta": {
                    "drainage": {"export_validation": {"ready": False}},
                    "storm_pipes": {"storm_pipe_segments": [{"id": "sp-1"}]},
                },
            }

        runner = build_orchestrate_job_runner(
            project_store=store,
            update_job_progress=lambda *_args, **_kwargs: None,
            run_orchestration=lambda payload: {"success": True, "final_plan": {"project_name": "Demo", "meta": {}}},
            build_run_summary=lambda result, **kwargs: {
                "run_id": "run_2",
                "job_id": kwargs.get("job_id"),
                "convergence_summary": {
                    "assumption_summary": {"count": 0, "categories": [], "examples": []},
                    "unresolved_issue_categories": ["pipes"],
                    "blocked_reasons": ["primary_detention_missing"],
                    "blocked_exports": ["dxf"],
                },
                "reliability_summary": {
                    "operational_state": "review",
                    "primary_attention": "primary_detention_missing",
                },
            },
            merge_project_metadata=lambda metadata, **kwargs: metadata,
            final_plan_from_result=plan_builder,
        )
        result = runner(
            {
                "job_id": "job_2",
                "job_type": "orchestrate",
                "user_id": "u1",
                "project_id": "p1",
                "payload": {"prompt_text": "run"},
            }
        )
        self.assertEqual(result["blocked"], ["storm_network_missing", "storm_graph_invalid"])
        self.assertFalse(result["final_plan"]["export_ready"])
        self.assertEqual(result["final_plan"]["blockers"], ["storm_network_missing", "storm_graph_invalid"])

    def test_build_orchestrate_job_runner_reports_real_phase_progress(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {},
                "latest_result": {},
                "session_state": {},
                "metadata": {},
            }
        )
        progress_updates = []

        def run_orchestration(payload, progress_callback=None):
            self.assertIsNotNone(progress_callback)
            progress_callback("layout", "running", 18, "Running layout phase.")
            progress_callback("grading", "running", 30, "Running grading phase.")
            return {
                "success": True,
                "final_plan": {
                    "project_name": "Demo",
                    "meta": {
                        "grading": {"surface": "ok"},
                    },
                },
            }

        runner = build_orchestrate_job_runner(
            project_store=store,
            update_job_progress=lambda job_id, **kwargs: progress_updates.append({"job_id": job_id, **kwargs}),
            run_orchestration=run_orchestration,
            build_run_summary=lambda result, **kwargs: {
                "run_id": "run_phase",
                "job_id": kwargs.get("job_id"),
                "convergence_summary": {
                    "assumption_summary": {"count": 0, "categories": [], "examples": []},
                    "unresolved_issue_categories": [],
                    "blocked_reasons": [],
                    "blocked_exports": [],
                },
                "reliability_summary": {
                    "operational_state": "ready",
                    "release_ready": True,
                },
                "phase_checkpoints": {
                    "layout": {"status": "complete", "ready": True},
                    "grading": {"status": "complete", "ready": True},
                    "combined_view": {"status": "ready", "ready": True},
                },
                "requested_deliverables": ["site_plan"],
                "produced_deliverables": ["site_plan"],
                "ready_deliverables": ["site_plan"],
                "extra_deliverables": [],
                "failed_deliverables": [],
            },
            merge_project_metadata=lambda metadata, **kwargs: metadata,
            final_plan_from_result=lambda result, **kwargs: {
                "project_name": "Demo",
                "meta": {
                    "grading": {"surface": "ok"},
                },
            },
        )

        runner(
            {
                "job_id": "job_phase",
                "job_type": "orchestrate",
                "user_id": "u1",
                "project_id": "p1",
                "payload": {"prompt_text": "run"},
            }
        )

        self.assertEqual(
            [item["stage"] for item in progress_updates],
            [
                "Engineering Run",
                "Layout Phase",
                "Grading Phase",
                "Saving Project",
                "Finalizing",
            ],
        )
        self.assertEqual(progress_updates[1]["detail"], "Running layout phase.")
        self.assertEqual(progress_updates[2]["detail"], "Running grading phase.")

    def test_build_orchestrate_job_runner_passes_runtime_controls_through_orchestrator_meta(self):
        existing_final_plan = {
            "project_name": "Demo",
            "meta": {
                "stage_completeness": {"statuses": {"layout": "complete"}},
                "phase_checkpoints": {
                    "layout": {"status": "complete", "ready": True},
                    "grading": {"status": "pending", "ready": False},
                },
            },
        }
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {},
                "latest_result": {"final_plan": existing_final_plan, "metadata": {"run_summary": {"phase_checkpoints": existing_final_plan["meta"]["phase_checkpoints"]}}},
                "session_state": {},
                "metadata": {},
            }
        )
        seen_meta = {}

        def run_orchestration(payload, progress_callback=None):
            nonlocal seen_meta
            seen_meta = dict(payload.get("meta") or {})
            return {
                "success": True,
                "final_plan": existing_final_plan,
                "metadata": {
                    "runtime_should_continue": True,
                    "runtime_phase_checkpoint": {
                        "stage_name": "grading",
                        "status": "complete",
                        "message": "Grading checkpoint saved.",
                    },
                },
            }

        runner = build_orchestrate_job_runner(
            project_store=store,
            update_job_progress=lambda *_args, **_kwargs: None,
            run_orchestration=run_orchestration,
            build_run_summary=lambda result, **kwargs: {
                "run_id": "run_resume",
                "job_id": kwargs.get("job_id"),
                "source": "queued_job",
                "convergence_summary": {
                    "assumption_summary": {"count": 0, "categories": [], "examples": []},
                    "unresolved_issue_categories": [],
                    "blocked_reasons": [],
                    "blocked_exports": [],
                },
                "reliability_summary": {
                    "operational_state": "review",
                    "release_ready": False,
                },
                "phase_checkpoints": {
                    "layout": {"status": "complete", "ready": True},
                    "grading": {"status": "pending", "ready": False},
                    "combined_view": {"status": "review", "ready": False},
                },
                "requested_deliverables": [],
                "produced_deliverables": [],
                "ready_deliverables": [],
                "extra_deliverables": [],
                "failed_deliverables": [],
            },
            merge_project_metadata=lambda metadata, **kwargs: metadata,
            final_plan_from_result=lambda result, **kwargs: existing_final_plan,
        )

        result = runner(
            {
                "job_id": "job_resume",
                "job_type": "orchestrate",
                "user_id": "u1",
                "project_id": "p1",
                "payload": {"prompt_text": "run"},
            }
        )

        self.assertTrue(result["metadata"]["runtime_should_continue"])
        orchestrator_meta = dict(seen_meta.get("orchestrator_meta") or {})
        self.assertEqual(orchestrator_meta.get("runtime_phase_batch_limit"), 1)
        self.assertEqual(
            dict(orchestrator_meta.get("runtime_resume") or {}).get("stage_statuses"),
            {"layout": "complete"},
        )

    def test_build_orchestrate_job_runner_restores_runtime_continue_from_final_plan_checkpoint(self):
        yielded_final_plan = {
            "project_name": "Demo",
            "actions": [{"layer": "BUILDING", "kind": "rectangle", "x": 0, "y": 0, "w": 10, "h": 10}],
            "meta": {
                "runtime_phase_checkpoint": {
                    "stage_name": "layout",
                    "status": "complete",
                    "message": "Layout stage completed.",
                    "yielded": True,
                },
            },
        }
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {},
                "latest_result": {},
                "session_state": {},
                "metadata": {},
            }
        )

        def run_orchestration(payload, progress_callback=None):
            return {
                "success": True,
                "final_plan": yielded_final_plan,
                "metadata": {},
            }

        runner = build_orchestrate_job_runner(
            project_store=store,
            update_job_progress=lambda *_args, **_kwargs: None,
            run_orchestration=run_orchestration,
            build_run_summary=lambda result, **kwargs: {
                "run_id": "run_layout",
                "job_id": kwargs.get("job_id"),
                "source": "queued_job",
                "convergence_summary": {
                    "assumption_summary": {"count": 0, "categories": [], "examples": []},
                    "unresolved_issue_categories": [],
                    "blocked_reasons": [],
                    "blocked_exports": [],
                },
                "reliability_summary": {
                    "operational_state": "review",
                    "release_ready": False,
                },
                "phase_checkpoints": {
                    "layout": {"status": "complete", "ready": True},
                    "grading": {"status": "pending", "ready": False},
                    "drainage_storm": {"status": "pending", "ready": False},
                    "utilities": {"status": "pending", "ready": False},
                    "coordination_validation": {"status": "pending", "ready": False},
                    "combined_view": {"status": "review", "ready": False},
                },
                "requested_deliverables": [],
                "produced_deliverables": [],
                "ready_deliverables": [],
                "extra_deliverables": [],
                "failed_deliverables": [],
            },
            merge_project_metadata=lambda metadata, **kwargs: metadata,
            final_plan_from_result=lambda result, **kwargs: result.get("final_plan") or yielded_final_plan,
        )

        result = runner(
            {
                "job_id": "job_layout",
                "job_type": "orchestrate",
                "user_id": "u1",
                "project_id": "p1",
                "payload": {"prompt_text": "run"},
            }
        )

        self.assertTrue(result["metadata"]["runtime_should_continue"])
        self.assertEqual(
            dict(result["metadata"]["runtime_phase_checkpoint"]).get("stage_name"),
            "layout",
        )
        self.assertTrue(
            dict(result["metadata"]["runtime_phase_checkpoint"]).get("yielded")
        )

    def test_build_orchestrate_job_runner_finishes_after_coordination_checkpoint(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {},
                "latest_result": {},
                "session_state": {},
                "metadata": {},
            }
        )

        updates = []

        def run_orchestration(payload, progress_callback=None):
            return {
                "success": True,
                "final_plan": {"project_name": "Demo", "actions": []},
                "metadata": {
                    "runtime_should_continue": True,
                    "runtime_phase_checkpoint": {
                        "stage_name": "coordination_resolution",
                        "status": "complete",
                        "message": "Coordination stage completed.",
                        "yielded": True,
                    },
                },
            }

        runner = build_orchestrate_job_runner(
            project_store=store,
            update_job_progress=lambda *args, **kwargs: updates.append((args, kwargs)),
            run_orchestration=run_orchestration,
            build_run_summary=lambda result, **kwargs: {
                "run_id": "run_final",
                "job_id": kwargs.get("job_id"),
                "source": "queued_job",
                "convergence_summary": {
                    "assumption_summary": {"count": 0, "categories": [], "examples": []},
                    "unresolved_issue_categories": [],
                    "blocked_reasons": [],
                    "blocked_exports": [],
                },
                "reliability_summary": {
                    "operational_state": "ready",
                    "release_ready": True,
                },
                "phase_checkpoints": {
                    "combined_view": {"status": "ready", "ready": True},
                },
                "requested_deliverables": [],
                "produced_deliverables": [],
                "ready_deliverables": [],
                "extra_deliverables": [],
                "failed_deliverables": [],
            },
            merge_project_metadata=lambda metadata, **kwargs: metadata,
            final_plan_from_result=lambda result, **kwargs: result.get("final_plan") or {"project_name": "Demo", "actions": []},
        )

        result = runner(
            {
                "job_id": "job_final",
                "job_type": "orchestrate",
                "user_id": "u1",
                "project_id": "p1",
                "payload": {"prompt_text": "run"},
            }
        )

        self.assertFalse(result["metadata"]["runtime_should_continue"])
        self.assertFalse(
            dict(result["metadata"]["runtime_phase_checkpoint"]).get("yielded")
        )

    def test_build_orchestrate_job_runner_does_not_promote_explicit_not_ready_final_plan(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {},
                "latest_result": {},
                "session_state": {},
                "metadata": {},
            }
        )

        def run_orchestration(payload, progress_callback=None):
            return {
                "success": True,
                "final_plan": {
                    "project_name": "Demo",
                    "actions": [{"task": "rectangle", "layer": "BUILDING"}],
                    "meta": {"release_ready": False},
                },
            }

        runner = build_orchestrate_job_runner(
            project_store=store,
            update_job_progress=lambda *_args, **_kwargs: None,
            run_orchestration=run_orchestration,
            build_run_summary=lambda result, **kwargs: {
                "run_id": "run_explicit_block",
                "job_id": kwargs.get("job_id"),
                "source": "queued_job",
                "convergence_summary": {
                    "assumption_summary": {"count": 0, "categories": [], "examples": []},
                    "unresolved_issue_categories": [],
                    "blocked_reasons": [],
                    "blocked_exports": [],
                },
                "reliability_summary": {
                    "operational_state": "ready",
                    "release_ready": True,
                },
                "phase_checkpoints": {
                    "layout": {"status": "complete", "ready": True},
                    "grading": {"status": "complete", "ready": True},
                    "drainage_storm": {"status": "complete", "ready": True},
                    "utilities": {"status": "complete", "ready": True},
                    "coordination_validation": {"status": "complete", "ready": True},
                    "combined_view": {
                        "status": "ready",
                        "ready": True,
                        "completed_phase_count": 5,
                        "total_phase_count": 5,
                    },
                },
                "requested_deliverables": [],
                "produced_deliverables": [],
                "ready_deliverables": [],
                "extra_deliverables": [],
                "failed_deliverables": [],
            },
            merge_project_metadata=lambda metadata, **kwargs: {"workflow": {"runs": [kwargs["run_summary"]]}},
            final_plan_from_result=lambda result, **kwargs: dict(result.get("final_plan") or {}),
        )

        result = runner(
            {
                "job_id": "job_explicit_block",
                "job_type": "orchestrate",
                "user_id": "u1",
                "project_id": "p1",
                "payload": {"prompt_text": "run"},
            }
        )

        final_plan = result["final_plan"]
        release_review = final_plan["meta"]["release_review"]
        self.assertFalse(final_plan["release_ready"])
        self.assertEqual(final_plan["release_status"], "blocked")
        self.assertIn("final_plan_release_blocked", final_plan["blockers"])
        self.assertFalse(release_review["release_ready"])
        self.assertIn("final_plan_release_blocked", release_review["blocked_reasons"])
        saved_plan = store.saved_payload["latest_result"]["final_plan"]
        self.assertFalse(saved_plan["release_ready"])
        self.assertIn("final_plan_release_blocked", saved_plan["blockers"])

    def test_build_orchestrate_job_runner_blocks_export_ready_when_deliverables_fail(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {},
                "latest_result": {},
                "session_state": {},
                "metadata": {},
            }
        )

        def run_orchestration(payload, progress_callback=None):
            return {
                "success": True,
                "final_plan": {
                    "project_name": "Demo",
                    "actions": [{"task": "rectangle", "layer": "BUILDING"}],
                    "meta": {},
                },
            }

        runner = build_orchestrate_job_runner(
            project_store=store,
            update_job_progress=lambda *_args, **_kwargs: None,
            run_orchestration=run_orchestration,
            build_run_summary=lambda result, **kwargs: {
                "run_id": "run_failed_deliverable",
                "job_id": kwargs.get("job_id"),
                "source": "queued_job",
                "convergence_summary": {
                    "assumption_summary": {"count": 0, "categories": [], "examples": []},
                    "unresolved_issue_categories": [],
                    "blocked_reasons": [],
                    "blocked_exports": [],
                },
                "reliability_summary": {
                    "operational_state": "ready",
                    "release_ready": True,
                },
                "phase_checkpoints": {
                    "layout": {"status": "complete", "ready": True},
                    "combined_view": {"status": "ready", "ready": True, "completed_phase_count": 1, "total_phase_count": 1},
                },
                "requested_deliverables": ["site_plan", "report"],
                "produced_deliverables": ["site_plan"],
                "ready_deliverables": ["site_plan"],
                "extra_deliverables": [],
                "failed_deliverables": ["report"],
            },
            merge_project_metadata=lambda metadata, **kwargs: {"workflow": {"runs": [kwargs["run_summary"]]}},
            final_plan_from_result=lambda result, **kwargs: dict(result.get("final_plan") or {}),
        )

        result = runner(
            {
                "job_id": "job_failed_deliverable",
                "job_type": "orchestrate",
                "user_id": "u1",
                "project_id": "p1",
                "payload": {"prompt_text": "run"},
            }
        )

        final_plan = result["final_plan"]
        final_meta = final_plan["meta"]
        release_review = final_meta["release_review"]
        self.assertEqual(final_plan["release_status"], "blocked")
        self.assertFalse(final_plan["release_ready"])
        self.assertFalse(final_plan["export_ready"])
        self.assertFalse(final_meta["release_ready"])
        self.assertFalse(final_meta["export_ready"])
        self.assertFalse(release_review["release_ready"])
        self.assertIn("failed_deliverable_report", final_plan["blockers"])
        self.assertIn("failed_deliverable_report", final_meta["blockers"])
        self.assertIn("failed_deliverable_report", release_review["blocked_reasons"])
        self.assertEqual(final_plan["deliverables"]["failed"], ["report"])
        self.assertEqual(final_meta["deliverables"]["failed"], ["report"])
        self.assertEqual(release_review["reliability_summary"]["primary_attention"], "failed_deliverable_report")
        saved_plan = store.saved_payload["latest_result"]["final_plan"]
        self.assertFalse(saved_plan["release_ready"])
        self.assertFalse(saved_plan["export_ready"])
        self.assertIn("failed_deliverable_report", saved_plan["blockers"])

    def test_build_orchestrate_job_runner_preserves_failed_deliverables_from_final_meta(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {},
                "latest_result": {},
                "session_state": {},
                "metadata": {},
            }
        )

        def run_orchestration(payload, progress_callback=None):
            return {
                "success": True,
                "final_plan": {
                    "project_name": "Demo",
                    "actions": [{"task": "rectangle", "layer": "BUILDING"}],
                    "meta": {
                        "release_ready": True,
                        "release_status": "ready",
                        "deliverables": {
                            "requested": ["site_plan", "report"],
                            "produced": ["site_plan"],
                            "ready": ["site_plan"],
                            "failed": ["report"],
                        },
                    },
                },
            }

        runner = build_orchestrate_job_runner(
            project_store=store,
            update_job_progress=lambda *_args, **_kwargs: None,
            run_orchestration=run_orchestration,
            build_run_summary=lambda result, **kwargs: {
                "run_id": "run_meta_failed_deliverable",
                "job_id": kwargs.get("job_id"),
                "source": "queued_job",
                "convergence_summary": {
                    "assumption_summary": {"count": 0, "categories": [], "examples": []},
                    "unresolved_issue_categories": [],
                    "blocked_reasons": [],
                    "blocked_exports": [],
                },
                "reliability_summary": {
                    "operational_state": "ready",
                    "release_ready": True,
                },
                "phase_checkpoints": {
                    "layout": {"status": "complete", "ready": True},
                    "combined_view": {"status": "ready", "ready": True, "completed_phase_count": 1, "total_phase_count": 1},
                },
                "requested_deliverables": ["site_plan", "report"],
                "produced_deliverables": ["site_plan"],
                "ready_deliverables": ["site_plan"],
                "extra_deliverables": [],
                "failed_deliverables": [],
            },
            merge_project_metadata=lambda metadata, **kwargs: {"workflow": {"runs": [kwargs["run_summary"]]}},
            final_plan_from_result=lambda result, **kwargs: dict(result.get("final_plan") or {}),
        )

        result = runner(
            {
                "job_id": "job_meta_failed_deliverable",
                "job_type": "orchestrate",
                "user_id": "u1",
                "project_id": "p1",
                "payload": {"prompt_text": "run"},
            }
        )

        final_plan = result["final_plan"]
        final_meta = final_plan["meta"]
        release_review = final_meta["release_review"]
        self.assertEqual(final_plan["release_status"], "blocked")
        self.assertFalse(final_plan["release_ready"])
        self.assertFalse(final_plan["export_ready"])
        self.assertEqual(final_plan["deliverables"]["failed"], ["report"])
        self.assertEqual(final_meta["deliverables"]["failed"], ["report"])
        self.assertEqual(final_meta["run_summary"]["failed_deliverables"], ["report"])
        self.assertIn("failed_deliverable_report", final_plan["blockers"])
        self.assertIn("failed_deliverable_report", release_review["blocked_reasons"])
        saved_plan = store.saved_payload["latest_result"]["final_plan"]
        self.assertFalse(saved_plan["release_ready"])
        self.assertEqual(saved_plan["deliverables"]["failed"], ["report"])

    def test_build_orchestrate_job_runner_blocks_manual_failures_from_final_meta(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {},
                "latest_result": {},
                "session_state": {},
                "metadata": {},
            }
        )

        def run_orchestration(payload, progress_callback=None):
            return {
                "success": True,
                "final_plan": {
                    "project_name": "Demo",
                    "actions": [{"task": "rectangle", "layer": "BUILDING"}],
                    "meta": {
                        "release_ready": True,
                        "release_status": "ready",
                        "manual_validation": {
                            "failures": [
                                {
                                    "code": "MANUAL_STORM_HYDRAULIC_INVALID",
                                    "message": "Storm hydraulic review failed.",
                                }
                            ]
                        },
                    },
                },
            }

        runner = build_orchestrate_job_runner(
            project_store=store,
            update_job_progress=lambda *_args, **_kwargs: None,
            run_orchestration=run_orchestration,
            build_run_summary=lambda result, **kwargs: {
                "run_id": "run_manual_failure",
                "job_id": kwargs.get("job_id"),
                "source": "queued_job",
                "convergence_summary": {
                    "assumption_summary": {"count": 0, "categories": [], "examples": []},
                    "unresolved_issue_categories": [],
                    "blocked_reasons": [],
                    "blocked_exports": [],
                },
                "reliability_summary": {
                    "operational_state": "ready",
                    "release_ready": True,
                },
                "phase_checkpoints": {
                    "layout": {"status": "complete", "ready": True},
                    "combined_view": {"status": "ready", "ready": True, "completed_phase_count": 1, "total_phase_count": 1},
                },
                "requested_deliverables": [],
                "produced_deliverables": [],
                "ready_deliverables": [],
                "extra_deliverables": [],
                "failed_deliverables": [],
                "manual_failures": [],
            },
            merge_project_metadata=lambda metadata, **kwargs: {"workflow": {"runs": [kwargs["run_summary"]]}},
            final_plan_from_result=lambda result, **kwargs: dict(result.get("final_plan") or {}),
        )

        result = runner(
            {
                "job_id": "job_manual_failure",
                "job_type": "orchestrate",
                "user_id": "u1",
                "project_id": "p1",
                "payload": {"prompt_text": "run"},
            }
        )

        final_plan = result["final_plan"]
        final_meta = final_plan["meta"]
        release_review = final_meta["release_review"]
        self.assertEqual(final_plan["release_status"], "blocked")
        self.assertFalse(final_plan["release_ready"])
        self.assertFalse(final_plan["export_ready"])
        self.assertFalse(final_meta["release_ready"])
        self.assertFalse(final_meta["export_ready"])
        self.assertFalse(release_review["release_ready"])
        self.assertIn("manual_validation_manual_storm_hydraulic_invalid", final_plan["blockers"])
        self.assertIn("manual_validation_manual_storm_hydraulic_invalid", final_meta["blockers"])
        self.assertIn("manual_validation_manual_storm_hydraulic_invalid", release_review["blocked_reasons"])
        self.assertEqual(final_meta["phase_checkpoints"]["combined_view"]["status"], "blocked")
        self.assertFalse(final_meta["phase_checkpoints"]["combined_view"]["ready"])
        self.assertIn(
            "manual_validation_manual_storm_hydraulic_invalid",
            final_meta["phase_checkpoints"]["combined_view"]["blocked_reasons"],
        )
        self.assertEqual(final_meta["run_summary"]["manual_failures"][0]["code"], "MANUAL_STORM_HYDRAULIC_INVALID")
        self.assertEqual(release_review["reliability_summary"]["manual_failure_count"], 1)
        saved_plan = store.saved_payload["latest_result"]["final_plan"]
        self.assertFalse(saved_plan["release_ready"])
        self.assertIn("manual_validation_manual_storm_hydraulic_invalid", saved_plan["blockers"])
        self.assertFalse(saved_plan["meta"]["phase_checkpoints"]["combined_view"]["ready"])

    def test_build_orchestrate_job_runner_persists_phase_checkpoints_mid_run(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {},
                "latest_result": {},
                "session_state": {},
                "metadata": {},
            }
        )

        def run_orchestration(payload, progress_callback=None):
            progress_callback("layout", "running", 18, "Running layout phase.")
            progress_callback("layout", "complete", 18, "Layout complete.")
            progress_callback("grading", "running", 30, "Running grading phase.")
            progress_callback("grading", "complete", 30, "Grading complete.")
            return {
                "success": True,
                "final_plan": {
                    "project_name": "Demo",
                    "meta": {
                        "grading": {"surface": "ok"},
                    },
                },
            }

        runner = build_orchestrate_job_runner(
            project_store=store,
            update_job_progress=lambda *_args, **_kwargs: None,
            run_orchestration=run_orchestration,
            build_run_summary=lambda result, **kwargs: {
                "run_id": "run_final",
                "job_id": kwargs.get("job_id"),
                "source": "queued_job",
                "convergence_summary": {
                    "assumption_summary": {"count": 0, "categories": [], "examples": []},
                    "unresolved_issue_categories": [],
                    "blocked_reasons": [],
                    "blocked_exports": [],
                },
                "reliability_summary": {
                    "operational_state": "ready",
                    "release_ready": True,
                },
                "phase_checkpoints": {
                    "layout": {"status": "complete", "ready": True},
                    "grading": {"status": "complete", "ready": True},
                    "combined_view": {"status": "ready", "ready": True},
                },
                "requested_deliverables": ["site_plan"],
                "produced_deliverables": ["site_plan"],
                "ready_deliverables": ["site_plan"],
                "extra_deliverables": [],
                "failed_deliverables": [],
            },
            merge_project_metadata=lambda metadata, **kwargs: {
                "workflow": {
                    "runs": [kwargs["run_summary"]],
                }
            },
            final_plan_from_result=lambda result, **kwargs: {
                "project_name": "Demo",
                "meta": {
                    "grading": {"surface": "ok"},
                },
            },
        )

        runner(
            {
                "job_id": "job_phase_persist",
                "job_type": "orchestrate",
                "user_id": "u1",
                "project_id": "p1",
                "payload": {"prompt_text": "run"},
            }
        )

        self.assertGreaterEqual(len(store.save_calls), 5)
        phase_save = store.save_calls[0]
        phase_run = phase_save["metadata"]["workflow"]["runs"][0]
        self.assertEqual(phase_run["job_id"], "job_phase_persist")
        self.assertEqual(phase_run["phase_checkpoints"]["layout"]["status"], "running")
        self.assertFalse(phase_run["phase_checkpoints"]["layout"]["ready"])
        self.assertEqual(
            phase_save["latest_result"]["final_plan"]["meta"]["phase_checkpoints"]["layout"]["status"],
            "running",
        )
        self.assertEqual(
            phase_save["latest_result"]["final_plan"]["meta"]["stage_completeness"]["statuses"]["layout"],
            "running",
        )
        self.assertEqual(
            phase_save["latest_result"]["final_plan"]["meta"]["phase_checkpoints"]["combined_view"]["status"],
            "running",
        )
        self.assertEqual(
            phase_save["latest_result"]["final_plan"]["meta"]["phase_checkpoints"]["combined_view"]["completed_phase_count"],
            0,
        )
        second_phase_save = store.save_calls[1]
        second_phase_run = second_phase_save["metadata"]["workflow"]["runs"][0]
        self.assertEqual(second_phase_run["phase_checkpoints"]["layout"]["status"], "complete")
        self.assertTrue(second_phase_run["phase_checkpoints"]["layout"]["ready"])
        self.assertEqual(
            second_phase_save["latest_result"]["final_plan"]["meta"]["stage_completeness"]["statuses"]["layout"],
            "complete",
        )
        self.assertEqual(
            second_phase_save["latest_result"]["final_plan"]["meta"]["phase_checkpoints"]["combined_view"]["completed_phase_count"],
            1,
        )
        third_phase_save = store.save_calls[2]
        third_phase_run = third_phase_save["metadata"]["workflow"]["runs"][0]
        self.assertEqual(third_phase_run["phase_checkpoints"]["grading"]["status"], "running")
        self.assertEqual(
            third_phase_save["latest_result"]["final_plan"]["meta"]["stage_completeness"]["statuses"]["grading"],
            "running",
        )
        fourth_phase_save = store.save_calls[3]
        fourth_phase_run = fourth_phase_save["metadata"]["workflow"]["runs"][0]
        self.assertEqual(fourth_phase_run["phase_checkpoints"]["grading"]["status"], "complete")
        self.assertTrue(fourth_phase_run["phase_checkpoints"]["grading"]["ready"])
        self.assertEqual(
            fourth_phase_save["latest_result"]["final_plan"]["meta"]["stage_completeness"]["statuses"]["grading"],
            "complete",
        )
        self.assertEqual(
            fourth_phase_save["latest_result"]["final_plan"]["meta"]["phase_checkpoints"]["combined_view"]["completed_phase_count"],
            2,
        )

    def test_build_orchestrate_job_runner_does_not_count_assumed_stage_progress_complete(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {},
                "latest_result": {
                    "final_plan": {
                        "actions": [{"task": "rectangle", "layer": "SITE"}],
                        "meta": {
                            "stage_completeness": {
                                "statuses": {
                                    "layout": "complete",
                                    "sanitary": "assumed",
                                }
                            },
                            "phase_checkpoints": {
                                "layout": {"status": "complete", "ready": True},
                                "utilities": {"status": "pending", "ready": False},
                            },
                        },
                    },
                    "metadata": {"run_summary": {}},
                },
                "session_state": {},
                "metadata": {},
            }
        )

        def run_orchestration(payload, progress_callback=None):
            progress_callback("layout", "complete", 18, "Layout complete.")
            return {"success": True, "final_plan": {"project_name": "Demo", "meta": {}}}

        runner = build_orchestrate_job_runner(
            project_store=store,
            update_job_progress=lambda *_args, **_kwargs: None,
            run_orchestration=run_orchestration,
            build_run_summary=lambda result, **kwargs: {
                "run_id": "run_assumed",
                "job_id": kwargs.get("job_id"),
                "source": "queued_job",
                "convergence_summary": {
                    "assumption_summary": {"count": 0, "categories": [], "examples": []},
                    "unresolved_issue_categories": [],
                    "blocked_reasons": [],
                    "blocked_exports": [],
                },
                "reliability_summary": {"operational_state": "review", "release_ready": False},
                "phase_checkpoints": {
                    "layout": {"status": "complete", "ready": True},
                    "combined_view": {"status": "partial", "ready": False},
                },
                "requested_deliverables": [],
                "produced_deliverables": [],
                "ready_deliverables": [],
                "extra_deliverables": [],
                "failed_deliverables": [],
            },
            merge_project_metadata=lambda metadata, **kwargs: {"workflow": {"runs": [kwargs["run_summary"]]}},
            final_plan_from_result=lambda result, **kwargs: {"project_name": "Demo", "meta": {}},
        )

        runner(
            {
                "job_id": "job_assumed_progress",
                "job_type": "orchestrate",
                "user_id": "u1",
                "project_id": "p1",
                "payload": {"prompt_text": "run"},
            }
        )

        phase_save = store.save_calls[0]
        phase_run = phase_save["metadata"]["workflow"]["runs"][0]
        self.assertEqual(phase_run["phase_checkpoints"]["utilities"]["status"], "partial")
        self.assertFalse(phase_run["phase_checkpoints"]["utilities"]["ready"])
        self.assertEqual(
            phase_save["latest_result"]["final_plan"]["meta"]["phase_checkpoints"]["combined_view"]["completed_phase_count"],
            1,
        )

    def test_build_orchestrate_job_runner_resumes_from_saved_checkpoint_state(self):
        captured_payload = {}
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {},
                "latest_result": {
                    "final_plan": {
                        "actions": [{"task": "rectangle", "layer": "BUILDING", "label": "MF-1"}],
                        "meta": {
                            "stage_completeness": {
                                "statuses": {
                                    "layout": "complete",
                                    "grading": "complete",
                                }
                            },
                            "phase_checkpoints": {
                                "layout": {"status": "complete", "ready": True},
                                "grading": {"status": "complete", "ready": True},
                            },
                            "parking_program": {"requested": 42},
                            "grading": {"surface": "checkpoint"},
                        },
                    },
                    "metadata": {
                        "run_summary": {
                            "phase_checkpoints": {
                                "layout": {"status": "complete", "ready": True},
                                "grading": {"status": "complete", "ready": True},
                            }
                        }
                    },
                },
                "session_state": {},
                "metadata": {},
            }
        )

        def run_orchestration(payload, progress_callback=None):
            captured_payload.update(payload)
            return {
                "success": True,
                "final_plan": {
                    "project_name": "Demo",
                    "meta": {
                        "grading": {"surface": "ok"},
                    },
                },
            }

        runner = build_orchestrate_job_runner(
            project_store=store,
            update_job_progress=lambda *_args, **_kwargs: None,
            run_orchestration=run_orchestration,
            build_run_summary=lambda result, **kwargs: {
                "run_id": "run_resume",
                "job_id": kwargs.get("job_id"),
                "source": "queued_job",
                "convergence_summary": {
                    "assumption_summary": {"count": 0, "categories": [], "examples": []},
                    "unresolved_issue_categories": [],
                    "blocked_reasons": [],
                    "blocked_exports": [],
                },
                "reliability_summary": {
                    "operational_state": "ready",
                    "release_ready": True,
                },
                "phase_checkpoints": {
                    "layout": {"status": "complete", "ready": True},
                    "grading": {"status": "complete", "ready": True},
                    "combined_view": {"status": "ready", "ready": True},
                },
                "requested_deliverables": ["site_plan"],
                "produced_deliverables": ["site_plan"],
                "ready_deliverables": ["site_plan"],
                "extra_deliverables": [],
                "failed_deliverables": [],
            },
            merge_project_metadata=lambda metadata, **kwargs: metadata,
            final_plan_from_result=lambda result, **kwargs: {
                "project_name": "Demo",
                "meta": {
                    "grading": {"surface": "ok"},
                },
            },
        )

        runner(
            {
                "job_id": "job_resume",
                "job_type": "orchestrate",
                "user_id": "u1",
                "project_id": "p1",
                "payload": {"prompt_text": "run"},
            }
        )

        runtime_resume = dict(dict(captured_payload.get("meta") or {}).get("runtime_resume") or {})
        self.assertEqual(runtime_resume["project_id"], "p1")
        self.assertEqual(runtime_resume["stage_statuses"]["layout"], "complete")
        self.assertEqual(runtime_resume["stage_statuses"]["grading"], "complete")
        self.assertTrue(runtime_resume["phase_checkpoints"]["layout"]["ready"])

    def test_build_orchestrate_job_runner_uses_full_latest_result_not_shell(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {},
                "latest_result": {},
                "session_state": {},
                "metadata": {},
            }
        )
        store.latest_result_override = {
            "final_plan": {
                "actions": [{"task": "rectangle", "layer": "BUILDING", "label": "MF-1"}],
                "meta": {
                    "stage_completeness": {
                        "statuses": {
                            "layout": "complete",
                            "grading": "complete",
                        }
                    },
                    "phase_checkpoints": {
                        "layout": {"status": "complete", "ready": True},
                        "grading": {"status": "complete", "ready": True},
                        "combined_view": {"status": "partial", "ready": False, "completed_phase_count": 2, "total_phase_count": 5},
                    },
                },
            },
            "metadata": {
                "run_summary": {
                    "phase_checkpoints": {
                        "layout": {"status": "complete", "ready": True},
                        "grading": {"status": "complete", "ready": True},
                        "combined_view": {"status": "partial", "ready": False, "completed_phase_count": 2, "total_phase_count": 5},
                    }
                }
            },
        }

        def run_orchestration(payload, progress_callback=None):
            progress_callback("drainage", "running", 42, "Running drainage phase.")
            progress_callback("drainage", "complete", 60, "Drainage network designed.")
            return {
                "success": True,
                "final_plan": {
                    "project_name": "Demo",
                    "actions": [{"task": "polyline", "layer": "DRAIN"}],
                    "meta": {
                        "drainage": {"ok": True},
                    },
                },
            }

        runner = build_orchestrate_job_runner(
            project_store=store,
            update_job_progress=lambda *_args, **_kwargs: None,
            run_orchestration=run_orchestration,
            build_run_summary=lambda result, **kwargs: {
                "run_id": "run_drain",
                "job_id": kwargs.get("job_id"),
                "source": "queued_job",
                "convergence_summary": {"assumption_summary": {"count": 0, "categories": [], "examples": []}},
                "reliability_summary": {"operational_state": "review", "release_ready": False},
                "phase_checkpoints": dict((result.get("final_plan") or {}).get("meta", {}).get("phase_checkpoints") or {}),
                "requested_deliverables": [],
                "produced_deliverables": [],
                "ready_deliverables": [],
                "extra_deliverables": [],
                "failed_deliverables": [],
            },
            merge_project_metadata=lambda metadata, **kwargs: {
                "workflow": {"runs": [kwargs["run_summary"]]},
            },
            final_plan_from_result=lambda result, **kwargs: dict(result.get("final_plan") or {}),
        )

        runner(
            {
                "job_id": "job_drain",
                "job_type": "orchestrate",
                "user_id": "u1",
                "project_id": "p1",
                "payload": {"prompt_text": "run"},
            }
        )

        self.assertGreaterEqual(len(store.save_calls), 2)
        second_phase_save = store.save_calls[1]
        self.assertEqual(
            second_phase_save["latest_result"]["final_plan"]["meta"]["phase_checkpoints"]["layout"]["status"],
            "complete",
        )
        self.assertEqual(
            second_phase_save["latest_result"]["final_plan"]["meta"]["phase_checkpoints"]["grading"]["status"],
            "complete",
        )
        self.assertEqual(store.saved_payload["project_input"], {"prompt_text": "run"})

    def test_cancel_existing_job_returns_summary(self):
        queue = FakeJobQueue()
        response = cancel_existing_job(job_queue=queue, user_id="u1", job_id="job_1")
        self.assertTrue(response["success"])
        self.assertEqual(queue.cancelled, {"user_id": "u1", "job_id": "job_1"})
        self.assertEqual(response["job"]["status"], "cancelled")

    def test_cancel_existing_job_raises_for_missing_job(self):
        queue = FakeJobQueue()
        with self.assertRaises(HTTPException) as ctx:
            cancel_existing_job(job_queue=queue, user_id="u1", job_id="missing")
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
