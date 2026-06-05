import json
import tempfile
import unittest
from pathlib import Path

from backend.application.alpha_smoke_soak import run_alpha_smoke_soak


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


class AlphaSmokeSoakTests(unittest.TestCase):
    def test_smoke_soak_ready_with_full_runtime_evidence(self) -> None:
        report = run_alpha_smoke_soak(
            iterations=2,
            sample_runtime=_healthy_sample,
            thresholds={"max_rss_mb": 256, "max_peak_rss_mb": 512},
        )

        self.assertTrue(report["success"])
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["sample_count"], 2)
        self.assertEqual(report["alpha_monitoring_report"]["readiness"], "ready")
        self.assertEqual(report["aggregate_runtime_monitoring"]["job_queue"]["sample_count"], 2)
        self.assertIn("does not make Civora construction-ready", report["truth_label"])

    def test_smoke_soak_blocks_without_queue_evidence(self) -> None:
        report = run_alpha_smoke_soak(
            iterations=1,
            sample_runtime=lambda: {
                "status": "ok",
                "monitoring": {
                    "status": "healthy",
                    "rss_mb": 100.0,
                    "peak_rss_mb": 120.0,
                    "process": {"status": "healthy", "recent_start_count": 1},
                },
            },
        )

        self.assertFalse(report["success"])
        fields = {item["field"] for item in report["alpha_monitoring_report"]["blockers"]}
        self.assertIn("job_queue", fields)

    def test_smoke_soak_blocks_sample_failures(self) -> None:
        calls = {"count": 0}

        def flaky_sample() -> dict:
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("sample failed")
            return _healthy_sample()

        report = run_alpha_smoke_soak(iterations=3, sample_runtime=flaky_sample)

        self.assertFalse(report["success"])
        self.assertEqual(report["sample_failure_count"], 1)
        fields = {item["field"] for item in report["alpha_monitoring_report"]["blockers"]}
        self.assertIn("sample_failures", fields)

    def test_smoke_soak_writes_report_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "alpha_report.json"
            report = run_alpha_smoke_soak(iterations=1, sample_runtime=_healthy_sample, output_path=target)
            written = json.loads(target.read_text(encoding="utf-8"))

        self.assertTrue(report["success"])
        self.assertTrue(written["success"])
        self.assertEqual(written["version"], "alpha_smoke_soak_report_v1")
        report_text = json.dumps(written)
        self.assertNotIn("/Users/", report_text)
        self.assertNotIn("pk.secret-prefix", report_text)
        self.assertIn("<local_runtime_path>", report_text)
        self.assertIn("<redacted>", report_text)


if __name__ == "__main__":
    unittest.main()
