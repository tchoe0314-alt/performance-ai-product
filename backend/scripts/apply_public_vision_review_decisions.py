from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from backend.planning.candidate_review_inbox import apply_candidate_review_decision
from backend.planning.common import safe_dict, safe_list, safe_str
from backend.planning.vision_ground_truth_flywheel import (
    DATASET_VERSION,
    LEDGER_VERSION,
    WORKSPACE_VERSION,
    verify_ground_truth_ledger,
)
from backend.planning.vision_public_bootstrap import verify_public_review_sprint


DECISIONS_VERSION = "civora_public_vision_review_decisions_v1"


def review_decisions_fingerprint(decisions: Dict[str, Any]) -> str:
    rows = []
    for item in safe_list(decisions.get("decisions")):
        row = safe_dict(item)
        if not row:
            continue
        rows.append(
            {
                "action": safe_str(row.get("action")),
                "candidate_id": safe_str(row.get("candidate_id")),
                "reason": safe_str(row.get("reason")),
            }
        )
    payload = {
        "decisions": rows,
        "exported_at": safe_str(decisions.get("exported_at")),
        "review_sprint_fingerprint": safe_str(decisions.get("review_sprint_fingerprint")),
        "reviewer_id": safe_str(decisions.get("reviewer_id")),
        "source_frame_review_attested": decisions.get("source_frame_review_attested") is True,
        "version": safe_str(decisions.get("version")),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply explicitly attested public-image review decisions to Civora's immutable ground-truth ledger."
    )
    parser.add_argument("--review-sprint", required=True, type=Path)
    parser.add_argument("--decisions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = apply_review_decisions(
        review_sprint=_read_object(args.review_sprint),
        decisions=_read_object(args.decisions),
    )
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "success": True,
                "output": str(output),
                "reviewed_decisions": result["reviewed_decision_count"],
                "accepted": result["accepted_count"],
                "rejected": result["rejected_count"],
                "ground_truth_annotations": result[DATASET_VERSION]["annotation_count"],
                "ground_truth_export_ready": result[DATASET_VERSION]["export_ready"],
            },
            indent=2,
        )
    )
    return 0


def apply_review_decisions(*, review_sprint: Dict[str, Any], decisions: Dict[str, Any]) -> Dict[str, Any]:
    sprint_validation = verify_public_review_sprint(review_sprint)
    if not sprint_validation["valid"]:
        raise ValueError("Review sprint failed verification: " + ", ".join(sprint_validation["blockers"]))
    if safe_str(decisions.get("version")) != DECISIONS_VERSION:
        raise ValueError("Unsupported public vision review decision version.")
    if safe_str(decisions.get("review_sprint_fingerprint")) != safe_str(review_sprint.get("review_sprint_fingerprint")):
        raise ValueError("Review decisions do not match this review sprint fingerprint.")
    exported_at = safe_str(decisions.get("exported_at"))
    if not exported_at:
        raise ValueError("Review decisions must include an export timestamp.")
    try:
        datetime.fromisoformat(exported_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Review decisions export timestamp is invalid.") from exc
    if safe_str(decisions.get("decisions_fingerprint")) != review_decisions_fingerprint(decisions):
        raise ValueError("Review decisions fingerprint mismatch.")
    reviewer_id = safe_str(decisions.get("reviewer_id"))
    if not reviewer_id:
        raise ValueError("A named reviewer ID is required.")
    if decisions.get("source_frame_review_attested") is not True:
        raise ValueError("The reviewer must attest that each submitted proposal was inspected against its source frame.")
    rows = [safe_dict(item) for item in safe_list(decisions.get("decisions")) if safe_dict(item)]
    if not rows:
        raise ValueError("At least one accept or reject decision is required.")
    candidate_ids = [safe_str(item.get("candidate_id")) for item in rows]
    if any(not item for item in candidate_ids) or len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("Review decision candidate IDs must be present and unique.")
    if any(safe_str(item.get("action")) not in {"accept", "reject"} for item in rows):
        raise ValueError("Public gallery decisions may only accept or reject; redraw corrections belong in Civora Draw.")
    sprint_meta = safe_dict(review_sprint.get("meta"))
    sprint_inbox = safe_dict(sprint_meta.get("candidate_review_inbox_v1"))
    known_candidate_ids = {
        safe_str(safe_dict(item).get("candidate_id"))
        for item in safe_list(sprint_inbox.get("candidates"))
        if safe_str(safe_dict(item).get("candidate_id"))
    }
    unknown_candidate_ids = sorted(set(candidate_ids) - known_candidate_ids)
    if unknown_candidate_ids:
        raise ValueError("Review decisions contain candidates outside this sprint: " + ", ".join(unknown_candidate_ids))
    meta = deepcopy(sprint_meta)
    for row in rows:
        result = apply_candidate_review_decision(
            meta,
            candidate_ids=[safe_str(row.get("candidate_id"))],
            action=safe_str(row.get("action")),
            reviewer_id=reviewer_id,
            reason=safe_str(row.get("reason"), "Reviewed against the registered public source frame."),
        )
        meta = dict(safe_dict(result.get("updated_meta")))
    accepted = sum(1 for item in rows if safe_str(item.get("action")) == "accept")
    rejected = len(rows) - accepted
    ledger = safe_dict(meta.get(LEDGER_VERSION))
    ledger_validation = verify_ground_truth_ledger(ledger)
    if not ledger_validation["valid"]:
        raise ValueError("Ground-truth ledger failed verification after applying review decisions.")
    return {
        "version": "civora_public_vision_review_result_v1",
        "source_review_sprint_fingerprint": safe_str(review_sprint.get("review_sprint_fingerprint")),
        "reviewer_id": reviewer_id,
        "source_frame_review_attested": True,
        "reviewed_decision_count": len(rows),
        "accepted_count": accepted,
        "rejected_count": rejected,
        "source_decisions_fingerprint": safe_str(decisions.get("decisions_fingerprint")),
        LEDGER_VERSION: ledger,
        DATASET_VERSION: safe_dict(meta.get(DATASET_VERSION)),
        WORKSPACE_VERSION: safe_dict(meta.get(WORKSPACE_VERSION)),
        "meta": meta,
        "promotion_eligible": False,
        "truth_label": (
            "This result contains reviewer-attributed training evidence. Model promotion remains separately blocked by "
            "coverage, held-out quality, artifact, and named approval gates."
        ),
}


__all__ = ["DECISIONS_VERSION", "apply_review_decisions", "review_decisions_fingerprint"]


def _read_object(path: Path) -> Dict[str, Any]:
    value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"Expected a JSON object: {path}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
