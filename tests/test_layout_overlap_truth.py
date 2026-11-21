from backend.planning.core_stage_runners import _layout_overlap_issues


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
