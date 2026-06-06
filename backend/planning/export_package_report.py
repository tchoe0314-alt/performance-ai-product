from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Sequence

from .common import blocker_explanations, safe_dict, safe_list, safe_str
from .production_depth import build_cad_interop_metadata
from .release_gates import construction_release_blockers_from_meta, final_plan_requires_construction_release


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _canonical_hash(meta: Dict[str, Any]) -> str:
    return safe_str(
        meta.get("source_canonical_hash")
        or meta.get("canonical_model_hash")
        or meta.get("final_model_hash")
        or meta.get("model_hash")
    )


def _canonical_revision(meta: Dict[str, Any]) -> str:
    return safe_str(
        meta.get("source_canonical_revision")
        or meta.get("canonical_revision")
        or meta.get("canonical_model_revision")
        or meta.get("final_model_revision")
        or meta.get("revision")
    )


def _project_id(plan: Dict[str, Any], meta: Dict[str, Any]) -> str:
    return safe_str(plan.get("project_id") or meta.get("project_id") or meta.get("source_project_id"))


def _included_systems(plan: Dict[str, Any], meta: Dict[str, Any]) -> List[str]:
    systems = []
    for key in (
        "layout",
        "grading",
        "drainage",
        "storm_pipes",
        "sanitary",
        "utilities",
        "profiles",
        "cross_sections",
        "quantities",
        "sheet_registry",
    ):
        value = meta.get(key)
        if safe_dict(value) or safe_list(value):
            systems.append(key)
    for action in safe_list(plan.get("actions")):
        rec = safe_dict(action)
        action_meta = safe_dict(rec.get("meta"))
        system = safe_str(action_meta.get("system") or rec.get("system"))
        if system:
            systems.append(system)
    return _unique(systems)


def _excluded_systems(included: Sequence[str], meta: Dict[str, Any]) -> List[str]:
    expected = [
        "layout",
        "grading",
        "drainage",
        "storm_pipes",
        "sanitary",
        "utilities",
        "profiles",
        "cross_sections",
        "quantities",
        "sheet_registry",
    ]
    requested = safe_list(safe_dict(meta.get("deliverables")).get("requested"))
    for item in requested:
        text = safe_str(item).lower()
        if "profile" in text:
            expected.append("profiles")
        if "section" in text:
            expected.append("cross_sections")
        if "quantit" in text or "takeoff" in text:
            expected.append("quantities")
    included_set = set(included)
    return _unique(item for item in expected if item not in included_set)


def _status_from_bool(ready: Any, *, missing_label: str = "missing") -> str:
    if ready is True:
        return "ready"
    if ready is False:
        return "blocked"
    return missing_label


def _standards_status(meta: Dict[str, Any], construction_readiness: Dict[str, Any]) -> str:
    evidence = safe_dict(construction_readiness.get("evidence"))
    if "standards_production_usable" in evidence:
        return _status_from_bool(evidence.get("standards_production_usable"))
    standards = safe_dict(meta.get("standards_package") or meta.get("standards"))
    if standards:
        return _status_from_bool(standards.get("production_usable"))
    return "missing"


def _existing_conditions_status(meta: Dict[str, Any], construction_readiness: Dict[str, Any]) -> str:
    evidence = safe_dict(construction_readiness.get("evidence"))
    if "existing_conditions_production_ready" in evidence:
        return _status_from_bool(evidence.get("existing_conditions_production_ready"))
    existing = safe_dict(
        meta.get("existing_conditions_package")
        or meta.get("canonical_existing_conditions")
        or meta.get("existing_conditions")
    )
    if existing:
        return _status_from_bool(existing.get("production_ready") or existing.get("ready"))
    return "missing"


def _engine_depth_status(meta: Dict[str, Any], construction_readiness: Dict[str, Any]) -> str:
    evidence = safe_dict(construction_readiness.get("evidence"))
    if "civil_production_ready" in evidence:
        return _status_from_bool(evidence.get("civil_production_ready"))
    civil = safe_dict(meta.get("civil_design_readiness") or meta.get("engine_depth_audit") or meta.get("engine_readiness"))
    if civil:
        return _status_from_bool(civil.get("production_ready") or civil.get("ready"))
    return "missing"


