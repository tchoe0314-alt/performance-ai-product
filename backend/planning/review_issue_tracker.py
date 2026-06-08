from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .candidate_review_inbox import build_candidate_review_inbox
from .common import safe_dict, safe_list, safe_str
from .smart_fix import build_smart_fix_recommendations


ISSUE_TRACKER_VERSION = "review_issue_tracker_v1"

ISSUE_STATUSES = {"open", "in_review", "resolved", "reopened", "waived_review_required"}
OPEN_STATUSES = {"open", "in_review", "reopened"}
SEVERITY_ORDER = {"blocker": 0, "critical": 1, "error": 2, "warning": 3, "review": 4, "info": 5}

DISCIPLINE_ALIASES: Dict[str, Sequence[str]] = {
    "grading": ("grading", "surface", "slope", "pad", "earthwork", "contour"),
    "drainage": ("drainage", "storm", "basin", "outfall", "inlet", "hydraulic", "hydrology", "pond"),
    "sanitary": ("sanitary", "sewer"),
    "water": ("water", "hydrant", "fire_flow", "pressure"),
    "roadway": ("roadway", "road", "corridor", "access", "intersection", "ada", "sidewalk"),
    "utilities": ("utility", "utilities", "coordination", "conflict"),
    "standards": ("standard", "rule", "source_registry"),
    "existing_conditions": ("existing", "survey", "terrain", "control", "datum", "gis", "candidate"),
    "exports": ("export", "deliverable", "sheet", "dxf", "landxml", "report", "package"),
    "qa": ("qa", "manual_validation", "convergence", "reviewer", "comment"),
}

DISCIPLINE_ASSIGNEE = {
    "grading": "grading_reviewer",
    "drainage": "drainage_reviewer",
    "sanitary": "utility_reviewer",
    "water": "utility_reviewer",
    "roadway": "roadway_reviewer",
    "utilities": "utility_reviewer",
    "standards": "standards_reviewer",
    "existing_conditions": "source_reviewer",
    "exports": "deliverables_reviewer",
    "qa": "qa_reviewer",
    "general": "project_reviewer",
}

TRACKER_TRUTH_LABEL = (
    "Review issues are workflow records for blockers, comments, QA, exports, candidates, and system depth. "
    "Resolved only means the issue record was closed; field use remains outside Civora. "
    "Waived items require an explicit review-required waiver record."
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slug(value: Any, fallback: str = "issue") -> str:
    text = safe_str(value, fallback).lower()
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in text)
    return "_".join(part for part in cleaned.split("_") if part) or fallback


def _stable_id(*parts: Any) -> str:
    seed = "|".join(safe_str(part) for part in parts if safe_str(part))
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    return f"rit_{digest}"


def _dedupe_text(values: Iterable[Any], *, limit: int = 12) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = safe_str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _flatten_text(value: Any, *, limit: int = 8) -> List[str]:
    if isinstance(value, dict):
        texts: List[str] = []
        for key, item in value.items():
            if safe_str(key).lower() in {
                "id",
                "object_id",
                "object_ids",
                "sheet_id",
                "sheet_number",
                "system",
                "system_id",
                "field",
                "area",
                "code",
                "message",
                "reason",
                "why_needed",
                "comment",
                "next_action",
                "suggested_next_action",
            }:
                texts.extend(_flatten_text(item, limit=limit))
            elif isinstance(item, (dict, list)):
                texts.extend(_flatten_text(item, limit=limit))
            if len(texts) >= limit:
                break
        return _dedupe_text(texts, limit=limit)
    if isinstance(value, list):
        texts = []
        for item in value:
            texts.extend(_flatten_text(item, limit=limit))
            if len(texts) >= limit:
                break
        return _dedupe_text(texts, limit=limit)
    text = safe_str(value)
    return [text] if text else []


def _stringify_record(value: Any) -> str:
    if isinstance(value, dict):
        return safe_str(
            value.get("message")
            or value.get("reason")
            or value.get("why_needed")
            or value.get("comment")
            or value.get("field")
            or value.get("code")
            or value.get("label")
        )
    return safe_str(value)


def _severity(value: Any, *, fallback: str = "review") -> str:
    text = safe_str(value, fallback).lower()
    if text in {"missing_input", "blocked"}:
        return "blocker"
    if text in {"blocker", "critical", "error", "warning", "review", "info"}:
        return text
    if "block" in text:
        return "blocker"
    if "warn" in text:
        return "warning"
    if "error" in text or "fail" in text:
        return "error"
    return fallback


