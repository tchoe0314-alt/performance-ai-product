import unittest

from backend.planning.engineer_review_package import build_engineer_review_package


def _ready_meta() -> dict:
    return {
        "project_id": "project-review-1",
        "standards_package": {
            "version": "standards_package_v1",
            "status": "ready",
            "production_usable": True,
            "construction_release_blocked": False,
            "accepted_rule_count": 2,
            "official_source_count": 1,
            "blockers": [],
            "standards_acceptance_report": {
                "qa_status": "ready",
                "rules": {
                    "accepted_rule_ids": ["storm-001", "water-001"],
                    "inferred_rule_ids": [],
                    "missing_rules": [],
                },
                "reviewer_comments": [
                    {
                        "area": "standards",
                        "field": "storm-001",
                        "comment": "Confirm local drainage manual edition during engineer review.",
                        "severity": "review",
                    }
                ],
            },
        },
        "existing_conditions_package": {
            "version": "existing_conditions_package_v1",
            "status": "ready",
            "production_ready": True,
            "review_usable": True,
            "accepted": True,
            "survey_ready": True,
            "gis_ready": True,
            "coordinate_system_ready": True,
            "metadata_only": False,
            "source_count": 3,
            "gate": {"terrain_source_confidence": "survey_surface"},
            "blockers": [],
            "warnings": [],
        },
        "engine_readiness": {
            "summary": {
                "alpha_readiness": {
                    "status": "ready",
                    "ready_engine_count": 20,
                    "applicable_engine_count": 20,
                    "blocked_engine_ids": [],
                    "needs_review_engine_ids": [],
                }
            }
        },
        "depth_validation": {
            "stormwater": {"production_ready": True, "blockers": [], "canonical_model_id": "MODEL-FINAL-1"},
            "water": {"production_ready": True, "blockers": [], "canonical_model_id": "MODEL-FINAL-1"},
            "roadway_corridor": {"production_ready": True, "blockers": [], "canonical_model_id": "MODEL-FINAL-1"},
        },
        "review_package_manifest": {
            "source": "review_package_manifest_v1",
            "review_ready": True,
            "review_package_id": "REVIEW-PKG-1",
            "construction_release_blocked": True,
        },
        "export_audit": {
            "ready": True,
            "production_export_ready": True,
            "export_blocked": False,
        },
        "quantities": {
            "success": True,
            "status": "ready",
            "explain": {"meta_summary": {"quantity_traceability_complete": True}},
        },
        "cost_estimate": {
            "success": True,
            "status": "ready",
            "explain": {"cost_estimate_reference": {"cost_estimate_hash": "COST-HASH-1"}},
        },
        "calculation_artifacts": [
            {
                "artifact_id": "storm_hydraulics",
                "status": "ready",
                "trace": {"pipe_ids": ["STM-1"]},
            }
        ],
    }


