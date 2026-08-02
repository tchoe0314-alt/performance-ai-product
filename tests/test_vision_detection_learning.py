from __future__ import annotations

import unittest

from backend.planning.candidate_review_inbox import apply_candidate_review_decision, build_candidate_review_inbox
from backend.planning.vision_detection_learning import (
    build_imagery_frame_v2,
    build_vision_detection_report_v2,
    build_vision_quality_report,
    build_vision_training_dataset,
    evaluate_detection_quality,
    georeference_pixel_geometry,
    resolve_detection_source_conflicts,
    sanitize_source_url,
)


def _polygon(x0: float, y0: float, x1: float, y1: float):
    return {
        "type": "Polygon",
        "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
    }


def _vision_meta(*, training_allowed: bool = True):
    frame = build_imagery_frame_v2(
        {
            "bbox": {"west": -96.0, "south": 40.0, "east": -95.0, "north": 41.0},
            "source_rights": {
                "license": "fixture-license",
                "training_use_allowed": training_allowed,
                "storage_allowed": training_allowed,
            },
        },
        source_url="https://imagery.example/tile.png?access_token=secret-value",
        provider="civora_fixture",
        image_width=100,
        image_height=100,
    )
    report = build_vision_detection_report_v2(
        detections=[
            {
                "detection_id": "det-building-1",
                "kind": "building",
                "bbox": [10, 10, 20, 20],
                "confidence": 0.82,
            }
        ],
        imagery_frame=frame,
        provider="civora_fixture",
        detector_metadata={"model_name": "fixture", "model_version": "1"},
    )
    detection = report["detections"][0]
    candidate = {
        "candidate_id": "candidate-building-1",
        "feature_type": "building_footprint",
        "geometry": detection["geo_geometry"],
        "source_type": "image_detected_candidate",
        "source_url": frame["source_url"],
        "source_name": "civora_fixture",
        "source_feature_id": "det-building-1",
        "confidence": 0.82,
        "review_required": True,
        "acceptance_status": "pending",
        "properties": {
            "vision_detection_id": "det-building-1",
            "imagery_frame_id": frame["frame_id"],
        },
    }
    return {
        "map_feature_detection_report_v1": {
            "version": "map_feature_detection_report_v1",
            "feature_candidates": [candidate],
            "civora_vision_detection_report_v2": report,
            "imagery_object_detection_report_v1": {
                "version": "imagery_object_detection_report_v1",
                "civora_vision_detection_report_v2": report,
            },
        }
    }


