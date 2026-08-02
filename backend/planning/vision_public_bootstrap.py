from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .common import safe_dict, safe_float, safe_list, safe_str
from .vision_model_lifecycle import COCO_PACKAGE_VERSION


PUBLIC_BOOTSTRAP_VERSION = "civora_public_vision_bootstrap_v1"
WEAK_SUPERVISION_STATUS = "weak_labels_pending_review"
REVIEWED_SUPERVISION_STATUS = "reviewer_labeled"


def quadkey_for_point(longitude: float, latitude: float, *, level: int = 9) -> str:
    tile_x, tile_y = _tile_coordinates_for_point(longitude, latitude, level=level)
    return _quadkey_for_tile(tile_x, tile_y, level=level)


def quadkeys_for_bbox(bbox: Dict[str, Any], *, level: int = 9) -> List[str]:
    bounds = normalize_bbox(bbox)
    if not bounds:
        return []
    west_x, north_y = _tile_coordinates_for_point(bounds["west"], bounds["north"], level=level)
    east_x, south_y = _tile_coordinates_for_point(bounds["east"], bounds["south"], level=level)
    tile_count = (east_x - west_x + 1) * (south_y - north_y + 1)
    if tile_count > 4096:
        raise ValueError("Bootstrap region spans too many building-footprint partitions; divide it into smaller regions.")
    return sorted(
        _quadkey_for_tile(tile_x, tile_y, level=level)
        for tile_x in range(west_x, east_x + 1)
        for tile_y in range(north_y, south_y + 1)
    )


def build_geographic_tile_grid(
    *,
    center_longitude: float,
    center_latitude: float,
    rows: int,
    columns: int,
    tile_meters: float,
    image_pixels: int,
) -> List[Dict[str, Any]]:
    rows = max(1, int(rows))
    columns = max(1, int(columns))
    tile_meters = max(10.0, float(tile_meters))
    image_pixels = max(32, int(image_pixels))
    latitude_radians = math.radians(float(center_latitude))
    latitude_span = tile_meters / 111_320.0
    longitude_span = tile_meters / max(111_320.0 * math.cos(latitude_radians), 1.0)
    west_origin = float(center_longitude) - columns * longitude_span / 2
    south_origin = float(center_latitude) - rows * latitude_span / 2
    tiles: List[Dict[str, Any]] = []
    for row in range(rows):
        for column in range(columns):
            west = west_origin + column * longitude_span
            east = west + longitude_span
            south = south_origin + row * latitude_span
            north = south + latitude_span
            frame_seed = f"{west:.9f},{south:.9f},{east:.9f},{north:.9f},{image_pixels}"
            frame_id = f"public_naip_{hashlib.sha256(frame_seed.encode('utf-8')).hexdigest()[:16]}"
            tiles.append(
                {
                    "frame_id": frame_id,
                    "row": row,
                    "column": column,
                    "bbox_wgs84": {
                        "west": round(west, 9),
                        "south": round(south, 9),
                        "east": round(east, 9),
                        "north": round(north, 9),
                    },
                    "width": image_pixels,
                    "height": image_pixels,
                    "file_name": f"naip-r{row:02d}-c{column:02d}.png",
                }
            )
    _assign_balanced_splits(tiles)
    return tiles


def normalize_microsoft_partition_url(value: Any) -> str:
    url = safe_str(value)
    legacy = "https://bfppub.z5.web.core.windows.net/"
    if url.startswith(legacy):
        return "https://bfppub.blob.core.windows.net/%24web/" + url[len(legacy) :]
    return url


def feature_intersects_bbox(feature: Dict[str, Any], bbox: Dict[str, Any]) -> bool:
    bounds = normalize_bbox(bbox)
    feature_bounds = geometry_bbox(safe_dict(feature).get("geometry"))
    return bool(bounds and feature_bounds and not (
        feature_bounds["east"] < bounds["west"]
        or feature_bounds["west"] > bounds["east"]
        or feature_bounds["north"] < bounds["south"]
        or feature_bounds["south"] > bounds["north"]
    ))


