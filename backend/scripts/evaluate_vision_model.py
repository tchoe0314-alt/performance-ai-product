from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.planning.vision_evidence_integrity import (
    assess_coco_evidence_integrity,
    declared_coco_evidence_fingerprint,
)
from backend.planning.vision_model_lifecycle import assess_ground_truth_attestation, evaluate_quality_by_class


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure Civora vision predictions against rights-cleared ground truth.")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument(
        "--split",
        choices=("train", "validation", "test"),
        default="test",
        help="Evaluate only this split when the ground-truth input is a COCO package.",
    )
    parser.add_argument(
        "--training-dataset",
        default="",
        help="COCO training package used by the candidate. Required for promotion-grade train/test overlap checks.",
    )
    args = parser.parse_args()
    if args.split == "test":
        raise SystemExit(
            "Standalone test evaluation is disabled before evidence files are opened. Use run_vision_model_diagnostic "
            "so learned and baseline predictions are produced and measured inside one atomic frozen-test reservation."
        )
    predictions_payload = _read_json(args.predictions)
    ground_truth_payload = _read_json(args.ground_truth)
    training_payload = _read_json(args.training_dataset) if args.training_dataset else None
    predictions = _records(
        predictions_payload,
        ("predictions", "detections", "features", "annotations"),
        split="",
    )
    ground_truth = _records(
        ground_truth_payload,
        ("ground_truth", "features", "annotations"),
        split=args.split,
    )
    integrity = (
        assess_coco_evidence_integrity(
            ground_truth_payload,
            evaluation_split=args.split,
            training_package=(training_payload if isinstance(training_payload, dict) else None),
        )
        if _is_coco_package(ground_truth_payload)
        else {}
    )
    prediction_scope = _scope_predictions_for_coco_split(
        predictions,
        ground_truth_payload,
        split=args.split,
    ) if _is_coco_package(ground_truth_payload) else {
        "valid": True,
        "selected": predictions,
        "blockers": [],
        "ignored_outside_split_count": 0,
    }
    predictions = prediction_scope["selected"]
    attestation_payload = dict(ground_truth_payload) if isinstance(ground_truth_payload, dict) else {}
    if integrity:
        attestation_payload["evidence_integrity"] = integrity
    attestation = assess_ground_truth_attestation(attestation_payload)
    reviewed_ground_truth = attestation["eligible"] is True and prediction_scope["valid"] is True
    evaluation_status = "measured_against_ground_truth" if reviewed_ground_truth else "unattested_or_weak_label_diagnostic"
    quality = evaluate_quality_by_class(
        predictions,
        ground_truth,
        iou_threshold=args.iou_threshold,
        evaluation_status=evaluation_status,
        ground_truth_attestation=(ground_truth_payload.get("ground_truth_attestation") if isinstance(ground_truth_payload, dict) else {}),
        evaluation_scope=(ground_truth_payload.get("evaluation_scope") if isinstance(ground_truth_payload, dict) else {}),
        source_supervision_status=(ground_truth_payload.get("supervision_status") if isinstance(ground_truth_payload, dict) else ""),
        promotion_eligible=reviewed_ground_truth,
        evidence_integrity=integrity,
    )
    quality["evaluation_split"] = args.split
    quality["dataset_fingerprint"] = (
        declared_coco_evidence_fingerprint(ground_truth_payload)
        if isinstance(ground_truth_payload, dict)
        else ""
    )
    quality["promotion_eligible"] = reviewed_ground_truth
    quality["evaluation_blockers"] = sorted(
        set(list(attestation["blockers"]) + list(prediction_scope["blockers"]))
    )
    quality["ground_truth_attestation_assessment"] = attestation
    quality["prediction_scope_integrity"] = {
        key: value for key, value in prediction_scope.items() if key != "selected"
    }
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(quality, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "output": str(output), **quality}, indent=2))
    return 0


