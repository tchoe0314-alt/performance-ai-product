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
REQUIRED_REACTIVE_CHECKS = (
    "change_recorded",
    "affected_systems_marked_stale",
    "unaffected_systems_remained_current",
    "impact_explanation_matched",
    "selective_rerun_completed",
    "quantities_updated",
    "deliverables_updated",
    "stale_exports_blocked",
    "save_reopen_preserved_change",
    "version_comparison_preserved_change",
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


def _assess_independent_review(
    evidence: Optional[Dict[str, Any]],
    *,
    benchmark_id: str,
    benchmark_version: str,
    software_revision: str,
    required_metrics: set[str],
    input_manifest: list[Dict[str, Any]],
) -> Dict[str, Any]:
    """Validate attributable review evidence without treating its claims as construction approval."""
    if not evidence:
        return {"status": "pending", "accepted": False, "blockers": ["review_evidence_missing"]}

    blockers = []
    reviewer = dict(evidence.get("reviewer") or {})
    attestation = dict(evidence.get("attestation") or {})
    if not str(reviewer.get("name") or "").strip():
        blockers.append("reviewer_name_missing")
    if not str(reviewer.get("organization") or "").strip():
        blockers.append("reviewer_organization_missing")
    if not str(reviewer.get("qualification") or "").strip():
        blockers.append("reviewer_qualification_missing")
    if not str(evidence.get("review_date") or "").strip():
        blockers.append("review_date_missing")
    if evidence.get("benchmark_id") != benchmark_id:
        blockers.append("benchmark_id_mismatch")
    if evidence.get("benchmark_version") != benchmark_version:
        blockers.append("benchmark_version_mismatch")
    if evidence.get("software_revision") != software_revision:
        blockers.append("software_revision_mismatch")
    if attestation.get("independent_from_benchmark_preparation") is not True:
        blockers.append("reviewer_independence_not_attested")
    if attestation.get("expected_values_prepared_before_civora_review") is not True:
        blockers.append("independent_method_not_attested")
    if attestation.get("no_construction_release_claim") is not True:
        blockers.append("scope_limitation_not_attested")

    expected_hashes = {
        str(item.get("path") or ""): str(item.get("sha256") or "") for item in input_manifest
    }
    evidence_hashes = {
        str(item.get("path") or ""): str(item.get("sha256") or "")
        for item in list(evidence.get("input_manifest") or [])
    }
    if evidence_hashes != expected_hashes:
        blockers.append("input_manifest_mismatch")

    calculation_rows = list(evidence.get("calculation_review") or [])
    reviewed_metrics = {
        str(row.get("metric") or "")
        for row in calculation_rows
        if row.get("passed") is True
        and str(row.get("independent_method") or "").strip()
        and str(row.get("reviewer_notes") or "").strip()
    }
    missing_metrics = sorted(required_metrics - reviewed_metrics)
    if missing_metrics:
        blockers.extend(f"calculation_review_missing_or_failed:{metric}" for metric in missing_metrics)

    reactive_review = dict(evidence.get("reactive_change_review") or {})
    if reactive_review.get("object_type") != "building":
        blockers.append("building_move_review_missing")
    for check in REQUIRED_REACTIVE_CHECKS:
        if reactive_review.get(check) is not True:
            blockers.append(f"reactive_check_missing_or_failed:{check}")
    if not str(reactive_review.get("reviewer_notes") or "").strip():
        blockers.append("reactive_review_notes_missing")

    if list(evidence.get("open_discrepancies") or []):
        blockers.append("open_discrepancies_present")

    if evidence.get("disposition") != "accepted_for_controlled_pilot_validation":
        blockers.append("review_disposition_not_accepted")

    accepted = not blockers
    return {
        "status": "accepted" if accepted else "rejected",
        "accepted": accepted,
        "blockers": blockers,
        "reviewer": reviewer,
        "review_date": evidence.get("review_date"),
        "evidence_sha256": evidence.get("_evidence_sha256", ""),
        "disposition": evidence.get("disposition"),
    }


def build_independent_review_template(report: Dict[str, Any]) -> Dict[str, Any]:
    """Create a reviewer worksheet already bound to the report's revision and inputs."""
    return {
        "benchmark_id": report.get("benchmark_id"),
        "benchmark_version": report.get("benchmark_version"),
        "software_revision": report.get("software_revision"),
        "review_date": "",
        "reviewer": {"name": "", "organization": "", "qualification": ""},
        "input_manifest": [
            {"path": item.get("path"), "sha256": item.get("sha256")}
            for item in list(report.get("input_manifest") or [])
        ],
        "attestation": {
            "independent_from_benchmark_preparation": False,
            "expected_values_prepared_before_civora_review": False,
            "no_construction_release_claim": False,
        },
        "calculation_review": [
            {
                "metric": item.get("metric"),
                "expected": item.get("expected"),
                "minimum": item.get("minimum"),
                "maximum": item.get("maximum"),
                "tolerance": item.get("tolerance"),
                "tolerance_type": item.get("tolerance_type"),
                "units": item.get("units"),
                "civora_observed": item.get("observed"),
                "independent_method": "",
                "independent_expected": None,
                "difference": None,
                "passed": False,
                "reviewer_notes": "",
            }
            for item in list(report.get("comparisons") or [])
        ],
        "reactive_change_review": {
            "object_type": "building",
            **{check: False for check in REQUIRED_REACTIVE_CHECKS},
            "reviewer_notes": "",
        },
        "open_discrepancies": [],
        "limitations": [],
        "disposition": "pending",
    }


def run_commercial_site_benchmark(
    *,
    output_path: Optional[Path] = None,
    spec_path: Path = DEFAULT_SPEC_PATH,
    review_evidence_path: Optional[Path] = None,
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
    software_revision = _revision()
    review_evidence = None
    if review_evidence_path is not None:
        review_path = Path(review_evidence_path)
        if review_path.is_file():
            review_evidence = json.loads(review_path.read_text(encoding="utf-8"))
            review_evidence["_evidence_sha256"] = _sha256(review_path)
    independent_review = _assess_independent_review(
        review_evidence,
        benchmark_id=str(spec.get("benchmark_id") or ""),
        benchmark_version=str(spec.get("benchmark_version") or ""),
        software_revision=software_revision,
        required_metrics={str(item.get("metric") or "") for item in list(spec.get("expected_outcomes") or [])},
        input_manifest=input_manifest,
    )
    independently_reviewed = independent_review["accepted"] is True
    blockers = list(input_blockers)
    if not scenario.get("success"):
        blockers.append("golden_scenario_failed")
    blockers.extend(f"comparison_failed:{metric}" for metric in failed_comparisons)
    if not independently_reviewed:
        blockers.append("independent_engineer_review_pending")
        blockers.extend(f"independent_review:{item}" for item in independent_review["blockers"])

    report = {
        "version": COMMERCIAL_SITE_BENCHMARK_VERSION,
        "benchmark_id": spec.get("benchmark_id"),
        "benchmark_version": spec.get("benchmark_version"),
        "name": spec.get("name"),
        "software_revision": software_revision,
        "data_classification": spec.get("data_classification"),
        "intended_use": spec.get("intended_use"),
        "prohibited_claims": list(spec.get("prohibited_claims") or []),
        "automated_status": "passed" if automated_passed else "failed",
        "automated_passed": automated_passed,
        "independent_review_status": independent_review["status"],
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


__all__ = [
    "COMMERCIAL_SITE_BENCHMARK_VERSION",
    "build_independent_review_template",
    "run_commercial_site_benchmark",
]
