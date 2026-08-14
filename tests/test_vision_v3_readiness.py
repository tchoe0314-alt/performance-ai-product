from __future__ import annotations

from backend.planning.vision_v3_readiness import build_vision_v3_readiness_report
from backend.planning.vision_evidence_integrity import (
    append_test_consumption_receipt,
    assess_coco_evidence_integrity,
    build_evaluation_reservation_manifest,
    build_frozen_split_manifest,
    build_split_scoped_coco_evidence_packages,
    build_test_consumption_receipt,
    coco_dataset_fingerprint,
    test_consumption_receipt_fingerprint as receipt_fingerprint,
)
from backend.planning.vision_ground_truth_flywheel import build_privacy_safe_correction_aggregate


def _healthy_shadow(*, persistence_restore_observed: bool) -> dict:
    return {
        "shadow_inference": {
            "status": "ready",
            "classes": ["building", "road", "surface_water"],
            "influenced_user_candidates": False,
            "contains_shadow_geometry": False,
            "quality_claim_allowed": False,
            "runtime_statistics": {
                "persistence_configured": True,
                "persistence_restore_observed": persistence_restore_observed,
                "persistence_integrity_valid": True,
                "storage_scope": "aggregate_metrics_only_no_imagery_or_geometry",
                "submitted_count": 100,
                "completed_count": 100,
                "failed_count": 0,
                "dropped_count": 0,
                "aggregate": {"sample_count": 100},
            },
        }
    }


def test_default_required_class_is_surface_water_not_basin() -> None:
    report = build_vision_v3_readiness_report()

    assert report["required_classes"] == ["building", "road", "surface_water"]
    assert "basin" not in report["required_classes"]
    correction_blockers = report["lanes"]["correction_learning"]["blockers"]
    assert "reviewed_correction_count_below_v3_gate:surface_water" in correction_blockers
    assert not any(blocker.endswith(":basin") for blocker in correction_blockers)
    assert "correction_learning_consent_not_proven" in correction_blockers
    assert "privacy_safe_correction_aggregate_not_proven" in correction_blockers


def test_correction_lane_requires_counts_consent_and_privacy_safe_aggregate() -> None:
    examples = []
    for label in ("building", "road", "surface_water"):
        for index in range(100):
            examples.append(
                {
                    "feature_type": label,
                    "review_action": "correct",
                    "split": "train",
                    "blockers": [],
                }
            )
    aggregate = build_privacy_safe_correction_aggregate([{"examples": examples}])
    coverage = {
        "source_dataset_count": 1,
        "learning_consent_required": True,
        "learning_consent_validated_count": 1,
        "learning_consent_ready": True,
        "privacy_safe_aggregate_validation": {
            "valid": True,
            "blockers": [],
            "aggregate_fingerprint": aggregate["aggregate_fingerprint"],
        },
        "classes": {
            label: {
                "reviewed_annotation_count": 100,
                "geography_count": 5,
                "season_count": 2,
                "imagery_quality_band_count": 2,
            }
            for label in ("building", "road", "surface_water")
        },
    }

    report = build_vision_v3_readiness_report(correction_coverage=coverage)

    assert report["lanes"]["correction_learning"]["ready"] is True
    assert report["lanes"]["correction_learning"]["privacy_safe_aggregate_valid"] is True


