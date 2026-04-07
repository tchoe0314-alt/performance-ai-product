from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from math import hypot, isclose, pi
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)
import copy
import uuid


EPS = 1e-9
MIN_GEOMETRY_SIZE = 1e-6
_SNAPSHOT_MAX_DEPTH = 10


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _snapshot_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _snapshot_fallback(value: Any) -> Any:
    if _snapshot_scalar(value):
        return value
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        try:
            return value.to_dict()
        except Exception:
            pass
    if hasattr(value, "as_tuple") and callable(getattr(value, "as_tuple")):
        try:
            return list(value.as_tuple())
        except Exception:
            pass
    return repr(value)


def _snapshot_serialize(value: Any, *, _active: Optional[set[int]] = None, _depth: int = 0) -> Any:
    if _snapshot_scalar(value):
        return value
    if isinstance(value, Enum):
        return value.value

    if _depth >= _SNAPSHOT_MAX_DEPTH:
        return _snapshot_fallback(value)

    active = _active if _active is not None else set()
    needs_guard = is_dataclass(value) or isinstance(value, (dict, list, tuple, set)) or hasattr(value, "__dict__")
    value_id = id(value) if needs_guard else None
    if value_id is not None:
        if value_id in active:
            return _snapshot_fallback(value)
        active.add(value_id)

    try:
        if is_dataclass(value):
            payload: Dict[str, Any] = {}
            for f in fields(value):
                payload[f.name] = _snapshot_serialize(
                    getattr(value, f.name),
                    _active=active,
                    _depth=_depth + 1,
                )
            return payload
        if isinstance(value, dict):
            payload = {}
            for k, v in value.items():
                key = str(k) if not _snapshot_scalar(k) else k
                payload[key] = _snapshot_serialize(v, _active=active, _depth=_depth + 1)
            return payload
        if isinstance(value, (list, tuple, set)):
            return [_snapshot_serialize(v, _active=active, _depth=_depth + 1) for v in value]
        return copy.deepcopy(value)
    except Exception:
        return _snapshot_fallback(value)
    finally:
        if value_id is not None:
            active.discard(value_id)


def _snapshot_restore_value(expected_type: Any, value: Any) -> Any:
    if value is None:
        return None

    origin = get_origin(expected_type)
    args = get_args(expected_type)

    if origin is Union:
        non_none = [arg for arg in args if arg is not type(None)]
        for arg in non_none:
            try:
                restored = _snapshot_restore_value(arg, value)
                if restored is not None or value is None:
                    return restored
            except Exception:
                continue
        return copy.deepcopy(value)

    if origin in (list, List, Sequence, Iterable, tuple, set):
        inner = args[0] if args else Any
        seq = value if isinstance(value, (list, tuple, set)) else []
        restored_items = [_snapshot_restore_value(inner, item) for item in seq]
        if origin in (tuple,):
            return tuple(restored_items)
        if origin in (set,):
            return set(restored_items)
        return restored_items

    if origin in (dict, Dict):
        key_type = args[0] if len(args) > 0 else Any
        val_type = args[1] if len(args) > 1 else Any
        if not isinstance(value, dict):
            return {}
        out = {}
        for k, v in value.items():
            rk = _snapshot_restore_value(key_type, k) if key_type is not Any else k
            rv = _snapshot_restore_value(val_type, v) if val_type is not Any else copy.deepcopy(v)
            out[rk] = rv
        return out

    if expected_type is Any or expected_type is None:
        return copy.deepcopy(value)

    if isinstance(expected_type, type) and issubclass(expected_type, Enum):
        try:
            return expected_type(value)
        except Exception:
            for member in expected_type:
                if member.name == value:
                    return member
            raise

    if isinstance(expected_type, type) and is_dataclass(expected_type):
        if not isinstance(value, dict):
            return copy.deepcopy(value)
        hints = get_type_hints(expected_type)
        kwargs = {}
        for f in fields(expected_type):
            if f.name in value:
                field_type = hints.get(f.name, f.type)
                kwargs[f.name] = _snapshot_restore_value(field_type, value[f.name])
        return expected_type(**kwargs)

    return copy.deepcopy(value)


def _require_number(value: Any, field_name: str) -> float:
    try:
        return float(value)
    except Exception as exc:
        raise ValueError(f"{field_name} must be numeric.") from exc


def _require_positive(value: Any, field_name: str, allow_zero: bool = False) -> float:
    value = _require_number(value, field_name)
    if allow_zero:
        if value < 0.0:
            raise ValueError(f"{field_name} must be >= 0.")
    else:
        if value <= 0.0:
            raise ValueError(f"{field_name} must be > 0.")
    return value


# ============================================================================
# Basic geometry
# ============================================================================

