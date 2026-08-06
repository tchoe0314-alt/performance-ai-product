from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image


MODEL_MANIFEST_VERSION = "civora_vision_model_manifest_v1"
SUPPORTED_ADAPTERS = {"civora_detection_v1", "civora_semantic_v1"}
PROMOTED_STATUS = "approved_for_review_candidates"


class VisionModelRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeDetectionResult:
    detections: List[Dict[str, Any]]
    image_width: int
    image_height: int
    model_name: str
    model_version: str
    model_sha256: str


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_model_manifest(path: str | Path) -> Dict[str, Any]:
    manifest_path = Path(path).expanduser().resolve()
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise VisionModelRuntimeError(f"Vision model manifest not found: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise VisionModelRuntimeError(f"Vision model manifest is invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise VisionModelRuntimeError("Vision model manifest must be a JSON object.")
    return value


class LearnedVisionRuntime:
    """Loads a promoted ONNX detector with Civora's stable output contract.

    The model must expose boxes, scores, and class IDs. Masks are optional. This
    adapter deliberately avoids guessing arbitrary model output shapes: export
    training models through the Civora detection wrapper before deployment.
    """

    def __init__(
        self,
        *,
        manifest_path: str | Path,
        model_path: str | Path | None = None,
        session_factory: Optional[Callable[[str], Any]] = None,
        require_promoted: bool = True,
    ) -> None:
        self.manifest_path = Path(manifest_path).expanduser().resolve()
        self.manifest = load_model_manifest(self.manifest_path)
        artifact = _dict(self.manifest.get("artifact"))
        configured_path = str(model_path or artifact.get("weights_path") or "").strip()
        if not configured_path:
            raise VisionModelRuntimeError("Vision model manifest is missing artifact.weights_path.")
        candidate = Path(configured_path).expanduser()
        self.model_path = (candidate if candidate.is_absolute() else self.manifest_path.parent / candidate).resolve()
        self.require_promoted = require_promoted
        self._session_factory = session_factory or _default_session_factory
        self._session: Any = None
        self._session_lock = threading.Lock()
        self._model_sha256 = ""
        self._validate_static_contract()

    @property
    def model_name(self) -> str:
        return str(self.manifest.get("model_name") or "unnamed_vision_model")

    @property
    def model_version(self) -> str:
        return str(self.manifest.get("model_version") or "unversioned")

    @property
    def classes(self) -> Dict[int, str]:
        values = _dict(self.manifest.get("classes"))
        result: Dict[int, str] = {}
        for key, label in values.items():
            try:
                class_id = int(key)
            except (TypeError, ValueError):
                continue
            normalized = _normalize_kind(str(label))
            if normalized:
                result[class_id] = normalized
        return result

    def health(self, *, load_session: bool = True) -> Dict[str, Any]:
        try:
            if load_session:
                self._get_session()
            return {
                "ready": True,
                "provider": "civora_learned",
                "capability_level": "learned_model_review_candidates",
                "manifest_version": MODEL_MANIFEST_VERSION,
                "model_name": self.model_name,
                "model_version": self.model_version,
                "model_sha256": self._model_sha256,
                "adapter": str(self.manifest.get("adapter")),
                "classes": [self.classes[key] for key in sorted(self.classes)],
                "tile_mode": str(_dict(self.manifest.get("inference")).get("tile_mode") or "disabled"),
                "promotion_status": str(_dict(self.manifest.get("promotion")).get("status") or "unpromoted"),
            }
        except Exception as exc:
            return {
                "ready": False,
                "provider": "civora_learned",
                "capability_level": "model_unavailable",
                "manifest_version": MODEL_MANIFEST_VERSION,
                "model_name": self.model_name,
                "model_version": self.model_version,
                "error": str(exc),
            }

    def detect(
        self,
        image_bytes: bytes,
        *,
        requested_kinds: Optional[Iterable[str]] = None,
    ) -> RuntimeDetectionResult:
        if not image_bytes:
            raise VisionModelRuntimeError("Source image response was empty.")
        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            raise VisionModelRuntimeError(f"Source image could not be decoded: {exc}") from exc
        original_width, original_height = image.size
        input_config = _dict(self.manifest.get("input"))
        input_width = max(32, int(float(input_config.get("width") or 1024)))
        input_height = max(32, int(float(input_config.get("height") or 1024)))
        inference = _dict(self.manifest.get("inference"))
        tile_mode = str(inference.get("tile_mode") or "disabled").strip().lower()
        use_tiles = tile_mode in {"auto", "enabled", "true", "on"} and (
            original_width > input_width or original_height > input_height
        )
        if use_tiles:
            overlap = _bounded_float(inference.get("tile_overlap"), default=0.2, low=0.0, high=0.75)
            x_origins = _tile_origins(original_width, min(input_width, original_width), overlap)
            y_origins = _tile_origins(original_height, min(input_height, original_height), overlap)
            detections: List[Dict[str, Any]] = []
            tile_count = len(x_origins) * len(y_origins)
            for tile_y in y_origins:
                for tile_x in x_origins:
                    tile = image.crop(
                        (
                            tile_x,
                            tile_y,
                            min(original_width, tile_x + input_width),
                            min(original_height, tile_y + input_height),
                        )
                    )
                    for detection in self._detect_image(tile, requested_kinds=requested_kinds):
                        rec = dict(detection)
                        bbox = list(rec.get("bbox") or [])
                        if len(bbox) >= 4:
                            bbox[0] = round(float(bbox[0]) + tile_x, 3)
                            bbox[1] = round(float(bbox[1]) + tile_y, 3)
                            rec["bbox"] = bbox
                        rec["geometry"] = _shift_geometry(_dict(rec.get("geometry")), offset_x=tile_x, offset_y=tile_y)
                        rec["properties"] = {
                            **_dict(rec.get("properties")),
                            "tiled_inference": True,
                            "inference_tile_origin": [tile_x, tile_y],
                            "inference_tile_count": tile_count,
                        }
                        detections.append(rec)
            thresholds = _dict(self.manifest.get("thresholds"))
            detections = _merge_tiled_detections(
                detections,
                iou_threshold=_bounded_float(thresholds.get("nms_iou"), default=0.5, low=0.0, high=1.0),
                limit=max(1, min(1000, int(float(thresholds.get("max_detections") or 200)))),
            )
        else:
            detections = self._detect_image(image, requested_kinds=requested_kinds)
            for rec in detections:
                rec["properties"] = {
                    **_dict(rec.get("properties")),
                    "tiled_inference": False,
                    "inference_tile_count": 1,
                }
        for ordinal, detection in enumerate(detections, start=1):
            detection["detection_id"] = f"{self.model_name}_{self.model_version}_{ordinal}"
        return RuntimeDetectionResult(
            detections=detections,
            image_width=original_width,
            image_height=original_height,
            model_name=self.model_name,
            model_version=self.model_version,
            model_sha256=self._model_sha256,
        )

    def _detect_image(
        self,
        image: Image.Image,
        *,
        requested_kinds: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        original_width, original_height = image.size
        tensor, input_width, input_height = self._prepare_input(image)
        session = self._get_session()
        input_name = str(_dict(self.manifest.get("input")).get("name") or session.get_inputs()[0].name)
        output_records = list(session.get_outputs())
        output_names = [str(item.name) for item in output_records]
        raw_values = session.run(output_names, {input_name: tensor})
        values = {name: value for name, value in zip(output_names, raw_values)}
        output_contract = _dict(self.manifest.get("outputs"))
        thresholds = _dict(self.manifest.get("thresholds"))
        confidence_threshold = _bounded_float(thresholds.get("confidence"), default=0.45, low=0.0, high=1.0)
        nms_threshold = _bounded_float(thresholds.get("nms_iou"), default=0.5, low=0.0, high=1.0)
        mask_threshold = _bounded_float(thresholds.get("mask"), default=0.5, low=0.0, high=1.0)
        max_detections = max(1, min(1000, int(float(thresholds.get("max_detections") or 200))))
        requested = {_normalize_kind(value) for value in requested_kinds or [] if _normalize_kind(value)}
        masks: Optional[np.ndarray] = None
        if str(self.manifest.get("adapter")) == "civora_semantic_v1":
            logits_name = str(output_contract.get("logits") or "logits")
            candidates = _semantic_candidates(
                values.get(logits_name),
                classes=self.classes,
                input_width=input_width,
                input_height=input_height,
                confidence_threshold=confidence_threshold,
                mask_threshold=mask_threshold,
                minimum_component_pixels=max(1, int(float(thresholds.get("minimum_component_pixels") or 24))),
                background_class_id=int(float(output_contract.get("background_class_id") or 0)),
                requested=requested,
            )
        else:
            boxes = _matrix(values.get(str(output_contract.get("boxes") or "boxes")), columns=4)
            scores = _vector(values.get(str(output_contract.get("scores") or "scores")), dtype=float)
            class_ids = _vector(values.get(str(output_contract.get("class_ids") or "class_ids")), dtype=int)
            masks_name = str(output_contract.get("masks") or "masks")
            masks = _masks(values.get(masks_name)) if masks_name in values else None
            count = min(len(boxes), len(scores), len(class_ids))
            candidates = []
            coordinate_space = str(output_contract.get("box_coordinate_space") or "input_pixels").strip().lower()
            box_format = str(output_contract.get("box_format") or "xyxy").strip().lower()
            for index in range(count):
                confidence = float(scores[index])
                class_id = int(class_ids[index])
                kind = self.classes.get(class_id, "")
                if confidence < confidence_threshold or not kind or (requested and kind not in requested):
                    continue
                xyxy = _box_to_xyxy(boxes[index], box_format=box_format)
                if coordinate_space == "normalized":
                    xyxy = [xyxy[0] * input_width, xyxy[1] * input_height, xyxy[2] * input_width, xyxy[3] * input_height]
                xyxy = _clip_xyxy(xyxy, input_width, input_height)
                if xyxy[2] <= xyxy[0] or xyxy[3] <= xyxy[1]:
                    continue
                candidates.append(
                    {
                        "index": index,
                        "kind": kind,
                        "class_id": class_id,
                        "confidence": confidence,
                        "input_xyxy": xyxy,
                    }
                )
        kept = _class_aware_nms(candidates, iou_threshold=nms_threshold, limit=max_detections)
        detections: List[Dict[str, Any]] = []
        scale_x = original_width / max(input_width, 1)
        scale_y = original_height / max(input_height, 1)
        for ordinal, candidate in enumerate(kept, start=1):
            x0, y0, x1, y1 = candidate["input_xyxy"]
            original_box = [x0 * scale_x, y0 * scale_y, x1 * scale_x, y1 * scale_y]
            bbox = [
                round(original_box[0], 3),
                round(original_box[1], 3),
                round(original_box[2] - original_box[0], 3),
                round(original_box[3] - original_box[1], 3),
            ]
            geometry = None
            fidelity = "bounding_box_only"
            source_index = int(candidate["index"])
            if candidate.get("input_geometry"):
                geometry = _scale_geometry(candidate["input_geometry"], scale_x=scale_x, scale_y=scale_y)
                fidelity = "semantic_segmentation"
            elif masks is not None and source_index < len(masks):
                mask = np.asarray(masks[source_index], dtype=np.float32)
                if str(output_contract.get("mask_activation") or "none").lower() == "sigmoid":
                    mask = 1.0 / (1.0 + np.exp(-np.clip(mask, -30.0, 30.0)))
                geometry = _mask_geometry(mask >= mask_threshold, original_width, original_height)
                if geometry:
                    fidelity = "segmentation_mask"
            if geometry is None:
                geometry = _box_polygon(original_box)
            detections.append(
                {
                    "detection_id": f"{self.model_name}_{self.model_version}_{ordinal}",
                    "kind": candidate["kind"],
                    "bbox": bbox,
                    "geometry": geometry,
                    "confidence": round(float(candidate["confidence"]), 6),
                    "provider": "civora_learned",
                    "properties": {
                        "class_id": int(candidate["class_id"]),
                        "geometry_fidelity": fidelity,
                        "image_width": original_width,
                        "image_height": original_height,
                        "model_name": self.model_name,
                        "model_version": self.model_version,
                        "model_sha256": self._model_sha256,
                        **_dict(candidate.get("component_quality")),
                    },
                }
            )
        return detections

    def _validate_static_contract(self) -> None:
        if str(self.manifest.get("version")) != MODEL_MANIFEST_VERSION:
            raise VisionModelRuntimeError(f"Unsupported vision model manifest version; expected {MODEL_MANIFEST_VERSION}.")
        if str(self.manifest.get("format") or "").lower() != "onnx":
            raise VisionModelRuntimeError("Only ONNX vision model artifacts are accepted by this runtime.")
        if str(self.manifest.get("adapter") or "") not in SUPPORTED_ADAPTERS:
            raise VisionModelRuntimeError("Vision model adapter is unsupported.")
        if not self.classes:
            raise VisionModelRuntimeError("Vision model manifest must define at least one class.")
        required_outputs = _dict(self.manifest.get("outputs"))
        if str(self.manifest.get("adapter")) == "civora_semantic_v1":
            if not required_outputs.get("logits"):
                raise VisionModelRuntimeError("Semantic vision model manifest must name its logits output.")
        elif not all(required_outputs.get(key) for key in ("boxes", "scores", "class_ids")):
            raise VisionModelRuntimeError("Vision model manifest must name boxes, scores, and class_ids outputs.")
        promotion = _dict(self.manifest.get("promotion"))
        if self.require_promoted and promotion.get("status") != PROMOTED_STATUS:
            raise VisionModelRuntimeError("Vision model is not approved for review-candidate inference.")
        if not self.model_path.is_file():
            raise VisionModelRuntimeError(f"Vision model weights not found: {self.model_path}")
        actual_hash = file_sha256(self.model_path)
        expected_hash = str(_dict(self.manifest.get("artifact")).get("weights_sha256") or "").lower()
        if not expected_hash:
            raise VisionModelRuntimeError("Vision model manifest is missing artifact.weights_sha256.")
        if actual_hash.lower() != expected_hash:
            raise VisionModelRuntimeError("Vision model weights fingerprint does not match the promoted manifest.")
        self._model_sha256 = actual_hash

    def _get_session(self) -> Any:
        if self._session is not None:
            return self._session
        with self._session_lock:
            if self._session is None:
                try:
                    self._session = self._session_factory(str(self.model_path))
                except VisionModelRuntimeError:
                    raise
                except Exception as exc:
                    raise VisionModelRuntimeError(f"Vision model runtime failed to load: {exc}") from exc
        return self._session

    def _prepare_input(self, image: Image.Image) -> Tuple[np.ndarray, int, int]:
        config = _dict(self.manifest.get("input"))
        width = max(32, int(float(config.get("width") or 1024)))
        height = max(32, int(float(config.get("height") or 1024)))
        resized = image.resize((width, height), Image.Resampling.BILINEAR)
        values = np.asarray(resized, dtype=np.float32)
        normalization = _dict(config.get("normalization"))
        values *= float(normalization.get("scale") if normalization.get("scale") is not None else 1.0 / 255.0)
        mean = np.asarray(normalization.get("mean") or [0.0, 0.0, 0.0], dtype=np.float32)
        std = np.asarray(normalization.get("std") or [1.0, 1.0, 1.0], dtype=np.float32)
        if mean.size != 3 or std.size != 3 or np.any(std == 0):
            raise VisionModelRuntimeError("Vision model normalization mean/std must each contain three non-zero channels.")
        values = (values - mean) / std
        layout = str(config.get("layout") or "NCHW").upper()
        if layout == "NCHW":
            values = np.transpose(values, (2, 0, 1))[None, ...]
        elif layout == "NHWC":
            values = values[None, ...]
        else:
            raise VisionModelRuntimeError("Vision model input layout must be NCHW or NHWC.")
        return np.ascontiguousarray(values, dtype=np.float32), width, height


def runtime_from_environment(*, session_factory: Optional[Callable[[str], Any]] = None) -> LearnedVisionRuntime:
    manifest_path = str(os.getenv("CIVORA_GATEWAY_MODEL_MANIFEST") or "").strip()
    if not manifest_path:
        raise VisionModelRuntimeError("CIVORA_GATEWAY_MODEL_MANIFEST is required for learned detection.")
    model_path = str(os.getenv("CIVORA_GATEWAY_MODEL_PATH") or "").strip() or None
    require_promoted = str(os.getenv("CIVORA_GATEWAY_REQUIRE_PROMOTED_MODEL") or "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    return LearnedVisionRuntime(
        manifest_path=manifest_path,
        model_path=model_path,
        session_factory=session_factory,
        require_promoted=require_promoted,
    )


def _default_session_factory(model_path: str) -> Any:
    try:
        import onnxruntime as ort
    except Exception as exc:  # pragma: no cover - deployment dependency guard
        raise VisionModelRuntimeError("onnxruntime is required for learned imagery detection.") from exc
    return ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])


