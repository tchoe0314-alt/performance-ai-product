from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
from time import monotonic
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests

from .common import safe_dict, safe_float, safe_int, safe_list, safe_str
from .existing_conditions import REQUIRED_GIS_LAYERS
from .gis_provider_registry import (
    build_provider_registry,
    normalize_source_type,
    provider_packs_for_location,
    providers_for_source_type,
    selected_provider,
    target_market_known_gaps,
)
from .imagery_object_detection import fetch_imagery_object_detection
from .map_feature_detection import build_map_feature_detection_report, location_context_from_geocode
from .standards_discovery import discover_standards_sources
from .worldwide_source_discovery import (
    DEFAULT_GLOBAL_ELEVATION_URL,
    DEFAULT_OVERPASS_URL,
    fetch_global_elevation_grid,
    fetch_global_elevation_point,
    fetch_openstreetmap_site_context,
)


CENSUS_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
USGS_EPQS_URL = "https://epqs.nationalmap.gov/v1/json"
USGS_3DEP_IMAGE_SERVER_URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer"
USGS_3DEP_GET_SAMPLES_URL = f"{USGS_3DEP_IMAGE_SERVER_URL}/getSamples"
FEMA_NFHL_MAPSERVER_URL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"
USFWS_WETLANDS_MAPSERVER_URL = "https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer"
ONLINE_DISCOVERY_VERSION = "online_existing_conditions_discovery_v1"


DISCOVERY_SOURCE_SPECS = {
    "parcel_site_boundary": {
        "label": "parcel/site boundary",
        "result_keys": ("parcels",),
        "layer_keys": ("parcels",),
    },
    "gis_constraints": {
        "label": "GIS constraints",
        "result_keys": ("floodplain", "wetlands", "easements", "zoning"),
        "layer_keys": ("floodplain", "wetlands", "easements", "zoning"),
    },
    "building_footprints": {
        "label": "building footprints",
        "result_keys": ("building_footprints",),
        "layer_keys": ("building_footprints",),
    },
    "imagery_object_detection": {
        "label": "imagery/object detection",
        "result_keys": ("imagery_object_detection",),
        "layer_keys": (),
    },
    "road_row": {
        "label": "road/ROW data",
        "result_keys": ("roads_row",),
        "layer_keys": ("roads", "row"),
    },
    "terrain_dem_lidar": {
        "label": "terrain/DEM/LiDAR",
        "result_keys": ("terrain_grid", "elevation", "terrain_breaklines", "lidar_index"),
        "layer_keys": ("terrain_breaklines", "lidar_coverage"),
    },
    "floodplain_wetlands_environmental": {
        "label": "floodplain/wetlands/environmental constraints",
        "result_keys": ("floodplain", "wetlands"),
        "layer_keys": ("floodplain", "wetlands"),
    },
    "public_utilities": {
        "label": "public utility layers",
        "result_keys": ("existing_utilities",),
        "layer_keys": ("existing_utilities",),
    },
    "contours": {
        "label": "contours",
        "result_keys": ("contours",),
        "layer_keys": ("contours",),
    },
    "official_standards": {
        "label": "official standards source candidates",
        "result_keys": (),
        "layer_keys": (),
    },
    "worldwide_mapped_context": {
        "label": "worldwide mapped site context",
        "result_keys": ("worldwide_mapped_context",),
        "layer_keys": ("parking", "sidewalks", "water"),
    },
}


def _json_get(session: Any, url: str, params: Dict[str, Any], *, timeout: float = 10.0) -> Dict[str, Any]:
    response = session.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    return safe_dict(payload)


def geocode_address_census(address: str, *, session: Any = requests) -> Dict[str, Any]:
    text = safe_str(address)
    if not text:
        return {"success": False, "source_type": "census_geocoder", "status": "blocked", "warnings": ["Address is required for Census geocoding."]}
    params = {"address": text, "benchmark": "Public_AR_Current", "format": "json"}
    try:
        payload = _json_get(session, CENSUS_GEOCODER_URL, params)
    except Exception as exc:
        return {"success": False, "source_type": "census_geocoder", "status": "fetch_failed", "warnings": [safe_str(exc)]}
    matches = safe_list(safe_dict(payload.get("result")).get("addressMatches"))
    if not matches:
        return {"success": False, "source_type": "census_geocoder", "status": "not_found", "warnings": ["Census geocoder returned no address matches."]}
    first = safe_dict(matches[0])
    coords = safe_dict(first.get("coordinates"))
    return {
        "success": True,
        "source": CENSUS_GEOCODER_URL,
        "source_type": "census_geocoder",
        "status": "ready",
        "address": text,
        "normalized_address": safe_str(first.get("matchedAddress")) or text,
        "matched_address": safe_str(first.get("matchedAddress")),
        "lat": safe_float(coords.get("y")),
        "lng": safe_float(coords.get("x")),
        "confidence": "address_match",
        "crs": {"epsg": "EPSG:4326", "name": "WGS 84 geographic coordinates", "units": "degrees", "source": CENSUS_GEOCODER_URL},
        "truth_label": "Public geocode for source discovery; verify against survey/site control before production.",
    }


def fetch_usgs_elevation_point(lat: float, lng: float, *, units: str = "Feet", session: Any = requests) -> Dict[str, Any]:
    params = {"x": lng, "y": lat, "wkid": 4326, "units": units, "includeDate": "true"}
    try:
        payload = _json_get(session, USGS_EPQS_URL, params)
    except Exception as exc:
        return {"success": False, "source_type": "usgs_3dep_epqs", "status": "fetch_failed", "warnings": [safe_str(exc)]}
    raw_value = payload.get("value")
    value = safe_dict(raw_value)
    elevation = raw_value if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool) else value.get("elevation")
    if elevation in (None, "", -1000000):
        return {"success": False, "source_type": "usgs_3dep_epqs", "status": "no_elevation", "warnings": ["USGS elevation query returned no usable elevation."]}
    return {
        "success": True,
        "source": USGS_EPQS_URL,
        "source_type": "usgs_3dep_epqs",
        "status": "ready",
        "lat": lat,
        "lng": lng,
        "elevation": safe_float(elevation),
        "units": units,
        "source_date": safe_str(safe_dict(payload.get("attributes")).get("AcquisitionDate") or value.get("date")),
        "truth_label": "Public DEM point elevation; not a topographic survey.",
    }


def fetch_usgs_elevation_grid(
    bbox: Dict[str, Any],
    *,
    rows: int = 7,
    cols: int = 7,
    session: Any = requests,
) -> Dict[str, Any]:
    west, south, east, north = _bbox_bounds(safe_dict(bbox))
    rows = min(max(safe_int(rows, 7), 2), 11)
    cols = min(max(safe_int(cols, 7), 2), 11)
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        return {
            "success": False,
            "status": "blocked",
            "source": USGS_3DEP_GET_SAMPLES_URL,
            "source_type": "usgs_3dep_elevation_grid",
            "source_tier": "national_public_context",
            "warnings": ["USGS 3DEP terrain-grid lookup needs a valid WGS84 site bounding box."],
            "review_required": True,
            "authoritative": False,
            "survey_backed": False,
        }
    requested = [
        {
            "row": row,
            "col": col,
            "lat": north - (north - south) * row / (rows - 1),
            "lng": west + (east - west) * col / (cols - 1),
            "x_ratio": col / (cols - 1),
            "y_ratio": row / (rows - 1),
        }
        for row in range(rows)
        for col in range(cols)
    ]
    params = {
        "f": "json",
        "geometry": json.dumps({
            "points": [[item["lng"], item["lat"]] for item in requested],
            "spatialReference": {"wkid": 4326},
        }),
        "geometryType": "esriGeometryMultipoint",
        "returnFirstValueOnly": "true",
        "outFields": "*",
    }
    try:
        response = session.get(USGS_3DEP_GET_SAMPLES_URL, params=params, timeout=18)
        response.raise_for_status()
        payload = safe_dict(response.json())
    except Exception as exc:
        return {
            "success": False,
            "status": "fetch_failed",
            "source": USGS_3DEP_GET_SAMPLES_URL,
            "source_type": "usgs_3dep_elevation_grid",
            "source_tier": "national_public_context",
            "warnings": [safe_str(exc, "USGS 3DEP terrain-grid request failed.")],
            "review_required": True,
            "authoritative": False,
            "survey_backed": False,
        }
    samples: List[Dict[str, Any]] = []
    source_attributes: Dict[str, Any] = {}
    resolution_values: List[float] = []
    for fallback_index, raw_sample in enumerate(safe_list(payload.get("samples"))):
        sample = safe_dict(raw_sample)
        raw_value = sample.get("value")
        if raw_value in (None, "", "NoData"):
            continue
        location_id = safe_int(sample.get("locationId"), fallback_index)
        if location_id < 0 or location_id >= len(requested):
            location_id = fallback_index
        if location_id >= len(requested):
            continue
        elevation_m = safe_float(raw_value)
        attributes = safe_dict(sample.get("attributes"))
        if attributes and not source_attributes:
            source_attributes = attributes
        resolution = safe_float(sample.get("resolution"))
        if resolution > 0:
            resolution_values.append(resolution)
        samples.append(
            {
                **requested[location_id],
                "elevation_m": elevation_m,
                "elevation_ft": elevation_m * 3.280839895,
            }
        )
    if len(samples) < 4:
        return {
            "success": False,
            "status": "no_elevation",
            "source": USGS_3DEP_GET_SAMPLES_URL,
            "source_type": "usgs_3dep_elevation_grid",
            "source_tier": "national_public_context",
            "sample_count": len(samples),
            "warnings": ["USGS 3DEP returned too few usable samples for a terrain surface."],
            "review_required": True,
            "authoritative": False,
            "survey_backed": False,
        }
    elevations_ft = [safe_float(item.get("elevation_ft")) for item in samples]
    vertical_datum = safe_str(
        source_attributes.get("VerticalDatum")
        or source_attributes.get("Vertical_Datum")
        or source_attributes.get("verticalDatum")
    )
    source_date = safe_str(
        source_attributes.get("AcquisitionDate")
        or source_attributes.get("SourceDataDate")
        or source_attributes.get("Date")
    )
    return {
        "success": True,
        "status": "ready",
        "source": USGS_3DEP_GET_SAMPLES_URL,
        "source_type": "usgs_3dep_elevation_grid",
        "source_tier": "national_public_context",
        "provider": "USGS 3DEP Elevation ImageServer",
        "rows": rows,
        "cols": cols,
        "sample_count": len(samples),
        "missing_sample_count": rows * cols - len(samples),
        "samples": samples,
        "min_elevation_ft": min(elevations_ft),
        "max_elevation_ft": max(elevations_ft),
        "elevation_range_ft": max(elevations_ft) - min(elevations_ft),
        "units": "feet",
        "horizontal_resolution": f"{min(resolution_values):g} meter service sample" if resolution_values else "USGS service-selected 3DEP resolution",
        "vertical_datum": vertical_datum,
        "source_date": source_date,
        "surface_ready": True,
        "review_required": True,
        "authoritative": False,
        "survey_backed": False,
        "truth_label": "USGS 3DEP elevation grid is public terrain context; it is not project survey/control or an accepted grading surface.",
    }


def _contour_interval_ft(elevation_range_ft: float) -> float:
    if elevation_range_ft <= 2:
        return 0.5
    if elevation_range_ft <= 8:
        return 1.0
    if elevation_range_ft <= 30:
        return 2.0
    if elevation_range_ft <= 75:
        return 5.0
    if elevation_range_ft <= 160:
        return 10.0
    return 20.0


