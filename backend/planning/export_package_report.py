from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Sequence

from .common import blocker_explanations, safe_dict, safe_list, safe_str
from .dwg_compatibility import DWG_UNSUPPORTED_STATUS, dwg_strategy_from_meta
from .production_evidence import build_production_evidence
from .production_depth import build_cad_interop_metadata
from .export_external_verification import normalize_external_verification_record
from .plotting_standards import build_plotting_standards
from .release_gates import construction_release_blockers_from_meta, final_plan_requires_construction_release
from .smart_fix import build_smart_fix_recommendations
from .annotation_standards import build_annotation_standards_trace
from .symbol_block_library import build_symbol_block_reference_trace


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
    for row in safe_list(quantities.get("line_items") or quantities.get("items") or quantities.get("rows")):
        ids.extend(_ids_from_record(safe_dict(row)))
    for key in ("profiles", "cross_sections", "alignments"):
        for row in safe_list(meta.get(key)):
            ids.extend(_ids_from_record(safe_dict(row)))
    evidence = safe_dict(meta.get("production_evidence"))
    for row in safe_list(safe_dict(evidence.get("profile_section")).get("profiles")):
        ids.extend(_ids_from_record(safe_dict(row)))
    for row in safe_list(safe_dict(evidence.get("profile_section")).get("cross_sections")):
        ids.extend(_ids_from_record(safe_dict(row)))
    for row in safe_list(safe_dict(evidence.get("quantity_cost")).get("quantity_line_items")):
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


def _quantity_line_items(meta: Dict[str, Any], export_type: str) -> List[Dict[str, Any]]:
    quantities = safe_dict(meta.get("quantities"))
    audit_by_metric: Dict[str, Dict[str, Any]] = {}
    for source in (
        safe_dict(quantities.get("quantity_audit")),
        safe_dict(quantities.get("trace")),
        safe_dict(quantities.get("explain")),
        safe_dict(safe_dict(quantities.get("meta_summary")).get("quantity_audit")),
    ):
        for metric, row in source.items():
            audit_by_metric[safe_str(metric)] = safe_dict(row)

    rows: List[Dict[str, Any]] = []
    line_items = safe_list(quantities.get("line_items") or quantities.get("items") or quantities.get("rows"))
    for index, row in enumerate(line_items, start=1):
        rec = safe_dict(row)
        if not rec:
            continue
        metric = safe_str(rec.get("metric") or rec.get("name") or rec.get("item") or rec.get("description"), f"quantity-{index}")
        source_rec = {key: value for key, value in rec.items() if key not in {"id", "line_item_id"}}
        ids = _ids_from_record(source_rec) + _ids_from_record(audit_by_metric.get(metric, {}))
        rows.append(
            {
                "package_type": safe_str(export_type),
                "record_type": "quantity_line_item",
                "record_id": safe_str(rec.get("id") or rec.get("line_item_id"), metric),
                "metric": metric,
                "quantity": rec.get("quantity", rec.get("value")),
                "unit": safe_str(rec.get("unit") or rec.get("units")),
                "canonical_ids": _unique(ids),
                "engineer_review_required": True,
                "civora_signoff_allowed": False,
                "construction_release_allowed": False,
                "review_package_only": True,
            }
        )

    if rows:
        return rows

    for index, (metric, audit) in enumerate(audit_by_metric.items(), start=1):
        if not metric:
            continue
        rows.append(
            {
                "package_type": safe_str(export_type),
                "record_type": "quantity_line_item",
                "record_id": safe_str(audit.get("id") or audit.get("line_item_id"), metric or f"quantity-{index}"),
                "metric": metric,
                "quantity": audit.get("quantity", audit.get("value")),
                "unit": safe_str(audit.get("unit") or audit.get("units")),
                "canonical_ids": _ids_from_record(audit),
                "engineer_review_required": True,
                "civora_signoff_allowed": False,
                "construction_release_allowed": False,
                "review_package_only": True,
            }
        )
    return rows


def _external_verification_record(meta: Dict[str, Any], *keys: str) -> Dict[str, Any]:
    external = safe_dict(meta.get("external_verification") or meta.get("external_verification_records"))
    for key in keys:
        direct = safe_dict(meta.get(key))
        if direct:
            return direct
        nested = safe_dict(external.get(key))
        if nested:
            return nested
    records = safe_list(external.get("records") or meta.get("external_verification_records"))
    wanted = {key.lower() for key in keys}
    for item in records:
        rec = safe_dict(item)
        format_id = safe_str(rec.get("format") or rec.get("export_format")).lower()
        tool = safe_str(rec.get("tool") or rec.get("target_tool")).lower()
        if format_id in wanted or tool in wanted:
            return rec
    return {}


