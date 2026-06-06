from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List

from .common import readiness_issue_explanations, safe_dict, safe_float, safe_list, safe_str


SURVEY_CONTROL_PACKAGE_VERSION = "survey_control_package_v1"


def _first_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return ""


def _source_from_sources(sources: Iterable[Any]) -> str:
    for item in sources:
        rec = safe_dict(item)
        source = safe_str(rec.get("source") or rec.get("file") or rec.get("file_name"))
        if source:
            return source
    return ""


def _blocker(field: str, reason: str, *, missing_fields: List[str] | None = None) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "area": "existing_conditions",
        "field": field,
        "reason": reason,
        "message": reason,
        "severity": "blocker",
    }
    if missing_fields:
        rec["missing_fields"] = missing_fields
    return rec


def build_survey_control_package(
    value: Dict[str, Any] | None = None,
    *,
    survey: Dict[str, Any] | None = None,
    coordinate_system: Dict[str, Any] | None = None,
    sources: Iterable[Any] = (),
) -> Dict[str, Any]:
    """Normalize survey control, benchmark, datum, and CRS evidence.

    This package is evidence for engineer/user review only. It is not a survey
    certification and does not authorize construction release.
    """

    explicit = deepcopy(safe_dict(value))
    survey_rec = safe_dict(survey)
    coord = safe_dict(coordinate_system)
    nested = safe_dict(explicit.get("survey_control_package") or explicit.get("control_package"))
    rec = {**nested, **explicit}
    coordinate = safe_dict(
        _first_value(
            rec.get("coordinate_system"),
            coord,
            survey_rec.get("coordinate_system"),
        )
    )
    benchmark_elevation_raw = _first_value(
        rec.get("benchmark_elevation"),
        rec.get("benchmark_elevation_ft"),
        rec.get("benchmark_z"),
        survey_rec.get("benchmark_elevation"),
        survey_rec.get("benchmark_elevation_ft"),
        survey_rec.get("benchmark_z"),
    )
    benchmark_elevation = None
    if benchmark_elevation_raw not in (None, ""):
        benchmark_elevation = safe_float(benchmark_elevation_raw, 0.0)

    package = {
        "version": SURVEY_CONTROL_PACKAGE_VERSION,
        "coordinate_system": deepcopy(coordinate),
        "horizontal_datum": safe_str(
            _first_value(
                rec.get("horizontal_datum"),
                rec.get("horizontalDatum"),
                coord.get("horizontal_datum"),
                coord.get("datum"),
                survey_rec.get("horizontal_datum"),
            )
        ),
        "vertical_datum": safe_str(
            _first_value(
                rec.get("vertical_datum"),
                rec.get("verticalDatum"),
                rec.get("datum"),
                survey_rec.get("vertical_datum"),
                survey_rec.get("datum"),
            )
        ),
        "benchmark_id": safe_str(
            _first_value(
                rec.get("benchmark_id"),
                rec.get("benchmark"),
                survey_rec.get("benchmark_id"),
                survey_rec.get("benchmark"),
            )
        ),
        "benchmark_elevation": benchmark_elevation,
        "control_verified": rec.get("control_verified") is True or survey_rec.get("control_verified") is True,
        "survey_source": safe_str(
            _first_value(
                rec.get("survey_source"),
                rec.get("source"),
                survey_rec.get("survey_source"),
                survey_rec.get("source"),
                _source_from_sources(sources),
            )
        ),
        "survey_date": safe_str(_first_value(rec.get("survey_date"), rec.get("date"), survey_rec.get("survey_date"))),
        "surveyor": safe_str(_first_value(rec.get("surveyor"), rec.get("surveyor_name"), survey_rec.get("surveyor"))),
        "surveyor_license": safe_str(
            _first_value(
                rec.get("surveyor_license"),
                rec.get("license"),
                rec.get("license_number"),
                survey_rec.get("surveyor_license"),
                survey_rec.get("license_number"),
            )
        ),
    }
    missing: List[str] = []
    if not package["coordinate_system"]:
        missing.append("coordinate_system")
    if not package["horizontal_datum"]:
        missing.append("horizontal_datum")
    if not package["vertical_datum"]:
        missing.append("vertical_datum")
    if not package["benchmark_id"]:
        missing.append("benchmark_id")
    if package["benchmark_elevation"] is None:
        missing.append("benchmark_elevation")
    if not package["survey_source"]:
        missing.append("survey_source")
    if not package["control_verified"]:
        missing.append("control_verified")

    blockers: List[Dict[str, Any]] = []
    if missing:
        blockers.append(
            _blocker(
                "survey_control_package",
                "Survey control package is missing required coordinate, datum, benchmark, source, or verification evidence.",
                missing_fields=missing,
            )
        )
    if not package["control_verified"]:
        blockers.append(
            _blocker(
                "survey_control_verified",
                "Survey/control evidence must be explicitly verified by the user or licensed professional before production-grade use.",
            )
        )

    has_evidence = any(
        package.get(key) not in (None, "", [], {})
        for key in (
            "coordinate_system",
            "horizontal_datum",
            "vertical_datum",
            "benchmark_id",
            "benchmark_elevation",
            "control_verified",
            "survey_source",
            "survey_date",
            "surveyor",
            "surveyor_license",
        )
    )
    package["confidence"] = "verified" if not blockers else ("partial" if has_evidence else "missing")
    package["production_usable"] = not blockers
    package["blockers"] = blockers
    package["blocker_details"] = readiness_issue_explanations(blockers)
    package["truth_label"] = (
        "Survey control package records review evidence only; Civora never stamps, seals, signs, certifies, "
        "approves construction, submits construction documents, or acts as engineer of record."
    )
    return package


__all__ = ["SURVEY_CONTROL_PACKAGE_VERSION", "build_survey_control_package"]
