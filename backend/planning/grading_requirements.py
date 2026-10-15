"""Preserve explicit percentage constraints; never silently loosen maxima."""
from math import isfinite


def requested_grading_ratio(profile, key, default):
    raw = profile.get(key)
    if raw is None or isinstance(raw, str) and not raw.strip():
        return default
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raise ValueError(f"{key} must be a finite, nonnegative percentage.")
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{key} must be a finite, nonnegative percentage.") from exc
    if not isfinite(value) or value < 0:
        raise ValueError(f"{key} must be a finite, nonnegative percentage.")
    return value / 100
