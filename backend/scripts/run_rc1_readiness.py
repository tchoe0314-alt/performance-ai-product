from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.application.release_candidate_readiness import run_rc1_readiness


def _revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate Civora RC1 technical, operational, human, legal, and billing gates.")
    parser.add_argument("--evidence-manifest", default="reports/release/rc1-evidence-manifest.json")
    parser.add_argument("--hosted-operational-evidence", default="reports/release/hosted-operational-evidence.json")
    parser.add_argument("--output", default="reports/release/rc1-readiness-report.json")
    parser.add_argument("--fail-on-technical-blocked", action="store_true")
    parser.add_argument("--fail-on-release-blocked", action="store_true")
    args = parser.parse_args()

    report = run_rc1_readiness(
        evidence_manifest_path=Path(args.evidence_manifest),
        hosted_operational_evidence_path=Path(args.hosted_operational_evidence),
        output_path=Path(args.output),
        revision=_revision(),
    )
    print(
        json.dumps(
            {
                "technical_rc_ready": report["technical_rc_ready"],
                "controlled_invite_only_release_allowed": report["controlled_invite_only_release_allowed"],
                "controlled_paid_release_allowed": report["controlled_paid_release_allowed"],
                "public_beta_allowed": report["public_beta_allowed"],
                "technical_blocker_count": len(report["technical_blockers"]),
                "operational_blocker_count": len(report["operational_blockers"]),
                "human_blocker_count": len(report["human_blockers"]),
                "billing_blocker_count": len(report["billing_blockers"]),
                "output": args.output,
            },
            sort_keys=True,
        )
    )
    if args.fail_on_technical_blocked and not report["technical_rc_ready"]:
        raise SystemExit(1)
    if args.fail_on_release_blocked and not report["controlled_invite_only_release_allowed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
