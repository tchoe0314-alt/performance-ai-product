from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.planning.export_external_verification import (
    build_supported_limited_unsupported_matrix,
    normalize_external_verification_record,
    verify_dxf_export,
    verify_landxml_export,
)
from backend.planning.landxml_io import build_landxml_pipe_network
from output.dxf_exporter import save_dxf
from tests.test_export_package_report import _plan


class ExportExternalVerificationTests(unittest.TestCase):
    def test_missing_external_verification_record_defaults_to_not_verified(self) -> None:
        record = normalize_external_verification_record(None, format_id="civil3d", target_tool="Civil3D")

        self.assertEqual(record["status"], "not_verified")
        self.assertFalse(record["verified"])
        self.assertFalse(record["construction_release_allowed"])
        self.assertEqual(record["scope"], "import_workflow_only")

    def test_failed_external_civil3d_verification_blocks_for_review(self) -> None:
        record = normalize_external_verification_record(
            {
                "verifier_identity": "External PE",
                "verification_date": "2026-06-06",
                "tool": "Autodesk Civil 3D",
                "tool_version": "2026",
                "result": "failed",
                "notes": "Pipe network import produced errors.",
            },
            format_id="civil3d",
            target_tool="Civil3D",
        )

        self.assertEqual(record["status"], "blocked_needs_review")
        self.assertFalse(record["verified"])
        self.assertEqual(record["failure_reason"], "external_verification_failed")
        self.assertFalse(record["construction_release_allowed"])

    def test_passed_external_civil3d_verification_is_review_only(self) -> None:
        record = normalize_external_verification_record(
            {
                "verification_record_id": "civil3d-check-1",
                "verifier_identity": "External Engineer",
                "verification_date": "2026-06-06",
                "tool": "Autodesk Civil 3D",
                "tool_version": "2026.1",
                "result": "passed",
                "notes": "Imported LandXML and completed target workflow check.",
            },
            format_id="civil3d",
            target_tool="Civil3D",
        )

        self.assertEqual(record["status"], "externally_verified_review_only")
        self.assertTrue(record["verified"])
        self.assertEqual(record["scope"], "import_workflow_only")
        self.assertFalse(record["construction_release_allowed"])

    def test_dxf_export_is_parseable_layer_checked_and_traceable_but_not_civil3d_verified(self) -> None:
        plan = _plan()

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "external-check.dxf"
            save_dxf(plan, filename=str(artifact_path))

            result = verify_dxf_export(artifact_path, plan=plan)

        self.assertEqual(result["local_parse_status"], "passed")
        self.assertEqual(result["layer_contract_status"], "passed")
        self.assertTrue(result["sidecar_metadata"]["present"])
        self.assertTrue(result["sidecar_metadata"]["artifact_path_matches"])
        self.assertTrue(result["sidecar_metadata"]["export_package_report_present"])
        self.assertTrue(result["sidecar_current_canonical_check"]["matches_current_canonical"])
        self.assertFalse(result["unknown_layers"])
        self.assertIn("PIPE", result["used_layers"])
        self.assertTrue(result["canonical_id_traceability"]["present"])
        self.assertIn("storm-1", result["canonical_id_traceability"]["canonical_ids"])
        self.assertTrue(result["profile_section_linkage"]["profile_alignment"])
        self.assertTrue(result["profile_section_linkage"]["section_alignment"])
        self.assertTrue(result["profile_section_linkage"]["profiles_have_canonical_ids"])
        self.assertTrue(result["profile_section_linkage"]["sections_have_canonical_ids"])
        self.assertEqual(result["civil3d_external_verification_status"], "not_verified")
        self.assertEqual(result["dwg_support_status"], "unsupported_no_writer")
        self.assertFalse(result["externally_verified"])
        self.assertFalse(result["construction_release_allowed"])
        self.assertTrue(result["construction_release_blocked"])

    def test_dxf_verification_fails_without_sidecar_metadata(self) -> None:
        plan = _plan()

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "missing-sidecar.dxf"
            save_dxf(plan, filename=str(artifact_path))
            artifact_path.with_suffix(".dxf.metadata.json").unlink()

            result = verify_dxf_export(artifact_path, plan=plan)

        self.assertEqual(result["local_parse_status"], "passed")
        self.assertFalse(result["sidecar_metadata"]["present"])
        self.assertFalse(result["local_contract_verified"])
        self.assertIn("sidecar_metadata_missing", result["failures"])

    def test_dxf_verification_blocks_stale_sidecar_metadata(self) -> None:
        plan = _plan()

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "stale-sidecar.dxf"
            save_dxf(plan, filename=str(artifact_path))
            sidecar_path = artifact_path.with_suffix(".dxf.metadata.json")
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            sidecar["source_canonical_hash"] = "hash-rev-1"
            sidecar["stale_outputs_detected"] = ["grading"]
            sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

            result = verify_dxf_export(artifact_path, plan=plan)

        self.assertEqual(result["local_parse_status"], "passed")
        self.assertFalse(result["local_contract_verified"])
        self.assertFalse(result["sidecar_current_canonical_check"]["matches_current_canonical"])
        self.assertIn("stale_export_blocked", result["failures"])
        self.assertIn("sidecar_canonical_reference_mismatch", result["failures"])

    def test_landxml_contract_roundtrips_with_canonical_ids_but_keeps_civil3d_not_verified(self) -> None:
        plan = _plan()
        xml_text = build_landxml_pipe_network(plan, network_name="External Verification")

        result = verify_landxml_export(xml_text, plan=plan)

        self.assertEqual(result["local_parse_status"], "passed")
        self.assertEqual(result["roundtrip_parse_status"], "passed")
        self.assertEqual(result["schema_like_contract_status"], "passed")
        self.assertGreaterEqual(result["pipe_count"], 1)
        self.assertGreaterEqual(result["structure_count"], 1)
        self.assertIn("storm-1", result["canonical_id_traceability"]["canonical_ids"])
        self.assertTrue(result["export_package_report_present"])
        self.assertTrue(result["review_only_flags_ok"])
        self.assertTrue(result["construction_release_flags_ok"])
        self.assertEqual(result["landxml_external_verification_status"], "not_verified")
        self.assertEqual(result["civil3d_external_verification_status"], "not_verified")
        self.assertEqual(result["dwg_support_status"], "unsupported_no_writer")
        self.assertFalse(result["externally_verified"])
        self.assertFalse(result["construction_release_allowed"])
        self.assertTrue(result["construction_release_blocked"])

    def test_landxml_contract_rejects_civil3d_or_release_overclaims(self) -> None:
        plan = _plan()
        xml_text = build_landxml_pipe_network(plan, network_name="External Verification")
        xml_text = xml_text.replace('civoraCivil3dVerificationStatus="not_verified"', 'civoraCivil3dVerificationStatus="verified"', 1)
        xml_text = xml_text.replace('civoraConstructionReleaseAllowed="false"', 'civoraConstructionReleaseAllowed="true"', 1)
        xml_text = xml_text.replace('civil3d_external_verification_status="not_verified"', 'civil3d_external_verification_status="verified"', 1)

        result = verify_landxml_export(xml_text, plan=plan)

        self.assertEqual(result["local_parse_status"], "passed")
        self.assertEqual(result["schema_like_contract_status"], "failed")
        self.assertFalse(result["local_contract_verified"])
        self.assertIn("civil3d_verification_overclaimed", result["failures"])
        self.assertIn("landxml_review_only_flags_missing", result["failures"])
        self.assertIn("landxml_construction_release_flags_invalid", result["failures"])

    def test_supported_limited_unsupported_matrix_never_promotes_civil3d_or_dwg_without_proof(self) -> None:
        plan = _plan()
        save_path = None
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "matrix.dxf"
            save_dxf(plan, filename=str(save_path))
            report = plan["meta"]["export_package_report_v1"]
            matrix = build_supported_limited_unsupported_matrix(report)

        self.assertIsNotNone(save_path)
        self.assertIn("dxf", matrix["supported"])
        self.assertIn("landxml", matrix["limited"])
        self.assertIn("civil3d", matrix["unsupported"])
        self.assertIn("dwg", matrix["unsupported"])
        self.assertEqual(report["supported_deliverables"]["civil3d"]["status"], "not_verified")
        self.assertEqual(report["supported_deliverables"]["dwg"]["status"], "unsupported_no_writer")
        self.assertFalse(report["supported_deliverables"]["civil3d"]["construction_ready"])
        self.assertFalse(report["supported_deliverables"]["dwg"]["construction_ready"])


if __name__ == "__main__":
    unittest.main()
