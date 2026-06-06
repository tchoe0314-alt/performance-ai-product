import json
import tempfile
import unittest
from pathlib import Path

from backend.application.private_alpha_readiness_audit import run_private_alpha_backend_readiness_audit


def _healthy_sample() -> dict:
    return {
        "status": "ok",
        "monitoring": {
            "status": "healthy",
            "rss_mb": 120.0,
            "peak_rss_mb": 150.0,
            "warnings": [],
            "job_queue": {
                "status": "healthy",
                "monitored_job_types": ["orchestrate", "drainage_only"],
                "queued_count": 0,
                "failed_recent_count": 0,
                "stale_job_count": 0,
                "oldest_active_age_sec": 0.0,
            },
            "process": {
                "status": "healthy",
                "recent_start_count": 1,
                "previous_shutdown_clean": True,
                "state_file": "/Users/tommychoe/Documents/Playground/Civora AI/data/runtime_monitoring.json",
            },
        },
        "storage_dir": "/Users/tommychoe/Documents/Playground/Civora AI/data",
        "mapbox_token_prefix": "pk.secret-prefix",
    }


def _fake_plan(payload: dict) -> dict:
    return {
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
        "meta": {
            "lot": {"w": 220.0, "h": 160.0},
            "grading": {"proposed_surface": {"source": "test"}, "low_points": [{"id": "lp-1"}]},
            "drainage": {"basins": [{"id": "basin-1"}]},
            "storm_pipes": {"segments": [{"id": "storm-1", "length_ft": 50.0}]},
            "sanitary": {"segments": [{"id": "san-1", "length_ft": 40.0}]},
            "utilities": {"conflict_hooks": {"utility_segments": [{"id": "util-1"}]}},
            "quantities": {"totals": {"pipe_length_ft": 50.0}},
            "civil_design_readiness": {
                "status": "needs_engineering_review",
                "success": True,
                "production_ready": False,
                "critical_blockers": [],
                "production_blockers": [{"area": "existing_conditions", "field": "survey_surface"}],
                "missing_requirements": [],
            },
            "engine_readiness": {
                "production_ready": False,
                "blocked_engine_ids": [],
                "production_blocked_engine_ids": ["gis_existing_conditions"],
            },
            "construction_readiness": {
                "ready": False,
                "status": "not_construction_ready",
                "blockers": [{"area": "existing_conditions", "field": "survey"}],
            },
            "construction_package_manifest": {
                "release_allowed": False,
                "construction_ready": False,
                "blockers": [{"area": "existing_conditions", "field": "survey"}],
            },
        },
    }


class PrivateAlphaReadinessAuditTests(unittest.TestCase):
    def test_audit_ready_when_monitoring_and_golden_scenarios_pass(self) -> None:
        report = run_private_alpha_backend_readiness_audit(
            iterations=2,
            sample_runtime=_healthy_sample,
            scenario_ids=["small_commercial_pad", "incomplete_bad_input_case"],
            build_plan_fn=_fake_plan,
            thresholds={"max_rss_mb": 256, "max_peak_rss_mb": 512},
        )

        self.assertTrue(report["success"])
        self.assertEqual(report["status"], "ready")
        self.assertTrue(report["private_alpha_backend_ready"])
        self.assertFalse(report["construction_ready"])
        self.assertFalse(report["construction_release_allowed"])
        self.assertTrue(report["construction_release_blocked"])
        self.assertEqual(report["sections"]["monitoring"]["status"], "ready")
        self.assertEqual(report["sections"]["golden_scenarios"]["status"], "passed")
        self.assertEqual(report["blocker_count"], 0)
        self.assertIn("does not make Civora construction-ready", report["truth_label"])

    def test_audit_blocks_failed_monitoring(self) -> None:
        report = run_private_alpha_backend_readiness_audit(
            iterations=1,
            sample_runtime=lambda: {"status": "ok", "monitoring": {"status": "healthy", "rss_mb": 10.0}},
            scenario_ids=["small_commercial_pad"],
            build_plan_fn=_fake_plan,
        )

        self.assertFalse(report["success"])
        self.assertEqual(report["sections"]["monitoring"]["status"], "blocked")
        self.assertIn("monitoring", {item["area"] for item in report["blockers"]})
        self.assertTrue(report["blocker_details"])

    def test_local_dev_missing_queue_is_reported_unavailable_without_alpha_claim(self) -> None:
        report = run_private_alpha_backend_readiness_audit(
            iterations=1,
            readiness_mode="local_dev",
            sample_runtime=lambda: {
                "status": "ok",
                "monitoring": {
                    "status": "healthy",
                    "rss_mb": 10.0,
                    "peak_rss_mb": 12.0,
                    "process": {"status": "healthy", "recent_start_count": 1},
                },
            },
            scenario_ids=["small_commercial_pad"],
            build_plan_fn=_fake_plan,
        )

        evidence = report["sections"]["monitoring"]["job_queue_monitoring_evidence"]
        self.assertEqual(report["readiness_mode"], "local_dev")
        self.assertEqual(evidence["applicability"], "unavailable_local")
        self.assertFalse(evidence["alpha_ready"])
        self.assertFalse(report["construction_release_allowed"])
        self.assertTrue(report["construction_release_blocked"])

    def test_production_blocks_snapshot_only_queue_evidence(self) -> None:
        report = run_private_alpha_backend_readiness_audit(
            iterations=1,
            readiness_mode="production",
            sample_runtime=_healthy_sample,
            scenario_ids=["small_commercial_pad"],
            build_plan_fn=_fake_plan,
        )

        self.assertFalse(report["success"])
        fields = {item["field"] for item in report["blockers"]}
        self.assertIn("monitoring_confidence", fields)
        self.assertFalse(report["construction_release_allowed"])
        self.assertTrue(report["construction_release_blocked"])

    def test_audit_writes_sanitized_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "private_alpha_backend_readiness.json"
            report = run_private_alpha_backend_readiness_audit(
                iterations=1,
                sample_runtime=_healthy_sample,
                scenario_ids=["small_commercial_pad"],
                build_plan_fn=_fake_plan,
                output_path=target,
            )
            written = json.loads(target.read_text(encoding="utf-8"))

        self.assertTrue(report["success"])
        self.assertEqual(written["version"], "private_alpha_backend_readiness_report_v1")
        text = json.dumps(written)
        self.assertNotIn("/Users/", text)
        self.assertNotIn("pk.secret-prefix", text)
        self.assertIn("<local_runtime_path>", text)
        self.assertIn("<redacted>", text)


if __name__ == "__main__":
    unittest.main()
