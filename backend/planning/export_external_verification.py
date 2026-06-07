from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from .common import safe_dict, safe_list, safe_str
from .dwg_compatibility import DWG_UNSUPPORTED_STATUS


DXF_ALLOWED_LAYERS = {
    "0",
    "DEFPOINTS",
    "SITE",
    "SETBACK",
    "BUILDING",
    "PAVEMENT",
    "PARKING",
    "LABEL",
    "ANNO",
    "SYMBOL",
    "STRUCTURE",
    "WATER",
    "ROAD",
    "FIRE",
    "LOT",
    "SURFACE",
    "EG_CONTOUR",
    "FG_CONTOUR",
    "DRAIN_FLOW",
    "LOW_POINTS",
    "SPOT_EG",
    "SPOT_FG",
    "PIPE",
    "BASIN_BOUNDARY",
    "UTILITY",
    "SAN",
    "STORM",
    "DRAIN",
    "ROUTE",
    "SKETCH_ZONE",
    "SKETCH_OBS",
    "SKETCH_LINE",
    "SKETCH_PTS",
    "SKETCH_BLDG",
    "SKETCH_PARK",
    "SKETCH_ROAD",
    "SKETCH_DRAIN",
    "SKETCH_UTIL",
    "SKETCH_PAD",
    "SKETCH_BLDG_PTS",
    "SKETCH_DRAIN_PTS",
    "SKETCH_UTIL_PTS",
    "SKETCH_ROAD_PTS",
    "WALK",
    "SHEET",
    "TITLE",
    "GRID",
    "AXIS",
    "VIEWPORT",
    "VIEWPORTS",
    "DIM",
    "MATCHLINE",
    "HATCH",
}

EXTERNAL_VERIFICATION_STATUS_NOT_VERIFIED = "not_verified"
EXTERNAL_VERIFICATION_STATUS_BLOCKED = "blocked_needs_review"
EXTERNAL_VERIFICATION_STATUS_PASSED = "externally_verified_review_only"

_PASSED_RESULTS = {"pass", "passed", "success", "successful", "accepted", "verified"}
_FAILED_RESULTS = {"fail", "failed", "blocked", "rejected", "error", "needs_review", "needs review"}


