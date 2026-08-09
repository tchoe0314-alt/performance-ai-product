from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"
SCRIPT = WEB / "scripts" / "run-hosted-gauntlet.mjs"


def _run_gauntlet(tmp_path: Path, *, authenticated: bool) -> tuple[subprocess.CompletedProcess[str], dict]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_npx = fake_bin / "npx"
    fake_npx.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_npx.chmod(0o755)
    report_path = tmp_path / "hosted-gauntlet.json"
    env = dict(os.environ)
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    env["HOSTED_GAUNTLET_REPORT"] = str(report_path)
    env.pop("CIVORA_EMAIL", None)
    env.pop("CIVORA_PASSWORD", None)
    if authenticated:
        env["CIVORA_EMAIL"] = "release-test@example.com"
        env["CIVORA_PASSWORD"] = "test-only-password"
    completed = subprocess.run(
        ["node", str(SCRIPT)],
        cwd=WEB,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return completed, json.loads(report_path.read_text(encoding="utf-8"))


def test_full_hosted_gauntlet_blocks_when_authenticated_proof_is_skipped(tmp_path: Path) -> None:
    completed, report = _run_gauntlet(tmp_path, authenticated=False)

    assert completed.returncode == 1
    assert report["success"] is False
    assert report["status"] == "blocked"
    assert report["authenticated_smoke"]["status"] == "skipped"
    assert "required for full hosted release evidence" in completed.stdout


def test_full_hosted_gauntlet_passes_only_when_all_authenticated_slices_pass(tmp_path: Path) -> None:
    completed, report = _run_gauntlet(tmp_path, authenticated=True)

    assert completed.returncode == 0
    assert report["success"] is True
    assert report["status"] == "passed"
    assert report["authenticated_smoke"]["status"] == "passed"
    assert report["authenticated_real_workflows"]["status"] == "passed"
    assert report["hosted_load_and_rate_limits"]["status"] == "passed"
