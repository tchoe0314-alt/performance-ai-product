from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.application.golden_load_benchmarks import run_golden_load_benchmarks


def main() -> None:
    parser = argparse.ArgumentParser(description="Run backend-only golden scenario load/soak benchmarks.")
    parser.add_argument("--scenario", action="append", dest="scenarios", help="Golden scenario ID to run. Repeat for multiple scenarios. Omit to run the default load benchmark set.")
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--interval-seconds", type=float, default=0.0)
    parser.add_argument("--benchmark-seed", default="golden-load-v1")
    parser.add_argument("--output", default="reports/benchmarks/golden_load_benchmark_report.json")
    parser.add_argument("--max-elapsed-ms", type=float, default=None)
    parser.add_argument("--max-rss-mb", type=float, default=None)
    parser.add_argument("--max-peak-rss-mb", type=float, default=None)
    parser.add_argument("--scenario-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--skip-heavy-real-file-scenarios", action="store_true")
    parser.add_argument("--engine-depth-audit-report", default="", help="Optional path to an engine_depth_audit_report_v1 JSON artifact to reference in the benchmark report.")
    args = parser.parse_args()

    threshold_values = {
        "max_elapsed_ms": args.max_elapsed_ms,
        "max_rss_mb": args.max_rss_mb,
        "max_peak_rss_mb": args.max_peak_rss_mb,
    }
    thresholds = {key: value for key, value in threshold_values.items() if value is not None}
    report = run_golden_load_benchmarks(
        scenario_ids=args.scenarios,
        iterations=args.iterations,
        interval_seconds=args.interval_seconds,
        benchmark_seed=args.benchmark_seed,
        output_path=Path(args.output),
        load_threshold_overrides=thresholds or None,
        scenario_timeout_seconds=args.scenario_timeout_seconds,
        skip_heavy_real_file_scenarios=args.skip_heavy_real_file_scenarios,
        engine_depth_audit_report_path=Path(args.engine_depth_audit_report) if args.engine_depth_audit_report else None,
    )
    print(
        json.dumps(
            {
                "success": report["success"],
                "status": report["status"],
                "scenario_count": report["scenario_count"],
                "iteration_count": report["iteration_count"],
                "total_run_count": report["total_run_count"],
                "blocker_count": report["blocker_count"],
                "runtime_ms": report["runtime_ms"],
                "scenario_timeout_seconds": report["scenario_timeout_seconds"],
                "engine_depth_audit_attached": report["engine_depth_audit_reference"]["attached"],
                "output": args.output,
            },
            sort_keys=True,
        )
    )
    raise SystemExit(0 if report["success"] else 1)


if __name__ == "__main__":
    main()
