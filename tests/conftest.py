import pytest


@pytest.fixture(autouse=True)
def disable_chat_learning_writes(monkeypatch):
    monkeypatch.setenv("CIVORA_DISABLE_CHAT_LEARNING", "1")
