import unittest

from backend.application.standards_workflows import (
    accept_standards_response,
    discover_standards_response,
    standards_review_packet_response,
)


class ApplicationStandardsWorkflowsTests(unittest.TestCase):
    def test_discover_and_accept_standards_workflow(self) -> None:
        discovery = discover_standards_response(city="Austin", state="Texas")
        packet = standards_review_packet_response(city="Austin", state="Texas")
        first_rule = packet["candidate_rules"][0]["rule_id"]
        accepted = accept_standards_response(review_packet=packet, accepted_rule_ids=[first_rule])

        self.assertTrue(discovery["success"])
        self.assertTrue(packet["candidate_rules"])
        self.assertTrue(accepted["success"])
        self.assertFalse(accepted["design_standards"]["production_usable"])
        self.assertTrue(accepted["design_standards"]["accepted_for_qa"])
        self.assertTrue(accepted["design_standards"]["production_validation"]["blockers"])
        self.assertIn("jurisdiction_standards", accepted)
        self.assertEqual(accepted["jurisdiction_standards"]["city"], "Austin")

    def test_official_accepted_standards_return_construction_evidence_fields(self) -> None:
        packet = standards_review_packet_response(
            city="Austin",
            state="Texas",
            extracted_rules=[
                {
                    "rule_id": "austin_cover",
                    "discipline": "utilities",
                    "topic": "Minimum utility cover",
                    "candidate_value": "Minimum utility cover shall be 3 feet.",
                    "source_url": "https://www.austintexas.gov/department/engineering-standards",
                    "source_section": "Utility Standards 2.1",
                }
            ],
        )

        accepted = accept_standards_response(
            review_packet=packet,
            accepted_rule_ids=["austin_cover"],
            company_standards={"source": "company_manual", "cad_layers": "CIVORA", "production_usable": True},
        )

        self.assertTrue(accepted["success"])
        self.assertTrue(accepted["production_usable"])
        self.assertTrue(accepted["design_standards"]["production_usable"])
        self.assertTrue(accepted["jurisdiction_standards"]["production_usable"])
        self.assertEqual(accepted["standards_acceptance"]["accepted_rules"][0]["accepted_by"], "user")
        self.assertEqual(accepted["company_standards"]["cad_layers"], "CIVORA")
        self.assertIn("official rules", accepted["truth_label"])


if __name__ == "__main__":
    unittest.main()
