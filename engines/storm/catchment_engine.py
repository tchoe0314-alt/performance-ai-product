
from __future__ import annotations

"""
engines/storm/catchment_engine.py (TRUE MAX VERSION)

Purpose
-------
Catchment delineation, runoff estimation, inlet assignment support, and
planner-ready drainage subarea generation for the storm module.

This engine fills the gap between:
- drainage_engine.py (surface behavior / flow logic)
- inlet_engine.py (collection point selection)
- storm_network_engine.py (pipe/structure network)
- detention / basin logic

Design intent
-------------
- concept-to-preliminary engineering behavior
- deterministic and explainable
- future-ready for richer raster/surface delineation later
- no toy placeholder logic
"""

from dataclasses import dataclass, field
from math import hypot
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .storm_types import (
    CatchmentSurfaceBreakdown,
    StormCatchment,
    StormPoint,
)


# =============================================================================
# DEFAULTS
# =============================================================================

DEFAULT_IMPERVIOUS_RUNOFF_C = 0.95
DEFAULT_ROOF_RUNOFF_C = 0.95
DEFAULT_PAVEMENT_RUNOFF_C = 0.90
DEFAULT_LANDSCAPED_RUNOFF_C = 0.30
DEFAULT_MIXED_SITE_RUNOFF_C = 0.70

DEFAULT_TC_MIN_MINUTES = 5.0
DEFAULT_TC_MAX_MINUTES = 30.0
DEFAULT_FLOW_PATH_FACTOR = 1.20
DEFAULT_INTENSITY_COEFF = 180.0   # concept IDF-like coefficient
DEFAULT_INTENSITY_EXP = 0.60

DEFAULT_MIN_CATCHMENT_AREA_SF = 500.0
DEFAULT_MAX_CATCHMENTS = 50
DEFAULT_LOW_POINT_SEARCH_RADIUS_FT = 200.0


# =============================================================================
# EXTRA MODELS
# =============================================================================

@dataclass
class SurfaceAreaBreakdownInput:
    roof_area_sf: float = 0.0
    pavement_area_sf: float = 0.0
    landscaped_area_sf: float = 0.0
    impervious_area_sf: float = 0.0
    total_area_sf: float = 0.0


@dataclass
class CatchmentCandidate:
    name: str
    centroid: StormPoint
    low_point: Optional[StormPoint] = None
    area_sf: float = 0.0
    boundary_points: List[Tuple[float, float]] = field(default_factory=list)
    surface_input: SurfaceAreaBreakdownInput = field(default_factory=SurfaceAreaBreakdownInput)
    flow_path_length_ft: float = 0.0
    runoff_c_override: Optional[float] = None
    tc_minutes_override: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CatchmentRequest:
    candidates: List[CatchmentCandidate] = field(default_factory=list)
    low_points: List[StormPoint] = field(default_factory=list)
    max_catchments: int = DEFAULT_MAX_CATCHMENTS
    min_catchment_area_sf: float = DEFAULT_MIN_CATCHMENT_AREA_SF
    default_runoff_c: float = DEFAULT_MIXED_SITE_RUNOFF_C
    default_flow_path_factor: float = DEFAULT_FLOW_PATH_FACTOR
    min_tc_minutes: float = DEFAULT_TC_MIN_MINUTES
    max_tc_minutes: float = DEFAULT_TC_MAX_MINUTES
    intensity_coeff: float = DEFAULT_INTENSITY_COEFF
    intensity_exp: float = DEFAULT_INTENSITY_EXP
    auto_assign_outlet_low_points: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CatchmentExplain:
    key_logic: List[str] = field(default_factory=list)
    selected_catchments: List[Dict[str, Any]] = field(default_factory=list)
    rejected_candidates: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_logic": list(self.key_logic),
            "selected_catchments": [dict(x) for x in self.selected_catchments],
            "rejected_candidates": [dict(x) for x in self.rejected_candidates],
        }


@dataclass
class CatchmentEngineResult:
    success: bool
    catchments: List[StormCatchment] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    explain: CatchmentExplain = field(default_factory=CatchmentExplain)
    optimize_hooks: Dict[str, Any] = field(default_factory=dict)
    inlet_hooks: Dict[str, Any] = field(default_factory=dict)
    conflict_hooks: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# ENGINE
