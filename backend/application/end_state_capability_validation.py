from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from time import perf_counter
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from backend.application.internal_assurance import (
    REQUIRED_INTERNAL_GATE_IDS,
    build_internal_calculation_crosschecks,
)


END_STATE_VALIDATION_VERSION = "civora_end_state_validation_v1"
ROOT = Path(__file__).resolve().parents[2]


LOCAL_GATES: List[Dict[str, Any]] = [
    {
        "gate_id": "source_terrain_truth",
        "label": "Address, source, survey, terrain, and registration truth",
        "evidence_level": "deterministic_local",
        "commands": [[
            "python3", "-m", "pytest",
            "tests/test_real_input_file_benchmarks.py",
            "tests/test_existing_conditions_importers.py",
            "tests/test_existing_conditions_online.py",
            "tests/test_worldwide_source_discovery.py",
            "tests/test_source_confidence_map.py",
            "-q",
        ]],
    },
    {
        "gate_id": "semantic_project_lifecycle",
        "label": "Semantic objects, persistence, history, and project lifecycle",
        "evidence_level": "deterministic_local",
        "commands": [[
            "python3", "-m", "pytest",
            "tests/test_real_firm_end_state_workflow.py",
            "tests/test_semantic_drafting_objects.py",
            "tests/test_cad_entity_model.py",
            "tests/test_cad_entity_history.py",
            "tests/test_project_lifecycle_collaboration_memory.py",
            "-q",
        ]],
    },
    {
        "gate_id": "engineering_reference_projects",
        "label": "Civil calculation reference projects and independent math checks",
        "evidence_level": "deterministic_local",
        "commands": [[
            "python3", "-m", "pytest",
            "tests/test_real_math_hydraulics.py",
            "tests/test_real_math_big_pass.py",
            "tests/test_engine_hardening_drainage.py",
            "tests/test_engine_hardening_storm.py",
            "tests/test_water_fire_flow_preview.py",
            "tests/test_production_depth_artifacts.py",
            "tests/test_engine_depth_audit.py",
            "tests/test_normal_alpha_scenario_runner.py",
            "-q",
        ]],
    },
    {
        "gate_id": "reactive_change_correctness",
        "label": "Dependency-aware change impact, stale outputs, and selective reruns",
        "evidence_level": "deterministic_local",
        "commands": [[
            "python3", "-m", "pytest",
            "tests/test_reactive_model_contract.py",
            "tests/test_dependency_aware_rerun.py",
            "tests/test_reactive_partial_rerun_entrypoint.py",
            "tests/test_engineering_generation_workflows.py",
            "tests/test_export_package_report.py",
            "-q",
        ]],
    },
    {
        "gate_id": "deliverable_interoperability",
        "label": "Review packages, DXF/LandXML roundtrip, and export freshness",
        "evidence_level": "deterministic_local",
        "commands": [[
            "python3", "-m", "pytest",
            "tests/test_export_external_verification.py",
            "tests/test_cad_entity_dxf_roundtrip.py",
            "tests/test_landxml_io.py",
            "tests/test_export_package_report.py",
            "tests/test_engineer_review_package.py",
            "-q",
        ]],
    },
    {
        "gate_id": "heavy_use_reliability",
        "label": "Large projects, queues, persistence fast paths, and repeated use",
        "evidence_level": "deterministic_local",
        "commands": [[
            "python3", "-m", "pytest",
            "tests/test_golden_load_benchmarks.py",
            "tests/test_dense_utility_benchmark.py",
            "tests/test_project_store_fast_paths.py",
            "tests/test_job_queue_service.py",
            "tests/test_application_project_workflows.py",
            "-q",
        ]],
    },
]


FRONTEND_GATE: Dict[str, Any] = {
    "gate_id": "frontend_build_quality",
    "label": "Frontend lint, type safety, and production build",
    "evidence_level": "local_production_build",
    "commands": [
        ["npm", "--prefix", "apps/web", "run", "lint"],
        [
            "node",
            "apps/web/node_modules/typescript/bin/tsc",
            "--project",
            "apps/web/tsconfig.json",
            "--noEmit",
            "--pretty",
            "false",
            "--incremental",
            "false",
        ],
        ["npm", "--prefix", "apps/web", "run", "build"],
    ],
}


