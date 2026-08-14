from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from .common import safe_dict, safe_float, safe_list, safe_str
from .vision_evidence_integrity import (
    assess_coco_evidence_integrity,
    declared_coco_evidence_fingerprint,
    validate_evaluation_reservation_manifest,
    validate_evidence_integrity_report,
    validate_test_consumption_ledger,
    validate_test_consumption_receipt,
)
from .vision_model_lifecycle import (
    assess_ground_truth_attestation,
    assess_model_promotion,
    canonical_model_label,
)
from .vision_public_bootstrap import verify_weak_supervision_package


VISION_V3_READINESS_VERSION = "civora_vision_v3_readiness_v1"


def build_vision_v3_readiness_report(
    *,
    evaluation_dataset: Optional[Dict[str, Any]] = None,
    training_dataset: Optional[Dict[str, Any]] = None,
    quality_report: Optional[Dict[str, Any]] = None,
    shadow_health: Optional[Dict[str, Any]] = None,
    correction_coverage: Optional[Dict[str, Any]] = None,
    required_classes: Sequence[str] = ("building", "road", "surface_water"),
) -> Dict[str, Any]:
    evaluation = safe_dict(evaluation_dataset)
    training = safe_dict(training_dataset)
    quality = safe_dict(quality_report)
    shadow = _shadow_status(safe_dict(shadow_health), required_classes=required_classes)
    corrections = _correction_status(safe_dict(correction_coverage), required_classes=required_classes)
    training_status = _training_status(training, required_classes=required_classes)
    integrity = (
        assess_coco_evidence_integrity(
            evaluation,
            evaluation_split="test",
            training_package=training or None,
            required_classes=required_classes,
        )
        if evaluation
        else {}
    )
    integrity_validation = (
        validate_evidence_integrity_report(integrity)
        if integrity
        else {
            "valid": False,
            "promotion_eligible": False,
            "blockers": ["evaluation_dataset_missing"],
        }
    )
    ground_truth_attestation = (
        assess_ground_truth_attestation(
            {
                **evaluation,
                "evaluation_eligible": integrity_validation["valid"],
                "evidence_integrity": integrity,
            }
        )
        if evaluation
        else {"eligible": False, "blockers": ["evaluation_dataset_missing"]}
    )
    if quality and integrity:
        quality = {**quality, "evidence_integrity": integrity}
    consumption_receipt = safe_dict(quality.get("test_consumption_receipt"))
    consumption_ledger = safe_dict(quality.get("test_consumption_ledger"))
    evaluation_reservation = safe_dict(quality.get("evaluation_reservation_manifest"))
    threshold_calibration = safe_dict(quality.get("threshold_calibration"))
    reservation_validation = (
        validate_evaluation_reservation_manifest(evaluation_reservation)
        if evaluation_reservation
        else {"valid": False, "blockers": ["evaluation_reservation_manifest_missing"]}
    )
    receipt_validation = (
        validate_test_consumption_receipt(
            consumption_receipt,
            evaluation_dataset_fingerprint=declared_coco_evidence_fingerprint(evaluation),
            model_artifact_sha256=safe_str(quality.get("model_artifact_sha256")),
            threshold_calibration_fingerprint=safe_str(
                threshold_calibration.get("calibration_fingerprint")
            ),
        )
        if consumption_receipt
        else {
            "valid": False,
            "promotion_eligible": False,
            "blockers": ["test_consumption_receipt_missing"],
        }
    )
    ledger_validation = (
        validate_test_consumption_ledger(
            consumption_ledger,
            expected_receipt_sha256=safe_str(consumption_receipt.get("receipt_sha256")),
        )
        if consumption_ledger
        else {
            "valid": False,
            "promotion_eligible": False,
            "blockers": ["test_consumption_ledger_missing"],
        }
    )
    receipt_reservation_blockers = []
    if consumption_receipt and evaluation_reservation:
        if safe_str(consumption_receipt.get("evaluation_reservation_manifest_sha256")).lower() != safe_str(
            evaluation_reservation.get("manifest_sha256")
        ).lower():
            receipt_reservation_blockers.append("test_consumption_reservation_manifest_mismatch")
        if safe_str(consumption_receipt.get("test_image_membership_sha256")).lower() != safe_str(
            evaluation_reservation.get("test_image_membership_sha256")
        ).lower():
            receipt_reservation_blockers.append("test_consumption_reservation_membership_mismatch")
    promotion = (
        assess_model_promotion(
            quality,
            required_classes=required_classes,
            dataset_fingerprint=declared_coco_evidence_fingerprint(evaluation),
        )
        if quality
        else {"eligible": False, "blockers": ["independent_quality_report_missing"]}
    )
    independent_evaluation_blockers = sorted(
        set(
            safe_list(integrity_validation.get("blockers"))
            + safe_list(integrity.get("blockers"))
            + safe_list(ground_truth_attestation.get("blockers"))
            + safe_list(reservation_validation.get("blockers"))
            + safe_list(receipt_validation.get("blockers"))
            + safe_list(ledger_validation.get("blockers"))
            + receipt_reservation_blockers
            + (
                ["test_consumption_receipt_not_pre_evaluation"]
                if receipt_validation.get("valid") is True
                and receipt_validation.get("promotion_eligible") is not True
                else []
            )
            + (
                ["test_consumption_ledger_not_promotion_eligible"]
                if ledger_validation.get("valid") is True
                and ledger_validation.get("promotion_eligible") is not True
                else []
            )
        )
    )
    independent_evaluation_ready = (
        integrity_validation["valid"] is True
        and ground_truth_attestation.get("eligible") is True
        and reservation_validation.get("valid") is True
        and safe_str(consumption_receipt.get("evaluation_reservation_manifest_sha256")).lower()
        == safe_str(evaluation_reservation.get("manifest_sha256")).lower()
        and safe_str(consumption_receipt.get("test_image_membership_sha256")).lower()
        == safe_str(evaluation_reservation.get("test_image_membership_sha256")).lower()
        and receipt_validation.get("promotion_eligible") is True
        and ledger_validation.get("promotion_eligible") is True
    )
    lanes = {
        "shadow_monitoring": shadow,
        "correction_learning": corrections,
        "training_evidence": training_status,
        "independent_evaluation": {
            "status": "ready" if independent_evaluation_ready else "blocked",
            "ready": independent_evaluation_ready,
            "structural_integrity_ready": integrity_validation["valid"] is True,
            "ground_truth_attested": ground_truth_attestation.get("eligible") is True,
            "blockers": independent_evaluation_blockers,
            "evaluation_annotation_count": int(safe_float(integrity.get("evaluation_annotation_count"))),
            "evaluation_classes": safe_list(integrity.get("evaluation_classes")),
            "evaluation_reservation_valid": reservation_validation.get("valid") is True,
            "one_way_test_consumption_recorded": (
                receipt_validation.get("valid") is True and ledger_validation.get("valid") is True
            ),
            "pre_evaluation_atomic_reservation_proven": (
                receipt_validation.get("promotion_eligible") is True
                and ledger_validation.get("promotion_eligible") is True
            ),
        },
        "model_promotion": {
            "status": "ready" if promotion.get("eligible") is True else "blocked",
            "ready": promotion.get("eligible") is True,
            "blockers": safe_list(promotion.get("blockers")),
        },
    }
    deployment_ready = all(
        lanes[name]["ready"]
        for name in ("shadow_monitoring", "correction_learning", "training_evidence", "independent_evaluation", "model_promotion")
    )
    blockers = sorted(
        {
            f"{name}:{blocker}"
            for name, lane in lanes.items()
            for blocker in safe_list(lane.get("blockers"))
            if safe_str(blocker)
        }
    )
    return {
        "version": VISION_V3_READINESS_VERSION,
        "status": "ready_for_bounded_review_candidates" if deployment_ready else "candidate_blocked",
        "deployment_ready": deployment_ready,
        "visible_detection_influence_allowed": deployment_ready,
        "required_classes": list(required_classes),
        "lanes": lanes,
        "blockers": blockers,
        "evidence_integrity": integrity,
        "promotion": promotion,
        "truth_label": (
            "Ready means eligible only for bounded visual review candidates in the tested operating scope. It does not "
            "make detections survey/control, utility-locate, compliance, or engineering evidence."
        ),
    }


