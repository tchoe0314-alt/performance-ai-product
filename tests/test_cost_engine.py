import unittest

import planner
from backend.planning.engine_readiness import evaluate_engine_readiness
from engines.cost_engine import compute_cost_estimate


class CostEngineTests(unittest.TestCase):
    def test_cost_engine_prices_traceable_quantity_takeoff_with_default_pricing(self) -> None:
        plan = {
            "meta": {
                "quantities": {
                    "success": True,
                    "totals": {"parking_area_sf": 1000.0, "pipe_length_ft": 40.0, "inlet_count": 2},
                    "explain": {
                        "quantity_audit": {
                            "parking_area_sf": {"source_object_ids": ["park-1"]},
                            "pipe_length_ft": {"source_object_ids": ["storm-1"]},
                            "inlet_count": {"source_object_ids": ["inlet-1", "inlet-2"]},
                        }
                    },
                }
            }
        }

        result = compute_cost_estimate(plan)

        self.assertTrue(result.success)
        self.assertEqual(result.totals["direct_cost"], 20900.0)
        self.assertEqual(result.totals["total_cost"], 24035.0)
        self.assertFalse(result.totals["production_usable"])
        self.assertTrue(result.assumptions)
        self.assertEqual(len(result.line_items), 3)

    def test_cost_engine_can_be_production_usable_with_traceable_pricing_book(self) -> None:
        plan = {
            "meta": {
                "cost_pricing": {
                    "source": "company_2026_bid_book",
                    "production_usable": True,
                    "currency": "USD",
                    "contingency_pct": 10,
                    "unit_prices": {
                        "pipe_length_ft": {"item": "RCP storm pipe", "category": "storm", "unit": "ft", "unit_cost": 100.0}
                    },
                },
                "quantities": {
                    "success": True,
                    "totals": {"pipe_length_ft": 50.0},
                    "explain": {"quantity_audit": {"pipe_length_ft": {"source_object_ids": ["P-1"]}}},
                },
            }
        }

        result = compute_cost_estimate(plan)

        self.assertTrue(result.success)
        self.assertTrue(result.totals["production_usable"])
        self.assertEqual(result.totals["direct_cost"], 5000.0)
        self.assertEqual(result.totals["total_cost"], 5500.0)
        self.assertFalse(result.assumptions)

    def test_cost_engine_blocks_untraceable_priced_quantities(self) -> None:
        result = compute_cost_estimate(
            {
                "meta": {
                    "quantities": {
                        "success": True,
                        "totals": {"road_area_sf": 1000.0},
                        "explain": {"quantity_audit": {"road_area_sf": {"source_object_ids": []}}},
                    }
                }
            }
        )

        self.assertFalse(result.success)
        self.assertIn("road_area_sf", result.explain["trace_gaps"])

    def test_build_plan_attaches_cost_estimate(self) -> None:
        plan = planner.build_plan(
            {
                "project_name": "Cost Smoke",
                "units": "ft",
                "mode": "site_plan",
                "lot": {"x": 0.0, "y": 0.0, "w": 120.0, "h": 100.0},
                "site_plan": {"building_width": 40.0, "building_depth": 30.0, "parking_count": 12},
            }
        )

        cost = plan["meta"]["cost_estimate"]

        self.assertIn("totals", cost)
        self.assertIn("line_items", cost)
        self.assertIn("explain", cost)

    def test_quantity_engine_readiness_reports_cost_pricing_blocker(self) -> None:
        readiness = evaluate_engine_readiness(
            {
                "meta": {
                    "quantities": {
                        "success": True,
                        "totals": {"pipe_length_ft": 20.0},
                        "explain": {
                            "meta_summary": {"quantity_traceability_complete": True},
                            "trace_gaps": {},
                        },
                    },
                    "cost_estimate": {
                        "success": True,
                        "explain": {"pricing": {"production_usable": False}, "trace_gaps": {}},
                    },
                }
            }
        )

        quantity = readiness["engines"]["quantity"]
        self.assertIn("pricing_source", {item["field"] for item in quantity["production_blockers"]})


if __name__ == "__main__":
    unittest.main()
