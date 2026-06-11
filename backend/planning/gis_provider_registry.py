from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from .common import safe_dict, safe_int, safe_list, safe_str


GIS_PROVIDER_REGISTRY_VERSION = "local_gis_provider_registry_v1"
GIS_SOURCE_TYPES = ("parcels", "buildings", "roads_row", "utilities", "contours", "floodplain", "wetlands")
JURISDICTION_LEVELS = ("jurisdiction", "county", "city", "state", "federal", "utility")
DEFAULT_STALE_AFTER_DAYS = 90


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
        "arcgis": {
            "service_url": url,
            "service_kind": _arcgis_service_kind(url),
            "layer_id": layer,
            "query_url": f"{url.rstrip('/')}/{layer}/query" if url else "",
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
        build_arcgis_provider_record(
            source_type="floodplain",
            service_url="https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer",
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
        if safe_str(item.get("provider_kind")) == "arcgis_rest" or safe_str(safe_dict(item.get("arcgis")).get("service_url") or item.get("service_url")):
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
    return {
        "version": GIS_PROVIDER_REGISTRY_VERSION,
        "status": "configured" if configured else "unconfigured",
        "provider_count": len(normalized),
        "configured_provider_count": len(configured),
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
        and safe_str(safe_dict(item).get("service_url"))
    ]


def selected_provider(registry: Dict[str, Any], source_type: str) -> Dict[str, Any]:
    providers = providers_for_source_type(registry, source_type)
    return providers[0] if providers else {}


def check_provider_health(provider: Dict[str, Any], *, session: Any = requests) -> Dict[str, Any]:
    rec = safe_dict(provider)
    url = safe_str(rec.get("service_url") or safe_dict(rec.get("arcgis")).get("service_url"))
    checked_at = _utc_now_iso()
    if not url:
        return {"status": "unconfigured", "checked_at": checked_at, "ok": False, "message": "Provider service URL is not configured."}
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
    "build_provider_registry",
    "check_provider_health",
    "check_registry_health",
    "provider_freshness_status",
    "providers_for_source_type",
    "selected_provider",
]
