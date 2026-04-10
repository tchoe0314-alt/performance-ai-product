import unittest

from fastapi import HTTPException

from backend.application.job_workflows import (
    build_orchestrate_job_runner,
    cancel_existing_job,
    queue_orchestrate_job,
)


class FakeProjectStore:
    def __init__(self, project=None):
        self.project = project
        self.saved_payload = None
        self.save_calls = []

    def get_project(self, *, user_id: str, project_id: str):
        if self.project and user_id == self.project.get("user_id") and project_id == self.project.get("project_id"):
            return dict(self.project)
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

    def submit_job(self, *, user_id, job_type, payload, project_id=None):
        self.submitted = {
            "user_id": user_id,
            "job_type": job_type,
            "payload": dict(payload),
            "project_id": project_id,
        }
        return {"job_id": "job_1", "status": "queued", "project_id": project_id, "job_type": job_type}

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
        store = FakeProjectStore({"user_id": "u1", "project_id": "p1"})
        queue = FakeJobQueue()
        response = queue_orchestrate_job(
            project_store=store,
            job_queue=queue,
            user_id="u1",
            project_id="p1",
            request_payload={"prompt_text": "run"},
        )
        self.assertTrue(response["success"])
        self.assertEqual(queue.submitted["job_type"], "orchestrate")
        self.assertEqual(response["operational_summary"]["status"], "queued")
        self.assertTrue(response["operational_summary"]["project_bound"])
        self.assertEqual(response["operational_summary"]["job_id"], "job_1")

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
        self.assertEqual(result["final_plan"]["blockers"], [])
        self.assertEqual(result["final_plan"]["deliverables"]["ready"], [])
        self.assertEqual(result["final_plan"]["meta"]["phase_checkpoints"]["layout"]["status"], "complete")
        self.assertFalse(result["final_plan"]["meta"]["phase_checkpoints"]["combined_view"]["ready"])
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
            [item["stage"] for item in progress_updates],
            ["Engineering Run", "Saving Project", "Finalizing"],
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
        second_phase_save = store.save_calls[1]
        second_phase_run = second_phase_save["metadata"]["workflow"]["runs"][0]
        self.assertEqual(second_phase_run["phase_checkpoints"]["layout"]["status"], "complete")
        self.assertTrue(second_phase_run["phase_checkpoints"]["layout"]["ready"])
        third_phase_save = store.save_calls[2]
        third_phase_run = third_phase_save["metadata"]["workflow"]["runs"][0]
        self.assertEqual(third_phase_run["phase_checkpoints"]["grading"]["status"], "running")
        fourth_phase_save = store.save_calls[3]
        fourth_phase_run = fourth_phase_save["metadata"]["workflow"]["runs"][0]
        self.assertEqual(fourth_phase_run["phase_checkpoints"]["grading"]["status"], "complete")
        self.assertTrue(fourth_phase_run["phase_checkpoints"]["grading"]["ready"])

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
