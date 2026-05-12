from __future__ import annotations

import unittest

from backend.planning.finalization import canonical_area_accounting, canonical_truth_audit
from backend.planning.runtime import collect_plan_stats


def _metric(value: float) -> dict:
    return {"value": value, "units": "ft", "category": "stale", "meta": {}}


class Phase1Slice6BMetricPrecedenceTest(unittest.TestCase):
    def test_collect_plan_stats_prefers_canonical_summaries_and_quantities_over_stale_metrics(self) -> None:
        plan = {
            "actions": [],
            "meta": {
                "storm_pipes": {
                    "total_length_ft": 100.0,
                    "segments": [{"id": "storm-1", "length_ft": 100.0}],
                },
                "utilities": {
                    "total_length_ft": 40.0,
                    "conflict_hooks": {"utility_segments": [{"id": "util-1", "length_ft": 40.0}]},
                },
                "quantities": {
                    "totals": {
                        "action_count": 4,
                        "building_area_sf": 1200.0,
                        "parking_area_sf": 2400.0,
                        "road_area_sf": 800.0,
                        "pipe_length_ft": 100.0,
                        "utility_length_ft": 40.0,
                        "estimated_impervious_area_sf": 4400.0,
                    }
                },
                "manager_export": {
                    "metrics": {
                        "layout_action_count": _metric(99.0),
                        "layout_building_area_sf": _metric(9999.0),
                        "layout_parking_area_sf": _metric(9999.0),
                        "layout_road_area_sf": _metric(9999.0),
                        "layout_impervious_area_sf": _metric(99999.0),
                        "storm_pipe_length_ft": _metric(999.0),
                        "utility_total_length_ft": _metric(777.0),
                    }
                },
            },
        }

        stats = collect_plan_stats(plan)

        self.assertEqual(stats["action_count"], 4)
        self.assertEqual(stats["estimated_building_area_sf"], 1200.0)
        self.assertEqual(stats["estimated_parking_area_sf"], 2400.0)
        self.assertEqual(stats["estimated_road_area_sf"], 800.0)
        self.assertEqual(stats["estimated_pipe_length_ft"], 100.0)
        self.assertEqual(stats["estimated_utility_length_ft"], 40.0)
        self.assertEqual(stats["estimated_impervious_area_sf"], 4400.0)

    def test_collect_plan_stats_uses_manager_metrics_only_when_canonical_values_are_missing(self) -> None:
        plan = {
            "actions": [],
            "meta": {
                "manager_export": {
                    "metrics": {
                        "layout_action_count": _metric(3.0),
                        "storm_pipe_length_ft": _metric(25.0),
                        "utility_total_length_ft": _metric(35.0),
                        "layout_impervious_area_sf": _metric(45.0),
                    }
                }
            },
        }

        stats = collect_plan_stats(plan)

        self.assertEqual(stats["action_count"], 3)
        self.assertEqual(stats["estimated_pipe_length_ft"], 25.0)
        self.assertEqual(stats["estimated_utility_length_ft"], 35.0)
        self.assertEqual(stats["estimated_impervious_area_sf"], 45.0)

    def test_truth_audit_reports_canonical_truth_sources_before_stale_metrics(self) -> None:
        plan = {
            "actions": [],
            "meta": {
                "stats": {"estimated_impervious_area_sf": 4400.0},
                "qa": {
                    "stats": {
                        "estimated_pipe_length_ft": 100.0,
                        "estimated_utility_length_ft": 40.0,
                        "estimated_impervious_area_sf": 4400.0,
                        "lot_area_sf": 10000.0,
                    }
                },
                "quantities": {
                    "totals": {
                        "pipe_length_ft": 100.0,
                        "utility_length_ft": 40.0,
                        "sanitary_length_ft": 80.0,
                        "estimated_impervious_area_sf": 4400.0,
                        "lot_area_sf": 10000.0,
                    }
                },
                "storm_pipes": {
                    "total_length_ft": 100.0,
                    "segments": [{"id": "storm-1", "length_ft": 100.0}],
                    "total_system_flow_cfs": 1.0,
                    "total_system_capacity_cfs": 3.0,
                    "controlling_segment": "storm-1",
                    "max_capacity_ratio": 0.33,
                    "hydraulic_validation": {"valid": True},
                    "graph_validation": {"valid": True},
                    "missing_data_segments": [],
                },
                "sanitary": {
                    "route_count": 1,
                    "total_length_ft": 80.0,
                    "stats": {"total_length_ft": 80.0},
                    "graph_validation": {"valid": True},
                    "network_validation": {"valid": True},
                    "missing_service_buildings": [],
                    "segments": [{"id": "san-1", "length_ft": 80.0}],
                },
                "utilities": {
                    "route_count": 1,
                    "total_length_ft": 40.0,
                    "stats": {"total_length_ft": 40.0},
                    "conflict_hooks": {"utility_segments": [{"id": "util-1", "length_ft": 40.0}]},
                },
                "coordination": {"unresolved_conflicts": []},
                "manager_export": {
                    "metrics": {
                        "layout_impervious_area_sf": _metric(99999.0),
                        "storm_pipe_length_ft": _metric(999.0),
                        "sanitary_total_length_ft": _metric(888.0),
                        "utility_total_length_ft": _metric(777.0),
                    }
                },
            },
        }

        audit = canonical_truth_audit({"mode": "site_plan", "lot": {"w": 100.0, "h": 100.0}}, plan, sanitary_requested=lambda _parsed: True)
        checks = {check["code"]: check for check in audit["checks"]}

        self.assertEqual(checks["PIPE_LENGTH_CONSISTENT"]["context"]["truth_length_ft"], 100.0)
        self.assertEqual(checks["PIPE_LENGTH_CONSISTENT"]["context"]["truth_source"], "storm_pipes.total_length_ft")
        self.assertEqual(checks["UTILITY_LENGTH_CONSISTENT"]["context"]["truth_length_ft"], 40.0)
        self.assertEqual(checks["UTILITY_LENGTH_CONSISTENT"]["context"]["truth_source"], "utilities.total_length_ft")
        self.assertEqual(checks["SANITARY_LENGTH_CONSISTENT"]["context"]["truth_length_ft"], 80.0)
        self.assertEqual(checks["SANITARY_LENGTH_CONSISTENT"]["context"]["truth_source"], "sanitary.total_length_ft")

        accounting = canonical_area_accounting({"lot": {"w": 100.0, "h": 100.0}}, plan)
        self.assertEqual(accounting["impervious_area_sf"], 4400.0)


if __name__ == "__main__":
    unittest.main()
