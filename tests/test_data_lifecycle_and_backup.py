from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from backend.services.auth_store import AuthStore
from backend.services.backup_restore import DatabaseBackupService, hosted_backup_evidence
from backend.services.data_lifecycle import (
    ACCOUNT_DELETE_CONFIRMATION,
    DataLifecycleService,
    cleanup_deletion_quarantine,
)
from backend.services.database import Database
from backend.services.project_store import ProjectStore
from backend.services.support_store import SupportStore


class DataLifecycleAndBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.storage = self.root / "storage"
        self.uploads = self.storage / "uploads"
        self.artifacts = self.storage / "artifacts"
        self.uploads.mkdir(parents=True)
        self.artifacts.mkdir(parents=True)
        self.learning = self.storage / "chat_learning.jsonl"
        self.db = Database(self.storage / "performance_ai.db")
        self.auth = AuthStore(self.db)
        self.projects = ProjectStore(self.db)
        self.support = SupportStore(self.db)
        registration = self.auth.register_user(
            email="owner@example.com",
            password="password123",
            name="Owner",
        )
        self.user = registration["user"]
        self.token = registration["token"]
        self.lifecycle = DataLifecycleService(
            self.db,
            storage_dir=self.storage,
            upload_dir=self.uploads,
            artifact_dir=self.artifacts,
            learning_paths=(self.learning,),
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _create_project(self) -> dict:
        return self.projects.save_project(
            user_id=self.user["user_id"],
            project_id=None,
            name="RC1 commercial site",
            project_input={"address": "20525 Margo St", "meta": {"site_inputs": {"lot_width": 1000}}},
            latest_result={"success": True, "metadata": {"review_required": True}},
            session_state={"active_panel": "draw"},
            metadata={"source": "data_lifecycle_test"},
        )

    def test_support_request_is_persistent_and_redacts_secrets(self) -> None:
        project = self._create_project()
        record = self.support.create_request(
            user_id=self.user["user_id"],
            project_id=project["project_id"],
            category="workflow",
            severity="p1",
            summary="Generate did not finish",
            details="The visible status stayed on Working.",
            client_context={
                "url": "https://civoraai.com/demo/workspace?access_token=do-not-store-url#secret",
                "authorization": "Bearer do-not-store",
                "nested": {
                    "api_token": "secret",
                    "browser": "chromium",
                    "message": "Authorization failed with Bearer do-not-store-value",
                },
            },
        )

        self.assertEqual(record["status"], "received")
        self.assertEqual(record["client_context"]["authorization"], "[redacted]")
        self.assertEqual(record["client_context"]["nested"]["api_token"], "[redacted]")
        self.assertEqual(record["client_context"]["url"], "https://civoraai.com/demo/workspace")
        self.assertEqual(
            record["client_context"]["nested"]["message"],
            "Authorization failed with Bearer [redacted]",
        )
        saved = self.support.list_requests(user_id=self.user["user_id"])
        self.assertEqual(saved[0]["request_id"], record["request_id"])
        self.assertNotIn("do-not-store", json.dumps(saved))

        operations = self.support.list_for_operations(status="received", severity="p1")
        self.assertEqual(operations[0]["request_id"], record["request_id"])
        updated = self.support.update_status(request_id=record["request_id"], status="triaged")
        self.assertEqual(updated["status"], "triaged")

    def test_account_export_contains_owned_data_and_files_but_no_auth_secrets(self) -> None:
        project = self._create_project()
        upload = self.uploads / f"{self.user['user_id']}_survey.csv"
        upload.write_text("x,y,z\n0,0,100\n", encoding="utf-8")
        artifact_dir = self.artifacts / self.user["user_id"]
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "review.pdf").write_bytes(b"review artifact")
        cache_dir = self.artifacts / "_preview_cache" / project["project_id"]
        cache_dir.mkdir(parents=True)
        (cache_dir / "preview.png").write_bytes(b"preview")
        self.learning.write_text(
            "\n".join(
                (
                    json.dumps({"user_id": self.user["user_id"], "message": "mine"}),
                    json.dumps({"user_id": "other", "message": "not mine"}),
                )
            )
            + "\n",
            encoding="utf-8",
        )

        package = self.lifecycle.account_export(user_id=self.user["user_id"])

        self.assertTrue(package["secrets_excluded"])
        self.assertEqual(package["data"]["account"]["email"], "owner@example.com")
        self.assertEqual(package["data"]["owned_projects"][0]["project_id"], project["project_id"])
        self.assertEqual(len(package["data"]["chat_learning_records"]), 1)
        self.assertEqual(len(package["data"]["file_manifest"]), 3)
        serialized = json.dumps(package)
        self.assertNotIn("password_hash", serialized)
        self.assertNotIn("password_salt", serialized)
        self.assertNotIn(self.token, serialized)

        archive = self.lifecycle.create_account_export_archive(user_id=self.user["user_id"])
        with zipfile.ZipFile(archive["path"], "r") as bundle:
            names = set(bundle.namelist())
            self.assertIn("account-data.json", names)
            self.assertTrue(any(name.endswith("survey.csv") for name in names))
            self.assertTrue(any(name.endswith("review.pdf") for name in names))
            archived_package = json.loads(bundle.read("account-data.json"))
            self.assertEqual(archived_package["content_sha256"], package["content_sha256"])

    def test_account_deletion_blocks_shared_ownership(self) -> None:
        project = self._create_project()
        collaborator = self.auth.register_user(
            email="collaborator@example.com",
            password="password123",
            name="Collaborator",
        )["user"]
        self.projects.invite_project_member(
            actor_user_id=self.user["user_id"],
            project_id=project["project_id"],
            email=collaborator["email"],
            role="editor",
        )

        readiness = self.lifecycle.deletion_readiness(user_id=self.user["user_id"])

        self.assertFalse(readiness["ready"])
        self.assertIn("owned_projects_have_collaborators", {item["code"] for item in readiness["blockers"]})
        with self.assertRaisesRegex(ValueError, "ownership issues"):
            self.lifecycle.delete_account(
                user_id=self.user["user_id"],
                confirmation=ACCOUNT_DELETE_CONFIRMATION,
            )
        self.assertIsNotNone(self.auth.authenticate_token(self.token))

    def test_account_deletion_revokes_auth_removes_data_files_and_learning_records(self) -> None:
        project = self._create_project()
        upload = self.uploads / f"{self.user['user_id']}_survey.csv"
        upload.write_text("x,y,z\n0,0,100\n", encoding="utf-8")
        artifact_dir = self.artifacts / self.user["user_id"]
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "report.json").write_text("{}", encoding="utf-8")
        cache_dir = self.artifacts / "_preview_cache" / project["project_id"]
        cache_dir.mkdir(parents=True)
        (cache_dir / "preview.png").write_bytes(b"preview")
        self.learning.write_text(
            json.dumps({"user_id": self.user["user_id"], "message": "remove"})
            + "\n"
            + json.dumps({"user_id": "other", "message": "keep"})
            + "\n",
            encoding="utf-8",
        )

        self.assertTrue(self.auth.verify_password(user_id=self.user["user_id"], password="password123"))
        result = self.lifecycle.delete_account(
            user_id=self.user["user_id"],
            confirmation=ACCOUNT_DELETE_CONFIRMATION,
        )

        self.assertTrue(result["account_deleted"])
        self.assertTrue(result["storage_cleanup_complete"])
        self.assertIsNone(self.auth.authenticate_token(self.token))
        self.assertFalse(upload.exists())
        self.assertFalse(artifact_dir.exists())
        self.assertFalse(cache_dir.exists())
        self.assertNotIn(self.user["user_id"], self.learning.read_text(encoding="utf-8"))
        self.assertIn("other", self.learning.read_text(encoding="utf-8"))
        connection = self.db.connect()
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)
        finally:
            connection.close()

    def test_account_deletion_reports_pending_file_cleanup_instead_of_false_success(self) -> None:
        self._create_project()
        artifact_dir = self.artifacts / self.user["user_id"]
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "report.json").write_text("{}", encoding="utf-8")

        with patch("backend.services.data_lifecycle.shutil.rmtree", return_value=None):
            result = self.lifecycle.delete_account(
                user_id=self.user["user_id"],
                confirmation=ACCOUNT_DELETE_CONFIRMATION,
            )

        self.assertTrue(result["account_deleted"])
        self.assertFalse(result["success"])
        self.assertFalse(result["storage_cleanup_complete"])
        self.assertTrue(result["storage_cleanup_pending"])
        self.assertIsNone(self.auth.authenticate_token(self.token))

    def test_partial_file_quarantine_failure_restores_every_staged_path(self) -> None:
        first = self.uploads / f"{self.user['user_id']}_first.csv"
        second = self.uploads / f"{self.user['user_id']}_second.csv"
        first.write_text("first", encoding="utf-8")
        second.write_text("second", encoding="utf-8")
        real_move = shutil.move

        def fail_second_source(source: str, destination: str) -> str:
            if Path(source) == second:
                raise OSError("simulated staging failure")
            return str(real_move(source, destination))

        with patch("backend.services.data_lifecycle.shutil.move", side_effect=fail_second_source):
            with self.assertRaisesRegex(OSError, "simulated staging failure"):
                self.lifecycle._quarantine_paths(
                    user_id=self.user["user_id"],
                    paths=(first, second),
                )

        self.assertEqual(first.read_text(encoding="utf-8"), "first")
        self.assertEqual(second.read_text(encoding="utf-8"), "second")
        self.assertEqual(list(self.lifecycle.quarantine_dir.iterdir()), [])

    def test_partial_learning_redaction_failure_restores_prior_logs(self) -> None:
        first = self.storage / "learning-one.jsonl"
        second = self.storage / "learning-two.jsonl"
        original_first = json.dumps({"user_id": self.user["user_id"], "message": "first"}) + "\n"
        original_second = json.dumps({"user_id": self.user["user_id"], "message": "second"}) + "\n"
        first.write_text(original_first, encoding="utf-8")
        second.write_text(original_second, encoding="utf-8")
        lifecycle = DataLifecycleService(
            self.db,
            storage_dir=self.storage,
            upload_dir=self.uploads,
            artifact_dir=self.artifacts,
            learning_paths=(first, second),
        )
        quarantine = lifecycle.quarantine_dir / "learning-failure-test"
        quarantine.mkdir()
        real_replace = os.replace
        replace_count = 0

        def fail_second_replace(source: object, destination: object) -> None:
            nonlocal replace_count
            replace_count += 1
            if replace_count == 2:
                raise OSError("simulated learning write failure")
            real_replace(source, destination)

        with patch("backend.services.data_lifecycle.os.replace", side_effect=fail_second_replace):
            with self.assertRaisesRegex(OSError, "simulated learning write failure"):
                lifecycle._stage_learning_log_redactions(
                    user_id=self.user["user_id"],
                    quarantine_root=quarantine,
                )

        self.assertEqual(first.read_text(encoding="utf-8"), original_first)
        self.assertEqual(second.read_text(encoding="utf-8"), original_second)
        self.assertEqual(replace_count, 2)
        self.assertEqual(
            [path for path in self.storage.iterdir() if path.name.startswith("tmp")],
            [],
        )

    def test_account_deletion_retries_learning_log_restore_after_inner_rollback_failure(self) -> None:
        self._create_project()
        first = self.storage / "learning-one.jsonl"
        second = self.storage / "learning-two.jsonl"
        original_first = json.dumps({"user_id": self.user["user_id"], "message": "first"}) + "\n"
        original_second = json.dumps({"user_id": self.user["user_id"], "message": "second"}) + "\n"
        first.write_text(original_first, encoding="utf-8")
        second.write_text(original_second, encoding="utf-8")
        lifecycle = DataLifecycleService(
            self.db,
            storage_dir=self.storage,
            upload_dir=self.uploads,
            artifact_dir=self.artifacts,
            learning_paths=(first, second),
        )
        real_replace = os.replace
        real_copy = shutil.copy2
        replace_count = 0
        copy_count = 0

        def fail_second_replace(source: object, destination: object) -> None:
            nonlocal replace_count
            replace_count += 1
            if replace_count == 2:
                raise OSError("simulated second learning write failure")
            real_replace(source, destination)

        def fail_first_inner_restore(source: object, destination: object) -> object:
            nonlocal copy_count
            copy_count += 1
            if copy_count == 3:
                raise OSError("simulated inner restore failure")
            return real_copy(source, destination)

        with patch("backend.services.data_lifecycle.os.replace", side_effect=fail_second_replace):
            with patch("backend.services.data_lifecycle.shutil.copy2", side_effect=fail_first_inner_restore):
                with self.assertRaisesRegex(RuntimeError, "operator recovery"):
                    lifecycle.delete_account(
                        user_id=self.user["user_id"],
                        confirmation=ACCOUNT_DELETE_CONFIRMATION,
                    )

        self.assertEqual(first.read_text(encoding="utf-8"), original_first)
        self.assertEqual(second.read_text(encoding="utf-8"), original_second)
        self.assertIsNotNone(self.auth.authenticate_token(self.token))

    def test_deletion_quarantine_cleanup_is_dry_run_first(self) -> None:
        quarantine = self.lifecycle.quarantine_dir / "account-old-quarantine"
        quarantine.mkdir()
        (quarantine / "artifact.json").write_text("{}", encoding="utf-8")

        dry_run = cleanup_deletion_quarantine(
            storage_dir=self.storage,
            older_than_hours=0,
        )

        self.assertTrue(dry_run["success"])
        self.assertTrue(dry_run["dry_run"])
        self.assertEqual(dry_run["candidate_count"], 1)
        self.assertTrue(quarantine.exists())

        confirmed = cleanup_deletion_quarantine(
            storage_dir=self.storage,
            older_than_hours=0,
            confirm=True,
        )
        self.assertTrue(confirmed["success"])
        self.assertFalse(confirmed["dry_run"])
        self.assertEqual(confirmed["removed_count"], 1)
        self.assertFalse(quarantine.exists())

    def test_sqlite_backup_restore_drill_matches_every_table(self) -> None:
        self._create_project()
        report = DatabaseBackupService(self.db).run_restore_drill(
            output_dir=self.root / "backups",
            report_path=self.root / "backup-report.json",
        )

        self.assertTrue(report["success"])
        self.assertTrue(report["local_restore_drill_performed"])
        self.assertTrue(report["exact_table_evidence_match"])
        self.assertTrue(report["exact_schema_evidence_match"])
        self.assertTrue(report["integrity_check"]["passed"])
        self.assertGreater(report["table_count"], 0)
        self.assertTrue(Path(report["backup_path"]).is_file())
        self.assertTrue((self.root / "backup-report.json").is_file())

    def test_hosted_backup_evidence_stays_blocked_without_external_proof(self) -> None:
        blocked = hosted_backup_evidence({})
        ready = hosted_backup_evidence(
            {
                "CIVORA_DATABASE_PROVIDER_BACKUPS_ENABLED": "true",
                "CIVORA_DATABASE_BACKUP_OWNER": "operations-owner",
                "CIVORA_DATABASE_BACKUP_EVIDENCE_URL": "https://provider.example/backups/evidence",
                "CIVORA_DATABASE_RESTORE_DRILL_AT": datetime.now(timezone.utc).isoformat(),
                "CIVORA_DATABASE_BACKUP_RETENTION_DAYS": "30",
            }
        )
        invalid = hosted_backup_evidence(
            {
                "CIVORA_DATABASE_PROVIDER_BACKUPS_ENABLED": "true",
                "CIVORA_DATABASE_BACKUP_OWNER": "operations-owner",
                "CIVORA_DATABASE_BACKUP_EVIDENCE_URL": "http://localhost/evidence",
                "CIVORA_DATABASE_RESTORE_DRILL_AT": "not-a-date",
                "CIVORA_DATABASE_BACKUP_RETENTION_DAYS": "2",
            }
        )

        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(invalid["status"], "blocked")
        self.assertEqual(len(invalid["invalid_evidence"]), 3)


if __name__ == "__main__":
    unittest.main()
