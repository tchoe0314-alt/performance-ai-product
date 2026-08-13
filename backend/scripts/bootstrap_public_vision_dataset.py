from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any, Dict, Iterable, List
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from PIL import Image

from backend.planning.vision_public_bootstrap import (
    build_geographic_tile_grid,
    build_weak_supervision_package,
    capture_date_from_epoch_ms,
    capture_season,
    feature_intersects_bbox,
    imagery_quality_band,
    normalize_microsoft_partition_url,
    quadkeys_for_bbox,
)


DEFAULT_USGS_IMAGE_SERVER = "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPPlus/ImageServer"
DEFAULT_BUILDING_INDEX = "https://bfppub.blob.core.windows.net/%24web/2026-07-24/dataset-links.csv"
DEFAULT_SOURCE_REGISTRY = Path("vision/datasets/public-source-registry-v1.json")
ALLOWED_SOURCE_HOSTS = {
    "imagery.nationalmap.gov",
    "bfppub.blob.core.windows.net",
    "bfppub.z5.web.core.windows.net",
    "hydro.nationalmap.gov",
    "tigerweb.geo.census.gov",
}
RETRYABLE_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}
SOURCE_REQUEST_ATTEMPTS = 3


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a real weak-supervision starter set from public USGS imagery and Microsoft footprints."
    )
    parser.add_argument("--center-lat", type=float, required=True)
    parser.add_argument("--center-lon", type=float, required=True)
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--tile-meters", type=float, default=320.0)
    parser.add_argument("--image-pixels", type=int, default=512)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--usgs-image-server", default=DEFAULT_USGS_IMAGE_SERVER)
    parser.add_argument("--building-index-url", default=DEFAULT_BUILDING_INDEX)
    parser.add_argument("--country", default="UnitedStates")
    parser.add_argument("--quadkey-level", type=int, default=9)
    parser.add_argument("--geography-id", default="")
    parser.add_argument("--split", choices=("train", "validation", "test"), default="")
    parser.add_argument("--source-registry", default=str(DEFAULT_SOURCE_REGISTRY))
    parser.add_argument("--imagery-source-id", default="usgs_naip_conus")
    parser.add_argument("--label-source-id", default="microsoft_global_building_footprints")
    args = parser.parse_args()
    result = bootstrap_public_vision_region(
        center_latitude=args.center_lat,
        center_longitude=args.center_lon,
        rows=args.rows,
        columns=args.columns,
        tile_meters=args.tile_meters,
        image_pixels=args.image_pixels,
        output_root=Path(args.output_root),
        usgs_image_server=args.usgs_image_server,
        building_index_url=args.building_index_url,
        country=args.country,
        quadkey_level=args.quadkey_level,
        geography_id=args.geography_id,
        permanent_split=args.split,
        source_registry_path=Path(args.source_registry),
        imagery_source_id=args.imagery_source_id,
        label_source_id=args.label_source_id,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["success"] else 2


def bootstrap_public_vision_region(
    *,
    center_latitude: float,
    center_longitude: float,
    rows: int,
    columns: int,
    tile_meters: float,
    image_pixels: int,
    output_root: Path,
    usgs_image_server: str = DEFAULT_USGS_IMAGE_SERVER,
    building_index_url: str = DEFAULT_BUILDING_INDEX,
    country: str = "UnitedStates",
    quadkey_level: int = 9,
    geography_id: str = "",
    permanent_split: str = "",
    source_registry_path: Path = DEFAULT_SOURCE_REGISTRY,
    imagery_source_id: str = "usgs_naip_conus",
    label_source_id: str = "microsoft_global_building_footprints",
    additional_label_sources: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    registry, registry_fingerprint = _load_source_registry(source_registry_path)
    sources = dict(registry.get("sources") or {})
    imagery_spec = dict(sources.get(imagery_source_id) or {})
    label_spec = dict(sources.get(label_source_id) or {})
    additional_source_configs = [dict(item) for item in additional_label_sources or []]
    if not imagery_spec or imagery_spec.get("source_role") != "training_imagery":
        raise SystemExit(f"Unknown or ineligible imagery source registry entry: {imagery_source_id}")
    if not label_spec or label_spec.get("source_role") != "weak_label_proposals_only":
        raise SystemExit(f"Unknown or ineligible weak-label source registry entry: {label_source_id}")
    for config in additional_source_configs:
        source_id = str(config.get("source_id") or "")
        source_spec = dict(sources.get(source_id) or {})
        if not source_spec or source_spec.get("source_role") != "weak_label_proposals_only":
            raise SystemExit(f"Unknown or ineligible weak-label source registry entry: {source_id}")
    if imagery_spec.get("allowed_geography") == "conterminous_united_states":
        if country != "UnitedStates" or not (-125.0 <= center_longitude <= -66.0 and 24.0 <= center_latitude <= 50.0):
            raise SystemExit("The registered NAIP source is limited to a CONUS collection center.")
    usgs_image_server = str(imagery_spec.get("image_server_url") or usgs_image_server)
    building_index_url = str(label_spec.get("dataset_index_url") or building_index_url)
    record_filter = str(imagery_spec.get("record_filter") or "Category=1 AND acquisition_date IS NOT NULL AND agency='USDA'")

    output_root = output_root.expanduser().resolve()
    image_root = output_root / "images"
    cache_root = output_root / "cache"
    image_root.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)
    tiles = build_geographic_tile_grid(
        center_longitude=center_longitude,
        center_latitude=center_latitude,
        rows=rows,
        columns=columns,
        tile_meters=tile_meters,
        image_pixels=image_pixels,
        permanent_split=permanent_split,
    )
    for tile in tiles:
        destination = image_root / str(tile["file_name"])
        source_records = _select_usgs_records(
            _query_usgs_catalog(usgs_image_server, tile["bbox_wgs84"], where=record_filter)
        )
        if not source_records:
            raise SystemExit(
                f"No rights-cleared USDA NAIP source record covers tile {tile['frame_id']}; no fallback imagery was used."
            )
        source_item_ids = [int(record["OBJECTID"]) for record in source_records]
        image_url = _usgs_export_url(usgs_image_server, tile["bbox_wgs84"], image_pixels, raster_ids=source_item_ids)
        _download_image(image_url, destination)
        with Image.open(destination) as image:
            if image.size != (image_pixels, image_pixels):
                raise SystemExit(f"USGS image dimensions did not match the requested tile: {destination}")
        tile["sha256"] = _file_sha256(destination)
        tile["source_url"] = image_url
        tile["geography_id"] = geography_id
        tile["source_item_ids"] = source_item_ids
        tile["source_item_names"] = [str(record.get("Name") or "") for record in source_records]
        acquisition_ms = max(float(record.get("acquisition_date") or 0) for record in source_records)
        capture_date = capture_date_from_epoch_ms(acquisition_ms)
        resolutions = [float(record.get("resolution_value") or 0) for record in source_records if float(record.get("resolution_value") or 0) > 0]
        resolution = min(resolutions) if resolutions else 0.0
        tile["capture_date"] = capture_date
        tile["capture_year"] = max(int(record.get("Year") or 0) for record in source_records) or None
        tile["season"] = capture_season(capture_date)
        tile["imagery_quality_band"] = imagery_quality_band(resolution)
        tile["resolution_meters"] = resolution or None
        tile["source_agency"] = ", ".join(sorted({str(record.get("agency") or "") for record in source_records if record.get("agency")}))
        tile["source_vendor"] = ", ".join(sorted({str(record.get("vendor") or "") for record in source_records if record.get("vendor")}))
        tile["sensor_type"] = ", ".join(sorted({str(record.get("sensor_type") or "") for record in source_records if record.get("sensor_type")}))
        tile["datum"] = ", ".join(sorted({str(record.get("datum") or "") for record in source_records if record.get("datum")}))

    region_bbox = {
        "west": min(tile["bbox_wgs84"]["west"] for tile in tiles),
        "south": min(tile["bbox_wgs84"]["south"] for tile in tiles),
        "east": max(tile["bbox_wgs84"]["east"] for tile in tiles),
        "north": max(tile["bbox_wgs84"]["north"] for tile in tiles),
    }
    index_text = _download_text(building_index_url)
    partition_urls = _partition_urls(
        index_text,
        country=country,
        quadkeys=quadkeys_for_bbox(region_bbox, level=quadkey_level),
    )
    if not partition_urls:
        raise SystemExit("No Microsoft building-footprint partition matched the requested region.")
    footprints: List[Dict[str, Any]] = []
    for partition_url in partition_urls:
        cache_path = cache_root / (hashlib.sha256(partition_url.encode("utf-8")).hexdigest()[:16] + ".jsonl.gz")
        if not cache_path.is_file():
            _download_file(partition_url, cache_path)
        footprints.extend(_read_footprints(cache_path, region_bbox))
    additional_label_sets = _collect_additional_label_sets(
        source_configs=additional_source_configs,
        source_registry=sources,
        registry_fingerprint=registry_fingerprint,
        bbox=region_bbox,
    )
    package = build_weak_supervision_package(
        tiles=tiles,
        footprint_features=footprints,
        imagery_source={
            "source_id": imagery_source_id,
            "source_role": imagery_spec["source_role"],
            "name": imagery_spec["name"],
            "url": imagery_spec["catalog_url"],
            "license": imagery_spec["license"],
            "license_url": imagery_spec["license_url"],
            "source_rights": _source_rights(imagery_spec, registry_fingerprint=registry_fingerprint),
        },
        label_source={
            "source_id": label_source_id,
            "source_role": label_spec["source_role"],
            "name": label_spec["name"],
            "url": label_spec["source_url"],
            "license": label_spec["license"],
            "license_url": label_spec["license_url"],
            "source_rights": _source_rights(label_spec, registry_fingerprint=registry_fingerprint),
        },
        additional_label_sets=additional_label_sets,
    )
    package["geography_id"] = geography_id
    package["source_region_bbox_wgs84"] = region_bbox
    package["source_partition_urls"] = partition_urls
    package["source_registry"] = {
        "version": registry.get("version"),
        "fingerprint": registry_fingerprint,
        "imagery_source_id": imagery_source_id,
        "label_source_id": label_source_id,
    }
    package["image_root"] = str(image_root)
    package_path = output_root / "weak-coco-package.json"
    review_path = output_root / "review-candidates.geojson"
    manifest_path = output_root / "source-manifest.json"
    package_path.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    review_path.write_text(json.dumps(package["review_candidates"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "version": package["bootstrap_version"],
                "dataset_fingerprint": package["dataset_fingerprint"],
                "imagery_tiles": len(package["images"]),
                "weak_building_labels": _annotation_counts_by_class(package).get("building", 0),
                "weak_proposals_by_class": _annotation_counts_by_class(package),
                "source_region_bbox_wgs84": region_bbox,
                "geography_id": geography_id,
                "capture_dates": sorted({str(tile.get("capture_date") or "") for tile in tiles if tile.get("capture_date")}),
                "seasons": sorted({str(tile.get("season") or "") for tile in tiles if tile.get("season")}),
                "imagery_quality_bands": sorted({str(tile.get("imagery_quality_band") or "") for tile in tiles if tile.get("imagery_quality_band")}),
                "source_registry_fingerprint": registry_fingerprint,
                "supervision_status": package["supervision_status"],
                "promotion_eligible": False,
                "promotion_blockers": package["promotion_blockers"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "success": bool(package["images"] and package["annotations"]),
        "package": str(package_path),
        "image_root": str(image_root),
        "review_candidates": str(review_path),
        "imagery_tiles": len(package["images"]),
        "weak_building_labels": _annotation_counts_by_class(package).get("building", 0),
        "weak_proposals_by_class": _annotation_counts_by_class(package),
        "capture_dates": sorted({str(tile.get("capture_date") or "") for tile in tiles if tile.get("capture_date")}),
        "seasons": sorted({str(tile.get("season") or "") for tile in tiles if tile.get("season")}),
        "imagery_quality_bands": sorted({str(tile.get("imagery_quality_band") or "") for tile in tiles if tile.get("imagery_quality_band")}),
        "splits": package["splits"],
        "promotion_eligible": False,
        "promotion_blockers": package["promotion_blockers"],
    }


def _collect_additional_label_sets(
    *,
    source_configs: List[Dict[str, Any]],
    source_registry: Dict[str, Any],
    registry_fingerprint: str,
    bbox: Dict[str, Any],
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for config in source_configs:
        source_id = str(config.get("source_id") or "")
        spec = dict(source_registry.get(source_id) or {})
        service_url = str(spec.get("service_url") or "")
        layer_specs = [dict(item) for item in spec.get("service_layers") or [] if isinstance(item, dict)]
        features: List[Dict[str, Any]] = []
        for layer_spec in layer_specs:
            layer_features = _query_arcgis_geojson_features(
                service_url,
                int(layer_spec.get("layer_id") or 0),
                bbox,
            )
            buffer_meters = float(layer_spec.get("centerline_buffer_meters") or 0.0)
            if buffer_meters > 0:
                for feature in layer_features:
                    features.extend(_buffer_line_feature(feature, half_width_meters=buffer_meters / 2.0))
            else:
                features.extend(layer_features)
        features = _dedupe_geojson_features(features)
        result.append(
            {
                "category_id": int(config.get("category_id") or 0),
                "category_name": str(config.get("category_name") or ""),
                "feature_type": str(config.get("feature_type") or ""),
                "features": features,
                "label_source": {
                    "source_id": source_id,
                    "source_role": spec["source_role"],
                    "name": spec["name"],
                    "url": spec["source_url"],
                    "license": spec["license"],
                    "license_url": spec["license_url"],
                    "source_rights": _source_rights(spec, registry_fingerprint=registry_fingerprint),
                },
            }
        )
    return result


def _dedupe_geojson_features(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for feature in features:
        geometry = dict(feature.get("geometry") or {})
        if not geometry:
            continue
        fingerprint = hashlib.sha256(
            json.dumps(geometry, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        result.append(feature)
    return result


def _query_arcgis_geojson_features(
    service_url: str,
    layer_id: int,
    bbox: Dict[str, Any],
) -> List[Dict[str, Any]]:
    _require_allowed_https(service_url)
    params = urlencode(
        {
            "f": "geojson",
            "where": "1=1",
            "geometry": f"{bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "outSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "true",
            "resultRecordCount": "5000",
        }
    )
    payload = _download_json(f"{service_url.rstrip('/')}/{layer_id}/query?{params}")
    if payload.get("type") != "FeatureCollection":
        raise SystemExit(f"Approved ArcGIS source layer {layer_id} did not return a GeoJSON FeatureCollection.")
    return [dict(item) for item in payload.get("features") or [] if isinstance(item, dict)]


def _buffer_line_feature(feature: Dict[str, Any], *, half_width_meters: float) -> List[Dict[str, Any]]:
    geometry = dict(feature.get("geometry") or {})
    geometry_type = str(geometry.get("type") or "")
    coordinate_sets = [geometry.get("coordinates") or []]
    if geometry_type == "MultiLineString":
        coordinate_sets = list(geometry.get("coordinates") or [])
    elif geometry_type != "LineString":
        return []
    result: List[Dict[str, Any]] = []
    for coordinates in coordinate_sets:
        points = [
            [float(point[0]), float(point[1])]
            for point in coordinates
            if isinstance(point, (list, tuple)) and len(point) >= 2
        ]
        if len(points) < 2:
            continue
        latitude = sum(point[1] for point in points) / len(points)
        meters_per_degree_lon = max(1.0, 111_320.0 * abs(math.cos(math.radians(latitude))))
        origin_lon, origin_lat = points[0]
        metric_points = [
            ((point[0] - origin_lon) * meters_per_degree_lon, (point[1] - origin_lat) * 111_320.0)
            for point in points
        ]
        segment_normals: List[tuple[float, float]] = []
        for start, end in zip(metric_points, metric_points[1:]):
            dx_m, dy_m = end[0] - start[0], end[1] - start[1]
            length_m = math.hypot(dx_m, dy_m)
            segment_normals.append((-dy_m / length_m, dx_m / length_m) if length_m > 0.01 else (0.0, 0.0))
        vertex_normals: List[tuple[float, float]] = []
        for index in range(len(metric_points)):
            adjacent = []
            if index > 0:
                adjacent.append(segment_normals[index - 1])
            if index < len(segment_normals):
                adjacent.append(segment_normals[index])
            nx, ny = sum(item[0] for item in adjacent), sum(item[1] for item in adjacent)
            normal_length = math.hypot(nx, ny)
            if normal_length <= 0.01:
                nx, ny = next((item for item in adjacent if math.hypot(*item) > 0.01), (0.0, 0.0))
                normal_length = math.hypot(nx, ny)
            vertex_normals.append((nx / normal_length, ny / normal_length) if normal_length > 0.01 else (0.0, 0.0))

        def project(point: tuple[float, float]) -> List[float]:
            return [origin_lon + point[0] / meters_per_degree_lon, origin_lat + point[1] / 111_320.0]

        left = [
            project((point[0] + normal[0] * half_width_meters, point[1] + normal[1] * half_width_meters))
            for point, normal in zip(metric_points, vertex_normals)
        ]
        right = [
            project((point[0] - normal[0] * half_width_meters, point[1] - normal[1] * half_width_meters))
            for point, normal in zip(metric_points, vertex_normals)
        ]
        ring = left + list(reversed(right))
        ring.append(ring[0])
        result.append(
            {
                "type": "Feature",
                "properties": {
                    **dict(feature.get("properties") or {}),
                    "weak_geometry_method": "buffered_centerline_corridor",
                    "half_width_meters": round(half_width_meters, 3),
                },
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        )
    return result


def _annotation_counts_by_class(package: Dict[str, Any]) -> Dict[str, int]:
    category_names = {
        int(item.get("id") or 0): str(item.get("name") or "unknown")
        for item in package.get("categories") or []
        if isinstance(item, dict)
    }
    counts: Dict[str, int] = {}
    for annotation in package.get("annotations") or []:
        if not isinstance(annotation, dict):
            continue
        name = str(
            annotation.get("category_name")
            or category_names.get(int(annotation.get("category_id") or 0))
            or "unknown"
        )
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def _usgs_export_url(
    base_url: str,
    bbox: Dict[str, Any],
    pixels: int,
    *,
    raster_ids: Iterable[int] = (),
) -> str:
    _require_allowed_https(base_url)
    lock_ids = sorted({int(value) for value in raster_ids if int(value) > 0})
    if not lock_ids:
        raise SystemExit("A rights-cleared USGS raster record is required before imagery export.")
    params = urlencode(
        {
            "bbox": f"{bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}",
            "bboxSR": "4326",
            "imageSR": "4326",
            "size": f"{pixels},{pixels}",
            "format": "png",
            "interpolation": "RSP_BilinearInterpolation",
            "mosaicRule": json.dumps(
                {"mosaicMethod": "esriMosaicLockRaster", "lockRasterIds": lock_ids},
                separators=(",", ":"),
            ),
            "f": "image",
        }
    )
    return base_url.rstrip("/") + "/exportImage?" + params


def _query_usgs_catalog(base_url: str, bbox: Dict[str, Any], *, where: str) -> List[Dict[str, Any]]:
    _require_allowed_https(base_url)
    params = urlencode(
        {
            "f": "json",
            "where": where,
            "geometry": f"{bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": (
                "OBJECTID,Category,Name,State,Year,acquisition_date,agency,vendor,resolution_value,"
                "resolution_units,band_count,sensor_type,datum"
            ),
            "returnGeometry": "false",
        }
    )
    payload = _download_json(base_url.rstrip("/") + "/query?" + params)
    if payload.get("error"):
        raise SystemExit("USGS imagery catalog query failed; no fallback imagery was used.")
    return [dict(item.get("attributes") or {}) for item in payload.get("features") or [] if isinstance(item, dict)]


def _select_usgs_records(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    eligible = [
        dict(record)
        for record in records
        if int(record.get("Category") or 0) == 1
        and str(record.get("agency") or "").upper() == "USDA"
        and float(record.get("acquisition_date") or 0) > 0
        and int(record.get("OBJECTID") or 0) > 0
    ]
    if not eligible:
        return []
    latest_capture = max(float(record.get("acquisition_date") or 0) for record in eligible)
    selected = [record for record in eligible if float(record.get("acquisition_date") or 0) == latest_capture]
    return sorted(selected, key=lambda record: int(record.get("OBJECTID") or 0))


def _download_image(url: str, destination: Path) -> None:
    _require_allowed_https(url)
    request = Request(url, headers={"User-Agent": "CivoraVisionBootstrap/1.0 (support@civora.ai)"})
    # URL is restricted to the approved HTTPS host allowlist above.
    with _open_source_request(request, timeout=90) as response:
        content_type = str(response.headers.get("content-type") or "").lower()
        if not content_type.startswith("image/"):
            raise SystemExit(f"Expected an image from {urlsplit(url).hostname}; received {content_type or 'unknown'}.")
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
            shutil.copyfileobj(response, handle)
            temp_path = Path(handle.name)
    temp_path.replace(destination)


def _download_file(url: str, destination: Path) -> None:
    normalized = normalize_microsoft_partition_url(url)
    _require_allowed_https(normalized)
    request = Request(normalized, headers={"User-Agent": "CivoraVisionBootstrap/1.0 (support@civora.ai)"})
    # The normalized URL is restricted to the approved HTTPS host allowlist above.
    with _open_source_request(request, timeout=180) as response, tempfile.NamedTemporaryFile(
        dir=destination.parent,
        delete=False,
    ) as handle:
        shutil.copyfileobj(response, handle)
        temp_path = Path(handle.name)
    temp_path.replace(destination)


def _download_text(url: str) -> str:
    _require_allowed_https(url)
    request = Request(url, headers={"User-Agent": "CivoraVisionBootstrap/1.0 (support@civora.ai)"})
    # URL is restricted to the approved HTTPS host allowlist above.
    with _open_source_request(request, timeout=90) as response:
        return response.read().decode("utf-8-sig")


def _download_json(url: str) -> Dict[str, Any]:
    _require_allowed_https(url)
    request = Request(url, headers={"User-Agent": "CivoraVisionBootstrap/1.0 (support@civora.ai)"})
    # URL is restricted to the approved HTTPS host allowlist above.
    with _open_source_request(request, timeout=90) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise SystemExit("Expected a JSON object from the approved imagery catalog.")
    return value


def _open_source_request(request: Request, *, timeout: float, attempts: int = SOURCE_REQUEST_ATTEMPTS):
    attempt_count = max(1, int(attempts))
    hostname = str(urlsplit(request.full_url).hostname or "approved source")
    for attempt in range(1, attempt_count + 1):
        try:
            # Every caller validates the URL against the approved HTTPS source allowlist before reaching this helper.
            return urlopen(request, timeout=timeout)  # nosec B310
        except HTTPError as exc:
            retryable = exc.code in RETRYABLE_HTTP_STATUS_CODES
            if not retryable or attempt >= attempt_count:
                raise SystemExit(
                    f"Approved source {hostname} returned HTTP {exc.code} after {attempt} attempt"
                    f"{'s' if attempt != 1 else ''}; no fallback source was used."
                ) from exc
        except (URLError, TimeoutError) as exc:
            if attempt >= attempt_count:
                raise SystemExit(
                    f"Approved source {hostname} could not be reached after {attempt_count} attempts; "
                    "no fallback source was used."
                ) from exc
        time.sleep(min(2.0, 0.25 * (2 ** (attempt - 1))))
    raise AssertionError("Source request retry loop exited unexpectedly.")


def _load_source_registry(path: Path) -> tuple[Dict[str, Any], str]:
    registry_path = path.expanduser().resolve()
    try:
        raw = registry_path.read_bytes()
        registry = json.loads(raw.decode("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Vision source registry is missing or invalid: {registry_path}") from exc
    if not isinstance(registry, dict) or registry.get("version") != "civora_vision_public_source_registry_v1":
        raise SystemExit("Unsupported vision public source registry.")
    return registry, hashlib.sha256(raw).hexdigest()


def _source_rights(spec: Dict[str, Any], *, registry_fingerprint: str) -> Dict[str, Any]:
    rights = dict(spec.get("rights") or {})
    required = ("training_use_allowed", "storage_allowed", "derivative_labels_allowed")
    if any(rights.get(key) is not True for key in required):
        raise SystemExit(f"Source registry rights are incomplete for {spec.get('name') or 'source'}.")
    if not str(spec.get("license") or "") or not str(spec.get("license_url") or ""):
        raise SystemExit(f"Source registry license evidence is incomplete for {spec.get('name') or 'source'}.")
    return {
        **rights,
        "license": str(spec.get("license") or ""),
        "license_url": str(spec.get("license_url") or ""),
        "rights_source": str(spec.get("license_url") or ""),
        "rights_registry_fingerprint": registry_fingerprint,
        "rights_review_status": "operational_source_record_not_legal_advice",
    }


def _partition_urls(index_text: str, *, country: str, quadkeys: Iterable[str]) -> List[str]:
    expected = set(quadkeys)
    result = []
    for row in csv.DictReader(io.StringIO(index_text)):
        if row.get("Location") != country or row.get("QuadKey") not in expected:
            continue
        result.append(normalize_microsoft_partition_url(row.get("Url")))
    return sorted(set(result))


def _read_footprints(path: Path, bbox: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            try:
                feature = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(feature, dict) and feature_intersects_bbox(feature, bbox):
                result.append(feature)
    return result


def _require_allowed_https(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_SOURCE_HOSTS:
        raise SystemExit("Bootstrap source URL must use an approved HTTPS USGS or Microsoft host.")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
