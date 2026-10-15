import pytest
from fastapi import HTTPException
from backend.services.input_count_controls import validate_input_count_controls
from geometry.layout_engine import expand_plan


@pytest.mark.parametrize("bad", ["-", "NaN", float("inf"), -1, 1.5, True, {}, "1000000000"])
def test_invalid_building_count_cannot_start_calculations(bad):
    with pytest.raises(HTTPException) as error:
        validate_input_count_controls({"edit_controls_v1": {"buildingCount": bad}})
    assert error.value.status_code == 422


def test_zero_count_is_valid_but_does_not_delete_positioned_objects():
    validate_input_count_controls({"edit_controls_v1": {"buildingCount": "0", "parkingCount": "0"}})
    source = {"units": "ft", "lot": {"x": 0, "y": 0, "w": 900, "h": 700}, "site_plan": {"building_count": 0, "parking_count": 0}, "building_width": 100, "building_depth": 100}
    assert expand_plan(source)["meta"]["building_count"] == 0
    source["buildings"] = [{"id": "retained", "name": "Existing drawn building", "x": 100, "y": 100, "w": 50, "d": 50}]
    assert expand_plan(source)["meta"]["building_count"] == 1
