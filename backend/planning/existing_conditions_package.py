from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from .common import readiness_issue_explanations, safe_dict, safe_list, safe_str
from .existing_conditions import REQUIRED_GIS_LAYERS, summarize_existing_conditions


def _package_blocker(field: str, reason: str, *, next_action: str = "") -> Dict[str, Any]:
    return {
        "area": "existing_conditions",
        "field": field,
        "reason": reason,
        "message": reason,
        "why_needed": reason,
        "suggested_next_action": next_action or "Resolve this existing-conditions package issue and rerun the package gate.",
        "severity": "blocker",
    }


def _package_warning(field: str, reason: str, *, next_action: str = "") -> Dict[str, Any]:
    rec = _package_blocker(field, reason, next_action=next_action)
    rec["severity"] = "warning"
    return rec


def _source_count(meta: Dict[str, Any], validation: Dict[str, Any]) -> int:
    explicit = safe_intish(validation.get("source_count"))
    if explicit > 0:
        return explicit
    return len(safe_list(meta.get("sources") or safe_dict(meta.get("existing_conditions_import")).get("sources")))


def safe_intish(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _acceptance(meta: Dict[str, Any], accepted_by: str = "") -> Dict[str, Any]:
    existing = safe_dict(meta.get("existing_conditions_package"))
    acceptance = safe_dict(existing.get("acceptance"))
    accepted_user = safe_str(
        accepted_by
        or acceptance.get("accepted_by")
        or meta.get("existing_conditions_accepted_by")
        or safe_dict(meta.get("existing_conditions_acceptance")).get("accepted_by")
    )
    accepted = bool(acceptance.get("accepted") or meta.get("existing_conditions_accepted") is True or accepted_user)
    return {
        "accepted": accepted,
        "accepted_by": accepted_user,
        "accepted_at": safe_str(acceptance.get("accepted_at") or safe_dict(meta.get("existing_conditions_acceptance")).get("accepted_at")),
        "notes": safe_str(acceptance.get("notes") or safe_dict(meta.get("existing_conditions_acceptance")).get("notes")),
        "truth_label": "User acceptance records that the imported existing-condition package may be used for review workflows; it is not a professional survey certification.",
    }


def build_existing_conditions_package(plan_or_meta: Dict[str, Any], *, accepted_by: str = "") -> Dict[str, Any]:
    meta = safe_dict(plan_or_meta.get("meta")) if isinstance(plan_or_meta, dict) and "meta" in plan_or_meta else safe_dict(plan_or_meta)
    summary = safe_dict(meta.get("existing_conditions_summary")) or summarize_existing_conditions({"meta": meta})
    validation = safe_dict(
        meta.get("existing_conditions_import_validation")
        or meta.get("import_validation")
        or safe_dict(meta.get("existing_conditions_import")).get("import_validation")
    )
    acceptance = _acceptance(meta, accepted_by=accepted_by)
    blockers: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    if not summary:
        blockers.append(
            _package_blocker(
                "existing_conditions_summary",
                "Existing-conditions package needs a summary of survey, terrain, GIS, and coordinate-system evidence.",
                next_action="Run existing-condition summarization after import.",
            )
        )
    for item in safe_list(summary.get("missing_requirements")):
        rec = safe_dict(item)
        blockers.append(
            _package_blocker(
                safe_str(rec.get("field"), "missing_requirement"),
                safe_str(rec.get("reason"), "Existing-condition evidence is incomplete."),
                next_action="Attach or explicitly mark missing existing-condition evidence before clearing the package.",
            )
        )

    if validation:
        for item in safe_list(validation.get("blockers")):
            rec = safe_dict(item)
            blockers.append(
                _package_blocker(
                    safe_str(rec.get("field"), "import_validation"),
                    safe_str(rec.get("reason"), "Existing-condition import validation failed."),
                    next_action="Fix the failed import evidence and rerun import validation.",
                )
            )
        for item in safe_list(validation.get("warnings")):
            text = safe_str(item)
            if text:
                warnings.append(_package_warning("import_warning", text, next_action="Review import warning before relying on this package."))
    else:
        blockers.append(
            _package_blocker(
                "import_validation",
                "Existing-conditions package needs import validation proving parsed data is usable, not metadata-only.",
                next_action="Run import package validation for survey/GIS/terrain sources.",
            )
        )

    if not acceptance["accepted"]:
        warnings.append(
            _package_warning(
                "package_acceptance",
                "Existing-conditions package has not been accepted for private-alpha review use.",
                next_action="Have the user accept the import package or keep design systems blocked/needs-review.",
            )
        )

    production_ready = bool(summary.get("production_ready")) and bool(validation.get("production_usable"))
    if blockers:
        status = "blocked"
    elif not acceptance["accepted"]:
        status = "needs_review"
    else:
        status = "ready" if production_ready else "needs_review"

    survey = safe_dict(summary.get("survey"))
    gis = safe_dict(summary.get("gis"))
    coordinate = safe_dict(summary.get("coordinate_system"))
    layer_counts = safe_dict(validation.get("layer_counts")) or {
        layer: safe_intish(safe_dict(safe_dict(gis.get("layers")).get(layer)).get("count"))
        for layer in REQUIRED_GIS_LAYERS
    }
    canonical_model = safe_dict(
        meta.get("canonical_existing_conditions_model")
        or safe_dict(meta.get("existing_conditions_import")).get("canonical_existing_conditions_model")
    )
    if not canonical_model:
        try:
            from .existing_conditions_importers import build_canonical_existing_conditions_model

            canonical_model = build_canonical_existing_conditions_model(
                {
                    "survey": meta.get("survey"),
                    "gis_layers": meta.get("gis_layers") or meta.get("existing_conditions"),
                    "coordinate_system": meta.get("coordinate_system"),
                    "surfaces": meta.get("surfaces"),
                    "sources": meta.get("sources") or safe_dict(meta.get("existing_conditions_import")).get("sources"),
                    "metadata_only_sources": meta.get("metadata_only_sources")
                    or safe_dict(meta.get("existing_conditions_import")).get("metadata_only_sources"),
                    "canonical_targets": meta.get("canonical_targets")
                    or safe_dict(meta.get("existing_conditions_import")).get("canonical_targets"),
                    "import_validation": validation,
                }
            )
        except Exception:
            canonical_model = {}
    metadata_only_sources = safe_list(
        canonical_model.get("metadata_only_sources")
        or meta.get("metadata_only_sources")
        or safe_dict(meta.get("existing_conditions_import")).get("metadata_only_sources")
    )
    production_requirements = safe_list(validation.get("production_requirements"))
    importer_matrix = safe_list(validation.get("importer_production_matrix"))
    terrain_confidence = safe_dict(validation.get("terrain_source_confidence")) or safe_dict(safe_dict(canonical_model.get("terrain")).get("confidence"))
    return {
        "version": "existing_conditions_package_v1",
        "status": status,
        "production_ready": status == "ready" and production_ready,
        "review_usable": status in {"ready", "needs_review"} and not blockers,
        "metadata_only": not bool(validation) or (bool(canonical_model.get("metadata_only")) if canonical_model else False),
        "gate": {
            "status": status,
            "production_ready": status == "ready" and production_ready,
            "terrain_source_confidence": safe_str(terrain_confidence.get("label"), "missing"),
            "metadata_only_source_count": len(metadata_only_sources),
            "dependency_blocked_source_count": len(safe_list(validation.get("dependency_blocked_sources"))),
            "truth_label": "The existing-conditions gate separates parsed evidence from production-grade survey/GIS/control readiness.",
        },
        "accepted": bool(acceptance["accepted"]),
        "acceptance": acceptance,
        "source_count": _source_count(meta, validation),
        "canonical_existing_conditions": {
            "survey": deepcopy(meta.get("survey")),
            "gis_layers": deepcopy(meta.get("gis_layers") or meta.get("existing_conditions")),
            "coordinate_system": deepcopy(meta.get("coordinate_system")),
            "surfaces": deepcopy(meta.get("surfaces")),
            "sources": deepcopy(meta.get("sources") or safe_dict(meta.get("existing_conditions_import")).get("sources")),
            "model": deepcopy(canonical_model),
            "metadata_only_sources": deepcopy(metadata_only_sources),
        },
        "canonical_existing_conditions_model": deepcopy(canonical_model),
        "metadata_only_sources": deepcopy(metadata_only_sources),
        "summary": deepcopy(summary),
        "import_validation": deepcopy(validation),
        "production_requirements": deepcopy(production_requirements),
        "importer_production_matrix": deepcopy(importer_matrix),
        "terrain_source_confidence": deepcopy(terrain_confidence),
        "survey_ready": bool(survey.get("ready")),
        "gis_ready": bool(gis.get("ready")),
        "coordinate_system_ready": bool(coordinate.get("ready")),
        "layer_counts": layer_counts,
        "blockers": blockers,
        "blocker_details": readiness_issue_explanations(blockers),
        "warnings": warnings,
        "truth_label": "Existing-condition packages are review inputs until source/control, CRS, GIS constraints, acceptance, and professional review are complete.",
    }


__all__ = ["build_existing_conditions_package"]
