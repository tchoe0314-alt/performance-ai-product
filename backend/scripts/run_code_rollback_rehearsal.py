from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.application.release_rollback_rehearsal import build_code_rollback_rehearsal_report


def _git(*args: str, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rehearse Civora code rollback retrieval without changing a deployment or database.")
    parser.add_argument("--current-revision", default="HEAD")
    parser.add_argument("--candidate-revision", default="HEAD^")
    parser.add_argument(
        "--verification-command",
        default=f"{sys.executable} -m pytest tests/test_api_release_safety.py tests/test_release_candidate_readiness.py -q",
    )
    parser.add_argument("--output", default="reports/release/code-rollback-rehearsal.json")
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    current = _git("rev-parse", args.current_revision).stdout.strip()
    candidate = _git("rev-parse", args.candidate_revision).stdout.strip()
    ancestor = _git("merge-base", "--is-ancestor", candidate, current, check=False).returncode == 0
    candidate_retrieved = False
    candidate_clean = False
    verification_exit_code = 127
    verification_duration = 0.0
    critical_paths = {
        "backend/api/app.py": False,
        "apps/web/app/page.tsx": False,
        "scripts/release_regression.sh": False,
    }

    with tempfile.TemporaryDirectory(prefix="civora-code-rollback-") as temporary:
        worktree = Path(temporary) / "candidate"
        added = _git("worktree", "add", "--detach", str(worktree), candidate, check=False)
        if added.returncode == 0:
            try:
                candidate_retrieved = _git("rev-parse", "HEAD", cwd=worktree).stdout.strip() == candidate
                candidate_clean = not bool(_git("status", "--porcelain", "--untracked-files=no", cwd=worktree).stdout.strip())
                critical_paths = {path: (worktree / path).is_file() for path in critical_paths}
                command = shlex.split(args.verification_command)
                started = time.perf_counter()
                completed = subprocess.run(command, cwd=worktree, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
                verification_duration = time.perf_counter() - started
                verification_exit_code = int(completed.returncode)
            finally:
                _git("worktree", "remove", "--force", str(worktree), check=False)

    report = build_code_rollback_rehearsal_report(
        current_revision=current,
        candidate_revision=candidate,
        candidate_is_ancestor=ancestor,
        candidate_retrieved=candidate_retrieved,
        candidate_worktree_clean=candidate_clean,
        critical_paths=critical_paths,
        verification_command=args.verification_command,
        verification_exit_code=verification_exit_code,
        verification_duration_seconds=verification_duration,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "current_revision": current,
        "candidate_revision": candidate,
        "verification_exit_code": verification_exit_code,
        "provider_rollback_proven": False,
        "output": str(output),
    }, sort_keys=True))
    if args.fail_on_blocked and not report["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
