from __future__ import annotations

import io
import math
import os
from typing import Any, Dict, Optional, Tuple

from PIL import Image
from backend.services.outbound_http import safe_get

from engines.surface_engine import GridSurface

# Match the grading caller's existing intended sampling envelope. Enforce it
# again at the provider boundary rather than trusting every caller to coarsen.
MAX_TERRAIN_GRID_CELLS = 12000
MAX_TERRAIN_GRID_AXIS = 140


def _lat_lng_to_tile(lat: float, lng: float, zoom: int, tile_size: int) -> Tuple[int, int, int, int]:
    lat_rad = math.radians(max(min(lat, 85.05112878), -85.05112878))
    n = 2.0 ** zoom
    x = (lng + 180.0) / 360.0 * n
    y = (1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n
    tile_x = int(math.floor(x))
    tile_y = int(math.floor(y))
    px = int(math.floor((x - tile_x) * tile_size))
    py = int(math.floor((y - tile_y) * tile_size))
    return tile_x, tile_y, px, py


def _tile_url(tile_x: int, tile_y: int, zoom: int, token: str) -> str:
    return (
        f"https://api.mapbox.com/v4/mapbox.terrain-rgb/{zoom}/{tile_x}/{tile_y}@2x.pngraw"
        f"?access_token={token}"
    )


def _elevation_from_rgb(r: int, g: int, b: int) -> float:
    return -10000.0 + (r * 256 * 256 + g * 256 + b) * 0.1


def _fetch_tile(
    token: str,
    tile_x: int,
    tile_y: int,
    zoom: int,
    cache: Dict[Tuple[int, int, int], Image.Image],
) -> Optional[Image.Image]:
    key = (zoom, tile_x, tile_y)
    cached = cache.get(key)
    if cached is not None:
        return cached
    url = _tile_url(tile_x, tile_y, zoom, token)
    try:
        response = safe_get(url, timeout=10, response_kind="binary")
        response.raise_for_status()
        with Image.open(io.BytesIO(response.content)) as source:
            # This URL requests a512px Terrain-RGB tile, not arbitrary imagery.
            # Inspect dimensions before pixel decode to bound image memory.
            if source.format != "PNG" or source.size != (512, 512) or source.mode not in ("RGB", "RGBA"):
                return None
            source.load()
            if source.mode == "RGBA" and source.getextrema()[3] != (255, 255):
                return None
            image = source.convert("RGB")
    except (OSError, ValueError, Image.DecompressionBombError):
        return None
    cache[key] = image
    return image


def sample_elevation(lat: float, lng: float, token: str, *, zoom: int = 14, tile_size: int = 512) -> Optional[float]:
    tile_x, tile_y, px, py = _lat_lng_to_tile(lat, lng, zoom, tile_size)
    cache: Dict[Tuple[int, int, int], Image.Image] = {}
    image = _fetch_tile(token, tile_x, tile_y, zoom, cache)
    if image is None:
        return None
    r, g, b = image.getpixel((px, py))
    return _elevation_from_rgb(r, g, b)


def build_terrain_surface(
    *,
    center_lat: float,
    center_lng: float,
    lot_x: float,
    lot_y: float,
    lot_width_ft: float,
    lot_height_ft: float,
    rotation_deg: float,
    x_min: float,
    y_min: float,
    ncols: int,
    nrows: int,
    cell: float,
    lat_lng_bounds: Optional[Dict[str, Any]] = None,
) -> Optional[GridSurface]:
    if (type(ncols) is not int or type(nrows) is not int
            or not 2 <= ncols <= MAX_TERRAIN_GRID_AXIS
            or not 2 <= nrows <= MAX_TERRAIN_GRID_AXIS
            or ncols * nrows > MAX_TERRAIN_GRID_CELLS):
        return None
    coordinates = (center_lat, center_lng, lot_x, lot_y, lot_width_ft,
                   lot_height_ft, rotation_deg, x_min, y_min, cell)
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in coordinates):
        return None
    if (not -90 <= center_lat <= 90 or not -180 <= center_lng <= 180
            or lot_width_ft <= 0 or lot_height_ft <= 0 or cell <= 0):
        return None
    token = os.getenv("MAPBOX_TOKEN") or os.getenv("NEXT_PUBLIC_MAPBOX_TOKEN")
    if not token:
        return None
    meters_per_deg_lat = 111320.0
    meters_per_deg_lng = 111320.0 * math.cos(math.radians(center_lat))
    if meters_per_deg_lng <= 0:
        return None

    theta = math.radians(rotation_deg)
    cache: Dict[Tuple[int, int, int], Image.Image] = {}
    values: list[list[float]] = []
    center_x = lot_x + lot_width_ft / 2.0
    center_y = lot_y + lot_height_ft / 2.0
    bounds = _normalize_bounds(lat_lng_bounds)
    sample_count = 0
    missing_count = 0
    for row in range(nrows):
        y = y_min + row * cell
        row_vals: list[float] = []
        for col in range(ncols):
            x = x_min + col * cell
            if bounds is not None:
                lng, lat = _site_xy_to_bounds_lat_lng(
                    x=x,
                    y=y,
                    lot_x=lot_x,
                    lot_y=lot_y,
                    lot_width_ft=lot_width_ft,
                    lot_height_ft=lot_height_ft,
                    bounds=bounds,
                )
            else:
                dx_ft = x - center_x
                dy_ft = center_y - y
                dx_rot = dx_ft * math.cos(theta) - dy_ft * math.sin(theta)
                dy_rot = dx_ft * math.sin(theta) + dy_ft * math.cos(theta)
                dx_m = dx_rot * 0.3048
                dy_m = dy_rot * 0.3048
                lng = center_lng + dx_m / meters_per_deg_lng
                lat = center_lat + dy_m / meters_per_deg_lat
            tile_x, tile_y, px, py = _lat_lng_to_tile(lat, lng, 14, 512)
            image = _fetch_tile(token, tile_x, tile_y, 14, cache)
            if image is None:
                row_vals.append(float("nan"))
                missing_count += 1
                continue
            r, g, b = image.getpixel((px, py))
            row_vals.append(_elevation_from_rgb(r, g, b))
            sample_count += 1
        values.append(row_vals)

    # An unavailable tile is missing evidence, not permission to manufacture
    # elevation from neighboring samples. Do not pass a partial grid to the
    # legacy mean-fill normalization path used by the grading caller.
    if sample_count <= 0 or missing_count > 0:
        return None

    surface = GridSurface(
        x_min=x_min,
        y_min=y_min,
        x_max=x_min + (ncols - 1) * cell,
        y_max=y_min + (nrows - 1) * cell,
        cell_size=cell,
        ncols=ncols,
        nrows=nrows,
        values=values,
    )
    setattr(
        surface,
        "_terrain_sample_stats",
        {
            "source": "mapbox.terrain-rgb",
            "zoom": 14,
            "sample_count": sample_count,
            "missing_count": missing_count,
            "bounds_used": bounds is not None,
        },
    )
    return surface


