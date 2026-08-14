from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

import fcntl

from .common import safe_dict, safe_list, safe_str


EVIDENCE_INTEGRITY_VERSION = "civora_vision_evidence_integrity_v1"
FROZEN_SPLIT_VERSION = "civora_vision_frozen_split_v1"
HELD_OUT_COMMITMENT_VERSION = "civora_vision_held_out_commitment_v1"
EVALUATION_RESERVATION_VERSION = "civora_vision_evaluation_reservation_v2"
TEST_CONSUMPTION_RECEIPT_VERSION = "civora_vision_test_consumption_receipt_v2"
TEST_CONSUMPTION_LEDGER_VERSION = "civora_vision_test_consumption_ledger_v2"
SUPPORTED_SPLITS = ("train", "validation", "test")
FROZEN_IDENTITY_FIELDS = (
    "test_image_count",
    "test_image_ids_sha256",
    "test_source_identities_sha256",
    "test_source_identity_count",
    "test_split_mutation_allowed",
)
HELD_OUT_COMMITMENT_FIELDS = {
    "version",
    "dataset_fingerprint",
    "test_image_membership_sha256",
    "test_image_count",
    "test_image_ids_sha256",
    "test_source_identities_sha256",
    "test_source_identity_count",
    "test_split_mutation_allowed",
    "label_statistics_disclosed",
    "manifest_sha256",
}
MODEL_CLASS_ALIASES = {
    "basin": "surface_water",
    "pond": "surface_water",
    "water": "surface_water",
}
EVALUATION_RESERVATION_FIELDS = {
    "version",
    "evaluation_dataset_fingerprint",
    "training_dataset_fingerprint",
    "evidence_family_fingerprint",
    "evaluation_package_sha256",
    "training_package_sha256",
    "test_image_membership_sha256",
    "test_image_count",
    "test_image_ids_sha256",
    "test_source_identities_sha256",
    "test_source_identity_count",
    "test_split_mutation_allowed",
    "test_source_identity_digests",
    "required_model_classes",
    "physical_split_isolation_proven",
    "training_held_out_manifest_bound",
    "label_statistics_disclosed",
    "contains_image_bytes",
    "contains_image_records",
    "contains_annotation_records",
    "contains_source_urls_or_locations",
    "manifest_sha256",
}
TEST_CONSUMPTION_RECEIPT_FIELDS = {
    "version",
    "candidate_id",
    "model_artifact_sha256",
    "threshold_calibration_fingerprint",
    "evaluation_dataset_fingerprint",
    "test_image_membership_sha256",
    "test_image_ids_sha256",
    "test_source_identities_sha256",
    "test_source_identity_digests",
    "test_image_count",
    "label_statistics_disclosed",
    "consumed_at",
    "reservation_mode",
    "evaluation_reservation_manifest_sha256",
    "purpose",
    "reusable_as_untouched_evidence",
    "receipt_sha256",
}
TEST_CONSUMPTION_LEDGER_FIELDS = {"version", "entries", "ledger_sha256"}


