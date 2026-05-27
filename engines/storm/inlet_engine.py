
from __future__ import annotations

"""
engines/storm/inlet_engine.py (TRUE MAX VERSION)

Purpose
-------
Storm inlet placement, capture estimation, spacing control, and preliminary
collection-point generation for the storm module.

This engine is responsible for:
- converting low points / candidate points into inlet structures
- enforcing spacing and placement logic
- estimating concept capture / bypass behavior
- identifying sag vs on-grade inlet roles
- producing planner / network / compliance / explain-ready outputs

Design intent
-------------
- Works as a strong concept-to-preliminary inlet engine
- Integrates with storm_types.py data models
- Deterministic and explainable
- Ready for future surface/gutter/hydraulic deepening
"""

from dataclasses import dataclass, field
from math import hypot, sqrt
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .storm_types import (
    InletCaptureResult,
    InletPlacementRequest,
    InletPlacementResult,
    InletType,
    StormCatchment,
    StormInlet,
    StormNodeType,
    StormPoint,
)


# =============================================================================
# DEFAULTS
# =============================================================================

DEFAULT_MIN_INLET_SPACING_FT = 20.0
DEFAULT_MAX_TRIBUTARY_AREA_SF_PER_INLET = 25000.0
DEFAULT_MAX_CAPTURE_CFS_PER_INLET = 10.0
DEFAULT_CURB_OPENING_FT = 3.0
DEFAULT_GRATE_LENGTH_FT = 4.0
DEFAULT_GRATE_WIDTH_FT = 2.0
DEFAULT_THROAT_WIDTH_FT = 2.0
DEFAULT_GUTTER_SPREAD_LIMIT_FT = 8.0
DEFAULT_SAG_CAPTURE_FACTOR = 0.95
DEFAULT_ON_GRADE_CAPTURE_FACTOR = 0.65
DEFAULT_BYPASS_FACTOR = 0.15
DEFAULT_GUTTER_N = 0.016
DEFAULT_GUTTER_CROSS_SLOPE = 0.02
DEFAULT_GUTTER_LONGITUDINAL_SLOPE = 0.005
DEFAULT_GRATE_OPEN_AREA_RATIO = 0.65
DEFAULT_WEIR_COEFF = 3.0
DEFAULT_ORIFICE_COEFF = 0.67


# =============================================================================
# EXTRA REQUEST / RESULT MODELS
# =============================================================================

@dataclass
class InletHydrologyRequest:
    candidate_points: List[StormPoint] = field(default_factory=list)
    catchments: List[StormCatchment] = field(default_factory=list)
    max_inlets: int = 12
    min_spacing_ft: float = DEFAULT_MIN_INLET_SPACING_FT
    default_inlet_type: str = InletType.AREA.value
    use_sag_points: bool = True
    use_on_grade_points: bool = True
    max_tributary_area_sf_per_inlet: float = DEFAULT_MAX_TRIBUTARY_AREA_SF_PER_INLET
    max_capture_cfs_per_inlet: float = DEFAULT_MAX_CAPTURE_CFS_PER_INLET
    gutter_spread_limit_ft: float = DEFAULT_GUTTER_SPREAD_LIMIT_FT
    prefer_low_point_score: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InletPlacementExplain:
    selected_count: int = 0
    rejected_count: int = 0
    key_logic: List[str] = field(default_factory=list)
    selected_inlets: List[Dict[str, Any]] = field(default_factory=list)
    rejected_candidates: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_count": self.selected_count,
            "rejected_count": self.rejected_count,
            "key_logic": list(self.key_logic),
            "selected_inlets": [dict(x) for x in self.selected_inlets],
            "rejected_candidates": [dict(x) for x in self.rejected_candidates],
        }


@dataclass
class InletEngineResult:
    success: bool
    inlets: List[StormInlet] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    explain: InletPlacementExplain = field(default_factory=InletPlacementExplain)
    optimize_hooks: Dict[str, Any] = field(default_factory=dict)
    conflict_hooks: Dict[str, Any] = field(default_factory=dict)

    def to_placement_result(self) -> InletPlacementResult:
        return InletPlacementResult(
            success=self.success,
            inlets=list(self.inlets),
            warnings=list(self.warnings),
            summary=dict(self.summary),
        )


