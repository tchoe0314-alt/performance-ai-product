from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from .common import safe_dict, safe_int, safe_list, safe_str


GIS_PROVIDER_REGISTRY_VERSION = "local_gis_provider_registry_v1"
GIS_SOURCE_TYPES = (
    "parcels",
    "buildings",
    "roads_row",
    "utilities",
    "contours",
    "elevation",
    "terrain_breaklines",
    "lidar_index",
    "floodplain",
    "wetlands",
    "zoning",
)
JURISDICTION_LEVELS = ("jurisdiction", "county", "city", "state", "federal", "utility")
DEFAULT_STALE_AFTER_DAYS = 90
SARPY_COUNTY_BBOX = {"west": -96.3426, "south": 40.9837, "east": -95.8407, "north": 41.2048}
DOUGLAS_COUNTY_BBOX = {"west": -96.32, "south": 41.19, "east": -95.80, "north": 41.40}
AUSTIN_BBOX = {"west": -97.94, "south": 30.05, "east": -97.56, "north": 30.52}
FULTON_COUNTY_BBOX = {"west": -84.85, "south": 33.50, "east": -84.05, "north": 34.25}
DALLAS_BBOX = {"west": -97.04, "south": 32.55, "east": -96.52, "north": 33.03}
HARRIS_COUNTY_BBOX = {"west": -96.04, "south": 29.49, "east": -94.91, "north": 30.17}
DENVER_COUNTY_BBOX = {"west": -105.11, "south": 39.61, "east": -104.60, "north": 39.92}
MARICOPA_COUNTY_BBOX = {"west": -113.34, "south": 32.50, "east": -111.04, "north": 34.05}
MECKLENBURG_COUNTY_BBOX = {"west": -81.06, "south": 35.00, "east": -80.55, "north": 35.52}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any) -> Optional[datetime]:
    text = safe_str(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _days_since(value: Any, *, now: Optional[datetime] = None) -> Optional[int]:
    dt = _parse_datetime(value)
    if dt is None:
        return None
    ref = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, int((ref - dt).total_seconds() // 86400))


def _provider_id(*, source_type: str, service_url: str, jurisdiction: Dict[str, Any], layer_id: int = 0) -> str:
    host = urlparse(service_url).netloc.replace(".", "-") if service_url else "unconfigured"
    scope = safe_str(jurisdiction.get("city") or jurisdiction.get("county") or jurisdiction.get("name") or jurisdiction.get("state") or "local")
    slug = "-".join("".join(ch.lower() if ch.isalnum() else "-" for ch in f"{scope}-{source_type}-{host}-{layer_id}").split("-"))
    return slug[:96] or f"{source_type}-{layer_id}"


def _arcgis_service_kind(service_url: str) -> str:
    lowered = safe_str(service_url).lower()
    if "/vectortileserver" in lowered:
        return "VectorTileServer"
    if "/featureserver" in lowered:
        return "FeatureServer"
    if "/mapserver" in lowered:
        return "MapServer"
    return "ArcGIS REST"


def normalize_source_type(value: str) -> str:
    text = safe_str(value).lower().replace("-", "_").replace("/", "_")
    aliases = {
        "parcel": "parcels",
        "parcel_site_boundary": "parcels",
        "building": "buildings",
        "building_footprints": "buildings",
        "roads": "roads_row",
        "row": "roads_row",
        "road_row": "roads_row",
        "right_of_way": "roads_row",
        "existing_utilities": "utilities",
        "utility": "utilities",
        "contour": "contours",
        "breaklines": "terrain_breaklines",
        "terrain_breakline": "terrain_breaklines",
        "lidar": "lidar_index",
        "lidar_tiles": "lidar_index",
        "fema": "floodplain",
        "flood": "floodplain",
        "wetland": "wetlands",
        "nwi": "wetlands",
    }
    return aliases.get(text, text)


def build_arcgis_provider_record(
    *,
    source_type: str,
    service_url: str,
    layer_id: int = 0,
    name: str = "",
    jurisdiction: Optional[Dict[str, Any]] = None,
    jurisdiction_level: str = "",
    provider_kind: str = "arcgis_rest",
    freshness_date: str = "",
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
    status: str = "configured",
    fixture_only: bool = False,
    notes: str = "",
) -> Dict[str, Any]:
    normalized_type = normalize_source_type(source_type)
    juris = safe_dict(jurisdiction)
    level = safe_str(jurisdiction_level or juris.get("level"), "jurisdiction")
    if level not in JURISDICTION_LEVELS:
        level = "jurisdiction"
    url = safe_str(service_url)
    layer = safe_int(layer_id, 0)
    record = {
        "id": _provider_id(source_type=normalized_type, service_url=url, jurisdiction=juris, layer_id=layer),
        "name": safe_str(name) or f"{level.title()} {normalized_type.replace('_', '/')} provider",
        "source_type": normalized_type,
        "jurisdiction_level": level,
        "jurisdiction": juris,
        "provider_kind": provider_kind,
        "service_url": url,
        "queryable": bool(url and "/vectortileserver" not in url.lower() and provider_kind != "vector_tile"),
        "arcgis": {
            "service_url": url,
            "service_kind": _arcgis_service_kind(url),
            "layer_id": layer,
            "query_url": f"{url.rstrip('/')}/{layer}/query" if url and "/vectortileserver" not in url.lower() else "",
            "out_sr": 4326,
            "in_sr": 4326,
        },
        "status": safe_str(status, "configured") if url else "unconfigured",
        "health": {"status": "unchecked", "checked_at": "", "message": "Health check has not run."},
        "freshness": provider_freshness_status({"freshness_date": freshness_date, "stale_after_days": stale_after_days}),
        "freshness_date": safe_str(freshness_date),
        "stale_after_days": safe_int(stale_after_days, DEFAULT_STALE_AFTER_DAYS),
        "fixture_only": bool(fixture_only),
        "review_required": True,
        "survey_backed": False,
        "truth_label": "GIS provider records configure context sources only; they are not survey/control evidence.",
        "notes": safe_str(notes),
    }
    return record


def build_known_provider_record(
    *,
    source_type: str,
    service_url: str,
    name: str,
    jurisdiction: Optional[Dict[str, Any]] = None,
    jurisdiction_level: str = "jurisdiction",
    provider_kind: str = "known_nonqueryable",
    status: str = "known_not_queryable",
    notes: str = "",
) -> Dict[str, Any]:
    normalized_type = normalize_source_type(source_type)
    juris = safe_dict(jurisdiction)
    url = safe_str(service_url)
    service_kind = _arcgis_service_kind(url)
    return {
        "id": _provider_id(source_type=normalized_type, service_url=url, jurisdiction=juris, layer_id=0),
        "name": safe_str(name) or f"Known {normalized_type} source",
        "source_type": normalized_type,
        "jurisdiction_level": safe_str(jurisdiction_level, "jurisdiction"),
        "jurisdiction": juris,
        "provider_kind": provider_kind,
        "service_url": url,
        "queryable": False,
        "arcgis": {"service_url": url, "service_kind": service_kind, "layer_id": 0, "query_url": "", "out_sr": 4326, "in_sr": 4326},
        "status": status,
        "health": {"status": "not_queryable", "checked_at": "", "ok": False, "message": f"{service_kind} is known but cannot be queried for candidate extraction."},
        "freshness": provider_freshness_status({}),
        "freshness_date": "",
        "stale_after_days": DEFAULT_STALE_AFTER_DAYS,
        "fixture_only": False,
        "review_required": True,
        "survey_backed": False,
        "truth_label": "Known GIS source metadata is context only; it is not survey/control evidence.",
        "notes": safe_str(notes) or f"{service_kind} is not usable for candidate extraction.",
    }


def provider_freshness_status(provider: Dict[str, Any], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    stale_after = safe_int(provider.get("stale_after_days"), DEFAULT_STALE_AFTER_DAYS)
    source_date = safe_str(provider.get("freshness_date") or provider.get("source_date") or provider.get("last_updated") or provider.get("updated_at"))
    age_days = _days_since(source_date, now=now)
    if age_days is None:
        return {
            "status": "unknown",
            "source_date": source_date,
            "age_days": None,
            "stale_after_days": stale_after,
            "stale": True,
            "message": "Provider freshness date is not recorded.",
        }
    stale = age_days > stale_after
    return {
        "status": "stale" if stale else "current",
        "source_date": source_date,
        "age_days": age_days,
        "stale_after_days": stale_after,
        "stale": stale,
        "message": f"Provider source date is {age_days} day(s) old.",
    }


def builtin_provider_records() -> List[Dict[str, Any]]:
    federal = {"level": "federal", "country": "US"}
    return [
        {
            "id": "us-census-geocoder-location-context",
            "name": "US Census Geocoder location context",
            "source_type": "location_context",
            "jurisdiction_level": "federal",
            "jurisdiction": federal,
            "provider_kind": "census_geocoder",
            "service_url": "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress",
            "queryable": True,
            "status": "configured",
            "health": {"status": "unchecked", "checked_at": "", "message": "Health check has not run."},
            "freshness": provider_freshness_status({}),
            "review_required": True,
            "survey_backed": False,
            "truth_label": "Geocoder context is not survey/control evidence.",
            "notes": "National address/location context fallback.",
        },
        {
            "id": "usgs-3dep-epqs-elevation",
            "name": "USGS 3DEP EPQS point elevation",
            "source_type": "elevation",
            "jurisdiction_level": "federal",
            "jurisdiction": federal,
            "provider_kind": "usgs_epqs",
            "service_url": "https://epqs.nationalmap.gov/v1/json",
            "queryable": True,
            "status": "configured",
            "health": {"status": "unchecked", "checked_at": "", "message": "Health check has not run."},
            "freshness": provider_freshness_status({}),
            "review_required": True,
            "survey_backed": False,
            "truth_label": "Public DEM elevation is not a topographic survey.",
            "notes": "National point elevation fallback where available.",
        },
        build_arcgis_provider_record(
            source_type="floodplain",
            service_url="https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer",
            layer_id=28,
            name="FEMA NFHL floodplain",
            jurisdiction=federal,
            jurisdiction_level="federal",
            provider_kind="arcgis_rest",
            status="configured",
            notes="National floodplain context layer.",
        ),
        build_arcgis_provider_record(
            source_type="wetlands",
            service_url="https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer",
            layer_id=0,
            name="USFWS NWI wetlands",
            jurisdiction=federal,
            jurisdiction_level="federal",
            provider_kind="arcgis_rest",
            status="configured",
            notes="National wetlands context layer.",
        ),
    ]


def _point_in_bbox(lat: Any, lng: Any, bbox: Dict[str, float]) -> bool:
    try:
        y = float(lat)
        x = float(lng)
    except (TypeError, ValueError):
        return False
    return bbox["south"] <= y <= bbox["north"] and bbox["west"] <= x <= bbox["east"]


def _pack_record(pack_id: str, label: str, jurisdiction: Dict[str, Any], providers: List[Dict[str, Any]], known_gaps: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "pack_id": pack_id,
        "label": label,
        "jurisdiction": jurisdiction,
        "providers": providers,
        "known_gaps": known_gaps,
        "review_required": True,
        "survey_backed": False,
        "truth_label": "Provider packs configure candidate public context sources only; they are not survey/control.",
    }


def _gap(source_type: str, label: str, message: str, *, status: str = "local_provider_unknown", source_url: str = "") -> Dict[str, Any]:
    record = {"source_type": source_type, "label": label, "status": status, "message": message}
    if source_url:
        record["source_url"] = source_url
    return record


def _address_mentions(text: str, *terms: str) -> bool:
    return any(term in text for term in terms)


def provider_packs_for_location(*, address: str = "", lat: Any = None, lng: Any = None, location_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    text = safe_str(address).lower()
    loc = safe_dict(location_context)
    if lat in (None, ""):
        lat = safe_dict(loc.get("coordinates")).get("lat") or safe_dict(loc.get("geocode")).get("lat")
    if lng in (None, ""):
        lng = safe_dict(loc.get("coordinates")).get("lng") or safe_dict(loc.get("geocode")).get("lng")
    packs: List[Dict[str, Any]] = []
    point_in_sarpy = _point_in_bbox(lat, lng, SARPY_COUNTY_BBOX)
    address_in_sarpy = "gretna" in text and (" ne" in text or "nebraska" in text)
    if point_in_sarpy or address_in_sarpy:
        sarpy = {"level": "county", "county": "Sarpy County", "state": "NE", "city": "Gretna", "target_market": "gretna_ne"}
        providers = [
        build_arcgis_provider_record(
            source_type="parcels",
            service_url="https://services.arcgis.com/OiG7dbwhQEWoy77N/arcgis/rest/services/Sarpy_Parcels_WFL1/FeatureServer",
            layer_id=0,
            name="Sarpy County tax parcels",
            jurisdiction=sarpy,
            jurisdiction_level="county",
            freshness_date="2023-12-09T00:00:00Z",
            notes="Public Sarpy County parcel polygons; candidate context only, not survey control.",
        ),
        build_arcgis_provider_record(
            source_type="buildings",
            service_url="https://geodata.sarpy.gov/arcgis/rest/services/Cadastral/LandRecordsDynamic/MapServer",
            layer_id=42,
            name="Sarpy County building footprints",
            jurisdiction=sarpy,
            jurisdiction_level="county",
            notes="Public Sarpy County building footprint layer. Empty responses are reported as missing candidates, not inferred buildings.",
        ),
        build_arcgis_provider_record(
            source_type="roads_row",
            service_url="https://geodata.sarpy.gov/arcgis/rest/services/Cadastral/LandRecordsDynamic/MapServer",
            layer_id=3,
            name="Sarpy County road centerlines",
            jurisdiction=sarpy,
            jurisdiction_level="county",
            notes="Road centerlines only; not a right-of-way survey or construction control source.",
        ),
        build_arcgis_provider_record(
            source_type="utilities",
            service_url="https://geodata.sarpy.gov/arcgis/rest/services/PublicWorks/SanitarySewerNetwork/MapServer",
            layer_id=10,
            name="Sarpy County sanitary gravity mains",
            jurisdiction=sarpy,
            jurisdiction_level="utility",
            notes="Partial public sanitary layer only; does not replace utility-owner records, one-call locates, or field verification.",
        ),
        build_arcgis_provider_record(
            source_type="utilities",
            service_url="https://geodata.sarpy.gov/arcgis/rest/services/PublicWorks/StormwaterNetwork/MapServer",
            layer_id=7,
            name="Sarpy County stormwater gravity mains",
            jurisdiction=sarpy,
            jurisdiction_level="utility",
            notes="Public stormwater gravity-main context only; does not replace survey, CCTV/as-built records, utility-owner clearance, or field verification.",
        ),
        build_arcgis_provider_record(
            source_type="utilities",
            service_url="https://geodata.sarpy.gov/arcgis/rest/services/PublicWorks/StormwaterNetwork/MapServer",
            layer_id=3,
            name="Sarpy County stormwater inlets",
            jurisdiction=sarpy,
            jurisdiction_level="utility",
            notes="Public storm inlet context only; inlet locations and rim/invert data require source review and field/survey confirmation.",
        ),
        build_arcgis_provider_record(
            source_type="utilities",
            service_url="https://geodata.sarpy.gov/arcgis/rest/services/PublicWorks/StormwaterNetwork/MapServer",
            layer_id=4,
            name="Sarpy County stormwater discharge points",
            jurisdiction=sarpy,
            jurisdiction_level="utility",
            notes="Public storm discharge-point context only; outfall availability and tailwater assumptions require review.",
        ),
        build_arcgis_provider_record(
            source_type="utilities",
            service_url="https://geodata.sarpy.gov/arcgis/rest/services/Cadastral/LandRecordsDynamic/MapServer",
            layer_id=46,
            name="Sarpy County waterlines",
            jurisdiction=sarpy,
            jurisdiction_level="utility",
            notes="Public waterline context only; does not replace utility-owner records, hydrant flow testing, locates, or material/pressure confirmation.",
        ),
        ]
        gaps = [
            {
                "source_type": "contours",
                "label": "contours",
                "status": "known_source_not_query_configured",
                "message": (
                    "Sarpy/Omaha metro contours were found as a VectorTileServer, not a queryable ArcGIS FeatureServer/MapServer layer. "
                    "Configure a queryable contour service URL/API or import contours before reporting contour candidates."
                ),
                "source_url": "https://tiles.arcgis.com/tiles/OiG7dbwhQEWoy77N/arcgis/rest/services/Contours_Metro/VectorTileServer",
            },
            {
                "source_type": "elevation",
                "label": "terrain surface / LiDAR",
                "status": "known_source_needs_raster_import",
                "message": (
                    "Nebraska/Sarpy LiDAR and DEM sources are known, but Civora currently uses USGS point elevation for online context. "
                    "Import DEM/LiDAR/contours or configure a raster/tile elevation pipeline before treating terrain as a surface."
                ),
                "source_url": "https://gis.ne.gov/portal/home/item.html?id=4aeda92955de4a388588f523e4fe1f28",
            }
        ]
        packs.append(_pack_record("gretna_ne_sarpy_county", "Gretna/Sarpy County, NE provider pack", sarpy, providers, gaps))
    address_in_douglas = _address_mentions(text, "omaha", "douglas county") and (" ne" in text or "nebraska" in text)
    if _point_in_bbox(lat, lng, DOUGLAS_COUNTY_BBOX) or address_in_douglas:
        douglas = {
            "level": "county",
            "city": "Omaha",
            "county": "Douglas County",
            "state": "NE",
            "target_market": "omaha_douglas_ne",
        }
        providers = [
            build_arcgis_provider_record(
                source_type="parcels",
                service_url="https://dcgis.org/server/rest/services/vector/Parcels_public/FeatureServer",
                layer_id=0,
                name="Douglas County public parcels",
                jurisdiction=douglas,
                jurisdiction_level="county",
                notes="Douglas County public parcel polygons; candidate context only, not a boundary survey.",
            ),
            build_arcgis_provider_record(
                source_type="buildings",
                service_url="https://dcgis.org/server/rest/services/Hosted/2022_Building_Footprints/FeatureServer",
                layer_id=0,
                name="Douglas County 2022 building footprints",
                jurisdiction=douglas,
                jurisdiction_level="county",
                notes="County building-footprint context; verify current conditions and source vintage before use.",
            ),
            build_arcgis_provider_record(
                source_type="roads_row",
                service_url="https://dcgis.org/server/rest/services/vector/Street_Centerlines/FeatureServer",
                layer_id=0,
                name="Douglas County street centerlines",
                jurisdiction=douglas,
                jurisdiction_level="county",
                notes="Street centerline context only; not right-of-way or survey control.",
            ),
            build_arcgis_provider_record(
                source_type="utilities",
                service_url="https://dcgis.org/server/rest/services/Sewer/Sewer_Network_Public/FeatureServer",
                layer_id=1,
                name="Douglas County public sewer lines",
                jurisdiction=douglas,
                jurisdiction_level="utility",
                notes="Public sewer network context only; verify owner records, locates, inverts, and field conditions.",
            ),
            build_arcgis_provider_record(
                source_type="utilities",
                service_url="https://dcgis.org/server/rest/services/Sewer/Sewer_Network_Public/FeatureServer",
                layer_id=0,
                name="Douglas County public sewer nodes",
                jurisdiction=douglas,
                jurisdiction_level="utility",
                notes="Public sewer node context only; rims, inverts, and connectivity require source and field review.",
            ),
            build_arcgis_provider_record(
                source_type="utilities",
                service_url="https://dcgis.org/server/rest/services/Hosted/Waterlines_%28source%29_view/FeatureServer",
                layer_id=0,
                name="Douglas County public waterlines",
                jurisdiction=douglas,
                jurisdiction_level="utility",
                notes="Public waterline context only; verify utility-owner records, material, pressure, and locates.",
            ),
            build_arcgis_provider_record(
                source_type="wetlands",
                service_url="https://dcgis.org/server/rest/services/Hosted/Wetlands/FeatureServer",
                layer_id=0,
                name="Douglas County wetlands",
                jurisdiction=douglas,
                jurisdiction_level="county",
                notes="County wetlands context; delineation and agency confirmation remain separate requirements.",
            ),
            build_arcgis_provider_record(
                source_type="zoning",
                service_url="https://dcgis.org/server/rest/services/Hosted/Douglas_County_Zoning_view/FeatureServer",
                layer_id=0,
                name="Douglas County zoning",
                jurisdiction=douglas,
                jurisdiction_level="county",
                notes="Zoning context requires current jurisdiction review and does not establish entitlement.",
            ),
            build_arcgis_provider_record(
                source_type="terrain_breaklines",
                service_url="https://dcgis.org/server/rest/services/Hosted/Breaklines/FeatureServer",
                layer_id=0,
                name="Douglas County 2022 terrain breaklines",
                jurisdiction=douglas,
                jurisdiction_level="county",
                notes="Terrain breakline context only; not a survey surface, datum, or grading control source.",
            ),
            build_arcgis_provider_record(
                source_type="lidar_index",
                service_url="https://dcgis.org/server/rest/services/Hosted/Douglas_County_NE_LiDAR_Tiles_view/FeatureServer",
                layer_id=4,
                name="Douglas County 2022 LiDAR tile index",
                jurisdiction=douglas,
                jurisdiction_level="county",
                notes="LiDAR coverage index only; it does not import point-cloud elevations or create a terrain surface.",
            ),
            build_known_provider_record(
                source_type="contours",
                service_url="https://dcgis.org/server/rest/services/Hosted/2022_Contours/VectorTileServer",
                name="Douglas County 2022 contour vector tiles",
                jurisdiction=douglas,
                jurisdiction_level="county",
                provider_kind="vector_tile",
                notes="Official contour tiles are known, but the VectorTileServer is not queryable for candidate geometry.",
            ),
        ]
        gaps = [
            _gap(
                "contours",
                "contours",
                "Douglas County contours are published as official vector tiles, not a queryable FeatureServer/MapServer layer for candidate extraction.",
                status="known_source_not_queryable",
                source_url="https://dcgis.org/server/rest/services/Hosted/2022_Contours/VectorTileServer",
            ),
            _gap(
                "easements",
                "easements",
                "No verified queryable Douglas County easement layer is configured; title records and recorded documents remain required.",
            ),
            _gap(
                "utilities",
                "complete utility inventory",
                "The pack includes public sewer and water context only; electric, gas, telecom, owner records, and field locates remain separate inputs.",
                status="partial_provider_coverage",
            ),
        ]
        packs.append(_pack_record("omaha_douglas_ne", "Omaha/Douglas County, NE provider pack", douglas, providers, gaps))
    address_in_austin = "austin" in text and (" tx" in text or "texas" in text)
    if _point_in_bbox(lat, lng, AUSTIN_BBOX) or address_in_austin:
        austin = {"level": "city", "city": "Austin", "county": "Travis County", "state": "TX", "target_market": "austin_tx"}
        providers = [
            build_arcgis_provider_record(source_type="parcels", service_url="https://maps.austintexas.gov/gis/rest/Shared/AppraisalDistricts/MapServer", layer_id=0, name="City of Austin TCAD parcels", jurisdiction=austin, jurisdiction_level="county", notes="Austin Property Profile Appraisal Districts layer; candidate parcel context only."),
            build_arcgis_provider_record(source_type="buildings", service_url="https://maps.austintexas.gov/gis/rest/Shared/PlanimetricsSurvey_1/MapServer", layer_id=0, name="City of Austin building footprints 2023", jurisdiction=austin, jurisdiction_level="city", notes="Austin planimetrics building footprints; candidate context only."),
            build_arcgis_provider_record(source_type="roads_row", service_url="https://maps.austintexas.gov/gis/rest/Shared/Property/MapServer", layer_id=1, name="City of Austin streets", jurisdiction=austin, jurisdiction_level="city", notes="Street centerline/context layer; not ROW survey."),
            build_arcgis_provider_record(source_type="utilities", service_url="https://maps.austintexas.gov/gis/rest/PropertyProfile/AustinWater/MapServer", layer_id=3, name="Austin Water service area", jurisdiction=austin, jurisdiction_level="utility", notes="Utility service area context only; not utility as-built, locate, or owner clearance."),
            build_arcgis_provider_record(source_type="floodplain", service_url="https://maps.austintexas.gov/gis/rest/Shared/Environmental_2/MapServer", layer_id=1, name="City of Austin FEMA floodplain", jurisdiction=austin, jurisdiction_level="city", notes="Local floodplain context; FEMA NFHL remains available as national fallback."),
            build_arcgis_provider_record(source_type="contours", service_url="https://maps.austintexas.gov/gis/rest/Shared/PlanimetricsSurvey_2/MapServer", layer_id=0, name="City of Austin contours 2021", jurisdiction=austin, jurisdiction_level="city", notes="Public contour context only; not topographic survey/control."),
            build_arcgis_provider_record(source_type="zoning", service_url="https://maps.austintexas.gov/gis/rest/Shared/Zoning_1/MapServer", layer_id=0, name="City of Austin zoning", jurisdiction=austin, jurisdiction_level="city", notes="Zoning context requires jurisdiction review."),
        ]
        gaps = [
            {"source_type": "wetlands", "label": "local wetlands", "status": "local_provider_unknown", "message": "No verified queryable local Austin wetlands provider is configured; use USFWS NWI as national candidate fallback where available."},
        ]
        packs.append(_pack_record("austin_tx_city", "Austin, TX provider pack", austin, providers, gaps))
    address_in_atlanta = ("atlanta" in text or "fulton" in text) and (" ga" in text or "georgia" in text)
    if _point_in_bbox(lat, lng, FULTON_COUNTY_BBOX) or address_in_atlanta:
        fulton = {"level": "county", "city": "Atlanta", "county": "Fulton County", "state": "GA", "target_market": "atlanta_fulton_ga"}
        providers = [
            build_arcgis_provider_record(source_type="parcels", service_url="https://gismaps.fultoncountyga.gov/arcgispub2/rest/services/PropertyMapViewer/PropertyMapViewer/MapServer", layer_id=11, name="Fulton County tax parcels", jurisdiction=fulton, jurisdiction_level="county", notes="Fulton County Property Map Viewer tax parcel layer; candidate context only."),
            build_arcgis_provider_record(source_type="contours", service_url="https://gismaps.fultoncountyga.gov/arcgispub2/rest/services/PropertyMapViewer/PropertyMapViewer/MapServer", layer_id=25, name="Fulton County elevation contours", jurisdiction=fulton, jurisdiction_level="county", notes="Fulton County contour context only; not topographic survey/control."),
            build_arcgis_provider_record(source_type="zoning", service_url="https://gismaps.fultoncountyga.gov/arcgispub2/rest/services/PropertyMapViewer/PropertyMapViewer/MapServer", layer_id=34, name="Fulton County zoning", jurisdiction=fulton, jurisdiction_level="county", notes="Zoning context requires jurisdiction review."),
        ]
        gaps = [
            {"source_type": "buildings", "label": "building footprints", "status": "local_provider_unknown", "message": "Fulton/Atlanta building footprint open-data references were found, but no verified queryable local provider is configured for candidate extraction."},
            {"source_type": "roads_row", "label": "roads/right-of-way", "status": "local_provider_unknown", "message": "No verified queryable Fulton/Atlanta road/ROW provider is configured."},
            {"source_type": "utilities", "label": "existing utilities", "status": "local_provider_unknown", "message": "No verified queryable Fulton/Atlanta utility owner/jurisdiction provider is configured."},
            {"source_type": "wetlands", "label": "local wetlands", "status": "local_provider_unknown", "message": "No verified queryable local wetlands provider is configured; use USFWS NWI as national candidate fallback where available."},
        ]
        packs.append(_pack_record("atlanta_fulton_ga", "Atlanta/Fulton County, GA provider pack", fulton, providers, gaps))
    address_in_dallas = _address_mentions(text, "dallas") and (" tx" in text or "texas" in text)
    if _point_in_bbox(lat, lng, DALLAS_BBOX) or address_in_dallas:
        dallas = {"level": "city", "city": "Dallas", "county": "Dallas County", "state": "TX", "target_market": "dallas_tx"}
        providers = [
            build_arcgis_provider_record(source_type="parcels", service_url="https://gis.dallascityhall.com/arcgis/rest/services/Basemap/DallasTaxParcels/FeatureServer", layer_id=0, name="City of Dallas tax parcels", jurisdiction=dallas, jurisdiction_level="city", notes="City of Dallas Basemap DallasTaxParcels FeatureServer layer 0; candidate parcel context only."),
            build_arcgis_provider_record(source_type="roads_row", service_url="https://gis.dallascityhall.com/arcgis/rest/services/Pbw_public/ROWMSReferenceLayers/MapServer", layer_id=0, name="City of Dallas ROW centerline", jurisdiction=dallas, jurisdiction_level="city", notes="Dallas ROWMS reference ROW Centerline layer; context only, not ROW survey/control."),
            build_arcgis_provider_record(source_type="roads_row", service_url="https://gis.dallascityhall.com/arcgis/rest/services/Basemap/DallasAreaRoads/MapServer", layer_id=2, name="City of Dallas area roads", jurisdiction=dallas, jurisdiction_level="city", notes="DallasAreaRoads streets layer; road context only."),
        ]
        gaps = [
            _gap("buildings", "building footprints", "No verified queryable City of Dallas/Dallas County building-footprint provider is configured for candidate extraction."),
            _gap("utilities", "existing utilities", "No verified queryable Dallas utility owner/jurisdiction provider is configured; require utility-owner records and locates before reliance."),
            _gap("contours", "contours", "No verified queryable Dallas contour/elevation line provider is configured; use USGS 3DEP point elevation as national candidate fallback where available."),
            _gap("wetlands", "local wetlands", "No verified queryable local Dallas wetlands provider is configured; use USFWS NWI as national candidate fallback where available."),
        ]
        packs.append(_pack_record("dallas_tx_city", "Dallas, TX provider pack", dallas, providers, gaps))
    address_in_harris = _address_mentions(text, "houston", "harris county") and (" tx" in text or "texas" in text)
    if _point_in_bbox(lat, lng, HARRIS_COUNTY_BBOX) or address_in_harris:
        harris = {"level": "county", "city": "Houston", "county": "Harris County", "state": "TX", "target_market": "houston_harris_tx"}
        providers = [
            build_arcgis_provider_record(source_type="parcels", service_url="https://www.gis.hctx.net/arcgis/rest/services/HCAD/Parcels/MapServer", layer_id=0, name="Harris County HCAD parcels", jurisdiction=harris, jurisdiction_level="county", notes="Harris County HCAD Parcels MapServer layer 0; candidate parcel context only."),
            build_arcgis_provider_record(source_type="roads_row", service_url="https://www.gis.hctx.net/arcgis/rest/services/ITC/CTS_roads/MapServer", layer_id=0, name="Harris County roads", jurisdiction=harris, jurisdiction_level="county", notes="Harris County CTS roads layer; road context only, not ROW survey/control."),
        ]
        gaps = [
            _gap("buildings", "building footprints", "No verified queryable Houston/Harris building-footprint provider is configured for candidate extraction."),
            _gap("utilities", "existing utilities", "No verified queryable Houston/Harris utility owner/jurisdiction provider is configured; require utility-owner records and locates before reliance."),
            _gap("contours", "contours", "No verified queryable Houston/Harris contour provider is configured; use USGS 3DEP point elevation as national candidate fallback where available."),
            _gap("wetlands", "local wetlands", "No verified queryable local Houston/Harris wetlands provider is configured; use USFWS NWI as national candidate fallback where available."),
        ]
        packs.append(_pack_record("houston_harris_tx", "Houston/Harris County, TX provider pack", harris, providers, gaps))
    address_in_denver = _address_mentions(text, "denver") and (" co" in text or "colorado" in text)
    if _point_in_bbox(lat, lng, DENVER_COUNTY_BBOX) or address_in_denver:
        denver = {"level": "city_county", "city": "Denver", "county": "Denver County", "state": "CO", "target_market": "denver_co"}
        providers = [
            build_arcgis_provider_record(source_type="parcels", service_url="https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/ArcGIS/rest/services/ODC_PROP_PARCELS_A/FeatureServer", layer_id=245, name="Denver open data parcels", jurisdiction=denver, jurisdiction_level="city", notes="Denver Open Data Catalog hosted FeatureServer PROP_PARCELS_A layer; candidate parcel context only."),
            build_arcgis_provider_record(source_type="buildings", service_url="https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/ArcGIS/rest/services/ODC_PROP_BUILDINGOUTLINES_A/FeatureServer", layer_id=111, name="Denver building outlines", jurisdiction=denver, jurisdiction_level="city", notes="Denver Open Data building outlines layer; candidate context only."),
            build_arcgis_provider_record(source_type="roads_row", service_url="https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/ArcGIS/rest/services/ODC_TRANS_STREET_L/FeatureServer", layer_id=145, name="Denver streets", jurisdiction=denver, jurisdiction_level="city", notes="Denver street centerline/context layer; not ROW survey/control."),
            build_arcgis_provider_record(source_type="floodplain", service_url="https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/ArcGIS/rest/services/ODC_PLAN_FEMAFLOODPLAIN_A/FeatureServer", layer_id=389, name="Denver FEMA floodplain", jurisdiction=denver, jurisdiction_level="city", notes="Denver-hosted FEMA floodplain context; FEMA NFHL remains national fallback."),
            build_arcgis_provider_record(source_type="zoning", service_url="https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/ArcGIS/rest/services/ODC_ZONE_ZONING_A/FeatureServer", layer_id=209, name="Denver zoning", jurisdiction=denver, jurisdiction_level="city", notes="Zoning context requires jurisdiction review."),
        ]
        gaps = [
            _gap("utilities", "existing utilities", "No verified queryable Denver utility owner/jurisdiction provider is configured; require utility-owner records and locates before reliance."),
            _gap("contours", "contours", "No verified queryable Denver ground-surface contour provider is configured in this pack; use USGS 3DEP point elevation as national candidate fallback where available."),
            _gap("wetlands", "local wetlands", "No verified queryable local Denver wetlands provider is configured; use USFWS NWI as national candidate fallback where available."),
        ]
        packs.append(_pack_record("denver_co_city_county", "Denver/Denver County, CO provider pack", denver, providers, gaps))
    address_in_maricopa = _address_mentions(text, "phoenix", "maricopa") and (" az" in text or "arizona" in text)
    if _point_in_bbox(lat, lng, MARICOPA_COUNTY_BBOX) or address_in_maricopa:
        maricopa = {"level": "county", "city": "Phoenix", "county": "Maricopa County", "state": "AZ", "target_market": "phoenix_maricopa_az"}
        providers = [
            build_arcgis_provider_record(source_type="parcels", service_url="https://gis.mcassessor.maricopa.gov/arcgis/rest/services/Parcels/MapServer", layer_id=0, name="Maricopa County assessor parcels", jurisdiction=maricopa, jurisdiction_level="county", notes="Maricopa County Assessor Parcels MapServer layer 0; candidate parcel context only."),
            build_arcgis_provider_record(source_type="roads_row", service_url="https://gis.mcassessor.maricopa.gov/arcgis/rest/services/Streets/MapServer", layer_id=0, name="Maricopa County assessor streets", jurisdiction=maricopa, jurisdiction_level="county", notes="Maricopa County Assessor Streets MapServer layer; road context only."),
            build_arcgis_provider_record(source_type="floodplain", service_url="https://gis.mcassessor.maricopa.gov/arcgis/rest/services/Flood/MapServer", layer_id=0, name="Maricopa County assessor flood", jurisdiction=maricopa, jurisdiction_level="county", notes="Maricopa County Assessor Flood MapServer layer; flood context only, FEMA NFHL remains national fallback."),
        ]
        gaps = [
            _gap("buildings", "building footprints", "No verified queryable Phoenix/Maricopa building-footprint provider is configured for candidate extraction."),
            _gap("utilities", "existing utilities", "No verified queryable Phoenix/Maricopa utility owner/jurisdiction provider is configured; require utility-owner records and locates before reliance."),
            _gap("contours", "contours", "No verified queryable Phoenix/Maricopa contour provider is configured; use USGS 3DEP point elevation as national candidate fallback where available."),
            _gap("wetlands", "local wetlands", "No verified queryable local Phoenix/Maricopa wetlands provider is configured; use USFWS NWI as national candidate fallback where available."),
        ]
        packs.append(_pack_record("phoenix_maricopa_az", "Phoenix/Maricopa County, AZ provider pack", maricopa, providers, gaps))
    address_in_mecklenburg = _address_mentions(text, "charlotte", "mecklenburg") and (" nc" in text or "north carolina" in text)
    if _point_in_bbox(lat, lng, MECKLENBURG_COUNTY_BBOX) or address_in_mecklenburg:
        mecklenburg = {"level": "county", "city": "Charlotte", "county": "Mecklenburg County", "state": "NC", "target_market": "charlotte_mecklenburg_nc"}
        providers = [
            build_arcgis_provider_record(source_type="parcels", service_url="https://meckgis.mecklenburgcountync.gov/server/rest/services/TaxParcelBoundaries/FeatureServer", layer_id=0, name="Mecklenburg County tax parcel boundaries", jurisdiction=mecklenburg, jurisdiction_level="county", notes="Mecklenburg County Tax Parcel Boundaries FeatureServer layer 0; candidate parcel context only."),
            build_arcgis_provider_record(source_type="buildings", service_url="https://meckgis.mecklenburgcountync.gov/server/rest/services/BuildingFootprints/FeatureServer", layer_id=0, name="Mecklenburg County building footprints", jurisdiction=mecklenburg, jurisdiction_level="county", notes="Mecklenburg County Building Footprints FeatureServer layer 0; candidate context only."),
        ]
        gaps = [
            _gap("roads_row", "roads/right-of-way", "No verified queryable Charlotte/Mecklenburg road/ROW provider is configured in this pack."),
            _gap("utilities", "existing utilities", "No verified queryable Charlotte/Mecklenburg utility owner/jurisdiction provider is configured; require utility-owner records and locates before reliance."),
            _gap("contours", "contours", "No verified queryable Charlotte/Mecklenburg contour provider is configured; use USGS 3DEP point elevation as national candidate fallback where available."),
            _gap("wetlands", "local wetlands", "No verified queryable local Charlotte/Mecklenburg wetlands provider is configured; use USFWS NWI as national candidate fallback where available."),
        ]
        packs.append(_pack_record("charlotte_mecklenburg_nc", "Charlotte/Mecklenburg County, NC provider pack", mecklenburg, providers, gaps))
    return packs


def target_market_provider_records(*, address: str = "", lat: Any = None, lng: Any = None) -> List[Dict[str, Any]]:
    providers: List[Dict[str, Any]] = []
    for pack in provider_packs_for_location(address=address, lat=lat, lng=lng):
        providers.extend(safe_list(safe_dict(pack).get("providers")))
    return providers


def target_market_known_gaps(*, address: str = "", lat: Any = None, lng: Any = None) -> List[Dict[str, Any]]:
    gaps: List[Dict[str, Any]] = []
    for pack in provider_packs_for_location(address=address, lat=lat, lng=lng):
        gaps.extend(safe_list(safe_dict(pack).get("known_gaps")))
    return gaps


def env_provider_records(env: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    data = dict(os.environ if env is None else env)
    specs = [
        ("parcels", "CIVORA_PARCEL_ARCGIS_SERVICE_URL", "CIVORA_PARCEL_ARCGIS_LAYER_ID", "county", "Configured parcel ArcGIS provider"),
        ("buildings", "CIVORA_BUILDING_FOOTPRINTS_ARCGIS_SERVICE_URL", "CIVORA_BUILDING_FOOTPRINTS_ARCGIS_LAYER_ID", "city", "Configured building footprint ArcGIS provider"),
        ("roads_row", "CIVORA_ROADS_ROW_ARCGIS_SERVICE_URL", "CIVORA_ROADS_ROW_ARCGIS_LAYER_ID", "jurisdiction", "Configured road/ROW ArcGIS provider"),
        ("utilities", "CIVORA_EXISTING_UTILITIES_ARCGIS_SERVICE_URL", "CIVORA_EXISTING_UTILITIES_ARCGIS_LAYER_ID", "utility", "Configured existing utility ArcGIS provider"),
        ("contours", "CIVORA_CONTOURS_ARCGIS_SERVICE_URL", "CIVORA_CONTOURS_ARCGIS_LAYER_ID", "county", "Configured contour ArcGIS provider"),
    ]
    records: List[Dict[str, Any]] = []
    jurisdiction = {
        "state": safe_str(data.get("CIVORA_GIS_STATE")),
        "county": safe_str(data.get("CIVORA_GIS_COUNTY")),
        "city": safe_str(data.get("CIVORA_GIS_CITY")),
    }
    for source_type, url_key, layer_key, level, default_name in specs:
        url = safe_str(data.get(url_key))
        if not url:
            continue
        records.append(
            build_arcgis_provider_record(
                source_type=source_type,
                service_url=url,
                layer_id=safe_int(data.get(layer_key), 0),
                name=safe_str(data.get(f"{url_key}_NAME")) or default_name,
                jurisdiction=jurisdiction,
                jurisdiction_level=level,
                freshness_date=safe_str(data.get(f"{url_key}_FRESHNESS_DATE")),
            )
        )
    return records


def build_provider_registry(
    *,
    providers: Optional[List[Dict[str, Any]]] = None,
    env: Optional[Dict[str, str]] = None,
    include_builtin: bool = True,
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    if include_builtin:
        rows.extend(builtin_provider_records())
    rows.extend(env_provider_records(env))
    rows.extend(safe_dict(item) for item in safe_list(providers) if safe_dict(item))
    normalized: List[Dict[str, Any]] = []
    seen = set()
    for item in rows:
        source_type = normalize_source_type(safe_str(item.get("source_type")))
        record = item
        if safe_str(item.get("queryable")) == "False" or item.get("queryable") is False or safe_str(item.get("provider_kind")) in {"known_nonqueryable", "vector_tile"}:
            record = deepcopy(item)
        elif safe_str(item.get("provider_kind")) == "arcgis_rest" or safe_str(safe_dict(item.get("arcgis")).get("service_url") or item.get("service_url")):
            arcgis = safe_dict(item.get("arcgis"))
            record = build_arcgis_provider_record(
                source_type=source_type,
                service_url=safe_str(arcgis.get("service_url") or item.get("service_url")),
                layer_id=safe_int(arcgis.get("layer_id", item.get("layer_id")), 0),
                name=safe_str(item.get("name")),
                jurisdiction=safe_dict(item.get("jurisdiction")),
                jurisdiction_level=safe_str(item.get("jurisdiction_level")),
                provider_kind=safe_str(item.get("provider_kind"), "arcgis_rest"),
                freshness_date=safe_str(item.get("freshness_date") or safe_dict(item.get("freshness")).get("source_date")),
                stale_after_days=safe_int(item.get("stale_after_days"), DEFAULT_STALE_AFTER_DAYS),
                status=safe_str(item.get("status"), "configured"),
                fixture_only=bool(item.get("fixture_only")),
                notes=safe_str(item.get("notes")),
            )
            if item.get("health"):
                record["health"] = deepcopy(safe_dict(item.get("health")))
        key = safe_str(record.get("id")) or _provider_id(
            source_type=source_type,
            service_url=safe_str(record.get("service_url")),
            jurisdiction=safe_dict(record.get("jurisdiction")),
            layer_id=safe_int(safe_dict(record.get("arcgis")).get("layer_id"), 0),
        )
        if key in seen:
            continue
        seen.add(key)
        record["id"] = key
        normalized.append(record)
    configured = [item for item in normalized if safe_str(item.get("status")) != "unconfigured" and safe_str(item.get("service_url"))]
    queryable = [item for item in configured if item.get("queryable") is not False and safe_str(item.get("status")) != "known_not_queryable"]
    return {
        "version": GIS_PROVIDER_REGISTRY_VERSION,
        "status": "configured" if configured else "unconfigured",
        "provider_count": len(normalized),
        "configured_provider_count": len(configured),
        "queryable_provider_count": len(queryable),
        "source_types": list(GIS_SOURCE_TYPES),
        "providers": normalized,
        "truth_label": "Provider registry configures GIS context sources. No provider record is survey-backed unless separate survey/control evidence exists.",
    }


def providers_for_source_type(registry: Dict[str, Any], source_type: str) -> List[Dict[str, Any]]:
    wanted = normalize_source_type(source_type)
    return [
        safe_dict(item)
        for item in safe_list(safe_dict(registry).get("providers"))
        if normalize_source_type(safe_str(safe_dict(item).get("source_type"))) == wanted
        and safe_str(safe_dict(item).get("status")) != "unconfigured"
        and safe_str(safe_dict(item).get("status")) != "known_not_queryable"
        and safe_dict(item).get("queryable") is not False
        and safe_str(safe_dict(item).get("service_url"))
    ]


def selected_provider(registry: Dict[str, Any], source_type: str) -> Dict[str, Any]:
    providers = providers_for_source_type(registry, source_type)
    providers.sort(key=lambda item: safe_str(item.get("jurisdiction_level")) == "federal")
    return providers[0] if providers else {}


def check_provider_health(provider: Dict[str, Any], *, session: Any = requests) -> Dict[str, Any]:
    rec = safe_dict(provider)
    url = safe_str(rec.get("service_url") or safe_dict(rec.get("arcgis")).get("service_url"))
    checked_at = _utc_now_iso()
    if not url:
        return {"status": "unconfigured", "checked_at": checked_at, "ok": False, "message": "Provider service URL is not configured."}
    if rec.get("queryable") is False or safe_str(rec.get("status")) == "known_not_queryable":
        return {"status": "not_queryable", "checked_at": checked_at, "ok": False, "message": "Provider is known but not usable for candidate extraction."}
    try:
        response = session.get(url.rstrip("/"), params={"f": "json"}, timeout=10)
        response.raise_for_status()
        payload = safe_dict(response.json())
    except Exception as exc:
        return {"status": "failed", "checked_at": checked_at, "ok": False, "message": safe_str(exc)}
    if payload.get("error"):
        return {"status": "failed", "checked_at": checked_at, "ok": False, "message": safe_str(safe_dict(payload.get("error")).get("message"), "ArcGIS service returned an error.")}
    layer_id = safe_int(safe_dict(rec.get("arcgis")).get("layer_id"), 0)
    layers = safe_list(payload.get("layers"))
    layer_known = not layers or any(safe_int(safe_dict(item).get("id"), -1) == layer_id for item in layers)
    return {
        "status": "healthy" if layer_known else "layer_missing",
        "checked_at": checked_at,
        "ok": bool(layer_known),
        "message": "ArcGIS service metadata responded." if layer_known else f"ArcGIS service responded but layer {layer_id} was not listed.",
        "service_name": safe_str(payload.get("serviceDescription") or payload.get("name") or payload.get("mapName")),
    }


def check_registry_health(registry: Dict[str, Any], *, session: Any = requests) -> Dict[str, Any]:
    providers = [safe_dict(item) for item in safe_list(safe_dict(registry).get("providers")) if safe_dict(item)]
    checked: List[Dict[str, Any]] = []
    for provider in providers:
        updated = deepcopy(provider)
        updated["health"] = check_provider_health(provider, session=session)
        updated["freshness"] = provider_freshness_status(provider)
        checked.append(updated)
    healthy_count = sum(1 for item in checked if safe_dict(item.get("health")).get("ok") is True)
    return {
        "version": GIS_PROVIDER_REGISTRY_VERSION,
        "status": "healthy" if healthy_count == len(checked) and checked else "needs_attention",
        "provider_count": len(checked),
        "healthy_provider_count": healthy_count,
        "stale_provider_count": sum(1 for item in checked if safe_dict(item.get("freshness")).get("stale") is True),
        "providers": checked,
        "checked_at": _utc_now_iso(),
        "truth_label": "Health checks only verify provider reachability/configuration; they do not validate source correctness.",
    }


__all__ = [
    "GIS_PROVIDER_REGISTRY_VERSION",
    "GIS_SOURCE_TYPES",
    "build_arcgis_provider_record",
    "build_known_provider_record",
    "build_provider_registry",
    "check_provider_health",
    "check_registry_health",
    "provider_freshness_status",
    "provider_packs_for_location",
    "providers_for_source_type",
    "selected_provider",
    "target_market_known_gaps",
    "target_market_provider_records",
]
