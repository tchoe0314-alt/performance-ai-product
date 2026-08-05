from __future__ import annotations

from backend.scripts.run_combined_backend import (
    build_process_environments,
    build_web_command,
    build_worker_command,
)


def test_combined_runner_externalizes_heavy_jobs_and_keeps_file_jobs_local() -> None:
    web_env, worker_env = build_process_environments(
        {
            "DATABASE_URL": "postgresql://example.invalid/civora",
            "CIVORA_DISABLED_JOB_TYPES": "custom_disabled",
            "PORT": "8123",
        }
    )

    assert web_env["CIVORA_PROCESS_ROLE"] == "web"
    assert web_env["PERFORMANCE_AI_JOB_WORKERS"] == "0"
    assert web_env["CIVORA_DATABASE_POOL_MIN_SIZE"] == "2"
    assert web_env["CIVORA_DATABASE_POOL_MAX_SIZE"] == "6"
    assert web_env["CIVORA_ANYIO_THREAD_LIMIT"] == "8"
    assert web_env["CIVORA_DISABLED_JOB_TYPES"] == "custom_disabled"
    assert worker_env["CIVORA_PROCESS_ROLE"] == "worker"
    assert set(worker_env["CIVORA_ENABLED_JOB_TYPES"].split(",")) == {
        "drainage_only",
        "export_dxf",
        "export_pdf",
        "export_report",
        "orchestrate",
        "plan_pdf_analysis",
        "source_context",
    }
    assert worker_env["CIVORA_DISABLED_JOB_TYPES"] == ""
    assert worker_env["CIVORA_WORKER_HEALTH_ENABLED"] == "false"
    assert worker_env["CIVORA_DATABASE_POOL_MAX_SIZE"] == "2"


def test_combined_runner_builds_stable_single_web_process() -> None:
    command = build_web_command({"PORT": "8123", "WEB_TIMEOUT_SECONDS": "42"})

    assert command[0] == "gunicorn"
    assert command[command.index("--bind") + 1] == "0.0.0.0:8123"
    assert command[command.index("--workers") + 1] == "1"
    assert command[command.index("--timeout") + 1] == "42"
    assert command[command.index("--max-requests") + 1] == "0"


def test_combined_runner_lowers_worker_priority_by_default() -> None:
    command = build_worker_command({})

    assert command[:3] == ["nice", "-n", "10"]
    assert command[-2:] == ["-m", "backend.scripts.run_job_worker"]


def test_combined_runner_allows_explicit_worker_priority_override() -> None:
    command = build_worker_command({"CIVORA_WORKER_NICE_LEVEL": "0"})

    assert command[0] != "nice"
    assert command[-2:] == ["-m", "backend.scripts.run_job_worker"]
