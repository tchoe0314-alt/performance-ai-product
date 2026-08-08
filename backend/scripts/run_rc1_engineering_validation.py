from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.application.rc1_engineering_validation import run_rc1_engineering_validation


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Civora RC1 engineering scenarios and real-file expected-versus-actual comparisons.")
    parser.add_argument("--output", default="reports/release/rc1-engineering-validation.json")
    args = parser.parse_args()
    report = run_rc1_engineering_validation(output_path=Path(args.output))
    print(
        json.dumps(
            {
                "success": report["success"],
                "status": report["status"],
                "scenario_count": report["scenario_count"],
                "real_file_fixture_count": report["real_file_fixture_count"],
                "comparison_count": report["automated_expected_actual_comparison_count"],
                "failed_comparison_count": report["failed_comparison_count"],
                "output": args.output,
            },
            sort_keys=True,
        )
    )
    raise SystemExit(0 if report["success"] else 1)


if __name__ == "__main__":
    main()
