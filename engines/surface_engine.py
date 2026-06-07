# engines/surface_engine.py



from __future__ import annotations



import csv
import math

from dataclasses import dataclass, field

from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple





# =========================================================

# DATA CLASSES

# =========================================================



@dataclass

class SurveyPoint:

    x: float

    y: float

    z: float

    point_id: str = ""

    source: str = ""

    confidence: str = ""


@dataclass
class Breakline:
    points: List[Tuple[float, float, float]]
    breakline_id: str = ""
    source: str = ""


@dataclass
class TinTriangle:
    vertex_indices: Tuple[int, int, int]
    plane: Tuple[float, float, float]
    area: float
    confidence: str = ""


@dataclass
class TinSurface:
    points: List[SurveyPoint]
    triangles: List[TinTriangle]
    breaklines: List[Breakline] = field(default_factory=list)
    boundary: Optional[List[Tuple[float, float]]] = None
    source_type: str = "survey-unverified"
    control_verified: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def bounds(self) -> Tuple[float, float, float, float]:
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return min(xs), min(ys), max(xs), max(ys)

    def triangle_points(self, triangle: TinTriangle) -> Tuple[SurveyPoint, SurveyPoint, SurveyPoint]:
        a, b, c = triangle.vertex_indices
        return self.points[a], self.points[b], self.points[c]

    def elevation_at(self, x: float, y: float) -> Optional[float]:
        for triangle in self.triangles:
            p1, p2, p3 = self.triangle_points(triangle)
            if _point_in_triangle_2d(x, y, p1, p2, p3):
                a, b, c = triangle.plane
                return a * x + b * y + c
        return None

    def slope_at(self, x: float, y: float) -> Optional[Dict[str, float]]:
        for triangle in self.triangles:
            p1, p2, p3 = self.triangle_points(triangle)
            if _point_in_triangle_2d(x, y, p1, p2, p3):
                a, b, _ = triangle.plane
                mag = math.hypot(a, b)
                if mag <= 1e-12:
                    return {
                        "slope_x": a,
                        "slope_y": b,
                        "magnitude": 0.0,
                        "downhill_dx": 0.0,
                        "downhill_dy": 0.0,
                    }
                return {
                    "slope_x": a,
                    "slope_y": b,
                    "magnitude": mag,
                    "downhill_dx": -a / mag,
                    "downhill_dy": -b / mag,
                }
        return None

    def build_grid(self, *, cell_size: float = 10.0, padding: float = 0.0) -> "GridSurface":
        if cell_size <= 0:
            raise ValueError("cell_size must be > 0")
        x_min, y_min, x_max, y_max = self.bounds()
        x_min -= padding
        y_min -= padding
        x_max += padding
        y_max += padding
        ncols = int(round((x_max - x_min) / cell_size)) + 1
        nrows = int(round((y_max - y_min) / cell_size)) + 1
        values: List[List[float]] = []
        for row in range(nrows):
            y = y_min + row * cell_size
            row_values: List[float] = []
            for col in range(ncols):
                x = x_min + col * cell_size
                z = self.elevation_at(x, y)
                if z is None:
                    z = _idw_elevation(self.points, x, y)
                row_values.append(float(z))
            values.append(row_values)
        surface = GridSurface(
            x_min=x_min,
            y_min=y_min,
            x_max=x_min + (ncols - 1) * cell_size,
            y_max=y_min + (nrows - 1) * cell_size,
            cell_size=cell_size,
            ncols=ncols,
            nrows=nrows,
            values=values,
        )
        setattr(surface, "_tin_surface", self)
        return surface





@dataclass

