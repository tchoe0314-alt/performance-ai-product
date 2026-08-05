import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.artifact_service import ArtifactService, HeavyExportBlockedError
from output.dxf_exporter import _prepare_modelspace_actions, get_layer, mark_heavy_export_timeout


class ArtifactServiceTest(unittest.TestCase):
    def test_review_dxf_modelspace_keeps_all_available_disciplines(self):
        actions = [
            {"task": "rectangle", "layer": "SITE", "origin": [0, 0], "width": 100, "height": 100, "canonical_source_id": "site-1"},
            {"task": "rectangle", "layer": "BUILDING", "origin": [20, 20], "width": 20, "height": 20, "canonical_source_id": "building-1"},
            {"task": "polyline", "layer": "PIPE", "points": [[0, 10], [100, 10]], "canonical_source_id": "storm-1"},
            {"task": "polyline", "layer": "WATER", "points": [[0, 20], [100, 20]], "canonical_source_id": "water-1"},
            {"task": "polyline", "layer": "SAN", "points": [[0, 30], [100, 30]], "canonical_source_id": "sanitary-1"},
        ]
        plan = {
            "actions": actions,
            "meta": {"review_export_include_all_systems": True},
        }

        prepared = _prepare_modelspace_actions(plan, actions)
        layers = {get_layer(action, "SITE") for action in prepared}

        self.assertTrue({"SITE", "BUILDING", "PIPE", "WATER", "SAN"}.issubset(layers))

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
            self.assertEqual(sidecar["external_artifact_verification"]["dwg_support_status"], "unsupported_no_native_writer")
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

    def test_export_report_json_compacts_recursive_runtime_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ArtifactService(Path(tmpdir))
            final_plan = {
                "project_name": "Compact Report",
                "actions": [{"task": "polyline", "layer": "LOT", "points": [[0, 0], [1, 0]]}],
                "meta": {},
            }
            artifact_path = service.export_report_json(
                user_id="user-1",
                result_data={
                    "final_plan": final_plan,
                    "metadata": {
                        "workflow": "review",
                        "recommended_option_name": "Option A",
                        "backend_result": {"payload": "x" * 1_000_000},
                    },
                    "request_metadata": {
                        "release_review": {"release_status": "review"},
                        "latest_result": {"payload": "y" * 1_000_000},
                    },
                },
                stem="compact-report",
            )
            report = json.loads(artifact_path.read_text(encoding="utf-8"))

            self.assertLess(artifact_path.stat().st_size, 1_000_000)
            self.assertEqual(report["metadata"]["orchestrator_metadata"]["workflow"], "review")
            self.assertNotIn("backend_result", report["metadata"]["orchestrator_metadata"])
            self.assertNotIn("latest_result", report["metadata"]["request_metadata"])

    def test_export_review_pdf_creates_real_pdf_with_sidecar(self):
        from io import BytesIO

        from PIL import Image
        from pypdf import PdfReader

        with tempfile.TemporaryDirectory() as tmpdir:
            service = ArtifactService(Path(tmpdir))
            preview_buffer = BytesIO()
            Image.new("RGB", (800, 500), "white").save(preview_buffer, format="PNG")
            final_plan = {
                "project_name": "Review PDF Demo",
                "units": "ft",
                "actions": [
                    {
                        "task": "rectangle",
                        "layer": "BUILDING",
                        "x": 10,
                        "y": 20,
                        "width": 80,
                        "height": 40,
                        "canonical_source_id": "building-1",
                    }
                ],
                "meta": {
                    "project_id": "review-pdf-project",
                    "canonical_revision": "rev-pdf-1",
                    "canonical_model_hash": "hash-pdf-1",
                },
            }
            sheet_set = {
                "name": "Review PDF Demo Package",
                "plotStyles": {"reviewWatermark": "REVIEW ONLY"},
                "blockers": ["Confirm utility source."],
                "sheets": [
                    {
                        "name": "Site Plan",
                        "size": "11x17",
                        "titleBlock": {
                            "projectName": "Review PDF Demo",
                            "sheetTitle": "Site Plan",
                            "sheetNumber": "C-1.0",
                            "reviewStage": "Review",
                            "preparedBy": "Civora",
                            "checkedBy": "Reviewer",
                            "date": "2026-08-05",
                        },
                        "viewports": [{"scale": "1:40"}],
                    }
                ],
            }

            with patch.object(service, "build_preview_png", return_value=preview_buffer.getvalue()):
                artifact_path = service.export_review_pdf(
                    user_id="user-1",
                    result_data={"final_plan": final_plan},
                    sheet_set=sheet_set,
                    auto_site_context_summary={"candidateCount": 12, "missingLabels": ["utilities"]},
                    review_package_summary={"missing": ["Confirm utility source."]},
                    stem="review-pdf-demo",
                )

            sidecar_path = artifact_path.with_suffix(f"{artifact_path.suffix}.metadata.json")
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            reader = PdfReader(str(artifact_path))

            self.assertEqual(artifact_path.suffix, ".pdf")
            self.assertTrue(artifact_path.read_bytes().startswith(b"%PDF"))
            self.assertEqual(len(reader.pages), 1)
            self.assertEqual(sidecar["export_type"], "pdf")
            self.assertEqual(sidecar["export_package_report_v1"]["source_project_id"], "review-pdf-project")
            self.assertTrue(sidecar["engineer_review_required"])
            self.assertFalse(sidecar["construction_release_allowed"])


if __name__ == "__main__":
    unittest.main()