@dataclass(frozen=True)
class Point2D:
    x: float
    y: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", float(self.x))
        object.__setattr__(self, "y", float(self.y))

    def as_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def distance_to(self, other: "Point2D") -> float:
        return hypot(self.x - other.x, self.y - other.y)

    def translate(self, dx: float, dy: float) -> "Point2D":
        return Point2D(self.x + dx, self.y + dy)

    def midpoint(self, other: "Point2D") -> "Point2D":
        return Point2D((self.x + other.x) / 2.0, (self.y + other.y) / 2.0)

    def moved(self, dx: float, dy: float) -> "Point2D":
        return self.translate(dx, dy)

    def almost_equals(self, other: "Point2D", tol: float = EPS) -> bool:
        return abs(self.x - other.x) <= tol and abs(self.y - other.y) <= tol


@dataclass(frozen=True)
class Point3D:
    x: float
    y: float
    z: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", float(self.x))
        object.__setattr__(self, "y", float(self.y))
        object.__setattr__(self, "z", float(self.z))

    def as_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def as_2d(self) -> Point2D:
        return Point2D(self.x, self.y)

    def translate(self, dx: float, dy: float, dz: float = 0.0) -> "Point3D":
        return Point3D(self.x + dx, self.y + dy, self.z + dz)

    def moved(self, dx: float, dy: float, dz: float = 0.0) -> "Point3D":
        return self.translate(dx, dy, dz)

    def distance_to(self, other: "Point3D") -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2) ** 0.5


@dataclass(frozen=True)
class Vector2D:
    dx: float
    dy: float

    @property
    def length(self) -> float:
        return hypot(self.dx, self.dy)

    def normalized(self) -> "Vector2D":
        length = self.length
        if length < EPS:
            return Vector2D(0.0, 0.0)
        return Vector2D(self.dx / length, self.dy / length)

    def scale(self, factor: float) -> "Vector2D":
        return Vector2D(self.dx * factor, self.dy * factor)


@dataclass(frozen=True)
class BoundingBox2D:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def __post_init__(self) -> None:
        if self.max_x < self.min_x or self.max_y < self.min_y:
            raise ValueError("BoundingBox2D max values must be >= min values.")

    @classmethod
    def from_points(cls, points: Sequence[Point2D]) -> "BoundingBox2D":
        if not points:
            raise ValueError("Cannot build bounding box from empty point list.")
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        return cls(min(xs), min(ys), max(xs), max(ys))

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def center(self) -> Point2D:
        return Point2D((self.min_x + self.max_x) / 2.0, (self.min_y + self.max_y) / 2.0)

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)

    def contains_point(self, pt: Point2D, inclusive: bool = True) -> bool:
        if inclusive:
            return (
                self.min_x - EPS <= pt.x <= self.max_x + EPS
                and self.min_y - EPS <= pt.y <= self.max_y + EPS
            )
        return (
            self.min_x + EPS < pt.x < self.max_x - EPS
            and self.min_y + EPS < pt.y < self.max_y - EPS
        )

    def intersects(self, other: "BoundingBox2D") -> bool:
        return not (
            self.max_x < other.min_x
            or self.min_x > other.max_x
            or self.max_y < other.min_y
            or self.min_y > other.max_y
        )

    def expanded(self, margin: float) -> "BoundingBox2D":
        margin = _require_positive(margin, "margin", allow_zero=True)
        return BoundingBox2D(
            self.min_x - margin,
            self.min_y - margin,
            self.max_x + margin,
            self.max_y + margin,
        )

    def translate(self, dx: float, dy: float) -> "BoundingBox2D":
        return BoundingBox2D(
            self.min_x + dx,
            self.min_y + dy,
            self.max_x + dx,
            self.max_y + dy,
        )


@dataclass(frozen=True)
class LineSegment2D:
    start: Point2D
    end: Point2D

    def __post_init__(self) -> None:
        if self.start.distance_to(self.end) < MIN_GEOMETRY_SIZE:
            raise ValueError("LineSegment2D is too small.")

    @property
    def length(self) -> float:
        return self.start.distance_to(self.end)

    @property
    def bbox(self) -> BoundingBox2D:
        return BoundingBox2D.from_points([self.start, self.end])

    def midpoint(self) -> Point2D:
        return self.start.midpoint(self.end)

    def is_axis_aligned(self) -> bool:
        return isclose(self.start.x, self.end.x, abs_tol=EPS) or isclose(
            self.start.y, self.end.y, abs_tol=EPS
        )

    def translate(self, dx: float, dy: float) -> "LineSegment2D":
        return LineSegment2D(self.start.translate(dx, dy), self.end.translate(dx, dy))

    def contains_point(self, point: Point2D, tol: float = EPS) -> bool:
        cross = ((point.y - self.start.y) * (self.end.x - self.start.x)) - (
            (point.x - self.start.x) * (self.end.y - self.start.y)
        )
        if abs(cross) > tol:
            return False

        dot = ((point.x - self.start.x) * (self.end.x - self.start.x)) + (
            (point.y - self.start.y) * (self.end.y - self.start.y)
        )
        if dot < -tol:
            return False

        seg_len_sq = (self.end.x - self.start.x) ** 2 + (self.end.y - self.start.y) ** 2
        if dot > seg_len_sq + tol:
            return False

        return True


