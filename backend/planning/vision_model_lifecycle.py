from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from vision.model_runtime import MODEL_MANIFEST_VERSION, PROMOTED_STATUS, file_sha256

from .common import safe_dict, safe_float, safe_list, safe_str
from .vision_detection_learning import DATASET_VERSION, evaluate_detection_quality
from .vision_evidence_integrity import (
    EVIDENCE_INTEGRITY_VERSION,
    assess_coco_evidence_integrity,
    build_frozen_split_manifest,
    evidence_context_fingerprint,
    frozen_test_image_membership_fingerprint,
    validate_evaluation_reservation_manifest,
    validate_evidence_integrity_report,
    validate_test_consumption_ledger,
    validate_test_consumption_receipt,
)
from .vision_model_calibration import validate_baseline_comparison, validate_threshold_calibration


COCO_PACKAGE_VERSION = "civora_vision_coco_package_v1"
MODEL_PROMOTION_VERSION = "civora_vision_model_promotion_v1"

DEFAULT_CLASSES = {
    "building_footprint": "building",
    "road_or_drive": "road",
    "parking_area": "parking",
    "sidewalk_or_path": "sidewalk",
    "vegetation/tree_area": "tree",
    "water/pond/basin": "surface_water",
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

MODEL_LABEL_ALIASES = {
    "water": "surface_water",
    "pond": "surface_water",
    "pool": "surface_water",
    "basin": "surface_water",
    "basin_or_pond": "surface_water",
}

DEFAULT_PROMOTION_THRESHOLDS = {
    "precision": 0.85,
    "recall": 0.75,
    "f1": 0.79,
    "mean_matched_iou": 0.60,
    "minimum_ground_truth_count": 100,
    "minimum_per_class_precision": 0.85,
    "minimum_per_class_recall": 0.75,
    "minimum_per_class_ground_truth_count": 25,
    "minimum_geography_count": 5,
    "minimum_season_count": 2,
    "minimum_imagery_quality_band_count": 2,
    "require_validation_only_threshold_calibration": True,
    "require_baseline_comparison": True,
}

ACCEPTED_GROUND_TRUTH_SUPERVISION = {"reviewer_labeled", "independent_benchmark_annotated"}
ACCEPTED_GROUND_TRUTH_ATTESTATIONS = {"human_reviewed_annotations", "third_party_benchmark_annotations"}


def build_coco_training_package(
    datasets: Iterable[Dict[str, Any]],
    *,
    asset_registry: Dict[str, Any],
    class_map: Optional[Dict[str, str]] = None,
    split_seed: str = "civora-vision-v1",
    ground_truth_attestation: Optional[Dict[str, Any]] = None,
    evaluation_scope: Optional[Dict[str, Any]] = None,
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
    represented_category_ids = sorted(
        {int(item["category_id"]) for item in annotations if item.get("category_id") is not None}
    )
    category_id_remap = {
        old_id: new_id for new_id, old_id in enumerate(represented_category_ids, start=1)
    }
    categories = [
        {**item, "id": category_id_remap[int(item["id"])]}
        for item in categories
        if int(item["id"]) in category_id_remap
    ]
    annotations = [
        {**item, "category_id": category_id_remap[int(item["category_id"])]}
        for item in annotations
    ]
    attestation_payload = safe_dict(ground_truth_attestation)
    scope_payload = safe_dict(evaluation_scope)
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
        "split_policy": {
            "strategy": "source_identity_disjoint",
            "test_split_frozen": True,
        },
        "excluded_examples": excluded,
        "eligible_image_count": len(images),
        "annotation_count": len(annotations),
        "excluded_example_count": len(excluded),
        "contains_image_bytes": False,
        "supervision_status": "reviewer_labeled",
        "evaluation_eligible": False,
        "promotion_eligible": False,
        "promotion_blockers": [],
        "ground_truth_attestation": attestation_payload,
        "evaluation_scope": scope_payload,
        "truth_label": (
            "This package references rights-cleared local imagery assets and reviewer labels. Training eligibility does "
            "not make it independent evaluation evidence; promotion remains blocked until test-split, license, coverage, "
            "and human-review attestations are explicitly attached."
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
    payload["frozen_split_manifest"] = build_frozen_split_manifest(payload)
    payload["evidence_integrity"] = assess_coco_evidence_integrity(
        payload,
        evaluation_split="test",
        training_package=payload,
    )
    payload["evaluation_eligible"] = (
        bool(images and annotations)
        and payload["evidence_integrity"]["promotion_eligible"] is True
    )
    payload["promotion_eligible"] = payload["evaluation_eligible"]
    attestation_assessment = assess_ground_truth_attestation(payload)
    evaluation_eligible = (
        bool(images and annotations)
        and payload["evidence_integrity"]["promotion_eligible"] is True
        and attestation_assessment["eligible"] is True
    )
    payload["evaluation_eligible"] = evaluation_eligible
    payload["promotion_eligible"] = evaluation_eligible
    payload["promotion_blockers"] = (
        []
        if evaluation_eligible
        else sorted(
            set(
                ([] if images and annotations else ["reviewed_training_annotations_missing"])
                + safe_list(payload["evidence_integrity"].get("blockers"))
                + safe_list(attestation_assessment.get("blockers"))
            )
        )
    )
    return payload


def evaluate_quality_by_class(
    predictions: Iterable[Dict[str, Any]],
    ground_truth: Iterable[Dict[str, Any]],
    *,
    iou_threshold: float = 0.5,
    evaluation_status: str = "measured_against_ground_truth",
    ground_truth_attestation: Optional[Dict[str, Any]] = None,
    evaluation_scope: Optional[Dict[str, Any]] = None,
    source_supervision_status: str = "",
    promotion_eligible: Optional[bool] = None,
    evidence_integrity: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    predicted = [_evaluation_record(item) for item in predictions if safe_dict(item)]
    truth = [_evaluation_record(item) for item in ground_truth if safe_dict(item)]
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
    result = {
        **overall,
        "evaluation_status": safe_str(evaluation_status, "unattested_ground_truth"),
        "ground_truth_count": len(truth),
        "prediction_count": len(predicted),
        "per_class": per_class,
    }
    if ground_truth_attestation is not None:
        result["ground_truth_attestation"] = safe_dict(ground_truth_attestation)
    if evaluation_scope is not None:
        result["evaluation_scope"] = safe_dict(evaluation_scope)
    if safe_str(source_supervision_status):
        result["source_supervision_status"] = safe_str(source_supervision_status)
    if promotion_eligible is not None:
        result["promotion_eligible"] = promotion_eligible is True
    if evidence_integrity is not None:
        result["evidence_integrity"] = safe_dict(evidence_integrity)
    return result


def assess_ground_truth_attestation(payload: Dict[str, Any]) -> Dict[str, Any]:
    source = safe_dict(payload)
    attestation = safe_dict(source.get("ground_truth_attestation"))
    supervision = safe_str(source.get("source_supervision_status") or source.get("supervision_status"))
    blockers: List[str] = []
    if supervision not in ACCEPTED_GROUND_TRUTH_SUPERVISION:
        blockers.append("reviewed_or_independent_ground_truth_missing")
    if safe_str(attestation.get("status")) not in ACCEPTED_GROUND_TRUTH_ATTESTATIONS:
        blockers.append("ground_truth_attestation_missing")
    if attestation.get("independent_test_split") is not True:
        blockers.append("independent_test_split_not_attested")
    if attestation.get("test_images_excluded_from_training") is not True:
        blockers.append("test_split_training_exclusion_not_attested")
    if not safe_str(attestation.get("dataset_name")):
        blockers.append("ground_truth_dataset_name_missing")
    if not safe_str(attestation.get("license")):
        blockers.append("ground_truth_license_missing")
    evaluation_eligible = source.get("evaluation_eligible") is True or source.get("promotion_eligible") is True
    if not evaluation_eligible:
        blockers.append("ground_truth_evaluation_not_eligible")
    integrity = safe_dict(source.get("evidence_integrity"))
    integrity_validation = validate_evidence_integrity_report(integrity)
    if safe_str(integrity.get("version")) != EVIDENCE_INTEGRITY_VERSION:
        blockers.append("ground_truth_evidence_integrity_missing")
    elif integrity_validation["valid"] is not True:
        blockers.extend(
            f"evidence_integrity:{item}" for item in safe_list(integrity_validation.get("blockers"))
        )
    elif integrity.get("evaluation_eligible") is not True:
        blockers.extend(
            f"evidence_integrity:{item}" for item in safe_list(integrity.get("blockers"))
            if not safe_str(item).startswith("training_")
        )
        if not [
            item
            for item in safe_list(integrity.get("blockers"))
            if not safe_str(item).startswith("training_")
        ]:
            blockers.append("ground_truth_evidence_integrity_invalid")
    if integrity and safe_str(integrity.get("evidence_context_fingerprint")) != evidence_context_fingerprint(source):
        blockers.append("ground_truth_evidence_context_mismatch")
    return {
        "eligible": not blockers,
        "supervision_status": supervision,
        "attestation_status": safe_str(attestation.get("status")),
        "independent_test_split": attestation.get("independent_test_split") is True,
        "evidence_integrity_valid": integrity.get("evaluation_eligible") is True,
        "blockers": sorted(set(blockers)),
    }


def assess_model_promotion(
    quality_report: Dict[str, Any],
    *,
    thresholds: Optional[Dict[str, Any]] = None,
    required_classes: Optional[Sequence[str]] = None,
    dataset_fingerprint: str = "",
) -> Dict[str, Any]:
    quality = safe_dict(quality_report)
    limits = {**DEFAULT_PROMOTION_THRESHOLDS, **safe_dict(thresholds)}
    blockers: List[str] = []
    expected_dataset_fingerprint = safe_str(dataset_fingerprint).lower()
    quality_dataset_fingerprint = safe_str(quality.get("dataset_fingerprint")).lower()
    if expected_dataset_fingerprint and quality_dataset_fingerprint != expected_dataset_fingerprint:
        blockers.append("evaluation_dataset_fingerprint_mismatch")
    if safe_str(quality.get("evaluation_status")) != "measured_against_ground_truth":
        blockers.append("ground_truth_evaluation_missing")
    attestation = assess_ground_truth_attestation(quality)
    blockers.extend(safe_list(attestation.get("blockers")))
    integrity = safe_dict(quality.get("evidence_integrity"))
    integrity_validation = validate_evidence_integrity_report(integrity)
    if integrity_validation["promotion_eligible"] is not True:
        integrity_blockers = safe_list(integrity.get("blockers"))
        blockers.extend(
            f"evidence_integrity:{item}"
            for item in [*safe_list(integrity_validation.get("blockers")), *integrity_blockers]
        )
        if not integrity_blockers:
            blockers.append("promotion_evidence_integrity_invalid")
    evaluation_reservation = safe_dict(quality.get("evaluation_reservation_manifest"))
    reservation_assessment = (
        validate_evaluation_reservation_manifest(evaluation_reservation)
        if evaluation_reservation
        else {
            "valid": False,
            "blockers": ["evaluation_reservation_manifest_missing"],
            "manifest_sha256": "",
            "evaluation_dataset_fingerprint": "",
        }
    )
    if not reservation_assessment["valid"]:
        blockers.extend(reservation_assessment["blockers"])
    elif (
        safe_str(evaluation_reservation.get("evaluation_dataset_fingerprint")).lower()
        != safe_str(quality.get("dataset_fingerprint") or dataset_fingerprint).lower()
        or safe_str(evaluation_reservation.get("test_image_membership_sha256")).lower()
        != frozen_test_image_membership_fingerprint(safe_dict(integrity.get("frozen_test_manifest")))
    ):
        blockers.append("evaluation_reservation_quality_evidence_mismatch")
    calibration_record = safe_dict(quality.get("threshold_calibration"))
    receipt = safe_dict(quality.get("test_consumption_receipt"))
    receipt_assessment = (
        validate_test_consumption_receipt(
            receipt,
            evaluation_dataset_fingerprint=safe_str(quality.get("dataset_fingerprint") or dataset_fingerprint),
            model_artifact_sha256=safe_str(quality.get("model_artifact_sha256")),
            threshold_calibration_fingerprint=safe_str(calibration_record.get("calibration_fingerprint")),
        )
        if receipt
        else {
            "valid": False,
            "blockers": ["test_consumption_receipt_missing"],
            "receipt_sha256": "",
            "candidate_id": "",
            "evaluation_dataset_fingerprint": "",
        }
    )
    if not receipt_assessment.get("promotion_eligible"):
        blockers.extend(receipt_assessment["blockers"])
        if receipt_assessment["valid"]:
            blockers.append("test_consumption_receipt_not_pre_evaluation")
    if receipt and evaluation_reservation and (
        safe_str(receipt.get("evaluation_reservation_manifest_sha256")).lower()
        != safe_str(evaluation_reservation.get("manifest_sha256")).lower()
        or safe_str(receipt.get("test_image_membership_sha256")).lower()
        != safe_str(evaluation_reservation.get("test_image_membership_sha256")).lower()
    ):
        blockers.append("test_consumption_evaluation_reservation_mismatch")
    ledger = safe_dict(quality.get("test_consumption_ledger"))
    ledger_assessment = (
        validate_test_consumption_ledger(
            ledger,
            expected_receipt_sha256=safe_str(receipt.get("receipt_sha256")),
        )
        if ledger
        else {
            "valid": False,
            "blockers": ["test_consumption_ledger_missing"],
            "ledger_sha256": "",
            "entry_count": 0,
            "recorded_receipt_sha256": [],
        }
    )
    if not ledger_assessment.get("promotion_eligible"):
        blockers.extend(ledger_assessment["blockers"])
        if ledger_assessment["valid"]:
            blockers.append("test_consumption_ledger_not_promotion_eligible")
    calibration_assessment = (
        validate_threshold_calibration(
            calibration_record,
            dataset_fingerprint=safe_str(
                quality.get("evidence_family_fingerprint")
                or dataset_fingerprint
                or calibration_record.get("dataset_fingerprint")
            ),
            require_promotion_eligible=True,
            validation_dataset_fingerprint=safe_str(quality.get("validation_dataset_fingerprint")),
            training_dataset_fingerprint=safe_str(quality.get("training_dataset_fingerprint")),
            validation_package_sha256=safe_str(evaluation_reservation.get("training_package_sha256")),
            model_artifact_sha256=safe_str(quality.get("model_artifact_sha256")),
        )
        if calibration_record
        else {
            "valid": False,
            "blockers": ["validation_only_threshold_calibration_missing"],
            "calibration_fingerprint": "",
            "chosen_thresholds": {},
        }
    )
    if limits.get("require_validation_only_threshold_calibration") is True:
        if not calibration_assessment["valid"]:
            blockers.extend(calibration_assessment["blockers"])
        if safe_str(calibration_record.get("source_supervision_status")) != safe_str(
            quality.get("source_supervision_status")
        ):
            blockers.append("threshold_calibration_supervision_mismatch")
    baseline_record = safe_dict(quality.get("baseline_comparison"))
    baseline_assessment = (
        validate_baseline_comparison(
            baseline_record,
            model_quality=quality,
        )
        if baseline_record
        else {
            "valid": False,
            "eligible": False,
            "blockers": ["held_out_baseline_comparison_missing"],
            "comparison": {},
        }
    )
    if limits.get("require_baseline_comparison") is True:
        if not baseline_assessment["valid"]:
            blockers.extend(baseline_assessment["blockers"])
    for metric in ("precision", "recall", "f1", "mean_matched_iou"):
        if safe_float(quality.get(metric)) < safe_float(limits.get(metric)):
            blockers.append(f"{metric}_below_promotion_threshold")
    if int(safe_float(quality.get("ground_truth_count"))) < int(safe_float(limits.get("minimum_ground_truth_count"))):
        blockers.append("ground_truth_sample_count_below_promotion_threshold")
    scope = safe_dict(quality.get("evaluation_scope"))
    for field, threshold_name, blocker in (
        ("geography_count", "minimum_geography_count", "geographic_coverage_below_promotion_threshold"),
        ("season_count", "minimum_season_count", "seasonal_coverage_below_promotion_threshold"),
        (
            "imagery_quality_band_count",
            "minimum_imagery_quality_band_count",
            "imagery_quality_coverage_below_promotion_threshold",
        ),
    ):
        if int(safe_float(scope.get(field))) < int(safe_float(limits.get(threshold_name))):
            blockers.append(blocker)
    per_class = safe_dict(quality.get("per_class"))
    class_assessments: Dict[str, Any] = {}
    for raw_label in required_classes or []:
        label = canonical_model_label(raw_label)
        class_quality = safe_dict(per_class.get(label))
        class_blockers: List[str] = []
        if not class_quality:
            class_blockers.append("required_class_not_evaluated")
        else:
            if safe_float(class_quality.get("precision")) < safe_float(limits.get("minimum_per_class_precision")):
                class_blockers.append("required_class_precision_below_threshold")
            if safe_float(class_quality.get("recall")) < safe_float(limits.get("minimum_per_class_recall")):
                class_blockers.append("required_class_recall_below_threshold")
            if int(safe_float(class_quality.get("ground_truth_count"))) < int(
                safe_float(limits.get("minimum_per_class_ground_truth_count"))
            ):
                class_blockers.append("required_class_sample_count_below_threshold")
        class_assessments[label] = {
            "eligible": not class_blockers,
            "precision": safe_float(class_quality.get("precision")),
            "recall": safe_float(class_quality.get("recall")),
            "ground_truth_count": int(safe_float(class_quality.get("ground_truth_count"))),
            "blockers": class_blockers,
        }
        blockers.extend(f"{item}:{label}" for item in class_blockers)
    eligible_classes = sorted(label for label, item in class_assessments.items() if item["eligible"])
    blocked_classes = sorted(label for label, item in class_assessments.items() if not item["eligible"])
    return {
        "version": MODEL_PROMOTION_VERSION,
        "eligible": not blockers,
        "thresholds": limits,
        "blockers": sorted(set(blockers)),
        "ground_truth_attestation": attestation,
        "evidence_integrity": integrity,
        "evaluation_reservation_manifest": reservation_assessment,
        "test_consumption_receipt": receipt_assessment,
        "test_consumption_ledger": ledger_assessment,
        "threshold_calibration": calibration_assessment,
        "baseline_comparison": baseline_assessment,
        "evaluation_scope": scope,
        "class_assessments": class_assessments,
        "eligible_classes": eligible_classes,
        "blocked_classes": blocked_classes,
        "truth_label": (
            "Promotion means eligible to create visual review candidates only for classes and operating conditions that "
            "passed independent evidence gates. It does not make detections survey/control or engineering evidence."
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
    evaluation_dataset_fingerprint: str = "",
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
    training_fingerprint = safe_str(dataset_fingerprint).lower()
    evaluation_fingerprint = safe_str(evaluation_dataset_fingerprint or dataset_fingerprint).lower()
    artifact_sha256 = file_sha256(path)
    promotion = assess_model_promotion(
        quality_report,
        thresholds=thresholds,
        required_classes=evaluated_classes,
        dataset_fingerprint=evaluation_fingerprint,
    )
    blockers = list(safe_list(promotion.get("blockers")))
    if safe_str(safe_dict(quality_report).get("model_artifact_sha256")).lower() != artifact_sha256:
        blockers.append("evaluation_model_artifact_fingerprint_mismatch")
    if len(training_fingerprint) != 64 or any(
        character not in "0123456789abcdef" for character in training_fingerprint
    ):
        blockers.append("training_dataset_fingerprint_invalid")
    if len(evaluation_fingerprint) != 64 or any(
        character not in "0123456789abcdef" for character in evaluation_fingerprint
    ):
        blockers.append("evaluation_dataset_fingerprint_invalid")
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
            "weights_sha256": artifact_sha256,
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
            "dataset_fingerprint": training_fingerprint,
            "training_dataset_fingerprint": training_fingerprint,
            "evaluation_dataset_fingerprint": evaluation_fingerprint,
            "training_code_revision": safe_str(training_code_revision),
            "model_license": safe_str(model_license),
        },
        "evaluation": safe_dict(quality_report),
        "promotion": {
            **promotion,
            "evidence_eligible": promotion.get("eligible") is True,
            "eligible": status == PROMOTED_STATUS,
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
    explicit_model_label = safe_str(
        item.get("model_label") or item.get("category_name") or item.get("kind") or item.get("label")
    )
    if explicit_model_label:
        return canonical_model_label(explicit_model_label)
    source_feature_type = safe_str(item.get("feature_type"))
    canonical_feature_type = FEATURE_TYPE_ALIASES.get(source_feature_type, source_feature_type)
    return canonical_model_label(DEFAULT_CLASSES.get(canonical_feature_type, source_feature_type))


def canonical_model_label(value: Any) -> str:
    label = safe_str(value)
    return MODEL_LABEL_ALIASES.get(label, label)


def _evaluation_record(item: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(safe_dict(item))
    label = _label(record)
    if not label:
        return record
    source_feature_type = safe_str(record.get("feature_type"))
    if source_feature_type and source_feature_type != label:
        record["source_feature_type"] = source_feature_type
    record["feature_type"] = label
    record["kind"] = label
    return record


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
    "assess_ground_truth_attestation",
    "assess_model_promotion",
    "build_coco_training_package",
    "build_model_manifest",
    "canonical_model_label",
    "evaluate_quality_by_class",
]
