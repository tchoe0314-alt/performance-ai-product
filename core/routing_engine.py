
from __future__ import annotations

"""
routing_engine.py (MERGED TRUE MAX VERSION)

Purpose
-------
System-aware, terrain-aware, conflict-aware routing engine for the AI civil
engineering platform.

This version preserves the strong original base:
- stable A* search
- obstacle avoidance
- bend penalties
- axis-aligned preference
- project graph integration
- route reservation behavior

And adds:
- system profiles (storm / sanitary / water / road / walk / generic utility)
- BOTH gravity modes:
    - strict
    - penalty
- slope-aware routing hooks
- corridor/easement preference and enforcement
- multi-objective routing cost model
- alternative route generation
- route explanation/cost breakdown
- conflict/compliance/planner-ready metadata
- trunk/lateral reuse hooks
"""

from dataclasses import dataclass, field
from enum import Enum
from heapq import heappop, heappush
from itertools import count
from math import hypot
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from core.geometry_core import (
    BoundingBox2D,
    NetworkGraph,
    Node,
    Edge,
    Obstacle,
    Point2D,
    Point3D,
    Polyline2D,
    ProjectModel,
)

EPS = 1e-9


# =============================================================================
# ENUMS / SYSTEM PROFILES
# =============================================================================

class GravityMode(str, Enum):
    STRICT = "strict"
    PENALTY = "penalty"
    OFF = "off"


class RouteSystemType(str, Enum):
    GENERIC = "generic"
    STORM = "storm"
    SANITARY = "sanitary"
    WATER = "water"
    UTILITY = "utility"
    ROAD = "road"
    WALK = "walk"


@dataclass
class RoutingSystemProfile:
    system_type: str = RouteSystemType.GENERIC.value
    gravity_mode: str = GravityMode.OFF.value
    min_slope: float = 0.0
    max_grade: Optional[float] = None
    prefer_corridor: bool = False
    require_corridor: bool = False
    allow_diagonal: bool = False
    prefer_axis_aligned: bool = True
    bend_penalty: float = 2.0
    slope_penalty_factor: float = 0.0
    uphill_penalty_factor: float = 0.0
    crossing_penalty: float = 0.0
    obstacle_penalty: float = 1e6
    route_reuse_reward: float = 0.0


SYSTEM_PROFILES: Dict[str, RoutingSystemProfile] = {
    RouteSystemType.GENERIC.value: RoutingSystemProfile(
        system_type=RouteSystemType.GENERIC.value,
        gravity_mode=GravityMode.OFF.value,
        allow_diagonal=False,
        prefer_axis_aligned=True,
        bend_penalty=2.0,
        obstacle_penalty=1e6,
    ),
    RouteSystemType.STORM.value: RoutingSystemProfile(
        system_type=RouteSystemType.STORM.value,
        gravity_mode=GravityMode.STRICT.value,
        min_slope=0.003,
        prefer_corridor=True,
        allow_diagonal=False,
        prefer_axis_aligned=True,
        bend_penalty=2.5,
        slope_penalty_factor=8.0,
        uphill_penalty_factor=500.0,
        crossing_penalty=50.0,
        obstacle_penalty=1e6,
        route_reuse_reward=0.5,
    ),
    RouteSystemType.SANITARY.value: RoutingSystemProfile(
        system_type=RouteSystemType.SANITARY.value,
        gravity_mode=GravityMode.STRICT.value,
        min_slope=0.004,
        prefer_corridor=True,
        allow_diagonal=False,
        prefer_axis_aligned=True,
        bend_penalty=3.0,
        slope_penalty_factor=10.0,
        uphill_penalty_factor=750.0,
        crossing_penalty=75.0,
        obstacle_penalty=1e6,
        route_reuse_reward=0.3,
    ),
    RouteSystemType.WATER.value: RoutingSystemProfile(
        system_type=RouteSystemType.WATER.value,
        gravity_mode=GravityMode.PENALTY.value,
        prefer_corridor=True,
        allow_diagonal=False,
        prefer_axis_aligned=True,
        bend_penalty=2.0,
        uphill_penalty_factor=4.0,
        crossing_penalty=25.0,
        obstacle_penalty=1e6,
        route_reuse_reward=1.0,
    ),
    RouteSystemType.UTILITY.value: RoutingSystemProfile(
        system_type=RouteSystemType.UTILITY.value,
        gravity_mode=GravityMode.PENALTY.value,
        prefer_corridor=True,
        allow_diagonal=False,
        prefer_axis_aligned=True,
        bend_penalty=2.0,
        uphill_penalty_factor=2.0,
        crossing_penalty=20.0,
        obstacle_penalty=1e6,
        route_reuse_reward=1.0,
    ),
    RouteSystemType.ROAD.value: RoutingSystemProfile(
        system_type=RouteSystemType.ROAD.value,
        gravity_mode=GravityMode.PENALTY.value,
        max_grade=0.08,
        prefer_corridor=False,
        allow_diagonal=True,
        prefer_axis_aligned=False,
        bend_penalty=8.0,
        slope_penalty_factor=15.0,
        uphill_penalty_factor=8.0,
        crossing_penalty=100.0,
        obstacle_penalty=1e7,
    ),
    RouteSystemType.WALK.value: RoutingSystemProfile(
        system_type=RouteSystemType.WALK.value,
        gravity_mode=GravityMode.PENALTY.value,
        max_grade=0.05,
        prefer_corridor=False,
        allow_diagonal=True,
        prefer_axis_aligned=False,
        bend_penalty=3.0,
        slope_penalty_factor=25.0,
        uphill_penalty_factor=12.0,
        crossing_penalty=10.0,
        obstacle_penalty=1e6,
    ),
}


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class RouteCorridor:
    name: str
    boundary: BoundingBox2D
    system_types: List[str] = field(default_factory=list)
    penalty_outside: float = 15.0
    required: bool = False