BROWSER_GATE: Dict[str, Any] = {
    "gate_id": "human_style_browser_workflow",
    "label": "Fresh-project browser use, every major workflow, misuse, telemetry, and responsiveness",
    "evidence_level": "local_built_browser",
    "cwd": "apps/web",
    "commands": [[
        "./node_modules/.bin/playwright",
        "test",
        "--config=playwright.config.ts",
        "tests/live/human-chaos-workflow.spec.ts",
        "tests/live/button-functionality-audit.spec.ts",
        "tests/live/apply-address-auto-site-context.spec.ts",
        "tests/live/drawn-boundary-finish.spec.ts",
        "tests/live/draw-drafting-usability-chat221b.spec.ts",
        "tests/live/generate-uses-drawn-context-chat240.spec.ts",
        "tests/live/generate-deliver-flow.spec.ts",
        "tests/live/reactive-rerun.spec.ts",
        "tests/live/projects-flow.spec.ts",
        "tests/live/preview-realism-truth-chat234.spec.ts",
        "tests/live/civil-3d-viewer.spec.ts",
        "tests/live/performance-responsiveness-chat222b.spec.ts",
        "tests/live/hostile-use-ui-chat253.spec.ts",
        "--project=chromium",
        "--workers=1",
    ]],
}


EXTERNAL_EVIDENCE_REQUIREMENTS: List[Dict[str, Any]] = [
    {
        "requirement_id": "accepted_project_survey_control",
        "status": "external_evidence_required",
        "owner": "project surveyor or licensed reviewer",
        "proof": "Rights-cleared project survey/control, datum, coordinate system, and independent registration check.",
    },
    {
        "requirement_id": "external_civil3d_or_target_cad_verification",
        "status": "external_evidence_required",
        "owner": "independent CAD reviewer",
        "proof": "Open exported DXF/LandXML in the named target tool and record preserved, limited, and lost content.",
    },
    {
        "requirement_id": "independent_engineer_benchmark_review",
        "status": "external_evidence_required",
        "owner": "qualified independent civil engineer",
        "proof": "Review calculation inputs, expected results, tolerances, assumptions, and review deliverables for named benchmark projects.",
    },
    {
        "requirement_id": "hosted_authenticated_repeat_workflow",
        "status": "external_evidence_required",
        "owner": "product operations",
        "proof": "Complete the same fresh-project workflow twice on the deployed product with real auth, storage, queues, and provider credentials.",
    },
    {
        "requirement_id": "real_gpu_visualization_provider",
        "status": "external_evidence_required",
        "owner": "visualization operations",
        "proof": "Generate and inspect a non-mock visualization artifact from the configured renderer; visual output remains separate from engineering evidence.",
    },
]