def _contour_edge_intersection(
    first: Dict[str, Any],
    second: Dict[str, Any],
    level_ft: float,
) -> Optional[List[float]]:
    first_z = safe_float(first.get("elevation_ft"))
    second_z = safe_float(second.get("elevation_ft"))
    if first_z == second_z or not (min(first_z, second_z) <= level_ft <= max(first_z, second_z)):
        return None
    ratio = (level_ft - first_z) / (second_z - first_z)
    if ratio < 0 or ratio > 1:
        return None
    return [
        safe_float(first.get("lng")) + (safe_float(second.get("lng")) - safe_float(first.get("lng"))) * ratio,
        safe_float(first.get("lat")) + (safe_float(second.get("lat")) - safe_float(first.get("lat"))) * ratio,
    ]


def derive_review_contours_from_terrain_grid(terrain_grid: Dict[str, Any]) -> Dict[str, Any]:
    grid = safe_dict(terrain_grid)
    rows = safe_int(grid.get("rows"))
    cols = safe_int(grid.get("cols"))
    samples = {
        (safe_int(item.get("row")), safe_int(item.get("col"))): safe_dict(item)
        for item in (safe_dict(raw) for raw in safe_list(grid.get("samples")))
        if item
    }
    if not grid.get("success") or rows < 2 or cols < 2 or len(samples) < 4:
        return {
            "success": False,
            "status": "terrain_grid_unavailable",
            "source_type": "derived_public_dem_contours",
            "layer_name": "contours",
            "geojson": {"type": "FeatureCollection", "features": []},
            "warnings": ["Review contours need a usable terrain elevation grid."],
            "review_required": True,
        }
    min_elevation = safe_float(grid.get("min_elevation_ft"))
    max_elevation = safe_float(grid.get("max_elevation_ft"))
    elevation_range = max_elevation - min_elevation
    if elevation_range < 0.1:
        return {
            "success": True,
            "status": "ready_flat",
            "source": safe_str(grid.get("source")),
            "source_type": "derived_public_dem_contours",
            "source_tier": safe_str(grid.get("source_tier")),
            "provider": safe_str(grid.get("provider")),
            "layer_name": "contours",
            "feature_count": 0,
            "geojson": {"type": "FeatureCollection", "features": []},
            "warnings": ["The sampled public DEM surface is effectively flat at this scale; no review contour lines were derived."],
            "review_required": True,
            "authoritative": False,
            "survey_backed": False,
            "truth_label": "No contours were invented from an effectively flat public DEM sample grid.",
        }
    interval = _contour_interval_ft(elevation_range)
    first_level = math.ceil(min_elevation / interval) * interval
    levels: List[float] = []
    level = first_level
    while level < max_elevation and len(levels) < 18:
        if level > min_elevation + 0.0001:
            levels.append(level)
        level += interval
    features: List[Dict[str, Any]] = []
    for level_ft in levels:
        segments: List[List[List[float]]] = []
        for row in range(rows - 1):
            for col in range(cols - 1):
                nw = samples.get((row, col))
                ne = samples.get((row, col + 1))
                se = samples.get((row + 1, col + 1))
                sw = samples.get((row + 1, col))
                if not all((nw, ne, se, sw)):
                    continue
                intersections = [
                    point
                    for point in (
                        _contour_edge_intersection(nw, ne, level_ft),
                        _contour_edge_intersection(ne, se, level_ft),
                        _contour_edge_intersection(se, sw, level_ft),
                        _contour_edge_intersection(sw, nw, level_ft),
                    )
                    if point is not None
                ]
                deduped: List[List[float]] = []
                for point in intersections:
                    if not any(abs(point[0] - seen[0]) < 1e-10 and abs(point[1] - seen[1]) < 1e-10 for seen in deduped):
                        deduped.append(point)
                if len(deduped) == 2:
                    segments.append([deduped[0], deduped[1]])
                elif len(deduped) == 4:
                    segments.extend([[deduped[0], deduped[1]], [deduped[2], deduped[3]]])
        if segments:
            features.append(
                {
                    "type": "Feature",
                    "id": f"public-dem-contour-{level_ft:g}",
                    "geometry": {"type": "MultiLineString", "coordinates": segments},
                    "properties": {
                        "contour_elevation_ft": level_ft,
                        "contour_interval_ft": interval,
                        "derived_from": safe_str(grid.get("source_type")),
                        "review_required": True,
                        "survey_backed": False,
                    },
                }
            )
    return {
        "success": True,
        "status": "ready" if features else "ready_empty",
        "source": safe_str(grid.get("source")),
        "source_type": "derived_public_dem_contours",
        "source_tier": safe_str(grid.get("source_tier")),
        "provider": safe_str(grid.get("provider")),
        "layer_name": "contours",
        "feature_count": len(features),
        "contour_interval_ft": interval,
        "geojson": {"type": "FeatureCollection", "features": features},
        "warnings": ["Contour lines were derived from a sampled public DEM grid and are review visualization, not surveyed contours."],
        "review_required": True,
        "authoritative": False,
        "survey_backed": False,
        "truth_label": "Derived public-DEM contours are review context only; they are not survey/control or accepted grading evidence.",
    }


def _arcgis_query_url(service_url: str, layer_id: int) -> str:
    return f"{service_url.rstrip('/')}/{int(layer_id)}/query"


def _bbox_geometry(bbox: Dict[str, Any]) -> str:
    xmin = safe_float(bbox.get("min_lng") or bbox.get("xmin") or bbox.get("west"))
    ymin = safe_float(bbox.get("min_lat") or bbox.get("ymin") or bbox.get("south"))
    xmax = safe_float(bbox.get("max_lng") or bbox.get("xmax") or bbox.get("east"))
    ymax = safe_float(bbox.get("max_lat") or bbox.get("ymax") or bbox.get("north"))
    return f"{xmin},{ymin},{xmax},{ymax}"


def _bbox_bounds(bbox: Dict[str, Any]) -> Tuple[float, float, float, float]:
    return (
        safe_float(bbox.get("min_lng") or bbox.get("xmin") or bbox.get("west")),
        safe_float(bbox.get("min_lat") or bbox.get("ymin") or bbox.get("south")),
        safe_float(bbox.get("max_lng") or bbox.get("xmax") or bbox.get("east")),
        safe_float(bbox.get("max_lat") or bbox.get("ymax") or bbox.get("north")),
    )


def _arcgis_geometry_tolerance(bbox: Dict[str, Any], *, preserve_feature_shape: bool) -> float:
    west, south, east, north = _bbox_bounds(bbox)
    span = max(abs(east - west), abs(north - south), 0.00001)
    # Parcel and building outlines keep sub-foot detail at a typical site scale.
    # Context layers use roughly two-foot detail so a county-scale polygon cannot
    # inflate one site lookup into tens of megabytes of off-site coordinates.
    divisor = 2048.0 if preserve_feature_shape else 512.0
    return max(0.0000001, min(0.00005, span / divisor))


def _clip_ring_to_bbox(points: List[Any], west: float, south: float, east: float, north: float) -> List[List[float]]:
    ring = [[safe_float(point[0]), safe_float(point[1])] for point in points if isinstance(point, (list, tuple)) and len(point) >= 2]
    if len(ring) < 3:
        return []

    def clip_edge(
        vertices: List[List[float]],
        inside: Any,
        intersection: Any,
    ) -> List[List[float]]:
        if not vertices:
            return []
        output: List[List[float]] = []
        previous = vertices[-1]
        previous_inside = inside(previous)
        for current in vertices:
            current_inside = inside(current)
            if current_inside:
                if not previous_inside:
                    output.append(intersection(previous, current))
                output.append(current)
            elif previous_inside:
                output.append(intersection(previous, current))
            previous = current
            previous_inside = current_inside
        return output

    def vertical_intersection(first: List[float], second: List[float], x_value: float) -> List[float]:
        delta = second[0] - first[0]
        ratio = 0.0 if abs(delta) < 1e-15 else (x_value - first[0]) / delta
        return [x_value, first[1] + ratio * (second[1] - first[1])]

    def horizontal_intersection(first: List[float], second: List[float], y_value: float) -> List[float]:
        delta = second[1] - first[1]
        ratio = 0.0 if abs(delta) < 1e-15 else (y_value - first[1]) / delta
        return [first[0] + ratio * (second[0] - first[0]), y_value]

    ring = clip_edge(ring, lambda point: point[0] >= west, lambda first, second: vertical_intersection(first, second, west))
    ring = clip_edge(ring, lambda point: point[0] <= east, lambda first, second: vertical_intersection(first, second, east))
    ring = clip_edge(ring, lambda point: point[1] >= south, lambda first, second: horizontal_intersection(first, second, south))
    ring = clip_edge(ring, lambda point: point[1] <= north, lambda first, second: horizontal_intersection(first, second, north))
    if len(ring) < 3:
        return []
    if ring[0] != ring[-1]:
        ring.append(list(ring[0]))
    return ring


def _clip_segment_to_bbox(
    first: List[float],
    second: List[float],
    west: float,
    south: float,
    east: float,
    north: float,
) -> Optional[Tuple[List[float], List[float]]]:
    x0, y0 = first
    x1, y1 = second
    dx = x1 - x0
    dy = y1 - y0
    start = 0.0
    end = 1.0
    for direction, distance in (
        (-dx, x0 - west),
        (dx, east - x0),
        (-dy, y0 - south),
        (dy, north - y0),
    ):
        if abs(direction) < 1e-15:
            if distance < 0:
                return None
            continue
        ratio = distance / direction
        if direction < 0:
            start = max(start, ratio)
        else:
            end = min(end, ratio)
        if start > end:
            return None
    return (
        [x0 + start * dx, y0 + start * dy],
        [x0 + end * dx, y0 + end * dy],
    )


def _clip_line_to_bbox(
    points: List[Any],
    west: float,
    south: float,
    east: float,
    north: float,
) -> List[List[List[float]]]:
    coordinates = [
        [safe_float(point[0]), safe_float(point[1])]
        for point in points
        if isinstance(point, (list, tuple)) and len(point) >= 2
    ]
    paths: List[List[List[float]]] = []
    current: List[List[float]] = []
    for first, second in zip(coordinates, coordinates[1:]):
        clipped = _clip_segment_to_bbox(first, second, west, south, east, north)
        if not clipped:
            if len(current) >= 2:
                paths.append(current)
            current = []
            continue
        clipped_start, clipped_end = clipped
        if all(abs(clipped_start[idx] - clipped_end[idx]) < 1e-12 for idx in (0, 1)):
            continue
        if current and all(abs(current[-1][idx] - clipped_start[idx]) < 1e-12 for idx in (0, 1)):
            if any(abs(current[-1][idx] - clipped_end[idx]) >= 1e-12 for idx in (0, 1)):
                current.append(clipped_end)
        else:
            if len(current) >= 2:
                paths.append(current)
            current = [clipped_start, clipped_end]
    if len(current) >= 2:
        paths.append(current)
    return paths


