import unittest

from backend.planning.alpha_monitoring import build_alpha_monitoring_report, build_job_queue_monitoring_evidence


def _healthy_runtime() -> dict:
    return {
        "status": "healthy",
        "rss_mb": 128.0,
        "peak_rss_mb": 180.0,
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
        },
        "warnings": [],
    }


class AlphaMonitoringTests(unittest.TestCase):
    def test_healthy_runtime_passes_alpha_thresholds(self) -> None:
        report = build_alpha_monitoring_report(
            _healthy_runtime(),
            thresholds={"max_rss_mb": 256, "max_peak_rss_mb": 512, "max_recent_start_count": 2},
        )

        self.assertEqual(report["readiness"], "ready")
        self.assertEqual(report["status"], "healthy")
        self.assertTrue(report["success"])
        self.assertFalse(report["blockers"])
        evidence = report["job_queue_monitoring_evidence"]
        self.assertEqual(evidence["version"], "job_queue_monitoring_evidence_v1")
        self.assertTrue(evidence["queue_system_present"])
        self.assertEqual(evidence["monitored_job_types"], ["orchestrate", "drainage_only"])
        self.assertEqual(evidence["pending_count"], 0)
        self.assertEqual(evidence["failed_count"], 0)
        self.assertEqual(evidence["timeout_count"], 0)
        self.assertTrue(evidence["alpha_ready"])

    def test_job_queue_evidence_blocks_when_queue_missing(self) -> None:
        evidence = build_job_queue_monitoring_evidence({})

        self.assertEqual(evidence["version"], "job_queue_monitoring_evidence_v1")
        self.assertEqual(evidence["readiness_mode"], "private_alpha_review")
        self.assertFalse(evidence["queue_system_present"])
        self.assertFalse(evidence["alpha_ready"])
        fields = {item["field"] for item in evidence["blockers"]}
        self.assertIn("job_queue", fields)
        self.assertIn("pending_count", fields)

    def test_local_dev_queue_unavailable_is_truthful_not_alpha_ready(self) -> None:
        runtime = {
            "status": "healthy",
            "rss_mb": 128.0,
            "peak_rss_mb": 180.0,
            "process": {"status": "healthy", "recent_start_count": 1},
        }

        report = build_alpha_monitoring_report(runtime, readiness_mode="local_dev")
        evidence = report["job_queue_monitoring_evidence"]

        self.assertEqual(report["readiness_mode"], "local_dev")
        self.assertEqual(report["readiness"], "ready")
        self.assertEqual(evidence["status"], "unavailable_local")
        self.assertEqual(evidence["applicability"], "unavailable_local")
        self.assertFalse(evidence["queue_system_present"])
        self.assertFalse(evidence["alpha_ready"])
        self.assertIn("live job queue", evidence["not_applicable_reason"])

    def test_private_alpha_missing_queue_evidence_blocks(self) -> None:
        report = build_alpha_monitoring_report(
            {
                "status": "healthy",
                "rss_mb": 128.0,
                "peak_rss_mb": 180.0,
                "process": {"status": "healthy", "recent_start_count": 1},
            },
            readiness_mode="private_alpha_review",
        )

        self.assertEqual(report["readiness"], "blocked")
        fields = {item["field"] for item in report["blockers"]}
        self.assertIn("job_queue", fields)
        self.assertIn("pending_count", fields)

    def test_private_alpha_real_queue_evidence_clears_queue_blocker(self) -> None:
        report = build_alpha_monitoring_report(_healthy_runtime(), readiness_mode="private_alpha_review")

        self.assertEqual(report["readiness"], "ready")
        evidence = report["job_queue_monitoring_evidence"]
        self.assertTrue(evidence["alpha_ready"])
        self.assertFalse([item for item in report["blockers"] if item["field"] in {"job_queue", "pending_count"}])

    def test_production_requires_live_queue_monitoring_confidence(self) -> None:
        report = build_alpha_monitoring_report(_healthy_runtime(), readiness_mode="production")

        self.assertEqual(report["readiness"], "blocked")
        fields = {item["field"] for item in report["blockers"]}
        self.assertIn("monitoring_confidence", fields)
        self.assertFalse(report["construction_release_allowed"])
        self.assertTrue(report["construction_release_blocked"])

    def test_partial_runtime_snapshot_is_blocked(self) -> None:
        report = build_alpha_monitoring_report({"status": "healthy", "rss_mb": 128.0, "peak_rss_mb": 180.0})

        self.assertEqual(report["readiness"], "blocked")
        fields = {item["field"] for item in report["blockers"]}
        self.assertIn("job_queue", fields)
        self.assertIn("pending_count", fields)
        self.assertIn("process", fields)

    def test_memory_and_queue_thresholds_block_alpha_monitoring(self) -> None:
        runtime = _healthy_runtime()
        runtime["rss_mb"] = 900.0
        runtime["job_queue"]["stale_job_count"] = 1

        report = build_alpha_monitoring_report(runtime, thresholds={"max_rss_mb": 512, "max_stale_job_count": 0})

        self.assertEqual(report["readiness"], "blocked")
        fields = {item["field"] for item in report["blockers"]}
        self.assertIn("rss_mb", fields)
        self.assertIn("stale_job_count", fields)
        self.assertTrue(report["blocker_details"])

    def test_restart_threshold_blocks_alpha_monitoring(self) -> None:
        runtime = _healthy_runtime()
        runtime["process"]["recent_start_count"] = 4

        report = build_alpha_monitoring_report(runtime, thresholds={"max_recent_start_count": 2})

        self.assertEqual(report["readiness"], "blocked")
        fields = {item["field"] for item in report["blockers"]}
        self.assertIn("recent_start_count", fields)


if __name__ == "__main__":
    unittest.main()
