import unittest

import planner
from backend.planning.construction_package import build_construction_package_manifest


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

    def test_manifest_allows_release_only_when_construction_gate_is_ready(self) -> None:
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
            "professional_review": {
                "status": "released_for_construction",
                "sealed": True,
                "engineer_name": "Alex Morgan",
                "license_number": "TX-123456",
                "review_date": "2026-05-29",
                "jurisdiction": "Test City",
                "license_jurisdiction": "TX",
                "discipline": "civil",
                "review_scope": "civil_site_construction_documents",
                "canonical_model_id": "MODEL-FINAL-1",
                "reviewed_package_id": "PKG-IFC-1",
            },
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
                "canonical_model_id": "MODEL-OLD",
                "reviewed_package_id": "PKG-OLD",
            },
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
        plan["meta"]["professional_review"] = {
            "canonical_model_id": expected,
            "reviewed_package_id": "PKG-IFC-1",
        }

        manifest = build_construction_package_manifest(plan)

        self.assertTrue(manifest["release_allowed"])
        self.assertEqual(manifest["expected_canonical_model_reference"], expected)
        artifact_status = manifest["construction_package_artifact_status"]
        self.assertTrue(artifact_status["model_matches_expected"])
        self.assertTrue(artifact_status["complete_for_release"])
        self.assertTrue(manifest["professional_package_release_status"]["model_matches_package"])

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
                "reviewed_package_id": "PKG-IFC-1",
            },
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
            "professional_review": {
                "canonical_model_id": "MODEL-FINAL-1",
                "reviewed_package_id": "PKG-IFC-1",
            },
        }

        manifest = build_construction_package_manifest({"meta": meta})

        self.assertTrue(manifest["release_allowed"])
        artifact_status = manifest["construction_package_artifact_status"]
        self.assertFalse(artifact_status["cost_untraced"])
        self.assertFalse(artifact_status["cost_mismatched"])


if __name__ == "__main__":
    unittest.main()
