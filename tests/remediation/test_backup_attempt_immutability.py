"""C04 independent expectations; all databases are synthetic and disposable."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import errno
import io
import json
import multiprocessing
import os
from contextlib import redirect_stdout, redirect_stderr
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from backend.services.backup_restore import DatabaseBackupService, _publish_report
from backend.scripts import run_backup_restore_drill as cli


def _parallel_attempt(source, output, report):
    service = DatabaseBackupService(SimpleNamespace(storage_kind="sqlite", db_path=source))
    with patch("backend.services.backup_restore.time.time", return_value=1792454400):
        service.run_restore_drill(output_dir=output, report_path=report)


class BackupAttemptImmutabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="c04-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.sqlite3"
        with sqlite3.connect(self.source) as connection:
            connection.execute("CREATE TABLE specimen (value TEXT)")
            connection.execute("INSERT INTO specimen VALUES ('first')")
        self.service = DatabaseBackupService(SimpleNamespace(
            storage_kind="sqlite", db_path=self.source,
        ))

    def test_same_second_preserves_first_snapshot_and_restores_both(self):
        with patch("backend.services.backup_restore.time.time", return_value=1792454400):
            first = self.service.run_restore_drill(output_dir=self.root / "backups")
            first_path = Path(first["backup_path"])
            first_bytes = first_path.read_bytes()
            with sqlite3.connect(self.source) as connection:
                connection.execute("UPDATE specimen SET value='second'")
            second = self.service.run_restore_drill(output_dir=self.root / "backups")
        self.assertNotEqual(first["backup_path"], second["backup_path"])
        self.assertEqual(first_bytes, first_path.read_bytes())
        for report, expected in ((first, "first"), (second, "second")):
            path = Path(report["backup_path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), report["backup_sha256"])
            with sqlite3.connect(path) as connection:
                self.assertEqual(connection.execute("SELECT value FROM specimen").fetchone()[0], expected)

    def test_existing_report_is_not_replaced(self):
        report = self.root / "existing.json"
        original = b'{"historical_evidence":true}\n'
        report.write_bytes(original)
        try:
            self.service.run_restore_drill(output_dir=self.root / "backups", report_path=report)
        except FileExistsError:
            pass
        self.assertEqual(report.read_bytes(), original)

    def test_report_source_alias_cannot_destroy_database(self):
        original = self.source.read_bytes()
        try:
            self.service.run_restore_drill(output_dir=self.root / "backups", report_path=self.source)
        except (ValueError, FileExistsError):
            pass
        self.assertEqual(self.source.read_bytes(), original)

    def test_post_copy_source_edit_does_not_relabel_snapshot(self):
        original_reader = self.service._sqlite_table_evidence
        edited = False

        def read_with_concurrent_edit(path):
            nonlocal edited
            if not edited:
                edited = True
                with sqlite3.connect(self.source) as connection:
                    connection.execute("UPDATE specimen SET value='later edit'")
            return original_reader(path)

        with patch.object(self.service, "_sqlite_table_evidence", side_effect=read_with_concurrent_edit):
            report = self.service.run_restore_drill(output_dir=self.root / "backups")
        self.assertTrue(report["success"], "An intact restored snapshot must not be compared to later live data")
        self.assertEqual(report["source_table_evidence"], report["backup_table_evidence"])
        with sqlite3.connect(report["backup_path"]) as connection:
            self.assertEqual(connection.execute("SELECT value FROM specimen").fetchone()[0], "first")

    def test_dangling_report_symlink_is_preserved(self):
        report = self.root / "report.json"
        report.symlink_to(self.root / "absent-target")
        with self.assertRaises(FileExistsError):
            self.service.run_restore_drill(output_dir=self.root / "backups", report_path=report)
        self.assertTrue(report.is_symlink())
        self.assertFalse((self.root / "absent-target").exists())

    def test_report_publication_race_keeps_winner_and_cleans_staging(self):
        report = self.root / "report.json"
        real_link = __import__("os").link

        def competing_link(source, destination):
            report.write_bytes(b"winner")
            return real_link(source, destination)

        with patch("backend.services.backup_restore.os.link", side_effect=competing_link):
            with self.assertRaises(FileExistsError):
                _publish_report(report, {"new": True})
        self.assertEqual(report.read_bytes(), b"winner")
        self.assertEqual(list(self.root.glob(".civora-report-*")), [])

    def test_backup_publication_failure_preserves_previous_attempt(self):
        output = self.root / "backups"
        first = self.service.run_restore_drill(output_dir=output)
        before = {path.name: path.read_bytes() for path in output.iterdir()}
        with patch("backend.services.backup_restore.os.link", side_effect=PermissionError("synthetic denied")):
            with self.assertRaises(PermissionError):
                self.service.run_restore_drill(output_dir=output)
        self.assertEqual(before, {path.name: path.read_bytes() for path in output.iterdir()})
        self.assertTrue(Path(first["backup_path"]).exists())

    def test_multiprocess_same_second_attempts_keep_all_artifacts(self):
        output = self.root / "parallel"
        context = multiprocessing.get_context("fork")
        children = [context.Process(target=_parallel_attempt, args=(
            self.source, output, self.root / f"attempt-{index}.json",
        )) for index in range(3)]
        try:
            for child in children:
                child.start()
            for child in children:
                child.join(timeout=10)
                self.assertFalse(child.is_alive(), "Owned synthetic backup worker timed out")
                self.assertEqual(child.exitcode, 0)
        finally:
            for child in children:
                if child.is_alive():
                    child.terminate()
                    child.join(timeout=5)
        reports = [json.loads((self.root / f"attempt-{index}.json").read_text()) for index in range(3)]
        self.assertEqual(len({report["backup_path"] for report in reports}), 3)
        for report in reports:
            self.assertTrue(report["success"])
            self.assertEqual(hashlib.sha256(Path(report["backup_path"]).read_bytes()).hexdigest(), report["backup_sha256"])
        self.assertEqual(len(list(output.iterdir())), 3)

    def test_backup_collision_preserves_preexisting_destination(self):
        output = self.root / "backups"
        real_link = os.link

        def collide(source, destination):
            Path(destination).write_bytes(b"earlier artifact")
            return real_link(source, destination)

        with patch("backend.services.backup_restore.os.link", side_effect=collide):
            with self.assertRaises(FileExistsError):
                self.service.run_restore_drill(output_dir=output)
        self.assertEqual([path.read_bytes() for path in output.iterdir()], [b"earlier artifact"])

    def test_report_disk_full_and_cancellation_remove_only_owned_staging(self):
        earlier = self.root / "earlier.json"
        earlier.write_bytes(b"earlier")
        for failure in (OSError(errno.ENOSPC, "synthetic full"), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__):
                with patch("backend.services.backup_restore.json.dump", side_effect=failure):
                    with self.assertRaises(type(failure)):
                        _publish_report(self.root / "new.json", {"test": True})
                self.assertFalse((self.root / "new.json").exists())
                self.assertEqual(list(self.root.glob(".civora-report-*")), [])
                self.assertEqual(earlier.read_bytes(), b"earlier")

    def test_copy_interruption_and_disk_full_preserve_prior_backups(self):
        output = self.root / "backups"
        self.service.run_restore_drill(output_dir=output)
        before = {path.name: path.read_bytes() for path in output.iterdir()}
        source_before = self.source.read_bytes()
        real_connect = sqlite3.connect
        for failure in (OSError(errno.ENOSPC, "synthetic full"), KeyboardInterrupt()):
            def failing_connect(path, **kwargs):
                connection = real_connect(path, **kwargs)
                if kwargs.get("uri"):
                    def fail_copy(destination):
                        # Simulate a partially written staging file before failure.
                        destination.execute("CREATE TABLE incomplete (value TEXT)")
                        destination.commit()
                        raise failure
                    return SimpleNamespace(backup=fail_copy, close=connection.close)
                return connection

            with self.subTest(failure=type(failure).__name__):
                with patch("backend.services.backup_restore.sqlite3.connect", side_effect=failing_connect):
                    with self.assertRaises(type(failure)):
                        self.service.run_restore_drill(output_dir=output)
                self.assertEqual(before, {path.name: path.read_bytes() for path in output.iterdir()})
                self.assertEqual(self.source.read_bytes(), source_before)

    def test_cli_default_reports_are_distinct_and_backups_valid(self):
        results = []
        for _ in range(2):
            stdout = io.StringIO()
            with patch.object(cli, "Database", return_value=self.service.db), patch(
                "sys.argv", ["backup", "--db-path", str(self.source), "--output-dir", str(self.root / "cli")],
            ), redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as caught:
                    cli.main()
            self.assertEqual(caught.exception.code, 0)
            results.append(json.loads(stdout.getvalue()))
        self.assertNotEqual(results[0]["report"], results[1]["report"])
        for result in results:
            self.assertTrue(json.loads(Path(result["report"]).read_text())["success"])

    def test_cli_existing_report_rejected_before_database_initialization(self):
        report = self.root / "existing.json"
        report.write_bytes(b"original")
        with patch.object(cli, "Database") as database, patch(
            "sys.argv", ["backup", "--report", str(report)],
        ), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                cli.main()
        self.assertEqual(caught.exception.code, 2)
        database.assert_not_called()
        self.assertEqual(report.read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()
