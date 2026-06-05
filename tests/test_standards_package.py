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
        self.assertTrue(package["accepted_for_qa"])
        self.assertEqual(package["accepted_rule_count"], 1)
        self.assertEqual(package["selected_jurisdiction"]["city"], "Austin")
        self.assertEqual(package["official_source_count"], 1)
        self.assertFalse(package["blockers"])

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


if __name__ == "__main__":
    unittest.main()
