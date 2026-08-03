from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import time
import uuid

from .database import Database


def _now() -> float:
    return time.time()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        try:
            return _json_safe(value.to_dict())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return _json_safe(vars(value))
        except Exception:
            pass
    return str(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(_json_safe(value if value is not None else {}))


def _json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _project_name(name: Any, project_input: Dict[str, Any]) -> str:
    requested = str(name or "").strip()
    if requested and requested.lower() != "untitled project":
        return requested
    site_inputs = dict(dict(project_input.get("meta") or {}).get("site_inputs") or {})
    geocode = dict(site_inputs.get("geocode") or {})
    address = str(
        site_inputs.get("address")
        or geocode.get("display_name")
        or geocode.get("formatted_address")
        or ""
    ).strip()
    street = address.split(",", 1)[0].strip()
    return f"{street} Site" if street else "Untitled Project"


def _merge_project_input_value(existing: Any, incoming: Any) -> Any:
    if incoming is None:
        return existing
    if isinstance(existing, dict) and isinstance(incoming, dict):
        return _merge_project_input(existing, incoming)
    if isinstance(existing, list) and isinstance(incoming, list):
        return incoming if incoming else existing
    if isinstance(existing, str) and isinstance(incoming, str):
        return incoming if incoming.strip() else existing
    if (
        isinstance(existing, (int, float))
        and isinstance(incoming, (int, float))
        and not isinstance(existing, bool)
        and not isinstance(incoming, bool)
    ):
        if incoming != 0:
            return incoming
        return existing if existing not in (0, 0.0) else incoming
    return incoming


def _merge_project_input(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    if not existing:
        return dict(incoming or {})
    if not incoming:
        return dict(existing or {})
    merged: Dict[str, Any] = {}
    for key in set(existing.keys()) | set(incoming.keys()):
        if key not in incoming:
            merged[key] = existing[key]
        elif key not in existing:
            merged[key] = incoming[key]
        else:
            merged[key] = _merge_project_input_value(existing[key], incoming[key])
    return merged


_CANDIDATE_REVIEW_STATE_KEYS = (
    "candidate_review_inbox_v1",
    "candidate_review_decisions_v1",
    "candidate_review_accepted_drafts_v1",
    "candidate_review_rejected_v1",
    "source_confidence_map_v1",
    "civora_vision_training_dataset_v1",
    "civora_vision_quality_report_v1",
    "civora_vision_ground_truth_ledger_v1",
    "civora_vision_ground_truth_dataset_v1",
    "civora_vision_split_registry_v1",
    "civora_vision_active_learning_queue_v1",
    "civora_vision_ground_truth_coverage_v1",
    "civora_vision_review_workspace_v1",
)


def _site_inputs(project_input: Dict[str, Any]) -> Dict[str, Any]:
    return dict(dict(project_input.get("meta") or {}).get("site_inputs") or {})


def _candidate_review_progress(site_inputs: Dict[str, Any]) -> int:
    decisions = list(site_inputs.get("candidate_review_decisions_v1") or [])
    if decisions:
        return len(decisions)
    counts = dict(dict(site_inputs.get("candidate_review_inbox_v1") or {}).get("counts") or {})
    return int(counts.get("accepted") or 0) + int(counts.get("rejected") or 0)


def _preserve_newer_candidate_review_state(
    existing: Dict[str, Any],
    incoming: Dict[str, Any],
    merged: Dict[str, Any],
) -> Dict[str, Any]:
    existing_site_inputs = _site_inputs(existing)
    incoming_site_inputs = _site_inputs(incoming)
    incoming_address = str(incoming_site_inputs.get("address") or "").strip().lower()
    existing_address = str(existing_site_inputs.get("address") or "").strip().lower()
    if incoming_address and existing_address and incoming_address != existing_address:
        reset_site_inputs = _site_inputs(merged)
        for key in _CANDIDATE_REVIEW_STATE_KEYS:
            if key in incoming_site_inputs:
                reset_site_inputs[key] = incoming_site_inputs[key]
            else:
                reset_site_inputs.pop(key, None)
        reset_meta = dict(merged.get("meta") or {})
        reset_meta["site_inputs"] = reset_site_inputs
        reset = dict(merged)
        reset["meta"] = reset_meta
        return reset
    if _candidate_review_progress(existing_site_inputs) <= _candidate_review_progress(incoming_site_inputs):
        return merged

    protected_site_inputs = _site_inputs(merged)
    for key in _CANDIDATE_REVIEW_STATE_KEYS:
        if key in existing_site_inputs:
            protected_site_inputs[key] = existing_site_inputs[key]
    protected_meta = dict(merged.get("meta") or {})
    protected_meta["site_inputs"] = protected_site_inputs
    protected = dict(merged)
    protected["meta"] = protected_meta
    return protected


PROJECT_ROLES = ("owner", "admin", "editor", "reviewer", "viewer")
ROLE_RANK = {role: index for index, role in enumerate(("viewer", "reviewer", "editor", "admin", "owner"))}


def _normalize_role(role: str, *, default: str = "viewer") -> str:
    normalized = str(role or "").strip().lower()
    return normalized if normalized in PROJECT_ROLES else default


def _role_allows(actual: str, required: str) -> bool:
    return ROLE_RANK.get(_normalize_role(actual), -1) >= ROLE_RANK.get(_normalize_role(required), 0)


class ProjectStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def _public_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        connection = self.db.connect()
        try:
            row = connection.execute(
                "SELECT user_id, email, name, created_at, updated_at FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return None if row is None else dict(row)
        finally:
            connection.close()

    def _public_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        email_norm = str(email or "").strip().lower()
        if not email_norm:
            return None
        connection = self.db.connect()
        try:
            row = connection.execute(
                "SELECT user_id, email, name, created_at, updated_at FROM users WHERE email = ?",
                (email_norm,),
            ).fetchone()
            return None if row is None else dict(row)
        finally:
            connection.close()

    def _log_access_event(
        self,
        connection: Any,
        *,
        actor_user_id: str,
        action: str,
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        target_user_id: Optional[str] = None,
        target_email: str = "",
        role: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO access_audit_log (
                audit_id, organization_id, project_id, actor_user_id, target_user_id,
                target_email, action, role, created_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _new_id("audit"),
                organization_id,
                project_id,
                actor_user_id,
                target_user_id,
                str(target_email or "").strip().lower(),
                str(action or "").strip(),
                str(role or "").strip(),
                _now(),
                _json_dumps(metadata or {}),
            ),
        )

    def ensure_default_organization(self, *, user_id: str) -> Dict[str, Any]:
        connection = self.db.connect()
        try:
            row = connection.execute(
                """
                SELECT o.organization_id, o.name, o.created_by_user_id, o.created_at, o.updated_at, o.metadata_json
                FROM organizations o
                JOIN organization_members om ON om.organization_id = o.organization_id
                WHERE om.user_id = ? AND o.created_by_user_id = ?
                ORDER BY o.created_at ASC
                """,
                (user_id, user_id),
            ).fetchone()
            if row is not None:
                return self._organization_row_to_record(row)

            user = self._public_user_by_id(user_id) or {"name": "Personal", "email": ""}
            now = _now()
            organization_id = _new_id("org")
            name = f"{str(user.get('name') or 'Personal').strip() or 'Personal'} Team"
            metadata = {"source": "default_personal_team"}
            connection.execute(
                """
                INSERT INTO organizations (organization_id, name, created_by_user_id, created_at, updated_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (organization_id, name, user_id, now, now, _json_dumps(metadata)),
            )
            connection.execute(
                """
                INSERT INTO organization_members (organization_id, user_id, role, invited_email, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (organization_id, user_id, "owner", str(user.get("email") or ""), now, now),
            )
            self._log_access_event(
                connection,
                actor_user_id=user_id,
                organization_id=organization_id,
                target_user_id=user_id,
                target_email=str(user.get("email") or ""),
                action="organization_created",
                role="owner",
            )
            connection.commit()
            return {
                "organization_id": organization_id,
                "name": name,
                "created_by_user_id": user_id,
                "created_at": now,
                "updated_at": now,
                "metadata": metadata,
            }
        finally:
            connection.close()

    def _ensure_owner_membership(
        self,
        connection: Any,
        *,
        project_id: str,
        user_id: str,
        organization_id: Optional[str],
    ) -> None:
        now = _now()
        user = self._public_user_by_id(user_id) or {}
        existing = connection.execute(
            "SELECT role FROM project_members WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone()
        if existing is None:
            connection.execute(
                """
                INSERT INTO project_members (project_id, user_id, role, invited_email, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (project_id, user_id, "owner", str(user.get("email") or ""), now, now),
            )
            self._log_access_event(
                connection,
                actor_user_id=user_id,
                organization_id=organization_id,
                project_id=project_id,
                target_user_id=user_id,
                target_email=str(user.get("email") or ""),
                action="project_owner_membership_created",
                role="owner",
            )
        elif existing["role"] != "owner":
            connection.execute(
                "UPDATE project_members SET role = ?, updated_at = ? WHERE project_id = ? AND user_id = ?",
                ("owner", now, project_id, user_id),
            )

    def project_role(self, *, user_id: str, project_id: str) -> Optional[str]:
        connection = self.db.connect()
        try:
            row = connection.execute(
                """
                SELECT p.user_id, pm.role
                FROM projects p
                LEFT JOIN project_members pm ON pm.project_id = p.project_id AND pm.user_id = ?
                WHERE p.project_id = ?
                """,
                (user_id, project_id),
            ).fetchone()
            if row is None:
                return None
            if row["user_id"] == user_id:
                return "owner"
            return _normalize_role(row["role"]) if row["role"] else None
        finally:
            connection.close()

    def has_project_permission(self, *, user_id: str, project_id: str, minimum_role: str) -> bool:
        role = self.project_role(user_id=user_id, project_id=project_id)
        return bool(role and _role_allows(role, minimum_role))

    def list_projects(
        self,
        *,
        user_id: str,
        include_archived: bool = True,
        include_deleted: bool = False,
    ) -> List[Dict[str, Any]]:
        connection = self.db.connect()
        try:
            lifecycle_filters = ["(p.user_id = ? OR pm.user_id = ?)"]
            params: List[Any] = [user_id, user_id, user_id, user_id]
            if not include_archived:
                lifecycle_filters.append("p.archived_at IS NULL")
            if not include_deleted:
                lifecycle_filters.append("p.deleted_at IS NULL")
            rows = connection.execute(
                f"""
                SELECT p.project_id, p.user_id, p.organization_id, p.name, p.description,
                       p.created_at, p.updated_at, p.session_id, p.has_result, p.tags_json,
                       p.archived_at, p.deleted_at,
                       COALESCE(pm.role, CASE WHEN p.user_id = ? THEN 'owner' ELSE '' END) AS access_role
                FROM projects p
                LEFT JOIN project_members pm ON pm.project_id = p.project_id AND pm.user_id = ?
                WHERE {' AND '.join(lifecycle_filters)}
                ORDER BY CASE WHEN p.archived_at IS NULL THEN 0 ELSE 1 END, p.updated_at DESC
                """,
                params,
            ).fetchall()
            return [
                {
                    "project_id": row["project_id"],
                    "user_id": row["user_id"],
                    "organization_id": row["organization_id"] if "organization_id" in row.keys() else None,
                    "name": row["name"],
                    "description": row["description"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "session_id": row["session_id"],
                    "tags": _json_loads(row["tags_json"], []),
                    "has_result": bool(row["has_result"]),
                    "archived_at": row["archived_at"],
                    "deleted_at": row["deleted_at"],
                    "access_role": _normalize_role(row["access_role"], default="owner" if row["user_id"] == user_id else "viewer"),
                }
                for row in rows
            ]
        finally:
            connection.close()

    def get_project(self, *, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        connection = self.db.connect()
        try:
            row = connection.execute(
                """
                SELECT p.*, COALESCE(pm.role, CASE WHEN p.user_id = ? THEN 'owner' ELSE '' END) AS access_role
                FROM projects p
                LEFT JOIN project_members pm ON pm.project_id = p.project_id AND pm.user_id = ?
                WHERE p.project_id = ? AND p.deleted_at IS NULL AND (p.user_id = ? OR pm.user_id = ?)
                """,
                (user_id, user_id, project_id, user_id, user_id),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_record(row)
        finally:
            connection.close()

    def get_project_shell(self, *, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        connection = self.db.connect()
        try:
            row = connection.execute(
                """
                SELECT p.project_id, p.user_id, p.organization_id, p.name, p.description,
                       p.created_at, p.updated_at, p.session_id, p.has_result, p.tags_json,
                       p.project_input_json, p.session_state_json, p.metadata_json,
                       p.archived_at, p.deleted_at,
                       COALESCE(pm.role, CASE WHEN p.user_id = ? THEN 'owner' ELSE '' END) AS access_role
                FROM projects p
                LEFT JOIN project_members pm ON pm.project_id = p.project_id AND pm.user_id = ?
                WHERE p.project_id = ? AND p.deleted_at IS NULL AND (p.user_id = ? OR pm.user_id = ?)
                """,
                (user_id, user_id, project_id, user_id, user_id),
            ).fetchone()
            return None if row is None else self._shell_row_to_record(row)
        finally:
            connection.close()

    def get_project_latest_result(self, *, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        connection = self.db.connect()
        try:
            row = connection.execute(
                """
                SELECT p.latest_result_json
                FROM projects p
                LEFT JOIN project_members pm ON pm.project_id = p.project_id AND pm.user_id = ?
                WHERE p.project_id = ? AND p.deleted_at IS NULL AND (p.user_id = ? OR pm.user_id = ?)
                """,
                (user_id, project_id, user_id, user_id),
            ).fetchone()
            if row is None:
                return None
            return dict(_json_loads(row["latest_result_json"], {}) or {})
        finally:
            connection.close()

    def update_project_candidate_review_state(
        self,
        *,
        user_id: str,
        project_id: str,
        candidate_state: Dict[str, Any],
        minimum_role: str = "reviewer",
    ) -> Dict[str, Any]:
        """Persist candidate review state without loading or rewriting generated results."""

        connection = self.db.connect()
        try:
            row = connection.execute(
                """
                SELECT p.project_id, p.user_id, p.organization_id, p.name, p.description,
                       p.created_at, p.updated_at, p.session_id, p.has_result, p.tags_json,
                       p.project_input_json, p.session_state_json, p.metadata_json,
                       COALESCE(pm.role, CASE WHEN p.user_id = ? THEN 'owner' ELSE '' END) AS access_role
                FROM projects p
                LEFT JOIN project_members pm ON pm.project_id = p.project_id AND pm.user_id = ?
                WHERE p.project_id = ? AND p.deleted_at IS NULL AND (p.user_id = ? OR pm.user_id = ?)
                """,
                (user_id, user_id, project_id, user_id, user_id),
            ).fetchone()
            if row is None:
                raise ValueError("Project not found.")
            role = _normalize_role(
                row["access_role"],
                default="owner" if row["user_id"] == user_id else "viewer",
            )
            if not _role_allows(role, minimum_role):
                raise ValueError(f"You do not have {minimum_role} access to that project.")

            project_input = dict(_json_loads(row["project_input_json"], {}) or {})
            input_meta = dict(project_input.get("meta") or {})
            site_inputs = dict(input_meta.get("site_inputs") or {})
            site_inputs.update(_json_safe(candidate_state))
            input_meta["site_inputs"] = site_inputs
            project_input["meta"] = input_meta
            project_name = _project_name(row["name"], project_input)
            updated_at = _now()
            connection.execute(
                "UPDATE projects SET name = ?, project_input_json = ?, updated_at = ? WHERE project_id = ?",
                (project_name, _json_dumps(project_input), updated_at, project_id),
            )
            connection.commit()

            shell_row = dict(row)
            shell_row["name"] = project_name
            shell_row["project_input_json"] = _json_dumps(project_input)
            shell_row["updated_at"] = updated_at
            record = self._shell_row_to_record(shell_row)
            record["access_role"] = role
            return record
        finally:
            connection.close()

    def save_project_shell(
        self,
        *,
        user_id: str,
        project_id: str,
        name: str,
        description: str = "",
        session_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        project_input: Optional[Dict[str, Any]] = None,
        session_state: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        organization_id: Optional[str] = None,
        minimum_role: str = "editor",
    ) -> Dict[str, Any]:
        """Update project shell state while preserving the generated result in place."""

        connection = self.db.connect()
        try:
            row = connection.execute(
                """
                SELECT p.project_id, p.user_id, p.organization_id, p.name, p.description,
                       p.created_at, p.updated_at, p.session_id, p.has_result, p.tags_json,
                       p.project_input_json, p.session_state_json, p.metadata_json,
                       COALESCE(pm.role, CASE WHEN p.user_id = ? THEN 'owner' ELSE '' END) AS access_role
                FROM projects p
                LEFT JOIN project_members pm ON pm.project_id = p.project_id AND pm.user_id = ?
                WHERE p.project_id = ? AND p.deleted_at IS NULL AND (p.user_id = ? OR pm.user_id = ?)
                """,
                (user_id, user_id, project_id, user_id, user_id),
            ).fetchone()
            if row is None:
                raise ValueError("Project not found.")
            role = _normalize_role(
                row["access_role"],
                default="owner" if row["user_id"] == user_id else "viewer",
            )
            if not _role_allows(role, minimum_role):
                raise ValueError(f"You do not have {minimum_role} access to that project.")

            existing_project_input = dict(_json_loads(row["project_input_json"], {}) or {})
            incoming_project_input = dict(project_input or {})
            merged_project_input = (
                _merge_project_input(existing_project_input, incoming_project_input)
                if incoming_project_input
                else existing_project_input
            )
            merged_project_input = _preserve_newer_candidate_review_state(
                existing_project_input,
                incoming_project_input,
                merged_project_input,
            )
            project_name = _project_name(name, merged_project_input)
            updated_at = _now()
            resolved_organization_id = organization_id or row["organization_id"]
            resolved_tags = list(tags or [])
            resolved_session_state = dict(session_state or {})
            resolved_metadata = dict(metadata or {})
            connection.execute(
                """
                UPDATE projects
                SET organization_id = ?, name = ?, description = ?, updated_at = ?,
                    session_id = ?, tags_json = ?, project_input_json = ?,
                    session_state_json = ?, metadata_json = ?
                WHERE project_id = ?
                """,
                (
                    resolved_organization_id,
                    project_name,
                    description or "",
                    updated_at,
                    session_id,
                    _json_dumps(resolved_tags),
                    _json_dumps(merged_project_input),
                    _json_dumps(resolved_session_state),
                    _json_dumps(resolved_metadata),
                    project_id,
                ),
            )
            connection.commit()

            shell_row = dict(row)
            shell_row.update(
                {
                    "organization_id": resolved_organization_id,
                    "name": project_name,
                    "description": description or "",
                    "updated_at": updated_at,
                    "session_id": session_id,
                    "tags_json": _json_dumps(resolved_tags),
                    "project_input_json": _json_dumps(merged_project_input),
                    "session_state_json": _json_dumps(resolved_session_state),
                    "metadata_json": _json_dumps(resolved_metadata),
                }
            )
            record = self._shell_row_to_record(shell_row)
            record["access_role"] = role
            return record
        finally:
            connection.close()

    def save_project(
        self,
        *,
        user_id: str,
        project_id: Optional[str],
        name: str,
        description: str = "",
        session_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        project_input: Optional[Dict[str, Any]] = None,
        latest_result: Optional[Dict[str, Any]] = None,
        session_state: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        organization_id: Optional[str] = None,
        minimum_role: str = "editor",
    ) -> Dict[str, Any]:
        now = _now()
        existing = self.get_project(user_id=user_id, project_id=project_id) if project_id else None
        if project_id:
            connection = self.db.connect()
            try:
                lifecycle_row = connection.execute(
                    "SELECT user_id, deleted_at FROM projects WHERE project_id = ?",
                    (project_id,),
                ).fetchone()
            finally:
                connection.close()
            if lifecycle_row is not None and lifecycle_row["deleted_at"] is not None:
                raise ValueError("This project is in Recently deleted. Restore it before saving.")
            if lifecycle_row is not None and not self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role=minimum_role):
                raise ValueError(f"You do not have {minimum_role} access to that project.")
        elif not organization_id:
            organization_id = self.ensure_default_organization(user_id=user_id)["organization_id"]

        existing_latest_result = dict((existing or {}).get("latest_result") or {})
        existing_project_input = dict((existing or {}).get("project_input") or {})
        incoming_latest_result = dict(latest_result or {})
        incoming_project_input = dict(project_input or {})
        # Empty autosaves should never wipe a richer staged checkpoint that is
        # already persisted on the project record.
        if existing_latest_result and not incoming_latest_result:
            incoming_latest_result = existing_latest_result
        if existing_project_input and incoming_project_input:
            incoming_project_input = _merge_project_input(existing_project_input, incoming_project_input)
            incoming_project_input = _preserve_newer_candidate_review_state(
                existing_project_input,
                dict(project_input or {}),
                incoming_project_input,
            )
        elif existing_project_input and not incoming_project_input:
            incoming_project_input = existing_project_input
        record = {
            "project_id": project_id or _new_id("project"),
            "user_id": user_id,
            "organization_id": organization_id or (existing or {}).get("organization_id"),
            "name": _project_name(name, incoming_project_input),
            "description": description or "",
            "created_at": (existing or {}).get("created_at", now),
            "updated_at": now,
            "session_id": session_id,
            "tags": list(tags or []),
            "project_input": incoming_project_input,
            "latest_result": incoming_latest_result,
            "session_state": dict(session_state or {}),
            "metadata": dict(metadata or {}),
        }

        connection = self.db.connect()
        try:
            connection.execute(
                """
                INSERT INTO projects (
                    project_id, user_id, organization_id, name, description, created_at, updated_at, session_id,
                    has_result,
                    tags_json, project_input_json, latest_result_json, session_state_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    organization_id = COALESCE(excluded.organization_id, projects.organization_id),
                    name = excluded.name,
                    description = excluded.description,
                    updated_at = excluded.updated_at,
                    session_id = excluded.session_id,
                    has_result = CASE
                        WHEN excluded.has_result = 0 AND projects.has_result = 1 THEN projects.has_result
                        ELSE excluded.has_result
                    END,
                    tags_json = excluded.tags_json,
                    project_input_json = excluded.project_input_json,
                    latest_result_json = CASE
                        WHEN excluded.latest_result_json = '{}' AND projects.latest_result_json IS NOT NULL AND projects.latest_result_json != '{}' THEN projects.latest_result_json
                        ELSE excluded.latest_result_json
                    END,
                    session_state_json = excluded.session_state_json,
                    metadata_json = excluded.metadata_json
                """,
                (
                    record["project_id"],
                    record["user_id"],
                    record["organization_id"],
                    record["name"],
                    record["description"],
                    record["created_at"],
                    record["updated_at"],
                    record["session_id"],
                    1 if record["latest_result"] else 0,
                    _json_dumps(record["tags"]),
                    _json_dumps(record["project_input"]),
                    _json_dumps(record["latest_result"]),
                    _json_dumps(record["session_state"]),
                    _json_dumps(record["metadata"]),
                ),
            )
            self._ensure_owner_membership(
                connection,
                project_id=record["project_id"],
                user_id=user_id,
                organization_id=record["organization_id"],
            )
            connection.commit()
            record["access_role"] = "owner"
            return record
        finally:
            connection.close()

    def duplicate_project(
        self,
        *,
        user_id: str,
        project_id: str,
        name: str = "",
    ) -> Dict[str, Any]:
        source = self.get_project(user_id=user_id, project_id=project_id)
        if source is None:
            raise ValueError("Project not found.")
        duplicate_name = str(name or "").strip() or f"{source.get('name') or 'Untitled Project'} Copy"
        metadata = dict(source.get("metadata") or {})
        metadata.update(
            {
                "duplicated_from_project_id": project_id,
                "duplicated_at": _now(),
                "duplicate_owner_user_id": user_id,
            }
        )
        duplicate = self.save_project(
            user_id=user_id,
            project_id=None,
            name=duplicate_name,
            description=str(source.get("description") or ""),
            session_id=None,
            tags=list(source.get("tags") or []),
            project_input=dict(source.get("project_input") or {}),
            latest_result=dict(source.get("latest_result") or {}),
            session_state=dict(source.get("session_state") or {}),
            metadata=metadata,
        )
        connection = self.db.connect()
        try:
            self._log_access_event(
                connection,
                actor_user_id=user_id,
                organization_id=duplicate.get("organization_id"),
                project_id=duplicate["project_id"],
                action="project_duplicated",
                role="owner",
                metadata={"source_project_id": project_id},
            )
            connection.commit()
        finally:
            connection.close()
        return duplicate

    def set_project_archived(self, *, user_id: str, project_id: str, archived: bool) -> Dict[str, Any]:
        role = self.project_role(user_id=user_id, project_id=project_id)
        if not role or not _role_allows(role, "editor"):
            raise ValueError("You do not have editor access to that project.")
        timestamp = _now()
        archived_at = timestamp if archived else None
        connection = self.db.connect()
        try:
            cursor = connection.execute(
                "UPDATE projects SET archived_at = ?, updated_at = ? WHERE project_id = ? AND deleted_at IS NULL",
                (archived_at, timestamp, project_id),
            )
            if cursor.rowcount <= 0:
                raise ValueError("Project not found.")
            self._log_access_event(
                connection,
                actor_user_id=user_id,
                project_id=project_id,
                action="project_archived" if archived else "project_unarchived",
                role=role,
            )
            connection.commit()
        finally:
            connection.close()
        project = self.get_project(user_id=user_id, project_id=project_id)
        if project is None:
            raise ValueError("Project not found.")
        return project

    def delete_project(self, *, user_id: str, project_id: str) -> bool:
        if not self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role="owner"):
            return False
        connection = self.db.connect()
        try:
            now = _now()
            cursor = connection.execute(
                "UPDATE projects SET deleted_at = ?, updated_at = ? WHERE user_id = ? AND project_id = ? AND deleted_at IS NULL",
                (now, now, user_id, project_id),
            )
            if cursor.rowcount > 0:
                self._log_access_event(
                    connection,
                    actor_user_id=user_id,
                    project_id=project_id,
                    action="project_soft_deleted",
                    role="owner",
                )
            connection.commit()
            return cursor.rowcount > 0
        finally:
            connection.close()

    def restore_project(self, *, user_id: str, project_id: str) -> Dict[str, Any]:
        if not self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role="owner"):
            raise ValueError("You do not have owner access to that project.")
        connection = self.db.connect()
        try:
            now = _now()
            cursor = connection.execute(
                "UPDATE projects SET deleted_at = NULL, archived_at = NULL, updated_at = ? WHERE user_id = ? AND project_id = ? AND deleted_at IS NOT NULL",
                (now, user_id, project_id),
            )
            if cursor.rowcount <= 0:
                raise ValueError("Deleted project not found.")
            self._log_access_event(
                connection,
                actor_user_id=user_id,
                project_id=project_id,
                action="project_restored",
                role="owner",
            )
            connection.commit()
        finally:
            connection.close()
        project = self.get_project(user_id=user_id, project_id=project_id)
        if project is None:
            raise ValueError("Project could not be restored.")
        return project

    def invite_project_member(self, *, actor_user_id: str, project_id: str, email: str, role: str) -> Dict[str, Any]:
        if not self.has_project_permission(user_id=actor_user_id, project_id=project_id, minimum_role="admin"):
            raise ValueError("You do not have admin access to that project.")
        normalized_role = _normalize_role(role, default="viewer")
        if normalized_role == "owner":
            raise ValueError("Owner access cannot be granted by invite.")
        target_email = str(email or "").strip().lower()
        if not target_email or "@" not in target_email:
            raise ValueError("A valid invite email is required.")
        target_user = self._public_user_by_email(target_email)
        now = _now()
        invite_id = _new_id("invite")
        connection = self.db.connect()
        try:
            project = connection.execute(
                "SELECT organization_id FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                raise ValueError("Project not found.")
            status = "accepted" if target_user else "pending"
            connection.execute(
                """
                INSERT INTO project_invites (
                    invite_id, project_id, email, role, invited_by_user_id,
                    accepted_by_user_id, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invite_id,
                    project_id,
                    target_email,
                    normalized_role,
                    actor_user_id,
                    target_user.get("user_id") if target_user else None,
                    status,
                    now,
                    now,
                ),
            )
            if target_user:
                connection.execute(
                    """
                    INSERT INTO project_members (project_id, user_id, role, invited_email, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_id, user_id) DO UPDATE SET
                        role = excluded.role,
                        invited_email = excluded.invited_email,
                        updated_at = excluded.updated_at
                    """,
                    (project_id, target_user["user_id"], normalized_role, target_email, now, now),
                )
            self._log_access_event(
                connection,
                actor_user_id=actor_user_id,
                organization_id=project["organization_id"] if "organization_id" in project.keys() else None,
                project_id=project_id,
                target_user_id=target_user.get("user_id") if target_user else None,
                target_email=target_email,
                action="project_member_added" if target_user else "project_member_invited",
                role=normalized_role,
                metadata={"invite_id": invite_id, "status": status},
            )
            connection.commit()
            return {
                "invite_id": invite_id,
                "project_id": project_id,
                "email": target_email,
                "role": normalized_role,
                "status": status,
                "user": target_user or {},
                "created_at": now,
                "updated_at": now,
            }
        finally:
            connection.close()

    def remove_project_member(self, *, actor_user_id: str, project_id: str, user_id: str) -> bool:
        if not self.has_project_permission(user_id=actor_user_id, project_id=project_id, minimum_role="admin"):
            raise ValueError("You do not have admin access to that project.")
        if actor_user_id == user_id:
            raise ValueError("You cannot remove your own access from this admin endpoint.")
        target_role = self.project_role(user_id=user_id, project_id=project_id)
        if target_role == "owner":
            raise ValueError("Owner access cannot be removed from this endpoint.")
        connection = self.db.connect()
        try:
            project = connection.execute(
                "SELECT organization_id FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            target_user = self._public_user_by_id(user_id) or {}
            cursor = connection.execute(
                "DELETE FROM project_members WHERE project_id = ? AND user_id = ?",
                (project_id, user_id),
            )
            if cursor.rowcount <= 0:
                connection.rollback()
                return False
            self._log_access_event(
                connection,
                actor_user_id=actor_user_id,
                organization_id=project["organization_id"] if project and "organization_id" in project.keys() else None,
                project_id=project_id,
                target_user_id=user_id,
                target_email=str(target_user.get("email") or ""),
                action="project_member_removed",
                role=str(target_role or ""),
            )
            connection.commit()
            return True
        finally:
            connection.close()

    def update_project_member_role(self, *, actor_user_id: str, project_id: str, user_id: str, role: str) -> Dict[str, Any]:
        if not self.has_project_permission(user_id=actor_user_id, project_id=project_id, minimum_role="admin"):
            raise ValueError("You do not have admin access to that project.")
        normalized_role = _normalize_role(role, default="viewer")
        if normalized_role == "owner":
            raise ValueError("Owner access cannot be assigned from this endpoint.")
        target_role = self.project_role(user_id=user_id, project_id=project_id)
        if not target_role:
            raise ValueError("Project member not found.")
        if target_role == "owner":
            raise ValueError("Owner access cannot be changed from this endpoint.")
        connection = self.db.connect()
        try:
            project = connection.execute(
                "SELECT organization_id FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            target_user = self._public_user_by_id(user_id) or {}
            connection.execute(
                "UPDATE project_members SET role = ?, updated_at = ? WHERE project_id = ? AND user_id = ?",
                (normalized_role, _now(), project_id, user_id),
            )
            self._log_access_event(
                connection,
                actor_user_id=actor_user_id,
                organization_id=project["organization_id"] if project and "organization_id" in project.keys() else None,
                project_id=project_id,
                target_user_id=user_id,
                target_email=str(target_user.get("email") or ""),
                action="project_member_role_changed",
                role=normalized_role,
                metadata={"previous_role": target_role},
            )
            connection.commit()
            return {
                "project_id": project_id,
                "user_id": user_id,
                "email": str(target_user.get("email") or ""),
                "name": str(target_user.get("name") or ""),
                "role": normalized_role,
                "previous_role": target_role,
            }
        finally:
            connection.close()

    def project_audit_log(self, *, user_id: str, project_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role="admin"):
            return []
        connection = self.db.connect()
        try:
            rows = connection.execute(
                """
                SELECT audit_id, organization_id, project_id, actor_user_id, target_user_id,
                       target_email, action, role, created_at, metadata_json
                FROM access_audit_log
                WHERE project_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (project_id, int(max(1, min(limit, 200)))),
            ).fetchall()
            return [
                {
                    "audit_id": row["audit_id"],
                    "organization_id": row["organization_id"],
                    "project_id": row["project_id"],
                    "actor_user_id": row["actor_user_id"],
                    "target_user_id": row["target_user_id"],
                    "target_email": row["target_email"],
                    "action": row["action"],
                    "role": row["role"],
                    "created_at": row["created_at"],
                    "metadata": _json_loads(row["metadata_json"], {}),
                }
                for row in rows
            ]
        finally:
            connection.close()

    def project_admin_surface(self, *, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        if not self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role="viewer"):
            return None
        project = self.get_project_shell(user_id=user_id, project_id=project_id)
        if project is None:
            return None
        connection = self.db.connect()
        try:
            members = [
                {
                    "user_id": row["user_id"],
                    "email": row["email"],
                    "name": row["name"],
                    "role": _normalize_role(row["role"]),
                    "invited_email": row["invited_email"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in connection.execute(
                    """
                    SELECT pm.user_id, u.email, u.name, pm.role, pm.invited_email, pm.created_at, pm.updated_at
                    FROM project_members pm
                    JOIN users u ON u.user_id = pm.user_id
                    WHERE pm.project_id = ?
                    ORDER BY CASE pm.role
                        WHEN 'owner' THEN 5
                        WHEN 'admin' THEN 4
                        WHEN 'editor' THEN 3
                        WHEN 'reviewer' THEN 2
                        ELSE 1
                    END DESC, u.email ASC
                    """,
                    (project_id,),
                ).fetchall()
            ]
            invites = [
                {
                    "invite_id": row["invite_id"],
                    "project_id": row["project_id"],
                    "email": row["email"],
                    "role": _normalize_role(row["role"]),
                    "status": row["status"],
                    "invited_by_user_id": row["invited_by_user_id"],
                    "accepted_by_user_id": row["accepted_by_user_id"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in connection.execute(
                    """
                    SELECT invite_id, project_id, email, role, invited_by_user_id, accepted_by_user_id,
                           status, created_at, updated_at
                    FROM project_invites
                    WHERE project_id = ?
                    ORDER BY updated_at DESC
                    """,
                    (project_id,),
                ).fetchall()
            ]
        finally:
            connection.close()
        return {
            "project": project,
            "roles": list(PROJECT_ROLES),
            "current_user_role": self.project_role(user_id=user_id, project_id=project_id),
            "permissions": {
                "can_view": self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role="viewer"),
                "can_review": self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role="reviewer"),
                "can_edit": self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role="editor"),
                "can_manage_access": self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role="admin"),
                "can_delete_project": self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role="owner"),
            },
            "members": members,
            "invites": invites,
            "audit_log": self.project_audit_log(user_id=user_id, project_id=project_id, limit=50),
            "explanation": (
                "Project access uses owner, admin, editor, reviewer, and viewer roles. "
                "Admin-level users can add or remove non-owner project members; viewers keep read-only access."
            ),
        }

    def record_project_presence(
        self,
        *,
        user_id: str,
        project_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role="viewer"):
            raise ValueError("You do not have access to that project.")
        now = _now()
        safe_context = {
            key: value
            for key, value in _json_safe(context or {}).items()
            if key in {"mode", "selected_object_id", "view"}
        }
        connection = self.db.connect()
        try:
            connection.execute(
                """
                INSERT INTO project_presence (project_id, user_id, last_seen_at, context_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(project_id, user_id) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    context_json = excluded.context_json
                """,
                (project_id, user_id, now, _json_dumps(safe_context)),
            )
            connection.commit()
        finally:
            connection.close()
        user = self._public_user_by_id(user_id) or {}
        return {
            "project_id": project_id,
            "user_id": user_id,
            "name": str(user.get("name") or "Project member"),
            "email": str(user.get("email") or ""),
            "last_seen_at": now,
            "context": safe_context,
        }

    def add_project_comment(
        self,
        *,
        user_id: str,
        project_id: str,
        body: str,
        mentions: Optional[List[str]] = None,
        object_id: str = "",
        issue_id: str = "",
    ) -> Dict[str, Any]:
        if not self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role="reviewer"):
            raise ValueError("You need reviewer access to comment on that project.")
        normalized_body = str(body or "").strip()
        if not normalized_body:
            raise ValueError("Comment text is required.")
        if len(normalized_body) > 4000:
            raise ValueError("Comments must be 4000 characters or fewer.")
        normalized_mentions = list(
            dict.fromkeys(
                str(item or "").strip().lower()
                for item in list(mentions or [])
                if str(item or "").strip()
            )
        )[:25]
        now = _now()
        comment_id = _new_id("comment")
        connection = self.db.connect()
        try:
            connection.execute(
                """
                INSERT INTO project_comments (
                    comment_id, project_id, user_id, body, mentions_json,
                    object_id, issue_id, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    comment_id,
                    project_id,
                    user_id,
                    normalized_body,
                    _json_dumps(normalized_mentions),
                    str(object_id or "").strip(),
                    str(issue_id or "").strip(),
                    "open",
                    now,
                    now,
                ),
            )
            self._log_access_event(
                connection,
                actor_user_id=user_id,
                project_id=project_id,
                action="project_comment_added",
                role=str(self.project_role(user_id=user_id, project_id=project_id) or ""),
                metadata={"comment_id": comment_id, "object_id": object_id, "issue_id": issue_id},
            )
            connection.commit()
        finally:
            connection.close()
        return {
            "comment_id": comment_id,
            "project_id": project_id,
            "user_id": user_id,
            "body": normalized_body,
            "mentions": normalized_mentions,
            "object_id": str(object_id or "").strip(),
            "issue_id": str(issue_id or "").strip(),
            "status": "open",
            "created_at": now,
            "updated_at": now,
        }

    def update_project_comment_status(
        self,
        *,
        user_id: str,
        project_id: str,
        comment_id: str,
        status: str,
    ) -> Dict[str, Any]:
        if not self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role="reviewer"):
            raise ValueError("You need reviewer access to update comments.")
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in {"open", "resolved", "reopened"}:
            raise ValueError("Comment status must be open, resolved, or reopened.")
        now = _now()
        connection = self.db.connect()
        try:
            cursor = connection.execute(
                "UPDATE project_comments SET status = ?, updated_at = ? WHERE project_id = ? AND comment_id = ?",
                (normalized_status, now, project_id, comment_id),
            )
            if cursor.rowcount <= 0:
                raise ValueError("Comment not found.")
            connection.commit()
        finally:
            connection.close()
        return {"comment_id": comment_id, "project_id": project_id, "status": normalized_status, "updated_at": now}

    def create_review_request(
        self,
        *,
        user_id: str,
        project_id: str,
        assigned_email: str = "",
        message: str = "",
    ) -> Dict[str, Any]:
        if not self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role="editor"):
            raise ValueError("You need editor access to request a review.")
        target_email = str(assigned_email or "").strip().lower()
        target_user = self._public_user_by_email(target_email) if target_email else None
        if target_email and target_user is None:
            raise ValueError("Invite that reviewer to the project before assigning the review request.")
        if target_user and not self.has_project_permission(
            user_id=str(target_user.get("user_id") or ""),
            project_id=project_id,
            minimum_role="reviewer",
        ):
            raise ValueError("The assigned user needs reviewer access to this project.")
        now = _now()
        request_id = _new_id("review")
        connection = self.db.connect()
        try:
            connection.execute(
                """
                INSERT INTO project_review_requests (
                    request_id, project_id, requested_by_user_id, assigned_user_id,
                    assigned_email, message, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    project_id,
                    user_id,
                    target_user.get("user_id") if target_user else None,
                    target_email,
                    str(message or "").strip()[:4000],
                    "open",
                    now,
                    now,
                ),
            )
            self._log_access_event(
                connection,
                actor_user_id=user_id,
                project_id=project_id,
                target_user_id=target_user.get("user_id") if target_user else None,
                target_email=target_email,
                action="project_review_requested",
                role="reviewer",
                metadata={"request_id": request_id},
            )
            connection.commit()
        finally:
            connection.close()
        return {
            "request_id": request_id,
            "project_id": project_id,
            "requested_by_user_id": user_id,
            "assigned_user_id": target_user.get("user_id") if target_user else None,
            "assigned_email": target_email,
            "message": str(message or "").strip()[:4000],
            "status": "open",
            "created_at": now,
            "updated_at": now,
        }

    def update_review_request_status(
        self,
        *,
        user_id: str,
        project_id: str,
        request_id: str,
        status: str,
    ) -> Dict[str, Any]:
        if not self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role="reviewer"):
            raise ValueError("You need reviewer access to update a review request.")
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in {"open", "in_review", "completed", "cancelled"}:
            raise ValueError("Review request status is not supported.")
        now = _now()
        connection = self.db.connect()
        try:
            cursor = connection.execute(
                "UPDATE project_review_requests SET status = ?, updated_at = ? WHERE project_id = ? AND request_id = ?",
                (normalized_status, now, project_id, request_id),
            )
            if cursor.rowcount <= 0:
                raise ValueError("Review request not found.")
            connection.commit()
        finally:
            connection.close()
        return {"request_id": request_id, "project_id": project_id, "status": normalized_status, "updated_at": now}

    def project_collaboration_surface(self, *, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        if not self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role="viewer"):
            return None
        now = _now()
        connection = self.db.connect()
        try:
            comments = [
                {
                    "comment_id": row["comment_id"],
                    "project_id": row["project_id"],
                    "user_id": row["user_id"],
                    "author_name": row["author_name"],
                    "author_email": row["author_email"],
                    "body": row["body"],
                    "mentions": _json_loads(row["mentions_json"], []),
                    "object_id": row["object_id"],
                    "issue_id": row["issue_id"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in connection.execute(
                    """
                    SELECT pc.*, u.name AS author_name, u.email AS author_email
                    FROM project_comments pc
                    JOIN users u ON u.user_id = pc.user_id
                    WHERE pc.project_id = ?
                    ORDER BY pc.updated_at DESC
                    LIMIT 100
                    """,
                    (project_id,),
                ).fetchall()
            ]
            review_requests = [dict(row) for row in connection.execute(
                """
                SELECT request_id, project_id, requested_by_user_id, assigned_user_id,
                       assigned_email, message, status, created_at, updated_at
                FROM project_review_requests
                WHERE project_id = ?
                ORDER BY updated_at DESC
                LIMIT 100
                """,
                (project_id,),
            ).fetchall()]
            active_after = now - 120.0
            presence = [
                {
                    "user_id": row["user_id"],
                    "name": row["name"],
                    "email": row["email"],
                    "last_seen_at": row["last_seen_at"],
                    "context": _json_loads(row["context_json"], {}),
                }
                for row in connection.execute(
                    """
                    SELECT pp.user_id, u.name, u.email, pp.last_seen_at, pp.context_json
                    FROM project_presence pp
                    JOIN users u ON u.user_id = pp.user_id
                    WHERE pp.project_id = ? AND pp.last_seen_at >= ?
                    ORDER BY pp.last_seen_at DESC
                    """,
                    (project_id, active_after),
                ).fetchall()
            ]
        finally:
            connection.close()
        role = str(self.project_role(user_id=user_id, project_id=project_id) or "viewer")
        return {
            "project_id": project_id,
            "current_user_role": role,
            "permissions": {
                "can_comment": _role_allows(role, "reviewer"),
                "can_request_review": _role_allows(role, "editor"),
                "can_manage_access": _role_allows(role, "admin"),
            },
            "presence": presence,
            "comments": comments,
            "review_requests": review_requests,
            "poll_after_seconds": 20,
        }

    def get_memory_consent(self, *, user_id: str) -> Dict[str, Any]:
        connection = self.db.connect()
        try:
            row = connection.execute(
                "SELECT personal_enabled, company_enabled, global_learning_enabled, updated_at FROM memory_consents WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        finally:
            connection.close()
        return {
            "personal_enabled": bool(row["personal_enabled"]) if row else False,
            "company_enabled": bool(row["company_enabled"]) if row else False,
            "global_learning_enabled": bool(row["global_learning_enabled"]) if row else False,
            "updated_at": row["updated_at"] if row else None,
            "default": "off",
        }

    def update_memory_consent(
        self,
        *,
        user_id: str,
        personal_enabled: bool,
        company_enabled: bool,
        global_learning_enabled: bool,
    ) -> Dict[str, Any]:
        now = _now()
        connection = self.db.connect()
        try:
            connection.execute(
                """
                INSERT INTO memory_consents (
                    user_id, personal_enabled, company_enabled, global_learning_enabled, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    personal_enabled = excluded.personal_enabled,
                    company_enabled = excluded.company_enabled,
                    global_learning_enabled = excluded.global_learning_enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    1 if personal_enabled else 0,
                    1 if company_enabled else 0,
                    1 if global_learning_enabled else 0,
                    now,
                ),
            )
            connection.commit()
        finally:
            connection.close()
        return self.get_memory_consent(user_id=user_id)

    def add_engineering_memory(
        self,
        *,
        user_id: str,
        scope: str,
        category: str,
        label: str,
        value: Any,
        project_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        source: str = "user_explicit",
    ) -> Dict[str, Any]:
        normalized_scope = str(scope or "").strip().lower()
        if normalized_scope not in {"project", "personal", "company"}:
            raise ValueError("Memory scope must be project, personal, or company.")
        consent = self.get_memory_consent(user_id=user_id)
        if normalized_scope == "personal" and not consent["personal_enabled"]:
            raise ValueError("Enable personal memory before saving personal preferences.")
        if normalized_scope == "company" and not consent["company_enabled"]:
            raise ValueError("Enable company memory before saving company preferences.")
        if normalized_scope == "project":
            if not project_id or not self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role="reviewer"):
                raise ValueError("Reviewer access to a project is required for project memory.")
        if normalized_scope == "company":
            if not project_id or not self.has_project_permission(user_id=user_id, project_id=project_id, minimum_role="admin"):
                raise ValueError("Admin access to a project is required for company memory.")
            project = self.get_project(user_id=user_id, project_id=project_id)
            organization_id = str((project or {}).get("organization_id") or organization_id or "") or None
            if not organization_id:
                raise ValueError("Company memory requires an organization-backed project.")
        normalized_label = str(label or "").strip()
        if not normalized_label:
            raise ValueError("A memory label is required.")
        memory_id = _new_id("memory")
        now = _now()
        connection = self.db.connect()
        try:
            connection.execute(
                """
                INSERT INTO engineering_memory (
                    memory_id, owner_user_id, organization_id, project_id, scope,
                    category, label, value_json, source, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    user_id,
                    organization_id,
                    project_id if normalized_scope in {"project", "company"} else None,
                    normalized_scope,
                    str(category or "preference").strip().lower() or "preference",
                    normalized_label[:240],
                    _json_dumps(value),
                    str(source or "user_explicit").strip() or "user_explicit",
                    "active",
                    now,
                    now,
                ),
            )
            connection.commit()
        finally:
            connection.close()
        return {
            "memory_id": memory_id,
            "scope": normalized_scope,
            "category": str(category or "preference").strip().lower() or "preference",
            "label": normalized_label[:240],
            "value": _json_safe(value),
            "project_id": project_id if normalized_scope in {"project", "company"} else None,
            "organization_id": organization_id,
            "source": str(source or "user_explicit").strip() or "user_explicit",
            "status": "active",
            "suggestion_only": True,
            "engineering_authority": False,
            "created_at": now,
            "updated_at": now,
        }

    def list_engineering_memory(
        self,
        *,
        user_id: str,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        project: Optional[Dict[str, Any]] = None
        if project_id:
            project = self.get_project(user_id=user_id, project_id=project_id)
            if project is None:
                raise ValueError("Project not found.")
        consent = self.get_memory_consent(user_id=user_id)
        scope_clauses: List[str] = []
        params: List[Any] = []
        if consent["personal_enabled"]:
            scope_clauses.append("(scope = 'personal' AND owner_user_id = ?)")
            params.append(user_id)
        if project_id:
            scope_clauses.append("(scope = 'project' AND project_id = ?)")
            params.append(project_id)
            organization_id = str((project or {}).get("organization_id") or "")
            if organization_id and consent["company_enabled"]:
                scope_clauses.append("(scope = 'company' AND organization_id = ?)")
                params.append(organization_id)
        if not scope_clauses:
            return {
                "consent": consent,
                "items": [],
                "rules": {
                    "silent_learning": False,
                    "overrides_standards": False,
                    "changes_engineering_state": False,
                    "suggestion_only": True,
                },
            }
        connection = self.db.connect()
        try:
            rows = connection.execute(
                f"""
                SELECT memory_id, owner_user_id, organization_id, project_id, scope,
                       category, label, value_json, source, status, created_at, updated_at
                FROM engineering_memory
                WHERE status = 'active' AND ({' OR '.join(scope_clauses)})
                ORDER BY updated_at DESC
                LIMIT 200
                """,
                params,
            ).fetchall()
        finally:
            connection.close()
        items = [
            {
                "memory_id": row["memory_id"],
                "scope": row["scope"],
                "category": row["category"],
                "label": row["label"],
                "value": _json_loads(row["value_json"], None),
                "project_id": row["project_id"],
                "organization_id": row["organization_id"],
                "source": row["source"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "suggestion_only": True,
                "engineering_authority": False,
            }
            for row in rows
        ]
        return {
            "consent": consent,
            "items": items,
            "rules": {
                "silent_learning": False,
                "overrides_standards": False,
                "changes_engineering_state": False,
                "suggestion_only": True,
            },
        }

    def delete_engineering_memory(self, *, user_id: str, memory_id: str) -> bool:
        connection = self.db.connect()
        try:
            row = connection.execute(
                """
                SELECT owner_user_id, project_id, scope
                FROM engineering_memory
                WHERE memory_id = ? AND status = 'active'
                """,
                (memory_id,),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return False

        owner_user_id = str(row["owner_user_id"] or "")
        project_id = str(row["project_id"] or "")
        scope = str(row["scope"] or "")
        may_delete = owner_user_id == user_id
        if not may_delete and scope in {"project", "company"} and project_id:
            may_delete = self.has_project_permission(
                user_id=user_id,
                project_id=project_id,
                minimum_role="admin",
            )
        if not may_delete:
            return False

        connection = self.db.connect()
        try:
            now = _now()
            cursor = connection.execute(
                "UPDATE engineering_memory SET status = 'deleted', updated_at = ? WHERE memory_id = ? AND status = 'active'",
                (now, memory_id),
            )
            connection.commit()
            return cursor.rowcount > 0
        finally:
            connection.close()

    def _row_to_record(self, row: Any) -> Dict[str, Any]:
        return {
            "project_id": row["project_id"],
            "user_id": row["user_id"],
            "organization_id": row["organization_id"] if "organization_id" in row.keys() else None,
            "name": row["name"],
            "description": row["description"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "session_id": row["session_id"],
            "has_result": bool(row["has_result"]) if "has_result" in row.keys() else bool(_json_loads(row["latest_result_json"], {})),
            "tags": _json_loads(row["tags_json"], []),
            "project_input": _json_loads(row["project_input_json"], {}),
            "latest_result": _json_loads(row["latest_result_json"], {}),
            "session_state": _json_loads(row["session_state_json"], {}),
            "metadata": _json_loads(row["metadata_json"], {}),
            "archived_at": row["archived_at"] if "archived_at" in row.keys() else None,
            "deleted_at": row["deleted_at"] if "deleted_at" in row.keys() else None,
            "access_role": _normalize_role(row["access_role"], default="owner") if "access_role" in row.keys() else "owner",
        }

    def _shell_row_to_record(self, row: Any) -> Dict[str, Any]:
        return {
            "project_id": row["project_id"],
            "user_id": row["user_id"],
            "organization_id": row["organization_id"] if "organization_id" in row.keys() else None,
            "name": row["name"],
            "description": row["description"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "session_id": row["session_id"],
            "has_result": bool(row["has_result"]),
            "tags": _json_loads(row["tags_json"], []),
            "project_input": _json_loads(row["project_input_json"], {}),
            "latest_result": {},
            "session_state": _json_loads(row["session_state_json"], {}),
            "metadata": _json_loads(row["metadata_json"], {}),
            "archived_at": row["archived_at"] if "archived_at" in row.keys() else None,
            "deleted_at": row["deleted_at"] if "deleted_at" in row.keys() else None,
            "access_role": _normalize_role(row["access_role"], default="owner") if "access_role" in row.keys() else "owner",
        }

    def _organization_row_to_record(self, row: Any) -> Dict[str, Any]:
        return {
            "organization_id": row["organization_id"],
            "name": row["name"],
            "created_by_user_id": row["created_by_user_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "metadata": _json_loads(row["metadata_json"], {}),
        }
