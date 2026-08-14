from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.planning.vision_evidence_integrity import (
    assess_coco_evidence_integrity,
    build_test_consumption_receipt,
    declared_coco_evidence_fingerprint,
    reserve_test_consumption,
    validate_evaluation_reservation_manifest,
    validate_reservation_against_evidence,
    validate_training_package_against_reservation,
)
from backend.planning.vision_model_lifecycle import (
    assess_model_promotion,
    assess_ground_truth_attestation,
    build_model_manifest,
    canonical_model_label,
    evaluate_quality_by_class,
)
from backend.planning.vision_model_calibration import (
    compare_model_to_baseline,
    validate_threshold_calibration,
)
from vision.feature_detection_engine import FeatureDetectionEngine
from vision.model_runtime import LearnedVisionRuntime
from vision.model_runtime import file_sha256


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a trained Civora ONNX model against a held-out diagnostic split.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--classes", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument(
        "--evaluation-reservation-manifest",
        help=(
            "Sealed label-blind manifest emitted with the split packages. Required for --split test and read "
            "before frozen annotation records are parsed or image bytes are opened."
        ),
    )
    parser.add_argument(
        "--training-dataset",
        default="",
        help=(
            "Training COCO package used by the candidate. Defaults to --dataset for the legacy combined-package "
            "workflow; pass it explicitly when evaluation uses a separate frozen package."
        ),
    )
    parser.add_argument("--image-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--name", default="civora-semantic-diagnostic")
    parser.add_argument("--version", default="diagnostic-v1")
    parser.add_argument("--training-code-revision", default="working-tree-diagnostic")
    parser.add_argument("--input-size", type=int, default=256)
    parser.add_argument("--confidence", type=float, default=0.30)
    parser.add_argument("--minimum-component-pixels", type=int, default=24)
    parser.add_argument("--mask-threshold", type=float, default=0.50)
    parser.add_argument("--split", choices=("validation", "test"), default="test")
    parser.add_argument("--calibration", help="Validation-only threshold calibration artifact to freeze for evaluation.")
    parser.add_argument(
        "--baseline-quality",
        help=(
            "Legacy validation-only baseline report. Test evaluation rejects external baseline reports so the learned "
            "candidate and heuristic are measured in one reserved frozen-test campaign."
        ),
    )
    parser.add_argument(
        "--heuristic-max-size",
        type=int,
        default=512,
        help="Maximum image dimension used by the in-campaign heuristic baseline.",
    )
    parser.add_argument(
        "--test-consumption-ledger",
        help=(
            "Durable JSON ledger used to reserve the frozen test evidence before image bytes are opened. "
            "Required for --split test. Keep it outside disposable output directories."
        ),
    )
    parser.add_argument("--imagenet-normalization", action="store_true")
    args = parser.parse_args()

    model_path = Path(args.model).expanduser().resolve()
    classes_path = Path(args.classes).expanduser().resolve()
    dataset_path = Path(args.dataset).expanduser().resolve()
    training_dataset_path = Path(args.training_dataset).expanduser().resolve() if args.training_dataset else dataset_path
    if args.split == "test" and not args.evaluation_reservation_manifest:
        raise SystemExit("--evaluation-reservation-manifest is required before frozen-test evidence is opened.")
    if args.split == "test" and not args.test_consumption_ledger:
        raise SystemExit("--test-consumption-ledger is required for one-way frozen-test evaluation.")
    if args.split == "test" and not args.training_dataset:
        raise SystemExit("--training-dataset is required and must be physically separate from frozen-test evidence.")
    if args.split == "test" and training_dataset_path == dataset_path:
        raise SystemExit("Training and frozen-test package paths must be physically separate.")
    if args.split == "test" and not args.calibration:
        raise SystemExit("--calibration is required and must be frozen from validation before test reservation.")
    if args.split == "test" and args.baseline_quality:
        raise SystemExit(
            "External baseline reports are forbidden. Test evaluation measures the heuristic baseline in the same "
            "reserved campaign."
        )
    reservation_path = (
        Path(args.evaluation_reservation_manifest).expanduser().resolve()
        if args.evaluation_reservation_manifest
        else None
    )
    calibration_path = Path(args.calibration).expanduser().resolve() if args.calibration else None
    ledger_path = Path(args.test_consumption_ledger).expanduser().resolve() if args.test_consumption_ledger else None
    image_root = Path(args.image_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if args.split == "test":
        protected_inputs = {
            "model": model_path,
            "classes": classes_path,
            "frozen test package": dataset_path,
            "development package": training_dataset_path,
            "evaluation reservation": reservation_path,
            "calibration": calibration_path,
        }
        _validate_isolated_test_paths(
            {name: path for name, path in protected_inputs.items() if path is not None},
            ledger_path=ledger_path,
            image_root=image_root,
            output_dir=output_dir,
        )
        for name, path in protected_inputs.items():
            if path is None or not path.is_file():
                raise SystemExit(f"Required {name} file is missing or is not a regular file: {path}")
        if output_dir.exists() and any(output_dir.iterdir()):
            raise SystemExit("Frozen-test output directory must be empty so stale evidence cannot be reused.")
    evaluation_reservation: Dict[str, Any] = {}
    pre_evaluation_receipt: Dict[str, Any] = {}
    pre_evaluation_ledger: Dict[str, Any] = {}
    evaluation_package_bytes = b""
    training_package_bytes = b""
    try:
        model_artifact_sha256 = file_sha256(model_path)
    except OSError as exc:
        raise SystemExit(f"Candidate model artifact could not be read: {model_path}") from exc
    classes = _read_object(classes_path)
    required_classes = sorted(
        {canonical_model_label(label) for key, label in classes.items() if str(key) != "0"}
    )
    if not required_classes:
        raise SystemExit("Candidate class map must define at least one non-background class.")
    if not image_root.is_dir():
        raise SystemExit(f"Diagnostic image root is missing or is not a directory: {image_root}")
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SystemExit(f"Diagnostic output directory cannot be created: {output_dir}") from exc
    calibration: Dict[str, Any] = {}
    runtime: LearnedVisionRuntime | None = None
    if args.split == "test":
        assert reservation_path is not None
        assert calibration_path is not None
        assert ledger_path is not None
        evaluation_reservation = _read_object(reservation_path)
        reservation_validation = validate_evaluation_reservation_manifest(evaluation_reservation)
        if not reservation_validation["valid"]:
            raise SystemExit(
                "Evaluation reservation is invalid before frozen evidence is opened: "
                + ", ".join(reservation_validation["blockers"])
            )
        reserved_classes = sorted(
            {canonical_model_label(value) for value in evaluation_reservation.get("required_model_classes") or []}
        )
        if required_classes != reserved_classes:
            raise SystemExit(
                "Candidate class map does not match the sealed evaluation class contract: "
                f"candidate={required_classes}, reserved={reserved_classes}"
            )
        evidence_family_fingerprint = str(evaluation_reservation.get("evidence_family_fingerprint") or "")
        training_fingerprint = str(evaluation_reservation.get("training_dataset_fingerprint") or "")
        evaluation_fingerprint = str(evaluation_reservation.get("evaluation_dataset_fingerprint") or "")
        calibration = _load_threshold_calibration(
            args,
            evidence_family_fingerprint=evidence_family_fingerprint,
            training_fingerprint=training_fingerprint,
            validation_package_sha256=str(evaluation_reservation.get("training_package_sha256") or ""),
            model_artifact_sha256=model_artifact_sha256,
        )
        runtime = _preflight_candidate_runtime(
            model_path=model_path,
            classes=classes,
            evaluation_fingerprint=evaluation_fingerprint,
            training_fingerprint=training_fingerprint,
            model_artifact_sha256=model_artifact_sha256,
            output_dir=output_dir,
            args=args,
            required_classes=required_classes,
        )
        training_package_bytes = _read_file_bytes(training_dataset_path)
        training_dataset = _read_object_bytes(training_package_bytes, source=training_dataset_path)
        training_binding_validation = validate_training_package_against_reservation(
            evaluation_reservation,
            training_dataset,
            training_package_sha256=hashlib.sha256(training_package_bytes).hexdigest(),
        )
        if not training_binding_validation["valid"]:
            raise SystemExit(
                "Development package failed the sealed reservation before frozen evidence was consumed: "
                + ", ".join(training_binding_validation["blockers"])
            )
        proposed_receipt = build_test_consumption_receipt(
            {},
            candidate_id=f"{args.name}:{args.version}",
            model_artifact_sha256=model_artifact_sha256,
            threshold_calibration_fingerprint=str(calibration.get("calibration_fingerprint") or ""),
            evaluation_reservation_manifest=evaluation_reservation,
        )
        try:
            reservation = reserve_test_consumption(
                ledger_path,
                proposed_receipt,
            )
        except ValueError as exc:
            raise SystemExit(f"Frozen-test reservation failed before evaluation: {exc}") from exc
        pre_evaluation_receipt = dict(reservation["receipt"])
        pre_evaluation_ledger = dict(reservation["ledger"])
        evaluation_package_bytes = _read_file_bytes(dataset_path)
        package_binding_validation = validate_evaluation_reservation_manifest(
            evaluation_reservation,
            evaluation_package_sha256=hashlib.sha256(evaluation_package_bytes).hexdigest(),
            training_package_sha256=hashlib.sha256(training_package_bytes).hexdigest(),
        )
        if not package_binding_validation["valid"]:
            raise SystemExit(
                "Reserved frozen package bytes failed the sealed reservation and remain consumed: "
                + ", ".join(package_binding_validation["blockers"])
            )
    dataset = (
        _read_object_bytes(evaluation_package_bytes, source=dataset_path)
        if evaluation_package_bytes
        else _read_object(dataset_path)
    )
    training_dataset = (
        _read_object_bytes(training_package_bytes, source=training_dataset_path)
        if training_package_bytes
        else _read_object(training_dataset_path)
        if args.training_dataset
        else dataset
    )
    evaluation_fingerprint = declared_coco_evidence_fingerprint(dataset)
    evidence_family_fingerprint = str(
        dataset.get("parent_coco_evidence_fingerprint") or evaluation_fingerprint
    )
    training_fingerprint = declared_coco_evidence_fingerprint(training_dataset)
    if args.split != "test":
        calibration = _load_threshold_calibration(
            args,
            evidence_family_fingerprint=evidence_family_fingerprint,
            training_fingerprint=training_fingerprint,
            model_artifact_sha256=model_artifact_sha256,
        )
        runtime = _preflight_candidate_runtime(
            model_path=model_path,
            classes=classes,
            evaluation_fingerprint=evaluation_fingerprint,
            training_fingerprint=training_fingerprint,
            model_artifact_sha256=model_artifact_sha256,
            output_dir=output_dir,
            args=args,
            required_classes=required_classes,
        )
    evidence_integrity = assess_coco_evidence_integrity(
        dataset,
        evaluation_split=args.split,
        training_package=training_dataset,
        required_classes=required_classes,
    )
    test_consumption_receipt: Dict[str, Any] = pre_evaluation_receipt
    test_consumption_ledger: Dict[str, Any] = pre_evaluation_ledger
    if args.split == "test":
        evidence_validation = validate_reservation_against_evidence(
            evaluation_reservation,
            dataset,
            training_dataset,
            evaluation_package_sha256=hashlib.sha256(evaluation_package_bytes).hexdigest(),
            training_package_sha256=hashlib.sha256(training_package_bytes).hexdigest(),
            required_classes=required_classes,
        )
        if not evidence_validation["valid"]:
            raise SystemExit(
                "Reserved frozen evidence failed full integrity verification and remains consumed: "
                + ", ".join(evidence_validation["blockers"])
            )
        expected_receipt = build_test_consumption_receipt(
            evidence_integrity,
            candidate_id=f"{args.name}:{args.version}",
            model_artifact_sha256=model_artifact_sha256,
            threshold_calibration_fingerprint=str(calibration.get("calibration_fingerprint") or ""),
            consumed_at=str(test_consumption_receipt.get("consumed_at") or ""),
            evaluation_reservation_manifest=evaluation_reservation,
        )
        if expected_receipt != test_consumption_receipt:
            raise SystemExit("Reserved frozen-test receipt does not match the verified evidence package.")
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
        training_dataset=training_dataset,
        quality=seed_quality,
        args=args,
        required_classes=required_classes,
    )
    manifest_path = output_dir / "candidate-manifest.json"
    _write_json(manifest_path, manifest)
    if runtime is None:  # Defensive guard; every supported split preflights before evaluation.
        raise SystemExit("Candidate runtime preflight did not complete.")

    evaluation_ids = {int(value) for value in (dataset.get("splits") or {}).get(args.split) or []}
    evaluation_images = [
        dict(item)
        for item in dataset.get("images") or []
        if isinstance(item, dict) and int(item.get("id") or 0) in evaluation_ids
    ]
    if not evaluation_images:
        raise SystemExit(f"Diagnostic {args.split} split contains no images.")
    predictions: List[Dict[str, Any]] = []
    baseline_predictions: List[Dict[str, Any]] = []
    baseline_engine = FeatureDetectionEngine(max_size=max(128, int(args.heuristic_max_size)))
    for image in evaluation_images:
        path = (image_root / str(image.get("file_name") or "")).resolve()
        if image_root not in path.parents or not path.is_file():
            raise SystemExit(f"Diagnostic image is missing or escaped its image root: {path}")
        image_bytes = _read_file_bytes(path)
        expected_image_sha256 = _expected_image_file_sha256(image)
        actual_image_sha256 = hashlib.sha256(image_bytes).hexdigest()
        if not expected_image_sha256 or actual_image_sha256 != expected_image_sha256:
            raise SystemExit(f"Diagnostic image fingerprint mismatch: {path}")
        result = runtime.detect(image_bytes, requested_kinds=required_classes)
        for detection in result.detections:
            predictions.append(
                {
                    **detection,
                    "image_id": int(image["id"]),
                    "file_name": str(image.get("file_name") or ""),
                }
            )
        if args.split == "test":
            baseline_result = baseline_engine.detect_bytes(image_bytes)
            if not baseline_result.success:
                raise SystemExit(f"Heuristic baseline failed inside the reserved campaign: {baseline_result.message}")
            for detection in baseline_result.detections:
                label = canonical_model_label(detection.kind)
                if label not in required_classes:
                    continue
                baseline_predictions.append(
                    {
                        "image_id": int(image["id"]),
                        "file_name": str(image.get("file_name") or ""),
                        "kind": label,
                        "bbox": list(detection.bbox),
                        "geometry": _heuristic_detection_geometry(detection),
                        "confidence": float(detection.confidence),
                    }
                )
    category_labels = {
        int(item["id"]): str(item.get("name") or "")
        for item in dataset.get("categories") or []
        if isinstance(item, dict) and item.get("id") is not None
    }
    ground_truth = []
    for annotation in dataset.get("annotations") or []:
        if not isinstance(annotation, dict) or int(annotation.get("image_id") or 0) not in evaluation_ids:
            continue
        ground_truth.append(
            {
                **annotation,
                "kind": category_labels.get(int(annotation.get("category_id") or -1), ""),
                "geometry": _annotation_geometry(annotation),
            }
        )
    attestation = assess_ground_truth_attestation({**dataset, "evidence_integrity": evidence_integrity})
    validation_labels_reviewed = (
        args.split == "validation"
        and str(dataset.get("supervision_status") or "")
        in {"reviewer_labeled", "independent_benchmark_annotated"}
        and str((dataset.get("ground_truth_attestation") or {}).get("status") or "")
        in {"human_reviewed_annotations", "third_party_benchmark_annotations"}
    )
    attested = attestation["eligible"] is True or validation_labels_reviewed
    measured = attested and args.split == "test"
    evaluation_status = (
        "measured_against_ground_truth"
        if measured
        else "measured_on_validation_split"
        if attested and args.split == "validation"
        else "unattested_or_weak_label_diagnostic"
    )
    evaluation_blockers = list(attestation["blockers"])
    if attested and args.split != "test":
        evaluation_blockers.append("independent_test_split_not_used_for_evaluation")
    quality = evaluate_quality_by_class(
        predictions,
        ground_truth,
        evaluation_status=evaluation_status,
        ground_truth_attestation=dict(dataset.get("ground_truth_attestation") or {}),
        evaluation_scope=dict(dataset.get("evaluation_scope") or {}),
        source_supervision_status=str(dataset.get("supervision_status") or "unspecified"),
        promotion_eligible=measured,
        evidence_integrity=evidence_integrity,
    )
    quality.update(
        {
            "promotion_eligible": measured,
            "evaluation_blockers": sorted(
                set(evaluation_blockers + list(evidence_integrity.get("blockers") or []))
            ),
            "ground_truth_attestation_assessment": attestation,
            "source_supervision_status": str(dataset.get("supervision_status") or "unspecified"),
            "evaluation_split": args.split,
            "dataset_fingerprint": evaluation_fingerprint,
            "evidence_family_fingerprint": evidence_family_fingerprint,
            "validation_dataset_fingerprint": training_fingerprint,
            "training_dataset_fingerprint": training_fingerprint,
            "model_artifact_sha256": model_artifact_sha256,
            "truth_label": (
                "These metrics use an independently held-out, attested benchmark split. Promotion still requires every "
                "quality, class-depth, coverage, artifact, and human-approval gate."
                if measured
                else "These metrics use reviewed validation labels for threshold selection only. They are not "
                "independent test evidence and cannot qualify this model for promotion."
                if attested and args.split == "validation"
                else "These metrics compare a diagnostic model with weak or unattested labels. They do not measure "
                "independent ground-truth quality and cannot qualify this model for production."
            ),
        }
    )
    if calibration:
        quality["threshold_calibration"] = calibration
    if test_consumption_receipt:
        quality["evaluation_reservation_manifest"] = evaluation_reservation
        quality["test_consumption_receipt"] = test_consumption_receipt
        quality["test_consumption_ledger"] = test_consumption_ledger
    if args.baseline_quality:
        raise SystemExit(
            "External baseline reports are forbidden. Test evaluation measures the heuristic baseline in the same "
            "reserved campaign; validation does not create promotion-grade baseline evidence."
        )
    if args.split == "test":
        baseline_quality = evaluate_quality_by_class(
            baseline_predictions,
            ground_truth,
            evaluation_status=evaluation_status,
            ground_truth_attestation=dict(dataset.get("ground_truth_attestation") or {}),
            evaluation_scope=dict(dataset.get("evaluation_scope") or {}),
            source_supervision_status=str(dataset.get("supervision_status") or "unspecified"),
            promotion_eligible=measured,
            evidence_integrity=evidence_integrity,
        )
        baseline_quality.update(
            {
                "detector": "civora_heuristic",
                "evaluation_split": "test",
                "dataset_fingerprint": evaluation_fingerprint,
                "test_consumption_receipt_sha256": test_consumption_receipt.get("receipt_sha256"),
            }
        )
        quality["baseline_comparison"] = compare_model_to_baseline(quality, baseline_quality)
        quality["in_campaign_baseline_quality"] = baseline_quality
    promotion = assess_model_promotion(
        quality,
        required_classes=required_classes,
        dataset_fingerprint=evaluation_fingerprint,
    )
    manifest = _candidate_manifest(
        model_path=model_path,
        classes=classes,
        dataset=dataset,
        training_dataset=training_dataset,
        quality=quality,
        args=args,
        required_classes=required_classes,
    )
    _write_json(manifest_path, manifest)
    _write_json(
        output_dir / "predictions.json",
        {
            "version": "civora_vision_diagnostic_predictions_v1",
            "dataset_fingerprint": evaluation_fingerprint,
            "evidence_family_fingerprint": evidence_family_fingerprint,
            "validation_dataset_fingerprint": training_fingerprint,
            "training_dataset_fingerprint": training_fingerprint,
            "model_artifact_sha256": model_artifact_sha256,
            "evaluation_split": args.split,
            "applied_thresholds": {
                "confidence": args.confidence,
                "minimum_component_pixels": args.minimum_component_pixels,
                "mask": args.mask_threshold,
            },
            "predictions": predictions,
            "heuristic_baseline_predictions": baseline_predictions,
        },
    )
    _write_json(
        output_dir / (
            "ground-truth.json"
            if measured or (validation_labels_reviewed and args.split == "validation")
            else "weak-ground-truth.json"
        ),
        {
            "version": "civora_vision_diagnostic_ground_truth_v1",
            "dataset_fingerprint": evaluation_fingerprint,
            "evaluation_split": args.split,
            "supervision_status": dataset.get("supervision_status"),
            "promotion_eligible": measured,
            "validation_calibration_eligible": validation_labels_reviewed and args.split == "validation",
            "ground_truth_attestation": dataset.get("ground_truth_attestation"),
            "evaluation_scope": dataset.get("evaluation_scope"),
            "ground_truth": ground_truth,
        },
    )
    _write_json(output_dir / "diagnostic-quality.json", quality)
    _write_json(output_dir / "promotion-assessment.json", promotion)
    if test_consumption_receipt:
        _write_json(output_dir / "test-consumption-receipt.json", test_consumption_receipt)
    print(
        json.dumps(
            {
                "success": True,
                "evaluation_split": args.split,
                "evaluation_images": len(evaluation_images),
                "ground_truth_count": len(ground_truth),
                "prediction_count": len(predictions),
                "diagnostic_quality": quality,
                "promotion_eligible": promotion["eligible"],
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
    training_dataset: Dict[str, Any],
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
        dataset_fingerprint=declared_coco_evidence_fingerprint(training_dataset),
        evaluation_dataset_fingerprint=declared_coco_evidence_fingerprint(dataset),
        approved_by="",
        model_license="internal-diagnostic-only",
        training_code_revision=args.training_code_revision,
        adapter="civora_semantic_v1",
        input_contract={
            "width": args.input_size,
            "height": args.input_size,
            "normalization": (
                {"scale": 1.0 / 255.0, "mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]}
                if args.imagenet_normalization
                else {"scale": 1.0 / 255.0, "mean": [0.0, 0.0, 0.0], "std": [1.0, 1.0, 1.0]}
            ),
        },
        required_classes=required_classes,
        weights_path=str(model_path),
    )
    manifest["thresholds"]["confidence"] = max(0.0, min(1.0, float(args.confidence)))
    manifest["thresholds"]["minimum_component_pixels"] = max(1, int(args.minimum_component_pixels))
    manifest["thresholds"]["mask"] = max(0.0, min(1.0, float(args.mask_threshold)))
    manifest["inference"]["tile_mode"] = "disabled"
    return manifest


def _load_threshold_calibration(
    args: Any,
    *,
    evidence_family_fingerprint: str,
    training_fingerprint: str,
    model_artifact_sha256: str,
    validation_package_sha256: str = "",
) -> Dict[str, Any]:
    if not args.calibration:
        return {}
    calibration = _read_object(Path(args.calibration).expanduser().resolve())
    validation = validate_threshold_calibration(
        calibration,
        dataset_fingerprint=evidence_family_fingerprint,
        require_promotion_eligible=str(args.split).lower() == "test",
        validation_dataset_fingerprint=training_fingerprint,
        training_dataset_fingerprint=training_fingerprint,
        validation_package_sha256=validation_package_sha256,
        model_artifact_sha256=model_artifact_sha256,
    )
    if not validation["valid"]:
        raise SystemExit("Threshold calibration is invalid: " + ", ".join(validation["blockers"]))
    chosen = validation["chosen_thresholds"]
    args.confidence = float(chosen["confidence"])
    args.minimum_component_pixels = int(chosen["minimum_component_pixels"])
    args.mask_threshold = float(chosen["mask"])
    return calibration


def _validate_isolated_test_paths(
    protected_inputs: Dict[str, Path],
    *,
    ledger_path: Path | None,
    image_root: Path,
    output_dir: Path,
) -> None:
    items = list(protected_inputs.items())
    for index, (left_name, left_path) in enumerate(items):
        for right_name, right_path in items[index + 1 :]:
            same_path = left_path == right_path
            same_file = False
            if not same_path and left_path.exists() and right_path.exists():
                try:
                    same_file = left_path.samefile(right_path)
                except OSError:
                    same_file = False
            if same_path or same_file:
                raise SystemExit(
                    "Candidate, configuration, and evidence files must be physically distinct before frozen evidence is "
                    f"opened: {left_name} conflicts with {right_name}."
                )
    if ledger_path is None:
        raise SystemExit("--test-consumption-ledger is required for one-way frozen-test evaluation.")
    if ledger_path in protected_inputs.values():
        raise SystemExit("Test-consumption ledger must be distinct from every candidate and evidence artifact.")
    if ledger_path.exists():
        for name, path in protected_inputs.items():
            try:
                if path.exists() and ledger_path.samefile(path):
                    raise SystemExit(
                        f"Test-consumption ledger aliases the {name} artifact and would corrupt frozen evidence."
                    )
            except OSError:
                continue
    if any(path == image_root or image_root in path.parents for path in protected_inputs.values()):
        raise SystemExit("Candidate, configuration, and manifest files must remain outside the evidence image root.")
    if output_dir == image_root or output_dir in image_root.parents or image_root in output_dir.parents:
        raise SystemExit("Diagnostic output directory must be isolated from the evidence image root.")
    if output_dir == ledger_path.parent or output_dir in ledger_path.parents:
        raise SystemExit("Test-consumption ledger must live outside the disposable diagnostic output directory.")
    if any(output_dir == path or output_dir in path.parents for path in protected_inputs.values()):
        raise SystemExit("Diagnostic output directory must not contain candidate, configuration, or evidence artifacts.")


def _preflight_candidate_runtime(
    *,
    model_path: Path,
    classes: Dict[str, Any],
    evaluation_fingerprint: str,
    training_fingerprint: str,
    model_artifact_sha256: str,
    output_dir: Path,
    args: Any,
    required_classes: List[str],
) -> LearnedVisionRuntime:
    seed_quality = {
        "evaluation_status": "candidate_preflight_without_evaluation_evidence",
        "ground_truth_count": 0,
        "prediction_count": 0,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "mean_matched_iou": 0.0,
        "per_class": {},
        "model_artifact_sha256": model_artifact_sha256,
    }
    dataset_stub = {"dataset_fingerprint": evaluation_fingerprint}
    training_stub = {"dataset_fingerprint": training_fingerprint}
    manifest = _candidate_manifest(
        model_path=model_path,
        classes=classes,
        dataset=dataset_stub,
        training_dataset=training_stub,
        quality=seed_quality,
        args=args,
        required_classes=required_classes,
    )
    try:
        with tempfile.TemporaryDirectory(prefix="candidate-preflight-", dir=output_dir) as directory:
            manifest_path = Path(directory) / "candidate-manifest.json"
            _write_json(manifest_path, manifest)
            runtime = LearnedVisionRuntime(manifest_path=manifest_path, require_promoted=False)
            health = runtime.health(load_session=True)
            if health.get("ready") is not True:
                raise SystemExit(f"Candidate runtime preflight failed: {health.get('error') or 'model unavailable'}")
            buffer = BytesIO()
            Image.new("RGB", (32, 32), color=(127, 127, 127)).save(buffer, format="PNG")
            runtime.detect(buffer.getvalue(), requested_kinds=required_classes)
            return runtime
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit(f"Candidate runtime preflight failed: {exc}") from exc


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


def _heuristic_detection_geometry(detection: Any) -> Dict[str, Any]:
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


def _read_object(path: Path) -> Dict[str, Any]:
    return _read_object_bytes(_read_file_bytes(path), source=path)


def _read_object_bytes(value_bytes: bytes, *, source: Path) -> Dict[str, Any]:
    try:
        value = json.loads(value_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Expected valid UTF-8 JSON: {source}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"Expected a JSON object: {source}")
    return value


def _read_file_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise SystemExit(f"Required evidence file could not be read: {path}") from exc


def _expected_image_file_sha256(image: Dict[str, Any]) -> str:
    for field in ("converted_sha256", "sha256", "source_sha256"):
        value = str(image.get(field) or "").strip().lower()
        if len(value) == 64 and all(character in "0123456789abcdef" for character in value):
            return value
    return ""


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