def _external_verification_hooks(meta: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    dwg_strategy = dwg_strategy_from_meta(meta)
    landxml = normalize_external_verification_record(
        _external_verification_record(meta, "landxml", "landxml_external_verification"),
        format_id="landxml",
        target_tool="LandXML",
    )
    civil3d = normalize_external_verification_record(
        _external_verification_record(meta, "civil3d", "civil3d_external_verification"),
        format_id="civil3d",
        target_tool="Civil3D",
    )
    dwg = normalize_external_verification_record(
        _external_verification_record(meta, "dwg", "dwg_external_verification"),
        format_id="dwg",
        target_tool="DWG",
    )
    dwg["status"] = dwg_strategy["dwg_status"]
    dwg["verified"] = bool(dwg_strategy["dwg_review_ready"])
    dwg["requires_external_verification"] = True
    dwg["native_dwg_writer"] = False
    dwg["conversion_hook"] = deepcopy(dwg_strategy["conversion_hook"])
    return {"landxml": landxml, "civil3d": civil3d, "dwg": dwg}


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
    formats["dxf"]["preservation_contract"] = {
        "layers": "verified_by_local_parse_when_export_exists",
        "object_types": "verified_by_local_parse_for_supported_entities",
        "blocks_symbols": "placeholder_preservation_checked_when_present",
        "text_labels": "verified_by_local_parse_when_present",
        "dimensions": "verified_where_supported_by_exporter",
        "canonical_ids": "required_via_sidecar_and_export_audit_traceability",
    }
    formats["dxf"]["verification_scope"] = "Civora DXF export -> local parse -> Civora verification"
    formats["civil3d"]["available"] = False
    formats["civil3d"]["review_ready"] = False
    formats["civil3d"]["status"] = "not_verified"
    formats["civil3d"]["workflow_state"] = "not_verified"
    formats["civil3d"]["required_external_record"] = {
        "verifier_identity": True,
        "verification_date": True,
        "tool": True,
        "tool_version": True,
        "source_artifact_hashes": True,
        "import_result": True,
        "observed_limitations": True,
    }
    dwg_strategy = safe_dict(cad_interop.get("dwg_strategy"))
    formats["dwg"]["available"] = bool(dwg_strategy.get("dwg_export_supported"))
    formats["dwg"]["review_ready"] = bool(dwg_strategy.get("dwg_review_ready"))
    formats["dwg"]["status"] = safe_str(dwg_strategy.get("dwg_status"), DWG_UNSUPPORTED_STATUS)
    formats["dwg"]["native_writer"] = False
    formats["dwg"]["requires_external_workflow_record"] = True
    formats["dwg"]["external_conversion_opt_in_required"] = True
    formats["dwg"]["review_artifact_only"] = True
    if not export_audit_ready:
        formats["dxf"]["review_ready"] = False
        if formats["dxf"]["status"] in {"", "ready", "review_ready", "available"}:
            formats["dxf"]["status"] = "blocked_by_export_audit"
    return formats


def _civil3d_compatibility_status(external_verification: Dict[str, Dict[str, Any]]) -> str:
    status = safe_str(safe_dict(external_verification.get("civil3d")).get("status"), "not_verified")
    if status == "externally_verified_review_only":
        return "externally_verified_for_import_workflow_only"
    if status == "blocked_needs_review":
        return "blocked_needs_review"
    return "not_verified"


def _apply_external_verification_to_formats(
    formats: Dict[str, Dict[str, Any]],
    external_verification: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    updated = deepcopy(formats)
    for format_id in ("landxml", "civil3d"):
        status = safe_str(safe_dict(external_verification.get(format_id)).get("status"), "not_verified")
        if status in {"blocked_needs_review", "externally_verified_review_only", "not_verified"}:
            updated.setdefault(format_id, {})["status"] = status
            updated.setdefault(format_id, {})["workflow_state"] = status
        updated.setdefault(format_id, {})["construction_ready"] = False
    dwg_status = safe_str(safe_dict(external_verification.get("dwg")).get("status"))
    if dwg_status:
        updated.setdefault("dwg", {})["status"] = dwg_status
    updated.setdefault("dwg", {})["construction_ready"] = False
    updated.setdefault("dwg", {})["native_writer"] = False
    updated.setdefault("dwg", {})["review_artifact_only"] = True
    return updated


def build_export_package_report_v1(
    plan: Dict[str, Any],
    *,
    export_type: str,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    meta = safe_dict(plan.get("meta"))
    production_evidence = safe_dict(meta.get("production_evidence")) or build_production_evidence(plan)
    evidence_meta = {**meta, "production_evidence": production_evidence}
    cad_interop = safe_dict(meta.get("cad_interop")) or build_cad_interop_metadata(plan)
    dwg_strategy = dwg_strategy_from_meta({**meta, "cad_interop": cad_interop})
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
    if not _canonical_ids(evidence_meta):
        missing_inputs.append("canonical_id_traceability")
    evidence_blockers = safe_list(production_evidence.get("blockers"))
    if evidence_blockers:
        missing_inputs.append("canonical_production_evidence")

    construction_blockers = construction_release_blockers_from_meta(
        meta,
        requires_construction_release=final_plan_requires_construction_release(plan),
    )
    audit_blocked = export_audit.get("export_blocked") is True or export_audit.get("production_export_ready") is False
    gate_blocked = any(status != "ready" for status in (standards_status, existing_status, depth_status))
    construction_release_blocked = True
    formats = _format_matrix(cad_interop, bool(export_audit and not audit_blocked))
    external_verification = _external_verification_hooks(meta)
    formats = _apply_external_verification_to_formats(formats, external_verification)
    civil3d_compatibility = _civil3d_compatibility_status(external_verification)
    annotation_trace = build_annotation_standards_trace(meta, export_type=safe_str(export_type))
    symbol_reference_trace = build_symbol_block_reference_trace(meta)
    plotting_standards = build_plotting_standards(meta)
    review_blocked = bool(audit_blocked or gate_blocked or stale)
    deliverable_confidence = (
        "construction_blocked"
        if review_blocked
        else "ready_for_engineer_review"
        if export_audit.get("production_export_ready") is True
        else "review_only_unverified"
    )
    canonical_ids = _canonical_ids(evidence_meta)
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
        "canonical_evidence_version": safe_str(production_evidence.get("version")),
        "canonical_evidence": deepcopy(production_evidence),
        "canonical_evidence_blockers": deepcopy(evidence_blockers),
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
        "smart_fix_recommendations_v1": build_smart_fix_recommendations(plan, meta=meta),
        "canonical_ids_included": canonical_ids,
        "annotation_standard_trace": annotation_trace,
        "symbol_block_reference_trace": symbol_reference_trace,
        "layer_contract_status": _layer_contract_status(meta, cad_interop),
        "paper_model_plotting_standards_v1": plotting_standards,
        "sheet_manager": deepcopy(plotting_standards["sheet_manager"]),
        "plot_package": {
            "review_pdf_print_package": True,
            "sheet_json": True,
            "review_watermark": plotting_standards["plot_styles"]["review_watermark"],
            "approved_construction_documents": False,
            "submission_ready": False,
            "engineer_review_required": True,
            "construction_release_allowed": False,
        },
        "deliverable_confidence": deliverable_confidence,
        "quantity_line_items": _quantity_line_items(meta, safe_str(export_type)),
        "profile_packages": _deliverable_records(meta, "profiles", safe_str(export_type)),
        "section_packages": _deliverable_records(meta, "cross_sections", safe_str(export_type)),
        "external_verification": external_verification,
        "supported_deliverables": deepcopy(formats),
        "dxf_compatibility_matrix": deepcopy(formats["dxf"].get("preservation_contract")),
        "external_workflow_requirements": {
            "landxml": {
                "workflow_states": ["not_verified", "blocked_needs_review", "externally_verified_review_only"],
                "current_state": safe_str(formats["landxml"].get("workflow_state") or formats["landxml"].get("status"), "not_verified"),
                "review_only": True,
            },
            "civil3d": {
                "workflow_states": ["not_verified", "blocked_needs_review", "externally_verified_review_only"],
                "current_state": civil3d_compatibility,
                "required_record": deepcopy(formats["civil3d"].get("required_external_record")),
                "review_only": True,
            },
            "dwg": {
                "native_supported": False,
                "external_conversion_hook_required": True,
                "external_workflow_record_required": True,
                "current_state": dwg_strategy["dwg_status"],
                "review_only": True,
            },
        },
        "cad_interop_blockers": {
            "dwg": dwg_strategy["dwg_unsupported_reason"],
            "civil3d": "Civil 3D remains not_verified until a target workflow record documents tool/version, source hashes, import result, and limitations.",
        },
        "dwg_strategy": dwg_strategy,
        "dwg_capability_matrix": dwg_strategy["capability_matrix"],
        "dwg_provider_options": dwg_strategy["provider_options"],
        "civil3d_compatibility": civil3d_compatibility,
        "dwg_compatibility": dwg_strategy["dwg_status"],
        "landxml_compatibility": formats["landxml"]["status"],
        "truth_label": "Export package report is traceable review metadata only. Civora never signs, seals, certifies, or approves construction; construction release requires external licensed engineer/user action outside Civora.",
    }


__all__ = ["build_export_package_report_v1"]
