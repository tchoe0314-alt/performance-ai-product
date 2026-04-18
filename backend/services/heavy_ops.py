from __future__ import annotations

import logging
from typing import Any, Callable

from backend.monitoring import log_memory, run_timed

logger = logging.getLogger(__name__)


def run_heavy_operation(name: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """
    Execute a heavy operation with memory + timing logging.

    This is a seam for moving heavy work into a worker later.
    """
    log_memory(f"{name}:start")
    logger.info("heavy_op_start %s", {"op": name})
    result, elapsed = run_timed(name, func, *args, **kwargs)
    logger.info("heavy_op_end %s", {"op": name, "elapsed_s": round(elapsed, 3)})
    log_memory(f"{name}:end")
    return result
