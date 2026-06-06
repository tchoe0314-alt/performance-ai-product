import unittest

from backend.planning.standards_discovery import (
    accept_standards_rules,
    build_standards_review_packet,
    standards_project_evidence_from_acceptance,
)
from backend.planning.standards_package import build_standards_package


def _official_evidence(*, company_usable: bool = True) -> dict:
    packet = build_standards_review_packet(
        city="Austin",
        county="Travis",
        state="Texas",
        extracted_rules=[
            {
                "rule_id": "city_cover",
                "discipline": "utilities",
                "topic": "minimum cover",
                "candidate_value": "Minimum cover shall be 4 feet.",
                "source_url": "https://city.example.gov/manual",
                "source_section": "Section 5.1",
            }
        ],
    )
    accepted = accept_standards_rules(packet, ["city_cover"], accepted_by="u1")
    return standards_project_evidence_from_acceptance(
        accepted,
        review_packet=packet,
        company_standards={"source": "company_manual", "production_usable": company_usable},
    )


class StandardsPackageTests(unittest.TestCase):
    def test_official_accepted_standards_package_is_ready(self) -> None:
        package = build_standards_package(_official_evidence())

        self.assertEqual(package["status"], "ready")
        self.assertTrue(package["production_usable"])
        self.assertFalse(package["review_only"])
        self.assertFalse(package["construction_release_blocked"])
        self.assertTrue(package["accepted_for_qa"])
        self.assertEqual(package["accepted_rule_count"], 1)
        self.assertEqual(package["selected_jurisdiction"]["city"], "Austin")
        self.assertTrue(package["selected_jurisdiction"]["explicitly_selected"])
        self.assertEqual(package["official_source_count"], 1)
        self.assertFalse(package["blockers"])
        self.assertEqual(package["requirements_gate"]["status"], "construction_ready")
        self.assertTrue(package["requirements_gate"]["construction_allowed"])
        self.assertEqual(package["requirements_gate"]["qa_status"], "ready")
        self.assertEqual(package["standards_acceptance_report"]["qa_status"], "ready")
        self.assertTrue(package["selected_standards_source"]["explicitly_selected"])
        self.assertEqual(package["standards_acceptance_report"]["rules"]["accepted_rule_ids"], ["city_cover"])
        self.assertEqual(package["standards_acceptance_report"]["rules"]["inferred_rule_ids"], [])
        self.assertEqual(package["standards_acceptance_report"]["rules"]["missing_rules"], [])
        self.assertIn("not a code-compliance certification", package["standards_acceptance_report"]["compliance_statement"])

    def test_baseline_rules_do_not_clear_package(self) -> None:
        packet = build_standards_review_packet(city="Austin", state="Texas")
        accepted = accept_standards_rules(packet, [packet["candidate_rules"][0]["rule_id"]], accepted_by="u1")
        evidence = standards_project_evidence_from_acceptance(
            accepted,
            review_packet=packet,
            company_standards={"source": "company_manual", "production_usable": True},
        )

        package = build_standards_package(evidence)

        self.assertEqual(package["status"], "blocked")
        fields = {item["field"] for item in package["blockers"]}
        self.assertIn("official_sources", fields)
        self.assertIn("baseline_rules", fields)
        self.assertFalse(package["production_usable"])
        self.assertTrue(package["review_only"])
        self.assertTrue(package["construction_release_blocked"])
        self.assertTrue(package["requirements_gate"]["review_allowed"])
        self.assertFalse(package["requirements_gate"]["construction_allowed"])
        self.assertEqual(package["requirements_gate"]["inferred_rule_ids"], [packet["candidate_rules"][0]["rule_id"]])
        self.assertEqual(package["standards_acceptance_report"]["qa_status"], "blocked")
        self.assertFalse(package["selected_standards_source"]["explicitly_selected"])
        comments = " ".join(item["comment"] for item in package["standards_acceptance_report"]["reviewer_comments"])
        self.assertIn("inferred/search/baseline", comments)

    def test_missing_company_standards_blocks_package(self) -> None:
        package = build_standards_package(_official_evidence(company_usable=False))

        self.assertEqual(package["status"], "blocked")
        fields = {item["field"] for item in package["blockers"]}
        self.assertIn("company_standards", fields)

    def test_missing_jurisdiction_blocks_package(self) -> None:
        evidence = _official_evidence()
        evidence["jurisdiction_standards"] = {"source_urls": ["https://city.example.gov/manual"], "production_usable": True}

        package = build_standards_package(evidence)

        self.assertEqual(package["status"], "blocked")
        fields = {item["field"] for item in package["blockers"]}
        self.assertIn("jurisdiction", fields)

    def test_stale_official_standards_need_review_without_fake_compliance(self) -> None:
        evidence = _official_evidence()
        evidence["standards_acceptance"]["retrieved_date"] = "2000-01-01"
        evidence["design_standards"]["retrieved_date"] = "2000-01-01"
        for rule in evidence["standards_acceptance"]["accepted_rules"]:
            rule["retrieved_date"] = "2000-01-01"
        for rule in evidence["design_standards"]["rules"]:
            rule["retrieved_date"] = "2000-01-01"

        package = build_standards_package(evidence)

        self.assertEqual(package["status"], "needs_review")
        self.assertFalse(package["production_usable"])
        self.assertTrue(package["staleness"]["stale"])
        self.assertIn("standards_stale", {item["field"] for item in package["warnings"]})

    def test_complete_override_history_is_preserved_without_blocking_package(self) -> None:
        evidence = _official_evidence()
        evidence["standards_overrides"] = [
            {
                "rule_id": "city_cover",
                "reason": "User selected a stricter company minimum cover for private-alpha review.",
                "accepted_by": "u1",
                "accepted_date": "2026-06-05",
            }
        ]

        package = build_standards_package(evidence)

        self.assertEqual(package["status"], "ready")
        self.assertEqual(package["override_count"], 1)
        self.assertTrue(package["override_history_complete"])
        self.assertEqual(package["overrides"][0]["rule_id"], "city_cover")

    def test_incomplete_override_history_blocks_package(self) -> None:
        evidence = _official_evidence()
        evidence["standards_overrides"] = [{"rule_id": "city_cover", "reason": "Use stricter company value."}]

        package = build_standards_package(evidence)

        self.assertEqual(package["status"], "blocked")
        self.assertFalse(package["override_history_complete"])
        self.assertIn("override_history", {item["field"] for item in package["blockers"]})

    def test_inferred_jurisdiction_selection_blocks_construction_even_with_official_rule(self) -> None:
        packet = build_standards_review_packet(
            city="Austin",
            state="Texas",
            extracted_rules=[
                {
                    "rule_id": "city_cover",
                    "discipline": "utilities",
                    "topic": "minimum cover",
                    "candidate_value": "Minimum cover shall be 4 feet.",
                    "source_url": "https://city.example.gov/manual",
                    "source_section": "Section 5.1",
                }
            ],
        )
        accepted = accept_standards_rules(packet, ["city_cover"], accepted_by="u1")
        evidence = {
            "standards_acceptance": accepted,
            "design_standards": {
                "rules": accepted["accepted_rules"],
                "source_urls": accepted["source_urls"],
                "production_validation": accepted["production_validation"],
                "production_usable": True,
            },
            "standards_review_packet": packet,
            "company_standards": {"source": "company_manual", "production_usable": True},
        }

        package = build_standards_package(evidence)

        self.assertEqual(package["status"], "blocked")
        self.assertEqual(package["selected_jurisdiction"]["selection_status"], "inferred_from_review_packet")
        self.assertIn("jurisdiction_selection", {item["field"] for item in package["blockers"]})
        self.assertTrue(package["construction_release_blocked"])
        self.assertFalse(package["requirements_gate"]["construction_allowed"])
        self.assertEqual(package["requirements_gate"]["status"], "construction_blocked")
        self.assertEqual(package["standards_acceptance_report"]["qa_status"], "blocked")
        self.assertTrue(package["selected_standards_source"]["explicitly_selected"])
        comments = " ".join(item["comment"] for item in package["standards_acceptance_report"]["reviewer_comments"])
        self.assertIn("Jurisdiction/provider selection", comments)

    def test_missing_inputs_are_reported_for_unselected_empty_package(self) -> None:
        package = build_standards_package({})

        fields = {item["field"] for item in package["requirements_gate"]["missing_inputs"]}
        self.assertEqual(package["status"], "blocked")
        self.assertTrue(package["construction_release_blocked"])
        self.assertIn("accepted_rules", fields)
        self.assertIn("official_sources", fields)
        self.assertIn("jurisdiction", fields)
        self.assertIn("company_standards", fields)
        self.assertEqual(package["standards_acceptance_report"]["qa_status"], "blocked")
        self.assertEqual(package["standards_acceptance_report"]["rules"]["accepted"], [])
        missing_rule_keys = {item["rule_key"] for item in package["standards_acceptance_report"]["rules"]["missing_rules"]}
        self.assertIn("accepted_rules", missing_rule_keys)
        comments = " ".join(item["comment"] for item in package["standards_acceptance_report"]["reviewer_comments"])
        self.assertIn("No user-accepted standards rules", comments)
        self.assertIn("No accepted official HTTPS standards source", comments)


if __name__ == "__main__":
    unittest.main()