def _matrix(value: Any, *, columns: int) -> np.ndarray:
    array = np.asarray(value)
    while array.ndim > 2 and array.shape[0] == 1:
        array = array[0]
    if array.ndim != 2 or array.shape[1] != columns:
        raise VisionModelRuntimeError(f"Model output must have shape [N,{columns}].")
    return array.astype(np.float32)


def _vector(value: Any, *, dtype: type) -> np.ndarray:
    array = np.asarray(value)
    while array.ndim > 1 and array.shape[0] == 1:
        array = array[0]
    if array.ndim != 1:
        raise VisionModelRuntimeError("Model score/class output must have shape [N].")
    return array.astype(np.int64 if dtype is int else np.float32)


def _masks(value: Any) -> Optional[np.ndarray]:
    array = np.asarray(value)
    while array.ndim > 3 and array.shape[0] == 1:
        array = array[0]
    if array.ndim != 3:
        raise VisionModelRuntimeError("Model mask output must have shape [N,H,W].")
    return array.astype(np.float32)


def _semantic_candidates(
    value: Any,
    *,
    classes: Dict[int, str],
    input_width: int,
    input_height: int,
    confidence_threshold: float,
    mask_threshold: float,
    minimum_component_pixels: int,
    background_class_id: int,
    requested: set[str],
) -> List[Dict[str, Any]]:
    logits = np.asarray(value, dtype=np.float32)
    while logits.ndim > 3 and logits.shape[0] == 1:
        logits = logits[0]
    if logits.ndim != 3:
        raise VisionModelRuntimeError("Semantic model logits must have shape [C,H,W].")
    shifted = logits - np.max(logits, axis=0, keepdims=True)
    probabilities = np.exp(np.clip(shifted, -30.0, 30.0))
    probabilities /= np.maximum(np.sum(probabilities, axis=0, keepdims=True), 1e-12)
    assigned = np.argmax(probabilities, axis=0)
    mask_height, mask_width = assigned.shape
    try:
        from affine import Affine
        from rasterio.features import shapes
    except Exception as exc:
        raise VisionModelRuntimeError("rasterio is required to polygonize semantic model output.") from exc
    transform = Affine.scale(input_width / max(mask_width, 1), input_height / max(mask_height, 1))
    candidates: List[Dict[str, Any]] = []
    ordinal = 0
    for class_id, kind in sorted(classes.items()):
        if class_id == background_class_id or kind in {"", "background"} or (requested and kind not in requested):
            continue
        if class_id < 0 or class_id >= probabilities.shape[0]:
            continue
        class_probabilities = probabilities[class_id]
        class_mask = (assigned == class_id) & (class_probabilities >= mask_threshold)
        if not np.any(class_mask):
            continue
        component_labels, component_stats = _label_connected_components(class_mask, class_probabilities)
        for geometry, component_value in shapes(
            component_labels,
            mask=component_labels > 0,
            transform=transform,
        ):
            component_id = int(component_value)
            stats = component_stats.get(component_id)
            if not stats or geometry.get("type") not in {"Polygon", "MultiPolygon"}:
                continue
            if int(stats["pixel_count"]) < minimum_component_pixels:
                continue
            if float(stats["mean_probability"]) < confidence_threshold:
                continue
            xyxy = _geometry_xyxy(geometry)
            if not xyxy:
                continue
            ordinal += 1
            candidates.append(
                {
                    "index": ordinal,
                    "kind": kind,
                    "class_id": class_id,
                    "confidence": float(stats["mean_probability"]),
                    "input_xyxy": _clip_xyxy(xyxy, input_width, input_height),
                    "input_geometry": geometry,
                    "component_quality": {
                        "component_pixel_count": int(stats["pixel_count"]),
                        "component_mean_probability": round(float(stats["mean_probability"]), 6),
                        "component_max_probability": round(float(stats["max_probability"]), 6),
                        "component_touches_frame_edge": bool(stats["touches_frame_edge"]),
                    },
                }
            )
    return candidates


