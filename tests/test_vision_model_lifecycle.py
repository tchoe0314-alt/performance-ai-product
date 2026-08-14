from __future__ import annotations

from copy import deepcopy
import hashlib
import tempfile
import unittest
from pathlib import Path

from backend.planning.vision_model_lifecycle import (
    assess_ground_truth_attestation,
    assess_model_promotion,
    build_coco_training_package,
    build_model_manifest,
    evaluate_quality_by_class,
)
from backend.planning.vision_model_calibration import (
    calibrate_detection_thresholds,
    compare_model_to_baseline,
    threshold_calibration_fingerprint,
)
from backend.planning.vision_evidence_integrity import (
    append_test_consumption_receipt,
    assess_coco_evidence_integrity,
    build_frozen_split_manifest,
    build_held_out_test_commitment,
    build_evaluation_reservation_manifest,
    build_test_consumption_receipt,
    coco_dataset_fingerprint,
)


def _polygon(x0: float, y0: float, x1: float, y1: float):
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


def _dataset(*, rights: bool = True):
    return {
        "version": "civora_vision_training_dataset_v1",
        "imagery_frames": [
            {
                "frame_id": "frame-1",
                "pixel_width": 100,
                "pixel_height": 100,
                "bbox_wgs84": {"west": -96, "south": 40, "east": -95, "north": 41},
                "source_rights": {"training_use_allowed": rights, "storage_allowed": rights},
            }
        ],
        "examples": [
            {
                "example_id": "example-1",
                "imagery_frame_id": "frame-1",
                "original_feature_type": "building_footprint",
                "review_action": "accept",
                "pixel_geometry": _polygon(10, 10, 30, 35),
                "training_eligible": rights,
                "training_blockers": [] if rights else ["imagery_source_training_rights_not_confirmed"],
            },
            {
                "example_id": "example-negative",
                "imagery_frame_id": "frame-1",
                "original_feature_type": "parking_area",
                "review_action": "reject",
                "pixel_geometry": _polygon(50, 50, 70, 70),
                "training_eligible": rights,
                "training_blockers": [] if rights else ["imagery_source_training_rights_not_confirmed"],
            },
        ],
    }


def _asset_registry(*, rights: bool = True):
    return {
        "assets": [
            {
                "imagery_frame_id": "frame-1",
                "asset_id": "asset-1",
                "file_name": "tiles/frame-1.png",
                "width": 100,
                "height": 100,
                "sha256": "a" * 64,
                "source_rights": {"training_use_allowed": rights, "storage_allowed": rights},
            }
        ]
    }


def _attested_quality_fixture():
    attestation = {
        "status": "third_party_benchmark_annotations",
        "dataset_name": "fixture benchmark",
        "license": "CC-BY-SA-4.0",
        "independent_test_split": True,
        "test_images_excluded_from_training": True,
    }
    evaluation_scope = {
        "geography_count": 5,
        "season_count": 2,
        "imagery_quality_band_count": 2,
    }
    parent = {
        "categories": [{"id": 1, "name": "building"}],
        "images": [
            {"id": 1, "file_name": "train.png", "split": "train", "source_sha256": "1" * 64},
            {"id": 2, "file_name": "validation.png", "split": "validation", "source_sha256": "2" * 64},
            {"id": 3, "file_name": "test.png", "split": "test", "source_sha256": "3" * 64},
        ],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 1, "bbox": [0, 0, 10, 10]},
            {"id": 2, "image_id": 2, "category_id": 1, "bbox": [0, 0, 10, 10]},
            {"id": 3, "image_id": 3, "category_id": 1, "bbox": [0, 0, 10, 10]},
        ],
        "splits": {"train": [1], "validation": [2], "test": [3]},
        "split_policy": {"strategy": "source_identity_disjoint", "test_split_frozen": True},
        "ground_truth_attestation": attestation,
        "evaluation_scope": evaluation_scope,
        "supervision_status": "independent_benchmark_annotated",
    }
    parent["dataset_fingerprint"] = coco_dataset_fingerprint(parent)
    parent["frozen_split_manifest"] = build_frozen_split_manifest(parent)
    parent_fingerprint = parent["dataset_fingerprint"]

    training = {
        **parent,
        "dataset_role": "training_and_validation",
        "parent_coco_evidence_fingerprint": parent_fingerprint,
        "images": [item for item in parent["images"] if item["split"] != "test"],
        "annotations": [item for item in parent["annotations"] if item["image_id"] != 3],
        "splits": {"train": [1], "validation": [2], "test": []},
        "held_out_test_manifest": build_held_out_test_commitment(parent["frozen_split_manifest"]),
        "test_records_in_package": False,
    }
    training.pop("frozen_split_manifest", None)
    training["dataset_fingerprint"] = coco_dataset_fingerprint(training)

    evaluation = {
        **parent,
        "dataset_role": "frozen_test",
        "parent_coco_evidence_fingerprint": parent_fingerprint,
        "images": [item for item in parent["images"] if item["split"] == "test"],
        "annotations": [item for item in parent["annotations"] if item["image_id"] == 3],
        "splits": {"train": [], "validation": [], "test": [3]},
        "training_records_in_package": False,
    }
    evaluation["dataset_fingerprint"] = coco_dataset_fingerprint(evaluation)
    evaluation["frozen_split_manifest"] = build_frozen_split_manifest(evaluation)
    integrity = assess_coco_evidence_integrity(evaluation, training_package=training)
    assert integrity["promotion_eligible"] is True
    reservation = build_evaluation_reservation_manifest(
        evaluation,
        training,
        evaluation_package_sha256="e" * 64,
        training_package_sha256="d" * 64,
        required_classes=["building"],
    )
    scope = {
        "source_supervision_status": "independent_benchmark_annotated",
        "promotion_eligible": True,
        "ground_truth_attestation": attestation,
        "evaluation_scope": evaluation_scope,
        "evidence_integrity": integrity,
    }
    return scope, reservation