def _stale_outputs(meta: Dict[str, Any], source_revision: str, source_hash: str) -> List[str]:
    stale = []
    export_audit = safe_dict(meta.get("export_audit"))
    stale_status = safe_dict(export_audit.get("stale_output_status"))
    stale.extend(safe_list(stale_status.get("dirty_stages")))
    stale.extend(safe_list(safe_dict(export_audit.get("canonical_integrity")).get("dirty_stages")))
    stale.extend(safe_list(meta.get("stale_outputs")))
    stale.extend(safe_list(meta.get("invalidated_targets") or meta.get("dependency_invalidated_targets")))
    for key in ("last_exported_canonical_revision", "export_canonical_revision"):
        previous = safe_str(meta.get(key))
        if previous and source_revision and previous != source_revision:
            stale.append(key)
    for key in ("last_exported_canonical_hash", "export_canonical_hash"):
        previous = safe_str(meta.get(key))
        if previous and source_hash and previous != source_hash:
            stale.append(key)
    previous_report = safe_dict(meta.get("export_package_report_v1"))
    if previous_report:
        previous_revision = safe_str(previous_report.get("source_canonical_revision"))
        previous_hash = safe_str(previous_report.get("source_canonical_hash"))
        if previous_revision and source_revision and previous_revision != source_revision:
            stale.append("export_package_report_v1")
        if previous_hash and source_hash and previous_hash != source_hash:
            stale.append("export_package_report_v1")
    return _unique(stale)


def _canonical_ids(meta: Dict[str, Any]) -> List[str]:
    trace = safe_dict(safe_dict(meta.get("export_audit")).get("canonical_id_traceability"))
    ids = list(safe_list(trace.get("canonical_summary_ids"))) + list(safe_list(trace.get("mapped_action_source_ids")))
    quantities = safe_dict(meta.get("quantities"))
    quantity_audit = safe_dict(safe_dict(quantities.get("meta_summary")).get("quantity_audit"))
    for row in quantity_audit.values():
        ids.extend(safe_list(safe_dict(row).get("source_object_ids")))
    for key in ("quantity_audit", "trace", "explain"):
        for row in safe_dict(quantities.get(key)).values():
            ids.extend(_ids_from_record(safe_dict(row)))
    for key in ("profiles", "cross_sections", "alignments"):
        for row in safe_list(meta.get(key)):
            ids.extend(_ids_from_record(safe_dict(row)))
    return _unique(ids)