def _label_connected_components(
    mask: np.ndarray,
    probabilities: np.ndarray,
) -> Tuple[np.ndarray, Dict[int, Dict[str, Any]]]:
    if mask.ndim != 2 or probabilities.shape != mask.shape:
        raise VisionModelRuntimeError("Semantic component inputs must use matching two-dimensional shapes.")
    height, width = mask.shape
    labels = np.zeros((height, width), dtype=np.int32)
    stats: Dict[int, Dict[str, Any]] = {}
    component_id = 0
    for start_y, start_x in np.argwhere(mask):
        y = int(start_y)
        x = int(start_x)
        if labels[y, x] != 0:
            continue
        component_id += 1
        labels[y, x] = component_id
        stack = [(y, x)]
        pixel_count = 0
        probability_sum = 0.0
        max_probability = 0.0
        touches_frame_edge = False
        while stack:
            current_y, current_x = stack.pop()
            probability = float(probabilities[current_y, current_x])
            pixel_count += 1
            probability_sum += probability
            max_probability = max(max_probability, probability)
            touches_frame_edge = touches_frame_edge or (
                current_y == 0
                or current_x == 0
                or current_y == height - 1
                or current_x == width - 1
            )
            for next_y, next_x in (
                (current_y - 1, current_x),
                (current_y + 1, current_x),
                (current_y, current_x - 1),
                (current_y, current_x + 1),
            ):
                if (
                    0 <= next_y < height
                    and 0 <= next_x < width
                    and bool(mask[next_y, next_x])
                    and labels[next_y, next_x] == 0
                ):
                    labels[next_y, next_x] = component_id
                    stack.append((next_y, next_x))
        stats[component_id] = {
            "pixel_count": pixel_count,
            "mean_probability": probability_sum / max(pixel_count, 1),
            "max_probability": max_probability,
            "touches_frame_edge": touches_frame_edge,
        }
    return labels, stats


