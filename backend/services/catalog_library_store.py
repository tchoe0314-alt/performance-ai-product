"""Durable library boundary. Never adopt ambiguous process-global imports.

User libraries are private. Organization libraries require membership (admin to
edit); project libraries require project membership (editor to edit). Organization
template selections are personal; project selections are shared editor decisions.
Public samples are code-owned and read-only. Consumers outside this API boundary
are deliberately a separate C01b migration.
"""
from copy import deepcopy
import hashlib
import json
import time

from backend.planning.customer_templates import CustomerTemplateManager, sample_customer_template
from backend.planning.utility_catalogs import UtilityCatalogManager, sample_catalog


class LibraryAccessError(PermissionError):
    pass


class CatalogLibraryStore:
    READS = {
        "templates": {"snapshot", "export_json", "explain_missing"},
        "utilities": {"snapshot", "available_pipe_sizes", "validate_network"},
    }
    WRITES = {
        "templates": {"import_template", "activate"},
        "utilities": {"add_pipe_catalog", "add_part_catalog"},
    }

    def __init__(self, db):
        self.db = db

    @staticmethod
    def _seed(kind):
        if kind == "templates":
            return {"templates": [sample_customer_template()]}
        return sample_catalog()

    @staticmethod
    def _encode(payload):
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return encoded, hashlib.sha256(encoded.encode()).hexdigest()

    def _authorize(self, connection, user_id, scope_type, scope_id, *, write):
        if not user_id or not connection.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone():
            raise LibraryAccessError("Library access denied.")
        if scope_type == "user":
            allowed = scope_id == user_id
        elif scope_type == "public":
            allowed = scope_id == "reference" and not write
        elif scope_type == "organization":
            row = connection.execute(
                "SELECT o.created_by_user_id, m.role FROM organizations o "
                "LEFT JOIN organization_members m ON m.organization_id = o.organization_id AND m.user_id = ? "
                "WHERE o.organization_id = ?", (user_id, scope_id),
            ).fetchone()
            role = ("owner" if row["created_by_user_id"] == user_id else row["role"]) if row else None
            allowed = role in ({"owner", "admin"} if write else {"owner", "admin", "editor", "reviewer", "viewer", "member"})
        elif scope_type == "project":
            row = connection.execute(
                "SELECT p.user_id, m.role FROM projects p "
                "LEFT JOIN project_members m ON m.project_id = p.project_id AND m.user_id = ? "
                "WHERE p.project_id = ? AND p.deleted_at IS NULL", (user_id, scope_id),
            ).fetchone()
            role = ("owner" if row["user_id"] == user_id else row["role"]) if row else None
            allowed = role in ({"owner", "admin", "editor"} if write else {"owner", "admin", "editor", "reviewer", "viewer"})
        else:
            allowed = False
        if not allowed:
            raise LibraryAccessError("Library access denied.")

    def run(self, *, user_id, kind, operation, payload=None, scope_type="user", scope_id="", **kwargs):
        if kind not in self.READS or operation not in self.READS[kind] | self.WRITES[kind]:
            raise ValueError("Unsupported library operation.")
        scope_id = scope_id or (user_id if scope_type == "user" else "reference" if scope_type == "public" else "")
        write = operation in self.WRITES[kind]
        # Organization selection is per-member, not an organization-wide mutation.
        personal_selection = operation == "activate" and scope_type in {"user", "organization"}
        selector_id = "" if scope_type == "project" else user_id
        key = (scope_type, scope_id, kind)
        connection = self.db.connect()
        try:
            if self.db.storage_kind == "sqlite":
                connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            elif not write:
                connection.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            self._authorize(connection, user_id, scope_type, scope_id, write=write and not personal_selection)
            # INSERT + row lock serializes first-write as well as existing-row
            # updates across processes; no dependence on Python process locks.
            if write:
                seed_json, seed_hash = self._encode(self._seed(kind))
                connection.execute(
                    "INSERT INTO catalog_libraries(scope_type, scope_id, kind, owner_user_id, owner_organization_id, owner_project_id, revision, payload_json, content_hash, updated_by) "
                    "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?) ON CONFLICT(scope_type, scope_id, kind) DO NOTHING",
                    (*key, scope_id if scope_type == "user" else None,
                     scope_id if scope_type == "organization" else None,
                     scope_id if scope_type == "project" else None, seed_json, seed_hash, user_id),
                )
            lock = " FOR UPDATE" if write and self.db.storage_kind == "postgres" else ""
            row = connection.execute(
                "SELECT * FROM catalog_libraries WHERE scope_type = ? AND scope_id = ? AND kind = ?" + lock, key,
            ).fetchone() if scope_type != "public" else None
            data = json.loads(row["payload_json"]) if row else self._seed(kind)
            revision = row["revision"] if row else 0
            content_hash = row["content_hash"] if row else self._encode(data)[1]
            selection = None
            if kind == "templates":
                selection = connection.execute(
                    "SELECT template_id, revision FROM catalog_template_selections "
                    "WHERE scope_type = ? AND scope_id = ? AND selector_id = ?",
                    (scope_type, scope_id, selector_id),
                ).fetchone()
                data["active_template_id"] = selection["template_id"] if selection else ""
                manager = CustomerTemplateManager(data)
            else:
                manager = UtilityCatalogManager(data)
            if write and operation != "activate":
                seed = self._seed(kind)
                if kind == "templates":
                    reserved = {item["template_id"] for item in seed["templates"]}
                    submitted = (payload or {}).get("template_id")
                else:
                    field = "pipes" if operation == "add_pipe_catalog" else "parts"
                    reserved = {item["item_id"] for item in seed[field]}
                    submitted = (payload or {}).get("item_id")
                if str(submitted or "").strip() in reserved:
                    raise LibraryAccessError("Public reference items are read-only; import under a private ID.")
                original = manager.snapshot()
            method = getattr(manager, operation)
            result = method(deepcopy(payload or {}), **kwargs) if payload is not None else method(**kwargs)
            if write and result.get("success"):
                if operation != "activate":
                    field = "templates" if kind == "templates" else field
                    id_field = "template_id" if kind == "templates" else "item_id"
                    before = {item[id_field]: item for item in original[field] if item[id_field] in reserved}
                    after = {item[id_field]: item for item in manager.snapshot()[field] if item[id_field] in reserved}
                    if before != after:
                        raise LibraryAccessError("Public reference items are read-only.")
                if operation == "activate":
                    connection.execute(
                        "INSERT INTO catalog_template_selections(scope_type, scope_id, selector_id, template_id, personal_user_id, revision) "
                        "VALUES (?, ?, ?, ?, ?, 1) ON CONFLICT(scope_type, scope_id, selector_id) DO UPDATE SET "
                        "template_id = excluded.template_id, revision = catalog_template_selections.revision + 1",
                        (scope_type, scope_id, selector_id, manager.active_template_id, user_id if selector_id else None),
                    )
                    selection = connection.execute(
                        "SELECT template_id, revision FROM catalog_template_selections "
                        "WHERE scope_type = ? AND scope_id = ? AND selector_id = ?",
                        (scope_type, scope_id, selector_id),
                    ).fetchone()
                else:
                    snapshot = manager.snapshot()
                    # Selection is not shared mutable organization content.
                    if kind == "templates":
                        snapshot = {"templates": snapshot["templates"]}
                    else:
                        snapshot.pop("summary", None)
                    encoded, content_hash = self._encode(snapshot)
                    revision += 1
                    connection.execute(
                        "UPDATE catalog_libraries SET revision = ?, payload_json = ?, content_hash = ?, updated_by = ? "
                        "WHERE scope_type = ? AND scope_id = ? AND kind = ?",
                        (revision, encoded, content_hash, user_id, *key),
                    )
                    connection.execute(
                        "INSERT INTO catalog_library_versions(scope_type, scope_id, kind, revision, payload_json, content_hash, updated_by, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (*key, revision, encoded, content_hash, user_id, time.time()),
                    )
                connection.commit()
            elif write:
                connection.rollback()
            result["library"] = {
                "scope_type": scope_type, "scope_id": scope_id, "kind": kind,
                "revision": revision, "content_hash": content_hash,
                "selection_revision": selection["revision"] if selection else 0,
                "public_reference_version": "c01a-seeds-v1",
            }
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
