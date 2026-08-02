from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from backend.planning.vision_detection_learning import DATASET_VERSION
from backend.planning.vision_model_lifecycle import build_coco_training_package


def main() -> int:
    parser = argparse.ArgumentParser(description="Export rights-cleared Civora vision feedback as a COCO manifest.")
    parser.add_argument("--learning-package", action="append", required=True, help="JSON learning package or training dataset.")
    parser.add_argument("--asset-registry", required=True, help="JSON registry of rights-cleared local image assets.")
    parser.add_argument("--output", required=True, help="Output COCO package JSON path.")
    parser.add_argument("--split-seed", default="civora-vision-v1")
    args = parser.parse_args()

    datasets: List[Dict[str, Any]] = []
    for source in args.learning_package:
        payload = _read_json(source)
        dataset = payload if payload.get("version") == DATASET_VERSION else payload.get(DATASET_VERSION)
        if not isinstance(dataset, dict):
            raise SystemExit(f"{source} does not contain {DATASET_VERSION}.")
        datasets.append(dataset)
    package = build_coco_training_package(
        datasets,
        asset_registry=_read_json(args.asset_registry),
        split_seed=args.split_seed,
    )
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "success": package.get("eligible_image_count", 0) > 0,
                "output": str(output),
                "eligible_image_count": package.get("eligible_image_count", 0),
                "annotation_count": package.get("annotation_count", 0),
                "excluded_example_count": package.get("excluded_example_count", 0),
                "dataset_fingerprint": package.get("dataset_fingerprint"),
            },
            indent=2,
        )
    )
    return 0 if package.get("eligible_image_count", 0) > 0 else 2


def _read_json(path: str) -> Dict[str, Any]:
    value = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path} must contain a JSON object.")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