def _box_to_xyxy(box: Sequence[float], *, box_format: str) -> List[float]:
    values = [float(item) for item in box]
    if box_format == "xyxy":
        return values
    if box_format == "xywh":
        return [values[0], values[1], values[0] + values[2], values[1] + values[3]]
    if box_format == "cxcywh":
        return [
            values[0] - values[2] / 2.0,
            values[1] - values[3] / 2.0,
            values[0] + values[2] / 2.0,
            values[1] + values[3] / 2.0,
        ]
    raise VisionModelRuntimeError("Vision model box_format must be xyxy, xywh, or cxcywh.")


def _clip_xyxy(box: Sequence[float], width: int, height: int) -> List[float]:
    return [
        max(0.0, min(float(width), float(box[0]))),
        max(0.0, min(float(height), float(box[1]))),
        max(0.0, min(float(width), float(box[2]))),
        max(0.0, min(float(height), float(box[3]))),
    ]


def _class_aware_nms(candidates: List[Dict[str, Any]], *, iou_threshold: float, limit: int) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    for candidate in sorted(candidates, key=lambda item: float(item["confidence"]), reverse=True):
        if any(
            candidate["kind"] == prior["kind"]
            and _xyxy_iou(candidate["input_xyxy"], prior["input_xyxy"]) > iou_threshold
            for prior in kept
        ):
            continue
        kept.append(candidate)
        if len(kept) >= limit:
            break
    return kept


