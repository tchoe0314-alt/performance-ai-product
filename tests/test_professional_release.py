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
        detail_fields = {item["field"] for item in validation["blocker_details"]}
        self.assertIn("engineer_name", detail_fields)
        detail = next(item for item in validation["blocker_details"] if item["field"] == "license_number")
        self.assertTrue(detail["engineer_review_required"])
        self.assertTrue(detail["next_action"])

    def test_professional_release_record_builds_valid_release_evidence(self) -> None:
        record = build_professional_review_record(
            engineer_name="Alex Morgan",
            license_number="TX-123456",
            status="released_for_construction",
            review_date="2026-05-28",
            sealed=True,
            jurisdiction="Test City",
            license_jurisdiction="TX",
        )

        self.assertTrue(record["validation"]["success"])
        self.assertTrue(record["validation"]["released_for_construction"])
        self.assertEqual(record["status"], "released_for_construction")
        self.assertEqual(record["discipline"], "civil")

    def test_application_professional_release_response_is_explicit_about_stamp_boundary(self) -> None:
        response = professional_release_response(
            engineer_name="Alex Morgan",
            license_number="TX-123456",
            status="released_for_construction",
            review_date="2026-05-28",
            sealed=True,
            jurisdiction="Test City",
            license_jurisdiction="TX",
        )
        validation = validate_professional_release_response(response["professional_review"])

        self.assertTrue(response["success"])
        self.assertTrue(validation["success"])
        self.assertIn("never stamps, seals, signs, certifies, approves construction", response["truth_label"])

    def test_professional_release_builder_defaults_to_blocked_draft_record(self) -> None:
        record = build_professional_review_record(
            engineer_name="Alex Morgan",
            license_number="TX-123456",
            jurisdiction="Test City",
            license_jurisdiction="TX",
        )
        fields = {item["field"] for item in record["validation"]["blockers"]}

        self.assertFalse(record["validation"]["success"])
        self.assertFalse(record["validation"]["released_for_construction"])
        self.assertEqual(record["status"], "draft_external_review_record")
        self.assertFalse(record["sealed"])
        self.assertEqual(record["review_date"], "")
        self.assertIn("sealed_release", fields)
        self.assertIn("review_date", fields)

    def test_professional_release_requires_license_jurisdiction_and_civil_scope(self) -> None:
        validation = validate_professional_release(
            {
                "engineer_name": "Alex Morgan",
                "license_number": "TX-123456",
                "status": "released_for_construction",
                "sealed": True,
                "review_date": "2026-05-28",
                "jurisdiction": "Test City",
            }
        )
        fields = {item["field"] for item in validation["blockers"]}

        self.assertFalse(validation["success"])
        self.assertIn("license_jurisdiction", fields)
        self.assertIn("discipline", fields)
        self.assertIn("review_scope", fields)

    def test_professional_release_blocks_future_review_date(self) -> None:
        validation = validate_professional_release(
            {
                "engineer_name": "Alex Morgan",
                "license_number": "TX-123456",
                "status": "released_for_construction",
                "sealed": True,
                "review_date": "2999-01-01",
                "jurisdiction": "Test City",
                "license_jurisdiction": "TX",
                "discipline": "civil",
                "review_scope": "civil_site_construction_documents",
            }
        )
        blockers = {(item["field"], item["reason"]) for item in validation["blockers"]}

        self.assertFalse(validation["success"])
        self.assertFalse(validation["released_for_construction"])
        self.assertIn(("review_date", "Professional release review date cannot be in the future."), blockers)

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