class GridSurface:

    x_min: float

    y_min: float

    x_max: float

    y_max: float

    cell_size: float

    ncols: int

    nrows: int

    values: List[List[float]]



    # -----------------------------------------------------



    def x_at(self, col: int) -> float:

        return self.x_min + col * self.cell_size



    def y_at(self, row: int) -> float:

        return self.y_min + row * self.cell_size



    def elevation_at_index(self, row: int, col: int) -> float:

        return self.values[row][col]



    def iter_points(self) -> Iterator[Tuple[float, float, float]]:

        for row in range(self.nrows):

            y = self.y_at(row)

            for col in range(self.ncols):

                x = self.x_at(col)

                yield x, y, self.values[row][col]



    def bounds(self) -> Tuple[float, float, float, float]:

        return self.x_min, self.y_min, self.x_max, self.y_max

    def copy(self) -> "GridSurface":

        return GridSurface(
            x_min=self.x_min,
            y_min=self.y_min,
            x_max=self.x_max,
            y_max=self.y_max,
            cell_size=self.cell_size,
            ncols=self.ncols,
            nrows=self.nrows,
            values=[list(row) for row in self.values],
        )




# =========================================================
# TIN HELPERS
# =========================================================


def _triangle_area_xy(p1: SurveyPoint, p2: SurveyPoint, p3: SurveyPoint) -> float:
    return abs(((p2.x - p1.x) * (p3.y - p1.y) - (p3.x - p1.x) * (p2.y - p1.y)) / 2.0)


def _triangle_plane(p1: SurveyPoint, p2: SurveyPoint, p3: SurveyPoint) -> Tuple[float, float, float]:
    det = p1.x * (p2.y - p3.y) + p2.x * (p3.y - p1.y) + p3.x * (p1.y - p2.y)
    if abs(det) <= 1e-12:
        return 0.0, 0.0, (p1.z + p2.z + p3.z) / 3.0
    a = (p1.z * (p2.y - p3.y) + p2.z * (p3.y - p1.y) + p3.z * (p1.y - p2.y)) / det
    b = (p1.x * (p2.z - p3.z) + p2.x * (p3.z - p1.z) + p3.x * (p1.z - p2.z)) / det
    c = (
        p1.x * (p2.y * p3.z - p3.y * p2.z)
        + p2.x * (p3.y * p1.z - p1.y * p3.z)
        + p3.x * (p1.y * p2.z - p2.y * p1.z)
    ) / det
    return a, b, c


def _point_in_triangle_2d(x: float, y: float, p1: SurveyPoint, p2: SurveyPoint, p3: SurveyPoint) -> bool:
    denom = (p2.y - p3.y) * (p1.x - p3.x) + (p3.x - p2.x) * (p1.y - p3.y)
    if abs(denom) <= 1e-12:
        return False
    a = ((p2.y - p3.y) * (x - p3.x) + (p3.x - p2.x) * (y - p3.y)) / denom
    b = ((p3.y - p1.y) * (x - p3.x) + (p1.x - p3.x) * (y - p3.y)) / denom
    c = 1.0 - a - b
    eps = 1e-9
    return a >= -eps and b >= -eps and c >= -eps


def _point_in_polygon(point: Tuple[float, float], polygon: Sequence[Tuple[float, float]]) -> bool:
    if len(polygon) < 3:
        return True
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / max(yj - yi, 1e-12) + xi
        if intersects:
            inside = not inside
        j = i
    return inside


def _idw_elevation(
    points: Sequence[SurveyPoint],
    x: float,
    y: float,
    *,
    power: float = 2.0,
    neighbors: int = 8,
    max_radius: Optional[float] = None,
) -> float:
    dists: List[Tuple[float, float]] = []
    for pt in points:
        d = math.hypot(x - pt.x, y - pt.y)
        if d == 0:
            return pt.z
        if max_radius is not None and d > max_radius:
            continue
        dists.append((d, pt.z))
    if not dists:
        dists = [(max(math.hypot(x - pt.x, y - pt.y), 1e-9), pt.z) for pt in points]
    dists.sort(key=lambda item: item[0])
    weighted_sum = 0.0
    total_weight = 0.0
    for d, z in dists[: max(1, neighbors)]:
        w = 1.0 / (d**power)
        weighted_sum += z * w
        total_weight += w
    return weighted_sum / total_weight if total_weight else 0.0


