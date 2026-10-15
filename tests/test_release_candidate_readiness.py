from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import patch
import backend.scripts.run_rc1_readiness as readiness_cli
import backend.scripts.run_rc1_verification as verification_cli

from backend.application.release_candidate_readiness import (
    TECHNICAL_EVIDENCE_KEYS,
    build_rc1_readiness_report,
)
from backend.scripts.run_rc1_verification import _firefox_ci_evidence, _section_commands


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


def _hosted_operational_report(revision: str = "rc1-test"):
    return {
        "success": True,
        "status": "ready",
        "expected_revision": revision,
        "hosted_revision": revision,
        "revision_matches": True,
        "checks": {
            "support_contact_configured": True,
            "bug_report_configured": True,
            "escalation_owner_configured": True,
            "monitoring_owner_configured": True,
            "rollback_owner_configured": True,
            "provider_backups_enabled": True,
            "backup_owner_configured": True,
            "backup_evidence_url_configured": True,
            "restore_drill_at": "2026-08-08T12:00:00Z",
            "backup_retention_days": 30,
        },
    }


class ReleaseCandidateReadinessTests(unittest.TestCase):
    def test_hosted_backup_requires_valid_recent_time_and_retention(self) -> None:
        for field, value in [
            ("restore_drill_at", "false"), ("restore_drill_at", "2099-01-01T00:00:00Z"),
            ("restore_drill_at", "2020-01-01T00:00:00Z"), ("restore_drill_at", "2026-08-08T12:00:00"),
            ("restore_drill_at", None), ("backup_retention_days", 0),
            ("backup_retention_days", 6), ("backup_retention_days", True), ("backup_retention_days", "30"),
        ]:
            with self.subTest(field=field, value=value):
                hosted = _hosted_operational_report()
                hosted["checks"][field] = value
                report = build_rc1_readiness_report(evidence_manifest=_technical_manifest(), hosted_operational_evidence=hosted, env={})
                self.assertFalse(report["hosted_operational_evidence"]["backup_accepted"])
                self.assertIn("hosted_backup_restore_not_proven", {item["code"] for item in report["operational_blockers"]})

    def test_non_boolean_success_cannot_approve_technical_evidence(self) -> None:
        for value in ["false", "true", 1, [], {}, None]:
            with self.subTest(value=value):
                manifest = _technical_manifest()
                manifest["evidence"]["backend_regression"]["success"] = value
                report = build_rc1_readiness_report(evidence_manifest=manifest, env=_controlled_release_env())
                self.assertFalse(report["technical_rc_ready"])

    def test_hosted_flags_require_actual_boolean_true(self) -> None:
        for field in ["success", "revision_matches"]:
            for value in ["false", "true", 1, None]:
                with self.subTest(field=field, value=value):
                    hosted = _hosted_operational_report()
                    hosted[field] = value
                    report = build_rc1_readiness_report(evidence_manifest=_technical_manifest(), hosted_operational_evidence=hosted, env={})
                    self.assertFalse(report["hosted_operational_evidence"]["accepted"])

    def test_hosted_configuration_cannot_accept_string_false(self) -> None:
        hosted = _hosted_operational_report()
        hosted["checks"]["support_contact_configured"] = "false"
        hosted["checks"]["provider_backups_enabled"] = "false"
        report = build_rc1_readiness_report(evidence_manifest=_technical_manifest(), hosted_operational_evidence=hosted, env={})
        self.assertFalse(report["operational_checks"]["support_contact"])
        self.assertFalse(report["hosted_operational_evidence"]["backup_accepted"])

    def test_readiness_and_verification_cli_mark_dirty_source(self) -> None:
        for module in [readiness_cli, verification_cli]:
            with self.subTest(module=module.__name__):
                with patch.object(module.subprocess, "check_output", side_effect=["a" * 40, " M planner.py"]):
                    self.assertEqual(module._revision(), "a" * 40 + "-dirty")

    def test_technical_manifest_cannot_approve_a_different_report_revision(self) -> None:
        report = build_rc1_readiness_report(evidence_manifest=_technical_manifest(), revision="new-release", env=_controlled_release_env())
        self.assertFalse(report["technical_rc_ready"])
        self.assertIn("technical_evidence_revision_mismatch", {item["code"] for item in report["technical_blockers"]})

    def test_individual_stale_evidence_cannot_hide_under_a_current_manifest(self) -> None:
        manifest = _technical_manifest()
        manifest["evidence"]["backend_regression"]["revision"] = "old-release"
        report = build_rc1_readiness_report(evidence_manifest=manifest, env=_controlled_release_env())
        self.assertFalse(report["technical_rc_ready"])
        self.assertIn("backend_regression_revision_mismatch", {item["code"] for item in report["technical_blockers"]})

    def test_dirty_checkpoint_cannot_approve_release(self) -> None:
        manifest = _technical_manifest()
        manifest["revision"] = "a" * 40 + "-dirty"
        report = build_rc1_readiness_report(evidence_manifest=manifest, env=_controlled_release_env())
        self.assertFalse(report["controlled_invite_only_release_allowed"])

    def test_hosted_prefix_or_incorrect_actual_identity_is_not_exact_evidence(self) -> None:
        for expected, actual in [("rc1-test-extended", "rc1-test-extended"), ("rc1-test", "old-release")]:
            with self.subTest(expected=expected, actual=actual):
                hosted = _hosted_operational_report(expected)
                hosted["hosted_revision"] = actual
                report = build_rc1_readiness_report(evidence_manifest=_technical_manifest(), hosted_operational_evidence=hosted, env={})
                self.assertFalse(report["hosted_operational_evidence"]["accepted"])

    def test_security_evidence_includes_static_python_analysis(self) -> None:
        commands = _section_commands(skip_install=True, hosted_base_url="")["security_dependency"]

        command_tokens = [tuple(command) for command, _cwd in commands]
        self.assertTrue(
            any(tokens[1:] == ("-m", "bandit", "-r", "backend", "scripts", "-ll") for tokens in command_tokens)
        )

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

    def test_exact_revision_hosted_evidence_clears_machine_observable_operations(self) -> None:
        report = build_rc1_readiness_report(
            evidence_manifest=_technical_manifest(),
            hosted_operational_evidence=_hosted_operational_report(),
            env={},
        )

        self.assertTrue(report["technical_rc_ready"])
        self.assertFalse(report["operational_blockers"])
        self.assertTrue(report["hosted_operational_evidence"]["accepted"])
        self.assertEqual(report["operational_evidence_sources"]["monitoring_owner"], "hosted_exact_revision")
        self.assertFalse(report["controlled_invite_only_release_allowed"])
        self.assertTrue(report["human_blockers"])

    def test_stale_hosted_evidence_does_not_clear_operations(self) -> None:
        report = build_rc1_readiness_report(
            evidence_manifest=_technical_manifest(),
            hosted_operational_evidence=_hosted_operational_report("older-revision"),
            env={},
        )

        self.assertFalse(report["hosted_operational_evidence"]["accepted"])
        self.assertTrue(report["operational_blockers"])

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
