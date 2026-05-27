from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests

from .common import safe_dict, safe_float, safe_list, safe_str
from .existing_conditions import REQUIRED_GIS_LAYERS


CENSUS_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
USGS_EPQS_URL = "https://epqs.nationalmap.gov/v1/json"
FEMA_NFHL_MAPSERVER_URL = "https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer"
USFWS_WETLANDS_MAPSERVER_URL = "https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer"


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
        "matched_address": safe_str(first.get("matchedAddress")),
        "lat": safe_float(coords.get("y")),
        "lng": safe_float(coords.get("x")),
        "truth_label": "Public geocode for source discovery; verify against survey/site control before production.",
    }


def fetch_usgs_elevation_point(lat: float, lng: float, *, units: str = "Feet", session: Any = requests) -> Dict[str, Any]:
    params = {"x": lng, "y": lat, "wkid": 4326, "units": units, "includeDate": "true"}
    try:
        payload = _json_get(session, USGS_EPQS_URL, params)
    except Exception as exc:
        return {"success": False, "source_type": "usgs_3dep_epqs", "status": "fetch_failed", "warnings": [safe_str(exc)]}
    value = safe_dict(payload.get("value"))
    elevation = value.get("elevation")
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
        "truth_label": "Public DEM point elevation; not a stamped topographic survey.",
    }


def _arcgis_query_url(service_url: str, layer_id: int) -> str:
    return f"{service_url.rstrip('/')}/{int(layer_id)}/query"


def _bbox_geometry(bbox: Dict[str, Any]) -> str:
    xmin = safe_float(bbox.get("min_lng") or bbox.get("xmin") or bbox.get("west"))
    ymin = safe_float(bbox.get("min_lat") or bbox.get("ymin") or bbox.get("south"))
    xmax = safe_float(bbox.get("max_lng") or bbox.get("xmax") or bbox.get("east"))
    ymax = safe_float(bbox.get("max_lat") or bbox.get("ymax") or bbox.get("north"))
    return f"{xmin},{ymin},{xmax},{ymax}"


def fetch_arcgis_layer_geojson(
    *,
    service_url: str,
    layer_id: int,
    bbox: Dict[str, Any],
    source_type: str,
    layer_name: str,
    session: Any = requests,
) -> Dict[str, Any]:
    if not safe_dict(bbox):
        return {"success": False, "source_type": source_type, "status": "blocked", "warnings": ["Lat/lng bbox is required for online GIS layer fetch."]}
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
    }
    try:
        response = session.get(_arcgis_query_url(service_url, layer_id), params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return {"success": False, "source_type": source_type, "status": "fetch_failed", "warnings": [safe_str(exc)]}
    features = safe_list(safe_dict(payload).get("features"))
    return {
        "success": True,
        "source": _arcgis_query_url(service_url, layer_id),
        "source_type": source_type,
        "status": "ready",
        "layer_name": layer_name,
        "feature_count": len(features),
        "geojson": safe_dict(payload),
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
    session: Any = requests,
) -> Dict[str, Any]:
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
        session=session,
    )


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
    warnings: List[str] = []
    sources: List[Dict[str, Any]] = []
    for item in imports:
        rec = safe_dict(item)
        if not rec:
            continue
        sources.append({"source": safe_str(rec.get("source")), "source_type": safe_str(rec.get("source_type")), "success": bool(rec.get("success"))})
        warnings.extend(safe_list(rec.get("warnings")))
        if not rec.get("success"):
            continue
        layer_name = safe_str(rec.get("layer_name"))
        target = "floodplain" if layer_name == "floodplain" else "wetlands" if layer_name == "wetlands" else "parcels" if layer_name == "parcels" else ""
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


