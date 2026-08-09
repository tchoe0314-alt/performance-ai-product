from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
from urllib.parse import urlparse

from .database import Database


BACKUP_REPORT_VERSION = "civora_backup_restore_drill_v1"


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _stable_digest(rows: Iterable[Any]) -> str:
    serialized = [json.dumps(dict(row), sort_keys=True, default=str, separators=(",", ":")) for row in rows]
    serialized.sort()
    return hashlib.sha256("\n".join(serialized).encode("utf-8")).hexdigest()


def _quote_sqlite_identifier(value: str) -> str:
    if "\x00" in value:
        raise ValueError("SQLite identifiers cannot contain NUL bytes.")
    return '"' + value.replace('"', '""') + '"'


def hosted_backup_evidence(env: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    source = dict(os.environ if env is None else env)
    owner = str(source.get("CIVORA_DATABASE_BACKUP_OWNER") or "").strip()
    evidence_url = str(source.get("CIVORA_DATABASE_BACKUP_EVIDENCE_URL") or "").strip()
    restore_drill_at = str(source.get("CIVORA_DATABASE_RESTORE_DRILL_AT") or "").strip()
    retention_days = str(source.get("CIVORA_DATABASE_BACKUP_RETENTION_DAYS") or "").strip()
    provider_enabled = _truthy(source.get("CIVORA_DATABASE_PROVIDER_BACKUPS_ENABLED"))
    missing = [
        name
        for name, present in (
            ("CIVORA_DATABASE_PROVIDER_BACKUPS_ENABLED", provider_enabled),
            ("CIVORA_DATABASE_BACKUP_OWNER", bool(owner)),
            ("CIVORA_DATABASE_BACKUP_EVIDENCE_URL", bool(evidence_url)),
            ("CIVORA_DATABASE_RESTORE_DRILL_AT", bool(restore_drill_at)),
            ("CIVORA_DATABASE_BACKUP_RETENTION_DAYS", bool(retention_days)),
        )
        if not present
    ]
    invalid: list[Dict[str, str]] = []
    parsed_evidence_url = urlparse(evidence_url)
    if evidence_url and (parsed_evidence_url.scheme != "https" or not parsed_evidence_url.netloc):
        invalid.append(
            {
                "field": "CIVORA_DATABASE_BACKUP_EVIDENCE_URL",
                "code": "backup_evidence_url_not_https",
                "message": "Backup evidence must use a non-empty HTTPS URL.",
            }
        )
    retention_value = 0
    if retention_days:
        try:
            retention_value = int(retention_days)
        except ValueError:
            retention_value = 0
        if retention_value < 7:
            invalid.append(
                {
                    "field": "CIVORA_DATABASE_BACKUP_RETENTION_DAYS",
                    "code": "backup_retention_too_short",
                    "message": "Backup retention must be an integer of at least 7 days.",
                }
            )
    restore_drill_datetime: Optional[datetime] = None
    if restore_drill_at:
        try:
            restore_drill_datetime = datetime.fromisoformat(restore_drill_at.replace("Z", "+00:00"))
            if restore_drill_datetime.tzinfo is None:
                raise ValueError("timezone required")
            restore_drill_datetime = restore_drill_datetime.astimezone(timezone.utc)
        except ValueError:
            invalid.append(
                {
                    "field": "CIVORA_DATABASE_RESTORE_DRILL_AT",
                    "code": "restore_drill_timestamp_invalid",
                    "message": "Restore drill time must be an ISO-8601 timestamp with a timezone.",
                }
            )
        if restore_drill_datetime is not None:
            age_seconds = (datetime.now(timezone.utc) - restore_drill_datetime).total_seconds()
            if age_seconds < -300:
                invalid.append(
                    {
                        "field": "CIVORA_DATABASE_RESTORE_DRILL_AT",
                        "code": "restore_drill_timestamp_in_future",
                        "message": "Restore drill time cannot be in the future.",
                    }
                )
            elif age_seconds > 366 * 24 * 60 * 60:
                invalid.append(
                    {
                        "field": "CIVORA_DATABASE_RESTORE_DRILL_AT",
                        "code": "restore_drill_evidence_stale",
                        "message": "Restore drill evidence is older than one year.",
                    }
                )
    return {
        "status": "ready" if not missing and not invalid else "blocked",
        "provider_backups_enabled": provider_enabled,
        "owner_configured": bool(owner),
        "evidence_url_configured": bool(evidence_url),
        "restore_drill_at": restore_drill_at,
        "retention_days": retention_value if retention_days else None,
        "missing_env_vars": missing,
        "invalid_evidence": invalid,
        "truth_label": "Hosted backup readiness requires actual provider backup evidence and a recorded restore drill; configuration names alone do not prove recovery.",
    }


class DatabaseBackupService:
    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def _sqlite_table_evidence(path: Path) -> Dict[str, Dict[str, Any]]:
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        try:
            tables = [
                str(row["name"])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
            ]
            evidence: Dict[str, Dict[str, Any]] = {}
            for table in tables:
                quoted_table = _quote_sqlite_identifier(table)
                # Table names come only from sqlite_master and are quoted by the tested identifier helper.
                count_query = "SELECT COUNT(*) FROM __TABLE__".replace("__TABLE__", quoted_table)  # nosec B608
                content_query = "SELECT * FROM __TABLE__".replace("__TABLE__", quoted_table)  # nosec B608
                row_count = connection.execute(count_query).fetchone()[0]
                rows = connection.execute(content_query).fetchall()
                evidence[table] = {
                    "row_count": int(row_count),
                    "content_sha256": _stable_digest(rows),
                }
            return evidence
        finally:
            connection.close()

    @staticmethod
    def _sqlite_schema_sha256(path: Path) -> str:
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT type, name, tbl_name, sql
                FROM sqlite_master
                WHERE name NOT LIKE 'sqlite_%'
                ORDER BY type, name
                """
            ).fetchall()
            return _stable_digest(rows)
        finally:
            connection.close()

    @staticmethod
    def _sqlite_integrity(path: Path) -> str:
        connection = sqlite3.connect(path)
        try:
            rows = connection.execute("PRAGMA integrity_check").fetchall()
            return "; ".join(str(row[0]) for row in rows)
        finally:
            connection.close()

    def run_restore_drill(
        self,
        *,
        output_dir: Path,
        report_path: Optional[Path] = None,
        env: Optional[Mapping[str, str]] = None,
    ) -> Dict[str, Any]:
        started_at = time.time()
        output_root = Path(output_dir).resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        if self.db.storage_kind != "sqlite":
            provider = hosted_backup_evidence(env)
            report = {
                "version": BACKUP_REPORT_VERSION,
                "success": provider["status"] == "ready",
                "status": "provider_evidence_ready" if provider["status"] == "ready" else "blocked",
                "storage_kind": self.db.storage_kind,
                "local_restore_drill_performed": False,
                "provider_backup_evidence": provider,
                "blockers": [] if provider["status"] == "ready" else [
                    {
                        "code": "hosted_backup_restore_evidence_missing",
                        "message": "Attach provider backup retention evidence and a completed hosted restore drill before claiming hosted recovery readiness.",
                    }
                ],
                "elapsed_seconds": round(time.time() - started_at, 3),
            }
            if report_path is not None:
                Path(report_path).parent.mkdir(parents=True, exist_ok=True)
                Path(report_path).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
            return report

        source_path = Path(self.db.db_path).resolve()
        if not source_path.is_file():
            raise ValueError("SQLite database file does not exist.")
        backup_path = output_root / f"civora-backup-{int(started_at)}.sqlite3"
        source_connection = sqlite3.connect(source_path)
        backup_connection = sqlite3.connect(backup_path)
        try:
            source_connection.backup(backup_connection)
        finally:
            backup_connection.close()
            source_connection.close()

        source_evidence = self._sqlite_table_evidence(source_path)
        backup_evidence = self._sqlite_table_evidence(backup_path)
        source_schema_sha256 = self._sqlite_schema_sha256(source_path)
        backup_schema_sha256 = self._sqlite_schema_sha256(backup_path)
        source_integrity = self._sqlite_integrity(source_path)
        backup_integrity = self._sqlite_integrity(backup_path)
        with tempfile.TemporaryDirectory(prefix="civora-restore-drill-") as temp_dir:
            restored_path = Path(temp_dir) / "restored.sqlite3"
            shutil.copy2(backup_path, restored_path)
            restored_evidence = self._sqlite_table_evidence(restored_path)
            restored_schema_sha256 = self._sqlite_schema_sha256(restored_path)
            restored_integrity = self._sqlite_integrity(restored_path)
        table_evidence_matched = source_evidence == backup_evidence == restored_evidence
        schema_evidence_matched = source_schema_sha256 == backup_schema_sha256 == restored_schema_sha256
        integrity_passed = all(value.lower() == "ok" for value in (source_integrity, backup_integrity, restored_integrity))
        matched = table_evidence_matched and schema_evidence_matched and integrity_passed
        backup_sha256 = hashlib.sha256(backup_path.read_bytes()).hexdigest()
        report = {
            "version": BACKUP_REPORT_VERSION,
            "success": matched,
            "status": "passed" if matched else "failed",
            "storage_kind": "sqlite",
            "local_restore_drill_performed": True,
            "backup_path": str(backup_path),
            "backup_size_bytes": backup_path.stat().st_size,
            "backup_sha256": backup_sha256,
            "table_count": len(source_evidence),
            "source_table_evidence": source_evidence,
            "backup_table_evidence": backup_evidence,
            "restored_table_evidence": restored_evidence,
            "exact_table_evidence_match": table_evidence_matched,
            "source_schema_sha256": source_schema_sha256,
            "backup_schema_sha256": backup_schema_sha256,
            "restored_schema_sha256": restored_schema_sha256,
            "exact_schema_evidence_match": schema_evidence_matched,
            "integrity_check": {
                "source": source_integrity,
                "backup": backup_integrity,
                "restored": restored_integrity,
                "passed": integrity_passed,
            },
            "blockers": [] if matched else [
                {
                    "code": "backup_restore_mismatch",
                    "message": "The restored SQLite database did not match the source table counts and content hashes.",
                }
            ],
            "elapsed_seconds": round(time.time() - started_at, 3),
            "truth_label": "This proves an isolated SQLite backup and restore roundtrip for the recorded database only. Hosted PostgreSQL recovery requires separate provider evidence.",
        }
        if report_path is not None:
            Path(report_path).parent.mkdir(parents=True, exist_ok=True)
            Path(report_path).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        return report


__all__ = ["BACKUP_REPORT_VERSION", "DatabaseBackupService", "hosted_backup_evidence"]
