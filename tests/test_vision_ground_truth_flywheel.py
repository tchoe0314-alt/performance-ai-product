from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import unittest

from backend.planning.candidate_review_inbox import apply_candidate_review_decision, build_candidate_review_inbox
from backend.planning.vision_detection_learning import build_imagery_frame_v2, build_vision_detection_report_v2
from backend.planning.vision_ground_truth_flywheel import (
    DATASET_VERSION,
    LEARNING_CONSENT_VERSION,
    LEDGER_VERSION,
    SPLIT_REGISTRY_VERSION,
    append_ground_truth_review_event,
    attach_vision_ground_truth_flywheel,
    build_active_learning_queue,
    build_class_model_readiness,
    build_ground_truth_coverage,
    build_ground_truth_dataset,
    build_split_registry,
    ground_truth_dataset_fingerprint,
    merge_ground_truth_datasets,
    verify_ground_truth_dataset,
    verify_ground_truth_ledger,
)


def _polygon(x0: float, y0: float, x1: float, y1: float):
    return {
        "type": "Polygon",
        "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
    }


def _legacy_event_hash(event):
    payload = {key: value for key, value in event.items() if key != "event_hash"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _geometry_coordinates_as_floats(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return float(value)
    if isinstance(value, list):
        return [_geometry_coordinates_as_floats(item) for item in value]
    return value


def _vision_meta(*, second_candidate: bool = False):
    frame = build_imagery_frame_v2(
        {
            "bbox": {"west": -96.0, "south": 40.0, "east": -95.99, "north": 40.01},
            "source_rights": {
                "license": "fixture-training-license",
                "training_use_allowed": True,
                "storage_allowed": True,
                "derivative_labels_allowed": True,
            },
        },
        source_url="https://imagery.example/frame.png?access_token=secret",
        provider="fixture-imagery",
        image_width=1000,
        image_height=1000,
    )
    frame["geography_id"] = "gretna-ne"
    frame["season"] = "summer"
    frame["imagery_quality_band"] = "high"
    detections = [
        {"detection_id": "det-1", "kind": "building", "bbox": [100, 100, 200, 200], "confidence": 0.51}
    ]
    if second_candidate:
        detections.append(
            {"detection_id": "det-2", "kind": "building", "bbox": [400, 100, 180, 180], "confidence": 0.94}
        )
    report = build_vision_detection_report_v2(
        detections=detections,
        imagery_frame=frame,
        provider="fixture-detector",
        detector_metadata={"model_name": "fixture", "model_version": "1"},
    )
    candidates = []
    for index, detection in enumerate(report["detections"], start=1):
        candidates.append(
            {
                "candidate_id": f"candidate-{index}",
                "feature_type": "building_footprint",
                "geometry": detection["geo_geometry"],
                "source_type": "image_detected_candidate",
                "source_name": "fixture-detector",
                "source_url": frame["source_url"],
                "source_feature_id": detection["detection_id"],
                "confidence": detection["confidence"],
                "review_required": True,
                "acceptance_status": "pending",
                "properties": {
                    "vision_detection_id": detection["detection_id"],
                    "imagery_frame_id": frame["frame_id"],
                    "source_rights": frame["source_rights"],
                },
            }
        )
    return {
        "map_feature_detection_report_v1": {
            "feature_candidates": candidates,
            "civora_vision_detection_report_v2": report,
            "imagery_object_detection_report_v1": {"civora_vision_detection_report_v2": report},
        }
    }


def _learning_consent(dataset):
    return {
        "version": LEARNING_CONSENT_VERSION,
        "status": "granted",
        "scopes": ["model_training", "cross_project_aggregation"],
        "dataset_fingerprint": dataset["dataset_fingerprint"],
        "granted_by_role": "data_owner",
        "granted_at": "2026-08-13T00:00:00Z",
        "revocable": True,
        "private_identifiers_exported": False,
    }


class VisionGroundTruthFlywheelTests(unittest.TestCase):
    def test_review_decision_appends_hash_chained_event_and_dataset(self) -> None:
        meta = _vision_meta()
        meta["candidate_review_inbox_v1"] = build_candidate_review_inbox(meta)

        result = apply_candidate_review_decision(
            meta,
            candidate_ids=["candidate-1"],
            action="accept",
            reviewer_id="reviewer-1",
            reason="Outline matches the visible roof.",
        )

        ledger = result[LEDGER_VERSION]
        dataset = result[DATASET_VERSION]
        self.assertTrue(verify_ground_truth_ledger(ledger)["valid"])
        self.assertEqual(len(ledger["events"]), 1)
        self.assertEqual(ledger["events"][0]["event_type"], "accept")
        self.assertEqual(dataset["annotation_count"], 1)
        self.assertEqual(dataset["eligible_annotation_count"], 1)
        self.assertFalse(dataset["contains_image_bytes"])
        self.assertTrue(result["civora_vision_review_workspace_v1"]["ledger_summary"]["integrity_valid"])

    def test_ledger_detects_content_tampering_and_refuses_append(self) -> None:
        meta = _vision_meta()
        inbox = build_candidate_review_inbox(meta)
        candidate = inbox["candidates"][0]
        ledger = append_ground_truth_review_event(
            {**meta, "candidate_review_inbox_v1": inbox},
            candidates=[candidate],
            action="accept",
            reviewer_id="reviewer-1",
        )
        tampered = deepcopy(ledger)
        tampered["events"][0]["reason"] = "Changed after review"

        self.assertFalse(verify_ground_truth_ledger(tampered)["valid"])
        with self.assertRaisesRegex(ValueError, "integrity check failed"):
            append_ground_truth_review_event(
                {**meta, LEDGER_VERSION: tampered},
                candidates=[candidate],
                action="reject",
                reviewer_id="reviewer-2",
            )

    def test_new_event_hash_survives_browser_numeric_roundtrip(self) -> None:
        meta = _vision_meta()
        meta["candidate_review_inbox_v1"] = build_candidate_review_inbox(meta)
        result = apply_candidate_review_decision(
            meta,
            candidate_ids=["candidate-1"],
            action="redraw",
            reviewer_id="reviewer-1",
            corrected_feature_type="building_footprint",
            corrected_geometry=_polygon(20.0, 20.0, 80.0, 80.0),
            correction_coordinate_space="project_local",
        )

        ledger = result[LEDGER_VERSION]
        event = ledger["events"][0]
        self.assertEqual(event["hash_canonicalization"], "json_browser_numeric_v1")
        self.assertIsInstance(event["outputs"][0]["geometry"]["coordinates"][0][0][0], int)
        browser_roundtrip = json.loads(json.dumps(ledger))
        validation = verify_ground_truth_ledger(browser_roundtrip)
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["compatibility_notes"], [])

    def test_legacy_browser_float_normalization_is_compatible_but_tampering_is_not(self) -> None:
        meta = _vision_meta(second_candidate=True)
        inbox = build_candidate_review_inbox(meta)
        first = apply_candidate_review_decision(
            {**meta, "candidate_review_inbox_v1": inbox},
            candidate_ids=["candidate-1"],
            action="redraw",
            reviewer_id="reviewer-1",
            corrected_feature_type="building_footprint",
            corrected_geometry=_polygon(20.0, 20.0, 80.0, 80.0),
            correction_coordinate_space="project_local",
        )
        legacy_event = deepcopy(first[LEDGER_VERSION]["events"][0])
        legacy_event.pop("event_hash")
        legacy_event.pop("hash_canonicalization")
        coordinates = legacy_event["outputs"][0]["geometry"]["coordinates"]
        legacy_event["outputs"][0]["geometry"]["coordinates"] = _geometry_coordinates_as_floats(coordinates)
        original_hash = _legacy_event_hash(legacy_event)
        browser_event = json.loads(json.dumps(legacy_event))
        browser_event["outputs"][0]["geometry"]["coordinates"] = coordinates
        browser_event["event_hash"] = original_hash
        legacy_ledger = {
            "version": LEDGER_VERSION,
            "events": [browser_event],
            "head_hash": original_hash,
        }

        validation = verify_ground_truth_ledger(legacy_ledger)
        self.assertTrue(validation["valid"])
        self.assertEqual(
            validation["compatibility_notes"],
            [f"legacy_browser_numeric_roundtrip:{browser_event['event_id']}"],
        )

        second_candidate = next(
            candidate for candidate in inbox["candidates"] if candidate["candidate_id"] == "candidate-2"
        )
        appended = append_ground_truth_review_event(
            {**meta, LEDGER_VERSION: legacy_ledger},
            candidates=[second_candidate],
            action="reject",
            reviewer_id="reviewer-2",
        )
        self.assertEqual(len(appended["events"]), 2)
        self.assertTrue(verify_ground_truth_ledger(appended)["valid"])

        tampered = deepcopy(legacy_ledger)
        tampered["events"][0]["outputs"][0]["geometry"]["coordinates"][0][0][0] = 21
        self.assertFalse(verify_ground_truth_ledger(tampered)["valid"])

    def test_dataset_fails_closed_without_explicit_imagery_rights(self) -> None:
        meta = _vision_meta()
        report = meta["map_feature_detection_report_v1"]["civora_vision_detection_report_v2"]
        report["imagery_frame"]["source_rights"] = {
            "training_use_allowed": True,
            "storage_allowed": False,
        }
        candidate = meta["map_feature_detection_report_v1"]["feature_candidates"][0]
        candidate["properties"]["source_rights"] = {
            "training_use_allowed": True,
            "storage_allowed": False,
        }
        meta["candidate_review_inbox_v1"] = build_candidate_review_inbox(meta)

        result = apply_candidate_review_decision(
            meta,
            candidate_ids=["candidate-1"],
            action="accept",
            reviewer_id="reviewer-1",
        )

        event = result[LEDGER_VERSION]["events"][0]
        self.assertFalse(event["training_eligible"])
        self.assertIn("imagery_derivative_label_rights_not_confirmed", event["training_blockers"])
        self.assertIn("imagery_source_license_missing", event["training_blockers"])
        self.assertIn("imagery_storage_rights_not_confirmed", event["training_blockers"])
        self.assertFalse(result[DATASET_VERSION]["export_ready"])

    def test_split_creates_two_annotations_and_preserves_one_frame_split(self) -> None:
        meta = _vision_meta()
        meta["candidate_review_inbox_v1"] = build_candidate_review_inbox(meta)
        result = apply_candidate_review_decision(
            meta,
            candidate_ids=["candidate-1"],
            action="split",
            reviewer_id="reviewer-1",
            corrected_feature_type="building_footprint",
            replacement_geometries=[
                _polygon(-95.999, 40.005, -95.997, 40.007),
                _polygon(-95.996, 40.005, -95.994, 40.007),
            ],
            correction_coordinate_space="EPSG:4326",
        )

        dataset = result[DATASET_VERSION]
        self.assertEqual(dataset["annotation_count"], 2)
        self.assertEqual(len(result["accepted_drafts"]), 2)
        self.assertEqual({item["split"] for item in dataset["examples"]}.__len__(), 1)
        self.assertFalse(dataset["split_registry"]["leakage_frame_ids"])
        self.assertEqual(result[LEDGER_VERSION]["events"][0]["event_type"], "split")

    def test_merge_requires_reviewed_outline_and_creates_one_annotation(self) -> None:
        meta = _vision_meta(second_candidate=True)
        meta["candidate_review_inbox_v1"] = build_candidate_review_inbox(meta)
        with self.assertRaisesRegex(ValueError, "corrected_geometry"):
            apply_candidate_review_decision(
                meta,
                candidate_ids=["candidate-1", "candidate-2"],
                action="merge",
                reviewer_id="reviewer-1",
            )

        result = apply_candidate_review_decision(
            meta,
            candidate_ids=["candidate-1", "candidate-2"],
            action="merge",
            reviewer_id="reviewer-1",
            corrected_feature_type="building_footprint",
            corrected_geometry=_polygon(-95.999, 40.004, -95.992, 40.008),
            correction_coordinate_space="EPSG:4326",
        )

        self.assertEqual(result[DATASET_VERSION]["annotation_count"], 1)
        self.assertEqual(len(result["accepted_drafts"]), 1)
        self.assertEqual(result["accepted_drafts"][0]["vision_correction_action"], "merge")
        self.assertEqual(result[LEDGER_VERSION]["events"][0]["candidate_ids"], ["candidate-1", "candidate-2"])

    def test_split_registry_is_permanent_when_new_events_arrive(self) -> None:
        meta = _vision_meta(second_candidate=True)
        meta["candidate_review_inbox_v1"] = build_candidate_review_inbox(meta)
        accepted = apply_candidate_review_decision(
            meta,
            candidate_ids=["candidate-1"],
            action="accept",
            reviewer_id="reviewer-1",
        )
        first_registry = accepted[SPLIT_REGISTRY_VERSION]
        second = apply_candidate_review_decision(
            accepted["updated_meta"],
            candidate_ids=["candidate-2"],
            action="reject",
            reviewer_id="reviewer-2",
        )

        self.assertEqual(first_registry["assignments"], second[SPLIT_REGISTRY_VERSION]["assignments"])
        self.assertTrue(second[SPLIT_REGISTRY_VERSION]["valid"])

    def test_rejected_detection_becomes_a_split_isolated_negative_frame(self) -> None:
        meta = _vision_meta()
        meta["candidate_review_inbox_v1"] = build_candidate_review_inbox(meta)
        result = apply_candidate_review_decision(
            meta,
            candidate_ids=["candidate-1"],
            action="reject",
            reviewer_id="reviewer-1",
            reason="No visible building is present in this frame region.",
        )

        dataset = result[DATASET_VERSION]
        self.assertEqual(dataset["annotation_count"], 0)
        self.assertEqual(dataset["negative_frame_count"], 1)
        self.assertIn(dataset["negative_frames"][0]["split"], {"train", "validation", "test"})
        self.assertTrue(dataset["export_ready"])

    def test_active_learning_prioritizes_uncertainty_and_reports_coverage_gaps(self) -> None:
        meta = _vision_meta(second_candidate=True)
        meta["candidate_review_inbox_v1"] = build_candidate_review_inbox(meta)
        enriched = attach_vision_ground_truth_flywheel(meta)
        coverage = build_ground_truth_coverage(enriched[DATASET_VERSION])
        queue = build_active_learning_queue(enriched, coverage=coverage)

        self.assertEqual(queue["candidate_count"], 2)
        self.assertEqual(queue["items"][0]["candidate_id"], "candidate-1")
        self.assertIn("high_model_uncertainty", queue["items"][0]["reason_codes"])
        self.assertIn("building_footprint", coverage["blocked_classes"])
        self.assertFalse(coverage["model_promotion_implied"])
        readiness = build_class_model_readiness(enriched, coverage)
        self.assertFalse(readiness["visible_model_use_allowed"])
        self.assertIn("explicit_human_model_approval_missing", readiness["classes"]["building_footprint"]["blockers"])

    def test_dataset_fails_closed_when_ledger_is_tampered(self) -> None:
        meta = _vision_meta()
        meta["candidate_review_inbox_v1"] = build_candidate_review_inbox(meta)
        result = apply_candidate_review_decision(
            meta,
            candidate_ids=["candidate-1"],
            action="accept",
            reviewer_id="reviewer-1",
        )
        tampered_meta = deepcopy(result["updated_meta"])
        tampered_meta[LEDGER_VERSION]["events"][0]["reviewed_by"] = "attacker"

        dataset = build_ground_truth_dataset(tampered_meta)
        self.assertFalse(dataset["export_ready"])
        self.assertEqual(dataset["annotation_count"], 0)
        self.assertIn("event_content_hash_mismatch", dataset["export_blockers"])

    def test_exported_dataset_detects_geometry_tampering(self) -> None:
        meta = _vision_meta()
        meta["candidate_review_inbox_v1"] = build_candidate_review_inbox(meta)
        result = apply_candidate_review_decision(
            meta,
            candidate_ids=["candidate-1"],
            action="accept",
            reviewer_id="reviewer-1",
        )
        dataset = deepcopy(result[DATASET_VERSION])
        self.assertEqual(dataset["dataset_fingerprint"], ground_truth_dataset_fingerprint(dataset))
        dataset["examples"][0]["geometry"] = _polygon(-95.5, 40.5, -95.4, 40.6)

        validation = verify_ground_truth_dataset(dataset)
        self.assertFalse(validation["valid"])
        self.assertIn("dataset_fingerprint_mismatch", validation["blockers"])

    def test_multi_project_merge_deduplicates_labels_and_rejects_split_conflicts(self) -> None:
        meta = _vision_meta()
        meta["candidate_review_inbox_v1"] = build_candidate_review_inbox(meta)
        result = apply_candidate_review_decision(
            meta,
            candidate_ids=["candidate-1"],
            action="accept",
            reviewer_id="reviewer-1",
        )
        dataset = result[DATASET_VERSION]
        consent = _learning_consent(dataset)
        merged = merge_ground_truth_datasets(
            [dataset, deepcopy(dataset)],
            learning_consents=[consent],
        )
        self.assertEqual(merged["annotation_count"], 1)
        self.assertTrue(merged["export_ready"])
        self.assertFalse(merged["promotion_eligible"])

        conflicting = deepcopy(dataset)
        frame_id = next(iter(conflicting["split_registry"]["assignments"]))
        current = conflicting["split_registry"]["assignments"][frame_id]
        conflicting["split_registry"]["assignments"][frame_id] = "test" if current != "test" else "train"
        blocked = merge_ground_truth_datasets(
            [dataset, conflicting],
            learning_consents=[consent, _learning_consent(conflicting)],
        )
        self.assertFalse(blocked["export_ready"])
        self.assertTrue(any(item.startswith("conflicting_permanent_split:") for item in blocked["export_blockers"]))


if __name__ == "__main__":
    unittest.main()
