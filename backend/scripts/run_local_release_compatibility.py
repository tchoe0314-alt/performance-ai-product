from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=check,
    )


def _changed_files(base: str, current: str) -> list[str]:
    return [line for line in _git("diff", "--name-only", f"{base}..{current}").stdout.splitlines() if line]


def _schema_change_evidence(base: str, current: str, files: list[str]) -> dict[str, object]:
    schema_paths = [
        path for path in files
        if path.startswith("migrations/")
        or path.startswith("alembic/")
        or path == "backend/services/database.py"
    ]
    database_diff = ""
    if "backend/services/database.py" in files:
        database_diff = _git("diff", "--unified=0", f"{base}..{current}", "--", "backend/services/database.py").stdout
    ddl_lines = [
        line.strip() for line in database_diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
        and any(token in line.upper() for token in ("CREATE TABLE", "ALTER TABLE", "DROP TABLE", "CREATE INDEX"))
    ]
    return {
        "introduced_by_compared_release": bool(schema_paths or ddl_lines),
        "changed_schema_paths": schema_paths,
        "added_ddl_lines": ddl_lines,
        "preexisting_runtime_ddl_risk": True,
        "interpretation": (
            "The compared release changes schema-related code; disposable compatibility and an explicit migration/rollback plan are required."
            if schema_paths or ddl_lines else
            "No schema-related file or added DDL was found in the compared release. Runtime DDL remains a preexisting platform risk."
        ),
    }


def _run(command: list[str]) -> dict[str, object]:
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return {
        "command": command,
        "exit_code": completed.returncode,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "output_tail": completed.stdout[-4000:],
        "passed": completed.returncode == 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create local, non-provider Civora release compatibility evidence.")
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--deployed-revision", help="Exact currently deployed revision. Omit only to record a release blocker.")
    parser.add_argument("--rollback-revision", help="Exact previously proven revision. Omit only to record a rollback blocker.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--run-disposable-tests", action="store_true")
    args = parser.parse_args()

    current = _git("rev-parse", "HEAD").stdout.strip()
    expected = _git("rev-parse", args.expected_revision).stdout.strip()
    clean = not bool(_git("status", "--porcelain", "--untracked-files=no").stdout.strip())
    base = args.deployed_revision
    base_resolved = _git("rev-parse", base, check=False).stdout.strip() if base else ""
    rollback_resolved = _git("rev-parse", args.rollback_revision, check=False).stdout.strip() if args.rollback_revision else ""
    changed = _changed_files(base_resolved, current) if base_resolved else []
    schema = _schema_change_evidence(base_resolved, current, changed) if base_resolved else {
        "introduced_by_compared_release": None,
        "changed_schema_paths": [],
        "added_ddl_lines": [],
        "preexisting_runtime_ddl_risk": True,
        "interpretation": "Blocked: exact deployed revision was not supplied, so release-introduced schema change cannot be determined.",
    }
    rollback_is_ancestor = bool(rollback_resolved) and _git("merge-base", "--is-ancestor", rollback_resolved, current, check=False).returncode == 0
    required_paths = [
        "apps/web/app/api/release-identity/route.ts",
        "backend/scripts/run_combined_backend.py",
        "backend/scripts/run_job_worker.py",
        "backend/services/database.py",
        "backend/application/hosted_operational_evidence.py",
        "backend/scripts/run_code_rollback_rehearsal.py",
    ]
    tests: list[dict[str, object]] = []
    if args.run_disposable_tests:
        tests.append(_run([
            sys.executable, "-m", "pytest",
            "tests/test_phase0_legacy_database_migration.py",
            "tests/test_database_pool.py",
            "tests/test_api_release_safety.py", "-q",
        ]))
    blockers = []
    if sys.version_info < (3, 11):
        blockers.append("Python 3.11 or newer is required for release compatibility checks")
    if current != expected:
        blockers.append("working tree revision does not equal expected release revision")
    if not clean:
        blockers.append("tracked working tree is dirty")
    if not base_resolved:
        blockers.append("exact currently deployed revision is missing")
    if not rollback_resolved:
        blockers.append("exact previously proven rollback revision is missing")
    elif not rollback_is_ancestor:
        blockers.append("rollback revision is not an ancestor of the candidate")
    if any(not (ROOT / path).is_file() for path in required_paths):
        blockers.append("one or more release identity/worker/database/rollback paths are missing")
    if args.run_disposable_tests and any(not item["passed"] for item in tests):
        blockers.append("disposable database/API compatibility tests failed")
    report = {
        "schema_version": 1,
        "scope": "local_repository_and_disposable_services_only",
        "provider_state_verified": False,
        "candidate_revision": current,
        "python_version": sys.version.split()[0],
        "expected_revision": expected,
        "tracked_worktree_clean": clean,
        "deployed_revision": base_resolved or None,
        "rollback_revision": rollback_resolved or None,
        "rollback_is_ancestor": rollback_is_ancestor,
        "required_paths": {path: (ROOT / path).is_file() for path in required_paths},
        "changed_files_count": len(changed),
        "schema_change_evidence": schema,
        "disposable_checks": tests,
        "blockers": blockers,
        "local_gate_passed": not blockers,
        "release_allowed": False,
        "release_allowed_reason": "Local evidence cannot prove provider revision, shared database, backups, worker readiness, hosted canary, or rollback controls.",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"local_gate_passed": report["local_gate_passed"], "blockers": blockers, "output": str(output)}, sort_keys=True))
    if blockers:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
