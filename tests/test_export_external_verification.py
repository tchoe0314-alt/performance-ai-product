from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.planning.export_external_verification import (
    build_supported_limited_unsupported_matrix,
    verify_dxf_export,
    verify_landxml_export,
)
from backend.planning.landxml_io import build_landxml_pipe_network
from output.dxf_exporter import save_dxf
from tests.test_export_package_report import _plan


class ExportExternalVerificationTests(unittest.TestCase):
    def test_dxf_export_is_parseable_layer_checked_and_traceable_but_not_civil3d_verified(self) -> None:
        plan = _plan()

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "external-check.dxf"
            save_dxf(plan, filename=str(artifact_path))

            result = verify_dxf_export(artifact_path, plan=plan)

        self.assertEqual(result["local_parse_status"], "passed")
        self.assertEqual(result["layer_contract_status"], "passed")
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
        self.assertEqual(result["landxml_external_verification_status"], "not_verified")
        self.assertEqual(result["civil3d_external_verification_status"], "not_verified")
        self.assertEqual(result["dwg_support_status"], "unsupported_no_writer")
        self.assertFalse(result["externally_verified"])
        self.assertFalse(result["construction_release_allowed"])
        self.assertTrue(result["construction_release_blocked"])

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
        self.assertEqual(report["supported_deliverables"]["civil3d"]["status"], "not_implemented_not_verified")
        self.assertEqual(report["supported_deliverables"]["dwg"]["status"], "unsupported_no_writer")
        self.assertFalse(report["supported_deliverables"]["civil3d"]["construction_ready"])
        self.assertFalse(report["supported_deliverables"]["dwg"]["construction_ready"])


if __name__ == "__main__":
    unittest.main()
