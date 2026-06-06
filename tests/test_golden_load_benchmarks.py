import json
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, Dict

from backend.application.golden_load_benchmarks import (
    DEFAULT_GOLDEN_LOAD_SCENARIO_IDS,
    deterministic_benchmark_projects,
    run_golden_load_benchmarks,
)


def _fake_benchmark_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    lot = dict(payload.get("lot") or {})
    site_plan = dict(payload.get("site_plan") or {})
    width = float(lot.get("w") or 0.0)
    height = float(lot.get("h") or 0.0)
    building_count = int(site_plan.get("building_count") or 1)
    parking_count = int(site_plan.get("parking_count") or 36)
    return {
        "project_name": payload.get("project_name"),
        "actions": [
            {
                "task": "rectangle",
                "layer": "SITE",
                "canonical_source_type": "site",
                "canonical_source_id": "site-1",
                "width": width,
                "height": height,
            },
            *[
                {"task": "rectangle", "layer": "BUILDING", "canonical_source_id": f"building-{index + 1}"}
                for index in range(building_count)
            ],
        ],
        "meta": {
            "lot": {"w": width, "h": height, "area_sf": width * height},
            "building_count": building_count,
            "parking_count": parking_count,
            "parking_program": {"stall_count": parking_count},
            "grading": {
                "existing_surface": {"source": "benchmark_fixture"},
                "proposed_surface": {"source": "benchmark_engine"},
                "low_points": [{"id": "LP-1"}],
                "road_crown_controls": [{"id": "CROWN-1"}],
                "earthwork": {"cut_cy": 120.0, "fill_cy": 95.0},
            },
            "drainage": {
                "low_points": [{"id": "LP-1"}],
                "basins": [{"id": "BASIN-1"}],
                "detention_routing": [{"id": "ROUTE-1"}],
            },
            "storm_pipes": {"segments": [{"id": "ST-1", "length_ft": 80.0}]},
            "sanitary": {"segments": [{"id": "SAN-1", "length_ft": 70.0}]},
            "utilities": {"segments": [{"id": "W-1", "length_ft": 60.0}], "conflict_hooks": {"utility_segments": [{"id": "W-1"}]}},
            "coordination": {
                "detected_conflicts": 2,
                "resolved_conflicts": [{"id": "X-1"}],
                "resolution_history": [{"id": "R-1"}],
            },
            "quantities": {"totals": {"lot_area_sf": width * height, "pipe_length_ft": 80.0, "estimated_parking_stalls": parking_count}},
            "alignments": [{"id": "CL-1"}],
            "profiles": [{"id": "P-1"}],
            "cross_sections": [{"id": "XS-1"}],
            "sheet_registry": [{"id": "C-101"}],
            "existing_conditions": {"protected_zones": [{"id": "PZ-1"}], "floodplain": {"id": "AE"}, "wetlands": {"id": "NWI-1"}},
            "floodplain": {"id": "AE"},
            "wetlands": {"id": "NWI-1"},
            "protected_zones": [{"id": "PZ-1"}],
            "civil_design_readiness": {
                "status": "needs_engineering_review",
                "success": True,
                "production_ready": False,
                "critical_blockers": [],
                "production_blockers": [{"area": "existing_conditions", "field": "survey_surface"}],
                "missing_requirements": [],
            },
            "engine_readiness": {
                "production_ready": False,
                "blocked_engine_ids": [],
                "production_blocked_engine_ids": ["gis_existing_conditions"],
            },
            "construction_readiness": {
                "ready": False,
                "status": "not_construction_ready",
                "blockers": [{"area": "existing_conditions", "field": "survey"}],
            },
            "construction_package_manifest": {
                "release_allowed": False,
                "construction_ready": False,
                "blockers": [{"area": "existing_conditions", "field": "survey"}],
            },
        },
    }


def _slow_benchmark_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    time.sleep(2.0)
    return _fake_benchmark_plan(payload)


def _failing_benchmark_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    raise RuntimeError("controlled benchmark failure")


