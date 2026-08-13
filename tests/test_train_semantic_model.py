from __future__ import annotations

import unittest

from vision.train_semantic_model import build_class_split_coverage, build_class_weight_values


class TrainSemanticModelTests(unittest.TestCase):
    def test_inverse_sqrt_class_weights_reduce_dominant_foreground_class(self) -> None:
        weights = build_class_weight_values(
            [1_000_000, 100_000, 400_000, 1_600_000],
            background_weight=0.25,
            mode="inverse_sqrt",
        )

        self.assertEqual(weights[0], 0.25)
        self.assertGreater(weights[1], weights[2])
        self.assertGreater(weights[2], weights[3])
        self.assertEqual(build_class_weight_values([5, 2, 9], background_weight=2.0, mode="uniform"), [1.0, 1.0, 1.0])

    def test_class_split_coverage_blocks_declared_class_missing_from_test(self) -> None:
        payload = {
            "categories": [
                {"id": 1, "name": "building"},
                {"id": 2, "name": "road"},
                {"id": 3, "name": "water"},
            ],
            "images": [
                {"id": 1, "split": "train"},
                {"id": 2, "split": "validation"},
                {"id": 3, "split": "test"},
            ],
            "annotations": [
                {"image_id": image_id, "category_id": category_id}
                for image_id in (1, 2, 3)
                for category_id in (1, 2)
            ]
            + [
                {"image_id": 1, "category_id": 3},
                {"image_id": 2, "category_id": 3},
            ],
        }

        coverage = build_class_split_coverage(payload)

        self.assertFalse(coverage["ready"])
        self.assertEqual(
            coverage["blockers"],
            ["declared_class_missing_from_split:test:water"],
        )

    def test_class_split_coverage_accepts_every_class_in_every_split(self) -> None:
        payload = {
            "categories": [{"id": 1, "name": "building"}, {"id": 2, "name": "road"}],
            "images": [
                {"id": 1, "split": "train"},
                {"id": 2, "split": "validation"},
                {"id": 3, "split": "test"},
            ],
            "annotations": [
                {"image_id": image_id, "category_id": category_id}
                for image_id in (1, 2, 3)
                for category_id in (1, 2)
            ],
        }

        coverage = build_class_split_coverage(payload)

        self.assertTrue(coverage["ready"])
        self.assertEqual(coverage["blockers"], [])


if __name__ == "__main__":
    unittest.main()
