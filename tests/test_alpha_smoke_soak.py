import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

from backend.application.alpha_smoke_soak import fetch_runtime_debug_sample, run_alpha_smoke_soak


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


class _FakeRuntimeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


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
        self.assertTrue(report["aggregate_runtime_monitoring"]["job_queue_monitoring_evidence"]["alpha_ready"])
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
        self.assertIn("pending_count", fields)

    def test_smoke_soak_does_not_convert_missing_queue_counters_to_zero(self) -> None:
        report = run_alpha_smoke_soak(
            iterations=1,
            sample_runtime=lambda: {
                "status": "ok",
                "monitoring": {
                    "status": "healthy",
                    "rss_mb": 100.0,
                    "peak_rss_mb": 120.0,
                    "job_queue": {
                        "status": "healthy",
                        "monitored_job_types": ["orchestrate"],
                    },
                    "process": {
                        "status": "healthy",
                        "recent_start_count": 1,
                        "previous_shutdown_clean": True,
                    },
                },
            },
        )

        evidence = report["aggregate_runtime_monitoring"]["job_queue_monitoring_evidence"]
        self.assertFalse(report["success"])
        self.assertIsNone(evidence["pending_count"])
        self.assertIsNone(evidence["failed_count"])
        self.assertIsNone(evidence["timeout_count"])
        fields = {item["field"] for item in report["alpha_monitoring_report"]["blockers"]}
        self.assertIn("pending_count", fields)
        self.assertIn("failed_count", fields)
        self.assertIn("timeout_count", fields)

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

    def test_authenticated_runtime_sampler_sends_bearer_and_accepts_queue_counts(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout=0):
            captured["authorization"] = request.headers.get("Authorization")
            captured["timeout"] = timeout
            return _FakeRuntimeResponse(_healthy_sample())

        with patch("backend.application.alpha_smoke_soak.urlopen", side_effect=fake_urlopen):
            report = run_alpha_smoke_soak(
                iterations=1,
                base_url="http://runtime.local",
                runtime_bearer_token="runtime-token",
            )

        self.assertEqual(captured["authorization"], "Bearer runtime-token")
        self.assertTrue(report["success"])
        evidence = report["aggregate_runtime_monitoring"]["job_queue_monitoring_evidence"]
        self.assertTrue(evidence["alpha_ready"])
        self.assertEqual(evidence["pending_count"], 0)
        self.assertEqual(evidence["failed_count"], 0)
        self.assertEqual(evidence["timeout_count"], 0)

    def test_runtime_sampler_without_token_blocks_with_auth_missing(self) -> None:
        with patch.dict("os.environ", {"CIVORA_READINESS_AUDIT_BEARER_TOKEN": "", "CIVORA_RUNTIME_DEBUG_BEARER_TOKEN": ""}, clear=False):
            with patch("backend.application.alpha_smoke_soak.urlopen") as mocked_urlopen:
                report = run_alpha_smoke_soak(iterations=1, base_url="http://runtime.local")

        mocked_urlopen.assert_not_called()
        self.assertFalse(report["success"])
        self.assertEqual(report["sample_count"], 0)
        fields = {item["field"] for item in report["alpha_monitoring_report"]["blockers"]}
        self.assertIn("auth_missing", fields)
        self.assertIn("sample_failures", fields)
        evidence = report["aggregate_runtime_monitoring"]["job_queue_monitoring_evidence"]
        self.assertFalse(evidence["queue_system_present"])
        self.assertIsNone(evidence["pending_count"])

    def test_runtime_sampler_wrong_token_blocks_without_queue_counts(self) -> None:
        unauthorized = HTTPError(
            "http://runtime.local/api/debug/runtime",
            401,
            "Unauthorized",
            hdrs=None,
            fp=BytesIO(b'{"detail":"Authentication required."}'),
        )
        with patch("backend.application.alpha_smoke_soak.urlopen", side_effect=unauthorized):
            report = run_alpha_smoke_soak(
                iterations=1,
                base_url="http://runtime.local",
                runtime_bearer_token="wrong-token",
            )

        self.assertFalse(report["success"])
        fields = {item["field"] for item in report["alpha_monitoring_report"]["blockers"]}
        self.assertIn("runtime_auth_unauthorized", fields)
        evidence = report["aggregate_runtime_monitoring"]["job_queue_monitoring_evidence"]
        self.assertFalse(evidence["queue_system_present"])
        self.assertIsNone(evidence["pending_count"])

    def test_fetch_runtime_debug_sample_uses_env_token_without_exposing_value(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout=0):
            captured["authorization"] = request.headers.get("Authorization")
            return _FakeRuntimeResponse(_healthy_sample())

        with patch.dict("os.environ", {"CIVORA_READINESS_AUDIT_BEARER_TOKEN": "env-runtime-token"}):
            with patch("backend.application.alpha_smoke_soak.urlopen", side_effect=fake_urlopen):
                sample = fetch_runtime_debug_sample("http://runtime.local")

        self.assertEqual(captured["authorization"], "Bearer env-runtime-token")
        self.assertEqual(sample["monitoring"]["job_queue"]["queued_count"], 0)

    def test_fetch_runtime_debug_sample_rejects_non_http_urls(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute HTTP"):
            fetch_runtime_debug_sample("file:///etc/passwd", bearer_token="test-token")

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
