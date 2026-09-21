from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Dict, Iterable, Mapping


FULL_LAUNCH_READINESS_VERSION = "civora_full_launch_readiness_v1"

REQUIRED_TECHNICAL_EVIDENCE = {
    "backend_regression",
    "frontend_quality",
    "security_dependency",
    "engineering_real_files",
    "browser_core",
    "browser_cross_device_accessibility",
    "long_session_concurrency",
    "hosted_end_to_end",
}

REQUIRED_CONFIRMATION_ACTIONS = {
    "accept_detected_conditions",
    "change_accepted_standards",
    "apply_major_design_fix",
    "reroute_engineering_system",
    "delete_protected_object",
    "regenerate_affected_systems",
    "create_review_package",
}

REQUIRED_EXTERNAL_GATES = {
    "independent_engineer_benchmark_review",
    "source_license_and_rights_review",
    "security_assessment",
    "incident_response_owner",
    "support_owner",
    "provider_backup_restore_drill",
    "professional_liability_insurance_review",
    "legal_terms_and_privacy_review",
    "billing_activation_review",
}


def _dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_SENSITIVE_KEY_PARTS = ("password", "token", "secret", "api_key", "authorization", "cookie")


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[redacted]" if any(part in str(key).lower() for part in _SENSITIVE_KEY_PARTS) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return deepcopy(value)


def _current_evidence_date(value: Any, *, max_age_days: int = 365) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return now - timedelta(days=max_age_days) <= parsed <= now + timedelta(days=1)


def _blocker(area: str, code: str, message: str, next_action: str) -> Dict[str, str]:
    return {"area": area, "code": code, "message": message, "next_action": next_action}


def _accepted_external_gate(record: Mapping[str, Any]) -> bool:
    status = _text(record.get("status")).lower()
    evidence_url = _text(record.get("evidence_url"))
    owner = _text(record.get("owner") or record.get("reviewer"))
    evidence_date = _text(record.get("evidence_date") or record.get("review_date"))
    return status in {"accepted", "passed", "verified", "completed"} and evidence_url.startswith("https://") and bool(owner) and _current_evidence_date(evidence_date)


def _comparison_passes(item: Mapping[str, Any]) -> bool:
    try:
        expected = float(item.get("expected"))
        observed = float(item.get("observed"))
        tolerance = float(item.get("tolerance"))
    except (TypeError, ValueError):
        return False
    return tolerance >= 0 and abs(observed - expected) <= tolerance


def _real_project_status(records: Iterable[Mapping[str, Any]], revision: str) -> Dict[str, Any]:
    normalized = []
    for source in records:
        record = _dict(source)
        comparisons = [_dict(item) for item in _list(record.get("comparisons"))]
        comparison_passed = bool(comparisons) and all(_comparison_passes(item) for item in comparisons)
        complete = bool(
            _text(record.get("project_id"))
            and _text(record.get("project_type"))
            and _text(record.get("software_revision")) == revision
            and _list(record.get("input_artifact_hashes"))
            and _text(record.get("reviewer"))
            and _text(record.get("reviewer_qualification"))
            and _current_evidence_date(record.get("review_date"))
            and _text(record.get("disposition")).lower() in {"accepted", "passed"}
            and comparison_passed
        )
        normalized.append({**_redact(record), "complete": complete, "comparison_count": len(comparisons)})
    complete_records = [record for record in normalized if record["complete"]]
    unique_project_ids = {_text(record.get("project_id")) for record in complete_records}
    covered_disciplines = sorted(
        {
            _text(discipline).lower()
            for record in complete_records
            for discipline in _list(record.get("disciplines"))
            if _text(discipline)
        }
    )
    required_disciplines = {"grading", "drainage", "storm", "sanitary", "water", "roadway", "earthwork", "quantities"}
    missing_disciplines = sorted(required_disciplines - set(covered_disciplines))
    ready = len(unique_project_ids) >= 3 and not missing_disciplines
    return {
        "ready": ready,
        "required_project_count": 3,
        "record_count": len(normalized),
        "complete_record_count": len(complete_records),
        "unique_complete_project_count": len(unique_project_ids),
        "covered_disciplines": covered_disciplines,
        "missing_disciplines": missing_disciplines,
        "records": normalized,
    }


