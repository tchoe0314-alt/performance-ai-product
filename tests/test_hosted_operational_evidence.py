from __future__ import annotations

import unittest

from backend.application.hosted_operational_evidence import build_hosted_operational_evidence
from backend.application.release_rollback_rehearsal import build_code_rollback_rehearsal_report


def _health() -> dict:
    return {
        "success": True,
        "storage": "postgres",
        "deployment": {"commit_sha": "abcdef123456"},
        "support": {"support_contact_configured": True, "bug_report_configured": True},
        "recovery": {"status": "ready", "provider_backups_enabled": True},
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


class HostedOperationalEvidenceTests(unittest.TestCase):
    def test_exact_revision_healthy_runtime_and_recovery_are_ready(self) -> None:
        report = build_hosted_operational_evidence(
            health=_health(),
            runtime=_runtime(),
            expected_revision="abcdef1234567890",
            base_url="https://api.example.test",
        )

        self.assertTrue(report["hosted_runtime_ready"])
        self.assertTrue(report["operational_configuration_ready"])
        self.assertTrue(report["success"])
        self.assertFalse(report["construction_ready"])

    def test_recent_queue_failure_and_missing_backup_stay_blocked(self) -> None:
        health = _health()
        health["support"]["bug_report_configured"] = False
        runtime = _runtime()
        runtime["job_queue"]["monitoring"]["failed_recent_count"] = 2
        runtime["recovery"] = {
            "status": "blocked",
            "provider_backups_enabled": False,
            "owner_configured": False,
            "evidence_url_configured": False,
        }

        report = build_hosted_operational_evidence(
            health=health,
            runtime=runtime,
            expected_revision="abcdef123456",
            base_url="https://api.example.test",
        )

        self.assertFalse(report["hosted_runtime_ready"])
        self.assertFalse(report["operational_configuration_ready"])
        self.assertIn("queue_recent_failures", {item["code"] for item in report["runtime_blockers"]})
        self.assertIn("provider_backup_restore_not_proven", {item["code"] for item in report["operational_blockers"]})

    def test_revision_mismatch_is_not_silently_accepted(self) -> None:
        report = build_hosted_operational_evidence(
            health=_health(),
            runtime=_runtime(),
            expected_revision="999999999999",
            base_url="https://api.example.test",
        )

        self.assertFalse(report["revision_matches"])
        self.assertIn("hosted_revision_mismatch", {item["code"] for item in report["runtime_blockers"]})

    def test_missing_operational_owners_remain_blocked(self) -> None:
        runtime = _runtime()
        runtime["operations"]["monitoring_owner_configured"] = False

        report = build_hosted_operational_evidence(
            health=_health(),
            runtime=runtime,
            expected_revision="abcdef123456",
            base_url="https://api.example.test",
        )

        self.assertFalse(report["operational_configuration_ready"])
        self.assertIn("monitoring_owner_missing", {item["code"] for item in report["operational_blockers"]})

    def test_code_rollback_rehearsal_does_not_claim_provider_rollback(self) -> None:
        report = build_code_rollback_rehearsal_report(
            current_revision="current123",
            candidate_revision="previous12",
            candidate_is_ancestor=True,
            candidate_retrieved=True,
            candidate_worktree_clean=True,
            critical_paths={"backend/api/app.py": True},
            verification_command="python -m pytest -q",
            verification_exit_code=0,
            verification_duration_seconds=1.25,
        )

        self.assertTrue(report["success"])
        self.assertFalse(report["provider_rollback_proven"])
        self.assertFalse(report["hosted_deployment_changed"])
        self.assertFalse(report["database_changed"])


if __name__ == "__main__":
    unittest.main()