@dataclass
class Polyline2D:
    points: List[Point2D]
    closed: bool = False

    def __post_init__(self) -> None:
        self.points = [p if isinstance(p, Point2D) else Point2D(*p) for p in self.points]
        self._validate_points()

    def _validate_points(self) -> None:
        if len(self.points) < 2:
            raise ValueError("Polyline2D requires at least 2 points.")
        total_length = 0.0
        for i in range(len(self.points) - 1):
            total_length += self.points[i].distance_to(self.points[i + 1])
        if self.closed and len(self.points) > 2:
            total_length += self.points[-1].distance_to(self.points[0])
        if total_length < MIN_GEOMETRY_SIZE:
            raise ValueError("Polyline2D total length is too small.")

    @property
    def segments(self) -> List[LineSegment2D]:
        segs = [
            LineSegment2D(self.points[i], self.points[i + 1])
            for i in range(len(self.points) - 1)
            if self.points[i].distance_to(self.points[i + 1]) > MIN_GEOMETRY_SIZE
        ]
        if self.closed and len(self.points) > 2 and self.points[-1].distance_to(self.points[0]) > MIN_GEOMETRY_SIZE:
            segs.append(LineSegment2D(self.points[-1], self.points[0]))
        return segs

    @property
    def length(self) -> float:
        return sum(seg.length for seg in self.segments)

    @property
    def bbox(self) -> BoundingBox2D:
        return BoundingBox2D.from_points(self.points)

    def centroid(self) -> Point2D:
        x = sum(p.x for p in self.points) / len(self.points)
        y = sum(p.y for p in self.points) / len(self.points)
        return Point2D(x, y)

    def translate(self, dx: float, dy: float) -> "Polyline2D":
        return Polyline2D(points=[p.translate(dx, dy) for p in self.points], closed=self.closed)

    def move_in_place(self, dx: float, dy: float) -> None:
        self.points = [p.translate(dx, dy) for p in self.points]


@dataclass
class Polygon2D:
    points: List[Point2D]

    def __post_init__(self) -> None:
        self.points = [p if isinstance(p, Point2D) else Point2D(*p) for p in self.points]
        self._validate_polygon()

    def _validate_polygon(self) -> None:
        if len(self.points) < 3:
            raise ValueError("Polygon2D requires at least 3 points.")
        unique: List[Point2D] = []
        for p in self.points:
            if not any(p.almost_equals(existing) for existing in unique):
                unique.append(p)
        if len(unique) < 3:
            raise ValueError("Polygon2D requires at least 3 distinct points.")
        if self.area < MIN_GEOMETRY_SIZE:
            raise ValueError("Polygon2D area is too small or degenerate.")

    @property
    def bbox(self) -> BoundingBox2D:
        return BoundingBox2D.from_points(self.points)

    @property
    def edges(self) -> List[LineSegment2D]:
        return [
            LineSegment2D(self.points[i], self.points[(i + 1) % len(self.points)])
            for i in range(len(self.points))
            if self.points[i].distance_to(self.points[(i + 1) % len(self.points)]) > MIN_GEOMETRY_SIZE
        ]

    @property
    def area(self) -> float:
        total = 0.0
        n = len(self.points)
        for i in range(n):
            x1, y1 = self.points[i].as_tuple()
            x2, y2 = self.points[(i + 1) % n].as_tuple()
            total += (x1 * y2) - (x2 * y1)
        return abs(total) * 0.5

    def centroid(self) -> Point2D:
        total_cross = 0.0
        cx = 0.0
        cy = 0.0
        n = len(self.points)

        for i in range(n):
            x0, y0 = self.points[i].as_tuple()
            x1, y1 = self.points[(i + 1) % n].as_tuple()
            cross = x0 * y1 - x1 * y0
            total_cross += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross

        if abs(total_cross) < EPS:
            x = sum(p.x for p in self.points) / len(self.points)
            y = sum(p.y for p in self.points) / len(self.points)
            return Point2D(x, y)

        total_cross *= 0.5
        cx /= (6.0 * total_cross)
        cy /= (6.0 * total_cross)
        return Point2D(cx, cy)

    def contains_point(self, point: Point2D) -> bool:
        if not self.bbox.contains_point(point, inclusive=True):
            return False

        x, y = point.x, point.y
        inside = False
        n = len(self.points)
        for i in range(n):
            p1 = self.points[i]
            p2 = self.points[(i + 1) % n]

            edge = LineSegment2D(p1, p2)
            if edge.contains_point(point):
                return True

            if ((p1.y > y) != (p2.y > y)) and (
                x < (p2.x - p1.x) * (y - p1.y) / ((p2.y - p1.y) + EPS) + p1.x
            ):
                inside = not inside
        return inside

    def translate(self, dx: float, dy: float) -> "Polygon2D":
        return Polygon2D([p.translate(dx, dy) for p in self.points])

    def move_in_place(self, dx: float, dy: float) -> None:
        self.points = [p.translate(dx, dy) for p in self.points]


