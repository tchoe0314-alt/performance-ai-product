
from __future__ import annotations

"""
engines/drainage_engine.py (MERGED TRUE MAX VERSION)

Purpose
-------
Surface-drainage analysis and concept drainage-design engine for the AI civil
engineering platform.

This file preserves the strong real drainage base and expands it into a deeper
coordination engine that can:
- trace terrain-driven flow and low points
- group drainage basins and produce basin records
- rank/select inlet candidates using terrain + accumulation
- generate concept pipe runs toward ponds / outfalls
- compute contributing-area proxies and runoff estimates
- build structured summaries for planner/UI use
- expose hooks for storm module, conflict, compliance, and optimization

Design intent
-------------
- keep drainage_engine focused on surface behavior and collection logic
- keep storm_network_engine focused on structures / pipes / trunk network
- keep pipe/hydraulic engines as lower-level hydraulic math engines
- remain deterministic, explainable, and planner-ready
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Set, Iterable, Sequence

from geometry.geometry_actions import circle_action, polyline_action, text_action
from .surface_engine import GridSurface

EPS = 1e-9


# =====================================================
# DATA STRUCTURES
# =====================================================

@dataclass
class FlowArrow:
    start: Tuple[float, float]
    end: Tuple[float, float]
    slope: float


@dataclass
class LowPoint:
    x: float
    y: float
    z: float
    row: int
    col: int
    contributing_cells: int = 0


@dataclass
class PondTarget:
    name: str
    x: float
    y: float
    radius: float = 6.0


@dataclass
class Inlet:
    name: str
    x: float
    y: float
    z: float
    contributing_cells: int = 0
    contributing_area_sf: float = 0.0
    estimated_flow_cfs: Optional[float] = None
    basin_sink: Optional[Tuple[int, int]] = None
    target_name: Optional[str] = None
    tributary_basin_name: Optional[str] = None


@dataclass
class PipeRun:
    start: Tuple[float, float]
    end: Tuple[float, float]
    label: str
    path: Optional[List[Tuple[float, float]]] = None
    slope: Optional[float] = None
    flow_cfs: Optional[float] = None
    diameter_in: Optional[int] = None
    hydraulic_basis: str = "geometry_only"
    warnings: List[str] = field(default_factory=list)


@dataclass
class HydraulicInputs:
    runoff_c: float
    intensity_in_hr: float
    min_pipe_slope: float
    min_pipe_diameter_in: int = 12


@dataclass
class HydraulicAssumption:
    field_name: str
    assumed_value: Any
    reason: str


@dataclass
class InletRecord:
    inlet: Inlet
    warnings: List[str] = field(default_factory=list)


@dataclass
class BasinRecord:
    sink: Tuple[int, int]
    sink_name: str
    area_sf: float
    contributing_cells: int
    centroid_xy: Tuple[float, float]
    target_name: Optional[str] = None
    average_z: Optional[float] = None
    estimated_runoff_cfs: Optional[float] = None
    runoff_c: Optional[float] = None
    intensity_in_hr: Optional[float] = None


@dataclass
class DrainageValidationIssue:
    code: str
    severity: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DrainageDesignSummary:
    mode: str
    success: bool
    message: str
    provided_inputs: Dict[str, Any] = field(default_factory=dict)
    assumed_inputs: List[HydraulicAssumption] = field(default_factory=list)
    issues: List[DrainageValidationIssue] = field(default_factory=list)
    basin_records: List[BasinRecord] = field(default_factory=list)
    inlet_records: List[InletRecord] = field(default_factory=list)
    pipe_runs: List[PipeRun] = field(default_factory=list)
    explain: Dict[str, Any] = field(default_factory=dict)
    optimize_hooks: Dict[str, Any] = field(default_factory=dict)
    conflict_hooks: Dict[str, Any] = field(default_factory=dict)

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity.lower() == "error")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity.lower() == "warning")


# =====================================================
# ENGINE
# =====================================================

class DrainageEngine:
    """
    Commercial-grade drainage analysis engine built from the real base file.

    Preserved original capabilities:
    - pond targets
    - flow arrows
    - low point detection
    - flow path tracing
    - routed paths
    - drainage basin grouping
    - basin boundary actions
    - basin label actions
    - inlet placement
    - concept pipe runs
    - low point records
    - concept inlet records
    - drainage drawing actions

    Upgrades added:
    - strict vs assisted design modes
    - flow accumulation and contributing-area aware inlet ranking
    - basin records and structured design summaries
    - concept runoff estimates using Rational Method assumptions
    - pipe run concept sizing hooks
    - explain / optimize / conflict-ready payloads
    - stronger validation and caching
    """

    STRICT_MODE = "strict"
    ASSISTED_MODE = "assisted"

    def __init__(self, surface: GridSurface):
        self.surface = surface
        self.ponds: List[PondTarget] = []
        self._descent_cache: Dict[Tuple[int, int, float], Optional[Tuple[int, int, float]]] = {}
        self._flow_trace_cache: Dict[Tuple[int, int, float, int, bool, bool], Tuple[List[Tuple[float, float]], Optional[str], Tuple[int, int]]] = {}
        self._flow_accumulation_cache: Dict[Tuple[float, int], Dict[Tuple[int, int], int]] = {}
        self._validate_surface()

    # =====================================================
    # BASIC VALIDATION
    # =====================================================

    def _validate_surface(self) -> None:
        required_attrs = ["x_min", "y_min", "x_max", "y_max", "cell_size", "ncols", "nrows", "values"]
        for attr in required_attrs:
            if not hasattr(self.surface, attr):
                raise ValueError(f"DrainageEngine requires GridSurface with attribute '{attr}'.")
        if self.surface.cell_size <= 0:
            raise ValueError("GridSurface.cell_size must be > 0.")
        if self.surface.nrows <= 0 or self.surface.ncols <= 0:
            raise ValueError("GridSurface dimensions must be positive.")
        if len(self.surface.values) != self.surface.nrows:
            raise ValueError("GridSurface row count mismatch.")
        for row in self.surface.values:
            if len(row) != self.surface.ncols:
                raise ValueError("GridSurface column count mismatch.")

    # =====================================================
    # BASIC HELPERS
    # =====================================================

    def add_pond_target(self, name: str, x: float, y: float, radius: float = 6.0) -> None:
        self.ponds.append(PondTarget(name=name, x=x, y=y, radius=radius))

    def clear_pond_targets(self) -> None:
        self.ponds.clear()

    def _neighbors(self, row: int, col: int) -> List[Tuple[int, int]]:
        out: List[Tuple[int, int]] = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                rr = row + dr
                cc = col + dc
                if 0 <= rr < self.surface.nrows and 0 <= cc < self.surface.ncols:
                    out.append((rr, cc))
        return out

    def _point_xy(self, row: int, col: int) -> Tuple[float, float]:
        return self.surface.x_at(col), self.surface.y_at(row)

    def _cell_z(self, row: int, col: int) -> float:
        return self.surface.values[row][col]

    def _inside_pond(self, x: float, y: float) -> Optional[PondTarget]:
        for pond in self.ponds:
            if math.hypot(x - pond.x, y - pond.y) <= pond.radius:
                return pond
        return None

    def _inside_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.surface.nrows and 0 <= col < self.surface.ncols

    def _normalize_xy(self, x: float, y: float) -> Tuple[int, int]:
        row = int(round((y - self.surface.y_min) / self.surface.cell_size))
        col = int(round((x - self.surface.x_min) / self.surface.cell_size))
        row = max(0, min(self.surface.nrows - 1, row))
        col = max(0, min(self.surface.ncols - 1, col))
        return row, col

    def _polyline_length(self, pts: List[Tuple[float, float]]) -> float:
        if len(pts) < 2:
            return 0.0
        total = 0.0
        for i in range(1, len(pts)):
            total += math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
        return total

    def _dedupe_path(self, pts: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        if not pts:
            return []
        out = [pts[0]]
        for p in pts[1:]:
            if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > EPS:
                out.append(p)
        return out

    def _point_to_nearest_pond(self, x: float, y: float) -> Optional[PondTarget]:
        if not self.ponds:
            return None
        return min(self.ponds, key=lambda p: math.hypot(x - p.x, y - p.y))

    def _issue(self, code: str, severity: str, message: str, **context: Any) -> DrainageValidationIssue:
        return DrainageValidationIssue(code=code, severity=severity, message=message, context=dict(context))

    # =====================================================
    # FLOW ANALYSIS
    # =====================================================

    def _steepest_descent_neighbor(
        self,
        row: int,
        col: int,
        min_slope: float = 0.001,
        use_cache: bool = True,
    ) -> Optional[Tuple[int, int, float]]:
        key = (row, col, round(min_slope, 6))
        if use_cache and key in self._descent_cache:
            return self._descent_cache[key]

        z0 = self._cell_z(row, col)
        x0, y0 = self._point_xy(row, col)

        best: Optional[Tuple[int, int, float]] = None
        best_slope = 0.0
        best_drop = 0.0

        for rr, cc in self._neighbors(row, col):
            z1 = self._cell_z(rr, cc)
            if z1 >= z0:
                continue

            x1, y1 = self._point_xy(rr, cc)
            run = math.hypot(x1 - x0, y1 - y0)
            if run <= EPS:
                continue

            drop = z0 - z1
            slope = drop / run

            # Slight diagonal bias reduction for gridded stability
            if abs(rr - row) == 1 and abs(cc - col) == 1:
                slope *= 0.97

            if (slope > best_slope + EPS) or (abs(slope - best_slope) <= EPS and drop > best_drop + EPS):
                best_slope = slope
                best_drop = drop
                best = (rr, cc, slope)

        result = None if best is None or best_slope < min_slope else best
        if use_cache:
            self._descent_cache[key] = result
        return result

    def find_flow_arrows(
        self,
        sample_step: int = 2,
        min_slope: float = 0.001,
        arrow_scale: float = 0.75,
    ) -> List[FlowArrow]:
        arrows: List[FlowArrow] = []
        sample_step = max(1, int(sample_step))
        arrow_scale = max(0.1, min(1.0, arrow_scale))

        for row in range(0, self.surface.nrows, sample_step):
            for col in range(0, self.surface.ncols, sample_step):
                result = self._steepest_descent_neighbor(row, col, min_slope=min_slope)
                if result is None:
                    continue
                rr, cc, slope = result
                x0, y0 = self._point_xy(row, col)
                x1, y1 = self._point_xy(rr, cc)
                dx = x1 - x0
                dy = y1 - y0
                arrows.append(FlowArrow(start=(x0, y0), end=(x0 + dx * arrow_scale, y0 + dy * arrow_scale), slope=slope))
        return arrows

    def find_low_points(
        self,
        allow_flats_as_lows: bool = True,
        include_accumulation: bool = False,
        min_slope: float = 0.001,
    ) -> List[LowPoint]:
        acc = self.flow_accumulation(min_slope=min_slope) if include_accumulation else {}
        lows: List[LowPoint] = []

        for row in range(self.surface.nrows):
            for col in range(self.surface.ncols):
                z0 = self._cell_z(row, col)
                is_low = True
                has_strictly_higher_neighbor = False

                for rr, cc in self._neighbors(row, col):
                    zn = self._cell_z(rr, cc)
                    if zn < z0 - EPS:
                        is_low = False
                        break
                    if zn > z0 + EPS:
                        has_strictly_higher_neighbor = True

                if not is_low:
                    continue
                if not allow_flats_as_lows and not has_strictly_higher_neighbor:
                    continue

                x, y = self._point_xy(row, col)
                lows.append(
                    LowPoint(
                        x=x,
                        y=y,
                        z=z0,
                        row=row,
                        col=col,
                        contributing_cells=int(acc.get((row, col), 0)),
                    )
                )

        return lows

    def trace_flow_path(
        self,
        start_row: int,
        start_col: int,
        min_slope: float = 0.001,
        max_steps: int = 500,
        stop_at_pond: bool = True,
        stop_at_boundary: bool = False,
        use_cache: bool = True,
    ) -> Tuple[List[Tuple[float, float]], Optional[str], Tuple[int, int]]:
        cache_key = (start_row, start_col, round(min_slope, 6), max_steps, stop_at_pond, stop_at_boundary)
        if use_cache and cache_key in self._flow_trace_cache:
            return self._flow_trace_cache[cache_key]

        path: List[Tuple[float, float]] = []
        visited: Set[Tuple[int, int]] = set()
        row, col = start_row, start_col

        if not self._inside_bounds(row, col):
            result = (path, None, (start_row, start_col))
            return result

        for _ in range(max_steps):
            if (row, col) in visited:
                break
            visited.add((row, col))

            x, y = self._point_xy(row, col)
            path.append((x, y))

            if stop_at_pond:
                pond = self._inside_pond(x, y)
                if pond is not None:
                    result = (path, pond.name, (row, col))
                    if use_cache:
                        self._flow_trace_cache[cache_key] = result
                    return result

            if stop_at_boundary:
                if row in (0, self.surface.nrows - 1) or col in (0, self.surface.ncols - 1):
                    result = (path, "BOUNDARY", (row, col))
                    if use_cache:
                        self._flow_trace_cache[cache_key] = result
                    return result

            result = self._steepest_descent_neighbor(row, col, min_slope=min_slope)
            if result is None:
                final = (path, "LOW POINT", (row, col))
                if use_cache:
                    self._flow_trace_cache[cache_key] = final
                return final

            row, col, _ = result

        final = (path, None, (row, col))
        if use_cache:
            self._flow_trace_cache[cache_key] = final
        return final

    def routed_paths(
        self,
        sample_step: int = 4,
        min_slope: float = 0.001,
        max_steps: int = 500,
        dedupe: bool = True,
    ) -> List[Tuple[List[Tuple[float, float]], Optional[str]]]:
        routes: List[Tuple[List[Tuple[float, float]], Optional[str]]] = []
        seen_signatures: Set[Tuple[Tuple[int, int], ...]] = set()
        sample_step = max(1, int(sample_step))

        for row in range(0, self.surface.nrows, sample_step):
            for col in range(0, self.surface.ncols, sample_step):
                path, target, _ = self.trace_flow_path(row, col, min_slope=min_slope, max_steps=max_steps)
                if len(path) < 2:
                    continue
                if dedupe:
                    idx_path = tuple(self._normalize_xy(x, y) for x, y in path)
                    if idx_path in seen_signatures:
                        continue
                    seen_signatures.add(idx_path)
                routes.append((path, target))
        return routes

    def flow_accumulation(self, min_slope: float = 0.001, sample_step: int = 1) -> Dict[Tuple[int, int], int]:
        key = (round(min_slope, 6), int(sample_step))
        if key in self._flow_accumulation_cache:
            return self._flow_accumulation_cache[key]

        acc: Dict[Tuple[int, int], int] = {}
        sample_step = max(1, int(sample_step))

        for row in range(0, self.surface.nrows, sample_step):
            for col in range(0, self.surface.ncols, sample_step):
                _, _, sink = self.trace_flow_path(row, col, min_slope=min_slope, max_steps=500)
                acc[sink] = acc.get(sink, 0) + 1

        self._flow_accumulation_cache[key] = acc
        return acc

    # =====================================================
    # BASINS
    # =====================================================

    def drainage_basins(
        self,
        sample_step: int = 2,
        min_slope: float = 0.001,
        max_steps: int = 500,
    ) -> Dict[Tuple[int, int], List[Tuple[int, int]]]:
        basins: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
        sample_step = max(1, int(sample_step))

        for row in range(0, self.surface.nrows, sample_step):
            for col in range(0, self.surface.ncols, sample_step):
                _, _, sink = self.trace_flow_path(row, col, min_slope=min_slope, max_steps=max_steps)
                basins.setdefault(sink, []).append((row, col))
        return basins

    def basin_records(
        self,
        sample_step: int = 2,
        min_slope: float = 0.001,
        max_steps: int = 500,
    ) -> List[BasinRecord]:
        basins = self.drainage_basins(sample_step=sample_step, min_slope=min_slope, max_steps=max_steps)
        records: List[BasinRecord] = []

        for sink, cells in basins.items():
            if not cells:
                continue
            pts = [self._point_xy(r, c) for r, c in cells]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            zs = [self._cell_z(r, c) for r, c in cells]
            cx = sum(xs) / len(xs)
            cy = sum(ys) / len(ys)
            area_sf = len(cells) * (self.surface.cell_size * sample_step) ** 2

            sink_xy = self._point_xy(sink[0], sink[1])
            nearest_pond = self._point_to_nearest_pond(sink_xy[0], sink_xy[1])

            records.append(
                BasinRecord(
                    sink=sink,
                    sink_name=f"SINK_{sink[0]}_{sink[1]}",
                    area_sf=area_sf,
                    contributing_cells=len(cells),
                    centroid_xy=(cx, cy),
                    target_name=nearest_pond.name if nearest_pond else None,
                    average_z=(sum(zs) / len(zs)) if zs else None,
                )
            )

        records.sort(key=lambda r: (-r.area_sf, r.sink_name))
        return records

    def _convex_hull(self, points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        if len(points) <= 1:
            return points[:]

        pts = sorted(set(points))
        if len(pts) <= 2:
            return pts

        def cross(o: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]) -> float:
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        lower: List[Tuple[float, float]] = []
        for p in pts:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)

        upper: List[Tuple[float, float]] = []
        for p in reversed(pts):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)

        return lower[:-1] + upper[:-1]

    def basin_boundary_actions(
        self,
        basins: Dict[Tuple[int, int], List[Tuple[int, int]]],
        min_cells: int = 3,
        close_polylines: bool = True,
    ) -> List[Dict]:
        actions: List[Dict] = []

        for _, cells in basins.items():
            if not cells or len(cells) < min_cells:
                continue
            points = [self._point_xy(row, col) for row, col in cells]
            hull = self._convex_hull(points)
            if len(hull) >= 3:
                actions.append(polyline_action(hull, "", "BASIN_BOUNDARY", close_polylines))
        return actions

    def basin_label_actions(
        self,
        sample_step: int = 2,
        min_slope: float = 0.001,
        max_steps: int = 500,
    ) -> List[Dict]:
        actions: List[Dict] = []
        records = self.basin_records(sample_step=sample_step, min_slope=min_slope, max_steps=max_steps)

        for idx, record in enumerate(records, start=1):
            sink_x, sink_y = self._point_xy(record.sink[0], record.sink[1])
            sink_z = self._cell_z(record.sink[0], record.sink[1])

            actions.append(text_action(record.centroid_xy, f"BASIN {idx}", 1.4, "ANNO"))
            actions.append(text_action((record.centroid_xy[0], record.centroid_xy[1] - 2.0), f"{record.area_sf:.0f} SF", 1.0, "ANNO"))
            actions.append(text_action((sink_x + 1.0, sink_y + 1.0), f"SINK {sink_z:.2f}", 0.9, "ANNO"))

        return actions

    # =====================================================
    # INLETS / CONCEPT PIPES
    # =====================================================

    def place_inlets(
        self,
        basin_records: Optional[Sequence[BasinRecord]] = None,
        hydraulic: Optional[HydraulicInputs] = None,
        min_spacing: float = 20.0,
        max_inlets: int = 12,
        min_edge_offset: float = 0.0,
        use_flow_accumulation: bool = True,
        min_contributing_cells: int = 1,
        min_slope: float = 0.001,
    ) -> List[Inlet]:
        lows = self.find_low_points(include_accumulation=use_flow_accumulation, min_slope=min_slope)
        basin_by_sink = {tuple(record.sink): record for record in (basin_records or []) if getattr(record, "sink", None)}

        def inlet_priority(lp: LowPoint) -> Tuple[float, float, float, int, int]:
            basin = basin_by_sink.get((lp.row, lp.col))
            basin_runoff = float(getattr(basin, "estimated_runoff_cfs", 0.0) or 0.0)
            basin_area = float(getattr(basin, "area_sf", 0.0) or 0.0)
            target_bonus = 1.0 if getattr(basin, "target_name", None) else 0.0
            if hydraulic is not None and basin is not None and basin_runoff <= 0.0:
                basin_runoff = self._estimate_basin_runoff_cfs(basin, hydraulic)
            return (-basin_runoff, -basin_area, -target_bonus, -int(lp.contributing_cells), lp.row * 10000 + lp.col)

        lows = sorted(lows, key=inlet_priority)
        inlets: List[Inlet] = []

        for lp in lows:
            if len(inlets) >= max_inlets:
                break

            x, y = lp.x, lp.y
            if min_edge_offset > 0.0:
                if (
                    x < self.surface.x_min + min_edge_offset
                    or x > self.surface.x_max - min_edge_offset
                    or y < self.surface.y_min + min_edge_offset
                    or y > self.surface.y_max - min_edge_offset
                ):
                    continue

            if lp.contributing_cells < max(1, int(min_contributing_cells)):
                continue

            too_close = False
            for inlet in inlets:
                if math.hypot(lp.x - inlet.x, lp.y - inlet.y) < min_spacing:
                    too_close = True
                    break
            if too_close:
                continue

            area_sf = lp.contributing_cells * (self.surface.cell_size ** 2)
            basin = basin_by_sink.get((lp.row, lp.col))
            inlets.append(
                Inlet(
                    name=f"INLET-{len(inlets)+1}",
                    x=lp.x,
                    y=lp.y,
                    z=lp.z,
                    contributing_cells=lp.contributing_cells,
                    contributing_area_sf=max(area_sf, float(getattr(basin, "area_sf", 0.0) or 0.0)),
                    basin_sink=(lp.row, lp.col),
                    target_name=getattr(basin, "target_name", None),
                    tributary_basin_name=getattr(basin, "sink_name", None),
                    estimated_flow_cfs=(
                        self._estimate_basin_runoff_cfs(basin, hydraulic)
                        if basin is not None and hydraulic is not None
                        else None
                    ),
                )
            )

        return inlets

    def _route_path_to_pond(
        self,
        inlet: Inlet,
        nearest_pond: PondTarget,
        min_slope: float = 0.001,
        max_steps: int = 500,
        snap_last_segment: bool = True,
    ) -> List[Tuple[float, float]]:
        row, col = self._normalize_xy(inlet.x, inlet.y)

        path, target, _ = self.trace_flow_path(
            row,
            col,
            min_slope=min_slope,
            max_steps=max_steps,
            stop_at_pond=True,
            stop_at_boundary=False,
        )

        path = self._dedupe_path(path)

        if not path:
            path = [(inlet.x, inlet.y)]

        last_x, last_y = path[-1]
        d_to_pond = math.hypot(last_x - nearest_pond.x, last_y - nearest_pond.y)

        if snap_last_segment and d_to_pond > nearest_pond.radius:
            path.append((nearest_pond.x, nearest_pond.y))
        elif target is None and path[-1] != (nearest_pond.x, nearest_pond.y):
            path.append((nearest_pond.x, nearest_pond.y))

        return self._dedupe_path(path)

    def _resolve_hydraulic_inputs(
        self,
        mode: str,
        hydraulic: Optional[HydraulicInputs],
        summary: DrainageDesignSummary,
    ) -> Optional[HydraulicInputs]:
        if hydraulic is not None:
            summary.provided_inputs = {
                "runoff_c": hydraulic.runoff_c,
                "intensity_in_hr": hydraulic.intensity_in_hr,
                "min_pipe_slope": hydraulic.min_pipe_slope,
                "min_pipe_diameter_in": hydraulic.min_pipe_diameter_in,
            }
            return hydraulic

        if mode == self.STRICT_MODE:
            summary.issues.append(self._issue(
                code="MISSING_HYDRAULIC_INPUTS",
                severity="error",
                message="Strict drainage design requires explicit hydraulic inputs.",
            ))
            summary.success = False
            summary.message = "Missing required hydraulic inputs."
            return None

        assumed = HydraulicInputs(
            runoff_c=0.85,
            intensity_in_hr=4.0,
            min_pipe_slope=0.003,
            min_pipe_diameter_in=12,
        )
        summary.assumed_inputs.extend([
            HydraulicAssumption("runoff_c", assumed.runoff_c, "Used concept commercial-site runoff coefficient."),
            HydraulicAssumption("intensity_in_hr", assumed.intensity_in_hr, "Used concept rainfall intensity."),
            HydraulicAssumption("min_pipe_slope", assumed.min_pipe_slope, "Used default concept storm pipe slope."),
            HydraulicAssumption("min_pipe_diameter_in", assumed.min_pipe_diameter_in, "Used minimum concept storm diameter."),
        ])
        return assumed

    def _estimate_inlet_flow_cfs(self, inlet: Inlet, hydraulic: HydraulicInputs) -> float:
        area_ac = max(inlet.contributing_area_sf / 43560.0, 0.01)
        return 1.008 * area_ac * hydraulic.runoff_c * hydraulic.intensity_in_hr

    def _estimate_basin_runoff_cfs(self, basin: BasinRecord, hydraulic: HydraulicInputs) -> float:
        area_ac = max(basin.area_sf / 43560.0, 0.01)
        return 1.008 * area_ac * hydraulic.runoff_c * hydraulic.intensity_in_hr

    def _apply_basin_context_to_inlets(
        self,
        inlets: Sequence[Inlet],
        basin_records: Sequence[BasinRecord],
        hydraulic: HydraulicInputs,
    ) -> None:
        basin_by_sink = {tuple(record.sink): record for record in basin_records if record.sink}
        for inlet in inlets:
            sink_key = tuple(inlet.basin_sink or ())
            basin = basin_by_sink.get(sink_key)
            if basin is None and basin_records:
                basin = min(
                    basin_records,
                    key=lambda record: math.hypot(
                        float(record.centroid_xy[0]) - inlet.x,
                        float(record.centroid_xy[1]) - inlet.y,
                    ),
                )
            if basin is None:
                continue
            inlet.tributary_basin_name = basin.sink_name
            inlet.target_name = inlet.target_name or basin.target_name
            inlet.contributing_area_sf = max(inlet.contributing_area_sf, basin.area_sf)
            inlet.estimated_flow_cfs = self._estimate_inlet_flow_cfs(inlet, hydraulic)

    def _choose_concept_diameter(self, flow_cfs: float, hydraulic: HydraulicInputs) -> int:
        table = [
            (12, 3.5),
            (15, 5.5),
            (18, 8.5),
            (24, 16.0),
            (30, 27.0),
            (36, 41.0),
            (42, 57.0),
            (48, 76.0),
        ]
        required = max(flow_cfs, 0.0)
        for dia, cap in table:
            if dia < hydraulic.min_pipe_diameter_in:
                continue
            if cap >= required:
                return dia
        return table[-1][0]

    def pipe_runs(
        self,
        inlets: List[Inlet],
        basin_records: Optional[Sequence[BasinRecord]] = None,
        follow_surface: bool = True,
        min_slope: float = 0.001,
        max_steps: int = 500,
        mode: str = ASSISTED_MODE,
        hydraulic: Optional[HydraulicInputs] = None,
    ) -> Tuple[List[PipeRun], DrainageDesignSummary]:
        summary = DrainageDesignSummary(
            mode=mode,
            success=True,
            message="Pipe runs generated.",
        )
        runs: List[PipeRun] = []

        if not self.ponds:
            summary.success = False
            summary.message = "No pond/outfall targets defined."
            summary.issues.append(self._issue(
                code="NO_PONDS_DEFINED",
                severity="error",
                message="Drainage pipe design requires at least one pond/outfall target.",
            ))
            return runs, summary

        hydraulic_resolved = self._resolve_hydraulic_inputs(mode, hydraulic, summary)
        if hydraulic_resolved is None:
            return runs, summary

        self._apply_basin_context_to_inlets(
            inlets=inlets,
            basin_records=list(basin_records or []),
            hydraulic=hydraulic_resolved,
        )

        for inlet in inlets:
            nearest_pond = min(self.ponds, key=lambda p: math.hypot(inlet.x - p.x, inlet.y - p.y))
            inlet.target_name = inlet.target_name or nearest_pond.name

            inlet_warnings: List[str] = []
            inlet.estimated_flow_cfs = inlet.estimated_flow_cfs or self._estimate_inlet_flow_cfs(inlet, hydraulic_resolved)
            inlet_record = InletRecord(inlet=inlet, warnings=inlet_warnings)
            summary.inlet_records.append(inlet_record)

            if follow_surface:
                path = self._route_path_to_pond(
                    inlet=inlet,
                    nearest_pond=nearest_pond,
                    min_slope=min_slope,
                    max_steps=max_steps,
                )
            else:
                path = [(inlet.x, inlet.y), (nearest_pond.x, nearest_pond.y)]

            path = self._dedupe_path(path)
            run_length = self._polyline_length(path)

            inlet_z = inlet.z
            pond_z = self._cell_z(*self._normalize_xy(nearest_pond.x, nearest_pond.y))
            slope = None
            pipe_warnings: List[str] = []

            if run_length > EPS:
                slope = max((inlet_z - pond_z) / run_length, hydraulic_resolved.min_pipe_slope)
                if slope < hydraulic_resolved.min_pipe_slope:
                    pipe_warnings.append("Computed terrain slope is below minimum pipe slope; minimum concept slope used.")

            diameter_in = self._choose_concept_diameter(inlet.estimated_flow_cfs or 0.0, hydraulic_resolved)

            run = PipeRun(
                start=(inlet.x, inlet.y),
                end=(nearest_pond.x, nearest_pond.y),
                path=path,
                label=f"{inlet.name} TO {nearest_pond.name}",
                slope=slope,
                flow_cfs=inlet.estimated_flow_cfs,
                diameter_in=diameter_in,
                hydraulic_basis="rational_method_concept" if inlet.estimated_flow_cfs is not None else "geometry_only",
                warnings=[*inlet_record.warnings, *pipe_warnings],
            )
            runs.append(run)

            for warning in run.warnings:
                summary.issues.append(self._issue(
                    code="PIPE_WARNING",
                    severity="warning",
                    message=warning,
                    pipe_label=run.label,
                ))

        summary.pipe_runs = runs
        if summary.error_count() > 0:
            summary.success = False
            summary.message = "One or more pipe runs failed."
        elif summary.warning_count() > 0:
            summary.message = "Pipe runs generated with warnings."

        return runs, summary

    # =====================================================
    # FULL DESIGN
    # =====================================================

    def design_network(
        self,
        *,
        mode: str = STRICT_MODE,
        hydraulic: Optional[HydraulicInputs] = None,
        inlet_min_spacing: float = 20.0,
        max_inlets: int = 12,
        min_edge_offset: float = 0.0,
        min_contributing_cells: int = 1,
        min_slope: float = 0.001,
        sample_step: int = 2,
    ) -> DrainageDesignSummary:
        summary = DrainageDesignSummary(
            mode=mode,
            success=True,
            message="Drainage network designed.",
        )

        if not self.ponds:
            summary.success = False
            summary.message = "No pond/outfall targets defined."
            summary.issues.append(self._issue(
                code="NO_PONDS_DEFINED",
                severity="error",
                message="Drainage design requires at least one pond/outfall target.",
            ))
            return summary

        summary.basin_records = self.basin_records(sample_step=sample_step, min_slope=min_slope)
        hydraulic_resolved = self._resolve_hydraulic_inputs(mode, hydraulic, summary)
        if hydraulic_resolved is None:
            summary.explain = self._build_explain(summary)
            summary.optimize_hooks = self._build_optimize_hooks(summary)
            summary.conflict_hooks = self._build_conflict_hooks(summary)
            return summary

        for basin in summary.basin_records:
            basin.runoff_c = hydraulic_resolved.runoff_c
            basin.intensity_in_hr = hydraulic_resolved.intensity_in_hr
            basin.estimated_runoff_cfs = self._estimate_basin_runoff_cfs(basin, hydraulic_resolved)

        inlets = self.place_inlets(
            basin_records=summary.basin_records,
            hydraulic=hydraulic_resolved,
            min_spacing=inlet_min_spacing,
            max_inlets=max_inlets,
            min_edge_offset=min_edge_offset,
            use_flow_accumulation=True,
            min_contributing_cells=min_contributing_cells,
            min_slope=min_slope,
        )

        if not inlets:
            summary.success = False
            summary.message = "No suitable inlet locations were identified."
            summary.issues.append(self._issue(
                code="NO_INLETS_IDENTIFIED",
                severity="error",
                message="No suitable inlet locations were identified from terrain flow analysis.",
            ))
            summary.explain = self._build_explain(summary)
            summary.optimize_hooks = self._build_optimize_hooks(summary)
            summary.conflict_hooks = self._build_conflict_hooks(summary)
            return summary

        runs, run_summary = self.pipe_runs(
            inlets=inlets,
            basin_records=summary.basin_records,
            follow_surface=True,
            min_slope=min_slope,
            max_steps=500,
            mode=mode,
            hydraulic=hydraulic_resolved,
        )

        summary.provided_inputs = run_summary.provided_inputs
        summary.assumed_inputs = run_summary.assumed_inputs
        summary.inlet_records = run_summary.inlet_records
        summary.pipe_runs = runs
        summary.issues.extend(run_summary.issues)

        if run_summary.error_count() > 0:
            summary.success = False
            summary.message = "Drainage network design failed."
        elif run_summary.warning_count() > 0:
            summary.message = "Drainage network designed with warnings."

        summary.explain = self._build_explain(summary)
        summary.optimize_hooks = self._build_optimize_hooks(summary)
        summary.conflict_hooks = self._build_conflict_hooks(summary)
        return summary

    # =====================================================
    # DRAWING / EXPORT HELPERS
    # =====================================================

    def get_low_point_records(self) -> List[Dict]:
        records: List[Dict] = []
        for lp in self.find_low_points(include_accumulation=True):
            records.append({
                "name": f"LOW-{lp.row}-{lp.col}",
                "x": lp.x,
                "y": lp.y,
                "z": lp.z,
                "row": lp.row,
                "col": lp.col,
                "contributing_cells": lp.contributing_cells,
            })
        return records

    def get_inlet_records(self, inlets: Sequence[Inlet]) -> List[Dict]:
        return [
            {
                "name": inlet.name,
                "x": inlet.x,
                "y": inlet.y,
                "z": inlet.z,
                "contributing_cells": inlet.contributing_cells,
                "contributing_area_sf": inlet.contributing_area_sf,
                "estimated_flow_cfs": inlet.estimated_flow_cfs,
                "target_name": inlet.target_name,
                "tributary_basin_name": inlet.tributary_basin_name,
            }
            for inlet in inlets
        ]

    def inlet_actions(self, inlets: Sequence[Inlet]) -> List[Dict]:
        actions: List[Dict] = []
        for inlet in inlets:
            actions.append(circle_action((inlet.x, inlet.y), 1.5, inlet.name, "SYMBOL"))
            actions.append(text_action((inlet.x + 1.5, inlet.y + 1.5), inlet.name, 0.8, "ANNO"))
        return actions

    def pipe_actions(self, runs: Sequence[PipeRun], add_labels: bool = True) -> List[Dict]:
        actions: List[Dict] = []
        for run in runs:
            path = run.path if run.path else [run.start, run.end]
            actions.append(polyline_action(path, "", "PIPE", False))
            if add_labels:
                mid_idx = len(path) // 2
                mx, my = path[mid_idx]
                parts = [run.label]
                if run.diameter_in is not None:
                    parts.append(f'{run.diameter_in}"')
                if run.flow_cfs is not None:
                    parts.append(f"{run.flow_cfs:.2f} CFS")
                actions.append(text_action((mx, my), " | ".join(parts), 0.8, "ANNO"))
        return actions

    def drainage_actions(
        self,
        sample_step: int = 4,
        min_slope: float = 0.001,
        max_steps: int = 500,
        include_basins: bool = True,
        include_labels: bool = True,
        include_flow_arrows: bool = True,
        include_inlets: bool = True,
        include_pipes: bool = True,
    ) -> List[Dict]:
        actions: List[Dict] = []

        if include_flow_arrows:
            for arrow in self.find_flow_arrows(sample_step=sample_step, min_slope=min_slope):
                actions.append(polyline_action([arrow.start, arrow.end], "", "DRAIN_FLOW", False))

        if include_basins:
            basins = self.drainage_basins(sample_step=sample_step, min_slope=min_slope, max_steps=max_steps)
            actions.extend(self.basin_boundary_actions(basins))
            if include_labels:
                actions.extend(self.basin_label_actions(sample_step=sample_step, min_slope=min_slope, max_steps=max_steps))

        if include_inlets and self.ponds:
            inlets = self.place_inlets(min_spacing=20.0, max_inlets=12, use_flow_accumulation=True, min_contributing_cells=1, min_slope=min_slope)
            actions.extend(self.inlet_actions(inlets))
            if include_pipes:
                runs, _ = self.pipe_runs(
                    inlets=inlets,
                    follow_surface=True,
                    min_slope=min_slope,
                    max_steps=max_steps,
                    mode=self.ASSISTED_MODE,
                    hydraulic=None,
                )
                actions.extend(self.pipe_actions(runs, add_labels=include_labels))

        return actions

    # =====================================================
    # PLANNER/UI HOOKS
    # =====================================================

    def _build_explain(self, summary: DrainageDesignSummary) -> Dict[str, Any]:
        return {
            "system_type": "drainage",
            "key_logic": [
                "Terrain cells were traced downslope to sinks/pond targets.",
                "Basin groups were formed from common sinks.",
                "Low points were ranked by contributing accumulation and elevation.",
                "Inlet candidates were selected using spacing and contributing-area thresholds.",
                "Pipe runs were generated to the nearest pond/outfall target using surface-following paths.",
            ],
            "basin_count": len(summary.basin_records),
            "inlet_count": len(summary.inlet_records),
            "pipe_run_count": len(summary.pipe_runs),
            "critical_issues": [
                {
                    "code": issue.code,
                    "severity": issue.severity,
                    "message": issue.message,
                    "context": dict(issue.context),
                }
                for issue in summary.issues[:25]
            ],
        }

    def _build_optimize_hooks(self, summary: DrainageDesignSummary) -> Dict[str, Any]:
        total_length = sum(self._polyline_length(run.path or [run.start, run.end]) for run in summary.pipe_runs)
        total_flow = sum((run.flow_cfs or 0.0) for run in summary.pipe_runs)
        return {
            "penalties": {
                "warning_penalty": summary.warning_count() * 4.0,
                "error_penalty": summary.error_count() * 20.0,
                "pipe_length_penalty": round(total_length / 100.0, 3),
                "high_flow_penalty": round(total_flow * 1.5, 3),
            },
            "candidate_improvements": [
                "reduce isolated low points by improving grading continuity",
                "increase inlet spacing quality to reduce redundant structures",
                "shorten concept pipe paths to nearest acceptable outfall",
                "increase detention/outfall count where tributary areas are oversized",
            ],
        }

    def _build_conflict_hooks(self, summary: DrainageDesignSummary) -> Dict[str, Any]:
        return {
            "drainage_inlets": [
                {
                    "name": rec.inlet.name,
                    "x": rec.inlet.x,
                    "y": rec.inlet.y,
                    "z": rec.inlet.z,
                    "contributing_area_sf": rec.inlet.contributing_area_sf,
                }
                for rec in summary.inlet_records
            ],
            "drainage_pipe_runs": [
                {
                    "label": run.label,
                    "path": list(run.path or [run.start, run.end]),
                    "diameter_in": run.diameter_in,
                    "flow_cfs": run.flow_cfs,
                    "slope": run.slope,
                }
                for run in summary.pipe_runs
            ],
            "basin_boundaries": [
                {
                    "sink_name": rec.sink_name,
                    "centroid_xy": rec.centroid_xy,
                    "area_sf": rec.area_sf,
                    "target_name": rec.target_name,
                    "estimated_runoff_cfs": rec.estimated_runoff_cfs,
                }
                for rec in summary.basin_records
            ],
        }