def _circumcircle_contains(points: Sequence[SurveyPoint], triangle: Tuple[int, int, int], point: SurveyPoint) -> bool:
    p1, p2, p3 = (points[triangle[0]], points[triangle[1]], points[triangle[2]])
    ax = p1.x - point.x
    ay = p1.y - point.y
    bx = p2.x - point.x
    by = p2.y - point.y
    cx = p3.x - point.x
    cy = p3.y - point.y
    det = (
        (ax * ax + ay * ay) * (bx * cy - cx * by)
        - (bx * bx + by * by) * (ax * cy - cx * ay)
        + (cx * cx + cy * cy) * (ax * by - bx * ay)
    )
    orientation = (p2.x - p1.x) * (p3.y - p1.y) - (p3.x - p1.x) * (p2.y - p1.y)
    return det > 1e-9 if orientation > 0 else det < -1e-9


def _dedupe_points(points: Sequence[SurveyPoint]) -> List[SurveyPoint]:
    by_xy: Dict[Tuple[float, float], SurveyPoint] = {}
    for point in points:
        key = (round(point.x, 8), round(point.y, 8))
        by_xy[key] = point
    return list(by_xy.values())


def _densify_breaklines(breaklines: Sequence[Breakline], *, max_segment_length: float) -> List[SurveyPoint]:
    densified: List[SurveyPoint] = []
    if max_segment_length <= 0:
        return densified
    for breakline in breaklines:
        pts = list(breakline.points or [])
        for index in range(len(pts) - 1):
            x1, y1, z1 = pts[index]
            x2, y2, z2 = pts[index + 1]
            segment_length = math.hypot(x2 - x1, y2 - y1)
            steps = max(1, int(math.ceil(segment_length / max_segment_length)))
            for step in range(steps + 1):
                t = step / steps
                densified.append(
                    SurveyPoint(
                        x=x1 + (x2 - x1) * t,
                        y=y1 + (y2 - y1) * t,
                        z=z1 + (z2 - z1) * t,
                        point_id=f"{breakline.breakline_id or 'breakline'}-{index}-{step}",
                        source=breakline.source or "breakline",
                        confidence="breakline_control",
                    )
                )
    return densified


def _delaunay_triangles(points: Sequence[SurveyPoint]) -> List[Tuple[int, int, int]]:
    if len(points) < 3:
        return []
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    delta = max(max_x - min_x, max_y - min_y, 1.0)
    mid_x = (min_x + max_x) / 2.0
    mid_y = (min_y + max_y) / 2.0
    work_points = list(points) + [
        SurveyPoint(mid_x - 20.0 * delta, mid_y - delta, 0.0),
        SurveyPoint(mid_x, mid_y + 20.0 * delta, 0.0),
        SurveyPoint(mid_x + 20.0 * delta, mid_y - delta, 0.0),
    ]
    super_indices = {len(work_points) - 3, len(work_points) - 2, len(work_points) - 1}
    triangles: List[Tuple[int, int, int]] = [(len(work_points) - 3, len(work_points) - 2, len(work_points) - 1)]

    for point_index in range(len(points)):
        point = work_points[point_index]
        bad = [triangle for triangle in triangles if _circumcircle_contains(work_points, triangle, point)]
        edge_count: Dict[Tuple[int, int], int] = {}
        for triangle in bad:
            for edge in ((triangle[0], triangle[1]), (triangle[1], triangle[2]), (triangle[2], triangle[0])):
                normalized = tuple(sorted(edge))
                edge_count[normalized] = edge_count.get(normalized, 0) + 1
        triangles = [triangle for triangle in triangles if triangle not in bad]
        boundary_edges = [edge for edge, count in edge_count.items() if count == 1]
        for edge in boundary_edges:
            candidate = (edge[0], edge[1], point_index)
            p1, p2, p3 = (work_points[candidate[0]], work_points[candidate[1]], work_points[candidate[2]])
            if _triangle_area_xy(p1, p2, p3) <= 1e-9:
                continue
            triangles.append(candidate)

    return [triangle for triangle in triangles if not any(index in super_indices for index in triangle)]



