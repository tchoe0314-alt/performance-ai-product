from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .common import safe_dict, safe_float, safe_list, safe_str
from .vision_detection_learning import TRAINABLE_FEATURE_TYPES, sanitize_source_url


LEDGER_VERSION = "civora_vision_ground_truth_ledger_v1"
DATASET_VERSION = "civora_vision_ground_truth_dataset_v1"
ACTIVE_QUEUE_VERSION = "civora_vision_active_learning_queue_v1"
COVERAGE_VERSION = "civora_vision_ground_truth_coverage_v1"
WORKSPACE_VERSION = "civora_vision_review_workspace_v1"
SPLIT_REGISTRY_VERSION = "civora_vision_split_registry_v1"
CLASS_READINESS_VERSION = "civora_vision_class_readiness_v1"
PRIVACY_AGGREGATE_VERSION = "civora_vision_privacy_safe_correction_aggregate_v1"
LEARNING_CONSENT_VERSION = "civora_vision_learning_consent_v1"
EVENT_HASH_CANONICALIZATION = "json_browser_numeric_v1"

GROUND_TRUTH_ACTIONS = {
    "accept",
    "reject",
    "pending",
    "correct",
    "reclassify",
    "redraw",
    "merge",
    "split",
}

POSITIVE_ACTIONS = {"accept", "correct", "reclassify", "redraw", "merge", "split"}
DEFAULT_SPLIT_SEED = "civora-ground-truth-v1"
DEFAULT_CLASS_TARGET = 500
PRIVACY_SAFE_ACTIONS = frozenset(GROUND_TRUTH_ACTIONS)
PRIVACY_SAFE_CLASSES = frozenset(TRAINABLE_FEATURE_TYPES)
PRIVACY_SAFE_RIGHTS_BLOCKERS = frozenset(
    {
        "source_imagery_missing_license",
        "source_imagery_storage_rights_not_confirmed",
        "source_imagery_training_rights_not_confirmed",
        "source_label_missing_license",
        "source_label_training_rights_not_confirmed",
    }
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _browser_json_stable(value: Any) -> Any:
    """Normalize JSON numbers that JavaScript cannot round-trip distinctly."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer():
            return int(value)
        return value
    if isinstance(value, dict):
        return {str(key): _browser_json_stable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_browser_json_stable(item) for item in value]
    return value


def _integral_numbers_as_floats(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return float(value)
    if isinstance(value, float):
        return value
    if isinstance(value, dict):
        return {key: _integral_numbers_as_floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_integral_numbers_as_floats(item) for item in value]
    return value


def _legacy_browser_numeric_hash_matches(hash_payload: Dict[str, Any], claimed_hash: str) -> bool:
    """Accept only hash-preserving legacy JSON float normalization.

    Earlier events hashed validated coordinates such as ``20.0``. A browser
    autosave serializes that same JSON number as ``20``. The transforms below
    restore float representation only in fields that were float-valued when
    legacy vision events were created, then require the original SHA-256 to
    match exactly. Any semantic value change still fails closed.
    """

    if safe_str(hash_payload.get("hash_canonicalization")):
        return False

    def convert_output_geometry(payload: Dict[str, Any]) -> None:
        for output in safe_list(payload.get("outputs")):
            geometry = safe_dict(safe_dict(output).get("geometry"))
            if "coordinates" in geometry:
                geometry["coordinates"] = _integral_numbers_as_floats(geometry.get("coordinates"))

    def convert_source_geometry(payload: Dict[str, Any]) -> None:
        for snapshot in safe_list(payload.get("source_snapshots")):
            geometry = safe_dict(safe_dict(snapshot).get("geometry"))
            if "coordinates" in geometry:
                geometry["coordinates"] = _integral_numbers_as_floats(geometry.get("coordinates"))

    def convert_source_confidence(payload: Dict[str, Any]) -> None:
        for snapshot in safe_list(payload.get("source_snapshots")):
            rec = safe_dict(snapshot)
            if isinstance(rec.get("confidence"), int) and not isinstance(rec.get("confidence"), bool):
                rec["confidence"] = float(rec["confidence"])

    def convert_frame_coordinates(payload: Dict[str, Any]) -> None:
        for snapshot in safe_list(payload.get("source_snapshots")):
            frame = safe_dict(safe_dict(snapshot).get("frame"))
            for key in ("bbox_wgs84", "center_wgs84"):
                if safe_dict(frame.get(key)):
                    frame[key] = _integral_numbers_as_floats(frame[key])

    transforms = (
        convert_output_geometry,
        convert_source_geometry,
        convert_source_confidence,
        convert_frame_coordinates,
    )
    for mask in range(1, 1 << len(transforms)):
        candidate = deepcopy(hash_payload)
        for index, transform in enumerate(transforms):
            if mask & (1 << index):
                transform(candidate)
        if _sha256(candidate) == claimed_hash:
            return True
    return False


def _stable_id(prefix: str, *parts: Any) -> str:
    return f"{prefix}_{_sha256(parts)[:18]}"


def _source_record(candidate: Dict[str, Any]) -> Dict[str, Any]:
    return safe_dict(candidate.get("source_record")) or candidate


def _feature_type(candidate: Dict[str, Any]) -> str:
    source = _source_record(candidate)
    return safe_str(
        candidate.get("corrected_feature_type")
        or source.get("feature_type")
        or candidate.get("candidate_type")
    )


def _candidate_geometry(candidate: Dict[str, Any]) -> Dict[str, Any]:
    source = _source_record(candidate)
    return deepcopy(
        safe_dict(candidate.get("corrected_geometry"))
        or safe_dict(source.get("geometry"))
        or safe_dict(source.get("geo_geometry"))
    )


def _frame_catalog(meta: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    map_report = safe_dict(meta.get("map_feature_detection_report_v1"))
    imagery_report = safe_dict(map_report.get("imagery_object_detection_report_v1"))
    vision_report = safe_dict(
        map_report.get("civora_vision_detection_report_v2")
        or imagery_report.get("civora_vision_detection_report_v2")
        or meta.get("civora_vision_detection_report_v2")
    )
    frames: Dict[str, Dict[str, Any]] = {}
    for frame in [vision_report.get("imagery_frame"), *safe_list(vision_report.get("imagery_frames"))]:
        rec = safe_dict(frame)
        frame_id = safe_str(rec.get("frame_id"))
        if frame_id:
            frames[frame_id] = rec
    return frames


def _frame_id(candidate: Dict[str, Any]) -> str:
    source = _source_record(candidate)
    properties = safe_dict(source.get("properties"))
    return safe_str(
        properties.get("imagery_frame_id")
        or source.get("imagery_frame_id")
        or candidate.get("imagery_frame_id")
    )


def _frame_rights(candidate: Dict[str, Any], frames: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    source = _source_record(candidate)
    properties = safe_dict(source.get("properties"))
    frame = frames.get(_frame_id(candidate), {})
    return {
        **safe_dict(frame.get("source_rights")),
        **safe_dict(properties.get("source_rights")),
        **safe_dict(source.get("source_rights")),
    }


def _frame_context(candidate: Dict[str, Any], frames: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    source = _source_record(candidate)
    properties = safe_dict(source.get("properties"))
    frame = frames.get(_frame_id(candidate), {})
    bounds = safe_dict(frame.get("bbox_wgs84"))
    center = {}
    if bounds:
        center = {
            "longitude": round((safe_float(bounds.get("west")) + safe_float(bounds.get("east"))) / 2, 6),
            "latitude": round((safe_float(bounds.get("south")) + safe_float(bounds.get("north"))) / 2, 6),
        }
    return {
        "frame_id": _frame_id(candidate),
        "provider": safe_str(source.get("source_name") or candidate.get("provider") or frame.get("provider")),
        "source_url": sanitize_source_url(source.get("source_url") or candidate.get("source_url") or frame.get("source_url")),
        "source_fingerprint_sha256": safe_str(frame.get("source_fingerprint_sha256")),
        "captured_at": safe_str(frame.get("captured_at") or source.get("source_date") or candidate.get("source_date")),
        "geography_id": safe_str(
            properties.get("geography_id")
            or frame.get("geography_id")
            or properties.get("market")
            or properties.get("city")
        ),
        "season": safe_str(properties.get("season") or frame.get("season")),
        "imagery_quality_band": safe_str(
            properties.get("imagery_quality_band")
            or frame.get("imagery_quality_band")
            or properties.get("quality_band")
        ),
        "bbox_wgs84": bounds,
        "center_wgs84": center,
    }


def _candidate_snapshot(candidate: Dict[str, Any], frames: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    source = _source_record(candidate)
    rights = _frame_rights(candidate, frames)
    return {
        "candidate_id": safe_str(candidate.get("candidate_id")),
        "feature_type": _feature_type(candidate),
        "confidence": candidate.get("confidence"),
        "geometry": _candidate_geometry(candidate),
        "coordinate_space": safe_str(candidate.get("correction_coordinate_space"), "EPSG:4326"),
        "source_type": safe_str(source.get("source_type")),
        "source_feature_id": safe_str(source.get("source_feature_id")),
        "frame": _frame_context(candidate, frames),
        "source_rights": {
            "license": safe_str(rights.get("license")),
            "license_url": sanitize_source_url(rights.get("license_url")),
            "training_use_allowed": rights.get("training_use_allowed") is True,
            "storage_allowed": rights.get("storage_allowed") is True,
            "derivative_labels_allowed": (
                True
                if rights.get("derivative_labels_allowed") is True
                else False
                if rights.get("derivative_labels_allowed") is False
                else None
            ),
        },
    }


def _normalized_output(
    *,
    operation_id: str,
    index: int,
    feature_type: str,
    geometry: Dict[str, Any],
    coordinate_space: str,
) -> Dict[str, Any]:
    stable_geometry = _browser_json_stable(deepcopy(geometry))
    return {
        "annotation_id": _stable_id("gt", operation_id, index, feature_type, stable_geometry),
        "feature_type": feature_type,
        "geometry": stable_geometry,
        "coordinate_space": coordinate_space,
    }


def _build_outputs(
    candidates: Sequence[Dict[str, Any]],
    *,
    action: str,
    corrected_feature_type: str,
    corrected_geometry: Any,
    correction_coordinate_space: str,
    replacement_geometries: Sequence[Dict[str, Any]],
    replacement_feature_types: Sequence[str],
    operation_id: str,
) -> List[Dict[str, Any]]:
    if action not in POSITIVE_ACTIONS:
        return []
    default_type = corrected_feature_type or _feature_type(candidates[0])
    default_space = safe_str(correction_coordinate_space, "EPSG:4326")
    if action == "split":
        if len(candidates) != 1:
            raise ValueError("split requires exactly one candidate_id.")
        if len(replacement_geometries) < 2:
            raise ValueError("split requires at least two replacement_geometries.")
        return [
            _normalized_output(
                operation_id=operation_id,
                index=index,
                feature_type=(replacement_feature_types[index] if index < len(replacement_feature_types) else default_type),
                geometry=safe_dict(geometry),
                coordinate_space=default_space,
            )
            for index, geometry in enumerate(replacement_geometries)
        ]
    if action == "merge":
        if len(candidates) < 2:
            raise ValueError("merge requires at least two candidate_ids.")
        if corrected_geometry in (None, {}, []):
            raise ValueError("merge requires one reviewed corrected_geometry for the merged outline.")
        return [
            _normalized_output(
                operation_id=operation_id,
                index=0,
                feature_type=default_type,
                geometry=safe_dict(corrected_geometry),
                coordinate_space=default_space,
            )
        ]
    outputs: List[Dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        output_geometry = (
            safe_dict(corrected_geometry)
            if len(candidates) == 1 and corrected_geometry not in (None, {}, [])
            else _candidate_geometry(candidate)
        )
        if not output_geometry:
            continue
        outputs.append(
            _normalized_output(
                operation_id=operation_id,
                index=index,
                feature_type=corrected_feature_type or _feature_type(candidate),
                geometry=output_geometry,
                coordinate_space=(
                    default_space
                    if len(candidates) == 1 and corrected_geometry not in (None, {}, [])
                    else "EPSG:4326"
                ),
            )
        )
    return outputs


def verify_ground_truth_ledger(ledger: Dict[str, Any]) -> Dict[str, Any]:
    events = [safe_dict(item) for item in safe_list(ledger.get("events"))]
    blockers: List[str] = []
    compatibility_notes: List[str] = []
    previous_hash = "GENESIS"
    seen_event_ids: set[str] = set()
    expected_sequence = 1
    for event in events:
        event_id = safe_str(event.get("event_id"))
        if not event_id or event_id in seen_event_ids:
            blockers.append("duplicate_or_missing_event_id")
        seen_event_ids.add(event_id)
        if int(safe_float(event.get("sequence"))) != expected_sequence:
            blockers.append("event_sequence_gap")
        if safe_str(event.get("previous_event_hash")) != previous_hash:
            blockers.append("event_hash_chain_broken")
        claimed_hash = safe_str(event.get("event_hash"))
        hash_payload = {key: value for key, value in event.items() if key != "event_hash"}
        calculated_hash = _sha256(hash_payload)
        if claimed_hash != calculated_hash:
            if _legacy_browser_numeric_hash_matches(hash_payload, claimed_hash):
                compatibility_notes.append(f"legacy_browser_numeric_roundtrip:{event_id}")
            else:
                blockers.append("event_content_hash_mismatch")
        previous_hash = claimed_hash
        expected_sequence += 1
    if safe_str(ledger.get("head_hash"), "GENESIS") != previous_hash:
        blockers.append("ledger_head_hash_mismatch")
    return {
        "valid": not blockers,
        "event_count": len(events),
        "head_hash": previous_hash,
        "blockers": sorted(set(blockers)),
        "compatibility_notes": sorted(set(compatibility_notes)),
    }


def append_ground_truth_review_event(
    meta: Dict[str, Any],
    *,
    candidates: Sequence[Dict[str, Any]],
    action: str,
    reviewer_id: str,
    reason: str = "",
    corrected_feature_type: str = "",
    corrected_geometry: Any = None,
    correction_coordinate_space: str = "",
    replacement_geometries: Optional[Sequence[Dict[str, Any]]] = None,
    replacement_feature_types: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    normalized_action = safe_str(action).lower()
    if normalized_action not in GROUND_TRUTH_ACTIONS:
        raise ValueError(f"Unsupported ground-truth action: {normalized_action}")
    if not candidates:
        raise ValueError("At least one reviewed candidate is required.")
    ledger = deepcopy(safe_dict(meta.get(LEDGER_VERSION)))
    if not ledger:
        ledger = {
            "version": LEDGER_VERSION,
            "created_at": _now_iso(),
            "events": [],
            "head_hash": "GENESIS",
        }
    validation = verify_ground_truth_ledger(ledger)
    if not validation["valid"]:
        raise ValueError("Ground-truth ledger integrity check failed: " + ", ".join(validation["blockers"]))
    frames = _frame_catalog(meta)
    candidate_ids = sorted({safe_str(item.get("candidate_id")) for item in candidates if safe_str(item.get("candidate_id"))})
    sequence = len(safe_list(ledger.get("events"))) + 1
    reviewed_at = _now_iso()
    operation_id = _stable_id(
        "review_op",
        validation["head_hash"],
        sequence,
        normalized_action,
        candidate_ids,
        reviewer_id,
        reviewed_at,
    )
    outputs = _build_outputs(
        candidates,
        action=normalized_action,
        corrected_feature_type=safe_str(corrected_feature_type),
        corrected_geometry=corrected_geometry,
        correction_coordinate_space=safe_str(correction_coordinate_space),
        replacement_geometries=[safe_dict(item) for item in replacement_geometries or []],
        replacement_feature_types=[safe_str(item) for item in replacement_feature_types or []],
        operation_id=operation_id,
    )
    snapshots = [_candidate_snapshot(item, frames) for item in candidates]
    rights_records = [safe_dict(item.get("source_rights")) for item in snapshots]
    frame_ids = sorted({safe_str(safe_dict(item.get("frame")).get("frame_id")) for item in snapshots if safe_str(safe_dict(item.get("frame")).get("frame_id"))})
    blockers: List[str] = []
    if normalized_action == "pending":
        blockers.append("review_deferred")
    if not rights_records or not all(item.get("training_use_allowed") is True for item in rights_records):
        blockers.append("imagery_source_training_rights_not_confirmed")
    if not rights_records or not all(item.get("derivative_labels_allowed") is True for item in rights_records):
        blockers.append("imagery_derivative_label_rights_not_confirmed")
    if not rights_records or not all(bool(safe_str(item.get("license"))) for item in rights_records):
        blockers.append("imagery_source_license_missing")
    if not rights_records or not all(item.get("storage_allowed") is True for item in rights_records):
        blockers.append("imagery_storage_rights_not_confirmed")
    if not frame_ids:
        blockers.append("imagery_frame_missing")
    if len(frame_ids) > 1:
        blockers.append("cross_frame_review_operation_not_training_eligible")
    if normalized_action in POSITIVE_ACTIONS and not outputs:
        blockers.append("reviewed_geometry_missing")
    if any(safe_str(item.get("coordinate_space")) not in {"image_pixels", "EPSG:4326"} for item in outputs):
        blockers.append("reviewed_geometry_needs_imagery_registration")
    event_payload = _browser_json_stable({
        "version": "civora_vision_ground_truth_event_v1",
        "hash_canonicalization": EVENT_HASH_CANONICALIZATION,
        "event_id": _stable_id("gte", operation_id),
        "operation_id": operation_id,
        "sequence": sequence,
        "previous_event_hash": validation["head_hash"],
        "event_type": normalized_action,
        "candidate_ids": candidate_ids,
        "reviewed_by": safe_str(reviewer_id, "unknown_reviewer"),
        "reviewed_at": reviewed_at,
        "reason": safe_str(reason),
        "source_snapshots": snapshots,
        "outputs": outputs,
        "training_eligible": not blockers and normalized_action in POSITIVE_ACTIONS | {"reject"},
        "training_blockers": sorted(set(blockers)),
        "review_required": True,
        "visible_detection_influence": False,
    })
    event_payload["event_hash"] = _sha256(event_payload)
    ledger["events"] = [*safe_list(ledger.get("events")), event_payload]
    ledger["head_hash"] = event_payload["event_hash"]
    ledger["updated_at"] = reviewed_at
    ledger["integrity"] = verify_ground_truth_ledger(ledger)
    ledger["truth_label"] = (
        "This append-only ledger records reviewer decisions and geometry corrections for model development. "
        "It does not change visible detector output or create survey, compliance, or engineering evidence."
    )
    return ledger


def _split_for_frame(frame_id: str, *, seed: str = DEFAULT_SPLIT_SEED) -> str:
    bucket = int(hashlib.sha256(f"{seed}|{frame_id}".encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < 70:
        return "train"
    if bucket < 85:
        return "validation"
    return "test"


def ground_truth_dataset_fingerprint(dataset: Dict[str, Any]) -> str:
    if safe_str(dataset.get("package_scope")) == "multi_project_aggregate":
        payload = {
            "source_dataset_fingerprints": sorted(
                set(safe_str(item) for item in safe_list(dataset.get("source_dataset_fingerprints")) if safe_str(item))
            ),
            "assignments": safe_dict(safe_dict(dataset.get("split_registry")).get("assignments")),
            "examples": safe_list(dataset.get("examples")),
            "negative_frames": safe_list(dataset.get("negative_frames")),
        }
    else:
        payload = {
            "ledger_head_hash": safe_str(dataset.get("ledger_head_hash"), "GENESIS"),
            "split_registry": safe_dict(safe_dict(dataset.get("split_registry")).get("assignments")),
            "examples": safe_list(dataset.get("examples")),
            "negative_frames": safe_list(dataset.get("negative_frames")),
        }
    return _sha256(payload)


def verify_ground_truth_dataset(dataset: Dict[str, Any]) -> Dict[str, Any]:
    blockers: List[str] = []
    if safe_str(dataset.get("version")) != DATASET_VERSION:
        blockers.append("unsupported_dataset_version")
    registry = safe_dict(dataset.get("split_registry"))
    assignments = safe_dict(registry.get("assignments"))
    if registry.get("valid") is not True:
        blockers.append("split_registry_invalid")
    expected_fingerprint = ground_truth_dataset_fingerprint(dataset)
    if safe_str(dataset.get("dataset_fingerprint")) != expected_fingerprint:
        blockers.append("dataset_fingerprint_mismatch")
    for example in safe_list(dataset.get("examples")):
        rec = safe_dict(example)
        annotation_id = safe_str(rec.get("annotation_id"), "unknown")
        split = safe_str(rec.get("split"))
        assigned = safe_str(assignments.get(safe_str(rec.get("frame_id"))))
        if not assigned or assigned != split:
            blockers.append(f"example_split_mismatch:{annotation_id}")
        if split != "train" and rec.get("training_eligible") is True:
            blockers.append(f"non_train_example_marked_training_eligible:{annotation_id}")
        if split != "validation" and rec.get("validation_eligible") is True:
            blockers.append(f"non_validation_example_marked_validation_eligible:{annotation_id}")
        if split != "test" and rec.get("independent_test_eligible") is True:
            blockers.append(f"non_test_example_marked_test_eligible:{annotation_id}")
    return {
        "valid": not blockers,
        "dataset_fingerprint": expected_fingerprint,
        "blockers": sorted(set(blockers)),
    }


def build_split_registry(
    ledger: Dict[str, Any],
    *,
    existing_registry: Optional[Dict[str, Any]] = None,
    seed: str = DEFAULT_SPLIT_SEED,
) -> Dict[str, Any]:
    registry = deepcopy(safe_dict(existing_registry))
    assignments = dict(safe_dict(registry.get("assignments")))
    for event in safe_list(ledger.get("events")):
        for snapshot in safe_list(safe_dict(event).get("source_snapshots")):
            frame_id = safe_str(safe_dict(safe_dict(snapshot).get("frame")).get("frame_id"))
            if frame_id and frame_id not in assignments:
                assignments[frame_id] = _split_for_frame(frame_id, seed=seed)
    split_frames = {
        split: sorted(frame_id for frame_id, assigned in assignments.items() if assigned == split)
        for split in ("train", "validation", "test")
    }
    leakage = sorted(
        frame_id
        for frame_id in assignments
        if sum(frame_id in split_frames[split] for split in split_frames) != 1
    )
    return {
        "version": SPLIT_REGISTRY_VERSION,
        "seed": seed,
        "assignments": dict(sorted(assignments.items())),
        "splits": split_frames,
        "frame_count": len(assignments),
        "leakage_frame_ids": leakage,
        "valid": not leakage,
        "truth_label": "Imagery frames keep one permanent split assignment so nearby labels cannot leak across train, validation, and test.",
    }


def _active_events(ledger: Dict[str, Any]) -> List[Dict[str, Any]]:
    events = [safe_dict(item) for item in safe_list(ledger.get("events"))]
    latest_by_candidate: Dict[str, str] = {}
    for event in events:
        for candidate_id in safe_list(event.get("candidate_ids")):
            if safe_str(candidate_id):
                latest_by_candidate[safe_str(candidate_id)] = safe_str(event.get("event_id"))
    active = []
    for event in events:
        candidate_ids = [safe_str(item) for item in safe_list(event.get("candidate_ids")) if safe_str(item)]
        if candidate_ids and all(latest_by_candidate.get(item) == safe_str(event.get("event_id")) for item in candidate_ids):
            active.append(event)
    return active


def build_ground_truth_dataset(
    meta: Dict[str, Any],
    *,
    split_seed: str = DEFAULT_SPLIT_SEED,
) -> Dict[str, Any]:
    ledger = safe_dict(meta.get(LEDGER_VERSION))
    validation = verify_ground_truth_ledger(ledger)
    registry = build_split_registry(
        ledger,
        existing_registry=safe_dict(meta.get(SPLIT_REGISTRY_VERSION)),
        seed=split_seed,
    )
    examples: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = []
    negative_frames: List[Dict[str, Any]] = []
    if validation["valid"]:
        for event in _active_events(ledger):
            snapshots = [safe_dict(item) for item in safe_list(event.get("source_snapshots"))]
            frame_ids = sorted({safe_str(safe_dict(item.get("frame")).get("frame_id")) for item in snapshots if safe_str(safe_dict(item.get("frame")).get("frame_id"))})
            frame_id = frame_ids[0] if len(frame_ids) == 1 else ""
            split = safe_str(safe_dict(registry.get("assignments")).get(frame_id))
            blockers = list(safe_list(event.get("training_blockers")))
            if not split:
                blockers.append("permanent_split_assignment_missing")
            if safe_str(event.get("event_type")) == "reject" and not blockers:
                negative_frames.append(
                    {
                        "event_id": safe_str(event.get("event_id")),
                        "frame_id": frame_id,
                        "split": split,
                        "candidate_ids": list(safe_list(event.get("candidate_ids"))),
                    }
                )
            for output in safe_list(event.get("outputs")):
                rec = safe_dict(output)
                feature_type = safe_str(rec.get("feature_type"))
                output_blockers = list(blockers)
                if feature_type not in TRAINABLE_FEATURE_TYPES:
                    output_blockers.append("unsupported_training_feature_type")
                if not safe_dict(rec.get("geometry")):
                    output_blockers.append("reviewed_geometry_missing")
                if safe_str(rec.get("coordinate_space")) not in {"image_pixels", "EPSG:4326"}:
                    output_blockers.append("reviewed_geometry_needs_imagery_registration")
                example = {
                    "annotation_id": safe_str(rec.get("annotation_id")),
                    "event_id": safe_str(event.get("event_id")),
                    "operation_id": safe_str(event.get("operation_id")),
                    "candidate_ids": list(safe_list(event.get("candidate_ids"))),
                    "frame_id": frame_id,
                    "split": split,
                    "feature_type": feature_type,
                    "geometry": deepcopy(safe_dict(rec.get("geometry"))),
                    "coordinate_space": safe_str(rec.get("coordinate_space")),
                    "reviewed_by": safe_str(event.get("reviewed_by")),
                    "reviewed_at": safe_str(event.get("reviewed_at")),
                    "review_action": safe_str(event.get("event_type")),
                    "source_snapshots": deepcopy(snapshots),
                    "training_eligible": not output_blockers and split == "train",
                    "validation_eligible": not output_blockers and split == "validation",
                    "independent_test_eligible": not output_blockers and split == "test",
                    "blockers": sorted(set(output_blockers)),
                }
                examples.append(example)
                if output_blockers:
                    excluded.append(
                        {
                            "annotation_id": example["annotation_id"],
                            "event_id": example["event_id"],
                            "blockers": example["blockers"],
                        }
                    )
    counts_by_split = {
        split: sum(1 for item in examples if item.get("split") == split and not item.get("blockers"))
        for split in ("train", "validation", "test")
    }
    counts_by_class = {
        label: sum(1 for item in examples if item.get("feature_type") == label and not item.get("blockers"))
        for label in sorted({safe_str(item.get("feature_type")) for item in examples if safe_str(item.get("feature_type"))})
    }
    dataset_blockers = list(validation.get("blockers") or [])
    if not registry.get("valid"):
        dataset_blockers.append("train_validation_test_frame_leakage")
    for excluded_item in excluded:
        dataset_blockers.extend(safe_list(safe_dict(excluded_item).get("blockers")))
    if not examples and not negative_frames:
        dataset_blockers.append("reviewed_ground_truth_missing")
    payload = {
        "version": DATASET_VERSION,
        "generated_at": _now_iso(),
        "ledger_head_hash": safe_str(ledger.get("head_hash"), "GENESIS"),
        "ledger_integrity": validation,
        "split_registry": registry,
        "examples": examples,
        "negative_frames": negative_frames,
        "excluded_examples": excluded,
        "annotation_count": len(examples),
        "negative_frame_count": len(negative_frames),
        "eligible_annotation_count": sum(1 for item in examples if not item.get("blockers")),
        "counts_by_split": counts_by_split,
        "counts_by_class": counts_by_class,
        "contains_image_bytes": False,
        "export_ready": not dataset_blockers,
        "export_blockers": sorted(set(dataset_blockers)),
        "visible_detection_influence": False,
        "truth_label": (
            "This versioned manifest contains reviewed labels and source provenance without image bytes. Test frames are "
            "permanently isolated and cannot be used for training or model selection."
        ),
    }
    payload["dataset_fingerprint"] = ground_truth_dataset_fingerprint(payload)
    return payload


def build_ground_truth_coverage(
    dataset: Dict[str, Any],
    *,
    required_classes: Optional[Sequence[str]] = None,
    per_class_target: int = DEFAULT_CLASS_TARGET,
) -> Dict[str, Any]:
    required = list(required_classes or sorted(TRAINABLE_FEATURE_TYPES))
    examples = [safe_dict(item) for item in safe_list(dataset.get("examples")) if not safe_list(safe_dict(item).get("blockers"))]
    class_rows: Dict[str, Any] = {}
    all_geographies: set[str] = set()
    all_seasons: set[str] = set()
    all_quality_bands: set[str] = set()
    licenses: set[str] = set()
    for feature_type in required:
        class_examples = [item for item in examples if safe_str(item.get("feature_type")) == feature_type]
        geographies: set[str] = set()
        seasons: set[str] = set()
        quality_bands: set[str] = set()
        for example in class_examples:
            for snapshot in safe_list(example.get("source_snapshots")):
                rec = safe_dict(snapshot)
                frame = safe_dict(rec.get("frame"))
                rights = safe_dict(rec.get("source_rights"))
                if safe_str(frame.get("geography_id")):
                    geographies.add(safe_str(frame.get("geography_id")))
                if safe_str(frame.get("season")):
                    seasons.add(safe_str(frame.get("season")))
                if safe_str(frame.get("imagery_quality_band")):
                    quality_bands.add(safe_str(frame.get("imagery_quality_band")))
                if safe_str(rights.get("license")):
                    licenses.add(safe_str(rights.get("license")))
        all_geographies.update(geographies)
        all_seasons.update(seasons)
        all_quality_bands.update(quality_bands)
        blockers = []
        if len(class_examples) < per_class_target:
            blockers.append("reviewed_example_target_not_met")
        if len(geographies) < 5:
            blockers.append("geographic_coverage_target_not_met")
        if len(seasons) < 2:
            blockers.append("seasonal_coverage_target_not_met")
        if len(quality_bands) < 2:
            blockers.append("imagery_quality_coverage_target_not_met")
        class_rows[feature_type] = {
            "reviewed_annotation_count": len(class_examples),
            "target_annotation_count": per_class_target,
            "geography_count": len(geographies),
            "season_count": len(seasons),
            "imagery_quality_band_count": len(quality_bands),
            "target_ready": not blockers,
            "blockers": blockers,
        }
    source_dataset_count = max(0, int(safe_float(dataset.get("source_dataset_count"))))
    consent_validated_count = max(0, int(safe_float(dataset.get("learning_consent_validated_count"))))
    consent_required = dataset.get("learning_consent_required") is True
    consent_ready = (
        consent_required
        and source_dataset_count > 0
        and consent_validated_count == source_dataset_count
        and dataset.get("export_ready") is True
    )
    privacy_aggregate = build_privacy_safe_correction_aggregate([dataset])
    privacy_validation = validate_privacy_safe_correction_aggregate(privacy_aggregate)
    return {
        "version": COVERAGE_VERSION,
        "required_classes": required,
        "classes": class_rows,
        "target_ready_classes": sorted(label for label, row in class_rows.items() if row["target_ready"]),
        "blocked_classes": sorted(label for label, row in class_rows.items() if not row["target_ready"]),
        "geography_count": len(all_geographies),
        "season_count": len(all_seasons),
        "imagery_quality_band_count": len(all_quality_bands),
        "license_count": len(licenses),
        "source_dataset_count": source_dataset_count,
        "learning_consent_required": consent_required,
        "learning_consent_validated_count": consent_validated_count,
        "learning_consent_ready": consent_ready,
        "privacy_safe_aggregate": privacy_aggregate,
        "privacy_safe_aggregate_validation": privacy_validation,
        "model_promotion_implied": False,
        "truth_label": (
            "Coverage targets describe the evidence still needed for robust model development. Meeting a count target "
            "does not replace independent quality evaluation or human model approval."
        ),
    }


def validate_learning_consent(consent: Dict[str, Any], *, dataset_fingerprint: str) -> Dict[str, Any]:
    rec = safe_dict(consent)
    blockers: List[str] = []
    if safe_str(rec.get("version")) != LEARNING_CONSENT_VERSION:
        blockers.append("learning_consent_record_missing")
    if safe_str(rec.get("status")) != "granted":
        blockers.append("learning_consent_not_granted")
    scopes = {safe_str(item) for item in safe_list(rec.get("scopes")) if safe_str(item)}
    if "model_training" not in scopes:
        blockers.append("model_training_consent_scope_missing")
    if "cross_project_aggregation" not in scopes:
        blockers.append("cross_project_aggregation_consent_scope_missing")
    if safe_str(rec.get("dataset_fingerprint")) != safe_str(dataset_fingerprint):
        blockers.append("learning_consent_dataset_mismatch")
    if safe_str(rec.get("granted_by_role")) not in {"data_owner", "company_admin"}:
        blockers.append("learning_consent_authority_missing")
    if not safe_str(rec.get("granted_at")):
        blockers.append("learning_consent_timestamp_missing")
    if rec.get("revocable") is not True:
        blockers.append("learning_consent_not_revocable")
    if rec.get("private_identifiers_exported") is not False:
        blockers.append("learning_consent_private_identifier_boundary_missing")
    return {
        "valid": not blockers,
        "blockers": sorted(set(blockers)),
        "dataset_fingerprint": safe_str(dataset_fingerprint),
        "scopes": sorted(scopes),
    }


def merge_ground_truth_datasets(
    datasets: Iterable[Dict[str, Any]],
    *,
    learning_consents: Optional[Iterable[Dict[str, Any]]] = None,
    require_learning_consent: bool = True,
) -> Dict[str, Any]:
    inputs = [safe_dict(item) for item in datasets if safe_dict(item)]
    consents_by_fingerprint = {
        safe_str(safe_dict(item).get("dataset_fingerprint")): safe_dict(item)
        for item in learning_consents or []
        if safe_str(safe_dict(item).get("dataset_fingerprint"))
    }
    blockers: List[str] = []
    assignments: Dict[str, str] = {}
    examples_by_id: Dict[str, Dict[str, Any]] = {}
    negatives_by_key: Dict[str, Dict[str, Any]] = {}
    source_fingerprints: List[str] = []
    for index, dataset in enumerate(inputs):
        dataset_validation = verify_ground_truth_dataset(dataset)
        if not dataset_validation["valid"]:
            blockers.extend(
                f"source_dataset_{index}:{safe_str(item)}"
                for item in safe_list(dataset_validation.get("blockers"))
                if safe_str(item)
            )
        if safe_str(dataset.get("version")) != DATASET_VERSION:
            blockers.append(f"unsupported_dataset_version:{index}")
            continue
        if safe_dict(dataset.get("ledger_integrity")).get("valid") is not True:
            blockers.append(f"invalid_source_ledger:{index}")
        if dataset.get("export_ready") is not True:
            blockers.append(f"blocked_source_dataset:{index}")
            blockers.extend(
                f"source_dataset_{index}:{safe_str(item)}"
                for item in safe_list(dataset.get("export_blockers"))
                if safe_str(item)
            )
        source_fingerprint = safe_str(dataset.get("dataset_fingerprint"))
        if source_fingerprint:
            source_fingerprints.append(source_fingerprint)
        if require_learning_consent:
            consent_validation = validate_learning_consent(
                consents_by_fingerprint.get(source_fingerprint, {}),
                dataset_fingerprint=source_fingerprint,
            )
            blockers.extend(
                f"source_dataset_{index}:{item}" for item in consent_validation["blockers"]
            )
        registry = safe_dict(dataset.get("split_registry"))
        for frame_id, split in safe_dict(registry.get("assignments")).items():
            normalized_frame_id = safe_str(frame_id)
            normalized_split = safe_str(split)
            previous = assignments.get(normalized_frame_id)
            if previous and previous != normalized_split:
                blockers.append(f"conflicting_permanent_split:{normalized_frame_id}")
            elif normalized_frame_id and normalized_split in {"train", "validation", "test"}:
                assignments[normalized_frame_id] = normalized_split
        for example in safe_list(dataset.get("examples")):
            rec = deepcopy(safe_dict(example))
            annotation_id = safe_str(rec.get("annotation_id"))
            if not annotation_id:
                blockers.append(f"annotation_id_missing:{index}")
                continue
            previous = examples_by_id.get(annotation_id)
            if previous and _sha256(previous) != _sha256(rec):
                blockers.append(f"conflicting_annotation:{annotation_id}")
                continue
            examples_by_id[annotation_id] = rec
        for negative in safe_list(dataset.get("negative_frames")):
            rec = deepcopy(safe_dict(negative))
            key = safe_str(rec.get("event_id")) or _sha256(rec)
            negatives_by_key[key] = rec
    examples = sorted(examples_by_id.values(), key=lambda item: safe_str(item.get("annotation_id")))
    negatives = sorted(negatives_by_key.values(), key=lambda item: safe_str(item.get("event_id")))
    for example in examples:
        frame_id = safe_str(example.get("frame_id"))
        assigned = assignments.get(frame_id)
        if assigned and safe_str(example.get("split")) != assigned:
            blockers.append(f"example_split_mismatch:{safe_str(example.get('annotation_id'))}")
    counts_by_split = {
        split: sum(1 for item in examples if safe_str(item.get("split")) == split and not safe_list(item.get("blockers")))
        for split in ("train", "validation", "test")
    }
    counts_by_class = {
        label: sum(1 for item in examples if safe_str(item.get("feature_type")) == label and not safe_list(item.get("blockers")))
        for label in sorted({safe_str(item.get("feature_type")) for item in examples if safe_str(item.get("feature_type"))})
    }
    if not examples and not negatives:
        blockers.append("reviewed_ground_truth_missing")
    payload = {
        "version": DATASET_VERSION,
        "package_scope": "multi_project_aggregate",
        "generated_at": _now_iso(),
        "source_dataset_fingerprints": sorted(set(source_fingerprints)),
        "source_dataset_count": len(set(source_fingerprints)),
        "source_input_file_count": len(inputs),
        "examples": examples,
        "negative_frames": negatives,
        "annotation_count": len(examples),
        "negative_frame_count": len(negatives),
        "eligible_annotation_count": sum(1 for item in examples if not safe_list(item.get("blockers"))),
        "counts_by_split": counts_by_split,
        "counts_by_class": counts_by_class,
        "split_registry": {
            "version": SPLIT_REGISTRY_VERSION,
            "seed": DEFAULT_SPLIT_SEED,
            "assignments": dict(sorted(assignments.items())),
            "splits": {
                split: sorted(frame_id for frame_id, assigned in assignments.items() if assigned == split)
                for split in ("train", "validation", "test")
            },
            "valid": not any(item.startswith("conflicting_permanent_split:") for item in blockers),
        },
        "contains_image_bytes": False,
        "export_ready": not blockers,
        "export_blockers": sorted(set(blockers)),
        "promotion_eligible": False,
        "learning_consent_required": require_learning_consent,
        "learning_consent_validated_count": sum(
            1
            for fingerprint in set(source_fingerprints)
            if validate_learning_consent(
                consents_by_fingerprint.get(fingerprint, {}),
                dataset_fingerprint=fingerprint,
            )["valid"]
        ),
        "truth_label": (
            "This aggregate combines reviewed labels without image bytes and preserves permanent frame splits. It is "
            "training input only; independent evaluation and human model approval remain separate gates."
        ),
    }
    payload["dataset_fingerprint"] = ground_truth_dataset_fingerprint(payload)
    return payload


def build_privacy_safe_correction_aggregate(datasets: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    inputs = [safe_dict(item) for item in datasets if safe_dict(item)]
    counts_by_action: Dict[str, int] = {}
    counts_by_class: Dict[str, int] = {}
    counts_by_split: Dict[str, int] = {"train": 0, "validation": 0, "test": 0}
    rights_blocker_counts: Dict[str, int] = {}
    eligible_annotation_count = 0
    blocked_annotation_count = 0
    negative_frame_count = 0
    for dataset in inputs:
        negative_frame_count += max(0, int(safe_float(dataset.get("negative_frame_count"))))
        for item in safe_list(dataset.get("examples")):
            rec = safe_dict(item)
            raw_action = safe_str(rec.get("review_action"))
            raw_feature_type = safe_str(rec.get("feature_type"))
            action = raw_action if raw_action in PRIVACY_SAFE_ACTIONS else "unknown"
            feature_type = raw_feature_type if raw_feature_type in PRIVACY_SAFE_CLASSES else "unknown"
            split = safe_str(rec.get("split"))
            counts_by_action[action] = counts_by_action.get(action, 0) + 1
            counts_by_class[feature_type] = counts_by_class.get(feature_type, 0) + 1
            if split in counts_by_split:
                counts_by_split[split] += 1
            blockers = [safe_str(value) for value in safe_list(rec.get("blockers")) if safe_str(value)]
            if blockers:
                blocked_annotation_count += 1
            else:
                eligible_annotation_count += 1
            for blocker in blockers:
                if blocker in PRIVACY_SAFE_RIGHTS_BLOCKERS:
                    key = blocker
                elif "rights" in blocker or "license" in blocker:
                    key = "other_rights_or_license_blocker"
                else:
                    continue
                rights_blocker_counts[key] = rights_blocker_counts.get(key, 0) + 1
    payload = {
        "version": PRIVACY_AGGREGATE_VERSION,
        "generated_at": _now_iso(),
        "source_dataset_count": len(inputs),
        "annotation_count": eligible_annotation_count + blocked_annotation_count,
        "eligible_annotation_count": eligible_annotation_count,
        "blocked_annotation_count": blocked_annotation_count,
        "negative_frame_count": negative_frame_count,
        "counts_by_action": dict(sorted(counts_by_action.items())),
        "counts_by_class": dict(sorted(counts_by_class.items())),
        "counts_by_split": counts_by_split,
        "rights_blocker_counts": dict(sorted(rights_blocker_counts.items())),
        "contains_image_bytes": False,
        "contains_geometry": False,
        "contains_addresses": False,
        "contains_source_urls": False,
        "contains_project_or_reviewer_identifiers": False,
        "model_training_input": False,
        "visible_detection_influence": False,
        "truth_label": (
            "This aggregate contains correction counts only. It omits imagery, geometry, locations, source URLs, "
            "project IDs, candidate IDs, and reviewer identities, and cannot be used as model training input."
        ),
    }
    payload["aggregate_fingerprint"] = _sha256(
        {key: value for key, value in payload.items() if key not in {"generated_at", "truth_label"}}
    )
    return payload


def validate_privacy_safe_correction_aggregate(payload: Dict[str, Any]) -> Dict[str, Any]:
    rec = safe_dict(payload)
    blockers: List[str] = []
    if safe_str(rec.get("version")) != PRIVACY_AGGREGATE_VERSION:
        blockers.append("privacy_safe_correction_aggregate_missing")
    for field in (
        "contains_image_bytes",
        "contains_geometry",
        "contains_addresses",
        "contains_source_urls",
        "contains_project_or_reviewer_identifiers",
        "model_training_input",
        "visible_detection_influence",
    ):
        if rec.get(field) is not False:
            blockers.append(f"privacy_safe_correction_boundary_invalid:{field}")
    allowed_fields = {
        "version",
        "generated_at",
        "source_dataset_count",
        "annotation_count",
        "eligible_annotation_count",
        "blocked_annotation_count",
        "negative_frame_count",
        "counts_by_action",
        "counts_by_class",
        "counts_by_split",
        "rights_blocker_counts",
        "contains_image_bytes",
        "contains_geometry",
        "contains_addresses",
        "contains_source_urls",
        "contains_project_or_reviewer_identifiers",
        "model_training_input",
        "visible_detection_influence",
        "truth_label",
        "aggregate_fingerprint",
    }
    unexpected_fields = sorted(set(rec) - allowed_fields)
    blockers.extend(f"privacy_safe_correction_unexpected_field:{field}" for field in unexpected_fields)
    expected_fingerprint = _sha256(
        {key: value for key, value in rec.items() if key not in {"generated_at", "truth_label", "aggregate_fingerprint"}}
    )
    if safe_str(rec.get("aggregate_fingerprint")) != expected_fingerprint:
        blockers.append("privacy_safe_correction_aggregate_fingerprint_mismatch")
    return {
        "valid": not blockers,
        "blockers": sorted(set(blockers)),
        "aggregate_fingerprint": expected_fingerprint,
        "storage_scope": "aggregate_counts_only_no_private_identifiers",
    }


def _confidence_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return max(0.0, min(1.0, number))


def build_active_learning_queue(
    meta: Dict[str, Any],
    *,
    coverage: Optional[Dict[str, Any]] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    inbox = safe_dict(meta.get("candidate_review_inbox_v1"))
    shadow = safe_dict(meta.get("civora_vision_shadow_report_v1"))
    coverage_rows = safe_dict(safe_dict(coverage).get("classes"))
    shadow_classes = safe_dict(shadow.get("per_class"))
    items: List[Dict[str, Any]] = []
    for candidate in safe_list(inbox.get("candidates")):
        rec = safe_dict(candidate)
        if safe_str(rec.get("status"), "pending") in {"accepted", "rejected"}:
            continue
        source = _source_record(rec)
        if safe_str(source.get("source_type")) != "image_detected_candidate":
            continue
        feature_type = _feature_type(rec)
        confidence = _confidence_number(rec.get("confidence"))
        score = 40.0
        reasons = ["pending_human_review"]
        if confidence is None:
            score += 20
            reasons.append("confidence_missing")
        else:
            uncertainty = 1 - abs(confidence - 0.5) * 2
            score += max(0.0, uncertainty) * 30
            if 0.35 <= confidence <= 0.65:
                reasons.append("high_model_uncertainty")
        source_properties = safe_dict(source.get("properties"))
        if source.get("corroborates_candidate_id") or source_properties.get("corroborates_candidate_id"):
            score += 8
            reasons.append("cross_source_overlap")
        if source.get("classification_disagreement") or source_properties.get("classification_disagreement"):
            score += 20
            reasons.append("source_classification_disagreement")
        shadow_row = safe_dict(shadow_classes.get(feature_type))
        if shadow_row and safe_float(shadow_row.get("agreement_rate"), 1.0) < 0.5:
            score += 15
            reasons.append("baseline_shadow_disagreement")
        coverage_row = safe_dict(coverage_rows.get(feature_type))
        if coverage_row and coverage_row.get("target_ready") is not True:
            score += 10
            reasons.append("underrepresented_class")
        rights = safe_dict(source_properties.get("source_rights"))
        if rights.get("training_use_allowed") is True:
            score += 5
            reasons.append("rights_cleared_learning_value")
        items.append(
            {
                "candidate_id": safe_str(rec.get("candidate_id")),
                "feature_type": feature_type,
                "label": safe_str(rec.get("label"), feature_type.replace("_", " ")),
                "priority_score": round(score, 2),
                "confidence": confidence,
                "reason_codes": reasons,
                "recommended_action": "review_geometry_and_class",
            }
        )
    ordered = sorted(items, key=lambda item: (-safe_float(item.get("priority_score")), safe_str(item.get("candidate_id"))))
    return {
        "version": ACTIVE_QUEUE_VERSION,
        "generated_at": _now_iso(),
        "candidate_count": len(ordered),
        "items": ordered[: max(1, min(int(limit), 500))],
        "visible_detection_influence": False,
        "truth_label": "Priority scores only order human review work; they do not accept candidates or change visible geometry.",
    }


def build_class_model_readiness(meta: Dict[str, Any], coverage: Dict[str, Any]) -> Dict[str, Any]:
    promotion = safe_dict(
        meta.get("civora_vision_model_promotion_v1")
        or safe_dict(meta.get("civora_vision_model_manifest_v1")).get("promotion")
    )
    class_assessments = safe_dict(promotion.get("class_assessments"))
    coverage_rows = safe_dict(coverage.get("classes"))
    explicit_status = safe_str(promotion.get("status"), "candidate_blocked")
    human_approved = bool(safe_str(promotion.get("approved_by"))) and explicit_status == "approved_for_review_candidates"
    rows: Dict[str, Any] = {}
    for feature_type in sorted(TRAINABLE_FEATURE_TYPES):
        coverage_row = safe_dict(coverage_rows.get(feature_type))
        quality_row = safe_dict(class_assessments.get(feature_type))
        blockers = list(safe_list(coverage_row.get("blockers")))
        if not quality_row:
            blockers.append("independent_per_class_evaluation_missing")
        else:
            blockers.extend(safe_list(quality_row.get("blockers")))
            if quality_row.get("eligible") is not True:
                blockers.append("per_class_quality_gate_not_met")
        if not human_approved:
            blockers.append("explicit_human_model_approval_missing")
        eligible = not blockers and human_approved
        rows[feature_type] = {
            "status": "approved_for_review_candidates" if eligible else "candidate_blocked",
            "eligible_for_visible_review_candidates": eligible,
            "reviewed_annotation_count": int(safe_float(coverage_row.get("reviewed_annotation_count"))),
            "precision": quality_row.get("precision"),
            "recall": quality_row.get("recall"),
            "blockers": sorted(set(blockers)),
        }
    return {
        "version": CLASS_READINESS_VERSION,
        "model_status": explicit_status,
        "human_approval_present": human_approved,
        "classes": rows,
        "eligible_classes": sorted(label for label, row in rows.items() if row["eligible_for_visible_review_candidates"]),
        "blocked_classes": sorted(label for label, row in rows.items() if not row["eligible_for_visible_review_candidates"]),
        "visible_model_use_allowed": bool(rows) and all(row["eligible_for_visible_review_candidates"] for row in rows.values()),
        "truth_label": (
            "Each class must independently pass coverage, held-out quality, and named human approval before that class "
            "may create visible review candidates. Approval never makes imagery survey or engineering evidence."
        ),
    }


def build_vision_review_workspace(meta: Dict[str, Any]) -> Dict[str, Any]:
    dataset = build_ground_truth_dataset(meta)
    coverage = build_ground_truth_coverage(dataset)
    queue = build_active_learning_queue(meta, coverage=coverage)
    class_readiness = build_class_model_readiness(meta, coverage)
    ledger = safe_dict(meta.get(LEDGER_VERSION))
    integrity = verify_ground_truth_ledger(ledger)
    return {
        "version": WORKSPACE_VERSION,
        "generated_at": _now_iso(),
        "ledger_summary": {
            "event_count": integrity["event_count"],
            "head_hash": integrity["head_hash"],
            "integrity_valid": integrity["valid"],
            "integrity_blockers": integrity["blockers"],
        },
        "dataset_summary": {
            "fingerprint": safe_str(dataset.get("dataset_fingerprint")),
            "annotation_count": int(safe_float(dataset.get("annotation_count"))),
            "eligible_annotation_count": int(safe_float(dataset.get("eligible_annotation_count"))),
            "counts_by_split": safe_dict(dataset.get("counts_by_split")),
            "export_ready": dataset.get("export_ready") is True,
            "export_blockers": list(safe_list(dataset.get("export_blockers"))),
        },
        "active_learning_queue": queue,
        "coverage": coverage,
        "class_readiness": class_readiness,
        "review_actions": ["accept", "reject", "reclassify", "redraw", "merge", "split"],
        "geometry_edit_workflow": "Edit user-drawn polygon vertices in Draw, then attach the selected outline to a candidate.",
        "visible_detection_influence": False,
        "model_promotion_status": safe_str(class_readiness.get("model_status"), "candidate_blocked"),
        "truth_label": (
            "This workspace prepares reviewed training evidence. It cannot promote a model, alter visible detections, "
            "or turn imagery into survey, control, utility-locate, compliance, or engineering evidence."
        ),
    }


def attach_vision_ground_truth_flywheel(meta: Dict[str, Any]) -> Dict[str, Any]:
    updated = dict(safe_dict(meta))
    ledger = safe_dict(updated.get(LEDGER_VERSION))
    updated[SPLIT_REGISTRY_VERSION] = build_split_registry(
        ledger,
        existing_registry=safe_dict(updated.get(SPLIT_REGISTRY_VERSION)),
    )
    updated[DATASET_VERSION] = build_ground_truth_dataset(updated)
    updated[COVERAGE_VERSION] = build_ground_truth_coverage(updated[DATASET_VERSION])
    updated[ACTIVE_QUEUE_VERSION] = build_active_learning_queue(updated, coverage=updated[COVERAGE_VERSION])
    updated[WORKSPACE_VERSION] = build_vision_review_workspace(updated)
    return updated


__all__ = [
    "ACTIVE_QUEUE_VERSION",
    "CLASS_READINESS_VERSION",
    "COVERAGE_VERSION",
    "DATASET_VERSION",
    "LEDGER_VERSION",
    "LEARNING_CONSENT_VERSION",
    "PRIVACY_AGGREGATE_VERSION",
    "SPLIT_REGISTRY_VERSION",
    "WORKSPACE_VERSION",
    "append_ground_truth_review_event",
    "attach_vision_ground_truth_flywheel",
    "build_active_learning_queue",
    "build_class_model_readiness",
    "build_ground_truth_coverage",
    "build_ground_truth_dataset",
    "build_privacy_safe_correction_aggregate",
    "build_split_registry",
    "build_vision_review_workspace",
    "ground_truth_dataset_fingerprint",
    "merge_ground_truth_datasets",
    "validate_learning_consent",
    "validate_privacy_safe_correction_aggregate",
    "verify_ground_truth_dataset",
    "verify_ground_truth_ledger",
]
