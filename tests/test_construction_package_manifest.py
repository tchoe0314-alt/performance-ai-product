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
            }
        }

        manifest = build_construction_package_manifest({"meta": meta})

        self.assertEqual(manifest["release_state"], "released_for_construction")
        self.assertTrue(manifest["construction_export_allowed"])
        self.assertFalse(manifest["blocked_sections"])
        self.assertTrue(all(section["ready"] for section in manifest["sections"]))


if __name__ == "__main__":
    unittest.main()
