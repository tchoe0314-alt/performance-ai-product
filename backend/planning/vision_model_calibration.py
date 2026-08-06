from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List, Sequence

from .common import safe_dict, safe_float, safe_list, safe_str
from .vision_detection_learning import evaluate_detection_quality


CALIBRATION_VERSION = "civora_vision_threshold_calibration_v1"
BASELINE_COMPARISON_VERSION = "civora_vision_baseline_comparison_v1"


def calibrate_detection_thresholds(
    predictions: Iterable[Dict[str, Any]],
    ground_truth: Iterable[Dict[str, Any]],
    *,
    dataset_fingerprint: str,
    confidence_values: Sequence[float],
    minimum_component_pixels_values: Sequence[int],
    precision_floor: float = 0.0,
    mask_threshold: float = 0.5,
    ground_truth_attested: bool = False,
    source_supervision_status: str = "",
) -> Dict[str, Any]:
    predicted = [safe_dict(item) for item in predictions if safe_dict(item)]
    truth = [safe_dict(item) for item in ground_truth if safe_dict(item)]
    confidence_grid = sorted({round(min(max(float(item), 0.0), 1.0), 6) for item in confidence_values})
    component_grid = sorted({max(1, int(item)) for item in minimum_component_pixels_values})
    if not confidence_grid or not component_grid:
        raise ValueError("Calibration requires confidence and component-size search values.")
    trials: List[Dict[str, Any]] = []
    floor = min(max(float(precision_floor), 0.0), 1.0)
    fixed_mask_threshold = min(max(float(mask_threshold), 0.0), 1.0)
    for confidence in confidence_grid:
        for minimum_pixels in component_grid:
            selected = [
                item
                for item in predicted
                if safe_float(item.get("confidence")) >= confidence
                and _component_pixel_count(item) >= minimum_pixels
            ]
            quality = evaluate_detection_quality(selected, truth)
            quality["evaluation_status"] = (
                "measured_on_validation_split"
                if ground_truth_attested
                else "unattested_or_weak_label_diagnostic"
            )
            trials.append(
                {
                    "confidence": confidence,
                    "minimum_component_pixels": minimum_pixels,
                    "prediction_count": len(selected),
                    "precision_floor_satisfied": safe_float(quality.get("precision")) >= floor,
                    "quality": quality,
                }
            )
    chosen = max(
        trials,
        key=lambda item: (
            item["precision_floor_satisfied"],
            safe_float(safe_dict(item.get("quality")).get("f1")),
            safe_float(safe_dict(item.get("quality")).get("precision")),
            safe_float(safe_dict(item.get("quality")).get("recall")),
            safe_float(item.get("confidence")),
            int(safe_float(item.get("minimum_component_pixels"))),
        ),
    )
    blockers: List[str] = []
    if not safe_str(dataset_fingerprint):
        blockers.append("calibration_dataset_fingerprint_missing")
    if not truth:
        blockers.append("calibration_ground_truth_missing")
    if not chosen["precision_floor_satisfied"]:
        blockers.append("calibration_precision_floor_not_met")
    if not ground_truth_attested:
        blockers.append("calibration_ground_truth_not_attested")
    if source_supervision_status not in {"reviewer_labeled", "independent_benchmark_annotated"}:
        blockers.append("calibration_supervision_not_promotion_eligible")
    result: Dict[str, Any] = {
        "version": CALIBRATION_VERSION,
        "dataset_fingerprint": safe_str(dataset_fingerprint),
        "evaluation_split": "validation",
        "test_data_used": False,
        "source_supervision_status": safe_str(source_supervision_status),
        "ground_truth_attested": ground_truth_attested is True,
        "search": {
            "confidence_values": confidence_grid,
            "minimum_component_pixels_values": component_grid,
            "precision_floor": floor,
            "trial_count": len(trials),
        },
        "chosen_thresholds": {
            "confidence": chosen["confidence"],
            "minimum_component_pixels": chosen["minimum_component_pixels"],
            "mask": fixed_mask_threshold,
        },
        "chosen_quality": chosen["quality"],
        "trials": trials,
        "promotion_eligible": not blockers,
        "blockers": blockers,
        "truth_label": (
            "Thresholds were selected on the validation split only. This calibration never uses test data and does not "
            "itself prove model quality or authorize model promotion."
        ),
    }
    result["calibration_fingerprint"] = threshold_calibration_fingerprint(result)
    return result


