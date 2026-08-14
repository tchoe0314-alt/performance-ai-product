from __future__ import annotations

import unittest

from vision.train_semantic_model import (
    build_class_split_coverage,
    build_class_weight_values,
    held_out_test_image_count,
    semantic_annotation_priority,
    training_split_usage_contract,
)


class TrainSemanticModelTests(unittest.TestCase):
    def test_training_run_contract_declares_frozen_test_non_use(self) -> None:
        contract = training_split_usage_contract()

        self.assertEqual(contract["test_images_loaded_during_training"], 0)
        self.assertEqual(contract["test_image_bytes_loaded_during_training"], 0)
        self.assertEqual(contract["test_annotations_loaded_during_training"], 0)
        self.assertFalse(contract["test_labels_inspected_for_training_coverage"])
        self.assertEqual(contract["test_images_used_for_checkpoint_selection"], 0)
        self.assertEqual(contract["test_images_used_for_threshold_selection"], 0)
        self.assertTrue(contract["test_split_manifest_only_access"])
        self.assertTrue(contract["frozen_test_split_untouched"])

    def test_held_out_count_comes_from_manifest_without_test_records(self) -> None:
        self.assertEqual(
            held_out_test_image_count(
                {
                    "held_out_test_manifest": {"test_image_count": 45},
                    "splits": {"test": []},
                }
            ),
            45,
        )

    def test_semantic_mask_priority_keeps_buildings_above_weak_road_corridors(self) -> None:
        self.assertLess(semantic_annotation_priority("road"), semantic_annotation_priority("surface_water"))
        self.assertLess(semantic_annotation_priority("surface_water"), semantic_annotation_priority("building"))

    def test_surface_water_aliases_share_one_priority(self) -> None:
        self.assertEqual(semantic_annotation_priority("surface_water"), semantic_annotation_priority("water"))
        self.assertEqual(semantic_annotation_priority("surface_water"), semantic_annotation_priority("basin"))

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

        coverage = build_class_split_coverage(
            payload,
            required_splits=("train", "validation", "test"),
        )

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

        coverage = build_class_split_coverage(
            payload,
            required_splits=("train", "validation", "test"),
        )

        self.assertTrue(coverage["ready"])
        self.assertEqual(coverage["blockers"], [])

    def test_training_coverage_never_reads_test_labels(self) -> None:
        payload = {
            "categories": [{"id": 1, "name": "building"}, {"id": 2, "name": "road"}],
            "images": [
                {"id": 1, "split": "train"},
                {"id": 2, "split": "validation"},
                {"id": 3, "split": "test"},
            ],
            "annotations": [
                {"image_id": 1, "category_id": 1},
                {"image_id": 1, "category_id": 2},
                {"image_id": 2, "category_id": 1},
                {"image_id": 2, "category_id": 2},
            ],
        }

        coverage = build_class_split_coverage(payload)

        self.assertTrue(coverage["ready"])
        self.assertEqual(coverage["required_splits"], ["train", "validation"])
        self.assertNotIn("test", coverage["counts"])


if __name__ == "__main__":
    unittest.main()