def _discipline(*values: Any) -> str:
    text = " ".join(safe_str(value).lower() for value in values if safe_str(value))
    for discipline, aliases in DISCIPLINE_ALIASES.items():
        if discipline in text or any(alias in text for alias in aliases):
            return discipline
    return "general"


def _links(record: Dict[str, Any], *, source_key: str, discipline: str) -> Dict[str, List[str]]:
    object_ids = _dedupe_text(
        _flatten_text(
            [
                record.get("object_id"),
                record.get("object_ids"),
                record.get("canonical_id"),
                record.get("canonical_ids"),
                record.get("source_object_id"),
                record.get("candidate_id"),
                record.get("accepted_as"),
                record.get("pipe_id"),
                record.get("structure_id"),
                record.get("surface_id"),
            ]
        )
    )
    sheet_ids = _dedupe_text(_flatten_text([record.get("sheet_id"), record.get("sheet_ids"), record.get("sheet_number")]))
    system_ids = _dedupe_text(
        _flatten_text([record.get("system"), record.get("system_id"), record.get("engine_id"), record.get("area"), discipline])
    )
    return {
        "object_ids": object_ids,
        "sheet_ids": sheet_ids,
        "system_ids": system_ids,
        "source_keys": [source_key],
    }


def _comment(
    *,
    author: str,
    body: str,
    action: str,
    created_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "comment_id": _stable_id(author, body, action, created_at or _now()),
        "author": author,
        "created_at": created_at or _now(),
        "body": body,
        "action": action,
        "metadata": deepcopy(metadata or {}),
    }


def _history(action: str, *, actor: str, note: str, status: str, created_at: Optional[str] = None) -> Dict[str, Any]:
    return {
        "history_id": _stable_id(action, actor, note, created_at or _now()),
        "created_at": created_at or _now(),
        "actor": actor,
        "action": action,
        "status": status,
        "note": note,
    }


