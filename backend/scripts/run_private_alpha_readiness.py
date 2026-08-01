from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.application.private_alpha_readiness_audit import run_private_alpha_backend_readiness_audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Civora backend-only private-alpha readiness evidence audit.")
    parser.add_argument("--base-url", default="", help="Backend URL to sample, e.g. http://127.0.0.1:8000. If omitted, local process monitoring is used and queue evidence remains blocked.")
    parser.add_argument("--runtime-bearer-token", default="", help="Optional Bearer token for authenticated /api/debug/runtime sampling. Prefer env config in shell history.")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--interval-seconds", type=float, default=0.0)
    parser.add_argument("--readiness-mode", default="private_alpha_review", choices=["local_dev", "private_alpha_review", "production"])
    parser.add_argument("--async-jobs-enabled", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--scenario", action="append", dest="scenarios", help="Golden scenario ID to run. Repeat for multiple scenarios. Omit to run all.")
    parser.add_argument("--output", default="reports/alpha/private_alpha_backend_readiness_report.json")
    parser.add_argument("--max-rss-mb", type=float, default=None)
    parser.add_argument("--max-peak-rss-mb", type=float, default=None)
    parser.add_argument("--max-recent-start-count", type=float, default=None)
    parser.add_argument("--max-failed-recent-count", type=float, default=None)
    parser.add_argument("--max-stale-job-count", type=float, default=None)
    parser.add_argument("--max-oldest-active-age-sec", type=float, default=None)
    parser.add_argument("--fail-on-blocked", action="store_true", help="Exit non-zero when readiness is blocked. By default, a completed truthful blocked audit exits zero.")
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
        readiness_mode=args.readiness_mode,
        async_jobs_enabled=args.async_jobs_enabled,
        runtime_bearer_token=args.runtime_bearer_token,
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
                "queue_monitoring_status": report["sections"]["monitoring"]["job_queue_monitoring_evidence"].get("status"),
                "queue_monitoring_setup": report["how_to_clear_queue_monitoring_blocker"],
                "output": args.output,
            },
            sort_keys=True,
        )
    )
    if not report["success"]:
        print(
            "Readiness remains blocked. This command completed the audit but did not mark private-alpha readiness green. "
            "Use --base-url with an authenticated /api/debug/runtime sample to provide real queue monitoring evidence.",
        )
    raise SystemExit(1 if args.fail_on_blocked and not report["success"] else 0)


if __name__ == "__main__":
    main()
