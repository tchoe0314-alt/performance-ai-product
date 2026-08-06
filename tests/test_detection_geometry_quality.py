import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from backend.planning.candidate_review_inbox import apply_candidate_review_decision, build_candidate_review_inbox
from backend.planning.map_feature_detection import build_map_feature_detection_report
from vision.detection_geometry import normalize_detection_candidates
from vision.feature_detection_engine import FeatureDetectionEngine


class DetectionGeometryQualityTests(unittest.TestCase):
    def test_local_detector_drops_border_shadow_and_keeps_separate_roof(self) -> None:
        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "aerial.png"
            image = Image.new("RGB", (512, 512), (118, 154, 96))
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 20, 300, 350), fill=(48, 48, 48))
            draw.rectangle((360, 80, 455, 150), fill=(54, 54, 54))
            image.save(image_path)

            result = FeatureDetectionEngine(max_size=512).detect(str(image_path))

        buildings = [item for item in result.detections if item.kind == "building"]
        self.assertEqual(len(buildings), 1)
        self.assertGreater(buildings[0].bbox[0], 300)
        self.assertFalse(buildings[0].properties["component_shape_v1"]["touches_frame"])

    def test_heuristic_rejects_oversized_building_instead_of_creating_false_footprint(self) -> None:
        accepted, report = normalize_detection_candidates(
            [
                {
                    "detection_id": "bad-building",
                    "kind": "building",
                    "confidence": 0.58,
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[10, 10], [900, 20], [880, 780], [40, 800], [10, 10]]],
                    },
                    "properties": {
                        "component_shape_v1": {
                            "fill_ratio": 0.88,
                            "aspect_ratio": 1.1,
                            "touches_frame": False,
                        }
                    },
                }
            ],
            image_width=1024,
            image_height=1024,
            provider="civora_heuristic",
        )

        self.assertEqual(accepted, [])
        self.assertEqual(report["rejected_count"], 1)
        self.assertEqual(report["rejected_by_reason"]["oversized_building_candidate"], 1)

    def test_clean_building_outline_is_closed_simplified_and_scored(self) -> None:
        accepted, report = normalize_detection_candidates(
            [
                {
                    "detection_id": "roof-1",
                    "kind": "building",
                    "confidence": 0.55,
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [100, 100], [160, 100], [220, 100], [220, 180],
                            [160, 180], [100, 180], [100, 100],
                        ]],
                    },
                    "properties": {
                        "component_shape_v1": {
                            "fill_ratio": 0.96,
                            "aspect_ratio": 1.5,
                            "touches_frame": False,
                        }
                    },
                }
            ],
            image_width=1024,
            image_height=1024,
            provider="civora_heuristic",
        )

        self.assertEqual(report["accepted_count"], 1)
        ring = accepted[0]["geometry"]["coordinates"][0]
        self.assertEqual(ring[0], ring[-1])
        self.assertLessEqual(len(ring), 6)
        quality = accepted[0]["properties"]["geometry_quality_v1"]
        self.assertEqual(quality["status"], "usable_review_candidate")
        self.assertGreaterEqual(quality["quality_score"], 0.55)
        self.assertTrue(quality["review_edit_supported"])

    def test_road_region_becomes_centerline_with_width_trace(self) -> None:
        accepted, report = normalize_detection_candidates(
            [
                {
                    "detection_id": "road-1",
                    "kind": "road",
                    "confidence": 0.5,
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0, 430], [1024, 440], [1024, 490], [0, 480], [0, 430]]],
                    },
                    "properties": {
                        "component_shape_v1": {
                            "fill_ratio": 0.92,
                            "aspect_ratio": 18.0,
                            "touches_frame": True,
                        }
                    },
                }
            ],
            image_width=1024,
            image_height=1024,
            provider="civora_heuristic",
        )

        self.assertEqual(report["accepted_count"], 1)
        self.assertEqual(accepted[0]["geometry"]["type"], "LineString")
        self.assertGreater(accepted[0]["properties"]["corridor_width_px"], 0)
        self.assertEqual(
            accepted[0]["properties"]["geometry_fidelity"],
            "derived_centerline_from_visual_region",
        )

    def test_quality_trace_reaches_review_candidate_and_corrected_draft(self) -> None:
        quality = {
            "status": "usable_review_candidate",
            "quality_score": 0.81,
            "cleanup_actions": ["closed_polygon"],
            "review_edit_supported": True,
        }
        map_report = build_map_feature_detection_report(
            image_detections=[
                {
                    "detection_id": "roof-2",
                    "kind": "building",
                    "confidence": 0.61,
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[10, 10], [50, 10], [50, 40], [10, 40], [10, 10]]],
                    },
                    "properties": {"geometry_quality_v1": quality},
                }
            ]
        )
        candidate = map_report["feature_candidates"][0]
        self.assertEqual(candidate["properties"]["outline_quality_score"], 0.81)
        self.assertTrue(candidate["properties"]["outline_edit_supported"])

        meta = {"map_feature_detection_report_v1": map_report}
        inbox = build_candidate_review_inbox(meta)
        corrected = {
            "type": "Polygon",
            "coordinates": [[[100, 100], [160, 100], [160, 140], [100, 140], [100, 100]]],
        }
        result = apply_candidate_review_decision(
            {**meta, "candidate_review_inbox_v1": inbox},
            candidate_ids=[candidate["candidate_id"]],
            action="redraw",
            reviewer_id="reviewer-1",
            corrected_feature_type="building_footprint",
            corrected_geometry=corrected,
            correction_coordinate_space="project_local",
        )
        draft = result["accepted_drafts"][0]
        self.assertEqual(draft["geometry"], corrected)
        self.assertEqual(draft["correction_coordinate_space"], "project_local")
        self.assertEqual(draft["vision_correction_action"], "redraw")


if __name__ == "__main__":
    unittest.main()
