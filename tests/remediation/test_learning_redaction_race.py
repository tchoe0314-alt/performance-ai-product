from concurrent.futures import ThreadPoolExecutor, TimeoutError
import json
import threading
import pytest

from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.data_lifecycle import DataLifecycleService, ACCOUNT_DELETE_CONFIRMATION
from backend.services import chat_learning_store as learning
from backend.services import data_lifecycle


@pytest.mark.parametrize("rollback", [False, True])
def test_account_redaction_cannot_erase_another_users_concurrent_append(tmp_path, monkeypatch, rollback):
    storage = tmp_path / "storage"
    storage.mkdir()
    path = storage / "learning.jsonl"
    db = Database(storage / "test.db")
    actor = AuthStore(db).register_user(email="deleted@example.test", password="Synthetic-only-123", name="Deleted")["user"]
    path.write_text(json.dumps({"user_id": actor["user_id"], "message": "delete me"}) + "\n")
    service = DataLifecycleService(db, storage_dir=storage, upload_dir=storage / "uploads",
                                   artifact_dir=storage / "artifacts", learning_paths=[path])
    monkeypatch.setenv("CIVORA_ENABLE_CHAT_LEARNING", "1")
    monkeypatch.setenv("CIVORA_DISABLE_CHAT_LEARNING", "")
    monkeypatch.setenv("CIVORA_CHAT_LEARNING_PATH", str(path))
    ready = threading.Event()
    proceed = threading.Event()
    started = threading.Event()
    replace = data_lifecycle.os.replace

    def delayed_replace(source, destination):
        if str(destination) == str(path):
            ready.set()
            assert proceed.wait(timeout=5)
        return replace(source, destination)

    monkeypatch.setattr(data_lifecycle.os, "replace", delayed_replace)
    if rollback:
        connect = db.connect
        class FailedDeletion:
            def __init__(self):
                self.connection = connect()
            def __getattr__(self, name):
                return getattr(self.connection, name)
            def execute(self, statement, *args):
                if statement.strip().startswith("DELETE FROM users"):
                    raise RuntimeError("synthetic database deletion failure")
                return self.connection.execute(statement, *args)
        monkeypatch.setattr(db, "connect", FailedDeletion)

    def append():
        started.set()
        learning.append_chat_learning_event({"user_id": "remaining-user", "message": "retain me"},
                                             consent={"global_learning_enabled": True})

    with ThreadPoolExecutor(max_workers=2) as pool:
        deletion = pool.submit(service.delete_account, user_id=actor["user_id"], confirmation=ACCOUNT_DELETE_CONFIRMATION)
        try:
            assert ready.wait(timeout=5)
            writer = pool.submit(append)
            assert started.wait(timeout=5)
            try:
                writer.result(timeout=0.2)
            except TimeoutError:
                pass  # Correctly serialized writers wait until deletion commits.
        finally:
            proceed.set()
        if rollback:
            with pytest.raises(RuntimeError, match="synthetic database deletion failure"):
                deletion.result(timeout=5)
        else:
            assert deletion.result(timeout=5)["account_deleted"]
        writer.result(timeout=5)
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(records) == (2 if rollback else 1)
    assert records[-1]["user_id"] == "remaining-user"
    assert records[-1]["message"] == "retain me"
    if rollback:
        assert records[0]["user_id"] == actor["user_id"]
        assert records[0]["message"] == "delete me"
