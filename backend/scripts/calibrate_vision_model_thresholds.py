from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from backend.planning.vision_model_calibration import calibrate_detection_thresholds
from backend.planning.vision_model_lifecycle import assess_ground_truth_attestation


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
    dataset = _read_object(args.dataset)
    for name, payload in (("predictions", predictions_payload), ("ground truth", ground_truth_payload)):
        if payload.get("evaluation_split") != "validation":
            raise SystemExit(f"Calibration {name} must come from the validation split, never test.")
        if payload.get("dataset_fingerprint") != dataset.get("dataset_fingerprint"):
            raise SystemExit(f"Calibration {name} dataset fingerprint does not match the dataset package.")
    attestation = assess_ground_truth_attestation(dataset)
    calibration = calibrate_detection_thresholds(
        _records(predictions_payload, "predictions"),
        _records(ground_truth_payload, "ground_truth"),
        dataset_fingerprint=str(dataset.get("dataset_fingerprint") or ""),
        confidence_values=_float_values(args.confidence_grid),
        minimum_component_pixels_values=_integer_values(args.component_pixel_grid),
        precision_floor=args.precision_floor,
        mask_threshold=args.mask_threshold,
        ground_truth_attested=attestation["eligible"] is True,
        source_supervision_status=str(dataset.get("supervision_status") or ""),
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
    value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"Expected a JSON object: {path}")
    return value


def _records(payload: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    return [dict(item) for item in payload.get(key) or [] if isinstance(item, dict)]


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
