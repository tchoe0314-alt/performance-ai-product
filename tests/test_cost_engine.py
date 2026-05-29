import unittest

import planner
from backend.planning.engine_readiness import evaluate_engine_readiness
from engines.cost_engine import compute_cost_estimate, normalize_unit_price_book, unit_price_book_from_csv


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
                    "location": "Austin, TX",
                    "effective_date": "2026-05-01",
                    "approved_by": "Estimator",
                    "approval_date": "2026-05-02",
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
        self.assertTrue(result.explain["pricing"]["production_validation"]["success"])
        reference = result.explain["quantity_model_reference"]
        self.assertTrue(reference["quantity_traceability_complete"])
        self.assertTrue(reference["quantity_model_hash"])
        self.assertEqual(reference["priced_quantity_metrics"], ["pipe_length_ft"])

    def test_cost_engine_does_not_trust_claimed_production_book_without_approval_metadata(self) -> None:
        result = compute_cost_estimate(
            {
                "meta": {
                    "cost_pricing": {
                        "source": "company_2026_bid_book",
                        "production_usable": True,
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
        )

        self.assertTrue(result.success)
        self.assertFalse(result.totals["production_usable"])
        self.assertFalse(result.explain["pricing"]["production_validation"]["success"])
        self.assertIn("Attached unit-price book is not production-usable", result.assumptions[0])

    def test_cost_engine_blocks_production_when_price_book_misses_positive_quantity_metric(self) -> None:
        result = compute_cost_estimate(
            {
                "meta": {
                    "cost_pricing": {
                        "source": "company_2026_bid_book",
                        "location": "Austin, TX",
                        "effective_date": "2026-05-01",
                        "approved_by": "Estimator",
                        "approval_date": "2026-05-02",
                        "unit_prices": {
                            "pipe_length_ft": {"item": "RCP storm pipe", "category": "storm", "unit": "ft", "unit_cost": 100.0}
                        },
                    },
                    "quantities": {
                        "success": True,
                        "totals": {"pipe_length_ft": 50.0, "parking_area_sf": 1000.0},
                        "explain": {
                            "quantity_audit": {
                                "pipe_length_ft": {"source_object_ids": ["P-1"]},
                                "parking_area_sf": {"source_object_ids": ["PK-1"]},
                            }
                        },
                    },
                }
            }
        )

        self.assertTrue(result.success)
        self.assertFalse(result.totals["production_usable"])
        self.assertIn("parking_area_sf", result.explain["pricing_coverage_gaps"])
        parking = next(item for item in result.line_items if item["metric"] == "parking_area_sf")
        self.assertFalse(parking["production_price"])

    def test_unit_price_book_from_csv_normalizes_and_validates(self) -> None:
        price_book = unit_price_book_from_csv(
            "metric,item,category,unit,unit_cost,bid_item_id\npipe_length_ft,RCP storm pipe,storm,ft,125,ST-01\n",
            source="company_bid_book",
            location="Austin, TX",
            effective_date="2026-05-01",
            approved_by="Estimator",
            approval_date="2026-05-02",
            contingency_pct=8,
        )

        self.assertTrue(price_book["production_usable"])
        self.assertTrue(price_book["production_validation"]["success"])
        self.assertEqual(price_book["unit_prices"]["pipe_length_ft"]["source_item_id"], "ST-01")
        self.assertEqual(price_book["contingency_pct"], 8.0)

    def test_unit_price_book_validation_blocks_missing_required_metadata(self) -> None:
        price_book = normalize_unit_price_book(
            {"unit_prices": {"pipe_length_ft": {"item": "Pipe", "unit": "ft", "unit_cost": 100.0}}}
        )

        fields = {item["field"] for item in price_book["production_validation"]["blockers"]}

        self.assertFalse(price_book["production_usable"])
        self.assertIn("source", fields)
        self.assertIn("location", fields)
        self.assertIn("approved_by", fields)

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

    def test_cost_engine_requires_explicit_successful_quantity_model(self) -> None:
        result = compute_cost_estimate(
            {
                "meta": {
                    "quantities": {
                        "totals": {"pipe_length_ft": 50.0},
                        "explain": {"quantity_audit": {"pipe_length_ft": {"source_object_ids": ["P-1"]}}},
                    }
                }
            }
        )

        self.assertFalse(result.success)
        self.assertFalse(result.totals["production_usable"])
        self.assertIn("Quantity engine is not explicitly production-successful", result.warnings[0])
        self.assertIsNone(result.explain["quantity_model_reference"]["quantity_success"])

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
                        "explain": {"pricing": {"production_usable": False}, "trace_gaps": {}, "pricing_coverage_gaps": {}},
                    },
                }
            }
        )

        quantity = readiness["engines"]["quantity"]
        self.assertIn("pricing_source", {item["field"] for item in quantity["production_blockers"]})

    def test_quantity_engine_readiness_reports_price_book_coverage_gaps(self) -> None:
        readiness = evaluate_engine_readiness(
            {
                "meta": {
                    "quantities": {
                        "success": True,
                        "totals": {"parking_area_sf": 1000.0},
                        "explain": {
                            "meta_summary": {"quantity_traceability_complete": True},
                            "trace_gaps": {},
                        },
                    },
                    "cost_estimate": {
                        "success": True,
                        "explain": {
                            "pricing": {"production_usable": True},
                            "trace_gaps": {},
                            "pricing_coverage_gaps": {"parking_area_sf": {"quantity": 1000.0}},
                        },
                    },
                }
            }
        )

        quantity = readiness["engines"]["quantity"]
        self.assertIn("pricing_coverage", {item["field"] for item in quantity["production_blockers"]})


if __name__ == "__main__":
    unittest.main()
