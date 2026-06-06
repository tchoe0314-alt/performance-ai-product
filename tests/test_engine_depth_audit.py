import json
import tempfile
import unittest
from pathlib import Path

from backend.planning.engine_depth_audit import (
    CLASS_CONCEPT,
    CLASS_REVIEW,
    REPORT_VERSION,
    run_engine_depth_audit,
    run_engine_depth_audit_for_scenario,
    run_engine_depth_audit_scenario,
)
from backend.planning.engine_readiness import evaluate_engine_readiness
from backend.planning.engine_contracts import engine_contracts
from backend.planning.golden_runner import run_golden_scenario
from core.civil_design import civil_design_readiness
from tests.test_civil_design_readiness import _complete_meta


def _review_depth_meta() -> dict:
    meta = _complete_meta()
    meta["lot"] = {"w": 220.0, "h": 160.0, "area_sf": 35200.0}
    meta["building_count"] = 1
    meta["parking_program"] = {"stall_count": 36}
    meta["truth_audit"] = {"success": True}
    meta["manual_validation"] = {"success": True, "failures": []}
    meta["quantities"] = {
        "success": True,
        "totals": {"lot_area_sf": 35200.0, "pipe_length_ft": 80.0, "estimated_parking_stalls": 36},
        "explain": {
            "meta_summary": {"quantity_traceability_complete": True},
            "quantity_audit": {"pipe_length_ft": {"source_object_ids": ["storm-1"]}},
            "trace_gaps": {},
        },
    }
    meta["cost_estimate"] = {
        "success": False,
        "totals": {},
        "explain": {"pricing": {"production_usable": False}, "trace_gaps": {}, "pricing_coverage_gaps": {}},
    }
    meta["export_audit"] = {
        "ready": True,
        "production_export_ready": False,
        "export_blocked": False,
        "canonical_id_traceability": {"ready": True},
    }
    meta["construction_readiness"] = {
        "ready": False,
        "status": "not_construction_ready",
        "blockers": [{"area": "existing_conditions", "field": "survey_surface"}],
    }
    meta["construction_package_manifest"] = {
        "release_allowed": False,
        "construction_ready": False,
        "blockers": [{"area": "existing_conditions", "field": "survey_surface"}],
    }
    return meta


def _review_depth_plan(payload: dict) -> dict:
    meta = _review_depth_meta()
    meta["lot"] = payload.get("lot") or meta["lot"]
    plan = {
        "project_name": payload.get("project_name"),
        "actions": [
            {
                "task": "rectangle",
                "layer": "SITE",
                "canonical_source_type": "site",
                "canonical_source_id": "site-1",
                "width": 220.0,
                "height": 160.0,
            }
        ],
        "meta": meta,
    }
    meta["civil_design_readiness"] = civil_design_readiness(plan)
    meta["engine_readiness"] = evaluate_engine_readiness(plan)
    return plan


def _concept_plan(payload: dict) -> dict:
    return {
        "project_name": payload.get("project_name"),
        "meta": {
            "civil_design_readiness": {
                "status": "blocked",
                "success": False,
                "production_ready": False,
                "production_blockers": [{"area": "site", "field": "site_boundary"}],
                "missing_requirements": [{"system": "site", "field": "site_boundary"}],
            },
            "construction_readiness": {"ready": False, "blockers": [{"area": "site", "field": "site_boundary"}]},
            "construction_package_manifest": {"release_allowed": False, "construction_ready": False},
        },
    }