def build_weak_supervision_package(
    *,
    tiles: Sequence[Dict[str, Any]],
    footprint_features: Iterable[Dict[str, Any]],
    imagery_source: Dict[str, Any],
    label_source: Dict[str, Any],
) -> Dict[str, Any]:
    normalized_tiles = [dict(tile) for tile in tiles]
    features = [safe_dict(feature) for feature in footprint_features if safe_dict(feature)]
    images: List[Dict[str, Any]] = []
    annotations: List[Dict[str, Any]] = []
    review_features: List[Dict[str, Any]] = []
    annotation_id = 1
    for image_id, tile in enumerate(normalized_tiles, start=1):
        bbox = normalize_bbox(tile.get("bbox_wgs84"))
        if not bbox:
            continue
        images.append(
            {
                "id": image_id,
                "file_name": safe_str(tile.get("file_name")),
                "width": int(safe_float(tile.get("width"))),
                "height": int(safe_float(tile.get("height"))),
                "imagery_frame_id": safe_str(tile.get("frame_id")),
                "source_sha256": safe_str(tile.get("sha256")),
                "split": safe_str(tile.get("split"), "train"),
                "bbox_wgs84": bbox,
                "source_rights": safe_dict(imagery_source.get("source_rights")),
            }
        )
        for feature in features:
            if not feature_intersects_bbox(feature, bbox):
                continue
            for ring in geometry_exterior_rings(feature.get("geometry")):
                clipped = clip_ring_to_bbox(ring, bbox)
                if len(clipped) < 4:
                    continue
                pixel_ring = wgs84_ring_to_pixels(
                    clipped,
                    bbox,
                    width=int(safe_float(tile.get("width"))),
                    height=int(safe_float(tile.get("height"))),
                )
                segmentation, pixel_bbox, area = coco_polygon(pixel_ring)
                if not segmentation or area < 4.0:
                    continue
                annotations.append(
                    {
                        "id": annotation_id,
                        "image_id": image_id,
                        "category_id": 1,
                        "segmentation": segmentation,
                        "bbox": pixel_bbox,
                        "area": area,
                        "iscrowd": 0,
                        "supervision": WEAK_SUPERVISION_STATUS,
                        "label_source": safe_str(label_source.get("name")),
                        "label_license": safe_str(label_source.get("license")),
                        "review_status": "pending",
                        "geo_geometry": {"type": "Polygon", "coordinates": [clipped]},
                    }
                )
                review_features.append(
                    {
                        "type": "Feature",
                        "id": annotation_id,
                        "properties": {
                            "annotation_id": annotation_id,
                            "image_id": image_id,
                            "tile_file": safe_str(tile.get("file_name")),
                            "feature_type": "building",
                            "review_status": "pending",
                            "supervision": WEAK_SUPERVISION_STATUS,
                        },
                        "geometry": {"type": "Polygon", "coordinates": [clipped]},
                    }
                )
                annotation_id += 1
    package: Dict[str, Any] = {
        "version": COCO_PACKAGE_VERSION,
        "bootstrap_version": PUBLIC_BOOTSTRAP_VERSION,
        "generated_at": now_iso(),
        "info": {
            "description": "Public-domain aerial imagery with separately licensed weak building labels.",
            "contains_image_bytes": False,
            "supervision_status": WEAK_SUPERVISION_STATUS,
        },
        "licenses": [
            {"id": 1, **safe_dict(imagery_source)},
            {"id": 2, **safe_dict(label_source)},
        ],
        "categories": [{"id": 1, "name": "building", "source_feature_type": "building_footprint"}],
        "images": images,
        "annotations": annotations,
        "splits": {
            split: [image["id"] for image in images if image.get("split") == split]
            for split in ("train", "validation", "test")
        },
        "eligible_image_count": len(images),
        "annotation_count": len(annotations),
        "contains_image_bytes": False,
        "supervision_status": WEAK_SUPERVISION_STATUS,
        "promotion_eligible": False,
        "promotion_blockers": [
            "weak_labels_require_image_by_image_review",
            "independent_reviewed_ground_truth_evaluation_missing",
            "single_geography_bootstrap_does_not_prove_generalization",
        ],
        "review_candidates": {"type": "FeatureCollection", "features": review_features},
        "truth_label": (
            "These Microsoft-derived footprints are weak labels aligned to public USGS imagery. They may bootstrap "
            "training, but they are not reviewed ground truth and cannot promote a production model."
        ),
    }
    package["dataset_fingerprint"] = stable_fingerprint(
        {
            "categories": package["categories"],
            "images": images,
            "annotations": annotations,
            "splits": package["splits"],
            "supervision_status": package["supervision_status"],
        }
    )
    return package


