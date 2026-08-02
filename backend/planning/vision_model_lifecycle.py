from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from vision.model_runtime import MODEL_MANIFEST_VERSION, PROMOTED_STATUS, file_sha256

from .common import safe_dict, safe_float, safe_list, safe_str
from .vision_detection_learning import DATASET_VERSION, evaluate_detection_quality


COCO_PACKAGE_VERSION = "civora_vision_coco_package_v1"
MODEL_PROMOTION_VERSION = "civora_vision_model_promotion_v1"

DEFAULT_CLASSES = {
    "building_footprint": "building",
    "road_or_drive": "road",
    "parking_area": "parking",
    "sidewalk_or_path": "sidewalk",
    "vegetation/tree_area": "tree",
    "water/pond/basin": "basin",
    "utility": "utility",
    "constraint_area": "constraint",
}

FEATURE_TYPE_ALIASES = {
    "building": "building_footprint",
    "road": "road_or_drive",
    "driveway": "road_or_drive",
    "parking": "parking_area",
    "sidewalk": "sidewalk_or_path",
    "tree": "vegetation/tree_area",
    "tree_or_landscape": "vegetation/tree_area",
    "basin": "water/pond/basin",
    "basin_or_pond": "water/pond/basin",
    "visible_utility_structure": "utility",
    "open_space": "constraint_area",
}

DEFAULT_PROMOTION_THRESHOLDS = {
    "precision": 0.75,
    "recall": 0.70,
    "f1": 0.72,
    "mean_matched_iou": 0.55,
    "minimum_ground_truth_count": 25,
    "minimum_per_class_recall": 0.50,
}


def build_coco_training_package(
    datasets: Iterable[Dict[str, Any]],
    *,
    asset_registry: Dict[str, Any],
    class_map: Optional[Dict[str, str]] = None,
    split_seed: str = "civora-vision-v1",
) -> Dict[str, Any]:
    """Build a deterministic COCO manifest without copying source image bytes."""

    normalized_classes = dict(class_map or DEFAULT_CLASSES)
    categories = [
        {"id": index, "name": model_label, "source_feature_type": feature_type}
        for index, (feature_type, model_label) in enumerate(sorted(normalized_classes.items()), start=1)
    ]
    category_ids = {item["source_feature_type"]: item["id"] for item in categories}
    assets = {
        safe_str(item.get("imagery_frame_id")): safe_dict(item)
        for item in safe_list(asset_registry.get("assets"))
        if safe_str(safe_dict(item).get("imagery_frame_id"))
    }
    images: List[Dict[str, Any]] = []
    annotations: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = []
    image_ids: Dict[str, int] = {}
    annotation_id = 1
    for dataset_index, raw_dataset in enumerate(datasets, start=1):
        dataset = safe_dict(raw_dataset)
        if safe_str(dataset.get("version")) != DATASET_VERSION:
            excluded.append({"dataset_index": dataset_index, "blockers": ["unsupported_training_dataset_version"]})
            continue
        frames = {
            safe_str(item.get("frame_id")): safe_dict(item)
            for item in safe_list(dataset.get("imagery_frames"))
            if safe_str(safe_dict(item).get("frame_id"))
        }
        for example in safe_list(dataset.get("examples")):
            rec = safe_dict(example)
            example_id = safe_str(rec.get("example_id"), f"dataset_{dataset_index}_example")
            frame_id = safe_str(rec.get("imagery_frame_id"))
            frame = frames.get(frame_id, {})
            asset = assets.get(frame_id, {})
            blockers = _training_export_blockers(rec, frame, asset)
            feature_type = _training_feature_type(rec)
            if rec.get("review_action") != "reject" and feature_type not in category_ids:
                blockers.append("unsupported_training_feature_type")
            if blockers:
                excluded.append({"example_id": example_id, "imagery_frame_id": frame_id, "blockers": sorted(set(blockers))})
                continue
            if frame_id not in image_ids:
                image_id = len(image_ids) + 1
                image_ids[frame_id] = image_id
                images.append(
                    {
                        "id": image_id,
                        "asset_id": safe_str(asset.get("asset_id"), frame_id),
                        "file_name": _safe_asset_file_name(asset.get("file_name")),
                        "width": int(safe_float(asset.get("width") or frame.get("pixel_width"))),
                        "height": int(safe_float(asset.get("height") or frame.get("pixel_height"))),
                        "imagery_frame_id": frame_id,
                        "source_sha256": safe_str(asset.get("sha256")),
                        "split": _split_for_frame(frame_id, split_seed),
                    }
                )
            if rec.get("review_action") == "reject":
                continue
            geometry = _training_pixel_geometry(rec, frame)
            segmentation, bbox, area = _coco_geometry(geometry)
            if not segmentation or not bbox:
                excluded.append(
                    {"example_id": example_id, "imagery_frame_id": frame_id, "blockers": ["training_polygon_geometry_missing"]}
                )
                continue
            annotations.append(
                {
                    "id": annotation_id,
                    "image_id": image_ids[frame_id],
                    "category_id": category_ids[feature_type],
                    "segmentation": segmentation,
                    "bbox": bbox,
                    "area": area,
                    "iscrowd": 0,
                    "example_id": example_id,
                    "review_action": safe_str(rec.get("review_action")),
                }
            )
            annotation_id += 1
    payload: Dict[str, Any] = {
        "version": COCO_PACKAGE_VERSION,
        "generated_at": _now_iso(),
        "info": {
            "description": "Rights-cleared, reviewer-labeled Civora imagery candidates.",
            "contains_image_bytes": False,
            "split_seed": split_seed,
        },
        "licenses": [],
        "categories": categories,
        "images": images,
        "annotations": annotations,
        "splits": {
            split_name: [item["id"] for item in images if item["split"] == split_name]
            for split_name in ("train", "validation", "test")
        },
        "excluded_examples": excluded,
        "eligible_image_count": len(images),
        "annotation_count": len(annotations),
        "excluded_example_count": len(excluded),
        "contains_image_bytes": False,
        "supervision_status": "reviewer_labeled",
        "promotion_eligible": bool(images and annotations),
        "promotion_blockers": [] if images and annotations else ["reviewed_training_annotations_missing"],
        "truth_label": (
            "This package references rights-cleared local imagery assets and reviewer labels. It contains no image bytes, "
            "does not grant source rights, and is not a model-quality claim."
        ),
    }
    payload["dataset_fingerprint"] = _stable_fingerprint(
        {
            "categories": categories,
            "images": images,
            "annotations": annotations,
            "splits": payload["splits"],
        }
    )
    return payload


