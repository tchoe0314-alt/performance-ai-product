from __future__ import annotations

from queue import Empty, Queue
from typing import Any, Callable, Dict, List, Optional
from dataclasses import asdict, is_dataclass
from enum import Enum
import json
import threading
import time
import uuid

from .database import Database


JobRunner = Callable[[Dict[str, Any]], Dict[str, Any]]


class JobCancelledError(RuntimeError):
    pass


def _now() -> float:
    return time.time()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        try:
            return _json_safe(value.to_dict())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return _json_safe(vars(value))
        except Exception:
            pass
    return str(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(_json_safe(value if value is not None else {}))


def _json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _job_progress_payload(stage: str, detail: str, progress: int) -> Dict[str, Any]:
    return {
        "job_progress": {
            "stage": str(stage or "").strip(),
            "detail": str(detail or "").strip(),
            "progress": max(0, min(100, int(progress))),
        }
    }


class JobQueueService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._queue: Queue[str] = Queue()
        self._handlers: Dict[str, JobRunner] = {}
        self._lock = threading.Lock()
        self._worker: Optional[threading.Thread] = None
        self._ensure_worker_alive()

    def _ensure_worker_alive(self) -> None:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(target=self._run_worker, name="performance-ai-job-worker", daemon=True)
            self._worker.start()

    def register_handler(self, job_type: str, runner: JobRunner) -> None:
        self._handlers[job_type] = runner
        self._ensure_worker_alive()
        self._enqueue_pending_jobs(job_type)

    def submit_job(
        self,
        *,
        user_id: str,
        job_type: str,
        payload: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._ensure_worker_alive()
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
            "result": _job_progress_payload("Queued", "Waiting for a worker to pick up the job.", 12),
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

        if job_type in self._handlers:
            self._queue.put(record["job_id"])
        return self._job_summary(record)

    def list_jobs(self, *, user_id: str) -> List[Dict[str, Any]]:
        self._ensure_worker_alive()
        connection = self.db.connect()
        try:
            rows = connection.execute(
                """
                SELECT *
                FROM jobs
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
            return [
                self._job_summary(self._row_to_record(row))
                for row in rows
            ]
        finally:
            connection.close()

    def get_job(self, *, user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_worker_alive()
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

    def get_job_detail(self, *, user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        record = self.get_job(user_id=user_id, job_id=job_id)
        if record is None:
            return None
        detail = self._job_summary(record)
        detail.update(
            {
                "payload": record.get("payload") or {},
                "result": record.get("result") or {},
            }
        )
        return detail

    def cancel_job(self, *, user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_worker_alive()
        record = self.get_job(user_id=user_id, job_id=job_id)
        if record is None:
            return None
        if record["status"] in {"completed", "failed", "cancelled"}:
            return self._job_summary(record)

        result = dict(record.get("result") or {})
        result.update(
            _job_progress_payload(
                "Cancelling",
                "Cancellation requested. Civora is stopping this job as soon as it can.",
                max(0, int(((record.get("result") or {}).get("job_progress") or {}).get("progress") or 0)),
            )
        )
        next_status = "cancelled" if record["status"] == "queued" else "cancelling"
        error = "Cancelled by user."
        self._update_job_state(job_id, status=next_status, result=result, error=error)
        updated = self.get_job(user_id=user_id, job_id=job_id)
        return None if updated is None else self._job_summary(updated)

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

    def _find_next_pending_job_id(self) -> Optional[str]:
        if not self._handlers:
            return None
        job_types = sorted(self._handlers.keys())
        placeholders = ",".join("?" for _ in job_types)
        connection = self.db.connect()
        try:
            row = connection.execute(
                f"""
                SELECT job_id
                FROM jobs
                WHERE status = 'queued' AND job_type IN ({placeholders})
                ORDER BY created_at ASC
                LIMIT 1
                """,
                tuple(job_types),
            ).fetchone()
            if row is None:
                return None
            return str(row["job_id"])
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

    def update_job_progress(self, job_id: str, *, stage: str, detail: str, progress: int) -> None:
        current = self._get_job_for_worker(job_id)
        if current is None:
            return
        if current.get("status") in {"cancelling", "cancelled"}:
            raise JobCancelledError("Cancelled by user.")
        merged_result = dict(current.get("result") or {})
        merged_result.update(_job_progress_payload(stage, detail, progress))
        self._update_job_state(job_id, status="running", result=merged_result, error=None)

    def _job_summary(self, record: Dict[str, Any]) -> Dict[str, Any]:
        job_progress = dict((record.get("result") or {}).get("job_progress") or {})
        try:
            progress = int(job_progress.get("progress") or 0)
        except Exception:
            progress = 0
        return {
            "job_id": record["job_id"],
            "job_type": record["job_type"],
            "status": record["status"],
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
            "project_id": record["project_id"],
            "error": record["error"],
            "stage": str(job_progress.get("stage") or ""),
            "stage_detail": str(job_progress.get("detail") or ""),
            "progress": progress,
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
                job_id = self._find_next_pending_job_id()
                if not job_id:
                    continue
                queue_task = False
            else:
                queue_task = True

            job = self._get_job_for_worker(job_id)
            if job is None:
                if queue_task:
                    self._queue.task_done()
                continue
            if job["status"] == "cancelled":
                if queue_task:
                    self._queue.task_done()
                continue

            runner = self._handlers.get(job["job_type"])
            if runner is None:
                self._update_job_state(job_id, status="failed", error=f"No handler registered for job type '{job['job_type']}'.")
                if queue_task:
                    self._queue.task_done()
                continue

            self._update_job_state(job_id, status="running", error=None)
            try:
                self.update_job_progress(
                    job_id,
                    stage="Preparing",
                    detail="Validating the request and preparing the engineering run.",
                    progress=24,
                )
                result = runner(job)
                current = self._get_job_for_worker(job_id)
                if current and current.get("status") in {"cancelling", "cancelled"}:
                    cancelled_result = dict(current.get("result") or {})
                    cancelled_result.update(
                        _job_progress_payload(
                            "Cancelled",
                            "This run was cancelled before the result was returned.",
                            int(((cancelled_result.get("job_progress") or {}).get("progress") or 0)),
                        )
                    )
                    self._update_job_state(job_id, status="cancelled", result=cancelled_result, error="Cancelled by user.")
                else:
                    self._update_job_state(job_id, status="completed", result=result, error=None)
            except JobCancelledError:
                current = self._get_job_for_worker(job_id)
                cancelled_result = dict((current or {}).get("result") or {})
                cancelled_result.update(
                    _job_progress_payload(
                        "Cancelled",
                        "This run was cancelled before completion.",
                        int(((cancelled_result.get("job_progress") or {}).get("progress") or 0)),
                    )
                )
                self._update_job_state(job_id, status="cancelled", result=cancelled_result, error="Cancelled by user.")
            except Exception as exc:
                self._update_job_state(job_id, status="failed", result={}, error=str(exc))
            finally:
                if queue_task:
                    self._queue.task_done()
