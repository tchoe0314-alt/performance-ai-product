from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.application.end_state_capability_validation import (
    build_end_state_validation_gates,
    run_end_state_capability_validation,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Civora's repeatable end-state capability validation without promoting external evidence to a pass.",
    )
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--skip-browser", action="store_true")
    parser.add_argument("--hosted-url", default="")
    parser.add_argument("--include-hosted-auth", action="store_true")
    parser.add_argument("--gate", action="append", dest="gates", help="Run one named gate; repeat to run multiple gates.")
    parser.add_argument("--list", action="store_true", help="List available gates and exit.")
    parser.add_argument("--output", default="reports/validation/end_state_capability_validation.json")
    args = parser.parse_args()

    available = build_end_state_validation_gates(
        include_frontend=not args.skip_frontend,
        include_browser=not args.skip_browser,
        hosted_url=args.hosted_url,
        include_hosted_auth=args.include_hosted_auth,
    )
    if args.list:
        print(json.dumps([{"gate_id": item["gate_id"], "label": item["label"]} for item in available], indent=2))
        return

    report = run_end_state_capability_validation(
        include_frontend=not args.skip_frontend,
        include_browser=not args.skip_browser,
        hosted_url=args.hosted_url,
        include_hosted_auth=args.include_hosted_auth,
        selected_gate_ids=args.gates,
        output_path=Path(args.output),
    )
    print(
        json.dumps(
            {
                "success": report["success"],
                "status": report["status"],
                "passed_gate_count": report["passed_gate_count"],
                "gate_count": report["gate_count"],
                "failed_gate_ids": report["failed_gate_ids"],
                "external_evidence_complete": report["external_evidence_complete"],
                "output_path": report.get("output_path"),
            },
            sort_keys=True,
        )
    )
    raise SystemExit(0 if report["success"] else 1)


if __name__ == "__main__":
    main()
