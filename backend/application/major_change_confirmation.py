from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, Mapping


MAJOR_CHANGE_CONFIRMATION_VERSION = "major_change_confirmation_v1"

MAJOR_CHANGE_POLICIES: Dict[str, Dict[str, Any]] = {
    "accept_detected_conditions": {"preview_required": True, "confirmation_required": True, "reversible": True, "history_event": "detected_condition_accepted"},
    "change_accepted_standards": {"preview_required": True, "confirmation_required": True, "reversible": True, "history_event": "accepted_standard_changed"},
    "apply_major_design_fix": {"preview_required": True, "confirmation_required": True, "reversible": True, "history_event": "major_design_fix_applied"},
    "reroute_engineering_system": {"preview_required": True, "confirmation_required": True, "reversible": True, "history_event": "engineering_system_rerouted"},
    "delete_protected_object": {"preview_required": True, "confirmation_required": True, "reversible": True, "history_event": "protected_object_deleted"},
    "regenerate_affected_systems": {"preview_required": True, "confirmation_required": True, "reversible": True, "history_event": "affected_systems_regenerated"},
    "create_review_package": {"preview_required": True, "confirmation_required": True, "reversible": True, "history_event": "review_package_created"},
}


def build_major_change_preview(
    action: str,
    *,
    target_ids: Iterable[str] = (),
    affected_systems: Iterable[str] = (),
    before: Mapping[str, Any] | None = None,
    proposed: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    policy = MAJOR_CHANGE_POLICIES.get(action)
    if policy is None:
        return {
            "version": MAJOR_CHANGE_CONFIRMATION_VERSION,
            "action": action,
            "supported": False,
            "can_apply": False,
            "blocker": "unsupported_major_change_action",
        }
    targets = sorted({str(item).strip() for item in target_ids if str(item).strip()})
    systems = sorted({str(item).strip() for item in affected_systems if str(item).strip()})
    return {
        "version": MAJOR_CHANGE_CONFIRMATION_VERSION,
        "action": action,
        "supported": True,
        "can_apply": False,
        "status": "awaiting_confirmation",
        "target_ids": targets,
        "affected_systems": systems,
        "before": deepcopy(dict(before or {})),
        "proposed": deepcopy(dict(proposed or {})),
        "policy": deepcopy(policy),
        "confirmation_token_required": True,
        "history_preserved": True,
        "truth_label": "The preview describes a proposed change only. No canonical engineering state changes until explicit confirmation is accepted.",
    }


def confirm_major_change(preview: Mapping[str, Any], *, confirmation_token: str) -> Dict[str, Any]:
    record = deepcopy(dict(preview or {}))
    valid = bool(
        record.get("supported") is True
        and record.get("status") == "awaiting_confirmation"
        and confirmation_token == "CONFIRM CHANGE"
    )
    record.update(
        {
            "can_apply": valid,
            "status": "confirmed" if valid else "blocked",
            "blocker": "" if valid else "explicit_confirmation_required",
            "confirmation_token_recorded": False,
        }
    )
    return record


def build_confirmation_evidence(
    *,
    tests_passed: bool,
    integrated_actions: Iterable[str] = (),
    browser_verified_actions: Iterable[str] = (),
) -> Dict[str, Any]:
    rows = deepcopy(MAJOR_CHANGE_POLICIES)
    integrated = sorted({str(action).strip() for action in integrated_actions if str(action).strip() in rows})
    browser_verified = sorted({str(action).strip() for action in browser_verified_actions if str(action).strip() in rows})
    required = set(rows)
    return {
        "version": MAJOR_CHANGE_CONFIRMATION_VERSION,
        "covered_actions": sorted(rows),
        "preview_required": all(row["preview_required"] for row in rows.values()),
        "explicit_confirmation_required": all(row["confirmation_required"] for row in rows.values()),
        "reversible": all(row["reversible"] for row in rows.values()),
        "history_preserved": all(bool(row["history_event"]) for row in rows.values()),
        "tests_passed": bool(tests_passed),
        "integrated_actions": integrated,
        "browser_verified_actions": browser_verified,
        "integration_complete": required.issubset(integrated),
        "browser_verification_complete": required.issubset(browser_verified),
        "policies": rows,
        "truth_label": "This evidence proves the shared confirmation contract. Each product action must still call the contract and pass its browser workflow before release evidence is complete.",
    }


__all__ = ["MAJOR_CHANGE_CONFIRMATION_VERSION", "MAJOR_CHANGE_POLICIES", "build_confirmation_evidence", "build_major_change_preview", "confirm_major_change"]
