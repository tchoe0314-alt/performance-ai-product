from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from backend.planning.vision_model_lifecycle import evaluate_quality_by_class


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure Civora vision predictions against rights-cleared ground truth.")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    args = parser.parse_args()
    predictions_payload = _read_json(args.predictions)
    ground_truth_payload = _read_json(args.ground_truth)
    predictions = _records(predictions_payload, ("predictions", "detections", "features", "annotations"))
    ground_truth = _records(ground_truth_payload, ("ground_truth", "features", "annotations"))
    reviewed_ground_truth = bool(
        isinstance(ground_truth_payload, dict)
        and ground_truth_payload.get("supervision_status") == "reviewer_labeled"
        and ground_truth_payload.get("promotion_eligible") is True
    )
    evaluation_status = "measured_against_ground_truth" if reviewed_ground_truth else "unattested_or_weak_label_diagnostic"
    quality = evaluate_quality_by_class(
        predictions,
        ground_truth,
        iou_threshold=args.iou_threshold,
        evaluation_status=evaluation_status,
    )
    quality["promotion_eligible"] = reviewed_ground_truth
    quality["evaluation_blockers"] = [] if reviewed_ground_truth else [
        "reviewed_ground_truth_attestation_missing"
    ]
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(quality, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "output": str(output), **quality}, indent=2))
    return 0


def _read_json(path: str) -> Any:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def _records(value: Any, keys: tuple[str, ...]) -> List[Dict[str, Any]]:
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
            for item in value["annotations"]:
                if not isinstance(item, dict):
                    continue
                rec = dict(item)
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