# =============================================================================
# ENGINE
# =============================================================================

class InletEngine:
    """
    True-max inlet placement engine.

    Current strengths:
    - low-point-driven placement
    - spacing enforcement
    - catchment assignment hooks
    - capture/bypass concept logic
    - sag/on-grade logic
    - planner/network-ready metadata
    """

    def place_inlets(
        self,
        request: InletPlacementRequest,
    ) -> InletEngineResult:
        expanded = InletHydrologyRequest(
            candidate_points=list(request.candidate_points),
            max_inlets=request.max_inlets,
            min_spacing_ft=request.min_spacing_ft,
            default_inlet_type=request.default_inlet_type,
            use_sag_points=request.use_sag_points,
            use_on_grade_points=request.use_on_grade_points,
            meta=dict(request.meta),
        )
        expanded.candidate_points = list(request.low_points) + [p for p in request.candidate_points if p not in request.low_points]
        return self.place_inlets_with_hydrology(expanded)

    def place_inlets_with_hydrology(
        self,
        request: InletHydrologyRequest,
    ) -> InletEngineResult:
        if request.max_inlets <= 0:
            return InletEngineResult(success=False, warnings=["max_inlets must be greater than zero."])

        candidates = self._normalize_candidates(request)
        selected: List[StormInlet] = []
        rejected: List[Dict[str, Any]] = []
        warnings: List[str] = []

        # sort strongest candidates first
        candidates.sort(
            key=lambda c: (
                c["sag_priority"],
                c["low_point_score"],
                c["runoff_cfs"],
                c["tributary_area_sf"],
            ),
            reverse=True,
        )

        for cand in candidates:
            if len(selected) >= request.max_inlets:
                rejected.append({
                    "name": cand["name"],
                    "reason": "max_inlets_reached",
                    "low_point_score": cand["low_point_score"],
                })
                continue

            if not self._passes_spacing(cand, selected, request.min_spacing_ft):
                rejected.append({
                    "name": cand["name"],
                    "reason": "spacing_conflict",
                    "low_point_score": cand["low_point_score"],
                })
                continue

            if cand["tributary_area_sf"] > request.max_tributary_area_sf_per_inlet:
                rejected.append({
                    "name": cand["name"],
                    "reason": "tributary_area_too_large",
                    "tributary_area_sf": cand["tributary_area_sf"],
                })
                continue

            inlet = self._build_inlet_from_candidate(cand, request)
            selected.append(inlet)

        if not selected:
            warnings.append("No inlets were selected from the available candidates.")

        # post-process sequencing, bypass, and summary
        self._assign_bypass_chain(selected)
        summary = self._build_summary(selected, warnings, rejected)
        explain = self._build_explain(selected, rejected)
        optimize_hooks = self._build_optimize_hooks(selected, rejected)
        conflict_hooks = self._build_conflict_hooks(selected)

        return InletEngineResult(
            success=len(selected) > 0,
            inlets=selected,
            warnings=warnings,
            summary=summary,
            explain=explain,
            optimize_hooks=optimize_hooks,
            conflict_hooks=conflict_hooks,
        )

    # =========================================================================
    # NORMALIZATION / CANDIDATE PREP
    # =========================================================================

    def _normalize_candidates(self, request: InletHydrologyRequest) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []

        # map catchments to candidate points by nearest centroid / point
        catchments = list(request.catchments)
        for idx, pt in enumerate(request.candidate_points, start=1):
            nearest_catch = self._nearest_catchment(pt, catchments)
            tributary_area_sf = nearest_catch.area_sf if nearest_catch else 0.0
            runoff_cfs = nearest_catch.peak_runoff_cfs if nearest_catch else 0.0

            low_point_score = self._compute_low_point_score(pt, nearest_catch)
            sag = self._is_sag_candidate(pt, nearest_catch, request)

            candidates.append({
                "name": pt.label or f"INLET-{idx}",
                "point": pt,
                "tributary_area_sf": tributary_area_sf,
                "runoff_cfs": runoff_cfs,
                "catchment_name": nearest_catch.name if nearest_catch else None,
                "low_point_score": low_point_score,
                "sag_priority": 1 if sag else 0,
                "sag": sag,
            })

        return candidates

    def _nearest_catchment(self, point: StormPoint, catchments: Sequence[StormCatchment]) -> Optional[StormCatchment]:
        best: Optional[StormCatchment] = None
        best_d = float("inf")
        for c in catchments:
            if c.centroid is None:
                continue
            d = hypot(point.x - c.centroid.x, point.y - c.centroid.y)
            if d < best_d:
                best = c
                best_d = d
        return best

    def _compute_low_point_score(self, point: StormPoint, catchment: Optional[StormCatchment]) -> float:
        score = 0.0
        if point.z is not None:
            score += max(0.0, 1000.0 - point.z) * 0.001
        if catchment is not None:
            score += catchment.peak_runoff_cfs * 0.5
            score += catchment.area_sf / 10000.0
        if point.meta.get("local_low_point", False):
            score += 5.0
        if point.meta.get("sag_point", False):
            score += 10.0
        return round(score, 4)

    def _is_sag_candidate(
        self,
        point: StormPoint,
        catchment: Optional[StormCatchment],
        request: InletHydrologyRequest,
    ) -> bool:
        if not request.use_sag_points:
            return False
        if point.meta.get("sag_point", False):
            return True
        if point.meta.get("on_grade", False):
            return False
        if catchment and catchment.peak_runoff_cfs > request.max_capture_cfs_per_inlet * 0.75:
            return True
        return False

    def _passes_spacing(
        self,
        candidate: Dict[str, Any],
        selected: Sequence[StormInlet],
        min_spacing_ft: float,
    ) -> bool:
        cx = candidate["point"].x
        cy = candidate["point"].y
        for inlet in selected:
            d = hypot(cx - inlet.point.x, cy - inlet.point.y)
            if d < min_spacing_ft:
                return False
        return True

    # =========================================================================
    # INLET BUILD / CAPTURE
    # =========================================================================

    def _build_inlet_from_candidate(
        self,
        cand: Dict[str, Any],
        request: InletHydrologyRequest,
    ) -> StormInlet:
        point: StormPoint = cand["point"]
        runoff_cfs = float(cand["runoff_cfs"])
        sag = bool(cand["sag"])

        inlet_type = request.default_inlet_type
        if sag and request.default_inlet_type == InletType.AREA.value:
            inlet_type = InletType.COMBINATION.value

        capture = self._estimate_capture(
            design_runoff_cfs=runoff_cfs,
            sag=sag,
            max_capture_cfs=request.max_capture_cfs_per_inlet,
            gutter_spread_limit_ft=request.gutter_spread_limit_ft,
        )

        inlet = StormInlet(
            name=cand["name"],
            node_type=StormNodeType.INLET.value,
            point=StormPoint(point.x, point.y, point.z, point.label, dict(point.meta)),
            rim_elev_ft=point.z,
            invert_elev_ft=(point.z - 3.0) if point.z is not None else None,
            inlet_type=inlet_type,
            throat_width_ft=DEFAULT_THROAT_WIDTH_FT,
            grate_length_ft=DEFAULT_GRATE_LENGTH_FT,
            grate_width_ft=DEFAULT_GRATE_WIDTH_FT,
            curb_opening_ft=DEFAULT_CURB_OPENING_FT,
            sag_point=sag,
            on_grade=not sag,
            gutter_spread_limit_ft=request.gutter_spread_limit_ft,
            capture=capture,
            connected_pipe_names=[],
            incoming_catchment_names=[cand["catchment_name"]] if cand["catchment_name"] else [],
            contributing_area_sf=round(cand["tributary_area_sf"], 3),
            contributing_runoff_cfs=round(runoff_cfs, 3),
            bypass_runoff_cfs=round(capture.bypass_cfs, 3),
            local_low_point_score=float(cand["low_point_score"]),
            placement_reason=self._placement_reason(cand),
            warnings=list(capture.warnings),
            meta={
                "tributary_area_sf": cand["tributary_area_sf"],
                "low_point_score": cand["low_point_score"],
                "catchment_name": cand["catchment_name"],
            },
        )
        return inlet

    def _estimate_capture(
        self,
        design_runoff_cfs: float,
        sag: bool,
        max_capture_cfs: float,
        gutter_spread_limit_ft: float,
    ) -> InletCaptureResult:
        design_runoff_cfs = max(0.0, float(design_runoff_cfs))
        max_capture_cfs = max(0.1, float(max_capture_cfs))

        spread_ft = self._triangular_gutter_spread_ft(
            design_runoff_cfs,
            cross_slope=DEFAULT_GUTTER_CROSS_SLOPE,
            longitudinal_slope=DEFAULT_GUTTER_LONGITUDINAL_SLOPE,
            mannings_n=DEFAULT_GUTTER_N,
        )
        depth_ft = spread_ft * DEFAULT_GUTTER_CROSS_SLOPE
        grate_area_sf = DEFAULT_GRATE_LENGTH_FT * DEFAULT_GRATE_WIDTH_FT * DEFAULT_GRATE_OPEN_AREA_RATIO
        grate_perimeter_ft = 2.0 * (DEFAULT_GRATE_LENGTH_FT + DEFAULT_GRATE_WIDTH_FT)
        sag_capacity = min(
            DEFAULT_WEIR_COEFF * grate_perimeter_ft * (max(depth_ft, 0.0) ** 1.5),
            DEFAULT_ORIFICE_COEFF * grate_area_sf * sqrt(2.0 * 32.2 * max(depth_ft, 0.0)),
        )
        on_grade_capacity = max_capture_cfs * min(DEFAULT_ON_GRADE_CAPTURE_FACTOR, max(0.1, gutter_spread_limit_ft / max(spread_ft, 1e-9)))
        hydraulic_capacity = sag_capacity if sag else on_grade_capacity
        intercepted = min(design_runoff_cfs, max_capture_cfs, hydraulic_capacity)
        bypass = max(0.0, design_runoff_cfs - intercepted)
        efficiency = 0.0 if design_runoff_cfs <= 0 else intercepted / design_runoff_cfs

        warnings: List[str] = []
        if bypass > 0.0:
            warnings.append("Bypass flow remains after concept inlet capture.")
        if spread_ft > gutter_spread_limit_ft:
            warnings.append("Estimated gutter spread exceeds preferred limit.")

        return InletCaptureResult(
            intercepted_cfs=round(intercepted, 3),
            bypass_cfs=round(bypass, 3),
            capture_efficiency=round(efficiency, 4),
            spread_ft=round(spread_ft, 3),
            depth_ft=round(depth_ft, 3),
            warnings=warnings,
        )

    def _triangular_gutter_capacity_cfs(self, spread_ft: float, *, cross_slope: float, longitudinal_slope: float, mannings_n: float) -> float:
        spread = max(0.0, spread_ft)
        sx = max(0.0001, cross_slope)
        sl = max(0.000001, longitudinal_slope)
        n = max(0.001, mannings_n)
        return (0.56 / n) * (sx ** (5.0 / 3.0)) * (sl ** 0.5) * (spread ** (8.0 / 3.0))

    def _triangular_gutter_spread_ft(self, flow_cfs: float, *, cross_slope: float, longitudinal_slope: float, mannings_n: float) -> float:
        q = max(0.0, flow_cfs)
        if q <= 0.0:
            return 0.0
        sx = max(0.0001, cross_slope)
        sl = max(0.000001, longitudinal_slope)
        n = max(0.001, mannings_n)
        return (q * n / (0.56 * (sx ** (5.0 / 3.0)) * (sl ** 0.5))) ** (3.0 / 8.0)

    def _placement_reason(self, cand: Dict[str, Any]) -> str:
        reasons: List[str] = []
        if cand["sag"]:
            reasons.append("Selected as sag / strong collection point.")
        if cand["catchment_name"]:
            reasons.append(f"Assigned to catchment '{cand['catchment_name']}'.")
        reasons.append(f"Low-point score = {cand['low_point_score']:.2f}.")
        return " ".join(reasons)

    def _assign_bypass_chain(self, selected: Sequence[StormInlet]) -> None:
        if len(selected) <= 1:
            return
        ordered = sorted(selected, key=lambda i: (i.point.y, i.point.x))
        for i in range(len(ordered) - 1):
            if ordered[i].capture.bypass_cfs > 0.0:
                ordered[i].bypass_to_node_name = ordered[i + 1].name

    # =========================================================================
    # OUTPUTS
    # =========================================================================

    def _build_summary(
        self,
        inlets: Sequence[StormInlet],
        warnings: Sequence[str],
        rejected: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        total_capture = sum(i.capture.intercepted_cfs for i in inlets)
        total_bypass = sum(i.capture.bypass_cfs for i in inlets)
        total_area = sum(i.contributing_area_sf for i in inlets)
        sag_count = sum(1 for i in inlets if i.sag_point)
        return {
            "selected_inlet_count": len(inlets),
            "rejected_candidate_count": len(rejected),
            "total_intercepted_cfs": round(total_capture, 3),
            "total_bypass_cfs": round(total_bypass, 3),
            "total_contributing_area_sf": round(total_area, 3),
            "sag_inlet_count": sag_count,
            "warning_count": len(warnings) + sum(len(i.warnings) for i in inlets),
        }

    def _build_explain(
        self,
        inlets: Sequence[StormInlet],
        rejected: Sequence[Dict[str, Any]],
    ) -> InletPlacementExplain:
        explain = InletPlacementExplain()
        explain.selected_count = len(inlets)
        explain.rejected_count = len(rejected)
        explain.key_logic = [
            "Candidates were ranked using sag priority, low-point score, runoff, and tributary area.",
            "Minimum spacing was enforced between selected inlets.",
            "Each inlet received concept capture/bypass estimates.",
            "Sag inlets were preferred where runoff concentration was higher.",
        ]
        explain.selected_inlets = [
            {
                "name": i.name,
                "sag_point": i.sag_point,
                "contributing_area_sf": i.contributing_area_sf,
                "contributing_runoff_cfs": i.contributing_runoff_cfs,
                "intercepted_cfs": i.capture.intercepted_cfs,
                "bypass_cfs": i.capture.bypass_cfs,
                "placement_reason": i.placement_reason,
            }
            for i in inlets
        ]
        explain.rejected_candidates = [dict(x) for x in rejected[:25]]
        return explain

    def _build_optimize_hooks(
        self,
        inlets: Sequence[StormInlet],
        rejected: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "penalties": {
                "bypass_penalty": round(sum(i.capture.bypass_cfs for i in inlets) * 10.0, 3),
                "spacing_penalty": sum(1 for r in rejected if r.get("reason") == "spacing_conflict") * 3.0,
            },
            "candidate_improvements": [
                "increase inlet count where bypass remains high",
                "shift inlets toward lower concentration points",
                "convert selected on-grade inlets to sag/combination where runoff is high",
            ],
        }

    def _build_conflict_hooks(
        self,
        inlets: Sequence[StormInlet],
    ) -> Dict[str, Any]:
        return {
            "node_candidates": [
                {
                    "name": i.name,
                    "x": i.point.x,
                    "y": i.point.y,
                    "rim_elev_ft": i.rim_elev_ft,
                    "invert_elev_ft": i.invert_elev_ft,
                    "node_type": i.node_type,
                    "system_type": "storm",
                }
                for i in inlets
            ]
        }


def place_storm_inlets(request: InletPlacementRequest) -> InletPlacementResult:
    return InletEngine().place_inlets(request).to_placement_result()


def place_storm_inlets_with_hydrology(request: InletHydrologyRequest) -> InletEngineResult:
    return InletEngine().place_inlets_with_hydrology(request)
