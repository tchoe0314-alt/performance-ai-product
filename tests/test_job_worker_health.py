from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

from backend.scripts.run_job_worker import build_health_server, normalize_worker_poll_seconds


class _FakeJobQueue:
    def runtime_stats(self) -> dict:
        return {
            "worker_count": 1,
            "alive_workers": 1,
            "registered_handlers": ["source_context"],
            "monitoring": {
                "pending_count": 2,
                "running_count": 1,
                "failed_count": 0,
                "stale_count": 0,
            },
        }


def test_worker_polling_cannot_be_disabled_by_zero_or_invalid_interval() -> None:
    assert normalize_worker_poll_seconds("0") == "1"
    assert normalize_worker_poll_seconds("-5") == "1"
    assert normalize_worker_poll_seconds("invalid") == "1"
    assert normalize_worker_poll_seconds("0.25") == "0.25"


def test_worker_health_server_reports_safe_aggregate_status() -> None:
    server = build_health_server(_FakeJobQueue(), host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/api/health",
            timeout=2,
        ) as response:
            payload = json.loads(response.read())
        assert response.status == 200
        assert payload == {
            "status": "ok",
            "service": "civora-job-worker",
            "role": "worker",
            "worker_count": 1,
            "alive_workers": 1,
            "registered_handlers": ["source_context"],
            "queue": {
                "queued": 2,
                "running": 1,
                "failed": 0,
                "stale": 0,
            },
        }
        assert "projects" not in payload
        assert "users" not in payload
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_worker_health_server_rejects_unknown_paths() -> None:
    server = build_health_server(_FakeJobQueue(), host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/debug",
                timeout=2,
            )
        except urllib.error.HTTPError as error:
            assert error.code == 404
        else:
            raise AssertionError("Worker health server should reject unknown paths.")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
