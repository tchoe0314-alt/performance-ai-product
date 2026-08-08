from __future__ import annotations

import argparse
import json
from pathlib import Path
import os
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.backup_restore import DatabaseBackupService
from backend.services.database import Database


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a truthful Civora database backup and restore evidence drill.")
    parser.add_argument(
        "--db-path",
        default=str(Path(os.getenv("PERFORMANCE_AI_STORAGE_DIR") or ROOT / "data") / "performance_ai.db"),
        help="SQLite database path. Hosted PostgreSQL uses DATABASE_URL and requires provider evidence env vars.",
    )
    parser.add_argument("--output-dir", default="reports/release/backup")
    parser.add_argument("--report", default="reports/release/backup_restore_report.json")
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    db = Database(Path(args.db_path), database_url=os.getenv("DATABASE_URL"))
    report = DatabaseBackupService(db).run_restore_drill(
        output_dir=Path(args.output_dir),
        report_path=Path(args.report),
    )
    print(
        json.dumps(
            {
                "success": report["success"],
                "status": report["status"],
                "storage_kind": report["storage_kind"],
                "local_restore_drill_performed": report["local_restore_drill_performed"],
                "report": args.report,
            },
            sort_keys=True,
        )
    )
    raise SystemExit(1 if args.fail_on_blocked and not report["success"] else 0)


if __name__ == "__main__":
    main()
