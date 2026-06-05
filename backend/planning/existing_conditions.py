from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

from .common import readiness_issue_explanations, safe_dict, safe_float, safe_int, safe_list, safe_str


REQUIRED_GIS_LAYERS = ("parcels", "easements", "row", "floodplain", "wetlands", "existing_utilities")
GEOGRAPHIC_EPSG_CODES = {"4326", "4269", "4258"}
ENGINEERING_UNITS = {"ft", "foot", "feet", "us-ft", "us_survey_ft", "survey_ft", "m", "meter", "meters", "metre", "metres"}
SOURCE_KEYS = ("source", "provider", "source_url", "file", "file_name", "dataset", "authority", "agency")


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


def _epsg_code(value: str) -> str:
    text = safe_str(value).upper().replace("EPSG::", "EPSG:")
    import re

    match = re.search(r"(?:EPSG[:/ ]*)?(\d{4,6})", text)
    return match.group(1) if match else ""


def _normalize_units(value: str) -> str:
    text = safe_str(value).strip().lower().replace(" ", "_")
    aliases = {
        "feet": "ft",
        "foot": "ft",
        "us_survey_foot": "us_survey_ft",
        "us_survey_feet": "us_survey_ft",
        "metres": "m",
        "metre": "m",
        "meters": "m",
        "meter": "m",
        "degree": "degrees",
    }
    return aliases.get(text, text)


def _coordinate_quality(coord: Dict[str, Any], fallback_units: str = "ft") -> Dict[str, Any]:
    rec = safe_dict(coord)
    raw = safe_str(rec.get("epsg") or rec.get("epsg_code") or rec.get("srid") or rec.get("name") or rec.get("crs") or rec.get("projection"))
    code = _epsg_code(raw)
    epsg = f"EPSG:{code}" if code else safe_str(rec.get("epsg") or rec.get("epsg_code") or rec.get("srid"))
    name = safe_str(rec.get("name") or rec.get("crs") or rec.get("projection"))
    explicit_units = _normalize_units(safe_str(rec.get("units")))
    units = explicit_units or _normalize_units(safe_str(fallback_units))
    is_geographic = code in GEOGRAPHIC_EPSG_CODES or units in {"degree", "degrees", "decimal_degrees"}
    blockers: List[Dict[str, str]] = []
    if not (epsg or name):
        blockers.append({"field": "coordinate_system", "reason": "No CRS/EPSG/projection is attached for real-world coordinates."})
    if not explicit_units:
        blockers.append({"field": "coordinate_system", "reason": "Coordinate-system units are missing."})
    elif units not in ENGINEERING_UNITS:
        blockers.append({"field": "coordinate_system", "reason": f"Coordinate-system units '{units}' are not engineering distance units."})
    if is_geographic:
        blockers.append({"field": "coordinate_system", "reason": "Latitude/longitude CRS is not production-usable for civil engineering distances; use a projected site CRS."})
    return {
        "ready": bool(epsg or name),
        "epsg": epsg,
        "name": name,
        "units": units,
        "units_provided": bool(explicit_units),
        "is_geographic": is_geographic,
        "is_projected": bool((epsg or name) and not is_geographic),
        "production_usable": not blockers,
        "blockers": blockers,
        "blocker_details": readiness_issue_explanations(blockers),
        "source": safe_str(rec.get("source"), "missing" if not (epsg or name) else "provided"),
    }


def _layer_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value.get("features") or value.get("items") or value.get("records") or value)
    return 1 if value not in (None, "", [], {}) else 0


def _source_evidence(value: Any) -> str:
    rec = safe_dict(value)
    for key in SOURCE_KEYS:
        source = safe_str(rec.get(key))
        if source:
            return source
    for key in ("features", "items", "records"):
        for item in safe_list(rec.get(key)):
            source = _source_evidence(item)
            if source:
                return source
    if isinstance(value, list):
        for item in value:
            source = _source_evidence(item)
            if source:
                return source
    return ""