@dataclass
class RouteReservation:
    polyline: Polyline2D
    width: float
    name: str
    kind: str
    cost_reward: float = 0.0


@dataclass
class ElevationGrid:
    """
    Optional terrain abstraction for slope-aware routing.
    Expects either:
    - callable get_z(x, y)
    - or a lightweight grid-like object with sample(x, y)
    """
    sampler: object

    def z_at(self, x: float, y: float) -> float:
        if hasattr(self.sampler, "get_z"):
            return float(self.sampler.get_z(x, y))
        if hasattr(self.sampler, "sample"):
            return float(self.sampler.sample(x, y))
        if callable(self.sampler):
            return float(self.sampler(x, y))
        return 0.0


@dataclass
class RoutingRequest:
    start: Point2D
    goal: Point2D
    grid_size: float = 5.0
    clearance: float = 0.0
    boundary: Optional[BoundingBox2D] = None

    # Original behavior controls (preserved)
    allow_diagonal: bool = False
    prefer_axis_aligned: bool = True
    obstacle_penalty: float = 1e6
    bend_penalty: float = 2.0

    layer_name: str = "ROUTE"
    kind: str = "generic"
    name: Optional[str] = None
    level: Optional[str] = None
    meta: Dict[str, object] = field(default_factory=dict)

    # New max controls
    system_type: str = RouteSystemType.GENERIC.value
    gravity_mode: Optional[str] = None
    min_slope: Optional[float] = None
    max_grade: Optional[float] = None
    terrain: Optional[ElevationGrid] = None
    corridors: List[RouteCorridor] = field(default_factory=list)
    prefer_existing_routes: bool = False
    existing_reservations: List[RouteReservation] = field(default_factory=list)
    crossing_penalty: Optional[float] = None
    uphill_penalty_factor: Optional[float] = None
    slope_penalty_factor: Optional[float] = None
    require_corridor: Optional[bool] = None
    prefer_corridor: Optional[bool] = None
    max_alternatives: int = 1


@dataclass
class RouteCostBreakdown:
    distance_cost: float = 0.0
    bend_cost: float = 0.0
    slope_cost: float = 0.0
    uphill_cost: float = 0.0
    corridor_cost: float = 0.0
    crossing_cost: float = 0.0
    reuse_reward: float = 0.0
    obstacle_cost: float = 0.0

    def total(self) -> float:
        return (
            self.distance_cost
            + self.bend_cost
            + self.slope_cost
            + self.uphill_cost
            + self.corridor_cost
            + self.crossing_cost
            + self.obstacle_cost
            - self.reuse_reward
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            "distance_cost": round(self.distance_cost, 6),
            "bend_cost": round(self.bend_cost, 6),
            "slope_cost": round(self.slope_cost, 6),
            "uphill_cost": round(self.uphill_cost, 6),
            "corridor_cost": round(self.corridor_cost, 6),
            "crossing_cost": round(self.crossing_cost, 6),
            "reuse_reward": round(self.reuse_reward, 6),
            "obstacle_cost": round(self.obstacle_cost, 6),
            "total": round(self.total(), 6),
        }


@dataclass
class RoutingAlternative:
    rank: int
    polyline: Polyline2D
    total_cost: float
    cost_breakdown: Dict[str, float]
    message: str = ""


@dataclass
class RoutingResult:
    success: bool
    polyline: Optional[Polyline2D] = None
    message: str = ""
    visited_nodes: int = 0
    total_cost: float = 0.0
    graph_node_ids: List[str] = field(default_factory=list)
    graph_edge_ids: List[str] = field(default_factory=list)

    # New max outputs
    cost_breakdown: Dict[str, float] = field(default_factory=dict)
    route_system_type: str = RouteSystemType.GENERIC.value
    gravity_mode_used: str = GravityMode.OFF.value
    stage_notes: List[str] = field(default_factory=list)
    reasoning: List[str] = field(default_factory=list)
    avoided_obstacle_count: int = 0
    corridors_used: List[str] = field(default_factory=list)
    alternatives: List[RoutingAlternative] = field(default_factory=list)
    metadata: Dict[str, object] = field(default_factory=dict)


# =============================================================================
# ENGINE
# =============================================================================

