import tempfile
import unittest
from pathlib import Path

from backend.services.database import Database
from backend.services.job_queue import JobQueueService


class JobQueueServiceTest(unittest.TestCase):
    def test_list_jobs_tolerates_legacy_progress_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(Path(tmpdir) / "jobs.sqlite3")
            queue = JobQueueService(db)
            connection = db.connect()
            try:
                connection.execute(
                    """
                    INSERT INTO jobs (
                        job_id, user_id, job_type, status, created_at, updated_at,
                        project_id, payload_json, result_json, error_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "job_legacy",
                        "user_1",
                        "orchestrate",
                        "running",
                        1.0,
                        2.0,
                        "project_1",
                        "{}",
                        '{"job_progress":{"stage":"Engineering Run","detail":"Legacy percent string","progress":"67%"}}',
                        None,
                    ),
                )
                connection.commit()
            finally:
                connection.close()

            jobs = queue.list_jobs(user_id="user_1")
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["stage"], "Engineering Run")
            self.assertEqual(jobs[0]["stage_detail"], "Legacy percent string")
            self.assertEqual(jobs[0]["progress"], 67)


if __name__ == "__main__":
    unittest.main()
