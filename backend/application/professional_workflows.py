from __future__ import annotations

from typing import Any, Dict

from backend.planning.professional_release import build_professional_review_record, validate_professional_release


def professional_release_response(
    *,
    engineer_name: str,
    license_number: str,
    status: str = "released_for_construction",
    review_date: str = "",
    sealed: bool = True,
    jurisdiction: str = "",
    notes: str = "",
) -> Dict[str, Any]:
    record = build_professional_review_record(
        engineer_name=engineer_name,
        license_number=license_number,
        status=status,
        review_date=review_date,
        sealed=sealed,
        jurisdiction=jurisdiction,
        notes=notes,
    )
    return {
        "success": bool(record["validation"]["success"]),
        "professional_review": record,
        "truth_label": "Attach this professional_review record to project meta only after licensed review; Civora does not stamp drawings.",
    }


def validate_professional_release_response(record: Dict[str, Any]) -> Dict[str, Any]:
    validation = validate_professional_release(record)
    return {
        "success": bool(validation["success"]),
        "validation": validation,
    }


__all__ = ["professional_release_response", "validate_professional_release_response"]
