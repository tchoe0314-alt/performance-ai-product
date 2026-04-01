from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.geometry_core import (
    EngineeringObject,
    Point2D,
    Point3D,
    Polygon2D,
    Polyline2D,
    ProjectModel,
    Zone,
    ZoneType,
    rect_zone,
)


@dataclass
class StructuralGridRequest:
    building_zone_id: Optional[str] = None
    spacing_x: float = 25.0
    spacing_y: float = 25.0
    edge_offset_x: float = 0.0
    edge_offset_y: float = 0.0
    level: Optional[str] = None
    create_grid_lines: bool = True
    create_columns: bool = True
    create_beams: bool = True
    create_bay_objects: bool = True
    grid_prefix_x: str = "A"
    grid_prefix_y: str = "1"
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StructuralResult:
    success: bool
    message: str = ""
    object_ids: List[str] = field(default_factory=list)
    zone_ids: List[str] = field(default_factory=list)
    grid_line_count: int = 0
    column_count: int = 0
    beam_count: int = 0
    bay_count: int = 0
    warnings: List[str] = field(default_factory=list)


class StructureEngine:
    """
    Early-stage structural layout engine.

    Current version supports:
    - finding a building zone
    - generating an orthogonal structural grid
    - placing columns at grid intersections
    - creating beam centerlines between adjacent columns
    - creating structural bay objects

    This is a concept/foundation engine, not a full structural analysis package.
    """

    def generate_grid(
        self,
        project: ProjectModel,
        request: StructuralGridRequest,
    ) -> StructuralResult:
        building = self._resolve_building_zone(project, request.building_zone_id)
        if building is None:
            return StructuralResult(False, message="No building zone found for structural layout.")

        bbox = building.boundary.bbox
        min_x = bbox.min_x + request.edge_offset_x
        max_x = bbox.max_x - request.edge_offset_x
        min_y = bbox.min_y + request.edge_offset_y
        max_y = bbox.max_y - request.edge_offset_y

        if max_x <= min_x or max_y <= min_y:
            return StructuralResult(False, message="Edge offsets eliminate usable structural layout area.")

        x_coords = self._axis_coords(min_x, max_x, request.spacing_x)
        y_coords = self._axis_coords(min_y, max_y, request.spacing_y)

        if len(x_coords) < 2 or len(y_coords) < 2:
            return StructuralResult(False, message="Not enough grid lines fit within the building zone.")

        result = StructuralResult(success=True, message="Structural grid generated.")

        x_labels = self._make_alpha_labels(len(x_coords), request.grid_prefix_x)
        y_labels = self._make_numeric_labels(len(y_coords), request.grid_prefix_y)

        column_lookup: Dict[Tuple[int, int], str] = {}
        column_points: Dict[Tuple[int, int], Point2D] = {}

        if request.create_grid_lines:
            for i, x in enumerate(x_coords):
                line_obj = EngineeringObject(
                    kind="grid_line_x",
                    anchor=Point3D(x, (min_y + max_y) / 2.0, 0.0),
                    name=f"{x_labels[i]}",
                    level=request.level,
                    tags=["structure", "grid", "x"],
                    properties={
                        "orientation": "vertical",
                        "x": x,
                        "y_min": min_y,
                        "y_max": max_y,
                        "source": "structure_engine",
                        **request.meta,
                    },
                )
                project.add_object(line_obj)
                result.object_ids.append(line_obj.id)
                result.grid_line_count += 1

            for j, y in enumerate(y_coords):
                line_obj = EngineeringObject(
                    kind="grid_line_y",
                    anchor=Point3D((min_x + max_x) / 2.0, y, 0.0),
                    name=f"{y_labels[j]}",
                    level=request.level,
                    tags=["structure", "grid", "y"],
                    properties={
                        "orientation": "horizontal",
                        "y": y,
                        "x_min": min_x,
                        "x_max": max_x,
                        "source": "structure_engine",
                        **request.meta,
                    },
                )
                project.add_object(line_obj)
                result.object_ids.append(line_obj.id)
                result.grid_line_count += 1

        if request.create_columns:
            for i, x in enumerate(x_coords):
                for j, y in enumerate(y_coords):
                    name = f"C-{x_labels[i]}{y_labels[j]}"
                    col = EngineeringObject(
                        kind="column",
                        anchor=Point3D(x, y, 0.0),
                        name=name,
                        level=request.level,
                        tags=["structure", "column"],
                        properties={
                            "grid_x": x_labels[i],
                            "grid_y": y_labels[j],
                            "source": "structure_engine",
                            **request.meta,
                        },
                    )
                    project.add_object(col)
                    result.object_ids.append(col.id)
                    result.column_count += 1
                    column_lookup[(i, j)] = col.id
                    column_points[(i, j)] = Point2D(x, y)

        if request.create_beams:
            # Horizontal beams
            for j in range(len(y_coords)):
                for i in range(len(x_coords) - 1):
                    p1 = column_points[(i, j)]
                    p2 = column_points[(i + 1, j)]
                    beam = EngineeringObject(
                        kind="beam",
                        anchor=Point3D((p1.x + p2.x) / 2.0, (p1.y + p2.y) / 2.0, 0.0),
                        name=f"B-{x_labels[i]}{y_labels[j]}-{x_labels[i + 1]}{y_labels[j]}",
                        level=request.level,
                        tags=["structure", "beam", "horizontal"],
                        properties={
                            "start": (p1.x, p1.y),
                            "end": (p2.x, p2.y),
                            "orientation": "horizontal",
                            "source": "structure_engine",
                            **request.meta,
                        },
                    )
                    project.add_object(beam)
                    result.object_ids.append(beam.id)
                    result.beam_count += 1

            # Vertical beams
            for i in range(len(x_coords)):
                for j in range(len(y_coords) - 1):
                    p1 = column_points[(i, j)]
                    p2 = column_points[(i, j + 1)]
                    beam = EngineeringObject(
                        kind="beam",
                        anchor=Point3D((p1.x + p2.x) / 2.0, (p1.y + p2.y) / 2.0, 0.0),
                        name=f"B-{x_labels[i]}{y_labels[j]}-{x_labels[i]}{y_labels[j + 1]}",
                        level=request.level,
                        tags=["structure", "beam", "vertical"],
                        properties={
                            "start": (p1.x, p1.y),
                            "end": (p2.x, p2.y),
                            "orientation": "vertical",
                            "source": "structure_engine",
                            **request.meta,
                        },
                    )
                    project.add_object(beam)
                    result.object_ids.append(beam.id)
                    result.beam_count += 1

        if request.create_bay_objects:
            for i in range(len(x_coords) - 1):
                for j in range(len(y_coords) - 1):
                    x1 = x_coords[i]
                    x2 = x_coords[i + 1]
                    y1 = y_coords[j]
                    y2 = y_coords[j + 1]
                    bay_zone = rect_zone(
                        x=x1,
                        y=y1,
                        width=x2 - x1,
                        height=y2 - y1,
                        zone_type=ZoneType.STRUCTURE,
                        name=f"Bay {x_labels[i]}{y_labels[j]}-{x_labels[i + 1]}{y_labels[j + 1]}",
                        level=request.level,
                        tags=["structure", "bay"],
                    )
                    project.add_zone(bay_zone)
                    result.zone_ids.append(bay_zone.id)
                    result.bay_count += 1

        max_span_x = max(x_coords[i + 1] - x_coords[i] for i in range(len(x_coords) - 1))
        max_span_y = max(y_coords[j + 1] - y_coords[j] for j in range(len(y_coords) - 1))
        if max_span_x > 40.0 or max_span_y > 40.0:
            result.warnings.append("Some structural bays exceed 40 units; verify framing feasibility.")

        return result

    def _resolve_building_zone(
        self,
        project: ProjectModel,
        building_zone_id: Optional[str],
    ) -> Optional[Zone]:
        if building_zone_id:
            zone = project.zones.get(building_zone_id)
            if zone and zone.zone_type in {ZoneType.BUILDING, ZoneType.FLOOR, ZoneType.ROOM}:
                return zone

        candidates = [
            z for z in project.zones.values()
            if z.zone_type in {ZoneType.BUILDING, ZoneType.FLOOR}
        ]
        if not candidates:
            return None

        candidates.sort(key=lambda z: z.boundary.area, reverse=True)
        return candidates[0]

    def _axis_coords(self, start: float, end: float, spacing: float) -> List[float]:
        coords: List[float] = []
        if spacing <= 0:
            return coords

        cur = start
        while cur <= end + 1e-9:
            coords.append(round(cur, 6))
            cur += spacing

        if abs(coords[-1] - end) > 1e-6:
            coords.append(round(end, 6))

        return sorted(set(coords))

    def _make_alpha_labels(self, count: int, prefix: str) -> List[str]:
        labels: List[str] = []
        use_prefix = prefix.strip() if prefix else ""
        if use_prefix and len(use_prefix) == 1 and use_prefix.isalpha():
            start_ord = ord(use_prefix.upper())
            for i in range(count):
                labels.append(chr(start_ord + i))
            return labels

        # Excel-like fallback
        for i in range(count):
            labels.append(self._alpha_index(i))
        return labels

    def _alpha_index(self, index: int) -> str:
        s = ""
        idx = index
        while True:
            idx, rem = divmod(idx, 26)
            s = chr(ord("A") + rem) + s
            if idx == 0:
                break
            idx -= 1
        return s

    def _make_numeric_labels(self, count: int, prefix: str) -> List[str]:
        start = 1
        if prefix.strip().isdigit():
            start = int(prefix.strip())
        return [str(start + i) for i in range(count)]


def generate_structural_grid(
    project: ProjectModel,
    request: StructuralGridRequest,
) -> StructuralResult:
    return StructureEngine().generate_grid(project, request)