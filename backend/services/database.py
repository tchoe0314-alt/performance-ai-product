from __future__ import annotations

from pathlib import Path
import sqlite3
import threading


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000;")
        connection.execute("PRAGMA foreign_keys = ON;")
        return connection

    def _initialize(self) -> None:
        schema = """
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS auth_tokens (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at REAL NOT NULL,
            last_used_at REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            session_id TEXT,
            tags_json TEXT NOT NULL,
            project_input_json TEXT NOT NULL,
            latest_result_json TEXT NOT NULL,
            session_state_json TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_projects_user_updated
        ON projects(user_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            project_id TEXT,
            payload_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            error_text TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_user_updated
        ON jobs(user_id, updated_at DESC);

        CREATE INDEX IF NOT EXISTS idx_jobs_status
        ON jobs(status, job_type);
        """

        with self._lock:
            connection = self.connect()
            try:
                connection.executescript(schema)
                connection.commit()
            finally:
                connection.close()
