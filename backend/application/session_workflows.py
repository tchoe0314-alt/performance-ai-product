from __future__ import annotations

from typing import Any, Callable, Dict, Optional


def maybe_export_session(
    session_id: Optional[str],
    *,
    export_session_state: Optional[Callable[[str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if not session_id or export_session_state is None:
        return {}
    try:
        exported = export_session_state(session_id)
        return exported if isinstance(exported, dict) else {}
    except Exception:
        return {}
