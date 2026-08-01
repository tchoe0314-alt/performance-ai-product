from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.geometry_core import (
    EngineeringObject,
    Point2D,
    Point3D,
    Polygon2D,
    ProjectModel,
    Zone,
    ZoneType,
)


@dataclass
class SubdivisionRequest:
    parcel_zone_id: Optional[str] = None

    road_width: float = 60.0
    lot_width: float = 80.0
    lot_depth: float = 140.0

    include_culdesac: bool = False
    culdesac_count: int = 0

    include_utility_corridors: bool = False
    include_detention_ponds: bool = False
    detention_pond_count: int = 0

    lot_name_prefix: str = "Lot"
    road_name: str = "Internal Road"

    layout_mode: str = "auto"  # auto | spine | grid | culdesac
    street_frontage_edge: str = "bottom"

    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SubdivisionResult:
    success: bool
    message: str = ""
    lot_ids: List[str] = field(default_factory=list)
    road_ids: List[str] = field(default_factory=list)
    object_ids: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class SubdivisionEngine:
    """
    Concept-stage residential subdivision engine.

    Supports:
    - spine-road layouts
    - simple grid road layouts
    - cul-de-sac variants
    - double-loaded loting
    - utility corridor placeholders
    - detention pond placeholders
    - road centerline objects

    Still concept-level, not final civil design.
    """

    def generate(
        self,
        project: ProjectModel,
        request: SubdivisionRequest,
    ) -> SubdivisionResult:
        parcel_zone = self._resolve_parcel(project, request)
        if parcel_zone is None:
            return SubdivisionResult(
                False,
                message=(
                    f"Parcel zone '{request.parcel_zone_id}' not found in project."
                    if request.parcel_zone_id
                    else "No parcel zone available in project."
                ),
            )

        request = self._normalize_request(request)

        bbox = parcel_zone.boundary.bbox
        x0, y0 = bbox.min_x, bbox.min_y
        x1, y1 = bbox.max_x, bbox.max_y
        parcel_width = x1 - x0
        parcel_depth = y1 - y0

        result = SubdivisionResult(success=True, message="Subdivision generated.")

        if parcel_width <= 0 or parcel_depth <= 0:
            return SubdivisionResult(False, message="Parcel zone has zero or negative dimensions.")

        if request.road_width <= 0 or request.lot_width <= 0 or request.lot_depth <= 0:
            return SubdivisionResult(False, message="road_width, lot_width, and lot_depth must all be positive.")

        layout_mode = self._choose_layout_mode(parcel_width, parcel_depth, request)

        if layout_mode == "grid":
            self._generate_grid_layout(project, parcel_zone, request, result)
        elif layout_mode == "culdesac":
            self._generate_culdesac_layout(project, parcel_zone, request, result)
        else:
            self._generate_spine_layout(project, parcel_zone, request, result)

        if request.include_utility_corridors:
            self._add_utility_corridors(project, parcel_zone, request, result)

        if request.include_detention_ponds:
            self._add_detention_ponds(project, parcel_zone, request, result)

        if not result.lot_ids:
            result.warnings.append(
                "No lots were generated. Check parcel dimensions against road_width, lot_width, and lot_depth."
            )

        return result

    # ------------------------------------------------------------------
    # Layout selection
    # ------------------------------------------------------------------

    def _normalize_request(self, request: SubdivisionRequest) -> SubdivisionRequest:
        layout_mode = str(request.layout_mode or "auto").strip().lower()
        if layout_mode not in {"auto", "spine", "grid", "culdesac"}:
            layout_mode = "auto"

        edge = str(request.street_frontage_edge or "bottom").strip().lower()
        if edge not in {"bottom", "top", "left", "right"}:
            edge = "bottom"

        culdesac_count = max(0, int(request.culdesac_count))
        detention_pond_count = max(0, int(request.detention_pond_count))

        if request.include_culdesac and culdesac_count <= 0:
            culdesac_count = 1

        if request.include_detention_ponds and detention_pond_count <= 0:
            detention_pond_count = 1

        return SubdivisionRequest(
            parcel_zone_id=request.parcel_zone_id,
            road_width=max(20.0, float(request.road_width)),
            lot_width=max(30.0, float(request.lot_width)),
            lot_depth=max(50.0, float(request.lot_depth)),
            include_culdesac=bool(request.include_culdesac),
            culdesac_count=culdesac_count,
            include_utility_corridors=bool(request.include_utility_corridors),
            include_detention_ponds=bool(request.include_detention_ponds),
            detention_pond_count=detention_pond_count,
            lot_name_prefix=request.lot_name_prefix,
            road_name=request.road_name,
            layout_mode=layout_mode,
            street_frontage_edge=edge,
            meta=dict(request.meta),
        )

    def _choose_layout_mode(
        self,
        parcel_width: float,
        parcel_depth: float,
        request: SubdivisionRequest,
    ) -> str:
        if request.layout_mode != "auto":
            return request.layout_mode

        if request.include_culdesac:
            return "culdesac"

        # crude heuristic:
        # deeper parcels like spine/courts, broader parcels can take grid
        if parcel_width >= 1.7 * parcel_depth:
            return "grid"
        return "spine"

    # ------------------------------------------------------------------
    # Main layout generators
    # ------------------------------------------------------------------

    def _generate_spine_layout(
        self,
        project: ProjectModel,
        parcel_zone: Zone,
        request: SubdivisionRequest,
        result: SubdivisionResult,
    ) -> None:
        bbox = parcel_zone.boundary.bbox
        x0, y0 = bbox.min_x, bbox.min_y
        x1, y1 = bbox.max_x, bbox.max_y
        w = x1 - x0
        h = y1 - y0

        rw = request.road_width

        road_rect = self._spine_road_rect(x0, y0, x1, y1, request.street_frontage_edge, rw)
        road_zone = self._add_road_zone(project, road_rect, f"{request.road_name} 1", request.meta)
        result.road_ids.append(road_zone.id)

        centerline_obj = self._make_road_centerline_object(road_rect, f"{request.road_name} 1 CL", request.meta)
        project.add_object(centerline_obj)
        result.object_ids.append(centerline_obj.id)

        lot_counter = 1

        if request.street_frontage_edge in {"bottom", "top"}:
            road_x = road_rect.boundary.bbox.min_x
            road_w = road_rect.boundary.bbox.width
            left_band = (x0, y0, road_x - x0, h)
            right_band = (road_x + road_w, y0, x1 - (road_x + road_w), h)

            lot_counter = self._fill_vertical_lot_band(
                project, request, result, left_band, lot_counter, lots_face="east"
            )
            lot_counter = self._fill_vertical_lot_band(
                project, request, result, right_band, lot_counter, lots_face="west"
            )

        else:
            road_y = road_rect.boundary.bbox.min_y
            road_h = road_rect.boundary.bbox.height
            bottom_band = (x0, y0, w, road_y - y0)
            top_band = (x0, road_y + road_h, w, y1 - (road_y + road_h))

            lot_counter = self._fill_horizontal_lot_band(
                project, request, result, bottom_band, lot_counter, lots_face="north"
            )
            lot_counter = self._fill_horizontal_lot_band(
                project, request, result, top_band, lot_counter, lots_face="south"
            )

    def _generate_grid_layout(
        self,
        project: ProjectModel,
        parcel_zone: Zone,
        request: SubdivisionRequest,
        result: SubdivisionResult,
    ) -> None:
        bbox = parcel_zone.boundary.bbox
        x0, y0 = bbox.min_x, bbox.min_y
        x1, y1 = bbox.max_x, bbox.max_y
        rw = request.road_width
        ld = request.lot_depth

        main_road = self._spine_road_rect(x0, y0, x1, y1, request.street_frontage_edge, rw)
        road_zone = self._add_road_zone(project, main_road, f"{request.road_name} 1", request.meta)
        result.road_ids.append(road_zone.id)
        centerline_obj = self._make_road_centerline_object(main_road, f"{request.road_name} 1 CL", request.meta)
        project.add_object(centerline_obj)
        result.object_ids.append(centerline_obj.id)

        cross_roads = self._grid_cross_roads(x0, y0, x1, y1, main_road.boundary.bbox, rw, ld)
        for i, rect in enumerate(cross_roads, start=2):
            rz = self._add_road_zone(project, rect, f"{request.road_name} {i}", request.meta)
            result.road_ids.append(rz.id)
            cl = self._make_road_centerline_object(rect, f"{request.road_name} {i} CL", request.meta)
            project.add_object(cl)
            result.object_ids.append(cl.id)

        occupied = [z.boundary.bbox for z in project.zones.values() if z.zone_type == ZoneType.ROAD]
        lot_counter = 1
        lot_counter = self._fill_grid_blocks(project, parcel_zone, request, result, occupied, lot_counter)

    def _generate_culdesac_layout(
        self,
        project: ProjectModel,
        parcel_zone: Zone,
        request: SubdivisionRequest,
        result: SubdivisionResult,
    ) -> None:
        bbox = parcel_zone.boundary.bbox
        x0, y0 = bbox.min_x, bbox.min_y
        x1, y1 = bbox.max_x, bbox.max_y
        rw = request.road_width

        main_road = self._spine_road_rect(x0, y0, x1, y1, request.street_frontage_edge, rw)
        road_zone = self._add_road_zone(project, main_road, f"{request.road_name} 1", request.meta)
        result.road_ids.append(road_zone.id)

        centerline_obj = self._make_road_centerline_object(main_road, f"{request.road_name} 1 CL", request.meta)
        project.add_object(centerline_obj)
        result.object_ids.append(centerline_obj.id)

        court_centers = self._culdesac_centers(main_road.boundary.bbox, request.street_frontage_edge, request.culdesac_count)

        for i, (cx, cy) in enumerate(court_centers, start=1):
            cul_obj = self._make_culdesac_object(
                cx=cx,
                cy=cy,
                radius=rw / 2.0,
                name=f"Cul-de-sac {i}",
                meta=request.meta,
            )
            project.add_object(cul_obj)
            result.object_ids.append(cul_obj.id)

        lot_counter = 1
        occupied = [z.boundary.bbox for z in project.zones.values() if z.zone_type == ZoneType.ROAD]
        lot_counter = self._fill_grid_blocks(project, parcel_zone, request, result, occupied, lot_counter)

    # ------------------------------------------------------------------
    # Road helpers
    # ------------------------------------------------------------------

    def _spine_road_rect(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        frontage_edge: str,
        road_width: float,
    ) -> Zone:
        width = x1 - x0
        height = y1 - y0

        if frontage_edge in {"bottom", "top"}:
            rx = x0 + width * 0.42
            rw = road_width
            return Zone(
                boundary=Polygon2D([
                    Point2D(rx, y0),
                    Point2D(rx + rw, y0),
                    Point2D(rx + rw, y1),
                    Point2D(rx, y1),
                ]),
                zone_type=ZoneType.ROAD,
                name=None,
                tags=["subdivision", "internal_road"],
            )

        ry = y0 + height * 0.42
        rh = road_width
        return Zone(
            boundary=Polygon2D([
                Point2D(x0, ry),
                Point2D(x1, ry),
                Point2D(x1, ry + rh),
                Point2D(x0, ry + rh),
            ]),
            zone_type=ZoneType.ROAD,
            name=None,
            tags=["subdivision", "internal_road"],
        )

    def _grid_cross_roads(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        main_road_bbox,
        road_width: float,
        lot_depth: float,
    ) -> List[Zone]:
        roads: List[Zone] = []

        if main_road_bbox.height > main_road_bbox.width:
            usable_height = y1 - y0
            spacing = max(road_width + 2.0 * lot_depth, lot_depth * 1.8)
            n = int(usable_height // spacing)
            for i in range(1, max(1, n)):
                cy = y0 + i * spacing
                if cy + road_width > y1:
                    continue
                roads.append(
                    Zone(
                        boundary=Polygon2D([
                            Point2D(x0, cy),
                            Point2D(x1, cy),
                            Point2D(x1, cy + road_width),
                            Point2D(x0, cy + road_width),
                        ]),
                        zone_type=ZoneType.ROAD,
                        tags=["subdivision", "cross_road"],
                    )
                )
        else:
            usable_width = x1 - x0
            spacing = max(road_width + 2.0 * lot_depth, lot_depth * 1.8)
            n = int(usable_width // spacing)
            for i in range(1, max(1, n)):
                cx = x0 + i * spacing
                if cx + road_width > x1:
                    continue
                roads.append(
                    Zone(
                        boundary=Polygon2D([
                            Point2D(cx, y0),
                            Point2D(cx + road_width, y0),
                            Point2D(cx + road_width, y1),
                            Point2D(cx, y1),
                        ]),
                        zone_type=ZoneType.ROAD,
                        tags=["subdivision", "cross_road"],
                    )
                )

        return roads

    def _add_road_zone(
        self,
        project: ProjectModel,
        road_zone: Zone,
        name: str,
        meta: Dict[str, Any],
    ) -> Zone:
        road_zone.name = name
        road_zone.meta = {"source": "subdivision_engine", **meta}
        project.add_zone(road_zone)
        return road_zone

    def _make_road_centerline_object(
        self,
        road_zone: Zone,
        name: str,
        meta: Dict[str, Any],
    ) -> EngineeringObject:
        bb = road_zone.boundary.bbox
        if bb.height > bb.width:
            pts = [Point2D(bb.center.x, bb.min_y), Point2D(bb.center.x, bb.max_y)]
        else:
            pts = [Point2D(bb.min_x, bb.center.y), Point2D(bb.max_x, bb.center.y)]

        return EngineeringObject(
            kind="road_centerline",
            anchor=Point3D(bb.center.x, bb.center.y, 0.0),
            name=name,
            tags=["subdivision", "road_centerline"],
            properties={
                "source": "subdivision_engine",
                "geometry": [(p.x, p.y) for p in pts],
                **meta,
            },
        )

    # ------------------------------------------------------------------
    # Lot filling helpers
    # ------------------------------------------------------------------

    def _fill_vertical_lot_band(
        self,
        project: ProjectModel,
        request: SubdivisionRequest,
        result: SubdivisionResult,
        band: Tuple[float, float, float, float],
        lot_counter: int,
        lots_face: str,
    ) -> int:
        bx, by, bw, bh = band
        lw = request.lot_width
        ld = request.lot_depth

        if bw < ld or bh < lw:
            result.warnings.append("Vertical lot band too small to generate lots.")
            return lot_counter

        n = int(bh // lw)
        lot_depth = min(ld, bw)

        for i in range(n):
            ly0 = by + i * lw
            ly1 = ly0 + lw
            if ly1 > by + bh + 1e-6:
                break

            if lots_face == "east":
                lx0 = bx + bw - lot_depth
            else:
                lx0 = bx
            lx1 = lx0 + lot_depth

            lot_poly = Polygon2D([
                Point2D(lx0, ly0),
                Point2D(lx1, ly0),
                Point2D(lx1, ly1),
                Point2D(lx0, ly1),
            ])
            lot_zone = Zone(
                boundary=lot_poly,
                zone_type=ZoneType.PARCEL,
                name=f"{request.lot_name_prefix} {lot_counter}",
                tags=["subdivision", "lot"],
                meta={
                    "source": "subdivision_engine",
                    "frontage_direction": lots_face,
                    **request.meta,
                },
            )
            project.add_zone(lot_zone)
            result.lot_ids.append(lot_zone.id)
            lot_counter += 1

        return lot_counter

    def _fill_horizontal_lot_band(
        self,
        project: ProjectModel,
        request: SubdivisionRequest,
        result: SubdivisionResult,
        band: Tuple[float, float, float, float],
        lot_counter: int,
        lots_face: str,
    ) -> int:
        bx, by, bw, bh = band
        lw = request.lot_width
        ld = request.lot_depth

        if bh < ld or bw < lw:
            result.warnings.append("Horizontal lot band too small to generate lots.")
            return lot_counter

        n = int(bw // lw)
        lot_depth = min(ld, bh)

        for i in range(n):
            lx0 = bx + i * lw
            lx1 = lx0 + lw
            if lx1 > bx + bw + 1e-6:
                break

            if lots_face == "north":
                ly0 = by + bh - lot_depth
            else:
                ly0 = by
            ly1 = ly0 + lot_depth

            lot_poly = Polygon2D([
                Point2D(lx0, ly0),
                Point2D(lx1, ly0),
                Point2D(lx1, ly1),
                Point2D(lx0, ly1),
            ])
            lot_zone = Zone(
                boundary=lot_poly,
                zone_type=ZoneType.PARCEL,
                name=f"{request.lot_name_prefix} {lot_counter}",
                tags=["subdivision", "lot"],
                meta={
                    "source": "subdivision_engine",
                    "frontage_direction": lots_face,
                    **request.meta,
                },
            )
            project.add_zone(lot_zone)
            result.lot_ids.append(lot_zone.id)
            lot_counter += 1

        return lot_counter

    def _fill_grid_blocks(
        self,
        project: ProjectModel,
        parcel_zone: Zone,
        request: SubdivisionRequest,
        result: SubdivisionResult,
        occupied_boxes: List[Any],
        lot_counter: int,
    ) -> int:
        bbox = parcel_zone.boundary.bbox
        x0, y0 = bbox.min_x, bbox.min_y
        x1, y1 = bbox.max_x, bbox.max_y

        lw = request.lot_width
        ld = request.lot_depth

        x = x0
        while x + lw <= x1 + 1e-6:
            y = y0
            while y + ld <= y1 + 1e-6:
                lot_bb = (x, y, x + lw, y + ld)
                if not self._intersects_any(lot_bb, occupied_boxes):
                    lot_poly = Polygon2D([
                        Point2D(x, y),
                        Point2D(x + lw, y),
                        Point2D(x + lw, y + ld),
                        Point2D(x, y + ld),
                    ])
                    lot_zone = Zone(
                        boundary=lot_poly,
                        zone_type=ZoneType.PARCEL,
                        name=f"{request.lot_name_prefix} {lot_counter}",
                        tags=["subdivision", "lot"],
                        meta={"source": "subdivision_engine", **request.meta},
                    )
                    project.add_zone(lot_zone)
                    result.lot_ids.append(lot_zone.id)
                    lot_counter += 1
                y += ld
            x += lw

        return lot_counter

    def _intersects_any(self, bb: Tuple[float, float, float, float], occupied_boxes: List[Any]) -> bool:
        min_x, min_y, max_x, max_y = bb
        for ob in occupied_boxes:
            if not (
                max_x <= ob.min_x
                or min_x >= ob.max_x
                or max_y <= ob.min_y
                or min_y >= ob.max_y
            ):
                return True
        return False

    # ------------------------------------------------------------------
    # Cul-de-sac helpers
    # ------------------------------------------------------------------

    def _culdesac_centers(
        self,
        road_bbox,
        frontage_edge: str,
        count: int,
    ) -> List[Tuple[float, float]]:
        count = max(1, count)
        centers: List[Tuple[float, float]] = []

        if road_bbox.height > road_bbox.width:
            ys = self._distributed_values(road_bbox.min_y, road_bbox.max_y, count)
            side_x = road_bbox.center.x
            for cy in ys:
                centers.append((side_x, cy))
        else:
            xs = self._distributed_values(road_bbox.min_x, road_bbox.max_x, count)
            side_y = road_bbox.center.y
            for cx in xs:
                centers.append((cx, side_y))

        return centers

    def _distributed_values(self, start: float, end: float, count: int) -> List[float]:
        if count <= 1:
            return [(start + end) / 2.0]
        span = end - start
        return [start + span * (i + 1) / (count + 1) for i in range(count)]

    def _make_culdesac_object(
        self,
        cx: float,
        cy: float,
        radius: float,
        name: str,
        meta: Dict[str, Any],
    ) -> EngineeringObject:
        sides = 20
        pts = [
            Point2D(
                cx + radius * math.cos(2 * math.pi * i / sides),
                cy + radius * math.sin(2 * math.pi * i / sides),
            )
            for i in range(sides)
        ]
        return EngineeringObject(
            kind="culdesac",
            anchor=Point3D(cx, cy, 0.0),
            name=name,
            boundary=Polygon2D(pts),
            tags=["subdivision", "culdesac"],
            properties={"radius": radius, "source": "subdivision_engine", **meta},
        )

    # ------------------------------------------------------------------
    # Utility / pond placeholders
    # ------------------------------------------------------------------

    def _add_utility_corridors(
        self,
        project: ProjectModel,
        parcel_zone: Zone,
        request: SubdivisionRequest,
        result: SubdivisionResult,
    ) -> None:
        bbox = parcel_zone.boundary.bbox
        width = max(12.0, request.road_width * 0.25)

        corridor = Zone(
            boundary=Polygon2D([
                Point2D(bbox.min_x, bbox.max_y - width),
                Point2D(bbox.max_x, bbox.max_y - width),
                Point2D(bbox.max_x, bbox.max_y),
                Point2D(bbox.min_x, bbox.max_y),
            ]),
            zone_type=ZoneType.UTILITY,
            name="Utility Corridor",
            tags=["subdivision", "utility_corridor"],
            meta={"source": "subdivision_engine", **request.meta},
        )
        project.add_zone(corridor)
        result.object_ids.append(corridor.id)

        util_obj = EngineeringObject(
            kind="utility_corridor",
            anchor=Point3D(corridor.boundary.bbox.center.x, corridor.boundary.bbox.center.y, 0.0),
            name="Utility Corridor",
            boundary=corridor.boundary,
            tags=["subdivision", "utility_corridor"],
            properties={"source": "subdivision_engine", **request.meta},
        )
        project.add_object(util_obj)
        result.object_ids.append(util_obj.id)

    def _add_detention_ponds(
        self,
        project: ProjectModel,
        parcel_zone: Zone,
        request: SubdivisionRequest,
        result: SubdivisionResult,
    ) -> None:
        bbox = parcel_zone.boundary.bbox
        pond_count = max(1, request.detention_pond_count)

        pond_w = max(50.0, (bbox.width * 0.16))
        pond_h = max(40.0, (bbox.height * 0.12))

        for i in range(pond_count):
            px = bbox.min_x + 10.0 + i * (pond_w + 12.0)
            py = bbox.min_y + 10.0

            if px + pond_w > bbox.max_x:
                px = bbox.max_x - pond_w - 10.0

            poly = Polygon2D([
                Point2D(px + pond_w * 0.10, py),
                Point2D(px + pond_w * 0.90, py),
                Point2D(px + pond_w, py + pond_h * 0.45),
                Point2D(px + pond_w * 0.80, py + pond_h),
                Point2D(px + pond_w * 0.20, py + pond_h),
                Point2D(px, py + pond_h * 0.45),
            ])

            pond_zone = Zone(
                boundary=poly,
                zone_type=ZoneType.DRAINAGE,
                name=f"Detention Pond {i + 1}",
                tags=["subdivision", "detention_pond"],
                meta={"source": "subdivision_engine", **request.meta},
            )
            project.add_zone(pond_zone)
            result.object_ids.append(pond_zone.id)

            pond_obj = EngineeringObject(
                kind="detention_pond",
                anchor=Point3D(poly.centroid().x, poly.centroid().y, 0.0),
                name=f"Detention Pond {i + 1}",
                boundary=poly,
                tags=["subdivision", "detention_pond"],
                properties={"source": "subdivision_engine", **request.meta},
            )
            project.add_object(pond_obj)
            result.object_ids.append(pond_obj.id)

    # ------------------------------------------------------------------
    # Parcel resolution
    # ------------------------------------------------------------------

    def _resolve_parcel(
        self,
        project: ProjectModel,
        request: SubdivisionRequest,
    ) -> Optional[Zone]:
        if request.parcel_zone_id:
            zone = project.zones.get(request.parcel_zone_id)
            if zone is not None:
                return zone

        candidates = [
            zone for zone in project.zones.values()
            if zone.zone_type in (ZoneType.SITE, ZoneType.PARCEL)
        ]
        if not candidates:
            return None

        candidates.sort(key=lambda z: z.boundary.area, reverse=True)
        return candidates[0]