def _shadow_status(health: Dict[str, Any], *, required_classes: Sequence[str]) -> Dict[str, Any]:
    shadow = safe_dict(health.get("shadow_inference") or health)
    runtime = safe_dict(shadow.get("runtime_statistics"))
    aggregate = safe_dict(runtime.get("aggregate"))
    classes = {safe_str(item) for item in safe_list(shadow.get("classes")) if safe_str(item)}
    blockers = []
    if safe_str(shadow.get("status")) != "ready":
        blockers.append("shadow_runtime_not_ready")
    if shadow.get("influenced_user_candidates") is not False:
        blockers.append("shadow_influenced_user_candidates")
    if shadow.get("contains_shadow_geometry") is not False:
        blockers.append("shadow_geometry_exposed")
    if shadow.get("quality_claim_allowed") is not False:
        blockers.append("shadow_quality_claim_enabled")
    if runtime.get("persistence_configured") is not True:
        blockers.append("shadow_persistence_not_configured")
    if runtime.get("persistence_restore_observed") is not True:
        blockers.append("shadow_persistence_restore_not_proven")
    if runtime.get("persistence_integrity_valid") is not True:
        blockers.append("shadow_persistence_integrity_not_proven")
    if safe_str(runtime.get("storage_scope")) != "aggregate_metrics_only_no_imagery_or_geometry":
        blockers.append("shadow_storage_scope_not_privacy_safe")
    if int(safe_float(aggregate.get("sample_count"))) < 100:
        blockers.append("shadow_sample_count_below_v3_gate")
    for label in required_classes:
        if label not in classes:
            blockers.append(f"shadow_required_class_missing:{label}")
    submitted = int(safe_float(runtime.get("submitted_count")))
    completed = int(safe_float(runtime.get("completed_count")))
    failed = int(safe_float(runtime.get("failed_count")))
    dropped = int(safe_float(runtime.get("dropped_count")))
    if submitted and (failed + dropped) / submitted > 0.05:
        blockers.append("shadow_failure_or_drop_rate_above_v3_gate")
    return {
        "status": "ready" if not blockers else "blocked",
        "ready": not blockers,
        "sample_count": int(safe_float(aggregate.get("sample_count"))),
        "blockers": sorted(set(blockers)),
    }


