from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urljoin

import requests


REGISTRY_VERSION = "local_gis_provider_registry_v1"
SOURCE_TYPE_ALIASES = {
    "parcel": "parcels",
    "parcels": "parcels",
    "building": "buildings",
    "buildings": "buildings",
    "building_footprints": "buildings",
    "road": "roads_row",
    "roads": "roads_row",
    "row": "roads_row",
    "roads_row": "roads_row",
    "utility": "utilities",
    "utilities": "utilities",
    "contour": "contours",
    "contours": "contours",
    "flood": "floodplain",
    "floodplain": "floodplain",
    "wetland": "wetlands",
    "wetlands": "wetlands",
}
DEFAULT_SOURCE_TYPES = ("parcels", "buildings", "roads_row", "utilities", "contours")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_str(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def normalize_source_type(value: Any) -> str:
    normalized = safe_str(value).lower().replace("-", "_").replace(" ", "_")
    return SOURCE_TYPE_ALIASES.get(normalized, normalized or "parcels")


def _arcgis_query_url(service_url: str, layer_id: int) -> str:
    base = service_url.rstrip("/") + "/"
    return urljoin(base, f"{int(layer_id)}/query")


def build_arcgis_provider_record(
    *,
    source_type: str,
    service_url: str,
    layer_id: int = 0,
    name: str = "",
    jurisdiction_level: str = "",
    notes: str = "",
) -> Dict[str, Any]:
    normalized_source_type = normalize_source_type(source_type)
    clean_url = safe_str(service_url)
    service_kind = "FeatureServer" if "featureserver" in clean_url.lower() else "MapServer"
    provider_id = f"{normalized_source_type}_{abs(hash((clean_url, int(layer_id)))) % 10_000_000}"
    return {
        "id": provider_id,
        "name": safe_str(name, f"Configured {normalized_source_type.replace('_', '/')} provider"),
        "source_type": normalized_source_type,
        "jurisdiction_level": safe_str(jurisdiction_level, "jurisdiction"),
        "provider_kind": "arcgis_rest",
        "service_url": clean_url,
        "arcgis": {
            "service_url": clean_url,
            "service_kind": service_kind,
            "layer_id": int(layer_id),
            "query_url": _arcgis_query_url(clean_url, int(layer_id)) if clean_url else "",
        },
        "status": "configured" if clean_url else "unconfigured",
        "health": {"status": "unchecked", "checked_at": "", "message": "Health check has not run."},
        "freshness": {"status": "unknown", "message": "Freshness is not verified by configuration alone."},
        "review_required": True,
        "survey_backed": False,
        "notes": safe_str(notes),
        "truth_label": "GIS provider records configure context sources only; they are not survey/control evidence.",
    }


def _provider_from_input(value: Dict[str, Any]) -> Dict[str, Any]:
    provider = deepcopy(safe_dict(value))
    arcgis = safe_dict(provider.get("arcgis"))
    service_url = safe_str(provider.get("service_url") or arcgis.get("service_url"))
    source_type = normalize_source_type(provider.get("source_type"))
    try:
        layer_id = int(arcgis.get("layer_id", provider.get("layer_id", 0)) or 0)
    except Exception:
        layer_id = 0
    if not provider:
        provider = build_arcgis_provider_record(source_type=source_type, service_url=service_url, layer_id=layer_id)
    provider["source_type"] = source_type
    provider["provider_kind"] = safe_str(provider.get("provider_kind"), "arcgis_rest")
    provider["service_url"] = service_url
    provider["arcgis"] = {
        **arcgis,
        "service_url": service_url,
        "service_kind": safe_str(
            arcgis.get("service_kind"),
            "FeatureServer" if "featureserver" in service_url.lower() else "MapServer",
        ),
        "layer_id": layer_id,
        "query_url": safe_str(arcgis.get("query_url")) or (_arcgis_query_url(service_url, layer_id) if service_url else ""),
    }
    provider["id"] = safe_str(provider.get("id")) or f"{source_type}_{abs(hash((service_url, layer_id))) % 10_000_000}"
    provider["name"] = safe_str(provider.get("name"), f"Configured {source_type.replace('_', '/')} provider")
    provider["jurisdiction_level"] = safe_str(provider.get("jurisdiction_level"), "jurisdiction")
    provider["status"] = "configured" if service_url else "unconfigured"
    provider["health"] = safe_dict(provider.get("health")) or {"status": "unchecked", "checked_at": "", "message": "Health check has not run."}
    provider["freshness"] = safe_dict(provider.get("freshness")) or {"status": "unknown", "message": "Freshness is not verified by configuration alone."}
    provider["review_required"] = True
    provider["survey_backed"] = False
    provider["truth_label"] = "GIS provider records configure context sources only; they are not survey/control evidence."
    return provider


def build_provider_registry(
    *,
    providers: Optional[Iterable[Dict[str, Any]]] = None,
    jurisdiction: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized = [_provider_from_input(item) for item in (providers or []) if safe_dict(item)]
    configured = [item for item in normalized if safe_str(item.get("service_url")) and item.get("status") != "unconfigured"]
    source_types = sorted({safe_str(item.get("source_type")) for item in normalized if safe_str(item.get("source_type"))})
    missing_source_types = [item for item in DEFAULT_SOURCE_TYPES if item not in source_types]
    return {
        "version": REGISTRY_VERSION,
        "status": "configured" if configured else "needs_configuration",
        "provider_count": len(normalized),
        "configured_provider_count": len(configured),
        "source_types": source_types,
        "missing_source_types": missing_source_types,
        "jurisdiction": safe_dict(jurisdiction),
        "providers": normalized,
        "review_required": True,
        "survey_backed": False,
        "truth_label": "GIS provider records configure context sources only; they are not survey/control evidence.",
    }


def check_provider_health(provider: Dict[str, Any], *, session: Any = requests) -> Dict[str, Any]:
    record = _provider_from_input(provider)
    service_url = safe_str(record.get("service_url"))
    layer_id = int(safe_dict(record.get("arcgis")).get("layer_id") or 0)
    checked_at = _now_iso()
    if not service_url:
        return {
            "ok": False,
            "status": "unconfigured",
            "checked_at": checked_at,
            "message": "No ArcGIS REST service URL is configured.",
            "review_required": True,
        }
    metadata_url = service_url.rstrip("/") + f"/{layer_id}"
    try:
        response = session.get(metadata_url, params={"f": "json"}, timeout=8)
        status_code = int(getattr(response, "status_code", 0) or 0)
        payload = response.json() if hasattr(response, "json") else {}
        layer_known = 200 <= status_code < 300 and not safe_dict(payload).get("error")
    except Exception as exc:
        return {
            "ok": False,
            "status": "unreachable",
            "checked_at": checked_at,
            "message": f"ArcGIS metadata check failed: {exc}",
            "metadata_url": metadata_url,
            "review_required": True,
        }
    return {
        "ok": bool(layer_known),
        "status": "healthy" if layer_known else "layer_missing",
        "checked_at": checked_at,
        "message": "ArcGIS layer metadata is reachable." if layer_known else "ArcGIS service responded, but the configured layer was not confirmed.",
        "metadata_url": metadata_url,
        "http_status": status_code,
        "review_required": True,
    }


def check_registry_health(registry: Dict[str, Any], *, session: Any = requests) -> Dict[str, Any]:
    current = build_provider_registry(providers=safe_dict(registry).get("providers") or [])
    checked = []
    for provider in current["providers"]:
        updated = deepcopy(provider)
        updated["health"] = check_provider_health(provider, session=session)
        checked.append(updated)
    healthy_count = sum(1 for item in checked if safe_dict(item.get("health")).get("ok") is True)
    stale_count = sum(1 for item in checked if safe_str(safe_dict(item.get("freshness")).get("status"), "unknown") in {"", "unknown", "stale"})
    return {
        **current,
        "status": "healthy" if checked and healthy_count == len(checked) else "needs_attention",
        "provider_count": len(checked),
        "healthy_provider_count": healthy_count,
        "stale_provider_count": stale_count,
        "providers": checked,
        "checked_at": _now_iso(),
        "truth_label": "Provider health is reachability/configuration evidence only; it is not survey/control evidence or construction approval.",
    }


__all__ = [
    "build_arcgis_provider_record",
    "build_provider_registry",
    "check_provider_health",
    "check_registry_health",
    "normalize_source_type",
]
