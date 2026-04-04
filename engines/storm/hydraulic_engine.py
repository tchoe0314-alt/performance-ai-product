
from __future__ import annotations

"""
engines/storm/hydraulic_engine.py (TRUE MAX VERSION)

Purpose
-------
Hydraulic analysis engine for the storm module.

This engine provides concept-to-preliminary hydraulic evaluation for storm
pipes and nodes, including:
- full-flow capacity estimation
- velocity checks
- flow depth ratio proxy
- HGL/EGL propagation
- surcharge risk flags
- deficiency detection
- planner / compliance / explain / optimize hooks

Design intent
-------------
- deterministic and explainable
- broad enough for real system coordination now
- future-ready for deeper dynamic / hydrograph / inlet spread modeling later
- integrates cleanly with storm_types.py and storm_network_engine.py
"""

from dataclasses import dataclass, field
from math import pi
from typing import Any, Dict, List, Optional, Sequence

from .storm_types import (
    CapacityStatus,
    HydraulicAnalysisRequest,
    HydraulicAnalysisResult,
    HydraulicCheck,
    StormNode,
    StormPipe,
)


# =============================================================================
# DEFAULTS
# =============================================================================

DEFAULT_MIN_VELOCITY_FPS = 2.0
DEFAULT_MAX_VELOCITY_FPS = 15.0
DEFAULT_MAX_HGL_ABOVE_RIM_FT = 0.5
DEFAULT_MINOR_LOSS_COEFF = 0.2
DEFAULT_ENERGY_GRADE_BUMP_FT = 0.2
DEFAULT_PARTIAL_FLOW_FACTOR = 0.85


# =============================================================================
# EXTRA MODELS
# =============================================================================

@dataclass
class PipeHydraulicDecision:
    pipe_name: str
    design_flow_cfs: float
    full_capacity_cfs: float
    velocity_fps: float
    flow_depth_ratio: float
    capacity_status: str
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipe_name": self.pipe_name,
            "design_flow_cfs": round(self.design_flow_cfs, 3),
            "full_capacity_cfs": round(self.full_capacity_cfs, 3),
            "velocity_fps": round(self.velocity_fps, 3),
            "flow_depth_ratio": round(self.flow_depth_ratio, 4),
            "capacity_status": self.capacity_status,
            "warnings": list(self.warnings),
        }


# =============================================================================
# ENGINE
# =============================================================================

