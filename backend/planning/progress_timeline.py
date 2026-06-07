from __future__ import annotations

from typing import Any, Dict, List, Optional

from .candidate_review_inbox import build_candidate_review_inbox
from .setup_wizard import build_setup_wizard_state


PROGRESS_TIMELINE_VERSION = "progress_timeline_v1"

TIMELINE_STEP_ORDER = [
    "setup",
    "sources",
    "candidates",
    "design_objects",
    "systems",
    "qa",
    "review_package",
    "deliverables",
]

VALID_TIMELINE_STATUSES = {"completed", "blocked", "needs_review", "current", "pending", "not_started"}


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return list(value) if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value > 0
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return False


def _dedupe(values: List[Any], limit: int = 6) -> List[str]:
    out: List[str] = []
    for value in values:
        if isinstance(value, dict):
            text = _text(value.get("message") or value.get("reason") or value.get("code") or value.get("field"))
        else:
            text = _text(value)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _record_blockers(*records: Dict[str, Any], limit: int = 6) -> List[str]:
    values: List[Any] = []
    for record in records:
        for key in ("blockers", "warnings", "missing_inputs", "blocked_reasons", "blocked_exports", "failures"):
            values.extend(_safe_list(record.get(key)))
    return _dedupe(values, limit=limit)


def _wizard_step(wizard: Dict[str, Any], step_id: str) -> Dict[str, Any]:
    for item in _safe_list(wizard.get("steps")):
        rec = _safe_dict(item)
        if _text(rec.get("id")) == step_id:
            return rec
    return {}


def _wizard_blockers(wizard: Dict[str, Any], step_ids: List[str]) -> List[str]:
    blockers: List[str] = []
    for step_id in step_ids:
        rec = _wizard_step(wizard, step_id)
        if not rec:
            continue
        if _text(rec.get("status")) == "blocked":
            blockers.extend([rec.get("why_blocked"), rec.get("next_action")])
    return _dedupe(blockers)


def _wizard_has_status(wizard: Dict[str, Any], step_ids: List[str], statuses: set[str]) -> bool:
    return any(_text(_wizard_step(wizard, step_id).get("status")) in statuses for step_id in step_ids)


def _wizard_completed(wizard: Dict[str, Any], step_ids: List[str]) -> bool:
    return all(_text(_wizard_step(wizard, step_id).get("status")) == "complete" for step_id in step_ids)


def _normalize_status(status: str) -> str:
    return status if status in VALID_TIMELINE_STATUSES else "pending"