# =============================================================================

class CatchmentEngine:
    """
    True-max catchment engine.

    Responsibilities:
    - normalize candidate subareas
    - estimate weighted runoff C
    - estimate Tc and rainfall intensity
    - compute Rational Method peak runoff
    - assign nearest low points / outlet collection hints
    - generate explain/optimize/inlet-ready outputs
    """

    def build_catchments(self, request: CatchmentRequest) -> CatchmentEngineResult:
        warnings: List[str] = []
        catchments: List[StormCatchment] = []
        rejected: List[Dict[str, Any]] = []

        if not request.candidates:
            return CatchmentEngineResult(
                success=False,
                warnings=["No catchment candidates were provided."],
            )

        candidates = list(request.candidates)[: max(1, request.max_catchments)]

        for cand in candidates:
            area_sf = max(0.0, self._resolve_area(cand))
            if area_sf < request.min_catchment_area_sf:
                rejected.append({
                    "name": cand.name,
                    "reason": "area_below_minimum",
                    "area_sf": round(area_sf, 3),
                })
                continue

            breakdown = self._build_surface_breakdown(cand, request.default_runoff_c)
            tc = self._estimate_tc_minutes(cand, request)
            intensity = self._estimate_intensity_in_hr(tc, request)
            runoff_c = cand.runoff_c_override if cand.runoff_c_override is not None else breakdown.weighted_runoff_c
            peak_q = self._rational_peak_runoff_cfs(runoff_c, intensity, area_sf)

            low_point = cand.low_point
            if low_point is None and request.auto_assign_outlet_low_points:
                low_point = self._nearest_low_point(cand.centroid, request.low_points)

            catch = StormCatchment(
                name=cand.name,
                area_sf=round(area_sf, 3),
                runoff_c=round(runoff_c, 4),
                tc_minutes=round(tc, 3),
                intensity_in_hr=round(intensity, 3),
                peak_runoff_cfs=round(peak_q, 3),
                outlet_node_name=low_point.label if low_point else None,
                centroid=self._clone_point(cand.centroid),
                boundary_points=list(cand.boundary_points),
                surface_breakdown=breakdown,
                warnings=[],
                meta={
                    **dict(cand.meta),
                    "candidate_name": cand.name,
                    "assigned_low_point": low_point.label if low_point else None,
                    "flow_path_length_ft": round(self._resolve_flow_path_length(cand, request), 3),
                },
            )

            if low_point is None:
                catch.warnings.append("No low point/outlet hint was assigned to catchment.")
            if peak_q <= 0.0:
                catch.warnings.append("Catchment peak runoff resolved to zero.")
            if tc <= request.min_tc_minutes:
                catch.warnings.append("Tc hit lower bound; review flow path assumptions.")
            if tc >= request.max_tc_minutes:
                catch.warnings.append("Tc hit upper bound; review candidate geometry assumptions.")

            catchments.append(catch)

        if not catchments:
            warnings.append("No valid catchments were generated.")

        summary = self._build_summary(catchments, warnings, rejected)
        explain = self._build_explain(catchments, rejected)
        optimize_hooks = self._build_optimize_hooks(catchments)
        inlet_hooks = self._build_inlet_hooks(catchments)
        conflict_hooks = self._build_conflict_hooks(catchments)

        return CatchmentEngineResult(
            success=len(catchments) > 0,
            catchments=catchments,
            warnings=warnings,
            summary=summary,
            explain=explain,
            optimize_hooks=optimize_hooks,
            inlet_hooks=inlet_hooks,
            conflict_hooks=conflict_hooks,
        )

    # =========================================================================
    # CORE CALCS
    # =========================================================================

    def _resolve_area(self, cand: CatchmentCandidate) -> float:
        if cand.area_sf > 0.0:
            return cand.area_sf
        s = cand.surface_input
        if s.total_area_sf > 0.0:
            return s.total_area_sf
        subtotal = max(0.0, s.roof_area_sf) + max(0.0, s.pavement_area_sf) + max(0.0, s.landscaped_area_sf)
        if subtotal > 0.0:
            return subtotal
        if cand.boundary_points:
            return self._polygon_area(cand.boundary_points)
        return 0.0

    def _build_surface_breakdown(self, cand: CatchmentCandidate, default_runoff_c: float) -> CatchmentSurfaceBreakdown:
        s = cand.surface_input
        total_area = self._resolve_area(cand)
        roof = max(0.0, s.roof_area_sf)
        pav = max(0.0, s.pavement_area_sf)
        land = max(0.0, s.landscaped_area_sf)
        imp = max(0.0, s.impervious_area_sf)

        # if only impervious + total known, infer landscaped remainder
        if roof + pav + land <= 0.0 and total_area > 0.0:
            if imp > 0.0:
                pav = imp
                land = max(0.0, total_area - imp)
            else:
                pav = total_area * 0.5
                land = total_area * 0.5

        if roof + pav + land < total_area:
            land += max(0.0, total_area - (roof + pav + land))

        weighted_num = (
            roof * DEFAULT_ROOF_RUNOFF_C
            + pav * DEFAULT_PAVEMENT_RUNOFF_C
            + land * DEFAULT_LANDSCAPED_RUNOFF_C
        )
        weighted = (weighted_num / total_area) if total_area > 0 else default_runoff_c

        return CatchmentSurfaceBreakdown(
            impervious_area_sf=round(roof + pav, 3),
            roof_area_sf=round(roof, 3),
            pavement_area_sf=round(pav, 3),
            landscaped_area_sf=round(land, 3),
            weighted_runoff_c=round(weighted, 4),
            tc_minutes=0.0,
            intensity_in_hr=0.0,
        )

    def _resolve_flow_path_length(self, cand: CatchmentCandidate, request: CatchmentRequest) -> float:
        if cand.flow_path_length_ft > 0.0:
            return cand.flow_path_length_ft
        if cand.low_point is not None:
            return hypot(cand.centroid.x - cand.low_point.x, cand.centroid.y - cand.low_point.y) * request.default_flow_path_factor
        if cand.boundary_points:
            # simple size proxy
            area = self._polygon_area(cand.boundary_points)
            return max(20.0, (area ** 0.5) * request.default_flow_path_factor)
        return 50.0

    def _estimate_tc_minutes(self, cand: CatchmentCandidate, request: CatchmentRequest) -> float:
        if cand.tc_minutes_override is not None:
            return self._clamp(float(cand.tc_minutes_override), request.min_tc_minutes, request.max_tc_minutes)

        L = self._resolve_flow_path_length(cand, request)
        # concept proxy: longer path -> larger Tc
        tc = 4.0 + (L / 100.0) * 2.2
        return self._clamp(tc, request.min_tc_minutes, request.max_tc_minutes)

    def _estimate_intensity_in_hr(self, tc_minutes: float, request: CatchmentRequest) -> float:
        tc_minutes = max(1.0, tc_minutes)
        # concept IDF-like expression
        return request.intensity_coeff / (tc_minutes ** request.intensity_exp)

    def _rational_peak_runoff_cfs(self, runoff_c: float, intensity_in_hr: float, area_sf: float) -> float:
        area_ac = area_sf / 43560.0
        return runoff_c * intensity_in_hr * area_ac

    # =========================================================================
    # LOW POINT / GEOMETRY
    # =========================================================================

    def _nearest_low_point(self, centroid: StormPoint, low_points: Sequence[StormPoint]) -> Optional[StormPoint]:
        if not low_points:
            return None
        best = None
        best_d = float("inf")
        for p in low_points:
            d = hypot(centroid.x - p.x, centroid.y - p.y)
            if d < best_d:
                best = p
                best_d = d
        return self._clone_point(best) if best is not None else None

    def _clone_point(self, p: Optional[StormPoint]) -> Optional[StormPoint]:
        if p is None:
            return None
        return StormPoint(x=p.x, y=p.y, z=p.z, label=p.label, meta=dict(p.meta))

    def _polygon_area(self, pts: Sequence[Tuple[float, float]]) -> float:
        if len(pts) < 3:
            return 0.0
        area = 0.0
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            area += x1 * y2 - x2 * y1
        return abs(area) * 0.5

    def _clamp(self, value: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, value))

    # =========================================================================
    # OUTPUTS
    # =========================================================================

    def _build_summary(
        self,
        catchments: Sequence[StormCatchment],
        warnings: Sequence[str],
        rejected: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        total_area = sum(c.area_sf for c in catchments)
        total_peak = sum(c.peak_runoff_cfs for c in catchments)
        avg_tc = (sum(c.tc_minutes for c in catchments) / len(catchments)) if catchments else 0.0
        weighted_c = (
            sum(c.runoff_c * c.area_sf for c in catchments) / total_area
            if total_area > 0 else 0.0
        )
        return {
            "catchment_count": len(catchments),
            "rejected_candidate_count": len(rejected),
            "total_area_sf": round(total_area, 3),
            "total_peak_runoff_cfs": round(total_peak, 3),
            "average_tc_minutes": round(avg_tc, 3),
            "weighted_runoff_c": round(weighted_c, 4),
            "warning_count": len(warnings) + sum(len(c.warnings) for c in catchments),
        }

    def _build_explain(
        self,
        catchments: Sequence[StormCatchment],
        rejected: Sequence[Dict[str, Any]],
    ) -> CatchmentExplain:
        explain = CatchmentExplain()
        explain.key_logic = [
            "Candidate subareas were normalized into drainage catchments.",
            "Weighted runoff coefficients were estimated from roof, pavement, and landscaped surface areas.",
            "Time of concentration was estimated from flow path length with bounded concept limits.",
            "Rational Method peak runoff was computed for each catchment.",
            "Nearest low points were assigned as collection/outlet hints where available.",
        ]
        explain.selected_catchments = [
            {
                "name": c.name,
                "area_sf": c.area_sf,
                "runoff_c": c.runoff_c,
                "tc_minutes": c.tc_minutes,
                "intensity_in_hr": c.intensity_in_hr,
                "peak_runoff_cfs": c.peak_runoff_cfs,
                "outlet_node_name": c.outlet_node_name,
            }
            for c in catchments
        ]
        explain.rejected_candidates = [dict(x) for x in rejected[:25]]
        return explain

    def _build_optimize_hooks(self, catchments: Sequence[StormCatchment]) -> Dict[str, Any]:
        return {
            "penalties": {
                "high_runoff_penalty": round(sum(c.peak_runoff_cfs for c in catchments) * 2.0, 3),
                "high_intensity_penalty": round(sum(c.intensity_in_hr for c in catchments) / 10.0, 3),
            },
            "candidate_improvements": [
                "reduce impervious area in high-runoff catchments",
                "split oversized catchments into more collection zones",
                "shorten flow paths to improve collection control",
                "place additional inlets near highest-runoff low points",
            ],
        }

    def _build_inlet_hooks(self, catchments: Sequence[StormCatchment]) -> Dict[str, Any]:
        return {
            "candidate_points": [
                {
                    "name": c.name,
                    "x": c.centroid.x if c.centroid else 0.0,
                    "y": c.centroid.y if c.centroid else 0.0,
                    "z": c.centroid.z if c.centroid else None,
                    "catchment_name": c.name,
                    "tributary_area_sf": c.area_sf,
                    "runoff_cfs": c.peak_runoff_cfs,
                    "low_point_score": round((c.peak_runoff_cfs * 0.5) + (c.area_sf / 10000.0), 4),
                }
                for c in catchments
                if c.centroid is not None
            ]
        }

    def _build_conflict_hooks(self, catchments: Sequence[StormCatchment]) -> Dict[str, Any]:
        return {
            "catchment_boundaries": [
                {
                    "name": c.name,
                    "boundary_points": list(c.boundary_points),
                    "area_sf": c.area_sf,
                }
                for c in catchments
                if c.boundary_points
            ]
        }


def build_catchments(request: CatchmentRequest) -> CatchmentEngineResult:
    return CatchmentEngine().build_catchments(request)
