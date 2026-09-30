from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.application.commercial_site_benchmark import (
    build_independent_review_template,
    run_commercial_site_benchmark,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Civora's first commercial-site reference benchmark.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/validation/commercial-pad-001.json"),
        help="Benchmark report path.",
    )
    parser.add_argument(
        "--review-evidence",
        type=Path,
        help="Optional independent-review evidence JSON bound to the benchmark inputs and exact software revision.",
    )
    parser.add_argument(
        "--write-review-template",
        type=Path,
        help="Write a fail-closed reviewer worksheet bound to this run's revision and input hashes.",
    )
    args = parser.parse_args()
    report = run_commercial_site_benchmark(
        output_path=args.output,
        review_evidence_path=args.review_evidence,
    )
    if args.write_review_template:
        args.write_review_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_review_template.write_text(
            json.dumps(build_independent_review_template(report), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "automated_passed": report["automated_passed"],
                "automated_status": report["automated_status"],
                "benchmark_id": report["benchmark_id"],
                "failed_comparisons": report["failed_comparisons"],
                "independent_review_status": report["independent_review_status"],
                "output": str(args.output),
                "review_template": str(args.write_review_template) if args.write_review_template else None,
                "pilot_validation_status": report["pilot_validation_status"],
                "software_revision": report["software_revision"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["automated_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
