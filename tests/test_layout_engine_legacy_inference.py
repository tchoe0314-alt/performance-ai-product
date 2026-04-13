import unittest

from geometry.layout_engine import _infer_drive_aisles_from_legacy, _infer_roads_from_legacy


class LayoutEngineLegacyInferenceTests(unittest.TestCase):
    def test_multi_parking_legacy_inference_uses_local_aisles(self) -> None:
        parsed = {"street_edge": "bottom"}
        site_box = {"x": 0.0, "y": 0.0, "w": 500.0, "h": 500.0}
        parking_areas = [
            {"x": 100.0, "y": 220.0, "w": 120.0, "h": 60.0},
            {"x": 260.0, "y": 220.0, "w": 120.0, "h": 60.0},
        ]

        aisles = _infer_drive_aisles_from_legacy(parsed, site_box, parking_areas)

        self.assertEqual(len(aisles), 2)
        self.assertTrue(all(item.get("type") == "parking_aisle" for item in aisles))
        self.assertTrue(all(str(item.get("label", "")).startswith("AISLE-") for item in aisles))

    def test_single_parking_legacy_inference_does_not_create_long_access_drive(self) -> None:
        parsed = {"street_edge": "bottom"}
        site_box = {"x": 0.0, "y": 0.0, "w": 500.0, "h": 500.0}
        parking_areas = [{"x": 160.0, "y": 220.0, "w": 120.0, "h": 60.0}]

        aisles = _infer_drive_aisles_from_legacy(parsed, site_box, parking_areas)

        self.assertEqual(len(aisles), 1)
        self.assertEqual(aisles[0].get("type"), "parking_aisle")
        self.assertEqual(aisles[0].get("label"), "AISLE-1")

    def test_legacy_roads_are_suppressed_when_program_has_parking_areas(self) -> None:
        parsed = {
            "street_edge": "bottom",
            "parking_areas": [{"x": 160.0, "y": 220.0, "w": 120.0, "h": 60.0}],
        }
        site_box = {"x": 0.0, "y": 0.0, "w": 500.0, "h": 500.0}

        roads = _infer_roads_from_legacy(parsed, site_box)

        self.assertEqual(roads, [])


if __name__ == "__main__":
    unittest.main()
