import unittest
from unittest.mock import patch

from core.project_manager import ProjectManager
from backend.planning.finalization import produced_deliverables
from planner import _recompute_sanitary_summary, build_plan


def _manual_sanitary_payload(**overrides):
    payload = {
        "project_name": "Sanitary Stage Test",
        "units": "ft",
        "mode": "site_plan",
        "project_type": "commercial_pad",
        "site_type": "commercial_pad",
        "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
        "setback": 10.0,
        "street_edge": "bottom",
        "layout_strategy": "front_parking",
        "site_plan": {"building_width": 48.0, "building_depth": 34.0, "parking_count": 24},
        "deliverables": ["sanitary_plan"],
        "meta": {"input_mode": "manual", "source_input_mode": "manual", "manual_mode": True},
    }
    payload.update(overrides)
    return payload


class SanitaryStageTest(unittest.TestCase):
    def test_manual_mode_generates_canonical_sanitary_system(self) -> None:
        plan = build_plan(_manual_sanitary_payload())
        meta = plan.get("meta") or {}
        sanitary = meta.get("sanitary") or {}
        totals = ((meta.get("quantities") or {}).get("totals") or {})
        produced = ((meta.get("deliverables") or {}).get("produced") or [])

        self.assertTrue((meta.get("engineering_status") or {}).get("success"))
        self.assertTrue(sanitary.get("success"))
        self.assertGreater(sanitary.get("route_count") or 0, 0)
        self.assertGreater(sanitary.get("service_count") or 0, 0)
        self.assertGreater(sanitary.get("manhole_count") or 0, 0)
        self.assertIn("sanitary_plan", produced)
        self.assertGreater(totals.get("sanitary_length_ft") or 0, 0)
        self.assertGreater(totals.get("sanitary_main_length_ft") or 0, 0)
        self.assertGreater(totals.get("sanitary_service_count") or 0, 0)

        san_layers = sum(1 for action in plan.get("actions") or [] if str(action.get("layer") or "").upper() == "SAN")
        self.assertGreater(san_layers, 0)

    def test_manual_mode_fails_when_sanitary_is_requested_but_cannot_be_generated(self) -> None:
        with patch("planner._sanitary_building_nodes", return_value=[]):
            plan = build_plan(_manual_sanitary_payload())
        failures = (((plan.get("meta") or {}).get("manual_validation") or {}).get("failures") or [])
        codes = [item.get("code") for item in failures]
        self.assertIn("MANUAL_SANITARY_OUTPUT_MISSING", codes)

    def test_sanitary_plan_is_not_packaged_without_canonical_sanitary_state(self) -> None:
        plan = build_plan(
            {
                "project_name": "No Sanitary Request",
                "units": "ft",
                "mode": "site_plan",
                "project_type": "commercial_pad",
                "site_type": "commercial_pad",
                "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
                "setback": 10.0,
                "street_edge": "bottom",
                "layout_strategy": "front_parking",
                "site_plan": {"parking_count": 24},
                "meta": {"input_mode": "manual", "source_input_mode": "manual", "manual_mode": True},
            }
        )
        sanitary = ((plan.get("meta") or {}).get("sanitary") or {})
        produced = ((plan.get("meta") or {}).get("deliverables") or {}).get("produced") or []
        self.assertEqual(sanitary, {})
        self.assertNotIn("sanitary_plan", produced)

    def test_sanitary_plan_is_not_packaged_when_network_validation_fails(self) -> None:
        plan = {
            "actions": [{"task": "polyline", "layer": "SAN", "points": [[0.0, 0.0], [80.0, 0.0]]}],
            "meta": {
                "sanitary": {
                    "success": True,
                    "route_count": 1,
                    "missing_service_buildings": ["BLDG-2"],
                    "graph_validation": {"valid": True},
                    "network_validation": {
                        "valid": False,
                        "service_coverage": {
                            "expected_buildings": ["BLDG-1", "BLDG-2"],
                            "served_buildings": ["BLDG-1"],
                            "missing_buildings": ["BLDG-2"],
                            "valid": False,
                        },
                    },
                }
            },
        }

        self.assertNotIn("sanitary_plan", produced_deliverables(plan))

    def test_sanitary_plan_is_packaged_only_after_canonical_sanitary_validation(self) -> None:
        plan = {
            "actions": [{"task": "polyline", "layer": "SAN", "points": [[0.0, 0.0], [80.0, 0.0]]}],
            "meta": {
                "sanitary": {
                    "success": True,
                    "route_count": 1,
                    "missing_service_buildings": [],
                    "graph_validation": {"valid": True},
                    "network_validation": {
                        "valid": True,
                        "service_coverage": {
                            "expected_buildings": ["BLDG-1"],
                            "served_buildings": ["BLDG-1"],
                            "missing_buildings": [],
                            "valid": True,
                        },
                    },
                }
            },
        }

        self.assertIn("sanitary_plan", produced_deliverables(plan))

    def test_post_reroute_recompute_rolls_service_flow_into_main_and_blocks_missing_service(self) -> None:
        manager = ProjectManager()
        project = manager.project
        sanitary = {
            "expected_service_buildings": ["BLDG-1", "BLDG-2", "BLDG-3"],
            "segments": [
                {
                    "name": "LAT-1",
                    "segment_role": "lateral",
                    "served_building": "BLDG-1",
                    "start_name": "BLDG-1",
                    "end_name": "MAIN-A",
                    "route_points": [[10.0, 10.0], [20.0, 10.0]],
                    "diameter_in": 8.0,
                    "flow_cfs": 0.02,
                    "start_invert_ft": 97.0,
                    "end_invert_ft": 96.7,
                },
                {
                    "name": "LAT-2",
                    "segment_role": "lateral",
                    "served_building": "BLDG-2",
                    "start_name": "BLDG-2",
                    "end_name": "MAIN-A",
                    "route_points": [[10.0, 20.0], [20.0, 10.0]],
                    "diameter_in": 8.0,
                    "flow_cfs": 0.03,
                    "start_invert_ft": 97.0,
                    "end_invert_ft": 96.65,
                },
                {
                    "name": "SAN-MAIN-1",
                    "segment_role": "main",
                    "served_building": "shared_main",
                    "start_name": "MAIN-A",
                    "end_name": "SAN_TIE_IN",
                    "route_points": [[20.0, 10.0], [80.0, 10.0]],
                    "diameter_in": 8.0,
                    "flow_cfs": 0.01,
                    "start_invert_ft": 96.5,
                    "end_invert_ft": 95.8,
                },
            ],
            "manholes": [],
        }
        manager.latest_outputs["sanitary"] = sanitary
        project.meta["sanitary_summary"] = sanitary

        _recompute_sanitary_summary(project, manager, prefer_cache=True)

        recomputed = project.meta["sanitary_summary"]
        main = next(item for item in recomputed["segments"] if item["name"] == "SAN-MAIN-1")
        self.assertAlmostEqual(main["upstream_service_flow_cfs"], 0.05, places=4)
        self.assertAlmostEqual(main["flow_cfs"], 0.05, places=4)
        self.assertFalse(recomputed["service_coverage"]["valid"])
        self.assertIn("BLDG-3", recomputed["service_coverage"]["missing_buildings"])
        self.assertFalse(recomputed["network_validation"]["valid"])

    def test_post_reroute_recompute_propagates_service_flow_through_main_graph(self) -> None:
        manager = ProjectManager()
        project = manager.project
        sanitary = {
            "expected_service_buildings": ["BLDG-1", "BLDG-2"],
            "segments": [
                {
                    "name": "LAT-1",
                    "segment_role": "lateral",
                    "served_building": "BLDG-1",
                    "start_name": "BLDG-1",
                    "end_name": "NODE-A",
                    "route_points": [[0.0, 0.0], [10.0, 0.0]],
                    "diameter_in": 8.0,
                    "flow_cfs": 0.02,
                    "start_invert_ft": 98.0,
                    "end_invert_ft": 97.8,
                },
                {
                    "name": "LAT-2",
                    "segment_role": "lateral",
                    "served_building": "BLDG-2",
                    "start_name": "BLDG-2",
                    "end_name": "NODE-B",
                    "route_points": [[0.0, 10.0], [40.0, 0.0]],
                    "diameter_in": 8.0,
                    "flow_cfs": 0.03,
                    "start_invert_ft": 98.0,
                    "end_invert_ft": 97.6,
                },
                {
                    "name": "SAN-MAIN-1",
                    "segment_role": "main",
                    "start_name": "NODE-A",
                    "end_name": "NODE-B",
                    "route_points": [[10.0, 0.0], [40.0, 0.0]],
                    "diameter_in": 8.0,
                    "flow_cfs": 0.01,
                    "start_invert_ft": 97.5,
                    "end_invert_ft": 97.0,
                },
                {
                    "name": "SAN-MAIN-2",
                    "segment_role": "main",
                    "start_name": "NODE-B",
                    "end_name": "SAN_TIE_IN",
                    "route_points": [[40.0, 0.0], [90.0, 0.0]],
                    "diameter_in": 8.0,
                    "flow_cfs": 0.01,
                    "start_invert_ft": 96.9,
                    "end_invert_ft": 96.2,
                },
            ],
            "manholes": [],
        }
        manager.latest_outputs["sanitary"] = sanitary
        project.meta["sanitary_summary"] = sanitary

        _recompute_sanitary_summary(project, manager, prefer_cache=True)

        recomputed = project.meta["sanitary_summary"]
        by_name = {item["name"]: item for item in recomputed["segments"]}
        self.assertAlmostEqual(by_name["SAN-MAIN-1"]["flow_cfs"], 0.02, places=4)
        self.assertAlmostEqual(by_name["SAN-MAIN-2"]["flow_cfs"], 0.05, places=4)
        self.assertAlmostEqual(recomputed["post_reroute_recalculation"]["node_inflow_cfs"]["NODE-B"], 0.05, places=4)

    def test_recompute_generates_manholes_at_main_spacing_points(self) -> None:
        manager = ProjectManager()
        project = manager.project
        sanitary = {
            "expected_service_buildings": [],
            "segments": [
                {
                    "name": "SAN-LONG-MAIN",
                    "segment_role": "main",
                    "start_name": "NODE-A",
                    "end_name": "OUTFALL",
                    "route_points": [[0.0, 0.0], [900.0, 0.0]],
                    "diameter_in": 8.0,
                    "flow_cfs": 0.04,
                    "start_invert_ft": 98.0,
                    "end_invert_ft": 94.0,
                }
            ],
            "manholes": [],
        }
        manager.latest_outputs["sanitary"] = sanitary
        project.meta["sanitary_summary"] = sanitary

        _recompute_sanitary_summary(project, manager, prefer_cache=True)

        recomputed = project.meta["sanitary_summary"]
        main = recomputed["segments"][0]
        self.assertGreaterEqual(recomputed["manhole_count"], 4)
        self.assertGreaterEqual(len(main["node_ids"]), 4)
        self.assertTrue(recomputed["structure_spacing_validation"]["valid"])
        self.assertGreaterEqual(recomputed["structure_spacing_validation"]["generated_manhole_count"], 4)


if __name__ == "__main__":
    unittest.main()