def merge_weak_supervision_packages(
    packages: Sequence[Dict[str, Any]],
    *,
    source_names: Sequence[str],
) -> Dict[str, Any]:
    if not packages or len(packages) != len(source_names):
        raise ValueError("Each weak-supervision package requires a source name.")
    merged_images: List[Dict[str, Any]] = []
    merged_annotations: List[Dict[str, Any]] = []
    review_features: List[Dict[str, Any]] = []
    source_datasets: List[Dict[str, Any]] = []
    licenses: List[Dict[str, Any]] = []
    license_keys: set[Tuple[str, str, str]] = set()
    categories: List[Dict[str, Any]] = []
    next_image_id = 1
    next_annotation_id = 1
    for source_name, raw_package in zip(source_names, packages):
        package = safe_dict(raw_package)
        if safe_str(package.get("version")) != COCO_PACKAGE_VERSION:
            raise ValueError(f"{source_name} is not a Civora COCO package.")
        if safe_str(package.get("supervision_status")) != WEAK_SUPERVISION_STATUS:
            raise ValueError(f"{source_name} is not a weak-supervision bootstrap package.")
        if package.get("promotion_eligible") is not False:
            raise ValueError(f"{source_name} must remain promotion-ineligible before review.")
        package_categories = [safe_dict(item) for item in safe_list(package.get("categories"))]
        if not categories:
            categories = package_categories
        elif package_categories != categories:
            raise ValueError("Weak-supervision packages use incompatible category contracts.")
        image_id_map: Dict[int, int] = {}
        for raw_image in safe_list(package.get("images")):
            image = safe_dict(raw_image)
            old_id = int(safe_float(image.get("id")))
            image_id_map[old_id] = next_image_id
            merged_images.append(
                {
                    **image,
                    "id": next_image_id,
                    "source_image_id": old_id,
                    "source_dataset": source_name,
                }
            )
            next_image_id += 1
        for raw_annotation in safe_list(package.get("annotations")):
            annotation = safe_dict(raw_annotation)
            old_image_id = int(safe_float(annotation.get("image_id")))
            if old_image_id not in image_id_map:
                continue
            old_annotation_id = int(safe_float(annotation.get("id")))
            merged = {
                **annotation,
                "id": next_annotation_id,
                "image_id": image_id_map[old_image_id],
                "source_annotation_id": old_annotation_id,
                "source_dataset": source_name,
            }
            merged_annotations.append(merged)
            geo_geometry = safe_dict(annotation.get("geo_geometry"))
            if geo_geometry:
                review_features.append(
                    {
                        "type": "Feature",
                        "id": next_annotation_id,
                        "properties": {
                            "annotation_id": next_annotation_id,
                            "image_id": image_id_map[old_image_id],
                            "feature_type": "building",
                            "review_status": "pending",
                            "supervision": WEAK_SUPERVISION_STATUS,
                            "source_dataset": source_name,
                        },
                        "geometry": geo_geometry,
                    }
                )
            next_annotation_id += 1
        for raw_license in safe_list(package.get("licenses")):
            license_rec = safe_dict(raw_license)
            key = (
                safe_str(license_rec.get("name")),
                safe_str(license_rec.get("license")),
                safe_str(license_rec.get("url")),
            )
            if key in license_keys:
                continue
            license_keys.add(key)
            licenses.append({**license_rec, "id": len(licenses) + 1})
        source_datasets.append(
            {
                "name": source_name,
                "dataset_fingerprint": safe_str(package.get("dataset_fingerprint")),
                "source_region_bbox_wgs84": safe_dict(package.get("source_region_bbox_wgs84")),
                "image_count": len(safe_list(package.get("images"))),
                "annotation_count": len(safe_list(package.get("annotations"))),
            }
        )
    payload: Dict[str, Any] = {
        "version": COCO_PACKAGE_VERSION,
        "bootstrap_version": PUBLIC_BOOTSTRAP_VERSION,
        "generated_at": now_iso(),
        "info": {
            "description": "Multi-geography public imagery with separately licensed weak building labels.",
            "contains_image_bytes": False,
            "supervision_status": WEAK_SUPERVISION_STATUS,
        },
        "licenses": licenses,
        "categories": categories,
        "images": merged_images,
        "annotations": merged_annotations,
        "splits": {
            split: [image["id"] for image in merged_images if image.get("split") == split]
            for split in ("train", "validation", "test")
        },
        "eligible_image_count": len(merged_images),
        "annotation_count": len(merged_annotations),
        "contains_image_bytes": False,
        "supervision_status": WEAK_SUPERVISION_STATUS,
        "promotion_eligible": False,
        "promotion_blockers": [
            "weak_labels_require_image_by_image_review",
            "independent_reviewed_ground_truth_evaluation_missing",
            "multi_geography_generalization_not_measured",
        ],
        "source_datasets": source_datasets,
        "review_candidates": {"type": "FeatureCollection", "features": review_features},
        "truth_label": (
            "This merged corpus can bootstrap diagnostic training across multiple geographies. Its labels remain weak, "
            "pending human review, and ineligible for production model promotion."
        ),
    }
    payload["dataset_fingerprint"] = stable_fingerprint(
        {
            "categories": categories,
            "images": merged_images,
            "annotations": merged_annotations,
            "splits": payload["splits"],
            "source_datasets": source_datasets,
            "supervision_status": WEAK_SUPERVISION_STATUS,
        }
    )
    return payload