def test_missing_evidence_lanes_fail_closed_with_clear_blockers() -> None:
    report = build_vision_v3_readiness_report()

    assert report["status"] == "candidate_blocked"
    assert report["deployment_ready"] is False
    assert report["visible_detection_influence_allowed"] is False

    lanes = report["lanes"]
    assert lanes["shadow_monitoring"]["ready"] is False
    assert "shadow_runtime_not_ready" in lanes["shadow_monitoring"]["blockers"]
    assert lanes["correction_learning"]["ready"] is False
    assert "reviewed_correction_count_below_v3_gate:building" in lanes["correction_learning"]["blockers"]
    assert lanes["training_evidence"] == {
        "status": "missing",
        "ready": False,
        "blockers": ["training_dataset_missing"],
    }
    assert lanes["independent_evaluation"]["ready"] is False
    assert lanes["independent_evaluation"]["blockers"] == [
        "evaluation_dataset_missing",
        "evaluation_reservation_manifest_missing",
        "test_consumption_ledger_missing",
        "test_consumption_receipt_missing",
    ]
    assert lanes["model_promotion"]["ready"] is False
    assert lanes["model_promotion"]["blockers"] == ["independent_quality_report_missing"]

    assert "training_evidence:training_dataset_missing" in report["blockers"]
    assert "independent_evaluation:evaluation_dataset_missing" in report["blockers"]
    assert "model_promotion:independent_quality_report_missing" in report["blockers"]


def test_valid_looking_shadow_still_blocks_without_durable_restore_proof() -> None:
    report = build_vision_v3_readiness_report(
        shadow_health=_healthy_shadow(persistence_restore_observed=False)
    )

    shadow = report["lanes"]["shadow_monitoring"]
    assert shadow["ready"] is False
    assert shadow["sample_count"] == 100
    assert shadow["blockers"] == ["shadow_persistence_restore_not_proven"]
    assert report["deployment_ready"] is False
    assert "shadow_monitoring:shadow_persistence_restore_not_proven" in report["blockers"]


def test_shadow_lane_clears_only_after_restore_is_observed() -> None:
    report = build_vision_v3_readiness_report(
        shadow_health=_healthy_shadow(persistence_restore_observed=True)
    )

    shadow = report["lanes"]["shadow_monitoring"]
    assert shadow == {
        "status": "ready",
        "ready": True,
        "sample_count": 100,
        "blockers": [],
    }
    assert report["deployment_ready"] is False
    assert "training_evidence:training_dataset_missing" in report["blockers"]


def test_clean_frozen_split_does_not_masquerade_as_attested_ground_truth() -> None:
    package = {
        "categories": [
            {"id": 1, "name": "building"},
            {"id": 2, "name": "road"},
            {"id": 3, "name": "surface_water"},
        ],
        "images": [
            {
                "id": 1,
                "file_name": "train.png",
                "source_sha256": "a" * 64,
                "imagery_frame_id": "train-frame",
                "geography_id": "train-city",
                "split": "train",
            },
            {
                "id": 2,
                "file_name": "test.png",
                "source_sha256": "b" * 64,
                "imagery_frame_id": "test-frame",
                "geography_id": "test-city",
                "split": "test",
            },
        ],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 1},
            {"id": 2, "image_id": 1, "category_id": 2},
            {"id": 3, "image_id": 1, "category_id": 3},
            {"id": 4, "image_id": 2, "category_id": 1},
            {"id": 5, "image_id": 2, "category_id": 2},
            {"id": 6, "image_id": 2, "category_id": 3},
        ],
        "splits": {"train": [1], "validation": [], "test": [2]},
        "split_policy": {"strategy": "geography_disjoint"},
        "contains_image_bytes": False,
        "supervision_status": "weak_labels_pending_review",
        "promotion_eligible": False,
    }
    package["dataset_fingerprint"] = coco_dataset_fingerprint(package)
    package["frozen_split_manifest"] = build_frozen_split_manifest(package)

    report = build_vision_v3_readiness_report(
        evaluation_dataset=package,
        training_dataset=package,
    )

    lane = report["lanes"]["independent_evaluation"]
    assert lane["structural_integrity_ready"] is False
    assert lane["ground_truth_attested"] is False
    assert lane["ready"] is False
    assert "physical_split_isolation_not_proven" in lane["blockers"]
    assert lane["one_way_test_consumption_recorded"] is False
    assert "reviewed_or_independent_ground_truth_missing" in lane["blockers"]
    assert report["deployment_ready"] is False


