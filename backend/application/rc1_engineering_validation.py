from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional
import hashlib
import json
import time

from backend.planning.golden_runner import run_golden_scenarios


RC1_ENGINEERING_VALIDATION_VERSION = "civora_rc1_engineering_validation_v1"
ROOT = Path(__file__).resolve().parents[2]
GOLDEN_FIXTURE_ROOT = ROOT / "backend" / "fixtures" / "golden"
REAL_INPUT_FIXTURE_ROOT = ROOT / "backend" / "fixtures" / "real_input_benchmarks"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fixture_manifest() -> list[Dict[str, Any]]:
    files = sorted(
        path
        for root in (GOLDEN_FIXTURE_ROOT, REAL_INPUT_FIXTURE_ROOT)
        if root.is_dir()
        for path in root.rglob("*")
        if path.is_file()
    )
    return [
        {
            "path": str(path.relative_to(ROOT)),
            "format": path.suffix.lower().lstrip(".") or "text",
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in files
    ]


def run_rc1_engineering_validation(
    *,
    output_path: Optional[Path] = None,
    run_suite_fn: Callable[[], Dict[str, Any]] = run_golden_scenarios,
) -> Dict[str, Any]:
    started = time.perf_counter()
    suite = run_suite_fn()
    results = list(suite.get("results") or [])
    comparisons = []
    for scenario in results:
        scenario_id = str(scenario.get("scenario_id") or "")
        for item in list(scenario.get("benchmark_expectation_results") or []):
            record = dict(item or {})
            comparisons.append(
                {
                    "scenario_id": scenario_id,
                    "metric": record.get("metric") or record.get("field") or record.get("name"),
                    "expected": record.get("expected"),
                    "actual": record.get("actual") if "actual" in record else record.get("value"),
                    "tolerance": record.get("tolerance"),
                    "passed": bool(record.get("passed")),
                }
            )
    failed_comparisons = [item for item in comparisons if not item["passed"]]
    failed_scenarios = [
        {
            "scenario_id": item.get("scenario_id"),
            "benchmark_status": item.get("benchmark_status"),
            "hard_failures": item.get("hard_failures") or [],
            "failed_expectations": item.get("failed_benchmark_expectations") or [],
        }
        for item in results
        if not bool(item.get("success"))
        or item.get("missing_canonical_signals")
        or item.get("failed_benchmark_expectations")
        or item.get("failed_load_thresholds")
    ]
    fixture_manifest = _fixture_manifest()
    formats = sorted({item["format"] for item in fixture_manifest})
    expected_scenario_count = 10
    expected_real_file_count = 8
    success = bool(
        suite.get("success")
        and int(suite.get("scenario_count") or 0) >= expected_scenario_count
        and int(suite.get("real_file_fixture_count") or 0) >= expected_real_file_count
        and not failed_scenarios
        and not failed_comparisons
    )
    blockers = []
    if int(suite.get("scenario_count") or 0) < expected_scenario_count:
        blockers.append({"code": "scenario_coverage_incomplete", "message": "Fewer than ten RC1 engineering scenarios ran."})
    if int(suite.get("real_file_fixture_count") or 0) < expected_real_file_count:
        blockers.append({"code": "real_file_coverage_incomplete", "message": "Fewer than eight real-file fixture scenarios ran."})
    if failed_scenarios:
        blockers.append({"code": "engineering_scenario_failures", "message": "One or more engineering scenarios failed their expected behavior."})
    if failed_comparisons:
        blockers.append({"code": "engineering_output_comparison_failures", "message": "One or more deterministic expected-versus-actual comparisons failed."})
    report = {
        "version": RC1_ENGINEERING_VALIDATION_VERSION,
        "success": success,
        "status": "passed" if success else "failed",
        "scenario_count": int(suite.get("scenario_count") or 0),
        "real_file_fixture_count": int(suite.get("real_file_fixture_count") or 0),
        "real_file_fixture_ids": list(suite.get("real_file_fixture_ids") or []),
        "fixture_file_count": len(fixture_manifest),
        "fixture_formats": formats,
        "fixture_manifest": fixture_manifest,
        "automated_expected_actual_comparison_count": len(comparisons),
        "automated_expected_actual_comparisons": comparisons,
        "failed_comparison_count": len(failed_comparisons),
        "failed_scenarios": failed_scenarios,
        "blockers": blockers,
        "independent_engineer_comparison": {
            "status": "pending_human_uat",
            "required": True,
            "evidence_url": "",
            "truth_label": "Deterministic fixture comparisons are regression evidence. They are not independent engineering validation.",
        },
        "construction_ready": False,
        "construction_release_allowed": False,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "suite_summary": {
            "success": bool(suite.get("success")),
            "status": suite.get("status"),
            "truth_label": suite.get("truth_label"),
        },
        "truth_label": "RC1 engineering validation proves deterministic scenarios, real-file fixture ingestion, expected blockers, and expected-versus-actual regression checks. Independent engineer calculations and target-tool acceptance remain separate human evidence.",
    }
    if output_path is not None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


__all__ = ["RC1_ENGINEERING_VALIDATION_VERSION", "run_rc1_engineering_validation"]
