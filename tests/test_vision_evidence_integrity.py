from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from backend.planning.vision_evidence_integrity import (
    append_test_consumption_receipt,
    assess_coco_evidence_integrity,
    build_frozen_split_manifest,
    build_split_scoped_coco_evidence_packages,
    build_evaluation_reservation_manifest,
    build_test_consumption_receipt,
    build_held_out_test_commitment,
    coco_dataset_fingerprint,
    declared_coco_evidence_fingerprint,
    evaluation_reservation_fingerprint,
    reserve_test_consumption,
    test_consumption_ledger_fingerprint as ledger_fingerprint,
    test_consumption_receipt_fingerprint as receipt_fingerprint,
    validate_evaluation_reservation_manifest,
    validate_evidence_integrity_report,
    validate_reservation_against_evidence,
    validate_training_package_against_reservation,
    validate_test_consumption_ledger,
    validate_test_consumption_receipt,
)
from backend.planning.vision_ground_truth_flywheel import (
    build_privacy_safe_correction_aggregate,
    validate_privacy_safe_correction_aggregate,
)
from backend.planning.vision_model_lifecycle import assess_ground_truth_attestation


def _package() -> dict:
    package = {
        "categories": [
            {"id": 1, "name": "building"},
            {"id": 2, "name": "road"},
            {"id": 3, "name": "surface_water"},
        ],
        "images": [
            {"id": 1, "file_name": "train.png", "split": "train", "source_sha256": "1" * 64},
            {"id": 2, "file_name": "validation.png", "split": "validation", "source_sha256": "2" * 64},
            {"id": 3, "file_name": "test.png", "split": "test", "source_sha256": "3" * 64},
        ],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 1, "bbox": [0, 0, 10, 10]},
            {"id": 2, "image_id": 2, "category_id": 2, "bbox": [0, 0, 10, 10]},
            {"id": 3, "image_id": 3, "category_id": 1, "bbox": [0, 0, 10, 10]},
            {"id": 4, "image_id": 3, "category_id": 2, "bbox": [20, 0, 10, 10]},
            {"id": 5, "image_id": 3, "category_id": 3, "bbox": [40, 0, 10, 10]},
        ],
        "splits": {"train": [1], "validation": [2], "test": [3]},
        "split_policy": {"strategy": "source_identity_disjoint", "test_split_frozen": True},
    }
    package["dataset_fingerprint"] = coco_dataset_fingerprint(package)
    package["frozen_split_manifest"] = build_frozen_split_manifest(package)
    return package


def _scoped_packages() -> tuple[dict, dict]:
    parent = _package()
    parent_fingerprint = parent["dataset_fingerprint"]
    held_out_manifest = build_held_out_test_commitment(parent["frozen_split_manifest"])
    development = deepcopy(parent)
    development["dataset_role"] = "training_and_validation"
    development["test_records_in_package"] = False
    development["parent_coco_evidence_fingerprint"] = parent_fingerprint
    development["images"] = [item for item in development["images"] if item["split"] != "test"]
    development["annotations"] = [item for item in development["annotations"] if item["image_id"] != 3]
    development["splits"] = {"train": [1], "validation": [2], "test": []}
    development.pop("frozen_split_manifest", None)
    development["held_out_test_manifest"] = held_out_manifest
    development["dataset_fingerprint"] = coco_dataset_fingerprint(development)

    evaluation = deepcopy(parent)
    evaluation["dataset_role"] = "frozen_test"
    evaluation["training_records_in_package"] = False
    evaluation["parent_coco_evidence_fingerprint"] = parent_fingerprint
    evaluation["images"] = [item for item in evaluation["images"] if item["split"] == "test"]
    evaluation["annotations"] = [item for item in evaluation["annotations"] if item["image_id"] == 3]
    evaluation["splits"] = {"train": [], "validation": [], "test": [3]}
    evaluation["dataset_fingerprint"] = coco_dataset_fingerprint(evaluation)
    evaluation["frozen_split_manifest"] = build_frozen_split_manifest(evaluation)
    return development, evaluation