def test_post_hoc_consumption_is_recorded_but_never_clears_independent_evaluation() -> None:
    package = {
        "categories": [
            {"id": 1, "name": "building"},
            {"id": 2, "name": "road"},
            {"id": 3, "name": "surface_water"},
        ],
        "images": [
            {"id": 1, "split": "train", "source_sha256": "1" * 64},
            {"id": 2, "split": "validation", "source_sha256": "2" * 64},
            {"id": 3, "split": "test", "source_sha256": "3" * 64},
        ],
        "annotations": [
            {"id": index * 3 + category, "image_id": image, "category_id": category}
            for index, image in enumerate((1, 2, 3))
            for category in (1, 2, 3)
        ],
        "splits": {"train": [1], "validation": [2], "test": [3]},
        "split_policy": {"strategy": "source_identity_disjoint", "test_split_frozen": True},
        "contains_image_bytes": False,
        "supervision_status": "independent_benchmark_annotated",
        "ground_truth_attestation": {
            "status": "third_party_benchmark_annotations",
            "dataset_name": "fixture",
            "license": "fixture-rights-cleared",
            "independent_test_split": True,
            "test_images_excluded_from_training": True,
        },
        "evaluation_scope": {
            "geography_count": 5,
            "season_count": 2,
            "imagery_quality_band_count": 2,
        },
    }
    package["dataset_fingerprint"] = coco_dataset_fingerprint(package)
    package["frozen_split_manifest"] = build_frozen_split_manifest(package)
    scoped = build_split_scoped_coco_evidence_packages(
        package,
        required_classes=["building", "road", "surface_water"],
    )
    training = scoped["training_validation"]
    evaluation = scoped["frozen_test"]
    integrity = assess_coco_evidence_integrity(
        evaluation,
        training_package=training,
        required_classes=["building", "road", "surface_water"],
    )
    reservation = build_evaluation_reservation_manifest(
        evaluation,
        training,
        evaluation_package_sha256="e" * 64,
        training_package_sha256="d" * 64,
        required_classes=["building", "road", "surface_water"],
    )
    receipt = build_test_consumption_receipt(
        integrity,
        candidate_id="legacy-rejected:v1",
        model_artifact_sha256="a" * 64,
        reservation_mode="post_hoc_rejection_record",
        evaluation_reservation_manifest=reservation,
    )
    quality = {
        "evaluation_status": "measured_against_ground_truth",
        "promotion_eligible": True,
        "source_supervision_status": "independent_benchmark_annotated",
        "ground_truth_attestation": evaluation["ground_truth_attestation"],
        "evaluation_scope": evaluation["evaluation_scope"],
        "dataset_fingerprint": evaluation["dataset_fingerprint"],
        "model_artifact_sha256": "a" * 64,
        "evaluation_reservation_manifest": reservation,
        "test_consumption_receipt": receipt,
        "test_consumption_ledger": append_test_consumption_receipt({}, receipt),
    }

    report = build_vision_v3_readiness_report(
        evaluation_dataset=evaluation,
        training_dataset=training,
        quality_report=quality,
    )

    lane = report["lanes"]["independent_evaluation"]
    assert lane["one_way_test_consumption_recorded"] is True
    assert lane["pre_evaluation_atomic_reservation_proven"] is False
    assert lane["ready"] is False
    assert "test_consumption_receipt_not_pre_evaluation" in lane["blockers"]

    mismatched_receipt = {**receipt, "evaluation_reservation_manifest_sha256": "f" * 64}
    mismatched_receipt["receipt_sha256"] = receipt_fingerprint(mismatched_receipt)
    mismatched_quality = {
        **quality,
        "test_consumption_receipt": mismatched_receipt,
        "test_consumption_ledger": append_test_consumption_receipt({}, mismatched_receipt),
    }
    mismatched_report = build_vision_v3_readiness_report(
        evaluation_dataset=evaluation,
        training_dataset=training,
        quality_report=mismatched_quality,
    )
    assert (
        "test_consumption_reservation_manifest_mismatch"
        in mismatched_report["lanes"]["independent_evaluation"]["blockers"]
    )
