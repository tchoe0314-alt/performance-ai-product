from __future__ import annotations

from typing import Dict, List, Tuple

from .surface_engine import GridSurface


Point2D = Tuple[float, float]
Segment = Tuple[Point2D, Point2D]


def _interp(p1: Point2D, z1: float, p2: Point2D, z2: float, level: float) -> Point2D:
    if abs(z2 - z1) < 1e-12:
        return p1
    t = (level - z1) / (z2 - z1)
    x = p1[0] + t * (p2[0] - p1[0])
    y = p1[1] + t * (p2[1] - p1[1])
    return (x, y)


def _cell_segments(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    z_bl: float,
    z_br: float,
    z_tr: float,
    z_tl: float,
    level: float,
) -> List[Segment]:
    """
    Marching squares on one cell.
    Corner order:
      tl ---- tr
      |       |
      bl ---- br
    """

    bl = (x0, y0)
    br = (x1, y0)
    tr = (x1, y1)
    tl = (x0, y1)

    edges: List[Point2D] = []

    def crosses(a: float, b: float) -> bool:
        return (a < level <= b) or (b < level <= a)

    if crosses(z_bl, z_br):
        edges.append(_interp(bl, z_bl, br, z_br, level))
    if crosses(z_br, z_tr):
        edges.append(_interp(br, z_br, tr, z_tr, level))
    if crosses(z_tr, z_tl):
        edges.append(_interp(tr, z_tr, tl, z_tl, level))
    if crosses(z_tl, z_bl):
        edges.append(_interp(tl, z_tl, bl, z_bl, level))

    if len(edges) == 2:
        return [(edges[0], edges[1])]

    if len(edges) == 4:
        # ambiguous case — split into two segments
        return [(edges[0], edges[1]), (edges[2], edges[3])]

    return []


def contour_segments(surface: GridSurface, interval: float = 1.0) -> Dict[float, List[Segment]]:
    if interval <= 0:
        raise ValueError("interval must be > 0")

    z_min = min(min(row) for row in surface.values)
    z_max = max(max(row) for row in surface.values)

    start = int(z_min // interval) * interval
    end = int(z_max // interval + 1) * interval

    levels: List[float] = []
    level = start
    while level <= end + 1e-9:
        levels.append(round(level, 6))
        level += interval

    result: Dict[float, List[Segment]] = {lvl: [] for lvl in levels}

    for row in range(surface.nrows - 1):
        y0 = surface.y_at(row)
        y1 = surface.y_at(row + 1)

        for col in range(surface.ncols - 1):
            x0 = surface.x_at(col)
            x1 = surface.x_at(col + 1)

            z_bl = surface.values[row][col]
            z_br = surface.values[row][col + 1]
            z_tl = surface.values[row + 1][col]
            z_tr = surface.values[row + 1][col + 1]

            cell_min = min(z_bl, z_br, z_tr, z_tl)
            cell_max = max(z_bl, z_br, z_tr, z_tl)

            for lvl in levels:
                if cell_min <= lvl <= cell_max:
                    segs = _cell_segments(x0, y0, x1, y1, z_bl, z_br, z_tr, z_tl, lvl)
                    result[lvl].extend(segs)

    return result


def contour_actions(surface: GridSurface, interval: float = 1.0) -> List[Dict]:
    from geometry.geometry_actions import polyline_action, text_action

    segs_by_level = contour_segments(surface, interval=interval)
    actions: List[Dict] = []

    for level, segs in segs_by_level.items():
        for i, (p1, p2) in enumerate(segs):
            actions.append(polyline_action([p1, p2], "", "SURFACE", False))

        if segs:
            p1, p2 = segs[0]
            mx = (p1[0] + p2[0]) / 2.0
            my = (p1[1] + p2[1]) / 2.0
            actions.append(text_action((mx, my), f"{level:.1f}", 1.6, "ANNO"))

    return actions
