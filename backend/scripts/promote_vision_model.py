from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from backend.planning.vision_model_lifecycle import build_model_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a fingerprinted Civora learned-model deployment manifest.")
    parser.add_argument("--model", required=True, help="ONNX weights path.")
    parser.add_argument("--quality-report", required=True)
    parser.add_argument("--dataset-package", required=True)
    parser.add_argument("--classes", required=True, help="JSON class-id to label mapping.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--model-license", required=True)
    parser.add_argument("--training-code-revision", required=True)
    parser.add_argument("--adapter", choices=("civora_detection_v1", "civora_semantic_v1"), default="civora_semantic_v1")
    parser.add_argument("--input-size", type=int, default=512, help="Model input width/height used during export.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    quality = _read_json(args.quality_report)
    dataset = _read_json(args.dataset_package)
    classes = _read_json(args.classes)
    if dataset.get("version") != "civora_vision_coco_package_v1":
        raise SystemExit("Dataset package is not a Civora rights-cleared COCO package.")
    if dataset.get("contains_image_bytes") is not False:
        raise SystemExit("Dataset package violated the no-embedded-image contract.")
    if int(dataset.get("eligible_image_count") or 0) <= 0:
        raise SystemExit("Dataset package has no eligible rights-cleared images.")
    if dataset.get("supervision_status") != "reviewer_labeled" or dataset.get("promotion_eligible") is not True:
        blockers = dataset.get("promotion_blockers") or ["reviewed_training_supervision_missing"]
        raise SystemExit(
            "Dataset package is not eligible for model promotion: " + ", ".join(str(item) for item in blockers)
        )
    manifest = build_model_manifest(
        model_path=args.model,
        model_name=args.name,
        model_version=args.version,
        classes=classes,
        quality_report=quality,
        dataset_fingerprint=str(dataset.get("dataset_fingerprint") or ""),
        approved_by=args.approved_by,
        model_license=args.model_license,
        training_code_revision=args.training_code_revision,
        adapter=args.adapter,
        input_contract={"width": args.input_size, "height": args.input_size},
    )
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    promoted = manifest["promotion"]["status"] == "approved_for_review_candidates"
    print(
        json.dumps(
            {
                "success": promoted,
                "output": str(output),
                "status": manifest["promotion"]["status"],
                "blockers": manifest["promotion"]["blockers"],
                "weights_sha256": manifest["artifact"]["weights_sha256"],
            },
            indent=2,
        )
    )
    return 0 if promoted else 2


def _read_json(path: str) -> Dict[str, Any]:
    value = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path} must contain a JSON object.")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
