from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional
import os
import sqlite3
import threading


class _PostgresRow(dict):
    def __init__(self, columns: list[str], values: Iterable[Any]) -> None:
        pairs = list(zip(columns, values))
        super().__init__(pairs)
        self._columns = [name for name, _ in pairs]
        self._values = [value for _, value in pairs]

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class _PostgresResult:
    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor
        self.rowcount = int(getattr(cursor, "rowcount", 0) or 0)
        description = getattr(cursor, "description", None) or []
        self._columns = [str(item[0]) for item in description]

    def _wrap(self, row: Any) -> Any:
        if row is None:
            return None
        if not self._columns:
            return row
        return _PostgresRow(self._columns, row)

    def fetchone(self) -> Any:
        return self._wrap(self._cursor.fetchone())

    def fetchall(self) -> list[Any]:
        return [self._wrap(row) for row in self._cursor.fetchall()]


class _PostgresConnection:
    def __init__(self, connection: Any, *, pool: Any = None) -> None:
        self._connection = connection
        self._pool = pool
        self._closed = False

    def execute(self, sql: str, params: Iterable[Any] = ()) -> _PostgresResult:
        cursor = self._connection.cursor()
        cursor.execute(self._normalize_sql(sql), tuple(params or ()))
        return _PostgresResult(cursor)

    def executescript(self, script: str) -> None:
        cursor = self._connection.cursor()
        for statement in self._iter_statements(script):
            cursor.execute(statement)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._pool is not None:
            self._pool.putconn(self._connection)
            return
        self._connection.close()

    @staticmethod
    def _normalize_sql(sql: str) -> str:
        return str(sql or "").replace("?", "%s")

    @classmethod
    def _iter_statements(cls, script: str) -> list[str]:
        statements: list[str] = []
        for raw in str(script or "").split(";"):
            statement = raw.strip()
            if not statement:
                continue
            upper = statement.upper()
            if upper.startswith("PRAGMA "):
                continue
            statements.append(statement)
        return statements


