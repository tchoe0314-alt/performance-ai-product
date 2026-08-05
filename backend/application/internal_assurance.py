from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from PIL import Image

from backend.ai.hybrid_renderer_engine import ReferenceHybridRendererEngine
from backend.planning.cad_entity_model import CAD_ENGINEERING_OBJECTS_VERSION, build_cad_entity_model
from backend.planning.export_external_verification import (
    normalize_external_verification_record,
    verify_dxf_export,
    verify_landxml_export,
)
from engines.storm.catchment_engine import CatchmentEngine
from engines.storm.hydraulic_engine import HydraulicEngine
from engines.water_sizing_engine import WaterSizingEngine


INTERNAL_ASSURANCE_VERSION = "civora_internal_assurance_v1"
REQUIRED_INTERNAL_GATE_IDS = {
    "source_terrain_truth",
    "semantic_project_lifecycle",
    "engineering_reference_projects",
    "reactive_change_correctness",
    "deliverable_interoperability",
    "heavy_use_reliability",
    "frontend_build_quality",
    "human_style_browser_workflow",
}
EXTERNAL_REQUIREMENT_IDS = {
    "accepted_project_survey_control",
    "external_civil3d_or_target_cad_verification",
    "independent_engineer_benchmark_review",
    "hosted_authenticated_repeat_workflow",
    "real_gpu_visualization_provider",
}


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_artifact_manifest(paths: Iterable[Path | str]) -> Dict[str, Any]:
    artifacts: List[Dict[str, Any]] = []
    missing: List[str] = []
    for value in paths:
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            missing.append(str(path))
            continue
        artifacts.append(
            {
                "path": str(path),
                "file_name": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    manifest_payload = {"artifacts": artifacts, "missing_paths": missing}
    return {
        "version": "internal_artifact_manifest_v1",
        **manifest_payload,
        "artifact_count": len(artifacts),
        "complete": not missing,
        "manifest_sha256": _sha256_value(manifest_payload),
        "truth_label": "Hashes prove file identity and change detection only; they do not prove source authority or engineering acceptance.",
    }


def build_internal_interoperability_bundle(
    *,
    dxf_paths: Iterable[Path | str] = (),
    landxml_paths: Iterable[Path | str] = (),
    plan: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    canonical_plan = dict(plan or {})
    reports: List[Dict[str, Any]] = []
    artifact_paths: List[Path] = []
    for value in dxf_paths:
        path = Path(value).expanduser().resolve()
        artifact_paths.append(path)
        sidecar = path.with_suffix(f"{path.suffix}.metadata.json")
        if sidecar.exists():
            artifact_paths.append(sidecar)
        reports.append(verify_dxf_export(path, plan=canonical_plan))
    for value in landxml_paths:
        path = Path(value).expanduser().resolve()
        artifact_paths.append(path)
        if not path.is_file():
            reports.append(
                {
                    "format": "landxml",
                    "artifact_path": str(path),
                    "local_contract_verified": False,
                    "failures": ["landxml_artifact_missing"],
                }
            )
            continue
        reports.append(verify_landxml_export(path.read_text(encoding="utf-8"), plan=canonical_plan))
        reports[-1]["artifact_path"] = str(path)
    local_contract_verified = bool(reports) and all(report.get("local_contract_verified") is True for report in reports)
    artifact_manifest = build_artifact_manifest(artifact_paths)
    payload: Dict[str, Any] = {
        "version": "internal_interoperability_bundle_v1",
        "local_contract_verified": local_contract_verified,
        "format_count": len(reports),
        "reports": reports,
        "artifact_manifest": artifact_manifest,
        "failures": sorted(
            {
                _safe_str(failure)
                for report in reports
                for failure in _safe_list(report.get("failures"))
                if _safe_str(failure)
            }
        ),
        "external_target_tool_verified": False,
        "construction_release_allowed": False,
        "truth_label": "Civora parsed, roundtripped, and hashed these artifacts internally; named external CAD application behavior remains unverified.",
    }
    payload["bundle_sha256"] = _sha256_value(payload)
    return payload


def _numeric_crosscheck(
    *,
    check_id: str,
    discipline: str,
    expected: float,
    observed: float,
    absolute_tolerance: float,
    reference_method: str,
    implementation_method: str,
    inputs: Mapping[str, Any],
) -> Dict[str, Any]:
    difference = abs(float(observed) - float(expected))
    passed = math.isfinite(difference) and difference <= absolute_tolerance
    return {
        "check_id": check_id,
        "discipline": discipline,
        "inputs": dict(inputs),
        "reference_method": reference_method,
        "implementation_method": implementation_method,
        "methods_are_distinct": reference_method != implementation_method,
        "expected": expected,
        "observed": observed,
        "absolute_difference": difference,
        "absolute_tolerance": absolute_tolerance,
        "passed": passed and reference_method != implementation_method,
    }


def build_internal_calculation_crosschecks() -> Dict[str, Any]:
    runoff_inputs = {"runoff_coefficient": 0.82, "intensity_in_hr": 4.25, "area_acres": 4.2}
    runoff_expected = 1.008 * runoff_inputs["runoff_coefficient"] * runoff_inputs["intensity_in_hr"] * runoff_inputs["area_acres"]
    runoff_observed = CatchmentEngine()._rational_peak_runoff_cfs(
        runoff_inputs["runoff_coefficient"],
        runoff_inputs["intensity_in_hr"],
        runoff_inputs["area_acres"] * 43_560.0,
    )

    manning_inputs = {"diameter_ft": 2.0, "slope_ft_ft": 0.01, "mannings_n": 0.013}
    area = math.pi * manning_inputs["diameter_ft"] ** 2 / 4.0
    hydraulic_radius = manning_inputs["diameter_ft"] / 4.0
    manning_expected = (
        (1.486 / manning_inputs["mannings_n"])
        * area
        * hydraulic_radius ** (2.0 / 3.0)
        * manning_inputs["slope_ft_ft"] ** 0.5
    )
    manning_observed = HydraulicEngine()._full_flow_capacity_cfs(
        manning_inputs["diameter_ft"],
        manning_inputs["slope_ft_ft"],
        manning_inputs["mannings_n"],
    )

    hazen_inputs = {"flow_gpm": 75.0, "diameter_in": 2.0, "hazen_williams_c": 130.0}
    headloss_ft = (
        4.52
        * 100.0
        * hazen_inputs["flow_gpm"] ** 1.85
        / (hazen_inputs["hazen_williams_c"] ** 1.85 * hazen_inputs["diameter_in"] ** 4.87)
    )
    hazen_expected = round(headloss_ft * 0.433, 3)
    hazen_observed = WaterSizingEngine()._hazen_williams_loss_psi_per_100ft(
        hazen_inputs["flow_gpm"],
        hazen_inputs["diameter_in"],
        c_factor=hazen_inputs["hazen_williams_c"],
    )

    site_width = 500.0
    site_height = 4.2 * 43_560.0 / site_width
    project_input = {
        "manual_fields": {
            "canonical_geometry_handoff_v1": [
                {
                    "schema_version": "canonical_geometry_handoff_v1",
                    "object_id": "internal-reference-building",
                    "geometry_id": "internal-reference-building-geometry",
                    "object_name": "Internal Reference Building",
                    "object_type": "office_building",
                    "canonical_object_type": "office_building",
                    "geometry_type": "polygon",
                    "vertices": [
                        {"x": 0.0, "y": 0.0},
                        {"x": site_width, "y": 0.0},
                        {"x": site_width, "y": site_height},
                        {"x": 0.0, "y": site_height},
                        {"x": 0.0, "y": 0.0},
                    ],
                    "valid": True,
                }
            ]
        }
    }
    model = build_cad_entity_model({}, project_input=project_input)
    semantic_object = model[CAD_ENGINEERING_OBJECTS_VERSION]["objects"][0]
    semantic_area_observed = float(semantic_object["engineering_attributes"]["footprint_area_sf"])
    semantic_area_expected = 4.2 * 43_560.0

    checks = [
        _numeric_crosscheck(
            check_id="rational_method_us_customary",
            discipline="hydrology",
            expected=runoff_expected,
            observed=runoff_observed,
            absolute_tolerance=1e-9,
            reference_method="direct_dimensional_equation_1.008_c_i_a",
            implementation_method="catchment_engine_rational_peak_runoff",
            inputs=runoff_inputs,
        ),
        _numeric_crosscheck(
            check_id="manning_full_circular_pipe",
            discipline="storm_hydraulics",
            expected=manning_expected,
            observed=manning_observed,
            absolute_tolerance=1e-9,
            reference_method="direct_full_pipe_manning_equation",
            implementation_method="hydraulic_engine_full_flow_capacity",
            inputs=manning_inputs,
        ),
        _numeric_crosscheck(
            check_id="hazen_williams_pressure_loss",
            discipline="water",
            expected=hazen_expected,
            observed=hazen_observed,
            absolute_tolerance=1e-9,
            reference_method="direct_hazen_williams_headloss_conversion",
            implementation_method="water_sizing_engine_pressure_loss",
            inputs=hazen_inputs,
        ),
        _numeric_crosscheck(
            check_id="semantic_geometry_area",
            discipline="geometry",
            expected=semantic_area_expected,
            observed=semantic_area_observed,
            absolute_tolerance=0.001,
            reference_method="exact_rectangle_area",
            implementation_method="canonical_semantic_geometry_metrics",
            inputs={"width_ft": site_width, "height_ft": site_height},
        ),
    ]
    payload = {"checks": checks}
    return {
        "version": "internal_calculation_crosschecks_v1",
        "status": "passed" if all(check["passed"] for check in checks) else "failed",
        "passed": all(check["passed"] for check in checks),
        "check_count": len(checks),
        "checks": checks,
        "evidence_sha256": _sha256_value(payload),
        "independent_external_review": False,
        "truth_label": "These are separate deterministic implementations inside Civora; they catch regressions but are not an independent licensed-engineer review.",
    }


def build_internal_renderer_contract_probe() -> Dict[str, Any]:
    reference = Image.new("RGB", (96, 64), (224, 226, 222))
    control = Image.new("L", (96, 64), 0)
    depth = Image.new("L", (96, 64), 128)
    renderer = ReferenceHybridRendererEngine()
    result = renderer.render(
        prompt="Internal Civora renderer contract probe",
        negative_prompt="",
        reference_image=reference,
        control_image=control,
        depth_image=depth,
        seed=259,
        output_format="png",
    )
    image_valid = False
    width = 0
    height = 0
    try:
        output = Image.open(BytesIO(result.image_bytes))
        width, height = output.size
        output.verify()
        image_valid = width > 0 and height > 0
    except Exception:
        image_valid = False
    return {
        "version": "internal_renderer_contract_probe_v1",
        "status": "passed" if image_valid else "failed",
        "passed": image_valid,
        "engine": result.model,
        "mime_type": result.mime_type,
        "width": width,
        "height": height,
        "artifact_sha256": hashlib.sha256(result.image_bytes).hexdigest() if result.image_bytes else "",
        "self_hosted": True,
        "photorealistic": False,
        "external_provider_used": False,
        "truth_label": "This deterministic probe proves the internal image contract only; it is not a photorealistic GPU-renderer result.",
    }


def _hosted_repeat_summary(hosted_report: Mapping[str, Any]) -> Dict[str, Any]:
    report = dict(hosted_report or {})
    authenticated = _safe_dict(report.get("authenticated_smoke"))
    repeat_count = int(authenticated.get("repeat_count") or (1 if authenticated.get("status") == "passed" else 0))
    passed_runs = int(authenticated.get("passed_runs") or (repeat_count if authenticated.get("status") == "passed" else 0))
    return {
        "status": _safe_str(authenticated.get("status"), "not_provided"),
        "repeat_count": repeat_count,
        "passed_runs": passed_runs,
        "repeated_authenticated_workflow_proven": repeat_count >= 2 and passed_runs >= 2,
        "credentials_recorded": False,
    }


def _external_requirement_status(
    requirement_id: str,
    external_evidence: Mapping[str, Any],
    hosted_summary: Mapping[str, Any],
    renderer_status: Mapping[str, Any],
) -> Dict[str, Any]:
    record = _safe_dict(external_evidence.get(requirement_id))
    missing_fields: List[str] = []
    satisfied = False
    normalized_record = deepcopy(record)
    if requirement_id == "accepted_project_survey_control":
        required = {
            "accepted_by": record.get("accepted_by") or record.get("surveyor") or record.get("verifier_identity"),
            "acceptance_date": record.get("acceptance_date") or record.get("verification_date"),
            "coordinate_system": record.get("coordinate_system"),
            "datum": record.get("datum") or record.get("vertical_datum"),
            "artifact_hashes": record.get("artifact_hashes"),
        }
        missing_fields = [key for key, value in required.items() if value in (None, "", [], {})]
        satisfied = record.get("status") in {"accepted", "verified"} and not missing_fields
    elif requirement_id == "external_civil3d_or_target_cad_verification":
        normalized_record = normalize_external_verification_record(
            record,
            format_id=_safe_str(record.get("format"), "dxf_landxml"),
            target_tool=_safe_str(record.get("target_tool") or record.get("tool"), "target_cad_tool"),
        )
        satisfied = normalized_record.get("verified") is True
        if not satisfied:
            missing_fields = [_safe_str(normalized_record.get("failure_reason"), "external_verification_incomplete")]
    elif requirement_id == "independent_engineer_benchmark_review":
        attestation = _safe_dict(record.get("attestation"))
        required = {
            "reviewer": attestation.get("reviewer") or record.get("reviewer"),
            "qualification": attestation.get("qualification") or attestation.get("license") or record.get("reviewer_license"),
            "review_date": attestation.get("review_date") or record.get("review_date"),
            "benchmark_ids": attestation.get("benchmark_ids") or record.get("benchmark_ids"),
            "artifact_hashes": record.get("artifact_hashes"),
            "disposition": attestation.get("disposition") or record.get("disposition"),
        }
        missing_fields = [key for key, value in required.items() if value in (None, "", [], {})]
        satisfied = record.get("status") in {"passed", "accepted", "verified"} and not missing_fields
    elif requirement_id == "hosted_authenticated_repeat_workflow":
        satisfied = bool(hosted_summary.get("repeated_authenticated_workflow_proven"))
    elif requirement_id == "real_gpu_visualization_provider":
        satisfied = bool(
            renderer_status.get("self_hosted") is True
            and renderer_status.get("photorealistic") is True
            and renderer_status.get("ready") is True
            and renderer_status.get("smoke_status") == "passed"
            and renderer_status.get("artifact_sha256")
        )
    return {
        "requirement_id": requirement_id,
        "status": "satisfied_for_recorded_scope" if satisfied else "external_evidence_required",
        "satisfied": satisfied,
        "evidence_recorded": bool(record),
        "missing_fields": missing_fields,
        "record": normalized_record,
    }


def build_internal_assurance_bundle(
    *,
    validation_report: Mapping[str, Any],
    artifact_paths: Iterable[Path | str] = (),
    survey_control_package: Optional[Mapping[str, Any]] = None,
    interoperability_reports: Iterable[Mapping[str, Any]] = (),
    hosted_report: Optional[Mapping[str, Any]] = None,
    renderer_status: Optional[Mapping[str, Any]] = None,
    external_evidence: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    validation = dict(validation_report or {})
    gate_rows = [_safe_dict(row) for row in _safe_list(validation.get("gates"))]
    gate_status = {
        _safe_str(row.get("gate_id")): _safe_str(row.get("status"))
        for row in gate_rows
        if _safe_str(row.get("gate_id"))
    }
    passed_gate_ids = {gate_id for gate_id, status in gate_status.items() if status == "passed"}
    missing_internal_gate_ids = sorted(REQUIRED_INTERNAL_GATE_IDS - passed_gate_ids)
    calculation_crosschecks = build_internal_calculation_crosschecks()
    renderer_contract_probe = build_internal_renderer_contract_probe()
    artifact_manifest = build_artifact_manifest(artifact_paths)
    survey = dict(survey_control_package or {})
    interop = [dict(item) for item in interoperability_reports]
    interop_passed = bool(interop) and all(item.get("local_contract_verified") is True for item in interop)
    hosted = _hosted_repeat_summary(dict(hosted_report or {}))
    renderer = dict(renderer_status or {})
    external = dict(external_evidence or {})
    requirement_statuses = [
        _external_requirement_status(requirement_id, external, hosted, renderer)
        for requirement_id in sorted(EXTERNAL_REQUIREMENT_IDS)
    ]
    internal_complete = (
        not missing_internal_gate_ids
        and calculation_crosschecks["passed"] is True
        and validation.get("success") is True
    )
    external_complete = all(item["satisfied"] for item in requirement_statuses)
    payload: Dict[str, Any] = {
        "version": INTERNAL_ASSURANCE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "internal_software_assurance_complete": internal_complete,
        "internal_gate_status": gate_status,
        "missing_internal_gate_ids": missing_internal_gate_ids,
        "calculation_crosschecks": calculation_crosschecks,
        "artifact_manifest": artifact_manifest,
        "survey_control": {
            "status": "validated_input_recorded" if survey.get("production_usable") is True else "not_accepted_or_not_provided",
            "internally_normalized": bool(survey),
            "production_usable": survey.get("production_usable") is True,
            "package": deepcopy(survey),
            "truth_label": "Civora can validate and register supplied survey evidence, but it cannot create accepted survey control from public GIS or imagery.",
        },
        "interoperability": {
            "status": "internal_artifact_contracts_passed" if interop_passed else "artifact_evidence_not_provided",
            "local_contract_verified": interop_passed,
            "reports": deepcopy(interop),
            "external_target_tool_verified": False,
            "truth_label": "Internal parsing and roundtrip checks do not prove behavior in Civil3D, AutoCAD, or another named external tool.",
        },
        "hosted_authenticated_repeat": hosted,
        "internal_renderer": {
            "status": deepcopy(renderer),
            "contract_probe": renderer_contract_probe,
            "self_hosted_path_available": renderer_contract_probe["passed"] is True,
            "real_photorealistic_smoke_proven": any(
                item["requirement_id"] == "real_gpu_visualization_provider" and item["satisfied"]
                for item in requirement_statuses
            ),
        },
        "external_requirements": requirement_statuses,
        "external_evidence_complete": external_complete,
        "construction_release_allowed": False,
        "truth_label": (
            "Internal assurance proves named software contracts and recorded artifacts only. Accepted survey/control, "
            "independent professional review, and external target-tool behavior remain separate evidence when not recorded."
        ),
    }
    payload["bundle_sha256"] = _sha256_value(payload)
    return payload


__all__ = [
    "EXTERNAL_REQUIREMENT_IDS",
    "INTERNAL_ASSURANCE_VERSION",
    "REQUIRED_INTERNAL_GATE_IDS",
    "build_artifact_manifest",
    "build_internal_assurance_bundle",
    "build_internal_calculation_crosschecks",
    "build_internal_interoperability_bundle",
    "build_internal_renderer_contract_probe",
]
