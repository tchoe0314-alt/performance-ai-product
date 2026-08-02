from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.planning.vision_model_lifecycle import (
    assess_model_promotion,
    build_coco_training_package,
    build_model_manifest,
    evaluate_quality_by_class,
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


class VisionModelLifecycleTests(unittest.TestCase):
    def test_coco_export_includes_reviewed_positive_and_negative_image_without_bytes(self) -> None:
        package = build_coco_training_package([_dataset()], asset_registry=_asset_registry())

        self.assertEqual(package["eligible_image_count"], 1)
        self.assertEqual(package["annotation_count"], 1)
        self.assertEqual(package["excluded_example_count"], 0)
        self.assertFalse(package["contains_image_bytes"])
        self.assertEqual(package["annotations"][0]["bbox"], [10.0, 10.0, 20.0, 25.0])
        self.assertEqual(len(package["dataset_fingerprint"]), 64)

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
            for index in range(30)
        ]
        quality = evaluate_quality_by_class(
            [{**item, "confidence": 0.9} for item in truth],
            truth,
        )
        promotion = assess_model_promotion(quality, required_classes=["building"])

        self.assertEqual(quality["precision"], 1.0)
        self.assertEqual(quality["per_class"]["building"]["recall"], 1.0)
        self.assertTrue(promotion["eligible"])

        blocked = assess_model_promotion({"evaluation_status": "ground_truth_not_attached"})
        self.assertFalse(blocked["eligible"])
        self.assertIn("ground_truth_evaluation_missing", blocked["blockers"])

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

    def test_manifest_is_promoted_only_with_quality_provenance_and_approver(self) -> None:
        quality = {
            "evaluation_status": "measured_against_ground_truth",
            "precision": 0.9,
            "recall": 0.85,
            "f1": 0.87,
            "mean_matched_iou": 0.7,
            "ground_truth_count": 100,
            "per_class": {"building": {"recall": 0.8}},
        }
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "model.onnx"
            model.write_bytes(b"model-weights")
            manifest = build_model_manifest(
                model_path=model,
                model_name="civora-semantic",
                model_version="v1",
                classes={0: "background", 1: "building"},
                quality_report=quality,
                dataset_fingerprint="b" * 64,
                approved_by="model-reviewer",
                model_license="internal-rights-cleared",
                training_code_revision="abc123",
                adapter="civora_semantic_v1",
                required_classes=["building"],
            )

        self.assertEqual(manifest["promotion"]["status"], "approved_for_review_candidates")
        self.assertEqual(manifest["adapter"], "civora_semantic_v1")
        self.assertEqual(len(manifest["artifact"]["weights_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
