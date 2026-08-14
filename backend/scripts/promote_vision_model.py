from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.planning.vision_evidence_integrity import validate_reservation_against_evidence
from backend.planning.vision_model_lifecycle import build_model_manifest, canonical_model_label


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a fingerprinted Civora learned-model deployment manifest.")
    parser.add_argument("--model", required=True, help="ONNX weights path.")
    parser.add_argument("--quality-report", required=True)
    parser.add_argument(
        "--training-dataset-package",
        "--dataset-package",
        dest="training_dataset_package",
        required=True,
        help="Physically isolated training_and_validation COCO package. --dataset-package is a legacy alias.",
    )
    parser.add_argument(
        "--evaluation-dataset-package",
        required=True,
        help="Physically isolated frozen_test COCO package used by the reserved quality report.",
    )
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
    training_dataset, training_package_sha256 = _read_json_with_sha(args.training_dataset_package)
    evaluation_dataset, evaluation_package_sha256 = _read_json_with_sha(args.evaluation_dataset_package)
    classes = _read_json(args.classes)
    for label, dataset, expected_role in (
        ("Training", training_dataset, "training_and_validation"),
        ("Evaluation", evaluation_dataset, "frozen_test"),
    ):
        if dataset.get("version") != "civora_vision_coco_package_v1":
            raise SystemExit(f"{label} dataset is not a Civora rights-cleared COCO package.")
        if dataset.get("contains_image_bytes") is not False:
            raise SystemExit(f"{label} dataset violated the no-embedded-image contract.")
        if int(dataset.get("eligible_image_count") or 0) <= 0:
            raise SystemExit(f"{label} dataset has no eligible rights-cleared images.")
        if dataset.get("dataset_role") != expected_role:
            raise SystemExit(
                f"{label} dataset must be the physically isolated {expected_role} package. "
                "Combined COCO packages cannot be promoted."
            )
    if training_dataset.get("test_records_in_package") is not False or (
        training_dataset.get("splits") or {}
    ).get("test"):
        raise SystemExit("Training dataset still contains frozen-test records.")
    if evaluation_dataset.get("training_records_in_package") is not False or any(
        (evaluation_dataset.get("splits") or {}).get(name) for name in ("train", "validation")
    ):
        raise SystemExit("Evaluation dataset still contains development records.")
    accepted_supervision = {"reviewer_labeled", "independent_benchmark_annotated"}
    if (
        training_dataset.get("supervision_status") not in accepted_supervision
        or evaluation_dataset.get("supervision_status") not in accepted_supervision
    ):
        raise SystemExit("Promotion requires reviewer-labeled or independent benchmark supervision.")
    quality_fingerprint = str(quality.get("dataset_fingerprint") or "").lower()
    evaluation_fingerprint = str(
        evaluation_dataset.get("coco_evidence_fingerprint")
        or evaluation_dataset.get("dataset_fingerprint")
        or ""
    ).lower()
    if quality_fingerprint != evaluation_fingerprint:
        raise SystemExit("Quality report is not bound to the supplied frozen-test package.")
    training_family = str(training_dataset.get("parent_coco_evidence_fingerprint") or "")
    evaluation_family = str(evaluation_dataset.get("parent_coco_evidence_fingerprint") or "")
    if not training_family or training_family != evaluation_family:
        raise SystemExit("Training and evaluation packages do not belong to the same sealed evidence family.")
    reservation = quality.get("evaluation_reservation_manifest") or {}
    required_classes = sorted(
        {
            canonical_model_label(label)
            for key, label in classes.items()
            if str(key) != "0" and canonical_model_label(label)
        }
    )
    reservation_validation = validate_reservation_against_evidence(
        reservation,
        evaluation_dataset,
        training_dataset,
        evaluation_package_sha256=evaluation_package_sha256,
        training_package_sha256=training_package_sha256,
        required_classes=required_classes,
    )
    if not reservation_validation["valid"]:
        raise SystemExit(
            "Promotion packages do not match the sealed evaluation reservation: "
            + ", ".join(reservation_validation["blockers"])
        )
    manifest = build_model_manifest(
        model_path=args.model,
        model_name=args.name,
        model_version=args.version,
        classes=classes,
        quality_report=quality,
        dataset_fingerprint=str(training_dataset.get("dataset_fingerprint") or ""),
        evaluation_dataset_fingerprint=evaluation_fingerprint,
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


def _read_json_with_sha(path: str) -> tuple[Dict[str, Any], str]:
    source = Path(path).expanduser()
    try:
        raw = source.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{path} must contain readable UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"{path} must contain a JSON object.")
    return value, hashlib.sha256(raw).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