def _clip_geometry_without_shapely(geometry: Dict[str, Any], west: float, south: float, east: float, north: float) -> Dict[str, Any]:
    geometry_type = safe_str(geometry.get("type"))
    coordinates = geometry.get("coordinates")
    if geometry_type == "Point":
        point = safe_list(coordinates)
        if len(point) >= 2 and west <= safe_float(point[0]) <= east and south <= safe_float(point[1]) <= north:
            return geometry
        return {}
    if geometry_type == "Polygon":
        rings = safe_list(coordinates)
        if not rings:
            return {}
        outer = _clip_ring_to_bbox(safe_list(rings[0]), west, south, east, north)
        if not outer:
            return {}
        holes = [
            clipped
            for ring in rings[1:]
            if (clipped := _clip_ring_to_bbox(safe_list(ring), west, south, east, north))
        ]
        return {"type": "Polygon", "coordinates": [outer, *holes]}
    if geometry_type == "MultiPolygon":
        polygons = []
        for polygon in safe_list(coordinates):
            clipped = _clip_geometry_without_shapely({"type": "Polygon", "coordinates": polygon}, west, south, east, north)
            if clipped:
                polygons.append(clipped["coordinates"])
        return {"type": "MultiPolygon", "coordinates": polygons} if polygons else {}
    if geometry_type == "LineString":
        paths = _clip_line_to_bbox(safe_list(coordinates), west, south, east, north)
        if len(paths) == 1:
            return {"type": "LineString", "coordinates": paths[0]}
        return {"type": "MultiLineString", "coordinates": paths} if paths else {}
    if geometry_type == "MultiLineString":
        paths = [
            path
            for line in safe_list(coordinates)
            for path in _clip_line_to_bbox(safe_list(line), west, south, east, north)
        ]
        if len(paths) == 1:
            return {"type": "LineString", "coordinates": paths[0]}
        return {"type": "MultiLineString", "coordinates": paths} if paths else {}
    return {}


def _clip_geojson_features_to_bbox(payload: Dict[str, Any], bbox: Dict[str, Any]) -> Dict[str, Any]:
    features = safe_list(payload.get("features"))
    if not features:
        return payload
    west, south, east, north = _bbox_bounds(bbox)
    if west >= east or south >= north:
        return payload
    try:
        from shapely.geometry import box, mapping, shape
    except ImportError:
        clipped_features: List[Dict[str, Any]] = []
        for raw_feature in features:
            feature = safe_dict(raw_feature)
            geometry = safe_dict(feature.get("geometry"))
            if not geometry or not geometry.get("coordinates"):
                clipped_features.append(feature)
                continue
            clipped_geometry = _clip_geometry_without_shapely(geometry, west, south, east, north)
            if not clipped_geometry:
                continue
            clipped_features.append({**feature, "geometry": clipped_geometry})
        return {**payload, "features": clipped_features}

    clip_box = box(west, south, east, north)
    clipped_features: List[Dict[str, Any]] = []
    for raw_feature in features:
        feature = safe_dict(raw_feature)
        geometry = safe_dict(feature.get("geometry"))
        if not geometry or not geometry.get("coordinates"):
            clipped_features.append(feature)
            continue
        try:
            clipped = shape(geometry).intersection(clip_box)
        except Exception:
            clipped_features.append(feature)
            continue
        if clipped.is_empty:
            continue
        clipped_feature = dict(feature)
        clipped_feature["geometry"] = mapping(clipped)
        clipped_features.append(clipped_feature)
    return {**payload, "features": clipped_features}


def fetch_arcgis_layer_geojson(
    *,
    service_url: str,
    layer_id: int,
    bbox: Dict[str, Any],
    source_type: str,
    layer_name: str,
    provider: Optional[Dict[str, Any]] = None,
    session: Any = requests,
) -> Dict[str, Any]:
    if not safe_dict(bbox):
        return {"success": False, "source_type": source_type, "status": "blocked", "warnings": ["Lat/lng bbox is required for online GIS layer fetch."]}
    provider_record = safe_dict(provider)
    if provider_record and provider_record.get("queryable") is False:
        return {
            "success": False,
            "source_type": source_type,
            "status": "known_not_queryable",
            "warnings": [f"{safe_str(provider_record.get('name'), layer_name)} is known but not queryable for candidate extraction."],
            "provider": safe_str(provider_record.get("name") or provider_record.get("id") or source_type),
            "provider_id": safe_str(provider_record.get("id")),
            "provider_record": provider_record,
        }
    preserve_feature_shape = layer_name in {"parcels", "building_footprints"}
    geometry_tolerance = _arcgis_geometry_tolerance(
        bbox,
        preserve_feature_shape=preserve_feature_shape,
    )
    params = {
        "f": "geojson",
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "geometry": _bbox_geometry(bbox),
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outSR": 4326,
        "maxAllowableOffset": geometry_tolerance,
        "geometryPrecision": 7,
        "returnZ": "false",
        "returnM": "false",
    }
    try:
        response = session.get(_arcgis_query_url(service_url, layer_id), params=params, timeout=15)
        response.raise_for_status()
        payload = safe_dict(response.json())
    except Exception as exc:
        return {"success": False, "source_type": source_type, "status": "fetch_failed", "warnings": [safe_str(exc)]}
    geometry_clipped = not preserve_feature_shape
    if geometry_clipped:
        payload = _clip_geojson_features_to_bbox(payload, bbox)
    features = safe_list(safe_dict(payload).get("features"))
    return {
        "success": True,
        "source": _arcgis_query_url(service_url, layer_id),
        "source_type": source_type,
        "status": "ready",
        "layer_name": layer_name,
        "feature_count": len(features),
        "geojson": safe_dict(payload),
        "query_geometry_tolerance": geometry_tolerance,
        "geometry_clipped_to_query_bbox": geometry_clipped,
        "provider": safe_str(provider_record.get("name") or provider_record.get("id") or source_type),
        "provider_id": safe_str(provider_record.get("id")),
        "provider_record": provider_record,
        "truth_label": "Public GIS context layer; verify against jurisdiction records and survey before production.",
    }


def fetch_fema_floodplain(bbox: Dict[str, Any], *, layer_id: int = 28, session: Any = requests) -> Dict[str, Any]:
    return fetch_arcgis_layer_geojson(
        service_url=FEMA_NFHL_MAPSERVER_URL,
        layer_id=layer_id,
        bbox=bbox,
        source_type="fema_nfhl_arcgis",
        layer_name="floodplain",
        session=session,
    )


def fetch_usfws_wetlands(bbox: Dict[str, Any], *, layer_id: int = 0, session: Any = requests) -> Dict[str, Any]:
    return fetch_arcgis_layer_geojson(
        service_url=USFWS_WETLANDS_MAPSERVER_URL,
        layer_id=layer_id,
        bbox=bbox,
        source_type="usfws_nwi_arcgis",
        layer_name="wetlands",
        session=session,
    )


def fetch_configured_parcels(
    bbox: Dict[str, Any],
    *,
    service_url: str = "",
    layer_id: int = 0,
    provider: Optional[Dict[str, Any]] = None,
    session: Any = requests,
) -> Dict[str, Any]:
    provider_record = safe_dict(provider)
    if provider_record:
        arcgis = safe_dict(provider_record.get("arcgis"))
        service_url = safe_str(arcgis.get("service_url") or provider_record.get("service_url") or service_url)
        layer_id = int(arcgis.get("layer_id", layer_id) or 0)
    if not safe_str(service_url):
        return {
            "success": False,
            "source_type": "configured_parcel_arcgis",
            "status": "unconfigured",
            "warnings": ["No parcel ArcGIS service is configured. Parcel sources are local/county-specific."],
        }
    return fetch_arcgis_layer_geojson(
        service_url=service_url,
        layer_id=layer_id,
        bbox=bbox,
        source_type="configured_parcel_arcgis",
        layer_name="parcels",
        provider=provider_record,
        session=session,
    )


def fetch_unconfigured_gis_source(*, source_type: str, label: str) -> Dict[str, Any]:
    return {
        "success": False,
        "source_type": source_type,
        "status": "unconfigured",
        "warnings": [
            f"No {label} GIS source is configured.",
            "Configure/import an official source before detection.",
        ],
    }