def _attested_quality_scope():
    return _attested_quality_fixture()[0]


def _attach_promotion_evidence(
    quality,
    *,
    dataset_fingerprint="",
    model_artifact_sha256="a" * 64,
):
    _, reservation = _attested_quality_fixture()
    if (
        reservation["evaluation_dataset_fingerprint"]
        != quality["evidence_integrity"]["dataset_fingerprint"]
    ):
        raise ValueError("Fixture reservation must match its sealed integrity evidence.")
    quality["evaluation_reservation_manifest"] = reservation
    evidence_fingerprint = quality["evidence_integrity"]["dataset_fingerprint"]
    evaluation_fingerprint = dataset_fingerprint or evidence_fingerprint
    if evaluation_fingerprint != evidence_fingerprint:
        raise ValueError("Fixture evaluation fingerprint must match its sealed integrity evidence.")
    calibration = calibrate_detection_thresholds(
        [{"kind": "building", "geometry": _polygon(0, 0, 10, 10), "confidence": 0.9}],
        [{"kind": "building", "geometry": _polygon(0, 0, 10, 10)}],
        dataset_fingerprint=evaluation_fingerprint,
        confidence_values=[0.5],
        minimum_component_pixels_values=[1],
        ground_truth_attested=True,
        source_supervision_status="independent_benchmark_annotated",
        validation_dataset_fingerprint=evaluation_fingerprint,
        training_dataset_fingerprint=evaluation_fingerprint,
        validation_package_sha256="d" * 64,
        model_artifact_sha256=model_artifact_sha256,
    )
    baseline = {
        "evaluation_status": "measured_against_ground_truth",
        "evaluation_split": "test",
        "dataset_fingerprint": evaluation_fingerprint,
        "ground_truth_count": quality.get("ground_truth_count"),
        "prediction_count": quality.get("prediction_count", quality.get("ground_truth_count")),
        "true_positive": max(0, int(quality.get("true_positive") or 0) - 5),
        "false_positive": int(quality.get("false_positive") or 0),
        "false_negative": int(quality.get("false_negative") or 0) + 5,
        "precision": max(0.0, float(quality.get("precision") or 0.0) - 0.05),
        "recall": max(0.0, float(quality.get("recall") or 0.0) - 0.1),
        "f1": max(0.0, float(quality.get("f1") or 0.0) - 0.1),
        "mean_matched_iou": quality.get("mean_matched_iou"),
    }
    quality["evaluation_split"] = "test"
    quality["dataset_fingerprint"] = evaluation_fingerprint
    quality["validation_dataset_fingerprint"] = evaluation_fingerprint
    quality["training_dataset_fingerprint"] = evaluation_fingerprint
    quality["model_artifact_sha256"] = model_artifact_sha256
    quality["threshold_calibration"] = calibration
    quality["baseline_comparison"] = compare_model_to_baseline(quality, baseline)
    receipt = build_test_consumption_receipt(
        quality["evidence_integrity"],
        candidate_id="test-candidate:v1",
        model_artifact_sha256=model_artifact_sha256,
        threshold_calibration_fingerprint=calibration["calibration_fingerprint"],
        consumed_at="2026-08-13T12:00:00Z",
        evaluation_reservation_manifest=quality["evaluation_reservation_manifest"],
    )
    quality["test_consumption_receipt"] = receipt
    quality["test_consumption_ledger"] = append_test_consumption_receipt({}, receipt)
    return quality


