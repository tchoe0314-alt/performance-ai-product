from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Optional

import pytest

import planner
from backend.planning.cad_entity_model import (
    CAD_ENGINEERING_OBJECTS_VERSION,
    apply_cad_entity_operation,
    attach_cad_entity_model_to_result,
    build_cad_entity_model,
)
from backend.planning.export_package_report import build_export_package_report_v1
from backend.planning.reactive_model import build_reactive_change_evidence
from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.project_store import ProjectStore


SITE_AREA_SF = 4.2 * 43_560
SITE_WIDTH_FT = 500.0
SITE_HEIGHT_FT = SITE_AREA_SF / SITE_WIDTH_FT


def _handoff(
    object_id: str,
    object_type: str,
    geometry_type: str,
    points: list[tuple[float, float]],
    *,
    name: str,
    attributes: Optional[dict] = None,
    relationships: Optional[list[dict]] = None,
) -> dict:
    return {
        "schema_version": "canonical_geometry_handoff_v1",
        "object_id": object_id,
        "geometry_id": f"geometry-{object_id}",
        "object_name": name,
        "object_type": object_type,
        "canonical_object_type": object_type,
        "geometry_type": geometry_type,
        "vertices": [
            {"id": f"{object_id}-v{index}", "x": x, "y": y, "units": "ft"}
            for index, (x, y) in enumerate(points)
        ],
        "units": "ft",
        "coordinate_system": "site_local_ft",
        "source": "manual_drawn",
        "confidence": "user_drawn_review_required",
        "engineering_status": "draft_review_required",
        "engineering_attributes": attributes or {},
        "relationships": relationships or [],
        "source_ui_mode": "canvas_draw",
        "valid": True,
        "blockers": [],
    }


def _commercial_project_input() -> dict:
    objects = [
        _handoff(
            "office-a",
            "office_building",
            "polygon",
            [(120, 120), (320, 120), (320, 260), (120, 260), (120, 120)],
            name="Office Building A",
            attributes={"use_type": "office", "floor_count": 1, "gross_area_sf": 28_000},
            relationships=[
                {"relationship": "served_by", "target_object_id": "parking-a"},
                {"relationship": "drains_to", "target_object_id": "basin-a"},
                {"relationship": "connected_to", "target_object_id": "water-a"},
                {"relationship": "connected_to", "target_object_id": "sanitary-a"},
            ],
        ),
        _handoff(
            "parking-a",
            "parking",
            "polygon",
            [(40, 35), (390, 35), (390, 110), (40, 110), (40, 35)],
            name="Parking Area A",
            attributes={"stall_count": 140, "ada_space_count": 6, "stall_angle_deg": 90},
            relationships=[{"relationship": "serves", "target_object_id": "office-a"}],
        ),
        _handoff(
            "basin-a",
            "detention_basin",
            "polygon",
            [(365, 230), (455, 220), (475, 270), (450, 330), (370, 320), (350, 270), (365, 230)],
            name="Detention Basin A",
            attributes={"bottom_elevation_ft": 96.0, "top_elevation_ft": 102.0, "side_slope_h_to_1v": 4.0},
            relationships=[{"relationship": "discharges_to", "target_object_id": "outfall-a"}],
        ),
        _handoff(
            "driveway-a",
            "driveway",
            "polyline",
            [(0, 75), (40, 75), (90, 90)],
            name="Driveway A",
            attributes={"width_ft": 28.0},
        ),
        _handoff(
            "sidewalk-a",
            "sidewalk",
            "polyline",
            [(95, 105), (120, 120), (220, 120)],
            name="ADA Sidewalk A",
            attributes={"width_ft": 5.0, "max_running_slope": 0.05},
            relationships=[{"relationship": "serves", "target_object_id": "office-a"}],
        ),
        _handoff(
            "storm-a",
            "storm_sewer",
            "polyline",
            [(80, 90), (210, 85), (360, 260)],
            name="Storm Main A",
            attributes={"diameter_in": 18.0, "slope_ft_ft": 0.01},
            relationships=[{"relationship": "discharges_to", "target_object_id": "basin-a"}],
        ),
        _handoff(
            "water-a",
            "water_line",
            "polyline",
            [(0, 60), (120, 60), (120, 120)],
            name="Water Main A",
            attributes={"diameter_in": 8.0, "material": "ductile iron"},
            relationships=[{"relationship": "serves", "target_object_id": "office-a"}],
        ),
        _handoff(
            "sanitary-a",
            "sanitary_line",
            "polyline",
            [(0, 50), (150, 50), (170, 120)],
            name="Sanitary Main A",
            attributes={"diameter_in": 8.0, "slope_ft_ft": 0.02},
            relationships=[{"relationship": "serves", "target_object_id": "office-a"}],
        ),
        _handoff(
            "inlet-a",
            "inlet",
            "point",
            [(210, 85)],
            name="Inlet A",
            relationships=[{"relationship": "connects_to", "target_object_id": "storm-a"}],
        ),
        _handoff(
            "outfall-a",
            "outfall",
            "point",
            [(455, 270)],
            name="Outfall A",
            relationships=[{"relationship": "receives_from", "target_object_id": "basin-a"}],
        ),
    ]
    return {
        "address": "20525 Margo St, Gretna, NE 68028",
        "manual_fields": {
            "lot_width": SITE_WIDTH_FT,
            "lot_height": SITE_HEIGHT_FT,
            "site_locked": True,
            "canonical_geometry_handoff_v1": objects,
        },
    }