def _ids_from_record(record: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    for key in (
        "canonical_id",
        "canonical_source_id",
        "canonical_model_id",
        "alignment_id",
        "alignment_owner",
        "id",
        "profile_id",
        "section_id",
        "source_object_id",
        "quantity_source_id",
    ):
        value = safe_str(record.get(key))
        if value:
            ids.append(value)
    for key in ("canonical_ids", "canonical_source_ids", "source_object_ids", "quantity_source_ids"):
        ids.extend(safe_list(record.get(key)))
    trace = safe_dict(record.get("trace") or record.get("explain") or record.get("canonical_id_traceability"))
    if trace and trace is not record:
        ids.extend(_ids_from_record(trace))
    return _unique(ids)


def _deliverable_records(meta: Dict[str, Any], key: str, export_type: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for index, row in enumerate(safe_list(meta.get(key)), start=1):
        rec = safe_dict(row)
        if not rec:
            continue
        records.append(
            {
                "package_type": export_type,
                "record_type": key[:-1] if key.endswith("s") else key,
                "record_id": safe_str(
                    rec.get("id")
                    or rec.get("name")
                    or rec.get("profile_id")
                    or rec.get("section_id"),
                    f"{key}-{index}",
                ),
                "canonical_ids": _ids_from_record(rec),
                "engineer_review_required": True,
                "civora_signoff_allowed": False,
                "construction_release_allowed": False,
                "review_package_only": True,
            }
        )
    return records


def _layer_contract_status(meta: Dict[str, Any], cad_interop: Dict[str, Any]) -> str:
    audit = safe_dict(meta.get("export_audit"))
    if audit.get("sheet_metadata_consistent") is False:
        return "blocked"
    if cad_interop.get("dxf") is True and audit:
        return "audited_review_ready" if audit.get("export_blocked") is not True else "blocked_by_export_audit"
    return "missing_export_audit"


def _format_matrix(cad_interop: Dict[str, Any], export_audit_ready: bool) -> Dict[str, Dict[str, Any]]:
    checks = {safe_str(item.get("format")): safe_dict(item) for item in safe_list(cad_interop.get("compatibility_checks"))}
    formats: Dict[str, Dict[str, Any]] = {}
    for format_id in ("dxf", "landxml", "civil3d", "dwg"):
        row = checks.get(format_id, {})
        if not row and format_id == "landxml":
            row = {
                "available": bool(cad_interop.get("landxml_pipe_network_contract")),
                "review_ready": bool(cad_interop.get("landxml_pipe_network_contract") and export_audit_ready),
                "construction_ready": False,
                "status": safe_str(cad_interop.get("landxml_pipe_network_contract_status"), "not_available"),
            }
        formats[format_id] = {
            "available": bool(row.get("available")),
            "review_ready": bool(row.get("review_ready")),
            "construction_ready": False,
            "status": safe_str(row.get("status"), "not_available"),
        }
    formats["civil3d"]["available"] = False
    formats["civil3d"]["review_ready"] = False
    formats["civil3d"]["status"] = "not_implemented_not_verified"
    formats["dwg"]["available"] = False
    formats["dwg"]["review_ready"] = False
    formats["dwg"]["status"] = "unsupported_no_writer"
    return formats


def build_export_package_report_v1(
    plan: Dict[str, Any],
    *,
    export_type: str,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    meta = safe_dict(plan.get("meta"))
    cad_interop = safe_dict(meta.get("cad_interop")) or build_cad_interop_metadata(plan)
    export_audit = safe_dict(meta.get("export_audit"))
    construction_readiness = safe_dict(meta.get("construction_readiness"))
    source_revision = _canonical_revision(meta)
    source_hash = _canonical_hash(meta)
    included = _included_systems(plan, meta)
    stale = _stale_outputs(meta, source_revision, source_hash)
    standards_status = _standards_status(meta, construction_readiness)
    existing_status = _existing_conditions_status(meta, construction_readiness)
    depth_status = _engine_depth_status(meta, construction_readiness)
    missing_inputs = []
    if standards_status != "ready":
        missing_inputs.append("production_usable_standards")
    if existing_status != "ready":
        missing_inputs.append("production_ready_existing_conditions")
    if depth_status != "ready":
        missing_inputs.append("production_ready_engine_depth")
    if not export_audit:
        missing_inputs.append("export_audit")
    if not _canonical_ids(meta):
        missing_inputs.append("canonical_id_traceability")

    construction_blockers = construction_release_blockers_from_meta(
        meta,
        requires_construction_release=final_plan_requires_construction_release(plan),
    )
    audit_blocked = export_audit.get("export_blocked") is True or export_audit.get("production_export_ready") is False
    gate_blocked = any(status != "ready" for status in (standards_status, existing_status, depth_status))
    construction_release_blocked = True
    formats = _format_matrix(cad_interop, bool(export_audit and not audit_blocked))
    review_blocked = bool(audit_blocked or gate_blocked or stale)
    deliverable_confidence = (
        "construction_blocked"
        if review_blocked
        else "ready_for_engineer_review"
        if export_audit.get("production_export_ready") is True
        else "review_only_unverified"
    )
    canonical_ids = _canonical_ids(meta)
    return {
        "source": "export_package_report_v1",
        "export_type": safe_str(export_type),
        "source_project_id": _project_id(plan, meta),
        "source_canonical_revision": source_revision,
        "source_canonical_hash": source_hash,
        "generated_at": generated_at or _utc_now_iso(),
        "included_systems": included,
        "excluded_systems": _excluded_systems(included, meta),
        "stale_outputs_detected": stale,
        "missing_inputs": _unique(missing_inputs),
        "standards_status": standards_status,
        "existing_conditions_status": existing_status,
        "engine_depth_status": depth_status,
        "engineer_review_required": True,
        "civora_signoff_allowed": False,
        "construction_release_allowed": False,
        "construction_release_blocked": construction_release_blocked,
        "external_construction_release_required": True,
        "construction_release_blockers": _unique(construction_blockers + safe_list(export_audit.get("blocked_reasons"))),
        "construction_release_blocker_details": blocker_explanations(_unique(construction_blockers + safe_list(export_audit.get("blocked_reasons")))),
        "canonical_ids_included": canonical_ids,
        "layer_contract_status": _layer_contract_status(meta, cad_interop),
        "deliverable_confidence": deliverable_confidence,
        "profile_packages": _deliverable_records(meta, "profiles", safe_str(export_type)),
        "section_packages": _deliverable_records(meta, "cross_sections", safe_str(export_type)),
        "supported_deliverables": deepcopy(formats),
        "civil3d_compatibility": "unsupported_limited_not_verified",
        "dwg_compatibility": "unsupported_no_writer",
        "landxml_compatibility": formats["landxml"]["status"],
        "truth_label": "Export package report is traceable review metadata only. Civora never signs, seals, certifies, or approves construction; construction release requires external licensed engineer/user action outside Civora.",
    }


__all__ = ["build_export_package_report_v1"]
