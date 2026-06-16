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
            "active_customer_template": {
                "template_id": "acme_site_template",
                "review_status": "accepted_for_workspace",
                "accepted_for_workspace": True,
                "sections": {
                    "layer_standards": {"layers": [{"name": "C-ANNO-DIMS"}, {"name": "C-UTIL"}]},
                    "label_style": {"styles": [{"key": "company_label", "format": "{label}"}]},
                    "symbol_library": {
                        "blocks": [
                            {
                                "block_id": "hydrant_plan",
                                "kind": "hydrant",
                                "name": "Hydrant",
                                "attribute_fields": ["id", "label", "elevation", "material", "size", "source", "review_note"],
                            }
                        ]
                    },
                    "annotation_standards": {
                        "dimension_styles": [
                            {"key": "linear", "kind": "linear", "precision": 2, "units": "ft", "suffix": "'"},
                            {"key": "aligned", "kind": "aligned", "precision": 2, "units": "ft", "suffix": "'"},
                            {"key": "angular", "kind": "angular", "precision": 1, "units": "deg", "suffix": " deg"},
                        ],
                        "text_styles": [{"key": "company_label", "family": "Inter", "size": 0.12}],
                        "leader_callout_styles": [{"key": "object_callout", "connected_to_objects": True}],
                        "hatch_fill_styles": [
                            {"target": "pavement", "pattern": "ANSI31"},
                            {"target": "building", "pattern": "SOLID"},
                            {"target": "basin", "pattern": "GRAVEL"},
                            {"target": "landscape", "pattern": "AR-SAND"},
                            {"target": "easement_constraint", "pattern": "DOTS"},
                        ],
                        "linetype_styles": [
                            {"target": "existing", "linetype": "CONTINUOUS"},
                            {"target": "proposed", "linetype": "CONTINUOUS"},
                            {"target": "utility", "linetype": "DASHED"},
                            {"target": "row", "linetype": "PHANTOM"},
                            {"target": "easement", "linetype": "HIDDEN"},
                            {"target": "existing_contours", "linetype": "DASHED"},
                            {"target": "proposed_contours", "linetype": "CONTINUOUS"},
                        ],
                    },
                },
            },
            "symbol_instances": [
                {
                    "kind": "hydrant",
                    "attributes": {
                        "id": "HYD-1",
                        "label": "Hydrant 1",
                        "elevation": "101.2",
                        "material": "ductile iron",
                        "size": "6 in",
                        "source": "manual_drawn",
                        "review_note": "Draft hydrant marker.",
                    },
                }
            ],
            "converted_symbol_candidates": [
                {
                    "candidate_id": "gis-valve-1",
                    "kind": "valve",
                    "label": "Valve candidate",
                    "source": "GIS",
                    "confidence": "candidate_review_required",
                }
            ],
            "reference_underlays": [
                {
                    "reference_id": "pdf-underlay-1",
                    "file_type": "pdf",
                    "source": "upload://site-plan.pdf",
                    "source_confidence": "source_underlay_review_required",
                }
            ],
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
        annotation_trace = report["annotation_standard_trace"]
        self.assertEqual(annotation_trace["source"], "customer_template")
        self.assertEqual(annotation_trace["template_id"], "acme_site_template")
        self.assertTrue(annotation_trace["engineer_review_required"])
        self.assertFalse(annotation_trace["construction_release_allowed"])
        self.assertEqual(annotation_trace["supported_annotation_styles"]["dimension_kinds"], ["linear", "aligned", "angular"])
        self.assertIn("pavement", annotation_trace["supported_annotation_styles"]["hatch_targets"])
        self.assertIn("utility", annotation_trace["supported_annotation_styles"]["linetype_targets"])
        self.assertTrue(annotation_trace["template_backed_behavior"]["uses_customer_label_styles_when_present"])
        self.assertEqual(annotation_trace["export_support"]["dxf"].split(";")[0], "supported_where_exporter_maps layers, linetypes, text, blocks, and hatch records")
        symbol_trace = report["symbol_block_reference_trace"]
        self.assertIn("hydrant", symbol_trace["supported_symbols"])
        self.assertEqual(symbol_trace["attribute_fields"], ["id", "label", "elevation", "material", "size", "source", "review_note"])
        self.assertEqual(symbol_trace["symbol_instances"][0]["attributes"]["id"], "HYD-1")
        self.assertTrue(symbol_trace["symbol_instances"][1]["converted_from_candidate"])
        self.assertEqual(symbol_trace["symbol_instances"][1]["engineering_status"], "draft_review_required")
        self.assertTrue(symbol_trace["reference_underlays"][0]["not_editable"])
        self.assertFalse(symbol_trace["native_dwg_block_parity"])
        self.assertFalse(symbol_trace["native_xref_parity"])

        plotting = report["paper_model_plotting_standards_v1"]
        self.assertEqual(plotting["workspace_modes"]["model_space"]["editable_geometry_space"], True)
        self.assertEqual(plotting["workspace_modes"]["sheet_layout"]["plotted_sheet_space"], True)
        self.assertTrue(plotting["sheet_manager"]["sheets"])
        self.assertTrue(plotting["sheet_manager"]["table_of_contents"])
        self.assertTrue(plotting["viewports"][0]["scale_locked"])
        self.assertTrue(plotting["viewports"][0]["north_arrow"])
        self.assertTrue(plotting["viewports"][0]["scale_bar"])
        self.assertIn("layer_visibility", plotting["viewports"][0])
        self.assertTrue(plotting["plot_styles"]["grayscale_option"])
        self.assertEqual(plotting["plot_styles"]["review_watermark"], "REVIEW ONLY - NOT FOR CONSTRUCTION")
        self.assertIn("project_name", plotting["title_block"]["fields"])
        self.assertTrue(plotting["revision_block"]["history"])
        self.assertFalse(plotting["exports"]["approved_construction_documents"])
        self.assertFalse(plotting["exports"]["submission_ready"])
        self.assertFalse(report["plot_package"]["construction_release_allowed"])
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
        self.assertEqual(report["dxf_compatibility_matrix"]["layers"], "verified_by_local_parse_when_export_exists")
        self.assertEqual(report["dxf_compatibility_matrix"]["canonical_ids"], "required_via_sidecar_and_export_audit_traceability")
        self.assertEqual(report["external_workflow_requirements"]["landxml"]["current_state"], "not_verified")
        self.assertEqual(report["external_workflow_requirements"]["civil3d"]["current_state"], "not_verified")
        self.assertTrue(report["external_workflow_requirements"]["dwg"]["external_conversion_hook_required"])
        self.assertFalse(report["external_workflow_requirements"]["dwg"]["native_supported"])
        self.assertIn("no native DWG writer", report["cad_interop_blockers"]["dwg"])
        self.assertIn("target workflow record", report["cad_interop_blockers"]["civil3d"])

    def test_unsupported_civil3d_and_dwg_are_labeled_honestly(self) -> None:
        plan = _plan()
        finalize_export_metadata(plan)
        report = plan["meta"]["export_package_report_v1"]

        self.assertEqual(report["civil3d_compatibility"], "not_verified")
        self.assertEqual(report["dwg_compatibility"], "unsupported_no_native_writer")
        self.assertEqual(report["supported_deliverables"]["civil3d"]["status"], "not_verified")
        self.assertEqual(report["supported_deliverables"]["dwg"]["status"], "unsupported_no_native_writer")
        self.assertFalse(report["supported_deliverables"]["civil3d"]["construction_ready"])
        self.assertFalse(report["supported_deliverables"]["dwg"]["construction_ready"])
        self.assertIn("dwg_capability_matrix", report)
        self.assertEqual(report["dwg_capability_matrix"]["dwg_native"]["status"], "unsupported_no_native_writer")
        self.assertFalse(report["dwg_capability_matrix"]["dwg_native"]["native_writer"])
        self.assertFalse(report["dwg_strategy"]["dwg_native_export_supported"])
        self.assertFalse(report["dwg_strategy"]["dwg_external_conversion_review_artifact_available"])
        self.assertEqual(report["dwg_capability_matrix"]["landxml_exchange"]["workflow_states"], ["not_verified", "blocked_needs_review", "externally_verified_review_only"])
        self.assertEqual(report["dwg_capability_matrix"]["civil3d_native_package"]["workflow_states"], ["not_verified", "blocked_needs_review", "externally_verified_review_only"])
        self.assertGreaterEqual(len(report["dwg_provider_options"]), 3)
        self.assertFalse(any(option["civora_native_support"] for option in report["dwg_provider_options"]))

    def test_dwg_external_conversion_hook_requires_workflow_record(self) -> None:
        plan = _plan()
        plan["meta"]["dwg_conversion_hook"] = {
            "enabled": True,
            "provider": "Autodesk Platform Services Design Automation",
            "hook_id": "dwg-hook-1",
            "source_formats": ["dxf"],
        }

        unverified = build_export_package_report_v1(plan, export_type="dxf", generated_at="2026-06-06T00:00:00Z")

        self.assertEqual(unverified["dwg_compatibility"], "external_conversion_hook_configured_unverified")
        self.assertFalse(unverified["supported_deliverables"]["dwg"]["review_ready"])
        self.assertFalse(unverified["supported_deliverables"]["dwg"]["native_writer"])

        plan["meta"]["external_verification"] = {
            "dwg_conversion": {
                "result": "passed",
                "tool": "AutoCAD",
                "tool_version": "2026",
                "source_artifact_hash": "hash-rev-2",
            }
        }
        verified = build_export_package_report_v1(plan, export_type="dxf", generated_at="2026-06-06T00:00:00Z")

        self.assertEqual(verified["dwg_compatibility"], "external_conversion_hook_configured_review_only")
        self.assertTrue(verified["supported_deliverables"]["dwg"]["available"])
        self.assertTrue(verified["supported_deliverables"]["dwg"]["review_ready"])
        self.assertFalse(verified["supported_deliverables"]["dwg"]["native_writer"])
        self.assertTrue(verified["supported_deliverables"]["dwg"]["review_artifact_only"])
        self.assertFalse(verified["dwg_strategy"]["dwg_native_export_supported"])
        self.assertTrue(verified["dwg_strategy"]["dwg_external_conversion_review_artifact_available"])
        self.assertTrue(verified["dwg_strategy"]["external_workflow_record_present"])

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
                "source_artifacts": ["review.landxml", "review.dxf"],
                "artifact_hashes": {"review.landxml": "sha256-landxml", "review.dxf": "sha256-dxf"},
                "workflow_steps": ["Import LandXML", "Open DXF overlay", "Review pipe network"],
                "import_result": "Imported with warnings",
                "preserved_elements": ["alignments", "pipe runs", "structure labels"],
                "lost_limited_elements": ["Civil 3D styles require remapping"],
                "screenshots_evidence_uri": "s3://evidence/civil3d-landxml-2026-06-06.png",
                "result": "passed",
                "notes": "LandXML import and workflow check completed.",
            }
        }

        report = build_export_package_report_v1(plan, export_type="landxml", generated_at="2026-06-06T00:00:00Z")

        self.assertEqual(report["external_verification"]["civil3d"]["status"], "externally_verified_review_only")
        self.assertEqual(report["civil3d_compatibility"], "externally_verified_review_only")
        self.assertEqual(report["supported_deliverables"]["civil3d"]["status"], "externally_verified_review_only")
        self.assertEqual(report["external_verification"]["civil3d"]["verifier_identity"], "External Engineer")
        self.assertEqual(report["external_verification"]["civil3d"]["verification_date"], "2026-06-06")
        self.assertEqual(report["external_verification"]["civil3d"]["tool"], "Autodesk Civil 3D")
        self.assertEqual(report["external_verification"]["civil3d"]["tool_version"], "2026.1")
        self.assertEqual(report["external_verification"]["civil3d"]["artifact_hashes"]["review.landxml"], "sha256-landxml")
        self.assertIn("pipe runs", report["external_verification"]["civil3d"]["preserved_elements"])
        self.assertIn("Civil 3D styles require remapping", report["external_verification"]["civil3d"]["lost_limited_elements"])
        self.assertEqual(report["external_workflow_requirements"]["civil3d"]["current_state"], "externally_verified_review_only")
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
        self.assertEqual(report["external_verification"]["civil3d"]["status"], "blocked_needs_review")
        self.assertEqual(
            report["external_verification"]["civil3d"]["failure_reason"],
            "external_verification_workflow_evidence_incomplete",
        )

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