class GoldenLoadBenchmarkTests(unittest.TestCase):
    def test_deterministic_benchmark_projects_are_stable(self) -> None:
        first = deterministic_benchmark_projects(DEFAULT_GOLDEN_LOAD_SCENARIO_IDS)
        second = deterministic_benchmark_projects(DEFAULT_GOLDEN_LOAD_SCENARIO_IDS)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 6)
        self.assertEqual([item["scenario_id"] for item in first], list(DEFAULT_GOLDEN_LOAD_SCENARIO_IDS))
        self.assertTrue(all(str(item["project_id"]).startswith("golden-load-") for item in first))
        self.assertTrue(all(item["payload_sha256"] for item in first))

    def test_golden_load_benchmark_report_passes_and_writes_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "golden_load_report.json"
            report = run_golden_load_benchmarks(
                iterations=2,
                build_plan_fn=_fake_benchmark_plan,
                output_path=output,
            )

            self.assertTrue(report["success"], report)
            self.assertEqual(report["scenario_count"], 6)
            self.assertEqual(report["iteration_count"], 2)
            self.assertEqual(report["total_run_count"], 12)
            self.assertEqual(report["blocker_count"], 0)
            self.assertFalse(report["construction_ready"])
            self.assertFalse(report["construction_release_allowed"])
            self.assertTrue(report["construction_release_blocked"])
            self.assertIn("site_boundary", report["systems_completed"])
            self.assertIn("unknown", {report["export_readiness"]["status"], report["standards_readiness"]["status"]})
            self.assertTrue(output.exists())
            self.assertTrue(all(summary["runtime_ms"]["max"] >= 0.0 for summary in report["scenario_summaries"]))
            self.assertTrue(all(summary["memory_mb"]["max_peak_rss_mb"] >= 0.0 for summary in report["scenario_summaries"]))

    def test_golden_load_benchmark_reports_threshold_blockers(self) -> None:
        report = run_golden_load_benchmarks(
            scenario_ids=["small_commercial_pad"],
            iterations=1,
            build_plan_fn=_fake_benchmark_plan,
            load_threshold_overrides={"max_rss_mb": 0.001},
        )

        self.assertFalse(report["success"])
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["blocker_count"], 1)
        self.assertIn("rss_mb", report["scenario_summaries"][0]["failed_load_thresholds"])
        self.assertIn("golden_load_thresholds_failed", report["runs"][0]["hard_failures"])

    def test_golden_load_benchmark_times_out_instead_of_hanging(self) -> None:
        start = time.perf_counter()
        report = run_golden_load_benchmarks(
            scenario_ids=["small_commercial_pad"],
            iterations=1,
            build_plan_fn=_slow_benchmark_plan,
            scenario_timeout_seconds=0.05,
        )
        elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 1.5)
        self.assertFalse(report["success"])
        self.assertEqual(report["runs"][0]["benchmark_status"], "timeout_blocked")
        self.assertIn("golden_scenario_timeout", report["runs"][0]["hard_failures"])
        self.assertEqual(report["blockers"][0]["field"], "small_commercial_pad")
        self.assertIn("scenario_timeout", report["runs"][0]["missing_inputs"][0]["field"])
        self.assertGreaterEqual(report["scenario_summaries"][0]["runtime_ms"]["max"], 0.0)
        self.assertGreaterEqual(report["scenario_summaries"][0]["memory_mb"]["max_peak_rss_mb"], 0.0)
        self.assertTrue(report["construction_release_blocked"])

    def test_golden_load_benchmark_reports_exception_with_runtime_and_memory(self) -> None:
        report = run_golden_load_benchmarks(
            scenario_ids=["small_commercial_pad"],
            iterations=1,
            build_plan_fn=_failing_benchmark_plan,
        )

        self.assertFalse(report["success"])
        self.assertEqual(report["runs"][0]["benchmark_status"], "execution_failed")
        self.assertIn("golden_scenario_execution_failed", report["runs"][0]["hard_failures"])
        self.assertIn("controlled benchmark failure", report["runs"][0]["error"])
        self.assertGreaterEqual(report["scenario_summaries"][0]["runtime_ms"]["max"], 0.0)
        self.assertGreaterEqual(report["scenario_summaries"][0]["memory_mb"]["max_rss_mb"], 0.0)

    def test_heavy_real_file_scenario_can_be_skipped_with_clear_blocker(self) -> None:
        report = run_golden_load_benchmarks(
            scenario_ids=["roadway_corridor"],
            iterations=1,
            build_plan_fn=_fake_benchmark_plan,
            skip_heavy_real_file_scenarios=True,
        )

        self.assertFalse(report["success"])
        self.assertEqual(report["runs"][0]["benchmark_status"], "heavy_initialization_skipped")
        self.assertIn("heavy_golden_initialization_skipped", report["runs"][0]["hard_failures"])
        self.assertIn("heavy_golden_initialization_skipped", report["runs"][0]["missing_inputs"][0]["field"])

    def test_engine_depth_audit_report_reference_can_be_attached_from_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "engine_depth.json"
            path.write_text(
                json.dumps(
                    {
                        "version": "engine_depth_audit_report_v1",
                        "status": "failed",
                        "success": False,
                        "engine_count": 3,
                        "scenario_count": 1,
                        "blocker_count": 2,
                        "failed_deterministic_check_count": 2,
                    }
                ),
                encoding="utf-8",
            )
            report = run_golden_load_benchmarks(
                scenario_ids=["small_commercial_pad"],
                iterations=1,
                build_plan_fn=_fake_benchmark_plan,
                engine_depth_audit_report_path=path,
            )

        reference = report["engine_depth_audit_reference"]
        self.assertTrue(reference["attached"])
        self.assertTrue(reference["valid"])
        self.assertEqual(reference["version"], "engine_depth_audit_report_v1")
        self.assertEqual(reference["blocker_count"], 2)


if __name__ == "__main__":
    unittest.main()
