from __future__ import annotations

import json
from pathlib import Path

from backend.application.commercial_site_benchmark import run_commercial_site_benchmark


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
