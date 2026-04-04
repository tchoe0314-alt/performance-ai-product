from __future__ import annotations

from typing import Any, Callable, Dict


def decide_chat(
    payload_data: Dict[str, Any],
    *,
    decide_chat_message: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> Dict[str, Any]:
    message = str(payload_data.get("message") or "").strip()
    if not message:
        raise ValueError("Chat message is required.")
    return decide_chat_message(dict(payload_data))