def _engineering_payload(project_input: dict) -> dict:
    return {
        "project_name": "4.2 Acre Commercial End-State Benchmark",
        "units": "ft",
        "mode": "site_plan",
        "project_type": "commercial_pad",
        "site_type": "commercial_pad",
        "terrain": "8% slope west to east",
        "lot": {"x": 0.0, "y": 0.0, "w": SITE_WIDTH_FT, "h": SITE_HEIGHT_FT},
        "street_edge": "left",
        "setback": 20.0,
        "site_plan": {"building_width": 200.0, "building_depth": 140.0, "parking_count": 140},
        "ponds": [{"name": "BASIN-A", "x": 350.0, "y": 220.0, "w": 125.0, "d": 110.0}],
        "drainage": {"verified_overflow_capacity_cfs": 5.0, "tailwater_elev_ft": 95.0},
        "standards": {"jurisdiction": "Gretna, Nebraska", "design_manual": "accepted benchmark criteria", "version": "2026"},
        "survey_control": {
            "datum": "NAVD88",
            "benchmark": "BM-1",
            "source": "accepted_deterministic_benchmark_fixture",
            "points": [
                {"id": "CP-1", "x": 0.0, "y": 0.0, "z": 104.0},
                {"id": "CP-2", "x": SITE_WIDTH_FT, "y": SITE_HEIGHT_FT, "z": 96.0},
            ],
        },
        "coordinate_system": {"crs": "EPSG:26841", "datum": "NAD83 / Nebraska"},
        "manual_fields": deepcopy(project_input["manual_fields"]),
    }


