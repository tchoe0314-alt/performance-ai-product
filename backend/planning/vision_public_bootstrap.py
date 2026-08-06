from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .common import safe_dict, safe_float, safe_list, safe_str
from .vision_detection_learning import build_imagery_frame_v2
from .vision_model_lifecycle import COCO_PACKAGE_VERSION


PUBLIC_BOOTSTRAP_VERSION = "civora_public_vision_bootstrap_v1"
WEAK_SUPERVISION_STATUS = "weak_labels_pending_review"
REVIEWED_SUPERVISION_STATUS = "reviewer_labeled"
REVIEW_SPRINT_VERSION = "civora_public_vision_review_sprint_v1"
VISION_DATASET_SPLITS = ("train", "validation", "test")


def capture_date_from_epoch_ms(value: Any) -> str:
    milliseconds = safe_float(value)
    if milliseconds <= 0:
        return ""
    try:
        return datetime.fromtimestamp(milliseconds / 1000.0, tz=timezone.utc).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return ""


def capture_season(value: Any) -> str:
    text = safe_str(value)
    if not text:
        return ""
    try:
        month = datetime.fromisoformat(text.replace("Z", "+00:00")).month
    except ValueError:
        return ""
    if month in {12, 1, 2}:
        return "winter"
    if month in {3, 4, 5}:
        return "spring"
    if month in {6, 7, 8}:
        return "summer"
    return "autumn"


def imagery_quality_band(resolution_meters: Any) -> str:
    resolution = safe_float(resolution_meters)
    if resolution <= 0:
        return "unknown"
    if resolution <= 0.3:
        return "high_resolution_0_30m_or_better"
    if resolution <= 0.6:
        return "medium_resolution_0_31m_to_0_60m"
    if resolution <= 1.0:
        return "standard_resolution_0_61m_to_1_00m"
    return "low_resolution_over_1_00m"


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
    permanent_split: str = "",
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
    split = safe_str(permanent_split).lower()
    if split:
        if split not in VISION_DATASET_SPLITS:
            raise ValueError("Permanent vision split must be train, validation, or test.")
        for tile in tiles:
            tile["split"] = split
    else:
        _assign_balanced_splits(tiles)
    return tiles


