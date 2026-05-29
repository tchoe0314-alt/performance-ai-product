import unittest

from backend.planning.standards_discovery import (
    accept_standards_rules,
    build_standards_review_packet,
    discover_standards_sources,
    extract_rule_candidates_from_text,
    fetch_and_extract_rule_candidates,
    standards_pack_from_acceptance,
    standards_project_evidence_from_acceptance,
    validate_standards_acceptance_for_production,
)
from core.civil_design import civil_design_readiness


class StandardsDiscoveryTests(unittest.TestCase):
    def test_discovery_returns_candidate_sources_not_accepted_rules(self) -> None:
        result = discover_standards_sources(city="Austin", county="Travis", state="Texas")

        self.assertTrue(result["success"])
        self.assertTrue(result["sources"])
        self.assertIn("candidate", {item["status"].split("_")[0] for item in result["sources"] if item["source_id"] != "civora_us_baseline"})
        self.assertIn("must not apply", result["truth_label"])

    def test_review_packet_requires_acceptance(self) -> None:
        packet = build_standards_review_packet(city="Austin", state="Texas")

        self.assertTrue(packet["candidate_rules"])
        self.assertEqual(packet["accepted_rules"], [])
        self.assertIn("require user acceptance", packet["truth_label"])

    def test_acceptance_builds_concept_pack_until_official_source_is_accepted(self) -> None:
        packet = build_standards_review_packet()
        first_rule = packet["candidate_rules"][0]["rule_id"]

        accepted = accept_standards_rules(packet, [first_rule], edits={first_rule: {"candidate_value": "Accepted edited value"}})
        pack = standards_pack_from_acceptance(accepted)

        self.assertTrue(accepted["accepted_for_qa"])
        self.assertFalse(accepted["production_usable"])
        self.assertEqual(accepted["accepted_rule_count"], 1)
        self.assertEqual(pack["rules"][0]["candidate_value"], "Accepted edited value")
        self.assertTrue(pack["needs_source_review"])
        self.assertFalse(pack["production_validation"]["production_usable"])

    def test_civil_readiness_can_use_accepted_standards_without_fake_jurisdiction(self) -> None:
        packet = build_standards_review_packet()
        first_rule = packet["candidate_rules"][0]["rule_id"]
        accepted = accept_standards_rules(packet, [first_rule])

        readiness = civil_design_readiness({"meta": {"standards_acceptance": accepted}})
        standards = readiness["systems"]["standards"]

        self.assertEqual(standards["metrics"]["accepted_rule_count"], 1)
        fields = {(item["area"], item["field"]) for item in readiness["production_blockers"]}
        self.assertNotIn(("standards", "design_standards"), fields)
        self.assertIn(("standards", "official_sources"), fields)
        self.assertFalse(readiness["production_ready"])

    def test_extract_rule_candidates_from_text_requires_acceptance(self) -> None:
        candidates = extract_rule_candidates_from_text(
            "Accessible route cross slope shall not exceed 2 percent. Minimum utility cover shall be 3 feet. "
            "Hydrant spacing shall not exceed 300 feet. Required fire flow is 1500 gpm. "
            "Residual pressure shall be 20 psi. Manhole spacing shall not exceed 400 feet.",
            source_id="test_city",
            source_url="https://example.gov/standards",
        )

        topics = {item["topic"] for item in candidates}
        self.assertGreaterEqual(len(candidates), 6)
        self.assertIn("hydrant spacing", topics)
        self.assertIn("fire flow", topics)
        self.assertIn("residual pressure", topics)
        self.assertIn("manhole spacing", topics)
        self.assertTrue(all(item["needs_human_confirmation"] for item in candidates))

    def test_fetch_and_extract_rule_candidates_from_html(self) -> None:
        class Response:
            headers = {"content-type": "text/html"}
            text = "<html><body>Maximum road grade shall be 8 percent.</body></html>"

            def raise_for_status(self):
                return None

        class Session:
            def get(self, url, timeout=None):
                return Response()

        result = fetch_and_extract_rule_candidates("https://example.gov/manual", source_id="manual", session=Session())

        self.assertTrue(result["success"])
        self.assertEqual(result["candidate_count"], 1)
        self.assertIn("candidates only", result["truth_label"])

    def test_standards_production_validation_requires_official_source(self) -> None:
        packet = build_standards_review_packet(
            extracted_rules=[
                {
                    "rule_id": "city_cover",
                    "discipline": "utilities",
                    "topic": "minimum cover",
                    "candidate_value": "Minimum cover shall be 4 feet.",
                    "source_url": "https://city.example.gov/manual",
                    "source_section": "Section 5.1",
                }
            ]
        )
        accepted = accept_standards_rules(packet, ["city_cover"])
        pack = standards_pack_from_acceptance(accepted)

        validation = validate_standards_acceptance_for_production(pack)

        self.assertTrue(validation["production_usable"])
        self.assertEqual(validation["official_source_count"], 1)

    def test_project_standards_evidence_carries_jurisdiction_and_company_profiles(self) -> None:
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
        accepted = accept_standards_rules(packet, ["city_cover"])

        evidence = standards_project_evidence_from_acceptance(
            accepted,
            review_packet=packet,
            company_standards={"source": "company_manual", "production_usable": True},
        )

        self.assertTrue(evidence["production_usable"])
        self.assertEqual(evidence["jurisdiction_standards"]["city"], "Austin")
        self.assertEqual(evidence["jurisdiction_standards"]["state"], "Texas")
        self.assertTrue(evidence["company_standards"]["production_usable"])

    def test_baseline_or_search_sources_are_not_production_authority(self) -> None:
        packet = build_standards_review_packet()
        baseline = packet["candidate_rules"][0]["rule_id"]
        accepted = accept_standards_rules(packet, [baseline])

        validation = validate_standards_acceptance_for_production(accepted)

        self.assertFalse(validation["production_usable"])
        fields = {item["field"] for item in validation["blockers"]}
        self.assertIn("official_sources", fields)
        self.assertIn("baseline_rules", fields)


if __name__ == "__main__":
    unittest.main()