def build_evaluation_reservation_manifest(
    evaluation_package: Dict[str, Any],
    training_package: Dict[str, Any],
    *,
    evaluation_package_sha256: str,
    training_package_sha256: str,
    required_classes: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    integrity = assess_coco_evidence_integrity(
        evaluation_package,
        evaluation_split="test",
        training_package=training_package,
        required_classes=required_classes,
    )
    if integrity.get("promotion_eligible") is not True:
        raise ValueError(
            "Cannot seal an evaluation reservation from invalid evidence: "
            + ", ".join(safe_list(integrity.get("blockers")))
        )
    evaluation_sha = safe_str(evaluation_package_sha256).lower()
    training_sha = safe_str(training_package_sha256).lower()
    if not _is_sha256(evaluation_sha) or not _is_sha256(training_sha):
        raise ValueError("Reservation package fingerprints must be SHA-256 digests.")
    frozen = safe_dict(integrity.get("frozen_test_manifest"))
    required = sorted(
        {
            _canonical_class_label(item)
            for item in (required_classes or safe_list(integrity.get("evaluation_classes")))
            if _canonical_class_label(item)
        }
    )
    payload = {
        "version": EVALUATION_RESERVATION_VERSION,
        "evaluation_dataset_fingerprint": safe_str(integrity.get("dataset_fingerprint")).lower(),
        "training_dataset_fingerprint": safe_str(integrity.get("training_dataset_fingerprint")).lower(),
        "evidence_family_fingerprint": safe_str(
            safe_dict(evaluation_package).get("parent_coco_evidence_fingerprint")
        ).lower(),
        "evaluation_package_sha256": evaluation_sha,
        "training_package_sha256": training_sha,
        "test_image_membership_sha256": frozen_test_image_membership_fingerprint(frozen),
        "test_image_count": int(frozen.get("test_image_count") or 0),
        "test_image_ids_sha256": safe_str(frozen.get("test_image_ids_sha256")).lower(),
        "test_source_identities_sha256": safe_str(frozen.get("test_source_identities_sha256")).lower(),
        "test_source_identity_count": int(frozen.get("test_source_identity_count") or 0),
        "test_split_mutation_allowed": False,
        "test_source_identity_digests": safe_list(integrity.get("test_source_identity_digests")),
        "required_model_classes": required,
        "physical_split_isolation_proven": integrity.get("physical_split_isolation_proven") is True,
        "training_held_out_manifest_bound": integrity.get("training_held_out_manifest_bound") is True,
        "label_statistics_disclosed": False,
        "contains_image_bytes": False,
        "contains_image_records": False,
        "contains_annotation_records": False,
        "contains_source_urls_or_locations": False,
    }
    payload["manifest_sha256"] = evaluation_reservation_fingerprint(payload)
    return payload


def evaluation_reservation_fingerprint(manifest: Dict[str, Any]) -> str:
    return _stable_hash(
        {key: value for key, value in safe_dict(manifest).items() if key != "manifest_sha256"}
    )


def validate_evaluation_reservation_manifest(
    manifest: Dict[str, Any],
    *,
    evaluation_package_sha256: str = "",
    training_package_sha256: str = "",
) -> Dict[str, Any]:
    rec = safe_dict(manifest)
    blockers: List[str] = []
    unknown_fields = sorted(set(rec) - EVALUATION_RESERVATION_FIELDS)
    blockers.extend(f"evaluation_reservation_unknown_field:{field}" for field in unknown_fields)
    missing_fields = sorted(EVALUATION_RESERVATION_FIELDS - set(rec))
    blockers.extend(f"evaluation_reservation_required_field_missing:{field}" for field in missing_fields)
    if safe_str(rec.get("version")) != EVALUATION_RESERVATION_VERSION:
        blockers.append("unsupported_evaluation_reservation_version")
    for field in (
        "evaluation_dataset_fingerprint",
        "training_dataset_fingerprint",
        "evidence_family_fingerprint",
        "evaluation_package_sha256",
        "training_package_sha256",
    ):
        if not _is_sha256(safe_str(rec.get(field)).lower()):
            blockers.append(f"evaluation_reservation_{field}_invalid")
    for field in (
        "test_image_membership_sha256",
        "test_image_ids_sha256",
        "test_source_identities_sha256",
    ):
        if not _is_sha256(safe_str(rec.get(field)).lower()):
            blockers.append(f"evaluation_reservation_{field}_invalid")
    if rec.get("test_split_mutation_allowed") is not False:
        blockers.append("evaluation_reservation_frozen_manifest_invalid")
    test_image_count = int(rec.get("test_image_count") or 0)
    test_source_identity_count = int(rec.get("test_source_identity_count") or 0)
    if test_image_count <= 0 or test_source_identity_count != test_image_count:
        blockers.append("evaluation_reservation_test_image_membership_invalid")
    identities = [safe_str(item).lower() for item in safe_list(rec.get("test_source_identity_digests"))]
    if (
        len(identities) != test_image_count
        or len(identities) != len(set(identities))
        or any(not _is_sha256(item) for item in identities)
    ):
        blockers.append("evaluation_reservation_source_identity_membership_invalid")
    required_model_classes = [
        _canonical_class_label(item) for item in safe_list(rec.get("required_model_classes"))
    ]
    if (
        not required_model_classes
        or required_model_classes != sorted(set(required_model_classes))
        or any(not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", item) for item in required_model_classes)
    ):
        blockers.append("evaluation_reservation_classes_missing")
    if rec.get("physical_split_isolation_proven") is not True:
        blockers.append("evaluation_reservation_physical_isolation_missing")
    if rec.get("training_held_out_manifest_bound") is not True:
        blockers.append("evaluation_reservation_held_out_binding_missing")
    if rec.get("label_statistics_disclosed") is not False:
        blockers.append("evaluation_reservation_label_statistics_disclosed")
    for forbidden in (
        "evidence_integrity",
        "frozen_test_manifest",
        "test_annotation_count",
        "evaluation_annotation_count",
        "split_counts",
        "evaluation_classes",
    ):
        if forbidden in rec:
            blockers.append(f"evaluation_reservation_label_blind_boundary_invalid:{forbidden}")
    for field in (
        "contains_image_bytes",
        "contains_image_records",
        "contains_annotation_records",
        "contains_source_urls_or_locations",
    ):
        if rec.get(field) is not False:
            blockers.append(f"evaluation_reservation_privacy_boundary_invalid:{field}")
    expected_manifest_sha = evaluation_reservation_fingerprint(rec)
    if safe_str(rec.get("manifest_sha256")).lower() != expected_manifest_sha:
        blockers.append("evaluation_reservation_fingerprint_mismatch")
    expected_values = {
        "evaluation_package_sha256": safe_str(evaluation_package_sha256).lower(),
        "training_package_sha256": safe_str(training_package_sha256).lower(),
    }
    for field, expected in expected_values.items():
        if expected and safe_str(rec.get(field)).lower() != expected:
            blockers.append(f"evaluation_reservation_{field}_mismatch")
    return {
        "valid": not blockers,
        "blockers": sorted(set(blockers)),
        "manifest_sha256": expected_manifest_sha,
        "evaluation_dataset_fingerprint": safe_str(rec.get("evaluation_dataset_fingerprint")).lower(),
    }


def validate_reservation_against_evidence(
    manifest: Dict[str, Any],
    evaluation_package: Dict[str, Any],
    training_package: Dict[str, Any],
    *,
    evaluation_package_sha256: str,
    training_package_sha256: str,
    required_classes: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    rec = safe_dict(manifest)
    validation = validate_evaluation_reservation_manifest(
        rec,
        evaluation_package_sha256=evaluation_package_sha256,
        training_package_sha256=training_package_sha256,
    )
    blockers = list(validation["blockers"])
    if not blockers:
        try:
            expected = build_evaluation_reservation_manifest(
                evaluation_package,
                training_package,
                evaluation_package_sha256=evaluation_package_sha256,
                training_package_sha256=training_package_sha256,
                required_classes=required_classes,
            )
        except ValueError as exc:
            blockers.append(f"evaluation_reservation_evidence_invalid:{exc}")
        else:
            if rec != expected:
                blockers.append("evaluation_reservation_evidence_mismatch")
    return {
        "valid": not blockers,
        "blockers": sorted(set(blockers)),
        "manifest_sha256": validation["manifest_sha256"],
    }


def validate_training_package_against_reservation(
    manifest: Dict[str, Any],
    training_package: Dict[str, Any],
    *,
    training_package_sha256: str,
) -> Dict[str, Any]:
    """Validate development evidence without opening frozen evaluation records."""

    rec = safe_dict(manifest)
    training = safe_dict(training_package)
    validation = validate_evaluation_reservation_manifest(
        rec,
        training_package_sha256=training_package_sha256,
    )
    blockers = list(validation["blockers"])
    images = _images_by_id(training, blockers=blockers)
    splits = _split_ids(training, images, blockers=blockers)
    held_out = safe_dict(training.get("held_out_test_manifest"))
    held_out_validation = validate_held_out_test_commitment(held_out)
    blockers.extend(held_out_validation["blockers"])
    if safe_str(training.get("dataset_role")) != "training_and_validation":
        blockers.append("training_dataset_role_not_training_and_validation")
    if training.get("test_records_in_package") is not False or splits["test"]:
        blockers.append("training_package_contains_test_records")
    if any(safe_str(item.get("split")).lower() == "test" for item in images.values()):
        blockers.append("training_package_contains_test_image_records")
    if _declared_coco_fingerprint(training) != safe_str(rec.get("training_dataset_fingerprint")).lower():
        blockers.append("training_package_fingerprint_mismatch")
    if safe_str(training.get("parent_coco_evidence_fingerprint")).lower() != safe_str(
        rec.get("evidence_family_fingerprint")
    ).lower():
        blockers.append("training_package_evidence_family_mismatch")
    if (
        safe_str(held_out.get("test_image_membership_sha256")).lower()
        != safe_str(rec.get("test_image_membership_sha256")).lower()
        or int(held_out.get("test_image_count") or 0) != int(rec.get("test_image_count") or 0)
        or safe_str(held_out.get("test_image_ids_sha256")).lower()
        != safe_str(rec.get("test_image_ids_sha256")).lower()
        or safe_str(held_out.get("test_source_identities_sha256")).lower()
        != safe_str(rec.get("test_source_identities_sha256")).lower()
    ):
        blockers.append("training_held_out_manifest_reservation_mismatch")
    return {
        "valid": not blockers,
        "blockers": sorted(set(blockers)),
        "training_dataset_fingerprint": _declared_coco_fingerprint(training),
        "manifest_sha256": validation["manifest_sha256"],
    }


def coco_dataset_fingerprint(package: Dict[str, Any]) -> str:
    source = safe_dict(package)
    return _stable_hash(
        {
            "categories": safe_list(source.get("categories")),
            "images": safe_list(source.get("images")),
            "annotations": safe_list(source.get("annotations")),
            "splits": safe_dict(source.get("splits")),
        }
    )


def build_split_scoped_coco_evidence_packages(
    package: Dict[str, Any],
    *,
    required_classes: Optional[Sequence[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Physically separate a complete COCO evidence manifest by lifecycle role.

    The returned training package contains only train/validation records. The
    returned evaluation package contains only frozen-test records and is bound
    to the same parent evidence family through the immutable held-out manifest.
    """

    source = deepcopy(safe_dict(package))
    computed_fingerprint = coco_dataset_fingerprint(source)
    declared_fingerprint = _declared_coco_fingerprint(source, fallback=False)
    if not declared_fingerprint or declared_fingerprint != computed_fingerprint:
        raise ValueError("Combined COCO evidence must have a valid deterministic fingerprint before scoping.")
    images = _images_by_id(source)
    splits = _split_ids(source, images)
    missing_splits = [name for name in SUPPORTED_SPLITS if not splits[name]]
    if missing_splits:
        raise ValueError("Combined COCO evidence is missing required splits: " + ", ".join(missing_splits))
    category_labels = {
        _safe_int(safe_dict(item).get("id")): _canonical_class_label(safe_dict(item).get("name"))
        for item in safe_list(source.get("categories"))
        if _safe_int(safe_dict(item).get("id")) is not None
    }
    required = sorted({_canonical_class_label(item) for item in required_classes or [] if safe_str(item)})
    split_classes = {
        split_name: {
            category_labels.get(_safe_int(safe_dict(annotation).get("category_id")), "")
            for annotation in safe_list(source.get("annotations"))
            if _safe_int(safe_dict(annotation).get("image_id")) in set(splits[split_name])
        }
        for split_name in SUPPORTED_SPLITS
    }
    missing_class_coverage = [
        f"{split_name}:{label}"
        for split_name in SUPPORTED_SPLITS
        for label in required
        if label not in split_classes[split_name]
    ]
    if missing_class_coverage:
        raise ValueError(
            "Combined COCO evidence is missing required class coverage: "
            + ", ".join(missing_class_coverage)
        )
    expected_frozen = build_frozen_split_manifest(source)
    held_out_commitment = build_held_out_test_commitment(expected_frozen)
    declared_frozen = safe_dict(source.get("frozen_split_manifest"))
    if declared_frozen and declared_frozen != expected_frozen:
        raise ValueError("Combined COCO frozen-test manifest is invalid or stale.")

    def scoped(*, role: str, included_splits: Sequence[str]) -> Dict[str, Any]:
        included = set(included_splits)
        selected_images = [
            scope_coco_image_record(image)
            for image in safe_list(source.get("images"))
            if safe_str(safe_dict(image).get("split")).lower() in included
        ]
        selected_ids = {
            _safe_int(image.get("id"))
            for image in selected_images
            if _safe_int(image.get("id")) is not None
        }
        selected_annotations = [
            scope_coco_annotation_record(annotation)
            for annotation in safe_list(source.get("annotations"))
            if _safe_int(safe_dict(annotation).get("image_id")) in selected_ids
        ]
        result = {
            "version": safe_str(source.get("version")),
            "generated_at": safe_str(source.get("generated_at")),
            "info": _scoped_coco_info(source.get("info")),
            "licenses": scope_coco_license_records(source.get("licenses")),
            "categories": [
                scope_coco_category_record(item)
                for item in safe_list(source.get("categories"))
                if safe_dict(item)
            ],
            "ground_truth_attestation": _scoped_ground_truth_attestation(
                source.get("ground_truth_attestation")
            ),
            "supervision_status": safe_str(source.get("supervision_status")),
            "source_supervision_status": safe_str(source.get("source_supervision_status")),
            "truth_label": safe_str(source.get("truth_label")),
            "dataset_role": role,
            "parent_coco_evidence_fingerprint": declared_fingerprint,
            "images": selected_images,
            "annotations": selected_annotations,
            "splits": {
                name: [
                    int(image["id"])
                    for image in selected_images
                    if safe_str(image.get("split")).lower() == name
                ]
                for name in SUPPORTED_SPLITS
            },
            "eligible_image_count": len(selected_images),
            "annotation_count": len(selected_annotations),
            "contains_image_bytes": False,
            "evaluation_eligible": False,
            "promotion_eligible": False,
            "promotion_blockers": [
                "training_package_is_not_independent_evaluation"
                if role == "training_and_validation"
                else "model_quality_coverage_calibration_and_approval_gates_pending"
            ],
        }
        for field in ("benchmark_import_version", "bootstrap_version"):
            if safe_str(source.get(field)):
                result[field] = safe_str(source.get(field))
        if safe_list(source.get("source_registry_fingerprints")):
            result["source_registry_fingerprints"] = scope_registry_fingerprints(
                source.get("source_registry_fingerprints")
            )
        if role == "frozen_test" and safe_dict(source.get("evaluation_scope")):
            result["evaluation_scope"] = _scoped_evaluation_scope(source.get("evaluation_scope"))
        if role == "training_and_validation":
            result["held_out_test_manifest"] = deepcopy(held_out_commitment)
            result["test_records_in_package"] = False
        else:
            result["training_records_in_package"] = False
        result["dataset_fingerprint"] = coco_dataset_fingerprint(result)
        return result

    training = scoped(
        role="training_and_validation",
        included_splits=("train", "validation"),
    )
    evaluation = scoped(role="frozen_test", included_splits=("test",))
    evaluation["frozen_split_manifest"] = build_frozen_split_manifest(evaluation)
    integrity = assess_coco_evidence_integrity(
        evaluation,
        evaluation_split="test",
        training_package=training,
        required_classes=required_classes,
    )
    if integrity["promotion_eligible"] is not True:
        raise ValueError(
            "Split-scoped COCO evidence failed integrity verification: "
            + ", ".join(safe_list(integrity.get("blockers")))
        )
    evaluation["evidence_integrity"] = integrity
    evaluation["evaluation_eligible"] = True
    return {
        "training_validation": training,
        "frozen_test": evaluation,
    }


def _scoped_coco_info(value: Any) -> Dict[str, Any]:
    source = safe_dict(value)
    return {
        key: deepcopy(source[key])
        for key in (
            "description",
            "contains_image_bytes",
            "split_seed",
            "source_dataset",
            "source_url",
            "attribution",
        )
        if key in source
    }


def scope_coco_license_records(value: Any) -> List[Dict[str, Any]]:
    allowed = {
        "id",
        "name",
        "url",
        "license",
        "license_url",
        "attribution",
        "source_id",
        "source_role",
        "source_rights",
    }
    records: List[Dict[str, Any]] = []
    for item in (safe_dict(raw) for raw in safe_list(value)):
        if not item:
            continue
        record = {key: deepcopy(item[key]) for key in allowed if key in item and key != "source_rights"}
        if safe_dict(item.get("source_rights")):
            record["source_rights"] = scope_source_rights_record(item.get("source_rights"))
        records.append(record)
    return records


def scope_coco_category_record(value: Any) -> Dict[str, Any]:
    source = safe_dict(value)
    allowed = {"id", "name", "supercategory", "source_feature_type", "color"}
    return {key: deepcopy(source[key]) for key in allowed if key in source}


def scope_coco_image_record(value: Any) -> Dict[str, Any]:
    source = safe_dict(value)
    allowed = {
        "id",
        "asset_id",
        "file_name",
        "width",
        "height",
        "split",
        "imagery_frame_id",
        "source_sha256",
        "label_sha256",
        "converted_sha256",
        "source_image_id",
        "source_item_ids",
        "source_item_names",
        "source_url",
        "source_vendor",
        "source_agency",
        "source_dataset",
        "source_file",
        "label_file",
        "bbox_wgs84",
        "geography_id",
        "geography",
        "aoi",
        "datum",
        "resolution_meters",
        "capture_date",
        "capture_year",
        "season",
        "sensor_type",
        "imagery_quality_band",
        "density_band",
    }
    record = {key: deepcopy(source[key]) for key in allowed if key in source}
    if safe_dict(source.get("source_rights")):
        record["source_rights"] = scope_source_rights_record(source.get("source_rights"))
    return record


def scope_coco_annotation_record(value: Any) -> Dict[str, Any]:
    source = safe_dict(value)
    allowed = {
        "id",
        "image_id",
        "category_id",
        "category_name",
        "segmentation",
        "bbox",
        "area",
        "iscrowd",
        "feature_type",
        "geo_geometry",
        "label_license",
        "label_source",
        "review_status",
        "review_action",
        "example_id",
        "source_annotation_id",
        "source_confidence",
        "source_dataset",
        "supervision",
    }
    return {key: deepcopy(source[key]) for key in allowed if key in source}


def scope_source_rights_record(value: Any) -> Dict[str, Any]:
    source = safe_dict(value)
    allowed = {
        "license",
        "license_url",
        "rights_source",
        "rights_review_status",
        "rights_registry_fingerprint",
        "training_use_allowed",
        "storage_allowed",
        "derivative_labels_allowed",
        "redistribution_allowed",
    }
    return {key: deepcopy(source[key]) for key in allowed if key in source}


def scope_registry_fingerprints(value: Any) -> List[Any]:
    records: List[Any] = []
    for item in safe_list(value):
        if isinstance(item, str) and _is_sha256(item):
            records.append(item.lower())
            continue
        source = safe_dict(item)
        allowed = {"registry_fingerprint", "rights_registry_fingerprint"}
        record = {
            key: safe_str(source[key]).lower()
            for key in allowed
            if key in source and _is_sha256(safe_str(source[key]))
        }
        if record:
            records.append(record)
    return records


def _scoped_ground_truth_attestation(value: Any) -> Dict[str, Any]:
    source = safe_dict(value)
    allowed = {
        "status",
        "dataset_name",
        "dataset_url",
        "license",
        "attribution",
        "independent_test_split",
        "test_images_excluded_from_training",
        "annotation_source",
        "reviewed_by",
        "reviewed_at",
    }
    return {key: deepcopy(source[key]) for key in allowed if key in source}


def _scoped_evaluation_scope(value: Any) -> Dict[str, Any]:
    source = safe_dict(value)
    allowed = {
        "geography_count",
        "geographies",
        "season_count",
        "seasons",
        "season_metadata_status",
        "imagery_quality_band_count",
        "imagery_quality_bands",
        "density_band_count",
        "density_bands",
        "supported_classes",
    }
    return {key: deepcopy(source[key]) for key in allowed if key in source}


def declared_coco_evidence_fingerprint(package: Dict[str, Any]) -> str:
    """Return the declared canonical evaluation identity, with legacy package fallback."""

    return _declared_coco_fingerprint(safe_dict(package))


def evidence_context_fingerprint(package: Dict[str, Any]) -> str:
    source = safe_dict(package)
    return _stable_hash(
        {
            "ground_truth_attestation": safe_dict(source.get("ground_truth_attestation")),
            "evaluation_scope": safe_dict(source.get("evaluation_scope")),
            "supervision_status": safe_str(
                source.get("source_supervision_status") or source.get("supervision_status")
            ),
        }
    )


def build_frozen_split_manifest(package: Dict[str, Any]) -> Dict[str, Any]:
    source = safe_dict(package)
    images = _images_by_id(source)
    split_ids = _split_ids(source, images)
    test_images = [images[image_id] for image_id in split_ids["test"] if image_id in images]
    identities = sorted(
        {_content_image_identity(item) for item in test_images if _content_image_identity(item)}
    )
    payload = {
        "version": FROZEN_SPLIT_VERSION,
        "dataset_fingerprint": _declared_coco_fingerprint(source),
        "test_image_count": len(test_images),
        "test_annotation_count": _annotation_count_for_images(source, set(split_ids["test"])),
        "test_image_ids_sha256": _stable_hash(sorted(split_ids["test"])),
        "test_source_identities_sha256": _stable_hash(identities),
        "test_source_identity_count": len(identities),
        "test_split_mutation_allowed": False,
    }
    payload["manifest_sha256"] = _stable_hash(payload)
    return payload


def build_held_out_test_commitment(frozen_manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Return the label-blind frozen-test identity exposed to model development."""

    frozen = safe_dict(frozen_manifest)
    payload = {
        "version": HELD_OUT_COMMITMENT_VERSION,
        "dataset_fingerprint": safe_str(frozen.get("dataset_fingerprint")).lower(),
        "test_image_membership_sha256": frozen_test_image_membership_fingerprint(frozen),
        "test_image_count": int(frozen.get("test_image_count") or 0),
        "test_image_ids_sha256": safe_str(frozen.get("test_image_ids_sha256")).lower(),
        "test_source_identities_sha256": safe_str(frozen.get("test_source_identities_sha256")).lower(),
        "test_source_identity_count": int(frozen.get("test_source_identity_count") or 0),
        "test_split_mutation_allowed": False,
        "label_statistics_disclosed": False,
    }
    payload["manifest_sha256"] = _stable_hash(payload)
    return payload


def validate_held_out_test_commitment(commitment: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the exact label-blind schema exposed to model development."""

    rec = safe_dict(commitment)
    blockers: List[str] = []
    blockers.extend(
        f"training_held_out_manifest_unknown_field:{field}"
        for field in sorted(set(rec) - HELD_OUT_COMMITMENT_FIELDS)
    )
    blockers.extend(
        f"training_held_out_manifest_required_field_missing:{field}"
        for field in sorted(HELD_OUT_COMMITMENT_FIELDS - set(rec))
    )
    if safe_str(rec.get("version")) != HELD_OUT_COMMITMENT_VERSION:
        blockers.append("training_held_out_manifest_version_invalid")
    for field in (
        "dataset_fingerprint",
        "test_image_membership_sha256",
        "test_image_ids_sha256",
        "test_source_identities_sha256",
    ):
        if not _is_sha256(safe_str(rec.get(field)).lower()):
            blockers.append(f"training_held_out_manifest_{field}_invalid")
    image_count = int(rec.get("test_image_count") or 0)
    source_count = int(rec.get("test_source_identity_count") or 0)
    if image_count <= 0 or source_count != image_count:
        blockers.append("training_held_out_manifest_image_membership_invalid")
    if rec.get("test_split_mutation_allowed") is not False:
        blockers.append("training_held_out_manifest_mutation_boundary_invalid")
    if rec.get("label_statistics_disclosed") is not False:
        blockers.append("training_held_out_manifest_label_blind_boundary_invalid")
    expected_sha = _stable_hash({key: value for key, value in rec.items() if key != "manifest_sha256"})
    if safe_str(rec.get("manifest_sha256")).lower() != expected_sha:
        blockers.append("training_held_out_manifest_fingerprint_invalid")
    return {
        "valid": not blockers,
        "blockers": sorted(set(blockers)),
        "manifest_sha256": expected_sha,
    }


def assess_coco_evidence_integrity(
    package: Dict[str, Any],
    *,
    evaluation_split: str = "test",
    training_package: Optional[Dict[str, Any]] = None,
    required_classes: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    source = safe_dict(package)
    blockers: List[str] = []
    notes: List[str] = []
    images = _images_by_id(source, blockers=blockers)
    split_ids = _split_ids(source, images, blockers=blockers)
    split = safe_str(evaluation_split).lower()
    if split not in SUPPORTED_SPLITS:
        blockers.append("unsupported_evaluation_split")
        split = "test"

    declared_fingerprint = _declared_coco_fingerprint(source, fallback=False)
    computed_fingerprint = coco_dataset_fingerprint(source)
    if not declared_fingerprint:
        blockers.append("dataset_fingerprint_missing")
    elif declared_fingerprint != computed_fingerprint:
        blockers.append("dataset_fingerprint_mismatch")

    for left_index, left in enumerate(SUPPORTED_SPLITS):
        for right in SUPPORTED_SPLITS[left_index + 1 :]:
            overlap = set(split_ids[left]) & set(split_ids[right])
            if overlap:
                blockers.append(f"image_id_overlap:{left}:{right}")

    image_split_membership: Dict[int, Set[str]] = {}
    for split_name, image_ids in split_ids.items():
        for image_id in image_ids:
            image_split_membership.setdefault(image_id, set()).add(split_name)
    for image_id, image in images.items():
        declared_split = safe_str(image.get("split")).lower()
        if declared_split and declared_split not in SUPPORTED_SPLITS:
            blockers.append(f"image_split_invalid:{image_id}")
        if declared_split and declared_split not in image_split_membership.get(image_id, set()):
            blockers.append(f"image_split_manifest_mismatch:{image_id}")

    source_identities_by_split = {
        split_name: {
            identity
            for image_id in image_ids
            if image_id in images
            for identity in [_content_image_identity(images[image_id])]
            if identity
        }
        for split_name, image_ids in split_ids.items()
    }
    for split_name, image_ids in split_ids.items():
        missing_content_identity = [
            image_id
            for image_id in image_ids
            if image_id in images and not _content_image_identity(images[image_id])
        ]
        blockers.extend(
            f"source_content_fingerprint_missing:{split_name}:{image_id}"
            for image_id in missing_content_identity
        )
        if len(source_identities_by_split[split_name]) != len(image_ids) - len(missing_content_identity):
            blockers.append(f"duplicate_source_content_identity:{split_name}")
    test_source_identity_digests = sorted(
        hashlib.sha256(identity.encode("utf-8")).hexdigest()
        for identity in source_identities_by_split["test"]
    )
    for left_index, left in enumerate(SUPPORTED_SPLITS):
        for right in SUPPORTED_SPLITS[left_index + 1 :]:
            overlap = source_identities_by_split[left] & source_identities_by_split[right]
            if overlap:
                blockers.append(f"source_identity_overlap:{left}:{right}")

    annotation_image_ids: Set[int] = set()
    evaluated_classes: Set[str] = set()
    category_labels = {
        _safe_int(item.get("id")): _canonical_class_label(item.get("name"))
        for item in safe_list(source.get("categories"))
        if safe_dict(item) and _safe_int(safe_dict(item).get("id")) is not None
    }
    for index, item in enumerate(safe_list(source.get("annotations")), start=1):
        rec = safe_dict(item)
        image_id = _safe_int(rec.get("image_id"))
        if image_id is None or image_id not in images:
            blockers.append(f"annotation_image_missing:{index}")
            continue
        annotation_image_ids.add(image_id)
        if image_id in split_ids[split]:
            label = category_labels.get(_safe_int(rec.get("category_id")))
            if label:
                evaluated_classes.add(label)

    if not split_ids[split]:
        blockers.append(f"evaluation_split_empty:{split}")
    if not annotation_image_ids.intersection(split_ids[split]):
        blockers.append(f"evaluation_annotations_missing:{split}")
    for label in required_classes or []:
        canonical_label = _canonical_class_label(label)
        if canonical_label not in evaluated_classes:
            blockers.append(f"required_class_missing_from_evaluation_split:{canonical_label}")

    frozen = safe_dict(source.get("frozen_split_manifest"))
    expected_frozen = build_frozen_split_manifest(source)
    frozen_valid = bool(frozen) and all(
        frozen.get(key) == expected_frozen.get(key)
        for key in (
            "version",
            "dataset_fingerprint",
            "test_image_count",
            "test_annotation_count",
            "test_image_ids_sha256",
            "test_source_identities_sha256",
            "test_source_identity_count",
            "test_split_mutation_allowed",
            "manifest_sha256",
        )
    )
    if split == "test" and not frozen:
        blockers.append("frozen_test_split_manifest_missing")
    elif split == "test" and not frozen_valid:
        blockers.append("frozen_test_split_manifest_invalid")

    training_fingerprint = ""
    development_overlap_count = 0
    training_development_geographies: Set[str] = set()
    held_out_manifest_bound = False
    training_evidence_attached = training_package is not None
    physical_split_isolation_proven = False
    if training_package is None:
        blockers.append("training_dataset_evidence_missing")
    else:
        training = safe_dict(training_package)
        training_fingerprint = _declared_coco_fingerprint(training)
        training_images = _images_by_id(training)
        training_splits = _split_ids(training, training_images)
        development_ids = set(training_splits["train"]) | set(training_splits["validation"])
        training_development_geographies = {
            safe_str(
                training_images[image_id].get("geography")
                or training_images[image_id].get("geography_id")
            )
            for image_id in development_ids
            if image_id in training_images
            and safe_str(
                training_images[image_id].get("geography")
                or training_images[image_id].get("geography_id")
            )
        }
        development_identities = {
            identity
            for image_id in development_ids
            if image_id in training_images
            for identity in [_content_image_identity(training_images[image_id])]
            if identity
        }
        training_missing_content_identity = [
            image_id
            for image_id in development_ids
            if image_id in training_images and not _content_image_identity(training_images[image_id])
        ]
        blockers.extend(
            f"training_source_content_fingerprint_missing:{image_id}"
            for image_id in training_missing_content_identity
        )
        if len(development_identities) != len(development_ids) - len(training_missing_content_identity):
            blockers.append("training_duplicate_source_content_identity")
        test_identities = source_identities_by_split["test"]
        development_overlap_count = len(development_identities & test_identities)
        if development_overlap_count:
            blockers.append("development_test_source_identity_overlap")
        if not training_splits["train"]:
            blockers.append("training_split_empty")
        strict_scoped_test = split == "test"
        if strict_scoped_test:
            if safe_str(source.get("dataset_role")) != "frozen_test":
                blockers.append("evaluation_dataset_role_not_frozen_test")
            if safe_str(training.get("dataset_role")) != "training_and_validation":
                blockers.append("training_dataset_role_not_training_and_validation")
            physical_split_isolation_proven = (
                safe_str(source.get("dataset_role")) == "frozen_test"
                and safe_str(training.get("dataset_role")) == "training_and_validation"
                and not split_ids["train"]
                and not split_ids["validation"]
                and not training_splits["test"]
                and bool(source.get("training_records_in_package") is False)
                and bool(training.get("test_records_in_package") is False)
                and declared_fingerprint != training_fingerprint
            )
            if not physical_split_isolation_proven:
                blockers.append("physical_split_isolation_not_proven")
            held_out = safe_dict(training.get("held_out_test_manifest"))
            expected_held_out = build_held_out_test_commitment(expected_frozen)
            held_out_validation = validate_held_out_test_commitment(held_out)
            held_out_manifest_bound = bool(held_out) and held_out_validation["valid"] and all(
                held_out.get(key) == expected_held_out.get(key) for key in FROZEN_IDENTITY_FIELDS
            ) and (
                safe_str(held_out.get("test_image_membership_sha256"))
                == safe_str(expected_held_out.get("test_image_membership_sha256"))
            )
            if not held_out:
                blockers.append("training_held_out_manifest_missing")
            elif not held_out_manifest_bound:
                blockers.append("training_held_out_manifest_mismatch")
            blockers.extend(held_out_validation["blockers"])
            source_family = safe_str(
                source.get("parent_coco_evidence_fingerprint") or source.get("dataset_fingerprint")
            )
            training_family = safe_str(
                training.get("parent_coco_evidence_fingerprint") or held_out.get("dataset_fingerprint")
            )
            if not source_family or source_family != training_family:
                blockers.append("training_evaluation_evidence_family_mismatch")
            if safe_str(held_out.get("dataset_fingerprint")) != training_family:
                blockers.append("training_held_out_manifest_evidence_family_mismatch")

    geographic_policy = safe_dict(source.get("split_policy"))
    geography_by_split = {
        split_name: {
            safe_str(images[image_id].get("geography") or images[image_id].get("geography_id"))
            for image_id in image_ids
            if image_id in images
            and safe_str(images[image_id].get("geography") or images[image_id].get("geography_id"))
        }
        for split_name, image_ids in split_ids.items()
    }
    development_geographies = geography_by_split["train"] | geography_by_split["validation"]
    geography_overlap = sorted(
        (development_geographies | training_development_geographies)
        & geography_by_split["test"]
    )
    if safe_str(geographic_policy.get("strategy")) == "geography_disjoint" and geography_overlap:
        blockers.append("development_test_geography_overlap")
    elif geography_overlap:
        notes.append("benchmark_is_image_disjoint_but_not_geography_disjoint")

    unique_blockers = sorted(set(blockers))
    hard_evaluation_blockers = {
        item
        for item in unique_blockers
        if not item.startswith("training_")
    }
    result = {
        "version": EVIDENCE_INTEGRITY_VERSION,
        "valid": not unique_blockers,
        "evaluation_eligible": not hard_evaluation_blockers,
        "promotion_eligible": not unique_blockers,
        "evaluation_split": split,
        "dataset_fingerprint": declared_fingerprint,
        "computed_dataset_fingerprint": computed_fingerprint,
        "evidence_context_fingerprint": evidence_context_fingerprint(source),
        "training_dataset_fingerprint": training_fingerprint,
        "training_evidence_attached": training_evidence_attached,
        "training_test_source_identity_overlap_count": development_overlap_count,
        "development_test_source_identity_overlap_count": development_overlap_count,
        "training_held_out_manifest_bound": held_out_manifest_bound,
        "physical_split_isolation_proven": physical_split_isolation_proven,
        "split_counts": {name: len(ids) for name, ids in split_ids.items()},
        "evaluation_annotation_count": _annotation_count_for_images(source, set(split_ids[split])),
        "evaluation_classes": sorted(evaluated_classes),
        "frozen_test_split_valid": frozen_valid,
        "frozen_test_manifest": expected_frozen,
        "test_source_identity_digests": test_source_identity_digests,
        "train_test_geography_overlap_count": len(geography_overlap),
        "development_test_geography_overlap_count": len(geography_overlap),
        "blockers": unique_blockers,
        "notes": sorted(set(notes)),
        "contains_image_bytes": False,
        "truth_label": (
            "This report verifies manifest, split, source-identity, and frozen-test integrity. It does not establish "
            "model accuracy; promotion still requires independently measured quality, coverage, calibration, baseline "
            "comparison, and named human approval."
        ),
    }
    result["integrity_fingerprint"] = evidence_integrity_fingerprint(result)
    return result


def build_test_consumption_receipt(
    evidence_integrity: Dict[str, Any],
    *,
    candidate_id: str,
    model_artifact_sha256: str,
    threshold_calibration_fingerprint: str = "",
    consumed_at: str = "",
    reservation_mode: str = "pre_evaluation_atomic",
    evaluation_reservation_manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    integrity = safe_dict(evidence_integrity)
    candidate = safe_str(candidate_id)
    model_sha = safe_str(model_artifact_sha256).lower()
    if not candidate or len(candidate) > 160 or not re.fullmatch(r"[A-Za-z0-9._:@/+-]+", candidate):
        raise ValueError("candidate_id must be a stable, non-sensitive identifier.")
    if not _is_sha256(model_sha):
        raise ValueError("model_artifact_sha256 must be a lowercase SHA-256 digest.")
    calibration_fingerprint = safe_str(threshold_calibration_fingerprint).lower()
    timestamp = safe_str(consumed_at) or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if not _is_utc_timestamp(timestamp):
        raise ValueError("consumed_at must be a timezone-aware ISO-8601 timestamp.")
    mode = safe_str(reservation_mode)
    if mode not in {"pre_evaluation_atomic", "post_hoc_rejection_record"}:
        raise ValueError("Unsupported frozen-test reservation mode.")
    if mode == "pre_evaluation_atomic" and not _is_sha256(calibration_fingerprint):
        raise ValueError("A validation threshold-calibration fingerprint is required before frozen-test reservation.")
    if calibration_fingerprint and not _is_sha256(calibration_fingerprint):
        raise ValueError("threshold_calibration_fingerprint must be a SHA-256 digest.")
    reservation = safe_dict(evaluation_reservation_manifest)
    reservation_validation = (
        validate_evaluation_reservation_manifest(reservation)
        if reservation
        else {"valid": False, "blockers": ["evaluation_reservation_manifest_missing"]}
    )
    if mode == "pre_evaluation_atomic" and not reservation_validation["valid"]:
        raise ValueError("A valid sealed evaluation reservation manifest is required.")
    frozen = safe_dict(integrity.get("frozen_test_manifest"))
    if integrity:
        validation = validate_evidence_integrity_report(integrity)
        if not validation["promotion_eligible"]:
            raise ValueError("Frozen-test evidence integrity must be promotion-eligible before it can be consumed.")
        if safe_str(integrity.get("evaluation_split")) != "test":
            raise ValueError("A frozen-test consumption receipt can only be issued for the test split.")
        if integrity.get("physical_split_isolation_proven") is not True:
            raise ValueError("Physical training/evaluation package isolation is required.")
        if not frozen or frozen.get("test_split_mutation_allowed") is not False:
            raise ValueError("A valid immutable frozen-test manifest is required.")
    if mode == "post_hoc_rejection_record" and not integrity:
        raise ValueError("Post-hoc rejection receipts require verified frozen-test integrity.")
    if reservation and integrity and (
        safe_str(reservation.get("evaluation_dataset_fingerprint")).lower()
        != safe_str(integrity.get("dataset_fingerprint")).lower()
        or safe_str(reservation.get("test_image_membership_sha256")).lower()
        != frozen_test_image_membership_fingerprint(frozen)
    ):
        raise ValueError("Evaluation reservation does not match frozen evidence integrity.")
    source = reservation if mode == "pre_evaluation_atomic" else integrity
    source_frozen = reservation if mode == "pre_evaluation_atomic" else frozen
    payload = {
        "version": TEST_CONSUMPTION_RECEIPT_VERSION,
        "candidate_id": candidate,
        "model_artifact_sha256": model_sha,
        "threshold_calibration_fingerprint": calibration_fingerprint,
        "evaluation_dataset_fingerprint": safe_str(source.get("evaluation_dataset_fingerprint") or source.get("dataset_fingerprint")).lower(),
        "test_image_membership_sha256": safe_str(
            source.get("test_image_membership_sha256")
            or frozen_test_image_membership_fingerprint(source_frozen)
        ).lower(),
        "test_image_ids_sha256": safe_str(source_frozen.get("test_image_ids_sha256")).lower(),
        "test_source_identities_sha256": safe_str(source_frozen.get("test_source_identities_sha256")).lower(),
        "test_source_identity_digests": sorted(
            {
                safe_str(item).lower()
                for item in safe_list(source.get("test_source_identity_digests"))
                if _is_sha256(safe_str(item).lower())
            }
        ),
        "test_image_count": int(source_frozen.get("test_image_count") or 0),
        "label_statistics_disclosed": False,
        "consumed_at": timestamp,
        "reservation_mode": mode,
        "evaluation_reservation_manifest_sha256": safe_str(reservation.get("manifest_sha256")).lower(),
        "purpose": "one_way_final_model_evaluation",
        "reusable_as_untouched_evidence": False,
    }
    payload["receipt_sha256"] = test_consumption_receipt_fingerprint(payload)
    receipt_validation = validate_test_consumption_receipt(
        payload,
        evaluation_dataset_fingerprint=safe_str(payload.get("evaluation_dataset_fingerprint")),
        model_artifact_sha256=model_sha,
        threshold_calibration_fingerprint=calibration_fingerprint,
    )
    if not receipt_validation["valid"]:
        raise ValueError("Generated frozen-test consumption receipt is invalid.")
    return payload


def test_consumption_receipt_fingerprint(receipt: Dict[str, Any]) -> str:
    return _stable_hash(
        {key: value for key, value in safe_dict(receipt).items() if key != "receipt_sha256"}
    )


def validate_test_consumption_receipt(
    receipt: Dict[str, Any],
    *,
    evaluation_dataset_fingerprint: str = "",
    model_artifact_sha256: str = "",
    threshold_calibration_fingerprint: str = "",
) -> Dict[str, Any]:
    rec = safe_dict(receipt)
    blockers: List[str] = []
    blockers.extend(
        f"test_consumption_receipt_unknown_field:{field}"
        for field in sorted(set(rec) - TEST_CONSUMPTION_RECEIPT_FIELDS)
    )
    blockers.extend(
        f"test_consumption_receipt_required_field_missing:{field}"
        for field in sorted(TEST_CONSUMPTION_RECEIPT_FIELDS - set(rec))
    )
    if safe_str(rec.get("version")) != TEST_CONSUMPTION_RECEIPT_VERSION:
        blockers.append("unsupported_test_consumption_receipt_version")
    candidate = safe_str(rec.get("candidate_id"))
    if not candidate or len(candidate) > 160 or not re.fullmatch(r"[A-Za-z0-9._:@/+-]+", candidate):
        blockers.append("test_consumption_candidate_id_invalid")
    for field in (
        "model_artifact_sha256",
        "evaluation_dataset_fingerprint",
        "test_image_membership_sha256",
        "test_image_ids_sha256",
        "test_source_identities_sha256",
    ):
        if not _is_sha256(safe_str(rec.get(field)).lower()):
            blockers.append(f"test_consumption_{field}_invalid")
    calibration_fingerprint = safe_str(rec.get("threshold_calibration_fingerprint")).lower()
    reservation_sha = safe_str(rec.get("evaluation_reservation_manifest_sha256")).lower()
    if reservation_sha and not _is_sha256(reservation_sha):
        blockers.append("test_consumption_evaluation_reservation_manifest_sha256_invalid")
    identity_digests = [safe_str(item).lower() for item in safe_list(rec.get("test_source_identity_digests"))]
    if (
        len(identity_digests) != int(rec.get("test_image_count") or 0)
        or len(identity_digests) != len(set(identity_digests))
        or any(not _is_sha256(item) for item in identity_digests)
    ):
        blockers.append("test_consumption_source_identity_membership_invalid")
    if int(rec.get("test_image_count") or 0) <= 0:
        blockers.append("test_consumption_image_count_invalid")
    if rec.get("label_statistics_disclosed") is not False or "test_annotation_count" in rec:
        blockers.append("test_consumption_label_blind_boundary_invalid")
    if not _is_utc_timestamp(safe_str(rec.get("consumed_at"))):
        blockers.append("test_consumption_timestamp_invalid")
    if safe_str(rec.get("purpose")) != "one_way_final_model_evaluation":
        blockers.append("test_consumption_purpose_invalid")
    mode = safe_str(rec.get("reservation_mode"))
    if mode not in {"pre_evaluation_atomic", "post_hoc_rejection_record"}:
        blockers.append("test_consumption_reservation_mode_invalid")
    if mode == "pre_evaluation_atomic" and not _is_sha256(
        safe_str(rec.get("evaluation_reservation_manifest_sha256")).lower()
    ):
        blockers.append("test_consumption_evaluation_reservation_missing")
    if mode == "pre_evaluation_atomic" and not _is_sha256(calibration_fingerprint):
        blockers.append("test_consumption_threshold_calibration_missing")
    if calibration_fingerprint and not _is_sha256(calibration_fingerprint):
        blockers.append("test_consumption_threshold_calibration_fingerprint_invalid")
    if rec.get("reusable_as_untouched_evidence") is not False:
        blockers.append("test_consumption_reuse_boundary_invalid")
    expected_receipt_sha = test_consumption_receipt_fingerprint(rec)
    if safe_str(rec.get("receipt_sha256")).lower() != expected_receipt_sha:
        blockers.append("test_consumption_receipt_fingerprint_mismatch")
    expected_values = {
        "evaluation_dataset_fingerprint": safe_str(evaluation_dataset_fingerprint).lower(),
        "model_artifact_sha256": safe_str(model_artifact_sha256).lower(),
        "threshold_calibration_fingerprint": safe_str(threshold_calibration_fingerprint).lower(),
    }
    for field, expected in expected_values.items():
        if expected and safe_str(rec.get(field)).lower() != expected:
            blockers.append(f"test_consumption_{field}_mismatch")
    return {
        "valid": not blockers,
        "promotion_eligible": not blockers and mode == "pre_evaluation_atomic",
        "blockers": sorted(set(blockers)),
        "receipt_sha256": expected_receipt_sha,
        "candidate_id": candidate,
        "evaluation_dataset_fingerprint": safe_str(rec.get("evaluation_dataset_fingerprint")).lower(),
        "threshold_calibration_fingerprint": calibration_fingerprint,
    }


def append_test_consumption_receipt(
    ledger: Optional[Dict[str, Any]],
    receipt: Dict[str, Any],
) -> Dict[str, Any]:
    rec = safe_dict(receipt)
    receipt_validation = validate_test_consumption_receipt(rec)
    if not receipt_validation["valid"]:
        raise ValueError("Cannot append an invalid frozen-test consumption receipt.")
    current = safe_dict(ledger)
    if current:
        ledger_validation = validate_test_consumption_ledger(current)
        if not ledger_validation["valid"]:
            raise ValueError("Cannot append to an invalid frozen-test consumption ledger.")
        entries = [safe_dict(item) for item in safe_list(current.get("entries"))]
    else:
        entries = []
    evaluation_fingerprint = safe_str(rec.get("evaluation_dataset_fingerprint")).lower()
    consumed_identity_digests = {
        safe_str(value).lower()
        for item in entries
        for value in safe_list(item.get("test_source_identity_digests"))
        if safe_str(value)
    }
    incoming_identity_digests = {
        safe_str(value).lower()
        for value in safe_list(rec.get("test_source_identity_digests"))
        if safe_str(value)
    }
    if any(
        safe_str(item.get("evaluation_dataset_fingerprint")).lower() == evaluation_fingerprint
        for item in entries
    ) or consumed_identity_digests.intersection(incoming_identity_digests):
        raise ValueError("Frozen test evidence has already been consumed and cannot be reused.")
    payload = {
        "version": TEST_CONSUMPTION_LEDGER_VERSION,
        "entries": [*entries, rec],
    }
    payload["ledger_sha256"] = test_consumption_ledger_fingerprint(payload)
    return payload


def reserve_test_consumption(
    ledger_path: str | Path,
    receipt: Dict[str, Any],
) -> Dict[str, Any]:
    """Atomically reserve frozen evidence before any model sees evaluation image bytes."""

    path = Path(ledger_path).expanduser().resolve()
    if safe_str(receipt.get("reservation_mode")) != "pre_evaluation_atomic":
        raise ValueError("Atomic reservation accepts only pre-evaluation receipts.")
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with os.fdopen(lock_fd, "r+", encoding="utf-8") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            current: Dict[str, Any] = {}
            if path.exists():
                try:
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise ValueError("Frozen-test consumption ledger is unreadable or corrupt.") from exc
                if not isinstance(loaded, dict):
                    raise ValueError("Frozen-test consumption ledger must contain a JSON object.")
                current = loaded
                ledger_validation = validate_test_consumption_ledger(current)
                if not ledger_validation["valid"]:
                    raise ValueError("Frozen-test consumption ledger is invalid or was tampered with.")
                matching = next(
                    (
                        safe_dict(item)
                        for item in safe_list(current.get("entries"))
                        if safe_str(safe_dict(item).get("evaluation_dataset_fingerprint")).lower()
                        == safe_str(receipt.get("evaluation_dataset_fingerprint")).lower()
                    ),
                    {},
                )
                if matching:
                    raise ValueError("Frozen test evidence has already been consumed and cannot be reopened.")
            ledger = append_test_consumption_receipt(current, receipt)
            encoded = json.dumps(ledger, indent=2, sort_keys=True) + "\n"
            with temp_path.open("x", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            return {
                "created": True,
                "receipt": receipt,
                "ledger": ledger,
            }
    finally:
        temp_path.unlink(missing_ok=True)


def test_consumption_ledger_fingerprint(ledger: Dict[str, Any]) -> str:
    return _stable_hash(
        {key: value for key, value in safe_dict(ledger).items() if key != "ledger_sha256"}
    )


def validate_test_consumption_ledger(
    ledger: Dict[str, Any],
    *,
    expected_receipt_sha256: str = "",
) -> Dict[str, Any]:
    rec = safe_dict(ledger)
    blockers: List[str] = []
    blockers.extend(
        f"test_consumption_ledger_unknown_field:{field}"
        for field in sorted(set(rec) - TEST_CONSUMPTION_LEDGER_FIELDS)
    )
    blockers.extend(
        f"test_consumption_ledger_required_field_missing:{field}"
        for field in sorted(TEST_CONSUMPTION_LEDGER_FIELDS - set(rec))
    )
    if safe_str(rec.get("version")) != TEST_CONSUMPTION_LEDGER_VERSION:
        blockers.append("unsupported_test_consumption_ledger_version")
    entries = [safe_dict(item) for item in safe_list(rec.get("entries"))]
    if not entries:
        blockers.append("test_consumption_ledger_empty")
    fingerprints: Set[str] = set()
    source_identity_digests: Set[str] = set()
    receipt_hashes: Set[str] = set()
    for index, entry in enumerate(entries, start=1):
        validation = validate_test_consumption_receipt(entry)
        blockers.extend(f"test_consumption_ledger_entry:{index}:{item}" for item in validation["blockers"])
        fingerprint = safe_str(entry.get("evaluation_dataset_fingerprint")).lower()
        if fingerprint in fingerprints:
            blockers.append("test_consumption_ledger_reused_frozen_evidence")
        fingerprints.add(fingerprint)
        entry_identity_digests = {
            safe_str(value).lower()
            for value in safe_list(entry.get("test_source_identity_digests"))
            if safe_str(value)
        }
        if source_identity_digests.intersection(entry_identity_digests):
            blockers.append("test_consumption_ledger_reused_source_identity")
        source_identity_digests.update(entry_identity_digests)
        receipt_hashes.add(safe_str(entry.get("receipt_sha256")).lower())
    expected_ledger_sha = test_consumption_ledger_fingerprint(rec)
    if safe_str(rec.get("ledger_sha256")).lower() != expected_ledger_sha:
        blockers.append("test_consumption_ledger_fingerprint_mismatch")
    expected_receipt = safe_str(expected_receipt_sha256).lower()
    if expected_receipt and expected_receipt not in receipt_hashes:
        blockers.append("test_consumption_receipt_not_recorded_in_ledger")
    return {
        "valid": not blockers,
        "promotion_eligible": not blockers
        and all(
            validate_test_consumption_receipt(entry).get("promotion_eligible") is True
            for entry in entries
        ),
        "blockers": sorted(set(blockers)),
        "ledger_sha256": expected_ledger_sha,
        "entry_count": len(entries),
        "recorded_receipt_sha256": sorted(receipt_hashes),
    }


def _declared_coco_fingerprint(package: Dict[str, Any], *, fallback: bool = True) -> str:
    source = safe_dict(package)
    declared = safe_str(source.get("coco_evidence_fingerprint") or source.get("dataset_fingerprint"))
    return declared or (coco_dataset_fingerprint(source) if fallback else "")


def _canonical_class_label(value: Any) -> str:
    label = safe_str(value).lower()
    return MODEL_CLASS_ALIASES.get(label, label)


def evidence_integrity_fingerprint(report: Dict[str, Any]) -> str:
    return _stable_hash(
        {
            key: value
            for key, value in safe_dict(report).items()
            if key not in {"integrity_fingerprint", "truth_label"}
        }
    )


def validate_evidence_integrity_report(report: Dict[str, Any]) -> Dict[str, Any]:
    rec = safe_dict(report)
    blockers: List[str] = []
    if safe_str(rec.get("version")) != EVIDENCE_INTEGRITY_VERSION:
        blockers.append("unsupported_evidence_integrity_version")
    expected = evidence_integrity_fingerprint(rec)
    if safe_str(rec.get("integrity_fingerprint")) != expected:
        blockers.append("evidence_integrity_fingerprint_mismatch")
    if rec.get("evaluation_eligible") is not True:
        blockers.append("evaluation_evidence_integrity_not_eligible")
    return {
        "valid": not blockers,
        "promotion_eligible": not blockers and rec.get("promotion_eligible") is True,
        "blockers": sorted(set(blockers)),
        "integrity_fingerprint": expected,
    }


def records_for_split(package: Dict[str, Any], split: str) -> List[Dict[str, Any]]:
    source = safe_dict(package)
    images = _images_by_id(source)
    selected_ids = set(_split_ids(source, images).get(safe_str(split).lower(), []))
    return [safe_dict(item) for item in safe_list(source.get("annotations")) if _safe_int(safe_dict(item).get("image_id")) in selected_ids]


def _images_by_id(package: Dict[str, Any], *, blockers: Optional[List[str]] = None) -> Dict[int, Dict[str, Any]]:
    result: Dict[int, Dict[str, Any]] = {}
    for index, item in enumerate(safe_list(package.get("images")), start=1):
        rec = safe_dict(item)
        image_id = _safe_int(rec.get("id"))
        if image_id is None:
            if blockers is not None:
                blockers.append(f"image_id_missing:{index}")
            continue
        if image_id in result and blockers is not None:
            blockers.append(f"duplicate_image_id:{image_id}")
        result[image_id] = rec
    return result


def _split_ids(
    package: Dict[str, Any],
    images: Dict[int, Dict[str, Any]],
    *,
    blockers: Optional[List[str]] = None,
) -> Dict[str, List[int]]:
    declared = safe_dict(package.get("splits"))
    result: Dict[str, List[int]] = {name: [] for name in SUPPORTED_SPLITS}
    for split in SUPPORTED_SPLITS:
        values = safe_list(declared.get(split))
        ids = [_safe_int(value) for value in values]
        result[split] = sorted({value for value in ids if value is not None})
        if blockers is not None:
            for value in ids:
                if value is not None and value not in images:
                    blockers.append(f"split_references_missing_image:{split}:{value}")
    for image_id, image in images.items():
        split = safe_str(image.get("split")).lower()
        if split in SUPPORTED_SPLITS and image_id not in result[split]:
            if blockers is not None and declared:
                blockers.append(f"image_split_manifest_mismatch:{image_id}")
            result[split].append(image_id)
            result[split].sort()
    return result


def _content_image_identity(image: Dict[str, Any]) -> str:
    rec = safe_dict(image)
    for key in (
        "source_sha256",
        "source_fingerprint_sha256",
        "converted_sha256",
        "sha256",
    ):
        value = safe_str(rec.get(key))
        if _is_sha256(value.lower()):
            return f"{key}:{value.lower()}"
    return ""


def _annotation_count_for_images(package: Dict[str, Any], image_ids: Set[int]) -> int:
    return sum(
        1
        for item in safe_list(package.get("annotations"))
        if _safe_int(safe_dict(item).get("image_id")) in image_ids
    )


def _safe_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_sha256(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", safe_str(value).lower()))


def _is_utc_timestamp(value: str) -> bool:
    text = safe_str(value)
    if not text:
        return False
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def frozen_test_image_membership_fingerprint(frozen_manifest: Dict[str, Any]) -> str:
    frozen = safe_dict(frozen_manifest)
    return _stable_hash(
        {
            "test_image_count": int(frozen.get("test_image_count") or 0),
            "test_image_ids_sha256": safe_str(frozen.get("test_image_ids_sha256")).lower(),
            "test_source_identities_sha256": safe_str(frozen.get("test_source_identities_sha256")).lower(),
            "test_source_identity_count": int(frozen.get("test_source_identity_count") or 0),
            "test_split_mutation_allowed": frozen.get("test_split_mutation_allowed") is False,
        }
    )


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "EVIDENCE_INTEGRITY_VERSION",
    "EVALUATION_RESERVATION_VERSION",
    "FROZEN_SPLIT_VERSION",
    "HELD_OUT_COMMITMENT_VERSION",
    "TEST_CONSUMPTION_LEDGER_VERSION",
    "TEST_CONSUMPTION_RECEIPT_VERSION",
    "append_test_consumption_receipt",
    "assess_coco_evidence_integrity",
    "build_evaluation_reservation_manifest",
    "build_frozen_split_manifest",
    "build_held_out_test_commitment",
    "build_split_scoped_coco_evidence_packages",
    "build_test_consumption_receipt",
    "coco_dataset_fingerprint",
    "declared_coco_evidence_fingerprint",
    "evidence_context_fingerprint",
    "evaluation_reservation_fingerprint",
    "evidence_integrity_fingerprint",
    "frozen_test_image_membership_fingerprint",
    "records_for_split",
    "reserve_test_consumption",
    "scope_coco_annotation_record",
    "scope_coco_category_record",
    "scope_coco_image_record",
    "scope_coco_license_records",
    "scope_registry_fingerprints",
    "scope_source_rights_record",
    "test_consumption_ledger_fingerprint",
    "test_consumption_receipt_fingerprint",
    "validate_evidence_integrity_report",
    "validate_evaluation_reservation_manifest",
    "validate_held_out_test_commitment",
    "validate_reservation_against_evidence",
    "validate_training_package_against_reservation",
    "validate_test_consumption_ledger",
    "validate_test_consumption_receipt",
]
