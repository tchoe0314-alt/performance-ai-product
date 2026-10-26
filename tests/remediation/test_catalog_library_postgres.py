"""Real PostgreSQL reuse of C01a contracts. Skipped until explicitly approved.

Run serially in a separately authorized disposable local PostgreSQL database.
Ordinary DATABASE_URL must be absent. No discovery, installation or hosted calls.
Skipping this lane is missing evidence, never a successful PostgreSQL result.
"""
import os

import pytest

from c01a_postgres_support import disposable_postgres
from test_catalog_library_store import (
    make_state,
    test_default_private_and_same_id_isolation,
    test_shared_role_matrix_and_denied_nonmutation,
    test_template_selection_personal_and_project_editor_shared,
    test_immutable_public_seeds_and_invalid_requests_rollback,
    test_restart_versions_and_two_independent_store_connections,
    test_unknown_global_imports_not_adopted_and_never_destroyed,
    test_removed_members_lose_read_export_write_and_selection,
    test_account_export_and_fk_deletion_preserve_other_scopes,
    test_failed_persistence_rolls_back_snapshot_and_history,
    test_http_real_auth_private_exports_mutations_and_shared_permissions,
)


@pytest.fixture
def state(tmp_path, monkeypatch):
    if not os.environ.get("CIVORA_C01A_POSTGRES_DSN") and not os.environ.get("CIVORA_C01A_POSTGRES_APPROVAL"):
        pytest.skip("NOT VERIFIED: approved disposable C01a PostgreSQL target unavailable")
    # API import must not initialize ordinary/production storage. An unrelated
    # DATABASE_URL is refused by disposable_postgres, not silently overwritten.
    monkeypatch.setenv("PERFORMANCE_AI_STORAGE_DIR", str(tmp_path / "api-storage"))
    monkeypatch.setenv("CIVORA_PROCESS_ROLE", "web")
    monkeypatch.setenv("CIVORA_AI_PROVIDER", "none")
    monkeypatch.setenv("CIVORA_IMAGE_PROVIDER", "none")
    monkeypatch.setenv("CIVORA_DISABLE_CHAT_LEARNING", "1")
    with disposable_postgres(tmp_path, os.environ) as db:
        assert db.storage_kind == "postgres"
        yield make_state(db)


# The SQLite fork test is deliberately not imported. PostgreSQL pools must not
# be inherited across forks. A fresh-process worker lane and legacy PG upgrade
# fixture still need qualification before PH1-06/09 can close.
