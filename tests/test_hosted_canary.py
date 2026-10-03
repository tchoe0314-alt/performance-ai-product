from __future__ import annotations

import unittest
from unittest.mock import patch
import json

from backend.application.hosted_canary import build_hosted_canary_report
from backend.scripts.run_hosted_canary import _safe_origin, _capture


def _health() -> dict:
    return {
        "success": True,
        "product_mode": "private_alpha",
        "storage": "postgres",
        "storage_pool": {"status": "available", "requests_errors": 0},
        "deployment": {
            "commit_sha": "abcdef123456",
            "backend_status": "online",
            "api_status": "configured",
        },
        "support": {"support_contact_configured": True, "bug_report_configured": True},
        "recovery": {"status": "ready", "provider_backups_enabled": True},
        "operational_summary": {"ready_for_ui": True},
    }


def _runtime() -> dict:
    return {
        "status": "ok",
        "storage_kind": "postgres",
        "monitoring": {"process": {"previous_shutdown_clean": True}},
        "job_queue": {
            "monitoring": {
                "status": "healthy",
                "queued_count": 0,
                "running_count": 0,
                "failed_recent_count": 0,
                "stale_job_count": 0,
            }
        },
        "alpha_monitoring_report": {"job_queue_monitoring_evidence": {"status": "ready"}},
        "recovery": {
            "status": "ready",
            "provider_backups_enabled": True,
            "owner_configured": True,
            "evidence_url_configured": True,
            "restore_drill_at": "2026-08-08T12:00:00Z",
            "retention_days": 30,
        },
        "operations": {
            "escalation_owner_configured": True,
            "monitoring_owner_configured": True,
            "rollback_owner_configured": True,
        },
    }


def _report(**overrides):
    values = {
        "frontend_url": "https://civora.example",
        "api_base_url": "https://api.civora.example",
        "expected_revision": "abcdef1234567890",
        "expected_product_mode": "private_alpha",
        "frontend": {"status": 200, "body_has_civora": True, "revision": "abcdef1234567890"},
        "health": _health(),
        "auth_status": {"success": True, "auth_enabled": True},
        "cors": {"status": 200, "allow_origin": "https://civora.example"},
        "unauthenticated_runtime_status": 401,
        "unauthenticated_production_env_status": 401,
    }
    values.update(overrides)
    return build_hosted_canary_report(**values)


class HostedCanaryTests(unittest.TestCase):
    def test_missing_or_html_identity_preserves_other_public_checks(self) -> None:
        for status, body in ((404, b"missing"), (200, b"<html>fallback</html>")):
            captures = [
                (200, {}, b"Civora", 1),
                (status, {}, body, 1),
                (200, {}, json.dumps(_health()).encode(), 1),
                (200, {}, b'{"success":true,"auth_enabled":true}', 1),
                (401, {}, b"{}", 1),
                (401, {}, b"{}", 1),
                (200, {"access-control-allow-origin": "https://civora.example"}, b"", 1),
            ]
            with patch.dict("os.environ", {"CIVORA_CANARY_EMAIL": "", "CIVORA_CANARY_PASSWORD": ""}), \
                 patch("backend.scripts.run_hosted_canary._request", side_effect=captures):
                report = _capture(frontend_url="https://civora.example", api_base_url="https://api.civora.example",
                                  expected_revision="abcdef1234567890", expected_product_mode="private_alpha",
                                  timeout=1, require_authenticated=False)
            self.assertTrue(report["checks"]["health_success"])
            self.assertFalse(report["success"])
            self.assertEqual(report["frontend_revision"], "")
            self.assertIn("frontend_revision_mismatch", {item["code"] for item in report["public_blockers"]})

    def test_remote_canary_origins_require_https_without_paths_or_credentials(self) -> None:
        self.assertEqual(_safe_origin("https://civora.example/", label="Frontend"), "https://civora.example")
        for invalid in (
            "http://civora.example",
            "https://user:secret@civora.example",
            "https://civora.example/workspace",
        ):
            with self.assertRaises(ValueError):
                _safe_origin(invalid, label="Frontend")

    def test_public_canary_can_pass_without_mutating_or_authenticating(self) -> None:
        report = _report()

        self.assertTrue(report["success"])
        self.assertTrue(report["public_checks_ready"])
        self.assertEqual(report["authenticated_checks_status"], "not_configured")
        self.assertFalse(report["construction_ready"])
        self.assertFalse(report["public_beta_allowed"])

    def test_revision_and_cors_mismatch_are_blocking(self) -> None:
        report = _report(
            expected_revision="999999999999",
            cors={"status": 200, "allow_origin": "https://wrong.example"},
        )

        self.assertFalse(report["success"])
        codes = {item["code"] for item in report["public_blockers"]}
        self.assertIn("hosted_revision_mismatch", codes)
        self.assertIn("cors_not_ready", codes)

    def test_required_authenticated_canary_does_not_pass_without_evidence(self) -> None:
        report = _report(require_authenticated=True)

        self.assertFalse(report["success"])
        self.assertEqual(report["authenticated_checks_status"], "blocked")
        self.assertIn("authenticated_canary_missing", {item["code"] for item in report["authenticated_blockers"]})

    def test_matching_backend_cannot_certify_an_old_or_unknown_website(self) -> None:
        for revision in ("", "9999999999999999"):
            report = _report(frontend={"status": 200, "body_has_civora": True, "revision": revision})
            self.assertFalse(report["success"])
            self.assertFalse(report["frontend_revision_matches"])
            self.assertIn("frontend_revision_mismatch", {item["code"] for item in report["public_blockers"]})

    def test_authenticated_runtime_and_operational_evidence_can_pass(self) -> None:
        report = _report(authenticated_runtime=_runtime(), require_authenticated=True)

        self.assertTrue(report["success"])
        self.assertEqual(report["authenticated_checks_status"], "ready")
        self.assertTrue(report["authenticated_evidence"]["hosted_runtime_ready"])
        self.assertTrue(report["authenticated_evidence"]["operational_configuration_ready"])

    def test_authenticated_queue_failure_is_not_hidden(self) -> None:
        runtime = _runtime()
        runtime["job_queue"]["monitoring"]["failed_recent_count"] = 1
        report = _report(authenticated_runtime=runtime)

        self.assertFalse(report["success"])
        self.assertIn("queue_recent_failures", {item["code"] for item in report["authenticated_blockers"]})


if __name__ == "__main__":
    unittest.main()