def fetch_online_existing_conditions(
    *,
    address: str = "",
    bbox: Optional[Dict[str, Any]] = None,
    parcel_service_url: str = "",
    parcel_layer_id: int = 0,
    include_floodplain: bool = True,
    include_wetlands: bool = True,
    include_parcels: bool = True,
    include_elevation: bool = True,
    session: Any = requests,
) -> Dict[str, Any]:
    source_results: Dict[str, Dict[str, Any]] = {}
    warnings: List[str] = []
    working_bbox = safe_dict(bbox)
    geocode = geocode_address_census(address, session=session) if safe_str(address) else {
        "success": False,
        "source_type": "census_geocoder",
        "status": "skipped",
        "warnings": ["No address supplied; geocoding skipped."],
    }
    source_results["geocode"] = geocode
    if not working_bbox and geocode.get("success"):
        working_bbox = bbox_around_point(safe_float(geocode.get("lat")), safe_float(geocode.get("lng")))
    if not working_bbox:
        warnings.append("Online existing-condition fetch needs either an address that geocodes or a lat/lng bbox.")
        return {
            "success": False,
            "source_type": "online_existing_conditions_fetch",
            "status": "blocked",
            "source_results": source_results,
            "canonical_existing_conditions": {
                "survey": {"source": "missing", "point_count": 0, "points": []},
                "gis_layers": {layer: [] for layer in REQUIRED_GIS_LAYERS},
                "coordinate_system": {"name": "EPSG:4326", "source": "online_public_sources"},
            },
            "warnings": warnings,
            "truth_label": "Online fetch blocked before any public context layers were imported.",
        }

    center_lat, center_lng = bbox_center(working_bbox)
    elevation = fetch_usgs_elevation_point(center_lat, center_lng, session=session) if include_elevation else {
        "success": False,
        "source_type": "usgs_3dep_epqs",
        "status": "skipped",
        "warnings": ["Elevation fetch skipped by request."],
    }
    source_results["elevation"] = elevation

    layer_imports: List[Dict[str, Any]] = []
    if include_floodplain:
        floodplain = fetch_fema_floodplain(working_bbox, session=session)
        source_results["floodplain"] = floodplain
        layer_imports.append(floodplain)
    if include_wetlands:
        wetlands = fetch_usfws_wetlands(working_bbox, session=session)
        source_results["wetlands"] = wetlands
        layer_imports.append(wetlands)
    if include_parcels:
        parcels = fetch_configured_parcels(
            working_bbox,
            service_url=parcel_service_url,
            layer_id=parcel_layer_id,
            session=session,
        )
        source_results["parcels"] = parcels
        layer_imports.append(parcels)

    online_layers = online_import_to_gis_layers(*layer_imports)
    warnings.extend(safe_list(online_layers.get("warnings")))
    dem_lidar = {
        "ready": bool(elevation.get("success")),
        "source": safe_str(elevation.get("source"), "missing"),
        "source_type": safe_str(elevation.get("source_type"), "usgs_3dep_epqs"),
        "sample_elevation": {
            "lat": center_lat,
            "lng": center_lng,
            "elevation": elevation.get("elevation"),
            "units": elevation.get("units"),
        } if elevation.get("success") else {},
        "approved_for_production": False,
        "truth_label": "Public DEM context only; production grading still needs survey/control or approved DEM source.",
    }
    canonical = {
        "survey": {"source": "missing", "point_count": 0, "points": []},
        "gis_layers": online_layers.get("gis_layers"),
        "existing_conditions": online_layers.get("gis_layers"),
        "coordinate_system": {"name": "EPSG:4326", "epsg": "EPSG:4326", "units": "degrees", "source": "online_public_sources"},
        "dem_lidar": dem_lidar,
        "sources": [
            {"key": key, "source_type": safe_str(result.get("source_type")), "status": safe_str(result.get("status")), "success": bool(result.get("success"))}
            for key, result in source_results.items()
        ],
    }
    return {
        "success": any(bool(result.get("success")) for result in source_results.values()),
        "source_type": "online_existing_conditions_fetch",
        "status": "ready_with_context" if any(bool(result.get("success")) for result in source_results.values()) else "no_sources_ready",
        "bbox": working_bbox,
        "source_results": source_results,
        "canonical_existing_conditions": canonical,
        "warnings": warnings,
        "truth_label": "Fetched online public context. This does not replace boundary/topo survey, utility locates, record drawings, or jurisdiction confirmation.",
    }


def build_online_source_urls(address: str = "", bbox: Optional[Dict[str, Any]] = None, parcel_service_url: str = "") -> Dict[str, Any]:
    params = {"address": safe_str(address), "benchmark": "Public_AR_Current", "format": "json"}
    return {
        "census_geocoder": f"{CENSUS_GEOCODER_URL}?{urlencode(params)}" if address else CENSUS_GEOCODER_URL,
        "usgs_elevation": USGS_EPQS_URL,
        "fema_nfhl": FEMA_NFHL_MAPSERVER_URL,
        "usfws_wetlands": USFWS_WETLANDS_MAPSERVER_URL,
        "parcel_service": safe_str(parcel_service_url) or "unconfigured_county_specific_source",
        "bbox_required": bool(bbox is None),
    }


__all__ = [
    "CENSUS_GEOCODER_URL",
    "FEMA_NFHL_MAPSERVER_URL",
    "USFWS_WETLANDS_MAPSERVER_URL",
    "USGS_EPQS_URL",
    "build_online_source_urls",
    "bbox_around_point",
    "bbox_center",
    "fetch_arcgis_layer_geojson",
    "fetch_configured_parcels",
    "fetch_fema_floodplain",
    "fetch_online_existing_conditions",
    "fetch_usfws_wetlands",
    "fetch_usgs_elevation_point",
    "geocode_address_census",
    "online_import_to_gis_layers",
]