# =========================================================

# SURFACE ENGINE

# =========================================================



class SurfaceEngine:

    """

    Builds an existing ground surface from real point input.

    TIN is preferred for survey/topo points. IDW remains available for legacy
    grid generation and fallback sampling outside the triangulated hull.

    """



    def __init__(
        self,
        points: List[SurveyPoint],
        *,
        breaklines: Optional[List[Breakline]] = None,
        boundary: Optional[List[Tuple[float, float]]] = None,
        control_verified: bool = False,
        source_type: str = "survey-unverified",
    ):

        if len(points) < 3:

            raise ValueError("Need at least 3 survey points.")

        self.breaklines = list(breaklines or [])
        self.boundary = list(boundary or []) or None
        breakline_points = _densify_breaklines(self.breaklines, max_segment_length=self._default_breakline_spacing(points))
        self.points = _dedupe_points(list(points) + breakline_points)
        self.control_verified = bool(control_verified)
        if source_type in {"survey", "survey-backed", "survey-unverified"}:
            self.source_type = "survey-backed" if self.control_verified else "survey-unverified"
        else:
            self.source_type = source_type



    # -----------------------------------------------------



    @classmethod

    def from_csv(cls, csv_path: str) -> "SurfaceEngine":

        points: List[SurveyPoint] = []



        with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:

            reader = csv.DictReader(f)



            required = {"x", "y", "z"}

            fieldnames = {h.lower().strip() for h in (reader.fieldnames or [])}



            if not required.issubset(fieldnames):

                raise ValueError(f"CSV must contain columns: {required}")



            for i, row in enumerate(reader, start=2):

                try:

                    x = float(row["x"])

                    y = float(row["y"])

                    z = float(row["z"])

                except Exception:

                    raise ValueError(f"Bad row {i}: {row}")



                points.append(SurveyPoint(x, y, z))



        return cls(points)



    # -----------------------------------------------------



    def bounds(self) -> Tuple[float, float, float, float]:

        xs = [p.x for p in self.points]

        ys = [p.y for p in self.points]

        return min(xs), min(ys), max(xs), max(ys)



    # -----------------------------------------------------



    def elevation_at(

        self,

        x: float,

        y: float,

        power: float = 2.0,

        neighbors: int = 8,

        max_radius: Optional[float] = None,

    ) -> float:



        return _idw_elevation(self.points, x, y, power=power, neighbors=neighbors, max_radius=max_radius)

    # -----------------------------------------------------

    @staticmethod
    def _default_breakline_spacing(points: Sequence[SurveyPoint]) -> float:
        if len(points) < 2:
            return 10.0
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        span = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
        return max(2.0, span / 24.0)

    # -----------------------------------------------------

    def build_tin(self) -> TinSurface:
        triangles_raw = _delaunay_triangles(self.points)
        triangles: List[TinTriangle] = []
        for triangle in triangles_raw:
            p1, p2, p3 = self.points[triangle[0]], self.points[triangle[1]], self.points[triangle[2]]
            area = _triangle_area_xy(p1, p2, p3)
            if area <= 1e-9:
                continue
            if self.boundary:
                cx = (p1.x + p2.x + p3.x) / 3.0
                cy = (p1.y + p2.y + p3.y) / 3.0
                if not _point_in_polygon((cx, cy), self.boundary):
                    continue
            point_confidences = {p1.confidence, p2.confidence, p3.confidence}
            confidence = "breakline_control" if "breakline_control" in point_confidences else self.source_type
            triangles.append(
                TinTriangle(
                    vertex_indices=(triangle[0], triangle[1], triangle[2]),
                    plane=_triangle_plane(p1, p2, p3),
                    area=area,
                    confidence=confidence,
                )
            )
        return TinSurface(
            points=list(self.points),
            triangles=triangles,
            breaklines=list(self.breaklines),
            boundary=list(self.boundary) if self.boundary else None,
            source_type=self.source_type,
            control_verified=self.control_verified,
            metadata={
                "point_count": len(self.points),
                "triangle_count": len(triangles),
                "breakline_count": len(self.breaklines),
                "boundary_clipped": bool(self.boundary),
                "truth_label": "TIN surface is built from supplied points and breakline samples; DEM/LiDAR is not survey-backed without verified control.",
            },
        )



    # -----------------------------------------------------



    def build_grid(

        self,

        x_min: Optional[float] = None,

        y_min: Optional[float] = None,

        x_max: Optional[float] = None,

        y_max: Optional[float] = None,

        cell_size: float = 10.0,

        padding: float = 0.0,

        power: float = 2.0,

        neighbors: int = 8,

        method: str = "idw",

    ) -> GridSurface:



        if cell_size <= 0:

            raise ValueError("cell_size must be > 0")



        bx0, by0, bx1, by1 = self.bounds()



        x_min = bx0 if x_min is None else x_min

        y_min = by0 if y_min is None else y_min

        x_max = bx1 if x_max is None else x_max

        y_max = by1 if y_max is None else y_max



        # apply padding

        x_min -= padding

        y_min -= padding

        x_max += padding

        y_max += padding



        ncols = int(round((x_max - x_min) / cell_size)) + 1

        nrows = int(round((y_max - y_min) / cell_size)) + 1



        tin = self.build_tin() if method.strip().lower() == "tin" else None
        values: List[List[float]] = []



        for row in range(nrows):

            y = y_min + row * cell_size

            row_vals: List[float] = []



            for col in range(ncols):

                x = x_min + col * cell_size

                z = tin.elevation_at(x, y) if tin is not None else None
                if z is None:
                    z = self.elevation_at(x, y, power=power, neighbors=neighbors)

                row_vals.append(z)



            values.append(row_vals)



        surface = GridSurface(

            x_min=x_min,

            y_min=y_min,

            x_max=x_min + (ncols - 1) * cell_size,

            y_max=y_min + (nrows - 1) * cell_size,

            cell_size=cell_size,

            ncols=ncols,

            nrows=nrows,

            values=values,

        )
        if tin is not None:
            setattr(surface, "_tin_surface", tin)
        return surface



    # -----------------------------------------------------



    def spot_elevations(

        self,

        x_min: float,

        y_min: float,

        x_max: float,

        y_max: float,

        spacing: float = 25.0,

    ) -> List[Tuple[float, float, float]]:



        if spacing <= 0:

            raise ValueError("spacing must be > 0")



        spots: List[Tuple[float, float, float]] = []



        y = y_min

        while y <= y_max + 1e-9:

            x = x_min

            while x <= x_max + 1e-9:

                z = self.elevation_at(x, y)

                spots.append((x, y, z))

                x += spacing

            y += spacing



        return spots

    # -----------------------------------------------------

    def surface_artifact(
        self,
        *,
        tin: Optional[TinSurface] = None,
        existing: Optional[GridSurface] = None,
        proposed: Optional[GridSurface] = None,
        contour_interval: float = 1.0,
        spot_spacing: float = 25.0,
        flow_step: float = 25.0,
        max_items: int = 120,
    ) -> Dict[str, Any]:
        tin_model = tin or self.build_tin()
        artifact = serialize_tin_surface(
            tin_model,
            contour_interval=contour_interval,
            spot_spacing=spot_spacing,
            flow_step=flow_step,
            max_items=max_items,
        )
        if existing is not None and proposed is not None:
            artifact["surface_comparison"] = compare_surfaces(existing, proposed, max_cells=max_items)
        return artifact


