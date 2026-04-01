# geometry/geometry_actions.py

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple

from core.utils import safe_num, safe_text


PointLike = Tuple[float, float]


def _xy(point: PointLike) -> List[float]:
    return [safe_num(point[0]), safe_num(point[1])]


def _clean_points(points: Sequence[PointLike]) -> List[List[float]]:
    cleaned: List[List[float]] = []
    for p in points:
        if p is None or len(p) < 2:
            continue
        cleaned.append(_xy((p[0], p[1])))
    return cleaned


def _base_action(task: str) -> Dict[str, Any]:
    return {
        "task": task,
        "origin": None,
        "points": None,
        "closed": None,
        "width": None,
        "height": None,
        "label": None,
        "layer": None,
        "text": None,
        "text_height": None,
        "center": None,
        "radius": None,
        "start_angle": None,
        "end_angle": None,
    }


def rect_action(
    origin: PointLike,
    width: float,
    height: float,
    label: str = "",
    layer: str = "SITE",
) -> Dict[str, Any]:
    action = _base_action("rectangle")
    action["origin"] = _xy(origin)
    action["width"] = safe_num(width)
    action["height"] = safe_num(height)
    action["label"] = safe_text(label, "")
    action["layer"] = safe_text(layer, "SITE")
    return action


def rect_from_corners_action(
    lower_left: PointLike,
    upper_right: PointLike,
    label: str = "",
    layer: str = "SITE",
) -> Dict[str, Any]:
    x1 = safe_num(lower_left[0])
    y1 = safe_num(lower_left[1])
    x2 = safe_num(upper_right[0])
    y2 = safe_num(upper_right[1])

    x = min(x1, x2)
    y = min(y1, y2)
    w = abs(x2 - x1)
    h = abs(y2 - y1)

    return rect_action((x, y), w, h, label=label, layer=layer)


def arc_action(
    center: PointLike,
    radius: float,
    start_angle: float,
    end_angle: float,
    label: str = "",
    layer: str = "PAVEMENT",
) -> Dict[str, Any]:
    action = _base_action("arc")
    action["center"] = _xy(center)
    action["radius"] = safe_num(radius)
    action["start_angle"] = safe_num(start_angle)
    action["end_angle"] = safe_num(end_angle)
    action["label"] = safe_text(label, "")
    action["layer"] = safe_text(layer, "PAVEMENT")
    return action


def text_action(
    origin: PointLike,
    text: str,
    height: float = 2.0,
    layer: str = "ANNO",
) -> Dict[str, Any]:
    action = _base_action("text_note")
    action["origin"] = _xy(origin)
    action["layer"] = safe_text(layer, "ANNO")
    action["text"] = safe_text(text, "")
    action["text_height"] = safe_num(height)
    return action


def point_action(
    origin: PointLike,
    label: str = "",
    layer: str = "SYMBOL",
) -> Dict[str, Any]:
    action = _base_action("point")
    action["origin"] = _xy(origin)
    action["label"] = safe_text(label, "")
    action["layer"] = safe_text(layer, "SYMBOL")
    return action


def north_arrow_action(
    origin: PointLike,
    layer: str = "SYMBOL",
) -> Dict[str, Any]:
    action = _base_action("north_arrow")
    action["origin"] = _xy(origin)
    action["label"] = "N"
    action["layer"] = safe_text(layer, "SYMBOL")
    return action


def polyline_action(
    points: Sequence[PointLike],
    label: str = "",
    layer: str = "PAVEMENT",
    closed: bool = False,
) -> Dict[str, Any]:
    clean_points = _clean_points(points)
    if len(clean_points) < 2:
        raise ValueError("polyline_action requires at least 2 valid points.")

    action = _base_action("polygon" if closed else "polyline")
    action["points"] = clean_points
    action["closed"] = bool(closed)
    action["label"] = safe_text(label, "")
    action["layer"] = safe_text(layer, "PAVEMENT")
    return action


def polygon_action(
    points: Sequence[PointLike],
    label: str = "",
    layer: str = "SITE",
) -> Dict[str, Any]:
    clean_points = _clean_points(points)
    if len(clean_points) < 3:
        raise ValueError("polygon_action requires at least 3 valid points.")

    action = _base_action("polygon")
    action["points"] = clean_points
    action["closed"] = True
    action["label"] = safe_text(label, "")
    action["layer"] = safe_text(layer, "SITE")
    return action


def circle_action(
    center: PointLike,
    radius: float,
    label: str = "",
    layer: str = "SITE",
) -> Dict[str, Any]:
    action = _base_action("circle")
    action["center"] = _xy(center)
    action["radius"] = safe_num(radius)
    action["label"] = safe_text(label, "")
    action["layer"] = safe_text(layer, "SITE")
    return action


def center_label_action(
    rect_origin: PointLike,
    width: float,
    height: float,
    text: str,
    text_height: float = 2.0,
    layer: str = "ANNO",
) -> Dict[str, Any]:
    x = safe_num(rect_origin[0]) + safe_num(width) / 2.0
    y = safe_num(rect_origin[1]) + safe_num(height) / 2.0
    return text_action((x, y), text=text, height=text_height, layer=layer)


def chain_actions(*action_groups: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for group in action_groups:
        for action in group:
            out.append(action)
    return out