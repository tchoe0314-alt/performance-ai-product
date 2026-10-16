import pytest
from engines.quantity_engine import compute_plan_quantities


@pytest.mark.parametrize("stage", ["storm_pipes", "utilities"])
@pytest.mark.parametrize("summary, stats", [(100, None), (0, None), (10, 100), (-1, None), (float("nan"), None)])
def test_conflicting_route_totals_cannot_be_successful(stage, summary, stats):
    metadata = {"segments": [{"id": "route", "length_ft": 10}], "total_length_ft": summary}
    if stats is not None:
        metadata["stats"] = {"total_length_ft": stats}
    result = compute_plan_quantities({"units": "ft", "actions": [], "meta": {stage: metadata}})
    assert result.success is False
    assert result.totals == {}


@pytest.mark.parametrize("stage, metric", [("storm_pipes", "pipe_length_ft"), ("utilities", "utility_length_ft")])
def test_consistent_route_totals_use_existing_three_decimal_precision(stage, metric):
    result = compute_plan_quantities({"units": "ft", "actions": [], "meta": {stage: {
        "segments": [{"id": "a", "length_ft": 0.1}, {"id": "b", "length_ft": 0.2}],
        "total_length_ft": 0.3, "stats": {"total_length_ft": 0.3},
    }}})
    assert result.success
    assert result.totals[metric] == 0.3
