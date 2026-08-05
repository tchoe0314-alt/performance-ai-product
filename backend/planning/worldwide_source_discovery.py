from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import math
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from .common import safe_dict, safe_float, safe_int, safe_list, safe_str


DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_OVERPASS_FALLBACK_URL = "https://overpass.kumi.systems/api/interpreter"
DEFAULT_GLOBAL_ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
OPENSTREETMAP_ATTRIBUTION = "OpenStreetMap contributors, ODbL 1.0"
GLOBAL_ELEVATION_ATTRIBUTION = "Open-Meteo elevation API; Copernicus DEM"
WORLDWIDE_SOURCE_VERSION = "worldwide_source_context_v1"

_CACHE_MAX_ITEMS = 64
_CACHE_TTL_SECONDS = 900.0
_CACHE: "OrderedDict[str, Tuple[float, Dict[str, Any]]]" = OrderedDict()
_CACHE_LOCK = threading.Lock()


def _bbox_bounds(bbox: Dict[str, Any]) -> Tuple[float, float, float, float]:
    return (
        safe_float(bbox.get("min_lng") or bbox.get("xmin") or bbox.get("west")),
        safe_float(bbox.get("min_lat") or bbox.get("ymin") or bbox.get("south")),
        safe_float(bbox.get("max_lng") or bbox.get("xmax") or bbox.get("east")),
        safe_float(bbox.get("max_lat") or bbox.get("ymax") or bbox.get("north")),
    )


def _bbox_area_sq_km(bbox: Dict[str, Any]) -> float:
    west, south, east, north = _bbox_bounds(bbox)
    mean_lat = math.radians((south + north) / 2.0)
    width_km = abs(east - west) * 111.32 * max(abs(math.cos(mean_lat)), 0.01)
    height_km = abs(north - south) * 110.574
    return width_km * height_km


def _validate_bbox(bbox: Dict[str, Any], *, max_area_sq_km: float) -> Optional[str]:
    west, south, east, north = _bbox_bounds(bbox)
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        return "Worldwide mapped-context lookup needs a valid WGS84 site bounding box."
    area = _bbox_area_sq_km(bbox)
    if area > max_area_sq_km:
        return f"Worldwide mapped-context lookup is limited to {max_area_sq_km:g} square kilometers per site request; requested area is approximately {area:.2f}."
    return None


def _cache_key(endpoint: str, bbox: Dict[str, Any], max_features: int) -> str:
    west, south, east, north = _bbox_bounds(bbox)
    return f"{endpoint}|{west:.6f}|{south:.6f}|{east:.6f}|{north:.6f}|{max_features}"


def _overpass_endpoints(endpoint: str) -> List[str]:
    configured = safe_str(endpoint or os.getenv("CIVORA_OVERPASS_URL"))
    values = [item.strip() for item in configured.split(",") if item.strip()]
    if not values:
        values = [DEFAULT_OVERPASS_URL, DEFAULT_OVERPASS_FALLBACK_URL]
    return list(dict.fromkeys(values))[:3]


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if not cached:
            return None
        created_at, payload = cached
        if now - created_at > _CACHE_TTL_SECONDS:
            _CACHE.pop(key, None)
            return None
        _CACHE.move_to_end(key)
        return deepcopy(payload)


def _cache_put(key: str, payload: Dict[str, Any]) -> None:
    with _CACHE_LOCK:
        _CACHE[key] = (time.monotonic(), deepcopy(payload))
        _CACHE.move_to_end(key)
        while len(_CACHE) > _CACHE_MAX_ITEMS:
            _CACHE.popitem(last=False)


