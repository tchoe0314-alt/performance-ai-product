from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
import zipfile

from .database import Database


ACCOUNT_EXPORT_VERSION = "civora_account_export_v1"
ACCOUNT_DELETE_CONFIRMATION = "DELETE MY CIVORA ACCOUNT"

_JSON_COLUMNS = {
    "tags_json": "tags",
    "project_input_json": "project_input",
    "latest_result_json": "latest_result",
    "session_state_json": "session_state",
    "metadata_json": "metadata",
    "mentions_json": "mentions",
    "context_json": "context",
    "value_json": "value",
    "payload_json": "payload",
    "result_json": "result",
    "client_context_json": "client_context",
}


def _now() -> float:
    return time.time()


def _safe_json_loads(value: Any, default: Any) -> Any:
    try:
        return json.loads(str(value or ""))
    except Exception:
        return default


def _public_row(row: Any) -> Dict[str, Any]:
    record = dict(row)
    for source, target in _JSON_COLUMNS.items():
        if source not in record:
            continue
        default: Any = [] if target in {"tags", "mentions"} else {}
        record[target] = _safe_json_loads(record.pop(source), default)
    return record


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cleanup_deletion_quarantine(
    *,
    storage_dir: Path,
    older_than_hours: float = 24.0,
    confirm: bool = False,
) -> Dict[str, Any]:
    quarantine_dir = Path(storage_dir).resolve() / "deletion_quarantine"
    age_hours = max(0.0, float(older_than_hours))
    cutoff = _now() - age_hours * 60 * 60
    candidates: List[Dict[str, Any]] = []
    failures: List[Dict[str, str]] = []
    removed_count = 0
    if quarantine_dir.is_dir():
        for path in sorted(quarantine_dir.iterdir()):
            if path.is_symlink() or not path.is_dir():
                continue
            modified_at = path.stat().st_mtime
            if modified_at > cutoff:
                continue
            record: Dict[str, Any] = {
                "name": path.name,
                "modified_at": modified_at,
                "action": "would_remove" if not confirm else "removed",
            }
            if confirm:
                try:
                    shutil.rmtree(path)
                    removed_count += 1
                except Exception as exc:
                    record["action"] = "cleanup_failed"
                    failures.append({"name": path.name, "error": exc.__class__.__name__})
            candidates.append(record)
    return {
        "success": not failures,
        "dry_run": not confirm,
        "quarantine_dir": str(quarantine_dir),
        "older_than_hours": age_hours,
        "candidate_count": len(candidates),
        "removed_count": removed_count,
        "candidates": candidates,
        "failures": failures,
        "message": (
            "Dry run only; pass --confirm to remove the listed quarantine directories."
            if not confirm
            else "Quarantine cleanup completed."
            if not failures
            else "One or more quarantine directories still require operator recovery."
        ),
    }


