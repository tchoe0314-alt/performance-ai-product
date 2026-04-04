import unittest

from fastapi import HTTPException

from backend.application.job_workflows import (
    build_orchestrate_job_runner,
    queue_orchestrate_job,
)


class FakeProjectStore:
    def __init__(self, project=None):
        self.project = project
        self.saved_payload = None

    def get_project(self, *, user_id: str, project_id: str):
        if self.project and user_id == self.project.get("user_id") and project_id == self.project.get("project_id"):
            return dict(self.project)
        return None

    def save_project(self, **kwargs):
        self.saved_payload = dict(kwargs)
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

    def submit_job(self, *, user_id, job_type, payload, project_id=None):
        self.submitted = {
            "user_id": user_id,
            "job_type": job_type,
            "payload": dict(payload),
            "project_id": project_id,
        }
        return {"job_id": "job_1", "status": "queued", "project_id": project_id}

    def register_handler(self, job_type, runner):
        self.registered[job_type] = runner


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
        runner = build_orchestrate_job_runner(
            project_store=store,
            run_orchestration=lambda payload: {"success": True, "final_plan": {"project_name": "Demo", "meta": {}}},
            build_run_summary=lambda result, **kwargs: {"run_id": "run_1", "job_id": kwargs.get("job_id")},
            merge_project_metadata=lambda metadata, **kwargs: {"workflow": {"runs": [kwargs["run_summary"]]}},
        )
        result = runner(
            {
                "job_id": "job_1",
                "user_id": "u1",
                "project_id": "p1",
                "payload": {"prompt_text": "run"},
            }
        )
        self.assertTrue(result["success"])
        self.assertEqual(store.saved_payload["metadata"]["workflow"]["runs"][0]["job_id"], "job_1")


if __name__ == "__main__":
    unittest.main()
