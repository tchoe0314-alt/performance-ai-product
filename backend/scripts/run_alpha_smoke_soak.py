from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.application.alpha_smoke_soak import run_alpha_smoke_soak


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Civora private-alpha backend smoke/soak monitoring.")
    parser.add_argument("--base-url", default="", help="Backend URL to sample, e.g. http://127.0.0.1:8000. If omitted, local process monitoring is used and queue evidence remains blocked.")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--interval-seconds", type=float, default=0.0)
    parser.add_argument("--output", default="data/alpha_smoke_soak_report.json")
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
    report = run_alpha_smoke_soak(
        iterations=args.iterations,
        interval_seconds=args.interval_seconds,
        base_url=args.base_url,
        output_path=Path(args.output),
        thresholds=thresholds or None,
    )
    print(json.dumps({
        "success": report["success"],
        "status": report["status"],
        "sample_count": report["sample_count"],
        "sample_failure_count": report["sample_failure_count"],
        "output": args.output,
        "alpha_monitoring_readiness": report["alpha_monitoring_report"].get("readiness"),
    }, sort_keys=True))
    raise SystemExit(0 if report["success"] else 1)


if __name__ == "__main__":
    main()