def _unique(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = safe_str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def normalize_external_verification_record(
    record: Optional[Dict[str, Any]],
    *,
    format_id: str,
    target_tool: str = "Civil3D",
) -> Dict[str, Any]:
    """Normalize external user/engineer import evidence without granting release authority."""

    raw = safe_dict(record)
    verification_result = safe_str(raw.get("result") or raw.get("status")).lower()
    verifier = safe_str(
        raw.get("verifier_identity")
        or raw.get("verifier")
        or raw.get("engineer")
        or raw.get("tested_by")
        or raw.get("user")
    )
    verification_date = safe_str(raw.get("verification_date") or raw.get("date") or raw.get("tested_at"))
    tool_name = safe_str(raw.get("tool") or raw.get("tool_name") or raw.get("target_tool"), target_tool)
    tool_version = safe_str(raw.get("tool_version") or raw.get("version"))
    notes = safe_str(raw.get("notes") or raw.get("summary"))
    record_id = safe_str(raw.get("verification_record_id") or raw.get("record_id") or raw.get("id"))
    evidence_uri = safe_str(raw.get("evidence_uri") or raw.get("result_uri") or raw.get("upload_uri") or raw.get("source"))
    required_present = bool(verifier and verification_date and tool_name and tool_version and verification_result)

    if not raw:
        status = EXTERNAL_VERIFICATION_STATUS_NOT_VERIFIED
        failure_reason = "external_verification_missing"
    elif not required_present:
        status = EXTERNAL_VERIFICATION_STATUS_BLOCKED
        failure_reason = "external_verification_record_incomplete"
    elif verification_result in _PASSED_RESULTS:
        status = EXTERNAL_VERIFICATION_STATUS_PASSED
        failure_reason = ""
    elif verification_result in _FAILED_RESULTS:
        status = EXTERNAL_VERIFICATION_STATUS_BLOCKED
        failure_reason = "external_verification_failed"
    else:
        status = EXTERNAL_VERIFICATION_STATUS_BLOCKED
        failure_reason = "external_verification_result_unknown"

    return {
        "source": "external_verification_record_v1",
        "format": safe_str(format_id),
        "target_tool": tool_name,
        "status": status,
        "verified": status == EXTERNAL_VERIFICATION_STATUS_PASSED,
        "requires_external_verification": status != EXTERNAL_VERIFICATION_STATUS_PASSED,
        "verification_record_id": record_id,
        "verifier_identity": verifier,
        "verification_date": verification_date,
        "tool": tool_name,
        "tool_version": tool_version,
        "result": safe_str(raw.get("result") or raw.get("status")),
        "notes": notes,
        "evidence_uri": evidence_uri,
        "failure_reason": failure_reason,
        "scope": "import_workflow_only",
        "construction_release_allowed": False,
        "civora_signoff_allowed": False,
        "truth_label": (
            "External verification records only confirm the named import/workflow check; "
            "they do not authorize construction use or professional responsibility."
        ),
    }


def _default_sidecar_path(artifact_path: Path) -> Path:
    return artifact_path.with_suffix(f"{artifact_path.suffix}.metadata.json")


def _load_sidecar(sidecar_path: Optional[Path]) -> Dict[str, Any]:
    if sidecar_path is None or not sidecar_path.exists():
        return {}
    try:
        return safe_dict(json.loads(sidecar_path.read_text(encoding="utf-8")))
    except Exception:
        return {}


def _package_report_from_plan_or_sidecar(plan: Dict[str, Any], sidecar: Dict[str, Any]) -> Dict[str, Any]:
    return safe_dict(
        safe_dict(plan.get("meta")).get("export_package_report_v1")
        or sidecar.get("export_package_report_v1")
    )


def _sidecar_metadata_check(artifact_path: Path, sidecar_path: Optional[Path], sidecar: Dict[str, Any]) -> Dict[str, Any]:
    present = bool(sidecar_path and sidecar_path.exists() and sidecar)
    report = safe_dict(sidecar.get("export_package_report_v1"))
    stale = safe_list(sidecar.get("stale_outputs_detected") or report.get("stale_outputs_detected"))
    return {
        "present": present,
        "path": str(sidecar_path) if sidecar_path else "",
        "artifact_path_matches": bool(present and safe_str(sidecar.get("artifact_path")) == str(artifact_path)),
        "export_package_report_present": bool(present and safe_dict(sidecar.get("export_package_report_v1"))),
        "source_canonical_revision": safe_str(sidecar.get("source_canonical_revision") or report.get("source_canonical_revision")),
        "source_canonical_hash": safe_str(sidecar.get("source_canonical_hash") or report.get("source_canonical_hash")),
        "stale_outputs_detected": stale,
        "stale_export_blocked": bool(stale),
        "construction_release_allowed": bool(sidecar.get("construction_release_allowed")),
    }


def _current_canonical_reference(plan: Dict[str, Any]) -> Dict[str, str]:
    meta = safe_dict(plan.get("meta"))
    return {
        "revision": safe_str(
            meta.get("source_canonical_revision")
            or meta.get("canonical_revision")
            or meta.get("canonical_model_revision")
            or meta.get("final_model_revision")
            or meta.get("revision")
        ),
        "hash": safe_str(
            meta.get("source_canonical_hash")
            or meta.get("canonical_model_hash")
            or meta.get("final_model_hash")
            or meta.get("model_hash")
        ),
    }


def _sidecar_current_check(plan: Dict[str, Any], sidecar_check: Dict[str, Any]) -> Dict[str, Any]:
    current = _current_canonical_reference(plan)
    sidecar_revision = safe_str(sidecar_check.get("source_canonical_revision"))
    sidecar_hash = safe_str(sidecar_check.get("source_canonical_hash"))
    revision_matches = bool(not current["revision"] or (sidecar_revision and sidecar_revision == current["revision"]))
    hash_matches = bool(not current["hash"] or (sidecar_hash and sidecar_hash == current["hash"]))
    return {
        "current_canonical_revision": current["revision"],
        "current_canonical_hash": current["hash"],
        "sidecar_canonical_revision": sidecar_revision,
        "sidecar_canonical_hash": sidecar_hash,
        "revision_matches_current": revision_matches,
        "hash_matches_current": hash_matches,
        "matches_current_canonical": revision_matches and hash_matches,
    }


def _canonical_trace_check(plan: Dict[str, Any], sidecar: Dict[str, Any]) -> Dict[str, Any]:
    report = _package_report_from_plan_or_sidecar(plan, sidecar)
    audit = safe_dict(safe_dict(plan.get("meta")).get("export_audit"))
    trace = safe_dict(audit.get("canonical_id_traceability"))
    ids = _unique(report.get("canonical_ids_included") or trace.get("canonical_summary_ids") or [])
    return {
        "present": bool(ids),
        "canonical_ids": ids,
        "audit_ready": trace.get("ready") is True,
        "unmapped_canonical_summary_ids": safe_list(trace.get("unmapped_canonical_summary_ids")),
        "orphaned_action_source_ids": safe_list(trace.get("orphaned_action_source_ids")),
    }


def _profile_section_linkage_check(plan: Dict[str, Any], sidecar: Dict[str, Any]) -> Dict[str, Any]:
    report = _package_report_from_plan_or_sidecar(plan, sidecar)
    audit = safe_dict(safe_dict(plan.get("meta")).get("export_audit"))
    alignment = safe_dict(audit.get("canonical_sheet_alignment"))
    profile_packages = [safe_dict(item) for item in safe_list(report.get("profile_packages")) if safe_dict(item)]
    section_packages = [safe_dict(item) for item in safe_list(report.get("section_packages")) if safe_dict(item)]
    return {
        "profile_packages": len(profile_packages),
        "section_packages": len(section_packages),
        "profile_alignment": alignment.get("profile_alignment") is not False,
        "section_alignment": alignment.get("section_alignment") is not False,
        "profiles_have_canonical_ids": all(safe_list(item.get("canonical_ids")) for item in profile_packages),
        "sections_have_canonical_ids": all(safe_list(item.get("canonical_ids")) for item in section_packages),
    }


def verify_dxf_export(
    artifact_path: Path,
    *,
    plan: Optional[Dict[str, Any]] = None,
    sidecar_path: Optional[Path] = None,
    allowed_layers: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    plan = plan or {}
    if sidecar_path is None:
        sidecar_path = _default_sidecar_path(artifact_path)
    sidecar = _load_sidecar(sidecar_path)
    allowed = set(allowed_layers or DXF_ALLOWED_LAYERS)
    parseable = False
    used_layers: List[str] = []
    table_layers: List[str] = []
    failures: List[str] = []
    try:
        import ezdxf

        doc = ezdxf.readfile(str(artifact_path))
        parseable = True
        table_layers = sorted(layer.dxf.name for layer in doc.layers)
        used_layers = sorted(
            {
                safe_str(entity.dxf.layer)
                for layout in doc.layouts
                for entity in layout
                if safe_str(getattr(entity.dxf, "layer", ""))
            }
        )
    except Exception as exc:
        failures.append(f"dxf_parse_failed:{safe_str(exc)}")

    unknown_layers = sorted(layer for layer in used_layers if layer not in allowed)
    if unknown_layers:
        failures.append("dxf_layer_contract_failed")
    sidecar_check = _sidecar_metadata_check(artifact_path, sidecar_path, sidecar)
    sidecar_current_check = _sidecar_current_check(plan, sidecar_check)
    trace_check = _canonical_trace_check(plan, sidecar)
    linkage_check = _profile_section_linkage_check(plan, sidecar)
    local_contract_ok = (
        parseable
        and not unknown_layers
        and sidecar_check["present"]
        and sidecar_check["artifact_path_matches"]
        and sidecar_check["export_package_report_present"]
        and not sidecar_check["stale_export_blocked"]
        and sidecar_current_check["matches_current_canonical"]
        and trace_check["present"]
        and sidecar_check["construction_release_allowed"] is False
    )
    if not sidecar_check["present"]:
        failures.append("sidecar_metadata_missing")
    if sidecar_check["present"] and not sidecar_check["artifact_path_matches"]:
        failures.append("sidecar_artifact_path_mismatch")
    if sidecar_check["present"] and not sidecar_check["export_package_report_present"]:
        failures.append("sidecar_export_package_report_missing")
    if sidecar_check["stale_export_blocked"]:
        failures.append("stale_export_blocked")
    if not sidecar_current_check["matches_current_canonical"]:
        failures.append("sidecar_canonical_reference_mismatch")
    if not trace_check["present"]:
        failures.append("canonical_id_traceability_missing")
    return {
        "source": "export_external_verification_v1",
        "format": "dxf",
        "artifact_path": str(artifact_path),
        "local_parse_status": "passed" if parseable else "failed",
        "layer_contract_status": "passed" if parseable and not unknown_layers else "failed",
        "used_layers": used_layers,
        "declared_layers": table_layers,
        "unknown_layers": unknown_layers,
        "sidecar_metadata": sidecar_check,
        "sidecar_current_canonical_check": sidecar_current_check,
        "canonical_id_traceability": trace_check,
        "profile_section_linkage": linkage_check,
        "civil3d_external_verification_status": "not_verified",
        "dwg_support_status": DWG_UNSUPPORTED_STATUS,
        "construction_release_allowed": False,
        "construction_release_blocked": True,
        "local_contract_verified": local_contract_ok,
        "externally_verified": False,
        "failures": failures,
        "truth_label": "DXF was locally parsed and checked against Civora layer/metadata contracts only; Civil3D compatibility remains not_verified.",
    }


def verify_landxml_export(xml_text: str, *, plan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    plan = plan or {}
    failures: List[str] = []
    pipe_count = 0
    struct_count = 0
    canonical_ids: List[str] = []
    report_present = False
    civil3d_status = "not_verified"
    landxml_status = "not_verified"
    review_only_flags_ok = False
    construction_release_flags_ok = False
    try:
        root = ET.fromstring(xml_text)
        ET.fromstring(ET.tostring(root, encoding="unicode"))
        pipe_count = len(root.findall(".//Pipe"))
        struct_count = len(root.findall(".//Struct"))
        network = root.find(".//PipeNetwork")
        network_attrs = network.attrib if network is not None else {}
        review_only_flags_ok = (
            safe_str(network_attrs.get("civoraReviewOnly")).lower() == "true"
            and safe_str(network_attrs.get("civoraExternalVerificationRequired")).lower() == "true"
            and safe_str(network_attrs.get("civoraCivil3dVerificationStatus"), "not_verified") == "not_verified"
        )
        release_flags: List[str] = []
        for item in list(root.findall(".//Pipe")) + list(root.findall(".//Struct")):
            release_flags.append(safe_str(item.attrib.get("civoraConstructionReleaseAllowed"), "false").lower())
            if safe_str(item.attrib.get("civoraExternalVerificationStatus"), "not_verified") != "not_verified":
                failures.append("landxml_external_verification_overclaimed")
        construction_release_flags_ok = bool(release_flags) and all(value == "false" for value in release_flags)
        canonical_ids = _unique(
            item.attrib.get("civoraCanonicalId")
            for item in list(root.findall(".//Pipe")) + list(root.findall(".//Struct"))
        )
        report = root.find(".//CivoraExportPackageReport")
        report_present = report is not None
        if report is not None:
            civil3d_status = safe_str(report.attrib.get("civil3d_external_verification_status"), "not_verified")
            landxml_status = safe_str(report.attrib.get("landxml_external_verification_status"), "not_verified")
    except Exception as exc:
        failures.append(f"landxml_parse_failed:{safe_str(exc)}")

    if pipe_count <= 0 and struct_count <= 0:
        failures.append("landxml_pipe_network_empty")
    if not canonical_ids:
        failures.append("canonical_id_traceability_missing")
    if not report_present:
        failures.append("export_package_report_missing")
    if not review_only_flags_ok:
        failures.append("landxml_review_only_flags_missing")
    if not construction_release_flags_ok:
        failures.append("landxml_construction_release_flags_invalid")
    allowed_external_statuses = {
        EXTERNAL_VERIFICATION_STATUS_NOT_VERIFIED,
        EXTERNAL_VERIFICATION_STATUS_BLOCKED,
        EXTERNAL_VERIFICATION_STATUS_PASSED,
    }
    if civil3d_status not in allowed_external_statuses:
        failures.append("civil3d_verification_overclaimed")
    if landxml_status not in allowed_external_statuses:
        failures.append("landxml_external_verification_overclaimed")

    return {
        "source": "export_external_verification_v1",
        "format": "landxml",
        "local_parse_status": "passed" if not any(item.startswith("landxml_parse_failed") for item in failures) else "failed",
        "roundtrip_parse_status": "passed" if not any(item.startswith("landxml_parse_failed") for item in failures) else "failed",
        "schema_like_contract_status": "passed" if not failures else "failed",
        "pipe_count": pipe_count,
        "structure_count": struct_count,
        "canonical_id_traceability": {
            "present": bool(canonical_ids),
            "canonical_ids": canonical_ids,
        },
        "export_package_report_present": report_present,
        "review_only_flags_ok": review_only_flags_ok,
        "construction_release_flags_ok": construction_release_flags_ok,
        "landxml_external_verification_status": landxml_status,
        "civil3d_external_verification_status": civil3d_status or "not_verified",
        "dwg_support_status": DWG_UNSUPPORTED_STATUS,
        "construction_release_allowed": False,
        "construction_release_blocked": True,
        "local_contract_verified": not failures,
        "externally_verified": bool(
            landxml_status == EXTERNAL_VERIFICATION_STATUS_PASSED
            or civil3d_status == EXTERNAL_VERIFICATION_STATUS_PASSED
        ),
        "failures": failures,
        "truth_label": "LandXML was XML-parsed and roundtrip-parsed against Civora's pipe-network contract; external Civil3D evidence is limited to import/workflow review.",
    }


def build_supported_limited_unsupported_matrix(report: Dict[str, Any]) -> Dict[str, List[str]]:
    supported: List[str] = []
    limited: List[str] = []
    unsupported: List[str] = []
    deliverables = safe_dict(report.get("supported_deliverables"))
    for format_id in ("dxf", "landxml", "civil3d", "dwg"):
        row = safe_dict(deliverables.get(format_id))
        status = safe_str(row.get("status"))
        if format_id == "dxf" and row.get("available") is True and status in {"audited_review_ready", "review_ready", "ready", "available"}:
            supported.append(format_id)
        elif row.get("available") is True or format_id == "landxml":
            limited.append(format_id)
        else:
            unsupported.append(format_id)
    if "civil3d" not in unsupported:
        unsupported.append("civil3d")
    if "dwg" not in unsupported:
        unsupported.append("dwg")
    return {
        "supported": _unique(supported),
        "limited": _unique(limited),
        "unsupported": _unique(unsupported),
    }


__all__ = [
    "DXF_ALLOWED_LAYERS",
    "build_supported_limited_unsupported_matrix",
    "normalize_external_verification_record",
    "verify_dxf_export",
    "verify_landxml_export",
]
