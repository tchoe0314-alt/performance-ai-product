from __future__ import annotations

import os
import signal
import time


os.environ.setdefault("CIVORA_PROCESS_ROLE", "worker")
os.environ.setdefault("PERFORMANCE_AI_JOB_WORKERS", "1")
os.environ.setdefault("PERFORMANCE_AI_RESUME_PENDING_JOBS", "true")
os.environ.setdefault("PERFORMANCE_AI_RESUME_POLL_SECONDS", "1")

from backend.api.app import JOB_QUEUE, register_job_handlers  # noqa: E402


def main() -> int:
    stopping = False

    def request_stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    register_job_handlers()
    print(
        {
            "event": "civora_job_worker_ready",
            "registered_handlers": JOB_QUEUE.runtime_stats().get("registered_handlers"),
        },
        flush=True,
    )
    while not stopping:
        time.sleep(1)
    print({"event": "civora_job_worker_stopped"}, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
