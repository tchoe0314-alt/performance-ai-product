import unittest

from backend.planning.standards_discovery import (
    accept_standards_rules,
    build_standards_review_packet,
    discover_standards_sources,
    extract_rule_candidates_from_text,
    fetch_and_extract_rule_candidates,
    standards_pack_from_acceptance,
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

    def test_acceptance_builds_production_usable_standards_pack(self) -> None:
        packet = build_standards_review_packet()
        first_rule = packet["candidate_rules"][0]["rule_id"]

        accepted = accept_standards_rules(packet, [first_rule], edits={first_rule: {"candidate_value": "Accepted edited value"}})
        pack = standards_pack_from_acceptance(accepted)

        self.assertTrue(accepted["production_usable"])
        self.assertEqual(accepted["accepted_rule_count"], 1)
        self.assertEqual(pack["rules"][0]["candidate_value"], "Accepted edited value")
        self.assertTrue(pack["needs_source_review"])

    def test_civil_readiness_can_use_accepted_standards_without_fake_jurisdiction(self) -> None:
        packet = build_standards_review_packet()
        first_rule = packet["candidate_rules"][0]["rule_id"]
        accepted = accept_standards_rules(packet, [first_rule])

        readiness = civil_design_readiness({"meta": {"standards_acceptance": accepted}})
        standards = readiness["systems"]["standards"]

        self.assertEqual(standards["metrics"]["accepted_rule_count"], 1)
        self.assertFalse(any(item["area"] == "standards" and item["field"] == "design_standards" for item in readiness["production_blockers"]))
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


if __name__ == "__main__":
    unittest.main()
