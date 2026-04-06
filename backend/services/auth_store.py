from __future__ import annotations

from typing import Any, Dict, Optional
import hashlib
import os
import secrets
import sqlite3
import time
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


class AuthStore:
    def __init__(self, db: Database) -> None:
        self.db = db

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
            if "UNIQUE constraint failed" in str(exc):
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
            row = connection.execute(
                """
                SELECT u.user_id, u.email, u.name, u.created_at, u.updated_at
                FROM auth_tokens t
                JOIN users u ON u.user_id = t.user_id
                WHERE t.token = ?
                """,
                (token_value,),
            ).fetchone()
            if row is None:
                return None

            try:
                connection.execute(
                    "UPDATE auth_tokens SET last_used_at = ? WHERE token = ?",
                    (_now(), token_value),
                )
                connection.commit()
            except sqlite3.OperationalError as exc:
                # Avoid turning transient SQLite lock contention into auth 500s.
                if "locked" not in str(exc).lower():
                    raise
            return dict(row)
        finally:
            connection.close()

    def logout(self, token: str) -> None:
        token_value = str(token or "").strip()
        if not token_value:
            return
        connection = self.db.connect()
        try:
            connection.execute("DELETE FROM auth_tokens WHERE token = ?", (token_value,))
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
                (token, user_id, now, now),
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
