from __future__ import annotations

from io import BytesIO
from math import isfinite
from typing import Any, Iterable, Mapping, Sequence

from PIL import Image, ImageDraw


REFERENCE_WIDTH = 1536
REFERENCE_HEIGHT = 1024
REFERENCE_PADDING = 56


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if isfinite(result) else default


def _geometry(item: Mapping[str, Any]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for raw in list(item.get("geometry") or []):
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or len(raw) < 2:
            continue
        x = _number(raw[0], float("nan"))
        y = _number(raw[1], float("nan"))
        if isfinite(x) and isfinite(y):
            points.append((x, y))
    return points


def render_ai_visualization_reference(
    *,
    site_width_ft: float,
    site_height_ft: float,
    source_objects: Iterable[Mapping[str, Any]],
) -> bytes:
    width_ft = max(1.0, _number(site_width_ft, 1000.0))
    height_ft = max(1.0, _number(site_height_ft, 700.0))
    drawable_width = REFERENCE_WIDTH - REFERENCE_PADDING * 2
    drawable_height = REFERENCE_HEIGHT - REFERENCE_PADDING * 2
    scale = min(drawable_width / width_ft, drawable_height / height_ft)
    frame_width = width_ft * scale
    frame_height = height_ft * scale
    offset_x = (REFERENCE_WIDTH - frame_width) / 2
    offset_y = (REFERENCE_HEIGHT - frame_height) / 2

    image = Image.new("RGB", (REFERENCE_WIDTH, REFERENCE_HEIGHT), (236, 240, 232))
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle(
        (offset_x, offset_y, offset_x + frame_width, offset_y + frame_height),
        fill=(221, 233, 213, 255),
        outline=(43, 57, 48, 255),
        width=4,
    )

    def point(x: float, y: float) -> tuple[float, float]:
        return (offset_x + x * scale, offset_y + y * scale)

    def rectangle(item: Mapping[str, Any]) -> tuple[float, float, float, float]:
        x = _number(item.get("x"))
        y = _number(item.get("y"))
        w = max(1.0, _number(item.get("w"), 10.0))
        d = max(1.0, _number(item.get("d"), 10.0))
        left, top = point(x, y)
        right, bottom = point(x + w, y + d)
        return left, top, right, bottom

    items = [dict(item) for item in source_objects if isinstance(item, Mapping)]
    priority = {
        "road": 1,
        "driveway": 1,
        "parking": 2,
        "landscape": 3,
        "open_space": 3,
        "utility_corridor": 4,
        "building": 5,
        "office_building": 5,
        "basin": 6,
        "pond": 6,
    }
    items.sort(key=lambda item: priority.get(str(item.get("type") or "").lower(), 4))

    for item in items:
        object_type = str(item.get("type") or "custom").strip().lower()
        geometry = _geometry(item)
        geometry_type = str(item.get("geometryType") or item.get("geometry_type") or "rect").lower()
        polygon = [point(x, y) for x, y in geometry] if geometry_type == "polygon" and len(geometry) >= 3 else []

        if object_type in {"road", "driveway", "road_centerline", "sidewalk"} and len(geometry) >= 2:
            width_ft_hint = max(4.0, _number(item.get("w"), 24.0))
            line_width = max(5, min(70, round(width_ft_hint * scale)))
            path = [point(x, y) for x, y in geometry]
            draw.line(path, fill=(68, 76, 82, 255), width=line_width, joint="curve")
            draw.line(path, fill=(245, 241, 213, 225), width=max(2, line_width // 16), joint="curve")
            continue

        if object_type == "utility_corridor" and len(geometry) >= 2:
            label = str(item.get("label") or "").lower()
            color = (16, 128, 196, 255) if "water" in label else (172, 51, 173, 255) if "sanitary" in label else (35, 117, 151, 255)
            draw.line([point(x, y) for x, y in geometry], fill=color, width=5, joint="curve")
            continue

        shape = polygon or list(_rect_polygon(rectangle(item)))
        if object_type == "parking":
            draw.polygon(shape, fill=(81, 90, 98, 255), outline=(227, 173, 55, 255), width=4)
            bounds = rectangle(item)
            stall_count = max(4, min(32, int(_number(item.get("stallCount"), 12))))
            for index in range(stall_count):
                fraction = (index + 1) / (stall_count + 1)
                x = bounds[0] + (bounds[2] - bounds[0]) * fraction
                draw.line((x, bounds[1] + 5, x, bounds[3] - 5), fill=(248, 250, 252, 210), width=2)
        elif object_type in {"building", "office_building"} or object_type.endswith("_building"):
            draw.polygon(shape, fill=(201, 181, 144, 255), outline=(49, 54, 59, 255), width=5)
            shadow = [(x + 7, y + 7) for x, y in shape]
            draw.line(shadow + [shadow[0]], fill=(15, 23, 42, 75), width=8, joint="curve")
            draw.line(shape + [shape[0]], fill=(49, 54, 59, 255), width=5, joint="curve")
        elif object_type in {"basin", "pond"}:
            draw.polygon(shape, fill=(85, 187, 220, 210), outline=(5, 105, 149, 255), width=5)
        elif object_type in {"landscape", "open_space", "amenity"}:
            draw.polygon(shape, fill=(103, 154, 77, 180), outline=(53, 104, 44, 255), width=3)
        else:
            draw.polygon(shape, fill=(151, 164, 174, 160), outline=(71, 85, 105, 255), width=3)

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _rect_polygon(bounds: tuple[float, float, float, float]) -> Iterable[tuple[float, float]]:
    left, top, right, bottom = bounds
    yield left, top
    yield right, top
    yield right, bottom
    yield left, bottom
