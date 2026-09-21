from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.application.full_launch_readiness import build_full_launch_readiness


def _load(path_value: str) -> Any:
    path = (ROOT / path_value).resolve()
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _revision() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Civora's fail-closed full-launch readiness report.")
    parser.add_argument("--engineering", default="reports/release/rc1-engineering-validation.json")
    parser.add_argument("--sources", default="reports/release/source-infrastructure-evidence.json")
    parser.add_argument("--confirmation", default="reports/release/major-change-confirmation-evidence.json")
    parser.add_argument("--reliability", default="reports/release/rc1-evidence-manifest.json")
    parser.add_argument("--hosted", default="reports/release/hosted-operational-evidence.json")
    parser.add_argument("--external", default="reports/release/external-readiness-evidence.json")
    parser.add_argument("--real-projects", default="reports/validation/real-project-validation.json")
    parser.add_argument("--output", default="reports/release/full-launch-readiness.json")
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    real_projects = _load(args.real_projects)
    if isinstance(real_projects, dict):
        real_projects = real_projects.get("projects") or []
    report = build_full_launch_readiness(
        revision=_revision(),
        engineering_validation=_load(args.engineering),
        source_infrastructure=_load(args.sources),
        confirmation_evidence=_load(args.confirmation),
        reliability_manifest=_load(args.reliability),
        hosted_evidence=_load(args.hosted),
        external_evidence=_load(args.external),
        real_project_records=real_projects if isinstance(real_projects, list) else [],
    )
    output = (ROOT / args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": report["status"], "full_launch_ready": report["full_launch_ready"], "blocker_count": report["blocker_count"], "output": str(output.relative_to(ROOT))}, sort_keys=True))
    if args.fail_on_blocked and not report["full_launch_ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