def _read_json(path: str) -> Any:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def _records(value: Any, keys: tuple[str, ...], *, split: str = "") -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        if isinstance(value.get("annotations"), list) and isinstance(value.get("categories"), list):
            labels = {
                int(item["id"]): str(item.get("name") or "")
                for item in value["categories"]
                if isinstance(item, dict) and item.get("id") is not None
            }
            result: List[Dict[str, Any]] = []
            selected_image_ids = _selected_image_ids(value, split)
            for item in value["annotations"]:
                if not isinstance(item, dict):
                    continue
                rec = dict(item)
                if selected_image_ids is not None and int(rec.get("image_id") or -1) not in selected_image_ids:
                    continue
                geometry = _annotation_geometry(rec)
                result.append(
                    {
                        **rec,
                        "kind": labels.get(int(rec.get("category_id") or -1), str(rec.get("kind") or "")),
                        "geometry": geometry,
                    }
                )
            return result
        for key in keys:
            if isinstance(value.get(key), list):
                return [dict(item) for item in value[key] if isinstance(item, dict)]
    raise SystemExit("Input must be a JSON list or object containing a supported record list.")


def _is_coco_package(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("annotations"), list)
        and isinstance(value.get("categories"), list)
        and isinstance(value.get("images"), list)
    )


def _scope_predictions_for_coco_split(
    predictions: List[Dict[str, Any]],
    ground_truth: Dict[str, Any],
    *,
    split: str,
) -> Dict[str, Any]:
    selected_ids = _selected_image_ids(ground_truth, split) or set()
    images = {
        int(item["id"]): item
        for item in ground_truth.get("images") or []
        if isinstance(item, dict) and item.get("id") is not None
    }
    known_scopes = {
        scope: image_id
        for image_id, item in images.items()
        for scope in _image_scopes(item)
        if scope
    }
    selected: List[Dict[str, Any]] = []
    blockers: List[str] = []
    ignored = 0
    for index, item in enumerate(predictions, start=1):
        image_id = _prediction_image_id(item, known_scopes)
        if image_id is None:
            blockers.append(f"prediction_scope_missing_or_unknown:{index}")
            continue
        if image_id not in images:
            blockers.append(f"prediction_scope_unknown_image:{index}")
            continue
        if image_id not in selected_ids:
            ignored += 1
            continue
        selected.append(item)
    return {
        "valid": not blockers,
        "selected": selected,
        "blockers": sorted(set(blockers)),
        "selected_prediction_count": len(selected),
        "ignored_outside_split_count": ignored,
        "evaluation_image_count": len(selected_ids),
    }


def _prediction_image_id(item: Dict[str, Any], known_scopes: Dict[str, int]) -> int | None:
    if item.get("image_id") not in (None, ""):
        try:
            return int(item["image_id"])
        except (TypeError, ValueError):
            return None
    scopes = []
    for key, prefix in (("imagery_frame_id", "frame"), ("frame_id", "frame"), ("file_name", "file")):
        value = str(item.get(key) or "").strip()
        if value:
            scopes.append(f"{prefix}:{value}")
    matches = {known_scopes[scope] for scope in scopes if scope in known_scopes}
    return next(iter(matches)) if len(matches) == 1 else None


def _image_scopes(item: Dict[str, Any]) -> set[str]:
    scopes = set()
    for key, prefix in (("imagery_frame_id", "frame"), ("frame_id", "frame"), ("file_name", "file")):
        value = str(item.get(key) or "").strip()
        if value:
            scopes.add(f"{prefix}:{value}")
    return scopes


def _selected_image_ids(value: Dict[str, Any], split: str) -> set[int] | None:
    if not split:
        return None
    declared = value.get("splits")
    if isinstance(declared, dict) and isinstance(declared.get(split), list):
        return {int(item) for item in declared[split]}
    selected = {
        int(item["id"])
        for item in value.get("images") or []
        if isinstance(item, dict) and item.get("id") is not None and str(item.get("split") or "") == split
    }
    return selected


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


if __name__ == "__main__":
    raise SystemExit(main())
