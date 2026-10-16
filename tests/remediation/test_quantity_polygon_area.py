"""Independent planar takeoff oracles, not bounding-box proxies."""
import pytest

from engines.quantity_engine import compute_plan_quantities


@pytest.mark.parametrize("points, expected", [
    ([[0, 0], [10, 0], [0, 10]], 50),
    ([[0, 0], [10, 0], [10, 2], [2, 2], [2, 10], [0, 10]], 36),
    ([[0, 5], [5, 10], [10, 5], [5, 0]], 50),
    ([[1000000, -1000000], [1000010, -1000000], [1000000, -999990]], 50),
])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("closed", [False, True])
def test_polygon_takeoff_uses_enclosed_area(points, expected, reverse, closed):
    points = list(reversed(points)) if reverse else list(points)
    if closed:
        points.append(points[0])
    result = compute_plan_quantities({"units": "ft", "actions": [{
        "task": "polygon", "layer": "BUILDING", "points": points,
        "canonical_source_id": "building-1", "canonical_source_type": "building",
    }]})
    assert result.success
    assert result.totals["building_area_sf"] == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize("points", [
    [[0, 0], [10, 10], [0, 10], [10, 0]],
    [[0, 0], [1, 1], [2, 2]],
    [[0, 0], [1, 1]],
    [[0, 0], [10, 0], [0, float("nan")]],
    [[0, 0], [10, 0], [0, float("inf")]],
    [[0, 0], [10, 0], [0, "invalid"]],
    [[0, 0], [10, 0], [False, 10]],
])
def test_invalid_polygon_cannot_return_successful_takeoff(points):
    result = compute_plan_quantities({"units": "ft", "actions": [{
        "task": "polygon", "layer": "BUILDING", "points": points,
        "canonical_source_id": "invalid", "canonical_source_type": "building",
    }]})
    assert result.success is False
    assert result.totals == {}
    assert "polygon" in result.message.lower()
