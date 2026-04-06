import tempfile
import time
import unittest
from pathlib import Path

from backend.services.database import Database
from backend.services.job_queue import JobQueueService


class JobQueueServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.db"
        self.db = Database(self.db_path)
        self.queue = JobQueueService(self.db)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_list_jobs_returns_full_records(self):
        created = self.queue.submit_job(
            user_id="u1",
            job_type="orchestrate",
            payload={"prompt_text": "demo"},
            project_id="p1",
        )
        jobs = self.queue.list_jobs(user_id="u1")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["job_id"], created["job_id"])
        self.assertEqual(jobs[0]["project_id"], "p1")
        self.assertEqual(jobs[0]["status"], "queued")

    def test_job_summary_tolerates_bad_progress_shape(self):
        connection = self.db.connect()
        try:
            connection.execute(
                """
                INSERT INTO jobs (job_id, user_id, job_type, status, created_at, updated_at, project_id, payload_json, result_json, error_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "job_legacy",
                    "u1",
                    "orchestrate",
                    "running",
                    1.0,
                    2.0,
                    None,
                    "{}",
                    '{"job_progress":{"stage":"Running","detail":"legacy","progress":"oops"}}',
                    None,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        jobs = self.queue.list_jobs(user_id="u1")
        self.assertEqual(jobs[0]["job_id"], "job_legacy")
        self.assertEqual(jobs[0]["progress"], 0)

    def test_worker_recovers_queued_jobs_from_database_without_in_memory_queue(self):
        self.queue.register_handler(
            "orchestrate",
            lambda job: {"success": True, "result": {"job_id": job["job_id"]}},
        )
        created = self.queue.submit_job(
            user_id="u1",
            job_type="orchestrate",
            payload={"prompt_text": "demo"},
        )

        drained_job_id = self.queue._queue.get(timeout=1.0)
        self.assertEqual(drained_job_id, created["job_id"])
        self.queue._queue.task_done()

        deadline = time.time() + 3.0
        record = None
        while time.time() < deadline:
            record = self.queue.get_job(user_id="u1", job_id=created["job_id"])
            if record and record["status"] == "completed":
                break
            time.sleep(0.05)

        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "completed")

    def test_list_jobs_restarts_worker_if_thread_dies(self):
        self.queue._worker = None
        jobs = self.queue.list_jobs(user_id="u1")
        self.assertEqual(jobs, [])
        self.assertIsNotNone(self.queue._worker)
        self.assertTrue(self.queue._worker.is_alive())


if __name__ == "__main__":
    unittest.main()
