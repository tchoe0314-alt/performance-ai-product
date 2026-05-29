from __future__ import annotations

from queue import Empty, Queue
from typing import Any, Callable, Dict, List, Optional
from dataclasses import asdict, is_dataclass
from enum import Enum
import json
import os
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


def _coerce_progress(progress: Any) -> int:
    try:
        return max(0, min(100, int(progress or 0)))
    except Exception:
        return 0


class JobQueueService:
    def __init__(
        self,
        db: Database,
        *,
        heartbeat_interval_sec: float = 10.0,
        worker_count: Optional[int] = None,
    ) -> None:
        self.db = db
        self._queue: Queue[str] = Queue()
        self._handlers: Dict[str, JobRunner] = {}
        self._lock = threading.Lock()
        raw_worker_count = str(os.getenv("PERFORMANCE_AI_JOB_WORKERS") or "").strip()
        if worker_count is None:
            try:
                worker_count = int(raw_worker_count) if raw_worker_count else 1
            except Exception:
                worker_count = 1
        self._worker_count = max(1, int(worker_count or 1))
        resume_setting = str(os.getenv("PERFORMANCE_AI_RESUME_PENDING_JOBS") or "true").strip().lower()
        self._resume_pending_jobs = resume_setting not in {"0", "false", "no", "off"}
        self._workers: List[threading.Thread] = []
        self._heartbeat_interval_sec = max(0.5, float(heartbeat_interval_sec or 10.0))
        self._ensure_workers_alive()

    def _ensure_workers_alive(self) -> None:
        with self._lock:
            self._workers = [worker for worker in self._workers if worker.is_alive()]
            while len(self._workers) < self._worker_count:
                worker_index = len(self._workers) + 1
                worker = threading.Thread(
                    target=self._run_worker,
                    name=f"performance-ai-job-worker-{worker_index}",
                    daemon=True,
                )
                worker.start()
                self._workers.append(worker)

    def register_handler(self, job_type: str, runner: JobRunner) -> None:
        self._handlers[job_type] = runner
        self._ensure_workers_alive()
        if self._resume_pending_jobs:
            self._enqueue_pending_jobs(job_type)

    def runtime_stats(self) -> Dict[str, Any]:
        self._ensure_workers_alive()
        return {
            "worker_count": self._worker_count,
            "alive_workers": len([worker for worker in self._workers if worker.is_alive()]),
            "queued_in_memory": self._queue.qsize(),
            "resume_pending_jobs": self._resume_pending_jobs,
            "registered_handlers": sorted(self._handlers.keys()),
        }

    def submit_job(
        self,
        *,
        user_id: str,
        job_type: str,
        payload: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._ensure_workers_alive()
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
        job_progress = dict((record["result"] or {}).get("job_progress") or {})

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
                    record["job_id"],
                    record["user_id"],
                    record["job_type"],
                    record["status"],
                    record["created_at"],
                    record["updated_at"],
                    record["project_id"],
                    str(job_progress.get("stage") or ""),
                    str(job_progress.get("detail") or ""),
                    _coerce_progress(job_progress.get("progress")),
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
        self._ensure_workers_alive()
        connection = self.db.connect()
        try:
            rows = connection.execute(
                """
                SELECT job_id, job_type, status, created_at, updated_at, project_id, stage, stage_detail, progress, error_text
                FROM jobs
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
            queue_stats = self._queue_stats(connection, user_id=user_id)
            return [
                self._job_summary(self._row_to_record(row), queue_stats=queue_stats)
                for row in rows
            ]
        finally:
            connection.close()

    def get_job(self, *, user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_workers_alive()
        connection = self.db.connect()
        try:
            row = connection.execute(
                """
                SELECT job_id, user_id, job_type, status, created_at, updated_at, project_id, stage, stage_detail, progress, error_text
                FROM jobs
                WHERE user_id = ? AND job_id = ?
                """,
                (user_id, job_id),
            ).fetchone()
            return None if row is None else self._row_to_record(row)
        finally:
            connection.close()

    def get_job_detail(self, *, user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
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
        finally:
            connection.close()
        record = None if row is None else self._row_to_record(row)
        if record is None:
            return None
        connection = self.db.connect()
        try:
            queue_stats = self._queue_stats(connection, user_id=user_id)
        finally:
            connection.close()
        detail = self._job_summary(record, queue_stats=queue_stats)
        result_payload: Dict[str, Any] = {}
        candidate_result = dict(record.get("result") or {})
        candidate_metadata = dict(candidate_result.get("metadata") or {})
        has_partial_plan = bool(
            dict(candidate_result.get("final_plan") or {})
            or candidate_metadata.get("run_summary")
            or dict(candidate_result.get("job_progress") or {}).get("partial_result_ready")
            or candidate_metadata.get("runtime_phase_checkpoint")
        )
        if record["status"] in {"completed", "failed", "cancelled"} or has_partial_plan:
            result_payload = candidate_result
        detail.update(
            {
                "payload": record.get("payload") or {},
                "result": result_payload,
            }
        )
        return detail

    def delete_jobs_for_project(self, *, user_id: str, project_id: str) -> int:
        connection = self.db.connect()
        try:
            cursor = connection.execute(
                "DELETE FROM jobs WHERE user_id = ? AND project_id = ?",
                (user_id, project_id),
            )
            connection.commit()
            return cursor.rowcount
        finally:
            connection.close()

    def cancel_job(self, *, user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_workers_alive()
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

    def continue_job(self, *, user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_workers_alive()
        record = self.get_job_detail(user_id=user_id, job_id=job_id)
        if record is None:
            return None
        if record["status"] != "awaiting_approval":
            return self._job_summary(record)

        result = dict(record.get("result") or {})
        checkpoint = dict(dict(result.get("metadata") or {}).get("runtime_phase_checkpoint") or {})
        stage_name = str(checkpoint.get("stage_name") or "").strip()
        detail = (
            f"Approval received. Queued the next engineering phase after {stage_name or 'the saved'} checkpoint."
        )
        result.update(_job_progress_payload("Queued Next Phase", detail, 64))
        self._update_job_state(job_id, status="queued", result=result, error=None)
        updated = self.get_job(user_id=user_id, job_id=job_id)
        summary = None if updated is None else self._job_summary(updated)
        self._queue.put(job_id)
        return summary

    def revise_job(
        self,
        *,
        user_id: str,
        job_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        self._ensure_workers_alive()
        record = self.get_job_detail(user_id=user_id, job_id=job_id)
        if record is None:
            return None
        if record["status"] != "awaiting_approval":
            return self._job_summary(record)

        result = dict(record.get("result") or {})
        checkpoint = dict(dict(result.get("metadata") or {}).get("runtime_phase_checkpoint") or {})
        stage_name = str(checkpoint.get("stage_name") or "").strip()
        detail = (
            f"Revision requested. Queued {stage_name or 'current'} phase again with your latest changes."
        )
        result.update(_job_progress_payload("Queued Phase Revision", detail, 62))
        if payload is not None:
            self._update_job_payload(job_id, payload)
        self._update_job_state(job_id, status="queued", result=result, error=None)
        updated = self.get_job(user_id=user_id, job_id=job_id)
        summary = None if updated is None else self._job_summary(updated)
        self._queue.put(job_id)
        return summary

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
                        """
                        UPDATE jobs
                        SET status = ?, updated_at = ?, error_text = ?, stage = ?, stage_detail = ?, progress = ?
                        WHERE job_id = ?
                        """,
                        ("queued", _now(), "Recovered after process restart.", "Queued", "Recovered after process restart.", 12, row["job_id"]),
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

    def _claim_job_for_worker(self, job_id: str) -> Optional[Dict[str, Any]]:
        current = self._get_job_for_worker(job_id)
        if current is None:
            return None
        if current.get("status") == "cancelled":
            return current
        if current.get("status") != "queued":
            return None
        connection = self.db.connect()
        try:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = ?, updated_at = ?
                WHERE job_id = ? AND status = 'queued'
                """,
                ("running", _now(), job_id),
            )
            connection.commit()
            if int(getattr(cursor, "rowcount", 0) or 0) <= 0:
                return None
        finally:
            connection.close()
        return self._get_job_for_worker(job_id)

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
        job_progress = dict((result or {}).get("job_progress") or {})
        connection = self.db.connect()
        try:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, updated_at = ?, stage = ?, stage_detail = ?, progress = ?, result_json = ?, error_text = ?
                WHERE job_id = ?
                """,
                (
                    status,
                    _now(),
                    str(job_progress.get("stage") or ""),
                    str(job_progress.get("detail") or ""),
                    _coerce_progress(job_progress.get("progress")),
                    _json_dumps(result or {}),
                    error,
                    job_id,
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def _update_job_payload(self, job_id: str, payload: Dict[str, Any]) -> None:
        connection = self.db.connect()
        try:
            connection.execute(
                """
                UPDATE jobs
                SET payload_json = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (
                    _json_dumps(payload or {}),
                    _now(),
                    job_id,
                ),
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

    def _touch_job_activity(self, job_id: str) -> bool:
        current = self._get_job_for_worker(job_id)
        if current is None:
            return False
        status = str(current.get("status") or "")
        if status not in {"running", "cancelling"}:
            return False
        connection = self.db.connect()
        try:
            connection.execute(
                """
                UPDATE jobs
                SET updated_at = ?
                WHERE job_id = ? AND status IN ('running', 'cancelling')
                """,
                (_now(), job_id),
            )
            connection.commit()
        finally:
            connection.close()
        return True

    def _heartbeat_loop(self, job_id: str, stop_event: threading.Event) -> None:
        while not stop_event.wait(self._heartbeat_interval_sec):
            if not self._touch_job_activity(job_id):
                break

    def _queue_stats(self, connection: Any, *, user_id: str) -> Dict[str, Any]:
        running_count = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM jobs
                WHERE user_id = ? AND status = 'running'
                """,
                (user_id,),
            ).fetchone()[0]
        )
        queued_rows = connection.execute(
            """
            SELECT job_id
            FROM jobs
            WHERE user_id = ? AND status = 'queued'
            ORDER BY created_at ASC
            """,
            (user_id,),
        ).fetchall()
        queued_ids = [str(row["job_id"]) for row in queued_rows]
        return {
            "running_count": running_count,
            "queued_count": len(queued_ids),
            "queued_positions": {job_id: index + 1 for index, job_id in enumerate(queued_ids)},
        }

    def _job_summary(self, record: Dict[str, Any], *, queue_stats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        job_progress = dict((record.get("result") or {}).get("job_progress") or {})
        stage = str(record.get("stage") or job_progress.get("stage") or "")
        stage_detail = str(record.get("stage_detail") or job_progress.get("detail") or "")
        progress = _coerce_progress(record.get("progress"))
        if progress == 0 and job_progress:
            progress = _coerce_progress(job_progress.get("progress"))
        queue_position = None
        queued_count = 0
        running_count = 0
        if queue_stats:
            queued_positions = dict(queue_stats.get("queued_positions") or {})
            queue_position = queued_positions.get(record["job_id"])
            queued_count = int(queue_stats.get("queued_count") or 0)
            running_count = int(queue_stats.get("running_count") or 0)
        return {
            "job_id": record["job_id"],
            "job_type": record["job_type"],
            "status": record["status"],
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
            "project_id": record["project_id"],
            "error": record["error"],
            "stage": stage,
            "stage_detail": stage_detail,
            "progress": progress,
            "queue_position": queue_position,
            "queued_count": queued_count,
            "running_count": running_count,
        }

    def _row_to_record(self, row: Any) -> Dict[str, Any]:
        keys = set(row.keys())
        return {
            "job_id": row["job_id"],
            "user_id": row["user_id"] if "user_id" in keys else None,
            "job_type": row["job_type"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "project_id": row["project_id"] if "project_id" in keys else None,
            "stage": row["stage"] if "stage" in keys else "",
            "stage_detail": row["stage_detail"] if "stage_detail" in keys else "",
            "progress": row["progress"] if "progress" in keys else 0,
            "payload": _json_loads(row["payload_json"], {}) if "payload_json" in keys else {},
            "result": _json_loads(row["result_json"], {}) if "result_json" in keys else {},
            "error": row["error_text"] if "error_text" in keys else None,
        }

    def _run_worker(self) -> None:
        while True:
            try:
                job_id = self._queue.get(timeout=0.25)
            except Empty:
                if not self._resume_pending_jobs:
                    continue
                job_id = self._find_next_pending_job_id()
                if not job_id:
                    continue
                queue_task = False
            else:
                queue_task = True

            job = self._claim_job_for_worker(job_id)
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

            heartbeat_stop = threading.Event()
            heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                args=(job_id, heartbeat_stop),
                name=f"performance-ai-job-heartbeat-{job_id}",
                daemon=True,
            )
            heartbeat_thread.start()
            try:
                self.update_job_progress(
                    job_id,
                    stage="Preparing",
                    detail="Validating the request and preparing the engineering run.",
                    progress=24,
                )
                result = runner(job)
                runtime_should_continue = bool(
                    dict((result or {}).get("metadata") or {}).get("runtime_should_continue")
                )
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
                elif runtime_should_continue:
                    checkpoint = dict(
                        dict((result or {}).get("metadata") or {}).get("runtime_phase_checkpoint") or {}
                    )
                    stage_name = str(checkpoint.get("stage_name") or "").strip()
                    checkpoint_message = str(checkpoint.get("message") or "").strip()
                    detail = (
                        f"{checkpoint_message} Review it and approve when you want to continue."
                        if checkpoint_message
                        else f"Saved {stage_name or 'current'} checkpoint. Review it and approve when you want to continue."
                    )
                    awaiting_result = dict(result or {})
                    awaiting_result.update(
                        _job_progress_payload(
                            "Awaiting Approval",
                            detail,
                            60,
                        )
                    )
                    self._update_job_state(job_id, status="awaiting_approval", result=awaiting_result, error=None)
                else:
                    previous_result = dict((current or {}).get("result") or {})
                    previous_metadata = dict(previous_result.get("metadata") or {})
                    result_payload = dict(result or {})
                    result_metadata = dict(result_payload.get("metadata") or {})
                    if previous_metadata.get("runtime_phase_checkpoint") and not result_metadata.get("runtime_phase_checkpoint"):
                        result_metadata["runtime_phase_checkpoint"] = previous_metadata.get("runtime_phase_checkpoint")
                        result_payload["metadata"] = result_metadata
                        result = result_payload
                    if previous_result.get("job_progress") and not result_payload.get("job_progress"):
                        result_payload["job_progress"] = previous_result.get("job_progress")
                        result = result_payload
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
                heartbeat_stop.set()
                heartbeat_thread.join(timeout=1.0)
                if queue_task:
                    self._queue.task_done()
