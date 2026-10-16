import pytest
from engines.quantity_engine import compute_plan_quantities


@pytest.mark.parametrize("stage, metric", [("storm_pipes", "pipe_length_ft"), ("utilities", "utility_length_ft")])
@pytest.mark.parametrize("segment, expected", [
    ({"length_ft": 0, "path": [[0, 0], [100, 0]]}, 0),
    ({"length_ft": 10, "units": "m"}, 10),
    ({"units": "m", "path": [[0, 0], [3.048, 0]]}, 10),
    ({"units": "ft", "path": [[0, 0], [10, 0]]}, 10),
])
def test_route_unit_contract_and_explicit_zero(stage, metric, segment, expected):
    result = compute_plan_quantities({"units": "m", "actions": [],
        "meta": {stage: {"segments": [{"id": "segment", **segment}]}}})
    assert result.success
    assert result.totals[metric] == pytest.approx(expected, abs=0.001)


@pytest.mark.parametrize("stage", ["storm_pipes", "utilities"])
@pytest.mark.parametrize("segment", [
    {"path": [[0, 0], [3.048, 0]]},
    {"units": "degrees", "path": [[0, 0], [1, 0]]},
    {"length_ft": -1}, {"length_ft": float("nan")}, {"length_ft": True},
    {"units": "m", "path": [[0, 0], [float("inf"), 0]]},
    {"units": "m", "path": [[0, 0], ["invalid", 0]]},
])
def test_ambiguous_or_invalid_route_length_fails_without_partial_totals(stage, segment):
    result = compute_plan_quantities({"units": "m", "actions": [],
        "meta": {stage: {"segments": [{"id": "segment", **segment}]}}})
    assert result.success is False
    assert result.totals == {}


@pytest.mark.parametrize("stage, metric, layer", [
    ("storm_pipes", "pipe_length_ft", "PIPE"),
    ("utilities", "utility_length_ft", "UTILITY"),
])
def test_explicit_zero_is_not_replaced_by_drawing_proxy(stage, metric, layer):
    result = compute_plan_quantities({"units": "ft", "actions": [{
        "task": "polyline", "layer": layer, "points": [[0, 0], [100, 0]],
        "canonical_source_id": "segment", "canonical_source_type": "pipe",
    }], "meta": {stage: {"segments": [{"id": "segment", "length_ft": 0}]}}})
    assert result.success
    assert result.totals[metric] == 0
