from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from core.geometry_core import (
    BaseEntity,
    BoundingBox2D,
    Edge,
    EntityType,
    IssueSeverity,
    LineEntity,
    NetworkGraph,
    Obstacle,
    Point2D,
    Polyline2D,
    PolylineEntity,
    ProjectModel,
    ReviewIssue,
    TextEntity,
)


@dataclass
class ReviewRuleConfig:
    min_text_height: float = 0.5
    required_layers: List[str] = field(default_factory=list)
    max_unlabeled_linear_fraction: float = 0.35
    detect_entity_overlaps: bool = True
    detect_obstacle_collisions: bool = True
    detect_disconnected_graph_nodes: bool = True
    detect_short_segments: bool = True
    short_segment_threshold: float = 0.25
    require_text_for_layers: Dict[str, str] = field(default_factory=dict)
    route_layers: List[str] = field(default_factory=lambda: ["PIPE", "ROUTE", "UTILITY", "WATER", "SAN", "STORM"])


@dataclass
class ReviewSummary:
    issue_count: int
    error_count: int
    warning_count: int
    info_count: int
    issues: List[ReviewIssue]


class PlanReviewEngine:
    """
    General QA/review engine for early-stage engineering CAD output.

    It checks for:
    - missing required layers
    - disconnected graph nodes
    - short/suspicious segments
    - route collisions with obstacles
    - missing labels on route-heavy layers
    - overlapping entity bounding boxes
    - tiny/unreadable text
    """

    def review_project(
        self,
        project: ProjectModel,
        config: Optional[ReviewRuleConfig] = None,
        persist_to_project: bool = True,
    ) -> ReviewSummary:
        cfg = config or ReviewRuleConfig()
        issues: List[ReviewIssue] = []

        issues.extend(self._check_required_layers(project, cfg))
        issues.extend(self._check_text_entities(project, cfg))
        issues.extend(self._check_graph_connectivity(project, cfg))
        issues.extend(self._check_short_linear_entities(project, cfg))
        issues.extend(self._check_obstacle_collisions(project, cfg))
        issues.extend(self._check_layer_label_coverage(project, cfg))

        if cfg.detect_entity_overlaps:
            issues.extend(self._check_entity_bbox_overlaps(project))

        if persist_to_project:
            project.review_issues.extend(issues)

        return ReviewSummary(
            issue_count=len(issues),
            error_count=sum(1 for i in issues if i.severity == IssueSeverity.ERROR),
            warning_count=sum(1 for i in issues if i.severity == IssueSeverity.WARNING),
            info_count=sum(1 for i in issues if i.severity == IssueSeverity.INFO),
            issues=issues,
        )

    def _check_required_layers(
        self,
        project: ProjectModel,
        cfg: ReviewRuleConfig,
    ) -> List[ReviewIssue]:
        issues: List[ReviewIssue] = []
        if not cfg.required_layers:
            return issues

        existing_layers = {entity.style.layer for entity in project.drawing_entities}
        for layer in cfg.required_layers:
            if layer not in existing_layers:
                issues.append(
                    ReviewIssue(
                        severity=IssueSeverity.WARNING,
                        message=f"Required layer '{layer}' is missing.",
                        rule_name="required_layers",
                    )
                )
        return issues

    def _check_text_entities(
        self,
        project: ProjectModel,
        cfg: ReviewRuleConfig,
    ) -> List[ReviewIssue]:
        issues: List[ReviewIssue] = []

        for entity in project.drawing_entities:
            if isinstance(entity, TextEntity):
                if entity.height < cfg.min_text_height:
                    issues.append(
                        ReviewIssue(
                            severity=IssueSeverity.WARNING,
                            message=f"Text '{entity.text}' is smaller than minimum readable height.",
                            object_id=entity.id,
                            location=entity.insertion,
                            rule_name="text_height",
                            meta={"height": entity.height, "min_height": cfg.min_text_height},
                        )
                    )

        return issues

    def _check_graph_connectivity(
        self,
        project: ProjectModel,
        cfg: ReviewRuleConfig,
    ) -> List[ReviewIssue]:
        if not cfg.detect_disconnected_graph_nodes:
            return []

        issues: List[ReviewIssue] = []

        for graph in project.graphs.values():
            if not graph.nodes:
                issues.append(
                    ReviewIssue(
                        severity=IssueSeverity.WARNING,
                        message=f"Graph '{graph.name or graph.id}' has no nodes.",
                        object_id=graph.id,
                        rule_name="graph_empty",
                    )
                )
                continue

            adjacency = {node_id: set() for node_id in graph.nodes.keys()}
            for edge in graph.edges.values():
                adjacency[edge.start_node_id].add(edge.end_node_id)
                adjacency[edge.end_node_id].add(edge.start_node_id)

            disconnected = [node_id for node_id, neighbors in adjacency.items() if not neighbors]
            for node_id in disconnected:
                node = graph.nodes[node_id]
                issues.append(
                    ReviewIssue(
                        severity=IssueSeverity.ERROR,
                        message=f"Disconnected node found in graph '{graph.name or graph.id}'.",
                        object_id=node.id,
                        location=node.point.as_2d(),
                        rule_name="graph_disconnected_node",
                        meta={"graph_id": graph.id, "node_kind": node.kind},
                    )
                )

            if graph.nodes and graph.edges:
                comps = self._connected_components(graph)
                if len(comps) > 1:
                    issues.append(
                        ReviewIssue(
                            severity=IssueSeverity.WARNING,
                            message=f"Graph '{graph.name or graph.id}' has {len(comps)} disconnected components.",
                            object_id=graph.id,
                            rule_name="graph_multiple_components",
                            meta={"component_count": len(comps)},
                        )
                    )

        return issues

    def _check_short_linear_entities(
        self,
        project: ProjectModel,
        cfg: ReviewRuleConfig,
    ) -> List[ReviewIssue]:
        if not cfg.detect_short_segments:
            return []

        issues: List[ReviewIssue] = []

        for entity in project.drawing_entities:
            length = self._entity_length(entity)
            if length is None:
                continue

            if length < cfg.short_segment_threshold:
                bbox = entity.bbox()
                issues.append(
                    ReviewIssue(
                        severity=IssueSeverity.INFO,
                        message="Very short linear entity detected; may be accidental fragment.",
                        object_id=entity.id,
                        location=bbox.center if bbox else None,
                        rule_name="short_segment",
                        meta={"length": length, "threshold": cfg.short_segment_threshold},
                    )
                )

        for graph in project.graphs.values():
            for edge in graph.edges.values():
                length = edge.inferred_length(graph.nodes)
                if length < cfg.short_segment_threshold:
                    mid = self._edge_midpoint(edge, graph)
                    issues.append(
                        ReviewIssue(
                            severity=IssueSeverity.INFO,
                            message=f"Very short graph edge found in '{graph.name or graph.id}'.",
                            object_id=edge.id,
                            location=mid,
                            rule_name="short_graph_edge",
                            meta={"length": length, "threshold": cfg.short_segment_threshold},
                        )
                    )

        return issues

    def _check_obstacle_collisions(
        self,
        project: ProjectModel,
        cfg: ReviewRuleConfig,
    ) -> List[ReviewIssue]:
        if not cfg.detect_obstacle_collisions:
            return []

        issues: List[ReviewIssue] = []
        obstacles = list(project.obstacles.values())

        if not obstacles:
            return issues

        linear_entities = [
            e for e in project.drawing_entities
            if e.entity_type in {EntityType.LINE, EntityType.POLYLINE}
        ]

        for entity in linear_entities:
            bbox = entity.bbox()
            if bbox is None:
                continue

            for obstacle in obstacles:
                obox = obstacle.effective_boundary
                if bbox.intersects(obox):
                    issues.append(
                        ReviewIssue(
                            severity=IssueSeverity.WARNING,
                            message=f"Entity intersects obstacle '{obstacle.name or obstacle.id}'.",
                            object_id=entity.id,
                            location=bbox.center,
                            rule_name="entity_obstacle_collision",
                            meta={"obstacle_id": obstacle.id, "entity_layer": entity.style.layer},
                        )
                    )

        for graph in project.graphs.values():
            for edge in graph.edges.values():
                ebbox = self._edge_bbox(edge, graph)
                if ebbox is None:
                    continue

                for obstacle in obstacles:
                    obox = obstacle.effective_boundary
                    if ebbox.intersects(obox):
                        issues.append(
                            ReviewIssue(
                                severity=IssueSeverity.WARNING,
                                message=f"Graph edge intersects obstacle '{obstacle.name or obstacle.id}'.",
                                object_id=edge.id,
                                location=ebbox.center,
                                rule_name="graph_edge_obstacle_collision",
                                meta={"graph_id": graph.id, "obstacle_id": obstacle.id},
                            )
                        )

        return issues

    def _check_layer_label_coverage(
        self,
        project: ProjectModel,
        cfg: ReviewRuleConfig,
    ) -> List[ReviewIssue]:
        issues: List[ReviewIssue] = []

        layer_to_linear_count: Dict[str, int] = {}
        layer_to_text_count: Dict[str, int] = {}

        for entity in project.drawing_entities:
            layer = entity.style.layer
            if entity.entity_type in {EntityType.LINE, EntityType.POLYLINE}:
                layer_to_linear_count[layer] = layer_to_linear_count.get(layer, 0) + 1
            elif entity.entity_type == EntityType.TEXT:
                layer_to_text_count[layer] = layer_to_text_count.get(layer, 0) + 1

        relevant_layers = set(cfg.route_layers) | set(cfg.require_text_for_layers.keys())

        for layer in relevant_layers:
            linear_count = layer_to_linear_count.get(layer, 0)
            if linear_count == 0:
                continue

            text_count = layer_to_text_count.get(layer, 0)

            if layer in cfg.require_text_for_layers and text_count == 0:
                issues.append(
                    ReviewIssue(
                        severity=IssueSeverity.WARNING,
                        message=f"Layer '{layer}' requires text/labels but none were found.",
                        rule_name="missing_layer_labels",
                        meta={"layer": layer},
                    )
                )
                continue

            unlabeled_fraction = 1.0 if linear_count > 0 and text_count == 0 else max(0.0, 1.0 - (text_count / max(1, linear_count)))
            if unlabeled_fraction > cfg.max_unlabeled_linear_fraction:
                issues.append(
                    ReviewIssue(
                        severity=IssueSeverity.INFO,
                        message=f"Layer '{layer}' appears lightly labeled relative to route count.",
                        rule_name="light_label_coverage",
                        meta={
                            "layer": layer,
                            "linear_count": linear_count,
                            "text_count": text_count,
                            "unlabeled_fraction": round(unlabeled_fraction, 3),
                        },
                    )
                )

        return issues

    def _check_entity_bbox_overlaps(
        self,
        project: ProjectModel,
    ) -> List[ReviewIssue]:
        issues: List[ReviewIssue] = []
        entities = [e for e in project.drawing_entities if e.bbox() is not None]

        for i in range(len(entities)):
            e1 = entities[i]
            b1 = e1.bbox()
            if b1 is None:
                continue

            for j in range(i + 1, len(entities)):
                e2 = entities[j]
                if e1.style.layer != e2.style.layer:
                    continue

                b2 = e2.bbox()
                if b2 is None:
                    continue

                if not b1.intersects(b2):
                    continue

                if self._likely_safe_overlap(e1, e2):
                    continue

                issues.append(
                    ReviewIssue(
                        severity=IssueSeverity.INFO,
                        message=f"Possible overlapping entities on layer '{e1.style.layer}'.",
                        object_id=e1.id,
                        location=b1.center,
                        rule_name="bbox_overlap",
                        meta={"other_entity_id": e2.id, "layer": e1.style.layer},
                    )
                )

        return issues

    def _connected_components(
        self,
        graph: NetworkGraph,
    ) -> List[List[str]]:
        remaining = set(graph.nodes.keys())
        comps: List[List[str]] = []

        adjacency = {node_id: set() for node_id in graph.nodes.keys()}
        for edge in graph.edges.values():
            adjacency[edge.start_node_id].add(edge.end_node_id)
            adjacency[edge.end_node_id].add(edge.start_node_id)

        while remaining:
            start = next(iter(remaining))
            stack = [start]
            comp: List[str] = []

            while stack:
                node_id = stack.pop()
                if node_id not in remaining:
                    continue
                remaining.remove(node_id)
                comp.append(node_id)
                stack.extend(adjacency[node_id])

            comps.append(comp)

        return comps

    def _entity_length(
        self,
        entity: BaseEntity,
    ) -> Optional[float]:
        if isinstance(entity, LineEntity):
            return entity.segment.length
        if isinstance(entity, PolylineEntity):
            return entity.polyline.length
        return None

    def _edge_bbox(
        self,
        edge: Edge,
        graph: NetworkGraph,
    ) -> Optional[BoundingBox2D]:
        if edge.geometry is not None:
            return edge.geometry.bbox

        start = graph.nodes.get(edge.start_node_id)
        end = graph.nodes.get(edge.end_node_id)
        if not start or not end:
            return None

        min_x = min(start.point.x, end.point.x)
        min_y = min(start.point.y, end.point.y)
        max_x = max(start.point.x, end.point.x)
        max_y = max(start.point.y, end.point.y)
        return BoundingBox2D(min_x, min_y, max_x, max_y)

    def _edge_midpoint(
        self,
        edge: Edge,
        graph: NetworkGraph,
    ) -> Optional[Point2D]:
        if edge.geometry is not None and len(edge.geometry.points) >= 2:
            pts = edge.geometry.points
            return pts[len(pts) // 2]

        start = graph.nodes.get(edge.start_node_id)
        end = graph.nodes.get(edge.end_node_id)
        if not start or not end:
            return None

        return Point2D(
            (start.point.x + end.point.x) / 2.0,
            (start.point.y + end.point.y) / 2.0,
        )

    def _likely_safe_overlap(
        self,
        e1: BaseEntity,
        e2: BaseEntity,
    ) -> bool:
        if isinstance(e1, TextEntity) or isinstance(e2, TextEntity):
            return True
        if e1.entity_type == EntityType.POINT or e2.entity_type == EntityType.POINT:
            return True
        return False


def review_project(
    project: ProjectModel,
    config: Optional[ReviewRuleConfig] = None,
    persist_to_project: bool = True,
) -> ReviewSummary:
    return PlanReviewEngine().review_project(
        project=project,
        config=config,
        persist_to_project=persist_to_project,
    )