def tin_contour_segments(tin: TinSurface, interval: float = 1.0) -> Dict[float, List[Tuple[Tuple[float, float], Tuple[float, float]]]]:
    if interval <= 0:
        raise ValueError("interval must be > 0")
    if not tin.points or not tin.triangles:
        return {}
    z_min = min(point.z for point in tin.points)
    z_max = max(point.z for point in tin.points)
    start = math.floor(z_min / interval) * interval
    end = math.ceil(z_max / interval) * interval
    levels: List[float] = []
    level = start
    while level <= end + 1e-9:
        levels.append(round(level, 6))
        level += interval
    out: Dict[float, List[Tuple[Tuple[float, float], Tuple[float, float]]]] = {level: [] for level in levels}
    for triangle in tin.triangles:
        vertices = list(tin.triangle_points(triangle))
        edges = [(vertices[0], vertices[1]), (vertices[1], vertices[2]), (vertices[2], vertices[0])]
        for level in levels:
            hits: List[Tuple[float, float]] = []
            for p1, p2 in edges:
                if (p1.z < level <= p2.z) or (p2.z < level <= p1.z):
                    if abs(p2.z - p1.z) <= 1e-12:
                        continue
                    t = (level - p1.z) / (p2.z - p1.z)
                    hits.append((p1.x + (p2.x - p1.x) * t, p1.y + (p2.y - p1.y) * t))
            if len(hits) == 2:
                out[level].append((hits[0], hits[1]))
    return out