@dataclass(frozen=True)
class Circle2D:
    center: Point2D
    radius: float

    def __post_init__(self) -> None:
        if self.radius <= 0.0:
            raise ValueError("Circle2D.radius must be > 0.")

    @property
    def area(self) -> float:
        return pi * self.radius * self.radius

    @property
    def bbox(self) -> BoundingBox2D:
        return BoundingBox2D(
            self.center.x - self.radius,
            self.center.y - self.radius,
            self.center.x + self.radius,
            self.center.y + self.radius,
        )

    def contains_point(self, point: Point2D) -> bool:
        return self.center.distance_to(point) <= self.radius + EPS

    def translate(self, dx: float, dy: float) -> "Circle2D":
        return Circle2D(self.center.translate(dx, dy), self.radius)


# ============================================================================
# Units
# ============================================================================

class UnitSystem(str, Enum):
    FT = "ft"
    IN = "in"
    M = "m"
    MM = "mm"
    CM = "cm"
    KM = "km"
    YD = "yd"


_UNIT_TO_METERS = {
    UnitSystem.FT.value: 0.3048,
    UnitSystem.IN.value: 0.0254,
    UnitSystem.M.value: 1.0,
    UnitSystem.MM.value: 0.001,
    UnitSystem.CM.value: 0.01,
    UnitSystem.KM.value: 1000.0,
    UnitSystem.YD.value: 0.9144,
}


def normalize_unit(unit: Union[str, UnitSystem]) -> UnitSystem:
    if isinstance(unit, UnitSystem):
        return unit
    text = str(unit).strip().lower()
    aliases = {
        "feet": UnitSystem.FT,
        "foot": UnitSystem.FT,
        "ft": UnitSystem.FT,
        "inches": UnitSystem.IN,
        "inch": UnitSystem.IN,
        "in": UnitSystem.IN,
        "meters": UnitSystem.M,
        "meter": UnitSystem.M,
        "m": UnitSystem.M,
        "millimeters": UnitSystem.MM,
        "mm": UnitSystem.MM,
        "centimeters": UnitSystem.CM,
        "cm": UnitSystem.CM,
        "kilometers": UnitSystem.KM,
        "km": UnitSystem.KM,
        "yards": UnitSystem.YD,
        "yard": UnitSystem.YD,
        "yd": UnitSystem.YD,
    }
    if text in aliases:
        return aliases[text]
    for candidate in UnitSystem:
        if candidate.value == text:
            return candidate
    raise ValueError(f"Unsupported unit '{unit}'.")


def convert_value(value: float, from_unit: Union[str, UnitSystem], to_unit: Union[str, UnitSystem]) -> float:
    source = normalize_unit(from_unit)
    target = normalize_unit(to_unit)
    meters = float(value) * _UNIT_TO_METERS[source.value]
    return meters / _UNIT_TO_METERS[target.value]


# ============================================================================
# Engineering / planning models
# ============================================================================

class EngineeringDomain(str, Enum):
    GENERAL = "general"
    BUILDING = "building"
    ROAD = "road"
    BRIDGE = "bridge"
    SITE = "site"
    DRAINAGE = "drainage"
    UTILITY = "utility"
    STRUCTURE = "structure"
    SUBDIVISION = "subdivision"


class ZoneType(str, Enum):
    UNKNOWN = "unknown"
    SITE = "site"
    LOT = "lot"
    BUILDING = "building"
    PAD = "pad"
    BUILDING_PAD = "building_pad"
    PARKING = "parking"
    ROAD = "road"
    ROADWAY = "roadway"
    CORRIDOR = "corridor"
    DRAINAGE = "drainage"
    DETENTION = "detention"
    UTILITY = "utility"
    STRUCTURE = "structure"
    BRIDGE = "bridge"
    OPEN_SPACE = "open_space"
    EASEMENT = "easement"
    FLOOR = "floor"
    ROOM = "room"


@dataclass
class Zone:
    boundary: Polygon2D
    zone_type: ZoneType = ZoneType.UNKNOWN
    id: str = field(default_factory=lambda: _new_id("zone"))
    name: Optional[str] = None
    level: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def bbox(self) -> BoundingBox2D:
        return self.boundary.bbox

    def contains_point(self, pt: Point2D) -> bool:
        return self.boundary.contains_point(pt)

    def translate(self, dx: float, dy: float) -> None:
        self.boundary.move_in_place(dx, dy)


@dataclass
class Obstacle:
    boundary: Polygon2D
    id: str = field(default_factory=lambda: _new_id("obs"))
    kind: str = "generic"
    name: Optional[str] = None
    clearance: float = 0.0
    level: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.clearance = _require_positive(self.clearance, "Obstacle.clearance", allow_zero=True)

    @property
    def effective_boundary(self) -> BoundingBox2D:
        return self.boundary.bbox.expanded(self.clearance)

    def translate(self, dx: float, dy: float) -> None:
        self.boundary = self.boundary.translate(dx, dy)


