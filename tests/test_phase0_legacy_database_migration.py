import json
import sqlite3

from backend.services.database import Database


def test_legacy_sqlite_upgrade_preserves_project_geometry_results_and_jobs(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    path = tmp_path / "legacy.sqlite3"
    geometry = json.dumps({"manual_fields": {"units": "ft", "site_objects": [
        {"id": "legacy-road", "type": "road", "geometry": [[-25, 10], [40, 65]], "rotation": 17},
    ]}})
    result = json.dumps({"review_only": True, "legacy_marker": "preserve exactly"})
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE users (
                user_id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                password_salt TEXT NOT NULL, password_hash TEXT NOT NULL,
                created_at REAL NOT NULL, updated_at REAL NOT NULL
            );
            CREATE TABLE projects (
                project_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL,
                description TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL,
                session_id TEXT, tags_json TEXT NOT NULL, project_input_json TEXT NOT NULL,
                latest_result_json TEXT NOT NULL, session_state_json TEXT NOT NULL, metadata_json TEXT NOT NULL
            );
            CREATE TABLE jobs (
                job_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, job_type TEXT NOT NULL,
                status TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL,
                project_id TEXT, payload_json TEXT NOT NULL, result_json TEXT NOT NULL, error_text TEXT
            );
            INSERT INTO users VALUES ('owner', 'fixture@example.invalid', 'Fixture', 'salt', 'hash', 1, 2);
            INSERT INTO jobs VALUES ('old-job', 'owner', 'plan', 'completed', 1, 2, 'old-project', '{}', '{}', NULL);
        """)
        connection.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           ("old-project", "owner", "Legacy", "Keep", 1, 2, None, "[]", geometry, result, "{}", "{}"))
        connection.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           ("empty-project", "owner", "Empty", "Keep", 1, 2, None, "[]", "{}", "{}", "{}", "{}"))

    for _ in range(2):
        database = Database(path)
        connection = database.connect()
        try:
            project = connection.execute("SELECT * FROM projects WHERE project_id = ?", ("old-project",)).fetchone()
            assert project["project_input_json"] == geometry
            assert project["latest_result_json"] == result
            assert project["user_id"] == "owner"
            assert project["has_result"] == 1
            assert project["organization_id"] is None
            assert project["archived_at"] is None and project["deleted_at"] is None
            assert connection.execute("SELECT has_result FROM projects WHERE project_id = ?", ("empty-project",)).fetchone()[0] == 0
            job = connection.execute("SELECT * FROM jobs WHERE job_id = ?", ("old-job",)).fetchone()
            assert job["status"] == "completed" and job["project_id"] == "old-project"
            assert job["stage"] == "" and job["stage_detail"] == "" and job["progress"] == 0
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            connection.close()
