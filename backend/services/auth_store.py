from __future__ import annotations

from typing import Any, Dict, Optional
import hashlib
import os
import secrets
import time
import math
import uuid

from .database import Database


def _now() -> float:
    return time.time()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _hash_password(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        200_000,
    ).hex()


def _session_digest(token: str) -> str:
    return "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def _is_duplicate_email_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "unique constraint failed",
            "duplicate key value violates unique constraint",
            "users_email",
            "users_email_key",
        )
    )


class AuthStore:
    def __init__(self, db: Database, *, session_ttl_seconds: float = 7 * 24 * 3600, session_idle_seconds: float = 24 * 3600) -> None:
        if type(session_ttl_seconds) not in (int, float) or not math.isfinite(session_ttl_seconds) or session_ttl_seconds <= 0:
            raise ValueError("Session lifetime must be finite and positive.")
        self.db = db
        self.session_ttl_seconds = float(session_ttl_seconds)
        if type(session_idle_seconds) not in (int, float) or not math.isfinite(session_idle_seconds) or session_idle_seconds <= 0:
            raise ValueError("Session idle lifetime must be finite and positive.")
        self.session_idle_seconds = float(session_idle_seconds)

    def register_user(self, *, email: str, password: str, name: str) -> Dict[str, Any]:
        email_norm = str(email or "").strip().lower()
        if not email_norm:
            raise ValueError("Email is required.")
        if len(password or "") < 8:
            raise ValueError("Password must be at least 8 characters.")
        display_name = str(name or "").strip() or email_norm.split("@")[0]

        salt = os.urandom(16).hex()
        password_hash = _hash_password(password, salt)
        now = _now()
        user = {
            "user_id": _new_id("user"),
            "email": email_norm,
            "name": display_name,
            "password_salt": salt,
            "password_hash": password_hash,
            "created_at": now,
            "updated_at": now,
        }

        connection = self.db.connect()
        try:
            connection.execute(
                """
                INSERT INTO users (user_id, email, name, password_salt, password_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user["user_id"],
                    user["email"],
                    user["name"],
                    user["password_salt"],
                    user["password_hash"],
                    user["created_at"],
                    user["updated_at"],
                ),
            )
            connection.commit()
        except Exception as exc:
            connection.rollback()
            if _is_duplicate_email_error(exc):
                raise ValueError("That email is already registered.") from exc
            raise
        finally:
            connection.close()

        token = self._create_token(user["user_id"])
        return {
            "user": self._public_user_dict(user),
            "token": token,
        }

    def login(self, *, email: str, password: str) -> Dict[str, Any]:
        user = self._get_user_by_email(email)
        if user is None:
            raise ValueError("Invalid email or password.")

        expected_hash = _hash_password(password, user["password_salt"])
        if not secrets.compare_digest(expected_hash, user["password_hash"]):
            raise ValueError("Invalid email or password.")

        token = self._create_token(user["user_id"])
        return {
            "user": self._public_user_dict(user),
            "token": token,
        }

    def authenticate_token(self, token: str) -> Optional[Dict[str, Any]]:
        token_value = str(token or "").strip()
        if not token_value:
            return None

        connection = self.db.connect()
        try:
            now = _now()
            row = connection.execute(
                """
                SELECT u.user_id, u.email, u.name, u.created_at, u.updated_at
                FROM auth_tokens t
                JOIN users u ON u.user_id = t.user_id
                WHERE t.token = ? AND t.created_at > ? AND t.created_at <= ?
                    AND t.last_used_at > ? AND t.last_used_at <= ?
                """,
                (_session_digest(token_value), now - self.session_ttl_seconds, now,
                 now - self.session_idle_seconds, now),
            ).fetchone()
            if row is None:
                return None

            try:
                connection.execute(
                    "UPDATE auth_tokens SET last_used_at = ? WHERE token = ?",
                    (_now(), _session_digest(token_value)),
                )
                connection.commit()
            except Exception as exc:
                # Avoid turning transient storage lock contention into auth 500s.
                if "locked" not in str(exc).lower():
                    raise
            return dict(row)
        finally:
            connection.close()

    def revoke_all_sessions(self, *, user_id: str, password: str) -> None:
        if not self.verify_password(user_id=user_id, password=password):
            raise ValueError("Password confirmation failed.")
        connection = self.db.connect()
        try:
            connection.execute("DELETE FROM auth_tokens WHERE user_id = ?", (user_id,))
            connection.commit()
        finally:
            connection.close()

    def rotate_session(self, token: str) -> str:
        """Single-winner rotation; preserve original absolute session lifetime."""
        now = _now()
        replacement = secrets.token_urlsafe(32)
        connection = self.db.connect()
        try:
            cursor = connection.execute(
                """UPDATE auth_tokens SET token = ?, last_used_at = ?
                WHERE token = ? AND created_at > ? AND created_at <= ?
                    AND last_used_at > ? AND last_used_at <= ?""",
                (_session_digest(replacement), now, _session_digest(str(token or "")),
                 now-self.session_ttl_seconds, now, now-self.session_idle_seconds, now),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise ValueError("Session is invalid or expired.")
            connection.commit()
            return replacement
        finally:
            connection.close()

    def verify_password(self, *, user_id: str, password: str) -> bool:
        connection = self.db.connect()
        try:
            row = connection.execute(
                """
                SELECT password_salt, password_hash
                FROM users
                WHERE user_id = ?
                """,
                (str(user_id or ""),),
            ).fetchone()
        finally:
            connection.close()
        if row is None or not str(password or ""):
            return False
        candidate = _hash_password(password, row["password_salt"])
        return secrets.compare_digest(candidate, row["password_hash"])

    def logout(self, token: str) -> None:
        token_value = str(token or "").strip()
        if not token_value:
            return
        connection = self.db.connect()
        try:
            connection.execute("DELETE FROM auth_tokens WHERE token = ?", (_session_digest(token_value),))
            connection.commit()
        finally:
            connection.close()

    def _create_token(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = _now()
        connection = self.db.connect()
        try:
            connection.execute(
                "INSERT INTO auth_tokens (token, user_id, created_at, last_used_at) VALUES (?, ?, ?, ?)",
                (_session_digest(token), user_id, now, now),
            )
            connection.commit()
        finally:
            connection.close()
        return token

    def _get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        email_norm = str(email or "").strip().lower()
        connection = self.db.connect()
        try:
            row = connection.execute(
                """
                SELECT user_id, email, name, password_salt, password_hash, created_at, updated_at
                FROM users
                WHERE email = ?
                """,
                (email_norm,),
            ).fetchone()
            return None if row is None else dict(row)
        finally:
            connection.close()

    def _public_user_dict(self, user: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user["name"],
            "created_at": user["created_at"],
            "updated_at": user["updated_at"],
        }
