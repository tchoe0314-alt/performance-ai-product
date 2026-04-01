from __future__ import annotations

"""
engines/utility_engine.py (FULL CIVIL-GRADE TRUE MAX VERSION)
"""

from dataclasses import dataclass, field
import inspect
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.geometry_core import (
    EngineeringDomain,
    EngineeringObject,
    RoutingGraph,
    Node,
    Edge,
    Point2D,
    Point3D,
    Polyline2D,
    Obstacle,
    ProjectModel,
    TextEntity,
    StyleRef,
)
from core.geometry_core import rect_obstacle
from core.routing_engine import RoutingEngine, RoutingRequest
from review.plan_review_engine import review_project, ReviewRuleConfig


EPS = 1e-9


@dataclass
class UtilityNodeSpec:
    x: float
    y: float
    z: float = 0.0
    name: Optional[str] = None
    kind: str = "utility_node"
    demand: float = 0.0
    required: bool = True
    invert_elev_ft: Optional[float] = None
    rim_elev_ft: Optional[float] = None
    min_cover_ft: float = 3.0
    preferred_depth_ft: float = 4.0
    service_type: str = "service"
    zone_name: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_point2d(self) -> Point2D:
        return Point2D(self.x, self.y)

    def to_point3d(self) -> Point3D:
        return Point3D(self.x, self.y, self.z)


@dataclass
class UtilityRequest:
    system_type: str = "generic_utility"
    source: UtilityNodeSpec = field(default_factory=lambda: UtilityNodeSpec(0.0, 0.0, name="SOURCE", kind="source"))
    destinations: List[UtilityNodeSpec] = field(default_factory=list)
    grid_size: float = 5.0
    clearance: float = 0.0
    trunk_first: bool = True
    connect_sequentially: bool = False
    prefer_existing_routes: bool = True
    build_branches: bool = True
    build_services: bool = True
    add_labels: bool = True
    annotate_depths: bool = True
    annotate_diameters: bool = True
    label_prefix: Optional[str] = None
    layer_name: str = "UTILITY"
    graph_name: Optional[str] = None
    level: Optional[str] = None
    auto_add_to_project: bool = True
    review_after_generation: bool = True
    min_cover_ft: float = 3.0
    preferred_depth_ft: float = 4.0
    default_diameter_in: float = 8.0
    min_horizontal_separation_ft: float = 3.0
    min_vertical_separation_ft: float = 1.0
    generate_service_structures: bool = True
    generate_junctions: bool = True
    generate_mainline_objects: bool = True
    routing_system_type: Optional[str] = None
    pressure_class: str = "concept"
    min_pipe_slope: float = 0.004
    max_pipe_slope: float = 0.15
    use_gravity_defaults: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UtilitySystemProfile:
    system_type: str
    routing_system_type: str
    edge_kind: str
    layer_name: str
    default_diameter_in: float
    default_depth_ft: float
    min_cover_ft: float
    is_gravity: bool
    use_trunk_first: bool
    min_slope: float = 0.0
    max_slope: Optional[float] = None
    pressure_class: str = "concept"


@dataclass
class UtilitySegmentRecord:
    name: str
    segment_role: str
    system_type: str
    start_name: str
    end_name: str
    length_ft: float
    route_points: List[Tuple[float, float]]
    cover_start_ft: float
    cover_end_ft: float
    depth_start_ft: float
    depth_end_ft: float
    start_invert_ft: Optional[float]
    end_invert_ft: Optional[float]
    diameter_in: float
    demand: float
    slope_ft_ft: Optional[float]
    hydraulic_mode: str
    warnings: List[str] = field(default_factory=list)


@dataclass
class UtilityResult:
    success: bool
    message: str = ""
    graph_id: Optional[str] = None
    node_ids: List[str] = field(default_factory=list)
    edge_ids: List[str] = field(default_factory=list)
    object_ids: List[str] = field(default_factory=list)
    label_entity_ids: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    route_count: int = 0
    total_length: float = 0.0
    segment_records: List[UtilitySegmentRecord] = field(default_factory=list)
    explain: Dict[str, Any] = field(default_factory=dict)
    optimize_hooks: Dict[str, Any] = field(default_factory=dict)
    conflict_hooks: Dict[str, Any] = field(default_factory=dict)


