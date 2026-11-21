import json
import logging
import threading
import time
from pathlib import Path

import pytest

from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.job_queue import JobQueueService


def _awaiting_job(tmp_path: Path):
    db = Database(tmp_path / "jobs.db")
    auth = AuthStore(db)
    user_id = auth.register_user(
        email="approval-atomicity@example.com",
        password="password123",
        name="Approval Atomicity",
    )["user"]["user_id"]
    queue = JobQueueService(db, worker_count=0)
    created = queue.submit_job(
        user_id=user_id,
        job_type="orchestrate",
        payload={"meta": {"orchestrator_meta": {}}},
    )
    queue._update_job_state(
        created["job_id"],
        status="awaiting_approval",
        result={
            "metadata": {
                "runtime_phase_checkpoint": {
                    "stage_name": "sanitary",
                    "message": "Sanitary checkpoint saved.",
                    "yielded": True,
                }
            }
        },
        error=None,
    )
    return db, queue, user_id, created["job_id"]


class _FailStatusUpdateConnection:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, params=()):
        normalized = " ".join(str(sql).split()).lower()
        if normalized.startswith("update jobs set") and "status =" in normalized:
            raise RuntimeError("synthetic transition failure")
        return self._connection.execute(sql, params)

    def __getattr__(self, name):
        return getattr(self._connection, name)


def test_continue_failure_cannot_persist_approval_without_queue_transition(tmp_path, monkeypatch):
    db, queue, user_id, job_id = _awaiting_job(tmp_path)
    original_connect = db.connect

    def failing_connect():
        return _FailStatusUpdateConnection(original_connect())

    monkeypatch.setattr(db, "connect", failing_connect)
    try:
        with pytest.raises(RuntimeError, match="synthetic transition failure"):
            queue.continue_job(
                user_id=user_id,
                job_id=job_id,
                expected_stage="sanitary",
            )
    finally:
        monkeypatch.setattr(db, "connect", original_connect)

    record = queue.get_job_detail(user_id=user_id, job_id=job_id)
    assert record["status"] == "awaiting_approval"
    assert record["payload"]["meta"]["orchestrator_meta"].get("runtime_approved_stages") in (None, [])
    queue.shutdown()


def test_double_continue_consumes_checkpoint_once(tmp_path, monkeypatch):
    _db, queue, user_id, job_id = _awaiting_job(tmp_path)
    original_detail = queue.get_job_detail
    both_read = threading.Barrier(2)
    caller_ids = set()
    caller_lock = threading.Lock()

    def synchronized_detail(*, user_id, job_id):
        record = original_detail(user_id=user_id, job_id=job_id)
        thread_id = threading.get_ident()
        with caller_lock:
            first_read = thread_id not in caller_ids
            caller_ids.add(thread_id)
        if first_read and record and record["status"] == "awaiting_approval":
            both_read.wait(timeout=2)
        return record

    monkeypatch.setattr(queue, "get_job_detail", synchronized_detail)
    outcomes = []

    def submit_continue():
        try:
            outcomes.append(
                queue.continue_job(
                    user_id=user_id,
                    job_id=job_id,
                    expected_stage="sanitary",
                )["status"]
            )
        except ValueError as exc:
            outcomes.append(str(exc))

    threads = [threading.Thread(target=submit_continue) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)
        assert not thread.is_alive()

    assert len([item for item in outcomes if item == "queued"]) == 1
    assert len([item for item in outcomes if "no longer waiting" in item]) == 1
    record = original_detail(user_id=user_id, job_id=job_id)
    assert record["status"] == "queued"
    assert record["payload"]["meta"]["orchestrator_meta"]["runtime_approved_stages"] == ["sanitary"]
    queue.shutdown()


def test_continue_does_not_overwrite_newer_claimed_generation(tmp_path, monkeypatch, caplog):
    _db, queue, user_id, job_id = _awaiting_job(tmp_path)
    monkeypatch.setenv("CIVORA_JOB_TRANSITION_DIAGNOSTIC_IDS", job_id)
    monkeypatch.setenv("CIVORA_JOB_TRANSITION_DIAGNOSTIC_UNTIL_EPOCH", str(time.time() + 300))
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    original_detail = queue.get_job_detail
    approval_read = threading.Event()
    release_continue = threading.Event()

    def paused_detail(*, user_id, job_id):
        record = original_detail(user_id=user_id, job_id=job_id)
        if record and record["status"] == "awaiting_approval" and not approval_read.is_set():
            approval_read.set()
            assert release_continue.wait(timeout=2)
        return record

    monkeypatch.setattr(queue, "get_job_detail", paused_detail)
    outcome = []

    def submit_continue():
        try:
            queue.continue_job(
                user_id=user_id,
                job_id=job_id,
                expected_stage="sanitary",
            )
        except ValueError as exc:
            outcome.append(str(exc))

    thread = threading.Thread(target=submit_continue)
    thread.start()
    assert approval_read.wait(timeout=2)
    queue._update_job_state(
        job_id,
        status="running",
        result={"job_progress": {"stage": "Utility", "detail": "Newer generation claimed.", "progress": 66}},
        error=None,
    )
    release_continue.set()
    thread.join(timeout=3)
    assert not thread.is_alive()

    assert outcome == ["This review checkpoint is no longer waiting for approval."]
    record = original_detail(user_id=user_id, job_id=job_id)
    assert record["status"] == "running"
    assert record["stage"] == "Utility"
    assert record["stage_detail"] == "Newer generation claimed."
    assert record["payload"]["meta"]["orchestrator_meta"].get("runtime_approved_stages") in (None, [])
    events = [
        json.loads(item.getMessage().split("JOB_LIFECYCLE ", 1)[1])
        for item in caplog.records
        if "JOB_LIFECYCLE " in item.getMessage()
    ]
    assert [(item["reason_category"], item["prior_stage"], item["approved_stage"], item["next_stage"]) for item in events] == [
        ("cas_rejected", "sanitary", "sanitary", "unknown")
    ]
    assert events[0]["checkpoint_cause"] == "atomic_approval_rejected"
    queue.shutdown()