def _tile_origins(length: int, tile_length: int, overlap: float) -> List[int]:
    if length <= tile_length:
        return [0]
    stride = max(1, int(round(tile_length * (1.0 - overlap))))
    origins = list(range(0, max(1, length - tile_length + 1), stride))
    final_origin = max(0, length - tile_length)
    if not origins or origins[-1] != final_origin:
        origins.append(final_origin)
    return sorted(set(origins))


def _merge_tiled_detections(
    detections: List[Dict[str, Any]],
    *,
    iou_threshold: float,
    limit: int,
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for index, detection in enumerate(detections):
        bbox = list(detection.get("bbox") or [])
        if len(bbox) < 4:
            continue
        x, y, width, height = [float(value) for value in bbox[:4]]
        candidates.append(
            {
                "index": index,
                "kind": str(detection.get("kind") or ""),
                "confidence": float(detection.get("confidence") or 0),
                "input_xyxy": [x, y, x + width, y + height],
                "record": detection,
            }
        )
    return [
        dict(item["record"])
        for item in _class_aware_nms(candidates, iou_threshold=iou_threshold, limit=limit)
    ]


def _xyxy_iou(a: Sequence[float], b: Sequence[float]) -> float:
    left = max(float(a[0]), float(b[0]))
    top = max(float(a[1]), float(b[1]))
    right = min(float(a[2]), float(b[2]))
    bottom = min(float(a[3]), float(b[3]))
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    area_a = max(0.0, float(a[2]) - float(a[0])) * max(0.0, float(a[3]) - float(a[1]))
    area_b = max(0.0, float(b[2]) - float(b[0])) * max(0.0, float(b[3]) - float(b[1]))
    return intersection / max(area_a + area_b - intersection, 1e-12)


def _mask_geometry(mask: np.ndarray, width: int, height: int) -> Optional[Dict[str, Any]]:
    if mask.ndim != 2 or not np.any(mask):
        return None
    try:
        from affine import Affine
        from rasterio.features import shapes

        transform = Affine.scale(width / max(mask.shape[1], 1), height / max(mask.shape[0], 1))
        geometries = [
            geometry
            for geometry, value in shapes(mask.astype(np.uint8), mask=mask, transform=transform)
            if int(value) == 1 and geometry.get("type") in {"Polygon", "MultiPolygon"}
        ]
        if geometries:
            return max(geometries, key=_geometry_area_hint)
    except Exception:
        pass
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    x0 = float(xs.min()) * width / max(mask.shape[1], 1)
    y0 = float(ys.min()) * height / max(mask.shape[0], 1)
    x1 = float(xs.max() + 1) * width / max(mask.shape[1], 1)
    y1 = float(ys.max() + 1) * height / max(mask.shape[0], 1)
    return _box_polygon([x0, y0, x1, y1])


def _geometry_area_hint(geometry: Dict[str, Any]) -> float:
    points: List[Tuple[float, float]] = []

    def collect(value: Any) -> None:
        if isinstance(value, (list, tuple)) and len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
            points.append((float(value[0]), float(value[1])))
        elif isinstance(value, (list, tuple)):
            for item in value:
                collect(item)

    collect(geometry.get("coordinates"))
    if not points:
        return 0.0
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


def _geometry_xyxy(geometry: Dict[str, Any]) -> Optional[List[float]]:
    points: List[Tuple[float, float]] = []

    def collect(value: Any) -> None:
        if isinstance(value, (list, tuple)) and len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
            points.append((float(value[0]), float(value[1])))
        elif isinstance(value, (list, tuple)):
            for item in value:
                collect(item)

    collect(geometry.get("coordinates"))
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def _scale_geometry(geometry: Dict[str, Any], *, scale_x: float, scale_y: float) -> Dict[str, Any]:
    def scale(value: Any) -> Any:
        if (
            isinstance(value, (list, tuple))
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            return [round(float(value[0]) * scale_x, 3), round(float(value[1]) * scale_y, 3)]
        if isinstance(value, (list, tuple)):
            return [scale(item) for item in value]
        return value

    return {"type": str(geometry.get("type") or "Polygon"), "coordinates": scale(geometry.get("coordinates"))}


def _shift_geometry(geometry: Dict[str, Any], *, offset_x: float, offset_y: float) -> Dict[str, Any]:
    if not geometry:
        return {}

    def shift(value: Any) -> Any:
        if (
            isinstance(value, (list, tuple))
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            return [round(float(value[0]) + offset_x, 3), round(float(value[1]) + offset_y, 3)]
        if isinstance(value, (list, tuple)):
            return [shift(item) for item in value]
        return value

    return {"type": str(geometry.get("type") or "Polygon"), "coordinates": shift(geometry.get("coordinates"))}


def _box_polygon(box: Sequence[float]) -> Dict[str, Any]:
    x0, y0, x1, y1 = [round(float(item), 3) for item in box]
    return {
        "type": "Polygon",
        "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
    }


def _bounded_float(value: Any, *, default: float, low: float, high: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(low, min(high, parsed))


def _normalize_kind(value: str) -> str:
    text = value.strip().lower().replace("_", " ").replace("-", " ")
    if "building" in text or "roof" in text or "structure" in text:
        return "building"
    if "road" in text or "street" in text or text == "row":
        return "road"
    if "drive" in text:
        return "driveway"
    if "parking" in text or "stall" in text:
        return "parking"
    if "sidewalk" in text or "walkway" in text or "pedestrian" in text:
        return "sidewalk"
    if "tree" in text or "canopy" in text or "landscape" in text:
        return "tree"
    if "basin" in text or "pond" in text or "detention" in text or "water" in text:
        return "basin"
    if "utility" in text or "hydrant" in text or "manhole" in text or "inlet" in text:
        return "utility"
    if "open" in text or "grass" in text or "vegetation" in text:
        return "open_space"
    return text.replace(" ", "_")


def _dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


__all__ = [
    "LearnedVisionRuntime",
    "MODEL_MANIFEST_VERSION",
    "PROMOTED_STATUS",
    "RuntimeDetectionResult",
    "VisionModelRuntimeError",
    "file_sha256",
    "load_model_manifest",
    "runtime_from_environment",
]
