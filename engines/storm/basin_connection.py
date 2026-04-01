
from __future__ import annotations

"""
engines/storm/basin_connection.py (TRUE MAX VERSION)

Purpose
-------
Basin / detention / outfall connection engine for the storm module.

This engine connects upstream storm collection nodes to a basin or outfall and
adds the missing coordination layer between:
- storm_network_engine
- detention sizing / basin geometry
- overflow routing
- outlet / release assumptions
- planner / compliance / conflict / explain hooks

Design intent
-------------
- concept-to-preliminary engineering behavior
- deterministic and explainable
- future-ready for deeper hydrograph / outlet structure routing
- no placeholder-only behavior
"""

from dataclasses import dataclass, field
from math import hypot
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .storm_types import (
    BasinConnectionRequest,
    BasinConnectionResult,
    BasinType,
    FlowPathType,
    StormBasin,
    StormFlowPath,
    StormNode,
    StormNodeType,
    StormPoint,
)


# =============================================================================
# DEFAULTS
# =============================================================================

DEFAULT_CONNECTION_DEPTH_BUFFER_FT = 1.0
DEFAULT_MIN_BASIN_FREEBOARD_FT = 1.0
DEFAULT_MAX_CONNECTION_SLOPE = 0.08
DEFAULT_MIN_CONNECTION_SLOPE = 0.002
DEFAULT_DEFAULT_OVERFLOW_SLOPE = 0.01
DEFAULT_EMERGENCY_OVERFLOW_DEPTH_FT = 0.5
DEFAULT_TARGET_DRAWDOWN_HOURS = 48.0
DEFAULT_RELEASE_RATIO = 0.35
DEFAULT_CONNECTION_CLEARANCE_FT = 5.0


# =============================================================================
# EXTRA MODELS
# =============================================================================

@dataclass
class BasinOutletConcept:
    release_cfs: float = 0.0
    outlet_type: str = "orifice"
    outlet_invert_ft: Optional[float] = None
    control_elev_ft: Optional[float] = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "release_cfs": self.release_cfs,
            "outlet_type": self.outlet_type,
            "outlet_invert_ft": self.outlet_invert_ft,
            "control_elev_ft": self.control_elev_ft,
            "notes": list(self.notes),
        }


@dataclass
class BasinConnectionExplain:
    key_logic: List[str] = field(default_factory=list)
    selected_connection_node: Dict[str, Any] = field(default_factory=dict)
    overflow_summary: Dict[str, Any] = field(default_factory=dict)
    outlet_summary: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_logic": list(self.key_logic),
            "selected_connection_node": dict(self.selected_connection_node),
            "overflow_summary": dict(self.overflow_summary),
            "outlet_summary": dict(self.outlet_summary),
            "warnings": list(self.warnings),
        }


# =============================================================================
# ENGINE
# =============================================================================

