from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.planning.vision_model_calibration import calibrate_detection_thresholds
from backend.planning.vision_model_lifecycle import assess_ground_truth_attestation
from backend.planning.vision_evidence_integrity import declared_coco_evidence_fingerprint


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Select semantic-model thresholds from validation predictions without touching the test split."
    )
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--ground-truth", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--confidence-grid", default="0.20,0.30,0.40,0.50,0.60,0.70,0.80")
    parser.add_argument("--component-pixel-grid", default="8,16,24,48,96")
    parser.add_argument("--precision-floor", type=float, default=0.70)
    parser.add_argument("--mask-threshold", type=float, default=0.50)
    args = parser.parse_args()

    predictions_payload = _read_object(args.predictions)
    ground_truth_payload = _read_object(args.ground_truth)
    dataset_bytes = _read_bytes(args.dataset)
    dataset = _read_object_bytes(dataset_bytes, source=args.dataset)
    validation_package_sha256 = hashlib.sha256(dataset_bytes).hexdigest()
    evaluation_fingerprint = declared_coco_evidence_fingerprint(dataset)
    evidence_family_fingerprint = str(
        dataset.get("parent_coco_evidence_fingerprint") or evaluation_fingerprint
    )
    for name, payload in (("predictions", predictions_payload), ("ground truth", ground_truth_payload)):
        if payload.get("evaluation_split") != "validation":
            raise SystemExit(f"Calibration {name} must come from the validation split, never test.")
        if payload.get("dataset_fingerprint") != evaluation_fingerprint:
            raise SystemExit(f"Calibration {name} dataset fingerprint does not match the dataset package.")
    if ground_truth_payload.get("validation_calibration_eligible") is not True:
        raise SystemExit("Calibration ground truth must be explicitly reviewed validation evidence.")
    expected_ground_truth = _expected_validation_ground_truth(dataset)
    if _records(ground_truth_payload, "ground_truth") != expected_ground_truth:
        raise SystemExit("Calibration ground truth records do not match the reviewed validation dataset package.")
    if predictions_payload.get("validation_dataset_fingerprint") != evaluation_fingerprint:
        raise SystemExit("Calibration predictions are not bound to this validation package.")
    if predictions_payload.get("evidence_family_fingerprint") != evidence_family_fingerprint:
        raise SystemExit("Calibration predictions are not bound to this evidence family.")
    if not predictions_payload.get("training_dataset_fingerprint"):
        raise SystemExit("Calibration predictions are missing their training dataset identity.")
    if not predictions_payload.get("model_artifact_sha256"):
        raise SystemExit("Calibration predictions are missing their model artifact identity.")
    attestation = assess_ground_truth_attestation(dataset)
    calibration = calibrate_detection_thresholds(
        _records(predictions_payload, "predictions"),
        _records(ground_truth_payload, "ground_truth"),
        dataset_fingerprint=evidence_family_fingerprint,
        confidence_values=_float_values(args.confidence_grid),
        minimum_component_pixels_values=_integer_values(args.component_pixel_grid),
        precision_floor=args.precision_floor,
        mask_threshold=args.mask_threshold,
        ground_truth_attested=attestation["eligible"] is True,
        source_supervision_status=str(dataset.get("supervision_status") or ""),
        validation_dataset_fingerprint=evaluation_fingerprint,
        training_dataset_fingerprint=str(predictions_payload["training_dataset_fingerprint"]),
        validation_package_sha256=validation_package_sha256,
        model_artifact_sha256=str(predictions_payload["model_artifact_sha256"]),
        validation_labels_reviewed=True,
    )
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(calibration, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "success": True,
                "output": str(output),
                "chosen_thresholds": calibration["chosen_thresholds"],
                "chosen_quality": calibration["chosen_quality"],
                "promotion_eligible": calibration["promotion_eligible"],
                "blockers": calibration["blockers"],
            },
            indent=2,
        )
    )
    return 0


def _read_object(path: Path) -> Dict[str, Any]:
    return _read_object_bytes(_read_bytes(path), source=path)


def _read_bytes(path: Path) -> bytes:
    try:
        return path.expanduser().resolve().read_bytes()
    except OSError as exc:
        raise SystemExit(f"Could not read calibration input: {path}") from exc


def _read_object_bytes(value_bytes: bytes, *, source: Path) -> Dict[str, Any]:
    try:
        value = json.loads(value_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Expected valid UTF-8 JSON: {source}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"Expected a JSON object: {source}")
    return value


def _records(payload: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    return [dict(item) for item in payload.get(key) or [] if isinstance(item, dict)]


def _expected_validation_ground_truth(dataset: Dict[str, Any]) -> List[Dict[str, Any]]:
    validation_ids = {int(value) for value in (dataset.get("splits") or {}).get("validation") or []}
    category_labels = {
        int(item["id"]): str(item.get("name") or "")
        for item in dataset.get("categories") or []
        if isinstance(item, dict) and item.get("id") is not None
    }
    records: List[Dict[str, Any]] = []
    for annotation in dataset.get("annotations") or []:
        if not isinstance(annotation, dict) or int(annotation.get("image_id") or 0) not in validation_ids:
            continue
        records.append(
            {
                **annotation,
                "kind": category_labels.get(int(annotation.get("category_id") or -1), ""),
                "geometry": _annotation_geometry(annotation),
            }
        )
    return records


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


def _float_values(value: str) -> List[float]:
    try:
        return [float(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise SystemExit("Confidence grid must be comma-separated numbers.") from exc


def _integer_values(value: str) -> List[int]:
    try:
        return [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise SystemExit("Component-pixel grid must be comma-separated integers.") from exc


if __name__ == "__main__":
    raise SystemExit(main())
