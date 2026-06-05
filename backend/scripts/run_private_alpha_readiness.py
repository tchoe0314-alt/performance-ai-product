from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.application.private_alpha_readiness_audit import run_private_alpha_backend_readiness_audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Civora backend-only private-alpha readiness evidence audit.")
    parser.add_argument("--base-url", default="", help="Backend URL to sample, e.g. http://127.0.0.1:8000. If omitted, local process monitoring is used and queue evidence remains blocked.")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--interval-seconds", type=float, default=0.0)
    parser.add_argument("--scenario", action="append", dest="scenarios", help="Golden scenario ID to run. Repeat for multiple scenarios. Omit to run all.")
    parser.add_argument("--output", default="reports/alpha/private_alpha_backend_readiness_report.json")
    parser.add_argument("--max-rss-mb", type=float, default=None)
    parser.add_argument("--max-peak-rss-mb", type=float, default=None)
    parser.add_argument("--max-recent-start-count", type=float, default=None)
    parser.add_argument("--max-failed-recent-count", type=float, default=None)
    parser.add_argument("--max-stale-job-count", type=float, default=None)
    parser.add_argument("--max-oldest-active-age-sec", type=float, default=None)
    args = parser.parse_args()

    threshold_values = {
        "max_rss_mb": args.max_rss_mb,
        "max_peak_rss_mb": args.max_peak_rss_mb,
        "max_recent_start_count": args.max_recent_start_count,
        "max_failed_recent_count": args.max_failed_recent_count,
        "max_stale_job_count": args.max_stale_job_count,
        "max_oldest_active_age_sec": args.max_oldest_active_age_sec,
    }
    thresholds = {key: value for key, value in threshold_values.items() if value is not None}
    report = run_private_alpha_backend_readiness_audit(
        iterations=args.iterations,
        interval_seconds=args.interval_seconds,
        base_url=args.base_url,
        scenario_ids=args.scenarios,
        output_path=Path(args.output),
        thresholds=thresholds or None,
    )
    print(
        json.dumps(
            {
                "success": report["success"],
                "status": report["status"],
                "private_alpha_backend_ready": report["private_alpha_backend_ready"],
                "construction_release_allowed": report["construction_release_allowed"],
                "blocker_count": report["blocker_count"],
                "golden_scenario_count": report["sections"]["golden_scenarios"]["scenario_count"],
                "monitoring_sample_count": report["sections"]["monitoring"]["sample_count"],
                "output": args.output,
            },
            sort_keys=True,
        )
    )
    raise SystemExit(0 if report["success"] else 1)


if __name__ == "__main__":
    main()
