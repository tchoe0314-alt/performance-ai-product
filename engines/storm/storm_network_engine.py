
from __future__ import annotations

"""
engines/storm/storm_network_engine.py (TRUE MAX VERSION)

Purpose
-------
Build and coordinate a concept-to-preliminary storm collection network using:
- catchments
- inlet placement
- basin / outfall targets
- routing hooks
- pipe sizing hooks
- relative invert assignment
- planner / compliance / conflict / explain hooks

Design intent
-------------
- keep drainage_engine focused on surface/runoff behavior
- keep pipe/hydraulic engines as lower-level hydraulic math layers
- make this engine the actual storm collection system builder

Notes
-----
This engine is intentionally broad:
- it can accept inlets/catchments/basins already prepared upstream
- it can generate trunk/lateral style network topology
- it can assign preliminary pipe diameters, slopes, lengths, and inverts
- it provides hooks for routing_engine / hydraulic_engine / conflict_engine
"""

from dataclasses import dataclass, field
from math import hypot
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .storm_types import (
    CapacityStatus,
    HydraulicCheck,
    StormBasin,
    StormCatchment,
    StormFlowPath,
    StormInlet,
    StormNetwork,
    StormNetworkRequest,
    StormNetworkResult,
    StormNode,
    StormNodeType,
    StormPipe,
    StormPipeType,
    StormPoint,
    summarize_storm_network,
)

try:
    from engines.routing_engine import RoutingEngine, RoutingRequest, RouteSystemType
except Exception:  # pragma: no cover
    RoutingEngine = None
    RoutingRequest = None
    RouteSystemType = None


# =============================================================================
# DEFAULTS
# =============================================================================

DEFAULT_MIN_PIPE_SLOPE = 0.003
DEFAULT_MIN_COVER_FT = 3.0
DEFAULT_MIN_DIAMETER_IN = 12.0
DEFAULT_DEFAULT_MANNINGS_N = 0.013
DEFAULT_NODE_RIM_TO_INVERT_DROP_FT = 3.0
DEFAULT_TRUNK_JOIN_DISTANCE_FT = 120.0
DEFAULT_MAX_LATERAL_LENGTH_FT = 250.0
DEFAULT_OUTFALL_DEPTH_BUFFER_FT = 1.0
DEFAULT_DEFAULT_STORAGE_HOURS = 0.5

# Simplified capacity table for concept storm pipes
# Manning-like proxy bands, concept only
PIPE_CAPACITY_TABLE = [
    {"diameter_in": 12.0, "max_flow_cfs": 3.5, "min_slope": 0.010},
    {"diameter_in": 15.0, "max_flow_cfs": 5.5, "min_slope": 0.008},
    {"diameter_in": 18.0, "max_flow_cfs": 8.5, "min_slope": 0.006},
    {"diameter_in": 24.0, "max_flow_cfs": 16.0, "min_slope": 0.004},
    {"diameter_in": 30.0, "max_flow_cfs": 27.0, "min_slope": 0.003},
    {"diameter_in": 36.0, "max_flow_cfs": 41.0, "min_slope": 0.003},
    {"diameter_in": 42.0, "max_flow_cfs": 57.0, "min_slope": 0.002},
    {"diameter_in": 48.0, "max_flow_cfs": 76.0, "min_slope": 0.002},
]


# =============================================================================
# EXTRA MODELS
# =============================================================================

@dataclass
class StormRoutingHook:
    enabled: bool = True
    grid_size: float = 5.0
    clearance: float = 2.0
    prefer_existing_routes: bool = True
    use_corridors: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StormNetworkExplain:
    key_logic: List[str] = field(default_factory=list)
    selected_outfall_name: Optional[str] = None
    inlet_assignments: List[Dict[str, Any]] = field(default_factory=list)
    pipe_decisions: List[Dict[str, Any]] = field(default_factory=list)
    network_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_logic": list(self.key_logic),
            "selected_outfall_name": self.selected_outfall_name,
            "inlet_assignments": [dict(x) for x in self.inlet_assignments],
            "pipe_decisions": [dict(x) for x in self.pipe_decisions],
            "network_warnings": list(self.network_warnings),
        }


