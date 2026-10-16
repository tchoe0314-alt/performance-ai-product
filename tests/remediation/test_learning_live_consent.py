import pytest
import threading
from concurrent.futures import ThreadPoolExecutor
from backend.services import chat_learning_store as learning
from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.project_store import ProjectStore


@pytest.fixture
def account(tmp_path, monkeypatch):
    path = tmp_path / "learning.jsonl"
    monkeypatch.setenv("CIVORA_CHAT_LEARNING_PATH", str(path))
    monkeypatch.setenv("CIVORA_ENABLE_CHAT_LEARNING", "1")
    monkeypatch.setenv("CIVORA_DISABLE_CHAT_LEARNING", "")
    db = Database(tmp_path / "consent.db")
    user = AuthStore(db).register_user(email="consent@example.test", password="Synthetic-only-123", name="Consent")["user"]["user_id"]
    store = ProjectStore(db)
    old = store.update_memory_consent(user_id=user, personal_enabled=False, company_enabled=False, global_learning_enabled=True)
    return db, store, user, path, old


def test_old_opt_in_snapshot_cannot_authorize_a_later_learning_write(account):
    db, store, user, path, old = account
    store.update_memory_consent(user_id=user, personal_enabled=False, company_enabled=False, global_learning_enabled=False)
    learning.append_chat_learning_event({"user_id": user, "message": "do not collect"}, consent=old)
    assert not path.exists()


@pytest.mark.parametrize("state", ["active", "withdrawn", "deleted"])
def test_live_database_authority_controls_collection(account, state):
    db, store, user, path, old = account
    if state == "withdrawn":
        store.update_memory_consent(user_id=user, personal_enabled=False,
                                    company_enabled=False, global_learning_enabled=False)
    if state == "deleted":
        connection = db.connect()
        try:
            connection.execute("DELETE FROM users WHERE user_id = ?", (user,))
            connection.commit()
        finally:
            connection.close()
    learning.append_chat_learning_event({"user_id": user, "message": "synthetic"}, consent=old,
                                        consent_lookup=learning.database_learning_consent(db))
    assert path.exists() is (state == "active")


def test_wrong_owner_live_receipt_fails_closed(account):
    _, _, user, path, old = account
    learning.append_chat_learning_event({"user_id": user, "message": "synthetic"}, consent=old,
        consent_lookup=lambda _: {"user_id": "different-user", "account_active": True,
                                   "global_learning_enabled": True})
    assert not path.exists()


def test_live_lookup_failure_fails_closed(account):
    _, _, user, path, old = account
    def unavailable(_):
        raise RuntimeError("synthetic consent lookup failure")
    learning.append_chat_learning_event({"user_id": user, "message": "synthetic"}, consent=old,
                                        consent_lookup=unavailable)
    assert not path.exists()


def test_waiting_append_rechecks_consent_only_after_acquiring_log_lock(account):
    db, store, user, path, old = account
    started = threading.Event()
    checked = threading.Event()
    lookup = learning.database_learning_consent(db)
    def current(owner):
        checked.set()
        return lookup(owner)
    def append():
        started.set()
        learning.append_chat_learning_event({"user_id": user, "message": "synthetic"},
                                             consent=old, consent_lookup=current)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with learning.learning_log_lock(path):
            pending = pool.submit(append)
            assert started.wait(timeout=5)
            assert not checked.wait(timeout=0.2)
            # Exercise the real DB update body while this test owns its required
            # lock, as the public withdrawal method does. No production bypass.
            store._update_memory_consent_locked(user_id=user, personal_enabled=False,
                                                company_enabled=False, global_learning_enabled=False)
        pending.result(timeout=5)
    assert checked.is_set()
    assert not path.exists()
