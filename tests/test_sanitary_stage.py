import unittest
from unittest.mock import patch

from planner import build_plan


def _manual_sanitary_payload(**overrides):
    payload = {
        "project_name": "Sanitary Stage Test",
        "units": "ft",
        "mode": "site_plan",
        "project_type": "commercial_pad",
        "site_type": "commercial_pad",
        "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
        "setback": 10.0,
        "street_edge": "bottom",
        "layout_strategy": "front_parking",
        "site_plan": {"building_width": 48.0, "building_depth": 34.0, "parking_count": 24},
        "deliverables": ["sanitary_plan"],
        "meta": {"input_mode": "manual", "source_input_mode": "manual", "manual_mode": True},
    }
    payload.update(overrides)
    return payload


class SanitaryStageTest(unittest.TestCase):
    def test_manual_mode_generates_canonical_sanitary_system(self) -> None:
        plan = build_plan(_manual_sanitary_payload())
        meta = plan.get("meta") or {}
        sanitary = meta.get("sanitary") or {}
        totals = ((meta.get("quantities") or {}).get("totals") or {})
        produced = ((meta.get("deliverables") or {}).get("produced") or [])

        self.assertTrue((meta.get("engineering_status") or {}).get("success"))
        self.assertTrue(sanitary.get("success"))
        self.assertGreater(sanitary.get("route_count") or 0, 0)
        self.assertGreater(sanitary.get("service_count") or 0, 0)
        self.assertGreater(sanitary.get("manhole_count") or 0, 0)
        self.assertIn("sanitary_plan", produced)
        self.assertGreater(totals.get("sanitary_length_ft") or 0, 0)
        self.assertGreater(totals.get("sanitary_main_length_ft") or 0, 0)
        self.assertGreater(totals.get("sanitary_service_count") or 0, 0)

        san_layers = sum(1 for action in plan.get("actions") or [] if str(action.get("layer") or "").upper() == "SAN")
        self.assertGreater(san_layers, 0)

    def test_manual_mode_fails_when_sanitary_is_requested_but_cannot_be_generated(self) -> None:
        with patch("planner._sanitary_building_nodes", return_value=[]):
            plan = build_plan(_manual_sanitary_payload())
        failures = (((plan.get("meta") or {}).get("manual_validation") or {}).get("failures") or [])
        codes = [item.get("code") for item in failures]
        self.assertIn("MANUAL_SANITARY_OUTPUT_MISSING", codes)

    def test_sanitary_plan_is_not_packaged_without_canonical_sanitary_state(self) -> None:
        plan = build_plan(
            {
                "project_name": "No Sanitary Request",
                "units": "ft",
                "mode": "site_plan",
                "project_type": "commercial_pad",
                "site_type": "commercial_pad",
                "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
                "setback": 10.0,
                "street_edge": "bottom",
                "layout_strategy": "front_parking",
                "site_plan": {"parking_count": 24},
                "meta": {"input_mode": "manual", "source_input_mode": "manual", "manual_mode": True},
            }
        )
        sanitary = ((plan.get("meta") or {}).get("sanitary") or {})
        produced = ((plan.get("meta") or {}).get("deliverables") or {}).get("produced") or []
        self.assertEqual(sanitary, {})
        self.assertNotIn("sanitary_plan", produced)


if __name__ == "__main__":
    unittest.main()
