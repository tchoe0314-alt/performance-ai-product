from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

from .common import safe_dict, safe_float, safe_int, safe_list, safe_str


REQUIRED_GIS_LAYERS = ("parcels", "easements", "row", "floodplain", "wetlands", "existing_utilities")


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        rec = safe_dict(value)
        if rec:
            return rec
    return {}


def _nested_lookup(mapping: Dict[str, Any], paths: Iterable[str]) -> Any:
    for path in paths:
        current: Any = mapping
        found = True
        for part in path.split("."):
            current = safe_dict(current).get(part)
            if current is None:
                found = False
                break
        if found and current not in (None, "", [], {}):
            return current
    return None


def _layer_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value.get("features") or value.get("items") or value.get("records") or value)
    return 1 if value not in (None, "", [], {}) else 0


def _survey_summary(meta: Dict[str, Any], parsed: Dict[str, Any], grading: Dict[str, Any]) -> Dict[str, Any]:
    existing_surface = safe_dict(grading.get("existing_surface"))
    survey = _first_dict(
        meta.get("survey"),
        meta.get("survey_control"),
        parsed.get("survey"),
        parsed.get("survey_control"),
        _nested_lookup(parsed, ("site_inputs.survey", "site_inputs.survey_control")),
        existing_surface.get("survey"),
    )
    points = (
        safe_list(survey.get("points"))
        or safe_list(survey.get("survey_points"))
        or safe_list(meta.get("survey_points"))
        or safe_list(parsed.get("survey_points"))
        or safe_list(_nested_lookup(parsed, ("site_inputs.survey_points",)))
    )
    point_count = max(safe_int(survey.get("point_count"), 0), len(points))
    surface_source = (
        safe_str(grading.get("source_quality"))
        or safe_str(grading.get("grading_source_quality"))
        or safe_str(existing_surface.get("source_quality"))
    )
    source = safe_str(survey.get("source") or survey.get("file") or meta.get("survey_file") or parsed.get("survey_file"))
    ready = point_count >= 3 or surface_source == "survey" or bool(source)
    return {
        "ready": ready,
        "point_count": point_count,
        "source": source or ("survey_surface" if surface_source == "survey" else "missing"),
        "surface_source": surface_source or "missing",
        "has_control": bool(survey.get("control_points") or survey.get("benchmark") or survey.get("datum")),
    }


def _dem_lidar_summary(meta: Dict[str, Any], parsed: Dict[str, Any], grading: Dict[str, Any]) -> Dict[str, Any]:
    existing_surface = safe_dict(grading.get("existing_surface"))
    dem = _first_dict(
        meta.get("dem_lidar"),
        meta.get("terrain_source"),
        parsed.get("dem_lidar"),
        parsed.get("terrain_source"),
        _nested_lookup(parsed, ("site_inputs.dem_lidar", "site_inputs.terrain_source")),
        existing_surface.get("dem_lidar"),
    )
    source_quality = (
        safe_str(grading.get("source_quality"))
        or safe_str(grading.get("grading_source_quality"))
        or safe_str(existing_surface.get("source_quality"))
    )
    source = safe_str(dem.get("source") or dem.get("file") or dem.get("provider") or source_quality)
    resolution = safe_float(dem.get("resolution_ft") or dem.get("cell_size_ft") or existing_surface.get("cell_size"), 0.0)
    ready = bool(dem) or source_quality in {"terrain", "dem", "lidar", "survey"}
    return {
        "ready": ready,
        "source": source or "missing",
        "resolution_ft": round(resolution, 3) if resolution > 0.0 else None,
        "approved_for_production": bool(dem.get("approved_for_production")) or source_quality == "survey",
    }