class HydraulicEngine:
    """
    True-max storm hydraulic engine.

    Current capabilities:
    - Manning-style full-flow capacity estimation
    - velocity and capacity checks
    - partial-flow proxy depth ratio
    - HGL / EGL node propagation
    - surcharge risk marking
    - planner-ready summaries and hooks
    """

    def analyze(self, request: HydraulicAnalysisRequest) -> HydraulicAnalysisResult:
        pipes = [self._clone_pipe(p) for p in request.pipes]
        nodes = [self._clone_node(n) for n in request.nodes]

        if not pipes:
            return HydraulicAnalysisResult(
                success=False,
                pipes=[],
                warnings=["No storm pipes were provided for hydraulic analysis."],
                summary={},
            )

        node_lookup = {n.name: n for n in nodes}
        warnings: List[str] = []

        decisions: List[PipeHydraulicDecision] = []

        # First pass: compute each pipe's direct hydraulic state
        for pipe in pipes:
            decision = self._analyze_pipe(pipe, request)
            decisions.append(decision)
            pipe.hydraulic = HydraulicCheck(
                design_flow_cfs=round(decision.design_flow_cfs, 3),
                full_capacity_cfs=round(decision.full_capacity_cfs, 3),
                velocity_fps=round(decision.velocity_fps, 3),
                flow_depth_ratio=round(decision.flow_depth_ratio, 4),
                capacity_status=decision.capacity_status,
                warnings=list(decision.warnings),
            )
            pipe.warnings.extend(decision.warnings)
            warnings.extend(decision.warnings)

        # Second pass: assign HGL/EGL node-to-node
        if request.compute_hgl or request.compute_egl:
            self._propagate_hydraulic_grades(pipes, node_lookup, request, warnings)

        # Third pass: node surcharge checks
        self._mark_node_surcharge(node_lookup, warnings)

        summary = self._build_summary(pipes, node_lookup, warnings)
        return HydraulicAnalysisResult(
            success=True,
            pipes=pipes,
            warnings=sorted(set(warnings)),
            summary=summary,
        )

    # =========================================================================
    # PIPE ANALYSIS
    # =========================================================================

    def _analyze_pipe(self, pipe: StormPipe, request: HydraulicAnalysisRequest) -> PipeHydraulicDecision:
        q = max(0.0, float(pipe.assigned_runoff_cfs))
        d_ft = max(0.01, float(pipe.diameter_in) / 12.0)
        n = max(0.001, float(pipe.mannings_n))
        slope = max(0.0001, float(pipe.slope))

        full_capacity = self._full_flow_capacity_cfs(d_ft, slope, n)
        area = pi * (d_ft ** 2) / 4.0
        velocity = q / max(area, 1e-9)

        if request.allow_partial_flow:
            flow_depth_ratio = min(1.0, q / max(full_capacity * DEFAULT_PARTIAL_FLOW_FACTOR, 1e-9))
        else:
            flow_depth_ratio = min(1.0, q / max(full_capacity, 1e-9))

        status = CapacityStatus.OK.value
        warnings: List[str] = []

        if q > full_capacity:
            status = CapacityStatus.DEFICIENT.value
            warnings.append("Design flow exceeds estimated full-flow pipe capacity.")
        elif q > 0.85 * full_capacity:
            status = CapacityStatus.MARGINAL.value
            warnings.append("Design flow approaches full-flow capacity.")

        if velocity < DEFAULT_MIN_VELOCITY_FPS and q > 0.0:
            warnings.append("Pipe velocity is below preferred self-cleansing range.")
        if velocity > DEFAULT_MAX_VELOCITY_FPS:
            warnings.append("Pipe velocity exceeds preferred maximum range.")

        return PipeHydraulicDecision(
            pipe_name=pipe.name,
            design_flow_cfs=q,
            full_capacity_cfs=full_capacity,
            velocity_fps=velocity,
            flow_depth_ratio=flow_depth_ratio,
            capacity_status=status,
            warnings=warnings,
        )

    def _full_flow_capacity_cfs(self, diameter_ft: float, slope: float, mannings_n: float) -> float:
        area = pi * (diameter_ft ** 2) / 4.0
        wetted_perimeter = pi * diameter_ft
        hydraulic_radius = area / max(wetted_perimeter, 1e-9)
        return (1.486 / mannings_n) * area * (hydraulic_radius ** (2.0 / 3.0)) * (slope ** 0.5)

    # =========================================================================
    # HGL / EGL PROPAGATION
    # =========================================================================

    def _propagate_hydraulic_grades(
        self,
        pipes: Sequence[StormPipe],
        node_lookup: Dict[str, StormNode],
        request: HydraulicAnalysisRequest,
        warnings: List[str],
    ) -> None:
        # downstream-first sort heuristic: lower invert first when available
        ordered = sorted(
            pipes,
            key=lambda p: (
                p.downstream_invert_ft if p.downstream_invert_ft is not None else 1e9,
                p.upstream_invert_ft if p.upstream_invert_ft is not None else 1e9,
            )
        )

        for pipe in ordered:
            up = node_lookup.get(pipe.upstream_node_name)
            dn = node_lookup.get(pipe.downstream_node_name)

            up_inv = pipe.upstream_invert_ft if pipe.upstream_invert_ft is not None else (up.invert_elev_ft if up else 100.0)
            dn_inv = pipe.downstream_invert_ft if pipe.downstream_invert_ft is not None else (dn.invert_elev_ft if dn else up_inv - max(pipe.length_ft * pipe.slope, 0.1))

            depth_head = (float(pipe.diameter_in) / 12.0) * max(pipe.hydraulic.flow_depth_ratio, 0.2)
            friction_loss = max(0.0, pipe.length_ft * pipe.slope * 0.25)
            minor_loss = DEFAULT_MINOR_LOSS_COEFF * max(pipe.hydraulic.velocity_fps, 0.0) * 0.05

            hgl_up = up_inv + depth_head + friction_loss + minor_loss
            hgl_dn = dn_inv + depth_head
            egl_up = hgl_up + DEFAULT_ENERGY_GRADE_BUMP_FT
            egl_dn = hgl_dn + DEFAULT_ENERGY_GRADE_BUMP_FT

            pipe.hydraulic.hgl_upstream_ft = round(hgl_up, 3)
            pipe.hydraulic.hgl_downstream_ft = round(hgl_dn, 3)
            pipe.hydraulic.egl_upstream_ft = round(egl_up, 3)
            pipe.hydraulic.egl_downstream_ft = round(egl_dn, 3)

            if up is not None:
                up.max_hgl_ft = max(up.max_hgl_ft or hgl_up, hgl_up)
            if dn is not None:
                dn.max_hgl_ft = max(dn.max_hgl_ft or hgl_dn, hgl_dn)

            if hgl_up < hgl_dn:
                warnings.append(f"Hydraulic grade trend is unusual for pipe '{pipe.name}'.")
                pipe.warnings.append("Hydraulic grade trend is unusual for this pipe.")

    # =========================================================================
    # NODE SURCHARGE
    # =========================================================================

    def _mark_node_surcharge(self, node_lookup: Dict[str, StormNode], warnings: List[str]) -> None:
        for node in node_lookup.values():
            if node.max_hgl_ft is None or node.rim_elev_ft is None:
                continue
            if node.max_hgl_ft > node.rim_elev_ft + DEFAULT_MAX_HGL_ABOVE_RIM_FT:
                node.surcharge_risk = True
                node.warnings.append("Node HGL exceeds rim elevation threshold; surcharge risk flagged.")
                warnings.append(f"Node '{node.name}' is at surcharge risk.")

    # =========================================================================
    # SUMMARY
    # =========================================================================

    def _build_summary(
        self,
        pipes: Sequence[StormPipe],
        node_lookup: Dict[str, StormNode],
        warnings: Sequence[str],
    ) -> Dict[str, Any]:
        deficient = [p for p in pipes if p.hydraulic.capacity_status == CapacityStatus.DEFICIENT.value]
        marginal = [p for p in pipes if p.hydraulic.capacity_status == CapacityStatus.MARGINAL.value]
        surcharge = [n for n in node_lookup.values() if n.surcharge_risk]
        system_tributary_area_sf = max((float(dict(p.meta).get("tributary_area_sf") or 0.0) for p in pipes), default=0.0)
        system_tributary_runoff_cfs = max((float(dict(p.meta).get("tributary_runoff_cfs") or 0.0) for p in pipes), default=0.0)
        system_tributary_catchment_count = max((int(dict(p.meta).get("tributary_catchment_count") or 0) for p in pipes), default=0)
        system_tributary_basin_names: List[str] = []
        for pipe in pipes:
            for basin_name in list(dict(pipe.meta).get("tributary_basin_names") or []):
                safe_name = str(basin_name).strip()
                if safe_name and safe_name not in system_tributary_basin_names:
                    system_tributary_basin_names.append(safe_name)

        return {
            "pipe_count": len(pipes),
            "node_count": len(node_lookup),
            "deficient_pipe_count": len(deficient),
            "marginal_pipe_count": len(marginal),
            "surcharge_node_count": len(surcharge),
            "total_design_flow_cfs": round(sum(p.hydraulic.design_flow_cfs for p in pipes), 3),
            "total_full_capacity_cfs": round(sum(p.hydraulic.full_capacity_cfs for p in pipes), 3),
            "system_tributary_area_sf": round(system_tributary_area_sf, 3),
            "system_tributary_runoff_cfs": round(system_tributary_runoff_cfs, 3),
            "system_tributary_catchment_count": system_tributary_catchment_count,
            "system_tributary_basin_names": system_tributary_basin_names,
            "max_velocity_fps": round(max((p.hydraulic.velocity_fps for p in pipes), default=0.0), 3),
            "warning_count": len(warnings),
            "critical_pipes": [
                {
                    "name": p.name,
                    "status": p.hydraulic.capacity_status,
                    "design_flow_cfs": p.hydraulic.design_flow_cfs,
                    "full_capacity_cfs": p.hydraulic.full_capacity_cfs,
                    "velocity_fps": p.hydraulic.velocity_fps,
                    "flow_depth_ratio": p.hydraulic.flow_depth_ratio,
                    "tributary_area_sf": round(float(dict(p.meta).get("tributary_area_sf") or 0.0), 3),
                    "tributary_runoff_cfs": round(float(dict(p.meta).get("tributary_runoff_cfs") or 0.0), 3),
                    "tributary_catchment_count": int(dict(p.meta).get("tributary_catchment_count") or 0),
                    "tributary_basin_names": list(dict(p.meta).get("tributary_basin_names") or []),
                }
                for p in sorted(
                    pipes,
                    key=lambda x: (
                        2 if x.hydraulic.capacity_status == CapacityStatus.DEFICIENT.value else
                        1 if x.hydraulic.capacity_status == CapacityStatus.MARGINAL.value else 0,
                        x.hydraulic.flow_depth_ratio,
                    ),
                    reverse=True,
                )[:8]
            ],
            "critical_nodes": [
                {
                    "name": n.name,
                    "max_hgl_ft": n.max_hgl_ft,
                    "rim_elev_ft": n.rim_elev_ft,
                    "surcharge_risk": n.surcharge_risk,
                }
                for n in surcharge[:8]
            ],
            "optimize_hooks": {
                "penalties": {
                    "deficiency_penalty": len(deficient) * 25.0,
                    "marginal_penalty": len(marginal) * 10.0,
                    "surcharge_penalty": len(surcharge) * 30.0,
                },
                "candidate_improvements": [
                    "increase deficient pipe diameters",
                    "increase slope where capacity is marginal",
                    "shorten routes to reduce losses",
                    "lower downstream control elevation to reduce HGL",
                ],
            },
            "conflict_hooks": {
                "hydraulic_nodes": [
                    {
                        "name": n.name,
                        "max_hgl_ft": n.max_hgl_ft,
                        "rim_elev_ft": n.rim_elev_ft,
                        "surcharge_risk": n.surcharge_risk,
                    }
                    for n in node_lookup.values()
                ]
            },
        }

    # =========================================================================
    # CLONERS
    # =========================================================================

    def _clone_pipe(self, p: StormPipe) -> StormPipe:
        out = StormPipe(**p.__dict__)
        out.route_points = list(p.route_points)
        out.contributing_catchment_names = list(p.contributing_catchment_names)
        out.warnings = list(p.warnings)
        out.meta = dict(p.meta)
        out.hydraulic = HydraulicCheck(**p.hydraulic.__dict__) if p.hydraulic is not None else HydraulicCheck()
        return out

    def _clone_node(self, n: StormNode) -> StormNode:
        return StormNode(
            name=n.name,
            node_type=n.node_type,
            point=n.point,
            rim_elev_ft=n.rim_elev_ft,
            invert_elev_ft=n.invert_elev_ft,
            structure_diameter_ft=n.structure_diameter_ft,
            connected_pipe_names=list(n.connected_pipe_names),
            incoming_catchment_names=list(n.incoming_catchment_names),
            contributing_area_sf=n.contributing_area_sf,
            contributing_runoff_cfs=n.contributing_runoff_cfs,
            bypass_runoff_cfs=n.bypass_runoff_cfs,
            max_hgl_ft=n.max_hgl_ft,
            surcharge_risk=n.surcharge_risk,
            warnings=list(n.warnings),
            meta=dict(n.meta),
        )


def analyze_storm_hydraulics(request: HydraulicAnalysisRequest) -> HydraulicAnalysisResult:
    return HydraulicEngine().analyze(request)
