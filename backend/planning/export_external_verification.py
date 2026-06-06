from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from .common import safe_dict, safe_list, safe_str


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
    return {
        "present": present,
        "path": str(sidecar_path) if sidecar_path else "",
        "artifact_path_matches": bool(present and safe_str(sidecar.get("artifact_path")) == str(artifact_path)),
        "export_package_report_present": bool(present and safe_dict(sidecar.get("export_package_report_v1"))),
        "construction_release_allowed": bool(sidecar.get("construction_release_allowed")),
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
    trace_check = _canonical_trace_check(plan, sidecar)
    linkage_check = _profile_section_linkage_check(plan, sidecar)
    local_contract_ok = (
        parseable
        and not unknown_layers
        and (not sidecar_path or sidecar_check["present"])
        and sidecar_check["construction_release_allowed"] is False
    )
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
        "canonical_id_traceability": trace_check,
        "profile_section_linkage": linkage_check,
        "civil3d_external_verification_status": "not_verified",
        "dwg_support_status": "unsupported_no_writer",
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
    try:
        root = ET.fromstring(xml_text)
        ET.fromstring(ET.tostring(root, encoding="unicode"))
        pipe_count = len(root.findall(".//Pipe"))
        struct_count = len(root.findall(".//Struct"))
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
        "landxml_external_verification_status": landxml_status,
        "civil3d_external_verification_status": civil3d_status or "not_verified",
        "dwg_support_status": "unsupported_no_writer",
        "construction_release_allowed": False,
        "construction_release_blocked": True,
        "local_contract_verified": not failures,
        "externally_verified": False,
        "failures": failures,
        "truth_label": "LandXML was XML-parsed and roundtrip-parsed against Civora's pipe-network contract only; Civil3D workflow compatibility remains not_verified.",
    }


def build_supported_limited_unsupported_matrix(report: Dict[str, Any]) -> Dict[str, List[str]]:
    supported: List[str] = []
    limited: List[str] = []
    unsupported: List[str] = []
    deliverables = safe_dict(report.get("supported_deliverables"))
    for format_id in ("dxf", "landxml", "civil3d", "dwg"):
        row = safe_dict(deliverables.get(format_id))
        status = safe_str(row.get("status"))
        if format_id == "dxf" and row.get("available") is True and row.get("review_ready") is True:
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
    "verify_dxf_export",
    "verify_landxml_export",
]
