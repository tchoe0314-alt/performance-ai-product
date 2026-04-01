
from __future__ import annotations

"""
engines/grading_engine.py (MERGED TRUE MAX VERSION)

Purpose
-------
Coordinated grading engine for the AI civil engineering platform.

This file preserves the strong existing grading base and expands it into a
broader grading/physics coordination layer that can:
- build a proposed surface from multiple grading elements
- interpolate existing/proposed elevations robustly
- enforce tie-ins and transitions
- evaluate slopes, ponding risk, and drainage direction
- provide low-point / drainage-support metadata
- compute earthwork directly from surfaces
- register grading objects / zones into ProjectModel
- expose planner-ready explain / optimize / conflict hooks

Design intent
-------------
- Keep grading as a real discipline engine, not just a drawing helper
- Preserve rectangular grading primitives for robustness and compatibility
- Expand coordination depth for drainage, storm, utilities, roads, parking,
  ADA-like slope checks, and earthwork
- Keep architecture ready for planner/orchestrator integration
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from core.geometry_core import EngineeringDomain, EngineeringObject, Point3D, ProjectModel, ZoneType, rect_zone
from .surface_engine import GridSurface


EPS = 1e-9


# =============================================================================
# helpers
# =============================================================================

def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _smoothstep01(t: float) -> float:
    t = _clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if abs(b) > EPS else default


def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def _polyline_length(pts: Sequence[Tuple[float, float]]) -> float:
    if len(pts) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(pts)):
        total += math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
    return total


# =============================================================================
# core grading models
# =============================================================================

@dataclass
class GradeElement:
    """
    Design grading primitive.

    Supported kinds:
    - pad
    - parking
    - road
    - pond
    - swale
    - utility
    - plaza
    - sidewalk
    - basin
    """

    kind: str
    x: float
    y: float
    width: float
    depth: float
    base_elev: float

    slope_x: float = 0.0
    slope_y: float = 0.0

    edge_rise: float = 3.0
    crown: float = 0.0
    side_slope: float = 0.25
    min_grade: float = 0.005
    max_grade: float = 0.15

    priority: int = 0
    transition_zone: float = 10.0
    shoulder_width: float = 0.0
    tie_mode: str = "smooth"  # smooth | linear | hold
    orientation: str = "x"    # x or y
    name: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        warnings: List[str] = []

        if self.width <= 0.0:
            warnings.append(f"{self.label}: width must be > 0.")
        if self.depth <= 0.0:
            warnings.append(f"{self.label}: depth must be > 0.")
        if self.transition_zone < 0.0:
            warnings.append(f"{self.label}: transition_zone cannot be negative.")
        if self.shoulder_width < 0.0:
            warnings.append(f"{self.label}: shoulder_width cannot be negative.")
        if self.orientation not in {"x", "y"}:
            warnings.append(f"{self.label}: orientation should be 'x' or 'y'.")
        if self.tie_mode not in {"smooth", "linear", "hold"}:
            warnings.append(f"{self.label}: tie_mode should be 'smooth', 'linear', or 'hold'.")
        if self.kind not in {"pad", "parking", "road", "pond", "swale", "utility", "plaza", "sidewalk", "basin"}:
            warnings.append(f"{self.label}: unsupported kind '{self.kind}'.")

        avg_grade = math.hypot(self.slope_x, self.slope_y)
        if avg_grade > self.max_grade + 1e-6:
            warnings.append(
                f"{self.label}: planar grade {avg_grade:.4f} exceeds max_grade {self.max_grade:.4f}."
            )

        if self.kind == "road" and abs(self.crown) < EPS:
            warnings.append(f"{self.label}: road has zero crown; drainage may be poor.")

        if self.kind in {"parking", "plaza", "utility", "sidewalk"} and avg_grade < self.min_grade - 1e-6:
            warnings.append(
                f"{self.label}: planar grade {avg_grade:.4f} is below min_grade {self.min_grade:.4f}; surface may pond."
            )

        if self.kind in {"sidewalk"} and avg_grade > 0.05 + 1e-6:
            warnings.append(f"{self.label}: sidewalk grade exceeds ADA-like concept limit of 5.0%.")

        return warnings

    @property
    def label(self) -> str:
        return self.name or f"{self.kind}@({self.x:.2f},{self.y:.2f})"

    @property
    def x2(self) -> float:
        return self.x + self.width

    @property
    def y2(self) -> float:
        return self.y + self.depth

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2.0

    @property
    def center_y(self) -> float:
        return self.y + self.depth / 2.0

    def contains(self, px: float, py: float, include_transition: bool = False) -> bool:
        pad = self.transition_zone if include_transition else 0.0
        return (self.x - pad) <= px <= (self.x2 + pad) and (self.y - pad) <= py <= (self.y2 + pad)

    def distance_to_edge(self, px: float, py: float) -> float:
        if not self.contains(px, py):
            return 0.0
        dx = min(px - self.x, self.x2 - px)
        dy = min(py - self.y, self.y2 - py)
        return min(dx, dy)

    def outside_distance_to_box(self, px: float, py: float) -> float:
        dx = max(self.x - px, 0.0, px - self.x2)
        dy = max(self.y - py, 0.0, py - self.y2)
        return math.hypot(dx, dy)

    def local_offsets(self, px: float, py: float) -> Tuple[float, float]:
        return px - self.x, py - self.y

    def plane_elevation_at(self, px: float, py: float) -> float:
        dx, dy = self.local_offsets(px, py)
        return self.base_elev + dx * self.slope_x + dy * self.slope_y

    def drainage_fall_direction(self) -> Tuple[float, float]:
        gx = self.slope_x
        gy = self.slope_y
        mag = math.hypot(gx, gy)
        if mag <= EPS:
            return (0.0, 0.0)
        return (-gx / mag, -gy / mag)

    def _road_crossfall_component(self, px: float, py: float) -> float:
        if self.orientation == "x":
            cross = py - self.center_y
        else:
            cross = px - self.center_x
        return -abs(cross) * abs(self.crown)

    def _swale_component(self, px: float, py: float) -> float:
        if self.orientation == "x":
            cross = abs(py - self.center_y)
        else:
            cross = abs(px - self.center_x)
        return -cross * abs(self.side_slope)

    def _pond_component(self, px: float, py: float) -> float:
        cx = self.center_x
        cy = self.center_y
        rx = max(self.width / 2.0, EPS)
        ry = max(self.depth / 2.0, EPS)

        nx = (px - cx) / rx
        ny = (py - cy) / ry
        r = math.sqrt(nx * nx + ny * ny)
        t = _clamp(r, 0.0, 1.0)
        return _smoothstep01(t) * self.edge_rise

    def _shoulder_component(self, px: float, py: float) -> float:
        if self.shoulder_width <= EPS:
            return 0.0
        edge_dist = self.distance_to_edge(px, py)
        if edge_dist <= 0.0 or edge_dist >= self.shoulder_width:
            return 0.0
        t = 1.0 - (edge_dist / max(self.shoulder_width, EPS))
        return t * 0.25

    def elevation_at(self, px: float, py: float) -> float:
        z = self.plane_elevation_at(px, py)

        if self.kind == "pad":
            return self.base_elev

        if self.kind in {"parking", "plaza", "utility", "sidewalk"}:
            return z

        if self.kind == "road":
            return z + self._road_crossfall_component(px, py) + self._shoulder_component(px, py)

        if self.kind == "swale":
            return z + self._swale_component(px, py)

        if self.kind in {"pond", "basin"}:
            return self.base_elev + self._pond_component(px, py)

        return z

    def tie_weight_inside(self, px: float, py: float) -> float:
        if not self.contains(px, py):
            return 0.0

        tz = max(self.transition_zone, EPS)
        edge_dist = self.distance_to_edge(px, py)

        if self.tie_mode == "hold":
            return 1.0
        if edge_dist >= tz:
            return 1.0

        t = edge_dist / tz
        if self.tie_mode == "linear":
            return _clamp(t, 0.0, 1.0)
        return _smoothstep01(t)

    def tie_weight_outside(self, px: float, py: float) -> float:
        d = self.outside_distance_to_box(px, py)
        if d <= EPS:
            return 1.0
        tz = max(self.transition_zone, EPS)
        if d >= tz:
            return 0.0

        t = 1.0 - (d / tz)
        if self.tie_mode == "hold":
            return 0.0
        if self.tie_mode == "linear":
            return _clamp(t, 0.0, 1.0)
        return _smoothstep01(t)

    def influence_weight(self, px: float, py: float) -> float:
        if self.contains(px, py):
            return self.tie_weight_inside(px, py)
        if self.contains(px, py, include_transition=True):
            return self.tie_weight_outside(px, py)
        return 0.0

    def footprint_area(self) -> float:
        return max(self.width, 0.0) * max(self.depth, 0.0)

    def as_properties(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "depth": self.depth,
            "base_elev": self.base_elev,
            "slope_x": self.slope_x,
            "slope_y": self.slope_y,
            "edge_rise": self.edge_rise,
            "crown": self.crown,
            "side_slope": self.side_slope,
            "min_grade": self.min_grade,
            "max_grade": self.max_grade,
            "priority": self.priority,
            "transition_zone": self.transition_zone,
            "shoulder_width": self.shoulder_width,
            "tie_mode": self.tie_mode,
            "orientation": self.orientation,
            "name": self.name,
            "tags": list(self.tags),
            **self.meta,
        }


@dataclass
class GradingRequest:
    create_project_objects: bool = True
    create_project_zones: bool = True
    level: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    # direct checks / constraints
    min_site_slope: float = 0.002
    max_parking_slope: float = 0.05
    max_road_grade: float = 0.10
    max_walk_grade: float = 0.05

    # flow / sample settings
    flow_sample_step: int = 4
    spot_sample_step: int = 8
    low_point_min_spacing_ft: float = 10.0
    low_point_max_count: int = 50

    # optional coordination hints
    drainage_enabled: bool = True
    compute_earthwork: bool = True
    create_drainage_hints: bool = True


@dataclass
class GradeCheck:
    name: str
    passed: bool
    value: float
    threshold: Optional[float] = None
    message: str = ""


@dataclass
class FlowSample:
    x: float
    y: float
    z: float
    slope_x: float
    slope_y: float
    magnitude: float
    downhill_dx: float
    downhill_dy: float


@dataclass
class LowPointRecord:
    x: float
    y: float
    z: float
    row: int
    col: int
    local_basin_score: float = 0.0


@dataclass
class GradingResult:
    success: bool
    message: str = ""
    proposed_surface: Optional[GridSurface] = None
    object_ids: List[str] = field(default_factory=list)
    zone_ids: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checks: List[GradeCheck] = field(default_factory=list)
    cut_volume: float = 0.0
    fill_volume: float = 0.0
    net_volume: float = 0.0
    low_points: List[LowPointRecord] = field(default_factory=list)
    flow_samples: List[FlowSample] = field(default_factory=list)
    drainage_hints: Dict[str, Any] = field(default_factory=dict)
    explain: Dict[str, Any] = field(default_factory=dict)
    optimize_hooks: Dict[str, Any] = field(default_factory=dict)
    conflict_hooks: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# engine
# =============================================================================

class GradingEngine:
    """
    Proposed grading surface engine.

    Upgrades over the original version:
    - stronger interpolation of existing surface using bilinear sampling
    - real outside-of-footprint tie-ins, not just interior edge blending
    - richer grading primitives: swale / utility / plaza / sidewalk / basin support
    - improved roadway crown behavior with orientation control
    - more realistic pond bowls and swales
    - element validation and grading warnings
    - surface QA helpers for slope/drainage checks and cut/fill
    - stronger low-point and drainage-hint extraction
    - project-model registration hooks
    - planner-ready explain / optimize / conflict payloads
    """

    def __init__(self, existing_surface: GridSurface):
        self.existing_surface = existing_surface
        self.elements: List[GradeElement] = []
        self.project: Optional[ProjectModel] = None

    # =========================================================================
    # element management
    # =========================================================================

    def add_element(self, element: GradeElement) -> None:
        self.elements.append(element)
        self.elements.sort(key=lambda e: e.priority)

    def extend_elements(self, elements: Sequence[GradeElement]) -> None:
        for element in elements:
            self.add_element(element)

    def clear_elements(self) -> None:
        self.elements.clear()

    def attach_project(self, project: ProjectModel) -> None:
        self.project = project

    # =========================================================================
    # sampling / gradients
    # =========================================================================

    def surface_elevation_at(
        self,
        surface: GridSurface,
        x: float,
        y: float,
        method: str = "bilinear",
    ) -> float:
        if method == "nearest":
            row = round((y - surface.y_min) / surface.cell_size)
            col = round((x - surface.x_min) / surface.cell_size)
            row = max(0, min(surface.nrows - 1, row))
            col = max(0, min(surface.ncols - 1, col))
            return surface.values[row][col]

        col_f = (x - surface.x_min) / surface.cell_size
        row_f = (y - surface.y_min) / surface.cell_size

        r0 = int(math.floor(row_f))
        c0 = int(math.floor(col_f))
        r1 = r0 + 1
        c1 = c0 + 1

        r0c = max(0, min(surface.nrows - 1, r0))
        c0c = max(0, min(surface.ncols - 1, c0))
        r1c = max(0, min(surface.nrows - 1, r1))
        c1c = max(0, min(surface.ncols - 1, c1))

        z00 = surface.values[r0c][c0c]
        z10 = surface.values[r1c][c0c]
        z01 = surface.values[r0c][c1c]
        z11 = surface.values[r1c][c1c]

        tr = _clamp(row_f - r0, 0.0, 1.0)
        tc = _clamp(col_f - c0, 0.0, 1.0)

        z0 = z00 * (1.0 - tc) + z01 * tc
        z1 = z10 * (1.0 - tc) + z11 * tc
        return z0 * (1.0 - tr) + z1 * tr

    def surface_gradient_at(
        self,
        surface: GridSurface,
        x: float,
        y: float,
        delta: Optional[float] = None,
    ) -> Tuple[float, float]:
        d = delta or surface.cell_size
        d = max(d, surface.cell_size * 0.5, 0.25)

        x0 = max(surface.x_min, x - d)
        x1 = min(surface.x_max, x + d)
        y0 = max(surface.y_min, y - d)
        y1 = min(surface.y_max, y + d)

        zx0 = self.surface_elevation_at(surface, x0, y)
        zx1 = self.surface_elevation_at(surface, x1, y)
        zy0 = self.surface_elevation_at(surface, x, y0)
        zy1 = self.surface_elevation_at(surface, x, y1)

        gx = _safe_div(zx1 - zx0, x1 - x0, default=0.0)
        gy = _safe_div(zy1 - zy0, y1 - y0, default=0.0)
        return gx, gy

    def surface_flow_sample(
        self,
        surface: GridSurface,
        x: float,
        y: float,
    ) -> FlowSample:
        gx, gy = self.surface_gradient_at(surface, x, y)
        mag = math.hypot(gx, gy)
        z = self.surface_elevation_at(surface, x, y)

        if mag <= EPS:
            dx = 0.0
            dy = 0.0
        else:
            dx = -gx / mag
            dy = -gy / mag

        return FlowSample(
            x=x,
            y=y,
            z=z,
            slope_x=gx,
            slope_y=gy,
            magnitude=mag,
            downhill_dx=dx,
            downhill_dy=dy,
        )

    # =========================================================================
    # proposed surface generation
    # =========================================================================

    def _weighted_design_elevation(self, x: float, y: float) -> Tuple[Optional[float], float]:
        weighted_z = 0.0
        weighted_w = 0.0

        for element in self.elements:
            w = element.influence_weight(x, y)
            if w <= EPS:
                continue
            z = element.elevation_at(x, y)
            weighted_z += z * w
            weighted_w += w

        if weighted_w <= EPS:
            return None, 0.0
        return weighted_z / weighted_w, weighted_w

    def _blend_existing_and_design(self, existing_z: float, design_z: Optional[float], weight: float) -> float:
        if design_z is None or weight <= EPS:
            return existing_z

        if weight >= 1.0 - EPS:
            return design_z

        w = _clamp(weight, 0.0, 1.0)
        return existing_z * (1.0 - w) + design_z * w

    def build_proposed_surface(self) -> GridSurface:
        proposed = self.existing_surface.copy()

        for row in range(proposed.nrows):
            y = proposed.y_at(row)
            for col in range(proposed.ncols):
                x = proposed.x_at(col)
                existing_z = proposed.values[row][col]
                design_z, weight_sum = self._weighted_design_elevation(x, y)

                # convert potentially multiple influences into a 0..1 blend
                final_weight = _clamp(weight_sum, 0.0, 1.0)
                proposed.values[row][col] = self._blend_existing_and_design(existing_z, design_z, final_weight)

        return proposed

    # =========================================================================
    # checks / analysis
    # =========================================================================

    def _run_element_checks(self) -> List[GradeCheck]:
        checks: List[GradeCheck] = []

        for element in self.elements:
            for warning in element.validate():
                checks.append(
                    GradeCheck(
                        name=f"{element.label}_validation",
                        passed=False,
                        value=0.0,
                        threshold=None,
                        message=warning,
                    )
                )

        return checks

    def _sample_surface_flow_grid(self, surface: GridSurface, step: int = 4) -> List[FlowSample]:
        samples: List[FlowSample] = []
        step = max(1, int(step))

        for row in range(0, surface.nrows, step):
            for col in range(0, surface.ncols, step):
                x = surface.x_at(col)
                y = surface.y_at(row)
                samples.append(self.surface_flow_sample(surface, x, y))
        return samples

    def _find_low_points(
        self,
        surface: GridSurface,
        min_spacing_ft: float = 10.0,
        max_count: int = 50,
    ) -> List[LowPointRecord]:
        raw: List[LowPointRecord] = []

        for row in range(surface.nrows):
            for col in range(surface.ncols):
                z0 = surface.values[row][col]
                is_low = True
                lower_neighbors = 0

                for rr in range(max(0, row - 1), min(surface.nrows, row + 2)):
                    for cc in range(max(0, col - 1), min(surface.ncols, col + 2)):
                        if rr == row and cc == col:
                            continue
                        z1 = surface.values[rr][cc]
                        if z1 < z0 - EPS:
                            is_low = False
                        if z1 > z0 + EPS:
                            lower_neighbors += 1

                if not is_low:
                    continue

                x = surface.x_at(col)
                y = surface.y_at(row)
                raw.append(
                    LowPointRecord(
                        x=x,
                        y=y,
                        z=z0,
                        row=row,
                        col=col,
                        local_basin_score=float(lower_neighbors),
                    )
                )

        raw.sort(key=lambda lp: (lp.z, -lp.local_basin_score))

        selected: List[LowPointRecord] = []
        for lp in raw:
            if len(selected) >= max_count:
                break
            too_close = any(_distance(lp.x, lp.y, s.x, s.y) < min_spacing_ft for s in selected)
            if too_close:
                continue
            selected.append(lp)

        return selected

    def _surface_range(self, surface: GridSurface) -> Tuple[float, float]:
        min_z = float("inf")
        max_z = float("-inf")
        for row in surface.values:
            for z in row:
                min_z = min(min_z, float(z))
                max_z = max(max_z, float(z))
        return min_z, max_z

    def _compute_earthwork(self, proposed: GridSurface) -> Tuple[float, float, float]:
        cell_area = self.existing_surface.cell_size * self.existing_surface.cell_size
        cut_cf = 0.0
        fill_cf = 0.0

        for r in range(self.existing_surface.nrows):
            for c in range(self.existing_surface.ncols):
                dz = proposed.values[r][c] - self.existing_surface.values[r][c]
                vol = dz * cell_area
                if vol > 0.0:
                    fill_cf += vol
                elif vol < 0.0:
                    cut_cf += -vol

        net_cf = fill_cf - cut_cf
        return cut_cf, fill_cf, net_cf

    def _high_level_checks(
        self,
        surface: GridSurface,
        request: GradingRequest,
        flow_samples: Sequence[FlowSample],
    ) -> List[GradeCheck]:
        checks: List[GradeCheck] = []
        mags = [s.magnitude for s in flow_samples]
        min_mag = min(mags) if mags else 0.0
        avg_mag = sum(mags) / len(mags) if mags else 0.0

        checks.append(
            GradeCheck(
                name="min_site_slope",
                passed=min_mag + EPS >= request.min_site_slope,
                value=min_mag,
                threshold=request.min_site_slope,
                message=f"Minimum sampled site slope magnitude = {min_mag:.4f}",
            )
        )
        checks.append(
            GradeCheck(
                name="average_site_slope",
                passed=avg_mag > 0.0,
                value=avg_mag,
                threshold=None,
                message=f"Average sampled site slope magnitude = {avg_mag:.4f}",
            )
        )

        for element in self.elements:
            avg_grade = math.hypot(element.slope_x, element.slope_y)
            if element.kind == "parking":
                checks.append(
                    GradeCheck(
                        name=f"{element.label}_parking_slope",
                        passed=avg_grade <= request.max_parking_slope + EPS,
                        value=avg_grade,
                        threshold=request.max_parking_slope,
                        message=f"{element.label} parking planar grade = {avg_grade:.4f}",
                    )
                )
            elif element.kind == "road":
                checks.append(
                    GradeCheck(
                        name=f"{element.label}_road_grade",
                        passed=avg_grade <= request.max_road_grade + EPS,
                        value=avg_grade,
                        threshold=request.max_road_grade,
                        message=f"{element.label} road planar grade = {avg_grade:.4f}",
                    )
                )
            elif element.kind == "sidewalk":
                checks.append(
                    GradeCheck(
                        name=f"{element.label}_walk_grade",
                        passed=avg_grade <= request.max_walk_grade + EPS,
                        value=avg_grade,
                        threshold=request.max_walk_grade,
                        message=f"{element.label} sidewalk planar grade = {avg_grade:.4f}",
                    )
                )

        min_z, max_z = self._surface_range(surface)
        checks.append(
            GradeCheck(
                name="surface_range",
                passed=max_z >= min_z,
                value=max_z - min_z,
                threshold=0.0,
                message=f"Proposed surface elevation range = {(max_z - min_z):.3f}",
            )
        )

        return checks

    # =========================================================================
    # project-model hooks
    # =========================================================================

    def _register_into_project(
        self,
        project: ProjectModel,
        request: GradingRequest,
    ) -> Tuple[List[str], List[str]]:
        object_ids: List[str] = []
        zone_ids: List[str] = []

        for element in self.elements:
            if request.create_project_objects:
                obj = EngineeringObject(
                    kind=f"grading_{element.kind}",
                    name=element.name or element.label,
                    anchor=Point3D(element.center_x, element.center_y, element.base_elev),
                    tags=["grading", element.kind, *list(element.tags)],
                    domain=EngineeringDomain.SITE,
                    properties=element.as_properties(),
                    level=request.level,
                )
                object_ids.append(project.add_object(obj))

            if request.create_project_zones:
                zone_type = {
                    "pad": ZoneType.BUILDING_PAD,
                    "parking": ZoneType.PARKING,
                    "road": ZoneType.ROAD,
                    "pond": ZoneType.DETENTION,
                    "basin": ZoneType.DETENTION,
                    "swale": ZoneType.DRAINAGE,
                    "utility": ZoneType.UTILITY,
                    "plaza": ZoneType.OPEN_SPACE,
                    "sidewalk": ZoneType.CORRIDOR,
                }.get(element.kind, ZoneType.SITE)

                zone = rect_zone(
                    element.x,
                    element.y,
                    element.width,
                    element.depth,
                    zone_type=zone_type,
                    name=element.name or element.label,
                    level=request.level,
                    meta=element.as_properties(),
                )
                zone_ids.append(project.add_zone(zone))

        return object_ids, zone_ids

    # =========================================================================
    # explain / hooks
    # =========================================================================

    def _build_drainage_hints(
        self,
        low_points: Sequence[LowPointRecord],
        flow_samples: Sequence[FlowSample],
    ) -> Dict[str, Any]:
        return {
            "low_point_count": len(low_points),
            "low_points": [
                {
                    "name": f"LOW-{i+1}",
                    "x": lp.x,
                    "y": lp.y,
                    "z": lp.z,
                    "row": lp.row,
                    "col": lp.col,
                    "local_basin_score": lp.local_basin_score,
                }
                for i, lp in enumerate(low_points)
            ],
            "flow_samples": [
                {
                    "x": s.x,
                    "y": s.y,
                    "z": s.z,
                    "magnitude": s.magnitude,
                    "downhill_dx": s.downhill_dx,
                    "downhill_dy": s.downhill_dy,
                }
                for s in flow_samples[:200]
            ],
        }

    def _build_explain(
        self,
        proposed: GridSurface,
        checks: Sequence[GradeCheck],
        cut_volume: float,
        fill_volume: float,
        net_volume: float,
        low_points: Sequence[LowPointRecord],
    ) -> Dict[str, Any]:
        failed = [c for c in checks if not c.passed]
        return {
            "system_type": "grading",
            "element_count": len(self.elements),
            "key_logic": [
                "Existing surface was sampled using bilinear interpolation.",
                "Multiple grading elements were blended using inside/outside tie-in weights.",
                "Road crowns, swales, ponds, and pads were shaped with kind-specific surface behavior.",
                "Surface flow, low points, and earthwork were evaluated from the proposed surface.",
            ],
            "elements": [
                {
                    "name": e.name or e.label,
                    "kind": e.kind,
                    "priority": e.priority,
                    "base_elev": e.base_elev,
                    "planar_grade": round(math.hypot(e.slope_x, e.slope_y), 5),
                    "transition_zone": e.transition_zone,
                }
                for e in self.elements
            ],
            "failed_checks": [
                {
                    "name": c.name,
                    "value": c.value,
                    "threshold": c.threshold,
                    "message": c.message,
                }
                for c in failed[:25]
            ],
            "earthwork": {
                "cut_cf": round(cut_volume, 3),
                "fill_cf": round(fill_volume, 3),
                "net_cf": round(net_volume, 3),
            },
            "drainage_summary": {
                "low_point_count": len(low_points),
            },
        }

    def _build_optimize_hooks(
        self,
        checks: Sequence[GradeCheck],
        cut_volume: float,
        fill_volume: float,
        low_points: Sequence[LowPointRecord],
    ) -> Dict[str, Any]:
        failed_count = sum(1 for c in checks if not c.passed)
        imbalance = abs(fill_volume - cut_volume)
        return {
            "penalties": {
                "failed_check_penalty": failed_count * 10.0,
                "earthwork_balance_penalty": round(imbalance / 100.0, 3),
                "low_point_penalty": max(0, len(low_points) - 8) * 2.0,
            },
            "candidate_improvements": [
                "reduce isolated low points",
                "balance cut and fill more closely",
                "reduce parking and road slopes where they exceed targets",
                "tighten tie-ins around roads, pads, and ponds",
            ],
        }

    def _build_conflict_hooks(
        self,
        proposed: GridSurface,
        low_points: Sequence[LowPointRecord],
    ) -> Dict[str, Any]:
        return {
            "grading_elements": [
                {
                    "name": e.name or e.label,
                    "kind": e.kind,
                    "x": e.x,
                    "y": e.y,
                    "width": e.width,
                    "depth": e.depth,
                    "base_elev": e.base_elev,
                }
                for e in self.elements
            ],
            "grading_low_points": [
                {
                    "x": lp.x,
                    "y": lp.y,
                    "z": lp.z,
                    "name": f"LOW-{i+1}",
                }
                for i, lp in enumerate(low_points)
            ],
            "surface_shape": {
                "nrows": proposed.nrows,
                "ncols": proposed.ncols,
                "cell_size": proposed.cell_size,
            },
        }

    # =========================================================================
    # main public entrypoint
    # =========================================================================

    def build(
        self,
        request: Optional[GradingRequest] = None,
        project: Optional[ProjectModel] = None,
    ) -> GradingResult:
        request = request or GradingRequest()
        warnings: List[str] = []

        element_checks = self._run_element_checks()
        warnings.extend([c.message for c in element_checks if not c.passed])

        proposed = self.build_proposed_surface()
        flow_samples = self._sample_surface_flow_grid(proposed, step=request.flow_sample_step)
        low_points = self._find_low_points(
            proposed,
            min_spacing_ft=request.low_point_min_spacing_ft,
            max_count=request.low_point_max_count,
        )

        checks = list(element_checks) + self._high_level_checks(proposed, request, flow_samples)
        cut_volume, fill_volume, net_volume = (0.0, 0.0, 0.0)
        if request.compute_earthwork:
            cut_volume, fill_volume, net_volume = self._compute_earthwork(proposed)

        object_ids: List[str] = []
        zone_ids: List[str] = []
        active_project = project or self.project
        if active_project is not None:
            obj_ids, zn_ids = self._register_into_project(active_project, request)
            object_ids.extend(obj_ids)
            zone_ids.extend(zn_ids)

        drainage_hints = self._build_drainage_hints(low_points, flow_samples) if request.create_drainage_hints else {}
        explain = self._build_explain(proposed, checks, cut_volume, fill_volume, net_volume, low_points)
        optimize_hooks = self._build_optimize_hooks(checks, cut_volume, fill_volume, low_points)
        conflict_hooks = self._build_conflict_hooks(proposed, low_points)

        success = True
        message = "Proposed grading surface built."
        return GradingResult(
            success=success,
            message=message,
            proposed_surface=proposed,
            object_ids=object_ids,
            zone_ids=zone_ids,
            warnings=sorted(set(warnings)),
            checks=checks,
            cut_volume=cut_volume,
            fill_volume=fill_volume,
            net_volume=net_volume,
            low_points=low_points,
            flow_samples=flow_samples,
            drainage_hints=drainage_hints,
            explain=explain,
            optimize_hooks=optimize_hooks,
            conflict_hooks=conflict_hooks,
        )


def build_proposed_grading_surface(
    existing_surface: GridSurface,
    elements: Sequence[GradeElement],
    request: Optional[GradingRequest] = None,
    project: Optional[ProjectModel] = None,
) -> GradingResult:
    engine = GradingEngine(existing_surface)
    engine.extend_elements(elements)
    return engine.build(request=request, project=project)
