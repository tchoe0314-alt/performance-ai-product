from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from backend.services.data_lifecycle import cleanup_deletion_quarantine


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect or clean account-deletion quarantine directories after database deletion succeeds."
    )
    parser.add_argument(
        "--storage-dir",
        default=str(os.getenv("PERFORMANCE_AI_STORAGE_DIR") or "./data"),
    )
    parser.add_argument("--older-than-hours", type=float, default=24.0)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Remove eligible directories. Without this flag the command is a dry run.",
    )
    parser.add_argument("--fail-on-pending", action="store_true")
    args = parser.parse_args()
    report = cleanup_deletion_quarantine(
        storage_dir=Path(args.storage_dir),
        older_than_hours=args.older_than_hours,
        confirm=args.confirm,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.fail_on_pending and (not report["success"] or (not args.confirm and report["candidate_count"] > 0)):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
