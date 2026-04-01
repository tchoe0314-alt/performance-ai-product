from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.geometry_core import (
    EngineeringObject,
    Point3D,
    ProjectModel,
    Zone,
    ZoneType,
    rect_zone,
)


@dataclass
class BuildingRequest:
    site_zone_id: Optional[str] = None

    building_width: float = 120.0
    building_depth: float = 80.0

    front_setback: float = 25.0
    side_setback: float = 10.0
    rear_setback: float = 20.0

    floor_count: int = 1
    floor_height: float = 12.0

    create_building_zone: bool = True
    create_floor_zones: bool = True
    create_core_zone: bool = True
    create_room_placeholders: bool = False
    create_entry_object: bool = True
    create_pad_object: bool = True
    create_vertical_circulation: bool = True
    create_program_zones: bool = True

    core_width: float = 24.0
    core_depth: float = 20.0

    anchor_mode: str = "centered_front_setback"  # centered_front_setback | centered | southwest
    frontage_edge: str = "bottom"  # bottom | top | left | right
    building_name: str = "Building A"
    building_use: str = "generic"  # generic | office | multifamily | retail | industrial
    footprint_type: str = "bar"    # bar | slab | compact | l_shape | u_shape | courtyard | h_shape
    level: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BuildingResult:
    success: bool
    message: str = ""
    zone_ids: List[str] = field(default_factory=list)
    object_ids: List[str] = field(default_factory=list)
    floor_count: int = 0
    warnings: List[str] = field(default_factory=list)