@dataclass
class Alignment:
    centerline: Polyline2D
    id: str = field(default_factory=lambda: _new_id("align"))
    name: Optional[str] = None
    station_start: float = 0.0
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.station_start = _require_number(self.station_start, "Alignment.station_start")

    @property
    def length(self) -> float:
        return self.centerline.length

    def translate(self, dx: float, dy: float) -> None:
        self.centerline = self.centerline.translate(dx, dy)


@dataclass
class Corridor:
    alignment_id: str
    width_left: float
    width_right: float
    id: str = field(default_factory=lambda: _new_id("corr"))
    name: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.width_left = _require_positive(self.width_left, "Corridor.width_left", allow_zero=True)
        self.width_right = _require_positive(self.width_right, "Corridor.width_right", allow_zero=True)

    @property
    def total_width(self) -> float:
        return self.width_left + self.width_right


@dataclass
class Level:
    name: str
    elevation: float = 0.0
    id: str = field(default_factory=lambda: _new_id("lvl"))
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.name = str(self.name)
        self.elevation = _require_number(self.elevation, "Level.elevation")


@dataclass
class EngineeringObject:
    kind: str
    anchor: Point3D
    id: str = field(default_factory=lambda: _new_id("obj"))
    name: Optional[str] = None
    level: Optional[str] = None
    boundary: Optional[Polygon2D] = None
    tags: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    domain: EngineeringDomain = EngineeringDomain.GENERAL

    def bbox(self) -> Optional[BoundingBox2D]:
        if self.boundary is not None:
            return self.boundary.bbox
        pt = self.anchor.as_2d()
        return BoundingBox2D(pt.x, pt.y, pt.x, pt.y)

    def validate(self) -> None:
        if not self.kind:
            raise ValueError("EngineeringObject.kind cannot be empty.")
        if self.boundary is not None and self.boundary.area < MIN_GEOMETRY_SIZE:
            raise ValueError(f"EngineeringObject '{self.name or self.id}' has invalid boundary area.")

    def translate(self, dx: float, dy: float, dz: float = 0.0) -> None:
        self.anchor = self.anchor.translate(dx, dy, dz)
        if self.boundary is not None:
            self.boundary = self.boundary.translate(dx, dy)


# ============================================================================
# Review / issue tracking
# ============================================================================

class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class EntityType(str, Enum):
    POINT = "point"
    LINE = "line"
    POLYLINE = "polyline"
    POLYGON = "polygon"
    CIRCLE = "circle"
    TEXT = "text"


@dataclass
class ReviewIssue:
    severity: IssueSeverity
    message: str
    code: str = "GENERIC"
    object_id: Optional[str] = None
    location: Optional[Point2D] = None
    rule_name: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: _new_id("issue"))


# ============================================================================
# Drawing entities
# ============================================================================

@dataclass
class EntityStyle:
    layer: str = "0"
    color: Optional[int] = None
    linetype: Optional[str] = None
    lineweight: Optional[float] = None


@dataclass
class StyleRef(EntityStyle):
    """Backward-compatible alias used by older engine modules."""


@dataclass
class BaseEntity:
    id: str = field(default_factory=lambda: _new_id("ent"))
    style: EntityStyle = field(default_factory=EntityStyle)
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def entity_type(self) -> EntityType:
        return EntityType.POINT

    def bbox(self) -> Optional[BoundingBox2D]:
        return None


@dataclass
class PointEntity(BaseEntity):
    point: Point2D = field(default_factory=lambda: Point2D(0.0, 0.0))

    @property
    def entity_type(self) -> EntityType:
        return EntityType.POINT

    def bbox(self) -> BoundingBox2D:
        return BoundingBox2D(self.point.x, self.point.y, self.point.x, self.point.y)


@dataclass
class LineEntity(BaseEntity):
    segment: LineSegment2D = field(default_factory=lambda: LineSegment2D(Point2D(0.0, 0.0), Point2D(1.0, 0.0)))

    @property
    def entity_type(self) -> EntityType:
        return EntityType.LINE

    def bbox(self) -> BoundingBox2D:
        return self.segment.bbox


@dataclass
class PolylineEntity(BaseEntity):
    polyline: Polyline2D = field(default_factory=lambda: Polyline2D([Point2D(0.0, 0.0), Point2D(1.0, 0.0)]))

    @property
    def entity_type(self) -> EntityType:
        return EntityType.POLYLINE

    def bbox(self) -> BoundingBox2D:
        return self.polyline.bbox


@dataclass
class PolygonEntity(BaseEntity):
    polygon: Polygon2D = field(default_factory=lambda: Polygon2D([Point2D(0.0, 0.0), Point2D(1.0, 0.0), Point2D(0.0, 1.0)]))

    @property
    def entity_type(self) -> EntityType:
        return EntityType.POLYGON

    def bbox(self) -> BoundingBox2D:
        return self.polygon.bbox


