from __future__ import annotations

import json
import math
import resource
import time
import unittest
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

from backend.planning.canonical_export import canonical_export_actions
from backend.planning.export_package_report import build_export_package_report_v1
from backend.planning.export_validation import (
    drainage_export_validation,
    storm_export_validation,
    utility_export_validation,
)
from core.geometry_core import ProjectModel
from engines.quantity_engine import compute_plan_quantities
from engines.surface_engine import SurfaceEngine, SurveyPoint


REPORT_PATH = Path("reports/benchmarks/chat145_dense_utility_benchmark.json")


def _polyline_length(points: List[List[float]]) -> float:
    total = 0.0
    for index in range(1, len(points)):
        x1, y1 = points[index - 1]
        x2, y2 = points[index]
        total += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    return round(total, 3)


def _ids(records: Iterable[Dict[str, Any]]) -> Set[str]:
    return {str(item.get("id") or item.get("name")) for item in records if item.get("id") or item.get("name")}


def _source_ids(actions: Iterable[Dict[str, Any]], source_type: str) -> Set[str]:
    return {
        str(action.get("canonical_source_id"))
        for action in actions
        if action.get("canonical_source_type") == source_type and action.get("canonical_source_id")
    }


def _rss_to_mb(value: int) -> float:
    # macOS reports ru_maxrss in bytes; Linux reports it in kilobytes.
    divisor = 1024.0 * 1024.0 if value > 10_000_000 else 1024.0
    return round(float(value) / divisor, 3)


def _make_segment(prefix: str, index: int, y: float, *, layer_offset: float = 0.0) -> Dict[str, Any]:
    start_x = 20.0 + (index % 12) * 14.0
    end_x = start_x + 8.0 + (index % 3) * 2.0
    points = [[start_x, y + layer_offset], [end_x, y + layer_offset + (index % 4) * 0.75]]
    return {
        "id": f"{prefix}-{index:03d}",
        "name": f"{prefix.upper()}-{index:03d}",
        "route_points": points,
        "path": points,
        "length_ft": _polyline_length(points),
        "diameter_in": 12.0 if prefix == "storm" else 8.0,
        "slope_ft_ft": 0.01,
        "start_invert_ft": 94.0 - index * 0.08,
        "end_invert_ft": 93.9 - index * 0.08,
        "cover_start_ft": 4.0,
        "cover_end_ft": 4.1,
        "flow_cfs": 1.0 + index * 0.01,
        "capacity_cfs": 3.0 + index * 0.01,
        "system_type": "water" if prefix == "water" else prefix,
        "segment_role": "main" if index % 3 else "lateral",
    }