def _issue_from_record(
    record: Any,
    *,
    source_key: str,
    default_severity: str,
    default_discipline: str = "",
    title_prefix: str = "",
    created_at: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    rec = safe_dict(record)
    text = _stringify_record(record)
    if not text:
        return None
    code = safe_str(rec.get("code") or rec.get("field") or rec.get("id") or rec.get("candidate_id") or _slug(text))
    discipline = safe_str(rec.get("discipline")) or _discipline(default_discipline, rec.get("area"), rec.get("field"), code, text)
    severity = _severity(rec.get("severity") or rec.get("status"), fallback=default_severity)
    title = safe_str(rec.get("title") or rec.get("label") or text)
    if title_prefix and not title.lower().startswith(title_prefix.lower()):
        title = f"{title_prefix}: {title}"
    next_action = safe_str(rec.get("next_action") or rec.get("suggested_next_action") or rec.get("blocker_review_reason"))
    issue_id = _stable_id(source_key, code, discipline, text)
    return {
        "issue_id": issue_id,
        "source_key": source_key,
        "source_code": code,
        "title": title[:180],
        "description": text,
        "status": "open",
        "severity": severity,
        "discipline": discipline,
        "assigned_role": safe_str(rec.get("assigned_role") or DISCIPLINE_ASSIGNEE.get(discipline), "project_reviewer"),
        "assigned_to": safe_str(rec.get("assigned_to")),
        "created_at": created_at or _now(),
        "updated_at": created_at or _now(),
        "next_action": next_action or "Review the source record, address the cause, and rerun affected checks.",
        "links": _links(rec, source_key=source_key, discipline=discipline),
        "comments": [
            _comment(
                author=safe_str(rec.get("source") or source_key, "system"),
                body=next_action or text,
                action="created_from_source",
                created_at=created_at,
                metadata={"source_key": source_key},
            )
        ],
        "history": [
            _history(
                "created",
                actor=safe_str(rec.get("source") or source_key, "system"),
                note=f"Created from {source_key}.",
                status="open",
                created_at=created_at,
            )
        ],
        "source_record": deepcopy(rec) if rec else {"value": text},
        "review_required": True,
        "field_use_allowed": False,
    }


def _extend_issues(
    issues: List[Dict[str, Any]],
    records: Iterable[Any],
    *,
    source_key: str,
    default_severity: str,
    default_discipline: str = "",
    title_prefix: str = "",
) -> None:
    for record in records:
        issue = _issue_from_record(
            record,
            source_key=source_key,
            default_severity=default_severity,
            default_discipline=default_discipline,
            title_prefix=title_prefix,
        )
        if issue:
            issues.append(issue)


def _source_records(meta: Dict[str, Any], final_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    _extend_issues(issues, safe_list(meta.get("blockers")) or safe_list(final_plan.get("blockers")), source_key="blockers", default_severity="blocker")
    _extend_issues(issues, safe_list(meta.get("blocker_details")), source_key="blocker_details", default_severity="blocker")
    _extend_issues(issues, safe_list(meta.get("issues")) or safe_list(final_plan.get("issues")), source_key="qa", default_severity="warning", default_discipline="qa")
    _extend_issues(issues, safe_list(meta.get("reviewer_comments")), source_key="reviewer_comments", default_severity="review", default_discipline="qa", title_prefix="Reviewer")

    for failure in safe_list(safe_dict(meta.get("manual_validation")).get("failures")):
        _extend_issues(issues, [failure], source_key="manual_validation", default_severity="error", default_discipline="qa")

    convergence = safe_dict(meta.get("convergence_summary"))
    _extend_issues(issues, safe_list(convergence.get("blocked_reasons")), source_key="qa_convergence", default_severity="blocker", default_discipline="qa")
    _extend_issues(issues, safe_list(convergence.get("blocked_exports")), source_key="qa_exports", default_severity="blocker", default_discipline="exports")

    smart_fix = safe_dict(meta.get("smart_fix_recommendations_v1")) or build_smart_fix_recommendations(final_plan, meta=meta)
    for rec in safe_list(smart_fix.get("recommendations")):
        item = safe_dict(rec)
        if safe_str(item.get("status")).lower() in {"resolved", "done"}:
            continue
        item.setdefault("message", item.get("reason") or item.get("title") or item.get("label"))
        _extend_issues(issues, [item], source_key="smart_fix_recommendations_v1", default_severity="review")

    for key in ("engine_depth_dashboard_v1", "engine_depth_audit", "engine_readiness"):
        record = safe_dict(meta.get(key))
        _extend_issues(issues, safe_list(record.get("blockers")), source_key=key, default_severity="blocker")
        for row in safe_list(record.get("rows")) + safe_list(record.get("engine_rows")) + safe_list(record.get("proof_items")):
            row_rec = safe_dict(row)
            if safe_list(row_rec.get("blockers")):
                _extend_issues(issues, safe_list(row_rec.get("blockers")), source_key=key, default_severity="blocker", default_discipline=row_rec.get("engine_id"))

    depth_validation = safe_dict(meta.get("depth_validation"))
    for discipline, record in depth_validation.items():
        rec = safe_dict(record)
        _extend_issues(issues, safe_list(rec.get("blockers")), source_key="depth_validation", default_severity="blocker", default_discipline=discipline)

    for key in ("export_audit", "export_package_report_v1", "review_package_manifest"):
        record = safe_dict(meta.get(key))
        _extend_issues(issues, safe_list(record.get("blockers")), source_key=key, default_severity="blocker", default_discipline="exports")
        _extend_issues(issues, safe_list(record.get("blocked_reasons")), source_key=key, default_severity="blocker", default_discipline="exports")
        _extend_issues(issues, safe_list(record.get("missing_inputs")), source_key=key, default_severity="blocker", default_discipline="exports")

    review_package = safe_dict(meta.get("engineer_review_package_v1"))
    _extend_issues(issues, safe_list(review_package.get("blockers")), source_key="engineer_review_package_v1", default_severity="blocker")
    _extend_issues(issues, safe_list(review_package.get("missing_inputs")), source_key="engineer_review_package_v1", default_severity="review")
    _extend_issues(issues, safe_list(review_package.get("reviewer_comments")), source_key="engineer_review_package_v1", default_severity="review")

    inbox = safe_dict(meta.get("candidate_review_inbox_v1")) or build_candidate_review_inbox(meta)
    for candidate in safe_list(inbox.get("candidates")):
        rec = safe_dict(candidate)
        if safe_str(rec.get("status")).lower() != "pending":
            continue
        rec.setdefault("message", rec.get("blocker_review_reason") or rec.get("label") or rec.get("candidate_type"))
        _extend_issues(issues, [rec], source_key="candidate_review_inbox_v1", default_severity="review", default_discipline="existing_conditions", title_prefix="Candidate")

    return issues


def _merge_previous(current: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, Any]:
    if not previous:
        return current
    merged = deepcopy(current)
    status = safe_str(previous.get("status"))
    if status in ISSUE_STATUSES:
        merged["status"] = status
    for key in ("assigned_to", "assigned_role"):
        if safe_str(previous.get(key)):
            merged[key] = previous[key]
    merged["comments"] = safe_list(previous.get("comments")) or merged["comments"]
    merged["history"] = safe_list(previous.get("history")) or merged["history"]
    merged["waiver_record"] = deepcopy(safe_dict(previous.get("waiver_record")))
    merged["updated_at"] = safe_str(previous.get("updated_at")) or merged["updated_at"]
    return merged


def _sort_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        issues,
        key=lambda item: (
            0 if safe_str(item.get("status")) in OPEN_STATUSES else 1,
            SEVERITY_ORDER.get(safe_str(item.get("severity")).lower(), 9),
            safe_str(item.get("discipline")),
            safe_str(item.get("title")),
        ),
    )


def _summaries(issues: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, int], Dict[str, int]]:
    by_status: Dict[str, int] = {status: 0 for status in sorted(ISSUE_STATUSES)}
    by_severity: Dict[str, int] = {}
    by_discipline: Dict[str, int] = {}
    for issue in issues:
        status = safe_str(issue.get("status"), "open")
        by_status[status] = by_status.get(status, 0) + 1
        severity = safe_str(issue.get("severity"), "review")
        discipline = safe_str(issue.get("discipline"), "general")
        by_severity[severity] = by_severity.get(severity, 0) + 1
        by_discipline[discipline] = by_discipline.get(discipline, 0) + 1
    return by_status, by_severity, by_discipline