def _get_json(
    session: Any,
    url: str,
    *,
    params: Dict[str, Any],
    timeout: float,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    try:
        response = session.get(url, params=params, timeout=timeout, headers=headers or {})
    except TypeError:
        response = session.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return safe_dict(response.json())


def _overpass_limits(max_features: int) -> Dict[str, int]:
    limits = {
        "building_footprints": max(1, int(max_features * 0.35)),
        "roads": max(1, int(max_features * 0.25)),
        "sidewalks": max(1, int(max_features * 0.20)),
        "site_context": max(1, int(max_features * 0.15)),
    }
    limits["existing_utilities"] = max(1, max_features - sum(limits.values()))
    return limits


def _overpass_query(bbox: Dict[str, Any], *, max_features: int, query_timeout_seconds: int = 9) -> str:
    west, south, east, north = _bbox_bounds(bbox)
    bounds = f"{south:.7f},{west:.7f},{north:.7f},{east:.7f}"
    limits = _overpass_limits(max_features)
    return "\n".join(
        [
            f"[out:json][timeout:{max(2, min(safe_int(query_timeout_seconds, 9), 20))}][bbox:{bounds}];",
            "(",
            '  way["building"];',
            '  relation["building"];',
            ")->.buildings;",
            f".buildings out tags geom qt {limits['building_footprints']};",
            "(",
            '  way["highway"]["highway"!~"^(footway|path|pedestrian|steps|cycleway|bridleway)$"];',
            ")->.roadways;",
            f".roadways out tags geom qt {limits['roads']};",
            "(",
            '  way["highway"~"^(footway|path|pedestrian|steps|cycleway|bridleway)$"];',
            ")->.paths;",
            f".paths out tags geom qt {limits['sidewalks']};",
            "(",
            '  way["amenity"="parking"];',
            '  relation["amenity"="parking"];',
            '  way["natural"="water"];',
            '  relation["natural"="water"];',
            '  way["water"];',
            '  way["waterway"];',
            '  way["landuse"~"^(basin|reservoir)$"];',
            ")->.sitecontext;",
            f".sitecontext out tags geom qt {limits['site_context']};",
            "(",
            '  way["man_made"="pipeline"];',
            '  way["power"~"^(line|minor_line)$"];',
            '  node["emergency"="fire_hydrant"];',
            '  node["man_made"="manhole"];',
            ")->.utilities;",
            f".utilities out tags geom qt {limits['existing_utilities']};",
        ]
    )


def _coordinates(raw_geometry: Any) -> List[List[float]]:
    coordinates: List[List[float]] = []
    for item in safe_list(raw_geometry):
        point = safe_dict(item)
        lat = point.get("lat")
        lon = point.get("lon")
        if lat in (None, "") or lon in (None, ""):
            continue
        coordinates.append([safe_float(lon), safe_float(lat)])
    return coordinates


def _closed_ring(coordinates: List[List[float]]) -> List[List[float]]:
    if len(coordinates) < 3:
        return []
    ring = [list(point) for point in coordinates]
    if ring[0] != ring[-1]:
        ring.append(list(ring[0]))
    return ring if len(ring) >= 4 else []


def _element_geometry(element: Dict[str, Any], *, polygon_preferred: bool) -> Dict[str, Any]:
    element_type = safe_str(element.get("type"))
    if element_type == "node":
        if element.get("lat") in (None, "") or element.get("lon") in (None, ""):
            return {}
        return {"type": "Point", "coordinates": [safe_float(element.get("lon")), safe_float(element.get("lat"))]}
    if element_type == "relation":
        polygons: List[List[List[List[float]]]] = []
        for member in safe_list(element.get("members")):
            member_rec = safe_dict(member)
            if safe_str(member_rec.get("type")) != "way" or safe_str(member_rec.get("role")) not in {"", "outer"}:
                continue
            ring = _closed_ring(_coordinates(member_rec.get("geometry")))
            if ring:
                polygons.append([ring])
        if polygons:
            return {"type": "MultiPolygon", "coordinates": polygons}
        return {}
    coordinates = _coordinates(element.get("geometry"))
    if polygon_preferred:
        ring = _closed_ring(coordinates)
        return {"type": "Polygon", "coordinates": [ring]} if ring else {}
    if len(coordinates) >= 2:
        return {"type": "LineString", "coordinates": coordinates}
    return {}


def _classify_element(element: Dict[str, Any]) -> Tuple[str, bool]:
    tags = safe_dict(element.get("tags"))
    if safe_str(tags.get("building")):
        return "building_footprints", True
    if safe_str(tags.get("amenity")) == "parking" or safe_str(tags.get("parking")):
        return "parking", True
    highway = safe_str(tags.get("highway"))
    if highway:
        if highway in {"footway", "path", "pedestrian", "steps", "cycleway", "bridleway"}:
            return "sidewalks", False
        return "roads", False
    if (
        safe_str(tags.get("natural")) == "water"
        or safe_str(tags.get("water"))
        or safe_str(tags.get("waterway"))
        or safe_str(tags.get("landuse")) in {"basin", "reservoir"}
    ):
        return "water", not bool(safe_str(tags.get("waterway")))
    if (
        safe_str(tags.get("man_made")) in {"pipeline", "manhole"}
        or safe_str(tags.get("power")) in {"line", "minor_line"}
        or safe_str(tags.get("emergency")) == "fire_hydrant"
    ):
        return "existing_utilities", False
    return "", False


def _layer_result(layer_name: str, features: List[Dict[str, Any]], *, endpoint: str) -> Dict[str, Any]:
    warnings = [
        "OpenStreetMap is community-mapped context. Coverage, currency, tags, and positional accuracy vary by location.",
    ]
    if layer_name == "roads":
        warnings.append("Mapped road centerlines are not right-of-way or survey boundaries.")
    elif layer_name == "existing_utilities":
        warnings.append("Mapped utility features are incomplete context and never replace utility-owner records, locates, or field verification.")
    elif layer_name == "building_footprints":
        warnings.append("Mapped building outlines are not surveyed structure locations.")
    return {
        "success": bool(features),
        "status": "ready" if features else "ready_empty",
        "source": endpoint,
        "source_type": "openstreetmap_overpass",
        "source_tier": "community_global",
        "provider": "OpenStreetMap",
        "provider_id": "openstreetmap_overpass",
        "layer_name": layer_name,
        "geojson": {"type": "FeatureCollection", "features": features},
        "feature_count": len(features),
        "review_required": True,
        "authoritative": False,
        "survey_backed": False,
        "attribution": OPENSTREETMAP_ATTRIBUTION,
        "warnings": warnings,
        "truth_label": "Community-mapped context only; confirm against authoritative records and project survey before reliance.",
    }


def fetch_openstreetmap_site_context(
    bbox: Dict[str, Any],
    *,
    session: Any = requests,
    endpoint: str = "",
    max_features: int = 1200,
    max_area_sq_km: float = 25.0,
    request_timeout_seconds: float = 5.0,
) -> Dict[str, Any]:
    endpoints = _overpass_endpoints(endpoint)
    max_features = min(max(safe_int(max_features, 1200), 1), 2500)
    bbox_error = _validate_bbox(safe_dict(bbox), max_area_sq_km=max_area_sq_km)
    if bbox_error:
        return {
            "success": False,
            "status": "blocked",
            "source_type": "openstreetmap_overpass",
            "source_tier": "community_global",
            "provider": "OpenStreetMap",
            "layer_results": {},
            "warnings": [bbox_error],
            "review_required": True,
            "authoritative": False,
            "survey_backed": False,
            "attribution": OPENSTREETMAP_ATTRIBUTION,
            "truth_label": "Worldwide mapped context was blocked; no features were inferred.",
        }
    cache_key = _cache_key(",".join(endpoints), bbox, max_features)
    use_cache = session is requests
    if use_cache:
        cached = _cache_get(cache_key)
        if cached is not None:
            cached["cache_status"] = "hit"
            return cached
    request_timeout = min(max(safe_float(request_timeout_seconds, 5.0), 3.0), 30.0)
    query = _overpass_query(
        bbox,
        max_features=max_features,
        query_timeout_seconds=max(2, int(request_timeout) - 1),
    )
    payload: Dict[str, Any] = {}
    resolved_endpoint = ""
    endpoint_errors: List[str] = []
    for candidate_endpoint in endpoints:
        try:
            payload = _get_json(
                session,
                candidate_endpoint,
                params={"data": query},
                timeout=request_timeout,
                headers={"User-Agent": "CivoraAI/0.1 (source-context; contact: support@civora.ai)"},
            )
            resolved_endpoint = candidate_endpoint
            break
        except Exception as exc:
            endpoint_errors.append(f"{candidate_endpoint}: {safe_str(exc, 'request failed')}")
    if not resolved_endpoint:
        return {
            "success": False,
            "status": "fetch_failed",
            "source": endpoints[0] if endpoints else DEFAULT_OVERPASS_URL,
            "source_type": "openstreetmap_overpass",
            "source_tier": "community_global",
            "provider": "OpenStreetMap",
            "layer_results": {},
            "warnings": endpoint_errors or ["OpenStreetMap context request failed."],
            "review_required": True,
            "authoritative": False,
            "survey_backed": False,
            "attribution": OPENSTREETMAP_ATTRIBUTION,
            "truth_label": "Worldwide mapped context was unavailable; no features were inferred from the address alone.",
        }
    grouped: Dict[str, List[Dict[str, Any]]] = {
        "building_footprints": [],
        "roads": [],
        "parking": [],
        "sidewalks": [],
        "water": [],
        "existing_utilities": [],
    }
    elements = safe_list(payload.get("elements"))[:max_features]
    seen_elements = set()
    for element in elements:
        rec = safe_dict(element)
        element_key = (safe_str(rec.get("type")), safe_str(rec.get("id")))
        if element_key in seen_elements:
            continue
        seen_elements.add(element_key)
        layer_name, polygon_preferred = _classify_element(rec)
        if not layer_name:
            continue
        geometry = _element_geometry(rec, polygon_preferred=polygon_preferred)
        if not geometry:
            continue
        osm_type = safe_str(rec.get("type"), "element")
        osm_id = safe_str(rec.get("id"))
        grouped[layer_name].append(
            {
                "type": "Feature",
                "id": f"osm-{osm_type}-{osm_id}",
                "geometry": geometry,
                "properties": {
                    "osm_id": osm_id,
                    "osm_type": osm_type,
                    "osm_tags": safe_dict(rec.get("tags")),
                    "source_tier": "community_global",
                    "community_mapped": True,
                    "authoritative": False,
                    "review_required": True,
                },
            }
        )
    layer_results = {
        layer_name: _layer_result(layer_name, features, endpoint=resolved_endpoint)
        for layer_name, features in grouped.items()
    }
    feature_count = sum(len(features) for features in grouped.values())
    limits = _overpass_limits(max_features)
    observed_by_budget = {
        "building_footprints": len(grouped["building_footprints"]),
        "roads": len(grouped["roads"]),
        "sidewalks": len(grouped["sidewalks"]),
        "site_context": len(grouped["parking"]) + len(grouped["water"]),
        "existing_utilities": len(grouped["existing_utilities"]),
    }
    budget_limited_categories = [
        category
        for category, observed in observed_by_budget.items()
        if observed >= limits[category]
    ]
    result = {
        "version": WORLDWIDE_SOURCE_VERSION,
        "success": True,
        "status": "ready" if feature_count else "ready_empty",
        "source": resolved_endpoint,
        "source_type": "openstreetmap_overpass",
        "source_tier": "community_global",
        "provider": "OpenStreetMap",
        "feature_count": feature_count,
        "element_count": len(elements),
        "truncated": len(safe_list(payload.get("elements"))) > len(elements),
        "result_budget_reached": bool(budget_limited_categories),
        "budget_limited_categories": budget_limited_categories,
        "bbox_area_sq_km": round(_bbox_area_sq_km(bbox), 4),
        "layer_results": layer_results,
        "review_required": True,
        "authoritative": False,
        "survey_backed": False,
        "cache_status": "miss",
        "attribution": OPENSTREETMAP_ATTRIBUTION,
        "warnings": [
            "Worldwide mapped context is best-effort and may be incomplete or outdated.",
            "Parcels, right-of-way, easements, zoning, and subsurface utilities still require authoritative local sources.",
            *(
                ["Mapped-context result budget was reached for: " + ", ".join(budget_limited_categories) + ". More mapped features may exist."]
                if budget_limited_categories
                else []
            ),
            *([f"Primary mapped-context endpoint failed before fallback succeeded: {endpoint_errors[0]}"] if endpoint_errors else []),
        ],
        "truth_label": "Worldwide mapped features are candidates for review, not survey/control or jurisdiction records.",
    }
    if use_cache:
        _cache_put(cache_key, result)
    return result


def fetch_global_elevation_point(
    lat: float,
    lng: float,
    *,
    session: Any = requests,
    endpoint: str = "",
) -> Dict[str, Any]:
    resolved_endpoint = safe_str(endpoint or os.getenv("CIVORA_GLOBAL_ELEVATION_URL"), DEFAULT_GLOBAL_ELEVATION_URL)
    try:
        payload = _get_json(
            session,
            resolved_endpoint,
            params={"latitude": safe_float(lat), "longitude": safe_float(lng)},
            timeout=12.0,
            headers={"User-Agent": "CivoraAI/0.1 (source-context; contact: support@civora.ai)"},
        )
    except Exception as exc:
        return {
            "success": False,
            "status": "fetch_failed",
            "source": resolved_endpoint,
            "source_type": "global_dem_point_elevation",
            "source_tier": "global_public_context",
            "warnings": [safe_str(exc, "Global elevation request failed.")],
            "review_required": True,
            "authoritative": False,
            "survey_backed": False,
            "attribution": GLOBAL_ELEVATION_ATTRIBUTION,
            "truth_label": "Global elevation was unavailable; no terrain elevation was inferred.",
        }
    elevations = safe_list(payload.get("elevation"))
    if not elevations or elevations[0] in (None, ""):
        return {
            "success": False,
            "status": "no_elevation",
            "source": resolved_endpoint,
            "source_type": "global_dem_point_elevation",
            "source_tier": "global_public_context",
            "warnings": ["Global elevation provider returned no usable point elevation."],
            "review_required": True,
            "authoritative": False,
            "survey_backed": False,
            "attribution": GLOBAL_ELEVATION_ATTRIBUTION,
            "truth_label": "Global elevation provider returned no usable point; no terrain elevation was inferred.",
        }
    return {
        "success": True,
        "status": "ready",
        "source": resolved_endpoint,
        "source_type": "global_dem_point_elevation",
        "source_tier": "global_public_context",
        "provider": "Open-Meteo elevation",
        "lat": safe_float(lat),
        "lng": safe_float(lng),
        "elevation": safe_float(elevations[0]),
        "units": "meters",
        "horizontal_resolution": "approximately 90 meters",
        "review_required": True,
        "authoritative": False,
        "survey_backed": False,
        "attribution": GLOBAL_ELEVATION_ATTRIBUTION,
        "truth_label": "Global DEM point elevation is terrain context only; it is not a topographic survey or grading surface.",
    }


def fetch_global_elevation_grid(
    bbox: Dict[str, Any],
    *,
    rows: int = 5,
    cols: int = 5,
    session: Any = requests,
    endpoint: str = "",
) -> Dict[str, Any]:
    resolved_endpoint = safe_str(endpoint or os.getenv("CIVORA_GLOBAL_ELEVATION_URL"), DEFAULT_GLOBAL_ELEVATION_URL)
    west, south, east, north = _bbox_bounds(safe_dict(bbox))
    rows = min(max(safe_int(rows, 5), 2), 9)
    cols = min(max(safe_int(cols, 5), 2), 9)
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        return {
            "success": False,
            "status": "blocked",
            "source": resolved_endpoint,
            "source_type": "global_dem_elevation_grid",
            "source_tier": "global_public_context",
            "warnings": ["Global terrain-grid lookup needs a valid WGS84 site bounding box."],
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
    try:
        payload = _get_json(
            session,
            resolved_endpoint,
            params={
                "latitude": ",".join(f"{item['lat']:.7f}" for item in requested),
                "longitude": ",".join(f"{item['lng']:.7f}" for item in requested),
            },
            timeout=15.0,
            headers={"User-Agent": "CivoraAI/0.1 (source-context; contact: support@civora.ai)"},
        )
    except Exception as exc:
        return {
            "success": False,
            "status": "fetch_failed",
            "source": resolved_endpoint,
            "source_type": "global_dem_elevation_grid",
            "source_tier": "global_public_context",
            "warnings": [safe_str(exc, "Global terrain-grid request failed.")],
            "review_required": True,
            "authoritative": False,
            "survey_backed": False,
            "attribution": GLOBAL_ELEVATION_ATTRIBUTION,
        }
    elevations = safe_list(payload.get("elevation"))
    samples: List[Dict[str, Any]] = []
    for index, item in enumerate(requested):
        if index >= len(elevations) or elevations[index] in (None, ""):
            continue
        elevation_m = safe_float(elevations[index])
        samples.append(
            {
                **item,
                "elevation_m": elevation_m,
                "elevation_ft": elevation_m * 3.280839895,
            }
        )
    if len(samples) < 4:
        return {
            "success": False,
            "status": "no_elevation",
            "source": resolved_endpoint,
            "source_type": "global_dem_elevation_grid",
            "source_tier": "global_public_context",
            "sample_count": len(samples),
            "warnings": ["Global elevation provider returned too few usable samples for a terrain surface."],
            "review_required": True,
            "authoritative": False,
            "survey_backed": False,
            "attribution": GLOBAL_ELEVATION_ATTRIBUTION,
        }
    elevations_ft = [safe_float(item.get("elevation_ft")) for item in samples]
    return {
        "success": True,
        "status": "ready",
        "source": resolved_endpoint,
        "source_type": "global_dem_elevation_grid",
        "source_tier": "global_public_context",
        "provider": "Open-Meteo elevation",
        "rows": rows,
        "cols": cols,
        "sample_count": len(samples),
        "missing_sample_count": rows * cols - len(samples),
        "samples": samples,
        "min_elevation_ft": min(elevations_ft),
        "max_elevation_ft": max(elevations_ft),
        "elevation_range_ft": max(elevations_ft) - min(elevations_ft),
        "units": "feet",
        "horizontal_resolution": "approximately 90 meters",
        "surface_ready": True,
        "review_required": True,
        "authoritative": False,
        "survey_backed": False,
        "attribution": GLOBAL_ELEVATION_ATTRIBUTION,
        "truth_label": "Global DEM grid is approximate terrain context only; it is not survey/control or an accepted grading surface.",
    }


__all__ = [
    "DEFAULT_GLOBAL_ELEVATION_URL",
    "DEFAULT_OVERPASS_FALLBACK_URL",
    "DEFAULT_OVERPASS_URL",
    "GLOBAL_ELEVATION_ATTRIBUTION",
    "OPENSTREETMAP_ATTRIBUTION",
    "WORLDWIDE_SOURCE_VERSION",
    "fetch_global_elevation_grid",
    "fetch_global_elevation_point",
    "fetch_openstreetmap_site_context",
]
