import unittest

from backend.application.professional_workflows import (
    professional_release_response,
    validate_professional_release_response,
)
from backend.planning.professional_release import build_professional_review_record, validate_professional_release
from core.civil_design import construction_readiness


class ProfessionalReleaseTests(unittest.TestCase):
    def test_professional_release_validation_blocks_incomplete_record(self) -> None:
        validation = validate_professional_release({"status": "released_for_construction", "sealed": True})
        fields = {item["field"] for item in validation["blockers"]}

        self.assertFalse(validation["success"])
        self.assertIn("engineer_name", fields)
        self.assertIn("license_number", fields)
        self.assertIn("review_date", fields)

    def test_professional_release_record_builds_valid_release_evidence(self) -> None:
        record = build_professional_review_record(
            engineer_name="Alex Morgan",
            license_number="TX-123456",
            review_date="2026-05-28",
            jurisdiction="Test City",
        )

        self.assertTrue(record["validation"]["success"])
        self.assertTrue(record["validation"]["released_for_construction"])
        self.assertEqual(record["status"], "released_for_construction")

    def test_application_professional_release_response_is_explicit_about_stamp_boundary(self) -> None:
        response = professional_release_response(
            engineer_name="Alex Morgan",
            license_number="TX-123456",
            review_date="2026-05-28",
        )
        validation = validate_professional_release_response(response["professional_review"])

        self.assertTrue(response["success"])
        self.assertTrue(validation["success"])
        self.assertIn("does not stamp", response["truth_label"])

    def test_construction_readiness_requires_complete_professional_release_metadata(self) -> None:
        meta = {
            "civil_design_readiness": {"production_ready": True, "score": 100.0, "production_blockers": []},
            "existing_conditions_summary": {"production_ready": True},
            "survey": {"point_count": 3, "source": "survey.csv"},
            "coordinate_system": {"epsg": "EPSG:2276", "units": "ft"},
            "design_standards": {"production_usable": True},
            "jurisdiction_standards": {"agency": "Test City"},
            "company_standards": {"cad": "Test"},
            "depth_validation": {
                "stormwater": {"production_ready": True},
                "water": {"production_ready": True},
                "roadway_corridor": {"production_ready": True},
            },
            "truth_audit": {"success": True},
            "manual_validation": {"success": True},
            "reactive_update_report": {"export_blocked": False, "post_rerun_stale_outputs": []},
            "export_audit": {"production_export_ready": True, "export_blocked": False},
            "sheet_registry": {"sheets": [{"id": "C-100"}]},
            "professional_review": {"status": "released_for_construction", "sealed": True},
        }

        readiness = construction_readiness({"meta": meta})
        fields = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("professional_review", "engineer_name"), fields)
        self.assertIn(("professional_review", "license_number"), fields)
        self.assertIn(("professional_review", "review_date"), fields)


if __name__ == "__main__":
    unittest.main()
