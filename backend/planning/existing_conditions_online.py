from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests

from .common import safe_dict, safe_float, safe_list, safe_str
from .existing_conditions import REQUIRED_GIS_LAYERS
from .gis_provider_registry import (
    build_provider_registry,
    providers_for_source_type,
    selected_provider,
    target_market_known_gaps,
    target_market_provider_records,
)
from .map_feature_detection import build_map_feature_detection_report, location_context_from_geocode
from .standards_discovery import discover_standards_sources


CENSUS_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
USGS_EPQS_URL = "https://epqs.nationalmap.gov/v1/json"
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
    "road_row": {
        "label": "road/ROW data",
        "result_keys": ("roads_row",),
        "layer_keys": ("roads", "row"),
    },
    "terrain_dem_lidar": {
        "label": "terrain/DEM/LiDAR",
        "result_keys": ("elevation",),
        "layer_keys": (),
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
    provider: Optional[Dict[str, Any]] = None,
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
    provider_record = safe_dict(provider)
    return {
        "success": True,
        "source": _arcgis_query_url(service_url, layer_id),
        "source_type": source_type,
        "status": "ready",
        "layer_name": layer_name,
        "feature_count": len(features),
        "geojson": safe_dict(payload),
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
        "warnings": [f"No {label} GIS source is configured. Configure/import an official source before detection."],
    }


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


def _candidate_count_for_source(*, source_key: str, result: Dict[str, Any], gis_layers: Dict[str, Any], layer_keys: Tuple[str, ...]) -> int:
    if source_key == "terrain_dem_lidar":
        return 1 if result.get("success") else 0
    count = sum(len(safe_list(gis_layers.get(key))) for key in layer_keys)
    if count:
        return count
    geojson_features = safe_list(safe_dict(result.get("geojson")).get("features"))
    return len(geojson_features)


def _source_blockers(*, label: str, result_records: List[Dict[str, Any]], candidate_count: int) -> List[str]:
    blockers: List[str] = []
    if candidate_count:
        blockers.append(f"{label} candidates are review-required and not survey-backed.")
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
    return {
        "key": key,
        "label": label,
        "source_url": _source_url(first),
        "agency": safe_str(first.get("agency") or first.get("layer_name") or first.get("source_type")),
        "provider": safe_str(first.get("provider") or first.get("source_type")),
        "confidence": "candidate" if success else "unavailable",
        "source_type": safe_str(first.get("source_type"), key),
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
        if key == "terrain_dem_lidar":
            count = sum(
                _candidate_count_for_source(source_key=key, result=result, gis_layers=layers, layer_keys=())
                for result in result_records
            )
        else:
            layer_keys = tuple(spec.get("layer_keys", ()))
            count = sum(len(safe_list(layers.get(layer_key))) for layer_key in layer_keys)
            if not count:
                count = sum(len(safe_list(safe_dict(result.get("geojson")).get("features"))) for result in result_records)
        blockers = _source_blockers(label=label, result_records=result_records, candidate_count=count)
        record = _source_record(key=key, label=label, result_records=result_records, candidate_count=count, blockers=blockers)
        for gap in known_gaps:
            gap_rec = safe_dict(gap)
            if normalize_gap := safe_str(gap_rec.get("source_type")):
                if normalize_gap == safe_str(spec.get("result_keys", ("",))[0]) or normalize_gap in spec.get("layer_keys", ()):
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
    supported_live_providers = [
        {
            "key": "census_geocoder",
            "provider": "US Census Geocoder",
            "source_url": CENSUS_GEOCODER_URL,
            "supports": ["address/location context"],
            "status": safe_str(safe_dict(results.get("geocode")).get("status"), "available"),
        },
        {
            "key": "usgs_3dep_epqs",
            "provider": "USGS 3DEP EPQS",
            "source_url": USGS_EPQS_URL,
            "supports": ["terrain/DEM point elevation"],
            "status": safe_str(safe_dict(results.get("elevation")).get("status"), "available"),
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
        "configured_provider_count": registry.get("configured_provider_count", 0),
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


def fetch_online_existing_conditions(
    *,
    address: str = "",
    bbox: Optional[Dict[str, Any]] = None,
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
    standards_jurisdiction: Optional[Dict[str, Any]] = None,
    provider_registry: Optional[Dict[str, Any]] = None,
    session: Any = requests,
) -> Dict[str, Any]:
    source_results: Dict[str, Dict[str, Any]] = {}
    warnings: List[str] = []
    registry = safe_dict(provider_registry) or build_provider_registry(include_builtin=True)
    working_bbox = safe_dict(bbox)
    geocode = geocode_address_census(address, session=session) if safe_str(address) else {
        "success": False,
        "source_type": "census_geocoder",
        "status": "skipped",
        "warnings": ["No address supplied; geocoding skipped."],
    }
    source_results["geocode"] = geocode
    location_context = location_context_from_geocode(address=address, geocode=geocode)
    target_records = target_market_provider_records(
        address=address,
        lat=safe_float(geocode.get("lat")) if geocode.get("success") else None,
        lng=safe_float(geocode.get("lng")) if geocode.get("success") else None,
    )
    if target_records:
        registry = build_provider_registry(
            providers=safe_list(registry.get("providers")) + target_records,
            include_builtin=False,
        )
        registry["known_gaps"] = target_market_known_gaps(
            address=address,
            lat=safe_float(geocode.get("lat")) if geocode.get("success") else None,
            lng=safe_float(geocode.get("lng")) if geocode.get("success") else None,
        )
    if not working_bbox and geocode.get("success"):
        working_bbox = bbox_around_point(safe_float(geocode.get("lat")), safe_float(geocode.get("lng")))
    if not working_bbox:
        warnings.append("Online existing-condition fetch needs either an address that geocodes or a lat/lng bbox.")
        feature_report = build_map_feature_detection_report(
            location_context=location_context,
            gis_layers={layer: [] for layer in REQUIRED_GIS_LAYERS},
            source_results=source_results,
        )
        discovery_report = build_online_existing_conditions_discovery_report(
            source_results=source_results,
            gis_layers={layer: [] for layer in REQUIRED_GIS_LAYERS},
            location_context=location_context,
            standards_jurisdiction=standards_jurisdiction,
            provider_registry=registry,
        )
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
        parcel_provider = selected_provider(registry, "parcels")
        parcels = fetch_configured_parcels(
            working_bbox,
            service_url=parcel_service_url,
            layer_id=parcel_layer_id,
            provider=parcel_provider,
            session=session,
        )
        source_results["parcels"] = parcels
        layer_imports.append(parcels)
    if include_building_footprints:
        building_provider = selected_provider(registry, "buildings")
        building_arcgis = safe_dict(building_provider.get("arcgis"))
        building_url = safe_str(building_arcgis.get("service_url") or building_footprints_service_url)
        building_layer = int(building_arcgis.get("layer_id", building_footprints_layer_id) or 0)
        if safe_str(building_url):
            buildings = fetch_arcgis_layer_geojson(
                service_url=building_url,
                layer_id=building_layer,
                bbox=working_bbox,
                source_type="configured_building_footprints_arcgis",
                layer_name="building_footprints",
                provider=building_provider,
                session=session,
            )
        else:
            buildings = fetch_unconfigured_gis_source(source_type="configured_building_footprints_arcgis", label="building footprint")
        source_results["building_footprints"] = buildings
        layer_imports.append(buildings)
    if include_roads:
        roads_provider = selected_provider(registry, "roads_row")
        roads_arcgis = safe_dict(roads_provider.get("arcgis"))
        roads_url = safe_str(roads_arcgis.get("service_url") or roads_service_url)
        roads_layer = int(roads_arcgis.get("layer_id", roads_layer_id) or 0)
        if safe_str(roads_url):
            roads = fetch_arcgis_layer_geojson(
                service_url=roads_url,
                layer_id=roads_layer,
                bbox=working_bbox,
                source_type="configured_roads_row_arcgis",
                layer_name="roads",
                provider=roads_provider,
                session=session,
            )
        else:
            roads = fetch_unconfigured_gis_source(source_type="configured_roads_row_arcgis", label="roads/right-of-way")
        source_results["roads_row"] = roads
        layer_imports.append(roads)
    if include_easements:
        if safe_str(easements_service_url):
            easements = fetch_arcgis_layer_geojson(
                service_url=easements_service_url,
                layer_id=easements_layer_id,
                bbox=working_bbox,
                source_type="configured_easements_arcgis",
                layer_name="easements",
                session=session,
            )
        else:
            easements = fetch_unconfigured_gis_source(source_type="configured_easements_arcgis", label="easement")
        source_results["easements"] = easements
        layer_imports.append(easements)
    if include_zoning:
        if safe_str(zoning_service_url):
            zoning = fetch_arcgis_layer_geojson(
                service_url=zoning_service_url,
                layer_id=zoning_layer_id,
                bbox=working_bbox,
                source_type="configured_zoning_arcgis",
                layer_name="zoning",
                session=session,
            )
        else:
            zoning = fetch_unconfigured_gis_source(source_type="configured_zoning_arcgis", label="zoning")
        source_results["zoning"] = zoning
        layer_imports.append(zoning)
    if include_utilities:
        utilities_provider = selected_provider(registry, "utilities")
        utilities_arcgis = safe_dict(utilities_provider.get("arcgis"))
        utilities_url = safe_str(utilities_arcgis.get("service_url") or utilities_service_url)
        utilities_layer = int(utilities_arcgis.get("layer_id", utilities_layer_id) or 0)
        if safe_str(utilities_url):
            utilities = fetch_arcgis_layer_geojson(
                service_url=utilities_url,
                layer_id=utilities_layer,
                bbox=working_bbox,
                source_type="configured_existing_utilities_arcgis",
                layer_name="existing_utilities",
                provider=utilities_provider,
                session=session,
            )
        else:
            utilities = fetch_unconfigured_gis_source(source_type="configured_existing_utilities_arcgis", label="existing utilities")
        source_results["existing_utilities"] = utilities
        layer_imports.append(utilities)
    if include_contours:
        contours_provider = selected_provider(registry, "contours")
        contours_arcgis = safe_dict(contours_provider.get("arcgis"))
        contours_url = safe_str(contours_arcgis.get("service_url") or contours_service_url)
        contours_layer = int(contours_arcgis.get("layer_id", contours_layer_id) or 0)
        if safe_str(contours_url):
            contours = fetch_arcgis_layer_geojson(
                service_url=contours_url,
                layer_id=contours_layer,
                bbox=working_bbox,
                source_type="configured_contours_arcgis",
                layer_name="contours",
                provider=contours_provider,
                session=session,
            )
        else:
            contours = fetch_unconfigured_gis_source(source_type="configured_contours_arcgis", label="contour")
        source_results["contours"] = contours
        layer_imports.append(contours)

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
        "local_gis_provider_registry_v1": registry,
    }
    feature_report = build_map_feature_detection_report(
        location_context=location_context,
        gis_layers=online_layers.get("gis_layers"),
        source_results=source_results,
    )
    discovery_report = build_online_existing_conditions_discovery_report(
        source_results=source_results,
        gis_layers=online_layers.get("gis_layers"),
        location_context=location_context,
        standards_jurisdiction=standards_jurisdiction,
        provider_registry=registry,
    )
    return {
        "success": any(bool(result.get("success")) for result in source_results.values()),
        "source_type": "online_existing_conditions_fetch",
        "status": "ready_with_context" if any(bool(result.get("success")) for result in source_results.values()) else "no_sources_ready",
        "bbox": working_bbox,
        "source_results": source_results,
        "location_context": location_context,
        ONLINE_DISCOVERY_VERSION: discovery_report,
        "map_feature_detection_report_v1": feature_report,
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
    "geocode_address_census",
    "online_import_to_gis_layers",
]
