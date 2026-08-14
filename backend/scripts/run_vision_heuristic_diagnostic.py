from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.planning.vision_evidence_integrity import (
    assess_coco_evidence_integrity,
    declared_coco_evidence_fingerprint,
)
from backend.planning.vision_model_lifecycle import (
    assess_ground_truth_attestation,
    canonical_model_label,
    evaluate_quality_by_class,
)
from vision.feature_detection_engine import FeatureDetectionEngine


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure Civora's current heuristic detector on the same split used by a learned-model diagnostic."
    )
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--training-dataset", type=Path)
    parser.add_argument("--image-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--split", choices=("validation", "test"), default="test")
    parser.add_argument("--max-size", type=int, default=512)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    args = parser.parse_args()

    if args.split == "test":
        raise SystemExit(
            "Standalone frozen-test baseline evaluation is disabled. Use run_vision_model_diagnostic so the heuristic "
            "and learned candidate share one atomic test-evidence reservation."
        )

    dataset = _read_object(args.dataset)
    evaluation_fingerprint = declared_coco_evidence_fingerprint(dataset)
    training = _read_object(args.training_dataset) if args.training_dataset else dataset
    image_root = args.image_root.expanduser().resolve()
    image_ids = {int(value) for value in (dataset.get("splits") or {}).get(args.split) or []}
    images = [
        dict(item)
        for item in dataset.get("images") or []
        if isinstance(item, dict) and int(item.get("id") or 0) in image_ids
    ]
    if not images:
        raise SystemExit(f"Diagnostic {args.split} split contains no images.")
    required_classes = sorted(
        {
            canonical_model_label(item.get("name"))
            for item in dataset.get("categories") or []
            if isinstance(item, dict) and canonical_model_label(item.get("name"))
        }
    )
    engine = FeatureDetectionEngine(max_size=max(128, int(args.max_size)))
    predictions: List[Dict[str, Any]] = []
    for image in images:
        path = (image_root / str(image.get("file_name") or "")).resolve()
        if image_root not in path.parents or not path.is_file():
            raise SystemExit(f"Diagnostic image is missing or escaped its image root: {path}")
        result = engine.detect(str(path))
        if not result.success:
            raise SystemExit(f"Heuristic detector failed for {path.name}: {result.message}")
        for detection in result.detections:
            label = canonical_model_label(detection.kind)
            if label not in required_classes:
                continue
            predictions.append(
                {
                    "image_id": int(image["id"]),
                    "file_name": str(image.get("file_name") or ""),
                    "kind": label,
                    "bbox": list(detection.bbox),
                    "geometry": _detection_geometry(detection),
                    "confidence": float(detection.confidence),
                    "properties": dict(detection.properties),
                }
            )
    labels = {
        int(item["id"]): canonical_model_label(item.get("name"))
        for item in dataset.get("categories") or []
        if isinstance(item, dict) and item.get("id") is not None
    }
    ground_truth = [
        {
            **dict(item),
            "kind": labels.get(int(item.get("category_id") or -1), ""),
            "geometry": _annotation_geometry(dict(item)),
        }
        for item in dataset.get("annotations") or []
        if isinstance(item, dict) and int(item.get("image_id") or 0) in image_ids
    ]
    evidence_integrity = assess_coco_evidence_integrity(
        dataset,
        evaluation_split=args.split,
        training_package=training,
        required_classes=required_classes,
    )
    attestation = assess_ground_truth_attestation({**dataset, "evidence_integrity": evidence_integrity})
    measured = attestation["eligible"] is True and args.split == "test"
    quality = evaluate_quality_by_class(
        predictions,
        ground_truth,
        iou_threshold=float(args.iou_threshold),
        evaluation_status=(
            "measured_against_ground_truth"
            if measured
            else "measured_on_validation_split"
            if attestation["eligible"] is True
            else "unattested_or_weak_label_diagnostic"
        ),
        ground_truth_attestation=dict(dataset.get("ground_truth_attestation") or {}),
        evaluation_scope=dict(dataset.get("evaluation_scope") or {}),
        source_supervision_status=str(dataset.get("supervision_status") or "unspecified"),
        promotion_eligible=measured,
        evidence_integrity=evidence_integrity,
    )
    quality.update(
        {
            "detector": "civora_heuristic",
            "evaluation_split": args.split,
            "dataset_fingerprint": evaluation_fingerprint,
            "promotion_eligible": measured,
            "evaluation_blockers": sorted(
                set(list(attestation["blockers"]) + list(evidence_integrity.get("blockers") or []))
            ),
            "ground_truth_attestation_assessment": attestation,
            "truth_label": (
                "This baseline uses the same held-out evidence as the learned candidate. Weak or unattested labels remain "
                "diagnostic only and cannot support promotion."
            ),
        }
    )
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(quality, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "success": True,
                "output": str(output),
                "evaluation_images": len(images),
                "ground_truth_count": len(ground_truth),
                "prediction_count": len(predictions),
                "quality": quality,
            },
            indent=2,
        )
    )
    return 0


def _detection_geometry(detection: Any) -> Dict[str, Any]:
    if str(detection.geometry_type or "").lower() == "polygon" and len(detection.geometry) >= 3:
        points = [[float(x), float(y)] for x, y in detection.geometry]
        if points[0] != points[-1]:
            points.append(points[0])
        return {"type": "Polygon", "coordinates": [points]}
    x, y, width, height = [float(value) for value in detection.bbox]
    return {
        "type": "Polygon",
        "coordinates": [[[x, y], [x + width, y], [x + width, y + height], [x, y + height], [x, y]]],
    }


def _annotation_geometry(item: Dict[str, Any]) -> Dict[str, Any]:
    segments = item.get("segmentation")
    if isinstance(segments, list) and segments and isinstance(segments[0], list):
        values = segments[0]
        points = [[float(values[index]), float(values[index + 1])] for index in range(0, len(values) - 1, 2)]
        if len(points) >= 3:
            if points[0] != points[-1]:
                points.append(points[0])
            return {"type": "Polygon", "coordinates": [points]}
    bbox = item.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        x, y, width, height = [float(value) for value in bbox[:4]]
        return {
            "type": "Polygon",
            "coordinates": [[[x, y], [x + width, y], [x + width, y + height], [x, y + height], [x, y]]],
        }
    return {}


def _read_object(path: Path) -> Dict[str, Any]:
    value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"Expected a JSON object: {path}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
