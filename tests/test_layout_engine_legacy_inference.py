import unittest

from geometry.layout_engine import _build_expanded_plan, _infer_drive_aisles_from_legacy, _infer_roads_from_legacy


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

    def test_expanded_multi_building_plan_drops_schematic_raw_actions(self) -> None:
        plan = _build_expanded_plan(
            {
                "project_type": "mixed_use",
                "lot": {"w": 620.0, "h": 980.0},
                "buildings": [
                    {"name": "MF-1", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "MF-2", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "MF-3", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "Retail", "type": "retail", "width": 70, "depth": 45},
                ],
                "actions": [
                    {"task": "text_note", "layer": "PAVEMENT", "origin": [290, 534], "text": "FRONTAGE ACCESS"},
                    {"task": "polyline", "layer": "ROAD", "points": [[0, 0], [300, 300]]},
                    {"task": "circle", "layer": "FIRE", "center": [10, 10], "radius": 15},
                    {"task": "polyline", "layer": "PIPE", "points": [[220, 520], [310, 430], [410, 380]]},
                ],
            }
        )

        actions = plan["actions"]
        self.assertFalse(any("FRONTAGE" in str(action.get("text") or "").upper() for action in actions))
        self.assertFalse(any(str(action.get("layer") or "").upper() == "ROAD" and str(action.get("task") or "").lower() == "polyline" for action in actions))
        self.assertFalse(any(str(action.get("layer") or "").upper() == "FIRE" and str(action.get("task") or "").lower() == "circle" for action in actions))
        self.assertTrue(any(str(action.get("layer") or "").upper() == "PIPE" for action in actions))


if __name__ == "__main__":
    unittest.main()
