from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import transform as transform_coordinates

from .vision_model_lifecycle import COCO_PACKAGE_VERSION


SPACENET_BENCHMARK_VERSION = "civora_spacenet_benchmark_import_v1"
SPACENET_2_DATASET_URL = "https://spacenet.ai/spacenet-buildings-dataset-v2/"
SPACENET_LICENSE = "CC-BY-SA-4.0"
_RGB_PREFIX = "RGB-PanSharpen_"


def import_spacenet2_building_benchmark(
    source_root: str | Path,
    output_dir: str | Path,
) -> Dict[str, Any]:
    """Convert the official SpaceNet 2 sample/training layout into a traceable COCO package."""

    source = Path(source_root).expanduser().resolve()
    destination = Path(output_dir).expanduser().resolve()
    if not source.is_dir():
        raise ValueError(f"SpaceNet source root was not found: {source}")
    destination.mkdir(parents=True, exist_ok=True)
    image_root = destination / "images"
    image_root.mkdir(parents=True, exist_ok=True)

    regions = _discover_regions(source)
    if not regions:
        raise ValueError("No SpaceNet AOI RGB-PanSharpen directories were found.")

    images: List[Dict[str, Any]] = []
    annotations: List[Dict[str, Any]] = []
    exclusions: List[Dict[str, Any]] = []
    source_artifacts: List[Dict[str, Any]] = []
    annotation_id = 1
    region_split_counts: Dict[str, Dict[str, int]] = {}
    density_bands: set[str] = set()

    for region_path in regions:
        region_id, geography = _region_identity(region_path.name)
        source_images = sorted((region_path / "RGB-PanSharpen").glob("*.tif"))
        split_assignments = _balanced_split_assignments(source_images, region_id)
        region_split_counts[geography] = {"train": 0, "validation": 0, "test": 0}
        for source_image in source_images:
            stem = source_image.stem
            label_stem = stem[len(_RGB_PREFIX) :] if stem.startswith(_RGB_PREFIX) else stem
            label_path = region_path / "geojson" / "buildings" / f"buildings_{label_stem}.geojson"
            if not label_path.is_file():
                exclusions.append(
                    {
                        "source_image": str(source_image.relative_to(source)),
                        "blockers": ["matching_spacenet_building_labels_missing"],
                    }
                )
                continue
            image_id = len(images) + 1
            relative_output = Path(region_id) / f"{stem}.png"
            output_image = image_root / relative_output
            output_image.parent.mkdir(parents=True, exist_ok=True)
            image_metadata = _convert_geotiff_to_png(source_image, output_image)
            label_payload = _read_json_object(label_path)
            image_annotations = _spacenet_annotations(
                label_payload.get("features") or [],
                image_id=image_id,
                first_annotation_id=annotation_id,
                transform=image_metadata["transform"],
                raster_crs=image_metadata["crs"],
                width=image_metadata["width"],
                height=image_metadata["height"],
            )
            annotation_id += len(image_annotations)
            annotations.extend(image_annotations)
            split = split_assignments[source_image]
            region_split_counts[geography][split] += 1
            density_band = _density_band(len(image_annotations))
            density_bands.add(density_band)
            source_sha = _file_sha256(source_image)
            label_sha = _file_sha256(label_path)
            converted_sha = _file_sha256(output_image)
            images.append(
                {
                    "id": image_id,
                    "file_name": relative_output.as_posix(),
                    "width": image_metadata["width"],
                    "height": image_metadata["height"],
                    "split": split,
                    "geography": geography,
                    "aoi": region_id,
                    "density_band": density_band,
                    "imagery_quality_band": "spacenet_rgb_pansharpened",
                    "season": "not_provided_by_source",
                    "source_sha256": source_sha,
                    "label_sha256": label_sha,
                    "converted_sha256": converted_sha,
                    "source_file": str(source_image.relative_to(source)),
                    "label_file": str(label_path.relative_to(source)),
                }
            )
            source_artifacts.append(
                {
                    "image_id": image_id,
                    "source_image_sha256": source_sha,
                    "source_label_sha256": label_sha,
                    "converted_image_sha256": converted_sha,
                }
            )

    if not images or not annotations:
        raise ValueError("SpaceNet import produced no eligible images or building polygons.")

    geographies = sorted(region_split_counts)
    splits = {
        split: [image["id"] for image in images if image["split"] == split]
        for split in ("train", "validation", "test")
    }
    package: Dict[str, Any] = {
        "version": COCO_PACKAGE_VERSION,
        "benchmark_import_version": SPACENET_BENCHMARK_VERSION,
        "generated_at": _now_iso(),
        "info": {
            "description": "SpaceNet 2 RGB PanSharpen building benchmark imported for Civora model evaluation.",
            "contains_image_bytes": False,
            "source_dataset": "SpaceNet 2 Buildings",
            "source_url": SPACENET_2_DATASET_URL,
            "attribution": "SpaceNet Partners",
        },
        "licenses": [
            {
                "id": 1,
                "name": SPACENET_LICENSE,
                "url": "https://creativecommons.org/licenses/by-sa/4.0/",
            }
        ],
        "categories": [{"id": 1, "name": "building", "source_feature_type": "building_footprint"}],
        "images": images,
        "annotations": annotations,
        "splits": splits,
        "region_split_counts": region_split_counts,
        "excluded_examples": exclusions,
        "eligible_image_count": len(images),
        "annotation_count": len(annotations),
        "excluded_example_count": len(exclusions),
        "contains_image_bytes": False,
        "supervision_status": "independent_benchmark_annotated",
        "evaluation_eligible": True,
        "promotion_eligible": True,
        "promotion_blockers": [],
        "ground_truth_attestation": {
            "status": "third_party_benchmark_annotations",
            "dataset_name": "SpaceNet 2 Buildings",
            "dataset_url": SPACENET_2_DATASET_URL,
            "license": SPACENET_LICENSE,
            "attribution": "SpaceNet Partners",
            "independent_test_split": True,
            "test_images_excluded_from_training": True,
            "annotation_source": "official_dataset_labels",
        },
        "evaluation_scope": {
            "geography_count": len(geographies),
            "geographies": geographies,
            "season_count": 0,
            "seasons": [],
            "season_metadata_status": "not_provided_by_source",
            "imagery_quality_band_count": 1,
            "imagery_quality_bands": ["spacenet_rgb_pansharpened"],
            "density_band_count": len(density_bands),
            "density_bands": sorted(density_bands),
            "supported_classes": ["building"],
        },
        "source_artifacts": source_artifacts,
        "truth_label": (
            "This package uses official SpaceNet benchmark imagery and labels under CC BY-SA 4.0. Its held-out split "
            "can measure building-detection quality, but it does not by itself prove multi-season or production-site "
            "generalization and does not make detections survey or engineering evidence."
        ),
    }
    package["dataset_fingerprint"] = _stable_hash(
        {
            "categories": package["categories"],
            "images": images,
            "annotations": annotations,
            "splits": splits,
            "attestation": package["ground_truth_attestation"],
        }
    )
    package_path = destination / "spacenet2-buildings-coco.json"
    package_path.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**package, "package_path": str(package_path), "image_root": str(image_root)}