# =============================================================================
# ENGINE
# =============================================================================

class StormNetworkEngine:
    """
    True-max storm network engine.

    Responsibilities:
    - assemble inlets/basins/outfalls into one network
    - assign catchments to inlets
    - build lateral + trunk topology
    - optionally route alignments
    - assign lengths, slopes, diameters, and relative inverts
    - produce planner/intelligence/compliance-ready outputs
    """

    def build_network(
        self,
        request: StormNetworkRequest,
        *,
        routing_hook: Optional[StormRoutingHook] = None,
    ) -> StormNetworkResult:
        routing_hook = routing_hook or StormRoutingHook()
        warnings: List[str] = []

        network = StormNetwork(
            name=request.network_name,
            nodes=[],
            inlets=[self._clone_inlet(i) for i in request.inlets],
            basins=[self._clone_basin(b) for b in request.basins],
            pipes=[],
            catchments=[self._clone_catchment(c) for c in request.catchments],
            flow_paths=[],
            warnings=[],
            meta=dict(request.meta),
        )

        outfalls = [self._clone_node(n) for n in request.outfalls]
        if not outfalls and request.connect_to_basin and network.basins:
            outfalls = self._make_outfalls_from_basins(network.basins)
        if not outfalls:
            warnings.append("No explicit outfall or basin target provided; last downstream node will act as implied outfall.")

        all_nodes: List[StormNode] = []
        all_nodes.extend([self._inlet_to_node(i) for i in network.inlets])
        all_nodes.extend(outfalls)
        all_nodes.extend([self._basin_to_connection_node(b) for b in network.basins if self._basin_to_connection_node(b) is not None])

        # assign catchments to nearest inlets / outfalls
        self._assign_catchments_to_inlets(network.catchments, network.inlets, outfalls, warnings)

        # build topology
        pipes, flow_paths = self._build_topology(
            catchments=network.catchments,
            inlets=network.inlets,
            basins=network.basins,
            outfalls=outfalls,
            request=request,
            routing_hook=routing_hook,
            warnings=warnings,
        )
        network.pipes.extend(pipes)
        network.flow_paths.extend(flow_paths)

        # derive total runoff into nodes
        node_lookup = {n.name: n for n in all_nodes}
        self._attach_pipe_node_relationships(network.pipes, node_lookup)
        self._assign_node_runoff_from_inlets(network.inlets, node_lookup)

        # assign hydraulic placeholders and invert system
        self._size_pipes(network.pipes, request, warnings)
        self._assign_relative_inverts(network.pipes, node_lookup, request, warnings)
        self._assign_hydraulic_status(network.pipes, request, warnings)

        # merge nodes into network
        network.nodes = list(node_lookup.values())
        network.warnings.extend(warnings)

        summary = summarize_storm_network(network)
        explain = self._build_explain(network, outfalls, warnings)
        optimize_hooks = self._build_optimize_hooks(network)
        conflict_hooks = self._build_conflict_hooks(network)

        return StormNetworkResult(
            success=len(network.pipes) > 0 or len(network.inlets) > 0,
            network=network,
            total_runoff_cfs=round(sum(c.peak_runoff_cfs for c in network.catchments), 3),
            total_pipe_length_ft=round(sum(p.length_ft for p in network.pipes), 3),
            total_pipe_count=len(network.pipes),
            total_inlet_count=len(network.inlets),
            total_structure_count=len(network.nodes),
            warnings=sorted(set(warnings)),
            explain=explain.to_dict(),
            optimize_hooks=optimize_hooks,
            conflict_hooks=conflict_hooks,
        )

    # =========================================================================
    # CLONERS / CONVERTERS
    # =========================================================================

    def _clone_point(self, p: StormPoint) -> StormPoint:
        return StormPoint(x=p.x, y=p.y, z=p.z, label=p.label, meta=dict(p.meta))

    def _clone_node(self, n: StormNode) -> StormNode:
        return StormNode(
            name=n.name,
            node_type=n.node_type,
            point=self._clone_point(n.point),
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

    def _clone_inlet(self, i: StormInlet) -> StormInlet:
        out = StormInlet(**i.__dict__)
        out.point = self._clone_point(i.point)
        out.connected_pipe_names = list(i.connected_pipe_names)
        out.incoming_catchment_names = list(i.incoming_catchment_names)
        out.warnings = list(i.warnings)
        out.meta = dict(i.meta)
        return out

    def _clone_basin(self, b: StormBasin) -> StormBasin:
        out = StormBasin(**b.__dict__)
        out.stage_storage_curve = list(b.stage_storage_curve)
        out.boundary_points = list(b.boundary_points)
        out.warnings = list(b.warnings)
        out.meta = dict(b.meta)
        return out

    def _clone_catchment(self, c: StormCatchment) -> StormCatchment:
        out = StormCatchment(**c.__dict__)
        out.centroid = self._clone_point(c.centroid) if c.centroid else None
        out.boundary_points = list(c.boundary_points)
        out.warnings = list(c.warnings)
        out.meta = dict(c.meta)
        return out

    def _inlet_to_node(self, inlet: StormInlet) -> StormNode:
        return StormNode(
            name=inlet.name,
            node_type=StormNodeType.INLET.value,
            point=self._clone_point(inlet.point),
            rim_elev_ft=inlet.rim_elev_ft,
            invert_elev_ft=inlet.invert_elev_ft,
            structure_diameter_ft=4.0,
            connected_pipe_names=list(inlet.connected_pipe_names),
            incoming_catchment_names=list(inlet.incoming_catchment_names),
            contributing_area_sf=inlet.contributing_area_sf,
            contributing_runoff_cfs=inlet.contributing_runoff_cfs,
            bypass_runoff_cfs=inlet.bypass_runoff_cfs,
            warnings=list(inlet.warnings),
            meta=dict(inlet.meta),
        )

    def _basin_to_connection_node(self, basin: StormBasin) -> Optional[StormNode]:
        if not basin.boundary_points and basin.connection_node_name is None:
            return None
        if basin.connection_node_name:
            name = basin.connection_node_name
        else:
            name = f"{basin.name}_CONN"
        pt = self._basin_connection_point(basin)
        return StormNode(
            name=name,
            node_type=StormNodeType.BASIN_CONNECTION.value,
            point=pt,
            rim_elev_ft=basin.overflow_elev_ft,
            invert_elev_ft=(basin.bottom_elev_ft + DEFAULT_OUTFALL_DEPTH_BUFFER_FT) if basin.bottom_elev_ft is not None else None,
            structure_diameter_ft=4.0,
            warnings=list(basin.warnings),
            meta={"basin_name": basin.name, **dict(basin.meta)},
        )

    def _make_outfalls_from_basins(self, basins: Sequence[StormBasin]) -> List[StormNode]:
        outfalls: List[StormNode] = []
        for basin in basins:
            pt = self._basin_connection_point(basin)
            outfalls.append(
                StormNode(
                    name=f"{basin.name}_OUTFALL",
                    node_type=StormNodeType.OUTFALL.value,
                    point=pt,
                    rim_elev_ft=basin.overflow_elev_ft,
                    invert_elev_ft=(basin.bottom_elev_ft + DEFAULT_OUTFALL_DEPTH_BUFFER_FT) if basin.bottom_elev_ft is not None else None,
                    structure_diameter_ft=4.0,
                    meta={"generated_from_basin": basin.name},
                )
            )
        return outfalls

    def _basin_connection_point(self, basin: StormBasin) -> StormPoint:
        if basin.boundary_points:
            xs = [p[0] for p in basin.boundary_points]
            ys = [p[1] for p in basin.boundary_points]
            return StormPoint(x=sum(xs) / len(xs), y=sum(ys) / len(ys), z=basin.bottom_elev_ft, label=basin.name)
        return StormPoint(x=0.0, y=0.0, z=basin.bottom_elev_ft, label=basin.name)

    # =========================================================================
    # CATCHMENT ASSIGNMENT
    # =========================================================================

    def _assign_catchments_to_inlets(
        self,
        catchments: Sequence[StormCatchment],
        inlets: Sequence[StormInlet],
        outfalls: Sequence[StormNode],
        warnings: List[str],
    ) -> None:
        if not inlets and not outfalls:
            if catchments:
                warnings.append("Catchments exist but no inlets or outfalls are available for assignment.")
            return

        for catch in catchments:
            target_inlet = self._nearest_inlet(catch, inlets)
            if target_inlet is not None:
                catch.outlet_node_name = target_inlet.name
                target_inlet.incoming_catchment_names.append(catch.name)
                target_inlet.contributing_area_sf += catch.area_sf
                target_inlet.contributing_runoff_cfs += catch.peak_runoff_cfs
            elif outfalls:
                catch.outlet_node_name = outfalls[0].name

    def _nearest_inlet(self, catch: StormCatchment, inlets: Sequence[StormInlet]) -> Optional[StormInlet]:
        if not inlets:
            return None
        ref = catch.centroid
        if ref is None:
            return inlets[0]
        best = None
        best_d = float("inf")
        for inlet in inlets:
            d = hypot(inlet.point.x - ref.x, inlet.point.y - ref.y)
            if d < best_d:
                best = inlet
                best_d = d
        return best

    # =========================================================================
    # TOPOLOGY BUILD
    # =========================================================================

    def _build_topology(
        self,
        catchments: Sequence[StormCatchment],
        inlets: Sequence[StormInlet],
        basins: Sequence[StormBasin],
        outfalls: Sequence[StormNode],
        request: StormNetworkRequest,
        routing_hook: StormRoutingHook,
        warnings: List[str],
    ) -> Tuple[List[StormPipe], List[StormFlowPath]]:
        pipes: List[StormPipe] = []
        flows: List[StormFlowPath] = []

        if not inlets:
            return pipes, flows

        target = self._pick_primary_downstream_target(basins, outfalls)
        if target is None:
            target = self._make_implied_outfall_from_inlets(inlets)

        # trunk collector point
        trunk_anchor = self._compute_trunk_anchor(inlets, target)
        trunk_node_name = f"{request.network_name}_TRUNK_J1"

        # lateral pipes inlet -> trunk
        for idx, inlet in enumerate(inlets, start=1):
            route_pts, length = self._route_or_direct(
                start=(inlet.point.x, inlet.point.y),
                goal=trunk_anchor,
                routing_hook=routing_hook,
                request=request,
                name=f"{inlet.name}_TO_TRUNK",
            )
            pipe_type = StormPipeType.LATERAL.value if request.use_laterals else StormPipeType.MAIN.value
            design_flow = inlet.contributing_runoff_cfs + inlet.bypass_runoff_cfs
            pipes.append(
                StormPipe(
                    name=f"P-{idx:03d}",
                    pipe_type=pipe_type,
                    upstream_node_name=inlet.name,
                    downstream_node_name=trunk_node_name,
                    material=request.default_pipe_material,
                    length_ft=length,
                    slope=max(request.min_pipe_slope, DEFAULT_MIN_PIPE_SLOPE),
                    min_slope=request.min_pipe_slope,
                    mannings_n=request.default_mannings_n,
                    cover_ft=request.min_cover_ft,
                    route_points=route_pts,
                    contributing_catchment_names=list(inlet.incoming_catchment_names),
                    assigned_runoff_cfs=round(design_flow, 3),
                    meta={"route_name": f"{inlet.name}_TO_TRUNK"},
                )
            )
            flows.append(
                StormFlowPath(
                    name=f"FP-{idx:03d}",
                    flow_path_type="pipe",
                    from_name=inlet.name,
                    to_name=trunk_node_name,
                    path_points=route_pts,
                    slope=max(request.min_pipe_slope, DEFAULT_MIN_PIPE_SLOPE),
                    contributing_area_sf=inlet.contributing_area_sf,
                    assigned_flow_cfs=round(design_flow, 3),
                )
            )

        # trunk pipe trunk -> target
        trunk_route_pts, trunk_length = self._route_or_direct(
            start=trunk_anchor,
            goal=(target.point.x, target.point.y),
            routing_hook=routing_hook,
            request=request,
            name="TRUNK_TO_TARGET",
        )
        total_trunk_runoff = sum(i.contributing_runoff_cfs + i.bypass_runoff_cfs for i in inlets)
        pipes.append(
            StormPipe(
                name=f"P-{len(pipes)+1:03d}",
                pipe_type=StormPipeType.TRUNK.value if request.use_trunks else StormPipeType.MAIN.value,
                upstream_node_name=trunk_node_name,
                downstream_node_name=target.name,
                material=request.default_pipe_material,
                length_ft=trunk_length,
                slope=max(request.min_pipe_slope, DEFAULT_MIN_PIPE_SLOPE),
                min_slope=request.min_pipe_slope,
                mannings_n=request.default_mannings_n,
                cover_ft=request.min_cover_ft,
                route_points=trunk_route_pts,
                contributing_catchment_names=[c.name for c in catchments],
                assigned_runoff_cfs=round(total_trunk_runoff, 3),
                meta={"route_name": "TRUNK_TO_TARGET"},
            )
        )
        flows.append(
            StormFlowPath(
                name=f"FP-{len(flows)+1:03d}",
                flow_path_type="pipe",
                from_name=trunk_node_name,
                to_name=target.name,
                path_points=trunk_route_pts,
                slope=max(request.min_pipe_slope, DEFAULT_MIN_PIPE_SLOPE),
                contributing_area_sf=sum(c.area_sf for c in catchments),
                assigned_flow_cfs=round(total_trunk_runoff, 3),
            )
        )

        return pipes, flows

    def _pick_primary_downstream_target(
        self,
        basins: Sequence[StormBasin],
        outfalls: Sequence[StormNode],
    ) -> Optional[StormNode]:
        if basins:
            basin_conn = self._basin_to_connection_node(basins[0])
            if basin_conn is not None:
                return basin_conn
        if outfalls:
            return outfalls[0]
        return None

    def _make_implied_outfall_from_inlets(self, inlets: Sequence[StormInlet]) -> StormNode:
        x = max(i.point.x for i in inlets) + 50.0
        y = min(i.point.y for i in inlets) - 20.0
        z = min((i.invert_elev_ft or 100.0) for i in inlets) - 3.0
        return StormNode(
            name="IMPLIED_OUTFALL",
            node_type=StormNodeType.OUTFALL.value,
            point=StormPoint(x=x, y=y, z=z, label="IMPLIED_OUTFALL"),
            rim_elev_ft=z + 3.0,
            invert_elev_ft=z,
        )

    def _compute_trunk_anchor(self, inlets: Sequence[StormInlet], target: StormNode) -> Tuple[float, float]:
        x = sum(i.point.x for i in inlets) / max(1, len(inlets))
        y = sum(i.point.y for i in inlets) / max(1, len(inlets))
        # bias slightly toward downstream target
        x = 0.7 * x + 0.3 * target.point.x
        y = 0.7 * y + 0.3 * target.point.y
        return (x, y)

    def _route_or_direct(
        self,
        start: Tuple[float, float],
        goal: Tuple[float, float],
        routing_hook: StormRoutingHook,
        request: StormNetworkRequest,
        name: str,
    ) -> Tuple[List[Tuple[float, float]], float]:
        if routing_hook.enabled and RoutingEngine is not None and RoutingRequest is not None:
            try:
                engine = RoutingEngine()
                rr = RoutingRequest(
                    start=type("P", (), {"x": start[0], "y": start[1]})(),
                    goal=type("P", (), {"x": goal[0], "y": goal[1]})(),
                    grid_size=routing_hook.grid_size,
                    clearance=routing_hook.clearance,
                    allow_diagonal=False,
                    prefer_axis_aligned=True,
                    system_type="storm",
                    kind="storm",
                    name=name,
                    prefer_existing_routes=routing_hook.prefer_existing_routes,
                )
                res = engine.route(rr, obstacles=[])
                if res.success and res.polyline is not None:
                    pts = [(p.x, p.y) for p in res.polyline.points]
                    return pts, self._polyline_length(pts)
            except Exception:
                pass
        pts = [start, goal]
        return pts, self._polyline_length(pts)

    def _polyline_length(self, pts: Sequence[Tuple[float, float]]) -> float:
        if len(pts) < 2:
            return 0.0
        total = 0.0
        for i in range(1, len(pts)):
            total += hypot(pts[i][0] - pts[i-1][0], pts[i][1] - pts[i-1][1])
        return round(total, 3)

    # =========================================================================
    # PIPE / NODE RELATIONSHIPS
    # =========================================================================

    def _attach_pipe_node_relationships(self, pipes: Sequence[StormPipe], node_lookup: Dict[str, StormNode]) -> None:
        for pipe in pipes:
            up = node_lookup.get(pipe.upstream_node_name)
            dn = node_lookup.get(pipe.downstream_node_name)
            if up is not None:
                up.connected_pipe_names.append(pipe.name)
            if dn is not None:
                dn.connected_pipe_names.append(pipe.name)

            if pipe.upstream_node_name not in node_lookup:
                pt = pipe.route_points[0] if pipe.route_points else (0.0, 0.0)
                node_lookup[pipe.upstream_node_name] = StormNode(
                    name=pipe.upstream_node_name,
                    node_type=StormNodeType.JUNCTION.value,
                    point=StormPoint(x=pt[0], y=pt[1], label=pipe.upstream_node_name),
                )
            if pipe.downstream_node_name not in node_lookup:
                pt = pipe.route_points[-1] if pipe.route_points else (0.0, 0.0)
                node_lookup[pipe.downstream_node_name] = StormNode(
                    name=pipe.downstream_node_name,
                    node_type=StormNodeType.JUNCTION.value,
                    point=StormPoint(x=pt[0], y=pt[1], label=pipe.downstream_node_name),
                )

    def _assign_node_runoff_from_inlets(self, inlets: Sequence[StormInlet], node_lookup: Dict[str, StormNode]) -> None:
        for inlet in inlets:
            node = node_lookup.get(inlet.name)
            if node is not None:
                node.contributing_area_sf = inlet.contributing_area_sf
                node.contributing_runoff_cfs = inlet.contributing_runoff_cfs
                node.bypass_runoff_cfs = inlet.bypass_runoff_cfs

    # =========================================================================
    # PIPE SIZING / HYDRAULIC PLACEHOLDERS
    # =========================================================================

    def _pick_pipe_row(self, design_flow_cfs: float, min_diameter_in: float, min_slope: float) -> Dict[str, float]:
        eligible = [r for r in PIPE_CAPACITY_TABLE if r["diameter_in"] >= min_diameter_in]
        if not eligible:
            return PIPE_CAPACITY_TABLE[-1]
        for row in eligible:
            if design_flow_cfs <= row["max_flow_cfs"] and row["min_slope"] <= max(min_slope, 0.0) + 1e-9:
                return row
        for row in eligible:
            if design_flow_cfs <= row["max_flow_cfs"]:
                return row
        return eligible[-1]

    def _size_pipes(self, pipes: Sequence[StormPipe], request: StormNetworkRequest, warnings: List[str]) -> None:
        for pipe in pipes:
            row = self._pick_pipe_row(
                design_flow_cfs=max(0.0, pipe.assigned_runoff_cfs),
                min_diameter_in=max(request.min_diameter_in, DEFAULT_MIN_DIAMETER_IN),
                min_slope=max(request.min_pipe_slope, DEFAULT_MIN_PIPE_SLOPE),
            )
            pipe.diameter_in = row["diameter_in"]
            pipe.slope = max(pipe.slope, row["min_slope"], request.min_pipe_slope)
            pipe.min_slope = max(pipe.min_slope, row["min_slope"], request.min_pipe_slope)
            pipe.mannings_n = request.default_mannings_n or DEFAULT_DEFAULT_MANNINGS_N
            pipe.cover_ft = max(request.min_cover_ft, DEFAULT_MIN_COVER_FT)
            if pipe.assigned_runoff_cfs > row["max_flow_cfs"]:
                pipe.warnings.append("Assigned runoff exceeds simplified concept capacity table.")
                warnings.append(f"Pipe '{pipe.name}' exceeds concept capacity table.")

    def _assign_hydraulic_status(self, pipes: Sequence[StormPipe], request: StormNetworkRequest, warnings: List[str]) -> None:
        for pipe in pipes:
            row = self._pick_pipe_row(pipe.assigned_runoff_cfs, pipe.diameter_in, pipe.min_slope)
            full_capacity = row["max_flow_cfs"]
            velocity = 0.0
            if pipe.length_ft > 0:
                velocity = max(0.5, pipe.assigned_runoff_cfs / max(0.1, (pipe.diameter_in / 12.0) ** 2))
            status = CapacityStatus.OK.value
            if pipe.assigned_runoff_cfs > full_capacity:
                status = CapacityStatus.DEFICIENT.value
            elif pipe.assigned_runoff_cfs > 0.85 * full_capacity:
                status = CapacityStatus.MARGINAL.value

            pipe.hydraulic = HydraulicCheck(
                design_flow_cfs=round(pipe.assigned_runoff_cfs, 3),
                full_capacity_cfs=round(full_capacity, 3),
                velocity_fps=round(velocity, 3),
                flow_depth_ratio=round(min(1.0, pipe.assigned_runoff_cfs / max(full_capacity, 0.1)), 4),
                capacity_status=status,
                warnings=list(pipe.warnings),
            )

            if status == CapacityStatus.DEFICIENT.value:
                warnings.append(f"Pipe '{pipe.name}' is deficient by simplified capacity logic.")

    # =========================================================================
    # RELATIVE INVERT SYSTEM
    # =========================================================================

    def _assign_relative_inverts(
        self,
        pipes: Sequence[StormPipe],
        node_lookup: Dict[str, StormNode],
        request: StormNetworkRequest,
        warnings: List[str],
    ) -> None:
        # downstream control elevations first
        for node in node_lookup.values():
            if node.invert_elev_ft is None and node.rim_elev_ft is not None:
                node.invert_elev_ft = node.rim_elev_ft - DEFAULT_NODE_RIM_TO_INVERT_DROP_FT

        # trunk/outfall-like pipes first, then laterals
        ordered = sorted(
            pipes,
            key=lambda p: (
                0 if p.pipe_type == StormPipeType.TRUNK.value else 1,
                -p.assigned_runoff_cfs,
            )
        )

        for pipe in ordered:
            up = node_lookup.get(pipe.upstream_node_name)
            dn = node_lookup.get(pipe.downstream_node_name)
            if dn is None or up is None:
                continue

            if dn.invert_elev_ft is None:
                if dn.rim_elev_ft is not None:
                    dn.invert_elev_ft = dn.rim_elev_ft - DEFAULT_NODE_RIM_TO_INVERT_DROP_FT
                else:
                    dn.invert_elev_ft = 95.0

            required_drop = max(pipe.min_slope, request.min_pipe_slope) * max(pipe.length_ft, 0.0)
            pipe.downstream_invert_ft = dn.invert_elev_ft
            pipe.upstream_invert_ft = pipe.downstream_invert_ft + required_drop

            if up.invert_elev_ft is None:
                up.invert_elev_ft = pipe.upstream_invert_ft
            else:
                up.invert_elev_ft = max(up.invert_elev_ft, pipe.upstream_invert_ft)

            if up.rim_elev_ft is None:
                if up.point.z is not None:
                    up.rim_elev_ft = up.point.z
                else:
                    up.rim_elev_ft = up.invert_elev_ft + DEFAULT_NODE_RIM_TO_INVERT_DROP_FT

            if dn.rim_elev_ft is None:
                if dn.point.z is not None:
                    dn.rim_elev_ft = dn.point.z
                else:
                    dn.rim_elev_ft = dn.invert_elev_ft + DEFAULT_NODE_RIM_TO_INVERT_DROP_FT

            if pipe.downstream_invert_ft >= pipe.upstream_invert_ft:
                pipe.warnings.append("Downstream invert is not below upstream invert.")
                warnings.append(f"Pipe '{pipe.name}' has invalid invert direction.")

    # =========================================================================
    # OUTPUT / HOOKS
    # =========================================================================

    def _build_explain(
        self,
        network: StormNetwork,
        outfalls: Sequence[StormNode],
        warnings: Sequence[str],
    ) -> StormNetworkExplain:
        exp = StormNetworkExplain()
        exp.key_logic = [
            "Catchments were assigned to nearest available storm inlets.",
            "Inlets were connected to a collector/trunk anchor.",
            "A trunk pipe was routed from the collector to a basin/outfall target.",
            "Pipes were sized from a simplified concept storm capacity table.",
            "Relative invert elevations were assigned to maintain downstream flow.",
        ]
        exp.selected_outfall_name = outfalls[0].name if outfalls else None
        exp.inlet_assignments = [
            {
                "inlet_name": i.name,
                "catchments": list(i.incoming_catchment_names),
                "runoff_cfs": round(i.contributing_runoff_cfs + i.bypass_runoff_cfs, 3),
            }
            for i in network.inlets
        ]
        exp.pipe_decisions = [
            {
                "pipe_name": p.name,
                "pipe_type": p.pipe_type,
                "diameter_in": p.diameter_in,
                "slope": p.slope,
                "assigned_runoff_cfs": p.assigned_runoff_cfs,
                "capacity_cfs": p.hydraulic.full_capacity_cfs,
                "status": p.hydraulic.capacity_status,
            }
            for p in network.pipes
        ]
        exp.network_warnings = list(warnings)
        return exp

    def _build_optimize_hooks(self, network: StormNetwork) -> Dict[str, Any]:
        total_bypass = sum(i.bypass_runoff_cfs for i in network.inlets)
        deficient = sum(1 for p in network.pipes if p.hydraulic.capacity_status == CapacityStatus.DEFICIENT.value)
        return {
            "penalties": {
                "pipe_length_penalty": round(sum(p.length_ft for p in network.pipes) / 100.0, 3),
                "bypass_penalty": round(total_bypass * 12.0, 3),
                "deficiency_penalty": deficient * 25.0,
            },
            "candidate_improvements": [
                "shorten lateral routes",
                "increase inlet count where bypass remains high",
                "increase trunk capacity or slope where deficiencies remain",
                "move basin/outfall target to reduce total pipe length",
            ],
        }

    def _build_conflict_hooks(self, network: StormNetwork) -> Dict[str, Any]:
        return {
            "storm_nodes": [
                {
                    "name": n.name,
                    "node_type": n.node_type,
                    "x": n.point.x,
                    "y": n.point.y,
                    "rim_elev_ft": n.rim_elev_ft,
                    "invert_elev_ft": n.invert_elev_ft,
                }
                for n in network.nodes
            ],
            "storm_pipes": [
                {
                    "name": p.name,
                    "pipe_type": p.pipe_type,
                    "upstream_node_name": p.upstream_node_name,
                    "downstream_node_name": p.downstream_node_name,
                    "route_points": list(p.route_points),
                    "diameter_in": p.diameter_in,
                    "upstream_invert_ft": p.upstream_invert_ft,
                    "downstream_invert_ft": p.downstream_invert_ft,
                    "cover_ft": p.cover_ft,
                }
                for p in network.pipes
            ],
        }


def build_storm_network(
    request: StormNetworkRequest,
    *,
    routing_hook: Optional[StormRoutingHook] = None,
) -> StormNetworkResult:
    return StormNetworkEngine().build_network(request, routing_hook=routing_hook)