def build_full_launch_readiness(
    *,
    revision: str,
    engineering_validation: Mapping[str, Any],
    source_infrastructure: Mapping[str, Any],
    confirmation_evidence: Mapping[str, Any],
    reliability_manifest: Mapping[str, Any],
    hosted_evidence: Mapping[str, Any],
    external_evidence: Mapping[str, Any],
    real_project_records: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    revision = _text(revision)
    engineering = _dict(engineering_validation)
    source = _dict(source_infrastructure)
    confirmation = _dict(confirmation_evidence)
    reliability = _dict(reliability_manifest)
    hosted = _dict(hosted_evidence)
    external = _dict(external_evidence)
    blockers: list[Dict[str, str]] = []

    engineering_ready = bool(
        engineering.get("success") is True
        and int(engineering.get("scenario_count") or 0) >= 10
        and int(engineering.get("real_file_fixture_count") or 0) >= 8
        and int(engineering.get("failed_comparison_count") or 0) == 0
        and int(engineering.get("automated_expected_actual_comparison_count") or 0) > 0
    )
    if not engineering_ready:
        blockers.append(_blocker("engineering_validation", "engineering_validation_incomplete", "The revision does not have a passing ten-scenario, eight-real-file engineering comparison report.", "Run RC1 engineering validation and resolve every failed scenario or comparison."))

    rights = _dict(source.get("rights_review"))
    source_ready = bool(
        source.get("source_traceability_verified") is True
        and source.get("missing_source_behavior_verified") is True
        and int(source.get("queryable_source_count") or 0) > 0
        and int(source.get("market_count") or 0) > 0
        and _accepted_external_gate(rights)
    )
    if not source_ready:
        blockers.append(_blocker("source_infrastructure", "source_infrastructure_incomplete", "Queryable sources, source traceability, missing-source behavior, and source-rights evidence are not all proven.", "Attach a dated source inventory and accepted rights review for the enabled providers."))

    covered_actions = {_text(item) for item in _list(confirmation.get("covered_actions")) if _text(item)}
    integrated_actions = {_text(item) for item in _list(confirmation.get("integrated_actions")) if _text(item)}
    browser_verified_actions = {_text(item) for item in _list(confirmation.get("browser_verified_actions")) if _text(item)}
    confirmation_ready = bool(
        confirmation.get("preview_required") is True
        and confirmation.get("explicit_confirmation_required") is True
        and confirmation.get("reversible") is True
        and confirmation.get("history_preserved") is True
        and confirmation.get("tests_passed") is True
        and REQUIRED_CONFIRMATION_ACTIONS.issubset(covered_actions)
        and REQUIRED_CONFIRMATION_ACTIONS.issubset(integrated_actions)
        and REQUIRED_CONFIRMATION_ACTIONS.issubset(browser_verified_actions)
    )
    if not confirmation_ready:
        blockers.append(_blocker("confirmation", "major_change_confirmation_incomplete", "One or more meaningful changes lack preview, explicit confirmation, reversibility, history, or test evidence.", "Prove every required action through the shared confirmation contract and browser workflow."))

    manifest_revision = _text(reliability.get("revision"))
    evidence = _dict(reliability.get("evidence"))
    successful_evidence = {key for key, value in evidence.items() if _dict(value).get("success") is True}
    hosted_revision = _text(hosted.get("revision"))
    authenticated = _dict(hosted.get("authenticated_smoke"))
    hosted_repeat_ready = bool(
        hosted_revision == revision
        and _text(authenticated.get("status")).lower() == "passed"
        and int(authenticated.get("repeat_count") or 0) >= 2
        and int(authenticated.get("passed_runs") or 0) >= 2
    )
    reliability_ready = bool(
        revision
        and manifest_revision == revision
        and REQUIRED_TECHNICAL_EVIDENCE.issubset(successful_evidence)
        and hosted_repeat_ready
    )
    if not reliability_ready:
        blockers.append(_blocker("whole_product_reliability", "revision_bound_reliability_incomplete", "The exact revision lacks every required regression, browser, concurrency, and repeated hosted workflow record.", "Run the RC evidence suite and two authenticated hosted workflows against this exact revision."))

    external_rows = []
    for gate_id in sorted(REQUIRED_EXTERNAL_GATES):
        record = _dict(external.get(gate_id))
        accepted = _accepted_external_gate(record)
        external_rows.append({"gate_id": gate_id, "accepted": accepted, "record": _redact(record)})
        if not accepted:
            blockers.append(_blocker("external_readiness", f"{gate_id}_missing", f"External gate '{gate_id}' has no accepted, dated, owner-attributed HTTPS evidence.", f"Have the accountable owner complete and attach evidence for {gate_id.replace('_', ' ')}."))
    external_ready = all(row["accepted"] for row in external_rows)

    real_projects = _real_project_status(real_project_records, revision)
    if not real_projects["ready"]:
        blockers.append(_blocker("real_project_validation", "real_project_validation_incomplete", "Fewer than three independently reviewed real projects cover every required site-development discipline on this revision.", "Complete three revision-bound real-project comparisons and resolve every tolerance discrepancy."))

    technical_program_ready = engineering_ready and confirmation_ready and reliability_ready
    full_launch_ready = technical_program_ready and source_ready and external_ready and real_projects["ready"]
    report: Dict[str, Any] = {
        "version": FULL_LAUNCH_READINESS_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "revision": revision,
        "technical_program_ready": technical_program_ready,
        "full_launch_ready": full_launch_ready,
        "status": "full_launch_ready" if full_launch_ready else "blocked",
        "domains": {
            "engineering_validation": {"ready": engineering_ready, "report": _redact(engineering)},
            "source_infrastructure": {"ready": source_ready, "report": _redact(source)},
            "major_change_confirmation": {"ready": confirmation_ready, "covered_actions": sorted(covered_actions), "integrated_actions": sorted(integrated_actions), "browser_verified_actions": sorted(browser_verified_actions), "missing_actions": sorted(REQUIRED_CONFIRMATION_ACTIONS - (covered_actions & integrated_actions & browser_verified_actions))},
            "whole_product_reliability": {"ready": reliability_ready, "successful_evidence": sorted(successful_evidence), "missing_evidence": sorted(REQUIRED_TECHNICAL_EVIDENCE - successful_evidence), "hosted_repeat_ready": hosted_repeat_ready},
            "external_readiness": {"ready": external_ready, "gates": external_rows},
            "real_project_validation": real_projects,
        },
        "blocker_count": len(blockers),
        "blockers": blockers,
        "construction_ready": False,
        "construction_release_allowed": False,
        "truth_label": "Full launch requires revision-bound automated proof plus source rights, professional review, security, operations, recovery, insurance, legal, billing, and real-project evidence. Missing external evidence always blocks full launch.",
    }
    report["report_sha256"] = _sha256(report)
    return report


__all__ = [
    "FULL_LAUNCH_READINESS_VERSION",
    "REQUIRED_CONFIRMATION_ACTIONS",
    "REQUIRED_EXTERNAL_GATES",
    "REQUIRED_TECHNICAL_EVIDENCE",
    "build_full_launch_readiness",
]
