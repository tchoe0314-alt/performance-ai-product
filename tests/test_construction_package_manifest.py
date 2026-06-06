import unittest

import planner
from backend.planning.construction_package import (
    build_construction_document_support_package,
    build_construction_package_manifest,
    build_review_package_manifest,
)


def _valid_professional_review(model_id: str = "MODEL-FINAL-1", package_id: str = "PKG-IFC-1") -> dict:
    return {
        "status": "released_for_construction",
        "sealed": True,
        "engineer_name": "Alex Morgan",
        "license_number": "TX-123456",
        "review_date": "2026-05-29",
        "jurisdiction": "Test City",
        "license_jurisdiction": "TX",
        "discipline": "civil",
        "review_scope": "civil_site_construction_documents",
        "canonical_model_id": model_id,
        "reviewed_package_id": package_id,
    }


class ConstructionPackageManifestTests(unittest.TestCase):
    def test_build_plan_attaches_blocking_manifest_for_concept_plan(self) -> None:
        plan = planner.build_plan(
            {
                "project_name": "Construction Manifest Smoke",
                "units": "ft",
                "mode": "site_plan",
                "lot": {"x": 0.0, "y": 0.0, "w": 120.0, "h": 100.0},
                "site_plan": {"building_width": 40.0, "building_depth": 30.0, "parking_count": 12},
            }
        )

        manifest = plan["meta"]["construction_package_manifest"]

        self.assertEqual(manifest["release_state"], "blocked_from_construction_release")
        self.assertFalse(manifest["construction_export_allowed"])
        self.assertTrue(manifest["review_package_allowed"])
        self.assertIn("existing_conditions", manifest["blocked_sections"])
        self.assertIn("standards", manifest["blocked_sections"])
        self.assertIn("professional_release", manifest["blocked_sections"])
        artifact_status = manifest["construction_package_artifact_status"]
        self.assertFalse(artifact_status["package_present"])
        self.assertEqual(set(artifact_status["missing"]), {"sheets", "cad_export", "qa_report", "cost_estimate", "construction_manifest"})
        self.assertFalse(artifact_status["complete_for_release"])
        self.assertTrue(manifest["next_actions"])
        review_manifest = plan["meta"]["review_package_manifest"]
        self.assertEqual(review_manifest["source"], "review_package_manifest_v1")
        self.assertFalse(review_manifest["construction_release_allowed"])
        self.assertTrue(review_manifest["construction_release_blocked"])
        self.assertIn("civil3d", review_manifest["export_confidence"]["formats"])
        self.assertEqual(review_manifest["export_confidence"]["formats"]["dwg"]["status"], "unsupported_no_writer")

    def test_review_package_manifest_allows_alpha_review_without_construction_release(self) -> None:
        meta = {
            "product_mode": "private_alpha",
            "sheet_registry": [{"sheet_id": "C-100", "title": "Civil Site Plan"}],
            "export_audit": {"ready": True, "production_export_ready": True},
            "cad_interop": {
                "dxf": True,
                "dwg": False,
                "civil3d": False,
                "landxml_pipe_network_contract": True,
            },
        }

        manifest = build_review_package_manifest({"meta": meta})

        self.assertTrue(manifest["review_ready"])
        self.assertTrue(manifest["review_package_allowed"])
        self.assertFalse(manifest["construction_ready"])
        self.assertFalse(manifest["construction_release_allowed"])
        self.assertTrue(manifest["construction_release_blocked"])
        self.assertFalse(manifest["review_blockers"])
        formats = manifest["export_confidence"]["formats"]
        self.assertEqual(formats["dxf"]["status"], "audited_review_ready")
        self.assertTrue(formats["dxf"]["review_ready"])
        self.assertEqual(formats["landxml"]["status"], "pipe_network_contract_review_ready_not_civil3d_verified")
        self.assertEqual(formats["civil3d"]["status"], "not_verified")
        self.assertEqual(formats["dwg"]["status"], "unsupported_no_writer")

    def test_review_package_manifest_blocks_missing_export_audit(self) -> None:
        meta = {
            "product_mode": "private_alpha",
            "sheet_registry": [{"sheet_id": "C-100", "title": "Civil Site Plan"}],
            "cad_interop": {"dxf": True, "dwg": False, "civil3d": False},
        }

        manifest = build_review_package_manifest({"meta": meta})

        self.assertFalse(manifest["review_ready"])
        self.assertFalse(manifest["review_package_allowed"])
        fields = {item["field"] for item in manifest["review_blockers"]}
        self.assertIn("dxf_review_export", fields)
        self.assertEqual(manifest["export_confidence"]["formats"]["dxf"]["status"], "blocked_missing_export_audit")

    def test_manifest_groups_blockers_into_actionable_release_sections(self) -> None:
        meta = {
            "construction_readiness": {
                "ready": False,
                "status": "not_construction_ready",
                "score": 64.0,
                "evidence": {
                    "civil_production_ready": False,
                    "existing_conditions_production_ready": False,
                    "standards_production_usable": True,
                    "export_production_ready": False,
                    "professional_release": False,
                },
                "blockers": [
                    {
                        "area": "existing_conditions",
                        "field": "survey",
                        "why_needed": "Survey is required.",
                        "suggested_next_action": "Import survey.",
                    },
                    {
                        "area": "deliverables",
                        "field": "export_audit",
                        "why_needed": "Export audit is required.",
                        "suggested_next_action": "Regenerate export audit.",
                    },
                    {
                        "area": "professional_review",
                        "field": "sealed_release",
                        "why_needed": "Seal is required.",
                        "suggested_next_action": "Attach professional release.",
                    },
                ],
                "warnings": [],
            }
        }

        manifest = build_construction_package_manifest({"meta": meta})
        sections = {section["section_id"]: section for section in manifest["sections"]}

        self.assertFalse(manifest["release_allowed"])
        self.assertEqual(sections["existing_conditions"]["status"], "blocked")
        self.assertEqual(sections["deliverables"]["status"], "blocked")
        self.assertEqual(sections["professional_release"]["status"], "blocked")
        self.assertEqual(sections["standards"]["status"], "ready")
        self.assertTrue(manifest["blocker_details"])
        self.assertEqual(sections["existing_conditions"]["blocker_details"][0]["field"], "survey")

    def test_manifest_allows_release_only_when_construction_gate_is_ready(self) -> None:
        meta = {
            "product_mode": "production",
            "construction_readiness": {
                "ready": True,
                "status": "construction_ready",
                "score": 100.0,
                "evidence": {
                    "civil_production_ready": True,
                    "existing_conditions_production_ready": True,
                    "standards_production_usable": True,
                    "export_production_ready": True,
                    "cost_production_usable": True,
                    "professional_release": True,
                },
                "blockers": [],
                "warnings": [],
            },
            "cost_estimate": {
                "success": True,
                "totals": {"production_usable": True, "total_cost": 1000.0, "cost_estimate_hash": "COST-HASH-1"},
                "line_items": [{"metric": "pipe_length_ft", "quantity": 10.0, "amount": 1000.0}],
                "explain": {
                    "cost_estimate_reference": {
                        "cost_estimate_hash": "COST-HASH-1",
                        "quantity_model_hash": "QTY-HASH-1",
                        "price_book_hash": "PRICE-HASH-1",
                    },
                    "quantity_model_reference": {"quantity_model_hash": "QTY-HASH-1"},
                    "pricing": {"price_book_hash": "PRICE-HASH-1"},
                },
            },
            "construction_deliverable_package": {
                "id": "PKG-IFC-1",
                "release_ready": True,
                "production_ready": True,
                "canonical_model_id": "MODEL-FINAL-1",
                "artifacts": [
                    {"type": "sheets", "id": "SHEETS-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cad_export", "id": "CAD-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "qa_report", "id": "QA-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {
                        "type": "cost_estimate",
                        "id": "COST-1",
                        "current": True,
                        "canonical_model_id": "MODEL-FINAL-1",
                        "cost_estimate_hash": "COST-HASH-1",
                    },
                    {"type": "construction_manifest", "id": "MANIFEST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                ],
            },
            "professional_review": _valid_professional_review(),
        }

        manifest = build_construction_package_manifest({"meta": meta})

        self.assertEqual(manifest["release_state"], "released_for_construction")
        self.assertTrue(manifest["construction_export_allowed"])
        self.assertFalse(manifest["blocked_sections"])
        artifact_status = manifest["construction_package_artifact_status"]
        self.assertTrue(artifact_status["package_present"])
        self.assertEqual(artifact_status["package_identity"], "PKG-IFC-1")
        self.assertTrue(artifact_status["complete_for_release"])
        self.assertEqual(artifact_status["package_model_reference"], "MODEL-FINAL-1")
        self.assertFalse(artifact_status["missing"])
        self.assertFalse(artifact_status["untraced"])
        self.assertTrue(manifest["professional_package_release_status"]["model_matches_package"])
        self.assertTrue(manifest["professional_package_release_status"]["package_matches_review"])
        self.assertTrue(all(section["ready"] for section in manifest["sections"]))

    def test_manifest_blocks_construction_release_in_private_alpha_even_when_gates_pass(self) -> None:
        meta = {
            "product_mode": "private_alpha",
            "construction_readiness": {
                "ready": True,
                "status": "construction_ready",
                "score": 100.0,
                "evidence": {
                    "civil_production_ready": True,
                    "existing_conditions_production_ready": True,
                    "standards_production_usable": True,
                    "export_production_ready": True,
                    "cost_production_usable": True,
                    "professional_release": True,
                },
                "blockers": [],
                "warnings": [],
            },
            "cost_estimate": {
                "success": True,
                "totals": {"production_usable": True, "total_cost": 1000.0, "cost_estimate_hash": "COST-HASH-1"},
                "line_items": [{"metric": "pipe_length_ft", "quantity": 10.0, "amount": 1000.0}],
                "explain": {
                    "cost_estimate_reference": {
                        "cost_estimate_hash": "COST-HASH-1",
                        "quantity_model_hash": "QTY-HASH-1",
                        "price_book_hash": "PRICE-HASH-1",
                    },
                    "quantity_model_reference": {"quantity_model_hash": "QTY-HASH-1"},
                    "pricing": {"price_book_hash": "PRICE-HASH-1"},
                },
            },
            "construction_deliverable_package": {
                "id": "PKG-IFC-1",
                "release_ready": True,
                "production_ready": True,
                "canonical_model_id": "MODEL-FINAL-1",
                "artifacts": [
                    {"type": "sheets", "id": "SHEETS-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cad_export", "id": "CAD-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "qa_report", "id": "QA-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {
                        "type": "cost_estimate",
                        "id": "COST-1",
                        "current": True,
                        "canonical_model_id": "MODEL-FINAL-1",
                        "cost_estimate_hash": "COST-HASH-1",
                    },
                    {"type": "construction_manifest", "id": "MANIFEST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                ],
            },
            "professional_review": _valid_professional_review(),
        }

        manifest = build_construction_package_manifest({"meta": meta})

        self.assertEqual(manifest["release_state"], "blocked_from_construction_release")
        self.assertFalse(manifest["release_allowed"])
        self.assertTrue(manifest["review_package_allowed"])
        self.assertTrue(manifest["construction_release_guard"]["review_only"])
        self.assertIn("professional_release", manifest["blocked_sections"])
        self.assertIn("alpha_review_only_guard", {item["field"] for item in manifest["blockers"]})

    def test_manifest_uses_existing_manifest_alias_as_package_evidence(self) -> None:
        meta = {
            "product_mode": "production",
            "construction_readiness": {
                "ready": True,
                "status": "construction_ready",
                "score": 100.0,
                "evidence": {
                    "civil_production_ready": True,
                    "existing_conditions_production_ready": True,
                    "standards_production_usable": True,
                    "export_production_ready": True,
                    "cost_production_usable": True,
                    "professional_release": True,
                },
                "blockers": [],
                "warnings": [],
            },
            "cost_estimate": {
                "success": True,
                "totals": {"production_usable": True, "total_cost": 1000.0, "cost_estimate_hash": "COST-HASH-1"},
                "line_items": [{"metric": "pipe_length_ft", "quantity": 10.0, "amount": 1000.0}],
                "explain": {
                    "cost_estimate_reference": {
                        "cost_estimate_hash": "COST-HASH-1",
                        "quantity_model_hash": "QTY-HASH-1",
                        "price_book_hash": "PRICE-HASH-1",
                    }
                },
            },
            "construction_package_manifest": {
                "id": "PKG-MANIFEST-1",
                "release_ready": True,
                "production_ready": True,
                "canonical_model_id": "MODEL-FINAL-1",
                "artifacts": [
                    {"type": "sheets", "id": "SHEETS-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cad_export", "id": "CAD-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "qa_report", "id": "QA-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {
                        "type": "cost_estimate",
                        "id": "COST-1",
                        "current": True,
                        "canonical_model_id": "MODEL-FINAL-1",
                        "cost_estimate_hash": "COST-HASH-1",
                    },
                    {"type": "construction_manifest", "id": "MANIFEST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                ],
            },
            "professional_review": _valid_professional_review(package_id="PKG-MANIFEST-1"),
        }

        manifest = build_construction_package_manifest({"meta": meta})

        self.assertEqual(manifest["release_state"], "released_for_construction")
        self.assertEqual(manifest["construction_package_artifact_status"]["package_identity"], "PKG-MANIFEST-1")
        self.assertFalse(manifest["construction_package_artifact_status"]["missing"])
        self.assertTrue(manifest["professional_package_release_status"]["package_matches_review"])

    def test_manifest_blocks_construction_release_when_any_section_needs_review(self) -> None:
        meta = {
            "construction_readiness": {
                "ready": True,
                "status": "construction_ready",
                "score": 96.0,
                "evidence": {
                    "civil_production_ready": True,
                    "existing_conditions_production_ready": True,
                    "standards_production_usable": True,
                    "export_production_ready": True,
                    "cost_production_usable": True,
                    "professional_release": True,
                },
                "blockers": [],
                "warnings": [
                    {
                        "area": "cost",
                        "field": "bid_contingency_review",
                        "why_needed": "Cost estimate needs final bid contingency review.",
                        "suggested_next_action": "Review cost contingency before release.",
                    }
                ],
            },
            "cost_estimate": {
                "success": True,
                "totals": {"production_usable": True, "total_cost": 1000.0, "cost_estimate_hash": "COST-HASH-1"},
                "line_items": [{"metric": "pipe_length_ft", "quantity": 10.0, "amount": 1000.0}],
                "explain": {
                    "cost_estimate_reference": {
                        "cost_estimate_hash": "COST-HASH-1",
                        "quantity_model_hash": "QTY-HASH-1",
                        "price_book_hash": "PRICE-HASH-1",
                    },
                    "quantity_model_reference": {"quantity_model_hash": "QTY-HASH-1"},
                    "pricing": {"price_book_hash": "PRICE-HASH-1"},
                },
            },
            "construction_deliverable_package": {
                "id": "PKG-IFC-1",
                "release_ready": True,
                "production_ready": True,
                "canonical_model_id": "MODEL-FINAL-1",
                "artifacts": [
                    {"type": "sheets", "id": "SHEETS-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cad_export", "id": "CAD-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "qa_report", "id": "QA-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {
                        "type": "cost_estimate",
                        "id": "COST-1",
                        "current": True,
                        "canonical_model_id": "MODEL-FINAL-1",
                        "cost_estimate_hash": "COST-HASH-1",
                    },
                    {"type": "construction_manifest", "id": "MANIFEST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                ],
            },
            "professional_review": _valid_professional_review(),
        }

        manifest = build_construction_package_manifest({"meta": meta})

        self.assertEqual(manifest["release_state"], "blocked_from_construction_release")
        self.assertFalse(manifest["release_allowed"])
        self.assertFalse(manifest["construction_export_allowed"])
        self.assertEqual(manifest["review_sections"], ["cost"])
        self.assertTrue(manifest["review_package_allowed"])

    def test_manifest_blocks_ready_engineering_without_assembled_package_artifacts(self) -> None:
        meta = {
            "construction_readiness": {
                "ready": True,
                "status": "construction_ready",
                "score": 100.0,
                "evidence": {
                    "civil_production_ready": True,
                    "existing_conditions_production_ready": True,
                    "standards_production_usable": True,
                    "export_production_ready": True,
                    "cost_production_usable": True,
                    "professional_release": True,
                },
                "blockers": [],
                "warnings": [],
            }
        }

        manifest = build_construction_package_manifest({"meta": meta})
        fields = {(item["area"], item["field"]) for item in manifest["blockers"]}

        self.assertFalse(manifest["release_allowed"])
        self.assertIn("deliverables", manifest["blocked_sections"])
        self.assertIn(("deliverables", "construction_package_artifacts"), fields)
        artifact_status = manifest["construction_package_artifact_status"]
        self.assertFalse(artifact_status["package_present"])
        self.assertEqual(artifact_status["artifact_count"], 0)
        self.assertEqual(artifact_status["review_package_state"], "review_only_incomplete")

    def test_manifest_blocks_stale_construction_package_artifacts(self) -> None:
        meta = {
            "construction_readiness": {
                "ready": True,
                "status": "construction_ready",
                "score": 100.0,
                "evidence": {
                    "civil_production_ready": True,
                    "existing_conditions_production_ready": True,
                    "standards_production_usable": True,
                    "export_production_ready": True,
                    "cost_production_usable": True,
                    "professional_release": True,
                },
                "blockers": [],
                "warnings": [],
            },
            "construction_deliverable_package": {
                "release_ready": True,
                "production_ready": True,
                "canonical_model_id": "MODEL-FINAL-1",
                "artifacts": [
                    {"type": "sheets", "id": "SHEETS-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cad_export", "id": "CAD-1", "stale": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "qa_report", "id": "QA-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cost_estimate", "id": "COST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "construction_manifest", "id": "MANIFEST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                ],
            },
        }

        manifest = build_construction_package_manifest({"meta": meta})
        fields = {(item["area"], item["field"]) for item in manifest["blockers"]}

        self.assertFalse(manifest["release_allowed"])
        self.assertIn(("deliverables", "stale_construction_package_artifacts"), fields)
        self.assertEqual(manifest["construction_package_artifact_status"]["stale"], ["CAD-1"])

    def test_manifest_blocks_package_without_final_model_reference(self) -> None:
        meta = {
            "construction_readiness": {
                "ready": True,
                "status": "construction_ready",
                "score": 100.0,
                "evidence": {
                    "civil_production_ready": True,
                    "existing_conditions_production_ready": True,
                    "standards_production_usable": True,
                    "export_production_ready": True,
                    "cost_production_usable": True,
                    "professional_release": True,
                },
                "blockers": [],
                "warnings": [],
            },
            "construction_deliverable_package": {
                "release_ready": True,
                "production_ready": True,
                "artifacts": [
                    {"type": "sheets", "id": "SHEETS-1", "current": True},
                    {"type": "cad_export", "id": "CAD-1", "current": True},
                    {"type": "qa_report", "id": "QA-1", "current": True},
                    {"type": "cost_estimate", "id": "COST-1", "current": True},
                    {"type": "construction_manifest", "id": "MANIFEST-1", "current": True},
                ],
            },
        }

        manifest = build_construction_package_manifest({"meta": meta})
        fields = {(item["area"], item["field"]) for item in manifest["blockers"]}

        self.assertFalse(manifest["release_allowed"])
        self.assertIn(("deliverables", "construction_package_model_reference"), fields)
        artifact_status = manifest["construction_package_artifact_status"]
        self.assertFalse(artifact_status["model_reference_present"])
        self.assertFalse(artifact_status["complete_for_release"])

    def test_manifest_blocks_untraced_and_mismatched_package_artifacts(self) -> None:
        meta = {
            "construction_readiness": {
                "ready": True,
                "status": "construction_ready",
                "score": 100.0,
                "evidence": {
                    "civil_production_ready": True,
                    "existing_conditions_production_ready": True,
                    "standards_production_usable": True,
                    "export_production_ready": True,
                    "cost_production_usable": True,
                    "professional_release": True,
                },
                "blockers": [],
                "warnings": [],
            },
            "construction_deliverable_package": {
                "release_ready": True,
                "production_ready": True,
                "canonical_model_id": "MODEL-FINAL-1",
                "artifacts": [
                    {"type": "sheets", "id": "SHEETS-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cad_export", "id": "CAD-1", "current": True},
                    {"type": "qa_report", "id": "QA-1", "current": True, "canonical_model_id": "MODEL-OLD"},
                    {"type": "cost_estimate", "id": "COST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "construction_manifest", "id": "MANIFEST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                ],
            },
        }

        manifest = build_construction_package_manifest({"meta": meta})
        fields = {(item["area"], item["field"]) for item in manifest["blockers"]}

        self.assertFalse(manifest["release_allowed"])
        self.assertIn(("deliverables", "untraced_construction_package_artifacts"), fields)
        self.assertIn(("deliverables", "mismatched_construction_package_artifacts"), fields)
        artifact_status = manifest["construction_package_artifact_status"]
        self.assertEqual(artifact_status["untraced"], ["CAD-1"])
        self.assertEqual(artifact_status["mismatched"], ["QA-1"])

    def test_manifest_blocks_anonymous_package_artifacts(self) -> None:
        meta = {
            "construction_readiness": {
                "ready": True,
                "status": "construction_ready",
                "score": 100.0,
                "evidence": {
                    "civil_production_ready": True,
                    "existing_conditions_production_ready": True,
                    "standards_production_usable": True,
                    "export_production_ready": True,
                    "cost_production_usable": True,
                    "professional_release": True,
                },
                "blockers": [],
                "warnings": [],
            },
            "construction_deliverable_package": {
                "release_ready": True,
                "production_ready": True,
                "canonical_model_id": "MODEL-FINAL-1",
                "artifacts": [
                    {"type": "sheets", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cad_export", "id": "CAD-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "qa_report", "id": "QA-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cost_estimate", "id": "COST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "construction_manifest", "id": "MANIFEST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                ],
            },
        }

        manifest = build_construction_package_manifest({"meta": meta})
        fields = {(item["area"], item["field"]) for item in manifest["blockers"]}

        self.assertFalse(manifest["release_allowed"])
        self.assertIn(("deliverables", "construction_package_artifact_identity"), fields)
        self.assertEqual(manifest["construction_package_artifact_status"]["anonymous"], ["sheets"])

    def test_manifest_blocks_package_without_stable_package_identity(self) -> None:
        meta = {
            "construction_readiness": {
                "ready": True,
                "status": "construction_ready",
                "score": 100.0,
                "evidence": {
                    "civil_production_ready": True,
                    "existing_conditions_production_ready": True,
                    "standards_production_usable": True,
                    "export_production_ready": True,
                    "cost_production_usable": True,
                    "professional_release": True,
                },
                "blockers": [],
                "warnings": [],
            },
            "construction_deliverable_package": {
                "release_ready": True,
                "production_ready": True,
                "canonical_model_id": "MODEL-FINAL-1",
                "artifacts": [
                    {"type": "sheets", "id": "SHEETS-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cad_export", "id": "CAD-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "qa_report", "id": "QA-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cost_estimate", "id": "COST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "construction_manifest", "id": "MANIFEST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                ],
            },
            "professional_review": {
                "canonical_model_id": "MODEL-FINAL-1",
                "reviewed_package_id": "PKG-MISSING",
            },
        }

        manifest = build_construction_package_manifest({"meta": meta})
        fields = {(item["area"], item["field"]) for item in manifest["blockers"]}

        self.assertFalse(manifest["release_allowed"])
        self.assertIn(("deliverables", "construction_package_identity"), fields)
        self.assertFalse(manifest["construction_package_artifact_status"]["package_identity_present"])

    def test_manifest_blocks_package_without_explicit_release_ready_flag(self) -> None:
        meta = {
            "construction_readiness": {
                "ready": True,
                "status": "construction_ready",
                "score": 100.0,
                "evidence": {
                    "civil_production_ready": True,
                    "existing_conditions_production_ready": True,
                    "standards_production_usable": True,
                    "export_production_ready": True,
                    "cost_production_usable": True,
                    "professional_release": True,
                },
                "blockers": [],
                "warnings": [],
            },
            "cost_estimate": {
                "success": True,
                "totals": {"production_usable": True, "total_cost": 1000.0, "cost_estimate_hash": "COST-HASH-1"},
                "line_items": [{"metric": "pipe_length_ft", "quantity": 10.0, "amount": 1000.0}],
                "explain": {
                    "cost_estimate_reference": {
                        "cost_estimate_hash": "COST-HASH-1",
                        "quantity_model_hash": "QTY-HASH-1",
                        "price_book_hash": "PRICE-HASH-1",
                    },
                    "quantity_model_reference": {"quantity_model_hash": "QTY-HASH-1"},
                    "pricing": {"price_book_hash": "PRICE-HASH-1"},
                },
            },
            "construction_deliverable_package": {
                "id": "PKG-IFC-1",
                "canonical_model_id": "MODEL-FINAL-1",
                "artifacts": [
                    {"type": "sheets", "id": "SHEETS-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cad_export", "id": "CAD-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "qa_report", "id": "QA-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {
                        "type": "cost_estimate",
                        "id": "COST-1",
                        "current": True,
                        "canonical_model_id": "MODEL-FINAL-1",
                        "cost_estimate_hash": "COST-HASH-1",
                    },
                    {"type": "construction_manifest", "id": "MANIFEST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                ],
            },
            "professional_review": _valid_professional_review(),
        }

        manifest = build_construction_package_manifest({"meta": meta})
        fields = {(item["area"], item["field"]) for item in manifest["blockers"]}

        self.assertFalse(manifest["release_allowed"])
        self.assertIn(("deliverables", "construction_package_release_ready"), fields)
        artifact_status = manifest["construction_package_artifact_status"]
        self.assertIsNone(artifact_status["release_ready_flag"])
        self.assertFalse(artifact_status["complete_for_release"])

    def test_manifest_blocks_package_without_explicit_production_ready_flag(self) -> None:
        meta = {
            "construction_readiness": {
                "ready": True,
                "status": "construction_ready",
                "score": 100.0,
                "evidence": {
                    "civil_production_ready": True,
                    "existing_conditions_production_ready": True,
                    "standards_production_usable": True,
                    "export_production_ready": True,
                    "cost_production_usable": True,
                    "professional_release": True,
                },
                "blockers": [],
                "warnings": [],
            },
            "cost_estimate": {
                "success": True,
                "totals": {"production_usable": True, "total_cost": 1000.0, "cost_estimate_hash": "COST-HASH-1"},
                "line_items": [{"metric": "pipe_length_ft", "quantity": 10.0, "amount": 1000.0}],
                "explain": {
                    "cost_estimate_reference": {
                        "cost_estimate_hash": "COST-HASH-1",
                        "quantity_model_hash": "QTY-HASH-1",
                        "price_book_hash": "PRICE-HASH-1",
                    },
                    "quantity_model_reference": {"quantity_model_hash": "QTY-HASH-1"},
                    "pricing": {"price_book_hash": "PRICE-HASH-1"},
                },
            },
            "construction_deliverable_package": {
                "id": "PKG-IFC-1",
                "release_ready": True,
                "canonical_model_id": "MODEL-FINAL-1",
                "artifacts": [
                    {"type": "sheets", "id": "SHEETS-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cad_export", "id": "CAD-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "qa_report", "id": "QA-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {
                        "type": "cost_estimate",
                        "id": "COST-1",
                        "current": True,
                        "canonical_model_id": "MODEL-FINAL-1",
                        "cost_estimate_hash": "COST-HASH-1",
                    },
                    {"type": "construction_manifest", "id": "MANIFEST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                ],
            },
            "professional_review": _valid_professional_review(),
        }

        manifest = build_construction_package_manifest({"meta": meta})
        fields = {(item["area"], item["field"]) for item in manifest["blockers"]}

        self.assertFalse(manifest["release_allowed"])
        self.assertIn(("deliverables", "construction_package_production_ready"), fields)
        artifact_status = manifest["construction_package_artifact_status"]
        self.assertIsNone(artifact_status["production_ready_flag"])
        self.assertFalse(artifact_status["complete_for_release"])

    def test_manifest_blocks_professional_release_not_tied_to_final_package(self) -> None:
        meta = {
            "construction_readiness": {
                "ready": True,
                "status": "construction_ready",
                "score": 100.0,
                "evidence": {
                    "civil_production_ready": True,
                    "existing_conditions_production_ready": True,
                    "standards_production_usable": True,
                    "export_production_ready": True,
                    "cost_production_usable": True,
                    "professional_release": True,
                },
                "blockers": [],
                "warnings": [],
            },
            "construction_deliverable_package": {
                "id": "PKG-IFC-1",
                "release_ready": True,
                "production_ready": True,
                "canonical_model_id": "MODEL-FINAL-1",
                "artifacts": [
                    {"type": "sheets", "id": "SHEETS-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cad_export", "id": "CAD-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "qa_report", "id": "QA-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cost_estimate", "id": "COST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "construction_manifest", "id": "MANIFEST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                ],
            },
            "professional_review": _valid_professional_review(model_id="MODEL-OLD", package_id="PKG-OLD"),
        }

        manifest = build_construction_package_manifest({"meta": meta})
        fields = {(item["area"], item["field"]) for item in manifest["blockers"]}

        self.assertFalse(manifest["release_allowed"])
        self.assertIn(("professional_review", "released_model_mismatch"), fields)
        self.assertIn(("professional_review", "released_package_mismatch"), fields)
        self.assertFalse(manifest["professional_package_release_status"]["model_matches_package"])
        self.assertFalse(manifest["professional_package_release_status"]["package_matches_review"])

    def test_manifest_blocks_package_model_reference_that_does_not_match_final_plan(self) -> None:
        plan = {
            "project_name": "Final Model Package",
            "actions": [
                {
                    "task": "rectangle",
                    "layer": "SITE",
                    "canonical_source_id": "site-1",
                    "canonical_source_type": "site",
                }
            ],
            "meta": {
                "revision": "IFC-1",
                "issue_date": "2026-05-29",
                "construction_readiness": {
                    "ready": True,
                    "status": "construction_ready",
                    "score": 100.0,
                    "evidence": {
                        "civil_production_ready": True,
                        "existing_conditions_production_ready": True,
                        "standards_production_usable": True,
                        "export_production_ready": True,
                        "cost_production_usable": True,
                        "professional_release": True,
                    },
                    "blockers": [],
                    "warnings": [],
                },
                "construction_deliverable_package": {
                    "id": "PKG-IFC-1",
                    "release_ready": True,
                    "production_ready": True,
                    "canonical_model_id": "MODEL-OLD",
                    "artifacts": [
                        {"type": "sheets", "id": "SHEETS-1", "current": True, "canonical_model_id": "MODEL-OLD"},
                        {"type": "cad_export", "id": "CAD-1", "current": True, "canonical_model_id": "MODEL-OLD"},
                        {"type": "qa_report", "id": "QA-1", "current": True, "canonical_model_id": "MODEL-OLD"},
                        {"type": "cost_estimate", "id": "COST-1", "current": True, "canonical_model_id": "MODEL-OLD"},
                        {"type": "construction_manifest", "id": "MANIFEST-1", "current": True, "canonical_model_id": "MODEL-OLD"},
                    ],
                },
                "professional_review": {
                    "canonical_model_id": "MODEL-OLD",
                    "reviewed_package_id": "PKG-IFC-1",
                },
            },
        }

        manifest = build_construction_package_manifest(plan)
        fields = {(item["area"], item["field"]) for item in manifest["blockers"]}

        self.assertFalse(manifest["release_allowed"])
        self.assertTrue(manifest["expected_canonical_model_reference"].startswith("plan-sha256:"))
        self.assertIn(("deliverables", "construction_package_model_mismatch"), fields)
        self.assertFalse(manifest["construction_package_artifact_status"]["model_matches_expected"])

    def test_manifest_allows_package_matching_final_plan_fingerprint(self) -> None:
        plan = {
            "project_name": "Final Model Package",
            "actions": [
                {
                    "task": "rectangle",
                    "layer": "SITE",
                    "canonical_source_id": "site-1",
                    "canonical_source_type": "site",
                }
            ],
            "meta": {
                "product_mode": "production",
                "revision": "IFC-1",
                "issue_date": "2026-05-29",
                "construction_readiness": {
                    "ready": True,
                    "status": "construction_ready",
                    "score": 100.0,
                    "evidence": {
                        "civil_production_ready": True,
                        "existing_conditions_production_ready": True,
                        "standards_production_usable": True,
                        "export_production_ready": True,
                        "cost_production_usable": True,
                        "professional_release": True,
                    },
                    "blockers": [],
                    "warnings": [],
                },
            },
        }
        expected = build_construction_package_manifest(plan)["expected_canonical_model_reference"]
        plan["meta"]["cost_estimate"] = {
            "success": True,
            "totals": {"production_usable": True, "total_cost": 1000.0, "cost_estimate_hash": "COST-HASH-1"},
            "line_items": [{"metric": "pipe_length_ft", "quantity": 10.0, "amount": 1000.0}],
            "explain": {
                "cost_estimate_reference": {
                    "cost_estimate_hash": "COST-HASH-1",
                    "quantity_model_hash": "QTY-HASH-1",
                    "price_book_hash": "PRICE-HASH-1",
                },
                "quantity_model_reference": {"quantity_model_hash": "QTY-HASH-1"},
                "pricing": {"price_book_hash": "PRICE-HASH-1"},
            },
        }
        plan["meta"]["construction_deliverable_package"] = {
            "id": "PKG-IFC-1",
            "release_ready": True,
            "production_ready": True,
            "canonical_model_id": expected,
            "artifacts": [
                {"type": "sheets", "id": "SHEETS-1", "current": True, "canonical_model_id": expected},
                {"type": "cad_export", "id": "CAD-1", "current": True, "canonical_model_id": expected},
                {"type": "qa_report", "id": "QA-1", "current": True, "canonical_model_id": expected},
                {
                    "type": "cost_estimate",
                    "id": "COST-1",
                    "current": True,
                    "canonical_model_id": expected,
                    "cost_estimate_hash": "COST-HASH-1",
                },
                {"type": "construction_manifest", "id": "MANIFEST-1", "current": True, "canonical_model_id": expected},
            ],
        }
        plan["meta"]["professional_review"] = _valid_professional_review(model_id=expected)

        manifest = build_construction_package_manifest(plan)

        self.assertTrue(manifest["release_allowed"])
        self.assertEqual(manifest["expected_canonical_model_reference"], expected)
        artifact_status = manifest["construction_package_artifact_status"]
        self.assertTrue(artifact_status["model_matches_expected"])
        self.assertTrue(artifact_status["complete_for_release"])
        self.assertTrue(manifest["professional_package_release_status"]["model_matches_package"])
        self.assertTrue(manifest["professional_package_release_status"]["professional_release_valid"])

    def test_manifest_blocks_professional_reference_without_valid_release_metadata(self) -> None:
        meta = {
            "construction_readiness": {
                "ready": True,
                "status": "construction_ready",
                "score": 100.0,
                "evidence": {
                    "civil_production_ready": True,
                    "existing_conditions_production_ready": True,
                    "standards_production_usable": True,
                    "export_production_ready": True,
                    "cost_production_usable": True,
                    "professional_release": True,
                },
                "blockers": [],
                "warnings": [],
            },
            "cost_estimate": {
                "success": True,
                "totals": {"production_usable": True, "total_cost": 1000.0, "cost_estimate_hash": "COST-HASH-1"},
                "line_items": [{"metric": "pipe_length_ft", "quantity": 10.0, "amount": 1000.0}],
                "explain": {
                    "cost_estimate_reference": {
                        "cost_estimate_hash": "COST-HASH-1",
                        "quantity_model_hash": "QTY-HASH-1",
                        "price_book_hash": "PRICE-HASH-1",
                    },
                    "quantity_model_reference": {"quantity_model_hash": "QTY-HASH-1"},
                    "pricing": {"price_book_hash": "PRICE-HASH-1"},
                },
            },
            "construction_deliverable_package": {
                "id": "PKG-IFC-1",
                "release_ready": True,
                "production_ready": True,
                "canonical_model_id": "MODEL-FINAL-1",
                "artifacts": [
                    {"type": "sheets", "id": "SHEETS-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cad_export", "id": "CAD-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "qa_report", "id": "QA-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {
                        "type": "cost_estimate",
                        "id": "COST-1",
                        "current": True,
                        "canonical_model_id": "MODEL-FINAL-1",
                        "cost_estimate_hash": "COST-HASH-1",
                    },
                    {"type": "construction_manifest", "id": "MANIFEST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                ],
            },
            "professional_review": {
                "canonical_model_id": "MODEL-FINAL-1",
                "reviewed_package_id": "PKG-IFC-1",
            },
        }

        manifest = build_construction_package_manifest({"meta": meta})
        fields = {(item["area"], item["field"]) for item in manifest["blockers"]}

        self.assertFalse(manifest["release_allowed"])
        self.assertIn(("professional_review", "professional_release_validation"), fields)
        self.assertFalse(manifest["professional_package_release_status"]["professional_release_valid"])

    def test_manifest_blocks_cost_artifact_not_tied_to_current_cost_estimate(self) -> None:
        meta = {
            "construction_readiness": {
                "ready": True,
                "status": "construction_ready",
                "score": 100.0,
                "evidence": {
                    "civil_production_ready": True,
                    "existing_conditions_production_ready": True,
                    "standards_production_usable": True,
                    "export_production_ready": True,
                    "cost_production_usable": True,
                    "professional_release": True,
                },
                "blockers": [],
                "warnings": [],
            },
            "cost_estimate": {
                "success": True,
                "totals": {"production_usable": True, "total_cost": 1000.0, "cost_estimate_hash": "COST-HASH-1"},
                "line_items": [{"metric": "pipe_length_ft", "quantity": 10.0, "amount": 1000.0}],
                "explain": {
                    "cost_estimate_reference": {
                        "cost_estimate_hash": "COST-HASH-1",
                        "quantity_model_hash": "QTY-HASH-1",
                        "price_book_hash": "PRICE-HASH-1",
                    },
                    "quantity_model_reference": {"quantity_model_hash": "QTY-HASH-1"},
                    "pricing": {"price_book_hash": "PRICE-HASH-1"},
                },
            },
            "construction_deliverable_package": {
                "id": "PKG-IFC-1",
                "release_ready": True,
                "production_ready": True,
                "canonical_model_id": "MODEL-FINAL-1",
                "artifacts": [
                    {"type": "sheets", "id": "SHEETS-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cad_export", "id": "CAD-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "qa_report", "id": "QA-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cost_estimate", "id": "COST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "construction_manifest", "id": "MANIFEST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                ],
            },
            "professional_review": _valid_professional_review(),
        }

        manifest = build_construction_package_manifest({"meta": meta})
        fields = {(item["area"], item["field"]) for item in manifest["blockers"]}

        self.assertFalse(manifest["release_allowed"])
        self.assertIn(("cost", "cost_estimate_artifact_traceability"), fields)
        artifact_status = manifest["construction_package_artifact_status"]
        self.assertEqual(artifact_status["cost_untraced"], ["COST-1"])
        self.assertFalse(artifact_status["complete_for_release"])

    def test_manifest_accepts_cost_artifact_matching_current_cost_estimate(self) -> None:
        meta = {
            "product_mode": "production",
            "construction_readiness": {
                "ready": True,
                "status": "construction_ready",
                "score": 100.0,
                "evidence": {
                    "civil_production_ready": True,
                    "existing_conditions_production_ready": True,
                    "standards_production_usable": True,
                    "export_production_ready": True,
                    "cost_production_usable": True,
                    "professional_release": True,
                },
                "blockers": [],
                "warnings": [],
            },
            "cost_estimate": {
                "success": True,
                "totals": {"production_usable": True, "total_cost": 1000.0, "cost_estimate_hash": "COST-HASH-1"},
                "line_items": [{"metric": "pipe_length_ft", "quantity": 10.0, "amount": 1000.0}],
                "explain": {
                    "cost_estimate_reference": {
                        "cost_estimate_hash": "COST-HASH-1",
                        "quantity_model_hash": "QTY-HASH-1",
                        "price_book_hash": "PRICE-HASH-1",
                    },
                    "quantity_model_reference": {"quantity_model_hash": "QTY-HASH-1"},
                    "pricing": {"price_book_hash": "PRICE-HASH-1"},
                },
            },
            "construction_deliverable_package": {
                "id": "PKG-IFC-1",
                "release_ready": True,
                "production_ready": True,
                "canonical_model_id": "MODEL-FINAL-1",
                "artifacts": [
                    {"type": "sheets", "id": "SHEETS-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "cad_export", "id": "CAD-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {"type": "qa_report", "id": "QA-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                    {
                        "type": "cost_estimate",
                        "id": "COST-1",
                        "current": True,
                        "canonical_model_id": "MODEL-FINAL-1",
                        "cost_estimate_hash": "COST-HASH-1",
                    },
                    {"type": "construction_manifest", "id": "MANIFEST-1", "current": True, "canonical_model_id": "MODEL-FINAL-1"},
                ],
            },
            "professional_review": _valid_professional_review(),
        }

        manifest = build_construction_package_manifest({"meta": meta})

        self.assertTrue(manifest["release_allowed"])
        artifact_status = manifest["construction_package_artifact_status"]
        self.assertFalse(artifact_status["cost_untraced"])
        self.assertFalse(artifact_status["cost_mismatched"])

    def test_construction_document_support_package_scope_matrix_is_review_only(self) -> None:
        meta = {
            "grading": {"status": "ready"},
            "drainage": {"status": "ready"},
            "utilities": {"status": "ready"},
            "profiles": [{"profile_id": "P-1"}],
            "quantities": {"success": True},
            "assumptions": [{"field_name": "runoff_coefficient", "assumed_value": 0.75}],
            "standards_package": {"status": "ready", "production_usable": True},
            "existing_conditions_package": {"status": "ready", "production_ready": True},
            "engineer_review_package": {
                "review_status": "ready_for_engineer_review",
                "approval_checklist": [
                    {"item_id": "calculations_reviewed", "status": "manual_required"},
                    {"item_id": "external_engineer_approval_record", "status": "manual_required"},
                ],
            },
            "construction_readiness": {
                "ready": False,
                "blockers": [
                    {
                        "area": "profile_section",
                        "field": "cross_sections",
                        "reason": "Cross sections were requested but are missing.",
                    }
                ],
            },
        }

        package = build_construction_document_support_package({"actions": [{"task": "draw_site_plan"}], "meta": meta})

        self.assertEqual(package["version"], "construction_document_support_package_v1")
        self.assertTrue(package["engineer_review_required"])
        self.assertTrue(package["engineer_approval_required"])
        self.assertFalse(package["construction_approval"])
        self.assertFalse(package["construction_release_allowed"])
        self.assertFalse(package["construction_export_allowed"])
        self.assertFalse(package["civora_engineer_of_record"])
        self.assertFalse(package["civora_signoff_allowed"])
        self.assertIn("never stamps, seals, signs", package["truth_label"])

        matrix = package["section_status_matrix"]
        self.assertEqual(matrix["site_plan"], "included")
        self.assertEqual(matrix["grading_plan"], "included")
        self.assertEqual(matrix["drainage_plan"], "included")
        self.assertEqual(matrix["utility_plan"], "included")
        self.assertEqual(matrix["profiles"], "included")
        self.assertEqual(matrix["sections"], "blocked")
        self.assertEqual(matrix["quantities"], "included")
        self.assertEqual(matrix["assumptions"], "review_required")
        self.assertEqual(matrix["standards_sources"], "review_required")
        self.assertEqual(matrix["existing_conditions"], "review_required")
        self.assertEqual(matrix["engineer_review_checklist"], "review_required")
        self.assertEqual(set(matrix.values()).issubset({"included", "missing", "blocked", "review_required"}), True)

    def test_build_plan_attaches_construction_document_support_package(self) -> None:
        plan = planner.build_plan(
            {
                "project_name": "Construction Document Support Smoke",
                "units": "ft",
                "mode": "site_plan",
                "lot": {"x": 0.0, "y": 0.0, "w": 120.0, "h": 100.0},
                "site_plan": {"building_width": 40.0, "building_depth": 30.0, "parking_count": 12},
            }
        )

        package = plan["meta"]["construction_document_support_package_v1"]

        self.assertEqual(package["source"], "construction_document_support_package_v1")
        self.assertTrue(package["engineer_review_required"])
        self.assertFalse(package["construction_approval"])
        self.assertFalse(package["construction_release_allowed"])
        self.assertIn("site_plan", package["section_status_matrix"])
        self.assertIn("engineer_review_checklist", package["section_status_matrix"])

    def test_construction_document_support_package_preserves_section_traceability(self) -> None:
        meta = {
            "layout": {
                "status": "ready",
                "canonical_id": "LAYOUT-1",
                "canonical_source_id": "SITE-PLAN-1",
            },
            "grading": {
                "status": "ready",
                "surface_id": "SURF-1",
                "canonical_model_id": "MODEL-1",
            },
            "profiles": [{"profile_id": "PROF-1", "canonical_ids": ["ALIGN-1"]}],
            "assumptions": [{"field_name": "runoff_coefficient", "canonical_source_id": "ASSUME-1"}],
            "export_package_report_v1": {
                "source": "export_package_report_v1",
                "canonical_ids_included": ["MODEL-1"],
                "stale_outputs_detected": ["grading"],
                "profile_packages": [
                    {
                        "record_id": "PROFILE-PKG-1",
                        "canonical_ids": ["PROF-1", "ALIGN-1"],
                    }
                ],
            },
            "export_audit": {
                "ready": False,
                "stale_output_status": {"dirty_stages": ["grading"]},
            },
            "engineer_review_package": {
                "review_status": "ready_for_engineer_review",
                "approval_checklist": [
                    {"item_id": "external_engineer_approval_record", "status": "manual_required"}
                ],
            },
        }

        package = build_construction_document_support_package({"meta": meta})
        sections = {section["section_id"]: section for section in package["sections"]}

        site = sections["site_plan"]
        self.assertEqual(site["status"], "included")
        self.assertIn("LAYOUT-1", site["canonical_ids"])
        self.assertIn("SITE-PLAN-1", site["canonical_ids"])
        self.assertEqual(site["source_evidence_references"][0]["key"], "layout")

        profiles = sections["profiles"]
        self.assertEqual(profiles["status"], "included")
        self.assertIn("PROF-1", profiles["canonical_ids"])
        self.assertIn("ALIGN-1", profiles["canonical_ids"])
        self.assertEqual(profiles["linked_export_report_artifacts"][0]["linked_record_key"], "profile_packages")
        self.assertEqual(profiles["linked_export_report_artifacts"][0]["linked_record_count"], 1)

        utilities = sections["utility_plan"]
        self.assertEqual(utilities["status"], "missing")
        self.assertTrue(utilities["missing_inputs"])
        self.assertTrue(utilities["blockers"])
        self.assertTrue(all(item["severity"] == "missing_input" for item in utilities["blockers"]))

        grading = sections["grading_plan"]
        self.assertEqual(grading["status"], "blocked")
        self.assertEqual(grading["confidence"], "stale_or_dirty")
        self.assertTrue(grading["stale_dirty_status"]["dirty"])
        self.assertIn("stale_dirty_evidence_requires_rerun_or_engineer_review", grading["review_reasons"])

        assumptions = sections["assumptions"]
        self.assertEqual(assumptions["status"], "review_required")
        self.assertIn("assumptions_require_engineer_acceptance", assumptions["review_required_reason"])

        checklist = sections["engineer_review_checklist"]
        self.assertEqual(checklist["status"], "review_required")
        self.assertIn("external_engineer_approval_record", checklist["review_required_reason"])

        self.assertFalse(package["construction_approval"])
        self.assertFalse(package["construction_release_allowed"])
        self.assertFalse(package["construction_export_allowed"])
        self.assertFalse(package["civora_approval_authority"])
        self.assertFalse(package["civora_engineer_of_record"])
        self.assertNotIn("ready_for_construction", package)


if __name__ == "__main__":
    unittest.main()
