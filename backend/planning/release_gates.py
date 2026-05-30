from __future__ import annotations

from typing import Any, Dict


def final_plan_requires_construction_release(final_plan: Dict[str, Any]) -> bool:
    meta = dict(final_plan.get("meta") or {})
    if meta.get("construction_release_required") is True:
        return True
    if final_plan.get("construction_release_required") is True:
        return True
    return any(
        bool(meta.get(key))
        for key in (
            "construction_readiness",
            "construction_package_manifest",
            "construction_package",
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
    package = dict(meta.get("construction_package_manifest") or meta.get("construction_package") or {})
    if construction.get("ready") is True and not package:
        blockers.append("construction_package_manifest_missing")
    if package and package.get("release_allowed") is True:
        artifact_status = dict(package.get("construction_package_artifact_status") or {})
        professional_status = dict(package.get("professional_package_release_status") or {})
        if artifact_status.get("release_ready_flag") is not True:
            blockers.append("construction_package_release_not_marked_ready")
        if artifact_status and artifact_status.get("complete_for_release") is not True:
            blockers.append("construction_package_incomplete_release")
        if not professional_status:
            blockers.append("construction_professional_release_missing")
        elif professional_status.get("professional_release_valid") is not True:
            blockers.append("construction_professional_release_invalid")
        if professional_status and (
            professional_status.get("model_matches_package") is not True
            or professional_status.get("package_matches_review") is not True
        ):
            blockers.append("construction_professional_release_untraced")
    if package and package.get("release_allowed") is not True:
        blockers.append("construction_package_blocked")
        artifact_status = dict(package.get("construction_package_artifact_status") or {})
        if artifact_status.get("package_present") is False:
            blockers.append("construction_package_missing")
        if list(artifact_status.get("missing") or []):
            blockers.append("construction_package_missing_artifacts")
        if list(artifact_status.get("anonymous") or []):
            blockers.append("construction_package_anonymous_artifacts")
        if list(artifact_status.get("stale") or []):
            blockers.append("construction_package_stale_artifacts")
        if artifact_status.get("model_reference_present") is False:
            blockers.append("construction_package_model_reference_missing")
        elif artifact_status.get("model_matches_expected") is False:
            blockers.append("construction_package_model_mismatch")
        if artifact_status.get("release_ready_flag") is not True:
            blockers.append("construction_package_release_not_marked_ready")
        if list(artifact_status.get("untraced") or []):
            blockers.append("construction_package_untraced_artifacts")
        if list(artifact_status.get("mismatched") or []):
            blockers.append("construction_package_mismatched_artifacts")
        if list(artifact_status.get("cost_untraced") or []):
            blockers.append("construction_package_cost_untraced")
        if list(artifact_status.get("cost_mismatched") or []):
            blockers.append("construction_package_cost_mismatched")
        professional_status = dict(package.get("professional_package_release_status") or {})
        if professional_status.get("professional_release_valid") is False:
            blockers.append("construction_professional_release_invalid")
    return blockers


__all__ = ["construction_release_blockers_from_meta", "final_plan_requires_construction_release"]
