from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from core.geometry_core import (
    EngineeringObject,
    Obstacle,
    Point2D,
    Point3D,
    Polyline2D,
    Polygon2D,
    ProjectModel,
    Zone,
    ZoneType,
    PolylineEntity,
    PolygonEntity,
    PointEntity,
    EntityStyle,
)


# =============================================================================
# Sketch DTOs
# =============================================================================

@dataclass
class SketchPoint:
    x: float
    y: float
    label: Optional[str] = None
    kind: str = "point"
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_point2d(self) -> Point2D:
        return Point2D(float(self.x), float(self.y))


@dataclass
class SketchStroke:
    points: List[SketchPoint]
    label: Optional[str] = None
    kind: str = "line"
    closed_hint: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_polyline(self) -> Polyline2D:
        pts = [p.to_point2d() for p in self.points]
        return Polyline2D(points=pts, closed=bool(self.closed_hint))


@dataclass
class SketchRegion:
    points: List[SketchPoint]
    label: Optional[str] = None
    kind: str = "region"
    zone_type_hint: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_polygon(self) -> Polygon2D:
        pts = [p.to_point2d() for p in self.points]
        return Polygon2D(points=pts)


@dataclass
class SketchText:
    text: str
    x: float
    y: float
    kind: str = "text"
    meta: Dict[str, Any] = field(default_factory=dict)

    def point(self) -> Point2D:
        return Point2D(float(self.x), float(self.y))


@dataclass
class SketchInput:
    points: List[SketchPoint] = field(default_factory=list)
    strokes: List[SketchStroke] = field(default_factory=list)
    regions: List[SketchRegion] = field(default_factory=list)
    texts: List[SketchText] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedSketch:
    boundary_zones: List[Zone] = field(default_factory=list)
    obstacles: List[Obstacle] = field(default_factory=list)
    objects: List[EngineeringObject] = field(default_factory=list)
    centerlines: List[Polyline2D] = field(default_factory=list)
    anchors: List[EngineeringObject] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    site_regions: List[Zone] = field(default_factory=list)
    building_regions: List[Zone] = field(default_factory=list)
    parking_regions: List[Zone] = field(default_factory=list)
    road_regions: List[Zone] = field(default_factory=list)
    pad_regions: List[Zone] = field(default_factory=list)
    pond_regions: List[Zone] = field(default_factory=list)
    drainage_regions: List[Zone] = field(default_factory=list)
    utility_regions: List[Zone] = field(default_factory=list)
    bridge_regions: List[Zone] = field(default_factory=list)
    structure_regions: List[Zone] = field(default_factory=list)
    corridor_regions: List[Zone] = field(default_factory=list)

    roadway_centerlines: List[Polyline2D] = field(default_factory=list)
    utility_centerlines: List[Polyline2D] = field(default_factory=list)
    drainage_centerlines: List[Polyline2D] = field(default_factory=list)
    sidewalk_centerlines: List[Polyline2D] = field(default_factory=list)
    fire_access_centerlines: List[Polyline2D] = field(default_factory=list)

    building_objects: List[EngineeringObject] = field(default_factory=list)
    drainage_objects: List[EngineeringObject] = field(default_factory=list)
    utility_objects: List[EngineeringObject] = field(default_factory=list)
    roadway_objects: List[EngineeringObject] = field(default_factory=list)
    bridge_objects: List[EngineeringObject] = field(default_factory=list)
    structure_objects: List[EngineeringObject] = field(default_factory=list)
    text_derived_objects: List[EngineeringObject] = field(default_factory=list)


# =============================================================================
# Parser
# =============================================================================

