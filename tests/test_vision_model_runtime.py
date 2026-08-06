from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from vision.model_runtime import LearnedVisionRuntime, VisionModelRuntimeError


class _TensorRecord:
    def __init__(self, name: str) -> None:
        self.name = name


class _DetectionSession:
    def get_inputs(self):
        return [_TensorRecord("images")]

    def get_outputs(self):
        return [_TensorRecord("boxes"), _TensorRecord("scores"), _TensorRecord("class_ids"), _TensorRecord("masks")]

    def run(self, names, feeds):
        self.last_input = feeds["images"]
        masks = np.zeros((3, 100, 100), dtype=np.float32)
        masks[0, 20:80, 10:60] = 1
        masks[1, 22:78, 12:58] = 1
        masks[2, 5:15, 5:95] = 1
        return [
            np.asarray([[10, 20, 60, 80], [12, 22, 58, 78], [5, 5, 95, 15]], dtype=np.float32),
            np.asarray([0.92, 0.70, 0.88], dtype=np.float32),
            np.asarray([1, 1, 2], dtype=np.int64),
            masks,
        ]


class _SemanticSession:
    def get_inputs(self):
        return [_TensorRecord("images")]

    def get_outputs(self):
        return [_TensorRecord("logits")]

    def run(self, names, feeds):
        logits = np.full((1, 3, 32, 32), -4.0, dtype=np.float32)
        logits[:, 0, :, :] = 1.0
        logits[:, 1, 5:17, 4:15] = 8.0
        logits[:, 2, 23:27, 2:30] = 8.0
        return [logits]


class _MultiConfidenceSemanticSession:
    def get_inputs(self):
        return [_TensorRecord("images")]

    def get_outputs(self):
        return [_TensorRecord("logits")]

    def run(self, names, feeds):
        logits = np.full((1, 3, 32, 32), -4.0, dtype=np.float32)
        logits[:, 0, :, :] = 1.0
        logits[:, 1, 0:8, 2:10] = 3.0
        logits[:, 1, 20:30, 18:30] = 8.0
        return [logits]


def _image_bytes(width: int = 200, height: int = 100) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), (120, 130, 140)).save(buffer, format="PNG")
    return buffer.getvalue()


