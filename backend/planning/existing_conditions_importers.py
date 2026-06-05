from __future__ import annotations

import csv
import importlib.util
import json
import re
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from engines.surface_engine import GridSurface, SurfaceEngine, SurveyPoint

from .common import dedupe_keep_order, readiness_issue_explanations, safe_dict, safe_float, safe_int, safe_list, safe_str
from .existing_conditions import REQUIRED_GIS_LAYERS
from .landxml_io import import_landxml


SURVEY_X_COLUMNS = ("x", "easting", "east", "lon", "longitude")
SURVEY_Y_COLUMNS = ("y", "northing", "north", "lat", "latitude")
SURVEY_Z_COLUMNS = ("z", "elev", "elevation", "height")
SURVEY_ID_COLUMNS = ("point_id", "point", "id", "name", "number")
SURVEY_DESC_COLUMNS = ("description", "desc", "code", "feature", "label")
HEAVY_FORMAT_REQUIREMENTS = {
    ".dxf": "DXF import requires ezdxf.",
    ".shp": "Shapefile import requires fiona/geopandas or GDAL.",
    ".gpkg": "GeoPackage import requires fiona/geopandas or GDAL.",
    ".tif": "GeoTIFF import requires rasterio/GDAL.",
    ".tiff": "GeoTIFF import requires rasterio/GDAL.",
    ".las": "LAS point-cloud import requires laspy plus coordinate metadata validation.",
    ".laz": "LAZ point-cloud import requires laspy with LAZ backend support.",
}
GEOGRAPHIC_EPSG_CODES = {"4326", "4269", "4258"}
ENGINEERING_UNITS = {"ft", "foot", "feet", "us-ft", "us_survey_ft", "survey_ft", "m", "meter", "meters", "metre", "metres"}
COORDINATE_SOURCE_KEYS = ("source", "authority", "control_source", "source_url", "official_source_url", "survey_control")
GIS_SOURCE_KEYS = ("source", "provider", "source_url", "file", "file_name", "dataset", "authority", "agency")


def _normalized_field_map(fieldnames: Iterable[str]) -> Dict[str, str]:
    return {safe_str(name).strip().lower(): safe_str(name) for name in fieldnames if safe_str(name)}


def _first_column(fields: Dict[str, str], candidates: Iterable[str]) -> str:
    for candidate in candidates:
        if candidate in fields:
            return fields[candidate]
    return ""


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _source_evidence(value: Any) -> str:
    rec = safe_dict(value)
    for key in GIS_SOURCE_KEYS:
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