class SketchParser:
    """
    Product-grade sketch interpreter for sketch-to-plan workflows.

    Goals:
    - robust against sparse / imperfect labels
    - compatible with broader civil/site/building/bridge workflows
    - planner-friendly structured output
    - avoids brittle dependencies on old enum names
    """

    ZONE_LABEL_MAP: Dict[str, ZoneType] = {
        "unknown": ZoneType.UNKNOWN,
        "site": ZoneType.SITE,
        "lot": ZoneType.LOT,
        "building": ZoneType.BUILDING,
        "building pad": ZoneType.BUILDING_PAD if hasattr(ZoneType, "BUILDING_PAD") else ZoneType.PAD,
        "pad": ZoneType.PAD,
        "parking": ZoneType.PARKING,
        "road": ZoneType.ROAD,
        "roadway": ZoneType.ROADWAY if hasattr(ZoneType, "ROADWAY") else ZoneType.ROAD,
        "corridor": ZoneType.CORRIDOR,
        "bridge": ZoneType.BRIDGE,
        "structure": ZoneType.STRUCTURE,
        "utility": ZoneType.UTILITY,
        "drainage": ZoneType.DRAINAGE,
        "detention": ZoneType.DETENTION,
        "open space": ZoneType.OPEN_SPACE,
        "easement": ZoneType.EASEMENT,
        "floor": ZoneType.FLOOR,
        "room": ZoneType.ROOM,
    }

    OBSTACLE_KEYWORDS = (
        "column",
        "wall",
        "core",
        "no build",
        "obstacle",
        "keepout",
        "beam",
        "pier",
        "retaining wall",
        "barrier",
        "median island",
    )

    CENTERLINE_KEYWORDS = (
        "centerline",
        "alignment",
        "route",
        "pipe",
        "road",
        "path",
        "main",
        "trunk",
        "drive",
        "sidewalk",
        "fire lane",
        "utility",
    )

    OBJECT_KEYWORDS = (
        "fixture",
        "inlet",
        "manhole",
        "drain",
        "sink",
        "toilet",
        "pump",
        "building",
        "pad",
        "lot",
        "equipment",
        "column",
        "beam",
        "pier",
        "abutment",
        "mh",
        "cb",
        "gi",
        "headwall",
        "junction box",
        "transformer",
        "hydrant",
        "valve",
        "pond",
        "basin",
        "outfall",
    )

    BUILDING_KEYWORDS = (
        "building",
        "bldg",
        "apartment",
        "office",
        "retail",
        "warehouse",
        "clubhouse",
        "garage",
        "structure",
    )

    PARKING_KEYWORDS = (
        "parking",
        "park",
        "stall",
        "lot",
        "aisle",
        "garage parking",
    )

    ROAD_KEYWORDS = (
        "road",
        "street",
        "drive",
        "lane",
        "access",
        "entry",
        "boulevard",
        "culdesac",
        "cul-de-sac",
        "alley",
        "roadway",
    )

    SIDEWALK_KEYWORDS = (
        "sidewalk",
        "walk",
        "walkway",
        "ada path",
        "pedestrian",
    )

    FIRE_ACCESS_KEYWORDS = (
        "fire lane",
        "fire access",
        "emergency access",
    )

    DRAINAGE_KEYWORDS = (
        "drainage",
        "storm",
        "inlet",
        "manhole",
        "pond",
        "basin",
        "swale",
        "ditch",
        "outfall",
        "pipe",
        "culvert",
        "cb",
        "gi",
        "mh",
        "detention",
        "retention",
    )

    UTILITY_KEYWORDS = (
        "utility",
        "water",
        "sanitary",
        "sewer",
        "electric",
        "gas",
        "fiber",
        "telecom",
        "force main",
        "service",
        "hydrant",
        "valve",
    )

    PAD_KEYWORDS = (
        "pad",
        "building pad",
        "house pad",
        "finished pad",
    )

    SITE_BOUNDARY_KEYWORDS = (
        "site",
        "boundary",
        "property",
        "lot line",
        "tract",
        "parcel",
    )

    POND_KEYWORDS = (
        "pond",
        "basin",
        "detention",
        "retention",
    )

    BRIDGE_KEYWORDS = (
        "bridge",
        "pier",
        "abutment",
        "deck",
        "span",
    )

    STRUCTURE_KEYWORDS = (
        "structure",
        "frame",
        "column grid",
        "beam line",
    )

    def parse(self, sketch: SketchInput) -> ParsedSketch:
        parsed = ParsedSketch(meta=dict(sketch.meta))

        self._parse_regions(sketch.regions, parsed)
        self._parse_strokes(sketch.strokes, parsed)
        self._parse_points(sketch.points, parsed)
        self._parse_text_anchors(sketch.texts, parsed)
        self._post_process(parsed)

        return parsed

    def apply_to_project(
        self,
        project: ProjectModel,
        sketch: SketchInput,
        add_as_entities: bool = False,
    ) -> ParsedSketch:
        parsed = self.parse(sketch)

        for zone in parsed.boundary_zones:
            project.add_zone(zone)

        for obstacle in parsed.obstacles:
            project.add_obstacle(obstacle)

        for obj in parsed.objects:
            project.add_object(obj)

        for anchor in parsed.anchors:
            project.add_object(anchor)

        if add_as_entities:
            for zone in parsed.boundary_zones:
                project.add_entity(
                    PolygonEntity(
                        polygon=zone.boundary,
                        style=EntityStyle(layer=self._zone_layer(zone)),
                        meta={"source": "sketch", "zone_id": zone.id},
                    )
                )

            for obs in parsed.obstacles:
                project.add_entity(
                    PolygonEntity(
                        polygon=obs.boundary,
                        style=EntityStyle(layer="SKETCH_OBS"),
                        meta={"source": "sketch", "obstacle_id": obs.id},
                    )
                )

            for line in parsed.centerlines:
                project.add_entity(
                    PolylineEntity(
                        polyline=line,
                        style=EntityStyle(layer="SKETCH_LINE"),
                        meta={"source": "sketch"},
                    )
                )

            for obj in parsed.objects + parsed.anchors:
                project.add_entity(
                    PointEntity(
                        point=obj.anchor.as_2d(),
                        style=EntityStyle(layer=self._object_layer(obj)),
                        meta={"source": "sketch", "object_id": obj.id},
                    )
                )

        return parsed

    def from_dict(self, data: Dict[str, Any]) -> SketchInput:
        def _mk_point(item: Dict[str, Any]) -> SketchPoint:
            return SketchPoint(
                x=float(item["x"]),
                y=float(item["y"]),
                label=item.get("label"),
                kind=item.get("kind", "point"),
                meta=item.get("meta", {}),
            )

        points = [_mk_point(item) for item in data.get("points", [])]

        strokes = [
            SketchStroke(
                points=[_mk_point(p) for p in item.get("points", [])],
                label=item.get("label"),
                kind=item.get("kind", "line"),
                closed_hint=bool(item.get("closed_hint", False)),
                meta=item.get("meta", {}),
            )
            for item in data.get("strokes", [])
        ]

        regions = [
            SketchRegion(
                points=[_mk_point(p) for p in item.get("points", [])],
                label=item.get("label"),
                kind=item.get("kind", "region"),
                zone_type_hint=item.get("zone_type_hint"),
                meta=item.get("meta", {}),
            )
            for item in data.get("regions", [])
        ]

        texts = [
            SketchText(
                text=str(item["text"]),
                x=float(item["x"]),
                y=float(item["y"]),
                kind=item.get("kind", "text"),
                meta=item.get("meta", {}),
            )
            for item in data.get("texts", [])
        ]

        return SketchInput(
            points=points,
            strokes=strokes,
            regions=regions,
            texts=texts,
            meta=data.get("meta", {}),
        )

    def _parse_regions(self, regions: Sequence[SketchRegion], parsed: ParsedSketch) -> None:
        for region in regions:
            if len(region.points) < 3:
                parsed.warnings.append("Skipped sketch region with fewer than 3 points.")
                continue

            try:
                polygon = region.to_polygon()
            except Exception as exc:
                parsed.warnings.append(f"Skipped invalid sketch region '{region.label or 'unnamed'}': {exc}")
                continue

            label_raw = (region.label or "").strip()
            label = label_raw.lower()
            zone_type = self._infer_zone_type(label, region.zone_type_hint)

            tags = ["sketch"]
            category = self._classify_region(label, region.kind, region.meta)
            if category:
                tags.append(category)

            zone = Zone(
                boundary=polygon,
                zone_type=zone_type,
                name=region.label,
                tags=tags,
                meta={
                    "source": "sketch",
                    "region_kind": region.kind,
                    "region_category": category,
                    **region.meta,
                },
            )
            parsed.boundary_zones.append(zone)

            self._bucket_zone(parsed, zone, category)

            if self._looks_like_obstacle(label, region.kind, region.meta):
                parsed.obstacles.append(
                    Obstacle(
                        boundary=polygon,
                        kind=str(region.meta.get("obstacle_kind", "sketch_obstacle")),
                        name=region.label,
                        clearance=float(region.meta.get("clearance", 0.0)),
                        meta={
                            "source": "sketch_region",
                            "region_category": category,
                            **region.meta,
                        },
                    )
                )

            centroid = self._polygon_centroid(polygon)
            if centroid is not None and category in {
                "building",
                "parking",
                "pad",
                "pond",
                "drainage",
                "utility",
                "road",
                "bridge",
                "structure",
                "corridor",
            }:
                obj = EngineeringObject(
                    kind=f"{category}_region",
                    anchor=Point3D(centroid.x, centroid.y, float(region.meta.get("z", 0.0))),
                    name=region.label or None,
                    tags=["sketch", "region", category],
                    properties={
                        "source": "sketch_region",
                        "region_kind": region.kind,
                        "zone_type": zone.zone_type.value,
                        **region.meta,
                    },
                )
                parsed.objects.append(obj)
                self._bucket_object(parsed, obj, category)

    def _parse_strokes(self, strokes: Sequence[SketchStroke], parsed: ParsedSketch) -> None:
        for stroke in strokes:
            if len(stroke.points) < 2:
                parsed.warnings.append("Skipped sketch stroke with fewer than 2 points.")
                continue

            try:
                polyline = stroke.to_polyline()
            except Exception as exc:
                parsed.warnings.append(f"Skipped invalid sketch stroke '{stroke.label or 'unnamed'}': {exc}")
                continue

            parsed.centerlines.append(polyline)

            label_raw = (stroke.label or "").strip()
            label = label_raw.lower()
            category = self._classify_stroke(label, stroke.kind, stroke.meta)

            if category == "road":
                parsed.roadway_centerlines.append(polyline)
            elif category == "utility":
                parsed.utility_centerlines.append(polyline)
            elif category == "drainage":
                parsed.drainage_centerlines.append(polyline)
            elif category == "sidewalk":
                parsed.sidewalk_centerlines.append(polyline)
            elif category == "fire_access":
                parsed.fire_access_centerlines.append(polyline)

            if category in {"road", "utility", "drainage", "sidewalk", "fire_access"}:
                anchor = self._polyline_midpoint(polyline)
                if anchor is not None:
                    obj = EngineeringObject(
                        kind=f"{category}_centerline",
                        anchor=Point3D(anchor.x, anchor.y, float(stroke.meta.get("z", 0.0))),
                        name=stroke.label or None,
                        tags=["sketch", "centerline", category],
                        properties={
                            "source": "sketch_stroke",
                            "stroke_kind": stroke.kind,
                            "polyline_closed": polyline.closed,
                            **stroke.meta,
                        },
                    )
                    parsed.objects.append(obj)
                    self._bucket_object(parsed, obj, category)

            if self._looks_like_obstacle(label, stroke.kind, stroke.meta):
                bbox = polyline.bbox
                parsed.obstacles.append(
                    Obstacle(
                        boundary=Polygon2D(
                            [
                                Point2D(bbox.min_x, bbox.min_y),
                                Point2D(bbox.max_x, bbox.min_y),
                                Point2D(bbox.max_x, bbox.max_y),
                                Point2D(bbox.min_x, bbox.max_y),
                            ]
                        ),
                        kind=str(stroke.meta.get("obstacle_kind", "stroke_obstacle")),
                        name=stroke.label,
                        clearance=float(stroke.meta.get("clearance", 0.0)),
                        meta={"source": "sketch_stroke", "stroke_category": category, **stroke.meta},
                    )
                )

    def _parse_points(self, points: Sequence[SketchPoint], parsed: ParsedSketch) -> None:
        for pt in points:
            label = (pt.label or "").strip()
            label_l = label.lower()
            category = self._classify_point(label_l, pt.kind, pt.meta)

            if self._looks_like_object(label_l, pt.kind, pt.meta) or category is not None:
                kind = str(pt.meta.get("object_kind") or self._object_kind_from_category(category, pt.kind))
                obj = EngineeringObject(
                    kind=kind,
                    anchor=Point3D(pt.x, pt.y, float(pt.meta.get("z", 0.0))),
                    name=label or None,
                    tags=["sketch"] + ([category] if category else []),
                    properties={"source": "sketch_point", **pt.meta},
                )
                parsed.objects.append(obj)
                self._bucket_object(parsed, obj, category)
            else:
                parsed.objects.append(
                    EngineeringObject(
                        kind="anchor_point",
                        anchor=Point3D(pt.x, pt.y, float(pt.meta.get("z", 0.0))),
                        name=label or None,
                        tags=["sketch", "anchor"],
                        properties={"source": "sketch_point", **pt.meta},
                    )
                )

    def _parse_text_anchors(self, texts: Sequence[SketchText], parsed: ParsedSketch) -> None:
        for text in texts:
            txt = text.text.strip()
            txt_l = txt.lower()
            category = self._classify_text(txt_l, text.kind, text.meta)

            anchor = EngineeringObject(
                kind="text_anchor",
                anchor=Point3D(text.x, text.y, float(text.meta.get("z", 0.0))),
                name=txt,
                tags=["sketch", "text"] + ([category] if category else []),
                properties={"source": "sketch_text", **text.meta},
            )
            parsed.anchors.append(anchor)

            if self._looks_like_object(txt_l, "text", text.meta) or category is not None:
                obj = EngineeringObject(
                    kind=str(text.meta.get("object_kind", self._object_kind_from_category(category, "text"))),
                    anchor=Point3D(text.x, text.y, float(text.meta.get("z", 0.0))),
                    name=txt,
                    tags=["sketch", "derived_from_text"] + ([category] if category else []),
                    properties={"source": "sketch_text", **text.meta},
                )
                parsed.objects.append(obj)
                parsed.text_derived_objects.append(obj)
                self._bucket_object(parsed, obj, category)

    def _post_process(self, parsed: ParsedSketch) -> None:
        if not parsed.site_regions and parsed.boundary_zones:
            largest = self._largest_zone(parsed.boundary_zones)
            if largest is not None:
                parsed.site_regions.append(largest)

        if not parsed.building_regions:
            for obj in parsed.building_objects:
                parsed.warnings.append(
                    f"Detected building-like object '{obj.name or obj.kind}' without a building region."
                )

        if parsed.drainage_centerlines and not (
            parsed.drainage_objects or parsed.pond_regions or parsed.drainage_regions
        ):
            parsed.warnings.append(
                "Detected drainage-like centerlines but no drainage structures or pond/drainage regions."
            )

        if parsed.utility_centerlines and not (parsed.utility_objects or parsed.utility_regions):
            parsed.warnings.append(
                "Detected utility-like centerlines but no utility objects or utility regions."
            )

    def _infer_zone_type(self, label: str, zone_type_hint: Optional[str]) -> ZoneType:
        if zone_type_hint:
            zth = zone_type_hint.strip().lower()
            if zth in self.ZONE_LABEL_MAP:
                return self.ZONE_LABEL_MAP[zth]

        for key, zone_type in self.ZONE_LABEL_MAP.items():
            if key in label:
                return zone_type

        if any(word in label for word in self.BUILDING_KEYWORDS):
            return ZoneType.BUILDING
        if any(word in label for word in self.PARKING_KEYWORDS):
            return ZoneType.PARKING
        if any(word in label for word in self.ROAD_KEYWORDS):
            return ZoneType.ROAD
        if any(word in label for word in self.PAD_KEYWORDS):
            return ZoneType.PAD
        if any(word in label for word in self.UTILITY_KEYWORDS):
            return ZoneType.UTILITY
        if any(word in label for word in self.DRAINAGE_KEYWORDS):
            return ZoneType.DRAINAGE
        if any(word in label for word in self.BRIDGE_KEYWORDS):
            return ZoneType.BRIDGE
        if any(word in label for word in self.STRUCTURE_KEYWORDS):
            return ZoneType.STRUCTURE
        if any(word in label for word in self.SITE_BOUNDARY_KEYWORDS):
            return ZoneType.SITE

        return ZoneType.UNKNOWN

    def _classify_region(self, label: str, kind: str, meta: Dict[str, Any]) -> Optional[str]:
        explicit = str(meta.get("category", "")).strip().lower()
        if explicit:
            return explicit

        kind_l = (kind or "").lower()

        if any(word in label for word in self.SITE_BOUNDARY_KEYWORDS) or kind_l == "site":
            return "site"
        if any(word in label for word in self.BUILDING_KEYWORDS) or kind_l == "building":
            return "building"
        if any(word in label for word in self.PARKING_KEYWORDS) or kind_l == "parking":
            return "parking"
        if any(word in label for word in self.ROAD_KEYWORDS) or kind_l == "road":
            return "road"
        if any(word in label for word in self.PAD_KEYWORDS):
            return "pad"
        if any(word in label for word in self.POND_KEYWORDS):
            return "pond"
        if any(word in label for word in self.DRAINAGE_KEYWORDS):
            return "drainage"
        if any(word in label for word in self.UTILITY_KEYWORDS):
            return "utility"
        if any(word in label for word in self.BRIDGE_KEYWORDS):
            return "bridge"
        if any(word in label for word in self.STRUCTURE_KEYWORDS):
            return "structure"
        if "corridor" in label:
            return "corridor"

        return None

    def _classify_stroke(self, label: str, kind: str, meta: Dict[str, Any]) -> Optional[str]:
        explicit = str(meta.get("category", "")).strip().lower()
        if explicit:
            return explicit

        kind_l = (kind or "").lower()

        if any(word in label for word in self.FIRE_ACCESS_KEYWORDS) or kind_l == "fire_access":
            return "fire_access"
        if any(word in label for word in self.SIDEWALK_KEYWORDS) or kind_l == "sidewalk":
            return "sidewalk"
        if any(word in label for word in self.DRAINAGE_KEYWORDS) or kind_l in {"pipe", "drainage"}:
            return "drainage"
        if any(word in label for word in self.UTILITY_KEYWORDS) or kind_l == "utility":
            return "utility"
        if any(word in label for word in self.ROAD_KEYWORDS) or kind_l in {"centerline", "alignment", "route", "road"}:
            return "road"

        if self._looks_like_centerline(label, kind, meta):
            return "road"

        return None

    def _classify_point(self, label: str, kind: str, meta: Dict[str, Any]) -> Optional[str]:
        explicit = str(meta.get("category", "")).strip().lower()
        if explicit:
            return explicit

        kind_l = (kind or "").lower()

        if any(word in label for word in self.BUILDING_KEYWORDS) or kind_l == "building":
            return "building"
        if any(word in label for word in self.DRAINAGE_KEYWORDS) or kind_l in {"inlet", "manhole", "drain"}:
            return "drainage"
        if any(word in label for word in self.UTILITY_KEYWORDS) or kind_l in {"utility", "hydrant", "valve"}:
            return "utility"
        if any(word in label for word in self.ROAD_KEYWORDS):
            return "road"
        if any(word in label for word in self.BRIDGE_KEYWORDS):
            return "bridge"
        if any(word in label for word in self.STRUCTURE_KEYWORDS):
            return "structure"

        return None

    def _classify_text(self, label: str, kind: str, meta: Dict[str, Any]) -> Optional[str]:
        explicit = str(meta.get("category", "")).strip().lower()
        if explicit:
            return explicit

        if any(word in label for word in self.BUILDING_KEYWORDS):
            return "building"
        if any(word in label for word in self.PARKING_KEYWORDS):
            return "parking"
        if any(word in label for word in self.FIRE_ACCESS_KEYWORDS):
            return "fire_access"
        if any(word in label for word in self.SIDEWALK_KEYWORDS):
            return "sidewalk"
        if any(word in label for word in self.POND_KEYWORDS):
            return "pond"
        if any(word in label for word in self.DRAINAGE_KEYWORDS):
            return "drainage"
        if any(word in label for word in self.UTILITY_KEYWORDS):
            return "utility"
        if any(word in label for word in self.ROAD_KEYWORDS):
            return "road"
        if any(word in label for word in self.PAD_KEYWORDS):
            return "pad"
        if any(word in label for word in self.SITE_BOUNDARY_KEYWORDS):
            return "site"
        if any(word in label for word in self.BRIDGE_KEYWORDS):
            return "bridge"
        if any(word in label for word in self.STRUCTURE_KEYWORDS):
            return "structure"

        return None

    def _looks_like_obstacle(self, label: str, kind: str, meta: Dict[str, Any]) -> bool:
        if meta.get("is_obstacle") is True:
            return True
        if (kind or "").lower() in {"obstacle", "keepout", "wall"}:
            return True
        return any(word in label for word in self.OBSTACLE_KEYWORDS)

    def _looks_like_centerline(self, label: str, kind: str, meta: Dict[str, Any]) -> bool:
        if meta.get("is_centerline") is True:
            return True
        if (kind or "").lower() in {"centerline", "alignment", "route"}:
            return True
        return any(word in label for word in self.CENTERLINE_KEYWORDS)

    def _looks_like_object(self, label: str, kind: str, meta: Dict[str, Any]) -> bool:
        if meta.get("is_object") is True:
            return True
        if (kind or "").lower() in {
            "fixture",
            "equipment",
            "object",
            "anchor",
            "inlet",
            "manhole",
            "column",
            "beam",
            "pier",
            "abutment",
            "hydrant",
            "valve",
            "building",
            "pump",
        }:
            return True
        return any(word in label for word in self.OBJECT_KEYWORDS)

    def _object_kind_from_category(self, category: Optional[str], fallback_kind: str) -> str:
        if category == "building":
            return "building_anchor"
        if category == "drainage":
            return "drainage_object"
        if category == "utility":
            return "utility_object"
        if category == "road":
            return "roadway_anchor"
        if category == "parking":
            return "parking_anchor"
        if category == "pond":
            return "pond_anchor"
        if category == "pad":
            return "pad_anchor"
        if category == "fire_access":
            return "fire_access_anchor"
        if category == "sidewalk":
            return "sidewalk_anchor"
        if category == "bridge":
            return "bridge_anchor"
        if category == "structure":
            return "structure_anchor"
        if category == "corridor":
            return "corridor_anchor"
        return fallback_kind or "sketch_object"

    def _bucket_zone(self, parsed: ParsedSketch, zone: Zone, category: Optional[str]) -> None:
        if category == "site":
            parsed.site_regions.append(zone)
        elif category == "building":
            parsed.building_regions.append(zone)
        elif category == "parking":
            parsed.parking_regions.append(zone)
        elif category == "road":
            parsed.road_regions.append(zone)
        elif category == "pad":
            parsed.pad_regions.append(zone)
        elif category == "pond":
            parsed.pond_regions.append(zone)
        elif category == "drainage":
            parsed.drainage_regions.append(zone)
        elif category == "utility":
            parsed.utility_regions.append(zone)
        elif category == "bridge":
            parsed.bridge_regions.append(zone)
        elif category == "structure":
            parsed.structure_regions.append(zone)
        elif category == "corridor":
            parsed.corridor_regions.append(zone)

    def _bucket_object(self, parsed: ParsedSketch, obj: EngineeringObject, category: Optional[str]) -> None:
        if category == "building":
            parsed.building_objects.append(obj)
        elif category == "drainage" or obj.kind.startswith("drainage"):
            parsed.drainage_objects.append(obj)
        elif category == "utility" or obj.kind.startswith("utility"):
            parsed.utility_objects.append(obj)
        elif category == "road" or obj.kind.startswith("roadway"):
            parsed.roadway_objects.append(obj)
        elif category == "bridge" or obj.kind.startswith("bridge"):
            parsed.bridge_objects.append(obj)
        elif category == "structure" or obj.kind.startswith("structure"):
            parsed.structure_objects.append(obj)

    def _largest_zone(self, zones: Sequence[Zone]) -> Optional[Zone]:
        best: Optional[Zone] = None
        best_area = -1.0
        for zone in zones:
            area = self._polygon_area(zone.boundary)
            if area > best_area:
                best_area = area
                best = zone
        return best

    def _polygon_area(self, polygon: Polygon2D) -> float:
        pts = polygon.points
        if len(pts) < 3:
            return 0.0

        area = 0.0
        for i in range(len(pts)):
            x1, y1 = pts[i].x, pts[i].y
            x2, y2 = pts[(i + 1) % len(pts)].x, pts[(i + 1) % len(pts)].y
            area += (x1 * y2) - (x2 * y1)
        return abs(area) * 0.5

    def _polygon_centroid(self, polygon: Polygon2D) -> Optional[Point2D]:
        pts = polygon.points
        if len(pts) < 3:
            return None

        area_factor = 0.0
        cx = 0.0
        cy = 0.0

        for i in range(len(pts)):
            x0, y0 = pts[i].x, pts[i].y
            x1, y1 = pts[(i + 1) % len(pts)].x, pts[(i + 1) % len(pts)].y
            cross = (x0 * y1) - (x1 * y0)
            area_factor += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross

        if abs(area_factor) < 1e-9:
            sx = sum(p.x for p in pts) / len(pts)
            sy = sum(p.y for p in pts) / len(pts)
            return Point2D(sx, sy)

        area_factor *= 0.5
        cx /= (6.0 * area_factor)
        cy /= (6.0 * area_factor)
        return Point2D(cx, cy)

    def _polyline_midpoint(self, polyline: Polyline2D) -> Optional[Point2D]:
        pts = polyline.points
        if not pts:
            return None
        if len(pts) == 1:
            return pts[0]
        return pts[len(pts) // 2]

    def _zone_layer(self, zone: Zone) -> str:
        zone_type = zone.zone_type.value.lower()
        tags = {t.lower() for t in zone.tags}

        if "building" in tags or "building" in zone_type:
            return "SKETCH_BLDG"
        if "parking" in tags or "parking" in zone_type:
            return "SKETCH_PARK"
        if "road" in tags or "road" in zone_type:
            return "SKETCH_ROAD"
        if "drainage" in tags or "drainage" in zone_type:
            return "SKETCH_DRAIN"
        if "utility" in tags or "utility" in zone_type:
            return "SKETCH_UTIL"
        if "pad" in tags or "pad" in zone_type:
            return "SKETCH_PAD"
        if "bridge" in tags or "bridge" in zone_type:
            return "SKETCH_BRIDGE"
        if "structure" in tags or "structure" in zone_type:
            return "SKETCH_STRUCT"
        return "SKETCH_ZONE"

    def _object_layer(self, obj: EngineeringObject) -> str:
        kind = (obj.kind or "").lower()
        tags = {t.lower() for t in obj.tags}

        if "building" in kind or "building" in tags:
            return "SKETCH_BLDG_PTS"
        if "drainage" in kind or "drainage" in tags:
            return "SKETCH_DRAIN_PTS"
        if "utility" in kind or "utility" in tags:
            return "SKETCH_UTIL_PTS"
        if "road" in kind or "road" in tags:
            return "SKETCH_ROAD_PTS"
        if "bridge" in kind or "bridge" in tags:
            return "SKETCH_BRIDGE_PTS"
        if "structure" in kind or "structure" in tags:
            return "SKETCH_STRUCT_PTS"
        return "SKETCH_PTS"


def parse_sketch(sketch: SketchInput) -> ParsedSketch:
    return SketchParser().parse(sketch)


def parse_sketch_dict(data: Dict[str, Any]) -> ParsedSketch:
    parser = SketchParser()
    sketch = parser.from_dict(data)
    return parser.parse(sketch)