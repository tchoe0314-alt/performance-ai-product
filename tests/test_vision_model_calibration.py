from __future__ import annotations

from copy import deepcopy
import unittest

from backend.planning.vision_model_calibration import (
    calibrate_detection_thresholds,
    compare_model_to_baseline,
    threshold_calibration_fingerprint,
    validate_baseline_comparison,
    validate_threshold_calibration,
)


def _polygon(x0: float, y0: float, x1: float, y1: float):
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


class VisionModelCalibrationTests(unittest.TestCase):
    def test_calibration_selects_validation_thresholds_and_fingerprint_detects_tampering(self) -> None:
        truth = [
            {"image_id": 1, "kind": "building", "geometry": _polygon(0, 0, 10, 10)},
            {"image_id": 1, "kind": "building", "geometry": _polygon(20, 20, 30, 30)},
        ]
        predictions = [
            {
                **truth[0],
                "confidence": 0.92,
                "properties": {"component_pixel_count": 100},
            },
            {
                **truth[1],
                "confidence": 0.70,
                "properties": {"component_pixel_count": 80},
            },
            {
                "image_id": 1,
                "kind": "building",
                "geometry": _polygon(50, 50, 60, 60),
                "confidence": 0.30,
                "properties": {"component_pixel_count": 90},
            },
        ]

        calibration = calibrate_detection_thresholds(
            predictions,
            truth,
            dataset_fingerprint="a" * 64,
            confidence_values=[0.2, 0.5, 0.8],
            minimum_component_pixels_values=[20, 120],
            precision_floor=0.8,
            ground_truth_attested=True,
            source_supervision_status="reviewer_labeled",
            validation_dataset_fingerprint="v" * 64,
            training_dataset_fingerprint="t" * 64,
            validation_package_sha256="c" * 64,
            model_artifact_sha256="m" * 64,
        )

        self.assertEqual(calibration["evaluation_split"], "validation")
        self.assertFalse(calibration["test_data_used"])
        self.assertEqual(
            calibration["chosen_thresholds"],
            {"confidence": 0.5, "minimum_component_pixels": 20, "mask": 0.5},
        )
        self.assertTrue(
            validate_threshold_calibration(
                calibration,
                dataset_fingerprint="a" * 64,
                validation_dataset_fingerprint="v" * 64,
                training_dataset_fingerprint="t" * 64,
                validation_package_sha256="c" * 64,
                model_artifact_sha256="m" * 64,
            )["valid"]
        )

        wrong_model = validate_threshold_calibration(
            calibration,
            dataset_fingerprint="a" * 64,
            model_artifact_sha256="x" * 64,
        )
        self.assertIn("threshold_calibration_model_artifact_mismatch", wrong_model["blockers"])

        wrong_validation_package = validate_threshold_calibration(
            calibration,
            dataset_fingerprint="a" * 64,
            validation_dataset_fingerprint="x" * 64,
        )
        self.assertIn(
            "threshold_calibration_validation_dataset_mismatch",
            wrong_validation_package["blockers"],
        )

        wrong_validation_bytes = validate_threshold_calibration(
            calibration,
            dataset_fingerprint="a" * 64,
            validation_package_sha256="x" * 64,
        )
        self.assertIn(
            "threshold_calibration_validation_package_sha256_mismatch",
            wrong_validation_bytes["blockers"],
        )

        tampered = deepcopy(calibration)
        tampered["chosen_thresholds"]["confidence"] = 0.1
        validation = validate_threshold_calibration(tampered, dataset_fingerprint="a" * 64)
        self.assertFalse(validation["valid"])
        self.assertIn("threshold_calibration_fingerprint_mismatch", validation["blockers"])

        smuggled = deepcopy(calibration)
        smuggled["test_annotation_count"] = 42
        smuggled["calibration_fingerprint"] = threshold_calibration_fingerprint(smuggled)
        validation = validate_threshold_calibration(smuggled, dataset_fingerprint="a" * 64)
        self.assertFalse(validation["valid"])
        self.assertIn("threshold_calibration_schema_mismatch", validation["blockers"])

    def test_weak_calibration_remains_ineligible_for_promotion(self) -> None:
        calibration = calibrate_detection_thresholds(
            [],
            [],
            dataset_fingerprint="b" * 64,
            confidence_values=[0.5],
            minimum_component_pixels_values=[24],
            ground_truth_attested=False,
            source_supervision_status="weak_labels_pending_review",
        )

        self.assertFalse(calibration["promotion_eligible"])
        validation = validate_threshold_calibration(calibration, dataset_fingerprint="b" * 64)
        self.assertIn("threshold_calibration_not_promotion_eligible", validation["blockers"])

    def test_reviewed_validation_labels_are_sufficient_without_claiming_test_quality(self) -> None:
        truth = [{"image_id": 1, "kind": "building", "geometry": _polygon(0, 0, 10, 10)}]
        calibration = calibrate_detection_thresholds(
            [{**truth[0], "confidence": 0.9, "properties": {"component_pixel_count": 100}}],
            truth,
            dataset_fingerprint="a" * 64,
            confidence_values=[0.5],
            minimum_component_pixels_values=[24],
            ground_truth_attested=False,
            validation_labels_reviewed=True,
            source_supervision_status="reviewer_labeled",
            validation_package_sha256="c" * 64,
        )

        self.assertTrue(calibration["promotion_eligible"])
        self.assertTrue(calibration["validation_labels_reviewed"])
        self.assertFalse(calibration["ground_truth_attested"])
        self.assertEqual(calibration["chosen_quality"]["evaluation_status"], "measured_on_validation_split")
        self.assertTrue(
            validate_threshold_calibration(calibration, dataset_fingerprint="a" * 64)["valid"]
        )

    def test_baseline_gate_requires_real_gain_without_more_false_positives(self) -> None:
        baseline = {
            "evaluation_status": "measured_against_ground_truth",
            "evaluation_split": "test",
            "dataset_fingerprint": "c" * 64,
            "ground_truth_count": 100,
            "prediction_count": 90,
            "true_positive": 80,
            "false_positive": 10,
            "false_negative": 20,
            "precision": 0.8889,
            "recall": 0.8,
            "f1": 0.8421,
            "mean_matched_iou": 0.7,
        }
        improved = {
            **baseline,
            "prediction_count": 94,
            "true_positive": 86,
            "false_positive": 8,
            "false_negative": 14,
            "precision": 0.9149,
            "recall": 0.86,
            "f1": 0.8866,
            "mean_matched_iou": 0.72,
        }
        comparison = compare_model_to_baseline(improved, baseline)
        self.assertTrue(comparison["eligible"])
        self.assertTrue(validate_baseline_comparison(comparison, model_quality=improved)["valid"])

        regressed = {**improved, "false_positive": 12, "precision": 0.8776}
        blocked = compare_model_to_baseline(regressed, baseline)
        self.assertFalse(blocked["eligible"])
        self.assertIn("learned_model_false_positives_exceed_baseline_gate", blocked["blockers"])


if __name__ == "__main__":
    unittest.main()
