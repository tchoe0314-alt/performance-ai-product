from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds

from backend.planning.vision_benchmark_dataset import import_spacenet2_building_benchmark


class VisionBenchmarkDatasetTests(unittest.TestCase):
    def test_spacenet_import_preserves_attestation_and_disjoint_splits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            region = root / "AOI_2_Vegas_Train"
            images = region / "RGB-PanSharpen"
            labels = region / "geojson" / "buildings"
            images.mkdir(parents=True)
            labels.mkdir(parents=True)
            for index in range(10):
                suffix = f"AOI_2_Vegas_img{index}"
                image_path = images / f"RGB-PanSharpen_{suffix}.tif"
                self._write_raster(image_path, value=200 + index)
                self._write_labels(labels / f"buildings_{suffix}.geojson")

            result = import_spacenet2_building_benchmark(root, Path(directory) / "output")

            self.assertEqual(result["eligible_image_count"], 10)
            self.assertEqual(result["annotation_count"], 10)
            self.assertEqual({key: len(value) for key, value in result["splits"].items()}, {"train": 7, "validation": 1, "test": 2})
            self.assertFalse(set(result["splits"]["train"]) & set(result["splits"]["test"]))
            self.assertEqual(result["supervision_status"], "independent_benchmark_annotated")
            self.assertTrue(result["ground_truth_attestation"]["independent_test_split"])
            self.assertEqual(result["evaluation_scope"]["geography_count"], 1)
            self.assertEqual(result["evaluation_scope"]["season_count"], 0)
            self.assertEqual(len(result["dataset_fingerprint"]), 64)
            self.assertTrue((Path(result["image_root"]) / result["images"][0]["file_name"]).is_file())
            self.assertGreater(result["annotations"][0]["area"], 1.0)
            training = json.loads(Path(result["training_validation_package_path"]).read_text())
            evaluation = json.loads(Path(result["frozen_test_package_path"]).read_text())
            reservation = json.loads(Path(result["evaluation_reservation_manifest_path"]).read_text())
            self.assertEqual(training["dataset_role"], "training_and_validation")
            self.assertEqual(training["splits"]["test"], [])
            self.assertFalse(training["test_records_in_package"])
            self.assertEqual(evaluation["dataset_role"], "frozen_test")
            self.assertEqual(evaluation["splits"]["train"], [])
            self.assertFalse(evaluation["training_records_in_package"])
            self.assertEqual(
                reservation["evaluation_dataset_fingerprint"],
                evaluation["dataset_fingerprint"],
            )

    def test_missing_matching_label_is_reported_not_invented(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            region = root / "AOI_3_Paris_Train"
            images = region / "RGB-PanSharpen"
            labels = region / "geojson" / "buildings"
            images.mkdir(parents=True)
            labels.mkdir(parents=True)
            self._write_raster(images / "RGB-PanSharpen_AOI_3_Paris_img1.tif", value=500)
            self._write_raster(images / "RGB-PanSharpen_AOI_3_Paris_img2.tif", value=600)
            self._write_labels(labels / "buildings_AOI_3_Paris_img1.geojson")

            result = import_spacenet2_building_benchmark(root, Path(directory) / "output")

            self.assertEqual(result["eligible_image_count"], 1)
            self.assertEqual(result["excluded_example_count"], 1)
            self.assertIn("matching_spacenet_building_labels_missing", result["excluded_examples"][0]["blockers"])
            self.assertEqual(result["training_validation_package_path"], "")
            self.assertTrue(result["split_artifact_blockers"])

    @staticmethod
    def _write_raster(path: Path, *, value: int) -> None:
        data = np.zeros((3, 64, 64), dtype=np.uint16)
        data[0] = value
        data[1] = value + 100
        data[2] = value + 200
        data[:, 8:56, 8:56] += np.arange(48, dtype=np.uint16)[None, None, :]
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            width=64,
            height=64,
            count=3,
            dtype="uint16",
            crs="EPSG:4326",
            transform=from_bounds(-1.0, 0.0, 0.0, 1.0, 64, 64),
        ) as dataset:
            dataset.write(data)

    @staticmethod
    def _write_labels(path: Path) -> None:
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"OBJECTID": 1},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[-0.75, 0.75], [-0.25, 0.75], [-0.25, 0.25], [-0.75, 0.25], [-0.75, 0.75]]],
                    },
                }
            ],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
