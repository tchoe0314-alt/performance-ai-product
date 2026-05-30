from __future__ import annotations

from typing import Any, Dict

from backend.planning.professional_release import RELEASE_STATUSES


def _append_once(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _construction_package_record(meta: Dict[str, Any]) -> Dict[str, Any]:
    package = dict(
        meta.get("construction_package_manifest")
        or meta.get("construction_package")
        or meta.get("construction_deliverable_package")
        or meta.get("deliverable_package")
        or {}
    )
    if not package:
        packages = list(meta.get("deliverable_packages") or [])
        if packages and isinstance(packages[-1], dict):
            package = dict(packages[-1])
    return package


def _professional_release_claimed(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    status = str(record.get("status") or "").strip().lower()
    if status in RELEASE_STATUSES:
        return True
    return (
        record.get("sealed") is True
        or record.get("released_for_construction") is True
        or record.get("issued_for_construction") is True
    )


def _artifact_status_blockers(artifact_status: Dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if artifact_status.get("package_present") is False:
        _append_once(blockers, "construction_package_missing")
    if artifact_status.get("package_identity_present") is False:
        _append_once(blockers, "construction_package_identity_missing")
    if list(artifact_status.get("missing") or []):
        _append_once(blockers, "construction_package_missing_artifacts")
    if list(artifact_status.get("anonymous") or []):
        _append_once(blockers, "construction_package_anonymous_artifacts")
    if list(artifact_status.get("stale") or []):
        _append_once(blockers, "construction_package_stale_artifacts")
    if artifact_status.get("model_reference_present") is False:
        _append_once(blockers, "construction_package_model_reference_missing")
    elif artifact_status.get("model_matches_expected") is False:
        _append_once(blockers, "construction_package_model_mismatch")
    if artifact_status.get("release_ready_flag") is not True:
        _append_once(blockers, "construction_package_release_not_marked_ready")
    if artifact_status.get("production_ready_flag") is not True:
        _append_once(blockers, "construction_package_production_not_marked_ready")
    if list(artifact_status.get("untraced") or []):
        _append_once(blockers, "construction_package_untraced_artifacts")
    if list(artifact_status.get("mismatched") or []):
        _append_once(blockers, "construction_package_mismatched_artifacts")
    if list(artifact_status.get("cost_untraced") or []):
        _append_once(blockers, "construction_package_cost_untraced")
    if list(artifact_status.get("cost_mismatched") or []):
        _append_once(blockers, "construction_package_cost_mismatched")
    return blockers


def final_plan_requires_construction_release(final_plan: Dict[str, Any]) -> bool:
    meta = dict(final_plan.get("meta") or {})
    if meta.get("construction_release_required") is True:
        return True
    if final_plan.get("construction_release_required") is True:
        return True
    if meta.get("construction_export_allowed") is True or final_plan.get("construction_export_allowed") is True:
        return True
    if meta.get("construction_release_allowed") is True or final_plan.get("construction_release_allowed") is True:
        return True
    release_state = str(meta.get("release_state") or final_plan.get("release_state") or "").lower()
    construction_release_state = str(
        meta.get("construction_release_state") or final_plan.get("construction_release_state") or ""
    ).lower()
    if release_state in {"released_for_construction", "issued_for_construction"}:
        return True
    if construction_release_state in {"released_for_construction", "issued_for_construction"}:
        return True
    if _professional_release_claimed(meta.get("professional_review")):
        return True
    if _professional_release_claimed(meta.get("engineer_review")):
        return True
    if _professional_release_claimed(final_plan.get("professional_review")):
        return True
    if _professional_release_claimed(final_plan.get("engineer_review")):
        return True
    return any(
        bool(meta.get(key))
        for key in (
            "construction_readiness",
            "construction_package_manifest",
            "construction_package",
            "construction_deliverable_package",
            "deliverable_package",
            "deliverable_packages",
            "professional_package_release_status",
        )
    )


def construction_release_blockers_from_meta(meta: Dict[str, Any], *, requires_construction_release: bool = False) -> list[str]:
    blockers: list[str] = []
    construction = dict(meta.get("construction_readiness") or {})
    if requires_construction_release and not construction:
        blockers.append("construction_readiness_missing")
    if construction and construction.get("ready") is not True:
        blockers.append("construction_readiness_blocked")
    package = _construction_package_record(meta)
    if construction.get("ready") is True and not package:
        blockers.append("construction_package_manifest_missing")
    if package and package.get("release_allowed") is True:
        artifact_status = dict(package.get("construction_package_artifact_status") or {})
        professional_status = dict(
            package.get("professional_package_release_status")
            or meta.get("professional_package_release_status")
            or {}
        )
        if not artifact_status:
            _append_once(blockers, "construction_package_artifact_status_missing")
        if artifact_status.get("release_ready_flag") is not True:
            _append_once(blockers, "construction_package_release_not_marked_ready")
        if artifact_status and artifact_status.get("complete_for_release") is not True:
            _append_once(blockers, "construction_package_incomplete_release")
        for artifact_blocker in _artifact_status_blockers(artifact_status):
            _append_once(blockers, artifact_blocker)
        if not professional_status:
            _append_once(blockers, "construction_professional_release_missing")
        elif professional_status.get("professional_release_valid") is not True:
            _append_once(blockers, "construction_professional_release_invalid")
        if professional_status and (
            professional_status.get("model_matches_package") is not True
            or professional_status.get("package_matches_review") is not True
        ):
            _append_once(blockers, "construction_professional_release_untraced")
    if package and package.get("release_allowed") is not True:
        _append_once(blockers, "construction_package_blocked")
        artifact_status = dict(package.get("construction_package_artifact_status") or {})
        if not artifact_status:
            _append_once(blockers, "construction_package_artifact_status_missing")
        for artifact_blocker in _artifact_status_blockers(artifact_status):
            _append_once(blockers, artifact_blocker)
        professional_status = dict(
            package.get("professional_package_release_status")
            or meta.get("professional_package_release_status")
            or {}
        )
        if professional_status.get("professional_release_valid") is False:
            _append_once(blockers, "construction_professional_release_invalid")
    return blockers


__all__ = ["construction_release_blockers_from_meta", "final_plan_requires_construction_release"]