def _discover_regions(source: Path) -> List[Path]:
    candidates = [path for path in source.glob("AOI_*_Train") if path.is_dir()]
    if candidates:
        return sorted(candidates)
    nested = [path for path in source.glob("*/AOI_*_Train") if path.is_dir()]
    return sorted(nested)


def _region_identity(name: str) -> Tuple[str, str]:
    match = re.match(r"(?P<id>AOI_\d+)_(?P<name>.+?)_Train$", name)
    if not match:
        return name, name
    return match.group("id"), match.group("name").replace("_", " ")


def _balanced_split_assignments(paths: Sequence[Path], region_id: str) -> Dict[Path, str]:
    ordered = sorted(paths, key=lambda path: _stable_hash(f"{region_id}:{path.name}"))
    count = len(ordered)
    if count < 3:
        assignments = ["train"] * count
    else:
        test_count = max(1, int(round(count * 0.20)))
        validation_count = max(1, int(round(count * 0.10)))
        if test_count + validation_count >= count:
            test_count = 1
            validation_count = 1
        train_count = count - validation_count - test_count
        assignments = ["train"] * train_count + ["validation"] * validation_count + ["test"] * test_count
    return dict(zip(ordered, assignments))


def _convert_geotiff_to_png(source: Path, destination: Path) -> Dict[str, Any]:
    with rasterio.open(source) as dataset:
        if dataset.count < 3:
            raise ValueError(f"SpaceNet RGB source has fewer than three bands: {source}")
        pixels = dataset.read([1, 2, 3]).astype(np.float32)
        rendered = np.zeros_like(pixels, dtype=np.uint8)
        for index in range(3):
            band = pixels[index]
            finite = band[np.isfinite(band)]
            nonzero = finite[finite > 0]
            sample = nonzero if nonzero.size >= 64 else finite
            if not sample.size:
                continue
            low, high = np.percentile(sample, [2.0, 98.0])
            if not math.isfinite(float(low)) or not math.isfinite(float(high)) or high <= low:
                low = float(np.min(sample))
                high = float(np.max(sample))
            if high > low:
                rendered[index] = np.clip((band - low) / (high - low) * 255.0, 0, 255).astype(np.uint8)
        Image.fromarray(np.transpose(rendered, (1, 2, 0))).save(destination, format="PNG")
        return {
            "width": int(dataset.width),
            "height": int(dataset.height),
            "transform": dataset.transform,
            "crs": str(dataset.crs or "EPSG:4326"),
        }