@dataclass
class CircleEntity(BaseEntity):
    circle: Circle2D = field(default_factory=lambda: Circle2D(Point2D(0.0, 0.0), 1.0))

    @property
    def entity_type(self) -> EntityType:
        return EntityType.CIRCLE

    def bbox(self) -> BoundingBox2D:
        return self.circle.bbox


@dataclass
class TextEntity(BaseEntity):
    insertion: Point2D = field(default_factory=lambda: Point2D(0.0, 0.0))
    text: str = ""
    height: float = 1.0
    rotation: float = 0.0

    @property
    def entity_type(self) -> EntityType:
        return EntityType.TEXT

    def bbox(self) -> BoundingBox2D:
        return BoundingBox2D(self.insertion.x, self.insertion.y, self.insertion.x, self.insertion.y)


# ============================================================================
# Graphs / routing support
# ============================================================================

@dataclass
class GraphNode:
    point: Point3D
    id: str = field(default_factory=lambda: _new_id("node"))
    name: Optional[str] = None
    kind: str = "node"
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    start_node_id: str
    end_node_id: str
    id: str = field(default_factory=lambda: _new_id("edge"))
    weight: float = 0.0
    geometry: Optional[Polyline2D] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.weight = _require_positive(self.weight, "GraphEdge.weight", allow_zero=True)


@dataclass
class RoutingGraph:
    id: str = field(default_factory=lambda: _new_id("graph"))
    name: Optional[str] = None
    kind: str = "generic"
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: Dict[str, GraphEdge] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: GraphNode) -> str:
        self.nodes[node.id] = node
        return node.id

    def add_edge(self, edge: GraphEdge) -> str:
        self.edges[edge.id] = edge
        return edge.id

    def validate_connectivity(self) -> List[str]:
        issues: List[str] = []
        node_ids = set(self.nodes.keys())
        for edge in self.edges.values():
            if edge.start_node_id not in node_ids:
                issues.append(f"Edge {edge.id} start node missing.")
            if edge.end_node_id not in node_ids:
                issues.append(f"Edge {edge.id} end node missing.")
        return issues


# ============================================================================
# Project model
# ============================================================================

