# engines/autofix_engine.py

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from core.constraint_engine import ConstraintIssue


EPS = 1e-9
STRICT_MODE = "strict"
ASSISTED_MODE = "assisted"


@dataclass
class AutofixAction:
    code: str
    target: str
    message: str
    before: Dict[str, Any] = field(default_factory=dict)
    after: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AutofixIssue:
    code: str
    severity: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AutofixResult:
    success: bool
    message: str = ""
    fixed_layout: Dict[str, Any] = field(default_factory=dict)
    actions: List[AutofixAction] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    issues: List[AutofixIssue] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def error_count(self) -> int:
        return len(self.errors) + sum(1 for i in self.issues if i.severity.lower() == "error")

    def warning_count(self) -> int:
        return len(self.warnings) + sum(1 for i in self.issues if i.severity.lower() == "warning")


# -----------------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------------

def _issue(code: str, severity: str, message: str, **context: Any) -> AutofixIssue:
    return AutofixIssue(code=code, severity=severity, message=message, context=context)


def _clamp(val: float, min_val: float, max_val: float) -> float:
    if max_val < min_val:
        return min_val
    return max(min_val, min(val, max_val))


def _rect_copy(rect: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return deepcopy(rect) if isinstance(rect, dict) else None


def _required_rect(rect: Dict[str, Any], name: str) -> Tuple[bool, Optional[str]]:
    required = ("x", "y", "w", "h")
    for key in required:
        if key not in rect:
            return False, f"{name} is missing required key '{key}'."
        try:
            float(rect[key])
        except Exception:
            return False, f"{name}.{key} must be numeric."
    if float(rect["w"]) <= 0.0 or float(rect["h"]) <= 0.0:
        return False, f"{name} width and height must be > 0."
    return True, None


def _normalize_rect(rect: Dict[str, Any]) -> Dict[str, float]:
    return {
        "x": float(rect["x"]),
        "y": float(rect["y"]),
        "w": float(rect["w"]),
        "h": float(rect["h"]),
    }


def _bounds_from_lot_and_setback(lot: Dict[str, float], setback: float) -> Dict[str, float]:
    return {
        "x": lot["x"] + setback,
        "y": lot["y"] + setback,
        "w": max(0.0, lot["w"] - 2.0 * setback),
        "h": max(0.0, lot["h"] - 2.0 * setback),
    }


def _rect_right(rect: Dict[str, float]) -> float:
    return rect["x"] + rect["w"]


def _rect_top(rect: Dict[str, float]) -> float:
    return rect["y"] + rect["h"]


def _rect_center(rect: Dict[str, float]) -> Tuple[float, float]:
    return rect["x"] + rect["w"] / 2.0, rect["y"] + rect["h"] / 2.0


def _rects_overlap(a: Dict[str, float], b: Dict[str, float], clearance: float = 0.0) -> bool:
    return not (
        _rect_right(a) <= b["x"] - clearance + EPS
        or a["x"] >= _rect_right(b) + clearance - EPS
        or _rect_top(a) <= b["y"] - clearance + EPS
        or a["y"] >= _rect_top(b) + clearance - EPS
    )


def _clamp_rect_into_bounds(rect: Dict[str, float], bounds: Dict[str, float], pad: float = 1.0) -> Dict[str, float]:
    fixed = dict(rect)
    fixed["x"] = _clamp(
        fixed["x"],
        bounds["x"] + pad,
        bounds["x"] + bounds["w"] - fixed["w"] - pad,
    )
    fixed["y"] = _clamp(
        fixed["y"],
        bounds["y"] + pad,
        bounds["y"] + bounds["h"] - fixed["h"] - pad,
    )
    return fixed


def _fits_inside(rect: Dict[str, float], bounds: Dict[str, float], pad: float = 0.0) -> bool:
    return (
        rect["x"] >= bounds["x"] + pad - EPS
        and rect["y"] >= bounds["y"] + pad - EPS
        and _rect_right(rect) <= bounds["x"] + bounds["w"] - pad + EPS
        and _rect_top(rect) <= bounds["y"] + bounds["h"] - pad + EPS
    )


def _record_action(
    result: AutofixResult,
    code: str,
    target: str,
    message: str,
    before: Optional[Dict[str, Any]],
    after: Optional[Dict[str, Any]],
) -> None:
    result.actions.append(
        AutofixAction(
            code=code,
            target=target,
            message=message,
            before=deepcopy(before) if before is not None else {},
            after=deepcopy(after) if after is not None else {},
        )
    )


def _candidate_positions_around(
    anchor: Dict[str, float],
    moving: Dict[str, float],
    clearance: float,
) -> List[Tuple[str, Dict[str, float]]]:
    cx, cy = _rect_center(anchor)
    candidates: List[Tuple[str, Dict[str, float]]] = []

    # below
    candidates.append((
        "below",
        {
            "x": cx - moving["w"] / 2.0,
            "y": anchor["y"] - moving["h"] - clearance,
            "w": moving["w"],
            "h": moving["h"],
        },
    ))
    # above
    candidates.append((
        "above",
        {
            "x": cx - moving["w"] / 2.0,
            "y": _rect_top(anchor) + clearance,
            "w": moving["w"],
            "h": moving["h"],
        },
    ))
    # left
    candidates.append((
        "left",
        {
            "x": anchor["x"] - moving["w"] - clearance,
            "y": cy - moving["h"] / 2.0,
            "w": moving["w"],
            "h": moving["h"],
        },
    ))
    # right
    candidates.append((
        "right",
        {
            "x": _rect_right(anchor) + clearance,
            "y": cy - moving["h"] / 2.0,
            "w": moving["w"],
            "h": moving["h"],
        },
    ))
    return candidates


def _find_non_overlapping_position(
    moving: Dict[str, float],
    anchor: Dict[str, float],
    bounds: Dict[str, float],
    clearance: float,
    pad: float,
) -> Optional[Dict[str, float]]:
    for _, candidate in _candidate_positions_around(anchor, moving, clearance):
        clamped = _clamp_rect_into_bounds(candidate, bounds, pad=pad)
        if _fits_inside(clamped, bounds, pad=pad) and not _rects_overlap(clamped, anchor, clearance=clearance):
            return clamped
    return None


def _validate_layout(
    layout: Dict[str, Any],
    result: AutofixResult,
) -> Optional[Tuple[Dict[str, float], float, Optional[Dict[str, float]], Optional[Dict[str, float]], Optional[Dict[str, float]]]]:
    if not isinstance(layout, dict):
        result.errors.append("layout must be a dict.")
        result.issues.append(_issue("LAYOUT_INVALID", "error", "layout must be a dict."))
        return None

    if "lot" not in layout:
        result.errors.append("layout must include 'lot'.")
        result.issues.append(_issue("LOT_REQUIRED", "error", "layout must include 'lot'."))
        return None

    ok, msg = _required_rect(layout["lot"], "lot")
    if not ok:
        result.errors.append(msg or "lot is invalid.")
        result.issues.append(_issue("LOT_INVALID", "error", msg or "lot is invalid."))
        return None

    lot = _normalize_rect(layout["lot"])

    setback = layout.get("setback", 0.0)
    try:
        setback = float(setback)
        if setback < 0.0:
            raise ValueError
    except Exception:
        result.errors.append("setback must be numeric and >= 0.")
        result.issues.append(_issue("SETBACK_INVALID", "error", "setback must be numeric and >= 0.", setback=layout.get("setback")))
        return None

    building = None
    parking = None
    driveway = None

    if layout.get("building") is not None:
        ok, msg = _required_rect(layout["building"], "building")
        if not ok:
            result.errors.append(msg or "building is invalid.")
            result.issues.append(_issue("BUILDING_INVALID", "error", msg or "building is invalid."))
            return None
        building = _normalize_rect(layout["building"])

    if layout.get("parking") is not None:
        ok, msg = _required_rect(layout["parking"], "parking")
        if not ok:
            result.errors.append(msg or "parking is invalid.")
            result.issues.append(_issue("PARKING_INVALID", "error", msg or "parking is invalid."))
            return None
        parking = _normalize_rect(layout["parking"])

    if layout.get("driveway") is not None:
        ok, msg = _required_rect(layout["driveway"], "driveway")
        if not ok:
            result.errors.append(msg or "driveway is invalid.")
            result.issues.append(_issue("DRIVEWAY_INVALID", "error", msg or "driveway is invalid."))
            return None
        driveway = _normalize_rect(layout["driveway"])

    return lot, setback, building, parking, driveway


# -----------------------------------------------------------------------------
# main autofix API
# -----------------------------------------------------------------------------

def autofix_site_layout_detailed(
    layout: Dict[str, Any],
    issues: List[ConstraintIssue],
    *,
    mode: str = ASSISTED_MODE,
    building_clearance_ft: float = 10.0,
    parking_pad: float = 1.0,
    driveway_pad: float = 0.0,
) -> AutofixResult:
    """
    Applies safe, deterministic layout fixes only.

    Philosophy:
    - No hidden geometry invention in strict mode
    - Only constrained moves / clamping / repositioning
    - No resizing or deletion of objects
    - Preserve original capabilities and layout structure
    """
    result = AutofixResult(success=True, message="Autofix completed.")
    fixed = deepcopy(layout)

    mode = str(mode or ASSISTED_MODE).strip().lower()
    if mode not in {STRICT_MODE, ASSISTED_MODE}:
        result.errors.append("mode must be 'strict' or 'assisted'.")
        result.issues.append(_issue("MODE_INVALID", "error", "mode must be 'strict' or 'assisted'.", mode=mode))
        result.success = False
        result.fixed_layout = fixed
        return result

    validated = _validate_layout(fixed, result)
    if validated is None:
        result.success = False
        result.message = "Autofix input validation failed."
        result.fixed_layout = fixed
        return result

    lot, setback, building, parking, driveway = validated
    buildable = _bounds_from_lot_and_setback(lot, setback)

    if buildable["w"] <= EPS or buildable["h"] <= EPS:
        result.errors.append("Setback leaves no buildable area inside lot.")
        result.issues.append(_issue("BUILDABLE_AREA_INVALID", "error", "Setback leaves no buildable area inside lot.", buildable=buildable))
        result.success = False
        result.fixed_layout = fixed
        return result

    codes: Set[str] = {str(getattr(issue, "code", "") or "") for issue in issues}

    # ------------------------------------------------------------------
    # Fix building outside setback / lot
    # ------------------------------------------------------------------
    if building is not None and (("BUILDING_OUTSIDE_SETBACK" in codes) or not _fits_inside(building, buildable, pad=1.0)):
        before = dict(building)

        if building["w"] > buildable["w"] + EPS or building["h"] > buildable["h"] + EPS:
            msg = "Building footprint does not fit within buildable area; autofix cannot safely solve this without resizing."
            severity = "error" if mode == STRICT_MODE else "warning"
            result.issues.append(_issue("BUILDING_TOO_LARGE", severity, msg, building=building, buildable=buildable))
            if severity == "error":
                result.errors.append(msg)
            else:
                result.warnings.append(msg)
        else:
            building["x"] = buildable["x"] + max(0.0, (buildable["w"] - building["w"]) / 2.0)
            building["y"] = buildable["y"] + max(0.0, (buildable["h"] - building["h"]) / 2.0)
            building = _clamp_rect_into_bounds(building, buildable, pad=1.0)
            fixed["building"] = building
            _record_action(
                result,
                "BUILDING_REPOSITIONED",
                "building",
                "Repositioned building inside buildable area.",
                before,
                building,
            )

    # ------------------------------------------------------------------
    # Fix parking overlap with building
    # ------------------------------------------------------------------
    if parking is not None and building is not None and (("PARKING_OVERLAPS_BUILDING" in codes) or _rects_overlap(parking, building, clearance=0.0)):
        before = dict(parking)
        candidate = _find_non_overlapping_position(
            moving=parking,
            anchor=building,
            bounds=lot,
            clearance=building_clearance_ft,
            pad=parking_pad,
        )
        if candidate is None:
            msg = "Parking overlaps building and no safe non-overlapping position was found inside lot."
            severity = "error" if mode == STRICT_MODE else "warning"
            result.issues.append(_issue("PARKING_FIX_FAILED", severity, msg, parking=parking, building=building))
            if severity == "error":
                result.errors.append(msg)
            else:
                result.warnings.append(msg)
        else:
            parking = candidate
            fixed["parking"] = parking
            _record_action(
                result,
                "PARKING_REPOSITIONED",
                "parking",
                "Moved parking to avoid building overlap.",
                before,
                parking,
            )

    # ------------------------------------------------------------------
    # Fix parking outside lot
    # ------------------------------------------------------------------
    if parking is not None and (("PARKING_OUTSIDE_LOT" in codes) or not _fits_inside(parking, lot, pad=parking_pad)):
        before = dict(parking)
        parking = _clamp_rect_into_bounds(parking, lot, pad=parking_pad)
        fixed["parking"] = parking
        _record_action(
            result,
            "PARKING_CLAMPED",
            "parking",
            "Clamped parking inside lot bounds.",
            before,
            parking,
        )

    # ------------------------------------------------------------------
    # Fix driveway outside lot
    # ------------------------------------------------------------------
    if driveway is not None and (("DRIVEWAY_OUTSIDE_LOT" in codes) or not _fits_inside(driveway, lot, pad=driveway_pad)):
        before = dict(driveway)
        driveway = _clamp_rect_into_bounds(driveway, lot, pad=driveway_pad)
        fixed["driveway"] = driveway
        _record_action(
            result,
            "DRIVEWAY_CLAMPED",
            "driveway",
            "Clamped driveway inside lot bounds.",
            before,
            driveway,
        )

    # ------------------------------------------------------------------
    # Secondary consistency checks
    # ------------------------------------------------------------------
    final_validated = _validate_layout(fixed, result)
    if final_validated is not None:
        lot2, setback2, building2, parking2, driveway2 = final_validated
        buildable2 = _bounds_from_lot_and_setback(lot2, setback2)

        if building2 is not None and not _fits_inside(building2, buildable2, pad=1.0):
            msg = "Autofix completed but building remains outside buildable area."
            severity = "error" if mode == STRICT_MODE else "warning"
            result.issues.append(_issue("BUILDING_STILL_OUTSIDE", severity, msg, building=building2, buildable=buildable2))
            if severity == "error":
                result.errors.append(msg)
            else:
                result.warnings.append(msg)

        if parking2 is not None and building2 is not None and _rects_overlap(parking2, building2, clearance=0.0):
            msg = "Autofix completed but parking still overlaps building."
            severity = "error" if mode == STRICT_MODE else "warning"
            result.issues.append(_issue("PARKING_STILL_OVERLAPS", severity, msg, parking=parking2, building=building2))
            if severity == "error":
                result.errors.append(msg)
            else:
                result.warnings.append(msg)

        if parking2 is not None and not _fits_inside(parking2, lot2, pad=parking_pad):
            msg = "Autofix completed but parking still lies outside lot."
            severity = "error" if mode == STRICT_MODE else "warning"
            result.issues.append(_issue("PARKING_STILL_OUTSIDE", severity, msg, parking=parking2, lot=lot2))
            if severity == "error":
                result.errors.append(msg)
            else:
                result.warnings.append(msg)

        if driveway2 is not None and not _fits_inside(driveway2, lot2, pad=driveway_pad):
            msg = "Autofix completed but driveway still lies outside lot."
            severity = "error" if mode == STRICT_MODE else "warning"
            result.issues.append(_issue("DRIVEWAY_STILL_OUTSIDE", severity, msg, driveway=driveway2, lot=lot2))
            if severity == "error":
                result.errors.append(msg)
            else:
                result.warnings.append(msg)

    result.fixed_layout = fixed
    result.metadata = {
        "mode": mode,
        "issue_codes_seen": sorted(codes),
        "action_count": len(result.actions),
        "warning_count": result.warning_count(),
        "error_count": result.error_count(),
    }

    if result.error_count() > 0:
        result.success = False
        result.message = "Autofix completed with blocking errors."
    elif result.warning_count() > 0:
        result.message = "Autofix completed with warnings."

    return result


# -----------------------------------------------------------------------------
# backward-compatible wrapper
# -----------------------------------------------------------------------------

def autofix_site_layout(
    layout: Dict[str, Any],
    issues: List[ConstraintIssue],
) -> Dict[str, Any]:
    """
    Backward-compatible wrapper.

    Preserves the original behavior contract:
    - returns only the fixed layout dict

    The detailed autofix result is available through autofix_site_layout_detailed().
    """
    result = autofix_site_layout_detailed(
        layout=layout,
        issues=issues,
        mode=ASSISTED_MODE,
    )
    return result.fixed_layout
