"""C01a: real synthetic database and HTTP routes, never production state."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import threading

import pytest

from backend.planning.customer_templates import sample_customer_template, GLOBAL_CUSTOMER_TEMPLATE_MANAGER
from backend.planning.utility_catalogs import sample_catalog, GLOBAL_UTILITY_CATALOG_MANAGER
from backend.services.auth_store import AuthStore
from backend.services.catalog_library_store import CatalogLibraryStore, LibraryAccessError
from backend.services.database import Database
from backend.services.project_store import ProjectStore


def template(item_id="firm-private"):
    value = sample_customer_template()
    value.update(template_id=item_id, name="Private synthetic standard", firm_id="not-an-access-grant")
    return value


def pipe(item_id="firm-private", sizes=None):
    value = sample_catalog()["pipes"][0]
    value.update(item_id=item_id, material="PRIVATE", sizes_in=sizes or [17, 19])
    return value


@pytest.fixture
def state(tmp_path):
    db = Database(tmp_path / "libraries.db", database_url="")
    return make_state(db)


def make_state(db):
    """Same synthetic actors and assertions for each explicitly selected engine."""
    auth = AuthStore(db)
    accounts = {role: auth.register_user(email=f"{role}@synthetic.invalid", password="synthetic-only-password", name=role)
                for role in ("owner", "admin", "editor", "reviewer", "viewer", "stranger")}
    users = {role: account["user"]["user_id"] for role, account in accounts.items()}
    projects = ProjectStore(db)
    project = projects.save_project(user_id=users["owner"], project_id=None, name="Synthetic scoped library")
    org = projects.ensure_default_organization(user_id=users["owner"])["organization_id"]
    connection = db.connect()
    try:
        for role in ("admin", "editor", "reviewer", "viewer"):
            connection.execute("INSERT INTO project_members(project_id,user_id,role,invited_email,created_at,updated_at) VALUES(?,?,?,?,0,0)",
                               (project["project_id"], users[role], role, ""))
            connection.execute("INSERT INTO organization_members(organization_id,user_id,role,invited_email,created_at,updated_at) VALUES(?,?,?,?,0,0)",
                               (org, users[role], role, ""))
        connection.commit()
    finally:
        connection.close()
    return db, CatalogLibraryStore(db), users, accounts, {"organization": org, "project": project["project_id"]}


def contents(db):
    connection = db.connect()
    try:
        return [[tuple(row[key] for key in row.keys()) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1,2,3").fetchall()]
                for table in ("catalog_libraries", "catalog_library_versions", "catalog_template_selections")]
    finally:
        connection.close()


@pytest.mark.parametrize("kind,operation,payload", [
    ("templates", "import_template", template()), ("utilities", "add_pipe_catalog", pipe()),
])
def test_default_private_and_same_id_isolation(state, kind, operation, payload):
    db, store, users, _, _ = state
    first = store.run(user_id=users["owner"], kind=kind, operation=operation, payload=payload)
    assert first["success"] and first["library"]["revision"] == 1
    other = store.run(user_id=users["stranger"], kind=kind, operation="snapshot")
    assert "firm-private" not in json.dumps(other)
    before = contents(db)
    for action in ("snapshot", operation):
        with pytest.raises(LibraryAccessError):
            store.run(user_id=users["stranger"], kind=kind, operation=action,
                      payload=payload if action == operation else None, scope_id=users["owner"])
    assert contents(db) == before
    changed = deepcopy(payload)
    changed.update({"name": "Unrelated firm's distinct template"} if kind == "templates" else {"sizes_in": [29]})
    owner_before = store.run(user_id=users["owner"], kind=kind, operation="snapshot")
    second = store.run(user_id=users["stranger"], kind=kind, operation=operation, payload=changed)
    assert second["success"] and second["library"]["revision"] == 1
    assert first["library"]["scope_id"] != second["library"]["scope_id"]
    assert store.run(user_id=users["owner"], kind=kind, operation="snapshot") == owner_before


@pytest.mark.parametrize("scope", ["organization", "project"])
@pytest.mark.parametrize("role", ["owner", "admin", "editor", "reviewer", "viewer", "stranger"])
def test_shared_role_matrix_and_denied_nonmutation(state, scope, role):
    db, store, users, _, scopes = state
    args = dict(scope_type=scope, scope_id=scopes[scope], kind="utilities", user_id=users[role])
    before = contents(db)
    if role == "stranger":
        with pytest.raises(LibraryAccessError):
            store.run(operation="snapshot", **args)
    else:
        assert store.run(operation="snapshot", **args)["library"]["scope_id"] == scopes[scope]
    allowed = role in {"owner", "admin"} or (role == "editor" and scope == "project")
    if allowed:
        assert store.run(operation="add_pipe_catalog", payload=pipe(), **args)["success"]
        assert "firm-private" in json.dumps(store.run(operation="snapshot", **args))
    else:
        with pytest.raises(LibraryAccessError):
            store.run(operation="add_pipe_catalog", payload=pipe(), **args)
        assert contents(db) == before


def test_template_selection_personal_and_project_editor_shared(state):
    db, store, users, _, scopes = state
    for scope in ("organization", "project"):
        args = dict(kind="templates", scope_type=scope, scope_id=scopes[scope])
        assert store.run(user_id=users["owner"], operation="import_template", payload=template(), **args)["success"]
        actor = "viewer" if scope == "organization" else "editor"
        selected = store.run(user_id=users[actor], operation="activate", template_id="firm-private", **args)
        assert selected["success"] and selected["library"]["selection_revision"] == 1
        owner = store.run(user_id=users["owner"], operation="snapshot", **args)
        assert (owner["active_template_id"] == "firm-private") == (scope == "project")
        before = contents(db)
        with pytest.raises(LibraryAccessError):
            store.run(user_id=users["stranger"], operation="activate", template_id="firm-private", **args)
        if scope == "project":
            with pytest.raises(LibraryAccessError):
                store.run(user_id=users["viewer"], operation="activate", template_id="firm-private", **args)
        assert contents(db) == before
    own = dict(user_id=users["owner"], kind="templates")
    store.run(operation="import_template", payload=template(), **own)
    store.run(operation="activate", template_id="firm-private", **own)
    assert store.run(operation="snapshot", **own)["active_template_id"] == "firm-private"
    assert store.run(user_id=users["stranger"], kind="templates", operation="snapshot")["active_template_id"] != "firm-private"


def test_immutable_public_seeds_and_invalid_requests_rollback(state):
    db, store, users, _, _ = state
    for kind, operation, payload in (("templates", "import_template", sample_customer_template()),
                                      ("utilities", "add_pipe_catalog", sample_catalog()["pipes"][0]),
                                      ("utilities", "add_part_catalog", sample_catalog()["parts"][0])):
        before = contents(db)
        for scope in ({}, {"scope_type": "public"}):
            with pytest.raises(LibraryAccessError):
                store.run(user_id=users["owner"], kind=kind, operation=operation, payload=payload, **scope)
        assert contents(db) == before
        public = store.run(user_id=users["owner"], kind=kind, operation="snapshot", scope_type="public")
        assert public["library"]["scope_id"] == "reference"
    before = contents(db)
    rejected = store.run(user_id=users["owner"], kind="utilities", operation="add_pipe_catalog", payload={"item_id": "bad"})
    assert not rejected["success"]
    assert contents(db) == before
    with pytest.raises(LibraryAccessError):
        store.run(user_id=users["owner"], kind="templates", operation="snapshot", scope_type="firm", scope_id="not-an-access-grant")


def test_restart_versions_and_two_independent_store_connections(state):
    db, store, users, _, _ = state
    args = dict(user_id=users["owner"], kind="utilities")
    first = store.run(operation="add_pipe_catalog", payload=pipe(sizes=[17]), **args)
    historical = contents(db)[1]
    reopen = getattr(db, "_c01a_test_reopen", lambda: Database(db.db_path, database_url=db.database_url))
    second_db = reopen()
    reopened = CatalogLibraryStore(second_db)
    assert reopened.run(operation="snapshot", **args)["library"] == first["library"]
    barrier = threading.Barrier(2)
    def add(pair):
        worker, item_id = pair
        barrier.wait(timeout=5)
        return worker.run(operation="add_pipe_catalog", payload=pipe(item_id), **args)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(add, [(store, "concurrent-a"), (reopened, "concurrent-b")]))
    assert sorted(result["library"]["revision"] for result in results) == [2, 3]
    final = reopened.run(operation="snapshot", **args)
    assert {item["item_id"] for item in final["pipes"]} >= {"firm-private", "concurrent-a", "concurrent-b"}
    versions = contents(db)[1]
    assert versions[0] == historical[0]
    for row in versions:
        assert hashlib.sha256(row[4].encode()).hexdigest() == row[5]


def test_unknown_global_imports_not_adopted_and_never_destroyed(state, monkeypatch):
    _, store, users, _, _ = state
    legacy_templates = deepcopy(GLOBAL_CUSTOMER_TEMPLATE_MANAGER.templates)
    legacy_templates["unknown-legacy-owner"] = template("unknown-legacy-owner")
    monkeypatch.setattr(GLOBAL_CUSTOMER_TEMPLATE_MANAGER, "templates", legacy_templates)
    legacy_utilities = deepcopy(GLOBAL_UTILITY_CATALOG_MANAGER.catalog)
    legacy_utilities["pipes"].append(pipe("unknown-legacy-owner"))
    monkeypatch.setattr(GLOBAL_UTILITY_CATALOG_MANAGER, "catalog", legacy_utilities)
    for kind in ("templates", "utilities"):
        assert "unknown-legacy-owner" not in json.dumps(store.run(user_id=users["owner"], kind=kind, operation="snapshot"))
    assert "unknown-legacy-owner" in GLOBAL_CUSTOMER_TEMPLATE_MANAGER.templates
    assert GLOBAL_UTILITY_CATALOG_MANAGER.catalog == legacy_utilities


@pytest.mark.parametrize("scope", ["organization", "project"])
def test_removed_members_lose_read_export_write_and_selection(state, scope):
    db, store, users, _, scopes = state
    args = dict(kind="templates", scope_type=scope, scope_id=scopes[scope])
    store.run(user_id=users["owner"], operation="import_template", payload=template(), **args)
    assert store.run(user_id=users["editor"], operation="snapshot", **args)
    connection = db.connect()
    try:
        if scope == "organization":
            connection.execute("DELETE FROM organization_members WHERE organization_id = ? AND user_id = ?", (scopes[scope], users["editor"]))
        else:
            connection.execute("DELETE FROM project_members WHERE project_id = ? AND user_id = ?", (scopes[scope], users["editor"]))
        connection.commit()
    finally:
        connection.close()
    before = contents(db)
    for operation, kwargs in (("snapshot", {}), ("export_json", {}), ("activate", {"template_id": "firm-private"}),
                              ("import_template", {"payload": template("denied")})):
        with pytest.raises(LibraryAccessError):
            store.run(user_id=users["editor"], operation=operation, **kwargs, **args)
    assert contents(db) == before


def test_account_export_and_fk_deletion_preserve_other_scopes(state, tmp_path):
    from backend.services.data_lifecycle import DataLifecycleService, ACCOUNT_DELETE_CONFIRMATION
    db, store, users, _, scopes = state
    for role in ("owner", "stranger"):
        store.run(user_id=users[role], kind="templates", operation="import_template", payload=template(role))
        store.run(user_id=users[role], kind="templates", operation="activate", template_id=role)
    store.run(user_id=users["owner"], kind="utilities", operation="add_pipe_catalog", payload=pipe(), scope_type="project", scope_id=scopes["project"])
    root = tmp_path / "lifecycle"
    lifecycle = DataLifecycleService(db, storage_dir=root, upload_dir=root / "uploads", artifact_dir=root / "artifacts")
    exported = lifecycle.account_export(user_id=users["stranger"])["data"]
    assert len(exported["catalog_libraries"]) == 1
    assert len(exported["catalog_library_versions"]) == 1
    assert len(exported["catalog_template_selections"]) == 1
    assert exported["catalog_libraries"][0]["scope_id"] == users["stranger"]
    before = store.run(user_id=users["owner"], kind="templates", operation="snapshot")
    assert lifecycle.delete_account(user_id=users["stranger"], confirmation=ACCOUNT_DELETE_CONFIRMATION)["account_deleted"]
    assert store.run(user_id=users["owner"], kind="templates", operation="snapshot") == before
    assert all(users["stranger"] not in json.dumps(rows) for rows in contents(db))
    # Deleting a project follows existing project-retention/deletion policy;
    # when its row is purged the scope and history must not be orphaned.
    connection = db.connect()
    try:
        connection.execute("DELETE FROM projects WHERE project_id = ?", (scopes["project"],))
        connection.commit()
        assert not connection.execute("SELECT * FROM catalog_libraries WHERE owner_project_id = ?", (scopes["project"],)).fetchall()
        assert not connection.execute("SELECT * FROM catalog_library_versions WHERE scope_id = ?", (scopes["project"],)).fetchall()
    finally:
        connection.close()


def test_failed_persistence_rolls_back_snapshot_and_history(state, monkeypatch):
    db, store, users, _, _ = state
    args = dict(user_id=users["owner"], kind="utilities", operation="add_pipe_catalog")
    store.run(payload=pipe(), **args)
    before = contents(db)
    connect = db.connect
    class FailingConnection:
        def __init__(self):
            self.inner = connect()
        def execute(self, sql, params=()):
            if "INSERT INTO catalog_library_versions" in sql:
                raise OSError("Synthetic history write failure")
            return self.inner.execute(sql, params)
        def __getattr__(self, key):
            return getattr(self.inner, key)
    with monkeypatch.context() as patch:
        patch.setattr(db, "connect", FailingConnection)
        with pytest.raises(OSError, match="Synthetic history"):
            store.run(payload=pipe("must-not-persist"), **args)
    assert contents(db) == before


def test_two_processes_persist_selection_and_merge_distinct_imports(state):
    """Forked worker has a new store/connection, not a manager shared in RAM."""
    import os
    db, store, users, _, _ = state
    args = dict(user_id=users["owner"], kind="templates")
    store.run(operation="import_template", payload=template("worker-selected"), **args)
    # No DB connection is held at fork. A pipe releases the worker while the
    # parent writes; every mutation still opens its own transactional connection.
    read_fd, write_fd = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(write_fd)
        try:
            os.read(read_fd, 1)
            worker = CatalogLibraryStore(db)
            assert worker.run(operation="import_template", payload=template("child-import"), **args)["success"]
            assert worker.run(operation="activate", template_id="worker-selected", **args)["success"]
            os._exit(0)
        except BaseException:
            os._exit(1)
    os.close(read_fd)
    try:
        os.write(write_fd, b"1")
        assert store.run(operation="import_template", payload=template("parent-import"), **args)["success"]
    finally:
        os.close(write_fd)
        _, status = os.waitpid(child, 0)
    assert os.waitstatus_to_exitcode(status) == 0
    reopened = CatalogLibraryStore(Database(db.db_path, database_url=""))
    final = reopened.run(operation="snapshot", **args)
    assert final["active_template_id"] == "worker-selected"
    assert final["library"]["revision"] == 3
    assert {item["template_id"] for item in final["templates"]} >= {"worker-selected", "parent-import", "child-import"}


def test_http_real_auth_private_exports_mutations_and_shared_permissions(state, monkeypatch):
    # The runner must set a fresh storage root BEFORE importing the API.
    from fastapi.testclient import TestClient
    import importlib
    api = importlib.import_module("backend.api.app")
    db, store, users, accounts, scopes = state
    monkeypatch.setattr(api, "CATALOG_LIBRARY_STORE", store)
    monkeypatch.setattr(api, "AUTH_STORE", AuthStore(db))
    from backend.services.rate_limit_store import RateLimitStore
    monkeypatch.setattr(api, "RATE_LIMIT_STORE", RateLimitStore(db))
    client = TestClient(api.app)
    def headers(role):
        return {"Authorization": f"Bearer {accounts[role]['token']}"}
    assert client.get("/api/customer-templates").status_code == 401
    assert client.post("/api/customer-templates/import", json=template(), headers=headers("owner")).status_code == 200
    assert client.post("/api/utility-catalogs/pipes", json=pipe(), headers=headers("owner")).status_code == 200
    before = contents(db)
    for path in ("/api/customer-templates", "/api/customer-templates/export", "/api/customer-templates/missing?template_id=firm-private",
                 "/api/utility-catalogs", "/api/utility-catalogs/pipe-sizes?material=PRIVATE"):
        response = client.get(path, headers=headers("stranger"))
        assert response.status_code == 200
        if "/missing" not in path:
            assert "firm-private" not in response.text
        response = client.get(path, params={"scope_id": users["owner"]}, headers=headers("stranger"))
        assert response.status_code == 403
    for path, payload in (("/api/customer-templates/import", template("evil")),
                          ("/api/customer-templates/activate", {"template_id": "firm-private"}),
                          ("/api/utility-catalogs/pipes", pipe(sizes=[999])),
                          ("/api/utility-catalogs/parts", sample_catalog()["parts"][0]),
                          ("/api/utility-catalogs/validate-network", {"features": []})):
        assert client.post(path, params={"scope_id": users["owner"]}, json=payload, headers=headers("stranger")).status_code == 403
    assert contents(db) == before
    # Original default-scope attack: the same item ID now belongs to B's own
    # namespace; it cannot overwrite A's sizes or activate A's private template.
    owner_catalog = client.get("/api/utility-catalogs", headers=headers("owner")).json()
    assert client.post("/api/customer-templates/activate", json={"template_id": "firm-private"}, headers=headers("stranger")).status_code == 404
    assert client.post("/api/utility-catalogs/pipes", json=pipe(sizes=[999]), headers=headers("stranger")).status_code == 200
    assert client.get("/api/utility-catalogs", headers=headers("owner")).json() == owner_catalog
    private_part = sample_catalog()["parts"][0]
    private_part["item_id"] = "private-part"
    assert client.post("/api/utility-catalogs/parts", json=private_part, headers=headers("owner")).status_code == 200
    assert "private-part" not in client.get("/api/utility-catalogs", headers=headers("stranger")).text
    own = client.post("/api/customer-templates/activate", json={"template_id": "firm-private"}, headers=headers("owner"))
    assert own.status_code == 200 and own.json()["registry"]["active_template_id"] == "firm-private"
    scope = {"scope_type": "project", "scope_id": scopes["project"]}
    assert client.post("/api/utility-catalogs/pipes", params=scope, json=pipe(), headers=headers("editor")).status_code == 200
    assert "firm-private" in client.get("/api/utility-catalogs", params=scope, headers=headers("viewer")).text
    assert client.post("/api/utility-catalogs/pipes", params=scope, json=pipe(), headers=headers("viewer")).status_code == 403