@dataclass
class ProjectModel:
    id: str = field(default_factory=lambda: _new_id("project"))
    name: str = "Untitled Project"
    units: UnitSystem = UnitSystem.FT
    levels: Dict[str, Level] = field(default_factory=dict)
    zones: Dict[str, Zone] = field(default_factory=dict)
    obstacles: Dict[str, Obstacle] = field(default_factory=dict)
    alignments: Dict[str, Alignment] = field(default_factory=dict)
    corridors: Dict[str, Corridor] = field(default_factory=dict)
    objects: Dict[str, EngineeringObject] = field(default_factory=dict)
    graphs: Dict[str, RoutingGraph] = field(default_factory=dict)
    drawing_entities: List[BaseEntity] = field(default_factory=list)
    review_issues: List[ReviewIssue] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def add_level(self, level: Level) -> str:
        self.levels[level.id] = level
        return level.id

    def add_zone(self, zone: Zone) -> str:
        self.zones[zone.id] = zone
        return zone.id

    def add_obstacle(self, obstacle: Obstacle) -> str:
        self.obstacles[obstacle.id] = obstacle
        return obstacle.id

    def add_alignment(self, alignment: Alignment) -> str:
        self.alignments[alignment.id] = alignment
        return alignment.id

    def add_corridor(self, corridor: Corridor) -> str:
        self.corridors[corridor.id] = corridor
        return corridor.id

    def add_object(self, obj: EngineeringObject) -> str:
        self.objects[obj.id] = obj
        return obj.id

    def add_graph(self, graph: RoutingGraph) -> str:
        self.graphs[graph.id] = graph
        return graph.id

    def add_entity(self, entity: BaseEntity) -> str:
        self.drawing_entities.append(entity)
        return entity.id

    def add_issue(self, issue: ReviewIssue) -> str:
        self.review_issues.append(issue)
        return issue.id

    def add_review_issue(self, severity: str, message: str, code: str = "GENERIC", **context: Any) -> str:
        sev = IssueSeverity(str(severity).lower())
        issue = ReviewIssue(severity=sev, message=message, code=code, context=dict(context))
        self.review_issues.append(issue)
        return issue.id

    def all_bboxes(self) -> List[BoundingBox2D]:
        boxes: List[BoundingBox2D] = []

        for zone in self.zones.values():
            boxes.append(zone.bbox)

        for obstacle in self.obstacles.values():
            boxes.append(obstacle.effective_boundary)

        for alignment in self.alignments.values():
            boxes.append(alignment.centerline.bbox)

        for obj in self.objects.values():
            bbox = obj.bbox()
            if bbox is not None:
                boxes.append(bbox)

        for ent in self.drawing_entities:
            if isinstance(ent, PointEntity):
                p = ent.point
                boxes.append(BoundingBox2D(p.x, p.y, p.x, p.y))
            elif isinstance(ent, LineEntity):
                boxes.append(ent.segment.bbox)
            elif isinstance(ent, PolylineEntity):
                boxes.append(ent.polyline.bbox)
            elif isinstance(ent, PolygonEntity):
                boxes.append(ent.polygon.bbox)
            elif isinstance(ent, CircleEntity):
                boxes.append(ent.circle.bbox)
            elif isinstance(ent, TextEntity):
                p = ent.insertion
                boxes.append(BoundingBox2D(p.x, p.y, p.x, p.y))

        return boxes

    def project_bbox(self) -> Optional[BoundingBox2D]:
        boxes = self.all_bboxes()
        if not boxes:
            return None

        return BoundingBox2D(
            min(box.min_x for box in boxes),
            min(box.min_y for box in boxes),
            max(box.max_x for box in boxes),
            max(box.max_y for box in boxes),
        )

    def entities_on_layer(self, layer: str) -> List[BaseEntity]:
        return [e for e in self.drawing_entities if e.style.layer == layer]

    def objects_by_kind(self, kind: str) -> List[EngineeringObject]:
        return [o for o in self.objects.values() if o.kind == kind]

    def objects_by_kind_prefix(self, prefix: str) -> List[EngineeringObject]:
        return [o for o in self.objects.values() if o.kind.startswith(prefix)]

    def zones_by_type(self, zone_type: ZoneType) -> List[Zone]:
        return [z for z in self.zones.values() if z.zone_type == zone_type]

    def graphs_by_kind(self, kind: str) -> List[RoutingGraph]:
        target = str(kind or "").strip().lower()
        return [g for g in self.graphs.values() if str(g.kind).lower() == target]

    def find_object(self, object_id_or_name: str) -> Optional[EngineeringObject]:
        if object_id_or_name in self.objects:
            return self.objects[object_id_or_name]
        target = str(object_id_or_name).strip().lower()
        for obj in self.objects.values():
            if str(obj.name or "").strip().lower() == target:
                return obj
        return None

    def find_zone(self, zone_id_or_name: str) -> Optional[Zone]:
        if zone_id_or_name in self.zones:
            return self.zones[zone_id_or_name]
        target = str(zone_id_or_name).strip().lower()
        for zone in self.zones.values():
            if str(zone.name or "").strip().lower() == target:
                return zone
        return None

    def find_graph(self, graph_id_or_name: str) -> Optional[RoutingGraph]:
        if graph_id_or_name in self.graphs:
            return self.graphs[graph_id_or_name]
        target = str(graph_id_or_name).strip().lower()
        for graph in self.graphs.values():
            if str(graph.name or "").strip().lower() == target:
                return graph
        return None

    def translate_building_group(self, building_name: str, dx: float, dy: float) -> None:
        for zone in self.zones.values():
            zname = str(zone.name or "")
            if zname.startswith(building_name):
                zone.translate(dx, dy)

        for obj in self.objects.values():
            oname = str(obj.name or "")
            bname = str((obj.properties or {}).get("building_name") or "")
            if oname.startswith(building_name) or bname == building_name:
                obj.translate(dx, dy)

    def validate(self) -> List[str]:
        issues: List[str] = []

        for zone in self.zones.values():
            try:
                _ = zone.bbox
            except Exception as exc:
                issues.append(f"Zone {zone.name or zone.id} invalid: {exc}")

        for obstacle in self.obstacles.values():
            try:
                _ = obstacle.effective_boundary
            except Exception as exc:
                issues.append(f"Obstacle {obstacle.name or obstacle.id} invalid: {exc}")

        for alignment in self.alignments.values():
            try:
                alignment.centerline._validate_points()
            except Exception as exc:
                issues.append(f"Alignment {alignment.name or alignment.id} invalid: {exc}")

        for obj in self.objects.values():
            try:
                obj.validate()
            except Exception as exc:
                issues.append(f"Object {obj.name or obj.id} invalid: {exc}")

        for graph in self.graphs.values():
            issues.extend(graph.validate_connectivity())

        return issues

    def convert_units(self, to_unit: Union[str, UnitSystem]) -> None:
        target = normalize_unit(to_unit)
        if target == self.units:
            return

        def sx(v: float) -> float:
            return convert_value(v, self.units, target)

        for level in self.levels.values():
            level.elevation = sx(level.elevation)

        for zone in self.zones.values():
            zone.boundary = Polygon2D([Point2D(sx(p.x), sx(p.y)) for p in zone.boundary.points])

        for obstacle in self.obstacles.values():
            obstacle.boundary = Polygon2D([Point2D(sx(p.x), sx(p.y)) for p in obstacle.boundary.points])
            obstacle.clearance = sx(obstacle.clearance)

        for alignment in self.alignments.values():
            alignment.centerline = Polyline2D(
                [Point2D(sx(p.x), sx(p.y)) for p in alignment.centerline.points],
                closed=alignment.centerline.closed,
            )
            alignment.station_start = sx(alignment.station_start)

        for corridor in self.corridors.values():
            corridor.width_left = sx(corridor.width_left)
            corridor.width_right = sx(corridor.width_right)

        for obj in self.objects.values():
            obj.anchor = Point3D(sx(obj.anchor.x), sx(obj.anchor.y), sx(obj.anchor.z))
            if obj.boundary is not None:
                obj.boundary = Polygon2D([Point2D(sx(p.x), sx(p.y)) for p in obj.boundary.points])

        for graph in self.graphs.values():
            for node in graph.nodes.values():
                node.point = Point3D(sx(node.point.x), sx(node.point.y), sx(node.point.z))
            for edge in graph.edges.values():
                if edge.geometry is not None:
                    edge.geometry = Polyline2D(
                        [Point2D(sx(p.x), sx(p.y)) for p in edge.geometry.points],
                        closed=edge.geometry.closed,
                    )
                edge.weight = sx(edge.weight)

        for ent in self.drawing_entities:
            if isinstance(ent, PointEntity):
                ent.point = Point2D(sx(ent.point.x), sx(ent.point.y))
            elif isinstance(ent, LineEntity):
                ent.segment = LineSegment2D(
                    Point2D(sx(ent.segment.start.x), sx(ent.segment.start.y)),
                    Point2D(sx(ent.segment.end.x), sx(ent.segment.end.y)),
                )
            elif isinstance(ent, PolylineEntity):
                ent.polyline = Polyline2D([Point2D(sx(p.x), sx(p.y)) for p in ent.polyline.points], closed=ent.polyline.closed)
            elif isinstance(ent, PolygonEntity):
                ent.polygon = Polygon2D([Point2D(sx(p.x), sx(p.y)) for p in ent.polygon.points])
            elif isinstance(ent, CircleEntity):
                ent.circle = Circle2D(Point2D(sx(ent.circle.center.x), sx(ent.circle.center.y)), sx(ent.circle.radius))
            elif isinstance(ent, TextEntity):
                ent.insertion = Point2D(sx(ent.insertion.x), sx(ent.insertion.y))
                ent.height = sx(ent.height)

        self.units = target

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_snapshot_type": "ProjectModel",
            "_snapshot_version": 2,
            **_snapshot_serialize(self),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectModel":
        if not isinstance(data, dict):
            raise TypeError("ProjectModel.from_dict expects a dict.")
        raw = copy.deepcopy(data)
        raw.pop("_snapshot_type", None)
        raw.pop("_snapshot_version", None)
        return _snapshot_restore_value(cls, raw)

    @classmethod
    def from_command(cls, parsed: Dict[str, Any]) -> "ProjectModel":
        if not isinstance(parsed, dict):
            raise TypeError("ProjectModel.from_command expects a dict payload.")

        project = cls(
            name=str(parsed.get("project_name") or parsed.get("name") or "Untitled Project"),
            units=normalize_unit(parsed.get("units", "ft")),
        )
        project.meta["source_payload"] = copy.deepcopy(parsed)
        project.meta["mode"] = parsed.get("mode")
        project.meta["project_type"] = parsed.get("project_type")
        return project