class UtilityEngine:
    DEFAULT_LAYER_MAP: Dict[str, str] = {
        "domestic_water": "WATER",
        "cold_water": "WATER",
        "hot_water": "WATER",
        "water": "WATER",
        "fire_water": "WATER",
        "reclaimed_water": "WATER",
        "sanitary": "SAN",
        "storm": "STORM",
        "drainage": "DRAIN",
        "utility": "UTILITY",
        "generic_utility": "UTILITY",
        "power": "UTILITY",
    }

    DEFAULT_EDGE_KIND_MAP: Dict[str, str] = {
        "domestic_water": "water_run",
        "cold_water": "water_run",
        "hot_water": "water_run",
        "water": "water_run",
        "fire_water": "fire_water_run",
        "reclaimed_water": "reclaimed_water_run",
        "sanitary": "sanitary_run",
        "storm": "storm_run",
        "drainage": "drainage_run",
        "utility": "utility_run",
        "generic_utility": "utility_run",
        "power": "utility_run",
    }

    DEFAULT_DIAMETER_MAP: Dict[str, float] = {
        "domestic_water": 8.0,
        "cold_water": 6.0,
        "hot_water": 4.0,
        "water": 8.0,
        "fire_water": 10.0,
        "reclaimed_water": 8.0,
        "sanitary": 8.0,
        "storm": 12.0,
        "drainage": 12.0,
        "utility": 6.0,
        "generic_utility": 6.0,
        "power": 4.0,
    }

    DEFAULT_DEPTH_MAP: Dict[str, float] = {
        "domestic_water": 4.0,
        "cold_water": 4.0,
        "hot_water": 3.0,
        "water": 4.0,
        "fire_water": 4.5,
        "reclaimed_water": 4.0,
        "sanitary": 5.0,
        "storm": 4.0,
        "drainage": 4.0,
        "utility": 3.5,
        "generic_utility": 3.5,
        "power": 3.0,
    }

    GRAVITY_SYSTEMS = {"sanitary", "storm", "drainage"}
    _NODE_ACCEPTS_LEVEL = "level" in inspect.signature(Node).parameters
    _EDGE_ACCEPTS_KIND = "kind" in inspect.signature(Edge).parameters

    def __init__(
        self,
        *,
        router: Optional[RoutingEngine] = None,
        level: Optional[str] = None,
        default_level: Optional[str] = None,
        layer_name: Optional[str] = None,
        system_type: Optional[str] = None,
        graph_name: Optional[str] = None,
        min_cover_ft: Optional[float] = None,
        preferred_depth_ft: Optional[float] = None,
        default_diameter_in: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        self.router = router or RoutingEngine()
        self.compatibility_options: Dict[str, Any] = {
            "level": default_level or level,
            "layer_name": layer_name,
            "system_type": system_type,
            "graph_name": graph_name,
            "min_cover_ft": min_cover_ft,
            "preferred_depth_ft": preferred_depth_ft,
            "default_diameter_in": default_diameter_in,
        }
        if kwargs:
            self.compatibility_options["legacy_kwargs"] = dict(kwargs)

    def generate(self, project: ProjectModel, request: UtilityRequest, obstacles: Optional[Sequence[Obstacle]] = None) -> UtilityResult:
        if not request.destinations:
            return UtilityResult(False, message="No utility destinations were provided.")

        request = self._normalize_request(request)

        profile = self._resolve_profile(request)
        layer_name = profile.layer_name
        edge_kind = profile.edge_kind

        graph = RoutingGraph(
            name=request.graph_name or f"{request.system_type}_graph",
            kind=request.system_type,
            meta={"system_type": request.system_type, "layer_name": layer_name, **request.meta},
        )

        result = UtilityResult(success=True, message="Utility network generated.")

        source_node = self._make_node(
            point=request.source.to_point3d(),
            kind=request.source.kind,
            name=request.source.name or "SOURCE",
            level=request.level,
            meta={"role": "source", **request.source.meta},
        )
        graph.add_node(source_node)
        result.node_ids.append(source_node.id)

        route_obstacles = self._normalize_obstacles(obstacles if obstacles is not None else project.obstacles.values())
        destinations = self._ordered_destinations(request)
        trunk_node: Optional[Node] = None
        trunk_anchor_spec: Optional[UtilityNodeSpec] = None

        if request.trunk_first and len(destinations) > 1 and profile.use_trunk_first:
            tx, ty = self._compute_trunk_anchor(request, destinations)
            trunk_anchor_spec = UtilityNodeSpec(
                x=tx, y=ty, z=request.source.z, name=f"{request.system_type.upper()}_TRUNK",
                kind="junction", preferred_depth_ft=profile.default_depth_ft, min_cover_ft=profile.min_cover_ft,
                meta={"role": "trunk_anchor"},
            )
            trunk_node = self._make_node(
                point=trunk_anchor_spec.to_point3d(),
                kind="junction",
                name=trunk_anchor_spec.name,
                level=request.level,
                meta={"role": "trunk_anchor"},
            )
            graph.add_node(trunk_node)
            result.node_ids.append(trunk_node.id)

            trunk_route = self._route_between(
                request=request, profile=profile, start_point=request.source.to_point2d(),
                goal_point=trunk_anchor_spec.to_point2d(), layer_name=layer_name, edge_kind=edge_kind,
                route_name=f"{request.system_type}_TRUNK", obstacles=route_obstacles,
                destination_name=trunk_anchor_spec.name,
            )

            if trunk_route["success"] and trunk_route["polyline"] is not None:
                trunk_edge = self._make_edge(
                    start_node_id=source_node.id,
                    end_node_id=trunk_node.id,
                    kind=edge_kind,
                    geometry=trunk_route["polyline"],
                    meta={"system_type": request.system_type, "layer_name": layer_name, "route_role": "trunk"},
                )
                graph.add_edge(trunk_edge)
                result.edge_ids.append(trunk_edge.id)
                result.route_count += 1
                result.total_length += trunk_route["polyline"].length

                result.segment_records.append(
                    self._make_segment_record(
                        name=f"{request.system_type}_TRUNK", segment_role="trunk", system_type=request.system_type,
                        start_spec=request.source, end_spec=trunk_anchor_spec, polyline=trunk_route["polyline"],
                        request=request, profile=profile, demand=sum(max(0.0, d.demand) for d in destinations),
                    )
                )

                route_obstacles.extend(
                    self.router._polyline_to_obstacles(
                        trunk_route["polyline"], width=max(request.grid_size * 0.5, 2.0),
                        name=trunk_anchor_spec.name or "TRUNK",
                    )
                )
            else:
                result.warnings.append("Failed to build trunk anchor route; falling back to source-direct routing.")
                trunk_node = None
                trunk_anchor_spec = None

        current_anchor_id = source_node.id
        current_anchor_spec = request.source

        for idx, dest in enumerate(destinations):
            dest_node = self._make_node(
                point=dest.to_point3d(),
                kind=dest.kind,
                name=dest.name or f"DST_{idx + 1}",
                level=request.level,
                meta={"role": "destination", "demand": dest.demand, **dest.meta},
            )
            graph.add_node(dest_node)
            result.node_ids.append(dest_node.id)

            if request.connect_sequentially:
                start_spec = current_anchor_spec
                start_node_id = current_anchor_id
            elif trunk_node is not None and trunk_anchor_spec is not None:
                start_spec = trunk_anchor_spec
                start_node_id = trunk_node.id
            else:
                start_spec = request.source
                start_node_id = source_node.id

            route_result = self._route_between(
                request=request, profile=profile, start_point=start_spec.to_point2d(),
                goal_point=dest.to_point2d(), layer_name=layer_name, edge_kind=edge_kind,
                route_name=f"{request.system_type}_{idx + 1}", obstacles=route_obstacles,
                destination_name=dest.name or dest_node.id,
            )

            if not route_result["success"] or route_result["polyline"] is None:
                msg = f"Failed to route to destination '{dest.name or dest_node.id}'."
                if dest.required:
                    return UtilityResult(False, message=msg, warnings=result.warnings + [route_result["message"]])
                result.warnings.append(msg)
                continue

            polyline = route_result["polyline"]

            edge = self._make_edge(
                start_node_id=start_node_id,
                end_node_id=dest_node.id,
                kind=edge_kind,
                geometry=polyline,
                meta={
                    "system_type": request.system_type,
                    "layer_name": layer_name,
                    "destination_name": dest.name,
                    "route_index": idx + 1,
                    "diameter_in": profile.default_diameter_in,
                },
            )
            graph.add_edge(edge)
            result.edge_ids.append(edge.id)
            result.route_count += 1
            result.total_length += polyline.length

            seg_role = "service" if request.build_services else "main"
            seg_record = self._make_segment_record(
                name=f"{request.system_type}_{idx + 1}", segment_role=seg_role, system_type=request.system_type,
                start_spec=start_spec, end_spec=dest, polyline=polyline, request=request, profile=profile,
                demand=max(0.0, dest.demand),
            )
            result.segment_records.append(seg_record)

            if request.connect_sequentially:
                current_anchor_id = dest_node.id
                current_anchor_spec = dest

            if request.prefer_existing_routes or request.trunk_first:
                route_obstacles.extend(
                    self.router._polyline_to_obstacles(
                        polyline, width=max(request.grid_size * 0.5, 2.0),
                        name=dest.name or f"route_{idx + 1}",
                    )
                )

            if request.add_labels:
                result.label_entity_ids.extend(
                    self._add_route_labels(
                        project=project, request=request, polyline=polyline, route_index=idx + 1,
                        dest_name=dest.name or dest_node.id, layer_name=layer_name, segment_record=seg_record,
                    )
                )

            if request.auto_add_to_project:
                result.object_ids.append(
                    self._add_destination_object(project=project, dest=dest, system_type=request.system_type, level=request.level)
                )

            if request.generate_service_structures and request.auto_add_to_project:
                result.object_ids.extend(self._add_service_structures(project, request, profile, dest, polyline))

        if request.auto_add_to_project:
            project.add_graph(graph)
            result.graph_id = graph.id

            source_obj = EngineeringObject(
                kind=f"{request.system_type}_source",
                anchor=request.source.to_point3d(),
                name=request.source.name or "SOURCE",
                level=request.level,
                tags=["utility", "source", request.system_type],
                properties={
                    "system_type": request.system_type,
                    "preferred_depth_ft": profile.default_depth_ft,
                    "default_diameter_in": profile.default_diameter_in,
                    **request.source.meta,
                },
                domain=EngineeringDomain.UTILITY,
            )
            project.add_object(source_obj)
            result.object_ids.append(source_obj.id)
        else:
            result.graph_id = graph.id

        result.total_length = round(result.total_length, 3)
        result.explain = self._build_explain(request, profile, result)
        result.optimize_hooks = self._build_optimize_hooks(request, profile, result)
        result.conflict_hooks = self._build_conflict_hooks(request, profile, result)

        if request.review_after_generation and request.auto_add_to_project:
            summary = review_project(
                project,
                ReviewRuleConfig(
                    required_layers=["ANNO"],
                    route_layers=[layer_name],
                    require_text_for_layers={layer_name: "Utility routes should be labeled"},
                    short_segment_threshold=max(0.25, request.grid_size * 0.15),
                ),
                persist_to_project=True,
            )
            if summary.warning_count > 0 or summary.error_count > 0:
                result.warnings.append(
                    f"Review found {summary.error_count} errors and {summary.warning_count} warnings."
                )

        return result

    def _make_node(
        self,
        *,
        point: Point3D,
        kind: str,
        name: Optional[str],
        level: Optional[str],
        meta: Dict[str, Any],
    ) -> Node:
        kwargs: Dict[str, Any] = {
            "point": point,
            "kind": kind,
            "name": name,
            "meta": dict(meta),
        }
        if self._NODE_ACCEPTS_LEVEL:
            kwargs["level"] = level
        return Node(**kwargs)

    def _make_edge(
        self,
        *,
        start_node_id: str,
        end_node_id: str,
        kind: str,
        geometry: Polyline2D,
        meta: Dict[str, Any],
    ) -> Edge:
        kwargs: Dict[str, Any] = {
            "start_node_id": start_node_id,
            "end_node_id": end_node_id,
            "geometry": geometry,
            "meta": dict(meta),
        }
        if self._EDGE_ACCEPTS_KIND:
            kwargs["kind"] = kind
        else:
            kwargs["meta"]["kind"] = kind
        return Edge(**kwargs)

    def _normalize_obstacles(self, obstacles: Sequence[Obstacle] | None) -> List[Obstacle]:
        normalized: List[Obstacle] = []
        for obstacle in list(obstacles or []):
            if hasattr(obstacle, "boundary"):
                normalized.append(obstacle)  # type: ignore[arg-type]
                continue
            if not isinstance(obstacle, dict):
                continue

            x = obstacle.get("x")
            y = obstacle.get("y")
            w = obstacle.get("w", obstacle.get("width"))
            h = obstacle.get("h", obstacle.get("height"))
            origin = obstacle.get("origin")

            if origin is not None and isinstance(origin, (list, tuple)) and len(origin) >= 2:
                x = origin[0]
                y = origin[1]

            try:
                if x is None or y is None or w is None or h is None:
                    continue
                normalized.append(
                    rect_obstacle(
                        float(x),
                        float(y),
                        float(w),
                        float(h),
                        kind=str(obstacle.get("kind") or obstacle.get("type") or "generic"),
                        name=obstacle.get("name"),
                        clearance=float(obstacle.get("clearance", 0.0) or 0.0),
                        level=obstacle.get("level"),
                        meta=dict(obstacle.get("meta") or {}),
                    )
                )
            except Exception:
                continue
        return normalized

    def _normalize_request(self, request: UtilityRequest) -> UtilityRequest:
        overrides = self.compatibility_options
        if not overrides:
            return request

        if not request.level and overrides.get("level"):
            request.level = overrides["level"]
        if overrides.get("layer_name") and not request.layer_name:
            request.layer_name = str(overrides["layer_name"])
        if overrides.get("system_type") and (not request.system_type or request.system_type == "generic_utility"):
            request.system_type = str(overrides["system_type"])
        if overrides.get("graph_name") and not request.graph_name:
            request.graph_name = str(overrides["graph_name"])
        if overrides.get("min_cover_ft") is not None and request.min_cover_ft == 3.0:
            request.min_cover_ft = float(overrides["min_cover_ft"])
        if overrides.get("preferred_depth_ft") is not None and request.preferred_depth_ft == 4.0:
            request.preferred_depth_ft = float(overrides["preferred_depth_ft"])
        if overrides.get("default_diameter_in") is not None and request.default_diameter_in == 8.0:
            request.default_diameter_in = float(overrides["default_diameter_in"])
        return request

    def _resolve_profile(self, request: UtilityRequest) -> UtilitySystemProfile:
        system = request.system_type
        layer = request.layer_name if request.layer_name != "UTILITY" else self.DEFAULT_LAYER_MAP.get(system, request.layer_name)
        edge_kind = self.DEFAULT_EDGE_KIND_MAP.get(system, "utility_run")
        is_gravity = system in self.GRAVITY_SYSTEMS
        depth = self.DEFAULT_DEPTH_MAP.get(system, request.preferred_depth_ft)
        diameter = self.DEFAULT_DIAMETER_MAP.get(system, request.default_diameter_in)

        return UtilitySystemProfile(
            system_type=system,
            routing_system_type=request.routing_system_type or self._routing_system_type_for_request(request),
            edge_kind=edge_kind,
            layer_name=layer,
            default_diameter_in=float(diameter),
            default_depth_ft=float(depth),
            min_cover_ft=max(request.min_cover_ft, 0.0),
            is_gravity=is_gravity,
            use_trunk_first=bool(request.trunk_first),
            min_slope=max(request.min_pipe_slope, 0.001) if is_gravity else 0.0,
            max_slope=request.max_pipe_slope if is_gravity else None,
            pressure_class=request.pressure_class,
        )

    def _ordered_destinations(self, request: UtilityRequest) -> List[UtilityNodeSpec]:
        if request.connect_sequentially:
            return list(request.destinations)
        src = request.source.to_point2d()
        return sorted(request.destinations, key=lambda d: src.distance_to(d.to_point2d()))

    def _routing_system_type_for_request(self, request: UtilityRequest) -> str:
        if request.system_type in {"sanitary", "storm", "drainage"}:
            return request.system_type
        if request.system_type in {"water", "domestic_water", "cold_water", "hot_water", "fire_water", "reclaimed_water"}:
            return "water"
        return "utility"

    def _compute_trunk_anchor(self, request: UtilityRequest, destinations: Sequence[UtilityNodeSpec]) -> Tuple[float, float]:
        sx = request.source.x
        sy = request.source.y
        dx = sum(d.x for d in destinations) / len(destinations)
        dy = sum(d.y for d in destinations) / len(destinations)
        return (sx * 0.4 + dx * 0.6, sy * 0.4 + dy * 0.6)

    def _route_between(
        self,
        request: UtilityRequest,
        profile: UtilitySystemProfile,
        start_point: Point2D,
        goal_point: Point2D,
        layer_name: str,
        edge_kind: str,
        route_name: str,
        obstacles: Sequence[Obstacle],
        destination_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        route_req = RoutingRequest(
            start=start_point,
            goal=goal_point,
            grid_size=request.grid_size,
            clearance=request.clearance,
            layer_name=layer_name,
            kind=edge_kind,
            name=route_name,
            level=request.level,
            system_type=profile.routing_system_type,
            prefer_existing_routes=request.prefer_existing_routes,
            meta={"system_type": request.system_type, "destination": destination_name},
        )
        route_result = self.router.route(route_req, obstacles=obstacles)
        return {
            "success": bool(route_result.success and route_result.polyline is not None),
            "message": route_result.message,
            "polyline": route_result.polyline,
            "cost_breakdown": dict(route_result.cost_breakdown),
            "reasoning": list(route_result.reasoning),
        }

    def _make_segment_record(
        self,
        name: str,
        segment_role: str,
        system_type: str,
        start_spec: UtilityNodeSpec,
        end_spec: UtilityNodeSpec,
        polyline: Polyline2D,
        request: UtilityRequest,
        profile: UtilitySystemProfile,
        demand: float,
    ) -> UtilitySegmentRecord:
        default_depth = profile.default_depth_ft
        cover_start = max(profile.min_cover_ft, start_spec.min_cover_ft)
        cover_end = max(profile.min_cover_ft, end_spec.min_cover_ft)
        depth_start = max(default_depth, start_spec.preferred_depth_ft)
        depth_end = max(default_depth, end_spec.preferred_depth_ft)

        warnings: List[str] = []
        slope_ft_ft: Optional[float] = None
        start_invert: Optional[float] = None
        end_invert: Optional[float] = None
        hydraulic_mode = "pressure"

        if profile.is_gravity:
            hydraulic_mode = "gravity"
            length_ft = max(polyline.length, EPS)

            if start_spec.invert_elev_ft is not None:
                start_invert = float(start_spec.invert_elev_ft)
            else:
                start_invert = start_spec.z - depth_start

            required_slope = max(profile.min_slope, request.min_pipe_slope)
            end_invert = start_invert - required_slope * length_ft
            slope_ft_ft = (start_invert - end_invert) / length_ft

            if slope_ft_ft < required_slope - 1e-6:
                warnings.append("Gravity segment slope is below minimum concept slope.")
            if profile.max_slope is not None and slope_ft_ft > profile.max_slope + 1e-6:
                warnings.append("Gravity segment slope exceeds maximum concept slope.")

            if system_type == "sanitary" and depth_start < 4.0:
                warnings.append("Sanitary segment depth may be shallow for gravity coordination.")
            if system_type in {"storm", "drainage"} and depth_start < 3.0:
                warnings.append("Storm/drainage segment depth may be shallow for structure tie-ins.")
        else:
            if system_type in {"water", "domestic_water", "fire_water"} and cover_start < 3.5:
                warnings.append("Water line cover may be shallow for freeze/constructability assumptions.")

        return UtilitySegmentRecord(
            name=name,
            segment_role=segment_role,
            system_type=system_type,
            start_name=start_spec.name or "START",
            end_name=end_spec.name or "END",
            length_ft=round(polyline.length, 3),
            route_points=[(p.x, p.y) for p in polyline.points],
            cover_start_ft=round(cover_start, 3),
            cover_end_ft=round(cover_end, 3),
            depth_start_ft=round(depth_start, 3),
            depth_end_ft=round(depth_end, 3),
            start_invert_ft=None if start_invert is None else round(start_invert, 3),
            end_invert_ft=None if end_invert is None else round(end_invert, 3),
            diameter_in=round(profile.default_diameter_in, 3),
            demand=float(demand),
            slope_ft_ft=None if slope_ft_ft is None else round(slope_ft_ft, 5),
            hydraulic_mode=hydraulic_mode,
            warnings=warnings,
        )

    def _add_destination_object(self, project: ProjectModel, dest: UtilityNodeSpec, system_type: str, level: Optional[str]) -> str:
        obj = EngineeringObject(
            kind=f"{system_type}_endpoint",
            anchor=dest.to_point3d(),
            name=dest.name or "ENDPOINT",
            level=level,
            tags=["utility", "endpoint", system_type],
            properties={"demand": dest.demand, **dest.meta},
            domain=EngineeringDomain.UTILITY,
        )
        project.add_object(obj)
        return obj.id

    def _add_service_structures(
        self,
        project: ProjectModel,
        request: UtilityRequest,
        profile: UtilitySystemProfile,
        dest: UtilityNodeSpec,
        polyline: Polyline2D,
    ) -> List[str]:
        ids: List[str] = []
        if len(polyline.points) < 2:
            return ids

        first = polyline.points[0]
        last = polyline.points[-1]

        labels = [("service_tie", first), ("service_connection", last)]
        if request.generate_junctions and len(polyline.points) >= 3:
            mid = polyline.points[len(polyline.points) // 2]
            labels.append(("utility_junction", mid))

        for label, pt in labels:
            obj = EngineeringObject(
                kind=f"{request.system_type}_{label}",
                anchor=Point3D(pt.x, pt.y, dest.z),
                name=f"{dest.name or 'SERVICE'}_{label.upper()}",
                level=request.level,
                tags=["utility", request.system_type, label],
                properties={
                    "system_type": request.system_type,
                    "pressure_class": profile.pressure_class,
                    "destination": dest.name,
                },
                domain=EngineeringDomain.UTILITY,
            )
            project.add_object(obj)
            ids.append(obj.id)

        return ids

    def _add_route_labels(
        self,
        project: ProjectModel,
        request: UtilityRequest,
        polyline: Polyline2D,
        route_index: int,
        dest_name: str,
        layer_name: str,
        segment_record: UtilitySegmentRecord,
    ) -> List[str]:
        if len(polyline.points) < 2:
            return []

        mid_idx = min(len(polyline.points) - 1, max(1, len(polyline.points) // 2))
        mid_pt = polyline.points[mid_idx]
        prefix = request.label_prefix or request.system_type.upper()

        parts = [f"{prefix}-{route_index}: {dest_name}"]
        parts.append(f"L={segment_record.length_ft:.1f}ft")
        if request.annotate_diameters:
            parts.append(f'DIA={segment_record.diameter_in:.0f}"')
        if request.annotate_depths:
            parts.append(f"D={segment_record.depth_end_ft:.1f}ft")
        if segment_record.slope_ft_ft is not None:
            parts.append(f"S={segment_record.slope_ft_ft:.4f}")

        label = TextEntity(
            text=" | ".join(parts),
            insertion=Point2D(mid_pt.x, mid_pt.y),
            height=max(1.0, request.grid_size * 0.35),
            style=StyleRef(layer="ANNO"),
            meta={"source": "utility_engine", "route_layer": layer_name},
        )
        project.add_entity(label)
        return [label.id]

    def _build_explain(self, request: UtilityRequest, profile: UtilitySystemProfile, result: UtilityResult) -> Dict[str, Any]:
        return {
            "system_type": request.system_type,
            "route_count": result.route_count,
            "routing_system_type": profile.routing_system_type,
            "gravity_system": profile.is_gravity,
            "key_logic": [
                "Utility destinations were ordered from the source unless sequential routing was requested.",
                "RoutingEngine generated obstacle-aware utility alignments.",
                "Trunk-first topology was used when enabled and beneficial.",
                "Segments were assigned concept depth, cover, diameter, and invert metadata.",
                "Service structures and route labels were created when enabled.",
            ],
            "segments": [
                {
                    "name": seg.name,
                    "segment_role": seg.segment_role,
                    "start_name": seg.start_name,
                    "end_name": seg.end_name,
                    "length_ft": seg.length_ft,
                    "diameter_in": seg.diameter_in,
                    "depth_start_ft": seg.depth_start_ft,
                    "depth_end_ft": seg.depth_end_ft,
                    "hydraulic_mode": seg.hydraulic_mode,
                    "warning_count": len(seg.warnings),
                }
                for seg in result.segment_records[:25]
            ],
        }

    def _build_optimize_hooks(self, request: UtilityRequest, profile: UtilitySystemProfile, result: UtilityResult) -> Dict[str, Any]:
        total_warning_penalty = sum(len(seg.warnings) for seg in result.segment_records) * 4.0
        gravity_penalty = sum(
            2.0 for seg in result.segment_records
            if seg.hydraulic_mode == "gravity" and seg.slope_ft_ft is not None and seg.slope_ft_ft < profile.min_slope + 1e-6
        )
        return {
            "penalties": {
                "length_penalty": round(result.total_length / 100.0, 3),
                "route_count_penalty": result.route_count * 1.5,
                "warning_penalty": total_warning_penalty,
                "gravity_penalty": gravity_penalty,
            },
            "candidate_improvements": [
                "reduce route length through stronger trunk sharing",
                "increase utility separation near buildings and roads",
                "deepen shallow segments where gravity or cover is weak",
                "group nearby service destinations under shared corridors",
            ],
        }

    def _build_conflict_hooks(self, request: UtilityRequest, profile: UtilitySystemProfile, result: UtilityResult) -> Dict[str, Any]:
        return {
            "utility_segments": [
                {
                    "name": seg.name,
                    "segment_role": seg.segment_role,
                    "system_type": seg.system_type,
                    "route_points": list(seg.route_points),
                    "cover_start_ft": seg.cover_start_ft,
                    "cover_end_ft": seg.cover_end_ft,
                    "depth_start_ft": seg.depth_start_ft,
                    "depth_end_ft": seg.depth_end_ft,
                    "start_invert_ft": seg.start_invert_ft,
                    "end_invert_ft": seg.end_invert_ft,
                    "diameter_in": seg.diameter_in,
                    "slope_ft_ft": seg.slope_ft_ft,
                    "hydraulic_mode": seg.hydraulic_mode,
                }
                for seg in result.segment_records
            ],
            "utility_system_type": request.system_type,
            "minimum_horizontal_separation_ft": request.min_horizontal_separation_ft,
            "minimum_vertical_separation_ft": request.min_vertical_separation_ft,
        }


def generate_utility_network(
    project: ProjectModel,
    request: UtilityRequest,
    obstacles: Optional[Sequence[Obstacle]] = None,
) -> UtilityResult:
    return UtilityEngine().generate(project, request, obstacles=obstacles)