def slope_arrows(tin: TinSurface, *, step: float = 25.0, limit: int = 48) -> List[Dict[str, float]]:
    x_min, y_min, x_max, y_max = tin.bounds()
    arrows: List[Dict[str, float]] = []
    y = y_min + step / 2.0
    while y <= y_max and len(arrows) < limit:
        x = x_min + step / 2.0
        while x <= x_max and len(arrows) < limit:
            slope = tin.slope_at(x, y)
            z = tin.elevation_at(x, y)
            if slope and z is not None and slope["magnitude"] > 1e-6:
                arrows.append(
                    {
                        "x": round(x, 3),
                        "y": round(y, 3),
                        "z": round(z, 3),
                        "slope_pct": round(slope["magnitude"] * 100.0, 3),
                        "dx": round(slope["downhill_dx"], 6),
                        "dy": round(slope["downhill_dy"], 6),
                    }
                )
            x += step
        y += step
    return arrows


def flow_paths(tin: TinSurface, *, seed_step: float = 35.0, step_length: float = 15.0, limit: int = 12) -> List[Dict[str, Any]]:
    x_min, y_min, x_max, y_max = tin.bounds()
    seeds = slope_arrows(tin, step=seed_step, limit=limit * 2)
    paths: List[Dict[str, Any]] = []
    for index, seed in enumerate(seeds[:limit], start=1):
        x = float(seed["x"])
        y = float(seed["y"])
        path = [{"x": round(x, 3), "y": round(y, 3), "z": round(float(seed["z"]), 3)}]
        for _ in range(20):
            slope = tin.slope_at(x, y)
            if not slope or slope["magnitude"] <= 1e-6:
                break
            x += slope["downhill_dx"] * step_length
            y += slope["downhill_dy"] * step_length
            z = tin.elevation_at(x, y)
            if z is None:
                break
            path.append({"x": round(x, 3), "y": round(y, 3), "z": round(z, 3)})
            if x <= x_min or x >= x_max or y <= y_min or y >= y_max:
                break
        if len(path) >= 2:
            paths.append({"id": f"flow-{index}", "points": path, "source": "tin_gradient"})
    return paths


