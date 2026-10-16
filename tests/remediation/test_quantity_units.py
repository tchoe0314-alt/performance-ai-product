"""Exact international-foot conversions at the drawing takeoff boundary."""
from copy import deepcopy
import pytest
from engines.quantity_engine import compute_plan_quantities


def plan(units):
    return {"units": units, "actions": [
        {"task": "rectangle", "layer": "SITE", "width": 30.48, "height": 30.48,
         "canonical_source_id": "site", "canonical_source_type": "site"},
        {"task": "rectangle", "layer": "BUILDING", "width": 3.048, "height": 6.096,
         "canonical_source_id": "b", "canonical_source_type": "building"},
        {"task": "polyline", "layer": "ROAD", "points": [[0, 0], [3.048, 0]],
         "canonical_source_id": "r", "canonical_source_type": "road"},
    ]}


@pytest.mark.parametrize("units", ["m", "meter", "meters", "metre", "metres"])
def test_metric_drawing_converts_before_imperial_takeoff(units):
    source = plan(units)
    before = deepcopy(source)
    result = compute_plan_quantities(source)
    assert result.success
    assert result.totals["building_area_sf"] == pytest.approx(200, abs=0.001)
    assert result.totals["lot_area_sf"] == pytest.approx(10000, abs=0.001)
    assert result.totals["road_length_ft"] == pytest.approx(10, abs=0.001)
    assert source == before
    assert result.explain["meta_summary"]["drawing_to_ft"] == pytest.approx(1 / 0.3048)
    assert result.explain["meta_summary"]["quantity_units"]["area"] == "sf"


@pytest.mark.parametrize("units", ["degrees", "pixels", "unknown", None, 123])
def test_explicit_unknown_drawing_units_do_not_produce_imperial_totals(units):
    result = compute_plan_quantities(plan(units))
    assert result.success is False
    assert result.totals == {}
    assert "unit" in result.message.lower()


def test_feet_geometry_is_unchanged_and_explicit_metadata_is_not_double_converted():
    source = plan("ft")
    imperial = compute_plan_quantities(source)
    assert imperial.totals["building_area_sf"] == pytest.approx(18.581, abs=0.001)
    source = plan("m")
    source["meta"] = {"manager_export": {"metrics": {
        "layout_building_area_sf": {"value": 200},
    }}}
    result = compute_plan_quantities(source)
    assert result.totals["building_area_sf"] == pytest.approx(200, abs=0.001)


@pytest.mark.parametrize("action, metric, expected", [
    ({"task": "polygon", "layer": "BUILDING", "points": [[0, 0], [3.048, 0], [0, 3.048]]}, "building_area_sf", 50),
    ({"task": "circle", "layer": "BUILDING", "radius": 3.048}, "building_area_sf", 314.159),
    ({"task": "polyline", "layer": "WALK", "points": [[0, 0], [3.048, 0]]}, "sidewalk_length_ft", 10),
])
def test_metric_shape_types_and_linear_defaults(action, metric, expected):
    action = {**action, "canonical_source_id": "object",
              "canonical_source_type": "sidewalk" if action["layer"] == "WALK" else "building"}
    result = compute_plan_quantities({"units": "m", "actions": [action]})
    assert result.success
    assert result.totals[metric] == pytest.approx(expected, abs=0.001)


def test_missing_legacy_units_are_visible_not_surveyed_or_reinterpreted():
    source = plan("ft")
    del source["units"]
    result = compute_plan_quantities(source)
    assert result.success
    assert result.explain["meta_summary"]["legacy_units_assumed"] is True
