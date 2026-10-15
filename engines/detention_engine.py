
from __future__ import annotations

"""
detention_engine.py (MERGED MAX VERSION)

Purpose
-------
Concept-to-preliminary detention sizing and basin evaluation engine for the
AI civil engineering platform.

This file upgrades a very small concept-sizing helper into a real detention
engine that can:
- size required storage from inflow / release assumptions
- size basin geometry from depth and side slopes
- generate stage-storage curves
- evaluate provided basin layouts
- estimate simple drawdown time
- compare alternatives
- return planner / intelligence / report-ready outputs

Design intent
-------------
- Preserve the original concept_detention_size entrypoint
- Expand without removing original capability
- Keep logic deterministic and engineering-oriented
- Stay compatible with planner, compliance, optimization, and reporting layers
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple
import math


# =============================================================================
# DEFAULTS / ENGINEERING ASSUMPTIONS
# =============================================================================

DEFAULT_STORAGE_HOURS = 0.50
DEFAULT_MAX_DEPTH_FT = 6.0
DEFAULT_FREEBOARD_FT = 1.0
DEFAULT_SIDE_SLOPE_H = 4.0  # 4H:1V conceptual basin side slope
DEFAULT_BOTTOM_LENGTH_WIDTH_RATIO = 1.5
DEFAULT_STAGE_INCREMENT_FT = 0.5
DEFAULT_MIN_BOTTOM_DIM_FT = 12.0
DEFAULT_MAX_DRAWDOWN_HOURS = 48.0
DEFAULT_MAX_STORAGE_CF = 5_000_000.0
DEFAULT_MAX_BASIN_DIM_FT = 2_500.0


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class StageStoragePoint:
    elevation: float
    storage_cf: float
    water_surface_area_sf: float = 0.0
    bottom_area_sf: float = 0.0
    average_area_sf: float = 0.0


@dataclass
class BasinGeometry:
    bottom_length_ft: float
    bottom_width_ft: float
    depth_ft: float
    side_slope_h_to_1v: float
    freeboard_ft: float = DEFAULT_FREEBOARD_FT

    @property
    def bottom_area_sf(self) -> float:
        return self.bottom_length_ft * self.bottom_width_ft

    @property
    def top_length_ft(self) -> float:
        return self.bottom_length_ft + 2.0 * self.side_slope_h_to_1v * self.depth_ft

    @property
    def top_width_ft(self) -> float:
        return self.bottom_width_ft + 2.0 * self.side_slope_h_to_1v * self.depth_ft

    @property
    def top_area_sf(self) -> float:
        return self.top_length_ft * self.top_width_ft

    @property
    def excavation_depth_ft(self) -> float:
        return self.depth_ft + self.freeboard_ft


@dataclass
class DetentionAlternative:
    name: str
    geometry: BasinGeometry
    storage_cf: float
    required_storage_cf: float
    excess_storage_cf: float
    drawdown_hours: float
    score: float
    notes: List[str] = field(default_factory=list)


@dataclass
class DetentionResult:
    success: bool
    required_storage_cf: float = 0.0
    recommended_bottom_area_sf: float = 0.0
    recommended_geometry: Optional[BasinGeometry] = None
    provided_geometry_storage_cf: float = 0.0
    drawdown_hours: float = 0.0
    stage_storage_curve: List[StageStoragePoint] = field(default_factory=list)
    alternatives: List[DetentionAlternative] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    summary: Dict[str, float] = field(default_factory=dict)


@dataclass
class DetentionRoutingPoint:
    time_hr: float
    inflow_cfs: float
    outflow_cfs: float
    storage_cf: float
    water_surface_elev_ft: float
    interval_inflow_volume_cf: float = 0.0
    interval_outflow_volume_cf: float = 0.0
    continuity_residual_cf: float = 0.0


# =============================================================================
# BASIC HELPERS
# =============================================================================

def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        result = float(value)
        return result if math.isfinite(result) else float(default)
    except Exception:
        return float(default)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _frustum_volume_cf(bottom_area_sf: float, top_area_sf: float, depth_ft: float) -> float:
    """
    Prismoidal/frustum-style volume approximation for a basin slice.
    """
    if depth_ft <= 0.0:
        return 0.0
    mid_area = math.sqrt(max(bottom_area_sf, 0.0) * max(top_area_sf, 0.0))
    return depth_ft / 3.0 * (bottom_area_sf + top_area_sf + mid_area)


def _basin_area_at_depth(bottom_length_ft: float, bottom_width_ft: float, side_slope_h_to_1v: float, depth_ft: float) -> float:
    if depth_ft <= 0.0:
        return _clamp(bottom_length_ft, 0.0, DEFAULT_MAX_BASIN_DIM_FT) * _clamp(bottom_width_ft, 0.0, DEFAULT_MAX_BASIN_DIM_FT)
    top_length = _clamp(bottom_length_ft + 2.0 * side_slope_h_to_1v * depth_ft, 0.0, DEFAULT_MAX_BASIN_DIM_FT)
    top_width = _clamp(bottom_width_ft + 2.0 * side_slope_h_to_1v * depth_ft, 0.0, DEFAULT_MAX_BASIN_DIM_FT)
    return max(0.0, top_length) * max(0.0, top_width)


# =============================================================================
# CORE STORAGE CALCS
# =============================================================================

def compute_required_storage_cf(inflow_cfs: float, release_cfs: float, storage_hours: float = DEFAULT_STORAGE_HOURS) -> float:
    inflow_cfs = max(0.0, _safe_float(inflow_cfs, 0.0))
    release_cfs = max(0.0, min(_safe_float(release_cfs, 0.0), inflow_cfs))
    storage_hours = max(0.0, _safe_float(storage_hours, DEFAULT_STORAGE_HOURS))
    net = max(0.0, inflow_cfs - release_cfs)
    return net * storage_hours * 3600.0


def basin_storage_cf(
    bottom_length_ft: float,
    bottom_width_ft: float,
    depth_ft: float,
    side_slope_h_to_1v: float = DEFAULT_SIDE_SLOPE_H,
) -> float:
    # Integral of (L+2*s*z)*(W+2*s*z), not a similar-frustum approximation.
    values = (bottom_length_ft, bottom_width_ft, depth_ft, side_slope_h_to_1v)
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("Basin dimensions, depth and side slope must be finite and nonnegative.")
    if bottom_length_ft <= 0 or bottom_width_ft <= 0:
        raise ValueError("Basin bottom dimensions must be positive.")
    length, width, depth, slope = values
    if max(length + 2*slope*depth, width + 2*slope*depth) > DEFAULT_MAX_BASIN_DIM_FT:
        raise ValueError("Basin dimensions exceed supported geometry bounds.")
    volume = length*width*depth + slope*(length+width)*depth**2 + (4.0/3.0)*slope**2*depth**3
    if not math.isfinite(volume):
        raise ValueError("Basin storage exceeds finite numeric range.")
    return volume


def generate_stage_storage_curve(
    geometry: BasinGeometry,
    *,
    base_elevation: float = 100.0,
    stage_increment_ft: float = DEFAULT_STAGE_INCREMENT_FT,
) -> List[StageStoragePoint]:
    if type(stage_increment_ft) not in (int, float) or not math.isfinite(stage_increment_ft) or stage_increment_ft <= 0:
        raise ValueError("Stage increment must be positive and finite.")
    if type(base_elevation) not in (int, float) or not math.isfinite(base_elevation):
        raise ValueError("Base elevation must be finite.")
    basin_storage_cf(geometry.bottom_length_ft, geometry.bottom_width_ft, geometry.depth_ft, geometry.side_slope_h_to_1v)
    intervals = geometry.depth_ft / stage_increment_ft
    if not math.isfinite(intervals) or intervals > 100000:
        raise ValueError("Stage curve exceeds supported sample count.")
    count = math.ceil(intervals)
    # Every stage, including a fractional terminal interval, uses the same integral.
    return [StageStoragePoint(
        elevation=base_elevation + depth,
        storage_cf=basin_storage_cf(geometry.bottom_length_ft, geometry.bottom_width_ft, depth, geometry.side_slope_h_to_1v),
        water_surface_area_sf=_basin_area_at_depth(geometry.bottom_length_ft, geometry.bottom_width_ft, geometry.side_slope_h_to_1v, depth),
        bottom_area_sf=geometry.bottom_area_sf,
        average_area_sf=(geometry.bottom_area_sf + _basin_area_at_depth(geometry.bottom_length_ft, geometry.bottom_width_ft, geometry.side_slope_h_to_1v, depth))/2.0,
    ) for depth in [min(i*stage_increment_ft, geometry.depth_ft) for i in range(count+1)]]


def estimate_drawdown_hours(storage_cf: float, release_cfs: float) -> float:
    release_cfs = max(0.0, _safe_float(release_cfs, 0.0))
    storage_cf = max(0.0, _safe_float(storage_cf, 0.0))
    if release_cfs <= 0.0:
        return float("inf")
    return storage_cf / release_cfs / 3600.0


def route_detention_level_pool(
    inflow_hydrograph: Sequence[Tuple[float, float]],
    stage_storage_curve: Sequence[StageStoragePoint],
    *,
    outlet_coefficient: float = 0.6,
    outlet_area_sf: float = 1.0,
    outlet_invert_elev: Optional[float] = None,
) -> List[DetentionRoutingPoint]:
    """Bounded backward-Euler continuity routing, seconds internally.

    Piecewise-linear inflow and storage/stage interpolation; one orifice outlet,
    no tailwater/backwater/overflow solver. Exceeding the supplied curve fails
    explicitly, never a capped elevation with hidden excess storage. Each output
    includes interval water volumes for independent continuity checking.
    """
    if len(inflow_hydrograph) < 2 or len(stage_storage_curve) < 2:
        raise ValueError("Routing needs at least two hydrograph and storage-curve samples.")
    curve = list(stage_storage_curve)
    def finite(value):
        return type(value) in (int, float) and math.isfinite(value)
    if any(not finite(v) or v < 0 for v in (outlet_coefficient, outlet_area_sf)):
        raise ValueError("Outlet coefficient and area must be finite and nonnegative.")
    if any(not finite(p.storage_cf) or p.storage_cf < 0 or not finite(p.elevation) for p in curve):
        raise ValueError("Storage curve must be finite and nonnegative.")
    if curve[0].storage_cf != 0 or any(b.storage_cf <= a.storage_cf or b.elevation <= a.elevation for a,b in zip(curve,curve[1:])):
        raise ValueError("Storage curve must start dry and increase strictly in stage and storage.")
    if any(len(row) != 2 or not finite(row[0]) or not finite(row[1]) or row[0] < 0 or row[1] < 0 for row in inflow_hydrograph):
        raise ValueError("Hydrograph times and flows must be finite and nonnegative.")
    if any(b[0] <= a[0] for a,b in zip(inflow_hydrograph,inflow_hydrograph[1:])):
        raise ValueError("Hydrograph time must increase strictly.")
    invert = outlet_invert_elev if outlet_invert_elev is not None else curve[0].elevation
    if not finite(invert) or invert < curve[0].elevation:
        raise ValueError("Outlet invert must be finite and at or above the dry basin elevation.")

    def elevation_for_storage(storage: float) -> float:
        if storage <= curve[0].storage_cf:
            return curve[0].elevation
        for idx in range(1, len(curve)):
            a = curve[idx - 1]
            b = curve[idx]
            if storage <= b.storage_cf:
                frac = (storage - a.storage_cf) / max(b.storage_cf - a.storage_cf, 1e-9)
                return a.elevation + frac * (b.elevation - a.elevation)
        raise ValueError("Routing exceeds supported stage/storage curve; overflow analysis required.")

    def outflow(storage: float) -> float:
        elev = elevation_for_storage(storage)
        head = max(0.0, elev - invert)
        flow = outlet_coefficient * outlet_area_sf * math.sqrt(2.0 * 32.2 * head)
        if not math.isfinite(flow):
            raise ValueError("Outlet calculation exceeds finite numeric range.")
        return max(0.0, flow)

    routed: List[DetentionRoutingPoint] = []
    storage = 0.0
    first_time, first_inflow = inflow_hydrograph[0]
    routed.append(DetentionRoutingPoint(first_time, max(0.0, first_inflow), outflow(storage), storage, elevation_for_storage(storage)))
    total_steps = 0
    for idx in range(1, len(inflow_hydrograph)):
        t0, q0 = inflow_hydrograph[idx - 1]
        t1, q1 = inflow_hydrograph[idx]
        seconds = (t1-t0)*3600.0
        if not math.isfinite(seconds) or seconds > 60.0*(100000-total_steps):
            raise ValueError("Routing exceeds supported timestep budget.")
        count = max(1, math.ceil(seconds/60.0))
        total_steps += count
        if total_steps > 100000:
            raise ValueError("Routing exceeds supported timestep budget.")
        dt = seconds/count
        start_storage = storage
        inflow_volume = outflow_volume = 0.0
        for step in range(count):
            average = q0 + (q1-q0)*(step+.5)/count
            available = storage + average*dt
            if not math.isfinite(available):
                raise ValueError("Routing inflow volume exceeds finite numeric range.")
            maximum = curve[-1].storage_cf
            if available > maximum + dt*outflow(maximum) + 1e-7:
                raise ValueError("Routing exceeds supported storage; explicit overflow analysis required.")
            lo, hi = 0.0, min(available, maximum)
            for _ in range(70):
                mid = (lo+hi)/2.0
                if mid + dt*outflow(mid) > available: hi = mid
                else: lo = mid
            new_storage = (lo+hi)/2.0
            discharged = available-new_storage
            inflow_volume += average*dt
            outflow_volume += discharged
            storage = new_storage
        residual = start_storage+inflow_volume-outflow_volume-storage
        routed.append(DetentionRoutingPoint(t1,q1,outflow(storage),storage,elevation_for_storage(storage),inflow_volume,outflow_volume,residual))
    return routed


# =============================================================================
# GEOMETRY SIZING
# =============================================================================

def recommend_basin_geometry(
    required_storage_cf: float,
    *,
    max_depth_ft: float = DEFAULT_MAX_DEPTH_FT,
    side_slope_h_to_1v: float = DEFAULT_SIDE_SLOPE_H,
    length_width_ratio: float = DEFAULT_BOTTOM_LENGTH_WIDTH_RATIO,
    freeboard_ft: float = DEFAULT_FREEBOARD_FT,
) -> BasinGeometry:
    required_storage_cf = _clamp(_safe_float(required_storage_cf, 0.0), 0.0, DEFAULT_MAX_STORAGE_CF)
    max_depth_ft = max(1.0, _safe_float(max_depth_ft, DEFAULT_MAX_DEPTH_FT))
    side_slope_h_to_1v = max(1.0, _safe_float(side_slope_h_to_1v, DEFAULT_SIDE_SLOPE_H))
    length_width_ratio = max(1.0, _safe_float(length_width_ratio, DEFAULT_BOTTOM_LENGTH_WIDTH_RATIO))

    if required_storage_cf <= 0.0:
        return BasinGeometry(
            bottom_length_ft=DEFAULT_MIN_BOTTOM_DIM_FT * length_width_ratio,
            bottom_width_ft=DEFAULT_MIN_BOTTOM_DIM_FT,
            depth_ft=max_depth_ft,
            side_slope_h_to_1v=side_slope_h_to_1v,
            freeboard_ft=freeboard_ft,
        )

    target_depth = max_depth_ft
    lo = DEFAULT_MIN_BOTTOM_DIM_FT
    hi = min(DEFAULT_MAX_BASIN_DIM_FT, math.sqrt(required_storage_cf) * 5.0 + 200.0)

    best_width = hi
    for _ in range(40):
        width = (lo + hi) / 2.0
        length = width * length_width_ratio
        storage = basin_storage_cf(length, width, target_depth, side_slope_h_to_1v)
        if storage >= required_storage_cf:
            best_width = width
            hi = width
        else:
            lo = width

    best_length = best_width * length_width_ratio
    return BasinGeometry(
        bottom_length_ft=max(DEFAULT_MIN_BOTTOM_DIM_FT, best_length),
        bottom_width_ft=max(DEFAULT_MIN_BOTTOM_DIM_FT, best_width),
        depth_ft=target_depth,
        side_slope_h_to_1v=side_slope_h_to_1v,
        freeboard_ft=freeboard_ft,
    )


def evaluate_provided_basin(
    required_storage_cf: float,
    *,
    bottom_length_ft: float,
    bottom_width_ft: float,
    depth_ft: float,
    side_slope_h_to_1v: float = DEFAULT_SIDE_SLOPE_H,
    freeboard_ft: float = DEFAULT_FREEBOARD_FT,
    release_cfs: float = 0.0,
) -> DetentionResult:
    geometry = BasinGeometry(
        bottom_length_ft=max(DEFAULT_MIN_BOTTOM_DIM_FT, _safe_float(bottom_length_ft, DEFAULT_MIN_BOTTOM_DIM_FT)),
        bottom_width_ft=max(DEFAULT_MIN_BOTTOM_DIM_FT, _safe_float(bottom_width_ft, DEFAULT_MIN_BOTTOM_DIM_FT)),
        depth_ft=max(0.1, _safe_float(depth_ft, DEFAULT_MAX_DEPTH_FT)),
        side_slope_h_to_1v=max(1.0, _safe_float(side_slope_h_to_1v, DEFAULT_SIDE_SLOPE_H)),
        freeboard_ft=max(0.0, _safe_float(freeboard_ft, DEFAULT_FREEBOARD_FT)),
    )
    storage = basin_storage_cf(
        geometry.bottom_length_ft,
        geometry.bottom_width_ft,
        geometry.depth_ft,
        geometry.side_slope_h_to_1v,
    )
    curve = generate_stage_storage_curve(geometry)
    drawdown = estimate_drawdown_hours(storage, release_cfs)
    warnings: List[str] = []

    if storage < required_storage_cf:
        warnings.append("Provided basin geometry does not meet required storage.")
    if drawdown != float("inf") and drawdown > DEFAULT_MAX_DRAWDOWN_HOURS:
        warnings.append("Estimated drawdown exceeds concept target duration.")
    if geometry.depth_ft > DEFAULT_MAX_DEPTH_FT:
        warnings.append("Provided basin depth exceeds default concept maximum depth.")

    return DetentionResult(
        success=storage >= required_storage_cf,
        required_storage_cf=required_storage_cf,
        recommended_bottom_area_sf=geometry.bottom_area_sf,
        recommended_geometry=geometry,
        provided_geometry_storage_cf=storage,
        drawdown_hours=drawdown,
        stage_storage_curve=curve,
        warnings=warnings,
        summary={
            "required_storage_cf": required_storage_cf,
            "provided_storage_cf": storage,
            "bottom_area_sf": geometry.bottom_area_sf,
            "top_area_sf": geometry.top_area_sf,
            "depth_ft": geometry.depth_ft,
            "drawdown_hours": drawdown,
        },
    )


def generate_detention_alternatives(
    required_storage_cf: float,
    release_cfs: float,
    *,
    side_slopes: Sequence[float] = (3.0, 4.0, 5.0),
    depths_ft: Sequence[float] = (4.0, 5.0, 6.0),
    length_width_ratios: Sequence[float] = (1.2, 1.5, 2.0),
) -> List[DetentionAlternative]:
    required_storage_cf = max(0.0, _safe_float(required_storage_cf, 0.0))
    alternatives: List[DetentionAlternative] = []

    for ss in side_slopes:
        for depth in depths_ft:
            for ratio in length_width_ratios:
                geom = recommend_basin_geometry(
                    required_storage_cf,
                    max_depth_ft=depth,
                    side_slope_h_to_1v=ss,
                    length_width_ratio=ratio,
                )
                storage = basin_storage_cf(
                    geom.bottom_length_ft,
                    geom.bottom_width_ft,
                    geom.depth_ft,
                    geom.side_slope_h_to_1v,
                )
                excess = storage - required_storage_cf
                drawdown = estimate_drawdown_hours(storage, release_cfs)

                score = 100.0
                score -= abs(excess) / max(1.0, required_storage_cf) * 30.0
                score -= max(0.0, geom.bottom_area_sf / 1000.0)
                if drawdown == float("inf"):
                    score -= 50.0
                else:
                    score -= max(0.0, drawdown - DEFAULT_MAX_DRAWDOWN_HOURS) * 1.5

                notes: List[str] = []
                if excess >= 0.0:
                    notes.append("Meets required storage.")
                else:
                    notes.append("Does not meet required storage.")
                if drawdown != float("inf") and drawdown <= DEFAULT_MAX_DRAWDOWN_HOURS:
                    notes.append("Drawdown is within concept target.")
                elif drawdown == float("inf"):
                    notes.append("No release; drawdown cannot be estimated.")
                else:
                    notes.append("Drawdown exceeds concept target.")

                alternatives.append(
                    DetentionAlternative(
                        name=f"D{depth:.1f}_SS{ss:.1f}_R{ratio:.1f}",
                        geometry=geom,
                        storage_cf=storage,
                        required_storage_cf=required_storage_cf,
                        excess_storage_cf=excess,
                        drawdown_hours=drawdown,
                        score=score,
                        notes=notes,
                    )
                )

    alternatives.sort(key=lambda a: a.score, reverse=True)
    return alternatives


# =============================================================================
# ORIGINAL ENTRYPOINT PRESERVED + EXPANDED
# =============================================================================

def concept_detention_size(inflow_cfs: float, release_cfs: float, storage_hours: float = DEFAULT_STORAGE_HOURS) -> DetentionResult:
    """
    Preserved original public entrypoint, now greatly expanded.

    Original behavior preserved:
    - required storage = (inflow - release) * storage time
    - recommended bottom area returned

    New behavior added:
    - recommended basin geometry
    - stage-storage curve
    - drawdown time
    - alternative basin concepts
    """
    inflow_cfs = max(0.0, _safe_float(inflow_cfs, 0.0))
    release_cfs = max(0.0, min(_safe_float(release_cfs, 0.0), inflow_cfs))
    storage_hours = max(0.0, _safe_float(storage_hours, DEFAULT_STORAGE_HOURS))

    required = compute_required_storage_cf(inflow_cfs, release_cfs, storage_hours)
    warnings: List[str] = []

    if required <= 0.0:
        warnings.append("No detention storage required by this concept check.")

    geometry = recommend_basin_geometry(required)
    stage_curve = generate_stage_storage_curve(geometry)
    drawdown = estimate_drawdown_hours(required, release_cfs)
    alternatives = generate_detention_alternatives(required, release_cfs)[:6]

    if drawdown == float("inf") and required > 0.0:
        warnings.append("No release rate available; drawdown time is infinite.")
    elif drawdown > DEFAULT_MAX_DRAWDOWN_HOURS:
        warnings.append("Estimated drawdown exceeds concept target duration.")

    return DetentionResult(
        success=True,
        required_storage_cf=required,
        recommended_bottom_area_sf=geometry.bottom_area_sf if required > 0.0 else 0.0,
        recommended_geometry=geometry,
        provided_geometry_storage_cf=basin_storage_cf(
            geometry.bottom_length_ft,
            geometry.bottom_width_ft,
            geometry.depth_ft,
            geometry.side_slope_h_to_1v,
        ),
        drawdown_hours=drawdown,
        stage_storage_curve=stage_curve,
        alternatives=alternatives,
        warnings=warnings,
        summary={
            "inflow_cfs": inflow_cfs,
            "release_cfs": release_cfs,
            "storage_hours": storage_hours,
            "required_storage_cf": required,
            "recommended_bottom_area_sf": geometry.bottom_area_sf if required > 0.0 else 0.0,
            "recommended_top_area_sf": geometry.top_area_sf,
            "recommended_depth_ft": geometry.depth_ft,
            "estimated_drawdown_hours": drawdown,
        },
    )
