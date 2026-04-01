import unittest

from geometry.layout_engine import generate_smart_layout


class LayoutEngineParkingFitTest(unittest.TestCase):
    def test_front_parking_layout_can_fit_explicit_target_on_standard_pad(self) -> None:
        layout = generate_smart_layout(
            lot={"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
            setback=10.0,
            site_type="commercial_pad",
            layout_strategy="front_parking",
            street_edge="bottom",
            parking_count=24,
        )

        self.assertGreaterEqual(layout.get("parking_count", 0), 24)
        self.assertGreaterEqual(layout["parking"]["w"], 100.0)
        self.assertGreaterEqual(layout["parking"]["h"], 60.0)


if __name__ == "__main__":
    unittest.main()
