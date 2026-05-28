from __future__ import annotations

from datetime import date
from typing import Any, Dict, List


RELEASE_STATUSES = {"approved", "sealed", "released_for_construction", "issued_for_construction"}


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _today() -> str:
    return date.today().isoformat()


def validate_professional_release(record: Dict[str, Any]) -> Dict[str, Any]:
    rec = _safe_dict(record)
    blockers: List[Dict[str, str]] = []
    status = _safe_str(rec.get("status")).lower()
    sealed = rec.get("sealed") is True
    if not (sealed or status in RELEASE_STATUSES):
        blockers.append(
            {
                "field": "sealed_release",
                "reason": "Professional review is not marked sealed/released for construction.",
            }
        )
    for field in ("engineer_name", "license_number"):
        if not _safe_str(rec.get(field)):
            blockers.append(
                {
                    "field": field,
                    "reason": f"Professional release is missing {field.replace('_', ' ')}.",
                }
            )
    review_date = _safe_str(rec.get("review_date") or rec.get("sealed_date") or rec.get("approved_date"))
    if not review_date:
        blockers.append({"field": "review_date", "reason": "Professional release is missing review/seal date."})
    return {
        "success": not blockers,
        "released_for_construction": not blockers,
        "blockers": blockers,
        "status": status or "missing",
        "sealed": sealed,
        "review_date": review_date,
        "engineer_name": _safe_str(rec.get("engineer_name")),
        "license_number": _safe_str(rec.get("license_number")),
        "truth_label": "Professional release metadata records reviewer signoff evidence; Civora does not stamp drawings.",
    }


def build_professional_review_record(
    *,
    engineer_name: str,
    license_number: str,
    status: str = "released_for_construction",
    review_date: str = "",
    sealed: bool = True,
    jurisdiction: str = "",
    notes: str = "",
) -> Dict[str, Any]:
    record = {
        "source": "professional_release_workflow",
        "engineer_name": _safe_str(engineer_name),
        "license_number": _safe_str(license_number),
        "status": _safe_str(status, "released_for_construction"),
        "review_date": _safe_str(review_date, _today()),
        "sealed": bool(sealed),
        "jurisdiction": _safe_str(jurisdiction),
        "notes": _safe_str(notes),
    }
    record["validation"] = validate_professional_release(record)
    return record


__all__ = ["RELEASE_STATUSES", "build_professional_review_record", "validate_professional_release"]