def build_review_issue_tracker(final_plan_or_meta: Optional[Dict[str, Any]] = None, *, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    source = safe_dict(final_plan_or_meta)
    final_plan = source if safe_dict(source.get("meta")) else {}
    plan_meta = deepcopy(meta if meta is not None else safe_dict(final_plan.get("meta")) or source)
    previous_tracker = safe_dict(plan_meta.get(ISSUE_TRACKER_VERSION))
    previous_by_id = {safe_str(item.get("issue_id")): safe_dict(item) for item in safe_list(previous_tracker.get("issues"))}

    deduped: Dict[str, Dict[str, Any]] = {}
    for issue in _source_records(plan_meta, final_plan):
        issue_id = safe_str(issue.get("issue_id"))
        if not issue_id:
            continue
        if issue_id in deduped:
            existing = deduped[issue_id]
            existing["links"]["source_keys"] = _dedupe_text(
                safe_list(existing.get("links", {}).get("source_keys")) + safe_list(issue.get("links", {}).get("source_keys"))
            )
            continue
        deduped[issue_id] = _merge_previous(issue, previous_by_id.get(issue_id, {}))

    # Keep manually created records visible even when their source text is not present in the regenerated payload.
    for issue_id, previous in previous_by_id.items():
        if issue_id not in deduped and safe_str(previous.get("source_key")) == "manual":
            deduped[issue_id] = deepcopy(previous)

    issues = _sort_issues(list(deduped.values()))
    by_status, by_severity, by_discipline = _summaries(issues)
    open_issues = [item for item in issues if safe_str(item.get("status")) in OPEN_STATUSES]
    engineer_review_queue = [
        {
            "issue_id": issue["issue_id"],
            "title": issue["title"],
            "discipline": issue["discipline"],
            "severity": issue["severity"],
            "assigned_role": issue["assigned_role"],
            "next_action": issue["next_action"],
        }
        for issue in open_issues
        if safe_str(issue.get("severity")) in {"blocker", "critical", "error", "review"}
        or safe_str(issue.get("status")) in {"in_review", "reopened"}
    ]
    return {
        "version": ISSUE_TRACKER_VERSION,
        "generated_at": _now(),
        "issue_count": len(issues),
        "open_count": len(open_issues),
        "needs_review_count": len(engineer_review_queue),
        "by_status": by_status,
        "by_severity": by_severity,
        "by_discipline": by_discipline,
        "issues": issues,
        "open_issues": open_issues,
        "engineer_review_queue": engineer_review_queue,
        "status_values": sorted(ISSUE_STATUSES),
        "field_use_allowed": False,
        "truth_label": TRACKER_TRUTH_LABEL,
    }


def _matches_issue(issue: Dict[str, Any], selector: str) -> bool:
    text = safe_str(selector).lower()
    if not text:
        return False
    if text in safe_str(issue.get("issue_id")).lower():
        return True
    haystack = " ".join(
        safe_str(value).lower()
        for value in (
            issue.get("title"),
            issue.get("description"),
            issue.get("discipline"),
            issue.get("source_code"),
            issue.get("source_key"),
        )
        if safe_str(value)
    )
    tokens = [token for token in re.split(r"[^a-z0-9_]+", text) if token and token not in {"issue", "this", "the"}]
    return bool(tokens) and all(token in haystack for token in tokens)


def select_review_issues(tracker: Dict[str, Any], selector: str = "", *, discipline: str = "", status: str = "") -> List[Dict[str, Any]]:
    selected = []
    for issue in safe_list(tracker.get("issues")):
        rec = safe_dict(issue)
        if discipline and safe_str(rec.get("discipline")).lower() != discipline.lower():
            continue
        if status:
            wanted = status.lower()
            issue_status = safe_str(rec.get("status")).lower()
            if wanted == "open":
                if issue_status not in OPEN_STATUSES:
                    continue
            elif issue_status != wanted:
                continue
        if selector and not _matches_issue(rec, selector):
            continue
        selected.append(deepcopy(rec))
    return selected


def apply_review_issue_update(
    meta: Dict[str, Any],
    *,
    action: str,
    selector: str = "",
    issue_id: str = "",
    actor: str = "user",
    note: str = "",
    discipline: str = "",
    assigned_to: str = "",
) -> Dict[str, Any]:
    updated_meta = deepcopy(safe_dict(meta))
    tracker = build_review_issue_tracker(updated_meta)
    target_selector = issue_id or selector
    matches = select_review_issues(tracker, target_selector, discipline=discipline)
    if not matches and issue_id:
        matches = select_review_issues(tracker, issue_id)
    if not matches:
        raise ValueError("No matching review issue was found.")
    if len(matches) > 1 and not issue_id and not discipline:
        raise ValueError("Multiple review issues matched; include an issue id or discipline.")

    target_ids = {safe_str(item.get("issue_id")) for item in matches}
    status_by_action = {
        "resolve": "resolved",
        "reopen": "reopened",
        "in_review": "in_review",
        "waive": "waived_review_required",
    }
    if action not in status_by_action:
        raise ValueError("Unsupported issue action.")
    next_status = status_by_action[action]
    now = _now()
    next_issues = []
    for issue in safe_list(tracker.get("issues")):
        rec = deepcopy(safe_dict(issue))
        if safe_str(rec.get("issue_id")) in target_ids:
            rec["status"] = next_status
            rec["updated_at"] = now
            if assigned_to:
                rec["assigned_to"] = assigned_to
            action_note = note or (
                "Issue workflow item resolved; independent review may still be required."
                if action == "resolve"
                else "Issue reopened for review."
                if action == "reopen"
                else "Review-required waiver recorded; field use remains outside Civora."
                if action == "waive"
                else "Issue moved into review."
            )
            rec.setdefault("comments", [])
            rec["comments"] = safe_list(rec.get("comments")) + [
                _comment(author=actor, body=action_note, action=action, created_at=now)
            ]
            rec.setdefault("history", [])
            rec["history"] = safe_list(rec.get("history")) + [
                _history(action, actor=actor, note=action_note, status=next_status, created_at=now)
            ]
            if action == "waive":
                rec["waiver_record"] = {
                    "waiver_id": _stable_id("waiver", rec.get("issue_id"), actor, now),
                    "created_at": now,
                    "actor": actor,
                    "reason": action_note,
                    "review_required": True,
                    "field_use_allowed": False,
                }
        next_issues.append(rec)
    tracker["issues"] = next_issues
    updated_meta[ISSUE_TRACKER_VERSION] = tracker
    # Rebuild to refresh counts while preserving the status changes above.
    updated_meta[ISSUE_TRACKER_VERSION] = build_review_issue_tracker(updated_meta)
    return {
        "updated_meta": updated_meta,
        ISSUE_TRACKER_VERSION: updated_meta[ISSUE_TRACKER_VERSION],
        "updated_issue_ids": sorted(target_ids),
        "status": next_status,
        "truth_label": TRACKER_TRUTH_LABEL,
    }


__all__ = [
    "ISSUE_TRACKER_VERSION",
    "ISSUE_STATUSES",
    "OPEN_STATUSES",
    "build_review_issue_tracker",
    "apply_review_issue_update",
    "select_review_issues",
]
