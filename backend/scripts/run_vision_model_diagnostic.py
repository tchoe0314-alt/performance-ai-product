from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from backend.planning.vision_model_lifecycle import (
    assess_model_promotion,
    build_model_manifest,
    evaluate_quality_by_class,
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
    args = parser.parse_args()

    model_path = Path(args.model).expanduser().resolve()
    dataset = _read_object(Path(args.dataset).expanduser().resolve())
    classes = _read_object(Path(args.classes).expanduser().resolve())
    image_root = Path(args.image_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
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

    test_ids = {int(value) for value in (dataset.get("splits") or {}).get("test") or []}
    test_images = [
        dict(item)
        for item in dataset.get("images") or []
        if isinstance(item, dict) and int(item.get("id") or 0) in test_ids
    ]
    if not test_images:
        raise SystemExit("Diagnostic test split contains no images.")
    predictions: List[Dict[str, Any]] = []
    for image in test_images:
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
        if not isinstance(annotation, dict) or int(annotation.get("image_id") or 0) not in test_ids:
            continue
        ground_truth.append(
            {
                **annotation,
                "kind": category_labels.get(int(annotation.get("category_id") or -1), ""),
                "geometry": _annotation_geometry(annotation),
            }
        )
    quality = evaluate_quality_by_class(
        predictions,
        ground_truth,
        evaluation_status="unattested_or_weak_label_diagnostic",
    )
    quality.update(
        {
            "promotion_eligible": False,
            "evaluation_blockers": [
                "reviewed_ground_truth_attestation_missing",
                "weak_label_temporal_alignment_unverified",
            ],
            "source_supervision_status": str(dataset.get("supervision_status") or "unspecified"),
            "truth_label": (
                "These metrics compare a diagnostic model with weak labels. They do not measure independent ground-truth "
                "quality and cannot qualify this model for production."
            ),
        }
    )
    promotion = assess_model_promotion(quality, required_classes=required_classes)
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
            "predictions": predictions,
        },
    )
    _write_json(
        output_dir / "weak-ground-truth.json",
        {
            "version": "civora_vision_diagnostic_ground_truth_v1",
            "supervision_status": dataset.get("supervision_status"),
            "promotion_eligible": False,
            "ground_truth": ground_truth,
        },
    )
    _write_json(output_dir / "diagnostic-quality.json", quality)
    _write_json(output_dir / "promotion-assessment.json", promotion)
    print(
        json.dumps(
            {
                "success": True,
                "test_images": len(test_images),
                "weak_ground_truth_count": len(ground_truth),
                "prediction_count": len(predictions),
                "diagnostic_quality": quality,
                "promotion_eligible": False,
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
        approved_by="not-approved-diagnostic",
        model_license="internal-diagnostic-only",
        training_code_revision=args.training_code_revision,
        adapter="civora_semantic_v1",
        input_contract={"width": args.input_size, "height": args.input_size},
        required_classes=required_classes,
        weights_path=str(model_path),
    )
    manifest["thresholds"]["confidence"] = max(0.0, min(1.0, float(args.confidence)))
    manifest["thresholds"]["minimum_component_pixels"] = 4
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
