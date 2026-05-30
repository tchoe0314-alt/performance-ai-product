import unittest

import report_builder


class ReportBuilderTest(unittest.TestCase):
    def test_build_report_exposes_blocked_release_review_as_first_class_section(self):
        report = report_builder.build_report(
            final_plan={
                "project_name": "Construction Report",
                "actions": [{"task": "polyline", "layer": "LOT"}],
                "meta": {
                    "construction_release_required": True,
                    "canonical_model_id": "model-1",
                    "canonical_model_hash": "hash-1",
                    "construction_readiness": {"ready": False, "status": "not_construction_ready"},
                    "construction_package_manifest": {
                        "package_id": "pkg-1",
                        "construction_package_artifact_status": {"complete_for_release": False},
                        "professional_package_release_status": {"model_matches_package": False},
                    },
                },
            },
            request_metadata={
                "release_review": {
                    "release_status": "blocked",
                    "release_note": "Blocked until construction package is complete.",
                    "blocked_reasons": ["construction_readiness_blocked"],
                    "blocked_exports": ["dxf_export_blocked"],
                }
            },
        )

        self.assertEqual(report["summary"]["release_status"], "blocked")
        self.assertFalse(report["summary"]["release_ready"])
        self.assertEqual(report["summary"]["release_blocker_count"], 4)
        self.assertEqual(report["release"]["release_status"], "blocked")
        self.assertFalse(report["release"]["release_ready"])
        self.assertEqual(
            report["release"]["release_blockers"],
            [
                "construction_readiness_blocked",
                "dxf_export_blocked",
                "construction_package_blocked",
                "construction_package_release_not_marked_ready",
            ],
        )
        self.assertTrue(report["release"]["construction_release_required"])
        self.assertEqual(report["release"]["construction_package_id"], "pkg-1")
        self.assertEqual(report["release"]["canonical_model_reference"]["canonical_model_hash"], "hash-1")
        self.assertIn("release", report["exports"]["report_sections"])
        release_sections = [section for section in report["sections"] if section["section_id"] == "release"]
        self.assertEqual(len(release_sections), 1)
        self.assertEqual(release_sections[0]["content"]["release_status"], "blocked")

    def test_build_report_keeps_release_ready_false_when_metadata_has_blockers(self):
        report = report_builder.build_report(
            final_plan={
                "project_name": "Construction Report",
                "actions": [{"task": "polyline", "layer": "LOT"}],
                "meta": {
                    "release_status": "ready",
                    "release_ready": True,
                    "release_review": {
                        "release_status": "blocked",
                        "blocked_reasons": ["construction_package_blocked"],
                    },
                },
            },
        )

        self.assertEqual(report["release"]["release_status"], "blocked")
        self.assertFalse(report["release"]["release_ready"])
        self.assertEqual(report["summary"]["release_blocker_count"], 1)

    def test_build_report_explains_explicit_release_review_not_ready(self):
        report = report_builder.build_report(
            final_plan={
                "project_name": "Construction Report",
                "actions": [{"task": "polyline", "layer": "LOT"}],
                "meta": {
                    "release_ready": True,
                    "release_review": {
                        "release_status": "ready",
                        "release_ready": False,
                    },
                },
            },
        )

        self.assertEqual(report["release"]["release_status"], "ready")
        self.assertFalse(report["release"]["release_ready"])
        self.assertIn("release_review_not_ready", report["release"]["release_blockers"])
        self.assertEqual(report["summary"]["release_blocker_count"], 1)

    def test_build_report_explains_blocked_release_status_without_reasons(self):
        report = report_builder.build_report(
            final_plan={
                "project_name": "Construction Report",
                "actions": [{"task": "polyline", "layer": "LOT"}],
                "meta": {
                    "release_ready": True,
                    "release_review": {
                        "release_status": "blocked",
                    },
                },
            },
        )

        self.assertEqual(report["release"]["release_status"], "blocked")
        self.assertFalse(report["release"]["release_ready"])
        self.assertIn("release_status_blocked", report["release"]["release_blockers"])
        self.assertEqual(report["summary"]["release_blocker_count"], 1)

    def test_build_report_surfaces_failed_deliverables_as_release_blockers(self):
        report = report_builder.build_report(
            final_plan={
                "project_name": "Construction Report",
                "actions": [{"task": "polyline", "layer": "LOT"}],
                "meta": {
                    "release_status": "ready",
                    "release_ready": True,
                    "deliverables": {
                        "requested": ["site_plan", "report"],
                        "produced": ["site_plan"],
                        "failed": ["report"],
                    },
                },
            },
        )

        self.assertFalse(report["release"]["release_ready"])
        self.assertIn("failed_deliverable_report", report["release"]["release_blockers"])
        self.assertEqual(report["summary"]["release_blocker_count"], 1)

    def test_build_report_surfaces_missing_deliverables_as_release_blockers(self):
        report = report_builder.build_report(
            final_plan={
                "project_name": "Construction Report",
                "actions": [{"task": "polyline", "layer": "LOT"}],
                "meta": {
                    "release_status": "ready",
                    "release_ready": True,
                    "deliverables": {
                        "requested": ["site_plan", "report"],
                        "produced": ["site_plan"],
                    },
                },
            },
        )

        self.assertFalse(report["release"]["release_ready"])
        self.assertIn("missing_deliverable_report", report["release"]["release_blockers"])
        self.assertEqual(report["summary"]["release_blocker_count"], 1)

    def test_build_report_surfaces_manual_validation_failures_as_release_blockers(self):
        report = report_builder.build_report(
            final_plan={
                "project_name": "Construction Report",
                "actions": [{"task": "polyline", "layer": "LOT"}],
                "meta": {
                    "release_status": "ready",
                    "release_ready": True,
                    "manual_validation": {
                        "failures": [
                            {
                                "code": "MANUAL_STORM_HYDRAULIC_INVALID",
                                "message": "Manual storm pipe hydraulic validation failed.",
                                "system": "storm",
                                "rule": "hydraulic_capacity",
                            }
                        ]
                    },
                },
            },
        )

        self.assertFalse(report["release"]["release_ready"])
        self.assertIn(
            "manual_validation_manual_storm_hydraulic_invalid",
            report["release"]["release_blockers"],
        )
        self.assertEqual(report["summary"]["release_blocker_count"], 1)

    def test_build_report_surfaces_reactive_post_rerun_release_blockers(self):
        report = report_builder.build_report(
            final_plan={
                "project_name": "Construction Report",
                "actions": [{"task": "polyline", "layer": "LOT"}],
                "meta": {
                    "release_status": "ready",
                    "release_ready": True,
                    "reactive_update_report": {
                        "post_rerun_production_ready": False,
                        "post_rerun_release_blockers": ["manual_validation_manual_storm_hydraulic_invalid"],
                    },
                },
            },
        )

        self.assertFalse(report["release"]["release_ready"])
        self.assertIn("reactive_post_rerun_not_ready", report["release"]["release_blockers"])
        self.assertIn(
            "manual_validation_manual_storm_hydraulic_invalid",
            report["release"]["release_blockers"],
        )
        self.assertEqual(report["summary"]["release_blocker_count"], 2)

    def test_build_report_blocks_stale_ready_with_construction_package_metadata(self):
        report = report_builder.build_report(
            final_plan={
                "project_name": "Construction Report",
                "actions": [{"task": "polyline", "layer": "LOT"}],
                "meta": {
                    "release_status": "ready",
                    "release_ready": True,
                    "construction_readiness": {"ready": True, "status": "construction_ready"},
                    "construction_package_manifest": {
                        "release_allowed": False,
                        "construction_package_artifact_status": {
                            "package_present": True,
                            "missing": [],
                            "anonymous": [],
                            "stale": [],
                            "model_reference_present": True,
                            "model_matches_expected": True,
                            "release_ready_flag": None,
                            "untraced": [],
                            "mismatched": [],
                        },
                    },
                },
            },
        )

        self.assertEqual(report["release"]["release_status"], "ready")
        self.assertFalse(report["release"]["release_ready"])
        self.assertIn("construction_package_blocked", report["release"]["release_blockers"])
        self.assertIn("construction_package_release_not_marked_ready", report["release"]["release_blockers"])

    def test_build_report_marks_construction_release_required_from_package_metadata_without_explicit_flag(self):
        report = report_builder.build_report(
            final_plan={
                "project_name": "Construction Report",
                "actions": [{"task": "polyline", "layer": "LOT"}],
                "meta": {
                    "release_status": "ready",
                    "release_ready": True,
                    "construction_readiness": {"ready": True, "status": "construction_ready"},
                    "construction_package": {
                        "release_allowed": False,
                        "construction_package_artifact_status": {
                            "package_present": True,
                            "release_ready_flag": True,
                            "stale": ["C-400"],
                        },
                    },
                },
            },
        )

        self.assertTrue(report["release"]["construction_release_required"])
        self.assertFalse(report["release"]["release_ready"])
        self.assertIn("construction_package_stale_artifacts", report["release"]["release_blockers"])


if __name__ == "__main__":
    unittest.main()
