from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Mapping


EXTERNAL_JOB_TYPES = (
    "ai_visualization",
    "drainage_only",
    "export_dxf",
    "export_pdf",
    "export_report",
    "orchestrate",
    "plan_pdf_analysis",
    "source_context",
)


def _positive_poll_seconds(source: Mapping[str, str], default: float = 1.0) -> str:
    raw_value = str(source.get("PERFORMANCE_AI_RESUME_POLL_SECONDS") or "").strip()
    try:
        value = float(raw_value)
    except Exception:
        value = default
    if value <= 0:
        value = default
    return f"{value:g}"


def build_process_environments(
    source: Mapping[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    base = dict(source or os.environ)
    configured_worker_job_types = tuple(
        item.strip()
        for item in str(base.get("CIVORA_ENABLED_JOB_TYPES") or "").split(",")
        if item.strip()
    )
    worker_job_types = configured_worker_job_types or EXTERNAL_JOB_TYPES
    worker_env = dict(base)
    worker_env.update(
        {
            "CIVORA_PROCESS_ROLE": "worker",
            # A dedicated service may intentionally own one queue slice. Do
            # not broaden its explicit allowlist when the startup wrapper
            # falls through combined-process supervision.
            "CIVORA_ENABLED_JOB_TYPES": ",".join(worker_job_types),
            "CIVORA_DISABLED_JOB_TYPES": "",
            "CIVORA_WORKER_HEALTH_ENABLED": "false",
            "PERFORMANCE_AI_JOB_WORKERS": str(base.get("CIVORA_EXTERNAL_JOB_WORKERS") or "2"),
            "PERFORMANCE_AI_RESUME_PENDING_JOBS": "true",
            "PERFORMANCE_AI_RESUME_POLL_SECONDS": _positive_poll_seconds(base),
            "CIVORA_DATABASE_POOL_MIN_SIZE": "1",
            "CIVORA_DATABASE_POOL_MAX_SIZE": str(
                base.get("CIVORA_WORKER_DATABASE_POOL_MAX_SIZE") or "2"
            ),
        }
    )

    web_env = dict(base)
    web_env.update(
        {
            "CIVORA_PROCESS_ROLE": "web",
            "CIVORA_DEDICATED_WORKER_ENABLED": "true",
            "CIVORA_EXTERNAL_WORKER_CONFIRMED": "true",
            "PERFORMANCE_AI_JOB_WORKERS": "0",
            "CIVORA_DATABASE_POOL_MIN_SIZE": "2",
            "CIVORA_DATABASE_POOL_MAX_SIZE": str(
                base.get("CIVORA_WEB_DATABASE_POOL_MAX_SIZE") or "6"
            ),
            "CIVORA_ANYIO_THREAD_LIMIT": str(base.get("CIVORA_ANYIO_THREAD_LIMIT") or "8"),
        }
    )
    web_env.pop("CIVORA_ENABLED_JOB_TYPES", None)
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


def build_worker_command(source: Mapping[str, str] | None = None) -> list[str]:
    env = source or os.environ
    raw_nice_level = str(env.get("CIVORA_WORKER_NICE_LEVEL") or "10").strip()
    try:
        nice_level = min(19, max(0, int(raw_nice_level or 10)))
    except Exception:
        nice_level = 10
    command = [sys.executable, "-m", "backend.scripts.run_job_worker"]
    if nice_level <= 0:
        return command
    return ["nice", "-n", str(nice_level), *command]


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
            build_worker_command(worker_env),
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
