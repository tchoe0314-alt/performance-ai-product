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

    def test_ready_for_review_still_requires_manual_engineer_signoff(self) -> None:
        package = build_engineer_review_package({"meta": _ready_meta()})

        self.assertEqual(package["review_status"], "ready_for_review")
        self.assertFalse(package["blockers"])
        self.assertFalse(package["missing_inputs"])
        self.assertTrue(package["required_engineer_review"])
        self.assertTrue(package["construction_release_blocked"])
        self.assertFalse(package["construction_release_allowed"])
        checklist = {item["item_id"]: item for item in package["signoff_checklist"]}
        self.assertEqual(checklist["standards_accepted"]["status"], "complete")
        self.assertEqual(checklist["survey_control_verified"]["status"], "complete")
        self.assertEqual(checklist["terrain_verified"]["status"], "complete")
        self.assertEqual(checklist["calculations_reviewed"]["status"], "manual_required")
        self.assertEqual(checklist["engineer_seal_signature_external_manual"]["status"], "manual_required")
        self.assertTrue(checklist["engineer_seal_signature_external_manual"]["external_manual"])

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
        checklist = {item["item_id"]: item for item in package["signoff_checklist"]}
        self.assertEqual(checklist["assumptions_accepted"]["status"], "manual_required")

    def test_reviewer_comments_are_structured(self) -> None:
        meta = _ready_meta()
        meta["reviewer_comments"] = [
            {
                "id": "qa-1",
                "area": "storm",
                "field": "pipe_capacity",
                "comment": "Engineer should verify tailwater before signoff.",
                "severity": "review",
            }
        ]

        package = build_engineer_review_package({"meta": meta})

        comments = package["reviewer_comments"]
        self.assertGreaterEqual(len(comments), 2)
        self.assertTrue(all(comment["requires_engineer_review"] for comment in comments))
        self.assertIn("source", comments[0])
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


if __name__ == "__main__":
    unittest.main()
