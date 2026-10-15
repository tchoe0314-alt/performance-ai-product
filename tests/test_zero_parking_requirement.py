import pytest
from geometry.layout_engine import _explicit_parking_count, _parking_count_from_program, _infer_parking_from_legacy, generate_smart_layout, _generic_render_label


@pytest.mark.parametrize("raw", [0, 0.0, "0", "0.0"])
def test_zero_is_an_explicit_requirement_not_unknown(raw):
    assert _explicit_parking_count(raw) == 0
    assert _parking_count_from_program({"x": 0, "y": 0, "w": 100, "h": 100}, "commercial_pad", "medium", _explicit_parking_count(raw)) == 0


@pytest.mark.parametrize("raw", [None, "", " ", -1, "-1", 1.5, True, float("nan"), float("inf")])
def test_invalid_or_absent_count_does_not_become_zero(raw):
    assert _explicit_parking_count(raw) is None


def test_zero_does_not_infer_parking_from_building_geometry():
    assert _infer_parking_from_legacy({"site_plan": {"parking_count": 0}}, {"x": 0, "y": 0, "w": 900, "h": 700}, [{"x": 100, "y": 100, "w": 100, "d": 100}]) == []
    layout = generate_smart_layout(lot={"x": 0, "y": 0, "w": 900, "h": 700}, setback=20, building_width=100, building_depth=100, parking_count=0)
    assert layout["parking_count"] == 0


def test_customer_labels_are_preserved_while_generic_internal_labels_remain_hidden():
    assert _generic_render_label("Office A", "BUILDING") == "Office A"
    assert _generic_render_label("PARK-1", "PARKING") is None
