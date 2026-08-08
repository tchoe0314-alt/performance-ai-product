from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
START_SCRIPT = ROOT / "scripts" / "start_backend_service.sh"


def _run_startup(tmp_path: Path, *, role: str, extra_env: dict[str, str] | None = None) -> str:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    recorder = tmp_path / "recorded.txt"
    for command in ("gunicorn", "python"):
        executable = fake_bin / command
        executable.write_text(
            "#!/usr/bin/env sh\n"
            f"printf '%s\\n' '{command}' \"$@\" > '{recorder}'\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
        "CIVORA_PROCESS_ROLE": role,
        "PERFORMANCE_AI_STORAGE_DIR": str(tmp_path / "data"),
        "MPLCONFIGDIR": str(tmp_path / "mpl"),
        "PORT": "8123",
        **(extra_env or {}),
    }
    subprocess.run(["sh", str(START_SCRIPT)], cwd=ROOT, env=env, check=True)
    return recorder.read_text(encoding="utf-8")


def test_combined_service_keeps_one_stable_worker_process(tmp_path: Path) -> None:
    output = _run_startup(
        tmp_path,
        role="combined",
        extra_env={
            "WEB_CONCURRENCY": "8",
            "WEB_MAX_REQUESTS": "12",
            "CIVORA_COMBINED_PROCESS_ISOLATION": "false",
        },
    )
    assert output.startswith("gunicorn\n")
    assert "--workers\n1\n" in output
    assert "--max-requests\n0\n" in output
    assert "--max-requests-jitter\n0\n" in output


def test_web_service_keeps_configurable_request_workers(tmp_path: Path) -> None:
    output = _run_startup(
        tmp_path,
        role="web",
        extra_env={"WEB_CONCURRENCY": "3", "WEB_MAX_REQUESTS": "400", "WEB_MAX_REQUESTS_JITTER": "40"},
    )
    assert output.startswith("gunicorn\n")
    assert "--workers\n3\n" in output
    assert "--max-requests\n400\n" in output
    assert "--max-requests-jitter\n40\n" in output


def test_postgres_web_service_uses_isolated_worker_fallback_until_external_worker_is_confirmed(tmp_path: Path) -> None:
    output = _run_startup(
        tmp_path,
        role="web",
        extra_env={"DATABASE_URL": "postgresql://example.invalid/civora"},
    )
    assert output == "python\n-m\nbackend.scripts.run_combined_backend\n"


def test_postgres_web_service_stays_web_only_after_external_worker_confirmation(tmp_path: Path) -> None:
    output = _run_startup(
        tmp_path,
        role="web",
        extra_env={
            "DATABASE_URL": "postgresql://example.invalid/civora",
            "CIVORA_EXTERNAL_WORKER_CONFIRMED": "true",
            "WEB_CONCURRENCY": "2",
        },
    )
    assert output.startswith("gunicorn\n")
    assert "--workers\n2\n" in output


def test_worker_service_runs_dedicated_job_worker(tmp_path: Path) -> None:
    output = _run_startup(tmp_path, role="worker")
    assert output == "python\n-m\nbackend.scripts.run_job_worker\n"


def test_postgres_combined_service_uses_process_isolated_runner(tmp_path: Path) -> None:
    output = _run_startup(
        tmp_path,
        role="combined",
        extra_env={"DATABASE_URL": "postgresql://example.invalid/civora"},
    )
    assert output == "python\n-m\nbackend.scripts.run_combined_backend\n"