def _spacenet_annotations(
    features: Iterable[Any],
    *,
    image_id: int,
    first_annotation_id: int,
    transform: Any,
    raster_crs: str,
    width: int,
    height: int,
) -> List[Dict[str, Any]]:
    annotations: List[Dict[str, Any]] = []
    inverse = ~transform
    for feature in features:
        if not isinstance(feature, dict):
            continue
        geometry = feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {}
        polygons = _polygon_exteriors(geometry)
        segments: List[List[float]] = []
        boxes: List[Tuple[float, float, float, float]] = []
        total_area = 0.0
        for ring in polygons:
            pixel_ring = _ring_to_pixels(
                ring,
                inverse=inverse,
                raster_crs=raster_crs,
                width=width,
                height=height,
            )
            if len(pixel_ring) < 4:
                continue
            flattened = [round(value, 4) for point in pixel_ring[:-1] for value in point]
            if len(flattened) < 6:
                continue
            area = _polygon_area(pixel_ring)
            if area < 1.0:
                continue
            xs = [point[0] for point in pixel_ring]
            ys = [point[1] for point in pixel_ring]
            segments.append(flattened)
            boxes.append((min(xs), min(ys), max(xs), max(ys)))
            total_area += area
        if not segments:
            continue
        annotation_id = first_annotation_id + len(annotations)
        x0 = min(box[0] for box in boxes)
        y0 = min(box[1] for box in boxes)
        x1 = max(box[2] for box in boxes)
        y1 = max(box[3] for box in boxes)
        properties = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
        annotations.append(
            {
                "id": annotation_id,
                "image_id": image_id,
                "category_id": 1,
                "segmentation": segments,
                "bbox": [round(x0, 4), round(y0, 4), round(x1 - x0, 4), round(y1 - y0, 4)],
                "area": round(total_area, 4),
                "iscrowd": 0,
                "source_feature_id": str(properties.get("OBJECTID") or properties.get("Id") or annotation_id),
            }
        )
    return annotations


def _polygon_exteriors(geometry: Dict[str, Any]) -> List[List[List[float]]]:
    geometry_type = str(geometry.get("type") or "")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon" and isinstance(coordinates, list) and coordinates:
        return [coordinates[0]] if isinstance(coordinates[0], list) else []
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        return [polygon[0] for polygon in coordinates if isinstance(polygon, list) and polygon]
    return []


def _ring_to_pixels(
    ring: Sequence[Any],
    *,
    inverse: Any,
    raster_crs: str,
    width: int,
    height: int,
) -> List[List[float]]:
    source_points = [point for point in ring if isinstance(point, (list, tuple)) and len(point) >= 2]
    if len(source_points) < 3:
        return []
    xs = [float(point[0]) for point in source_points]
    ys = [float(point[1]) for point in source_points]
    if raster_crs and raster_crs.upper() not in {"EPSG:4326", "OGC:CRS84"}:
        xs, ys = transform_coordinates("EPSG:4326", raster_crs, xs, ys)
    pixels: List[List[float]] = []
    for x_value, y_value in zip(xs, ys):
        column, row = inverse * (x_value, y_value)
        pixels.append([
            min(max(float(column), 0.0), float(width)),
            min(max(float(row), 0.0), float(height)),
        ])
    if pixels and pixels[0] != pixels[-1]:
        pixels.append(list(pixels[0]))
    return pixels


def _polygon_area(ring: Sequence[Sequence[float]]) -> float:
    return abs(
        sum(
            float(ring[index][0]) * float(ring[index + 1][1])
            - float(ring[index + 1][0]) * float(ring[index][1])
            for index in range(len(ring) - 1)
        )
    ) / 2.0


def _density_band(annotation_count: int) -> str:
    if annotation_count < 10:
        return "low"
    if annotation_count < 40:
        return "medium"
    return "high"


def _read_json_object(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "SPACENET_2_DATASET_URL",
    "SPACENET_BENCHMARK_VERSION",
    "SPACENET_LICENSE",
    "import_spacenet2_building_benchmark",
]
