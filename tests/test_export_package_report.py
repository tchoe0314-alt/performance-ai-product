from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from backend.planning.export_package_report import build_export_package_report_v1
from backend.planning.landxml_io import build_landxml_pipe_network
from output.dxf_exporter import finalize_export_metadata


def _plan() -> dict:
    return {
        "project_id": "project-1",
        "project_name": "Export Package Report",
        "units": "ft",
        "actions": [
            {
                "task": "polyline",
                "layer": "PIPE",
                "points": [[0.0, 0.0], [100.0, 0.0]],
                "label": "STM-1",
                "canonical_source_id": "storm-1",
                "canonical_source_type": "storm_pipe",
            }
        ],
        "meta": {
            "project_id": "project-1",
            "canonical_revision": "rev-2",
            "canonical_model_hash": "hash-rev-2",
            "deliverables": {"requested": ["storm_pipe_plan"], "produced": ["storm_pipe_plan"]},
            "storm_pipes": {
                "segments": [
                    {
                        "id": "storm-1",
                        "name": "STM-1",
                        "length_ft": 100.0,
                        "diameter_in": 18.0,
                        "slope_ft_ft": 0.01,
                        "path": [{"x": 0, "y": 0}, {"x": 100, "y": 0}],
                    }
                ],
                "structures": [{"id": "cb-1", "name": "CB-1", "x": 0, "y": 0}],
            },
            "profiles": [
                {
                    "id": "profile-1",
                    "name": "ROAD PROFILE 1",
                    "alignment_id": "align-1",
                    "canonical_source_id": "profile-canon-1",
                }
            ],
            "cross_sections": [
                {
                    "id": "section-1",
                    "name": "ROAD SECTION 1",
                    "alignment_id": "align-1",
                    "canonical_source_id": "section-canon-1",
                }
            ],
            "quantities": {
                "line_items": [
                    {
                        "id": "qty-pipe-1",
                        "metric": "pipe_length_ft",
                        "quantity": 100.0,
                        "unit": "lf",
                        "source_object_ids": ["storm-1"],
                    }
                ],
                "quantity_audit": {
                    "pipe_length_ft": {"source_object_ids": ["storm-1"]},
                    "profile_length_ft": {"source_object_ids": ["profile-canon-1"]},
                }
            },
            "construction_readiness": {
                "ready": True,
                "status": "construction_ready",
                "evidence": {
                    "standards_production_usable": True,
                    "existing_conditions_production_ready": True,
                    "civil_production_ready": True,
                },
            },
        },
    }


