from backend.planning.core_stage_runners import (
    _building_actions_viable,
    _layout_overlap_issues,
)


def _rectangle(layer: str, x: float, y: float, width: float, height: float) -> dict:
    return {
        "task": "rectangle",
        "layer": layer,
        "origin": [x, y],
        "width": width,
        "height": height,
    }


def test_exact_gen01_building_and_parking_are_separate() -> None:
    actions = [
        _rectangle("BUILDING", 372, 88, 180, 80),
        _rectangle("PARKING", 96, 72, 252, 112),
    ]
    assert _layout_overlap_issues(actions) == []


def test_original_gen01_overlap_remains_a_hard_failure() -> None:
    actions = [
        _rectangle("BUILDING", 216, 88, 180, 80),
        _rectangle("PARKING", 96, 72, 252, 112),
    ]
    assert _layout_overlap_issues(actions) == [
        "Parking overlaps or crowds building footprints."
    ]


def test_gen01_building_must_remain_inside_the_parcel() -> None:
    representative = [_rectangle("BUILDING", 292, 66, 170, 14_400 / 170)]
    assert _building_actions_viable(
        representative,
        lot_x=0,
        lot_y=0,
        lot_w=500,
        lot_h=300,
    )

    forced_tight = [_rectangle("BUILDING", 148.8, 39.6, 81.6, 14_400 / 81.6)]
    assert not _building_actions_viable(
        forced_tight,
        lot_x=0,
        lot_y=0,
        lot_w=240,
        lot_h=180,
    )
