import copy
import json
import math

from engines.quantity_engine import compute_plan_quantities


def _plan():
    return {
        "units": "ft",
        "actions": [],
        "meta": {
            "grading": {"earthwork": {"cut_cf": 2700.0, "fill_cf": 1350.0, "net_cf": 1350.0}},
            "storm_pipes": {
                "segments": [
                    {"id": "STM-1", "diameter_in": 18, "path": [[0, 0, 100], [30, 40, 96]], "length_3d_ft": math.sqrt(2516), "upstream_structure_id": "DI-1", "downstream_structure_id": "MH-1"},
                    {"id": "STM-2", "diameter_in": 24, "path": [[30, 40, 96], [90, 40, 90]], "length_3d_ft": math.sqrt(3636), "upstream_structure_id": "MH-1", "downstream_structure_id": "DI-2"},
                ],
            },
            "drainage": {
                "structures": [
                    {"id": "DI-1", "structure_type": "inlet"},
                    {"id": "MH-1", "structure_type": "manhole"},
                    {"id": "DI-2", "structure_type": "inlet"},
                ],
            },
            "sanitary": {
                "segments": [{"id": "SAN-1", "diameter_in": 18, "length_ft": 70.0, "measurement_basis": "centerline_horizontal"}],
                "manholes": [{"id": "SMH-1", "structure_type": "manhole"}],
            },
        },
    }


def _construction(plan):
    result = compute_plan_quantities(plan)
    assert result.success, result.message
    return result.tables["construction_takeoff"], result.totals


def test_construction_takeoff_separates_cut_fill_pipe_groups_and_structures():
    takeoff, totals = _construction(_plan())
    assert takeoff["earthwork"] == {
        "cut_cy": 100.0,
        "fill_cy": 50.0,
        "unit": "cy",
        "status": "current",
        "derivation_method": "canonical_cut_and_fill_cf_divided_by_27",
        "haul_quantity_inferred": False,
    }
    assert totals["earthwork_cut_cy"] == 100.0
    assert totals["earthwork_fill_cy"] == 50.0
    assert [(row["system"], row["diameter_in"], row["horizontal_length_ft"]) for row in takeoff["pipes_by_system_and_diameter"]] == [
        ("sanitary", 18.0, 70.0),
        ("storm", 18.0, 50.0),
        ("storm", 24.0, 60.0),
    ]
    storm_18 = takeoff["pipes_by_system_and_diameter"][1]
    assert storm_18["three_dimensional_length_ft"] == round(math.sqrt(2516), 3)
    assert storm_18["measurement_basis"] == "centerline_horizontal"
    assert storm_18["unit"] == "ft"
    assert storm_18["rate_provenance"] == {"status": "missing", "unit_rate": None, "currency": None, "source": None}
    assert [(row["system"], row["structure_type"], row["count"]) for row in takeoff["structures_by_system_and_type"]] == [
        ("sanitary", "manhole", 1),
        ("storm", "inlet", 2),
        ("storm", "manhole", 1),
    ]


def test_diameter_change_survives_reopen_and_regroups_supported_takeoff_report():
    plan = copy.deepcopy(_plan())
    plan["meta"]["storm_pipes"]["segments"][0]["diameter_in"] = 24
    reopened = json.loads(json.dumps(plan))
    takeoff, _ = _construction(reopened)
    rows = takeoff["pipes_by_system_and_diameter"]
    assert [(row["system"], row["diameter_in"], row["horizontal_length_ft"]) for row in rows] == [
        ("sanitary", 18.0, 70.0),
        ("storm", 24.0, 110.0),
    ]
    storm = rows[1]
    assert storm["source_object_ids"] == ["STM-1", "STM-2"]
    assert storm["three_dimensional_length_ft"] == round(math.sqrt(2516) + math.sqrt(3636), 3)


def test_explicit_face_measurement_is_not_mixed_with_centerline_basis():
    plan = _plan()
    plan["meta"]["storm_pipes"]["segments"][1]["diameter_in"] = 18
    plan["meta"]["storm_pipes"]["segments"][1]["measurement_basis"] = "structure_face_to_face_horizontal"
    takeoff, _ = _construction(plan)
    storm_rows = [row for row in takeoff["pipes_by_system_and_diameter"] if row["system"] == "storm"]
    assert [(row["measurement_basis"], row["horizontal_length_ft"]) for row in storm_rows] == [
        ("centerline_horizontal", 50.0),
        ("structure_face_to_face_horizontal", 60.0),
    ]


def test_missing_earthwork_and_rates_remain_missing_not_zero_or_implied():
    plan = _plan()
    del plan["meta"]["grading"]
    takeoff, totals = _construction(plan)
    assert takeoff["earthwork"] == {
        "cut_cy": None,
        "fill_cy": None,
        "unit": "cy",
        "status": "missing",
        "derivation_method": None,
        "haul_quantity_inferred": False,
    }
    assert "earthwork_cut_cy" not in totals
    assert "earthwork_fill_cy" not in totals
    assert all(row["rate_provenance"]["status"] == "missing" for row in takeoff["pipes_by_system_and_diameter"])


def test_measured_zero_earthwork_remains_current_instead_of_missing():
    plan = _plan()
    plan["meta"]["grading"]["earthwork"] = {"cut_cf": 0.0, "fill_cf": 0.0, "net_cf": 0.0}
    takeoff, totals = _construction(plan)
    assert takeoff["earthwork"] == {
        "cut_cy": 0.0,
        "fill_cy": 0.0,
        "unit": "cy",
        "status": "current",
        "derivation_method": "canonical_cut_and_fill_cf_divided_by_27",
        "haul_quantity_inferred": False,
    }
    assert totals["earthwork_cut_cy"] == 0.0
    assert totals["earthwork_fill_cy"] == 0.0


def test_explicit_rate_provenance_is_preserved_without_applying_it_to_other_groups():
    plan = _plan()
    plan["meta"]["storm_pipes"]["segments"][0].update({"unit_rate": 125, "rate_currency": "USD", "rate_source": "Approved synthetic price book ST-18"})
    takeoff, _ = _construction(plan)
    storm_18 = next(row for row in takeoff["pipes_by_system_and_diameter"] if row["system"] == "storm" and row["diameter_in"] == 18)
    sanitary_18 = next(row for row in takeoff["pipes_by_system_and_diameter"] if row["system"] == "sanitary" and row["diameter_in"] == 18)
    assert storm_18["rate_provenance"] == {"status": "source_provided", "unit_rate": 125.0, "currency": "USD", "source": "Approved synthetic price book ST-18"}
    assert sanitary_18["rate_provenance"]["status"] == "missing"