class EngineDepthAuditTests(unittest.TestCase):
    def test_scenario_report_classifies_required_engines_and_gate_labels(self) -> None:
        report = run_engine_depth_audit_scenario("small_commercial_pad", build_plan_fn=_review_depth_plan)

        self.assertTrue(report["success"], report)
        self.assertEqual(report["status"], "passed")
        self.assertIn("deterministic_checks", report)
        self.assertFalse(report["failed_check_ids"])
        storm = report["required_engine_results"]["storm_pipe"]
        self.assertIn(storm["actual_depth_classification"], {"review", "production-depth"})
        self.assertIn(
            storm["backend_readiness_gate_label"],
            {"expected_engine_depth_actual_review", "expected_production_depth_actual_production_depth"},
        )
        self.assertTrue(
            any(check["check_type"] == "expected_vs_actual_engine_depth" for check in report["deterministic_checks"])
        )
        self.assertTrue(
            any(check["check_type"] == "expected_vs_actual_metric" for check in report["deterministic_checks"])
        )

    def test_audit_report_contract_preserves_phase_1_truth_labels(self) -> None:
        report = run_engine_depth_audit(scenario_ids=["small_commercial_pad"], build_plan_fn=_review_depth_plan)

        self.assertEqual(report["version"], REPORT_VERSION)
        self.assertEqual(report["phase"], "phase_1_engine_depth_audit")
        self.assertTrue(report["success"], report)
        self.assertEqual(report["backend_readiness_gate_label"], "phase_1_backend_depth_audit_passed")
        self.assertFalse(report["construction_ready"])
        self.assertFalse(report["construction_release_allowed"])
        self.assertEqual(report["scenario_count"], 1)
        self.assertGreater(report["deterministic_check_count"], 0)
        self.assertIn("overall_depth_score", report["summary"])
        self.assertGreaterEqual(report["summary"]["overall_depth_score"], 60.0)
        self.assertEqual(report["summary"]["private_alpha_gate_recommendation"], "allow_backend_private_alpha")
        self.assertEqual(report["summary"]["public_beta_gate_recommendation"], "allow_backend_public_beta_review_only")
        self.assertEqual(report["summary"]["construction_gate_recommendation"], "block_construction_not_production_depth")
        self.assertFalse(report["construction_depth_requirements_met"])
        self.assertFalse(report["construction_ready"])
        self.assertIn(CLASS_REVIEW, report["classification_counts"])
        self.assertIn("storm_pipe", report["engine_results"])
        self.assertEqual(len(report["engine_rows"]), len(engine_contracts()))
        row = report["engine_results"]["storm_pipe"]
        for field in ("score", "classification", "checks", "blockers", "first_failing_layer", "confidence", "launch_gate"):
            self.assertIn(field, row)
        self.assertEqual(row["launch_gate"], "review_launch_allowed")
        self.assertGreater(row["confidence"], 0.0)
        self.assertIn("does not modify UI", report["truth_label"])

    def test_single_scenario_helper_returns_full_report_contract(self) -> None:
        report = run_engine_depth_audit_for_scenario("small_commercial_pad", build_plan_fn=_review_depth_plan)

        self.assertEqual(report["version"], REPORT_VERSION)
        self.assertEqual(report["scenario_count"], 1)
        self.assertEqual(report["scenario_results"][0]["scenario_id"], "small_commercial_pad")
        self.assertEqual(len(report["engine_rows"]), len(engine_contracts()))

    def test_concept_or_missing_required_engine_blocks_backend_gate(self) -> None:
        report = run_engine_depth_audit(scenario_ids=["small_commercial_pad"], build_plan_fn=_concept_plan)

        self.assertFalse(report["success"])
        self.assertEqual(report["backend_readiness_gate_label"], "phase_1_backend_depth_audit_blocked")
        self.assertGreater(report["failed_deterministic_check_count"], 0)
        self.assertGreater(report["blocker_count"], 0)
        self.assertEqual(report["engine_results"]["storm_pipe"]["actual_depth_classification"], CLASS_CONCEPT)
        self.assertEqual(
            report["engine_results"]["storm_pipe"]["backend_readiness_gate_label"],
            "backend_blocked_concept_or_missing",
        )
        self.assertTrue(report["blocker_details"][0]["next_action"])

    def test_audit_writes_report_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "engine_depth_audit.json"
            report = run_engine_depth_audit(
                scenario_ids=["small_commercial_pad"],
                build_plan_fn=_review_depth_plan,
                output_path=target,
            )
            written = json.loads(target.read_text(encoding="utf-8"))

        self.assertEqual(written["version"], REPORT_VERSION)
        self.assertEqual(written["status"], report["status"])
        self.assertIn("deterministic_checks", written)

    def test_report_serialization_is_stable_for_ci(self) -> None:
        first = run_engine_depth_audit(scenario_ids=["small_commercial_pad"], build_plan_fn=_review_depth_plan)
        second = run_engine_depth_audit(scenario_ids=["small_commercial_pad"], build_plan_fn=_review_depth_plan)

        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        golden = first["scenario_results"][0]["golden_result"]
        self.assertNotIn("load_threshold_results", golden)
        self.assertIn("failed_load_thresholds", golden)

    def test_golden_scenario_references_engine_depth_audit_contract(self) -> None:
        result = run_golden_scenario("small_commercial_pad", build_plan_fn=_review_depth_plan)

        reference = result["engine_depth_audit"]
        self.assertEqual(reference["report_version"], REPORT_VERSION)
        self.assertEqual(reference["scenario_id"], "small_commercial_pad")
        self.assertEqual(reference["helper"], "backend.planning.engine_depth_audit.run_engine_depth_audit_for_scenario")
        self.assertTrue(reference["reference_only"])


if __name__ == "__main__":
    unittest.main()