def _normalize_bounds(bounds: Optional[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    if not isinstance(bounds, dict):
        return None
    try:
        north = float(bounds.get("north"))
        south = float(bounds.get("south"))
        east = float(bounds.get("east"))
        west = float(bounds.get("west"))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (north, south, east, west)):
        return None
    if abs(north - south) < 1e-9 or abs(east - west) < 1e-9:
        return None
    return {
        "north": max(north, south),
        "south": min(north, south),
        "east": max(east, west),
        "west": min(east, west),
    }


def _site_xy_to_bounds_lat_lng(
    *,
    x: float,
    y: float,
    lot_x: float,
    lot_y: float,
    lot_width_ft: float,
    lot_height_ft: float,
    bounds: Dict[str, float],
) -> Tuple[float, float]:
    width = max(lot_width_ft, 1.0)
    height = max(lot_height_ft, 1.0)
    x_ratio = (x - lot_x) / width
    y_ratio = (y - lot_y) / height
    lng = bounds["west"] + x_ratio * (bounds["east"] - bounds["west"])
    lat = bounds["south"] + y_ratio * (bounds["north"] - bounds["south"])
    return lng, lat


def normalize_surface(surface: GridSurface, default: float) -> GridSurface:
    finite_values = [
        val
        for row in surface.values
        for val in row
        if isinstance(val, (int, float)) and math.isfinite(val)
    ]
    fill_value = sum(finite_values) / len(finite_values) if finite_values else default
    values = []
    for row in surface.values:
        values.append([fill_value if not math.isfinite(val) else val for val in row])
    surface.values = values
    return surface
