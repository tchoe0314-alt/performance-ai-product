from __future__ import annotations

import unittest

import planner
from backend.planning.finalization import _accessible_route_evidence, _circulation_access_evidence


def _base_payload() -> dict:
    return {
        "project_name": "Site planning release candidate",
        "units": "ft",
        "mode": "site_plan",
        "project_type": "commercial_pad",
        "site_type": "commercial_pad",
        "terrain": "2% slope north to south",
        "lot": {"x": 0, "y": 0, "w": 240, "h": 180},
        "street_edge": "left",
        "setback": 12,
        "site_plan": {"building_width": 60, "building_depth": 40, "parking_count": 12},
        "buildings": [{"id": "office", "type": "office", "x": 80, "y": 40, "w": 60, "d": 40}],
        "site_objects": [],
        "meta": {"orchestrator_meta": {"runtime_phase_batch_limit": 1}},
    }


def _parking() -> dict:
    return {
        "id": "parking", "type": "parking", "x": 60, "y": 115, "w": 120, "d": 50,
        "meta": {"requested_stalls": 12, "parking_design_basis": {
            "stall_width_ft": 9, "stall_depth_ft": 18, "aisle_width_ft": 24,
            "accessible_stall_count": 1, "accessible_stall_width_ft": 8,
            "access_aisle_width_ft": 5, "source": "synthetic_candidate_basis_v1",
        }},
    }


def _route() -> dict:
    return {
        "id": "accessible-route", "type": "sidewalk",
        "geometry": [[74.5, 152], [74.5, 131], [74.5, 105], [110, 80]],
        "meta": {"accessible_route_design_basis": {
            "route_geometry_source": "synthetic_route_survey_v1",
            "criteria_source": "synthetic_accessibility_basis_v1",
            "building_entrance_xy": [110, 80], "route_width_ft": 5,
            "minimum_route_width_ft": 4, "measured_running_slope_pct": 2.5,
            "maximum_running_slope_pct": 5, "measured_cross_slope_pct": 1.2,
            "maximum_cross_slope_pct": 2, "vehicle_crossing_count": 1,
            "vehicle_crossing_controls_source": "synthetic_marked_crossing_v1",
        }},
    }


def _access(*, valid: bool = True) -> dict:
    return {
        "id": "site-access", "type": "driveway",
        "geometry": [[0 if valid else 10, 140], [30, 140], [60, 140]],
        "meta": {"circulation_design_basis": {
            "route_geometry_source": "synthetic_access_survey_v1",
            "criteria_source": "synthetic_circulation_basis_v1",
            "site_entrance_xy": [0 if valid else 10, 140],
            "route_width_ft": 24 if valid else 16, "minimum_route_width_ft": 20,
            "design_vehicle": {"name": "Synthetic SU", "overall_length_ft": 30,
                "overall_width_ft": 8.5, "wheelbase_ft": 20,
                "source": "synthetic_vehicle_record_v1"},
            "swept_path_evidence": {"source": "synthetic_envelope_v1",
                "maneuvering_area_polygon": [[0, 110], [190, 110], [190, 175], [0, 175]],
                "swept_envelope_polygon": [[4, 124], [180, 124], [180, 158], [4, 158]]},
            "fire_access_design_basis": {"criteria_source": "synthetic_fire_basis_v1",
                "clear_width_ft": 24, "minimum_clear_width_ft": 20,
                "vertical_clearance_ft": 14, "minimum_vertical_clearance_ft": 13.5,
                "measured_max_grade_pct": 5, "maximum_grade_pct": 10,
                "surface_capacity_tons": 40, "minimum_surface_capacity_tons": 36,
                "dead_end_length_ft": 60, "maximum_dead_end_without_turnaround_ft": 150,
                "surface_capacity_source": "synthetic_pavement_record_v1",
                "access_control_source": "synthetic_access_control_v1"},
        }},
    }


class SitePlanningReleaseCandidateTests(unittest.TestCase):
    def test_supported_geometry_persists_truthful_evidence(self) -> None:
        payload = _base_payload()
        payload["site_objects"] = [_parking(), _route(), _access()]
        plan = planner.build_plan(payload)
        self.assertEqual(plan["meta"]["stage_completeness"]["statuses"]["layout"], "complete")
        program = plan["meta"]["parking_program"]
        self.assertEqual(program["geometry_stall_count"], 12)
        self.assertTrue(program["accessible_route_verified"])
        self.assertTrue(program["vehicle_access_route_verified"])
        circulation = program["circulation_access_evidence"]
        self.assertTrue(circulation["turning_movement_verified"])
        self.assertTrue(circulation["fire_access_geometry_verified"])
        self.assertFalse(circulation["fire_access_verified"])
        self.assertFalse(circulation["jurisdictional_compliance_verified"])

    def test_interior_narrow_access_fails_closed(self) -> None:
        parsed = {"lot": _base_payload()["lot"]}
        actions = [
            {"task": "rectangle", "layer": "PARKING", "origin": [60, 115], "width": 120, "height": 50},
            {"task": "polyline", "layer": "PAVEMENT", "points": [[10, 140], [60, 140]],
             "canonical_source_id": "bad", "meta": {"circulation_geometry_candidate": True,
             "circulation_design_basis": _access(valid=False)["meta"]["circulation_design_basis"]}},
        ]
        evidence = _circulation_access_evidence(parsed, actions)
        self.assertFalse(evidence["verified"])
        self.assertIn("site_entrance_to_parking_geometry", evidence["missing_evidence"])
        self.assertIn("circulation_width_design_basis", evidence["missing_evidence"])

    def test_accessible_route_slope_and_crossing_fail_closed(self) -> None:
        route = _route()
        basis = route["meta"]["accessible_route_design_basis"]
        basis["measured_running_slope_pct"] = 7
        basis.pop("vehicle_crossing_controls_source")
        evidence = _accessible_route_evidence([
            {"task": "rectangle", "layer": "ACCESS_AISLE", "origin": [72, 130], "width": 5, "height": 18},
            {"task": "rectangle", "layer": "BUILDING", "origin": [80, 40], "width": 60, "height": 40},
            {"task": "polyline", "layer": "WALK", "points": route["geometry"],
             "canonical_source_id": "route", "meta": {"accessible_route_geometry_candidate": True,
             "accessible_route_design_basis": basis}},
        ])
        self.assertFalse(evidence["verified"])
        self.assertIn("route_width_and_slope_design_basis", evidence["missing_evidence"])
        self.assertIn("vehicle_crossing_treatment", evidence["missing_evidence"])


if __name__ == "__main__":
    unittest.main()
