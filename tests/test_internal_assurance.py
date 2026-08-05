from pathlib import Path

from backend.application.internal_assurance import (
    EXTERNAL_REQUIREMENT_IDS,
    REQUIRED_INTERNAL_GATE_IDS,
    build_artifact_manifest,
    build_internal_assurance_bundle,
    build_internal_calculation_crosschecks,
    build_internal_interoperability_bundle,
    build_internal_renderer_contract_probe,
)
from backend.planning.landxml_io import build_landxml_pipe_network
from output.dxf_exporter import save_dxf
from tests.test_export_package_report import _plan


def _validation_report() -> dict:
    return {
        "success": True,
        "gates": [{"gate_id": gate_id, "status": "passed"} for gate_id in sorted(REQUIRED_INTERNAL_GATE_IDS)],
    }


def test_internal_crosschecks_use_distinct_methods_and_pass() -> None:
    result = build_internal_calculation_crosschecks()

    assert result["passed"] is True
    assert result["check_count"] == 4
    assert len(result["evidence_sha256"]) == 64
    assert all(check["methods_are_distinct"] is True for check in result["checks"])
    assert all(check["passed"] is True for check in result["checks"])


def test_internal_renderer_contract_probe_needs_no_external_provider() -> None:
    result = build_internal_renderer_contract_probe()

    assert result["passed"] is True
    assert result["artifact_sha256"]
    assert result["self_hosted"] is True
    assert result["external_provider_used"] is False
    assert result["photorealistic"] is False


def test_artifact_manifest_hashes_files_and_reports_missing_paths(tmp_path: Path) -> None:
    artifact = tmp_path / "survey.csv"
    artifact.write_text("point,x,y,z\nP1,0,0,100\n", encoding="utf-8")

    manifest = build_artifact_manifest([artifact, tmp_path / "missing.dxf"])

    assert manifest["artifact_count"] == 1
    assert manifest["complete"] is False
    assert len(manifest["artifacts"][0]["sha256"]) == 64
    assert manifest["missing_paths"] == [str((tmp_path / "missing.dxf").resolve())]


def test_internal_assurance_never_promotes_missing_external_evidence() -> None:
    bundle = build_internal_assurance_bundle(validation_report=_validation_report())

    assert bundle["internal_software_assurance_complete"] is True
    assert bundle["external_evidence_complete"] is False
    assert bundle["construction_release_allowed"] is False
    assert {item["requirement_id"] for item in bundle["external_requirements"]} == EXTERNAL_REQUIREMENT_IDS
    assert all(item["satisfied"] is False for item in bundle["external_requirements"])
    assert len(bundle["bundle_sha256"]) == 64


def test_recorded_internal_and_external_evidence_is_scoped_truthfully(tmp_path: Path) -> None:
    external = {
        "accepted_project_survey_control": {
            "status": "accepted",
            "artifact_hashes": {"survey.csv": "a" * 64},
            "accepted_by": "Licensed Surveyor",
            "acceptance_date": "2026-08-04",
            "coordinate_system": "NAD83 / Nebraska",
            "datum": "NAVD88",
        },
        "external_civil3d_or_target_cad_verification": {
            "status": "passed",
            "verifier_identity": "Independent CAD Reviewer",
            "verification_date": "2026-08-04",
            "tool": "Autodesk Civil 3D",
            "tool_version": "2026",
            "source_artifacts": ["review.dxf"],
            "artifact_hashes": {"review.dxf": "b" * 64},
            "workflow_steps": ["Open DXF", "Inspect layers", "Compare coordinates"],
            "import_result": "opened_with_recorded_limitations",
        },
        "independent_engineer_benchmark_review": {
            "status": "passed",
            "artifact_hashes": {"benchmark.json": "d" * 64},
            "attestation": {
                "reviewer": "Independent Reviewer",
                "qualification": "Licensed civil engineer",
                "review_date": "2026-08-04",
                "benchmark_ids": ["commercial", "drainage", "utility"],
                "disposition": "passed_with_recorded_limitations",
            },
        },
    }
    hosted = {
        "authenticated_smoke": {"status": "passed", "repeat_count": 2, "passed_runs": 2},
    }
    renderer = {
        "self_hosted": True,
        "photorealistic": True,
        "ready": True,
        "smoke_status": "passed",
        "artifact_sha256": "c" * 64,
    }
    interop = [{"format": "dxf", "local_contract_verified": True}]
    bundle = build_internal_assurance_bundle(
        validation_report=_validation_report(),
        interoperability_reports=interop,
        hosted_report=hosted,
        renderer_status=renderer,
        external_evidence=external,
    )

    assert bundle["interoperability"]["local_contract_verified"] is True
    assert bundle["interoperability"]["external_target_tool_verified"] is False
    assert bundle["hosted_authenticated_repeat"]["repeated_authenticated_workflow_proven"] is True
    assert bundle["internal_renderer"]["real_photorealistic_smoke_proven"] is True
    assert bundle["external_evidence_complete"] is True
    assert bundle["construction_release_allowed"] is False


def test_incomplete_external_records_cannot_satisfy_requirements() -> None:
    bundle = build_internal_assurance_bundle(
        validation_report=_validation_report(),
        external_evidence={
            "accepted_project_survey_control": {"status": "accepted", "artifact_hashes": {"survey": "a" * 64}},
            "external_civil3d_or_target_cad_verification": {"status": "passed", "artifact_hashes": {"dxf": "b" * 64}},
            "independent_engineer_benchmark_review": {"status": "passed", "attestation": {"reviewer": "Someone"}},
        },
    )

    by_id = {item["requirement_id"]: item for item in bundle["external_requirements"]}
    assert by_id["accepted_project_survey_control"]["satisfied"] is False
    assert "accepted_by" in by_id["accepted_project_survey_control"]["missing_fields"]
    assert by_id["external_civil3d_or_target_cad_verification"]["satisfied"] is False
    assert by_id["independent_engineer_benchmark_review"]["satisfied"] is False


def test_missing_required_internal_gate_keeps_assurance_incomplete() -> None:
    report = _validation_report()
    report["gates"] = report["gates"][1:]

    bundle = build_internal_assurance_bundle(validation_report=report)

    assert bundle["internal_software_assurance_complete"] is False
    assert len(bundle["missing_internal_gate_ids"]) == 1


def test_internal_interoperability_bundle_parses_hashes_and_preserves_truth(tmp_path: Path) -> None:
    plan = _plan()
    dxf_path = tmp_path / "internal-review.dxf"
    landxml_path = tmp_path / "internal-review.xml"
    save_dxf(plan, filename=str(dxf_path))
    landxml_path.write_text(build_landxml_pipe_network(plan, network_name="Internal Review"), encoding="utf-8")

    bundle = build_internal_interoperability_bundle(
        dxf_paths=[dxf_path],
        landxml_paths=[landxml_path],
        plan=plan,
    )

    assert bundle["local_contract_verified"] is True
    assert bundle["format_count"] == 2
    assert bundle["artifact_manifest"]["artifact_count"] == 3
    assert bundle["external_target_tool_verified"] is False
    assert bundle["construction_release_allowed"] is False
    assert len(bundle["bundle_sha256"]) == 64
