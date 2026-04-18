from __future__ import annotations

import io
import math
import os
from typing import Dict, Optional, Tuple

import requests
from PIL import Image

from engines.surface_engine import GridSurface
from .common import safe_float


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
    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        return None
    image = Image.open(io.BytesIO(response.content))
    image = image.convert("RGB")
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
) -> Optional[GridSurface]:
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
    for row in range(nrows):
        y = y_min + row * cell
        row_vals: list[float] = []
        for col in range(ncols):
            x = x_min + col * cell
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
                continue
            r, g, b = image.getpixel((px, py))
            row_vals.append(_elevation_from_rgb(r, g, b))
        values.append(row_vals)

    return GridSurface(
        x_min=x_min,
        y_min=y_min,
        x_max=x_min + (ncols - 1) * cell,
        y_max=y_min + (nrows - 1) * cell,
        cell_size=cell,
        ncols=ncols,
        nrows=nrows,
        values=values,
    )


def normalize_surface(surface: GridSurface, default: float) -> GridSurface:
    values = []
    for row in surface.values:
        values.append([default if not math.isfinite(val) else val for val in row])
    surface.values = values
    return surface
