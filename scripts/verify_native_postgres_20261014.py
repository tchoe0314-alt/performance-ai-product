"""Disposable native PostgreSQL probe; refuses hosted or unrelated databases."""
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

from backend.services.auth_store import AuthStore
from backend.services.canonical_canvas import with_canvas_snapshot
from backend.services.canonical_results import canvas_result_freshness
from backend.services.database import Database
from backend.services.project_store import ProjectStore

url = os.environ["CIVORA_TEST_POSTGRES_URL"]
target = urlsplit(url)
assert target.hostname in {"127.0.0.1", "localhost"}
assert target.path.startswith("/civora_pilot_test_")
checks = []
pools = []
with tempfile.TemporaryDirectory(prefix="civora-native-pg-probe-") as folder:
    db = Database(Path(folder) / "unused.db", database_url=url)
    pools.append(db)
    try:
        auth, store = AuthStore(db), ProjectStore(db)
        owner = auth.register_user(email="native-owner@example.test", password="Disposable-native-123", name="Synthetic native owner")["user"]
        viewer = auth.register_user(email="native-viewer@example.test", password="Disposable-native-123", name="Synthetic native viewer")["user"]
        source = with_canvas_snapshot({"manual_fields": {"units": "ft", "site_objects": [
            {"id": "office", "type": "building", "x": 20, "y": 30, "w": 40, "d": 50}]}})
        project = store.save_project(user_id=owner["user_id"], project_id=None, name="Native synthetic pilot", project_input=source)
        pid, uid = project["project_id"], owner["user_id"]
        store.invite_project_member(actor_user_id=uid, project_id=pid, email=viewer["email"], role="viewer")
        result = {"success": True, "message": "native", "final_plan": {"actions": [], "meta": {"quantities": {"area": 2000}}}}
        active = store.save_calculation_result(user_id=uid, project_id=pid, source_input=source, result=result)
        assert active["metadata"]["calculation_save_v1"]["disposition"] == "active"
        assert canvas_result_freshness(active, source)["status"] == "current"
        checks.append("native schema, owner registration, project and active calculation persistence")
        for value in [False, None, "true", "false", 1]:
            archived = store.save_calculation_result(user_id=uid, project_id=pid, source_input=source, result={"success": value})
            assert archived["metadata"]["calculation_save_v1"]["disposition"] == "archived"
            assert store.get_project(user_id=uid, project_id=pid)["latest_result"] == active
        history = store.list_calculation_history(user_id=uid, project_id=pid)
        assert sum(row["successful"] for row in history) == 1
        assert sum(row["is_active"] for row in history) == 1
        assert store.get_last_successful_calculation_at(user_id=uid, project_id=pid) is not None
        checks.append("PostgreSQL JSON boolean history, latest-success query and failed-result exclusion")
        try:
            store.save_calculation_result(user_id=viewer["user_id"], project_id=pid, source_input=source, result=result)
        except ValueError:
            pass
        else:
            raise AssertionError("Viewer saved a calculation")
        checks.append("viewer cannot save calculations")
        changed = deepcopy(source)
        changed["manual_fields"]["site_objects"][0]["x"] = 120
        changed = with_canvas_snapshot(changed)
        with ThreadPoolExecutor(max_workers=2) as workers:
            edit = workers.submit(store.save_project_shell, user_id=uid, project_id=pid, name="Changed native pilot", project_input=changed)
            late = workers.submit(store.save_calculation_result, user_id=uid, project_id=pid, source_input=source, result=result)
            edit.result(timeout=15)
            late.result(timeout=15)
        current = store.get_project(user_id=uid, project_id=pid)
        assert current["project_input"]["manual_fields"]["site_objects"][0]["x"] == 120
        assert not any(row["is_active"] for row in store.list_calculation_history(user_id=uid, project_id=pid))
        fresh = store.save_calculation_result(user_id=uid, project_id=pid, source_input=changed, result=result)
        stale = store.save_calculation_result(user_id=uid, project_id=pid, source_input=source, result=result)
        assert stale["metadata"]["calculation_save_v1"]["disposition"] == "archived"
        assert store.get_project(user_id=uid, project_id=pid)["latest_result"] == fresh
        checks.append("native row-lock edit/calculation race and late-result protection")
        connection = db.connect()
        try:
            connection.execute("SELECT 1 / 0")
        except Exception:
            pass
        else:
            raise AssertionError("Expected a failed PostgreSQL transaction")
        finally:
            connection.close()
        connection = db.connect()
        assert connection.execute("SELECT 1 AS ok").fetchone()["ok"] == 1
        version = connection.execute("SHOW server_version").fetchone()["server_version"]
        connection.close()
        checks.append("failed transaction reset and pooled connection reuse")
        reopened = Database(Path(folder) / "reopened.db", database_url=url)
        pools.append(reopened)
        restored = ProjectStore(reopened).get_project(user_id=uid, project_id=pid)
        assert restored["latest_result"] == fresh
        assert canvas_result_freshness(fresh, restored["project_input"])["status"] == "current"
        checks.append("fresh database pool reopens exact current result and input binding")
        print(json.dumps({"passed": True, "postgres_version": version, "checks": checks}, indent=2))
    finally:
        for database in pools:
            database._postgres_pool.close()
