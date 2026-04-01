from __future__ import annotations

from queue import Empty, Queue
from typing import Any, Callable, Dict, List, Optional
import json
import threading
import time
import uuid

from .database import Database


JobRunner = Callable[[Dict[str, Any]], Dict[str, Any]]


def _now() -> float:
    return time.time()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {})


def _json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


class JobQueueService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._queue: Queue[str] = Queue()
        self._handlers: Dict[str, JobRunner] = {}
        self._lock = threading.Lock()
        self._worker = threading.Thread(target=self._run_worker, name="performance-ai-job-worker", daemon=True)
        self._worker.start()

    def register_handler(self, job_type: str, runner: JobRunner) -> None:
        self._handlers[job_type] = runner
        self._enqueue_pending_jobs(job_type)

    def submit_job(
        self,
        *,
        user_id: str,
        job_type: str,
        payload: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = _now()
        record = {
            "job_id": _new_id("job"),
            "user_id": user_id,
            "job_type": job_type,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "project_id": project_id,
            "payload": dict(payload),
            "result": {},
            "error": None,
        }

        connection = self.db.connect()
        try:
            connection.execute(
                """
                INSERT INTO jobs (job_id, user_id, job_type, status, created_at, updated_at, project_id, payload_json, result_json, error_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["job_id"],
                    record["user_id"],
                    record["job_type"],
                    record["status"],
                    record["created_at"],
                    record["updated_at"],
                    record["project_id"],
                    _json_dumps(record["payload"]),
                    _json_dumps(record["result"]),
                    record["error"],
                ),
            )
            connection.commit()
        finally:
            connection.close()

        self._queue.put(record["job_id"])
        return self._job_summary(record)

    def list_jobs(self, *, user_id: str) -> List[Dict[str, Any]]:
        connection = self.db.connect()
        try:
            rows = connection.execute(
                """
                SELECT job_id, job_type, status, created_at, updated_at, project_id, error_text
                FROM jobs
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
            return [
                {
                    "job_id": row["job_id"],
                    "job_type": row["job_type"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "project_id": row["project_id"],
                    "error": row["error_text"],
                }
                for row in rows
            ]
        finally:
            connection.close()

    def get_job(self, *, user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        connection = self.db.connect()
        try:
            row = connection.execute(
                """
                SELECT *
                FROM jobs
                WHERE user_id = ? AND job_id = ?
                """,
                (user_id, job_id),
            ).fetchone()
            return None if row is None else self._row_to_record(row)
        finally:
            connection.close()

    def _enqueue_pending_jobs(self, job_type: str) -> None:
        connection = self.db.connect()
        try:
            rows = connection.execute(
                """
                SELECT job_id, status
                FROM jobs
                WHERE job_type = ? AND status IN ('queued', 'running')
                ORDER BY created_at ASC
                """,
                (job_type,),
            ).fetchall()
            for row in rows:
                if row["status"] == "running":
                    connection.execute(
                        "UPDATE jobs SET status = ?, updated_at = ?, error_text = ? WHERE job_id = ?",
                        ("queued", _now(), "Recovered after process restart.", row["job_id"]),
                    )
                self._queue.put(row["job_id"])
            connection.commit()
        finally:
            connection.close()

    def _get_job_for_worker(self, job_id: str) -> Optional[Dict[str, Any]]:
        connection = self.db.connect()
        try:
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            return None if row is None else self._row_to_record(row)
        finally:
            connection.close()

    def _update_job_state(self, job_id: str, *, status: str, result: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> None:
        connection = self.db.connect()
        try:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, updated_at = ?, result_json = ?, error_text = ?
                WHERE job_id = ?
                """,
                (status, _now(), _json_dumps(result or {}), error, job_id),
            )
            connection.commit()
        finally:
            connection.close()

    def _job_summary(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "job_id": record["job_id"],
            "job_type": record["job_type"],
            "status": record["status"],
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
            "project_id": record["project_id"],
            "error": record["error"],
        }

    def _row_to_record(self, row: Any) -> Dict[str, Any]:
        return {
            "job_id": row["job_id"],
            "user_id": row["user_id"],
            "job_type": row["job_type"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "project_id": row["project_id"],
            "payload": _json_loads(row["payload_json"], {}),
            "result": _json_loads(row["result_json"], {}),
            "error": row["error_text"],
        }

    def _run_worker(self) -> None:
        while True:
            try:
                job_id = self._queue.get(timeout=0.25)
            except Empty:
                continue

            job = self._get_job_for_worker(job_id)
            if job is None:
                self._queue.task_done()
                continue

            runner = self._handlers.get(job["job_type"])
            if runner is None:
                self._update_job_state(job_id, status="failed", error=f"No handler registered for job type '{job['job_type']}'.")
                self._queue.task_done()
                continue

            self._update_job_state(job_id, status="running", error=None)
            try:
                result = runner(job)
                self._update_job_state(job_id, status="completed", result=result, error=None)
            except Exception as exc:
                self._update_job_state(job_id, status="failed", result={}, error=str(exc))
            finally:
                self._queue.task_done()