class VisionModelRuntimeTests(unittest.TestCase):
    def _runtime(self, root: Path, *, adapter: str, session) -> LearnedVisionRuntime:
        model = root / "model.onnx"
        model.write_bytes(b"fixture-onnx-weights")
        outputs = (
            {"logits": "logits", "background_class_id": 0}
            if adapter == "civora_semantic_v1"
            else {
                "boxes": "boxes",
                "scores": "scores",
                "class_ids": "class_ids",
                "masks": "masks",
                "box_format": "xyxy",
                "box_coordinate_space": "input_pixels",
            }
        )
        manifest = {
            "version": "civora_vision_model_manifest_v1",
            "model_name": "fixture-model",
            "model_version": "v1",
            "format": "onnx",
            "adapter": adapter,
            "artifact": {
                "weights_path": model.name,
                "weights_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
            },
            "classes": {"0": "background", "1": "building", "2": "road"},
            "input": {
                "name": "images",
                "width": 100 if adapter == "civora_detection_v1" else 64,
                "height": 100 if adapter == "civora_detection_v1" else 64,
                "layout": "NCHW",
            },
            "outputs": outputs,
            "thresholds": {
                "confidence": 0.45,
                "nms_iou": 0.5,
                "mask": 0.5,
                "minimum_component_pixels": 5,
            },
            "promotion": {"status": "approved_for_review_candidates"},
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return LearnedVisionRuntime(
            manifest_path=manifest_path,
            session_factory=lambda _: session,
        )

    def test_detection_runtime_scales_geometry_and_runs_class_aware_nms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = _DetectionSession()
            runtime = self._runtime(Path(directory), adapter="civora_detection_v1", session=session)
            result = runtime.detect(_image_bytes())

        self.assertEqual(result.model_name, "fixture-model")
        self.assertEqual(len(result.detections), 2)
        building = next(item for item in result.detections if item["kind"] == "building")
        self.assertEqual(building["bbox"], [20.0, 20.0, 100.0, 60.0])
        self.assertEqual(building["properties"]["geometry_fidelity"], "segmentation_mask")
        self.assertEqual(session.last_input.shape, (1, 3, 100, 100))

    def test_semantic_runtime_polygonizes_irregular_class_regions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = self._runtime(Path(directory), adapter="civora_semantic_v1", session=_SemanticSession())
            result = runtime.detect(_image_bytes(128, 128))

        self.assertEqual({item["kind"] for item in result.detections}, {"building", "road"})
        self.assertTrue(all(item["properties"]["geometry_fidelity"] == "semantic_segmentation" for item in result.detections))
        self.assertTrue(all(item["geometry"]["type"] in {"Polygon", "MultiPolygon"} for item in result.detections))

    def test_semantic_runtime_scores_each_connected_component_independently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = self._runtime(
                Path(directory),
                adapter="civora_semantic_v1",
                session=_MultiConfidenceSemanticSession(),
            )
            result = runtime.detect(_image_bytes(128, 128), requested_kinds={"building"})

        self.assertEqual(len(result.detections), 2)
        low, high = sorted(result.detections, key=lambda item: item["confidence"])
        self.assertGreater(high["confidence"] - low["confidence"], 0.1)
        self.assertTrue(low["properties"]["component_touches_frame_edge"])
        self.assertFalse(high["properties"]["component_touches_frame_edge"])
        self.assertEqual(low["properties"]["component_pixel_count"], 64)
        self.assertEqual(high["properties"]["component_pixel_count"], 120)
        self.assertEqual(low["confidence"], low["properties"]["component_mean_probability"])

    def test_semantic_confidence_filters_components_without_reshaping_the_mask(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initial = self._runtime(
                root,
                adapter="civora_semantic_v1",
                session=_MultiConfidenceSemanticSession(),
            )
            manifest = json.loads(initial.manifest_path.read_text(encoding="utf-8"))
            manifest["thresholds"]["confidence"] = 0.95
            initial.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            runtime = LearnedVisionRuntime(
                manifest_path=initial.manifest_path,
                session_factory=lambda _: _MultiConfidenceSemanticSession(),
            )
            result = runtime.detect(_image_bytes(128, 128), requested_kinds={"building"})

        self.assertEqual(len(result.detections), 1)
        detection = result.detections[0]
        self.assertEqual(detection["properties"]["component_pixel_count"], 120)
        self.assertEqual(detection["bbox"], [72.0, 80.0, 48.0, 40.0])

    def test_runtime_tiles_large_imagery_without_losing_global_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initial = self._runtime(root, adapter="civora_detection_v1", session=_DetectionSession())
            manifest = json.loads(initial.manifest_path.read_text(encoding="utf-8"))
            manifest["inference"] = {"tile_mode": "auto", "tile_overlap": 0.2}
            initial.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            runtime = LearnedVisionRuntime(
                manifest_path=initial.manifest_path,
                session_factory=lambda _: _DetectionSession(),
            )
            result = runtime.detect(_image_bytes(240, 100))

        self.assertTrue(all(item["properties"]["tiled_inference"] for item in result.detections))
        self.assertTrue(all(item["properties"]["inference_tile_count"] == 3 for item in result.detections))
        self.assertTrue(any(float(item["bbox"][0]) > 100 for item in result.detections))

    def test_runtime_rejects_unpromoted_or_tampered_weights(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = self._runtime(root, adapter="civora_detection_v1", session=_DetectionSession())
            manifest_path = runtime.manifest_path
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["promotion"]["status"] = "candidate_blocked"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(VisionModelRuntimeError, "not approved"):
                LearnedVisionRuntime(manifest_path=manifest_path, session_factory=lambda _: _DetectionSession())

            manifest["promotion"]["status"] = "approved_for_review_candidates"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            (root / "model.onnx").write_bytes(b"tampered")
            with self.assertRaisesRegex(VisionModelRuntimeError, "fingerprint"):
                LearnedVisionRuntime(manifest_path=manifest_path, session_factory=lambda _: _DetectionSession())


if __name__ == "__main__":
    unittest.main()
