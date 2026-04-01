from __future__ import annotations

from typing import Any, Dict, List, Optional
import json
import time
import uuid

from .database import Database


def _now() -> float:
    return time.time()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {})


def _json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


class ProjectStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def _project_owner(self, project_id: str) -> Optional[str]:
        connection = self.db.connect()
        try:
            row = connection.execute(
                "SELECT user_id FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            return None if row is None else str(row["user_id"])
        finally:
            connection.close()

    def list_projects(self, *, user_id: str) -> List[Dict[str, Any]]:
        connection = self.db.connect()
        try:
            rows = connection.execute(
                """
                SELECT project_id, name, description, created_at, updated_at, session_id, tags_json, latest_result_json
                FROM projects
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
            return [
                {
                    "project_id": row["project_id"],
                    "name": row["name"],
                    "description": row["description"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "session_id": row["session_id"],
                    "tags": _json_loads(row["tags_json"], []),
                    "has_result": bool(_json_loads(row["latest_result_json"], {})),
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
                SELECT *
                FROM projects
                WHERE user_id = ? AND project_id = ?
                """,
                (user_id, project_id),
            ).fetchone()
            return None if row is None else self._row_to_record(row)
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
    ) -> Dict[str, Any]:
        now = _now()
        if project_id:
            owner_id = self._project_owner(project_id)
            if owner_id is not None and owner_id != user_id:
                raise ValueError("That project belongs to another user.")

        existing = self.get_project(user_id=user_id, project_id=project_id) if project_id else None
        record = {
            "project_id": project_id or _new_id("project"),
            "user_id": user_id,
            "name": str(name or "").strip() or "Untitled Project",
            "description": description or "",
            "created_at": (existing or {}).get("created_at", now),
            "updated_at": now,
            "session_id": session_id,
            "tags": list(tags or []),
            "project_input": dict(project_input or {}),
            "latest_result": dict(latest_result or {}),
            "session_state": dict(session_state or {}),
            "metadata": dict(metadata or {}),
        }

        connection = self.db.connect()
        try:
            connection.execute(
                """
                INSERT INTO projects (
                    project_id, user_id, name, description, created_at, updated_at, session_id,
                    tags_json, project_input_json, latest_result_json, session_state_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    name = excluded.name,
                    description = excluded.description,
                    updated_at = excluded.updated_at,
                    session_id = excluded.session_id,
                    tags_json = excluded.tags_json,
                    project_input_json = excluded.project_input_json,
                    latest_result_json = excluded.latest_result_json,
                    session_state_json = excluded.session_state_json,
                    metadata_json = excluded.metadata_json
                """,
                (
                    record["project_id"],
                    record["user_id"],
                    record["name"],
                    record["description"],
                    record["created_at"],
                    record["updated_at"],
                    record["session_id"],
                    _json_dumps(record["tags"]),
                    _json_dumps(record["project_input"]),
                    _json_dumps(record["latest_result"]),
                    _json_dumps(record["session_state"]),
                    _json_dumps(record["metadata"]),
                ),
            )
            connection.commit()
            return record
        finally:
            connection.close()

    def delete_project(self, *, user_id: str, project_id: str) -> bool:
        connection = self.db.connect()
        try:
            cursor = connection.execute(
                "DELETE FROM projects WHERE user_id = ? AND project_id = ?",
                (user_id, project_id),
            )
            connection.commit()
            return cursor.rowcount > 0
        finally:
            connection.close()

    def _row_to_record(self, row: Any) -> Dict[str, Any]:
        return {
            "project_id": row["project_id"],
            "user_id": row["user_id"],
            "name": row["name"],
            "description": row["description"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "session_id": row["session_id"],
            "tags": _json_loads(row["tags_json"], []),
            "project_input": _json_loads(row["project_input_json"], {}),
            "latest_result": _json_loads(row["latest_result_json"], {}),
            "session_state": _json_loads(row["session_state_json"], {}),
            "metadata": _json_loads(row["metadata_json"], {}),
        }
