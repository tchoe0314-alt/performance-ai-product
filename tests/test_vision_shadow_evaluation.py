from __future__ import annotations

import json
import unittest

from backend.planning.vision_shadow_evaluation import build_shadow_comparison_report, build_shadow_status_report


class VisionShadowEvaluationTests(unittest.TestCase):
    def test_shadow_report_is_aggregate_only_and_class_aware(self) -> None:
        baseline = [
            {"kind": "building", "bbox": [10, 10, 20, 20]},
            {"kind": "road", "bbox": [0, 60, 100, 12]},
        ]
        shadow = [
            {"kind": "building", "bbox": [11, 11, 20, 20]},
            {"kind": "building", "bbox": [70, 10, 10, 10]},
            {"kind": "road", "bbox": [0, 60, 100, 12]},
        ]

        report = build_shadow_comparison_report(
            baseline,
            shadow,
            baseline_provider="civora_heuristic",
            shadow_model={"model_name": "candidate", "model_version": "v1", "model_sha256": "a" * 64},
        )

        self.assertEqual(report["matched_count"], 2)
        self.assertEqual(report["per_class"]["building"]["count_delta"], 1)
        self.assertFalse(report["influenced_user_candidates"])
        self.assertFalse(report["contains_shadow_geometry"])
        self.assertNotIn("bbox", json.dumps(report))
        self.assertNotIn("coordinates", json.dumps(report))

    def test_failed_shadow_report_cannot_imply_quality_or_influence(self) -> None:
        report = build_shadow_status_report("failed", reason="model unavailable")

        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["quality_claim_allowed"])
        self.assertFalse(report["influenced_user_candidates"])


if __name__ == "__main__":
    unittest.main()
