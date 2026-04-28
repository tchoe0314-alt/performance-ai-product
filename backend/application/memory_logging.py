from __future__ import annotations

import logging
import os
import resource
from typing import Any


LOGGER = logging.getLogger("uvicorn.error")


def current_rss_mb() -> float:
    """Return current resident memory when available.

    Linux reports ru_maxrss in kilobytes, while macOS reports bytes. Railway
    runs Linux, but local dev often runs macOS, so normalize both for readable
    diagnostics.
    """
    rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if os.uname().sysname == "Darwin":
        rss = rss / 1024.0
    return rss / 1024.0


def log_memory(event: str, **fields: Any) -> None:
    payload = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    suffix = f" {payload}" if payload else ""
    LOGGER.info("MEMORY %s rss_mb=%.1f%s", event, current_rss_mb(), suffix)