# ============================================================================
# Convenience builders
# ============================================================================

def rect_polygon(x: float, y: float, width: float, height: float) -> Polygon2D:
    width = _require_positive(width, "width")
    height = _require_positive(height, "height")
    return Polygon2D(
        [
            Point2D(x, y),
            Point2D(x + width, y),
            Point2D(x + width, y + height),
            Point2D(x, y + height),
        ]
    )


def rect_zone(
    x: float,
    y: float,
    width: float,
    height: float,
    zone_type: ZoneType,
    name: Optional[str] = None,
    level: Optional[str] = None,
    tags: Optional[List[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Zone:
    return Zone(
        boundary=rect_polygon(x, y, width, height),
        zone_type=zone_type,
        name=name,
        level=level,
        tags=tags or [],
        meta=dict(meta or {}),
    )


def rect_obstacle(
    x: float,
    y: float,
    width: float,
    height: float,
    kind: str = "generic",
    name: Optional[str] = None,
    clearance: float = 0.0,
    level: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Obstacle:
    return Obstacle(
        boundary=rect_polygon(x, y, width, height),
        kind=kind,
        name=name,
        clearance=clearance,
        level=level,
        meta=dict(meta or {}),
    )


def make_polyline(points: Sequence[Tuple[float, float]], closed: bool = False) -> Polyline2D:
    return Polyline2D([Point2D(x, y) for x, y in points], closed=closed)


def make_polygon(points: Sequence[Tuple[float, float]]) -> Polygon2D:
    return Polygon2D([Point2D(x, y) for x, y in points])
Node = GraphNode
NetworkGraph = RoutingGraph
Edge = GraphEdge