def _dense_project(storm_count: int = 1000, sanitary_count: int = 800, water_count: int = 1000) -> Dict[str, Any]:
    project = ProjectModel(name="Chat 50 Dense Utility Benchmark")
    storm_segments = [_make_segment("storm", index, 120.0) for index in range(1, storm_count + 1)]
    sanitary_segments = [_make_segment("san", index, 90.0, layer_offset=1.25) for index in range(1, sanitary_count + 1)]
    water_segments = [_make_segment("water", index, 60.0, layer_offset=2.5) for index in range(1, water_count + 1)]
    inlets = [
        {
            "id": f"inlet-{index:03d}",
            "name": f"CI-{index:03d}",
            "structure_type": "inlet",
            "x": 18.0 + (index % 12) * 14.0,
            "y": 116.0 + (index // 12) * 8.0,
            "z": 100.0,
            "estimated_flow_cfs": 1.2,
        }
        for index in range(1, storm_count + 1)
    ]
    manholes = [
        {
            "id": f"smh-{index:03d}",
            "name": f"SMH-{index:03d}",
            "x": 16.0 + (index % 10) * 15.0,
            "y": 86.0 + (index // 10) * 7.0,
            "rim_elev_ft": 101.0,
        }
        for index in range(1, sanitary_count + 1)
    ]
    hydrants = [
        {"id": f"hydrant-{index:03d}", "name": f"FH-{index:03d}", "x": 12.0 + index * 6.0, "y": 52.0}
        for index in range(1, 9)
    ]
    basin = {
        "id": "basin-primary-001",
        "name": "PRIMARY DETENTION",
        "engineering_role": "primary_detention",
        "canonical_type": "detention_basin",
        "exportable": True,
        "centroid_xy": [180.0, 155.0],
        "boundary_points": [[160.0, 140.0], [205.0, 140.0], [205.0, 178.0], [160.0, 178.0]],
        "bottom_points": [[168.0, 148.0], [197.0, 148.0], [197.0, 170.0], [168.0, 170.0]],
        "top_of_bank_area_sf": 1710.0,
        "area_sf": 1710.0,
        "bottom_elev_ft": 94.0,
        "detention_design": {"adequacy_status": "adequate", "provided_storage_cf": 45000.0, "required_storage_cf": 42000.0},
        "geometry_quality": {"has_bottom": True, "footprint_consistency_ratio": 0.75},
        "overflow_spillway": {"verified": True, "capacity_cfs": 25.0},
    }
    project.meta.update(
        {
            "grading_summary": {
                "success": True,
                "source": "dense_benchmark",
                "existing_surface": {"id": "eg-dense"},
                "proposed_surface": {"id": "fg-dense", "cell_size": 5.0},
                "stats": {"proposed_contour_count": 12, "spot_grade_count": 18, "flow_arrow_count": 10},
                "surface_controls": {
                    "has_primary_drainage_direction": True,
                    "primary_low_point": {"id": "lp-1", "x": 180.0, "y": 155.0},
                },
            },
            "drainage_canonical": {
                "success": True,
                "source": "dense_benchmark",
                "structures": inlets,
                "basins": [basin],
                "pipe_runs": storm_segments,
                "stats": {
                    "structure_count": len(inlets),
                    "inlet_count": len(inlets),
                    "basin_count": 1,
                    "primary_detention_count": 1,
                    "pipe_count": len(storm_segments),
                    "pipe_total_length_ft": round(sum(item["length_ft"] for item in storm_segments), 3),
                },
            },
            "storm_pipe_summary": {
                "success": True,
                "source": "dense_benchmark",
                "segments": storm_segments,
                "total_length_ft": round(sum(item["length_ft"] for item in storm_segments), 3),
                "missing_data_segments": [],
                "stats": {"total_length_ft": round(sum(item["length_ft"] for item in storm_segments), 3), "selected_basin_name": "PRIMARY DETENTION"},
                "graph_validation": {"valid": True},
                "hydraulic_validation": {"valid": True},
                "backwater_validation": {"valid": True, "surcharged_segments": []},
            },
            "sanitary_summary": {
                "success": True,
                "source": "dense_benchmark",
                "segments": sanitary_segments,
                "manholes": manholes,
                "route_count": len(sanitary_segments),
                "total_length_ft": round(sum(item["length_ft"] for item in sanitary_segments), 3),
                "stats": {
                    "segment_count": len(sanitary_segments),
                    "manhole_count": len(manholes),
                    "service_count": 0,
                    "total_length_ft": round(sum(item["length_ft"] for item in sanitary_segments), 3),
                    "main_length_ft": round(sum(item["length_ft"] for item in sanitary_segments if item["segment_role"] == "main"), 3),
                    "lateral_length_ft": round(sum(item["length_ft"] for item in sanitary_segments if item["segment_role"] == "lateral"), 3),
                },
            },
            "utility_summary": {
                "success": True,
                "source": "dense_benchmark",
                "system_type": "water",
                "segments": water_segments,
                "structures": hydrants,
                "hydrants": hydrants,
                "route_count": len(water_segments),
                "total_length_ft": round(sum(item["length_ft"] for item in water_segments), 3),
                "shallow_segment_count": 0,
                "gravity_slope_issue_count": 0,
                "stats": {"total_length_ft": round(sum(item["length_ft"] for item in water_segments), 3)},
                "coordination": {"utility_related_unresolved_conflict_count": 0, "post_validation_valid": True},
                "conflict_hooks": {"utility_system_type": "water", "utility_segments": water_segments},
            },
        }
    )
    return {
        "project": project,
        "storm_segments": storm_segments,
        "sanitary_segments": sanitary_segments,
        "water_segments": water_segments,
        "inlets": inlets,
        "manholes": manholes,
        "hydrants": hydrants,
    }


def _large_terrain_benchmark(point_side: int = 31, grid_side: int = 100) -> Dict[str, Any]:
    points = [
        SurveyPoint(
            x=float(col * 10.0),
            y=float(row * 10.0),
            z=100.0 + math.sin(col / 5.0) * 2.0 + math.cos(row / 7.0) * 2.0,
            point_id=f"pt-{row:03d}-{col:03d}",
            source="synthetic_scale_fixture",
            confidence="survey-unverified",
        )
        for row in range(point_side)
        for col in range(point_side)
    ]
    tin_started = time.perf_counter()
    tin_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    tin = SurfaceEngine(points, control_verified=False, source_type="survey-unverified").build_tin()
    tin_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    grid_started = time.perf_counter()
    terrain_grid_values = [
        [100.0 + math.sin(col / 8.0) * 1.5 + math.cos(row / 9.0) * 1.5 for col in range(grid_side)]
        for row in range(grid_side)
    ]
    grid_runtime_ms = round((time.perf_counter() - grid_started) * 1000.0, 3)
    return {
        "tin": {
            "point_count": len(points),
            "triangle_count": len(tin.triangles),
            "runtime_ms": round((time.perf_counter() - tin_started) * 1000.0, 3),
            "memory_delta_mb": round(max(0.0, _rss_to_mb(tin_after) - _rss_to_mb(tin_before)), 3),
            "control_verified": tin.control_verified,
            "source_type": tin.source_type,
            "truth_label": tin.metadata["truth_label"],
        },
        "terrain_grid": {
            "sample_count": grid_side * grid_side,
            "runtime_ms": grid_runtime_ms,
            "min_elevation": round(min(min(row) for row in terrain_grid_values), 3),
            "max_elevation": round(max(max(row) for row in terrain_grid_values), 3),
            "review_required": True,
            "construction_release_allowed": False,
        },
        "blockers": [
            "TIN builds above roughly 2500 points exceeded 10 seconds in local probing and must stay async or be replaced with a proven triangulation/indexing path before public beta.",
            "Synthetic terrain scale fixtures verify runtime shape only; they are not survey/control evidence.",
        ],
    }


def run_dense_utility_benchmark(write_report: bool = False) -> Dict[str, Any]:
    fixture = _dense_project()
    project: ProjectModel = fixture["project"]
    started = time.perf_counter()
    before_mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    actions = canonical_export_actions(project)
    plan = {
        "project_id": "chat50-dense-utility",
        "project_name": project.name,
        "units": "ft",
        "actions": actions,
        "meta": {
            "project_id": "chat50-dense-utility",
            "canonical_revision": "chat50-dense-v1",
            "canonical_model_hash": "chat50-dense-hash-v1",
            "storm_pipes": project.meta["storm_pipe_summary"],
            "sanitary": project.meta["sanitary_summary"],
            "utilities": project.meta["utility_summary"],
            "coordination": {
                "resolved_count": 14,
                "unresolved_count": 0,
                "conflicts": [{"id": f"conflict-{index:03d}", "status": "resolved", "reroute_id": f"reroute-{index:03d}"} for index in range(1, 15)],
                "reroutes": [{"id": f"reroute-{index:03d}", "source_conflict_id": f"conflict-{index:03d}"} for index in range(1, 15)],
            },
            "construction_readiness": {
                "evidence": {
                    "standards_production_usable": True,
                    "existing_conditions_production_ready": True,
                    "civil_production_ready": True,
                }
            },
        },
    }
    quantities = compute_plan_quantities(plan)
    plan["meta"]["quantities"] = {
        "quantity_audit": quantities.explain.get("quantity_audit", {}),
        "meta_summary": quantities.explain.get("meta_summary", {}),
        "line_items": [
            {"metric": "pipe_length_ft", "quantity": quantities.totals["pipe_length_ft"], "unit": "ft"},
            {"metric": "sanitary_length_ft", "quantity": quantities.totals["sanitary_length_ft"], "unit": "ft"},
            {"metric": "utility_length_ft", "quantity": quantities.totals["utility_length_ft"], "unit": "ft"},
        ],
    }
    export_report = build_export_package_report_v1(plan, export_type="dxf", generated_at="2026-06-06T00:00:00Z")
    terrain_report = _large_terrain_benchmark()
    after_mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    runtime_ms = round((time.perf_counter() - started) * 1000.0, 3)

    expected = {
        "storm_segments": _ids(fixture["storm_segments"]),
        "sanitary_segments": _ids(fixture["sanitary_segments"]),
        "water_segments": _ids(fixture["water_segments"]),
        "inlets": _ids(fixture["inlets"]),
        "sanitary_manholes": _ids(fixture["manholes"]),
    }
    output = {
        "storm_segments": _source_ids(actions, "storm_pipe_segment"),
        "sanitary_segments": _source_ids(actions, "sanitary_segment"),
        "water_segments": _source_ids(actions, "utility_segment"),
        "inlets": _source_ids(actions, "drainage_structure"),
        "sanitary_manholes": _source_ids(actions, "sanitary_manhole"),
    }
    missing = {key: sorted(expected[key] - output[key]) for key in expected}
    extra = {key: sorted(output[key] - expected[key]) for key in expected}
    quantity_audit = quantities.explain.get("quantity_audit", {})
    export_ids = set(export_report["canonical_ids_included"])
    report = {
        "benchmark": "chat145_dense_utility_benchmark",
        "benchmark_design": {
            "storm_segments": len(fixture["storm_segments"]),
            "sanitary_segments": len(fixture["sanitary_segments"]),
            "water_segments": len(fixture["water_segments"]),
            "crossings_and_conflicts": 14,
            "supported_structures": {"inlets": len(fixture["inlets"]), "sanitary_manholes": len(fixture["manholes"])},
            "unsupported_structures": {"water_hydrants": len(fixture["hydrants"])},
        },
        "runtime_ms": runtime_ms,
        "terrain_runtime_ms": terrain_report["tin"]["runtime_ms"] + terrain_report["terrain_grid"]["runtime_ms"],
        "memory_mb": {
            "ru_maxrss_before": _rss_to_mb(before_mem),
            "ru_maxrss_after": _rss_to_mb(after_mem),
            "delta": round(max(0.0, _rss_to_mb(after_mem) - _rss_to_mb(before_mem)), 3),
        },
        "terrain_memory_mb": {
            "tin_delta": terrain_report["tin"]["memory_delta_mb"],
        },
        "input_object_counts": {key: len(value) for key, value in expected.items()} | {"water_hydrants_unsupported": len(fixture["hydrants"])},
        "output_object_counts": {key: len(value) for key, value in output.items()},
        "dropped_missing_objects": missing,
        "unexpected_output_objects": extra,
        "validation": {
            "drainage": drainage_export_validation(project),
            "storm": storm_export_validation(project),
            "utility": utility_export_validation(project),
            "quantities_success": quantities.success,
            "quantity_traceability_complete": quantities.explain["meta_summary"]["quantity_traceability_complete"],
            "coordination_resolved_conflict_count": quantities.totals["coordination_resolved_conflict_count"],
            "coordination_unresolved_conflict_count": quantities.totals["coordination_unresolved_conflict_count"],
            "export_trace_contains_all_supported_ids": all(set(ids).issubset(export_ids) for ids in expected.values()),
            "quantity_trace_contains_all_segment_ids": {
                "storm": expected["storm_segments"].issubset(set(quantity_audit["pipe_length_ft"]["source_object_ids"])),
                "sanitary": expected["sanitary_segments"].issubset(set(quantity_audit["sanitary_length_ft"]["source_object_ids"])),
                "water": expected["water_segments"].issubset(set(quantity_audit["utility_length_ft"]["source_object_ids"])),
            },
        },
        "blockers": [
            "Water hydrants are accepted in the dense input fixture but are not yet represented by canonical_utility_actions; benchmark reports them as unsupported instead of counting them as a pass."
        ]
        + terrain_report["blockers"],
        "terrain": terrain_report,
        "engine_scale_limit": {
            "supported_dense_scale_verified": "1000 storm segments, 800 sanitary segments, 1000 water segments, 1000 inlets, 800 sanitary manholes",
            "supported_tin_scale_verified": "961 survey-unverified TIN points and 10000 terrain grid samples",
            "unsupported_at_this_scale": "8 water hydrants lack canonical output support",
        },
    }
    if write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


class DenseUtilityBenchmarkTest(unittest.TestCase):
    def test_dense_utility_objects_are_represented_traced_and_coordinated(self) -> None:
        report = run_dense_utility_benchmark()

        self.assertTrue(report["validation"]["drainage"]["ready"], report)
        self.assertTrue(report["validation"]["storm"]["ready"], report)
        self.assertTrue(report["validation"]["utility"]["ready"], report)
        self.assertTrue(report["validation"]["quantities_success"], report)
        self.assertTrue(report["validation"]["quantity_traceability_complete"], report)
        self.assertTrue(report["validation"]["export_trace_contains_all_supported_ids"], report)
        self.assertTrue(all(report["validation"]["quantity_trace_contains_all_segment_ids"].values()), report)
        self.assertEqual(report["validation"]["coordination_resolved_conflict_count"], 14)
        self.assertEqual(report["validation"]["coordination_unresolved_conflict_count"], 0)
        self.assertTrue(all(not missing for missing in report["dropped_missing_objects"].values()), report)
        self.assertEqual(report["output_object_counts"], {key: value for key, value in report["input_object_counts"].items() if not key.endswith("_unsupported")})
        self.assertLess(report["runtime_ms"], 15000.0, report)
        self.assertGreaterEqual(report["terrain"]["tin"]["point_count"], 900, report)
        self.assertGreaterEqual(report["terrain"]["terrain_grid"]["sample_count"], 10000, report)
        self.assertLess(report["terrain"]["tin"]["runtime_ms"], 10000.0, report)
        self.assertLess(report["memory_mb"]["delta"], 96.0, report)


if __name__ == "__main__":
    unittest.main()
