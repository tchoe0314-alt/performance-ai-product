from __future__ import annotations

import logging
import resource
import time
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def memory_rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux: KB. macOS: bytes.
    if usage > 10_000_000:
        return usage / (1024 * 1024)
    return usage / 1024.0


def log_memory(label: str, extra: Optional[Dict[str, Any]] = None) -> None:
    payload = {"label": label, "rss_mb": round(memory_rss_mb(), 2)}
    if extra:
        payload.update(extra)
    logger.info("memory_snapshot %s", payload)


def run_timed(label: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Tuple[Any, float]:
    start = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = time.perf_counter() - start
    logger.info("timing %s took %.3fs", label, elapsed)
    return result, elapsed
