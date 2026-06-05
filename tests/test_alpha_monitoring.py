import unittest

from backend.planning.alpha_monitoring import build_alpha_monitoring_report


def _healthy_runtime() -> dict:
    return {
        "status": "healthy",
        "rss_mb": 128.0,
        "peak_rss_mb": 180.0,
        "job_queue": {
            "status": "healthy",
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

    def test_partial_runtime_snapshot_is_blocked(self) -> None:
        report = build_alpha_monitoring_report({"status": "healthy", "rss_mb": 128.0, "peak_rss_mb": 180.0})

        self.assertEqual(report["readiness"], "blocked")
        fields = {item["field"] for item in report["blockers"]}
        self.assertIn("job_queue", fields)
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
