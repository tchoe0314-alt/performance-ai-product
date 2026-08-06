from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from backend.planning.vision_model_lifecycle import (
    assess_model_promotion,
    assess_ground_truth_attestation,
    build_model_manifest,
    evaluate_quality_by_class,
)
from backend.planning.vision_model_calibration import (
    compare_model_to_baseline,
    validate_threshold_calibration,
)
from vision.model_runtime import LearnedVisionRuntime


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a trained Civora ONNX model against a held-out diagnostic split.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--classes", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--image-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--name", default="civora-semantic-diagnostic")
    parser.add_argument("--version", default="diagnostic-v1")
    parser.add_argument("--training-code-revision", default="working-tree-diagnostic")
    parser.add_argument("--input-size", type=int, default=256)
    parser.add_argument("--confidence", type=float, default=0.30)
    parser.add_argument("--minimum-component-pixels", type=int, default=24)
    parser.add_argument("--mask-threshold", type=float, default=0.50)
    parser.add_argument("--split", choices=("validation", "test"), default="test")
    parser.add_argument("--calibration", help="Validation-only threshold calibration artifact to freeze for evaluation.")
    parser.add_argument("--baseline-quality", help="Quality report for the heuristic baseline on the same test split.")
    parser.add_argument("--imagenet-normalization", action="store_true")
    args = parser.parse_args()

    model_path = Path(args.model).expanduser().resolve()
    dataset = _read_object(Path(args.dataset).expanduser().resolve())
    classes = _read_object(Path(args.classes).expanduser().resolve())
    image_root = Path(args.image_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    calibration: Dict[str, Any] = {}
    if args.calibration:
        calibration = _read_object(Path(args.calibration).expanduser().resolve())
        calibration_validation = validate_threshold_calibration(
            calibration,
            dataset_fingerprint=str(dataset.get("dataset_fingerprint") or ""),
            require_promotion_eligible=False,
        )
        if not calibration_validation["valid"]:
            raise SystemExit(
                "Threshold calibration is invalid: " + ", ".join(calibration_validation["blockers"])
            )
        chosen_thresholds = calibration_validation["chosen_thresholds"]
        args.confidence = float(chosen_thresholds["confidence"])
        args.minimum_component_pixels = int(chosen_thresholds["minimum_component_pixels"])
        args.mask_threshold = float(chosen_thresholds["mask"])
    required_classes = sorted({str(label) for key, label in classes.items() if str(key) != "0"})
    seed_quality = {
        "evaluation_status": "unattested_or_weak_label_diagnostic",
        "ground_truth_count": 0,
        "prediction_count": 0,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "mean_matched_iou": 0.0,
        "per_class": {},
    }
    manifest = _candidate_manifest(
        model_path=model_path,
        classes=classes,
        dataset=dataset,
        quality=seed_quality,
        args=args,
        required_classes=required_classes,
    )
    manifest_path = output_dir / "candidate-manifest.json"
    _write_json(manifest_path, manifest)
    runtime = LearnedVisionRuntime(manifest_path=manifest_path, require_promoted=False)

    evaluation_ids = {int(value) for value in (dataset.get("splits") or {}).get(args.split) or []}
    evaluation_images = [
        dict(item)
        for item in dataset.get("images") or []
        if isinstance(item, dict) and int(item.get("id") or 0) in evaluation_ids
    ]
    if not evaluation_images:
        raise SystemExit(f"Diagnostic {args.split} split contains no images.")
    predictions: List[Dict[str, Any]] = []
    for image in evaluation_images:
        path = (image_root / str(image.get("file_name") or "")).resolve()
        if image_root not in path.parents or not path.is_file():
            raise SystemExit(f"Diagnostic image is missing or escaped its image root: {path}")
        result = runtime.detect(path.read_bytes(), requested_kinds=required_classes)
        for detection in result.detections:
            predictions.append(
                {
                    **detection,
                    "image_id": int(image["id"]),
                    "file_name": str(image.get("file_name") or ""),
                }
            )
    category_labels = {
        int(item["id"]): str(item.get("name") or "")
        for item in dataset.get("categories") or []
        if isinstance(item, dict) and item.get("id") is not None
    }
    ground_truth = []
    for annotation in dataset.get("annotations") or []:
        if not isinstance(annotation, dict) or int(annotation.get("image_id") or 0) not in evaluation_ids:
            continue
        ground_truth.append(
            {
                **annotation,
                "kind": category_labels.get(int(annotation.get("category_id") or -1), ""),
                "geometry": _annotation_geometry(annotation),
            }
        )
    attestation = assess_ground_truth_attestation(dataset)
    attested = attestation["eligible"] is True
    measured = attested and args.split == "test"
    evaluation_status = (
        "measured_against_ground_truth"
        if measured
        else "measured_on_validation_split"
        if attested and args.split == "validation"
        else "unattested_or_weak_label_diagnostic"
    )
    evaluation_blockers = list(attestation["blockers"])
    if attested and args.split != "test":
        evaluation_blockers.append("independent_test_split_not_used_for_evaluation")
    quality = evaluate_quality_by_class(
        predictions,
        ground_truth,
        evaluation_status=evaluation_status,
        ground_truth_attestation=dict(dataset.get("ground_truth_attestation") or {}),
        evaluation_scope=dict(dataset.get("evaluation_scope") or {}),
        source_supervision_status=str(dataset.get("supervision_status") or "unspecified"),
        promotion_eligible=measured,
    )
    quality.update(
        {
            "promotion_eligible": measured,
            "evaluation_blockers": evaluation_blockers,
            "ground_truth_attestation_assessment": attestation,
            "source_supervision_status": str(dataset.get("supervision_status") or "unspecified"),
            "evaluation_split": args.split,
            "dataset_fingerprint": str(dataset.get("dataset_fingerprint") or ""),
            "truth_label": (
                "These metrics use an independently held-out, attested benchmark split. Promotion still requires every "
                "quality, class-depth, coverage, artifact, and human-approval gate."
                if measured
                else "These metrics use attested validation labels for threshold selection. They are not independent test "
                "evidence and cannot qualify this model for promotion."
                if attested and args.split == "validation"
                else "These metrics compare a diagnostic model with weak or unattested labels. They do not measure "
                "independent ground-truth quality and cannot qualify this model for production."
            ),
        }
    )
    if calibration:
        quality["threshold_calibration"] = calibration
    if args.baseline_quality:
        if args.split != "test":
            raise SystemExit("Baseline comparison is valid only on the held-out test split.")
        baseline_quality = _read_object(Path(args.baseline_quality).expanduser().resolve())
        quality["baseline_comparison"] = compare_model_to_baseline(quality, baseline_quality)
    promotion = assess_model_promotion(
        quality,
        required_classes=required_classes,
        dataset_fingerprint=str(dataset.get("dataset_fingerprint") or ""),
    )
    manifest = _candidate_manifest(
        model_path=model_path,
        classes=classes,
        dataset=dataset,
        quality=quality,
        args=args,
        required_classes=required_classes,
    )
    _write_json(manifest_path, manifest)
    _write_json(
        output_dir / "predictions.json",
        {
            "version": "civora_vision_diagnostic_predictions_v1",
            "dataset_fingerprint": dataset.get("dataset_fingerprint"),
            "evaluation_split": args.split,
            "applied_thresholds": {
                "confidence": args.confidence,
                "minimum_component_pixels": args.minimum_component_pixels,
                "mask": args.mask_threshold,
            },
            "predictions": predictions,
        },
    )
    _write_json(
        output_dir / ("ground-truth.json" if measured else "weak-ground-truth.json"),
        {
            "version": "civora_vision_diagnostic_ground_truth_v1",
            "dataset_fingerprint": dataset.get("dataset_fingerprint"),
            "evaluation_split": args.split,
            "supervision_status": dataset.get("supervision_status"),
            "promotion_eligible": measured,
            "ground_truth_attestation": dataset.get("ground_truth_attestation"),
            "evaluation_scope": dataset.get("evaluation_scope"),
            "ground_truth": ground_truth,
        },
    )
    _write_json(output_dir / "diagnostic-quality.json", quality)
    _write_json(output_dir / "promotion-assessment.json", promotion)
    print(
        json.dumps(
            {
                "success": True,
                "evaluation_split": args.split,
                "evaluation_images": len(evaluation_images),
                "ground_truth_count": len(ground_truth),
                "prediction_count": len(predictions),
                "diagnostic_quality": quality,
                "promotion_eligible": promotion["eligible"],
                "promotion_blockers": promotion["blockers"],
                "candidate_manifest": str(manifest_path),
            },
            indent=2,
        )
    )
    return 0


def _candidate_manifest(
    *,
    model_path: Path,
    classes: Dict[str, Any],
    dataset: Dict[str, Any],
    quality: Dict[str, Any],
    args: Any,
    required_classes: List[str],
) -> Dict[str, Any]:
    manifest = build_model_manifest(
        model_path=model_path,
        model_name=args.name,
        model_version=args.version,
        classes=classes,
        quality_report=quality,
        dataset_fingerprint=str(dataset.get("dataset_fingerprint") or ""),
        approved_by="",
        model_license="internal-diagnostic-only",
        training_code_revision=args.training_code_revision,
        adapter="civora_semantic_v1",
        input_contract={
            "width": args.input_size,
            "height": args.input_size,
            "normalization": (
                {"scale": 1.0 / 255.0, "mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]}
                if args.imagenet_normalization
                else {"scale": 1.0 / 255.0, "mean": [0.0, 0.0, 0.0], "std": [1.0, 1.0, 1.0]}
            ),
        },
        required_classes=required_classes,
        weights_path=str(model_path),
    )
    manifest["thresholds"]["confidence"] = max(0.0, min(1.0, float(args.confidence)))
    manifest["thresholds"]["minimum_component_pixels"] = max(1, int(args.minimum_component_pixels))
    manifest["thresholds"]["mask"] = max(0.0, min(1.0, float(args.mask_threshold)))
    manifest["inference"]["tile_mode"] = "disabled"
    return manifest


def _annotation_geometry(item: Dict[str, Any]) -> Dict[str, Any]:
    segments = item.get("segmentation")
    if isinstance(segments, list) and segments and isinstance(segments[0], list):
        values = segments[0]
        points = [[float(values[index]), float(values[index + 1])] for index in range(0, len(values) - 1, 2)]
        if len(points) >= 3:
            if points[0] != points[-1]:
                points.append(points[0])
            return {"type": "Polygon", "coordinates": [points]}
    return {}


def _read_object(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"Expected a JSON object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
