from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict


_LEARNING_PATH = Path(__file__).resolve().parents[2] / "data" / "chat_learning.jsonl"


def append_chat_learning_event(payload: Dict[str, Any]) -> None:
    try:
        _LEARNING_PATH.parent.mkdir(parents=True, exist_ok=True)
        event = dict(payload)
        event["ts"] = time.time()
        with _LEARNING_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        # Learning log failures should never break the user flow.
        return