def validate_threshold_calibration(
    calibration: Dict[str, Any],
    *,
    dataset_fingerprint: str,
    require_promotion_eligible: bool = True,
) -> Dict[str, Any]:
    rec = safe_dict(calibration)
    blockers: List[str] = []
    if safe_str(rec.get("version")) != CALIBRATION_VERSION:
        blockers.append("unsupported_threshold_calibration_version")
    if safe_str(rec.get("dataset_fingerprint")) != safe_str(dataset_fingerprint):
        blockers.append("threshold_calibration_dataset_mismatch")
    if safe_str(rec.get("evaluation_split")) != "validation":
        blockers.append("threshold_calibration_not_validation_only")
    if rec.get("test_data_used") is not False:
        blockers.append("threshold_calibration_used_test_data")
    thresholds = safe_dict(rec.get("chosen_thresholds"))
    if not 0.0 <= safe_float(thresholds.get("confidence"), -1.0) <= 1.0:
        blockers.append("threshold_calibration_confidence_invalid")
    if int(safe_float(thresholds.get("minimum_component_pixels"))) < 1:
        blockers.append("threshold_calibration_component_size_invalid")
    if not 0.0 <= safe_float(thresholds.get("mask"), -1.0) <= 1.0:
        blockers.append("threshold_calibration_mask_invalid")
    if require_promotion_eligible and rec.get("ground_truth_attested") is not True:
        blockers.append("threshold_calibration_ground_truth_not_attested")
    if require_promotion_eligible and safe_str(rec.get("source_supervision_status")) not in {
        "reviewer_labeled",
        "independent_benchmark_annotated",
    }:
        blockers.append("threshold_calibration_supervision_not_eligible")
    if require_promotion_eligible and rec.get("promotion_eligible") is not True:
        blockers.append("threshold_calibration_not_promotion_eligible")
    expected = threshold_calibration_fingerprint(rec)
    if safe_str(rec.get("calibration_fingerprint")) != expected:
        blockers.append("threshold_calibration_fingerprint_mismatch")
    return {
        "valid": not blockers,
        "blockers": sorted(set(blockers)),
        "calibration_fingerprint": expected,
        "chosen_thresholds": thresholds,
    }


def compare_model_to_baseline(
    model_quality: Dict[str, Any],
    baseline_quality: Dict[str, Any],
    *,
    minimum_f1_lift: float = 0.02,
    minimum_precision_lift: float = 0.0,
    maximum_false_positive_increase: int = 0,
) -> Dict[str, Any]:
    model = safe_dict(model_quality)
    baseline = safe_dict(baseline_quality)
    model_false_positive = int(safe_float(model.get("false_positive")))
    baseline_false_positive = int(safe_float(baseline.get("false_positive")))
    f1_lift = safe_float(model.get("f1")) - safe_float(baseline.get("f1"))
    precision_lift = safe_float(model.get("precision")) - safe_float(baseline.get("precision"))
    recall_lift = safe_float(model.get("recall")) - safe_float(baseline.get("recall"))
    false_positive_delta = model_false_positive - baseline_false_positive
    blockers: List[str] = []
    if safe_str(model.get("evaluation_status")) != "measured_against_ground_truth":
        blockers.append("learned_model_ground_truth_evaluation_missing")
    if safe_str(baseline.get("evaluation_status")) != "measured_against_ground_truth":
        blockers.append("baseline_ground_truth_evaluation_missing")
    if safe_str(model.get("evaluation_split")) != "test" or safe_str(baseline.get("evaluation_split")) != "test":
        blockers.append("baseline_comparison_not_on_same_test_split")
    model_fingerprint = safe_str(model.get("dataset_fingerprint"))
    baseline_fingerprint = safe_str(baseline.get("dataset_fingerprint"))
    if not model_fingerprint or model_fingerprint != baseline_fingerprint:
        blockers.append("baseline_comparison_dataset_mismatch")
    if int(safe_float(model.get("ground_truth_count"))) != int(safe_float(baseline.get("ground_truth_count"))):
        blockers.append("baseline_ground_truth_scope_mismatch")
    if f1_lift + 1e-12 < float(minimum_f1_lift):
        blockers.append("learned_model_f1_lift_below_baseline_gate")
    if precision_lift + 1e-12 < float(minimum_precision_lift):
        blockers.append("learned_model_precision_below_baseline_gate")
    if false_positive_delta > int(maximum_false_positive_increase):
        blockers.append("learned_model_false_positives_exceed_baseline_gate")
    return {
        "version": BASELINE_COMPARISON_VERSION,
        "evaluation_split": "test",
        "same_ground_truth_required": True,
        "model": _quality_summary(model),
        "baseline": _quality_summary(baseline),
        "gates": {
            "minimum_f1_lift": float(minimum_f1_lift),
            "minimum_precision_lift": float(minimum_precision_lift),
            "maximum_false_positive_increase": int(maximum_false_positive_increase),
        },
        "f1_lift": round(f1_lift, 6),
        "precision_lift": round(precision_lift, 6),
        "recall_lift": round(recall_lift, 6),
        "false_positive_delta": false_positive_delta,
        "eligible": not blockers,
        "blockers": blockers,
        "truth_label": (
            "The learned model was compared with the existing baseline on the same held-out test evidence. Promotion "
            "requires a measurable F1 gain without worse precision or additional false positives."
        ),
    }


