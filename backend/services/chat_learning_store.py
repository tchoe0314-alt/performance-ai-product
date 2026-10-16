from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Dict


_DEFAULT_LEARNING_PATH = Path(__file__).resolve().parents[2] / "data" / "chat_learning.jsonl"


def _truthy_env(name: str) -> bool:
    value = os.environ.get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _chat_learning_disabled() -> bool:
    if _truthy_env("CIVORA_DISABLE_CHAT_LEARNING"):
        return True
    return not _truthy_env("CIVORA_ENABLE_CHAT_LEARNING")


def chat_learning_enabled() -> bool:
    return not _chat_learning_disabled()


def _learning_path() -> Path:
    override = os.environ.get("CIVORA_CHAT_LEARNING_PATH")
    if override:
        return Path(override).expanduser()
    return _DEFAULT_LEARNING_PATH


@contextmanager
def learning_log_lock(path: Path):
    """Stable lock inode shared by append, export and deletion/rollback.

    Never unlink the sidecar: replacing the log must not change the lock identity.
    """
    import fcntl
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(descriptor, "a") as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise ValueError("Learning lock must be a regular file.")
        os.fchmod(lock.fileno(), 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield


def _append_jsonl(record: Dict[str, Any], *, consent: Dict[str, Any] | None = None) -> None:
    # Consent is supplied by the server's account-consent lookup, never a flag
    # copied out of the message/training payload. Missing consent fails closed.
    if _chat_learning_disabled() or not isinstance(consent, dict) or consent.get("global_learning_enabled") is not True:
        return
    owner = record.get("user_id")
    if not isinstance(owner, str) or not owner.strip():
        return  # Unowned personal data cannot be exported/deleted reliably.
    serialized = json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n"
    # POSIX deployments: fail closed rather than follow links or write a FIFO.
    # This does not enable collection or substitute for server consent lookup.
    import fcntl
    path = _learning_path()
    with learning_log_lock(path):
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise ValueError("Learning log must be a regular file.")
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            os.fchmod(handle.fileno(), 0o600)
            handle.write(serialized)
            handle.flush()


def append_chat_learning_event(payload: Dict[str, Any], *, consent: Dict[str, Any] | None = None) -> None:
    try:
        event = dict(payload)
        event["ts"] = time.time()
        _append_jsonl(event, consent=consent)
    except Exception:
        # Learning log failures should never break the user flow.
        return


def append_chat_interaction_event(payload: Dict[str, Any], *, consent: Dict[str, Any] | None = None) -> None:
    try:
        event = dict(payload)
        event["ts"] = time.time()
        event.setdefault("event_type", "interaction")
        _append_jsonl(event, consent=consent)
    except Exception:
        return


def append_chat_training_example(example: Dict[str, Any], *, consent: Dict[str, Any] | None = None) -> None:
    try:
        record = dict(example)
        record["ts"] = time.time()
        record["event_type"] = "training_example"
        _append_jsonl(record, consent=consent)
    except Exception:
        return
