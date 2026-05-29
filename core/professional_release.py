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


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _today() -> str:
    return date.today().isoformat()


def _has_digit(value: str) -> bool:
    return any(ch.isdigit() for ch in value)


def _valid_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def validate_professional_release(record: Dict[str, Any]) -> Dict[str, Any]:
    rec = _safe_dict(record)
    blockers: List[Dict[str, str]] = []
    status = _safe_str(rec.get("status")).lower()
    sealed = rec.get("sealed") is True
    if status not in RELEASE_STATUSES:
        blockers.append(
            {
                "field": "sealed_release",
                "reason": "Professional review is not marked released for construction.",
            }
        )
    if not sealed:
        blockers.append(
            {
                "field": "sealed_release",
                "reason": "Professional review is not explicitly sealed/signed.",
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
    license_number = _safe_str(rec.get("license_number"))
    if license_number and (len(license_number) < 5 or not _has_digit(license_number)):
        blockers.append(
            {
                "field": "license_number",
                "reason": "Professional release license number is not specific enough for traceable review evidence.",
            }
        )
    license_jurisdiction = _safe_str(
        rec.get("license_jurisdiction") or rec.get("license_state") or rec.get("state")
    )
    if not license_jurisdiction:
        blockers.append(
            {
                "field": "license_jurisdiction",
                "reason": "Professional release is missing the licensing jurisdiction/state.",
            }
        )
    project_jurisdiction = _safe_str(rec.get("jurisdiction") or rec.get("project_jurisdiction") or rec.get("authority"))
    if not project_jurisdiction:
        blockers.append(
            {
                "field": "jurisdiction",
                "reason": "Professional release is missing the project review jurisdiction.",
            }
        )
    discipline = _safe_str(rec.get("discipline")).lower()
    if not discipline:
        blockers.append(
            {
                "field": "discipline",
                "reason": "Professional release is missing the reviewed engineering discipline.",
            }
        )
    elif "civil" not in discipline:
        blockers.append(
            {
                "field": "discipline",
                "reason": "Construction release requires civil engineering review scope.",
            }
        )
    scope_raw = rec.get("review_scope") or rec.get("scope")
    scope_items = [_safe_str(item).lower() for item in _safe_list(scope_raw)]
    scope_text = " ".join(scope_items) if scope_items else _safe_str(scope_raw).lower()
    if not scope_text:
        blockers.append(
            {
                "field": "review_scope",
                "reason": "Professional release is missing the review scope covered by the signoff.",
            }
        )
    elif "construction" not in scope_text and "civil" not in scope_text and "site" not in scope_text:
        blockers.append(
            {
                "field": "review_scope",
                "reason": "Professional release scope does not clearly cover civil/site construction documents.",
            }
        )
    review_date = _safe_str(rec.get("review_date") or rec.get("sealed_date") or rec.get("approved_date"))
    if not review_date:
        blockers.append({"field": "review_date", "reason": "Professional release is missing review/seal date."})
    elif not _valid_date(review_date):
        blockers.append({"field": "review_date", "reason": "Professional release review date must be ISO format YYYY-MM-DD."})
    return {
        "success": not blockers,
        "released_for_construction": not blockers,
        "blockers": blockers,
        "status": status or "missing",
        "sealed": sealed,
        "review_date": review_date,
        "engineer_name": _safe_str(rec.get("engineer_name")),
        "license_number": _safe_str(rec.get("license_number")),
        "license_jurisdiction": license_jurisdiction,
        "jurisdiction": project_jurisdiction,
        "discipline": discipline,
        "review_scope": scope_items or scope_text,
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
    license_jurisdiction: str = "",
    discipline: str = "civil",
    review_scope: str = "civil_site_construction_documents",
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
        "license_jurisdiction": _safe_str(license_jurisdiction),
        "discipline": _safe_str(discipline, "civil"),
        "review_scope": _safe_str(review_scope, "civil_site_construction_documents"),
        "notes": _safe_str(notes),
    }
    record["validation"] = validate_professional_release(record)
    return record


__all__ = ["RELEASE_STATUSES", "build_professional_review_record", "validate_professional_release"]