class VisionDetectionLearningTests(unittest.TestCase):
    def test_source_url_redaction_removes_tokens(self) -> None:
        sanitized = sanitize_source_url(
            "https://api.mapbox.com/tile.png?access_token=secret&style=satellite&api_key=also-secret"
        )

        self.assertEqual(sanitized, "https://api.mapbox.com/tile.png?style=satellite")
        self.assertNotIn("secret", sanitized)

    def test_frame_georeferences_pixel_geometry(self) -> None:
        frame = build_imagery_frame_v2(
            {"bbox": {"west": -96, "south": 40, "east": -95, "north": 41}},
            source_url="https://imagery.example/image.png",
            provider="fixture",
            image_width=100,
            image_height=100,
        )
        result = georeference_pixel_geometry(
            {"type": "Point", "coordinates": [50, 25]},
            frame,
        )

        self.assertTrue(frame["georeference_ready"])
        self.assertEqual(result, {"type": "Point", "coordinates": [-95.5, 40.75]})

    def test_detection_report_preserves_pixel_and_geographic_geometry(self) -> None:
        meta = _vision_meta()
        report = meta["map_feature_detection_report_v1"]["civora_vision_detection_report_v2"]
        detection = report["detections"][0]

        self.assertEqual(report["georeferenced_detection_count"], 1)
        self.assertEqual(detection["geometry_space"], "EPSG:4326")
        self.assertEqual(detection["pixel_geometry"]["type"], "Polygon")
        self.assertEqual(detection["geo_geometry"]["type"], "Polygon")
        self.assertTrue(report["training_ready"])

    def test_official_geometry_remains_primary_over_overlapping_imagery(self) -> None:
        result = resolve_detection_source_conflicts(
            [
                {
                    "candidate_id": "official-building",
                    "feature_type": "building_footprint",
                    "source_type": "official_gis",
                    "geometry": _polygon(0, 0, 10, 10),
                },
                {
                    "candidate_id": "vision-building",
                    "feature_type": "building_footprint",
                    "source_type": "image_detected_candidate",
                    "geometry": _polygon(0.5, 0.5, 9.5, 9.5),
                },
            ]
        )
        by_id = {item["candidate_id"]: item for item in result["candidates"]}

        self.assertEqual(result["corroborating_candidate_count"], 1)
        self.assertFalse(by_id["vision-building"]["render_as_primary"])
        self.assertEqual(by_id["vision-building"]["corroborates_candidate_id"], "official-building")

    def test_corrected_candidate_becomes_rights_cleared_training_example(self) -> None:
        meta = _vision_meta(training_allowed=True)
        inbox = build_candidate_review_inbox(meta)
        meta["candidate_review_inbox_v1"] = inbox
        decision = apply_candidate_review_decision(
            meta,
            candidate_ids=["candidate-building-1"],
            action="correct",
            reviewer_id="reviewer-1",
            reason="Roof is a parking canopy, not a building.",
            corrected_feature_type="parking_area",
            corrected_geometry=_polygon(-95.9, 40.7, -95.8, 40.8),
            correction_coordinate_space="EPSG:4326",
        )
        dataset = build_vision_training_dataset(decision["updated_meta"])
        example = dataset["examples"][0]

        self.assertEqual(example["review_action"], "correct")
        self.assertEqual(example["corrected_feature_type"], "parking_area")
        self.assertTrue(example["training_eligible"])
        self.assertEqual(dataset["counts"]["corrected"], 1)
        self.assertEqual(decision["accepted_drafts"][0]["object_type"], "parking")

    def test_training_export_stays_blocked_without_source_rights(self) -> None:
        meta = _vision_meta(training_allowed=False)
        inbox = build_candidate_review_inbox(meta)
        meta["candidate_review_inbox_v1"] = inbox
        decision = apply_candidate_review_decision(
            meta,
            candidate_ids=["candidate-building-1"],
            action="accept",
            reviewer_id="reviewer-1",
        )
        dataset = build_vision_training_dataset(decision["updated_meta"])

        self.assertEqual(dataset["training_eligible_example_count"], 0)
        self.assertIn("imagery_source_training_rights_not_confirmed", dataset["examples"][0]["training_blockers"])
        self.assertFalse(dataset["contains_image_bytes"])

    def test_quality_metrics_are_withheld_without_ground_truth(self) -> None:
        dataset = build_vision_training_dataset(_vision_meta())
        quality = build_vision_quality_report(dataset)

        self.assertEqual(quality["evaluation_status"], "ground_truth_not_attached")
        self.assertIsNone(quality["precision"])
        self.assertFalse(quality["quality_claim_allowed"])

    def test_quality_evaluation_measures_false_positive_and_false_negative(self) -> None:
        quality = evaluate_detection_quality(
            [
                {"feature_type": "building_footprint", "geometry": _polygon(0, 0, 10, 10), "confidence": 0.9},
                {"feature_type": "parking_area", "geometry": _polygon(20, 20, 30, 30), "confidence": 0.8},
            ],
            [
                {"feature_type": "building_footprint", "geometry": _polygon(0, 0, 10, 10)},
                {"feature_type": "road_or_drive", "geometry": _polygon(40, 40, 50, 50)},
            ],
        )

        self.assertEqual(quality["true_positive"], 1)
        self.assertEqual(quality["false_positive"], 1)
        self.assertEqual(quality["false_negative"], 1)
        self.assertEqual(quality["precision"], 0.5)
        self.assertEqual(quality["recall"], 0.5)
        self.assertEqual(quality["geometry_metric"], "class_aware_bounding_box_iou")

    def test_project_local_redraw_is_saved_but_not_training_eligible_until_registered(self) -> None:
        meta = _vision_meta(training_allowed=True)
        meta["candidate_review_inbox_v1"] = build_candidate_review_inbox(meta)
        decision = apply_candidate_review_decision(
            meta,
            candidate_ids=["candidate-building-1"],
            action="redraw",
            reviewer_id="reviewer-1",
            corrected_geometry=_polygon(10, 10, 40, 30),
            correction_coordinate_space="project_local",
        )
        dataset = build_vision_training_dataset(decision["updated_meta"])
        example = dataset["examples"][0]

        self.assertEqual(example["review_action"], "redraw")
        self.assertEqual(example["correction_coordinate_space"], "project_local")
        self.assertFalse(example["training_eligible"])
        self.assertIn("corrected_geometry_needs_imagery_registration", example["training_blockers"])

    def test_invalid_or_mismatched_correction_geometry_is_rejected(self) -> None:
        meta = _vision_meta(training_allowed=True)
        meta["candidate_review_inbox_v1"] = build_candidate_review_inbox(meta)

        with self.assertRaisesRegex(ValueError, "require Polygon"):
            apply_candidate_review_decision(
                meta,
                candidate_ids=["candidate-building-1"],
                action="redraw",
                reviewer_id="reviewer-1",
                corrected_geometry={"type": "LineString", "coordinates": [[1, 1], [2, 2]]},
                correction_coordinate_space="image_pixels",
            )

        with self.assertRaisesRegex(ValueError, "valid longitude/latitude"):
            apply_candidate_review_decision(
                meta,
                candidate_ids=["candidate-building-1"],
                action="redraw",
                reviewer_id="reviewer-1",
                corrected_geometry=_polygon(200, 10, 210, 20),
                correction_coordinate_space="EPSG:4326",
            )


if __name__ == "__main__":
    unittest.main()
