from __future__ import annotations

from typing import Any, Dict, List, Optional
import json
import re
import time
import uuid
from urllib.parse import urlsplit, urlunsplit

from .database import Database


SUPPORT_CATEGORIES = {
    "workflow",
    "account",
    "data",
    "source",
    "export",
    "billing",
    "privacy",
    "safety",
    "other",
}
SUPPORT_SEVERITIES = {"p0", "p1", "p2", "p3"}
SUPPORT_STATUSES = {"received", "triaged", "in_progress", "resolved", "closed"}
_SENSITIVE_KEY_MARKERS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "credential",
)


def _now() -> float:
    return time.time()


def _new_id() -> str:
    return f"support_{uuid.uuid4().hex[:16]}"


def _safe_text(value: Any, *, limit: int) -> str:
    return _redact_text(str(value or "").strip())[:limit]


def _redact_text(value: str) -> str:
    clean = re.sub(
        r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}",
        "Bearer [redacted]",
        str(value or ""),
    )
    clean = re.sub(
        r"(?i)\b(password|secret|token|api[_-]?key|credential)\s*[:=]\s*[^\s,;]+",
        lambda match: f"{match.group(1)}=[redacted]",
        clean,
    )
    return clean


def _sanitize_url(value: str) -> str:
    try:
        parsed = urlsplit(str(value or ""))
    except Exception:
        return _redact_text(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return _redact_text(value)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _sanitize_context(value: Any, *, depth: int = 0, context_key: str = "") -> Any:
    if depth >= 5:
        return "[additional context omitted]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        lowered_key = str(context_key or "").lower()
        clean = _sanitize_url(value) if any(marker in lowered_key for marker in ("url", "uri", "href", "location")) else _redact_text(value)
        return clean[:1000]
    if isinstance(value, list):
        return [_sanitize_context(item, depth=depth + 1, context_key=context_key) for item in value[:50]]
    if isinstance(value, dict):
        clean: Dict[str, Any] = {}
        for index, (raw_key, child) in enumerate(value.items()):
            if index >= 80:
                clean["_additional_fields_omitted"] = len(value) - index
                break
            key = str(raw_key)[:100]
            lowered = key.lower()
            if any(marker in lowered for marker in _SENSITIVE_KEY_MARKERS):
                clean[key] = "[redacted]"
            else:
                clean[key] = _sanitize_context(child, depth=depth + 1, context_key=key)
        return clean
    return _redact_text(str(value))[:1000]


class SupportStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def _can_access_project(self, *, user_id: str, project_id: str) -> bool:
        if not project_id:
            return True
        connection = self.db.connect()
        try:
            row = connection.execute(
                """
                SELECT p.project_id
                FROM projects p
                LEFT JOIN project_members pm ON pm.project_id = p.project_id AND pm.user_id = ?
                WHERE p.project_id = ? AND p.deleted_at IS NULL AND (p.user_id = ? OR pm.user_id = ?)
                """,
                (user_id, project_id, user_id, user_id),
            ).fetchone()
            return row is not None
        finally:
            connection.close()

    def create_request(
        self,
        *,
        user_id: str,
        project_id: str = "",
        category: str,
        severity: str,
        summary: str,
        details: str = "",
        client_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_category = str(category or "other").strip().lower()
        normalized_severity = str(severity or "p2").strip().lower()
        clean_summary = _safe_text(summary, limit=240)
        clean_details = _safe_text(details, limit=8000)
        clean_project_id = _safe_text(project_id, limit=120)
        if normalized_category not in SUPPORT_CATEGORIES:
            raise ValueError("Choose a supported issue category.")
        if normalized_severity not in SUPPORT_SEVERITIES:
            raise ValueError("Severity must be P0, P1, P2, or P3.")
        if not clean_summary:
            raise ValueError("A short issue summary is required.")
        if clean_project_id and not self._can_access_project(user_id=user_id, project_id=clean_project_id):
            raise ValueError("That project is not available to this account.")

        now = _now()
        record = {
            "request_id": _new_id(),
            "user_id": user_id,
            "project_id": clean_project_id or None,
            "category": normalized_category,
            "severity": normalized_severity,
            "summary": clean_summary,
            "details": clean_details,
            "client_context": _sanitize_context(client_context or {}),
            "status": "received",
            "created_at": now,
            "updated_at": now,
        }
        connection = self.db.connect()
        try:
            connection.execute(
                """
                INSERT INTO support_requests (
                    request_id, user_id, project_id, category, severity, summary,
                    details, client_context_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["request_id"],
                    record["user_id"],
                    record["project_id"],
                    record["category"],
                    record["severity"],
                    record["summary"],
                    record["details"],
                    json.dumps(record["client_context"], sort_keys=True, separators=(",", ":")),
                    record["status"],
                    record["created_at"],
                    record["updated_at"],
                ),
            )
            connection.commit()
        finally:
            connection.close()
        return record

    def list_requests(self, *, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        connection = self.db.connect()
        try:
            rows = connection.execute(
                """
                SELECT request_id, user_id, project_id, category, severity, summary,
                       details, client_context_json, status, created_at, updated_at
                FROM support_requests
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (user_id, max(1, min(100, int(limit or 50)))),
            ).fetchall()
        finally:
            connection.close()
        return [
            {
                **dict(row),
                "client_context": json.loads(str(row["client_context_json"] or "{}")),
            }
            for row in rows
        ]

    def list_for_operations(
        self,
        *,
        status: str = "",
        severity: str = "",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        normalized_status = str(status or "").strip().lower()
        normalized_severity = str(severity or "").strip().lower()
        if normalized_status and normalized_status not in SUPPORT_STATUSES:
            raise ValueError("Choose a supported support-request status.")
        if normalized_severity and normalized_severity not in SUPPORT_SEVERITIES:
            raise ValueError("Severity must be P0, P1, P2, or P3.")
        query = """
                SELECT sr.request_id, sr.user_id, u.email AS user_email, sr.project_id,
                       sr.category, sr.severity, sr.summary, sr.status,
                       sr.created_at, sr.updated_at
                FROM support_requests sr
                JOIN users u ON u.user_id = sr.user_id
                WHERE (? = '' OR sr.status = ?)
                  AND (? = '' OR sr.severity = ?)
                ORDER BY
                    CASE sr.severity WHEN 'p0' THEN 0 WHEN 'p1' THEN 1 WHEN 'p2' THEN 2 ELSE 3 END,
                    sr.updated_at ASC
                LIMIT ?
                """
        connection = self.db.connect()
        try:
            rows = connection.execute(
                query,
                (
                    normalized_status,
                    normalized_status,
                    normalized_severity,
                    normalized_severity,
                    max(1, min(500, int(limit or 100))),
                ),
            ).fetchall()
        finally:
            connection.close()
        return [dict(row) for row in rows]

    def update_status(self, *, request_id: str, status: str) -> Dict[str, Any]:
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in SUPPORT_STATUSES:
            raise ValueError("Choose a supported support-request status.")
        now = _now()
        connection = self.db.connect()
        try:
            cursor = connection.execute(
                "UPDATE support_requests SET status = ?, updated_at = ? WHERE request_id = ?",
                (normalized_status, now, str(request_id or "").strip()),
            )
            if cursor.rowcount <= 0:
                raise ValueError("Support request not found.")
            connection.commit()
            row = connection.execute(
                """
                SELECT request_id, user_id, project_id, category, severity, summary,
                       details, client_context_json, status, created_at, updated_at
                FROM support_requests WHERE request_id = ?
                """,
                (str(request_id or "").strip(),),
            ).fetchone()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return {
            **dict(row),
            "client_context": json.loads(str(row["client_context_json"] or "{}")),
        }


__all__ = ["SUPPORT_CATEGORIES", "SUPPORT_SEVERITIES", "SUPPORT_STATUSES", "SupportStore"]