class Database:
    def __init__(self, db_path: Path, database_url: Optional[str] = None) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.database_url = str(database_url or os.getenv("DATABASE_URL") or "").strip()
        self.storage_kind = "postgres" if self.database_url.startswith(("postgres://", "postgresql://")) else "sqlite"
        self._postgres_pool: Any = None
        self._initialize()
        if self.storage_kind == "postgres":
            self._initialize_postgres_pool()

    @staticmethod
    def _database_connect_timeout() -> float:
        raw_timeout = str(os.getenv("CIVORA_DATABASE_CONNECT_TIMEOUT_SECONDS") or "10").strip()
        try:
            return max(1.0, float(raw_timeout or 10))
        except Exception:
            return 10.0

    def _initialize_postgres_pool(self) -> None:
        try:
            from psycopg_pool import ConnectionPool
        except ImportError as exc:
            raise RuntimeError(
                "Postgres storage requires psycopg pooling. Install psycopg[binary,pool]."
            ) from exc
        raw_min = str(os.getenv("CIVORA_DATABASE_POOL_MIN_SIZE") or "1").strip()
        raw_max = str(os.getenv("CIVORA_DATABASE_POOL_MAX_SIZE") or "4").strip()
        try:
            min_size = max(1, int(raw_min or 1))
        except Exception:
            min_size = 1
        try:
            max_size = max(min_size, int(raw_max or 4))
        except Exception:
            max_size = max(min_size, 4)
        connect_timeout = self._database_connect_timeout()
        self._postgres_pool = ConnectionPool(
            self.database_url,
            kwargs={"autocommit": False, "connect_timeout": connect_timeout},
            min_size=min_size,
            max_size=max_size,
            open=True,
            timeout=max(connect_timeout, 10.0),
            name="civora-api",
        )
        self._postgres_pool.wait(timeout=max(connect_timeout * 2.0, 30.0))

    def connect(self) -> Any:
        if self.storage_kind == "postgres":
            try:
                import psycopg
            except ImportError as exc:
                raise RuntimeError(
                    "Postgres storage requires psycopg. Add psycopg[binary] to backend dependencies."
                ) from exc
            connect_timeout = self._database_connect_timeout()
            if self._postgres_pool is not None:
                connection = self._postgres_pool.getconn(timeout=max(connect_timeout, 10.0))
                return _PostgresConnection(connection, pool=self._postgres_pool)
            else:
                connection = psycopg.connect(
                    self.database_url,
                    autocommit=False,
                    connect_timeout=connect_timeout,
                )
            return _PostgresConnection(connection)

        connection = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000;")
        connection.execute("PRAGMA foreign_keys = ON;")
        return connection

    def _initialize(self) -> None:
        sqlite_schema = """
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
            organization_id TEXT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            session_id TEXT,
            has_result INTEGER NOT NULL DEFAULT 0,
            tags_json TEXT NOT NULL,
            project_input_json TEXT NOT NULL,
            latest_result_json TEXT NOT NULL,
            session_state_json TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_projects_user_updated
        ON projects(user_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS organizations (
            organization_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_by_user_id TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            metadata_json TEXT NOT NULL,
            FOREIGN KEY (created_by_user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS organization_members (
            organization_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            invited_email TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (organization_id, user_id),
            FOREIGN KEY (organization_id) REFERENCES organizations(organization_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_organization_members_user
        ON organization_members(user_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS project_members (
            project_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            invited_email TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (project_id, user_id),
            FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_project_members_user
        ON project_members(user_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS project_invites (
            invite_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            email TEXT NOT NULL,
            role TEXT NOT NULL,
            invited_by_user_id TEXT NOT NULL,
            accepted_by_user_id TEXT,
            status TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
            FOREIGN KEY (invited_by_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (accepted_by_user_id) REFERENCES users(user_id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_project_invites_project
        ON project_invites(project_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS access_audit_log (
            audit_id TEXT PRIMARY KEY,
            organization_id TEXT,
            project_id TEXT,
            actor_user_id TEXT NOT NULL,
            target_user_id TEXT,
            target_email TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            metadata_json TEXT NOT NULL,
            FOREIGN KEY (organization_id) REFERENCES organizations(organization_id) ON DELETE SET NULL,
            FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
            FOREIGN KEY (actor_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (target_user_id) REFERENCES users(user_id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_access_audit_project
        ON access_audit_log(project_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            project_id TEXT,
            stage TEXT NOT NULL DEFAULT '',
            stage_detail TEXT NOT NULL DEFAULT '',
            progress INTEGER NOT NULL DEFAULT 0,
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

        postgres_schema = """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL
        );

        CREATE TABLE IF NOT EXISTS auth_tokens (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            created_at DOUBLE PRECISION NOT NULL,
            last_used_at DOUBLE PRECISION NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            organization_id TEXT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL,
            session_id TEXT,
            has_result INTEGER NOT NULL DEFAULT 0,
            tags_json TEXT NOT NULL,
            project_input_json TEXT NOT NULL,
            latest_result_json TEXT NOT NULL,
            session_state_json TEXT NOT NULL,
            metadata_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_projects_user_updated
        ON projects(user_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS organizations (
            organization_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_by_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL,
            metadata_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS organization_members (
            organization_id TEXT NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            invited_email TEXT NOT NULL DEFAULT '',
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (organization_id, user_id)
        );

        CREATE INDEX IF NOT EXISTS idx_organization_members_user
        ON organization_members(user_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS project_members (
            project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            invited_email TEXT NOT NULL DEFAULT '',
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (project_id, user_id)
        );

        CREATE INDEX IF NOT EXISTS idx_project_members_user
        ON project_members(user_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS project_invites (
            invite_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            role TEXT NOT NULL,
            invited_by_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            accepted_by_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
            status TEXT NOT NULL,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_project_invites_project
        ON project_invites(project_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS access_audit_log (
            audit_id TEXT PRIMARY KEY,
            organization_id TEXT REFERENCES organizations(organization_id) ON DELETE SET NULL,
            project_id TEXT REFERENCES projects(project_id) ON DELETE CASCADE,
            actor_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            target_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
            target_email TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT '',
            created_at DOUBLE PRECISION NOT NULL,
            metadata_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_access_audit_project
        ON access_audit_log(project_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL,
            project_id TEXT REFERENCES projects(project_id) ON DELETE SET NULL,
            stage TEXT NOT NULL DEFAULT '',
            stage_detail TEXT NOT NULL DEFAULT '',
            progress INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            error_text TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_user_updated
        ON jobs(user_id, updated_at DESC);

        CREATE INDEX IF NOT EXISTS idx_jobs_status
        ON jobs(status, job_type);
        """

        with self._lock:
            connection = self.connect()
            try:
                schema = postgres_schema if self.storage_kind == "postgres" else sqlite_schema
                connection.executescript(schema)
                connection.commit()
            finally:
                connection.close()
        self._ensure_jobs_runtime_columns()
        self._ensure_project_summary_columns()
        self._ensure_team_access_columns()

    def _get_table_columns(self, table_name: str) -> set[str]:
        connection = self.connect()
        try:
            if self.storage_kind == "postgres":
                rows = connection.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = ?
                    """,
                    (table_name,),
                ).fetchall()
                return {str(row["column_name"]) for row in rows}
            rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
            return {str(row["name"]) for row in rows}
        finally:
            connection.close()

    def _ensure_jobs_runtime_columns(self) -> None:
        with self._lock:
            connection = self.connect()
            try:
                columns = self._get_table_columns("jobs")
                if self.storage_kind == "postgres":
                    if "stage" not in columns:
                        connection.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS stage TEXT NOT NULL DEFAULT ''")
                    if "stage_detail" not in columns:
                        connection.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS stage_detail TEXT NOT NULL DEFAULT ''")
                    if "progress" not in columns:
                        connection.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS progress INTEGER NOT NULL DEFAULT 0")
                else:
                    if "stage" not in columns:
                        connection.execute("ALTER TABLE jobs ADD COLUMN stage TEXT NOT NULL DEFAULT ''")
                    if "stage_detail" not in columns:
                        connection.execute("ALTER TABLE jobs ADD COLUMN stage_detail TEXT NOT NULL DEFAULT ''")
                    if "progress" not in columns:
                        connection.execute("ALTER TABLE jobs ADD COLUMN progress INTEGER NOT NULL DEFAULT 0")
                connection.commit()
            finally:
                connection.close()

    def _ensure_project_summary_columns(self) -> None:
        with self._lock:
            connection = self.connect()
            try:
                columns = self._get_table_columns("projects")
                if self.storage_kind == "postgres":
                    if "has_result" not in columns:
                        connection.execute(
                            "ALTER TABLE projects ADD COLUMN IF NOT EXISTS has_result INTEGER NOT NULL DEFAULT 0"
                        )
                else:
                    if "has_result" not in columns:
                        connection.execute(
                            "ALTER TABLE projects ADD COLUMN has_result INTEGER NOT NULL DEFAULT 0"
                        )
                connection.execute(
                    """
                    UPDATE projects
                    SET has_result = CASE
                        WHEN latest_result_json IS NOT NULL
                             AND latest_result_json != ''
                             AND latest_result_json != '{}'
                        THEN 1
                        ELSE 0
                    END
                    """
                )
                connection.commit()
            finally:
                connection.close()

    def _ensure_team_access_columns(self) -> None:
        with self._lock:
            connection = self.connect()
            try:
                columns = self._get_table_columns("projects")
                if self.storage_kind == "postgres":
                    if "organization_id" not in columns:
                        connection.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS organization_id TEXT")
                else:
                    if "organization_id" not in columns:
                        connection.execute("ALTER TABLE projects ADD COLUMN organization_id TEXT")
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_projects_organization_updated
                    ON projects(organization_id, updated_at DESC)
                    """
                )
                connection.commit()
            finally:
                connection.close()