class VisionModelLifecycleTests(unittest.TestCase):
    def test_coco_export_includes_reviewed_positive_and_negative_image_without_bytes(self) -> None:
        package = build_coco_training_package([_dataset()], asset_registry=_asset_registry())

        self.assertEqual(package["eligible_image_count"], 1)
        self.assertEqual(package["annotation_count"], 1)
        self.assertEqual(package["excluded_example_count"], 0)
        self.assertFalse(package["contains_image_bytes"])
        self.assertFalse(package["promotion_eligible"])
        self.assertIn("ground_truth_attestation_missing", package["promotion_blockers"])
        self.assertEqual(package["annotations"][0]["bbox"], [10.0, 10.0, 20.0, 25.0])
        self.assertEqual(len(package["dataset_fingerprint"]), 64)

        attested = build_coco_training_package(
            [_dataset()],
            asset_registry=_asset_registry(),
            ground_truth_attestation={
                "status": "human_reviewed_annotations",
                "dataset_name": "held-out fixture",
                "license": "internal-rights-cleared",
                "independent_test_split": True,
                "test_images_excluded_from_training": True,
            },
            evaluation_scope={"geography_count": 5, "season_count": 2, "imagery_quality_band_count": 2},
        )
        self.assertFalse(attested["promotion_eligible"])
        self.assertIn("evaluation_split_empty:test", attested["promotion_blockers"])

    def test_coco_export_blocks_source_without_training_or_storage_rights(self) -> None:
        package = build_coco_training_package(
            [_dataset(rights=False)],
            asset_registry=_asset_registry(rights=False),
        )

        self.assertEqual(package["eligible_image_count"], 0)
        self.assertEqual(package["excluded_example_count"], 2)
        blockers = {blocker for item in package["excluded_examples"] for blocker in item["blockers"]}
        self.assertIn("imagery_source_training_rights_not_confirmed", blockers)
        self.assertIn("imagery_source_storage_rights_not_confirmed", blockers)

    def test_quality_and_promotion_are_ground_truth_and_class_gated(self) -> None:
        truth = [
            {"kind": "building", "geometry": _polygon(index * 20, 0, index * 20 + 10, 10)}
            for index in range(120)
        ]
        quality = evaluate_quality_by_class(
            [{**item, "confidence": 0.9} for item in truth],
            truth,
            **_attested_quality_scope(),
        )
        _attach_promotion_evidence(quality)
        promotion = assess_model_promotion(quality, required_classes=["building"])

        self.assertEqual(quality["precision"], 1.0)
        self.assertEqual(quality["per_class"]["building"]["recall"], 1.0)
        self.assertTrue(promotion["eligible"])

        wrong_package = deepcopy(quality)
        wrong_package["threshold_calibration"]["validation_package_sha256"] = "b" * 64
        wrong_package["threshold_calibration"]["calibration_fingerprint"] = threshold_calibration_fingerprint(
            wrong_package["threshold_calibration"]
        )
        wrong_package_assessment = assess_model_promotion(wrong_package, required_classes=["building"])
        self.assertFalse(wrong_package_assessment["eligible"])
        self.assertIn(
            "threshold_calibration_validation_package_sha256_mismatch",
            wrong_package_assessment["blockers"],
        )

        blocked = assess_model_promotion({"evaluation_status": "ground_truth_not_attached"})
        self.assertFalse(blocked["eligible"])
        self.assertIn("ground_truth_evaluation_missing", blocked["blockers"])
        self.assertIn("validation_only_threshold_calibration_missing", blocked["blockers"])
        self.assertIn("held_out_baseline_comparison_missing", blocked["blockers"])

    def test_promotion_rejects_missing_or_post_hoc_test_consumption_evidence(self) -> None:
        truth = [
            {"kind": "building", "geometry": _polygon(index * 20, 0, index * 20 + 10, 10)}
            for index in range(120)
        ]
        quality = evaluate_quality_by_class(
            [{**item, "confidence": 0.9} for item in truth],
            truth,
            **_attested_quality_scope(),
        )
        _attach_promotion_evidence(quality)

        missing = dict(quality)
        missing.pop("test_consumption_receipt")
        missing.pop("test_consumption_ledger")
        missing_assessment = assess_model_promotion(missing, required_classes=["building"])
        self.assertIn("test_consumption_receipt_missing", missing_assessment["blockers"])
        self.assertIn("test_consumption_ledger_missing", missing_assessment["blockers"])

        post_hoc = dict(quality)
        receipt = build_test_consumption_receipt(
            quality["evidence_integrity"],
            candidate_id="legacy-rejection:v1",
            model_artifact_sha256=quality["model_artifact_sha256"],
            consumed_at="2026-08-13T12:00:00Z",
            reservation_mode="post_hoc_rejection_record",
        )
        post_hoc["test_consumption_receipt"] = receipt
        post_hoc["test_consumption_ledger"] = append_test_consumption_receipt({}, receipt)
        post_hoc_assessment = assess_model_promotion(post_hoc, required_classes=["building"])
        self.assertFalse(post_hoc_assessment["eligible"])
        self.assertFalse(post_hoc_assessment["test_consumption_receipt"]["promotion_eligible"])

    def test_promotion_blocks_narrow_coverage_and_reports_class_gate(self) -> None:
        quality = {
            "evaluation_status": "measured_against_ground_truth",
            "precision": 0.95,
            "recall": 0.90,
            "f1": 0.92,
            "mean_matched_iou": 0.80,
            "ground_truth_count": 120,
            "per_class": {"building": {"precision": 0.90, "recall": 0.80, "ground_truth_count": 120}},
            **_attested_quality_scope(),
        }
        quality["evaluation_scope"] = {
            "geography_count": 4,
            "season_count": 0,
            "imagery_quality_band_count": 1,
        }
        _attach_promotion_evidence(quality)

        promotion = assess_model_promotion(quality, required_classes=["building"])

        self.assertFalse(promotion["eligible"])
        self.assertEqual(promotion["eligible_classes"], ["building"])
        self.assertIn("geographic_coverage_below_promotion_threshold", promotion["blockers"])
        self.assertIn("seasonal_coverage_below_promotion_threshold", promotion["blockers"])

    def test_attestation_rejects_weak_or_train_overlapping_labels(self) -> None:
        assessment = assess_ground_truth_attestation(
            {
                "supervision_status": "weak_public_footprint_labels",
                "promotion_eligible": False,
                "ground_truth_attestation": {"independent_test_split": False},
            }
        )

        self.assertFalse(assessment["eligible"])
        self.assertIn("reviewed_or_independent_ground_truth_missing", assessment["blockers"])
        self.assertIn("independent_test_split_not_attested", assessment["blockers"])

    def test_weak_diagnostic_status_is_preserved_per_class(self) -> None:
        truth = [{"kind": "building", "geometry": _polygon(0, 0, 10, 10)}]

        quality = evaluate_quality_by_class(
            [{**truth[0], "confidence": 0.9}],
            truth,
            evaluation_status="unattested_or_weak_label_diagnostic",
        )

        self.assertEqual(quality["evaluation_status"], "unattested_or_weak_label_diagnostic")
        self.assertEqual(
            quality["per_class"]["building"]["evaluation_status"],
            "unattested_or_weak_label_diagnostic",
        )

    def test_quality_uses_model_category_over_source_feature_type_alias(self) -> None:
        truth = [
            {
                "kind": "building",
                "feature_type": "building_footprint",
                "geometry": _polygon(0, 0, 10, 10),
            },
            {
                "kind": "road",
                "feature_type": "road_or_drive",
                "geometry": _polygon(20, 0, 40, 10),
            },
            {
                "kind": "water",
                "feature_type": "water/pond/basin",
                "geometry": _polygon(50, 0, 65, 15),
            },
        ]
        predictions = [
            {"kind": item["kind"], "geometry": item["geometry"], "confidence": 0.9}
            for item in truth
        ]

        quality = evaluate_quality_by_class(
            predictions,
            truth,
            evaluation_status="unattested_or_weak_label_diagnostic",
        )

        self.assertEqual(quality["true_positive"], 3)
        self.assertEqual(quality["precision"], 1.0)
        self.assertEqual(quality["recall"], 1.0)
        self.assertEqual(sorted(quality["per_class"]), ["building", "road", "surface_water"])
        self.assertEqual(truth[0]["feature_type"], "building_footprint")

    def test_manifest_is_promoted_only_with_quality_provenance_and_approver(self) -> None:
        quality = {
            "evaluation_status": "measured_against_ground_truth",
            "precision": 0.9,
            "recall": 0.85,
            "f1": 0.87,
            "mean_matched_iou": 0.7,
            "ground_truth_count": 100,
            "per_class": {"building": {"precision": 0.9, "recall": 0.8, "ground_truth_count": 100}},
            **_attested_quality_scope(),
        }
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "model.onnx"
            model.write_bytes(b"model-weights")
            _attach_promotion_evidence(
                quality,
                model_artifact_sha256=hashlib.sha256(b"model-weights").hexdigest(),
            )
            manifest = build_model_manifest(
                model_path=model,
                model_name="civora-semantic",
                model_version="v1",
                classes={0: "background", 1: "building"},
                quality_report=quality,
                dataset_fingerprint="b" * 64,
                evaluation_dataset_fingerprint=quality["dataset_fingerprint"],
                approved_by="model-reviewer",
                model_license="internal-rights-cleared",
                training_code_revision="abc123",
                adapter="civora_semantic_v1",
                required_classes=["building"],
            )

        self.assertEqual(manifest["promotion"]["status"], "approved_for_review_candidates")
        self.assertTrue(manifest["promotion"]["evidence_eligible"])
        self.assertTrue(manifest["promotion"]["eligible"])
        self.assertEqual(manifest["adapter"], "civora_semantic_v1")
        self.assertEqual(len(manifest["artifact"]["weights_sha256"]), 64)

    def test_manifest_does_not_report_eligible_when_human_approver_is_missing(self) -> None:
        quality = {
            "evaluation_status": "measured_against_ground_truth",
            "precision": 0.9,
            "recall": 0.85,
            "f1": 0.87,
            "mean_matched_iou": 0.7,
            "ground_truth_count": 100,
            "per_class": {"building": {"precision": 0.9, "recall": 0.8, "ground_truth_count": 100}},
            **_attested_quality_scope(),
        }
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "model.onnx"
            model.write_bytes(b"model-weights")
            _attach_promotion_evidence(
                quality,
                model_artifact_sha256=hashlib.sha256(b"model-weights").hexdigest(),
            )
            manifest = build_model_manifest(
                model_path=model,
                model_name="candidate",
                model_version="v1",
                classes={0: "background", 1: "building"},
                quality_report=quality,
                dataset_fingerprint="b" * 64,
                evaluation_dataset_fingerprint=quality["dataset_fingerprint"],
                approved_by="",
                model_license="internal-rights-cleared",
                training_code_revision="abc123",
                adapter="civora_semantic_v1",
                required_classes=["building"],
            )

        self.assertTrue(manifest["promotion"]["evidence_eligible"])
        self.assertFalse(manifest["promotion"]["eligible"])
        self.assertEqual(manifest["promotion"]["status"], "candidate_blocked")
        self.assertIn("model_approver_missing", manifest["promotion"]["blockers"])

    def test_manifest_keeps_training_and_evaluation_dataset_identities_separate(self) -> None:
        quality = {
            "evaluation_status": "measured_against_ground_truth",
            "precision": 0.9,
            "recall": 0.85,
            "f1": 0.87,
            "mean_matched_iou": 0.7,
            "ground_truth_count": 100,
            "per_class": {"building": {"precision": 0.9, "recall": 0.8, "ground_truth_count": 100}},
            **_attested_quality_scope(),
        }
        evaluation_fingerprint = quality["evidence_integrity"]["dataset_fingerprint"]
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "model.onnx"
            model.write_bytes(b"model-weights")
            _attach_promotion_evidence(
                quality,
                dataset_fingerprint=evaluation_fingerprint,
                model_artifact_sha256=hashlib.sha256(b"model-weights").hexdigest(),
            )
            manifest = build_model_manifest(
                model_path=model,
                model_name="separate-evidence",
                model_version="v1",
                classes={0: "background", 1: "building"},
                quality_report=quality,
                dataset_fingerprint="d" * 64,
                evaluation_dataset_fingerprint=evaluation_fingerprint,
                approved_by="model-reviewer",
                model_license="internal-rights-cleared",
                training_code_revision="abc123",
                adapter="civora_semantic_v1",
                required_classes=["building"],
            )

        self.assertEqual(manifest["provenance"]["training_dataset_fingerprint"], "d" * 64)
        self.assertEqual(manifest["provenance"]["evaluation_dataset_fingerprint"], evaluation_fingerprint)


if __name__ == "__main__":
    unittest.main()
