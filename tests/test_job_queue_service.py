import tempfile
import threading
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
        self.queue = JobQueueService(self.db, heartbeat_interval_sec=0.5, resume_poll_interval_sec=0.5)

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

    def test_submit_job_reuses_matching_active_job(self):
        first = self.queue.submit_job(
            user_id=self.user_id,
            job_type="orchestrate",
            payload={"prompt_text": "demo", "meta": {"requested_system": "grading"}},
            project_id=None,
        )
        second = self.queue.submit_job(
            user_id=self.user_id,
            job_type="orchestrate",
            payload={"meta": {"requested_system": "grading"}, "prompt_text": "demo"},
            project_id=None,
        )

        self.assertEqual(second["job_id"], first["job_id"])
        self.assertTrue(second["deduplicated"])
        self.assertEqual(second["duplicate_of"], first["job_id"])
        self.assertEqual(len(self.queue.list_jobs(user_id=self.user_id)), 1)

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
        self.assertEqual(job["result"]["final_plan"]["name"], "Demo")
        self.assertEqual(job["timeline"][0]["id"], "queued")
        self.assertTrue(job["can_cancel"])

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
        self.assertTrue(job["can_retry"])
        self.assertEqual(job["timeline"][-1]["id"], "completed")

    def test_get_job_detail_hides_non_plan_running_result_payloads(self):
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
                    "job_progress_only",
                    self.user_id,
                    "orchestrate",
                    "running",
                    1.0,
                    2.0,
                    None,
                    "Engineering Run",
                    "Working",
                    48,
                    '{"prompt_text":"demo"}',
                    '{"job_progress":{"stage":"Engineering Run","detail":"Working","progress":48}}',
                    None,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        job = self.queue.get_job_detail(user_id=self.user_id, job_id="job_progress_only")
        self.assertIsNotNone(job)
        self.assertEqual(job["result"], {})

    def test_worker_recovers_queued_jobs_from_database_without_in_memory_queue(self):
        web_queue = JobQueueService(self.db, worker_count=0)
        created = web_queue.submit_job(
            user_id=self.user_id,
            job_type="orchestrate",
            payload={"prompt_text": "demo"},
        )
        worker_queue = JobQueueService(
            self.db,
            worker_count=1,
            resume_poll_interval_sec=0.05,
        )
        worker_queue.register_handler(
            "orchestrate",
            lambda job: {"success": True, "result": {"job_id": job["job_id"]}},
        )

        deadline = time.time() + 3.0
        record = None
        while time.time() < deadline:
            record = worker_queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
            if record and record["status"] == "completed":
                break
            time.sleep(0.05)

        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "completed")
        worker_queue._resume_pending_jobs = False
        worker_queue.db = Database(Path(tempfile.gettempdir()) / "civora_job_queue_recovery_teardown.db")

    def test_web_only_queue_is_completed_by_separate_worker_service(self):
        web_queue = JobQueueService(self.db, worker_count=0)
        web_queue.register_handler(
            "source_context_external_test",
            lambda job: {"success": True, "processed_by": "web"},
        )
        created = web_queue.submit_job(
            user_id=self.user_id,
            job_type="source_context_external_test",
            payload={"address": "20525 Margo St"},
        )

        self.assertEqual(created["status"], "queued")
        self.assertEqual(web_queue.runtime_stats()["execution_mode"], "external_worker")
        self.assertEqual(web_queue.runtime_stats()["alive_workers"], 0)

        worker_queue = JobQueueService(
            self.db,
            worker_count=1,
            heartbeat_interval_sec=0.5,
            resume_poll_interval_sec=0.05,
        )
        worker_queue.register_handler(
            "source_context_external_test",
            lambda job: {"success": True, "processed_by": "dedicated_worker"},
        )

        deadline = time.time() + 3.0
        record = None
        while time.time() < deadline:
            record = web_queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
            if record and record["status"] == "completed":
                break
            time.sleep(0.05)

        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["result"]["processed_by"], "dedicated_worker")
        worker_queue._resume_pending_jobs = False

    def test_web_queue_continuation_waits_for_external_worker_when_handler_is_disabled(self):
        web_queue = JobQueueService(self.db, worker_count=1)
        created = web_queue.submit_job(
            user_id=self.user_id,
            job_type="orchestrate_external_test",
            payload={"prompt_text": "review checkpoint"},
        )
        checkpoint_result = {
            "metadata": {
                "runtime_phase_checkpoint": {
                    "stage_name": "grading",
                    "message": "Grading checkpoint saved.",
                }
            },
            "job_progress": {
                "stage": "Awaiting Approval",
                "detail": "Review grading before continuing.",
                "progress": 60,
            },
        }
        web_queue._update_job_state(
            created["job_id"],
            status="awaiting_approval",
            result=checkpoint_result,
            error=None,
        )

        continued = web_queue.continue_job(user_id=self.user_id, job_id=created["job_id"])
        self.assertIsNotNone(continued)
        self.assertEqual(continued["status"], "queued")
        self.assertEqual(web_queue._queue.qsize(), 0)

        worker_queue = JobQueueService(
            self.db,
            worker_count=1,
            resume_poll_interval_sec=0.05,
        )
        worker_queue.register_handler(
            "orchestrate_external_test",
            lambda job: {"success": True, "processed_by": "isolated_worker", "job_id": job["job_id"]},
        )

        deadline = time.time() + 3.0
        record = None
        while time.time() < deadline:
            record = web_queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
            if record and record["status"] == "completed":
                break
            time.sleep(0.05)

        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["result"]["processed_by"], "isolated_worker")
        worker_queue._resume_pending_jobs = False

    def test_list_jobs_restarts_worker_if_thread_dies(self):
        self.queue._workers = []
        jobs = self.queue.list_jobs(user_id=self.user_id)
        self.assertEqual(jobs, [])
        self.assertTrue(self.queue._workers)
        self.assertTrue(all(worker.is_alive() for worker in self.queue._workers))

    def test_runtime_stats_flags_stale_running_jobs(self):
        old_time = time.time() - 2000.0
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
                    "job_stale",
                    self.user_id,
                    "orchestrate",
                    "running",
                    old_time,
                    old_time,
                    None,
                    "Engineering Run",
                    "No heartbeat",
                    48,
                    "{}",
                    "{}",
                    None,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        self.queue._job_timeout_seconds = 60.0
        stats = self.queue.runtime_stats()
        monitoring = stats["monitoring"]

        self.assertEqual(monitoring["status"], "critical")
        self.assertEqual(monitoring["stale_job_count"], 1)
        self.assertEqual(monitoring["stale_jobs"][0]["job_id"], "job_stale")
        self.assertIn("stale_or_timed_out_jobs_present", monitoring["warnings"])

    def test_runtime_stats_reports_pending_failed_and_stale_counts(self):
        old_time = time.time() - 2000.0
        connection = self.db.connect()
        try:
            for job_id, status, created_at, updated_at in (
                ("job_pending", "queued", time.time(), time.time()),
                ("job_failed", "failed", time.time(), time.time()),
                ("job_stale_running", "running", old_time, old_time),
            ):
                connection.execute(
                    """
                    INSERT INTO jobs (
                        job_id, user_id, job_type, status, created_at, updated_at, project_id,
                        stage, stage_detail, progress, payload_json, result_json, error_text
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        self.user_id,
                        "orchestrate",
                        status,
                        created_at,
                        updated_at,
                        None,
                        "Queued" if status == "queued" else "Running" if status == "running" else "Failed",
                        "Monitoring test",
                        12,
                        "{}",
                        "{}",
                        "failed" if status == "failed" else None,
                    ),
                )
            connection.commit()
        finally:
            connection.close()

        self.queue._job_timeout_seconds = 60.0
        monitoring = self.queue.runtime_stats()["monitoring"]

        self.assertEqual(monitoring["pending_count"], 1)
        self.assertEqual(monitoring["queued_count"], 1)
        self.assertEqual(monitoring["running_count"], 1)
        self.assertEqual(monitoring["failed_count"], 1)
        self.assertEqual(monitoring["failed_recent_count"], 1)
        self.assertEqual(monitoring["stale_job_count"], 1)

    def test_get_job_detail_marks_timed_out_job_failed_with_exact_blocker(self):
        old_time = time.time() - 2000.0
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
                    "job_timeout",
                    self.user_id,
                    "orchestrate",
                    "running",
                    old_time,
                    old_time,
                    None,
                    "Grading",
                    "Building proposed surface",
                    52,
                    "{}",
                    '{"job_progress":{"stage":"Grading","detail":"Building proposed surface","progress":52}}',
                    None,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        self.queue._job_timeout_seconds = 60.0
        job = self.queue.get_job_detail(user_id=self.user_id, job_id="job_timeout")

        self.assertIsNotNone(job)
        self.assertEqual(job["status"], "failed")
        self.assertIn("timed out after 60 seconds", job["error"])
        self.assertIn("Last stage: Grading", job["error"])
        self.assertEqual(job["stage"], "Timed Out")
        self.assertEqual(job["result"]["error_details"]["code"], "job_timeout")

    def test_runner_failure_preserves_stage_and_exact_error(self):
        def runner(_job):
            raise RuntimeError("grading surface missing terrain triangles")

        self.queue.register_handler("orchestrate", runner)
        created = self.queue.submit_job(
            user_id=self.user_id,
            job_type="orchestrate",
            payload={"prompt_text": "grading"},
        )

        deadline = time.time() + 3.0
        record = None
        while time.time() < deadline:
            record = self.queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
            if record and record["status"] == "failed":
                break
            time.sleep(0.05)

        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "failed")
        self.assertIn("Job failed during Preparing", record["error"])
        self.assertIn("grading surface missing terrain triangles", record["error"])
        self.assertEqual(record["result"]["error_details"]["code"], "job_runner_failed")

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

    def test_project_store_preserves_existing_latest_result_on_empty_save(self):
        store = ProjectStore(self.db)
        saved = store.save_project(
            user_id=self.user_id,
            project_id=None,
            name="Checkpoint Demo",
            latest_result={
                "final_plan": {
                    "project_name": "Checkpoint Demo",
                    "meta": {"phase_checkpoints": {"layout": {"status": "complete"}}},
                }
            },
        )

        store.save_project(
            user_id=self.user_id,
            project_id=saved["project_id"],
            name="Checkpoint Demo",
            latest_result={},
        )

        loaded = store.get_project_latest_result(
            user_id=self.user_id,
            project_id=saved["project_id"],
        )
        self.assertEqual(
            dict(loaded or {}).get("final_plan", {}).get("project_name"),
            "Checkpoint Demo",
        )

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

    def test_list_jobs_page_bounds_large_histories(self):
        connection = self.db.connect()
        try:
            for index in range(12):
                connection.execute(
                    """
                    INSERT INTO jobs (
                        job_id, user_id, job_type, status, created_at, updated_at, project_id,
                        stage, stage_detail, progress, payload_json, result_json, error_text
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"job_page_{index:02d}",
                        self.user_id,
                        "orchestrate",
                        "completed",
                        float(index + 1),
                        float(index + 1),
                        None,
                        "Completed",
                        "Done",
                        100,
                        "{}",
                        '{"job_progress":{"stage":"Completed","detail":"Done","progress":100}}',
                        None,
                    ),
                )
            connection.commit()
        finally:
            connection.close()

        page = self.queue.list_jobs_page(user_id=self.user_id, limit=5, offset=5)

        self.assertEqual(len(page["jobs"]), 5)
        self.assertEqual(page["pagination"]["total_count"], 12)
        self.assertTrue(page["pagination"]["has_more"])
        self.assertEqual(page["pagination"]["next_offset"], 10)
        self.assertEqual(page["jobs"][0]["job_id"], "job_page_06")
        self.assertEqual(page["jobs"][-1]["job_id"], "job_page_02")

    def test_cancel_queued_job_marks_cancelled_and_retryable(self):
        created = self.queue.submit_job(
            user_id=self.user_id,
            job_type="orchestrate",
            payload={"prompt_text": "cancel me"},
        )

        cancelled = self.queue.cancel_job(user_id=self.user_id, job_id=created["job_id"])
        self.assertIsNotNone(cancelled)
        self.assertEqual(cancelled["status"], "cancelled")

        detail = self.queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
        self.assertIsNotNone(detail)
        self.assertEqual(detail["status"], "cancelled")
        self.assertTrue(detail["can_retry"])
        self.assertEqual(detail["timeline"][-1]["id"], "cancelled")

    def test_cancel_review_hold_job_marks_cancelled_immediately(self):
        created = self.queue.submit_job(
            user_id=self.user_id,
            job_type="orchestrate",
            payload={"prompt_text": "cancel at review hold"},
        )
        self.queue._update_job_state(
            created["job_id"],
            status="awaiting_approval",
            result={
                "job_progress": {
                    "stage": "Awaiting Approval",
                    "detail": "Layout stage completed.",
                    "progress": 60,
                }
            },
            error=None,
        )

        cancelled = self.queue.cancel_job(user_id=self.user_id, job_id=created["job_id"])

        self.assertIsNotNone(cancelled)
        self.assertEqual(cancelled["status"], "cancelled")
        detail = self.queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
        self.assertIsNotNone(detail)
        self.assertEqual(detail["status"], "cancelled")
        self.assertEqual(detail["timeline"][-1]["id"], "cancelled")

    def test_retry_failed_job_creates_linked_queued_job_from_original_payload(self):
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
                    "job_failed_retry",
                    self.user_id,
                    "orchestrate",
                    "failed",
                    1.0,
                    2.0,
                    None,
                    "Failed",
                    "Bad input",
                    42,
                    '{"prompt_text":"retry source"}',
                    '{"job_progress":{"stage":"Failed","detail":"Bad input","progress":42}}',
                    "Bad input",
                ),
            )
            connection.commit()
        finally:
            connection.close()

        retried = self.queue.retry_job(user_id=self.user_id, job_id="job_failed_retry")
        self.assertIsNotNone(retried)
        self.assertNotEqual(retried["job_id"], "job_failed_retry")
        self.assertEqual(retried["status"], "queued")
        self.assertEqual(retried["retry_of_job_id"], "job_failed_retry")

        retry_detail = self.queue.get_job_detail(user_id=self.user_id, job_id=retried["job_id"])
        self.assertEqual(retry_detail["payload"]["prompt_text"], "retry source")
        self.assertEqual(retry_detail["payload"]["meta"]["retry_of_job_id"], "job_failed_retry")

    def test_worker_waits_for_approval_after_partial_runtime_phase_result(self):
        call_count = {"value": 0}

        def runner(job):
            call_count["value"] += 1
            if call_count["value"] == 1:
                return {
                    "success": True,
                    "final_plan": {
                        "project_name": "Demo",
                        "meta": {
                            "runtime_phase_checkpoint": {
                                "stage_name": "layout",
                                "message": "Layout checkpoint saved.",
                                "yielded": True,
                            }
                        },
                    },
                    "metadata": {
                        "runtime_should_continue": True,
                        "runtime_phase_checkpoint": {
                            "stage_name": "layout",
                            "message": "Layout checkpoint saved.",
                            "yielded": True,
                        },
                    },
                }
            return {
                "success": True,
                "final_plan": {"project_name": "Demo", "meta": {}},
                "metadata": {},
            }

        self.queue.register_handler("orchestrate", runner)
        created = self.queue.submit_job(
            user_id=self.user_id,
            job_type="orchestrate",
            payload={"prompt_text": "resume"},
        )

        record = None
        deadline = time.time() + 4.0
        while time.time() < deadline:
            record = self.queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
            if record and record["status"] == "awaiting_approval":
                break
            time.sleep(0.05)

        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "awaiting_approval")
        self.assertEqual(call_count["value"], 1)
        self.assertEqual(record["stage"], "Awaiting Approval")
        self.assertIn("Review it and approve", record["stage_detail"])

    def test_continue_job_requeues_saved_phase_after_approval(self):
        call_count = {"value": 0}

        def runner(job):
            call_count["value"] += 1
            if call_count["value"] == 1:
                return {
                    "success": True,
                    "final_plan": {
                        "project_name": "Demo",
                        "meta": {
                            "runtime_phase_checkpoint": {
                                "stage_name": "layout",
                                "message": "Layout checkpoint saved.",
                                "yielded": True,
                            }
                        },
                    },
                    "metadata": {
                        "runtime_should_continue": True,
                        "runtime_phase_checkpoint": {
                            "stage_name": "layout",
                            "message": "Layout checkpoint saved.",
                            "yielded": True,
                        },
                    },
                }
            return {
                "success": True,
                "final_plan": {"project_name": "Demo", "meta": {}},
                "metadata": {},
            }

        self.queue.register_handler("orchestrate", runner)
        created = self.queue.submit_job(
            user_id=self.user_id,
            job_type="orchestrate",
            payload={"prompt_text": "resume"},
        )

        waiting = None
        deadline = time.time() + 4.0
        while time.time() < deadline:
            waiting = self.queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
            if waiting and waiting["status"] == "awaiting_approval":
                break
            time.sleep(0.05)

        self.assertIsNotNone(waiting)
        self.assertEqual(waiting["status"], "awaiting_approval")
        self.assertEqual(
            waiting["result"]["metadata"]["runtime_phase_checkpoint"]["stage_name"],
            "layout",
        )
        continued = self.queue.continue_job(user_id=self.user_id, job_id=created["job_id"])
        self.assertIsNotNone(continued)
        self.assertIn(continued["status"], {"queued", "running"})

        queued_detail = self.queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
        self.assertIsNotNone(queued_detail)
        self.assertEqual(
            queued_detail["result"]["metadata"]["runtime_phase_checkpoint"]["stage_name"],
            "layout",
        )
        self.assertIn(
            queued_detail["result"]["job_progress"]["stage"],
            {"Queued Next Phase", "Preparing"},
        )

        record = None
        deadline = time.time() + 4.0
        while time.time() < deadline:
            record = self.queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
            if record and record["status"] == "completed":
                break
            time.sleep(0.05)

        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(call_count["value"], 2)

    def test_in_process_worker_start_is_deferred_until_after_queue_acknowledgement(self):
        started = threading.Event()
        queue = JobQueueService(
            self.db,
            worker_count=1,
            in_process_start_delay_sec=0.2,
        )
        queue.register_handler(
            "orchestrate",
            lambda _job: started.set() or {"success": True},
        )

        submitted = queue.submit_job(
            user_id=self.user_id,
            job_type="orchestrate",
            payload={"prompt_text": "deferred start"},
        )

        self.assertEqual(submitted["status"], "queued")
        self.assertFalse(started.wait(timeout=0.05))
        self.assertTrue(started.wait(timeout=1.0))

    def test_revise_job_requeues_saved_phase_with_updated_payload(self):
        call_payloads = []

        def runner(job):
            call_payloads.append(dict(job.get("payload") or {}))
            if len(call_payloads) == 1:
                return {
                    "success": True,
                    "final_plan": {
                        "project_name": "Demo",
                        "meta": {
                            "runtime_phase_checkpoint": {
                                "stage_name": "grading",
                                "message": "Grading checkpoint saved.",
                                "yielded": True,
                            }
                        },
                    },
                    "metadata": {
                        "runtime_should_continue": True,
                        "runtime_phase_checkpoint": {
                            "stage_name": "grading",
                            "message": "Grading checkpoint saved.",
                            "yielded": True,
                        },
                    },
                }
            return {
                "success": True,
                "final_plan": {"project_name": "Demo", "meta": {}},
                "metadata": {},
            }

        self.queue.register_handler("orchestrate", runner)
        created = self.queue.submit_job(
            user_id=self.user_id,
            job_type="orchestrate",
            payload={"prompt_text": "old prompt"},
        )

        waiting = None
        deadline = time.time() + 4.0
        while time.time() < deadline:
            waiting = self.queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
            if waiting and waiting["status"] == "awaiting_approval":
                break
            time.sleep(0.05)

        self.assertIsNotNone(waiting)
        self.assertEqual(
            waiting["result"]["metadata"]["runtime_phase_checkpoint"]["stage_name"],
            "grading",
        )
        revised = self.queue.revise_job(
            user_id=self.user_id,
            job_id=created["job_id"],
            payload={"prompt_text": "new prompt"},
        )
        self.assertIsNotNone(revised)
        self.assertIn(revised["status"], {"queued", "running"})

        queued_detail = self.queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
        self.assertIsNotNone(queued_detail)
        self.assertEqual(
            queued_detail["result"]["metadata"]["runtime_phase_checkpoint"]["stage_name"],
            "grading",
        )
        self.assertIn(
            queued_detail["result"]["job_progress"]["stage"],
            {"Queued Phase Revision", "Preparing"},
        )

        record = None
        deadline = time.time() + 4.0
        while time.time() < deadline:
            record = self.queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
            if record and record["status"] == "completed":
                break
            time.sleep(0.05)

        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(call_payloads[0]["prompt_text"], "old prompt")
        self.assertEqual(call_payloads[-1]["prompt_text"], "new prompt")

    def test_worker_does_not_auto_continue_partial_runtime_phase_results_without_approval(self):
        class NoDbScanJobQueueService(JobQueueService):
            def _find_next_pending_job_id(self):
                return None

        queue = NoDbScanJobQueueService(self.db)
        call_count = {"value": 0}

        def runner(job):
            call_count["value"] += 1
            if call_count["value"] == 1:
                return {
                    "success": True,
                    "final_plan": {
                        "project_name": "Demo",
                        "meta": {
                            "runtime_phase_checkpoint": {
                                "stage_name": "layout",
                                "message": "Layout checkpoint saved.",
                                "yielded": True,
                            }
                        },
                    },
                    "metadata": {
                        "runtime_should_continue": True,
                        "runtime_phase_checkpoint": {
                            "stage_name": "layout",
                            "message": "Layout checkpoint saved.",
                            "yielded": True,
                        },
                    },
                }
            return {
                "success": True,
                "final_plan": {"project_name": "Demo", "meta": {}},
                "metadata": {},
            }

        queue.register_handler("orchestrate", runner)
        created = queue.submit_job(
            user_id=self.user_id,
            job_type="orchestrate",
            payload={"prompt_text": "resume"},
        )

        record = None
        deadline = time.time() + 4.0
        while time.time() < deadline:
            record = queue.get_job_detail(user_id=self.user_id, job_id=created["job_id"])
            if record and record["status"] == "awaiting_approval":
                break
            time.sleep(0.05)

        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "awaiting_approval")
        self.assertEqual(call_count["value"], 1)


if __name__ == "__main__":
    unittest.main()
