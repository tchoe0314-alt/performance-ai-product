"""Draft text can be saved; invalid count controls cannot start calculations."""
from math import isfinite
from fastapi import HTTPException


def validate_input_count_controls(meta):
    controls = (meta or {}).get("edit_controls_v1")
    if controls is None:
        return
    if not isinstance(controls, dict):
        raise HTTPException(422, "Invalid count controls.")
    for field, maximum in (("buildingCount", 500), ("parkingCount", 9007199254740991)):
        raw = controls.get(field)
        if raw is None or isinstance(raw, str) and not raw.strip():
            continue
        try:
            value = float(raw) if not isinstance(raw, bool) else float("nan")
        except (TypeError, ValueError, OverflowError):
            value = float("nan")
        if not isfinite(value) or value < 0 or not value.is_integer() or value > maximum:
            raise HTTPException(422, f"{field} must be a whole number between 0 and {maximum} before calculating.")