def _reservation(training: dict, evaluation: dict) -> dict:
    return build_evaluation_reservation_manifest(
        evaluation,
        training,
        evaluation_package_sha256="e" * 64,
        training_package_sha256="d" * 64,
        required_classes=["building", "road", "surface_water"],
    )


class VisionEvidenceIntegrityTests(unittest.TestCase):
    def test_evaluation_reservation_is_label_free_tamper_evident_and_package_bound(self) -> None:
        training, evaluation = _scoped_packages()
        reservation = _reservation(training, evaluation)

        validation = validate_evaluation_reservation_manifest(
            reservation,
            evaluation_package_sha256="e" * 64,
            training_package_sha256="d" * 64,
        )
        self.assertTrue(validation["valid"])
        self.assertTrue(
            validate_reservation_against_evidence(
                reservation,
                evaluation,
                training,
                evaluation_package_sha256="e" * 64,
                training_package_sha256="d" * 64,
                required_classes=["building", "road", "surface_water"],
            )["valid"]
        )
        encoded = json.dumps(reservation)
        self.assertFalse(reservation["contains_image_records"])
        self.assertFalse(reservation["contains_annotation_records"])
        self.assertFalse(reservation["label_statistics_disclosed"])
        for forbidden in (
            '"images"',
            '"annotations"',
            '"bbox"',
            '"file_name"',
            '"source_url"',
            '"test_annotation_count"',
            '"evaluation_annotation_count"',
            '"evidence_integrity"',
        ):
            self.assertNotIn(forbidden, encoded)

        tampered = deepcopy(reservation)
        tampered["required_model_classes"] = ["building"]
        self.assertFalse(validate_evaluation_reservation_manifest(tampered)["valid"])
        leaked = deepcopy(reservation)
        leaked["test_annotation_count"] = 3
        leaked["manifest_sha256"] = evaluation_reservation_fingerprint(leaked)
        leaked_validation = validate_evaluation_reservation_manifest(leaked)
        self.assertFalse(leaked_validation["valid"])
        self.assertIn(
            "evaluation_reservation_unknown_field:test_annotation_count",
            leaked_validation["blockers"],
        )
        self.assertFalse(
            validate_evaluation_reservation_manifest(
                reservation,
                evaluation_package_sha256="f" * 64,
            )["valid"]
        )

    def test_scoping_fails_when_a_required_class_is_absent_from_development(self) -> None:
        package = _package()
        package["annotations"] = [
            item
            for item in package["annotations"]
            if item["category_id"] != 3 or item["image_id"] == 3
        ]
        package["dataset_fingerprint"] = coco_dataset_fingerprint(package)
        package["frozen_split_manifest"] = build_frozen_split_manifest(package)

        with self.assertRaisesRegex(ValueError, "train:surface_water"):
            build_split_scoped_coco_evidence_packages(
                package,
                required_classes=["building", "road", "surface_water"],
            )

    def test_scoped_development_package_drops_unrecognized_test_metadata(self) -> None:
        package = _package()
        package["leaked_test_labels"] = [{"image_id": 3, "category_id": 1}]
        package["source_artifacts"] = [{"split": "test", "source_label_sha256": "f" * 64}]
        package["images"][0]["leaked_test_labels"] = [{"image_id": 3, "category_id": 1}]
        package["annotations"][0]["test_geography"] = "hidden-test-city"
        package["categories"][0]["test_class_count"] = 99
        package["licenses"] = [
            {
                "id": 1,
                "name": "fixture",
                "source_rights": {
                    "training_use_allowed": True,
                    "hidden_test_location": "hidden-test-city",
                },
                "hidden_test_labels": [1, 2, 3],
            }
        ]
        package["dataset_fingerprint"] = coco_dataset_fingerprint(package)
        package["frozen_split_manifest"] = build_frozen_split_manifest(package)

        scoped = build_split_scoped_coco_evidence_packages(
            package,
            required_classes=[],
        )
        training = scoped["training_validation"]

        self.assertNotIn("leaked_test_labels", training)
        self.assertNotIn("source_artifacts", training)
        self.assertNotIn("evaluation_scope", training)
        self.assertEqual(training["splits"]["test"], [])
        self.assertFalse(training["test_records_in_package"])
        encoded = json.dumps(training)
        self.assertNotIn("leaked_test_labels", encoded)
        self.assertNotIn("hidden_test_labels", encoded)
        self.assertNotIn("hidden-test-city", encoded)
        self.assertNotIn("test_class_count", encoded)

    def test_complete_package_passes_and_report_is_tamper_evident(self) -> None:
        training, package = _scoped_packages()

        report = assess_coco_evidence_integrity(
            package,
            training_package=training,
            required_classes=["building", "road", "surface_water"],
        )

        self.assertTrue(report["promotion_eligible"])
        self.assertTrue(validate_evidence_integrity_report(report)["valid"])
        tampered = deepcopy(report)
        tampered["split_counts"]["test"] = 999
        self.assertFalse(validate_evidence_integrity_report(tampered)["valid"])

    def test_same_source_under_different_name_cannot_cross_train_test(self) -> None:
        training, package = _scoped_packages()
        training["images"][0]["source_sha256"] = "3" * 64
        training["dataset_fingerprint"] = coco_dataset_fingerprint(training)

        report = assess_coco_evidence_integrity(package, training_package=training)

        self.assertFalse(report["promotion_eligible"])
        self.assertIn("development_test_source_identity_overlap", report["blockers"])

    def test_validation_source_cannot_overlap_frozen_test(self) -> None:
        training, evaluation = _scoped_packages()
        training["images"][1]["source_sha256"] = "3" * 64
        training["dataset_fingerprint"] = coco_dataset_fingerprint(training)

        report = assess_coco_evidence_integrity(evaluation, training_package=training)

        self.assertFalse(report["promotion_eligible"])
        self.assertEqual(report["development_test_source_identity_overlap_count"], 1)
        self.assertIn("development_test_source_identity_overlap", report["blockers"])

    def test_scoped_packages_bind_the_same_held_out_identity(self) -> None:
        training, evaluation = _scoped_packages()

        report = assess_coco_evidence_integrity(evaluation, training_package=training)

        self.assertTrue(report["promotion_eligible"])
        self.assertTrue(report["training_held_out_manifest_bound"])

        training["held_out_test_manifest"]["test_image_ids_sha256"] = "f" * 64
        tampered = assess_coco_evidence_integrity(evaluation, training_package=training)
        self.assertFalse(tampered["promotion_eligible"])
        self.assertIn("training_held_out_manifest_mismatch", tampered["blockers"])

    def test_training_package_preflight_is_label_blind_and_package_bound(self) -> None:
        training, evaluation = _scoped_packages()
        reservation = _reservation(training, evaluation)
        held_out = training["held_out_test_manifest"]

        self.assertFalse(held_out["label_statistics_disclosed"])
        self.assertNotIn("test_annotation_count", held_out)
        self.assertNotIn("annotations", held_out)
        self.assertTrue(
            validate_training_package_against_reservation(
                reservation,
                training,
                training_package_sha256="d" * 64,
            )["valid"]
        )

        tampered = deepcopy(training)
        tampered["held_out_test_manifest"]["test_image_count"] = 2
        result = validate_training_package_against_reservation(
            reservation,
            tampered,
            training_package_sha256="d" * 64,
        )
        self.assertFalse(result["valid"])

        leaked = deepcopy(training)
        leaked_held_out = leaked["held_out_test_manifest"]
        leaked_held_out["test_annotation_count"] = 3
        leaked_held_out["manifest_sha256"] = hashlib.sha256(
            json.dumps(
                {key: value for key, value in leaked_held_out.items() if key != "manifest_sha256"},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        leaked_result = validate_training_package_against_reservation(
            reservation,
            leaked,
            training_package_sha256="d" * 64,
        )
        self.assertFalse(leaked_result["valid"])
        self.assertIn(
            "training_held_out_manifest_unknown_field:test_annotation_count",
            leaked_result["blockers"],
        )
        self.assertIn("training_held_out_manifest_fingerprint_invalid", result["blockers"])
        self.assertIn("training_held_out_manifest_reservation_mismatch", result["blockers"])

    def test_frozen_test_consumption_receipt_and_ledger_are_tamper_evident_and_one_way(self) -> None:
        training, package = _scoped_packages()
        integrity = assess_coco_evidence_integrity(package, training_package=training)
        receipt = build_test_consumption_receipt(
            integrity,
            candidate_id="civora-v3:strict-1",
            model_artifact_sha256="a" * 64,
            threshold_calibration_fingerprint="c" * 64,
            consumed_at="2026-08-13T12:00:00Z",
            evaluation_reservation_manifest=_reservation(training, package),
        )

        self.assertTrue(
            validate_test_consumption_receipt(
                receipt,
                threshold_calibration_fingerprint="c" * 64,
            )["valid"]
        )
        with self.assertRaisesRegex(ValueError, "calibration fingerprint is required"):
            build_test_consumption_receipt(
                integrity,
                candidate_id="civora-v3:missing-calibration",
                model_artifact_sha256="a" * 64,
                consumed_at="2026-08-13T12:00:00Z",
                evaluation_reservation_manifest=_reservation(training, package),
            )
        wrong_calibration = deepcopy(receipt)
        wrong_calibration["threshold_calibration_fingerprint"] = "d" * 64
        wrong_calibration["receipt_sha256"] = receipt_fingerprint(wrong_calibration)
        wrong_calibration_validation = validate_test_consumption_receipt(
            wrong_calibration,
            threshold_calibration_fingerprint="c" * 64,
        )
        self.assertFalse(wrong_calibration_validation["valid"])
        self.assertIn(
            "test_consumption_threshold_calibration_fingerprint_mismatch",
            wrong_calibration_validation["blockers"],
        )
        ledger = append_test_consumption_receipt({}, receipt)
        self.assertTrue(validate_test_consumption_ledger(ledger)["valid"])
        leaked_receipt = deepcopy(receipt)
        leaked_receipt["test_annotation_count"] = 3
        leaked_receipt["receipt_sha256"] = receipt_fingerprint(leaked_receipt)
        leaked_receipt_validation = validate_test_consumption_receipt(leaked_receipt)
        self.assertFalse(leaked_receipt_validation["valid"])
        self.assertIn(
            "test_consumption_receipt_unknown_field:test_annotation_count",
            leaked_receipt_validation["blockers"],
        )
        leaked_ledger = deepcopy(ledger)
        leaked_ledger["test_annotation_count"] = 3
        leaked_ledger["ledger_sha256"] = ledger_fingerprint(leaked_ledger)
        leaked_ledger_validation = validate_test_consumption_ledger(leaked_ledger)
        self.assertFalse(leaked_ledger_validation["valid"])
        self.assertIn(
            "test_consumption_ledger_unknown_field:test_annotation_count",
            leaked_ledger_validation["blockers"],
        )
        with self.assertRaisesRegex(ValueError, "already been consumed"):
            append_test_consumption_receipt(ledger, receipt)

        tampered = deepcopy(receipt)
        tampered["candidate_id"] = "different-candidate"
        self.assertFalse(validate_test_consumption_receipt(tampered)["valid"])

        with tempfile.TemporaryDirectory() as directory:
            ledger_path = Path(directory) / "frozen-test-ledger.json"
            reservation = reserve_test_consumption(ledger_path, receipt)
            self.assertTrue(reservation["created"])
            self.assertTrue(validate_test_consumption_ledger(json.loads(ledger_path.read_text()))["valid"])
            with self.assertRaisesRegex(ValueError, "cannot be reopened"):
                reserve_test_consumption(ledger_path, receipt)

        repackaged = deepcopy(package)
        repackaged["categories"].append({"id": 4, "name": "unused_repackaging_marker"})
        repackaged["dataset_fingerprint"] = coco_dataset_fingerprint(repackaged)
        repackaged["frozen_split_manifest"] = build_frozen_split_manifest(repackaged)
        repackaged_integrity = assess_coco_evidence_integrity(
            repackaged,
            training_package=training,
        )
        repackaged_receipt = build_test_consumption_receipt(
            repackaged_integrity,
            candidate_id="civora-v4:repackaged",
            model_artifact_sha256="b" * 64,
            threshold_calibration_fingerprint="c" * 64,
            consumed_at="2026-08-14T12:00:00Z",
            evaluation_reservation_manifest=_reservation(training, repackaged),
        )
        with self.assertRaisesRegex(ValueError, "already been consumed"):
            append_test_consumption_receipt(ledger, repackaged_receipt)

    def test_post_hoc_receipt_records_rejection_but_cannot_be_atomically_reserved(self) -> None:
        training, package = _scoped_packages()
        integrity = assess_coco_evidence_integrity(package, training_package=training)
        receipt = build_test_consumption_receipt(
            integrity,
            candidate_id="legacy-rejected:v1",
            model_artifact_sha256="a" * 64,
            consumed_at="2026-08-13T12:00:00Z",
            reservation_mode="post_hoc_rejection_record",
        )

        validation = validate_test_consumption_receipt(receipt)
        self.assertTrue(validation["valid"])
        self.assertFalse(validation["promotion_eligible"])
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "pre-evaluation"):
                reserve_test_consumption(Path(directory) / "ledger.json", receipt)

    def test_duplicate_split_membership_and_frozen_manifest_tampering_fail(self) -> None:
        package = _package()
        package["splits"]["train"].append(3)
        package["frozen_split_manifest"]["test_image_count"] = 0

        report = assess_coco_evidence_integrity(package, training_package=package)

        self.assertFalse(report["promotion_eligible"])
        self.assertIn("image_id_overlap:train:test", report["blockers"])
        self.assertIn("frozen_test_split_manifest_invalid", report["blockers"])

    def test_required_class_must_be_present_on_evaluation_split(self) -> None:
        package = _package()
        package["annotations"] = [item for item in package["annotations"] if item["category_id"] != 3]
        package["dataset_fingerprint"] = coco_dataset_fingerprint(package)
        package["frozen_split_manifest"] = build_frozen_split_manifest(package)

        report = assess_coco_evidence_integrity(
            package,
            training_package=package,
            required_classes=["building", "road", "surface_water"],
        )

        self.assertIn("required_class_missing_from_evaluation_split:surface_water", report["blockers"])

    def test_legacy_water_category_satisfies_canonical_surface_water_requirement(self) -> None:
        training, package = _scoped_packages()
        package["categories"][2]["name"] = "water"
        package["dataset_fingerprint"] = coco_dataset_fingerprint(package)
        package["frozen_split_manifest"] = build_frozen_split_manifest(package)

        report = assess_coco_evidence_integrity(
            package,
            training_package=training,
            required_classes=["building", "road", "surface_water"],
        )

        self.assertTrue(report["promotion_eligible"])
        self.assertIn("surface_water", report["evaluation_classes"])

    def test_weak_package_can_bind_a_distinct_coco_evidence_fingerprint(self) -> None:
        training, package = _scoped_packages()
        package["dataset_fingerprint"] = "weak-package-fingerprint"
        package["coco_evidence_fingerprint"] = coco_dataset_fingerprint(package)
        package["frozen_split_manifest"] = build_frozen_split_manifest(package)

        report = assess_coco_evidence_integrity(package, training_package=training)

        self.assertTrue(report["promotion_eligible"])
        self.assertEqual(report["dataset_fingerprint"], package["coco_evidence_fingerprint"])
        self.assertEqual(
            declared_coco_evidence_fingerprint(package),
            package["coco_evidence_fingerprint"],
        )

    def test_attestation_cannot_change_after_integrity_report_is_sealed(self) -> None:
        training, package = _scoped_packages()
        package["supervision_status"] = "independent_benchmark_annotated"
        package["ground_truth_attestation"] = {
            "status": "third_party_benchmark_annotations",
            "dataset_name": "fixture",
            "license": "CC-BY-SA-4.0",
            "independent_test_split": True,
            "test_images_excluded_from_training": True,
        }
        package["evaluation_scope"] = {
            "geography_count": 5,
            "season_count": 2,
            "imagery_quality_band_count": 2,
        }
        package["evidence_integrity"] = assess_coco_evidence_integrity(package, training_package=training)
        package["promotion_eligible"] = True

        package["ground_truth_attestation"]["dataset_name"] = "silently replaced"
        assessment = assess_ground_truth_attestation(package)

        self.assertFalse(assessment["eligible"])
        self.assertIn("ground_truth_evidence_context_mismatch", assessment["blockers"])

    def test_declared_split_manifest_cannot_omit_image_membership(self) -> None:
        package = _package()
        package["splits"]["test"] = []
        package["dataset_fingerprint"] = coco_dataset_fingerprint(package)
        package["frozen_split_manifest"] = build_frozen_split_manifest(package)

        report = assess_coco_evidence_integrity(package, training_package=package)

        self.assertIn("image_split_manifest_mismatch:3", report["blockers"])

    def test_privacy_aggregate_contains_counts_and_no_private_payloads(self) -> None:
        dataset = {
            "examples": [
                {
                    "annotation_id": "private-id",
                    "frame_id": "private-frame",
                    "feature_type": "building_footprint",
                    "review_action": "redraw",
                    "reviewed_by": "reviewer@example.com",
                    "geometry": {"type": "Point", "coordinates": [-96.1, 41.1]},
                    "source_snapshots": [{"frame": {"source_url": "https://private.example/tile"}}],
                    "split": "train",
                    "blockers": [],
                }
            ],
            "negative_frame_count": 1,
        }

        aggregate = build_privacy_safe_correction_aggregate([dataset])
        encoded = json.dumps(aggregate)

        self.assertEqual(aggregate["counts_by_action"], {"redraw": 1})
        self.assertFalse(aggregate["contains_geometry"])
        self.assertTrue(validate_privacy_safe_correction_aggregate(aggregate)["valid"])
        for private_value in ("private-id", "private-frame", "reviewer@example.com", "private.example", "-96.1"):
            self.assertNotIn(private_value, encoded)

        tampered = deepcopy(aggregate)
        tampered["project_id"] = "private-project"
        validation = validate_privacy_safe_correction_aggregate(tampered)
        self.assertFalse(validation["valid"])
        self.assertIn(
            "privacy_safe_correction_unexpected_field:project_id",
            validation["blockers"],
        )

    def test_privacy_aggregate_bounds_user_controlled_dimensions(self) -> None:
        secret = "private-project-42-reviewer@example.com"
        aggregate = build_privacy_safe_correction_aggregate(
            [
                {
                    "examples": [
                        {
                            "feature_type": secret,
                            "review_action": secret,
                            "split": "train",
                            "blockers": [f"license_missing:{secret}"],
                        }
                    ]
                }
            ]
        )
        encoded = json.dumps(aggregate)

        self.assertEqual(aggregate["counts_by_action"], {"unknown": 1})
        self.assertEqual(aggregate["counts_by_class"], {"unknown": 1})
        self.assertEqual(
            aggregate["rights_blocker_counts"],
            {"other_rights_or_license_blocker": 1},
        )
        self.assertNotIn(secret, encoded)
        self.assertTrue(validate_privacy_safe_correction_aggregate(aggregate)["valid"])


if __name__ == "__main__":
    unittest.main()
