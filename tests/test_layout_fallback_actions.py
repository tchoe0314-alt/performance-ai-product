import unittest

from backend.planning.core_stage_runners import _layout_fallback_actions


class LayoutFallbackActionsTests(unittest.TestCase):
    def test_layout_fallback_emits_parking_walk_and_fire_layers(self) -> None:
        actions = _layout_fallback_actions(
            [{"name": "BLDG 1", "x": 100.0, "y": 200.0, "w": 120.0, "d": 60.0}],
            lot_x=0.0,
            lot_y=0.0,
            lot_w=500.0,
            lot_h=500.0,
            street_edge="bottom",
            culdesac_count=2,
        )

        layers = [str(action.get("layer", "")).upper() for action in actions]
        self.assertIn("ROAD", layers)
        self.assertIn("FIRE", layers)
        self.assertIn("PARKING", layers)
        self.assertIn("WALK", layers)


if __name__ == "__main__":
    unittest.main()