def _correction_status(coverage: Dict[str, Any], *, required_classes: Sequence[str]) -> Dict[str, Any]:
    rows = safe_dict(coverage.get("classes"))
    blockers = []
    source_dataset_count = int(safe_float(coverage.get("source_dataset_count")))
    consent_count = int(safe_float(coverage.get("learning_consent_validated_count")))
    if coverage.get("learning_consent_required") is not True:
        blockers.append("correction_learning_consent_not_required")
    if source_dataset_count < 1:
        blockers.append("correction_source_dataset_missing")
    if source_dataset_count > 0 and consent_count != source_dataset_count:
        blockers.append("correction_learning_consent_incomplete")
    if coverage.get("learning_consent_ready") is not True:
        blockers.append("correction_learning_consent_not_proven")
    privacy = safe_dict(coverage.get("privacy_safe_aggregate_validation"))
    if privacy.get("valid") is not True:
        blockers.append("privacy_safe_correction_aggregate_not_proven")
        blockers.extend(
            f"privacy_safe_correction:{item}"
            for item in safe_list(privacy.get("blockers"))
            if safe_str(item)
        )
    for label in required_classes:
        canonical_label = canonical_model_label(label)
        row = _coverage_row_for_model_label(rows, canonical_label)
        if int(safe_float(row.get("reviewed_annotation_count"))) < 100:
            blockers.append(f"reviewed_correction_count_below_v3_gate:{canonical_label}")
        if int(safe_float(row.get("geography_count"))) < 5:
            blockers.append(f"reviewed_correction_geography_below_v3_gate:{canonical_label}")
        if int(safe_float(row.get("season_count"))) < 2:
            blockers.append(f"reviewed_correction_season_below_v3_gate:{canonical_label}")
        if int(safe_float(row.get("imagery_quality_band_count"))) < 2:
            blockers.append(f"reviewed_correction_quality_band_below_v3_gate:{canonical_label}")
    return {
        "status": "ready" if not blockers else "blocked",
        "ready": not blockers,
        "source_dataset_count": source_dataset_count,
        "learning_consent_validated_count": consent_count,
        "privacy_safe_aggregate_valid": privacy.get("valid") is True,
        "blockers": sorted(set(blockers)),
    }


