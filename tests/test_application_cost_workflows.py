import unittest

from backend.application.cost_workflows import (
    normalize_unit_price_book_response,
    unit_price_book_from_csv_response,
    validate_unit_price_book_response,
)


class ApplicationCostWorkflowsTests(unittest.TestCase):
    def test_csv_unit_price_book_workflow_returns_production_usable_book(self) -> None:
        response = unit_price_book_from_csv_response(
            csv_text="metric,item,category,unit,unit_cost\npipe_length_ft,RCP storm pipe,storm,ft,120\n",
            source="company_2026_bid_book",
            location="Austin, TX",
            effective_date="2026-05-01",
            approved_by="Estimator",
            approval_date="2026-05-02",
        )

        self.assertTrue(response["success"])
        self.assertTrue(response["validation"]["production_usable"])
        self.assertTrue(response["unit_price_book"]["production_usable"])
        self.assertIn("price_book_hash", response["unit_price_book"])

    def test_json_unit_price_book_workflow_blocks_unapproved_book(self) -> None:
        response = validate_unit_price_book_response(
            {
                "source": "company_2026_bid_book",
                "unit_prices": {
                    "pipe_length_ft": {"item": "RCP storm pipe", "category": "storm", "unit": "ft", "unit_cost": 120.0}
                },
            }
        )

        fields = {item["field"] for item in response["validation"]["blockers"]}

        self.assertFalse(response["success"])
        self.assertIn("location", fields)
        self.assertIn("effective_date", fields)
        self.assertIn("approved_by", fields)

    def test_normalize_response_has_truth_label(self) -> None:
        response = normalize_unit_price_book_response({})

        self.assertTrue(response["success"])
        self.assertFalse(response["unit_price_book"]["production_usable"])
        self.assertIn("production-usable", response["truth_label"])


if __name__ == "__main__":
    unittest.main()
