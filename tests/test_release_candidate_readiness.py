from __future__ import annotations

from datetime import datetime, timezone
import unittest

from backend.application.release_candidate_readiness import (
    TECHNICAL_EVIDENCE_KEYS,
    build_rc1_readiness_report,
)
from backend.scripts.run_rc1_verification import _firefox_ci_evidence


def _technical_manifest(success: bool = True):
    return {
        "revision": "rc1-test",
        "evidence": {
            key: {"success": success, "command": f"verify {key}"}
            for key in TECHNICAL_EVIDENCE_KEYS
        },
    }


def _controlled_release_env():
    return {
        "CIVORA_PRODUCT_MODE": "private_alpha",
        "CIVORA_DEPLOYMENT_TARGET": "railway",
        "CORS_ALLOW_ORIGINS": "https://civoraai.com",
        "PERFORMANCE_AI_STORAGE_DIR": "/data",
        "CIVORA_AI_PROVIDER": "none",
        "CIVORA_SUPPORT_EMAIL": "support@example.com",
        "CIVORA_BUG_REPORT_URL": "https://example.com/bugs",
        "CIVORA_ESCALATION_CONTACT": "escalation-owner",
        "CIVORA_MONITORING_OWNER": "monitoring-owner",
        "CIVORA_ROLLBACK_OWNER": "rollback-owner",
        "CIVORA_DATABASE_PROVIDER_BACKUPS_ENABLED": "true",
        "CIVORA_DATABASE_BACKUP_OWNER": "backup-owner",
        "CIVORA_DATABASE_BACKUP_EVIDENCE_URL": "https://provider.example/backups/evidence",
        "CIVORA_DATABASE_RESTORE_DRILL_AT": datetime.now(timezone.utc).isoformat(),
        "CIVORA_DATABASE_BACKUP_RETENTION_DAYS": "30",
        "CIVORA_ENGINEER_UAT_EVIDENCE_URL": "https://evidence.example/uat/rc1",
        "CIVORA_ENGINEER_UAT_OWNER": "uat-owner",
        "CIVORA_PILOT_TERMS_READY": "true",
        "CIVORA_TERMS_PRIVACY_READY": "true",
        "CIVORA_DATA_RETENTION_POLICY_READY": "true",
    }


class ReleaseCandidateReadinessTests(unittest.TestCase):
    def test_missing_evidence_blocks_technical_rc(self) -> None:
        report = build_rc1_readiness_report(evidence_manifest={}, env={})

        self.assertFalse(report["technical_rc_ready"])
        self.assertEqual(len(report["technical_blockers"]), len(TECHNICAL_EVIDENCE_KEYS))
        self.assertFalse(report["controlled_invite_only_release_allowed"])
        self.assertFalse(report["construction_ready"])

    def test_technical_proof_does_not_self_approve_human_or_operational_gates(self) -> None:
        report = build_rc1_readiness_report(evidence_manifest=_technical_manifest(), env={})

        self.assertTrue(report["technical_rc_ready"])
        self.assertFalse(report["controlled_invite_only_release_allowed"])
        self.assertTrue(report["operational_blockers"])
        self.assertIn("engineer_uat_not_accepted", {item["code"] for item in report["human_blockers"]})

    def test_controlled_release_can_clear_with_full_recorded_evidence(self) -> None:
        report = build_rc1_readiness_report(
            evidence_manifest=_technical_manifest(),
            env=_controlled_release_env(),
        )

        self.assertTrue(report["technical_rc_ready"])
        self.assertTrue(report["controlled_invite_only_release_allowed"])
        self.assertFalse(report["controlled_paid_release_allowed"])
        self.assertFalse(report["public_beta_allowed"])
        self.assertFalse(report["operational_blockers"])
        self.assertFalse(report["human_blockers"])

    def test_any_failed_technical_evidence_blocks_release(self) -> None:
        manifest = _technical_manifest()
        manifest["evidence"]["hosted_end_to_end"] = {"success": False, "message": "Hosted workflow failed."}
        report = build_rc1_readiness_report(
            evidence_manifest=manifest,
            env=_controlled_release_env(),
        )

        self.assertFalse(report["technical_rc_ready"])
        self.assertIn("hosted_end_to_end_failed", {item["code"] for item in report["technical_blockers"]})
        self.assertFalse(report["controlled_invite_only_release_allowed"])

    def test_firefox_ci_evidence_requires_https_success_and_exact_revision(self) -> None:
        revision = "abc123"
        ready = _firefox_ci_evidence(
            env={
                "CIVORA_FIREFOX_CI_EVIDENCE_URL": "https://github.com/example/repo/actions/runs/123",
                "CIVORA_FIREFOX_CI_REVISION": revision,
                "CIVORA_FIREFOX_CI_STATUS": "success",
            },
            revision=revision,
        )
        stale = _firefox_ci_evidence(
            env={
                "CIVORA_FIREFOX_CI_EVIDENCE_URL": "https://github.com/example/repo/actions/runs/122",
                "CIVORA_FIREFOX_CI_REVISION": "older",
                "CIVORA_FIREFOX_CI_STATUS": "success",
            },
            revision=revision,
        )
        insecure = _firefox_ci_evidence(
            env={
                "CIVORA_FIREFOX_CI_EVIDENCE_URL": "http://localhost/fake",
                "CIVORA_FIREFOX_CI_REVISION": revision,
                "CIVORA_FIREFOX_CI_STATUS": "success",
            },
            revision=revision,
        )

        self.assertTrue(ready["success"])
        self.assertFalse(stale["success"])
        self.assertFalse(insecure["success"])


if __name__ == "__main__":
    unittest.main()
