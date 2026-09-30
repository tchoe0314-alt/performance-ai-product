from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from backend.planning.golden_runner import run_golden_scenario


COMMERCIAL_SITE_BENCHMARK_VERSION = "civora_commercial_site_benchmark_v1"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC_PATH = (
    ROOT / "backend" / "fixtures" / "golden" / "small_commercial_pad" / "benchmark-spec.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _comparison_passes(expected: Dict[str, Any], observed: Any) -> bool:
    if "equals" in expected:
        return observed == expected.get("equals")
    if observed is None:
        return False
    value = float(observed)
    if "expected" in expected:
        target = float(expected["expected"])
        tolerance = max(0.0, float(expected.get("tolerance") or 0.0))
        if abs(value - target) > tolerance:
            return False
    if "minimum" in expected and value < float(expected["minimum"]):
        return False
    if "maximum" in expected and value > float(expected["maximum"]):
        return False
    return True


def run_commercial_site_benchmark(
    *,
    output_path: Optional[Path] = None,
    spec_path: Path = DEFAULT_SPEC_PATH,
    run_scenario_fn: Callable[..., Dict[str, Any]] = run_golden_scenario,
) -> Dict[str, Any]:
    started = time.perf_counter()
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    scenario_id = str(spec.get("scenario_id") or "")
    scenario = run_scenario_fn(scenario_id)
    observed_by_metric = {
        str(item.get("metric") or ""): item.get("value")
        for item in list(scenario.get("benchmark_expectation_results") or [])
    }

    comparisons = []
    for expected in list(spec.get("expected_outcomes") or []):
        metric = str(expected.get("metric") or "")
        observed = observed_by_metric.get(metric)
        comparisons.append(
            {
                "metric": metric,
                "expected": expected.get("expected"),
                "minimum": expected.get("minimum"),
                "maximum": expected.get("maximum"),
                "tolerance": expected.get("tolerance"),
                "tolerance_type": expected.get("tolerance_type"),
                "units": expected.get("units"),
                "method": expected.get("method"),
                "observed": observed,
                "passed": _comparison_passes(expected, observed),
            }
        )

    input_manifest = []
    input_blockers = []
    for record in list(spec.get("inputs") or []):
        relative_path = str(record.get("path") or "")
        path = ROOT / relative_path
        exists = path.is_file()
        if not exists:
            input_blockers.append(f"missing_input:{relative_path}")
        input_manifest.append(
            {
                **record,
                "exists": exists,
                "size_bytes": path.stat().st_size if exists else 0,
                "sha256": _sha256(path) if exists else "",
            }
        )

    failed_comparisons = [item["metric"] for item in comparisons if not item["passed"]]
    automated_passed = bool(scenario.get("success")) and not input_blockers and not failed_comparisons
    independent_review = dict(spec.get("independent_review") or {})
    independently_reviewed = independent_review.get("status") == "accepted"
    blockers = list(input_blockers)
    if not scenario.get("success"):
        blockers.append("golden_scenario_failed")
    blockers.extend(f"comparison_failed:{metric}" for metric in failed_comparisons)
    if not independently_reviewed:
        blockers.append("independent_engineer_review_pending")

    report = {
        "version": COMMERCIAL_SITE_BENCHMARK_VERSION,
        "benchmark_id": spec.get("benchmark_id"),
        "benchmark_version": spec.get("benchmark_version"),
        "name": spec.get("name"),
        "software_revision": _revision(),
        "data_classification": spec.get("data_classification"),
        "intended_use": spec.get("intended_use"),
        "prohibited_claims": list(spec.get("prohibited_claims") or []),
        "automated_status": "passed" if automated_passed else "failed",
        "automated_passed": automated_passed,
        "independent_review_status": independent_review.get("status", "pending"),
        "independently_reviewed": independently_reviewed,
        "pilot_validation_status": "accepted" if automated_passed and independently_reviewed else "pending_human_review",
        "input_manifest": input_manifest,
        "comparisons": comparisons,
        "failed_comparisons": failed_comparisons,
        "scenario_summary": {
            "success": bool(scenario.get("success")),
            "benchmark_status": scenario.get("benchmark_status"),
            "real_file_fixture": bool(scenario.get("real_file_fixture")),
            "hard_failures": list(scenario.get("hard_failures") or []),
            "readiness_summary": dict(scenario.get("readiness_summary") or {}),
        },
        "independent_review": independent_review,
        "blockers": blockers,
        "construction_ready": False,
        "construction_release_allowed": False,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "truth_label": (
            "This internal benchmark records deterministic fixture inputs and automated comparisons. "
            "It is not a real customer project or independent engineering validation until the named human-review evidence is completed."
        ),
    }
    if output_path is not None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


__all__ = ["COMMERCIAL_SITE_BENCHMARK_VERSION", "run_commercial_site_benchmark"]