def validate_baseline_comparison(
    comparison: Dict[str, Any],
    *,
    model_quality: Dict[str, Any],
) -> Dict[str, Any]:
    rec = safe_dict(comparison)
    blockers: List[str] = []
    if safe_str(rec.get("version")) != BASELINE_COMPARISON_VERSION:
        blockers.append("unsupported_baseline_comparison_version")
    if safe_str(rec.get("evaluation_split")) != "test":
        blockers.append("baseline_comparison_not_on_test_split")
    if safe_dict(rec.get("model")) != _quality_summary(safe_dict(model_quality)):
        blockers.append("baseline_comparison_model_quality_mismatch")
    gates = safe_dict(rec.get("gates"))
    expected = compare_model_to_baseline(
        safe_dict(rec.get("model")),
        safe_dict(rec.get("baseline")),
        minimum_f1_lift=safe_float(gates.get("minimum_f1_lift"), 0.02),
        minimum_precision_lift=safe_float(gates.get("minimum_precision_lift"), 0.0),
        maximum_false_positive_increase=int(safe_float(gates.get("maximum_false_positive_increase"), 0.0)),
    )
    for key in ("f1_lift", "precision_lift", "recall_lift", "false_positive_delta", "eligible", "blockers"):
        if rec.get(key) != expected.get(key):
            blockers.append("baseline_comparison_result_mismatch")
            break
    blockers.extend(safe_list(expected.get("blockers")))
    return {
        "valid": not blockers,
        "eligible": not blockers,
        "blockers": sorted(set(blockers)),
        "comparison": expected,
    }


def threshold_calibration_fingerprint(calibration: Dict[str, Any]) -> str:
    payload = {key: value for key, value in safe_dict(calibration).items() if key != "calibration_fingerprint"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _component_pixel_count(item: Dict[str, Any]) -> int:
    properties = safe_dict(item.get("properties"))
    explicit = int(safe_float(properties.get("component_pixel_count")))
    if explicit > 0:
        return explicit
    bbox = safe_list(item.get("bbox"))
    if len(bbox) >= 4:
        return max(1, int(safe_float(bbox[2]) * safe_float(bbox[3])))
    return 1


def _quality_summary(quality: Dict[str, Any]) -> Dict[str, Any]:
    rec = safe_dict(quality)
    return {
        key: rec.get(key)
        for key in (
            "evaluation_status",
            "evaluation_split",
            "dataset_fingerprint",
            "ground_truth_count",
            "prediction_count",
            "true_positive",
            "false_positive",
            "false_negative",
            "precision",
            "recall",
            "f1",
            "mean_matched_iou",
        )
    }
