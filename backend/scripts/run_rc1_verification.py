from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, Iterable, Sequence
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "apps" / "web"
REPORT_ROOT = ROOT / "reports" / "release"
DEFAULT_MANIFEST = REPORT_ROOT / "rc1-evidence-manifest.json"
TECHNICAL_EVIDENCE_KEYS = (
    "backend_regression",
    "frontend_quality",
    "security_dependency",
    "data_lifecycle",
    "backup_restore_local",
    "engineering_real_files",
    "browser_core",
    "browser_cross_device_accessibility",
    "long_session_concurrency",
    "hosted_end_to_end",
)


def _revision() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _redact(text: str, env: Dict[str, str]) -> str:
    redacted = text
    sensitive_fragments = ("PASSWORD", "TOKEN", "SECRET", "API_KEY", "AUTHORIZATION", "COOKIE")
    for name, value in env.items():
        if any(fragment in name.upper() for fragment in sensitive_fragments) and len(str(value)) >= 6:
            redacted = redacted.replace(str(value), "[redacted]")
    return redacted


def _command_label(command: Sequence[str]) -> str:
    return " ".join(command)


def _run_command(
    *,
    section: str,
    command: Sequence[str],
    cwd: Path,
    env: Dict[str, str],
    timeout_seconds: int = 3600,
) -> Dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_seconds,
            check=False,
        )
        exit_code = int(completed.returncode)
        output = completed.stdout or ""
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        output = str(exc.stdout or "") + "\nCommand timed out."
        timed_out = True
    duration = round(time.perf_counter() - started, 3)
    safe_output = _redact(output, env)
    log_dir = REPORT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{section}.log"
    log_path.write_text(safe_output, encoding="utf-8")
    return {
        "success": exit_code == 0,
        "command": _command_label(command),
        "cwd": str(cwd.relative_to(ROOT) if cwd != ROOT else Path(".")),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_seconds": duration,
        "log_path": str(log_path.relative_to(ROOT)),
        "message": "Passed." if exit_code == 0 else f"Failed with exit code {exit_code}; inspect {log_path.relative_to(ROOT)}.",
    }


def _run_group(
    *,
    section: str,
    commands: Iterable[tuple[Sequence[str], Path]],
    env: Dict[str, str],
) -> Dict[str, Any]:
    records = []
    for index, (command, cwd) in enumerate(commands, start=1):
        record = _run_command(
            section=f"{section}-{index}",
            command=command,
            cwd=cwd,
            env=env,
        )
        records.append(record)
        print(json.dumps({"section": section, "step": index, **record}, sort_keys=True), flush=True)
        if not record["success"]:
            break
    return {
        "success": bool(records) and all(record["success"] for record in records),
        "commands": records,
        "duration_seconds": round(sum(float(record["duration_seconds"]) for record in records), 3),
        "message": "All commands passed." if records and all(record["success"] for record in records) else "One or more commands failed.",
    }


def _section_commands(*, skip_install: bool, hosted_base_url: str) -> Dict[str, list[tuple[Sequence[str], Path]]]:
    python = sys.executable
    playwright = str(WEB / "node_modules" / ".bin" / "playwright")
    frontend_quality = []
    if not skip_install:
        frontend_quality.append((("npm", "ci"), WEB))
    frontend_quality.extend(
        (
            (("npm", "run", "lint"), WEB),
            (("node", "node_modules/typescript/bin/tsc", "--project", "tsconfig.json", "--noEmit", "--pretty", "false", "--incremental", "false"), WEB),
            (("npm", "run", "build"), WEB),
        )
    )
    sections: Dict[str, list[tuple[Sequence[str], Path]]] = {
        "backend_regression": [((python, "-m", "pytest", "-q", "--junitxml=reports/release/backend-pytest.xml"), ROOT)],
        "frontend_quality": frontend_quality,
        "security_dependency": [
            (("npm", "audit", "--audit-level=moderate"), WEB),
            ((python, "-m", "pip", "check"), ROOT),
            ((python, "-m", "bandit", "-r", "backend", "scripts", "-ll"), ROOT),
            ((python, "-m", "pip_audit", "-r", "requirements_backend.txt", "--no-deps", "--disable-pip", "--progress-spinner", "off"), ROOT),
            ((python, "-m", "pip_audit", "-r", "requirements_imagery_gateway.txt", "--no-deps", "--disable-pip", "--progress-spinner", "off"), ROOT),
            ((python, "-m", "pip_audit", "-r", "requirements_ai_renderer.txt", "--no-deps", "--disable-pip", "--progress-spinner", "off"), ROOT),
            ((python, "-m", "pip_audit", "-r", "requirements_vision_training.txt", "--no-deps", "--disable-pip", "--progress-spinner", "off"), ROOT),
        ],
        "data_lifecycle": [
            ((python, "-m", "pytest", "tests/test_data_lifecycle_and_backup.py", "tests/test_api_account_support.py", "-q"), ROOT),
            ((playwright, "test", "--config=playwright.config.ts", "tests/live/rc1-support-data-lifecycle.spec.ts", "--project=chromium", "--workers=1"), WEB),
        ],
        "backup_restore_local": [
            ((python, "backend/scripts/run_backup_restore_drill.py", "--db-path", "reports/release/rc1-backup-source.sqlite3", "--output-dir", "reports/release/backup", "--report", "reports/release/backup_restore_report.json", "--fail-on-blocked"), ROOT),
        ],
        "engineering_real_files": [((python, "backend/scripts/run_rc1_engineering_validation.py"), ROOT)],
        "browser_core": [((playwright, "test", "--config=playwright.config.ts", "--project=chromium", "--workers=1"), WEB)],
        "browser_cross_device_accessibility": [
            ((playwright, "test", "--config=playwright.config.ts", "tests/live/rc1-accessibility-cross-browser.spec.ts", "--project=webkit", "--project=mobile-chromium", "--project=mobile-webkit", "--workers=1"), WEB),
        ],
        "long_session_concurrency": [
            ((playwright, "test", "--config=playwright.config.ts", "tests/live/rc1-long-session-concurrency.spec.ts", "--project=chromium", "--workers=1"), WEB),
        ],
    }
    if hosted_base_url:
        sections["hosted_end_to_end"] = [(("npm", "run", "test:hosted"), WEB)]
    return sections


