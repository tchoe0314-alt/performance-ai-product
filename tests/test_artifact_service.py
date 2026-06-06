import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.artifact_service import ArtifactService, HeavyExportBlockedError
from output.dxf_exporter import mark_heavy_export_timeout


class ArtifactServiceTest(unittest.TestCase):
    def test_build_preview_png_reuses_cached_render(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ArtifactService(Path(tmpdir))
            final_plan = {
                "project_name": "Cache Demo",
                "units": "ft",
                "actions": [{"task": "rectangle", "layer": "BUILDING", "x": 0, "y": 0, "width": 10, "height": 10}],
            }

            with patch(
                "backend.services.artifact_service.render_plan_preview_png",
                return_value=b"preview-bytes",
            ) as render_mock:
                first = service.build_preview_png(final_plan)
                second = service.build_preview_png(final_plan)

            self.assertEqual(first, b"preview-bytes")
            self.assertEqual(second, b"preview-bytes")
            self.assertEqual(render_mock.call_count, 1)

    def test_build_preview_png_invalidates_cache_when_renderer_version_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ArtifactService(Path(tmpdir))
            final_plan = {
                "project_name": "Cache Demo",
                "units": "ft",
                "actions": [{"task": "rectangle", "layer": "BUILDING", "x": 0, "y": 0, "width": 10, "height": 10}],
            }

            with patch(
                "backend.services.artifact_service.render_plan_preview_png",
                side_effect=[b"preview-v1", b"preview-v2"],
            ) as render_mock:
                first = service.build_preview_png(final_plan)
                service.preview_cache_version = "test-next-version"
                second = service.build_preview_png(final_plan)

            self.assertEqual(first, b"preview-v1")
            self.assertEqual(second, b"preview-v2")
            self.assertEqual(render_mock.call_count, 2)

    def test_export_dxf_writes_sidecar_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ArtifactService(Path(tmpdir))
            final_plan = {
                "project_id": "sidecar-project",
                "project_name": "Sidecar Demo",
                "units": "ft",
                "actions": [
                    {
                        "task": "polyline",
                        "layer": "PIPE",
                        "points": [[0.0, 0.0], [25.0, 0.0]],
                        "canonical_source_id": "storm-line-1",
                    }
                ],
                "meta": {
                    "project_id": "sidecar-project",
                    "canonical_revision": "rev-sidecar-1",
                    "canonical_model_hash": "hash-sidecar-1",
                    "quantities": {
                        "line_items": [
                            {
                                "metric": "pipe_length_ft",
                                "quantity": 25.0,
                                "unit": "lf",
                                "source_object_ids": ["storm-line-1"],
                            }
                        ]
                    },
                },
            }

            artifact_path = service.export_dxf(user_id="user-1", final_plan=final_plan, stem="sidecar")
            sidecar_path = artifact_path.with_suffix(f"{artifact_path.suffix}.metadata.json")
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))

            self.assertTrue(artifact_path.exists())
            self.assertTrue(sidecar_path.exists())
            self.assertEqual(sidecar["source"], "export_artifact_sidecar_v1")
            self.assertEqual(sidecar["export_type"], "dxf")
            self.assertEqual(sidecar["export_package_report_v1"]["source_project_id"], "sidecar-project")
            self.assertEqual(sidecar["export_package_report_v1"]["source_canonical_revision"], "rev-sidecar-1")
            self.assertTrue(sidecar["engineer_review_required"])
            self.assertFalse(sidecar["civora_signoff_allowed"])
            self.assertFalse(sidecar["construction_release_allowed"])
            self.assertTrue(sidecar["construction_release_blocked"])
            self.assertEqual(sidecar["external_artifact_verification"]["format"], "dxf")
            self.assertEqual(sidecar["external_artifact_verification"]["local_parse_status"], "passed")
            self.assertEqual(sidecar["external_artifact_verification"]["layer_contract_status"], "passed")
            self.assertEqual(
                sidecar["external_artifact_verification"]["civil3d_external_verification_status"],
                "not_verified",
            )
            self.assertEqual(sidecar["external_artifact_verification"]["dwg_support_status"], "unsupported_no_writer")
            self.assertFalse(sidecar["external_artifact_verification"]["externally_verified"])
            self.assertEqual(sidecar["quantity_line_items"][0]["canonical_ids"], ["storm-line-1"])
            self.assertEqual(final_plan["meta"]["artifact_sidecars"][0]["sidecar_metadata_path"], str(sidecar_path))

    def test_heavy_dxf_export_timeout_returns_blocker_without_fake_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ArtifactService(Path(tmpdir), heavy_export_timeout_seconds=0.000001)
            final_plan = {
                "project_name": "Timeout Demo",
                "units": "ft",
                "actions": [
                    {
                        "task": "polyline",
                        "layer": "PIPE",
                        "points": [[0.0, 0.0], [25.0, 0.0]],
                        "canonical_source_id": "storm-timeout-1",
                    }
                ],
                "meta": {},
            }

            with self.assertRaises(HeavyExportBlockedError) as ctx:
                service.export_dxf(user_id="user-1", final_plan=final_plan, stem="timeout")

            self.assertEqual(ctx.exception.code, "heavy_export_timeout")
            self.assertTrue(ctx.exception.metadata["review_only"])
            self.assertFalse(ctx.exception.metadata["construction_release_allowed"])
            self.assertEqual(ctx.exception.metadata["recommended_path"], "async_queue_heavy_export")
            self.assertIn("heavy_export_timeout", final_plan["meta"]["export_audit"]["blocked_reasons"])
            self.assertFalse(final_plan["meta"]["export_package_report_v1"]["construction_release_allowed"])
            self.assertFalse(final_plan["meta"]["export_package_report_v1"]["supported_deliverables"]["dxf"]["review_ready"])
            self.assertFalse(list((Path(tmpdir) / "user-1").glob("*.dxf")))

    def test_skipped_heavy_export_report_remains_review_only_without_dxf_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ArtifactService(Path(tmpdir))
            final_plan = {
                "project_id": "skip-project",
                "project_name": "Skipped Heavy Export",
                "units": "ft",
                "actions": [
                    {
                        "task": "polyline",
                        "layer": "PIPE",
                        "points": [[0.0, 0.0], [50.0, 0.0]],
                        "canonical_source_id": "storm-skip-1",
                    }
                ],
                "meta": {
                    "project_id": "skip-project",
                    "cad_interop": {
                        "compatibility_checks": [
                            {
                                "format": "dxf",
                                "available": True,
                                "review_ready": True,
                                "construction_ready": False,
                                "status": "ready",
                            }
                        ]
                    },
                },
            }
            mark_heavy_export_timeout(
                final_plan,
                stage="test.skip",
                timeout_seconds=0.01,
                elapsed_seconds=0.02,
            )

            artifact_path = service.export_report_json(
                user_id="user-1",
                result_data={"final_plan": final_plan, "metadata": {}, "assumptions": [], "warnings": [], "errors": []},
                stem="skipped-heavy-export",
            )
            report = json.loads(artifact_path.read_text(encoding="utf-8"))
            package = report["export_package_report_v1"]

            self.assertEqual(package["export_type"], "report")
            self.assertFalse(package["construction_release_allowed"])
            self.assertIn("heavy_export_timeout", package["construction_release_blockers"])
            self.assertEqual(package["deliverable_confidence"], "construction_blocked")
            self.assertFalse(package["supported_deliverables"]["dxf"]["review_ready"])
            self.assertTrue(package["engineer_review_required"])
            self.assertFalse(package["civora_signoff_allowed"])
            self.assertFalse(list((Path(tmpdir) / "user-1").glob("*.dxf")))

    def test_export_report_json_writes_sidecar_and_report_references(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ArtifactService(Path(tmpdir))
            final_plan = {
                "project_id": "report-project",
                "project_name": "Report Sidecar Demo",
                "units": "ft",
                "actions": [
                    {
                        "task": "polyline",
                        "layer": "PIPE",
                        "points": [[0.0, 0.0], [50.0, 0.0]],
                        "canonical_source_id": "report-storm-1",
                    }
                ],
                "meta": {
                    "project_id": "report-project",
                    "canonical_revision": "rev-report-1",
                    "canonical_model_hash": "hash-report-1",
                    "quantities": {
                        "line_items": [
                            {
                                "metric": "pipe_length_ft",
                                "quantity": 50.0,
                                "unit": "lf",
                                "source_object_ids": ["report-storm-1"],
                            }
                        ]
                    },
                },
            }

            artifact_path = service.export_report_json(
                user_id="user-1",
                result_data={"final_plan": final_plan, "metadata": {}, "assumptions": [], "warnings": [], "errors": []},
                stem="report-sidecar",
            )
            report = json.loads(artifact_path.read_text(encoding="utf-8"))
            sidecar_path = artifact_path.with_suffix(f"{artifact_path.suffix}.metadata.json")
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))

            self.assertEqual(report["artifact_metadata"]["sidecar_metadata_path"], str(sidecar_path))
            self.assertEqual(report["export_package_report_v1"]["export_type"], "report")
            self.assertEqual(sidecar["export_type"], "report")
            self.assertEqual(
                sidecar["export_package_report_ref"]["source_canonical_hash"],
                report["export_package_report_v1"]["source_canonical_hash"],
            )
            self.assertTrue(sidecar["report_line_items"])
            self.assertIn("report-storm-1", sidecar["report_line_items"][0]["canonical_ids"])
            self.assertEqual(sidecar["quantity_line_items"][0]["canonical_ids"], ["report-storm-1"])


if __name__ == "__main__":
    unittest.main()
