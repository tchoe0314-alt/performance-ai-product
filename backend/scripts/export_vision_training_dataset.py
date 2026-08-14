from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.planning.vision_detection_learning import DATASET_VERSION
from backend.planning.vision_model_lifecycle import build_coco_training_package
from backend.planning.vision_evidence_integrity import (
    build_evaluation_reservation_manifest,
    build_split_scoped_coco_evidence_packages,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export rights-cleared Civora vision feedback as a COCO manifest.")
    parser.add_argument("--learning-package", action="append", required=True, help="JSON learning package or training dataset.")
    parser.add_argument("--asset-registry", required=True, help="JSON registry of rights-cleared local image assets.")
    parser.add_argument("--output", required=True, help="Output COCO package JSON path.")
    parser.add_argument("--split-seed", default="civora-vision-v1")
    parser.add_argument("--ground-truth-attestation", help="Optional JSON attestation for an independent held-out split.")
    parser.add_argument("--evaluation-scope", help="Optional JSON coverage record for geography/season/imagery quality.")
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
        ground_truth_attestation=_read_json(args.ground_truth_attestation) if args.ground_truth_attestation else None,
        evaluation_scope=_read_json(args.evaluation_scope) if args.evaluation_scope else None,
    )
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    training_output = output.with_name(f"{output.stem}-training-validation{output.suffix}")
    evaluation_output = output.with_name(f"{output.stem}-frozen-test{output.suffix}")
    reservation_output = output.with_name(f"{output.stem}-evaluation-reservation{output.suffix}")
    split_artifact_blockers: List[str] = []
    try:
        scoped = build_split_scoped_coco_evidence_packages(
            package,
            required_classes=[
                str(item.get("name") or "")
                for item in package.get("categories") or []
                if isinstance(item, dict) and str(item.get("name") or "")
            ],
        )
    except ValueError as exc:
        split_artifact_blockers.append(str(exc))
    else:
        training_output.write_text(
            json.dumps(scoped["training_validation"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        evaluation_output.write_text(
            json.dumps(scoped["frozen_test"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        reservation = build_evaluation_reservation_manifest(
            scoped["frozen_test"],
            scoped["training_validation"],
            evaluation_package_sha256=_file_sha256(evaluation_output),
            training_package_sha256=_file_sha256(training_output),
            required_classes=[
                str(item.get("name") or "")
                for item in package.get("categories") or []
                if isinstance(item, dict) and str(item.get("name") or "")
            ],
        )
        reservation_output.write_text(
            json.dumps(reservation, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "success": package.get("eligible_image_count", 0) > 0,
                "output": str(output),
                "split_artifacts_ready": not split_artifact_blockers,
                "training_validation_output": str(training_output) if training_output.is_file() else "",
                "frozen_test_output": str(evaluation_output) if evaluation_output.is_file() else "",
                "evaluation_reservation_output": str(reservation_output) if reservation_output.is_file() else "",
                "split_artifact_blockers": split_artifact_blockers,
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


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
