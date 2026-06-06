import unittest

from backend.fixtures.standards.real_official_sources import (
    AUSTIN_WATER_CONSTRUCTION_STANDARDS_ALLOWLIST,
    AUSTIN_WATER_CONSTRUCTION_STANDARDS_RECORDED_HTML,
    AUSTIN_WATER_CONSTRUCTION_STANDARDS_SOURCE,
)
from backend.planning.standards_package import build_standards_package
from backend.planning.standards_discovery import (
    accept_standards_rules,
    build_candidate_rule_report,
    build_live_source_fetch_record,
    build_standards_source_registry,
    build_standards_review_packet,
    controlled_single_source_lookup,
    discover_standards_sources,
    extract_rule_candidates_from_text,
    fetch_and_extract_rule_candidates,
    fetch_live_standards_source_candidate,
    review_candidate_standards,
    standards_live_source_policy,
    standards_pack_from_acceptance,
    standards_project_evidence_from_acceptance,
    trusted_standards_source_allowlist,
    validate_standards_acceptance_for_production,
)
from core.civil_design import civil_design_readiness, construction_readiness


class StandardsDiscoveryTests(unittest.TestCase):
    def _trusted_city_allowlist(self):
        return [
            {
                "jurisdiction": {"city": "Example City", "state": "Texas"},
                "agency": "Example City Public Works",
                "allowed_domains": ["city.example.gov"],
                "allowed_source_types": ["official_city"],
                "disciplines": ["utilities"],
                "configured_by": "standards-admin",
                "configured_at": "2026-06-05",
                "confidence_cap": "trusted_candidate",
            }
        ]

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

        accepted = accept_standards_rules(packet, [first_rule], edits={first_rule: {"candidate_value": "Accepted edited value"}}, accepted_by="u1")
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
        accepted = accept_standards_rules(packet, [first_rule], accepted_by="u1")

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

    def test_live_source_policy_lists_allowed_and_blocked_types(self) -> None:
        policy = standards_live_source_policy()

        self.assertEqual(policy["version"], "standards_live_source_policy_v1")
        self.assertIn("official_city", policy["allowed_source_types"])
        self.assertIn("official_utility", policy["allowed_source_types"])
        self.assertIn("blogs", policy["blocked_source_types"])
        self.assertTrue(policy["candidate_only"])
        self.assertEqual(policy["acceptance_status"], "unaccepted")

    def test_trusted_allowlist_normalizes_required_fields(self) -> None:
        allowlist = trusted_standards_source_allowlist(
            [
                {
                    "jurisdiction": {"city": "Example City", "state": "Texas"},
                    "agency": "Example City Public Works",
                    "allowed_domains": ["https://www.examplecity.gov/standards"],
                    "allowed_source_types": ["Official City"],
                    "disciplines": ["roadway", "utilities"],
                    "effective_from": "2026-01-01",
                    "configured_by": "admin-1",
                    "configured_at": "2026-06-05",
                    "confidence_cap": "trusted_candidate",
                }
            ]
        )

        entry = allowlist["entries"][0]

        self.assertEqual(allowlist["version"], "trusted_standards_source_allowlist_v1")
        self.assertEqual(entry["allowed_domains"], ["www.examplecity.gov"])
        self.assertEqual(entry["allowed_source_types"], ["official_city"])
        self.assertEqual(entry["confidence_cap"], "trusted_candidate")
        self.assertTrue(allowlist["candidate_only"])

    def test_official_live_source_fetch_is_candidate_only(self) -> None:
        class Response:
            url = "https://city.example.gov/manual"
            text = "<html><body>Minimum cover shall be 4 feet.</body></html>"

            def raise_for_status(self):
                return None

        class Session:
            def get(self, url, timeout=None):
                return Response()

        result = fetch_live_standards_source_candidate(
            source_url="https://city.example.gov/manual",
            source_id="city_manual",
            source_type="official_city",
            jurisdiction={"city": "Example City", "state": "Texas"},
            agency="Example City Public Works",
            document_title="Engineering Criteria Manual",
            version="2026-01",
            session=Session(),
            allow_network_fetch=True,
        )

        record = result["fetch_record"]
        rule = result["candidate_rules"][0]

        self.assertTrue(result["success"])
        self.assertEqual(record["source_type"], "official_city")
        self.assertEqual(record["fetch_status"], "fetched")
        self.assertTrue(record["content_hash"])
        self.assertTrue(record["candidate_only"])
        self.assertEqual(record["acceptance_status"], "unaccepted")
        self.assertEqual(result["source_registry"]["accepted_source_count"], 0)
        self.assertEqual(rule["acceptance_status"], "candidate")
        self.assertTrue(rule["requires_user_acceptance"])
        self.assertFalse(result["candidate_rule_report"]["production_usable"])

    def test_allowlisted_official_city_domain_gets_high_confidence_candidate_source(self) -> None:
        allowlist_entries = [
            {
                "jurisdiction": {"city": "Example City", "state": "Texas"},
                "agency": "Example City Public Works",
                "allowed_domains": ["city.example.gov"],
                "allowed_source_types": ["official_city"],
                "disciplines": ["utilities"],
                "configured_by": "standards-admin",
                "configured_at": "2026-06-05",
                "confidence_cap": "trusted_candidate",
            }
        ]

        record = build_live_source_fetch_record(
            source_url="https://city.example.gov/manual",
            jurisdiction={"city": "Example City", "state": "Texas"},
            agency="Example City Public Works",
            source_type="official_city",
            allowlist_entries=allowlist_entries,
        )

        self.assertEqual(record["confidence"], "trusted_candidate")
        self.assertTrue(record["policy_decision"]["allowlist_matched"])
        self.assertFalse(record["review_only"])
        self.assertTrue(record["candidate_only"])
        self.assertEqual(record["acceptance_status"], "unaccepted")

    def test_unmatched_official_looking_domain_remains_review_only(self) -> None:
        record = build_live_source_fetch_record(
            source_url="https://city.example.gov/manual",
            jurisdiction={"city": "Example City", "state": "Texas"},
            agency="Example City Public Works",
            source_type="official_city",
            allowlist_entries=[
                {
                    "jurisdiction": {"city": "Other City", "state": "Texas"},
                    "agency": "Other City Public Works",
                    "allowed_domains": ["other.example.gov"],
                    "allowed_source_types": ["official_city"],
                    "disciplines": ["utilities"],
                    "configured_by": "standards-admin",
                }
            ],
        )

        self.assertEqual(record["confidence"], "low")
        self.assertTrue(record["review_only"])
        self.assertFalse(record["policy_decision"]["allowlist_matched"])
        self.assertTrue(record["needs_review"])

    def test_blocked_source_type_remains_blocked_even_if_domain_looks_allowed(self) -> None:
        record = build_live_source_fetch_record(
            source_url="https://city.example.gov/manual-summary",
            jurisdiction={"city": "Example City", "state": "Texas"},
            agency="Example City Public Works",
            source_type="blogs",
            allowlist_entries=[
                {
                    "jurisdiction": {"city": "Example City", "state": "Texas"},
                    "agency": "Example City Public Works",
                    "allowed_domains": ["city.example.gov"],
                    "allowed_source_types": ["official_city", "blogs"],
                    "disciplines": ["utilities"],
                    "confidence_cap": "trusted_candidate",
                }
            ],
        )

        self.assertEqual(record["confidence"], "blocked")
        self.assertTrue(record["policy_decision"]["blocked"])
        self.assertFalse(record["policy_decision"]["allowlist_matched"])
        self.assertTrue(record["needs_review"])

    def test_company_uploaded_without_owner_metadata_is_review_only_blocked(self) -> None:
        record = build_live_source_fetch_record(
            source_url="internal://company-uploads/water-standards.pdf",
            source_type="company_uploaded",
            allowlist_entries=[
                {
                    "agency": "Example Utility",
                    "allowed_domains": ["company-uploads"],
                    "allowed_source_types": ["company_uploaded"],
                    "disciplines": ["water"],
                    "confidence_cap": "trusted_candidate",
                }
            ],
        )

        self.assertEqual(record["confidence"], "blocked")
        self.assertTrue(record["policy_decision"]["blocked"])
        self.assertTrue(record["review_only"])
        self.assertIn("uploaded_by", " ".join(record["policy_decision"]["reasons"]))

    def test_allowlisted_candidate_cannot_satisfy_production_without_acceptance(self) -> None:
        validation = validate_standards_acceptance_for_production(
            {
                "accepted_rules": [
                    {
                        "rule_id": "city_manual_utilities_1_1",
                        "discipline": "utilities",
                        "topic": "minimum cover",
                        "candidate_value": "Minimum cover shall be 4 feet.",
                        "source_id": "city_manual",
                        "source_url": "https://city.example.gov/manual",
                        "source_section": "minimum cover",
                        "retrieved_date": "2026-06-05",
                        "confidence": "trusted_candidate",
                        "status": "candidate",
                        "acceptance_status": "candidate",
                        "source_type": "official_city",
                    }
                ],
                "source_urls": ["https://city.example.gov/manual"],
            }
        )

        self.assertFalse(validation["production_usable"])
        blocker_fields = {item["field"] for item in validation["blockers"]}
        self.assertIn("rule_acceptance_status", blocker_fields)
        self.assertIn("rule_metadata", blocker_fields)

    def test_single_source_lookup_blocks_without_operator_authorization(self) -> None:
        result = controlled_single_source_lookup(
            source_url="https://city.example.gov/manual",
            source_id="city_manual",
            jurisdiction={"city": "Example City", "state": "Texas"},
            agency="Example City Public Works",
            source_type="official_city",
            discipline="utilities",
            operator_authorized=False,
            allowlist_entries=self._trusted_city_allowlist(),
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["fetch_record"]["fetch_status"], "blocked_by_operator_authorization")
        self.assertEqual(result["warnings"], ["operator_authorized must be true for controlled single-source lookup."])
        self.assertEqual(result["candidate_count"], 0)
        self.assertFalse(result["production_usable"])
        self.assertFalse(result["construction_release_allowed"])

    def test_single_source_lookup_requires_allowlist_match(self) -> None:
        result = controlled_single_source_lookup(
            source_url="https://city.example.gov/manual",
            source_id="city_manual",
            jurisdiction={"city": "Example City", "state": "Texas"},
            agency="Example City Public Works",
            source_type="official_city",
            discipline="utilities",
            operator_authorized=True,
            allowlist_entries=[
                {
                    "jurisdiction": {"city": "Other City", "state": "Texas"},
                    "agency": "Other City Public Works",
                    "allowed_domains": ["other.example.gov"],
                    "allowed_source_types": ["official_city"],
                    "disciplines": ["utilities"],
                }
            ],
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["fetch_record"]["fetch_status"], "blocked_by_allowlist")
        self.assertEqual(result["fetch_record"]["confidence"], "low")
        self.assertTrue(result["fetch_record"]["review_only"])
        self.assertFalse(result["source_classification"]["allowlist_matched"])

    def test_single_source_lookup_extracts_candidate_rules_from_fixture(self) -> None:
        class Response:
            url = "https://city.example.gov/manual"
            text = "<html><body>Minimum cover shall be 4 feet.</body></html>"
            headers = {"content-type": "text/html"}

            def raise_for_status(self):
                return None

        class Session:
            def get(self, url, timeout=None):
                return Response()

        result = controlled_single_source_lookup(
            source_url="https://city.example.gov/manual",
            source_id="city_manual",
            jurisdiction={"city": "Example City", "state": "Texas"},
            agency="Example City Public Works",
            source_type="official_city",
            discipline="utilities",
            operator_authorized=True,
            document_title="Engineering Criteria Manual",
            version="2026-01",
            session=Session(),
            allowlist_entries=self._trusted_city_allowlist(),
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["workflow_version"], "controlled_single_source_lookup_v1")
        self.assertEqual(result["fetch_record"]["fetch_status"], "fetched")
        self.assertEqual(result["fetch_record"]["confidence"], "trusted_candidate")
        self.assertTrue(result["fetch_record"]["candidate_only"])
        self.assertEqual(result["fetch_record"]["acceptance_status"], "unaccepted")
        self.assertEqual(result["source_registry"]["accepted_source_count"], 0)
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["candidate_rules"][0]["acceptance_status"], "candidate")
        self.assertTrue(result["candidate_rules"][0]["requires_user_acceptance"])
        self.assertFalse(result["candidate_rule_report"]["production_usable"])
        self.assertFalse(result["production_usable"])
        self.assertFalse(result["construction_release_allowed"])

    def test_real_official_single_source_lookup_uses_candidate_only_recorded_fixture(self) -> None:
        source = AUSTIN_WATER_CONSTRUCTION_STANDARDS_SOURCE

        class Response:
            url = source["source_url"]
            text = AUSTIN_WATER_CONSTRUCTION_STANDARDS_RECORDED_HTML
            headers = {"content-type": "text/html"}

            def raise_for_status(self):
                return None

        class Session:
            def get(self, url, timeout=None):
                self.requested_url = url
                return Response()

        session = Session()
        result = controlled_single_source_lookup(
            source_url=source["source_url"],
            source_id=source["source_id"],
            jurisdiction=source["jurisdiction"],
            agency=source["agency"],
            source_type=source["source_type"],
            discipline=source["discipline"],
            operator_authorized=True,
            document_title=source["document_title"],
            session=session,
            allowlist_entries=AUSTIN_WATER_CONSTRUCTION_STANDARDS_ALLOWLIST,
        )
        meta = {
            "standards_source_registry": result["source_registry"],
            "standards_candidate_rule_report": result["candidate_rule_report"],
            "selected_standards_source": {
                "source_id": source["source_id"],
                "source_url": source["source_url"],
                "source_urls": [source["source_url"]],
                "candidate_only": True,
                "acceptance_status": "unaccepted",
            },
            "jurisdiction_standards": {
                "city": "Austin",
                "state": "Texas",
                "agency": source["agency"],
                "source_urls": [source["source_url"]],
                "production_usable": False,
            },
        }
        meta["standards_package"] = build_standards_package(meta)

        self.assertTrue(result["success"])
        self.assertEqual(session.requested_url, source["source_url"])
        self.assertEqual(result["fetch_record"]["fetch_status"], "fetched")
        self.assertEqual(result["fetch_record"]["source_url"], source["source_url"])
        self.assertTrue(result["source_classification"]["allowlist_matched"])
        self.assertEqual(result["source_classification"]["confidence"], "trusted_candidate")
        self.assertTrue(result["fetch_record"]["candidate_only"])
        self.assertEqual(result["fetch_record"]["acceptance_status"], "unaccepted")
        self.assertEqual(result["source_registry"]["accepted_source_count"], 0)
        self.assertEqual(result["source_registry"]["sources"][0]["acceptance_status"], "unaccepted")
        self.assertEqual(result["candidate_rule_report"]["accepted_rule_count"], 0)
        self.assertFalse(result["candidate_rule_report"]["production_usable"])
        self.assertTrue(result["candidate_rule_report"]["requires_user_acceptance"])
        self.assertFalse(result["production_usable"])
        self.assertFalse(result["construction_release_allowed"])
        self.assertEqual(result["candidate_count"], 0)
        self.assertIn("Austin Water", source["why_official"])

        readiness = civil_design_readiness({"meta": meta})
        release = construction_readiness({"meta": meta})

        self.assertFalse(meta["standards_package"]["production_usable"])
        self.assertTrue(meta["standards_package"]["construction_release_blocked"])
        self.assertFalse(readiness["production_ready"])
        self.assertFalse(release["ready"])
        self.assertEqual(release["status"], "not_construction_ready")

    def test_single_source_lookup_handles_network_failure_safely(self) -> None:
        class Session:
            def get(self, url, timeout=None):
                raise TimeoutError("fixture timeout")

        result = controlled_single_source_lookup(
            source_url="https://city.example.gov/manual",
            source_id="city_manual",
            jurisdiction={"city": "Example City", "state": "Texas"},
            agency="Example City Public Works",
            source_type="official_city",
            discipline="utilities",
            operator_authorized=True,
            session=Session(),
            allowlist_entries=self._trusted_city_allowlist(),
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["fetch_record"]["fetch_status"], "fetch_failed")
        self.assertEqual(result["warnings"], ["fixture timeout"])
        self.assertEqual(result["candidate_count"], 0)
        self.assertFalse(result["production_usable"])

    def test_single_source_lookup_rejects_unsupported_content_type(self) -> None:
        class Response:
            url = "https://city.example.gov/manual"
            text = '{"minimum_cover": "4 feet"}'
            headers = {"content-type": "application/json"}

            def raise_for_status(self):
                return None

        class Session:
            def get(self, url, timeout=None):
                return Response()

        result = controlled_single_source_lookup(
            source_url="https://city.example.gov/manual",
            source_id="city_manual",
            jurisdiction={"city": "Example City", "state": "Texas"},
            agency="Example City Public Works",
            source_type="official_city",
            discipline="utilities",
            operator_authorized=True,
            session=Session(),
            allowlist_entries=self._trusted_city_allowlist(),
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["fetch_record"]["fetch_status"], "unsupported_content_type")
        self.assertEqual(result["warnings"], ["Controlled single-source lookup supports HTML, text, or PDF sources only."])
        self.assertEqual(result["candidate_count"], 0)

    def test_single_source_lookup_rejects_invalid_url_safely(self) -> None:
        result = controlled_single_source_lookup(
            source_url="not-a-url",
            source_id="city_manual",
            jurisdiction={"city": "Example City", "state": "Texas"},
            agency="Example City Public Works",
            source_type="official_city",
            discipline="utilities",
            operator_authorized=True,
            allowlist_entries=self._trusted_city_allowlist(),
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["fetch_record"]["fetch_status"], "blocked_by_policy")
        self.assertIn("HTTPS", result["warnings"][0])
        self.assertEqual(result["candidate_count"], 0)

    def test_unofficial_live_source_is_blocked_or_low_confidence(self) -> None:
        result = fetch_live_standards_source_candidate(
            source_url="https://standards-blog.example.com/city-manual-summary",
            source_id="blog_summary",
            source_type="blogs",
            agency="",
            allow_network_fetch=True,
        )

        self.assertFalse(result["success"])
        self.assertTrue(result["source_classification"]["blocked"])
        self.assertEqual(result["fetch_record"]["fetch_status"], "blocked_by_policy")
        self.assertEqual(result["fetch_record"]["confidence"], "blocked")
        self.assertTrue(result["fetch_record"]["candidate_only"])
        self.assertEqual(result["fetch_record"]["acceptance_status"], "unaccepted")
        self.assertEqual(result["candidate_count"], 0)

    def test_unknown_pdf_without_source_owner_is_blocked(self) -> None:
        result = fetch_live_standards_source_candidate(
            source_url="https://files.example.com/standards.pdf",
            source_id="unknown_pdf",
            source_type="",
            agency="",
            allow_network_fetch=True,
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["source_classification"]["source_type"], "unknown_pdf_without_source_owner")
        self.assertTrue(result["source_classification"]["blocked"])
        self.assertEqual(result["fetch_record"]["fetch_status"], "blocked_by_policy")

    def test_stale_live_source_record_needs_review(self) -> None:
        record = build_live_source_fetch_record(
            source_url="https://city.example.gov/manual",
            agency="Example City Public Works",
            source_type="official_city",
            retrieved_at="2000-01-01",
            fetch_status="deferred_by_policy",
        )

        self.assertTrue(record["staleness"]["stale"])
        self.assertTrue(record["needs_review"])
        self.assertTrue(record["next_refresh_due"])

    def test_fetched_candidate_cannot_satisfy_production_compliance(self) -> None:
        validation = validate_standards_acceptance_for_production(
            {
                "accepted_rules": [
                    {
                        "rule_id": "city_manual_utilities_1_1",
                        "discipline": "utilities",
                        "topic": "minimum cover",
                        "candidate_value": "Minimum cover shall be 4 feet.",
                        "source_id": "city_manual",
                        "source_url": "https://city.example.gov/manual",
                        "source_section": "minimum cover",
                        "retrieved_date": "2026-06-05",
                        "confidence": "live_source_candidate",
                        "status": "candidate",
                        "acceptance_status": "candidate",
                        "source_type": "official_city",
                        "accepted_by": "engineer-1",
                        "accepted_date": "2026-06-05",
                    }
                ],
                "source_urls": ["https://city.example.gov/manual"],
            }
        )

        self.assertFalse(validation["production_usable"])
        self.assertIn("rule_acceptance_status", {item["field"] for item in validation["blockers"]})

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
        accepted = accept_standards_rules(packet, ["city_cover"], accepted_by="u1")
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
        accepted = accept_standards_rules(packet, ["city_cover"], accepted_by="u1")
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

    def test_legacy_acceptance_without_reviewer_identity_remains_pending(self) -> None:
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

        self.assertEqual(accepted["accepted_rule_count"], 0)
        self.assertFalse(accepted["accepted_for_qa"])
        self.assertIn("city_cover", {rule["rule_id"] for rule in accepted["pending_rules"]})
        self.assertTrue(accepted["action_errors"])
        self.assertIn("accepted_rules", {item["field"] for item in accepted["production_validation"]["blockers"]})

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
        accepted = accept_standards_rules(packet, ["city_cover"], accepted_by="u1")
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
        accepted = accept_standards_rules(packet, ["city_cover"], accepted_by="u1")

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
        accepted = accept_standards_rules(packet, ["city_cover"], accepted_by="u1")

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
        accepted = accept_standards_rules(packet, ["city_cover"], accepted_by="u1")
        evidence = standards_project_evidence_from_acceptance(accepted, review_packet=packet)

        readiness = civil_design_readiness({"meta": evidence})

        fields = {(item["area"], item["field"]) for item in readiness["production_blockers"]}
        self.assertIn(("standards", "company_standards"), fields)
        self.assertFalse(readiness["production_ready"])

    def test_baseline_or_search_sources_are_not_production_authority(self) -> None:
        packet = build_standards_review_packet()
        baseline = packet["candidate_rules"][0]["rule_id"]
        accepted = accept_standards_rules(packet, [baseline], accepted_by="u1")

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
