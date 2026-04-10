import tempfile
import time
import unittest
from pathlib import Path

from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.job_queue import JobQueueService
from backend.services.project_store import ProjectStore
from engines.storm.storm_types import StormPipe, StormPipeType


class JobQueueServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.db"
        self.db = Database(self.db_path)
        self.auth = AuthStore(self.db)
        registered = self.auth.register_user(email="u1@example.com", password="password123", name="U1")
        self.user_id = registered["user"]["user_id"]
        self.queue = JobQueueService(self.db, heartbeat_interval_sec=0.5)

    def tearDown(self) -> None:
        self.queue.db = Database(Path(tempfile.gettempdir()) / "civora_job_queue_teardown.db")
        self.tmpdir.cleanup()

    def test_list_jobs_returns_full_records(self):
        ProjectStore(self.db).save_project(
            user_id=self.user_id,
            project_id="p1",
            name="Project 1",
        )
        created = self.queue.submit_job(
            user_id=self.user_id,
            job_type="orchestrate",
            payload={"prompt_text": "demo"},
            project_id="p1",
        )
        jobs = self.queue.list_jobs(user_id=self.user_id)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["job_id"], created["job_id"])
        self.assertEqual(jobs[0]["project_id"], "p1")
        self.assertEqual(jobs[0]["status"], "queued")

    def test_job_summary_tolerates_bad_progress_shape(self):
        connection = self.db.connect()
        try:
            connection.execute(
                """
                INSERT INTO jobs (
                    job_id, user_id, job_type, status, created_at, updated_at, project_id,
                    stage, stage_detail, progress, payload_json, result_json, error_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "job_legacy",
                    self.user_id,
                    "orchestrate",
                    "running",
                    1.0,
                    2.0,
                    None,
                    "Running",
                    "legacy",
                    0,
                    "{}",
                    '{"job_progress":{"stage":"Running","detail":"legacy","progress":"oops"}}',
                    None,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        jobs = self.queue.list_jobs(user_id=self.user_id)
        self.assertEqual(jobs[0]["job_id"], "job_legacy")
        self.assertEqual(jobs[0]["progress"], 0)

    def test_get_job_detail_exposes_progress_and_result_together(self):
        ProjectStore(self.db).save_project(
            user_id=self.user_id,
            project_id="p1",
            name="Project 1",
        )
        connection = self.db.connect()
        try:
            connection.execute(
                """
                INSERT INTO jobs (
                    job_id, user_id, job_type, status, created_at, updated_at, project_id,
                    stage, stage_detail, progress, payload_json, result_json, error_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "job_detail",
                    self.user_id,
                    "orchestrate",
                    "running",
                    1.0,
                    2.0,
                    "p1",
                    "Engineering Run",
                    "Working",
                    48,
                    '{"prompt_text":"demo"}',
                    '{"job_progress":{"stage":"Engineering Run","detail":"Working","progress":48},"final_plan":{"name":"Demo"}}',
                    None,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        job = self.queue.get_job_detail(user_id=self.user_id, job_id="job_detail")
        self.assertIsNotNone(job)
        self.assertEqual(job["stage"], "Engineering Run")
        self.assertEqual(job["progress"], 48)
        self.assertEqual(job["result"], {})

    def test_get_job_detail_includes_result_after_completion_only(self):
        connection = self.db.connect()
        try:
            connection.execute(
                """
                INSERT INTO jobs (
                    job_id, user_id, job_type, status, created_at, updated_at, project_id,
                    stage, stage_detail, progress, payload_json, result_json, error_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "job_done",
                    self.user_id,
                    "orchestrate",
                    "completed",
                    1.0,
                    3.0,
                    None,
                    "Completed",
                    "Ready",
                    100,
                    '{"prompt_text":"demo"}',
                    '{"job_progress":{"stage":"Completed","detail":"Ready","progress":100},"final_plan":{"name":"Demo"}}',
                    None,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        job = self.queue.get_job_detail(user_id=self.user_id, job_id="job_done")
        self.assertIsNotNone(job)
        self.assertEqual(job["result"]["final_plan"]["name"], "Demo")

    def test_worker_recovers_queued_jobs_from_database_without_in_memory_queue(self):
        self.queue.register_handler(
            "orchestrate",
            lambda job: {"success": True, "result": {"job_id": job["job_id"]}},
        )
        created = self.queue.submit_job(
            user_id=self.user_id,
            job_type="orchestrate",
            payload={"prompt_text": "demo"},
        )

        drained_job_id = self.queue._queue.get(timeout=1.0)
        self.assertEqual(drained_job_id, created["job_id"])
        self.queue._queue.task_done()

        deadline = time.time() + 3.0
        record = None
        while time.time() < deadline:
            record = self.queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
            if record and record["status"] == "completed":
                break
            time.sleep(0.05)

        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "completed")

    def test_list_jobs_restarts_worker_if_thread_dies(self):
        self.queue._workers = []
        jobs = self.queue.list_jobs(user_id=self.user_id)
        self.assertEqual(jobs, [])
        self.assertTrue(self.queue._workers)
        self.assertTrue(all(worker.is_alive() for worker in self.queue._workers))

    def test_job_result_serializes_dataclass_objects(self):
        self.queue.register_handler(
            "orchestrate",
            lambda job: {
                "success": True,
                "storm_pipe": StormPipe(
                    name="P-001",
                    pipe_type=StormPipeType.MAIN.value,
                    upstream_node_name="I-1",
                    downstream_node_name="J-1",
                    route_points=[(0.0, 0.0), (10.0, 0.0)],
                    diameter_in=18.0,
                ),
            },
        )
        created = self.queue.submit_job(
            user_id=self.user_id,
            job_type="orchestrate",
            payload={"prompt_text": "storm"},
        )

        deadline = time.time() + 3.0
        record = None
        while time.time() < deadline:
            record = self.queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
            if record and record["status"] == "completed":
                break
            time.sleep(0.05)

        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["result"]["storm_pipe"]["name"], "P-001")
        self.assertEqual(record["result"]["storm_pipe"]["upstream_node_name"], "I-1")

    def test_project_store_serializes_dataclass_results(self):
        store = ProjectStore(self.db)
        saved = store.save_project(
            user_id=self.user_id,
            project_id=None,
            name="Storm Demo",
            latest_result={
                "success": True,
                "storm_pipe": StormPipe(
                    name="P-002",
                    pipe_type=StormPipeType.TRUNK.value,
                    upstream_node_name="J-1",
                    downstream_node_name="O-1",
                    route_points=[(1.0, 2.0), (8.0, 9.0)],
                    diameter_in=24.0,
                ),
            },
        )

        loaded = store.get_project(user_id=self.user_id, project_id=saved["project_id"])
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["latest_result"]["storm_pipe"]["name"], "P-002")
        self.assertEqual(loaded["latest_result"]["storm_pipe"]["diameter_in"], 24.0)

    def test_project_list_uses_persisted_has_result_flag(self):
        store = ProjectStore(self.db)
        saved = store.save_project(
            user_id=self.user_id,
            project_id=None,
            name="Summary Demo",
            latest_result={},
        )
        summaries = store.list_projects(user_id=self.user_id)
        self.assertEqual(len(summaries), 1)
        self.assertFalse(summaries[0]["has_result"])

        store.save_project(
            user_id=self.user_id,
            project_id=saved["project_id"],
            name="Summary Demo",
            latest_result={"final_plan": {"project_name": "Summary Demo"}},
        )
        summaries = store.list_projects(user_id=self.user_id)
        self.assertTrue(summaries[0]["has_result"])

    def test_running_job_heartbeat_keeps_updated_at_fresh(self):
        self.queue.register_handler(
            "orchestrate",
            lambda job: (time.sleep(1.3), {"success": True})[1],
        )
        created = self.queue.submit_job(
            user_id=self.user_id,
            job_type="orchestrate",
            payload={"prompt_text": "slow"},
        )

        initial_running = None
        deadline = time.time() + 3.0
        while time.time() < deadline:
            current = self.queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
            if current and current["status"] == "running":
                initial_running = current
                break
            time.sleep(0.05)

        self.assertIsNotNone(initial_running)

        refreshed_running = None
        heartbeat_deadline = time.time() + 2.0
        while time.time() < heartbeat_deadline:
            current = self.queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
            if current and current["status"] == "running" and float(current["updated_at"]) > float(initial_running["updated_at"]):
                refreshed_running = current
                break
            time.sleep(0.05)

        self.assertIsNotNone(refreshed_running)
        self.assertEqual(refreshed_running["progress"], 24)

    def test_job_summaries_include_queue_position_and_running_count(self):
        store = ProjectStore(self.db)
        for project_id in ("p1", "p2", "p3"):
            store.save_project(
                user_id=self.user_id,
                project_id=project_id,
                name=project_id.upper(),
            )
        connection = self.db.connect()
        try:
            connection.execute(
                """
                INSERT INTO jobs (
                    job_id, user_id, job_type, status, created_at, updated_at, project_id,
                    stage, stage_detail, progress, payload_json, result_json, error_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "job_running",
                    self.user_id,
                    "orchestrate",
                    "running",
                    1.0,
                    5.0,
                    "p1",
                    "Engineering Run",
                    "Working",
                    48,
                    "{}",
                    '{"job_progress":{"stage":"Engineering Run","detail":"Working","progress":48}}',
                    None,
                ),
            )
            connection.execute(
                """
                INSERT INTO jobs (
                    job_id, user_id, job_type, status, created_at, updated_at, project_id,
                    stage, stage_detail, progress, payload_json, result_json, error_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "job_queued_1",
                    self.user_id,
                    "orchestrate",
                    "queued",
                    2.0,
                    2.0,
                    "p2",
                    "Queued",
                    "Waiting",
                    12,
                    "{}",
                    '{"job_progress":{"stage":"Queued","detail":"Waiting","progress":12}}',
                    None,
                ),
            )
            connection.execute(
                """
                INSERT INTO jobs (
                    job_id, user_id, job_type, status, created_at, updated_at, project_id,
                    stage, stage_detail, progress, payload_json, result_json, error_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "job_queued_2",
                    self.user_id,
                    "orchestrate",
                    "queued",
                    3.0,
                    3.0,
                    "p3",
                    "Queued",
                    "Waiting",
                    12,
                    "{}",
                    '{"job_progress":{"stage":"Queued","detail":"Waiting","progress":12}}',
                    None,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        jobs = {job["job_id"]: job for job in self.queue.list_jobs(user_id=self.user_id)}
        self.assertEqual(jobs["job_running"]["running_count"], 1)
        self.assertEqual(jobs["job_queued_1"]["queue_position"], 1)
        self.assertEqual(jobs["job_queued_1"]["queued_count"], 2)
        self.assertEqual(jobs["job_queued_1"]["running_count"], 1)
        self.assertEqual(jobs["job_queued_2"]["queue_position"], 2)


if __name__ == "__main__":
    unittest.main()
