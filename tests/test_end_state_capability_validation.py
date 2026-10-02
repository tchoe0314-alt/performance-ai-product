from pathlib import Path
import sys

import backend.application.end_state_capability_validation as validation

from backend.application.end_state_capability_validation import (
    END_STATE_VALIDATION_VERSION,
    EXTERNAL_EVIDENCE_REQUIREMENTS,
    build_end_state_validation_gates,
    run_end_state_capability_validation,
)


def test_local_python_gates_use_the_calling_runtime() -> None:
    gates = build_end_state_validation_gates(include_frontend=False, include_browser=False)
    assert all(command[0] == sys.executable for gate in gates for command in gate["commands"])


def test_source_changes_during_validation_cannot_produce_assurance(monkeypatch) -> None:
    revisions = iter([{"head": "before", "tracked_diff_sha256": "one"}, {"head": "after", "tracked_diff_sha256": "two"}])
    monkeypatch.setattr(validation, "_revision_evidence", lambda: next(revisions))
    report = run_end_state_capability_validation(include_frontend=False, include_browser=False,
        selected_gate_ids=["source_terrain_truth"],
        executor=lambda *args: {"exit_code": 0, "elapsed_seconds": 0.0})
    assert report["success"] is False
    assert report["failed_gate_ids"] == ["source_revision_changed"]
    assert report["internal_software_assurance_complete"] is False
    assert report["execution_provenance"]["python_executable"] == sys.executable
    assert report["execution_provenance"]["served_artifact_verified"] is False
    assert report["execution_provenance"]["deployed_artifact_verified"] is False

def test_manifest_covers_every_end_state_proof_layer() -> None:
    gate_ids = {item["gate_id"] for item in build_end_state_validation_gates(
        include_frontend=True, include_browser=True, hosted_url="https://example.test", include_hosted_auth=True)}
    assert gate_ids == {
        "source_terrain_truth",
        "semantic_project_lifecycle",
        "engineering_reference_projects",
        "reactive_change_correctness",
        "deliverable_interoperability",
        "heavy_use_reliability",
        "frontend_build_quality",
        "human_style_browser_workflow",
        "hosted_product_proof",
    }
    assert {item["requirement_id"] for item in EXTERNAL_EVIDENCE_REQUIREMENTS} == {
        "accepted_project_survey_control",
        "external_civil3d_or_target_cad_verification",
        "independent_engineer_benchmark_review",
        "hosted_authenticated_repeat_workflow",
        "real_gpu_visualization_provider",
    }


def test_browser_gate_includes_phase0_integrity_regressions_and_existing_files() -> None:
    gate = next(item for item in build_end_state_validation_gates() if item["gate_id"] == "human_style_browser_workflow")
    paths = {arg for command in gate["commands"] for arg in command if arg.endswith(".spec.ts")}
    assert {
        "tests/live/canonical-edit-command-foundation.spec.ts",
        "tests/live/phase0-candidate-contract.spec.ts",
        "tests/live/dense-commercial-concept-chat240.spec.ts",
        "tests/live/project-object-integration.spec.ts",
        "tests/live/phase0-review-sheet-truth.spec.ts",
        "tests/live/canvas-first-workspace-redesign.spec.ts",
        "tests/live/video-website-regression.spec.ts",
    } <= paths
    root = Path(__file__).resolve().parents[1]
    assert all((root / gate["cwd"] / path).is_file() for path in paths)


def test_runner_stops_each_failed_gate_and_keeps_external_truth_separate(tmp_path: Path) -> None:
    seen = []

    def fake_executor(command, cwd, env):
        seen.append((list(command), cwd, env.get("PLAYWRIGHT_BASE_URL", "")))
        failed = any(str(item).endswith("test_real_firm_end_state_workflow.py") for item in command)
        return {"exit_code": 1 if failed else 0, "elapsed_seconds": 0.01, "stdout": "", "stderr": "failure" if failed else ""}

    output = tmp_path / "validation.json"
    report = run_end_state_capability_validation(
        include_frontend=False,
        include_browser=False,
        selected_gate_ids=["source_terrain_truth", "semantic_project_lifecycle"],
        output_path=output,
        executor=fake_executor,
    )

    assert report["version"] == END_STATE_VALIDATION_VERSION
    assert report["success"] is False
    assert report["failed_gate_ids"] == ["semantic_project_lifecycle"]
    assert report["external_evidence_complete"] is False
    assert report["construction_release_allowed"] is False
    assert report["internal_calculation_crosschecks"]["passed"] is True
    assert report["internal_software_assurance_complete"] is False
    assert output.exists()
    assert len(seen) == 2


def test_hosted_gate_is_opt_in_and_uses_environment_not_embedded_credentials() -> None:
    without_hosted = build_end_state_validation_gates(include_frontend=False, include_browser=False)
    with_hosted = build_end_state_validation_gates(
        include_frontend=False,
        include_browser=False,
        hosted_url="https://civora.example",
        include_hosted_auth=True,
    )

    assert "hosted_product_proof" not in {item["gate_id"] for item in without_hosted}
    hosted = next(item for item in with_hosted if item["gate_id"] == "hosted_product_proof")
    assert hosted["environment"] == {
        "PLAYWRIGHT_BASE_URL": "https://civora.example",
        "PLAYWRIGHT_SKIP_WEBSERVER": "1",
    }
    assert all("password" not in " ".join(command).lower() for command in hosted["commands"])


def test_unknown_gate_name_fails_instead_of_returning_empty_success(tmp_path: Path) -> None:
    report = run_end_state_capability_validation(
        include_frontend=False,
        include_browser=False,
        selected_gate_ids=["semantic_project_lifecyle"],
        output_path=tmp_path / "validation.json",
        executor=lambda command, cwd, env: {
            "exit_code": 0,
            "elapsed_seconds": 0.0,
            "stdout": "",
            "stderr": "",
        },
    )

    assert report["success"] is False
    assert report["failed_gate_ids"] == ["validation_configuration"]
    assert report["gates"][0]["errors"] == ["Unknown validation gate: semantic_project_lifecyle"]


def test_full_internal_gate_manifest_can_complete_software_assurance() -> None:
    report = run_end_state_capability_validation(
        include_frontend=True,
        include_browser=True,
        executor=lambda command, cwd, env: {
            "exit_code": 0,
            "elapsed_seconds": 0.0,
            "stdout": "passed",
            "stderr": "",
        },
    )

    assert report["success"] is True
    assert report["internal_software_assurance_complete"] is True
    assert report["missing_internal_gate_ids"] == []
    assert report["external_evidence_complete"] is False