def _aggregate_layer_results(*, source_type: str, layer_name: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    records = [safe_dict(item) for item in safe_list(results) if safe_dict(item)]
    if not records:
        return fetch_unconfigured_gis_source(source_type=source_type, label=layer_name)
    features: List[Dict[str, Any]] = []
    warnings: List[str] = []
    providers: List[str] = []
    provider_ids: List[str] = []
    sources: List[str] = []
    child_records: List[Dict[str, Any]] = []
    for record in records:
        warnings.extend(safe_list(record.get("warnings")))
        provider = safe_str(record.get("provider"))
        provider_id = safe_str(record.get("provider_id"))
        source = safe_str(record.get("source"))
        if provider:
            providers.append(provider)
        if provider_id:
            provider_ids.append(provider_id)
        if source:
            sources.append(source)
        child_records.append(
            {
                "source": source,
                "source_type": safe_str(record.get("source_type")),
                "status": safe_str(record.get("status")),
                "success": bool(record.get("success")),
                "provider": provider,
                "provider_id": provider_id,
                "feature_count": safe_int(record.get("feature_count"), 0),
                "warnings": safe_list(record.get("warnings")),
            }
        )
        if record.get("success"):
            features.extend(safe_list(safe_dict(record.get("geojson")).get("features")))
    success = any(bool(record.get("success")) for record in records)
    feature_count = len(features)
    status = "ready" if success else safe_str(records[0].get("status"), "missing")
    if success and feature_count == 0:
        status = "ready_empty"
    return {
        "success": success,
        "source": ", ".join(list(dict.fromkeys(sources))[:4]),
        "source_type": source_type,
        "status": status,
        "layer_name": layer_name,
        "feature_count": feature_count,
        "geojson": {"type": "FeatureCollection", "features": features},
        "provider": ", ".join(list(dict.fromkeys(providers))[:4]) or source_type,
        "provider_id": ", ".join(list(dict.fromkeys(provider_ids))[:4]),
        "child_sources": child_records,
        "warnings": list(dict.fromkeys(safe_str(item) for item in warnings if safe_str(item))),
        "truth_label": "Public GIS context layers; verify against jurisdiction records, utility-owner records, locates, and survey before relying on them.",
    }


def _missing_configured_source(*, registry: Dict[str, Any], source_type: str, result_source_type: str, label: str) -> Dict[str, Any]:
    known = [
        safe_dict(item)
        for item in safe_list(safe_dict(registry).get("providers"))
        if normalize_source_type(safe_str(safe_dict(item).get("source_type"))) == normalize_source_type(source_type)
    ]
    nonqueryable = [item for item in known if item.get("queryable") is False or safe_str(item.get("status")) == "known_not_queryable"]
    if nonqueryable:
        first = nonqueryable[0]
        return {
            "success": False,
            "source_type": result_source_type,
            "status": "known_not_queryable",
            "source": safe_str(first.get("service_url")),
            "provider": safe_str(first.get("name") or first.get("id")),
            "provider_id": safe_str(first.get("id")),
            "provider_record": first,
            "warnings": [f"{safe_str(first.get('name'), label)} is known but not queryable for candidate extraction."],
        }
    return fetch_unconfigured_gis_source(source_type=result_source_type, label=label)


def bbox_around_point(lat: float, lng: float, *, buffer_deg: float = 0.002) -> Dict[str, float]:
    buffer = max(0.00001, safe_float(buffer_deg, 0.002))
    return {
        "west": safe_float(lng) - buffer,
        "south": safe_float(lat) - buffer,
        "east": safe_float(lng) + buffer,
        "north": safe_float(lat) + buffer,
    }


def bbox_center(bbox: Dict[str, Any]) -> Tuple[float, float]:
    west = safe_float(bbox.get("min_lng") or bbox.get("xmin") or bbox.get("west"))
    south = safe_float(bbox.get("min_lat") or bbox.get("ymin") or bbox.get("south"))
    east = safe_float(bbox.get("max_lng") or bbox.get("xmax") or bbox.get("east"))
    north = safe_float(bbox.get("max_lat") or bbox.get("ymax") or bbox.get("north"))
    return ((south + north) / 2.0, (west + east) / 2.0)


def online_import_to_gis_layers(*imports: Dict[str, Any]) -> Dict[str, Any]:
    layers: Dict[str, List[Dict[str, Any]]] = {layer: [] for layer in REQUIRED_GIS_LAYERS}
    layers.setdefault("building_footprints", [])
    layers.setdefault("roads", [])
    layers.setdefault("contours", [])
    layers.setdefault("zoning", [])
    layers.setdefault("terrain_breaklines", [])
    layers.setdefault("lidar_coverage", [])
    layers.setdefault("parking", [])
    layers.setdefault("sidewalks", [])
    layers.setdefault("water", [])
    warnings: List[str] = []
    sources: List[Dict[str, Any]] = []
    for item in imports:
        rec = safe_dict(item)
        if not rec:
            continue
        sources.append(
            {
                "source": safe_str(rec.get("source")),
                "source_type": safe_str(rec.get("source_type")),
                "provider": safe_str(rec.get("provider")),
                "provider_id": safe_str(rec.get("provider_id")),
                "source_tier": safe_str(rec.get("source_tier")),
                "success": bool(rec.get("success")),
            }
        )
        warnings.extend(safe_list(rec.get("warnings")))
        if not rec.get("success"):
            continue
        layer_name = safe_str(rec.get("layer_name"))
        target_map = {
            "floodplain": "floodplain",
            "wetlands": "wetlands",
            "parcels": "parcels",
            "building_footprints": "building_footprints",
            "roads": "roads",
            "roads_row": "roads",
            "zoning": "zoning",
            "existing_utilities": "existing_utilities",
            "easements": "easements",
            "row": "row",
            "contours": "contours",
            "terrain_breaklines": "terrain_breaklines",
            "lidar_coverage": "lidar_coverage",
            "parking": "parking",
            "sidewalks": "sidewalks",
            "water": "water",
        }
        target = target_map.get(layer_name, "")
        if not target:
            continue
        for feature in safe_list(safe_dict(rec.get("geojson")).get("features")):
            layers[target].append(
                {
                    "id": safe_str(safe_dict(feature).get("id"), f"{target}-{len(layers[target]) + 1}"),
                    "geometry": safe_dict(safe_dict(feature).get("geometry")),
                    "properties": safe_dict(safe_dict(feature).get("properties")),
                    "source": safe_str(rec.get("source")),
                    "source_type": safe_str(rec.get("source_type")),
                    "source_name": safe_str(rec.get("provider") or rec.get("source_type")),
                    "provider": safe_str(rec.get("provider")),
                    "provider_id": safe_str(rec.get("provider_id")),
                    "source_tier": safe_str(rec.get("source_tier")),
                    "attribution": safe_str(rec.get("attribution")),
                }
            )
    return {
        "success": any(source["success"] for source in sources),
        "source_type": "online_existing_conditions",
        "sources": sources,
        "gis_layers": layers,
        "warnings": warnings,
        "truth_label": "Online public existing-condition layers are context data until confirmed by survey/jurisdiction records.",
    }


def _source_url(result: Dict[str, Any]) -> str:
    return safe_str(result.get("source") or result.get("source_url"))


def _source_blockers(*, label: str, result_records: List[Dict[str, Any]], candidate_count: int) -> List[str]:
    blockers: List[str] = []
    if candidate_count:
        blockers.append(f"{label} candidates are review-required and not survey-backed.")
    if any(safe_str(result.get("source_tier")) == "community_global" for result in result_records):
        blockers.append(f"{label} includes community-mapped context whose coverage, currency, and positional accuracy can vary.")
    if any(safe_str(result.get("source_tier")) == "global_public_context" for result in result_records):
        blockers.append(f"{label} includes approximate global public context, not a surveyed project surface or control source.")
    if any(safe_str(result.get("source_tier")) == "national_public_context" for result in result_records):
        blockers.append(f"{label} includes national public elevation context, not project survey/control or an accepted grading surface.")
    if not result_records:
        blockers.append(f"{label} source is missing/unavailable.")
    if not candidate_count and any(result.get("success") for result in result_records):
        blockers.append(f"{label} provider responded but returned no features inside the address search area.")
    for result in result_records:
        status = safe_str(result.get("status"), "missing")
        warnings = [safe_str(item) for item in safe_list(result.get("warnings")) if safe_str(item)]
        if result.get("success"):
            continue
        if status == "skipped":
            blockers.append(f"{label} source was skipped.")
        elif status == "unconfigured":
            blockers.append(warnings[0] if warnings else f"{label} source is not configured.")
        elif status == "not_found":
            blockers.append(warnings[0] if warnings else f"{label} source returned no matches.")
        elif status == "fetch_failed":
            blockers.append(warnings[0] if warnings else f"{label} source fetch failed.")
        elif status:
            blockers.append(warnings[0] if warnings else f"{label} source status is {status}.")
        else:
            blockers.append(f"{label} source is missing/unavailable.")
    return list(dict.fromkeys(item for item in blockers if item))


def _source_record(
    *,
    key: str,
    label: str,
    result_records: List[Dict[str, Any]],
    candidate_count: int,
    blockers: List[str],
) -> Dict[str, Any]:
    first = next((item for item in result_records if safe_dict(item)), {})
    success = candidate_count > 0
    status = "candidates_found" if success else safe_str(first.get("status"), "missing")
    if not success and any(safe_str(item.get("status")) == "fetch_failed" for item in result_records):
        status = "fetch_failed"
    if not success and any(safe_str(item.get("status")) == "unconfigured" for item in result_records):
        status = "unconfigured"
    source_type = safe_str(first.get("source_type"), key)
    source_tier = safe_str(first.get("source_tier"))
    if not source_tier:
        source_tier = "visual_candidate" if key == "imagery_object_detection" else ("verified_or_official" if success else "unavailable")
    default_authoritative = source_tier == "verified_or_official" and key != "imagery_object_detection"
    return {
        "key": key,
        "label": label,
        "source_url": _source_url(first),
        "agency": safe_str(first.get("agency") or first.get("layer_name") or first.get("source_type")),
        "provider": safe_str(first.get("provider") or first.get("source_type")),
        "confidence": "candidate" if success else "unavailable",
        "source_type": source_type,
        "source_tier": source_tier,
        "authoritative": bool(first.get("authoritative", default_authoritative)) if success else False,
        "attribution": safe_str(first.get("attribution")),
        "status": status,
        "candidate_count": candidate_count,
        "review_required": True,
        "acceptance_status": "candidate" if success else "missing",
        "blockers": blockers,
    }


def build_online_existing_conditions_discovery_report(
    *,
    source_results: Optional[Dict[str, Any]] = None,
    gis_layers: Optional[Dict[str, Any]] = None,
    location_context: Optional[Dict[str, Any]] = None,
    standards_jurisdiction: Optional[Dict[str, Any]] = None,
    provider_registry: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    results = safe_dict(source_results)
    layers = safe_dict(gis_layers)
    sources: List[Dict[str, Any]] = []
    candidate_count = 0
    missing_sources: List[Dict[str, Any]] = []
    failed_sources: List[Dict[str, Any]] = []
    registry = safe_dict(provider_registry) or build_provider_registry(include_builtin=True)
    known_gaps = safe_list(registry.get("known_gaps"))

    for key, spec in DISCOVERY_SOURCE_SPECS.items():
        label = safe_str(spec.get("label"), key)
        if key == "official_standards":
            jurisdiction = safe_dict(standards_jurisdiction)
            if any(safe_str(jurisdiction.get(field)) for field in ("city", "county", "state", "utility_provider")):
                standards = discover_standards_sources(
                    city=safe_str(jurisdiction.get("city")),
                    county=safe_str(jurisdiction.get("county")),
                    state=safe_str(jurisdiction.get("state")),
                    utility_provider=safe_str(jurisdiction.get("utility_provider")),
                )
                standards_sources = [
                    safe_dict(item)
                    for item in safe_list(standards.get("sources"))
                    if safe_str(safe_dict(item).get("url")).startswith("https://")
                ]
                blockers = ["Official standards sources are candidates until exact jurisdiction/provider standards are reviewed and accepted."]
                record = {
                    "key": key,
                    "label": label,
                    "source_url": safe_str(standards_sources[0].get("url")) if standards_sources else "",
                    "agency": safe_str(standards_sources[0].get("name")) if standards_sources else "",
                    "provider": "standards_discovery_registry",
                    "confidence": "candidate" if standards_sources else "unavailable",
                    "source_type": "standards_discovery_registry",
                    "status": "candidates_found" if standards_sources else "missing",
                    "candidate_count": len(standards_sources),
                    "review_required": True,
                    "acceptance_status": "candidate" if standards_sources else "missing",
                    "blockers": blockers if standards_sources else ["Official standards source candidates need city/county/state or utility provider context."],
                }
            else:
                record = _source_record(
                    key=key,
                    label=label,
                    result_records=[],
                    candidate_count=0,
                    blockers=["Official standards source candidates need city/county/state or utility provider context."],
                )
            sources.append(record)
            candidate_count += int(record["candidate_count"])
            if not record["candidate_count"]:
                missing_sources.append({"key": key, "label": label, "missing": record["blockers"]})
            continue

        result_records = [safe_dict(results.get(item)) for item in spec.get("result_keys", ()) if safe_dict(results.get(item))]
        if key == "imagery_object_detection":
            count = sum(safe_int(result.get("detection_count")) for result in result_records)
        elif key == "worldwide_mapped_context":
            count = sum(_result_feature_count(result) for result in result_records)
        elif key == "terrain_dem_lidar":
            count = sum(len(safe_list(layers.get(layer_key))) for layer_key in spec.get("layer_keys", ()))
            terrain_grid_result = safe_dict(results.get("terrain_grid"))
            elevation_result = safe_dict(results.get("elevation"))
            if terrain_grid_result.get("success"):
                count += max(1, safe_int(terrain_grid_result.get("sample_count")))
            elif elevation_result.get("success"):
                count += 1
        else:
            layer_keys = tuple(spec.get("layer_keys", ()))
            count = sum(len(safe_list(layers.get(layer_key))) for layer_key in layer_keys)
            if not count:
                count = sum(_result_feature_count(result) for result in result_records)
        blockers = _source_blockers(label=label, result_records=result_records, candidate_count=count)
        record = _source_record(key=key, label=label, result_records=result_records, candidate_count=count, blockers=blockers)
        for gap in known_gaps:
            gap_rec = safe_dict(gap)
            if normalize_gap := safe_str(gap_rec.get("source_type")):
                normalized_gap = normalize_source_type(normalize_gap)
                normalized_results = {normalize_source_type(safe_str(item)) for item in spec.get("result_keys", ())}
                normalized_layers = {normalize_source_type(safe_str(item)) for item in spec.get("layer_keys", ())}
                if normalized_gap in normalized_results or normalized_gap in normalized_layers:
                    if not count:
                        message = safe_str(gap_rec.get("message"))
                        if message and message not in record["blockers"]:
                            blockers.append(message)
        sources.append(record)
        candidate_count += count
        if not count:
            missing_sources.append({"key": key, "label": label, "missing": blockers or [f"{label} source is missing/unavailable."]})
        if record["status"] == "fetch_failed":
            failed_sources.append({"key": key, "label": label, "blockers": blockers})

    survey_control = {
        "status": "not_satisfied",
        "survey_control_satisfied": False,
        "review_required": True,
        "blockers": ["Online discovery does not satisfy survey, boundary, benchmark, utility locate, or site-control requirements."],
    }
    blockers = [
        item
        for source in sources
        for item in safe_list(source.get("blockers"))
        if safe_str(item)
    ]
    if not candidate_count:
        status = "fetch_failed" if failed_sources else "no_sources_found"
    else:
        status = "candidates_found"
    geocode_result = safe_dict(results.get("geocode"))
    terrain_grid_result = safe_dict(results.get("terrain_grid"))
    elevation_result = safe_dict(results.get("elevation"))
    geocode_source_type = safe_str(geocode_result.get("source_type"), "census_geocoder")
    elevation_source_type = safe_str(elevation_result.get("source_type"), "usgs_3dep_epqs")
    supported_live_providers = [
        {
            "key": geocode_source_type,
            "provider": safe_str(geocode_result.get("provider"), "Mapbox Geocoding" if "mapbox" in geocode_source_type else "US Census Geocoder"),
            "source_url": safe_str(geocode_result.get("source"), CENSUS_GEOCODER_URL),
            "supports": ["address/location context"],
            "status": safe_str(geocode_result.get("status"), "available"),
        },
        {
            "key": "usgs_3dep_elevation_grid",
            "provider": "USGS 3DEP Elevation ImageServer",
            "source_url": USGS_3DEP_GET_SAMPLES_URL,
            "supports": ["terrain/DEM elevation grid", "review contour derivation"],
            "status": (
                safe_str(terrain_grid_result.get("status"), "available_in_us")
                if safe_str(terrain_grid_result.get("source_type")) == "usgs_3dep_elevation_grid"
                else "available_in_us"
            ),
        },
        {
            "key": "fema_nfhl_arcgis",
            "provider": "FEMA NFHL ArcGIS",
            "source_url": FEMA_NFHL_MAPSERVER_URL,
            "supports": ["floodplain constraints"],
            "status": safe_str(safe_dict(results.get("floodplain")).get("status"), "available"),
        },
        {
            "key": "usfws_nwi_arcgis",
            "provider": "USFWS NWI ArcGIS",
            "source_url": USFWS_WETLANDS_MAPSERVER_URL,
            "supports": ["wetlands/environmental constraints"],
            "status": safe_str(safe_dict(results.get("wetlands")).get("status"), "available"),
        },
        {
            "key": "openstreetmap_overpass",
            "provider": "OpenStreetMap Overpass",
            "source_url": DEFAULT_OVERPASS_URL,
            "supports": ["worldwide mapped buildings, roads, paths, parking, water, and limited mapped utility context"],
            "status": safe_str(safe_dict(results.get("worldwide_mapped_context")).get("status"), "available_on_global_geocode"),
        },
        {
            "key": "global_dem_point_elevation",
            "provider": "Open-Meteo elevation / Copernicus DEM",
            "source_url": DEFAULT_GLOBAL_ELEVATION_URL,
            "supports": ["worldwide approximate DEM point elevation"],
            "status": safe_str(elevation_result.get("status"), "available") if elevation_source_type == "global_dem_point_elevation" else "available_fallback",
        },
    ]
    fixture_provider_only_sources = [
        {
            "key": "parcel_site_boundary",
            "provider": "Configured county/local ArcGIS service",
            "source_type": "configured_parcel_arcgis",
            "status": safe_str(next((source.get("status") for source in sources if source.get("key") == "parcel_site_boundary"), ""), "unconfigured"),
            "missing_message": next((safe_list(source.get("blockers"))[0] for source in sources if source.get("key") == "parcel_site_boundary" and safe_list(source.get("blockers"))), "No parcel GIS source is configured."),
        },
        {
            "key": "building_footprints",
            "provider": "Configured city/county building-footprint ArcGIS service",
            "source_type": "configured_building_footprints_arcgis",
            "status": safe_str(next((source.get("status") for source in sources if source.get("key") == "building_footprints"), ""), "unconfigured"),
            "missing_message": next((safe_list(source.get("blockers"))[0] for source in sources if source.get("key") == "building_footprints" and safe_list(source.get("blockers"))), "No building footprint GIS source is configured."),
        },
        {
            "key": "road_row",
            "provider": "Configured road/ROW ArcGIS service",
            "source_type": "configured_roads_row_arcgis",
            "status": safe_str(next((source.get("status") for source in sources if source.get("key") == "road_row"), ""), "unconfigured"),
            "missing_message": next((safe_list(source.get("blockers"))[0] for source in sources if source.get("key") == "road_row" and safe_list(source.get("blockers"))), "No road/ROW GIS source is configured."),
        },
        {
            "key": "public_utilities",
            "provider": "Configured utility owner/jurisdiction ArcGIS service",
            "source_type": "configured_existing_utilities_arcgis",
            "status": safe_str(next((source.get("status") for source in sources if source.get("key") == "public_utilities"), ""), "unconfigured"),
            "missing_message": next((safe_list(source.get("blockers"))[0] for source in sources if source.get("key") == "public_utilities" and safe_list(source.get("blockers"))), "No public utility GIS source is configured."),
        },
        {
            "key": "contours",
            "provider": "Configured contour ArcGIS service",
            "source_type": "configured_contours_arcgis",
            "status": safe_str(next((source.get("status") for source in sources if source.get("key") == "contours"), ""), "unconfigured"),
            "missing_message": next((safe_list(source.get("blockers"))[0] for source in sources if source.get("key") == "contours" and safe_list(source.get("blockers"))), "No contour GIS source is configured."),
        },
        {
            "key": "official_standards",
            "provider": "Standards discovery registry",
            "source_type": "standards_discovery_registry",
            "status": safe_str(next((source.get("status") for source in sources if source.get("key") == "official_standards"), ""), "missing"),
            "missing_message": next((safe_list(source.get("blockers"))[0] for source in sources if source.get("key") == "official_standards" and safe_list(source.get("blockers"))), "Official standards source candidates need jurisdiction/provider context."),
        },
    ]
    return {
        "version": ONLINE_DISCOVERY_VERSION,
        "status": status,
        "source_type": "online_existing_conditions_discovery",
        "location_context": safe_dict(location_context),
        "supported_live_providers": supported_live_providers,
        "fixture_provider_only_sources": fixture_provider_only_sources,
        "local_gis_provider_registry_v1": registry,
        "provider_packs": safe_list(registry.get("provider_packs")),
        "configured_provider_count": registry.get("configured_provider_count", 0),
        "queryable_provider_count": registry.get("queryable_provider_count", 0),
        "sources": sources,
        "candidate_count": candidate_count,
        "missing_sources": missing_sources,
        "failed_sources": failed_sources,
        "blockers": list(dict.fromkeys(blockers)),
        "survey_control": survey_control,
        "review_required": True,
        "acceptance_status": "candidate" if candidate_count else "missing",
        "construction_release_allowed": False,
        "truth_label": "Online existing-condition discovery returns candidate/review-required sources only; it is not survey-backed and does not satisfy final reliance requirements.",
    }


def _resolve_standards_jurisdiction(
    *,
    explicit: Optional[Dict[str, Any]],
    provider_packs: List[Dict[str, Any]],
    location_context: Dict[str, Any],
) -> Dict[str, Any]:
    resolved = safe_dict(explicit)
    if any(safe_str(resolved.get(field)) for field in ("city", "county", "state", "utility_provider")):
        return resolved
    first_pack = safe_dict(provider_packs[0]) if provider_packs else {}
    pack_jurisdiction = safe_dict(first_pack.get("jurisdiction"))
    location_text = " ".join(
        safe_str(location_context.get(field)).lower()
        for field in ("address", "matched_address", "normalized_address")
    )
    pack_city = safe_str(pack_jurisdiction.get("city")).lower()
    pack_county = safe_str(pack_jurisdiction.get("county")).lower()
    jurisdiction_named = bool(
        (pack_city and pack_city in location_text)
        or (pack_county and pack_county in location_text)
    )
    if jurisdiction_named and any(safe_str(pack_jurisdiction.get(field)) for field in ("city", "county", "state")):
        return {
            "city": safe_str(pack_jurisdiction.get("city")),
            "county": safe_str(pack_jurisdiction.get("county")),
            "state": safe_str(pack_jurisdiction.get("state")),
            "utility_provider": safe_str(pack_jurisdiction.get("utility_provider")),
        }
    geocoded_jurisdiction = safe_dict(location_context.get("jurisdiction"))
    if any(safe_str(geocoded_jurisdiction.get(field)) for field in ("place", "district", "region")):
        return {
            "city": safe_str(geocoded_jurisdiction.get("place")),
            "county": safe_str(geocoded_jurisdiction.get("district")),
            "state": safe_str(geocoded_jurisdiction.get("region")),
            "country": safe_str(geocoded_jurisdiction.get("country")),
            "country_code": safe_str(geocoded_jurisdiction.get("country_code")),
            "utility_provider": "",
        }
    matched = safe_str(location_context.get("matched_address") or location_context.get("normalized_address"))
    parts = [part.strip() for part in matched.split(",") if part.strip()]
    if len(parts) >= 3:
        return {
            "city": parts[-3] if len(parts) >= 4 else parts[-2],
            "county": "",
            "state": parts[-2] if len(parts) >= 4 else parts[-1],
            "utility_provider": "",
        }
    return {}


def _result_feature_count(result: Dict[str, Any]) -> int:
    rec = safe_dict(result)
    geojson_count = len(safe_list(safe_dict(rec.get("geojson")).get("features")))
    if geojson_count:
        return geojson_count
    explicit_count = safe_int(rec.get("feature_count"))
    if explicit_count:
        return explicit_count
    nested_layers = safe_dict(rec.get("layer_results"))
    return sum(_result_feature_count(safe_dict(item)) for item in nested_layers.values())


def _source_not_applicable(*, source_type: str, label: str, country_code: str) -> Dict[str, Any]:
    country = safe_str(country_code, "this location")
    return {
        "success": False,
        "status": "outside_provider_scope",
        "source_type": source_type,
        "warnings": [f"{label} is not a worldwide provider and does not cover {country}; a local authoritative source is still needed."],
        "review_required": True,
    }


def _normalized_supplied_geocode(address: str, geocode_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    geocode = safe_dict(geocode_context)
    nested = safe_dict(geocode.get("location_context"))
    nested_coordinates = safe_dict(nested.get("coordinates"))
    lat = geocode.get("lat") if geocode.get("lat") not in (None, "") else nested_coordinates.get("lat")
    lng = geocode.get("lng") if geocode.get("lng") not in (None, "") else nested_coordinates.get("lng")
    if lat in (None, "") or lng in (None, ""):
        return {}
    normalized = safe_str(
        geocode.get("normalized_address")
        or geocode.get("formatted_address")
        or geocode.get("display_name")
        or nested.get("normalized_address")
        or address
    )
    return {
        **geocode,
        "success": True,
        "status": safe_str(geocode.get("status"), "ready"),
        "lat": safe_float(lat),
        "lng": safe_float(lng),
        "address": safe_str(address or normalized),
        "display_name": safe_str(geocode.get("display_name") or normalized),
        "formatted_address": safe_str(geocode.get("formatted_address") or normalized),
        "normalized_address": normalized,
        "matched_address": safe_str(geocode.get("matched_address") or normalized),
        "provider": safe_str(geocode.get("provider"), "supplied_geocode"),
        "source_type": safe_str(geocode.get("source_type"), "supplied_geocode"),
        "truth_label": "Geocode coordinates locate the source search area only; they do not establish a parcel, boundary, survey, or control point.",
    }


def _location_source_strategy(
    *,
    location_context: Dict[str, Any],
    provider_packs: List[Dict[str, Any]],
    worldwide_context: Dict[str, Any],
    source_results: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    jurisdiction = safe_dict(location_context.get("jurisdiction"))
    pack_ids = [safe_str(safe_dict(pack).get("pack_id")) for pack in provider_packs if safe_str(safe_dict(pack).get("pack_id"))]
    worldwide_ready = bool(worldwide_context.get("success"))
    authoritative_gaps: List[str] = []
    for key, label in (
        ("parcels", "authoritative parcel/boundary record"),
        ("building_footprints", "authoritative building-footprint record"),
        ("roads_row", "authoritative right-of-way record"),
        ("easements", "recorded easements"),
        ("zoning", "current jurisdiction zoning"),
        ("existing_utilities", "utility-owner records and field locates"),
        ("contours", "authoritative terrain/contour source"),
        ("floodplain", "applicable authoritative floodplain source"),
        ("wetlands", "applicable authoritative wetlands/environmental source"),
    ):
        result = safe_dict(source_results.get(key))
        source_tier = safe_str(result.get("source_tier"))
        if _result_feature_count(result) <= 0 or source_tier in {"community_global", "global_public_context", "national_public_context"}:
            authoritative_gaps.append(label)
    authoritative_gaps.extend(["boundary/topographic survey", "benchmark/datum and project control"])
    return {
        "version": "location_source_strategy_v1",
        "jurisdiction": jurisdiction,
        "verified_local_pack_ids": pack_ids,
        "verified_local_pack_found": bool(pack_ids),
        "worldwide_fallback_status": safe_str(worldwide_context.get("status"), "not_requested"),
        "worldwide_fallback_feature_count": safe_int(worldwide_context.get("feature_count")),
        "worldwide_fallback_used": worldwide_ready and safe_int(worldwide_context.get("feature_count")) > 0,
        "source_priority": [
            "accepted project survey/control and record documents",
            "verified local/county/utility records",
            "applicable national public sources",
            "worldwide community-mapped context",
            "imagery-detected candidates",
        ],
        "remaining_authoritative_gaps": list(dict.fromkeys(authoritative_gaps)),
        "review_required": True,
        "truth_label": "Civora uses the best available location-specific sources without promoting worldwide mapped or imagery context into survey/control evidence.",
    }


def fetch_online_existing_conditions(
    *,
    address: str = "",
    bbox: Optional[Dict[str, Any]] = None,
    geocode_context: Optional[Dict[str, Any]] = None,
    parcel_service_url: str = "",
    parcel_layer_id: int = 0,
    building_footprints_service_url: str = "",
    building_footprints_layer_id: int = 0,
    roads_service_url: str = "",
    roads_layer_id: int = 0,
    easements_service_url: str = "",
    easements_layer_id: int = 0,
    zoning_service_url: str = "",
    zoning_layer_id: int = 0,
    utilities_service_url: str = "",
    utilities_layer_id: int = 0,
    contours_service_url: str = "",
    contours_layer_id: int = 0,
    include_floodplain: bool = True,
    include_wetlands: bool = True,
    include_parcels: bool = True,
    include_building_footprints: bool = True,
    include_roads: bool = True,
    include_easements: bool = True,
    include_zoning: bool = True,
    include_utilities: bool = True,
    include_contours: bool = True,
    include_elevation: bool = True,
    include_terrain_context: bool = True,
    include_imagery_detection: bool = True,
    include_worldwide_context: bool = True,
    imagery_detection_provider_url: str = "",
    imagery_detection_provider_token: str = "",
    imagery_detection_provider_name: str = "",
    standards_jurisdiction: Optional[Dict[str, Any]] = None,
    provider_registry: Optional[Dict[str, Any]] = None,
    active_site_boundary: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    session: Any = requests,
) -> Dict[str, Any]:
    source_results: Dict[str, Dict[str, Any]] = {}
    warnings: List[str] = []
    registry = safe_dict(provider_registry) or build_provider_registry(include_builtin=True)
    working_bbox = safe_dict(bbox)
    supplied_geocode = _normalized_supplied_geocode(address, geocode_context)
    if supplied_geocode:
        geocode = supplied_geocode
    elif safe_str(address):
        geocode = geocode_address_census(address, session=session)
    else:
        geocode = {
            "success": False,
            "source_type": "census_geocoder",
            "status": "skipped",
            "warnings": ["No address supplied; geocoding skipped."],
        }
    source_results["geocode"] = geocode
    location_context = location_context_from_geocode(address=address, geocode=geocode)
    jurisdiction = safe_dict(location_context.get("jurisdiction"))
    country_code = safe_str(jurisdiction.get("country_code")).upper()
    is_us_location = country_code in {"US", "USA"} or (not country_code and safe_str(geocode.get("source_type")) == "census_geocoder")
    provider_packs = provider_packs_for_location(
        address=address,
        lat=safe_float(geocode.get("lat")) if geocode.get("success") else None,
        lng=safe_float(geocode.get("lng")) if geocode.get("success") else None,
        location_context=location_context,
    )
    resolved_standards_jurisdiction = _resolve_standards_jurisdiction(
        explicit=standards_jurisdiction,
        provider_packs=provider_packs,
        location_context=location_context,
    )
    target_records = [provider for pack in provider_packs for provider in safe_list(safe_dict(pack).get("providers"))]
    if target_records:
        registry = build_provider_registry(
            providers=safe_list(registry.get("providers")) + target_records,
            include_builtin=False,
        )
        registry["provider_packs"] = provider_packs
        registry["known_gaps"] = target_market_known_gaps(
            address=address,
            lat=safe_float(geocode.get("lat")) if geocode.get("success") else None,
            lng=safe_float(geocode.get("lng")) if geocode.get("success") else None,
        )
    elif provider_packs:
        registry["provider_packs"] = provider_packs
    if not working_bbox and geocode.get("success"):
        working_bbox = bbox_around_point(safe_float(geocode.get("lat")), safe_float(geocode.get("lng")))
    if not working_bbox:
        warnings.append("Online existing-condition fetch needs either an address that geocodes or a lat/lng bbox.")
        feature_report = build_map_feature_detection_report(
            location_context=location_context,
            gis_layers={layer: [] for layer in REQUIRED_GIS_LAYERS},
            source_results=source_results,
            active_site_boundary=active_site_boundary,
        )
        discovery_report = build_online_existing_conditions_discovery_report(
            source_results=source_results,
            gis_layers={layer: [] for layer in REQUIRED_GIS_LAYERS},
            location_context=location_context,
            standards_jurisdiction=resolved_standards_jurisdiction,
            provider_registry=registry,
        )
        discovery_report["site_intelligence_summary_v1"] = safe_dict(feature_report.get("site_intelligence_summary_v1"))
        return {
            "success": False,
            "source_type": "online_existing_conditions_fetch",
            "status": "blocked",
            "source_results": source_results,
            "location_context": location_context,
            ONLINE_DISCOVERY_VERSION: discovery_report,
            "map_feature_detection_report_v1": feature_report,
            "canonical_existing_conditions": {
                "survey": {"source": "missing", "point_count": 0, "points": []},
                "gis_layers": {layer: [] for layer in REQUIRED_GIS_LAYERS},
                "coordinate_system": {"name": "EPSG:4326", "source": "online_public_sources"},
            },
            "warnings": warnings,
            "truth_label": "Online fetch blocked before any public context layers were imported.",
        }

    center_lat, center_lng = bbox_center(working_bbox)
    fetch_started = monotonic()
    source_tasks: List[Tuple[str, str, Callable[[], Dict[str, Any]]]] = []
    source_timings: Dict[str, float] = {}
    task_payloads: Dict[str, Dict[str, Any]] = {}

    def notify_progress(*, label: str, completed: int, total: int) -> None:
        if progress_callback is None:
            return
        progress_callback(
            {
                "stage": "Finding Site Sources",
                "detail": f"Checked {label}. {completed} of {total} source checks complete.",
                "progress": 20 + round(52 * completed / max(total, 1)),
                "completed_source_count": completed,
                "total_source_count": total,
                "latest_source": label,
            }
        )

    def add_task(task_id: str, label: str, fetcher: Callable[[], Dict[str, Any]]) -> None:
        source_tasks.append((task_id, label, fetcher))

    def fetch_terrain_sources() -> Dict[str, Any]:
        attempts: Dict[str, Any] = {}
        if include_worldwide_context and supplied_geocode and not is_us_location:
            terrain = fetch_global_elevation_grid(working_bbox, session=session)
            point = fetch_global_elevation_point(center_lat, center_lng, session=session)
        else:
            terrain = fetch_usgs_elevation_grid(working_bbox, session=session)
            if terrain.get("success"):
                center_sample = min(
                    safe_list(terrain.get("samples")),
                    key=lambda item: abs(safe_float(safe_dict(item).get("x_ratio")) - 0.5)
                    + abs(safe_float(safe_dict(item).get("y_ratio")) - 0.5),
                )
                point = {
                    "success": True,
                    "status": "ready",
                    "source": terrain.get("source"),
                    "source_type": terrain.get("source_type"),
                    "source_tier": terrain.get("source_tier"),
                    "provider": terrain.get("provider"),
                    "lat": safe_float(safe_dict(center_sample).get("lat"), center_lat),
                    "lng": safe_float(safe_dict(center_sample).get("lng"), center_lng),
                    "elevation": safe_float(safe_dict(center_sample).get("elevation_ft")),
                    "units": "Feet",
                    "source_date": terrain.get("source_date"),
                    "horizontal_resolution": terrain.get("horizontal_resolution"),
                    "vertical_datum": terrain.get("vertical_datum"),
                    "truth_label": terrain.get("truth_label"),
                }
            else:
                point = fetch_usgs_elevation_point(center_lat, center_lng, session=session)
            if include_worldwide_context and supplied_geocode and not terrain.get("success") and not point.get("success"):
                attempts["usgs_terrain_grid_attempt"] = terrain
                attempts["usgs_elevation_attempt"] = point
                terrain = fetch_global_elevation_grid(working_bbox, session=session)
                point = fetch_global_elevation_point(center_lat, center_lng, session=session)
        return {"terrain_grid": terrain, "elevation": point, **attempts}

    if include_elevation:
        add_task("terrain", "terrain and elevation", fetch_terrain_sources)
    else:
        task_payloads["terrain"] = {
            "terrain_grid": {
                "success": False,
                "source_type": "usgs_3dep_elevation_grid",
                "status": "skipped",
                "warnings": ["Terrain-grid fetch skipped by request."],
            },
            "elevation": {
                "success": False,
                "source_type": "usgs_3dep_epqs",
                "status": "skipped",
                "warnings": ["Elevation fetch skipped by request."],
            },
        }

    if include_floodplain:
        floodplain_provider = selected_provider(registry, "floodplain")
        floodplain_arcgis = safe_dict(floodplain_provider.get("arcgis"))
        if safe_str(floodplain_arcgis.get("service_url")) and safe_str(floodplain_provider.get("jurisdiction_level")) != "federal":
            add_task(
                "floodplain",
                "floodplain",
                lambda: fetch_arcgis_layer_geojson(
                    service_url=safe_str(floodplain_arcgis.get("service_url")),
                    layer_id=int(floodplain_arcgis.get("layer_id") or 0),
                    bbox=working_bbox,
                    source_type="configured_floodplain_arcgis",
                    layer_name="floodplain",
                    provider=floodplain_provider,
                    session=session,
                ),
            )
        elif supplied_geocode and not is_us_location:
            task_payloads["floodplain"] = _source_not_applicable(
                source_type="fema_nfhl_arcgis", label="FEMA floodplain", country_code=country_code
            )
        else:
            add_task("floodplain", "floodplain", lambda: fetch_fema_floodplain(working_bbox, session=session))

    if include_wetlands:
        wetlands_provider = selected_provider(registry, "wetlands")
        wetlands_arcgis = safe_dict(wetlands_provider.get("arcgis"))
        if safe_str(wetlands_arcgis.get("service_url")) and safe_str(wetlands_provider.get("jurisdiction_level")) != "federal":
            add_task(
                "wetlands",
                "wetlands",
                lambda: fetch_arcgis_layer_geojson(
                    service_url=safe_str(wetlands_arcgis.get("service_url")),
                    layer_id=int(wetlands_arcgis.get("layer_id") or 0),
                    bbox=working_bbox,
                    source_type="configured_wetlands_arcgis",
                    layer_name="wetlands",
                    provider=wetlands_provider,
                    session=session,
                ),
            )
        elif supplied_geocode and not is_us_location:
            task_payloads["wetlands"] = _source_not_applicable(
                source_type="usfws_nwi_arcgis", label="USFWS wetlands", country_code=country_code
            )
        else:
            add_task("wetlands", "wetlands", lambda: fetch_usfws_wetlands(working_bbox, session=session))

    if include_parcels:
        parcel_provider = selected_provider(registry, "parcels")
        add_task(
            "parcels",
            "parcels",
            lambda: fetch_configured_parcels(
                working_bbox,
                service_url=parcel_service_url,
                layer_id=parcel_layer_id,
                provider=parcel_provider,
                session=session,
            ),
        )

    if include_building_footprints:
        building_provider = selected_provider(registry, "buildings")
        building_arcgis = safe_dict(building_provider.get("arcgis"))
        building_url = safe_str(building_arcgis.get("service_url") or building_footprints_service_url)
        building_layer = int(building_arcgis.get("layer_id", building_footprints_layer_id) or 0)
        if building_url:
            add_task(
                "building_footprints",
                "building footprints",
                lambda: fetch_arcgis_layer_geojson(
                    service_url=building_url,
                    layer_id=building_layer,
                    bbox=working_bbox,
                    source_type="configured_building_footprints_arcgis",
                    layer_name="building_footprints",
                    provider=building_provider,
                    session=session,
                ),
            )
        else:
            task_payloads["building_footprints"] = _missing_configured_source(
                registry=registry,
                source_type="buildings",
                result_source_type="configured_building_footprints_arcgis",
                label="building footprint",
            )

    if include_roads:
        roads_provider = selected_provider(registry, "roads_row")
        roads_arcgis = safe_dict(roads_provider.get("arcgis"))
        roads_url = safe_str(roads_arcgis.get("service_url") or roads_service_url)
        roads_layer = int(roads_arcgis.get("layer_id", roads_layer_id) or 0)
        if roads_url:
            add_task(
                "roads_row",
                "roads and right-of-way",
                lambda: fetch_arcgis_layer_geojson(
                    service_url=roads_url,
                    layer_id=roads_layer,
                    bbox=working_bbox,
                    source_type="configured_roads_row_arcgis",
                    layer_name="roads",
                    provider=roads_provider,
                    session=session,
                ),
            )
        else:
            task_payloads["roads_row"] = _missing_configured_source(
                registry=registry,
                source_type="roads_row",
                result_source_type="configured_roads_row_arcgis",
                label="roads/right-of-way",
            )

    if include_easements:
        if safe_str(easements_service_url):
            add_task(
                "easements",
                "easements",
                lambda: fetch_arcgis_layer_geojson(
                    service_url=easements_service_url,
                    layer_id=easements_layer_id,
                    bbox=working_bbox,
                    source_type="configured_easements_arcgis",
                    layer_name="easements",
                    session=session,
                ),
            )
        else:
            task_payloads["easements"] = fetch_unconfigured_gis_source(
                source_type="configured_easements_arcgis", label="easement"
            )

    if include_zoning:
        zoning_provider = selected_provider(registry, "zoning")
        zoning_arcgis = safe_dict(zoning_provider.get("arcgis"))
        zoning_url = safe_str(zoning_arcgis.get("service_url") or zoning_service_url)
        zoning_layer = int(zoning_arcgis.get("layer_id", zoning_layer_id) or 0)
        if zoning_url:
            add_task(
                "zoning",
                "zoning",
                lambda: fetch_arcgis_layer_geojson(
                    service_url=zoning_url,
                    layer_id=zoning_layer,
                    bbox=working_bbox,
                    source_type="configured_zoning_arcgis",
                    layer_name="zoning",
                    provider=zoning_provider,
                    session=session,
                ),
            )
        else:
            task_payloads["zoning"] = fetch_unconfigured_gis_source(
                source_type="configured_zoning_arcgis", label="zoning"
            )

    utility_task_ids: List[str] = []
    if include_utilities:
        utilities_providers = providers_for_source_type(registry, "utilities")
        if utilities_providers:
            for index, utilities_provider in enumerate(utilities_providers):
                utilities_arcgis = safe_dict(utilities_provider.get("arcgis"))
                utilities_url = safe_str(utilities_arcgis.get("service_url"))
                if not utilities_url:
                    continue
                task_id = f"utility:{index}"
                utility_task_ids.append(task_id)
                add_task(
                    task_id,
                    safe_str(utilities_provider.get("name"), "utility records"),
                    lambda provider=utilities_provider, arcgis=utilities_arcgis, url=utilities_url: fetch_arcgis_layer_geojson(
                        service_url=url,
                        layer_id=int(arcgis.get("layer_id", 0) or 0),
                        bbox=working_bbox,
                        source_type="configured_existing_utilities_arcgis",
                        layer_name="existing_utilities",
                        provider=provider,
                        session=session,
                    ),
                )
        elif safe_str(utilities_service_url):
            utility_task_ids.append("utility:configured")
            add_task(
                "utility:configured",
                "utility records",
                lambda: fetch_arcgis_layer_geojson(
                    service_url=utilities_service_url,
                    layer_id=utilities_layer_id,
                    bbox=working_bbox,
                    source_type="configured_existing_utilities_arcgis",
                    layer_name="existing_utilities",
                    session=session,
                ),
            )
        else:
            task_payloads["existing_utilities"] = _missing_configured_source(
                registry=registry,
                source_type="utilities",
                result_source_type="configured_existing_utilities_arcgis",
                label="existing utilities",
            )

    if include_contours:
        contours_provider = selected_provider(registry, "contours")
        contours_arcgis = safe_dict(contours_provider.get("arcgis"))
        contours_url = safe_str(contours_arcgis.get("service_url") or contours_service_url)
        contours_layer = int(contours_arcgis.get("layer_id", contours_layer_id) or 0)
        if contours_url:
            add_task(
                "contours",
                "contours",
                lambda: fetch_arcgis_layer_geojson(
                    service_url=contours_url,
                    layer_id=contours_layer,
                    bbox=working_bbox,
                    source_type="configured_contours_arcgis",
                    layer_name="contours",
                    provider=contours_provider,
                    session=session,
                ),
            )
        else:
            task_payloads["contours"] = _missing_configured_source(
                registry=registry,
                source_type="contours",
                result_source_type="configured_contours_arcgis",
                label="contour",
            )

    terrain_provider_tasks: Dict[str, Tuple[str, str]] = {}
    if include_terrain_context:
        for provider_source_type, result_key, layer_name in (
            ("terrain_breaklines", "terrain_breaklines", "terrain_breaklines"),
            ("lidar_index", "lidar_index", "lidar_coverage"),
        ):
            for index, terrain_provider in enumerate(providers_for_source_type(registry, provider_source_type)):
                terrain_arcgis = safe_dict(terrain_provider.get("arcgis"))
                terrain_url = safe_str(terrain_arcgis.get("service_url"))
                if not terrain_url:
                    continue
                task_id = f"{provider_source_type}:{index}"
                terrain_provider_tasks[task_id] = (result_key, layer_name)
                add_task(
                    task_id,
                    safe_str(terrain_provider.get("name"), layer_name),
                    lambda provider=terrain_provider, arcgis=terrain_arcgis, url=terrain_url, source_type=provider_source_type, layer=layer_name: fetch_arcgis_layer_geojson(
                        service_url=url,
                        layer_id=int(arcgis.get("layer_id") or 0),
                        bbox=working_bbox,
                        source_type=f"configured_{source_type}_arcgis",
                        layer_name=layer,
                        provider=provider,
                        session=session,
                    ),
                )

    if include_worldwide_context and geocode.get("success"):
        add_task(
            "worldwide_mapped_context",
            "worldwide mapped context",
            lambda: fetch_openstreetmap_site_context(working_bbox, session=session),
        )
    elif include_worldwide_context:
        task_payloads["worldwide_mapped_context"] = {
            "success": False,
            "status": "not_requested_without_geocode",
            "source_type": "openstreetmap_overpass",
            "warnings": ["Worldwide mapped context needs usable geocoded coordinates."],
            "review_required": True,
        }

    if include_imagery_detection:
        add_task(
            "imagery_object_detection",
            "imagery detection",
            lambda: fetch_imagery_object_detection(
                address=address,
                bbox=working_bbox,
                location_context=location_context,
                active_site_boundary=active_site_boundary,
                provider_url=imagery_detection_provider_url,
                provider_token=imagery_detection_provider_token,
                provider_name=imagery_detection_provider_name,
                session=session,
            ),
        )
    else:
        task_payloads["imagery_object_detection"] = fetch_imagery_object_detection(
            provider_name="skipped", session=session
        )

    def run_source_task(task_id: str, fetcher: Callable[[], Dict[str, Any]]) -> Tuple[Dict[str, Any], float]:
        started = monotonic()
        try:
            payload = safe_dict(fetcher())
        except Exception as exc:
            payload = {
                "success": False,
                "status": "fetch_failed",
                "source_type": task_id.split(":", 1)[0],
                "warnings": [safe_str(exc, f"{task_id} source lookup failed.")],
                "review_required": True,
            }
        return payload, monotonic() - started

    if source_tasks:
        max_workers = min(8, len(source_tasks))
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="civora-source") as executor:
            futures = {
                executor.submit(run_source_task, task_id, fetcher): (task_id, label)
                for task_id, label, fetcher in source_tasks
            }
            for completed_count, future in enumerate(as_completed(futures), start=1):
                task_id, label = futures[future]
                payload, elapsed = future.result()
                task_payloads[task_id] = payload
                source_timings[task_id] = round(elapsed, 3)
                notify_progress(label=label, completed=completed_count, total=len(source_tasks))

    terrain_payload = safe_dict(task_payloads.get("terrain"))
    terrain_grid = safe_dict(terrain_payload.get("terrain_grid"))
    elevation = safe_dict(terrain_payload.get("elevation"))
    source_results["terrain_grid"] = terrain_grid
    source_results["elevation"] = elevation
    for attempt_key in ("usgs_terrain_grid_attempt", "usgs_elevation_attempt"):
        if terrain_payload.get(attempt_key):
            source_results[attempt_key] = safe_dict(terrain_payload.get(attempt_key))

    layer_imports: List[Dict[str, Any]] = []
    for source_key in (
        "floodplain",
        "wetlands",
        "parcels",
        "building_footprints",
        "roads_row",
        "easements",
        "zoning",
    ):
        if source_key not in task_payloads:
            continue
        result = safe_dict(task_payloads.get(source_key))
        source_results[source_key] = result
        layer_imports.append(result)

    if include_utilities:
        utility_results = [safe_dict(task_payloads.get(task_id)) for task_id in utility_task_ids if task_payloads.get(task_id)]
        if utility_results:
            layer_imports.extend(utility_results)
            source_results["existing_utilities"] = _aggregate_layer_results(
                source_type="configured_existing_utilities_arcgis",
                layer_name="existing_utilities",
                results=utility_results,
            )
        else:
            source_results["existing_utilities"] = safe_dict(task_payloads.get("existing_utilities"))

    if include_contours:
        contours = safe_dict(task_payloads.get("contours"))
        if not _result_feature_count(contours) and terrain_grid.get("success"):
            source_results["authoritative_contours_attempt"] = contours
            contours = derive_review_contours_from_terrain_grid(terrain_grid)
        source_results["contours"] = contours
        layer_imports.append(contours)

    for result_key, layer_name in (
        ("terrain_breaklines", "terrain_breaklines"),
        ("lidar_index", "lidar_coverage"),
    ):
        terrain_results = [
            safe_dict(task_payloads.get(task_id))
            for task_id, (target_key, _) in terrain_provider_tasks.items()
            if target_key == result_key and task_payloads.get(task_id)
        ]
        if not terrain_results:
            continue
        aggregated_terrain = _aggregate_layer_results(
            source_type=f"configured_{result_key}_arcgis",
            layer_name=layer_name,
            results=terrain_results,
        )
        source_results[result_key] = aggregated_terrain
        layer_imports.append(aggregated_terrain)

    worldwide_context = safe_dict(task_payloads.get("worldwide_mapped_context"))
    if include_worldwide_context:
        source_results["worldwide_mapped_context"] = worldwide_context
    if include_worldwide_context and geocode.get("success"):
        worldwide_layers = safe_dict(worldwide_context.get("layer_results"))
        fallback_targets = {
            **({"building_footprints": "building_footprints"} if include_building_footprints else {}),
            **({"roads": "roads_row"} if include_roads else {}),
            **({"existing_utilities": "existing_utilities"} if include_utilities else {}),
        }
        for layer_name, source_key in fallback_targets.items():
            fallback_result = safe_dict(worldwide_layers.get(layer_name))
            existing_result = safe_dict(source_results.get(source_key))
            if _result_feature_count(existing_result) or not _result_feature_count(fallback_result):
                continue
            source_results[f"authoritative_{source_key}"] = existing_result
            source_results[source_key] = fallback_result
            layer_imports.append(fallback_result)
        for layer_name in ("parking", "sidewalks", "water"):
            fallback_result = safe_dict(worldwide_layers.get(layer_name))
            if _result_feature_count(fallback_result):
                layer_imports.append(fallback_result)
        registry["worldwide_fallback"] = {
            "provider": "OpenStreetMap",
            "status": safe_str(worldwide_context.get("status")),
            "feature_count": safe_int(worldwide_context.get("feature_count")),
            "source_tier": "community_global",
            "review_required": True,
        }

    online_layers = online_import_to_gis_layers(*layer_imports)
    imagery_detection = safe_dict(task_payloads.get("imagery_object_detection"))
    source_results["imagery_object_detection"] = imagery_detection
    source_fetch_metrics = {
        "version": "source_context_fetch_metrics_v1",
        "mode": "concurrent_provider_fanout",
        "task_count": len(source_tasks),
        "max_parallel_workers": min(8, len(source_tasks)) if source_tasks else 0,
        "elapsed_seconds": round(monotonic() - fetch_started, 3),
        "source_elapsed_seconds": source_timings,
        "failed_task_count": sum(
            1
            for payload in task_payloads.values()
            if safe_str(safe_dict(payload).get("status")) in {"fetch_failed", "provider_failed"}
        ),
    }
    warnings.extend(safe_list(online_layers.get("warnings")))
    source_strategy = _location_source_strategy(
        location_context=location_context,
        provider_packs=provider_packs,
        worldwide_context=worldwide_context,
        source_results=source_results,
    )
    dem_lidar = {
        "ready": bool(terrain_grid.get("success") or elevation.get("success")),
        "source": safe_str(terrain_grid.get("source") or elevation.get("source"), "missing"),
        "source_type": safe_str(terrain_grid.get("source_type") or elevation.get("source_type"), "usgs_3dep_elevation_grid"),
        "source_tier": safe_str(terrain_grid.get("source_tier") or elevation.get("source_tier")),
        "provider": safe_str(terrain_grid.get("provider") or elevation.get("provider")),
        "horizontal_resolution": safe_str(terrain_grid.get("horizontal_resolution") or elevation.get("horizontal_resolution")),
        "vertical_datum": safe_str(terrain_grid.get("vertical_datum") or elevation.get("vertical_datum")),
        "attribution": safe_str(terrain_grid.get("attribution") or elevation.get("attribution")),
        "sample_elevation": {
            "lat": center_lat,
            "lng": center_lng,
            "elevation": elevation.get("elevation"),
            "units": elevation.get("units"),
        } if elevation.get("success") else {},
        "approved_for_production": False,
        "surface_grid": terrain_grid if terrain_grid.get("success") else {},
        "surface_sample_count": safe_int(terrain_grid.get("sample_count")),
        "min_elevation_ft": terrain_grid.get("min_elevation_ft"),
        "max_elevation_ft": terrain_grid.get("max_elevation_ft"),
        "elevation_range_ft": terrain_grid.get("elevation_range_ft"),
        "terrain_breakline_count": len(safe_list(safe_dict(online_layers.get("gis_layers")).get("terrain_breaklines"))),
        "lidar_coverage_count": len(safe_list(safe_dict(online_layers.get("gis_layers")).get("lidar_coverage"))),
        "surface_ready": bool(terrain_grid.get("success") and terrain_grid.get("surface_ready")),
        "truth_label": "Public DEM surface context only; project grading still needs accepted source review and survey/control where required.",
    }
    canonical = {
        "survey": {"source": "missing", "point_count": 0, "points": []},
        "gis_layers": online_layers.get("gis_layers"),
        "existing_conditions": online_layers.get("gis_layers"),
        "coordinate_system": {"name": "EPSG:4326", "epsg": "EPSG:4326", "units": "degrees", "source": "online_public_sources"},
        "dem_lidar": dem_lidar,
        "sources": [
            {
                "key": key,
                "source_type": safe_str(result.get("source_type")),
                "source_tier": safe_str(result.get("source_tier")),
                "provider": safe_str(result.get("provider")),
                "attribution": safe_str(result.get("attribution")),
                "status": safe_str(result.get("status")),
                "success": bool(result.get("success")),
            }
            for key, result in source_results.items()
        ],
        "local_gis_provider_registry_v1": registry,
        "location_source_strategy_v1": source_strategy,
    }
    feature_report = build_map_feature_detection_report(
        location_context=location_context,
        gis_layers=online_layers.get("gis_layers"),
        source_results=source_results,
        active_site_boundary=active_site_boundary,
        imagery_object_detection_report=imagery_detection,
    )
    discovery_report = build_online_existing_conditions_discovery_report(
        source_results=source_results,
        gis_layers=online_layers.get("gis_layers"),
        location_context=location_context,
        standards_jurisdiction=resolved_standards_jurisdiction,
        provider_registry=registry,
    )
    discovery_report["site_intelligence_summary_v1"] = safe_dict(feature_report.get("site_intelligence_summary_v1"))
    discovery_report["location_source_strategy_v1"] = source_strategy
    has_context = bool(
        online_layers.get("success")
        or elevation.get("success")
        or safe_int(imagery_detection.get("detection_count")) > 0
    )
    request_succeeded = bool(geocode.get("success") or has_context)
    return {
        "success": request_succeeded,
        "source_type": "online_existing_conditions_fetch",
        "status": "ready_with_context" if has_context else ("address_located_no_context" if geocode.get("success") else "no_sources_ready"),
        "bbox": working_bbox,
        "source_results": source_results,
        "location_context": location_context,
        ONLINE_DISCOVERY_VERSION: discovery_report,
        "map_feature_detection_report_v1": feature_report,
        "location_source_strategy_v1": source_strategy,
        "source_context_fetch_metrics_v1": source_fetch_metrics,
        "canonical_existing_conditions": canonical,
        "warnings": warnings,
        "truth_label": "Fetched online public context. This does not replace boundary/topo survey, utility locates, record drawings, or jurisdiction confirmation.",
    }


def build_online_source_urls(address: str = "", bbox: Optional[Dict[str, Any]] = None, parcel_service_url: str = "") -> Dict[str, Any]:
    params = {"address": safe_str(address), "benchmark": "Public_AR_Current", "format": "json"}
    return {
        "census_geocoder": f"{CENSUS_GEOCODER_URL}?{urlencode(params)}" if address else CENSUS_GEOCODER_URL,
        "usgs_elevation": USGS_EPQS_URL,
        "usgs_3dep_surface_grid": USGS_3DEP_GET_SAMPLES_URL,
        "fema_nfhl": FEMA_NFHL_MAPSERVER_URL,
        "usfws_wetlands": USFWS_WETLANDS_MAPSERVER_URL,
        "worldwide_mapped_context": DEFAULT_OVERPASS_URL,
        "global_point_elevation": DEFAULT_GLOBAL_ELEVATION_URL,
        "parcel_service": safe_str(parcel_service_url) or "unconfigured_county_specific_source",
        "building_footprints_service": "unconfigured_local_or_county_source",
        "roads_row_service": "unconfigured_local_or_county_source",
        "easements_service": "unconfigured_local_or_county_source",
        "zoning_service": "unconfigured_jurisdiction_source",
        "existing_utilities_service": "unconfigured_utility_owner_or_record_source",
        "bbox_required": bool(bbox is None),
    }


__all__ = [
    "CENSUS_GEOCODER_URL",
    "FEMA_NFHL_MAPSERVER_URL",
    "ONLINE_DISCOVERY_VERSION",
    "USFWS_WETLANDS_MAPSERVER_URL",
    "USGS_EPQS_URL",
    "USGS_3DEP_GET_SAMPLES_URL",
    "USGS_3DEP_IMAGE_SERVER_URL",
    "build_online_existing_conditions_discovery_report",
    "build_online_source_urls",
    "bbox_around_point",
    "bbox_center",
    "fetch_arcgis_layer_geojson",
    "fetch_configured_parcels",
    "fetch_unconfigured_gis_source",
    "fetch_fema_floodplain",
    "fetch_online_existing_conditions",
    "fetch_usfws_wetlands",
    "fetch_usgs_elevation_point",
    "fetch_usgs_elevation_grid",
    "derive_review_contours_from_terrain_grid",
    "geocode_address_census",
    "online_import_to_gis_layers",
]