def geometry_exterior_rings(geometry: Any) -> List[List[List[float]]]:
    rec = safe_dict(geometry)
    geometry_type = safe_str(rec.get("type"))
    coordinates = safe_list(rec.get("coordinates"))
    if geometry_type == "Polygon" and coordinates:
        return [_numeric_ring(coordinates[0])]
    if geometry_type == "MultiPolygon":
        return [_numeric_ring(safe_list(polygon)[0]) for polygon in coordinates if safe_list(polygon)]
    return []


def geometry_bbox(geometry: Any) -> Dict[str, float]:
    points = [point for ring in geometry_exterior_rings(geometry) for point in ring]
    if not points:
        return {}
    return {
        "west": min(point[0] for point in points),
        "south": min(point[1] for point in points),
        "east": max(point[0] for point in points),
        "north": max(point[1] for point in points),
    }


def clip_ring_to_bbox(ring: Sequence[Sequence[float]], bbox: Dict[str, Any]) -> List[List[float]]:
    bounds = normalize_bbox(bbox)
    points = _numeric_ring(ring)
    if not bounds or len(points) < 3:
        return []
    if points[0] == points[-1]:
        points = points[:-1]

    def clip(
        values: List[List[float]],
        inside: Any,
        intersect: Any,
    ) -> List[List[float]]:
        if not values:
            return []
        output: List[List[float]] = []
        previous = values[-1]
        previous_inside = inside(previous)
        for current in values:
            current_inside = inside(current)
            if current_inside:
                if not previous_inside:
                    output.append(intersect(previous, current))
                output.append(current)
            elif previous_inside:
                output.append(intersect(previous, current))
            previous, previous_inside = current, current_inside
        return output

    def vertical(a: Sequence[float], b: Sequence[float], x: float) -> List[float]:
        delta = b[0] - a[0]
        ratio = 0.0 if abs(delta) < 1e-15 else (x - a[0]) / delta
        return [x, a[1] + ratio * (b[1] - a[1])]

    def horizontal(a: Sequence[float], b: Sequence[float], y: float) -> List[float]:
        delta = b[1] - a[1]
        ratio = 0.0 if abs(delta) < 1e-15 else (y - a[1]) / delta
        return [a[0] + ratio * (b[0] - a[0]), y]

    points = clip(points, lambda p: p[0] >= bounds["west"], lambda a, b: vertical(a, b, bounds["west"]))
    points = clip(points, lambda p: p[0] <= bounds["east"], lambda a, b: vertical(a, b, bounds["east"]))
    points = clip(points, lambda p: p[1] >= bounds["south"], lambda a, b: horizontal(a, b, bounds["south"]))
    points = clip(points, lambda p: p[1] <= bounds["north"], lambda a, b: horizontal(a, b, bounds["north"]))
    if len(points) < 3:
        return []
    cleaned: List[List[float]] = []
    for point in points:
        normalized = [round(float(point[0]), 9), round(float(point[1]), 9)]
        if not cleaned or normalized != cleaned[-1]:
            cleaned.append(normalized)
    if len(cleaned) < 3:
        return []
    if cleaned[0] != cleaned[-1]:
        cleaned.append(cleaned[0])
    return cleaned


