import unittest

from backend.planning.standards_discovery import (
    accept_standards_rules,
    build_candidate_rule_report,
    build_standards_source_registry,
    build_standards_review_packet,
    discover_standards_sources,
    extract_rule_candidates_from_text,
    fetch_and_extract_rule_candidates,
    review_candidate_standards,
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
        self.assertIn("source_registry", result)
        self.assertEqual(result["source_registry"]["accepted_source_count"], 0)
        self.assertGreaterEqual(result["source_registry"]["candidate_source_count"], 1)
        self.assertIn("candidate", {item["status"].split("_")[0] for item in result["sources"] if item["source_id"] != "civora_us_baseline"})
        self.assertEqual({item["acceptance_status"] for item in result["source_registry"]["sources"]}, {"candidate"})
        self.assertIn("must not apply", result["truth_label"])

    def test_review_packet_requires_acceptance(self) -> None:
        packet = build_standards_review_packet(city="Austin", state="Texas")

        self.assertTrue(packet["candidate_rules"])
        self.assertEqual(packet["accepted_rules"], [])
        self.assertEqual({item["acceptance_status"] for item in packet["candidate_rules"]}, {"candidate"})
        self.assertEqual(packet["source_registry"]["accepted_source_count"], 0)
        self.assertIn("require user acceptance", packet["truth_label"])

    def test_acceptance_builds_concept_pack_until_official_source_is_accepted(self) -> None:
        packet = build_standards_review_packet()
        first_rule = packet["candidate_rules"][0]["rule_id"]

        accepted = accept_standards_rules(packet, [first_rule], edits={first_rule: {"candidate_value": "Accepted edited value"}})
        pack = standards_pack_from_acceptance(accepted)

        self.assertTrue(accepted["accepted_for_qa"])
        self.assertFalse(accepted["production_usable"])
        self.assertEqual(accepted["accepted_rule_count"], 1)
        self.assertEqual(accepted["accepted_rules"][0]["acceptance_status"], "accepted")
        self.assertEqual(accepted["rejected_rules"][0]["acceptance_status"], "unaccepted")
        self.assertEqual(pack["rules"][0]["candidate_value"], "Accepted edited value")
        self.assertTrue(pack["needs_source_review"])
        self.assertFalse(pack["production_validation"]["production_usable"])

    def test_source_registry_keeps_official_candidates_unaccepted_by_default(self) -> None:
        registry = build_standards_source_registry(
            jurisdiction={"city": "Austin", "state": "Texas"},
            sources=[
                {
                    "source_id": "austin_manual",
                    "agency": "Austin Public Works",
                    "discipline": "utilities",
                    "source_url": "https://www.austintexas.gov/department/engineering-standards",
                    "document_title": "Engineering Standards",
                    "version_or_effective_date": "2026-01-01",
                    "retrieved_at": "2026-06-05",
                    "source_type": "official_candidate",
                }
            ],
            candidate_rules=[{"rule_id": "austin_cover", "source_id": "austin_manual"}],
        )

        source = registry["sources"][0]

        self.assertEqual(registry["accepted_source_count"], 0)
        self.assertEqual(source["acceptance_status"], "candidate")
        self.assertEqual(source["candidate_rule_ids"], ["austin_cover"])
        self.assertEqual(source["source_type"], "official_candidate")
        self.assertFalse(source["stale"])

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
        self.assertEqual({item["acceptance_status"] for item in candidates}, {"candidate"})
        self.assertEqual({item["source_type"] for item in candidates}, {"scraped_candidate"})
        cover = next(item for item in candidates if item["topic"] == "minimum cover")
        self.assertEqual(cover["extracted_text_or_summary"], cover["candidate_value"])
        self.assertTrue(cover["requires_user_acceptance"])
        self.assertEqual(cover["numeric_thresholds"][0]["value"], 3.0)
        self.assertEqual(cover["numeric_thresholds"][0]["comparator"], "min")

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
        self.assertEqual(result["source_registry"]["accepted_source_count"], 0)
        self.assertEqual(result["candidate_rules"][0]["acceptance_status"], "candidate")
        self.assertIn("roadway", result["candidate_rule_report"]["by_discipline"])
        self.assertIn("candidates only", result["truth_label"])

    def test_candidate_rule_report_groups_rules_and_flags_duplicates(self) -> None:
        registry = build_standards_source_registry(
            sources=[
                {
                    "source_id": "city_manual",
                    "source_url": "https://city.example.gov/manual",
                    "document_title": "City Manual",
                    "version_or_effective_date": "2026-01-01",
                    "retrieved_at": "2026-06-05",
                    "source_type": "official_candidate",
                }
            ],
            candidate_rules=[
                {"rule_id": "cover_a", "source_id": "city_manual"},
                {"rule_id": "cover_b", "source_id": "city_manual"},
            ],
        )

        report = build_candidate_rule_report(
            [
                {
                    "rule_id": "cover_a",
                    "discipline": "utilities",
                    "topic": "minimum cover",
                    "candidate_value": "Minimum cover shall be 4 feet.",
                    "source_id": "city_manual",
                    "source_url": "https://city.example.gov/manual",
                },
                {
                    "rule_id": "cover_b",
                    "discipline": "utilities",
                    "topic": "minimum cover",
                    "candidate_value": "Minimum cover shall be 4 feet.",
                    "source_id": "city_manual",
                    "source_url": "https://city.example.gov/manual",
                },
            ],
            source_registry=registry,
        )

        self.assertEqual(report["version"], "standards_candidate_rule_report_v1")
        self.assertEqual(report["accepted_rule_count"], 0)
        self.assertFalse(report["production_usable"])
        self.assertIn("utilities", report["by_discipline"])
        self.assertEqual(len(report["by_source"]["city_manual"]), 2)
        self.assertEqual(report["duplicate_rule_ids"], ["cover_a", "cover_b"])
        self.assertTrue(all(rule["requires_user_acceptance"] for rule in report["candidate_rules"]))
        self.assertEqual(report["candidate_rules"][0]["source_document_title"], "City Manual")
        self.assertEqual(report["candidate_rules"][0]["source_version_or_effective_date"], "2026-01-01")

    def test_stale_source_candidates_are_marked_needs_review(self) -> None:
        registry = build_standards_source_registry(
            sources=[
                {
                    "source_id": "old_manual",
                    "source_url": "https://city.example.gov/manual",
                    "document_title": "Old City Manual",
                    "retrieved_at": "2000-01-01",
                    "source_type": "official_candidate",
                }
            ],
            candidate_rules=[{"rule_id": "old_cover", "source_id": "old_manual"}],
        )

        report = build_candidate_rule_report(
            [
                {
                    "rule_id": "old_cover",
                    "discipline": "utilities",
                    "topic": "minimum cover",
                    "candidate_value": "Minimum cover shall be 4 feet.",
                    "source_id": "old_manual",
                    "source_url": "https://city.example.gov/manual",
                }
            ],
            source_registry=registry,
        )

        rule = report["candidate_rules"][0]

        self.assertTrue(rule["needs_review"])
        self.assertIn("source_stale", rule["review_reasons"])
        self.assertEqual(report["stale_rule_ids"], ["old_cover"])

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

    def test_standards_production_validation_requires_acceptance_signoff(self) -> None:
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
        accepted["accepted_rules"][0].pop("accepted_by")

        validation = validate_standards_acceptance_for_production(accepted)

        self.assertFalse(validation["production_usable"])
        blockers = {item["field"]: item for item in validation["blockers"]}
        detail_fields = {item["field"] for item in validation["blocker_details"]}
        self.assertIn("rule_metadata", blockers)
        self.assertIn("rule_metadata", detail_fields)
        self.assertEqual(blockers["rule_metadata"]["rules"][0]["missing"], ["accepted_by"])
        detail = next(item for item in validation["blocker_details"] if item["field"] == "rule_metadata")
        self.assertTrue(detail["next_action"])

    def test_civil_readiness_blocks_standards_without_acceptance_signoff(self) -> None:
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
        accepted["accepted_rules"][0].pop("accepted_by")
        evidence = standards_project_evidence_from_acceptance(
            accepted,
            review_packet=packet,
            company_standards={"source": "company_manual", "cad_layers": "CIVORA", "production_usable": True},
        )

        readiness = civil_design_readiness({"meta": evidence})
        fields = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertIn(("standards", "rule_metadata"), fields)
        self.assertFalse(readiness["production_ready"])

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

    def test_project_standards_evidence_requires_company_profile_for_production(self) -> None:
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

        evidence = standards_project_evidence_from_acceptance(accepted, review_packet=packet)

        self.assertFalse(evidence["production_usable"])
        self.assertFalse(evidence["company_standards"]["production_usable"])
        self.assertEqual(evidence["company_standards"]["source"], "civora_default_company_standards_placeholder")

    def test_civil_readiness_blocks_missing_company_standards(self) -> None:
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
        evidence = standards_project_evidence_from_acceptance(accepted, review_packet=packet)

        readiness = civil_design_readiness({"meta": evidence})

        fields = {(item["area"], item["field"]) for item in readiness["production_blockers"]}
        self.assertIn(("standards", "company_standards"), fields)
        self.assertFalse(readiness["production_ready"])

    def test_baseline_or_search_sources_are_not_production_authority(self) -> None:
        packet = build_standards_review_packet()
        baseline = packet["candidate_rules"][0]["rule_id"]
        accepted = accept_standards_rules(packet, [baseline])

        validation = validate_standards_acceptance_for_production(accepted)

        self.assertFalse(validation["production_usable"])
        fields = {item["field"] for item in validation["blockers"]}
        self.assertIn("official_sources", fields)
        self.assertIn("baseline_rules", fields)
        self.assertEqual(validation["inferred_rule_ids"], [baseline])

    def test_inferred_search_candidates_remain_blocked_after_acceptance(self) -> None:
        validation = validate_standards_acceptance_for_production(
            {
                "accepted_rules": [
                    {
                        "rule_id": "search_result_rule",
                        "discipline": "storm",
                        "topic": "Stormwater manual",
                        "candidate_value": "Use the city stormwater manual.",
                        "source_id": "municipal_code_search",
                        "source_url": "https://www.google.com/search?q=city+stormwater+manual",
                        "source_section": "Search result",
                        "accepted_by": "u1",
                        "accepted_date": "2026-06-05",
                        "confidence": "candidate",
                    }
                ]
            }
        )

        fields = {item["field"] for item in validation["blockers"]}
        self.assertFalse(validation["production_usable"])
        self.assertIn("inferred_rules", fields)
        self.assertIn("official_sources", fields)
        self.assertEqual(validation["accepted_rule_ids"], ["search_result_rule"])
        self.assertEqual(validation["inferred_rule_ids"], ["search_result_rule"])

    def test_candidate_rule_cannot_satisfy_production_acceptance_even_with_official_url(self) -> None:
        validation = validate_standards_acceptance_for_production(
            {
                "accepted_rules": [
                    {
                        "rule_id": "candidate_city_cover",
                        "discipline": "utilities",
                        "topic": "minimum cover",
                        "candidate_value": "Minimum cover shall be 4 feet.",
                        "source_id": "city_manual",
                        "source_url": "https://city.example.gov/manual",
                        "source_section": "Section 5.1",
                        "retrieved_date": "2026-06-05",
                        "retrieved_at": "2026-06-05",
                        "confidence": "text_pattern_candidate",
                        "status": "candidate",
                        "acceptance_status": "candidate",
                        "source_type": "scraped_candidate",
                        "accepted_by": "u1",
                        "accepted_date": "2026-06-05",
                    }
                ],
                "source_urls": ["https://city.example.gov/manual"],
            }
        )

        fields = {item["field"] for item in validation["blockers"]}

        self.assertFalse(validation["production_usable"])
        self.assertIn("rule_acceptance_status", fields)
        self.assertIn("inferred_rules", fields)
        self.assertEqual(validation["official_source_count"], 1)

    def test_review_workflow_accepts_candidate_with_audit_metadata(self) -> None:
        packet = build_standards_review_packet(
            city="Austin",
            state="Texas",
            extracted_rules=[
                {
                    "rule_id": "city_cover",
                    "discipline": "utilities",
                    "topic": "minimum cover",
                    "candidate_value": "Minimum cover shall be 4 feet.",
                    "source_id": "city_manual",
                    "source_url": "https://city.example.gov/manual",
                    "source_document_title": "City Utility Manual",
                    "source_version_or_effective_date": "2026-01-01",
                    "source_section": "Section 5.1",
                }
            ],
        )

        reviewed = review_candidate_standards(
            packet,
            [{"rule_id": "city_cover", "action": "accept", "acceptance_note": "Applies to private utility cover."}],
            reviewer_id="engineer-1",
        )

        accepted = reviewed["accepted_rules"][0]

        self.assertTrue(reviewed["accepted_for_qa"])
        self.assertEqual(reviewed["accepted_rule_count"], 1)
        self.assertEqual(accepted["status"], "accepted")
        self.assertEqual(accepted["acceptance_status"], "accepted")
        self.assertEqual(accepted["accepted_by"], "engineer-1")
        self.assertTrue(accepted["accepted_at"])
        self.assertTrue(accepted["accepted_date"])
        self.assertEqual(accepted["source_id"], "city_manual")
        self.assertEqual(accepted["source_url"], "https://city.example.gov/manual")
        self.assertEqual(accepted["source_version_or_effective_date"], "2026-01-01")
        self.assertEqual(accepted["acceptance_note"], "Applies to private utility cover.")
        audit = {item["rule_id"]: item for item in reviewed["audit_trail"]}
        self.assertEqual(audit["city_cover"]["decision"], "accepted")

    def test_review_workflow_rejects_candidate_and_preserves_reason(self) -> None:
        packet = build_standards_review_packet(
            extracted_rules=[
                {
                    "rule_id": "wrong_rule",
                    "discipline": "storm",
                    "topic": "detention drawdown",
                    "candidate_value": "Detention drawdown shall be 72 hours.",
                    "source_url": "https://city.example.gov/manual",
                    "source_section": "Section 3.2",
                }
            ],
        )

        reviewed = review_candidate_standards(
            packet,
            [{"rule_id": "wrong_rule", "action": "reject", "rejection_reason": "Not applicable to this project area."}],
            reviewer_id="engineer-1",
        )

        rejected = reviewed["rejected_rules"][0]

        self.assertEqual(reviewed["accepted_rule_count"], 0)
        self.assertEqual(reviewed["rejected_rule_count"], 1)
        self.assertEqual(rejected["acceptance_status"], "unaccepted")
        self.assertEqual(rejected["rejection_reason"], "Not applicable to this project area.")
        self.assertFalse(reviewed["production_usable"])
        self.assertIn("accepted_rules", {item["field"] for item in reviewed["production_validation"]["blockers"]})

    def test_review_workflow_pending_candidate_remains_blocked(self) -> None:
        packet = build_standards_review_packet(
            extracted_rules=[
                {
                    "rule_id": "pending_cover",
                    "discipline": "utilities",
                    "topic": "minimum cover",
                    "candidate_value": "Minimum cover shall be 4 feet.",
                    "source_url": "https://city.example.gov/manual",
                    "source_section": "Section 5.1",
                }
            ],
        )

        reviewed = review_candidate_standards(packet, [{"rule_id": "pending_cover", "action": "pending"}])

        self.assertEqual(reviewed["accepted_rule_count"], 0)
        self.assertEqual(reviewed["pending_rule_count"], len(packet["candidate_rules"]))
        self.assertTrue(all(rule["requires_user_acceptance"] for rule in reviewed["pending_rules"]))
        self.assertFalse(reviewed["production_usable"])
        self.assertIn("accepted_rules", {item["field"] for item in reviewed["production_validation"]["blockers"]})

    def test_review_workflow_accept_requires_identity_or_approval_metadata(self) -> None:
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
            ],
        )

        reviewed = review_candidate_standards(packet, [{"rule_id": "city_cover", "action": "accept"}])

        self.assertEqual(reviewed["accepted_rule_count"], 0)
        self.assertTrue(reviewed["action_errors"])
        self.assertIn("Acceptance requires reviewer identity", reviewed["action_errors"][0]["reason"])
        self.assertIn("city_cover", {rule["rule_id"] for rule in reviewed["pending_rules"]})

    def test_review_workflow_audit_trail_preserved_in_standards_pack(self) -> None:
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
            ],
        )
        reviewed = review_candidate_standards(
            packet,
            [{"rule_id": "city_cover", "action": "accept", "acceptance_note": "Selected for utility cover review."}],
            reviewer_id="engineer-1",
        )

        pack = standards_pack_from_acceptance(reviewed)

        audit = {item["rule_id"]: item for item in pack["audit_trail"]}
        self.assertIn("city_cover", audit)
        self.assertEqual(pack["rules"][0]["acceptance_note"], "Selected for utility cover review.")


if __name__ == "__main__":
    unittest.main()
