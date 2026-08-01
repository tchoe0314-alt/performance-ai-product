from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Mapping


DEFAULT_EXTERNAL_JOB_TYPES = ("orchestrate", "source_context")


def _csv_values(raw: str | None) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def build_process_environments(
    source: Mapping[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    base = dict(source or os.environ)
    external_types = _csv_values(base.get("CIVORA_COMBINED_EXTERNAL_JOB_TYPES"))
    if not external_types:
        external_types = list(DEFAULT_EXTERNAL_JOB_TYPES)

    worker_env = dict(base)
    worker_env.update(
        {
            "CIVORA_PROCESS_ROLE": "worker",
            "CIVORA_ENABLED_JOB_TYPES": ",".join(external_types),
            "CIVORA_DISABLED_JOB_TYPES": "",
            "CIVORA_WORKER_HEALTH_ENABLED": "false",
            "PERFORMANCE_AI_JOB_WORKERS": str(base.get("CIVORA_EXTERNAL_JOB_WORKERS") or "1"),
            "PERFORMANCE_AI_RESUME_PENDING_JOBS": "true",
            "PERFORMANCE_AI_RESUME_POLL_SECONDS": str(
                base.get("PERFORMANCE_AI_RESUME_POLL_SECONDS") or "1"
            ),
        }
    )

    web_disabled = list(dict.fromkeys(_csv_values(base.get("CIVORA_DISABLED_JOB_TYPES")) + external_types))
    web_env = dict(base)
    web_env.update(
        {
            "CIVORA_PROCESS_ROLE": "combined",
            "CIVORA_DEDICATED_WORKER_ENABLED": "true",
            "CIVORA_DISABLED_JOB_TYPES": ",".join(web_disabled),
        }
    )
    web_env.pop("CIVORA_ENABLED_JOB_TYPES", None)
    web_env.setdefault("PERFORMANCE_AI_JOB_WORKERS", "1")
    return web_env, worker_env


def build_web_command(source: Mapping[str, str] | None = None) -> list[str]:
    env = source or os.environ
    port = str(env.get("PORT") or "8002")
    timeout = str(env.get("WEB_TIMEOUT_SECONDS") or "35")
    return [
        "gunicorn",
        "backend.api.app:app",
        "--worker-class",
        "uvicorn.workers.UvicornWorker",
        "--bind",
        f"0.0.0.0:{port}",
        "--workers",
        "1",
        "--timeout",
        timeout,
        "--graceful-timeout",
        "10",
        "--keep-alive",
        "3",
        "--max-requests",
        "0",
        "--max-requests-jitter",
        "0",
        "--access-logfile",
        "/dev/null",
        "--error-logfile",
        "-",
        "--log-level",
        "warning",
    ]


def _stop_process(process: subprocess.Popen[bytes] | None, *, timeout: float = 10.0) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def main() -> int:
    web_env, worker_env = build_process_environments()
    worker_process: subprocess.Popen[bytes] | None = None
    web_process: subprocess.Popen[bytes] | None = None
    stopping = False

    def request_stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    try:
        worker_process = subprocess.Popen(
            [sys.executable, "-m", "backend.scripts.run_job_worker"],
            env=worker_env,
        )
        web_process = subprocess.Popen(build_web_command(web_env), env=web_env)

        while not stopping:
            worker_status = worker_process.poll()
            web_status = web_process.poll()
            if worker_status is not None:
                print(
                    {"event": "civora_combined_worker_exited", "exit_code": worker_status},
                    flush=True,
                )
                return worker_status or 1
            if web_status is not None:
                return web_status
            time.sleep(0.5)
        return 0
    finally:
        _stop_process(web_process)
        _stop_process(worker_process)


if __name__ == "__main__":
    raise SystemExit(main())