class DataLifecycleService:
    def __init__(
        self,
        db: Database,
        *,
        storage_dir: Path,
        upload_dir: Path,
        artifact_dir: Path,
        learning_paths: Optional[Iterable[Path]] = None,
    ) -> None:
        self.db = db
        self.storage_dir = Path(storage_dir).resolve()
        self.upload_dir = Path(upload_dir).resolve()
        self.artifact_dir = Path(artifact_dir).resolve()
        self.export_dir = self.storage_dir / "account_exports"
        self.quarantine_dir = self.storage_dir / "deletion_quarantine"
        self.learning_paths = list(dict.fromkeys(Path(path).resolve() for path in (learning_paths or [])))
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    def _rows(self, sql: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        connection = self.db.connect()
        try:
            return [_public_row(row) for row in connection.execute(sql, tuple(params)).fetchall()]
        finally:
            connection.close()

    def _account(self, user_id: str) -> Dict[str, Any]:
        rows = self._rows(
            "SELECT user_id, email, name, created_at, updated_at FROM users WHERE user_id = ?",
            (user_id,),
        )
        if not rows:
            raise ValueError("Account not found.")
        return rows[0]

    def _owned_project_ids(self, user_id: str) -> List[str]:
        rows = self._rows("SELECT project_id FROM projects WHERE user_id = ?", (user_id,))
        return [str(row.get("project_id") or "") for row in rows if str(row.get("project_id") or "")]

    def _learning_records(self, user_id: str) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        for path in self.learning_paths:
            if not path.is_file():
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for line in lines:
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                if str(record.get("user_id") or "") == user_id:
                    records.append({"source_file": path.name, "record": record})
        return records

    def _file_candidates(self, *, user_id: str, project_ids: Iterable[str]) -> List[Path]:
        candidates: List[Path] = []
        safe_prefix = f"{str(user_id).replace('/', '_')}_"
        if self.upload_dir.is_dir():
            candidates.extend(
                path for path in self.upload_dir.iterdir() if path.is_file() and path.name.startswith(safe_prefix)
            )
        artifact_user_dir = self.artifact_dir / user_id
        if artifact_user_dir.is_dir():
            candidates.extend(path for path in artifact_user_dir.rglob("*") if path.is_file())
        preview_root = self.artifact_dir / "_preview_cache"
        for project_id in project_ids:
            project_cache = preview_root / str(project_id)
            if project_cache.is_dir():
                candidates.extend(path for path in project_cache.rglob("*") if path.is_file())
        return sorted(set(path.resolve() for path in candidates if path.exists() and not path.is_symlink()))

    def _relative_storage_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.storage_dir))
        except ValueError:
            return f"external/{path.name}"

    def account_export(self, *, user_id: str) -> Dict[str, Any]:
        account = self._account(user_id)
        owned_projects = self._rows(
            "SELECT * FROM projects WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        )
        shared_memberships = self._rows(
            """
            SELECT p.project_id, p.name, p.description, p.updated_at, p.archived_at, p.deleted_at,
                   pm.role, pm.created_at AS membership_created_at, pm.updated_at AS membership_updated_at
            FROM project_members pm
            JOIN projects p ON p.project_id = pm.project_id
            WHERE pm.user_id = ? AND p.user_id <> ?
            ORDER BY p.updated_at DESC
            """,
            (user_id, user_id),
        )
        organizations = self._rows(
            """
            SELECT o.organization_id, o.name, o.created_by_user_id, o.created_at, o.updated_at,
                   o.metadata_json, om.role, om.invited_email
            FROM organization_members om
            JOIN organizations o ON o.organization_id = om.organization_id
            WHERE om.user_id = ?
            ORDER BY o.updated_at DESC
            """,
            (user_id,),
        )
        comments = self._rows(
            "SELECT * FROM project_comments WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        )
        review_requests = self._rows(
            """
            SELECT * FROM project_review_requests
            WHERE requested_by_user_id = ? OR assigned_user_id = ?
            ORDER BY updated_at DESC
            """,
            (user_id, user_id),
        )
        access_audit = self._rows(
            """
            SELECT * FROM access_audit_log
            WHERE actor_user_id = ? OR target_user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id, user_id),
        )
        memory_consent = self._rows("SELECT * FROM memory_consents WHERE user_id = ?", (user_id,))
        memory = self._rows(
            "SELECT * FROM engineering_memory WHERE owner_user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        )
        jobs = self._rows("SELECT * FROM jobs WHERE user_id = ? ORDER BY updated_at DESC", (user_id,))
        support_requests = self._rows(
            "SELECT * FROM support_requests WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        )
        project_ids = [str(item.get("project_id") or "") for item in owned_projects]
        file_manifest = [
            {
                "path": self._relative_storage_path(path),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
            for path in self._file_candidates(user_id=user_id, project_ids=project_ids)
        ]
        data = {
            "account": account,
            "owned_projects": owned_projects,
            "shared_project_memberships": shared_memberships,
            "organizations": organizations,
            "comments": comments,
            "review_requests": review_requests,
            "access_audit": access_audit,
            "memory_consent": memory_consent[0] if memory_consent else None,
            "engineering_memory": memory,
            "jobs": jobs,
            "support_requests": support_requests,
            "chat_learning_records": self._learning_records(user_id),
            "file_manifest": file_manifest,
        }
        return {
            "version": ACCOUNT_EXPORT_VERSION,
            "generated_at": _now(),
            "secrets_excluded": True,
            "data": data,
            "content_sha256": _stable_hash(data),
            "truth_label": "This archive contains Civora-held account data and owned project records available to the current account. Password hashes and active authentication tokens are excluded.",
        }

    def create_account_export_archive(self, *, user_id: str) -> Dict[str, Any]:
        package = self.account_export(user_id=user_id)
        project_ids = [str(item.get("project_id") or "") for item in package["data"]["owned_projects"]]
        source_files = self._file_candidates(user_id=user_id, project_ids=project_ids)
        user_export_dir = self.export_dir / user_id
        user_export_dir.mkdir(parents=True, exist_ok=True)
        archive_path = user_export_dir / f"civora-account-export-{int(_now())}-{uuid.uuid4().hex[:8]}.zip"
        max_bytes = int(os.getenv("CIVORA_ACCOUNT_EXPORT_MAX_BYTES") or str(5 * 1024 * 1024 * 1024))
        total_bytes = sum(path.stat().st_size for path in source_files)
        if total_bytes > max_bytes:
            raise ValueError("Account export is too large for automatic download. Contact Civora support for a managed export.")
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            archive.writestr("account-data.json", json.dumps(package, indent=2, sort_keys=True, default=str))
            for path in source_files:
                archive.write(path, arcname=f"files/{self._relative_storage_path(path)}")
        return {
            "path": archive_path,
            "filename": archive_path.name,
            "package": package,
            "archive_size_bytes": archive_path.stat().st_size,
            "included_file_count": len(source_files),
        }

    def deletion_readiness(self, *, user_id: str) -> Dict[str, Any]:
        account = self._account(user_id)
        shared_projects = self._rows(
            """
            SELECT p.project_id, p.name, COUNT(pm.user_id) AS other_member_count
            FROM projects p
            JOIN project_members pm ON pm.project_id = p.project_id AND pm.user_id <> ?
            WHERE p.user_id = ?
            GROUP BY p.project_id, p.name
            ORDER BY p.name
            """,
            (user_id, user_id),
        )
        pending_invites = self._rows(
            """
            SELECT p.project_id, p.name, COUNT(pi.invite_id) AS pending_invite_count
            FROM projects p
            JOIN project_invites pi ON pi.project_id = p.project_id AND pi.status = 'pending'
            WHERE p.user_id = ?
            GROUP BY p.project_id, p.name
            ORDER BY p.name
            """,
            (user_id,),
        )
        shared_organizations = self._rows(
            """
            SELECT o.organization_id, o.name, COUNT(om.user_id) AS other_member_count
            FROM organizations o
            JOIN organization_members om ON om.organization_id = o.organization_id AND om.user_id <> ?
            WHERE o.created_by_user_id = ?
            GROUP BY o.organization_id, o.name
            ORDER BY o.name
            """,
            (user_id, user_id),
        )
        blockers: List[Dict[str, Any]] = []
        if shared_projects:
            blockers.append(
                {
                    "code": "owned_projects_have_collaborators",
                    "message": "Transfer ownership or remove collaborators from owned projects before deleting this account.",
                    "items": shared_projects,
                }
            )
        if pending_invites:
            blockers.append(
                {
                    "code": "owned_projects_have_pending_invites",
                    "message": "Cancel pending project invitations before deleting this account.",
                    "items": pending_invites,
                }
            )
        if shared_organizations:
            blockers.append(
                {
                    "code": "owned_organizations_have_members",
                    "message": "Transfer organization ownership or remove other members before deleting this account.",
                    "items": shared_organizations,
                }
            )
        return {
            "ready": not blockers,
            "account": account,
            "confirmation_phrase": ACCOUNT_DELETE_CONFIRMATION,
            "blockers": blockers,
            "owned_project_count": len(self._owned_project_ids(user_id)),
        }

    def _account_paths(self, *, user_id: str, project_ids: Iterable[str]) -> List[Path]:
        paths: List[Path] = []
        artifact_user_dir = self.artifact_dir / user_id
        if artifact_user_dir.exists():
            paths.append(artifact_user_dir)
        safe_prefix = f"{str(user_id).replace('/', '_')}_"
        if self.upload_dir.is_dir():
            paths.extend(path for path in self.upload_dir.iterdir() if path.name.startswith(safe_prefix))
        preview_root = self.artifact_dir / "_preview_cache"
        paths.extend(preview_root / str(project_id) for project_id in project_ids if (preview_root / str(project_id)).exists())
        user_export_dir = self.export_dir / user_id
        if user_export_dir.exists():
            paths.append(user_export_dir)
        return sorted(set(path.resolve() for path in paths if path.exists()), key=lambda path: len(path.parts))

    def _quarantine_paths(self, *, user_id: str, paths: Iterable[Path]) -> tuple[Path, List[tuple[Path, Path]]]:
        root = self.quarantine_dir / f"{user_id}-{uuid.uuid4().hex[:12]}"
        root.mkdir(parents=True, exist_ok=False)
        moves: List[tuple[Path, Path]] = []
        try:
            for index, source in enumerate(paths):
                destination = root / f"item-{index:04d}-{source.name}"
                shutil.move(str(source), str(destination))
                moves.append((source, destination))
        except Exception as exc:
            try:
                self._restore_quarantined_paths(moves)
            except Exception as restore_exc:
                raise RuntimeError(
                    "Account file staging failed and one or more files could not be restored from quarantine."
                ) from restore_exc
            shutil.rmtree(root, ignore_errors=True)
            raise
        return root, moves

    def _restore_quarantined_paths(self, moves: Iterable[tuple[Path, Path]]) -> None:
        failures: List[str] = []
        for original, quarantined in reversed(list(moves)):
            if not quarantined.exists():
                continue
            try:
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(quarantined), str(original))
            except Exception as exc:
                failures.append(f"{quarantined.name}:{exc.__class__.__name__}")
        if failures:
            raise RuntimeError(f"Could not restore quarantined account files: {', '.join(failures)}")

    def _stage_learning_log_redactions(
        self,
        *,
        user_id: str,
        quarantine_root: Path,
        backups: Optional[List[tuple[Path, Path]]] = None,
    ) -> List[tuple[Path, Path]]:
        staged_backups = backups if backups is not None else []
        temporary: Optional[Path] = None
        try:
            for index, path in enumerate(self.learning_paths):
                if not path.is_file():
                    continue
                backup = quarantine_root / f"learning-{index:04d}-{path.name}.original"
                shutil.copy2(path, backup)
                staged_backups.append((path, backup))
                clean_lines: List[str] = []
                for line in path.read_text(encoding="utf-8").splitlines():
                    try:
                        record = json.loads(line)
                    except Exception:
                        clean_lines.append(line)
                        continue
                    if str(record.get("user_id") or "") != user_id:
                        clean_lines.append(json.dumps(record, ensure_ascii=False))
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
                    if clean_lines:
                        handle.write("\n".join(clean_lines) + "\n")
                    temporary = Path(handle.name)
                os.replace(temporary, path)
                temporary = None
        except Exception:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            try:
                self._restore_learning_logs(staged_backups)
            except Exception as restore_exc:
                raise RuntimeError(
                    "Learning-record redaction failed and one or more logs need operator recovery."
                ) from restore_exc
            raise
        return staged_backups

    def _restore_learning_logs(self, backups: Iterable[tuple[Path, Path]]) -> None:
        failures: List[str] = []
        for path, backup in backups:
            if backup.exists():
                try:
                    shutil.copy2(backup, path)
                except Exception as exc:
                    failures.append(f"{path.name}:{exc.__class__.__name__}")
        if failures:
            raise RuntimeError(f"Could not restore account learning logs: {', '.join(failures)}")

    def delete_account(self, *, user_id: str, confirmation: str) -> Dict[str, Any]:
        if str(confirmation or "").strip() != ACCOUNT_DELETE_CONFIRMATION:
            raise ValueError(f"Type {ACCOUNT_DELETE_CONFIRMATION} to confirm account deletion.")
        readiness = self.deletion_readiness(user_id=user_id)
        if not readiness["ready"]:
            raise ValueError("Account deletion is blocked until project and organization ownership issues are resolved.")
        project_ids = self._owned_project_ids(user_id)
        account_paths = self._account_paths(user_id=user_id, project_ids=project_ids)
        quarantine_root, moves = self._quarantine_paths(user_id=user_id, paths=account_paths)
        learning_backups: List[tuple[Path, Path]] = []
        connection = self.db.connect()
        try:
            self._stage_learning_log_redactions(
                user_id=user_id,
                quarantine_root=quarantine_root,
                backups=learning_backups,
            )
            cursor = connection.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            if cursor.rowcount <= 0:
                raise ValueError("Account not found.")
            connection.commit()
        except Exception as exc:
            connection.rollback()
            rollback_failures: List[str] = []
            try:
                self._restore_learning_logs(learning_backups)
            except Exception as rollback_exc:
                rollback_failures.append(f"learning_logs:{rollback_exc.__class__.__name__}")
            try:
                self._restore_quarantined_paths(moves)
            except Exception as rollback_exc:
                rollback_failures.append(f"files:{rollback_exc.__class__.__name__}")
            if rollback_failures:
                raise RuntimeError(
                    "Account deletion failed and rollback needs operator recovery: " + ", ".join(rollback_failures)
                ) from exc
            shutil.rmtree(quarantine_root, ignore_errors=True)
            raise
        finally:
            connection.close()
        shutil.rmtree(quarantine_root, ignore_errors=True)
        storage_cleanup_complete = not quarantine_root.exists()
        return {
            "success": storage_cleanup_complete,
            "account_deleted": True,
            "deleted_user_id": user_id,
            "deleted_project_count": len(project_ids),
            "deleted_storage_path_count": len(moves),
            "storage_cleanup_complete": storage_cleanup_complete,
            "storage_cleanup_pending": not storage_cleanup_complete,
            "authentication_revoked": True,
            "message": (
                "The account and Civora-held account data were deleted."
                if storage_cleanup_complete
                else "Account access was removed, but quarantined file cleanup requires operator follow-up."
            ),
        }


__all__ = [
    "ACCOUNT_DELETE_CONFIRMATION",
    "ACCOUNT_EXPORT_VERSION",
    "DataLifecycleService",
    "cleanup_deletion_quarantine",
]
