from __future__ import annotations

import logging
import os
import resource
from typing import Any


LOGGER = logging.getLogger("uvicorn.error")


def current_rss_mb() -> float:
    """Return current resident memory when available.

    Linux exposes current RSS in /proc/self/status. Fall back to ru_maxrss,
    which is peak RSS rather than current RSS, when /proc is unavailable.
    """
    status_path = "/proc/self/status"
    if os.path.exists(status_path):
        try:
            with open(status_path, "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("VmRSS:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            return float(parts[1]) / 1024.0
        except OSError:
            pass

    rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if os.uname().sysname == "Darwin":
        rss = rss / 1024.0
    return rss / 1024.0


def peak_rss_mb() -> float:
    """Return peak resident memory for diagnostics."""
    rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if os.uname().sysname == "Darwin":
        rss = rss / 1024.0
    return rss / 1024.0


def log_memory(event: str, **fields: Any) -> None:
    payload = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    suffix = f" {payload}" if payload else ""
    LOGGER.info("MEMORY %s rss_mb=%.1f%s", event, current_rss_mb(), suffix)