class BasinConnectionEngine:
    """
    Connects upstream storm inflows to a basin / outfall concept.

    Major responsibilities:
    - choose / generate a basin connection node
    - estimate basin release concept
    - estimate drawdown and adequacy
    - generate an emergency overflow path if requested
    - build planner/compliance/conflict-ready outputs
    """

    def connect(self, request: BasinConnectionRequest) -> BasinConnectionResult:
        basin = self._clone_basin(request.basin)
        inflow_nodes = [self._clone_node(n) for n in request.inflow_nodes]
        outfall_node = self._clone_node(request.outfall_node) if request.outfall_node else None

        warnings: List[str] = []

        connection_node = self._build_connection_node(basin, inflow_nodes)
        basin.connection_node_name = connection_node.name

        total_inflow_cfs = sum(max(0.0, n.contributing_runoff_cfs + n.bypass_runoff_cfs) for n in inflow_nodes)
        outlet_concept = self._build_outlet_concept(basin, total_inflow_cfs)
        drawdown_hours = self._estimate_drawdown_hours(
            storage_cf=max(0.0, basin.provided_storage_cf or basin.required_storage_cf),
            release_cfs=outlet_concept.release_cfs,
        )
        basin.drawdown_hours = drawdown_hours

        if basin.required_storage_cf > 0.0 and basin.provided_storage_cf > 0.0 and basin.provided_storage_cf < basin.required_storage_cf:
            warnings.append("Provided basin storage is below required storage.")
        if drawdown_hours is not None and drawdown_hours > DEFAULT_TARGET_DRAWDOWN_HOURS:
            warnings.append("Estimated basin drawdown exceeds concept target duration.")
        if basin.depth_ft > 0.0 and basin.depth_ft < DEFAULT_EMERGENCY_OVERFLOW_DEPTH_FT:
            warnings.append("Basin depth is very shallow for a robust connection/overflow concept.")

        overflow_path = None
        if request.allow_overflow_path:
            overflow_path = self._build_overflow_path(
                basin=basin,
                connection_node=connection_node,
                outfall_node=outfall_node,
            )
            if overflow_path is None:
                warnings.append("Emergency overflow path could not be generated.")
        else:
            warnings.append("Emergency overflow path generation was disabled.")

        basin.meta = {
            **dict(basin.meta),
            "connection_node_name": connection_node.name,
            "outlet_concept": outlet_concept.to_dict(),
            "estimated_drawdown_hours": drawdown_hours,
            "total_inflow_cfs": round(total_inflow_cfs, 3),
        }

        summary = {
            "basin_name": basin.name,
            "connection_node_name": connection_node.name,
            "total_inflow_cfs": round(total_inflow_cfs, 3),
            "release_cfs": round(outlet_concept.release_cfs, 3),
            "required_storage_cf": round(basin.required_storage_cf, 3),
            "provided_storage_cf": round(basin.provided_storage_cf, 3),
            "drawdown_hours": None if drawdown_hours is None else round(drawdown_hours, 3),
            "overflow_path_generated": overflow_path is not None,
        }

        explain = self._build_explain(
            basin=basin,
            connection_node=connection_node,
            outlet_concept=outlet_concept,
            overflow_path=overflow_path,
            warnings=warnings,
        )
        basin.meta["explain"] = explain.to_dict()
        basin.warnings.extend(warnings)

        return BasinConnectionResult(
            success=True,
            basin=basin,
            connection_node=connection_node,
            overflow_path=overflow_path,
            warnings=warnings,
            summary=summary,
        )

    # =========================================================================
    # BASIN / NODE BUILDERS
    # =========================================================================

    def _clone_basin(self, b: StormBasin) -> StormBasin:
        return StormBasin(
            name=b.name,
            basin_type=b.basin_type,
            bottom_area_sf=b.bottom_area_sf,
            top_area_sf=b.top_area_sf,
            depth_ft=b.depth_ft,
            side_slope_h_to_1v=b.side_slope_h_to_1v,
            bottom_elev_ft=b.bottom_elev_ft,
            overflow_elev_ft=b.overflow_elev_ft,
            release_cfs=b.release_cfs,
            required_storage_cf=b.required_storage_cf,
            provided_storage_cf=b.provided_storage_cf,
            drawdown_hours=b.drawdown_hours,
            stage_storage_curve=list(b.stage_storage_curve),
            connection_node_name=b.connection_node_name,
            boundary_points=list(b.boundary_points),
            warnings=list(b.warnings),
            meta=dict(b.meta),
        )

    def _clone_node(self, n: Optional[StormNode]) -> Optional[StormNode]:
        if n is None:
            return None
        return StormNode(
            name=n.name,
            node_type=n.node_type,
            point=StormPoint(n.point.x, n.point.y, n.point.z, n.point.label, dict(n.point.meta)),
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

    def _build_connection_node(self, basin: StormBasin, inflow_nodes: Sequence[StormNode]) -> StormNode:
        point = self._select_connection_point(basin, inflow_nodes)
        rim = basin.overflow_elev_ft if basin.overflow_elev_ft is not None else (
            (basin.bottom_elev_ft + basin.depth_ft + DEFAULT_MIN_BASIN_FREEBOARD_FT) if basin.bottom_elev_ft is not None else point.z
        )
        invert = None
        if basin.bottom_elev_ft is not None:
            invert = basin.bottom_elev_ft + DEFAULT_CONNECTION_DEPTH_BUFFER_FT
        elif rim is not None:
            invert = rim - 3.0

        return StormNode(
            name=basin.connection_node_name or f"{basin.name}_CONN",
            node_type=StormNodeType.BASIN_CONNECTION.value,
            point=point,
            rim_elev_ft=rim,
            invert_elev_ft=invert,
            structure_diameter_ft=4.0,
            meta={"basin_name": basin.name, "connection_role": "basin_connection"},
        )

    def _select_connection_point(self, basin: StormBasin, inflow_nodes: Sequence[StormNode]) -> StormPoint:
        if basin.boundary_points:
            # choose boundary point closest to average inflow centroid to mimic practical tie-in
            if inflow_nodes:
                cx = sum(n.point.x for n in inflow_nodes) / len(inflow_nodes)
                cy = sum(n.point.y for n in inflow_nodes) / len(inflow_nodes)
                best = min(basin.boundary_points, key=lambda p: hypot(p[0] - cx, p[1] - cy))
                return StormPoint(best[0], best[1], basin.bottom_elev_ft, label=f"{basin.name}_CONN")
            xs = [p[0] for p in basin.boundary_points]
            ys = [p[1] for p in basin.boundary_points]
            return StormPoint(sum(xs) / len(xs), sum(ys) / len(ys), basin.bottom_elev_ft, label=f"{basin.name}_CONN")

        if inflow_nodes:
            cx = sum(n.point.x for n in inflow_nodes) / len(inflow_nodes)
            cy = sum(n.point.y for n in inflow_nodes) / len(inflow_nodes)
            return StormPoint(cx, cy, basin.bottom_elev_ft, label=f"{basin.name}_CONN")

        return StormPoint(0.0, 0.0, basin.bottom_elev_ft, label=f"{basin.name}_CONN")

    # =========================================================================
    # OUTLET / DRAWDOWN / OVERFLOW
    # =========================================================================

    def _build_outlet_concept(self, basin: StormBasin, inflow_cfs: float) -> BasinOutletConcept:
        release = basin.release_cfs if basin.release_cfs > 0.0 else inflow_cfs * DEFAULT_RELEASE_RATIO
        release = max(0.1, release) if inflow_cfs > 0 else max(0.0, release)

        outlet_invert = None
        control_elev = None
        notes: List[str] = []

        if basin.bottom_elev_ft is not None:
            outlet_invert = basin.bottom_elev_ft + DEFAULT_CONNECTION_DEPTH_BUFFER_FT
            control_elev = outlet_invert + 0.5
        elif basin.overflow_elev_ft is not None:
            outlet_invert = basin.overflow_elev_ft - 2.0
            control_elev = outlet_invert + 0.5

        outlet_type = "orifice"
        if basin.basin_type in {BasinType.SWALE.value, BasinType.BIORETENTION.value}:
            outlet_type = "weir_or_underdrain"
            notes.append("Basin type suggests a shallow open-channel / underdrain style outlet concept.")
        elif basin.basin_type == BasinType.RETENTION.value:
            outlet_type = "controlled_outlet"
            notes.append("Retention-like basin assigned a controlled outlet concept for planning consistency.")
        else:
            notes.append("Standard detention outlet concept assumed.")

        return BasinOutletConcept(
            release_cfs=round(release, 3),
            outlet_type=outlet_type,
            outlet_invert_ft=outlet_invert,
            control_elev_ft=control_elev,
            notes=notes,
        )

    def _estimate_drawdown_hours(self, storage_cf: float, release_cfs: float) -> Optional[float]:
        storage_cf = max(0.0, float(storage_cf))
        release_cfs = max(0.0, float(release_cfs))
        if storage_cf <= 0.0:
            return 0.0
        if release_cfs <= 0.0:
            return None
        return storage_cf / release_cfs / 3600.0

    def _build_overflow_path(
        self,
        basin: StormBasin,
        connection_node: StormNode,
        outfall_node: Optional[StormNode],
    ) -> Optional[StormFlowPath]:
        if outfall_node is None:
            # create implied overflow receiver downgradient
            outfall_node = StormNode(
                name=f"{basin.name}_OVERFLOW_OUTFALL",
                node_type=StormNodeType.OUTFALL.value,
                point=StormPoint(
                    connection_node.point.x + 40.0,
                    connection_node.point.y - 20.0,
                    (connection_node.point.z - DEFAULT_EMERGENCY_OVERFLOW_DEPTH_FT) if connection_node.point.z is not None else None,
                    label=f"{basin.name}_OVERFLOW_OUTFALL",
                ),
                rim_elev_ft=(connection_node.rim_elev_ft - DEFAULT_EMERGENCY_OVERFLOW_DEPTH_FT) if connection_node.rim_elev_ft is not None else None,
                invert_elev_ft=(connection_node.invert_elev_ft - DEFAULT_EMERGENCY_OVERFLOW_DEPTH_FT) if connection_node.invert_elev_ft is not None else None,
            )

        pts = [
            (connection_node.point.x, connection_node.point.y),
            (outfall_node.point.x, outfall_node.point.y),
        ]
        length = self._polyline_length(pts)
        if length <= 0.0:
            return None

        dz = 0.0
        if connection_node.point.z is not None and outfall_node.point.z is not None:
            dz = connection_node.point.z - outfall_node.point.z
        slope = max(DEFAULT_MIN_CONNECTION_SLOPE, dz / length if length > 0 else DEFAULT_DEFAULT_OVERFLOW_SLOPE)
        slope = min(DEFAULT_MAX_CONNECTION_SLOPE, max(DEFAULT_MIN_CONNECTION_SLOPE, slope))

        return StormFlowPath(
            name=f"{basin.name}_EMERGENCY_OVERFLOW",
            flow_path_type=FlowPathType.OVERFLOW.value,
            from_name=connection_node.name,
            to_name=outfall_node.name,
            path_points=pts,
            slope=round(slope, 5),
            contributing_area_sf=0.0,
            assigned_flow_cfs=0.0,
            meta={
                "basin_name": basin.name,
                "overflow_role": "emergency",
                "length_ft": round(length, 3),
            },
        )

    # =========================================================================
    # EXPLAIN / UTILS
    # =========================================================================

    def _build_explain(
        self,
        basin: StormBasin,
        connection_node: StormNode,
        outlet_concept: BasinOutletConcept,
        overflow_path: Optional[StormFlowPath],
        warnings: Sequence[str],
    ) -> BasinConnectionExplain:
        explain = BasinConnectionExplain()
        explain.key_logic = [
            "A basin connection node was selected at the boundary/centroid nearest probable inflow approach.",
            "A concept outlet release was assigned from basin release data or an inflow-based default ratio.",
            "Drawdown duration was estimated from available storage and release rate.",
            "An emergency overflow path was generated when allowed.",
        ]
        explain.selected_connection_node = {
            "name": connection_node.name,
            "x": connection_node.point.x,
            "y": connection_node.point.y,
            "rim_elev_ft": connection_node.rim_elev_ft,
            "invert_elev_ft": connection_node.invert_elev_ft,
        }
        explain.outlet_summary = outlet_concept.to_dict()
        explain.overflow_summary = {
            "generated": overflow_path is not None,
            "name": overflow_path.name if overflow_path else None,
            "to_name": overflow_path.to_name if overflow_path else None,
            "slope": overflow_path.slope if overflow_path else None,
            "length_ft": round(self._polyline_length(overflow_path.path_points), 3) if overflow_path else None,
        }
        explain.warnings = list(warnings)
        return explain

    def _polyline_length(self, pts: Sequence[Tuple[float, float]]) -> float:
        if len(pts) < 2:
            return 0.0
        total = 0.0
        for i in range(1, len(pts)):
            total += hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
        return total


def connect_basin(request: BasinConnectionRequest) -> BasinConnectionResult:
    return BasinConnectionEngine().connect(request)
