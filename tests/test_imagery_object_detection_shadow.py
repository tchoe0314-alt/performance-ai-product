from __future__ import annotations

import unittest

from backend.planning.imagery_object_detection import fetch_imagery_object_detection


class _Response:
    def raise_for_status(self) -> None:
        return None

    def json(self):
        return {
            "status": "detected",
            "provider": "civora_heuristic",
            "detections": [{"kind": "building", "bbox": [1, 2, 3, 4], "confidence": 0.7}],
            "civora_vision_shadow_report_v1": {
                "version": "civora_vision_shadow_report_v1",
                "status": "ready",
                "baseline_count": 1,
                "shadow_count": 2,
                "matched_count": 1,
                "influenced_user_candidates": False,
                "contains_shadow_geometry": False,
            },
        }


class _Session:
    def post(self, *args, **kwargs):
        return _Response()


class ImageryObjectDetectionShadowTests(unittest.TestCase):
    def test_shadow_aggregate_propagates_without_becoming_a_candidate(self) -> None:
        report = fetch_imagery_object_detection(
            address="fixture",
            provider_url="https://gateway.example/detect",
            session=_Session(),
        )

        shadow = report["civora_vision_shadow_report_v1"]
        self.assertEqual(report["detection_count"], 1)
        self.assertEqual(shadow["status"], "ready")
        self.assertFalse(shadow["influenced_user_candidates"])
        self.assertEqual(len(report["detections"]), 1)


if __name__ == "__main__":
    unittest.main()
