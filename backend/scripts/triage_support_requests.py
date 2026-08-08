from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.database import Database
from backend.services.support_store import SUPPORT_STATUSES, SupportStore


def main() -> None:
    parser = argparse.ArgumentParser(description="List and update persisted Civora support requests.")
    parser.add_argument(
        "--db-path",
        default=str(Path(os.getenv("PERFORMANCE_AI_STORAGE_DIR") or ROOT / "data") / "performance_ai.db"),
    )
    parser.add_argument("--status", default="", choices=("", *sorted(SUPPORT_STATUSES)))
    parser.add_argument("--severity", default="", choices=("", "p0", "p1", "p2", "p3"))
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--request-id", default="")
    parser.add_argument("--set-status", default="", choices=("", *sorted(SUPPORT_STATUSES)))
    parser.add_argument(
        "--fail-on-urgent",
        action="store_true",
        help="Exit nonzero when unresolved P0/P1 requests are present.",
    )
    args = parser.parse_args()

    store = SupportStore(Database(Path(args.db_path), database_url=os.getenv("DATABASE_URL")))
    updated = None
    if args.set_status:
        if not args.request_id:
            raise SystemExit("--request-id is required with --set-status.")
        updated = store.update_status(request_id=args.request_id, status=args.set_status)
    requests = store.list_for_operations(
        status=args.status,
        severity=args.severity,
        limit=args.limit,
    )
    urgent = [
        record
        for record in requests
        if record.get("severity") in {"p0", "p1"} and record.get("status") not in {"resolved", "closed"}
    ]
    print(
        json.dumps(
            {
                "success": True,
                "updated_request": (
                    {
                        "request_id": updated["request_id"],
                        "status": updated["status"],
                        "updated_at": updated["updated_at"],
                    }
                    if updated
                    else None
                ),
                "request_count": len(requests),
                "urgent_open_count": len(urgent),
                "requests": requests,
            },
            indent=2,
            sort_keys=True,
        )
    )
    raise SystemExit(1 if args.fail_on_urgent and urgent else 0)


if __name__ == "__main__":
    main()