def evaluate_quality_by_class(
    predictions: Iterable[Dict[str, Any]],
    ground_truth: Iterable[Dict[str, Any]],
    *,
    iou_threshold: float = 0.5,
    evaluation_status: str = "measured_against_ground_truth",
) -> Dict[str, Any]:
    predicted = [safe_dict(item) for item in predictions if safe_dict(item)]
    truth = [safe_dict(item) for item in ground_truth if safe_dict(item)]
    overall = evaluate_detection_quality(predicted, truth, iou_threshold=iou_threshold)
    labels = sorted({_label(item) for item in predicted + truth if _label(item)})
    per_class: Dict[str, Any] = {}
    for label in labels:
        class_predictions = [item for item in predicted if _label(item) == label]
        class_truth = [item for item in truth if _label(item) == label]
        per_class[label] = {
            **evaluate_detection_quality(class_predictions, class_truth, iou_threshold=iou_threshold),
            "evaluation_status": safe_str(evaluation_status, "unattested_ground_truth"),
            "prediction_count": len(class_predictions),
            "ground_truth_count": len(class_truth),
        }
    return {
        **overall,
        "evaluation_status": safe_str(evaluation_status, "unattested_ground_truth"),
        "ground_truth_count": len(truth),
        "prediction_count": len(predicted),
        "per_class": per_class,
    }