def _training_status(training: Dict[str, Any], *, required_classes: Sequence[str]) -> Dict[str, Any]:
    if not training:
        return {
            "status": "missing",
            "ready": False,
            "blockers": ["training_dataset_missing"],
        }
    blockers = []
    if training.get("contains_image_bytes") is not False:
        blockers.append("training_package_embedded_image_contract_invalid")
    if not safe_str(training.get("dataset_fingerprint")):
        blockers.append("training_dataset_fingerprint_missing")
    supervision = safe_str(training.get("supervision_status"))
    if supervision not in {"reviewer_labeled", "independent_benchmark_annotated"}:
        blockers.append("training_supervision_not_reviewed")
    if supervision == "weak_labels_pending_review":
        weak_validation = verify_weak_supervision_package(training)
        blockers.extend(
            f"weak_training_package:{item}"
            for item in safe_list(weak_validation.get("blockers"))
        )
    categories = {
        int(safe_float(item.get("id"))): canonical_model_label(item.get("name"))
        for item in safe_list(training.get("categories"))
        if safe_dict(item) and int(safe_float(safe_dict(item).get("id"))) > 0
    }
    train_ids = {
        int(safe_float(item))
        for item in safe_list(safe_dict(training.get("splits")).get("train"))
        if int(safe_float(item)) > 0
    }
    if not train_ids:
        train_ids = {
            int(safe_float(item.get("id")))
            for item in safe_list(training.get("images"))
            if safe_dict(item) and safe_str(safe_dict(item).get("split")) == "train"
        }
    if not train_ids:
        blockers.append("training_split_empty")
    represented = {
        categories.get(int(safe_float(item.get("category_id"))))
        for item in safe_list(training.get("annotations"))
        if safe_dict(item) and int(safe_float(safe_dict(item).get("image_id"))) in train_ids
    }
    for label in required_classes:
        canonical_label = canonical_model_label(label)
        if canonical_label not in represented:
            blockers.append(f"required_class_missing_from_training_split:{canonical_label}")
    return {
        "status": "ready" if not blockers else "blocked",
        "ready": not blockers,
        "supervision_status": supervision or "missing",
        "train_image_count": len(train_ids),
        "represented_classes": sorted(item for item in represented if item),
        "blockers": sorted(set(blockers)),
    }


def _coverage_row_for_model_label(rows: Dict[str, Any], label: str) -> Dict[str, Any]:
    aliases = {
        "building": ("building", "building_footprint"),
        "road": ("road", "road_or_drive"),
        "surface_water": ("surface_water", "water/pond/basin", "water", "pond", "basin"),
    }
    for key in aliases.get(label, (label,)):
        row = safe_dict(rows.get(key))
        if row:
            return row
    return {}


__all__ = ["VISION_V3_READINESS_VERSION", "build_vision_v3_readiness_report"]