def _bounds(points: List[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    if not points:
        return None
    xs = [safe_float(point.get("x"), 0.0) for point in points]
    ys = [safe_float(point.get("y"), 0.0) for point in points]
    return {"min_x": min(xs), "min_y": min(ys), "max_x": max(xs), "max_y": max(ys)}


def _point_quality(points: List[Dict[str, Any]]) -> Dict[str, Any]:
    unique_xy = {
        (round(safe_float(point.get("x"), 0.0), 6), round(safe_float(point.get("y"), 0.0), 6))
        for point in points
    }
    bounds = _bounds(points)
    width = safe_float(safe_dict(bounds).get("max_x"), 0.0) - safe_float(safe_dict(bounds).get("min_x"), 0.0)
    height = safe_float(safe_dict(bounds).get("max_y"), 0.0) - safe_float(safe_dict(bounds).get("min_y"), 0.0)
    elevations = [safe_float(point.get("z"), 0.0) for point in points]
    return {
        "unique_xy_count": len(unique_xy),
        "duplicate_xy_count": max(0, len(points) - len(unique_xy)),
        "bounds": bounds,
        "span_x": round(width, 6),
        "span_y": round(height, 6),
        "has_surface_span": width > 0.0 and height > 0.0,
        "elevation_range": {"min": min(elevations), "max": max(elevations)} if elevations else None,
    }


def _coordinate_key(value: Dict[str, Any]) -> str:
    rec = _normalize_coordinate_system(value)
    epsg = safe_str(rec.get("epsg"))
    name = safe_str(rec.get("name") or rec.get("crs"))
    return (epsg or name).lower()


def _epsg_code(value: str) -> str:
    text = safe_str(value).upper().replace("EPSG::", "EPSG:")
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


def _normalize_coordinate_system(value: Dict[str, Any]) -> Dict[str, Any]:
    rec = deepcopy(safe_dict(value))
    raw = safe_str(rec.get("epsg") or rec.get("EPSG") or rec.get("name") or rec.get("crs") or rec.get("projection"))
    code = _epsg_code(raw)
    if code:
        rec["epsg"] = f"EPSG:{code}"
    units = _normalize_units(safe_str(rec.get("units")))
    if not units and code in GEOGRAPHIC_EPSG_CODES:
        units = "degrees"
    if units:
        rec["units"] = units
    rec["is_geographic"] = bool(code in GEOGRAPHIC_EPSG_CODES or units in {"degree", "degrees", "decimal_degrees"})
    rec["is_projected"] = bool(code and not rec["is_geographic"])
    return rec


def _coordinate_validation(value: Dict[str, Any]) -> Dict[str, Any]:
    coord = _normalize_coordinate_system(value)
    missing: List[str] = []
    blockers: List[Dict[str, Any]] = []
    warnings: List[str] = []
    if not safe_str(coord.get("epsg") or coord.get("name") or coord.get("crs")):
        missing.append("epsg_or_projection")
    units = safe_str(coord.get("units"))
    if not units:
        missing.append("units")
    elif units not in ENGINEERING_UNITS:
        blockers.append({"field": "coordinate_system", "reason": f"Coordinate units '{units}' are not engineering distance units."})
    if bool(coord.get("is_geographic")):
        blockers.append({"field": "coordinate_system", "reason": "Geographic latitude/longitude CRS is map context only; engineering quantities require a projected site CRS."})
    if missing:
        blockers.append({"field": "coordinate_system", "reason": "Coordinate system metadata is incomplete.", "missing_fields": missing})
    if safe_str(coord.get("epsg")) in {"EPSG:3857", "EPSG:900913"}:
        warnings.append("Web Mercator is not survey-grade for civil engineering quantities; confirm a local projected CRS.")
    if not any(safe_str(coord.get(key)) for key in COORDINATE_SOURCE_KEYS):
        blockers.append(
            {
                "field": "coordinate_system_source",
                "reason": "Coordinate system needs source/control metadata before imported conditions are production-usable.",
            }
        )
    return {
        "valid": not blockers,
        "production_usable": not blockers,
        "coordinate_system": coord,
        "blockers": blockers,
        "blocker_details": readiness_issue_explanations(blockers),
        "warnings": warnings,
        "truth_label": "Coordinate systems must be projected with engineering distance units before imports are production-usable.",
    }


def _coordinate_from_import(rec: Dict[str, Any]) -> Dict[str, Any]:
    coordinate = safe_dict(rec.get("coordinate_system"))
    if coordinate:
        return _normalize_coordinate_system(coordinate)
    surface = rec.get("surface")
    profile = safe_dict(getattr(surface, "_inferred_profile", {})) if surface is not None else {}
    return _normalize_coordinate_system(safe_dict(profile.get("coordinate_system")))


def import_survey_csv(path: Path, *, coordinate_system: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    points: List[Dict[str, Any]] = []
    warnings: List[str] = []
    invalid_rows = 0
    with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = _normalized_field_map(reader.fieldnames or [])
        x_col = _first_column(fields, SURVEY_X_COLUMNS)
        y_col = _first_column(fields, SURVEY_Y_COLUMNS)
        z_col = _first_column(fields, SURVEY_Z_COLUMNS)
        id_col = _first_column(fields, SURVEY_ID_COLUMNS)
        desc_col = _first_column(fields, SURVEY_DESC_COLUMNS)
        if not (x_col and y_col and z_col):
            return {
                "success": False,
                "source": str(path),
                "source_type": "survey_csv",
                "points": [],
                "point_count": 0,
                "invalid_rows": 0,
                "recognized_columns": {"x": x_col, "y": y_col, "z": z_col, "id": id_col, "description": desc_col},
                "warnings": ["Survey CSV must include x/y/z, easting/northing/elevation, or longitude/latitude/elevation columns."],
            }
        for index, row in enumerate(reader, start=2):
            try:
                point = {
                    "point_id": safe_str(row.get(id_col), f"P-{index - 1}") if id_col else f"P-{index - 1}",
                    "x": float(row.get(x_col, "")),
                    "y": float(row.get(y_col, "")),
                    "z": float(row.get(z_col, "")),
                    "description": safe_str(row.get(desc_col), "") if desc_col else "",
                }
            except Exception:
                invalid_rows += 1
                continue
            points.append(point)
    if len(points) < 3:
        warnings.append("Survey CSV needs at least 3 valid points before it can build a surface.")
    quality = _point_quality(points)
    if safe_int(quality.get("unique_xy_count"), 0) < 3:
        warnings.append("Survey CSV needs at least 3 unique x/y locations before it can build a surface.")
    if points and not bool(quality.get("has_surface_span")):
        warnings.append("Survey CSV points do not span both x and y directions; surface generation is blocked.")
    return {
        "success": len(points) >= 3 and safe_int(quality.get("unique_xy_count"), 0) >= 3 and bool(quality.get("has_surface_span")),
        "source": str(path),
        "source_type": "survey_csv",
        "points": points,
        "point_count": len(points),
        "invalid_rows": invalid_rows,
        "quality": quality,
        "recognized_columns": {"x": x_col, "y": y_col, "z": z_col, "id": id_col, "description": desc_col},
        "bounds": quality.get("bounds"),
        "elevation_range": quality.get("elevation_range"),
        "coordinate_system": safe_dict(coordinate_system),
        "coordinate_validation": _coordinate_validation(safe_dict(coordinate_system)) if coordinate_system else {},
        "warnings": warnings,
    }


def surface_from_survey_import(import_result: Dict[str, Any], *, cell_size: float = 10.0, padding: float = 0.0) -> Optional[GridSurface]:
    points = [
        SurveyPoint(x=safe_float(point.get("x")), y=safe_float(point.get("y")), z=safe_float(point.get("z")))
        for point in safe_list(import_result.get("points"))
    ]
    quality = safe_dict(import_result.get("quality")) or _point_quality([{"x": point.x, "y": point.y, "z": point.z} for point in points])
    if len(points) < 3 or safe_int(quality.get("unique_xy_count"), 0) < 3 or not bool(quality.get("has_surface_span")):
        return None
    surface = SurfaceEngine(points).build_grid(cell_size=max(0.1, safe_float(cell_size, 10.0)), padding=max(0.0, safe_float(padding, 0.0)))
    setattr(
        surface,
        "_inferred_profile",
        {
            "source_quality": "survey",
            "source_detail": "survey_csv_import",
            "source_file": safe_str(import_result.get("source")),
            "point_count": len(points),
            "coordinate_system": safe_dict(import_result.get("coordinate_system")),
        },
    )
    return surface


def _read_xyz_rows(path: Path) -> Tuple[List[Dict[str, float]], Dict[str, str], int]:
    rows: List[Dict[str, float]] = []
    invalid_rows = 0
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = _normalized_field_map(reader.fieldnames or [])
        x_col = _first_column(fields, SURVEY_X_COLUMNS)
        y_col = _first_column(fields, SURVEY_Y_COLUMNS)
        z_col = _first_column(fields, SURVEY_Z_COLUMNS)
        if not (x_col and y_col and z_col):
            return [], {"x": x_col, "y": y_col, "z": z_col}, 0
        for row in reader:
            try:
                rows.append({"x": float(row.get(x_col, "")), "y": float(row.get(y_col, "")), "z": float(row.get(z_col, ""))})
            except Exception:
                invalid_rows += 1
    return rows, {"x": x_col, "y": y_col, "z": z_col}, invalid_rows


def import_surface_grid_csv(path: Path, *, coordinate_system: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    xyz_rows, columns, invalid_rows = _read_xyz_rows(Path(path))
    warnings: List[str] = []
    if len(xyz_rows) < 4:
        return {
            "success": False,
            "source": str(path),
            "source_type": "surface_xyz_csv",
            "surface": None,
            "coordinate_system": safe_dict(coordinate_system),
            "invalid_rows": invalid_rows,
            "recognized_columns": columns,
            "warnings": ["Surface CSV needs at least 4 valid x/y/z rows."],
        }
    xs = sorted({round(row["x"], 6) for row in xyz_rows})
    ys = sorted({round(row["y"], 6) for row in xyz_rows})
    if len(xs) < 2 or len(ys) < 2:
        return {
            "success": False,
            "source": str(path),
            "source_type": "surface_xyz_csv",
            "surface": None,
            "coordinate_system": safe_dict(coordinate_system),
            "invalid_rows": invalid_rows,
            "recognized_columns": columns,
            "warnings": ["Surface CSV rows do not span a usable grid."],
        }
    dx_values = [round(xs[index] - xs[index - 1], 6) for index in range(1, len(xs))]
    dy_values = [round(ys[index] - ys[index - 1], 6) for index in range(1, len(ys))]
    cell = min([value for value in dx_values + dy_values if value > 0.0] or [1.0])
    lookup = {(round(row["x"], 6), round(row["y"], 6)): row["z"] for row in xyz_rows}
    values: List[List[float]] = []
    missing_cells = 0
    for y in ys:
        row_values: List[float] = []
        for x in xs:
            z = lookup.get((x, y))
            if z is None:
                missing_cells += 1
                z = _nearest_z(x, y, xyz_rows)
            row_values.append(z)
        values.append(row_values)
    if missing_cells:
        warnings.append(f"Surface grid had {missing_cells} missing cells; nearest imported elevation was used.")
    surface = GridSurface(
        x_min=xs[0],
        y_min=ys[0],
        x_max=xs[-1],
        y_max=ys[-1],
        cell_size=cell,
        ncols=len(xs),
        nrows=len(ys),
        values=values,
    )
    setattr(
        surface,
        "_inferred_profile",
        {
            "source_quality": "survey",
            "source_detail": "surface_xyz_csv_import",
            "source_file": str(path),
            "coordinate_system": safe_dict(coordinate_system),
            "missing_cells": missing_cells,
        },
    )
    return {
        "success": True,
        "source": str(path),
        "source_type": "surface_xyz_csv",
        "surface": surface,
        "ncols": len(xs),
        "nrows": len(ys),
        "cell_size": cell,
        "invalid_rows": invalid_rows,
        "missing_cells": missing_cells,
        "recognized_columns": columns,
        "bounds": {"min_x": xs[0], "min_y": ys[0], "max_x": xs[-1], "max_y": ys[-1]},
        "coordinate_system": safe_dict(coordinate_system),
        "warnings": warnings,
    }


def _nearest_z(x: float, y: float, rows: List[Dict[str, float]]) -> float:
    nearest = min(rows, key=lambda row: (row["x"] - x) ** 2 + (row["y"] - y) ** 2)
    return nearest["z"]


def import_geojson(path: Path, *, layer_hint: str = "", coordinate_system: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    warnings: List[str] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    features = safe_list(payload.get("features"))
    if safe_str(payload.get("type")) == "Feature":
        features = [payload]
    layers: Dict[str, List[Dict[str, Any]]] = {layer: [] for layer in REQUIRED_GIS_LAYERS}
    unknown: List[Dict[str, Any]] = []
    for index, feature in enumerate(features, start=1):
        rec = safe_dict(feature)
        layer = _classify_geojson_layer(rec, layer_hint=layer_hint or Path(path).stem)
        normalized = {
            "id": safe_str(rec.get("id"), f"feature-{index}"),
            "geometry": safe_dict(rec.get("geometry")),
            "properties": safe_dict(rec.get("properties")),
            "source": str(path),
        }
        if layer in layers:
            layers[layer].append(normalized)
        else:
            unknown.append(normalized)
    if unknown:
        warnings.append(f"{len(unknown)} GeoJSON features could not be classified into required existing-condition layers.")
    return {
        "success": bool(features),
        "source": str(path),
        "source_type": "geojson",
        "feature_count": len(features),
        "layers": layers,
        "layer_counts": {layer: len(items) for layer, items in layers.items()},
        "unknown_feature_count": len(unknown),
        "coordinate_system": safe_dict(coordinate_system) or _coordinate_from_geojson(payload),
        "warnings": warnings,
    }


def _classify_geojson_layer(feature: Dict[str, Any], *, layer_hint: str = "") -> str:
    props = safe_dict(feature.get("properties"))
    haystack = " ".join(
        safe_str(value).lower()
        for value in (
            layer_hint,
            props.get("layer"),
            props.get("type"),
            props.get("category"),
            props.get("name"),
            props.get("description"),
        )
    )
    if "parcel" in haystack or "property" in haystack:
        return "parcels"
    if "easement" in haystack:
        return "easements"
    if "row" in haystack or "right of way" in haystack or "right-of-way" in haystack:
        return "row"
    if "flood" in haystack or "fema" in haystack:
        return "floodplain"
    if "wetland" in haystack or "nwi" in haystack:
        return "wetlands"
    if "utility" in haystack or "water" in haystack or "sanitary" in haystack or "storm" in haystack or "gas" in haystack or "electric" in haystack:
        return "existing_utilities"
    return ""


def classify_existing_conditions_file(path: Path) -> Dict[str, Any]:
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        return {"supported": True, "format": "csv", "mode": "survey_or_surface_xyz"}
    if suffix in {".geojson", ".json"}:
        return {"supported": True, "format": "geojson", "mode": "gis_features"}
    if suffix == ".dxf":
        available = _module_available("ezdxf")
        return {
            "supported": available,
            "format": "dxf",
            "mode": "survey_breaklines_or_existing_utilities",
            "required_dependency": "" if available else HEAVY_FORMAT_REQUIREMENTS[suffix],
        }
    if suffix == ".xml" or suffix == ".landxml":
        return {"supported": True, "format": "landxml", "mode": "surface_or_alignment_metadata"}
    if suffix == ".zip":
        return _classify_zip(path)
    if suffix in {".shp", ".gpkg"}:
        available = _module_available("geopandas")
        return {
            "supported": available,
            "format": suffix.lstrip("."),
            "mode": "geospatial_vector",
            "required_dependency": "" if available else HEAVY_FORMAT_REQUIREMENTS[suffix],
        }
    if suffix in {".tif", ".tiff"}:
        available = _module_available("rasterio")
        return {
            "supported": available,
            "format": "geotiff",
            "mode": "raster_surface",
            "required_dependency": "" if available else HEAVY_FORMAT_REQUIREMENTS[suffix],
        }
    if suffix in {".las", ".laz"}:
        available = _module_available("laspy")
        return {
            "supported": available,
            "format": suffix.lstrip("."),
            "mode": "point_cloud",
            "required_dependency": "" if available else HEAVY_FORMAT_REQUIREMENTS[suffix],
        }
    if suffix in HEAVY_FORMAT_REQUIREMENTS:
        return {
            "supported": False,
            "format": suffix.lstrip("."),
            "mode": "requires_external_gis_dependency",
            "required_dependency": HEAVY_FORMAT_REQUIREMENTS[suffix],
        }
    return {"supported": False, "format": suffix.lstrip(".") or "unknown", "mode": "unsupported"}


def _dxf_point_tuple(value: Any) -> Tuple[float, float, float]:
    return (
        safe_float(getattr(value, "x", 0.0), 0.0),
        safe_float(getattr(value, "y", 0.0), 0.0),
        safe_float(getattr(value, "z", 0.0), 0.0),
    )


def _dxf_feature(layer: str, geometry_type: str, coordinates: Any, *, source: Path, entity_type: str) -> Dict[str, Any]:
    return {
        "id": f"{entity_type}-{abs(hash((layer, safe_str(coordinates)))) % 1000000}",
        "geometry": {"type": geometry_type, "coordinates": coordinates},
        "properties": {"layer": layer, "type": entity_type, "source_format": "dxf"},
        "source": str(source),
    }


def _dxf_polyline_coordinates(entity: Any) -> List[Tuple[float, float, float]]:
    if entity.dxftype() == "LWPOLYLINE":
        elevation = safe_float(getattr(entity.dxf, "elevation", 0.0), 0.0)
        coords: List[Tuple[float, float, float]] = []
        for point in entity.get_points("xy"):
            coords.append((safe_float(point[0], 0.0), safe_float(point[1], 0.0), elevation))
        return coords
    if entity.dxftype() == "POLYLINE":
        return [_dxf_point_tuple(vertex.dxf.location) for vertex in entity.vertices]
    return []


def _dxf_layer_kind(layer: str, entity_type: str) -> str:
    haystack = f"{layer} {entity_type}".lower()
    words = {part for part in re.split(r"[^a-z0-9]+", haystack) if part}
    if any(token in words for token in ("contour", "breakline", "tin", "surface", "grade")):
        return "surface"
    if any(token in words for token in ("point", "points", "spot", "survey", "shot", "cogo")):
        return "survey"
    return "gis"


def import_dxf_existing_conditions(path: Path, *, coordinate_system: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not _module_available("ezdxf"):
        return {"success": False, "source": str(path), "source_type": "dxf_existing_conditions", "warnings": ["ezdxf is required for DXF import."]}
    import ezdxf

    warnings: List[str] = []
    try:
        doc = ezdxf.readfile(path)
    except Exception as exc:
        return {"success": False, "source": str(path), "source_type": "dxf_existing_conditions", "warnings": [safe_str(exc)]}

    layers: Dict[str, List[Dict[str, Any]]] = {layer: [] for layer in REQUIRED_GIS_LAYERS}
    survey_points: List[Dict[str, Any]] = []
    breaklines: List[Dict[str, Any]] = []
    unknown_feature_count = 0
    entity_count = 0
    for index, entity in enumerate(doc.modelspace(), start=1):
        entity_count += 1
        entity_type = safe_str(entity.dxftype())
        layer = safe_str(getattr(entity.dxf, "layer", ""), "0")
        kind = _dxf_layer_kind(layer, entity_type)
        if entity_type == "POINT":
            x, y, z = _dxf_point_tuple(entity.dxf.location)
            survey_points.append(
                {
                    "point_id": safe_str(getattr(entity.dxf, "handle", ""), f"DXF-P-{index}"),
                    "x": x,
                    "y": y,
                    "z": z,
                    "description": layer,
                    "source": str(path),
                }
            )
            if kind == "survey":
                continue
            feature = _dxf_feature(layer, "Point", [x, y, z], source=path, entity_type=entity_type)
        elif entity_type == "LINE":
            start = _dxf_point_tuple(entity.dxf.start)
            end = _dxf_point_tuple(entity.dxf.end)
            coords = [start, end]
            if kind == "surface":
                breaklines.append({"name": f"{layer}-{index}", "layer": layer, "points": coords, "source": str(path), "entity_type": entity_type})
                continue
            feature = _dxf_feature(layer, "LineString", coords, source=path, entity_type=entity_type)
        elif entity_type in {"LWPOLYLINE", "POLYLINE"}:
            coords = _dxf_polyline_coordinates(entity)
            if len(coords) < 2:
                continue
            closed = bool(getattr(entity, "closed", False))
            if kind == "surface":
                breaklines.append({"name": f"{layer}-{index}", "layer": layer, "points": coords, "closed": closed, "source": str(path), "entity_type": entity_type})
                continue
            geom_type = "Polygon" if closed else "LineString"
            geom_coords = [coords] if closed else coords
            feature = _dxf_feature(layer, geom_type, geom_coords, source=path, entity_type=entity_type)
        elif entity_type == "INSERT":
            insert = _dxf_point_tuple(entity.dxf.insert)
            feature = _dxf_feature(layer, "Point", list(insert), source=path, entity_type=entity_type)
        else:
            continue

        layer_name = _classify_geojson_layer({"properties": feature["properties"], "geometry": feature["geometry"]}, layer_hint=layer)
        if layer_name in layers:
            layers[layer_name].append(feature)
        else:
            unknown_feature_count += 1

    if not coordinate_system:
        warnings.append("DXF does not carry reliable CRS metadata here; production readiness remains blocked until CRS/EPSG is confirmed.")
    point_elevations = [safe_float(point.get("z"), 0.0) for point in survey_points]
    return {
        "success": bool(survey_points or breaklines or any(layers.values())),
        "source": str(path),
        "source_type": "dxf_existing_conditions",
        "entity_count": entity_count,
        "point_count": len(survey_points),
        "breakline_count": len(breaklines),
        "points": survey_points,
        "breaklines": breaklines,
        "layers": layers,
        "layer_counts": {layer: len(items) for layer, items in layers.items()},
        "unknown_feature_count": unknown_feature_count,
        "bounds": _bounds(survey_points),
        "elevation_range": {"min": min(point_elevations), "max": max(point_elevations)} if point_elevations else None,
        "coordinate_system": safe_dict(coordinate_system),
        "warnings": warnings,
        "truth_label": "DXF geometry was imported as existing-condition evidence; CRS, survey control, and layer semantics require review before production use.",
    }


def _classify_zip(path: Path) -> Dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as archive:
            names = [Path(name).suffix.lower() for name in archive.namelist()]
    except Exception as exc:
        return {"supported": False, "format": "zip", "mode": "unreadable_zip", "warning": safe_str(exc)}
    if ".shp" in names:
        available = _module_available("geopandas")
        return {
            "supported": available,
            "format": "zipped_shapefile",
            "mode": "geospatial_vector",
            "required_dependency": "" if available else HEAVY_FORMAT_REQUIREMENTS[".shp"],
        }
    return {"supported": False, "format": "zip", "mode": "unsupported_zip_contents"}


def import_geospatial_vector_file(path: Path, *, layer_hint: str = "", coordinate_system: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not _module_available("geopandas"):
        return {
            "success": False,
            "source": str(path),
            "source_type": "geospatial_vector",
            "warnings": ["GeoPandas is required for Shapefile/GeoPackage vector import."],
        }
    import geopandas as gpd

    warnings: List[str] = []
    try:
        gdf = gpd.read_file(path)
    except Exception as exc:
        return {"success": False, "source": str(path), "source_type": "geospatial_vector", "warnings": [safe_str(exc)]}
    crs_text = safe_str(gdf.crs.to_string() if gdf.crs is not None else "")
    if gdf.crs is not None:
        try:
            export_gdf = gdf.to_crs("EPSG:4326")
        except Exception as exc:
            warnings.append(f"CRS transform to EPSG:4326 failed; using source coordinates. {exc}")
            export_gdf = gdf
    else:
        export_gdf = gdf
        warnings.append("Vector file has no CRS metadata; production readiness must remain blocked until CRS is confirmed.")
    layers: Dict[str, List[Dict[str, Any]]] = {layer: [] for layer in REQUIRED_GIS_LAYERS}
    unknown = 0
    for index, row in export_gdf.iterrows():
        props = {safe_str(key): _json_safe_value(value) for key, value in dict(row.drop(labels=[export_gdf.geometry.name], errors="ignore")).items()}
        feature = {
            "id": safe_str(props.get("id") or props.get("OBJECTID") or props.get("objectid"), f"feature-{index + 1}"),
            "type": "Feature",
            "properties": props,
            "geometry": row.geometry.__geo_interface__ if row.geometry is not None else {},
        }
        layer = _classify_geojson_layer(feature, layer_hint=layer_hint or Path(path).stem)
        if layer in layers:
            layers[layer].append({"id": feature["id"], "geometry": feature["geometry"], "properties": props, "source": str(path)})
        else:
            unknown += 1
    return {
        "success": len(export_gdf) > 0,
        "source": str(path),
        "source_type": "geospatial_vector",
        "feature_count": int(len(export_gdf)),
        "layers": layers,
        "layer_counts": {layer: len(items) for layer, items in layers.items()},
        "unknown_feature_count": unknown,
        "coordinate_system": safe_dict(coordinate_system) or ({"name": crs_text, "source": "vector_crs"} if crs_text else {}),
        "warnings": warnings,
    }


def _json_safe_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    try:
        if hasattr(value, "item"):
            return value.item()
    except Exception:
        pass
    return safe_str(value)


def import_geotiff_surface(path: Path, *, coordinate_system: Optional[Dict[str, Any]] = None, max_cells: int = 40000) -> Dict[str, Any]:
    if not _module_available("rasterio"):
        return {"success": False, "source": str(path), "source_type": "geotiff_surface", "warnings": ["Rasterio/GDAL is required for GeoTIFF import."]}
    import math
    import rasterio

    warnings: List[str] = []
    try:
        with rasterio.open(path) as dataset:
            factor = max(1, int(math.ceil(((dataset.width * dataset.height) / max(1, max_cells)) ** 0.5)))
            out_width = max(1, int(math.ceil(dataset.width / factor)))
            out_height = max(1, int(math.ceil(dataset.height / factor)))
            data = dataset.read(1, out_shape=(out_height, out_width), masked=True)
            transform = dataset.transform * dataset.transform.scale(dataset.width / out_width, dataset.height / out_height)
            values: List[List[float]] = []
            finite: List[float] = []
            for row in range(out_height):
                row_vals: List[float] = []
                for col in range(out_width):
                    raw = data[row, col]
                    value = float(raw) if raw is not None and not getattr(raw, "mask", False) else float("nan")
                    if math.isfinite(value):
                        finite.append(value)
                    row_vals.append(value)
                values.append(row_vals)
            fill = sum(finite) / len(finite) if finite else 0.0
            values = [[fill if not math.isfinite(value) else value for value in row] for row in values]
            x0, y0 = transform * (0, 0)
            x1, y1 = transform * (out_width - 1, out_height - 1)
            cell_x = abs(float(transform.a)) or 1.0
            cell_y = abs(float(transform.e)) or cell_x
            cell = (cell_x + cell_y) / 2.0
            surface = GridSurface(
                x_min=min(x0, x1),
                y_min=min(y0, y1),
                x_max=max(x0, x1),
                y_max=max(y0, y1),
                cell_size=cell,
                ncols=out_width,
                nrows=out_height,
                values=values,
            )
            crs_text = safe_str(dataset.crs.to_string() if dataset.crs is not None else "")
    except Exception as exc:
        return {"success": False, "source": str(path), "source_type": "geotiff_surface", "warnings": [safe_str(exc)]}
    setattr(
        surface,
        "_inferred_profile",
        {
            "source_quality": "dem",
            "source_detail": "geotiff_import",
            "source_file": str(path),
            "coordinate_system": safe_dict(coordinate_system) or ({"name": crs_text, "source": "geotiff_crs"} if crs_text else {}),
            "downsample_factor": factor,
        },
    )
    if factor > 1:
        warnings.append(f"GeoTIFF was downsampled by factor {factor} to keep backend import bounded.")
    return {
        "success": True,
        "source": str(path),
        "source_type": "geotiff_surface",
        "surface": surface,
        "ncols": surface.ncols,
        "nrows": surface.nrows,
        "cell_size": surface.cell_size,
        "coordinate_system": safe_dict(coordinate_system) or ({"name": crs_text, "source": "geotiff_crs"} if crs_text else {}),
        "warnings": warnings,
    }


def import_las_point_cloud(path: Path, *, coordinate_system: Optional[Dict[str, Any]] = None, max_points: int = 5000) -> Dict[str, Any]:
    if not _module_available("laspy"):
        return {"success": False, "source": str(path), "source_type": "las_point_cloud", "warnings": ["laspy is required for LAS/LAZ import."]}
    import laspy

    warnings: List[str] = []
    try:
        las = laspy.read(path)
    except Exception as exc:
        return {"success": False, "source": str(path), "source_type": "las_point_cloud", "warnings": [safe_str(exc)]}
    total = len(las.x)
    if total <= 0:
        return {"success": False, "source": str(path), "source_type": "las_point_cloud", "warnings": ["LAS/LAZ file has no points."]}
    step = max(1, int(total / max(1, max_points)))
    points = [
        {"x": float(las.x[index]), "y": float(las.y[index]), "z": float(las.z[index])}
        for index in range(0, total, step)
    ][:max_points]
    if step > 1:
        warnings.append(f"LAS/LAZ point cloud sampled every {step} points for bounded backend import.")
    return {
        "success": len(points) >= 3,
        "source": str(path),
        "source_type": "las_point_cloud",
        "point_count": len(points),
        "source_point_count": int(total),
        "points": points,
        "bounds": _bounds(points),
        "coordinate_system": safe_dict(coordinate_system),
        "warnings": warnings,
        "truth_label": "Point cloud imported as sampled surface evidence; classification/breakline extraction still needs deeper processing.",
    }


def import_landxml_metadata(path: Path, *, coordinate_system: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    imported = import_landxml(path)
    if coordinate_system:
        imported["coordinate_system"] = safe_dict(coordinate_system)
    return imported


def _coordinate_from_geojson(payload: Dict[str, Any]) -> Dict[str, Any]:
    crs = safe_dict(payload.get("crs"))
    props = safe_dict(crs.get("properties"))
    name = safe_str(props.get("name") or crs.get("name"))
    if not name:
        return {}
    return _normalize_coordinate_system({
        "name": name,
        "source": "geojson_crs",
    })


def merge_imported_existing_conditions(*imports: Dict[str, Any]) -> Dict[str, Any]:
    survey_points: List[Dict[str, Any]] = []
    breaklines: List[Dict[str, Any]] = []
    gis_layers: Dict[str, List[Dict[str, Any]]] = {layer: [] for layer in REQUIRED_GIS_LAYERS}
    surfaces: List[Dict[str, Any]] = []
    warnings: List[str] = []
    coordinate_system: Dict[str, Any] = {}
    coordinate_systems: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []
    for item in imports:
        rec = safe_dict(item)
        if not rec:
            continue
        sources.append({"source": safe_str(rec.get("source")), "source_type": safe_str(rec.get("source_type")), "success": bool(rec.get("success"))})
        warnings.extend(safe_list(rec.get("warnings")))
        rec_coordinate = _coordinate_from_import(rec)
        if rec_coordinate:
            coordinate_systems.append(rec_coordinate)
        if not coordinate_system:
            coordinate_system = rec_coordinate
        if rec.get("source_type") in {"survey_csv", "las_point_cloud", "dxf_existing_conditions"}:
            survey_points.extend(safe_list(rec.get("points")))
        if rec.get("source_type") == "dxf_existing_conditions":
            breaklines.extend(safe_list(rec.get("breaklines")))
        if rec.get("source_type") in {"surface_xyz_csv", "geotiff_surface"} and rec.get("surface") is not None:
            surfaces.append({"source": rec.get("source"), "surface": rec.get("surface"), "ncols": rec.get("ncols"), "nrows": rec.get("nrows")})
        if rec.get("source_type") in {"geojson", "geospatial_vector", "dxf_existing_conditions"}:
            for layer, features in safe_dict(rec.get("layers")).items():
                if layer in gis_layers:
                    gis_layers[layer].extend(safe_list(features))
    merged = {
        "success": any(source["success"] for source in sources),
        "source_type": "merged_existing_conditions",
        "sources": sources,
        "survey": {
            "source": "imported_existing_conditions" if survey_points else "missing",
            "point_count": len(survey_points),
            "points": survey_points,
            "breakline_count": len(breaklines),
            "breaklines": breaklines,
        },
        "gis_layers": gis_layers,
        "existing_conditions": gis_layers,
        "coordinate_system": _normalize_coordinate_system(coordinate_system),
        "coordinate_systems": coordinate_systems,
        "surfaces": surfaces,
        "warnings": warnings,
    }
    merged["import_validation"] = validate_imported_existing_conditions_package(merged)
    return merged


def validate_imported_existing_conditions_package(
    merged: Dict[str, Any],
    *,
    require_all_gis_layers: bool = True,
    require_surface: bool = True,
) -> Dict[str, Any]:
    """Validate whether imported existing-condition evidence is safe to use.

    This is intentionally stricter than basic import success. A file can parse
    successfully but still be unsafe for production use when CRS, survey
    control, surfaces, or required constraint layers are missing.
    """

    rec = safe_dict(merged)
    blockers: List[Dict[str, Any]] = []
    warnings: List[str] = [safe_str(item) for item in safe_list(rec.get("warnings")) if safe_str(item)]
    sources = [safe_dict(item) for item in safe_list(rec.get("sources"))]
    failed_sources = [source for source in sources if source and not bool(source.get("success"))]
    if failed_sources:
        blockers.append(
            {
                "field": "sources",
                "reason": "One or more existing-condition imports failed.",
                "sources": failed_sources,
            }
        )

    coordinate = _normalize_coordinate_system(safe_dict(rec.get("coordinate_system")))
    coordinate_systems = [safe_dict(item) for item in safe_list(rec.get("coordinate_systems")) if safe_dict(item)]
    coordinate_keys = sorted({key for key in (_coordinate_key(item) for item in coordinate_systems) if key})
    if not coordinate and not coordinate_keys:
        blockers.append({"field": "coordinate_system", "reason": "No CRS/EPSG/coordinate system was confirmed."})
    elif len(coordinate_keys) > 1:
        blockers.append(
            {
                "field": "coordinate_system",
                "reason": "Imported sources use conflicting coordinate systems.",
                "coordinate_systems": coordinate_systems,
            }
        )
    coordinate_validation = _coordinate_validation(coordinate or (coordinate_systems[0] if coordinate_systems else {}))
    blockers.extend(safe_list(coordinate_validation.get("blockers")))
    warnings.extend(safe_list(coordinate_validation.get("warnings")))

    survey = safe_dict(rec.get("survey"))
    point_count = safe_int(survey.get("point_count"), len(safe_list(survey.get("points"))))
    breakline_count = safe_int(survey.get("breakline_count"), len(safe_list(survey.get("breaklines"))))
    survey_points = [safe_dict(item) for item in safe_list(survey.get("points"))]
    point_quality = _point_quality(survey_points)
    surface_count = len(safe_list(rec.get("surfaces")))
    if require_surface and point_count < 3 and surface_count <= 0:
        blockers.append(
            {
                "field": "survey_surface",
                "reason": "No usable survey surface, DEM/LiDAR surface, or at least 3 survey points were imported.",
            }
        )
    elif require_surface and surface_count <= 0 and safe_int(point_quality.get("unique_xy_count"), 0) < 3:
        blockers.append(
            {
                "field": "survey_surface",
                "reason": "Survey evidence has fewer than 3 unique x/y locations; no terrain surface can be built.",
                "unique_xy_count": safe_int(point_quality.get("unique_xy_count"), 0),
            }
        )
    elif require_surface and surface_count <= 0 and not bool(point_quality.get("has_surface_span")):
        blockers.append(
            {
                "field": "survey_surface",
                "reason": "Survey evidence is geometrically collapsed and does not span both x and y directions.",
                "span_x": point_quality.get("span_x"),
                "span_y": point_quality.get("span_y"),
            }
        )
    elif point_count >= 3 and breakline_count <= 0:
        warnings.append("Survey points are present, but no breaklines were imported.")
    if point_count > 0:
        if not safe_str(survey.get("benchmark") or survey.get("benchmark_id")):
            blockers.append(
                {
                    "field": "survey_benchmark",
                    "reason": "Survey import needs benchmark evidence before it is production-usable.",
                }
            )
        if not safe_str(survey.get("datum") or survey.get("vertical_datum")):
            blockers.append(
                {
                    "field": "survey_datum",
                    "reason": "Survey import needs vertical datum evidence before it is production-usable.",
                }
            )
        if survey.get("control_verified") is not True:
            blockers.append(
                {
                    "field": "survey_control_verified",
                    "reason": "Survey/control evidence must be explicitly verified before production use.",
                }
            )

    gis_layers = safe_dict(rec.get("gis_layers") or rec.get("existing_conditions"))
    layer_counts = {layer: len(safe_list(gis_layers.get(layer))) for layer in REQUIRED_GIS_LAYERS}
    present_layers = [layer for layer, count in layer_counts.items() if count > 0]
    source_missing_layers = [layer for layer in present_layers if not _source_evidence(gis_layers.get(layer))]
    if not present_layers:
        blockers.append({"field": "gis_layers", "reason": "No GIS/site constraint layers were imported."})
    elif require_all_gis_layers:
        missing_layers = [layer for layer in REQUIRED_GIS_LAYERS if layer_counts.get(layer, 0) <= 0]
        if missing_layers:
            blockers.append(
                {
                    "field": "gis_layers",
                    "reason": "Required existing-condition GIS layers are missing.",
                    "missing_layers": missing_layers,
                }
            )
    if source_missing_layers:
        blockers.append(
            {
                "field": "gis_layer_sources",
                "reason": "One or more imported GIS layers are missing source/provider metadata.",
                "missing_source_layers": source_missing_layers,
            }
        )

    return {
        "success": not blockers,
        "production_usable": not blockers,
        "blockers": blockers,
        "blocker_details": readiness_issue_explanations(blockers),
        "warnings": dedupe_keep_order(warnings),
        "source_count": len(sources),
        "surface_count": surface_count,
        "survey_point_count": point_count,
        "survey_point_quality": point_quality,
        "breakline_count": breakline_count,
        "layer_counts": layer_counts,
        "coordinate_system_validation": coordinate_validation,
        "truth_label": "Successful import is not production approval; CRS, surface evidence, and required GIS layers must validate first.",
    }


__all__ = [
    "import_geojson",
    "classify_existing_conditions_file",
    "import_geospatial_vector_file",
    "import_dxf_existing_conditions",
    "import_geotiff_surface",
    "import_las_point_cloud",
    "import_landxml_metadata",
    "import_surface_grid_csv",
    "import_survey_csv",
    "merge_imported_existing_conditions",
    "surface_from_survey_import",
    "validate_imported_existing_conditions_package",
]
