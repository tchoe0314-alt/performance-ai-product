from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.geometry_core import (
    Alignment,
    Corridor,
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
class CorridorTemplate:
    name: str = "Typical Road"
    lane_width: float = 12.0
    lane_count: int = 2
    median_width: float = 0.0
    shoulder_left: float = 2.0
    shoulder_right: float = 2.0
    sidewalk_left: float = 5.0
    sidewalk_right: float = 5.0
    parkway_left: float = 4.0
    parkway_right: float = 4.0
    bike_lane_left: float = 0.0
    bike_lane_right: float = 0.0

    @property
    def paved_width(self) -> float:
        return (
            self.lane_count * self.lane_width
            + self.median_width
            + self.shoulder_left
            + self.shoulder_right
            + self.bike_lane_left
            + self.bike_lane_right
        )

    @property
    def total_width(self) -> float:
        return (
            self.paved_width
            + self.parkway_left
            + self.parkway_right
            + self.sidewalk_left
            + self.sidewalk_right
        )

    @property
    def half_widths(self) -> Tuple[float, float]:
        total = self.total_width
        return total / 2.0, total / 2.0


@dataclass
class CorridorRequest:
    alignment_id: Optional[str] = None
    create_alignment_if_missing: bool = False
    fallback_points: List[Tuple[float, float]] = field(default_factory=list)

    template: CorridorTemplate = field(default_factory=CorridorTemplate)

    create_corridor_record: bool = True
    create_road_zone: bool = True
    create_pavement_zone: bool = True
    create_sidewalk_zones: bool = True
    create_parkway_zones: bool = True
    create_edge_objects: bool = True

    corridor_name: str = "Main Corridor"
    level: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CorridorResult:
    success: bool
    message: str = ""
    alignment_id: Optional[str] = None
    corridor_id: Optional[str] = None
    zone_ids: List[str] = field(default_factory=list)
    object_ids: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class RoadProfilePoint:
    station_ft: float
    elevation_ft: float
    grade: float = 0.0


@dataclass
class RoadCrossSectionPoint:
    offset_ft: float
    elevation_ft: float
    role: str


class CorridorEngine:
    def generate(
        self,
        project: ProjectModel,
        request: CorridorRequest,
    ) -> CorridorResult:
        alignment = self._resolve_alignment(project, request)
        if alignment is None:
            return CorridorResult(False, message="No valid alignment found for corridor generation.")

        if len(alignment.centerline.points) < 2:
            return CorridorResult(False, message="Alignment must contain at least 2 points.")

        result = CorridorResult(
            success=True,
            message="Corridor generated.",
            alignment_id=alignment.id,
        )

        left_half, right_half = request.template.half_widths

        if request.create_corridor_record:
            corridor = Corridor(
                alignment_id=alignment.id,
                width_left=left_half,
                width_right=right_half,
                name=request.corridor_name,
                meta={"source": "corridor_engine", **request.meta},
            )
            project.add_corridor(corridor)
            result.corridor_id = corridor.id

        road_outline = self._offset_envelope_polygon(
            alignment.centerline,
            left_half,
            right_half,
        )
        if road_outline is None:
            return CorridorResult(False, message="Failed to create corridor envelope geometry.")

        if request.create_road_zone:
            road_zone = Zone(
                boundary=road_outline,
                zone_type=ZoneType.CORRIDOR,
                name=request.corridor_name,
                level=request.level,
                tags=["corridor", "road_reserve"],
                meta={"source": "corridor_engine", **request.meta},
            )
            project.add_zone(road_zone)
            result.zone_ids.append(road_zone.id)

        paved_left = request.template.paved_width / 2.0
        paved_right = request.template.paved_width / 2.0
        pavement_outline = self._offset_envelope_polygon(
            alignment.centerline,
            paved_left,
            paved_right,
        )
        if request.create_pavement_zone and pavement_outline is not None:
            pave_zone = Zone(
                boundary=pavement_outline,
                zone_type=ZoneType.ROAD,
                name=f"{request.corridor_name} Pavement",
                level=request.level,
                tags=["corridor", "pavement"],
                meta={"source": "corridor_engine", **request.meta},
            )
            project.add_zone(pave_zone)
            result.zone_ids.append(pave_zone.id)

        if request.create_sidewalk_zones or request.create_parkway_zones:
            band_result = self._create_band_zones(project, alignment, request)
            result.zone_ids.extend(band_result["zone_ids"])
            result.warnings.extend(band_result["warnings"])

        if request.create_edge_objects:
            edge_objects = self._create_edge_objects(alignment, request)
            for obj in edge_objects:
                project.add_object(obj)
                result.object_ids.append(obj.id)

        return result

    def _resolve_alignment(
        self,
        project: ProjectModel,
        request: CorridorRequest,
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
                name=f"{request.corridor_name} CL",
                meta={"source": "corridor_engine", **request.meta},
            )
            project.add_alignment(alignment)
            return alignment

        return None

    def _create_band_zones(
        self,
        project: ProjectModel,
        alignment: Alignment,
        request: CorridorRequest,
    ) -> Dict[str, List[str]]:
        zone_ids: List[str] = []
        warnings: List[str] = []
        t = request.template

        paved_half = t.paved_width / 2.0
        left_cursor = paved_half
        right_cursor = paved_half

        if request.create_parkway_zones and t.parkway_left > 0:
            poly = self._single_side_band_polygon(
                alignment.centerline,
                left_inner=left_cursor,
                left_outer=left_cursor + t.parkway_left,
                side="left",
            )
            if poly:
                zone = Zone(
                    boundary=poly,
                    zone_type=ZoneType.CORRIDOR,
                    name=f"{request.corridor_name} Parkway Left",
                    level=request.level,
                    tags=["corridor", "parkway", "left"],
                    meta={"source": "corridor_engine"},
                )
                project.add_zone(zone)
                zone_ids.append(zone.id)
            else:
                warnings.append("Failed to create left parkway geometry.")
            left_cursor += t.parkway_left

        if request.create_parkway_zones and t.parkway_right > 0:
            poly = self._single_side_band_polygon(
                alignment.centerline,
                right_inner=right_cursor,
                right_outer=right_cursor + t.parkway_right,
                side="right",
            )
            if poly:
                zone = Zone(
                    boundary=poly,
                    zone_type=ZoneType.CORRIDOR,
                    name=f"{request.corridor_name} Parkway Right",
                    level=request.level,
                    tags=["corridor", "parkway", "right"],
                    meta={"source": "corridor_engine"},
                )
                project.add_zone(zone)
                zone_ids.append(zone.id)
            else:
                warnings.append("Failed to create right parkway geometry.")
            right_cursor += t.parkway_right

        if request.create_sidewalk_zones and t.sidewalk_left > 0:
            poly = self._single_side_band_polygon(
                alignment.centerline,
                left_inner=left_cursor,
                left_outer=left_cursor + t.sidewalk_left,
                side="left",
            )
            if poly:
                zone = Zone(
                    boundary=poly,
                    zone_type=ZoneType.CORRIDOR,
                    name=f"{request.corridor_name} Sidewalk Left",
                    level=request.level,
                    tags=["corridor", "sidewalk", "left"],
                    meta={"source": "corridor_engine"},
                )
                project.add_zone(zone)
                zone_ids.append(zone.id)
            else:
                warnings.append("Failed to create left sidewalk geometry.")

        if request.create_sidewalk_zones and t.sidewalk_right > 0:
            poly = self._single_side_band_polygon(
                alignment.centerline,
                right_inner=right_cursor,
                right_outer=right_cursor + t.sidewalk_right,
                side="right",
            )
            if poly:
                zone = Zone(
                    boundary=poly,
                    zone_type=ZoneType.CORRIDOR,
                    name=f"{request.corridor_name} Sidewalk Right",
                    level=request.level,
                    tags=["corridor", "sidewalk", "right"],
                    meta={"source": "corridor_engine"},
                )
                project.add_zone(zone)
                zone_ids.append(zone.id)
            else:
                warnings.append("Failed to create right sidewalk geometry.")

        return {"zone_ids": zone_ids, "warnings": warnings}

    def _create_edge_objects(
        self,
        alignment: Alignment,
        request: CorridorRequest,
    ) -> List[EngineeringObject]:
        objs: List[EngineeringObject] = []
        centerline = alignment.centerline
        start = centerline.points[0]
        end = centerline.points[-1]

        objs.append(
            EngineeringObject(
                kind="corridor_start",
                anchor=Point3D(start.x, start.y, 0.0),
                name=f"{request.corridor_name} Start",
                level=request.level,
                tags=["corridor", "control_point"],
                properties={"source": "corridor_engine"},
            )
        )
        objs.append(
            EngineeringObject(
                kind="corridor_end",
                anchor=Point3D(end.x, end.y, 0.0),
                name=f"{request.corridor_name} End",
                level=request.level,
                tags=["corridor", "control_point"],
                properties={"source": "corridor_engine"},
            )
        )

        for i, pt in enumerate(centerline.points):
            objs.append(
                EngineeringObject(
                    kind="corridor_pi",
                    anchor=Point3D(pt.x, pt.y, 0.0),
                    name=f"{request.corridor_name} PI-{i + 1}",
                    level=request.level,
                    tags=["corridor", "pi"],
                    properties={"source": "corridor_engine", "index": i},
                )
            )

        return objs

    def _offset_envelope_polygon(
        self,
        polyline: Polyline2D,
        width_left: float,
        width_right: float,
    ) -> Optional[Polygon2D]:
        if len(polyline.points) < 2:
            return None

        left_pts = self._offset_polyline(polyline.points, width_left)
        right_pts = self._offset_polyline(polyline.points, -width_right)

        if len(left_pts) < 2 or len(right_pts) < 2:
            return None

        polygon_points = left_pts + list(reversed(right_pts))
        if len(polygon_points) < 3:
            return None

        cleaned = self._dedupe_points(polygon_points)
        if len(cleaned) < 3:
            return None

        return Polygon2D(cleaned)

    def _single_side_band_polygon(
        self,
        polyline: Polyline2D,
        *,
        left_inner: float = 0.0,
        left_outer: float = 0.0,
        right_inner: float = 0.0,
        right_outer: float = 0.0,
        side: str,
    ) -> Optional[Polygon2D]:
        if side not in {"left", "right"}:
            return None
        if len(polyline.points) < 2:
            return None

        if side == "left":
            inner_pts = self._offset_polyline(polyline.points, left_inner)
            outer_pts = self._offset_polyline(polyline.points, left_outer)
        else:
            inner_pts = self._offset_polyline(polyline.points, -right_inner)
            outer_pts = self._offset_polyline(polyline.points, -right_outer)

        if len(inner_pts) < 2 or len(outer_pts) < 2:
            return None

        poly_points = inner_pts + list(reversed(outer_pts))
        cleaned = self._dedupe_points(poly_points)
        if len(cleaned) < 3:
            return None

        return Polygon2D(cleaned)

    def _offset_polyline(
        self,
        pts: Sequence[Point2D],
        offset: float,
    ) -> List[Point2D]:
        if len(pts) < 2:
            return []

        segments: List[Tuple[Point2D, Point2D]] = []
        for i in range(len(pts) - 1):
            p0 = pts[i]
            p1 = pts[i + 1]
            if self._dist(p0, p1) <= 1e-9:
                continue

            nx, ny = self._unit_left_normal(p0, p1)
            q0 = Point2D(p0.x + nx * offset, p0.y + ny * offset)
            q1 = Point2D(p1.x + nx * offset, p1.y + ny * offset)
            segments.append((q0, q1))

        if not segments:
            return []

        out: List[Point2D] = [segments[0][0]]

        for i in range(len(segments) - 1):
            a0, a1 = segments[i]
            b0, b1 = segments[i + 1]

            inter = self._line_intersection(a0, a1, b0, b1)
            if inter is None:
                out.append(a1)
            else:
                out.append(inter)

        out.append(segments[-1][1])
        return self._dedupe_points(out)

    def _unit_left_normal(self, a: Point2D, b: Point2D) -> Tuple[float, float]:
        dx = b.x - a.x
        dy = b.y - a.y
        length = (dx * dx + dy * dy) ** 0.5
        if length <= 1e-9:
            return (0.0, 0.0)
        return (-dy / length, dx / length)

    def _line_intersection(
        self,
        a1: Point2D,
        a2: Point2D,
        b1: Point2D,
        b2: Point2D,
    ) -> Optional[Point2D]:
        x1, y1 = a1.x, a1.y
        x2, y2 = a2.x, a2.y
        x3, y3 = b1.x, b1.y
        x4, y4 = b2.x, b2.y

        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) <= 1e-9:
            return None

        det1 = x1 * y2 - y1 * x2
        det2 = x3 * y4 - y3 * x4

        px = (det1 * (x3 - x4) - (x1 - x2) * det2) / denom
        py = (det1 * (y3 - y4) - (y1 - y2) * det2) / denom
        return Point2D(px, py)

    def _dist(self, a: Point2D, b: Point2D) -> float:
        dx = a.x - b.x
        dy = a.y - b.y
        return (dx * dx + dy * dy) ** 0.5

    def build_profile_from_points(self, points: Sequence[Point3D]) -> List[RoadProfilePoint]:
        if len(points) < 2:
            return []
        out: List[RoadProfilePoint] = []
        station = 0.0
        for idx, point in enumerate(points):
            if idx > 0:
                prev = points[idx - 1]
                station += math.hypot(point.x - prev.x, point.y - prev.y)
            grade = 0.0
            if idx > 0:
                prev_profile = out[-1]
                run = max(1e-9, station - prev_profile.station_ft)
                grade = (point.z - prev_profile.elevation_ft) / run
            out.append(RoadProfilePoint(round(station, 3), round(point.z, 3), round(grade, 5)))
        return out

    def build_crowned_section(
        self,
        *,
        lane_width: float = 12.0,
        lane_count: int = 2,
        crown_elev_ft: float = 100.0,
        cross_slope: float = 0.02,
        curb_reveal_ft: float = 0.5,
        sidewalk_width: float = 5.0,
        sidewalk_cross_slope: float = 0.015,
    ) -> List[RoadCrossSectionPoint]:
        half_pavement = max(1.0, lane_width * lane_count / 2.0)
        gutter_elev = crown_elev_ft - abs(cross_slope) * half_pavement
        sidewalk_outer_elev = gutter_elev + curb_reveal_ft + abs(sidewalk_cross_slope) * sidewalk_width
        return [
            RoadCrossSectionPoint(round(-half_pavement - sidewalk_width, 3), round(sidewalk_outer_elev, 3), "left_sidewalk_outer"),
            RoadCrossSectionPoint(round(-half_pavement, 3), round(gutter_elev + curb_reveal_ft, 3), "left_back_of_curb"),
            RoadCrossSectionPoint(0.0, round(crown_elev_ft, 3), "crown"),
            RoadCrossSectionPoint(round(half_pavement, 3), round(gutter_elev + curb_reveal_ft, 3), "right_back_of_curb"),
            RoadCrossSectionPoint(round(half_pavement + sidewalk_width, 3), round(sidewalk_outer_elev, 3), "right_sidewalk_outer"),
        ]

    def validate_profile_grades(
        self,
        profile: Sequence[RoadProfilePoint],
        *,
        min_grade: float = 0.003,
        max_grade: float = 0.08,
    ) -> Dict[str, Any]:
        rows: List[Dict[str, Any]] = []
        for index, point in enumerate(profile):
            if index == 0:
                continue
            grade = abs(point.grade)
            rows.append(
                {
                    "station_ft": point.station_ft,
                    "grade": point.grade,
                    "abs_grade": round(grade, 5),
                    "valid": min_grade <= grade <= max_grade,
                }
            )
        return {
            "valid": bool(rows) and all(row["valid"] for row in rows),
            "min_grade": round(min_grade, 5),
            "max_grade": round(max_grade, 5),
            "max_observed_grade": max((row["abs_grade"] for row in rows), default=0.0),
            "segments": rows,
            "source": "corridor_profile_grade_check",
            "truth_label": "Profile grade check computed from station/elevation samples.",
        }

    def validate_crowned_section(
        self,
        section: Sequence[RoadCrossSectionPoint],
        *,
        target_pavement_cross_slope: float = 0.02,
        max_sidewalk_cross_slope: float = 0.02,
        tolerance: float = 0.005,
    ) -> Dict[str, Any]:
        by_role = {point.role: point for point in section}
        crown = by_role.get("crown")
        left_curb = by_role.get("left_back_of_curb")
        right_curb = by_role.get("right_back_of_curb")
        left_walk = by_role.get("left_sidewalk_outer")
        right_walk = by_role.get("right_sidewalk_outer")

        checks: List[Dict[str, Any]] = []

        def add_check(name: str, a: Optional[RoadCrossSectionPoint], b: Optional[RoadCrossSectionPoint], limit: float, target: Optional[float] = None) -> None:
            if a is None or b is None:
                checks.append({"name": name, "valid": False, "missing": True})
                return
            run = abs(a.offset_ft - b.offset_ft)
            slope = abs(a.elevation_ft - b.elevation_ft) / max(run, 1e-9)
            if target is None:
                valid = slope <= limit
            else:
                valid = abs(slope - target) <= tolerance
            checks.append(
                {
                    "name": name,
                    "slope": round(slope, 5),
                    "target": round(target, 5) if target is not None else None,
                    "limit": round(limit, 5),
                    "valid": valid,
                }
            )

        add_check("left_pavement_cross_slope", crown, left_curb, target_pavement_cross_slope + tolerance, target_pavement_cross_slope)
        add_check("right_pavement_cross_slope", crown, right_curb, target_pavement_cross_slope + tolerance, target_pavement_cross_slope)
        add_check("left_sidewalk_cross_slope", left_curb, left_walk, max_sidewalk_cross_slope)
        add_check("right_sidewalk_cross_slope", right_curb, right_walk, max_sidewalk_cross_slope)
        return {
            "valid": bool(checks) and all(check.get("valid") is True for check in checks),
            "checks": checks,
            "source": "corridor_cross_section_slope_check",
            "truth_label": "Cross-section slopes computed from section offset/elevation points.",
        }

    def _dedupe_points(self, pts: Sequence[Point2D], tol: float = 1e-6) -> List[Point2D]:
        out: List[Point2D] = []
        for p in pts:
            if not out:
                out.append(p)
                continue
            if self._dist(out[-1], p) > tol:
                out.append(p)

        if len(out) > 1 and self._dist(out[0], out[-1]) <= tol:
            out.pop()

        return out


def generate_corridor(
    project: ProjectModel,
    request: CorridorRequest,
) -> CorridorResult:
    return CorridorEngine().generate(project, request)