def build_split_integrity(
    images: Sequence[Dict[str, Any]],
    *,
    grouping_field: str = "geography_id",
    required_splits: Sequence[str] = (),
) -> Dict[str, Any]:
    required = [safe_str(item).lower() for item in required_splits if safe_str(item)]
    invalid_required = sorted(set(required) - set(VISION_DATASET_SPLITS))
    groups_by_split: Dict[str, List[str]] = {split: [] for split in VISION_DATASET_SPLITS}
    image_counts_by_split: Dict[str, int] = {split: 0 for split in VISION_DATASET_SPLITS}
    group_splits: Dict[str, set[str]] = {}
    ungrouped_image_ids: List[int] = []
    invalid_split_image_ids: List[int] = []
    for image in images:
        rec = safe_dict(image)
        image_id = int(safe_float(rec.get("id")))
        split = safe_str(rec.get("split")).lower()
        if split not in VISION_DATASET_SPLITS:
            invalid_split_image_ids.append(image_id)
            continue
        image_counts_by_split[split] += 1
        group = safe_str(rec.get(grouping_field))
        if not group:
            ungrouped_image_ids.append(image_id)
            continue
        group_splits.setdefault(group, set()).add(split)
    leaked_groups = sorted(group for group, splits in group_splits.items() if len(splits) > 1)
    for split in VISION_DATASET_SPLITS:
        groups_by_split[split] = sorted(group for group, splits in group_splits.items() if split in splits)
    missing_required = sorted(split for split in required if image_counts_by_split.get(split, 0) <= 0)
    blockers: List[str] = []
    if invalid_required:
        blockers.append("split_policy_contains_invalid_required_split")
    if invalid_split_image_ids:
        blockers.append("images_have_invalid_or_missing_split")
    if ungrouped_image_ids:
        blockers.append("images_missing_split_group")
    if leaked_groups:
        blockers.append("split_group_leakage_detected")
    if missing_required:
        blockers.append("required_dataset_split_missing")
    return {
        "version": "civora_vision_split_integrity_v1",
        "strategy": "group_disjoint",
        "grouping_field": grouping_field,
        "required_splits": required,
        "image_counts_by_split": image_counts_by_split,
        "groups_by_split": groups_by_split,
        "leaked_groups": leaked_groups,
        "missing_required_splits": missing_required,
        "ungrouped_image_ids": sorted(ungrouped_image_ids),
        "invalid_split_image_ids": sorted(invalid_split_image_ids),
        "valid": not blockers,
        "blockers": blockers,
    }


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
                "source_url": safe_str(tile.get("source_url")),
                "source_item_ids": [safe_str(item) for item in safe_list(tile.get("source_item_ids")) if safe_str(item)],
                "source_item_names": [safe_str(item) for item in safe_list(tile.get("source_item_names")) if safe_str(item)],
                "geography_id": safe_str(tile.get("geography_id")),
                "capture_date": safe_str(tile.get("capture_date")),
                "capture_year": int(safe_float(tile.get("capture_year"))) if tile.get("capture_year") not in (None, "") else None,
                "season": safe_str(tile.get("season")),
                "imagery_quality_band": safe_str(tile.get("imagery_quality_band")),
                "resolution_meters": safe_float(tile.get("resolution_meters")) or None,
                "source_agency": safe_str(tile.get("source_agency")),
                "source_vendor": safe_str(tile.get("source_vendor")),
                "sensor_type": safe_str(tile.get("sensor_type")),
                "datum": safe_str(tile.get("datum")),
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
                        "source_confidence": (
                            round(min(max(safe_float(safe_dict(feature.get("properties")).get("confidence")), 0.0), 1.0), 4)
                            if safe_dict(feature.get("properties")).get("confidence") not in (None, "")
                            else None
                        ),
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
                            "imagery_frame_id": safe_str(tile.get("frame_id")),
                            "capture_date": safe_str(tile.get("capture_date")),
                            "season": safe_str(tile.get("season")),
                            "imagery_quality_band": safe_str(tile.get("imagery_quality_band")),
                        },
                        "geometry": {"type": "Polygon", "coordinates": [clipped]},
                    }
                )
                annotation_id += 1
    licenses = [
        {"id": 1, **safe_dict(imagery_source)},
        {"id": 2, **safe_dict(label_source)},
    ]
    registry_fingerprints = sorted(
        {
            safe_str(safe_dict(item.get("source_rights")).get("rights_registry_fingerprint"))
            for item in licenses
            if safe_str(safe_dict(item.get("source_rights")).get("rights_registry_fingerprint"))
        }
    )
    package: Dict[str, Any] = {
        "version": COCO_PACKAGE_VERSION,
        "bootstrap_version": PUBLIC_BOOTSTRAP_VERSION,
        "generated_at": now_iso(),
        "info": {
            "description": "Public-domain aerial imagery with separately licensed weak building labels.",
            "contains_image_bytes": False,
            "supervision_status": WEAK_SUPERVISION_STATUS,
        },
        "licenses": licenses,
        "source_registry_fingerprints": registry_fingerprints,
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
    package["dataset_fingerprint"] = weak_supervision_package_fingerprint(package)
    return package


def merge_weak_supervision_packages(
    packages: Sequence[Dict[str, Any]],
    *,
    source_names: Sequence[str],
    split_policy: Dict[str, Any] | None = None,
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
        validation = verify_weak_supervision_package(package)
        if not validation["valid"]:
            raise ValueError(
                f"{source_name} failed weak-supervision verification: "
                + ", ".join(validation["blockers"])
            )
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
    registry_fingerprints = sorted(
        {
            safe_str(safe_dict(item.get("source_rights")).get("rights_registry_fingerprint"))
            for item in licenses
            if safe_str(safe_dict(item.get("source_rights")).get("rights_registry_fingerprint"))
        }
    )
    normalized_split_policy = safe_dict(split_policy)
    split_integrity = build_split_integrity(
        merged_images,
        grouping_field=safe_str(normalized_split_policy.get("grouping_field"), "geography_id"),
        required_splits=safe_list(normalized_split_policy.get("required_splits")),
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
        "source_registry_fingerprints": registry_fingerprints,
        "categories": categories,
        "images": merged_images,
        "annotations": merged_annotations,
        "splits": {
            split: [image["id"] for image in merged_images if image.get("split") == split]
            for split in VISION_DATASET_SPLITS
        },
        "split_policy": normalized_split_policy,
        "split_integrity": split_integrity,
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
    payload["dataset_fingerprint"] = weak_supervision_package_fingerprint(payload)
    return payload


def verify_weak_supervision_package(package: Dict[str, Any]) -> Dict[str, Any]:
    rec = safe_dict(package)
    blockers: List[str] = []
    if safe_str(rec.get("version")) != COCO_PACKAGE_VERSION:
        blockers.append("unsupported_coco_package_version")
    if safe_str(rec.get("bootstrap_version")) != PUBLIC_BOOTSTRAP_VERSION:
        blockers.append("unsupported_public_bootstrap_version")
    if safe_str(rec.get("supervision_status")) != WEAK_SUPERVISION_STATUS:
        blockers.append("package_is_not_weak_supervision")
    if rec.get("promotion_eligible") is not False:
        blockers.append("weak_package_must_be_promotion_ineligible")
    images = [safe_dict(item) for item in safe_list(rec.get("images")) if safe_dict(item)]
    annotations = [safe_dict(item) for item in safe_list(rec.get("annotations")) if safe_dict(item)]
    licenses = [safe_dict(item) for item in safe_list(rec.get("licenses")) if safe_dict(item)]
    source_roles = {safe_str(item.get("source_role")) for item in licenses if safe_str(item.get("source_role"))}
    if "training_imagery" not in source_roles:
        blockers.append("training_imagery_license_record_missing")
    if "weak_label_proposals_only" not in source_roles:
        blockers.append("weak_label_license_record_missing")
    registry_fingerprints = sorted(
        {
            safe_str(safe_dict(item.get("source_rights")).get("rights_registry_fingerprint"))
            for item in licenses
            if safe_str(safe_dict(item.get("source_rights")).get("rights_registry_fingerprint"))
        }
    )
    if not registry_fingerprints:
        blockers.append("source_rights_registry_fingerprint_missing")
    if registry_fingerprints != sorted(
        safe_str(item) for item in safe_list(rec.get("source_registry_fingerprints")) if safe_str(item)
    ):
        blockers.append("source_rights_registry_fingerprint_mismatch")
    for license_record in licenses:
        rights = safe_dict(license_record.get("source_rights"))
        if not safe_str(license_record.get("license")) or not safe_str(license_record.get("license_url")):
            blockers.append("source_license_evidence_missing")
        if safe_str(rights.get("license")) != safe_str(license_record.get("license")):
            blockers.append("source_rights_license_mismatch")
        for right_name in ("training_use_allowed", "storage_allowed", "derivative_labels_allowed"):
            if rights.get(right_name) is not True:
                blockers.append(f"source_{right_name}_not_confirmed")
    image_ids = {int(safe_float(item.get("id"))) for item in images}
    frame_ids = [safe_str(item.get("imagery_frame_id")) for item in images]
    if not images:
        blockers.append("imagery_frames_missing")
    if len(frame_ids) != len(set(frame_ids)) or any(not item for item in frame_ids):
        blockers.append("imagery_frame_ids_missing_or_duplicate")
    for image in images:
        rights = safe_dict(image.get("source_rights"))
        if not safe_str(image.get("source_sha256")):
            blockers.append("imagery_source_sha256_missing")
        if not safe_dict(image.get("bbox_wgs84")):
            blockers.append("imagery_bbox_missing")
        if rights.get("training_use_allowed") is not True:
            blockers.append("imagery_training_rights_not_confirmed")
        if rights.get("storage_allowed") is not True:
            blockers.append("imagery_storage_rights_not_confirmed")
        if rights.get("derivative_labels_allowed") is not True:
            blockers.append("imagery_derivative_label_rights_not_confirmed")
        if not safe_str(rights.get("license")):
            blockers.append("imagery_license_missing")
    for annotation in annotations:
        if int(safe_float(annotation.get("image_id"))) not in image_ids:
            blockers.append("annotation_image_missing")
        if safe_str(annotation.get("review_status"), "pending") != "pending":
            blockers.append("weak_annotation_must_start_pending")
        if safe_str(annotation.get("supervision")) != WEAK_SUPERVISION_STATUS:
            blockers.append("weak_annotation_supervision_mismatch")
    split_policy = safe_dict(rec.get("split_policy"))
    if split_policy:
        expected_integrity = build_split_integrity(
            images,
            grouping_field=safe_str(split_policy.get("grouping_field"), "geography_id"),
            required_splits=safe_list(split_policy.get("required_splits")),
        )
        if safe_dict(rec.get("split_integrity")) != expected_integrity:
            blockers.append("split_integrity_report_mismatch")
        blockers.extend(expected_integrity["blockers"])
    expected_fingerprint = weak_supervision_package_fingerprint(rec)
    if safe_str(rec.get("dataset_fingerprint")) != expected_fingerprint:
        blockers.append("weak_dataset_fingerprint_mismatch")
    return {
        "valid": not blockers,
        "blockers": sorted(set(blockers)),
        "dataset_fingerprint": expected_fingerprint,
        "image_count": len(images),
        "annotation_count": len(annotations),
    }


def weak_supervision_package_fingerprint(package: Dict[str, Any]) -> str:
    rec = safe_dict(package)
    fingerprint_payload: Dict[str, Any] = {
        "categories": safe_list(rec.get("categories")),
        "licenses": [safe_dict(item) for item in safe_list(rec.get("licenses")) if safe_dict(item)],
        "images": [safe_dict(item) for item in safe_list(rec.get("images")) if safe_dict(item)],
        "annotations": [safe_dict(item) for item in safe_list(rec.get("annotations")) if safe_dict(item)],
        "splits": safe_dict(rec.get("splits")),
        "split_policy": safe_dict(rec.get("split_policy")),
        "split_integrity": safe_dict(rec.get("split_integrity")),
        "source_registry_fingerprints": safe_list(rec.get("source_registry_fingerprints")),
        "supervision_status": safe_str(rec.get("supervision_status")),
    }
    if safe_list(rec.get("source_datasets")):
        fingerprint_payload["source_datasets"] = safe_list(rec.get("source_datasets"))
    return stable_fingerprint(fingerprint_payload)


def build_public_review_sprint(package: Dict[str, Any]) -> Dict[str, Any]:
    validation = verify_weak_supervision_package(package)
    if not validation["valid"]:
        raise ValueError("Public vision package failed verification: " + ", ".join(validation["blockers"]))
    rec = safe_dict(package)
    images = [safe_dict(item) for item in safe_list(rec.get("images")) if safe_dict(item)]
    image_by_id = {int(safe_float(item.get("id"))): item for item in images}
    frames: List[Dict[str, Any]] = []
    frame_by_image_id: Dict[int, Dict[str, Any]] = {}
    for image in images:
        image_id = int(safe_float(image.get("id")))
        frame = build_imagery_frame_v2(
            {
                "bbox": safe_dict(image.get("bbox_wgs84")),
                "geography_id": safe_str(image.get("geography_id") or image.get("source_dataset")),
                "imagery_date": safe_str(image.get("capture_date")),
                "imagery_season": safe_str(image.get("season")),
                "imagery_quality_band": safe_str(image.get("imagery_quality_band")),
            },
            source_url=safe_str(image.get("source_url")),
            provider=safe_str(image.get("source_agency"), "USGS_NAIP"),
            image_width=image.get("width"),
            image_height=image.get("height"),
            source_rights=safe_dict(image.get("source_rights")),
        )
        frame["frame_id"] = safe_str(image.get("imagery_frame_id"))
        frame["source_fingerprint_sha256"] = safe_str(image.get("source_sha256"))
        frame["permanent_split"] = safe_str(image.get("split"))
        frame["source_item_ids"] = [safe_str(item) for item in safe_list(image.get("source_item_ids")) if safe_str(item)]
        frame["source_item_names"] = [safe_str(item) for item in safe_list(image.get("source_item_names")) if safe_str(item)]
        frame["resolution_meters"] = image.get("resolution_meters")
        frame["source_asset"] = {
            "file_name": safe_str(image.get("file_name")),
            "sha256": safe_str(image.get("source_sha256")),
        }
        frames.append(frame)
        frame_by_image_id[image_id] = frame

    detections: List[Dict[str, Any]] = []
    feature_candidates: List[Dict[str, Any]] = []
    for annotation in [safe_dict(item) for item in safe_list(rec.get("annotations")) if safe_dict(item)]:
        image_id = int(safe_float(annotation.get("image_id")))
        frame = frame_by_image_id.get(image_id)
        if not frame:
            continue
        annotation_id = int(safe_float(annotation.get("id")))
        detection_id = f"public_weak_building_{validation['dataset_fingerprint'][:10]}_{annotation_id}"
        candidate_id = f"public_review_{validation['dataset_fingerprint'][:10]}_{annotation_id}"
        pixel_geometry = _segmentation_polygon(annotation.get("segmentation"))
        geo_geometry = safe_dict(annotation.get("geo_geometry"))
        confidence = safe_float(annotation.get("source_confidence"), 0.5)
        detection = {
            "detection_id": detection_id,
            "kind": "building",
            "feature_type": "building_footprint",
            "confidence": round(min(max(confidence, 0.05), 0.7), 4),
            "pixel_geometry": pixel_geometry,
            "geo_geometry": geo_geometry,
            "imagery_frame_id": safe_str(frame.get("frame_id")),
            "provider": "Microsoft Global ML Building Footprints weak alignment",
            "source_url": safe_str(frame.get("source_url")),
            "properties": {
                "supervision": WEAK_SUPERVISION_STATUS,
                "review_status": "pending",
                "label_license": safe_str(annotation.get("label_license")),
            },
        }
        detections.append(detection)
        feature_candidates.append(
            {
                "candidate_id": candidate_id,
                "feature_type": "building_footprint",
                "geometry": geo_geometry,
                "source_type": "image_detected_candidate",
                "source_url": safe_str(frame.get("source_url")),
                "source_name": "Microsoft Global ML Building Footprints weak alignment",
                "confidence": detection["confidence"],
                "review_required": True,
                "needs_user_confirmation": True,
                "acceptance_status": "pending",
                "evidence_source": "USGS NAIP frame with Microsoft weak building proposal",
                "blockers": [
                    "Weak public label requires image-by-image accept, reject, or redraw review before it can become ground truth."
                ],
                "source_feature_id": detection_id,
                "properties": {
                    "vision_detection_id": detection_id,
                    "imagery_frame_id": safe_str(frame.get("frame_id")),
                    "pixel_geometry": pixel_geometry,
                    "geo_geometry": geo_geometry,
                    "geography_id": safe_str(frame.get("geography_id")),
                    "season": safe_str(frame.get("season")),
                    "imagery_quality_band": safe_str(frame.get("imagery_quality_band")),
                    "source_rights": safe_dict(frame.get("source_rights")),
                    "supervision": WEAK_SUPERVISION_STATUS,
                },
                "canonical_object_allowed": False,
                "draft_object_allowed_after_acceptance": True,
            }
        )

    vision_report = {
        "version": "civora_vision_detection_report_v2",
        "imagery_frame": frames[0] if len(frames) == 1 else {},
        "imagery_frames": frames,
        "detections": detections,
        "detection_count": len(detections),
        "provider": "public_weak_supervision_bootstrap",
        "review_required": True,
        "visible_detection_influence": False,
    }
    meta: Dict[str, Any] = {
        "map_feature_detection_report_v1": {
            "version": "map_feature_detection_report_v1",
            "feature_candidates": feature_candidates,
            "civora_vision_detection_report_v2": vision_report,
            "imagery_object_detection_report_v1": {
                "status": "ready_for_review",
                "provider": "public_weak_supervision_bootstrap",
                "detection_count": len(detections),
                "civora_vision_detection_report_v2": vision_report,
            },
        },
        "civora_vision_detection_report_v2": vision_report,
    }
    from .candidate_review_inbox import build_candidate_review_inbox
    from .vision_ground_truth_flywheel import LEDGER_VERSION, attach_vision_ground_truth_flywheel

    meta["candidate_review_inbox_v1"] = build_candidate_review_inbox(meta)
    meta[LEDGER_VERSION] = {
        "version": LEDGER_VERSION,
        "created_at": now_iso(),
        "events": [],
        "head_hash": "GENESIS",
        "truth_label": "The review sprint starts with an empty append-only ledger.",
    }
    meta = attach_vision_ground_truth_flywheel(meta)
    payload: Dict[str, Any] = {
        "version": REVIEW_SPRINT_VERSION,
        "created_at": now_iso(),
        "source_dataset_fingerprint": safe_str(rec.get("dataset_fingerprint")),
        "source_package_validation": validation,
        "source_assets": [safe_dict(frame.get("source_asset")) for frame in frames],
        "imagery_frame_count": len(frames),
        "pending_candidate_count": len(feature_candidates),
        "ground_truth_annotation_count": 0,
        "meta": meta,
        "review_required": True,
        "promotion_eligible": False,
        "truth_label": (
            "Every item in this sprint is a weak proposal over a rights-cleared source frame. The sprint starts with zero "
            "ground-truth annotations and gains labels only through explicit reviewer decisions recorded in the ledger."
        ),
    }
    payload["review_sprint_fingerprint"] = stable_fingerprint(
        _review_sprint_fingerprint_payload(payload)
    )
    return payload


def verify_public_review_sprint(sprint: Dict[str, Any]) -> Dict[str, Any]:
    rec = safe_dict(sprint)
    blockers: List[str] = []
    if safe_str(rec.get("version")) != REVIEW_SPRINT_VERSION:
        blockers.append("unsupported_review_sprint_version")
    if int(safe_float(rec.get("ground_truth_annotation_count"))) != 0:
        blockers.append("review_sprint_must_start_with_zero_ground_truth")
    if rec.get("promotion_eligible") is not False:
        blockers.append("unreviewed_sprint_must_be_promotion_ineligible")
    if safe_dict(rec.get("source_package_validation")).get("valid") is not True:
        blockers.append("source_package_validation_missing_or_blocked")
    meta = safe_dict(rec.get("meta"))
    ledger = safe_dict(meta.get("civora_vision_ground_truth_ledger_v1"))
    if safe_list(ledger.get("events")) or safe_str(ledger.get("head_hash"), "GENESIS") != "GENESIS":
        blockers.append("review_sprint_ledger_must_start_empty")
    inbox = safe_dict(meta.get("candidate_review_inbox_v1"))
    candidates = [safe_dict(item) for item in safe_list(inbox.get("candidates")) if safe_dict(item)]
    if len(candidates) != int(safe_float(rec.get("pending_candidate_count"))):
        blockers.append("review_sprint_candidate_count_mismatch")
    if any(safe_str(item.get("status"), "pending") != "pending" for item in candidates):
        blockers.append("review_sprint_candidates_must_start_pending")
    expected_fingerprint = stable_fingerprint(_review_sprint_fingerprint_payload(rec))
    if safe_str(rec.get("review_sprint_fingerprint")) != expected_fingerprint:
        blockers.append("review_sprint_fingerprint_mismatch")
    return {
        "valid": not blockers,
        "blockers": sorted(set(blockers)),
        "review_sprint_fingerprint": expected_fingerprint,
        "imagery_frame_count": int(safe_float(rec.get("imagery_frame_count"))),
        "pending_candidate_count": len(candidates),
    }


def _review_sprint_fingerprint_payload(sprint: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(sprint.get("meta"))
    vision_report = safe_dict(meta.get("civora_vision_detection_report_v2"))
    inbox = safe_dict(meta.get("candidate_review_inbox_v1"))
    return {
        "source_dataset_fingerprint": safe_str(sprint.get("source_dataset_fingerprint")),
        "source_assets": safe_list(sprint.get("source_assets")),
        "imagery_frames": safe_list(vision_report.get("imagery_frames")),
        "candidates": safe_list(inbox.get("candidates")),
        "imagery_frame_count": int(safe_float(sprint.get("imagery_frame_count"))),
        "pending_candidate_count": int(safe_float(sprint.get("pending_candidate_count"))),
    }


def _segmentation_polygon(value: Any) -> Dict[str, Any]:
    segments = safe_list(value)
    flat = safe_list(segments[0]) if segments else []
    points: List[List[float]] = []
    for index in range(0, len(flat) - 1, 2):
        points.append([safe_float(flat[index]), safe_float(flat[index + 1])])
    if len(points) < 3:
        return {}
    if points[0] != points[-1]:
        points.append(list(points[0]))
    return {"type": "Polygon", "coordinates": [points]}


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
    "REVIEW_SPRINT_VERSION",
    "REVIEWED_SUPERVISION_STATUS",
    "WEAK_SUPERVISION_STATUS",
    "build_geographic_tile_grid",
    "build_public_review_sprint",
    "build_weak_supervision_package",
    "capture_date_from_epoch_ms",
    "capture_season",
    "clip_ring_to_bbox",
    "coco_polygon",
    "feature_intersects_bbox",
    "geometry_bbox",
    "geometry_exterior_rings",
    "merge_weak_supervision_packages",
    "imagery_quality_band",
    "normalize_bbox",
    "normalize_microsoft_partition_url",
    "quadkey_for_point",
    "quadkeys_for_bbox",
    "stable_fingerprint",
    "verify_weak_supervision_package",
    "verify_public_review_sprint",
    "weak_supervision_package_fingerprint",
    "wgs84_ring_to_pixels",
]
