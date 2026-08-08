from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping


ROLLBACK_REHEARSAL_VERSION = "civora_code_rollback_rehearsal_v1"


def build_code_rollback_rehearsal_report(
    *,
    current_revision: str,
    candidate_revision: str,
    candidate_is_ancestor: bool,
    candidate_retrieved: bool,
    candidate_worktree_clean: bool,
    critical_paths: Mapping[str, bool],
    verification_command: str,
    verification_exit_code: int,
    verification_duration_seconds: float,
) -> Dict[str, Any]:
    blockers = []
    if not current_revision or not candidate_revision:
        blockers.append({"code": "rollback_revision_missing", "message": "Current and candidate rollback revisions are required."})
    if current_revision == candidate_revision:
        blockers.append({"code": "rollback_candidate_matches_current", "message": "Choose an earlier known revision for the rollback rehearsal."})
    if not candidate_is_ancestor:
        blockers.append({"code": "rollback_candidate_not_ancestor", "message": "The rollback candidate is not an ancestor of the current revision."})
    if not candidate_retrieved:
        blockers.append({"code": "rollback_candidate_not_retrieved", "message": "The candidate revision could not be checked out in an isolated worktree."})
    if not candidate_worktree_clean:
        blockers.append({"code": "rollback_worktree_not_clean", "message": "The isolated rollback candidate worktree was not clean."})
    missing_paths = sorted(path for path, present in critical_paths.items() if not present)
    if missing_paths:
        blockers.append({"code": "rollback_critical_paths_missing", "message": f"Critical rollback paths are missing: {', '.join(missing_paths)}."})
    if not verification_command:
        blockers.append({"code": "rollback_verification_command_missing", "message": "A safe candidate verification command is required."})
    elif verification_exit_code != 0:
        blockers.append({"code": "rollback_candidate_verification_failed", "message": "The isolated rollback candidate verification command failed."})
    success = not blockers
    return {
        "version": ROLLBACK_REHEARSAL_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "status": "passed" if success else "blocked",
        "current_revision": current_revision,
        "candidate_revision": candidate_revision,
        "candidate_is_ancestor": candidate_is_ancestor,
        "candidate_retrieved": candidate_retrieved,
        "candidate_worktree_clean": candidate_worktree_clean,
        "critical_paths": dict(critical_paths),
        "verification": {
            "command": verification_command,
            "exit_code": verification_exit_code,
            "duration_seconds": round(float(verification_duration_seconds), 3),
        },
        "blockers": blockers,
        "hosted_deployment_changed": False,
        "database_changed": False,
        "provider_rollback_proven": False,
        "construction_ready": False,
        "truth_label": "This is a non-destructive code retrieval and verification rehearsal. It does not deploy the candidate, change hosted infrastructure, restore a database, or prove provider rollback controls.",
    }


__all__ = ["ROLLBACK_REHEARSAL_VERSION", "build_code_rollback_rehearsal_report"]
