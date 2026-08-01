from __future__ import annotations

import json
import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


os.environ.setdefault("CIVORA_PROCESS_ROLE", "worker")
os.environ.setdefault("PERFORMANCE_AI_JOB_WORKERS", "1")
os.environ.setdefault("PERFORMANCE_AI_RESUME_PENDING_JOBS", "true")
os.environ.setdefault("PERFORMANCE_AI_RESUME_POLL_SECONDS", "1")

from backend.api.app import JOB_QUEUE, register_job_handlers  # noqa: E402


def _worker_health_payload(job_queue: Any) -> dict[str, Any]:
    stats = dict(job_queue.runtime_stats() or {})
    monitoring = dict(stats.get("monitoring") or {})
    return {
        "status": "ok",
        "service": "civora-job-worker",
        "role": "worker",
        "worker_count": int(stats.get("worker_count") or 0),
        "alive_workers": int(stats.get("alive_workers") or 0),
        "registered_handlers": list(stats.get("registered_handlers") or []),
        "queue": {
            "queued": int(monitoring.get("pending_count") or monitoring.get("queued_count") or 0),
            "running": int(monitoring.get("running_count") or 0),
            "failed": int(monitoring.get("failed_count") or 0),
            "stale": int(monitoring.get("stale_count") or 0),
        },
    }


def build_health_server(
    job_queue: Any,
    *,
    host: str = "0.0.0.0",
    port: int | None = None,
) -> ThreadingHTTPServer:
    class WorkerHealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path.rstrip("/") not in {"", "/api/health"}:
                self.send_error(404)
                return
            payload = json.dumps(_worker_health_payload(job_queue), separators=(",", ":")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    resolved_port = port if port is not None else int(os.getenv("PORT") or "8002")
    return ThreadingHTTPServer((host, resolved_port), WorkerHealthHandler)


def main() -> int:
    stopping = False

    def request_stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    register_job_handlers()
    health_enabled = str(os.getenv("CIVORA_WORKER_HEALTH_ENABLED") or "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    health_server = build_health_server(JOB_QUEUE) if health_enabled else None
    health_thread = None
    if health_server is not None:
        health_thread = threading.Thread(
            target=health_server.serve_forever,
            name="civora-worker-health",
            daemon=True,
        )
        health_thread.start()
    print(
        {
            "event": "civora_job_worker_ready",
            "registered_handlers": JOB_QUEUE.runtime_stats().get("registered_handlers"),
            "health_port": health_server.server_port if health_server is not None else None,
        },
        flush=True,
    )
    try:
        while not stopping:
            time.sleep(1)
    finally:
        if health_server is not None:
            health_server.shutdown()
            health_server.server_close()
        if health_thread is not None:
            health_thread.join(timeout=3)
    print({"event": "civora_job_worker_stopped"}, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