CommandExecutor = Callable[[Sequence[str], Path, Dict[str, str]], Dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_executor(command: Sequence[str], cwd: Path, env: Dict[str, str]) -> Dict[str, Any]:
    started = perf_counter()
    completed = subprocess.run(
        list(command),
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "exit_code": completed.returncode,
        "elapsed_seconds": round(perf_counter() - started, 3),
        "stdout": completed.stdout[-20_000:],
        "stderr": completed.stderr[-20_000:],
    }


def build_end_state_validation_gates(
    *,
    include_frontend: bool = True,
    include_browser: bool = True,
    hosted_url: str = "",
    include_hosted_auth: bool = False,
) -> List[Dict[str, Any]]:
    gates = deepcopy(LOCAL_GATES)
    if include_frontend:
        gates.append(deepcopy(FRONTEND_GATE))
    if include_browser:
        gates.append(deepcopy(BROWSER_GATE))
    if hosted_url:
        hosted_commands = [["npm", "run", "test:hosted:public"]]
        if include_hosted_auth:
            hosted_commands.append(["npm", "run", "test:hosted"])
        gates.append(
            {
                "gate_id": "hosted_product_proof",
                "label": "Deployed public and authenticated workflow proof",
                "evidence_level": "hosted_browser",
                "cwd": "apps/web",
                "environment": {"PLAYWRIGHT_BASE_URL": hosted_url, "PLAYWRIGHT_SKIP_WEBSERVER": "1"},
                "commands": hosted_commands,
            }
        )
    return gates


def run_end_state_capability_validation(
    *,
    include_frontend: bool = True,
    include_browser: bool = True,
    hosted_url: str = "",
    include_hosted_auth: bool = False,
    selected_gate_ids: Optional[Iterable[str]] = None,
    output_path: Optional[Path] = None,
    executor: CommandExecutor = _default_executor,
) -> Dict[str, Any]:
    selected = {str(item) for item in (selected_gate_ids or []) if str(item)}
    gates = build_end_state_validation_gates(
        include_frontend=include_frontend,
        include_browser=include_browser,
        hosted_url=hosted_url,
        include_hosted_auth=include_hosted_auth,
    )
    available_gate_ids = {str(gate["gate_id"]) for gate in gates}
    unknown_gate_ids = sorted(selected - available_gate_ids)
    if selected:
        gates = [gate for gate in gates if gate["gate_id"] in selected]
    results: List[Dict[str, Any]] = []
    if unknown_gate_ids:
        results.append(
            {
                "gate_id": "validation_configuration",
                "label": "Validation command configuration",
                "evidence_level": "configuration",
                "status": "failed",
                "command_results": [],
                "elapsed_seconds": 0.0,
                "errors": [f"Unknown validation gate: {gate_id}" for gate_id in unknown_gate_ids],
            }
        )
    for gate in gates:
        gate_cwd = ROOT / str(gate.get("cwd") or ".")
        gate_env = dict(os.environ)
        gate_env.update({str(key): str(value) for key, value in dict(gate.get("environment") or {}).items()})
        command_results = []
        for command in gate["commands"]:
            result = executor(command, gate_cwd, gate_env)
            command_results.append({"command": list(command), **result})
            if int(result.get("exit_code", 1)) != 0:
                break
        passed = len(command_results) == len(gate["commands"]) and all(
            int(result.get("exit_code", 1)) == 0 for result in command_results
        )
        results.append(
            {
                "gate_id": gate["gate_id"],
                "label": gate["label"],
                "evidence_level": gate["evidence_level"],
                "status": "passed" if passed else "failed",
                "command_results": command_results,
                "elapsed_seconds": round(sum(float(item.get("elapsed_seconds", 0.0)) for item in command_results), 3),
            }
        )

    failed_gate_ids = [result["gate_id"] for result in results if result["status"] != "passed"]
    passed_gate_ids = {result["gate_id"] for result in results if result["status"] == "passed"}
    calculation_crosschecks = build_internal_calculation_crosschecks()
    missing_internal_gate_ids = sorted(REQUIRED_INTERNAL_GATE_IDS - passed_gate_ids)
    internal_software_assurance_complete = bool(
        not failed_gate_ids
        and not missing_internal_gate_ids
        and calculation_crosschecks.get("passed") is True
    )
    report = {
        "version": END_STATE_VALIDATION_VERSION,
        "generated_at": _now_iso(),
        "status": "local_and_requested_hosted_gates_passed" if not failed_gate_ids else "validation_failed",
        "success": not failed_gate_ids,
        "gate_count": len(results),
        "passed_gate_count": len(results) - len(failed_gate_ids),
        "failed_gate_ids": failed_gate_ids,
        "gates": results,
        "internal_calculation_crosschecks": calculation_crosschecks,
        "missing_internal_gate_ids": missing_internal_gate_ids,
        "internal_software_assurance_complete": internal_software_assurance_complete,
        "external_evidence_requirements": deepcopy(EXTERNAL_EVIDENCE_REQUIREMENTS),
        "external_evidence_complete": False,
        "construction_release_allowed": False,
        "truth_label": (
            "Passing automated gates proves the named local or hosted workflows only. It does not replace accepted survey/control, "
            "independent engineering review, target-tool verification, or professional responsibility."
        ),
    }
    if output_path is not None:
        resolved_output = output_path if output_path.is_absolute() else ROOT / output_path
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        resolved_output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        report["output_path"] = str(resolved_output)
    return report


__all__ = [
    "BROWSER_GATE",
    "END_STATE_VALIDATION_VERSION",
    "EXTERNAL_EVIDENCE_REQUIREMENTS",
    "FRONTEND_GATE",
    "LOCAL_GATES",
    "build_end_state_validation_gates",
    "run_end_state_capability_validation",
]