class ExportPackageReportTests(unittest.TestCase):
    def test_export_package_report_matches_canonical_state(self) -> None:
        plan = _plan()
        finalize_export_metadata(plan)

        report = plan["meta"]["export_package_report_v1"]

        self.assertEqual(report["export_type"], "dxf")
        self.assertEqual(report["source_project_id"], "project-1")
        self.assertEqual(report["source_canonical_revision"], "rev-2")
        self.assertEqual(report["source_canonical_hash"], "hash-rev-2")
        self.assertIn("storm-1", report["canonical_ids_included"])
        self.assertIn("profile-canon-1", report["canonical_ids_included"])
        self.assertIn("section-canon-1", report["canonical_ids_included"])
        self.assertIn("align-1", report["canonical_ids_included"])
        self.assertIn("storm_pipes", report["included_systems"])
        self.assertIn("profiles", report["included_systems"])
        self.assertIn("cross_sections", report["included_systems"])
        self.assertEqual(report["standards_status"], "ready")
        self.assertEqual(report["existing_conditions_status"], "ready")
        self.assertEqual(report["engine_depth_status"], "ready")
        self.assertTrue(report["engineer_review_required"])
        self.assertFalse(report["civora_signoff_allowed"])
        self.assertFalse(report["construction_release_allowed"])
        self.assertTrue(report["construction_release_blocked"])
        self.assertEqual(report["deliverable_confidence"], "construction_blocked")
        self.assertIn("construction_package_manifest_missing", report["construction_release_blockers"])
        self.assertEqual(report["quantity_line_items"][0]["canonical_ids"], ["storm-1"])
        self.assertEqual(report["profile_packages"][0]["canonical_ids"], ["profile-canon-1", "align-1", "profile-1"])
        self.assertEqual(report["section_packages"][0]["canonical_ids"], ["section-canon-1", "align-1", "section-1"])

    def test_stale_canonical_revision_blocks_export_readiness(self) -> None:
        plan = _plan()
        plan["meta"]["last_exported_canonical_hash"] = "hash-rev-1"

        report = build_export_package_report_v1(plan, export_type="dxf", generated_at="2026-06-06T00:00:00Z")

        self.assertTrue(report["construction_release_blocked"])
        self.assertIn("last_exported_canonical_hash", report["stale_outputs_detected"])
        self.assertEqual(report["deliverable_confidence"], "construction_blocked")
        self.assertFalse(report["construction_release_allowed"])

    def test_missing_standards_imports_and_depth_gates_block_construction_status(self) -> None:
        plan = _plan()
        plan["meta"]["construction_readiness"]["evidence"] = {
            "standards_production_usable": False,
            "existing_conditions_production_ready": False,
            "civil_production_ready": False,
        }

        report = build_export_package_report_v1(plan, export_type="report", generated_at="2026-06-06T00:00:00Z")

        self.assertEqual(report["standards_status"], "blocked")
        self.assertEqual(report["existing_conditions_status"], "blocked")
        self.assertEqual(report["engine_depth_status"], "blocked")
        self.assertTrue(report["construction_release_blocked"])
        self.assertIn("production_usable_standards", report["missing_inputs"])
        self.assertIn("production_ready_existing_conditions", report["missing_inputs"])
        self.assertIn("production_ready_engine_depth", report["missing_inputs"])
        self.assertEqual(report["deliverable_confidence"], "construction_blocked")

    def test_dxf_landxml_and_report_package_include_audit_metadata(self) -> None:
        plan = _plan()
        metadata = finalize_export_metadata(plan)

        self.assertIn("export_package_report_v1", metadata)
        self.assertEqual(metadata["export_package_report_v1"], plan["meta"]["export_package_report_v1"])

        landxml = build_landxml_pipe_network(plan, network_name="Export Test")
        root = ET.fromstring(landxml)
        report_node = root.find(".//CivoraExportPackageReport")
        self.assertIsNotNone(report_node)
        self.assertEqual(report_node.attrib["source"], "export_package_report_v1")
        self.assertEqual(report_node.attrib["export_type"], "landxml")
        self.assertEqual(report_node.attrib["source_canonical_hash"], "hash-rev-2")
        self.assertEqual(report_node.attrib["engineer_review_required"], "true")
        self.assertEqual(report_node.attrib["civora_signoff_allowed"], "false")
        self.assertEqual(report_node.attrib["construction_release_allowed"], "false")
        self.assertEqual(report_node.attrib["construction_release_blocked"], "true")
        self.assertEqual(report_node.attrib["landxml_external_verification_status"], "not_verified")
        self.assertEqual(report_node.attrib["civil3d_external_verification_status"], "not_verified")
        pipe_node = root.find(".//Pipe")
        self.assertIsNotNone(pipe_node)
        self.assertEqual(pipe_node.attrib["civoraCanonicalId"], "storm-1")
        self.assertEqual(pipe_node.attrib["civoraExternalVerificationStatus"], "not_verified")

        report = build_export_package_report_v1(plan, export_type="report", generated_at="2026-06-06T00:00:00Z")
        self.assertEqual(report["export_type"], "report")
        self.assertEqual(report["source"], "export_package_report_v1")
        self.assertIn("supported_deliverables", report)
        self.assertEqual(report["external_verification"]["landxml"]["status"], "not_verified")
        self.assertEqual(report["external_verification"]["civil3d"]["status"], "not_verified")
        self.assertTrue(report["profile_packages"])
        self.assertTrue(report["section_packages"])

    def test_unsupported_civil3d_and_dwg_are_labeled_honestly(self) -> None:
        plan = _plan()
        finalize_export_metadata(plan)
        report = plan["meta"]["export_package_report_v1"]

        self.assertEqual(report["civil3d_compatibility"], "not_verified")
        self.assertEqual(report["dwg_compatibility"], "unsupported_no_writer")
        self.assertEqual(report["supported_deliverables"]["civil3d"]["status"], "not_verified")
        self.assertEqual(report["supported_deliverables"]["dwg"]["status"], "unsupported_no_writer")
        self.assertFalse(report["supported_deliverables"]["civil3d"]["construction_ready"])
        self.assertFalse(report["supported_deliverables"]["dwg"]["construction_ready"])

    def test_failed_external_civil3d_verification_is_blocked_needs_review(self) -> None:
        plan = _plan()
        plan["meta"]["external_verification"] = {
            "civil3d": {
                "verifier_identity": "External Engineer",
                "verification_date": "2026-06-06",
                "tool": "Autodesk Civil 3D",
                "tool_version": "2026",
                "result": "failed",
                "notes": "Import workflow failed.",
            }
        }

        report = build_export_package_report_v1(plan, export_type="landxml", generated_at="2026-06-06T00:00:00Z")

        self.assertEqual(report["external_verification"]["civil3d"]["status"], "blocked_needs_review")
        self.assertEqual(report["civil3d_compatibility"], "blocked_needs_review")
        self.assertEqual(report["supported_deliverables"]["civil3d"]["status"], "blocked_needs_review")
        self.assertFalse(report["external_verification"]["civil3d"]["construction_release_allowed"])
        self.assertFalse(report["supported_deliverables"]["civil3d"]["construction_ready"])

    def test_passed_external_civil3d_verification_is_import_workflow_only(self) -> None:
        plan = _plan()
        plan["meta"]["external_verification"] = {
            "civil3d": {
                "verification_record_id": "civil3d-landxml-2026-06-06",
                "verifier_identity": "External Engineer",
                "verification_date": "2026-06-06",
                "tool": "Autodesk Civil 3D",
                "tool_version": "2026.1",
                "result": "passed",
                "notes": "LandXML import and workflow check completed.",
            }
        }

        report = build_export_package_report_v1(plan, export_type="landxml", generated_at="2026-06-06T00:00:00Z")

        self.assertEqual(report["external_verification"]["civil3d"]["status"], "externally_verified_review_only")
        self.assertEqual(report["civil3d_compatibility"], "externally_verified_for_import_workflow_only")
        self.assertEqual(report["supported_deliverables"]["civil3d"]["status"], "externally_verified_review_only")
        self.assertEqual(report["external_verification"]["civil3d"]["verifier_identity"], "External Engineer")
        self.assertEqual(report["external_verification"]["civil3d"]["verification_date"], "2026-06-06")
        self.assertEqual(report["external_verification"]["civil3d"]["tool"], "Autodesk Civil 3D")
        self.assertEqual(report["external_verification"]["civil3d"]["tool_version"], "2026.1")
        self.assertFalse(report["construction_release_allowed"])
        self.assertFalse(report["supported_deliverables"]["civil3d"]["construction_ready"])

    def test_external_verification_labels_avoid_release_claim_words(self) -> None:
        plan = _plan()
        plan["meta"]["external_verification"] = {
            "civil3d": {
                "verifier_identity": "External Engineer",
                "verification_date": "2026-06-06",
                "tool": "Autodesk Civil 3D",
                "tool_version": "2026.1",
                "result": "passed",
            }
        }

        report = build_export_package_report_v1(plan, export_type="landxml", generated_at="2026-06-06T00:00:00Z")
        labels = " ".join(
            [
                report["civil3d_compatibility"],
                report["external_verification"]["civil3d"]["status"],
                report["supported_deliverables"]["civil3d"]["status"],
            ]
        ).lower()

        self.assertNotIn("construction-ready", labels)
        self.assertNotIn("stamp", labels)
        self.assertNotIn("seal", labels)

    def test_civora_never_approves_signs_or_seals_construction_deliverables(self) -> None:
        plan = _plan()
        plan["meta"]["professional_review"] = {
            "engineer_name": "External Engineer",
            "license_number": "PE-12345",
            "license_jurisdiction": "TX",
            "jurisdiction": "TX",
            "discipline": "civil",
            "status": "released_for_construction",
            "sealed": True,
            "review_date": "2026-06-01",
            "scope": ["civil review package"],
            "manual_external_record": True,
        }

        finalize_export_metadata(plan)
        report = plan["meta"]["export_package_report_v1"]

        self.assertTrue(report["engineer_review_required"])
        self.assertFalse(report["civora_signoff_allowed"])
        self.assertFalse(report["construction_release_allowed"])
        self.assertTrue(report["construction_release_blocked"])
        self.assertIn("Civora never signs, seals, certifies, or approves construction", report["truth_label"])


if __name__ == "__main__":
    unittest.main()