def assess_model_promotion(
    quality_report: Dict[str, Any],
    *,
    thresholds: Optional[Dict[str, Any]] = None,
    required_classes: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    quality = safe_dict(quality_report)
    limits = {**DEFAULT_PROMOTION_THRESHOLDS, **safe_dict(thresholds)}
    blockers: List[str] = []
    if safe_str(quality.get("evaluation_status")) != "measured_against_ground_truth":
        blockers.append("ground_truth_evaluation_missing")
    for metric in ("precision", "recall", "f1", "mean_matched_iou"):
        if safe_float(quality.get(metric)) < safe_float(limits.get(metric)):
            blockers.append(f"{metric}_below_promotion_threshold")
    if int(safe_float(quality.get("ground_truth_count"))) < int(safe_float(limits.get("minimum_ground_truth_count"))):
        blockers.append("ground_truth_sample_count_below_promotion_threshold")
    per_class = safe_dict(quality.get("per_class"))
    for label in required_classes or []:
        class_quality = safe_dict(per_class.get(label))
        if not class_quality:
            blockers.append(f"required_class_not_evaluated:{label}")
        elif safe_float(class_quality.get("recall")) < safe_float(limits.get("minimum_per_class_recall")):
            blockers.append(f"required_class_recall_below_threshold:{label}")
    return {
        "version": MODEL_PROMOTION_VERSION,
        "eligible": not blockers,
        "thresholds": limits,
        "blockers": sorted(set(blockers)),
        "truth_label": (
            "Promotion means eligible to create visual review candidates under the evaluated classes and conditions. "
            "It does not make detections survey/control or engineering evidence."
        ),
    }


def build_model_manifest(
    *,
    model_path: str | Path,
    model_name: str,
    model_version: str,
    classes: Dict[int | str, str],
    quality_report: Dict[str, Any],
    dataset_fingerprint: str,
    approved_by: str,
    thresholds: Optional[Dict[str, Any]] = None,
    required_classes: Optional[Sequence[str]] = None,
    weights_path: Optional[str] = None,
    model_license: str = "",
    training_code_revision: str = "",
    adapter: str = "civora_detection_v1",
    input_contract: Optional[Dict[str, Any]] = None,
    output_contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    path = Path(model_path).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Model weights not found: {path}")
    model_classes = {str(key): safe_str(value) for key, value in classes.items() if safe_str(value)}
    if not model_classes:
        raise ValueError("At least one model class is required.")
    evaluated_classes = list(required_classes) if required_classes is not None else sorted(
        {label for label in model_classes.values() if label != "background"}
    )
    promotion = assess_model_promotion(
        quality_report,
        thresholds=thresholds,
        required_classes=evaluated_classes,
    )
    blockers = list(safe_list(promotion.get("blockers")))
    fingerprint = safe_str(dataset_fingerprint).lower()
    if len(fingerprint) != 64 or any(character not in "0123456789abcdef" for character in fingerprint):
        blockers.append("training_dataset_fingerprint_invalid")
    if not safe_str(approved_by):
        blockers.append("model_approver_missing")
    if not safe_str(model_license):
        blockers.append("model_license_missing")
    if not safe_str(training_code_revision):
        blockers.append("training_code_revision_missing")
    status = PROMOTED_STATUS if not blockers else "candidate_blocked"
    if adapter not in {"civora_detection_v1", "civora_semantic_v1"}:
        raise ValueError("Unsupported Civora vision model adapter.")
    default_outputs = (
        {"logits": "logits", "background_class_id": 0}
        if adapter == "civora_semantic_v1"
        else {
            "boxes": "boxes",
            "scores": "scores",
            "class_ids": "class_ids",
            "masks": "masks",
            "box_format": "xyxy",
            "box_coordinate_space": "input_pixels",
        }
    )
    return {
        "version": MODEL_MANIFEST_VERSION,
        "model_name": safe_str(model_name, "civora-vision"),
        "model_version": safe_str(model_version, "unversioned"),
        "format": "onnx",
        "adapter": adapter,
        "artifact": {
            "weights_path": weights_path or path.name,
            "weights_sha256": file_sha256(path),
        },
        "classes": model_classes,
        "input": {
            "name": "images",
            "width": 1024,
            "height": 1024,
            "layout": "NCHW",
            "normalization": {"scale": 1.0 / 255.0, "mean": [0, 0, 0], "std": [1, 1, 1]},
            **safe_dict(input_contract),
        },
        "outputs": {**default_outputs, **safe_dict(output_contract)},
        "thresholds": {
            "confidence": 0.45,
            "nms_iou": 0.5,
            "mask": 0.5,
            "max_detections": 200,
        },
        "inference": {
            "tile_mode": "auto",
            "tile_overlap": 0.2,
        },
        "provenance": {
            "dataset_fingerprint": fingerprint,
            "training_code_revision": safe_str(training_code_revision),
            "model_license": safe_str(model_license),
        },
        "evaluation": safe_dict(quality_report),
        "promotion": {
            **promotion,
            "status": status,
            "approved_by": safe_str(approved_by),
            "approved_at": _now_iso() if status == PROMOTED_STATUS else "",
            "blockers": sorted(set(blockers)),
        },
        "truth_label": (
            "This model may create visual review candidates only after promotion gates pass. Model output is not "
            "survey/control, utility-locate, compliance, or engineering evidence."
        ),
    }


def _training_export_blockers(example: Dict[str, Any], frame: Dict[str, Any], asset: Dict[str, Any]) -> List[str]:
    blockers = [safe_str(item) for item in safe_list(example.get("training_blockers")) if safe_str(item)]
    if example.get("training_eligible") is not True:
        blockers.append("training_example_not_eligible")
    if not frame:
        blockers.append("imagery_frame_missing")
    frame_rights = safe_dict(frame.get("source_rights"))
    asset_rights = safe_dict(asset.get("source_rights"))
    if frame_rights.get("training_use_allowed") is not True or asset_rights.get("training_use_allowed") is not True:
        blockers.append("imagery_source_training_rights_not_confirmed")
    if frame_rights.get("storage_allowed") is not True or asset_rights.get("storage_allowed") is not True:
        blockers.append("imagery_source_storage_rights_not_confirmed")
    if not asset:
        blockers.append("imagery_asset_not_registered")
    if not safe_str(asset.get("sha256")):
        blockers.append("imagery_asset_fingerprint_missing")
    try:
        _safe_asset_file_name(asset.get("file_name"))
    except ValueError:
        blockers.append("imagery_asset_file_name_invalid")
    width = int(safe_float(asset.get("width") or frame.get("pixel_width")))
    height = int(safe_float(asset.get("height") or frame.get("pixel_height")))
    if width <= 0 or height <= 0:
        blockers.append("imagery_asset_dimensions_missing")
    return blockers


def _training_feature_type(example: Dict[str, Any]) -> str:
    value = safe_str(example.get("corrected_feature_type") or example.get("original_feature_type"))
    return FEATURE_TYPE_ALIASES.get(value, value)


def _training_pixel_geometry(example: Dict[str, Any], frame: Dict[str, Any]) -> Dict[str, Any]:
    corrected = safe_dict(example.get("corrected_geometry"))
    correction_space = safe_str(example.get("correction_coordinate_space"))
    if corrected and correction_space == "image_pixels":
        return corrected
    if corrected and correction_space == "EPSG:4326":
        return _wgs84_geometry_to_pixels(corrected, frame)
    return safe_dict(example.get("pixel_geometry"))


def _wgs84_geometry_to_pixels(geometry: Dict[str, Any], frame: Dict[str, Any]) -> Dict[str, Any]:
    bbox = safe_dict(frame.get("bbox_wgs84"))
    west = safe_float(bbox.get("west"))
    south = safe_float(bbox.get("south"))
    east = safe_float(bbox.get("east"))
    north = safe_float(bbox.get("north"))
    width = safe_float(frame.get("pixel_width"))
    height = safe_float(frame.get("pixel_height"))
    if east <= west or north <= south or width <= 0 or height <= 0:
        return {}

    def convert(value: Any) -> Any:
        if (
            isinstance(value, (list, tuple))
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            x = (float(value[0]) - west) / (east - west) * width
            y = (north - float(value[1])) / (north - south) * height
            return [round(x, 4), round(y, 4)]
        if isinstance(value, (list, tuple)):
            return [convert(item) for item in value]
        return value

    return {"type": safe_str(geometry.get("type")), "coordinates": convert(geometry.get("coordinates"))}


def _coco_geometry(geometry: Dict[str, Any]) -> Tuple[List[List[float]], List[float], float]:
    if safe_str(geometry.get("type")) != "Polygon":
        return [], [], 0.0
    rings = safe_list(geometry.get("coordinates"))
    if not rings:
        return [], [], 0.0
    ring = [item for item in safe_list(rings[0]) if isinstance(item, (list, tuple)) and len(item) >= 2]
    if len(ring) < 3:
        return [], [], 0.0
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    flat = [round(float(value), 4) for point in ring[:-1] for value in point[:2]]
    xs = [float(point[0]) for point in ring]
    ys = [float(point[1]) for point in ring]
    bbox = [round(min(xs), 4), round(min(ys), 4), round(max(xs) - min(xs), 4), round(max(ys) - min(ys), 4)]
    area = abs(
        sum(float(ring[index][0]) * float(ring[index + 1][1]) - float(ring[index + 1][0]) * float(ring[index][1]) for index in range(len(ring) - 1))
    ) / 2.0
    return [flat], bbox, round(area, 4)


def _safe_asset_file_name(value: Any) -> str:
    text = safe_str(value)
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts:
        raise ValueError("Asset file_name must be a safe relative path.")
    return str(path)


def _split_for_frame(frame_id: str, seed: str) -> str:
    bucket = int(hashlib.sha256(f"{seed}:{frame_id}".encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < 80:
        return "train"
    if bucket < 90:
        return "validation"
    return "test"


def _label(item: Dict[str, Any]) -> str:
    return safe_str(item.get("feature_type") or item.get("kind") or item.get("label"))


def _stable_fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "COCO_PACKAGE_VERSION",
    "DEFAULT_CLASSES",
    "DEFAULT_PROMOTION_THRESHOLDS",
    "MODEL_PROMOTION_VERSION",
    "assess_model_promotion",
    "build_coco_training_package",
    "build_model_manifest",
    "evaluate_quality_by_class",
]