def _step(
    *,
    step_id: str,
    label: str,
    status: str,
    summary: str,
    action_label: str,
    action_panel: str,
    blockers: Optional[List[str]] = None,
    source_refs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    clean_blockers = _dedupe(blockers or [])
    normalized = _normalize_status(status)
    if clean_blockers and normalized not in {"completed", "needs_review"}:
        normalized = "blocked"
    return {
        "id": step_id,
        "label": label,
        "status": normalized,
        "summary": summary,
        "blockers": clean_blockers,
        "action_label": action_label,
        "action_panel": action_panel,
        "action": {
            "type": "open_panel",
            "target": action_panel,
            "label": action_label,
        },
        "source_refs": list(source_refs or []),
    }


def _deliverable_lists(meta: Dict[str, Any], latest_result: Dict[str, Any]) -> Dict[str, List[str]]:
    deliverables = _safe_dict(meta.get("deliverables"))
    release_review = _safe_dict(meta.get("release_review"))
    requested = _dedupe(
        _safe_list(deliverables.get("requested"))
        + _safe_list(release_review.get("requested_deliverables"))
        + _safe_list(latest_result.get("requested_deliverables")),
        limit=20,
    )
    produced = _dedupe(
        _safe_list(deliverables.get("produced"))
        + _safe_list(meta.get("produced_deliverables"))
        + _safe_list(release_review.get("produced_deliverables"))
        + _safe_list(latest_result.get("produced_deliverables")),
        limit=20,
    )
    failed = _dedupe(
        _safe_list(deliverables.get("failed"))
        + _safe_list(meta.get("failed_deliverables"))
        + _safe_list(release_review.get("failed_deliverables"))
        + _safe_list(latest_result.get("failed_deliverables")),
        limit=20,
    )
    missing = _dedupe(
        _safe_list(deliverables.get("missing"))
        + _safe_list(release_review.get("missing_deliverables"))
        + _safe_list(latest_result.get("missing_deliverables")),
        limit=20,
    )
    produced_set = set(produced)
    failed_set = set(failed)
    missing.extend(item for item in requested if item not in produced_set and item not in failed_set and item not in missing)
    return {"requested": requested, "produced": produced, "failed": failed, "missing": missing}


def build_progress_timeline(
    *,
    project_input: Optional[Dict[str, Any]] = None,
    latest_result: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    project_input = _safe_dict(project_input)
    latest_result = _safe_dict(latest_result)
    context = _safe_dict(context)
    final_plan = _safe_dict(latest_result.get("final_plan"))
    meta = _safe_dict(final_plan.get("meta") or latest_result.get("metadata") or latest_result.get("meta"))
    wizard = _safe_dict(meta.get("setup_wizard_state_v1")) or build_setup_wizard_state(
        project_input=project_input,
        latest_result=latest_result,
        context=context,
    )
    inbox = _safe_dict(meta.get("candidate_review_inbox_v1")) or build_candidate_review_inbox(meta)

    export_audit = _safe_dict(meta.get("export_audit") or meta.get("export_package_report_v1"))
    review_package = _safe_dict(meta.get("engineer_review_package_v1"))
    release_review = _safe_dict(meta.get("release_review"))
    convergence = _safe_dict(meta.get("convergence_summary") or latest_result.get("convergence_summary"))
    manual_validation = _safe_dict(meta.get("manual_validation"))
    qa_blockers = _record_blockers(convergence, manual_validation, release_review)
    export_blockers = _record_blockers(export_audit, review_package, release_review)
    deliverable_lists = _deliverable_lists(meta, latest_result)

    candidate_counts = _safe_dict(inbox.get("counts"))
    pending_candidates = int(candidate_counts.get("pending") or 0)
    accepted_candidates = int(candidate_counts.get("accepted") or 0)
    candidate_count = int(inbox.get("candidate_count") or pending_candidates + accepted_candidates + int(candidate_counts.get("rejected") or 0))

    actions = _safe_list(final_plan.get("actions"))
    system_statuses = _safe_dict(context.get("system_statuses"))
    has_fresh_system = bool(actions) or any(_text(value).lower() == "fresh" for value in system_statuses.values())
    has_review_package = bool(review_package or export_audit or release_review)
    has_deliverables = bool(deliverable_lists["produced"])

    setup_status = (
        "blocked"
        if _wizard_has_status(wizard, ["address_location", "site_boundary"], {"blocked", "not_started"})
        else "needs_review"
        if _wizard_has_status(wizard, ["address_location", "site_boundary"], {"needs_review", "pending"})
        else "completed"
        if _wizard_completed(wizard, ["address_location", "site_boundary"])
        else "pending"
    )
    sources_status = (
        "blocked"
        if _wizard_has_status(wizard, ["online_sources_candidates", "survey_terrain_control", "standards"], {"blocked"})
        else "needs_review"
        if _wizard_has_status(wizard, ["online_sources_candidates", "survey_terrain_control", "standards"], {"needs_review", "pending"})
        else "completed"
        if _wizard_completed(wizard, ["online_sources_candidates", "survey_terrain_control", "standards"])
        else "pending"
    )
    candidates_status = "not_started"
    if candidate_count:
        candidates_status = "needs_review" if pending_candidates else "completed"
    elif sources_status == "blocked":
        candidates_status = "blocked"
    objects_status = _text(_wizard_step(wizard, "objects_program").get("status"))
    systems_status = _text(_wizard_step(wizard, "run_systems").get("status"))
    qa_status = "blocked" if qa_blockers else "needs_review" if has_fresh_system else "pending"
    review_status = "blocked" if export_blockers else "needs_review" if has_review_package else "pending"
    deliverables_status = (
        "blocked"
        if deliverable_lists["failed"] or deliverable_lists["missing"] or export_blockers
        else "needs_review"
        if has_deliverables
        else "pending"
    )

    steps = [
        _step(
            step_id="setup",
            label="Setup",
            status=setup_status,
            summary="Address, location, and boundary are ready to guide the rest of the project.",
            action_label="Open setup",
            action_panel="site_existing",
            blockers=_wizard_blockers(wizard, ["address_location", "site_boundary"]),
            source_refs=["setup_wizard_state_v1"],
        ),
        _step(
            step_id="sources",
            label="Sources",
            status=sources_status,
            summary="Online sources, survey/control, terrain, and standards evidence are collected for review.",
            action_label="Review sources",
            action_panel="data",
            blockers=_wizard_blockers(wizard, ["online_sources_candidates", "survey_terrain_control", "standards"]),
            source_refs=["setup_wizard_state_v1", "existing_conditions_package", "standards_package"],
        ),
        _step(
            step_id="candidates",
            label="Candidates",
            status=candidates_status,
            summary=f"{pending_candidates} pending, {accepted_candidates} accepted candidate(s).",
            action_label="Review candidates",
            action_panel="data",
            blockers=["Review pending source candidates before relying on them."] if pending_candidates else [],
            source_refs=["candidate_review_inbox_v1", "map_feature_detection_report_v1"],
        ),
        _step(
            step_id="design_objects",
            label="Design Objects",
            status="completed" if objects_status == "complete" else objects_status or "pending",
            summary="Project objects and program are ready when boundary, placements, and program inputs are coherent.",
            action_label="Open objects",
            action_panel="objects",
            blockers=_wizard_blockers(wizard, ["objects_program"]),
            source_refs=["setup_wizard_state_v1", "canonical_draft_geometry"],
        ),
        _step(
            step_id="systems",
            label="Systems",
            status="completed" if systems_status == "complete" else systems_status or "pending",
            summary="Roadway, grading, drainage, and utility systems need fresh run evidence.",
            action_label="Run systems",
            action_panel="generate",
            blockers=_wizard_blockers(wizard, ["run_systems"]),
            source_refs=["phase_checkpoints", "runtime_phase_checkpoint", "system_statuses"],
        ),
        _step(
            step_id="qa",
            label="QA",
            status=qa_status,
            summary="QA tracks unresolved conflicts, warnings, manual checks, and stale outputs.",
            action_label="Open QA",
            action_panel="analysis",
            blockers=qa_blockers,
            source_refs=["convergence_summary", "manual_validation", "release_review"],
        ),
        _step(
            step_id="review_package",
            label="Review Package",
            status=review_status,
            summary="Review package gathers model, sources, assumptions, QA, and export evidence.",
            action_label="Open review package",
            action_panel="reports",
            blockers=export_blockers,
            source_refs=["engineer_review_package_v1", "export_audit", "export_package_report_v1"],
        ),
        _step(
            step_id="deliverables",
            label="Deliverables",
            status=deliverables_status,
            summary=f"{len(deliverable_lists['produced'])} produced, {len(deliverable_lists['missing'])} missing, {len(deliverable_lists['failed'])} failed.",
            action_label="Open deliverables",
            action_panel="deliverables",
            blockers=_dedupe(
                [f"Missing deliverable: {item}" for item in deliverable_lists["missing"]]
                + [f"Failed deliverable: {item}" for item in deliverable_lists["failed"]]
                + export_blockers
            ),
            source_refs=["deliverables", "release_review", "export_audit"],
        ),
    ]

    current_step = next((item for item in steps if item["status"] in {"blocked", "needs_review", "current", "pending", "not_started"}), steps[-1])
    blocked_steps = [item for item in steps if item["status"] == "blocked"]
    needs_review_steps = [item for item in steps if item["status"] == "needs_review"]
    completed_steps = [item for item in steps if item["status"] == "completed"]
    blockers = _dedupe([blocker for step in blocked_steps for blocker in _safe_list(step.get("blockers"))], limit=10)
    next_action = _text(current_step.get("action_label"))
    if _safe_list(current_step.get("blockers")):
        next_action = f"{next_action}: {_safe_list(current_step.get('blockers'))[0]}"

    return {
        "schema_version": PROGRESS_TIMELINE_VERSION,
        "order": list(TIMELINE_STEP_ORDER),
        "steps": steps,
        "current_step_id": current_step["id"],
        "current_step_label": current_step["label"],
        "current_status": current_step["status"],
        "current_panel": current_step["action_panel"],
        "next_action": next_action,
        "exact_blockers": blockers,
        "blocked_step_ids": [item["id"] for item in blocked_steps],
        "needs_review_step_ids": [item["id"] for item in needs_review_steps],
        "completed_count": len(completed_steps),
        "total_count": len(steps),
        "can_export": not bool(export_blockers or deliverable_lists["failed"] or deliverable_lists["missing"]),
        "export_blockers": _dedupe(export_blockers + [f"Missing deliverable: {item}" for item in deliverable_lists["missing"]] + [f"Failed deliverable: {item}" for item in deliverable_lists["failed"]], limit=10),
        "chat_summary": {
            "where_am_i": f"{current_step['label']} ({current_step['status']})",
            "phase": current_step["label"],
            "whats_left": [item["label"] for item in steps if item["status"] != "completed"],
            "why_cant_export_yet": _dedupe(export_blockers + [f"Missing deliverable: {item}" for item in deliverable_lists["missing"]] + [f"Failed deliverable: {item}" for item in deliverable_lists["failed"]], limit=10),
            "what_should_i_do_next": next_action,
        },
        "truth_label": "Timeline is navigation and review state only; it does not replace professional review.",
    }


__all__ = ["PROGRESS_TIMELINE_VERSION", "build_progress_timeline"]