def serialize_tin_surface(
    tin: TinSurface,
    *,
    contour_interval: float = 1.0,
    spot_spacing: float = 25.0,
    flow_step: float = 25.0,
    max_items: int = 120,
) -> Dict[str, Any]:
    contours_by_level = tin_contour_segments(tin, interval=contour_interval)
    contours: List[Dict[str, Any]] = []
    for level, segments in contours_by_level.items():
        for p1, p2 in segments:
            contours.append({"level": round(level, 3), "points": [[round(p1[0], 3), round(p1[1], 3)], [round(p2[0], 3), round(p2[1], 3)]]})
            if len(contours) >= max_items:
                break
        if len(contours) >= max_items:
            break
    x_min, y_min, x_max, y_max = tin.bounds()
    spots: List[Dict[str, float]] = []
    y = y_min
    while y <= y_max + 1e-9 and len(spots) < max_items:
        x = x_min
        while x <= x_max + 1e-9 and len(spots) < max_items:
            z = tin.elevation_at(x, y)
            if z is not None:
                spots.append({"x": round(x, 3), "y": round(y, 3), "z": round(z, 3)})
            x += spot_spacing
        y += spot_spacing
    triangles = []
    for index, triangle in enumerate(tin.triangles[:max_items], start=1):
        pts = tin.triangle_points(triangle)
        triangles.append(
            {
                "id": f"tri-{index}",
                "points": [[round(pt.x, 3), round(pt.y, 3), round(pt.z, 3)] for pt in pts],
                "slope_pct": round(math.hypot(triangle.plane[0], triangle.plane[1]) * 100.0, 3),
                "confidence": triangle.confidence,
            }
        )
    return {
        "schema_version": "surface_artifact_v1",
        "model": "tin",
        "source_type": tin.source_type,
        "control_verified": tin.control_verified,
        "metadata": dict(tin.metadata),
        "bounds": [round(x_min, 3), round(y_min, 3), round(x_max, 3), round(y_max, 3)],
        "point_count": len(tin.points),
        "triangle_count": len(tin.triangles),
        "breaklines": [
            {
                "id": breakline.breakline_id,
                "source": breakline.source,
                "points": [[round(x, 3), round(y, 3), round(z, 3)] for x, y, z in breakline.points],
            }
            for breakline in tin.breaklines
        ],
        "boundary": [[round(x, 3), round(y, 3)] for x, y in tin.boundary] if tin.boundary else [],
        "triangles": triangles,
        "contours": contours,
        "spot_elevations": spots,
        "slope_arrows": slope_arrows(tin, step=flow_step, limit=max_items),
        "flow_paths": flow_paths(tin, seed_step=max(flow_step, 10.0), limit=min(16, max_items)),
        "confidence": {
            "source_type": tin.source_type,
            "control_verified": tin.control_verified,
            "not_survey_backed_reason": "" if tin.control_verified else "verified survey/control is not attached",
        },
        "truth_label": "TIN/surface data is computed from supplied elevation points; DEM/LiDAR is not survey-backed without verified control.",
    }


def compare_surfaces(existing: GridSurface, proposed: GridSurface, *, max_cells: int = 120) -> Dict[str, Any]:
    nrows = min(int(existing.nrows), int(proposed.nrows))
    ncols = min(int(existing.ncols), int(proposed.ncols))
    cells: List[Dict[str, Any]] = []
    cut_cf = 0.0
    fill_cf = 0.0
    cell_area = min(float(existing.cell_size), float(proposed.cell_size)) ** 2
    stride = max(1, int(math.sqrt(max(nrows * ncols / max(max_cells, 1), 1))))
    for row in range(nrows):
        for col in range(ncols):
            delta = float(proposed.values[row][col]) - float(existing.values[row][col])
            volume = delta * cell_area
            if volume < 0:
                cut_cf += -volume
            elif volume > 0:
                fill_cf += volume
            if row % stride == 0 and col % stride == 0 and len(cells) < max_cells:
                cells.append(
                    {
                        "x": round(existing.x_at(col), 3),
                        "y": round(existing.y_at(row), 3),
                        "delta_ft": round(delta, 3),
                        "mode": "cut" if delta < -1e-6 else "fill" if delta > 1e-6 else "balanced",
                    }
                )
    return {
        "cut_cf": round(cut_cf, 3),
        "fill_cf": round(fill_cf, 3),
        "net_cf": round(fill_cf - cut_cf, 3),
        "cells": cells,
        "truth_label": "Cut/fill comparison is sampled from existing and proposed surface elevations.",
    }

