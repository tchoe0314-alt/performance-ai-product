from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
from math import cos, isfinite, radians, sin
from typing import Any, Iterable, Mapping, Sequence

from PIL import Image, ImageDraw


REFERENCE_WIDTH = 1536
REFERENCE_HEIGHT = 1024
REFERENCE_PADDING = 56


@dataclass(frozen=True)
class AiVisualizationReferenceBundle:
    reference_png: bytes
    control_png: bytes
    depth_png: bytes
    manifest: Mapping[str, Any]


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


def _encode_png(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_building(object_type: str) -> bool:
    return object_type == "building" or object_type.endswith("_building")


def _is_point_object(object_type: str) -> bool:
    return object_type in {
        "benchmark",
        "cleanout",
        "hydrant",
        "inlet",
        "junction",
        "manhole",
        "outfall",
        "point",
        "structure",
        "survey_point",
        "utility_pole",
    }


def render_ai_visualization_reference_bundle(
    *,
    site_width_ft: float,
    site_height_ft: float,
    source_objects: Iterable[Mapping[str, Any]],
) -> AiVisualizationReferenceBundle:
    width_ft = max(1.0, _number(site_width_ft, 1000.0))
    height_ft = max(1.0, _number(site_height_ft, 700.0))
    drawable_width = REFERENCE_WIDTH - REFERENCE_PADDING * 2
    drawable_height = REFERENCE_HEIGHT - REFERENCE_PADDING * 2
    scale = min(drawable_width / width_ft, drawable_height / height_ft)
    frame_width = width_ft * scale
    frame_height = height_ft * scale
    offset_x = (REFERENCE_WIDTH - frame_width) / 2
    offset_y = (REFERENCE_HEIGHT - frame_height) / 2

    reference = Image.new("RGB", (REFERENCE_WIDTH, REFERENCE_HEIGHT), (236, 240, 232))
    control = Image.new("L", (REFERENCE_WIDTH, REFERENCE_HEIGHT), 0)
    depth = Image.new("L", (REFERENCE_WIDTH, REFERENCE_HEIGHT), 0)
    reference_draw = ImageDraw.Draw(reference, "RGBA")
    control_draw = ImageDraw.Draw(control)
    depth_draw = ImageDraw.Draw(depth)

    frame = (offset_x, offset_y, offset_x + frame_width, offset_y + frame_height)
    reference_draw.rectangle(frame, fill=(221, 233, 213, 255), outline=(43, 57, 48, 255), width=4)
    control_draw.rectangle(frame, fill=20, outline=150, width=3)
    depth_draw.rectangle(frame, fill=42, outline=42)

    def point(x: float, y: float) -> tuple[float, float]:
        return (offset_x + x * scale, offset_y + y * scale)

    def shape_points(item: Mapping[str, Any]) -> list[tuple[float, float]]:
        geometry = _geometry(item)
        geometry_type = str(item.get("geometryType") or item.get("geometry_type") or "rect").lower()
        if geometry_type == "polygon" and len(geometry) >= 3:
            return [point(x, y) for x, y in geometry]

        x = _number(item.get("x"))
        y = _number(item.get("y"))
        width = max(1.0, _number(item.get("w"), 10.0))
        height = max(1.0, _number(item.get("d"), 10.0))
        center_x = x + width / 2
        center_y = y + height / 2
        angle = radians(_number(item.get("rotation")))
        angle_cos = cos(angle)
        angle_sin = sin(angle)
        corners = [
            (x, y),
            (x + width, y),
            (x + width, y + height),
            (x, y + height),
        ]
        rotated = []
        for corner_x, corner_y in corners:
            dx = corner_x - center_x
            dy = corner_y - center_y
            rotated.append(
                point(
                    center_x + dx * angle_cos - dy * angle_sin,
                    center_y + dx * angle_sin + dy * angle_cos,
                )
            )
        return rotated

    items = [dict(item) for item in source_objects if isinstance(item, Mapping)]
    priority = {
        "road": 1,
        "road_centerline": 1,
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

        if object_type in {"road", "driveway", "road_centerline", "sidewalk", "sidewalk_path"} and len(geometry) >= 2:
            width_ft_hint = max(4.0, _number(item.get("w"), 24.0))
            line_width = max(5, min(70, round(width_ft_hint * scale)))
            path = [point(x, y) for x, y in geometry]
            surface = (74, 82, 88, 255) if object_type != "sidewalk" else (188, 184, 172, 255)
            reference_draw.line(path, fill=surface, width=line_width, joint="curve")
            if object_type not in {"sidewalk", "sidewalk_path"}:
                reference_draw.line(path, fill=(245, 241, 213, 225), width=max(2, line_width // 16), joint="curve")
            control_draw.line(path, fill=255, width=max(3, line_width // 8), joint="curve")
            depth_draw.line(path, fill=58, width=line_width, joint="curve")
            continue

        if object_type in {"utility_corridor", "storm_main", "water_main", "sanitary_main", "force_main"} and len(geometry) >= 2:
            label = str(item.get("label") or "").lower()
            color = (16, 128, 196, 255) if "water" in label else (172, 51, 173, 255) if "sanitary" in label else (35, 117, 151, 255)
            path = [point(x, y) for x, y in geometry]
            reference_draw.line(path, fill=color, width=5, joint="curve")
            control_draw.line(path, fill=220, width=3, joint="curve")
            depth_draw.line(path, fill=45, width=5, joint="curve")
            continue

        center = point(_number(item.get("x")), _number(item.get("y")))
        if _is_point_object(object_type):
            radius = max(4, min(14, round(4 * scale)))
            point_bounds = (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)
            reference_draw.ellipse(point_bounds, fill=(230, 245, 255, 255), outline=(10, 88, 140, 255), width=3)
            control_draw.ellipse(point_bounds, fill=0, outline=255, width=3)
            depth_draw.ellipse(point_bounds, fill=82)
            continue

        shape = shape_points(item)
        if object_type == "parking":
            reference_draw.polygon(shape, fill=(81, 90, 98, 255), outline=(227, 173, 55, 255), width=4)
            control_draw.polygon(shape, fill=35, outline=255, width=4)
            depth_draw.polygon(shape, fill=60)
            stall_count = max(4, min(32, int(_number(item.get("stallCount"), 12))))
            xs = [value[0] for value in shape]
            ys = [value[1] for value in shape]
            left, right = min(xs), max(xs)
            top, bottom = min(ys), max(ys)
            for index in range(stall_count):
                fraction = (index + 1) / (stall_count + 1)
                stripe_x = left + (right - left) * fraction
                reference_draw.line((stripe_x, top + 5, stripe_x, bottom - 5), fill=(248, 250, 252, 210), width=2)
        elif _is_building(object_type):
            shadow = [(x + 7, y + 7) for x, y in shape]
            reference_draw.polygon(shadow, fill=(15, 23, 42, 70))
            reference_draw.polygon(shape, fill=(201, 181, 144, 255), outline=(49, 54, 59, 255), width=5)
            control_draw.polygon(shape, fill=45, outline=255, width=5)
            building_height = max(10.0, _number(item.get("h"), 18.0))
            depth_draw.polygon(shape, fill=max(92, min(245, round(75 + building_height * 3.5))))
        elif object_type in {"basin", "pond", "detention_basin"}:
            reference_draw.polygon(shape, fill=(85, 187, 220, 210), outline=(5, 105, 149, 255), width=5)
            control_draw.polygon(shape, fill=20, outline=255, width=5)
            depth_draw.polygon(shape, fill=18)
        elif object_type in {"landscape", "open_space", "amenity"}:
            reference_draw.polygon(shape, fill=(103, 154, 77, 180), outline=(53, 104, 44, 255), width=3)
            control_draw.polygon(shape, fill=30, outline=210, width=3)
            depth_draw.polygon(shape, fill=48)
        else:
            reference_draw.polygon(shape, fill=(151, 164, 174, 160), outline=(71, 85, 105, 255), width=3)
            control_draw.polygon(shape, fill=30, outline=220, width=3)
            depth_draw.polygon(shape, fill=64)

    reference_png = _encode_png(reference)
    control_png = _encode_png(control.convert("RGB"))
    depth_png = _encode_png(depth.convert("RGB"))
    manifest = {
        "contract": "civora_visual_reference_v2",
        "width": REFERENCE_WIDTH,
        "height": REFERENCE_HEIGHT,
        "object_count": len(items),
        "control_kinds": ["edge", "height_depth"],
        "reference_sha256": _sha256(reference_png),
        "control_sha256": _sha256(control_png),
        "depth_sha256": _sha256(depth_png),
    }
    return AiVisualizationReferenceBundle(
        reference_png=reference_png,
        control_png=control_png,
        depth_png=depth_png,
        manifest=manifest,
    )


def render_ai_visualization_reference(
    *,
    site_width_ft: float,
    site_height_ft: float,
    source_objects: Iterable[Mapping[str, Any]],
) -> bytes:
    return render_ai_visualization_reference_bundle(
        site_width_ft=site_width_ft,
        site_height_ft=site_height_ft,
        source_objects=source_objects,
    ).reference_png
