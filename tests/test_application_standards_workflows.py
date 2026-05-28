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


if __name__ == "__main__":
    unittest.main()
