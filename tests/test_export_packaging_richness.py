import unittest

from planner import build_plan


class ExportPackagingRichnessTest(unittest.TestCase):
    def test_manual_mode_packages_canonical_engineering_layers_for_export(self) -> None:
        plan = build_plan(
            {
                "project_name": "Export Richness Test",
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

        layer_counts = {}
        for action in plan.get("actions") or []:
            layer = str(action.get("layer") or "").upper()
            layer_counts[layer] = layer_counts.get(layer, 0) + 1

        self.assertGreater(layer_counts.get("PIPE", 0), 0)
        self.assertGreater(layer_counts.get("STRUCTURE", 0), 0)
        self.assertGreater(layer_counts.get("UTILITY", 0), 0)
        self.assertGreater(layer_counts.get("BASIN_BOUNDARY", 0), 0)

    def test_sanitary_request_packages_real_san_layer_from_canonical_state(self) -> None:
        plan = build_plan(
            {
                "project_name": "Export Sanitary Richness Test",
                "units": "ft",
                "mode": "site_plan",
                "project_type": "commercial_pad",
                "site_type": "commercial_pad",
                "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
                "setback": 10.0,
                "street_edge": "bottom",
                "layout_strategy": "front_parking",
                "site_plan": {"parking_count": 24},
                "deliverables": ["sanitary_plan"],
                "meta": {"input_mode": "manual", "source_input_mode": "manual", "manual_mode": True},
            }
        )

        layer_counts = {}
        for action in plan.get("actions") or []:
            layer = str(action.get("layer") or "").upper()
            layer_counts[layer] = layer_counts.get(layer, 0) + 1

        self.assertGreater(layer_counts.get("SAN", 0), 0)


if __name__ == "__main__":
    unittest.main()