def test_real_firm_scenario_connects_objects_engines_persistence_reactivity_and_exports(tmp_path: Path) -> None:
    project_input = _commercial_project_input()
    model = build_cad_entity_model({}, project_input=project_input)
    objects = model[CAD_ENGINEERING_OBJECTS_VERSION]["objects"]
    by_type = {item["object_type"]: item for item in objects}

    assert SITE_WIDTH_FT * SITE_HEIGHT_FT == pytest.approx(SITE_AREA_SF)
    assert model[CAD_ENGINEERING_OBJECTS_VERSION]["object_count"] == 10
    assert {
        "building",
        "parking_area",
        "basin",
        "driveway",
        "sidewalk_path",
        "storm_main",
        "water_main",
        "sanitary_main",
        "inlet",
        "outfall",
    } == set(by_type)
    assert by_type["building"]["engineering_attributes"]["footprint_area_sf"] == pytest.approx(28_000)
    assert by_type["parking_area"]["engineering_attributes"]["stall_count"] == 140
    assert model["engineering_project_graph_v1"]["export_blocked_until_rerun"] is True

    plan = planner.build_plan(_engineering_payload(project_input))
    attached = attach_cad_entity_model_to_result({"final_plan": plan}, project_input=project_input)
    plan = attached["final_plan"]
    model = plan["meta"]["cad_entity_model_v1"]
    review = plan["meta"]["engineering_generation_review"]
    assert review["status"] == "review_required"
    assert review["blocked_systems"] == []
    for system_name in ("grading", "drainage", "storm", "sanitary", "water", "roadway", "quantities", "qa_review"):
        assert review["systems"][system_name]["canonical_output_present"] is True
    assert model["engineering_project_graph_v1"]["export_blocked_until_rerun"] is False
    assert model["generation_sync"]["cad_geometry_state_hash"] == model["cad_geometry_state_hash"]

    current_export = build_export_package_report_v1(plan, export_type="report")
    assert current_export["semantic_engineering_object_trace_v1"]["object_count"] == 10
    assert current_export["semantic_engineering_object_trace_v1"]["export_blocked_until_rerun"] is False

    database = Database(tmp_path / "end-state.db")
    auth = AuthStore(database)
    owner = auth.register_user(email="benchmark@example.com", password="benchmark-password", name="Benchmark Owner")["user"]
    store = ProjectStore(database)
    saved = store.save_project(
        user_id=owner["user_id"],
        project_id=None,
        name=plan["project_name"],
        project_input=project_input,
        latest_result={"final_plan": plan},
        session_state={"active_mode": "review", "selected_object_id": by_type["building"]["object_id"]},
        metadata={"benchmark": "real_firm_end_state_v1"},
    )
    reopened = store.get_project(user_id=owner["user_id"], project_id=saved["project_id"])
    assert reopened is not None
    assert reopened["project_input"]["manual_fields"]["lot_width"] == SITE_WIDTH_FT
    assert reopened["latest_result"]["final_plan"]["meta"]["cad_entity_model_v1"][CAD_ENGINEERING_OBJECTS_VERSION]["object_count"] == 10

    building_entity_id = by_type["building"]["geometry_entity_id"]
    moved_source, operation = apply_cad_entity_operation(
        model,
        {"action": "move_selected", "target_entity_ids": [building_entity_id], "dx": 20.0, "dy": 0.0},
        actor="benchmark-owner",
    )
    assert operation["safety_blockers"] == []
    moved_model = build_cad_entity_model({"cad_entity_model_v1": moved_source}, project_input=project_input)
    moved_graph = moved_model["engineering_project_graph_v1"]
    assert moved_graph["export_blocked_until_rerun"] is True
    assert {"parking", "ada", "drainage", "water", "sanitary", "grading", "earthwork", "quantities", "review_package"}.issubset(
        set(moved_graph["stale_systems"])
    )

    stale_plan = deepcopy(plan)
    stale_plan["meta"]["cad_entity_model_v1"] = moved_model
    stale_export = build_export_package_report_v1(stale_plan, export_type="report")
    assert stale_export["semantic_engineering_object_trace_v1"]["export_blocked_until_rerun"] is True
    assert any(item.startswith("engineering_project_graph:") for item in stale_export["stale_outputs_detected"])

    reactive = build_reactive_change_evidence(
        change_type="building",
        changed_object_id=by_type["building"]["object_id"],
        canonical_revision_before="rev-1",
        canonical_revision_after="rev-2",
    )
    assert reactive["export_blocked"] is True
    assert set(reactive["expected_dirty_stages"]) == {
        "layout",
        "grading",
        "drainage",
        "storm_pipes",
        "sanitary",
        "utility_network",
        "coordination_resolution",
        "earthwork",
        "sheets",
        "qa",
    }

    saved_after_move = store.save_project(
        user_id=owner["user_id"],
        project_id=saved["project_id"],
        name=plan["project_name"],
        project_input=project_input,
        latest_result={"final_plan": stale_plan},
        session_state={"active_mode": "review", "selected_object_id": by_type["building"]["object_id"]},
        metadata={"benchmark": "real_firm_end_state_v1", "canonical_revision": "rev-2"},
    )
    restored_moved_model = saved_after_move["latest_result"]["final_plan"]["meta"]["cad_entity_model_v1"]
    restored_building_entity = next(item for item in restored_moved_model["entities"] if item["id"] == building_entity_id)
    assert restored_building_entity["geometry"]["points"][0] == {"x": 140.0, "y": 120.0}
    assert restored_moved_model["engineering_project_graph_v1"]["export_blocked_until_rerun"] is True
