from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict


_DEFAULT_LEARNING_PATH = Path(__file__).resolve().parents[2] / "data" / "chat_learning.jsonl"


def _truthy_env(name: str) -> bool:
    value = os.environ.get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _chat_learning_disabled() -> bool:
    if _truthy_env("CIVORA_DISABLE_CHAT_LEARNING"):
        return True
    return not _truthy_env("CIVORA_ENABLE_CHAT_LEARNING")


def _learning_path() -> Path:
    override = os.environ.get("CIVORA_CHAT_LEARNING_PATH")
    if override:
        return Path(override).expanduser()
    return _DEFAULT_LEARNING_PATH


def _append_jsonl(record: Dict[str, Any]) -> None:
    if _chat_learning_disabled():
        return
    path = _learning_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_chat_learning_event(payload: Dict[str, Any]) -> None:
    try:
        event = dict(payload)
        event["ts"] = time.time()
        _append_jsonl(event)
    except Exception:
        # Learning log failures should never break the user flow.
        return


def append_chat_interaction_event(payload: Dict[str, Any]) -> None:
    try:
        event = dict(payload)
        event["ts"] = time.time()
        event.setdefault("event_type", "interaction")
        _append_jsonl(event)
    except Exception:
        return


def append_chat_training_example(example: Dict[str, Any]) -> None:
    try:
        record = dict(example)
        record["ts"] = time.time()
        record["event_type"] = "training_example"
        _append_jsonl(record)
    except Exception:
        return