def _layer_evidence(value: Any) -> Dict[str, Any]:
    rec = safe_dict(value)
    count = _layer_count(value)
    verified_absent = bool(
        rec.get("verified_absent")
        or rec.get("absence_verified")
        or rec.get("not_present")
        or safe_str(rec.get("status")).lower() in {"verified_absent", "absent", "none_present", "not_present"}
    )
    source = _source_evidence(value)
    present = value not in (None, "", [], {}) and count > 0 and not verified_absent
    has_source = bool(source)
    return {
        "present": present,
        "count": count if present else 0,
        "verified_absent": verified_absent,
        "source": source,
        "has_source_evidence": has_source,
        "has_evidence": (present or verified_absent) and has_source,
    }


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
    imported_surfaces = safe_list(meta.get("surfaces") or parsed.get("surfaces"))
    surface_count = len(imported_surfaces)
    surface_source = (
        safe_str(grading.get("source_quality"))
        or safe_str(grading.get("grading_source_quality"))
        or safe_str(existing_surface.get("source_quality"))
    )
    surface_evidence_source = ""
    for surface in imported_surfaces:
        surface_evidence_source = safe_str(safe_dict(surface).get("source"))
        if surface_evidence_source:
            break
    source = safe_str(
        survey.get("source")
        or survey.get("file")
        or meta.get("survey_file")
        or parsed.get("survey_file")
        or surface_evidence_source
    )
    has_benchmark = bool(survey.get("benchmark") or survey.get("benchmark_id"))
    has_datum = bool(survey.get("datum") or survey.get("vertical_datum"))
    control_verified = bool(survey.get("control_verified"))
    approved_surface = bool(survey.get("approved_for_production") or survey.get("surface_approved") or control_verified)
    ready = point_count >= 3 or surface_count > 0 or surface_source == "survey" or (bool(source) and approved_surface)
    return {
        "ready": ready,
        "point_count": point_count,
        "source": source or ("survey_surface" if surface_source == "survey" else "missing"),
        "surface_source": surface_source or "missing",
        "imported_surface_count": surface_count,
        "has_control": bool(survey.get("control_points") or (has_benchmark and has_datum and control_verified)),
        "has_benchmark": has_benchmark,
        "has_datum": has_datum,
        "control_verified": control_verified,
        "approved_surface": approved_surface,
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
        layers[layer] = _layer_evidence(gis.get(layer))
    return {
        "ready": all(item["has_evidence"] for item in layers.values()),
        "source": safe_str(gis.get("source") or gis.get("provider"), "missing"),
        "layers": layers,
        "missing_layers": [layer for layer, item in layers.items() if not item["has_evidence"]],
    }


def _coordinate_summary(meta: Dict[str, Any], parsed: Dict[str, Any]) -> Dict[str, Any]:
    coord = _first_dict(
        meta.get("coordinate_system"),
        parsed.get("coordinate_system"),
        _nested_lookup(parsed, ("site_inputs.coordinate_system", "gis_layers.coordinate_system", "existing_conditions.coordinate_system")),
    )
    return _coordinate_quality(coord, fallback_units=safe_str(parsed.get("units") or meta.get("units"), "ft"))


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
        missing.append({"field": "gis_layers", "reason": "No source-traceable parcel, easement, ROW, floodplain, wetland, or existing utility layers are attached."})
    if not coordinate_system["ready"]:
        missing.append({"field": "coordinate_system", "reason": "No CRS/EPSG/projection is attached for real-world coordinates."})
    elif not coordinate_system["production_usable"]:
        missing.extend(deepcopy(safe_list(coordinate_system.get("blockers"))))
    survey_control_verified = bool(survey["has_control"] and survey["has_benchmark"] and survey["has_datum"] and survey["control_verified"])
    if survey["ready"]:
        if not survey["has_benchmark"]:
            missing.append({"field": "survey_benchmark", "reason": "Survey evidence exists but benchmark metadata is missing."})
        if not survey["has_datum"]:
            missing.append({"field": "survey_datum", "reason": "Survey evidence exists but vertical datum metadata is missing."})
        if not survey["control_verified"]:
            missing.append({"field": "survey_control_verified", "reason": "Survey/control evidence is not explicitly verified."})
        if not survey_control_verified:
            warnings.append("Survey evidence exists but benchmark/datum/control metadata is incomplete.")
    for layer, item in gis["layers"].items():
        if (item["present"] or item["verified_absent"]) and not item["has_source_evidence"]:
            missing.append(
                {
                    "field": f"gis_{layer}_source",
                    "reason": f"{layer.replace('_', ' ')} evidence exists but source/provider metadata is missing.",
                }
            )
    if dem_lidar["ready"] and not dem_lidar["approved_for_production"]:
        warnings.append("DEM/LiDAR or terrain source is present but not marked production-approved.")

    return {
        "version": "existing_conditions_v1",
        "production_ready": not missing and ((survey["ready"] and survey_control_verified) or dem_lidar["approved_for_production"]),
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
