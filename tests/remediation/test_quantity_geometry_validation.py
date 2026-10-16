import pytest
from engines.quantity_engine import compute_plan_quantities


@pytest.mark.parametrize("action", [
    {"task": "rectangle", "width": -1, "height": 10},
    {"task": "rectangle", "width": float("nan"), "height": 10},
    {"task": "rectangle", "width": float("inf"), "height": 10},
    {"task": "rectangle", "width": True, "height": 10},
    {"task": "rectangle", "height": 10},
    {"task": "circle", "radius": -1},
    {"task": "circle", "radius": float("nan")},
    {"task": "circle", "radius": float("inf")},
    {"task": "circle", "radius": "invalid"},
    {"task": "polyline", "points": [[0, 0], ["invalid", 10]]},
    {"task": "polyline", "points": [[0, 0], [float("nan"), 10]]},
    {"task": "polyline", "points": [[0, 0], [True, 10]]},
    {"task": "polyline", "points": [[0, 0], [1]]},
])
def test_invalid_geometry_never_publishes_successful_totals(action):
    action = {**action, "layer": "BUILDING", "canonical_source_id": "invalid",
              "canonical_source_type": "building"}
    result = compute_plan_quantities({"units": "ft", "actions": [action]})
    assert result.success is False
    assert result.totals == {}


def test_overflowing_finite_dimensions_are_not_valid_quantity_results():
    result = compute_plan_quantities({"units": "ft", "actions": [{
        "task": "rectangle", "layer": "BUILDING", "width": 1e200, "height": 1e200,
        "canonical_source_id": "huge", "canonical_source_type": "building",
    }]})
    assert result.success is False
    assert result.totals == {}


def test_individually_finite_areas_cannot_overflow_the_takeoff_total():
    actions = [{"task": "rectangle", "layer": "BUILDING", "width": 1e154, "height": 1e154,
        "canonical_source_id": str(index), "canonical_source_type": "building"} for index in range(2)]
    result = compute_plan_quantities({"units": "ft", "actions": actions})
    assert result.success is False
    assert result.totals == {}