def wgs84_ring_to_pixels(
    ring: Sequence[Sequence[float]],
    bbox: Dict[str, Any],
    *,
    width: int,
    height: int,
) -> List[List[float]]:
    bounds = normalize_bbox(bbox)
    if not bounds or width <= 0 or height <= 0:
        return []
    result = []
    for longitude, latitude in _numeric_ring(ring):
        x = (longitude - bounds["west"]) / (bounds["east"] - bounds["west"]) * width
        y = (bounds["north"] - latitude) / (bounds["north"] - bounds["south"]) * height
        result.append([round(min(max(x, 0.0), width), 4), round(min(max(y, 0.0), height), 4)])
    return result


def coco_polygon(ring: Sequence[Sequence[float]]) -> Tuple[List[List[float]], List[float], float]:
    points = _numeric_ring(ring)
    if len(points) < 3:
        return [], [], 0.0
    if points[0] != points[-1]:
        points.append(points[0])
    flat = [round(value, 4) for point in points[:-1] for value in point[:2]]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    bbox = [round(min(xs), 4), round(min(ys), 4), round(max(xs) - min(xs), 4), round(max(ys) - min(ys), 4)]
    area = abs(
        sum(points[index][0] * points[index + 1][1] - points[index + 1][0] * points[index][1] for index in range(len(points) - 1))
    ) / 2.0
    return [flat], bbox, round(area, 4)


def normalize_bbox(value: Any) -> Dict[str, float]:
    rec = safe_dict(value)
    if not rec:
        return {}
    result = {
        "west": safe_float(rec.get("west")),
        "south": safe_float(rec.get("south")),
        "east": safe_float(rec.get("east")),
        "north": safe_float(rec.get("north")),
    }
    if result["east"] <= result["west"] or result["north"] <= result["south"]:
        return {}
    return result


def stable_fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _numeric_ring(value: Any) -> List[List[float]]:
    result: List[List[float]] = []
    for point in safe_list(value):
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            longitude = float(point[0])
            latitude = float(point[1])
        except (TypeError, ValueError):
            continue
        if math.isfinite(longitude) and math.isfinite(latitude):
            result.append([longitude, latitude])
    return result


def _tile_coordinates_for_point(longitude: float, latitude: float, *, level: int) -> Tuple[int, int]:
    normalized_level = max(1, int(level))
    latitude = min(max(float(latitude), -85.05112878), 85.05112878)
    longitude = min(max(float(longitude), -180.0), 180.0)
    size = 1 << normalized_level
    tile_x = min(size - 1, max(0, int((longitude + 180.0) / 360.0 * size)))
    sin_latitude = math.sin(math.radians(latitude))
    tile_y = min(
        size - 1,
        max(0, int((0.5 - math.log((1 + sin_latitude) / (1 - sin_latitude)) / (4 * math.pi)) * size)),
    )
    return tile_x, tile_y


def _quadkey_for_tile(tile_x: int, tile_y: int, *, level: int) -> str:
    digits: List[str] = []
    for index in range(max(1, int(level)), 0, -1):
        mask = 1 << (index - 1)
        digit = (1 if tile_x & mask else 0) + (2 if tile_y & mask else 0)
        digits.append(str(digit))
    return "".join(digits)


def _assign_balanced_splits(tiles: List[Dict[str, Any]]) -> None:
    ordered = sorted(
        tiles,
        key=lambda item: hashlib.sha256(safe_str(item.get("frame_id")).encode("utf-8")).hexdigest(),
    )
    count = len(ordered)
    if count < 3:
        for item in ordered:
            item["split"] = "train"
        return
    validation_count = max(1, round(count * 0.15))
    test_count = max(1, round(count * 0.15))
    if validation_count + test_count >= count:
        validation_count = test_count = 1
    for index, item in enumerate(ordered):
        if index < validation_count:
            item["split"] = "validation"
        elif index < validation_count + test_count:
            item["split"] = "test"
        else:
            item["split"] = "train"


__all__ = [
    "PUBLIC_BOOTSTRAP_VERSION",
    "REVIEWED_SUPERVISION_STATUS",
    "WEAK_SUPERVISION_STATUS",
    "build_geographic_tile_grid",
    "build_weak_supervision_package",
    "clip_ring_to_bbox",
    "coco_polygon",
    "feature_intersects_bbox",
    "geometry_bbox",
    "geometry_exterior_rings",
    "merge_weak_supervision_packages",
    "normalize_bbox",
    "normalize_microsoft_partition_url",
    "quadkey_for_point",
    "quadkeys_for_bbox",
    "stable_fingerprint",
    "wgs84_ring_to_pixels",
]