class BuildingEngine:
    """
    Concept-stage building generator.

    Supports:
    - frontage-aware siting inside setbacks
    - multiple footprint types
    - repeated floor zones
    - multiple cores for larger buildings
    - stairs and elevator placeholder objects
    - entry objects
    - program zones by building type
    - multifamily corridor + unit band placeholders
    - office lobby / office / service placeholders
    - retail shell / back-of-house placeholders
    - industrial warehouse / office / service split
    """

    VALID_FRONTAGE_EDGES = {"bottom", "top", "left", "right"}
    VALID_ANCHOR_MODES = {"centered_front_setback", "centered", "southwest"}

    def generate(
        self,
        project: ProjectModel,
        request: BuildingRequest,
    ) -> BuildingResult:
        site = self._resolve_site_zone(project, request.site_zone_id)
        if site is None:
            return BuildingResult(False, message="No site zone found for building generation.")

        request = self._normalized_request(request)
        site_bbox = site.boundary.bbox

        buildable = self._buildable_rect(
            min_x=site_bbox.min_x,
            min_y=site_bbox.min_y,
            max_x=site_bbox.max_x,
            max_y=site_bbox.max_y,
            front_setback=request.front_setback,
            side_setback=request.side_setback,
            rear_setback=request.rear_setback,
            frontage_edge=request.frontage_edge,
        )

        buildable_w = buildable["max_x"] - buildable["min_x"]
        buildable_h = buildable["max_y"] - buildable["min_y"]

        if buildable_w <= 0 or buildable_h <= 0:
            return BuildingResult(False, message="Setbacks leave no valid buildable area.")

        if request.building_width > buildable_w or request.building_depth > buildable_h:
            return BuildingResult(
                False,
                message="Requested building footprint does not fit inside site setbacks.",
            )

        bx, by = self._place_building_origin(buildable, request)

        result = BuildingResult(
            success=True,
            message="Building layout generated.",
            floor_count=request.floor_count,
        )

        footprint_rects = self._make_footprint_rects(
            x=bx,
            y=by,
            width=request.building_width,
            depth=request.building_depth,
            footprint_type=request.footprint_type,
        )

        primary_building_zone = self._add_building_footprint_zones(
            project=project,
            request=request,
            footprint_rects=footprint_rects,
            result=result,
        )

        if primary_building_zone is None:
            return BuildingResult(False, message="Could not create primary building footprint.")

        building_obj = EngineeringObject(
            kind="building",
            anchor=Point3D(
                primary_building_zone.boundary.bbox.center.x,
                primary_building_zone.boundary.bbox.center.y,
                0.0,
            ),
            name=request.building_name,
            level=request.level,
            boundary=primary_building_zone.boundary,
            tags=["building", request.building_use, request.footprint_type],
            properties={
                "floor_count": request.floor_count,
                "floor_height": request.floor_height,
                "frontage_edge": request.frontage_edge,
                "anchor_mode": request.anchor_mode,
                "building_use": request.building_use,
                "footprint_type": request.footprint_type,
                "footprint_piece_count": len(footprint_rects),
                "source": "building_engine",
                **request.meta,
            },
        )
        project.add_object(building_obj)
        result.object_ids.append(building_obj.id)

        if request.create_pad_object:
            pad_obj = self._create_building_pad_object(primary_building_zone, request)
            project.add_object(pad_obj)
            result.object_ids.append(pad_obj.id)

        floor_zone_ids = self._create_floor_zones(project, primary_building_zone, request)
        result.zone_ids.extend(floor_zone_ids)

        core_zone_ids, core_centers = self._create_core_zones(project, primary_building_zone, request)
        result.zone_ids.extend(core_zone_ids)

        if request.create_vertical_circulation:
            circulation_ids = self._create_vertical_circulation_objects(project, request, core_centers)
            result.object_ids.extend(circulation_ids)

        if request.create_program_zones:
            program_zone_ids = self._create_program_zones(project, primary_building_zone, request, core_centers)
            result.zone_ids.extend(program_zone_ids)

        if request.create_room_placeholders:
            room_zone_ids = self._create_room_placeholders(project, primary_building_zone, request)
            result.zone_ids.extend(room_zone_ids)

        if request.create_entry_object:
            entry_ids = self._create_entry_objects(project, primary_building_zone, request)
            result.object_ids.extend(entry_ids)

        self._append_warnings(result, request, primary_building_zone, core_centers)
        return result

    def _normalized_request(self, request: BuildingRequest) -> BuildingRequest:
        frontage = str(request.frontage_edge or "bottom").strip().lower()
        if frontage not in self.VALID_FRONTAGE_EDGES:
            frontage = "bottom"

        anchor_mode = str(request.anchor_mode or "centered_front_setback").strip().lower()
        if anchor_mode not in self.VALID_ANCHOR_MODES:
            anchor_mode = "centered_front_setback"

        building_use = str(request.building_use or "generic").strip().lower()
        footprint_type = str(request.footprint_type or "bar").strip().lower()

        floor_count = max(1, int(request.floor_count))
        floor_height = max(8.0, float(request.floor_height))

        core_w = float(request.core_width)
        core_d = float(request.core_depth)

        if building_use == "multifamily":
            core_w = max(core_w, 20.0)
            core_d = max(core_d, 18.0)
        elif building_use == "office":
            core_w = max(core_w, 24.0)
            core_d = max(core_d, 20.0)
        elif building_use == "industrial":
            core_w = max(core_w, 16.0)
            core_d = max(core_d, 14.0)

        return BuildingRequest(
            site_zone_id=request.site_zone_id,
            building_width=max(20.0, float(request.building_width)),
            building_depth=max(20.0, float(request.building_depth)),
            front_setback=max(0.0, float(request.front_setback)),
            side_setback=max(0.0, float(request.side_setback)),
            rear_setback=max(0.0, float(request.rear_setback)),
            floor_count=floor_count,
            floor_height=floor_height,
            create_building_zone=request.create_building_zone,
            create_floor_zones=request.create_floor_zones,
            create_core_zone=request.create_core_zone,
            create_room_placeholders=request.create_room_placeholders,
            create_entry_object=request.create_entry_object,
            create_pad_object=request.create_pad_object,
            create_vertical_circulation=request.create_vertical_circulation,
            create_program_zones=request.create_program_zones,
            core_width=core_w,
            core_depth=core_d,
            anchor_mode=anchor_mode,
            frontage_edge=frontage,
            building_name=request.building_name,
            building_use=building_use,
            footprint_type=footprint_type,
            level=request.level,
            meta=dict(request.meta),
        )

    def _resolve_site_zone(
        self,
        project: ProjectModel,
        site_zone_id: Optional[str],
    ) -> Optional[Zone]:
        if site_zone_id:
            zone = project.zones.get(site_zone_id)
            if zone and zone.zone_type in {ZoneType.SITE, ZoneType.PARCEL, ZoneType.PAD}:
                return zone

        candidates = [
            z for z in project.zones.values()
            if z.zone_type in {ZoneType.SITE, ZoneType.PARCEL, ZoneType.PAD}
        ]
        if not candidates:
            return None

        candidates.sort(key=lambda z: z.boundary.area, reverse=True)
        return candidates[0]

    def _buildable_rect(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        front_setback: float,
        side_setback: float,
        rear_setback: float,
        frontage_edge: str,
    ) -> Dict[str, float]:
        if frontage_edge == "bottom":
            return {
                "min_x": min_x + side_setback,
                "max_x": max_x - side_setback,
                "min_y": min_y + front_setback,
                "max_y": max_y - rear_setback,
            }
        if frontage_edge == "top":
            return {
                "min_x": min_x + side_setback,
                "max_x": max_x - side_setback,
                "min_y": min_y + rear_setback,
                "max_y": max_y - front_setback,
            }
        if frontage_edge == "left":
            return {
                "min_x": min_x + front_setback,
                "max_x": max_x - rear_setback,
                "min_y": min_y + side_setback,
                "max_y": max_y - side_setback,
            }
        return {
            "min_x": min_x + rear_setback,
            "max_x": max_x - front_setback,
            "min_y": min_y + side_setback,
            "max_y": max_y - side_setback,
        }

    def _place_building_origin(
        self,
        buildable: Dict[str, float],
        request: BuildingRequest,
    ) -> Tuple[float, float]:
        span_x = buildable["max_x"] - buildable["min_x"]
        span_y = buildable["max_y"] - buildable["min_y"]

        if request.anchor_mode == "southwest":
            return buildable["min_x"], buildable["min_y"]

        if request.anchor_mode == "centered":
            x = buildable["min_x"] + (span_x - request.building_width) / 2.0
            y = buildable["min_y"] + (span_y - request.building_depth) / 2.0
            return x, y

        if request.frontage_edge == "bottom":
            x = buildable["min_x"] + (span_x - request.building_width) / 2.0
            y = buildable["min_y"]
            return x, y
        if request.frontage_edge == "top":
            x = buildable["min_x"] + (span_x - request.building_width) / 2.0
            y = buildable["max_y"] - request.building_depth
            return x, y
        if request.frontage_edge == "left":
            x = buildable["min_x"]
            y = buildable["min_y"] + (span_y - request.building_depth) / 2.0
            return x, y

        x = buildable["max_x"] - request.building_width
        y = buildable["min_y"] + (span_y - request.building_depth) / 2.0
        return x, y

    def _make_footprint_rects(
        self,
        x: float,
        y: float,
        width: float,
        depth: float,
        footprint_type: str,
    ) -> List[Tuple[float, float, float, float, str]]:
        ft = footprint_type.lower().strip()

        if ft in {"bar", "slab", "compact"}:
            return [(x, y, width, depth, "Main")]

        if ft == "l_shape":
            wing_w = width * 0.38
            return [
                (x, y, width, depth * 0.42, "Wing A"),
                (x, y, wing_w, depth, "Wing B"),
            ]

        if ft == "u_shape":
            wing_w = width * 0.24
            base_h = depth * 0.30
            return [
                (x, y, wing_w, depth, "Wing L"),
                (x + width - wing_w, y, wing_w, depth, "Wing R"),
                (x, y, width, base_h, "Base"),
            ]

        if ft == "courtyard":
            wing_w = width * 0.22
            base_h = depth * 0.22
            return [
                (x, y, width, base_h, "Base S"),
                (x, y + depth - base_h, width, base_h, "Base N"),
                (x, y + base_h, wing_w, depth - 2.0 * base_h, "Wing W"),
                (x + width - wing_w, y + base_h, wing_w, depth - 2.0 * base_h, "Wing E"),
            ]

        if ft == "h_shape":
            wing_w = width * 0.24
            bridge_h = depth * 0.20
            return [
                (x, y, wing_w, depth, "Wing W"),
                (x + width - wing_w, y, wing_w, depth, "Wing E"),
                (x + wing_w, y + (depth - bridge_h) / 2.0, width - 2.0 * wing_w, bridge_h, "Connector"),
            ]

        return [(x, y, width, depth, "Main")]

    def _add_building_footprint_zones(
        self,
        project: ProjectModel,
        request: BuildingRequest,
        footprint_rects: List[Tuple[float, float, float, float, str]],
        result: BuildingResult,
    ) -> Optional[Zone]:
        primary_zone: Optional[Zone] = None

        for idx, (x, y, w, h, suffix) in enumerate(footprint_rects, start=1):
            zone_name = request.building_name if idx == 1 else f"{request.building_name} {suffix}"
            zone = rect_zone(
                x=x,
                y=y,
                width=w,
                height=h,
                zone_type=ZoneType.BUILDING,
                name=zone_name,
                level=request.level,
                tags=["building", "footprint", request.building_use, request.footprint_type],
            )

            if request.create_building_zone:
                project.add_zone(zone)
                result.zone_ids.append(zone.id)

            wing_obj = EngineeringObject(
                kind="building_wing" if idx > 1 else "building_footprint_piece",
                anchor=Point3D(zone.boundary.bbox.center.x, zone.boundary.bbox.center.y, 0.0),
                name=zone_name,
                level=request.level,
                boundary=zone.boundary,
                tags=["building", "footprint_piece", request.building_use],
                properties={
                    "source": "building_engine",
                    "piece_index": idx,
                    "piece_name": suffix,
                    "building_name": request.building_name,
                },
            )
            project.add_object(wing_obj)
            result.object_ids.append(wing_obj.id)

            if primary_zone is None:
                primary_zone = zone

        return primary_zone

    def _create_floor_zones(
        self,
        project: ProjectModel,
        building_zone: Zone,
        request: BuildingRequest,
    ) -> List[str]:
        if not request.create_floor_zones:
            return []

        ids: List[str] = []
        bb = building_zone.boundary.bbox

        for i in range(request.floor_count):
            floor_zone = rect_zone(
                x=bb.min_x,
                y=bb.min_y,
                width=bb.width,
                height=bb.height,
                zone_type=ZoneType.FLOOR,
                name=f"{request.building_name} Floor {i + 1}",
                level=f"Level {i + 1}",
                tags=["building", "floor", request.building_use],
            )
            project.add_zone(floor_zone)
            ids.append(floor_zone.id)

        return ids

    def _core_size_for_building(
        self,
        building_width: float,
        building_depth: float,
        request: BuildingRequest,
    ) -> Tuple[float, float]:
        core_w = min(max(request.core_width, building_width * 0.14), building_width * 0.8)
        core_h = min(max(request.core_depth, building_depth * 0.16), building_depth * 0.8)

        if request.building_use == "multifamily":
            core_w = min(max(core_w, 18.0), building_width * 0.55)
            core_h = min(max(core_h, 18.0), building_depth * 0.55)
        elif request.building_use == "office":
            core_w = min(max(core_w, 22.0), building_width * 0.45)
            core_h = min(max(core_h, 18.0), building_depth * 0.45)
        elif request.building_use == "industrial":
            core_w = min(max(core_w, 14.0), building_width * 0.35)
            core_h = min(max(core_h, 14.0), building_depth * 0.35)

        return core_w, core_h

    def _core_centers_for_building(
        self,
        bb,
        request: BuildingRequest,
        core_w: float,
        core_h: float,
    ) -> List[Tuple[float, float]]:
        centers: List[Tuple[float, float]] = []

        long_dim = max(bb.width, bb.height)
        multi_core = (
            request.building_use in {"multifamily", "office"}
            and request.floor_count >= 3
            and long_dim >= 140.0
        ) or request.footprint_type in {"u_shape", "courtyard", "h_shape"}

        if not multi_core:
            centers.append((bb.center.x, bb.center.y))
            return centers

        if bb.width >= bb.height:
            offset = min(bb.width * 0.22, 42.0)
            centers.append((bb.center.x - offset, bb.center.y))
            centers.append((bb.center.x + offset, bb.center.y))
        else:
            offset = min(bb.height * 0.22, 42.0)
            centers.append((bb.center.x, bb.center.y - offset))
            centers.append((bb.center.x, bb.center.y + offset))

        return centers

    def _create_core_zones(
        self,
        project: ProjectModel,
        building_zone: Zone,
        request: BuildingRequest,
    ) -> Tuple[List[str], List[Tuple[float, float]]]:
        if not request.create_core_zone:
            return [], []

        ids: List[str] = []
        bb = building_zone.boundary.bbox
        core_w, core_h = self._core_size_for_building(bb.width, bb.height, request)
        core_centers = self._core_centers_for_building(bb, request, core_w, core_h)

        if request.create_floor_zones:
            for i in range(request.floor_count):
                for j, (cx, cy) in enumerate(core_centers, start=1):
                    core_zone = rect_zone(
                        x=cx - core_w / 2.0,
                        y=cy - core_h / 2.0,
                        width=core_w,
                        height=core_h,
                        zone_type=ZoneType.ROOM,
                        name=f"{request.building_name} Core {j} L{i + 1}",
                        level=f"Level {i + 1}",
                        tags=["building", "core", request.building_use],
                    )
                    project.add_zone(core_zone)
                    ids.append(core_zone.id)
        else:
            for j, (cx, cy) in enumerate(core_centers, start=1):
                core_zone = rect_zone(
                    x=cx - core_w / 2.0,
                    y=cy - core_h / 2.0,
                    width=core_w,
                    height=core_h,
                    zone_type=ZoneType.ROOM,
                    name=f"{request.building_name} Core {j}",
                    level=request.level,
                    tags=["building", "core", request.building_use],
                )
                project.add_zone(core_zone)
                ids.append(core_zone.id)

        return ids, core_centers

    def _create_vertical_circulation_objects(
        self,
        project: ProjectModel,
        request: BuildingRequest,
        core_centers: List[Tuple[float, float]],
    ) -> List[str]:
        ids: List[str] = []

        for j, (cx, cy) in enumerate(core_centers, start=1):
            stair_a = EngineeringObject(
                kind="stair",
                anchor=Point3D(cx - 3.0, cy, 0.0),
                name=f"{request.building_name} Stair A Core {j}",
                level=request.level,
                tags=["building", "circulation", "stair"],
                properties={"source": "building_engine", "core_index": j},
            )
            stair_b = EngineeringObject(
                kind="stair",
                anchor=Point3D(cx + 3.0, cy, 0.0),
                name=f"{request.building_name} Stair B Core {j}",
                level=request.level,
                tags=["building", "circulation", "stair"],
                properties={"source": "building_engine", "core_index": j},
            )
            elevator = EngineeringObject(
                kind="elevator",
                anchor=Point3D(cx, cy, 0.0),
                name=f"{request.building_name} Elevator Core {j}",
                level=request.level,
                tags=["building", "circulation", "elevator"],
                properties={"source": "building_engine", "core_index": j},
            )

            project.add_object(stair_a)
            project.add_object(stair_b)
            project.add_object(elevator)
            ids.extend([stair_a.id, stair_b.id, elevator.id])

        return ids

    def _create_program_zones(
        self,
        project: ProjectModel,
        building_zone: Zone,
        request: BuildingRequest,
        core_centers: List[Tuple[float, float]],
    ) -> List[str]:
        if request.building_use == "multifamily":
            return self._create_multifamily_program(project, building_zone, request, core_centers)
        if request.building_use == "office":
            return self._create_office_program(project, building_zone, request, core_centers)
        if request.building_use == "retail":
            return self._create_retail_program(project, building_zone, request)
        if request.building_use == "industrial":
            return self._create_industrial_program(project, building_zone, request)
        return self._create_generic_program(project, building_zone, request)

    def _create_multifamily_program(
        self,
        project: ProjectModel,
        building_zone: Zone,
        request: BuildingRequest,
        core_centers: List[Tuple[float, float]],
    ) -> List[str]:
        ids: List[str] = []
        bb = building_zone.boundary.bbox
        levels = [f"Level {i + 1}" for i in range(request.floor_count)]

        corridor_width = min(10.0, max(8.0, bb.width * 0.08 if bb.width < bb.height else bb.height * 0.08))
        if bb.width >= bb.height:
            corridor = (
                bb.min_x,
                bb.center.y - corridor_width / 2.0,
                bb.width,
                corridor_width,
            )
            north_band = (bb.min_x, bb.center.y + corridor_width / 2.0, bb.width, bb.max_y - (bb.center.y + corridor_width / 2.0))
            south_band = (bb.min_x, bb.min_y, bb.width, (bb.center.y - corridor_width / 2.0) - bb.min_y)
            unit_split_dir = "x"
        else:
            corridor = (
                bb.center.x - corridor_width / 2.0,
                bb.min_y,
                corridor_width,
                bb.height,
            )
            west_band = (bb.min_x, bb.min_y, (bb.center.x - corridor_width / 2.0) - bb.min_x, bb.height)
            east_band = (bb.center.x + corridor_width / 2.0, bb.min_y, bb.max_x - (bb.center.x + corridor_width / 2.0), bb.height)
            unit_split_dir = "y"

        for level in levels:
            corridor_zone = rect_zone(
                x=corridor[0],
                y=corridor[1],
                width=max(4.0, corridor[2]),
                height=max(4.0, corridor[3]),
                zone_type=ZoneType.ROOM,
                name=f"{request.building_name} Corridor {level}",
                level=level,
                tags=["building", "corridor", "multifamily"],
            )
            project.add_zone(corridor_zone)
            ids.append(corridor_zone.id)

            if bb.width >= bb.height:
                ids.extend(self._create_unit_band(
                    project, request, level, "North Units", north_band, unit_split_dir
                ))
                ids.extend(self._create_unit_band(
                    project, request, level, "South Units", south_band, unit_split_dir
                ))
            else:
                ids.extend(self._create_unit_band(
                    project, request, level, "West Units", west_band, unit_split_dir
                ))
                ids.extend(self._create_unit_band(
                    project, request, level, "East Units", east_band, unit_split_dir
                ))

        if levels:
            lobby_h = min(20.0, bb.height * 0.18)
            lobby_y = bb.min_y if request.frontage_edge == "bottom" else bb.max_y - lobby_h
            lobby = rect_zone(
                x=bb.center.x - min(28.0, bb.width * 0.25) / 2.0,
                y=lobby_y,
                width=min(28.0, bb.width * 0.25),
                height=lobby_h,
                zone_type=ZoneType.ROOM,
                name=f"{request.building_name} Lobby",
                level="Level 1",
                tags=["building", "lobby", "multifamily"],
            )
            project.add_zone(lobby)
            ids.append(lobby.id)

            leasing = rect_zone(
                x=lobby.boundary.bbox.min_x,
                y=lobby.boundary.bbox.max_y if request.frontage_edge == "bottom" else lobby.boundary.bbox.min_y - 14.0,
                width=lobby.boundary.bbox.width,
                height=14.0,
                zone_type=ZoneType.ROOM,
                name=f"{request.building_name} Leasing",
                level="Level 1",
                tags=["building", "leasing", "multifamily"],
            )
            project.add_zone(leasing)
            ids.append(leasing.id)

            amenity = rect_zone(
                x=bb.center.x - min(36.0, bb.width * 0.30) / 2.0,
                y=bb.center.y - min(18.0, bb.height * 0.18) / 2.0,
                width=min(36.0, bb.width * 0.30),
                height=min(18.0, bb.height * 0.18),
                zone_type=ZoneType.ROOM,
                name=f"{request.building_name} Amenity",
                level="Level 1",
                tags=["building", "amenity", "multifamily"],
            )
            project.add_zone(amenity)
            ids.append(amenity.id)

        return ids

    def _create_unit_band(
        self,
        project: ProjectModel,
        request: BuildingRequest,
        level: str,
        band_name: str,
        band_rect: Tuple[float, float, float, float],
        split_dir: str,
    ) -> List[str]:
        ids: List[str] = []
        x, y, w, h = band_rect
        if w <= 8.0 or h <= 8.0:
            return ids

        unit_count = max(2, int((w / 26.0) if split_dir == "x" else (h / 26.0)))
        for i in range(unit_count):
            if split_dir == "x":
                ux = x + i * (w / unit_count)
                uy = y
                uw = w / unit_count
                uh = h
            else:
                ux = x
                uy = y + i * (h / unit_count)
                uw = w
                uh = h / unit_count

            zone = rect_zone(
                x=ux,
                y=uy,
                width=max(8.0, uw),
                height=max(8.0, uh),
                zone_type=ZoneType.ROOM,
                name=f"{request.building_name} {band_name} Unit {i + 1} {level}",
                level=level,
                tags=["building", "unit_placeholder", "multifamily"],
            )
            project.add_zone(zone)
            ids.append(zone.id)

        return ids

    def _create_office_program(
        self,
        project: ProjectModel,
        building_zone: Zone,
        request: BuildingRequest,
        core_centers: List[Tuple[float, float]],
    ) -> List[str]:
        ids: List[str] = []
        bb = building_zone.boundary.bbox
        levels = [f"Level {i + 1}" for i in range(request.floor_count)]

        for level in levels:
            office_plate = rect_zone(
                x=bb.min_x,
                y=bb.min_y,
                width=bb.width,
                height=bb.height,
                zone_type=ZoneType.ROOM,
                name=f"{request.building_name} Office Plate {level}",
                level=level,
                tags=["building", "office_plate", "office"],
            )
            project.add_zone(office_plate)
            ids.append(office_plate.id)

        lobby_h = min(22.0, bb.height * 0.20)
        lobby_y = bb.min_y if request.frontage_edge == "bottom" else bb.max_y - lobby_h
        lobby = rect_zone(
            x=bb.center.x - min(40.0, bb.width * 0.35) / 2.0,
            y=lobby_y,
            width=min(40.0, bb.width * 0.35),
            height=lobby_h,
            zone_type=ZoneType.ROOM,
            name=f"{request.building_name} Lobby",
            level="Level 1",
            tags=["building", "lobby", "office"],
        )
        project.add_zone(lobby)
        ids.append(lobby.id)

        service = rect_zone(
            x=bb.max_x - min(24.0, bb.width * 0.20),
            y=bb.max_y - min(18.0, bb.height * 0.18),
            width=min(24.0, bb.width * 0.20),
            height=min(18.0, bb.height * 0.18),
            zone_type=ZoneType.ROOM,
            name=f"{request.building_name} Service",
            level="Level 1",
            tags=["building", "service", "office"],
        )
        project.add_zone(service)
        ids.append(service.id)

        return ids

    def _create_retail_program(
        self,
        project: ProjectModel,
        building_zone: Zone,
        request: BuildingRequest,
    ) -> List[str]:
        ids: List[str] = []
        bb = building_zone.boundary.bbox

        shell = rect_zone(
            x=bb.min_x,
            y=bb.min_y,
            width=bb.width,
            height=bb.height * 0.72,
            zone_type=ZoneType.ROOM,
            name=f"{request.building_name} Retail Shell",
            level="Level 1",
            tags=["building", "retail_shell", "retail"],
        )
        boh = rect_zone(
            x=bb.min_x,
            y=bb.min_y + bb.height * 0.72,
            width=bb.width,
            height=bb.height * 0.28,
            zone_type=ZoneType.ROOM,
            name=f"{request.building_name} Back of House",
            level="Level 1",
            tags=["building", "back_of_house", "retail"],
        )

        project.add_zone(shell)
        project.add_zone(boh)
        ids.extend([shell.id, boh.id])
        return ids

    def _create_industrial_program(
        self,
        project: ProjectModel,
        building_zone: Zone,
        request: BuildingRequest,
    ) -> List[str]:
        ids: List[str] = []
        bb = building_zone.boundary.bbox

        office_w = min(32.0, bb.width * 0.22)
        office_h = min(28.0, bb.height * 0.28)

        office = rect_zone(
            x=bb.min_x,
            y=bb.min_y,
            width=office_w,
            height=office_h,
            zone_type=ZoneType.ROOM,
            name=f"{request.building_name} Office",
            level="Level 1",
            tags=["building", "office_component", "industrial"],
        )
        warehouse = rect_zone(
            x=bb.min_x,
            y=bb.min_y,
            width=bb.width,
            height=bb.height,
            zone_type=ZoneType.ROOM,
            name=f"{request.building_name} Warehouse",
            level="Level 1",
            tags=["building", "warehouse", "industrial"],
        )
        service = rect_zone(
            x=bb.max_x - min(20.0, bb.width * 0.16),
            y=bb.max_y - min(16.0, bb.height * 0.16),
            width=min(20.0, bb.width * 0.16),
            height=min(16.0, bb.height * 0.16),
            zone_type=ZoneType.ROOM,
            name=f"{request.building_name} Service",
            level="Level 1",
            tags=["building", "service", "industrial"],
        )

        project.add_zone(warehouse)
        project.add_zone(office)
        project.add_zone(service)
        ids.extend([warehouse.id, office.id, service.id])
        return ids

    def _create_generic_program(
        self,
        project: ProjectModel,
        building_zone: Zone,
        request: BuildingRequest,
    ) -> List[str]:
        ids: List[str] = []
        bb = building_zone.boundary.bbox

        generic = rect_zone(
            x=bb.min_x,
            y=bb.min_y,
            width=bb.width,
            height=bb.height,
            zone_type=ZoneType.ROOM,
            name=f"{request.building_name} Program",
            level="Level 1",
            tags=["building", "program", "generic"],
        )
        project.add_zone(generic)
        ids.append(generic.id)
        return ids

    def _create_room_placeholders(
        self,
        project: ProjectModel,
        building_zone: Zone,
        request: BuildingRequest,
    ) -> List[str]:
        ids: List[str] = []
        bb = building_zone.boundary.bbox
        room_cols, room_rows = self._placeholder_grid(request)

        room_w = bb.width / room_cols
        room_h = bb.height / room_rows
        levels = [f"Level {i + 1}" for i in range(request.floor_count)] if request.floor_count > 0 else [request.level]

        for level in levels:
            for r in range(room_rows):
                for c in range(room_cols):
                    room_zone = rect_zone(
                        x=bb.min_x + c * room_w,
                        y=bb.min_y + r * room_h,
                        width=room_w,
                        height=room_h,
                        zone_type=ZoneType.ROOM,
                        name=f"{request.building_name} Room {r + 1}-{c + 1} {level}",
                        level=level,
                        tags=["building", "room_placeholder", request.building_use],
                    )
                    project.add_zone(room_zone)
                    ids.append(room_zone.id)

        return ids

    def _placeholder_grid(self, request: BuildingRequest) -> Tuple[int, int]:
        if request.building_use == "multifamily":
            return 2, 4
        if request.building_use == "office":
            return 3, 2
        if request.building_use == "retail":
            return 2, 2
        if request.building_use == "industrial":
            return 2, 2
        return 2, 2

    def _create_entry_objects(
        self,
        project: ProjectModel,
        building_zone: Zone,
        request: BuildingRequest,
    ) -> List[str]:
        ids: List[str] = []
        bb = building_zone.boundary.bbox

        entries = self._entry_points_for_building(bb, request)

        for i, (ex, ey) in enumerate(entries, start=1):
            entry = EngineeringObject(
                kind="building_entry",
                anchor=Point3D(ex, ey, 0.0),
                name=f"{request.building_name} Entry {i}",
                level=request.level,
                tags=["building", "entry"],
                properties={
                    "source": "building_engine",
                    "frontage_edge": request.frontage_edge,
                    "building_name": request.building_name,
                    "entry_index": i,
                },
            )
            project.add_object(entry)
            ids.append(entry.id)

        return ids

    def _entry_points_for_building(self, bb, request: BuildingRequest) -> List[Tuple[float, float]]:
        entries: List[Tuple[float, float]] = []

        if request.frontage_edge == "bottom":
            entries.append((bb.center.x, bb.min_y))
            if bb.width >= 140.0:
                entries.append((bb.center.x - min(28.0, bb.width * 0.20), bb.min_y))
                entries.append((bb.center.x + min(28.0, bb.width * 0.20), bb.min_y))
        elif request.frontage_edge == "top":
            entries.append((bb.center.x, bb.max_y))
            if bb.width >= 140.0:
                entries.append((bb.center.x - min(28.0, bb.width * 0.20), bb.max_y))
                entries.append((bb.center.x + min(28.0, bb.width * 0.20), bb.max_y))
        elif request.frontage_edge == "left":
            entries.append((bb.min_x, bb.center.y))
            if bb.height >= 140.0:
                entries.append((bb.min_x, bb.center.y - min(28.0, bb.height * 0.20)))
                entries.append((bb.min_x, bb.center.y + min(28.0, bb.height * 0.20)))
        else:
            entries.append((bb.max_x, bb.center.y))
            if bb.height >= 140.0:
                entries.append((bb.max_x, bb.center.y - min(28.0, bb.height * 0.20)))
                entries.append((bb.max_x, bb.center.y + min(28.0, bb.height * 0.20)))

        return entries

    def _create_building_pad_object(
        self,
        building_zone: Zone,
        request: BuildingRequest,
    ) -> EngineeringObject:
        bb = building_zone.boundary.bbox
        return EngineeringObject(
            kind="building_pad",
            anchor=Point3D(bb.center.x, bb.center.y, 0.0),
            name=f"{request.building_name} Pad",
            level=request.level,
            boundary=building_zone.boundary,
            tags=["building", "pad"],
            properties={
                "source": "building_engine",
                "pad_width": bb.width,
                "pad_depth": bb.height,
                "building_name": request.building_name,
            },
        )

    def _append_warnings(
        self,
        result: BuildingResult,
        request: BuildingRequest,
        building_zone: Zone,
        core_centers: List[Tuple[float, float]],
    ) -> None:
        bb = building_zone.boundary.bbox

        if request.floor_count > 1 and request.create_floor_zones:
            result.warnings.append(
                "Upper floors are represented as repeated floor zones, not unique layouts yet."
            )

        if request.building_use == "multifamily" and request.floor_count < 2:
            result.warnings.append(
                "Multifamily buildings commonly need multiple floors; check floor_count if this was intentional."
            )

        if request.footprint_type in {"u_shape", "courtyard", "h_shape"}:
            result.warnings.append(
                "Complex footprint was approximated using multiple rectangular wings."
            )

        if len(core_centers) > 1:
            result.warnings.append(
                "Multiple cores were generated conceptually; final circulation and egress still need detailed design."
            )

        if bb.width >= 220.0 or bb.height >= 220.0:
            result.warnings.append(
                "Large floorplate detected; consider adding more detailed wing and circulation logic downstream."
            )


def generate_building(
    project: ProjectModel,
    request: BuildingRequest,
) -> BuildingResult:
    return BuildingEngine().generate(project, request)