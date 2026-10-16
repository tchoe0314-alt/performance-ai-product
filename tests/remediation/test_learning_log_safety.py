import stat
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from backend.services.chat_learning_store import append_chat_learning_event


@pytest.fixture
def log_path(tmp_path, monkeypatch):
    path = tmp_path / "learning.jsonl"
    monkeypatch.setenv("CIVORA_CHAT_LEARNING_PATH", str(path))
    monkeypatch.setenv("CIVORA_ENABLE_CHAT_LEARNING", "1")
    monkeypatch.setenv("CIVORA_DISABLE_CHAT_LEARNING", "")
    return path


def append(payload):
    append_chat_learning_event(payload, consent={"global_learning_enabled": True},
        consent_lookup=lambda owner:{"user_id":owner,"account_active":True,"global_learning_enabled":True})


def test_learning_log_is_owner_only_even_when_existing_file_is_public(log_path):
    log_path.write_text("")
    log_path.chmod(0o644)
    append({"user_id": "synthetic-user", "message": "synthetic"})
    assert stat.S_IMODE(log_path.stat().st_mode) == 0o600
    assert "synthetic-user" in log_path.read_text()


def test_learning_log_refuses_symlink_without_modifying_target(log_path):
    target = log_path.parent / "unrelated.txt"
    target.write_text("unchanged")
    target.chmod(0o644)
    log_path.symlink_to(target)
    append({"user_id": "synthetic-user", "message": "synthetic"})
    assert target.read_text() == "unchanged"
    assert stat.S_IMODE(target.stat().st_mode) == 0o644


@pytest.mark.parametrize("owner", [None, "", "   ", True, 123])
def test_learning_record_requires_an_attributable_owner(log_path, owner):
    append({"user_id": owner, "message": "synthetic"})
    assert not log_path.exists()


def test_nonfinite_learning_payload_is_not_persisted(log_path):
    append({"user_id": "synthetic-user", "value": float("nan")})
    assert not log_path.exists()


def test_new_log_is_private_and_concurrent_appends_keep_complete_records(log_path):
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda index: append({"user_id": "synthetic-user", "index": index,
                                           "message": "synthetic café 🚧"}), range(32)))
    records = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert sorted(record["index"] for record in records) == list(range(32))
    assert all(record["message"] == "synthetic café 🚧" for record in records)
    assert stat.S_IMODE(log_path.stat().st_mode) == 0o600
