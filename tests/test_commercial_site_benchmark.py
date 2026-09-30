from __future__ import annotations

import json
from pathlib import Path

from backend.application.commercial_site_benchmark import (
    build_independent_review_template,
    run_commercial_site_benchmark,
)


def _scenario(*, lot_area: float = 35200.0) -> dict:
    values = {
        "lot_area_sf": lot_area,
        "storm_segment_count": 1,
        "sanitary_segment_count": 1,
        "utility_segment_count": 1,
        "pipe_length_ft": 50.0,
        "civil_production_ready": False,
    }
    return {
        "success": True,
        "benchmark_status": "passed_with_expected_blockers",
        "real_file_fixture": True,
        "hard_failures": [],
        "readiness_summary": {"civil_production_ready": False},
        "benchmark_expectation_results": [
            {"metric": metric, "value": value, "passed": True}
            for metric, value in values.items()
        ],
    }


def test_commercial_site_benchmark_records_hashes_and_keeps_human_review_pending(tmp_path: Path) -> None:
    output_path = tmp_path / "benchmark.json"

    report = run_commercial_site_benchmark(
        output_path=output_path,
        run_scenario_fn=lambda _scenario_id: _scenario(),
    )

    assert report["automated_passed"] is True
    assert report["automated_status"] == "passed"
    assert report["pilot_validation_status"] == "pending_human_review"
    assert report["independently_reviewed"] is False
    assert "independent_engineer_review_pending" in report["blockers"]
    assert all(item["exists"] and len(item["sha256"]) == 64 for item in report["input_manifest"])
    assert report["construction_ready"] is False
    assert report["construction_release_allowed"] is False
    assert json.loads(output_path.read_text(encoding="utf-8"))["benchmark_id"] == "commercial-pad-001"


def test_commercial_site_benchmark_fails_closed_on_tolerance_miss() -> None:
    report = run_commercial_site_benchmark(run_scenario_fn=lambda _scenario_id: _scenario(lot_area=35199.0))

    assert report["automated_passed"] is False
    assert "lot_area_sf" in report["failed_comparisons"]
    assert "comparison_failed:lot_area_sf" in report["blockers"]


def _review_evidence(report: dict) -> dict:
    return {
        "benchmark_id": report["benchmark_id"],
        "benchmark_version": report["benchmark_version"],
        "software_revision": report["software_revision"],
        "review_date": "2026-09-30",
        "reviewer": {
            "name": "Independent Reviewer",
            "organization": "Review Engineering LLC",
            "qualification": "Licensed civil engineer",
        },
        "input_manifest": [
            {"path": item["path"], "sha256": item["sha256"]} for item in report["input_manifest"]
        ],
        "attestation": {
            "independent_from_benchmark_preparation": True,
            "expected_values_prepared_before_civora_review": True,
            "no_construction_release_claim": True,
        },
        "calculation_review": [
            {
                "metric": item["metric"],
                "passed": True,
                "independent_method": "Independent calculation workbook",
                "reviewer_notes": "Compared within the recorded tolerance.",
            }
            for item in report["comparisons"]
        ],
        "reactive_change_review": {
            "object_type": "building",
            "change_recorded": True,
            "affected_systems_marked_stale": True,
            "unaffected_systems_remained_current": True,
            "impact_explanation_matched": True,
            "selective_rerun_completed": True,
            "quantities_updated": True,
            "deliverables_updated": True,
            "stale_exports_blocked": True,
            "save_reopen_preserved_change": True,
            "version_comparison_preserved_change": True,
            "reviewer_notes": "Building move and selective regeneration behaved as recorded.",
        },
        "open_discrepancies": [],
        "disposition": "accepted_for_controlled_pilot_validation",
    }


def test_commercial_site_benchmark_accepts_complete_revision_bound_review(tmp_path: Path) -> None:
    initial = run_commercial_site_benchmark(run_scenario_fn=lambda _scenario_id: _scenario())
    evidence_path = tmp_path / "review.json"
    evidence_path.write_text(json.dumps(_review_evidence(initial)), encoding="utf-8")

    report = run_commercial_site_benchmark(
        review_evidence_path=evidence_path,
        run_scenario_fn=lambda _scenario_id: _scenario(),
    )

    assert report["independently_reviewed"] is True
    assert report["independent_review_status"] == "accepted"
    assert report["pilot_validation_status"] == "accepted"
    assert "independent_engineer_review_pending" not in report["blockers"]
    assert len(report["independent_review"]["evidence_sha256"]) == 64
    assert report["construction_ready"] is False


def test_commercial_site_benchmark_rejects_review_for_another_revision(tmp_path: Path) -> None:
    initial = run_commercial_site_benchmark(run_scenario_fn=lambda _scenario_id: _scenario())
    evidence = _review_evidence(initial)
    evidence["software_revision"] = "0" * 40
    evidence_path = tmp_path / "review.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    report = run_commercial_site_benchmark(
        review_evidence_path=evidence_path,
        run_scenario_fn=lambda _scenario_id: _scenario(),
    )

    assert report["independently_reviewed"] is False
    assert report["independent_review_status"] == "rejected"
    assert "independent_review:software_revision_mismatch" in report["blockers"]


def test_commercial_site_benchmark_rejects_incomplete_reactive_review(tmp_path: Path) -> None:
    initial = run_commercial_site_benchmark(run_scenario_fn=lambda _scenario_id: _scenario())
    evidence = _review_evidence(initial)
    evidence["reactive_change_review"]["stale_exports_blocked"] = False
    evidence_path = tmp_path / "review.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    report = run_commercial_site_benchmark(
        review_evidence_path=evidence_path,
        run_scenario_fn=lambda _scenario_id: _scenario(),
    )

    assert report["independently_reviewed"] is False
    assert "independent_review:reactive_check_missing_or_failed:stale_exports_blocked" in report["blockers"]


def test_commercial_site_benchmark_rejects_open_review_discrepancy(tmp_path: Path) -> None:
    initial = run_commercial_site_benchmark(run_scenario_fn=lambda _scenario_id: _scenario())
    evidence = _review_evidence(initial)
    evidence["open_discrepancies"] = [{"id": "DISC-1", "severity": "critical"}]
    evidence_path = tmp_path / "review.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    report = run_commercial_site_benchmark(
        review_evidence_path=evidence_path,
        run_scenario_fn=lambda _scenario_id: _scenario(),
    )

    assert report["independently_reviewed"] is False
    assert "independent_review:open_discrepancies_present" in report["blockers"]


def test_review_template_is_revision_bound_and_fail_closed() -> None:
    report = run_commercial_site_benchmark(run_scenario_fn=lambda _scenario_id: _scenario())

    template = build_independent_review_template(report)

    assert template["software_revision"] == report["software_revision"]
    assert template["input_manifest"] == [
        {"path": item["path"], "sha256": item["sha256"]} for item in report["input_manifest"]
    ]
    assert all(row["passed"] is False for row in template["calculation_review"])
    assert all(
        value is False
        for key, value in template["reactive_change_review"].items()
        if key not in {"object_type", "reviewer_notes"}
    )
    assert template["disposition"] == "pending"