class EngineerReviewPackageTests(unittest.TestCase):
    def test_missing_standards_imports_depth_and_exports_blocks_package(self) -> None:
        package = build_engineer_review_package({"meta": {"project_id": "missing-gates"}})

        self.assertEqual(package["version"], "engineer_review_package_v1")
        self.assertEqual(package["review_status"], "blocked")
        self.assertTrue(package["required_engineer_review"])
        self.assertTrue(package["construction_release_blocked"])
        self.assertFalse(package["construction_release_allowed"])
        fields = {(item["area"], item["field"]) for item in package["blockers"]}
        self.assertIn(("standards", "standards_package"), fields)
        self.assertIn(("existing_conditions", "existing_conditions_package"), fields)
        self.assertIn(("depth_validation", "engine_depth_evidence"), fields)
        self.assertIn(("deliverables", "export_package"), fields)

    def test_ready_for_engineer_review_still_requires_external_engineer_approval(self) -> None:
        package = build_engineer_review_package({"meta": _ready_meta()})

        self.assertEqual(package["review_status"], "ready_for_engineer_review")
        self.assertTrue(package["ready_for_engineer_review"])
        self.assertFalse(package["ready_for_construction"])
        self.assertFalse(package["blockers"])
        self.assertIn("engineer_approval", package["missing_inputs_by_gate"])
        self.assertEqual(
            package["missing_inputs_by_gate"]["engineer_approval"][0]["field"],
            "external_engineer_approval_record",
        )
        self.assertTrue(package["automated_gates_review_ready"])
        self.assertTrue(package["required_engineer_review"])
        self.assertTrue(package["engineer_approval_required"])
        self.assertFalse(package["civora_signoff_allowed"])
        self.assertFalse(package["civora_engineer_of_record"])
        self.assertFalse(package["civora_approval_authority"])
        self.assertFalse(package["construction_release_allowed_by_civora"])
        self.assertFalse(package["simulated_seal_allowed"])
        self.assertFalse(package["simulated_signature_allowed"])
        self.assertEqual(package["ready_language"], "ready_for_engineer_review")
        self.assertIn("review handoff", package["truth_label"])
        self.assertIn("simulated seal/signature", package["truth_label"])
        self.assertTrue(package["construction_release_blocked"])
        self.assertFalse(package["construction_release_allowed"])
        checklist = {item["item_id"]: item for item in package["approval_checklist"]}
        self.assertEqual(checklist["standards_ready_for_engineer_review"]["status"], "manual_required")
        self.assertEqual(checklist["standards_ready_for_engineer_review"]["check_type"], "engineer_manual_review_required")
        self.assertEqual(checklist["survey_control_verified"]["status"], "complete")
        self.assertEqual(checklist["terrain_verified"]["status"], "complete")
        self.assertEqual(checklist["calculations_reviewed"]["status"], "manual_required")
        self.assertEqual(checklist["calculations_reviewed"]["check_type"], "engineer_manual_review_required")
        self.assertEqual(checklist["exports_ready_for_engineer_review"]["status"], "manual_required")
        self.assertEqual(checklist["assumptions_accepted"]["status"], "manual_required")
        self.assertEqual(checklist["assumptions_accepted"]["check_type"], "engineer_manual_review_required")
        self.assertTrue(checklist["assumptions_accepted"]["external_manual"])
        self.assertEqual(checklist["external_engineer_approval_record"]["status"], "manual_required")
        self.assertEqual(checklist["external_engineer_approval_record"]["check_type"], "external_engineer_approval_record_required")
        self.assertTrue(checklist["external_engineer_approval_record"]["external_manual"])
        self.assertTrue(all(not item["civora_signoff_allowed"] for item in checklist.values()))
        self.assertTrue(all(item["required_engineer_review"] for item in checklist.values()))
        self.assertTrue(all(item["engineer_approval_required"] for item in checklist.values()))
        self.assertTrue(all(not item["simulated_seal_allowed"] for item in checklist.values()))
        self.assertTrue(all(not item["simulated_signature_allowed"] for item in checklist.values()))
        self.assertTrue(all(item["ready_language"] == "ready_for_engineer_review" for item in checklist.values()))

        export_summary = package["export_package_summary"]
        self.assertTrue(export_summary["review_package_only"])
        self.assertTrue(export_summary["external_engineer_approval_record_required"])
        self.assertFalse(export_summary["construction_release_allowed"])
        self.assertTrue(export_summary["construction_release_blocked"])
        self.assertFalse(export_summary["construction_release_allowed_by_civora"])
        self.assertFalse(export_summary["simulated_seal_allowed"])
        self.assertFalse(export_summary["simulated_signature_allowed"])
        self.assertEqual(export_summary["ready_language"], "ready_for_engineer_review")

    def test_assumptions_and_blockers_are_preserved(self) -> None:
        meta = _ready_meta()
        meta["standards_package"] = {
            "status": "blocked",
            "production_usable": False,
            "blockers": [
                {
                    "area": "standards",
                    "field": "official_sources",
                    "reason": "Official source missing.",
                    "suggested_next_action": "Attach official source.",
                }
            ],
        }
        meta["assumptions"] = [
            {
                "field_name": "runoff_coefficient",
                "assumed_value": 0.75,
                "reason": "User did not provide land-cover table.",
            }
        ]

        package = build_engineer_review_package({"meta": meta})

        self.assertEqual(package["review_status"], "blocked")
        self.assertEqual(package["assumptions"], meta["assumptions"])
        self.assertIn(
            ("standards", "official_sources"),
            {(item["area"], item["field"]) for item in package["blockers"]},
        )
        checklist = {item["item_id"]: item for item in package["approval_checklist"]}
        self.assertEqual(checklist["assumptions_accepted"]["status"], "manual_required")

    def test_reviewer_comments_are_structured(self) -> None:
        meta = _ready_meta()
        meta["reviewer_comments"] = [
            {
                "id": "qa-1",
                "area": "storm",
                "field": "pipe_capacity",
                "comment": "Engineer should verify tailwater before approval.",
                "severity": "review",
            }
        ]

        package = build_engineer_review_package({"meta": meta})

        comments = package["reviewer_comments"]
        self.assertGreaterEqual(len(comments), 2)
        self.assertTrue(all(comment["requires_engineer_review"] for comment in comments))
        self.assertIn("source", comments[0])
        self.assertIn("review", package["reviewer_comments_by_severity"])
        self.assertIn("storm", package["reviewer_comments_by_discipline"])
        self.assertIn(
            ("reviewer_comments", "qa-1", "storm", "pipe_capacity"),
            {
                (
                    comment["source"],
                    comment["comment_id"],
                    comment["area"],
                    comment["field"],
                )
                for comment in comments
            },
        )

    def test_discipline_blockers_assumptions_calculations_and_source_confidence_are_preserved(self) -> None:
        meta = _ready_meta()
        meta["depth_validation"]["stormwater"] = {
            "production_ready": False,
            "canonical_model_id": "MODEL-FINAL-1",
            "blockers": [
                {
                    "area": "storm",
                    "field": "pipe_capacity",
                    "reason": "Storm pipe capacity needs engineer review.",
                }
            ],
        }
        meta["assumptions"] = [
            {
                "discipline": "storm",
                "field_name": "tailwater",
                "assumed_value": "normal depth",
                "reason": "Tailwater was not provided.",
            }
        ]
        meta["calculation_artifacts"].append(
            {
                "artifact_id": "storm_pipe_capacity",
                "discipline": "storm",
                "status": "review_ready",
                "canonical_model_id": "MODEL-FINAL-1",
                "trace": {"source_object_ids": ["STM-100"], "pipe_ids": ["P-1"]},
            }
        )

        package = build_engineer_review_package({"meta": meta})

        storm = package["discipline_sections"]["storm"]
        self.assertEqual(storm["status"], "blocked")
        self.assertIn("pipe_capacity", {item["field"] for item in storm["blockers"]})
        self.assertEqual(storm["assumptions"][0]["field_name"], "tailwater")
        self.assertIn("storm_pipe_capacity", {item["artifact_id"] for item in storm["calculation_artifacts"]})
        self.assertEqual(storm["source_confidence"]["terrain_source_confidence"], "survey_surface")
        self.assertIn("MODEL-FINAL-1", storm["canonical_ids"])
        self.assertIn("STM-100", storm["canonical_ids"])

    def test_calculation_artifacts_include_canonical_ids(self) -> None:
        meta = _ready_meta()
        meta["storm_summary"] = {
            "success": True,
            "status": "ready",
            "canonical_model_id": "MODEL-FINAL-1",
            "explain": {"canonical_source_ids": ["STM-NET-1"], "pipe_ids": ["P-10"]},
        }

        package = build_engineer_review_package({"meta": meta})

        artifacts = {item["artifact_id"]: item for item in package["calculation_artifacts"]}
        self.assertIn("storm_summary", artifacts)
        self.assertEqual(
            artifacts["storm_summary"]["canonical_ids"],
            ["MODEL-FINAL-1", "STM-NET-1", "P-10"],
        )

    def test_missing_inputs_are_grouped_by_gate(self) -> None:
        package = build_engineer_review_package({"meta": {"project_id": "missing-gates"}})

        grouped = package["missing_inputs_by_gate"]
        self.assertEqual(
            set(grouped),
            {"standards", "existing_conditions", "engine_depth", "exports", "calculations", "engineer_approval"},
        )
        self.assertEqual(grouped["standards"][0]["field"], "standards_package")
        self.assertEqual(grouped["existing_conditions"][0]["field"], "existing_conditions_package")
        self.assertEqual(grouped["engine_depth"][0]["field"], "engine_depth_evidence")
        self.assertEqual(grouped["exports"][0]["field"], "export_package")
        self.assertEqual(grouped["calculations"][0]["field"], "calculation_artifacts")
        self.assertEqual(grouped["engineer_approval"][0]["field"], "external_engineer_approval_record")

    def test_external_engineer_approval_record_never_makes_civora_release_construction(self) -> None:
        meta = _ready_meta()
        meta["engineer_approval_record"] = {
            "engineer_name": "Licensed Reviewer",
            "license_number": "PE-12345",
            "license_jurisdiction": "TX",
            "jurisdiction": "TX",
            "discipline": "civil",
            "status": "released_for_construction",
            "sealed": True,
            "review_date": "2026-06-01",
            "scope": ["civil review package"],
            "canonical_model_id": "MODEL-FINAL-1",
            "manual_external_record": True,
        }

        package = build_engineer_review_package({"meta": meta})

        self.assertEqual(package["review_status"], "ready_for_engineer_review")
        self.assertTrue(package["external_engineer_approval"]["complete"])
        self.assertTrue(package["required_engineer_review"])
        self.assertTrue(package["engineer_approval_required"])
        self.assertFalse(package["civora_signoff_allowed"])
        self.assertFalse(package["construction_release_allowed"])
        self.assertTrue(package["construction_release_blocked"])
        self.assertFalse(package["ready_for_construction"])
        self.assertTrue(package["export_package_summary"]["review_package_only"])
        self.assertFalse(package["external_engineer_approval"]["civora_signoff_allowed"])
        self.assertFalse(package["external_engineer_approval"]["construction_release_allowed_by_civora"])
        self.assertFalse(package["external_engineer_approval"]["simulated_seal_allowed"])
        self.assertFalse(package["external_engineer_approval"]["simulated_signature_allowed"])
        self.assertEqual(package["external_engineer_approval"]["ready_language"], "ready_for_engineer_review")
        self.assertIn("external", package["external_engineer_approval"]["truth_label"])
        self.assertIn("simulate a seal/signature", package["external_engineer_approval"]["truth_label"])

    def test_professional_review_without_external_record_cannot_complete_approval(self) -> None:
        meta = _ready_meta()
        meta["professional_review"] = {
            "engineer_name": "Licensed Reviewer",
            "license_number": "PE-12345",
            "license_jurisdiction": "TX",
            "jurisdiction": "TX",
            "discipline": "civil",
            "status": "released_for_construction",
            "sealed": True,
            "review_date": "2026-06-01",
            "scope": ["civil review package"],
            "canonical_model_id": "MODEL-FINAL-1",
        }

        package = build_engineer_review_package({"meta": meta})

        self.assertEqual(package["review_status"], "ready_for_engineer_review")
        self.assertFalse(package["external_engineer_approval"]["complete"])
        self.assertEqual(package["external_engineer_approval"]["approval_source"], "external_record")
        self.assertIn("engineer_approval", package["missing_inputs_by_gate"])
        self.assertFalse(package["construction_release_allowed"])
        self.assertTrue(package["construction_release_blocked"])
        self.assertFalse(package["ready_for_construction"])
        self.assertFalse(package["civora_signoff_allowed"])
        self.assertFalse(package["simulated_seal_allowed"])
        self.assertFalse(package["simulated_signature_allowed"])


if __name__ == "__main__":
    unittest.main()