def _firefox_ci_evidence(*, env: Dict[str, str], revision: str) -> Dict[str, Any]:
    evidence_url = str(env.get("CIVORA_FIREFOX_CI_EVIDENCE_URL") or "").strip()
    evidence_revision = str(env.get("CIVORA_FIREFOX_CI_REVISION") or "").strip()
    evidence_status = str(env.get("CIVORA_FIREFOX_CI_STATUS") or "").strip().lower()
    parsed = urlparse(evidence_url)
    url_valid = parsed.scheme == "https" and bool(parsed.netloc)
    revision_matches = bool(revision) and evidence_revision == revision
    success = url_valid and revision_matches and evidence_status == "success"
    return {
        "success": success,
        "url": evidence_url,
        "url_valid": url_valid,
        "revision": evidence_revision,
        "revision_matches": revision_matches,
        "status": evidence_status,
        "message": (
            "Exact-revision Firefox CI evidence recorded."
            if success
            else "Firefox evidence requires a successful HTTPS CI run URL and an exact matching Git revision."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run resumable, revision-bound Civora RC1 verification evidence.")
    parser.add_argument("--sections", default=",".join(TECHNICAL_EVIDENCE_KEYS), help="Comma-separated evidence sections.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST.relative_to(ROOT)))
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--hosted-base-url", default=str(os.getenv("PLAYWRIGHT_BASE_URL") or "").strip())
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()

    selected = [item.strip() for item in args.sections.split(",") if item.strip()]
    unknown = sorted(set(selected) - set(TECHNICAL_EVIDENCE_KEYS))
    if unknown:
        raise SystemExit(f"Unknown evidence sections: {', '.join(unknown)}")
    revision = _revision()
    manifest_path = (ROOT / args.manifest).resolve()
    if manifest_path.is_file():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    else:
        existing = {}
    if str(existing.get("revision") or "") != revision:
        existing = {}
    manifest: Dict[str, Any] = {
        "version": "civora_rc1_evidence_manifest_v1",
        "revision": revision,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence": dict(existing.get("evidence") or {}),
        "truth_label": "Each successful evidence item records commands executed on this Git revision. Human, provider, legal, billing, and professional approvals remain separate gates.",
    }
    env = dict(os.environ)
    if args.hosted_base_url:
        env["PLAYWRIGHT_BASE_URL"] = args.hosted_base_url
        env["PLAYWRIGHT_SKIP_WEBSERVER"] = "1"
    commands = _section_commands(skip_install=args.skip_install, hosted_base_url=args.hosted_base_url)

    for section in selected:
        if section == "hosted_end_to_end" and not args.hosted_base_url:
            record = {
                "success": False,
                "commands": [],
                "duration_seconds": 0,
                "message": "Hosted evidence requires --hosted-base-url and authenticated CIVORA_EMAIL/CIVORA_PASSWORD environment variables.",
            }
        else:
            record = _run_group(section=section, commands=commands[section], env=env)
        if section == "browser_cross_device_accessibility":
            firefox_ci = _firefox_ci_evidence(env=env, revision=revision)
            record["firefox_ci"] = firefox_ci
            record["success"] = bool(record.get("success")) and firefox_ci["success"]
            if not firefox_ci["success"]:
                record["message"] = firefox_ci["message"]
        record["revision"] = revision
        record["recorded_at"] = datetime.now(timezone.utc).isoformat()
        manifest["evidence"][section] = record
        manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        if args.fail_fast and not record["success"]:
            raise SystemExit(1)

    failed = [key for key in selected if not bool(manifest["evidence"].get(key, {}).get("success"))]
    print(json.dumps({"revision": revision, "selected": selected, "failed": failed, "manifest": str(manifest_path.relative_to(ROOT))}, sort_keys=True))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
