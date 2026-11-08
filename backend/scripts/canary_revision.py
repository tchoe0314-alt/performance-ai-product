"""Resolve an independent expected release; never trust the service under test.

Update .github/production-revision.txt only after an approved deployment verifies
both services. Push checks always verify the pushed commit. Scheduled checks
verify the pinned production release, not unrelated changes on main.
"""
import os
from pathlib import Path
import re


def resolve_revision(event: str, pushed: str, approved: str, requested: str = "") -> str:
    if event == "push":
        revision = pushed
    elif event == "schedule":
        revision = approved
    elif event == "workflow_dispatch":
        revision = requested.strip() or approved
    else:
        raise ValueError(f"Unsupported canary event: {event}")
    revision = revision.strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
        raise ValueError("Expected release must be a full 40-character Git SHA.")
    return revision.lower()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    print(resolve_revision(
        os.environ.get("GITHUB_EVENT_NAME", ""),
        os.environ.get("GITHUB_SHA", ""),
        (root / ".github/production-revision.txt").read_text(),
        os.environ.get("CANARY_EXPECTED_REVISION", ""),
    ))
