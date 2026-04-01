from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.geometry_core import (
    Alignment,
    EngineeringObject,
    Point2D,
    Point3D,
    Polygon2D,
    Polyline2D,
    ProjectModel,
    Zone,
    ZoneType,
)


@dataclass
class BridgeRequest:
    alignment_id: Optional[str] = None
    create_alignment_if_missing: bool = False
    fallback_points: List[Tuple[float, float]] = field(default_factory=list)

    deck_width: float = 36.0
    span_length: float = 120.0
    max_span_length: float = 150.0
    pier_width: float = 8.0
    abutment_width: float = 12.0

    create_bridge_zone: bool = True
    create_deck_object: bool = True
    create_abutments: bool = True
    create_piers: bool = True
    create_span_objects: bool = True

    bridge_name: str = "Bridge 1"
    level: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BridgeResult:
    success: bool
    message: str = ""
    alignment_id: Optional[str] = None
    zone_ids: List[str] = field(default_factory=list)
    object_ids: List[str] = field(default_factory=list)
    span_count: int = 0
    pier_count: int = 0
    warnings: List[str] = field(default_factory=list)


class BridgeEngine:
    def generate(
        self,
        project: ProjectModel,
        request: BridgeRequest,
    ) -> BridgeResult:
        alignment = self._resolve_alignment(project, request)
        if alignment is None:
            return BridgeResult(False, message="No valid alignment found for bridge generation.")

        pts = alignment.centerline.points
        if len(pts) < 2:
            return BridgeResult(False, message="Bridge alignment must contain at least 2 points.")

        total_length = alignment.length
        if total_length <= 0.0:
            return BridgeResult(False, message="Bridge alignment length must be greater than zero.")

        result = BridgeResult(
            success=True,
            message="Bridge layout generated.",
            alignment_id=alignment.id,
        )

        deck_polygon = self._offset_envelope_polygon(
            alignment.centerline,
            request.deck_width / 2.0,
            request.deck_width / 2.0,
        )
        if deck_polygon is None:
            return BridgeResult(False, message="Failed to generate bridge deck geometry.")

        if request.create_bridge_zone:
            bridge_zone = Zone(
                boundary=deck_polygon,
                zone_type=ZoneType.BRIDGE,
                name=request.bridge_name,
                level=request.level,
                tags=["bridge", "deck"],
                meta={"source": "bridge_engine", **request.meta},
            )
            project.add_zone(bridge_zone)
            result.zone_ids.append(bridge_zone.id)

        if request.create_deck_object:
            c = deck_polygon.centroid()
            deck_obj = EngineeringObject(
                kind="bridge_deck",
                anchor=Point3D(c.x, c.y, 0.0),
                name=f"{request.bridge_name} Deck",
                level=request.level,
                boundary=deck_polygon,
                tags=["bridge", "deck"],
                properties={
                    "alignment_id": alignment.id,
                    "deck_width": request.deck_width,
                    "deck_length": total_length,
                    "source": "bridge_engine",
                    **request.meta,
                },
            )
            project.add_object(deck_obj)
            result.object_ids.append(deck_obj.id)

        stations = self._make_span_stations(
            total_length=total_length,
            target_span=request.span_length,
            max_span=request.max_span_length,
        )
        result.span_count = max(0, len(stations) - 1)

        if request.create_abutments:
            start_pt = pts[0]
            end_pt = pts[-1]

            a1 = self._make_support_object(
                kind="abutment",
                name=f"{request.bridge_name} Abutment A1",
                center=start_pt,
                width=request.abutment_width,
                along_vector=self._segment_direction(pts[0], pts[1]),
                level=request.level,
                extra={
                    "station": 0.0,
                    "support_role": "start",
                    "source": "bridge_engine",
                    **request.meta,
                },
            )
            a2 = self._make_support_object(
                kind="abutment",
                name=f"{request.bridge_name} Abutment A2",
                center=end_pt,
                width=request.abutment_width,
                along_vector=self._segment_direction(pts[-2], pts[-1]),
                level=request.level,
                extra={
                    "station": total_length,
                    "support_role": "end",
                    "source": "bridge_engine",
                    **request.meta,
                },
            )
            project.add_object(a1)
            project.add_object(a2)
            result.object_ids.extend([a1.id, a2.id])

        if request.create_piers and len(stations) > 2:
            for idx, station in enumerate(stations[1:-1], start=1):
                pt = self._point_at_station(alignment.centerline, station)
                if pt is None:
                    result.warnings.append(f"Could not place pier at station {station:.2f}.")
                    continue

                dir_vec = self._direction_at_station(alignment.centerline, station)
                pier = self._make_support_object(
                    kind="pier",
                    name=f"{request.bridge_name} Pier P{idx}",
                    center=pt,
                    width=request.pier_width,
                    along_vector=dir_vec,
                    level=request.level,
                    extra={
                        "station": station,
                        "pier_index": idx,
                        "source": "bridge_engine",
                        **request.meta,
                    },
                )
                project.add_object(pier)
                result.object_ids.append(pier.id)
                result.pier_count += 1

        if request.create_span_objects:
            for i in range(len(stations) - 1):
                s0 = stations[i]
                s1 = stations[i + 1]
                mid_station = (s0 + s1) / 2.0
                mid_pt = self._point_at_station(alignment.centerline, mid_station)
                if mid_pt is None:
                    continue

                span_obj = EngineeringObject(
                    kind="bridge_span",
                    anchor=Point3D(mid_pt.x, mid_pt.y, 0.0),
                    name=f"{request.bridge_name} Span {i + 1}",
                    level=request.level,
                    tags=["bridge", "span"],
                    properties={
                        "span_index": i + 1,
                        "station_start": s0,
                        "station_end": s1,
                        "span_length": s1 - s0,
                        "deck_width": request.deck_width,
                        "source": "bridge_engine",
                        **request.meta,
                    },
                )
                project.add_object(span_obj)
                result.object_ids.append(span_obj.id)

        if request.span_length > request.max_span_length:
            result.warnings.append("Requested span_length exceeds max_span_length; spans were subdivided.")

        return result

    def _resolve_alignment(
        self,
        project: ProjectModel,
        request: BridgeRequest,
    ) -> Optional[Alignment]:
        if request.alignment_id:
            return project.alignments.get(request.alignment_id)

        if project.alignments:
            return next(iter(project.alignments.values()))

        if request.create_alignment_if_missing and len(request.fallback_points) >= 2:
            alignment = Alignment(
                centerline=Polyline2D(
                    [Point2D(x, y) for x, y in request.fallback_points],
                    closed=False,
                ),
                name=f"{request.bridge_name} CL",
                meta={"source": "bridge_engine", **request.meta},
            )
            project.add_alignment(alignment)
            return alignment

        return None

    def _make_span_stations(
        self,
        total_length: float,
        target_span: float,
        max_span: float,
    ) -> List[float]:
        if total_length <= 0.0:
            return [0.0]

        if target_span <= 0.0:
            target_span = max_span if max_span > 0 else total_length

        if max_span <= 0.0:
            max_span = target_span

        span_count = max(1, int(round(total_length / target_span)))
        while (total_length / span_count) > max_span:
            span_count += 1

        actual_span = total_length / span_count
        return [round(i * actual_span, 6) for i in range(span_count + 1)]

    def _make_support_object(
        self,
        kind: str,
        name: str,
        center: Point2D,
        width: float,
        along_vector: Tuple[float, float],
        level: Optional[str],
        extra: Dict[str, Any],
    ) -> EngineeringObject:
        return EngineeringObject(
            kind=kind,
            anchor=Point3D(center.x, center.y, 0.0),
            name=name,
            level=level,
            tags=["bridge", kind],
            properties={
                "width": width,
                "direction": along_vector,
                **extra,
            },
        )

    def _point_at_station(
        self,
        polyline: Polyline2D,
        station: float,
    ) -> Optional[Point2D]:
        if station < 0.0:
            return polyline.points[0]

        walked = 0.0
        for seg in polyline.segments:
            seg_len = seg.length
            if seg_len <= 1e-9:
                continue
            if walked + seg_len >= station:
                ratio = (station - walked) / seg_len
                x = seg.start.x + (seg.end.x - seg.start.x) * ratio
                y = seg.start.y + (seg.end.y - seg.start.y) * ratio
                return Point2D(x, y)
            walked += seg_len

        return polyline.points[-1] if polyline.points else None

    def _direction_at_station(
        self,
        polyline: Polyline2D,
        station: float,
    ) -> Tuple[float, float]:
        walked = 0.0
        for seg in polyline.segments:
            seg_len = seg.length
            if seg_len <= 1e-9:
                continue
            if walked + seg_len >= station:
                return self._segment_direction(seg.start, seg.end)
            walked += seg_len

        if len(polyline.points) >= 2:
            return self._segment_direction(polyline.points[-2], polyline.points[-1])
        return (1.0, 0.0)

    def _segment_direction(self, a: Point2D, b: Point2D) -> Tuple[float, float]:
        dx = b.x - a.x
        dy = b.y - a.y
        length = (dx * dx + dy * dy) ** 0.5
        if length <= 1e-9:
            return (1.0, 0.0)
        return (dx / length, dy / length)

    def _offset_envelope_polygon(
        self,
        polyline: Polyline2D,
        width_left: float,
        width_right: float,
    ) -> Optional[Polygon2D]:
        left_pts: List[Point2D] = []
        right_pts: List[Point2D] = []

        if len(polyline.points) < 2:
            return None

        for i, pt in enumerate(polyline.points):
            nx, ny = self._vertex_normal(polyline.points, i)
            left_pts.append(Point2D(pt.x + nx * width_left, pt.y + ny * width_left))
            right_pts.append(Point2D(pt.x - nx * width_right, pt.y - ny * width_right))

        poly_points = left_pts + list(reversed(right_pts))
        if len(poly_points) < 3:
            return None
        return Polygon2D(poly_points)

    def _vertex_normal(
        self,
        pts: Sequence[Point2D],
        i: int,
    ) -> Tuple[float, float]:
        if len(pts) < 2:
            return (0.0, 0.0)

        if i == 0:
            dx = pts[1].x - pts[0].x
            dy = pts[1].y - pts[0].y
        elif i == len(pts) - 1:
            dx = pts[-1].x - pts[-2].x
            dy = pts[-1].y - pts[-2].y
        else:
            dx1 = pts[i].x - pts[i - 1].x
            dy1 = pts[i].y - pts[i - 1].y
            dx2 = pts[i + 1].x - pts[i].x
            dy2 = pts[i + 1].y - pts[i].y
            dx = dx1 + dx2
            dy = dy1 + dy2

        length = (dx * dx + dy * dy) ** 0.5
        if length <= 1e-9:
            return (0.0, 0.0)

        return (-dy / length, dx / length)


def generate_bridge(
    project: ProjectModel,
    request: BridgeRequest,
) -> BridgeResult:
    return BridgeEngine().generate(project, request)