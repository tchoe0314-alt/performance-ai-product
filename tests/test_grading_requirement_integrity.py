import pytest
from backend.planning.grading_requirements import requested_grading_ratio


@pytest.mark.parametrize("field", ["min_slope_pct", "max_parking_slope_pct", "max_road_grade_pct", "max_ada_cross_slope_pct"])
def test_explicit_zero_and_tight_limits_are_never_replaced_with_looser_defaults(field):
    assert requested_grading_ratio({field: 0}, field, .05) == 0
    assert requested_grading_ratio({field: .1}, field, .05) == .001
    assert requested_grading_ratio({}, field, .05) == .05
    assert requested_grading_ratio({field: ""}, field, .05) == .05


@pytest.mark.parametrize("raw", [True, -1, "-1", "bad", float("nan"), float("inf"), [], {}])
def test_invalid_grading_constraints_fail_instead_of_becoming_defaults(raw):
    with pytest.raises(ValueError):
        requested_grading_ratio({"max_road_grade_pct": raw}, "max_road_grade_pct", .10)
