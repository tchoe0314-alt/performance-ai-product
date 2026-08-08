from __future__ import annotations

from pathlib import Path

from backend.application.rc1_engineering_validation import run_rc1_engineering_validation


def _scenario(index: int, *, comparison_passed: bool = True) -> dict:
    return {
        "scenario_id": f"scenario_{index}",
        "success": True,
        "benchmark_status": "passed_with_expected_blockers",
        "missing_canonical_signals": [],
        "failed_benchmark_expectations": [],
        "failed_load_thresholds": [],
        "benchmark_expectation_results": [
            {
                "metric": "pipe_length_ft",
                "expected": 100.0,
                "actual": 100.0 if comparison_passed else 125.0,
                "tolerance": 0.01,
                "passed": comparison_passed,
            }
        ],
    }


def _passing_suite() -> dict:
    return {
        "success": True,
        "status": "passed_with_expected_blockers",
        "truth_label": "fixture regression only",
        "scenario_count": 10,
        "real_file_fixture_count": 8,
        "real_file_fixture_ids": [f"scenario_{index}" for index in range(8)],
        "results": [_scenario(index) for index in range(10)],
    }


def test_rc1_engineering_validation_records_real_comparisons_without_claiming_human_approval(tmp_path: Path) -> None:
    output_path = tmp_path / "engineering-validation.json"

    report = run_rc1_engineering_validation(output_path=output_path, run_suite_fn=_passing_suite)

    assert report["success"] is True
    assert report["status"] == "passed"
    assert report["scenario_count"] == 10
    assert report["real_file_fixture_count"] == 8
    assert report["automated_expected_actual_comparison_count"] == 10
    assert report["failed_comparison_count"] == 0
    assert report["independent_engineer_comparison"]["status"] == "pending_human_uat"
    assert report["construction_ready"] is False
    assert report["construction_release_allowed"] is False
    assert output_path.is_file()


def test_rc1_engineering_validation_fails_when_expected_actual_comparison_fails() -> None:
    suite = _passing_suite()
    suite["results"][4] = _scenario(4, comparison_passed=False)

    report = run_rc1_engineering_validation(run_suite_fn=lambda: suite)

    assert report["success"] is False
    assert report["failed_comparison_count"] == 1
    assert "engineering_output_comparison_failures" in {item["code"] for item in report["blockers"]}


def test_rc1_engineering_validation_fails_when_real_file_coverage_is_too_small() -> None:
    suite = _passing_suite()
    suite["real_file_fixture_count"] = 7

    report = run_rc1_engineering_validation(run_suite_fn=lambda: suite)

    assert report["success"] is False
    assert "real_file_coverage_incomplete" in {item["code"] for item in report["blockers"]}
