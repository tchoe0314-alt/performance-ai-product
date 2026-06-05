import tempfile
import unittest
from pathlib import Path

import planner
from backend.application.project_workflows import artifact_summary
from backend.planning.private_alpha_readiness import build_private_alpha_readiness


def _ready_meta() -> dict:
    return {
        "product_mode": "private_alpha",
        "construction_package_manifest": {
            "construction_release_guard": {
                "product_mode": "private_alpha",
                "review_only": True,
                "construction_release_enabled": False,
                "construction_release_blocked": True,
                "guard_reason": "Private alpha/review-only mode blocks construction release.",
            }
        },
        "engine_readiness": {
            "summary": {
                "alpha_readiness": {
                    "status": "ready",
                    "ready_engine_count": 20,
                    "applicable_engine_count": 20,
                    "blocked_engine_ids": [],
                    "needs_review_engine_ids": [],
                    "top_issues": [],
                }
            }
        },
        "existing_conditions_summary": {"production_ready": True},
        "existing_conditions_package": {
            "status": "ready",
            "production_ready": True,
            "accepted": True,
            "blockers": [],
            "warnings": [],
        },
        "standards_acceptance": {
            "production_validation": {
                "status": "ready",
                "production_usable": True,
            }
        },
        "export_audit": {
            "ready": True,
            "production_export_ready": True,
            "export_blocked": False,
        },
        "golden_scenario_report": {"status": "passed", "success": True},
        "alpha_monitoring_report": {"status": "healthy", "success": True},
    }


class PrivateAlphaReadinessTests(unittest.TestCase):
    def test_missing_evidence_blocks_full_system_alpha(self) -> None:
        readiness = build_private_alpha_readiness({"meta": {"product_mode": "private_alpha"}})

        self.assertEqual(readiness["status"], "blocked")
        self.assertFalse(readiness["full_system_private_alpha_ready"])
        self.assertTrue(readiness["review_only"])
        self.assertTrue(readiness["construction_release_blocked"])
        self.assertFalse(readiness["construction_release_allowed"])
        fields = {(item["area"], item["field"]) for item in readiness["blockers"]}
        self.assertIn(("engines", "engine_readiness"), fields)
        self.assertIn(("existing_conditions", "existing_conditions_package"), fields)
        self.assertIn(("standards", "standards_package"), fields)
        self.assertIn(("deliverables", "export_audit"), fields)
        self.assertIn(("golden_scenarios", "golden_scenario_report"), fields)
        self.assertIn(("monitoring", "alpha_monitoring_report"), fields)
        self.assertTrue(readiness["blocker_details"])
        self.assertTrue(readiness["next_actions"])

    def test_alpha_ready_keeps_construction_release_blocked(self) -> None:
        readiness = build_private_alpha_readiness({"meta": _ready_meta()})

        self.assertEqual(readiness["status"], "ready")
        self.assertTrue(readiness["full_system_private_alpha_ready"])
        self.assertTrue(readiness["review_only"])
        self.assertTrue(readiness["construction_release_blocked"])
        self.assertFalse(readiness["construction_release_allowed"])
        self.assertFalse(readiness["construction_ready"])
        self.assertEqual(readiness["launch_recommendation"], "private_alpha_review_ready")
        self.assertEqual(readiness["blocker_count"], 0)

    def test_alpha_guard_blocks_false_construction_release_in_private_alpha(self) -> None:
        meta = _ready_meta()
        meta["construction_package_manifest"]["construction_release_guard"] = {
            "product_mode": "private_alpha",
            "review_only": True,
            "construction_release_enabled": True,
            "construction_release_blocked": False,
        }

        readiness = build_private_alpha_readiness({"meta": meta})

        self.assertEqual(readiness["status"], "blocked")
        self.assertFalse(readiness["full_system_private_alpha_ready"])
        fields = {(item["area"], item["field"]) for item in readiness["blockers"]}
        self.assertIn(("release_guard", "construction_release_guard"), fields)

    def test_build_plan_attaches_private_alpha_readiness(self) -> None:
        plan = planner.build_plan(
            {
                "project_name": "Alpha Readiness Smoke",
                "units": "ft",
                "mode": "site_plan",
                "lot": {"x": 0.0, "y": 0.0, "w": 120.0, "h": 100.0},
                "site_plan": {"building_width": 40.0, "building_depth": 30.0, "parking_count": 12},
            }
        )

        readiness = plan["meta"]["private_alpha_readiness"]
        self.assertEqual(readiness["version"], "private_alpha_readiness_v1")
        self.assertEqual(readiness["status"], "blocked")
        self.assertFalse(readiness["construction_release_allowed"])
        self.assertTrue(readiness["construction_release_blocked"])
        self.assertIn("existing_conditions", readiness["sections"])

    def test_artifact_summary_carries_private_alpha_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text("x")
            summary = artifact_summary(
                path=path,
                artifact_kind="report",
                project_id="p1",
                result_data={
                    "final_plan": {
                        "project_name": "Alpha Artifact",
                        "meta": {"private_alpha_readiness": build_private_alpha_readiness({"meta": _ready_meta()})},
                    }
                },
            )

        alpha = summary["private_alpha_readiness"]
        self.assertEqual(alpha["status"], "ready")
        self.assertTrue(alpha["full_system_private_alpha_ready"])
        self.assertTrue(alpha["review_only"])
        self.assertTrue(alpha["construction_release_blocked"])
        self.assertFalse(alpha["construction_release_allowed"])


if __name__ == "__main__":
    unittest.main()
