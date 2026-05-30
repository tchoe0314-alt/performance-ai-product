from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from output.dxf_exporter import finalize_export_metadata, save_dxf


def _export_plan() -> dict:
    return {
        "project_name": "Slice 6D Export Metadata",
        "units": "ft",
        "actions": [
            {
                "task": "rectangle",
                "layer": "SITE",
                "origin": [0.0, 0.0],
                "width": 120.0,
                "height": 90.0,
                "label": "Site Boundary",
                "canonical_source_id": "site-1",
                "canonical_source_type": "site",
            },
            {
                "task": "polyline",
                "layer": "PIPE",
                "points": [[10.0, 10.0], [80.0, 40.0]],
                "label": "STORM-1",
                "canonical_source_id": "storm-1",
                "canonical_source_type": "storm_pipe",
            },
        ],
        "meta": {
            "revision": "T1",
            "issue_date": "2026-05-11",
            "deliverables": {
                "requested": ["storm_pipe_plan"],
                "produced": ["site_plan", "storm_pipe_plan"],
            },
            "storm_pipes": {
                "segments": [{"id": "storm-1", "name": "STORM-1", "length_ft": 76.158}],
                "pipe_count": 1,
                "total_length_ft": 76.158,
            },
        },
    }


class Phase1Slice6DExportMetadataTest(unittest.TestCase):
    def test_finalize_export_metadata_populates_sheet_registry_and_export_audit_before_save(self) -> None:
        plan = _export_plan()

        self.assertNotIn("sheet_registry", plan["meta"])
        self.assertNotIn("export_audit", plan["meta"])

        metadata = finalize_export_metadata(plan)

        self.assertTrue(plan["meta"]["sheet_registry"])
        self.assertTrue(plan["meta"]["export_audit"])
        self.assertEqual(metadata["sheet_registry"], plan["meta"]["sheet_registry"])
        self.assertEqual(metadata["export_audit"], plan["meta"]["export_audit"])
        self.assertTrue(plan["meta"]["export_audit"]["sheet_registry_meta_matches_plan"])
        self.assertTrue(plan["meta"]["export_audit"]["production_export_ready"])
        self.assertTrue(plan["meta"]["export_audit"]["canonical_id_traceability"]["ready"])
        self.assertEqual(plan["meta"]["export_audit"]["canonical_id_traceability"]["canonical_summary_ids"], ["storm-1"])

    def test_save_dxf_uses_matching_pre_finalized_metadata(self) -> None:
        plan = _export_plan()
        finalize_export_metadata(plan)
        before_registry = deepcopy(plan["meta"]["sheet_registry"])
        before_audit = deepcopy(plan["meta"]["export_audit"])

        with tempfile.TemporaryDirectory() as tmpdir:
            save_dxf(plan, filename=str(Path(tmpdir) / "slice-6d.dxf"))

        self.assertEqual(plan["meta"]["sheet_registry"], before_registry)
        self.assertEqual(plan["meta"]["export_audit"]["sheet_registry"], before_audit["sheet_registry"])
        self.assertEqual(plan["meta"]["export_audit"]["sheet_total"], before_audit["sheet_total"])
        self.assertTrue(plan["meta"]["export_audit"]["sheet_registry_meta_matches_plan"])

    def test_stale_export_metadata_is_recomputed_from_current_plan(self) -> None:
        plan = _export_plan()
        plan["meta"]["sheet_registry"] = [
            {
                "layout_name": "STALE",
                "sheet_kind": "stale",
                "sheet_number": 99,
                "sheet_total": 99,
            }
        ]
        plan["meta"]["export_audit"] = {"success": False, "sheet_total": 99, "sheet_registry": deepcopy(plan["meta"]["sheet_registry"])}

        metadata = finalize_export_metadata(plan)

        self.assertNotEqual(plan["meta"]["sheet_registry"], [{"layout_name": "STALE", "sheet_kind": "stale", "sheet_number": 99, "sheet_total": 99}])
        self.assertEqual(plan["meta"]["sheet_registry"][0]["layout_name"], "SITE PLAN")
        self.assertEqual(plan["meta"]["export_audit"], metadata["export_audit"])
        self.assertTrue(plan["meta"]["export_audit"]["sheet_registry_meta_matches_plan"])

    def test_export_audit_blocks_orphaned_engineering_ids(self) -> None:
        plan = _export_plan()
        plan["actions"][1]["canonical_source_id"] = "storm-from-stale-plan"

        metadata = finalize_export_metadata(plan)
        traceability = metadata["export_audit"]["canonical_id_traceability"]

        self.assertFalse(metadata["export_audit"]["success"])
        self.assertFalse(metadata["export_audit"]["production_export_ready"])
        self.assertFalse(traceability["ready"])
        self.assertEqual(traceability["orphaned_action_source_ids"], ["storm-from-stale-plan"])
        self.assertEqual(traceability["unmapped_canonical_summary_ids"], ["storm-1"])

    def test_export_audit_blocks_summary_without_stable_id(self) -> None:
        plan = _export_plan()
        plan["meta"]["storm_pipes"]["segments"] = [{"length_ft": 76.158}]

        metadata = finalize_export_metadata(plan)
        traceability = metadata["export_audit"]["canonical_id_traceability"]

        self.assertFalse(metadata["export_audit"]["success"])
        self.assertFalse(metadata["export_audit"]["production_export_ready"])
        self.assertFalse(traceability["ready"])
        self.assertEqual(traceability["missing_summary_source_ids"], ["storm[0]"])

    def test_export_audit_blocks_concept_or_fallback_engineering_sources(self) -> None:
        plan = _export_plan()
        plan["meta"]["storm_pipes"]["segments"][0]["source"] = "surface_fallback"
        plan["meta"]["storm_pipes"]["segments"][0]["hydraulic_basis"] = "rational_method_concept"

        metadata = finalize_export_metadata(plan)
        audit = metadata["export_audit"]
        traceability = audit["canonical_id_traceability"]

        self.assertFalse(audit["success"])
        self.assertFalse(audit["production_export_ready"])
        self.assertTrue(audit["export_blocked"])
        self.assertIn("concept_or_fallback_engineering_sources", audit["blocked_reasons"])
        self.assertEqual(traceability["concept_engineering_source_ids"], ["storm-1"])

    def test_export_audit_blocks_when_release_review_is_blocked(self) -> None:
        plan = _export_plan()
        plan["meta"]["release_review"] = {
            "release_status": "blocked",
            "release_ready": False,
            "blocked_reasons": ["construction_package_blocked"],
        }

        metadata = finalize_export_metadata(plan)
        audit = metadata["export_audit"]

        self.assertFalse(audit["success"])
        self.assertFalse(audit["production_export_ready"])
        self.assertTrue(audit["export_blocked"])
        self.assertIn("construction_package_blocked", audit["blocked_reasons"])
        self.assertIn("release_status_blocked", audit["blocked_reasons"])
        self.assertIn("final_plan_release_not_ready", audit["blocked_reasons"])
        self.assertEqual(audit["release_readiness"]["release_status"], "blocked")

    def test_export_audit_blocks_failed_deliverables_from_final_meta(self) -> None:
        plan = _export_plan()
        plan["meta"]["release_status"] = "ready"
        plan["meta"]["release_ready"] = True
        plan["meta"]["deliverables"]["failed"] = ["report"]

        metadata = finalize_export_metadata(plan)
        audit = metadata["export_audit"]

        self.assertFalse(audit["success"])
        self.assertFalse(audit["production_export_ready"])
        self.assertTrue(audit["export_blocked"])
        self.assertIn("failed_deliverable_report", audit["blocked_reasons"])
        self.assertIn("failed_deliverable_report", audit["release_readiness"]["release_blockers"])

    def test_export_audit_blocks_missing_deliverables_from_release_review(self) -> None:
        plan = _export_plan()
        plan["meta"]["release_status"] = "ready"
        plan["meta"]["release_ready"] = True
        plan["meta"]["release_review"] = {
            "release_status": "ready",
            "release_ready": True,
            "requested_deliverables": ["storm_pipe_plan", "report"],
            "produced_deliverables": ["storm_pipe_plan"],
        }

        metadata = finalize_export_metadata(plan)
        audit = metadata["export_audit"]

        self.assertFalse(audit["success"])
        self.assertFalse(audit["production_export_ready"])
        self.assertTrue(audit["export_blocked"])
        self.assertIn("missing_deliverable_report", audit["blocked_reasons"])
        self.assertIn("missing_deliverable_report", audit["release_readiness"]["release_blockers"])

    def test_export_audit_blocks_stored_run_errors(self) -> None:
        plan = _export_plan()
        plan["meta"]["release_status"] = "ready"
        plan["meta"]["release_ready"] = True
        plan["meta"]["run_summary"] = {"success": True, "error_count": 1}

        metadata = finalize_export_metadata(plan)
        audit = metadata["export_audit"]

        self.assertFalse(audit["success"])
        self.assertFalse(audit["production_export_ready"])
        self.assertTrue(audit["export_blocked"])
        self.assertIn("planner_errors_present", audit["blocked_reasons"])
        self.assertIn("planner_errors_present", audit["release_readiness"]["release_blockers"])

    def test_export_audit_blocks_manual_validation_failures_from_final_meta(self) -> None:
        plan = _export_plan()
        plan["meta"]["release_status"] = "ready"
        plan["meta"]["release_ready"] = True
        plan["meta"]["manual_validation"] = {
            "failures": [
                {
                    "code": "MANUAL_STORM_HYDRAULIC_INVALID",
                    "message": "Manual storm pipe hydraulic validation failed.",
                    "system": "storm",
                    "rule": "hydraulic_capacity",
                }
            ]
        }

        metadata = finalize_export_metadata(plan)
        audit = metadata["export_audit"]

        self.assertFalse(audit["success"])
        self.assertFalse(audit["production_export_ready"])
        self.assertTrue(audit["export_blocked"])
        self.assertIn("manual_validation_manual_storm_hydraulic_invalid", audit["blocked_reasons"])
        self.assertIn(
            "manual_validation_manual_storm_hydraulic_invalid",
            audit["release_readiness"]["release_blockers"],
        )

    def test_export_audit_blocks_required_construction_release_without_readiness(self) -> None:
        plan = _export_plan()
        plan["meta"]["construction_release_required"] = True

        metadata = finalize_export_metadata(plan)
        audit = metadata["export_audit"]

        self.assertFalse(audit["success"])
        self.assertFalse(audit["production_export_ready"])
        self.assertTrue(audit["export_blocked"])
        self.assertIn("construction_readiness_missing", audit["blocked_reasons"])
        self.assertTrue(audit["release_readiness"]["construction_release_required"])

    def test_export_audit_blocks_raw_deliverable_package_alias_without_release_manifest(self) -> None:
        plan = _export_plan()
        plan["meta"]["construction_deliverable_package"] = {
            "id": "PKG-RAW-1",
            "release_ready": True,
            "production_ready": True,
            "artifacts": [
                {"type": "sheets", "id": "SHEETS-1"},
                {"type": "cad_export", "id": "CAD-1"},
            ],
        }

        metadata = finalize_export_metadata(plan)
        audit = metadata["export_audit"]

        self.assertFalse(audit["success"])
        self.assertFalse(audit["production_export_ready"])
        self.assertTrue(audit["export_blocked"])
        self.assertTrue(audit["release_readiness"]["construction_release_required"])
        self.assertIn("construction_readiness_missing", audit["blocked_reasons"])
        self.assertIn("construction_package_blocked", audit["blocked_reasons"])
        self.assertIn("construction_package_artifact_status_missing", audit["blocked_reasons"])

    def test_export_audit_blocks_false_allowed_package_without_release_proof(self) -> None:
        plan = _export_plan()
        plan["meta"]["construction_readiness"] = {"ready": True, "status": "construction_ready", "blockers": []}
        plan["meta"]["construction_package_manifest"] = {
            "release_allowed": True,
            "construction_package_artifact_status": {
                "complete_for_release": True,
                "model_matches_expected": True,
                "release_ready_flag": None,
            },
        }

        metadata = finalize_export_metadata(plan)
        audit = metadata["export_audit"]

        self.assertFalse(audit["success"])
        self.assertFalse(audit["production_export_ready"])
        self.assertTrue(audit["export_blocked"])
        self.assertIn("construction_package_release_not_marked_ready", audit["blocked_reasons"])
        self.assertIn("construction_professional_release_missing", audit["blocked_reasons"])
        self.assertTrue(audit["release_readiness"]["construction_release_required"])

    def test_export_audit_blocks_false_allowed_package_with_invalid_professional_release(self) -> None:
        plan = _export_plan()
        plan["meta"]["construction_readiness"] = {"ready": True, "status": "construction_ready", "blockers": []}
        plan["meta"]["construction_package_manifest"] = {
            "release_allowed": True,
            "construction_package_artifact_status": {
                "complete_for_release": True,
                "model_matches_expected": True,
                "release_ready_flag": True,
            },
            "professional_package_release_status": {
                "professional_release_valid": False,
                "model_matches_package": True,
                "package_matches_review": True,
            },
        }

        metadata = finalize_export_metadata(plan)
        audit = metadata["export_audit"]

        self.assertFalse(audit["success"])
        self.assertFalse(audit["production_export_ready"])
        self.assertTrue(audit["export_blocked"])
        self.assertIn("construction_professional_release_invalid", audit["blocked_reasons"])
        self.assertNotIn("construction_professional_release_missing", audit["blocked_reasons"])


if __name__ == "__main__":
    unittest.main()