class RoutingEngine:
    """
    Expanded routing engine preserving the original A* foundation while adding:
    - system profiles
    - both strict + penalty gravity modes
    - terrain/slope-aware routing
    - corridor preferences and enforcement
    - route reservation/reuse
    - route explanations and alternatives
    """

    def route(
        self,
        request: RoutingRequest,
        obstacles: Sequence[Obstacle] | None = None,
    ) -> RoutingResult:
        obstacles = list(obstacles or [])

        if request.grid_size <= 0.0:
            return RoutingResult(False, message="grid_size must be greater than zero.")

        profile = self._resolve_profile(request)
        boundary = request.boundary or self._make_auto_boundary(
            request.start,
            request.goal,
            obstacles,
            request.grid_size,
            request.clearance,
        )

        blocked = self._build_blocked_cells(
            boundary=boundary,
            obstacles=obstacles,
            grid_size=request.grid_size,
            clearance=request.clearance,
        )

        start_cell = self._snap_point_to_cell(request.start, boundary, request.grid_size)
        goal_cell = self._snap_point_to_cell(request.goal, boundary, request.grid_size)

        if start_cell in blocked:
            return RoutingResult(False, message="Start point falls inside blocked routing space.")
        if goal_cell in blocked:
            return RoutingResult(False, message="Goal point falls inside blocked routing space.")

        path_cells, visited_count, total_cost, breakdown = self._astar(
            request=request,
            profile=profile,
            start=start_cell,
            goal=goal_cell,
            blocked=blocked,
            boundary=boundary,
            grid_size=request.grid_size,
        )

        if not path_cells:
            return RoutingResult(
                success=False,
                message="No valid route found.",
                visited_nodes=visited_count,
                total_cost=0.0,
                route_system_type=profile.system_type,
                gravity_mode_used=profile.gravity_mode,
            )

        raw_points = [
            self._cell_center_to_point(cell, boundary, request.grid_size)
            for cell in path_cells
        ]

        simplified = self._simplify_path_points(
            raw_points,
            prefer_axis_aligned=profile.prefer_axis_aligned,
        )

        if simplified:
            simplified[0] = Point2D(request.start.x, request.start.y)
            simplified[-1] = Point2D(request.goal.x, request.goal.y)

        polyline = Polyline2D(points=simplified, closed=False)

        reasoning = self._build_reasoning(request, profile, blocked_count=len(blocked))
        corridors_used = self._corridors_touched(polyline, request.corridors)

        alternatives = self._generate_alternatives(
            request=request,
            profile=profile,
            obstacles=obstacles,
            boundary=boundary,
            blocked=blocked,
            start_cell=start_cell,
            goal_cell=goal_cell,
            primary_polyline=polyline,
        )

        return RoutingResult(
            success=True,
            polyline=polyline,
            message="Route created successfully.",
            visited_nodes=visited_count,
            total_cost=round(total_cost, 3),
            cost_breakdown=breakdown.to_dict(),
            route_system_type=profile.system_type,
            gravity_mode_used=profile.gravity_mode,
            stage_notes=[
                "A* route search completed.",
                "Path simplified for engineering-style output.",
            ],
            reasoning=reasoning,
            avoided_obstacle_count=len(blocked),
            corridors_used=corridors_used,
            alternatives=alternatives,
            metadata={
                "profile": {
                    "system_type": profile.system_type,
                    "gravity_mode": profile.gravity_mode,
                    "min_slope": profile.min_slope,
                    "max_grade": profile.max_grade,
                    "prefer_corridor": profile.prefer_corridor,
                    "require_corridor": profile.require_corridor,
                }
            },
        )

    def route_into_project(
        self,
        project: ProjectModel,
        request: RoutingRequest,
        obstacles: Sequence[Obstacle] | None = None,
        graph_name: Optional[str] = None,
    ) -> RoutingResult:
        result = self.route(request=request, obstacles=obstacles or list(project.obstacles.values()))
        if not result.success or result.polyline is None:
            return result

        graph = NetworkGraph(
            name=graph_name or request.name or "Route Graph",
            kind=request.kind,
            meta={
                "layer_name": request.layer_name,
                "route_system_type": request.system_type,
                "gravity_mode_used": result.gravity_mode_used,
                **request.meta,
            },
        )

        node_ids: List[str] = []
        for idx, pt in enumerate(result.polyline.points):
            z = request.terrain.z_at(pt.x, pt.y) if request.terrain else 0.0
            node = Node(
                point=Point3D(pt.x, pt.y, z),
                kind=request.kind,
                name=f"{request.name or request.kind}_N{idx + 1}",
                level=request.level,
                meta={"route_role": "path_node"},
            )
            node_ids.append(graph.add_node(node))

        edge_ids: List[str] = []
        for i in range(len(node_ids) - 1):
            p1 = result.polyline.points[i]
            p2 = result.polyline.points[i + 1]
            edge = Edge(
                start_node_id=node_ids[i],
                end_node_id=node_ids[i + 1],
                kind=request.kind,
                geometry=Polyline2D([p1, p2], closed=False),
                meta={
                    "layer_name": request.layer_name,
                    "route_name": request.name,
                    "route_system_type": request.system_type,
                    "gravity_mode_used": result.gravity_mode_used,
                },
            )
            edge_ids.append(graph.add_edge(edge))

        project.add_graph(graph)
        result.graph_node_ids = node_ids
        result.graph_edge_ids = edge_ids
        return result

    def route_multiple(
        self,
        requests: Sequence[RoutingRequest],
        obstacles: Sequence[Obstacle] | None = None,
    ) -> List[RoutingResult]:
        shared_obstacles = list(obstacles or [])
        shared_reservations: List[RouteReservation] = []
        results: List[RoutingResult] = []

        for req in requests:
            req_local = RoutingRequest(**{**req.__dict__})
            req_local.existing_reservations = list(req.existing_reservations) + shared_reservations
            result = self.route(req_local, shared_obstacles)
            results.append(result)

            if result.success and result.polyline is not None:
                route_obstacles = self._polyline_to_obstacles(
                    result.polyline,
                    width=req.grid_size * 0.6,
                    name=req.name or req.kind,
                )
                shared_obstacles.extend(route_obstacles)
                shared_reservations.append(
                    RouteReservation(
                        polyline=result.polyline,
                        width=req.grid_size * 0.6,
                        name=req.name or req.kind,
                        kind=req.system_type,
                        cost_reward=SYSTEM_PROFILES.get(req.system_type, SYSTEM_PROFILES[RouteSystemType.GENERIC.value]).route_reuse_reward,
                    )
                )

        return results

    # =========================================================================
    # PROFILE / REASONING
    # =========================================================================

    def _resolve_profile(self, request: RoutingRequest) -> RoutingSystemProfile:
        base = SYSTEM_PROFILES.get(request.system_type, SYSTEM_PROFILES[RouteSystemType.GENERIC.value])
        profile = RoutingSystemProfile(**base.__dict__)
        if request.gravity_mode is not None:
            profile.gravity_mode = request.gravity_mode
        if request.min_slope is not None:
            profile.min_slope = request.min_slope
        if request.max_grade is not None:
            profile.max_grade = request.max_grade
        if request.crossing_penalty is not None:
            profile.crossing_penalty = request.crossing_penalty
        if request.uphill_penalty_factor is not None:
            profile.uphill_penalty_factor = request.uphill_penalty_factor
        if request.slope_penalty_factor is not None:
            profile.slope_penalty_factor = request.slope_penalty_factor
        if request.require_corridor is not None:
            profile.require_corridor = request.require_corridor
        if request.prefer_corridor is not None:
            profile.prefer_corridor = request.prefer_corridor
        profile.allow_diagonal = request.allow_diagonal if request.allow_diagonal != base.allow_diagonal else base.allow_diagonal
        profile.prefer_axis_aligned = request.prefer_axis_aligned if request.prefer_axis_aligned != base.prefer_axis_aligned else base.prefer_axis_aligned
        profile.bend_penalty = request.bend_penalty if abs(request.bend_penalty - 2.0) > EPS else base.bend_penalty
        profile.obstacle_penalty = request.obstacle_penalty if abs(request.obstacle_penalty - 1e6) > EPS else base.obstacle_penalty
        return profile

    def _build_reasoning(self, request: RoutingRequest, profile: RoutingSystemProfile, blocked_count: int) -> List[str]:
        notes = [
            f"System profile '{profile.system_type}' was used.",
            f"Gravity mode '{profile.gravity_mode}' was applied.",
            f"Grid size {request.grid_size:.2f} ft controlled route resolution.",
            f"{blocked_count} blocked cells were avoided during search.",
        ]
        if profile.prefer_corridor:
            notes.append("Corridors/easements were preferred where available.")
        if profile.require_corridor:
            notes.append("Routing was constrained to allowed corridors where possible.")
        if request.prefer_existing_routes or request.existing_reservations:
            notes.append("Existing route reservations were considered for reuse.")
        return notes

    # =========================================================================
    # COST MODEL
    # =========================================================================

    def _segment_grade(self, request: RoutingRequest, p1: Point2D, p2: Point2D) -> float:
        if not request.terrain:
            return 0.0
        z1 = request.terrain.z_at(p1.x, p1.y)
        z2 = request.terrain.z_at(p2.x, p2.y)
        dist = max(hypot(p2.x - p1.x, p2.y - p1.y), EPS)
        return (z2 - z1) / dist

    def _corridor_cost(self, request: RoutingRequest, profile: RoutingSystemProfile, p: Point2D) -> float:
        if not request.corridors:
            return 0.0
        matching = [
            c for c in request.corridors
            if not c.system_types or profile.system_type in c.system_types
        ]
        if not matching:
            return 0.0
        inside_any = any(c.boundary.contains_point(p, inclusive=True) for c in matching)
        if inside_any:
            return 0.0
        if profile.require_corridor:
            return profile.obstacle_penalty
        if profile.prefer_corridor:
            return min(c.penalty_outside for c in matching)
        return 0.0

    def _reuse_reward(self, request: RoutingRequest, p: Point2D) -> float:
        reward = 0.0
        for res in request.existing_reservations:
            pts = res.polyline.points
            for i in range(1, len(pts)):
                d = _point_to_segment_distance(p.x, p.y, pts[i-1].x, pts[i-1].y, pts[i].x, pts[i].y)
                if d <= max(1.0, res.width):
                    reward = max(reward, float(res.cost_reward))
        return reward

    def _crossing_penalty(self, request: RoutingRequest, current_pt: Point2D, next_pt: Point2D) -> float:
        if not request.existing_reservations:
            return 0.0
        penalty = 0.0
        a1 = (current_pt.x, current_pt.y)
        a2 = (next_pt.x, next_pt.y)
        for res in request.existing_reservations:
            pts = res.polyline.points
            for i in range(1, len(pts)):
                b1 = (pts[i-1].x, pts[i-1].y)
                b2 = (pts[i].x, pts[i].y)
                if _segments_intersect(a1, a2, b1, b2):
                    penalty += max(0.0, SYSTEM_PROFILES.get(request.system_type, SYSTEM_PROFILES[RouteSystemType.GENERIC.value]).crossing_penalty)
        return penalty

    def _move_cost(
        self,
        request: RoutingRequest,
        profile: RoutingSystemProfile,
        current_pt: Point2D,
        next_pt: Point2D,
        base_distance_cost: float,
        turn_cost: float,
    ) -> RouteCostBreakdown:
        breakdown = RouteCostBreakdown()
        breakdown.distance_cost = base_distance_cost
        breakdown.bend_cost = turn_cost

        grade = self._segment_grade(request, current_pt, next_pt)
        if request.terrain:
            if profile.gravity_mode == GravityMode.STRICT.value:
                if profile.system_type in {RouteSystemType.STORM.value, RouteSystemType.SANITARY.value}:
                    # strict: must fall at least min_slope from start to end
                    if grade > -max(profile.min_slope, EPS):
                        breakdown.uphill_cost += profile.obstacle_penalty
                    else:
                        if profile.min_slope > 0 and abs(grade) < profile.min_slope:
                            breakdown.slope_cost += profile.obstacle_penalty * 0.25
                elif profile.max_grade is not None and abs(grade) > profile.max_grade:
                    breakdown.slope_cost += profile.obstacle_penalty * 0.25
            elif profile.gravity_mode == GravityMode.PENALTY.value:
                if profile.system_type in {RouteSystemType.STORM.value, RouteSystemType.SANITARY.value}:
                    if grade > 0.0:
                        breakdown.uphill_cost += grade * base_distance_cost * max(profile.uphill_penalty_factor, 1.0)
                    if profile.min_slope > 0 and abs(grade) < profile.min_slope:
                        breakdown.slope_cost += (profile.min_slope - abs(grade)) * base_distance_cost * max(profile.slope_penalty_factor, 1.0)
                elif profile.max_grade is not None and abs(grade) > profile.max_grade:
                    breakdown.slope_cost += (abs(grade) - profile.max_grade) * base_distance_cost * max(profile.slope_penalty_factor, 1.0)

        breakdown.corridor_cost = self._corridor_cost(request, profile, next_pt)
        breakdown.crossing_cost = self._crossing_penalty(request, current_pt, next_pt)
        breakdown.reuse_reward = self._reuse_reward(request, next_pt)
        return breakdown

    # =========================================================================
    # SEARCH
    # =========================================================================

    def _astar(
        self,
        request: RoutingRequest,
        profile: RoutingSystemProfile,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        blocked: set[Tuple[int, int]],
        boundary: BoundingBox2D,
        grid_size: float,
    ) -> Tuple[List[Tuple[int, int]], int, float, RouteCostBreakdown]:
        open_heap: List[Tuple[float, float, int, Tuple[int, int], Optional[Tuple[int, int]], RouteCostBreakdown]] = []
        tie = count()

        start_h = self._heuristic(start, goal, profile.allow_diagonal, grid_size)
        heappush(open_heap, (start_h, 0.0, next(tie), start, None, RouteCostBreakdown()))

        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        g_score: Dict[Tuple[int, int], float] = {start: 0.0}
        cost_map: Dict[Tuple[int, int], RouteCostBreakdown] = {start: RouteCostBreakdown()}
        closed_set: set[Tuple[int, int]] = set()
        visited = 0

        while open_heap:
            _, current_g, _, current, prev_direction, current_breakdown = heappop(open_heap)

            if current in closed_set:
                continue

            closed_set.add(current)
            visited += 1

            if current == goal:
                path = self._reconstruct_path(came_from, current)
                return path, visited, current_g, current_breakdown

            current_pt = self._cell_center_to_point(current, boundary, grid_size)

            for neighbor, move_dir, move_cost in self._neighbors(
                current,
                boundary,
                grid_size,
                profile.allow_diagonal,
            ):
                if neighbor in blocked or neighbor in closed_set:
                    continue

                if profile.allow_diagonal and self._is_diagonal(move_dir):
                    if self._cuts_corner(current, move_dir, blocked):
                        continue

                turn_cost = 0.0
                if prev_direction is not None and move_dir != prev_direction:
                    turn_cost = profile.bend_penalty

                adjusted_move_cost = move_cost
                if profile.prefer_axis_aligned and self._is_diagonal(move_dir):
                    adjusted_move_cost *= 1.25

                next_pt = self._cell_center_to_point(neighbor, boundary, grid_size)
                move_breakdown = self._move_cost(request, profile, current_pt, next_pt, adjusted_move_cost, turn_cost)
                move_total = move_breakdown.total()
                tentative_g = g_score[current] + move_total

                if tentative_g + EPS < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    accum = RouteCostBreakdown(
                        distance_cost=current_breakdown.distance_cost + move_breakdown.distance_cost,
                        bend_cost=current_breakdown.bend_cost + move_breakdown.bend_cost,
                        slope_cost=current_breakdown.slope_cost + move_breakdown.slope_cost,
                        uphill_cost=current_breakdown.uphill_cost + move_breakdown.uphill_cost,
                        corridor_cost=current_breakdown.corridor_cost + move_breakdown.corridor_cost,
                        crossing_cost=current_breakdown.crossing_cost + move_breakdown.crossing_cost,
                        reuse_reward=current_breakdown.reuse_reward + move_breakdown.reuse_reward,
                        obstacle_cost=current_breakdown.obstacle_cost + move_breakdown.obstacle_cost,
                    )
                    cost_map[neighbor] = accum
                    f_score = tentative_g + self._heuristic(neighbor, goal, profile.allow_diagonal, grid_size)
                    heappush(open_heap, (f_score, tentative_g, next(tie), neighbor, move_dir, accum))

        return [], visited, 0.0, RouteCostBreakdown()

    def _neighbors(
        self,
        cell: Tuple[int, int],
        boundary: BoundingBox2D,
        grid_size: float,
        allow_diagonal: bool,
    ) -> Iterable[Tuple[Tuple[int, int], Tuple[int, int], float]]:
        x, y = cell
        steps = [
            ((1, 0), grid_size),
            ((-1, 0), grid_size),
            ((0, 1), grid_size),
            ((0, -1), grid_size),
        ]
        if allow_diagonal:
            diag = grid_size * 1.41421356237
            steps += [
                ((1, 1), diag),
                ((1, -1), diag),
                ((-1, 1), diag),
                ((-1, -1), diag),
            ]

        max_ix = max(0, int(round(boundary.width / grid_size)))
        max_iy = max(0, int(round(boundary.height / grid_size)))

        for (dx, dy), cost in steps:
            nx, ny = x + dx, y + dy
            if 0 <= nx <= max_ix and 0 <= ny <= max_iy:
                yield (nx, ny), (dx, dy), cost

    def _heuristic(
        self,
        a: Tuple[int, int],
        b: Tuple[int, int],
        allow_diagonal: bool,
        grid_size: float,
    ) -> float:
        dx = abs(a[0] - b[0])
        dy = abs(a[1] - b[1])
        if allow_diagonal:
            return hypot(dx, dy) * grid_size
        return float(dx + dy) * grid_size

    def _reconstruct_path(
        self,
        came_from: Dict[Tuple[int, int], Tuple[int, int]],
        current: Tuple[int, int],
    ) -> List[Tuple[int, int]]:
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path

    # =========================================================================
    # BLOCKING / SNAP / BOUNDARY
    # =========================================================================

    def _build_blocked_cells(
        self,
        boundary: BoundingBox2D,
        obstacles: Sequence[Obstacle],
        grid_size: float,
        clearance: float,
    ) -> set[Tuple[int, int]]:
        blocked: set[Tuple[int, int]] = set()

        max_ix = max(0, int(round(boundary.width / grid_size)))
        max_iy = max(0, int(round(boundary.height / grid_size)))

        for obs in obstacles:
            box = obs.boundary.bbox.expanded(obs.clearance + clearance)

            min_ix = max(0, int((box.min_x - boundary.min_x) // grid_size) - 1)
            min_iy = max(0, int((box.min_y - boundary.min_y) // grid_size) - 1)
            max_ix_box = min(max_ix, int((box.max_x - boundary.min_x) // grid_size) + 1)
            max_iy_box = min(max_iy, int((box.max_y - boundary.min_y) // grid_size) + 1)

            for ix in range(min_ix, max_ix_box + 1):
                for iy in range(min_iy, max_iy_box + 1):
                    pt = self._cell_center_to_point((ix, iy), boundary, grid_size)
                    if box.contains_point(pt, inclusive=True):
                        blocked.add((ix, iy))

        return blocked

    def _snap_point_to_cell(
        self,
        pt: Point2D,
        boundary: BoundingBox2D,
        grid_size: float,
    ) -> Tuple[int, int]:
        ix = int(round((pt.x - boundary.min_x) / grid_size))
        iy = int(round((pt.y - boundary.min_y) / grid_size))

        max_ix = max(0, int(round(boundary.width / grid_size)))
        max_iy = max(0, int(round(boundary.height / grid_size)))

        ix = max(0, min(max_ix, ix))
        iy = max(0, min(max_iy, iy))
        return ix, iy

    def _cell_center_to_point(
        self,
        cell: Tuple[int, int],
        boundary: BoundingBox2D,
        grid_size: float,
    ) -> Point2D:
        ix, iy = cell
        return Point2D(
            boundary.min_x + ix * grid_size,
            boundary.min_y + iy * grid_size,
        )

    def _make_auto_boundary(
        self,
        start: Point2D,
        goal: Point2D,
        obstacles: Sequence[Obstacle],
        grid_size: float,
        clearance: float,
    ) -> BoundingBox2D:
        xs = [start.x, goal.x]
        ys = [start.y, goal.y]

        for obs in obstacles:
            box = obs.boundary.bbox.expanded(obs.clearance + clearance)
            xs.extend([box.min_x, box.max_x])
            ys.extend([box.min_y, box.max_y])

        margin = max(grid_size * 4.0, 10.0)
        return BoundingBox2D(
            min(xs) - margin,
            min(ys) - margin,
            max(xs) + margin,
            max(ys) + margin,
        )

    # =========================================================================
    # POST PROCESS / ALTERNATIVES / UTILS
    # =========================================================================

    def _simplify_path_points(
        self,
        points: Sequence[Point2D],
        prefer_axis_aligned: bool = True,
    ) -> List[Point2D]:
        if len(points) <= 2:
            return list(points)

        simplified = list(points)
        simplified = self._simplify_collinear_points(simplified, orthogonal_only=prefer_axis_aligned)
        simplified = self._simplify_collinear_points(simplified, orthogonal_only=False)
        return simplified

    def _simplify_collinear_points(
        self,
        points: Sequence[Point2D],
        orthogonal_only: bool,
    ) -> List[Point2D]:
        if len(points) <= 2:
            return list(points)

        simplified: List[Point2D] = [points[0]]

        for i in range(1, len(points) - 1):
            a = simplified[-1]
            b = points[i]
            c = points[i + 1]

            if orthogonal_only:
                if self._is_collinear_orthogonal(a, b, c):
                    continue
            else:
                if self._is_nearly_collinear(a, b, c):
                    continue

            simplified.append(b)

        simplified.append(points[-1])
        return simplified

    def _is_collinear_orthogonal(self, a: Point2D, b: Point2D, c: Point2D) -> bool:
        same_x = abs(a.x - b.x) < 1e-9 and abs(b.x - c.x) < 1e-9
        same_y = abs(a.y - b.y) < 1e-9 and abs(b.y - c.y) < 1e-9
        return same_x or same_y

    def _is_nearly_collinear(self, a: Point2D, b: Point2D, c: Point2D) -> bool:
        abx = b.x - a.x
        aby = b.y - a.y
        bcx = c.x - b.x
        bcy = c.y - b.y
        cross = abs(abx * bcy - aby * bcx)
        scale = max(abs(abx) + abs(aby) + abs(bcx) + abs(bcy), 1.0)
        return cross <= 1e-9 * scale

    def _is_diagonal(self, move_dir: Tuple[int, int]) -> bool:
        return move_dir[0] != 0 and move_dir[1] != 0

    def _cuts_corner(
        self,
        current: Tuple[int, int],
        move_dir: Tuple[int, int],
        blocked: set[Tuple[int, int]],
    ) -> bool:
        dx, dy = move_dir
        if dx == 0 or dy == 0:
            return False
        adj1 = (current[0] + dx, current[1])
        adj2 = (current[0], current[1] + dy)
        return adj1 in blocked or adj2 in blocked

    def _polyline_to_obstacles(
        self,
        polyline: Polyline2D,
        width: float,
        name: str,
    ) -> List[Obstacle]:
        obstacles: List[Obstacle] = []
        from core.geometry_core import rect_obstacle

        for i in range(len(polyline.points) - 1):
            p1 = polyline.points[i]
            p2 = polyline.points[i + 1]

            min_x = min(p1.x, p2.x) - width / 2.0
            min_y = min(p1.y, p2.y) - width / 2.0
            max_x = max(p1.x, p2.x) + width / 2.0
            max_y = max(p1.y, p2.y) + width / 2.0

            obstacles.append(
                rect_obstacle(
                    min_x,
                    min_y,
                    max_x - min_x,
                    max_y - min_y,
                    kind="route_reserved",
                    name=f"{name}_seg_{i + 1}",
                    clearance=0.0,
                )
            )
        return obstacles

    def _corridors_touched(self, polyline: Polyline2D, corridors: Sequence[RouteCorridor]) -> List[str]:
        used: List[str] = []
        for corridor in corridors:
            for pt in polyline.points:
                if corridor.boundary.contains_point(pt, inclusive=True):
                    used.append(corridor.name)
                    break
        return list(dict.fromkeys(used))

    def _generate_alternatives(
        self,
        request: RoutingRequest,
        profile: RoutingSystemProfile,
        obstacles: Sequence[Obstacle],
        boundary: BoundingBox2D,
        blocked: set[Tuple[int, int]],
        start_cell: Tuple[int, int],
        goal_cell: Tuple[int, int],
        primary_polyline: Polyline2D,
    ) -> List[RoutingAlternative]:
        max_alts = max(1, int(request.max_alternatives))
        if max_alts <= 1:
            return []

        alts: List[RoutingAlternative] = []
        toggles = [
            {"prefer_axis_aligned": not profile.prefer_axis_aligned},
            {"allow_diagonal": not profile.allow_diagonal},
        ]

        rank = 2
        for t in toggles:
            if rank > max_alts:
                break
            alt_profile = RoutingSystemProfile(**profile.__dict__)
            for k, v in t.items():
                setattr(alt_profile, k, v)
            path_cells, visited_count, total_cost, breakdown = self._astar(
                request=request,
                profile=alt_profile,
                start=start_cell,
                goal=goal_cell,
                blocked=blocked,
                boundary=boundary,
                grid_size=request.grid_size,
            )
            if not path_cells:
                continue
            pts = [self._cell_center_to_point(cell, boundary, request.grid_size) for cell in path_cells]
            pts = self._simplify_path_points(pts, prefer_axis_aligned=alt_profile.prefer_axis_aligned)
            if pts:
                pts[0] = Point2D(request.start.x, request.start.y)
                pts[-1] = Point2D(request.goal.x, request.goal.y)
            poly = Polyline2D(points=pts, closed=False)
            if self._same_polyline(primary_polyline, poly):
                continue
            alts.append(
                RoutingAlternative(
                    rank=rank,
                    polyline=poly,
                    total_cost=round(total_cost, 3),
                    cost_breakdown=breakdown.to_dict(),
                    message=f"Alternative route using allow_diagonal={alt_profile.allow_diagonal}, prefer_axis_aligned={alt_profile.prefer_axis_aligned}",
                )
            )
            rank += 1

        return alts

    def _same_polyline(self, a: Polyline2D, b: Polyline2D) -> bool:
        if len(a.points) != len(b.points):
            return False
        for p1, p2 in zip(a.points, b.points):
            if hypot(p1.x - p2.x, p1.y - p2.y) > 1e-6:
                return False
        return True


def _segments_intersect(a1: Tuple[float, float], a2: Tuple[float, float], b1: Tuple[float, float], b2: Tuple[float, float]) -> bool:
    """
    Return True if segments a1-a2 and b1-b2 intersect (including collinear overlap).
    Uses orientation tests with a small EPS tolerance.
    """
    def orient(p: Tuple[float, float], q: Tuple[float, float], r: Tuple[float, float]) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def on_segment(p: Tuple[float, float], q: Tuple[float, float], r: Tuple[float, float]) -> bool:
        return (
            min(p[0], r[0]) - EPS <= q[0] <= max(p[0], r[0]) + EPS
            and min(p[1], r[1]) - EPS <= q[1] <= max(p[1], r[1]) + EPS
        )

    o1 = orient(a1, a2, b1)
    o2 = orient(a1, a2, b2)
    o3 = orient(b1, b2, a1)
    o4 = orient(b1, b2, a2)

    # Collinear cases
    if abs(o1) < EPS and on_segment(a1, b1, a2):
        return True
    if abs(o2) < EPS and on_segment(a1, b2, a2):
        return True
    if abs(o3) < EPS and on_segment(b1, a1, b2):
        return True
    if abs(o4) < EPS and on_segment(b1, a2, b2):
        return True

    # Proper intersection
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


def _point_to_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """
    Return the shortest distance from point (px,py) to the segment (x1,y1)-(x2,y2).
    """
    vx = x2 - x1
    vy = y2 - y1
    wx = px - x1
    wy = py - y1

    proj = vx * wx + vy * wy
    if proj <= 0:
        return hypot(px - x1, py - y1)

    seg_len2 = vx * vx + vy * vy
    if proj >= seg_len2:
        return hypot(px - x2, py - y2)

    t = proj / seg_len2
    projx = x1 + t * vx
    projy = y1 + t * vy
    return hypot(px - projx, py - projy)


def route_path(
    start: Point2D,
    goal: Point2D,
    obstacles: Sequence[Obstacle] | None = None,
    grid_size: float = 5.0,
    clearance: float = 0.0,
    boundary: Optional[BoundingBox2D] = None,
    allow_diagonal: bool = False,
    kind: str = "generic",
    name: Optional[str] = None,
) -> RoutingResult:
    engine = RoutingEngine()
    request = RoutingRequest(
        start=start,
        goal=goal,
        grid_size=grid_size,
        clearance=clearance,
        boundary=boundary,
        allow_diagonal=allow_diagonal,
        kind=kind,
        system_type=kind,
        name=name,
    )
    return engine.route(request, obstacles=obstacles)