def _gis_summary(meta: Dict[str, Any], parsed: Dict[str, Any]) -> Dict[str, Any]:
    gis = _first_dict(
        meta.get("gis_layers"),
        meta.get("existing_conditions"),
        parsed.get("gis_layers"),
        parsed.get("existing_conditions"),
        _nested_lookup(parsed, ("site_inputs.gis_layers", "site_inputs.existing_conditions")),
    )
    layers: Dict[str, Dict[str, Any]] = {}
    for layer in REQUIRED_GIS_LAYERS:
        raw = gis.get(layer)
        layers[layer] = {
            "present": raw not in (None, "", [], {}),
            "count": _layer_count(raw),
        }
    return {
        "ready": any(item["present"] for item in layers.values()),
        "source": safe_str(gis.get("source") or gis.get("provider"), "missing"),
        "layers": layers,
        "missing_layers": [layer for layer, item in layers.items() if not item["present"]],
    }


def _coordinate_summary(meta: Dict[str, Any], parsed: Dict[str, Any]) -> Dict[str, Any]:
    coord = _first_dict(
        meta.get("coordinate_system"),
        parsed.get("coordinate_system"),
        _nested_lookup(parsed, ("site_inputs.coordinate_system", "gis_layers.coordinate_system", "existing_conditions.coordinate_system")),
    )
    epsg = safe_str(coord.get("epsg") or coord.get("epsg_code") or coord.get("srid"))
    name = safe_str(coord.get("name") or coord.get("crs") or coord.get("projection"))
    units = safe_str(coord.get("units") or parsed.get("units") or meta.get("units"), "ft")
    ready = bool(epsg or name)
    return {
        "ready": ready,
        "epsg": epsg,
        "name": name,
        "units": units,
        "source": safe_str(coord.get("source"), "missing" if not ready else "provided"),
    }


def summarize_existing_conditions(plan_or_meta: Dict[str, Any], parsed: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    meta = safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else safe_dict(plan_or_meta)
    parsed_payload = safe_dict(parsed)
    grading = safe_dict(meta.get("grading") or meta.get("grading_summary"))
    survey = _survey_summary(meta, parsed_payload, grading)
    dem_lidar = _dem_lidar_summary(meta, parsed_payload, grading)
    gis = _gis_summary(meta, parsed_payload)
    coordinate_system = _coordinate_summary(meta, parsed_payload)

    missing: List[Dict[str, str]] = []
    warnings: List[str] = []
    if not survey["ready"]:
        missing.append({"field": "survey_surface", "reason": "No survey/control surface or survey point source is attached."})
    if not gis["ready"]:
        missing.append({"field": "gis_layers", "reason": "No parcel, easement, ROW, floodplain, wetland, or existing utility layers are attached."})
    if not coordinate_system["ready"]:
        missing.append({"field": "coordinate_system", "reason": "No CRS/EPSG/projection is attached for real-world coordinates."})
    if dem_lidar["ready"] and not dem_lidar["approved_for_production"]:
        warnings.append("DEM/LiDAR or terrain source is present but not marked production-approved.")
    if survey["ready"] and not survey["has_control"]:
        warnings.append("Survey evidence exists but benchmark/control metadata is incomplete.")

    return {
        "version": "existing_conditions_v1",
        "production_ready": not missing and (survey["ready"] or dem_lidar["approved_for_production"]),
        "survey": survey,
        "dem_lidar": dem_lidar,
        "gis": gis,
        "coordinate_system": coordinate_system,
        "constraints": {
            "has_parcels": gis["layers"]["parcels"]["present"],
            "has_easements": gis["layers"]["easements"]["present"],
            "has_row": gis["layers"]["row"]["present"],
            "has_floodplain": gis["layers"]["floodplain"]["present"],
            "has_wetlands": gis["layers"]["wetlands"]["present"],
            "has_existing_utilities": gis["layers"]["existing_utilities"]["present"],
        },
        "missing_requirements": missing,
        "warnings": warnings,
        "source_snapshot": {
            "survey": deepcopy(survey),
            "gis_layer_counts": {layer: item["count"] for layer, item in gis["layers"].items()},
            "coordinate_system": deepcopy(coordinate_system),
        },
    }


__all__ = ["REQUIRED_GIS_LAYERS", "summarize_existing_conditions"]
